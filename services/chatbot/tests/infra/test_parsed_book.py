import json
from pathlib import Path

import pytest

from manger.infra.parsed_book import ParsedBookNotFound, load_book_paragraphs


def test_load_book_paragraphs_reads_text_blocks_from_every_page(tmp_path: Path):
    parsed = tmp_path / "owner" / "book" / "Notes_parsed"
    parsed.mkdir(parents=True)
    (parsed / "page_0002.json").write_text(
        json.dumps(
            {
                "result": [
                    {
                        "res": {
                            "parsing_res_list": [
                                {"block_label": "paragraph_title", "block_content": "Title"},
                                {"block_label": "text", "block_content": 'Second page says "hi"'},
                            ]
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (parsed / "page_0001.json").write_text(
        '{"block_label": "text", "block_content": "Hello\\nthere"}'
        '{"block_label": "footer", "block_content": "1"}',
        encoding="utf-8",
    )
    (parsed / "notes.txt").write_text("ignore", encoding="utf-8")

    content = load_book_paragraphs("owner/book/notes.pdf", "Notes", tmp_path)

    assert content == 'Page 1\nHello\nthere\n\nPage 2\nSecond page says "hi"'


def test_load_book_paragraphs_rejects_a_missing_folder(tmp_path: Path):
    with pytest.raises(ParsedBookNotFound):
        load_book_paragraphs("owner/book/notes.pdf", "Notes", tmp_path)


def test_load_book_paragraphs_rejects_a_key_outside_storage(tmp_path: Path):
    with pytest.raises(ValueError, match="escapes"):
        load_book_paragraphs("../secret.pdf", "Notes", tmp_path)
