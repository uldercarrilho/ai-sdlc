from __future__ import annotations

import rfc8785


def canonicalize_json(obj: dict) -> bytes:
    return rfc8785.dumps(obj)
