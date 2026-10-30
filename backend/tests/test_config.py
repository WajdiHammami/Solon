"""Tests for ``backend.config`` settings loading."""

from backend.config import Settings, get_settings


def test_defaults_when_env_absent(monkeypatch):
    for var in ("NEWSAPI_KEY", "GROQ_API_KEY", "GROQ_MODEL", "PROFILE_PATH"):
        monkeypatch.delenv(var, raising=False)
    # Avoid picking up a developer's local .env during the test.
    settings = Settings(_env_file=None)
    assert settings.newsapi_key == ""
    assert settings.groq_api_key == ""
    assert settings.groq_model == "llama-3.3-70b-versatile"
    assert settings.profile_path == "profiles/default.json"


def test_reads_from_environment(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "news-123")
    monkeypatch.setenv("GROQ_API_KEY", "groq-456")
    monkeypatch.setenv("GROQ_MODEL", "custom-model")
    settings = Settings(_env_file=None)
    assert settings.newsapi_key == "news-123"
    assert settings.groq_api_key == "groq-456"
    assert settings.groq_model == "custom-model"


def test_get_settings_is_cached():
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()
