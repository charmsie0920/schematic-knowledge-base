# backend/tests/conftest.py
"""Shared fixtures: a fresh app per test, driven through its real lifespan."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Entering the context runs the lifespan: clients are built, then closed on exit.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
