"""Pytest configuration and test fixtures for Entropy AI."""

import pytest
import sys
from pathlib import Path

# Add src to pythonpath
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

@pytest.fixture
def sample_config():
    from entropy.core.config import EntropyConfig
    return EntropyConfig()
