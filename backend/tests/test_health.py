# backend/tests/test_health.py
"""Liveness and readiness endpoints. Requires `docker compose up -d`."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.api.deps import get_redis


def test_live_reports_ok(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_ok_when_postgres_and_redis_are_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"]["postgres"]["status"] == "ok"
    assert body["components"]["postgres"]["detail"].startswith("pgvector ")
    assert body["components"]["redis"]["status"] == "ok"


def test_ready_returns_503_when_redis_is_unreachable(app: FastAPI, client: TestClient) -> None:
    # Nothing listens on port 1, so every connection attempt fails.
    unreachable = Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.5)
    app.dependency_overrides[get_redis] = lambda: unreachable

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["redis"]["status"] == "error"
    assert body["components"]["postgres"]["status"] == "ok"
