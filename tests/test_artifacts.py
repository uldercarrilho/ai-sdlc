import pytest

from aisdlc.artifacts.store import ArtifactStore
from aisdlc.errors import ArtifactMismatchError


def test_put_get_round_trip(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    data = b'{"payload": true}'
    ref = store.put(data)
    assert store.get(ref) == data


def test_verify_detects_mismatch(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    ref = store.put(b"original")
    with pytest.raises(ArtifactMismatchError):
        store.verify(ref, b"tampered")


def test_put_is_idempotent(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    data = b"same-bytes"
    assert store.put(data) == store.put(data)


def test_put_heals_corrupted_file(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    data = b"correct-bytes"
    ref = store.put(data)
    path = store._path_for_ref(ref)
    path.write_bytes(b"corrupted")
    store.put(data)
    assert store.get(ref) == data
