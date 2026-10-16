"""Check database connectivity without printing connection credentials."""

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def check() -> None:
    engine = create_async_engine(get_settings().database_url, connect_args={"timeout": 10})
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        print("Database connection successful.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(check())
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except (SQLAlchemyError, OSError, TimeoutError):
        raise SystemExit(
            "Database connection failed. Check DATABASE_URL credentials, host, "
            "database name, SSL options, and network access."
        ) from None
