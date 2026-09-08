"""
Automated Test Suite: Antigravity Status Service & Diagnostics.
Validates:
1. Executable discovery in system PATH and Windows locations.
2. Responsiveness and version detection.
3. Cache TTL behavior.
"""

import pytest
from pathlib import Path
from src.entropy.agent_desk.core.agy_status import AntigravityStatusService


def test_agy_executable_detection():
    service = AntigravityStatusService()
    bin_path = service.find_agy_executable()
    # On Windows where agy is installed, this must return a valid existing path
    assert bin_path is not None
    assert Path(bin_path).exists()
    assert "agy" in bin_path.lower()


def test_agy_connection_check():
    service = AntigravityStatusService()
    status = service.check_connection(force_refresh=True)
    assert isinstance(status, dict)
    assert "is_connected" in status
    assert "version" in status
    assert "binary_path" in status
    assert "latency_ms" in status
    assert status["is_connected"] is True
    assert status["version"] != ""
    assert status["latency_ms"] >= 0.0


def test_agy_status_caching():
    service = AntigravityStatusService()
    s1 = service.check_connection(force_refresh=True)
    s2 = service.check_connection(force_refresh=False)
    assert s1["timestamp"] == s2["timestamp"], "Cached status should be returned without re-executing subprocess"
