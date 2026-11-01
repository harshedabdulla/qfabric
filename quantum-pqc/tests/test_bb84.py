"""BB84 behaviour without an eavesdropper."""

import numpy as np
import pytest

from bb84 import BB84Config, run_bb84
from bb84.alice import BLOCK_WIDTH, Alice
from bb84.basis_reconciliation import choose_sample, estimate_qber, sift
from bb84.bob import Bob
from bb84.error_correction import reconcile
from bb84.privacy_amplification import binary_entropy, secure_key_length, toeplitz_hash
from bb84.quantum_channel import QuantumChannel


def test_alice_bits_and_bases_are_binary():
    alice = Alice(rng=np.random.default_rng(1))
    bits, bases = alice.generate_bits(512), alice.choose_bases(512)
    assert bits.shape == bases.shape == (512,)
    assert set(np.unique(bits)) <= {0, 1} and set(np.unique(bases)) <= {0, 1}


def test_prepare_states_builds_real_qiskit_circuits():
    alice = Alice(rng=np.random.default_rng(2))
    n = BLOCK_WIDTH + 6
    circuits = alice.prepare_states(np.ones(n, dtype=np.uint8), np.ones(n, dtype=np.uint8))
    assert [c.num_qubits for c in circuits] == [BLOCK_WIDTH, 6]
    ops = circuits[0].count_ops()
    assert ops["x"] == BLOCK_WIDTH and ops["h"] == BLOCK_WIDTH  # |-> = H X |0>


@pytest.mark.parametrize("bit,basis", [(0, 0), (1, 0), (0, 1), (1, 1)])
def test_matching_basis_measurement_recovers_bit(bit, basis):
    n = 32
    bits, bases = np.full(n, bit, dtype=np.uint8), np.full(n, basis, dtype=np.uint8)
    states = Alice(np.random.default_rng(0)).prepare_states(bits, bases)
    measured = Bob(np.random.default_rng(0)).measure(states, bases, QuantumChannel.backend(seed=1))["bob"]
    assert np.array_equal(measured, bits)


def test_wrong_basis_measurement_is_random():
    n = 2000
    states = Alice(np.random.default_rng(0)).prepare_states(np.zeros(n, dtype=np.uint8), np.zeros(n, dtype=np.uint8))
    measured = Bob(np.random.default_rng(0)).measure(states, np.ones(n, dtype=np.uint8), QuantumChannel.backend(seed=3))["bob"]
    assert 0.45 < measured.mean() < 0.55


def test_sift_keeps_matching_bases_only():
    idx = sift(np.array([0, 1, 1, 0]), np.array([0, 0, 1, 1]))
    assert list(idx) == [0, 2]


def test_choose_sample_is_unique_and_sorted():
    sample = choose_sample(1000, 0.25, np.random.default_rng(0))
    assert sample.size == 250 and np.all(np.diff(sample) > 0)


def test_estimate_qber():
    assert estimate_qber(np.array([0, 1, 1, 0]), np.array([0, 1, 0, 0])) == pytest.approx(0.25)


def test_binary_entropy_edges():
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(0.5) == pytest.approx(1.0)


def test_secure_key_length_shrinks_with_qber():
    assert secure_key_length(1000, 0.0, 0) > secure_key_length(1000, 0.05, 100) >= 0


@pytest.mark.parametrize("error_rate", [0.01, 0.03, 0.06])
def test_cascade_corrects_all_errors(error_rate):
    rng = np.random.default_rng(4)
    alice = rng.integers(0, 2, 2000, dtype=np.uint8)
    flips = rng.random(2000) < error_rate
    bob = alice ^ flips.astype(np.uint8)
    result = reconcile(alice, bob, error_rate, np.random.default_rng(5))
    assert np.array_equal(result.corrected_key, alice)
    assert result.errors_corrected >= int(flips.sum())
    assert 0 < result.bits_leaked < 2000


def test_toeplitz_hash_is_deterministic_and_linear():
    rng = np.random.default_rng(6)
    a, b = rng.integers(0, 2, 500, dtype=np.uint8), rng.integers(0, 2, 500, dtype=np.uint8)
    h = lambda k: toeplitz_hash(k, 128, b"seed")  # noqa: E731
    assert h(a).shape == (128,) and np.array_equal(h(a), h(a))
    assert np.array_equal(h(a ^ b), h(a) ^ h(b))  # universal hash family is GF(2)-linear
    assert not np.array_equal(h(a), toeplitz_hash(a, 128, b"other"))


def test_ideal_channel_succeeds_with_256_bit_key():
    result = run_bb84(BB84Config(num_qubits=2048, seed=7))
    assert result.status == "SUCCESS"
    assert result.qber == pytest.approx(0.0, abs=1e-9)
    assert result.key_confirmed
    assert result.shared_secret is not None and len(result.shared_secret) == 32
    assert len(result.transcript_hash) == 64


def test_secret_not_in_repr():
    result = run_bb84(BB84Config(num_qubits=2048, seed=3))
    assert result.shared_secret.hex() not in repr(result)


def test_runs_are_reproducible_with_seed_and_random_without():
    a, b = run_bb84(BB84Config(seed=21)), run_bb84(BB84Config(seed=21))
    assert a.shared_secret == b.shared_secret and a.transcript_hash == b.transcript_hash
    assert run_bb84(BB84Config()).shared_secret != run_bb84(BB84Config()).shared_secret


def test_noisy_channel_below_threshold_still_succeeds():
    result = run_bb84(BB84Config(num_qubits=4096, channel_error_rate=0.02, seed=11))
    assert result.status == "SUCCESS"
    assert 0.0 < result.qber < 0.11
    assert result.bits_leaked > 0
