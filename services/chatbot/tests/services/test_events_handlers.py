import logging
from uuid import uuid4

from manger.domain import events
from manger.services import events_handlers


def test_every_event_has_a_handler():
    for event_type in events.Event.__subclasses__():
        assert events_handlers.EVENT_HANDLERS.get(event_type), event_type


def test_session_created_is_logged(caplog):
    event = events.SessionCreated(session_id=uuid4(), user_id=uuid4(), book_id=uuid4())

    with caplog.at_level(logging.INFO):
        events_handlers.log_session_created(event)

    assert str(event.session_id) in caplog.text
    assert str(event.book_id) in caplog.text
