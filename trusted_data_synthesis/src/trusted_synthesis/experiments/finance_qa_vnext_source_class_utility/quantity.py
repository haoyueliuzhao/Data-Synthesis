"""Finite public quantity interpretation, independent of canonical formatting.

Version 1.1 fixes complete amount-token boundaries and adds currency-qualified M.
Only the actual Final can supply a value or scale. Currency completion requires
agreement of the public target and relevant-source contexts; no reference number
is inspected during interpretation. No old experiment imports this new policy.
"""

import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction

VERSION = "public_quantity_interpretation.v1.1"
NUMBER = (
    r"[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)"
    r"(?:[eE][+-]?\d+)?(?:\s*/\s*[+-]?\d+(?:\.\d+)?)?"
)
SCALE_WORD = r"(?:thousand|million|billion)s?"
CURRENCY_WORD = (
    r"(?:U\.?S\.?\s*dollars?|United\s+States\s+dollars?|Canadian\s+dollars?|"
    r"Australian\s+dollars?|dollars?|euros?|pounds?|yen|yuan|"
    r"USD|EUR|GBP|JPY|CNY|RMB|CAD|AUD|CHF|HKD|SGD)"
)
UNIT_PHRASE = (
    rf"(?:(?:in\s+)?{SCALE_WORD}(?:\s+(?:of\s+)?{CURRENCY_WORD})?|"
    rf"{CURRENCY_WORD}(?:\s+(?:in\s+)?{SCALE_WORD})?|percent|percentage|%|ratio|fraction)"
)
AMOUNT = re.compile(
    rf"(?<![\w.])(?P<prefix>US\$|C\$|A\$|\$|€|£|¥|USD\s+|EUR\s+|GBP\s+)?"
    rf"\s*(?P<value>{NUMBER})(?:(?P<compact_m>M)(?!\w)|"
    rf"(?:\s*(?P<unit>{UNIT_PHRASE})))?",
    re.IGNORECASE,
)
CURRENCIES = {
    "USD": r"\b(?:usd|us\s+dollars?|united\s+states\s+dollars?)\b",
    "EUR": r"\b(?:eur|euros?)\b|€",
    "GBP": r"\b(?:gbp|pounds?)\b|£",
    "JPY": r"\b(?:jpy|yen)\b",
    "CNY": r"\b(?:cny|rmb|yuan)\b",
    "CAD": r"\b(?:cad|canadian\s+dollars?)\b",
    "AUD": r"\b(?:aud|australian\s+dollars?)\b",
    "CHF": r"\bchf\b",
    "HKD": r"\bhkd\b",
    "SGD": r"\bsgd\b",
}
DOLLAR_CURRENCIES = {"USD", "CAD", "AUD", "HKD", "SGD"}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("quantity.non_numeric_Final_value")
    text = str(value).strip()
    if len(text) > 256 or re.fullmatch(NUMBER, text) is None:
        raise ValueError("quantity.outside_finite_number_grammar")
    if any(abs(int(exponent)) > 18 for exponent in re.findall(r"[eE]([+-]?\d+)", text)):
        raise ValueError("quantity.exponent_outside_finite_domain")
    return Fraction(text.replace(",", "").replace(" ", ""))


def unique_public_currency(context):
    target = set(context.get("public_target_currencies", []))
    source = set(context.get("relevant_source_currencies", []))
    if len(target) == len(source) == 1 and target == source:
        return next(iter(target))
    return None


