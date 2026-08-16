import sqlite3
from pathlib import Path

import pytest

import scraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = (FIXTURES_DIR / "sample_frequency_list.html").read_text(encoding="utf-8")


def test_parse_words_extracts_and_dedupes():
    words = scraper.parse_words(SAMPLE_HTML)
    assert words == ["것", "하다", "있다"]


def test_parse_words_ignores_non_wiki_links():
    words = scraper.parse_words(SAMPLE_HTML)
    assert "edit" not in words
    assert "Wikipedia" not in words


def test_save_words_creates_table_and_inserts(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["것", "하다"], db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT word FROM korean_words ORDER BY id").fetchall()
    finally:
        connection.close()

    assert rows == [("것",), ("하다",)]


def test_save_words_is_idempotent(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["것", "하다"], db_path)
    scraper.save_words(["것", "있다"], db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT word FROM korean_words ORDER BY id").fetchall()
    finally:
        connection.close()

    assert rows == [("것",), ("하다",), ("있다",)]


def test_scrape_orchestrates_fetch_parse_save(tmp_path, monkeypatch):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)

    count = scraper.scrape(db_path=db_path)

    assert count == 3
    connection = sqlite3.connect(db_path)
    try:
        stored = connection.execute("SELECT COUNT(*) FROM korean_words").fetchone()[0]
    finally:
        connection.close()
    assert stored == 3


def test_scrape_warns_when_below_mvp_threshold(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)

    scraper.scrape(db_path=db_path)

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert str(scraper.MVP_MIN_WORDS) in captured.out
