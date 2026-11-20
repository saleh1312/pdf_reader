from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from manger.domain import Book, StorageLocation, StorageProvider, User
from manger.domain.events import Logging, ParseBook, StoreFile


@pytest.fixture
def location() -> StorageLocation:
    return StorageLocation(StorageProvider.S3, "books/clean-arch.pdf")


@pytest.fixture
def book(location: StorageLocation) -> Book:
    return Book("Clean Architecture", location)


def make_user(name: str, **kwargs) -> User:
    kwargs.setdefault("username", f"user-{uuid4()}")
    kwargs.setdefault("password_hash", "hash")
    return User(name, **kwargs)


# --- StorageProvider -------------------------------------------------------


def test_storage_provider_values():
    assert StorageProvider.S3.value == "s3"
    assert StorageProvider.LOCAL.value == "local"


def test_storage_provider_from_string():
    assert StorageProvider("s3") is StorageProvider.S3
    assert StorageProvider("local") is StorageProvider.LOCAL


def test_storage_provider_rejects_unknown_value():
    with pytest.raises(ValueError):
        StorageProvider("gcs")


# --- StorageLocation -------------------------------------------------------


def test_storage_location_holds_provider_and_key(location: StorageLocation):
    assert location.provider is StorageProvider.S3
    assert location.key == "books/clean-arch.pdf"


@pytest.mark.parametrize("key", ["", "   "])
def test_storage_location_rejects_blank_key(key: str):
    with pytest.raises(ValueError, match="Storage key"):
        StorageLocation(StorageProvider.LOCAL, key)


def test_storage_location_is_immutable(location: StorageLocation):
    with pytest.raises(FrozenInstanceError):
        location.key = "other.pdf"  # type: ignore[misc]


def test_storage_locations_with_same_values_are_equal():
    a = StorageLocation(StorageProvider.LOCAL, "a.pdf")
    b = StorageLocation(StorageProvider.LOCAL, "a.pdf")
    assert a == b
    assert hash(a) == hash(b)


# --- Book ------------------------------------------------------------------


def test_book_gets_generated_uuid(location: StorageLocation):
    b1 = Book("A", location)
    b2 = Book("B", location)
    assert isinstance(b1.id, UUID)
    assert b1.id != b2.id


def test_book_keeps_explicit_id(location: StorageLocation):
    book_id = uuid4()
    assert Book("A", location, id=book_id).id == book_id


@pytest.mark.parametrize("name", ["", "   "])
def test_book_rejects_blank_name(name: str, location: StorageLocation):
    with pytest.raises(ValueError, match="Book name"):
        Book(name, location)


# --- User ------------------------------------------------------------------


def test_user_starts_with_no_books():
    assert make_user("Ahmed").books == []


def test_users_do_not_share_books_list(book: Book):
    u1 = make_user("A")
    u2 = make_user("B")
    u1.add_book(book, b"file")
    assert u2.books == []


def test_user_gets_generated_uuid():
    assert make_user("A").id != make_user("B").id


@pytest.mark.parametrize("name", ["", "   "])
def test_user_rejects_blank_name(name: str):
    with pytest.raises(ValueError, match="User name"):
        make_user(name)


@pytest.mark.parametrize("username", ["", "   "])
def test_user_rejects_blank_username(username: str):
    with pytest.raises(ValueError, match="Username"):
        make_user("Ahmed", username=username)


def test_user_rejects_empty_password_hash():
    with pytest.raises(ValueError, match="Password hash"):
        make_user("Ahmed", password_hash="")


def test_users_with_same_id_are_equal():
    user_id = uuid4()
    a = make_user("A", id=user_id)
    b = make_user("Renamed", id=user_id)
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_users_with_different_ids_are_not_equal():
    assert make_user("Same") != make_user("Same")


def test_add_book(book: Book):
    user = make_user("Ahmed")
    user.add_book(book, b"file")
    assert user.books == [book]


def test_add_same_book_twice_raises(book: Book):
    user = make_user("Ahmed")
    user.add_book(book, b"file")
    with pytest.raises(ValueError, match="already belongs"):
        user.add_book(book, b"file")
    assert len(user.books) == 1


def test_remove_book(book: Book, location: StorageLocation):
    other = Book("Other", location)
    user = make_user("Ahmed", books=[book, other])
    user.remove_book(book.id)
    assert user.books == [other]


def test_new_user_has_no_events():
    assert make_user("Ahmed").events == []


def test_add_book_records_store_and_parse_events(book: Book):
    user = make_user("Ahmed")
    user.add_book(book, b"file")
    assert user.events == [
        StoreFile(user.id, book.id, book.location.provider.value, book.location.key, b"file"),
        ParseBook(user.id, book.id, book.name, book.location.provider.value, book.location.key),
    ]


def test_add_book_rejects_an_empty_file(book: Book):
    user = make_user("Ahmed")
    with pytest.raises(ValueError, match="empty"):
        user.add_book(book, b"")
    assert user.books == []
    assert user.events == []


def test_remove_book_records_logging_event(book: Book):
    user = make_user("Ahmed", books=[book])
    user.remove_book(book.id)
    assert user.events == [Logging(f"Book {book.id} removed from user {user.id}")]


def test_failed_book_changes_record_no_events(book: Book):
    user = make_user("Ahmed", books=[book])
    with pytest.raises(ValueError):
        user.add_book(book, b"file")
    with pytest.raises(ValueError):
        user.remove_book(uuid4())
    assert user.events == []


def test_remove_missing_book_raises(book: Book):
    user = make_user("Ahmed", books=[book])
    with pytest.raises(ValueError, match="not found"):
        user.remove_book(uuid4())
    assert user.books == [book]
