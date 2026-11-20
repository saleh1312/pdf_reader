"""Things that have happened in the domain, raised by aggregates."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class Logging(Event):
    message: str


@dataclass(frozen=True)
class StoreFile(Event):
    """The book's file still needs to be written to storage."""

    user_id: UUID
    book_id: UUID
    storage_provider: str
    key: str
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class ParseBook(Event):
    """The book's file should be parsed."""

    user_id: UUID
    book_id: UUID
    name: str
    storage_provider: str
    key: str
