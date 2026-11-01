"""Service layer: glue between HTTP routes and the bb84/mldsa/encryption
packages. Routes stay thin; all orchestration lives here.

Error handling: raise :class:`ServiceError` for expected failures (mapped
to the error envelope in docs/API_CONTRACT.md).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.util
import logging
import os
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from api import schemas
from bb84 import BB84Config, BB84Result, run_bb84
from encryption.decryption import TamperDetectedError, decrypt_document
from encryption.encryption import EncryptedDocument, encrypt_document
from encryption.key_derivation import associated_data, derive_aes_key
from mldsa.identity import KeyStore, OrganizationIdentity
from mldsa.keygen import public_key_id
from mldsa.manifest import canonical_manifest, to_ppm
from mldsa.verification import verify

logger = logging.getLogger("qfabric.services")

TRANSCRIPT_SIGNING_HEADER = "QFABRIC-BB84-TRANSCRIPT-V1"
MAX_QBER_THRESHOLD = 0.11
MIN_FINAL_KEY_BITS = 256


class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default))


@dataclass
class Settings:
    keystore_dir: Path = field(default_factory=lambda: Path(os.getenv("QFABRIC_KEYSTORE_DIR", ".keystore")))
    max_document_bytes: int = field(default_factory=lambda: int(os.getenv("QFABRIC_MAX_DOCUMENT_BYTES", str(10 * 1024 * 1024))))
    qber_threshold: float = field(default_factory=lambda: min(_env_float("QFABRIC_QBER_THRESHOLD", "0.11"), MAX_QBER_THRESHOLD))


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
        self._lock = threading.Lock()

    def put(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise ServiceError(404, "SESSION_NOT_FOUND", f"unknown session {session_id}")
        return session


settings = Settings()
sessions = SessionStore()
keystore = KeyStore(settings.keystore_dir)


def component_status() -> dict[str, str]:
    def probe(module: str) -> str:
        return "available" if importlib.util.find_spec(module) else "unavailable"

    # find_spec does not import oqs (importing it may try to build liboqs).
    return {"qiskit": probe("qiskit"), "qiskitAer": probe("qiskit_aer"), "liboqs": probe("oqs")}


def component_versions() -> dict[str, str]:
    """Versions of the quantum stack, and which Qiskit source is in use
    (the vendored clone in third_party/qiskit, or a site-packages wheel)."""
    from importlib.metadata import PackageNotFoundError, version

    versions: dict[str, str] = {}
    for name, dist in (("qiskit", "qiskit"), ("qiskitAer", "qiskit-aer"), ("liboqsPython", "liboqs-python")):
        try:
            versions[name] = version(dist)
        except PackageNotFoundError:
            pass
    spec = importlib.util.find_spec("qiskit")
    if spec and spec.origin:
        origin = Path(spec.origin).resolve()
        if "third_party" in origin.parts:
            versions["qiskitSource"] = "quantum-pqc/third_party/qiskit"
        else:
            # The Docker image builds a wheel from third_party/qiskit and sets this.
            versions["qiskitSource"] = os.getenv("QFABRIC_QISKIT_SOURCE", "site-packages")
    return versions


# --- helpers ---------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _unb64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ServiceError(422, "VALIDATION_ERROR", "invalid base64") from None


def _identity(org_id: str) -> OrganizationIdentity:
    try:
        return keystore.get(org_id)
    except KeyError:
        raise ServiceError(404, "ORGANIZATION_NOT_FOUND", f"unknown organization {org_id}") from None


def _org_response(identity: OrganizationIdentity) -> schemas.OrganizationResponse:
    return schemas.OrganizationResponse(
        org_id=identity.org_id, display_name=identity.display_name, msp_id=identity.msp_id,
        role=identity.role, public_key=_b64(identity.public_key),
        public_key_id=identity.public_key_id, created_at=identity.created_at,
    )


def _check_document_size(document: bytes) -> None:
    if len(document) > settings.max_document_bytes:
        raise ServiceError(413, "DOCUMENT_TOO_LARGE",
                           f"document exceeds {settings.max_document_bytes} bytes")


# --- Organizations / ML-DSA ------------------------------------------------

def register_organization(req: schemas.RegisterOrganizationRequest) -> schemas.OrganizationResponse:
    try:
        identity = keystore.register(req.org_id, req.display_name, req.msp_id, req.role.value)
    except FileExistsError:
        raise ServiceError(409, "ORGANIZATION_EXISTS", f"organization {req.org_id} already registered") from None
    logger.info("registered organization %s (%s) key=%s", identity.org_id, identity.msp_id, identity.public_key_id[:16])
    return _org_response(identity)


def get_organization(org_id: str) -> schemas.OrganizationResponse:
    return _org_response(_identity(org_id))


def sign_message(req: schemas.SignRequest) -> schemas.SignResponse:
    identity = _identity(req.org_id)
    message = _unb64(req.message)
    signature = keystore.sign_as(req.org_id, message)
    return schemas.SignResponse(
        org_id=req.org_id, public_key_id=identity.public_key_id,
        message_hash=hashlib.sha256(message).hexdigest(), signature=_b64(signature),
    )


def verify_signature(req: schemas.VerifyRequest) -> schemas.VerifyResponse:
    public_key = _unb64(req.public_key) if req.public_key else _identity(req.org_id).public_key
    valid = verify(public_key, _unb64(req.message), _unb64(req.signature))
    return schemas.VerifyResponse(valid=valid, public_key_id=public_key_id(public_key))


# --- BB84 ------------------------------------------------------------------

def _transcript_message(session_id: str, sender: str, receiver: str, transcript_hash: str) -> bytes:
    return "\n".join([
        TRANSCRIPT_SIGNING_HEADER, f"sessionId={session_id}", f"sender={sender}",
        f"receiver={receiver}", f"transcriptHash={transcript_hash}",
    ]).encode()


def _key_exchange(
    params: schemas.BB84Parameters, eavesdropper: bool, interception_rate: float
) -> tuple[Session, BB84Result, bool]:
    """Run BB84 between two registered orgs and authenticate the transcript
    with both orgs' ML-DSA-65 keys. Returns the stored session, the raw
    result and whether the transcript was authenticated."""
    sender, receiver = _identity(params.sender), _identity(params.receiver)
    threshold = min(params.qber_threshold, settings.qber_threshold)
    result = run_bb84(BB84Config(
        num_qubits=params.num_qubits, sample_fraction=params.sample_fraction,
        qber_threshold=threshold, channel_error_rate=params.channel_error_rate,
        eavesdropper=eavesdropper, interception_rate=interception_rate,
        final_key_bits=MIN_FINAL_KEY_BITS, seed=params.seed,
    ))
    session_id = f"qfabric-session-{secrets.token_hex(8)}"

    # Authenticate the classical channel: both parties sign the transcript,
    # each verifies the other's signature before the key is accepted.
    message = _transcript_message(session_id, sender.org_id, receiver.org_id, result.transcript_hash)
    alice_sig = keystore.sign_as(sender.org_id, message)
    bob_sig = keystore.sign_as(receiver.org_id, message)
    authenticated = verify(sender.public_key, message, alice_sig) and verify(receiver.public_key, message, bob_sig)

    status = schemas.BB84Status(result.status)
    if not authenticated:  # never accept a key from an unauthenticated exchange
        status, result.shared_secret = schemas.BB84Status.ABORTED, None
    session = Session(session_id, sender.org_id, receiver.org_id, status, result.shared_secret)
    sessions.put(session)
    logger.info("bb84 %s %s->%s status=%s qber=%.4f eve=%s", session_id, sender.org_id,
                receiver.org_id, status.value, result.qber, eavesdropper)
    return session, result, authenticated


def _bb84_response(session: Session, result: BB84Result, authenticated: bool) -> schemas.BB84Response:
    return schemas.BB84Response(
        session_id=session.session_id, sender=session.sender, receiver=session.receiver,
        status=session.status,
        abort_reason=schemas.AbortReason(result.abort_reason.value) if result.abort_reason else None,
        num_qubits=result.num_qubits, sifted_key_length=result.sifted_key_length,
        sample_size=result.sample_size, qber=result.qber, qber_threshold=result.qber_threshold,
        error_correction=(schemas.ErrorCorrectionInfo(method="cascade", bits_leaked=result.bits_leaked)
                          if result.bits_leaked else None),
        final_key_length=result.final_key_length if session.shared_secret else 0,
        key_confirmed=result.key_confirmed, transcript_hash=result.transcript_hash,
        transcript_authenticated=authenticated, eavesdropper_enabled=result.eavesdropper_enabled,
        interception_rate=result.interception_rate,
        expected_qber_from_attack=0.25 * result.interception_rate if result.eavesdropper_enabled else None,
        backend=result.backend, duration_ms=round(result.duration_ms, 2),
    )


def execute_bb84(req: schemas.BB84ExecuteRequest) -> schemas.BB84Response:
    return _bb84_response(*_key_exchange(req, req.eavesdropper, req.interception_rate))


def simulate_attack(req: schemas.BB84AttackRequest) -> schemas.BB84Response:
    return _bb84_response(*_key_exchange(req, True, req.interception_rate))


# --- Encryption ------------------------------------------------------------

def _session_key(session: Session) -> bytes:
    if session.status != schemas.BB84Status.SUCCESS or session.shared_secret is None:
        raise ServiceError(409, "SESSION_NOT_ESTABLISHED", f"session {session.session_id} has no key")
    return derive_aes_key(session.shared_secret, session.session_id, session.sender, session.receiver)


def _encrypt(session: Session, document: bytes, compression: str) -> EncryptedDocument:
    _check_document_size(document)
    aad = associated_data(session.session_id, session.sender, session.receiver)
    return encrypt_document(_session_key(session), document, aad, compression)


def _decrypt(session: Session, nonce: bytes, ciphertext: bytes, compression: str) -> bytes:
    aad = associated_data(session.session_id, session.sender, session.receiver)
    try:
        return decrypt_document(_session_key(session), nonce, ciphertext, aad, compression,
                                settings.max_document_bytes)
    except TamperDetectedError:
        raise ServiceError(422, "DECRYPTION_FAILED", "authentication failed: ciphertext, nonce or session mismatch") from None
    except ValueError as exc:
        raise ServiceError(422, "DECRYPTION_FAILED", str(exc)) from None


def encrypt(req: schemas.EncryptRequest) -> schemas.EncryptResponse:
    session = sessions.get(req.session_id)
    enc = _encrypt(session, _unb64(req.document), req.compression.value)
    return schemas.EncryptResponse(
        session_id=session.session_id, compression=req.compression, nonce=_b64(enc.nonce),
        ciphertext=_b64(enc.ciphertext), original_size=enc.original_size,
        compressed_size=enc.compressed_size, compression_ratio=round(enc.compression_ratio, 4),
        document_hash=enc.document_hash, encrypted_document_hash=enc.encrypted_document_hash,
    )


def decrypt(req: schemas.DecryptRequest) -> schemas.DecryptResponse:
    session = sessions.get(req.session_id)
    document = _decrypt(session, _unb64(req.nonce), _unb64(req.ciphertext), req.compression.value)
    digest = hashlib.sha256(document).hexdigest()
    return schemas.DecryptResponse(
        session_id=session.session_id, document=_b64(document), document_hash=digest,
        integrity_verified=True,
        hash_matched=(digest == req.expected_document_hash) if req.expected_document_hash else None,
    )


# --- Orchestrated secure transfer -----------------------------------------

def policy_violations(m: schemas.AuditManifest) -> list[str]:
    """Same rules as PolicyViolations in the chaincode (transaction.go)."""
    reasons = []
    success = m.bb84_status == schemas.BB84Status.SUCCESS
    if not success:
        reasons.append("BB84_NOT_SUCCESSFUL")
    if m.qber_threshold_ppm > to_ppm(MAX_QBER_THRESHOLD):
        reasons.append("QBER_THRESHOLD_ABOVE_POLICY")
    if m.qber_ppm > m.qber_threshold_ppm or m.qber_ppm > to_ppm(MAX_QBER_THRESHOLD):
        reasons.append("QBER_EXCEEDS_THRESHOLD")
    if success and m.final_key_length < MIN_FINAL_KEY_BITS:
        reasons.append("INSUFFICIENT_KEY_MATERIAL")
    if success and (m.encryption_algorithm != schemas.EncryptionAlgorithm.AES_256_GCM or not m.encrypted_document_hash):
        reasons.append("DOCUMENT_NOT_ENCRYPTED")
    return reasons


def secure_transfer(req: schemas.SecureTransferRequest) -> schemas.SecureTransferResponse:
    """Full flow (docs/ARCHITECTURE.md, "Secure document exchange"):

    1. BB84 between the registered orgs (eavesdropper per request), with an
       ML-DSA-authenticated transcript.
    2. On SUCCESS: HKDF key, compress, AES-256-GCM encrypt, then decrypt as
       the receiver to prove delivery.
    3. Build the audit manifest, canonicalize it, sign it as the sender.
    4. Verify our own signature and compute the chaincode's policy verdict.
    """
    document = _unb64(req.document)
    _check_document_size(document)
    params = schemas.BB84Parameters(
        sender=req.sender, receiver=req.receiver, num_qubits=req.num_qubits,
        sample_fraction=req.sample_fraction, qber_threshold=settings.qber_threshold,
        channel_error_rate=req.channel_error_rate, seed=req.seed,
    )
    session, result, _ = _key_exchange(params, req.simulate_eavesdropper, req.interception_rate)
    sender = _identity(req.sender)
    document_hash = hashlib.sha256(document).hexdigest()

    enc: EncryptedDocument | None = None
    if session.status == schemas.BB84Status.SUCCESS:
        enc = _encrypt(session, document, req.compression.value)
        delivered = _decrypt(session, enc.nonce, enc.ciphertext, enc.compression)  # receiver side
        if hashlib.sha256(delivered).hexdigest() != document_hash:
            raise ServiceError(500, "INTERNAL_ERROR", "delivery check failed")

    timestamp = _now()
    manifest = schemas.AuditManifest(
        session_id=session.session_id, sender=sender.org_id, receiver=req.receiver,
        sender_key_id=sender.public_key_id, bb84_status=session.status,
        qber_ppm=to_ppm(result.qber), qber_threshold_ppm=to_ppm(result.qber_threshold),
        sifted_key_length=result.sifted_key_length,
        final_key_length=result.final_key_length if enc else 0,
        transcript_hash=result.transcript_hash,
        encryption_algorithm=schemas.EncryptionAlgorithm.AES_256_GCM if enc else schemas.EncryptionAlgorithm.NONE,
        compression=req.compression, document_hash=document_hash,
        encrypted_document_hash=enc.encrypted_document_hash if enc else "",
        timestamp=timestamp,
    )
    canonical = canonical_manifest(manifest.model_dump(by_alias=True, mode="json"))
    signature = keystore.sign_as(sender.org_id, canonical)
    mldsa_verified = verify(sender.public_key, canonical, signature)
    status = schemas.SecurityStatus.REJECTED if policy_violations(manifest) or not mldsa_verified \
        else schemas.SecurityStatus.VERIFIED

    return schemas.SecureTransferResponse(
        session_id=session.session_id, sender=sender.org_id, receiver=req.receiver,
        mldsa_verified=mldsa_verified, bb84_status=session.status,
        abort_reason=schemas.AbortReason(result.abort_reason.value) if result.abort_reason else None,
        qber=result.qber, qber_threshold=result.qber_threshold,
        encryption_algorithm=manifest.encryption_algorithm, compression=req.compression,
        original_size=len(document),
        compressed_size=enc.compressed_size if enc else None,
        compression_ratio=round(enc.compression_ratio, 4) if enc else None,
        document_hash=document_hash,
        encrypted_document_hash=enc.encrypted_document_hash if enc else None,
        transcript_hash=result.transcript_hash, security_status=status, timestamp=timestamp,
        audit_manifest=manifest,
        signature=schemas.SignatureEnvelope(signer=sender.org_id, public_key_id=sender.public_key_id,
                                            value=_b64(signature)),
        encrypted_payload=(schemas.EncryptedPayload(nonce=_b64(enc.nonce), ciphertext=_b64(enc.ciphertext))
                           if enc and req.include_ciphertext else None),
    )
