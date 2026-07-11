from __future__ import annotations

import os
import tempfile
from pathlib import Path

from aisdlc.canonical.hashing import digest_ref, parse_digest_ref, sha256_digest
from aisdlc.errors import ArtifactMismatchError


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_ref(self, ref: str) -> Path:
        digest = parse_digest_ref(ref)
        hex_digest = digest.hex()
        return self.root / hex_digest[:2] / hex_digest[2:]

    def _atomic_write(self, path: Path, data: bytes) -> None:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def put(self, data: bytes) -> str:
        ref = digest_ref(data)
        path = self._path_for_ref(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if sha256_digest(existing) == sha256_digest(data):
                return ref
        self._atomic_write(path, data)
        return ref

    def get(self, ref: str) -> bytes:
        path = self._path_for_ref(ref)
        if not path.exists():
            raise FileNotFoundError(ref)
        data = path.read_bytes()
        self.verify(ref, data)
        return data

    def verify(self, ref: str, data: bytes) -> None:
        if digest_ref(data) != ref:
            raise ArtifactMismatchError(f"artifact bytes do not match {ref}")
