"""Receive parse requests and turn each book into page images and OCR JSON."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pika
from dotenv import dotenv_values

from parse_images import parse_images
from to_images import render_book

QUEUE = "parse_book"
_ENV_FILE = Path(__file__).resolve().parent / ".env"

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parameters = pika.URLParameters(_setting("RABBITMQ_URL", "amqp://pdf_reader:pdf_reader@localhost:5672/"))
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
    logger.info("waiting for messages on %s", QUEUE)
    channel.start_consuming()


def on_message(channel, method, _properties, body: bytes) -> None:
    try:
        handle(json.loads(body))
    except Exception:
        logger.exception("failed to parse book")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def handle(message: dict) -> None:
    if message.get("storage_provider") not in (None, "local"):
        raise RuntimeError(
            f"{message.get('storage_provider')} storage is not available to the parser"
        )
    book_path = _book_path(message["storage_key"])
    book_name = message.get("name") or book_path.stem
    logger.info("rendering %s", book_path)
    images_dir = render_book(book_path, book_name)
    logger.info("parsing %s", images_dir)
    parsed_dir = parse_images(images_dir, book_path, book_name)
    logger.info("parsed book saved in %s", parsed_dir)
    mark_book_parsed(message)


def mark_book_parsed(message: dict, *, connect=None) -> None:
    """Set books.is_parsed in the app database after the JSON files are written."""
    book_id = str(message["book_id"])
    user_id = str(message["user_id"])
    opener = connect or _connect_app_db
    with opener() as connection:
        result = connection.execute(
            "UPDATE books SET is_parsed = true WHERE id = %s AND user_id = %s",
            (book_id, user_id),
        )
        updated = result.rowcount
    if updated != 1:
        raise RuntimeError(f"book {book_id} was not marked parsed")
    logger.info("marked book %s parsed", book_id)


def _connect_app_db():
    import psycopg

    return psycopg.connect(_app_database_dsn())


def _app_database_dsn() -> str:
    raw = _setting(
        "APP_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/pdf_reader",
    )
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


def _book_path(storage_key: str) -> Path:
    root = _storage_root()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("storage key escapes the storage root")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _storage_root() -> Path:
    configured = _setting("LOCAL_STORAGE_PATH", "../app/storage")
    path = Path(configured)
    if not path.is_absolute():
        path = _ENV_FILE.parent / path
    return path.resolve()


def _setting(key: str, default: str = "") -> str:
    configured = os.environ.get(key, "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        from_file = (dotenv_values(_ENV_FILE).get(key) or "").strip()
        if from_file:
            return from_file
    return default


if __name__ == "__main__":
    main()
