from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerificationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    BridgeCellObservation,
    BridgeMechanism,
    BridgeRolloutObservation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_rollout_runner import (
    BridgeRunReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
)
from trusted_synthesis.hashing import canonical_hash

V26_BRIDGE_STATISTICAL_AUDIT_VERSION = "finance_v26_bridge_statistical_audit.v5"
V26_BRIDGE_ROLLOUT_DIAGNOSTIC_VERSION = "finance_v26_bridge_rollout_diagnostic.v3"
V26_BRIDGE_TRACE_CELL_VERSION = "finance_v26_bridge_trace_cell.v1"
V26_BRIDGE_SCAFFOLD_INFLUENCE_VERSION = "finance_v26_bridge_scaffold_influence.v2"
V26_BRIDGE_FAILURE_STAGE_POLICY_VERSION = "finance_v26_bridge_failure_stage_policy.v1"
V26_BRIDGE_TRACE_CANONICALIZER_VERSION = "finance_v26_bridge_trace_canonicalizer.v1"
V26_BRIDGE_BOOTSTRAP_VERSION = "finance_v26_bridge_task_bootstrap.v1"

SCAFFOLD_LEVELS = ("gamma_0", "gamma_1", "gamma_2", "gamma_3")
FailureStage = Literal[
    "model_contract",
    "public_state_interpretation",
    "tool_selection",
    "argument_construction",
    "recovery",
    "evidence_selection",
    "operation_execution",
    "verification",
    "citation",
    "answer_projection",
]
EvidenceRelation = Literal[
    "unavailable",
    "empty",
    "exact_gold",
    "strict_superset",
    "strict_subset",
    "partial_overlap",
    "disjoint",
]
OutcomeScope = Literal["all", "valid", "invalid"]
AnswerMismatchClass = Literal[
    "reference_representation_only",
    "reference_identity_only",
    "numeric_or_scalar_only",
    "mixed_value_and_reference",
    "structural_or_other",
]

FAILURE_STAGE_ORDER: tuple[FailureStage, ...] = (
    "model_contract",
    "public_state_interpretation",
    "tool_selection",
    "argument_construction",
    "recovery",
    "evidence_selection",
    "operation_execution",
    "verification",
    "citation",
    "answer_projection",
)

CHECK_STAGE: dict[str, FailureStage] = {
    "task_identity": "public_state_interpretation",
    "omega_public_corpus_preserved": "public_state_interpretation",
    "candidate_workflow_kind": "public_state_interpretation",
    "public_only_generation": "public_state_interpretation",
    "environment_identity": "public_state_interpretation",
    "allowed_environment_tools": "tool_selection",
    "required_agent_tools_succeeded": "tool_selection",
    "deterministic_tool_replay": "argument_construction",
    "failed_tool_calls_recovered": "recovery",
    "retrieved_evidence_known": "evidence_selection",
    "retrieved_evidence_valid": "evidence_selection",
    "selected_evidence_known": "evidence_selection",
    "selected_evidence_retrievable": "evidence_selection",
    "selected_evidence_covers_gold": "evidence_selection",
    "proof_graph_binding": "operation_execution",
    "operation_lineage_covers_gold": "operation_execution",
    "oracle_program_replay": "operation_execution",
    "verification_support_covers_gold": "verification",
    "verification_succeeded": "verification",
    "stop_after_successful_verification": "verification",
    "citations_were_selected": "citation",
    "cited_evidence_known": "citation",
    "cited_evidence_valid": "citation",
    "citation_exact_gold": "citation",
    "evidence_provenance_complete": "citation",
    "answer_schema_valid": "answer_projection",
    "answer_correct": "answer_projection",
}

