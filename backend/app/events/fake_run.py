# backend/app/events/fake_run.py
"""A fake ingestion run: walks N items through the pipeline states with random timing.

Stands in for the Phase 2 workers. It only publishes events, exactly as a real worker will,
so the UI cannot tell the difference.
"""

import asyncio
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.events.schema import Event, ItemState, ItemStateChanged, RunDone, RunStarted

# The stages a worker spends time in, in order.
WORK_STAGES: tuple[ItemState, ...] = (ItemState.PARSING, ItemState.CHUNKING, ItemState.EMBEDDING)

# (min, max) seconds per stage at speed 1.0. Embedding is the slow one, as it will be for real.
STAGE_SECONDS: dict[ItemState, tuple[float, float]] = {
    ItemState.PARSING: (0.05, 0.25),
    ItemState.CHUNKING: (0.02, 0.10),
    ItemState.EMBEDDING: (0.15, 0.60),
}


class FakeRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int = Field(default=2000, ge=1, le=10_000)
    concurrency: int = Field(default=64, ge=1, le=512)
    failure_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    # Divides every stage duration: 2.0 runs twice as fast. Tests use a large value.
    speed: float = Field(default=1.0, gt=0.0, le=1000.0)
    seed: int | None = None


class EventSink(Protocol):
    """Where events go: Redis in the app, a list in tests."""

    async def publish(self, event: Event) -> None: ...

    async def publish_many(self, events: Sequence[Event]) -> None: ...


@dataclass(frozen=True)
class ItemPlan:
    item_id: str
    stage_seconds: tuple[float, ...]
    fail_at: ItemState | None


def plan_items(config: FakeRunConfig) -> list[ItemPlan]:
    """Roll every random choice up front, so a seed fixes the outcome regardless of scheduling."""
    rng = random.Random(config.seed)
    plans = []
    for index in range(config.total_items):
        seconds = tuple(rng.uniform(*STAGE_SECONDS[stage]) / config.speed for stage in WORK_STAGES)
        fail_at = rng.choice(WORK_STAGES) if rng.random() < config.failure_rate else None
        plans.append(ItemPlan(f"item-{index:05d}", seconds, fail_at))
    return plans


async def run_fake(run_id: str, config: FakeRunConfig, sink: EventSink) -> RunDone:
    started = time.perf_counter()
    plans = plan_items(config)

    await sink.publish(RunStarted(run_id=run_id, total_items=len(plans)))
    await sink.publish_many(
        [ItemStateChanged(run_id=run_id, item_id=p.item_id, state=ItemState.QUEUED) for p in plans]
    )

    queue: asyncio.Queue[ItemPlan] = asyncio.Queue()
    for plan in plans:
        queue.put_nowait(plan)
    outcomes: list[ItemState] = []

    async def worker() -> None:
        while not queue.empty():
            outcomes.append(await _process_item(run_id, queue.get_nowait(), sink))

    async with asyncio.TaskGroup() as group:
        for _ in range(min(config.concurrency, len(plans))):
            group.create_task(worker())

    done = RunDone(
        run_id=run_id,
        indexed=outcomes.count(ItemState.INDEXED),
        failed=outcomes.count(ItemState.FAILED),
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    await sink.publish(done)
    return done


async def _process_item(run_id: str, plan: ItemPlan, sink: EventSink) -> ItemState:
    for stage, seconds in zip(WORK_STAGES, plan.stage_seconds, strict=True):
        await sink.publish(ItemStateChanged(run_id=run_id, item_id=plan.item_id, state=stage))
        await asyncio.sleep(seconds)
        if stage is plan.fail_at:
            await sink.publish(
                ItemStateChanged(
                    run_id=run_id,
                    item_id=plan.item_id,
                    state=ItemState.FAILED,
                    meta={"error": f"simulated failure while {stage}"},
                )
            )
            return ItemState.FAILED
    await sink.publish(
        ItemStateChanged(run_id=run_id, item_id=plan.item_id, state=ItemState.INDEXED)
    )
    return ItemState.INDEXED
