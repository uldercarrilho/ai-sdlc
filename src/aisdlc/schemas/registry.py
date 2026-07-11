# src/aisdlc/schemas/registry.py
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from aisdlc.errors import ValidationError


@lru_cache(maxsize=1)
def get_contract_validator() -> Draft202012Validator:
    raw = resources.files("aisdlc.schemas.execution-contract").joinpath("v0.1.0.schema.json").read_text(
        encoding="utf-8"
    )
    schema = json.loads(raw)
    return Draft202012Validator(schema)


def validate_contract_document(doc: dict[str, Any]) -> None:
    validator = get_contract_validator()
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        messages = "; ".join(e.message for e in errors)
        raise ValidationError(messages)
