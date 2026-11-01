"""Pydantic models for the QFabric crypto API (v1).

These models ARE the integration contract described in
docs/API_CONTRACT.md. JSON uses camelCase; binary values are standard
base64 (with padding); hashes are lowercase hex SHA-256. Changing a field
here is an API change: update the contract docs, the samples in
integration/, and blockchain/integration/metadata.go in the same PR.
"""

from __future__ import annotations

import base64
import binascii
from enum import Enum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


# --------------------------------------------------------------------------
# Shared field types
# --------------------------------------------------------------------------

def _check_base64(value: str) -> str:
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("must be standard base64") from exc
    return value


Base64 = Annotated[str, AfterValidator(_check_base64)]
OrgId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", examples=["OrgA"])]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,128}$")]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
UtcTimestamp = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
Ppm = Annotated[int, Field(ge=0, le=1_000_000)]


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class OrganizationRole(str, Enum):
    MANUFACTURER = "MANUFACTURER"
    SUPPLIER = "SUPPLIER"


class BB84Status(str, Enum):
    SUCCESS = "SUCCESS"
    ABORTED = "ABORTED"


class AbortReason(str, Enum):
    QBER_THRESHOLD_EXCEEDED = "QBER_THRESHOLD_EXCEEDED"
    KEY_CONFIRMATION_FAILED = "KEY_CONFIRMATION_FAILED"
    INSUFFICIENT_KEY_MATERIAL = "INSUFFICIENT_KEY_MATERIAL"


class SecurityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Compression(str, Enum):
    ZSTD = "zstd"
    GZIP = "gzip"
    NONE = "none"


class EncryptionAlgorithm(str, Enum):
    AES_256_GCM = "AES-256-GCM"
    NONE = "NONE"


SignatureAlgorithm = Literal["ML-DSA-65"]


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class ErrorBody(APIModel):
    code: str = Field(examples=["ORGANIZATION_NOT_FOUND"])
    message: str
    details: dict | None = None


class ErrorResponse(APIModel):
    error: ErrorBody


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    service: str = "qfabric-quantum-pqc"
    version: str
    components: dict[str, str] = Field(
        description="Component -> 'available' | 'unavailable' | 'not_implemented'",
        examples=[{"qiskit": "available", "qiskitAer": "available", "liboqs": "available"}],
    )
    versions: dict[str, str] = Field(
        default_factory=dict,
        description="Component versions and, for Qiskit, where it is loaded from",
        examples=[{"qiskit": "2.6.1", "qiskitSource": "quantum-pqc/third_party/qiskit", "qiskitAer": "0.18.2"}],
    )


# --------------------------------------------------------------------------
# Organizations
# --------------------------------------------------------------------------

class RegisterOrganizationRequest(APIModel):
    org_id: OrgId
    display_name: str = Field(min_length=1, max_length=128)
    msp_id: str = Field(pattern=r"^[A-Za-z0-9.-]{1,64}$", examples=["Org1MSP"])
    role: OrganizationRole


class OrganizationResponse(APIModel):
    org_id: OrgId
    display_name: str
    msp_id: str
    role: OrganizationRole
    algorithm: SignatureAlgorithm = "ML-DSA-65"
    public_key: Base64 = Field(description="Raw FIPS 204 public key (1952 bytes), base64")
    public_key_id: HexDigest = Field(description="SHA-256 of the raw public key")
    created_at: UtcTimestamp


# --------------------------------------------------------------------------
# ML-DSA
# --------------------------------------------------------------------------

class SignRequest(APIModel):
    org_id: OrgId
    message: Base64


class SignResponse(APIModel):
    org_id: OrgId
    algorithm: SignatureAlgorithm = "ML-DSA-65"
    public_key_id: HexDigest
    message_hash: HexDigest
    signature: Base64


class VerifyRequest(APIModel):
    """Provide exactly one of ``publicKey`` or ``orgId``."""

    message: Base64
    signature: Base64
    public_key: Base64 | None = None
    org_id: OrgId | None = None

    @model_validator(mode="after")
    def _one_key_source(self) -> "VerifyRequest":
        if (self.public_key is None) == (self.org_id is None):
            raise ValueError("provide exactly one of publicKey or orgId")
        return self


class VerifyResponse(APIModel):
    valid: bool
    algorithm: SignatureAlgorithm = "ML-DSA-65"
    public_key_id: HexDigest


# --------------------------------------------------------------------------
# BB84
# --------------------------------------------------------------------------

class BB84Parameters(APIModel):
    sender: OrgId
    receiver: OrgId
    num_qubits: int = Field(default=2048, ge=256, le=16384)
    sample_fraction: float = Field(default=0.25, ge=0.05, le=0.5)
    qber_threshold: float = Field(default=0.11, gt=0.0, le=0.11)
    channel_error_rate: float = Field(default=0.0, ge=0.0, le=0.25)
    seed: int | None = Field(default=None, description="Simulator/RNG seed for reproducible demos")

    @model_validator(mode="after")
    def _distinct_parties(self):
        if self.sender == self.receiver:
            raise ValueError("sender and receiver must differ")
        return self