_CITATION_CHECKS = frozenset(
    {
        "citations_were_selected",
        "cited_evidence_known",
        "cited_evidence_valid",
        "citation_exact_gold",
        "evidence_provenance_complete",
    }
)
_SEMANTIC_VALUE_KEYS = frozenset(
    {
        "aggregation",
        "comparison",
        "direction",
        "mode",
        "operator",
        "relation",
        "sort_order",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SealedBridgeSupportDecision(FrozenModel):
    freeze_id: str = Field(min_length=1)
    source_schema_version: Literal["finance_compiler_assisted_bridge_support_freeze.v4"]
    status: Literal["blocked"]
    blockers: tuple[BridgeMechanism, ...]
    next_transition: Literal["capability_task_or_scaffold_redesign_only"]
    observation_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    selection_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    schema_version: Literal["finance_v26_sealed_bridge_support_decision.v1"] = (
        "finance_v26_sealed_bridge_support_decision.v1"
    )

    @model_validator(mode="after")
    def validate_decision(self) -> SealedBridgeSupportDecision:
        if self.blockers != BRIDGE_MECHANISMS:
            raise ValueError("sealed Bridge support blockers are incomplete")
        if self.observation_ids != tuple(sorted(set(self.observation_ids))):
            raise ValueError("sealed Bridge support Cell identities are not canonical")
        if len(set(self.selection_ids)) != 3:
            raise ValueError("sealed Bridge support selections are duplicated")
        return self


class MetricInterval(FrozenModel):
    metric_id: str = Field(min_length=1)
    point_estimate: float = Field(ge=0, le=1)
    lower_bound: float = Field(ge=0, le=1)
    upper_bound: float = Field(ge=0, le=1)
    confidence_level: float = Field(default=0.95, ge=0.95, le=0.95)
    bootstrap_replicates: Literal[5000] = 5000
    method: Literal["task_percentile_bootstrap"] = "task_percentile_bootstrap"

    @model_validator(mode="after")
    def validate_interval(self) -> MetricInterval:
        if self.confidence_level != 0.95:
            raise ValueError("Bridge statistical confidence level must remain frozen at 0.95")
        if not self.lower_bound <= self.point_estimate <= self.upper_bound:
            raise ValueError("Bridge statistical interval does not contain its point estimate")
        return self


class RolloutDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    scaffold_level: Literal["gamma_0", "gamma_1", "gamma_2", "gamma_3"]
    replicate_index: int = Field(ge=0, le=5)
    terminal_category: str = Field(min_length=1)
    independently_valid: bool
    earliest_failed_contract_stage: FailureStage | None = None
    failed_check_ids: tuple[str, ...]
    failure_pattern_id: str | None = None
    answer_only_mismatch_class: AnswerMismatchClass | None = None
    answer_mismatch_paths: tuple[str, ...] = ()
    selected_evidence_relation: EvidenceRelation
    cited_evidence_relation: EvidenceRelation
    selection_recall: float | None = Field(default=None, ge=0, le=1)
    selection_precision: float | None = Field(default=None, ge=0, le=1)
    citation_recall: float | None = Field(default=None, ge=0, le=1)
    citation_precision: float | None = Field(default=None, ge=0, le=1)
    trace_template_id: str = Field(min_length=1)
    action_sequence_id: str = Field(min_length=1)
    first_model_tool: str | None = None
    trace_tokens: tuple[str, ...] = Field(min_length=1)
    action_tokens: tuple[str, ...] = Field(min_length=1)
    quotient_state_id: str | None = None
    estimand_success: dict[str, bool | None]
    schema_version: str = V26_BRIDGE_ROLLOUT_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> RolloutDiagnostic:
        if self.independently_valid != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("Bridge diagnostic validity differs from terminal category")
        if self.independently_valid and (
            self.earliest_failed_contract_stage is not None or self.failed_check_ids
        ):
            raise ValueError("valid Bridge diagnostic contains a failure stage")
        if not self.independently_valid and self.earliest_failed_contract_stage is None:
            raise ValueError("invalid Bridge diagnostic lacks a failure stage")
        expected_pattern = (
            canonical_hash(self.failed_check_ids, prefix="finance_v26_failure_pattern:")
            if self.failed_check_ids
            else None
        )
        if self.failure_pattern_id != expected_pattern:
            raise ValueError("Bridge diagnostic failure-pattern identity is invalid")
        answer_only = self.failed_check_ids == ("answer_correct",)
        if answer_only != bool(self.answer_only_mismatch_class):
            raise ValueError("Bridge answer-only mismatch classification is incomplete")
        if answer_only != bool(self.answer_mismatch_paths):
            raise ValueError("Bridge answer-only mismatch paths are incomplete")
        if self.answer_mismatch_paths != tuple(sorted(set(self.answer_mismatch_paths))):
            raise ValueError("Bridge answer mismatch paths are not canonical")
        if self.trace_template_id != canonical_hash(
            self.trace_tokens,
            prefix="finance_v26_model_owned_trace_template:",
        ):
            raise ValueError("Bridge diagnostic trace-template identity is invalid")
        if self.action_sequence_id != canonical_hash(
            self.action_tokens,
            prefix="finance_v26_model_owned_action_sequence:",
        ):
            raise ValueError("Bridge diagnostic action-sequence identity is invalid")
        if self.diagnostic_id != rollout_diagnostic_id(self):
            raise ValueError("Bridge rollout diagnostic identity is invalid")
        return self


class TraceSliceSummary(FrozenModel):
    outcome_scope: OutcomeScope
    rollout_count: int = Field(ge=0, le=6)
    unique_trace_count: int = Field(ge=0, le=6)
    maximum_trace_share: float | None = Field(default=None, ge=0, le=1)
    trace_entropy_bits: float | None = Field(default=None, ge=0)
    effective_trace_count: float | None = Field(default=None, ge=0)
    unique_action_sequence_count: int = Field(ge=0, le=6)
    maximum_action_sequence_share: float | None = Field(default=None, ge=0, le=1)
    action_sequence_entropy_bits: float | None = Field(default=None, ge=0)
    effective_action_sequence_count: float | None = Field(default=None, ge=0)
    pairwise_trace_count: int = Field(ge=0, le=15)
    mean_pairwise_normalized_edit_distance: float | None = Field(default=None, ge=0, le=1)


class TraceCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    scaffold_level: Literal["gamma_0", "gamma_1", "gamma_2", "gamma_3"]
    task_id: str = Field(min_length=1)
    slices: tuple[TraceSliceSummary, ...] = Field(min_length=3, max_length=3)
    schema_version: str = V26_BRIDGE_TRACE_CELL_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> TraceCellSummary:
        if tuple(item.outcome_scope for item in self.slices) != ("all", "valid", "invalid"):
            raise ValueError("Bridge trace cell lacks the ordered outcome slices")
        if self.slices[0].rollout_count != 6:
            raise ValueError("Bridge trace cell does not contain six rollouts")
        if self.summary_id != trace_cell_summary_id(self):
            raise ValueError("Bridge trace cell identity is invalid")
        return self


class ScaffoldLevelComparison(FrozenModel):
    scaffold_level: Literal["gamma_1", "gamma_2", "gamma_3"]
    trace_distribution_jsd_bits: float = Field(ge=0, le=1)
    action_distribution_jsd_bits: float = Field(ge=0, le=1)
    paired_trace_change_rate: float = Field(ge=0, le=1)
    paired_action_change_rate: float = Field(ge=0, le=1)
    paired_first_tool_change_rate: float = Field(ge=0, le=1)
    valid_rate: float = Field(ge=0, le=1)
    gamma_zero_valid_rate: float = Field(ge=0, le=1)


class ScaffoldTaskInfluence(FrozenModel):
    influence_id: str = Field(min_length=1)
    mechanism_id: BridgeMechanism
    task_id: str = Field(min_length=1)
    comparisons: tuple[ScaffoldLevelComparison, ...] = Field(min_length=3, max_length=3)
    modal_trace_ids: dict[str, str]
    modal_action_sequence_ids: dict[str, str]
    valid_rate_by_level: dict[str, float]
    schema_version: str = V26_BRIDGE_SCAFFOLD_INFLUENCE_VERSION

    @model_validator(mode="after")
    def validate_influence(self) -> ScaffoldTaskInfluence:
        if tuple(item.scaffold_level for item in self.comparisons) != SCAFFOLD_LEVELS[1:]:
            raise ValueError("Bridge scaffold influence lacks the three paired comparisons")
        if tuple(self.valid_rate_by_level) != SCAFFOLD_LEVELS:
            raise ValueError("Bridge scaffold influence valid-rate ladder is incomplete")
        if tuple(self.modal_trace_ids) != SCAFFOLD_LEVELS:
            raise ValueError("Bridge modal trace ladder is incomplete")
        if tuple(self.modal_action_sequence_ids) != SCAFFOLD_LEVELS:
            raise ValueError("Bridge modal action ladder is incomplete")
        if self.influence_id != scaffold_task_influence_id(self):
            raise ValueError("Bridge scaffold influence identity is invalid")
        return self


class MechanismScaffoldInfluence(FrozenModel):
    mechanism_id: BridgeMechanism
    task_count: Literal[8] = 8
    metric_intervals: tuple[MetricInterval, ...]
    tasks_with_any_modal_trace_change: int = Field(ge=0, le=8)
    tasks_with_any_modal_action_change: int = Field(ge=0, le=8)


class EvidenceSupportAudit(FrozenModel):
    verification_report_count: int = Field(ge=1)
    model_contract_failure_count: int = Field(ge=0)
    selected_relation_counts: dict[EvidenceRelation, int]
    cited_relation_counts: dict[EvidenceRelation, int]
    citation_exact_gold_failure_count: int = Field(ge=0)
    citation_failure_with_selection_covering_gold_count: int = Field(ge=0)
    citation_failure_with_correct_answer_count: int = Field(ge=0)
    citation_strict_superset_count: int = Field(ge=0)
    citation_strict_superset_with_known_valid_citations_count: int = Field(ge=0)
    citation_strict_superset_with_correct_answer_count: int = Field(ge=0)
    citation_exact_only_blocker_count: int = Field(ge=0)
    citation_family_only_blocker_count: int = Field(ge=0)
    semantic_equivalence_of_non_gold_evidence_evaluated: Literal[False] = False
    post_hoc_rescoring_performed: Literal[False] = False


class AnswerProjectionAudit(FrozenModel):
    answer_only_failure_count: int = Field(ge=0, le=576)
    answer_only_failure_counts_by_mechanism: dict[str, int]
    mismatch_class_counts: dict[str, int]
    mismatch_path_counts: dict[str, int]
    pairwise_difference_and_reference_count: int = Field(ge=0)
    scalar_value_count: int = Field(ge=0)
    reference_representation_only_count: int = Field(ge=0)
    reference_identity_only_count: int = Field(ge=0)
    numeric_or_scalar_only_count: int = Field(ge=0)
    mixed_value_and_reference_count: int = Field(ge=0)
    structural_or_other_count: int = Field(ge=0)
    projection_only_failure_is_not_equivalent_to_format_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_projection_accounting(self) -> AnswerProjectionAudit:
        if sum(self.answer_only_failure_counts_by_mechanism.values()) != (
            self.answer_only_failure_count
        ):
            raise ValueError("answer-only failures are not accounted by mechanism")
        named_counts = {
            "reference_representation_only": self.reference_representation_only_count,
            "reference_identity_only": self.reference_identity_only_count,
            "numeric_or_scalar_only": self.numeric_or_scalar_only_count,
            "mixed_value_and_reference": self.mixed_value_and_reference_count,
            "structural_or_other": self.structural_or_other_count,
        }
        if set(self.mismatch_class_counts) - set(named_counts):
            raise ValueError("answer-only mismatch classes contain an unknown category")
        if any(
            self.mismatch_class_counts.get(key, 0) != value for key, value in named_counts.items()
        ):
            raise ValueError("answer-only mismatch classes disagree with named counts")
        if sum(named_counts.values()) != self.answer_only_failure_count:
            raise ValueError("answer-only mismatch classes do not cover the denominator")
        return self


class ValidSupportAudit(FrozenModel):
    valid_rollout_count: int = Field(ge=0, le=576)
    valid_task_count: int = Field(ge=0, le=24)
    valid_cell_count: int = Field(ge=0, le=96)
    unique_valid_trace_template_count: int = Field(ge=0, le=576)
    unique_valid_action_sequence_count: int = Field(ge=0, le=576)
    valid_quotient_state_observation_count: int = Field(ge=0, le=576)
    invalid_quotient_state_observation_count: Literal[0] = 0
    unique_quotient_state_count: int = Field(ge=0, le=576)
    maximum_quotient_state_share: float = Field(ge=0, le=1)
    quotient_state_entropy_bits: float = Field(ge=0)
    effective_quotient_state_count: float = Field(ge=0, le=576)
    valid_trace_entropy_bits: float = Field(ge=0)
    effective_valid_trace_count: float = Field(ge=0, le=576)
    maximum_mechanism_share: float = Field(ge=0, le=1)
    inference_status: Literal["insufficient_support_for_positive_distribution_inference"] = (
        "insufficient_support_for_positive_distribution_inference"
    )

    @model_validator(mode="after")
    def validate_state_support(self) -> ValidSupportAudit:
        if self.valid_quotient_state_observation_count != self.valid_rollout_count:
            raise ValueError("every valid Bridge rollout must have a Quotient State")
        if self.unique_quotient_state_count > self.valid_quotient_state_observation_count:
            raise ValueError("unique Quotient State count exceeds its observation denominator")
        return self


class StaticPathSupportAudit(FrozenModel):
    task_count: Literal[24] = 24
    tasks_with_one_registered_reference_example: int = Field(ge=0, le=24)
    tasks_with_multiple_registered_reference_examples: int = Field(ge=0, le=24)
    alternative_valid_path_catalog_count: Literal[0] = 0
    mechanism_necessity_artifact_count: Literal[0] = 0
    public_executable_witness_artifact_count: Literal[0] = 0
    operation_branch_count_distribution: dict[str, int]
    operation_branch_count_minimum: int = Field(ge=0)
    operation_branch_count_maximum: int = Field(ge=0)
    observation: Literal[
        "single_registered_reference_is_not_proof_of_single_semantically_valid_path"
    ] = "single_registered_reference_is_not_proof_of_single_semantically_valid_path"


class BridgeStatisticalAuditReport(FrozenModel):
    audit_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_bridge_report_id: str = Field(min_length=1)
    source_support_freeze_id: str = Field(min_length=1)
    source_paths: dict[str, str]
    source_sha256: dict[str, str]
    implementation_sha256: str = Field(min_length=64, max_length=64)
    rollout_count: Literal[576] = 576
    terminal_counts: dict[str, int]
    earliest_failure_stage_counts: dict[str, int]
    earliest_failure_stage_counts_by_mechanism: dict[str, dict[str, int]]
    failed_check_counts: dict[str, int]
    failed_check_cooccurrence_counts: dict[str, int]
    failure_pattern_count: int = Field(ge=1)
    maximum_failure_pattern_share: float = Field(ge=0, le=1)
    failure_pattern_entropy_bits: float = Field(ge=0)
    evidence_support: EvidenceSupportAudit
    answer_projection: AnswerProjectionAudit
    valid_support: ValidSupportAudit
    mechanism_scaffold_influence: tuple[MechanismScaffoldInfluence, ...]
    static_path_support: StaticPathSupportAudit
    diagnostics_path: str = Field(min_length=1)
    diagnostics_sha256: str = Field(min_length=64, max_length=64)
    diagnostics_content_hash: str = Field(min_length=1)
    diagnostics_count: Literal[576] = 576
    trace_cells_path: str = Field(min_length=1)
    trace_cells_sha256: str = Field(min_length=64, max_length=64)
    trace_cells_content_hash: str = Field(min_length=1)
    trace_cell_count: Literal[96] = 96
    scaffold_influence_path: str = Field(min_length=1)
    scaffold_influence_sha256: str = Field(min_length=64, max_length=64)
    scaffold_influence_content_hash: str = Field(min_length=1)
    scaffold_influence_count: Literal[24] = 24
    failure_stage_policy_version: str = V26_BRIDGE_FAILURE_STAGE_POLICY_VERSION
    trace_canonicalizer_version: str = V26_BRIDGE_TRACE_CANONICALIZER_VERSION
    bootstrap_version: str = V26_BRIDGE_BOOTSTRAP_VERSION
    task_is_primary_sampling_unit: Literal[True] = True
    read_only_audit: Literal[True] = True
    post_hoc_rescoring_performed: Literal[False] = False
    authorization_effect: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["observed_non_authorizing"] = "observed_non_authorizing"
    next_transition: Literal["capability_task_or_scaffold_redesign_only"] = (
        "capability_task_or_scaffold_redesign_only"
    )
    schema_version: str = V26_BRIDGE_STATISTICAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BridgeStatisticalAuditReport:
        if sum(self.terminal_counts.values()) != self.rollout_count:
            raise ValueError("Bridge statistical audit terminal accounting is incomplete")
        accounted = (
            sum(self.earliest_failure_stage_counts.values())
            + self.valid_support.valid_rollout_count
        )
        if accounted != self.rollout_count:
            raise ValueError("Bridge statistical audit failure-stage accounting is incomplete")
        if self.terminal_counts.get("model_valid_trajectory", 0) != (
            self.valid_support.valid_rollout_count
        ):
            raise ValueError("Bridge valid-support count disagrees with terminal accounting")
        if self.terminal_counts.get("model_invalid_trajectory", 0) != sum(
            self.earliest_failure_stage_counts.values()
        ):
            raise ValueError("Bridge invalid terminal count disagrees with failure stages")
        if self.answer_projection.answer_only_failure_count != (
            self.earliest_failure_stage_counts.get("answer_projection", 0)
        ):
            raise ValueError("Bridge answer-only count disagrees with the failure cascade")
        if (
            self.evidence_support.verification_report_count
            + self.evidence_support.model_contract_failure_count
            != self.rollout_count
        ):
            raise ValueError("Bridge verifier-report denominator is incomplete")
        if sum(self.evidence_support.selected_relation_counts.values()) != self.rollout_count:
            raise ValueError("Bridge selected-Evidence relation denominator is incomplete")
        if sum(self.evidence_support.cited_relation_counts.values()) != self.rollout_count:
            raise ValueError("Bridge cited-Evidence relation denominator is incomplete")
        if tuple(item.mechanism_id for item in self.mechanism_scaffold_influence) != (
            BRIDGE_MECHANISMS
        ):
            raise ValueError("Bridge statistical audit mechanism summaries are incomplete")
        if self.audit_id != bridge_statistical_audit_id(self):
            raise ValueError("Bridge statistical audit identity is invalid")
        return self


def rollout_diagnostic_id(value: RolloutDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_bridge_rollout_diagnostic:",
    )


def trace_cell_summary_id(value: TraceCellSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_bridge_trace_cell:",
    )


def scaffold_task_influence_id(value: ScaffoldTaskInfluence) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"influence_id"}),
        prefix="finance_v26_bridge_scaffold_influence:",
    )


