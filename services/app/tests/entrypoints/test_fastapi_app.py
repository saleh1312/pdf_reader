import logging
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from manger.entrypoints.fastapi_app import create_app
from manger.infra.db.uow import AbstractUnitOfWork
from manger.infra.storage import LocalStorage


@pytest.fixture
def client(uow: AbstractUnitOfWork, tmp_path) -> TestClient:
    return TestClient(
        create_app(uow_factory=lambda: uow, storage=LocalStorage(tmp_path))
    )


@pytest.fixture
def username() -> str:
    return f"ahmed-{uuid4().hex[:8]}"


def sign_up(client: TestClient, username: str) -> str:
    response = client.post(
        "/sign_up", json={"name": "Ahmed", "username": username, "password": "secret"}
    )
    assert response.status_code == 201
    return response.json()["user_id"]


def add_book(client: TestClient, user_id: str, **overrides):
    body = {"name": "Clean Architecture", "storage_provider": "local", "storage_key": "a.pdf"}
    return client.post(f"/users/{user_id}/books", json=body | overrides)


def test_sign_up_then_sign_in_returns_the_same_user(client: TestClient, username: str):
    user_id = sign_up(client, username)

    response = client.post("/sign_in", json={"username": username, "password": "secret"})

    assert response.status_code == 200
    assert response.json() == {"user_id": user_id}


def test_sign_up_with_taken_username_is_409(client: TestClient, username: str):
    sign_up(client, username)

    response = client.post(
        "/sign_up", json={"name": "Other", "username": username, "password": "x"}
    )

    assert response.status_code == 409


def test_sign_in_with_wrong_password_is_401(client: TestClient, username: str):
    sign_up(client, username)

    response = client.post("/sign_in", json={"username": username, "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_missing_fields_are_422(client: TestClient):
    response = client.post("/sign_up", json={"name": "Ahmed"})

    assert response.status_code == 422
    missing = {error["loc"][-1] for error in response.json()["detail"]}
    assert missing == {"username", "password"}


def test_non_json_body_is_422(client: TestClient):
    assert client.post("/sign_in", content="hello").status_code == 422


def test_blank_name_rejected_by_the_domain_is_400(client: TestClient, username: str):
    response = client.post(
        "/sign_up", json={"name": "  ", "username": username, "password": "secret"}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "User name must not be empty"}


def test_add_book_then_remove_it(
    client: TestClient, username: str, caplog: pytest.LogCaptureFixture
):
    user_id = sign_up(client, username)

    with caplog.at_level(logging.INFO):
        added = add_book(client, user_id)
        book_id = added.json()["book_id"]
        removed = client.delete(f"/users/{user_id}/books/{book_id}")

    assert added.status_code == 201
    assert removed.status_code == 204
    # The domain events went through the message bus to the logging handler.
    assert f"Book {book_id} ('Clean Architecture') added to user {user_id}" in caplog.text
    assert f"Book {book_id} removed from user {user_id}" in caplog.text


def test_removing_a_book_twice_is_404(client: TestClient, username: str):
    user_id = sign_up(client, username)
    book_id = add_book(client, user_id).json()["book_id"]
    client.delete(f"/users/{user_id}/books/{book_id}")

    response = client.delete(f"/users/{user_id}/books/{book_id}")

    assert response.status_code == 404


def test_add_book_for_unknown_user_is_404(client: TestClient):
    assert add_book(client, str(uuid4())).status_code == 404


def test_add_book_with_unknown_storage_provider_is_422(client: TestClient, username: str):
    user_id = sign_up(client, username)

    assert add_book(client, user_id, storage_provider="ftp").status_code == 422


def test_invalid_user_id_in_path_is_422(client: TestClient):
    assert add_book(client, "not-a-uuid").status_code == 422


def test_upload_stores_the_file(
    client: TestClient,
    username: str,
    tmp_path,
    uow: AbstractUnitOfWork,
    caplog: pytest.LogCaptureFixture,
):
    user_id = sign_up(client, username)
    content = b"%PDF-1.4 notes"

    with caplog.at_level(logging.INFO):
        uploaded = client.post(
            f"/users/{user_id}/books/upload",
            files={"file": ("notes.pdf", content, "application/pdf")},
            data={"name": "Notes", "storage_provider": "local"},
        )

    assert uploaded.status_code == 201
    book_id = uploaded.json()["book_id"]
    assert f"Book {book_id} ('Notes') added to user {user_id}" in caplog.text

    saved = list(tmp_path.rglob("notes.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == content

    with uow:
        book = uow.users.get(UUID(user_id)).books[0]
        assert str(book.id) == book_id
        assert book.name == "Notes"
        assert book.location.key.endswith("/notes.pdf")


def test_upload_without_a_name_uses_the_file_name(
    client: TestClient, username: str, uow: AbstractUnitOfWork
):
    user_id = sign_up(client, username)

    uploaded = client.post(
        f"/users/{user_id}/books/upload",
        files={"file": ("My Chapter.docx", b"word", "application/octet-stream")},
        data={"storage_provider": "local"},
    )

    assert uploaded.status_code == 201
    with uow:
        book = uow.users.get(UUID(user_id)).books[0]
        assert str(book.id) == uploaded.json()["book_id"]
        assert book.name == "My Chapter"
        assert book.location.key.endswith("/My Chapter.docx")


def test_upload_of_unsupported_type_is_415(
    client: TestClient, username: str, tmp_path, uow: AbstractUnitOfWork
):
    user_id = sign_up(client, username)

    response = client.post(
        f"/users/{user_id}/books/upload",
        files={"file": ("pic.png", b"png", "image/png")},
        data={"storage_provider": "local"},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == (
        "Only PDF and Word files are supported (.pdf, .doc, .docx)"
    )
    with uow:
        assert uow.users.get(UUID(user_id)).books == []
    assert list(tmp_path.rglob("*")) == []


def test_upload_of_an_empty_file_is_400(client: TestClient, username: str):
    user_id = sign_up(client, username)

    response = client.post(
        f"/users/{user_id}/books/upload",
        files={"file": ("notes.pdf", b"", "application/pdf")},
        data={"storage_provider": "local"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty"}


def test_upload_for_unknown_user_is_404(client: TestClient):
    response = client.post(
        f"/users/{uuid4()}/books/upload",
        files={"file": ("notes.pdf", b"%PDF", "application/pdf")},
        data={"storage_provider": "local"},
    )

    assert response.status_code == 404


def test_upload_to_s3_is_not_found(client: TestClient, tmp_path):
    response = client.post(
        f"/users/{uuid4()}/books/upload",
        files={"file": ("notes.pdf", b"%PDF", "application/pdf")},
        data={"storage_provider": "s3", "name": "Notes"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "S3 storage not found"}
    assert list(tmp_path.rglob("*")) == []
