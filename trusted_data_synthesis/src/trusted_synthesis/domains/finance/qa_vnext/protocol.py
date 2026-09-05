"""Public, typed judgments that constrain execution, not post-hoc explanations."""

from __future__ import annotations

import copy
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trusted_synthesis.canonical_json import strict_canonical_hash

PROTOCOL_VERSION = "finance_qa_public_decision_protocol.v2"


class ProtocolError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProtocolError(code)


def record(kind: str, **values: Any) -> dict[str, Any]:
    require("id" not in values and "schema_version" not in values, "identity.fields")
    body = {"schema_version": "finance_qa_vnext_" + kind + ".v2", **copy.deepcopy(values)}
    return {**body, "id": strict_canonical_hash(body, prefix="finance_qa_vnext_" + kind + ":")}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Basis(Strict):
    relation: Literal["requires"]
    evidence_refs: list[str]
    claim_refs: list[str]


class Effect(Strict):
    establishes_obligation: str
    output_schema: str


class Decision(Strict):
    obligation_id: str
    subgoal: Literal[
        "resolve_evidence", "derive_quantity", "compare_quantities", "select_total_support"
    ]
    candidate_action_ids: list[str] = Field(min_length=1)
    selected_action_id: str
    selection_rule: Literal[
        "dependency_ready",
        "registered_semantic_preconditions",
        "disclosed_total",
        "reconstructed_total",
    ]
    basis: Basis
    unresolved_uncertainty_refs: list[str]
    expected_effect: Effect


class Action(Strict):
    kind: Literal["action"]
    state_id: str
    decision: Decision
    operation: str
    inputs: list[dict[str, Any]]
    parameters: dict[str, Any]


class Assessment(Strict):
    relation: Literal["accepts_observed_proposition", "declines_observation"]
    observation_refs: list[str]
    evidence_refs: list[str]
    fulfills_obligation: str | None


class Update(Strict):
    kind: Literal["update"]
    state_id: str
    observation_id: str
    disposition: Literal["accept", "reject"]
    proposed_claim: dict[str, Any] | None
    assessment: Assessment
    remaining_uncertainty_refs: list[str]
    newly_enabled_obligation_ids: list[str]
    next_subgoal: str


class Final(Strict):
    kind: Literal["final"]
    state_id: str
    answer_claim_id: str
    result: dict[str, Any]
    citations: list[str]


def parse(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= 1_048_576, "submission.byte_bound")
    try:

        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result = {}
            for key, value in pairs:
                require(key not in result, "json.duplicate_key")
                result[key] = value
            return result

        def invalid_constant(value: str) -> Any:
            raise ProtocolError("json.non_finite_number")

        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
        require(isinstance(value, dict), "submission.object")
        schemas: dict[str, type[BaseModel]] = {"action": Action, "update": Update, "final": Final}
        require(value.get("kind") in schemas, "submission.kind")
        return schemas[value["kind"]].model_validate(value).model_dump(mode="json")
    except (ValidationError, UnicodeError, json.JSONDecodeError) as error:
        raise ProtocolError("submission.schema") from error


def contract() -> dict[str, Any]:
    return record(
        "protocol",
        version=PROTOCOL_VERSION,
        submission_schemas={
            name: schema.model_json_schema()
            for name, schema in (("action", Action), ("update", Update), ("final", Final))
        },
        action_before_execution=True,
        receipt_durable_before_dispatch=True,
        observation_is_not_accepted_claim=True,
        callback_submits_complete_claim=True,
        supported_update_dispositions=["accept", "reject"],
        accepted_claim_retraction_replacement_or_descendant_invalidation_supported=False,
        uncertainty_policy="empty when no evidenced unresolved uncertainty exists; never invented",
        decision_policy=(
            "typed obligation, selection, grounding and expected effect checked before dispatch"
        ),
        private_chain_of_thought_required=False,
        host_writes_callback_semantics=False,
        plan_given_is_not_autonomous_hidden_plan_inference=True,
        training_or_production_release=False,
    )
