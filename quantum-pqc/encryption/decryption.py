"""AES-256-GCM decryption with tamper detection."""

from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from encryption import NONCE_SIZE
from encryption.compression import decompress


class TamperDetectedError(Exception):
    """GCM authentication failed: ciphertext, nonce, AAD or key mismatch."""


def decrypt_document(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes, compression: str, max_size: int) -> bytes:
    """Authenticate and decrypt, then decompress. Raises
    :class:`TamperDetectedError` if the GCM tag does not verify."""
    if len(key) != 32 or len(nonce) != NONCE_SIZE:
        raise TamperDetectedError("invalid key or nonce length")
    try:
        compressed = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag:
        raise TamperDetectedError("authentication tag mismatch") from None
    return decompress(compressed, compression, max_size)
