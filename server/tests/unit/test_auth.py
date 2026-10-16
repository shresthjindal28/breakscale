from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.main import app
from app.services.websocket_ticket_service import consume_ws_ticket, create_ws_ticket
from app.simulation.cancellation import CancellationToken, SimulationCancelled


def test_argon_password_hash():
    hashed = hash_password("long-password-for-testing")
    assert hashed.startswith("$argon2id$")
    assert verify_password("long-password-for-testing", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_and_invalid_signature():
    user_id = str(uuid4())
    assert decode_access_token(create_access_token(user_id))["sub"] == user_id
    invalid = jwt.encode({"sub":user_id}, "different-secret-with-32-characters", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(invalid)


def test_expired_token():
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub":str(uuid4()),"type":"access","jti":"id","iat":now-timedelta(hours=1),
        "exp":now-timedelta(seconds=1),"iss":"breakscale","aud":"breakscale-api"},get_settings().JWT_SECRET_KEY,algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


@pytest.mark.asyncio
async def test_missing_bearer_rejected():
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None,AsyncMock())
    assert exc.value.status_code == 401


def test_cookie_routes_reject_untrusted_origin():
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/refresh",headers={"Origin":"https://evil.example"}).status_code == 403
        assert client.post("/api/v1/auth/logout").status_code == 403


@pytest.mark.asyncio
async def test_websocket_ticket_is_consumed_once():
    redis = AsyncMock()
    user_id = uuid4()
    ticket = await create_ws_ticket(redis,user_id)
    redis.getdel.side_effect = [str(user_id).encode(),None]
    assert await consume_ws_ticket(redis,ticket) == user_id
    assert await consume_ws_ticket(redis,ticket) is None


def test_cooperative_cancellation():
    token = CancellationToken()
    token.check()
    token.cancel()
    with pytest.raises(SimulationCancelled):
        token.check()
