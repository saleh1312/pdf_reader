from __future__ import annotations

import abc
import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from manger.domain.events import Event

from manger.infra.db.repo import (
    AbstractUserRepository,
    FakeUserRepository,
    SqlAlchemyUserRepository,
)


def get_postgres_uri() -> str:
    # Defaults match db/lunch/docker-compose.yml.
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/pdf_reader",
    )


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


DEFAULT_ENGINE = create_engine(get_postgres_uri())
DEFAULT_SESSION_FACTORY = sessionmaker(bind=DEFAULT_ENGINE)


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: sessionmaker[Session] = DEFAULT_SESSION_FACTORY):
        self.session_factory = session_factory

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self.session_factory()
        self.users = SqlAlchemyUserRepository(self.session)
        super().__enter__()
        return self

    def __exit__(self, *args) -> None:
        super().__exit__(*args)
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class FakeUnitOfWork(AbstractUnitOfWork):
    """In-memory unit of work for testing services without a database.

    Changes are not undone on rollback; tests check `committed` instead.
    """

    def __init__(self, users: FakeUserRepository | None = None):
        self.users = users or FakeUserRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass
