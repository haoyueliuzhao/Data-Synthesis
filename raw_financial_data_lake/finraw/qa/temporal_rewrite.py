"""Finite, fail-closed question semantics for signed changes and growth rates.

This is a parser for an explicitly registered English domain, not a general
natural-language equivalence judge. It consumes the actual question text.
Opaque entity/metric/period/output slots cannot be paraphrased in this domain.
"""

import re
from typing import Any

VERSION = "temporal_quantity_question.v1"


def quantity_contract(
    semantics: dict[str, Any], constraints: list[dict]
) -> dict | None:
    names = [step.get("operator") for step in constraints]
    if names not in (["difference"], ["difference", "ratio_percent"]):
        return None
    errors = []
    difference = constraints[0]
    inputs = difference.get("inputs") or []
    expected_inputs = [{"binding": "previous"}, {"binding": "current"}]
    if inputs != expected_inputs:
        errors.append("unresolved_or_reversed_difference_operand_roles")
    growth = len(names) == 2
    if growth:
        ratio_inputs = constraints[1].get("inputs") or []
        if ratio_inputs != [
            {"step": difference.get("step_id")},
            {"binding": "previous"},
        ]:
            errors.append("unresolved_or_wrong_growth_denominator")
    scope = dict(semantics.get("time_scope") or {})
    return {
        "version": VERSION,
        "quantity": "relative_change" if growth else "difference",
        "direction": "current_minus_previous",
        "denominator": "previous" if growth else None,
        "previous_binding": "previous",
        "current_binding": "current",
        "previous_period": [
            scope.get("previous_period_start"),
            scope.get("previous_period_end"),
        ],
        "current_period": [scope.get("period_start"), scope.get("period_end")],
        "entity_ids": list(semantics.get("entity_ids") or []),
        "metric_ids": list(semantics.get("metric_ids") or []),
        "definition_ids": list(semantics.get("source_definition_ids") or []),
        "contract_errors": errors,
    }


def public_cues(contract: dict | None) -> dict | None:
    if contract is None:
        return None
    return {
        "quantity": contract["quantity"],
        "direction": contract["direction"],
        "denominator": contract["denominator"],
        "language_domain": VERSION,
        "instruction": (
            "Ask for a signed change from the previous period to the current period. "
            "For relative_change, ask for a year-over-year percentage change with the "
            "previous value as base, not a simple ratio. Do not ask for an absolute "
            "magnitude, sum, inverse difference or current-value denominator. Preserve "
            "the company, metric definition, actual periods, output units and precision "
            "through their unchanged placeholders. Use a direct question or request, "
            "without explanation, additional operations, scope qualifiers or aliases."
        ),
    }


def _mask(question: str, slots: dict[str, str]) -> tuple[str, list[str]]:
    errors = []
    result = question.replace("’", "'").strip()
    names = {
        "entity": "entity",
        "metric": "metric",
        "previous_period": "previous",
        "period": "current",
    }
    output = str(slots.get("output_instruction") or "").replace("’", "'")
    if output:
        if result.count(output) != 1 or not result.endswith(output):
            errors.append("output_instruction_changed_or_relocated")
        else:
            result = result[: -len(output)].strip()
    replacements = []
    for key, role in names.items():
        if key not in slots:
            continue
        original = str(slots[key]).replace("’", "'")
        if not original or result.count(original) != 1:
            errors.append("opaque_slot_occurrence_" + key)
        replacements.append((original, "@" + role + "@"))
    for original, token in sorted(replacements, key=lambda pair: -len(pair[0])):
        if original:
            result = result.replace(original, token)
    result = re.sub(r"\s+", " ", result.casefold()).strip()
    result = re.sub(r"[?.]$", "", result).strip()
    return result, errors


_E, _M = "@entity@", "@metric@"
_S = _E + "'s " + _M
_V = r"(?:calculate|compute|determine|find|report|give)"
_Q = r"(?:what (?:is|was)|calculate|compute|determine|find|report|give)"
_CHANGE = r"(?:signed |net )?(?:change|increase or decrease)"
_PLACE = r"(?:the end of |the period ending |the period |the year ending )?"
_A = _PLACE + r"(?P<from>@previous@|@current@)"
_B = _PLACE + r"(?P<to>@previous@|@current@)"
_BASE = (
    r"(?:,? (?:as a percentage of|relative to|using) (?:the )?"
    r"(?P<base>previous|prior|current|later)(?: period(?:'s)?)?"
    r"(?: value| amount)?(?: as (?:the )?(?:base|denominator))?)?"
)

