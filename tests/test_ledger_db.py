import sqlite3

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
