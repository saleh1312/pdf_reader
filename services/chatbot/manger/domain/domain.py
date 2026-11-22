"""Core domain model.

This layer is pure Python: no database, web framework, or model SDK imports.
A session owns its messages. One session has many messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .events import Event, SessionCreated


class Turn(str, Enum):
    """Who produced a message."""

    SYSTEM = "system"
    USER = "user"
    AI = "ai"


class ContentType(str, Enum):
    """How a message body should be read."""

    TEXT = "text"


@dataclass
class Message:
    date: datetime
    turn: Turn
    content: str
    content_type: ContentType
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.date, datetime):
            raise ValueError("Message date must be a datetime")
        if not isinstance(self.turn, Turn):
            raise ValueError("Message turn must be system, user, or ai")
        if not self.content.strip():
            raise ValueError("Message content must not be empty")
        if not isinstance(self.content_type, ContentType):
            raise ValueError("Message content type must be text")


@dataclass(eq=False)
class Session:
    user_id: UUID
    messages: list[Message] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    book_id: UUID | None = None
    events: list[Event] = field(default_factory=list, init=False, repr=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Session):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def add_message(self, message: Message) -> None:
        if any(existing.id == message.id for existing in self.messages):
            raise ValueError(f"Message {message.id} already belongs to this session")
        self.messages.append(message)

    def add_book_context(self, book_id: UUID, content: str) -> None:
        """Store the book's paragraphs as the session's system message."""
        self.book_id = book_id
        self.add_message(
            Message(
                date=datetime.now(timezone.utc),
                turn=Turn.SYSTEM,
                content=content,
                content_type=ContentType.TEXT,
            )
        )
        self.events.append(
            SessionCreated(session_id=self.id, user_id=self.user_id, book_id=book_id)
        )
