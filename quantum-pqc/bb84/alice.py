"""Alice: the sender in BB84. Generates random bits and bases and prepares
one single-qubit Qiskit circuit per bit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit


@dataclass
class Alice:
    """Sender state for one BB84 run.

    Use ``np.random.Generator`` seeded from :class:`bb84.protocol.BB84Config`
    so runs are reproducible in tests. For anything beyond simulation the
    randomness source must be a CSPRNG/QRNG (documented limitation).
    """

    rng: np.random.Generator

    def generate_bits(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random bits (dtype uint8, values 0/1)."""
        raise NotImplementedError("TODO(quantum-pqc): Alice.generate_bits")

    def choose_bases(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random bases (0 = Z, 1 = X)."""
        raise NotImplementedError("TODO(quantum-pqc): Alice.choose_bases")

    def prepare_states(self, bits: np.ndarray, bases: np.ndarray) -> list[QuantumCircuit]:
        """Encode each bit as a single-qubit circuit (1 qubit, 1 classical bit).

        bit 1  -> apply X
        basis X -> then apply H
        Bob appends his measurement later; do not measure here.
        """
        raise NotImplementedError("TODO(quantum-pqc): Alice.prepare_states")
