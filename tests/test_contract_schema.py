# tests/test_contract_schema.py
import json
from pathlib import Path

import pytest

from aisdlc.errors import ValidationError
from aisdlc.schemas.registry import get_contract_validator, validate_contract_document

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def test_valid_r1_minimal_contract_passes_schema():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    validate_contract_document(doc)  # should not raise


def test_unknown_top_level_field_rejected():
    doc = json.loads((FIXTURES / "invalid_unknown_field.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        validate_contract_document(doc)


def test_validator_is_draft_2020_12():
    validator = get_contract_validator()
    assert validator.schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