# Every expression is a full match: an added clause cannot hide after a valid
# prefix. The role captures preserve word order instead of sorting dates.
_CHANGE_FORMS = [
    _Q + r" the " + _CHANGE + r" in " + _S + r" from " + _A + r" to " + _B,
    _Q + r" the " + _CHANGE + r" in " + _S + r" between " + _A + r" and " + _B,
    r"by how much did " + _S + r" change from " + _A + r" to " + _B,
    r"how much did " + _S + r" change from " + _A + r" to " + _B,
    r"between the ends of "
    + _A
    + r" and "
    + _B
    + r", by how much did "
    + _S
    + r" change",
    r"for "
    + _E
    + r", "
    + _Q
    + r" the "
    + _CHANGE
    + r" in "
    + _M
    + r" from "
    + _A
    + r" to "
    + _B,
    r"for "
    + _E
    + r", "
    + _Q
    + r" the "
    + _CHANGE
    + r" in "
    + _M
    + r" between "
    + _A
    + r" and "
    + _B,
    r"from " + _A + r" to " + _B + r", " + _Q + r" the " + _CHANGE + r" in " + _S,
    r"what "
    + _CHANGE
    + r" (?:occurred|was recorded) in "
    + _S
    + r" from "
    + _A
    + r" to "
    + _B,
]
_PERCENT_FORMS = [
    pattern.replace(_CHANGE, r"(?:percentage|percent) change")
    for pattern in _CHANGE_FORMS
    if _CHANGE in pattern
]
_YOY_FORMS = [
    _Q + r" the year-over-year (?:growth rate|percentage change|percent change|change) "
    r"(?:of|in) " + _S + r" (?:in|for|as of the end of|at the end of) @current@",
    r"how did " + _S + r" change year over year (?:in|for) @current@",
    r"at the end of @current@, how much had "
    + _S
    + r" changed from the prior fiscal-year end, in percentage terms",
    r"for "
    + _E
    + r", "
    + _Q
    + r" the year-over-year (?:growth rate|percentage change|percent change) "
    r"(?:of|in) " + _M + r" (?:in|for|at the end of) @current@",
    r"(?:in|for) @current@, "
    + _Q
    + r" the year-over-year (?:growth rate|percentage change) "
    r"(?:of|in) " + _S,
    r"what (?:is|was) the (?:percentage|percent) change in "
    + _S
    + r" (?:in|for|at the end of) @current@ (?:compared with|compared to|relative to) "
    r"the (?:previous|prior) fiscal year(?:-end)?",
]


def parse_expression(masked: str) -> dict | None:
    for quantity, forms in (
        ("difference", _CHANGE_FORMS),
        ("relative_change", _PERCENT_FORMS),
    ):
        for pattern in forms:
            match = re.fullmatch(pattern + _BASE, masked)
            if match:
                parts = match.groupdict()
                before, after = parts["from"].strip("@"), parts["to"].strip("@")
                explicit_base = parts.get("base")
                observed_quantity = "relative_change" if explicit_base else quantity
                base = {"prior": "previous", "later": "current"}.get(
                    explicit_base, explicit_base
                )
                return {
                    "quantity": observed_quantity,
                    "direction": after + "_minus_" + before,
                    "denominator": (base or before)
                    if observed_quantity == "relative_change"
                    else None,
                }
    for pattern in _YOY_FORMS:
        match = re.fullmatch(pattern + _BASE, masked)
        if match:
            base = match.groupdict().get("base")
            return {
                "quantity": "relative_change",
                "direction": "current_minus_previous",
                "denominator": {"prior": "previous", "later": "current"}.get(base, base)
                or "previous",
            }
    # Explicit subtraction has its own direction, rather than a date-order guess.
    explicit = [
        r"for "
        + _E
        + r", "
        + _V
        + " "
        + _M
        + r" at "
        + _B
        + r" minus its value at "
        + _A,
        _V + r" the difference in " + _S + r" as " + _B + r" minus " + _A,
        r"for " + _E + r", subtract " + _M + r" at " + _A + r" from its value at " + _B,
        r"subtract the "
        + _A
        + r" value of "
        + _M
        + r" from the "
        + _B
        + r" value for "
        + _E,
    ]
    for pattern in explicit:
        match = re.fullmatch(pattern + _BASE, masked)
        if match:
            parts = match.groupdict()
            base = parts.get("base")
            return {
                "quantity": "relative_change" if base else "difference",
                "direction": parts["to"].strip("@")
                + "_minus_"
                + parts["from"].strip("@"),
                "denominator": {"prior": "previous", "later": "current"}.get(
                    base, base
                ),
            }
    return None


def validate_temporal_question(question: str, contract: dict) -> dict:
    expected = contract.get("temporal_quantity")
    if expected is None:
        return {"applicable": False, "passed": True, "errors": [], "observed": None}
    masked, errors = _mask(question, contract.get("slot_map") or {})
    errors.extend(expected.get("contract_errors") or [])
    observed = parse_expression(masked)
    if observed is None:
        errors.append("outside_registered_temporal_expression_domain")
    else:
        for key in ("quantity", "direction", "denominator"):
            if observed[key] != expected[key]:
                errors.append("temporal_" + key + "_mismatch")
    return {
        "applicable": True,
        "passed": not errors,
        "errors": errors,
        "version": VERSION,
        "observed": observed,
        "masked_question": masked,
    }
