"""Lossless document compression before encryption.

Methods: "zstd" (default, zstandard), "gzip" (stdlib), "none".
Enforce a maximum decompressed size (QFABRIC_MAX_DOCUMENT_BYTES) on
decompression to prevent decompression bombs.
"""

from __future__ import annotations

SUPPORTED = ("zstd", "gzip", "none")


def compress(data: bytes, method: str = "zstd") -> bytes:
    raise NotImplementedError("TODO(quantum-pqc): compress")


def decompress(data: bytes, method: str, max_size: int) -> bytes:
    raise NotImplementedError("TODO(quantum-pqc): decompress")
