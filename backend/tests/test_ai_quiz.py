import json

import pytest
from fastapi import HTTPException

from backend.app.config import get_settings
from backend.app.services import ai_quiz


def _payload():
    return {"questions": [
        {
            "type": "multiple_choice", "prompt_en": "What is one half plus one fourth?",
            "prompt_te": "ఒకటి రెండు వంతు మరియు ఒకటి నాలుగు వంతు కలిపితే ఎంత?",
            "choices": [
                {"english": "1/2", "telugu": "1/2"},
                {"english": "3/4", "telugu": "3/4"},
                {"english": "1/4", "telugu": "1/4"},
            ],
            "correct_index": 1, "accepted": [],
            "explanation_en": "Convert 1/2 to 2/4, then add the numerators.",
            "explanation_te": "1/2 ను 2/4గా మార్చి, లవాలను కలపాలి.",
        },
        {
            "type": "short_answer", "prompt_en": "Write one fraction equivalent to 2/3.",
            "prompt_te": "2/3కు సమానమైన ఒక భిన్నాన్ని రాయండి.",
            "choices": [], "correct_index": None, "accepted": ["4/6"],
            "explanation_en": "Multiply numerator and denominator by two.",
            "explanation_te": "లవం, హారాన్ని రెండుతో గుణించండి.",
        },
    ]}


def test_generate_ai_quiz_validates_and_builds_bilingual_mcq_and_short_answer(monkeypatch):
    monkeypatch.setenv("BHASHALEARN_GEMINI_API_KEY", "unit-test-key-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr(ai_quiz, "generate_tutor_reply", lambda *_: json.dumps(_payload(), ensure_ascii=False))
    questions = ai_quiz.generate_quiz_questions(
        topic="fractions", difficulty="beginner", language="mixed", question_count=2,
    )
    assert questions and [item.question_type for item in questions] == ["multiple_choice", "short_answer"]
    assert questions[0].accepted == ("3/4", "3/4")
    assert questions[0].source == "gemini_live"
    assert questions[1].accepted == ("4/6",)
    get_settings.cache_clear()


def test_generate_ai_quiz_rejects_missing_questions(monkeypatch):
    monkeypatch.setenv("BHASHALEARN_GEMINI_API_KEY", "unit-test-key-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr(ai_quiz, "generate_tutor_reply", lambda *_: '{"questions": []}')
    with pytest.raises(HTTPException) as exc:
        ai_quiz.generate_quiz_questions(
            topic="fractions", difficulty="beginner", language="english", question_count=1,
        )
    assert exc.value.status_code == 502
    get_settings.cache_clear()


def test_generate_ai_quiz_is_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("BHASHALEARN_GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    assert ai_quiz.generate_quiz_questions(
        topic="fractions", difficulty="beginner", language="english", question_count=1,
    ) is None
    get_settings.cache_clear()
