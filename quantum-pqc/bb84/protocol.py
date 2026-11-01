"""End-to-end BB84 orchestration.

Workflow (docs/ARCHITECTURE.md, "BB84 key establishment"):

 1. Alice generates random bits and bases.
 2. Alice prepares Qiskit circuits.
 3. Optional Eve intercept-resend.
 4. Channel (optionally noisy) delivers states to Bob.
 5. Bob measures in random bases.
 6. Sifting over the authenticated classical channel.
 7. QBER estimation on a disclosed sample.
 8. Abort if QBER > threshold (QBER_THRESHOLD_EXCEEDED).
 9. Error correction + key confirmation (KEY_CONFIRMATION_FAILED).
10. Privacy amplification; abort if < 256 bits (INSUFFICIENT_KEY_MATERIAL).
11. Output a 256-bit shared secret.

The shared secret never leaves this process: it is stored in the API's
in-memory session store and only used through HKDF. It is never logged,
returned by the API, or written to Fabric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AbortReason(str, Enum):
    QBER_THRESHOLD_EXCEEDED = "QBER_THRESHOLD_EXCEEDED"
    KEY_CONFIRMATION_FAILED = "KEY_CONFIRMATION_FAILED"
    INSUFFICIENT_KEY_MATERIAL = "INSUFFICIENT_KEY_MATERIAL"


@dataclass(frozen=True)
class BB84Config:
    num_qubits: int = 2048
    sample_fraction: float = 0.25
    qber_threshold: float = 0.11
    channel_error_rate: float = 0.0
    eavesdropper: bool = False
    interception_rate: float = 1.0
    final_key_bits: int = 256
    seed: int | None = None


@dataclass
class BB84Result:
    """Public outcome of one run plus the secret (kept out of repr)."""

    status: str                      # "SUCCESS" | "ABORTED"
    abort_reason: AbortReason | None
    num_qubits: int
    sifted_key_length: int
    sample_size: int
    qber: float
    qber_threshold: float
    bits_leaked: int
    final_key_length: int
    key_confirmed: bool
    transcript: bytes                # canonical classical-channel transcript
    transcript_hash: str             # lowercase hex SHA-256 of transcript
    eavesdropper_enabled: bool
    interception_rate: float
    duration_ms: float
    shared_secret: bytes | None = field(default=None, repr=False)  # None when ABORTED


def run_bb84(config: BB84Config) -> BB84Result:
    """Run the full protocol described in the module docstring."""
    raise NotImplementedError("TODO(quantum-pqc): run_bb84")
