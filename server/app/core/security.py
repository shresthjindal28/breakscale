from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False

def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "type": "access", "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid4()), "iss": "breakscale", "aud": "breakscale-api"},
        settings.JWT_SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, get_settings().JWT_SECRET_KEY, algorithms=[ALGORITHM],
        issuer="breakscale", audience="breakscale-api",
        options={"require": ["sub", "type", "iat", "exp", "jti", "iss", "aud"]})
    if payload["type"] != "access":
        raise jwt.InvalidTokenError("Wrong token type")
    return payload
