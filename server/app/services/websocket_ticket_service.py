import hashlib
import secrets
from uuid import UUID

from redis.asyncio import Redis


def ticket_key(ticket: str):
    return "breakscale:ws-ticket:" + hashlib.sha256(ticket.encode()).hexdigest()
async def create_ws_ticket(redis: Redis, user_id: UUID) -> str:
    ticket = secrets.token_urlsafe(32)
    await redis.set(ticket_key(ticket), str(user_id), ex=30, nx=True)
    return ticket
async def consume_ws_ticket(redis: Redis, ticket: str) -> UUID | None:
    if not isinstance(ticket, str) or not 16 <= len(ticket) <= 200:
        return None
    value = await redis.getdel(ticket_key(ticket))
    if not value:
        return None
    return UUID(value.decode() if isinstance(value, bytes) else value)