def interpret_unit(unit, context):
    base = {"raw_unit": unit, "policy": VERSION, "reference_used": False}
    if not isinstance(unit, str) or not unit.strip():
        return {**base, "status": "UNDETERMINED", "reason": "no_unit_in_actual_Final"}
    text = unit.casefold().strip().replace("_", " ")
    text = re.sub(r"u\.\s*s\.?", "us", text)
    for prefix, code in (("us$", "usd"), ("c$", "cad"), ("a$", "aud")):
        text = text.replace(prefix, code + " ")
    text = re.sub(r"[(),]", " ", text)
    currencies = set()
    for currency, pattern in CURRENCIES.items():
        if re.search(pattern, text):
            currencies.add(currency)
            text = re.sub(pattern, " ", text)
    ambiguous_dollar = "$" in text or bool(re.search(r"\bdollars?\b", text))
    ambiguous_yen = "¥" in text
    text = re.sub(r"\bdollars?\b", " ", text).replace("$", " ").replace("¥", " ")
    ratios = re.findall(r"\b(?:percent|percentage|per\s+cent|ratio|fraction)\b|%", text)
    if ratios:
        if currencies or ambiguous_dollar or ambiguous_yen:
            return {**base, "status": "FAIL", "reason": "conflicting_money_and_ratio_units"}
        scales = {"1/100" if word not in {"ratio", "fraction"} else "1" for word in ratios}
        if len(scales) != 1:
            return {**base, "status": "FAIL", "reason": "conflicting_ratio_scales"}
        rest = re.sub(r"\b(?:percent|percentage|per\s+cent|ratio|fraction)\b|%", " ", text)
        if rest.strip():
            return {**base, "status": "UNDETERMINED", "reason": "unparsed_ratio_unit_text"}
        return {
            **base,
            "status": "MAPPED",
            "dimension": "ratio",
            "currency": None,
            "scale": next(iter(scales)),
            "currency_completion": None,
        }
    scale_words = re.findall(r"\b(thousand|million|billion)s?\b", text)
    text = re.sub(r"\b(?:thousand|million|billion)s?\b", " ", text)
    if len(scale_words) > 1:
        return {**base, "status": "UNDETERMINED", "reason": "multiple_scale_markers"}
    text = re.sub(r"\b(?:in|of)\b", " ", text)
    if text.strip():
        return {**base, "status": "UNDETERMINED", "reason": "unparsed_unit_text"}
    if len(currencies) > 1:
        return {**base, "status": "FAIL", "reason": "conflicting_explicit_currencies"}
    currency = next(iter(currencies), None)
    if ambiguous_dollar and currency and currency not in DOLLAR_CURRENCIES:
        return {**base, "status": "FAIL", "reason": "dollar_symbol_currency_conflict"}
    if ambiguous_yen and currency and currency not in {"JPY", "CNY"}:
        return {**base, "status": "FAIL", "reason": "yen_symbol_currency_conflict"}
    inferred = False
    if currency is None:
        currency = unique_public_currency(context)
        inferred = currency is not None
        if ambiguous_dollar and currency not in DOLLAR_CURRENCIES:
            currency = None
        if ambiguous_yen and currency not in {"JPY", "CNY"}:
            currency = None
    if currency is None:
        return {**base, "status": "UNDETERMINED", "reason": "currency_not_uniquely_public"}
    if not (scale_words or currencies or ambiguous_dollar or ambiguous_yen):
        return {**base, "status": "UNDETERMINED", "reason": "no_explicit_scale_or_base_currency"}
    scale = {"thousand": "1000", "million": "1000000", "billion": "1000000000"}.get(
        scale_words[0] if scale_words else "", "1"
    )
    return {
        **base,
        "status": "MAPPED",
        "dimension": "money",
        "currency": currency,
        "scale": scale,
        "currency_completion": "unique_public_target_and_source" if inferred else None,
    }


def amount_mentions(text, context):
    if not isinstance(text, str):
        return []
    result = []
    for match in AMOUNT.finditer(text):
        prefix, unit, compact_m = (
            match.group("prefix"),
            match.group("unit"),
            match.group("compact_m"),
        )
        # Retain unparsed attached suffixes; never certify a recognizable
        # prefix of "$46.4Mystery" as 46.4 base dollars.
        tail = re.match(r"[\w%$€£¥]+", text[match.end() :])
        end = match.end() + (len(tail.group()) if tail else 0)
        if not prefix and not unit and not compact_m:
            continue
        combined = " ".join(
            part.strip() for part in (prefix, "million" if compact_m else unit) if part
        )
        try:
            exact = number(match.group("value"))
        except (ValueError, ZeroDivisionError):
            continue
        interpreted = interpret_unit(combined, context)
        incomplete = bool(tail) or bool(compact_m and not prefix)
        if incomplete:
            interpreted = {
                "raw_unit": text[match.end("value") : end],
                "policy": VERSION,
                "reference_used": False,
                "status": "UNDETERMINED",
                "reason": "outside_complete_amount_token_grammar",
            }
        result.append(
            {
                "value": match.group("value"),
                "exact_value": str(exact),
                "unit": combined,
                "interpretation": interpreted,
                "quote": text[match.start() : end].strip(),
                "span": [match.start(), end],
                "complete_token_consumed": not incomplete,
                "unparsed_attached_suffix": tail.group() if tail else None,
                "currency_qualified_compact_M": bool(compact_m and prefix),
            }
        )
    return result


