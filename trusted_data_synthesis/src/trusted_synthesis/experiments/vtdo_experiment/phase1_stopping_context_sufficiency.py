from __future__ import annotations

import argparse
import heapq
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import ProgramExecutionError
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION,
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceStoppingPublicRelationState,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    make_finance_submechanism_scenario,
    submechanism_policy_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    PUBLIC_SUBMECHANISM_METADATA_KEY,
    _freeze_scenario,
    _make_scenario,
    replay_submechanism_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_contextual_counterfactual import (  # noqa: E501
    FinanceStoppingContextualCounterfactualPopulation,
    FinanceStoppingContextualCounterfactualProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_instrument_reset import (
    _artifact_id,
    _reference,
    _sha256,
    _verify_reference,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy_protocol import (
    ALL_SHAPES,
    CONFLICT_MISMATCH_BY_CELL,
    REPLICAS,
    STRUCTURAL_STRATA,
    TARGET_ROLE_INDEX_BY_SHAPE,
    TASKS_PER_SHAPE,
    FinanceStoppingInstrumentResetGrammarProtocol,
    StoppingShapePolicyDefinition,
    StoppingShapePolicyDesign,
    StoppingShapePolicyThresholds,
    _build_one_difference_index,
    _indexed_one_difference_candidates,
    _materialize_shape_policy_task,
    _observed_evidence_state,
    _observed_record,
    _ordered_shape_candidates,
    load_stopping_shape_grammar_protocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    FrozenArtifactReference,
    StoppingShapeTask,
    _collect_excluded_identities,
    _difficulty_vector,
    stopping_shape_task_id,
)
from trusted_synthesis.hashing import canonical_hash

CONTEXT_SUFFICIENCY_PROTOCOL_VERSION = "finance_stopping_context_sufficiency_protocol.v1"
CONTEXT_SUFFICIENCY_POPULATION_VERSION = "finance_stopping_context_sufficiency_population.v1"
CONTEXT_SUFFICIENCY_STATIC_AUDIT_VERSION = "finance_stopping_context_sufficiency_static_audit.v1"
CONTEXT_SUFFICIENCY_CONTRACT_VERSION = "finance_stopping_context_sufficiency_contract.v1"
CONTEXT_SUFFICIENCY_MECHANISM_REPORT_VERSION = (
    "finance_stopping_context_sufficiency_mechanism_report.v1"
)
CONTEXT_SUFFICIENCY_REPORT_VERSION = "finance_stopping_context_sufficiency_report.v1"
CONTEXT_SUFFICIENCY_MANIFEST_VERSION = "finance_stopping_context_sufficiency_manifest.v1"
CONTEXT_SUFFICIENCY_LABEL = "finance_v25_47_context_sufficiency"

EXPECTED_TASK_COUNT = 48
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * REPLICAS
PAIR_COUNT = len(STRUCTURAL_STRATA)
CONTEXTUAL_TASK_COUNT = PAIR_COUNT * 2
FROZEN_REGRESSION_TASK_COUNT = EXPECTED_TASK_COUNT - CONTEXTUAL_TASK_COUNT
CONTEXTUAL_CONDITIONS: tuple[Literal["period", "definition"], ...] = (
    "period",
    "definition",
)
EXPECTED_ACTION_BY_CONDITION = {
    "period": "query_structured_fact",
    "definition": "normalize_metric_unit_period",
}
CONTEXT_SUFFICIENCY_CONTRACT_KIND = "context_sufficient_counterfactual_evidence_choice_two_step"
SHARED_RESOLUTION_POLICY = (
    "Choose the action whose stated effect resolves the sole unresolved relation while "
    "preserving every aligned relation."
)
ACTION_FUNCTION_BY_TOOL = {
    "normalize_metric_unit_period": (
        "transform selected entries to a common interpretive convention"
    ),
    "open_document": "inspect authoritative provenance when trust remains unsettled",
    "query_structured_fact": "obtain another archived entry through a revised selector",
}
RELATION_TO_ACTION_FUNCTION = {
    "observation_identity_relation": ACTION_FUNCTION_BY_TOOL["query_structured_fact"],
    "meaning_compatibility_relation": ACTION_FUNCTION_BY_TOOL["normalize_metric_unit_period"],
    "measurement_compatibility_relation": ACTION_FUNCTION_BY_TOOL["normalize_metric_unit_period"],
    "authority_relation": ACTION_FUNCTION_BY_TOOL["open_document"],
}
CANDIDATE_POOL_LIMIT = 8192
CONTEXTUAL_CANDIDATE_POOL_LIMIT = 512


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ContextSufficiencyThresholds(FrozenModel):
    minimum_contextual_flip_consistency: float = Field(default=0.125, ge=0, le=1)
    minimum_dual_correct_replicates_per_pair: int = Field(default=1, ge=1, le=8)
    minimum_informative_pair_count: int = Field(default=4, ge=4, le=4)
    maximum_branch_action_rate_difference: float = Field(default=0.75, ge=0, le=1)
    constant_action_baseline: float = Field(default=0.5, ge=0.5, le=0.5)
    minimum_branch_balanced_first_action_accuracy: float = Field(default=0.625, ge=0.625, le=0.625)
    minimum_contextual_policy_gain: float = Field(default=0.125, ge=0.125, le=0.125)
    minimum_branch_balanced_accuracy_bootstrap_lcb: float = Field(default=0.5, ge=0.5, le=0.5)
    bootstrap_replicates: int = Field(default=10_000, ge=10_000, le=10_000)
    bootstrap_seed: int = Field(default=20260847, ge=20260847, le=20260847)


class FinanceStoppingContextSufficiencyProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_47_context_sufficiency"] = (
        "finance_v25_47_context_sufficiency"
    )
    source_v25_46_report: FrozenArtifactReference
    source_v25_46_raw_audit: FrozenArtifactReference
    source_v25_46_shape_report: FrozenArtifactReference
    source_v25_46_mechanism_report: FrozenArtifactReference
    source_v25_46_manifest: FrozenArtifactReference
    source_v25_46_protocol: FrozenArtifactReference
    source_v25_46_population: FrozenArtifactReference
    source_grammar_protocol: FrozenArtifactReference
    source_grammar_population: FrozenArtifactReference
    source_finance_artifacts: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=45)
    shape_designs: tuple[StoppingShapePolicyDesign, ...] = Field(min_length=6, max_length=6)
    shape_thresholds: StoppingShapePolicyThresholds
    flip_thresholds: ContextSufficiencyThresholds = Field(
        default_factory=ContextSufficiencyThresholds
    )
    estimand_definition: StoppingShapePolicyDefinition = Field(
        default_factory=StoppingShapePolicyDefinition
    )
    structural_strata: tuple[tuple[str, str, DifficultyTier], ...] = STRUCTURAL_STRATA
    contextual_conditions: tuple[Literal["period", "definition"], ...] = (
        "period",
        "definition",
    )
    expected_actions: dict[str, str] = Field(
        default_factory=lambda: dict(EXPECTED_ACTION_BY_CONDITION)
    )
    single_conflict_mismatch_by_cell: dict[str, str] = Field(
        default_factory=lambda: {
            f"{stratum_id}|{instance_index}": mismatch
            for (stratum_id, instance_index), mismatch in sorted(CONFLICT_MISMATCH_BY_CELL.items())
        }
    )
    same_core_task_required: Literal[True] = True
    same_public_corpus_required: Literal[True] = True
    same_program_required: Literal[True] = True
    same_answer_schema_required: Literal[True] = True
    same_action_set_required: Literal[True] = True
    same_tool_budget_required: Literal[True] = True
    same_prompt_bytes_required: Literal[True] = True
    lexical_action_answer_leakage_forbidden: Literal[True] = True
    public_context_sufficiency_required: Literal[True] = True
    unique_applicable_action_required: Literal[True] = True
    no_shortcut_mutations_required: Literal[True] = True
    action_description_symmetry_required: Literal[True] = True
    empirical_thresholds_preregistered: Literal[True] = True
    pair_count: Literal[4] = 4
    task_count: Literal[48] = 48
    replicas: Literal[8] = 8
    rollout_count: Literal[384] = 384
    source_outcome_support_transferred: Literal[False] = False
    other_five_shape_mechanisms_frozen: Literal[True] = True
    shape_thresholds_frozen: Literal[True] = True
    public_result_schemas_frozen: Literal[True] = True
    recursive_noninterference_frozen: Literal[True] = True
    flash_only: Literal[True] = True
    pro_api_call_count: Literal[0] = 0
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["context_sufficiency_population_build"] = (
        "context_sufficiency_population_build"
    )
    schema_version: str = CONTEXT_SUFFICIENCY_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingContextSufficiencyProtocol:
        if self.structural_strata != STRUCTURAL_STRATA:
            raise ValueError("Context sufficiency structural strata changed")
        if {item.shape_id for item in self.shape_designs} != ALL_SHAPES:
            raise ValueError("Context sufficiency Shape coverage is incomplete")
        if self.contextual_conditions != CONTEXTUAL_CONDITIONS:
            raise ValueError("Context sufficiency conditions changed")
        if self.expected_actions != EXPECTED_ACTION_BY_CONDITION:
            raise ValueError("Context sufficiency action mapping changed")
        expected_conflicts = {
            f"{stratum_id}|{instance_index}": mismatch
            for (stratum_id, instance_index), mismatch in sorted(CONFLICT_MISMATCH_BY_CELL.items())
        }
        if self.single_conflict_mismatch_by_cell != expected_conflicts:
            raise ValueError("Frozen single-conflict allocation changed")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Context sufficiency historical populations are duplicated")
        if self.estimand_definition != StoppingShapePolicyDefinition():
            raise ValueError("Context sufficiency estimand changed")
        if self.protocol_id != _artifact_id(
            self, "protocol_id", "finance_stopping_context_sufficiency_protocol:"
        ):
            raise ValueError("Context sufficiency protocol identity is invalid")
        return self


