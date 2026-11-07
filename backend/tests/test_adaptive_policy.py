"""Storage-free tests for transparent lesson adaptation decisions."""
from backend.app.services.adaptive_learning import (
    StudentLearningProfile,
    TopicProficiency,
    lesson_directive,
    normalize_topic,
    recommend,
)


def test_difficulty_uses_evidence_thresholds():
    assert recommend(0, 0, 0).difficulty == "beginner"
    assert recommend(2, 2, 0).difficulty == "beginner"
    assert recommend(3, 2, 1).difficulty == "intermediate"
    assert recommend(3, 3, 0).difficulty == "intermediate"
    assert recommend(4, 4, 0).difficulty == "intermediate"
    assert recommend(5, 5, 0).difficulty == "advanced"


def test_repeated_mistakes_request_hints_then_review():
    two_mistakes = recommend(4, 2, 2, (True, True, False, False))
    assert two_mistakes.strategy == "hinted_practice"
    assert "Two consecutive" in two_mistakes.reason
    three_mistakes = recommend(5, 2, 3, (True, True, False, False, False))
    assert three_mistakes.strategy == "misconception_review"
    assert three_mistakes.difficulty == "beginner"


def test_recent_decline_recommends_revision():
    result = recommend(8, 7, 1, (True, True, True, True, True, False, True, False))
    assert result.mastery_score == 87.5
    assert result.revision_recommended is True
    assert result.strategy == "revision_review"
    assert "Recent accuracy" in result.reason


def test_ambiguous_attempts_are_excluded_by_caller_and_counters_are_bounded():
    result = recommend(5, 99, -4)
    assert result.mastery_score == 100
    assert result.difficulty == "advanced"


def test_topic_normalization_is_stable():
    assert normalize_topic("  Dijkstra   Algorithm ") == "dijkstra shortest path"


def test_lesson_directive_carries_student_language_and_pace():
    proficiency = TopicProficiency(
        topic="Equivalent Fractions", subject="Mathematics", mastery_score=100,
        evidence_attempts=4, difficulty="advanced", strategy="challenge_practice",
        recommendation="Try a transfer question.", revision_recommended=False,
        last_activity_at=None,
    )
    profile = StudentLearningProfile("telugu", "slow", (proficiency,), (), ())
    directive = lesson_directive(profile, "Equivalent Fractions")
    assert directive.language == "telugu"
    assert directive.pace == "slow"
    assert directive.difficulty == "advanced"
    assert lesson_directive(profile, "New topic").strategy == "diagnostic_practice"
