# src/aisdlc/validation/event.py
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from aisdlc.errors import ValidationError


@lru_cache(maxsize=1)
def get_event_validator() -> Draft202012Validator:
    raw = resources.files("aisdlc.schemas.evidence-event").joinpath("v0.1.0.schema.json").read_text(
        encoding="utf-8"
    )
    schema = json.loads(raw)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate_event_envelope(event: dict[str, Any]) -> None:
    validator = get_event_validator()
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    if errors:
        raise ValidationError("; ".join(e.message for e in errors))
