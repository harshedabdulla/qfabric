"""ML-DSA-65 key generation and key fingerprints."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from mldsa import ALGORITHM, PUBLIC_KEY_SIZE, SECRET_KEY_SIZE


@dataclass(frozen=True)
class KeyPair:
    public_key: bytes
    secret_key: bytes = field(repr=False)  # never log or return this


def generate_keypair() -> KeyPair:
    """Generate an ML-DSA-65 key pair with liboqs (OS randomness)."""
    import oqs  # lazy: importing oqs needs the liboqs C library

    with oqs.Signature(ALGORITHM) as signer:
        public_key = bytes(signer.generate_keypair())
        secret_key = bytes(signer.export_secret_key())
    if len(public_key) != PUBLIC_KEY_SIZE or len(secret_key) != SECRET_KEY_SIZE:
        raise RuntimeError("liboqs returned unexpected ML-DSA-65 key sizes")
    return KeyPair(public_key=public_key, secret_key=secret_key)


def public_key_id(public_key: bytes) -> str:
    """Trusted key fingerprint: lowercase hex SHA-256 of the raw public key.

    Must equal ``PublicKeyID`` in the Go chaincode (organization.go).
    """
    return hashlib.sha256(public_key).hexdigest()
