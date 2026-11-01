"""ML-DSA-65 signing."""

from __future__ import annotations


def sign(secret_key: bytes, message: bytes) -> bytes:
    """Sign ``message`` (pure ML-DSA-65, empty context) and return the raw
    3309-byte signature."""
    raise NotImplementedError("TODO(quantum-pqc): sign")