class ContextSufficiencyPair(FrozenModel):
    pair_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    period_task_artifact_id: str = Field(min_length=1)
    definition_task_artifact_id: str = Field(min_length=1)
    shared_gold_evidence_ids: tuple[str, ...] = Field(min_length=2)
    shared_public_corpus_evidence_ids: tuple[str, ...] = Field(min_length=4)
    period_context_evidence_id: str = Field(min_length=1)
    definition_context_evidence_id: str = Field(min_length=1)
    period_expected_action: Literal["query_structured_fact"] = "query_structured_fact"
    definition_expected_action: Literal["normalize_metric_unit_period"] = (
        "normalize_metric_unit_period"
    )
    source_instruction_hash: str = Field(min_length=1)
    program_hash: str = Field(min_length=1)
    answer_schema_hash: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    action_set_hash: str = Field(min_length=1)
    tool_budget_hash: str = Field(min_length=1)
    period_prompt_bytes: int = Field(ge=1)
    definition_prompt_bytes: int = Field(ge=1)
    exact_prompt_length_match: Literal[True] = True
    both_branches_runtime_replay_passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_pair(self) -> ContextSufficiencyPair:
        if self.period_task_artifact_id == self.definition_task_artifact_id:
            raise ValueError("Context sufficiency pair collapsed to one task")
        if self.period_context_evidence_id == self.definition_context_evidence_id:
            raise ValueError("Context sufficiency conditions use one Evidence item")
        if self.period_prompt_bytes != self.definition_prompt_bytes:
            raise ValueError("Context sufficiency Prompt length is not matched")
        if self.pair_id != _artifact_id(
            self, "pair_id", "finance_stopping_context_sufficiency_pair:"
        ):
            raise ValueError("Context sufficiency pair identity is invalid")
        return self


class ContextSufficiencyStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: int = Field(ge=0)
    contextual_task_count: int = Field(ge=0)
    frozen_regression_task_count: int = Field(ge=0)
    pair_count: int = Field(ge=0)
    shape_task_counts: dict[str, int]
    stratum_task_counts: dict[str, int]
    operation_replay_rate: float = Field(ge=0, le=1)
    runtime_replay_rate: float = Field(ge=0, le=1)
    pair_same_core_task_rate: float = Field(ge=0, le=1)
    pair_same_public_corpus_rate: float = Field(ge=0, le=1)
    pair_same_program_rate: float = Field(ge=0, le=1)
    pair_same_answer_schema_rate: float = Field(ge=0, le=1)
    pair_same_action_set_rate: float = Field(ge=0, le=1)
    pair_same_tool_budget_rate: float = Field(ge=0, le=1)
    pair_same_prompt_bytes_rate: float = Field(ge=0, le=1)
    pair_single_context_change_rate: float = Field(ge=0, le=1)
    pair_action_flip_rate: float = Field(ge=0, le=1)
    pair_branch_replay_rate: float = Field(ge=0, le=1)
    pair_unique_applicable_action_rate: float = Field(ge=0, le=1)
    pair_public_context_sufficiency_rate: float = Field(ge=0, le=1)
    action_order_permutation_invariance_rate: float = Field(ge=0, le=1)
    action_label_rewrite_invariance_rate: float = Field(ge=0, le=1)
    context_removal_indeterminate_rate: float = Field(ge=0, le=1)
    context_swap_action_flip_rate: float = Field(ge=0, le=1)
    action_description_symmetry_rate: float = Field(ge=0, le=1)
    lexical_action_answer_leakage_count: int = Field(ge=0)
    lexical_context_action_overlap_count: int = Field(ge=0)
    opaque_identifier_branch_leakage_count: int = Field(ge=0)
    pair_local_overlap_only: bool
    cross_pair_evidence_disjoint: bool
    noncontextual_evidence_disjoint: bool
    historical_task_disjoint: bool
    historical_evidence_disjoint: bool
    historical_evidence_version_disjoint: bool
    historical_semantic_signature_disjoint: bool
    historical_materializer_disjoint: bool
    other_five_shape_mechanisms_frozen: bool
    thresholds_frozen: bool
    empirical_thresholds_preregistered: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_context_sufficiency_development",
        "context_sufficiency_population_repair_only",
    ]
    schema_version: str = CONTEXT_SUFFICIENCY_STATIC_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ContextSufficiencyStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Context sufficiency static decision is inconsistent")
        stage = (
            "flash_context_sufficiency_development"
            if expected
            else "context_sufficiency_population_repair_only"
        )
        if self.next_permitted_stage != stage:
            raise ValueError("Context sufficiency static transition is inconsistent")
        if self.audit_id != _artifact_id(
            self, "audit_id", "finance_stopping_context_sufficiency_static_audit:"
        ):
            raise ValueError("Context sufficiency static audit identity is invalid")
        return self


class FinanceStoppingContextSufficiencyPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_protocol: FrozenArtifactReference
    tasks: tuple[StoppingShapeTask, ...] = Field(min_length=48, max_length=48)
    task_stratum_instance_indices: dict[str, int]
    task_design_statuses: dict[str, Literal["frozen_regression", "context_sufficiency_redesign"]]
    task_expected_host_events: dict[str, tuple[str, str]]
    task_pair_ids: dict[str, str | None]
    task_context_conditions: dict[str, Literal["period", "definition"] | None]
    contextual_pairs: tuple[ContextSufficiencyPair, ...] = Field(min_length=4, max_length=4)
    static_audit: ContextSufficiencyStaticAudit
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    next_permitted_stage: Literal[
        "flash_context_sufficiency_development",
        "context_sufficiency_population_repair_only",
    ]
    schema_version: str = CONTEXT_SUFFICIENCY_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingContextSufficiencyPopulation:
        task_ids = {item.artifact.artifact_id for item in self.tasks}
        maps = (
            self.task_stratum_instance_indices,
            self.task_design_statuses,
            self.task_expected_host_events,
            self.task_pair_ids,
            self.task_context_conditions,
        )
        if len(task_ids) != EXPECTED_TASK_COUNT or any(set(item) != task_ids for item in maps):
            raise ValueError("Context sufficiency task maps are incomplete")
        pair_task_ids = {
            task_id
            for pair in self.contextual_pairs
            for task_id in (
                pair.period_task_artifact_id,
                pair.definition_task_artifact_id,
            )
        }
        if len(pair_task_ids) != CONTEXTUAL_TASK_COUNT:
            raise ValueError("Context sufficiency pair task coverage is incomplete")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("Context sufficiency population differs from its audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_context_sufficiency_population_implementation:",
        ):
            raise ValueError("Context sufficiency implementation identity is invalid")
        if self.population_id != _artifact_id(
            self, "population_id", "finance_stopping_context_sufficiency_population:"
        ):
            raise ValueError("Context sufficiency population identity is invalid")
        return self


class FinanceStoppingContextSufficiencyContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_protocol: FrozenArtifactReference
    source_population: FrozenArtifactReference
    source_execution_contract: FrozenArtifactReference
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    pair_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    task_pair_ids: dict[str, str | None]
    task_context_conditions: dict[str, Literal["period", "definition"] | None]
    expected_actions: dict[str, str] = Field(
        default_factory=lambda: dict(EXPECTED_ACTION_BY_CONDITION)
    )
    flip_thresholds: ContextSufficiencyThresholds
    requested_model_arm: Literal["flash"] = "flash"
    requested_rollout_count: Literal[384] = 384
    recursive_noninterference_required: Literal[True] = True
    raw_audit_before_aggregation_required: Literal[True] = True
    posthoc_task_deletion_authorized: Literal[False] = False
    finalizer_is_disaster_recovery_only: Literal[True] = True
    pro_api_call_count: Literal[0] = 0
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_context_sufficiency_development"] = (
        "flash_context_sufficiency_development"
    )
    schema_version: str = CONTEXT_SUFFICIENCY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingContextSufficiencyContract:
        if len(set(self.pair_ids)) != PAIR_COUNT:
            raise ValueError("Context sufficiency Contract pair identities are incomplete")
        if self.expected_actions != EXPECTED_ACTION_BY_CONDITION:
            raise ValueError("Context sufficiency Contract action mapping changed")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_context_sufficiency_implementation:",
        ):
            raise ValueError("Context sufficiency execution identity is invalid")
        if self.contract_id != _artifact_id(
            self, "contract_id", "finance_stopping_context_sufficiency_contract:"
        ):
            raise ValueError("Context sufficiency Contract identity is invalid")
        return self


class ContextSufficiencyPairResult(FrozenModel):
    pair_id: str = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    replicate_count: Literal[8] = 8
    period_action_correct_count: int = Field(ge=0, le=8)
    definition_action_correct_count: int = Field(ge=0, le=8)
    dual_correct_replicate_count: int = Field(ge=0, le=8)
    period_action_correct_rate: float = Field(ge=0, le=1)
    definition_action_correct_rate: float = Field(ge=0, le=1)
    dual_correct_rate: float = Field(ge=0, le=1)
    action_rate_difference: float = Field(ge=0, le=1)
    informative: bool

    @model_validator(mode="after")
    def validate_result(self) -> ContextSufficiencyPairResult:
        if self.period_action_correct_rate != self.period_action_correct_count / REPLICAS:
            raise ValueError("Contextual period action rate is inconsistent")
        if self.definition_action_correct_rate != self.definition_action_correct_count / REPLICAS:
            raise ValueError("Contextual definition action rate is inconsistent")
        if self.dual_correct_rate != self.dual_correct_replicate_count / REPLICAS:
            raise ValueError("Contextual dual-correct rate is inconsistent")
        if self.action_rate_difference != abs(
            self.period_action_correct_rate - self.definition_action_correct_rate
        ):
            raise ValueError("Contextual action-rate difference is inconsistent")
        return self


class FinanceStoppingContextSufficiencyMechanismReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    pair_results: tuple[ContextSufficiencyPairResult, ...] = Field(min_length=4, max_length=4)
    pair_replicate_denominator: Literal[32] = 32
    period_action_correct_count: int = Field(ge=0, le=32)
    definition_action_correct_count: int = Field(ge=0, le=32)
    dual_correct_replicate_count: int = Field(ge=0, le=32)
    contextual_flip_consistency: float = Field(ge=0, le=1)
    informative_pair_count: int = Field(ge=0, le=4)
    maximum_branch_action_rate_difference: float = Field(ge=0, le=1)
    branch_balanced_first_action_accuracy: float = Field(ge=0, le=1)
    constant_action_baseline: float = Field(ge=0, le=1)
    contextual_policy_gain: float = Field(ge=-1, le=1)
    branch_balanced_accuracy_bootstrap_lcb95: float = Field(ge=0, le=1)
    bootstrap_replicates: int = Field(ge=1)
    bootstrap_seed: int = Field(ge=0)
    thresholds: ContextSufficiencyThresholds
    passed: bool
    rejection_reasons: tuple[str, ...]
    schema_version: str = CONTEXT_SUFFICIENCY_MECHANISM_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingContextSufficiencyMechanismReport:
        if len({item.pair_id for item in self.pair_results}) != PAIR_COUNT:
            raise ValueError("Contextual Flip pair coverage is incomplete")
        if self.contextual_flip_consistency != (
            self.dual_correct_replicate_count / self.pair_replicate_denominator
        ):
            raise ValueError("Contextual Flip consistency is inconsistent")
        balanced = 0.5 * (
            self.period_action_correct_count / self.pair_replicate_denominator
            + self.definition_action_correct_count / self.pair_replicate_denominator
        )
        if self.branch_balanced_first_action_accuracy != balanced:
            raise ValueError("Context-sufficiency balanced accuracy is inconsistent")
        if self.constant_action_baseline != self.thresholds.constant_action_baseline:
            raise ValueError("Context-sufficiency constant baseline changed")
        if self.contextual_policy_gain != balanced - self.constant_action_baseline:
            raise ValueError("Context-sufficiency policy gain is inconsistent")
        if (
            self.bootstrap_replicates != self.thresholds.bootstrap_replicates
            or self.bootstrap_seed != self.thresholds.bootstrap_seed
        ):
            raise ValueError("Context-sufficiency bootstrap contract changed")
        if self.passed != (not self.rejection_reasons):
            raise ValueError("Contextual Flip decision is inconsistent")
        if self.report_id != _artifact_id(
            self, "report_id", "finance_stopping_context_sufficiency_mechanism_report:"
        ):
            raise ValueError("Contextual Flip report identity is invalid")
        return self


class FinanceStoppingContextSufficiencyReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    raw_audit_id: str = Field(min_length=1)
    raw_instrument_status: Literal["passed", "failed"]
    shape_analysis_authorized: bool
    shape_report_id: str | None = None
    mechanism_report_id: str | None = None
    successful_agent_outcome_count: int = Field(ge=0, le=384)
    fail_closed_behavior_outcome_count: int = Field(ge=0, le=384)
    full_valid_trajectory_count: int = Field(ge=0, le=384)
    boundary_candidate_admitted_count: int = Field(ge=0, le=4)
    runtime_control_pass_count: int = Field(ge=0, le=2)
    all_shape_contracts_passing: bool
    contextual_mechanism_fidelity_passing: bool
    all_v25_47_gates_passing: bool
    historical_shape_support_transferred: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "instrument_repair_only",
        "contextual_shape_redesign_only",
        "fresh_three_population_shape_policy_preparation",
    ]
    schema_version: str = CONTEXT_SUFFICIENCY_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingContextSufficiencyReport:
        if self.successful_agent_outcome_count + self.fail_closed_behavior_outcome_count != (
            EXPECTED_ROLLOUT_COUNT
        ):
            raise ValueError("Context sufficiency capability denominator changed")
        expected_all = bool(
            self.shape_analysis_authorized
            and self.all_shape_contracts_passing
            and self.contextual_mechanism_fidelity_passing
        )
        if self.all_v25_47_gates_passing != expected_all:
            raise ValueError("Context sufficiency overall decision is inconsistent")
        expected_stage = (
            "instrument_repair_only"
            if not self.shape_analysis_authorized
            else (
                "fresh_three_population_shape_policy_preparation"
                if expected_all
                else "contextual_shape_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Context sufficiency transition is inconsistent")
        if self.report_id != _artifact_id(
            self, "report_id", "finance_stopping_context_sufficiency_report:"
        ):
            raise ValueError("Context sufficiency report identity is invalid")
        return self


def prepare_context_sufficiency_protocol(
    *,
    source_v25_46_report_path: Path,
    source_v25_46_raw_audit_path: Path,
    source_v25_46_shape_report_path: Path,
    source_v25_46_mechanism_report_path: Path,
    source_v25_46_manifest_path: Path,
    source_v25_46_protocol_path: Path,
    source_v25_46_population_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingContextSufficiencyProtocol:
    if output_path.exists():
        raise ValueError("Context sufficiency protocol is immutable")
    paths = tuple(
        path.resolve()
        for path in (
            source_v25_46_report_path,
            source_v25_46_raw_audit_path,
            source_v25_46_shape_report_path,
            source_v25_46_mechanism_report_path,
            source_v25_46_manifest_path,
            source_v25_46_protocol_path,
            source_v25_46_population_path,
        )
    )
    (
        report_path,
        raw_path,
        shape_path,
        mechanism_path,
        manifest_path,
        source_protocol_path,
        source_population_path,
    ) = paths
    report_payload, raw_payload, shape_payload, mechanism_payload, manifest_payload = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in (report_path, raw_path, shape_path, mechanism_path, manifest_path)
    )
    source_protocol = FinanceStoppingContextualCounterfactualProtocol.model_validate_json(
        source_protocol_path.read_text(encoding="utf-8")
    )
    source_population = FinanceStoppingContextualCounterfactualPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    grammar_path = Path(source_protocol.source_grammar_protocol.path).resolve()
    grammar = load_stopping_shape_grammar_protocol(grammar_path)
    if not isinstance(grammar, FinanceStoppingInstrumentResetGrammarProtocol):
        raise ValueError("v25.47 requires the frozen source-registry Grammar")
    if not (
        report_payload.get("raw_instrument_status") == "passed"
        and report_payload.get("shape_analysis_authorized") is True
        and report_payload.get("boundary_candidate_admitted_count") == 4
        and report_payload.get("runtime_control_pass_count") == 2
        and report_payload.get("all_shape_contracts_passing") is True
        and report_payload.get("contextual_flip_passing") is False
        and report_payload.get("all_v25_46_gates_passing") is False
        and report_payload.get("next_permitted_stage") == "contextual_shape_redesign_only"
        and report_payload.get("production_contribution") == 0.0
    ):
        raise ValueError("v25.46 source state does not authorize context-sufficiency redesign")
    if not (
        raw_payload.get("instrument_status") == "passed"
        and raw_payload.get("shape_analysis_authorized") is True
        and raw_payload.get("rejection_reasons") == []
        and raw_payload.get("recursive_host_field_violation_count") == 0
        and raw_payload.get("recursive_host_marker_violation_count") == 0
    ):
        raise ValueError("v25.46 recursive noninterference lineage is not clean")
    if not (
        shape_payload.get("all_shapes_contract_passing") is True
        and shape_payload.get("boundary_candidate_admitted_count") == 4
        and shape_payload.get("runtime_control_pass_count") == 2
    ):
        raise ValueError("v25.46 Shape boundary support changed")
    if not (
        mechanism_payload.get("passed") is False
        and mechanism_payload.get("contextual_flip_consistency") == 0.0625
        and mechanism_payload.get("informative_pair_count") == 2
        and mechanism_payload.get("rejection_reasons")
        == ["minimum_contextual_flip_consistency", "minimum_informative_pair_count"]
    ):
        raise ValueError("v25.46 mechanism-fidelity failure changed")
    if manifest_payload.get("production_contribution") != 0.0:
        raise ValueError("v25.46 unexpectedly authorized production Contribution")
    current_population = _reference(source_population_path, source_population.population_id)
    historical = tuple(
        sorted(
            (*source_protocol.historical_population_references, current_population),
            key=lambda item: item.artifact_id,
        )
    )
    if len({item.artifact_id for item in historical}) != len(historical):
        raise ValueError("v25.47 freshness exclusion set contains duplicates")
    values = {
        "run_id": run_id,
        "source_v25_46_report": _reference(report_path, str(report_payload["report_id"])),
        "source_v25_46_raw_audit": _reference(raw_path, str(raw_payload["audit_id"])),
        "source_v25_46_shape_report": _reference(shape_path, str(shape_payload["report_id"])),
        "source_v25_46_mechanism_report": _reference(
            mechanism_path, str(mechanism_payload["report_id"])
        ),
        "source_v25_46_manifest": _reference(
            manifest_path,
            canonical_hash(
                manifest_payload,
                prefix="finance_stopping_contextual_counterfactual_manifest:",
            ),
        ),
        "source_v25_46_protocol": _reference(source_protocol_path, source_protocol.protocol_id),
        "source_v25_46_population": current_population,
        "source_grammar_protocol": source_protocol.source_grammar_protocol,
        "source_grammar_population": source_protocol.source_grammar_population,
        "source_finance_artifacts": source_protocol.source_finance_artifacts,
        "source_calibration_contract": source_protocol.source_calibration_contract,
        "historical_population_references": historical,
        "shape_designs": grammar.shape_designs,
        "shape_thresholds": grammar.thresholds,
    }
    provisional = FinanceStoppingContextSufficiencyProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceStoppingContextSufficiencyProtocol(
        protocol_id=_artifact_id(
            provisional,
            "protocol_id",
            "finance_stopping_context_sufficiency_protocol:",
        ),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    return protocol


def build_context_sufficiency_population(
    *,
    protocol_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceStoppingContextSufficiencyPopulation:
    output_path = output_dir / "finance_stopping_context_sufficiency_population.json"
    if output_path.exists():
        raise ValueError("Context sufficiency population is immutable")
    protocol_path = protocol_path.resolve()
    protocol = FinanceStoppingContextSufficiencyProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    excluded = _collect_excluded_identities(protocol.historical_population_references)
    pool = _load_evidence_pool(Path(protocol.source_finance_artifacts.path))
    evidence_pool = tuple(pool.public.values())
    one_difference_index = _build_one_difference_index(
        evidence_pool, fields=("period", "definition", "payload_context")
    )
    builder = _CapabilityTaskBuilder(pool, sampling_salt=f"{run_id}:context-sufficiency")
    contextual_target_ids = _contextual_target_ids(
        evidence_pool=evidence_pool,
        one_difference_index=one_difference_index,
        blocked_ids=set(excluded["evidence_id"]),
        blocked_versions=set(excluded["evidence_version_id"]),
    )
    candidate_cache = {
        (family, tier): _bounded_candidate_rows(
            builder,
            family,
            tier,
            contextual_target_ids=contextual_target_ids,
            sampling_salt=f"{run_id}:candidate-pool:{stratum_id}",
        )
        for stratum_id, family, tier in protocol.structural_strata
    }
    used_ids = set(excluded["evidence_id"])
    used_versions = set(excluded["evidence_version_id"])
    tasks: list[StoppingShapeTask] = []
    pairs: list[ContextSufficiencyPair] = []
    instance_indices: dict[str, int] = {}
    statuses: dict[str, Literal["frozen_regression", "context_sufficiency_redesign"]] = {}
    pair_ids: dict[str, str | None] = {}
    conditions: dict[str, Literal["period", "definition"] | None] = {}
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}

    contextual_design = design_by_shape["contextual_resolution_choice"]
    for stratum_id, family, tier in protocol.structural_strata:
        pair_tasks, pair = _materialize_contextual_pair(
            builder=builder,
            candidate_rows=candidate_cache[(family, tier)],
            design=contextual_design,
            stratum_id=stratum_id,
            family=family,
            tier=tier,
            one_difference_index=one_difference_index,
            used_ids=used_ids,
            used_versions=used_versions,
            sampling_salt=f"{run_id}:contextual:{stratum_id}",
        )
        tasks.extend(pair_tasks)
        pairs.append(pair)
        for instance_index, (condition, task) in enumerate(
            zip(CONTEXTUAL_CONDITIONS, pair_tasks, strict=True)
        ):
            task_id = task.artifact.artifact_id
            instance_indices[task_id] = instance_index
            statuses[task_id] = "context_sufficiency_redesign"
            pair_ids[task_id] = pair.pair_id
            conditions[task_id] = cast(Any, condition)
        pair_evidence = {item.evidence_id for item in pair_tasks[0].artifact.public_corpus.evidence}
        pair_versions = {
            item.evidence_version_id for item in pair_tasks[0].artifact.public_corpus.evidence
        }
        used_ids.update(pair_evidence)
        used_versions.update(pair_versions)

    for shape_id in sorted(ALL_SHAPES - {"contextual_resolution_choice"}):
        design = design_by_shape[shape_id]
        for stratum_id, family, tier in protocol.structural_strata:
            for instance_index in range(2):
                task = _materialize_shape_policy_task(
                    builder=builder,
                    candidate_rows=candidate_cache[(family, tier)],
                    design=design,
                    stratum_id=stratum_id,
                    family=family,
                    tier=tier,
                    instance_index=instance_index,
                    evidence_pool=evidence_pool,
                    one_difference_index=one_difference_index,
                    conflict_mismatch_field=(
                        protocol.single_conflict_mismatch_by_cell[f"{stratum_id}|{instance_index}"]
                        if shape_id == "single_dimension_conflict"
                        else None
                    ),
                    target_role_index=TARGET_ROLE_INDEX_BY_SHAPE.get(shape_id),
                    used_ids=used_ids,
                    used_versions=used_versions,
                    sampling_salt=f"{run_id}:{shape_id}:{stratum_id}:{instance_index}",
                )
                tasks.append(task)
                task_id = task.artifact.artifact_id
                instance_indices[task_id] = instance_index
                statuses[task_id] = "frozen_regression"
                pair_ids[task_id] = None
                conditions[task_id] = None
                used_ids.update(item.evidence_id for item in task.artifact.public_corpus.evidence)
                used_versions.update(
                    item.evidence_version_id for item in task.artifact.public_corpus.evidence
                )

    frozen_tasks = tuple(tasks)
    host_events = {
        item.artifact.artifact_id: item.scenario.expected_host_events for item in frozen_tasks
    }
    audit = make_context_sufficiency_static_audit(
        frozen_tasks,
        tuple(pairs),
        protocol,
        excluded=excluded,
        task_stratum_instance_indices=instance_indices,
        task_design_statuses=statuses,
        task_pair_ids=pair_ids,
        task_context_conditions=conditions,
    )
    implementation = _population_implementation_manifest()
    values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "tasks": frozen_tasks,
        "task_stratum_instance_indices": instance_indices,
        "task_design_statuses": statuses,
        "task_expected_host_events": host_events,
        "task_pair_ids": pair_ids,
        "task_context_conditions": conditions,
        "contextual_pairs": tuple(pairs),
        "static_audit": audit,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix=("finance_stopping_context_sufficiency_population_implementation:"),
        ),
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = FinanceStoppingContextSufficiencyPopulation.model_construct(
        population_id="pending", **values
    )
    population = FinanceStoppingContextSufficiencyPopulation(
        population_id=_artifact_id(
            provisional,
            "population_id",
            "finance_stopping_context_sufficiency_population:",
        ),
        **values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_context_sufficiency_static_audit.json",
        audit.model_dump(mode="json"),
    )
    (output_dir / "finance_stopping_context_sufficiency_population_report.md").write_text(
        _render_population_report(population), encoding="utf-8"
    )
    return population


def _candidate_rows(
    builder: _CapabilityTaskBuilder, family: str, tier: DifficultyTier
) -> Iterable[Any]:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (  # noqa: E501
        _candidate_iterator,
    )

    return _candidate_iterator(builder, family, tier)


def _contextual_target_ids(
    *,
    evidence_pool: Sequence[EvidenceItem],
    one_difference_index: Any,
    blocked_ids: set[str],
    blocked_versions: set[str],
) -> frozenset[str]:
    target_ids = set()
    for target in evidence_pool:
        if target.evidence_id in blocked_ids or target.evidence_version_id in blocked_versions:
            continue
        definition = _exact_context_candidates(
            target=target,
            mismatch_field="definition",
            one_difference_index=one_difference_index,
            blocked_ids=blocked_ids | {target.evidence_id},
            blocked_versions=blocked_versions | {target.evidence_version_id},
        )
        if not definition:
            continue
        period = _exact_context_candidates(
            target=target,
            mismatch_field="period",
            one_difference_index=one_difference_index,
            blocked_ids=blocked_ids | {target.evidence_id},
            blocked_versions=blocked_versions | {target.evidence_version_id},
        )
        if period and _matched_context_items(
            period, definition, sampling_salt="contextual-target-capacity"
        ):
            target_ids.add(target.evidence_id)
    if not target_ids:
        raise ValueError("real Finance Evidence has no context sufficiency targets")
    return frozenset(target_ids)


def _bounded_candidate_rows(
    builder: _CapabilityTaskBuilder,
    family: str,
    tier: DifficultyTier,
    *,
    contextual_target_ids: frozenset[str],
    sampling_salt: str,
) -> tuple[Any, ...]:
    generic: list[tuple[int, int, Any]] = []
    contextual: list[tuple[int, int, Any]] = []
    target_index = TARGET_ROLE_INDEX_BY_SHAPE["contextual_resolution_choice"]
    for index, row in enumerate(_candidate_rows(builder, family, tier)):
        gold = row[0]
        rank = int(
            canonical_hash(
                {
                    "sampling_salt": sampling_salt,
                    "gold_versions": tuple(item.evidence_version_id for item in gold),
                },
                prefix="finance_contextual_bounded_candidate_pool:",
            ).split(":")[-1],
            16,
        )
        _retain_lowest_rank(generic, rank, index, row, CANDIDATE_POOL_LIMIT)
        if gold[target_index].evidence_id in contextual_target_ids:
            _retain_lowest_rank(
                contextual,
                rank,
                index,
                row,
                CONTEXTUAL_CANDIDATE_POOL_LIMIT,
            )
    selected: dict[tuple[str, ...], Any] = {}
    for _, _, row in (*generic, *contextual):
        identity = tuple(item.evidence_version_id for item in row[0])
        selected.setdefault(identity, row)
    return tuple(selected[key] for key in sorted(selected))


def _retain_lowest_rank(
    heap: list[tuple[int, int, Any]],
    rank: int,
    index: int,
    row: Any,
    limit: int,
) -> None:
    entry = (-rank, index, row)
    if len(heap) < limit:
        heapq.heappush(heap, entry)
        return
    if rank < -heap[0][0]:
        heapq.heapreplace(heap, entry)


def _counterfactual_actions() -> tuple[FinanceStoppingResolutionAction, ...]:
    return (
        FinanceStoppingResolutionAction(
            tool_id="normalize_metric_unit_period",
            applicable_when=ACTION_FUNCTION_BY_TOOL["normalize_metric_unit_period"],
        ),
        FinanceStoppingResolutionAction(
            tool_id="open_document",
            applicable_when=ACTION_FUNCTION_BY_TOOL["open_document"],
        ),
        FinanceStoppingResolutionAction(
            tool_id="query_structured_fact",
            applicable_when=ACTION_FUNCTION_BY_TOOL["query_structured_fact"],
        ),
    )


def _public_relation_state(
    condition: Literal["period", "definition"],
) -> FinanceStoppingPublicRelationState:
    return FinanceStoppingPublicRelationState(
        observation_identity_relation=("unresolved" if condition == "period" else "aligned"),
        meaning_compatibility_relation=("unresolved" if condition == "definition" else "aligned"),
        measurement_compatibility_relation="aligned",
        authority_relation="aligned",
    )


def _publicly_applicable_action_labels(
    relation_state: Mapping[str, Any],
    actions: Sequence[tuple[str, str]],
) -> tuple[str, ...]:
    unresolved = tuple(
        key
        for key, value in relation_state.items()
        if key.endswith("_relation") and value == "unresolved"
    )
    if len(unresolved) != 1:
        return ()
    expected_function = RELATION_TO_ACTION_FUNCTION.get(unresolved[0])
    if expected_function is None:
        return ()
    return tuple(label for label, function in actions if function == expected_function)


def _public_action_rows(
    decision: FinanceStoppingShapeDecisionContract | None,
) -> tuple[tuple[str, str], ...]:
    if decision is None:
        return ()
    return tuple(
        (item.tool_id, item.applicable_when) for item in decision.available_resolution_actions
    )


def _public_relation_payload(
    decision: FinanceStoppingShapeDecisionContract | None,
) -> dict[str, Any]:
    if decision is None or decision.public_relation_state is None:
        return {}
    return decision.public_relation_state.model_dump(mode="json")


def _action_descriptions_are_symmetric(
    actions: Sequence[tuple[str, str]],
) -> bool:
    descriptions = tuple(description for _, description in actions)
    lengths = tuple(len(item.split()) for item in descriptions)
    first_words = tuple(item.split()[0] for item in descriptions if item.split())
    return bool(
        len(descriptions) == 3
        and len(set(descriptions)) == 3
        and len(first_words) == 3
        and len(set(first_words)) == 3
        and max(lengths) - min(lengths) <= 1
        and all(description == description.lower() for description in descriptions)
    )


def _lexical_context_action_overlap(
    decision: FinanceStoppingShapeDecisionContract | None,
) -> bool:
    if decision is None or decision.public_relation_state is None:
        return True
    relation_tokens = {
        token
        for key in decision.public_relation_state.model_dump(mode="json")
        if key.endswith("_relation")
        for token in key.removesuffix("_relation").split("_")
    }
    action_tokens = {
        token.strip(".,:;()")
        for _, description in _public_action_rows(decision)
        for token in description.lower().split()
    }
    return bool(relation_tokens & action_tokens)


def _opaque_identifier_has_branch_label(pair: ContextSufficiencyPair) -> bool:
    opaque_ids = (
        pair.pair_id,
        pair.period_task_artifact_id,
        pair.definition_task_artifact_id,
        pair.period_context_evidence_id,
        pair.definition_context_evidence_id,
    )
    forbidden_fragments = (":period", ":definition", "_period", "_definition")
    return any(
        fragment in identifier.lower()
        for identifier in opaque_ids
        for fragment in forbidden_fragments
    )


def _materialize_contextual_pair(
    *,
    builder: _CapabilityTaskBuilder,
    candidate_rows: Sequence[Any],
    design: StoppingShapePolicyDesign,
    stratum_id: str,
    family: str,
    tier: DifficultyTier,
    one_difference_index: Any,
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> tuple[tuple[StoppingShapeTask, StoppingShapeTask], ContextSufficiencyPair]:
    target_role_index = TARGET_ROLE_INDEX_BY_SHAPE["contextual_resolution_choice"]
    ordered = _ordered_shape_candidates(
        candidate_rows=candidate_rows,
        used_ids=used_ids,
        used_versions=used_versions,
        sampling_salt=sampling_salt,
    )
    rejections: Counter[str] = Counter()
    for gold, program, source_instruction, projection in ordered:
        rejections["candidate_attempted"] += 1
        gold_ids = {item.evidence_id for item in gold}
        gold_versions = {item.evidence_version_id for item in gold}
        if gold_ids & used_ids or gold_versions & used_versions:
            rejections["gold_identity_reserved"] += 1
            continue
        target = gold[target_role_index]
        period = _exact_context_candidates(
            target=target,
            mismatch_field="period",
            one_difference_index=one_difference_index,
            blocked_ids=used_ids | gold_ids,
            blocked_versions=used_versions | gold_versions,
        )
        definition = _exact_context_candidates(
            target=target,
            mismatch_field="definition",
            one_difference_index=one_difference_index,
            blocked_ids=used_ids | gold_ids,
            blocked_versions=used_versions | gold_versions,
        )
        matched = _matched_context_items(period, definition, sampling_salt=sampling_salt)
        if matched is None:
            rejections["matched_context_pair_unavailable"] += 1
            continue
        period_item, definition_item = matched
        recovery = tuple(
            RecoveryBranch(
                distractor_evidence_id=item.evidence_id,
                mismatch_fields=_minimum_mismatch_fields(item, gold),
            )
            for item in (period_item, definition_item)
        )
        try:
            base_artifact = builder._materialize(
                family=family,
                tier=tier,
                gold=gold,
                distractors=(period_item, definition_item),
                recovery_branches=recovery,
                program=program,
                instruction=source_instruction,
                answer_projection=projection,
            )
        except ProgramExecutionError:
            rejections["program_execution_failed"] += 1
            continue
        branch_tasks = tuple(
            _materialize_contextual_branch(
                base_artifact=base_artifact,
                design=design,
                stratum_id=stratum_id,
                family=family,
                tier=tier,
                gold=gold,
                active_item=active_item,
                mismatch_field=condition,
                program=program,
                source_instruction=source_instruction,
                projection=projection,
                sampling_salt=f"{sampling_salt}:{condition}",
            )
            for condition, active_item in zip(
                CONTEXTUAL_CONDITIONS,
                (period_item, definition_item),
                strict=True,
            )
        )
        if not all(item.runtime_replay.passed for item in branch_tasks):
            rejections["runtime_replay_failed"] += 1
            continue
        public_corpus_ids = tuple(
            item.evidence_id for item in branch_tasks[0].artifact.public_corpus.evidence
        )
        prompt_bytes = tuple(_public_prompt_bytes(item) for item in branch_tasks)
        if prompt_bytes[0] != prompt_bytes[1]:
            rejections["prompt_length_mismatch"] += 1
            continue
        shared = {
            "stratum_id": stratum_id,
            "period_task_artifact_id": branch_tasks[0].artifact.artifact_id,
            "definition_task_artifact_id": branch_tasks[1].artifact.artifact_id,
            "shared_gold_evidence_ids": tuple(item.evidence_id for item in gold),
            "shared_public_corpus_evidence_ids": public_corpus_ids,
            "period_context_evidence_id": period_item.evidence_id,
            "definition_context_evidence_id": definition_item.evidence_id,
            "source_instruction_hash": canonical_hash(
                source_instruction, prefix="finance_contextual_source_instruction:"
            ),
            "program_hash": canonical_hash(
                branch_tasks[0].artifact.task.public.program_skeleton,
                prefix="finance_contextual_program:",
            ),
            "answer_schema_hash": canonical_hash(
                branch_tasks[0].artifact.task.public.answer_schema,
                prefix="finance_contextual_answer_schema:",
            ),
            "public_corpus_hash": canonical_hash(
                branch_tasks[0].artifact.public_corpus,
                prefix="finance_contextual_public_corpus:",
            ),
            "action_set_hash": canonical_hash(
                _counterfactual_actions(), prefix="finance_contextual_action_set:"
            ),
            "tool_budget_hash": _tool_budget_hash(branch_tasks[0]),
            "period_prompt_bytes": prompt_bytes[0],
            "definition_prompt_bytes": prompt_bytes[1],
        }
        provisional_pair = ContextSufficiencyPair.model_construct(pair_id="pending", **shared)
        pair = ContextSufficiencyPair(
            pair_id=_artifact_id(
                provisional_pair,
                "pair_id",
                "finance_stopping_context_sufficiency_pair:",
            ),
            **shared,
        )
        return cast(tuple[StoppingShapeTask, StoppingShapeTask], branch_tasks), pair
    raise ValueError(
        f"real Finance Evidence cannot support contextual pair/{stratum_id}; "
        f"rejections={dict(sorted(rejections.items()))}"
    )


def _exact_context_candidates(
    *,
    target: EvidenceItem,
    mismatch_field: Literal["period", "definition"],
    one_difference_index: Any,
    blocked_ids: set[str],
    blocked_versions: set[str],
) -> tuple[EvidenceItem, ...]:
    return tuple(
        item
        for item in _indexed_one_difference_candidates(
            one_difference_index=one_difference_index,
            gold=(target,),
            mismatch_field=mismatch_field,
        )
        if item.evidence_id not in blocked_ids
        and item.evidence_version_id not in blocked_versions
        and _minimum_mismatch_fields(item, (target,)) == (mismatch_field,)
    )


def _matched_context_items(
    period: Sequence[EvidenceItem],
    definition: Sequence[EvidenceItem],
    *,
    sampling_salt: str,
) -> tuple[EvidenceItem, EvidenceItem] | None:
    rows = []
    for period_item in period:
        period_bytes = _observed_record_bytes(period_item)
        for definition_item in definition:
            if period_bytes != _observed_record_bytes(definition_item):
                continue
            rank = canonical_hash(
                {
                    "sampling_salt": sampling_salt,
                    "period_version": period_item.evidence_version_id,
                    "definition_version": definition_item.evidence_version_id,
                },
                prefix="finance_context_sufficiency_neighbor_order:",
            )
            rows.append((rank, period_item, definition_item))
    if not rows:
        return None
    _, period_item, definition_item = min(rows, key=lambda row: row[0])
    return period_item, definition_item


def _materialize_contextual_branch(
    *,
    base_artifact: Any,
    design: StoppingShapePolicyDesign,
    stratum_id: str,
    family: str,
    tier: DifficultyTier,
    gold: tuple[EvidenceItem, ...],
    active_item: EvidenceItem,
    mismatch_field: Literal["period", "definition"],
    program: Any,
    source_instruction: str,
    projection: Any,
    sampling_salt: str,
) -> StoppingShapeTask:
    target_role_index = TARGET_ROLE_INDEX_BY_SHAPE["contextual_resolution_choice"]
    base_scenario = _make_scenario(
        design.spec,
        gold,
        active_item,
        base_artifact.projected_expected_output,
    )
    decision = FinanceStoppingShapeDecisionContract(
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION,
        contract_kind=CONTEXT_SUFFICIENCY_CONTRACT_KIND,
        observed_conflict_signal=(
            "One public relation remains unresolved after required record selection."
        ),
        observed_evidence_state=_observed_evidence_state(
            gold=gold,
            distractor=active_item,
            mismatch_field=mismatch_field,
            target_role_index=target_role_index,
        ),
        public_relation_state=_public_relation_state(mismatch_field),
        shared_resolution_policy=SHARED_RESOLUTION_POLICY,
        oracle_conflict_dimension={
            "period": "temporal_alignment",
            "definition": "source_definition_compatibility",
        }[mismatch_field],
        state_activation_phase="after_required_evidence_selection_before_calculation",
        available_resolution_actions=_counterfactual_actions(),
        resolution_step_count=2,
    )
    scenario = make_finance_submechanism_scenario(
        submechanism_id=base_scenario.submechanism_id,
        parent_mechanism_id=base_scenario.parent_mechanism_id,
        intervention_kind=base_scenario.intervention_kind,
        expected_host_events=base_scenario.expected_host_events,
        evidence_roles=base_scenario.evidence_roles,
        public_resolution_hint=(
            "Select every required record, apply the shared public relation policy using one "
            "registered action, calculate the requested result, and independently cross-check it."
        ),
        untrusted_candidate=base_scenario.untrusted_candidate,
        canonical_candidate=base_scenario.canonical_candidate,
        repair_target_field=base_scenario.repair_target_field,
        stopping_shape_decision_contract=decision,
    )
    artifact = _freeze_scenario(
        base_artifact,
        scenario,
        source_instruction=source_instruction,
        projection=projection,
    )
    replay = replay_submechanism_runtime(artifact, scenario)
    signature = canonical_hash(
        {
            "shape_id": design.shape_id,
            "family": family,
            "tier": tier,
            "stratum_id": stratum_id,
            "gold_versions": tuple(item.evidence_version_id for item in gold),
            "program": program,
            "projection": projection,
            "active_context_version": active_item.evidence_version_id,
            "mismatch_field": mismatch_field,
            "decision_contract": decision,
            "estimand_definition": StoppingShapePolicyDefinition(),
        },
        prefix="finance_stopping_context_sufficiency_semantics:",
    )
    difficulty = _difficulty_vector(
        cast(Any, design), artifact, design.spec, family=family, tier=tier
    )
    materializer_hash = canonical_hash(
        {
            "shape_id": design.shape_id,
            "stratum_id": stratum_id,
            "spec_hash": design.spec.spec_hash,
            "artifact_id": artifact.artifact_id,
            "scenario": scenario,
            "difficulty": difficulty,
            "sampling_salt": sampling_salt,
            "policy": submechanism_policy_manifest()[scenario.intervention_kind],
        },
        prefix="finance_stopping_context_sufficiency_materializer:",
    )
    values = {
        "shape_id": design.shape_id,
        "shape_role": design.shape_role,
        "stratum_id": stratum_id,
        "spec_hash": design.spec.spec_hash,
        "artifact": artifact,
        "scenario": scenario,
        "runtime_replay": replay,
        "difficulty": difficulty,
        "source_semantic_signature": signature,
        "materializer_hash": materializer_hash,
    }
    provisional = StoppingShapeTask.model_construct(task_record_id="pending", **values)
    return StoppingShapeTask(task_record_id=stopping_shape_task_id(provisional), **values)


def make_context_sufficiency_static_audit(
    tasks: Sequence[StoppingShapeTask],
    pairs: Sequence[ContextSufficiencyPair],
    protocol: FinanceStoppingContextSufficiencyProtocol,
    *,
    excluded: Mapping[str, set[str]],
    task_stratum_instance_indices: Mapping[str, int],
    task_design_statuses: Mapping[
        str, Literal["frozen_regression", "context_sufficiency_redesign"]
    ],
    task_pair_ids: Mapping[str, str | None],
    task_context_conditions: Mapping[str, Literal["period", "definition"] | None],
) -> ContextSufficiencyStaticAudit:
    task_by_id = {item.artifact.artifact_id: item for item in tasks}
    task_ids = set(task_by_id)
    shape_counts = Counter(item.shape_id for item in tasks)
    stratum_counts = Counter(item.stratum_id for item in tasks)
    contextual_ids = {
        item.artifact.artifact_id
        for item in tasks
        if item.shape_id == "contextual_resolution_choice"
    }
    frozen_ids = task_ids - contextual_ids
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}

    pair_checks: dict[str, list[bool]] = defaultdict(list)
    pair_task_sets: dict[str, set[str]] = {}
    pair_evidence_sets: dict[str, set[str]] = {}
    lexical_leaks = 0
    lexical_context_action_overlaps = 0
    opaque_identifier_branch_leaks = 0
    for pair in pairs:
        period_task = task_by_id.get(pair.period_task_artifact_id)
        definition_task = task_by_id.get(pair.definition_task_artifact_id)
        if period_task is None or definition_task is None:
            for key in (
                "same_core",
                "same_corpus",
                "same_program",
                "same_answer",
                "same_actions",
                "same_budget",
                "same_prompt",
                "single_context",
                "action_flip",
                "branch_replay",
                "unique_applicable_action",
                "public_context_sufficiency",
                "action_order_invariance",
                "action_label_invariance",
                "context_removal_indeterminate",
                "context_swap_flip",
                "action_description_symmetry",
            ):
                pair_checks[key].append(False)
            continue
        pair_task_sets[pair.pair_id] = {
            pair.period_task_artifact_id,
            pair.definition_task_artifact_id,
        }
        pair_evidence_sets[pair.pair_id] = set(pair.shared_public_corpus_evidence_ids)
        period_decision = period_task.scenario.stopping_shape_decision_contract
        definition_decision = definition_task.scenario.stopping_shape_decision_contract
        period_corpus = tuple(
            item.evidence_id for item in period_task.artifact.public_corpus.evidence
        )
        definition_corpus = tuple(
            item.evidence_id for item in definition_task.artifact.public_corpus.evidence
        )
        pair_checks["same_core"].append(
            _paired_core_hash(period_task) == _paired_core_hash(definition_task)
            and tuple(item.evidence_id for item in period_task.scenario.evidence_roles)
            == pair.shared_gold_evidence_ids
            and tuple(item.evidence_id for item in definition_task.scenario.evidence_roles)
            == pair.shared_gold_evidence_ids
        )
        pair_checks["same_corpus"].append(
            period_corpus == definition_corpus == pair.shared_public_corpus_evidence_ids
            and canonical_hash(
                period_task.artifact.public_corpus,
                prefix="finance_contextual_public_corpus:",
            )
            == pair.public_corpus_hash
        )
        pair_checks["same_program"].append(
            period_task.artifact.task.public.program_skeleton
            == definition_task.artifact.task.public.program_skeleton
            and canonical_hash(
                period_task.artifact.task.public.program_skeleton,
                prefix="finance_contextual_program:",
            )
            == pair.program_hash
        )
        pair_checks["same_answer"].append(
            period_task.artifact.task.public.answer_schema
            == definition_task.artifact.task.public.answer_schema
            and canonical_hash(
                period_task.artifact.task.public.answer_schema,
                prefix="finance_contextual_answer_schema:",
            )
            == pair.answer_schema_hash
        )
        pair_checks["same_actions"].append(
            period_decision is not None
            and definition_decision is not None
            and period_decision.available_resolution_actions
            == definition_decision.available_resolution_actions
            == _counterfactual_actions()
            and canonical_hash(
                period_decision.available_resolution_actions,
                prefix="finance_contextual_action_set:",
            )
            == pair.action_set_hash
        )
        pair_checks["same_budget"].append(
            _tool_budget_hash(period_task)
            == _tool_budget_hash(definition_task)
            == pair.tool_budget_hash
        )
        pair_checks["same_prompt"].append(
            _public_prompt_bytes(period_task)
            == _public_prompt_bytes(definition_task)
            == pair.period_prompt_bytes
            == pair.definition_prompt_bytes
        )
        pair_checks["single_context"].append(
            _single_context_counterfactual_ready(period_decision, definition_decision)
        )
        pair_checks["action_flip"].append(
            _expected_action(period_decision) == EXPECTED_ACTION_BY_CONDITION["period"]
            and _expected_action(definition_decision) == EXPECTED_ACTION_BY_CONDITION["definition"]
            and _expected_action(period_decision) != _expected_action(definition_decision)
        )
        pair_checks["branch_replay"].append(
            period_task.runtime_replay.passed
            and definition_task.runtime_replay.passed
            and pair.both_branches_runtime_replay_passed
        )
        period_state = _public_relation_payload(period_decision)
        definition_state = _public_relation_payload(definition_decision)
        period_actions = _public_action_rows(period_decision)
        definition_actions = _public_action_rows(definition_decision)
        period_applicable = _publicly_applicable_action_labels(period_state, period_actions)
        definition_applicable = _publicly_applicable_action_labels(
            definition_state, definition_actions
        )
        expected_period = EXPECTED_ACTION_BY_CONDITION["period"]
        expected_definition = EXPECTED_ACTION_BY_CONDITION["definition"]
        pair_checks["unique_applicable_action"].append(
            len(period_applicable) == len(definition_applicable) == 1
        )
        pair_checks["public_context_sufficiency"].append(
            period_applicable == (expected_period,)
            and definition_applicable == (expected_definition,)
            and period_decision is not None
            and definition_decision is not None
            and period_decision.shared_resolution_policy
            == definition_decision.shared_resolution_policy
            == SHARED_RESOLUTION_POLICY
        )
        pair_checks["action_order_invariance"].append(
            _publicly_applicable_action_labels(period_state, tuple(reversed(period_actions)))
            == period_applicable
            and _publicly_applicable_action_labels(
                definition_state, tuple(reversed(definition_actions))
            )
            == definition_applicable
        )
        relabeled_period = tuple(
            (f"candidate_{index}", description)
            for index, (_, description) in enumerate(period_actions)
        )
        relabeled_definition = tuple(
            (f"candidate_{index}", description)
            for index, (_, description) in enumerate(definition_actions)
        )
        pair_checks["action_label_invariance"].append(
            len(_publicly_applicable_action_labels(period_state, relabeled_period)) == 1
            and len(_publicly_applicable_action_labels(definition_state, relabeled_definition)) == 1
        )
        removed_period = {
            key: ("aligned" if key.endswith("_relation") else value)
            for key, value in period_state.items()
        }
        removed_definition = {
            key: ("aligned" if key.endswith("_relation") else value)
            for key, value in definition_state.items()
        }
        pair_checks["context_removal_indeterminate"].append(
            not _publicly_applicable_action_labels(removed_period, period_actions)
            and not _publicly_applicable_action_labels(removed_definition, definition_actions)
        )
        pair_checks["context_swap_flip"].append(
            period_applicable != definition_applicable
            and _publicly_applicable_action_labels(definition_state, period_actions)
            == (expected_definition,)
            and _publicly_applicable_action_labels(period_state, definition_actions)
            == (expected_period,)
        )
        pair_checks["action_description_symmetry"].append(
            _action_descriptions_are_symmetric(period_actions)
            and _action_descriptions_are_symmetric(definition_actions)
        )
        lexical_leaks += int(_contextual_lexical_leak(period_decision))
        lexical_leaks += int(_contextual_lexical_leak(definition_decision))
        lexical_context_action_overlaps += int(_lexical_context_action_overlap(period_decision))
        lexical_context_action_overlaps += int(_lexical_context_action_overlap(definition_decision))
        opaque_identifier_branch_leaks += int(_opaque_identifier_has_branch_label(pair))

    evidence_occurrences: dict[str, set[str]] = defaultdict(set)
    evidence_versions: dict[str, set[str]] = defaultdict(set)
    for task in tasks:
        task_id = task.artifact.artifact_id
        for item in task.artifact.public_corpus.evidence:
            evidence_occurrences[item.evidence_id].add(task_id)
            evidence_versions[item.evidence_version_id].add(task_id)
    allowed_overlaps = {
        evidence_id: pair_task_sets[pair_id]
        for pair_id, evidence_ids in pair_evidence_sets.items()
        for evidence_id in evidence_ids
    }
    pair_local_overlap_only = all(
        len(task_set) == 1 or task_set == allowed_overlaps.get(evidence_id)
        for evidence_id, task_set in evidence_occurrences.items()
    )
    pair_ids_ordered = tuple(pair.pair_id for pair in pairs)
    cross_pair_disjoint = all(
        not pair_evidence_sets[left] & pair_evidence_sets[right]
        for index, left in enumerate(pair_ids_ordered)
        for right in pair_ids_ordered[index + 1 :]
    )
    noncontextual_evidence = [
        item.evidence_id
        for task in tasks
        if task.artifact.artifact_id in frozen_ids
        for item in task.artifact.public_corpus.evidence
    ]
    contextual_evidence = {
        item.evidence_id
        for task in tasks
        if task.artifact.artifact_id in contextual_ids
        for item in task.artifact.public_corpus.evidence
    }
    noncontextual_disjoint = (
        len(noncontextual_evidence) == len(set(noncontextual_evidence))
        and not set(noncontextual_evidence) & contextual_evidence
    )
    all_evidence = [item for task in tasks for item in task.artifact.public_corpus.evidence]
    semantic = {item.source_semantic_signature for item in tasks}
    materializers = {item.materializer_hash for item in tasks}
    pair_task_coverage = {task_id for task_set in pair_task_sets.values() for task_id in task_set}
    expected_pair_map = {
        task_id: pair_id for pair_id, task_set in pair_task_sets.items() for task_id in task_set
    }
    expected_condition_map = {pair.period_task_artifact_id: "period" for pair in pairs} | {
        pair.definition_task_artifact_id: "definition" for pair in pairs
    }
    frozen_mechanisms = all(
        item.spec_hash == design_by_shape[item.shape_id].spec.spec_hash
        for item in tasks
        if item.shape_id != "contextual_resolution_choice"
    )
    checks = {
        "complete_task_count": len(tasks) == EXPECTED_TASK_COUNT
        and len(task_ids) == EXPECTED_TASK_COUNT,
        "shape_balance": set(shape_counts) == ALL_SHAPES
        and set(shape_counts.values()) == {TASKS_PER_SHAPE},
        "stratum_balance": set(stratum_counts) == {item[0] for item in STRUCTURAL_STRATA}
        and set(stratum_counts.values()) == {12},
        "contextual_denominator": len(contextual_ids) == CONTEXTUAL_TASK_COUNT,
        "frozen_denominator": len(frozen_ids) == FROZEN_REGRESSION_TASK_COUNT,
        "pair_count": len(pairs) == PAIR_COUNT and len(pair_task_coverage) == CONTEXTUAL_TASK_COUNT,
        "operation_replay": all(item.artifact.verification.passed for item in tasks),
        "runtime_replay": all(item.runtime_replay.passed for item in tasks),
        "same_core": len(pair_checks["same_core"]) == PAIR_COUNT and all(pair_checks["same_core"]),
        "same_corpus": all(pair_checks["same_corpus"]),
        "same_program": all(pair_checks["same_program"]),
        "same_answer": all(pair_checks["same_answer"]),
        "same_actions": all(pair_checks["same_actions"]),
        "same_budget": all(pair_checks["same_budget"]),
        "same_prompt": all(pair_checks["same_prompt"]),
        "single_context": all(pair_checks["single_context"]),
        "action_flip": all(pair_checks["action_flip"]),
        "branch_replay": all(pair_checks["branch_replay"]),
        "unique_applicable_action": all(pair_checks["unique_applicable_action"]),
        "public_context_sufficiency": all(pair_checks["public_context_sufficiency"]),
        "action_order_invariance": all(pair_checks["action_order_invariance"]),
        "action_label_invariance": all(pair_checks["action_label_invariance"]),
        "context_removal_indeterminate": all(pair_checks["context_removal_indeterminate"]),
        "context_swap_flip": all(pair_checks["context_swap_flip"]),
        "action_description_symmetry": all(pair_checks["action_description_symmetry"]),
        "zero_lexical_action_answer_leakage": lexical_leaks == 0,
        "zero_lexical_context_action_overlap": lexical_context_action_overlaps == 0,
        "zero_opaque_identifier_branch_leakage": opaque_identifier_branch_leaks == 0,
        "pair_local_overlap_only": pair_local_overlap_only,
        "cross_pair_evidence_disjoint": cross_pair_disjoint,
        "noncontextual_evidence_disjoint": noncontextual_disjoint,
        "historical_task_disjoint": not task_ids & excluded["artifact_id"],
        "historical_evidence_disjoint": not {item.evidence_id for item in all_evidence}
        & excluded["evidence_id"],
        "historical_version_disjoint": not {item.evidence_version_id for item in all_evidence}
        & excluded["evidence_version_id"],
        "historical_semantic_disjoint": not semantic & excluded["source_semantic_signature"],
        "historical_materializer_disjoint": not materializers & excluded["materializer_hash"],
        "task_pair_map": set(task_pair_ids) == task_ids
        and all(task_pair_ids[task_id] == expected_pair_map.get(task_id) for task_id in task_ids),
        "task_condition_map": set(task_context_conditions) == task_ids
        and all(
            task_context_conditions[task_id] == expected_condition_map.get(task_id)
            for task_id in task_ids
        ),
        "instance_pairing": set(task_stratum_instance_indices) == task_ids
        and all(
            {
                task_stratum_instance_indices[item.artifact.artifact_id]
                for item in tasks
                if item.shape_id == shape_id and item.stratum_id == stratum_id
            }
            == {0, 1}
            for shape_id in ALL_SHAPES
            for stratum_id, _, _ in STRUCTURAL_STRATA
        ),
        "design_status_scope": set(task_design_statuses) == task_ids
        and all(
            task_design_statuses[task_id]
            == (
                "context_sufficiency_redesign" if task_id in contextual_ids else "frozen_regression"
            )
            for task_id in task_ids
        ),
        "other_five_mechanisms_frozen": frozen_mechanisms,
        "thresholds_frozen": protocol.shape_thresholds == StoppingShapePolicyThresholds(),
        "empirical_thresholds_preregistered": (
            protocol.flip_thresholds == ContextSufficiencyThresholds()
        ),
    }
    rejections = tuple(sorted(key for key, passed in checks.items() if not passed))
    values = {
        "task_count": len(tasks),
        "contextual_task_count": len(contextual_ids),
        "frozen_regression_task_count": len(frozen_ids),
        "pair_count": len(pairs),
        "shape_task_counts": dict(sorted(shape_counts.items())),
        "stratum_task_counts": dict(sorted(stratum_counts.items())),
        "operation_replay_rate": _rate(item.artifact.verification.passed for item in tasks),
        "runtime_replay_rate": _rate(item.runtime_replay.passed for item in tasks),
        "pair_same_core_task_rate": _rate(pair_checks["same_core"]),
        "pair_same_public_corpus_rate": _rate(pair_checks["same_corpus"]),
        "pair_same_program_rate": _rate(pair_checks["same_program"]),
        "pair_same_answer_schema_rate": _rate(pair_checks["same_answer"]),
        "pair_same_action_set_rate": _rate(pair_checks["same_actions"]),
        "pair_same_tool_budget_rate": _rate(pair_checks["same_budget"]),
        "pair_same_prompt_bytes_rate": _rate(pair_checks["same_prompt"]),
        "pair_single_context_change_rate": _rate(pair_checks["single_context"]),
        "pair_action_flip_rate": _rate(pair_checks["action_flip"]),
        "pair_branch_replay_rate": _rate(pair_checks["branch_replay"]),
        "pair_unique_applicable_action_rate": _rate(pair_checks["unique_applicable_action"]),
        "pair_public_context_sufficiency_rate": _rate(pair_checks["public_context_sufficiency"]),
        "action_order_permutation_invariance_rate": _rate(pair_checks["action_order_invariance"]),
        "action_label_rewrite_invariance_rate": _rate(pair_checks["action_label_invariance"]),
        "context_removal_indeterminate_rate": _rate(pair_checks["context_removal_indeterminate"]),
        "context_swap_action_flip_rate": _rate(pair_checks["context_swap_flip"]),
        "action_description_symmetry_rate": _rate(pair_checks["action_description_symmetry"]),
        "lexical_action_answer_leakage_count": lexical_leaks,
        "lexical_context_action_overlap_count": lexical_context_action_overlaps,
        "opaque_identifier_branch_leakage_count": opaque_identifier_branch_leaks,
        "pair_local_overlap_only": pair_local_overlap_only,
        "cross_pair_evidence_disjoint": cross_pair_disjoint,
        "noncontextual_evidence_disjoint": noncontextual_disjoint,
        "historical_task_disjoint": checks["historical_task_disjoint"],
        "historical_evidence_disjoint": checks["historical_evidence_disjoint"],
        "historical_evidence_version_disjoint": checks["historical_version_disjoint"],
        "historical_semantic_signature_disjoint": checks["historical_semantic_disjoint"],
        "historical_materializer_disjoint": checks["historical_materializer_disjoint"],
        "other_five_shape_mechanisms_frozen": frozen_mechanisms,
        "thresholds_frozen": checks["thresholds_frozen"],
        "empirical_thresholds_preregistered": checks["empirical_thresholds_preregistered"],
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_context_sufficiency_development"
            if not rejections
            else "context_sufficiency_population_repair_only"
        ),
    }
    provisional = ContextSufficiencyStaticAudit.model_construct(audit_id="pending", **values)
    return ContextSufficiencyStaticAudit(
        audit_id=_artifact_id(
            provisional,
            "audit_id",
            "finance_stopping_context_sufficiency_static_audit:",
        ),
        **values,
    )


