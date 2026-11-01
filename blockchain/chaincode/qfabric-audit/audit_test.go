package main

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
	"testing"
)

// vectorPath points at the shared cross-language ML-DSA-65 test vector.
// The Python service verifies the same file with liboqs.
var vectorPath = filepath.Join("..", "..", "..", "integration", "test_vectors", "mldsa65_audit_manifest.json")

type testVector struct {
	PublicKey         string        `json:"publicKey"`
	PublicKeyID       string        `json:"publicKeyId"`
	Manifest          AuditManifest `json:"manifest"`
	CanonicalManifest string        `json:"canonicalManifest"`
	Signature         string        `json:"signature"`
}

func loadVector(t *testing.T) (testVector, []byte, []byte) {
	t.Helper()
	raw, err := os.ReadFile(vectorPath)
	if err != nil {
		t.Fatalf("read test vector: %v", err)
	}
	var v testVector
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("parse test vector: %v", err)
	}
	pk, err := base64.StdEncoding.DecodeString(v.PublicKey)
	if err != nil {
		t.Fatalf("decode public key: %v", err)
	}
	sig, err := base64.StdEncoding.DecodeString(v.Signature)
	if err != nil {
		t.Fatalf("decode signature: %v", err)
	}
	return v, pk, sig
}

func TestCanonicalManifestMatchesContract(t *testing.T) {
	v, _, _ := loadVector(t)
	if got := string(v.Manifest.CanonicalBytes()); got != v.CanonicalManifest {
		t.Fatalf("canonical manifest mismatch\n got: %q\nwant: %q", got, v.CanonicalManifest)
	}
}

func TestVectorSignatureVerifies(t *testing.T) {
	v, pk, sig := loadVector(t)
	if PublicKeyID(pk) != v.PublicKeyID || v.Manifest.SenderKeyID != v.PublicKeyID {
		t.Fatalf("public key id mismatch")
	}
	if err := v.Manifest.Validate(); err != nil {
		t.Fatalf("vector manifest should be valid: %v", err)
	}
	if err := verifyMLDSA65(pk, v.Manifest.CanonicalBytes(), sig); err != nil {
		t.Fatalf("vector signature should verify: %v", err)
	}
	if reasons := v.Manifest.PolicyViolations(); len(reasons) != 0 {
		t.Fatalf("vector manifest should be VERIFIED, got %v", reasons)
	}
}

func TestTamperedManifestFailsVerification(t *testing.T) {
	v, pk, sig := loadVector(t)

	tampered := v.Manifest
	tampered.QBERPpm = 10_000 // attacker "improves" the reported QBER
	if err := verifyMLDSA65(pk, tampered.CanonicalBytes(), sig); err == nil {
		t.Fatal("tampered manifest must not verify")
	}

	badSig := slices.Clone(sig)
	badSig[100] ^= 0x01
	if err := verifyMLDSA65(pk, v.Manifest.CanonicalBytes(), badSig); err == nil {
		t.Fatal("tampered signature must not verify")
	}
}

func TestValidateRejectsMalformedManifests(t *testing.T) {
	v, _, _ := loadVector(t)
	cases := map[string]func(m *AuditManifest){
		"newline injection":     func(m *AuditManifest) { m.SessionID = "abc\nsender=OrgC" },
		"uppercase hex":         func(m *AuditManifest) { m.DocumentHash = "ABCDEF" + m.DocumentHash[6:] },
		"unknown bb84 status":   func(m *AuditManifest) { m.BB84Status = "MAYBE" },
		"qber out of range":     func(m *AuditManifest) { m.QBERPpm = 1_000_001 },
		"same sender/receiver":  func(m *AuditManifest) { m.Receiver = m.Sender },
		"non-UTC timestamp":     func(m *AuditManifest) { m.Timestamp = "2026-11-01T10:00:00+01:00" },
		"ciphertext on abort":   func(m *AuditManifest) { m.BB84Status = BB84Aborted },
		"unsupported algorithm": func(m *AuditManifest) { m.EncryptionAlgorithm = "AES-128-CBC" },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			m := v.Manifest
			mutate(&m)
			if err := m.Validate(); err == nil {
				t.Fatalf("expected validation error")
			}
		})
	}
}

func TestPolicyViolations(t *testing.T) {
	v, _, _ := loadVector(t)

	eavesdropped := v.Manifest
	eavesdropped.BB84Status = BB84Aborted
	eavesdropped.QBERPpm = 250_000
	eavesdropped.EncryptionAlgorithm = EncryptionNone
	eavesdropped.EncryptedDocumentHash = ""
	if err := eavesdropped.Validate(); err != nil {
		t.Fatalf("aborted manifest is structurally valid: %v", err)
	}
	got := eavesdropped.PolicyViolations()
	for _, want := range []string{"BB84_NOT_SUCCESSFUL", "QBER_EXCEEDS_THRESHOLD"} {
		if !slices.Contains(got, want) {
			t.Errorf("missing reason %s in %v", want, got)
		}
	}

	loose := v.Manifest
	loose.QBERThresholdPpm = 200_000
	if !slices.Contains(loose.PolicyViolations(), "QBER_THRESHOLD_ABOVE_POLICY") {
		t.Error("threshold above ledger policy must be rejected")
	}
}
