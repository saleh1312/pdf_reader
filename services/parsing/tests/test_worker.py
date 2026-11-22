from pathlib import Path

import pytest

from worker import handle, mark_book_parsed


class _Result:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _Connection:
    def __init__(self, rowcount: int = 1):
        self.rowcount = rowcount
        self.sql = ""
        self.params = ()

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return _Result(self.rowcount)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_mark_book_parsed_sets_the_flag():
    connection = _Connection()

    mark_book_parsed(
        {"book_id": "book-1", "user_id": "user-1"},
        connect=lambda: connection,
    )

    assert "is_parsed = true" in connection.sql
    assert connection.params == ("book-1", "user-1")


def test_mark_book_parsed_fails_when_the_book_is_missing():
    connection = _Connection(rowcount=0)

    with pytest.raises(RuntimeError, match="not marked"):
        mark_book_parsed(
            {"book_id": "missing", "user_id": "user-1"},
            connect=lambda: connection,
        )


def test_handle_marks_the_book_after_the_json_is_saved(monkeypatch, tmp_path: Path):
    marked = {}

    monkeypatch.setattr("worker._book_path", lambda key: tmp_path / "notes.pdf")
    monkeypatch.setattr("worker.render_book", lambda path, name: tmp_path)
    monkeypatch.setattr("worker.parse_images", lambda images, path, name: tmp_path)
    monkeypatch.setattr("worker.mark_book_parsed", lambda message: marked.update(message))

    handle(
        {
            "storage_provider": "local",
            "storage_key": "owner/book/notes.pdf",
            "name": "Notes",
            "book_id": "book-1",
            "user_id": "user-1",
        }
    )

    assert marked["book_id"] == "book-1"
    assert marked["user_id"] == "user-1"
