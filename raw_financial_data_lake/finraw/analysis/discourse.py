from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

DISCOURSE_PLAN_VERSION = "1.2.0"
INSTRUCTION_SURFACE_VERSION = "1.0.0"

_STYLE_PREFIXES = {
    "compact_evidence": "",
    "analyst_review": "Evidence-based review: ",
    "balanced_diagnosis": "On the available evidence, ",
}
_FIRST_TRANSITIONS = {
    "lead": "",
    "first": "First, ",
    "starting_with": "Starting with the operating signals, ",
}
_NEXT_TRANSITIONS = {
    "additionally": "Additionally, ",
    "however": "However, ",
    "meanwhile": "Meanwhile, ",
    "next": "Next, ",
}
_CONCLUSION_TRANSITIONS = {
    "overall": "Overall, ",
    "on_balance": "On balance, ",
    "taken_together": "Taken together, ",
}
_CAVEAT_TRANSITIONS = {
    "limitation": "As a limitation, ",
    "scope_caveat": "Regarding scope, ",
    "evidence_boundary": "Within this evidence boundary, ",
}

_INSTRUCTION_SURFACES = {
    "operating_trend_summary_v1": {
        "canonical": (
            "Based on the company's revenue, net income, and operating cash flow "
            "over the observed three-year period, summarize its operating trend and "
            "identify the main positive and cautionary signals."
        ),
        "analyst_brief": (
            "Prepare a concise analyst review of the company's three-year revenue, "
            "net-income, and operating-cash-flow trends, balancing favorable evidence "
            "against cautionary signals."
        ),
        "evidence_summary": (
            "Using only the supplied three-year operating evidence, explain how revenue, "
            "profit, and operating cash flow developed and state the main caveat."
        ),
    },
    "growth_quality_diagnosis_v1": {
        "canonical": (
            "Evaluate the company's growth quality using revenue, profit, operating cash "
            "flow, margin, and asset-efficiency signals. State the strongest positive "
            "evidence, the main risk signal, and the limits of the evidence."
        ),
        "analyst_brief": (
            "Assess the quality of the company's growth from the supplied revenue, "
            "profitability, cash-flow, margin, and asset-efficiency evidence, highlighting "
            "both support and constraints."
        ),
        "diagnostic_review": (
            "Diagnose whether the covered growth is internally well supported. Weigh "
            "revenue and profit performance against cash conversion, margin, and asset "
            "efficiency, and include an evidence limitation."
        ),
    },
    "peer_positioning_v1": {
        "canonical": (
            "Compare the company with the complete covered industry peer set on revenue "
            "growth, net margin, and leverage. Identify its main relative strength, "
            "weakness, and an evidence limitation."
        ),
        "analyst_brief": (
            "Position the company within the complete covered peer universe using revenue "
            "growth, net margin, and leverage, and summarize its strongest and weakest "
            "relative dimensions."
        ),
        "relative_diagnosis": (
            "Using the full eligible peer scope, diagnose the company's relative growth, "
            "profitability, and leverage position and qualify the conclusion with the "
            "evidence boundary."
        ),
    },
}

_SELECTABLE_NUMERIC_FIELDS = {
    "growth_pct",
    "spread_pct",
    "change_pp",
    "percentile",
    "target_value",
    "scope_size",
}


def instruction_surface_ids(pattern_id: str) -> list[str]:
    return sorted(_INSTRUCTION_SURFACES.get(pattern_id, {}))


def render_instruction(pattern_id: str, surface_form_id: str) -> str:
    try:
        return _INSTRUCTION_SURFACES[pattern_id][surface_form_id]
    except KeyError as exc:
        raise ValueError(
            f"Unknown instruction surface: {pattern_id}/{surface_form_id}"
        ) from exc


def selectable_numeric_slot_ids(claim: dict[str, Any]) -> list[str]:
    priority = {
        "growth_pct": 0,
        "spread_pct": 1,
        "change_pp": 2,
        "percentile": 3,
        "target_value": 4,
        "scope_size": 5,
    }
    slots = [
        slot
        for slot in claim.get("required_numeric_slots") or []
        if str(slot.get("field") or "") in _SELECTABLE_NUMERIC_FIELDS
    ]
    return [
        str(slot["slot_id"])
        for slot in sorted(
            slots,
            key=lambda slot: (
                priority[str(slot.get("field") or "")],
                str(slot["slot_id"]),
            ),
        )
    ]


