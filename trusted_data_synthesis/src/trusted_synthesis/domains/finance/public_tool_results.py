from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from trusted_synthesis.core.evidence.payloads import EvidencePayload
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolResult

FINANCE_PUBLIC_RESULT_CONTRACT_VERSION = "finance_public_result_contract.v1"


class PublicModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PublicSubject(PublicModel):
    subject_id: str
    name: str
    type: str


class PublicMetric(PublicModel):
    predicate: str
    name: str | None = None
    definition_id: str | None = None


class PublicSource(PublicModel):
    source_id: str
    name: str
    authority: str


class PublicEvidenceSummary(PublicModel):
    evidence_id: str
    public_locator: str
    subject: PublicSubject
    metric: PublicMetric
    period: str | None = None
    source: PublicSource


class PublicFact(PublicEvidenceSummary):
    payload: EvidencePayload
    time_basis: str | None = None
    frequency: str | None = None
    source_locator_hash: str
    provenance_hash: str


class PublicResolution(PublicModel):
    resolved: bool


class PublicResolutionAction(PublicModel):
    tool_id: str
    applicable_when: str


class PublicDependencyOption(PublicModel):
    option_id: str
    tool_id: Literal["query_structured_fact"] = "query_structured_fact"
    subject_alias: str
    metric_alias: str
    period_label: str


class PublicTemporalIdentity(PublicModel):
    label: str
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None


class PublicMeasurementContext(PublicModel):
    unit: str | None = None
    currency: str | None = None


class PublicObservedRecord(PublicModel):
    subject_alias: str
    metric_alias: str
    temporal_identity: PublicTemporalIdentity
    source_id: str
    definition_id: str | None = None
    measurement_context: PublicMeasurementContext


class PublicObservedEvidenceState(PublicModel):
    observed_record: PublicObservedRecord
    required_record: PublicObservedRecord


class PublicRelationState(PublicModel):
    selected_evidence_exists: Literal[True]
    target_record_coverage: Literal["complete"]
    observation_identity_relation: Literal["aligned", "unresolved", "irrelevant"]
    meaning_compatibility_relation: Literal["aligned", "unresolved", "irrelevant"]
    measurement_compatibility_relation: Literal["aligned", "unresolved", "irrelevant"]
    authority_relation: Literal["aligned", "unresolved", "irrelevant"]


class PublicCandidateSubmissionContract(PublicModel):
    selector: tuple[str, ...]
    required_fields: tuple[str, ...]
    localized_field: str
    preserve_fields: tuple[str, ...]
    additional_fields_allowed: bool
    canonical_value_disclosed: bool
    value_source: str


class PublicSuggestedArgumentPatch(PublicModel):
    rule: str | None = None
    current_operation_refs: tuple[str, ...] = ()
    state_activation_phase: str | None = None
    observed_conflict_signal: str | None = None
    observed_evidence_state: PublicObservedEvidenceState | None = None
    public_relation_state: PublicRelationState | None = None
    shared_resolution_policy: str | None = None
    available_resolution_actions: tuple[PublicResolutionAction, ...] = ()
    candidate_submission_contract: PublicCandidateSubmissionContract | None = None
    public_filters: dict[str, str | int | float | bool | None] | None = None
    subject_alias: str | None = None


class PublicOperationOperand(PublicModel):
    evidence_id: str | None = None
    operation_ref: str | None = None
    selector: str | tuple[str, ...] | None = None

    @model_validator(mode="after")
    def validate_operand(self) -> PublicOperationOperand:
        if (self.evidence_id is None) == (self.operation_ref is None):
            raise ValueError("public Operation operand requires exactly one input identity")
        return self


class PublicOperationArgumentPatch(PublicModel):
    operator: str
    operands: tuple[PublicOperationOperand, ...]
    parameters: dict[str, str | int | float | bool | None]


class PublicQueryArguments(PublicModel):
    subject_alias: str
    metric_alias: str
    period_label: str
    public_filters: dict[str, str | int | float | bool | None]


class PublicNormalizeArguments(PublicModel):
    evidence_ids: tuple[str, ...]
    target_definition: dict[str, str | int | float | bool | None]


class PublicToolPrerequisiteAction(PublicModel):
    action: str
    tool_id: str
    arguments: PublicQueryArguments | PublicNormalizeArguments


class PublicSelectionPredicate(PublicModel):
    selector: tuple[str, ...]
    value: str | int | float | bool | None


