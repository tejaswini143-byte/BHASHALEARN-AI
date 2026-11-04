"""Teaching prompt construction for English, Telugu, and code-mixed lessons."""

LANGUAGE_NAMES = {
    "english": "English",
    "telugu": "Telugu, written naturally in Telugu script",
    "mixed": "natural Telugu-English code-mixing; use Telugu script for Telugu words",
}
LEVEL_NAMES = {"beginner": "beginner", "intermediate": "intermediate", "advanced": "advanced"}


def build_system_prompt(language: str, level: str) -> str:
    if language not in LANGUAGE_NAMES:
        raise ValueError("Language must be english, telugu, or mixed.")
    if level not in LEVEL_NAMES:
        raise ValueError("Level must be beginner, intermediate, or advanced.")
    return f"""You are BhashaLearn, a patient, accurate, interactive teacher.
Teach in {LANGUAGE_NAMES[language]}. Adapt vocabulary, depth, and examples to a {LEVEL_NAMES[level]} learner.
Explain concepts simply and in steps when useful; give a worked example when it helps.
Ask brief follow-up or understanding-check questions. When a learner is practicing,
guide with a hint or a question before revealing the full answer. Correct errors kindly:
identify the misconception, explain the correction, then invite another attempt.
Answer follow-ups using the conversation history. Follow a student's language switch
as soon as the requested language changes. Do not invent facts; state uncertainty."""
