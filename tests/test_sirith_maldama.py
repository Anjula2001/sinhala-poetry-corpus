import pytest

from sinhala_corpus.parsers.sirith_maldama import parse_verses


def test_verses_are_separated_and_line_breaks_preserved():
    text = (
        "{{header}}\n"
        "01.<br>පළමු පේළිය\n<br>දෙවන පේළිය\n"
        "<br>තුන්වන පේළිය\n<br>සිව්වන පේළිය\n\n"
        "02. <br>අ\n<br>ආ\n<br>ඇ\n<br>ඈ\n"
        "[[Category:සිංහල]]"
    )
    verses = parse_verses(text)

    assert len(verses) == 2
    assert verses[0]["verse_number"] == 1
    assert verses[0]["text"].splitlines() == [
        "පළමු පේළිය",
        "දෙවන පේළිය",
        "තුන්වන පේළිය",
        "සිව්වන පේළිය",
    ]
    assert verses[1]["text"] == "අ\nආ\nඇ\nඈ"
    assert verses[1]["quality_flags"] == []


def test_suspicious_character_is_preserved_and_flagged():
    verses = parse_verses("01.<br>අ>\n<br>ආ\n<br>ඇ\n<br>ඈ")

    assert ">" in verses[0]["text"]
    assert "possible_markup_or_transcription_artifact" in verses[0]["quality_flags"]


def test_missing_verse_number_is_rejected():
    with pytest.raises(ValueError, match="consecutive"):
        parse_verses("01.<br>අ\n03.<br>ආ")


def test_joining_characters_are_preserved():
    verses = parse_verses("01.<br>ක්\u200dර\n<br>ආ\n<br>ඇ\n<br>ඈ")

    assert "\u200d" in verses[0]["text"]


def test_unexpected_line_count_requires_review():
    verses = parse_verses("01.<br>අ\n<br>ආ")

    assert "unexpected_line_count" in verses[0]["quality_flags"]
    assert verses[0]["review_status"] == "pending"
