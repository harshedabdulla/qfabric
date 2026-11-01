"""Bob: the receiver in BB84. Chooses random bases and measures the
incoming qubits on the Aer simulator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit


@dataclass
class Bob:
    rng: np.random.Generator

    def choose_bases(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random measurement bases (0 = Z, 1 = X)."""
        raise NotImplementedError("TODO(quantum-pqc): Bob.choose_bases")

    def measure(self, states: list[QuantumCircuit], bases: np.ndarray, backend) -> np.ndarray:
        """Measure each received state in the chosen basis and return bits.

        For basis X apply H before measuring in Z. Run all circuits as one
        batched job with ``shots=1`` (one photon per circuit) on ``backend``
        (an ``AerSimulator``, optionally with a noise model from
        :class:`bb84.quantum_channel.QuantumChannel`).
        """
        raise NotImplementedError("TODO(quantum-pqc): Bob.measure")
