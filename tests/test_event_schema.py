# tests/test_event_schema.py
import json
from pathlib import Path

import pytest

from aisdlc.errors import ValidationError
from aisdlc.validation.event import validate_event_envelope

FIXTURES = Path(__file__).parent / "fixtures" / "events"


def test_valid_event_envelope_passes():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    validate_event_envelope(event)


def test_missing_event_id_rejected():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    del event["event_id"]
    with pytest.raises(ValidationError):
        validate_event_envelope(event)


def test_invalid_occurred_at_rejected():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    event["occurred_at"] = "not-a-datetime"
    with pytest.raises(ValidationError):
        validate_event_envelope(event)
