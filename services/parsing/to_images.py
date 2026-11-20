"""Render an uploaded book into one image per page.

Images are written next to the file, in a folder named `{book_name}_images`.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

_WORD_SUFFIXES = {".doc", ".docx"}
_INVALID_NAME_CHARS = '<>:"/\\|?*'


def render_book(book_path: Path, book_name: str) -> Path:
    """Render `book_path` and return the directory of page images."""
    book_path = Path(book_path)
    if not book_path.is_file():
        raise FileNotFoundError(book_path)

    images_dir = book_path.parent / _folder_name(book_name, "images")
    images_dir.mkdir(parents=True, exist_ok=True)
    for old in images_dir.glob("page_*.png"):
        old.unlink()

    pdf_path, temporary = _as_pdf(book_path)
    try:
        document = pdfium.PdfDocument(pdf_path)
        try:
            if len(document) == 0:
                raise ValueError(f"{book_path.name} has no pages")
            for index, page in enumerate(document, start=1):
                bitmap = page.render(scale=2)
                bitmap.to_pil().save(images_dir / f"page_{index:04d}.png")
        finally:
            document.close()
    finally:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
    return images_dir


def _as_pdf(book_path: Path) -> tuple[Path, Path | None]:
    if book_path.suffix.lower() == ".pdf":
        return book_path, None
    if book_path.suffix.lower() not in _WORD_SUFFIXES:
        raise ValueError(f"Cannot render {book_path.suffix or 'this file'} as page images")

    temporary = Path(tempfile.mkdtemp(prefix="book-pdf-"))
    soffice = shutil.which("soffice") or shutil.which("soffice.com")
    if soffice is None:
        shutil.rmtree(temporary, ignore_errors=True)
        raise RuntimeError(
            "Word files are rendered by LibreOffice. Install it and put soffice on PATH."
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(temporary), str(book_path)],
        check=True,
    )
    converted = temporary / f"{book_path.stem}.pdf"
    if not converted.is_file():
        shutil.rmtree(temporary, ignore_errors=True)
        raise RuntimeError(f"LibreOffice did not produce a PDF for {book_path.name}")
    return converted, temporary


def _folder_name(book_name: str, suffix: str) -> str:
    cleaned = "".join(
        "_" if character in _INVALID_NAME_CHARS or ord(character) < 32 else character
        for character in book_name
    ).strip().rstrip(".")
    if not cleaned:
        cleaned = "book"
    return f"{cleaned}_{suffix}"
