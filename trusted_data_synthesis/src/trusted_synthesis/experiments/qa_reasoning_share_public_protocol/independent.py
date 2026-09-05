"""Independent replay of generator-owned public submissions and Host transitions.

This module imports no protocol parser, admission helper, engine, generator,
financial Runtime or quotient comparator.  It reads actual public response text,
rebuilds admitted inputs, and checks that an observed result remains pending until
a separate generator update explicitly accepts its complete Claim.  The offline
answer oracle is never attributed to a generator or an executed Action.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
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
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
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


def _context(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> None:
    for obj in (
        source,
        legacy,
        legacy["task"],
        *source["evidence"].values(),
        *legacy["operations"].values(),
        context,
        protocol,
        binding,
    ):
        _identity(obj)
    _check(
        source["id"] == legacy["source_binding_id"] == legacy["task"]["source_binding_id"],
        "independent.frozen_context",
        "legacy source/task binding differs",
    )
    _check(
        set(source["evidence"]) == {"freight", "other", "total", "part_whole"}
        and set(legacy["operations"]) == {"relation_sum", "share_ratio", "scale_percent"},
        "independent.frozen_context",
        "frozen finite source or operation domain differs",
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
        "independent.public_context",
        "public context is not the exact allowed frozen projection",
    )
    _check(
        protocol["public_context_id"] == context["id"]
        and protocol["task_id"] == context["task"]["id"]
        and protocol["bounds"] == {"actions": 3, "updates": 3, "submissions": 12}
        and protocol["host_route_or_node_plan_input"] is False
        and protocol["automatic_observation_acceptance"] is False
        and protocol["host_fills_missing_proposed_claim"] is False
        and protocol["private_reasoning_requested_or_stored"] is False
        and protocol["provider_adapter_implemented"] is False
        and protocol["model_reachability_measured"] is False
        and protocol["provider_credential_gpu_limits"] == [0, 0, 0],
        "independent.protocol_contract",
        "unsupported public protocol or ownership policy",
    )
    _check(
        legacy["numeric"]
        == {
            "precision": 50,
            "rounding": "ROUND_HALF_EVEN",
            "final_quantum": "0.000001",
            "source_reconciliation_tolerance": "0",
            "answer_tolerance": "0",
        },
        "independent.numeric_contract",
        "numeric contract changed",
    )
    _check(
        binding["kind"] == "deterministic_fixture",
        "independent.generator_binding",
        "generator is not the registered fixture",
    )
    _check(
        binding["module"]
        == "trusted_synthesis.experiments.qa_reasoning_share_public_protocol.fixture"
        and binding["class_name"] == "PublicRequestFixture"
        and binding["method_name"] == "generate"
        and binding["source_path"]
        == (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/"
            "qa_reasoning_share_public_protocol/fixture.py"
        )
        and isinstance(binding["source_sha256"], str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", binding["source_sha256"]))
        and binding["semantic_choices_owned_by"] == "deterministic_fixture_not_model"
        and binding["host_route_or_plan_argument"] is False
        and binding["Provider_calls"] == binding["credentials"] == 0
        and binding["callback_response_is_authority_for_submission"] is True,
        "independent.generator_binding",
        "registered generator source/identity/ownership metadata differs",
    )
    _check(
        legacy["task"]["evidence_universe_ids"]
        == sorted(item["id"] for item in source["evidence"].values()),
        "independent.frozen_context",
        "visible Evidence universe differs",
    )


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


def _replay(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy: Mapping[str, Any],
    binding: Mapping[str, Any],
    initial_state: Mapping[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    _context(context, protocol, source, legacy, binding)
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
        initial_state == state,
        "independent.initial_state",
        "initial State is not the same uncommitted public environment",
    )
    witnesses = []
    final_result = None
    raw_hash_only = 0
    raw_replayed = 0
    callback_failures = 0
    rejected_count = 0
    for sequence, bundle in enumerate(events):
        _check(
            set(bundle) == BUNDLE_FIELDS,
            "independent.event_schema",
            "missing or unsupported exchange object",
        )
        for kind in ("generator_turn", "submission", "receipt", "event"):
            _identity(bundle[kind], kind)
        for kind in ("execution", "observation", "claim", "final"):
            if bundle[kind] is not None:
                _identity(bundle[kind], kind)
        request = _request(state, protocol)
        _check(
            bundle["request"] == request,
            "independent.generator_request",
            "generator saw a different State, schema or hidden Host plan",
        )
        turn, submission, receipt = (
            bundle["generator_turn"],
            bundle["submission"],
            bundle["receipt"],
        )
        _check(
            turn["request_id"] == request["id"]
            and turn["state_id"] == state["id"]
            and turn["generator_binding_id"] == binding["id"]
            and turn["origin"] == binding["kind"]
            and turn["provider_calls"] == 0
            and turn["host_supplied_response"] is False,
            "independent.generator_turn",
            "response origin does not bind the actual registered generator turn",
        )
        _check(
            submission["generator_turn_id"] == turn["id"]
            and submission["request_id"] == request["id"]
            and submission["state_id"] == state["id"]
            and submission["field_origin"] == binding["kind"]
            and submission["host_repairs"] == []
            and submission["response_sha256"] == turn["response_sha256"]
            and submission["response_byte_count"] == turn["response_byte_count"],
            "independent.submission_origin",
            "submission was repaired, substituted or detached from its generator response",
        )
        parsed, admission = None, None
        code = None
        if submission["raw_public_json"] is not None:
            raw_replayed += 1
            text = submission["raw_public_json"]
            _check(
                isinstance(text, str)
                and turn["callback_error"] is None
                and _sha(text.encode("utf-8")) == turn["response_sha256"]
                and len(text.encode("utf-8")) == turn["response_byte_count"],
                "independent.raw_response",
                "retained raw response bytes differ from the callback receipt",
            )
            try:
                parsed = _parse_raw(text)
            except SubmissionRejected as error:
                raise IndependentError("independent.retained_public_grammar", str(error)) from error
            _check(
                parsed == submission["parsed"],
                "independent.raw_response",
                "Host parsed fields differ from actual generator JSON",
            )
            try:
                admission = _admission(parsed, state, protocol, source, legacy)
                code = "admitted." + parsed["kind"]
            except SubmissionRejected as error:
                code = str(error)
        else:
            _check(
                submission["parsed"] is None,
                "independent.raw_response",
                "parsed response has no original public JSON",
            )
            if turn["callback_error"] is not None:
                _check(
                    turn["callback_error"] == "generator.callback_failure"
                    and turn["response_sha256"] is None
                    and turn["response_byte_count"] == 0,
                    "independent.callback_failure",
                    "callback failure was replaced with a response",
                )
                code = "generator.callback_failure"
                callback_failures += 1
            else:
                _check(
                    isinstance(turn["response_sha256"], str)
                    and bool(re.fullmatch(r"[0-9a-f]{64}", turn["response_sha256"]))
                    and type(turn["response_byte_count"]) is int
                    and turn["response_byte_count"] >= 0
                    and receipt["code"]
                    in {
                        "schema.payload_bytes",
                        "schema.object_required",
                        "schema.kind",
                        "schema.duplicate_key",
                        "schema.public_submission",
                    },
                    "independent.malformed_response_receipt",
                    "malformed raw response lacks a bounded typed refusal",
                )
                code = receipt["code"]
                raw_hash_only += 1
        expected_receipt = _record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            pre_state_id=state["id"],
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
            "independent.admission_receipt",
            "typed admission or pre-dispatch binding differs",
        )
        before = state
        dynamic = copy.deepcopy({key: before[key] for key in DYNAMIC_FIELDS})
        dynamic["submission_count"] += 1
        execution = observation = claim = final = None
        if admission is None:
            rejected_count += 1
            dynamic["last_feedback"] = {"code": code}
        elif parsed is not None and parsed["kind"] == "action":
            inputs = admission["inputs"]
            output = _output(parsed, inputs, source, legacy)
            operation = parsed["operation"]
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
            witnesses.append(
                {
                    "kind": "generator_action",
                    "generator_turn_id": turn["id"],
                    "submission_id": submission["id"],
                    "operation": operation,
                    "actual_inputs": parsed["inputs"],
                    "actual_observation_id": observation["id"],
                    "claim_created_before_update": False,
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
                    field_origin="deterministic_fixture",
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
            witnesses.append(
                {
                    "kind": "generator_update",
                    "generator_turn_id": turn["id"],
                    "submission_id": submission["id"],
                    "disposition": parsed["disposition"],
                    "actual_observation_id": pending["id"],
                    "accepted_claim_id": claim["id"] if claim else None,
                    "complete_claim_submitted_by_generator": parsed["proposed_claim"] is not None,
                    "host_filled_claim": False,
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
                field_origin="deterministic_fixture",
            )
            final_result = final
            dynamic.update(
                phase="terminal",
                terminal="final_submitted",
                last_feedback={"code": "final_submitted"},
            )
        for name, expected in (
            ("execution", execution),
            ("observation", observation),
            ("claim", claim),
            ("final", final),
        ):
            _check(
                bundle[name] == expected,
                "independent.actual_" + name,
                f"actual {name} was injected or detached from this generator submission",
            )
        if (
            dynamic["submission_count"] >= protocol["bounds"]["submissions"]
            and dynamic["phase"] != "terminal"
        ):
            dynamic.update(
                phase="terminal",
                terminal="submission_budget_exhausted",
                pending_observation=None,
                last_feedback={"code": "submission_budget_exhausted"},
            )
        after = _state(context, protocol, dynamic)
        _check(
            bundle["post_state"] == after,
            "independent.state_transition",
            (
                "Host state advanced or changed a Claim without the matching "
                "explicit generator submission"
            ),
        )
        expected_event = _record(
            "event",
            sequence=sequence,
            pre_state_id=before["id"],
            post_state_id=after["id"],
            request_id=request["id"],
            generator_turn_id=turn["id"],
            submission_id=submission["id"],
            receipt_id=receipt["id"],
            execution_id=execution["id"] if execution else None,
            observation_id=observation["id"] if observation else None,
            claim_id=claim["id"] if claim else None,
            final_id=final["id"] if final else None,
        )
        _check(
            bundle["event"] == expected_event,
            "independent.event_parents",
            "event ordering or actual producer references differ",
        )
        state = after
    oracle = None
    qa_valid = None
    if final_result is not None:
        evidence = source["evidence"]
        expected_answer = (
            _number(evidence["freight"]["value"])
            / _number(evidence["total"]["value"])
            * Decimal(100)
        ).quantize(Decimal(legacy["numeric"]["final_quantum"]))
        qa_valid = final_result["answer"] == {"value": str(expected_answer), "unit": "percent"}
        oracle = {
            "expected_answer": str(expected_answer),
            "formula": "100 * disclosed freight / disclosed total",
            "performed_offline_by_independent_validator": True,
            "generator_or_action_execution": False,
            "oracle_answer_inserted_into_public_request": False,
        }
    return {
        "protocol_valid": True,
        "qa_valid": qa_valid,
        "final_submitted": final_result is not None,
        "qualified": qa_valid is True,
        "generator_callbacks": len(events),
        "observed_action_count": dynamic["action_count"],
        "observed_update_count": dynamic["update_count"],
        "observed_submission_count": dynamic["submission_count"],
        "observed_rejections": rejected_count,
        "accepted_claim_count": len(state["accepted_claims"]),
        "terminal": state["terminal"],
        "generator_ownership_witnesses": witnesses,
        "answer_oracle": oracle,
        "raw_public_responses_replayed": raw_replayed,
        "callback_failures": callback_failures,
        "malformed_raw_hash_only_count": raw_hash_only,
        "malformed_raw_grammar_replayed": False,
        "final_state_id": state["id"],
    }


def audit_records(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy_contract: Mapping[str, Any],
    generator_binding: Mapping[str, Any],
    initial_state: Mapping[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replay actual decoded records without trusting receipt or origin labels alone."""
    report: dict[str, Any] = {
        "schema_version": "public_share_protocol_independent_report.v1",
        "protocol_valid": False,
        "qa_valid": None,
        "qualified": False,
        "first_failure": None,
        "candidate_runtime_executions": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "gpu_calls": 0,
        "old_quotient_recomputed": False,
        "model_reachability": "NOT_MEASURED",
        "model_class_count": None,
        "generator_origin": "registered_deterministic_fixture_not_model",
        "independent_imports_engine_parser_admission_or_runtime": False,
    }
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        decimal_context.rounding = ROUND_HALF_EVEN
        try:
            report.update(
                _replay(
                    context,
                    protocol,
                    source,
                    legacy_contract,
                    generator_binding,
                    initial_state,
                    events,
                )
            )
        except (OSError, ValueError, KeyError, TypeError, IndexError, ArithmeticError) as error:
            report["first_failure"] = {
                "stage": getattr(error, "stage", "independent.missing_or_invalid_object"),
                "reason": str(error),
            }
    return report


