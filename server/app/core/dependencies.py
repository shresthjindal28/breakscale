from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)
async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                           db: AsyncSession = Depends(get_db)) -> User:
    error = HTTPException(401, "Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise error
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise error from None
    user = await db.get(User, user_id)
    if user is None:
        raise error
    return user

async def get_owner_id(user: User = Depends(get_current_user)) -> UUID:
    return user.id
