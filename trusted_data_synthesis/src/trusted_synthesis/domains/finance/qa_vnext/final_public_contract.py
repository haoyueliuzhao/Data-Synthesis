"""Publish the unchanged Share Final boundary and diagnose, never repair, submissions.

The publisher contains source paths and transformations, not chosen Claim/State
ids or precomputed answers. Diagnostics may compare a submitted representation
with its already public accepted Claim; they never call a financial operation,
the Runtime, or the independent source-answer verifier.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Any

from .protocol import Final, record, require

VERSION = "finance_qa_final_public_contract.v1"
VALUE_PATTERN = r"^-?(?:0|[1-9][0-9]*)\.[0-9]{6}$"


def final_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "value": {
                "type": "string",
                "pattern": VALUE_PATTERN,
                "description": (
                    "Selected accepted percent Claim value, Decimal-quantized using "
                    "/context/numeric and serialized with exactly six fractional digits; "
                    "no percent sign. This is not the full unrounded Claim value."
                ),
            },
            "unit": {"type": "string", "const": "percent"},
        },
        "required": ["value", "unit"],
        "additionalProperties": False,
    }


def public_final_schema() -> dict[str, Any]:
    """The displayed Schema only; the original parser's Final model is unchanged."""
    schema = Final.model_json_schema()
    schema["properties"]["result"] = final_result_schema()
    schema["properties"]["state_id"]["description"] = "Copy /state/id from this Request exactly."
    schema["properties"]["answer_claim_id"]["description"] = (
        "Choose one current /final_claim_ids entry identifying an accepted percent Claim."
    )
    schema["properties"]["citations"].update(
        uniqueItems=True,
        description=(
            "Set exactly equal to selected accepted answer Claim /proposition/lineage; no extras."
        ),
    )
    return schema


def public_final_contract() -> dict[str, Any]:
    rules: list[dict[str, Any]] = []

    def add(name: str, code: str, fields: dict[str, Any], requirement: str) -> None:
        rules.append(
            {
                "rule_id": VERSION + ":" + name,
                "error_code": code,
                "fields": fields,
                "requirement": requirement,
            }
        )

    add(
        "schema",
        "submission.schema",
        {"/kind": {"literal": "final"}},
        "Return one Final matching /response_schemas/final; no extra outer or result fields.",
    )
    add(
        "current_state",
        "admission.current_state",
        {"/state_id": {"copy_from": "/state/id"}},
        "Copy the State id from THIS Request exactly. "
        "Do not invent, edit or reuse another State id.",
    )
    add("terminal", "admission.terminal", {}, "Final requires /state/terminal=false.")
    add(
        "accepted_answer",
        "admission.final_accepted_claim",
        {"/answer_claim_id": {"choose_id_from": "/final_claim_ids"}},
        "Choose one id in this Request's final_claim_ids. It identifies an already accepted "
        "percent Claim in /state/accepted_claims, with obligation_id=percent and "
        "proposition.operation=scale_percent. No pending Observation, other intermediate "
        "Claim or other-session answer is eligible. /state/pending_observation must be null.",
    )
    add(
        "result_fields",
        "admission.final_qa",
        {"/result": {"required_fields": ["value", "unit"], "allowed_fields": ["value", "unit"]}},
        "result has EXACTLY value and unit. Do not copy metric, period, subject, scope, "
        "currency, definition, lineage or other Claim/proposition metadata into result.",
    )
    add(
        "value_projection",
        "admission.final_qa",
        {
            "/result/value": {
                "from_selected": "/proposition/output/value",
                "transform": {
                    "operation": "decimal_quantize",
                    "precision_from": "/context/numeric/precision",
                    "rounding_from": "/context/numeric/rounding",
                    "quantum_from": "/context/numeric/final_quantum",
                    "serialization": "fixed_six_decimal_string",
                    "append_percent_symbol": False,
                },
            }
        },
        "Use the selected Claim's existing value; Decimal-quantize at precision=50, "
        "ROUND_HALF_EVEN, final_quantum=0.000001 as specified in the current numeric contract. "
        "Submit a STRING with exactly six fractional digits, without a percent sign. "
        "Do not submit a JSON number or the unquantized full-precision Claim string.",
    )
    add(
        "unit",
        "admission.final_qa",
        {"/result/unit": {"literal": "percent"}},
        'unit must be the exact string "percent"; it is a separate field from value.',
    )
    add(
        "actual_lineage",
        "admission.final_qa",
        {
            "/citations": {
                "set_from_selected": "/proposition/lineage",
                "unique": True,
                "order_significant": False,
                "elements_kind": "current_context_evidence_ids",
            }
        },
        "Citations must be unique and their set must equal the selected accepted answer "
        "Claim's actual Evidence lineage exactly. Cite its actual calculation support, "
        "not every visible source, the answer Claim id, or unused intermediate Claims. "
        "A disclosed denominator and a reconstructed denominator can have different lineage.",
    )
    add(
        "source_consistency",
        "admission.final_qa",
        {},
        "The unchanged original adapter also requires the answer to agree with its "
        "independent source calculation. Publication does not relax or replace that check.",
    )
    return record(
        "final_public_contract",
        version=VERSION,
        selected_binding={
            "request_collection": "/state/accepted_claims",
            "id_field": "id",
            "response_selector": "/answer_claim_id",
            "allowed_ids_from": "/final_claim_ids",
        },
        path_notation=(
            "RFC 6901 pointers in the current Request; "
            "from_selected paths start at the chosen Claim"
        ),
        result_schema=final_result_schema(),
        rules=rules,
        update_final_distinction=(
            "Update accept copies the ENTIRE pending proposition at original precision. "
            "Final instead submits only the prescribed two-field answer projection and "
            "the actual Evidence lineage. Do not copy the complete proposition into Final.result."
        ),
        parser_submission_contract_unchanged=True,
        original_admission_and_verifier_unchanged=True,
        response_schema_refines_existing_final_requirement=True,
        host_fills_response_fields=False,
        host_selects_answer_claim=False,
        precomputed_answer_supplied=False,
        publication_executes_finance=False,
        diagnostics_only_use_current_public_information=True,
    )


