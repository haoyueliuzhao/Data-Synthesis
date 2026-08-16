from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import ProgramExecutionError
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_RUNTIME_VERSION,
    FinanceStoppingDependencyOption,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    SubmechanismKind,
    make_finance_submechanism_scenario,
    submechanism_policy_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _candidate_iterator,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismSpec,
    _linear_graph,
    _spec,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    _RECOVERY_BRANCH_KINDS,
    PUBLIC_SUBMECHANISM_METADATA_KEY,
    _answer_contract_ready,
    _freeze_scenario,
    _make_scenario,
    _select_distractor,
    replay_submechanism_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_redesign import (
    FinanceStoppingShapeRedesignContract,
    FinanceStoppingShapeRedesignReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_redesign_protocol import (
    FinanceStoppingShapeRedesignPopulation,
    FinanceStoppingShapeRedesignProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    SHAPE_COUNT,
    STRUCTURAL_STRATA,
    FrozenArtifactReference,
    StoppingShapeTask,
    _collect_excluded_identities,
    _difficulty_vector,
    _public_task_isolated,
    _rate,
    stopping_shape_task_id,
)
from trusted_synthesis.hashing import canonical_hash

STOPPING_DUAL_ESTIMAND_PROTOCOL_VERSION = "finance_stopping_dual_estimand_protocol.v1"
STOPPING_DUAL_ESTIMAND_POPULATION_VERSION = "finance_stopping_dual_estimand_population.v1"
STOPPING_DUAL_ESTIMAND_AUDIT_VERSION = "finance_stopping_dual_estimand_static_audit.v1"
STOPPING_DUAL_ESTIMAND_EXPERIMENT_LABEL = "finance_v25_38_stopping_dual_estimand_development"

TASKS_PER_STRATUM = 2
TASKS_PER_SHAPE = len(STRUCTURAL_STRATA) * TASKS_PER_STRATUM
EXPECTED_TASK_COUNT = SHAPE_COUNT * TASKS_PER_SHAPE
REPLICAS = 8
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * REPLICAS

PROSPECTIVE_RECHECK_SHAPES = frozenset(
    {
        "authority_coverage_gap",
        "contextual_resolution_choice",
        "verified_extra_call_error_risk",
    }
)
STRUCTURAL_REDESIGN_SHAPES = frozenset(
    {
        "partial_required_evidence",
        "single_dimension_conflict",
        "verified_extra_call_cost",
    }
)
ALL_SHAPES = PROSPECTIVE_RECHECK_SHAPES | STRUCTURAL_REDESIGN_SHAPES


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoppingDualEstimandThresholds(FrozenModel):
    boundary_probability_lower: float = Field(default=0.125, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.875, ge=0, le=1)
    minimum_boundary_tasks_per_candidate_shape: int = Field(default=4, ge=1, le=8)
    minimum_nonzero_tasks_per_candidate_shape: int = Field(default=6, ge=1, le=8)
    minimum_effective_task_count: float = Field(default=4.0, ge=1, le=8)
    maximum_single_task_information_share: float = Field(default=0.35, gt=0, le=1)
    maximum_between_task_probability_range: float = Field(default=0.75, ge=0, le=1)
    minimum_control_shape_success_rate: float = Field(default=0.75, ge=0, le=1)
    minimum_runtime_execution_integrity: float = Field(default=1.0, ge=1, le=1)
    minimum_terminal_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=1, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_l0_l2_failure_count: int = Field(default=0, ge=0, le=0)
    bootstrap_replicates: int = Field(default=4_000, ge=1_000)
    bootstrap_seed: int = 20260818

    @model_validator(mode="after")
    def validate_thresholds(self) -> StoppingDualEstimandThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("Stopping dual-estimand boundary interval is empty")
        return self


class StoppingDualEstimandDefinition(FrozenModel):
    stopping_behavior_response: Literal["stopping_behavior_success"] = "stopping_behavior_success"
    stopping_behavior_expression: Literal[
        "runtime_eligible AND host_event_ordered AND NOT post_completion_violation"
    ] = "runtime_eligible AND host_event_ordered AND NOT post_completion_violation"
    full_valid_trajectory_response: Literal["full_valid_trajectory_success"] = (
        "full_valid_trajectory_success"
    )
    full_valid_trajectory_expression: Literal[
        "stopping_behavior_success AND terminal.valid_success"
    ] = "stopping_behavior_success AND terminal.valid_success"
    answer_semantic_response: Literal["answer_semantic_success"] = "answer_semantic_success"
    answer_semantic_expression: Literal["terminal.semantic_answer_correct"] = (
        "terminal.semantic_answer_correct"
    )
    mechanism_observable_support_response: Literal["stopping_behavior_success"] = (
        "stopping_behavior_success"
    )
    valid_training_support_response: Literal["full_valid_trajectory_success"] = (
        "full_valid_trajectory_success"
    )
    contribution_authorized_support_response: Literal["not_evaluated_in_v25_38"] = (
        "not_evaluated_in_v25_38"
    )
    cross_estimand_rescue_forbidden: Literal[True] = True
    invalid_trajectory_training_use_forbidden: Literal[True] = True
    historical_v25_37_reclassification_authorized: Literal[False] = False


class StoppingDualEstimandDesign(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    early_stop_consequence: str = Field(min_length=1)
    source_spec_id: str = Field(min_length=1)
    source_spec_hash: str = Field(min_length=1)
    source_result_admitted: bool
    historical_result_transfer_authorized: Literal[False] = False
    design_status: Literal["prospective_estimand_recheck", "structural_redesign"]
    spec: CapabilitySubmechanismSpec
    intervention_kind: SubmechanismKind
    decision_contract_kind: (
        Literal[
            "dependency_disambiguation_required",
            "single_conflict_semantic_choice_one_step",
            "sealed_terminal_extra_call_cost",
        ]
        | None
    ) = None
    expected_task_instances: Literal[8] = 8

    @model_validator(mode="after")
    def validate_design(self) -> StoppingDualEstimandDesign:
        if self.shape_id not in ALL_SHAPES:
            raise ValueError("Stopping dual-estimand contains an unknown Shape")
        if self.spec.runtime_contract.intervention_kind != self.intervention_kind:
            raise ValueError("Stopping dual-estimand Runtime kind differs from its spec")
        if self.spec.runtime_contract.implementation_status != (
            "host_and_materializer_implemented"
        ):
            raise ValueError("Stopping dual-estimand lacks an implemented Runtime")
        expected_contract = {
            "partial_required_evidence": "dependency_disambiguation_required",
            "single_dimension_conflict": "single_conflict_semantic_choice_one_step",
            "verified_extra_call_cost": "sealed_terminal_extra_call_cost",
        }.get(self.shape_id)
        if self.shape_id in PROSPECTIVE_RECHECK_SHAPES:
            valid = (
                self.design_status == "prospective_estimand_recheck"
                and self.decision_contract_kind is None
            )
        else:
            valid = (
                self.design_status == "structural_redesign"
                and self.decision_contract_kind == expected_contract
            )
        if not valid:
            raise ValueError("Stopping dual-estimand design status is inconsistent")
        return self


class FinanceStoppingDualEstimandProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_38_stopping_dual_estimand_development"] = (
        "finance_v25_38_stopping_dual_estimand_development"
    )
    source_v25_37_protocol: FrozenArtifactReference
    source_v25_37_population: FrozenArtifactReference
    source_v25_37_contract: FrozenArtifactReference
    source_v25_37_report: FrozenArtifactReference
    source_finance_artifacts: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=35)
    estimand_definition: StoppingDualEstimandDefinition = Field(
        default_factory=StoppingDualEstimandDefinition
    )
    shape_designs: tuple[StoppingDualEstimandDesign, ...] = Field(
        min_length=SHAPE_COUNT, max_length=SHAPE_COUNT
    )
    structural_strata: tuple[tuple[str, str, DifficultyTier], ...] = STRUCTURAL_STRATA
    thresholds: StoppingDualEstimandThresholds = Field(
        default_factory=StoppingDualEstimandThresholds
    )
    tasks_per_stratum: Literal[2] = 2
    tasks_per_shape: Literal[8] = 8
    task_count: Literal[48] = 48
    replicas: Literal[8] = 8
    rollout_count: Literal[384] = 384
    task_instance_is_primary_sampling_unit: Literal[True] = True
    same_task_replica_increase_forbidden: Literal[True] = True
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    cross_estimand_rescue_forbidden: Literal[True] = True
    posthoc_task_selection_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    historical_results_transfer_authorized: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["stopping_dual_estimand_population_build"] = (
        "stopping_dual_estimand_population_build"
    )
    schema_version: str = STOPPING_DUAL_ESTIMAND_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingDualEstimandProtocol:
        if self.structural_strata != STRUCTURAL_STRATA:
            raise ValueError("Stopping dual-estimand structural strata changed")
        if {item.shape_id for item in self.shape_designs} != ALL_SHAPES:
            raise ValueError("Stopping dual-estimand coverage is incomplete")
        if len({item.intervention_kind for item in self.shape_designs}) != SHAPE_COUNT:
            raise ValueError("Stopping dual-estimand Runtime kinds are duplicated")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Stopping dual-estimand historical populations are duplicated")
        if self.source_v25_37_population.artifact_id not in {
            item.artifact_id for item in self.historical_population_references
        }:
            raise ValueError("v25.37 Population is absent from the freshness exclusion set")
        if self.estimand_definition != StoppingDualEstimandDefinition():
            raise ValueError("Stopping dual-estimand definition changed")
        if self.protocol_id != stopping_dual_estimand_protocol_id(self):
            raise ValueError("Stopping dual-estimand protocol identity is invalid")
        return self


class StoppingDualEstimandStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: int = Field(ge=1)
    shape_task_counts: dict[str, int]
    stratum_task_counts: dict[str, int]
    shape_stratum_task_counts: dict[str, int]
    design_status_task_counts: dict[str, int]
    operation_replay_rate: float = Field(ge=0, le=1)
    host_replay_rate: float = Field(ge=0, le=1)
    public_oracle_isolation_rate: float = Field(ge=0, le=1)
    answer_contract_rate: float = Field(ge=0, le=1)
    public_decision_contract_rate: float = Field(ge=0, le=1)
    dependency_choice_contract_rate: float = Field(ge=0, le=1)
    semantic_conflict_contract_rate: float = Field(ge=0, le=1)
    sealed_cost_contract_rate: float = Field(ge=0, le=1)
    lexical_conflict_leakage_count: int = Field(ge=0, le=0)
    within_population_evidence_disjoint: bool
    historical_task_disjoint: bool
    historical_evidence_disjoint: bool
    historical_evidence_version_disjoint: bool
    historical_semantic_signature_disjoint: bool
    historical_materializer_disjoint: bool
    dual_estimand_frozen_pre_api: bool
    historical_result_transfer_forbidden: bool
    structural_redesign_scoped: bool
    exact_shape_stratum_redundancy: bool
    task_expected_host_events_frozen_pre_api: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_stopping_dual_estimand_development",
        "stopping_dual_estimand_population_repair_only",
    ]
    schema_version: str = STOPPING_DUAL_ESTIMAND_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingDualEstimandStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Stopping dual-estimand static decision is inconsistent")
        expected_stage = (
            "flash_stopping_dual_estimand_development"
            if expected
            else "stopping_dual_estimand_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping dual-estimand transition is not fail-closed")
        if self.audit_id != stopping_dual_estimand_static_audit_id(self):
            raise ValueError("Stopping dual-estimand audit identity is invalid")
        return self


class FinanceStoppingDualEstimandPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_path: str = Field(min_length=1)
    protocol_sha256: str = Field(min_length=64, max_length=64)
    protocol_id: str = Field(min_length=1)
    tasks: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_stratum_instance_indices: dict[str, int]
    task_design_statuses: dict[str, Literal["prospective_estimand_recheck", "structural_redesign"]]
    task_expected_host_events: dict[str, tuple[str, str]]
    static_audit: StoppingDualEstimandStaticAudit
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_api_calls: Literal[0] = 0
    model_tokens: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_stopping_dual_estimand_development",
        "stopping_dual_estimand_population_repair_only",
    ]
    schema_version: str = STOPPING_DUAL_ESTIMAND_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingDualEstimandPopulation:
        task_ids = {item.artifact.artifact_id for item in self.tasks}
        if any(
            set(mapping) != task_ids
            for mapping in (
                self.task_stratum_instance_indices,
                self.task_design_statuses,
                self.task_expected_host_events,
            )
        ):
            raise ValueError("Stopping dual-estimand task maps are incomplete")
        if set(self.task_stratum_instance_indices.values()) != {0, 1}:
            raise ValueError("Stopping dual-estimand lacks both stratum instances")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("Stopping dual-estimand population differs from its audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_dual_estimand_population_implementation:",
        ):
            raise ValueError("Stopping dual-estimand implementation identity is invalid")
        if self.population_id != stopping_dual_estimand_population_id(self):
            raise ValueError("Stopping dual-estimand population identity is invalid")
        return self


def stopping_dual_estimand_protocol_id(
    value: FinanceStoppingDualEstimandProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_stopping_dual_estimand_protocol:",
    )


def stopping_dual_estimand_static_audit_id(
    value: StoppingDualEstimandStaticAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_stopping_dual_estimand_static_audit:",
    )


def stopping_dual_estimand_population_id(
    value: FinanceStoppingDualEstimandPopulation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_stopping_dual_estimand_population:",
    )


