"""Eve: intercept-resend attacker.

For each intercepted photon Eve measures in a random basis and forwards the
state she observed. In the circuit this is a basis rotation, a real
mid-circuit measurement, and the inverse rotation: the post-measurement state
is exactly the eigenstate Eve would re-prepare.

When Eve's basis is wrong (50% of the time) the forwarded state is unbiased in
Alice's basis, so Bob's sifted bit is wrong with probability 1/2. Full
interception therefore yields an expected QBER of 25%, which is what the QBER
check detects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit


@dataclass
class InterceptResendEve:
    rng: np.random.Generator
    interception_rate: float = 1.0
    """Fraction of photons Eve intercepts, in [0, 1]."""

    intercepted: np.ndarray | None = field(default=None, init=False)
    bases: np.ndarray | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.interception_rate <= 1.0:
            raise ValueError("interception_rate must be in [0, 1]")

    @property
    def expected_qber(self) -> float:
        return 0.25 * self.interception_rate

    def intercept(self, states: list[QuantumCircuit]) -> list[QuantumCircuit]:
        """Return copies of the circuits with Eve's measure-and-resend applied
        to a random subset of photons. Her outcomes land in a classical
        register named ``eve`` (diagnostics only: never used by Alice or Bob).
        """
        total = sum(qc.num_qubits for qc in states)
        self.intercepted = self.rng.random(total) < self.interception_rate
        self.bases = self.rng.integers(0, 2, size=total, dtype=np.uint8)

        out_circuits, offset = [], 0
        for qc in states:
            out = qc.copy()
            creg = ClassicalRegister(out.num_qubits, "eve")
            out.add_register(creg)
            out.barrier()
            for q in range(out.num_qubits):
                photon = offset + q
                if not self.intercepted[photon]:
                    continue
                if self.bases[photon]:
                    out.h(q)
                out.measure(q, creg[q])
                if self.bases[photon]:
                    out.h(q)
            out_circuits.append(out)
            offset += out.num_qubits
        return out_circuits
