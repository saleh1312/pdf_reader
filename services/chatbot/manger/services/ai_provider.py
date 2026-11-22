"""Port for a chat model. Adapters live in the infrastructure layer."""

from __future__ import annotations

import abc

from manger.domain import Message


class AiProvider(abc.ABC):
    """Sends a session's messages and returns the model's reply text."""

    @abc.abstractmethod
    def send(self, messages: list[Message]) -> str:
        """Send `messages` in order and return the reply."""
        raise NotImplementedError
