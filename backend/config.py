"""Application configuration.

All secrets and tunables are loaded from the environment (and an optional
``.env`` file). Nothing sensitive is ever hardcoded here — see ``.env.example``
for the variables this expects.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, populated from environment variables / ``.env``."""

    newsapi_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    profile_path: str = "profiles/default.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
