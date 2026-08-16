"""Step 1 (Scraping) from docs/DesignDoc.md.

Scrapes Korean words from the Wiktionary frequency list and stores them in a
local SQLite database.
"""

import os
import sqlite3

import requests
from bs4 import BeautifulSoup

FREQUENCY_LIST_URL = "https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Korean_5800"
DEFAULT_DB_PATH = "data/korean_words.db"
MVP_MIN_WORDS = 100

# Wikimedia rejects requests with the default python-requests User-Agent; it
# requires a descriptive one identifying the client. See
# https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {"User-Agent": "LearnKoreanWords/1.0 (personal vocabulary-scraping project)"}


def fetch_page(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.text


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


def scrape(url: str = FREQUENCY_LIST_URL, db_path: str = DEFAULT_DB_PATH) -> int:
    html = fetch_page(url)
    words = parse_words(html)
    save_words(words, db_path)

    if len(words) < MVP_MIN_WORDS:
        print(
            f"Warning: only captured {len(words)} words, "
            f"below the MVP target of {MVP_MIN_WORDS}."
        )

    return len(words)


if __name__ == "__main__":
    count = scrape()
    print(f"Scraped and stored {count} Korean words.")
