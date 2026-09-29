# backend/app/events/publisher.py
"""Publish events to Redis pub/sub, one channel per run."""

import asyncio
import time
from collections.abc import Sequence

from redis.asyncio import Redis

from app.events.schema import Event


def channel_for(run_id: str) -> str:
    return f"events:{run_id}"


class RedisEventPublisher:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event: Event) -> None:
        await self._redis.publish(channel_for(event.run_id), event.model_dump_json())

    async def publish_many(self, events: Sequence[Event]) -> None:
        """Publish a burst in one network round trip instead of one per event."""
        async with self._redis.pipeline(transaction=False) as pipe:
            for event in events:
                pipe.publish(channel_for(event.run_id), event.model_dump_json())
            await pipe.execute()


async def wait_for_subscriber(
    redis: Redis, channel: str, timeout_s: float, poll_s: float = 0.05
) -> bool:
    """Wait until someone listens on `channel`. Pub/sub drops messages nobody is subscribed to."""
    deadline = time.monotonic() + timeout_s
    while True:
        [(_, subscribers)] = await redis.pubsub_numsub(channel)
        if subscribers > 0:
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(poll_s)
