"""OpenAI adapter for the chat-model port."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from manger.domain import Message, Turn
from manger.services.ai_provider import AiProvider

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_ROLES = {
    Turn.SYSTEM: "system",
    Turn.USER: "user",
    Turn.AI: "assistant",
}


class OpenAiProvider(AiProvider):
    """Sends session messages through an OpenAI-compatible chat API.

    `OPENAI_BASE_URL` selects the server: a local runtime, OpenRouter
    (`https://openrouter.ai/api/v1`), or the official API when it is empty.
    """

    def __init__(self, client=None, model: str | None = None, base_url: str | None = None):
        self._client = client
        self.model = model or _setting("OPENAI_MODEL")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL is missing from services/chatbot/.env")
        self.base_url = _api_root(base_url if base_url is not None else _setting("OPENAI_BASE_URL"))

    def send(self, messages: list[Message]) -> str:
        if not messages:
            raise ValueError("At least one message is required")
        client = self._client if self._client is not None else _openai_client(self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": _ROLES[message.turn], "content": message.content}
                for message in messages
            ],
        )
        content = response.choices[0].message.content
        if content is None or not content.strip():
            raise RuntimeError("OpenAI returned an empty response")
        return content


def _openai_client(base_url: str):
    from openai import OpenAI

    api_key = _setting("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from services/chatbot/.env")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def _api_root(raw: str) -> str:
    """Chat API root. A missing `/v1` is added for local servers and OpenRouter."""
    value = raw.strip().rstrip("/")
    if value and not value.endswith("/v1"):
        value = value + "/v1"
    return value


def _setting(key: str, default: str = "") -> str:
    configured = os.environ.get(key, "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        from_file = (dotenv_values(_ENV_FILE).get(key) or "").strip()
        if from_file:
            return from_file
    return default
