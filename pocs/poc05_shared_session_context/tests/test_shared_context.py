import pytest

from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import DeterministicEvaluator, ObjectiveQuestion, StructuredLLMEvaluator
from pocs.poc04_adaptive_teaching.models import Difficulty, Evaluation, Language, Outcome
from pocs.poc05_shared_session_context.context import Modality
from pocs.poc05_shared_session_context.manager import SessionEndedError, SessionManager, SessionNotFoundError
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime


class FakeProvider:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        prompt = messages[-1]["content"].lower()
        if "adaptation strategy: hint" in prompt:
            return "Hint: simplify both parts by the same number."
        return "A fraction represents equal parts of a whole."


class ScriptEvaluator:
    def __init__(self, results):
        self.results = iter(results)

    def evaluate(self, question, answer, reference_answer=""):
        return next(self.results)


def setup_session(*, student_id="student-1", language=Language.MIXED, history_limit=24, evaluator=None, provider=None):
    manager = SessionManager(max_history_events=history_limit)
    context = manager.create_session(student_id, "fractions", language, lesson_objective="Understand equivalent fractions")
    provider = provider or FakeProvider()
    tutor = Tutor(provider, language=language.value, level=context.difficulty.value)
    runtime = SharedSessionRuntime(manager, context.session_id, tutor, evaluator or DeterministicEvaluator())
    return manager, context, provider, tutor, runtime


def test_session_create_retrieve_and_recent_list():
    manager = SessionManager()
    created = manager.create_session("learner", "fractions", "mixed")
    assert manager.get_session(created.session_id) is created
    assert manager.list_recent_sessions("learner") == [created]
    assert created.student_id == "learner"
    assert created.language is Language.MIXED


def test_update_session_keeps_studentstate_as_source_of_truth():
    manager = SessionManager()
    context = manager.create_session("learner", "fractions")
    updated = manager.update_session(
        context.session_id,
        topic="decimals",
        language=Language.TELUGU,
        difficulty=Difficulty.INTERMEDIATE,
        lesson_objective="Compare place values",
        current_teaching_step="worked_example",
        adaptive_strategy="practice",
    )
    assert updated.topic == updated.learning_state.topic == "decimals"
    assert updated.language is updated.learning_state.preferred_language is Language.TELUGU
    assert updated.difficulty is updated.learning_state.difficulty is Difficulty.INTERMEDIATE
    assert updated.lesson_objective == "Compare place values"


def test_learning_progress_updates_reused_poc04_state():
    manager, context, _, _, runtime = setup_session()
    question = "Which fraction equals one half?"
    objective = ObjectiveQuestion(("2/4", "1/2"))
    incorrect = runtime.adaptive_answer(question, "3/4", objective=objective)
    corrected = runtime.adaptive_answer(question, "2/4", objective=objective)
    current = manager.get_teaching_context(context.session_id)
    assert incorrect.decision.evaluation.outcome is Outcome.INCORRECT
    assert corrected.decision.evaluation.outcome is Outcome.CORRECT
    assert current.mastery_score == pytest.approx(0.5)
    assert current.recent_answers[-1].answer == "2/4"
    assert current.difficulty is Difficulty.BEGINNER


def test_reset_clears_history_and_progress_but_preserves_session_identity():
    manager, context, _, tutor, runtime = setup_session()
    runtime.chat("Let's study equivalent fractions.")
    runtime.adaptive_answer("q", "wrong", objective=ObjectiveQuestion(("1/2",)))
    old_id = context.session_id
    reset = manager.reset_session(old_id)
    tutor.history.clear()
    assert reset.session_id == old_id
    assert reset.student_id == "student-1"
    assert reset.learning_state.mastery_score == 0.5
    assert reset.learning_state.attempts == 0
    assert reset.conversation_history == []
    assert reset.language is Language.MIXED


def test_end_session_marks_ended_and_blocks_mutations():
    manager = SessionManager()
    context = manager.create_session("learner", "fractions")
    ended = manager.end_session(context.session_id)
    assert ended.ended_at is not None
    assert manager.list_recent_sessions() == []
    assert manager.list_recent_sessions(include_ended=True) == [ended]
    with pytest.raises(SessionEndedError):
        manager.update_session(context.session_id, topic="decimals")


def test_recent_conversation_turns_are_bounded():
    manager, context, _, _, runtime = setup_session(history_limit=4)
    for n in range(3):
        runtime.chat(f"chat message {n}")
    turns = manager.list_recent_turns(context.session_id, limit=20)
    assert len(turns) == 4
    assert turns[0].content == "chat message 1"
    assert turns[-2].content == "chat message 2"


def test_chat_to_voice_transcript_continuity_in_poc03_context():
    _, context, provider, _, runtime = setup_session()
    runtime.chat("Explain fractions in a simple way.")
    runtime.voice_transcript("Follow-up: what does the denominator show?")
    second_call = provider.calls[1]
    assert any(message["content"] == "Explain fractions in a simple way." for message in second_call)
    assert any("A fraction represents" in message["content"] for message in second_call)
    assert any(turn.modality is Modality.VOICE_TRANSCRIPT for turn in context.conversation_history)


