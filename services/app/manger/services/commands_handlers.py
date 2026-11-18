"""One handler per command. Handlers depend only on the abstract unit of work,
so they run the same against Postgres or the in-memory fake.

`upload_book` writes a local file through `LocalStorage`. S3 is not
implemented and raises `StorageNotFound`.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from manger.domain import Book, StorageLocation, StorageProvider, User, commands
from manger.infra.db.uow import AbstractUnitOfWork
from manger.infra.storage import AbstractStorage, LocalStorage


class UsernameTaken(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class UnknownUser(Exception):
    pass


class UnknownBook(Exception):
    pass


class UnsupportedFileType(Exception):
    pass


class StorageNotFound(Exception):
    """The requested storage provider has no implementation."""


_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}
_ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT_PARAMS)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    _, salt_hex, digest_hex = password_hash.split("$")
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT_PARAMS
    )
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def sign_up(command: commands.SignUp, uow: AbstractUnitOfWork) -> UUID:
    """Register a new user and return their id."""
    if not command.password:
        raise ValueError("Password must not be empty")

    with uow:
        if uow.users.get_by_username(command.username) is not None:
            raise UsernameTaken(f"Username {command.username!r} is already taken")

        user = User(
            name=command.name,
            username=command.username,
            password_hash=hash_password(command.password),
        )
        uow.users.add(user)
        # Read before commit: committed objects expire in the SQLAlchemy UoW.
        user_id = user.id
        uow.commit()
    return user_id


def sign_in(command: commands.SignIn, uow: AbstractUnitOfWork) -> UUID:
    """Return the id of the user matching the credentials."""
    with uow:
        user = uow.users.get_by_username(command.username)
        if user is None or not verify_password(command.password, user.password_hash):
            raise InvalidCredentials("Invalid username or password")
        return user.id


def add_book(command: commands.AddBook, uow: AbstractUnitOfWork) -> UUID:
    """Add a book to the user's library and return the book's id."""
    with uow:
        user = uow.users.get(command.user_id)
        if user is None:
            raise UnknownUser(f"User {command.user_id} not found")

        book = Book(
            name=command.name,
            location=StorageLocation(command.storage_provider, command.storage_key),
        )
        user.add_book(book)
        book_id = book.id
        uow.commit()
    return book_id


def _stored_filename(filename: str) -> str:
    """Keep only the file's own name, and only for PDF or Word."""
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("File name must not be empty")
    if Path(name).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise UnsupportedFileType(
            "Only PDF and Word files are supported (.pdf, .doc, .docx)"
        )
    return name


def upload_book(
    command: commands.UploadBook,
    uow: AbstractUnitOfWork,
    storage: AbstractStorage | None = None,
) -> UUID:
    """Save an uploaded PDF or Word file and add it to the user's library.

    Only `local` is implemented. `s3` raises `StorageNotFound`.
    """
    if command.storage_provider is StorageProvider.S3:
        raise StorageNotFound("S3 storage not found")

    filename = _stored_filename(command.filename)
    if not command.content:
        raise ValueError("Uploaded file is empty")
    if not command.name.strip():
        raise ValueError("Book name must not be empty")

    storage = storage or LocalStorage()
    book_id = uuid4()
    key = f"{command.user_id}/{book_id}/{filename}"

    with uow:
        user = uow.users.get(command.user_id)
        if user is None:
            raise UnknownUser(f"User {command.user_id} not found")

        storage.save(key, command.content)
        book = Book(
            name=command.name,
            location=StorageLocation(command.storage_provider, key),
            id=book_id,
        )
        user.add_book(book)
        uow.commit()
    return book_id


def remove_book(command: commands.RemoveBook, uow: AbstractUnitOfWork) -> None:
    with uow:
        user = uow.users.get(command.user_id)
        if user is None:
            raise UnknownUser(f"User {command.user_id} not found")
        if not any(b.id == command.book_id for b in user.books):
            raise UnknownBook(f"Book {command.book_id} not found for this user")

        user.remove_book(command.book_id)
        uow.commit()


COMMAND_HANDLERS: dict[type[commands.Command], Callable[[Any, AbstractUnitOfWork], Any]] = {
    commands.SignUp: sign_up,
    commands.SignIn: sign_in,
    commands.AddBook: add_book,
    commands.RemoveBook: remove_book,
    commands.UploadBook: upload_book,
}
