"""Read models for chat sessions. They go through the session unit of work."""

from datetime import datetime, timezone
from uuid import UUID

from manger.domain import Turn
from manger.services.session_uow import AbstractSessionUnitOfWork


def list_sessions(user_id: UUID, uow: AbstractSessionUnitOfWork) -> list[dict]:
    """Every chat for this user, newest activity first."""
    with uow:
        found = uow.sessions.list_for_user(user_id)
        rows = [
            {
                "session_id": session.id,
                "book_id": session.book_id,
                "preview": _preview(session),
                "updated_at": _latest(session),
            }
            for session in found
        ]
    rows.sort(key=lambda row: row["updated_at"], reverse=True)
    for row in rows:
        del row["updated_at"]
    return rows


def get_session(user_id: UUID, session_id: UUID, uow: AbstractSessionUnitOfWork) -> dict | None:
    """The session's messages in time order, or None when it is not this user's."""
    with uow:
        session = uow.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return {
            "session_id": session.id,
            "book_id": session.book_id,
            "messages": [
                {
                    "turn": message.turn.value,
                    "content": message.content,
                    "date": message.date,
                }
                for message in session.messages
            ],
        }


def _preview(session) -> str:
    for message in session.messages:
        if message.turn is Turn.USER:
            text = " ".join(message.content.split())
            return text if len(text) <= 80 else text[:77] + "..."
    return "New chat"


def _latest(session) -> datetime:
    if not session.messages:
        return datetime.min.replace(tzinfo=timezone.utc)
    return session.messages[-1].date
