"""Service layer: glue between HTTP routes and the bb84/mldsa/encryption
packages. Routes stay thin; all orchestration lives here.

Error handling: raise :class:`ServiceError` for expected failures (mapped
to the error envelope in docs/API_CONTRACT.md). ``NotImplementedError`` is
mapped to HTTP 501 while the module is being built.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path

from api import schemas


class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


@dataclass
class Settings:
    keystore_dir: Path = field(default_factory=lambda: Path(os.getenv("QFABRIC_KEYSTORE_DIR", ".keystore")))
    max_document_bytes: int = int(os.getenv("QFABRIC_MAX_DOCUMENT_BYTES", str(10 * 1024 * 1024)))
    qber_threshold: float = float(os.getenv("QFABRIC_QBER_THRESHOLD", "0.11"))


@dataclass
class Session:
    """In-memory BB84 session. ``shared_secret`` never leaves the process."""

    session_id: str
    sender: str
    receiver: str
    status: schemas.BB84Status
    shared_secret: bytes | None = field(default=None, repr=False)


class SessionStore:
    """Process-local session store (single-worker demo; restart = sessions lost)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def put(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise ServiceError(404, "SESSION_NOT_FOUND", f"unknown session {session_id}") from None


settings = Settings()
sessions = SessionStore()


def component_status() -> dict[str, str]:
    def probe(module: str) -> str:
        return "available" if importlib.util.find_spec(module) else "unavailable"

    # find_spec does not import oqs (importing it may try to build liboqs).
    return {"qiskit": probe("qiskit"), "qiskitAer": probe("qiskit_aer"), "liboqs": probe("oqs")}


# --- Organizations / ML-DSA ------------------------------------------------

def register_organization(req: schemas.RegisterOrganizationRequest) -> schemas.OrganizationResponse:
    """KeyStore.register -> 201. Duplicate org -> ServiceError(409, ORGANIZATION_EXISTS)."""
    raise NotImplementedError("register_organization")


def get_organization(org_id: str) -> schemas.OrganizationResponse:
    """Unknown org -> ServiceError(404, ORGANIZATION_NOT_FOUND)."""
    raise NotImplementedError("get_organization")


def sign_message(req: schemas.SignRequest) -> schemas.SignResponse:
    raise NotImplementedError("sign_message")


def verify_signature(req: schemas.VerifyRequest) -> schemas.VerifyResponse:
    raise NotImplementedError("verify_signature")


# --- BB84 ------------------------------------------------------------------

def execute_bb84(req: schemas.BB84ExecuteRequest) -> schemas.BB84Response:
    """Both orgs must be registered (404 otherwise). Run bb84.run_bb84,
    sign the transcript as both parties, store the Session (secret
    included only on SUCCESS). An ABORTED run is a 200 response."""
    raise NotImplementedError("execute_bb84")


def simulate_attack(req: schemas.BB84AttackRequest) -> schemas.BB84Response:
    """execute_bb84 with the intercept-resend eavesdropper forced on."""
    raise NotImplementedError("simulate_attack")


# --- Encryption ------------------------------------------------------------

def encrypt(req: schemas.EncryptRequest) -> schemas.EncryptResponse:
    """Session must be SUCCESS (409 SESSION_NOT_ESTABLISHED otherwise).
    Document larger than max_document_bytes -> 413 DOCUMENT_TOO_LARGE."""
    raise NotImplementedError("encrypt")


def decrypt(req: schemas.DecryptRequest) -> schemas.DecryptResponse:
    """GCM tag failure -> ServiceError(422, DECRYPTION_FAILED)."""
    raise NotImplementedError("decrypt")


# --- Orchestrated secure transfer -----------------------------------------

def secure_transfer(req: schemas.SecureTransferRequest) -> schemas.SecureTransferResponse:
    """Full flow (docs/ARCHITECTURE.md, "Secure document exchange"):

    1. Load both organizations (404 if missing).
    2. BB84 (eavesdropper per request). On ABORTED skip encryption:
       encryptionAlgorithm=NONE, encryptedDocumentHash="".
    3. On SUCCESS: HKDF key, compress, AES-256-GCM encrypt, then decrypt as
       the receiver to prove delivery.
    4. Build AuditManifest, canonicalize (mldsa.manifest), sign as sender.
    5. Verify own signature (mldsaVerified) and compute securityStatus with
       the same policy as the chaincode (PolicyViolations in transaction.go).
    """
    raise NotImplementedError("secure_transfer")
