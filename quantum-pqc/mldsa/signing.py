"""ML-DSA-65 signing."""

from __future__ import annotations

from mldsa import ALGORITHM, SECRET_KEY_SIZE, SIGNATURE_SIZE


def sign(secret_key: bytes, message: bytes) -> bytes:
    """Sign ``message`` with pure ML-DSA-65 and an empty context string
    (liboqs default, matching the chaincode's CIRCL verifier). Returns the
    raw 3309-byte signature."""
    import oqs

    if len(secret_key) != SECRET_KEY_SIZE:
        raise ValueError("invalid ML-DSA-65 secret key length")
    with oqs.Signature(ALGORITHM, secret_key=secret_key) as signer:
        signature = bytes(signer.sign(message))
    if len(signature) != SIGNATURE_SIZE:
        raise RuntimeError("liboqs returned an unexpected ML-DSA-65 signature size")
    return signature