def _single_context_counterfactual_ready(
    period: FinanceStoppingShapeDecisionContract | None,
    definition: FinanceStoppingShapeDecisionContract | None,
) -> bool:
    if period is None or definition is None:
        return False
    expected_kind = CONTEXT_SUFFICIENCY_CONTRACT_KIND
    if period.contract_kind != expected_kind or definition.contract_kind != expected_kind:
        return False
    if period.observed_evidence_state is None or definition.observed_evidence_state is None:
        return False
    if period.public_relation_state is None or definition.public_relation_state is None:
        return False
    period_state = period.observed_evidence_state
    definition_state = definition.observed_evidence_state
    if period_state.required_record != definition_state.required_record:
        return False
    period_difference = _record_difference(
        period_state.observed_record, period_state.required_record
    )
    definition_difference = _record_difference(
        definition_state.observed_record, definition_state.required_record
    )
    period_public = period.model_dump(mode="json", exclude={"oracle_conflict_dimension"})
    definition_public = definition.model_dump(mode="json", exclude={"oracle_conflict_dimension"})
    period_public["observed_evidence_state"]["observed_record"] = "ACTIVE_CONTEXT"
    definition_public["observed_evidence_state"]["observed_record"] = "ACTIVE_CONTEXT"
    period_public["public_relation_state"] = "ACTIVE_CONTEXT"
    definition_public["public_relation_state"] = "ACTIVE_CONTEXT"
    return bool(
        period.schema_version == FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION
        and definition.schema_version == FINANCE_STOPPING_SHAPE_DECISION_V7_VERSION
        and period_difference == "period"
        and definition_difference == "definition"
        and period.public_relation_state == _public_relation_state("period")
        and definition.public_relation_state == _public_relation_state("definition")
        and period_public == definition_public
    )


