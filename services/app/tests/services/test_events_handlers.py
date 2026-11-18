import logging

import pytest

from manger.domain import Book, StorageLocation, StorageProvider, User, events
from manger.services import events_handlers


def test_every_event_has_handlers():
    for event_type in events.Event.__subclasses__():
        assert events_handlers.EVENT_HANDLERS.get(event_type), event_type


def test_log_message_logs_the_event_message(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO):
        events_handlers.log_message(events.Logging(message="hello"))

    assert caplog.messages == ["hello"]


def test_book_events_from_the_user_are_logged(caplog: pytest.LogCaptureFixture):
    user = User("Ahmed", "ahmed", "hash")
    book = Book("Clean Architecture", StorageLocation(StorageProvider.LOCAL, "a.pdf"))
    user.add_book(book)
    user.remove_book(book.id)

    with caplog.at_level(logging.INFO):
        for event in user.events:
            for handler in events_handlers.EVENT_HANDLERS[type(event)]:
                handler(event)

    assert caplog.messages == [e.message for e in user.events]
    assert len(caplog.messages) == 2
