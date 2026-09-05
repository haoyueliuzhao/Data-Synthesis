"""Exact public projections for one reused task, with no solution or route plan.

Inputs are already loaded frozen source/contract objects and Host-owned dynamic
state. This module never reads an Archive, constructs candidates, calls a kernel,
computes an answer, or attaches a generator identity to a public request.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from .models import DYNAMIC_FIELDS, record, require

CONTEXT_VIEW_FIELDS = (
    "task",
    "evidence",
    "operations",
    "numeric",
    "shared_obligations",
    "answer_schema",
)
EVIDENCE_ROLES = {"freight", "other", "total", "part_whole"}
OPERATION_NAMES = {"relation_sum", "share_ratio", "scale_percent"}
COUNTER_FIELDS = {
    "actions": "action_count",
    "updates": "update_count",
    "submissions": "submission_count",
}

# This complements the positive field projection. Source numbers, task targets,
# answer-format rules and actual Observations are public; evaluation outcomes and
# reference solutions are not. Numeric string scanning is not the authority.
PRIVATE_FIELDS = {
    "oracle",
    "answer_oracle",
    "expected_answer",
    "reference_answer",
    "gold_answer",
    "reference_solution",
    "route",
    "route_label",
    "candidate_route_label",
    "nodes",
    "candidate_family",
    "candidate_plan",
    "solution_plan",
    "next_operation",
    "next_action",
    "route_specific_preconditions",
    "measurement",
    "class_count",
    "formal_class_count",
    "w_share",
    "qa_valid",
    "trajectory_valid",
    "qualified",
    "private_reasoning",
}

INSTRUCTIONS = (
    "Return exactly one JSON object matching an allowed submission schema. "
    "Choose the operation, current visible operand references, and parameters yourself. "
    "After an action Observation, explicitly accept or reject it in an update before "
    "submitting another action or a final answer. An accepted claim must be fully "
    "submitted and supported by that actual Observation. Cite the actual support; "
    "do not include private reasoning."
)


def _content_identity(obj: dict[str, Any]) -> None:
    require(isinstance(obj, dict), "public_view.record_object")
    schema = obj.get("schema_version")
    require(isinstance(schema, str) and schema.endswith(".v1"), "public_view.record_schema")
    assert isinstance(schema, str)
    body = {key: value for key, value in obj.items() if key != "id"}
    require(
        obj.get("id") == strict_canonical_hash(body, prefix=schema.removesuffix(".v1") + ":"),
        "public_view.record_identity",
    )


def _public_fields_only(value: Any) -> None:
    if isinstance(value, dict):
        require(
            all(isinstance(key, str) and key.casefold() not in PRIVATE_FIELDS for key in value),
            "public_view.private_field",
        )
        for item in value.values():
            _public_fields_only(item)
    elif isinstance(value, list):
        for item in value:
            _public_fields_only(item)


def public_context(source: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Whitelist public frozen objects; omit the private outer experiment contract."""
    task = contract["task"]
    evidence = source["evidence"]
    operations = contract["operations"]
    require(set(evidence) == EVIDENCE_ROLES, "public_view.evidence_universe")
    require(set(operations) == OPERATION_NAMES, "public_view.operations")
    require(
        source["id"] == contract["source_binding_id"] == task["source_binding_id"],
        "public_view.source_binding",
    )
    require(
        sorted(item["id"] for item in evidence.values()) == task["evidence_universe_ids"],
        "public_view.task_evidence_universe",
    )
    # The original task, Evidence and operations are copied whole. Their old IDs
    # remain content identities, not IDs misleadingly attached to altered bodies.
    for obj in (task, *evidence.values(), *operations.values()):
        _content_identity(obj)
    values = {
        "task": task,
        "evidence": evidence,
        "operations": operations,
        "numeric": contract["numeric"],
        "shared_obligations": contract["shared_obligations"],
        "answer_schema": contract["answer_schema"],
        "actual_support_citations_required": contract["actual_support_citations_required"],
        "all_visible_evidence_citations_required": contract[
            "all_visible_evidence_citations_required"
        ],
    }
    _public_fields_only(values)
    return record("public_context", **deepcopy(values))


def make_state(
    context: dict[str, Any], protocol: dict[str, Any], dynamic: dict[str, Any]
) -> dict[str, Any]:
    """Project an independent public snapshot; never select an operation or accept a claim."""
    _content_identity(context)
    _content_identity(protocol)
    require(protocol["public_context_id"] == context["id"], "public_view.protocol_context")
    require(protocol["task_id"] == context["task"]["id"], "public_view.protocol_task")
    require(set(dynamic) == DYNAMIC_FIELDS, "public_view.dynamic_fields")
    require(dynamic["phase"] in {"action", "update", "terminal"}, "public_view.phase")
    require(isinstance(dynamic["accepted_claims"], list), "public_view.accepted_claims")
    for claim in dynamic["accepted_claims"]:
        _content_identity(claim)
    pending = dynamic["pending_observation"]
    require(pending is None or isinstance(pending, dict), "public_view.pending_observation")
    if pending is not None:
        _content_identity(pending)
    require(
        (dynamic["phase"] == "update") == (pending is not None),
        "public_view.pending_phase",
    )
    terminal = dynamic["terminal"]
    require(terminal is None or isinstance(terminal, str), "public_view.terminal_value")
    require(
        (dynamic["phase"] == "terminal") == (terminal is not None),
        "public_view.terminal_phase",
    )
    feedback = dynamic["last_feedback"]
    require(
        feedback is None
        or (
            isinstance(feedback, dict)
            and set(feedback) == {"code"}
            and isinstance(feedback["code"], str)
        ),
        "public_view.feedback_fields",
    )
    bounds = protocol["bounds"]
    require(set(bounds) == set(COUNTER_FIELDS), "public_view.bound_fields")
    remaining = {}
    for name, counter in COUNTER_FIELDS.items():
        value, bound = dynamic[counter], bounds[name]
        require(
            type(value) is int and type(bound) is int and 0 <= value <= bound,
            "public_view.counter_bounds",
        )
        remaining[name] = bound - value
    values = {
        "context_id": context["id"],
        "protocol_id": protocol["id"],
        **{key: context[key] for key in CONTEXT_VIEW_FIELDS},
        **dynamic,
        "remaining_bounds": remaining,
    }
    _public_fields_only(values)
    return record("public_state", **deepcopy(values))


def request_for(state: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    """Expose only the public snapshot and currently legal submission schemas."""
    _content_identity(state)
    _content_identity(protocol)
    require(state["protocol_id"] == protocol["id"], "public_view.request_protocol")
    require(state["context_id"] == protocol["public_context_id"], "public_view.request_context")
    require(state["phase"] != "terminal", "public_view.terminal_request")
    require(state["remaining_bounds"]["submissions"] > 0, "public_view.submission_budget")
    if state["phase"] == "update":
        require(state["remaining_bounds"]["updates"] > 0, "public_view.update_budget")
        kinds = ["update"]
    else:
        require(state["phase"] == "action", "public_view.request_phase")
        kinds = ["action", "final"] if state["remaining_bounds"]["actions"] > 0 else ["final"]
    schemas = protocol["submission_schemas"]
    require(set(schemas) == {"action", "update", "final"}, "public_view.submission_schemas")
    values = {
        "state_id": state["id"],
        "state": state,
        "allowed_submission_kinds": kinds,
        "response_schema": {kind: schemas[kind] for kind in kinds},
        "instructions": INSTRUCTIONS,
        "stable_public_json_only": True,
    }
    _public_fields_only(values)
    return record("generator_request", **deepcopy(values))
