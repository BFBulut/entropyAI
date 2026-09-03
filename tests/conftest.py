"""Pytest configuration and test fixtures for Entropy AI."""

import os
import pytest
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Add src to pythonpath
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

@pytest.fixture
def sample_config():
    from entropy.core.config import EntropyConfig
    return EntropyConfig()

@pytest.fixture(scope="session")
def qapp():
    """Ensure offscreen platform plugin for headless CI/CD testing."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