def bridge_statistical_audit_id(value: BridgeStatisticalAuditReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_bridge_statistical_audit:",
    )


def _load_sealed_bridge_support_decision(
    freeze_path: Path,
    cells_path: Path,
) -> SealedBridgeSupportDecision:
    payload = json.loads(freeze_path.read_text())
    freeze_id = payload.get("freeze_id")
    expected_id = canonical_hash(
        {key: value for key, value in payload.items() if key != "freeze_id"},
        prefix="finance_compiler_assisted_bridge_support_freeze:",
    )
    if freeze_id != expected_id:
        raise ValueError("sealed Bridge Support Freeze identity is invalid")
    if payload.get("schema_version") != "finance_compiler_assisted_bridge_support_freeze.v4":
        raise ValueError("statistical audit requires the sealed v26.43 Support Freeze v4")
    if payload.get("status") != "blocked" or payload.get("next_transition") != (
        "capability_task_or_scaffold_redesign_only"
    ):
        raise ValueError("sealed Bridge Support Freeze is not the blocked Development decision")

    observations = tuple(
        BridgeCellObservation.model_validate(item) for item in payload.get("observations", ())
    )
    persisted_cells = tuple(
        BridgeCellObservation.model_validate(item) for item in json.loads(cells_path.read_text())
    )
    observation_ids = tuple(sorted(item.observation_id for item in observations))
    persisted_ids = tuple(sorted(item.observation_id for item in persisted_cells))
    if len(observation_ids) != 12 or observation_ids != persisted_ids:
        raise ValueError("sealed Bridge Support Freeze does not embed the persisted 12 Cells")

    selections = tuple(payload.get("selections", ()))
    if len(selections) != 3:
        raise ValueError("sealed Bridge Support Freeze lacks three mechanism selections")
    by_mechanism = {item.get("mechanism_id"): item for item in selections}
    if tuple(by_mechanism) != BRIDGE_MECHANISMS:
        raise ValueError("sealed Bridge Support Freeze selections are reordered or incomplete")
    for mechanism in BRIDGE_MECHANISMS:
        selection = by_mechanism[mechanism]
        if (
            selection.get("status") != "blocked"
            or selection.get("selected_scaffold_level") is not None
            or selection.get("passing_scaffold_levels")
        ):
            raise ValueError("sealed Bridge Support Freeze contains a passing selection")
    blockers = tuple(payload.get("blockers", ()))
    return SealedBridgeSupportDecision(
        freeze_id=freeze_id,
        source_schema_version=payload["schema_version"],
        status=payload["status"],
        blockers=blockers,
        next_transition=payload["next_transition"],
        observation_ids=observation_ids,
        selection_ids=tuple(selection["selection_id"] for selection in selections),
    )


