# backend/tests/test_event_schema.py
"""Contract tests: the event shape the UI depends on. A failure here means the UI would break."""

import json

import pytest
from pydantic import ValidationError

from app.events.schema import (
    Event,
    ItemState,
    ItemStateChanged,
    RunDone,
    RunStarted,
    is_valid_transition,
    parse_event,
)


def test_item_state_event_has_the_documented_shape() -> None:
    event = ItemStateChanged(
        run_id="run-1", item_id="item-1", state=ItemState.EMBEDDING, ts=1727500000.123
    )

    assert json.loads(event.model_dump_json()) == {
        "type": "item.state",
        "run_id": "run-1",
        "item_id": "item-1",
        "state": "embedding",
        "ts": 1727500000.123,
        "meta": {},
    }


def test_item_states_match_the_documented_contract() -> None:
    # frontend/lib/events.ts mirrors this list; change both together.
    assert [state.value for state in ItemState] == [
        "queued",
        "parsing",
        "chunking",
        "embedding",
        "indexed",
        "failed",
    ]


@pytest.mark.parametrize(
    "event",
    [
        RunStarted(run_id="run-1", total_items=2000),
        ItemStateChanged(run_id="run-1", item_id="item-1", state=ItemState.QUEUED),
        ItemStateChanged(
            run_id="run-1", item_id="item-1", state=ItemState.FAILED, meta={"error": "boom"}
        ),
        RunDone(run_id="run-1", indexed=1990, failed=10, duration_ms=14250.5),
    ],
)
def test_every_event_survives_a_json_round_trip(event: Event) -> None:
    assert parse_event(event.model_dump_json()) == event


def test_parse_picks_the_model_from_the_type_field() -> None:
    raw = '{"type": "run.started", "run_id": "run-1", "ts": 1.0, "total_items": 5}'

    assert isinstance(parse_event(raw), RunStarted)


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_event('{"type": "item.teleported", "run_id": "run-1", "ts": 1.0}')


def test_unknown_item_state_is_rejected() -> None:
    raw = '{"type": "item.state", "run_id": "r", "item_id": "i", "state": "dancing", "ts": 1.0}'
    with pytest.raises(ValidationError):
        parse_event(raw)


def test_unexpected_fields_are_rejected() -> None:
    raw = '{"type": "item.state", "run_id": "r", "item_id": "i", "state": "queued", "stat": "x"}'
    with pytest.raises(ValidationError):
        parse_event(raw)


def test_timestamp_defaults_to_now() -> None:
    event = RunStarted(run_id="run-1", total_items=1)

    assert event.ts > 1_700_000_000


def test_events_are_immutable() -> None:
    event = ItemStateChanged(run_id="run-1", item_id="item-1", state=ItemState.QUEUED)

    with pytest.raises(ValidationError):
        event.state = ItemState.INDEXED  # type: ignore[misc]


@pytest.mark.parametrize(
    ("previous", "new"),
    [
        (None, ItemState.QUEUED),
        (ItemState.QUEUED, ItemState.PARSING),
        (ItemState.PARSING, ItemState.CHUNKING),
        (ItemState.CHUNKING, ItemState.EMBEDDING),
        (ItemState.EMBEDDING, ItemState.INDEXED),
        (ItemState.QUEUED, ItemState.FAILED),
        (ItemState.EMBEDDING, ItemState.FAILED),
    ],
)
def test_legal_transitions(previous: ItemState | None, new: ItemState) -> None:
    assert is_valid_transition(previous, new)


@pytest.mark.parametrize(
    ("previous", "new"),
    [
        (None, ItemState.PARSING),  # every item must be queued first
        (ItemState.QUEUED, ItemState.EMBEDDING),  # skipping a stage
        (ItemState.EMBEDDING, ItemState.PARSING),  # going backwards
        (ItemState.INDEXED, ItemState.FAILED),  # terminal states are final
        (ItemState.FAILED, ItemState.QUEUED),
    ],
)
def test_illegal_transitions(previous: ItemState | None, new: ItemState) -> None:
    assert not is_valid_transition(previous, new)
