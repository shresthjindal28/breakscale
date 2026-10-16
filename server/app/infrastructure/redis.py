from redis.asyncio import Redis

from app.core.config import get_settings


async def get_redis():
    url = get_settings().REDIS_URL
    if not url:
        raise RuntimeError("REDIS_URL is required")
    client = Redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
    try:
        yield client
    finally:
        await client.aclose()