def default_discourse_plan(
    mandatory_claims: list[dict[str, Any]],
    *,
    maximum_numeric_mentions: int,
) -> dict[str, Any]:
    claim_order = [str(claim["claim_id"]) for claim in mandatory_claims]
    seed = int(
        hashlib.sha256("|".join(claim_order).encode("utf-8")).hexdigest()[:16],
        16,
    )
    transition_ids = []
    selected: dict[str, list[str]] = {}
    remaining = max(maximum_numeric_mentions, 0)
    first_choices = sorted(_FIRST_TRANSITIONS)
    support_choices = ("additionally", "meanwhile", "next")
    risk_choices = ("however", "meanwhile")
    for index, claim in enumerate(mandatory_claims):
        if index == 0:
            transition_ids.append(first_choices[seed % len(first_choices)])
        elif claim.get("claim_role") == "risk":
            transition_ids.append(risk_choices[(seed + index) % len(risk_choices)])
        else:
            transition_ids.append(
                support_choices[(seed + index) % len(support_choices)]
            )
        available = selectable_numeric_slot_ids(claim)
        chosen = available[:1] if available and remaining else []
        selected[str(claim["claim_id"])] = chosen
        remaining -= len(chosen)
    return {
        "plan_version": DISCOURSE_PLAN_VERSION,
        "style_id": sorted(_STYLE_PREFIXES)[seed % len(_STYLE_PREFIXES)],
        "claim_order": claim_order,
        "transition_ids": transition_ids,
        "selected_numeric_slot_ids": selected,
        "conclusion_transition_id": sorted(_CONCLUSION_TRANSITIONS)[
            (seed // 3) % len(_CONCLUSION_TRANSITIONS)
        ],
        "caveat_transition_id": sorted(_CAVEAT_TRANSITIONS)[
            (seed // 7) % len(_CAVEAT_TRANSITIONS)
        ],
    }


def validate_discourse_plan(
    observed: Any,
    mandatory_claims: list[dict[str, Any]],
    *,
    maximum_numeric_mentions: int,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(observed, dict):
        return {"passed": False, "errors": ["discourse_plan_not_object"]}
    expected_fields = {
        "plan_version",
        "style_id",
        "claim_order",
        "transition_ids",
        "selected_numeric_slot_ids",
        "conclusion_transition_id",
        "caveat_transition_id",
    }
    if set(observed) != expected_fields:
        errors.append("discourse_plan_fields_mismatch")
    if str(observed.get("plan_version") or "") != DISCOURSE_PLAN_VERSION:
        errors.append("discourse_plan_version_mismatch")
    if str(observed.get("style_id") or "") not in _STYLE_PREFIXES:
        errors.append("discourse_style_unknown")
    expected_ids = [str(claim["claim_id"]) for claim in mandatory_claims]
    claim_order = [str(value) for value in observed.get("claim_order") or []]
    if sorted(claim_order) != sorted(expected_ids) or len(claim_order) != len(
        set(claim_order)
    ):
        errors.append("discourse_claim_order_mismatch")
    transitions = [str(value) for value in observed.get("transition_ids") or []]
    if len(transitions) != len(expected_ids):
        errors.append("discourse_transition_count_mismatch")
    elif transitions:
        if transitions[0] not in _FIRST_TRANSITIONS:
            errors.append("discourse_first_transition_unknown")
        if any(value not in _NEXT_TRANSITIONS for value in transitions[1:]):
            errors.append("discourse_next_transition_unknown")
    if str(observed.get("conclusion_transition_id") or "") not in (
        _CONCLUSION_TRANSITIONS
    ):
        errors.append("discourse_conclusion_transition_unknown")
    if str(observed.get("caveat_transition_id") or "") not in _CAVEAT_TRANSITIONS:
        errors.append("discourse_caveat_transition_unknown")
    numeric = observed.get("selected_numeric_slot_ids")
    numeric = numeric if isinstance(numeric, dict) else {}
    if set(str(key) for key in numeric) != set(expected_ids):
        errors.append("discourse_numeric_claim_set_mismatch")
    claim_by_id = {str(claim["claim_id"]): claim for claim in mandatory_claims}
    selected_count = 0
    for claim_id, values in numeric.items():
        selected_ids = [str(value) for value in values or []]
        if len(selected_ids) != len(set(selected_ids)):
            errors.append(f"discourse_numeric_duplicate:{claim_id}")
        available = set(selectable_numeric_slot_ids(claim_by_id.get(str(claim_id), {})))
        if not set(selected_ids).issubset(available):
            errors.append(f"discourse_numeric_slot_invalid:{claim_id}")
        if len(selected_ids) > 1:
            errors.append(f"discourse_numeric_per_claim_limit:{claim_id}")
        selected_count += len(selected_ids)
    if selected_count > max(maximum_numeric_mentions, 0):
        errors.append("discourse_numeric_global_limit")
    normalized = {
        "plan_version": str(observed.get("plan_version") or ""),
        "style_id": str(observed.get("style_id") or ""),
        "claim_order": claim_order,
        "transition_ids": transitions,
        "selected_numeric_slot_ids": {
            str(key): [str(value) for value in values or []]
            for key, values in numeric.items()
        },
        "conclusion_transition_id": str(
            observed.get("conclusion_transition_id") or ""
        ),
        "caveat_transition_id": str(observed.get("caveat_transition_id") or ""),
    }
    return {"passed": not errors, "errors": errors, "plan": normalized}


def _format_numeric_value(value: Any, unit: str) -> str:
    text = str(value if value is not None else "")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    places = Decimal("1") if unit in {"count", "year"} else Decimal("0.01")
    rendered = format(number.quantize(places, rounding=ROUND_HALF_UP), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def render_numeric_slot(slot: dict[str, Any]) -> str:
    label = str(slot.get("display_label") or slot.get("field") or "signal").replace(
        "_", " "
    )
    unit = str(slot.get("unit") or "number")
    value = _format_numeric_value(slot.get("value"), unit)
    if unit == "percent":
        display = f"{value}%"
    elif unit == "percentage_point":
        display = f"{value} percentage points"
    elif unit == "year":
        display = value
    elif unit == "count":
        display = value
    elif unit == "number":
        display = value
    else:
        display = f"{value} {unit}"
    return f"The registered {label} is {display}."


def _join_transition(prefix: str, sentence: str) -> str:
    if not prefix:
        return sentence
    lowered = sentence
    for registered_lead in ("overall, ", "on balance, ", "taken together, "):
        if lowered.lower().startswith(registered_lead):
            lowered = lowered[len(registered_lead) :]
            break
    if lowered and prefix[-1:] in {",", " "}:
        lowered = lowered[0].lower() + lowered[1:]
    return prefix + lowered


def render_analysis_text(
    alignment: list[dict[str, Any]],
    conclusion_text: str,
    caveats: list[dict[str, Any]],
    discourse_plan: dict[str, Any],
) -> str:
    by_id = {str(item.get("claim_id")): item for item in alignment}
    parts: list[str] = []
    for index, (claim_id, transition_id) in enumerate(
        zip(discourse_plan["claim_order"], discourse_plan["transition_ids"])
    ):
        item = by_id[claim_id]
        transition = (
            _FIRST_TRANSITIONS[transition_id]
            if index == 0
            else _NEXT_TRANSITIONS[transition_id]
        )
        prefix = _STYLE_PREFIXES[discourse_plan["style_id"]] if index == 0 else ""
        parts.append(_join_transition(prefix + transition, str(item["sentence"])))
        parts.extend(str(value) for value in item.get("numeric_sentences") or [])
    parts.append(
        _join_transition(
            _CONCLUSION_TRANSITIONS[discourse_plan["conclusion_transition_id"]],
            conclusion_text,
        )
    )
    caveat_prefix = _CAVEAT_TRANSITIONS[discourse_plan["caveat_transition_id"]]
    for caveat in caveats:
        parts.append(_join_transition(caveat_prefix, str(caveat["sentence"])))
        caveat_prefix = ""
    return " ".join(part for part in parts if part)


def discourse_manifest() -> dict[str, Any]:
    payload = {
        "discourse_plan_version": DISCOURSE_PLAN_VERSION,
        "instruction_surface_version": INSTRUCTION_SURFACE_VERSION,
        "styles": _STYLE_PREFIXES,
        "first_transitions": _FIRST_TRANSITIONS,
        "next_transitions": _NEXT_TRANSITIONS,
        "conclusion_transitions": _CONCLUSION_TRANSITIONS,
        "caveat_transitions": _CAVEAT_TRANSITIONS,
        "instruction_surfaces": _INSTRUCTION_SURFACES,
        "selectable_numeric_fields": sorted(_SELECTABLE_NUMERIC_FIELDS),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "manifest_hash": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }
