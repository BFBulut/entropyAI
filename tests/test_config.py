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

def test_cumulative_usage_field():
    cfg = EntropyConfig()
    assert "input_tokens" in cfg.last_cumulative_usage
    assert cfg.last_cumulative_usage["input_tokens"] == 0
    cfg.last_cumulative_usage["input_tokens"] = 12500
    assert cfg.last_cumulative_usage["input_tokens"] == 12500
