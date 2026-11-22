"""Port for the chatbot database. The SQLAlchemy adapter lives in the infrastructure layer."""

from __future__ import annotations

import abc
from collections.abc import Iterator

from manger.domain.events import Event
from manger.services.session_repository import AbstractSessionRepository


class AbstractSessionUnitOfWork(abc.ABC):
    sessions: AbstractSessionRepository

    def __enter__(self) -> AbstractSessionUnitOfWork:
        return self

    def __exit__(self, *args) -> None:
        self.rollback()

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError

    def collect_new_events(self) -> Iterator[Event]:
        """Drain the pending events of every session the repository has seen."""
        for session in self.sessions.seen:
            while session.events:
                yield session.events.pop(0)
