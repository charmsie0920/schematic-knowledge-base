# backend/app/db.py
"""Async SQLAlchemy engine factory and a Postgres readiness probe."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Create the connection pool. No connection is opened until first use."""
    return create_async_engine(
        str(settings.database_url),
        pool_size=5,
        max_overflow=10,
        # Validate a pooled connection before handing it out, so a Postgres
        # restart does not surface as a failed request.
        pool_pre_ping=True,
    )


async def ping_postgres(engine: AsyncEngine) -> str:
    """Round-trip the database and confirm pgvector is installed."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        version = result.scalar_one_or_none()
    if version is None:
        raise RuntimeError("pgvector extension is not installed")
    return f"pgvector {version}"
