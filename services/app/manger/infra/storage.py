"""Where uploaded book files are written.

Only local disk is implemented. The directory comes from `LOCAL_STORAGE_PATH`
in `services/app/.env`. S3 has no adapter; adding a book with `s3` is rejected.
"""

from __future__ import annotations

import abc
import os
from pathlib import Path

from dotenv import dotenv_values

from manger.domain import StorageProvider

# services/app/.env when this file lives in manger/infra/.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_STORAGE_PATH_KEY = "LOCAL_STORAGE_PATH"


class AbstractStorage(abc.ABC):
    """Writes a book's bytes. `provider` is recorded on the book."""

    provider: StorageProvider

    @abc.abstractmethod
    def save(self, key: str, content: bytes) -> None:
        """Store `content` at `key`, replacing anything already there."""


def storage_root_from_env(env_file: Path | str = _ENV_FILE) -> Path:
    """Read `LOCAL_STORAGE_PATH` from the environment, then from a `.env` file.

    Relative paths are resolved from the `.env` file's directory.
    """
    path = Path(env_file)
    configured = os.environ.get(_STORAGE_PATH_KEY, "").strip()
    if not configured:
        if not path.is_file():
            raise RuntimeError(f"Missing {path}")
        configured = (dotenv_values(path).get(_STORAGE_PATH_KEY) or "").strip()
        if not configured:
            raise RuntimeError(f"{_STORAGE_PATH_KEY} is missing from {path}")
    root = Path(configured)
    if not root.is_absolute():
        root = path.parent / root
    return root


class LocalStorage(AbstractStorage):
    """Stores files under the directory named by `LOCAL_STORAGE_PATH` in `.env`."""

    provider = StorageProvider.LOCAL

    def __init__(
        self,
        root: Path | str | None = None,
        env_file: Path | str | None = None,
    ):
        if root is None:
            root = storage_root_from_env(_ENV_FILE if env_file is None else env_file)
        self.root = Path(root)

    def save(self, key: str, content: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def resolve(self, key: str) -> Path:
        """Absolute path of a stored file, or FileNotFoundError when it is missing."""
        path = self._path_for(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path

    def _path_for(self, key: str) -> Path:
        if not key.strip():
            raise ValueError("Storage key must not be empty")
        root = self.root.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Storage key escapes the storage root")
        return path