class PublicSelectionMatch(PublicModel):
    collection_selector: tuple[str, ...]
    equals: tuple[PublicSelectionPredicate, ...]
    evidence_id_selector: tuple[str, ...]


class PublicSelectionBinding(PublicModel):
    metric: str
    period: str
    selection_match: PublicSelectionMatch
    subject: str
    symbol: str


class PublicUnresolvedSelectionInput(PublicModel):
    evidence_id: str | None
    input_ref: str
    public_binding: PublicSelectionBinding
    selection_required: bool
    source: str


class PublicSelectionPrerequisiteAction(PublicModel):
    action: Literal["select_missing_evidence"]
    unresolved_inputs: tuple[PublicUnresolvedSelectionInput, ...]


PublicPrerequisiteAction = PublicToolPrerequisiteAction | PublicSelectionPrerequisiteAction


class PublicRetryContract(PublicModel):
    policy: str
    maximum_identical_replays: int | None = None
    required_next_tools: tuple[str, ...] = ()
    suggested_argument_patch: PublicSuggestedArgumentPatch | PublicOperationArgumentPatch | None = (
        None
    )
    required_prerequisite_action: PublicPrerequisiteAction | None = None
    observed_conflict_dimensions: tuple[str, ...] = ()
    available_resolution_actions: tuple[PublicResolutionAction, ...] = ()
    decision_rule: str | None = None
    observed_conflict_signal: str | None = None
    observed_evidence_state: PublicObservedEvidenceState | None = None
    public_relation_state: PublicRelationState | None = None


class PublicMissingRole(PublicModel):
    role_id: str
    subject_alias: str
    metric_alias: str
    period_label: str


class PublicSearchArguments(PublicModel):
    query: str
    limit: int


class PublicDependencyProbe(PublicModel):
    tool_id: Literal["search_archive"]
    arguments: PublicSearchArguments


class PublicDependencyBranchObservation(PublicModel):
    required_option_id: str
    probe_query_hash: str | None = None
    observation_basis: str


class PublicAdditionalActionAssessment(PublicModel):
    marginal_cost: str | None = None
    evidence_integrity_risk: str | None = None
    remaining_call_budget_fraction: float | None = None
    remaining_token_budget_fraction: float | None = None
    terminal_utility_loss: float | None = None
    decision_rule: str | None = None
    archive_snapshot_sealed: bool | None = None
    maximum_additional_information_gain: float | None = None
    realized_call_budget_debit_fraction: float | None = None
    realized_token_budget_debit_fraction: float | None = None
    additional_action_rejected: bool | None = None


class PublicCompletionState(PublicModel):
    complete: bool
    resolved_role_ids: tuple[str, ...] = ()
    missing_role_ids: tuple[str, ...] = ()
    redundant_action_policy: str | None = None
    redundant_action_cost_applied: bool | None = None
    required_prerequisite_action: PublicPrerequisiteAction | None = None
    resolved_role_count: int | None = None
    missing_role_count: int | None = None
    required_role_count: int | None = None
    missing_role_disclosure: str | None = None
    completeness_rule: str | None = None
    selected_evidence_count: int | None = None
    unresolved_candidate_count: int | None = None
    dependency_rule: str | None = None
    candidate_actions: tuple[PublicDependencyOption, ...] = ()
    dependency_probe: PublicDependencyProbe | None = None
    dependency_branch_observed: bool | None = None
    dependency_branch_observation: PublicDependencyBranchObservation | None = None
    missing_roles: tuple[PublicMissingRole, ...] = ()
    additional_action_assessment: PublicAdditionalActionAssessment | None = None
    terminal_utility_loss: float | None = None
    relative_cost_contract_enforced: bool | None = None
    archive_snapshot_sealed: bool | None = None
    maximum_additional_information_gain: float | None = None
    realized_call_budget_debit_fraction: float | None = None
    realized_token_budget_debit_fraction: float | None = None
    additional_action_rejected: bool | None = None
    sealed_cost_contract_enforced: bool | None = None


class PublicCandidateRepair(PublicModel):
    localized: bool
    repair_verified: bool
    target_field: str | None = None
    submitted_candidate: dict[str, Any] | None = None
    preserve_fields: tuple[str, ...] = ()
    submission_contract: PublicCandidateSubmissionContract | None = None
    canonical_target_value: Any = None
    replay_operation_ref: str | None = None
    semantic_context_verified: bool | None = None


