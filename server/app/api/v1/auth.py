from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.infrastructure.limits import rate_limit
from app.infrastructure.redis import get_redis
from app.schemas.auth import AccessTokenResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.token_service import issue_refresh_token, revoke_refresh_token, rotate_refresh_token
from app.services.websocket_ticket_service import create_ws_ticket

router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE_NAME = "breakscale_refresh"
def trusted_origin(request: Request):
    if request.headers.get("origin") not in get_settings().trusted_origins:
        raise HTTPException(403, "Untrusted request origin")
def cookie_path():
    return get_settings().API_V1_PREFIX + "/auth"
def set_refresh_cookie(response: Response, token: str):
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS*86400,
        httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE, path=cookie_path())

@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(trusted_origin)])
async def register(data: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    await rate_limit(redis, "register:" + (request.client.host if request.client else "unknown"), 10)
    return await AuthService(db).register(data)

@router.post("/login", response_model=AccessTokenResponse, dependencies=[Depends(trusted_origin)])
async def login(data: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    await rate_limit(redis, "login:" + (request.client.host if request.client else "unknown"), 30)
    user = await AuthService(db).login(data)
    token = await issue_refresh_token(db, user.id)
    await db.commit()
    set_refresh_cookie(response, token)
    return AccessTokenResponse(access_token=create_access_token(str(user.id)))

@router.post("/refresh", response_model=AccessTokenResponse, dependencies=[Depends(trusted_origin)])
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    await rate_limit(redis, "refresh:" + (request.client.host if request.client else "unknown"), 60)
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "Refresh session required")
    token, user_id = await rotate_refresh_token(db, raw)
    set_refresh_cookie(response, token)
    return AccessTokenResponse(access_token=create_access_token(str(user_id)))

@router.post("/logout", status_code=204, dependencies=[Depends(trusted_origin)])
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        await revoke_refresh_token(db, raw)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path=cookie_path(), secure=get_settings().COOKIE_SECURE, httponly=True, samesite=get_settings().COOKIE_SAMESITE)
    return response

@router.post("/ws-ticket")
async def ws_ticket(user: User = Depends(get_current_user), redis: Redis = Depends(get_redis)):
    await rate_limit(redis,"ws-ticket:"+str(user.id),30)
    return {"ticket": await create_ws_ticket(redis,user.id)}
