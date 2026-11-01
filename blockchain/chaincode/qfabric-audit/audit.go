package main

import (
	"errors"
	"fmt"

	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// AuditContract exposes the QFabric chaincode functions.
type AuditContract struct {
	contractapi.Contract
}

var errNotImplemented = errors.New("not implemented yet")

// Composite-key object types. Kept here so every function uses the same
// key layout.
const (
	keyOrganization = "org"     // org~<orgId>            -> Organization
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
// TODO(blockchain):
//  1. Refuse if tx~transactionID or session~manifest.sessionId already
//     exists (replay protection: one ledger record per signed manifest).
//  2. Strict-decode manifestJSON (json.Decoder + DisallowUnknownFields),
//     then manifest.Validate().
//  3. Load the sender Organization; require
//     manifest.SenderKeyID == org.PublicKeyID.
//  4. Require ctx.GetClientIdentity().GetMSPID() == org.MSPID (the sender
//     records its own transfer through its own Fabric identity).
//  5. verifyMLDSA65(orgPublicKey, manifest.CanonicalBytes(), signature).
//     On failure return an error; an unauthenticated manifest is never
//     written to the ledger.
//  6. reasons := manifest.PolicyViolations();
//     status = VERIFIED if empty, else REJECTED.
//  7. Build AuditRecord (MLDSAVerified=true, QBER=QBERPpm/1e6,
//     FabricTxID=stub.GetTxID(), RecordedAt from GetTxTimestamp()).
//  8. PutState record + session index; SetEvent("SecureTransactionRecorded").
func (c *AuditContract) RecordSecureTransaction(
	ctx contractapi.TransactionContextInterface,
	transactionID, manifestJSON, signatureB64 string,
) (*AuditRecord, error) {
	return nil, errNotImplemented
}

// GetTransaction returns one audit record.
//
// TODO(blockchain): GetState(tx~transactionID); error if missing.
func (c *AuditContract) GetTransaction(
	ctx contractapi.TransactionContextInterface,
	transactionID string,
) (*AuditRecord, error) {
	return nil, errNotImplemented
}

// GetAllTransactions returns every audit record (demo scale; add pagination
// with GetStateByPartialCompositeKeyWithPagination if the ledger grows).
//
// TODO(blockchain): iterate GetStateByPartialCompositeKey(keyTransaction, nil).
func (c *AuditContract) GetAllTransactions(
	ctx contractapi.TransactionContextInterface,
) ([]*AuditRecord, error) {
	return nil, errNotImplemented
}

// VerifyTransactionRecord independently re-verifies a stored record: it
// re-checks the stored ML-DSA signature against the registered public key
// and recomputes the security status from the stored manifest.
//
// TODO(blockchain): load record + sender org; verifyMLDSA65; recompute
// PolicyViolations(); compare with the stored SecurityStatus.
func (c *AuditContract) VerifyTransactionRecord(
	ctx contractapi.TransactionContextInterface,
	transactionID string,
) (*VerificationResult, error) {
	return nil, errNotImplemented
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
