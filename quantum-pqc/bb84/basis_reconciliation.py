"""Sifting and QBER estimation over the authenticated classical channel.

Every message exchanged here (Bob's bases, Alice's matching indices, the
sampled bits) is appended to the protocol transcript, which both parties
sign with ML-DSA-65. See bb84/protocol.py.
"""

from __future__ import annotations

import numpy as np


def sift(alice_bases: np.ndarray, bob_bases: np.ndarray) -> np.ndarray:
    """Return the indices where Alice's and Bob's bases match (~50%)."""
    raise NotImplementedError("TODO(quantum-pqc): sift")


def choose_sample(sifted_len: int, sample_fraction: float, rng: np.random.Generator) -> np.ndarray:
    """Pick random positions (within the sifted key) to disclose for QBER
    estimation. Disclosed bits are discarded from the key afterwards."""
    raise NotImplementedError("TODO(quantum-pqc): choose_sample")


def estimate_qber(alice_sample: np.ndarray, bob_sample: np.ndarray) -> float:
    """Fraction of mismatching bits in the disclosed sample."""
    raise NotImplementedError("TODO(quantum-pqc): estimate_qber")
