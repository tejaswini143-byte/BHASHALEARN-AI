"""Small, deterministic objective question bank. Unsupported topics stay unassessed."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    id: str
    topic_key: str
    prompt: str
    options: tuple[str, ...]
    answer: str
    explanation: str


BANK = {
    "equivalent fractions": (
        Question("fractions-01", "equivalent fractions", "Which fraction is equivalent to 1/2?", ("2/4", "2/3", "3/5", "4/5"), "2/4", "Multiply the numerator and denominator of 1/2 by 2 to get 2/4."),
        Question("fractions-02", "equivalent fractions", "Which fraction is equivalent to 3/4?", ("6/8", "6/10", "4/6", "9/16"), "6/8", "Multiply both 3 and 4 by 2 to get 6/8."),
        Question("fractions-03", "equivalent fractions", "Which fraction is equivalent to 2/3?", ("4/6", "3/5", "2/5", "6/8"), "4/6", "Multiply the numerator and denominator by 2 to get 4/6."),
    ),
    "dijkstra shortest path": (
        Question("dijkstra-01", "dijkstra shortest path", "In the built-in graph, starting at A, which unvisited node has the smallest tentative distance after visiting A?", ("B", "C", "D", "F"), "C", "C has distance 2 from A, while B has distance 4."),
        Question("dijkstra-02", "dijkstra shortest path", "In the built-in graph, what is the tentative distance from A to B after visiting A?", ("2", "4", "5", "8"), "4", "The direct edge A–B has weight 4."),
        Question("dijkstra-03", "dijkstra shortest path", "After visiting C from A, what is the improved tentative distance to B through C?", ("2", "3", "4", "6"), "3", "A to C costs 2 and C to B costs 1, so the route costs 3."),
    ),
}


def question_for(topic_key: str, sequence: int) -> Question | None:
    questions = BANK.get(topic_key)
    if not questions:
        return None
    return questions[(max(1, sequence) - 1) % len(questions)]
