import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH, compute_event_hash
from aisdlc.ledger.store import LedgerStore


def _envelope(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "contract.drafted",
        "actor": {"kind": "human", "id": "owner"},
        "artifact_refs": [],
        "payload_schema": "contract-drafted/v0.1",
    }


def test_append_event_assigns_sequence_and_hash(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    payload1 = json.dumps({"n": 1}).encode("utf-8")
    payload2 = json.dumps({"n": 2}).encode("utf-8")

    first = store.append_event(task_id, _envelope(task_id), payload1)
    assert first["sequence"] == 1
    assert first["previous_event_hash"] == GENESIS_PREVIOUS_HASH
    assert first["event_hash"] == compute_event_hash(first)

    second = store.append_event(task_id, _envelope(task_id), payload2)
    assert second["sequence"] == 2
    assert second["previous_event_hash"] == first["event_hash"]
