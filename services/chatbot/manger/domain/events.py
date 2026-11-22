"""Things that have happened in the domain, raised by aggregates."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class SessionCreated(Event):
    """A chat session was opened with a book's paragraphs as its system message."""

    session_id: UUID
    user_id: UUID
    book_id: UUID
