"""Reactions to domain events. Each event can have any number of handlers."""

import json
import logging
from collections.abc import Callable

from manger.domain import StorageProvider, events
from manger.infra.mq import PARSE_QUEUE, AbstractMessagePublisher, RabbitMqPublisher
from manger.infra.storage import AbstractStorage, LocalStorage
from manger.services.commands_handlers import StorageNotFound

logger = logging.getLogger(__name__)


def log_message(event: events.Logging) -> None:
    logger.info(event.message)


def store_file(event: events.StoreFile, storage: AbstractStorage | None = None) -> None:
    """Write the book's bytes the same way an upload does: local disk only."""
    if StorageProvider(event.storage_provider) is StorageProvider.S3:
        raise StorageNotFound("S3 storage not found")
    (storage or LocalStorage()).save(event.key, event.content)


def publish_parse(
    event: events.ParseBook, publisher: AbstractMessagePublisher | None = None
) -> None:
    """Ask the parsing worker to render the book and send its pages to PaddleOCR."""
    body = json.dumps(
        {
            "user_id": str(event.user_id),
            "book_id": str(event.book_id),
            "name": event.name,
            "storage_provider": event.storage_provider,
            "storage_key": event.key,
        }
    ).encode()
    (publisher or RabbitMqPublisher()).publish(PARSE_QUEUE, body)


EVENT_HANDLERS: dict[type[events.Event], list[Callable[[events.Event], None]]] = {
    events.Logging: [log_message],
    events.StoreFile: [store_file],
    events.ParseBook: [publish_parse],
}
