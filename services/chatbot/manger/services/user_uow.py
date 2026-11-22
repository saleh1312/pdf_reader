"""Port for the app database, used to read books. The adapter lives in infrastructure."""

from __future__ import annotations

import abc
from typing import Any


class AbstractUserUnitOfWork(abc.ABC):
    """Opens one session on the app database.

    `db` is that session while the block is open. Views run SQL through it.
    """

    db: Any

    def __enter__(self) -> AbstractUserUnitOfWork:
        return self

    def __exit__(self, *args) -> None:
        self.rollback()

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
