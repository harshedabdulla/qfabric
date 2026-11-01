"""Eve: intercept-resend attacker.

For each intercepted qubit Eve measures in a random basis and re-prepares
the state she observed. When her basis is wrong (50%), Bob's sifted bit is
wrong with probability 50%, so full interception yields an expected QBER of
25%. This is what the QBER check must detect.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit


@dataclass
class InterceptResendEve:
    rng: np.random.Generator
    interception_rate: float = 1.0
    """Fraction of qubits Eve intercepts, in [0, 1]. Expected QBER
    contribution is ``0.25 * interception_rate``."""

    def intercept(self, states: list[QuantumCircuit], backend) -> list[QuantumCircuit]:
        """Measure the selected qubits in random bases and return the
        re-prepared circuits Eve forwards to Bob. Untouched qubits pass
        through unchanged. Must use real circuit measurement, not a shortcut
        on Alice's private bits."""
        raise NotImplementedError("TODO(quantum-pqc): InterceptResendEve.intercept")

    @property
    def expected_qber(self) -> float:
        return 0.25 * self.interception_rate
