"""Unit of work that opens a SQLAlchemy session on the app database."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from manger.services.user_uow import AbstractUserUnitOfWork

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


def app_database_url() -> str:
    configured = os.environ.get("APP_DATABASE_URL", "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        from_file = (dotenv_values(_ENV_FILE).get("APP_DATABASE_URL") or "").strip()
        if from_file:
            return from_file
    raise RuntimeError(f"APP_DATABASE_URL is missing from the environment or {_ENV_FILE}")


APP_ENGINE = create_engine(app_database_url())
APP_SESSION_FACTORY = sessionmaker(bind=APP_ENGINE)


class UserDbUnitOfWork(AbstractUserUnitOfWork):
    """Manages one database session connected to the services/app Postgres database."""

    def __init__(self, session_factory: sessionmaker[DbSession] = APP_SESSION_FACTORY):
        self.session_factory = session_factory

    def __enter__(self) -> UserDbUnitOfWork:
        self.db = self.session_factory()
        super().__enter__()
        return self

    def __exit__(self, *args) -> None:
        self.rollback()
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
