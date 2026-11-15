from decimal import Decimal

import pytest

from scripts.calculator_math import evaluate_expression, normalize_spoken_expression


def test_calculator_math_evaluates_bounded_arithmetic():
    assert evaluate_expression("250*18") == Decimal("4500")
    assert evaluate_expression("(20 + 5) * 18") == Decimal("450")


@pytest.mark.parametrize(("spoken", "expected"), [
    ("250 times 18", "250*18"),
    ("250 multiplied by 18", "250*18"),
    ("250 divided by 10", "250/10"),
    ("250 plus 18", "250+18"),
    ("250 minus 18", "250-18"),
])
def test_spoken_arithmetic_operators_normalize_to_safe_math(spoken, expected):
    assert normalize_spoken_expression(spoken) == expected


def test_spoken_arithmetic_rejects_unrecognized_words():
    with pytest.raises(ValueError, match="Only numbers"):
        normalize_spoken_expression("250 times 18 and open Calculator")


@pytest.mark.parametrize("expression", [
    "__import__('os').system('whoami')", "2 ** 100", "1 / 0", "True + 1", "1; 2", "9" * 100,
])
def test_calculator_math_rejects_code_and_unsafe_expressions(expression):
    with pytest.raises(ValueError):
        evaluate_expression(expression)
