import pytest

from pocs.poc06_bilingual_voice.evaluate_transcription import (
    SAMPLES,
    _normalize_words,
    character_error_rate,
    word_error_rate,
)


def test_sample_set_covers_english_telugu_and_mixed_practice_phrases():
    assert [(label, language) for label, _text, language, _key in SAMPLES] == [
        ("English", "en-IN"),
        ("Telugu", "te-IN"),
        ("Mixed", "indic-auto"),
    ]
    assert SAMPLES[0][1] == "What is a mixed fraction?"
    assert SAMPLES[1][1] == "మిశ్రమ భిన్నం అంటే ఏమిటి?"
    assert SAMPLES[2][1] == "Mixed fraction అంటే ఏమిటి? ఒక example చెప్పండి."


@pytest.mark.parametrize("metric", [word_error_rate, character_error_rate])
def test_transcription_metric_is_zero_for_exact_unicode_match(metric):
    phrase = "మిశ్రమ భిన్నం అంటే ఏమిటి?"
    assert metric(phrase, phrase) == 0.0


def test_word_error_rate_detects_one_word_substitution():
    assert word_error_rate("What is a mixed fraction", "What is a proper fraction") == pytest.approx(0.2)


def test_telugu_word_tokenization_keeps_unicode_combining_marks():
    assert _normalize_words("రెండు భిన్నాలు") == ["రెండు", "భిన్నాలు"]


def test_character_error_rate_ignores_whitespace_but_not_word_changes():
    assert character_error_rate("Hello world", "Hello   world") == 0.0
    assert character_error_rate("Hello world", "Hello word") > 0.0
