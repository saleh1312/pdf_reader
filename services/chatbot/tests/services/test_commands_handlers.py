from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from manger.domain import ContentType, Message, Session, Turn, commands
from manger.domain.commands import CreateSession, Infer
from manger.infra.db.session import mapper
from manger.infra.db.session.uow import CHATBOT_ENGINE, FakeSessionUnitOfWork, SessionDbUnitOfWork
from manger.infra.db.user.uow import APP_ENGINE, UserDbUnitOfWork
from manger.services import commands_handlers as handlers
from manger.view import get_book


def _book(**overrides) -> dict:
    book = {
        "name": "Notes",
        "storage_provider": "local",
        "storage_key": "owner/book/notes.pdf",
        "is_parsed": True,
    }
    book.update(overrides)
    return book


def test_every_command_has_a_handler():
    assert set(commands.Command.__subclasses__()) <= set(handlers.COMMAND_HANDLERS)


def test_create_session_stores_the_paragraphs_and_returns_success(tmp_path: Path):
    user_id, book_id = uuid4(), uuid4()
    parsed = tmp_path / "owner" / "book" / "Notes_parsed"
    parsed.mkdir(parents=True)
    (parsed / "page_0001.json").write_text(
        '{"block_label": "text", "block_content": "Chapter one"}',
        encoding="utf-8",
    )
    uow = FakeSessionUnitOfWork()

    result = handlers.create_session(
        CreateSession(user_id, book_id),
        uow,
        lookup_book=lambda uid, bid, _uow: _book(),
        storage_root=tmp_path,
    )

    assert result["status"] == "success"
    assert uow.committed is True
    stored = uow.sessions.get(result["session_id"])
    assert stored.user_id == user_id
    assert stored.messages[0].turn is Turn.SYSTEM
    assert stored.messages[0].content_type is ContentType.TEXT
    assert stored.messages[0].content == "Page 1\nChapter one"
    assert stored.events[0].book_id == book_id


def test_create_session_rejects_an_unknown_book():
    uow = FakeSessionUnitOfWork()

    with pytest.raises(handlers.UnknownBook):
        handlers.create_session(
            CreateSession(uuid4(), uuid4()),
            uow,
            lookup_book=lambda *_args: None,
        )

    assert uow.committed is False


def test_create_session_rejects_a_book_that_is_not_parsed(tmp_path: Path):
    uow = FakeSessionUnitOfWork()

    with pytest.raises(handlers.BookNotParsed):
        handlers.create_session(
            CreateSession(uuid4(), uuid4()),
            uow,
            lookup_book=lambda *_args: _book(is_parsed=False),
            storage_root=tmp_path,
        )

    assert uow.committed is False


def test_create_session_on_the_databases_returns_success(tmp_path: Path):
    mapper.start_mappers()
    try:
        mapper.init_db(CHATBOT_ENGINE)
    except OperationalError:
        pytest.skip("Chatbot Postgres is not reachable")

    user_id, book_id = uuid4(), uuid4()
    parsed = tmp_path / "owner" / "book" / "Notes_parsed"
    parsed.mkdir(parents=True)
    (parsed / "page_0001.json").write_text(
        '{"block_label": "text", "block_content": "From the database"}',
        encoding="utf-8",
    )
    try:
        with APP_ENGINE.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, name, username, password_hash)
                    VALUES (:id, 'Reader', :username, 'hash')
                    """
                ),
                {"id": user_id, "username": f"reader-{user_id}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO books (id, user_id, name, storage_provider, storage_key, is_parsed)
                    VALUES (:id, :user_id, 'Notes', 'local', 'owner/book/notes.pdf', true)
                    """
                ),
                {"id": book_id, "user_id": user_id},
            )
    except (OperationalError, ProgrammingError):
        pytest.skip("App Postgres is not reachable")

    session_id = None
    try:
        result = handlers.create_session(
            CreateSession(user_id, book_id),
            SessionDbUnitOfWork(),
            user_uow=UserDbUnitOfWork(),
            storage_root=tmp_path,
        )
        session_id = result["session_id"]
        assert result["status"] == "success"

        with SessionDbUnitOfWork() as uow:
            stored = uow.sessions.get(session_id)
            assert stored.messages[0].content == "Page 1\nFrom the database"
            assert stored.messages[0].turn is Turn.SYSTEM
    finally:
        if session_id is not None:
            with CHATBOT_ENGINE.begin() as connection:
                connection.execute(
                    text("DELETE FROM chat_sessions WHERE id = :id"), {"id": session_id}
                )
        with APP_ENGINE.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def test_get_book_reads_the_app_database():
    user_id, book_id = uuid4(), uuid4()
    try:
        with APP_ENGINE.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, name, username, password_hash)
                    VALUES (:id, 'Reader', :username, 'hash')
                    """
                ),
                {"id": user_id, "username": f"view-{user_id}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO books (id, user_id, name, storage_provider, storage_key, is_parsed)
                    VALUES (:id, :user_id, 'Notes', 'local', 'owner/book/notes.pdf', false)
                    """
                ),
                {"id": book_id, "user_id": user_id},
            )
    except (OperationalError, ProgrammingError):
        pytest.skip("App Postgres is not reachable")

    try:
        book = get_book(user_id, book_id, UserDbUnitOfWork())
        assert book == {
            "name": "Notes",
            "storage_provider": "local",
            "storage_key": "owner/book/notes.pdf",
            "is_parsed": False,
        }
        assert get_book(uuid4(), book_id, UserDbUnitOfWork()) is None
    finally:
        with APP_ENGINE.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


class RecordingProvider:
    def __init__(self, reply: str = "The answer"):
        self.reply = reply
        self.sent: list[list[Message]] = []

    def send(self, messages: list[Message]) -> str:
        self.sent.append(list(messages))
        return self.reply


def test_infer_sends_history_plus_the_user_message_and_stores_the_reply():
    session = Session(user_id=uuid4())
    session.add_book_context(uuid4(), "Page 1\nHello")
    uow = FakeSessionUnitOfWork()
    with uow:
        uow.sessions.add(session)
        uow.commit()
    provider = RecordingProvider("Chapter one.")

    reply = handlers.infer(Infer(session.id, "  What is chapter one?  "), uow, provider=provider)

    assert reply == "Chapter one."
    assert [item.turn for item in provider.sent[0]] == [Turn.SYSTEM, Turn.USER]
    assert provider.sent[0][-1].content == "What is chapter one?"
    stored = uow.sessions.get(session.id)
    assert [item.turn for item in stored.messages] == [Turn.SYSTEM, Turn.USER, Turn.AI]
    assert stored.messages[-1].content == "Chapter one."
    assert stored.messages[-1].content_type is ContentType.TEXT

    handlers.infer(Infer(session.id, "And chapter two?"), uow, provider=provider)

    assert [item.turn for item in provider.sent[1]] == [
        Turn.SYSTEM,
        Turn.USER,
        Turn.AI,
        Turn.USER,
    ]


def test_infer_rejects_an_unknown_session():
    with pytest.raises(handlers.UnknownSession):
        handlers.infer(Infer(uuid4(), "Hello"), FakeSessionUnitOfWork(), provider=RecordingProvider())


def test_infer_rejects_a_blank_message():
    provider = RecordingProvider()

    with pytest.raises(ValueError, match="empty"):
        handlers.infer(Infer(uuid4(), "   "), FakeSessionUnitOfWork(), provider=provider)

    assert provider.sent == []
