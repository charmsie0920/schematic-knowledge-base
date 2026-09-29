# backend/app/api/deps.py
"""FastAPI dependencies: shared resources owned by the app lifespan."""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.tasks import TaskRegistry


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    return engine


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


def get_tasks(request: Request) -> TaskRegistry:
    tasks: TaskRegistry = request.app.state.tasks
    return tasks


EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
RedisDep = Annotated[Redis, Depends(get_redis)]
TasksDep = Annotated[TaskRegistry, Depends(get_tasks)]
