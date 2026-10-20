from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return client


def new_redis() -> Redis:
    """Fresh client for worker tasks, which each run in their own event loop."""
    client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return client
