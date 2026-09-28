# backend/app/redis_client.py
"""Async Redis client factory and a Redis readiness probe."""

from redis.asyncio import Redis

from app.config import Settings


def build_redis(settings: Settings) -> Redis:
    """Create the client. Connections are opened lazily from an internal pool."""
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


async def ping_redis(redis: Redis) -> str:
    """Round-trip Redis and report the server version."""
    await redis.ping()
    info = await redis.info("server")
    return f"redis {info['redis_version']}"
