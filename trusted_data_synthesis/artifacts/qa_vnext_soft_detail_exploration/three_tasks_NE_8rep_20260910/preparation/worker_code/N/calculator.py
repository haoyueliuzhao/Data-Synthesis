"""Explicit numeric expressions only: no eval, imports, filesystem, source inference or oracle."""

import ast
import re
from decimal import Decimal, localcontext
from fractions import Fraction

try:
    from .common import LIMITS
except ImportError:  # Standalone isolated worker bundle, not the repository package.
    from common import LIMITS


class CalculationError(ValueError):
    pass


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise CalculationError("invalid_numeric_value")
    text = str(value)
    if len(text) > 256 or not re.fullmatch(r"[+\-0-9.eE/]+", text):
        raise CalculationError("invalid_numeric_literal")
    for exponent in re.findall(r"[eE]([+\-]?\d+)", text):
        if len(exponent) > 4 or abs(int(exponent)) > 308:
            raise CalculationError("numeric_literal_exponent_limit")
    try:
        return bounded(Fraction(text))
    except (ValueError, ZeroDivisionError):
        raise CalculationError("invalid_numeric_literal") from None


def bounded(value):
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > LIMITS["integer_bits"]:
        raise CalculationError("numeric_size_limit")
    return value


def display(value):
    with localcontext() as context:
        context.prec = 50
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def calculate(arguments, previous_results):
    expression = arguments.get("expression")
    variables = arguments.get("variables", {})
    if (
        not isinstance(expression, str)
        or not 0 < len(expression) <= LIMITS["expression_characters"]
    ):
        raise CalculationError("invalid_expression_length")
    if not isinstance(variables, dict):
        raise CalculationError("variables_must_be_object")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        raise CalculationError("expression_syntax_error") from None
    if sum(1 for _ in ast.walk(tree)) > LIMITS["ast_nodes"]:
        raise CalculationError("expression_node_limit")
    resolved, consumed, operations, depth_seen = {}, [], 0, 0

    def visit(node, depth=0):
        nonlocal operations, depth_seen
        depth_seen = max(depth_seen, depth)
        if depth > LIMITS["ast_depth"]:
            raise CalculationError("expression_depth_limit")
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return number(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Name):
            name = node.id
            if name not in variables:
                raise CalculationError("undefined_variable:" + name)
            if name not in resolved:
                supplied = variables[name]
                if isinstance(supplied, dict) and set(supplied) == {"result_id"}:
                    ref = supplied["result_id"]
                    prior = previous_results.get(ref)
                    if (
                        not prior
                        or prior.get("status") != "ok"
                        or not isinstance(prior.get("result"), dict)
                        or "exact_value" not in prior["result"]
                    ):
                        raise CalculationError("unknown_numeric_result_reference")
                    value = bounded(Fraction(prior["result"]["exact_value"]))
                    consumed.append(ref)
                    resolved[name] = {"exact_value": str(value), "result_id": ref}
                else:
                    if (
                        isinstance(supplied, dict)
                        and "value" in supplied
                        and "result_id" not in supplied
                    ):
                        supplied = supplied["value"]
                    value = number(supplied)
                    resolved[name] = {"exact_value": str(value), "result_id": None}
            return Fraction(resolved[name]["exact_value"])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operations += 1
            value = visit(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            operations += 1
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise CalculationError("division_by_zero")
                value = left / right
            elif isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right) > LIMITS["power_exponent"]:
                    raise CalculationError("power_exponent_limit")
                if left == 0 and right < 0:
                    raise CalculationError("division_by_zero")
                value = left ** int(right)
            else:
                raise CalculationError("unsupported_binary_operator")
            return bounded(value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name not in {"sum", "avg", "min", "max", "abs"}:
                raise CalculationError("unsupported_function")
            children = node.args
            if len(children) == 1 and isinstance(children[0], (ast.List, ast.Tuple)):
                children = children[0].elts
            if not 1 <= len(children) <= 32 or (name == "abs" and len(children) != 1):
                raise CalculationError("function_arity")
            operations += 1
            values = [visit(child, depth + 1) for child in children]
            if name == "sum":
                value = sum(values, Fraction())
            elif name == "avg":
                value = sum(values, Fraction()) / len(values)
            elif name == "min":
                value = min(values)
            elif name == "max":
                value = max(values)
            else:
                value = abs(values[0])
            return bounded(value)
        raise CalculationError("unsupported_expression_node:" + type(node).__name__)

    value = visit(tree.body)
    return {
        "expression": expression,
        "resolved_variables": resolved,
        "model_supplied_sources": arguments.get("sources"),
        "value": display(value),
        "exact_value": str(value),
        "used_result_ids": sorted(set(consumed)),
        "operation_count": operations,
        "dependency_depth": depth_seen,
        "source_declarations_validated": False,
        "financial_meaning_certified": False,
    }
