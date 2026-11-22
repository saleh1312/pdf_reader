from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from manger.domain import Session
from manger.infra.db.session.mapper import sessions
from manger.services.session_repository import AbstractSessionRepository


class SqlAlchemySessionRepository(AbstractSessionRepository):
    def __init__(self, db: DbSession):
        super().__init__()
        self.db = db

    def _add(self, session: Session) -> None:
        self.db.add(session)

    def _get(self, session_id: UUID) -> Session | None:
        return self.db.get(Session, session_id)

    def _list_for_user(self, user_id: UUID) -> list[Session]:
        stmt = select(Session).where(sessions.c.user_id == user_id).order_by(sessions.c.id)
        return list(self.db.scalars(stmt).all())


class FakeSessionRepository(AbstractSessionRepository):
    """In-memory repository for tests; never touches a database."""

    def __init__(self, sessions: list[Session] | None = None):
        super().__init__()
        self._sessions: dict[UUID, Session] = {session.id: session for session in sessions or []}

    def _add(self, session: Session) -> None:
        self._sessions[session.id] = session

    def _get(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    def _list_for_user(self, user_id: UUID) -> list[Session]:
        return [session for session in self._sessions.values() if session.user_id == user_id]
