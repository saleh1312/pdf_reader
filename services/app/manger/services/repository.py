"""Port for the user collection. The database adapter lives in the infrastructure layer."""

from __future__ import annotations

import abc
from uuid import UUID

from manger.domain import User


class AbstractUserRepository(abc.ABC):
    """Collection-like access to User aggregates (books are loaded with them).

    Every user added or retrieved through the repository is recorded in
    `seen`, so the unit of work can see which aggregates it touched.
    """

    def __init__(self) -> None:
        self.seen: set[User] = set()

    def add(self, user: User) -> None:
        self._add(user)
        self.seen.add(user)

    def get(self, user_id: UUID) -> User | None:
        user = self._get(user_id)
        if user:
            self.seen.add(user)
        return user

    def get_by_book_id(self, book_id: UUID) -> User | None:
        """Return the user who owns the given book."""
        user = self._get_by_book_id(book_id)
        if user:
            self.seen.add(user)
        return user

    def get_by_username(self, username: str) -> User | None:
        user = self._get_by_username(username)
        if user:
            self.seen.add(user)
        return user

    @abc.abstractmethod
    def _add(self, user: User) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abc.abstractmethod
    def _get_by_book_id(self, book_id: UUID) -> User | None:
        raise NotImplementedError

    @abc.abstractmethod
    def _get_by_username(self, username: str) -> User | None:
        raise NotImplementedError
