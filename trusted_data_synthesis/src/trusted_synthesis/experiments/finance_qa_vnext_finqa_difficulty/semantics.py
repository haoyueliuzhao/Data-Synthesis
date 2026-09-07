"""Finite source-anchored scalar arithmetic; financial target checked only at Final.

Intermediate claims certify numeric derivation and provenance, NOT that a selected
quantity has the right financial role. No reference-node membership is consulted
for action admission. The terminal oracle compares symbolic source expressions;
coincidentally equal numbers from wrong rows are not interchangeable facts.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

import sympy as sp

from trusted_synthesis.domains.finance.qa_vnext.protocol import require

CONSTANTS = ("1", "2", "3", "4", "5", "100", "1000", "1000000")
TOOLS = {
    "read": (
        "One source: numeric_catalog ID; copy its signed numeric value with exact "
        "source identity. No parameters. Reading does not certify relevance or "
        "financial units."
    ),
    "add": "Two accepted scalar claims/constants, first + second.",
    "subtract": "Two accepted scalar claims/constants, first - second.",
    "multiply": (
        "Two accepted scalar claims/constants, first * second. Scale conversions "
        "must be executed, not merely described."
    ),
    "divide": "Two accepted scalar claims/constants, first / second; nonzero denominator.",
    "sum": (
        "Two to eight explicitly selected accepted scalar claims/constants; sum "
        "all selected members, no implicit row or period selection."
    ),
    "average": (
        "Two to eight explicitly selected accepted scalar claims/constants; "
        "arithmetic mean of selected members."
    ),
    "minimum": (
        "Two to eight explicitly selected accepted scalar claims/constants; "
        "minimum of selected members."
    ),
    "maximum": (
        "Two to eight explicitly selected accepted scalar claims/constants; "
        "maximum of selected members."
    ),
    "absolute": (
        "One accepted scalar claim; its absolute value. Never executed implicitly by Final."
    ),
}


def decimal(value):
    value = Fraction(value)
    with localcontext() as ctx:
        ctx.prec = 50
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def calculate(op, values):
    if op == "read":
        return values[0]
    if op == "add":
        return values[0] + values[1]
    if op == "subtract":
        return values[0] - values[1]
    if op == "multiply":
        return values[0] * values[1]
    if op == "divide":
        require(values[1] != 0, "numeric.zero_denominator")
        return values[0] / values[1]
    if op == "sum":
        return sum(values)
    if op == "average":
        return sum(values) / len(values)
    if op == "minimum":
        return min(values)
    if op == "maximum":
        return max(values)
    if op == "absolute":
        return abs(values[0])
    raise ValueError("numeric.unsupported_operation")


def evaluate(tree, facts):
    if isinstance(tree, str):
        if tree.startswith("constant:"):
            require(tree.split(":", 1)[1] in CONSTANTS, "numeric.constant_whitelist")
            return Fraction(tree.split(":", 1)[1])
        return Fraction(facts[tree]["value"])
    return calculate(tree["op"], [evaluate(t, facts) for t in tree["args"]])


def expression(tree, facts=None):
    if isinstance(tree, str):
        if tree.startswith("constant:"):
            require(tree.split(":", 1)[1] in CONSTANTS, "numeric.constant_whitelist")
            return sp.Rational(tree.split(":", 1)[1])
        assumptions = {"real": True}
        if facts is not None:
            value = Fraction(facts[tree]["value"])
            if value > 0:
                assumptions["positive"] = True
            elif value < 0:
                assumptions["negative"] = True
        return sp.Symbol(tree, **assumptions)
    values = [expression(t, facts) for t in tree["args"]]
    if tree["op"] == "minimum":
        return sp.Min(*values)
    if tree["op"] == "maximum":
        return sp.Max(*values)
    if tree["op"] == "absolute":
        return sp.Abs(values[0])
    return calculate(tree["op"], values)


def equivalent(actual, target, facts=None, relations=None):
    # Trees are built exclusively by finite tools; never sympify/eval model strings.
    left, right = expression(actual, facts), expression(target, facts)
    rewrites = {
        expression(key, facts): expression(value, facts) for key, value in (relations or {}).items()
    }
    # Only pre-reviewed acyclic financial table identities, never same-number aliases.
    for _ in range(len(rewrites) + 1):
        next_left, next_right = left.xreplace(rewrites), right.xreplace(rewrites)
        if (next_left, next_right) == (left, right):
            break
        left, right = next_left, next_right
    return sp.simplify(left - right) == 0


def lineage(tree):
    if isinstance(tree, str):
        return {tree} if tree.startswith("source:") else set()
    return set().union(*(lineage(t) for t in tree["args"]))
