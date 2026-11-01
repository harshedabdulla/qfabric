"""Sifting and QBER estimation over the authenticated classical channel.

Every message exchanged here (Bob's bases, Alice's matching indices, the
sampled bits) is appended to the protocol transcript, which both parties
sign with ML-DSA-65 (see bb84/protocol.py and api/services.py).
"""

from __future__ import annotations

import numpy as np


def sift(alice_bases: np.ndarray, bob_bases: np.ndarray) -> np.ndarray:
    """Return the indices where Alice's and Bob's bases match (~50%)."""
    if alice_bases.shape != bob_bases.shape:
        raise ValueError("basis arrays must have the same length")
    return np.flatnonzero(alice_bases == bob_bases)


def choose_sample(sifted_len: int, sample_fraction: float, rng: np.random.Generator) -> np.ndarray:
    """Pick random positions (within the sifted key) to disclose for QBER
    estimation, sorted ascending. Disclosed bits are discarded from the key
    afterwards. At least one position is sampled."""
    if not 0.0 < sample_fraction < 1.0:
        raise ValueError("sample_fraction must be in (0, 1)")
    size = max(1, round(sifted_len * sample_fraction))
    return np.sort(rng.choice(sifted_len, size=size, replace=False))


def estimate_qber(alice_sample: np.ndarray, bob_sample: np.ndarray) -> float:
    """Fraction of mismatching bits in the disclosed sample."""
    if alice_sample.shape != bob_sample.shape or alice_sample.size == 0:
        raise ValueError("samples must be non-empty and the same length")
    return float(np.count_nonzero(alice_sample != bob_sample)) / alice_sample.size
