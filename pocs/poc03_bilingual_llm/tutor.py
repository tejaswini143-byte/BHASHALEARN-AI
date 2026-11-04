"""Small in-memory conversational teaching orchestration."""
from __future__ import annotations

try:
    from .prompts import build_system_prompt
except ImportError:
    from prompts import build_system_prompt

LANGUAGES = {"english", "telugu", "mixed"}
LEVELS = {"beginner", "intermediate", "advanced"}


class Tutor:
    def __init__(self, provider, language: str = "english", level: str = "beginner", max_turns: int = 6):
        if language not in LANGUAGES:
            raise ValueError("Language must be english, telugu, or mixed.")
        if level not in LEVELS:
            raise ValueError("Level must be beginner, intermediate, or advanced.")
        if max_turns < 1:
            raise ValueError("max_turns must be positive.")
        self.provider = provider
        self.language = language
        self.level = level
        self.max_turns = max_turns
        self.history: list[dict[str, str]] = []

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES:
            raise ValueError("Language must be english, telugu, or mixed.")
        self.language = language

    def set_level(self, level: str) -> None:
        if level not in LEVELS:
            raise ValueError("Level must be beginner, intermediate, or advanced.")
        self.level = level

    def ask(self, question: str) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must not be empty.")
        messages = [{"role": "system", "content": build_system_prompt(self.language, self.level)}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": question.strip()})
        answer = self.provider.complete(messages)
        self.history.extend([
            {"role": "user", "content": question.strip()},
            {"role": "assistant", "content": answer},
        ])
        self.history = self.history[-self.max_turns * 2:]
        return answer
