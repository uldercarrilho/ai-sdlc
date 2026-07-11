from __future__ import annotations

import hashlib
import re

_DIGEST_REF_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_ref(data: bytes) -> str:
    return f"sha256:{sha256_digest(data)}"


def parse_digest_ref(ref: str) -> bytes:
    match = _DIGEST_REF_RE.fullmatch(ref)
    if match is None:
        raise ValueError(f"invalid digest reference: {ref!r}")
    return bytes.fromhex(match.group(1))
