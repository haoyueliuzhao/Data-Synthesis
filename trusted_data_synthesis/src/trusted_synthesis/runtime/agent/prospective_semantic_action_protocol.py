from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.public_operation import (
    PublicOperationContractView,
    PublicTerminalVerificationTargetView,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    PublicOperandSlot,
    PublicToolGrammar,
    PublicVariableAffordance,
    build_public_action_state,
)
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

SEMANTIC_ACTION_PROTOCOL_VERSION: Final[Literal["prospective_semantic_action_selection.v1"]] = (
    "prospective_semantic_action_selection.v1"
)
SEMANTIC_ACTION_STATE_VERSION: Final[Literal["prospective_semantic_action_state.v1"]] = (
    "prospective_semantic_action_state.v1"
)
CANONICAL_ACTION_VERSION: Final[Literal["prospective_canonical_public_action.v1"]] = (
    "prospective_canonical_public_action.v1"
)
CANONICAL_PROPOSAL_VERSION: Final[Literal["prospective_canonical_action_proposal.v1"]] = (
    "prospective_canonical_action_proposal.v1"
)
CANONICAL_COMMIT_VERSION: Final[Literal["prospective_canonical_action_commit.v1"]] = (
    "prospective_canonical_action_commit.v1"
)
SEMANTIC_REJECTION_VERSION: Final[Literal["prospective_semantic_rejection_observation.v1"]] = (
    "prospective_semantic_rejection_observation.v1"
)

ABI_RESCUE_LIMIT: Final[Literal[1]] = 1
SEMANTIC_RECOVERY_LIMIT: Final[Literal[1]] = 1
SEARCH_RESULT_LIMIT: Final[Literal[12]] = 12

DecisionKind = Literal[
    "acquire_public_input",
    "execute_public_operation",
    "verify_terminal_operation",
    "emit_final_answer",
]
AcquisitionMode = Literal[
    "search_public_record",
    "query_source_scoped",
    "query_fully_qualified",
    "open_public_document",
]
FrontierStatus = Literal[
    "blocked_dependencies",
    "dependency_ready",
    "executable",
    "terminal_verifiable",
]
RejectionCategory = Literal[
    "stale_public_state",
    "unknown_or_unselectable_action",
    "decision_kind_mismatch",
    "blocked_identical_public_call",
]

