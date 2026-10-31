"""Application configuration.

All secrets and tunables are loaded from the environment (and an optional
``.env`` file). Nothing sensitive is ever hardcoded here — see ``.env.example``
for the variables this expects.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve ``.env`` next to this file so it is found regardless of the current
# working directory (the app is launched from the repo root).
BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Runtime settings, populated from environment variables / ``.env``."""

    newsapi_key: str = ""
    news_language: str = "en"
    news_country: str = ""  # ISO 3166-1 code for top headlines; empty = any
    llm_provider: Literal["groq", "azure"] = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = ""
    profile_path: str = "profiles/default.json"
    log_level: str = "INFO"
    # Relative paths resolve against the backend directory; empty disables it.
    log_file: str = "logs/solon.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    # Batch analysis limits; see ``backend.workflows.batch_workflow``.
    batch_max_tokens: int = 100_000
    batch_max_concurrency: int = 4
    # Articles with less text than this are scraped before analysis.
    min_content_chars: int = 600
    # SQLAlchemy async URL; empty means SQLite at backend/data/solon.db.
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite+aiosqlite:///{BACKEND_DIR / 'data' / 'solon.db'}"

    @property
    def log_file_path(self) -> Path | None:
        """``log_file`` resolved against the backend directory, or ``None``."""
        if not self.log_file:
            return None
        return BACKEND_DIR / self.log_file


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
