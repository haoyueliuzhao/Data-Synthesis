from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE: Final = "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_only"
DECISION: Final = (
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "passed_independent_audit_required"
)
NEXT_STAGE: Final = (
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "independent_audit_only"
)

EXTERNAL_REVIEW_SHA256: Final = "7ee383ced0b883c04e6187160c3fe11f7d6bbc40ad79263320d47a6c5825aa23"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 30_082
OPERATOR_DIRECTIVE: Final = "参照审计报告，逐一修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "a3ce5b0198c82767a5635e440b44e4f1978b50798db08132eb007f1efa865abb"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 33

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
PREDECESSOR_SOURCE_COMMIT: Final = "f084a4ff503935797acf2bc873943c6cd8670529"
PREDECESSOR_SOURCE_TREE: Final = "40b8b712da76c4100524160bd79be1bc30248e9c"
PREDECESSOR_FILE_COUNT: Final = 24
PREDECESSOR_TOTAL_BYTES: Final = 784_989
PREDECESSOR_MEMBER_COUNT: Final = 23
PREDECESSOR_MEMBER_BYTES: Final = 781_444
PREDECESSOR_MANIFEST_BYTES: Final = 3_545
PREDECESSOR_MANIFEST_SHA256: Final = (
    "8a86354d574311631e0b38faa6acb79d13602291d4bcac350af0edfdb92b83c2"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_archive_parameter_space_artifact_manifest:"
    "29dbf80f462d7dbf079df99e77d44dc5739b2a9ece8525356b43dc9ddc0f63b7"
)
PREDECESSOR_ROOT_ID: Final = (
    "qa_archive_parameter_space_artifact_root:"
    "b24d054bbf6cd5275675636f7a3f69fac127b2ab1a42483911c384c1cae60f98"
)
PREDECESSOR_REPORT_ID: Final = (
    "qa_archive_parameter_space_report:"
    "7669d8ba86b6bd13aabc2eed3eb332cf31b562fdc5ad30a84cbbc823bfe448d9"
)
PREDECESSOR_GATE_ID: Final = (
    "qa_archive_parameter_space_gate:"
    "3ceda0d6f3c8c003fb0aaf0413088ad53453cb3e13b2ad148275752c93c42a17"
)
PREDECESSOR_DECISION_ID: Final = (
    "qa_archive_parameter_space_decision:"
    "71454455586f36d36a1bd6edfddd2ce2cd00cf078caa45d92a382ec14b143ab6"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "qa_archive_parameter_space_transition:"
    "959194d0075ca272e53bba5c6c9e7aa1e3dc2e475f0399cc7584822ec259f0dc"
)

SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/contracts.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/preflight.py",
)

CONTRACT_NAMES: Final = (
    "AnswerOracleProgramBindingContract",
    "CriticalDecisionGraphContract",
    "PublicReasoningStateContract",
    "ReasoningActionEnvelopeContract",
    "ObservationUpdateContract",
    "ReasoningTrajectoryContract",
    "ReasoningValidityContract",
    "TargetEvidenceAuthorityContract",
    "DepthMetricContract",
    "QATaskAndReasoningCoverageMatrixContract",
)

