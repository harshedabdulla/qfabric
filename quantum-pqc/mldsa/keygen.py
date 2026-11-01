"""ML-DSA-65 key generation and key fingerprints."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class KeyPair:
    public_key: bytes
    secret_key: bytes = field(repr=False)  # never log or return this


def generate_keypair() -> KeyPair:
    """Generate an ML-DSA-65 key pair with ``oqs.Signature("ML-DSA-65")``."""
    raise NotImplementedError("TODO(quantum-pqc): generate_keypair")


def public_key_id(public_key: bytes) -> str:
    """Trusted key fingerprint: lowercase hex SHA-256 of the raw public key.

    Must equal ``PublicKeyID`` in the Go chaincode (organization.go).
    """
    return hashlib.sha256(public_key).hexdigest()
