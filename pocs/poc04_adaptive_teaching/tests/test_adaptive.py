import json

import pytest

from pocs.poc03_bilingual_llm.prompts import build_system_prompt
from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.adaptation import AdaptiveTeachingEngine
from pocs.poc04_adaptive_teaching.evaluation import (
    DeterministicEvaluator,
    EvaluationError,
    ObjectiveQuestion,
    StructuredLLMEvaluator,
)
from pocs.poc04_adaptive_teaching.models import Difficulty, Evaluation, Language, Outcome, Strategy, StudentState
from pocs.poc04_adaptive_teaching.session import AdaptiveSession


class ScriptEvaluator:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def evaluate(self, question, answer, reference_answer=""):
        outcome = next(self.outcomes)
        return Evaluation(outcome, f"{outcome.value} feedback", "Test explanation")


class BadEvaluator:
    def evaluate(self, question, answer, reference_answer=""):
        raise RuntimeError("private provider detail")


class FakeProvider:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.responses.pop(0)


def state(difficulty=Difficulty.BEGINNER, language=Language.ENGLISH, student="learner"):
    return StudentState(student_id=student, topic="fractions", difficulty=difficulty, preferred_language=language)


def engine(outcomes=(), difficulty=Difficulty.BEGINNER):
    return AdaptiveTeachingEngine(state(difficulty), ScriptEvaluator(outcomes))


def submit_many(subject, outcomes):
    result = None
    for index, outcome in enumerate(outcomes):
        result = subject.submit_answer("Explain a fraction", outcome.value)
    return result


def test_objective_correct_answer():
    result = DeterministicEvaluator().evaluate_objective(" 1 / 2! ", ObjectiveQuestion(("1/2", "one half")))
    assert result.outcome is Outcome.CORRECT


def test_objective_incorrect_answer():
    result = DeterministicEvaluator().evaluate_objective("three quarters", ObjectiveQuestion(("1/2",)))
    assert result.outcome is Outcome.INCORRECT


def test_objective_partially_correct_answer():
    result = DeterministicEvaluator().evaluate_objective("numerator", ObjectiveQuestion(("top number",), ("numerator",)))
    assert result.outcome is Outcome.PARTIALLY_CORRECT


def test_ambiguous_answer_does_not_change_mastery():
    result = DeterministicEvaluator().evaluate_objective("not sure", ObjectiveQuestion(("1/2",)))
    subject = engine()
    decision = subject.submit_answer("fraction?", "not sure", objective=ObjectiveQuestion(("1/2",)))
    assert result.outcome is Outcome.AMBIGUOUS
    assert decision.mastery_score == 0.5
    assert subject.state.ambiguous_count == 1


def test_first_mistake_selects_hint_and_tracks_usage():
    subject = engine([Outcome.INCORRECT])
    decision = subject.submit_answer("q", "wrong")
    assert decision.strategy is Strategy.HINT
    assert subject.state.hint_usage == 1


def test_repeated_mistakes_simplify_then_review_prerequisite():
    subject = engine([Outcome.INCORRECT] * 3)
    decisions = [subject.submit_answer("q", "wrong") for _ in range(3)]
    assert [item.strategy for item in decisions] == [Strategy.HINT, Strategy.SIMPLER_EXAMPLE, Strategy.PREREQUISITE_REVIEW]


def test_three_strong_answers_increase_difficulty():
    subject = engine([Outcome.CORRECT] * 3)
    decision = submit_many(subject, [Outcome.CORRECT] * 3)
    assert decision.difficulty_before is Difficulty.BEGINNER
    assert decision.difficulty_after is Difficulty.INTERMEDIATE
    assert decision.adjustment_reason


def test_three_low_scores_decrease_difficulty():
    subject = engine([Outcome.INCORRECT] * 3, Difficulty.ADVANCED)
    decision = submit_many(subject, [Outcome.INCORRECT] * 3)
    assert decision.difficulty_after is Difficulty.INTERMEDIATE


def test_difficulty_waits_for_minimum_evidence():
    subject = engine([Outcome.CORRECT] * 2)
    decision = submit_many(subject, [Outcome.CORRECT] * 2)
    assert decision.difficulty_after is Difficulty.BEGINNER


def test_mastery_uses_smoothed_correct_partial_incorrect_scores():
    subject = engine([Outcome.CORRECT, Outcome.PARTIALLY_CORRECT, Outcome.INCORRECT])
    for result in [Outcome.CORRECT, Outcome.PARTIALLY_CORRECT, Outcome.INCORRECT]:
        decision = subject.submit_answer("q", result.value)
    assert decision.mastery_score == pytest.approx((2 + 1 + 0.5) / (4 + 3))
    assert 0 <= decision.mastery_score <= 1


