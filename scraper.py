"""Step 1 (Scraping) from docs/DesignDoc.md.

Scrapes Korean words from the Wiktionary frequency list and stores them in a
local SQLite database.
"""

import os
import re
import sqlite3
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# Printing Korean text can fail on a Windows console using a non-UTF-8
# codepage (e.g. cp1252); force UTF-8 output so warnings never crash the run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FREQUENCY_LIST_URL = "https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Korean_5800"
WORD_PAGE_URL = "https://en.wiktionary.org/wiki/{}"
DEFAULT_DB_PATH = "data/korean_words.db"
DEFAULT_AUDIO_DIR = "data/audio"
MVP_MIN_WORDS = 100

# Wikimedia rate-limits by IP; a short pause between requests keeps this
# script's ~200 sequential requests (word pages + audio downloads) under
# that limit. See https://meta.wikimedia.org/wiki/User-Agent_policy
REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 5

# Wikimedia rejects requests with the default python-requests User-Agent; it
# requires a descriptive one identifying the client. See
# https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {"User-Agent": "LearnKoreanWords/1.0 (personal vocabulary-scraping project)"}

# Section headings under a word's "Korean" language heading that denote a
# part of speech, as opposed to sections like Etymology or Pronunciation.
KNOWN_PARTS_OF_SPEECH = {
    "Noun", "Proper noun", "Dependent noun", "Pronoun", "Verb", "Adjective",
    "Adverb", "Determiner", "Numeral", "Counter", "Classifier", "Particle",
    "Postposition", "Preposition", "Conjunction", "Interjection", "Prefix",
    "Suffix", "Root", "Symbol", "Punctuation mark", "Phrase", "Proverb",
    "Idiom", "Article", "Auxiliary verb",
}


def _get_with_retry(url: str) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 429 and attempt < MAX_RETRIES - 1:
            backoff = REQUEST_DELAY_SECONDS * 5 * (2**attempt)
            retry_after = float(response.headers.get("Retry-After", backoff))
            time.sleep(retry_after)
            continue
        response.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        return response


def fetch_page(url: str) -> str:
    return _get_with_retry(url).text


def parse_words(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="mw-content-text")

    words = []
    seen = set()
    for link in content.find_all("a", href=True):
        if not link["href"].startswith("/wiki/"):
            continue
        word = link.get_text(strip=True)
        if word and word not in seen:
            seen.add(word)
            words.append(word)

    return words


def fetch_word_page(word: str) -> str:
    return fetch_page(WORD_PAGE_URL.format(quote(word, safe="")))


def _find_korean_heading(content):
    for heading in content.find_all("h2"):
        if heading.get_text(strip=True) == "Korean":
            return heading
    return None


def parse_parts_of_speech(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="mw-content-text")
    korean_heading = _find_korean_heading(content)
    if korean_heading is None:
        return []

    parts_of_speech = []
    for heading in korean_heading.find_all_next(["h2", "h3", "h4", "h5"]):
        if heading.name == "h2":
            break
        text = heading.get_text(strip=True)
        if text in KNOWN_PARTS_OF_SPEECH and text not in parts_of_speech:
            parts_of_speech.append(text)

    return parts_of_speech


