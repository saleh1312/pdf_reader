"""Requests for the system to do something; each has exactly one handler."""

from dataclasses import dataclass, field
from uuid import UUID

from .domain import StorageProvider


@dataclass(frozen=True)
class Command:
    pass


# Passwords are excluded from repr so commands can be logged safely.


@dataclass(frozen=True)
class SignUp(Command):
    name: str
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class SignIn(Command):
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class AddBook(Command):
    user_id: UUID
    name: str
    storage_provider: StorageProvider
    storage_key: str


@dataclass(frozen=True)
class RemoveBook(Command):
    user_id: UUID
    book_id: UUID


@dataclass(frozen=True)
class UploadBook(Command):
    """Store an uploaded PDF or Word file and add it to the user's library."""

    user_id: UUID
    name: str
    filename: str
    storage_provider: StorageProvider
    content: bytes = field(repr=False)
