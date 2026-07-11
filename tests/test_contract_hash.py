# tests/test_contract_hash.py
import json
from pathlib import Path

from aisdlc.validation.contract import compute_contract_body_hash, contract_body_for_hash

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def test_contract_body_hash_omits_status_and_hash_fields():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    contract = doc["contract"]
    body = contract_body_for_hash(contract)
    assert "status" not in body
    assert "contract_body_hash" not in body
    assert "approval_event_refs" not in body


def test_contract_body_hash_is_stable():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    first = compute_contract_body_hash(doc["contract"])
    second = compute_contract_body_hash(doc["contract"])
    assert first == second
    assert first.startswith("sha256:")
