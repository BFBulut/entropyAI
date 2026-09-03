"""Basic smoke test for Entropy AI configuration."""

from entropy.core.config import config, EntropyConfig

def test_default_config():
    assert config.app_name == "Entropy AI"
    assert config.default_mode == "floating"
    assert config.model_fallback_name == "[Model: Unknown]"

def test_custom_config():
    custom = EntropyConfig(app_name="Test Entropy", default_mode="chat")
    assert custom.app_name == "Test Entropy"
    assert custom.default_mode == "chat"
