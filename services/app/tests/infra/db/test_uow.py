from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from manger.domain import Book, StorageLocation, StorageProvider, User
from manger.infra.db import mapper
from manger.infra.db.uow import DEFAULT_ENGINE, SqlAlchemyUnitOfWork


@pytest.fixture(scope="module", autouse=True)
def database() -> None:
    mapper.start_mappers()
    try:
        mapper.init_db(DEFAULT_ENGINE)
    except OperationalError:
        pytest.skip("Postgres is not reachable (start db/lunch/docker-compose.yml)")


def test_add_user_then_add_book_to_him_in_a_later_transaction():
    # Committed objects are expired and detached once the unit of work closes,
    # so ids are captured up front rather than read from them afterwards.
    user = User(name="Ahmed", username=f"ahmed-{uuid4()}", password_hash="hash")
    user_id = user.id

    with SqlAlchemyUnitOfWork() as uow:
        uow.users.add(user)
        uow.commit()

    location = StorageLocation(StorageProvider.LOCAL, "books/clean-arch.pdf")
    book = Book(name="Clean Architecture", location=location)
    book_id = book.id

    with SqlAlchemyUnitOfWork() as uow:
        stored_user = uow.users.get(user_id)
        assert stored_user is not None
        assert stored_user.books == []

        stored_user.add_book(book)
        uow.commit()

    with SqlAlchemyUnitOfWork() as uow:
        reloaded = uow.users.get(user_id)
        assert reloaded is not None
        assert reloaded.name == "Ahmed"
        assert [b.id for b in reloaded.books] == [book_id]
        assert reloaded.books[0].name == "Clean Architecture"
        assert reloaded.books[0].location == location

        owner = uow.users.get_by_book_id(book_id)
        assert owner is not None
        assert owner.id == user_id
