from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import pvariance
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_tier_localization import (
    MatchedTierCell,
    _group_monotonic_count,
    _wilson_interval,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_structural_capability_ladder import (
    STRUCTURAL_FAMILIES,
    STRUCTURAL_GROUP_COUNT,
    STRUCTURAL_GROUPS_PER_FAMILY,
    STRUCTURAL_TASK_COUNT,
    StructuralCapabilityLadderPopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_tier_localization_common import (
    TierLocalizationThresholds,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

STRUCTURAL_LOCALIZATION_CONTRACT_VERSION = (
    "finance_structural_tier_localization_contract.v2"
)
STRUCTURAL_LOCALIZATION_REPORT_VERSION = (
    "finance_structural_tier_localization_report.v2"
)
STRUCTURAL_LOCALIZATION_RUNNER_VERSION = (
    "finance_structural_tier_localization_runner.v2"
)

STRUCTURAL_REPLICAS = 5
STRUCTURAL_BINDING_COUNT = STRUCTURAL_TASK_COUNT
STRUCTURAL_ROLLOUT_COUNT = (
    STRUCTURAL_BINDING_COUNT * len(ExplorerArm) * STRUCTURAL_REPLICAS
)
STRUCTURAL_CELL_COUNT = (
    len(ExplorerArm) * len(STRUCTURAL_FAMILIES) * len(DifficultyTier)
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StructuralControlThresholds(TierLocalizationThresholds):
    minimum_technical_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_direct_control_semantic_rate: float = Field(default=0.95, ge=0, le=1)


class StructuralHierarchicalAnalysisPlan(FrozenModel):
    formula: str = (
        "execution_success ~ model * structural_tier + family + "
        "(1|ladder_group) + (1|task_variant)"
    )
    runtime_arm: Literal["direct_fixed_retrieval"] = "direct_fixed_retrieval"
    tier_comparison_unit: Literal["within_ladder_group"] = "within_ladder_group"
    shared_tier_unit: Literal["family"] = "family"
    group_random_effect_required: Literal[True] = True
    model_pairing_required: Literal[True] = True
    task_variant_pairing_required: Literal[True] = True
    structural_complexity_is_intervention: Literal[True] = True
    retrieval_planning_recovery_stopping_fixed: Literal[True] = True
    empirical_information_gate_required_before_calibration: Literal[True] = True
    unpaired_percentage_ranking_forbidden: Literal[True] = True
    direct_runtime_role: Literal["positive_execution_control"] = (
        "positive_execution_control"
    )
    capability_boundary_selection_forbidden: Literal[True] = True


class FinanceStructuralTierLocalizationContract(FrozenModel):
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
    task_group_ids: dict[str, str] = Field(min_length=STRUCTURAL_TASK_COUNT)
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=STRUCTURAL_BINDING_COUNT,
        max_length=STRUCTURAL_BINDING_COUNT,
    )
    replicas: int = Field(default=STRUCTURAL_REPLICAS, ge=5, le=5)
    requested_rollouts: int = Field(
        default=STRUCTURAL_ROLLOUT_COUNT,
        ge=STRUCTURAL_ROLLOUT_COUNT,
        le=STRUCTURAL_ROLLOUT_COUNT,
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
    thresholds: StructuralControlThresholds
    analysis_plan: StructuralHierarchicalAnalysisPlan
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    next_permitted_stage: Literal["direct_structural_tier_localization"] = (
        "direct_structural_tier_localization"
    )
    model_ranking_claim_authorized: Literal[False] = False
    paired_calibration_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = STRUCTURAL_LOCALIZATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStructuralTierLocalizationContract:
        if self.schema_version != STRUCTURAL_LOCALIZATION_CONTRACT_VERSION:
            raise ValueError("structural localization contract version is unsupported")
        if self.maximum_tool_calls != (
            MAXIMUM_REQUIRED_TOOL_CALLS + self.maximum_failed_tool_calls
        ):
            raise ValueError("structural localization lacks failed-call recovery capacity")
        if {item.arm for item in self.model_contracts} != set(ExplorerArm):
            raise ValueError("structural localization requires Pro and Flash")
        if self.paired_sampling_contract_hash != _paired_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("structural localization models are not paired")
        _validate_structural_bindings(self.bindings, self.task_group_ids)
        if self.requested_rollouts != (
            len(self.bindings) * len(self.model_contracts) * self.replicas
        ):
            raise ValueError("structural localization rollout denominator is inconsistent")
        if self.contract_id != structural_localization_contract_id(self):
            raise ValueError("structural localization contract identity is invalid")
        return self


class FinanceStructuralTierLocalizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    cell_count: int = Field(ge=1)
    cells: tuple[MatchedTierCell, ...] = Field(
        min_length=STRUCTURAL_CELL_COUNT,
        max_length=STRUCTURAL_CELL_COUNT,
    )
    thresholds: StructuralControlThresholds
    outcome_set_hash: str = Field(min_length=1)
    technical_resolution_rate: float = Field(ge=0, le=1)
    group_monotonic_ladder_count: int = Field(ge=0)
    group_ladder_count: int = Field(ge=1)
    group_monotonic_fraction: float = Field(ge=0, le=1)
    semantic_success_rate: float = Field(ge=0, le=1)
    direct_positive_control_ready: bool
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    technical_status: Literal["passed", "failed"]
    next_permitted_stage: Literal[
        "workflow_ladder_localization",
        "runtime_contract_repair_only",
    ]
    direct_runtime_only: Literal[True] = True
    direct_runtime_role: Literal["positive_execution_control"] = (
        "positive_execution_control"
    )
    direct_runtime_excluded_from_boundary_selection: Literal[True] = True
    workflow_confound_excluded: Literal[True] = True
    distractor_confound_excluded: Literal[True] = True
    matched_group_random_effect_included: Literal[True] = True
    semantic_results_are_development_only: Literal[True] = True
    pro_flash_ranking_authorized: Literal[False] = False
    paired_calibration_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = STRUCTURAL_LOCALIZATION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStructuralTierLocalizationReport:
        if self.schema_version != STRUCTURAL_LOCALIZATION_REPORT_VERSION:
            raise ValueError("structural localization report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("structural localization lacks its complete denominator")
        if self.cell_count != STRUCTURAL_CELL_COUNT or len(self.cells) != self.cell_count:
            raise ValueError("structural localization cells are incomplete")
        if sum(item.attempted_count for item in self.cells) != self.recorded_rollout_count:
            raise ValueError("structural localization cells do not cover every rollout")
        expected_cells = {
            (
                model,
                CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
                family,
                tier,
            )
            for model in ExplorerArm
            for family in STRUCTURAL_FAMILIES
            for tier in DifficultyTier
        }
        if {
            (item.model_arm, item.runtime_arm, item.family, item.tier)
            for item in self.cells
        } != expected_cells:
            raise ValueError("structural localization lacks a Model x Family x Tier cell")
        if not math.isclose(
            self.group_monotonic_fraction,
            self.group_monotonic_ladder_count / self.group_ladder_count,
            abs_tol=1e-12,
        ):
            raise ValueError("structural group monotonic fraction is inconsistent")
        expected_semantic_rate = sum(
            item.semantic_success_count for item in self.cells
        ) / self.recorded_rollout_count
        if not math.isclose(
            self.semantic_success_rate,
            expected_semantic_rate,
            abs_tol=1e-12,
        ):
            raise ValueError("Direct control semantic rate is inconsistent")
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
            and all(item.runtime_infrastructure_failure_count == 0 for item in self.cells)
        )
        if (self.technical_status == "passed") != technical_passed:
            raise ValueError("structural localization technical status is inconsistent")
        expected_ready = (
            technical_passed
            and self.semantic_success_rate
            >= self.thresholds.minimum_direct_control_semantic_rate
        )
        if self.direct_positive_control_ready != expected_ready:
            raise ValueError("Direct positive-control readiness is inconsistent")
        expected_next = (
            "workflow_ladder_localization"
            if expected_ready
            else "runtime_contract_repair_only"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("structural localization transition is not fail-closed")
        if self.report_id != structural_localization_report_id(self):
            raise ValueError("structural localization report identity is invalid")
        return self


def prepare_structural_tier_localization_contract(
    *,
    population_path: Path,
    regression_contract_path: Path,
    regression_report_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
) -> FinanceStructuralTierLocalizationContract:
    if output_path.exists():
        raise ValueError("structural localization contract is immutable and exists")
    population_path = population_path.resolve()
    regression_contract_path = regression_contract_path.resolve()
    regression_report_path = regression_report_path.resolve()
    population = StructuralCapabilityLadderPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    regression = FinancePublicContractRegressionContract.model_validate_json(
        regression_contract_path.read_text(encoding="utf-8")
    )
    regression_report = FinancePublicContractRegressionReport.model_validate_json(
        regression_report_path.read_text(encoding="utf-8")
    )
    if not population.audit.structural_ladder_ready:
        raise ValueError("structural localization requires a ready structural ladder")
    if (
        population.regression_contract_id != regression.contract_id
        or population.regression_report_id != regression_report.report_id
        or regression_report.status != "passed"
    ):
        raise ValueError("structural localization regression lineage is invalid")
    task_group_ids = {
        task.artifact_id: group.group_id
        for group in population.groups
        for task in group.variants
    }
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL,
            population.protocol_profile,
        )
        for task in population.tasks
    )
    thresholds = StructuralControlThresholds()
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
        "replicas": STRUCTURAL_REPLICAS,
        "requested_rollouts": STRUCTURAL_ROLLOUT_COUNT,
        "maximum_tool_calls": MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_total_observation_bytes": MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": 2,
        "thresholds": thresholds,
        "analysis_plan": StructuralHierarchicalAnalysisPlan(),
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "next_permitted_stage": "direct_structural_tier_localization",
        "model_ranking_claim_authorized": False,
        "paired_calibration_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinanceStructuralTierLocalizationContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceStructuralTierLocalizationContract(
        contract_id=structural_localization_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_structural_tier_localization(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceStructuralTierLocalizationReport:
    if workers < 1:
        raise ValueError("structural localization workers must be positive")
    contract = FinanceStructuralTierLocalizationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    population = StructuralCapabilityLadderPopulation.model_validate_json(
        Path(contract.population_path).read_text(encoding="utf-8")
    )
    if population.population_id != contract.population_id:
        raise ValueError("structural localization loaded another population")
    tasks = {item.artifact_id: item for item in population.tasks}
    if set(contract.task_group_ids) != set(tasks):
        raise ValueError("structural task manifest differs from its population")
    run_identity = structural_localization_run_identity(contract)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "structural_tier_localization.checkpoint.jsonl"
    records_path = output_dir / "structural_tier_localization_records.jsonl"
    outcomes_path = output_dir / "structural_tier_localization_outcomes.jsonl"
    report_path = output_dir / "finance_structural_tier_localization_report.json"
    manifest_path = output_dir / "structural_tier_localization_run_manifest.json"
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
        f"[v25.10:structural] resuming {len(records)}/{len(jobs)}; "
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
                    raise ValueError("structural localization worker returned another job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                records[key] = record
                if index % 25 == 0 or index == len(futures):
                    print(
                        f"[v25.10:structural] completed {len(records)}/{len(jobs)}",
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
    report = make_structural_localization_report(contract, outcomes)
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        manifest_path,
        {
            "run_identity": run_identity,
            "runner_version": STRUCTURAL_LOCALIZATION_RUNNER_VERSION,
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


def make_structural_localization_report(
    contract: FinanceStructuralTierLocalizationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinanceStructuralTierLocalizationReport:
    _validate_outcomes(contract, outcomes)
    binding_by_id = {item.binding_id: item for item in contract.bindings}
    grouped: dict[
        tuple[ExplorerArm, str, DifficultyTier],
        list[CapabilityRolloutOutcome],
    ] = defaultdict(list)
    for item in outcomes:
        binding = binding_by_id[item.binding_id]
        grouped[(item.model_arm, item.family, binding.tier)].append(item)
    cells = []
    runtime = CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
    for model in ExplorerArm:
        for family in STRUCTURAL_FAMILIES:
            for tier in DifficultyTier:
                cell_outcomes = grouped[(model, family, tier)]
                by_group: dict[str, list[CapabilityRolloutOutcome]] = defaultdict(list)
                for item in cell_outcomes:
                    by_group[contract.task_group_ids[item.task_artifact_id]].append(item)
                group_rates = {
                    group_id: sum(item.semantic_answer_correct for item in group_values)
                    / len(group_values)
                    for group_id, group_values in sorted(by_group.items())
                }
                success_count = sum(
                    item.semantic_answer_correct for item in cell_outcomes
                )
                cells.append(
                    MatchedTierCell(
                        model_arm=model,
                        runtime_arm=runtime,
                        family=family,
                        tier=tier,
                        attempted_count=len(cell_outcomes),
                        technical_resolution_count=sum(
                            item.completed for item in cell_outcomes
                        ),
                        bounded_json_resolution_count=sum(
                            item.bounded_json_resolution_success
                            for item in cell_outcomes
                        ),
                        observation_replay_count=sum(
                            item.observation_replay_success for item in cell_outcomes
                        ),
                        authority_integrity_count=sum(
                            item.authority_integrity_success for item in cell_outcomes
                        ),
                        semantic_success_count=success_count,
                        valid_success_count=sum(
                            item.valid_success for item in cell_outcomes
                        ),
                        semantic_success_rate=success_count / len(cell_outcomes),
                        semantic_success_interval=_wilson_interval(
                            success_count,
                            len(cell_outcomes),
                        ),
                        group_success_rates=group_rates,
                        group_rate_variance=pvariance(group_rates.values()),
                        budget_exhaustion_count=sum(
                            item.budget_exhausted for item in cell_outcomes
                        ),
                        runtime_infrastructure_failure_count=sum(
                            item.runtime_infrastructure_failure_count
                            for item in cell_outcomes
                        ),
                        api_call_count=sum(
                            item.api_call_count for item in cell_outcomes
                        ),
                        total_model_tokens=sum(
                            item.total_model_tokens for item in cell_outcomes
                        ),
                        estimated_cost_usd=sum(
                            item.estimated_cost_usd for item in cell_outcomes
                        ),
                    )
                )
    monotonic_count, ladder_count = _group_monotonic_count(
        outcomes,
        binding_by_id=binding_by_id,
        task_group_ids=contract.task_group_ids,
    )
    technical_rate = sum(item.completed for item in outcomes) / len(outcomes)
    technical_passed = (
        technical_rate >= contract.thresholds.minimum_technical_resolution_rate
        and all(item.bounded_json_resolution_success for item in outcomes)
        and all(item.observation_replay_success for item in outcomes)
        and all(item.authority_integrity_success for item in outcomes)
        and not any(item.budget_exhausted for item in outcomes)
        and not any(item.runtime_infrastructure_failure_count for item in outcomes)
    )
    semantic_rate = sum(item.semantic_answer_correct for item in outcomes) / len(outcomes)
    ready = (
        technical_passed
        and semantic_rate >= contract.thresholds.minimum_direct_control_semantic_rate
    )
    values = {
        "contract_id": contract.contract_id,
        "population_id": contract.population_id,
        "requested_rollout_count": contract.requested_rollouts,
        "recorded_rollout_count": len(outcomes),
        "cell_count": len(cells),
        "cells": tuple(cells),
        "thresholds": contract.thresholds,
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.outcome_id for item in outcomes)),
            prefix="finance_structural_localization_outcomes:",
        ),
        "technical_resolution_rate": technical_rate,
        "group_monotonic_ladder_count": monotonic_count,
        "group_ladder_count": ladder_count,
        "group_monotonic_fraction": monotonic_count / ladder_count,
        "semantic_success_rate": semantic_rate,
        "direct_positive_control_ready": ready,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "technical_status": "passed" if technical_passed else "failed",
        "next_permitted_stage": (
            "workflow_ladder_localization"
            if ready
            else "runtime_contract_repair_only"
        ),
        "direct_runtime_only": True,
        "direct_runtime_role": "positive_execution_control",
        "direct_runtime_excluded_from_boundary_selection": True,
        "workflow_confound_excluded": True,
        "distractor_confound_excluded": True,
        "matched_group_random_effect_included": True,
        "semantic_results_are_development_only": True,
        "pro_flash_ranking_authorized": False,
        "paired_calibration_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinanceStructuralTierLocalizationReport.model_construct(
        report_id="pending",
        **values,
    )
    return FinanceStructuralTierLocalizationReport(
        report_id=structural_localization_report_id(provisional),
        **values,
    )


def _validate_structural_bindings(
    bindings: tuple[RuntimeTaskBinding, ...],
    task_group_ids: Mapping[str, str],
) -> None:
    if len(bindings) != STRUCTURAL_BINDING_COUNT:
        raise ValueError("structural localization binding count is incomplete")
    if any(
        item.runtime_arm != CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
        for item in bindings
    ):
        raise ValueError("structural localization contains a non-Direct binding")
    task_ids = {item.task_artifact_id for item in bindings}
    if set(task_group_ids) != task_ids or len(task_ids) != STRUCTURAL_TASK_COUNT:
        raise ValueError("structural task/group manifest is inconsistent")
    if len(task_ids) != len(bindings):
        raise ValueError("structural task does not have exactly one Direct binding")
    group_counts = Counter(task_group_ids.values())
    if len(group_counts) != STRUCTURAL_GROUP_COUNT or set(group_counts.values()) != {3}:
        raise ValueError("structural groups lack exactly three Tiers")
    if Counter((item.family, item.tier) for item in bindings) != Counter(
        {
            (family, tier): STRUCTURAL_GROUPS_PER_FAMILY
            for family in STRUCTURAL_FAMILIES
            for tier in DifficultyTier
        }
    ):
        raise ValueError("structural localization is not balanced by family and Tier")


def _validate_outcomes(
    contract: FinanceStructuralTierLocalizationContract,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> None:
    if len(outcomes) != contract.requested_rollouts:
        raise ValueError("structural localization outcomes have an incomplete denominator")
    binding_ids = {item.binding_id for item in contract.bindings}
    keys = set()
    for item in outcomes:
        key = (item.model_arm, item.binding_id, item.replicate)
        if key in keys:
            raise ValueError("structural localization duplicates a rollout")
        keys.add(key)
        if (
            item.contract_id != contract.contract_id
            or item.stage != BoundaryStage.TIER_LOCALIZATION
            or item.runtime_arm
            != CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
            or item.binding_id not in binding_ids
            or not 0 <= item.replicate < contract.replicas
        ):
            raise ValueError("structural localization contains an unknown rollout")


def _verify_frozen_inputs(contract: FinanceStructuralTierLocalizationContract) -> None:
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
            raise ValueError(f"frozen structural-localization input changed:{path}")


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    contract: FinanceStructuralTierLocalizationContract,
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
            raise ValueError("structural checkpoint duplicates a rollout")
        keys.add(key)
        if (
            record.run_identity != run_identity
            or record.contract_id != contract.contract_id
            or record.stage != BoundaryStage.TIER_LOCALIZATION
            or record.runtime_arm
            != CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
            or record.binding_id not in binding_ids
            or not 0 <= record.replicate < contract.replicas
        ):
            raise ValueError("structural checkpoint contains an unknown rollout")
    return records


def _load_discovered_models(
    path: Path,
    run_identity: str,
) -> dict[ExplorerArm, tuple[str, ...]]:
    if not path.is_file():
        raise ValueError("completed structural run lacks a model-discovery manifest")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("run_identity") != run_identity:
        raise ValueError("structural model-discovery manifest belongs to another run")
    discovered = raw.get("discovered_models")
    if not isinstance(discovered, dict):
        raise ValueError("structural run manifest lacks model discovery evidence")
    return {
        arm: tuple(str(item) for item in discovered.get(arm.value, ()))
        for arm in ExplorerArm
    }


def _record_key(
    record: CapabilityBoundaryRolloutRecord,
) -> tuple[ExplorerArm, str, int]:
    return record.model_arm, record.binding_id, record.replicate


def structural_localization_run_identity(
    contract: FinanceStructuralTierLocalizationContract,
) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "runner_version": STRUCTURAL_LOCALIZATION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "binding_ids": tuple(sorted(item.binding_id for item in contract.bindings)),
            "replicas": contract.replicas,
        },
        prefix="finance_structural_tier_localization_run:",
    )


def structural_localization_contract_id(
    value: FinanceStructuralTierLocalizationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_structural_tier_localization_contract:",
    )


def structural_localization_report_id(
    value: FinanceStructuralTierLocalizationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_structural_tier_localization_report:",
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
        description="Freeze or run Direct structural Pro/Flash tier localization"
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
        contract = prepare_structural_tier_localization_contract(
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
        report = run_structural_tier_localization(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        result = {
            "report_id": report.report_id,
            "recorded_rollouts": report.recorded_rollout_count,
            "technical_status": report.technical_status,
            "semantic_success_rate": report.semantic_success_rate,
            "group_monotonic_fraction": report.group_monotonic_fraction,
            "direct_positive_control_ready": report.direct_positive_control_ready,
            "next_permitted_stage": report.next_permitted_stage,
            "api_calls": report.api_call_count,
            "total_model_tokens": report.total_model_tokens,
            "estimated_cost_usd": report.estimated_cost_usd,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
