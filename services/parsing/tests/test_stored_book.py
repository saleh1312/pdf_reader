"""Run page rendering and PaddleOCR on the stored sample book."""

import json
from pathlib import Path

from parse_images import parse_images
from to_images import render_book

BOOK = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "storage"
    / "0350e5c2-01c8-4be5-a7aa-1d4957db0adc"
    / "833b5675-261d-4611-8847-2e8e88354352"
    / "document_2026_11_18_13_53_13.pdf"
)
BOOK_NAME = "document_2026_11_18_13_53_13"


def test_render_and_parse_the_stored_book():
    images_dir = render_book(BOOK, BOOK_NAME)
    pages = sorted(images_dir.glob("page_*.png"))

    assert images_dir == BOOK.parent / f"{BOOK_NAME}_images"
    assert [page.name for page in pages] == ["page_0001.png", "page_0002.png"]
    assert all(page.stat().st_size > 0 for page in pages)

    parsed_dir = parse_images(images_dir, BOOK, BOOK_NAME)
    saved = sorted(parsed_dir.glob("*.json"))

    assert parsed_dir == BOOK.parent / f"{BOOK_NAME}_parsed"
    assert [path.name for path in saved] == ["page_0001.json", "page_0002.json"]
    assert any(_recognized(json.loads(path.read_text(encoding="utf-8"))) for path in saved)


def _recognized(payload: dict) -> bool:
    for page in payload["result"]:
        result = page["res"]
        blocks = result.get("parsing_res_list") or []
        boxes = (result.get("layout_det_res") or {}).get("boxes") or []
        if blocks or boxes:
            return True
    return False
