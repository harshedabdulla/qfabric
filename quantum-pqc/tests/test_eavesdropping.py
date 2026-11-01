"""Intercept-resend detection through QBER."""

import numpy as np
import pytest

from bb84 import BB84Config, run_bb84
from bb84.eavesdropper import InterceptResendEve
from bb84.protocol import AbortReason


def test_expected_qber_model():
    assert InterceptResendEve(rng=np.random.default_rng(0), interception_rate=1.0).expected_qber == 0.25
    assert InterceptResendEve(rng=np.random.default_rng(0), interception_rate=0.4).expected_qber == pytest.approx(0.10)


def test_full_intercept_resend_is_detected_and_aborts():
    result = run_bb84(BB84Config(num_qubits=2048, eavesdropper=True, interception_rate=1.0, seed=5))
    assert result.status == "ABORTED"
    assert result.abort_reason == AbortReason.QBER_THRESHOLD_EXCEEDED
    assert result.qber == pytest.approx(0.25, abs=0.06)
    assert result.shared_secret is None


def test_partial_interception_raises_qber_proportionally():
    low = run_bb84(BB84Config(num_qubits=4096, eavesdropper=True, interception_rate=0.2, seed=9))
    high = run_bb84(BB84Config(num_qubits=4096, eavesdropper=True, interception_rate=0.8, seed=9))
    assert low.qber < high.qber
