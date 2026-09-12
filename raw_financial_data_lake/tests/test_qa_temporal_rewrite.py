"""Actual-function controls for the temporal rewrite failures in the 2026-09-12 audit."""

import json

import pytest
from finraw.qa.verbalizer import (
    QUESTION_REWRITE_VERSION,
    build_question_contract,
    realize_question,
    render_protected_question,
    validate_protected_rewrite,
    validate_question_roundtrip,
    validate_rewrite_numeric_grounding,
)

SLOTS = {
    "entity": "Example Inc",
    "metric": "Revenue",
    "previous_period": "2020-12-31",
    "period": "2021-12-31",
    "output_instruction": "Return the value rounded to 2 decimal places.",
}
BASE = "For <slot_entity>, compute the change in <slot_metric> from <slot_previous_period> to <slot_period>"


def semantics(growth=False):
    operators = [
        {
            "step_id": "change",
            "operator": "difference",
            "inputs": [{"binding": "previous"}, {"binding": "current"}],
        }
    ]
    if growth:
        operators.append(
            {
                "step_id": "rate",
                "operator": "ratio_percent",
                "inputs": [{"step": "change"}, {"binding": "previous"}],
            }
        )
    return {
        "operation_plan": {
            "operators": operators,
            "output_step": operators[-1]["step_id"],
        },
        "answer_payload": {"value": "PRIVATE_ANSWER_CANARY"},
        "endpoint_movement_roles": "PRIVATE_ROUTE_CANARY",
    }


def check(template, *, growth=False, source_slots=None, plan=None):
    slots = source_slots or SLOTS
    payload = {
        "rewrite_version": QUESTION_REWRITE_VERSION,
        "question_template": template,
    }
    structural = validate_protected_rewrite(
        payload, ["<slot_" + key + ">" for key in slots]
    )
    question = render_protected_question(template, slots)
    contract = build_question_contract(plan or semantics(growth), slots, list(slots))
    meaning = validate_question_roundtrip(question, contract, trusted_contract=True)
    numbers = validate_rewrite_numeric_grounding(question, slots)
    return structural["passed"] and meaning["passed"] and numbers["passed"], meaning


@pytest.mark.parametrize(
    ("template", "growth", "expected"),
    [
        (BASE + ". <slot_output_instruction>", False, True),
        (
            "For <slot_entity>, calculate <slot_metric> at <slot_previous_period> minus its value at <slot_period>. <slot_output_instruction>",
            False,
            False,
        ),
        (
            "For <slot_entity>, add <slot_metric> at <slot_previous_period> and <slot_period>. <slot_output_instruction>",
            False,
            False,
        ),
        (
            BASE + " as a percentage of the previous value. <slot_output_instruction>",
            True,
            True,
        ),
        (
            BASE + " as a percentage of the current value. <slot_output_instruction>",
            True,
            False,
        ),
        (
            BASE.replace("<slot_metric>", "the measure")
            + ". <slot_output_instruction>",
            False,
            False,
        ),
        (BASE + ", then add 42 units. <slot_output_instruction>", False, False),
        (BASE + ", then add 42. <slot_output_instruction>", False, False),
    ],
)
def test_eight_audit_counterexamples(template, growth, expected):
    assert check(template, growth=growth)[0] is expected


@pytest.mark.parametrize(
    "template",
    [
        "Calculate the change in <slot_entity>'s <slot_metric> from <slot_previous_period> to <slot_period>. <slot_output_instruction>",
        "By how much did <slot_entity>'s <slot_metric> change from <slot_previous_period> to <slot_period>? <slot_output_instruction>",
        "For <slot_entity>, determine the signed change in <slot_metric> between <slot_previous_period> and <slot_period>. <slot_output_instruction>",
        "Subtract the <slot_previous_period> value of <slot_metric> from the <slot_period> value for <slot_entity>. <slot_output_instruction>",
    ],
)
def test_multiple_legal_signed_change_forms(template):
    assert check(template)[0]