def build_bridge_statistical_audit(
    *,
    run_id: str,
    bridge_dir: Path,
    no_api_dir: Path,
    output_dir: Path,
) -> BridgeStatisticalAuditReport:
    bridge_root = bridge_dir.resolve()
    no_api_root = no_api_dir.resolve()
    output_root = output_dir.resolve()
    if output_root.exists():
        raise ValueError("Bridge statistical audit output is immutable")
    output_root.mkdir(parents=True)

    source_paths = {
        "bridge_report": bridge_root / "report.json",
        "bridge_rollouts": bridge_root / "bridge_rollouts.json",
        "bridge_support_freeze": bridge_root / "bridge_support_freeze.json",
        "bridge_cells": bridge_root / "bridge_cells.json",
        "compiled_proof_artifacts": no_api_root / "joint" / "compiled_proof_artifacts.json",
        "development_population": no_api_root / "population" / "development.json",
    }
    for label, path in source_paths.items():
        if not path.is_file():
            raise ValueError(f"Bridge statistical audit input is missing: {label}")

    report = BridgeRunReport.model_validate_json(source_paths["bridge_report"].read_text())
    support_freeze = _load_sealed_bridge_support_decision(
        source_paths["bridge_support_freeze"],
        source_paths["bridge_cells"],
    )
    if (
        report.completed_rollout_count != 576
        or report.bridge_support_freeze_id != support_freeze.freeze_id
    ):
        raise ValueError("Bridge statistical audit received an incomplete or cross-run report")
    if support_freeze.status != "blocked" or support_freeze.next_transition != (
        "capability_task_or_scaffold_redesign_only"
    ):
        raise ValueError(
            "Bridge statistical audit may only inspect the frozen blocked Development run"
        )

    rollouts = tuple(
        BridgeRolloutObservation.model_validate(item)
        for item in json.loads(source_paths["bridge_rollouts"].read_text())
    )
    if len(rollouts) != 576 or len({item.rollout_id for item in rollouts}) != 576:
        raise ValueError("Bridge statistical audit requires 576 unique rollout identities")
    compiled = tuple(
        CompiledProofCarryingArtifacts.model_validate(item)
        for item in json.loads(source_paths["compiled_proof_artifacts"].read_text())
    )
    population = V26FreshTaskPopulation.model_validate_json(
        source_paths["development_population"].read_text()
    )
    source_population_path = Path(population.source_population_path)
    source_paths["source_population"] = source_population_path
    source_population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        source_population_path.read_text()
    )

    diagnostics = _make_rollout_diagnostics(rollouts, bridge_root=bridge_root, compiled=compiled)
    trace_cells = _make_trace_cells(diagnostics)
    scaffold_tasks = _make_scaffold_influences(diagnostics)
    mechanism_influence = _make_mechanism_influences(scaffold_tasks)

    diagnostics_path = output_root / "rollout_diagnostics.json"
    trace_cells_path = output_root / "trace_cell_summaries.json"
    scaffold_path = output_root / "scaffold_task_influences.json"
    _write_json_atomic(diagnostics_path, [item.model_dump(mode="json") for item in diagnostics])
    _write_json_atomic(trace_cells_path, [item.model_dump(mode="json") for item in trace_cells])
    _write_json_atomic(scaffold_path, [item.model_dump(mode="json") for item in scaffold_tasks])

    report_values = _report_values(
        run_id=run_id,
        source_report=report,
        support_freeze=support_freeze,
        source_paths=source_paths,
        diagnostics=diagnostics,
        trace_cells=trace_cells,
        scaffold_tasks=scaffold_tasks,
        mechanism_influence=mechanism_influence,
        compiled=compiled,
        population=population,
        source_population=source_population,
        diagnostics_path=diagnostics_path,
        trace_cells_path=trace_cells_path,
        scaffold_path=scaffold_path,
    )
    provisional = BridgeStatisticalAuditReport.model_construct(audit_id="pending", **report_values)
    audit = BridgeStatisticalAuditReport(
        audit_id=bridge_statistical_audit_id(provisional),
        **report_values,
    )
    _write_json_atomic(output_root / "report.json", audit.model_dump(mode="json"))
    return audit


def replay_bridge_statistical_audit(report_path: Path) -> None:
    audit_path = report_path.resolve()
    audit = BridgeStatisticalAuditReport.model_validate_json(audit_path.read_text())
    for label, path_text in audit.source_paths.items():
        path = Path(path_text)
        if _sha256(path) != audit.source_sha256[label]:
            raise ValueError(f"Bridge statistical audit source changed: {label}")
    if _sha256(Path(__file__)) != audit.implementation_sha256:
        raise ValueError("Bridge statistical audit implementation changed")

    outputs: tuple[tuple[str, str, str], ...] = (
        (audit.diagnostics_path, audit.diagnostics_sha256, audit.diagnostics_content_hash),
        (audit.trace_cells_path, audit.trace_cells_sha256, audit.trace_cells_content_hash),
        (
            audit.scaffold_influence_path,
            audit.scaffold_influence_sha256,
            audit.scaffold_influence_content_hash,
        ),
    )
    for path_text, expected_sha, expected_content_hash in outputs:
        path = Path(path_text)
        if _sha256(path) != expected_sha:
            raise ValueError("Bridge statistical audit output bytes changed")
        payload = json.loads(path.read_text())
        if canonical_hash(payload, prefix="finance_v26_bridge_statistical_output:") != (
            expected_content_hash
        ):
            raise ValueError("Bridge statistical audit output content changed")

    diagnostics = tuple(
        RolloutDiagnostic.model_validate(item)
        for item in json.loads(Path(audit.diagnostics_path).read_text())
    )
    trace_cells = tuple(
        TraceCellSummary.model_validate(item)
        for item in json.loads(Path(audit.trace_cells_path).read_text())
    )
    scaffold_tasks = tuple(
        ScaffoldTaskInfluence.model_validate(item)
        for item in json.loads(Path(audit.scaffold_influence_path).read_text())
    )
    if (len(diagnostics), len(trace_cells), len(scaffold_tasks)) != (576, 96, 24):
        raise ValueError("Bridge statistical audit output cardinality changed")


