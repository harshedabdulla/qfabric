package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// AuditContract exposes the QFabric chaincode functions.
type AuditContract struct {
	contractapi.Contract
}

// Composite-key object types. Kept here so every function uses the same
// key layout.
const (
	keyOrganization = "org"     // org~<orgId>            -> Organization
	keyMSP          = "msp"     // msp~<mspId>            -> orgId (one org per MSP)
	keyTransaction  = "tx"      // tx~<transactionId>     -> AuditRecord
	keySession      = "session" // session~<sessionId>   -> transactionId (replay guard)
)

// RecordSecureTransaction verifies a signed audit manifest and stores the
// resulting audit record.
//
// Arguments: transactionID chosen by the client (e.g. "qfabric-tx-001"),
// manifestJSON (the `auditManifest` object from the crypto service), and
// signatureB64 (the `signature.value` field).
//
// Malformed, replayed, mis-attributed or unauthenticated submissions return
// an error and nothing is written. Authenticated manifests that fail the
// security policy are recorded as REJECTED with reasons.
func (c *AuditContract) RecordSecureTransaction(
	ctx contractapi.TransactionContextInterface,
	transactionID, manifestJSON, signatureB64 string,
) (*AuditRecord, error) {
	stub := ctx.GetStub()
	if !reIdentifier.MatchString(transactionID) {
		return nil, fmt.Errorf("invalid transactionId %q", transactionID)
	}

	// 1. Structural validation.
	manifest, err := decodeManifest(manifestJSON)
	if err != nil {
		return nil, err
	}
	if err := manifest.Validate(); err != nil {
		return nil, err
	}
	signature, err := base64.StdEncoding.DecodeString(signatureB64)
	if err != nil {
		return nil, fmt.Errorf("signature must be standard base64: %w", err)
	}

	// 2. Replay protection: one record per transaction ID and per session.
	txKey, err := stub.CreateCompositeKey(keyTransaction, []string{transactionID})
	if err != nil {
		return nil, err
	}
	if exists, err := stateExists(ctx, txKey); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("transaction %s already recorded", transactionID)
	}
	sessionKey, err := stub.CreateCompositeKey(keySession, []string{manifest.SessionID})
	if err != nil {
		return nil, err
	}
	if prior, err := stub.GetState(sessionKey); err != nil {
		return nil, err
	} else if prior != nil {
		return nil, fmt.Errorf("session %s already recorded as transaction %s", manifest.SessionID, prior)
	}

	// 3. Bind the manifest to registered identities.
	sender, err := c.GetOrganization(ctx, manifest.Sender)
	if err != nil {
		return nil, fmt.Errorf("sender: %w", err)
	}
	if _, err := c.GetOrganization(ctx, manifest.Receiver); err != nil {
		return nil, fmt.Errorf("receiver: %w", err)
	}
	if manifest.SenderKeyID != sender.PublicKeyID {
		return nil, fmt.Errorf("senderKeyId does not match the ledger-registered key of %s", sender.OrgID)
	}
	submitterMSP, err := ctx.GetClientIdentity().GetMSPID()
	if err != nil {
		return nil, fmt.Errorf("read caller MSP: %w", err)
	}
	if submitterMSP != sender.MSPID {
		return nil, fmt.Errorf("submitter MSP %s may not record transfers sent by %s (%s)", submitterMSP, sender.OrgID, sender.MSPID)
	}

	// 4. Application-level post-quantum authentication, against the ledger key.
	publicKey, err := base64.StdEncoding.DecodeString(sender.PublicKey)
	if err != nil {
		return nil, fmt.Errorf("stored public key corrupt: %w", err)
	}
	if err := verifyMLDSA65(publicKey, manifest.CanonicalBytes(), signature); err != nil {
		return nil, err
	}

	// 5. Security policy.
	reasons := manifest.PolicyViolations()
	status := StatusVerified
	if len(reasons) > 0 {
		status = StatusRejected
	}
	recordedAt, err := txTimestamp(ctx)
	if err != nil {
		return nil, err
	}
	record := &AuditRecord{
		DocType:          "auditRecord",
		TransactionID:    transactionID,
		Manifest:         *manifest,
		QBER:             float64(manifest.QBERPpm) / 1e6,
		MLDSAVerified:    true,
		SignatureAlg:     SignatureAlgorithm,
		Signature:        signatureB64,
		SecurityStatus:   status,
		RejectionReasons: reasons,
		SenderMSPID:      sender.MSPID,
		SubmitterMSPID:   submitterMSP,
		FabricTxID:       stub.GetTxID(),
		RecordedAt:       recordedAt,
	}

	// 6. Persist record + replay index, emit event.
	if err := putJSON(ctx, txKey, record); err != nil {
		return nil, err
	}
	if err := stub.PutState(sessionKey, []byte(transactionID)); err != nil {
		return nil, err
	}
	event, _ := json.Marshal(map[string]string{
		"transactionId":  transactionID,
		"sessionId":      manifest.SessionID,
		"securityStatus": status,
	})
	if err := stub.SetEvent("SecureTransactionRecorded", event); err != nil {
		return nil, err
	}
	return record, nil
}

