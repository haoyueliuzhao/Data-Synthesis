"""Finite source-symbolic arithmetic, independent of task answers and financial identities.

Only explicitly evidenced AST occurrences become source symbols.  Numeric equality
never supplies a missing source binding.  The raw execution DAG belongs to the
caller; this module projects its answer-connected arithmetic after real result
references have been expanded.
"""

from __future__ import annotations

import ast
import re
from fractions import Fraction

import sympy as sp

SCHEMA = "source_rational_polynomial.v1"
MAX_CHARACTERS = 8192
MAX_NODES = 1024
MAX_TERMS = 1024
MAX_POWER = 64
MAX_INTEGER_BITS = 4096


class Unsupported(ValueError):
    """Outside the frozen finite normalization domain, not a new behavior class."""


def _exact(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise Unsupported("invalid_exact_number")
    text = str(value)
    if len(text) > 4096:
        raise Unsupported("exact_number_limit")
    for exponent in re.findall(r"[eE]([+\-]?\d+)", text):
        if len(exponent) > 4 or abs(int(exponent)) > 308:
            raise Unsupported("exact_number_limit")
    try:
        result = Fraction(text)
    except (ValueError, ZeroDivisionError, OverflowError):
        raise Unsupported("invalid_exact_number") from None
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > MAX_INTEGER_BITS:
        raise Unsupported("exact_number_limit")
    return result


def _rational(value):
    value = _exact(value)
    return sp.Rational(value.numerator, value.denominator)


def _symbols(expression):
    return sorted(expression.free_symbols, key=lambda item: item.name)


def _expanded(expression):
    result = sp.expand(expression)
    symbols = _symbols(result)
    if symbols:
        terms = sp.Poly(result, *symbols, domain=sp.QQ).terms()
        if len(terms) > MAX_TERMS or any(sum(powers) > MAX_POWER for powers, _ in terms):
            raise Unsupported("polynomial_size_limit")
        coefficients = [coefficient for _, coefficient in terms]
    else:
        coefficients = [result]
    for coefficient in coefficients:
        _exact(str(coefficient))
    return result


def _monic(expression):
    expression = _expanded(expression)
    if expression == 0:
        raise Unsupported("symbolically_zero_denominator")
    symbols = _symbols(expression)
    leading = sp.Poly(expression, *symbols, domain=sp.QQ).LC() if symbols else expression
    return _expanded(expression / leading), leading


def _terms(expression):
    expression = _expanded(expression)
    if expression == 0:
        return []
    symbols = _symbols(expression)
    if not symbols:
        return [{"coefficient": str(expression), "powers": []}]
    result = []
    for powers, coefficient in sp.Poly(expression, *symbols, domain=sp.QQ).terms():
        result.append(
            {
                "coefficient": str(coefficient),
                "powers": [
                    [symbol.name, int(power)]
                    for symbol, power in zip(symbols, powers, strict=True)
                    if power
                ],
            }
        )
    return result


def _factor_keys(expression):
    """Canonical nonconstant zero-set factors; rational scale is immaterial."""
    expression = _expanded(expression)
    if expression == 0:
        raise Unsupported("symbolically_zero_denominator")
    if not expression.free_symbols:
        return set()
    _, factors = sp.factor_list(expression)
    return {repr(_terms(_monic(factor)[0])) for factor, _ in factors}


def _pair(numerator, denominator):
    numerator, denominator = _expanded(numerator), _expanded(denominator)
    denominator, scale = _monic(denominator)
    return _expanded(numerator / scale), denominator


def _add(left, right, subtract=False):
    # A common denominator avoids introducing artificial cancellable factors in
    # x/y + z/y.  Genuine source-factor cancellation is checked at the boundary.
    denominator = _expanded(sp.lcm(left[1], right[1]))

    def exact_quotient(divisor):
        if not divisor.free_symbols:
            return _expanded(denominator / divisor)
        symbols = sorted(
            denominator.free_symbols | divisor.free_symbols, key=lambda item: item.name
        )
        quotient, remainder = sp.div(denominator, divisor, *symbols, domain=sp.QQ)
        if remainder != 0:
            raise Unsupported("unsupported_common_denominator")
        return _expanded(quotient)

    l_factor = exact_quotient(left[1])
    r_factor = exact_quotient(right[1])
    sign = -1 if subtract else 1
    return _pair(left[0] * l_factor + sign * right[0] * r_factor, denominator)


def _decode_terms(terms):
    if not isinstance(terms, list) or len(terms) > MAX_TERMS:
        raise Unsupported("invalid_previous_normal_form")
    expression = sp.Integer(0)
    for term in terms:
        if not isinstance(term, dict) or set(term) != {"coefficient", "powers"}:
            raise Unsupported("invalid_previous_normal_form")
        coefficient = _rational(term["coefficient"])
        powers = term["powers"]
        if not isinstance(powers, list):
            raise Unsupported("invalid_previous_normal_form")
        seen, total = set(), 0
        for item in powers:
            if (
                not isinstance(item, list)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0]
                or item[0] in seen
                or type(item[1]) is not int
                or not 0 < item[1] <= MAX_POWER
            ):
                raise Unsupported("invalid_previous_normal_form")
            source_id, power = item
            seen.add(source_id)
            total += power
            coefficient *= sp.Symbol(source_id) ** power
        if total > MAX_POWER:
            raise Unsupported("polynomial_size_limit")
        expression += coefficient
    return _expanded(expression)


