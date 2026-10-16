import hashlib
import time
from uuid import UUID

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


async def rate_limit(redis: Redis, identity: str, limit: int = 20):
    key = "breakscale:rate:" + hashlib.sha256(identity.encode()).hexdigest()
    try:
        count = await redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",1,key)
    except RedisError:
        raise HTTPException(503, "Authentication service unavailable") from None
    if count > limit:
        raise HTTPException(429, "Too many requests; try again shortly", headers={"Retry-After":"60"})

async def acquire_slot(redis: Redis, user_id: UUID, run_id: str):
    now = time.time()
    key = f"breakscale:slots:{user_id}"
    script = """redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',ARGV[1]);
    if redis.call('ZCARD',KEYS[1]) >= tonumber(ARGV[3]) then return 0 end;
    redis.call('ZADD',KEYS[1],ARGV[2],ARGV[4]); redis.call('EXPIRE',KEYS[1],960); return 1"""
    if not await redis.eval(script,1,key,now,now+900,get_settings().MAX_ACTIVE_SIMULATIONS,run_id):
        raise HTTPException(429, "Concurrent simulation limit reached")

async def release_slot(redis: Redis, user_id: UUID, run_id: str):
    await redis.zrem(f"breakscale:slots:{user_id}",run_id)
