import copy
import json
from pathlib import Path

import pytest

from aisdlc.errors import ChainIntegrityError
from aisdlc.ledger.chain import (
    GENESIS_PREVIOUS_HASH,
    compute_event_hash,
    event_body_for_hash,
    verify_task_chain,
)

FIXTURES = Path(__file__).parent / "fixtures" / "events"


def test_event_body_for_hash_excludes_event_hash():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    event["event_hash"] = "sha256:" + "f" * 64
    body = event_body_for_hash(event)
    assert "event_hash" not in body
    assert body["previous_event_hash"] == event["previous_event_hash"]


def test_compute_event_hash_is_deterministic():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    assert compute_event_hash(event) == compute_event_hash(copy.deepcopy(event))


def test_verify_task_chain_detects_tamper():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    event["previous_event_hash"] = GENESIS_PREVIOUS_HASH
    event["event_hash"] = compute_event_hash(event)
    tampered = copy.deepcopy(event)
    tampered["payload_schema"] = "mutated/v0.1"
    with pytest.raises(ChainIntegrityError):
        verify_task_chain([tampered])
