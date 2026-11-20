import logging
from uuid import UUID, uuid4

import pytest

from manger.domain import Book, StorageLocation, StorageProvider, events
from manger.domain.commands import SignIn, SignUp
from manger.infra.db.uow import AbstractUnitOfWork, FakeUnitOfWork
from manger.services import commands_handlers
from manger.services.commands_handlers import COMMAND_HANDLERS, InvalidCredentials
from manger.services.events_handlers import EVENT_HANDLERS
from manger.services.messagebus import MessageBus


@pytest.fixture
def username() -> str:
    return f"ahmed-{uuid4().hex[:8]}"


def test_sign_up_and_sign_in_through_the_bus(uow: AbstractUnitOfWork, username: str):
    bus = MessageBus(uow, EVENT_HANDLERS, COMMAND_HANDLERS)

    user_id = bus.handle(SignUp("Ahmed", username, "secret"))

    assert bus.handle(SignIn(username, "secret")) == user_id


def test_failing_command_is_reraised(uow: AbstractUnitOfWork, username: str):
    bus = MessageBus(uow, EVENT_HANDLERS, COMMAND_HANDLERS)

    with pytest.raises(InvalidCredentials):
        bus.handle(SignIn(username, "secret"))


def test_events_raised_by_the_domain_are_handled_after_the_command(
    uow: AbstractUnitOfWork, username: str
):
    def sign_up_with_a_book(command: SignUp, uow: AbstractUnitOfWork) -> UUID:
        user_id = commands_handlers.sign_up(command, uow)
        with uow:
            user = uow.users.get(user_id)
            user.add_book(
                Book("Clean Architecture", StorageLocation(StorageProvider.LOCAL, "a.pdf")),
                b"%PDF",
            )
            uow.commit()
        return user_id

    handled: list[type] = []

    def record(event: events.Event) -> None:
        handled.append(type(event))

    bus = MessageBus(
        uow,
        {events.StoreFile: [record], events.ParseBook: [record]},
        {SignUp: sign_up_with_a_book},
    )

    bus.handle(SignUp("Ahmed", username, "secret"))

    assert handled == [events.StoreFile, events.ParseBook]
    assert list(uow.collect_new_events()) == []


def test_events_raised_while_handling_an_event_are_handled_too():
    uow = FakeUnitOfWork()
    handled = []

    def first(event: events.Logging) -> None:
        handled.append(event.message)
        if event.message == "first":
            with uow:
                user = uow.users.get_by_username("ahmed")
                user.events.append(events.Logging("second"))

    commands_handlers.sign_up(SignUp("Ahmed", "ahmed", "secret"), uow)
    bus = MessageBus(uow, {events.Logging: [first]}, COMMAND_HANDLERS)

    bus.handle(events.Logging("first"))

    assert handled == ["first", "second"]


def test_failing_event_handler_does_not_stop_the_others(caplog: pytest.LogCaptureFixture):
    handled = []

    def broken(event: events.Logging) -> None:
        raise RuntimeError("boom")

    bus = MessageBus(
        FakeUnitOfWork(), {events.Logging: [broken, handled.append]}, COMMAND_HANDLERS
    )

    bus.handle(events.Logging("hello"))

    assert handled == [events.Logging("hello")]
    assert "Exception handling event" in caplog.text


def test_rejects_messages_that_are_not_commands_or_events():
    bus = MessageBus(FakeUnitOfWork(), EVENT_HANDLERS, COMMAND_HANDLERS)

    with pytest.raises(Exception, match="not an Event or Command"):
        bus.handle("hello")  # type: ignore[arg-type]
