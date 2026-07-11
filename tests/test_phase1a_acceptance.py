"""Phase 1A exit criteria from spec section 21."""
import json
from pathlib import Path

import pytest

from aisdlc.errors import ValidationError
from aisdlc.schemas.registry import validate_contract_document
from aisdlc.validation.contract import validate_and_hash_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_schemas_reject_invalid_inputs():
    bad = json.loads((FIXTURES / "contracts" / "invalid_unknown_field.json").read_text())
    with pytest.raises(ValidationError):
        validate_contract_document(bad)


def test_valid_contract_hashes_and_validates():
    good = json.loads((FIXTURES / "contracts" / "valid_r1_minimal.json").read_text())
    digest = validate_and_hash_contract_document(good)
    assert digest.startswith("sha256:")


def test_full_ledger_round_trip(tmp_data_dir):
    from datetime import datetime, timezone
    from uuid import uuid4

    from ulid import ULID

    from aisdlc.ledger.store import LedgerStore

    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    env = {
        "event_id": str(ULID()),
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "contract.approved",
        "actor": {"kind": "human", "id": "owner"},
        "artifact_refs": [],
        "payload_schema": "contract-approved/v0.1",
    }
    stored = store.append_event(task_id, env, b'{"approved": true}')
    events = store.get_events(task_id)
    assert events[0]["event_hash"] == stored["event_hash"]
    head = store.export_chain_head(task_id)
    assert head["latest_event_hash"] == stored["event_hash"]
