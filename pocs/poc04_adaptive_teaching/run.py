"""Interactive POC-04 adaptive tutoring CLI using POC-03's Gemini client."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from pocs.poc03_bilingual_llm.config import ConfigurationError, LLMConfig
from pocs.poc03_bilingual_llm.llm_client import LLMClient
from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import StructuredLLMEvaluator
from pocs.poc04_adaptive_teaching.models import Difficulty, Language, StudentState
from pocs.poc04_adaptive_teaching.session import AdaptiveSession


def _pick_language() -> Language:
    while True:
        value = input("Language (english/telugu/mixed) [english]: ").strip().lower() or "english"
        try:
            return Language(value)
        except ValueError:
            print("Choose english, telugu, or mixed.")


def _initial_question(lesson: str, topic: str) -> tuple[str, str]:
    marker = "PRACTICE QUESTION:"
    if marker in lesson:
        teaching, candidate = lesson.rsplit(marker, 1)
        if candidate.strip():
            return teaching.strip(), candidate.strip().splitlines()[0]
    return lesson, f"Explain {topic} in your own words and give one example."


def main() -> int:
    load_dotenv(REPO_ROOT / "pocs" / "poc03_bilingual_llm" / ".env")
    try:
        config = LLMConfig.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 1
    client = LLMClient(config)
    language = _pick_language()
    student_id = input("Student ID [learner]: ").strip() or "learner"
    topic = input("Topic to learn: ").strip()
    if not topic:
        print("Topic must not be empty.")
        return 1

    tutor = Tutor(client, language=language.value, level=Difficulty.BEGINNER.value)
    session = AdaptiveSession(
        StudentState(student_id=student_id, topic=topic, preferred_language=language),
        tutor,
        StructuredLLMEvaluator(client),
    )
    print("\nTeacher:", end=" ")
    try:
        lesson, question = _initial_question(session.teach_topic(), topic)
    except Exception as exc:
        print(f"Teaching request failed: {exc}")
        return 1
    print(lesson)
    while True:
        print(f"\nPractice question: {question}")
        try:
            answer = input("You (/language, /reset, /quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not answer:
            continue
        if answer.lower() in {"/quit", "/exit"}:
            return 0
        if answer.lower() == "/reset":
            session.reset()
            tutor.set_level(Difficulty.BEGINNER.value)
            print("Session reset. Mastery returned to 50%.")
            try:
                lesson, question = _initial_question(session.teach_topic(), topic)
                print("Teacher:", lesson)
            except Exception as exc:
                print(f"Teaching request failed: {exc}")
                return 1
            continue
        if answer.lower().startswith("/language"):
            value = answer.split(maxsplit=1)[1].lower() if len(answer.split()) == 2 else ""
            try:
                session.switch_language(value)
                print(f"Teaching language changed to {session.state.preferred_language.value}.")
            except ValueError:
                print("Choose /language english, /language telugu, or /language mixed.")
            continue

        try:
            reply = session.answer(
                question,
                answer,
                reference_answer=f"An accurate explanation of {topic} with a relevant example.",
            )
        except Exception as exc:
            print(f"Answer could not be processed: {exc}")
            continue
        decision = reply.decision
        print(f"\nAssessment: {decision.evaluation.outcome.value} — {decision.evaluation.feedback}")
        print(f"Mastery: {decision.mastery_score:.0%} | Difficulty: {decision.difficulty_after.value} | Strategy: {decision.strategy.value}")
        if decision.adjustment_reason:
            print(decision.adjustment_reason)
        if not decision.evaluated:
            print("The answer was not added to your performance history.")
        print("Teacher:", reply.teacher_message)
        question = session.next_question(decision)


if __name__ == "__main__":
    raise SystemExit(main())

