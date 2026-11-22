"""Port for chat sessions. The database adapter lives in the infrastructure layer."""

from __future__ import annotations

import abc
from uuid import UUID

from manger.domain import Session


class AbstractSessionRepository(abc.ABC):
    """Collection-like access to Session aggregates, messages included."""

    def __init__(self) -> None:
        self.seen: set[Session] = set()

    def add(self, session: Session) -> None:
        self._add(session)
        self.seen.add(session)

    def get(self, session_id: UUID) -> Session | None:
        session = self._get(session_id)
        if session is not None:
            self.seen.add(session)
        return session

    def list_for_user(self, user_id: UUID) -> list[Session]:
        found = self._list_for_user(user_id)
        self.seen.update(found)
        return found

    @abc.abstractmethod
    def _add(self, session: Session) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, session_id: UUID) -> Session | None:
        raise NotImplementedError

    @abc.abstractmethod
    def _list_for_user(self, user_id: UUID) -> list[Session]:
        raise NotImplementedError
