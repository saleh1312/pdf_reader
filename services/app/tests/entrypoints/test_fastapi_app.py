import json
import logging
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from manger.entrypoints.fastapi_app import create_app
from manger.services.unit_of_work import AbstractUnitOfWork
from manger.infra.mq import PARSE_QUEUE
from manger.infra.storage import LocalStorage


class RecordingPublisher:
    def __init__(self):
        self.messages: list[tuple[str, bytes]] = []

    def publish(self, queue: str, body: bytes) -> None:
        self.messages.append((queue, body))


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def client(uow: AbstractUnitOfWork, tmp_path, publisher: RecordingPublisher) -> TestClient:
    return TestClient(
        create_app(
            uow_factory=lambda: uow,
            storage=LocalStorage(tmp_path),
            publisher=publisher,
        )
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
    data = {"name": "Clean Architecture", "storage_provider": "local"}
    data.update(overrides)
    filename = data.pop("filename", "a.pdf")
    content = data.pop("content", b"%PDF-1.4")
    return client.post(
        f"/users/{user_id}/books",
        data=data,
        files={"file": (filename, content, "application/pdf")},
    )


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
    client: TestClient,
    username: str,
    tmp_path,
    publisher: RecordingPublisher,
    caplog: pytest.LogCaptureFixture,
):
    user_id = sign_up(client, username)

    with caplog.at_level(logging.INFO):
        added = add_book(client, user_id, content=b"%PDF-1.4 notes")
        book_id = added.json()["book_id"]
        removed = client.delete(f"/users/{user_id}/books/{book_id}")

    assert added.status_code == 201
    assert removed.status_code == 204
    assert f"Book {book_id} removed from user {user_id}" in caplog.text
    saved = list(tmp_path.rglob("a.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"%PDF-1.4 notes"
    assert len(publisher.messages) == 1
    queue, body = publisher.messages[0]
    assert queue == PARSE_QUEUE
    message = json.loads(body)
    assert message["book_id"] == book_id
    assert message["user_id"] == user_id
    assert message["storage_provider"] == "local"


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


def test_add_book_without_a_name_uses_the_file_name(
    client: TestClient, username: str, uow: AbstractUnitOfWork
):
    user_id = sign_up(client, username)

    added = client.post(
        f"/users/{user_id}/books",
        files={"file": ("My Chapter.docx", b"word", "application/octet-stream")},
        data={"storage_provider": "local"},
    )

    assert added.status_code == 201
    with uow:
        book = uow.users.get(UUID(user_id)).books[0]
        assert str(book.id) == added.json()["book_id"]
        assert book.name == "My Chapter"
        assert book.location.key.endswith("/My Chapter.docx")


def test_add_book_of_unsupported_type_is_415(
    client: TestClient, username: str, tmp_path, uow: AbstractUnitOfWork
):
    user_id = sign_up(client, username)

    response = client.post(
        f"/users/{user_id}/books",
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


def test_add_book_of_an_empty_file_is_400(client: TestClient, username: str):
    user_id = sign_up(client, username)

    response = client.post(
        f"/users/{user_id}/books",
        files={"file": ("notes.pdf", b"", "application/pdf")},
        data={"storage_provider": "local"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty"}


def test_add_book_to_s3_is_not_found(client: TestClient, username: str, tmp_path):
    user_id = sign_up(client, username)

    response = client.post(
        f"/users/{user_id}/books",
        files={"file": ("notes.pdf", b"%PDF", "application/pdf")},
        data={"storage_provider": "s3", "name": "Notes"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "S3 storage not found"}
    assert list(tmp_path.rglob("*")) == []
