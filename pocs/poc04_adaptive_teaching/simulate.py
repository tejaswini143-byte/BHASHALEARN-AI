"""Deterministic profiles showing how POC-04 adapts to different learners."""
from __future__ import annotations

from collections import deque

from pocs.poc04_adaptive_teaching.adaptation import AdaptiveTeachingEngine
from pocs.poc04_adaptive_teaching.models import Difficulty, Evaluation, Outcome, StudentState


class ScriptedEvaluator:
    def __init__(self, outcomes: list[Outcome]):
        self.outcomes = deque(outcomes)

    def evaluate(self, question: str, answer: str, reference_answer: str = "") -> Evaluation:
        outcome = self.outcomes.popleft()
        return Evaluation(outcome, f"Simulated {outcome.value} feedback.", "Deterministic profile simulation.")


PROFILES = [
    ("Student A: Struggling learner", Difficulty.INTERMEDIATE,
     [Outcome.INCORRECT] * 3),
    ("Student B: Improving learner", Difficulty.BEGINNER,
     [Outcome.PARTIALLY_CORRECT, Outcome.CORRECT, Outcome.CORRECT, Outcome.CORRECT]),
    ("Student C: Strong learner", Difficulty.INTERMEDIATE,
     [Outcome.CORRECT] * 6),
]


def main() -> None:
    for label, start_difficulty, outcomes in PROFILES:
        engine = AdaptiveTeachingEngine(
            StudentState(student_id=label.split(":")[0], topic="fractions", difficulty=start_difficulty),
            ScriptedEvaluator(outcomes),
        )
        decisions = []
        for index, outcome in enumerate(outcomes, 1):
            decision = engine.submit_answer(f"Practice {index}", f"simulated {outcome.value}")
            decisions.append(decision)
        last = decisions[-1]
        transitions = [
            f"{item.difficulty_before.value}->{item.difficulty_after.value}"
            for item in decisions if item.difficulty_before != item.difficulty_after
        ] or ["none"]
        print(f"{label}: mastery={last.mastery_score:.0%}; difficulty={last.difficulty_after.value}; "
              f"last_strategy={last.strategy.value}; transitions={', '.join(transitions)}; "
              f"hint_usage={engine.state.hint_usage}")


if __name__ == "__main__":
    main()

