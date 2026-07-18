from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

ANALYSIS_TEXT_PARSER_VERSION = "1.0.0"
_POSITIVE = re.compile(
    r"\b(?:positive|improv(?:e|ed|ement|ing)|increase(?:d|s)?|growth|strong|strength|expand(?:ed|s|ing)?|supports?|conservative|above|leader)\b",
    re.I,
)
_NEGATIVE = re.compile(
    r"\b(?:negative|declin(?:e|ed|ing)|decreas(?:e|ed|ing)|weak|weaken(?:ed|ing)?|deteriorat(?:e|ed|ing)|risk|caution|caveat|constraint|diverg(?:e|ed|ence)|elevated|below|laggard|trails?|does not|without)\b",
    re.I,
)
_MIXED = re.compile(
    r"\b(?:mixed|stable|middle|balanced|coexist|not uniformly|uncertain|inconclusive|tempered|limits?)\b",
    re.I,
)
_NUMERIC = re.compile(
    r"(?<![A-Za-z])([-+]?\d+(?:\.\d+)?)\s*(%|percent(?:age)?(?:\s+points?)?|pp)?", re.I
)


def parse_stance(text: str) -> dict[str, Any]:
    return {
        "positive": bool(_POSITIVE.search(text)),
        "negative_or_risk": bool(_NEGATIVE.search(text)),
        "mixed_or_neutral": bool(_MIXED.search(text)),
    }


def validate_stance(text: str, expected: str) -> dict[str, Any]:
    observed = parse_stance(text)
    if expected == "positive":
        passed = observed["positive"] and not observed["negative_or_risk"]
    elif expected in {"negative", "risk"}:
        passed = observed["negative_or_risk"]
    elif expected in {"neutral", "mixed"}:
        passed = observed["mixed_or_neutral"] or (
            observed["positive"] and observed["negative_or_risk"]
        )
    else:
        passed = False
    return {
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "parser_version": ANALYSIS_TEXT_PARSER_VERSION,
    }


def validate_numeric_grounding(
    text: str,
    numeric_slots: list[dict[str, Any]],
    allowed_years: list[int],
) -> dict[str, Any]:
    mentions = []
    unsupported = []
    unit_mismatches = []
    slots = list(numeric_slots)
    for match in _NUMERIC.finditer(text):
        raw_value = match.group(1)
        suffix = str(match.group(2) or "").lower()
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            unsupported.append(match.group(0))
            continue
        if (
            not suffix
            and value == value.to_integral()
            and int(value) in set(allowed_years)
        ):
            mentions.append({"text": match.group(0), "kind": "period", "matched": True})
            continue
        mention_unit = _mention_unit(suffix)
        matches = []
        wrong_unit = []
        for slot in slots:
            try:
                target = Decimal(str(slot.get("value")))
                tolerance = Decimal(str(slot.get("tolerance") or "0.01"))
            except InvalidOperation:
                continue
            if abs(value - target) <= tolerance:
                if _unit_compatible(
                    mention_unit,
                    str(slot.get("unit") or "number"),
                    text,
                    match.start(),
                    match.end(),
                ):
                    matches.append(str(slot.get("slot_id")))
                else:
                    wrong_unit.append(str(slot.get("slot_id")))
        item = {
            "text": match.group(0),
            "value": str(value),
            "unit": mention_unit,
            "matched_slot_ids": matches,
        }
        mentions.append(item)
        if not matches:
            if wrong_unit:
                unit_mismatches.append({**item, "candidate_slot_ids": wrong_unit})
            else:
                unsupported.append(item)
    return {
        "passed": not unsupported and not unit_mismatches,
        "mentions": mentions,
        "unsupported": unsupported,
        "unit_mismatches": unit_mismatches,
    }


def _mention_unit(suffix: str) -> str:
    if suffix in {"%", "percent", "percentage"}:
        return "percent"
    if suffix == "pp" or "point" in suffix:
        return "percentage_point"
    return "number"


def _unit_compatible(
    mention: str, expected: str, text: str, start: int, end: int
) -> bool:
    if expected in {"percent", "percentage_point"}:
        return mention == expected
    if expected in {"year", "count", "number"}:
        return mention == "number"
    context = text[max(0, start - 10) : min(len(text), end + 30)].lower()
    return mention == "number" and all(
        token.lower() in context
        for token in expected.split()
        if token.upper() not in {"USD", "CNY"}
    )