def publish_final_contract(request: dict[str, Any]) -> dict[str, Any]:
    """Add one publication and refine the displayed Schema; preserve all other fields."""
    require("public_final_contract" not in request, "final_publication.already_present")
    context = request["context"]
    require(
        context["final_projection"] == "share_percent_quantized"
        and context["numeric"]["precision"] == 50
        and context["numeric"]["rounding"] == "ROUND_HALF_EVEN"
        and context["numeric"]["final_quantum"] == "0.000001",
        "final_publication.bound_numeric_contract",
    )
    fields = {
        key: copy.deepcopy(value)
        for key, value in request.items()
        if key not in {"id", "schema_version"}
    }
    fields["response_schemas"]["final"] = public_final_schema()
    return record("request", **fields, public_final_contract=public_final_contract())


def _selected_claim(request: dict[str, Any], submitted: dict[str, Any]) -> dict[str, Any] | None:
    chosen = submitted.get("answer_claim_id")
    matches = [claim for claim in request["state"]["accepted_claims"] if claim.get("id") == chosen]
    if chosen not in request["final_claim_ids"] or len(matches) != 1:
        return None
    claim = matches[0]
    proposition = claim.get("proposition", {})
    if (
        claim.get("status") != "accepted"
        or claim.get("obligation_id") != "percent"
        or proposition.get("operation") != "scale_percent"
        or proposition.get("output", {}).get("unit") != "percent"
    ):
        return None
    return claim


