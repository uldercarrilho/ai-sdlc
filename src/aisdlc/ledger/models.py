from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskChainHead:
    task_id: str
    latest_sequence: int
    latest_event_hash: str


@dataclass(frozen=True)
class StoredEvent:
    event_id: str
    task_id: str
    sequence: int
    event_hash: str
    envelope_json: str
