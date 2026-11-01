"""End-to-end BB84 orchestration.

Workflow (docs/ARCHITECTURE.md, "BB84 key establishment"):

 1. Alice generates random bits and bases.
 2. Alice prepares Qiskit circuits.
 3. Optional Eve intercept-resend (real mid-circuit measurement).
 4. The channel (optionally noisy) delivers states to Bob.
 5. Bob measures in random bases on Qiskit Aer.
 6. Sifting over the classical channel.
 7. QBER estimation on a disclosed sample.
 8. Abort if QBER > threshold (QBER_THRESHOLD_EXCEEDED).
 9. Error correction + key confirmation (KEY_CONFIRMATION_FAILED).
10. Privacy amplification; abort if < 256 secure bits (INSUFFICIENT_KEY_MATERIAL).
11. Output a 256-bit shared secret.

Every classical message is recorded in a canonical transcript. The API layer
signs ``transcript_hash`` with both organizations' ML-DSA-65 keys and
verifies the signatures before accepting the key.

The shared secret never leaves this process. It is kept out of ``repr``,
never logged, and only used through HKDF.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from bb84.alice import Alice
from bb84.basis_reconciliation import choose_sample, estimate_qber, sift
from bb84.bob import Bob
from bb84.eavesdropper import InterceptResendEve
from bb84.error_correction import reconcile
from bb84.privacy_amplification import secure_key_length, toeplitz_hash
from bb84.quantum_channel import BACKEND_NAME, QuantumChannel

TRANSCRIPT_VERSION = "QFABRIC-BB84-TRANSCRIPT-V1"
CONFIRMATION_TAG_BITS = 64


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
    security_margin: int = 64
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.num_qubits < 64:
            raise ValueError("num_qubits must be >= 64")
        if not 0.0 < self.qber_threshold <= 0.11:
            raise ValueError("qber_threshold must be in (0, 0.11]")
        if self.final_key_bits % 8:
            raise ValueError("final_key_bits must be a multiple of 8")


@dataclass
class BB84Result:
    """Public outcome of one run, plus the secret (kept out of repr)."""

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
    transcript: bytes = field(repr=False)
    transcript_hash: str
    eavesdropper_enabled: bool
    interception_rate: float
    duration_ms: float
    backend: str = BACKEND_NAME
    secure_key_capacity: int = 0     # bits PA could have extracted
    shared_secret: bytes | None = field(default=None, repr=False)  # None when ABORTED


class Transcript:
    """Canonical record of every classical-channel message."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def add(self, sender: str, kind: str, **payload) -> None:
        self.messages.append({"from": sender, "type": kind, **payload})

    def to_bytes(self) -> bytes:
        body = {"version": TRANSCRIPT_VERSION, "messages": self.messages}
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _hex_bits(bits: np.ndarray) -> dict:
    return {"bits": np.packbits(bits.astype(np.uint8)).tobytes().hex(), "length": int(bits.size)}