def _record_difference(observed: Any, required: Any) -> str | None:
    differences = tuple(
        field
        for field, differs in (
            ("subject", observed.subject_alias != required.subject_alias),
            ("metric", observed.metric_alias != required.metric_alias),
            ("period", observed.temporal_identity != required.temporal_identity),
            ("source", observed.source_id != required.source_id),
            ("definition", observed.definition_id != required.definition_id),
            (
                "measurement_context",
                observed.measurement_context != required.measurement_context,
            ),
        )
        if differs
    )
    return differences[0] if len(differences) == 1 else None


def _expected_action(decision: FinanceStoppingShapeDecisionContract | None) -> str | None:
    if decision is None:
        return None
    return {
        "temporal_alignment": "query_structured_fact",
        "source_definition_compatibility": "normalize_metric_unit_period",
    }.get(decision.oracle_conflict_dimension or "")


def _contextual_lexical_leak(
    decision: FinanceStoppingShapeDecisionContract | None,
) -> bool:
    if decision is None:
        return True
    public_descriptions = " ".join(
        (
            decision.observed_conflict_signal or "",
            *(item.applicable_when for item in decision.available_resolution_actions),
        )
    ).lower()
    forbidden = (
        "period",
        "temporal",
        "definition",
        "scale",
        "unit",
        "currency",
        "source_definition",
    )
    return any(token in public_descriptions for token in forbidden)


