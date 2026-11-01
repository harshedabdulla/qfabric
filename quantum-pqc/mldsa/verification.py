"""ML-DSA-65 verification."""

from __future__ import annotations

from mldsa import ALGORITHM, PUBLIC_KEY_SIZE, SIGNATURE_SIZE


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return True only for a valid signature. Malformed inputs (wrong
    lengths, undecodable key) return False rather than raising."""
    if len(public_key) != PUBLIC_KEY_SIZE or len(signature) != SIGNATURE_SIZE:
        return False
    import oqs

    try:
        with oqs.Signature(ALGORITHM) as verifier:
            return bool(verifier.verify(message, signature, public_key))
    except Exception:  # liboqs raises on malformed input
        return False
