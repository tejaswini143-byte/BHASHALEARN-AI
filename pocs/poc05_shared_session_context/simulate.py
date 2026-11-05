"""Offline chat-to-voice session walkthrough using mocked POC-03 responses."""
from __future__ import annotations

from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import DeterministicEvaluator, ObjectiveQuestion
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc05_shared_session_context.context import Modality
from pocs.poc05_shared_session_context.manager import SessionManager
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime


class DemoProvider:
    def __init__(self):
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        prompt = messages[-1]["content"].lower()
        if "adaptation strategy: hint" in prompt:
            return "Hint: divide the numerator and denominator by the same number."
        if "correct" in prompt or "strategy: step_by_step" in prompt:
            return "Good correction. Two fourths simplifies to one half."
        if "follow-up" in prompt or "voice transcript" in prompt:
            return "The denominator counts equal parts in the whole."
        return "A fraction names equal parts of a whole. PRACTICE QUESTION: Which fraction equals one half?"


def main() -> None:
    manager = SessionManager(max_history_events=12)
    context = manager.create_session(
        "student-demo",
        "fractions",
        Language.MIXED,
        lesson_objective="Recognize equivalent fractions.",
    )
    provider = DemoProvider()
    tutor = Tutor(provider, language=Language.MIXED.value)
    runtime = SharedSessionRuntime(manager, context.session_id, tutor, DeterministicEvaluator())

    lesson = runtime.start_lesson()
    print(f"1. Session created: {context.session_id} | {context.student_id} | mixed | fractions")
    print(f"2. Chat lesson: {lesson.response}")

    question = "Which fraction is equivalent to 1/2?"
    objective = ObjectiveQuestion(("2/4", "4/8", "1/2"))
    wrong = runtime.adaptive_answer(question, "3/4", objective=objective)
    print(f"3. Incorrect answer: {wrong.decision.evaluation.outcome.value}; strategy={wrong.decision.strategy.value}")
    print(f"4. Adaptive hint: {wrong.response}")

    corrected = runtime.adaptive_answer(question, "2/4", objective=objective)
    print(f"5. Corrected answer: {corrected.decision.evaluation.outcome.value}; mastery={corrected.decision.mastery_score:.0%}")

    voice = runtime.voice_transcript("Follow-up: what does the denominator mean here?")
    print(f"6. Simulated voice transcript: {voice.response}")
    follow_up_messages = provider.calls[-1]
    has_chat_history = any(
        message["role"] == "user" and "equivalent to 1/2" in message["content"]
        for message in follow_up_messages
    )
    voice_turns = manager.list_recent_turns(context.session_id)
    assert has_chat_history
    assert any(turn.modality is Modality.VOICE_TRANSCRIPT for turn in voice_turns)

    current = manager.get_teaching_context(context.session_id)
    print(
        f"7. Context preserved: topic={current.topic}, language={current.language.value}, "
        f"difficulty={current.difficulty.value}, mastery={current.mastery_score:.0%}, "
        f"hint_usage={current.hint_usage}, turns={len(current.recent_turns)}"
    )
    runtime.end()
    print(f"8. Session ended: {manager.get_session(context.session_id).ended_at is not None}")


if __name__ == "__main__":
    main()