_PRIVATE_KEYS = frozenset(
    {
        "correct_answer",
        "expected_arguments",
        "gold_evidence_ids",
        "mechanism_private_state",
        "oracle",
        "oracle_program",
        "private_reasoning",
        "private_reasoning_content",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "suggested_argument_patch",
        "target_evidence_ids",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def _reject_private_keys(value: Any, *, path: str = "public") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _PRIVATE_KEYS:
                raise ValueError(f"private or action-bearing field exposed at {path}.{key}")
            _reject_private_keys(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_private_keys(item, path=f"{path}[{index}]")


class PublicSourceReference(FrozenModel):
    reference_id: str = Field(min_length=1)
    source_symbol: str = Field(min_length=1)
    reference_kind: Literal["public_evidence", "public_operation"]
    evidence_id: str | None = None
    operation_ref: str | None = None
    one_model_selectable_object_one_canonical_identifier: Literal[True] = True
    schema_version: Literal["prospective_public_source_reference.v1"] = (
        "prospective_public_source_reference.v1"
    )

    @model_validator(mode="after")
    def validate_reference(self) -> PublicSourceReference:
        if self.reference_kind == "public_evidence":
            if not self.evidence_id or self.operation_ref is not None:
                raise ValueError("public Evidence reference is malformed")
        elif not self.operation_ref or self.evidence_id is not None:
            raise ValueError("public Operation reference is malformed")
        if self.reference_id != _identity(
            self, "reference_id", "prospective_public_source_reference:"
        ):
            raise ValueError("public source-reference identity changed")
        return self


class PublicDocumentReference(FrozenModel):
    reference_id: str = Field(min_length=1)
    public_locator: str = Field(min_length=1)
    matching_source_symbols: tuple[str, ...] = Field(min_length=1)
    semantic_record: dict[str, Any] = Field(min_length=1)
    schema_version: Literal["prospective_public_document_reference.v1"] = (
        "prospective_public_document_reference.v1"
    )

    @model_validator(mode="after")
    def validate_reference(self) -> PublicDocumentReference:
        if self.matching_source_symbols != tuple(sorted(set(self.matching_source_symbols))):
            raise ValueError("public document symbols are not canonical")
        _reject_private_keys(self.semantic_record)
        if self.reference_id != _identity(
            self, "reference_id", "prospective_public_document_reference:"
        ):
            raise ValueError("public document-reference identity changed")
        return self


class PublicAcquisitionEvent(FrozenModel):
    call_index: int = Field(ge=1)
    tool_id: str = Field(min_length=1)
    acquisition_mode: AcquisitionMode | None
    target_source_symbols: tuple[str, ...]
    status: Literal["succeeded", "failed"]
    error_category: str | None
    public_call_signature: str = Field(min_length=1)
    exact_argument_values_retained: Literal[False] = False


class ActiveBlockedPublicCall(FrozenModel):
    public_call_signature: str = Field(min_length=1)
    failed_tool_id: str = Field(min_length=1)
    error_category: str = Field(min_length=1)
    latest_call_index: int = Field(ge=1)
    action_id: str | None = None
    acquisition_mode: AcquisitionMode | None = None
    target_source_symbols: tuple[str, ...] = ()
    exact_argument_values_retained: Literal[False] = False


class PublicOperationFrontier(FrozenModel):
    frontier_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    frontier_status: FrontierStatus
    node_kind: Literal["normalization", "calculation"]
    semantic_role: str = Field(min_length=1)
    terminal: bool
    tool_id: str = Field(min_length=1)
    dependency_node_ids: tuple[str, ...]
    missing_dependency_node_ids: tuple[str, ...]
    operand_slots: tuple[PublicOperandSlot, ...] = Field(min_length=1)
    unresolved_source_symbols: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    allowed_operator_ids: tuple[str, ...]
    operator_choice_mode: str = Field(min_length=1)
    operator_selection_rule: str | None
    operator_output_schemas: dict[str, str]
    required_output_schema: str | None
    fixed_parameters: dict[str, Any]
    normalization_target: dict[str, Any] | None

    @model_validator(mode="after")
    def validate_frontier(self) -> PublicOperationFrontier:
        if self.missing_dependency_node_ids != tuple(sorted(set(self.missing_dependency_node_ids))):
            raise ValueError("missing public dependencies are not canonical")
        if self.frontier_status == "blocked_dependencies":
            if not self.missing_dependency_node_ids:
                raise ValueError("blocked Operation has no missing dependency")
        elif self.frontier_status == "dependency_ready":
            if self.missing_dependency_node_ids or not self.unresolved_source_symbols:
                raise ValueError("dependency-ready Operation partition changed")
        elif self.frontier_status == "executable":
            if self.missing_dependency_node_ids or self.unresolved_source_symbols:
                raise ValueError("executable Operation is not fully resolved")
            if len(self.source_reference_ids) != len(self.operand_slots):
                raise ValueError("executable Operation source-reference count changed")
        elif (
            not self.terminal or self.missing_dependency_node_ids or self.unresolved_source_symbols
        ):
            raise ValueError("terminal-verifiable Operation partition changed")
        if self.frontier_id != _identity(
            self, "frontier_id", "prospective_public_operation_frontier:"
        ):
            raise ValueError("public Operation-frontier identity changed")
        return self


class CanonicalPublicAction(FrozenModel):
    action_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    tool_id: str | None = None
    target_source_symbols: tuple[str, ...] = ()
    acquisition_mode: AcquisitionMode | None = None
    acquisition_record: dict[str, Any] | None = None
    document_reference_id: str | None = None
    node_id: str | None = None
    operator_id: str | None = None
    source_reference_ids: tuple[str, ...] = ()
    evidence_reference_ids: tuple[str, ...] = ()
    wire_argument_fields: tuple[str, ...] = ()
    model_selects_this_complete_semantic_action: Literal[True] = True
    low_level_argument_values_model_generated: Literal[False] = False
    schema_version: Literal["prospective_canonical_public_action.v1"] = CANONICAL_ACTION_VERSION

    @model_validator(mode="after")
    def validate_action(self) -> CanonicalPublicAction:
        if self.target_source_symbols != tuple(sorted(set(self.target_source_symbols))):
            raise ValueError("canonical action target symbols are not canonical")
        if self.decision_kind == "acquire_public_input":
            if (
                not self.tool_id
                or not self.target_source_symbols
                or self.acquisition_mode is None
                or self.node_id is not None
                or self.operator_id is not None
                or self.source_reference_ids
                or self.evidence_reference_ids
            ):
                raise ValueError("canonical acquisition action is malformed")
            if self.acquisition_mode == "open_public_document":
                if self.document_reference_id is None or self.acquisition_record is not None:
                    raise ValueError("public document action is malformed")
            elif self.document_reference_id is not None or self.acquisition_record is None:
                raise ValueError("public record acquisition action is malformed")
        elif self.decision_kind == "execute_public_operation":
            if (
                not self.tool_id
                or not self.node_id
                or not self.source_reference_ids
                or self.acquisition_mode is not None
                or self.acquisition_record is not None
                or self.document_reference_id is not None
                or self.target_source_symbols
                or self.evidence_reference_ids
            ):
                raise ValueError("canonical Operation action is malformed")
        elif self.decision_kind == "verify_terminal_operation":
            if (
                not self.tool_id
                or not self.evidence_reference_ids
                or self.acquisition_mode is not None
                or self.acquisition_record is not None
                or self.document_reference_id is not None
                or self.target_source_symbols
                or self.node_id is not None
                or self.operator_id is not None
                or self.source_reference_ids
            ):
                raise ValueError("canonical verification action is malformed")
        elif any(
            (
                self.tool_id,
                self.target_source_symbols,
                self.acquisition_mode,
                self.acquisition_record,
                self.document_reference_id,
                self.node_id,
                self.operator_id,
                self.source_reference_ids,
                self.evidence_reference_ids,
                self.wire_argument_fields,
            )
        ):
            raise ValueError("canonical final action carries tool semantics")
        if self.wire_argument_fields != tuple(sorted(set(self.wire_argument_fields))):
            raise ValueError("canonical action wire fields are not canonical")
        _reject_private_keys(self.model_dump(mode="json", exclude={"action_id"}))
        if self.action_id != _identity(self, "action_id", "prospective_canonical_public_action:"):
            raise ValueError("canonical public-action identity changed")
        return self


class BlockedCanonicalAction(FrozenModel):
    action_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    selected_tool_id: str | None
    acquisition_mode: AcquisitionMode | None
    target_source_symbols: tuple[str, ...]
    error_category: str = Field(min_length=1)
    violated_public_constraint: Literal["identical_failed_public_call_is_not_selectable"] = (
        "identical_failed_public_call_is_not_selectable"
    )
    blocked_public_call_signature: str = Field(min_length=1)
    exact_argument_values_retained: Literal[False] = False


class PublicSemanticRejectionObservation(FrozenModel):
    rejection_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    failed_decision_kind: DecisionKind
    selected_action_id: str = Field(min_length=1)
    selected_tool_id: str | None
    error_category: RejectionCategory
    violated_public_constraint: str = Field(min_length=1)
    unresolved_public_symbols: tuple[str, ...]
    blocked_public_call_signature: str | None
    correct_tool_exposed: Literal[False] = False
    correct_node_exposed: Literal[False] = False
    correct_operator_exposed: Literal[False] = False
    correct_operand_exposed: Literal[False] = False
    correct_evidence_exposed: Literal[False] = False
    exact_argument_values_retained: Literal[False] = False
    job_terminal: Literal[False] = False
    semantic_recovery_available: bool
    schema_version: Literal["prospective_semantic_rejection_observation.v1"] = (
        SEMANTIC_REJECTION_VERSION
    )

    @model_validator(mode="after")
    def validate_rejection(self) -> PublicSemanticRejectionObservation:
        _reject_private_keys(self.model_dump(mode="json", exclude={"rejection_id"}))
        if self.rejection_id != _identity(
            self, "rejection_id", "prospective_semantic_rejection_observation:"
        ):
            raise ValueError("semantic rejection identity changed")
        return self


class SemanticActionState(FrozenModel):
    state_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    tool_grammars: tuple[PublicToolGrammar, ...] = Field(min_length=1)
    variable_affordances: tuple[PublicVariableAffordance, ...]
    source_references: tuple[PublicSourceReference, ...]
    document_references: tuple[PublicDocumentReference, ...]
    operation_frontier: tuple[PublicOperationFrontier, ...]
    acquisition_history: tuple[PublicAcquisitionEvent, ...]
    active_blocked_public_calls: tuple[ActiveBlockedPublicCall, ...]
    blocked_actions: tuple[BlockedCanonicalAction, ...]
    action_candidates: tuple[CanonicalPublicAction, ...] = Field(min_length=1)
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    unresolved_symbols: tuple[str, ...]
    terminal_operation_ref: str | None
    terminal_verification_completed: bool
    final_answer_allowed: bool
    visible_candidate_set_equals_validator_acceptance_set: Literal[True] = True
    acceptance_uses_only_state_and_proposal: Literal[True] = True
    stage_two_semantic_choice_or_repair: Literal[False] = False
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["prospective_semantic_action_state.v1"] = SEMANTIC_ACTION_STATE_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> SemanticActionState:
        if len(self.semantic_rejections) > SEMANTIC_RECOVERY_LIMIT:
            raise ValueError("semantic recovery bound exceeded")
        source_ids = tuple(item.reference_id for item in self.source_references)
        document_ids = tuple(item.reference_id for item in self.document_references)
        frontier_ids = tuple(item.frontier_id for item in self.operation_frontier)
        candidate_ids = tuple(item.action_id for item in self.action_candidates)
        blocked_ids = tuple(item.action_id for item in self.blocked_actions)
        for values, label in (
            (source_ids, "source references"),
            (document_ids, "document references"),
            (frontier_ids, "Operation frontier"),
            (candidate_ids, "action candidates"),
            (blocked_ids, "blocked actions"),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(f"public {label} are not canonical and unique")
        if set(candidate_ids) & set(blocked_ids):
            raise ValueError("blocked action remains model selectable")
        executable_nodes = {
            item.node_id for item in self.operation_frontier if item.frontier_status == "executable"
        }
        terminal_verifiable = any(
            item.frontier_status == "terminal_verifiable" for item in self.operation_frontier
        )
        for candidate in self.action_candidates:
            if (
                candidate.decision_kind == "execute_public_operation"
                and candidate.node_id not in executable_nodes
            ):
                raise ValueError("non-executable Operation became selectable")
            if candidate.decision_kind == "verify_terminal_operation" and not terminal_verifiable:
                raise ValueError("terminal verification became selectable in the wrong state")
            if candidate.decision_kind == "emit_final_answer" and not self.final_answer_allowed:
                raise ValueError("final answer became selectable before readiness")
        signatures = tuple(item.public_call_signature for item in self.active_blocked_public_calls)
        if signatures != tuple(sorted(set(signatures))):
            raise ValueError("active blocked-call signatures are not canonical and unique")
        _reject_private_keys(self.model_dump(mode="json", exclude={"state_id"}))
        if self.state_id != _identity(self, "state_id", "prospective_semantic_action_state:"):
            raise ValueError("semantic action-state identity changed")
        return self


class CanonicalActionProposal(FrozenModel):
    proposal_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    protocol: Literal["prospective_semantic_action_selection.v1"] = SEMANTIC_ACTION_PROTOCOL_VERSION
    model_selected_complete_action_id: Literal[True] = True
    schema_version: Literal["prospective_canonical_action_proposal.v1"] = CANONICAL_PROPOSAL_VERSION

    @model_validator(mode="after")
    def validate_proposal(self) -> CanonicalActionProposal:
        if self.proposal_id != _identity(
            self, "proposal_id", "prospective_canonical_action_proposal:"
        ):
            raise ValueError("canonical action-proposal identity changed")
        return self


class CanonicalActionCommit(FrozenModel):
    commit_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    action: Literal["call_tool", "emit_final"]
    call: AgentToolCall | None
    reversible_compilation_passed: Literal[True] = True
    compiler_selected_tool: Literal[False] = False
    compiler_selected_node: Literal[False] = False
    compiler_selected_operator: Literal[False] = False
    compiler_selected_operand: Literal[False] = False
    compiler_selected_evidence: Literal[False] = False
    compiler_repaired_semantics: Literal[False] = False
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["prospective_canonical_action_commit.v1"] = CANONICAL_COMMIT_VERSION

    @model_validator(mode="after")
    def validate_commit(self) -> CanonicalActionCommit:
        if (self.action == "call_tool") != (self.call is not None):
            raise ValueError("canonical Commit action and call differ")
        if self.commit_id != _identity(self, "commit_id", "prospective_canonical_action_commit:"):
            raise ValueError("canonical action-Commit identity changed")
        return self


class SemanticActionSelectionResult(FrozenModel):
    result_id: str = Field(min_length=1)
    status: Literal["committed", "rejected"]
    commit: CanonicalActionCommit | None
    rejection: PublicSemanticRejectionObservation | None
    abi_rescue_consumed: Literal[False] = False
    semantic_recovery_consumed: bool
    job_terminal: bool

    @model_validator(mode="after")
    def validate_result(self) -> SemanticActionSelectionResult:
        if self.status == "committed":
            if self.commit is None or self.rejection is not None or self.job_terminal:
                raise ValueError("committed semantic result is malformed")
        elif self.rejection is None or self.commit is not None or self.job_terminal:
            raise ValueError("rejected semantic result is not a neutral continuation")
        if self.result_id != _identity(
            self, "result_id", "prospective_semantic_action_selection_result:"
        ):
            raise ValueError("semantic action-selection result identity changed")
        return self


class RecoveryChannelAccounting(FrozenModel):
    abi_rescue_count: int = Field(ge=0, le=ABI_RESCUE_LIMIT)
    semantic_recovery_count: int = Field(ge=0, le=SEMANTIC_RECOVERY_LIMIT)
    abi_rescue_handles_semantic_rejection: Literal[False] = False
    semantic_recovery_handles_abi_failure: Literal[False] = False
    counters_are_independent: Literal[True] = True


def _make_source_reference(**values: Any) -> PublicSourceReference:
    provisional = PublicSourceReference.model_construct(reference_id="pending", **values)
    return PublicSourceReference(
        reference_id=_identity(provisional, "reference_id", "prospective_public_source_reference:"),
        **values,
    )


def _make_document_reference(**values: Any) -> PublicDocumentReference:
    provisional = PublicDocumentReference.model_construct(reference_id="pending", **values)
    return PublicDocumentReference(
        reference_id=_identity(
            provisional, "reference_id", "prospective_public_document_reference:"
        ),
        **values,
    )


def _make_frontier(**values: Any) -> PublicOperationFrontier:
    provisional = PublicOperationFrontier.model_construct(frontier_id="pending", **values)
    return PublicOperationFrontier(
        frontier_id=_identity(provisional, "frontier_id", "prospective_public_operation_frontier:"),
        **values,
    )


def _make_action(**values: Any) -> CanonicalPublicAction:
    provisional = CanonicalPublicAction.model_construct(action_id="pending", **values)
    return CanonicalPublicAction(
        action_id=_identity(provisional, "action_id", "prospective_canonical_public_action:"),
        **values,
    )


def make_canonical_action_proposal(
    *,
    state_id: str,
    action_id: str,
    decision_kind: DecisionKind,
) -> CanonicalActionProposal:
    provisional = CanonicalActionProposal.model_construct(
        proposal_id="pending",
        state_id=state_id,
        action_id=action_id,
        decision_kind=decision_kind,
    )
    return CanonicalActionProposal(
        proposal_id=_identity(
            provisional,
            "proposal_id",
            "prospective_canonical_action_proposal:",
        ),
        state_id=state_id,
        action_id=action_id,
        decision_kind=decision_kind,
    )


def _load_contracts(
    task: TaskPublicSpec,
) -> tuple[PublicOperationContractView, PublicTerminalVerificationTargetView]:
    guidance = task.metadata.get("agent_contract_guidance")
    if not isinstance(guidance, Mapping):
        raise ValueError("semantic action protocol requires public Agent guidance")
    raw_operation = guidance.get("public_operation_execution_contract")
    raw_target = guidance.get("public_terminal_verification_target")
    if not isinstance(raw_operation, Mapping) or not isinstance(raw_target, Mapping):
        raise ValueError("semantic action protocol requires public Operation contracts")
    return (
        PublicOperationContractView.model_validate(raw_operation),
        PublicTerminalVerificationTargetView.model_validate(raw_target),
    )


def _public_call_signature(tool_id: str, arguments: Mapping[str, Any]) -> str:
    return canonical_hash(
        {"tool_id": tool_id, "arguments": dict(arguments)},
        prefix="prospective_public_call_signature:",
    )


def _acquisition_arguments(
    mode: AcquisitionMode,
    record: Mapping[str, Any] | None,
    *,
    public_locator: str | None = None,
) -> dict[str, Any]:
    if mode == "open_public_document":
        if not public_locator:
            raise ValueError("public document recipe lacks a locator")
        return {"public_locator": public_locator}
    if record is None:
        raise ValueError("public acquisition recipe lacks a semantic record")
    subject = record.get("subject_name") or record.get("subject_id")
    subject_id = record.get("subject_id") or subject
    metric = record.get("metric")
    period = record.get("period")
    source_id = record.get("source_id")
    if not all(
        isinstance(item, str) and item for item in (subject, subject_id, metric, period, source_id)
    ):
        raise ValueError("public acquisition semantic record is incomplete")
    if mode == "search_public_record":
        return {
            "limit": SEARCH_RESULT_LIMIT,
            "period_labels": [period],
            "query": f"{subject} {metric} {period}",
            "source_filters": [source_id],
            "subject_aliases": [subject_id],
        }
    filters: dict[str, Any]
    if mode == "query_source_scoped":
        filters = {"source_id": source_id}
    else:
        filter_fields = (
            "currency",
            "definition_id",
            "frequency",
            "source_authority",
            "source_id",
            "subject_type",
            "time_basis",
            "unit",
        )
        filters = {key: record.get(key) for key in filter_fields}
    return {
        "metric_alias": metric,
        "period_label": period,
        "public_filters": filters,
        "subject_alias": subject,
    }


def _semantic_record_from_result(value: Mapping[str, Any]) -> dict[str, Any] | None:
    locator = value.get("public_locator")
    subject = value.get("subject")
    metric = value.get("metric")
    source = value.get("source")
    period = value.get("period")
    if (
        not isinstance(locator, str)
        or not isinstance(subject, Mapping)
        or not isinstance(metric, Mapping)
        or not isinstance(source, Mapping)
        or not isinstance(period, str)
    ):
        return None
    return {
        "subject_id": subject.get("subject_id"),
        "subject_name": subject.get("name"),
        "subject_type": subject.get("type"),
        "metric": metric.get("predicate"),
        "definition_id": metric.get("definition_id"),
        "period": period,
        "source_id": source.get("source_id"),
        "source_authority": source.get("authority"),
    }


def _walk_document_records(value: Any) -> tuple[tuple[str, dict[str, Any]], ...]:
    output: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, Mapping):
        record = _semantic_record_from_result(value)
        if record is not None:
            output.append((str(value["public_locator"]), record))
        for item in value.values():
            output.extend(_walk_document_records(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            output.extend(_walk_document_records(item))
    return tuple(output)


def _record_matches(
    variable_record: Mapping[str, Any],
    observed_record: Mapping[str, Any],
) -> bool:
    comparable = (
        "subject_id",
        "subject_name",
        "metric",
        "definition_id",
        "period",
        "source_id",
        "source_authority",
    )
    return all(
        observed_record.get(key) is None or variable_record.get(key) == observed_record.get(key)
        for key in comparable
    )


def _document_references(
    affordances: tuple[PublicVariableAffordance, ...],
    observations: tuple[AgentToolObservation, ...],
) -> tuple[PublicDocumentReference, ...]:
    values: dict[str, PublicDocumentReference] = {}
    for observation in observations:
        if observation.status != "succeeded":
            continue
        for locator, record in _walk_document_records(observation.result):
            matching = tuple(
                sorted(
                    item.symbol
                    for item in affordances
                    if _record_matches(item.public_record, record)
                )
            )
            if not matching:
                continue
            reference = _make_document_reference(
                public_locator=locator,
                matching_source_symbols=matching,
                semantic_record=record,
            )
            values[reference.reference_id] = reference
    return tuple(values[key] for key in sorted(values))


def _source_references(old_state: Any) -> tuple[PublicSourceReference, ...]:
    output = []
    for item in old_state.resolved_bindings:
        output.append(
            _make_source_reference(
                source_symbol=item.source_symbol,
                reference_kind=item.reference_kind,
                evidence_id=item.evidence_id,
                operation_ref=item.operation_ref,
            )
        )
    return tuple(sorted(output, key=lambda item: item.reference_id))


def _operation_frontier(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    source_references: tuple[PublicSourceReference, ...],
) -> tuple[PublicOperationFrontier, ...]:
    operation, _ = _load_contracts(task)
    progress = public_operation_progress(task, observations)
    if progress is None:
        raise ValueError("public Operation progress is unavailable")
    completed = {
        str(key): str(value) for key, value in progress["completed_node_operation_refs"].items()
    }
    references = {item.source_symbol: item for item in source_references}
    variable_symbols = {item.symbol for item in operation.variables}
    rows = []
    for node in operation.nodes:
        slots = tuple(
            PublicOperandSlot(
                position=index,
                source_symbol=item.source_symbol,
                reference_kind=(
                    "public_evidence"
                    if item.source_symbol in variable_symbols
                    else "public_operation"
                ),
                selector=item.selector,
                serialized_reference_fields=(
                    ("evidence_id",)
                    if item.source_symbol in variable_symbols
                    else (
                        ("operation_ref", "selector")
                        if item.selector is not None
                        else ("operation_ref",)
                    )
                ),
            )
            for index, item in enumerate(node.inputs)
        )
        missing_dependencies = tuple(
            sorted(item for item in node.dependency_node_ids if item not in completed)
        )
        unresolved = tuple(
            item.source_symbol for item in node.inputs if item.source_symbol not in references
        )
        if node.node_id in completed:
            if not node.terminal or progress["verification_after_terminal_completed"]:
                continue
            status: FrontierStatus = "terminal_verifiable"
        elif missing_dependencies:
            status = "blocked_dependencies"
        elif unresolved:
            status = "dependency_ready"
        else:
            status = "executable"
        rows.append(
            _make_frontier(
                node_id=node.node_id,
                frontier_status=status,
                node_kind=node.node_kind,
                semantic_role=node.semantic_role,
                terminal=node.terminal,
                tool_id=node.tool_id,
                dependency_node_ids=node.dependency_node_ids,
                missing_dependency_node_ids=missing_dependencies,
                operand_slots=slots,
                unresolved_source_symbols=unresolved,
                source_reference_ids=tuple(
                    references[item.source_symbol].reference_id
                    for item in node.inputs
                    if item.source_symbol in references
                ),
                allowed_operator_ids=node.allowed_operator_ids,
                operator_choice_mode=node.operator_choice_mode,
                operator_selection_rule=node.operator_selection_rule,
                operator_output_schemas=dict(node.operator_output_schemas),
                required_output_schema=node.required_output_schema,
                fixed_parameters=dict(node.parameters),
                normalization_target=(
                    dict(node.normalization_target)
                    if node.normalization_target is not None
                    else None
                ),
            )
        )
    return tuple(sorted(rows, key=lambda item: item.frontier_id))


def _acquisition_event(
    observation: AgentToolObservation,
    affordances: tuple[PublicVariableAffordance, ...],
    documents: tuple[PublicDocumentReference, ...],
) -> PublicAcquisitionEvent | None:
    mode: AcquisitionMode | None = None
    targets: tuple[str, ...] = ()
    for candidate_mode in (
        "search_public_record",
        "query_source_scoped",
        "query_fully_qualified",
    ):
        for affordance in affordances:
            tool_id = (
                "search_archive"
                if candidate_mode == "search_public_record"
                else "query_structured_fact"
            )
            if observation.call.tool_id != tool_id:
                continue
            if observation.call.arguments == _acquisition_arguments(
                candidate_mode, affordance.public_record
            ):
                mode = candidate_mode
                targets = (affordance.symbol,)
                break
        if mode is not None:
            break
    if mode is None and observation.call.tool_id == "open_document":
        locator = observation.call.arguments.get("public_locator")
        matches = tuple(item for item in documents if item.public_locator == locator)
        if matches:
            mode = "open_public_document"
            targets = tuple(
                sorted({symbol for item in matches for symbol in item.matching_source_symbols})
            )
    if mode is None and observation.call.tool_id not in {
        "search_archive",
        "query_structured_fact",
        "open_document",
    }:
        return None
    return PublicAcquisitionEvent(
        call_index=observation.call.call_index,
        tool_id=observation.call.tool_id,
        acquisition_mode=mode,
        target_source_symbols=targets,
        status=observation.status,
        error_category=observation.error_code,
        public_call_signature=_public_call_signature(
            observation.call.tool_id, observation.call.arguments
        ),
    )


def _base_action_candidates(
    *,
    old_state: Any,
    source_references: tuple[PublicSourceReference, ...],
    document_references: tuple[PublicDocumentReference, ...],
    frontier: tuple[PublicOperationFrontier, ...],
    verification_tool_id: str,
) -> tuple[CanonicalPublicAction, ...]:
    grammar_ids = {item.tool_id for item in old_state.tool_grammars}
    unresolved = set(old_state.unresolved_symbols)
    actions: dict[str, CanonicalPublicAction] = {}
    for affordance in old_state.variable_affordances:
        if affordance.symbol not in unresolved:
            continue
        if "search_archive" in grammar_ids:
            action = _make_action(
                decision_kind="acquire_public_input",
                tool_id="search_archive",
                target_source_symbols=(affordance.symbol,),
                acquisition_mode="search_public_record",
                acquisition_record=dict(affordance.public_record),
                wire_argument_fields=(
                    "limit",
                    "period_labels",
                    "query",
                    "source_filters",
                    "subject_aliases",
                ),
            )
            actions[action.action_id] = action
        if "query_structured_fact" in affordance.acquisition_tool_ids:
            for mode in ("query_source_scoped", "query_fully_qualified"):
                action = _make_action(
                    decision_kind="acquire_public_input",
                    tool_id="query_structured_fact",
                    target_source_symbols=(affordance.symbol,),
                    acquisition_mode=mode,
                    acquisition_record=dict(affordance.public_record),
                    wire_argument_fields=(
                        "metric_alias",
                        "period_label",
                        "public_filters",
                        "subject_alias",
                    ),
                )
                actions[action.action_id] = action
        if "open_document" in affordance.acquisition_tool_ids:
            for document in document_references:
                if affordance.symbol not in document.matching_source_symbols:
                    continue
                action = _make_action(
                    decision_kind="acquire_public_input",
                    tool_id="open_document",
                    target_source_symbols=(affordance.symbol,),
                    acquisition_mode="open_public_document",
                    document_reference_id=document.reference_id,
                    wire_argument_fields=("public_locator",),
                )
                actions[action.action_id] = action
    for item in frontier:
        if item.frontier_status != "executable":
            continue
        operators: tuple[str | None, ...] = (
            tuple(item.allowed_operator_ids) if item.allowed_operator_ids else (None,)
        )
        for operator_id in operators:
            action = _make_action(
                decision_kind="execute_public_operation",
                tool_id=item.tool_id,
                node_id=item.node_id,
                operator_id=operator_id,
                source_reference_ids=item.source_reference_ids,
                wire_argument_fields=(
                    ("evidence_ids", "target_definition")
                    if item.node_kind == "normalization"
                    else ("operands", "operator", "parameters")
                ),
            )
            actions[action.action_id] = action
    terminal_verifiable = any(item.frontier_status == "terminal_verifiable" for item in frontier)
    evidence_references = tuple(
        sorted(
            (item for item in source_references if item.reference_kind == "public_evidence"),
            key=lambda item: str(item.evidence_id),
        )
    )
    if terminal_verifiable:
        if len(evidence_references) > 8:
            raise ValueError("public verification candidate set exceeds its static bound")
        for count in range(1, len(evidence_references) + 1):
            for selected in combinations(evidence_references, count):
                action = _make_action(
                    decision_kind="verify_terminal_operation",
                    tool_id=verification_tool_id,
                    evidence_reference_ids=tuple(item.reference_id for item in selected),
                    wire_argument_fields=("claim_or_result", "evidence_ids"),
                )
                actions[action.action_id] = action
    if old_state.final_answer_allowed:
        action = _make_action(decision_kind="emit_final_answer")
        actions[action.action_id] = action
    return tuple(actions[key] for key in sorted(actions))


def _compile_action_call(
    state: SemanticActionState,
    candidate: CanonicalPublicAction,
    *,
    call_index: int,
) -> AgentToolCall | None:
    if candidate.decision_kind == "emit_final_answer":
        return None
    if candidate.decision_kind == "acquire_public_input":
        locator = None
        if candidate.document_reference_id is not None:
            documents = {item.reference_id: item for item in state.document_references}
            document = documents.get(candidate.document_reference_id)
            if document is None:
                raise ValueError("canonical action selects an unavailable document reference")
            locator = document.public_locator
        arguments = _acquisition_arguments(
            candidate.acquisition_mode or "search_public_record",
            candidate.acquisition_record,
            public_locator=locator,
        )
    elif candidate.decision_kind == "execute_public_operation":
        frontiers = {
            item.node_id: item
            for item in state.operation_frontier
            if item.frontier_status == "executable"
        }
        frontier = frontiers.get(str(candidate.node_id))
        if frontier is None or frontier.tool_id != candidate.tool_id:
            raise ValueError("canonical action selects a non-executable Operation")
        if candidate.source_reference_ids != frontier.source_reference_ids:
            raise ValueError("canonical action changes public operand references")
        references = {item.reference_id: item for item in state.source_references}
        operands = []
        for slot, reference_id in zip(
            frontier.operand_slots, candidate.source_reference_ids, strict=True
        ):
            reference = references.get(reference_id)
            if reference is None or reference.source_symbol != slot.source_symbol:
                raise ValueError("canonical action source reference changed")
            if reference.reference_kind == "public_evidence":
                operands.append({"evidence_id": reference.evidence_id})
            else:
                operand: dict[str, Any] = {"operation_ref": reference.operation_ref}
                if slot.selector is not None:
                    operand["selector"] = slot.selector
                operands.append(operand)
        if frontier.node_kind == "normalization":
            if candidate.operator_id is not None:
                raise ValueError("normalization candidate unexpectedly selects an operator")
            arguments = {
                "evidence_ids": [item["evidence_id"] for item in operands],
                "target_definition": dict(frontier.normalization_target or {}),
            }
        else:
            if candidate.operator_id not in set(frontier.allowed_operator_ids):
                raise ValueError("canonical action selects an unavailable operator")
            arguments = {
                "operator": candidate.operator_id,
                "operands": operands,
                "parameters": dict(frontier.fixed_parameters),
            }
    else:
        if not state.terminal_operation_ref or state.terminal_verification_completed:
            raise ValueError("canonical verification action is not currently available")
        references = {item.reference_id: item for item in state.source_references}
        selected = [references[item] for item in candidate.evidence_reference_ids]
        if any(item.reference_kind != "public_evidence" for item in selected):
            raise ValueError("canonical verification selects a non-Evidence reference")
        arguments = {
            "claim_or_result": {"operation_ref": state.terminal_operation_ref},
            "evidence_ids": [item.evidence_id for item in selected],
        }
    grammars = {item.tool_id: item for item in state.tool_grammars}
    grammar = grammars.get(str(candidate.tool_id))
    if grammar is None:
        raise ValueError("canonical action selects a tool outside the public state")
    missing = set(grammar.required_input_fields) - set(arguments)
    extra = set(arguments) - set(grammar.input_contract)
    if missing or (extra and not grammar.allow_additional_input_fields):
        raise ValueError("deterministic canonical compilation violates public tool grammar")
    if tuple(sorted(arguments)) != candidate.wire_argument_fields:
        raise ValueError("canonical action wire-field disclosure changed")
    return AgentToolCall(
        call_index=call_index,
        tool_id=str(candidate.tool_id),
        arguments=arguments,
    )


def _blocked_calls(
    observations: tuple[AgentToolObservation, ...],
    acquisition_history: tuple[PublicAcquisitionEvent, ...],
    base_candidates: tuple[CanonicalPublicAction, ...],
    provisional_state: SemanticActionState,
) -> tuple[
    tuple[ActiveBlockedPublicCall, ...],
    tuple[BlockedCanonicalAction, ...],
    tuple[CanonicalPublicAction, ...],
]:
    latest_by_signature: dict[str, AgentToolObservation] = {}
    for observation in observations:
        if observation.status == "failed" and observation.error_code:
            signature = _public_call_signature(observation.call.tool_id, observation.call.arguments)
            latest_by_signature[signature] = observation
    candidate_signatures: dict[str, str] = {}
    for candidate in base_candidates:
        call = _compile_action_call(provisional_state, candidate, call_index=1)
        if call is not None:
            candidate_signatures[candidate.action_id] = _public_call_signature(
                call.tool_id, call.arguments
            )
    events = {item.public_call_signature: item for item in acquisition_history}
    blocked_rows: list[ActiveBlockedPublicCall] = []
    selectable: list[CanonicalPublicAction] = []
    blocked_action_rows: list[BlockedCanonicalAction] = []
    for candidate in base_candidates:
        candidate_signature = candidate_signatures.get(candidate.action_id)
        failed_observation = (
            latest_by_signature.get(candidate_signature)
            if candidate_signature is not None
            else None
        )
        if failed_observation is None:
            selectable.append(candidate)
            continue
        blocked_action_rows.append(
            BlockedCanonicalAction(
                action_id=candidate.action_id,
                decision_kind=candidate.decision_kind,
                selected_tool_id=candidate.tool_id,
                acquisition_mode=candidate.acquisition_mode,
                target_source_symbols=candidate.target_source_symbols,
                error_category=str(failed_observation.error_code),
                blocked_public_call_signature=str(candidate_signature),
            )
        )
    action_by_signature = {
        signature: action_id for action_id, signature in candidate_signatures.items()
    }
    for signature in sorted(latest_by_signature):
        observation = latest_by_signature[signature]
        event = events.get(signature)
        blocked_rows.append(
            ActiveBlockedPublicCall(
                public_call_signature=signature,
                failed_tool_id=observation.call.tool_id,
                error_category=str(observation.error_code),
                latest_call_index=observation.call.call_index,
                action_id=action_by_signature.get(signature),
                acquisition_mode=event.acquisition_mode if event is not None else None,
                target_source_symbols=(event.target_source_symbols if event is not None else ()),
            )
        )
    return (
        tuple(blocked_rows),
        tuple(sorted(blocked_action_rows, key=lambda item: item.action_id)),
        tuple(sorted(selectable, key=lambda item: item.action_id)),
    )


def build_semantic_action_state(
    task: TaskPublicSpec,
    environment: AgentToolEnvironmentManifest,
    observations: tuple[AgentToolObservation, ...],
    *,
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...] = (),
    stage_tool_ids: frozenset[str] | None = None,
) -> SemanticActionState:
    if len(semantic_rejections) > SEMANTIC_RECOVERY_LIMIT:
        raise ValueError("semantic recovery bound exceeded before state construction")
    old_state = build_public_action_state(
        task,
        environment,
        observations,
        stage_tool_ids=stage_tool_ids,
    )
    _, verification = _load_contracts(task)
    sources = _source_references(old_state)
    documents = _document_references(old_state.variable_affordances, observations)
    frontier = _operation_frontier(task, observations, sources)
    history = tuple(
        item
        for observation in observations
        if (item := _acquisition_event(observation, old_state.variable_affordances, documents))
        is not None
    )
    base_candidates = _base_action_candidates(
        old_state=old_state,
        source_references=sources,
        document_references=documents,
        frontier=frontier,
        verification_tool_id=verification.verification_tool_id,
    )
    provisional_values: dict[str, Any] = {
        "task_id": task.task_id,
        "environment_manifest_id": environment.manifest_id,
        "tool_grammars": old_state.tool_grammars,
        "variable_affordances": old_state.variable_affordances,
        "source_references": sources,
        "document_references": documents,
        "operation_frontier": frontier,
        "acquisition_history": history,
        "active_blocked_public_calls": (),
        "blocked_actions": (),
        "action_candidates": base_candidates,
        "semantic_rejections": semantic_rejections,
        "unresolved_symbols": old_state.unresolved_symbols,
        "terminal_operation_ref": old_state.terminal_operation_ref,
        "terminal_verification_completed": old_state.terminal_verification_completed,
        "final_answer_allowed": old_state.final_answer_allowed,
    }
    provisional = SemanticActionState.model_construct(state_id="pending", **provisional_values)
    blocked_calls, blocked_actions, selectable = _blocked_calls(
        observations,
        history,
        base_candidates,
        provisional,
    )
    if not selectable:
        raise ValueError("semantic action state has no selectable public action")
    values = {
        **provisional_values,
        "active_blocked_public_calls": blocked_calls,
        "blocked_actions": blocked_actions,
        "action_candidates": selectable,
    }
    pending = SemanticActionState.model_construct(state_id="pending", **values)
    return SemanticActionState(
        state_id=_identity(pending, "state_id", "prospective_semantic_action_state:"),
        **values,
    )


def accepted_action_ids(state: SemanticActionState) -> tuple[str, ...]:
    """The complete validator acceptance set, derived only from public state."""

    return tuple(item.action_id for item in state.action_candidates)


def decompile_canonical_public_call(
    state: SemanticActionState,
    call: AgentToolCall,
) -> CanonicalActionProposal:
    matches = []
    for candidate in state.action_candidates:
        compiled = _compile_action_call(state, candidate, call_index=call.call_index)
        if compiled == call:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("public call does not map to exactly one canonical action")
    candidate = matches[0]
    return make_canonical_action_proposal(
        state_id=state.state_id,
        action_id=candidate.action_id,
        decision_kind=candidate.decision_kind,
    )


def _make_rejection(
    state: SemanticActionState,
    proposal: CanonicalActionProposal,
    *,
    error_category: RejectionCategory,
    violated_public_constraint: str,
    selected_tool_id: str | None,
    blocked_public_call_signature: str | None,
) -> PublicSemanticRejectionObservation:
    semantic_recovery_available = len(state.semantic_rejections) < SEMANTIC_RECOVERY_LIMIT
    provisional = PublicSemanticRejectionObservation.model_construct(
        rejection_id="pending",
        state_id=state.state_id,
        proposal_id=proposal.proposal_id,
        failed_decision_kind=proposal.decision_kind,
        selected_action_id=proposal.action_id,
        selected_tool_id=selected_tool_id,
        error_category=error_category,
        violated_public_constraint=violated_public_constraint,
        unresolved_public_symbols=state.unresolved_symbols,
        blocked_public_call_signature=blocked_public_call_signature,
        semantic_recovery_available=semantic_recovery_available,
    )
    return PublicSemanticRejectionObservation(
        rejection_id=_identity(
            provisional,
            "rejection_id",
            "prospective_semantic_rejection_observation:",
        ),
        state_id=state.state_id,
        proposal_id=proposal.proposal_id,
        failed_decision_kind=proposal.decision_kind,
        selected_action_id=proposal.action_id,
        selected_tool_id=selected_tool_id,
        error_category=error_category,
        violated_public_constraint=violated_public_constraint,
        unresolved_public_symbols=state.unresolved_symbols,
        blocked_public_call_signature=blocked_public_call_signature,
        semantic_recovery_available=semantic_recovery_available,
    )


def evaluate_canonical_action_proposal(
    state: SemanticActionState,
    proposal: CanonicalActionProposal,
    *,
    call_index: int,
) -> SemanticActionSelectionResult:
    candidates = {item.action_id: item for item in state.action_candidates}
    blocked = {item.action_id: item for item in state.blocked_actions}
    candidate = candidates.get(proposal.action_id)
    blocked_action = blocked.get(proposal.action_id)
    rejection: PublicSemanticRejectionObservation | None = None
    if proposal.state_id != state.state_id:
        rejection = _make_rejection(
            state,
            proposal,
            error_category="stale_public_state",
            violated_public_constraint="proposal_state_id_must_equal_current_public_state_id",
            selected_tool_id=(
                candidate.tool_id
                if candidate is not None
                else blocked_action.selected_tool_id
                if blocked_action is not None
                else None
            ),
            blocked_public_call_signature=None,
        )
    elif blocked_action is not None:
        rejection = _make_rejection(
            state,
            proposal,
            error_category="blocked_identical_public_call",
            violated_public_constraint=blocked_action.violated_public_constraint,
            selected_tool_id=blocked_action.selected_tool_id,
            blocked_public_call_signature=blocked_action.blocked_public_call_signature,
        )
    elif candidate is None:
        rejection = _make_rejection(
            state,
            proposal,
            error_category="unknown_or_unselectable_action",
            violated_public_constraint="action_id_must_be_in_visible_candidate_set",
            selected_tool_id=None,
            blocked_public_call_signature=None,
        )
    elif proposal.decision_kind != candidate.decision_kind:
        rejection = _make_rejection(
            state,
            proposal,
            error_category="decision_kind_mismatch",
            violated_public_constraint="decision_kind_must_equal_selected_action_kind",
            selected_tool_id=candidate.tool_id,
            blocked_public_call_signature=None,
        )
    if rejection is not None:
        values: dict[str, Any] = {
            "status": "rejected",
            "commit": None,
            "rejection": rejection,
            "semantic_recovery_consumed": True,
            "job_terminal": False,
        }
        provisional_result = SemanticActionSelectionResult.model_construct(
            result_id="pending", **values
        )
        return SemanticActionSelectionResult(
            result_id=_identity(
                provisional_result,
                "result_id",
                "prospective_semantic_action_selection_result:",
            ),
            **values,
        )
    if candidate is None:
        raise AssertionError("validated canonical action candidate disappeared")
    call = _compile_action_call(state, candidate, call_index=call_index)
    if call is not None:
        recovered = decompile_canonical_public_call(state, call)
        if recovered.action_id != proposal.action_id:
            raise ValueError("canonical call does not reverse to the selected action")
    commit_values: dict[str, Any] = {
        "state_id": state.state_id,
        "proposal_id": proposal.proposal_id,
        "action_id": proposal.action_id,
        "decision_kind": proposal.decision_kind,
        "action": "emit_final" if call is None else "call_tool",
        "call": call,
    }
    provisional_commit = CanonicalActionCommit.model_construct(commit_id="pending", **commit_values)
    commit = CanonicalActionCommit(
        commit_id=_identity(
            provisional_commit, "commit_id", "prospective_canonical_action_commit:"
        ),
        **commit_values,
    )
    result_values: dict[str, Any] = {
        "status": "committed",
        "commit": commit,
        "rejection": None,
        "semantic_recovery_consumed": False,
        "job_terminal": False,
    }
    provisional_result = SemanticActionSelectionResult.model_construct(
        result_id="pending", **result_values
    )
    return SemanticActionSelectionResult(
        result_id=_identity(
            provisional_result,
            "result_id",
            "prospective_semantic_action_selection_result:",
        ),
        **result_values,
    )


def render_semantic_action_prompt(
    *,
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
) -> str:
    payload = {
        "protocol": SEMANTIC_ACTION_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "public_action_state": state.model_dump(mode="json"),
        "response_contract": {
            "semantic_fields": ("state_id", "action_id", "decision_kind", "protocol"),
            "action_id_must_be_selected_from_visible_candidates": True,
            "low_level_tool_arguments_must_not_be_generated": True,
            "outer_response_abi_and_stage_metadata_unchanged_by_this_design": True,
            "private_reasoning_content_must_not_be_returned": True,
        },
    }
    _reject_private_keys(payload)
    return "Select one visible canonical public action as JSON.\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def semantic_action_prompt_payload(
    prompt: str,
) -> tuple[str, str | None, SemanticActionState]:
    prefix, separator, raw_payload = prompt.partition("\n")
    if prefix != "Select one visible canonical public action as JSON." or not separator:
        raise ValueError("semantic action Prompt envelope changed")
    payload = json.loads(raw_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("semantic action Prompt payload must be an object")
    if payload.get("protocol") != SEMANTIC_ACTION_PROTOCOL_VERSION:
        raise ValueError("semantic action Prompt protocol changed")
    instruction = payload.get("instruction")
    path_condition = payload.get("public_path_condition")
    raw_state = payload.get("public_action_state")
    if not isinstance(instruction, str) or not isinstance(raw_state, Mapping):
        raise ValueError("semantic action Prompt omits public instruction or state")
    if path_condition is not None and not isinstance(path_condition, str):
        raise ValueError("semantic action Prompt path condition is malformed")
    _reject_private_keys(payload)
    return instruction, path_condition, SemanticActionState.model_validate(raw_state)


def prompt_only_reference_proposal(prompt: str) -> CanonicalActionProposal:
    """A full-path control that reads only the final serialized Prompt."""

    instruction, path_condition, state = semantic_action_prompt_payload(prompt)
    candidates = tuple(state.action_candidates)
    if state.unresolved_symbols:
        symbol = state.unresolved_symbols[0]
        available = tuple(
            item
            for item in candidates
            if item.decision_kind == "acquire_public_input"
            and item.target_source_symbols == (symbol,)
        )
        if not available:
            raise ValueError("Prompt-only policy has no acquisition candidate")
        by_mode = {item.acquisition_mode: item for item in available}
        blocked_modes = {
            item.acquisition_mode
            for item in state.blocked_actions
            if item.target_source_symbols == (symbol,)
        }
        recovery_required = (
            "first exact selector attempt returns a typed recoverable failure"
            in instruction.casefold()
        )
        route = path_condition or "structured_direct"
        search_observed = any(
            item.acquisition_mode == "search_public_record"
            and symbol in item.target_source_symbols
            and item.status == "succeeded"
            for item in state.acquisition_history
        )
        if "query_source_scoped" in blocked_modes:
            selected = by_mode.get("query_fully_qualified")
        elif (
            recovery_required
            and not any(
                item.error_category == "typed_selector_requires_refinement"
                for item in state.acquisition_history
            )
            and not any(
                item.acquisition_mode
                in {
                    "query_source_scoped",
                    "query_fully_qualified",
                }
                and symbol in item.target_source_symbols
                for item in state.acquisition_history
            )
        ):
            if route != "structured_direct" and not search_observed:
                selected = by_mode.get("search_public_record")
            else:
                selected = by_mode.get("query_source_scoped")
        elif route == "structured_direct":
            selected = by_mode.get("query_fully_qualified")
        elif not search_observed:
            selected = by_mode.get("search_public_record")
        elif route == "search_then_structured":
            selected = by_mode.get("query_fully_qualified")
        else:
            selected = by_mode.get("open_public_document")
        if selected is None:
            raise ValueError("Prompt-only acquisition policy cannot satisfy its public route")
    else:
        executable = tuple(
            item for item in candidates if item.decision_kind == "execute_public_operation"
        )
        verification = tuple(
            item for item in candidates if item.decision_kind == "verify_terminal_operation"
        )
        final = tuple(item for item in candidates if item.decision_kind == "emit_final_answer")
        if executable:
            first_node_id = min(str(item.node_id) for item in executable)
            same_node = tuple(item for item in executable if item.node_id == first_node_id)
            frontier = next(
                item
                for item in state.operation_frontier
                if item.node_id == first_node_id and item.frontier_status == "executable"
            )
            schema_matched = tuple(
                item
                for item in same_node
                if frontier.required_output_schema is not None
                and frontier.operator_output_schemas.get(str(item.operator_id))
                == frontier.required_output_schema
            )
            selected = min(
                schema_matched or same_node,
                key=lambda item: str(item.operator_id),
            )
        elif verification:
            selected = max(verification, key=lambda item: len(item.evidence_reference_ids))
        elif len(final) == 1:
            selected = final[0]
        else:
            raise ValueError("Prompt-only policy has no canonical next action")
    return make_canonical_action_proposal(
        state_id=state.state_id,
        action_id=selected.action_id,
        decision_kind=selected.decision_kind,
    )
