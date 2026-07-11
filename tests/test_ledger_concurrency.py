import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import uuid4

from ulid import ULID

from aisdlc.ledger.store import LedgerStore


def _env(task_id: str, idx: int) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "tool.called",
        "actor": {"kind": "tool", "id": f"worker-{idx}"},
        "artifact_refs": [],
        "payload_schema": "tool-called/v0.1",
    }


def test_concurrent_appends_preserve_total_order(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    artifacts = tmp_data_dir / "artifacts"
    task_id = f"TASK-{uuid4().hex[:8]}"
    worker_count = 8
    events_per_worker = 5

    def append_one(i: int) -> None:
        store = LedgerStore(db_path, artifacts)
        payload = json.dumps({"worker": i}).encode("utf-8")
        store.append_event(task_id, _env(task_id, i), payload)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(append_one, i) for i in range(worker_count * events_per_worker)]
        for fut in as_completed(futures):
            fut.result()

    store = LedgerStore(db_path, artifacts)
    events = store.get_events(task_id)
    assert len(events) == worker_count * events_per_worker
    sequences = [e["sequence"] for e in events]
    assert sequences == list(range(1, len(events) + 1))
    assert len({e["event_hash"] for e in events}) == len(events)
