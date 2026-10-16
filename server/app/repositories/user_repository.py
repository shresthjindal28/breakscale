from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def by_email(self, email: str):
        return await self.db.scalar(select(User).where(User.email == email.strip().lower()))
