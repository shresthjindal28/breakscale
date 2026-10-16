import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.refresh_token import RefreshToken


def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

async def issue_refresh_token(db: AsyncSession, user_id: UUID, family_id: UUID | None = None) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user_id, family_id=family_id or uuid4(), token_hash=token_digest(raw),
        expires_at=datetime.now(timezone.utc)+timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)))
    await db.flush()
    return raw

async def locked_token(db: AsyncSession, raw: str):
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_digest(raw)))
    if token is None:
        return None
    # Serialize rotation/revocation for a session family across API replicas.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:family, 0))"), {"family": str(token.family_id)})
    return await db.scalar(select(RefreshToken).where(RefreshToken.id == token.id)
        .with_for_update().execution_options(populate_existing=True))

async def rotate_refresh_token(db: AsyncSession, raw: str) -> tuple[str, UUID]:
    token = await locked_token(db, raw)
    now = datetime.now(timezone.utc)
    if token is None:
        raise HTTPException(401, "Invalid refresh session")
    if token.revoked_at is not None:
        await db.execute(update(RefreshToken).where(RefreshToken.family_id == token.family_id).values(revoked_at=now))
        await db.commit()
        raise HTTPException(401, "Refresh token reused; session revoked")
    if token.expires_at <= now:
        raise HTTPException(401, "Refresh session expired")
    token.revoked_at = now
    raw_new = await issue_refresh_token(db, token.user_id, token.family_id)
    await db.commit()
    return raw_new, token.user_id

async def revoke_refresh_token(db: AsyncSession, raw: str):
    token = await locked_token(db, raw)
    if token is not None:
        await db.execute(update(RefreshToken).where(RefreshToken.family_id == token.family_id)
            .values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()
