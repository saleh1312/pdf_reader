"""Port for the app database. The SQLAlchemy adapter lives in the infrastructure layer."""

from __future__ import annotations

import abc
from collections.abc import Iterator

from manger.domain.events import Event
from manger.services.repository import AbstractUserRepository


class AbstractUnitOfWork(abc.ABC):
    users: AbstractUserRepository

    def __enter__(self) -> AbstractUnitOfWork:
        return self

    def __exit__(self, *args) -> None:
        # Anything not explicitly committed is discarded.
        self.rollback()

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError

    def collect_new_events(self) -> Iterator[Event]:
        """Drain the pending events of every user the repository has seen."""
        for user in self.users.seen:
            while user.events:
                yield user.events.pop(0)
