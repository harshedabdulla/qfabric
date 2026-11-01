"""AES-256-GCM encryption of compressed documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EncryptedDocument:
    nonce: bytes                   # 12 random bytes
    ciphertext: bytes              # includes the 16-byte GCM tag
    compression: str
    original_size: int
    compressed_size: int
    document_hash: str             # SHA-256 hex of the original plaintext
    encrypted_document_hash: str   # SHA-256 hex of nonce || ciphertext


def encrypt_document(key: bytes, plaintext: bytes, aad: bytes, compression: str = "zstd") -> EncryptedDocument:
    """Hash plaintext, compress, encrypt with a fresh random nonce."""
    raise NotImplementedError("TODO(quantum-pqc): encrypt_document")
