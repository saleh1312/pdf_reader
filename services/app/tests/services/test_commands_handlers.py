from uuid import uuid4

import pytest

from manger.domain import commands
from manger.domain.commands import SignIn, SignUp
from manger.infra.db.uow import AbstractUnitOfWork
from manger.services import commands_handlers as handlers


@pytest.fixture
def username() -> str:
    # Unique per test: with --real, users from earlier tests and runs remain.
    return f"ahmed-{uuid4().hex[:8]}"


def test_every_command_has_a_handler():
    assert set(commands.Command.__subclasses__()) <= set(handlers.COMMAND_HANDLERS)


def test_sign_up_stores_user(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with uow:
        user = uow.users.get(user_id)
        assert user is not None
        assert user.name == "Ahmed"
        assert user.username == username


def test_sign_up_does_not_store_plain_password(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with uow:
        assert "secret" not in uow.users.get(user_id).password_hash


def test_sign_up_rejects_taken_username(uow: AbstractUnitOfWork, username: str):
    handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(handlers.UsernameTaken):
        handlers.sign_up(SignUp("Other", username, "other"), uow)

    with uow:
        assert uow.users.get_by_username(username).name == "Ahmed"


def test_sign_up_rejects_empty_password(uow: AbstractUnitOfWork, username: str):
    with pytest.raises(ValueError, match="Password"):
        handlers.sign_up(SignUp("Ahmed", username, ""), uow)

    with uow:
        assert uow.users.get_by_username(username) is None


def test_sign_in_returns_user_id_for_correct_credentials(
    uow: AbstractUnitOfWork, username: str
):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    assert handlers.sign_in(SignIn(username, "secret"), uow) == user_id


def test_sign_in_rejects_wrong_password(uow: AbstractUnitOfWork, username: str):
    handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(handlers.InvalidCredentials):
        handlers.sign_in(SignIn(username, "wrong"), uow)


def test_sign_in_rejects_unknown_username(uow: AbstractUnitOfWork, username: str):
    with pytest.raises(handlers.InvalidCredentials):
        handlers.sign_in(SignIn(username, "secret"), uow)


def test_commands_do_not_show_password_in_repr():
    assert "secret" not in repr(SignUp("Ahmed", "ahmed", "secret"))
    assert "secret" not in repr(SignIn("ahmed", "secret"))
