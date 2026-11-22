from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from manger.infra.db.repo import FakeUserRepository, SqlAlchemyUserRepository
from manger.services.unit_of_work import AbstractUnitOfWork


def get_postgres_uri() -> str:
    # Defaults match db/lunch/docker-compose.yml.
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/pdf_reader",
    )


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
