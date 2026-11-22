from pathlib import Path
from uuid import uuid4

import pytest

from manger.domain import commands, events
from manger.domain.commands import CreateSession
from manger.infra.db.session.uow import FakeSessionUnitOfWork
from manger.services import commands_handlers
from manger.services.events_handlers import EVENT_HANDLERS
from manger.services.messagebus import MessageBus


def test_create_session_handles_the_event_it_raises(tmp_path: Path):
    user_id, book_id = uuid4(), uuid4()
    parsed = tmp_path / "owner" / "book" / "Notes_parsed"
    parsed.mkdir(parents=True)
    (parsed / "page_0001.json").write_text(
        '{"block_label": "text", "block_content": "Hello"}',
        encoding="utf-8",
    )
    uow = FakeSessionUnitOfWork()
    handled = []

    def create(command, unit):
        return commands_handlers.create_session(
            command,
            unit,
            lookup_book=lambda *_args: {
                "name": "Notes",
                "storage_provider": "local",
                "storage_key": "owner/book/notes.pdf",
                "is_parsed": True,
            },
            storage_root=tmp_path,
        )

    bus = MessageBus(uow, {events.SessionCreated: [handled.append]}, {CreateSession: create})

    result = bus.handle(CreateSession(user_id, book_id))

    assert result["status"] == "success"
    assert handled == [events.SessionCreated(result["session_id"], user_id, book_id)]
    assert list(uow.collect_new_events()) == []


def test_a_failing_event_handler_does_not_stop_the_others():
    uow = FakeSessionUnitOfWork()
    handled = []

    def broken(event: events.SessionCreated) -> None:
        raise RuntimeError("log failed")

    bus = MessageBus(
        uow,
        {events.SessionCreated: [broken, handled.append]},
        commands_handlers.COMMAND_HANDLERS,
    )

    bus.handle(events.SessionCreated(uuid4(), uuid4(), uuid4()))

    assert len(handled) == 1


def test_failing_command_is_reraised():
    bus = MessageBus(
        FakeSessionUnitOfWork(),
        EVENT_HANDLERS,
        {
            commands.CreateSession: lambda command, uow: commands_handlers.create_session(
                command, uow, lookup_book=lambda *_args: None
            )
        },
    )

    with pytest.raises(commands_handlers.UnknownBook):
        bus.handle(CreateSession(uuid4(), uuid4()))


def test_rejects_messages_that_are_not_commands_or_events():
    bus = MessageBus(FakeSessionUnitOfWork(), EVENT_HANDLERS, commands_handlers.COMMAND_HANDLERS)

    with pytest.raises(Exception, match="not an Event or Command"):
        bus.handle("hello")
