from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FinanceAgentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    RUNTIME_AXIS_RESPONSIBILITY,
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
    CapabilitySensitiveTaskArtifact,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_flash_information_matrix import (
    FinanceFlashInformationReport,
    FlashInformationCell,
    InformationGate,
    _make_information_cell,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    MatchedLadderGroup,
    core_task_semantic_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    MultiTierCapabilityPopulation,
    _build_multitier_groups,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    WORKFLOW_RUNTIME_ARMS,
    _execute_stage,
    _write_immutable_json,
    _write_immutable_model,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    MAXIMUM_OBSERVATION_SUMMARY_BYTES,
    MAXIMUM_PUBLIC_CONTEXT_BYTES,
    MODEL_TOKEN_BUDGET,
    FinanceRuntimeResolutionContract,
    FinanceRuntimeResolutionReport,
    RuntimeResolutionMetrics,
    RuntimeResolutionStage,
    RuntimeResolutionThresholds,
    RuntimeTerminalOutcome,
    _implementation_manifest,
    _load_records,
    _make_terminal_outcome,
    _metrics,
    _repair_task,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    PublicContractSatisfiabilityAudit,
    make_public_contract_audit,
    make_public_contract_record,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    WorkflowInformationThresholds,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

SUPPORT_DEVELOPMENT_VERSION = "finance_capability_support_development.v1"
SUPPORT_RULE_VERSION = "finance_capability_support_rule.v1"
SUPPORT_POPULATION_VERSION = "finance_capability_support_population.v1"
SUPPORT_FRESHNESS_VERSION = "finance_capability_support_freshness.v1"
SUPPORT_SELECTION_VERSION = "finance_capability_support_selection.v1"
SUPPORT_CONFIRMATION_CONTRACT_VERSION = "finance_capability_support_confirmation_contract.v1"
SUPPORT_CONFIRMATION_REPORT_VERSION = "finance_capability_support_confirmation_report.v1"
SUPPORT_CONFIRMATION_RUNNER_VERSION = "finance_capability_support_confirmation_runner.v1"

GROUPS_PER_FAMILY = 5
REPLICAS_PER_TASK = 5

# Core-program depth is changed only where v25.18 showed saturation. Public-corpus
# tier remains Runtime-specific and is selected by the frozen Development policy.
SUPPORT_CORE_PROGRAM_TIERS: dict[str, DifficultyTier] = {
    "finance.multi_hop_retrieval_join": DifficultyTier.HARD_CONTROL,
    "finance.branching_operation_plan": DifficultyTier.EASY_CONTROL,
    "finance.calculation_chain": DifficultyTier.HARD_CONTROL,
    "finance.definition_reconciliation": DifficultyTier.FRONTIER,
    "finance.verification_sensitive_selection": DifficultyTier.HARD_CONTROL,
    "finance.recovery_guided_search": DifficultyTier.FRONTIER,
    "finance.stopping_decision_control": DifficultyTier.FRONTIER,
}

TIER_ORDER: tuple[DifficultyTier, ...] = (
    DifficultyTier.EASY_CONTROL,
    DifficultyTier.FRONTIER,
    DifficultyTier.HARD_CONTROL,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilitySupportRule(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    primary_axis: str = Field(min_length=1)
    runtime_responsibility: float = Field(ge=0, le=1)
    development_attempts_by_tier: dict[DifficultyTier, int]
    development_success_rates_by_tier: dict[DifficultyTier, float]
    development_status: Literal["host_controlled", "saturated", "floor", "mixed"]
    anchor_tier: DifficultyTier | None
    confirmation_tier_schedule: tuple[DifficultyTier, ...]
    rationale: str = Field(min_length=1)
    schema_version: str = SUPPORT_RULE_VERSION

    @model_validator(mode="after")
    def validate_rule(self) -> CapabilitySupportRule:
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("support rule contains an unknown family")
        if self.primary_axis != FAMILY_PRIMARY_CAPABILITY[self.family]:
            raise ValueError("support rule primary axis differs from the family")
        expected = RUNTIME_AXIS_RESPONSIBILITY[self.runtime_arm][self.primary_axis]
        if self.runtime_responsibility != expected:
            raise ValueError("support rule Runtime responsibility is inconsistent")
        if set(self.development_attempts_by_tier) != set(TIER_ORDER):
            raise ValueError("support rule omits a Development tier denominator")
        if set(self.development_success_rates_by_tier) != set(TIER_ORDER):
            raise ValueError("support rule omits a Development tier response")
        if expected == 0:
            if (
                self.development_status != "host_controlled"
                or self.anchor_tier is not None
                or self.confirmation_tier_schedule
            ):
                raise ValueError("host-controlled support must remain excluded")
        elif self.anchor_tier is None or len(self.confirmation_tier_schedule) != GROUPS_PER_FAMILY:
            raise ValueError("model-visible support lacks its frozen group schedule")
        return self


class FinanceCapabilitySupportDevelopment(FrozenModel):
    policy_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_runtime_contract_path: str = Field(min_length=1)
    source_runtime_contract_sha256: str = Field(min_length=64, max_length=64)
    source_runtime_contract_id: str = Field(min_length=1)
    source_runtime_report_path: str = Field(min_length=1)
    source_runtime_report_sha256: str = Field(min_length=64, max_length=64)
    source_runtime_report_id: str = Field(min_length=1)
    source_terminal_outcomes_path: str = Field(min_length=1)
    source_terminal_outcomes_sha256: str = Field(min_length=64, max_length=64)
    source_outcome_set_hash: str = Field(min_length=1)
    source_information_report_path: str = Field(min_length=1)
    source_information_report_sha256: str = Field(min_length=64, max_length=64)
    source_information_report_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    rules: tuple[CapabilitySupportRule, ...] = Field(min_length=14, max_length=14)
    groups_per_family: int = Field(default=GROUPS_PER_FAMILY, ge=4, le=6)
    replicas_per_task: int = Field(default=REPLICAS_PER_TASK, ge=4, le=5)
    core_program_tiers: dict[str, DifficultyTier] = SUPPORT_CORE_PROGRAM_TIERS
    development_use_only: Literal[True] = True
    confirmation_response_access: Literal["forbidden"] = "forbidden"
    pro_api_calls_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["fresh_capability_support_population"] = (
        "fresh_capability_support_population"
    )
    schema_version: str = SUPPORT_DEVELOPMENT_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> FinanceCapabilitySupportDevelopment:
        expected = {
            (runtime, family)
            for runtime in WORKFLOW_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if {(item.runtime_arm, item.family) for item in self.rules} != expected:
            raise ValueError("support policy omits a Runtime-family cell")
        if self.core_program_tiers != SUPPORT_CORE_PROGRAM_TIERS:
            raise ValueError("support policy changes the preregistered core tiers")
        if self.policy_id != support_development_id(self):
            raise ValueError("support policy identity is invalid")
        return self


class CapabilitySupportSelection(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    primary_axis: str = Field(min_length=1)
    group_index: int = Field(ge=0, lt=GROUPS_PER_FAMILY)
    group_id: str = Field(min_length=1)
    tier: DifficultyTier
    source_task_artifact_id: str = Field(min_length=1)
    schema_version: str = SUPPORT_SELECTION_VERSION


class CapabilitySupportFreshness(FrozenModel):
    excluded_group_count: int = Field(ge=1)
    selected_group_count: int = Field(ge=GROUPS_PER_FAMILY * len(CAPABILITY_SENSITIVE_FAMILIES))
    task_artifact_overlap_count: Literal[0] = 0
    group_overlap_count: Literal[0] = 0
    evidence_overlap_count: Literal[0] = 0
    evidence_version_overlap_count: Literal[0] = 0
    semantic_signature_overlap_count: Literal[0] = 0
    task_signature_overlap_count: Literal[0] = 0
    schema_version: str = SUPPORT_FRESHNESS_VERSION


class FinanceCapabilitySupportPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_extension_report_path: str = Field(min_length=1)
    source_extension_report_sha256: str = Field(min_length=64, max_length=64)
    source_extension_report_id: str = Field(min_length=1)
    development_policy_path: str = Field(min_length=1)
    development_policy_sha256: str = Field(min_length=64, max_length=64)
    development_policy_id: str = Field(min_length=1)
    sampling_salt: str = Field(min_length=1)
    excluded_group_ids: tuple[str, ...] = Field(min_length=1)
    excluded_semantic_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    groups: tuple[MatchedLadderGroup, ...] = Field(
        min_length=GROUPS_PER_FAMILY * len(CAPABILITY_SENSITIVE_FAMILIES),
        max_length=GROUPS_PER_FAMILY * len(CAPABILITY_SENSITIVE_FAMILIES),
    )
    selections: tuple[CapabilitySupportSelection, ...] = Field(min_length=1)
    public_contract_audit: PublicContractSatisfiabilityAudit
    freshness: CapabilitySupportFreshness
    static_task_count: int = Field(ge=1)
    selected_binding_count: int = Field(ge=1)
    population_ready: bool
    model_api_calls: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_capability_support_confirmation",
        "capability_support_population_repair_only",
    ]
    schema_version: str = SUPPORT_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceCapabilitySupportPopulation:
        expected_group_count = GROUPS_PER_FAMILY * len(CAPABILITY_SENSITIVE_FAMILIES)
        if len({item.group_id for item in self.groups}) != expected_group_count:
            raise ValueError("support population duplicates a Matched Group")
        if len({item.core_semantic_signature for item in self.groups}) != expected_group_count:
            raise ValueError("support population duplicates core semantics")
        if self.selected_binding_count != len(self.selections):
            raise ValueError("support selection denominator is inconsistent")
        expected_selected = sum(
            GROUPS_PER_FAMILY
            for runtime in WORKFLOW_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
            if RUNTIME_AXIS_RESPONSIBILITY[runtime][FAMILY_PRIMARY_CAPABILITY[family]] > 0
        )
        if self.selected_binding_count != expected_selected:
            raise ValueError("support population omits a model-visible Runtime-family cell")
        ready = self.public_contract_audit.all_public_contracts_satisfiable and not any(
            (
                self.freshness.task_artifact_overlap_count,
                self.freshness.group_overlap_count,
                self.freshness.evidence_overlap_count,
                self.freshness.evidence_version_overlap_count,
                self.freshness.semantic_signature_overlap_count,
                self.freshness.task_signature_overlap_count,
            )
        )
        if self.population_ready != ready:
            raise ValueError("support population readiness is inconsistent")
        expected_stage = (
            "flash_capability_support_confirmation"
            if ready
            else "capability_support_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("support population transition is not fail-closed")
        if self.population_id != support_population_id(self):
            raise ValueError("support population identity is invalid")
        return self

    @property
    def all_tasks(self) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
        return tuple(
            sorted(
                (task for group in self.groups for task in group.variants),
                key=lambda item: item.artifact_id,
            )
        )


class FinanceCapabilitySupportConfirmationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: RuntimeResolutionStage = RuntimeResolutionStage.HELDOUT_CONFIRMATION
    source_population_path: str = Field(min_length=1)
    source_population_sha256: str = Field(min_length=64, max_length=64)
    source_population_id: str = Field(min_length=1)
    source_runtime_contract_path: str = Field(min_length=1)
    source_runtime_contract_sha256: str = Field(min_length=64, max_length=64)
    source_runtime_contract_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    runtime_thresholds: RuntimeResolutionThresholds
    information_thresholds: WorkflowInformationThresholds
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(min_length=1)
    source_task_artifact_ids: dict[str, str]
    task_group_ids: dict[str, str]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(min_length=1)
    replicas: int = Field(default=REPLICAS_PER_TASK, ge=4, le=5)
    requested_rollout_count: int = Field(ge=1)
    maximum_model_tokens_per_rollout: int = Field(default=MODEL_TOKEN_BUDGET, ge=1)
    maximum_observation_summary_bytes: int = Field(default=MAXIMUM_OBSERVATION_SUMMARY_BYTES, ge=1)
    maximum_public_context_bytes: int = Field(default=MAXIMUM_PUBLIC_CONTEXT_BYTES, ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    confirmation_response_access_during_selection: Literal["forbidden"] = "forbidden"
    pro_api_calls_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_capability_support_confirmation"] = (
        "flash_capability_support_confirmation"
    )
    schema_version: str = SUPPORT_CONFIRMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCapabilitySupportConfirmationContract:
        if self.stage != RuntimeResolutionStage.HELDOUT_CONFIRMATION:
            raise ValueError("support confirmation must remain a fresh Held-out stage")
        if self.requested_rollout_count != len(self.bindings) * self.replicas:
            raise ValueError("support confirmation rollout denominator is inconsistent")
        if {item.arm for item in self.model_contracts} != {ExplorerArm.FLASH}:
            raise ValueError("support confirmation is Flash-only")
        task_ids = {item.artifact_id for item in self.tasks}
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("support confirmation task/binding identity is incomplete")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("support confirmation rollout identities are incomplete")
        if self.contract_id != support_confirmation_contract_id(self):
            raise ValueError("support confirmation contract identity is invalid")
        return self


class SupportRuntimeGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    runtime_arm: CapabilityRuntimeArm | None
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class CapabilitySupportRuntimeMetrics(FrozenModel):
    attempted_count: int = Field(ge=1)
    runtime_eligible_count: int = Field(ge=0)
    observed_tiers: tuple[DifficultyTier, ...] = Field(min_length=1)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    failure_attribution_coverage_rate: float = Field(ge=0, le=1)
    external_infrastructure_failure_rate: float = Field(ge=0, le=1)
    task_runtime_contract_failure_rate: float = Field(ge=0, le=1)
    tool_environment_failure_rate: float = Field(ge=0, le=1)
    unattributed_failure_rate: float = Field(ge=0, le=1)
    runtime_prompt_pathology_rate: float = Field(ge=0, le=1)
    valid_success_given_runtime_eligible: float = Field(ge=0, le=1)
    tier_valid_success_given_runtime_eligible: dict[DifficultyTier, float]
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_metrics(self) -> CapabilitySupportRuntimeMetrics:
        if set(self.tier_valid_success_given_runtime_eligible) != set(self.observed_tiers):
            raise ValueError("support Runtime metrics contain an unobserved Tier")
        return self


class FinanceCapabilitySupportConfirmationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=1)
    runtime_eligible_rollout_count: int = Field(ge=0)
    overall_metrics: RuntimeResolutionMetrics
    runtime_metrics: dict[CapabilityRuntimeArm, CapabilitySupportRuntimeMetrics]
    runtime_gates: tuple[SupportRuntimeGate, ...] = Field(min_length=1)
    runtime_qualification_passed: bool
    information_cells: tuple[FlashInformationCell, ...]
    information_matrix_ready: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_api_call_count: Literal[0] = 0
    pro_sparse_anchor_authorized: bool
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "pro_sparse_anchor_preparation",
        "capability_task_support_redesign_only",
        "runtime_measurement_repair_only",
    ]
    schema_version: str = SUPPORT_CONFIRMATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceCapabilitySupportConfirmationReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("support confirmation lacks its complete denominator")
        info_ready = (
            self.runtime_qualification_passed
            and len(self.information_cells) == len(WORKFLOW_RUNTIME_ARMS)
            and all(item.passed for item in self.information_cells)
        )
        if self.information_matrix_ready != info_ready:
            raise ValueError("support information decision is inconsistent")
        if self.pro_sparse_anchor_authorized != info_ready:
            raise ValueError("support Pro authorization is inconsistent")
        expected_stage = (
            "runtime_measurement_repair_only"
            if not self.runtime_qualification_passed
            else (
                "pro_sparse_anchor_preparation"
                if info_ready
                else "capability_task_support_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("support confirmation transition is not fail-closed")
        if self.report_id != support_confirmation_report_id(self):
            raise ValueError("support confirmation report identity is invalid")
        return self


def develop_capability_support_policy(
    *,
    source_runtime_contract_path: Path,
    source_runtime_report_path: Path,
    source_terminal_outcomes_path: Path,
    source_information_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceCapabilitySupportDevelopment:
    if output_path.exists():
        raise ValueError("support Development policy is immutable and already exists")
    runtime_contract = FinanceRuntimeResolutionContract.model_validate_json(
        source_runtime_contract_path.read_text(encoding="utf-8")
    )
    runtime_report = FinanceRuntimeResolutionReport.model_validate_json(
        source_runtime_report_path.read_text(encoding="utf-8")
    )
    terminals = tuple(
        RuntimeTerminalOutcome.model_validate_json(line)
        for line in source_terminal_outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    information = FinanceFlashInformationReport.model_validate_json(
        source_information_report_path.read_text(encoding="utf-8")
    )
    if (
        runtime_contract.stage != RuntimeResolutionStage.HELDOUT_CONFIRMATION
        or runtime_report.contract_id != runtime_contract.contract_id
        or runtime_report.outcome_set_hash
        != canonical_hash(
            tuple(sorted(item.terminal_outcome_id for item in terminals)),
            prefix="finance_runtime_resolution_fresh_heldout_runtime_confirmation_outcomes:",
        )
        or runtime_report.next_permitted_stage != "flash_information_matrix_evaluation"
        or information.source_runtime_report_id != runtime_report.report_id
        or information.information_matrix_ready
        or information.next_permitted_stage != "capability_task_support_redesign_only"
    ):
        raise ValueError("support Development does not consume the frozen v25.18 result")
    rules = tuple(
        _develop_rule(runtime, family, terminals)
        for runtime in WORKFLOW_RUNTIME_ARMS
        for family in CAPABILITY_SENSITIVE_FAMILIES
    )
    values = {
        "run_id": run_id,
        "source_runtime_contract_path": str(source_runtime_contract_path.resolve()),
        "source_runtime_contract_sha256": _sha256(source_runtime_contract_path),
        "source_runtime_contract_id": runtime_contract.contract_id,
        "source_runtime_report_path": str(source_runtime_report_path.resolve()),
        "source_runtime_report_sha256": _sha256(source_runtime_report_path),
        "source_runtime_report_id": runtime_report.report_id,
        "source_terminal_outcomes_path": str(source_terminal_outcomes_path.resolve()),
        "source_terminal_outcomes_sha256": _sha256(source_terminal_outcomes_path),
        "source_outcome_set_hash": runtime_report.outcome_set_hash,
        "source_information_report_path": str(source_information_report_path.resolve()),
        "source_information_report_sha256": _sha256(source_information_report_path),
        "source_information_report_id": information.report_id,
        "source_population_id": runtime_contract.source_population_id,
        "rules": rules,
    }
    provisional = FinanceCapabilitySupportDevelopment.model_construct(policy_id="pending", **values)
    policy = FinanceCapabilitySupportDevelopment(
        policy_id=support_development_id(provisional), **values
    )
    _write_immutable_model(output_path, policy)
    return policy


def _develop_rule(
    runtime: CapabilityRuntimeArm,
    family: str,
    terminals: Sequence[RuntimeTerminalOutcome],
) -> CapabilitySupportRule:
    primary_axis = FAMILY_PRIMARY_CAPABILITY[family]
    responsibility = RUNTIME_AXIS_RESPONSIBILITY[runtime][primary_axis]
    attempts: dict[DifficultyTier, int] = {}
    rates: dict[DifficultyTier, float] = {}
    for tier in TIER_ORDER:
        values = tuple(
            item
            for item in terminals
            if item.runtime_arm == runtime
            and item.family == family
            and item.tier == tier
            and item.runtime_eligible_for_capability_denominator
        )
        if not values:
            raise ValueError(f"Development lacks {runtime.value}/{family}/{tier.value}")
        attempts[tier] = len(values)
        rates[tier] = sum(item.valid_success for item in values) / len(values)
    if responsibility == 0:
        status: Literal["host_controlled", "saturated", "floor", "mixed"] = "host_controlled"
        anchor = None
        schedule: tuple[DifficultyTier, ...] = ()
        rationale = (
            "The Runtime delegates this capability to the Host; exclude it from response geometry."
        )
    else:
        status = (
            "saturated"
            if min(rates.values()) >= 0.9
            else ("floor" if max(rates.values()) <= 0.1 else "mixed")
        )
        anchor = _select_anchor_tier(rates)
        schedule = _confirmation_tier_schedule(anchor)
        rationale = (
            f"Development status={status}; anchor={anchor.value}; "
            "allocate three independent groups at the closest observed boundary tier "
            "and two adjacent structural probes without observing Confirmation responses."
        )
    return CapabilitySupportRule(
        runtime_arm=runtime,
        family=family,
        primary_axis=primary_axis,
        runtime_responsibility=responsibility,
        development_attempts_by_tier=attempts,
        development_success_rates_by_tier=rates,
        development_status=status,
        anchor_tier=anchor,
        confirmation_tier_schedule=schedule,
        rationale=rationale,
    )


def _select_anchor_tier(
    rates: Mapping[DifficultyTier, float],
) -> DifficultyTier:
    if set(rates) != set(TIER_ORDER):
        raise ValueError("anchor selection requires every tier")
    # Ties prefer the structurally harder task so a saturated family is pushed away
    # from the ceiling without looking at fresh Confirmation responses.
    rank = {tier: index for index, tier in enumerate(TIER_ORDER)}
    return min(
        TIER_ORDER,
        key=lambda tier: (abs(rates[tier] - 0.5), -rank[tier]),
    )


def _confirmation_tier_schedule(
    anchor: DifficultyTier,
) -> tuple[DifficultyTier, ...]:
    if anchor == DifficultyTier.EASY_CONTROL:
        return (
            DifficultyTier.EASY_CONTROL,
            DifficultyTier.FRONTIER,
            DifficultyTier.EASY_CONTROL,
            DifficultyTier.FRONTIER,
            DifficultyTier.EASY_CONTROL,
        )
    if anchor == DifficultyTier.HARD_CONTROL:
        return (
            DifficultyTier.HARD_CONTROL,
            DifficultyTier.FRONTIER,
            DifficultyTier.HARD_CONTROL,
            DifficultyTier.FRONTIER,
            DifficultyTier.HARD_CONTROL,
        )
    return (
        DifficultyTier.FRONTIER,
        DifficultyTier.EASY_CONTROL,
        DifficultyTier.FRONTIER,
        DifficultyTier.HARD_CONTROL,
        DifficultyTier.FRONTIER,
    )


def build_capability_support_population(
    *,
    source_population_path: Path,
    source_artifacts_path: Path,
    source_extension_report_path: Path,
    development_policy_path: Path,
    output_path: Path,
    run_id: str,
    sampling_salt: str,
) -> FinanceCapabilitySupportPopulation:
    if output_path.exists():
        raise ValueError("support population is immutable and already exists")
    source = MultiTierCapabilityPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    policy = FinanceCapabilitySupportDevelopment.model_validate_json(
        development_policy_path.read_text(encoding="utf-8")
    )
    if policy.source_population_id != source.population_id:
        raise ValueError("support policy and source population identities differ")
    source_artifacts_path = source_artifacts_path.resolve()
    source_extension_report_path = source_extension_report_path.resolve()
    extension = FinanceAgentPopulationReport.model_validate_json(
        source_extension_report_path.read_text(encoding="utf-8")
    )
    if (
        extension.status != "passed"
        or extension.artifact_sha256 != _sha256(source_artifacts_path)
        or source.source_artifacts_sha256 not in set(extension.excluded_population_artifact_sha256s)
        or extension.excluded_public_evidence_version_count == 0
    ):
        raise ValueError("support source extension lacks frozen disjoint lineage")
    prior_tasks = source.tasks
    prior_task_ids = {item.artifact_id for item in prior_tasks}
    prior_signatures = set(source.excluded_core_signatures) | {
        item.core_semantic_signature for item in source.groups
    }
    prior_evidence_ids = set(source.excluded_evidence_ids) | {
        evidence.evidence_id for task in prior_tasks for evidence in task.public_corpus.evidence
    }
    prior_version_ids = set(source.excluded_evidence_version_ids) | {
        evidence.evidence_version_id
        for task in prior_tasks
        for evidence in task.public_corpus.evidence
    }
    pool = _load_evidence_pool(source_artifacts_path)
    builder = _CapabilityTaskBuilder(pool, sampling_salt=sampling_salt)
    builder._used_evidence_ids.update(prior_evidence_ids)
    groups = _build_multitier_groups(
        builder,
        excluded_signatures=prior_signatures,
        groups_per_family=GROUPS_PER_FAMILY,
        core_program_tiers=SUPPORT_CORE_PROGRAM_TIERS,
    )
    by_family = {
        family: tuple(
            sorted(
                (item for item in groups if item.family == family),
                key=lambda item: item.group_id,
            )
        )
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    rule_by_key = {(item.runtime_arm, item.family): item for item in policy.rules}
    selections: list[CapabilitySupportSelection] = []
    for runtime in WORKFLOW_RUNTIME_ARMS:
        for family in CAPABILITY_SENSITIVE_FAMILIES:
            rule = rule_by_key[(runtime, family)]
            for index, tier in enumerate(rule.confirmation_tier_schedule):
                group = by_family[family][index]
                task = next(item for item in group.variants if item.tier == tier)
                selections.append(
                    CapabilitySupportSelection(
                        runtime_arm=runtime,
                        family=family,
                        primary_axis=rule.primary_axis,
                        group_index=index,
                        group_id=group.group_id,
                        tier=tier,
                        source_task_artifact_id=task.artifact_id,
                    )
                )
    selected_group_ids = {item.group_id for item in groups}
    selected_signatures = {item.core_semantic_signature for item in groups}
    selected_tasks = tuple(task for group in groups for task in group.variants)
    selected_task_ids = {item.artifact_id for item in selected_tasks}
    selected_evidence_ids = {
        evidence.evidence_id for task in selected_tasks for evidence in task.public_corpus.evidence
    }
    selected_version_ids = {
        evidence.evidence_version_id
        for task in selected_tasks
        for evidence in task.public_corpus.evidence
    }
    prior_task_signatures = {core_task_semantic_signature(item) for item in prior_tasks}
    selected_task_signatures = {core_task_semantic_signature(item) for item in selected_tasks}
    freshness = CapabilitySupportFreshness(
        excluded_group_count=len(source.groups),
        selected_group_count=len(groups),
        task_artifact_overlap_count=len(selected_task_ids & prior_task_ids),
        group_overlap_count=len(selected_group_ids & {item.group_id for item in source.groups}),
        evidence_overlap_count=len(selected_evidence_ids & prior_evidence_ids),
        evidence_version_overlap_count=len(selected_version_ids & prior_version_ids),
        semantic_signature_overlap_count=len(selected_signatures & prior_signatures),
        task_signature_overlap_count=len(selected_task_signatures & prior_task_signatures),
    )
    identity = {
        "run_id": run_id,
        "source_population_id": source.population_id,
        "development_policy_id": policy.policy_id,
        "sampling_salt": sampling_salt,
        "group_hashes": tuple(item.group_hash for item in groups),
        "selections": tuple(item.model_dump(mode="json") for item in selections),
        "freshness": freshness.model_dump(mode="json"),
    }
    population_id = canonical_hash(identity, prefix="finance_capability_support_population:")
    records = tuple(
        make_public_contract_record(
            task=task,
            runtime_arm=cast(Any, runtime.value),
            runtime_task=context.task,
            manifest=manifest,
            maximum_required_tool_calls=20,
        )
        for group in groups
        for task in group.variants
        for runtime in WORKFLOW_RUNTIME_ARMS
        for context, manifest, _ in (_runtime_context(task, runtime, source.protocol_profile),)
    )
    static_audit = make_public_contract_audit(
        population_id=population_id,
        records=records,
        required_runtime_arms=tuple(cast(Any, item.value) for item in WORKFLOW_RUNTIME_ARMS),
    )
    ready = static_audit.all_public_contracts_satisfiable and not any(
        (
            freshness.task_artifact_overlap_count,
            freshness.group_overlap_count,
            freshness.evidence_overlap_count,
            freshness.evidence_version_overlap_count,
            freshness.semantic_signature_overlap_count,
            freshness.task_signature_overlap_count,
        )
    )
    population = FinanceCapabilitySupportPopulation(
        population_id=population_id,
        run_id=run_id,
        source_population_path=str(source_population_path.resolve()),
        source_population_sha256=_sha256(source_population_path),
        source_population_id=source.population_id,
        source_artifacts_path=str(source_artifacts_path.resolve()),
        source_artifacts_sha256=_sha256(source_artifacts_path),
        source_extension_report_path=str(source_extension_report_path),
        source_extension_report_sha256=_sha256(source_extension_report_path),
        source_extension_report_id=extension.report_id,
        development_policy_path=str(development_policy_path.resolve()),
        development_policy_sha256=_sha256(development_policy_path),
        development_policy_id=policy.policy_id,
        sampling_salt=sampling_salt,
        excluded_group_ids=tuple(sorted(item.group_id for item in source.groups)),
        excluded_semantic_signatures=tuple(sorted(prior_signatures)),
        excluded_evidence_ids=tuple(sorted(prior_evidence_ids)),
        excluded_evidence_version_ids=tuple(sorted(prior_version_ids)),
        groups=groups,
        selections=tuple(selections),
        public_contract_audit=static_audit,
        freshness=freshness,
        static_task_count=len(selected_tasks),
        selected_binding_count=len(selections),
        population_ready=ready,
        next_permitted_stage=(
            "flash_capability_support_confirmation"
            if ready
            else "capability_support_population_repair_only"
        ),
    )
    _write_immutable_model(output_path, population)
    return population


def _runtime_context(
    task: CapabilitySensitiveTaskArtifact,
    runtime: CapabilityRuntimeArm,
    profile: IterativeAgentProtocolProfile,
) -> tuple[Any, Any, Any]:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
        make_v25_native_runtime_context,
    )

    return make_v25_native_runtime_context(task, runtime, profile)


def prepare_capability_support_confirmation(
    *,
    source_population_path: Path,
    source_runtime_contract_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceCapabilitySupportConfirmationContract:
    if output_path.exists():
        raise ValueError("support confirmation contract is immutable and already exists")
    population = FinanceCapabilitySupportPopulation.model_validate_json(
        source_population_path.read_text(encoding="utf-8")
    )
    source_runtime = FinanceRuntimeResolutionContract.model_validate_json(
        source_runtime_contract_path.read_text(encoding="utf-8")
    )
    if not population.population_ready:
        raise ValueError("support population did not pass its static gates")
    flash_contracts = tuple(
        item for item in source_runtime.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(flash_contracts) != 1:
        raise ValueError("source Runtime does not freeze exactly one Flash model")
    profile = source_runtime.protocol_profile
    source_tasks = {item.artifact_id: item for item in population.all_tasks}
    repaired_by_source: dict[str, CapabilitySensitiveTaskArtifact] = {}
    task_group_ids: dict[str, str] = {}
    selection_tasks: list[tuple[CapabilitySupportSelection, CapabilitySensitiveTaskArtifact]] = []
    for selection in population.selections:
        source = source_tasks[selection.source_task_artifact_id]
        task = repaired_by_source.get(source.artifact_id)
        if task is None:
            task = _repair_task(
                source,
                run_id=run_id,
                stage=RuntimeResolutionStage.HELDOUT_CONFIRMATION,
            )
            repaired_by_source[source.artifact_id] = task
            task_group_ids[task.artifact_id] = selection.group_id
        selection_tasks.append((selection, task))
    bindings = tuple(
        _make_runtime_binding(task, selection.runtime_arm, profile)
        for selection, task in selection_tasks
    )
    tasks = tuple(sorted(repaired_by_source.values(), key=lambda item: item.artifact_id))
    tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "population_id": population.population_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
            },
            prefix="finance_capability_support_rollout_identity:",
        )
        for binding in bindings
        for replicate in range(REPLICAS_PER_TASK)
    }
    finance_config = Path(source_runtime.finance_archive_config_path)
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_population_path": str(source_population_path.resolve()),
        "source_population_sha256": _sha256(source_population_path),
        "source_population_id": population.population_id,
        "source_runtime_contract_path": str(source_runtime_contract_path.resolve()),
        "source_runtime_contract_sha256": _sha256(source_runtime_contract_path),
        "source_runtime_contract_id": source_runtime.contract_id,
        "finance_archive_config_path": str(finance_config.resolve()),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation, prefix="runtime_resolution_implementation:"
        ),
        "model_contracts": flash_contracts,
        "protocol_profile": profile,
        "runtime_thresholds": RuntimeResolutionThresholds(),
        "information_thresholds": WorkflowInformationThresholds(),
        "tasks": tasks,
        "source_task_artifact_ids": {
            task.artifact_id: source_id for source_id, task in repaired_by_source.items()
        },
        "task_group_ids": task_group_ids,
        "bindings": bindings,
        "replicas": REPLICAS_PER_TASK,
        "requested_rollout_count": len(bindings) * REPLICAS_PER_TASK,
        "maximum_model_tokens_per_rollout": source_runtime.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": source_runtime.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": source_runtime.maximum_public_context_bytes,
        "model_contract_repair_attempts": source_runtime.model_contract_repair_attempts,
        "rollout_identity_tokens": tokens,
    }
    provisional = FinanceCapabilitySupportConfirmationContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceCapabilitySupportConfirmationContract(
        contract_id=support_confirmation_contract_id(provisional), **values
    )
    _write_immutable_model(output_path, contract)
    return contract


def run_capability_support_confirmation(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceCapabilitySupportConfirmationReport:
    contract = FinanceCapabilitySupportConfirmationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_confirmation_inputs(contract)
    prefix = "capability_support_fresh_confirmation"
    outcomes, discovered = _execute_stage(
        contract=cast(Any, contract),
        tasks={item.artifact_id: item for item in contract.tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records_path = output_dir / f"{prefix}_records.jsonl"
    outcomes_path = output_dir / f"{prefix}_outcomes.jsonl"
    records = _load_records(records_path)
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    outcome_by_key = {(item.binding_id, item.replicate): item for item in outcomes}
    terminals = tuple(
        _make_terminal_outcome(
            cast(Any, contract),
            record,
            outcome_by_key[(record.binding_id, record.replicate)],
            binding_by_id[record.binding_id],
        )
        for record in records
    )
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    _write_jsonl_atomic(terminal_path, (item.model_dump(mode="json") for item in terminals))
    overall = _metrics(terminals)
    runtime_metrics = {
        runtime: _runtime_metrics(tuple(item for item in terminals if item.runtime_arm == runtime))
        for runtime in WORKFLOW_RUNTIME_ARMS
    }
    runtime_gates = tuple(
        gate
        for runtime in (None, *WORKFLOW_RUNTIME_ARMS)
        for gate in _runtime_qualification_gates(
            overall if runtime is None else runtime_metrics[runtime],
            contract.runtime_thresholds,
            runtime,
        )
    )
    runtime_ready = all(item.passed for item in runtime_gates)
    cells: tuple[FlashInformationCell, ...] = ()
    if runtime_ready:
        view = _InformationContractView(
            contract_id=contract.contract_id,
            thresholds=contract.information_thresholds,
            bootstrap_replicates=contract.information_thresholds.bootstrap_replicates,
        )
        cells = tuple(
            _augment_information_cell(
                _make_information_cell(
                    contract=cast(Any, view),
                    source_contract=cast(Any, contract),
                    terminals=terminals,
                    runtime=runtime,
                ),
                runtime=runtime,
                terminals=terminals,
                bindings=contract.bindings,
                task_group_ids=contract.task_group_ids,
                thresholds=contract.information_thresholds,
            )
            for runtime in WORKFLOW_RUNTIME_ARMS
        )
    info_ready = (
        runtime_ready
        and len(cells) == len(WORKFLOW_RUNTIME_ARMS)
        and all(item.passed for item in cells)
    )
    failure_codes = tuple(
        sorted(
            [
                *(
                    "runtime:"
                    f"{item.runtime_arm.value if item.runtime_arm else 'overall'}:"
                    f"{item.gate_id}"
                    for item in runtime_gates
                    if not item.passed
                ),
                *(
                    f"information:{cell.runtime_arm.value}:{gate.gate_id}"
                    for cell in cells
                    for gate in cell.gates
                    if not gate.passed
                ),
            ]
        )
    )
    values = {
        "contract_id": contract.contract_id,
        "requested_rollout_count": contract.requested_rollout_count,
        "recorded_rollout_count": len(terminals),
        "runtime_eligible_rollout_count": sum(
            item.runtime_eligible_for_capability_denominator for item in terminals
        ),
        "overall_metrics": overall,
        "runtime_metrics": runtime_metrics,
        "runtime_gates": runtime_gates,
        "runtime_qualification_passed": runtime_ready,
        "information_cells": cells,
        "information_matrix_ready": info_ready,
        "failure_codes": failure_codes,
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.terminal_outcome_id for item in terminals)),
            prefix="finance_capability_support_confirmation_outcomes:",
        ),
        "api_call_count": overall.api_call_count,
        "total_model_tokens": overall.total_model_tokens,
        "estimated_cost_usd": overall.estimated_cost_usd,
        "pro_sparse_anchor_authorized": info_ready,
        "next_permitted_stage": (
            "runtime_measurement_repair_only"
            if not runtime_ready
            else (
                "pro_sparse_anchor_preparation"
                if info_ready
                else "capability_task_support_redesign_only"
            )
        ),
    }
    provisional = FinanceCapabilitySupportConfirmationReport.model_construct(
        report_id="pending", **values
    )
    report = FinanceCapabilitySupportConfirmationReport(
        report_id=support_confirmation_report_id(provisional), **values
    )
    report_path = output_dir / "finance_capability_support_confirmation_report.json"
    _write_immutable_model(report_path, report)
    markdown_path = output_dir / "finance_capability_support_confirmation_report.md"
    markdown_path.write_text(_render_report(report), encoding="utf-8")
    _write_immutable_json(
        output_dir / "capability_support_confirmation_manifest.json",
        _confirmation_manifest_payload(
            contract_id=contract.contract_id,
            discovered_models=discovered,
            records_sha256=_sha256(records_path),
            outcomes_sha256=_sha256(outcomes_path),
            terminal_outcomes_sha256=_sha256(terminal_path),
            report_id=report.report_id,
            report_sha256=_sha256(report_path),
        ),
    )
    return report


class _InformationContractView(FrozenModel):
    contract_id: str
    thresholds: WorkflowInformationThresholds
    bootstrap_replicates: int


def _runtime_qualification_gates(
    metrics: RuntimeResolutionMetrics | CapabilitySupportRuntimeMetrics,
    thresholds: RuntimeResolutionThresholds,
    runtime: CapabilityRuntimeArm | None,
) -> tuple[SupportRuntimeGate, ...]:
    checks = (
        (
            "api_transport_resolution",
            metrics.api_transport_resolution_rate,
            thresholds.minimum_api_transport_resolution_rate,
            ">=",
        ),
        (
            "bounded_json_resolution",
            metrics.bounded_json_resolution_rate,
            thresholds.minimum_bounded_json_rate,
            ">=",
        ),
        (
            "observation_replay",
            metrics.observation_replay_rate,
            thresholds.minimum_observation_replay_rate,
            ">=",
        ),
        (
            "authority_integrity",
            metrics.authority_integrity_rate,
            thresholds.minimum_authority_integrity_rate,
            ">=",
        ),
        (
            "terminal_resolution",
            metrics.terminal_resolution_rate,
            thresholds.minimum_terminal_resolution_rate,
            ">=",
        ),
        (
            "failure_attribution",
            metrics.failure_attribution_coverage_rate,
            thresholds.minimum_failure_attribution_coverage_rate,
            ">=",
        ),
        (
            "external_failure",
            metrics.external_infrastructure_failure_rate,
            thresholds.maximum_external_failure_rate,
            "<=",
        ),
        (
            "runtime_contract_failure",
            metrics.task_runtime_contract_failure_rate,
            thresholds.maximum_runtime_contract_failure_rate,
            "<=",
        ),
        (
            "tool_environment_failure",
            metrics.tool_environment_failure_rate,
            thresholds.maximum_tool_environment_failure_rate,
            "<=",
        ),
        (
            "unattributed_failure",
            metrics.unattributed_failure_rate,
            thresholds.maximum_unattributed_failure_rate,
            "<=",
        ),
        (
            "runtime_prompt_pathology",
            metrics.runtime_prompt_pathology_rate,
            thresholds.maximum_runtime_prompt_pathology_rate,
            "<=",
        ),
    )
    return tuple(
        SupportRuntimeGate(
            gate_id=gate_id,
            runtime_arm=runtime,
            observed=observed,
            requirement=f"{operator}{target}",
            passed=(observed >= target if operator == ">=" else observed <= target),
        )
        for gate_id, observed, target, operator in checks
    )


def _runtime_metrics(
    terminals: Sequence[RuntimeTerminalOutcome],
) -> CapabilitySupportRuntimeMetrics:
    if not terminals:
        raise ValueError("support Runtime metrics require outcomes")
    count = len(terminals)
    eligible = tuple(item for item in terminals if item.runtime_eligible_for_capability_denominator)
    failures = tuple(item for item in terminals if item.primary_failure_layer.value != "l6_success")
    layer_counts: dict[str, int] = defaultdict(int)
    for item in terminals:
        layer_counts[item.primary_failure_layer.value] += 1
    observed_tiers = tuple(
        tier for tier in TIER_ORDER if any(item.tier == tier for item in terminals)
    )

    def rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            raise ValueError("support Runtime rate denominator must be positive")
        return numerator / denominator

    def layer_rate(name: str) -> float:
        return rate(layer_counts[name], count)

    return CapabilitySupportRuntimeMetrics(
        attempted_count=count,
        runtime_eligible_count=len(eligible),
        observed_tiers=observed_tiers,
        api_transport_resolution_rate=rate(
            sum(item.api_transport_resolved for item in terminals), count
        ),
        bounded_json_resolution_rate=rate(
            sum(item.bounded_json_resolution_success for item in terminals), count
        ),
        observation_replay_rate=rate(
            sum(item.observation_replay_success for item in terminals), count
        ),
        authority_integrity_rate=rate(
            sum(item.authority_integrity_success for item in terminals), count
        ),
        terminal_resolution_rate=rate(sum(item.terminal_resolved for item in terminals), count),
        failure_attribution_coverage_rate=(
            rate(sum(item.failure_attributed for item in failures), len(failures))
            if failures
            else 1.0
        ),
        external_infrastructure_failure_rate=layer_rate("l0_external_infrastructure"),
        task_runtime_contract_failure_rate=layer_rate("l1_task_runtime_contract"),
        tool_environment_failure_rate=layer_rate("l2_tool_environment"),
        unattributed_failure_rate=layer_rate("unattributed_or_mixed_failure"),
        runtime_prompt_pathology_rate=rate(sum(item.prompt_pathology for item in terminals), count),
        valid_success_given_runtime_eligible=(
            rate(sum(item.valid_success for item in eligible), len(eligible)) if eligible else 0.0
        ),
        tier_valid_success_given_runtime_eligible={
            tier: (
                sum(item.valid_success for item in eligible if item.tier == tier)
                / sum(item.tier == tier for item in eligible)
            )
            for tier in observed_tiers
        },
        api_call_count=sum(item.api_call_count for item in terminals),
        total_model_tokens=sum(item.total_model_tokens for item in terminals),
        estimated_cost_usd=round(sum(item.estimated_cost_usd for item in terminals), 9),
    )


def _augment_information_cell(
    cell: FlashInformationCell,
    *,
    runtime: CapabilityRuntimeArm,
    terminals: Sequence[RuntimeTerminalOutcome],
    bindings: Sequence[RuntimeTaskBinding],
    task_group_ids: Mapping[str, str],
    thresholds: WorkflowInformationThresholds,
) -> FlashInformationCell:
    binding_by_task = {
        item.task_artifact_id: item for item in bindings if item.runtime_arm == runtime
    }
    grouped: dict[str, list[RuntimeTerminalOutcome]] = defaultdict(list)
    for item in terminals:
        if item.runtime_arm == runtime and item.runtime_eligible_for_capability_denominator:
            grouped[item.task_artifact_id].append(item)
    weights: dict[str, float] = {}
    boundary_families: set[str] = set()
    for task_id, values in grouped.items():
        probability = sum(item.valid_success for item in values) / len(values)
        weight = probability * (1 - probability)
        group_id = task_group_ids[task_id]
        weights[group_id] = weights.get(group_id, 0.0) + weight
        binding = binding_by_task[task_id]
        primary = FAMILY_PRIMARY_CAPABILITY[binding.family]
        if (
            thresholds.boundary_probability_lower
            <= probability
            <= thresholds.boundary_probability_upper
            and binding.visible_demand.values[primary] > 0
        ):
            boundary_families.add(binding.family)
    total = sum(weights.values())
    maximum_group_share = max(weights.values(), default=0.0) / total if total else 1.0
    minimum_aligned = thresholds.minimum_primary_aligned_family_count[runtime]
    extra = (
        InformationGate(
            gate_id="final_valid_group_dominance",
            category="final_valid_information",
            observed=maximum_group_share,
            requirement=f"<={thresholds.maximum_group_information_share}",
            passed=maximum_group_share <= thresholds.maximum_group_information_share,
        ),
        InformationGate(
            gate_id="primary_aligned_boundary_family_count",
            category="final_valid_information",
            observed=len(boundary_families),
            requirement=f">={minimum_aligned}",
            passed=len(boundary_families) >= minimum_aligned,
        ),
    )
    gates = (*cell.gates, *extra)
    return cell.model_copy(update={"gates": gates, "passed": all(item.passed for item in gates)})


def _verify_confirmation_inputs(
    contract: FinanceCapabilitySupportConfirmationContract,
) -> None:
    checks = (
        (Path(contract.source_population_path), contract.source_population_sha256),
        (Path(contract.source_runtime_contract_path), contract.source_runtime_contract_sha256),
        (Path(contract.finance_archive_config_path), contract.finance_archive_config_sha256),
    )
    for path, expected in checks:
        if _sha256(path) != expected:
            raise ValueError(f"frozen support confirmation input changed: {path}")
    if contract.implementation_manifest_hash != canonical_hash(
        contract.implementation_manifest,
        prefix="runtime_resolution_implementation:",
    ):
        raise ValueError("support confirmation implementation manifest is invalid")
    if contract.implementation_manifest != _implementation_manifest():
        raise ValueError("support confirmation implementation changed after preparation")


def _render_report(report: FinanceCapabilitySupportConfirmationReport) -> str:
    lines = [
        "# Finance Capability-Support Confirmation",
        "",
        f"- Runtime qualification: **{report.runtime_qualification_passed}**",
        f"- Information matrix ready: **{report.information_matrix_ready}**",
        f"- Rollouts: **{report.recorded_rollout_count}/{report.requested_rollout_count}**",
        f"- API calls: **{report.api_call_count}**",
        f"- Model tokens: **{report.total_model_tokens}**",
        f"- Estimated cost: **USD {report.estimated_cost_usd:.6f}**",
        f"- Next permitted stage: **{report.next_permitted_stage}**",
        "",
        "Correctness is reported as a capability response and is not a Runtime qualification gate.",
        "",
    ]
    for cell in report.information_cells:
        lines.extend(
            (
                f"## {cell.runtime_arm.value}",
                "",
                f"- Success: {cell.final_valid.conditional_success_rate}",
                f"- Boundary fraction: {cell.final_valid.boundary_task_fraction}",
                f"- Residual rank: {cell.final_valid.residual_numerical_rank}",
                f"- Effective rank: {cell.final_valid.residual_effective_rank:.6f}",
                f"- Condition number: {cell.final_valid.residual_condition_number:.6f}",
                f"- Maximum family share: {cell.final_valid.maximum_family_information_share:.6f}",
                f"- Informative axes: {cell.final_valid_informative_axis_count}",
                f"- Passed: {cell.passed}",
                "",
            )
        )
    if report.failure_codes:
        lines.extend(("## Failed Gates", "", *(f"- {item}" for item in report.failure_codes), ""))
    return "\n".join(lines)


def support_development_id(value: FinanceCapabilitySupportDevelopment) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="finance_capability_support_development:",
    )


def support_population_id(value: FinanceCapabilitySupportPopulation) -> str:
    return canonical_hash(
        {
            "run_id": value.run_id,
            "source_population_id": value.source_population_id,
            "development_policy_id": value.development_policy_id,
            "sampling_salt": value.sampling_salt,
            "group_hashes": tuple(item.group_hash for item in value.groups),
            "selections": tuple(item.model_dump(mode="json") for item in value.selections),
            "freshness": value.freshness.model_dump(mode="json"),
        },
        prefix="finance_capability_support_population:",
    )


def support_confirmation_contract_id(
    value: FinanceCapabilitySupportConfirmationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_capability_support_confirmation_contract:",
    )


def support_confirmation_report_id(
    value: FinanceCapabilitySupportConfirmationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_support_confirmation_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _confirmation_manifest_payload(
    *,
    contract_id: str,
    discovered_models: Sequence[str],
    records_sha256: str,
    outcomes_sha256: str,
    terminal_outcomes_sha256: str,
    report_id: str,
    report_sha256: str,
) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "runner_version": SUPPORT_CONFIRMATION_RUNNER_VERSION,
        "discovered_models": list(discovered_models),
        "records_sha256": records_sha256,
        "outcomes_sha256": outcomes_sha256,
        "terminal_outcomes_sha256": terminal_outcomes_sha256,
        "report_id": report_id,
        "report_sha256": report_sha256,
        "pro_api_call_count": 0,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Develop and independently confirm capability-informative Finance support."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    develop = commands.add_parser("develop")
    develop.add_argument("--source-runtime-contract", type=Path, required=True)
    develop.add_argument("--source-runtime-report", type=Path, required=True)
    develop.add_argument("--source-terminal-outcomes", type=Path, required=True)
    develop.add_argument("--source-information-report", type=Path, required=True)
    develop.add_argument("--output", type=Path, required=True)
    develop.add_argument("--run-id", required=True)
    population = commands.add_parser("build-population")
    population.add_argument("--source-population", type=Path, required=True)
    population.add_argument("--source-artifacts", type=Path, required=True)
    population.add_argument("--source-extension-report", type=Path, required=True)
    population.add_argument("--development-policy", type=Path, required=True)
    population.add_argument("--output", type=Path, required=True)
    population.add_argument("--run-id", required=True)
    population.add_argument("--sampling-salt", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source-population", type=Path, required=True)
    prepare.add_argument("--source-runtime-contract", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=32)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "develop":
        value = develop_capability_support_policy(
            source_runtime_contract_path=args.source_runtime_contract,
            source_runtime_report_path=args.source_runtime_report,
            source_terminal_outcomes_path=args.source_terminal_outcomes,
            source_information_report_path=args.source_information_report,
            output_path=args.output,
            run_id=args.run_id,
        )
        summary = {
            "policy_id": value.policy_id,
            "rule_count": len(value.rules),
            "next_permitted_stage": value.next_permitted_stage,
        }
    elif args.command == "build-population":
        value = build_capability_support_population(
            source_population_path=args.source_population,
            source_artifacts_path=args.source_artifacts,
            source_extension_report_path=args.source_extension_report,
            development_policy_path=args.development_policy,
            output_path=args.output,
            run_id=args.run_id,
            sampling_salt=args.sampling_salt,
        )
        summary = {
            "population_id": value.population_id,
            "group_count": len(value.groups),
            "selected_binding_count": value.selected_binding_count,
            "population_ready": value.population_ready,
            "freshness": value.freshness.model_dump(mode="json"),
            "next_permitted_stage": value.next_permitted_stage,
        }
    elif args.command == "prepare":
        value = prepare_capability_support_confirmation(
            source_population_path=args.source_population,
            source_runtime_contract_path=args.source_runtime_contract,
            output_path=args.output,
            run_id=args.run_id,
        )
        summary = {
            "contract_id": value.contract_id,
            "task_count": len(value.tasks),
            "binding_count": len(value.bindings),
            "replicas": value.replicas,
            "requested_rollout_count": value.requested_rollout_count,
        }
    else:
        value = run_capability_support_confirmation(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": value.report_id,
            "runtime_qualification_passed": value.runtime_qualification_passed,
            "information_matrix_ready": value.information_matrix_ready,
            "next_permitted_stage": value.next_permitted_stage,
            "failure_codes": value.failure_codes,
            "api_call_count": value.api_call_count,
            "total_model_tokens": value.total_model_tokens,
            "estimated_cost_usd": value.estimated_cost_usd,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
