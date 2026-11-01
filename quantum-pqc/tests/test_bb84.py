"""BB84 behaviour without an eavesdropper."""

import numpy as np
import pytest

from bb84 import BB84Config, run_bb84
from bb84.alice import Alice
from bb84.basis_reconciliation import estimate_qber, sift
from bb84.privacy_amplification import binary_entropy, secure_key_length


def test_alice_bits_and_bases_are_binary():
    alice = Alice(rng=np.random.default_rng(1))
    bits, bases = alice.generate_bits(512), alice.choose_bases(512)
    assert bits.shape == bases.shape == (512,)
    assert set(np.unique(bits)) <= {0, 1} and set(np.unique(bases)) <= {0, 1}


def test_prepare_states_builds_one_qubit_circuits():
    alice = Alice(rng=np.random.default_rng(2))
    circuits = alice.prepare_states(np.array([0, 1, 0, 1]), np.array([0, 0, 1, 1]))
    assert len(circuits) == 4
    assert all(c.num_qubits == 1 for c in circuits)


def test_sift_keeps_matching_bases_only():
    idx = sift(np.array([0, 1, 1, 0]), np.array([0, 0, 1, 1]))
    assert list(idx) == [0, 2]


def test_estimate_qber():
    assert estimate_qber(np.array([0, 1, 1, 0]), np.array([0, 1, 0, 0])) == pytest.approx(0.25)


def test_binary_entropy_edges():
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(0.5) == pytest.approx(1.0)


def test_secure_key_length_shrinks_with_qber():
    assert secure_key_length(1000, 0.0, 0) > secure_key_length(1000, 0.05, 100) >= 0


def test_ideal_channel_succeeds_with_256_bit_key():
    result = run_bb84(BB84Config(num_qubits=2048, seed=7))
    assert result.status == "SUCCESS"
    assert result.qber == pytest.approx(0.0, abs=1e-9)
    assert result.key_confirmed
    assert result.shared_secret is not None and len(result.shared_secret) == 32
    assert len(result.transcript_hash) == 64


def test_secret_not_in_repr():
    result = run_bb84(BB84Config(num_qubits=1024, seed=3))
    assert result.shared_secret.hex() not in repr(result)


def test_noisy_channel_below_threshold_still_succeeds():
    result = run_bb84(BB84Config(num_qubits=4096, channel_error_rate=0.02, seed=11))
    assert result.status == "SUCCESS"
    assert 0.0 < result.qber < 0.11
