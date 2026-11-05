"""Session lifecycle and context operations, independent of any database."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TypeVar

from pocs.poc04_adaptive_teaching.models import Difficulty, Evaluation, Language, StudentState

from .context import ConversationTurn, Modality, SessionContext, TeachingContext
from .store import InMemorySessionStore, SessionStore

T = TypeVar("T")


class SessionNotFoundError(LookupError):
    pass


class SessionEndedError(RuntimeError):
    pass


class SessionManager:
    def __init__(self, store: SessionStore | None = None, max_history_events: int = 24):
        if max_history_events < 2:
            raise ValueError("max_history_events must be at least two")
        self.store = store or InMemorySessionStore()
        self.max_history_events = max_history_events

    def create_session(
        self,
        student_id: str,
        topic: str,
        language: Language | str = Language.ENGLISH,
        difficulty: Difficulty | str = Difficulty.BEGINNER,
        lesson_objective: str = "",
    ) -> SessionContext:
        now = datetime.now(timezone.utc)
        context = SessionContext(
            learning_state=StudentState(
                student_id=student_id,
                topic=topic,
                preferred_language=Language(language),
                difficulty=Difficulty(difficulty),
            ),
            lesson_objective=lesson_objective.strip(),
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self.store.create(context)
        return context

    def get_session(self, session_id: str) -> SessionContext:
        context = self.store.get(session_id)
        if context is None:
            raise SessionNotFoundError("session not found")
        return context

    def update_session(
        self,
        session_id: str,
        *,
        topic: str | None = None,
        language: Language | str | None = None,
        difficulty: Difficulty | str | None = None,
        lesson_objective: str | None = None,
        current_teaching_step: str | None = None,
        adaptive_strategy: str | None = None,
    ) -> SessionContext:
        context = self._get_active(session_id)
        next_topic = topic.strip() if topic is not None else None
        if next_topic == "":
            raise ValueError("topic must not be empty")
        next_language = Language(language) if language is not None else None
        next_difficulty = Difficulty(difficulty) if difficulty is not None else None
        if next_topic is not None:
            context.learning_state.topic = next_topic
        if next_language is not None:
            context.learning_state.preferred_language = next_language
        if next_difficulty is not None:
            context.learning_state.difficulty = next_difficulty
        if lesson_objective is not None:
            context.lesson_objective = lesson_objective.strip()
        if current_teaching_step is not None:
            context.current_teaching_step = current_teaching_step.strip()
        if adaptive_strategy is not None:
            context.adaptive_strategy = adaptive_strategy.strip()
        self._touch(context)
        return context

    def reset_session(
        self,
        session_id: str,
        *,
        topic: str | None = None,
        language: Language | str | None = None,
    ) -> SessionContext:
        context = self._get_active(session_id)
        old = context.learning_state
        context.learning_state = StudentState(
            student_id=old.student_id,
            topic=topic.strip() if topic is not None else old.topic,
            preferred_language=Language(language) if language is not None else old.preferred_language,
            difficulty=Difficulty.BEGINNER,
            session_id=old.session_id,
            history_limit=old.history_limit,
        )
        context.conversation_history.clear()
        context.lesson_objective = ""
        context.current_teaching_step = ""
        context.adaptive_strategy = ""
        context.last_reset_at = datetime.now(timezone.utc)
        self._touch(context)
        return context

    def end_session(self, session_id: str) -> SessionContext:
        context = self._get_active(session_id)
        context.ended_at = datetime.now(timezone.utc)
        self._touch(context)
        return context

    def list_recent_sessions(self, student_id: str | None = None, limit: int = 20, include_ended: bool = False) -> list[SessionContext]:
        if limit < 1:
            raise ValueError("limit must be positive")
        sessions = [
            item for item in self.store.list_all()
            if (student_id is None or item.student_id == student_id) and (include_ended or item.ended_at is None)
        ]
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return sessions[:limit]

    def record_turn(
        self,
        session_id: str,
        role: str,
        modality: Modality | str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> ConversationTurn:
        context = self._get_active(session_id)
        turn = ConversationTurn(role=role, modality=Modality(modality), content=content, metadata=metadata or {})
        context.conversation_history.append(turn)
        context.conversation_history = context.conversation_history[-self.max_history_events:]
        self._touch(context)
        return turn

    def list_recent_turns(self, session_id: str, limit: int = 12) -> list[ConversationTurn]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return self.get_session(session_id).conversation_history[-limit:]

    def update_learning_progress(self, session_id: str, update: Callable[[StudentState], T]) -> T:
        """Apply an in-place learner-state update; SQL adapters can wrap it in a transaction."""
        context = self._get_active(session_id)
        result = update(context.learning_state)
        self._touch(context)
        return result

    def get_teaching_context(self, session_id: str, recent_turn_limit: int = 12) -> TeachingContext:
        context = self.get_session(session_id)
        if recent_turn_limit < 1:
            raise ValueError("recent_turn_limit must be positive")
        state = context.learning_state
        return TeachingContext(
            session_id=context.session_id,
            student_id=context.student_id,
            topic=state.topic,
            language=state.preferred_language,
            difficulty=state.difficulty,
            mastery_score=state.mastery_score,
            hint_usage=state.hint_usage,
            lesson_objective=context.lesson_objective,
            current_teaching_step=context.current_teaching_step,
            adaptive_strategy=context.adaptive_strategy,
            recent_answers=tuple(state.recent_answers),
            recent_turns=tuple(context.conversation_history[-recent_turn_limit:]),
            created_at=context.created_at,
            updated_at=context.updated_at,
            ended_at=context.ended_at,
        )

    def _get_active(self, session_id: str) -> SessionContext:
        context = self.get_session(session_id)
        if context.ended_at is not None:
            raise SessionEndedError("session has ended")
        return context

    def _touch(self, context: SessionContext) -> None:
        now = datetime.now(timezone.utc)
        context.updated_at = now
        context.last_activity_at = now
        self.store.save(context)