// GetTransaction returns one audit record.
func (c *AuditContract) GetTransaction(
	ctx contractapi.TransactionContextInterface,
	transactionID string,
) (*AuditRecord, error) {
	if !reIdentifier.MatchString(transactionID) {
		return nil, fmt.Errorf("invalid transactionId %q", transactionID)
	}
	key, err := ctx.GetStub().CreateCompositeKey(keyTransaction, []string{transactionID})
	if err != nil {
		return nil, err
	}
	var record AuditRecord
	found, err := getJSON(ctx, key, &record)
	if err != nil {
		return nil, err
	}
	if !found {
		return nil, fmt.Errorf("transaction %s not found", transactionID)
	}
	return &record, nil
}

// GetAllTransactions returns every audit record, ordered by transaction ID
// (demo scale; switch to GetStateByPartialCompositeKeyWithPagination if the
// ledger grows).
func (c *AuditContract) GetAllTransactions(
	ctx contractapi.TransactionContextInterface,
) ([]*AuditRecord, error) {
	iter, err := ctx.GetStub().GetStateByPartialCompositeKey(keyTransaction, []string{})
	if err != nil {
		return nil, err
	}
	defer iter.Close()

	records := []*AuditRecord{}
	for iter.HasNext() {
		kv, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var record AuditRecord
		if err := json.Unmarshal(kv.Value, &record); err != nil {
			return nil, fmt.Errorf("corrupt record %q: %w", kv.Key, err)
		}
		records = append(records, &record)
	}
	return records, nil
}

// VerifyTransactionRecord independently re-verifies a stored record: it
// re-checks the stored ML-DSA signature against the registered public key
// and recomputes the security status from the stored manifest. It reports
// the outcome rather than failing, so auditors can see what is inconsistent.
func (c *AuditContract) VerifyTransactionRecord(
	ctx contractapi.TransactionContextInterface,
	transactionID string,
) (*VerificationResult, error) {
	record, err := c.GetTransaction(ctx, transactionID)
	if err != nil {
		return nil, err
	}
	sender, err := c.GetOrganization(ctx, record.Manifest.Sender)
	if err != nil {
		return nil, fmt.Errorf("sender: %w", err)
	}

	signatureValid := false
	publicKey, errKey := base64.StdEncoding.DecodeString(sender.PublicKey)
	signature, errSig := base64.StdEncoding.DecodeString(record.Signature)
	if errKey == nil && errSig == nil && record.Manifest.SenderKeyID == sender.PublicKeyID {
		signatureValid = verifyMLDSA65(publicKey, record.Manifest.CanonicalBytes(), signature) == nil
	}

	recomputed := StatusVerified
	if len(record.Manifest.PolicyViolations()) > 0 {
		recomputed = StatusRejected
	}
	return &VerificationResult{
		TransactionID:    transactionID,
		SignatureValid:   signatureValid,
		StoredStatus:     record.SecurityStatus,
		RecomputedStatus: recomputed,
		Consistent:       signatureValid && recomputed == record.SecurityStatus,
	}, nil
}

// decodeManifest strictly decodes the manifest JSON: unknown fields and
// trailing data are rejected.
func decodeManifest(manifestJSON string) (*AuditManifest, error) {
	dec := json.NewDecoder(bytes.NewReader([]byte(manifestJSON)))
	dec.DisallowUnknownFields()
	var m AuditManifest
	if err := dec.Decode(&m); err != nil {
		return nil, fmt.Errorf("invalid manifest JSON: %w", err)
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return nil, errors.New("invalid manifest JSON: trailing data")
	}
	return &m, nil
}

func stateExists(ctx contractapi.TransactionContextInterface, key string) (bool, error) {
	value, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return value != nil, nil
}

func getJSON(ctx contractapi.TransactionContextInterface, key string, out any) (bool, error) {
	value, err := ctx.GetStub().GetState(key)
	if err != nil || value == nil {
		return false, err
	}
	if err := json.Unmarshal(value, out); err != nil {
		return false, fmt.Errorf("corrupt state at %q: %w", key, err)
	}
	return true, nil
}

func putJSON(ctx contractapi.TransactionContextInterface, key string, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, data)
}

// txTimestamp is the deterministic transaction time (identical on every
// endorsing peer), never the local clock.
func txTimestamp(ctx contractapi.TransactionContextInterface) (string, error) {
	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return "", err
	}
	return ts.AsTime().UTC().Format(time.RFC3339), nil
}

// parseMLDSA65PublicKey decodes a raw FIPS 204 ML-DSA-65 public key.
func parseMLDSA65PublicKey(raw []byte) (*mldsa65.PublicKey, error) {
	if len(raw) != mldsa65.PublicKeySize {
		return nil, fmt.Errorf("ML-DSA-65 public key must be %d bytes, got %d", mldsa65.PublicKeySize, len(raw))
	}
	var pk mldsa65.PublicKey
	if err := pk.UnmarshalBinary(raw); err != nil {
		return nil, fmt.Errorf("invalid ML-DSA-65 public key: %w", err)
	}
	return &pk, nil
}

// verifyMLDSA65 verifies a pure ML-DSA-65 signature with an empty context
// string, matching liboqs' default ML-DSA-65 sign/verify.
func verifyMLDSA65(rawPublicKey, message, signature []byte) error {
	pk, err := parseMLDSA65PublicKey(rawPublicKey)
	if err != nil {
		return err
	}
	if len(signature) != mldsa65.SignatureSize {
		return fmt.Errorf("ML-DSA-65 signature must be %d bytes, got %d", mldsa65.SignatureSize, len(signature))
	}
	if !mldsa65.Verify(pk, message, nil, signature) {
		return errors.New("ML-DSA-65 signature verification failed")
	}
	return nil
}