def test_language_switch_persists_and_changes_poc03_prompt():
    manager, context, provider, _, runtime = setup_session(language=Language.ENGLISH)
    runtime.switch_language("telugu")
    runtime.chat("భిన్నం అంటే ఏమిటి?")
    assert manager.get_session(context.session_id).language is Language.TELUGU
    assert "Telugu" in provider.calls[0][0]["content"]


@pytest.mark.parametrize("language, prompt_token", [
    (Language.ENGLISH, "English"),
    (Language.TELUGU, "Telugu"),
    (Language.MIXED, "code-mixing"),
])
def test_each_supported_language_persists_into_tutor_context(language, prompt_token):
    manager, context, provider, _, runtime = setup_session(language=language)
    runtime.chat("Continue the lesson.")
    assert manager.get_session(context.session_id).language is language
    assert prompt_token in provider.calls[0][0]["content"]


def test_hint_and_adaptive_strategy_are_persisted_in_context():
    manager, context, _, _, runtime = setup_session()
    result = runtime.adaptive_answer(
        "Which fraction equals one half?", "3/4", objective=ObjectiveQuestion(("2/4", "1/2"))
    )
    current = manager.get_teaching_context(context.session_id)
    assert result.decision.strategy.value == "hint"
    assert current.hint_usage == 1
    assert current.adaptive_strategy == "hint"
    assert current.current_teaching_step == "hint"
    assert current.recent_turns[-2].metadata["outcome"] == "incorrect"


def test_multiple_students_have_isolated_learning_and_conversation():
    manager, first, _, _, first_runtime = setup_session(student_id="a")
    second_context = manager.create_session("b", "fractions", Language.MIXED)
    second_tutor = Tutor(FakeProvider(), language="mixed")
    second_runtime = SharedSessionRuntime(manager, second_context.session_id, second_tutor, DeterministicEvaluator())
    first_runtime.adaptive_answer("q", "wrong", objective=ObjectiveQuestion(("1/2",)))
    first_runtime.chat("first learner's chat")
    assert manager.get_session(first.session_id).learning_state.attempts == 1
    assert manager.get_session(second_context.session_id).learning_state.attempts == 0
    assert manager.get_session(second_context.session_id).conversation_history == []


def test_invalid_session_ids_fail_safely():
    manager = SessionManager()
    with pytest.raises(SessionNotFoundError, match="session not found"):
        manager.get_session("missing")
    with pytest.raises(SessionNotFoundError):
        manager.list_recent_turns("missing")


def test_visual_events_are_saved_but_not_sent_as_chat_history():
    manager, context, provider, _, runtime = setup_session()
    runtime.record_visual_event("Fractions diagram shown", {"asset_id": "diagram-1"})
    runtime.chat("What does this picture show?")
    assert any(turn.modality is Modality.VISUAL_LESSON for turn in context.conversation_history)
    assert all("Fractions diagram shown" not in message["content"] for message in provider.calls[0])


def test_provider_failure_does_not_store_failed_chat_turn():
    provider = FakeProvider(error=RuntimeError("provider unavailable"))
    manager, context, _, _, runtime = setup_session(provider=provider)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        runtime.chat("A question")
    assert manager.get_session(context.session_id).conversation_history == []


def test_evaluation_and_tutor_provider_failure_is_safe_and_does_not_add_mastery():
    provider = FakeProvider(error=RuntimeError("provider unavailable"))
    manager, context, _, _, runtime = setup_session(
        provider=provider,
        evaluator=StructuredLLMEvaluator(provider),
    )
    response = runtime.adaptive_answer("Explain a fraction", "maybe")
    current = manager.get_teaching_context(context.session_id)
    assert response.decision.evaluated is False
    assert current.mastery_score == 0.5
    assert context.learning_state.attempts == 0
    assert "unavailable" in response.response


def test_reset_runtime_clears_poc03_history_and_restarts_difficulty():
    manager, context, _, tutor, runtime = setup_session()
    runtime.chat("hello")
    manager.update_session(context.session_id, difficulty=Difficulty.ADVANCED)
    tutor.set_level("advanced")
    runtime.reset()
    current = manager.get_session(context.session_id)
    assert current.learning_state.difficulty is Difficulty.BEGINNER
    assert current.learning_state.mastery_score == 0.5
    assert current.conversation_history == []
    assert tutor.history == []


def test_list_recent_sessions_filters_student_and_ended_state():
    manager = SessionManager()
    first = manager.create_session("a", "fractions")
    second = manager.create_session("b", "decimals")
    manager.end_session(first.session_id)
    assert manager.list_recent_sessions(student_id="a") == []
    assert manager.list_recent_sessions(student_id="a", include_ended=True)[0].session_id == first.session_id
    assert manager.list_recent_sessions(limit=1)[0].session_id == second.session_id


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_history_limits_are_rejected(limit):
    manager = SessionManager()
    context = manager.create_session("a", "fractions")
    with pytest.raises(ValueError):
        manager.list_recent_turns(context.session_id, limit)


def test_reset_rejects_ended_session():
    manager = SessionManager()
    context = manager.create_session("a", "fractions")
    manager.end_session(context.session_id)
    with pytest.raises(SessionEndedError):
        manager.reset_session(context.session_id)
