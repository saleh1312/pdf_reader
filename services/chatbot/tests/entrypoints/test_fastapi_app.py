from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from manger.domain import Message, Turn
from manger.entrypoints.fastapi_app import create_app
from manger.infra.db.session.uow import FakeSessionUnitOfWork


class RecordingProvider:
    def __init__(self, reply: str = "The answer"):
        self.reply = reply
        self.sent: list[list[Message]] = []

    def send(self, messages: list[Message]) -> str:
        self.sent.append(list(messages))
        return self.reply


def test_create_session_then_infer_returns_the_model_reply():
    uow = FakeSessionUnitOfWork()
    provider = RecordingProvider("Chapter one.")
    client = TestClient(
        create_app(
            uow_factory=lambda: uow,
            provider=provider,
            lookup_book=lambda *_args: {
                "name": "Notes",
                "storage_provider": "local",
                "storage_key": "owner/book/notes.pdf",
                "is_parsed": True,
            },
            load_paragraphs=lambda *_args: "Page 1\nHello",
        )
    )
    user_id, book_id = uuid4(), uuid4()

    created = client.post("/sessions", json={"user_id": str(user_id), "book_id": str(book_id)})

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "success"
    session_id = body["session_id"]

    answer = client.post("/infer", json={"session_id": session_id, "msg": "What is this?"})

    assert answer.status_code == 200
    assert answer.json() == {"message": "Chapter one."}
    assert [item.turn for item in provider.sent[0]] == [Turn.SYSTEM, Turn.USER]
    assert provider.sent[0][0].content.endswith("Page 1\nHello")
    assert "plain text" in provider.sent[0][0].content
    assert provider.sent[0][1].content == "What is this?"
    stored = uow.sessions.get(UUID(session_id))
    assert [item.turn for item in stored.messages] == [Turn.SYSTEM, Turn.USER, Turn.AI]
    assert stored.messages[-1].content == "Chapter one."


def test_session_list_and_history_follow_the_conversation():
    uow = FakeSessionUnitOfWork()
    provider = RecordingProvider("Chapter one.")
    client = TestClient(
        create_app(
            uow_factory=lambda: uow,
            provider=provider,
            lookup_book=lambda *_args: {
                "name": "Notes",
                "storage_provider": "local",
                "storage_key": "owner/book/notes.pdf",
                "is_parsed": True,
            },
            load_paragraphs=lambda *_args: "Page 1\nHello",
        )
    )
    user_id, book_id = uuid4(), uuid4()
    created = client.post(
        "/sessions",
        json={"user_id": str(user_id), "book_id": str(book_id)},
    )
    session_id = created.json()["session_id"]

    listed = client.get(f"/users/{user_id}/sessions")

    assert listed.status_code == 200
    assert listed.json() == [
        {"session_id": session_id, "book_id": str(book_id), "preview": "New chat"}
    ]

    client.post("/infer", json={"session_id": session_id, "msg": "What is this?"})
    listed_again = client.get(f"/users/{user_id}/sessions")
    history = client.get(f"/users/{user_id}/sessions/{session_id}")

    assert listed_again.json()[0]["preview"] == "What is this?"
    assert history.json()["book_id"] == str(book_id)
    assert [item["turn"] for item in history.json()["messages"]] == ["system", "user", "ai"]
    assert history.json()["messages"][-1]["content"] == "Chapter one."


def test_history_for_another_users_session_is_404():
    uow = FakeSessionUnitOfWork()
    client = TestClient(
        create_app(
            uow_factory=lambda: uow,
            provider=RecordingProvider(),
            lookup_book=lambda *_args: {
                "name": "Notes",
                "storage_provider": "local",
                "storage_key": "a.pdf",
                "is_parsed": True,
            },
            load_paragraphs=lambda *_args: "Page 1\nHello",
        )
    )
    created = client.post(
        "/sessions",
        json={"user_id": str(uuid4()), "book_id": str(uuid4())},
    )

    response = client.get(f"/users/{uuid4()}/sessions/{created.json()['session_id']}")

    assert response.status_code == 404


def test_infer_unknown_session_is_404():
    client = TestClient(
        create_app(uow_factory=lambda: FakeSessionUnitOfWork(), provider=RecordingProvider())
    )

    response = client.post("/infer", json={"session_id": str(uuid4()), "msg": "Hello"})

    assert response.status_code == 404


def test_create_session_for_an_unknown_book_is_404():
    client = TestClient(
        create_app(
            uow_factory=lambda: FakeSessionUnitOfWork(),
            provider=RecordingProvider(),
            lookup_book=lambda *_args: None,
        )
    )

    response = client.post(
        "/sessions", json={"user_id": str(uuid4()), "book_id": str(uuid4())}
    )

    assert response.status_code == 404


def test_infer_blank_message_is_400():
    client = TestClient(
        create_app(uow_factory=lambda: FakeSessionUnitOfWork(), provider=RecordingProvider())
    )

    response = client.post("/infer", json={"session_id": str(uuid4()), "msg": "  "})

    assert response.status_code == 400
