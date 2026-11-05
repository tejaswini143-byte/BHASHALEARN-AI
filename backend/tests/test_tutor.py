"""BE-07 tutor integration tests."""
from backend.app.services.tutor import build_instruction, LANGUAGE_GUIDANCE

def test_bilingual_prompt():
    prompt = build_instruction("Greetings", "telugu", "beginner", "Speak clearly")
    assert "Greetings" in prompt
    assert "Speak clearly" in prompt
    assert "beginner" in prompt
    assert LANGUAGE_GUIDANCE["telugu"] in prompt

def test_english_prompt():
    prompt = build_instruction("Math", "english", "advanced", None)
    assert "advanced" in prompt
    assert LANGUAGE_GUIDANCE["english"] in prompt

def test_fallback_language():
    prompt = build_instruction("Numbers", "unknown", "beginner", None)
    assert LANGUAGE_GUIDANCE["mixed"] in prompt
