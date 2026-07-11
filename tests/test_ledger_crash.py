import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.ledger.db import connect
from aisdlc.ledger.store import LedgerStore


class CrashLedgerStore(LedgerStore):
    def __init__(self, db_path, artifact_root, crash_after_insert: bool = False):
        super().__init__(db_path, artifact_root)
        self.crash_after_insert = crash_after_insert

    def append_event(self, task_id, envelope, payload):
        payload_ref = self._artifacts.put(payload)
        envelope = dict(envelope)
        envelope["task_id"] = task_id
        envelope["payload_ref"] = payload_ref
        conn = connect(self._db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO tasks(task_id) VALUES (?)", (task_id,))
            head = conn.execute(
                "SELECT latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            sequence = 1 if head is None else int(head["latest_sequence"]) + 1
            previous_hash = (
                "sha256:" + "0" * 64 if head is None else head["latest_event_hash"]
            )
            envelope["sequence"] = sequence
            envelope["previous_event_hash"] = previous_hash
            from aisdlc.ledger.chain import compute_event_hash
            from aisdlc.validation.event import validate_event_envelope

            validate_event_envelope(envelope)
            envelope["event_hash"] = compute_event_hash(envelope)
            conn.execute(
                """
                INSERT INTO events(
                  event_id, task_id, sequence, occurred_at, event_type,
                  event_hash, previous_event_hash, payload_ref, envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope["event_id"],
                    task_id,
                    sequence,
                    envelope["occurred_at"],
                    envelope["event_type"],
                    envelope["event_hash"],
                    previous_hash,
                    payload_ref,
                    json.dumps(envelope),
                ),
            )
            if self.crash_after_insert:
                raise RuntimeError("simulated crash before commit")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return envelope


def _env(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "tool.called",
        "actor": {"kind": "tool", "id": "shell"},
        "artifact_refs": [],
        "payload_schema": "tool-called/v0.1",
    }


def test_crash_before_commit_leaves_no_partial_chain_head(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    artifacts = tmp_data_dir / "artifacts"
    task_id = f"TASK-{uuid4().hex[:8]}"
    store = CrashLedgerStore(db_path, artifacts, crash_after_insert=True)
    with pytest.raises(RuntimeError):
        store.append_event(task_id, _env(task_id), b"{}")
    recovery = LedgerStore(db_path, artifacts)
    assert recovery.get_chain_head(task_id) is None
    assert recovery.get_events(task_id) == []
