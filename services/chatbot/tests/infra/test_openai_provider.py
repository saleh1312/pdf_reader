from datetime import datetime, timezone

import pytest

from manger.domain import ContentType, Message, Turn
from manger.infra.ai_providers.openai import OpenAiProvider, _api_root
from manger.services.ai_provider import AiProvider


def message(turn: Turn, content: str) -> Message:
    return Message(
        date=datetime(2026, 11, 22, tzinfo=timezone.utc),
        turn=turn,
        content=content,
        content_type=ContentType.TEXT,
    )


class _Reply:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Reply(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _Response(self.content)


class _Client:
    def __init__(self, content="The answer"):
        self.chat = type("Chat", (), {"completions": _Completions(content)})()


def test_openai_provider_is_an_ai_provider():
    assert isinstance(OpenAiProvider(client=_Client(), model="gpt-4o-mini"), AiProvider)


def test_send_maps_session_messages_and_returns_the_reply():
    client = _Client("Chapter one is about design.")
    provider = OpenAiProvider(client=client, model="gpt-4o-mini")
    messages = [
        message(Turn.SYSTEM, "Page 1\nHello"),
        message(Turn.USER, "What is chapter one?"),
        message(Turn.AI, "It introduces the idea."),
        message(Turn.USER, "Say more."),
    ]

    reply = provider.send(messages)

    assert reply == "Chapter one is about design."
    assert client.chat.completions.kwargs == {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Page 1\nHello"},
            {"role": "user", "content": "What is chapter one?"},
            {"role": "assistant", "content": "It introduces the idea."},
            {"role": "user", "content": "Say more."},
        ],
    }


def test_send_rejects_an_empty_session():
    provider = OpenAiProvider(client=_Client(), model="gpt-4o-mini")

    with pytest.raises(ValueError, match="At least one message"):
        provider.send([])


def test_base_url_points_at_a_local_server_or_openrouter():
    assert _api_root("http://127.0.0.1:8092") == "http://127.0.0.1:8092/v1"
    assert _api_root("http://127.0.0.1:8092/v1/") == "http://127.0.0.1:8092/v1"
    assert _api_root("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"
    assert _api_root("") == ""


def test_provider_builds_the_client_with_the_base_url(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = type("Chat", (), {"completions": _Completions("ok")})()

    monkeypatch.setenv("OPENAI_API_KEY", "local-key")
    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    provider = OpenAiProvider(model="local-model", base_url="https://openrouter.ai/api/v1")

    assert provider.send([message(Turn.USER, "Hello")]) == "ok"
    assert captured == {
        "api_key": "local-key",
        "base_url": "https://openrouter.ai/api/v1",
    }


def test_send_rejects_an_empty_reply():
    provider = OpenAiProvider(client=_Client(content="   "), model="gpt-4o-mini")

    with pytest.raises(RuntimeError, match="empty"):
        provider.send([message(Turn.USER, "Hello")])
