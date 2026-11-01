"""Privacy amplification: compress the reconciled key to remove Eve's
partial information.

Toeplitz-matrix universal hashing with a public random seed. Asymptotic
secure length estimate:

    final_len = n * (1 - h(qber)) - bits_leaked - security_margin

where h is the binary entropy. This ignores finite-key effects (a
documented limitation).
"""

from __future__ import annotations

import hashlib
import math

import numpy as np


def binary_entropy(p: float) -> float:
    """h(p) = -p log2 p - (1-p) log2 (1-p), with h(0) = h(1) = 0."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def secure_key_length(n: int, qber: float, bits_leaked: int, security_margin: int = 64) -> int:
    """Return the number of secure bits extractable, floored at 0."""
    return max(0, math.floor(n * (1 - binary_entropy(qber)) - bits_leaked - security_margin))


def toeplitz_hash(key: np.ndarray, output_len: int, seed: bytes) -> np.ndarray:
    """Hash ``key`` (bits) to ``output_len`` bits with a Toeplitz matrix
    whose first row and column come from SHAKE-256(seed)."""
    n = key.size
    if not 0 < output_len <= n:
        raise ValueError("output_len must be in (0, len(key)]")
    needed = output_len + n - 1
    stream = hashlib.shake_256(seed).digest((needed + 7) // 8)
    diagonal = np.unpackbits(np.frombuffer(stream, dtype=np.uint8))[:needed]
    rows = np.arange(output_len)[:, None]
    cols = np.arange(n)[None, :]
    matrix = diagonal[rows - cols + n - 1]          # T[i, j] depends only on i - j
    return ((matrix.astype(np.int64) @ key.astype(np.int64)) % 2).astype(np.uint8)
