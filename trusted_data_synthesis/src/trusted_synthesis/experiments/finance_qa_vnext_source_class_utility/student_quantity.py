"""Task-specific Student units and the shared complete-money-token boundary fix.

The sealed panel supplies the task definition, never a missing published scale
or amount. Shares remain shares; ratio and percent have their physical scales.
Signed decline interpretation and lexical rounding follow the previous Student
review policy, with exact public evidence checked by student_review.
"""

import re
from decimal import InvalidOperation
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    evaluate as reference_value,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.evaluate import displayed_number

from . import quantity
from .plan import record, require

VERSION = quantity.VERSION + ".task_specific_student_adapter"
SHARE_UNIT = re.compile(
    r"(?:(?:in\s+)?(?P<scale>thousand|million|billion)s?\s+(?:of\s+)?)?"
    r"(?:common\s+)?shares?",
    re.IGNORECASE,
)
SHARE_AMOUNT = re.compile(
    rf"(?<![\w.])(?P<value>{quantity.NUMBER})\s+"
    r"(?P<unit>(?:(?:in\s+)?(?:thousand|million|billion)s?\s+(?:of\s+)?)?"
    r"(?:common\s+)?shares?)(?![\w])",
    re.IGNORECASE,
)


def context_from_target(target):
    """Use only the frozen unit/dimension definition, not the reference number."""
    empty = {"public_target_currencies": [], "relevant_source_currencies": []}
    descriptor = unit_descriptor(target, empty)
    require(descriptor["status"] == "MAPPED", "student_quantity.prebound_task_unit")
    currency = descriptor["currency"]
    return {
        "preferred_unit": target,
        "dimension": descriptor["dimension"],
        "target_currency": currency,
        "target_scale": descriptor["scale"],
        "public_target_currencies": [currency] if currency else [],
        "relevant_source_currencies": [currency] if currency else [],
        "currency_context_basis": "inherited sealed source-specific panel unit definition",
        "source_definition_is_not_a_published_unit_or_amount": True,
        "no_reference_number_used_for_interpretation": True,
        "no_cross_task_USD_million_assumption": True,
    }


def unit_descriptor(unit, context):
    if isinstance(unit, str):
        text = " ".join(unit.replace("_", " ").split())
        match = SHARE_UNIT.fullmatch(text)
        if match:
            scale = {"thousand": "1000", "million": "1000000", "billion": "1000000000"}.get(
                (match.group("scale") or "").lower(), "1"
            )
            return {
                "status": "MAPPED",
                "raw_unit": unit,
                "dimension": "shares",
                "currency": None,
                "scale": scale,
                "policy": VERSION,
                "reference_used": False,
                "currency_completion": None,
            }
    return quantity.interpret_unit(unit, context)


def unit_factor(actual, target):
    context = context_from_target(target)
    unit = unit_descriptor(actual, context)
    if (
        unit["status"] != "MAPPED"
        or unit["dimension"] != context["dimension"]
        or unit["currency"] != context["target_currency"]
    ):
        return None
    return Fraction(unit["scale"]) / Fraction(context["target_scale"])


def score_quantity(value, unit, direction, private, *, secondary=False):
    context = context_from_target(private["unit"])
    descriptor = unit_descriptor(unit, context)
    base = {
        "policy": VERSION,
        "published_number": value,
        "published_unit": unit,
        "direction_multiplier": direction,
        "unit_interpretation": descriptor,
    }
    try:
        quantity.number(str(value).strip().rstrip("%"))
        actual, quantum = displayed_number(value)
        if (
            type(direction) is not int
            or direction not in {-1, 1}
            or (direction == -1 and actual < 0)
        ):
            raise ValueError("ambiguous_or_double_direction")
        factor = unit_factor(unit, private["unit"])
        if factor is None:
            definite = descriptor["status"] in {"MAPPED", "FAIL"}
            return {
                **base,
                "numeric_correct": None,
                "unit_correct": False if definite else None,
                "task_answer_status": "FAIL" if definite else "UNDETERMINED",
                "reason": "unresolved_or_incompatible_unit",
            }
        actual, quantum = actual * factor * direction, quantum * factor
        tolerance = Fraction(0) if quantum == 0 else max(quantum / 2, Fraction(1, 10**12))
        if not secondary:
            tolerance = min(Fraction(1, 200), tolerance)
        target = reference_value(private["target"], private["facts"])
        numeric = abs(actual - target) <= tolerance
        return {
            **base,
            "interpreted_reference_unit_value": str(actual),
            "reference_unit": private["unit"],
            "reference_exact_value": str(target),
            "converted_lexical_quantum": str(quantum),
            "rounding_tolerance": str(tolerance),
            "numeric_correct": numeric,
            "unit_correct": True,
            "task_answer_status": "PASS" if numeric else "FAIL",
            "secondary_display_tolerance": secondary,
        }
    except (ValueError, TypeError, ZeroDivisionError, InvalidOperation):
        return {
            **base,
            "numeric_correct": None,
            "unit_correct": None,
            "task_answer_status": "UNDETERMINED",
            "reason": "unsupported_or_unresolved_public_quantity",
        }