def test_beginner_gets_stepwise_teaching():
    subject = engine([Outcome.CORRECT], Difficulty.BEGINNER)
    assert subject.submit_answer("q", "correct").strategy is Strategy.STEP_BY_STEP


def test_advanced_strong_mastery_gets_challenge():
    subject = engine([Outcome.CORRECT] * 6, Difficulty.ADVANCED)
    decision = submit_many(subject, [Outcome.CORRECT] * 6)
    assert decision.mastery_score == pytest.approx(0.8)
    assert decision.strategy is Strategy.CHALLENGE_PRACTICE


@pytest.mark.parametrize("language, expected", [
    (Language.ENGLISH, "English"),
    (Language.TELUGU, "Telugu"),
    (Language.MIXED, "code-mixing"),
])
def test_teaching_prompt_supports_each_language(language, expected):
    subject = state(language=language)
    assert expected in build_system_prompt(subject.preferred_language.value, "beginner")


def test_language_switch_updates_engine_and_poc03_tutor():
    provider = FakeProvider(responses=["Lesson", "Follow-up in Telugu"])
    tutor = Tutor(provider)
    session = AdaptiveSession(state(), tutor, ScriptEvaluator([Outcome.CORRECT]))
    session.teach_topic()
    session.switch_language("telugu")
    session.answer("q", "answer")
    assert session.state.preferred_language is Language.TELUGU
    assert "English" in provider.calls[0][0]["content"]
    assert "Telugu" in provider.calls[1][0]["content"]


def test_difficulty_promotion_updates_poc03_tutor_prompt():
    provider = FakeProvider(responses=["Lesson", "Response 1", "Response 2", "Response 3"])
    tutor = Tutor(provider)
    session = AdaptiveSession(state(), tutor, ScriptEvaluator([Outcome.CORRECT] * 3))
    session.teach_topic()
    for index in range(3):
        session.answer(f"q{index}", "correct")
    assert session.state.difficulty is Difficulty.INTERMEDIATE
    assert "intermediate learner" in provider.calls[3][0]["content"]


def test_ambiguous_response_does_not_trigger_stale_performance_promotion():
    subject = engine([Outcome.CORRECT, Outcome.CORRECT, Outcome.CORRECT, Outcome.AMBIGUOUS])
    submit_many(subject, [Outcome.CORRECT] * 3)
    previous_level = subject.state.difficulty
    decision = subject.submit_answer("q", "unclear")
    assert decision.difficulty_after is previous_level


def test_two_students_have_isolated_state():
    first = engine([Outcome.CORRECT])
    second = AdaptiveTeachingEngine(state(student="other"), ScriptEvaluator([Outcome.INCORRECT]))
    first.submit_answer("q", "yes")
    second.submit_answer("q", "no")
    assert first.state.student_id != second.state.student_id
    assert first.state.mastery_score > second.state.mastery_score
    assert first.state.attempts == second.state.attempts == 1


@pytest.mark.parametrize("raw", [
    "not json",
    "{}",
    json.dumps({"outcome": "wrong", "feedback": "x", "explanation": "y"}),
    json.dumps({"outcome": "correct", "feedback": "", "explanation": "y"}),
    json.dumps({"outcome": "correct", "feedback": "x", "explanation": "y", "confidence": 5}),
    json.dumps({"outcome": "correct", "feedback": "x", "explanation": "y", "extra": "field"}),
])
def test_malformed_llm_response_fails_safely(raw):
    with pytest.raises(EvaluationError):
        StructuredLLMEvaluator.parse(raw)


def test_llm_evaluation_parses_valid_structured_response():
    provider = FakeProvider([json.dumps({"outcome": "partially_correct", "feedback": "Good start", "explanation": "Add an example", "confidence": 0.8})])
    result = StructuredLLMEvaluator(provider).evaluate("q", "a", "reference")
    assert result.outcome is Outcome.PARTIALLY_CORRECT
    assert result.confidence == pytest.approx(0.8)


def test_provider_failure_is_not_recorded_and_is_safe():
    subject = AdaptiveTeachingEngine(state(), BadEvaluator())
    decision = subject.submit_answer("q", "a")
    assert not decision.evaluated
    assert decision.evaluation.outcome is Outcome.AMBIGUOUS
    assert "private provider detail" not in decision.evaluation.feedback
    assert subject.state.attempts == 0


def test_session_reset_clears_progress_and_rotates_session_id():
    provider = FakeProvider(responses=["First answer", "second answer"])
    tutor = Tutor(provider)
    session = AdaptiveSession(state(), tutor, ScriptEvaluator([Outcome.CORRECT]))
    old_session_id = session.state.session_id
    session.answer("q", "a")
    session.reset()
    assert session.state.session_id != old_session_id
    assert session.state.attempts == 0
    assert session.state.mastery_score == 0.5
    assert session.state.difficulty is Difficulty.BEGINNER
    assert tutor.history == []

