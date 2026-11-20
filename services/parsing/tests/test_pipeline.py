import threading
import time
from pathlib import Path

import pypdfium2 as pdfium

from parse_images import openai_base_url, parse_images
from to_images import render_book


def test_render_book_writes_a_page_image_next_to_the_pdf(tmp_path: Path):
    book = tmp_path / "notes.pdf"
    document = pdfium.PdfDocument.new()
    document.new_page(200, 200)
    document.save(book)
    document.close()

    images_dir = render_book(book, "Clean Architecture")

    assert images_dir == tmp_path / "Clean Architecture_images"
    pages = list(images_dir.glob("page_*.png"))
    assert len(pages) == 1
    assert pages[0].stat().st_size > 0


def test_openai_base_url_adds_v1():
    assert openai_base_url("http://185.62.108.226:46476/") == "http://185.62.108.226:46476/v1"
    assert openai_base_url("http://185.62.108.226:46476/v1") == "http://185.62.108.226:46476/v1"


def test_parse_images_saves_one_json_per_image_with_ten_at_a_time(tmp_path: Path):
    images_dir = tmp_path / "Notes_images"
    images_dir.mkdir()
    for index in range(12):
        (images_dir / f"page_{index:04d}.png").write_bytes(b"png")
    book = tmp_path / "notes.pdf"
    book.write_bytes(b"%PDF")

    in_flight = 0
    peak = 0
    lock = threading.Lock()

    def predict(image: Path) -> list:
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        time.sleep(0.05)
        with lock:
            in_flight -= 1
        return [{"text": image.stem, "boxes": [[1, 2, 3, 4]]}]

    parsed_dir = parse_images(
        images_dir, book, "Notes", concurrency=10, predict=predict
    )

    assert parsed_dir == tmp_path / "Notes_parsed"
    saved = sorted(parsed_dir.glob("*.json"))
    assert [path.name for path in saved] == [f"page_{index:04d}.json" for index in range(12)]
    assert 2 <= peak <= 10
