// Command mockcrypto is a DEVELOPMENT-ONLY stand-in for the Quantum/PQC
// service. It lets the blockchain side exercise the full client → Gateway →
// chaincode path before quantum-pqc/ is implemented.
//
// What is real:      ML-DSA-65 signatures (CIRCL), canonical manifest,
//
//	HKDF-SHA-256 + gzip + AES-256-GCM, all hashes.
//
// What is simulated: BB84. There is NO quantum simulation here: QBER is drawn
//
//	from a binomial model (≈2% noise, ≈25% with Eve). Never
//	present mock results as BB84 results.
//
// Keys are derived deterministically from the org ID so restarts keep the
// keys registered on the ledger. They are test-only.
//
//	go run ./tools/mockcrypto -addr :8000
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hkdf"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math"
	mrand "math/rand/v2"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/cloudflare/circl/sign/mldsa/mldsa65"

	"qfabric/blockchain/integration"
)

const (
	qberThresholdPpm = 110_000
	finalKeyBits     = 256
	defaultQubits    = 2048
)

type org struct {
	info integration.Organization
	sk   *mldsa65.PrivateKey
}

type server struct {
	mu   sync.Mutex
	orgs map[string]*org
}

func main() {
	addr := flag.String("addr", ":8000", "listen address")
	flag.Parse()
	s := &server{orgs: map[string]*org{}}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/health", s.health)
	mux.HandleFunc("POST /api/v1/organizations/register", s.register)
	mux.HandleFunc("GET /api/v1/organizations/{orgId}", s.getOrg)
	mux.HandleFunc("POST /api/v1/secure-transfer", s.secureTransfer)

	log.Printf("MOCK crypto service (no quantum simulation) listening on %s", *addr)
	log.Fatal(http.ListenAndServe(*addr, mux))
}

func (s *server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, 200, integration.HealthResponse{
		Status: "ok", Service: "qfabric-mock-crypto", Version: "mock",
		Components: map[string]string{"bb84": "mock", "mldsa65": "circl", "aesgcm": "go-stdlib"},
	})
}

func (s *server) register(w http.ResponseWriter, r *http.Request) {
	var req integration.RegisterOrganizationRequest
	if !decode(w, r, &req) {
		return
	}
	if req.OrgID == "" || req.MSPID == "" || req.DisplayName == "" || req.Role == "" {
		apiError(w, 422, "VALIDATION_ERROR", "orgId, displayName, mspId and role are required")
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.orgs[req.OrgID]; ok {
		apiError(w, 409, "ORGANIZATION_EXISTS", "organization "+req.OrgID+" already registered")
		return
	}
	seed := sha256.Sum256([]byte("qfabric-mock-key|" + req.OrgID)) // TEST-ONLY deterministic key
	pk, sk := mldsa65.NewKeyFromSeed(&seed)
	raw, _ := pk.MarshalBinary()
	o := &org{sk: sk, info: integration.Organization{
		OrgID: req.OrgID, DisplayName: req.DisplayName, MSPID: req.MSPID, Role: req.Role,
		Algorithm: "ML-DSA-65", PublicKey: base64.StdEncoding.EncodeToString(raw),
		PublicKeyID: sha256Hex(raw), CreatedAt: nowUTC(),
	}}
	s.orgs[req.OrgID] = o
	writeJSON(w, 201, o.info)
}

func (s *server) getOrg(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	o, ok := s.orgs[r.PathValue("orgId")]
	s.mu.Unlock()
	if !ok {
		apiError(w, 404, "ORGANIZATION_NOT_FOUND", "unknown organization "+r.PathValue("orgId"))
		return
	}
	writeJSON(w, 200, o.info)
}

func (s *server) secureTransfer(w http.ResponseWriter, r *http.Request) {
	var req integration.SecureTransferRequest
	if !decode(w, r, &req) {
		return
	}
	doc, err := base64.StdEncoding.DecodeString(req.Document)
	if err != nil || req.Sender == req.Receiver {
		apiError(w, 422, "VALIDATION_ERROR", "document must be base64 and sender != receiver")
		return
	}
	s.mu.Lock()
	sender, okS := s.orgs[req.Sender]
	_, okR := s.orgs[req.Receiver]
	s.mu.Unlock()
	if !okS || !okR {
		apiError(w, 404, "ORGANIZATION_NOT_FOUND", "sender and receiver must be registered")
		return
	}

	// --- Simulated BB84 statistics (NOT a quantum simulation) ---
	qubits := defaultQubits
	if req.NumQubits != nil {
		qubits = *req.NumQubits
	}
	sifted := qubits/2 + mrand.IntN(41) - 20
	sample := sifted / 4
	errRate := 0.02
	if req.SimulateEavesdropper {
		rate := 1.0
		if req.InterceptionRate != nil {
			rate = *req.InterceptionRate
		}
		errRate += 0.25 * rate
	}
	errors := 0
	for range sample {
		if mrand.Float64() < errRate {
			errors++
		}
	}
	qber := float64(errors) / float64(sample)
	qberPpm := int64(math.Round(qber * 1e6))
	transcript := make([]byte, 64)
	_, _ = rand.Read(transcript)

	sessionID := "qfabric-session-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	resp := integration.SecureTransferResponse{
		SessionID: sessionID, Sender: req.Sender, Receiver: req.Receiver,
		QBER: qber, QBERThreshold: 0.11, Compression: "gzip",
		OriginalSize: int64(len(doc)), DocumentHash: sha256Hex(doc),
		TranscriptHash: sha256Hex(transcript), Timestamp: nowUTC(),
	}
	manifest := integration.AuditManifest{
		SessionID: sessionID, Sender: req.Sender, Receiver: req.Receiver,
		SenderKeyID: sender.info.PublicKeyID, QBERPpm: qberPpm, QBERThresholdPpm: qberThresholdPpm,
		SiftedKeyLength: int64(sifted), TranscriptHash: resp.TranscriptHash,
		Compression: "gzip", DocumentHash: resp.DocumentHash, Timestamp: resp.Timestamp,
	}

	if qberPpm > qberThresholdPpm {
		reason := "QBER_THRESHOLD_EXCEEDED"
		resp.BB84Status, resp.AbortReason = "ABORTED", &reason
		resp.EncryptionAlgorithm, resp.SecurityStatus = "NONE", "REJECTED"
		manifest.BB84Status, manifest.EncryptionAlgorithm = "ABORTED", "NONE"
	} else {
		secret := make([]byte, 32) // stands in for the BB84 shared secret
		_, _ = rand.Read(secret)
		nonce, ciphertext, compressed, err := encrypt(secret, sessionID, req.Sender, req.Receiver, doc)
		if err != nil {
			apiError(w, 500, "INTERNAL_ERROR", "internal error")
			return
		}
		encHash := sha256Hex(append(append([]byte{}, nonce...), ciphertext...))
		size, ratio := int64(compressed), float64(len(doc))/float64(compressed)
		resp.BB84Status, resp.EncryptionAlgorithm, resp.SecurityStatus = "SUCCESS", "AES-256-GCM", "VERIFIED"
		resp.CompressedSize, resp.CompressionRatio, resp.EncryptedDocumentHash = &size, &ratio, &encHash
		manifest.BB84Status, manifest.EncryptionAlgorithm = "SUCCESS", "AES-256-GCM"
		manifest.FinalKeyLength, manifest.EncryptedDocumentHash = finalKeyBits, encHash
		if req.IncludeCiphertext {
			resp.EncryptedPayload = &integration.EncryptedPayload{
				Nonce: base64.StdEncoding.EncodeToString(nonce), Ciphertext: base64.StdEncoding.EncodeToString(ciphertext),
			}
		}
	}

	sig := make([]byte, mldsa65.SignatureSize)
	if err := mldsa65.SignTo(sender.sk, canonical(manifest), nil, true, sig); err != nil {
		apiError(w, 500, "INTERNAL_ERROR", "internal error")
		return
	}
	resp.AuditManifest = manifest
	resp.MLDSAVerified = true
	resp.Signature = integration.SignatureEnvelope{
		Algorithm: "ML-DSA-65", Signer: req.Sender, PublicKeyID: sender.info.PublicKeyID,
		Value: base64.StdEncoding.EncodeToString(sig),
	}
	log.Printf("secure-transfer %s %s->%s bb84=%s qber=%.4f", sessionID, req.Sender, req.Receiver, resp.BB84Status, qber)
	writeJSON(w, 200, resp)
}

