# backend/app/events/schema.py
"""The event contract: every state change the UI can see.

Mirrored by frontend/lib/events.ts and documented in CLAUDE.md. Change all three together.
"""

import time
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ItemState(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


# The happy path, in order. Any state before INDEXED may also move to FAILED.
PIPELINE_ORDER: tuple[ItemState, ...] = (
    ItemState.QUEUED,
    ItemState.PARSING,
    ItemState.CHUNKING,
    ItemState.EMBEDDING,
    ItemState.INDEXED,
)
TERMINAL_STATES = frozenset({ItemState.INDEXED, ItemState.FAILED})


def is_valid_transition(previous: ItemState | None, new: ItemState) -> bool:
    """Whether an item may move from `previous` (None = never seen) to `new`."""
    if previous is None:
        return new is ItemState.QUEUED
    if previous in TERMINAL_STATES:
        return False
    if new is ItemState.FAILED:
        return True
    return PIPELINE_ORDER.index(new) == PIPELINE_ORDER.index(previous) + 1


class _EventBase(BaseModel):
    # Frozen: an event is a fact about the past. Forbid extras: a typo is an error, not data.
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str
    run_id: str = Field(min_length=1, max_length=64)
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunStarted(_EventBase):
    type: Literal["run.started"] = "run.started"
    total_items: int = Field(ge=0)


class ItemStateChanged(_EventBase):
    type: Literal["item.state"] = "item.state"
    item_id: str = Field(min_length=1)
    state: ItemState


class RunDone(_EventBase):
    type: Literal["run.done"] = "run.done"
    indexed: int = Field(ge=0)
    failed: int = Field(ge=0)
    duration_ms: float = Field(ge=0)


# Pydantic reads `type` first, then validates against exactly one model.
Event = Annotated[RunStarted | ItemStateChanged | RunDone, Field(discriminator="type")]

_event_adapter: TypeAdapter[Event] = TypeAdapter(Event)


def parse_event(raw: str | bytes) -> Event:
    """Validate one JSON-encoded event. Raises ValidationError if it breaks the contract."""
    return _event_adapter.validate_json(raw)
