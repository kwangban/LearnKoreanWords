import sqlite3

import pytest

import scraper


SAMPLE_HTML = """
<html>
<body>
<div id="mw-content-text">
<h2>1 - 1000</h2>
<ul>
<li><a href="/wiki/%EA%B2%83" title="것">것</a></li>
<li><a href="/wiki/%ED%95%98%EB%8B%A4" title="하다">하다</a></li>
<li><a href="/wiki/%EC%9E%88%EB%8B%A4" title="있다">있다</a></li>
<li><a href="/wiki/%EA%B2%83" title="것">것</a></li>
</ul>
<p>See also <a href="/w/index.php?title=X&action=edit">edit</a> and
<a href="https://en.wikipedia.org/wiki/Korean_language">Wikipedia</a>.</p>
</div>
</body>
</html>
"""


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
