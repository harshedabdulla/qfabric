"""ML-DSA-65 verification."""

from __future__ import annotations


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return True only for a valid signature. Malformed inputs (wrong
    lengths, undecodable key) return False rather than raising."""
    raise NotImplementedError("TODO(quantum-pqc): verify")
