"""AES-256-GCM decryption with tamper detection."""

from __future__ import annotations


class TamperDetectedError(Exception):
    """GCM authentication failed: ciphertext, nonce, AAD or key mismatch."""


def decrypt_document(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes, compression: str, max_size: int) -> bytes:
    """Authenticate and decrypt, then decompress. Raise
    :class:`TamperDetectedError` on ``cryptography.exceptions.InvalidTag``."""
    raise NotImplementedError("TODO(quantum-pqc): decrypt_document")
