"""Small safe arithmetic evaluator for explicit Calculator requests."""
from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation


def evaluate_expression(expression: str) -> Decimal:
    if not isinstance(expression, str) or not 1 <= len(expression) <= 80:
        raise ValueError("Calculation must contain 1–80 characters.")
    try:
        root = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise ValueError("Use a valid arithmetic expression.") from exc

    def visit(node) -> Decimal:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            try:
                value = Decimal(str(node.value))
            except InvalidOperation as exc:
                raise ValueError("The calculation contains an invalid number.") from exc
            if not value.is_finite() or abs(value) > Decimal("1e100"):
                raise ValueError("The calculation number is out of range.")
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): result = left + right
            elif isinstance(node.op, ast.Sub): result = left - right
            elif isinstance(node.op, ast.Mult): result = left * right
            else:
                if right == 0: raise ValueError("Division by zero is not allowed.")
                result = left / right
            if not result.is_finite() or abs(result) > Decimal("1e100"):
                raise ValueError("The calculation result is out of range.")
            return result
        raise ValueError("Only numbers, parentheses, and +, -, ×, ÷, or * / are allowed.")

    return visit(root)
