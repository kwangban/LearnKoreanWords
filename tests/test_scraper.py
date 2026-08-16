import os
import sqlite3
from pathlib import Path

import pytest

import scraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = (FIXTURES_DIR / "sample_frequency_list.html").read_text(encoding="utf-8")
SAMPLE_WORD_PAGE_HTML = (FIXTURES_DIR / "sample_word_page.html").read_text(encoding="utf-8")
SAMPLE_WORD_PAGE_WITH_AUDIO_HTML = (
    FIXTURES_DIR / "sample_word_page_with_audio.html"
).read_text(encoding="utf-8")


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


def test_parse_parts_of_speech_scopes_to_korean_section():
    parts_of_speech = scraper.parse_parts_of_speech(SAMPLE_WORD_PAGE_HTML)

    assert parts_of_speech == ["Verb", "Adjective"]


def test_parse_parts_of_speech_returns_empty_when_no_korean_section():
    assert scraper.parse_parts_of_speech(SAMPLE_HTML) == []


def test_parse_gloss_returns_first_sense_excluding_usage_examples():
    gloss = scraper.parse_gloss(SAMPLE_WORD_PAGE_WITH_AUDIO_HTML)

    assert gloss == "thing; something"


def test_parse_gloss_returns_none_when_no_definitions():
    assert scraper.parse_gloss(SAMPLE_WORD_PAGE_HTML) is None
    assert scraper.parse_gloss(SAMPLE_HTML) is None


def test_save_glosses_links_to_word_id(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["것"], db_path)
    scraper.save_glosses({"것": "thing; something"}, db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT korean_words.word, word_glosses.gloss
            FROM word_glosses
            JOIN korean_words ON korean_words.id = word_glosses.word_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("것", "thing; something")]


def test_parse_audio_url_picks_original_source_from_pronunciation_section():
    audio_url = scraper.parse_audio_url(SAMPLE_WORD_PAGE_WITH_AUDIO_HTML)

    assert audio_url == "https://upload.wikimedia.org/wikipedia/commons/e/e4/Ko-word.oga"


def test_parse_audio_url_returns_none_when_no_pronunciation_audio():
    assert scraper.parse_audio_url(SAMPLE_WORD_PAGE_HTML) is None
    assert scraper.parse_audio_url(SAMPLE_HTML) is None


def test_download_audio_saves_file_with_word_name(tmp_path, monkeypatch):
    class FakeResponse:
        content = b"fake-audio-bytes"
        status_code = 200

        def raise_for_status(self):
            pass

    monkeypatch.setattr(scraper.requests, "get", lambda url, headers, timeout: FakeResponse())
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)

    audio_dir = str(tmp_path / "audio")
    path = scraper.download_audio("https://example.com/Ko-word.oga", "것", audio_dir)

    assert path == os.path.join(audio_dir, "것.oga")
    with open(path, "rb") as audio_file:
        assert audio_file.read() == b"fake-audio-bytes"


def test_save_audio_paths_links_to_word_id(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["것"], db_path)
    scraper.save_audio_paths({"것": "data/audio/것.oga"}, db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT korean_words.word, word_audio.audio_path
            FROM word_audio
            JOIN korean_words ON korean_words.id = word_audio.word_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("것", "data/audio/것.oga")]


def test_save_parts_of_speech_links_to_word_id(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["하다"], db_path)
    scraper.save_parts_of_speech({"하다": ["Verb", "Adjective"]}, db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT korean_words.word, word_parts_of_speech.part_of_speech
            FROM word_parts_of_speech
            JOIN korean_words ON korean_words.id = word_parts_of_speech.word_id
            ORDER BY word_parts_of_speech.id
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("하다", "Verb"), ("하다", "Adjective")]


def test_save_parts_of_speech_is_idempotent(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["하다"], db_path)
    scraper.save_parts_of_speech({"하다": ["Verb"]}, db_path)
    scraper.save_parts_of_speech({"하다": ["Verb", "Adjective"]}, db_path)

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT part_of_speech FROM word_parts_of_speech").fetchall()
    finally:
        connection.close()

    assert rows == [("Verb",), ("Adjective",)]


