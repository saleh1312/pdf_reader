"""Requests for the system to do something; each has exactly one handler."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Command:
    pass


@dataclass(frozen=True)
class CreateSession(Command):
    """Open a chat session on a book that has already been parsed."""

    user_id: UUID
    book_id: UUID


@dataclass(frozen=True)
class Infer(Command):
    """Answer one user message from a session's history."""

    session_id: UUID
    message: str