ATTACK_NAMES: Final = (
    "post_action_reasoning_backfill",
    "generic_rationale_without_evidence",
    "cross_state_reasoning",
    "reasoning_action_mismatch",
    "future_evidence_reference",
    "observation_claim_update_mismatch",
    "actual_margin_relabelled_as_target",
    "correct_final_with_missing_decision_obligation",
    "valid_reasoning_with_invalid_final_or_citation",
    "paraphrase_only_trajectories_as_distinct_quotient_states",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity_matches(model: FrozenModel, field: str, prefix: str) -> bool:
    return getattr(model, field) == strict_canonical_hash(
        model.model_dump(mode="python", exclude={field}), prefix=prefix
    )


class ContractDescriptor(FrozenModel):
    contract_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = "1.0.0"
    scientific_object: str = Field(min_length=1)
    required_fields: tuple[str, ...] = Field(min_length=1)
    invariants: tuple[str, ...] = Field(min_length=1)
    forbidden_substitutions: tuple[str, ...] = Field(min_length=1)
    claim_boundary: str = Field(min_length=1)
    schema_version: str = "finance_qa_reasoning_contract_descriptor.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> ContractDescriptor:
        if (
            len(self.required_fields) != len(set(self.required_fields))
            or len(self.invariants) != len(set(self.invariants))
            or not identity_matches(
                self, "contract_id", "finance_qa_reasoning_contract_descriptor:"
            )
        ):
            raise ValueError("reasoning Contract descriptor differs")
        return self


class AnswerOracleProgramBindingV1(FrozenModel):
    binding_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    evidence_binding_id: str = Field(min_length=1)
    canonical_semantic_plan_id: str = Field(min_length=1)
    expected_answer_schema: dict[str, Any] = Field(min_length=1)
    recompute_contract_id: str = Field(min_length=1)
    citation_contract_id: str = Field(min_length=1)
    tolerance_and_rounding_contract: dict[str, Any] = Field(min_length=1)
    is_answer_correctness_oracle_only: Literal[True] = True
    prescribes_unique_reasoning_path: Literal[False] = False
    schema_version: str = "answer_oracle_program_binding.v1"

    @model_validator(mode="after")
    def validate_binding(self) -> AnswerOracleProgramBindingV1:
        if not identity_matches(self, "binding_id", "answer_oracle_program_binding:"):
            raise ValueError("Answer Oracle Program Binding identity differs")
        return self


class CriticalDecisionObligationV1(FrozenModel):
    decision_id: str = Field(min_length=1)
    trigger_state_predicate: str = Field(min_length=1)
    subgoal: str = Field(min_length=1)
    unresolved_uncertainty_type: str = Field(min_length=1)
    required_evidence_roles: tuple[str, ...] = Field(min_length=1)
    admissible_action_classes: tuple[str, ...] = Field(min_length=1)
    admissible_alternative_action_ids: tuple[str, ...] = Field(min_length=1)
    forbidden_shortcut_classes: tuple[str, ...] = Field(min_length=1)
    produced_claim_schema: dict[str, Any] = Field(min_length=1)
    downstream_claim_dependencies: tuple[str, ...] = ()
    required: bool = True
    counterfactual_intervention_ids: tuple[str, ...] = Field(min_length=1)


class CriticalDecisionGraphV1(FrozenModel):
    graph_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    answer_oracle_program_binding_id: str = Field(min_length=1)
    obligations: tuple[CriticalDecisionObligationV1, ...] = Field(min_length=1)
    allows_multiple_valid_orders: Literal[True] = True
    language_realization_is_authority: Literal[False] = False
    schema_version: str = "critical_decision_graph.v1"

    @model_validator(mode="after")
    def validate_graph(self) -> CriticalDecisionGraphV1:
        identifiers = tuple(item.decision_id for item in self.obligations)
        known = set(identifiers)
        if len(identifiers) != len(known):
            raise ValueError("Critical Decision Graph repeats an obligation")
        for index, item in enumerate(self.obligations):
            earlier = set(identifiers[:index])
            if not set(item.downstream_claim_dependencies) <= earlier:
                raise ValueError("Critical Decision Graph dependency is not topological")
            if item.required and not item.counterfactual_intervention_ids:
                raise ValueError("required decision lacks a direct intervention")
        if not any(item.required for item in self.obligations) or not identity_matches(
            self, "graph_id", "critical_decision_graph:"
        ):
            raise ValueError("Critical Decision Graph identity differs")
        return self


class PublicReasoningStateV1(FrozenModel):
    state_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    sequence_index: int = Field(ge=0)
    available_evidence_refs: tuple[str, ...] = ()
    verified_claim_refs: tuple[str, ...] = ()
    current_subgoal: str = Field(min_length=1)
    remaining_uncertainties: tuple[str, ...] = ()
    available_action_ids: tuple[str, ...] = Field(min_length=1)
    completed_action_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    private_reasoning_content_present: Literal[False] = False
    schema_version: str = "public_reasoning_state.v1"

    @model_validator(mode="after")
    def validate_state(self) -> PublicReasoningStateV1:
        domains = (
            self.available_evidence_refs,
            self.verified_claim_refs,
            self.available_action_ids,
            self.completed_action_refs,
            self.observation_refs,
        )
        if any(len(values) != len(set(values)) for values in domains) or not identity_matches(
            self, "state_id", "public_reasoning_state:"
        ):
            raise ValueError("Public Reasoning State identity or set domain differs")
        return self


class DecisionBasisEdgeV1(FrozenModel):
    relation: Literal["supports", "rules_out", "requires", "insufficient"]
    subject_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    claim_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_basis(self) -> DecisionBasisEdgeV1:
        if not self.evidence_refs and not self.claim_refs:
            raise ValueError("decision basis has no Evidence or Claim reference")
        return self


class PublicActionV1(FrozenModel):
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    protocol: Literal["finance_reasoning_action.v1"] = "finance_reasoning_action.v1"


class ReasoningActionEnvelopeV1(FrozenModel):
    envelope_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    decision_graph_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    subgoal: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    claim_refs: tuple[str, ...] = ()
    unresolved_uncertainty: str = Field(min_length=1)
    candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    decision_basis: tuple[DecisionBasisEdgeV1, ...] = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    action: PublicActionV1
    preaction_commit_sequence: int = Field(ge=0)
    protocol: Literal["finance_public_critical_reasoning.v1"] = (
        "finance_public_critical_reasoning.v1"
    )
    private_chain_of_thought_present: Literal[False] = False
    schema_version: str = "reasoning_action_envelope.v1"

    @model_validator(mode="after")
    def validate_envelope(self) -> ReasoningActionEnvelopeV1:
        if (
            self.selected_action_id not in self.candidate_action_ids
            or self.action.action_id != self.selected_action_id
            or self.action.state_id != self.state_id
            or len(self.candidate_action_ids) != len(set(self.candidate_action_ids))
            or not identity_matches(self, "envelope_id", "reasoning_action_envelope:")
        ):
            raise ValueError("Reasoning Action Envelope identity or Action relation differs")
        return self


class ActionExecutionV1(FrozenModel):
    execution_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    parent_envelope_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    execution_sequence: int = Field(ge=1)
    succeeded: bool
    public_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "reasoning_action_execution.v1"

    @model_validator(mode="after")
    def validate_execution(self) -> ActionExecutionV1:
        if not identity_matches(self, "execution_id", "reasoning_action_execution:"):
            raise ValueError("Reasoning Action Execution identity differs")
        return self


class PublicObservationV1(FrozenModel):
    observation_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    parent_execution_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    observation_sequence: int = Field(ge=1)
    public_payload: dict[str, Any] = Field(min_length=1)
    public_payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "public_reasoning_observation.v1"

    @model_validator(mode="after")
    def validate_observation(self) -> PublicObservationV1:
        import hashlib

        from trusted_synthesis.canonical_json import canonical_json_bytes

        if self.public_payload_hash != hashlib.sha256(
            canonical_json_bytes(self.public_payload)
        ).hexdigest() or not identity_matches(
            self, "observation_id", "public_reasoning_observation:"
        ):
            raise ValueError("Public Observation content relation differs")
        return self


class ClaimUpdateV1(FrozenModel):
    claim_id: str = Field(min_length=1)
    disposition: Literal["accepted", "rejected", "revised"]
    support_observation_refs: tuple[str, ...] = Field(min_length=1)
    public_claim: dict[str, Any] = Field(min_length=1)


class ObservationUpdateV1(FrozenModel):
    update_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    parent_reasoning_action_id: str = Field(min_length=1)
    action_execution_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    accepted_claims: tuple[ClaimUpdateV1, ...] = ()
    rejected_or_revised_claims: tuple[ClaimUpdateV1, ...] = ()
    remaining_uncertainties: tuple[str, ...] = ()
    newly_enabled_actions: tuple[str, ...] = ()
    next_subgoal: str = Field(min_length=1)
    next_state_id: str = Field(min_length=1)
    update_sequence: int = Field(ge=1)
    schema_version: str = "observation_update.v1"

    @model_validator(mode="after")
    def validate_update(self) -> ObservationUpdateV1:
        claims = (*self.accepted_claims, *self.rejected_or_revised_claims)
        if (
            not claims
            or any(self.observation_id not in item.support_observation_refs for item in claims)
            or not identity_matches(self, "update_id", "observation_update:")
        ):
            raise ValueError("Observation Update is not bound to its Observation")
        return self


class ReasoningTrajectoryV1(FrozenModel):
    trajectory_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    initial_state_id: str = Field(min_length=1)
    ordered_reasoning_action_ids: tuple[str, ...] = Field(min_length=1)
    ordered_action_execution_ids: tuple[str, ...] = Field(min_length=1)
    ordered_observation_ids: tuple[str, ...] = Field(min_length=1)
    ordered_observation_update_ids: tuple[str, ...] = Field(min_length=1)
    final_claim_refs: tuple[str, ...] = Field(min_length=1)
    final_answer_ref: str = Field(min_length=1)
    critical_decision_graph_id: str = Field(min_length=1)
    answer_oracle_program_binding_id: str = Field(min_length=1)
    covered_decision_ids: tuple[str, ...] = Field(min_length=1)
    wording_fingerprint: str | None = None
    schema_version: str = "reasoning_trajectory.v1"

    @model_validator(mode="after")
    def validate_trajectory(self) -> ReasoningTrajectoryV1:
        lengths = {
            len(self.ordered_reasoning_action_ids),
            len(self.ordered_action_execution_ids),
            len(self.ordered_observation_ids),
            len(self.ordered_observation_update_ids),
        }
        if len(lengths) != 1 or not identity_matches(
            self, "trajectory_id", "reasoning_trajectory:"
        ):
            raise ValueError("Reasoning Trajectory chain cardinality or identity differs")
        return self


class AnswerValidityReportV1(FrozenModel):
    report_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    source_valid: bool
    answer_valid: bool
    citation_valid: bool
    qa_valid: bool
    schema_version: str = "answer_validity_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> AnswerValidityReportV1:
        if self.qa_valid != (
            self.source_valid and self.answer_valid and self.citation_valid
        ) or not (identity_matches(self, "report_id", "answer_validity_report:")):
            raise ValueError("Answer Validity is not a noncompensatory conjunction")
        return self


class TrajectoryValidityReportV1(FrozenModel):
    report_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    preaction_valid: bool
    grounding_valid: bool
    reasoning_action_valid: bool
    observation_update_valid: bool
    critical_coverage_valid: bool
    trajectory_valid: bool
    schema_version: str = "reasoning_trajectory_validity_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> TrajectoryValidityReportV1:
        expected = all(
            (
                self.preaction_valid,
                self.grounding_valid,
                self.reasoning_action_valid,
                self.observation_update_valid,
                self.critical_coverage_valid,
            )
        )
        if self.trajectory_valid != expected or not identity_matches(
            self, "report_id", "reasoning_trajectory_validity_report:"
        ):
            raise ValueError("Trajectory Validity is not a noncompensatory conjunction")
        return self


class QualifiedReasoningTrajectoryV1(FrozenModel):
    qualification_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    answer_validity_report_id: str = Field(min_length=1)
    trajectory_validity_report_id: str = Field(min_length=1)
    qa_valid: bool
    trajectory_valid: bool
    qualified: bool
    schema_version: str = "qualified_reasoning_trajectory.v1"

    @model_validator(mode="after")
    def validate_qualification(self) -> QualifiedReasoningTrajectoryV1:
        if self.qualified != (self.qa_valid and self.trajectory_valid) or not identity_matches(
            self, "qualification_id", "qualified_reasoning_trajectory:"
        ):
            raise ValueError("qualified trajectory is not QA-and-trajectory valid")
        return self


class TargetEvidenceAuthorityContractV1(FrozenModel):
    contract_id: str = Field(min_length=1)
    allowed_modalities: tuple[Literal["management_target", "company_guidance"], ...] = (
        "management_target",
        "company_guidance",
    )
    forbidden_modalities: tuple[str, ...] = (
        "observed_actual",
        "analyst_consensus",
        "peer_benchmark",
        "arbitrary_constant",
        "derived_margin",
    )
    required_fields: tuple[str, ...] = (
        "metric_definition_id",
        "target_modality",
        "source_authority",
        "issuer_or_author",
        "statement_as_of",
        "effective_period",
        "entity_scope",
        "unit",
        "gaap_or_non_gaap_basis",
        "exact_text_or_table_locator",
        "source_document_id",
    )
    same_entity_period_required: Literal[True] = True
    schema_version: str = "target_evidence_authority_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> TargetEvidenceAuthorityContractV1:
        if set(self.allowed_modalities) & set(self.forbidden_modalities) or not identity_matches(
            self, "contract_id", "target_evidence_authority_contract:"
        ):
            raise ValueError("Target Evidence Authority Contract domain differs")
        return self


class TargetEvidenceCandidateV1(FrozenModel):
    evidence_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    metric_definition_id: str = Field(min_length=1)
    target_modality: str = Field(min_length=1)
    source_authority: str = Field(min_length=1)
    issuer_or_author: str = Field(min_length=1)
    statement_as_of: str = Field(min_length=1)
    effective_period: str = Field(min_length=1)
    entity_scope: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    gaap_or_non_gaap_basis: str = Field(min_length=1)
    exact_text_or_table_locator: str = Field(min_length=1)
    source_document_id: str = Field(min_length=1)


class ReasoningDepthMetricsV1(FrozenModel):
    metrics_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    semantic_operation_depth: int = Field(ge=0)
    reasoning_depth: int = Field(ge=0)
    evidence_integration_depth: int = Field(ge=0)
    correction_depth: int = Field(ge=0)
    required_decision_count: int = Field(ge=1)
    covered_required_decision_count: int = Field(ge=0)
    critical_decision_coverage: float = Field(ge=0, le=1)
    metrics_noninterchangeable: Literal[True] = True
    token_count_used_as_depth: Literal[False] = False
    text_length_used_as_depth: Literal[False] = False
    schema_version: str = "reasoning_depth_metrics.v1"

    @model_validator(mode="after")
    def validate_metrics(self) -> ReasoningDepthMetricsV1:
        expected = self.covered_required_decision_count / self.required_decision_count
        if (
            self.covered_required_decision_count > self.required_decision_count
            or abs(self.critical_decision_coverage - expected) > 1e-12
            or not identity_matches(self, "metrics_id", "reasoning_depth_metrics:")
        ):
            raise ValueError("reasoning depth metrics are not derived independently")
        return self


class CoverageMatrixCellV1(FrozenModel):
    cell_id: str = Field(min_length=1)
    archetype: Literal[
        "serial_derivation",
        "branch_and_merge",
        "select_then_lookup",
        "evidence_insufficiency_or_correction",
    ]
    task_family: str = Field(min_length=1)
    program_topology: str = Field(min_length=1)
    evidence_modality: str = Field(min_length=1)
    temporal_structure: str = Field(min_length=1)
    entity_structure: str = Field(min_length=1)
    reasoning_obligation: str = Field(min_length=1)
    answer_shape: str = Field(min_length=1)
    trajectory_structure: str = Field(min_length=1)
    future_fixture_only: Literal[True] = True


class QATaskAndReasoningCoverageMatrixV1(FrozenModel):
    matrix_id: str = Field(min_length=1)
    axis_values: dict[str, tuple[str, ...]] = Field(min_length=8, max_length=8)
    minimum_constructive_cells: tuple[CoverageMatrixCellV1, ...] = Field(min_length=4, max_length=4)
    coverage_measured: Literal[False] = False
    benchmark_frequency_claimed: Literal[False] = False
    schema_version: str = "qa_task_and_reasoning_coverage_matrix.v1"

    @model_validator(mode="after")
    def validate_matrix(self) -> QATaskAndReasoningCoverageMatrixV1:
        expected_axes = {
            "task_family",
            "program_topology",
            "evidence_modality",
            "temporal_structure",
            "entity_structure",
            "reasoning_obligation",
            "answer_shape",
            "trajectory_structure",
        }
        archetypes = {item.archetype for item in self.minimum_constructive_cells}
        if (
            set(self.axis_values) != expected_axes
            or len(archetypes) != 4
            or not identity_matches(self, "matrix_id", "qa_task_and_reasoning_coverage_matrix:")
        ):
            raise ValueError("QA Task and Reasoning Coverage Matrix differs")
        return self


class Products(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    predecessor_freeze: dict[str, Any]
    scope_clarification: dict[str, Any]
    source_binding: dict[str, Any]
    contract_descriptors: tuple[ContractDescriptor, ...]
    answer_oracle_binding: AnswerOracleProgramBindingV1
    critical_decision_graph: CriticalDecisionGraphV1
    initial_state: PublicReasoningStateV1
    reasoning_action: ReasoningActionEnvelopeV1
    action_execution: ActionExecutionV1
    observation: PublicObservationV1
    observation_update: ObservationUpdateV1
    next_state: PublicReasoningStateV1
    reasoning_trajectory: ReasoningTrajectoryV1
    answer_validity: AnswerValidityReportV1
    trajectory_validity: TrajectoryValidityReportV1
    qualification: QualifiedReasoningTrajectoryV1
    target_contract: TargetEvidenceAuthorityContractV1
    depth_metrics: ReasoningDepthMetricsV1
    coverage_matrix: QATaskAndReasoningCoverageMatrixV1
    conformance_audit: dict[str, Any]
    negative_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
