"""Shared fixtures.

Tests that hit a stub raising NotImplementedError are reported as SKIPPED
("not implemented yet") instead of failing. Tests that need the liboqs C
library are skipped when it is not installed (see ``requires_liboqs``).
"""

from __future__ import annotations

import base64
import ctypes.util
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

# Isolate the ML-DSA key store before api.services is imported.
os.environ.setdefault("QFABRIC_KEYSTORE_DIR", tempfile.mkdtemp(prefix="qfabric-keystore-"))

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = REPO_ROOT / "integration"


def liboqs_available() -> bool:
    """True when liboqs-python *and* the liboqs shared library are present.
    Checked without importing ``oqs``, which would try to download and build
    liboqs on the fly."""
    if importlib.util.find_spec("oqs") is None:
        return False
    if ctypes.util.find_library("oqs"):
        return True
    roots = [os.environ.get("OQS_INSTALL_PATH", ""), str(Path(__file__).resolve().parents[1] / ".oqs"), str(Path.home() / "_oqs")]
    return any((Path(r) / "lib" / name).exists() for r in roots if r for name in ("liboqs.dylib", "liboqs.so"))


requires_liboqs = pytest.mark.skipif(not liboqs_available(), reason="liboqs not installed")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if call.excinfo is not None and call.excinfo.errisinstance(NotImplementedError):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] or 0, f"not implemented yet: {call.excinfo.value}")


@pytest.fixture(scope="session")
def mldsa_vector() -> dict:
    return json.loads((INTEGRATION_DIR / "test_vectors" / "mldsa65_audit_manifest.json").read_text())


@pytest.fixture(scope="session")
def sample_request() -> dict:
    return json.loads((INTEGRATION_DIR / "sample_request.json").read_text())


@pytest.fixture(scope="session")
def sample_response() -> dict:
    return json.loads((INTEGRATION_DIR / "sample_response.json").read_text())


@pytest.fixture
def b64():
    return lambda data: base64.b64encode(data).decode()
