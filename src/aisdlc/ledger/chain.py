from __future__ import annotations

import copy
from typing import Any

from aisdlc.canonical.hashing import digest_ref
from aisdlc.canonical.jcs import canonicalize_json
from aisdlc.errors import ChainIntegrityError

GENESIS_PREVIOUS_HASH = "sha256:" + ("0" * 64)


def event_body_for_hash(event: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(event)
    body.pop("event_hash", None)
    return body


def compute_event_hash(event: dict[str, Any]) -> str:
    return digest_ref(canonicalize_json(event_body_for_hash(event)))


def verify_task_chain(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    expected_sequence = 1
    expected_previous = GENESIS_PREVIOUS_HASH
    for event in events:
        if event.get("sequence") != expected_sequence:
            raise ChainIntegrityError(
                f"sequence gap: expected {expected_sequence}, got {event.get('sequence')}"
            )
        if event.get("previous_event_hash") != expected_previous:
            raise ChainIntegrityError("previous_event_hash does not match chain head")
        declared = event.get("event_hash")
        computed = compute_event_hash(event)
        if declared != computed:
            raise ChainIntegrityError(
                f"event_hash mismatch at sequence {event.get('sequence')}"
            )
        expected_sequence += 1
        expected_previous = declared
