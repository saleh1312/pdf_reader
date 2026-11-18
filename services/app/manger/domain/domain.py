"""Core domain model.

This layer is pure Python: no database, web framework, or cloud SDK imports.
Outer layers (repositories, storage adapters, API) depend on it, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from .events import Event, Logging


class StorageProvider(str, Enum):
    """Where a book's file is stored."""

    S3 = "s3"
    LOCAL = "local"


@dataclass(frozen=True)
class StorageLocation:
    """Value object: identifies a stored file without saying how to fetch it.

    `key` is the provider-specific identifier (an S3 object key, or a path
    relative to the local storage root). Turning it into a downloadable URL
    is the job of a storage adapter in the infrastructure layer.
    """

    provider: StorageProvider
    key: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("Storage key must not be empty")


@dataclass
class Book:
    name: str
    location: StorageLocation
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Book name must not be empty")


@dataclass(eq=False)
class User:
    name: str
    username: str
    # Only a hash is ever stored; hashing itself is done by the service layer.
    password_hash: str = field(repr=False)
    books: list[Book] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    # Events raised by this aggregate, waiting to be handled.
    events: list[Event] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("User name must not be empty")
        if not self.username.strip():
            raise ValueError("Username must not be empty")
        if not self.password_hash:
            raise ValueError("Password hash must not be empty")

    # Entity identity: two User objects are the same user if their ids match.
    # Hashing by id lets users be tracked in sets (e.g. the repository's `seen`).
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def add_book(self, book: Book) -> None:
        if any(b.id == book.id for b in self.books):
            raise ValueError(f"Book {book.id} already belongs to this user")
        self.books.append(book)
        self.events.append(
            Logging(message=f"Book {book.id} ({book.name!r}) added to user {self.id}")
        )

    def remove_book(self, book_id: UUID) -> None:
        remaining = [b for b in self.books if b.id != book_id]
        if len(remaining) == len(self.books):
            raise ValueError(f"Book {book_id} not found for this user")
        self.books = remaining
        self.events.append(Logging(message=f"Book {book_id} removed from user {self.id}"))