class PublicCompatibilityReport(PublicModel):
    compatible: bool
    mismatches: dict[str, list[Any]]
    candidate_repair: PublicCandidateRepair | None = None


class PublicConflict(PublicModel):
    type: str
    operation_refs: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    missing_role_ids: tuple[str, ...] = ()
    field: str | None = None
    candidate_value: Any = None
    canonical_value: Any = None
    required_preserve_fields: tuple[str, ...] = ()
    mismatches: dict[str, list[Any]] | None = None


class PublicExtensions(PublicModel):
    submechanism_resolution: PublicResolution | None = None
    completion_state: PublicCompletionState | None = None
    dependency_branch_observation: PublicDependencyBranchObservation | None = None


class SearchResultPublic(PublicExtensions):
    matches: tuple[PublicEvidenceSummary, ...]
    query_hash: str
    snapshot_hash: str


class PublicDocumentContent(PublicModel):
    public_locator: str
    section_or_page: str | None = None
    facts: tuple[PublicFact, ...]


class OpenDocumentResultPublic(PublicExtensions):
    content: PublicDocumentContent
    evidence_ids: tuple[str, ...]
    source_locator_hash: str


class StructuredFactResultPublic(PublicExtensions):
    facts: tuple[PublicFact, ...]
    evidence_ids: tuple[str, ...]
    query_hash: str


class PublicCalculation(PublicModel):
    operator: str
    output: Any
    operation_ref: str


class CalculatorResultPublic(PublicExtensions):
    result: PublicCalculation
    operation_hash: str


class PublicNormalizedValue(PublicModel):
    evidence_id: str
    value: str
    unit: str | None = None
    currency: str | None = None
    period: str | None = None


class NormalizeResultPublic(PublicExtensions):
    normalized_values: tuple[PublicNormalizedValue, ...]
    compatibility_report: PublicCompatibilityReport
    policy_hash: str


class CrossCheckResultPublic(PublicExtensions):
    verified: bool
    support: tuple[str, ...]
    conflicts: tuple[PublicConflict, ...]
    verification_hash: str
    candidate_repair: PublicCandidateRepair | None = None
    retry_contract: PublicRetryContract | None = None


class FailedResultPublic(PublicModel):
    retry_contract: PublicRetryContract | None = None
    completion_state: PublicCompletionState | None = None
    verified: bool | None = None
    support: tuple[str, ...] = ()
    conflicts: tuple[PublicConflict, ...] = ()
    verification_hash: str | None = None
    candidate_repair: PublicCandidateRepair | None = None
    submechanism_resolution: PublicResolution | None = None


SUCCESS_MODELS: dict[str, type[PublicModel]] = {
    "search_archive": SearchResultPublic,
    "open_document": OpenDocumentResultPublic,
    "query_structured_fact": StructuredFactResultPublic,
    "calculator": CalculatorResultPublic,
    "normalize_metric_unit_period": NormalizeResultPublic,
    "cross_check_evidence": CrossCheckResultPublic,
}


def validate_finance_public_tool_result(tool_id: str, result: AgentToolResult) -> None:
    """Fail closed unless the model-visible Finance payload matches a frozen public schema."""

    model = SUCCESS_MODELS.get(tool_id) if result.status == "succeeded" else FailedResultPublic
    if model is None:
        raise ValueError(f"Finance public result contract has no tool schema: {tool_id}")
    try:
        model.model_validate(result.result)
    except ValidationError as exc:
        raise ValueError(f"Finance public result contract rejected {tool_id}: {exc}") from exc


def finance_public_result_contract_manifest() -> dict[str, Any]:
    schemas = {
        tool_id: canonical_hash(model.model_json_schema(), prefix="finance_public_schema:")
        for tool_id, model in sorted(SUCCESS_MODELS.items())
    }
    schemas["failed_result"] = canonical_hash(
        FailedResultPublic.model_json_schema(), prefix="finance_public_schema:"
    )
    payload = {
        "schema_version": FINANCE_PUBLIC_RESULT_CONTRACT_VERSION,
        "success_schema_hashes": schemas,
        "all_nested_models_extra_forbid": True,
        "host_side_channel_excluded": True,
    }
    return {
        **payload,
        "manifest_hash": canonical_hash(payload, prefix="finance_public_result_contract:"),
    }