def _make_rollout_diagnostics(
    rollouts: tuple[BridgeRolloutObservation, ...],
    *,
    bridge_root: Path,
    compiled: tuple[CompiledProofCarryingArtifacts, ...],
) -> tuple[RolloutDiagnostic, ...]:
    gold_by_task = {
        item.task.task_id: frozenset(
            evidence.evidence_id for evidence in item.evidence_bundle.evidence
        )
        for item in compiled
    }
    answer_projection_by_task: dict[str, dict[str, str]] = {}
    for item in compiled:
        raw_projection = item.task.oracle.selection_contract.get("answer_projection", {})
        if not isinstance(raw_projection, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_projection.items()
        ):
            raise ValueError("Bridge task contains an invalid Answer Projection contract")
        answer_projection_by_task[item.task.task_id] = dict(raw_projection)
    diagnostics: list[RolloutDiagnostic] = []
    for rollout in sorted(rollouts, key=lambda item: item.rollout_id):
        task_id = rollout.condition_lineage.task_id
        gold = gold_by_task.get(task_id)
        if not gold:
            raise ValueError("Bridge rollout task is absent from compiled Gold support")
        raw_path = Path(rollout.raw_artifact_uri).resolve()
        if not raw_path.is_relative_to(bridge_root):
            raise ValueError("Bridge raw rollout escaped its immutable run directory")
        raw_bytes = raw_path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != rollout.raw_artifact_sha256:
            raise ValueError("Bridge raw rollout bytes differ from typed observation")
        raw = json.loads(raw_bytes)
        if raw != rollout.raw_payload:
            raise ValueError("Bridge raw rollout payload differs from typed observation")

        verification = (
            FinanceIterativeAgentVerificationReport.model_validate(raw["independent_verification"])
            if raw.get("independent_verification") is not None
            else None
        )
        failed_checks = (
            tuple(item.check_id for item in verification.checks if not item.passed)
            if verification is not None
            else ()
        )
        unknown = set(failed_checks) - set(CHECK_STAGE)
        if unknown:
            raise ValueError(
                f"Bridge statistical audit encountered unknown verifier checks: {unknown}"
            )
        earliest = _earliest_failure_stage(
            terminal_category=rollout.terminal_category,
            failed_check_ids=failed_checks,
        )
        trace_tokens, action_tokens, first_tool = _model_owned_trace(raw, gold)
        selection_relation = (
            _evidence_relation(verification.selected_evidence_ids, verification.gold_evidence_ids)
            if verification is not None
            else "unavailable"
        )
        cited_relation = (
            _evidence_relation(verification.cited_evidence_ids, verification.gold_evidence_ids)
            if verification is not None
            else "unavailable"
        )
        answer_class, answer_paths = (
            _classify_answer_only_mismatch(
                verification,
                answer_projection=answer_projection_by_task[task_id],
            )
            if verification is not None and failed_checks == ("answer_correct",)
            else (None, ())
        )
        values: dict[str, Any] = {
            "rollout_id": rollout.rollout_id,
            "task_id": task_id,
            "mechanism_id": rollout.mechanism_id,
            "scaffold_level": rollout.scaffold_level,
            "replicate_index": rollout.replicate_index,
            "terminal_category": rollout.terminal_category,
            "independently_valid": rollout.independent_validity_passed,
            "earliest_failed_contract_stage": earliest,
            "failed_check_ids": failed_checks,
            "failure_pattern_id": (
                canonical_hash(failed_checks, prefix="finance_v26_failure_pattern:")
                if failed_checks
                else None
            ),
            "answer_only_mismatch_class": answer_class,
            "answer_mismatch_paths": answer_paths,
            "selected_evidence_relation": selection_relation,
            "cited_evidence_relation": cited_relation,
            "selection_recall": verification.selection_recall if verification else None,
            "selection_precision": verification.selection_precision if verification else None,
            "citation_recall": verification.citation_recall if verification else None,
            "citation_precision": verification.citation_precision if verification else None,
            "trace_template_id": canonical_hash(
                trace_tokens,
                prefix="finance_v26_model_owned_trace_template:",
            ),
            "action_sequence_id": canonical_hash(
                action_tokens,
                prefix="finance_v26_model_owned_action_sequence:",
            ),
            "first_model_tool": first_tool,
            "trace_tokens": trace_tokens,
            "action_tokens": action_tokens,
            "quotient_state_id": rollout.quotient_state_id,
            "estimand_success": {
                item.estimand_id: item.success for item in rollout.estimand_outcomes
            },
            "schema_version": V26_BRIDGE_ROLLOUT_DIAGNOSTIC_VERSION,
        }
        provisional = RolloutDiagnostic.model_construct(diagnostic_id="pending", **values)
        diagnostics.append(
            RolloutDiagnostic(
                diagnostic_id=rollout_diagnostic_id(provisional),
                **values,
            )
        )
    return tuple(diagnostics)


def _classify_answer_only_mismatch(
    verification: FinanceIterativeAgentVerificationReport,
    *,
    answer_projection: Mapping[str, str],
) -> tuple[AnswerMismatchClass, tuple[str, ...]]:
    differences: list[tuple[tuple[str, ...], Any, Any]] = []
    structural = _collect_answer_differences(
        verification.normalized_candidate_answer,
        verification.normalized_oracle_answer,
        path=(),
        output=differences,
    )
    paths = tuple(sorted(".".join(path) or "$" for path, _, _ in differences))
    if not paths:
        raise ValueError("answer-only failure contains no normalized answer difference")
    if structural:
        return "structural_or_other", paths
    reference_rows = [row for row in differences if row[0] and row[0][-1].lower().endswith("ref")]
    if len(reference_rows) == len(differences):
        representation_only = all(
            isinstance(candidate, str)
            and isinstance(oracle, str)
            and oracle.startswith("evidence:")
            and answer_projection.get(oracle) == candidate
            for _, candidate, oracle in reference_rows
        )
        return (
            "reference_representation_only" if representation_only else "reference_identity_only",
            paths,
        )
    if not reference_rows:
        return "numeric_or_scalar_only", paths
    return "mixed_value_and_reference", paths


def _collect_answer_differences(
    candidate: Any,
    oracle: Any,
    *,
    path: tuple[str, ...],
    output: list[tuple[tuple[str, ...], Any, Any]],
) -> bool:
    if isinstance(candidate, Mapping) and isinstance(oracle, Mapping):
        if set(candidate) != set(oracle):
            output.append((path + ("<keys>",), tuple(sorted(candidate)), tuple(sorted(oracle))))
            return True
        structural = False
        for key in sorted(candidate):
            structural = (
                _collect_answer_differences(
                    candidate[key],
                    oracle[key],
                    path=path + (str(key),),
                    output=output,
                )
                or structural
            )
        return structural
    if isinstance(candidate, list) and isinstance(oracle, list):
        if len(candidate) != len(oracle):
            output.append((path + ("<length>",), len(candidate), len(oracle)))
            return True
        structural = False
        for index, (left, right) in enumerate(zip(candidate, oracle, strict=True)):
            structural = (
                _collect_answer_differences(
                    left,
                    right,
                    path=path + (str(index),),
                    output=output,
                )
                or structural
            )
        return structural
    if type(candidate) is not type(oracle):
        output.append((path, candidate, oracle))
        return True
    if candidate != oracle:
        output.append((path, candidate, oracle))
    return False


def _earliest_failure_stage(
    *,
    terminal_category: str,
    failed_check_ids: tuple[str, ...],
) -> FailureStage | None:
    if terminal_category == "model_valid_trajectory":
        if failed_check_ids:
            raise ValueError("valid Bridge rollout contains failed checks")
        return None
    if terminal_category == "model_invalid_trajectory" and not failed_check_ids:
        return "model_contract"
    if terminal_category in {"runtime_failure", "instrument_failure"}:
        raise ValueError("v26.43 statistical audit does not reclassify infrastructure failures")
    if not failed_check_ids:
        raise ValueError("invalid Bridge rollout lacks failure evidence")
    stages = {CHECK_STAGE[item] for item in failed_check_ids}
    return min(stages, key=FAILURE_STAGE_ORDER.index)


