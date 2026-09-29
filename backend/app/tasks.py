# backend/app/tasks.py
"""Owns fire-and-forget asyncio tasks so they are neither garbage-collected nor leaked."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger("recall.tasks")


class TaskRegistry:
    def __init__(self) -> None:
        # The event loop keeps only a weak reference to a task; this set is the strong one.
        self._tasks: set[asyncio.Task[Any]] = set()

    def __len__(self) -> int:
        return len(self._tasks)

    def spawn(self, coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            # Nobody awaits these tasks, so without this the error would vanish silently.
            logger.error("background task %s failed", task.get_name(), exc_info=exc)

    async def cancel_all(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
