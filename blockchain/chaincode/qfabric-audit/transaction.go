package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Contract constants. These values are part of the integration contract
// (docs/API_CONTRACT.md) and must match the Quantum/PQC service exactly.
const (
	// ManifestHeader is the first line of every canonical audit manifest.
	// It doubles as a domain-separation tag for the ML-DSA signature.
	ManifestHeader = "QFABRIC-AUDIT-MANIFEST-V1"

	SignatureAlgorithm = "ML-DSA-65"

	EncryptionAESGCM = "AES-256-GCM"
	EncryptionNone   = "NONE"

	BB84Success = "SUCCESS"
	BB84Aborted = "ABORTED"

	StatusVerified = "VERIFIED"
	StatusRejected = "REJECTED"

	// MaxQBERThresholdPpm is the highest QBER threshold the ledger accepts
	// (11%, the standard BB84 bound for one-way error correction and privacy
	// amplification). A manifest that claims a looser threshold is rejected.
	MaxQBERThresholdPpm = 110_000

	// MinFinalKeyLength is the minimum BB84 output (bits) needed to derive a
	// 256-bit AES key.
	MinFinalKeyLength = 256
)

var (
	reIdentifier = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,128}$`)
	reOrgID      = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)
	reHexDigest  = regexp.MustCompile(`^[0-9a-f]{64}$`)
	reTimestamp  = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`)

	validCompression = map[string]bool{"zstd": true, "gzip": true, "none": true}
)

// AuditManifest is the exact set of fields the sender signs with ML-DSA-65.
// Field names and JSON tags mirror the `auditManifest` object returned by
// POST /api/v1/secure-transfer.
type AuditManifest struct {
	SessionID             string `json:"sessionId"`
	Sender                string `json:"sender"`
	Receiver              string `json:"receiver"`
	SenderKeyID           string `json:"senderKeyId"`
	BB84Status            string `json:"bb84Status"`
	QBERPpm               int64  `json:"qberPpm"`
	QBERThresholdPpm      int64  `json:"qberThresholdPpm"`
	SiftedKeyLength       int64  `json:"siftedKeyLength"`
	FinalKeyLength        int64  `json:"finalKeyLength"`
	TranscriptHash        string `json:"transcriptHash"`
	EncryptionAlgorithm   string `json:"encryptionAlgorithm"`
	Compression           string `json:"compression"`
	DocumentHash          string `json:"documentHash"`
	EncryptedDocumentHash string `json:"encryptedDocumentHash"`
	Timestamp             string `json:"timestamp"`
}

// CanonicalBytes returns the byte string that is signed and verified.
//
// Format (docs/API_CONTRACT.md §4): the header line followed by one
// `key=value` line per field in the fixed order below, joined with "\n",
// UTF-8, no trailing newline. Validate() guarantees no value contains "\n".
func (m *AuditManifest) CanonicalBytes() []byte {
	lines := []string{
		ManifestHeader,
		"sessionId=" + m.SessionID,
		"sender=" + m.Sender,
		"receiver=" + m.Receiver,
		"senderKeyId=" + m.SenderKeyID,
		"bb84Status=" + m.BB84Status,
		"qberPpm=" + strconv.FormatInt(m.QBERPpm, 10),
		"qberThresholdPpm=" + strconv.FormatInt(m.QBERThresholdPpm, 10),
		"siftedKeyLength=" + strconv.FormatInt(m.SiftedKeyLength, 10),
		"finalKeyLength=" + strconv.FormatInt(m.FinalKeyLength, 10),
		"transcriptHash=" + m.TranscriptHash,
		"encryptionAlgorithm=" + m.EncryptionAlgorithm,
		"compression=" + m.Compression,
		"documentHash=" + m.DocumentHash,
		"encryptedDocumentHash=" + m.EncryptedDocumentHash,
		"timestamp=" + m.Timestamp,
	}
	return []byte(strings.Join(lines, "\n"))
}