def read_session_records(session_root: str | Path) -> dict[str, Any]:
    """Read the complete byte-bound event stream and verify pre-dispatch fsync order."""
    requested = Path(session_root)
    _check(not requested.is_symlink(), "independent.artifact_path", "session root is a symlink")
    root = requested.resolve()
    inventory = list(root.rglob("*"))
    _check(
        not any(path.is_symlink() for path in inventory),
        "independent.artifact_path",
        "session contains symlinks",
    )
    payload = (root / "session_manifest.json").read_bytes()
    manifest = json.loads(payload)
    _identity(manifest, "session_manifest")
    _check(
        payload == canonical_json_bytes(manifest),
        "independent.canonical_bytes",
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
            "positive_protocol_sessions",
            "Provider_calls",
        },
        "independent.manifest_schema",
        "session manifest fields differ",
    )
    objects = {}
    for member in manifest["members"]:
        _check(
            set(member) == {"relative_path", "sha256", "byte_count"},
            "independent.manifest_schema",
            "member schema differs",
        )
        relative = member["relative_path"]
        path = (root / relative).resolve()
        _check(
            not Path(relative).is_absolute()
            and ".." not in Path(relative).parts
            and path.is_relative_to(root)
            and relative not in objects
            and relative != "session_manifest.json",
            "independent.artifact_path",
            "unsafe or duplicate session file",
        )
        raw = path.read_bytes()
        _check(
            _sha(raw) == member["sha256"] and len(raw) == member["byte_count"],
            "independent.artifact_bytes",
            "actual session bytes differ from manifest",
        )
        obj = json.loads(raw)
        _check(
            raw == canonical_json_bytes(obj),
            "independent.canonical_bytes",
            "session object is not canonical",
        )
        objects[relative] = obj
    actual_files = {path.relative_to(root).as_posix() for path in inventory if path.is_file()}
    _check(
        actual_files == set(objects) | {"session_manifest.json"},
        "independent.artifact_inventory",
        "manifest does not cover actual files exactly",
    )
    initial_path = manifest["initial_state"]
    ordered_paths = [initial_path]
    events = []
    required = {"request", "generator_turn", "submission", "receipt", "post_state", "event"}
    for paths in manifest["events"]:
        _check(
            required.issubset(paths) and set(paths).issubset(BUNDLE_FIELDS),
            "independent.manifest_schema",
            "exchange paths omit required objects or include unknown ones",
        )
        event = {kind: objects[paths[kind]] if kind in paths else None for kind in BUNDLE_FIELDS}
        events.append(event)
        ordered_paths.extend(
            paths[kind]
            for kind in (
                "request",
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
    _check(
        len(ordered_paths) == len(set(ordered_paths)) and set(ordered_paths) == set(objects),
        "independent.artifact_inventory",
        "duplicate references or unaccounted session objects",
    )
    expected_events: list[dict[str, Any]] = []
    for path in ordered_paths:
        for kind in ("file_fsync", "directory_fsync"):
            expected_events.append(
                {"event_ordinal": len(expected_events) + 1, "kind": kind, "relative_path": path}
            )
    _check(
        manifest["write_events"] == expected_events,
        "independent.pre_dispatch_order",
        (
            "request/turn/submission/receipt do not durably precede execution "
            "and explicit update Claims"
        ),
    )
    _check(
        manifest["kernel_calls"] == sum(bundle["execution"] is not None for bundle in events)
        and manifest["generator_callbacks"] == len(events)
        and manifest["positive_protocol_sessions"] == 1
        and manifest["Provider_calls"] == 0,
        "independent.manifest_counters",
        "callback, kernel or provider counters differ from actual records",
    )
    return {"manifest": manifest, "initial_state": objects[initial_path], "events": events}


def audit_session(
    context: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source: Mapping[str, Any],
    legacy_contract: Mapping[str, Any],
    generator_binding: Mapping[str, Any],
    session_root: str | Path,
) -> dict[str, Any]:
    """Validate actual persisted session files and independently replay their semantics."""
    try:
        records = read_session_records(session_root)
        manifest = records["manifest"]
        _check(
            manifest["protocol_id"] == protocol["id"]
            and manifest["public_context_id"] == context["id"]
            and manifest["generator_binding_id"] == generator_binding["id"],
            "independent.manifest_binding",
            "session manifest binds a different protocol/context/generator",
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return {
            "schema_version": "public_share_protocol_independent_report.v1",
            "protocol_valid": False,
            "qa_valid": None,
            "qualified": False,
            "persisted_artifact_validation": False,
            "first_failure": {
                "stage": getattr(error, "stage", "independent.missing_or_invalid_artifact"),
                "reason": str(error),
            },
        }
    report = audit_records(
        context,
        protocol,
        source,
        legacy_contract,
        generator_binding,
        records["initial_state"],
        records["events"],
    )
    report["persisted_artifact_validation"] = True
    return report


def audit_registration(
    authority: Mapping[str, Any],
    binding: Mapping[str, Any],
    registration: Mapping[str, Any],
) -> dict[str, Any]:
    """Check registration records only; do not invoke or reconstruct a callback."""
    result: dict[str, Any] = {
        "passed": False,
        "errors": [],
        "callback_executed_by_this_check": False,
        "full_runtime_closure_asserted": False,
        "scope": "source authority / fixture binding / pre-callback registration record chain",
    }
    try:
        for obj in (authority, binding, registration):
            _identity(obj)
        members = [
            member
            for member in authority["implementation"]["members"]
            if member["path"] == binding["source_path"]
        ]
        _check(
            len(members) == 1 and members[0]["sha256"] == binding["source_sha256"],
            "independent.generator_registration",
            "generator source path and digest do not identify one declared source member",
        )
        expected = _record(
            "generator_registration",
            source_authority_id=authority["id"],
            generator_binding_id=binding["id"],
            fixture_source_member=members[0],
            before_first_callback=True,
            actual_callable_check=(
                "loaded_class_bound_method_and_compiled_source_code_each_exchange"
            ),
            callback_source_only_not_full_runtime_closure=True,
        )
        _check(
            registration == expected,
            "independent.generator_registration",
            "registration is not the exact pre-callback source/member/binding declaration",
        )
        result["passed"] = True
        result["generator_binding_id"] = binding["id"]
        result["registered_source_path"] = members[0]["path"]
        result["registered_source_sha256"] = members[0]["sha256"]
    except (ValueError, KeyError, TypeError, IndexError) as error:
        result["errors"].append(
            {
                "stage": getattr(error, "stage", "independent.missing_registration_object"),
                "reason": str(error),
            }
        )
    return result
