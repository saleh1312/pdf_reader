from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from manger.domain import ContentType, Message, Session, Turn
from manger.infra.db.session import mapper
from manger.infra.db.session.uow import CHATBOT_ENGINE, SessionDbUnitOfWork
from manger.infra.db.user.uow import APP_ENGINE, UserDbUnitOfWork


@pytest.fixture(scope="module", autouse=True)
def databases() -> None:
    mapper.start_mappers()
    try:
        mapper.init_db(CHATBOT_ENGINE)
    except OperationalError:
        pytest.skip("Chatbot Postgres is not reachable (docker compose up -d in services/chatbot)")


def test_session_db_unit_of_work_saves_a_session_and_its_messages():
    user_id = uuid4()
    first = Message(
        date=datetime(2026, 11, 22, 1, 0, tzinfo=timezone.utc),
        turn=Turn.USER,
        content="What is in the book?",
        content_type=ContentType.TEXT,
    )
    second = Message(
        date=datetime(2026, 11, 22, 1, 1, tzinfo=timezone.utc),
        turn=Turn.AI,
        content="Chapter one.",
        content_type=ContentType.TEXT,
    )
    session = Session(user_id=user_id)
    session.add_message(first)
    session.add_message(second)
    session_id = session.id

    try:
        with SessionDbUnitOfWork() as uow:
            uow.sessions.add(session)
            uow.commit()

        with SessionDbUnitOfWork() as uow:
            stored = uow.sessions.get(session_id)
            assert stored is not None
            assert stored.user_id == user_id
            assert [item.turn for item in stored.messages] == [Turn.USER, Turn.AI]
            assert [item.content for item in stored.messages] == [
                "What is in the book?",
                "Chapter one.",
            ]
            assert uow.sessions.list_for_user(user_id)[0].id == session_id
    finally:
        with CHATBOT_ENGINE.begin() as connection:
            connection.execute(text("DELETE FROM chat_sessions WHERE id = :id"), {"id": session_id})


def test_user_db_unit_of_work_reads_a_user_from_the_app_database():
    user_id = uuid4()
    username = f"chat-{user_id}"
    try:
        with APP_ENGINE.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, name, username, password_hash)
                    VALUES (:id, :name, :username, :password_hash)
                    """
                ),
                {
                    "id": user_id,
                    "name": "Chat User",
                    "username": username,
                    "password_hash": "hash",
                },
            )
    except (OperationalError, ProgrammingError):
        pytest.skip("App Postgres is not reachable")

    try:
        with UserDbUnitOfWork() as uow:
            row = uow.db.execute(
                text("SELECT name, username FROM users WHERE id = :id"),
                {"id": user_id},
            ).one()
            assert row.name == "Chat User"
            assert row.username == username
    finally:
        with APP_ENGINE.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
