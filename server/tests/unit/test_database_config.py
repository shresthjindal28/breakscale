import pytest

from app.core.config import Settings


def settings(url):
    return Settings(
        _env_file=None, JWT_SECRET_KEY="test-secret-key-with-at-least-32-characters", APP_NAME="test", APP_VERSION="1", DEBUG=False,
        API_V1_PREFIX="/api/v1", FRONTEND_URL="http://localhost:3000",
        DATABASE_URL=url,
    )


@pytest.mark.parametrize("url", [None, "postgresql://USER:PASSWORD@host/db", "invalid", "sqlite:///test.db"])
def test_rejects_missing_placeholder_or_invalid_database_url(url):
    with pytest.raises(ValueError):
        settings(url).database_url


def test_provider_url_normalizes_driver_and_ssl_preserving_password():
    url = settings(
        "postgresql://db_owner:secret%40pass%25@host/db?sslmode=require&channel_binding=require"
    ).database_url
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "secret@pass%"
    assert dict(url.query) == {"ssl": "require"}


def test_asyncpg_url_preserves_explicit_ssl():
    url = settings("postgresql+asyncpg://db_owner:secret@localhost/db?ssl=disable").database_url
    assert url.query["ssl"] == "disable"
