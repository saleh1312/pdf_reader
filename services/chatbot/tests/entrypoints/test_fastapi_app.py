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
    assert provider.sent[0][0].content == "Page 1\nHello"
    assert provider.sent[0][1].content == "What is this?"
    stored = uow.sessions.get(UUID(session_id))
    assert [item.turn for item in stored.messages] == [Turn.SYSTEM, Turn.USER, Turn.AI]
    assert stored.messages[-1].content == "Chapter one."


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
