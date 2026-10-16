import asyncio

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest

# Equal-cost password verification for nonexistent accounts.
DUMMY_HASH = hash_password("non-account-password-for-timing")
class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
    async def register(self, data: RegisterRequest):
        name = data.name.strip()
        if not name:
            raise HTTPException(422, "Name cannot be blank")
        user = User(email=str(data.email).lower(), name=name,
                    password_hash=await asyncio.to_thread(hash_password, data.password))
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(409, "Email is already registered") from None
        await self.db.refresh(user)
        return user
    async def login(self, data: LoginRequest):
        user = await self.repo.by_email(str(data.email))
        valid = await asyncio.to_thread(verify_password, data.password, user.password_hash if user else DUMMY_HASH)
        if user is None or not valid:
            raise HTTPException(401, "Invalid email or password")
        return user
