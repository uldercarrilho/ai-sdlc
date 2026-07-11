import sqlite3

import pytest

from aisdlc.ledger.db import connect, init_schema


def test_init_schema_creates_tables(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    conn = connect(db_path)
    init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"tasks", "events", "artifacts", "chain_heads"}.issubset(tables)
    conn.close()


def test_connect_enforces_foreign_keys(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    conn = connect(db_path)
    init_schema(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO events (
              event_id, task_id, sequence, occurred_at, event_type,
              event_hash, previous_event_hash, payload_ref, envelope_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1",
                "missing-task",
                1,
                "2026-07-11T14:36:00Z",
                "contract.drafted",
                "sha256:" + "0" * 64,
                "sha256:" + "0" * 64,
                "sha256:" + "0" * 64,
                "{}",
            ),
        )
    conn.close()
