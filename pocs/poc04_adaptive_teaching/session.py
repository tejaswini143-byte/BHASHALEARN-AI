"""Bridge the provider-independent adaptive engine to the existing POC-03 Tutor."""
from __future__ import annotations

from dataclasses import dataclass

from .adaptation import AdaptiveTeachingEngine, TeachingDecision, adaptive_instruction
from .evaluation import AnswerEvaluator, ObjectiveQuestion
from .models import Difficulty, Language, StudentState, Strategy


@dataclass(frozen=True)
class SessionReply:
    decision: TeachingDecision
    teacher_message: str


class AdaptiveSession:
    def __init__(self, state: StudentState, tutor, evaluator: AnswerEvaluator, difficulty: Difficulty | None = None):
        if difficulty is not None:
            state.difficulty = difficulty
        self.engine = AdaptiveTeachingEngine(state, evaluator)
        self.tutor = tutor

    @property
    def state(self) -> StudentState:
        return self.engine.state

    def switch_language(self, language: Language | str) -> None:
        selected = Language(language)
        self.engine.set_language(selected)
        self.tutor.set_language(selected.value)

    def teach_topic(self) -> str:
        if hasattr(self.tutor, "set_level"):
            self.tutor.set_level(self.state.difficulty.value)
        return self.tutor.ask(
            f"Teach the topic {self.state.topic!r} for a {self.state.difficulty.value} learner. "
            "Use a short step-by-step explanation and one worked example. Finish with exactly one practice question "
            "on its own final line, prefixed with the exact label PRACTICE QUESTION:."
        )

    def answer(
        self,
        question: str,
        answer: str,
        reference_answer: str = "",
        objective: ObjectiveQuestion | None = None,
        hint_used: bool = False,
    ) -> SessionReply:
        decision = self.engine.submit_answer(question, answer, reference_answer, objective, hint_used)
        if hasattr(self.tutor, "set_level"):
            self.tutor.set_level(decision.difficulty_after.value)
        try:
            teacher_message = self.tutor.ask(adaptive_instruction(decision, self.state, question, answer))
        except Exception:
            teacher_message = "The teaching response is unavailable right now. You can retry or reset the session."
        return SessionReply(decision, teacher_message)

    def next_question(self, decision: TeachingDecision) -> str:
        if decision.strategy in {Strategy.PRACTICE, Strategy.CHALLENGE_PRACTICE}:
            return f"Apply {self.state.topic} to a new example and explain your reasoning."
        return f"In your own words, explain one key idea about {self.state.topic}."

    def reset(self) -> None:
        self.engine.reset_session()
        if hasattr(self.tutor, "history"):
            self.tutor.history.clear()

