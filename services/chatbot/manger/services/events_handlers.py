"""Reactions to domain events. Each event can have any number of handlers."""

import logging
from collections.abc import Callable

from manger.domain import events

logger = logging.getLogger(__name__)


def log_session_created(event: events.SessionCreated) -> None:
    logger.info(
        "session %s created for user %s on book %s",
        event.session_id,
        event.user_id,
        event.book_id,
    )


EVENT_HANDLERS: dict[type[events.Event], list[Callable[[events.Event], None]]] = {
    events.SessionCreated: [log_session_created],
}
