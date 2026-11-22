from pathlib import Path
from uuid import UUID, uuid4

import pytest

from manger.domain import StorageProvider, commands
from manger.domain.commands import AddBook, RemoveBook, SignIn, SignUp
from manger.services.unit_of_work import AbstractUnitOfWork
from manger.infra.storage import LocalStorage
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


def add_book(uow: AbstractUnitOfWork, user_id) -> UUID:
    return handlers.add_book(
        AddBook(user_id, "Clean Architecture", "a.pdf", StorageProvider.LOCAL, b"%PDF"),
        uow,
    )


def test_add_book_stores_it_on_the_user(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    book_id = add_book(uow, user_id)

    with uow:
        user = uow.users.get(user_id)
        assert [b.id for b in user.books] == [book_id]
        assert user.books[0].location.provider is StorageProvider.LOCAL
        assert user.books[0].location.key.endswith("/a.pdf")


def test_add_book_for_unknown_user_raises(uow: AbstractUnitOfWork):
    with pytest.raises(handlers.UnknownUser):
        add_book(uow, uuid4())


def test_remove_book_deletes_it(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)
    book_id = add_book(uow, user_id)

    handlers.remove_book(RemoveBook(user_id, book_id), uow)

    with uow:
        assert uow.users.get(user_id).books == []


def test_remove_unknown_book_raises(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(handlers.UnknownBook):
        handlers.remove_book(RemoveBook(user_id, uuid4()), uow)


def test_remove_book_for_unknown_user_raises(uow: AbstractUnitOfWork):
    with pytest.raises(handlers.UnknownUser):
        handlers.remove_book(RemoveBook(uuid4(), uuid4()), uow)


def test_commands_do_not_show_password_in_repr():
    assert "secret" not in repr(SignUp("Ahmed", "ahmed", "secret"))
    assert "secret" not in repr(SignIn("ahmed", "secret"))
    assert "pdf-bytes" not in repr(
        AddBook(uuid4(), "Notes", "notes.pdf", StorageProvider.LOCAL, b"pdf-bytes")
    )


@pytest.mark.parametrize("filename", ["notes.pdf", "notes.PDF", "chapter.docx", "draft.doc"])
def test_add_book_records_pdf_and_word_files(
    uow: AbstractUnitOfWork, username: str, filename: str
):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)
    content = b"%PDF-1.4 notes" if filename.lower().endswith(".pdf") else b"word-bytes"

    book_id = handlers.add_book(
        AddBook(user_id, "Notes", filename, StorageProvider.LOCAL, content),
        uow,
    )

    with uow:
        book = uow.users.get(user_id).books[0]
        assert book.id == book_id
        assert book.name == "Notes"
        assert book.location.provider is StorageProvider.LOCAL
        assert book.location.key.endswith(f"/{Path(filename).name}")


def test_add_book_rejects_other_file_types(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(handlers.UnsupportedFileType):
        handlers.add_book(
            AddBook(user_id, "Pic", "pic.png", StorageProvider.LOCAL, b"png"),
            uow,
        )

    with uow:
        assert uow.users.get(user_id).books == []


def test_add_book_rejects_an_empty_file(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(ValueError, match="empty"):
        handlers.add_book(
            AddBook(user_id, "Notes", "notes.pdf", StorageProvider.LOCAL, b""),
            uow,
        )

    with uow:
        assert uow.users.get(user_id).books == []


def test_add_book_for_unknown_user_raises_before_saving(uow: AbstractUnitOfWork):
    with pytest.raises(handlers.UnknownUser):
        handlers.add_book(
            AddBook(uuid4(), "Notes", "notes.pdf", StorageProvider.LOCAL, b"%PDF"),
            uow,
        )


def test_add_book_keeps_only_the_file_name(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    handlers.add_book(
        AddBook(user_id, "Notes", "../../secret.pdf", StorageProvider.LOCAL, b"%PDF"),
        uow,
    )

    with uow:
        key = uow.users.get(user_id).books[0].location.key
    assert key.endswith("/secret.pdf")
    assert ".." not in key


def test_add_book_s3_is_not_found(uow: AbstractUnitOfWork, username: str):
    user_id = handlers.sign_up(SignUp("Ahmed", username, "secret"), uow)

    with pytest.raises(handlers.StorageNotFound, match="not found"):
        handlers.add_book(
            AddBook(user_id, "Notes", "notes.pdf", StorageProvider.S3, b"%PDF"),
            uow,
        )

    with uow:
        assert uow.users.get(user_id).books == []


def test_local_storage_prefers_an_absolute_path_from_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_STORAGE_PATH=books\n", encoding="utf-8")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "from-env"))

    storage = LocalStorage(env_file=env_file)

    assert storage.root == tmp_path / "from-env"


def test_local_storage_reads_the_directory_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_STORAGE_PATH", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_STORAGE_PATH=books\n", encoding="utf-8")

    storage = LocalStorage(env_file=env_file)
    storage.save("notes.pdf", b"%PDF")

    assert storage.root == tmp_path / "books"
    assert (tmp_path / "books" / "notes.pdf").read_bytes() == b"%PDF"


def test_local_storage_rejects_a_key_outside_its_root(tmp_path):
    storage = LocalStorage(tmp_path / "books")

    with pytest.raises(ValueError, match="escapes"):
        storage.save("../outside.pdf", b"nope")

    assert not (tmp_path / "outside.pdf").exists()