def _paired_core_hash(task: StoppingShapeTask) -> str:
    artifact = task.artifact.model_dump(mode="json")
    artifact.pop("artifact_id", None)
    task_payload = artifact["task"]
    public_contract = task_payload["public"]["metadata"][PUBLIC_SUBMECHANISM_METADATA_KEY][
        "stopping_shape_decision_contract"
    ]
    _mask_contextual_decision(public_contract, public_projection=True)
    oracle_scenario = task_payload["oracle"]["selection_contract"][FINANCE_SUBMECHANISM_ORACLE_KEY]
    oracle_scenario["scenario_id"] = "CONTEXTUAL_SCENARIO"
    oracle_contract = oracle_scenario["stopping_shape_decision_contract"]
    _mask_contextual_decision(oracle_contract, public_projection=False)
    return canonical_hash(artifact, prefix="finance_contextual_paired_core:")


def _mask_contextual_decision(decision: dict[str, Any], *, public_projection: bool) -> None:
    state = decision.get("observed_evidence_state")
    if not isinstance(state, dict) or "observed_record" not in state:
        raise ValueError("Contextual paired core lacks the active observed record")
    state["observed_record"] = "ACTIVE_CONTEXT"
    relation_state = decision.get("public_relation_state")
    if not isinstance(relation_state, dict):
        raise ValueError("Contextual paired core lacks the public relation state")
    decision["public_relation_state"] = "ACTIVE_CONTEXT"
    if not public_projection:
        decision["oracle_conflict_dimension"] = "ACTIVE_CONDITION"


