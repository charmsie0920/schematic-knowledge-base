# backend/tests/test_fake_run.py
"""The fake run generator, against an in-memory sink. No Redis needed."""

import asyncio
from collections.abc import Sequence

from app.events.fake_run import FakeRunConfig, run_fake
from app.events.schema import (
    TERMINAL_STATES,
    Event,
    ItemState,
    ItemStateChanged,
    RunDone,
    RunStarted,
    is_valid_transition,
)


class MemorySink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)

    async def publish_many(self, events: Sequence[Event]) -> None:
        self.events.extend(events)


def run(**overrides: object) -> list[Event]:
    # speed=1000 turns ~0.5s per item into ~0.5ms, so tests stay fast.
    config = FakeRunConfig.model_validate({"speed": 1000, "seed": 1, **overrides})
    sink = MemorySink()
    asyncio.run(run_fake("test-run", config, sink))
    return sink.events


def final_states(events: list[Event]) -> dict[str, ItemState]:
    return {e.item_id: e.state for e in events if isinstance(e, ItemStateChanged)}


def test_every_item_follows_a_legal_path_to_a_terminal_state() -> None:
    events = run(total_items=200, concurrency=16, failure_rate=0.2)

    last: dict[str, ItemState] = {}
    for event in events:
        if isinstance(event, ItemStateChanged):
            previous = last.get(event.item_id)
            assert is_valid_transition(previous, event.state), f"{previous} -> {event}"
            last[event.item_id] = event.state

    assert len(last) == 200
    assert set(last.values()) <= TERMINAL_STATES


def test_run_is_bracketed_by_started_and_done() -> None:
    events = run(total_items=50)

    assert isinstance(events[0], RunStarted)
    assert events[0].total_items == 50
    assert isinstance(events[-1], RunDone)
    assert sum(isinstance(e, RunStarted | RunDone) for e in events) == 2


def test_done_counts_match_item_outcomes() -> None:
    events = run(total_items=300, failure_rate=0.3)

    done = events[-1]
    outcomes = list(final_states(events).values())
    assert isinstance(done, RunDone)
    assert done.indexed == outcomes.count(ItemState.INDEXED)
    assert done.failed == outcomes.count(ItemState.FAILED)
    assert done.indexed + done.failed == 300


def test_failure_rate_bounds() -> None:
    assert set(final_states(run(total_items=40, failure_rate=0.0)).values()) == {ItemState.INDEXED}
    assert set(final_states(run(total_items=40, failure_rate=1.0)).values()) == {ItemState.FAILED}


def test_failed_items_carry_an_error_message() -> None:
    events = run(total_items=20, failure_rate=1.0)

    failures = [e for e in events if isinstance(e, ItemStateChanged) and e.state == "failed"]
    assert len(failures) == 20
    assert all(e.meta["error"].startswith("simulated failure") for e in failures)


def test_same_seed_gives_same_outcomes() -> None:
    first = final_states(run(total_items=200, failure_rate=0.25, seed=42))
    second = final_states(run(total_items=200, failure_rate=0.25, seed=42))

    assert first == second
