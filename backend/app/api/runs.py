# backend/app/api/runs.py
"""Start runs and stream their events to the browser over Server-Sent Events."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import anyio
from fastapi import APIRouter, Path, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

from app.api.deps import RedisDep, TasksDep
from app.events.fake_run import FakeRunConfig, run_fake
from app.events.publisher import RedisEventPublisher, channel_for, wait_for_subscriber
from app.events.schema import RunDone, parse_event
from app.events.sse import format_comment, format_sse

logger = logging.getLogger("recall.runs")

# Longest silence before a heartbeat. Proxies commonly drop connections idle for 30-60s.
HEARTBEAT_S = 15.0
# How long a fake run waits for its first viewer before starting anyway.
SUBSCRIBER_WAIT_S = 30.0

# A strict id format keeps Redis channel names predictable.
RunId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")]

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunResponse(BaseModel):
    run_id: str
    events_url: str


@router.post("/fake", status_code=status.HTTP_202_ACCEPTED, response_model=StartRunResponse)
async def start_fake_run(
    request: Request, redis: RedisDep, tasks: TasksDep, config: FakeRunConfig | None = None
) -> StartRunResponse:
    run_id = uuid.uuid4().hex
    tasks.spawn(_run_when_watched(redis, run_id, config or FakeRunConfig()), name=f"run:{run_id}")
    events_url = str(request.url_for("stream_run_events", run_id=run_id))
    return StartRunResponse(run_id=run_id, events_url=events_url)


@router.get("/{run_id}/events", name="stream_run_events")
async def stream_run_events(run_id: RunId, redis: RedisDep) -> StreamingResponse:
    return StreamingResponse(
        _relay(redis, run_id),
        media_type="text/event-stream",
        # no-cache: never serve a stored copy. X-Accel-Buffering: stop nginx from buffering it.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_when_watched(redis: Redis, run_id: str, config: FakeRunConfig) -> None:
    if not await wait_for_subscriber(redis, channel_for(run_id), SUBSCRIBER_WAIT_S):
        logger.warning(
            "run %s: no subscriber after %.0fs, starting anyway", run_id, SUBSCRIBER_WAIT_S
        )
    done = await run_fake(run_id, config, RedisEventPublisher(redis))
    logger.info(
        "run %s done: %d indexed, %d failed in %.0f ms",
        run_id,
        done.indexed,
        done.failed,
        done.duration_ms,
    )


async def _relay(redis: Redis, run_id: str) -> AsyncIterator[str]:
    """Subscribe to the run's channel and forward each valid event as one SSE message."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_for(run_id))
    try:
        # Send headers and a first byte now, so the client sees the stream open immediately.
        yield format_comment("subscribed")
        while True:
            message = await pubsub.get_message(timeout=HEARTBEAT_S)
            if message is None:  # nothing arrived within HEARTBEAT_S
                yield format_comment("heartbeat")
                continue
            if message["type"] != "message":  # e.g. Redis confirming our subscribe
                continue
            try:
                event = parse_event(message["data"])
            except ValidationError:
                # One bad publisher must not kill every viewer's stream.
                logger.warning("run %s: dropped invalid event %r", run_id, message["data"])
                continue
            yield format_sse(event.model_dump_json())
            if isinstance(event, RunDone):
                return
    finally:
        # Runs on normal end and on client disconnect (cancellation). The shield lets these
        # awaits finish even while cancelled, so the Redis connection is always released.
        with anyio.CancelScope(shield=True):
            await pubsub.unsubscribe()
            await pubsub.aclose()
