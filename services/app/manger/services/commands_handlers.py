"""One handler per command. Handlers depend only on the abstract unit of work,
so they run the same against Postgres or the in-memory fake.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from typing import Any
from uuid import UUID

from manger.domain import User, commands
from manger.infra.db.uow import AbstractUnitOfWork


class UsernameTaken(Exception):
    pass


class InvalidCredentials(Exception):
    pass


_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}


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
            raise UsernameTaken(command.username)

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
            raise InvalidCredentials()
        return user.id


COMMAND_HANDLERS: dict[type[commands.Command], Callable[[Any, AbstractUnitOfWork], Any]] = {
    commands.SignUp: sign_up,
    commands.SignIn: sign_in,
}
