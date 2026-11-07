"""Typed, deterministic learner context and adaptation policy.

This module has no database or provider dependency so it can be reused by the
tutor, smartboard, and voice adapters without giving those adapters ownership
of learner state.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

Difficulty = Literal["beginner", "intermediate", "advanced"]
TeachingLanguage = Literal["telugu", "english", "mixed"]
LearningPace = Literal["slow", "steady", "fast"]


def normalize_topic(topic: str) -> str:
    key = " ".join(re.sub(r"\s+", " ", topic.strip().lower()).split())[:200]
    key = key.replace("’", "'").replace("'", "")
    if key in {"dijkstras shortest path", "dijkstra algorithm", "dijkstras algorithm"}:
        return "dijkstra shortest path"
    return key


@dataclass(frozen=True)
class Adaptation:
    mastery_score: float
    difficulty: Difficulty
    strategy: str
    recommendation: str
    reason: str = ""
    revision_recommended: bool = False


def recommend(
    evidence_attempts: int,
    correct_attempts: int,
    incorrect_attempts: int,
    recent_outcomes: tuple[bool, ...] = (),
) -> Adaptation:
    """Recommend a lesson from scored objective evidence.

    ``recent_outcomes`` is oldest to newest and excludes ambiguous responses.
    Two latest mistakes request a hint; three indicate review. A recent drop
    below 50% after established 80%+ mastery recommends revision. Aggregate
    evidence remains the baseline when no recent history is supplied.
    """
    if evidence_attempts <= 0:
        return Adaptation(0.0, "beginner", "diagnostic_practice", "Start with a short diagnostic question.", "No scored answers yet.")
    correct_attempts = max(0, min(correct_attempts, evidence_attempts))
    incorrect_attempts = max(0, min(incorrect_attempts, evidence_attempts - correct_attempts))
    score = round(100 * correct_attempts / evidence_attempts, 1)
    if evidence_attempts < 3:
        base = Adaptation(score, "beginner", "guided_practice", "Complete a few more questions to establish a reliable baseline.", "Fewer than three scored answers; keep practice guided.")
    elif score < 50:
        base = Adaptation(score, "beginner", "misconception_review", "Review the key idea with a worked example, then try a similar question.", "Fewer than half of scored answers are correct.")
    elif score < 80:
        base = Adaptation(score, "intermediate", "prerequisite_review", "Review the prerequisite step and practise with a scaffolded example.", "Accuracy is between 50% and 79%.")
    elif score < 95 or evidence_attempts < 5:
        reason = "Accuracy is between 80% and 94%; continue with guided challenge." if score < 95 else "At least five scored answers are needed before advanced challenges."
        base = Adaptation(score, "intermediate", "guided_practice", "Try a new question with less scaffolding.", reason)
    else:
        base = Adaptation(score, "advanced", "challenge_practice", "Try a transfer question in a new context.", "At least five scored answers with 95% or better accuracy.")

    recent = recent_outcomes[-5:]
    if len(recent) >= 3 and recent[-3:] == (False, False, False):
        return Adaptation(score, "beginner", "misconception_review", "Review a worked example, then try one similar question with a hint.", "Three consecutive incorrect answers.")
    if len(recent) >= 2 and recent[-2:] == (False, False):
        return Adaptation(score, "beginner" if base.difficulty == "beginner" else "intermediate", "hinted_practice", "Show a small hint before the next similar question.", "Two consecutive incorrect answers.")
    recent_score = sum(recent[-3:]) / 3 * 100 if len(recent) >= 3 else None
    if score >= 80 and recent_score is not None and recent_score < 50:
        return Adaptation(score, "intermediate", "revision_review", "Revisit this topic with a short refresher before a new challenge.", "Recent accuracy is below 50% after established mastery of at least 80%.", True)
    return base


@dataclass(frozen=True)
class TopicProficiency:
    topic: str
    subject: str | None
    mastery_score: float
    evidence_attempts: int
    difficulty: Difficulty
    strategy: str
    recommendation: str
    revision_recommended: bool
    last_activity_at: datetime | None


@dataclass(frozen=True)
class LearningActivity:
    topic: str
    outcome: Literal["correct", "incorrect"]
    occurred_at: datetime


@dataclass(frozen=True)
class StudentLearningProfile:
    """Minimal adaptive view; intentionally excludes identity and chat text."""
    preferred_language: TeachingLanguage
    learning_pace: LearningPace
    proficiencies: tuple[TopicProficiency, ...]
    recent_activity: tuple[LearningActivity, ...]
    revision_topics: tuple[str, ...]


@dataclass(frozen=True)
class AdaptiveLessonDirective:
    topic: str
    language: TeachingLanguage
    pace: LearningPace
    difficulty: Difficulty
    strategy: str
    recommendation: str


def lesson_directive(profile: StudentLearningProfile, topic: str) -> AdaptiveLessonDirective:
    """Resolve profile preferences and proficiency into a provider-neutral lesson directive."""
    key = normalize_topic(topic)
    proficiency = next((item for item in profile.proficiencies if normalize_topic(item.topic) == key), None)
    if proficiency is None:
        return AdaptiveLessonDirective(
            topic=topic, language=profile.preferred_language, pace=profile.learning_pace,
            difficulty="beginner", strategy="diagnostic_practice",
            recommendation="Start with a short diagnostic question.",
        )
    return AdaptiveLessonDirective(
        topic=proficiency.topic, language=profile.preferred_language, pace=profile.learning_pace,
        difficulty=proficiency.difficulty, strategy=proficiency.strategy,
        recommendation=proficiency.recommendation,
    )


class TutorContextAdapter(Protocol):
    """ADV-03 seam: turn a directive and profile into bounded tutor context."""
    def teach(self, directive: AdaptiveLessonDirective, profile: StudentLearningProfile) -> object: ...


class SmartboardAdapter(Protocol):
    """ADV-04 seam: render an adaptive lesson without owning its decision."""
    def show_lesson(self, directive: AdaptiveLessonDirective) -> object: ...


class VoiceAdapter(Protocol):
    """ADV-06 seam: exchange lesson audio using the selected language."""
    def deliver(self, directive: AdaptiveLessonDirective, text: str) -> object: ...
