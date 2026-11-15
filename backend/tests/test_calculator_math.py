from decimal import Decimal

import pytest

from scripts.calculator_math import evaluate_expression


def test_calculator_math_evaluates_bounded_arithmetic():
    assert evaluate_expression("250*18") == Decimal("4500")
    assert evaluate_expression("(20 + 5) * 18") == Decimal("450")


@pytest.mark.parametrize("expression", [
    "__import__('os').system('whoami')", "2 ** 100", "1 / 0", "True + 1", "1; 2", "9" * 100,
])
def test_calculator_math_rejects_code_and_unsafe_expressions(expression):
    with pytest.raises(ValueError):
        evaluate_expression(expression)