def _physical_key(value, unit):
    return (
        unit["dimension"],
        unit["currency"],
        number(value) * Fraction(unit["scale"]),
    )


def interpret_final(final, context):
    text = final.get("answer") if isinstance(final, dict) else final
    mentions = amount_mentions(text, context)
    explicit_value = isinstance(final, dict) and "value" in final
    raw_value = final.get("value") if isinstance(final, dict) else None
    raw_unit = final.get("unit") if isinstance(final, dict) else None
    currency_claims = []
    if isinstance(final, dict) and "currency" in final:
        currency_claims.append(final["currency"])
    if isinstance(text, str):
        scoped_currency = re.compile(
            rf"\b(?:currency\s*(?:is|:)|all\s+amounts\s+(?:are\s+)?in|"
            rf"amounts\s+are\s+in)\s*(?P<currency>{CURRENCY_WORD})",
            re.IGNORECASE,
        )
        currency_claims.extend(m.group("currency") for m in scoped_currency.finditer(text))
    base = {
        "policy": VERSION,
        "raw_Final": final,
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "value_and_scale_from_actual_Final_only": True,
        "reference_tool_or_sibling_message_used_to_complete_Final": False,
        "actual_Final_amount_mentions": mentions,
        "actual_Final_explicit_currency_claims": currency_claims,
    }
    preferred_format = (
        explicit_value
        and raw_unit == context.get("preferred_unit")
        and isinstance(final, dict)
        and isinstance(raw_unit, str)
    )
    try:
        if explicit_value:
            value = number(raw_value)
            value_text = str(raw_value)
            extraction = "Final.value"
            if isinstance(raw_unit, str) and raw_unit.strip():
                if any(not isinstance(c, str) or not c.strip() for c in currency_claims):
                    raise ValueError("quantity.uninterpretable_actual_Final_currency_claim")
                unit = interpret_unit(" ".join([raw_unit, *currency_claims]), context)
                unit_text = raw_unit
            else:
                same = [m for m in mentions if number(m["value"]) == value]
                mapped = [m for m in same if m["interpretation"]["status"] == "MAPPED"]
                keys = {_physical_key(m["value"], m["interpretation"]) for m in mapped}
                if len(keys) != 1 or len(mapped) != len(same) or not mapped:
                    raise ValueError("quantity.missing_unit_not_unambiguous_in_actual_Final")
                chosen = mapped[0]
                unit, unit_text = chosen["interpretation"], chosen["unit"]
                extraction += "+Final.answer.unit"
        else:
            preferred_format = False
            mapped = [m for m in mentions if m["interpretation"]["status"] == "MAPPED"]
            keys = {_physical_key(m["value"], m["interpretation"]) for m in mapped}
            if len(keys) != 1 or len(mapped) != len(mentions) or not mapped:
                raise ValueError("quantity.no_unique_explicit_amount_in_actual_Final")
            chosen = mapped[0]
            value_text, value = chosen["value"], number(chosen["value"])
            unit, unit_text = chosen["interpretation"], chosen["unit"]
            extraction = "Final.answer" if isinstance(final, dict) else "Final.text"
        if unit["status"] != "MAPPED":
            return {
                **base,
                "status": unit["status"],
                "reason": unit["reason"],
                "V_format": "PASS" if preferred_format else "FAIL",
                "published_value": value_text,
                "published_unit": unit_text,
                "unit_interpretation": unit,
                "extraction": extraction,
            }
        for claim in currency_claims:
            claim_unit = interpret_unit(claim, context)
            if claim_unit["status"] != "MAPPED":
                raise ValueError("quantity.uninterpretable_actual_Final_currency_claim")
            if claim_unit["currency"] != unit["currency"]:
                return {
                    **base,
                    "status": "FAIL",
                    "reason": "conflicting_actual_Final_currency_claim",
                    "V_format": "PASS" if preferred_format else "FAIL",
                    "published_value": value_text,
                    "published_unit": unit_text,
                    "unit_interpretation": unit,
                    "extraction": extraction,
                }
        if explicit_value:
            key = _physical_key(value_text, unit)
            conflicts = [
                m
                for m in mentions
                if number(m["value"]) == value
                and m["interpretation"]["status"] == "MAPPED"
                and _physical_key(m["value"], m["interpretation"]) != key
            ]
            if conflicts:
                return {
                    **base,
                    "status": "FAIL",
                    "reason": "conflicting_explicit_Final_amount_units",
                    "V_format": "PASS" if preferred_format else "FAIL",
                    "unit_interpretation": unit,
                    "conflicts": conflicts,
                    "published_value": value_text,
                    "published_unit": unit_text,
                    "extraction": extraction,
                }
            unresolved = [
                m
                for m in mentions
                if number(m["value"]) == value and m["interpretation"]["status"] != "MAPPED"
            ]
            if unresolved:
                return {
                    **base,
                    "status": "UNDETERMINED",
                    "reason": "unresolved_complete_actual_Final_amount_token",
                    "V_format": "PASS" if preferred_format else "FAIL",
                    "unit_interpretation": unit,
                    "unresolved_mentions": unresolved,
                    "published_value": value_text,
                    "published_unit": unit_text,
                    "extraction": extraction,
                }
        return {
            **base,
            "status": "MAPPED",
            "V_format": "PASS" if preferred_format else "FAIL",
            "published_value": value_text,
            "published_unit": unit_text,
            "exact_value": str(value),
            "unit_interpretation": unit,
            "extraction": extraction,
            "physical_value": str(value * Fraction(unit["scale"])),
        }
    except (ValueError, ZeroDivisionError, InvalidOperation) as error:
        return {
            **base,
            "status": "UNDETERMINED",
            "V_format": "FAIL",
            "reason": str(error),
            "published_value": None,
            "published_unit": None,
        }


