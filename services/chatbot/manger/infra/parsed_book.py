"""Read the paragraph text PaddleOCR wrote next to a book."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_PAGE_FILE = re.compile(r"^page_(\d+)\.json$")
# PaddleOCR writes each region as block_label then block_content. A paragraph
# is a block whose label is "text".
_PARAGRAPH = re.compile(
    r'"block_label"\s*:\s*"text"\s*,\s*"block_content"\s*:\s*"((?:\\.|[^"\\])*)"'
)


class ParsedBookNotFound(Exception):
    pass


def load_book_paragraphs(
    storage_key: str, book_name: str, storage_root: Path | None = None
) -> str:
    """Return every page's paragraphs, in page order, as one system message."""
    parsed_dir = _parsed_dir(storage_key, book_name, storage_root)
    if not parsed_dir.is_dir():
        raise ParsedBookNotFound(f"Parsed book not found at {parsed_dir}")

    pages: list[tuple[int, list[str]]] = []
    for path in sorted(parsed_dir.iterdir()):
        match = _PAGE_FILE.match(path.name)
        if match is None or not path.is_file():
            continue
        paragraphs = _paragraphs(path.read_text(encoding="utf-8"))
        if paragraphs:
            pages.append((int(match.group(1)), paragraphs))

    if not pages:
        raise ParsedBookNotFound(f"No paragraphs in {parsed_dir}")

    return "\n\n".join(
        f"Page {number}\n" + "\n\n".join(paragraphs) for number, paragraphs in pages
    )


def _paragraphs(raw: str) -> list[str]:
    found = []
    for match in _PARAGRAPH.finditer(raw):
        text = json.loads(f'"{match.group(1)}"').strip()
        if text:
            found.append(text)
    return found


def _parsed_dir(storage_key: str, book_name: str, storage_root: Path | None) -> Path:
    root = (storage_root or _storage_root()).resolve()
    book = (root / storage_key).resolve()
    if not book.is_relative_to(root):
        raise ValueError("storage key escapes the storage root")
    return book.parent / _folder_name(book_name, "parsed")


def _folder_name(book_name: str, suffix: str) -> str:
    """Same folder name the parsing worker writes: `{book name}_parsed`."""
    invalid = '<>:"/\\|?*'
    cleaned = "".join(
        "_" if character in invalid or ord(character) < 32 else character
        for character in book_name
    ).strip().rstrip(".")
    if not cleaned:
        cleaned = "book"
    return f"{cleaned}_{suffix}"


def _storage_root() -> Path:
    configured = os.environ.get("LOCAL_STORAGE_PATH", "").strip()
    if not configured and _ENV_FILE.is_file():
        configured = (dotenv_values(_ENV_FILE).get("LOCAL_STORAGE_PATH") or "").strip()
    if not configured:
        configured = "../app/storage"
    path = Path(configured)
    if not path.is_absolute():
        path = _ENV_FILE.parent / path
    return path.resolve()
