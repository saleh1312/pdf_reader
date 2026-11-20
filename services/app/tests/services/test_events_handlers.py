import json
import logging

import pytest

from manger.domain import Book, StorageLocation, StorageProvider, User, events
from manger.infra.mq import PARSE_QUEUE
from manger.infra.storage import LocalStorage
from manger.services import events_handlers
from manger.services.commands_handlers import StorageNotFound


def test_every_event_has_handlers():
    for event_type in events.Event.__subclasses__():
        assert events_handlers.EVENT_HANDLERS.get(event_type), event_type


def test_log_message_logs_the_event_message(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO):
        events_handlers.log_message(events.Logging(message="hello"))

    assert caplog.messages == ["hello"]


def test_remove_book_event_is_logged(caplog: pytest.LogCaptureFixture):
    user = User("Ahmed", "ahmed", "hash")
    book = Book("Clean Architecture", StorageLocation(StorageProvider.LOCAL, "a.pdf"))
    user.add_book(book, b"pdf")
    user.events.clear()
    user.remove_book(book.id)

    with caplog.at_level(logging.INFO):
        for event in user.events:
            for handler in events_handlers.EVENT_HANDLERS[type(event)]:
                handler(event)

    assert caplog.messages == [e.message for e in user.events]


def test_store_file_writes_the_bytes(tmp_path):
    storage = LocalStorage(tmp_path)
    event = events.StoreFile(
        user_id=Book("A", StorageLocation(StorageProvider.LOCAL, "a.pdf")).id,
        book_id=Book("B", StorageLocation(StorageProvider.LOCAL, "b.pdf")).id,
        storage_provider="local",
        key="notes.pdf",
        content=b"%PDF-1.4",
    )

    events_handlers.store_file(event, storage)

    assert (tmp_path / "notes.pdf").read_bytes() == b"%PDF-1.4"


def test_store_file_rejects_s3(tmp_path):
    event = events.StoreFile(
        user_id=Book("A", StorageLocation(StorageProvider.LOCAL, "a.pdf")).id,
        book_id=Book("B", StorageLocation(StorageProvider.LOCAL, "b.pdf")).id,
        storage_provider="s3",
        key="notes.pdf",
        content=b"%PDF",
    )

    with pytest.raises(StorageNotFound, match="not found"):
        events_handlers.store_file(event, LocalStorage(tmp_path))

    assert list(tmp_path.rglob("*")) == []


class RecordingPublisher:
    def __init__(self):
        self.messages: list[tuple[str, bytes]] = []

    def publish(self, queue: str, body: bytes) -> None:
        self.messages.append((queue, body))


def test_publish_parse_sends_the_book_to_the_queue():
    book_id = Book("A", StorageLocation(StorageProvider.LOCAL, "a.pdf")).id
    user_id = Book("B", StorageLocation(StorageProvider.LOCAL, "b.pdf")).id
    event = events.ParseBook(user_id, book_id, "Notes", "local", "user/book/notes.pdf")
    publisher = RecordingPublisher()

    events_handlers.publish_parse(event, publisher)

    assert len(publisher.messages) == 1
    queue, body = publisher.messages[0]
    assert queue == PARSE_QUEUE
    assert json.loads(body) == {
        "user_id": str(user_id),
        "book_id": str(book_id),
        "name": "Notes",
        "storage_provider": "local",
        "storage_key": "user/book/notes.pdf",
    }
