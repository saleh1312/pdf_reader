"""Read models for the API.

Queries go through the unit of work's session as SQL, not through the
repositories, so reading a user does not load the domain model.
"""

from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from manger.domain import StorageProvider
from manger.services.unit_of_work import AbstractUnitOfWork


def get_user_data(user_id: UUID, uow: AbstractUnitOfWork) -> dict | None:
    """Return the user's id, name and username, or None if they do not exist."""
    with uow:
        row = uow.session.execute(
            text(
                """
                SELECT id AS user_id, name, username
                FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        return _as_dict(row) if row is not None else None


def get_books(user_id: UUID, uow: AbstractUnitOfWork) -> list[dict]:
    """Return the user's books, ordered by name."""
    with uow:
        rows = uow.session.execute(
            text(
                """
                SELECT id AS book_id, name, storage_provider, storage_key
                FROM books
                WHERE user_id = :user_id
                ORDER BY name, id
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [_as_dict(row) for row in rows]


def get_book_status(
    user_id: UUID, book_id: UUID, uow: AbstractUnitOfWork
) -> tuple[bool, dict | None]:
    """Return whether the user exists, and the book when they own it."""
    with uow:
        user = uow.users.get(user_id)
        if user is None:
            return False, None
        for book in user.books:
            if book.id == book_id:
                return True, {
                    "book_id": book.id,
                    "name": book.name,
                    "is_parsed": bool(book.is_parsed),
                    "viewable": Path(book.location.key).suffix.lower() == ".pdf",
                    "storage_provider": book.location.provider.value,
                    "storage_key": book.location.key,
                }
        return True, None


def _as_dict(row) -> dict:
    data = dict(row)
    provider = data.get("storage_provider")
    if isinstance(provider, StorageProvider):
        data["storage_provider"] = provider.value
    return data
