"""Simulated quantum channel between Alice and Bob.

Models the physical link as an optional noise source. With
``error_rate == 0`` the channel is ideal and QBER without Eve is 0.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiskit import QuantumCircuit


@dataclass
class QuantumChannel:
    error_rate: float = 0.0
    """Probability that a transmitted qubit is disturbed (e.g. bit-flip /
    depolarizing). Represents fibre/detector noise, not an attacker."""

    def transmit(self, states: list[QuantumCircuit]) -> list[QuantumCircuit]:
        """Return the states as delivered to Bob (eavesdropping is applied
        separately by :mod:`bb84.eavesdropper` before transmission ends)."""
        raise NotImplementedError("TODO(quantum-pqc): QuantumChannel.transmit")

    def backend(self, seed: int | None = None):
        """Return an ``AerSimulator`` configured with this channel's noise
        model (``qiskit_aer.noise.NoiseModel``) and ``seed_simulator``."""
        raise NotImplementedError("TODO(quantum-pqc): QuantumChannel.backend")
