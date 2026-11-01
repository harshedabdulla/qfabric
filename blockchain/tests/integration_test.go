// Package tests holds cross-module tests for the blockchain side.
//
//	go test ./tests/...                          # contract tests (offline)
//	QFABRIC_E2E=1 go test ./tests/... -run E2E   # needs crypto API + Fabric network
package tests

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"qfabric/blockchain/integration"
)

var integrationDir = filepath.Join("..", "..", "integration")

func strictDecode(t *testing.T, file string, out any) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(integrationDir, file))
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(out); err != nil {
		t.Fatalf("%s does not match Go contract structs: %v", file, err)
	}
}

// TestSampleFilesMatchContract fails when the shared JSON samples and the
// Go mirrors in blockchain/integration drift apart.
func TestSampleFilesMatchContract(t *testing.T) {
	var req integration.SecureTransferRequest
	strictDecode(t, "sample_request.json", &req)

	var resp integration.SecureTransferResponse
	strictDecode(t, "sample_response.json", &resp)

	if resp.AuditManifest.SenderKeyID != resp.Signature.PublicKeyID {
		t.Error("manifest senderKeyId must equal signature.publicKeyId")
	}
	if resp.Signature.Algorithm != "ML-DSA-65" {
		t.Errorf("unexpected algorithm %q", resp.Signature.Algorithm)
	}
}

// TestE2ESecureTransfer exercises the live crypto service. Ledger
// submission is covered by scripts/run-demo.sh once the chaincode is
// implemented.
func TestE2ESecureTransfer(t *testing.T) {
	if os.Getenv("QFABRIC_E2E") == "" {
		t.Skip("set QFABRIC_E2E=1 with the crypto API running")
	}
	url := os.Getenv("QFABRIC_CRYPTO_API_URL")
	if url == "" {
		url = "http://localhost:8000/api/v1"
	}
	c := integration.NewCryptoClient(url)
	ctx := context.Background()

	if _, err := c.Health(ctx); err != nil {
		t.Fatalf("crypto API unreachable: %v", err)
	}
	var req integration.SecureTransferRequest
	strictDecode(t, "sample_request.json", &req)

	resp, err := c.SecureTransfer(ctx, req)
	if err != nil {
		t.Fatalf("secure-transfer: %v", err)
	}
	if resp.BB84Status != "SUCCESS" || resp.AuditManifest.SessionID != resp.SessionID {
		t.Fatalf("unexpected response: %+v", resp)
	}
}
