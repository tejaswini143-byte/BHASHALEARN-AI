"""Shared session context built around POC-04's canonical StudentState."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from pocs.poc04_adaptive_teaching.models import AnswerRecord, Difficulty, Language, StudentState


class Modality(str, Enum):
    CHAT = "chat"
    VOICE_TRANSCRIPT = "voice_transcript"
    ADAPTIVE_TUTOR = "adaptive_tutor"
    VISUAL_LESSON = "visual_lesson"


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    modality: Modality
    content: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in {"user", "assistant", "system"}:
            raise ValueError("role must be user, assistant, or system")
        if not self.content.strip():
            raise ValueError("conversation content must not be empty")
        object.__setattr__(self, "modality", Modality(self.modality))


@dataclass
class SessionContext:
    """POC-04 learning state is the sole source for identity and progress."""

    learning_state: StudentState
    lesson_objective: str = ""
    current_teaching_step: str = ""
    adaptive_strategy: str = ""
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_reset_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def session_id(self) -> str:
        return self.learning_state.session_id

    @property
    def student_id(self) -> str:
        return self.learning_state.student_id

    @property
    def topic(self) -> str:
        return self.learning_state.topic

    @property
    def language(self) -> Language:
        return self.learning_state.preferred_language

    @property
    def difficulty(self) -> Difficulty:
        return self.learning_state.difficulty


@dataclass(frozen=True)
class TeachingContext:
    session_id: str
    student_id: str
    topic: str
    language: Language
    difficulty: Difficulty
    mastery_score: float
    hint_usage: int
    lesson_objective: str
    current_teaching_step: str
    adaptive_strategy: str
    recent_answers: tuple[AnswerRecord, ...]
    recent_turns: tuple[ConversationTurn, ...]
    created_at: datetime
    updated_at: datetime
    ended_at: datetime | None
