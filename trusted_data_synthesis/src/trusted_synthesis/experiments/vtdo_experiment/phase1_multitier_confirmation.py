from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import fmean
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_REQUIRED_TOOL_CALLS,
    MAXIMUM_TOOL_CALLS,
    MODEL_TOKEN_BUDGET,
    RUNTIME_AXIS_RESPONSIBILITY,
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    BoundaryStage,
    CapabilityRolloutOutcome,
    ConfidenceInterval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CAPABILITY_BOUNDARY_RUNNER_VERSION,
    CapabilityBoundaryRolloutRecord,
    _run_one,
    _to_outcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_tier_localization import (
    WORKFLOW_RUNTIME_ARMS,
    FinanceMatchedTierLocalizationContract,
    FinanceMatchedTierLocalizationReport,
    _validate_outcomes,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_capability_population import (
    MultiTierCapabilityPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_MODELS,
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_regression import (
    FinancePublicContractRegressionContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    FinanceWorkflowInformationAudit,
    InformationGate,
    WorkflowInformationThresholds,
    _bootstrap_axis_intervals,
    _information_components,
    _InformationRow,
    _normalize_demand,
    _stable_seed,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

MULTITIER_CONFIRMATION_CONTRACT_VERSION = (
    "finance_multitier_confirmation_contract.v1"
)
MULTITIER_SUPPORT_DEVELOPMENT_VERSION = "finance_multitier_support_development.v1"
MULTITIER_FLASH_REPORT_VERSION = "finance_multitier_flash_report.v1"
SPARSE_PRO_ANCHOR_REPORT_VERSION = "finance_sparse_pro_anchor_report.v1"
MULTITIER_INFORMATION_CELL_VERSION = "finance_multitier_information_cell.v1"
MULTITIER_CONFIRMATION_RUNNER_VERSION = "finance_multitier_confirmation_runner.v1"

FLASH_REPLICAS = 5
PRO_ANCHOR_REPLICAS = 3
FLASH_BINDING_COUNT = 63 * len(WORKFLOW_RUNTIME_ARMS)
PRO_ANCHOR_GROUP_COUNT = len(CAPABILITY_SENSITIVE_FAMILIES)
PRO_ANCHOR_BINDING_COUNT = (
    PRO_ANCHOR_GROUP_COUNT * len(DifficultyTier) * len(WORKFLOW_RUNTIME_ARMS)
)
FLASH_ROLLOUT_COUNT = FLASH_BINDING_COUNT * FLASH_REPLICAS
PRO_ANCHOR_ROLLOUT_COUNT = PRO_ANCHOR_BINDING_COUNT * PRO_ANCHOR_REPLICAS


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MultiTierStageExecutionContract(Protocol):
    contract_id: str
    finance_archive_config_path: str
    model_contracts: tuple[ExplorerModelContract, ...]
    protocol_profile: IterativeAgentProtocolProfile
    maximum_model_tokens_per_rollout: int
    model_contract_repair_attempts: int


class MultiTierSupportRule(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    primary_tiers: tuple[DifficultyTier, ...]
    secondary_tiers: tuple[DifficultyTier, ...]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rule(self) -> MultiTierSupportRule:
        if self.runtime_arm not in WORKFLOW_RUNTIME_ARMS:
            raise ValueError("multi-Tier support includes a non-workflow Runtime")
        if self.family not in CAPABILITY_SENSITIVE_FAMILIES:
            raise ValueError("multi-Tier support includes an unknown family")
        primary = set(self.primary_tiers)
        secondary = set(self.secondary_tiers)
        if primary & secondary or primary | secondary != set(DifficultyTier):
            raise ValueError("multi-Tier support must partition all frozen Tiers")
        primary_axis = FAMILY_PRIMARY_CAPABILITY[self.family]
        if RUNTIME_AXIS_RESPONSIBILITY[self.runtime_arm][primary_axis] == 0:
            if primary or secondary != set(DifficultyTier):
                raise ValueError("Host-controlled primary axes must remain secondary-only")
        elif len(primary) < 2:
            raise ValueError("primary multi-Tier support requires at least two Tiers")
        if self.family == "finance.recovery_guided_search" and (
            DifficultyTier.EASY_CONTROL in primary
        ):
            raise ValueError("Recovery Easy lacks the typed failure/recovery contrast")
        return self


class DevelopmentInformationCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    regularized_log_determinant: float
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    maximum_family_information_share: float = Field(ge=0, le=1)
    maximum_group_information_share: float = Field(ge=0, le=1)


class MultiTierSupportCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    candidate_name: str = Field(min_length=1)
    support_rules: tuple[MultiTierSupportRule, ...] = Field(min_length=14, max_length=14)
    information_cells: tuple[DevelopmentInformationCell, ...] = Field(
        min_length=4,
        max_length=4,
    )
    robust_log_determinant: float
    minimum_numerical_rank: int = Field(ge=0)
    minimum_effective_rank: float = Field(ge=0)
    maximum_condition_number: float = Field(ge=1)
    maximum_family_information_share: float = Field(ge=0, le=1)
    maximum_group_information_share: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_candidate(self) -> MultiTierSupportCandidate:
        _validate_support_rules(self.support_rules)
        if self.robust_log_determinant != min(
            item.regularized_log_determinant for item in self.information_cells
        ):
            raise ValueError("support candidate robust logdet is inconsistent")
        if self.minimum_numerical_rank != min(
            item.residual_numerical_rank for item in self.information_cells
        ):
            raise ValueError("support candidate minimum rank is inconsistent")
        if self.minimum_effective_rank != min(
            item.residual_effective_rank for item in self.information_cells
        ):
            raise ValueError("support candidate effective rank is inconsistent")
        if self.maximum_condition_number != max(
            item.residual_condition_number for item in self.information_cells
        ):
            raise ValueError("support candidate condition number is inconsistent")
        if self.candidate_id != multitier_support_candidate_id(self):
            raise ValueError("support candidate identity is invalid")
        return self


class FinanceMultiTierSupportDevelopment(FrozenModel):
    policy_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    localization_contract_path: str = Field(min_length=1)
    localization_contract_sha256: str = Field(min_length=64, max_length=64)
    localization_contract_id: str = Field(min_length=1)
    localization_report_path: str = Field(min_length=1)
    localization_report_sha256: str = Field(min_length=64, max_length=64)
    localization_report_id: str = Field(min_length=1)
    localization_outcomes_path: str = Field(min_length=1)
    localization_outcomes_sha256: str = Field(min_length=64, max_length=64)
    localization_outcome_set_hash: str = Field(min_length=1)
    information_audit_path: str = Field(min_length=1)
    information_audit_sha256: str = Field(min_length=64, max_length=64)
    information_audit_id: str = Field(min_length=1)
    ridge: float = Field(default=1e-6, gt=0)
    selection_objective: str = (
        "maximize worst-cell regularized logdet, then effective rank and numerical "
        "rank; minimize condition number and family/group dominance"
    )
    candidates: tuple[MultiTierSupportCandidate, ...] = Field(min_length=4, max_length=4)
    selected_candidate_id: str = Field(min_length=1)
    selected_support_rules: tuple[MultiTierSupportRule, ...] = Field(
        min_length=14,
        max_length=14,
    )
    development_only: Literal[True] = True
    fresh_confirmation_outcomes_access: Literal["forbidden"] = "forbidden"
    model_ranking_authorized: Literal[False] = False
    schema_version: str = MULTITIER_SUPPORT_DEVELOPMENT_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> FinanceMultiTierSupportDevelopment:
        if self.schema_version != MULTITIER_SUPPORT_DEVELOPMENT_VERSION:
            raise ValueError("multi-Tier support development version is unsupported")
        ids = {item.candidate_id for item in self.candidates}
        if len(ids) != len(self.candidates):
            raise ValueError("support development candidates are duplicated")
        selected = max(self.candidates, key=_support_candidate_selection_key)
        if self.selected_candidate_id != selected.candidate_id:
            raise ValueError("support development selected another candidate")
        if self.selected_support_rules != selected.support_rules:
            raise ValueError("support development rules differ from selected candidate")
        if self.policy_id != multitier_support_development_id(self):
            raise ValueError("multi-Tier support development identity is invalid")
        return self


class MultiTierInformationCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    primary_families: tuple[str, ...] = Field(min_length=1)
    primary_tiers_by_family: dict[str, tuple[DifficultyTier, ...]] = Field(
        min_length=1
    )
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    mean_success_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    residual_information_eigenvalues: tuple[float, ...]
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    marginal_axis_intervals: dict[str, ConfidenceInterval]
    informative_axis_count: int = Field(ge=0)
    family_information_share: dict[str, float]
    group_information_share: dict[str, float] = Field(min_length=1)
    maximum_family_information_share: float = Field(ge=0, le=1)
    maximum_group_information_share: float = Field(ge=0, le=1)
    primary_aligned_family_count: int = Field(ge=0)
    gates: tuple[InformationGate, ...] = Field(min_length=9)
    passed: bool
    schema_version: str = MULTITIER_INFORMATION_CELL_VERSION

    @model_validator(mode="after")
    def validate_cell(self) -> MultiTierInformationCell:
        if self.schema_version != MULTITIER_INFORMATION_CELL_VERSION:
            raise ValueError("multi-Tier information cell version is unsupported")
        if set(self.primary_tiers_by_family) != set(self.primary_families):
            raise ValueError("multi-Tier information family/Tier support is incomplete")
        if len(self.residual_information_eigenvalues) != len(CAPABILITY_AXES):
            raise ValueError("multi-Tier residual spectrum is incomplete")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("multi-Tier marginal information is incomplete")
        if set(self.marginal_axis_intervals) != set(CAPABILITY_AXES):
            raise ValueError("multi-Tier intervals are incomplete")
        if set(self.family_information_share) != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("multi-Tier family shares are incomplete")
        if not math.isclose(
            self.maximum_family_information_share,
            max(self.family_information_share.values()),
            abs_tol=1e-12,
        ):
            raise ValueError("multi-Tier family dominance is inconsistent")
        if not math.isclose(
            self.maximum_group_information_share,
            max(self.group_information_share.values()),
            abs_tol=1e-12,
        ):
            raise ValueError("multi-Tier group dominance is inconsistent")
        if self.passed != all(item.passed for item in self.gates):
            raise ValueError("multi-Tier information decision is inconsistent")
        return self


class FinanceMultiTierConfirmationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    regression_contract_path: str = Field(min_length=1)
    regression_contract_sha256: str = Field(min_length=64, max_length=64)
    regression_contract_id: str = Field(min_length=1)
    development_localization_contract_path: str = Field(min_length=1)
    development_localization_contract_sha256: str = Field(min_length=64, max_length=64)
    development_localization_contract_id: str = Field(min_length=1)
    development_localization_report_path: str = Field(min_length=1)
    development_localization_report_sha256: str = Field(min_length=64, max_length=64)
    development_localization_report_id: str = Field(min_length=1)
    development_information_audit_path: str = Field(min_length=1)
    development_information_audit_sha256: str = Field(min_length=64, max_length=64)
    development_information_audit_id: str = Field(min_length=1)
    support_development_path: str = Field(min_length=1)
    support_development_sha256: str = Field(min_length=64, max_length=64)
    support_development_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=2, max_length=2)
    protocol_profile: IterativeAgentProtocolProfile
    task_group_ids: dict[str, str] = Field(min_length=63)
    support_rules: tuple[MultiTierSupportRule, ...] = Field(min_length=14, max_length=14)
    flash_bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=FLASH_BINDING_COUNT,
        max_length=FLASH_BINDING_COUNT,
    )
    pro_anchor_group_ids: dict[str, str] = Field(
        min_length=PRO_ANCHOR_GROUP_COUNT,
        max_length=PRO_ANCHOR_GROUP_COUNT,
    )
    pro_anchor_bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=PRO_ANCHOR_BINDING_COUNT,
        max_length=PRO_ANCHOR_BINDING_COUNT,
    )
    flash_replicas: int = Field(default=FLASH_REPLICAS, ge=5, le=5)
    pro_anchor_replicas: int = Field(default=PRO_ANCHOR_REPLICAS, ge=3, le=3)
    flash_requested_rollouts: int = Field(
        default=FLASH_ROLLOUT_COUNT,
        ge=FLASH_ROLLOUT_COUNT,
        le=FLASH_ROLLOUT_COUNT,
    )
    pro_anchor_requested_rollouts: int = Field(
        default=PRO_ANCHOR_ROLLOUT_COUNT,
        ge=PRO_ANCHOR_ROLLOUT_COUNT,
        le=PRO_ANCHOR_ROLLOUT_COUNT,
    )
    pro_to_flash_rollout_ratio: float = Field(ge=0.20, le=0.40)
    maximum_tool_calls: int = Field(default=MAXIMUM_TOOL_CALLS, ge=1)
    maximum_failed_tool_calls: int = Field(default=MAXIMUM_FAILED_TOOL_CALLS, ge=0)
    maximum_total_observation_bytes: int = Field(default=MAXIMUM_OBSERVATION_BYTES, ge=1)
    maximum_model_tokens_per_rollout: int = Field(default=MODEL_TOKEN_BUDGET, ge=1)
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    thresholds: WorkflowInformationThresholds
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    pro_anchor_salt: str = Field(min_length=1)
    support_rule_developed_on_v25_11_only: Literal[True] = True
    fresh_confirmation_outcomes_unseen_at_freeze: Literal[True] = True
    stage_order: tuple[str, str] = ("flash_full_support", "pro_sparse_anchor")
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_started: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_full_support"] = "flash_full_support"
    schema_version: str = MULTITIER_CONFIRMATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceMultiTierConfirmationContract:
        if self.schema_version != MULTITIER_CONFIRMATION_CONTRACT_VERSION:
            raise ValueError("multi-Tier confirmation version is unsupported")
        if self.maximum_tool_calls != (
            MAXIMUM_REQUIRED_TOOL_CALLS + self.maximum_failed_tool_calls
        ):
            raise ValueError("multi-Tier confirmation lacks recovery-call capacity")
        if {item.arm for item in self.model_contracts} != set(ExplorerArm):
            raise ValueError("multi-Tier confirmation requires frozen Pro and Flash identities")
        _validate_support_rules(self.support_rules)
        _validate_binding_manifest(self)
        expected_ratio = self.pro_anchor_requested_rollouts / self.flash_requested_rollouts
        if not math.isclose(self.pro_to_flash_rollout_ratio, expected_ratio, abs_tol=1e-12):
            raise ValueError("multi-Tier asymmetric rollout ratio is inconsistent")
        if self.contract_id != multitier_confirmation_contract_id(self):
            raise ValueError("multi-Tier confirmation identity is invalid")
        return self


class FinanceMultiTierFlashReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    primary_rollout_count: int = Field(ge=1)
    secondary_diagnostic_rollout_count: int = Field(ge=0)
    information_cells: tuple[MultiTierInformationCell, ...] = Field(min_length=2, max_length=2)
    technical_resolution_rate: float = Field(ge=0, le=1)
    technical_status: Literal["passed", "failed"]
    all_information_cells_ready: bool
    flash_information_ready: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_stage_authorized: bool
    next_permitted_stage: Literal[
        "pro_sparse_anchor",
        "flash_support_or_task_redesign_only",
        "runtime_contract_repair_only",
    ]
    pro_flash_ranking_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = MULTITIER_FLASH_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceMultiTierFlashReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("Flash report lacks its complete frozen denominator")
        technical = self.technical_status == "passed"
        information = all(item.passed for item in self.information_cells)
        if self.all_information_cells_ready != information:
            raise ValueError("Flash information readiness is inconsistent")
        ready = technical and information
        if self.flash_information_ready != ready or self.pro_stage_authorized != ready:
            raise ValueError("Flash stage transition is inconsistent")
        expected_next = (
            "runtime_contract_repair_only"
            if not technical
            else (
                "pro_sparse_anchor"
                if information
                else "flash_support_or_task_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("Flash stage is not fail-closed")
        if self.report_id != multitier_flash_report_id(self):
            raise ValueError("Flash report identity is invalid")
        return self


class ProAnchorCell(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    attempted_count: int = Field(ge=1)
    technical_resolution_count: int = Field(ge=0)
    semantic_success_count: int = Field(ge=0)
    semantic_success_rate: float = Field(ge=0, le=1)
    tier_success_rates: dict[DifficultyTier, float] = Field(min_length=3, max_length=3)


class FinanceSparseProAnchorReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    flash_report_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    cells: tuple[ProAnchorCell, ...] = Field(min_length=14, max_length=14)
    technical_resolution_rate: float = Field(ge=0, le=1)
    technical_status: Literal["passed", "failed"]
    at_least_one_success_per_family_runtime: bool
    outcome_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pro_support_role: Literal["sparse_strong_capability_anchor"] = (
        "sparse_strong_capability_anchor"
    )
    model_ranking_authorized: Literal[False] = False
    beneficiary_screening_preparation_authorized: bool
    next_permitted_stage: Literal[
        "beneficiary_boundary_screening_preparation",
        "pro_anchor_or_runtime_repair_only",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = SPARSE_PRO_ANCHOR_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceSparseProAnchorReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("Pro anchor report lacks its frozen denominator")
        ready = (
            self.technical_status == "passed"
            and self.at_least_one_success_per_family_runtime
        )
        if self.beneficiary_screening_preparation_authorized != ready:
            raise ValueError("Pro anchor transition is inconsistent")
        expected = (
            "beneficiary_boundary_screening_preparation"
            if ready
            else "pro_anchor_or_runtime_repair_only"
        )
        if self.next_permitted_stage != expected:
            raise ValueError("Pro anchor stage is not fail-closed")
        if self.report_id != sparse_pro_anchor_report_id(self):
            raise ValueError("Pro anchor report identity is invalid")
        return self


def develop_multitier_support_policy(
    *,
    localization_contract_path: Path,
    localization_report_path: Path,
    localization_outcomes_path: Path,
    information_audit_path: Path,
    output_path: Path,
    run_id: str,
    ridge: float = 1e-6,
) -> FinanceMultiTierSupportDevelopment:
    if output_path.exists():
        raise ValueError("multi-Tier support policy is immutable and exists")
    paths = tuple(
        item.resolve()
        for item in (
            localization_contract_path,
            localization_report_path,
            localization_outcomes_path,
            information_audit_path,
        )
    )
    contract_path, report_path, outcomes_path, audit_path = paths
    contract = FinanceMatchedTierLocalizationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    report = FinanceMatchedTierLocalizationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    audit = FinanceWorkflowInformationAudit.model_validate_json(
        audit_path.read_text(encoding="utf-8")
    )
    outcomes = tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    _validate_outcomes(contract, outcomes)
    if (
        report.contract_id != contract.contract_id
        or report.outcome_set_hash != canonical_hash(
            tuple(sorted(item.outcome_id for item in outcomes)),
            prefix="finance_matched_localization_outcomes:",
        )
        or audit.localization_contract_id != contract.contract_id
        or audit.localization_report_id != report.report_id
        or audit.localization_outcome_set_hash != report.outcome_set_hash
        or audit.empirical_capability_information_ready
        or audit.next_permitted_stage != "workflow_task_redesign_only"
    ):
        raise ValueError("support policy requires the frozen failed v25.11 Development run")
    candidates = tuple(
        _evaluate_development_support_candidate(
            name,
            tiers,
            contract=contract,
            outcomes=outcomes,
            ridge=ridge,
        )
        for name, tiers in (
            ("complete_ladder", tuple(DifficultyTier)),
            (
                "easy_frontier",
                (DifficultyTier.EASY_CONTROL, DifficultyTier.FRONTIER),
            ),
            (
                "frontier_hard",
                (DifficultyTier.FRONTIER, DifficultyTier.HARD_CONTROL),
            ),
            (
                "easy_hard",
                (DifficultyTier.EASY_CONTROL, DifficultyTier.HARD_CONTROL),
            ),
        )
    )
    selected = max(candidates, key=_support_candidate_selection_key)
    values = {
        "run_id": run_id,
        "localization_contract_path": str(contract_path),
        "localization_contract_sha256": _sha256(contract_path),
        "localization_contract_id": contract.contract_id,
        "localization_report_path": str(report_path),
        "localization_report_sha256": _sha256(report_path),
        "localization_report_id": report.report_id,
        "localization_outcomes_path": str(outcomes_path),
        "localization_outcomes_sha256": _sha256(outcomes_path),
        "localization_outcome_set_hash": report.outcome_set_hash,
        "information_audit_path": str(audit_path),
        "information_audit_sha256": _sha256(audit_path),
        "information_audit_id": audit.audit_id,
        "ridge": ridge,
        "candidates": candidates,
        "selected_candidate_id": selected.candidate_id,
        "selected_support_rules": selected.support_rules,
    }
    provisional = FinanceMultiTierSupportDevelopment.model_construct(
        policy_id="pending",
        **values,
    )
    policy = FinanceMultiTierSupportDevelopment(
        policy_id=multitier_support_development_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, policy.model_dump(mode="json"))
    return policy


def _evaluate_development_support_candidate(
    name: str,
    default_tiers: tuple[DifficultyTier, ...],
    *,
    contract: FinanceMatchedTierLocalizationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    ridge: float,
) -> MultiTierSupportCandidate:
    rules = _make_support_rules(default_tiers=default_tiers)
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    rule_by_key = {(item.runtime_arm, item.family): item for item in rules}
    cells = []
    for model in ExplorerArm:
        for runtime in WORKFLOW_RUNTIME_ARMS:
            by_task: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
            for outcome in outcomes:
                binding = binding_by_id[outcome.binding_id]
                if (
                    outcome.model_arm == model
                    and outcome.runtime_arm == runtime
                    and binding.tier
                    in rule_by_key[(runtime, outcome.family)].primary_tiers
                ):
                    by_task[outcome.task_artifact_id].append(outcome)
            rows = []
            for task_id, values in sorted(by_task.items()):
                binding = binding_by_id[values[0].binding_id]
                realizations = tuple(int(item.valid_success) for item in values)
                rows.append(
                    _InformationRow(
                        task_artifact_id=task_id,
                        family=binding.family,
                        group_id=contract.task_group_ids[task_id],
                        probability=sum(realizations) / len(realizations),
                        general_difficulty=binding.general_difficulty,
                        demand=_normalize_demand(binding.visible_demand.values),
                        realizations=realizations,
                    )
                )
            components = _information_components(rows)
            boundary = sum(
                0.10 <= item.probability <= 0.90 for item in rows
            ) / len(rows)
            cells.append(
                DevelopmentInformationCell(
                    model_arm=model,
                    runtime_arm=runtime,
                    task_count=len(rows),
                    rollout_count=sum(len(item.realizations) for item in rows),
                    regularized_log_determinant=sum(
                        math.log(max(0.0, value) + ridge)
                        for value in components.residual_eigenvalues
                    ),
                    residual_numerical_rank=components.numerical_rank,
                    residual_effective_rank=components.effective_rank,
                    residual_condition_number=components.condition_number,
                    boundary_task_fraction=boundary,
                    maximum_family_information_share=max(
                        components.family_information_share.values()
                    ),
                    maximum_group_information_share=max(
                        components.group_information_share.values()
                    ),
                )
            )
    candidate_values = {
        "candidate_name": name,
        "support_rules": rules,
        "information_cells": tuple(cells),
        "robust_log_determinant": min(
            item.regularized_log_determinant for item in cells
        ),
        "minimum_numerical_rank": min(
            item.residual_numerical_rank for item in cells
        ),
        "minimum_effective_rank": min(
            item.residual_effective_rank for item in cells
        ),
        "maximum_condition_number": max(
            item.residual_condition_number for item in cells
        ),
        "maximum_family_information_share": max(
            item.maximum_family_information_share for item in cells
        ),
        "maximum_group_information_share": max(
            item.maximum_group_information_share for item in cells
        ),
    }
    provisional = MultiTierSupportCandidate.model_construct(
        candidate_id="pending",
        **candidate_values,
    )
    return MultiTierSupportCandidate(
        candidate_id=multitier_support_candidate_id(provisional),
        **candidate_values,
    )


def _support_candidate_selection_key(
    item: MultiTierSupportCandidate,
) -> tuple[float, float, int, float, float, float, str]:
    return (
        item.robust_log_determinant,
        item.minimum_effective_rank,
        item.minimum_numerical_rank,
        -item.maximum_condition_number,
        -item.maximum_family_information_share,
        -item.maximum_group_information_share,
        item.candidate_name,
    )


def prepare_multitier_confirmation_contract(
    *,
    population_path: Path,
    development_localization_contract_path: Path,
    development_localization_report_path: Path,
    development_information_audit_path: Path,
    support_development_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
    pro_anchor_salt: str,
) -> FinanceMultiTierConfirmationContract:
    if output_path.exists():
        raise ValueError("multi-Tier confirmation contract is immutable and exists")
    population_path = population_path.resolve()
    development_localization_contract_path = (
        development_localization_contract_path.resolve()
    )
    development_localization_report_path = development_localization_report_path.resolve()
    development_information_audit_path = development_information_audit_path.resolve()
    support_development_path = support_development_path.resolve()
    population = MultiTierCapabilityPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    if not population.audit.multi_tier_population_ready:
        raise ValueError("multi-Tier confirmation requires a ready fresh population")
    regression_path = Path(population.regression_contract_path).resolve()
    regression = FinancePublicContractRegressionContract.model_validate_json(
        regression_path.read_text(encoding="utf-8")
    )
    development_contract = FinanceMatchedTierLocalizationContract.model_validate_json(
        development_localization_contract_path.read_text(encoding="utf-8")
    )
    development_report = FinanceMatchedTierLocalizationReport.model_validate_json(
        development_localization_report_path.read_text(encoding="utf-8")
    )
    development_audit = FinanceWorkflowInformationAudit.model_validate_json(
        development_information_audit_path.read_text(encoding="utf-8")
    )
    support_development = FinanceMultiTierSupportDevelopment.model_validate_json(
        support_development_path.read_text(encoding="utf-8")
    )
    if (
        development_report.contract_id != development_contract.contract_id
        or development_audit.localization_contract_id != development_contract.contract_id
        or development_audit.localization_report_id != development_report.report_id
        or development_audit.empirical_capability_information_ready
        or development_audit.next_permitted_stage != "workflow_task_redesign_only"
        or support_development.localization_contract_id != development_contract.contract_id
        or support_development.localization_report_id != development_report.report_id
        or support_development.information_audit_id != development_audit.audit_id
    ):
        raise ValueError("v25.11 Development lineage does not authorize fresh redesign")
    exposure_ids = {
        item.contract_id for item in population.additional_exposure_contract_references
    }
    if development_contract.contract_id not in exposure_ids:
        raise ValueError("fresh population did not exclude the Development contract")
    tasks = population.tasks
    task_group_ids = {
        task.artifact_id: group.group_id
        for group in population.groups
        for task in group.variants
    }
    flash_bindings = tuple(
        _make_runtime_binding(task, runtime, population.protocol_profile)
        for task in tasks
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    anchor_groups = _select_pro_anchor_groups(population, pro_anchor_salt)
    anchor_task_ids = {
        task.artifact_id
        for group in population.groups
        if group.group_id in set(anchor_groups.values())
        for task in group.variants
    }
    pro_bindings = tuple(
        item for item in flash_bindings if item.task_artifact_id in anchor_task_ids
    )
    support_rules = support_development.selected_support_rules
    values = {
        "run_id": run_id,
        "population_path": str(population_path),
        "population_sha256": _sha256(population_path),
        "population_id": population.population_id,
        "regression_contract_path": str(regression_path),
        "regression_contract_sha256": _sha256(regression_path),
        "regression_contract_id": regression.contract_id,
        "development_localization_contract_path": str(
            development_localization_contract_path
        ),
        "development_localization_contract_sha256": _sha256(
            development_localization_contract_path
        ),
        "development_localization_contract_id": development_contract.contract_id,
        "development_localization_report_path": str(
            development_localization_report_path
        ),
        "development_localization_report_sha256": _sha256(
            development_localization_report_path
        ),
        "development_localization_report_id": development_report.report_id,
        "development_information_audit_path": str(development_information_audit_path),
        "development_information_audit_sha256": _sha256(
            development_information_audit_path
        ),
        "development_information_audit_id": development_audit.audit_id,
        "support_development_path": str(support_development_path),
        "support_development_sha256": _sha256(support_development_path),
        "support_development_id": support_development.policy_id,
        "finance_archive_config_path": regression.finance_archive_config_path,
        "finance_archive_config_sha256": regression.finance_archive_config_sha256,
        "model_contracts": regression.model_contracts,
        "protocol_profile": population.protocol_profile,
        "task_group_ids": task_group_ids,
        "support_rules": support_rules,
        "flash_bindings": flash_bindings,
        "pro_anchor_group_ids": anchor_groups,
        "pro_anchor_bindings": pro_bindings,
        "flash_replicas": FLASH_REPLICAS,
        "pro_anchor_replicas": PRO_ANCHOR_REPLICAS,
        "flash_requested_rollouts": FLASH_ROLLOUT_COUNT,
        "pro_anchor_requested_rollouts": PRO_ANCHOR_ROLLOUT_COUNT,
        "pro_to_flash_rollout_ratio": PRO_ANCHOR_ROLLOUT_COUNT
        / FLASH_ROLLOUT_COUNT,
        "maximum_tool_calls": MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_total_observation_bytes": MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": 2,
        "thresholds": WorkflowInformationThresholds(),
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "pro_anchor_salt": pro_anchor_salt,
    }
    provisional = FinanceMultiTierConfirmationContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceMultiTierConfirmationContract(
        contract_id=multitier_confirmation_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_multitier_flash_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceMultiTierFlashReport:
    contract = _load_contract(contract_path)
    population = _load_population(contract)
    outcomes, discovery = _execute_stage(
        contract=contract,
        tasks={item.artifact_id: item for item in population.tasks},
        bindings=contract.flash_bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.flash_replicas,
        output_dir=output_dir,
        prefix="flash_full_support",
        workers=workers,
    )
    report = make_multitier_flash_report(contract, outcomes)
    report_path = output_dir / "finance_multitier_flash_report.json"
    _write_immutable_model(report_path, report)
    _write_stage_manifest(
        output_dir / "flash_full_support_manifest.json",
        contract=contract,
        prefix="flash_full_support",
        model_arm=ExplorerArm.FLASH,
        discovered=discovery,
        report_id=report.report_id,
        report_path=report_path,
        outcome_set_hash=report.outcome_set_hash,
    )
    return report


def run_sparse_pro_anchor_stage(
    *,
    contract_path: Path,
    flash_report_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceSparseProAnchorReport:
    contract = _load_contract(contract_path)
    flash_report = FinanceMultiTierFlashReport.model_validate_json(
        flash_report_path.read_text(encoding="utf-8")
    )
    if (
        flash_report.contract_id != contract.contract_id
        or flash_report.next_permitted_stage != "pro_sparse_anchor"
        or not flash_report.pro_stage_authorized
    ):
        raise ValueError("Flash information Gate did not authorize Pro spending")
    population = _load_population(contract)
    outcomes, discovery = _execute_stage(
        contract=contract,
        tasks={item.artifact_id: item for item in population.tasks},
        bindings=contract.pro_anchor_bindings,
        model_arm=ExplorerArm.PRO,
        replicas=contract.pro_anchor_replicas,
        output_dir=output_dir,
        prefix="pro_sparse_anchor",
        workers=workers,
    )
    report = make_sparse_pro_anchor_report(contract, flash_report, outcomes)
    report_path = output_dir / "finance_sparse_pro_anchor_report.json"
    _write_immutable_model(report_path, report)
    _write_stage_manifest(
        output_dir / "pro_sparse_anchor_manifest.json",
        contract=contract,
        prefix="pro_sparse_anchor",
        model_arm=ExplorerArm.PRO,
        discovered=discovery,
        report_id=report.report_id,
        report_path=report_path,
        outcome_set_hash=report.outcome_set_hash,
    )
    return report


def make_multitier_flash_report(
    contract: FinanceMultiTierConfirmationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceMultiTierFlashReport:
    _validate_stage_outcomes(
        contract,
        outcomes,
        model_arm=ExplorerArm.FLASH,
        bindings=contract.flash_bindings,
        replicas=contract.flash_replicas,
    )
    bindings = {item.binding_id: item for item in contract.flash_bindings}
    rules = {(item.runtime_arm, item.family): item for item in contract.support_rules}
    primary = tuple(
        item
        for item in outcomes
        if bindings[item.binding_id].tier
        in rules[(item.runtime_arm, item.family)].primary_tiers
    )
    cells = tuple(
        _make_multitier_information_cell(
            contract=contract,
            runtime=runtime,
            outcomes=primary,
            binding_by_id=bindings,
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    technical_rate = sum(item.completed for item in outcomes) / len(outcomes)
    technical = _technical_stage_passed(contract, outcomes)
    information = all(item.passed for item in cells)
    failure_codes = tuple(
        sorted(
            ({"technical_resolution"} if not technical else set())
            | {
                f"information:{item.runtime_arm.value}"
                for item in cells
                if not item.passed
            }
        )
    )
    values = {
        "contract_id": contract.contract_id,
        "population_id": contract.population_id,
        "requested_rollout_count": contract.flash_requested_rollouts,
        "recorded_rollout_count": len(outcomes),
        "primary_rollout_count": len(primary),
        "secondary_diagnostic_rollout_count": len(outcomes) - len(primary),
        "information_cells": cells,
        "technical_resolution_rate": technical_rate,
        "technical_status": "passed" if technical else "failed",
        "all_information_cells_ready": information,
        "flash_information_ready": technical and information,
        "failure_codes": failure_codes,
        "outcome_set_hash": _outcome_set_hash(outcomes, "flash"),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "pro_stage_authorized": technical and information,
        "next_permitted_stage": (
            "runtime_contract_repair_only"
            if not technical
            else (
                "pro_sparse_anchor"
                if information
                else "flash_support_or_task_redesign_only"
            )
        ),
    }
    provisional = FinanceMultiTierFlashReport.model_construct(
        report_id="pending",
        **values,
    )
    return FinanceMultiTierFlashReport(
        report_id=multitier_flash_report_id(provisional),
        **values,
    )


def make_sparse_pro_anchor_report(
    contract: FinanceMultiTierConfirmationContract,
    flash_report: FinanceMultiTierFlashReport,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceSparseProAnchorReport:
    _validate_stage_outcomes(
        contract,
        outcomes,
        model_arm=ExplorerArm.PRO,
        bindings=contract.pro_anchor_bindings,
        replicas=contract.pro_anchor_replicas,
    )
    binding_by_id = {item.binding_id: item for item in contract.pro_anchor_bindings}
    grouped: dict[
        tuple[CapabilityRuntimeArm, str], list[CapabilityRolloutOutcome]
    ] = defaultdict(list)
    for item in outcomes:
        grouped[(item.runtime_arm, item.family)].append(item)
    cells = []
    for runtime in WORKFLOW_RUNTIME_ARMS:
        for family in CAPABILITY_SENSITIVE_FAMILIES:
            values = grouped[(runtime, family)]
            tier_rates = {
                tier: sum(
                    item.semantic_answer_correct
                    for item in values
                    if binding_by_id[item.binding_id].tier == tier
                )
                / contract.pro_anchor_replicas
                for tier in DifficultyTier
            }
            semantic = sum(item.semantic_answer_correct for item in values)
            cells.append(
                ProAnchorCell(
                    runtime_arm=runtime,
                    family=family,
                    attempted_count=len(values),
                    technical_resolution_count=sum(item.completed for item in values),
                    semantic_success_count=semantic,
                    semantic_success_rate=semantic / len(values),
                    tier_success_rates=tier_rates,
                )
            )
    technical_rate = sum(item.completed for item in outcomes) / len(outcomes)
    technical = _technical_stage_passed(contract, outcomes)
    support = all(item.semantic_success_count > 0 for item in cells)
    ready = technical and support
    report_values = {
        "contract_id": contract.contract_id,
        "flash_report_id": flash_report.report_id,
        "requested_rollout_count": contract.pro_anchor_requested_rollouts,
        "recorded_rollout_count": len(outcomes),
        "cells": tuple(cells),
        "technical_resolution_rate": technical_rate,
        "technical_status": "passed" if technical else "failed",
        "at_least_one_success_per_family_runtime": support,
        "outcome_set_hash": _outcome_set_hash(outcomes, "pro_anchor"),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "beneficiary_screening_preparation_authorized": ready,
        "next_permitted_stage": (
            "beneficiary_boundary_screening_preparation"
            if ready
            else "pro_anchor_or_runtime_repair_only"
        ),
    }
    provisional = FinanceSparseProAnchorReport.model_construct(
        report_id="pending",
        **report_values,
    )
    return FinanceSparseProAnchorReport(
        report_id=sparse_pro_anchor_report_id(provisional),
        **report_values,
    )


def _execute_stage(
    *,
    contract: MultiTierStageExecutionContract,
    tasks: Mapping[str, Any],
    bindings: tuple[RuntimeTaskBinding, ...],
    model_arm: ExplorerArm,
    replicas: int,
    output_dir: Path,
    prefix: str,
    workers: int,
) -> tuple[tuple[CapabilityRolloutOutcome, ...], tuple[str, ...]]:
    if workers < 1:
        raise ValueError("multi-Tier confirmation workers must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_identity = _stage_run_identity(contract, prefix, model_arm, bindings, replicas)
    checkpoint_path = output_dir / f"{prefix}.checkpoint.jsonl"
    records_path = output_dir / f"{prefix}_records.jsonl"
    outcomes_path = output_dir / f"{prefix}_outcomes.jsonl"
    discovery_path = output_dir / f"{prefix}_model_discovery.json"
    historical = _load_stage_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        contract=contract,
        model_arm=model_arm,
        bindings=bindings,
        replicas=replicas,
    )
    records = {_record_key(item): item for item in historical}
    jobs = tuple(
        (binding, replicate)
        for binding in sorted(bindings, key=lambda item: item.binding_id)
        for replicate in range(replicas)
    )
    pending = tuple(job for job in jobs if _job_key(*job) not in records)
    print(
        f"[multi-tier:{prefix}] resuming {len(records)}/{len(jobs)}; "
        f"executing {len(pending)} with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    model_contract = next(item for item in contract.model_contracts if item.arm == model_arm)
    if pending:
        client = OpenAICompatibleJsonClient(
            model_contract.config.model_copy(
                update={
                    "contract_repair_attempts": contract.model_contract_repair_attempts
                }
            )
        )
        discovered = client.discover_models()
        if EXPECTED_MODELS[model_arm.value] not in discovered:
            raise ValueError(f"provider evidence lacks frozen {model_arm.value} model")
        _write_immutable_json(
            discovery_path,
            {
                "run_identity": run_identity,
                "model_arm": model_arm.value,
                "requested_model": EXPECTED_MODELS[model_arm.value],
                "discovered_models": discovered,
            },
        )
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _run_one,
                    contract,
                    BoundaryStage.TIER_LOCALIZATION,
                    model_arm,
                    binding,
                    tasks[binding.task_artifact_id],
                    replicate,
                    run_identity,
                    client,
                ): (binding.binding_id, replicate)
                for binding, replicate in pending
            }
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                record = future.result()
                if key != _record_key(record):
                    raise ValueError("multi-Tier worker returned another frozen job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                records[key] = record
                if index % 20 == 0 or index == len(futures):
                    print(
                        f"[multi-tier:{prefix}] completed {len(records)}/{len(jobs)}",
                        flush=True,
                    )
    else:
        raw = json.loads(discovery_path.read_text(encoding="utf-8"))
        if raw.get("run_identity") != run_identity:
            raise ValueError("model discovery evidence belongs to another stage run")
        discovered = tuple(str(item) for item in raw.get("discovered_models", ()))
    ordered = tuple(records[_job_key(binding, replicate)] for binding, replicate in jobs)
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    outcomes = tuple(_to_outcome(item, bindings) for item in ordered)
    _write_jsonl_atomic(
        outcomes_path,
        (item.model_dump(mode="json") for item in outcomes),
    )
    return outcomes, tuple(discovered)


def _make_multitier_information_cell(
    *,
    contract: FinanceMultiTierConfirmationContract,
    runtime: CapabilityRuntimeArm,
    outcomes: Sequence[CapabilityRolloutOutcome],
    binding_by_id: Mapping[str, RuntimeTaskBinding],
) -> MultiTierInformationCell:
    rules = {
        item.family: item
        for item in contract.support_rules
        if item.runtime_arm == runtime and item.primary_tiers
    }
    grouped: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
    for outcome in outcomes:
        if outcome.runtime_arm == runtime:
            grouped[outcome.task_artifact_id].append(outcome)
    rows = []
    for task_id, task_outcomes in sorted(grouped.items()):
        binding = binding_by_id[task_outcomes[0].binding_id]
        if binding.family not in rules or binding.tier not in rules[binding.family].primary_tiers:
            continue
        realizations = tuple(int(item.valid_success) for item in task_outcomes)
        rows.append(
            _InformationRow(
                task_artifact_id=task_id,
                family=binding.family,
                group_id=contract.task_group_ids[task_id],
                probability=sum(realizations) / len(realizations),
                general_difficulty=binding.general_difficulty,
                demand=_normalize_demand(binding.visible_demand.values),
                realizations=realizations,
            )
        )
    if not rows:
        raise ValueError("multi-Tier information scope is empty")
    components = _information_components(rows)
    intervals = _bootstrap_axis_intervals(
        rows,
        replicates=contract.thresholds.bootstrap_replicates,
        seed=_stable_seed(
            str(contract.random_seed),
            ExplorerArm.FLASH.value,
            runtime.value,
            "fresh_multitier",
        ),
    )
    visible_axes = {
        axis
        for axis, responsibility in RUNTIME_AXIS_RESPONSIBILITY[runtime].items()
        if responsibility > 0
    }
    informative = sum(
        intervals[axis].lower
        >= contract.thresholds.minimum_marginal_axis_information
        for axis in visible_axes
    )
    boundary = sum(
        contract.thresholds.boundary_probability_lower
        <= row.probability
        <= contract.thresholds.boundary_probability_upper
        for row in rows
    ) / len(rows)
    aligned = sum(
        RUNTIME_AXIS_RESPONSIBILITY[runtime][FAMILY_PRIMARY_CAPABILITY[family]] > 0
        for family in rules
    )
    threshold = contract.thresholds.by_runtime[runtime]
    family_max = max(components.family_information_share.values())
    group_max = max(components.group_information_share.values())
    gates = (
        _gate(
            "runtime_primary_axis_alignment",
            aligned >= contract.thresholds.minimum_primary_aligned_family_count[runtime],
            float(aligned),
            f">={contract.thresholds.minimum_primary_aligned_family_count[runtime]}",
        ),
        _gate(
            "residual_numerical_rank",
            components.numerical_rank >= threshold.minimum_rank,
            float(components.numerical_rank),
            f">={threshold.minimum_rank}",
        ),
        _gate(
            "residual_effective_rank",
            components.effective_rank >= threshold.minimum_effective_rank,
            components.effective_rank,
            f">={threshold.minimum_effective_rank}",
        ),
        _gate(
            "residual_condition_number",
            components.condition_number <= threshold.maximum_condition_number,
            components.condition_number,
            f"<={threshold.maximum_condition_number}",
        ),
        _gate(
            "boundary_task_fraction",
            boundary >= threshold.minimum_boundary_task_fraction,
            boundary,
            f">={threshold.minimum_boundary_task_fraction}",
        ),
        _gate(
            "general_factor_fraction",
            components.general_factor_fraction <= threshold.maximum_general_factor_fraction,
            components.general_factor_fraction,
            f"<={threshold.maximum_general_factor_fraction}",
        ),
        _gate(
            "informative_axis_count",
            informative >= threshold.minimum_informative_axis_count,
            float(informative),
            f">={threshold.minimum_informative_axis_count}",
        ),
        _gate(
            "family_information_dominance",
            family_max <= contract.thresholds.maximum_family_information_share,
            family_max,
            f"<={contract.thresholds.maximum_family_information_share}",
        ),
        _gate(
            "ladder_group_information_dominance",
            group_max <= contract.thresholds.maximum_group_information_share,
            group_max,
            f"<={contract.thresholds.maximum_group_information_share}",
        ),
    )
    return MultiTierInformationCell(
        model_arm=ExplorerArm.FLASH,
        runtime_arm=runtime,
        primary_families=tuple(sorted(rules)),
        primary_tiers_by_family={
            family: rules[family].primary_tiers for family in sorted(rules)
        },
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        mean_success_rate=fmean(item.probability for item in rows),
        boundary_task_fraction=boundary,
        residual_information_eigenvalues=components.residual_eigenvalues,
        residual_numerical_rank=components.numerical_rank,
        residual_effective_rank=components.effective_rank,
        residual_condition_number=components.condition_number,
        general_factor_fraction=components.general_factor_fraction,
        marginal_axis_information=components.marginal_axis_information,
        marginal_axis_intervals=intervals,
        informative_axis_count=informative,
        family_information_share=components.family_information_share,
        group_information_share=components.group_information_share,
        maximum_family_information_share=family_max,
        maximum_group_information_share=group_max,
        primary_aligned_family_count=aligned,
        gates=gates,
        passed=all(item.passed for item in gates),
    )


def _make_support_rules(
    *,
    default_tiers: tuple[DifficultyTier, ...] | None = None,
) -> tuple[MultiTierSupportRule, ...]:
    all_tiers = tuple(DifficultyTier)
    selected_default = default_tiers or all_tiers
    if len(set(selected_default)) != len(selected_default) or not set(
        selected_default
    ) <= set(all_tiers):
        raise ValueError("default multi-Tier support is invalid")
    if len(selected_default) < 2:
        raise ValueError("default multi-Tier support must include at least two Tiers")
    rules = []
    for runtime in WORKFLOW_RUNTIME_ARMS:
        for family in CAPABILITY_SENSITIVE_FAMILIES:
            primary_axis = FAMILY_PRIMARY_CAPABILITY[family]
            if RUNTIME_AXIS_RESPONSIBILITY[runtime][primary_axis] == 0:
                primary: tuple[DifficultyTier, ...] = ()
                secondary = all_tiers
                rationale = (
                    f"Host-controlled {primary_axis} is a secondary demand diagnostic"
                )
            elif family == "finance.recovery_guided_search":
                primary = (
                    DifficultyTier.FRONTIER,
                    DifficultyTier.HARD_CONTROL,
                )
                secondary = (DifficultyTier.EASY_CONTROL,)
                rationale = "only tiers with a typed failure and corrected retry identify recovery"
            else:
                primary = selected_default
                secondary = tuple(
                    tier for tier in all_tiers if tier not in set(selected_default)
                )
                rationale = (
                    "fresh full-ladder support preserves complementary capability directions"
                )
            rules.append(
                MultiTierSupportRule(
                    runtime_arm=runtime,
                    family=family,
                    primary_tiers=primary,
                    secondary_tiers=secondary,
                    rationale=rationale,
                )
            )
    return tuple(rules)


def _select_pro_anchor_groups(
    population: MultiTierCapabilityPopulation,
    salt: str,
) -> dict[str, str]:
    output = {}
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        candidates = tuple(item for item in population.groups if item.family == family)
        output[family] = min(
            candidates,
            key=lambda item: canonical_hash(
                {"salt": salt, "family": family, "group_id": item.group_id},
                prefix="finance_multitier_pro_anchor_selection:",
            ),
        ).group_id
    return dict(sorted(output.items()))


def _validate_support_rules(rules: tuple[MultiTierSupportRule, ...]) -> None:
    keys = {(item.runtime_arm, item.family) for item in rules}
    expected = {
        (runtime, family)
        for runtime in WORKFLOW_RUNTIME_ARMS
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    if keys != expected or len(keys) != len(rules):
        raise ValueError("multi-Tier support rule manifest is incomplete or duplicated")


def _validate_binding_manifest(contract: FinanceMultiTierConfirmationContract) -> None:
    flash_ids = {item.binding_id for item in contract.flash_bindings}
    if len(flash_ids) != FLASH_BINDING_COUNT:
        raise ValueError("Flash binding manifest is duplicated")
    by_task: dict[str, list[RuntimeTaskBinding]] = defaultdict(list)
    for item in contract.flash_bindings:
        by_task[item.task_artifact_id].append(item)
    if set(by_task) != set(contract.task_group_ids) or len(by_task) != 63:
        raise ValueError("Flash task/group denominator is incomplete")
    if any(
        len(values) != len(WORKFLOW_RUNTIME_ARMS)
        or {item.runtime_arm for item in values} != set(WORKFLOW_RUNTIME_ARMS)
        for values in by_task.values()
    ):
        raise ValueError("a Flash task lacks exactly one binding per workflow Runtime")
    family_tier_counts = Counter(
        (values[0].family, values[0].tier) for values in by_task.values()
    )
    if family_tier_counts != Counter(
        {
            (family, tier): 3
            for family in CAPABILITY_SENSITIVE_FAMILIES
            for tier in DifficultyTier
        }
    ):
        raise ValueError("Flash support is not balanced by family, Tier, and group")
    if set(contract.pro_anchor_group_ids) != set(CAPABILITY_SENSITIVE_FAMILIES):
        raise ValueError("Pro anchor group manifest omits a family")
    if len(set(contract.pro_anchor_group_ids.values())) != PRO_ANCHOR_GROUP_COUNT:
        raise ValueError("Pro anchor groups are duplicated")
    pro_ids = {item.binding_id for item in contract.pro_anchor_bindings}
    if len(pro_ids) != PRO_ANCHOR_BINDING_COUNT or not pro_ids <= flash_ids:
        raise ValueError("Pro anchors are not a strict frozen subset of Flash support")
    pro_counts = Counter(
        (item.family, item.tier, item.runtime_arm)
        for item in contract.pro_anchor_bindings
    )
    if set(pro_counts.values()) != {1} or len(pro_counts) != PRO_ANCHOR_BINDING_COUNT:
        raise ValueError("Pro anchor support is not balanced across family/Tier/Runtime")
    if any(
        contract.task_group_ids[item.task_artifact_id]
        != contract.pro_anchor_group_ids[item.family]
        for item in contract.pro_anchor_bindings
    ):
        raise ValueError("Pro binding belongs to a non-preregistered group")


def _technical_stage_passed(
    contract: FinanceMultiTierConfirmationContract,
    outcomes: Sequence[CapabilityRolloutOutcome],
) -> bool:
    resolution_rate = sum(item.completed for item in outcomes) / len(outcomes)
    return bool(
        resolution_rate == 1.0
        and all(item.bounded_json_resolution_success for item in outcomes)
        and all(item.observation_replay_success for item in outcomes)
        and all(item.authority_integrity_success for item in outcomes)
        and not any(item.budget_exhausted for item in outcomes)
        and not any(item.runtime_infrastructure_failure_count for item in outcomes)
    )


def _validate_stage_outcomes(
    contract: FinanceMultiTierConfirmationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    *,
    model_arm: ExplorerArm,
    bindings: tuple[RuntimeTaskBinding, ...],
    replicas: int,
) -> None:
    if len(outcomes) != len(bindings) * replicas:
        raise ValueError("multi-Tier stage outcomes have an incomplete denominator")
    binding_ids = {item.binding_id for item in bindings}
    keys = set()
    for item in outcomes:
        key = (item.binding_id, item.replicate)
        if key in keys:
            raise ValueError("multi-Tier stage duplicates a rollout")
        keys.add(key)
        if (
            item.contract_id != contract.contract_id
            or item.stage != BoundaryStage.TIER_LOCALIZATION
            or item.model_arm != model_arm
            or item.binding_id not in binding_ids
            or not 0 <= item.replicate < replicas
        ):
            raise ValueError("multi-Tier stage contains an unknown rollout")


def _gate(gate_id: str, passed: bool, observed: float, requirement: str) -> InformationGate:
    return InformationGate(
        gate_id=gate_id,
        observed=observed,
        requirement=requirement,
        passed=passed,
    )


def _load_contract(path: Path) -> FinanceMultiTierConfirmationContract:
    contract = FinanceMultiTierConfirmationContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    for frozen_path, expected in (
        (Path(contract.population_path), contract.population_sha256),
        (Path(contract.regression_contract_path), contract.regression_contract_sha256),
        (
            Path(contract.development_localization_contract_path),
            contract.development_localization_contract_sha256,
        ),
        (
            Path(contract.development_localization_report_path),
            contract.development_localization_report_sha256,
        ),
        (
            Path(contract.development_information_audit_path),
            contract.development_information_audit_sha256,
        ),
        (Path(contract.support_development_path), contract.support_development_sha256),
        (Path(contract.finance_archive_config_path), contract.finance_archive_config_sha256),
    ):
        if _sha256(frozen_path) != expected:
            raise ValueError(f"frozen multi-Tier input changed:{frozen_path}")
    policy = FinanceMultiTierSupportDevelopment.model_validate_json(
        Path(contract.support_development_path).read_text(encoding="utf-8")
    )
    if (
        policy.policy_id != contract.support_development_id
        or policy.selected_support_rules != contract.support_rules
    ):
        raise ValueError("multi-Tier confirmation differs from its Development policy")
    return contract


def _load_population(
    contract: FinanceMultiTierConfirmationContract,
) -> MultiTierCapabilityPopulation:
    population = MultiTierCapabilityPopulation.model_validate_json(
        Path(contract.population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.population_id:
        raise ValueError("multi-Tier contract loaded another population")
    return population


def _load_stage_checkpoint(
    path: Path,
    *,
    run_identity: str,
    contract: MultiTierStageExecutionContract,
    model_arm: ExplorerArm,
    bindings: tuple[RuntimeTaskBinding, ...],
    replicas: int,
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    if not path.is_file():
        return ()
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    binding_ids = {item.binding_id for item in bindings}
    keys = set()
    for record in records:
        key = _record_key(record)
        if key in keys:
            raise ValueError("multi-Tier checkpoint duplicates a rollout")
        keys.add(key)
        if (
            record.run_identity != run_identity
            or record.contract_id != contract.contract_id
            or record.model_arm != model_arm
            or record.binding_id not in binding_ids
            or not 0 <= record.replicate < replicas
        ):
            raise ValueError("multi-Tier checkpoint contains an unknown rollout")
    return records


def _record_key(record: CapabilityBoundaryRolloutRecord) -> tuple[str, int]:
    return record.binding_id, record.replicate


def _job_key(binding: RuntimeTaskBinding, replicate: int) -> tuple[str, int]:
    return binding.binding_id, replicate


def _stage_run_identity(
    contract: MultiTierStageExecutionContract,
    prefix: str,
    model_arm: ExplorerArm,
    bindings: tuple[RuntimeTaskBinding, ...],
    replicas: int,
) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "runner_version": MULTITIER_CONFIRMATION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "stage_prefix": prefix,
            "model_arm": model_arm.value,
            "binding_ids": tuple(sorted(item.binding_id for item in bindings)),
            "replicas": replicas,
        },
        prefix="finance_multitier_confirmation_run:",
    )


def _write_stage_manifest(
    path: Path,
    *,
    contract: FinanceMultiTierConfirmationContract,
    prefix: str,
    model_arm: ExplorerArm,
    discovered: tuple[str, ...],
    report_id: str,
    report_path: Path,
    outcome_set_hash: str,
) -> None:
    output_dir = path.parent
    payload = {
        "contract_id": contract.contract_id,
        "population_id": contract.population_id,
        "runner_version": MULTITIER_CONFIRMATION_RUNNER_VERSION,
        "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
        "stage_prefix": prefix,
        "model_arm": model_arm.value,
        "requested_model": EXPECTED_MODELS[model_arm.value],
        "discovered_models": discovered,
        "checkpoint_sha256": _sha256(output_dir / f"{prefix}.checkpoint.jsonl"),
        "records_sha256": _sha256(output_dir / f"{prefix}_records.jsonl"),
        "outcomes_sha256": _sha256(output_dir / f"{prefix}_outcomes.jsonl"),
        "outcome_set_hash": outcome_set_hash,
        "report_id": report_id,
        "report_sha256": _sha256(report_path),
    }
    _write_immutable_json(path, payload)


def _write_immutable_model(path: Path, model: BaseModel) -> None:
    payload = model.model_dump(mode="json")
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError(f"immutable report already differs:{path}")
        return
    _write_json_atomic(path, payload)


def _write_immutable_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.is_file():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError(f"immutable artifact already differs:{path}")
        return
    _write_json_atomic(path, payload)


def _outcome_set_hash(
    outcomes: Sequence[CapabilityRolloutOutcome],
    role: str,
) -> str:
    return canonical_hash(
        tuple(sorted(item.outcome_id for item in outcomes)),
        prefix=f"finance_multitier_{role}_outcomes:",
    )


def multitier_confirmation_contract_id(
    value: FinanceMultiTierConfirmationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_multitier_confirmation_contract:",
    )


def multitier_support_candidate_id(value: MultiTierSupportCandidate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"candidate_id"}),
        prefix="finance_multitier_support_candidate:",
    )


def multitier_support_development_id(
    value: FinanceMultiTierSupportDevelopment,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="finance_multitier_support_development:",
    )


def multitier_flash_report_id(value: FinanceMultiTierFlashReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_multitier_flash_report:",
    )


def sparse_pro_anchor_report_id(value: FinanceSparseProAnchorReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_sparse_pro_anchor_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze and run v25.12 Flash-first multi-Tier confirmation."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    develop = commands.add_parser("develop-policy")
    develop.add_argument("--development-localization-contract", type=Path, required=True)
    develop.add_argument("--development-localization-report", type=Path, required=True)
    develop.add_argument("--development-localization-outcomes", type=Path, required=True)
    develop.add_argument("--development-information-audit", type=Path, required=True)
    develop.add_argument("--output", type=Path, required=True)
    develop.add_argument("--run-id", required=True)
    develop.add_argument("--ridge", type=float, default=1e-6)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--population", type=Path, required=True)
    prepare.add_argument("--development-localization-contract", type=Path, required=True)
    prepare.add_argument("--development-localization-report", type=Path, required=True)
    prepare.add_argument("--development-information-audit", type=Path, required=True)
    prepare.add_argument("--support-development", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=20260813)
    prepare.add_argument("--sampling-salt", required=True)
    prepare.add_argument("--pro-anchor-salt", required=True)
    flash = commands.add_parser("run-flash")
    flash.add_argument("--contract", type=Path, required=True)
    flash.add_argument("--output-dir", type=Path, required=True)
    flash.add_argument("--workers", type=int, default=32)
    pro = commands.add_parser("run-pro")
    pro.add_argument("--contract", type=Path, required=True)
    pro.add_argument("--flash-report", type=Path, required=True)
    pro.add_argument("--output-dir", type=Path, required=True)
    pro.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)
    if args.command == "develop-policy":
        policy = develop_multitier_support_policy(
            localization_contract_path=args.development_localization_contract,
            localization_report_path=args.development_localization_report,
            localization_outcomes_path=args.development_localization_outcomes,
            information_audit_path=args.development_information_audit,
            output_path=args.output,
            run_id=args.run_id,
            ridge=args.ridge,
        )
        selected = next(
            item
            for item in policy.candidates
            if item.candidate_id == policy.selected_candidate_id
        )
        result = {
            "policy_id": policy.policy_id,
            "selected_candidate": selected.candidate_name,
            "robust_log_determinant": selected.robust_log_determinant,
            "minimum_effective_rank": selected.minimum_effective_rank,
            "fresh_confirmation_outcomes_access": (
                policy.fresh_confirmation_outcomes_access
            ),
        }
    elif args.command == "prepare":
        contract = prepare_multitier_confirmation_contract(
            population_path=args.population,
            development_localization_contract_path=(
                args.development_localization_contract
            ),
            development_localization_report_path=args.development_localization_report,
            development_information_audit_path=args.development_information_audit,
            support_development_path=args.support_development,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
            sampling_salt=args.sampling_salt,
            pro_anchor_salt=args.pro_anchor_salt,
        )
        result = {
            "contract_id": contract.contract_id,
            "flash_rollouts": contract.flash_requested_rollouts,
            "pro_anchor_rollouts": contract.pro_anchor_requested_rollouts,
            "pro_to_flash_ratio": contract.pro_to_flash_rollout_ratio,
            "next_permitted_stage": contract.next_permitted_stage,
        }
    elif args.command == "run-flash":
        report = run_multitier_flash_stage(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        result = {
            "report_id": report.report_id,
            "recorded_rollouts": report.recorded_rollout_count,
            "technical_status": report.technical_status,
            "information_ready": report.flash_information_ready,
            "next_permitted_stage": report.next_permitted_stage,
            "api_calls": report.api_call_count,
            "model_tokens": report.total_model_tokens,
            "estimated_cost_usd": report.estimated_cost_usd,
        }
    else:
        report = run_sparse_pro_anchor_stage(
            contract_path=args.contract,
            flash_report_path=args.flash_report,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        result = {
            "report_id": report.report_id,
            "recorded_rollouts": report.recorded_rollout_count,
            "technical_status": report.technical_status,
            "strong_anchor_support": report.at_least_one_success_per_family_runtime,
            "next_permitted_stage": report.next_permitted_stage,
            "api_calls": report.api_call_count,
            "model_tokens": report.total_model_tokens,
            "estimated_cost_usd": report.estimated_cost_usd,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
