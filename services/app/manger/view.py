"""Read models for the API.

Queries go through the unit of work's session as SQL, not through the
repositories, so reading a user does not load the domain model.
"""

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


def _as_dict(row) -> dict:
    data = dict(row)
    provider = data.get("storage_provider")
    if isinstance(provider, StorageProvider):
        data["storage_provider"] = provider.value
    return data
