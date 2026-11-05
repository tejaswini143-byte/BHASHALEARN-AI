"""Small, server-authored objective checks for the existing visual topics."""
from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.adaptive_learning import normalize_topic


@dataclass(frozen=True)
class ObjectiveAssessment:
    question_code: str
    question: str
    choices: dict[str, str]
    expected_answer: str
    misconception_map: dict[str, str]


def topic_kind(topic: str) -> str | None:
    _, key = normalize_topic(topic)
    if "fraction" in key or "భిన్నం" in key:
        return "fractions"
    if "dijkstra" in key or "shortest path" in key:
        return "dijkstra"
    return None


def _rotate(values: list[tuple[str, str]], sequence: int) -> list[tuple[str, str]]:
    offset = sequence % len(values)
    return values[offset:] + values[:offset]


def make_assessment(topic: str, sequence: int, language: str) -> ObjectiveAssessment | None:
    kind = topic_kind(topic)
    if kind == "fractions":
        numerator = sequence % 9 + 1
        denominator = numerator + 2 + (sequence // 9) % 7
        correct = f"{numerator * 2}/{denominator * 2}"
        raw = [
            (correct, ""),
            (f"{numerator}/{denominator * 2}", "denominator_only"),
            (f"{numerator * 2}/{denominator}", "numerator_only"),
            (f"{numerator}/{denominator + 1}", "unequal_scaling"),
        ]
        values = _rotate(raw, sequence)
        letters = "ABCD"
        choices = {letter: value for letter, (value, _) in zip(letters, values, strict=True)}
        expected = next(letter for letter, (value, _) in zip(letters, values, strict=True) if value == correct)
        misconceptions = {letter: code for letter, (_, code) in zip(letters, values, strict=True) if code}
        if language == "telugu":
            question = f"{numerator}/{denominator} కు సమాన విలువ ఇచ్చే భిన్నం ఏది?"
        elif language == "mixed":
            question = f"{numerator}/{denominator} కి equivalent value ఇచ్చే fraction ఏది?"
        else:
            question = f"Which fraction has the same value as {numerator}/{denominator}?"
        return ObjectiveAssessment(f"fractions-equivalent-{sequence}", question, choices, expected, misconceptions)

    if kind == "dijkstra":
        edges = {
            "A": {"B": 4, "C": 2},
            "B": {"A": 4, "C": 1, "D": 5},
            "C": {"A": 2, "B": 1, "D": 8, "E": 10},
            "D": {"B": 5, "C": 8, "E": 2, "F": 6},
            "E": {"C": 10, "D": 2, "F": 3},
            "F": {"D": 6, "E": 3},
        }
        start = "ABCDEF"[sequence % 6]
        weights = edges[start]
        expected_node = min(weights, key=weights.get)
        distractors = [node for node in "ABCDEF" if node != start and node != expected_node]
        ranked = sorted(weights, key=weights.get, reverse=True)
        wrong_nodes = [ranked[0], next(node for node in distractors if node not in weights)]
        wrong_nodes.append(next(node for node in distractors if node != wrong_nodes[1]))
        raw = [(expected_node, "")]
        raw.extend((node, "larger_edge" if node in weights else "not_connected") for node in wrong_nodes)
        values = _rotate(raw, sequence)
        letters = "ABCD"
        choices = {letter: value for letter, (value, _) in zip(letters, values, strict=True)}
        expected = next(letter for letter, (value, _) in zip(letters, values, strict=True) if value == expected_node)
        misconceptions = {letter: code for letter, (_, code) in zip(letters, values, strict=True) if code}
        if language == "telugu":
            question = f"{start} నోడ్‌కు నేరుగా కలిసిన నోడ్స్‌లో, అతి తక్కువ edge weight ఉన్నది ఏది?"
        elif language == "mixed":
            question = f"Node {start}కి directly connected nodesలో, lowest edge weight ఉన్నది ఏది?"
        else:
            question = f"From node {start}, which adjacent node has the smallest direct edge weight?"
        return ObjectiveAssessment(f"dijkstra-neighbor-{sequence}", question, choices, expected, misconceptions)

    return None
