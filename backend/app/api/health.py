# backend/app/api/health.py
"""Liveness and readiness endpoints."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app import __version__
from app.api.deps import EngineDep, RedisDep
from app.db import ping_postgres
from app.redis_client import ping_redis

# A health check must answer quickly even when a dependency hangs.
PROBE_TIMEOUT_S = 1.0

router = APIRouter(prefix="/health", tags=["health"])

Probe = Callable[[], Awaitable[str]]


class ComponentHealth(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float
    detail: str


class LiveResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    components: dict[str, ComponentHealth]


async def run_probe(probe: Probe) -> ComponentHealth:
    """Run one dependency probe under a hard timeout. Never raises."""
    start = time.perf_counter()
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_S):
            detail = await probe()
    except Exception as exc:  # a failed probe is a result to report, not a crash
        return ComponentHealth(
            status="error", latency_ms=_elapsed_ms(start), detail=_describe(exc)
        )
    return ComponentHealth(status="ok", latency_ms=_elapsed_ms(start), detail=detail)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _describe(exc: Exception) -> str:
    message = str(exc)
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok", version=__version__)


@router.get("", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
async def ready(response: Response, engine: EngineDep, redis: RedisDep) -> ReadyResponse:
    postgres_health, redis_health = await asyncio.gather(
        run_probe(lambda: ping_postgres(engine)),
        run_probe(lambda: ping_redis(redis)),
    )
    components = {"postgres": postgres_health, "redis": redis_health}
    healthy = all(component.status == "ok" for component in components.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ok" if healthy else "degraded",
        version=__version__,
        components=components,
    )
