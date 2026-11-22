from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from manger.domain import ContentType, Message, Session, Turn
from manger.domain.events import SessionCreated


def message(**overrides) -> Message:
    values = {
        "date": datetime(2026, 11, 22, tzinfo=timezone.utc),
        "turn": Turn.USER,
        "content": "hello",
        "content_type": ContentType.TEXT,
    }
    values.update(overrides)
    return Message(**values)


def test_turn_values():
    assert Turn.SYSTEM.value == "system"
    assert Turn.USER.value == "user"
    assert Turn.AI.value == "ai"
    assert Turn("ai") is Turn.AI


def test_content_type_is_text():
    assert ContentType.TEXT.value == "text"
    assert ContentType("text") is ContentType.TEXT


def test_session_starts_with_no_messages():
    session = Session(user_id=uuid4())
    assert isinstance(session.id, UUID)
    assert session.messages == []


def test_add_message_appends_it_to_the_session():
    session = Session(user_id=uuid4())
    first = message(content="first")
    second = message(turn=Turn.AI, content="second")

    session.add_message(first)
    session.add_message(second)

    assert session.messages == [first, second]


def test_add_message_rejects_a_duplicate_id():
    session = Session(user_id=uuid4())
    sent = message()
    session.add_message(sent)

    with pytest.raises(ValueError, match="already belongs"):
        session.add_message(sent)


@pytest.mark.parametrize("content", ["", "   "])
def test_message_rejects_blank_content(content: str):
    with pytest.raises(ValueError, match="content"):
        message(content=content)


def test_message_rejects_an_unknown_turn():
    with pytest.raises(ValueError):
        Turn("assistant")


def test_add_book_context_stores_a_system_message_and_raises_an_event():
    user_id = uuid4()
    book_id = uuid4()
    session = Session(user_id=user_id)

    session.add_book_context(book_id, "Page 1\nHello")

    assert session.book_id == book_id
    assert session.events == [SessionCreated(session.id, user_id, book_id)]
    assert session.messages[0].turn is Turn.SYSTEM
    assert session.messages[0].content == "Page 1\nHello"
    assert session.messages[0].content_type is ContentType.TEXT


def test_new_session_has_no_events():
    assert Session(user_id=uuid4()).events == []


def test_sessions_with_the_same_id_are_the_same_session():
    session_id = uuid4()
    user_id = uuid4()
    assert Session(user_id, id=session_id) == Session(user_id, id=session_id)
