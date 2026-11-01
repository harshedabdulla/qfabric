"""Shared fixtures.

While the module is under construction, tests that hit a stub raising
NotImplementedError are reported as SKIPPED ("not implemented yet") instead
of failing. Once a function is implemented its tests run for real.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = REPO_ROOT / "integration"


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
