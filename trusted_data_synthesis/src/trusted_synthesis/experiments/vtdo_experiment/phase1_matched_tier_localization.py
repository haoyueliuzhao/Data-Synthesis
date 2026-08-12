from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import fmean, pvariance
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_REQUIRED_TOOL_CALLS,
    MAXIMUM_TOOL_CALLS,
    MODEL_TOKEN_BUDGET,
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
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    MATCHED_GROUP_COUNT,
    MATCHED_GROUPS_PER_FAMILY,
    MATCHED_TASK_COUNT,
    MatchedCapabilityLadderPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_MODELS,
    ExplorerArm,
    ExplorerModelContract,
    _paired_sampling_contract_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_regression import (
    FinancePublicContractRegressionContract,
    FinancePublicContractRegressionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_tier_localization_common import (
    TierLocalizationThresholds,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

MATCHED_LOCALIZATION_CONTRACT_VERSION = "finance_matched_tier_localization_contract.v2"
MATCHED_LOCALIZATION_REPORT_VERSION = "finance_matched_tier_localization_report.v2"
MATCHED_LOCALIZATION_RUNNER_VERSION = "finance_matched_tier_localization_runner.v2"

MATCHED_REPLICAS = 5
WORKFLOW_RUNTIME_ARMS: tuple[CapabilityRuntimeArm, ...] = (
    CapabilityRuntimeArm.SCRIPTED_TOOL,
    CapabilityRuntimeArm.AUTONOMOUS_AGENT,
)
MATCHED_BINDING_COUNT = MATCHED_TASK_COUNT * len(WORKFLOW_RUNTIME_ARMS)
MATCHED_ROLLOUT_COUNT = (
    MATCHED_BINDING_COUNT * len(ExplorerArm) * MATCHED_REPLICAS
)
MATCHED_CELL_COUNT = (
    len(ExplorerArm)
    * len(WORKFLOW_RUNTIME_ARMS)
    * len(CAPABILITY_SENSITIVE_FAMILIES)
    * len(DifficultyTier)
)
MATCHED_SELECTION_COUNT = len(WORKFLOW_RUNTIME_ARMS) * len(CAPABILITY_SENSITIVE_FAMILIES)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MatchedLocalizationThresholds(TierLocalizationThresholds):
    minimum_workflow_boundary_families: dict[CapabilityRuntimeArm, int] = Field(
        default_factory=lambda: {
            CapabilityRuntimeArm.SCRIPTED_TOOL: 3,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT: 3,
        }
    )

    @model_validator(mode="after")
    def validate_workflow_thresholds(self) -> MatchedLocalizationThresholds:
        if set(self.minimum_workflow_boundary_families) != set(WORKFLOW_RUNTIME_ARMS):
            raise ValueError("matched localization thresholds omit a workflow Runtime")
        return self


class MatchedHierarchicalAnalysisPlan(FrozenModel):
    formula: str = (
        "success ~ model * workflow_runtime * tier + family + "
        "(1|ladder_group) + (1|task_variant)"
    )
    tier_comparison_unit: Literal["within_ladder_group"] = "within_ladder_group"
    shared_tier_unit: Literal["runtime_x_family"] = "runtime_x_family"
    group_random_effect_required: Literal[True] = True
    model_pairing_required: Literal[True] = True
    task_variant_pairing_required: Literal[True] = True
    runtime_specific_tier_allowed: Literal[True] = True
    empirical_information_gate_required_before_calibration: Literal[True] = True
    unpaired_percentage_ranking_forbidden: Literal[True] = True
    direct_runtime_role: Literal["positive_execution_control"] = (
        "positive_execution_control"
    )
    direct_runtime_excluded_from_boundary_selection: Literal[True] = True
    workflow_runtime_arms: tuple[CapabilityRuntimeArm, ...] = WORKFLOW_RUNTIME_ARMS

    @model_validator(mode="after")
    def validate_analysis_plan(self) -> MatchedHierarchicalAnalysisPlan:
        if self.workflow_runtime_arms != WORKFLOW_RUNTIME_ARMS:
            raise ValueError("matched analysis includes an unauthorized Runtime")
        return self


class FinanceMatchedTierLocalizationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    regression_contract_path: str = Field(min_length=1)
    regression_contract_sha256: str = Field(min_length=64, max_length=64)
    regression_contract_id: str = Field(min_length=1)
    regression_report_path: str = Field(min_length=1)
    regression_report_sha256: str = Field(min_length=64, max_length=64)
    regression_report_id: str = Field(min_length=1)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(
        min_length=2,
        max_length=2,
    )
    paired_sampling_contract_hash: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    task_group_ids: dict[str, str] = Field(min_length=MATCHED_TASK_COUNT)
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=MATCHED_BINDING_COUNT,
        max_length=MATCHED_BINDING_COUNT,
    )
    replicas: int = Field(default=MATCHED_REPLICAS, ge=5, le=5)
    requested_rollouts: int = Field(
        default=MATCHED_ROLLOUT_COUNT,
        ge=MATCHED_ROLLOUT_COUNT,
        le=MATCHED_ROLLOUT_COUNT,
    )
    maximum_tool_calls: int = Field(default=MAXIMUM_TOOL_CALLS, ge=1)
    maximum_failed_tool_calls: int = Field(default=MAXIMUM_FAILED_TOOL_CALLS, ge=0)
    maximum_total_observation_bytes: int = Field(
        default=MAXIMUM_OBSERVATION_BYTES,
        ge=1,
    )
    maximum_model_tokens_per_rollout: int = Field(
        default=MODEL_TOKEN_BUDGET,
        ge=1,
    )
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    thresholds: MatchedLocalizationThresholds
    analysis_plan: MatchedHierarchicalAnalysisPlan
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    next_permitted_stage: Literal["matched_tier_localization"] = (
        "matched_tier_localization"
    )
    model_ranking_claim_authorized: Literal[False] = False
    paired_calibration_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = MATCHED_LOCALIZATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceMatchedTierLocalizationContract:
        if self.schema_version != MATCHED_LOCALIZATION_CONTRACT_VERSION:
            raise ValueError("matched localization contract version is unsupported")
        if self.maximum_tool_calls != (
            MAXIMUM_REQUIRED_TOOL_CALLS + self.maximum_failed_tool_calls
        ):
            raise ValueError("matched localization lacks failed-call recovery capacity")
        if {item.arm for item in self.model_contracts} != set(ExplorerArm):
            raise ValueError("matched localization requires Pro and Flash")
        if self.paired_sampling_contract_hash != _paired_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("matched localization models are not paired")
        _validate_bindings(self.bindings, self.task_group_ids)
        if self.requested_rollouts != (
            len(self.bindings) * len(self.model_contracts) * self.replicas
        ):
            raise ValueError("matched localization rollout denominator is inconsistent")
        if self.contract_id != matched_localization_contract_id(self):
            raise ValueError("matched localization contract identity is invalid")
        return self


class MatchedTierCell(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    tier: DifficultyTier
    attempted_count: int = Field(ge=1)
    technical_resolution_count: int = Field(ge=0)
    bounded_json_resolution_count: int = Field(ge=0)
    observation_replay_count: int = Field(ge=0)
    authority_integrity_count: int = Field(ge=0)
    semantic_success_count: int = Field(ge=0)
    valid_success_count: int = Field(ge=0)
    semantic_success_rate: float = Field(ge=0, le=1)
    semantic_success_interval: ConfidenceInterval
    group_success_rates: dict[str, float] = Field(min_length=MATCHED_GROUPS_PER_FAMILY)
    group_rate_variance: float = Field(ge=0)
    budget_exhaustion_count: int = Field(ge=0)
    runtime_infrastructure_failure_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_cell(self) -> MatchedTierCell:
        if self.attempted_count != MATCHED_GROUPS_PER_FAMILY * MATCHED_REPLICAS:
            raise ValueError("matched tier cell lacks its complete grouped denominator")
        if len(self.group_success_rates) != MATCHED_GROUPS_PER_FAMILY:
            raise ValueError("matched tier cell lacks a Ladder Group")
        expected_rate = self.semantic_success_count / self.attempted_count
        if not math.isclose(self.semantic_success_rate, expected_rate, abs_tol=1e-12):
            raise ValueError("matched tier success rate is inconsistent")
        if not math.isclose(
            self.group_rate_variance,
            pvariance(self.group_success_rates.values()),
            abs_tol=1e-12,
        ):
            raise ValueError("matched Ladder Group variance is inconsistent")
        return self


class MatchedTierSelection(FrozenModel):
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    selected_tier: DifficultyTier | None
    eligible_tiers: tuple[DifficultyTier, ...]
    informative_group_counts: dict[DifficultyTier, int]
    boundary_model_counts: dict[DifficultyTier, int]
    technical_passes: dict[DifficultyTier, bool]
    selected_tier_shared_by_models: bool
    boundary_identified: bool
    failure_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def validate_selection(self) -> MatchedTierSelection:
        if set(self.informative_group_counts) != set(DifficultyTier):
            raise ValueError("matched selection omits group diagnostics")
        if set(self.boundary_model_counts) != set(DifficultyTier):
            raise ValueError("matched selection omits model diagnostics")
        if set(self.technical_passes) != set(DifficultyTier):
            raise ValueError("matched selection omits technical diagnostics")
        if self.boundary_identified != (self.selected_tier is not None):
            raise ValueError("matched boundary decision is inconsistent")
        if self.selected_tier is not None and self.selected_tier not in self.eligible_tiers:
            raise ValueError("matched selected Tier is not eligible")
        if self.selected_tier_shared_by_models != (self.selected_tier is not None):
            raise ValueError("matched shared-Tier decision is inconsistent")
        return self


class FinanceMatchedTierLocalizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    cell_count: int = Field(ge=1)
    cells: tuple[MatchedTierCell, ...] = Field(
        min_length=MATCHED_CELL_COUNT,
        max_length=MATCHED_CELL_COUNT,
    )
    thresholds: MatchedLocalizationThresholds
    selections: tuple[MatchedTierSelection, ...] = Field(
        min_length=MATCHED_SELECTION_COUNT,
        max_length=MATCHED_SELECTION_COUNT,
    )
    outcome_set_hash: str = Field(min_length=1)
    technical_resolution_rate: float = Field(ge=0, le=1)
    group_monotonic_ladder_count: int = Field(ge=0)
    group_ladder_count: int = Field(ge=1)
    group_monotonic_fraction: float = Field(ge=0, le=1)
    selected_family_counts_by_workflow_runtime: dict[CapabilityRuntimeArm, int]
    workflow_runtime_localization_ready: dict[CapabilityRuntimeArm, bool]
    all_workflow_runtime_localization_ready: bool
    bridge_tier_indicated_for_autonomous: bool
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    technical_status: Literal["passed", "failed"]
    next_permitted_stage: Literal[
        "empirical_capability_information_audit",
        "bridge_or_task_redesign_only",
        "runtime_contract_repair_only",
    ]
    matched_group_random_effect_included: Literal[True] = True
    direct_runtime_excluded_from_boundary_selection: Literal[True] = True
    direct_runtime_role: Literal["positive_execution_control"] = (
        "positive_execution_control"
    )
    semantic_results_are_development_only: Literal[True] = True
    pro_flash_ranking_authorized: Literal[False] = False
    paired_calibration_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = MATCHED_LOCALIZATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceMatchedTierLocalizationReport:
        if self.schema_version != MATCHED_LOCALIZATION_REPORT_VERSION:
            raise ValueError("matched localization report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("matched localization lacks its complete denominator")
        if self.cell_count != MATCHED_CELL_COUNT or len(self.cells) != self.cell_count:
            raise ValueError("matched localization cells are incomplete")
        if sum(item.attempted_count for item in self.cells) != self.recorded_rollout_count:
            raise ValueError("matched localization cells do not cover every rollout")
        expected_cells = {
            (model, runtime, family, tier)
            for model in ExplorerArm
            for runtime in WORKFLOW_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
            for tier in DifficultyTier
        }
        if {
            (item.model_arm, item.runtime_arm, item.family, item.tier)
            for item in self.cells
        } != expected_cells:
            raise ValueError("matched localization lacks a Model x Runtime x Family x Tier cell")
        expected_selections = {
            (runtime, family)
            for runtime in WORKFLOW_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if {
            (item.runtime_arm, item.family) for item in self.selections
        } != expected_selections:
            raise ValueError("matched localization selections are incomplete")
        cell_index = {
            (item.model_arm, item.runtime_arm, item.family, item.tier): item
            for item in self.cells
        }
        replayed_selections = tuple(
            _select_shared_tier(runtime, family, cell_index, self.thresholds)
            for runtime in WORKFLOW_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
        )
        if self.selections != replayed_selections:
            raise ValueError("matched localization selections were not replayed")
        if not math.isclose(
            self.group_monotonic_fraction,
            self.group_monotonic_ladder_count / self.group_ladder_count,
            abs_tol=1e-12,
        ):
            raise ValueError("matched group monotonic fraction is inconsistent")
        if self.selected_family_counts_by_workflow_runtime != {
            runtime: sum(
                item.boundary_identified
                for item in self.selections
                if item.runtime_arm == runtime
            )
            for runtime in WORKFLOW_RUNTIME_ARMS
        }:
            raise ValueError("matched selected-family counts are inconsistent")
        if self.all_workflow_runtime_localization_ready != all(
            self.workflow_runtime_localization_ready.values()
        ):
            raise ValueError("matched workflow localization decision is inconsistent")
        expected_runtime_ready = {
            runtime: (
                self.selected_family_counts_by_workflow_runtime[runtime]
                >= self.thresholds.minimum_workflow_boundary_families[runtime]
                and self.group_monotonic_fraction
                >= self.thresholds.minimum_group_monotonic_fraction
            )
            for runtime in WORKFLOW_RUNTIME_ARMS
        }
        if self.workflow_runtime_localization_ready != expected_runtime_ready:
            raise ValueError("matched workflow Runtime decisions are inconsistent")
        technical_passed = (
            self.technical_resolution_rate
            >= self.thresholds.minimum_technical_resolution_rate
            and all(
                item.bounded_json_resolution_count == item.attempted_count
                and item.observation_replay_count == item.attempted_count
                and item.authority_integrity_count == item.attempted_count
                for item in self.cells
            )
            and all(item.budget_exhaustion_count == 0 for item in self.cells)
            and all(
                item.runtime_infrastructure_failure_count == 0 for item in self.cells
            )
        )
        if (self.technical_status == "passed") != technical_passed:
            raise ValueError("matched localization technical status is inconsistent")
        autonomous_easy = [
            cell_index[
                (
                    model,
                    CapabilityRuntimeArm.AUTONOMOUS_AGENT,
                    family,
                    DifficultyTier.EASY_CONTROL,
                )
            ].semantic_success_rate
            for model in ExplorerArm
            for family in CAPABILITY_SENSITIVE_FAMILIES
        ]
        expected_bridge = (
            technical_passed
            and not expected_runtime_ready[CapabilityRuntimeArm.AUTONOMOUS_AGENT]
            and fmean(autonomous_easy) <= 0.20
        )
        if self.bridge_tier_indicated_for_autonomous != expected_bridge:
            raise ValueError("matched Autonomous bridge decision is inconsistent")
        expected_next = (
            "runtime_contract_repair_only"
            if not technical_passed
            else (
                "empirical_capability_information_audit"
                if self.all_workflow_runtime_localization_ready
                else "bridge_or_task_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("matched localization transition is not fail-closed")
        if self.report_id != matched_localization_report_id(self):
            raise ValueError("matched localization report identity is invalid")
        return self


def prepare_matched_tier_localization_contract(
    *,
    population_path: Path,
    regression_contract_path: Path,
    regression_report_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
) -> FinanceMatchedTierLocalizationContract:
    if output_path.exists():
        raise ValueError("matched localization contract is immutable and exists")
    population_path = population_path.resolve()
    regression_contract_path = regression_contract_path.resolve()
    regression_report_path = regression_report_path.resolve()
    population = MatchedCapabilityLadderPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    regression = FinancePublicContractRegressionContract.model_validate_json(
        regression_contract_path.read_text(encoding="utf-8")
    )
    regression_report = FinancePublicContractRegressionReport.model_validate_json(
        regression_report_path.read_text(encoding="utf-8")
    )
    if not population.audit.matched_ladder_ready:
        raise ValueError("matched localization requires a ready matched ladder")
    if (
        population.regression_contract_id != regression.contract_id
        or population.regression_report_id != regression_report.report_id
        or regression_report.status != "passed"
    ):
        raise ValueError("matched localization regression lineage is invalid")
    tasks = population.tasks
    task_group_ids = {
        task.artifact_id: group.group_id
        for group in population.groups
        for task in group.variants
    }
    bindings = tuple(
        _make_runtime_binding(task, runtime, population.protocol_profile)
        for task in tasks
        for runtime in WORKFLOW_RUNTIME_ARMS
    )
    values = {
        "run_id": run_id,
        "population_path": str(population_path),
        "population_sha256": _sha256(population_path),
        "population_id": population.population_id,
        "regression_contract_path": str(regression_contract_path),
        "regression_contract_sha256": _sha256(regression_contract_path),
        "regression_contract_id": regression.contract_id,
        "regression_report_path": str(regression_report_path),
        "regression_report_sha256": _sha256(regression_report_path),
        "regression_report_id": regression_report.report_id,
        "finance_archive_config_path": regression.finance_archive_config_path,
        "finance_archive_config_sha256": regression.finance_archive_config_sha256,
        "model_contracts": regression.model_contracts,
        "paired_sampling_contract_hash": regression.paired_sampling_contract_hash,
        "protocol_profile": population.protocol_profile,
        "task_group_ids": task_group_ids,
        "bindings": bindings,
        "replicas": MATCHED_REPLICAS,
        "requested_rollouts": MATCHED_ROLLOUT_COUNT,
        "maximum_tool_calls": MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_total_observation_bytes": MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": 2,
        "thresholds": MatchedLocalizationThresholds(),
        "analysis_plan": MatchedHierarchicalAnalysisPlan(),
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "next_permitted_stage": "matched_tier_localization",
        "model_ranking_claim_authorized": False,
        "paired_calibration_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinanceMatchedTierLocalizationContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceMatchedTierLocalizationContract(
        contract_id=matched_localization_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_matched_tier_localization(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceMatchedTierLocalizationReport:
    if workers < 1:
        raise ValueError("matched localization workers must be positive")
    contract = FinanceMatchedTierLocalizationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    population = MatchedCapabilityLadderPopulation.model_validate_json(
        Path(contract.population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.population_id:
        raise ValueError("matched localization loaded another population")
    tasks = {item.artifact_id: item for item in population.tasks}
    if set(contract.task_group_ids) != set(tasks):
        raise ValueError("matched localization task manifest differs from its population")
    run_identity = matched_localization_run_identity(contract)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "matched_tier_localization.checkpoint.jsonl"
    records_path = output_dir / "matched_tier_localization_records.jsonl"
    outcomes_path = output_dir / "matched_tier_localization_outcomes.jsonl"
    report_path = output_dir / "finance_matched_tier_localization_report.json"
    manifest_path = output_dir / "matched_tier_localization_run_manifest.json"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        contract=contract,
    )
    records = {_record_key(item): item for item in historical}
    jobs = tuple(
        (model, binding, replicate)
        for binding in sorted(contract.bindings, key=lambda item: item.binding_id)
        for replicate in range(contract.replicas)
        for model in ExplorerArm
    )
    pending = tuple(
        job for job in jobs if (job[0], job[1].binding_id, job[2]) not in records
    )
    print(
        f"[v25.11:workflow-matched] resuming {len(records)}/{len(jobs)}; "
        f"executing {len(pending)} with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    if pending:
        clients = {
            item.arm: OpenAICompatibleJsonClient(
                item.config.model_copy(
                    update={
                        "contract_repair_attempts": contract.model_contract_repair_attempts
                    }
                )
            )
            for item in contract.model_contracts
        }
        discovered = {arm: client.discover_models() for arm, client in clients.items()}
        discovery_source = "live_provider"
    else:
        clients = {}
        discovered = _load_discovered_models(manifest_path, run_identity)
        discovery_source = "checkpoint_contract_replay"
    for arm in ExplorerArm:
        if EXPECTED_MODELS[arm.value] not in discovered.get(arm, ()):
            raise ValueError(f"provider evidence lacks frozen {arm.value} model")
    if pending:
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _run_one,
                    contract,
                    BoundaryStage.TIER_LOCALIZATION,
                    model,
                    binding,
                    tasks[binding.task_artifact_id],
                    replicate,
                    run_identity,
                    clients[model],
                ): (model, binding.binding_id, replicate)
                for model, binding, replicate in pending
            }
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                record = future.result()
                if key != _record_key(record):
                    raise ValueError("matched localization worker returned another job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                records[key] = record
                if index % 25 == 0 or index == len(futures):
                    print(
                        f"[v25.11:workflow-matched] completed {len(records)}/{len(jobs)}",
                        flush=True,
                    )
    ordered = tuple(
        records[(model, binding.binding_id, replicate)]
        for model, binding, replicate in jobs
    )
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    outcomes = tuple(_to_outcome(item, contract.bindings) for item in ordered)
    _write_jsonl_atomic(
        outcomes_path,
        (item.model_dump(mode="json") for item in outcomes),
    )
    report = make_matched_localization_report(contract, outcomes)
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        manifest_path,
        {
            "run_identity": run_identity,
            "runner_version": MATCHED_LOCALIZATION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "contract_id": contract.contract_id,
            "population_id": contract.population_id,
            "discovered_models": {
                arm.value: tuple(values) for arm, values in discovered.items()
            },
            "model_discovery_source": discovery_source,
            "checkpoint_sha256": _sha256(checkpoint_path),
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(outcomes_path),
            "outcome_set_hash": report.outcome_set_hash,
            "report_id": report.report_id,
            "report_sha256": _sha256(report_path),
        },
    )
    return report


def make_matched_localization_report(
    contract: FinanceMatchedTierLocalizationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceMatchedTierLocalizationReport:
    _validate_outcomes(contract, outcomes)
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    grouped: dict[
        tuple[ExplorerArm, CapabilityRuntimeArm, str, DifficultyTier],
        list[CapabilityRolloutOutcome],
    ] = defaultdict(list)
    for item in outcomes:
        binding = binding_by_id[item.binding_id]
        grouped[
            (item.model_arm, item.runtime_arm, item.family, binding.tier)
        ].append(item)
    cells = []
    for model in ExplorerArm:
        for runtime in WORKFLOW_RUNTIME_ARMS:
            for family in CAPABILITY_SENSITIVE_FAMILIES:
                for tier in DifficultyTier:
                    values = grouped[(model, runtime, family, tier)]
                    by_group: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
                    for item in values:
                        by_group[contract.task_group_ids[item.task_artifact_id]].append(item)
                    group_rates = {
                        group_id: sum(item.semantic_answer_correct for item in group_values)
                        / len(group_values)
                        for group_id, group_values in sorted(by_group.items())
                    }
                    success_count = sum(item.semantic_answer_correct for item in values)
                    cells.append(
                        MatchedTierCell(
                            model_arm=model,
                            runtime_arm=runtime,
                            family=family,
                            tier=tier,
                            attempted_count=len(values),
                            technical_resolution_count=sum(item.completed for item in values),
                            bounded_json_resolution_count=sum(
                                item.bounded_json_resolution_success for item in values
                            ),
                            observation_replay_count=sum(
                                item.observation_replay_success for item in values
                            ),
                            authority_integrity_count=sum(
                                item.authority_integrity_success for item in values
                            ),
                            semantic_success_count=success_count,
                            valid_success_count=sum(item.valid_success for item in values),
                            semantic_success_rate=success_count / len(values),
                            semantic_success_interval=_wilson_interval(
                                success_count,
                                len(values),
                            ),
                            group_success_rates=group_rates,
                            group_rate_variance=pvariance(group_rates.values()),
                            budget_exhaustion_count=sum(
                                item.budget_exhausted for item in values
                            ),
                            runtime_infrastructure_failure_count=sum(
                                item.runtime_infrastructure_failure_count for item in values
                            ),
                            api_call_count=sum(item.api_call_count for item in values),
                            total_model_tokens=sum(item.total_model_tokens for item in values),
                            estimated_cost_usd=sum(
                                item.estimated_cost_usd for item in values
                            ),
                        )
                    )
    cell_index = {
        (item.model_arm, item.runtime_arm, item.family, item.tier): item
        for item in cells
    }
    selections = tuple(
        _select_shared_tier(
            runtime,
            family,
            cell_index,
            contract.thresholds,
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
        for family in CAPABILITY_SENSITIVE_FAMILIES
    )
    monotonic_count, ladder_count = _group_monotonic_count(
        outcomes,
        binding_by_id=binding_by_id,
        task_group_ids=contract.task_group_ids,
    )
    selected_counts = {
        runtime: sum(
            item.boundary_identified
            for item in selections
            if item.runtime_arm == runtime
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    }
    runtime_ready = {
        runtime: (
            selected_counts[runtime]
            >= contract.thresholds.minimum_workflow_boundary_families[runtime]
            and monotonic_count / ladder_count
            >= contract.thresholds.minimum_group_monotonic_fraction
        )
        for runtime in WORKFLOW_RUNTIME_ARMS
    }
    technical_rate = sum(item.completed for item in outcomes) / len(outcomes)
    technical_passed = (
        technical_rate >= contract.thresholds.minimum_technical_resolution_rate
        and all(item.bounded_json_resolution_success for item in outcomes)
        and all(item.observation_replay_success for item in outcomes)
        and all(item.authority_integrity_success for item in outcomes)
        and not any(item.budget_exhausted for item in outcomes)
        and not any(item.runtime_infrastructure_failure_count for item in outcomes)
    )
    all_ready = all(runtime_ready.values())
    autonomous_easy = [
        cell_index[
            (
                model,
                CapabilityRuntimeArm.AUTONOMOUS_AGENT,
                family,
                DifficultyTier.EASY_CONTROL,
            )
        ].semantic_success_rate
        for model in ExplorerArm
        for family in CAPABILITY_SENSITIVE_FAMILIES
    ]
    bridge_indicated = (
        technical_passed
        and not runtime_ready[CapabilityRuntimeArm.AUTONOMOUS_AGENT]
        and fmean(autonomous_easy) <= 0.20
    )
    report_values = {
        "contract_id": contract.contract_id,
        "population_id": contract.population_id,
        "requested_rollout_count": contract.requested_rollouts,
        "recorded_rollout_count": len(outcomes),
        "cell_count": len(cells),
        "cells": tuple(cells),
        "thresholds": contract.thresholds,
        "selections": selections,
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.outcome_id for item in outcomes)),
            prefix="finance_matched_localization_outcomes:",
        ),
        "technical_resolution_rate": technical_rate,
        "group_monotonic_ladder_count": monotonic_count,
        "group_ladder_count": ladder_count,
        "group_monotonic_fraction": monotonic_count / ladder_count,
        "selected_family_counts_by_workflow_runtime": selected_counts,
        "workflow_runtime_localization_ready": runtime_ready,
        "all_workflow_runtime_localization_ready": all_ready,
        "bridge_tier_indicated_for_autonomous": bridge_indicated,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "technical_status": "passed" if technical_passed else "failed",
        "next_permitted_stage": (
            "runtime_contract_repair_only"
            if not technical_passed
            else (
                "empirical_capability_information_audit"
                if all_ready
                else "bridge_or_task_redesign_only"
            )
        ),
        "matched_group_random_effect_included": True,
        "direct_runtime_excluded_from_boundary_selection": True,
        "direct_runtime_role": "positive_execution_control",
        "semantic_results_are_development_only": True,
        "pro_flash_ranking_authorized": False,
        "paired_calibration_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinanceMatchedTierLocalizationReport.model_construct(
        report_id="pending",
        **report_values,
    )
    return FinanceMatchedTierLocalizationReport(
        report_id=matched_localization_report_id(provisional),
        **report_values,
    )


def _select_shared_tier(
    runtime: CapabilityRuntimeArm,
    family: str,
    cells: Mapping[
        tuple[ExplorerArm, CapabilityRuntimeArm, str, DifficultyTier],
        MatchedTierCell,
    ],
    thresholds: MatchedLocalizationThresholds,
) -> MatchedTierSelection:
    informative_groups = {}
    boundary_models = {}
    technical = {}
    eligible = []
    tier_scores = {}
    for tier in DifficultyTier:
        model_cells = [cells[(model, runtime, family, tier)] for model in ExplorerArm]
        technical[tier] = all(
            item.technical_resolution_count / item.attempted_count
            >= thresholds.minimum_technical_resolution_rate
            and item.budget_exhaustion_count == 0
            and item.runtime_infrastructure_failure_count == 0
            for item in model_cells
        )
        boundary_models[tier] = sum(
            thresholds.boundary_probability_lower
            <= item.semantic_success_rate
            <= thresholds.boundary_probability_upper
            for item in model_cells
        )
        group_ids = set(model_cells[0].group_success_rates)
        informative_groups[tier] = sum(
            any(
                thresholds.boundary_probability_lower
                <= item.group_success_rates[group_id]
                <= thresholds.boundary_probability_upper
                for item in model_cells
            )
            for group_id in group_ids
        )
        if (
            technical[tier]
            and boundary_models[tier] >= 1
            and informative_groups[tier] >= thresholds.minimum_informative_group_count
        ):
            eligible.append(tier)
            rates = [item.semantic_success_rate for item in model_cells]
            tier_scores[tier] = (
                boundary_models[tier],
                informative_groups[tier],
                abs(rates[0] - rates[1]),
                -abs(fmean(rates) - 0.5),
                {
                    DifficultyTier.FRONTIER: 2,
                    DifficultyTier.EASY_CONTROL: 1,
                    DifficultyTier.HARD_CONTROL: 0,
                }[tier],
            )
    selected = max(eligible, key=tier_scores.__getitem__) if eligible else None
    reasons = []
    if not any(technical.values()):
        reasons.append("no_technically_resolved_tier")
    if not any(boundary_models.values()):
        reasons.append("all_tiers_response_saturated_or_floor")
    if max(informative_groups.values(), default=0) < thresholds.minimum_informative_group_count:
        reasons.append("insufficient_ladder_group_support")
    if selected is None and not reasons:
        reasons.append("no_jointly_eligible_shared_tier")
    return MatchedTierSelection(
        runtime_arm=runtime,
        family=family,
        selected_tier=selected,
        eligible_tiers=tuple(eligible),
        informative_group_counts=informative_groups,
        boundary_model_counts=boundary_models,
        technical_passes=technical,
        selected_tier_shared_by_models=selected is not None,
        boundary_identified=selected is not None,
        failure_reasons=tuple(reasons),
    )


def _group_monotonic_count(
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    *,
    binding_by_id: Mapping[str, RuntimeTaskBinding],
    task_group_ids: Mapping[str, str],
) -> tuple[int, int]:
    values: dict[
        tuple[ExplorerArm, CapabilityRuntimeArm, str, str, DifficultyTier],
        list[bool],
    ] = defaultdict(list)
    for item in outcomes:
        binding = binding_by_id[item.binding_id]
        values[
            (
                item.model_arm,
                item.runtime_arm,
                item.family,
                task_group_ids[item.task_artifact_id],
                binding.tier,
            )
        ].append(item.semantic_answer_correct)
    ladders: dict[
        tuple[ExplorerArm, CapabilityRuntimeArm, str, str],
        dict[DifficultyTier, float],
    ] = defaultdict(dict)
    for (model, runtime, family, group, tier), successes in values.items():
        ladders[(model, runtime, family, group)][tier] = sum(successes) / len(successes)
    monotonic = sum(
        rates[DifficultyTier.EASY_CONTROL]
        >= rates[DifficultyTier.FRONTIER]
        >= rates[DifficultyTier.HARD_CONTROL]
        for rates in ladders.values()
    )
    return monotonic, len(ladders)


def _validate_bindings(
    bindings: tuple[RuntimeTaskBinding, ...],
    task_group_ids: Mapping[str, str],
) -> None:
    if len(bindings) != MATCHED_BINDING_COUNT:
        raise ValueError("matched localization binding count is incomplete")
    task_ids = {item.task_artifact_id for item in bindings}
    if set(task_group_ids) != task_ids or len(task_ids) != MATCHED_TASK_COUNT:
        raise ValueError("matched localization task/group manifest is inconsistent")
    by_task: dict[str, list[RuntimeTaskBinding]] = defaultdict(list)
    for item in bindings:
        by_task[item.task_artifact_id].append(item)
    if any(
        len(values) != len(WORKFLOW_RUNTIME_ARMS)
        or {item.runtime_arm for item in values} != set(WORKFLOW_RUNTIME_ARMS)
        for values in by_task.values()
    ):
        raise ValueError("a matched task lacks exactly one binding per Runtime")
    group_counts = Counter(task_group_ids.values())
    if len(group_counts) != MATCHED_GROUP_COUNT or set(group_counts.values()) != {3}:
        raise ValueError("matched localization groups lack exactly three Tiers")
    family_tier_counts = Counter(
        (task_bindings[0].family, task_bindings[0].tier)
        for task_bindings in by_task.values()
    )
    if family_tier_counts != Counter(
        {
            (family, tier): MATCHED_GROUPS_PER_FAMILY
            for family in CAPABILITY_SENSITIVE_FAMILIES
            for tier in DifficultyTier
        }
    ):
        raise ValueError("matched localization is not balanced by family and Tier")


def _validate_outcomes(
    contract: FinanceMatchedTierLocalizationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> None:
    if len(outcomes) != contract.requested_rollouts:
        raise ValueError("matched localization outcomes have an incomplete denominator")
    binding_ids = {item.binding_id for item in contract.bindings}
    keys = set()
    for item in outcomes:
        key = (item.model_arm, item.binding_id, item.replicate)
        if key in keys:
            raise ValueError("matched localization duplicates a rollout")
        keys.add(key)
        if (
            item.contract_id != contract.contract_id
            or item.stage != BoundaryStage.TIER_LOCALIZATION
            or item.binding_id not in binding_ids
            or not 0 <= item.replicate < contract.replicas
        ):
            raise ValueError("matched localization contains an unknown rollout")


def _wilson_interval(successes: int, total: int) -> ConfidenceInterval:
    z = 1.959963984540054
    point = successes / total
    denominator = 1 + z * z / total
    center = (point + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(point * (1 - point) / total + z * z / (4 * total * total))
        / denominator
    )
    return ConfidenceInterval(
        lower=max(0.0, center - radius),
        point=point,
        upper=min(1.0, center + radius),
    )


def _verify_frozen_inputs(contract: FinanceMatchedTierLocalizationContract) -> None:
    for path, expected in (
        (Path(contract.population_path), contract.population_sha256),
        (Path(contract.regression_contract_path), contract.regression_contract_sha256),
        (Path(contract.regression_report_path), contract.regression_report_sha256),
        (
            Path(contract.finance_archive_config_path),
            contract.finance_archive_config_sha256,
        ),
    ):
        if _sha256(path) != expected:
            raise ValueError(f"frozen matched-localization input changed:{path}")


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    contract: FinanceMatchedTierLocalizationContract,
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    if not path.is_file():
        return ()
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    binding_ids = {item.binding_id for item in contract.bindings}
    keys = set()
    for record in records:
        key = _record_key(record)
        if key in keys:
            raise ValueError("matched checkpoint duplicates a rollout")
        keys.add(key)
        if (
            record.run_identity != run_identity
            or record.contract_id != contract.contract_id
            or record.binding_id not in binding_ids
            or not 0 <= record.replicate < contract.replicas
        ):
            raise ValueError("matched checkpoint contains an unknown rollout")
    return records


def _load_discovered_models(
    path: Path,
    run_identity: str,
) -> dict[ExplorerArm, tuple[str, ...]]:
    if not path.is_file():
        raise ValueError("completed matched run lacks a model-discovery manifest")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("run_identity") != run_identity:
        raise ValueError("matched model-discovery manifest belongs to another run")
    discovered = raw.get("discovered_models")
    if not isinstance(discovered, dict):
        raise ValueError("matched run manifest lacks model discovery evidence")
    return {
        arm: tuple(str(item) for item in discovered.get(arm.value, ()))
        for arm in ExplorerArm
    }


def _record_key(
    record: CapabilityBoundaryRolloutRecord,
) -> tuple[ExplorerArm, str, int]:
    return record.model_arm, record.binding_id, record.replicate


def matched_localization_run_identity(
    contract: FinanceMatchedTierLocalizationContract,
) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "runner_version": MATCHED_LOCALIZATION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "binding_ids": tuple(sorted(item.binding_id for item in contract.bindings)),
            "replicas": contract.replicas,
        },
        prefix="finance_matched_tier_localization_run:",
    )


def matched_localization_contract_id(
    value: FinanceMatchedTierLocalizationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_matched_tier_localization_contract:",
    )


def matched_localization_report_id(
    value: FinanceMatchedTierLocalizationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_matched_tier_localization_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or run matched Pro/Flash tier localization"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--population", type=Path, required=True)
    prepare.add_argument("--regression-contract", type=Path, required=True)
    prepare.add_argument("--regression-report", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=20260812)
    prepare.add_argument("--sampling-salt", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=24)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        contract = prepare_matched_tier_localization_contract(
            population_path=args.population,
            regression_contract_path=args.regression_contract,
            regression_report_path=args.regression_report,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
            sampling_salt=args.sampling_salt,
        )
        result = {
            "contract_id": contract.contract_id,
            "bindings": len(contract.bindings),
            "requested_rollouts": contract.requested_rollouts,
            "next_permitted_stage": contract.next_permitted_stage,
            "output": str(args.output.resolve()),
        }
    else:
        report = run_matched_tier_localization(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        result = {
            "report_id": report.report_id,
            "recorded_rollouts": report.recorded_rollout_count,
            "technical_status": report.technical_status,
            "selected_family_counts_by_workflow_runtime": {
                key.value: value
                for key, value in report.selected_family_counts_by_workflow_runtime.items()
            },
            "group_monotonic_fraction": report.group_monotonic_fraction,
            "bridge_tier_indicated_for_autonomous": (
                report.bridge_tier_indicated_for_autonomous
            ),
            "next_permitted_stage": report.next_permitted_stage,
            "api_calls": report.api_call_count,
            "total_model_tokens": report.total_model_tokens,
            "estimated_cost_usd": report.estimated_cost_usd,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
