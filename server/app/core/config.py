from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    API_V1_PREFIX: str

    FRONTEND_URL: str

    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None

    @property
    def database_url(self) -> URL:
        """Return the validated async PostgreSQL URL without exposing secrets."""
        if not self.DATABASE_URL:
            raise ValueError("Set DATABASE_URL in server/.env before using the database.")
        try:
            url = make_url(self.DATABASE_URL)
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL.") from None
        if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError("DATABASE_URL must use PostgreSQL (postgresql+asyncpg://).")
        placeholders = {"user", "username", "password", "your_password", "your_username"}
        if any(value and value.lower() in placeholders for value in (url.username, url.password)):
            raise ValueError(
                "DATABASE_URL contains placeholder credentials. Replace them with the actual "
                "database credentials in server/.env (Neon: copy the connection string from Connect)."
            )
        if not url.host or not url.database or not url.username:
            raise ValueError("DATABASE_URL must include a username, host, and database name.")
        query = dict(url.query)
        # Provider URLs commonly use libpq's sslmode; asyncpg accepts ssl instead.
        if "sslmode" in query:
            query.setdefault("ssl", query.pop("sslmode"))
        # libpq-only option included in Neon connection strings.
        query.pop("channel_binding", None)
        return url.set(drivername="postgresql+asyncpg", query=query)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
