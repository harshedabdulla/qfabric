"""AES-256-GCM encryption of compressed documents."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from encryption import NONCE_SIZE
from encryption.compression import compress


@dataclass(frozen=True)
class EncryptedDocument:
    nonce: bytes                   # 12 random bytes
    ciphertext: bytes              # includes the 16-byte GCM tag
    compression: str
    original_size: int
    compressed_size: int
    document_hash: str             # SHA-256 hex of the original plaintext
    encrypted_document_hash: str   # SHA-256 hex of nonce || ciphertext

    @property
    def compression_ratio(self) -> float:
        return self.original_size / self.compressed_size if self.compressed_size else 0.0


def encrypt_document(key: bytes, plaintext: bytes, aad: bytes, compression: str = "zstd") -> EncryptedDocument:
    """Hash plaintext, compress, encrypt with a fresh random nonce."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    compressed = compress(plaintext, compression)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, aad)
    return EncryptedDocument(
        nonce=nonce,
        ciphertext=ciphertext,
        compression=compression,
        original_size=len(plaintext),
        compressed_size=len(compressed),
        document_hash=hashlib.sha256(plaintext).hexdigest(),
        encrypted_document_hash=hashlib.sha256(nonce + ciphertext).hexdigest(),
    )