@pytest.mark.parametrize(
    "change",
    [
        "absolute change",
        "sum",
        "average",
        "percentage change",
        "quarterly change",
        "adjusted change",
    ],
)
def test_different_operation_quantity_or_scope_is_not_a_paraphrase(change):
    assert not check(
        BASE.replace("the change", "the " + change) + ". <slot_output_instruction>"
    )[0]


def test_reversed_from_to_order_is_not_sorted_away():
    template = BASE.replace(
        "from <slot_previous_period> to <slot_period>",
        "from <slot_period> to <slot_previous_period>",
    )
    passed, detail = check(template + ". <slot_output_instruction>")
    assert not passed
    assert "question_semantics:temporal_direction_mismatch" in detail["contract_errors"]


@pytest.mark.parametrize(
    "expression", ["42.", "(42).", "-42.", "+42.", "−42.", "42.5.", ".42."]
)
def test_numeric_grounding_catches_punctuation_signs_and_decimals(expression):
    result = validate_rewrite_numeric_grounding(
        "Then add " + expression, {"period": "2021-12-31"}
    )
    assert not result["passed"]


def test_numeric_grounding_preserves_date_and_decimal_slots():
    slots = {"period": "2021-12-31", "threshold": "-42.5"}
    assert validate_rewrite_numeric_grounding("As of 2021-12-31, use -42.5.", slots)[
        "passed"
    ]


def test_actual_plan_input_roles_are_required_and_retained():
    contract = build_question_contract(semantics(True), SLOTS, list(SLOTS))
    assert contract["constraints"][1]["inputs"][1] == {"binding": "previous"}
    bad = semantics(True)
    bad["operation_plan"]["operators"][1]["inputs"][1] = {"binding": "current"}
    assert not check(
        BASE + " as a percentage of the previous value. <slot_output_instruction>",
        growth=True,
        plan=bad,
    )[0]


class Provider:
    def __init__(self, values):
        self.values, self.requests = values, []
        self.last_telemetry = {
            "request_count": 1,
            "http_success": True,
            "json_valid": True,
        }

    def generate(self, request):
        self.requests.append(request)
        return self.values


def test_response_order_and_private_cues():
    variants = [
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": BASE + ". <slot_output_instruction>",
        },
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": BASE.replace("compute", "determine")
            + ". <slot_output_instruction>",
        },
    ]
    provider = Provider(variants)
    result = realize_question(
        render_protected_question(variants[0]["question_template"], SLOTS),
        semantics=semantics(),
        immutable_slots=SLOTS,
        required_slots=list(SLOTS),
        config={
            "mode": "controlled_llm",
            "strategy": "protected_rewrite",
            "max_attempts": 2,
            "variants": 2,
            "style_variant_id": "analyst",
            "variant_order": "response_order",
            "surface_variation": {"enabled": False, "llm_selects_variants": False},
        },
        provider=provider,
        protected_question=variants[0]["question_template"],
    )
    assert result.validation["rewrite_variant_index"] == 0
    request = json.dumps(provider.requests[0])
    assert (
        "PRIVATE_ANSWER_CANARY" not in request and "PRIVATE_ROUTE_CANARY" not in request
    )
    assert "Example Inc" not in request and "2020-12-31" not in request
    assert (
        provider.requests[0]["semantic_cues"]["temporal_quantity"]["direction"]
        == "current_minus_previous"
    )


def test_empty_response_is_not_retried_without_a_contract_failure():
    provider = Provider([])
    template = BASE + ". <slot_output_instruction>"
    result = realize_question(
        render_protected_question(template, SLOTS),
        semantics=semantics(),
        immutable_slots=SLOTS,
        required_slots=list(SLOTS),
        config={
            "mode": "controlled_llm",
            "strategy": "protected_rewrite",
            "max_attempts": 2,
            "surface_variation": {"enabled": False},
        },
        provider=provider,
        protected_question=template,
    )
    assert len(provider.requests) == 1
    assert result.generation_method == "deterministic_surface_fallback"
