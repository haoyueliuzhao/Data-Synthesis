"""Public submission language; no route selector, plan input or Host-filled Claim."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE = (
    "finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_preflight_only"
)
REVIEW_BYTES = 15_329
REVIEW_SHA256 = "2e1bef7f9691f56931db9f22a8c0330f8bf557e66daa286e316f6b68b93cfab1"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/"
    "finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905"
)
PARENT_MANIFEST = (
    "part_whole_share_manifest:21a2e52198336101d1cf273af76a3bb0d26eb9baefb68dcd946c28261630a251"
)
PARENT_ROOT = (
    "part_whole_share_root:4a18be9c78b3f7bae7308339de50a0233db81c08484b5fa7fc3791c60fb1b221"
)
PARENT_SOURCE_COMMIT = "b6783ac6676c6b821ab819f9215961fbd0605e84"
PARENT_SOURCE_TREE = "475ff81d9e26d9424c1f6942de5cf7eb5cda1fb2"
CONTEXT_FIELDS = ("subject", "scope", "period", "unit", "currency")
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


class ProtocolError(ValueError):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def require(condition: bool, stage: str) -> None:
    if not condition:
        raise ProtocolError(stage)


def record(record_type: str, **fields: Any) -> dict[str, Any]:
    require("id" not in fields and "schema_version" not in fields, "identity.caller_identity")
    body = {"schema_version": f"public_share_protocol_{record_type}.v1", **fields}
    return {
        **body,
        "id": strict_canonical_hash(body, prefix=f"public_share_protocol_{record_type}:"),
    }


class StrictPublic(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class Operand(StrictPublic):
    role: Literal["member", "relation", "numerator", "denominator", "ratio"]
    kind: Literal["evidence", "claim"]
    ref_id: str = Field(min_length=1)


class ActionBasis(StrictPublic):
    relation: Literal["requires"]
    evidence_refs: list[str]
    claim_refs: list[str]
    intended_metric: str = Field(min_length=1)


class Action(StrictPublic):
    kind: Literal["action"]
    state_id: str = Field(min_length=1)
    operation: Literal["relation_sum", "share_ratio", "scale_percent"]
    inputs: list[Operand]
    parameters: dict[str, str]
    public_basis: ActionBasis


class ScalarClaim(StrictPublic):
    value: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    period: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    lineage: list[str] = Field(min_length=1)


class UpdateBasis(StrictPublic):
    relation: Literal["supports", "declines"]
    observation_refs: list[str]
    evidence_refs: list[str]


class Update(StrictPublic):
    kind: Literal["update"]
    state_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    disposition: Literal["accept", "reject"]
    proposed_claim: ScalarClaim | None
    public_basis: UpdateBasis


class Answer(StrictPublic):
    value: str = Field(min_length=1)
    unit: Literal["percent"]


class FinalBasis(StrictPublic):
    relation: Literal["supports"]
    claim_refs: list[str]
    evidence_refs: list[str]


class Final(StrictPublic):
    kind: Literal["final"]
    state_id: str = Field(min_length=1)
    answer_claim_id: str = Field(min_length=1)
    answer: Answer
    citations: list[str]
    public_basis: FinalBasis


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "schema.duplicate_key")
        result[key] = value
    return result


def parse_submission(payload: bytes) -> dict[str, Any]:
    require(isinstance(payload, bytes) and 0 < len(payload) <= 32_768, "schema.payload_bytes")
    try:
        data = json.loads(payload, object_pairs_hook=_unique_pairs)
        require(isinstance(data, dict), "schema.object_required")
        kind = data.get("kind")
        cls = {"action": Action, "update": Update, "final": Final}.get(kind)
        require(cls is not None, "schema.kind")
        assert cls is not None
        return cls.model_validate(data).model_dump(mode="json")
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as error:
        raise ProtocolError("schema.public_submission") from error


def protocol_contract(context: dict[str, Any]) -> dict[str, Any]:
    return record(
        "contract",
        stage=STAGE,
        public_context_id=context["id"],
        task_id=context["task"]["id"],
        bounds={"actions": 3, "updates": 3, "submissions": 12},
        submission_schemas={
            "action": Action.model_json_schema(),
            "update": Update.model_json_schema(),
            "final": Final.model_json_schema(),
        },
        generator_owns=[
            "operation",
            "input_references",
            "parameters",
            "public_basis",
            "update_disposition",
            "complete_proposed_claim",
            "final_answer_and_citations",
        ],
        host_owns=[
            "public_state",
            "type_and_source_admission",
            "numeric_dispatch",
            "observation",
            "validation_of_submitted_update",
            "persistence",
            "content_identifiers",
        ],
        host_route_or_node_plan_input=False,
        automatic_observation_acceptance=False,
        host_fills_missing_proposed_claim=False,
        private_reasoning_requested_or_stored=False,
        generator_response_origin="registered_deterministic_fixture_not_model",
        provider_adapter_implemented=False,
        model_reachability_measured=False,
        rejected_submission_rule=(
            "increment submission count, typed feedback, no semantic mutation or dispatch"
        ),
        rejection_feedback="stage code only; no answer Oracle feedback",
        failed_callback_rule="persist typed failure without fallback or substituted proposal",
        pending_observation_rule="new Action/Final blocked until explicit generator Update",
        reject_update_rule="clear pending observation without creating an accepted Claim",
        final_rule="consume submitted accepted percent Claim; offline independent QA Oracle",
        positive_protocol_sessions=1,
        additional_formal_quotient_comparisons=0,
        direct_controls_are_model_or_runtime_evidence=False,
        provider_credential_gpu_limits=[0, 0, 0],
        old_mainline="remains_paused",
    )


def initial_dynamic() -> dict[str, Any]:
    return {
        "phase": "action",
        "accepted_claims": [],
        "pending_observation": None,
        "action_count": 0,
        "update_count": 0,
        "submission_count": 0,
        "last_feedback": None,
        "terminal": None,
    }
