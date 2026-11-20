"""Publishes messages to RabbitMQ.

The parse worker in `services/parsing` consumes `parse_book`.
"""

from __future__ import annotations

import abc
import os
from pathlib import Path

import pika
from dotenv import dotenv_values

# services/app/.env when this file lives in manger/infra/.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_DEFAULT_URL = "amqp://pdf_reader:pdf_reader@localhost:5672/"

PARSE_QUEUE = "parse_book"


def rabbitmq_url() -> str:
    """`RABBITMQ_URL` from the environment, then from `.env`, then the local default."""
    configured = os.environ.get("RABBITMQ_URL", "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        from_file = (dotenv_values(_ENV_FILE).get("RABBITMQ_URL") or "").strip()
        if from_file:
            return from_file
    return _DEFAULT_URL


class AbstractMessagePublisher(abc.ABC):
    @abc.abstractmethod
    def publish(self, queue: str, body: bytes) -> None:
        """Send `body` to `queue`."""


class RabbitMqPublisher(AbstractMessagePublisher):
    def __init__(self, url: str | None = None):
        self.url = url or rabbitmq_url()

    def publish(self, queue: str, body: bytes) -> None:
        parameters = pika.URLParameters(self.url)
        parameters.socket_timeout = 2
        parameters.blocked_connection_timeout = 2
        connection = pika.BlockingConnection(parameters)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            connection.close()
