from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from manger.infra.db.repo import FakeUserRepository, SqlAlchemyUserRepository
from manger.services.unit_of_work import AbstractUnitOfWork


_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def get_postgres_uri() -> str:
    """`DATABASE_URL` from the environment, then from `services/app/.env`."""
    configured = os.environ.get("DATABASE_URL", "").strip()
    if not configured and _ENV_FILE.is_file():
        configured = (dotenv_values(_ENV_FILE).get("DATABASE_URL") or "").strip()
    if not configured:
        raise RuntimeError(f"DATABASE_URL is missing from the environment or {_ENV_FILE}")
    return configured


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