def _model_owned_trace(
    raw: Mapping[str, Any],
    gold: frozenset[str],
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    detailed: list[str] = []
    actions: list[str] = []
    first_tool: str | None = None
    trajectory = raw.get("trajectory")
    if isinstance(trajectory, Mapping):
        for step in trajectory.get("steps", ()):
            if not isinstance(step, Mapping):
                raise ValueError("Bridge trajectory step is not a mapping")
            tool = step.get("tool_name")
            if first_tool is None and isinstance(tool, str):
                first_tool = tool
            semantic_operator = _semantic_operator(step.get("tool_input"))
            action_payload = {
                "action": step.get("action"),
                "tool": tool,
                "status": step.get("status"),
                "operator": semantic_operator,
            }
            actions.append(_canonical_token(action_payload))
            detailed.append(
                _canonical_token(
                    {
                        **action_payload,
                        "argument_shape": _value_shape(step.get("tool_input")),
                        "evidence_role": _evidence_role(step.get("evidence_ids", ()), gold),
                        "input_ref_count": len(step.get("input_refs", ())),
                    }
                )
            )
    else:
        failure = raw.get("failure_artifact")
        if not isinstance(failure, Mapping):
            raise ValueError("Bridge model outcome lacks trajectory and failure artifact")
        detailed.append(_canonical_token({"action": "plan", "tool": None, "status": "succeeded"}))
        actions.append(_canonical_token({"action": "plan", "tool": None, "status": "succeeded"}))
        observations = failure.get("observations", ())
        for index, decision in enumerate(failure.get("decisions", ())):
            if not isinstance(decision, Mapping):
                raise ValueError("Bridge failure decision is not a mapping")
            observation = observations[index] if index < len(observations) else {}
            tool = decision.get("tool_id")
            if first_tool is None and isinstance(tool, str):
                first_tool = tool
            status = observation.get("status") if isinstance(observation, Mapping) else None
            semantic_operator = _semantic_operator(decision.get("arguments"))
            action_payload = {
                "action": decision.get("decision_type"),
                "tool": tool,
                "status": status,
                "operator": semantic_operator,
            }
            actions.append(_canonical_token(action_payload))
            evidence_ids = (
                observation.get("evidence_ids", ()) if isinstance(observation, Mapping) else ()
            )
            detailed.append(
                _canonical_token(
                    {
                        **action_payload,
                        "argument_shape": _value_shape(decision.get("arguments")),
                        "evidence_role": _evidence_role(evidence_ids, gold),
                        "citation_role": _evidence_role(
                            decision.get("cited_evidence_ids", ()), gold
                        ),
                    }
                )
            )
        detailed.append(
            _canonical_token(
                {"action": "model_contract_exhausted", "tool": None, "status": "failed"}
            )
        )
        actions.append(
            _canonical_token(
                {"action": "model_contract_exhausted", "tool": None, "status": "failed"}
            )
        )
    if not detailed:
        raise ValueError("Bridge model-owned trace is empty")
    return tuple(detailed), tuple(actions), first_tool


def _canonical_token(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _semantic_operator(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in _SEMANTIC_VALUE_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str):
            normalized = candidate.strip().lower()
            if (
                normalized
                and len(normalized) <= 48
                and not any(character.isdigit() for character in normalized)
            ):
                return normalized
    return None


def _value_shape(value: Any, *, key: str | None = None) -> Any:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        if key in _SEMANTIC_VALUE_KEYS:
            normalized = value.strip().lower()
            if (
                normalized
                and len(normalized) <= 48
                and not any(character.isdigit() for character in normalized)
            ):
                return {"type": "semantic_enum", "value": normalized}
        return "string"
    if isinstance(value, Mapping):
        return {
            str(item_key): _value_shape(item_value, key=str(item_key))
            for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        shapes = tuple(_canonical_token({"shape": _value_shape(item)}) for item in value)
        return {
            "type": "array",
            "length_bucket": _length_bucket(len(value)),
            "element_shapes": tuple(sorted(set(shapes))),
        }
    return type(value).__name__


def _length_bucket(value: int) -> str:
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2_3"
    if value <= 6:
        return "4_6"
    return "7_plus"


def _evidence_role(values: Iterable[Any], gold: frozenset[str]) -> dict[str, int | str]:
    observed = {str(item) for item in values}
    return {
        "relation": _evidence_relation(tuple(observed), tuple(gold)),
        "gold_count": len(observed & gold),
        "extra_count": len(observed - gold),
    }


def _evidence_relation(
    observed_values: Iterable[str], gold_values: Iterable[str]
) -> EvidenceRelation:
    observed = set(observed_values)
    gold = set(gold_values)
    if not observed:
        return "empty"
    if observed == gold:
        return "exact_gold"
    if gold < observed:
        return "strict_superset"
    if observed < gold:
        return "strict_subset"
    overlap = observed & gold
    if overlap:
        return "partial_overlap"
    return "disjoint"


def _make_trace_cells(diagnostics: tuple[RolloutDiagnostic, ...]) -> tuple[TraceCellSummary, ...]:
    grouped: defaultdict[tuple[str, str, str], list[RolloutDiagnostic]] = defaultdict(list)
    for item in diagnostics:
        grouped[(item.mechanism_id, item.scaffold_level, item.task_id)].append(item)
    if len(grouped) != 96:
        raise ValueError("Bridge statistical audit does not contain 96 task-level cells")
    output: list[TraceCellSummary] = []
    for key in sorted(
        grouped,
        key=lambda item: (
            BRIDGE_MECHANISMS.index(item[0]),
            SCAFFOLD_LEVELS.index(item[1]),
            item[2],
        ),
    ):
        rows = tuple(sorted(grouped[key], key=lambda item: item.replicate_index))
        if len(rows) != 6 or tuple(item.replicate_index for item in rows) != tuple(range(6)):
            raise ValueError("Bridge trace cell lacks the exact replicate denominator")
        slices = (
            _trace_slice("all", rows),
            _trace_slice("valid", tuple(item for item in rows if item.independently_valid)),
            _trace_slice("invalid", tuple(item for item in rows if not item.independently_valid)),
        )
        values = {
            "mechanism_id": key[0],
            "scaffold_level": key[1],
            "task_id": key[2],
            "slices": slices,
            "schema_version": V26_BRIDGE_TRACE_CELL_VERSION,
        }
        provisional = TraceCellSummary.model_construct(summary_id="pending", **values)
        output.append(TraceCellSummary(summary_id=trace_cell_summary_id(provisional), **values))
    return tuple(output)


def _trace_slice(
    scope: OutcomeScope,
    rows: tuple[RolloutDiagnostic, ...],
) -> TraceSliceSummary:
    trace_counts = Counter(item.trace_template_id for item in rows)
    action_counts = Counter(item.action_sequence_id for item in rows)
    distances = [
        _normalized_levenshtein(left.trace_tokens, right.trace_tokens)
        for left, right in itertools.combinations(rows, 2)
    ]
    return TraceSliceSummary(
        outcome_scope=scope,
        rollout_count=len(rows),
        unique_trace_count=len(trace_counts),
        maximum_trace_share=_maximum_share(trace_counts),
        trace_entropy_bits=_entropy_bits(trace_counts),
        effective_trace_count=_effective_count(trace_counts),
        unique_action_sequence_count=len(action_counts),
        maximum_action_sequence_share=_maximum_share(action_counts),
        action_sequence_entropy_bits=_entropy_bits(action_counts),
        effective_action_sequence_count=_effective_count(action_counts),
        pairwise_trace_count=len(distances),
        mean_pairwise_normalized_edit_distance=(
            sum(distances) / len(distances) if distances else None
        ),
    )


def _make_scaffold_influences(
    diagnostics: tuple[RolloutDiagnostic, ...],
) -> tuple[ScaffoldTaskInfluence, ...]:
    grouped: defaultdict[tuple[str, str, str], list[RolloutDiagnostic]] = defaultdict(list)
    for item in diagnostics:
        grouped[(item.mechanism_id, item.task_id, item.scaffold_level)].append(item)
    task_keys = sorted(
        {(mechanism, task_id) for mechanism, task_id, _ in grouped},
        key=lambda item: (BRIDGE_MECHANISMS.index(item[0]), item[1]),
    )
    if len(task_keys) != 24:
        raise ValueError("Bridge scaffold influence lacks the 24 Development tasks")
    output: list[ScaffoldTaskInfluence] = []
    for mechanism, task_id in task_keys:
        by_level = {
            level: tuple(
                sorted(grouped[(mechanism, task_id, level)], key=lambda item: item.replicate_index)
            )
            for level in SCAFFOLD_LEVELS
        }
        if any(len(rows) != 6 for rows in by_level.values()):
            raise ValueError("Bridge scaffold influence lacks six paired rollouts per level")
        baseline = by_level["gamma_0"]
        comparisons = tuple(
            _scaffold_comparison(level, baseline, by_level[level]) for level in SCAFFOLD_LEVELS[1:]
        )
        values = {
            "mechanism_id": mechanism,
            "task_id": task_id,
            "comparisons": comparisons,
            "modal_trace_ids": {
                level: _mode(item.trace_template_id for item in by_level[level])
                for level in SCAFFOLD_LEVELS
            },
            "modal_action_sequence_ids": {
                level: _mode(item.action_sequence_id for item in by_level[level])
                for level in SCAFFOLD_LEVELS
            },
            "valid_rate_by_level": {
                level: sum(item.independently_valid for item in by_level[level]) / 6.0
                for level in SCAFFOLD_LEVELS
            },
            "schema_version": V26_BRIDGE_SCAFFOLD_INFLUENCE_VERSION,
        }
        provisional = ScaffoldTaskInfluence.model_construct(influence_id="pending", **values)
        output.append(
            ScaffoldTaskInfluence(
                influence_id=scaffold_task_influence_id(provisional),
                **values,
            )
        )
    return tuple(output)


def _scaffold_comparison(
    level: str,
    baseline: tuple[RolloutDiagnostic, ...],
    current: tuple[RolloutDiagnostic, ...],
) -> ScaffoldLevelComparison:
    baseline_by_rep = {item.replicate_index: item for item in baseline}
    current_by_rep = {item.replicate_index: item for item in current}
    if set(baseline_by_rep) != set(current_by_rep) or set(current_by_rep) != set(range(6)):
        raise ValueError("Bridge scaffold comparison is not replicate-paired")
    return ScaffoldLevelComparison(
        scaffold_level=level,
        trace_distribution_jsd_bits=_jensen_shannon_bits(
            Counter(item.trace_template_id for item in baseline),
            Counter(item.trace_template_id for item in current),
        ),
        action_distribution_jsd_bits=_jensen_shannon_bits(
            Counter(item.action_sequence_id for item in baseline),
            Counter(item.action_sequence_id for item in current),
        ),
        paired_trace_change_rate=sum(
            baseline_by_rep[index].trace_template_id != current_by_rep[index].trace_template_id
            for index in range(6)
        )
        / 6.0,
        paired_action_change_rate=sum(
            baseline_by_rep[index].action_sequence_id != current_by_rep[index].action_sequence_id
            for index in range(6)
        )
        / 6.0,
        paired_first_tool_change_rate=sum(
            baseline_by_rep[index].first_model_tool != current_by_rep[index].first_model_tool
            for index in range(6)
        )
        / 6.0,
        valid_rate=sum(item.independently_valid for item in current) / 6.0,
        gamma_zero_valid_rate=sum(item.independently_valid for item in baseline) / 6.0,
    )


def _make_mechanism_influences(
    tasks: tuple[ScaffoldTaskInfluence, ...],
) -> tuple[MechanismScaffoldInfluence, ...]:
    output: list[MechanismScaffoldInfluence] = []
    for mechanism in BRIDGE_MECHANISMS:
        rows = tuple(item for item in tasks if item.mechanism_id == mechanism)
        if len(rows) != 8:
            raise ValueError("Bridge mechanism influence lacks eight tasks")
        task_metrics = {
            item.task_id: {
                "trace_distribution_jsd_bits": _mean(
                    comparison.trace_distribution_jsd_bits for comparison in item.comparisons
                ),
                "action_distribution_jsd_bits": _mean(
                    comparison.action_distribution_jsd_bits for comparison in item.comparisons
                ),
                "paired_trace_change_rate": _mean(
                    comparison.paired_trace_change_rate for comparison in item.comparisons
                ),
                "paired_action_change_rate": _mean(
                    comparison.paired_action_change_rate for comparison in item.comparisons
                ),
                "paired_first_tool_change_rate": _mean(
                    comparison.paired_first_tool_change_rate for comparison in item.comparisons
                ),
                "valid_rate": _mean(item.valid_rate_by_level.values()),
            }
            for item in rows
        }
        metric_ids = tuple(next(iter(task_metrics.values())))
        intervals = tuple(
            _task_bootstrap_interval(
                metric_id,
                {task_id: values[metric_id] for task_id, values in task_metrics.items()},
                seed_scope=mechanism,
            )
            for metric_id in metric_ids
        )
        output.append(
            MechanismScaffoldInfluence(
                mechanism_id=mechanism,
                metric_intervals=intervals,
                tasks_with_any_modal_trace_change=sum(
                    any(
                        item.modal_trace_ids[level] != item.modal_trace_ids["gamma_0"]
                        for level in SCAFFOLD_LEVELS[1:]
                    )
                    for item in rows
                ),
                tasks_with_any_modal_action_change=sum(
                    any(
                        item.modal_action_sequence_ids[level]
                        != item.modal_action_sequence_ids["gamma_0"]
                        for level in SCAFFOLD_LEVELS[1:]
                    )
                    for item in rows
                ),
            )
        )
    return tuple(output)


def _task_bootstrap_interval(
    metric_id: str,
    values_by_task: Mapping[str, float],
    *,
    seed_scope: str,
) -> MetricInterval:
    task_ids = tuple(sorted(values_by_task))
    point = _mean(values_by_task.values())
    seed = canonical_hash(
        {"scope": seed_scope, "metric_id": metric_id},
        prefix="finance_v26_bridge_statistical_bootstrap_seed:",
    )
    rng = random.Random(int(seed.rsplit(":", 1)[-1][:16], 16))
    draws = sorted(
        _mean(values_by_task[task_ids[rng.randrange(len(task_ids))]] for _ in task_ids)
        for _ in range(5000)
    )
    lower = min(point, _percentile(draws, 0.025))
    upper = max(point, _percentile(draws, 0.975))
    return MetricInterval(
        metric_id=metric_id,
        point_estimate=point,
        lower_bound=lower,
        upper_bound=upper,
    )


def _report_values(
    *,
    run_id: str,
    source_report: BridgeRunReport,
    support_freeze: SealedBridgeSupportDecision,
    source_paths: Mapping[str, Path],
    diagnostics: tuple[RolloutDiagnostic, ...],
    trace_cells: tuple[TraceCellSummary, ...],
    scaffold_tasks: tuple[ScaffoldTaskInfluence, ...],
    mechanism_influence: tuple[MechanismScaffoldInfluence, ...],
    compiled: tuple[CompiledProofCarryingArtifacts, ...],
    population: V26FreshTaskPopulation,
    source_population: CapabilitySensitiveFrontierPopulation,
    diagnostics_path: Path,
    trace_cells_path: Path,
    scaffold_path: Path,
) -> dict[str, Any]:
    terminal_counts = Counter(item.terminal_category for item in diagnostics)
    stage_counts = Counter(
        item.earliest_failed_contract_stage
        for item in diagnostics
        if item.earliest_failed_contract_stage is not None
    )
    stage_by_mechanism = {
        mechanism: dict(
            sorted(
                Counter(
                    item.earliest_failed_contract_stage
                    for item in diagnostics
                    if item.mechanism_id == mechanism
                    and item.earliest_failed_contract_stage is not None
                ).items()
            )
        )
        for mechanism in BRIDGE_MECHANISMS
    }
    failed_check_counts = Counter(
        check_id for item in diagnostics for check_id in item.failed_check_ids
    )
    cooccurrence = Counter(
        "|".join(pair)
        for item in diagnostics
        for pair in itertools.combinations(item.failed_check_ids, 2)
    )
    failure_patterns = Counter(
        item.failure_pattern_id for item in diagnostics if item.failure_pattern_id is not None
    )

    verification_rows = tuple(
        item for item in diagnostics if item.selected_evidence_relation != "unavailable"
    )
    citation_failures = tuple(
        item for item in verification_rows if "citation_exact_gold" in item.failed_check_ids
    )
    strict_supersets = tuple(
        item for item in verification_rows if item.cited_evidence_relation == "strict_superset"
    )
    evidence_support = EvidenceSupportAudit(
        verification_report_count=len(verification_rows),
        model_contract_failure_count=sum(
            item.earliest_failed_contract_stage == "model_contract" for item in diagnostics
        ),
        selected_relation_counts=_relation_counts(
            item.selected_evidence_relation for item in diagnostics
        ),
        cited_relation_counts=_relation_counts(
            item.cited_evidence_relation for item in diagnostics
        ),
        citation_exact_gold_failure_count=len(citation_failures),
        citation_failure_with_selection_covering_gold_count=sum(
            item.selection_recall == 1.0 for item in citation_failures
        ),
        citation_failure_with_correct_answer_count=sum(
            "answer_correct" not in item.failed_check_ids for item in citation_failures
        ),
        citation_strict_superset_count=len(strict_supersets),
        citation_strict_superset_with_known_valid_citations_count=sum(
            "cited_evidence_known" not in item.failed_check_ids
            and "cited_evidence_valid" not in item.failed_check_ids
            for item in strict_supersets
        ),
        citation_strict_superset_with_correct_answer_count=sum(
            "answer_correct" not in item.failed_check_ids for item in strict_supersets
        ),
        citation_exact_only_blocker_count=sum(
            item.failed_check_ids == ("citation_exact_gold",) for item in verification_rows
        ),
        citation_family_only_blocker_count=sum(
            bool(item.failed_check_ids) and set(item.failed_check_ids) <= _CITATION_CHECKS
            for item in verification_rows
        ),
    )

    answer_only_rows = tuple(
        item for item in diagnostics if item.answer_only_mismatch_class is not None
    )
    mismatch_class_counts = Counter(item.answer_only_mismatch_class for item in answer_only_rows)
    mismatch_path_counts = Counter(
        path for item in answer_only_rows for path in item.answer_mismatch_paths
    )
    answer_projection = AnswerProjectionAudit(
        answer_only_failure_count=len(answer_only_rows),
        answer_only_failure_counts_by_mechanism={
            mechanism: sum(item.mechanism_id == mechanism for item in answer_only_rows)
            for mechanism in BRIDGE_MECHANISMS
        },
        mismatch_class_counts=dict(sorted(mismatch_class_counts.items())),
        mismatch_path_counts=dict(sorted(mismatch_path_counts.items())),
        pairwise_difference_and_reference_count=sum(
            set(item.answer_mismatch_paths) == {"difference", "higher_ref"}
            for item in answer_only_rows
        ),
        scalar_value_count=sum(
            item.answer_mismatch_paths == ("value",) for item in answer_only_rows
        ),
        reference_representation_only_count=mismatch_class_counts["reference_representation_only"],
        reference_identity_only_count=mismatch_class_counts["reference_identity_only"],
        numeric_or_scalar_only_count=mismatch_class_counts["numeric_or_scalar_only"],
        mixed_value_and_reference_count=mismatch_class_counts["mixed_value_and_reference"],
        structural_or_other_count=mismatch_class_counts["structural_or_other"],
    )

    valid_rows = tuple(item for item in diagnostics if item.independently_valid)
    valid_trace_counts = Counter(item.trace_template_id for item in valid_rows)
    valid_mechanism_counts = Counter(item.mechanism_id for item in valid_rows)
    valid_state_counts = Counter(
        item.quotient_state_id for item in valid_rows if item.quotient_state_id is not None
    )
    invalid_state_count = sum(
        item.quotient_state_id is not None for item in diagnostics if not item.independently_valid
    )
    valid_support = ValidSupportAudit(
        valid_rollout_count=len(valid_rows),
        valid_task_count=len({item.task_id for item in valid_rows}),
        valid_cell_count=len(
            {(item.mechanism_id, item.scaffold_level, item.task_id) for item in valid_rows}
        ),
        unique_valid_trace_template_count=len(valid_trace_counts),
        unique_valid_action_sequence_count=len({item.action_sequence_id for item in valid_rows}),
        valid_quotient_state_observation_count=sum(valid_state_counts.values()),
        invalid_quotient_state_observation_count=invalid_state_count,
        unique_quotient_state_count=len(valid_state_counts),
        maximum_quotient_state_share=_maximum_share(valid_state_counts) or 0.0,
        quotient_state_entropy_bits=_entropy_bits(valid_state_counts) or 0.0,
        effective_quotient_state_count=_effective_count(valid_state_counts) or 0.0,
        valid_trace_entropy_bits=_entropy_bits(valid_trace_counts) or 0.0,
        effective_valid_trace_count=_effective_count(valid_trace_counts) or 0.0,
        maximum_mechanism_share=(
            max(valid_mechanism_counts.values()) / len(valid_rows) if valid_rows else 0.0
        ),
    )

    compiled_by_task = {item.task.task_id: item for item in compiled}
    source_by_id = {item.artifact_id: item for item in source_population.tasks}
    branch_counts: Counter[str] = Counter()
    reference_counts: list[int] = []
    for root in population.tasks:
        compiled_item = compiled_by_task[root.task_id]
        source_item = source_by_id[root.source_task_artifact_id]
        reference_counts.append(len(compiled_item.reference_examples))
        branch_counts[str(source_item.structure.operation_branch_count)] += 1
    static_path = StaticPathSupportAudit(
        tasks_with_one_registered_reference_example=sum(value == 1 for value in reference_counts),
        tasks_with_multiple_registered_reference_examples=sum(
            value > 1 for value in reference_counts
        ),
        operation_branch_count_distribution=dict(sorted(branch_counts.items())),
        operation_branch_count_minimum=min(int(value) for value in branch_counts),
        operation_branch_count_maximum=max(int(value) for value in branch_counts),
    )

    return {
        "run_id": run_id,
        "source_bridge_report_id": source_report.report_id,
        "source_support_freeze_id": support_freeze.freeze_id,
        "source_paths": {
            label: str(path.resolve()) for label, path in sorted(source_paths.items())
        },
        "source_sha256": {label: _sha256(path) for label, path in sorted(source_paths.items())},
        "implementation_sha256": _sha256(Path(__file__)),
        "rollout_count": 576,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "earliest_failure_stage_counts": dict(sorted(stage_counts.items())),
        "earliest_failure_stage_counts_by_mechanism": stage_by_mechanism,
        "failed_check_counts": dict(sorted(failed_check_counts.items())),
        "failed_check_cooccurrence_counts": dict(sorted(cooccurrence.items())),
        "failure_pattern_count": len(failure_patterns),
        "maximum_failure_pattern_share": max(failure_patterns.values())
        / sum(failure_patterns.values()),
        "failure_pattern_entropy_bits": _entropy_bits(failure_patterns) or 0.0,
        "evidence_support": evidence_support,
        "answer_projection": answer_projection,
        "valid_support": valid_support,
        "mechanism_scaffold_influence": mechanism_influence,
        "static_path_support": static_path,
        "diagnostics_path": str(diagnostics_path),
        "diagnostics_sha256": _sha256(diagnostics_path),
        "diagnostics_content_hash": canonical_hash(
            json.loads(diagnostics_path.read_text()),
            prefix="finance_v26_bridge_statistical_output:",
        ),
        "diagnostics_count": len(diagnostics),
        "trace_cells_path": str(trace_cells_path),
        "trace_cells_sha256": _sha256(trace_cells_path),
        "trace_cells_content_hash": canonical_hash(
            json.loads(trace_cells_path.read_text()),
            prefix="finance_v26_bridge_statistical_output:",
        ),
        "trace_cell_count": len(trace_cells),
        "scaffold_influence_path": str(scaffold_path),
        "scaffold_influence_sha256": _sha256(scaffold_path),
        "scaffold_influence_content_hash": canonical_hash(
            json.loads(scaffold_path.read_text()),
            prefix="finance_v26_bridge_statistical_output:",
        ),
        "scaffold_influence_count": len(scaffold_tasks),
        "failure_stage_policy_version": V26_BRIDGE_FAILURE_STAGE_POLICY_VERSION,
        "trace_canonicalizer_version": V26_BRIDGE_TRACE_CANONICALIZER_VERSION,
        "bootstrap_version": V26_BRIDGE_BOOTSTRAP_VERSION,
        "task_is_primary_sampling_unit": True,
        "read_only_audit": True,
        "post_hoc_rescoring_performed": False,
        "authorization_effect": False,
        "model_api_calls": 0,
        "gpu_jobs": 0,
        "status": "observed_non_authorizing",
        "next_transition": "capability_task_or_scaffold_redesign_only",
        "schema_version": V26_BRIDGE_STATISTICAL_AUDIT_VERSION,
    }


def _relation_counts(values: Iterable[EvidenceRelation]) -> dict[EvidenceRelation, int]:
    counts = Counter(values)
    return {
        relation: counts[relation]
        for relation in (
            "unavailable",
            "empty",
            "exact_gold",
            "strict_superset",
            "strict_subset",
            "partial_overlap",
            "disjoint",
        )
    }


def _maximum_share(counts: Counter[str]) -> float | None:
    return max(counts.values()) / sum(counts.values()) if counts else None


def _entropy_bits(counts: Counter[Any]) -> float | None:
    total = sum(counts.values())
    if not total:
        return None
    return -math.fsum(
        (count / total) * math.log2(count / total) for count in sorted(counts.values())
    )


def _effective_count(counts: Counter[str]) -> float | None:
    entropy = _entropy_bits(counts)
    return 2.0**entropy if entropy is not None else None


def _mode(values: Iterable[str]) -> str:
    counts = Counter(values)
    if not counts:
        raise ValueError("cannot select a modal trace from an empty cell")
    maximum = max(counts.values())
    return min(key for key, count in counts.items() if count == maximum)


def _jensen_shannon_bits(left: Counter[str], right: Counter[str]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    if not left_total or not right_total:
        raise ValueError("cannot compare empty trace distributions")
    keys = set(left) | set(right)
    terms: list[float] = []
    for key in sorted(keys):
        p = left[key] / left_total
        q = right[key] / right_total
        midpoint = (p + q) / 2.0
        if p:
            terms.append(0.5 * p * math.log2(p / midpoint))
        if q:
            terms.append(0.5 * q * math.log2(q / midpoint))
    return min(1.0, max(0.0, math.fsum(terms)))


def _normalized_levenshtein(left: Sequence[str], right: Sequence[str]) -> float:
    denominator = max(len(left), len(right))
    if denominator == 0:
        return 0.0
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1] / denominator


def _mean(values: Iterable[float]) -> float:
    rows = tuple(values)
    if not rows:
        raise ValueError("cannot average an empty Bridge statistic")
    return sum(rows) / len(rows)


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile from an empty sample")
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit v26.43 Bridge failure and trace structure.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--run-id", required=True)
    build_parser.add_argument("--bridge-dir", type=Path, required=True)
    build_parser.add_argument("--no-api-dir", type=Path, required=True)
    build_parser.add_argument("--output-dir", type=Path, required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        report = build_bridge_statistical_audit(
            run_id=args.run_id,
            bridge_dir=args.bridge_dir,
            no_api_dir=args.no_api_dir,
            output_dir=args.output_dir,
        )
        print(
            json.dumps(
                {
                    "audit_id": report.audit_id,
                    "status": report.status,
                    "next_transition": report.next_transition,
                    "model_api_calls": report.model_api_calls,
                    "gpu_jobs": report.gpu_jobs,
                },
                sort_keys=True,
            )
        )
        return 0
    replay_bridge_statistical_audit(args.report)
    print(json.dumps({"status": "replayed", "report": str(args.report.resolve())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
