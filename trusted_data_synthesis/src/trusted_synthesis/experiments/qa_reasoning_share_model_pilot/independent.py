"""Independent evidence closure, public-protocol replay and six-session measurement.

The public grammar and arithmetic are reproduced locally from the frozen protocol;
no Host parser, prepare function, Engine, adapter or operation kernel is imported.
Provider provenance is checked before semantic replay so incomplete evidence stays
unknown instead of being silently converted into an observed model failure.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

CONTEXT_FIELDS = ("subject", "scope", "period", "unit", "currency")
VIEW_FIELDS = ("task", "evidence", "operations", "numeric", "shared_obligations", "answer_schema")
DYNAMIC_FIELDS = {
    "phase",
    "accepted_claims",
    "pending_observation",
    "action_count",
    "update_count",
    "submission_count",
    "last_feedback",
    "terminal",
}
COUNTERS = {"actions": "action_count", "updates": "update_count", "submissions": "submission_count"}
SCALAR_FIELDS = {"value", "metric", "definition", *CONTEXT_FIELDS, "lineage"}
BUNDLE_FIELDS = {
    "event",
    "request",
    "generator_turn",
    "submission",
    "receipt",
    "execution",
    "observation",
    "claim",
    "final",
    "post_state",
}
RECORD_FIELDS = {
    "generator_turn": {
        "request_id",
        "state_id",
        "generator_binding_id",
        "origin",
        "response_sha256",
        "response_byte_count",
        "callback_error",
        "provider_calls",
        "host_supplied_response",
    },
    "submission": {
        "generator_turn_id",
        "request_id",
        "state_id",
        "parsed",
        "raw_public_json",
        "response_sha256",
        "response_byte_count",
        "field_origin",
        "host_repairs",
    },
    "receipt": {
        "submission_id",
        "request_id",
        "pre_state_id",
        "admitted",
        "code",
        "dispatch_permitted",
        "submission_sha256",
        "submission_byte_count",
        "no_replace",
        "missing_fields_filled",
        "response_rewritten",
    },
    "execution": {
        "submission_id",
        "generator_turn_id",
        "operation",
        "operation_contract_id",
        "parameters",
        "inputs",
        "output",
        "field_origin",
    },
    "observation": {
        "execution_id",
        "action_submission_id",
        "operation",
        "output",
        "success",
        "field_origin",
    },
    "claim": {
        "task_id",
        "observation_id",
        "update_submission_id",
        "generator_turn_id",
        "proposition",
        "grounding",
        "producer_operation",
        "status",
        "field_origin",
    },
    "final": {
        "task_id",
        "submission_id",
        "generator_turn_id",
        "answer",
        "answer_claim_id",
        "citations",
        "field_origin",
    },
    "event": {
        "sequence",
        "pre_state_id",
        "post_state_id",
        "request_id",
        "generator_turn_id",
        "submission_id",
        "receipt_id",
        "execution_id",
        "observation_id",
        "claim_id",
        "final_id",
    },
}
INSTRUCTIONS = (
    "Return exactly one JSON object matching an allowed submission schema. "
    "Choose the operation, current visible operand references, and parameters yourself. "
    "After an action Observation, explicitly accept or reject it in an update before "
    "submitting another action or a final answer. An accepted claim must be fully "
    "submitted and supported by that actual Observation. Cite the actual support; "
    "do not include private reasoning."
)


class IndependentError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


class SubmissionRejected(ValueError):
    """A public rejection independently reconstructed before arithmetic dispatch."""


def _check(condition: bool, stage: str, reason: str) -> None:
    if not condition:
        raise IndependentError(stage, reason)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SubmissionRejected(code)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record(kind: str, **fields: Any) -> dict[str, Any]:
    body = {"schema_version": f"public_share_protocol_{kind}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"public_share_protocol_{kind}:")}


def _identity(obj: Mapping[str, Any], kind: str | None = None) -> None:
    _check(isinstance(obj, Mapping), "independent.record_schema", "record is not an object")
    schema = obj["schema_version"]
    _check(
        isinstance(schema, str) and schema.endswith(".v1"),
        "independent.record_schema",
        "unsupported record version",
    )
    if kind is not None:
        _check(
            schema == f"public_share_protocol_{kind}.v1",
            "independent.record_schema",
            "record type differs",
        )
        if kind in RECORD_FIELDS:
            _check(
                set(obj) == RECORD_FIELDS[kind] | {"id", "schema_version"},
                "independent.record_schema",
                "missing or unsupported record fields",
            )
    _check(
        obj["id"]
        == strict_canonical_hash(
            {key: value for key, value in obj.items() if key != "id"},
            prefix=schema.removesuffix(".v1") + ":",
        ),
        "independent.record_identity",
        "record content identity differs",
    )


def _number(value: Any) -> Decimal:
    _require(isinstance(value, str), "admission.numeric")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise SubmissionRejected("admission.numeric") from error
    _require(number.is_finite(), "admission.numeric")
    return number


def _same_ids(actual: list[str], expected: list[str]) -> bool:
    return len(actual) == len(set(actual)) and set(actual) == set(expected)


def _shape(value: Any, fields: set[str]) -> None:
    _require(isinstance(value, dict) and set(value) == fields, "schema.public_submission")


def _text(value: Any, nonempty: bool = True) -> None:
    _require(isinstance(value, str) and (bool(value) or not nonempty), "schema.public_submission")


def _strings(value: Any, nonempty: bool = False) -> None:
    _require(isinstance(value, list) and (bool(value) or not nonempty), "schema.public_submission")
    for item in value:
        _text(item, False)


def _parse_raw(text: str) -> dict[str, Any]:
    """Manual independent public grammar, with no coercion or missing-field repair."""
    raw = text.encode("utf-8")
    _require(0 < len(raw) <= 32_768, "schema.payload_bytes")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            _require(key not in result, "schema.duplicate_key")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise SubmissionRejected("schema.public_submission") from error
    _require(isinstance(parsed, dict), "schema.object_required")
    kind = parsed.get("kind")
    _require(kind in ("action", "update", "final"), "schema.kind")
    if kind == "action":
        _shape(parsed, {"kind", "state_id", "operation", "inputs", "parameters", "public_basis"})
        _require(
            parsed["operation"] in ("relation_sum", "share_ratio", "scale_percent"),
            "schema.public_submission",
        )
        _require(isinstance(parsed["inputs"], list), "schema.public_submission")
        for operand in parsed["inputs"]:
            _shape(operand, {"role", "kind", "ref_id"})
            _require(
                operand["role"] in ("member", "relation", "numerator", "denominator", "ratio")
                and operand["kind"] in ("evidence", "claim"),
                "schema.public_submission",
            )
            _text(operand["ref_id"])
        _require(isinstance(parsed["parameters"], dict), "schema.public_submission")
        for key, value in parsed["parameters"].items():
            _text(key, False)
            _text(value, False)
        basis = parsed["public_basis"]
        _shape(basis, {"relation", "evidence_refs", "claim_refs", "intended_metric"})
        _require(basis["relation"] == "requires", "schema.public_submission")
        _strings(basis["evidence_refs"])
        _strings(basis["claim_refs"])
        _text(basis["intended_metric"])
    elif kind == "update":
        _shape(
            parsed,
            {"kind", "state_id", "observation_id", "disposition", "proposed_claim", "public_basis"},
        )
        _text(parsed["observation_id"])
        _require(parsed["disposition"] in ("accept", "reject"), "schema.public_submission")
        claim = parsed["proposed_claim"]
        if claim is not None:
            _shape(claim, SCALAR_FIELDS)
            for key in SCALAR_FIELDS - {"lineage"}:
                _text(claim[key])
            _strings(claim["lineage"], True)
        basis = parsed["public_basis"]
        _shape(basis, {"relation", "observation_refs", "evidence_refs"})
        _require(basis["relation"] in ("supports", "declines"), "schema.public_submission")
        _strings(basis["observation_refs"])
        _strings(basis["evidence_refs"])
    else:
        _shape(
            parsed, {"kind", "state_id", "answer_claim_id", "answer", "citations", "public_basis"}
        )
        _text(parsed["answer_claim_id"])
        _shape(parsed["answer"], {"value", "unit"})
        _text(parsed["answer"]["value"])
        _require(parsed["answer"]["unit"] == "percent", "schema.public_submission")
        _strings(parsed["citations"])
        basis = parsed["public_basis"]
        _shape(basis, {"relation", "claim_refs", "evidence_refs"})
        _require(basis["relation"] == "supports", "schema.public_submission")
        _strings(basis["claim_refs"])
        _strings(basis["evidence_refs"])
    _text(parsed["state_id"])
    return parsed


def _pilot_record(record_type: str, **fields: Any) -> dict[str, Any]:
    body = {"schema_version": f"share_model_pilot_{record_type}.v1", **copy.deepcopy(fields)}
    return {**body, "id": strict_canonical_hash(body, prefix=f"share_model_pilot_{record_type}:")}


def _context(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
    binding: Mapping[str, Any],
    config: Mapping[str, Any],
    registration: Mapping[str, Any],
) -> str:
    for obj in (
        source,
        legacy,
        legacy["task"],
        *source["evidence"].values(),
        *legacy["operations"].values(),
        context,
        protocol,
        binding,
        config,
        registration,
    ):
        _identity(obj)
    _check(
        source["id"] == legacy["source_binding_id"] == legacy["task"]["source_binding_id"],
        "evidence.frozen_context",
        "source and task are not the frozen common binding",
    )
    expected = _record(
        "public_context",
        task=legacy["task"],
        evidence=source["evidence"],
        operations=legacy["operations"],
        numeric=legacy["numeric"],
        shared_obligations=legacy["shared_obligations"],
        answer_schema=legacy["answer_schema"],
        actual_support_citations_required=legacy["actual_support_citations_required"],
        all_visible_evidence_citations_required=legacy["all_visible_evidence_citations_required"],
    )
    _check(
        context == expected,
        "evidence.frozen_context",
        "public context is not the complete unchanged frozen projection",
    )
    _check(
        protocol["public_context_id"] == context["id"]
        and protocol["task_id"] == context["task"]["id"]
        and protocol["model_configuration_id"] == config["id"]
        and protocol["bounds"] == {"actions": 3, "updates": 3, "submissions": 12}
        and protocol["host_route_or_node_plan_input"] is False
        and protocol["automatic_observation_acceptance"] is False
        and protocol["host_fills_missing_proposed_claim"] is False
        and protocol["private_reasoning_requested_or_stored"] is False
        and protocol["provider_adapter_implemented"] is True
        and protocol["provider_attempt_limits"] == {"per_session": 12, "pilot": 72}
        and protocol["class_mapping_or_new_quotient_comparison"] is False,
        "evidence.protocol_condition",
        "protocol, task, configuration or ownership condition differs",
    )
    _check(
        legacy["numeric"]
        == {
            "precision": 50,
            "rounding": "ROUND_HALF_EVEN",
            "final_quantum": "0.000001",
            "source_reconciliation_tolerance": "0",
            "answer_tolerance": "0",
        }
        and config["attempts_per_session"] == 12
        and config["total_online_attempts"] == 72
        and config["online_sessions"] == 6
        and config["automatic_retries"] == config["model_fallbacks"] == 0
        and config["session_replacements"] == config["redirects"] == 0
        and config["maximum_public_response_bytes"] == 32_768
        and config["raw_private_reasoning_persisted"] is False
        and config["raw_private_reasoning_hashed"] is False,
        "evidence.numeric_and_attempt_contract",
        "frozen numeric, response or attempt budget differs",
    )
    origin = registration["generator_origin"]
    _check(
        origin in {"model", "adapter_mock"}
        and binding["origin"] == origin
        and binding["model_configuration_id"] == config["id"]
        and registration["protocol_id"] == protocol["id"]
        and registration["model_configuration_id"] == config["id"],
        "evidence.session_registration",
        "session does not bind this origin/configuration/protocol",
    )
    if origin == "model":
        _check(
            registration["neutral_prompt"] is True
            and registration["reference_route"] is None
            and registration["independent_initial_state"] is True
            and registration["reads_other_session_responses"] is False
            and registration["maximum_provider_attempts"] == 12
            and registration["replacement_allowed"] is False,
            "evidence.session_condition",
            "model session was replaced, directed or cross-conditioned",
        )
    for callback in (binding["adapter_callback"], binding["transport_binding"]):
        _check(
            isinstance(callback, Mapping), "evidence.adapter_binding", "missing registered callback"
        )
    _check(
        config["maximum_request_reserved_tokens"]
        == config["maximum_input_tokens"] + config["max_tokens"]
        and config["maximum_session_reserved_tokens"]
        == 12 * config["maximum_request_reserved_tokens"]
        and config["maximum_pilot_reserved_tokens"] == 6 * config["maximum_session_reserved_tokens"]
        and config["allowed_response_models"] == ["deepseek-v4-pro", "deepseek-v4-pro-0813"],
        "evidence.resource_and_model_condition",
        "frozen model aliases or reservation caps differ",
    )
    for role in ("freight", "other", "total"):
        _number(source["evidence"][role]["value"])
    _check(
        _number(source["evidence"]["total"]["value"]) != 0,
        "evidence.frozen_context",
        "frozen total must be a finite nonzero scalar",
    )
    return origin


def _state(
    context: Mapping[str, Any], protocol: Mapping[str, Any], dynamic: Mapping[str, Any]
) -> dict[str, Any]:
    remaining = {
        name: protocol["bounds"][name] - dynamic[counter] for name, counter in COUNTERS.items()
    }
    _check(
        all(type(value) is int and value >= 0 for value in remaining.values()),
        "independent.budget",
        "state exceeded the frozen bounds",
    )
    return _record(
        "public_state",
        context_id=context["id"],
        protocol_id=protocol["id"],
        **{key: context[key] for key in VIEW_FIELDS},
        **dynamic,
        remaining_bounds=remaining,
    )


def _request(state: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    _check(
        state["phase"] != "terminal" and state["remaining_bounds"]["submissions"] > 0,
        "independent.request_phase",
        "generator called after terminal or exhausted state",
    )
    if state["phase"] == "update":
        _check(
            state["remaining_bounds"]["updates"] > 0,
            "independent.request_phase",
            "update budget exhausted",
        )
        allowed = ["update"]
    else:
        allowed = ["action", "final"] if state["remaining_bounds"]["actions"] > 0 else ["final"]
    return _record(
        "generator_request",
        state_id=state["id"],
        state=state,
        allowed_submission_kinds=allowed,
        response_schema={kind: protocol["submission_schemas"][kind] for kind in allowed},
        instructions=INSTRUCTIONS,
        stable_public_json_only=True,
    )


def _resolved(
    parsed: Mapping[str, Any], state: Mapping[str, Any], source: Mapping[str, Any]
) -> list[dict[str, Any]]:
    evidence = {item["id"]: item for item in source["evidence"].values()}
    claims = {claim["id"]: claim for claim in state["accepted_claims"]}
    result = []
    for operand in parsed["inputs"]:
        if operand["kind"] == "evidence":
            _require(operand["ref_id"] in evidence, "admission.visible_evidence")
            item = evidence[operand["ref_id"]]
            if item["kind"] == "part_whole":
                result.append({**operand, "relation": item, "lineage": [item["id"]]})
            else:
                result.append(
                    {
                        **operand,
                        **{
                            key: item[key]
                            for key in ("value", "metric", "definition", *CONTEXT_FIELDS)
                        },
                        "lineage": [item["id"]],
                        "producer_operation": None,
                    }
                )
        else:
            _require(
                operand["ref_id"] in claims and claims[operand["ref_id"]]["status"] == "accepted",
                "admission.accepted_claim",
            )
            claim = claims[operand["ref_id"]]
            result.append(
                {
                    **operand,
                    **claim["proposition"],
                    "producer_operation": claim["producer_operation"],
                }
            )
    return result


def _admit_operation(
    parsed: Mapping[str, Any],
    inputs: list[dict[str, Any]],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
) -> None:
    operation = parsed["operation"]
    op = legacy["operations"][operation]
    _require(parsed["parameters"] == op["parameters"], "admission.parameters")
    _require([item["role"] for item in inputs] == op["input_roles"], "admission.roles")
    evidence = source["evidence"]
    common = {key: evidence["freight"][key] for key in CONTEXT_FIELDS}
    for item in inputs:
        if item["role"] != "relation":
            _number(item["value"])
            fields = (
                CONTEXT_FIELDS
                if operation != "scale_percent"
                else ("subject", "scope", "period", "currency")
            )
            for key in fields:
                _require(item[key] == common[key], "admission." + key)
    if operation == "relation_sum":
        relation = evidence["part_whole"]
        _require(
            Counter(item["ref_id"] for item in inputs[:2]) == Counter(relation["member_ids"])
            and len({item["ref_id"] for item in inputs[:2]}) == 2,
            "admission.complete_members",
        )
        _require(
            inputs[2]["ref_id"] == relation["id"]
            and inputs[2]["relation"] == relation
            and relation["exhaustive"]
            and relation["nonoverlapping"],
            "admission.source_relation",
        )
        originals = {item["id"]: item for item in (evidence["freight"], evidence["other"])}
        for item in inputs[:2]:
            original = originals[item["ref_id"]]
            _require(
                item["kind"] == "evidence"
                and all(
                    item[k] == original[k]
                    for k in ("value", "metric", "definition", *CONTEXT_FIELDS)
                ),
                "admission.raw_component",
            )
    elif operation == "share_ratio":
        numerator, denominator = inputs
        _require(
            numerator["kind"] == "evidence"
            and numerator["ref_id"] == evidence["freight"]["id"]
            and numerator["metric"] == evidence["freight"]["metric"]
            and denominator["metric"] == evidence["total"]["metric"],
            "admission.ratio_metrics",
        )
        _require(_number(denominator["value"]) != 0, "admission.denominator")
        if denominator["kind"] == "evidence":
            _require(denominator["ref_id"] == evidence["total"]["id"], "admission.total")
        else:
            _require(
                denominator["producer_operation"] == "relation_sum"
                and denominator["lineage"]
                == sorted(evidence[k]["id"] for k in ("freight", "other", "part_whole")),
                "admission.derived_total",
            )
    else:
        _require(
            inputs[0]["kind"] == "claim"
            and inputs[0]["metric"] == "freight_share_ratio"
            and inputs[0]["unit"] == "ratio",
            "admission.percent",
        )


def _admission(
    parsed: Mapping[str, Any],
    state: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
) -> dict[str, Any]:
    _require(parsed["state_id"] == state["id"], "admission.current_state")
    _require(state["phase"] != "terminal", "admission.terminal")
    _require(
        state["submission_count"] < protocol["bounds"]["submissions"], "admission.submission_budget"
    )
    kind, basis = parsed["kind"], parsed["public_basis"]
    if kind == "action":
        _require(
            state["phase"] == "action" and state["pending_observation"] is None,
            "admission.pending_update",
        )
        _require(state["action_count"] < protocol["bounds"]["actions"], "admission.action_budget")
        inputs = _resolved(parsed, state, source)
        _admit_operation(parsed, inputs, source, legacy)
        _require(
            _same_ids(basis["evidence_refs"], [ref for item in inputs for ref in item["lineage"]])
            and _same_ids(
                basis["claim_refs"], [item["ref_id"] for item in inputs if item["kind"] == "claim"]
            )
            and basis["intended_metric"]
            == legacy["operations"][parsed["operation"]]["output_metric"],
            "admission.public_basis",
        )
        return {"inputs": inputs}
    if kind == "update":
        _require(
            state["phase"] == "update" and state["pending_observation"] is not None,
            "admission.no_pending_observation",
        )
        _require(state["update_count"] < protocol["bounds"]["updates"], "admission.update_budget")
        observation = state["pending_observation"]
        _require(
            parsed["observation_id"] == observation["id"]
            and basis["observation_refs"] == [observation["id"]],
            "admission.observation_parent",
        )
        _require(
            _same_ids(basis["evidence_refs"], observation["output"]["lineage"]),
            "admission.update_basis",
        )
        if parsed["disposition"] == "accept":
            _require(
                basis["relation"] == "supports" and parsed["proposed_claim"] is not None,
                "admission.explicit_proposed_claim",
            )
            _require(
                parsed["proposed_claim"] == observation["output"],
                "admission.observed_claim_content",
            )
        else:
            _require(
                basis["relation"] == "declines" and parsed["proposed_claim"] is None,
                "admission.reject_creates_no_claim",
            )
        return {"observation": observation}
    _require(
        state["phase"] == "action" and state["pending_observation"] is None, "admission.final_phase"
    )
    claims = {item["id"]: item for item in state["accepted_claims"]}
    _require(parsed["answer_claim_id"] in claims, "admission.final_accepted_claim")
    claim = claims[parsed["answer_claim_id"]]
    _require(
        claim["status"] == "accepted"
        and claim["producer_operation"] == "scale_percent"
        and claim["proposition"]["metric"] == "freight_share_percent"
        and claim["proposition"]["unit"] == "percent",
        "admission.final_percent_claim",
    )
    answer = str(
        _number(claim["proposition"]["value"]).quantize(Decimal(legacy["numeric"]["final_quantum"]))
    )
    _require(
        parsed["answer"] == {"value": answer, "unit": "percent"}
        and _same_ids(parsed["citations"], claim["grounding"])
        and basis["claim_refs"] == [claim["id"]]
        and _same_ids(basis["evidence_refs"], claim["grounding"]),
        "admission.final_grounding",
    )
    return {"answer_claim": claim}


def _output(
    parsed: Mapping[str, Any],
    inputs: list[dict[str, Any]],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
) -> dict[str, Any]:
    operation = parsed["operation"]
    if operation == "relation_sum":
        value = sum((_number(item["value"]) for item in inputs[:2]), Decimal(0))
        definition = source["evidence"]["total"]["definition"]
    elif operation == "share_ratio":
        value = _number(inputs[0]["value"]) / _number(inputs[1]["value"])
        definition = "freight divided by legitimate operating revenue total"
    else:
        value = _number(inputs[0]["value"]) * Decimal(100)
        definition = "freight share in percent"
    op = legacy["operations"][operation]
    return {
        **{key: source["evidence"]["freight"][key] for key in CONTEXT_FIELDS},
        "value": str(value),
        "metric": op["output_metric"],
        "unit": op["output_unit"],
        "definition": definition,
        "lineage": sorted({ref for item in inputs for ref in item["lineage"]}),
    }


RECORD_FIELDS["generator_turn"] |= {"session_id", "provider_attempt_id", "provider_response_id"}
BUNDLE_FIELDS |= {"call_declaration", "provider_request", "provider_attempt", "provider_response"}


SYSTEM_MESSAGE = (
    "Follow the public protocol in the user message. The user message is the complete current "
    "public request, including its State, instructions and exact allowed response_schema. "
    "Return exactly one JSON object matching one allowed submission schema. Make all semantic "
    "choices yourself from the public information. Do not output Markdown or private reasoning."
)
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "reasoning_tokens",
)
PROVIDER_RESPONSE_FIELDS = {
    "request_id",
    "attempt_id",
    "session_id",
    "turn_index",
    "call_id",
    "public_request_id",
    "state_id",
    "phase",
    "model_configuration_id",
    "transport_binding_id",
    "generator_origin",
    "status",
    "code",
    "http_status",
    "received_model",
    "response_id",
    "system_fingerprint",
    "finish_reason",
    "usage",
    "public_content_sha256",
    "public_content_bytes",
    "parser_status",
    "parser_code",
    "evidence_level",
}
PUBLIC_PARSE_FAILURES = {
    "schema.payload_bytes",
    "schema.object_required",
    "schema.kind",
    "schema.duplicate_key",
    "schema.public_submission",
}
TRANSPORT_FAILURES = {
    "transport.invalid_credential",
    "transport.process_start",
    "transport.timeout",
    "transport.process_io",
    "transport.http_response_byte_cap",
    "transport.curl_failure",
    "transport.http_status_unavailable",
    "transport.unclassified_failure",
    "transport.invalid_result",
    "transport.http_error",
    "provider.insufficient_system_resource",
}
ENVELOPE_FAILURES = {
    "provider.invalid_body_type",
    "provider.invalid_json_envelope",
    "provider.invalid_envelope",
    "provider.model_identity_mismatch",
    "provider.actual_token_cap",
    "provider.invalid_choices",
    "provider.invalid_message",
    "provider.native_tool_call_forbidden",
    "provider.public_content_unavailable",
    "provider.public_content_encoding",
    "provider.response_identity",
    "provider.usage_inconsistent",
    "provider.choice_index",
    "provider.finish_reason",
}


def _registered_adapter(binding: Mapping[str, Any], origin: str) -> None:
    callback, transport = binding["adapter_callback"], binding["transport_binding"]
    _identity(transport)
    callback_fields = {"module", "class_name", "method_name", "source_path", "source_sha256"}
    _check(
        set(callback) == callback_fields,
        "evidence.adapter_registration",
        "adapter callable source descriptor differs",
    )
    expected_module = "trusted_synthesis.experiments.qa_reasoning_share_model_pilot.adapter"
    expected_path = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "qa_reasoning_share_model_pilot/adapter.py"
    )
    _check(
        callback["module"] == transport["module"] == expected_module
        and callback["source_path"] == transport["source_path"] == expected_path
        and callback["source_sha256"] == transport["source_sha256"]
        and isinstance(callback["source_sha256"], str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", callback["source_sha256"]))
        and callback["class_name"] == "DeepSeekAdapter"
        and callback["method_name"] == "perform"
        and transport["class_name"] == ("CurlTransport" if origin == "model" else "MockTransport")
        and transport["method_name"] == "send"
        and transport["origin"] == transport["kind"] == origin
        and binding["origin"] == binding["kind"] == origin,
        "evidence.adapter_registration",
        "model/mock origin is not bound to the declared adapter and transport implementations",
    )
    _check(
        binding
        == _pilot_record(
            "adapter_binding",
            origin=origin,
            kind=origin,
            model_configuration_id=binding["model_configuration_id"],
            adapter_callback=callback,
            transport_binding=transport,
        ),
        "evidence.adapter_registration",
        "adapter binding contains unsupported origin fields",
    )


def _http_request(
    public: Mapping[str, Any],
    config: Mapping[str, Any],
    session_id: str,
    sequence: int,
    call_id: str,
) -> dict[str, Any]:
    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": canonical_json_bytes(public).decode("utf-8")},
        ],
        **{
            key: copy.deepcopy(config[key])
            for key in (
                "thinking",
                "temperature",
                "top_p",
                "max_tokens",
                "response_format",
                "stream",
            )
        },
    }
    raw = canonical_json_bytes(body)
    _check(
        len(raw) <= config["maximum_serialized_request_bytes"]
        and len(raw) + 1024 <= config["maximum_input_tokens"],
        "evidence.request_budget",
        "actual serialized request exceeds the frozen input limits",
    )
    return _pilot_record(
        "provider_request",
        session_id=session_id,
        turn_index=sequence,
        call_id=call_id,
        model_configuration_id=config["id"],
        public_request_id=public["id"],
        state_id=public["state_id"],
        phase=public["state"]["phase"],
        endpoint=config["endpoint"],
        requested_model=config["model"],
        body_json=raw.decode("utf-8"),
        body_sha256=_sha(raw),
        body_byte_count=len(raw),
        input_token_upper_bound=len(raw) + 1024,
        reserved_tokens=config["maximum_request_reserved_tokens"],
    )


def _response_evidence(
    response: Mapping[str, Any],
    request: Mapping[str, Any],
    attempt: Mapping[str, Any],
    binding: Mapping[str, Any],
    config: Mapping[str, Any],
    origin: str,
) -> bool:
    _identity(response)
    _check(
        set(response) == PROVIDER_RESPONSE_FIELDS | {"id", "schema_version"},
        "evidence.response_schema",
        "response receipt omits or adds unreviewed fields",
    )
    expected_parents = {
        "request_id": request["id"],
        "attempt_id": attempt["id"],
        **{
            key: request[key]
            for key in (
                "session_id",
                "turn_index",
                "call_id",
                "public_request_id",
                "state_id",
                "phase",
                "model_configuration_id",
            )
        },
        "transport_binding_id": binding["transport_binding"]["id"],
        "generator_origin": origin,
    }
    _check(
        all(response[key] == value for key, value in expected_parents.items()),
        "evidence.provider_response_binding",
        "response is not bound to this actual attempt/request/State",
    )
    _check(
        response["schema_version"] == "share_model_pilot_provider_response.v1",
        "evidence.response_schema",
        "response has the wrong record type",
    )
    for key in ("received_model", "response_id", "system_fingerprint", "finish_reason"):
        value = response[key]
        _check(
            value is None
            or (
                isinstance(value, str)
                and len(value) <= 512
                and not any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
            ),
            "evidence.provider_metadata",
            "provider metadata is not a bounded disclosed value",
        )
    usage = response["usage"]
    _check(
        set(usage) == set(USAGE_KEYS)
        and all(value is None or (type(value) is int and value >= 0) for value in usage.values()),
        "evidence.provider_usage",
        "missing usage must remain null, not fabricated numeric data",
    )
    over_budget = any(
        usage[key] is not None and usage[key] > config[cap]
        for key, cap in (
            ("prompt_tokens", "maximum_input_tokens"),
            ("completion_tokens", "max_tokens"),
            ("total_tokens", "maximum_request_reserved_tokens"),
        )
    )
    status, code = response["status"], response["code"]
    http_status = response["http_status"]
    _check(
        http_status is None or (type(http_status) is int and 100 <= http_status <= 599),
        "evidence.http_status",
        "invalid bounded HTTP status metadata",
    )
    has_public = response["public_content_bytes"] is not None
    if has_public:
        _check(
            status == "received"
            and code is None
            and type(response["public_content_bytes"]) is int
            and response["public_content_bytes"] >= 0
            and isinstance(response["public_content_sha256"], str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", response["public_content_sha256"]))
            and response["received_model"] in config["allowed_response_models"]
            and bool(response["response_id"])
            and response["finish_reason"] in {"stop", "length", "content_filter"}
            and (
                any(
                    usage[key] is None
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                )
                or usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
            )
            and http_status is not None
            and 200 <= http_status <= 299
            and not over_budget,
            "evidence.public_response",
            "public response or actual model/token condition is inconsistent",
        )
        if response["parser_status"] == "valid":
            _check(
                response["parser_code"] == "schema.valid"
                and response["evidence_level"] == "public_submission_replayable",
                "evidence.receiver_diagnostic",
                "valid public response lacks replayable evidence status",
            )
        else:
            _check(
                response["parser_status"] == "invalid"
                and response["parser_code"] in PUBLIC_PARSE_FAILURES
                and response["evidence_level"] == "receiver_diagnosis_only",
                "evidence.receiver_diagnostic",
                "hash-only malformed response lacks typed receiver evidence",
            )
    else:
        _check(
            response["public_content_sha256"] is None
            and response["parser_status"] == "not_available"
            and response["parser_code"] is None,
            "evidence.no_public_content",
            "transport/envelope failure invents a public response",
        )
        _check(
            (
                status == "transport_failure"
                and code in TRANSPORT_FAILURES
                and response["evidence_level"] == "typed_transport_observation"
            )
            or (
                status == "envelope_failure"
                and code in ENVELOPE_FAILURES
                and response["evidence_level"] == "receiver_envelope_diagnosis_only"
            ),
            "evidence.receiver_failure",
            "missing content has no admissible typed failure observation",
        )
        if code == "provider.model_identity_mismatch":
            _check(
                response["received_model"] not in config["allowed_response_models"],
                "evidence.model_identity",
                "model mismatch code contradicts the actual model receipt",
            )
        if code == "provider.actual_token_cap":
            _check(
                over_budget and response["received_model"] in config["allowed_response_models"],
                "evidence.provider_usage",
                "resource-stop code has no observed token bound exceedance",
            )
    return has_public


def _evidence_chain(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
    binding: Mapping[str, Any],
    config: Mapping[str, Any],
    registration: Mapping[str, Any],
    records: Mapping[str, Any],
) -> dict[str, Any]:
    origin = _context(context, protocol, source, legacy, binding, config, registration)
    _registered_adapter(binding, origin)
    manifest, stop = records["manifest"], records["stop"]
    _identity(manifest)
    _identity(stop)
    initial, events = records["initial_state"], records["events"]
    _identity(initial, "public_state")
    _check(
        manifest["protocol_id"] == protocol["id"]
        and manifest["public_context_id"] == context["id"]
        and manifest["generator_binding_id"] == binding["id"]
        and manifest["session_id"] == registration["id"]
        and manifest["model_configuration_id"] == config["id"]
        and manifest["origin"] == origin
        and 0 < len(events) <= config["attempts_per_session"],
        "evidence.session_manifest",
        "session registration or bounded actual event domain differs",
    )
    state = initial
    submissions = 0
    seen_response_ids: list[str] = []
    for sequence, event in enumerate(events):
        _check(
            set(event) == BUNDLE_FIELDS,
            "evidence.event_schema",
            "event omits a required provider/core object",
        )
        for kind in ("event", "request", "generator_turn"):
            _identity(event[kind], "generator_request" if kind == "request" else kind)
        for kind in ("submission", "receipt", "execution", "observation", "claim", "final"):
            if event[kind] is not None:
                _identity(event[kind], kind)
        _identity(event["post_state"], "public_state")
        public, turn = event["request"], event["generator_turn"]
        _check(
            public["state_id"] == state["id"]
            and public["state"] == state
            and event["event"]["pre_state_id"] == state["id"],
            "evidence.current_state",
            "actual Provider request does not use the preceding actual State",
        )
        call = _pilot_record(
            "call_declaration",
            session_id=registration["id"],
            turn_index=sequence,
            public_request_id=public["id"],
            state_id=state["id"],
            adapter_binding_id=binding["id"],
        )
        _check(
            event["call_declaration"] == call,
            "evidence.call_declaration",
            "call/session/State parent differs",
        )
        request = _http_request(public, config, registration["id"], sequence, call["id"])
        _check(
            event["provider_request"] == request,
            "evidence.actual_provider_request",
            (
                "actual serialized request contains changed schema, history, "
                "route conditioning or configuration"
            ),
        )
        request_bytes = canonical_json_bytes(request)
        attempt = _pilot_record(
            "provider_attempt",
            session_id=registration["id"],
            ordinal=sequence + 1,
            turn_index=sequence,
            call_id=call["id"],
            request_id=request["id"],
            public_request_id=public["id"],
            state_id=state["id"],
            phase=state["phase"],
            adapter_binding_id=binding["id"],
            model_configuration_id=config["id"],
            origin=origin,
            provider_attempts_consumed=1 if origin == "model" else 0,
            mock_attempts_consumed=1 if origin == "adapter_mock" else 0,
            reserved_token_allowance=config["maximum_request_reserved_tokens"],
            cumulative_reserved_tokens=(sequence + 1) * config["maximum_request_reserved_tokens"],
            request_artifact_sha256=_sha(request_bytes),
            request_artifact_bytes=len(request_bytes),
            counted_before_send=True,
            automatic_retries=0,
        )
        _check(
            event["provider_attempt"] == attempt
            and attempt["cumulative_reserved_tokens"] <= config["maximum_session_reserved_tokens"],
            "evidence.attempt_reservation",
            "attempt was not uniquely reserved before the actual send",
        )
        response = event["provider_response"]
        has_public = _response_evidence(response, request, attempt, binding, config, origin)
        seen_response_ids.append(response["id"])
        expected_turn = _record(
            "generator_turn",
            request_id=public["id"],
            state_id=state["id"],
            generator_binding_id=binding["id"],
            origin=origin,
            response_sha256=response["public_content_sha256"] if has_public else None,
            response_byte_count=response["public_content_bytes"] if has_public else 0,
            callback_error=None if has_public else response["code"],
            provider_calls=1 if origin == "model" else 0,
            host_supplied_response=False,
            session_id=registration["id"],
            provider_attempt_id=attempt["id"],
            provider_response_id=response["id"],
        )
        _check(
            turn == expected_turn,
            "evidence.generator_turn",
            "model/mock source or request/attempt/response association differs",
        )
        submission, receipt = event["submission"], event["receipt"]
        if not has_public:
            _check(
                submission is None
                and receipt is None
                and all(
                    event[kind] is None for kind in ("execution", "observation", "claim", "final")
                ),
                "evidence.no_synthetic_submission",
                "transport failure was replaced by a public submission or fallback",
            )
        else:
            _check(
                submission is not None and receipt is not None,
                "evidence.missing_submission",
                "public response is detached from its actual submission/receipt",
            )
            submissions += 1
            _check(
                submission["generator_turn_id"] == turn["id"]
                and submission["request_id"] == public["id"]
                and submission["state_id"] == state["id"]
                and submission["response_sha256"] == response["public_content_sha256"]
                and submission["response_byte_count"] == response["public_content_bytes"]
                and submission["field_origin"] == origin,
                "evidence.submission_binding",
                "actual public bytes are not associated with this model response",
            )
            if response["parser_status"] == "valid":
                raw = submission["raw_public_json"]
                _check(
                    isinstance(raw, str)
                    and submission["parsed"] is not None
                    and _sha(raw.encode("utf-8")) == response["public_content_sha256"]
                    and len(raw.encode("utf-8")) == response["public_content_bytes"],
                    "evidence.public_bytes",
                    "valid public JSON bytes are missing or do not match the response",
                )
            else:
                _check(
                    submission["raw_public_json"] is None and submission["parsed"] is None,
                    "evidence.malformed_policy",
                    "malformed response was repaired or persisted as arbitrary raw text",
                )
            _check(
                receipt["submission_id"] == submission["id"]
                and receipt["request_id"] == public["id"]
                and receipt["pre_state_id"] == state["id"]
                and receipt["submission_sha256"] == _sha(canonical_json_bytes(submission))
                and receipt["submission_byte_count"] == len(canonical_json_bytes(submission)),
                "evidence.submission_receipt",
                "receipt is not bound to the actual submitted object bytes",
            )
        parents = {
            "sequence": sequence,
            "pre_state_id": state["id"],
            "post_state_id": event["post_state"]["id"],
            **{
                kind + "_id": event[kind]["id"] if event[kind] is not None else None
                for kind in (
                    "request",
                    "generator_turn",
                    "submission",
                    "receipt",
                    "execution",
                    "observation",
                    "claim",
                    "final",
                )
            },
        }
        _check(
            event["event"] == _record("event", **parents),
            "evidence.event_parents",
            "event identity does not retain the actual provider/core producer chain",
        )
        state = event["post_state"]
    _check(
        len(seen_response_ids) == len(set(seen_response_ids)),
        "evidence.response_reuse",
        "one provider-response record was reused across different attempts",
    )
    expected_stop = _pilot_record(
        "session_stop",
        session_id=registration["id"],
        state_id=state["id"],
        terminal=state["terminal"],
        terminal_recorded=state["phase"] == "terminal",
        callback_attempts=len(events),
        provider_attempts=len(events) if origin == "model" else 0,
        public_submission_attempts=submissions,
        completed_events=len(events),
        automatic_retries=0,
        session_replacements=0,
    )
    _check(
        stop == expected_stop
        and stop["terminal_recorded"] is True
        and isinstance(stop["terminal"], str)
        and bool(stop["terminal"]),
        "evidence.terminal_stop",
        "session lacks a complete, actual terminal outcome",
    )
    _check(
        manifest["generator_callbacks"] == len(events)
        and manifest["provider_attempts"] == (len(events) if origin == "model" else 0)
        and manifest["public_submission_attempts"] == submissions
        and manifest["kernel_calls"] == sum(event["execution"] is not None for event in events),
        "evidence.actual_counts",
        "attempt/submission/action accounting differs from actual objects",
    )
    return {
        "origin": origin,
        "provider_attempts": len(events) if origin == "model" else 0,
        "callback_attempts": len(events),
        "public_submission_attempts": submissions,
        "recorded_terminal": stop["terminal"],
        "final_state": state,
    }


def _replay_protocol(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
    config: Mapping[str, Any],
    origin: str,
    records: Mapping[str, Any],
) -> dict[str, Any]:
    dynamic: dict[str, Any] = {
        "phase": "action",
        "accepted_claims": [],
        "pending_observation": None,
        "action_count": 0,
        "update_count": 0,
        "submission_count": 0,
        "last_feedback": None,
        "terminal": None,
    }
    state = _state(context, protocol, dynamic)
    _check(
        records["initial_state"] == state,
        "protocol.initial_state",
        "session did not begin with the same independent public State",
    )
    final_result = None
    ownership = []
    for sequence, event in enumerate(records["events"]):
        request = _request(state, protocol)
        _check(
            event["request"] == request,
            "protocol.public_request",
            "public request added a plan, private answer, changed schema or noncurrent State",
        )
        before = state
        dynamic = copy.deepcopy({key: state[key] for key in DYNAMIC_FIELDS})
        turn, response = event["generator_turn"], event["provider_response"]
        submission, receipt = event["submission"], event["receipt"]
        execution = observation = claim = final = None
        if submission is None:
            code = response["code"] or "provider.public_content_unavailable"
            dynamic.update(
                phase="terminal",
                pending_observation=None,
                terminal=code,
                last_feedback={"code": code},
            )
        else:
            _check(
                submission["host_repairs"] == [],
                "protocol.no_repair",
                "Host filled or changed semantic fields in the model response",
            )
            parsed, admission = None, None
            if submission["raw_public_json"] is not None:
                try:
                    parsed = _parse_raw(submission["raw_public_json"])
                except SubmissionRejected as error:
                    raise IndependentError("protocol.public_grammar", str(error)) from error
                _check(
                    parsed == submission["parsed"],
                    "protocol.parsed_public_response",
                    "Host parsed/repaired fields differ from the actual response JSON",
                )
                try:
                    admission = _admission(parsed, before, protocol, source, legacy)
                    code = "admitted." + parsed["kind"]
                except SubmissionRejected as error:
                    code = str(error)
            else:
                # The unretained malformed text is not independently reparsed.
                code = response["parser_code"]
            expected_receipt = _record(
                "receipt",
                submission_id=submission["id"],
                request_id=request["id"],
                pre_state_id=before["id"],
                admitted=admission is not None,
                code=code,
                dispatch_permitted=admission is not None
                and parsed is not None
                and parsed["kind"] == "action",
                submission_sha256=_sha(canonical_json_bytes(submission)),
                submission_byte_count=len(canonical_json_bytes(submission)),
                no_replace=True,
                missing_fields_filled=False,
                response_rewritten=False,
            )
            _check(
                receipt == expected_receipt,
                "protocol.admission_receipt",
                "Host admission differs from the unchanged independent public semantics",
            )
            dynamic["submission_count"] += 1
            if admission is None:
                dynamic["last_feedback"] = {"code": code}
            elif parsed is not None and parsed["kind"] == "action":
                inputs = admission["inputs"]
                operation = parsed["operation"]
                output = _output(parsed, inputs, source, legacy)
                execution = _record(
                    "execution",
                    submission_id=submission["id"],
                    generator_turn_id=turn["id"],
                    operation=operation,
                    operation_contract_id=legacy["operations"][operation]["id"],
                    parameters=parsed["parameters"],
                    inputs=inputs,
                    output=output,
                    field_origin="host_derived",
                )
                observation = _record(
                    "observation",
                    execution_id=execution["id"],
                    action_submission_id=submission["id"],
                    operation=operation,
                    output=output,
                    success=True,
                    field_origin="host_derived",
                )
                dynamic.update(
                    phase="update",
                    pending_observation=observation,
                    action_count=dynamic["action_count"] + 1,
                    last_feedback={"code": "observation_ready"},
                )
                ownership.append(
                    {
                        "kind": "action",
                        "origin": origin,
                        "provider_attempt_id": turn["provider_attempt_id"],
                        "generator_turn_id": turn["id"],
                        "submission_id": submission["id"],
                        "operation": operation,
                        "inputs": parsed["inputs"],
                        "parameters": parsed["parameters"],
                        "public_basis": parsed["public_basis"],
                        "actual_observation_id": observation["id"],
                        "automatic_claim_created": False,
                    }
                )
            elif parsed is not None and parsed["kind"] == "update":
                pending = before["pending_observation"]
                if parsed["disposition"] == "accept":
                    claim = _record(
                        "claim",
                        task_id=context["task"]["id"],
                        observation_id=pending["id"],
                        update_submission_id=submission["id"],
                        generator_turn_id=turn["id"],
                        proposition=parsed["proposed_claim"],
                        grounding=parsed["proposed_claim"]["lineage"],
                        producer_operation=pending["operation"],
                        status="accepted",
                        field_origin=origin,
                    )
                    dynamic["accepted_claims"].append(claim)
                dynamic.update(
                    phase="action",
                    pending_observation=None,
                    update_count=dynamic["update_count"] + 1,
                    last_feedback={
                        "code": "claim_accepted" if claim is not None else "observation_rejected"
                    },
                )
                ownership.append(
                    {
                        "kind": "update",
                        "origin": origin,
                        "provider_attempt_id": turn["provider_attempt_id"],
                        "generator_turn_id": turn["id"],
                        "submission_id": submission["id"],
                        "disposition": parsed["disposition"],
                        "actual_observation_id": pending["id"],
                        "accepted_claim_id": claim["id"] if claim else None,
                        "complete_claim_supplied": parsed["proposed_claim"] is not None,
                        "host_filled_proposed_claim": False,
                    }
                )
            elif parsed is not None:
                final = _record(
                    "final",
                    task_id=context["task"]["id"],
                    submission_id=submission["id"],
                    generator_turn_id=turn["id"],
                    answer=parsed["answer"],
                    answer_claim_id=parsed["answer_claim_id"],
                    citations=parsed["citations"],
                    field_origin=origin,
                )
                final_result = final
                dynamic.update(
                    phase="terminal",
                    terminal="final_submitted",
                    last_feedback={"code": "final_submitted"},
                )
                ownership.append(
                    {
                        "kind": "final",
                        "origin": origin,
                        "provider_attempt_id": turn["provider_attempt_id"],
                        "generator_turn_id": turn["id"],
                        "submission_id": submission["id"],
                        "answer_claim_id": parsed["answer_claim_id"],
                        "citations": parsed["citations"],
                        "host_filled_answer": False,
                    }
                )
            if dynamic["phase"] != "terminal" and (
                dynamic["submission_count"] >= protocol["bounds"]["submissions"]
                or sequence + 1 >= config["attempts_per_session"]
            ):
                code = (
                    "submission_budget_exhausted"
                    if dynamic["submission_count"] >= protocol["bounds"]["submissions"]
                    else "provider_attempt_budget_exhausted"
                )
                dynamic.update(
                    phase="terminal",
                    terminal=code,
                    pending_observation=None,
                    last_feedback={"code": code},
                )
        for name, expected in (
            ("execution", execution),
            ("observation", observation),
            ("claim", claim),
            ("final", final),
        ):
            _check(
                event[name] == expected,
                "protocol.actual_" + name,
                f"actual {name} was injected, repaired or detached from the submitted model fields",
            )
        after = _state(context, protocol, dynamic)
        _check(
            event["post_state"] == after,
            "protocol.state_transition",
            "Host state changes do not follow the explicit Action/Observation/Update boundary",
        )
        state = after
    _check(state["phase"] == "terminal", "protocol.terminal", "protocol has no terminal state")
    return {
        "protocol_valid": True,
        "valid_final": final_result is not None,
        "final": final_result,
        "actual_final_state": state,
        "ownership_witnesses": ownership,
        "action_count": dynamic["action_count"],
        "update_count": dynamic["update_count"],
        "public_submission_count": dynamic["submission_count"],
        "accepted_claim_count": len(state["accepted_claims"]),
        "terminal_reason": state["terminal"],
    }


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _stage_measurements(events: list[dict[str, Any]]) -> dict[str, Any]:
    phases = {
        phase: {
            "attempts": 0,
            "public_responses": 0,
            "schema_valid": 0,
            "phase_allowed_kind": 0,
            "no_public_content": 0,
        }
        for phase in ("action", "update")
    }
    kinds = {
        kind: {"parsed_submissions": 0, "admitted": 0} for kind in ("action", "update", "final")
    }
    dispositions = {
        "accept_submitted": 0,
        "reject_submitted": 0,
        "accept_committed": 0,
        "reject_committed": 0,
    }
    complete_claim_checks = complete_claim_matches = 0
    first_failure = None
    hash_only = raw_replayed = 0
    actual_models: set[str] = set()
    for sequence, event in enumerate(events):
        phase = event["provider_request"]["phase"]
        phase_row = phases[phase]
        phase_row["attempts"] += 1
        response, receipt = event["provider_response"], event["receipt"]
        if response["received_model"] is not None:
            actual_models.add(response["received_model"])
        submission = event["submission"]
        parsed = None if submission is None else submission["parsed"]
        if response["public_content_bytes"] is None:
            phase_row["no_public_content"] += 1
        else:
            phase_row["public_responses"] += 1
            if response["parser_status"] == "valid":
                phase_row["schema_valid"] += 1
                raw_replayed += 1
                if (
                    parsed is not None
                    and parsed["kind"] in event["request"]["allowed_submission_kinds"]
                ):
                    phase_row["phase_allowed_kind"] += 1
            else:
                hash_only += 1
        failure_code = (
            response["code"]
            if submission is None
            else (receipt["code"] if not receipt["admitted"] else None)
        )
        if failure_code is not None and first_failure is None:
            first_failure = {
                "turn_index": sequence,
                "request_phase": phase,
                "code": failure_code,
                "evidence_level": response["evidence_level"],
            }
        if parsed is None:
            continue
        kind = parsed["kind"]
        kinds[kind]["parsed_submissions"] += 1
        kinds[kind]["admitted"] += int(receipt["admitted"])
        if kind == "update":
            disposition = parsed["disposition"]
            dispositions[disposition + "_submitted"] += 1
            dispositions[disposition + "_committed"] += int(receipt["admitted"])
            state = event["request"]["state"]
            pending = state["pending_observation"]
            basis = parsed["public_basis"]
            content_check_reached = (
                disposition == "accept"
                and state["phase"] == "update"
                and pending is not None
                and parsed["state_id"] == state["id"]
                and parsed["observation_id"] == pending["id"]
                and basis["observation_refs"] == [pending["id"]]
                and _same_ids(basis["evidence_refs"], pending["output"]["lineage"])
                and basis["relation"] == "supports"
                and parsed["proposed_claim"] is not None
            )
            if content_check_reached:
                complete_claim_checks += 1
                complete_claim_matches += int(parsed["proposed_claim"] == pending["output"])
    phase_metrics = {}
    for phase, values in phases.items():
        phase_metrics["action_or_final" if phase == "action" else "update"] = {
            **values,
            "reached": values["attempts"] > 0,
            "public_response_per_request": _ratio(values["public_responses"], values["attempts"]),
            "strict_schema_per_received_response": _ratio(
                values["schema_valid"], values["public_responses"]
            ),
            "strict_schema_per_request": _ratio(values["schema_valid"], values["attempts"]),
            "allowed_kind_per_received_response": _ratio(
                values["phase_allowed_kind"], values["public_responses"]
            ),
        }
    return {
        "phase_metrics": phase_metrics,
        "parsed_kind_admission": {
            kind: _ratio(values["admitted"], values["parsed_submissions"])
            for kind, values in kinds.items()
        },
        "update_dispositions": dispositions,
        "complete_proposed_claim_consistency": _ratio(
            complete_claim_matches, complete_claim_checks
        ),
        "first_observed_failure": first_failure,
        "raw_public_json_response_count": raw_replayed,
        "receiver_diagnosis_only_response_count": hash_only,
        "malformed_raw_grammar_independently_replayed": False,
        "actual_response_models": sorted(actual_models),
        "conditional_denominator_rule": (
            "actual requested phase or reached check; zero denominator is null"
        ),
        "schema_failure_diagnosis_authority": (
            "raw replay for valid public JSON; receiver diagnosis for unretained malformed text"
        ),
    }


def _support_description(
    events: list[dict[str, Any]], final: Mapping[str, Any] | None, source: Mapping[str, Any]
) -> dict[str, Any]:
    history = []
    declined = []
    claims = {
        event["claim"]["id"]: event["claim"] for event in events if event["claim"] is not None
    }
    observations = {
        event["observation"]["id"]: event for event in events if event["observation"] is not None
    }
    for event in events:
        execution = event["execution"]
        if execution is not None and execution["operation"] == "share_ratio":
            denominator = execution["inputs"][1]
            history.append(
                {
                    "execution_id": execution["id"],
                    "denominator_kind": denominator["kind"],
                    "denominator_ref_id": denominator["ref_id"],
                    "denominator_producer_operation": denominator["producer_operation"],
                    "actual_lineage": denominator["lineage"],
                }
            )
        submitted = None if event["submission"] is None else event["submission"]["parsed"]
        if (
            submitted is not None
            and submitted["kind"] == "update"
            and submitted["disposition"] == "reject"
            and event["receipt"]["admitted"]
        ):
            declined.append(submitted["observation_id"])
    result: dict[str, Any] = {
        "label": "unresolved",
        "final_denominator_ref_id": None,
        "actual_ratio_history": history,
        "declined_observation_ids": declined,
        "old_quotient_mapping": False,
        "new_W": None,
        "new_semantic_class_count": None,
        "classification_basis": (
            "actual Final -> accepted percent Claim -> ratio denominator producer"
        ),
    }
    if final is None:
        return result
    try:
        percent = claims[final["answer_claim_id"]]
        percent_execution = observations[percent["observation_id"]]["execution"]
        ratio = claims[percent_execution["inputs"][0]["ref_id"]]
        ratio_execution = observations[ratio["observation_id"]]["execution"]
        denominator = ratio_execution["inputs"][1]
        result["final_denominator_ref_id"] = denominator["ref_id"]
        if (
            denominator["kind"] == "evidence"
            and denominator["ref_id"] == source["evidence"]["total"]["id"]
        ):
            result["label"] = "disclosed_total"
        elif denominator["kind"] == "claim":
            total = claims[denominator["ref_id"]]
            producer = observations[total["observation_id"]]["execution"]
            members = producer["inputs"]
            if (
                producer["operation"] == "relation_sum"
                and Counter(item["ref_id"] for item in members[:2])
                == Counter(source["evidence"][role]["id"] for role in ("freight", "other"))
                and members[2]["ref_id"] == source["evidence"]["part_whole"]["id"]
            ):
                result["label"] = "reconstructed_total_claim"
            else:
                result["label"] = "other_or_mixed"
        else:
            result["label"] = "other_or_mixed"
    except (KeyError, TypeError, IndexError):
        result["label"] = "unresolved"
    return result


def read_session_records(session_root: str | Path) -> dict[str, Any]:
    requested = Path(session_root)
    _check(not requested.is_symlink(), "evidence.artifact_path", "session root is a symlink")
    root = requested.resolve()
    inventory = list(root.rglob("*"))
    _check(
        not any(path.is_symlink() for path in inventory),
        "evidence.artifact_path",
        "session contains symlinks",
    )
    raw = (root / "session_manifest.json").read_bytes()
    manifest = json.loads(raw)
    _identity(manifest)
    _check(
        raw == canonical_json_bytes(manifest),
        "evidence.canonical_bytes",
        "manifest is not canonical",
    )
    _check(
        set(manifest)
        == {
            "id",
            "schema_version",
            "protocol_id",
            "public_context_id",
            "generator_binding_id",
            "initial_state",
            "events",
            "members",
            "kernel_calls",
            "generator_callbacks",
            "write_events",
            "session_id",
            "model_configuration_id",
            "origin",
            "provider_attempts",
            "public_submission_attempts",
            "stop_record",
        },
        "evidence.manifest_schema",
        "session manifest has missing or unsupported fields",
    )
    _check(
        manifest["schema_version"] == "public_share_protocol_session_manifest.v1",
        "evidence.manifest_schema",
        "wrong session manifest record type",
    )
    objects = {}
    for member in manifest["members"]:
        _check(
            set(member) == {"relative_path", "sha256", "byte_count"},
            "evidence.manifest_schema",
            "member declaration differs",
        )
        relative = member["relative_path"]
        path = (root / relative).resolve()
        _check(
            not Path(relative).is_absolute()
            and ".." not in Path(relative).parts
            and path.is_relative_to(root)
            and relative not in objects
            and relative != "session_manifest.json",
            "evidence.artifact_path",
            "unsafe or duplicate session artifact",
        )
        raw = path.read_bytes()
        _check(
            _sha(raw) == member["sha256"] and len(raw) == member["byte_count"],
            "evidence.artifact_bytes",
            "actual session bytes differ from the manifest",
        )
        obj = json.loads(raw)
        _check(
            raw == canonical_json_bytes(obj),
            "evidence.canonical_bytes",
            "session object is not canonical",
        )
        objects[relative] = obj
    actual_files = {path.relative_to(root).as_posix() for path in inventory if path.is_file()}
    _check(
        actual_files == set(objects) | {"session_manifest.json"},
        "evidence.artifact_inventory",
        "manifest does not cover actual session files",
    )
    ordered = [manifest["initial_state"]]
    events = []
    required = {
        "request",
        "call_declaration",
        "provider_request",
        "provider_attempt",
        "provider_response",
        "generator_turn",
        "post_state",
        "event",
    }
    for paths in manifest["events"]:
        _check(
            required.issubset(paths) and set(paths).issubset(BUNDLE_FIELDS),
            "evidence.event_inventory",
            "an attempted call has incomplete associated event objects",
        )
        _check(
            ("submission" in paths) == ("receipt" in paths),
            "evidence.event_inventory",
            "submission and receipt are not paired",
        )
        events.append(
            {kind: objects[paths[kind]] if kind in paths else None for kind in BUNDLE_FIELDS}
        )
        ordered.extend(
            paths[kind]
            for kind in (
                "request",
                "call_declaration",
                "provider_request",
                "provider_attempt",
                "provider_response",
                "generator_turn",
                "submission",
                "receipt",
                "execution",
                "observation",
                "claim",
                "final",
                "post_state",
                "event",
            )
            if kind in paths
        )
    ordered.append(manifest["stop_record"])
    _check(
        len(ordered) == len(set(ordered)) and set(ordered) == set(objects),
        "evidence.attempt_event_totality",
        "orphan attempts, missing events or unaccounted stop objects",
    )
    expected_events: list[dict[str, Any]] = []
    for path in ordered:
        for kind in ("file_fsync", "directory_fsync"):
            expected_events.append(
                {"event_ordinal": len(expected_events) + 1, "kind": kind, "relative_path": path}
            )
    _check(
        manifest["write_events"] == expected_events,
        "evidence.pre_attempt_order",
        "request/reservation/response/submission/dispatch/stop persistence order differs",
    )
    return {
        "manifest": manifest,
        "initial_state": objects[manifest["initial_state"]],
        "events": events,
        "stop": objects[manifest["stop_record"]],
    }


def audit_records(
    *,
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy_contract: Mapping[str, Any],
    adapter_binding: Mapping[str, Any],
    model_config: Mapping[str, Any],
    session_registration: Mapping[str, Any],
    records: Mapping[str, Any],
) -> dict[str, Any]:
    """Separate closed evidence, correct Host protocol processing and actual QA success."""
    report: dict[str, Any] = {
        "session_id": session_registration.get("id"),
        "session_label": session_registration.get("label"),
        "origin": session_registration.get("generator_origin"),
        "model_configuration_id": model_config.get("id"),
        "protocol_id": protocol.get("id"),
        "adapter_binding_id": adapter_binding.get("id"),
        "evidence_complete": False,
        "protocol_valid": None,
        "qa_valid": None,
        "valid_final": None,
        "qualified": None,
        "Y": None,
        "mock_control_success": None,
        "provider_attempts": None,
        "callback_attempts": None,
        "public_submission_attempts": None,
        "first_evidence_failure": None,
        "first_protocol_failure": None,
        "terminal_reason": None,
        "support_description": {"label": "unresolved"},
        "new_W_share": None,
        "new_semantic_class_count": None,
        "old_quotient_mapping": False,
        "candidate_runtime_executions": 0,
        "provider_calls_by_this_audit": 0,
        "independent_imports_host_parser_admission_adapter_or_runtime": False,
        "private_reasoning_examined": False,
        "raw_envelope_replayed": False,
    }
    with localcontext() as numeric_context:
        numeric_context.prec = 50
        numeric_context.rounding = ROUND_HALF_EVEN
        try:
            evidence = _evidence_chain(
                context,
                protocol,
                source,
                legacy_contract,
                adapter_binding,
                model_config,
                session_registration,
                records,
            )
            report.update(_stage_measurements(records["events"]))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            ArithmeticError,
            RecursionError,
        ) as error:
            report["first_evidence_failure"] = {
                "stage": getattr(error, "stage", "evidence.missing_or_invalid_object"),
                "reason": str(error),
            }
            return _pilot_record("session_audit", **report)
        report.update(
            evidence_complete=True,
            provider_attempts=evidence["provider_attempts"],
            callback_attempts=evidence["callback_attempts"],
            public_submission_attempts=evidence["public_submission_attempts"],
            terminal_reason=evidence["recorded_terminal"],
            session_manifest_id=records["manifest"]["id"],
            session_stop_id=records["stop"]["id"],
        )
        try:
            replay = _replay_protocol(
                context,
                protocol,
                source,
                legacy_contract,
                model_config,
                evidence["origin"],
                records,
            )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            ArithmeticError,
            RecursionError,
        ) as error:
            report["protocol_valid"] = False
            report["valid_final"] = False
            report["first_protocol_failure"] = {
                "stage": getattr(error, "stage", "protocol.missing_or_invalid_semantics"),
                "reason": str(error),
            }
            final = next(
                (
                    event["final"]
                    for event in reversed(records["events"])
                    if event["final"] is not None
                ),
                None,
            )
        else:
            report.update(
                {
                    key: value
                    for key, value in replay.items()
                    if key not in {"final", "actual_final_state"}
                }
            )
            final = replay["final"]
            report["support_description"] = _support_description(records["events"], final, source)
        if final is None:
            report["qa_valid"] = None
            report["answer_oracle"] = None
        else:
            expected = (
                _number(source["evidence"]["freight"]["value"])
                / _number(source["evidence"]["total"]["value"])
                * Decimal(100)
            ).quantize(Decimal(legacy_contract["numeric"]["final_quantum"]))
            report["qa_valid"] = final["answer"] == {"value": str(expected), "unit": "percent"}
            report["answer_oracle"] = {
                "expected_answer": str(expected),
                "actual_answer": final["answer"],
                "formula": "100 * disclosed freight / disclosed total",
                "independent_offline_check_only": True,
                "injected_into_request_or_action": False,
            }
        success = (
            report["valid_final"] is True
            and report["protocol_valid"] is True
            and report["qa_valid"] is True
        )
        report["qualified"] = success
        report["Y"] = int(success) if evidence["origin"] == "model" else None
        report["mock_control_success"] = success if evidence["origin"] == "adapter_mock" else None
        report["outcome"] = "complete_success" if success else "complete_observed_failure"
    return _pilot_record("session_audit", **report)


def audit_session(
    *,
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy_contract: Mapping[str, Any],
    adapter_binding: Mapping[str, Any],
    model_config: Mapping[str, Any],
    session_registration: Mapping[str, Any],
    session_root: str | Path,
) -> dict[str, Any]:
    try:
        records = read_session_records(session_root)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        ArithmeticError,
        RecursionError,
    ) as error:
        return _pilot_record(
            "session_audit",
            session_id=session_registration.get("id"),
            session_label=session_registration.get("label"),
            origin=session_registration.get("generator_origin"),
            model_configuration_id=model_config.get("id"),
            protocol_id=protocol.get("id"),
            adapter_binding_id=adapter_binding.get("id"),
            evidence_complete=False,
            protocol_valid=None,
            qa_valid=None,
            valid_final=None,
            qualified=None,
            Y=None,
            mock_control_success=None,
            provider_attempts=None,
            callback_attempts=None,
            public_submission_attempts=None,
            persisted_artifact_validation=False,
            first_evidence_failure={
                "stage": getattr(error, "stage", "evidence.missing_artifact"),
                "reason": str(error),
            },
            first_protocol_failure=None,
            terminal_reason=None,
            support_description={"label": "unresolved"},
            new_W_share=None,
            new_semantic_class_count=None,
            old_quotient_mapping=False,
            candidate_runtime_executions=0,
            provider_calls_by_this_audit=0,
        )
    report = audit_records(
        context=context,
        protocol=protocol,
        source=source,
        legacy_contract=legacy_contract,
        adapter_binding=adapter_binding,
        model_config=model_config,
        session_registration=session_registration,
        records=records,
    )
    fields = {key: value for key, value in report.items() if key not in {"id", "schema_version"}}
    return _pilot_record("session_audit", **fields, persisted_artifact_validation=True)


def aggregate_pilot(
    pilot_registration: Mapping[str, Any],
    session_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Use the six predeclared model sessions; missing evidence never becomes Y=0."""
    result: dict[str, Any] = {
        "evidence_complete_count": 0,
        "registered_denominator": 6,
        "success_count": None,
        "known_success_count": 0,
        "q_public_protocol": None,
        "exact_fraction": None,
        "provider_attempts": None,
        "known_provider_attempts": 0,
        "missing_or_unknown_sessions": [],
        "workflow_complete": False,
        "errors": [],
        "Y_by_session": [],
        "support_descriptions": {},
        "mock_sessions_in_denominator": 0,
        "mechanism_defect_session_ids": [],
        "model_attribution_allowed": False,
        "new_W_share": None,
        "new_semantic_class_count": None,
        "old_quotient_mapping": False,
        "scientific_scope": (
            "fixed single task and requested configuration; six-session engineering proportion"
        ),
    }
    try:
        _identity(pilot_registration)
        _check(
            pilot_registration["schema_version"] == "share_model_pilot_pilot_registration.v1",
            "measurement.registration",
            "wrong pilot registration record type",
        )
        ids, declarations = pilot_registration["session_ids"], pilot_registration["sessions"]
        _check(
            len(ids) == len(set(ids)) == len(declarations) == 6
            and ids == [declaration["id"] for declaration in declarations]
            and pilot_registration["fixed_online_denominator"] == 6
            and pilot_registration["maximum_online_provider_attempts"] == 72
            and pilot_registration["before_first_online_attempt"] is True
            and pilot_registration["never_replace_or_add_sessions"] is True,
            "measurement.registration",
            "the fixed six-session domain or before-online registration differs",
        )
        for index, declaration in enumerate(declarations):
            _identity(declaration)
            _check(
                declaration["ordinal"] == index
                and declaration["generator_origin"] == "model"
                and declaration["neutral_prompt"] is True
                and declaration["reference_route"] is None
                and declaration["independent_initial_state"] is True
                and declaration["reads_other_session_responses"] is False
                and declaration["replacement_allowed"] is False
                and declaration["maximum_provider_attempts"] == 12
                and declaration["protocol_id"] == pilot_registration["protocol_id"]
                and declaration["model_configuration_id"]
                == pilot_registration["model_configuration_id"],
                "measurement.session_domain",
                "a declared model session is directed, replaced or differently configured",
            )
        by_id = {}
        for report in session_reports:
            _identity(report)
            _check(
                report["schema_version"] == "share_model_pilot_session_audit.v1",
                "measurement.report_domain",
                "wrong session audit record type",
            )
            session_id = report["session_id"]
            _check(
                session_id in ids
                and session_id not in by_id
                and report["origin"] == "model"
                and report["protocol_id"] == pilot_registration["protocol_id"]
                and report["model_configuration_id"] == pilot_registration["model_configuration_id"]
                and report["adapter_binding_id"] == pilot_registration["adapter_binding_id"],
                "measurement.report_domain",
                "duplicate, mock, replaced or unregistered session report",
            )
            by_id[session_id] = report
        ys: list[int | None] = []
        attempts: list[int] = []
        for session_id in ids:
            session_report = by_id.get(session_id)
            if session_report is None or session_report["evidence_complete"] is not True:
                result["missing_or_unknown_sessions"].append(session_id)
                ys.append(None)
                if session_report is not None:
                    _check(
                        session_report["Y"] is None,
                        "measurement.null_not_zero",
                        "incomplete evidence was converted into a model failure",
                    )
                continue
            y = int(
                session_report["valid_final"] is True
                and session_report["protocol_valid"] is True
                and session_report["qa_valid"] is True
            )
            _check(
                type(session_report["Y"]) is int and session_report["Y"] == y,
                "measurement.success_definition",
                "reported Y does not equal valid Final AND protocol AND QA",
            )
            _check(
                type(session_report["provider_attempts"]) is int
                and 1 <= session_report["provider_attempts"] <= 12,
                "measurement.attempts",
                "complete model session has an invalid attempt count",
            )
            ys.append(y)
            attempts.append(session_report["provider_attempts"])
            result["evidence_complete_count"] += 1
            if session_report["protocol_valid"] is not True:
                result["mechanism_defect_session_ids"].append(session_id)
            result["known_success_count"] += y
            result["support_descriptions"][session_id] = session_report["support_description"][
                "label"
            ]
        result["known_provider_attempts"] = sum(attempts)
        _check(
            sum(attempts) <= 72,
            "measurement.attempt_budget",
            "actual online attempt total exceeds 72",
        )
        result["Y_by_session"] = [
            {"session_id": session_id, "Y": y} for session_id, y in zip(ids, ys, strict=True)
        ]
        if result["evidence_complete_count"] == 6:
            result["success_count"] = result["known_success_count"]
            result["q_public_protocol"] = result["success_count"] / 6
            result["exact_fraction"] = f"{result['success_count']}/6"
            result["provider_attempts"] = sum(attempts)
            result["model_attribution_allowed"] = not result["mechanism_defect_session_ids"]
            result["workflow_complete"] = all(
                by_id[session_id]["protocol_valid"] is True for session_id in ids
            )
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError, RecursionError) as error:
        result["errors"].append(
            {"stage": getattr(error, "stage", "measurement.missing_object"), "reason": str(error)}
        )
        result.update(
            workflow_complete=False, q_public_protocol=None, exact_fraction=None, success_count=None
        )
    return _pilot_record("pilot_measurement", **result)
