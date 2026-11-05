"""Typed, serializable learning-state models for adaptive tutoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class Language(str, Enum):
    ENGLISH = "english"
    TELUGU = "telugu"
    MIXED = "mixed"


class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Outcome(str, Enum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    AMBIGUOUS = "ambiguous"


class Strategy(str, Enum):
    STEP_BY_STEP = "step_by_step"
    HINT = "hint"
    SIMPLER_EXAMPLE = "simpler_example"
    ALTERNATIVE_EXPLANATION = "alternative_explanation"
    PREREQUISITE_REVIEW = "prerequisite_review"
    PRACTICE = "practice"
    CHALLENGE_PRACTICE = "challenge_practice"
    CONSTRUCTIVE_FEEDBACK = "constructive_feedback"


@dataclass(frozen=True)
class Evaluation:
    outcome: Outcome
    feedback: str
    explanation: str
    confidence: float = 1.0


@dataclass(frozen=True)
class AnswerRecord:
    question: str
    answer: str
    outcome: Outcome
    score: float | None
    hint_used: bool
    feedback: str
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StudentState:
    """In-memory session state; fields are deliberately persistence-friendly."""

    student_id: str
    topic: str
    preferred_language: Language = Language.ENGLISH
    difficulty: Difficulty = Difficulty.BEGINNER
    session_id: str = field(default_factory=lambda: str(uuid4()))
    recent_answers: list[AnswerRecord] = field(default_factory=list)
    correct_count: int = 0
    incorrect_count: int = 0
    partially_correct_count: int = 0
    ambiguous_count: int = 0
    attempts: int = 0
    hint_usage: int = 0
    recent_performance: list[float] = field(default_factory=list)
    mastery_score: float = 0.5
    evidence_count: int = 0
    evidence_points: float = 0.0
    last_difficulty_change_evidence: int = 0
    history_limit: int = 20

    def __post_init__(self) -> None:
        self.student_id = self.student_id.strip()
        self.topic = self.topic.strip()
        self.preferred_language = Language(self.preferred_language)
        self.difficulty = Difficulty(self.difficulty)
        if not self.student_id:
            raise ValueError("student_id must not be empty")
        if not self.topic:
            raise ValueError("topic must not be empty")
        if self.history_limit < 1:
            raise ValueError("history_limit must be positive")
        if not 0.0 <= self.mastery_score <= 1.0:
            raise ValueError("mastery_score must be between 0 and 1")
        if any(not 0.0 <= score <= 1.0 for score in self.recent_performance):
            raise ValueError("recent_performance scores must be between 0 and 1")

    def record(self, question: str, answer: str, evaluation: Evaluation, hint_used: bool = False) -> None:
        scores = {
            Outcome.CORRECT: 1.0,
            Outcome.PARTIALLY_CORRECT: 0.5,
            Outcome.INCORRECT: 0.0,
            Outcome.AMBIGUOUS: None,
        }
        score = scores[evaluation.outcome]
        self.attempts += 1
        if hint_used:
            self.hint_usage += 1
        if evaluation.outcome is Outcome.CORRECT:
            self.correct_count += 1
        elif evaluation.outcome is Outcome.INCORRECT:
            self.incorrect_count += 1
        elif evaluation.outcome is Outcome.PARTIALLY_CORRECT:
            self.partially_correct_count += 1
        else:
            self.ambiguous_count += 1

        self.recent_answers.append(AnswerRecord(
            question=question,
            answer=answer,
            outcome=evaluation.outcome,
            score=score,
            hint_used=hint_used,
            feedback=evaluation.feedback,
        ))
        self.recent_answers = self.recent_answers[-self.history_limit:]
        if score is not None:
            self.evidence_count += 1
            self.evidence_points += score
            self.recent_performance.append(score)
            self.recent_performance = self.recent_performance[-self.history_limit:]
            # Beta(2, 2) prior: two virtual successes and two virtual misses.
            self.mastery_score = (2.0 + self.evidence_points) / (4.0 + self.evidence_count)

