"""Privacy amplification: compress the reconciled key to remove Eve's
partial information.

Recommended: Toeplitz-matrix universal hashing with a public random seed.
Asymptotic secure length estimate:

    final_len = n * (1 - h(qber)) - bits_leaked - security_margin

where h is the binary entropy. This ignores finite-key effects
(documented limitation).
"""

from __future__ import annotations

import numpy as np


def binary_entropy(p: float) -> float:
    """h(p) = -p log2 p - (1-p) log2 (1-p), with h(0) = h(1) = 0."""
    raise NotImplementedError("TODO(quantum-pqc): binary_entropy")


def secure_key_length(n: int, qber: float, bits_leaked: int, security_margin: int = 64) -> int:
    """Return the number of secure bits extractable, floored at 0."""
    raise NotImplementedError("TODO(quantum-pqc): secure_key_length")


def toeplitz_hash(key: np.ndarray, output_len: int, seed: bytes) -> np.ndarray:
    """Hash ``key`` (bits) to ``output_len`` bits with a Toeplitz matrix
    derived from the public ``seed``."""
    raise NotImplementedError("TODO(quantum-pqc): toeplitz_hash")
