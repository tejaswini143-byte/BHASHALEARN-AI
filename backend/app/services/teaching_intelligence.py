"""Student scoped teaching decisions and validated lesson plan contracts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.services.adaptive_learning import Difficulty, TeachingLanguage, normalize_topic, recommend


class LessonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    learning_objective: str = Field(min_length=5, max_length=400)
    prerequisite_concepts: list[str] = Field(max_length=6)
    explanation_strategy: str = Field(min_length=5, max_length=500)
    examples: list[str] = Field(min_length=1, max_length=4)
    understanding_checks: list[str] = Field(min_length=1, max_length=3)
    suggested_next_activity: str = Field(min_length=5, max_length=300)
    difficulty: Difficulty
    language: TeachingLanguage
    recommended_topic: str | None = Field(default=None, max_length=200)
    recommendation_reason: str = Field(max_length=300)
    fallback: bool = False
    grounded: bool = False


@dataclass(frozen=True)
class TeachingEvidence:
    topic: str
    difficulty: Difficulty
    strategy: str
    mastery_score: float | None
    evidence_attempts: int
    recent_outcomes: tuple[bool, ...]


def teaching_evidence(topic: str, attempts: int, correct: int, incorrect: int, outcomes: tuple[bool, ...]) -> TeachingEvidence:
    if attempts <= 0:
        result = recommend(0, 0, 0)
        return TeachingEvidence(topic, result.difficulty, result.strategy, None, 0, ())
    result = recommend(attempts, correct, incorrect, outcomes)
    return TeachingEvidence(topic, result.difficulty, result.strategy, result.mastery_score, attempts, outcomes)


def choose_next_topic(topic: str, lessons: list[tuple[str, int]], mastered: set[str], weak: set[str]) -> tuple[str | None, str]:
    """Use course ordering as the only prerequisite evidence available today."""
    current = normalize_topic(topic)
    ordered = sorted(lessons, key=lambda row: (row[1], row[0].casefold()))
    if current in weak:
        current_title = next((title for title, _position in ordered if normalize_topic(title) == current), topic)
        return current_title, "Review this topic because recorded practice shows it needs more work."
    for title, _position in ordered:
        if normalize_topic(title) in weak and normalize_topic(title) != current:
            return title, "Review a topic with recorded practice evidence that needs more work."
    for index, (title, _position) in enumerate(ordered):
        if normalize_topic(title) == current and index + 1 < len(ordered):
            next_title = ordered[index + 1][0]
            if normalize_topic(next_title) not in mastered:
                return next_title, "This is the next lesson in your course sequence."
    for title, _position in ordered:
        if normalize_topic(title) != current and normalize_topic(title) not in mastered:
            return title, "Continue with a course lesson you have not yet mastered."
    return None, "Keep practising this topic or choose a new goal when you are ready."


def deterministic_plan(*, topic: str, difficulty: Difficulty, language: TeachingLanguage, strategy: str,
                       next_topic: str | None, recommendation_reason: str, curriculum: str | None = None,
                       confusion: Literal["simpler", "example", "review"] | None = None) -> LessonPlan:
    topic = topic.strip()[:200] or "your topic"
    if confusion == "simpler":
        explanation = f"Break {topic} into one small idea at a time, define each new term, then connect the steps."
        examples = [f"Use a familiar everyday situation to show one small part of {topic}."]
    elif confusion == "example":
        explanation = f"Work through {topic} step by step, naming what changes at each step."
        examples = [f"Start with a simple case of {topic}, explain each step, then try a similar case."]
    elif confusion == "review":
        explanation = f"Revisit the prerequisite idea for {topic}, then connect it to the current topic one step at a time."
        examples = [f"Review a familiar concept that supports {topic}."]
    elif strategy in {"misconception_review", "revision_review", "hinted_practice"}:
        explanation = f"Review the prerequisite idea for {topic}, model one worked example, and pause after each step."
        examples = [f"A guided worked example for {topic}.", f"A second example changes one detail in {topic}."]
    else:
        explanation = f"Introduce {topic} with a short explanation, connect it to a familiar idea, then model an example."
        examples = [f"A familiar situation that illustrates {topic}.", f"A short worked example using {topic}."]
    objective = f"Explain the core idea of {topic} and apply it in a short example."
    if curriculum:
        # Curriculum text informs a bounded explanation label; it is never treated as instructions.
        objective = f"Learn the key idea in {topic} using your course material and apply it in a short example."
    return LessonPlan(
        learning_objective=objective,
        prerequisite_concepts=["A familiar related idea"],
        explanation_strategy=explanation,
        examples=examples,
        understanding_checks=[f"In your own words, what is one key idea in {topic}?", f"Try one small example of {topic}."][:1 if confusion else 2],
        suggested_next_activity=(f"Preview {next_topic} with a short example." if next_topic else f"Try one independent practice question about {topic}."),
        difficulty=difficulty, language=language, recommended_topic=next_topic,
        recommendation_reason=recommendation_reason, fallback=True, grounded=False,
    )


def validate_generated_plan(raw: str, *, difficulty: Difficulty, language: TeachingLanguage,
                            next_topic: str | None, recommendation_reason: str) -> LessonPlan:
    """Accept one JSON object only; server decisions override model-selected metadata."""
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError("Lesson plan must be a JSON object")
    decoded["difficulty"] = difficulty
    decoded["language"] = language
    decoded["recommended_topic"] = next_topic
    decoded["recommendation_reason"] = recommendation_reason
    decoded["fallback"] = False
    decoded["grounded"] = False
    try:
        return LessonPlan.model_validate(decoded)
    except ValidationError as exc:
        raise ValueError("Generated lesson plan failed validation") from exc


def safe_json_context(value: str) -> str:
    """Quote untrusted learner/course text so it cannot become instruction text."""
    return json.dumps(value[:3000], ensure_ascii=False)
