"""Simulated quantum channel between Alice and Bob.

The physical link is modelled as a Pauli channel applied to every photon:

    X with probability e/2, Y with e/2, Z with e/2, identity otherwise.

X or Y flips a Z-basis outcome, and Z or Y flips an X-basis outcome, so the
expected QBER from the channel alone is ``e`` in both bases. This stands in
for fibre and detector noise. It is not an attacker: eavesdropping is added
separately by :mod:`bb84.eavesdropper`.

All circuits are Clifford (X, H, measurement) plus Pauli noise, so they run
on Aer's stabilizer method, which simulates hundreds of qubits exactly and
quickly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import pauli_error

BACKEND_NAME = "aer_simulator_stabilizer"


@dataclass
class QuantumChannel:
    error_rate: float = 0.0
    """Probability that a photon's measurement outcome is flipped by the
    channel (expected QBER contribution), in [0, 0.25]."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.error_rate <= 0.25:
            raise ValueError("channel error_rate must be in [0, 0.25]")

    def transmit(self, states: list[QuantumCircuit]) -> list[QuantumCircuit]:
        """Return copies of the circuits with the channel's noise applied to
        every photon (no-op for an ideal channel)."""
        if self.error_rate == 0.0:
            return [qc.copy() for qc in states]
        e = self.error_rate
        noise = pauli_error([("X", e / 2), ("Y", e / 2), ("Z", e / 2), ("I", 1 - 1.5 * e)])
        delivered = []
        for qc in states:
            out = qc.copy()
            out.barrier()
            for q in range(out.num_qubits):
                out.append(noise, [q])
            delivered.append(out)
        return delivered

    @staticmethod
    def backend(seed: int | None = None) -> AerSimulator:
        """Stabilizer simulator; ``seed`` fixes measurement randomness."""
        return AerSimulator(method="stabilizer", seed_simulator=seed)


def run_and_read(circuits: list[QuantumCircuit], backend: AerSimulator) -> dict[str, np.ndarray]:
    """Run every circuit once (one photon = one shot) and return the measured
    bits of each classical register, concatenated across circuits in photon
    order, e.g. ``{"bob": array([...]), "eve": array([...])}``."""
    result = backend.run(circuits, shots=1, memory=True).result()
    collected: dict[str, list[int]] = {}
    for index, qc in enumerate(circuits):
        # Qiskit prints registers last-created first, each register's bits
        # most-significant (highest index) first.
        fields = result.get_memory(index)[0].split(" ")[::-1]
        for creg, field in zip(qc.cregs, fields, strict=True):
            collected.setdefault(creg.name, []).extend(int(b) for b in reversed(field))
    return {name: np.array(bits, dtype=np.uint8) for name, bits in collected.items()}
