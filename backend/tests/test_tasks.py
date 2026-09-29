# backend/tests/test_tasks.py
"""TaskRegistry: tracks background tasks and cancels them on shutdown."""

import asyncio

from app.tasks import TaskRegistry


def test_finished_tasks_are_forgotten() -> None:
    async def scenario() -> int:
        registry = TaskRegistry()
        task = registry.spawn(asyncio.sleep(0), name="quick")
        await task
        await asyncio.sleep(0)  # done-callbacks run on the next loop iteration
        return len(registry)

    assert asyncio.run(scenario()) == 0


def test_cancel_all_stops_running_tasks() -> None:
    async def scenario() -> bool:
        registry = TaskRegistry()
        task = registry.spawn(asyncio.sleep(60), name="slow")
        await registry.cancel_all()
        return task.cancelled()

    assert asyncio.run(scenario())