// encrypt follows docs/API_CONTRACT.md: HKDF-SHA-256 key, compress, AES-256-GCM.
func encrypt(secret []byte, sessionID, sender, receiver string, doc []byte) (nonce, ciphertext []byte, compressedLen int, err error) {
	key, err := hkdf.Key(sha256.New, secret, []byte(sessionID), "qfabric/v1/aes-256-gcm|"+sender+"|"+receiver, 32)
	if err != nil {
		return nil, nil, 0, err
	}
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	_, _ = zw.Write(doc)
	_ = zw.Close()
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, nil, 0, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, nil, 0, err
	}
	nonce = make([]byte, gcm.NonceSize())
	_, _ = rand.Read(nonce)
	aad := []byte("qfabric/v1|" + sessionID + "|" + sender + "|" + receiver)
	return nonce, gcm.Seal(nil, nonce, buf.Bytes(), aad), buf.Len(), nil
}

// canonical mirrors CanonicalBytes in the chaincode (docs/API_CONTRACT.md §4).
func canonical(m integration.AuditManifest) []byte {
	return []byte(strings.Join([]string{
		"QFABRIC-AUDIT-MANIFEST-V1",
		"sessionId=" + m.SessionID, "sender=" + m.Sender, "receiver=" + m.Receiver,
		"senderKeyId=" + m.SenderKeyID, "bb84Status=" + m.BB84Status,
		fmt.Sprintf("qberPpm=%d", m.QBERPpm), fmt.Sprintf("qberThresholdPpm=%d", m.QBERThresholdPpm),
		fmt.Sprintf("siftedKeyLength=%d", m.SiftedKeyLength), fmt.Sprintf("finalKeyLength=%d", m.FinalKeyLength),
		"transcriptHash=" + m.TranscriptHash, "encryptionAlgorithm=" + m.EncryptionAlgorithm,
		"compression=" + m.Compression, "documentHash=" + m.DocumentHash,
		"encryptedDocumentHash=" + m.EncryptedDocumentHash, "timestamp=" + m.Timestamp,
	}, "\n"))
}

func decode(w http.ResponseWriter, r *http.Request, out any) bool {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 16<<20))
	dec.DisallowUnknownFields()
	if err := dec.Decode(out); err != nil {
		apiError(w, 422, "VALIDATION_ERROR", "request validation failed")
		return false
	}
	return true
}

func apiError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code, "message": msg}})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func sha256Hex(b []byte) string { s := sha256.Sum256(b); return hex.EncodeToString(s[:]) }
func nowUTC() string            { return time.Now().UTC().Format("2006-01-02T15:04:05Z") }
