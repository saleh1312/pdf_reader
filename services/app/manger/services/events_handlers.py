"""Reactions to domain events. Each event can have any number of handlers."""

import logging
from collections.abc import Callable

from manger.domain import events

logger = logging.getLogger(__name__)


def log_message(event: events.Logging) -> None:
    logger.info(event.message)


EVENT_HANDLERS: dict[type[events.Event], list[Callable[[events.Event], None]]] = {
    events.Logging: [log_message],
}
