"""Alice: the sender in BB84. She generates random bits and bases and
encodes each bit as a single-qubit state in a Qiskit circuit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister

# Qubits per simulated circuit. Each qubit is an independent "photon": there
# are no gates between qubits, so batching W photons into one W-qubit circuit
# is physically equivalent to W separate transmissions. It just lets the
# stabilizer simulator run the whole exchange in a handful of jobs.
BLOCK_WIDTH = 64


@dataclass
class Alice:
    """Sender state for one BB84 run.

    ``rng`` is a NumPy generator seeded from :class:`bb84.protocol.BB84Config`,
    so runs are reproducible. This is a simulation choice; a real deployment
    needs a QRNG/CSPRNG (see docs/SECURITY_MODEL.md, assumption A4).
    """

    rng: np.random.Generator

    def generate_bits(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random bits (dtype uint8, values 0/1)."""
        return self.rng.integers(0, 2, size=n, dtype=np.uint8)

    def choose_bases(self, n: int) -> np.ndarray:
        """Return ``n`` uniformly random bases (0 = Z, 1 = X)."""
        return self.rng.integers(0, 2, size=n, dtype=np.uint8)

    def prepare_states(self, bits: np.ndarray, bases: np.ndarray) -> list[QuantumCircuit]:
        """Encode each bit as a qubit state, ``BLOCK_WIDTH`` qubits per circuit.

        bit 0 / Z -> |0>    bit 1 / Z -> |1>
        bit 0 / X -> |+>    bit 1 / X -> |->

        Qubit ``i`` of circuit ``k`` carries photon ``k * BLOCK_WIDTH + i``.
        Circuits have no classical registers yet: Eve and Bob add their own.
        """
        if bits.shape != bases.shape:
            raise ValueError("bits and bases must have the same length")
        circuits = []
        for start in range(0, len(bits), BLOCK_WIDTH):
            width = min(BLOCK_WIDTH, len(bits) - start)
            qc = QuantumCircuit(QuantumRegister(width, "photon"), name=f"bb84_block_{start // BLOCK_WIDTH}")
            for i in range(width):
                if bits[start + i]:
                    qc.x(i)
                if bases[start + i]:
                    qc.h(i)
            circuits.append(qc)
        return circuits
