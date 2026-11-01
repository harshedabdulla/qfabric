"""Bob: the receiver in BB84. He chooses random bases and measures the
incoming photons on the Aer simulator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit

from bb84.quantum_channel import run_and_read


@dataclass
class Bob:
    rng: np.random.Generator

    def choose_bases(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random measurement bases (0 = Z, 1 = X)."""
        return self.rng.integers(0, 2, size=n, dtype=np.uint8)

    def measure(self, states: list[QuantumCircuit], bases: np.ndarray, backend) -> dict[str, np.ndarray]:
        """Measure every received photon in Bob's basis (H before a Z
        measurement for basis X) and run the circuits.

        Returns all classical registers of the run. ``"bob"`` holds Bob's
        bits; ``"eve"`` is present when Eve intercepted (simulation
        diagnostics only).
        """
        circuits, offset = [], 0
        for qc in states:
            out = qc.copy()
            creg = ClassicalRegister(out.num_qubits, "bob")
            out.add_register(creg)
            out.barrier()
            for q in range(out.num_qubits):
                if bases[offset + q]:
                    out.h(q)
                out.measure(q, creg[q])
            circuits.append(out)
            offset += out.num_qubits
        if offset != len(bases):
            raise ValueError("number of bases does not match number of photons")
        return run_and_read(circuits, backend)
