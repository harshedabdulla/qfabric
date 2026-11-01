"""API contract tests. The schema/sample tests pass today and must keep
passing: they guard the contract with the blockchain module."""

import base64
import hashlib

import pytest
from fastapi.testclient import TestClient

from api import schemas
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["components"]) == {"qiskit", "qiskitAer", "liboqs"}


def test_sample_request_matches_schema(sample_request):
    schemas.SecureTransferRequest.model_validate(sample_request)


def test_sample_response_matches_schema(sample_response):
    resp = schemas.SecureTransferResponse.model_validate(sample_response)
    assert resp.audit_manifest.sender_key_id == resp.signature.public_key_id
    assert len(base64.b64decode(resp.signature.value)) == 3309


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
    r = client.post("/api/v1/secure-transfer", json={"sender": "OrgA", "receiver": "OrgA", "document": "!!"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_fields_rejected(sample_request):
    r = client.post("/api/v1/secure-transfer", json={**sample_request, "mldsaVerified": True})
    assert r.status_code == 422


def test_secure_transfer_end_to_end(sample_request, b64):
    """Runs once the whole service is implemented (501 -> skipped until then)."""
    for org, msp, role in (("OrgA", "Org1MSP", "MANUFACTURER"), ("OrgB", "Org2MSP", "SUPPLIER")):
        r = client.post("/api/v1/organizations/register",
                        json={"orgId": org, "displayName": org, "mspId": msp, "role": role})
        if r.status_code == 501:
            pytest.skip("not implemented yet: organizations/register")
        assert r.status_code in (201, 409)

    r = client.post("/api/v1/secure-transfer", json=sample_request)
    if r.status_code == 501:
        pytest.skip("not implemented yet: secure-transfer")
    assert r.status_code == 200
    body = schemas.SecureTransferResponse.model_validate(r.json())
    assert body.bb84_status == schemas.BB84Status.SUCCESS
    assert body.security_status == schemas.SecurityStatus.VERIFIED

    attacked = client.post("/api/v1/secure-transfer", json={**sample_request, "simulateEavesdropper": True}).json()
    assert attacked["bb84Status"] == "ABORTED"
    assert attacked["securityStatus"] == "REJECTED"
    assert attacked["auditManifest"]["encryptedDocumentHash"] == ""
