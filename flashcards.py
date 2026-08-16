"""Step 3 (Display) from docs/DesignDoc.md.

A locally running flashcard viewer over the words scraped in scraper.py.
"""

import os
import sqlite3
import tkinter as tk
from dataclasses import dataclass, field

from scraper import DEFAULT_DB_PATH


@dataclass
class Flashcard:
    word: str
    gloss: str
    parts_of_speech: list[str] = field(default_factory=list)
    audio_path: str | None = None


def load_flashcards(db_path: str = DEFAULT_DB_PATH) -> list[Flashcard]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT korean_words.id, korean_words.word, word_glosses.gloss, word_audio.audio_path
            FROM korean_words
            JOIN word_glosses ON word_glosses.word_id = korean_words.id
            LEFT JOIN word_audio ON word_audio.word_id = korean_words.id
            ORDER BY korean_words.id
            """
        ).fetchall()

        flashcards = []
        for word_id, word, gloss, audio_path in rows:
            pos_rows = connection.execute(
                "SELECT part_of_speech FROM word_parts_of_speech WHERE word_id = ?",
                (word_id,),
            ).fetchall()
            flashcards.append(
                Flashcard(
                    word=word,
                    gloss=gloss,
                    parts_of_speech=[pos for (pos,) in pos_rows],
                    audio_path=audio_path,
                )
            )
        return flashcards
    finally:
        connection.close()


class FlashcardDeck:
    """Tracks which card is showing and whether its answer is revealed."""

    def __init__(self, flashcards: list[Flashcard]):
        self.flashcards = flashcards
        self.index = 0
        self.show_answer = False

    def current(self) -> Flashcard | None:
        if not self.flashcards:
            return None
        return self.flashcards[self.index]

    def next(self) -> None:
        if self.flashcards:
            self.index = (self.index + 1) % len(self.flashcards)
            self.show_answer = False

    def previous(self) -> None:
        if self.flashcards:
            self.index = (self.index - 1) % len(self.flashcards)
            self.show_answer = False

    def toggle_answer(self) -> None:
        self.show_answer = not self.show_answer

    def position_label(self) -> str:
        if not self.flashcards:
            return "0 / 0"
        return f"{self.index + 1} / {len(self.flashcards)}"


class FlashcardApp(tk.Tk):
    def __init__(self, deck: FlashcardDeck):
        super().__init__()
        self.deck = deck

        self.title("Learn Korean Words")
        self.geometry("480x360")

        self.position_label = tk.Label(self, font=("Segoe UI", 10))
        self.position_label.pack(pady=(16, 0))

        self.word_label = tk.Label(self, font=("Malgun Gothic", 48))
        self.word_label.pack(pady=24)

        self.answer_label = tk.Label(
            self, font=("Segoe UI", 16), wraplength=420, justify="center"
        )
        self.answer_label.pack(pady=8)

        button_row = tk.Frame(self)
        button_row.pack(pady=24)
        tk.Button(button_row, text="Previous", command=self.on_previous).grid(row=0, column=0, padx=6)
        tk.Button(button_row, text="Show Answer", command=self.on_toggle_answer).grid(row=0, column=1, padx=6)
        tk.Button(button_row, text="Play Audio", command=self.on_play_audio).grid(row=0, column=2, padx=6)
        tk.Button(button_row, text="Next", command=self.on_next).grid(row=0, column=3, padx=6)

        self.bind("<Left>", lambda event: self.on_previous())
        self.bind("<Right>", lambda event: self.on_next())
        self.bind("<space>", lambda event: self.on_toggle_answer())

        self.render()

    def render(self) -> None:
        card = self.deck.current()
        self.position_label.config(text=self.deck.position_label())

        if card is None:
            self.word_label.config(text="No flashcards yet")
            self.answer_label.config(text="Run scraper.py first.")
            return

        self.word_label.config(text=card.word)
        if self.deck.show_answer:
            pos_text = ", ".join(card.parts_of_speech) if card.parts_of_speech else ""
            text = f"{card.gloss}\n({pos_text})" if pos_text else card.gloss
            self.answer_label.config(text=text)
        else:
            self.answer_label.config(text="")

    def on_next(self) -> None:
        self.deck.next()
        self.render()

    def on_previous(self) -> None:
        self.deck.previous()
        self.render()

    def on_toggle_answer(self) -> None:
        self.deck.toggle_answer()
        self.render()

    def on_play_audio(self) -> None:
        card = self.deck.current()
        if card is None or not card.audio_path or not os.path.exists(card.audio_path):
            return
        try:
            os.startfile(card.audio_path)
        except OSError:
            pass


if __name__ == "__main__":
    deck = FlashcardDeck(load_flashcards())
    app = FlashcardApp(deck)
    app.mainloop()