def rejection_feedback(
    code: str | None,
    request: dict[str, Any],
    submitted: dict[str, Any] | None,
) -> dict[str, Any]:
    """Finite public diagnostics, preserving the actual earlier admission error code."""
    feedback: dict[str, Any] = {"code": code, "admitted": False}
    publication = request.get("public_final_contract")
    if publication is None or (submitted is not None and submitted.get("kind") != "final"):
        return feedback
    rule_map = {rule["rule_id"].removeprefix(VERSION + ":"): rule for rule in publication["rules"]}
    violations: list[dict[str, Any]] = []

    def add(name: str, paths: list[str], **details: Any) -> None:
        rule = rule_map[name]
        violations.append(
            {
                "rule_id": rule["rule_id"],
                "category": name,
                "response_field_paths": paths,
                "public_source_mapping": copy.deepcopy(rule["fields"]),
                "requirement": rule["requirement"],
                **details,
            }
        )

    if code == "admission.current_state":
        add("current_state", ["/state_id"], required_state_source="/state/id")
    elif code == "admission.terminal":
        add("terminal", [], required_terminal_source="/state/terminal")
    elif code == "admission.final_accepted_claim":
        add(
            "accepted_answer",
            ["/answer_claim_id"],
            pending_observation_present=request["state"]["pending_observation"] is not None,
        )
    elif code == "submission.schema" or submitted is None:
        add("schema", ["/"], schema_source="/response_schemas/final")
    elif code == "admission.final_qa":
        claim = _selected_claim(request, submitted)
        if claim is None:
            add("accepted_answer", ["/answer_claim_id"])
        result = submitted.get("result")
        if not isinstance(result, dict):
            add("result_fields", ["/result"], required_type="object")
        else:
            missing, extra = (
                sorted({"value", "unit"} - set(result)),
                sorted(set(result) - {"value", "unit"}),
            )
            if missing or extra:
                add(
                    "result_fields",
                    ["/result/" + key for key in sorted(set(missing + extra))],
                    missing_fields=missing,
                    extra_fields=extra,
                )
            value = result.get("value")
            if "value" in result:
                if not isinstance(value, str):
                    add(
                        "value_projection",
                        ["/result/value"],
                        violation="value_type",
                        required_type="string",
                        observed_type="null" if value is None else type(value).__name__,
                    )
                elif not re.fullmatch(VALUE_PATTERN, value):
                    add(
                        "value_projection",
                        ["/result/value"],
                        violation="value_quantum_format",
                        required_pattern=VALUE_PATTERN,
                    )
                elif claim is not None:
                    # Represent only the public existing value; never recompute F/O/T.
                    try:
                        numeric = request["context"]["numeric"]
                        with localcontext() as decimal_context:
                            decimal_context.prec = numeric["precision"]
                            projected = Decimal(claim["proposition"]["output"]["value"]).quantize(
                                Decimal(numeric["final_quantum"]), rounding=ROUND_HALF_EVEN
                            )
                        if value != str(projected):
                            add(
                                "value_projection",
                                ["/result/value"],
                                violation="selected_claim_projection_mismatch",
                            )
                    except (InvalidOperation, ValueError, KeyError, TypeError):
                        add(
                            "value_projection",
                            ["/result/value"],
                            violation="public_projection_unavailable",
                        )
            if "unit" in result and result["unit"] != "percent":
                add("unit", ["/result/unit"], allowed_unit="percent")
        citations = submitted.get("citations")
        if not isinstance(citations, list) or any(not isinstance(item, str) for item in citations):
            add("actual_lineage", ["/citations"], required_type="unique string array")
        elif claim is not None:
            expected = set(claim["proposition"]["lineage"])
            observed = set(citations)
            duplicates = sorted(key for key, count in Counter(citations).items() if count > 1)
            if expected != observed or duplicates:
                add(
                    "actual_lineage",
                    ["/citations"],
                    missing_ids=sorted(expected - observed),
                    extra_ids=sorted(observed - expected),
                    duplicate_ids=duplicates,
                )
        if not violations:
            add(
                "source_consistency",
                ["/result", "/citations"],
                violation="unchanged_final_qa_rejected_no_additional_public_mismatch_identified",
            )
    else:
        return feedback
    feedback["public_diagnostic"] = {
        "contract_id": publication["id"],
        "version": publication["version"],
        "rule_id": VERSION + ":" + (code or "unknown").removeprefix("admission."),
        "response_field_paths": sorted(
            {path for row in violations for path in row["response_field_paths"]}
        ),
        "violations": violations,
        "response_rewritten": False,
        "replacement_answer_supplied": False,
        "answer_claim_selected_by_host": False,
        "financial_operations_executed": False,
        "source_answer_verifier_called": False,
        "runtime_state_modified": False,
        "observed_gate_error_code_preserved": True,
    }
    return feedback
