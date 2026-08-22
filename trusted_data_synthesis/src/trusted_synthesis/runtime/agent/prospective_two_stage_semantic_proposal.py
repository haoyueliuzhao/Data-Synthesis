from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
    ProspectiveFailureClassification,
    PublicActionState,
    SemanticDecisionProposal,
    make_semantic_decision_proposal,
    public_action_state_from_rendered_prompt,
)

TWO_STAGE_RESPONSE_PROTOCOL_VERSION: Final = "prospective_two_stage_stage_one_response.v1"
SEMANTIC_PROPOSAL_RESCUE_VERSION: Final = "prospective_semantic_proposal_rescue.v1"
MAXIMUM_RESCUE_PROMPT_UTF8_BYTES: Final = 6144

DecisionKind = Literal[
    "acquire_public_input",
    "execute_public_operation",
    "verify_terminal_operation",
    "emit_final_answer",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StageOneSemanticProposalPayload(FrozenModel):
    stage: Literal["semantic_decision_proposal"] = "semantic_decision_proposal"
    state_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    tool_id: str | None = None
    node_id: str | None = None
    operator_id: str | None = None
    operand_sources: tuple[str, ...] = ()
    direct_arguments: dict[str, Any] | None = None
    evidence_ids: tuple[str, ...] = ()
    protocol: Literal["prospective_two_stage_stage_one_response.v1"] = (
        TWO_STAGE_RESPONSE_PROTOCOL_VERSION
    )

    @model_validator(mode="after")
    def validate_payload(self) -> StageOneSemanticProposalPayload:
        # Reuse the frozen semantic-proposal validator without letting the model
        # manufacture the content-addressed proposal identity.
        make_semantic_decision_proposal(
            state_id=self.state_id,
            decision_kind=self.decision_kind,
            tool_id=self.tool_id,
            node_id=self.node_id,
            operator_id=self.operator_id,
            operand_sources=self.operand_sources,
            direct_arguments=self.direct_arguments,
            evidence_ids=self.evidence_ids,
        )
        return self


class StageOneFinalAnswerPayload(FrozenModel):
    stage: Literal["final_answer"] = "final_answer"
    answer: dict[str, Any] = Field(min_length=1)
    protocol: Literal["prospective_two_stage_stage_one_response.v1"] = (
        TWO_STAGE_RESPONSE_PROTOCOL_VERSION
    )


class ModelResultRejection(ValueError):
    def __init__(self, classification: ProspectiveFailureClassification) -> None:
        super().__init__(classification.subtype)
        self.classification = classification


def _classification(
    family: Literal[
        "channel_parse_failure",
        "response_serialization_failure",
        "decision_phase_control_failure",
        "prompt_echo_instruction_failure",
        "semantic_tool_argument_failure",
        "runtime_failure",
        "instrument_failure",
    ],
    subtype: str,
) -> ProspectiveFailureClassification:
    return ProspectiveFailureClassification(family=family, subtype=subtype)


def _reject_prompt_echo(payload: Mapping[str, Any]) -> None:
    if any(
        key in payload
        for key in (
            "public_action_state",
            "public_context",
            "progress",
            "history",
            "response_contract",
            "instruction",
        )
    ):
        raise ModelResultRejection(
            _classification(
                "prompt_echo_instruction_failure",
                "public_prompt_payload_echoed",
            )
        )


def parse_semantic_proposal_payload(
    payload: Mapping[str, Any],
    *,
    expected_state: PublicActionState,
) -> SemanticDecisionProposal:
    _reject_prompt_echo(payload)
    if payload.get("stage") == "final_answer" or "answer" in payload:
        raise ModelResultRejection(
            _classification(
                "decision_phase_control_failure",
                "answer_emitted_during_semantic_proposal_stage",
            )
        )
    try:
        parsed = StageOneSemanticProposalPayload.model_validate(payload)
    except ValidationError as exc:
        raise ModelResultRejection(
            _classification(
                "response_serialization_failure",
                "semantic_proposal_not_exact_contract",
            )
        ) from exc
    if parsed.state_id != expected_state.state_id:
        raise ModelResultRejection(
            _classification(
                "semantic_tool_argument_failure",
                "semantic_proposal_binds_wrong_public_state",
            )
        )
    return make_semantic_decision_proposal(
        state_id=parsed.state_id,
        decision_kind=parsed.decision_kind,
        tool_id=parsed.tool_id,
        node_id=parsed.node_id,
        operator_id=parsed.operator_id,
        operand_sources=parsed.operand_sources,
        direct_arguments=parsed.direct_arguments,
        evidence_ids=parsed.evidence_ids,
    )


def parse_final_answer_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    _reject_prompt_echo(payload)
    if payload.get("stage") == "semantic_decision_proposal" or "decision_kind" in payload:
        raise ModelResultRejection(
            _classification(
                "decision_phase_control_failure",
                "semantic_proposal_emitted_during_final_answer_stage",
            )
        )
    try:
        parsed = StageOneFinalAnswerPayload.model_validate(payload)
    except ValidationError as exc:
        raise ModelResultRejection(
            _classification(
                "response_serialization_failure",
                "final_answer_not_exact_object_contract",
            )
        ) from exc
    return dict(parsed.answer)


def semantic_proposal_payload(proposal: SemanticDecisionProposal) -> dict[str, Any]:
    return {
        "stage": "semantic_decision_proposal",
        "state_id": proposal.state_id,
        "decision_kind": proposal.decision_kind,
        "tool_id": proposal.tool_id,
        "node_id": proposal.node_id,
        "operator_id": proposal.operator_id,
        "operand_sources": list(proposal.operand_sources),
        "direct_arguments": proposal.direct_arguments,
        "evidence_ids": list(proposal.evidence_ids),
        "protocol": TWO_STAGE_RESPONSE_PROTOCOL_VERSION,
    }


def final_answer_payload(answer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": "final_answer",
        "answer": dict(answer),
        "protocol": TWO_STAGE_RESPONSE_PROTOCOL_VERSION,
    }


def semantic_proposal_signature(proposal: SemanticDecisionProposal) -> str:
    return canonical_hash(
        proposal.model_dump(
            mode="json",
            exclude={
                "proposal_id",
                "state_id",
                "model_selected_every_semantic_field",
                "schema_version",
            },
        ),
        prefix="prospective_two_stage_semantic_proposal_signature:",
    )


def render_semantic_proposal_rescue_prompt(
    source_prompt: str,
    *,
    failure_family: str,
    failure_subtype: str,
) -> str:
    state = public_action_state_from_rendered_prompt(source_prompt)
    _, separator, raw_payload = source_prompt.partition("\n")
    if not separator:
        raise ValueError("semantic Proposal Rescue source Prompt lacks its JSON payload")
    source = json.loads(raw_payload)
    if not isinstance(source, Mapping):
        raise ValueError("semantic Proposal Rescue source Prompt is not an object")
    capsule = {
        "protocol": ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
        "response_protocol": TWO_STAGE_RESPONSE_PROTOCOL_VERSION,
        "instruction": source.get("instruction"),
        "public_path_condition": source.get("public_path_condition"),
        "public_action_state": state.model_dump(mode="json"),
        "typed_failure": {
            "family": failure_family,
            "subtype": failure_subtype,
        },
        "response_contract": {
            "stage": "semantic_decision_proposal",
            "model_must_select_every_semantic_field": True,
            "host_will_only_serialize_the_selected_semantics": True,
            "previous_response_content_reused": False,
            "private_reasoning_reused": False,
        },
        "rescue_protocol": SEMANTIC_PROPOSAL_RESCUE_VERSION,
    }
    prompt = "Return one corrected public semantic decision proposal as JSON.\n" + json.dumps(
        capsule,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(prompt.encode("utf-8")) > MAXIMUM_RESCUE_PROMPT_UTF8_BYTES:
        raise ValueError("semantic Proposal Rescue exceeds its absolute byte ceiling")
    return prompt