def rounding_tolerance(value_text, actual_scale, target_scale):
    text = str(value_text).replace(",", "").replace(" ", "")
    if "/" in text:
        return Fraction(0)
    decimal = Decimal(text)
    quantum = abs(Fraction(Decimal(1).scaleb(decimal.as_tuple().exponent)))
    return min(
        Fraction(1, 200),
        max(
            quantum * Fraction(actual_scale) / Fraction(target_scale) / 2,
            Fraction(1, 10**12),
        ),
    )


def score_quantity(interpreted, reference_value, context):
    result = {
        "policy": VERSION,
        "V_format": interpreted["V_format"],
        "format_is_hard_validity_condition": False,
        "reference_exact_value": str(Fraction(reference_value)),
        "target_unit": context["preferred_unit"],
        "interpretation": interpreted,
        "numeric_correct": None,
        "unit_correct": None,
        "quantity_correct": None,
    }
    if interpreted["status"] != "MAPPED":
        status = "FAIL" if interpreted["status"] == "FAIL" else "UNDETERMINED"
        return {
            **result,
            "V_quantity": status,
            "task_answer_status": status,
            "reason": interpreted["reason"],
        }
    unit = interpreted["unit_interpretation"]
    dimension = unit["dimension"] == context["dimension"]
    currency = unit["currency"] == context["target_currency"]
    converted = Fraction(interpreted["physical_value"]) / Fraction(context["target_scale"])
    tolerance = rounding_tolerance(
        interpreted["published_value"], unit["scale"], context["target_scale"]
    )
    numeric = abs(converted - Fraction(reference_value)) <= tolerance
    valid = dimension and currency and numeric
    return {
        **result,
        "V_quantity": "PASS" if valid else "FAIL",
        "task_answer_status": "PASS" if valid else "FAIL",
        "numeric_correct": numeric,
        "unit_correct": dimension and currency,
        "quantity_correct": valid,
        "converted_to_target_scale": str(converted),
        "rounding_tolerance": str(tolerance),
        "published_value": interpreted["published_value"],
        "published_unit": interpreted["published_unit"],
        "reason": None if valid else "explicit_dimension_currency_or_scaled_amount_mismatch",
    }
