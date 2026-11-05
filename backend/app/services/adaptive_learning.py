"""Deterministic adaptation policy driven only by submitted objective assessments."""
import re
from dataclasses import dataclass


def normalize_topic(topic: str) -> str:
    key = " ".join(re.sub(r"\s+", " ", topic.strip().lower()).split())[:200]
    key = key.replace("’", "'").replace("'", "")
    if key in {"dijkstras shortest path", "dijkstra algorithm", "dijkstras algorithm"}:
        return "dijkstra shortest path"
    return key


@dataclass(frozen=True)
class Adaptation:
    mastery_score: float
    difficulty: str
    strategy: str
    recommendation: str


def recommend(evidence_attempts: int, correct_attempts: int, incorrect_attempts: int) -> Adaptation:
    if evidence_attempts <= 0:
        return Adaptation(0.0, "beginner", "diagnostic_practice", "Start with a short diagnostic question.")
    score = round(100 * correct_attempts / evidence_attempts, 1)
    if evidence_attempts < 3:
        return Adaptation(score, "beginner", "guided_practice", "Complete a few more questions to establish a reliable baseline.")
    if score < 50:
        return Adaptation(score, "beginner", "misconception_review", "Review the key idea with a worked example, then try a similar question.")
    if score < 80:
        return Adaptation(score, "intermediate", "prerequisite_review", "Review the prerequisite step and practise with a scaffolded example.")
    if score < 95:
        return Adaptation(score, "intermediate", "guided_practice", "Try a new question with less scaffolding.")
    return Adaptation(score, "advanced", "challenge_practice", "Try a transfer question in a new context.")
