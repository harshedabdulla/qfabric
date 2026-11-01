package main

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"slices"
	"strings"
	"testing"

	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
)

type testOrg struct {
	id, msp, role string
	pk            []byte
	sk            *mldsa65.PrivateKey // nil for the vector key (signature provided)
}

func generatedOrg(t *testing.T, id, msp, role string) testOrg {
	t.Helper()
	pk, sk, err := mldsa65.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := pk.MarshalBinary()
	return testOrg{id: id, msp: msp, role: role, pk: raw, sk: sk}
}

func (o testOrg) sign(t *testing.T, m AuditManifest) string {
	t.Helper()
	sig := make([]byte, mldsa65.SignatureSize)
	if err := mldsa65.SignTo(o.sk, m.CanonicalBytes(), nil, true, sig); err != nil {
		t.Fatal(err)
	}
	return base64.StdEncoding.EncodeToString(sig)
}

func manifestJSON(t *testing.T, m AuditManifest) string {
	t.Helper()
	b, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// setup registers OrgA (vector key, Org1MSP) and OrgB (generated, Org2MSP).
func setup(t *testing.T) (*ledger, *AuditContract, testVector, testOrg) {
	t.Helper()
	v, pk, _ := loadVector(t)
	l, c := newLedger(), &AuditContract{}
	if _, err := c.RegisterOrganization(l.as(t, "Org1MSP"), "OrgA", "Manufacturer", RoleManufacturer, base64.StdEncoding.EncodeToString(pk)); err != nil {
		t.Fatalf("register OrgA: %v", err)
	}
	orgB := generatedOrg(t, "OrgB", "Org2MSP", RoleSupplier)
	if _, err := c.RegisterOrganization(l.as(t, "Org2MSP"), "OrgB", "Supplier", RoleSupplier, base64.StdEncoding.EncodeToString(orgB.pk)); err != nil {
		t.Fatalf("register OrgB: %v", err)
	}
	return l, c, v, orgB
}

func wantErr(t *testing.T, err error, substr string) {
	t.Helper()
	if err == nil || !strings.Contains(err.Error(), substr) {
		t.Fatalf("want error containing %q, got %v", substr, err)
	}
}

func TestRegisterAndGetOrganization(t *testing.T) {
	l, c, v, _ := setup(t)

	org, err := c.GetOrganization(l.as(t, "Org2MSP"), "OrgA")
	if err != nil {
		t.Fatal(err)
	}
	if org.MSPID != "Org1MSP" || org.PublicKeyID != v.PublicKeyID || org.Algorithm != "ML-DSA-65" {
		t.Fatalf("unexpected org: %+v", org)
	}
	if org.RegisteredAt != "2026-11-01T10:00:03Z" {
		t.Fatalf("registeredAt must come from tx timestamp, got %s", org.RegisteredAt)
	}
	if _, ok := l.stub.events["OrganizationRegistered"]; !ok {
		t.Error("missing OrganizationRegistered event")
	}
	_, err = c.GetOrganization(l.as(t, "Org1MSP"), "OrgZ")
	wantErr(t, err, "not registered")
}

func TestRegisterOrganizationRejections(t *testing.T) {
	l, c, _, orgB := setup(t)
	key := base64.StdEncoding.EncodeToString(orgB.pk)
	org3 := generatedOrg(t, "OrgC", "Org3MSP", RoleSupplier)
	key3 := base64.StdEncoding.EncodeToString(org3.pk)

	_, err := c.RegisterOrganization(l.as(t, "Org3MSP"), "OrgA", "Impostor", RoleSupplier, key3)
	wantErr(t, err, "already registered")

	_, err = c.RegisterOrganization(l.as(t, "Org1MSP"), "OrgC", "Second org of Org1", RoleSupplier, key3)
	wantErr(t, err, "MSP Org1MSP already registered")

	_, err = c.RegisterOrganization(l.as(t, "Org3MSP"), "OrgC", "C", "AUDITOR", key3)
	wantErr(t, err, "invalid role")

	_, err = c.RegisterOrganization(l.as(t, "Org3MSP"), "OrgC", "C", RoleSupplier, key[:100])
	wantErr(t, err, "")

	_, err = c.RegisterOrganization(l.as(t, "Org3MSP"), "Org C", "C", RoleSupplier, key3)
	wantErr(t, err, "invalid orgId")
}

func TestRecordVectorTransactionVerified(t *testing.T) {
	l, c, v, _ := setup(t)

	rec, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "qfabric-tx-001", manifestJSON(t, v.Manifest), v.Signature)
	if err != nil {
		t.Fatalf("record: %v", err)
	}
	if rec.SecurityStatus != StatusVerified || !rec.MLDSAVerified || len(rec.RejectionReasons) != 0 {
		t.Fatalf("want VERIFIED, got %+v", rec)
	}
	if rec.QBER != 0.02 || rec.SenderMSPID != "Org1MSP" || rec.SubmitterMSPID != "Org1MSP" || rec.FabricTxID == "" {
		t.Fatalf("unexpected derived fields: %+v", rec)
	}

	got, err := c.GetTransaction(l.as(t, "Org2MSP"), "qfabric-tx-001")
	if err != nil || got.Manifest != v.Manifest {
		t.Fatalf("GetTransaction: %v %+v", err, got)
	}
	res, err := c.VerifyTransactionRecord(l.as(t, "Org2MSP"), "qfabric-tx-001")
	if err != nil || !res.SignatureValid || !res.Consistent {
		t.Fatalf("VerifyTransactionRecord: %v %+v", err, res)
	}
}

