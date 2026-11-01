"""HKDF-SHA-256 key derivation from the BB84 shared secret.

Parameters (docs/SECURITY_MODEL.md, "Key management"):
    IKM  = BB84 shared secret (32 bytes)
    salt = UTF-8 sessionId
    info = b"qfabric/v1/aes-256-gcm|" + sender + b"|" + receiver
    L    = 32 bytes

The derived key is never logged, returned, or persisted.
"""

from __future__ import annotations


def derive_aes_key(shared_secret: bytes, session_id: str, sender: str, receiver: str) -> bytes:
    """Return a 32-byte AES-256 key (``cryptography`` HKDF)."""
    raise NotImplementedError("TODO(quantum-pqc): derive_aes_key")


def associated_data(session_id: str, sender: str, receiver: str) -> bytes:
    """AAD bound into every GCM operation so ciphertexts cannot be replayed
    into another session or direction: b"qfabric/v1|<sessionId>|<sender>|<receiver>"."""
    return f"qfabric/v1|{session_id}|{sender}|{receiver}".encode()
