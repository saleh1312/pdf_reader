"""One handler per command. The session unit of work stores the chat.
The book's path is read from the app database through the view.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from manger.domain import ContentType, Message, Session, Turn, commands
from manger.infra.parsed_book import ParsedBookNotFound, load_book_paragraphs
from manger.services.ai_provider import AiProvider
from manger.services.session_uow import AbstractSessionUnitOfWork
from manger.services.user_uow import AbstractUserUnitOfWork
from manger.view import get_book


class UnknownBook(Exception):
    pass


class BookNotParsed(Exception):
    pass


class UnsupportedStorage(Exception):
    pass


class UnknownSession(Exception):
    pass


# Sent with the book text. It is not stored, so older chats follow it too.
REPLY_PROMPT = (
    "Answer in plain text only, in the same language as the question. "
    "Keep the reply short or medium, a few simple sentences. "
    "Do not use markdown, bullets, headings, stars, numbering, or symbols.\n\n"
)


def _user_db() -> AbstractUserUnitOfWork:
    from manger.infra.db.user.uow import UserDbUnitOfWork

    return UserDbUnitOfWork()


def create_session(
    command: commands.CreateSession,
    uow: AbstractSessionUnitOfWork,
    *,
    lookup_book: Callable[..., dict | None] | None = None,
    load_paragraphs: Callable[..., str] | None = None,
    user_uow: AbstractUserUnitOfWork | None = None,
    storage_root: Path | None = None,
) -> dict:
    """Open a session whose system message is the book's paragraphs.

    Returns ``{"status": "success", "session_id": ...}`` once that message is stored.
    """
    lookup = lookup_book or get_book
    load = load_paragraphs or (
        lambda key, name: load_book_paragraphs(key, name, storage_root)
    )
    book = lookup(command.user_id, command.book_id, user_uow or _user_db())
    if book is None:
        raise UnknownBook(f"Book {command.book_id} not found for this user")
    if not book["is_parsed"]:
        raise BookNotParsed(f"Book {command.book_id} is not parsed yet")
    if book["storage_provider"] not in (None, "local"):
        raise UnsupportedStorage(
            f"{book['storage_provider']} storage is not available"
        )

    try:
        content = load(book["storage_key"], book["name"])
    except ParsedBookNotFound as exc:
        raise BookNotParsed(str(exc)) from exc

    session = Session(user_id=command.user_id)
    session.add_book_context(command.book_id, content)
    session_id = session.id
    with uow:
        uow.sessions.add(session)
        uow.commit()
    return {"status": "success", "session_id": session_id}


def infer(
    command: commands.Infer,
    uow: AbstractSessionUnitOfWork,
    *,
    provider: AiProvider | None = None,
) -> str:
    """Append the user message to the session history, ask the model, and store both."""
    text = command.message.strip()
    if not text:
        raise ValueError("Message must not be empty")

    model = provider or _provider()
    with uow:
        session = uow.sessions.get(command.session_id)
        if session is None:
            raise UnknownSession(f"Session {command.session_id} not found")
        asked_at = datetime.now(timezone.utc)
        user_message = Message(
            date=asked_at,
            turn=Turn.USER,
            content=text,
            content_type=ContentType.TEXT,
        )
        reply = model.send(_with_reply_prompt([*session.messages, user_message]))
        session.add_message(user_message)
        session.add_message(
            Message(
                date=asked_at + timedelta(milliseconds=1),
                turn=Turn.AI,
                content=reply,
                content_type=ContentType.TEXT,
            )
        )
        uow.commit()
    return reply


def _with_reply_prompt(messages: list[Message]) -> list[Message]:
    """Ask for a plain, short or medium reply without changing stored history."""
    for index, message in enumerate(messages):
        if message.turn is Turn.SYSTEM:
            prompted = list(messages)
            prompted[index] = replace(message, content=REPLY_PROMPT + message.content)
            return prompted
    return messages


def _provider() -> AiProvider:
    from manger.infra.ai_providers.openai import OpenAiProvider

    return OpenAiProvider()


COMMAND_HANDLERS: dict[
    type[commands.Command], Callable[[Any, AbstractSessionUnitOfWork], Any]
] = {
    commands.CreateSession: create_session,
    commands.Infer: infer,
}
