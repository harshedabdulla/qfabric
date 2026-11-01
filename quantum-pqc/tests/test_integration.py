"""API contract and end-to-end tests. The schema/sample tests guard the
contract with the blockchain module."""

import base64
import hashlib

import pytest
from conftest import requires_liboqs
from fastapi.testclient import TestClient

from api import schemas
from api.main import app
from api.services import policy_violations
from mldsa.manifest import canonical_manifest
from mldsa.verification import verify

client = TestClient(app)
API = "/api/v1"
DOC = b"PURCHASE ORDER PO-2026-0042\nItem: Titanium fasteners, qty 5000\n" * 20


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# --- contract (no liboqs needed) -------------------------------------------

def test_health():
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["components"]) == {"qiskit", "qiskitAer", "liboqs"}
    assert body["versions"]["qiskitSource"].startswith(("quantum-pqc/third_party/qiskit", "site-packages"))


def test_sample_request_matches_schema(sample_request):
    schemas.SecureTransferRequest.model_validate(sample_request)


def test_sample_response_matches_schema(sample_response):
    resp = schemas.SecureTransferResponse.model_validate(sample_response)
    assert resp.audit_manifest.sender_key_id == resp.signature.public_key_id
    assert len(base64.b64decode(resp.signature.value)) == 3309
    assert policy_violations(resp.audit_manifest) == []


def test_sample_document_hash_is_consistent(sample_request, sample_response):
    doc = base64.b64decode(sample_request["document"])
    assert hashlib.sha256(doc).hexdigest() == sample_response["documentHash"]


def test_response_never_contains_secret_fields(sample_response):
    forbidden = {"sharedSecret", "secretKey", "privateKey", "aesKey", "key"}

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in forbidden, k
                walk(v)

    walk(sample_response)
    for model in (schemas.SecureTransferResponse, schemas.BB84Response, schemas.EncryptResponse, schemas.OrganizationResponse):
        assert not forbidden & {f.alias or name for name, f in model.model_fields.items()}