def _tool_budget_hash(task: StoppingShapeTask) -> str:
    return canonical_hash(
        {
            "allowed_tools": task.artifact.task.public.allowed_tools,
            "required_tool_ids": task.artifact.required_tool_ids,
            "stopping_conditions": task.artifact.stopping_conditions,
            "structure": task.artifact.structure,
        },
        prefix="finance_contextual_tool_budget:",
    )


def _public_prompt_bytes(task: StoppingShapeTask) -> int:
    return len(_json_bytes(task.artifact.task.public.model_dump(mode="json")))


def _observed_record_bytes(item: EvidenceItem) -> int:
    return len(_json_bytes(_observed_record(item).model_dump(mode="json")))


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _rate(values: Sequence[bool] | Any) -> float:
    rows = tuple(bool(item) for item in values)
    return sum(rows) / len(rows) if rows else 0.0


def _verify_protocol_inputs(
    protocol: FinanceStoppingContextSufficiencyProtocol,
) -> None:
    references = (
        protocol.source_v25_46_report,
        protocol.source_v25_46_raw_audit,
        protocol.source_v25_46_shape_report,
        protocol.source_v25_46_mechanism_report,
        protocol.source_v25_46_manifest,
        protocol.source_v25_46_protocol,
        protocol.source_v25_46_population,
        protocol.source_grammar_protocol,
        protocol.source_grammar_population,
        protocol.source_finance_artifacts,
        protocol.source_calibration_contract,
        *protocol.historical_population_references,
    )
    for reference in references:
        _verify_reference(reference.path, reference.sha256)

    report = json.loads(Path(protocol.source_v25_46_report.path).read_text(encoding="utf-8"))
    raw = json.loads(Path(protocol.source_v25_46_raw_audit.path).read_text(encoding="utf-8"))
    shape = json.loads(Path(protocol.source_v25_46_shape_report.path).read_text(encoding="utf-8"))
    mechanism = json.loads(
        Path(protocol.source_v25_46_mechanism_report.path).read_text(encoding="utf-8")
    )
    manifest = json.loads(Path(protocol.source_v25_46_manifest.path).read_text(encoding="utf-8"))
    source_protocol = FinanceStoppingContextualCounterfactualProtocol.model_validate_json(
        Path(protocol.source_v25_46_protocol.path).read_text(encoding="utf-8")
    )
    source_population = FinanceStoppingContextualCounterfactualPopulation.model_validate_json(
        Path(protocol.source_v25_46_population.path).read_text(encoding="utf-8")
    )
    if not (
        report.get("raw_instrument_status") == "passed"
        and report.get("shape_analysis_authorized") is True
        and report.get("boundary_candidate_admitted_count") == 4
        and report.get("runtime_control_pass_count") == 2
        and report.get("all_shape_contracts_passing") is True
        and report.get("contextual_flip_passing") is False
        and report.get("all_v25_46_gates_passing") is False
        and report.get("next_permitted_stage") == "contextual_shape_redesign_only"
        and report.get("production_contribution") == 0.0
    ):
        raise ValueError("v25.47 source report no longer has the frozen v25.46 state")
    if not (
        raw.get("instrument_status") == "passed"
        and raw.get("shape_analysis_authorized") is True
        and raw.get("rejection_reasons") == []
        and raw.get("recursive_host_field_violation_count") == 0
        and raw.get("recursive_host_marker_violation_count") == 0
    ):
        raise ValueError("v25.47 source noninterference audit is not clean")
    if not (
        shape.get("all_shapes_contract_passing") is True
        and shape.get("boundary_candidate_admitted_count") == 4
        and shape.get("runtime_control_pass_count") == 2
    ):
        raise ValueError("v25.47 source Shape boundary support changed")
    if not (
        mechanism.get("passed") is False
        and mechanism.get("contextual_flip_consistency") == 0.0625
        and mechanism.get("informative_pair_count") == 2
        and mechanism.get("rejection_reasons")
        == ["minimum_contextual_flip_consistency", "minimum_informative_pair_count"]
    ):
        raise ValueError("v25.47 source mechanism-fidelity failure changed")
    if manifest.get("production_contribution") != 0.0:
        raise ValueError("v25.47 source unexpectedly authorized production Contribution")
    if not (
        source_protocol.protocol_id == protocol.source_v25_46_protocol.artifact_id
        and source_population.population_id == protocol.source_v25_46_population.artifact_id
        and source_population.source_protocol.artifact_id == source_protocol.protocol_id
        and source_protocol.source_grammar_protocol == protocol.source_grammar_protocol
        and source_protocol.source_grammar_population == protocol.source_grammar_population
        and source_protocol.source_finance_artifacts == protocol.source_finance_artifacts
        and source_protocol.source_calibration_contract == protocol.source_calibration_contract
    ):
        raise ValueError("v25.47 source Protocol or population lineage changed")
    expected_historical = {
        item.artifact_id for item in source_protocol.historical_population_references
    } | {source_population.population_id}
    if {item.artifact_id for item in protocol.historical_population_references} != (
        expected_historical
    ):
        raise ValueError("v25.47 freshness exclusion lineage changed")
    grammar = load_stopping_shape_grammar_protocol(Path(protocol.source_grammar_protocol.path))
    if (
        not isinstance(grammar, FinanceStoppingInstrumentResetGrammarProtocol)
        or grammar.protocol_id != protocol.source_grammar_protocol.artifact_id
        or grammar.source_finance_artifacts != protocol.source_finance_artifacts
        or grammar.source_calibration_contract != protocol.source_calibration_contract
    ):
        raise ValueError("v25.47 Grammar lineage is inconsistent")


