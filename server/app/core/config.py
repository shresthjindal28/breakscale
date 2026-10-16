from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

DEV_USER_ID: UUID = UUID("11111111-1111-4111-8111-111111111111")


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    API_V1_PREFIX: str

    FRONTEND_URL: str

    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None
    DEV_USER_ID: UUID = DEV_USER_ID
    JWT_SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, gt=0, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0, le=30)
    COOKIE_SECURE: bool = True
    ALLOWED_ORIGINS: list[str] = Field(default_factory=list)
    MAX_ACTIVE_SIMULATIONS: int = Field(default=2, ge=1, le=10)
    MAX_REQUESTS: int = Field(default=10_000, ge=1, le=100_000)
    MAX_WS_MESSAGE_BYTES: int = Field(default=262_144, ge=1024)

    @property
    def trusted_origins(self) -> list[str]:
        return self.ALLOWED_ORIGINS or [self.FRONTEND_URL.rstrip("/")]

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

