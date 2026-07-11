import json

from aisdlc.canonical.hashing import digest_ref, parse_digest_ref, sha256_digest
from aisdlc.canonical.jcs import canonicalize_json


def test_canonicalize_json_is_deterministic():
    obj = {"b": 2, "a": 1, "nested": {"z": True, "y": None}}
    first = canonicalize_json(obj)
    second = canonicalize_json({"a": 1, "b": 2, "nested": {"y": None, "z": True}})
    assert first == second
    assert json.loads(first) == {"a": 1, "b": 2, "nested": {"y": None, "z": True}}


def test_digest_ref_round_trip():
    data = b"artifact-body"
    ref = digest_ref(data)
    assert ref.startswith("sha256:")
    assert parse_digest_ref(ref) == bytes.fromhex(sha256_digest(data))


def test_sha256_digest_is_lowercase_hex():
    assert sha256_digest(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
