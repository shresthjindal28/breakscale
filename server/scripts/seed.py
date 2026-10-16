import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import AsyncSessionLocal, engine


async def main():
    settings = get_settings()

    if not settings.DEBUG:
        raise RuntimeError("Development seed is disabled outside DEBUG mode")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == settings.DEV_USER_ID)
        )

        if result.scalar_one_or_none() is None:
            session.add(
                User(
                    id=settings.DEV_USER_ID,
                    email="dev@breakscale.local",
                    password_hash="!development-account-login-disabled",
                )
            )
            await session.commit()
            print("Development user created")
        else:
            print("Development user already exists")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())