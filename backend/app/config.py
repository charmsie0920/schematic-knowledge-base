# backend/app/config.py
"""Typed application settings, loaded from the repo-root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the repository root, where .env lives.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        # .env also holds values for Docker (POSTGRES_USER, ...) that the app ignores.
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: PostgresDsn
    redis_url: RedisDsn

    # Comma-separated in .env; use cors_origin_list in code.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
