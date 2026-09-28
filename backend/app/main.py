# backend/app/main.py
"""FastAPI application factory and lifespan."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.config import Settings, get_settings
from app.db import build_engine
from app.redis_client import build_redis

logger = logging.getLogger("recall")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = build_engine(settings)
        app.state.redis = build_redis(settings)
        logger.info("startup complete (env=%s)", settings.app_env)
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await app.state.engine.dispose()
            logger.info("shutdown complete")

    app = FastAPI(title="Recall API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
