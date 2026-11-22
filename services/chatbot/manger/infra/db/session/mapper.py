"""Chat tables. Users stay in the app database, so `user_id` is not a foreign key."""

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Enum,
    ForeignKey,
    MetaData,
    Table,
    Text,
    Uuid,
    event,
    text,
)
from sqlalchemy.orm import registry, relationship

from manger.domain import ContentType, Message, Session, Turn

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

sessions = Table(
    "chat_sessions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, nullable=False, index=True),
    Column("book_id", Uuid, nullable=True),
)

messages = Table(
    "chat_messages",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "session_id",
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("date", DateTime(timezone=True), nullable=False),
    Column(
        "turn",
        Enum(Turn, name="chat_message_turn", values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
    ),
    Column("content", Text, nullable=False),
    Column(
        "content_type",
        Enum(
            ContentType,
            name="chat_message_content_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    ),
)

_mapped = False


def start_mappers() -> None:
    global _mapped
    if _mapped:
        return

    mapper_registry.map_imperatively(Message, messages)
    mapper_registry.map_imperatively(
        Session,
        sessions,
        properties={
            "messages": relationship(
                Message, cascade="all, delete-orphan", lazy="selectin", order_by=messages.c.date
            ),
        },
    )
    event.listen(Session, "load", _init_session_events)
    _mapped = True


def _init_session_events(session: Session, _context) -> None:
    # Loaded sessions skip __init__, so `events` is never set.
    session.events = []


def init_db(engine: Engine) -> None:
    """Create the chat tables in the chatbot database."""
    metadata.create_all(engine, checkfirst=True)
    # create_all does not add columns to a table that already exists.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS book_id UUID")
        )
