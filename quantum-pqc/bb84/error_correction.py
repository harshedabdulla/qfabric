"""Information reconciliation: make Bob's key equal to Alice's.

Recommended for the hackathon: a simplified Cascade (block parity +
binary search, a few passes with shuffling). Count every parity bit
disclosed: that leakage is subtracted during privacy amplification.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ErrorCorrectionResult:
    corrected_key: np.ndarray  # Bob's key after correction
    bits_leaked: int           # parity bits revealed on the public channel
    method: str = "cascade"


def reconcile(
    alice_key: np.ndarray,
    bob_key: np.ndarray,
    qber: float,
    rng: np.random.Generator,
) -> ErrorCorrectionResult:
    """Correct Bob's key towards Alice's. Callers must still confirm the
    keys match (e.g. compare SHA-256 of both keys) before privacy
    amplification; mismatch aborts with KEY_CONFIRMATION_FAILED."""
    raise NotImplementedError("TODO(quantum-pqc): reconcile")