class BB84ExecuteRequest(BB84Parameters):
    eavesdropper: bool = False
    interception_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class BB84AttackRequest(BB84Parameters):
    interception_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class ErrorCorrectionInfo(APIModel):
    method: str = Field(examples=["cascade"])
    bits_leaked: int = Field(ge=0)


class BB84Response(APIModel):
    session_id: Identifier
    sender: OrgId
    receiver: OrgId
    status: BB84Status
    abort_reason: AbortReason | None = None
    num_qubits: int
    sifted_key_length: int
    sample_size: int
    qber: float = Field(ge=0.0, le=1.0)
    qber_threshold: float
    error_correction: ErrorCorrectionInfo | None = None
    final_key_length: int = Field(description="Bits of shared secret produced (0 when aborted)")
    key_confirmed: bool
    transcript_hash: HexDigest
    transcript_authenticated: bool = Field(description="Both parties' ML-DSA transcript signatures verified")
    eavesdropper_enabled: bool
    interception_rate: float
    expected_qber_from_attack: float | None = None
    backend: str = Field(examples=["aer_simulator"])
    duration_ms: float


# --------------------------------------------------------------------------
# Encryption
# --------------------------------------------------------------------------

class EncryptRequest(APIModel):
    session_id: Identifier
    document: Base64
    compression: Compression = Compression.ZSTD


class EncryptResponse(APIModel):
    session_id: Identifier
    algorithm: Literal["AES-256-GCM"] = "AES-256-GCM"
    compression: Compression
    nonce: Base64
    ciphertext: Base64 = Field(description="Ciphertext with 16-byte GCM tag appended")
    original_size: int
    compressed_size: int
    compression_ratio: float = Field(description="originalSize / compressedSize")
    document_hash: HexDigest = Field(description="SHA-256 of the original plaintext")
    encrypted_document_hash: HexDigest = Field(description="SHA-256 of nonce || ciphertext")


class DecryptRequest(APIModel):
    session_id: Identifier
    nonce: Base64
    ciphertext: Base64
    compression: Compression
    expected_document_hash: HexDigest | None = None


class DecryptResponse(APIModel):
    session_id: Identifier
    document: Base64
    document_hash: HexDigest
    integrity_verified: bool = Field(description="GCM tag verified (always true on 200)")
    hash_matched: bool | None = Field(default=None, description="Set when expectedDocumentHash was supplied")


# --------------------------------------------------------------------------
# Secure transfer (orchestrated flow consumed by the blockchain client)
# --------------------------------------------------------------------------

class SecureTransferRequest(APIModel):
    sender: OrgId
    receiver: OrgId
    document: Base64
    filename: str | None = Field(default=None, max_length=255)
    compression: Compression = Compression.ZSTD
    num_qubits: int = Field(default=2048, ge=256, le=16384)
    sample_fraction: float = Field(default=0.25, ge=0.05, le=0.5)
    channel_error_rate: float = Field(default=0.0, ge=0.0, le=0.25)
    simulate_eavesdropper: bool = False
    interception_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    seed: int | None = None
    include_ciphertext: bool = False

    @model_validator(mode="after")
    def _distinct_parties(self):
        if self.sender == self.receiver:
            raise ValueError("sender and receiver must differ")
        return self


class AuditManifest(APIModel):
    """Exactly the signed fields. Serialized canonically by
    mldsa.manifest.canonical_manifest (docs/API_CONTRACT.md section 4)."""

    session_id: Identifier
    sender: OrgId
    receiver: OrgId
    sender_key_id: HexDigest
    bb84_status: BB84Status
    qber_ppm: Ppm
    qber_threshold_ppm: Ppm
    sifted_key_length: int = Field(ge=0)
    final_key_length: int = Field(ge=0)
    transcript_hash: HexDigest
    encryption_algorithm: EncryptionAlgorithm
    compression: Compression
    document_hash: HexDigest
    encrypted_document_hash: Literal[""] | HexDigest = Field(description='"" when BB84 aborted')
    timestamp: UtcTimestamp


class SignatureEnvelope(APIModel):
    algorithm: SignatureAlgorithm = "ML-DSA-65"
    signer: OrgId
    public_key_id: HexDigest
    value: Base64 = Field(description="Raw 3309-byte ML-DSA-65 signature over the canonical manifest")


class EncryptedPayload(APIModel):
    nonce: Base64
    ciphertext: Base64


class SecureTransferResponse(APIModel):
    session_id: Identifier
    sender: OrgId
    receiver: OrgId
    mldsa_verified: bool = Field(description="Service-side check only; the chaincode re-verifies independently")
    bb84_status: BB84Status
    abort_reason: AbortReason | None = None
    qber: float = Field(ge=0.0, le=1.0)
    qber_threshold: float
    encryption_algorithm: EncryptionAlgorithm
    compression: Compression
    original_size: int
    compressed_size: int | None = None
    compression_ratio: float | None = None
    document_hash: HexDigest
    encrypted_document_hash: HexDigest | None = None
    transcript_hash: HexDigest
    security_status: SecurityStatus
    timestamp: UtcTimestamp
    audit_manifest: AuditManifest
    signature: SignatureEnvelope
    encrypted_payload: EncryptedPayload | None = None
