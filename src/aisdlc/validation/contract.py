# src/aisdlc/validation/contract.py
from __future__ import annotations

import copy
from typing import Any

from aisdlc.canonical.hashing import digest_ref
from aisdlc.canonical.jcs import canonicalize_json
from aisdlc.schemas.registry import validate_contract_document

_OMIT_FOR_HASH = frozenset({"status", "contract_body_hash", "approval_event_refs"})


def contract_body_for_hash(contract: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(contract)
    for key in _OMIT_FOR_HASH:
        body.pop(key, None)
    return body


def compute_contract_body_hash(contract: dict[str, Any]) -> str:
    body = contract_body_for_hash(contract)
    return digest_ref(canonicalize_json(body))


def validate_and_hash_contract_document(doc: dict[str, Any]) -> str:
    validate_contract_document(doc)
    return compute_contract_body_hash(doc["contract"])
