// Package integration is the blockchain side of the QFabric integration
// contract: Go mirrors of the crypto service's JSON (docs/API_CONTRACT.md)
// and an HTTP client for it.
//
// Keep these structs in lockstep with quantum-pqc/api/schemas.py. The
// contract test in blockchain/tests strict-decodes integration/*.json into
// them, so drift fails CI.
package integration

// Organization mirrors OrganizationResponse.
type Organization struct {
	OrgID       string `json:"orgId"`
	DisplayName string `json:"displayName"`
	MSPID       string `json:"mspId"`
	Role        string `json:"role"`
	Algorithm   string `json:"algorithm"`
	PublicKey   string `json:"publicKey"` // base64, raw 1952-byte ML-DSA-65 key
	PublicKeyID string `json:"publicKeyId"`
	CreatedAt   string `json:"createdAt"`
}

// RegisterOrganizationRequest mirrors the request of
// POST /api/v1/organizations/register.
type RegisterOrganizationRequest struct {
	OrgID       string `json:"orgId"`
	DisplayName string `json:"displayName"`
	MSPID       string `json:"mspId"`
	Role        string `json:"role"`
}

// SecureTransferRequest mirrors the request of POST /api/v1/secure-transfer.
// Pointer fields are optional and omitted when nil (service defaults apply).
type SecureTransferRequest struct {
	Sender               string   `json:"sender"`
	Receiver             string   `json:"receiver"`
	Document             string   `json:"document"` // base64
	Filename             *string  `json:"filename,omitempty"`
	Compression          string   `json:"compression,omitempty"`
	NumQubits            *int     `json:"numQubits,omitempty"`
	SampleFraction       *float64 `json:"sampleFraction,omitempty"`
	ChannelErrorRate     *float64 `json:"channelErrorRate,omitempty"`
	SimulateEavesdropper bool     `json:"simulateEavesdropper"`
	InterceptionRate     *float64 `json:"interceptionRate,omitempty"`
	Seed                 *int64   `json:"seed,omitempty"`
	IncludeCiphertext    bool     `json:"includeCiphertext"`
}

// AuditManifest mirrors the signed manifest. It is passed to the chaincode
// verbatim (as JSON); the chaincode rebuilds the canonical bytes itself.
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

// SignatureEnvelope carries the ML-DSA-65 signature over the manifest.
type SignatureEnvelope struct {
	Algorithm   string `json:"algorithm"`
	Signer      string `json:"signer"`
	PublicKeyID string `json:"publicKeyId"`
	Value       string `json:"value"` // base64, raw 3309-byte signature
}

// EncryptedPayload is returned only when includeCiphertext was requested.
type EncryptedPayload struct {
	Nonce      string `json:"nonce"`
	Ciphertext string `json:"ciphertext"`
}

// SecureTransferResponse mirrors the response of POST /api/v1/secure-transfer.
//
// Only AuditManifest and Signature are submitted to the ledger. The
// summary fields (MLDSAVerified, SecurityStatus, ...) are informational:
// the chaincode never trusts them and recomputes its own verdict.
type SecureTransferResponse struct {
	SessionID             string            `json:"sessionId"`
	Sender                string            `json:"sender"`
	Receiver              string            `json:"receiver"`
	MLDSAVerified         bool              `json:"mldsaVerified"`
	BB84Status            string            `json:"bb84Status"`
	AbortReason           *string           `json:"abortReason"`
	QBER                  float64           `json:"qber"`
	QBERThreshold         float64           `json:"qberThreshold"`
	EncryptionAlgorithm   string            `json:"encryptionAlgorithm"`
	Compression           string            `json:"compression"`
	OriginalSize          int64             `json:"originalSize"`
	CompressedSize        *int64            `json:"compressedSize"`
	CompressionRatio      *float64          `json:"compressionRatio"`
	DocumentHash          string            `json:"documentHash"`
	EncryptedDocumentHash *string           `json:"encryptedDocumentHash"`
	TranscriptHash        string            `json:"transcriptHash"`
	SecurityStatus        string            `json:"securityStatus"`
	Timestamp             string            `json:"timestamp"`
	AuditManifest         AuditManifest     `json:"auditManifest"`
	Signature             SignatureEnvelope `json:"signature"`
	EncryptedPayload      *EncryptedPayload `json:"encryptedPayload"`
}

// HealthResponse mirrors GET /api/v1/health.
type HealthResponse struct {
	Status     string            `json:"status"`
	Service    string            `json:"service"`
	Version    string            `json:"version"`
	Components map[string]string `json:"components"`
	Versions   map[string]string `json:"versions,omitempty"`
}

// APIError mirrors the error envelope {"error": {...}}.
type APIError struct {
	HTTPStatus int            `json:"-"`
	Code       string         `json:"code"`
	Message    string         `json:"message"`
	Details    map[string]any `json:"details,omitempty"`
}

func (e *APIError) Error() string {
	return "crypto API " + e.Code + ": " + e.Message
}
