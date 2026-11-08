"""Optional quiz analytics boundary for a future independently developed adapter.

This module defines a provider-neutral contract only. It intentionally imports
no quiz API, model, migration, or storage schema.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence


@dataclass(frozen=True)
class QuizAttemptEvidence:
    """A completed, deduplicated quiz result already authorized for one student."""

    attempt_key: str
    student_id: str
    subject: str
    topic: str
    completed_at: datetime
    score: float
    max_score: float


class QuizAnalyticsProvider(Protocol):
    """Future adapter contract; implementations own their source-specific reads."""

    def completed_attempts(
        self,
        student_id: str,
        start_at: datetime,
        end_at: datetime,
        limit: int,
    ) -> Sequence[QuizAttemptEvidence]: ...


def scored_outcome(attempt: QuizAttemptEvidence) -> tuple[int, int] | None:
    """Normalize valid objective quiz results into (correct, total) evidence.

    Fractional or non-positive totals, non-finite values, and scores outside
    the declared range are ignored. Consumers must deduplicate by attempt_key
    and verify student_id before aggregating.
    """
    import math

    if not attempt.attempt_key or not attempt.student_id or not attempt.subject.strip() or not attempt.topic.strip():
        return None
    if not math.isfinite(attempt.score) or not math.isfinite(attempt.max_score) or attempt.max_score <= 0:
        return None
    if attempt.score < 0 or attempt.score > attempt.max_score:
        return None
    if not float(attempt.score).is_integer() or not float(attempt.max_score).is_integer():
        return None
    return int(attempt.score), int(attempt.max_score)
