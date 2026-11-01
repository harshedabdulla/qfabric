"""Lossless document compression before encryption.

Methods: "zstd" (default, zstandard level 10), "gzip" (stdlib), "none".
Decompression reads at most ``max_size + 1`` bytes and refuses anything
larger, so a small malicious payload cannot expand into a decompression bomb.
"""

from __future__ import annotations

import gzip
import io

import zstandard

SUPPORTED = ("zstd", "gzip", "none")
ZSTD_LEVEL = 10


def compress(data: bytes, method: str = "zstd") -> bytes:
    if method == "zstd":
        return zstandard.ZstdCompressor(level=ZSTD_LEVEL).compress(data)
    if method == "gzip":
        return gzip.compress(data, compresslevel=9, mtime=0)
    if method == "none":
        return data
    raise ValueError(f"unsupported compression {method!r}")


def decompress(data: bytes, method: str, max_size: int) -> bytes:
    if method == "none":
        out = data
    elif method == "zstd":
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
            out = reader.read(max_size + 1)
    elif method == "gzip":
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as reader:
            out = reader.read(max_size + 1)
    else:
        raise ValueError(f"unsupported compression {method!r}")
    if len(out) > max_size:
        raise ValueError("decompressed document exceeds the size limit")
    return out
