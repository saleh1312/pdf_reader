"""Unit of work for chat sessions and their messages."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from manger.infra.db.session.repo import FakeSessionRepository, SqlAlchemySessionRepository
from manger.services.session_uow import AbstractSessionUnitOfWork

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


def chatbot_database_url() -> str:
    configured = os.environ.get("CHATBOT_DATABASE_URL", "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        from_file = (dotenv_values(_ENV_FILE).get("CHATBOT_DATABASE_URL") or "").strip()
        if from_file:
            return from_file
    raise RuntimeError(f"CHATBOT_DATABASE_URL is missing from the environment or {_ENV_FILE}")


CHATBOT_ENGINE = create_engine(chatbot_database_url())
CHATBOT_SESSION_FACTORY = sessionmaker(bind=CHATBOT_ENGINE)


class SessionDbUnitOfWork(AbstractSessionUnitOfWork):
    """Persists chat sessions in the chatbot Postgres database."""

    def __init__(self, session_factory: sessionmaker[DbSession] = CHATBOT_SESSION_FACTORY):
        self.session_factory = session_factory

    def __enter__(self) -> SessionDbUnitOfWork:
        self.db = self.session_factory()
        self.sessions = SqlAlchemySessionRepository(self.db)
        super().__enter__()
        return self

    def __exit__(self, *args) -> None:
        super().__exit__(*args)
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class FakeSessionUnitOfWork(AbstractSessionUnitOfWork):
    def __init__(self, sessions: FakeSessionRepository | None = None):
        self.sessions = sessions or FakeSessionRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass
