from app.core.errors import RateLimited
from app.core.redis import get_redis


async def hit(key: str, limit: int, window_seconds: int) -> int:
    """Count one hit in a fixed window; raise RateLimited once over the limit."""
    redis = get_redis()
    full_key = f"rl:{key}"
    count = int(await redis.incr(full_key))
    if count == 1:
        await redis.expire(full_key, window_seconds)
    if count > limit:
        raise RateLimited()
    return count


async def count(key: str) -> int:
    value = await get_redis().get(f"rl:{key}")
    return int(value or 0)


async def reset(key: str) -> None:
    await get_redis().delete(f"rl:{key}")
