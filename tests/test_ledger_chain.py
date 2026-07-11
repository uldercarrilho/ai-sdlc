from datetime import datetime, timezone
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.errors import ChainIntegrityError
from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH
from aisdlc.ledger.store import LedgerStore


def _env(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "gate.completed",
        "actor": {"kind": "tool", "id": "verification-service"},
        "artifact_refs": [],
        "payload_schema": "gate-completed/v0.1",
    }


def test_get_events_verifies_chain(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    store.append_event(task_id, _env(task_id), b'{"exit_code": 0}')
    store.append_event(task_id, _env(task_id), b'{"exit_code": 0}')
    events = store.get_events(task_id)
    assert len(events) == 2
    assert events[0]["previous_event_hash"] == GENESIS_PREVIOUS_HASH
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]


def test_corrupted_envelope_detected_on_read(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    store.append_event(task_id, _env(task_id), b"{}")
    conn = store._conn()  # noqa: SLF001
    conn.execute(
        "UPDATE events SET envelope_json = json_set(envelope_json, '$.event_type', 'tampered') WHERE task_id = ?",
        (task_id,),
    )
    conn.commit()
    conn.close()
    with pytest.raises(ChainIntegrityError):
        store.get_events(task_id)
