from __future__ import annotations

import sqlite3
from pathlib import Path

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS artifacts (
  digest_ref TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  stored_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chain_heads (
  task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
  latest_sequence INTEGER NOT NULL,
  latest_event_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  sequence INTEGER NOT NULL,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  previous_event_hash TEXT NOT NULL,
  payload_ref TEXT NOT NULL,
  envelope_json TEXT NOT NULL,
  UNIQUE(task_id, sequence),
  UNIQUE(task_id, event_hash)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()
