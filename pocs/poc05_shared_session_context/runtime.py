"""Connect shared session storage to the existing POC-03 Tutor and POC-04 engine."""
from __future__ import annotations

from dataclasses import dataclass

from pocs.poc04_adaptive_teaching.adaptation import AdaptiveTeachingEngine, TeachingDecision, adaptive_instruction
from pocs.poc04_adaptive_teaching.evaluation import AnswerEvaluator, ObjectiveQuestion
from pocs.poc04_adaptive_teaching.models import Difficulty, Language

from .context import Modality
from .manager import SessionManager


@dataclass(frozen=True)
class SessionInteraction:
    response: str
    decision: TeachingDecision | None = None


class SharedSessionRuntime:
    """A provider-facing adapter whose authoritative memory stays in SessionManager."""

    def __init__(self, manager: SessionManager, session_id: str, tutor, evaluator: AnswerEvaluator):
        self.manager = manager
        self.session_id = session_id
        self.tutor = tutor
        self.evaluator = evaluator
        context = manager.get_session(session_id)
        self._set_tutor_preferences(context.language, context.difficulty)

    def start_lesson(
        self,
        topic: str | None = None,
        objective: str = "",
        practice_question: str | None = None,
    ) -> SessionInteraction:
        updates = {"current_teaching_step": "introduction"}
        if topic is not None:
            updates["topic"] = topic
        if objective:
            updates["lesson_objective"] = objective
        context = self.manager.update_session(self.session_id, **updates)
        visible_input = f"Start lesson: {context.topic}. Objective: {context.lesson_objective or 'understand the key idea'}"
        if practice_question:
            visible_input += f" Practice question: {practice_question}"
        practice_instruction = (
            f"End with this exact practice question: {practice_question}. Do not replace it with a different question."
            if practice_question
            else "End with one practice question."
        )
        prompt = (
            f"Teach {context.topic!r} to a {context.difficulty.value} learner. Objective: "
            f"{context.lesson_objective or 'understand the key idea'}. Give a concise step-by-step explanation "
            f"with one example. {practice_instruction}"
        )
        return SessionInteraction(self._ask_and_record(prompt, visible_input, Modality.CHAT))

    def chat(self, message: str) -> SessionInteraction:
        return SessionInteraction(self._ask_and_record(message, message, Modality.CHAT))

    def voice_transcript(self, transcript: str) -> SessionInteraction:
        if not transcript.strip():
            raise ValueError("voice transcript must not be empty")
        response = self._ask_and_record(
            transcript,
            transcript,
            Modality.VOICE_TRANSCRIPT,
            metadata={"source": "simulated_stt"},
        )
        return SessionInteraction(response)

    def adaptive_answer(
        self,
        question: str,
        answer: str,
        reference_answer: str = "",
        objective: ObjectiveQuestion | None = None,
        source: Modality | str = Modality.CHAT,
    ) -> SessionInteraction:
        modality = Modality(source)
        if modality not in {Modality.CHAT, Modality.VOICE_TRANSCRIPT}:
            raise ValueError("answer source must be chat or voice_transcript")

        decision = self.manager.update_learning_progress(
            self.session_id,
            lambda state: AdaptiveTeachingEngine(state, self.evaluator).submit_answer(
                question, answer, reference_answer, objective
            ),
        )
        state = self.manager.get_session(self.session_id).learning_state
        self.manager.update_session(
            self.session_id,
            current_teaching_step=decision.strategy.value,
            adaptive_strategy=decision.strategy.value,
        )
        self._sync_tutor_history()
        response = "The teaching response is unavailable right now. Your evaluated answer is saved."
        try:
            response = self.tutor.ask(adaptive_instruction(decision, state, question, answer))
        except Exception:
            # The evaluated progress remains valid even when the follow-up generation fails.
            pass
        self.manager.record_turn(
            self.session_id,
            "user",
            modality,
            f"Question: {question}\nStudent answer: {answer}",
            {"outcome": decision.evaluation.outcome.value},
        )
        self.manager.record_turn(self.session_id, "assistant", Modality.ADAPTIVE_TUTOR, response)
        self._set_tutor_preferences(state.preferred_language, state.difficulty)
        return SessionInteraction(response, decision)

    def switch_language(self, language: Language | str) -> None:
        selected = Language(language)
        context = self.manager.update_session(self.session_id, language=selected)
        self.tutor.set_language(context.language.value)

    def record_visual_event(self, description: str, metadata: dict[str, str] | None = None) -> None:
        self.manager.record_turn(
            self.session_id,
            "system",
            Modality.VISUAL_LESSON,
            description,
            metadata,
        )

    def reset(self) -> None:
        context = self.manager.reset_session(self.session_id)
        if hasattr(self.tutor, "history"):
            self.tutor.history.clear()
        self._set_tutor_preferences(context.language, context.difficulty)

    def end(self):
        return self.manager.end_session(self.session_id)

    def _ask_and_record(
        self,
        prompt: str,
        visible_input: str,
        modality: Modality,
        metadata: dict[str, str] | None = None,
    ) -> str:
        if not visible_input.strip():
            raise ValueError("message must not be empty")
        self._sync_tutor_history()
        response = self.tutor.ask(prompt)
        self.manager.record_turn(self.session_id, "user", modality, visible_input, metadata)
        self.manager.record_turn(self.session_id, "assistant", Modality.ADAPTIVE_TUTOR, response)
        return response

    def _sync_tutor_history(self) -> None:
        context = self.manager.get_session(self.session_id)
        self._set_tutor_preferences(context.language, context.difficulty)
        history = [
            {"role": turn.role, "content": turn.content}
            for turn in context.conversation_history
            if turn.modality is not Modality.VISUAL_LESSON and turn.role in {"user", "assistant"}
        ]
        max_messages = getattr(self.tutor, "max_turns", 6) * 2
        self.tutor.history[:] = history[-max_messages:]

    def _set_tutor_preferences(self, language: Language, difficulty: Difficulty) -> None:
        self.tutor.set_language(language.value)
        if hasattr(self.tutor, "set_level"):
            self.tutor.set_level(difficulty.value)