def explicit_amounts(text, context):
    """Actual Final-only evidence; do not reinterpret share units as dollars."""
    if not isinstance(text, str):
        return []
    shares = []
    spans = []
    for match in SHARE_AMOUNT.finditer(text):
        spans.append(match.span())
        shares.append(
            {
                "value": match.group("value"),
                "exact_value": str(quantity.number(match.group("value"))),
                "unit": match.group("unit"),
                "quote": match.group(),
                "span": list(match.span()),
                "complete_token_consumed": True,
                "interpretation": unit_descriptor(match.group("unit"), context),
            }
        )
    money = []
    for mention in quantity.amount_mentions(text, context):
        overlaps_share = any(
            left <= mention["span"][0] < right or left <= mention["span"][1] - 1 < right
            for left, right in spans
        )
        explicit_currency = re.match(
            r"\s*(?:US\$|C\$|A\$|\$|€|£|¥|USD\b|EUR\b|GBP\b)", mention["quote"], re.I
        )
        if not overlaps_share or explicit_currency:
            money.append(mention)
    return sorted([*money, *shares], key=lambda mention: mention["span"][0])


def final_amount_check(final, publication, private):
    """Check explicit actual-Final units, retaining the original selection rule."""
    if final is None:
        return {"status": "UNDETERMINED", "reason": "no_actual_Final"}
    context = context_from_target(private["unit"])
    text = final.get("answer") if isinstance(final, dict) else final
    value = publication.get("value")
    descriptor = unit_descriptor(publication.get("unit"), context)
    if value is None or descriptor["status"] != "MAPPED":
        return {"status": "UNDETERMINED", "reason": "publication_quantity_unresolved"}
    try:
        exact = quantity.number(str(value).strip().rstrip("%"))
    except (ValueError, ZeroDivisionError):
        return {"status": "UNDETERMINED", "reason": "publication_value_unresolved"}
    mentions = explicit_amounts(text, context)
    same = [m for m in mentions if quantity.number(m["value"]) == exact]
    expected = (
        descriptor["dimension"],
        descriptor["currency"],
        exact * Fraction(descriptor["scale"]),
    )
    conflicts, unknown = [], []
    for mention in same:
        unit = mention["interpretation"]
        if unit["status"] != "MAPPED":
            unknown.append(mention)
        elif (unit["dimension"], unit["currency"], exact * Fraction(unit["scale"])) != expected:
            conflicts.append(mention)
    claims = [final["currency"]] if isinstance(final, dict) and "currency" in final else []
    if isinstance(text, str):
        pattern = re.compile(
            rf"\b(?:currency\s*(?:is|:)|all\s+amounts\s+(?:are\s+)?in|"
            rf"amounts\s+are\s+in)\s*(?P<currency>{quantity.CURRENCY_WORD})",
            re.I,
        )
        claims.extend(m.group("currency") for m in pattern.finditer(text))
    unresolved_claim = False
    for claim in claims:
        unit = quantity.interpret_unit(claim, context)
        if unit["status"] != "MAPPED":
            unresolved_claim = True
        elif unit["currency"] != descriptor["currency"]:
            conflicts.append({"explicit_currency_claim": claim, "interpretation": unit})
    if conflicts:
        return {
            "status": "FAIL",
            "reason": "conflicting_actual_Final_amount_units",
            "conflicts": conflicts,
        }
    if unknown or unresolved_claim:
        return {
            "status": "UNDETERMINED",
            "reason": "unresolved_complete_Final_amount",
            "unresolved": unknown,
            "unresolved_currency_claim": unresolved_claim,
        }
    # If there is no explicit unit field, the chosen scale must itself appear in
    # an actual complete Final amount, not in a tool response or the gold unit.
    explicit_unit = isinstance(final, dict) and "unit" in final
    if not explicit_unit and not same:
        return {"status": "UNDETERMINED", "reason": "unit_not_in_actual_Final"}
    return {
        "status": "PASS",
        "actual_Final_mentions": mentions,
        "unit_and_value_not_completed_from_tool_or_reference": True,
    }


def policy():
    return record(
        "student_quantity_policy",
        version=VERSION,
        boundary_version=quantity.VERSION,
        actual_Final_value_and_unit_priority_unchanged=True,
        source_of_monetary_currency_context="unchanged sealed per-task source definition",
        public_evidence_required_for_unit_handling=True,
        primary_tolerance=(
            "min(0.005,max(converted lexical half-quantum,1e-12)); exact fractions zero"
        ),
        secondary_tolerance="converted lexical half-quantum floored 1e-12; exact fractions zero",
        share_unit_grammar=SHARE_UNIT.pattern,
        amount_grammar=quantity.AMOUNT.pattern,
        bare_scale_does_not_create_share_dimension=True,
        ratio_scale="1",
        percent_scale="1/100",
        unknown_suffix="UNDETERMINED; never discard a suffix and certify its prefix",
        directions="unchanged +1/-1 public evidence, no target-derived or double negation",
        no_Final_selection_source_period_or_tool_change=True,
    )
