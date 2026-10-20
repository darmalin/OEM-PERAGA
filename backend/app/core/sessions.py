"""Server-side sessions in Redis. The cookie carries only a random session ID.

Redis keys use the SHA-256 of the session ID, so a Redis dump does not expose live cookies.
"""

import hmac
import secrets
import time
import uuid
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.crypto import sha256_hex
from app.core.redis import get_redis


@dataclass(frozen=True)
class SessionData:
    session_id: str
    user_id: uuid.UUID
    csrf_token: str
    created_at: float


def _key(session_id: str) -> str:
    return f"sess:{sha256_hex(session_id)}"


def _user_key(user_id: uuid.UUID) -> str:
    return f"user_sess:{user_id}"


async def create(user_id: uuid.UUID) -> SessionData:
    s = get_settings()
    redis = get_redis()
    session_id = secrets.token_urlsafe(32)
    data = SessionData(session_id, user_id, secrets.token_urlsafe(32), time.time())
    key = _key(session_id)
    await redis.hset(  # type: ignore[misc]
        key,
        mapping={
            "user_id": str(user_id),
            "csrf": data.csrf_token,
            "created_at": str(data.created_at),
        },
    )
    await redis.expire(key, s.session_idle_timeout_seconds)
    await redis.sadd(_user_key(user_id), key)  # type: ignore[misc]
    await redis.expire(_user_key(user_id), s.session_absolute_timeout_seconds)
    return data


async def load(session_id: str) -> SessionData | None:
    """Return the session and slide its idle timeout, or None if missing/expired."""
    s = get_settings()
    redis = get_redis()
    key = _key(session_id)
    raw: dict[str, str] = await redis.hgetall(key)  # type: ignore[misc]
    if not raw:
        return None
    created_at = float(raw["created_at"])
    if time.time() - created_at > s.session_absolute_timeout_seconds:
        await redis.delete(key)
        return None
    await redis.expire(key, s.session_idle_timeout_seconds)
    return SessionData(session_id, uuid.UUID(raw["user_id"]), raw["csrf"], created_at)


async def destroy(session_id: str) -> None:
    await get_redis().delete(_key(session_id))


async def destroy_all_for_user(user_id: uuid.UUID) -> None:
    """Invalidate every session of a user (deactivation, password change)."""
    redis = get_redis()
    keys: set[str] = await redis.smembers(_user_key(user_id))  # type: ignore[misc]
    if keys:
        await redis.delete(*keys)
    await redis.delete(_user_key(user_id))


def csrf_matches(session: SessionData, token: str | None) -> bool:
    return token is not None and hmac.compare_digest(session.csrf_token, token)