def prepare_stopping_dual_estimand_protocol(
    *,
    source_protocol_path: Path,
    source_population_path: Path,
    source_contract_path: Path,
    source_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingDualEstimandProtocol:
    if output_path.exists():
        raise ValueError("Stopping dual-estimand protocol is immutable")
    paths = tuple(
        path.resolve()
        for path in (
            source_protocol_path,
            source_population_path,
            source_contract_path,
            source_report_path,
        )
    )
    source_protocol = FinanceStoppingShapeRedesignProtocol.model_validate_json(
        paths[0].read_text(encoding="utf-8")
    )
    source_population = FinanceStoppingShapeRedesignPopulation.model_validate_json(
        paths[1].read_text(encoding="utf-8")
    )
    source_contract = FinanceStoppingShapeRedesignContract.model_validate_json(
        paths[2].read_text(encoding="utf-8")
    )
    source_report = FinanceStoppingShapeRedesignReport.model_validate_json(
        paths[3].read_text(encoding="utf-8")
    )
    if not (
        source_population.protocol_id == source_protocol.protocol_id
        and source_contract.source_protocol.artifact_id == source_protocol.protocol_id
        and source_contract.source_population.artifact_id == source_population.population_id
        and source_report.contract_id == source_contract.contract_id
    ):
        raise ValueError("v25.37 Stopping Shape lineage is inconsistent")
    if not (
        source_report.runtime_measurement_ready
        and not source_report.all_shapes_admitted
        and not source_report.difficulty_policy_frozen
        and not source_report.fresh_three_population_preparation_authorized
        and source_report.next_permitted_stage == "stopping_shape_redesign_only"
    ):
        raise ValueError("v25.37 did not authorize prospective estimand redesign")
    admitted = {item.shape_id for item in source_report.shape_results if item.admitted}
    if admitted != {"authority_coverage_gap", "contextual_resolution_choice"}:
        raise ValueError("v25.37 Shape result identity differs from the frozen audit")
    result_by_shape = {item.shape_id: item for item in source_report.shape_results}
    designs = tuple(
        _make_dual_estimand_design(item, result_by_shape[item.shape_id].admitted)
        for item in source_protocol.shape_designs
    )
    historical = tuple(
        sorted(
            (
                *source_protocol.historical_population_references,
                _reference(paths[1], source_population.population_id),
            ),
            key=lambda item: item.artifact_id,
        )
    )
    if len({item.artifact_id for item in historical}) != len(historical):
        raise ValueError("v25.38 historical exclusion set contains a duplicate")
    values = {
        "run_id": run_id,
        "source_v25_37_protocol": _reference(paths[0], source_protocol.protocol_id),
        "source_v25_37_population": _reference(paths[1], source_population.population_id),
        "source_v25_37_contract": _reference(paths[2], source_contract.contract_id),
        "source_v25_37_report": _reference(paths[3], source_report.report_id),
        "source_finance_artifacts": source_protocol.source_finance_artifacts,
        "source_calibration_contract": source_protocol.source_calibration_contract,
        "historical_population_references": historical,
        "estimand_definition": StoppingDualEstimandDefinition(),
        "shape_designs": designs,
    }
    provisional = FinanceStoppingDualEstimandProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceStoppingDualEstimandProtocol(
        protocol_id=stopping_dual_estimand_protocol_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    return protocol


def build_stopping_dual_estimand_population(
    *,
    protocol_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceStoppingDualEstimandPopulation:
    output_path = output_dir / "finance_stopping_dual_estimand_population.json"
    if output_path.exists():
        raise ValueError("Stopping dual-estimand population is immutable")
    protocol_path = protocol_path.resolve()
    protocol = FinanceStoppingDualEstimandProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    excluded = _collect_excluded_identities(protocol.historical_population_references)
    pool = _load_evidence_pool(Path(protocol.source_finance_artifacts.path))
    builder = _CapabilityTaskBuilder(pool, sampling_salt=f"{run_id}:stopping-dual-estimand")
    used_ids = set(excluded["evidence_id"])
    used_versions = set(excluded["evidence_version_id"])
    tasks: list[StoppingShapeTask] = []
    instance_indices: dict[str, int] = {}
    statuses: dict[str, Literal["prospective_estimand_recheck", "structural_redesign"]] = {}
    for design in protocol.shape_designs:
        for stratum_id, family, tier in protocol.structural_strata:
            for instance_index in range(TASKS_PER_STRATUM):
                task = _materialize_dual_estimand_task(
                    builder=builder,
                    design=design,
                    stratum_id=stratum_id,
                    family=family,
                    tier=tier,
                    instance_index=instance_index,
                    evidence_pool=tuple(pool.public.values()),
                    used_ids=used_ids,
                    used_versions=used_versions,
                    sampling_salt=(f"{run_id}:{design.shape_id}:{stratum_id}:{instance_index}"),
                )
                if task.artifact.artifact_id in excluded["artifact_id"]:
                    raise ValueError("Stopping dual-estimand reused a historical task")
                if task.source_semantic_signature in excluded["source_semantic_signature"]:
                    raise ValueError("Stopping dual-estimand reused historical semantics")
                if task.materializer_hash in excluded["materializer_hash"]:
                    raise ValueError("Stopping dual-estimand reused a historical materializer")
                tasks.append(task)
                task_id = task.artifact.artifact_id
                instance_indices[task_id] = instance_index
                statuses[task_id] = design.design_status
                used_ids.update(item.evidence_id for item in task.artifact.public_corpus.evidence)
                used_versions.update(
                    item.evidence_version_id for item in task.artifact.public_corpus.evidence
                )
    frozen_tasks = tuple(tasks)
    host_events = {
        item.artifact.artifact_id: item.scenario.expected_host_events for item in frozen_tasks
    }
    audit = make_stopping_dual_estimand_static_audit(
        frozen_tasks,
        protocol,
        excluded=excluded,
        task_stratum_instance_indices=instance_indices,
        task_design_statuses=statuses,
        task_expected_host_events=host_events,
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "protocol_path": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "protocol_id": protocol.protocol_id,
        "tasks": frozen_tasks,
        "task_stratum_instance_indices": instance_indices,
        "task_design_statuses": statuses,
        "task_expected_host_events": host_events,
        "static_audit": audit,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_dual_estimand_population_implementation:",
        ),
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = FinanceStoppingDualEstimandPopulation.model_construct(
        population_id="pending", **values
    )
    population = FinanceStoppingDualEstimandPopulation(
        population_id=stopping_dual_estimand_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_dual_estimand_static_audit.json",
        audit.model_dump(mode="json"),
    )
    (output_dir / "finance_stopping_dual_estimand_population_report.md").write_text(
        _render_population_report(population), encoding="utf-8"
    )
    return population


def make_stopping_dual_estimand_static_audit(
    tasks: Sequence[StoppingShapeTask],
    protocol: FinanceStoppingDualEstimandProtocol,
    *,
    excluded: Mapping[str, set[str]],
    task_stratum_instance_indices: Mapping[str, int],
    task_design_statuses: Mapping[
        str, Literal["prospective_estimand_recheck", "structural_redesign"]
    ],
    task_expected_host_events: Mapping[str, tuple[str, str]],
) -> StoppingDualEstimandStaticAudit:
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}
    shape_counts = Counter(item.shape_id for item in tasks)
    stratum_counts = Counter(item.stratum_id for item in tasks)
    shape_stratum_counts = Counter(f"{item.shape_id}|{item.stratum_id}" for item in tasks)
    status_counts = Counter(task_design_statuses.values())
    evidence = [item for task in tasks for item in task.artifact.public_corpus.evidence]
    task_ids = {item.artifact.artifact_id for item in tasks}
    semantic = {item.source_semantic_signature for item in tasks}
    materializers = {item.materializer_hash for item in tasks}
    expected_shape_strata = {
        f"{shape_id}|{stratum[0]}" for shape_id in ALL_SHAPES for stratum in STRUCTURAL_STRATA
    }
    prospective_untuned = all(
        item.scenario.stopping_shape_decision_contract is None
        for item in tasks
        if item.shape_id in PROSPECTIVE_RECHECK_SHAPES
    )
    structural_scoped = all(
        (
            item.scenario.stopping_shape_decision_contract is not None
            and item.shape_id in STRUCTURAL_REDESIGN_SHAPES
        )
        == (item.shape_id in STRUCTURAL_REDESIGN_SHAPES)
        for item in tasks
    )
    partial_tasks = tuple(item for item in tasks if item.shape_id == "partial_required_evidence")
    conflict_tasks = tuple(item for item in tasks if item.shape_id == "single_dimension_conflict")
    cost_tasks = tuple(item for item in tasks if item.shape_id == "verified_extra_call_cost")
    dependency_checks = tuple(_dependency_contract_ready(item) for item in partial_tasks)
    conflict_checks = tuple(_semantic_conflict_contract_ready(item) for item in conflict_tasks)
    cost_checks = tuple(_sealed_cost_contract_ready(item) for item in cost_tasks)
    lexical_leaks = sum(not _conflict_public_text_isolated(item) for item in conflict_tasks)
    public_contract = {
        item.artifact.artifact_id: _public_decision_contract_matches(item) for item in tasks
    }
    checks = {
        "complete_task_count": len(tasks) == EXPECTED_TASK_COUNT,
        "shape_redundancy": set(shape_counts) == ALL_SHAPES
        and set(shape_counts.values()) == {TASKS_PER_SHAPE},
        "stratum_balance": set(stratum_counts) == {item[0] for item in STRUCTURAL_STRATA}
        and set(stratum_counts.values()) == {SHAPE_COUNT * TASKS_PER_STRATUM},
        "shape_stratum_redundancy": set(shape_stratum_counts) == expected_shape_strata
        and set(shape_stratum_counts.values()) == {TASKS_PER_STRATUM},
        "operation_replay": all(item.artifact.verification.passed for item in tasks),
        "host_replay": all(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation": all(_public_task_isolated(item) for item in tasks),
        "answer_contract": all(_answer_contract_ready(item.artifact) for item in tasks),
        "public_decision_contract": all(public_contract.values()),
        "dependency_choice_contract": len(dependency_checks) == TASKS_PER_SHAPE
        and all(dependency_checks),
        "semantic_conflict_contract": len(conflict_checks) == TASKS_PER_SHAPE
        and all(conflict_checks),
        "sealed_cost_contract": len(cost_checks) == TASKS_PER_SHAPE and all(cost_checks),
        "zero_lexical_conflict_leakage": lexical_leaks == 0,
        "within_evidence_disjoint": len(evidence) == len({item.evidence_id for item in evidence}),
        "historical_task_disjoint": not task_ids & excluded["artifact_id"],
        "historical_evidence_disjoint": not {item.evidence_id for item in evidence}
        & excluded["evidence_id"],
        "historical_version_disjoint": not {item.evidence_version_id for item in evidence}
        & excluded["evidence_version_id"],
        "historical_semantic_disjoint": not semantic & excluded["source_semantic_signature"],
        "historical_materializer_disjoint": not materializers & excluded["materializer_hash"],
        "distinct_task_instances": len(task_ids) == EXPECTED_TASK_COUNT,
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
        "prospective_shapes_untuned": prospective_untuned,
        "structural_redesign_scoped": structural_scoped,
        "design_statuses": set(task_design_statuses) == task_ids
        and all(
            task_design_statuses[item.artifact.artifact_id]
            == design_by_shape[item.shape_id].design_status
            for item in tasks
        ),
        "dual_estimand_frozen_pre_api": (
            protocol.estimand_definition == StoppingDualEstimandDefinition()
            and protocol.cross_estimand_rescue_forbidden
        ),
        "historical_result_transfer_forbidden": (
            not protocol.historical_results_transfer_authorized
            and all(
                not item.historical_result_transfer_authorized for item in protocol.shape_designs
            )
        ),
        "host_events_frozen_pre_api": set(task_expected_host_events) == task_ids,
        "frontier_only": all(item.artifact.tier == DifficultyTier.FRONTIER for item in tasks),
    }
    rejections = tuple(sorted(key for key, passed in checks.items() if not passed))
    values = {
        "task_count": len(tasks),
        "shape_task_counts": dict(sorted(shape_counts.items())),
        "stratum_task_counts": dict(sorted(stratum_counts.items())),
        "shape_stratum_task_counts": dict(sorted(shape_stratum_counts.items())),
        "design_status_task_counts": dict(sorted(status_counts.items())),
        "operation_replay_rate": _rate(item.artifact.verification.passed for item in tasks),
        "host_replay_rate": _rate(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation_rate": _rate(_public_task_isolated(item) for item in tasks),
        "answer_contract_rate": _rate(_answer_contract_ready(item.artifact) for item in tasks),
        "public_decision_contract_rate": _rate(public_contract.values()),
        "dependency_choice_contract_rate": _rate(dependency_checks),
        "semantic_conflict_contract_rate": _rate(conflict_checks),
        "sealed_cost_contract_rate": _rate(cost_checks),
        "lexical_conflict_leakage_count": lexical_leaks,
        "within_population_evidence_disjoint": checks["within_evidence_disjoint"],
        "historical_task_disjoint": checks["historical_task_disjoint"],
        "historical_evidence_disjoint": checks["historical_evidence_disjoint"],
        "historical_evidence_version_disjoint": checks["historical_version_disjoint"],
        "historical_semantic_signature_disjoint": checks["historical_semantic_disjoint"],
        "historical_materializer_disjoint": checks["historical_materializer_disjoint"],
        "dual_estimand_frozen_pre_api": checks["dual_estimand_frozen_pre_api"],
        "historical_result_transfer_forbidden": checks["historical_result_transfer_forbidden"],
        "structural_redesign_scoped": checks["structural_redesign_scoped"],
        "exact_shape_stratum_redundancy": checks["shape_stratum_redundancy"],
        "task_expected_host_events_frozen_pre_api": checks["host_events_frozen_pre_api"],
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_stopping_dual_estimand_development"
            if not rejections
            else "stopping_dual_estimand_population_repair_only"
        ),
    }
    provisional = StoppingDualEstimandStaticAudit.model_construct(audit_id="pending", **values)
    return StoppingDualEstimandStaticAudit(
        audit_id=stopping_dual_estimand_static_audit_id(provisional), **values
    )


def _make_dual_estimand_design(
    source: Any,
    source_result_admitted: bool,
) -> StoppingDualEstimandDesign:
    shape_id = str(source.shape_id)
    graph = source.spec.action_graph
    runtime = source.spec.runtime_contract.model_copy(
        update={
            "implementation_status": "host_and_materializer_implemented",
            "implementation_id": (
                f"{FINANCE_SUBMECHANISM_RUNTIME_VERSION}:"
                f"{source.spec.runtime_contract.intervention_kind}"
            ),
        }
    )
    if shape_id == "single_dimension_conflict":
        graph = _linear_graph(
            (
                (
                    "observe_conflict",
                    "observe_failure",
                    "cross_check_evidence",
                ),
                (
                    "resolve_conflict",
                    "resolve_conflict",
                    "normalize_metric_unit_period",
                ),
            )
        )
        runtime = runtime.model_copy(
            update={
                "trigger_node_id": "observe_conflict",
                "resolution_node_id": "resolve_conflict",
            }
        )
    spec = _spec(
        source.spec.parent_mechanism_id,
        shape_id,
        source.spec.title,
        graph,
        source.spec.evidence_dependencies,
        runtime,
        source.spec.diagnostic_outcomes,
    )
    decision_kind = {
        "partial_required_evidence": "dependency_disambiguation_required",
        "single_dimension_conflict": "single_conflict_semantic_choice_one_step",
        "verified_extra_call_cost": "sealed_terminal_extra_call_cost",
    }.get(shape_id)
    return StoppingDualEstimandDesign(
        shape_id=shape_id,
        shape_role=source.shape_role,
        early_stop_consequence=source.early_stop_consequence,
        source_spec_id=source.source_spec_id,
        source_spec_hash=source.spec.spec_hash,
        source_result_admitted=source_result_admitted,
        design_status=(
            "structural_redesign"
            if shape_id in STRUCTURAL_REDESIGN_SHAPES
            else "prospective_estimand_recheck"
        ),
        spec=spec,
        intervention_kind=cast(SubmechanismKind, spec.runtime_contract.intervention_kind),
        decision_contract_kind=cast(Any, decision_kind),
    )


def _task_decision_contract(
    *,
    shape_id: str,
    distractor: EvidenceItem,
    sampling_salt: str,
) -> FinanceStoppingShapeDecisionContract | None:
    if shape_id in PROSPECTIVE_RECHECK_SHAPES:
        return None
    if shape_id == "partial_required_evidence":
        decoy = FinanceStoppingDependencyOption(
            option_id=canonical_hash(
                {
                    "sampling_salt": sampling_salt,
                    "evidence_version_id": distractor.evidence_version_id,
                },
                prefix="finance_stopping_dependency_decoy_option:",
            ),
            subject_alias=distractor.subject.subject_id,
            metric_alias=distractor.predicate,
            period_label=str(distractor.temporal_context.label),
        )
        return FinanceStoppingShapeDecisionContract(
            contract_kind="dependency_disambiguation_required",
            dependency_rule=(
                "Choose the query that supplies an operand still required by the public "
                "operation graph after the already selected evidence. The other query is "
                "valid Archive data but does not close that dependency."
            ),
            dependency_decoy_option=decoy,
            resolution_step_count=1,
        )
    if shape_id == "single_dimension_conflict":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="single_conflict_semantic_choice_one_step",
            observed_conflict_signal=(
                "A direct comparison would change the economic meaning of at least one "
                "selected figure."
            ),
            oracle_conflict_dimension="source_definition_compatibility",
            available_resolution_actions=(
                FinanceStoppingResolutionAction(
                    tool_id="normalize_metric_unit_period",
                    applicable_when=(
                        "re-express the measurements under a shared reporting convention"
                    ),
                ),
                FinanceStoppingResolutionAction(
                    tool_id="open_document",
                    applicable_when=(
                        "inspect provenance when document authority or location is unresolved"
                    ),
                ),
            ),
            resolution_step_count=1,
        )
    if shape_id == "verified_extra_call_cost":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="sealed_terminal_extra_call_cost",
            terminal_utility_loss=1.0,
            archive_snapshot_sealed=True,
            maximum_additional_information_gain=0.0,
            realized_call_budget_debit_fraction=0.25,
            realized_token_budget_debit_fraction=0.20,
            additional_action_rejected=True,
        )
    raise ValueError(f"Stopping Shape has no dual-estimand contract: {shape_id}")


def _evidence_query_identity(item: EvidenceItem) -> tuple[str, str, str]:
    return (
        item.subject.subject_id,
        item.predicate,
        str(item.temporal_context.label),
    )


def _select_distinct_query_distractor(
    *,
    spec: CapabilitySubmechanismSpec,
    gold: tuple[EvidenceItem, ...],
    evidence_pool: tuple[EvidenceItem, ...],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> EvidenceItem | None:
    blocked_ids = set(used_ids)
    blocked_versions = set(used_versions)
    gold_queries = {_evidence_query_identity(item) for item in gold}
    for attempt in range(32):
        candidate = _select_distractor(
            spec,
            gold,
            evidence_pool,
            blocked_ids,
            blocked_versions,
            f"{sampling_salt}:candidate:{attempt}",
        )
        if candidate is None:
            return None
        if _evidence_query_identity(candidate) not in gold_queries:
            return candidate
        blocked_ids.add(candidate.evidence_id)
        blocked_versions.add(candidate.evidence_version_id)
    return None


def _materialize_dual_estimand_task(
    *,
    builder: _CapabilityTaskBuilder,
    design: StoppingDualEstimandDesign,
    stratum_id: str,
    family: str,
    tier: DifficultyTier,
    instance_index: int,
    evidence_pool: tuple[EvidenceItem, ...],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> StoppingShapeTask:
    spec = design.spec
    for gold, program, source_instruction, projection in _candidate_iterator(builder, family, tier):
        if design.shape_id == "partial_required_evidence" and len(gold) < 2:
            continue
        gold_ids = {item.evidence_id for item in gold}
        gold_versions = {item.evidence_version_id for item in gold}
        if gold_ids & used_ids or gold_versions & used_versions:
            continue
        distractor = _select_distinct_query_distractor(
            spec=spec,
            gold=gold,
            evidence_pool=evidence_pool,
            used_ids=used_ids | gold_ids,
            used_versions=used_versions | gold_versions,
            sampling_salt=sampling_salt,
        )
        if distractor is None:
            continue
        recovery = (
            (
                RecoveryBranch(
                    distractor_evidence_id=distractor.evidence_id,
                    mismatch_fields=_minimum_mismatch_fields(distractor, gold),
                ),
            )
            if spec.runtime_contract.intervention_kind in _RECOVERY_BRANCH_KINDS
            else ()
        )
        try:
            artifact = builder._materialize(
                family=family,
                tier=tier,
                gold=gold,
                distractors=(distractor,),
                recovery_branches=recovery,
                program=program,
                instruction=source_instruction,
                answer_projection=projection,
            )
        except ProgramExecutionError:
            continue
        base_scenario = _make_scenario(
            spec,
            gold,
            distractor,
            artifact.projected_expected_output,
        )
        decision = _task_decision_contract(
            shape_id=design.shape_id,
            distractor=distractor,
            sampling_salt=sampling_salt,
        )
        scenario = base_scenario
        if decision is not None:
            scenario = make_finance_submechanism_scenario(
                submechanism_id=base_scenario.submechanism_id,
                parent_mechanism_id=base_scenario.parent_mechanism_id,
                intervention_kind=base_scenario.intervention_kind,
                expected_host_events=base_scenario.expected_host_events,
                evidence_roles=base_scenario.evidence_roles,
                public_resolution_hint=_dual_estimand_resolution_hint(design.shape_id),
                untrusted_candidate=base_scenario.untrusted_candidate,
                canonical_candidate=base_scenario.canonical_candidate,
                repair_target_field=base_scenario.repair_target_field,
                stopping_shape_decision_contract=decision,
            )
        artifact = _freeze_scenario(
            artifact,
            scenario,
            source_instruction=source_instruction,
            projection=projection,
        )
        replay = replay_submechanism_runtime(artifact, scenario)
        if not replay.passed:
            continue
        signature = canonical_hash(
            {
                "shape_id": design.shape_id,
                "family": family,
                "tier": tier,
                "stratum_instance_index": instance_index,
                "gold_versions": tuple(item.evidence_version_id for item in gold),
                "program": program,
                "projection": projection,
                "spec_hash": spec.spec_hash,
                "decision_contract": decision,
                "estimand_definition": StoppingDualEstimandDefinition(),
            },
            prefix="finance_stopping_dual_estimand_semantics:",
        )
        difficulty = _difficulty_vector(
            cast(Any, design),
            artifact,
            spec,
            family=family,
            tier=tier,
        )
        materializer_hash = canonical_hash(
            {
                "shape_id": design.shape_id,
                "stratum_id": stratum_id,
                "stratum_instance_index": instance_index,
                "design_status": design.design_status,
                "spec_hash": spec.spec_hash,
                "artifact_id": artifact.artifact_id,
                "scenario": scenario,
                "difficulty": difficulty,
                "policy": submechanism_policy_manifest()[scenario.intervention_kind],
            },
            prefix="finance_stopping_dual_estimand_materializer:",
        )
        values = {
            "shape_id": design.shape_id,
            "shape_role": design.shape_role,
            "stratum_id": stratum_id,
            "spec_hash": spec.spec_hash,
            "artifact": artifact,
            "scenario": scenario,
            "runtime_replay": replay,
            "difficulty": difficulty,
            "source_semantic_signature": signature,
            "materializer_hash": materializer_hash,
        }
        provisional = StoppingShapeTask.model_construct(task_record_id="pending", **values)
        return StoppingShapeTask(task_record_id=stopping_shape_task_id(provisional), **values)
    raise ValueError(
        "real Finance Evidence cannot support Stopping dual-estimand "
        f"{design.shape_id}/{stratum_id}/{instance_index}"
    )


def _dual_estimand_resolution_hint(shape_id: str) -> str:
    hints = {
        "partial_required_evidence": (
            "The completion state presents two plausible Archive queries. Use the public "
            "operation dependency to choose the query that closes the unresolved operand."
        ),
        "single_dimension_conflict": (
            "One semantic comparison obstacle is present. Map its observed symptom to the "
            "single applicable public action without relying on an internal field label."
        ),
        "verified_extra_call_cost": (
            "The verified Archive snapshot is sealed. Another call cannot add information, "
            "is rejected, and incurs the frozen realized call, token, and utility debit."
        ),
    }
    return hints[shape_id]


def _public_decision_contract_matches(task: StoppingShapeTask) -> bool:
    metadata = task.artifact.task.public.metadata
    parent = metadata.get(PUBLIC_SUBMECHANISM_METADATA_KEY)
    if not isinstance(parent, Mapping):
        return False
    observed = parent.get("stopping_shape_decision_contract")
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None:
        return observed is None
    expected = decision.model_dump(
        mode="json",
        exclude={
            "contract_kind",
            "dependency_decoy_option",
            "oracle_conflict_dimension",
        },
    )
    expected["internal_shape_identity_disclosed"] = False
    public_dump = task.artifact.task.public.model_dump(mode="json")
    text = json.dumps(public_dump, ensure_ascii=False, sort_keys=True)
    return (
        observed == expected
        and "contract_kind" not in _mapping_keys(public_dump)
        and "dependency_decoy_option" not in _mapping_keys(public_dump)
        and "oracle_conflict_dimension" not in _mapping_keys(public_dump)
        and decision.contract_kind not in text
        and task.shape_id not in text
    )


def _dependency_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    if (
        decision is None
        or decision.contract_kind != "dependency_disambiguation_required"
        or decision.dependency_decoy_option is None
        or len(task.scenario.evidence_roles) < 2
    ):
        return False
    decoy_query = (
        decision.dependency_decoy_option.subject_alias,
        decision.dependency_decoy_option.metric_alias,
        decision.dependency_decoy_option.period_label,
    )
    required_queries = {
        (item.subject_alias, item.metric_alias, item.period_label)
        for item in task.scenario.evidence_roles
    }
    return decoy_query not in required_queries and _public_decision_contract_matches(task)


def _semantic_conflict_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    return bool(
        decision is not None
        and decision.contract_kind == "single_conflict_semantic_choice_one_step"
        and decision.oracle_conflict_dimension == "source_definition_compatibility"
        and decision.observed_conflict_signal
        and len(decision.available_resolution_actions) == 2
        and decision.resolution_step_count == 1
        and _conflict_public_text_isolated(task)
        and _public_decision_contract_matches(task)
    )


def _conflict_public_text_isolated(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None or decision.observed_conflict_signal is None:
        return False
    text = json.dumps(
        task.artifact.task.public.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    signal_tokens = _semantic_content_tokens(decision.observed_conflict_signal)
    action_tokens = tuple(
        _semantic_content_tokens(item.applicable_when)
        for item in decision.available_resolution_actions
    )
    return (
        "source_definition_compatibility" not in text
        and "source-definition compatibility" not in text
        and bool(signal_tokens)
        and all(not signal_tokens & tokens for tokens in action_tokens)
    )


def _semantic_content_tokens(value: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "at",
        "be",
        "is",
        "of",
        "or",
        "the",
        "to",
        "under",
        "when",
    }
    return {
        token
        for token in re.findall(r"[a-z]+", value.lower())
        if len(token) > 2 and token not in stopwords
    }


def _sealed_cost_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    return bool(
        decision is not None
        and decision.contract_kind == "sealed_terminal_extra_call_cost"
        and decision.archive_snapshot_sealed is True
        and decision.maximum_additional_information_gain == 0.0
        and decision.realized_call_budget_debit_fraction == 0.25
        and decision.realized_token_budget_debit_fraction == 0.20
        and decision.terminal_utility_loss == 1.0
        and decision.additional_action_rejected is True
        and _public_decision_contract_matches(task)
    )


def _mapping_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(key for item in value.values() for key in _mapping_keys(item)),
        }
    if isinstance(value, (list, tuple)):
        return {key for item in value for key in _mapping_keys(item)}
    return set()


def _verify_protocol_inputs(
    protocol: FinanceStoppingDualEstimandProtocol,
) -> None:
    references = (
        protocol.source_v25_37_protocol,
        protocol.source_v25_37_population,
        protocol.source_v25_37_contract,
        protocol.source_v25_37_report,
        protocol.source_finance_artifacts,
        protocol.source_calibration_contract,
        *protocol.historical_population_references,
    )
    for reference in references:
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"frozen Stopping dual-estimand input changed: {reference.path}")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_population.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_dual_estimand_protocol.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _render_population_report(
    population: FinanceStoppingDualEstimandPopulation,
) -> str:
    lines = [
        "# Finance v25.38 Stopping Dual Estimand Population",
        "",
        f"- Population: {population.population_id}",
        f"- Tasks: {len(population.tasks)}",
        f"- Static ready: {str(population.static_audit.ready).lower()}",
        f"- Next stage: {population.next_permitted_stage}",
        "",
        "| Shape | Stratum | Instance | Status | Program depth | Actions |",
        "| --- | --- | ---: | --- | ---: | ---: |",
    ]
    for item in population.tasks:
        task_id = item.artifact.artifact_id
        lines.append(
            f"| {item.shape_id} | {item.stratum_id} | "
            f"{population.task_stratum_instance_indices[task_id]} | "
            f"{population.task_design_statuses[task_id]} | "
            f"{item.difficulty.program_depth} | "
            f"{item.difficulty.resolution_action_count} |"
        )
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or build v25.38 Stopping Dual Estimand")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-protocol", required=True, type=Path)
    prepare.add_argument("--source-population", required=True, type=Path)
    prepare.add_argument("--source-contract", required=True, type=Path)
    prepare.add_argument("--source-report", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--protocol", required=True, type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--run-id", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        protocol = prepare_stopping_dual_estimand_protocol(
            source_protocol_path=args.source_protocol,
            source_population_path=args.source_population,
            source_contract_path=args.source_contract,
            source_report_path=args.source_report,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(protocol.model_dump_json(indent=2))
    else:
        population = build_stopping_dual_estimand_population(
            protocol_path=args.protocol,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        print(population.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
