from datetime import datetime, timezone
from uuid import uuid4

from manger.domain import ContentType, Message, Session, Turn
from manger.infra.db.session.repo import FakeSessionRepository
from manger.infra.db.session.uow import FakeSessionUnitOfWork


def message(content: str, turn: Turn = Turn.USER) -> Message:
    return Message(
        date=datetime(2026, 11, 22, tzinfo=timezone.utc),
        turn=turn,
        content=content,
        content_type=ContentType.TEXT,
    )


def test_repository_adds_and_lists_sessions_for_a_user():
    user_id = uuid4()
    other_user = uuid4()
    repo = FakeSessionRepository()
    session = Session(user_id=user_id)
    session.add_message(message("hello"))
    other = Session(user_id=other_user)

    repo.add(session)
    repo.add(other)

    assert repo.get(session.id) is session
    assert repo.get(uuid4()) is None
    assert repo.list_for_user(user_id) == [session]
    assert session in repo.seen


def test_fake_unit_of_work_commits_the_session_it_holds():
    user_id = uuid4()
    session = Session(user_id=user_id)
    session.add_message(message("hello", Turn.AI))

    with FakeSessionUnitOfWork() as uow:
        uow.sessions.add(session)
        uow.commit()
        stored = uow.sessions.get(session.id)

    assert uow.committed
    assert stored is not None
    assert stored.messages[0].content == "hello"
    assert stored.messages[0].turn is Turn.AI
