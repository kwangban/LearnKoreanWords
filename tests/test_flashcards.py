import scraper
from flashcards import Flashcard, FlashcardDeck, load_flashcards


def test_load_flashcards_only_includes_words_with_a_gloss(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["것", "하다"], db_path)
    scraper.save_glosses({"것": "thing; something"}, db_path)
    scraper.save_parts_of_speech({"것": ["Dependent noun"]}, db_path)
    scraper.save_audio_paths({"것": "data/audio/것.oga"}, db_path)

    flashcards = load_flashcards(db_path)

    assert flashcards == [
        Flashcard(
            word="것",
            gloss="thing; something",
            parts_of_speech=["Dependent noun"],
            audio_path="data/audio/것.oga",
        )
    ]


def test_load_flashcards_handles_missing_audio(tmp_path):
    db_path = str(tmp_path / "words.db")
    scraper.save_words(["나"], db_path)
    scraper.save_glosses({"나": "I, me"}, db_path)
    scraper.save_parts_of_speech({}, db_path)
    scraper.save_audio_paths({}, db_path)

    flashcards = load_flashcards(db_path)

    assert flashcards == [Flashcard(word="나", gloss="I, me", parts_of_speech=[], audio_path=None)]


def test_deck_next_and_previous_wrap_around():
    deck = FlashcardDeck([Flashcard(word="a", gloss="a"), Flashcard(word="b", gloss="b")])

    assert deck.current().word == "a"
    deck.next()
    assert deck.current().word == "b"
    deck.next()
    assert deck.current().word == "a"
    deck.previous()
    assert deck.current().word == "b"


def test_deck_next_resets_show_answer():
    deck = FlashcardDeck([Flashcard(word="a", gloss="a"), Flashcard(word="b", gloss="b")])
    deck.toggle_answer()
    assert deck.show_answer is True

    deck.next()

    assert deck.show_answer is False


def test_deck_position_label():
    deck = FlashcardDeck([Flashcard(word="a", gloss="a"), Flashcard(word="b", gloss="b")])
    assert deck.position_label() == "1 / 2"
    deck.next()
    assert deck.position_label() == "2 / 2"


def test_deck_handles_empty_flashcard_list():
    deck = FlashcardDeck([])

    assert deck.current() is None
    assert deck.position_label() == "0 / 0"
    deck.next()
    deck.previous()
    deck.toggle_answer()
