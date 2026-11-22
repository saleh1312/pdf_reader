"""Read models.

Queries go through the user unit of work's session as SQL, not through a
repository. The user unit of work is the connection to the app database.
"""

from uuid import UUID

from sqlalchemy import text

from manger.services.user_uow import AbstractUserUnitOfWork


def get_book(user_id: UUID, book_id: UUID, uow: AbstractUserUnitOfWork) -> dict | None:
    """Return the book's storage location, or None when this user does not own it."""
    with uow:
        row = uow.db.execute(
            text(
                """
                SELECT name, storage_provider, storage_key, is_parsed
                FROM books
                WHERE id = :book_id AND user_id = :user_id
                """
            ),
            {"book_id": book_id, "user_id": user_id},
        ).mappings().first()
    if row is None:
        return None
    return {
        "name": row["name"],
        "storage_provider": row["storage_provider"],
        "storage_key": row["storage_key"],
        "is_parsed": bool(row["is_parsed"]),
    }