// Validate performs structural validation. A manifest that fails here is
// malformed and must be refused (the transaction errors, nothing is written).
func (m *AuditManifest) Validate() error {
	checks := []struct {
		name string
		ok   bool
	}{
		{"sessionId", reIdentifier.MatchString(m.SessionID)},
		{"sender", reOrgID.MatchString(m.Sender)},
		{"receiver", reOrgID.MatchString(m.Receiver)},
		{"senderKeyId", reHexDigest.MatchString(m.SenderKeyID)},
		{"bb84Status", m.BB84Status == BB84Success || m.BB84Status == BB84Aborted},
		{"qberPpm", m.QBERPpm >= 0 && m.QBERPpm <= 1_000_000},
		{"qberThresholdPpm", m.QBERThresholdPpm > 0 && m.QBERThresholdPpm <= 1_000_000},
		{"siftedKeyLength", m.SiftedKeyLength >= 0},
		{"finalKeyLength", m.FinalKeyLength >= 0},
		{"transcriptHash", reHexDigest.MatchString(m.TranscriptHash)},
		{"encryptionAlgorithm", m.EncryptionAlgorithm == EncryptionAESGCM || m.EncryptionAlgorithm == EncryptionNone},
		{"compression", validCompression[m.Compression]},
		{"documentHash", reHexDigest.MatchString(m.DocumentHash)},
		{"encryptedDocumentHash", m.EncryptedDocumentHash == "" || reHexDigest.MatchString(m.EncryptedDocumentHash)},
		{"timestamp", reTimestamp.MatchString(m.Timestamp)},
	}
	for _, c := range checks {
		if !c.ok {
			return fmt.Errorf("invalid audit manifest field %q", c.name)
		}
	}
	if m.Sender == m.Receiver {
		return fmt.Errorf("invalid audit manifest: sender and receiver must differ")
	}
	// Encrypting after an aborted key exchange is a protocol violation, not
	// a policy outcome: refuse it outright.
	if m.BB84Status == BB84Aborted && (m.EncryptionAlgorithm != EncryptionNone || m.EncryptedDocumentHash != "") {
		return fmt.Errorf("invalid audit manifest: ciphertext reported for an aborted BB84 session")
	}
	return nil
}

// PolicyViolations evaluates the ledger's security policy on a structurally
// valid, signature-verified manifest. An empty result means VERIFIED;
// otherwise the record is stored as REJECTED with these reasons.
func (m *AuditManifest) PolicyViolations() []string {
	var reasons []string
	if m.BB84Status != BB84Success {
		reasons = append(reasons, "BB84_NOT_SUCCESSFUL")
	}
	if m.QBERThresholdPpm > MaxQBERThresholdPpm {
		reasons = append(reasons, "QBER_THRESHOLD_ABOVE_POLICY")
	}
	if m.QBERPpm > m.QBERThresholdPpm || m.QBERPpm > MaxQBERThresholdPpm {
		reasons = append(reasons, "QBER_EXCEEDS_THRESHOLD")
	}
	if m.BB84Status == BB84Success && m.FinalKeyLength < MinFinalKeyLength {
		reasons = append(reasons, "INSUFFICIENT_KEY_MATERIAL")
	}
	if m.BB84Status == BB84Success && (m.EncryptionAlgorithm != EncryptionAESGCM || m.EncryptedDocumentHash == "") {
		reasons = append(reasons, "DOCUMENT_NOT_ENCRYPTED")
	}
	return reasons
}

// AuditRecord is what the ledger stores for each secure transaction.
// It contains hashes and security metadata only: never plaintext documents,
// private keys, or BB84 shared secrets.
type AuditRecord struct {
	DocType       string `json:"docType"` // always "auditRecord"
	TransactionID string `json:"transactionId"`

	Manifest AuditManifest `json:"manifest"`

	// Derived and verified by the chaincode, never copied from client input.
	QBER             float64  `json:"qber"`          // QBERPpm / 1e6, for readability
	MLDSAVerified    bool     `json:"mldsaVerified"` // set only after verifyMLDSA65 succeeds
	SignatureAlg     string   `json:"signatureAlgorithm"`
	Signature        string   `json:"signature"` // base64; kept for independent re-verification
	SecurityStatus   string   `json:"securityStatus"`
	RejectionReasons []string `json:"rejectionReasons,omitempty" metadata:",optional"`

	// Fabric-level (MSP / ECDSA) context. Distinct from ML-DSA authentication.
	SenderMSPID    string `json:"senderMspId"`
	SubmitterMSPID string `json:"submitterMspId"`
	FabricTxID     string `json:"fabricTxId"`
	RecordedAt     string `json:"recordedAt"` // transaction timestamp (deterministic)
}

// VerificationResult is returned by VerifyTransactionRecord.
type VerificationResult struct {
	TransactionID    string `json:"transactionId"`
	SignatureValid   bool   `json:"signatureValid"`
	StoredStatus     string `json:"storedStatus"`
	RecomputedStatus string `json:"recomputedStatus"`
	Consistent       bool   `json:"consistent"`
}
