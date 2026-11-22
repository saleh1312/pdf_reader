from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from manger.domain import User
from manger.infra.db import mapper
from manger.services.repository import AbstractUserRepository


class SqlAlchemyUserRepository(AbstractUserRepository):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def _add(self, user: User) -> None:
        self.session.add(user)

    def _get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def _get_by_book_id(self, book_id: UUID) -> User | None:
        stmt = (
            select(User)
            .join(mapper.books, mapper.books.c.user_id == mapper.users.c.id)
            .where(mapper.books.c.id == book_id)
        )
        return self.session.scalars(stmt).first()

    def _get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(mapper.users.c.username == username)
        return self.session.scalars(stmt).first()


class FakeUserRepository(AbstractUserRepository):
    """In-memory repository for tests; never touches a database."""

    def __init__(self, users: list[User] | None = None):
        super().__init__()
        self._users: dict[UUID, User] = {u.id: u for u in users or []}

    def _add(self, user: User) -> None:
        self._users[user.id] = user

    def _get(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    def _get_by_book_id(self, book_id: UUID) -> User | None:
        return next(
            (u for u in self._users.values() if any(b.id == book_id for b in u.books)),
            None,
        )

    def _get_by_username(self, username: str) -> User | None:
        return next(
            (u for u in self._users.values() if u.username == username), None
        )


if __name__ == "__main__":
    from uuid import uuid4

    from manger.infra.db.uow import DEFAULT_ENGINE, SqlAlchemyUnitOfWork
    from manger.domain import Book
    from manger.infra.db.mapper import init_db, start_mappers
    from manger.domain import StorageLocation, StorageProvider

    start_mappers()
    init_db(DEFAULT_ENGINE)


    with SqlAlchemyUnitOfWork() as uow:
        user = User(name="John Doe", username=f"john-{uuid4()}", password_hash="not-a-real-hash")
        user.add_book(
            Book(name="Book 1", location=StorageLocation(provider=StorageProvider.LOCAL, key="book1.pdf")),
            b"%PDF",
        )
        uow.users.add(user)
        uow.commit()
        print(uow.users.get_by_book_id(user.books[0].id))