def _decode_previous(record):
    if not isinstance(record, dict) or record.get("status") != "MAPPED":
        raise Unsupported("unmapped_result_reference")
    normal = record.get("normal_form")
    if not isinstance(normal, dict) or set(normal) != {"schema", "numerator", "denominator"}:
        raise Unsupported("invalid_previous_normal_form")
    if normal["schema"] != SCHEMA:
        raise Unsupported("unsupported_previous_normal_form_schema")
    numerator, denominator = _pair(
        _decode_terms(normal["numerator"]), _decode_terms(normal["denominator"])
    )
    if normal != {
        "schema": SCHEMA,
        "numerator": _terms(numerator),
        "denominator": _terms(denominator),
    }:
        raise Unsupported("noncanonical_previous_normal_form")
    active = sorted(symbol.name for symbol in numerator.free_symbols | denominator.free_symbols)
    all_sources = record.get("all_source_ids")
    if (
        record.get("active_source_ids") != active
        or not isinstance(all_sources, list)
        or any(not isinstance(item, str) or not item for item in all_sources)
        or not set(active).issubset(all_sources)
    ):
        raise Unsupported("invalid_previous_source_support")
    return (numerator, denominator), all_sources


def normalize_expression(expression, bindings, previous=None):
    """Return a finite symbolic projection or UNDETERMINED, never infer a source.

    Addresses start at ``body`` and append ``.left``, ``.right``, ``.operand``,
    ``.args.N`` or ``.elts.N``.  Every numeric Constant and every variable Name
    needs its own evidenced source/constant/result binding.  A UnaryOp whose
    operand is one numeric Constant may instead be bound as one signed literal
    at the UnaryOp address; its child must then have no additional binding.
    This exception is scalar syntax only, not permission to replace arbitrary
    equal-valued arithmetic subexpressions with sources.  Function names are
    syntax, not variable leaves.  Extra binding metadata never enters the key.

    ``previous[result_id]`` must be a MAPPED result of this function.  Its exact
    symbolic normal form is expanded; numerical result equality is insufficient.
    """
    all_sources, guards, consumed_bindings = set(), set(), set()
    source_values = {}

    def output(status, normal=None, reason=None):
        active = []
        if normal is not None:
            active = sorted(
                {
                    source_id
                    for part in ("numerator", "denominator")
                    for term in normal[part]
                    for source_id, _ in term["powers"]
                }
            )
        return {
            "status": status,
            "normal_form": normal,
            "active_source_ids": active,
            "all_source_ids": sorted(all_sources),
            "reason": reason,
        }

    def leaf(node, address):
        binding = bindings.get(address)
        if not isinstance(binding, dict):
            raise Unsupported("missing_occurrence_binding:" + address)
        if binding.get("evidence_verified") is not True:
            raise Unsupported("unverified_occurrence_binding:" + address)
        consumed_bindings.add(address)
        kind = binding.get("kind")
        if kind == "source":
            source_id = binding.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise Unsupported("invalid_source_id:" + address)
            all_sources.add(source_id)
            if not isinstance(binding.get("attribution"), str) or not binding["attribution"]:
                raise Unsupported("missing_source_attribution:" + address)
            expected = _exact(binding.get("executed_exact"))
            if _exact(binding.get("source_exact")) != expected:
                raise Unsupported("source_execution_value_mismatch:" + address)
            if source_id in source_values and source_values[source_id] != expected:
                raise Unsupported("inconsistent_source_values:" + source_id)
            source_values[source_id] = expected
            value = (sp.Symbol(source_id), sp.Integer(1))
        elif kind == "constant":
            if not isinstance(binding.get("reason"), str) or not binding["reason"]:
                raise Unsupported("unexplained_constant:" + address)
            expected = _exact(binding.get("value"))
            value = (_rational(str(expected)), sp.Integer(1))
        elif kind == "result":
            result_id = binding.get("result_id")
            if not isinstance(result_id, str) or not result_id:
                raise Unsupported("invalid_result_id:" + address)
            expected = _exact(binding.get("executed_exact"))
            if result_id not in previous:
                raise Unsupported("unknown_result_reference:" + result_id)
            value, inherited_sources = _decode_previous(previous[result_id])
            all_sources.update(inherited_sources)
            guards.update(_factor_keys(value[1]))
        else:
            raise Unsupported("unsupported_binding_kind:" + address)
        if isinstance(node, (ast.Constant, ast.UnaryOp)):
            numeric_node = node.operand if isinstance(node, ast.UnaryOp) else node
            actual = _exact(ast.get_source_segment(expression, numeric_node))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                actual = -actual
            if actual != expected:
                raise Unsupported("literal_execution_value_mismatch:" + address)
        return value

    def visit(node, address, depth=0):
        if depth > 64:
            raise Unsupported("expression_depth_limit")
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return leaf(node, address)
        if isinstance(node, ast.Name):
            return leaf(node, address)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            if (
                address in bindings
                and isinstance(node.operand, ast.Constant)
                and type(node.operand.value) in {int, float}
            ):
                return leaf(node, address)
            value = visit(node.operand, address + ".operand", depth + 1)
            return _pair(value[0] if isinstance(node.op, ast.UAdd) else -value[0], value[1])
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise Unsupported("unsupported_binary_operator")
            left = visit(node.left, address + ".left", depth + 1)
            right = visit(node.right, address + ".right", depth + 1)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                return _add(left, right, isinstance(node.op, ast.Sub))
            if isinstance(node.op, ast.Mult):
                return _pair(left[0] * right[0], left[1] * right[1])
            guards.update(_factor_keys(right[0]))
            return _pair(left[0] * right[1], left[1] * right[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name not in {"sum", "avg"}:
                raise Unsupported("unsupported_function")
            children = [
                (child, address + f".args.{index}") for index, child in enumerate(node.args)
            ]
            if len(children) == 1 and isinstance(children[0][0], (ast.List, ast.Tuple)):
                container, base = children[0]
                children = [
                    (child, base + f".elts.{index}") for index, child in enumerate(container.elts)
                ]
            if not 1 <= len(children) <= 32:
                raise Unsupported("unsupported_function_arity")
            value = (sp.Integer(0), sp.Integer(1))
            for child, child_address in children:
                value = _add(value, visit(child, child_address, depth + 1))
            if name == "avg":
                value = _pair(value[0], value[1] * len(children))
            return value
        raise Unsupported("unsupported_expression_node:" + type(node).__name__)

    try:
        if not isinstance(expression, str) or not 0 < len(expression) <= MAX_CHARACTERS:
            raise Unsupported("invalid_expression_length")
        if not isinstance(bindings, dict) or any(not isinstance(key, str) for key in bindings):
            raise Unsupported("invalid_bindings")
        previous = {} if previous is None else previous
        if not isinstance(previous, dict):
            raise Unsupported("invalid_previous_results")
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError, RecursionError):
            raise Unsupported("expression_syntax_error") from None
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            raise Unsupported("expression_node_limit")
        numerator, denominator = visit(tree.body, "body")
        if set(bindings) != consumed_bindings:
            raise Unsupported("unused_occurrence_binding")
        common_factor = _expanded(sp.gcd(numerator, denominator))
        if common_factor.free_symbols:
            raise Unsupported("source_dependent_cancellation")
        denominator_factors = _factor_keys(denominator)
        if not guards.issubset(denominator_factors):
            raise Unsupported("source_domain_elimination")
        normal = {
            "schema": SCHEMA,
            "numerator": _terms(numerator),
            "denominator": _terms(denominator),
        }
        return output("MAPPED", normal)
    except Unsupported as error:
        return output("UNDETERMINED", reason=str(error))
    except (ArithmeticError, TypeError, KeyError, ValueError, RecursionError) as error:
        # Malformed annotations are missing measurement support, not new classes.
        return output("UNDETERMINED", reason="normalization_error:" + type(error).__name__)
