from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aisdlc.artifacts.store import ArtifactStore
from aisdlc.errors import ValidationError
from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH, compute_event_hash, verify_task_chain
from aisdlc.ledger.db import connect, init_schema
from aisdlc.ledger.models import TaskChainHead
from aisdlc.validation.event import validate_event_envelope


class LedgerStore:
    def __init__(self, db_path: Path, artifact_root: Path) -> None:
        self._db_path = db_path
        self._artifacts = ArtifactStore(artifact_root)
        conn = connect(db_path)
        init_schema(conn)
        conn.close()

    def _conn(self):
        return connect(self._db_path)

    def get_chain_head(self, task_id: str) -> TaskChainHead | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT task_id, latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return TaskChainHead(row["task_id"], row["latest_sequence"], row["latest_event_hash"])

    def append_event(self, task_id: str, envelope: dict[str, Any], payload: bytes) -> dict[str, Any]:
        payload_ref = self._artifacts.put(payload)
        envelope = dict(envelope)
        envelope["task_id"] = task_id
        envelope["payload_ref"] = payload_ref

        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO tasks(task_id) VALUES (?)", (task_id,))
            head = conn.execute(
                "SELECT latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            if head is None:
                sequence = 1
                previous_hash = GENESIS_PREVIOUS_HASH
            else:
                sequence = int(head["latest_sequence"]) + 1
                previous_hash = head["latest_event_hash"]

            envelope["sequence"] = sequence
            envelope["previous_event_hash"] = previous_hash
            validate_event_envelope(envelope)
            event_hash = compute_event_hash(envelope)
            envelope["event_hash"] = event_hash

            conn.execute(
                """
                INSERT INTO artifacts(digest_ref, size_bytes) VALUES (?, ?)
                ON CONFLICT(digest_ref) DO NOTHING
                """,
                (payload_ref, len(payload)),
            )
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
                    event_hash,
                    previous_hash,
                    payload_ref,
                    json.dumps(envelope),
                ),
            )
            conn.execute(
                """
                INSERT INTO chain_heads(task_id, latest_sequence, latest_event_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  latest_sequence = excluded.latest_sequence,
                  latest_event_hash = excluded.latest_event_hash
                """,
                (task_id, sequence, event_hash),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return envelope

    def get_events(self, task_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT envelope_json FROM events WHERE task_id = ? ORDER BY sequence ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        events = [json.loads(row["envelope_json"]) for row in rows]
        verify_task_chain(events)
        return events

    def export_chain_head(self, task_id: str) -> dict[str, Any]:
        head = self.get_chain_head(task_id)
        if head is None:
            raise ValidationError(f"no chain head for task {task_id}")
        return {
            "task_id": head.task_id,
            "latest_sequence": head.latest_sequence,
            "latest_event_hash": head.latest_event_hash,
        }