def test_scrape_orchestrates_fetch_parse_save(tmp_path, monkeypatch):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)
    monkeypatch.setattr(scraper, "fetch_word_page", lambda word: SAMPLE_WORD_PAGE_WITH_AUDIO_HTML)
    monkeypatch.setattr(
        scraper, "download_audio", lambda url, word, audio_dir: f"{audio_dir}/{word}.oga"
    )

    count = scraper.scrape(db_path=db_path, fetch_audio=True)

    assert count == 3
    connection = sqlite3.connect(db_path)
    try:
        stored = connection.execute("SELECT COUNT(*) FROM korean_words").fetchone()[0]
        pos_stored = connection.execute("SELECT COUNT(*) FROM word_parts_of_speech").fetchone()[0]
        gloss_stored = connection.execute("SELECT COUNT(*) FROM word_glosses").fetchone()[0]
        audio_stored = connection.execute("SELECT COUNT(*) FROM word_audio").fetchone()[0]
    finally:
        connection.close()
    assert stored == 3
    assert pos_stored == 3
    assert gloss_stored == 3
    assert audio_stored == 3


def test_scrape_skips_audio_by_default(tmp_path, monkeypatch):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)
    monkeypatch.setattr(scraper, "fetch_word_page", lambda word: SAMPLE_WORD_PAGE_WITH_AUDIO_HTML)

    def fail_if_called(url, word, audio_dir):
        raise AssertionError("download_audio should not be called when fetch_audio=False")

    monkeypatch.setattr(scraper, "download_audio", fail_if_called)

    scraper.scrape(db_path=db_path)

    connection = sqlite3.connect(db_path)
    try:
        # word_audio must still exist (flashcards.py queries it
        # unconditionally) but should be empty since audio was skipped.
        audio_count = connection.execute("SELECT COUNT(*) FROM word_audio").fetchone()[0]
    finally:
        connection.close()
    assert audio_count == 0


def test_scrape_skips_words_that_already_have_a_gloss(tmp_path, monkeypatch):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)
    fetched_words = []

    def fake_fetch_word_page(word):
        fetched_words.append(word)
        return SAMPLE_WORD_PAGE_WITH_AUDIO_HTML

    monkeypatch.setattr(scraper, "fetch_word_page", fake_fetch_word_page)
    monkeypatch.setattr(
        scraper, "download_audio", lambda url, word, audio_dir: f"{audio_dir}/{word}.oga"
    )

    scraper.scrape(db_path=db_path)
    fetched_words.clear()
    scraper.scrape(db_path=db_path)

    assert fetched_words == []


def test_scrape_continues_after_a_word_detail_fetch_fails(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)

    def flaky_fetch_word_page(word):
        if word == "하다":
            raise scraper.requests.exceptions.RequestException("boom")
        return SAMPLE_WORD_PAGE_WITH_AUDIO_HTML

    monkeypatch.setattr(scraper, "fetch_word_page", flaky_fetch_word_page)
    monkeypatch.setattr(
        scraper, "download_audio", lambda url, word, audio_dir: f"{audio_dir}/{word}.oga"
    )

    count = scraper.scrape(db_path=db_path)

    assert count == 3
    captured = capsys.readouterr()
    assert "하다" in captured.out
    connection = sqlite3.connect(db_path)
    try:
        pos_stored = connection.execute("SELECT COUNT(*) FROM word_parts_of_speech").fetchone()[0]
    finally:
        connection.close()
    assert pos_stored == 2


def test_scrape_only_fetches_details_up_to_the_word_limit(tmp_path, monkeypatch):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)
    fetched_words = []

    def fake_fetch_word_page(word):
        fetched_words.append(word)
        return SAMPLE_WORD_PAGE_WITH_AUDIO_HTML

    monkeypatch.setattr(scraper, "fetch_word_page", fake_fetch_word_page)
    monkeypatch.setattr(
        scraper, "download_audio", lambda url, word, audio_dir: f"{audio_dir}/{word}.oga"
    )

    scraper.scrape(db_path=db_path, detail_word_limit=1)

    assert fetched_words == ["것"]


def test_scrape_warns_when_below_mvp_threshold(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "words.db")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: SAMPLE_HTML)
    monkeypatch.setattr(scraper, "fetch_word_page", lambda word: SAMPLE_WORD_PAGE_HTML)

    scraper.scrape(db_path=db_path)

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert str(scraper.MVP_MIN_WORDS) in captured.out