def _confirmation_tag(key: np.ndarray, salt: bytes) -> str:
    digest = hashlib.sha256(salt + np.packbits(key).tobytes()).digest()
    return digest[: CONFIRMATION_TAG_BITS // 8].hex()


def run_bb84(config: BB84Config) -> BB84Result:
    """Run the full protocol described in the module docstring."""
    started = time.perf_counter()
    seeds = np.random.SeedSequence(config.seed).spawn(5)
    alice = Alice(np.random.default_rng(seeds[0]))
    bob = Bob(np.random.default_rng(seeds[1]))
    public = np.random.default_rng(seeds[3])  # public randomness (sampling, permutations, PA seed)
    sim_seed = int(np.random.default_rng(seeds[4]).integers(0, 2**31))
    transcript = Transcript()
    n = config.num_qubits

    # --- Quantum phase -----------------------------------------------------
    alice_bits = alice.generate_bits(n)
    alice_bases = alice.choose_bases(n)
    states = alice.prepare_states(alice_bits, alice_bases)
    if config.eavesdropper:
        states = InterceptResendEve(np.random.default_rng(seeds[2]), config.interception_rate).intercept(states)
    channel = QuantumChannel(config.channel_error_rate)
    states = channel.transmit(states)
    bob_bases = bob.choose_bases(n)
    bob_bits = bob.measure(states, bob_bases, channel.backend(sim_seed))["bob"]

    # --- Sifting -----------------------------------------------------------
    transcript.add("bob", "bases", **_hex_bits(bob_bases))
    transcript.add("alice", "bases", **_hex_bits(alice_bases))
    sifted = sift(alice_bases, bob_bases)
    alice_sifted, bob_sifted = alice_bits[sifted], bob_bits[sifted]

    # --- Parameter estimation ----------------------------------------------
    sample = choose_sample(sifted.size, config.sample_fraction, public)
    mask = np.zeros(sifted.size, dtype=bool)
    mask[sample] = True
    qber = estimate_qber(alice_sifted[mask], bob_sifted[mask])
    transcript.add("alice", "sample", positions=_hex_bits(mask.astype(np.uint8))["bits"], **_hex_bits(alice_sifted[mask]))
    transcript.add("bob", "sample", **_hex_bits(bob_sifted[mask]))
    alice_key, bob_key = alice_sifted[~mask], bob_sifted[~mask]

    def finish(status: str, reason: AbortReason | None, *, leaked=0, confirmed=False,
               capacity=0, secret: bytes | None = None) -> BB84Result:
        transcript.add("alice", "outcome", status=status, abortReason=reason.value if reason else None)
        raw = transcript.to_bytes()
        return BB84Result(
            status=status, abort_reason=reason, num_qubits=n,
            sifted_key_length=int(sifted.size), sample_size=int(sample.size),
            qber=qber, qber_threshold=config.qber_threshold, bits_leaked=leaked,
            final_key_length=config.final_key_bits if secret else 0, key_confirmed=confirmed,
            transcript=raw, transcript_hash=hashlib.sha256(raw).hexdigest(),
            eavesdropper_enabled=config.eavesdropper,
            interception_rate=config.interception_rate if config.eavesdropper else 0.0,
            duration_ms=(time.perf_counter() - started) * 1000,
            secure_key_capacity=capacity, shared_secret=secret,
        )

    transcript.add("alice", "qber", qberPpm=round(qber * 1_000_000),
                   thresholdPpm=round(config.qber_threshold * 1_000_000))
    if qber > config.qber_threshold:
        return finish("ABORTED", AbortReason.QBER_THRESHOLD_EXCEEDED)

    # --- Error correction + key confirmation (up to two rounds) ------------
    leaked, confirmed, corrected, passes_done = 0, False, bob_key, 0
    for _ in range(2):
        ec = reconcile(alice_key, corrected, qber, public, passes=4, start_pass=passes_done)
        corrected, passes_done = ec.corrected_key, passes_done + ec.passes
        leaked += ec.bits_leaked
        for message in ec.messages:
            transcript.add("alice", "cascade", **message)
        salt = public.bytes(16)
        tag = _confirmation_tag(alice_key, salt)
        confirmed = tag == _confirmation_tag(corrected, salt)
        leaked += CONFIRMATION_TAG_BITS
        transcript.add("alice", "confirmation", salt=salt.hex(), tag=tag)
        transcript.add("bob", "confirmation", match=confirmed)
        if confirmed:
            break
    if not confirmed:
        return finish("ABORTED", AbortReason.KEY_CONFIRMATION_FAILED, leaked=leaked)

    # --- Privacy amplification ---------------------------------------------
    capacity = secure_key_length(alice_key.size, qber, leaked, config.security_margin)
    if capacity < config.final_key_bits:
        return finish("ABORTED", AbortReason.INSUFFICIENT_KEY_MATERIAL, leaked=leaked,
                      confirmed=True, capacity=capacity)
    pa_seed = public.bytes(32)
    transcript.add("alice", "privacy_amplification", seed=pa_seed.hex(), outputBits=config.final_key_bits)
    alice_final = toeplitz_hash(alice_key, config.final_key_bits, pa_seed)
    bob_final = toeplitz_hash(corrected, config.final_key_bits, pa_seed)
    if not np.array_equal(alice_final, bob_final):  # cannot happen after confirmation; defensive
        return finish("ABORTED", AbortReason.KEY_CONFIRMATION_FAILED, leaked=leaked)
    secret = np.packbits(alice_final).tobytes()
    return finish("SUCCESS", None, leaked=leaked, confirmed=True, capacity=capacity, secret=secret)