def _population_implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_population.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_policy_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_contextual_counterfactual.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_context_sufficiency.py",
    )
    return {path: _sha256(root / path) for path in paths}


def _render_population_report(
    population: FinanceStoppingContextSufficiencyPopulation,
) -> str:
    audit = population.static_audit
    lines = [
        "# Finance v25.47 Contextual Counterfactual Population",
        "",
        f"- Population ID: `{population.population_id}`",
        f"- Tasks: **{audit.task_count}/48**",
        f"- Contextual paired tasks: **{audit.contextual_task_count}/8**",
        f"- Frozen regression tasks: **{audit.frozen_regression_task_count}/40**",
        f"- Matched pairs: **{audit.pair_count}/4**",
        f"- Same core task: **{audit.pair_same_core_task_rate:.3f}**",
        f"- Same public corpus: **{audit.pair_same_public_corpus_rate:.3f}**",
        f"- Same Prompt bytes: **{audit.pair_same_prompt_bytes_rate:.3f}**",
        f"- Single Context change: **{audit.pair_single_context_change_rate:.3f}**",
        f"- Correct action flip: **{audit.pair_action_flip_rate:.3f}**",
        f"- Pair branch replay: **{audit.pair_branch_replay_rate:.3f}**",
        f"- Unique publicly applicable action: **{audit.pair_unique_applicable_action_rate:.3f}**",
        f"- Public context sufficiency: **{audit.pair_public_context_sufficiency_rate:.3f}**",
        f"- Action-order invariance: **{audit.action_order_permutation_invariance_rate:.3f}**",
        f"- Action-label invariance: **{audit.action_label_rewrite_invariance_rate:.3f}**",
        f"- Context removal indeterminate: **{audit.context_removal_indeterminate_rate:.3f}**",
        f"- Context swap action flip: **{audit.context_swap_action_flip_rate:.3f}**",
        f"- Action-description symmetry: **{audit.action_description_symmetry_rate:.3f}**",
        f"- Lexical action leakage: **{audit.lexical_action_answer_leakage_count}**",
        f"- Lexical context/action overlap: **{audit.lexical_context_action_overlap_count}**",
        f"- Opaque branch-label leakage: **{audit.opaque_identifier_branch_leakage_count}**",
        f"- Static ready: **{audit.ready}**",
        f"- Next permitted stage: `{population.next_permitted_stage}`",
        "- Other five Shape mechanisms and all thresholds: **frozen**",
        "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
        "- Production Contribution: **0**",
        "",
    ]
    if audit.rejection_reasons:
        lines.extend(
            ["## Rejections", "", *(f"- `{item}`" for item in audit.rejection_reasons), ""]
        )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the immutable Finance v25.47 protocol or population"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    protocol = sub.add_parser("protocol")
    protocol.add_argument("--source-report", type=Path, required=True)
    protocol.add_argument("--source-raw-audit", type=Path, required=True)
    protocol.add_argument("--source-shape-report", type=Path, required=True)
    protocol.add_argument("--source-mechanism-report", type=Path, required=True)
    protocol.add_argument("--source-manifest", type=Path, required=True)
    protocol.add_argument("--source-protocol", type=Path, required=True)
    protocol.add_argument("--source-population", type=Path, required=True)
    protocol.add_argument("--output", type=Path, required=True)
    protocol.add_argument("--run-id", required=True)
    population = sub.add_parser("population")
    population.add_argument("--protocol", type=Path, required=True)
    population.add_argument("--output-dir", type=Path, required=True)
    population.add_argument("--run-id", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "protocol":
        prepare_context_sufficiency_protocol(
            source_v25_46_report_path=args.source_report,
            source_v25_46_raw_audit_path=args.source_raw_audit,
            source_v25_46_shape_report_path=args.source_shape_report,
            source_v25_46_mechanism_report_path=args.source_mechanism_report,
            source_v25_46_manifest_path=args.source_manifest,
            source_v25_46_protocol_path=args.source_protocol,
            source_v25_46_population_path=args.source_population,
            output_path=args.output,
            run_id=args.run_id,
        )
    else:
        build_context_sufficiency_population(
            protocol_path=args.protocol,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )


if __name__ == "__main__":
    main()
