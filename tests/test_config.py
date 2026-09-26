"""Tests for settings loading."""

from src.config import Settings


def test_empty_env_vars_fall_back_to_defaults(monkeypatch):
    """Empty env vars (e.g. created blank in a hosting dashboard) must not crash startup."""
    monkeypatch.setenv("LLM_TEMPERATURE", "")
    monkeypatch.setenv("LLM_MAX_TOKENS", "")

    s = Settings()

    assert s.llm.temperature == 0.1
    assert s.llm.max_tokens == 4096


def test_blank_data_provider_falls_back_to_yfinance(monkeypatch):
    """DATA_PROVIDER="" must use the yfinance default, not raise 'Unknown provider'."""
    import src.data.provider as provider

    monkeypatch.setenv("DATA_PROVIDER", "")
    monkeypatch.setattr(provider, "_provider_instance", None)

    assert (
        type(provider.get_provider()).__name__
        == type(provider._create_provider("yfinance")).__name__
    )