def _clean_gloss_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([;,.:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text


def parse_gloss(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="mw-content-text")
    korean_heading = _find_korean_heading(content)
    if korean_heading is None:
        return None

    for heading in korean_heading.find_all_next(["h2", "h3", "h4", "h5"]):
        if heading.name == "h2":
            break
        if heading.get_text(strip=True) not in KNOWN_PARTS_OF_SPEECH:
            continue

        for element in heading.find_all_next():
            if element.name in ("h2", "h3", "h4", "h5"):
                break
            if element.name != "ol":
                continue
            first_sense = element.find("li")
            if first_sense is None:
                continue
            # Re-parse just this <li> so decomposing nested usage-example
            # blocks (<dl>) doesn't mutate the tree we're still traversing.
            sense_copy = BeautifulSoup(str(first_sense), "html.parser")
            for nested in sense_copy.find_all(["dl", "ol", "ul"]):
                nested.decompose()
            gloss = _clean_gloss_text(sense_copy.get_text(separator=" "))
            if gloss:
                return gloss

    return None


def parse_audio_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find(id="mw-content-text")
    korean_heading = _find_korean_heading(content)
    if korean_heading is None:
        return None

    pronunciation_heading = None
    for heading in korean_heading.find_all_next(["h2", "h3"]):
        if heading.name == "h2":
            break
        if heading.get_text(strip=True) == "Pronunciation":
            pronunciation_heading = heading
            break
    if pronunciation_heading is None:
        return None

    for element in pronunciation_heading.find_all_next():
        if element.name in ("h2", "h3"):
            break
        if element.name == "audio":
            # The source without a transcodekey is the original upload;
            # the others are Wikimedia-generated mp3/ogg transcodes of it.
            for source in element.find_all("source"):
                if "data-transcodekey" not in source.attrs and source.get("src"):
                    src = source["src"].split("?")[0]
                    return "https:" + src if src.startswith("//") else src

    return None


def download_audio(url: str, word: str, audio_dir: str = DEFAULT_AUDIO_DIR) -> str:
    os.makedirs(audio_dir, exist_ok=True)
    extension = url.rsplit(".", 1)[-1]
    path = os.path.join(audio_dir, f"{word}.{extension}")

    if os.path.exists(path):
        return path

    response = _get_with_retry(url)
    with open(path, "wb") as audio_file:
        audio_file.write(response.content)

    return path


def save_words(words: list[str], db_path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS korean_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO korean_words (word) VALUES (?)",
            [(word,) for word in words],
        )
        connection.commit()
    finally:
        connection.close()


def save_parts_of_speech(
    parts_of_speech_by_word: dict[str, list[str]], db_path: str = DEFAULT_DB_PATH
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS word_parts_of_speech (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL REFERENCES korean_words(id),
                part_of_speech TEXT NOT NULL,
                UNIQUE(word_id, part_of_speech)
            )
            """
        )
        rows = []
        for word, parts_of_speech in parts_of_speech_by_word.items():
            word_id_row = connection.execute(
                "SELECT id FROM korean_words WHERE word = ?", (word,)
            ).fetchone()
            if word_id_row is None:
                continue
            word_id = word_id_row[0]
            rows.extend((word_id, pos) for pos in parts_of_speech)

        connection.executemany(
            """
            INSERT OR IGNORE INTO word_parts_of_speech (word_id, part_of_speech)
            VALUES (?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def save_audio_paths(
    audio_paths_by_word: dict[str, str], db_path: str = DEFAULT_DB_PATH
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS word_audio (
                word_id INTEGER PRIMARY KEY REFERENCES korean_words(id),
                audio_path TEXT NOT NULL
            )
            """
        )
        for word, audio_path in audio_paths_by_word.items():
            word_id_row = connection.execute(
                "SELECT id FROM korean_words WHERE word = ?", (word,)
            ).fetchone()
            if word_id_row is None:
                continue
            connection.execute(
                "INSERT OR REPLACE INTO word_audio (word_id, audio_path) VALUES (?, ?)",
                (word_id_row[0], audio_path),
            )
        connection.commit()
    finally:
        connection.close()


def save_glosses(glosses_by_word: dict[str, str], db_path: str = DEFAULT_DB_PATH) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS word_glosses (
                word_id INTEGER PRIMARY KEY REFERENCES korean_words(id),
                gloss TEXT NOT NULL
            )
            """
        )
        for word, gloss in glosses_by_word.items():
            word_id_row = connection.execute(
                "SELECT id FROM korean_words WHERE word = ?", (word,)
            ).fetchone()
            if word_id_row is None:
                continue
            connection.execute(
                "INSERT OR REPLACE INTO word_glosses (word_id, gloss) VALUES (?, ?)",
                (word_id_row[0], gloss),
            )
        connection.commit()
    finally:
        connection.close()


def _word_has_gloss(word: str, db_path: str) -> bool:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT 1 FROM korean_words
            JOIN word_glosses ON word_glosses.word_id = korean_words.id
            WHERE korean_words.word = ?
            """,
            (word,),
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError:
        return False
    finally:
        connection.close()


def scrape(
    url: str = FREQUENCY_LIST_URL,
    db_path: str = DEFAULT_DB_PATH,
    audio_dir: str = DEFAULT_AUDIO_DIR,
    detail_word_limit: int = MVP_MIN_WORDS,
    # Per docs/DesignDoc.md, audio downloads are deferred for now: they
    # trigger 429s from upload.wikimedia.org even with throttling/retries.
    fetch_audio: bool = False,
) -> int:
    html = fetch_page(url)
    words = parse_words(html)
    save_words(words, db_path)

    # Ensure the detail tables always exist, even when fetch_audio=False
    # means save_audio_paths is never otherwise called; consumers like
    # flashcards.py query them unconditionally.
    save_parts_of_speech({}, db_path)
    save_glosses({}, db_path)
    save_audio_paths({}, db_path)

    detail_words = words[:detail_word_limit]
    total = len(detail_words)
    for position, word in enumerate(detail_words, start=1):
        progress = f"[{position}/{total}] {word}"

        if _word_has_gloss(word, db_path):
            print(f"{progress}: already scraped, skipping")
            continue
        try:
            word_html = fetch_word_page(word)

            save_parts_of_speech({word: parse_parts_of_speech(word_html)}, db_path)

            gloss = parse_gloss(word_html)
            if gloss:
                save_glosses({word: gloss}, db_path)

            if fetch_audio:
                audio_url = parse_audio_url(word_html)
                if audio_url:
                    audio_path = download_audio(audio_url, word, audio_dir)
                    save_audio_paths({word: audio_path}, db_path)

            print(f"{progress}: done")
        except requests.exceptions.RequestException as error:
            print(f"{progress}: failed - {error}")

    if len(words) < MVP_MIN_WORDS:
        print(
            f"Warning: only captured {len(words)} words, "
            f"below the MVP target of {MVP_MIN_WORDS}."
        )

    return len(words)


if __name__ == "__main__":
    count = scrape()
    print(f"Scraped and stored {count} Korean words.")
