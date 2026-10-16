from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    API_V1_PREFIX: str

    FRONTEND_URL: str

    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