def test_validation_error_envelope():
    r = client.post(f"{API}/secure-transfer", json={"sender": "OrgA", "receiver": "OrgA", "document": "!!"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_fields_rejected(sample_request):
    r = client.post(f"{API}/secure-transfer", json={**sample_request, "mldsaVerified": True})
    assert r.status_code == 422


# --- end to end (real Qiskit BB84 + liboqs ML-DSA-65 + AES-GCM) ------------

@pytest.fixture(scope="module")
def orgs():
    for org, msp, role in (("OrgA", "Org1MSP", "MANUFACTURER"), ("OrgB", "Org2MSP", "SUPPLIER")):
        r = client.post(f"{API}/organizations/register",
                        json={"orgId": org, "displayName": org, "mspId": msp, "role": role})
        assert r.status_code in (201, 409), r.text
    return {o: client.get(f"{API}/organizations/{o}").json() for o in ("OrgA", "OrgB")}


@requires_liboqs
def test_register_is_not_idempotent_and_get_works(orgs):
    r = client.post(f"{API}/organizations/register",
                    json={"orgId": "OrgA", "displayName": "x", "mspId": "Org1MSP", "role": "MANUFACTURER"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ORGANIZATION_EXISTS"
    assert len(base64.b64decode(orgs["OrgA"]["publicKey"])) == 1952
    assert client.get(f"{API}/organizations/OrgZ").json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


@requires_liboqs
def test_sign_and_verify_endpoints(orgs):
    msg = b64(b"hello")
    sig = client.post(f"{API}/mldsa/sign", json={"orgId": "OrgA", "message": msg}).json()["signature"]
    ok = client.post(f"{API}/mldsa/verify", json={"message": msg, "signature": sig, "orgId": "OrgA"}).json()
    bad = client.post(f"{API}/mldsa/verify", json={"message": b64(b"hellO"), "signature": sig,
                                                    "publicKey": orgs["OrgA"]["publicKey"]}).json()
    wrong_key = client.post(f"{API}/mldsa/verify", json={"message": msg, "signature": sig, "orgId": "OrgB"}).json()
    assert ok["valid"] and not bad["valid"] and not wrong_key["valid"]


@requires_liboqs
def test_bb84_execute_and_attack(orgs):
    ok = client.post(f"{API}/bb84/execute", json={"sender": "OrgA", "receiver": "OrgB", "seed": 1}).json()
    assert ok["status"] == "SUCCESS" and ok["finalKeyLength"] == 256
    assert ok["transcriptAuthenticated"] and ok["keyConfirmed"]
    assert ok["backend"] == "aer_simulator_stabilizer"

    attack = client.post(f"{API}/bb84/simulate-attack", json={"sender": "OrgA", "receiver": "OrgB", "seed": 1}).json()
    assert attack["status"] == "ABORTED" and attack["abortReason"] == "QBER_THRESHOLD_EXCEEDED"
    assert attack["expectedQberFromAttack"] == 0.25 and attack["qber"] > 0.11


@requires_liboqs
def test_encrypt_decrypt_and_tamper_detection(orgs):
    sid = client.post(f"{API}/bb84/execute", json={"sender": "OrgA", "receiver": "OrgB"}).json()["sessionId"]
    enc = client.post(f"{API}/encryption/encrypt", json={"sessionId": sid, "document": b64(DOC)}).json()
    assert enc["compressedSize"] < enc["originalSize"] and enc["compressionRatio"] > 1

    dec = client.post(f"{API}/encryption/decrypt", json={
        "sessionId": sid, "nonce": enc["nonce"], "ciphertext": enc["ciphertext"],
        "compression": "zstd", "expectedDocumentHash": enc["documentHash"]}).json()
    assert base64.b64decode(dec["document"]) == DOC and dec["hashMatched"] is True

    ct = bytearray(base64.b64decode(enc["ciphertext"]))
    ct[5] ^= 1
    r = client.post(f"{API}/encryption/decrypt", json={
        "sessionId": sid, "nonce": enc["nonce"], "ciphertext": b64(bytes(ct)), "compression": "zstd"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "DECRYPTION_FAILED"

    other = client.post(f"{API}/bb84/execute", json={"sender": "OrgA", "receiver": "OrgB"}).json()["sessionId"]
    r = client.post(f"{API}/encryption/decrypt", json={
        "sessionId": other, "nonce": enc["nonce"], "ciphertext": enc["ciphertext"], "compression": "zstd"})
    assert r.status_code == 422, "ciphertext must not decrypt under another session"


@requires_liboqs
def test_encrypt_refused_for_aborted_session(orgs):
    sid = client.post(f"{API}/bb84/simulate-attack", json={"sender": "OrgA", "receiver": "OrgB"}).json()["sessionId"]
    r = client.post(f"{API}/encryption/encrypt", json={"sessionId": sid, "document": b64(DOC)})
    assert r.status_code == 409 and r.json()["error"]["code"] == "SESSION_NOT_ESTABLISHED"


@requires_liboqs
def test_secure_transfer_end_to_end(orgs, sample_request):
    r = client.post(f"{API}/secure-transfer", json={**sample_request, "includeCiphertext": True})
    assert r.status_code == 200, r.text
    body = schemas.SecureTransferResponse.model_validate(r.json())
    assert body.bb84_status == schemas.BB84Status.SUCCESS
    assert body.security_status == schemas.SecurityStatus.VERIFIED and body.mldsa_verified
    assert body.document_hash == hashlib.sha256(base64.b64decode(sample_request["document"])).hexdigest()

    # The signature must verify over the canonical manifest with the org's
    # registered key, exactly as the chaincode checks it.
    canonical = canonical_manifest(body.audit_manifest.model_dump(by_alias=True, mode="json"))
    pk = base64.b64decode(orgs["OrgA"]["publicKey"])
    assert verify(pk, canonical, base64.b64decode(body.signature.value))
    payload = body.encrypted_payload
    expected = hashlib.sha256(base64.b64decode(payload.nonce) + base64.b64decode(payload.ciphertext)).hexdigest()
    assert body.audit_manifest.encrypted_document_hash == expected


@requires_liboqs
def test_secure_transfer_with_eavesdropper_is_rejected(orgs, sample_request):
    attacked = client.post(f"{API}/secure-transfer", json={**sample_request, "simulateEavesdropper": True}).json()
    assert attacked["bb84Status"] == "ABORTED"
    assert attacked["securityStatus"] == "REJECTED"
    assert attacked["encryptionAlgorithm"] == "NONE"
    assert attacked["auditManifest"]["encryptedDocumentHash"] == ""
    assert attacked["encryptedDocumentHash"] is None
