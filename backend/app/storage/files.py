"""File storage behind a tiny interface. Local disk now; an S3-compatible bucket can implement the same."""

import hashlib
import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def put_stream(self, key: str, stream: BinaryIO, limit: int) -> tuple[int, str] | None:
        """Copy a large upload without holding it in memory. Returns (bytes, sha256), or None
        (and stores nothing) when it is larger than limit."""
        ...

    def local_path(self, key: str) -> AbstractContextManager[Path]:
        """A path on disk for tools like ffmpeg (a bucket would download to a temp file)."""
        ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def put_stream(self, key: str, stream: BinaryIO, limit: int) -> tuple[int, str] | None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        digest = hashlib.sha256()
        size = 0
        with tmp.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    break
                digest.update(chunk)
                out.write(chunk)
        if size > limit:
            tmp.unlink(missing_ok=True)
            return None
        os.replace(tmp, path)
        return size, digest.hexdigest()

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        yield self._path(key)


def get_storage() -> Storage:
    return LocalStorage(get_settings().storage_dir)