func TestRecordRefusals(t *testing.T) {
	l, c, v, orgB := setup(t)
	good := manifestJSON(t, v.Manifest)

	t.Run("tampered manifest", func(t *testing.T) {
		m := v.Manifest
		m.QBERPpm = 10_000
		_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "tx-tampered", manifestJSON(t, m), v.Signature)
		wantErr(t, err, "signature verification failed")
	})
	t.Run("wrong submitter MSP", func(t *testing.T) {
		_, err := c.RecordSecureTransaction(l.as(t, "Org2MSP"), "tx-msp", good, v.Signature)
		wantErr(t, err, "submitter MSP Org2MSP")
	})
	t.Run("signed by a different key", func(t *testing.T) {
		m := v.Manifest // claims OrgA's key id, signed with OrgB's key
		_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "tx-forged", good, orgB.sign(t, m))
		wantErr(t, err, "signature verification failed")
	})
	t.Run("unknown field", func(t *testing.T) {
		bad := strings.Replace(good, `{"sessionId"`, `{"mldsaVerified":true,"sessionId"`, 1)
		_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "tx-unknown", bad, v.Signature)
		wantErr(t, err, "unknown field")
	})
	t.Run("trailing data", func(t *testing.T) {
		_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "tx-trailing", good+"{}", v.Signature)
		wantErr(t, err, "trailing data")
	})
	t.Run("unregistered receiver", func(t *testing.T) {
		m := v.Manifest
		m.Receiver = "OrgZ"
		_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "tx-receiver", manifestJSON(t, m), v.Signature)
		wantErr(t, err, "receiver")
	})

	if records, _ := c.GetAllTransactions(l.as(t, "Org1MSP")); len(records) != 0 {
		t.Fatalf("refused submissions must not be written, found %d", len(records))
	}

	// Replay: first submission succeeds, then same tx id and same session fail.
	if _, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "qfabric-tx-001", good, v.Signature); err != nil {
		t.Fatal(err)
	}
	_, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "qfabric-tx-001", good, v.Signature)
	wantErr(t, err, "already recorded")
	_, err = c.RecordSecureTransaction(l.as(t, "Org1MSP"), "qfabric-tx-002", good, v.Signature)
	wantErr(t, err, "session qfabric-session-001 already recorded")
}

func TestEavesdroppedTransferRecordedAsRejected(t *testing.T) {
	l, c, _, orgB := setup(t)

	// OrgB sends to OrgA; BB84 aborted because Eve pushed QBER to 25%.
	m := AuditManifest{
		SessionID: "qfabric-session-eve", Sender: "OrgB", Receiver: "OrgA",
		SenderKeyID: PublicKeyID(orgB.pk), BB84Status: BB84Aborted,
		QBERPpm: 250_000, QBERThresholdPpm: 110_000, SiftedKeyLength: 1019, FinalKeyLength: 0,
		TranscriptHash:      strings.Repeat("a", 64),
		EncryptionAlgorithm: EncryptionNone, Compression: "zstd",
		DocumentHash: strings.Repeat("b", 64), EncryptedDocumentHash: "",
		Timestamp: "2026-11-01T10:05:00Z",
	}
	rec, err := c.RecordSecureTransaction(l.as(t, "Org2MSP"), "qfabric-tx-eve", manifestJSON(t, m), orgB.sign(t, m))
	if err != nil {
		t.Fatalf("authenticated rejection must be recorded: %v", err)
	}
	if rec.SecurityStatus != StatusRejected ||
		!slices.Contains(rec.RejectionReasons, "BB84_NOT_SUCCESSFUL") ||
		!slices.Contains(rec.RejectionReasons, "QBER_EXCEEDS_THRESHOLD") {
		t.Fatalf("want REJECTED with reasons, got %+v", rec)
	}
	res, err := c.VerifyTransactionRecord(l.as(t, "Org1MSP"), "qfabric-tx-eve")
	if err != nil || !res.Consistent || res.RecomputedStatus != StatusRejected {
		t.Fatalf("verify: %v %+v", err, res)
	}
}

func TestGetAllTransactionsAndTamperDetection(t *testing.T) {
	l, c, v, _ := setup(t)

	records, err := c.GetAllTransactions(l.as(t, "Org1MSP"))
	if err != nil || records == nil || len(records) != 0 {
		t.Fatalf("empty ledger must return [], got %v %v", records, err)
	}
	if _, err := c.RecordSecureTransaction(l.as(t, "Org1MSP"), "qfabric-tx-001", manifestJSON(t, v.Manifest), v.Signature); err != nil {
		t.Fatal(err)
	}
	if records, _ := c.GetAllTransactions(l.as(t, "Org1MSP")); len(records) != 1 {
		t.Fatalf("want 1 record, got %d", len(records))
	}

	// Simulate someone rewriting the stored record's QBER directly in state.
	key, _ := l.stub.CreateCompositeKey(keyTransaction, []string{"qfabric-tx-001"})
	var rec AuditRecord
	_ = json.Unmarshal(l.stub.state[key], &rec)
	rec.Manifest.QBERPpm = 0
	raw, _ := json.Marshal(rec)
	l.stub.state[key] = raw

	res, err := c.VerifyTransactionRecord(l.as(t, "Org2MSP"), "qfabric-tx-001")
	if err != nil {
		t.Fatal(err)
	}
	if res.SignatureValid || res.Consistent {
		t.Fatalf("tampered record must fail re-verification: %+v", res)
	}
}
