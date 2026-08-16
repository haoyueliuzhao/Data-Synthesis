from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_RUNTIME_VERSION,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability import (
    FinanceStoppingShapeStabilityContract,
    FinanceStoppingShapeStabilityReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    SHAPE_COUNT,
    STRUCTURAL_STRATA,
    FinanceStoppingShapePopulation,
    FinanceStoppingShapeStabilityProtocol,
    FrozenArtifactReference,
    StoppingShapeTask,
    _collect_excluded_identities,
    _difficulty_vector,
    _public_task_isolated,
    _rate,
    stopping_shape_task_id,
)
from trusted_synthesis.hashing import canonical_hash

STOPPING_SHAPE_REDESIGN_PROTOCOL_VERSION = "finance_stopping_shape_redesign_protocol.v1"
STOPPING_SHAPE_REDESIGN_POPULATION_VERSION = "finance_stopping_shape_redesign_population.v1"
STOPPING_SHAPE_REDESIGN_AUDIT_VERSION = "finance_stopping_shape_redesign_static_audit.v1"
STOPPING_SHAPE_REDESIGN_EXPERIMENT_LABEL = "finance_v25_37_stopping_shape_redesign_development"

TASKS_PER_STRATUM = 2
TASKS_PER_SHAPE = len(STRUCTURAL_STRATA) * TASKS_PER_STRATUM
EXPECTED_TASK_COUNT = SHAPE_COUNT * TASKS_PER_SHAPE
REPLICAS = 8
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * REPLICAS

FROZEN_POSITIVE_CONTROLS = frozenset(
    {
        "authority_coverage_gap",
        "contextual_resolution_choice",
        "verified_extra_call_error_risk",
    }
)
REDESIGNED_FAILURE_SHAPES = frozenset(
    {
        "partial_required_evidence",
        "single_dimension_conflict",
        "verified_extra_call_cost",
    }
)
ALL_SHAPES = FROZEN_POSITIVE_CONTROLS | REDESIGNED_FAILURE_SHAPES


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoppingShapeRedesignThresholds(FrozenModel):
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
    bootstrap_seed: int = 20260817

    @model_validator(mode="after")
    def validate_thresholds(self) -> StoppingShapeRedesignThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("Stopping Shape redesign boundary interval is empty")
        return self


class StoppingShapeRedesignDesign(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    early_stop_consequence: str = Field(min_length=1)
    source_spec_id: str = Field(min_length=1)
    source_spec_hash: str = Field(min_length=1)
    source_result_admitted: bool
    design_status: Literal["frozen_positive_control", "redesigned_failure_shape"]
    spec: CapabilitySubmechanismSpec
    intervention_kind: SubmechanismKind
    decision_contract: FinanceStoppingShapeDecisionContract | None = None
    expected_task_instances: Literal[8] = 8

    @model_validator(mode="after")
    def validate_design(self) -> StoppingShapeRedesignDesign:
        if self.shape_id not in ALL_SHAPES:
            raise ValueError("Stopping Shape redesign contains an unknown Shape")
        if self.spec.runtime_contract.intervention_kind != self.intervention_kind:
            raise ValueError("Stopping Shape redesign Runtime kind differs from its spec")
        if self.spec.runtime_contract.implementation_status != (
            "host_and_materializer_implemented"
        ):
            raise ValueError("Stopping Shape redesign lacks an implemented Runtime")
        if self.shape_id in FROZEN_POSITIVE_CONTROLS:
            valid = (
                self.source_result_admitted
                and self.design_status == "frozen_positive_control"
                and self.decision_contract is None
            )
        else:
            expected_contract = {
                "partial_required_evidence": "partial_evidence_count_only",
                "single_dimension_conflict": "single_conflict_two_action_one_step",
                "verified_extra_call_cost": "standardized_relative_extra_call_cost",
            }[self.shape_id]
            valid = (
                not self.source_result_admitted
                and self.design_status == "redesigned_failure_shape"
                and self.decision_contract is not None
                and self.decision_contract.contract_kind == expected_contract
            )
        if not valid:
            raise ValueError("Stopping Shape redesign status or decision contract is invalid")
        return self


class FinanceStoppingShapeRedesignProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_37_stopping_shape_redesign_development"] = (
        "finance_v25_37_stopping_shape_redesign_development"
    )
    source_v25_36_protocol: FrozenArtifactReference
    source_v25_36_population: FrozenArtifactReference
    source_v25_36_contract: FrozenArtifactReference
    source_v25_36_report: FrozenArtifactReference
    source_finance_artifacts: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=34)
    shape_designs: tuple[StoppingShapeRedesignDesign, ...] = Field(
        min_length=SHAPE_COUNT, max_length=SHAPE_COUNT
    )
    structural_strata: tuple[tuple[str, str, DifficultyTier], ...] = STRUCTURAL_STRATA
    thresholds: StoppingShapeRedesignThresholds = Field(
        default_factory=StoppingShapeRedesignThresholds
    )
    tasks_per_stratum: Literal[2] = 2
    tasks_per_shape: Literal[8] = 8
    task_count: Literal[48] = 48
    replicas: Literal[8] = 8
    rollout_count: Literal[384] = 384
    task_instance_is_primary_sampling_unit: Literal[True] = True
    same_task_replica_increase_forbidden: Literal[True] = True
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    posthoc_task_selection_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    positive_controls_may_be_tuned: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["stopping_shape_redesign_population_build"] = (
        "stopping_shape_redesign_population_build"
    )
    schema_version: str = STOPPING_SHAPE_REDESIGN_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingShapeRedesignProtocol:
        if self.structural_strata != STRUCTURAL_STRATA:
            raise ValueError("Stopping Shape redesign structural strata changed")
        if {item.shape_id for item in self.shape_designs} != ALL_SHAPES:
            raise ValueError("Stopping Shape redesign coverage is incomplete")
        if len({item.intervention_kind for item in self.shape_designs}) != SHAPE_COUNT:
            raise ValueError("Stopping Shape redesign Runtime kinds are duplicated")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Stopping Shape redesign historical populations are duplicated")
        if self.source_v25_36_population.artifact_id not in {
            item.artifact_id for item in self.historical_population_references
        }:
            raise ValueError("v25.36 Population is absent from the freshness exclusion set")
        if self.protocol_id != stopping_shape_redesign_protocol_id(self):
            raise ValueError("Stopping Shape redesign protocol identity is invalid")
        return self


class StoppingShapeRedesignStaticAudit(FrozenModel):
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
    within_population_evidence_disjoint: bool
    historical_task_disjoint: bool
    historical_evidence_disjoint: bool
    historical_evidence_version_disjoint: bool
    historical_semantic_signature_disjoint: bool
    historical_materializer_disjoint: bool
    frozen_positive_controls_unchanged: bool
    failed_shapes_only_redesigned: bool
    exact_shape_stratum_redundancy: bool
    task_expected_host_events_frozen_pre_api: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_stopping_shape_redesign_development",
        "stopping_shape_redesign_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_REDESIGN_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingShapeRedesignStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Stopping Shape redesign static decision is inconsistent")
        expected_stage = (
            "flash_stopping_shape_redesign_development"
            if expected
            else "stopping_shape_redesign_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping Shape redesign transition is not fail-closed")
        if self.audit_id != stopping_shape_redesign_static_audit_id(self):
            raise ValueError("Stopping Shape redesign audit identity is invalid")
        return self


class FinanceStoppingShapeRedesignPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_path: str = Field(min_length=1)
    protocol_sha256: str = Field(min_length=64, max_length=64)
    protocol_id: str = Field(min_length=1)
    tasks: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_stratum_instance_indices: dict[str, int]
    task_design_statuses: dict[str, Literal["frozen_positive_control", "redesigned_failure_shape"]]
    task_expected_host_events: dict[str, tuple[str, str]]
    static_audit: StoppingShapeRedesignStaticAudit
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
        "flash_stopping_shape_redesign_development",
        "stopping_shape_redesign_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_REDESIGN_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingShapeRedesignPopulation:
        task_ids = {item.artifact.artifact_id for item in self.tasks}
        if any(
            set(mapping) != task_ids
            for mapping in (
                self.task_stratum_instance_indices,
                self.task_design_statuses,
                self.task_expected_host_events,
            )
        ):
            raise ValueError("Stopping Shape redesign task maps are incomplete")
        if set(self.task_stratum_instance_indices.values()) != {0, 1}:
            raise ValueError("Stopping Shape redesign lacks both stratum instances")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("Stopping Shape redesign population differs from its audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_shape_redesign_population_implementation:",
        ):
            raise ValueError("Stopping Shape redesign implementation identity is invalid")
        if self.population_id != stopping_shape_redesign_population_id(self):
            raise ValueError("Stopping Shape redesign population identity is invalid")
        return self


def stopping_shape_redesign_protocol_id(
    value: FinanceStoppingShapeRedesignProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_stopping_shape_redesign_protocol:",
    )


def stopping_shape_redesign_static_audit_id(
    value: StoppingShapeRedesignStaticAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_stopping_shape_redesign_static_audit:",
    )


def stopping_shape_redesign_population_id(
    value: FinanceStoppingShapeRedesignPopulation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_stopping_shape_redesign_population:",
    )


def prepare_stopping_shape_redesign_protocol(
    *,
    source_protocol_path: Path,
    source_population_path: Path,
    source_contract_path: Path,
    source_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingShapeRedesignProtocol:
    if output_path.exists():
        raise ValueError("Stopping Shape redesign protocol is immutable")
    paths = tuple(
        path.resolve()
        for path in (
            source_protocol_path,
            source_population_path,
            source_contract_path,
            source_report_path,
        )
    )
    source_protocol = FinanceStoppingShapeStabilityProtocol.model_validate_json(
        paths[0].read_text(encoding="utf-8")
    )
    source_population = FinanceStoppingShapePopulation.model_validate_json(
        paths[1].read_text(encoding="utf-8")
    )
    source_contract = FinanceStoppingShapeStabilityContract.model_validate_json(
        paths[2].read_text(encoding="utf-8")
    )
    source_report = FinanceStoppingShapeStabilityReport.model_validate_json(
        paths[3].read_text(encoding="utf-8")
    )
    if not (
        source_population.protocol_id == source_protocol.protocol_id
        and source_contract.source_protocol.artifact_id == source_protocol.protocol_id
        and source_contract.source_population.artifact_id == source_population.population_id
        and source_report.contract_id == source_contract.contract_id
    ):
        raise ValueError("v25.36 Stopping Shape lineage is inconsistent")
    if not (
        source_report.runtime_measurement_ready
        and not source_report.all_shapes_admitted
        and not source_report.difficulty_policy_frozen
        and not source_report.fresh_cross_population_preparation_authorized
        and source_report.next_permitted_stage == "stopping_shape_support_redesign_only"
    ):
        raise ValueError("v25.36 did not authorize Shape redesign")
    admitted = {item.shape_id for item in source_report.shape_results if item.admitted}
    failed = {item.shape_id for item in source_report.shape_results if not item.admitted}
    if admitted != FROZEN_POSITIVE_CONTROLS or failed != REDESIGNED_FAILURE_SHAPES:
        raise ValueError("v25.36 Shape decisions differ from the pre-registered redesign")
    result_by_shape = {item.shape_id: item for item in source_report.shape_results}
    designs = tuple(
        _make_redesign_design(item, result_by_shape[item.shape_id].admitted)
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
        raise ValueError("v25.37 historical exclusion set contains a duplicate")
    values = {
        "run_id": run_id,
        "source_v25_36_protocol": _reference(paths[0], source_protocol.protocol_id),
        "source_v25_36_population": _reference(paths[1], source_population.population_id),
        "source_v25_36_contract": _reference(paths[2], source_contract.contract_id),
        "source_v25_36_report": _reference(paths[3], source_report.report_id),
        "source_finance_artifacts": source_protocol.source_finance_artifacts,
        "source_calibration_contract": source_protocol.source_calibration_contract,
        "historical_population_references": historical,
        "shape_designs": designs,
    }
    provisional = FinanceStoppingShapeRedesignProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceStoppingShapeRedesignProtocol(
        protocol_id=stopping_shape_redesign_protocol_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    return protocol


def build_stopping_shape_redesign_population(
    *,
    protocol_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceStoppingShapeRedesignPopulation:
    output_path = output_dir / "finance_stopping_shape_redesign_population.json"
    if output_path.exists():
        raise ValueError("Stopping Shape redesign population is immutable")
    protocol_path = protocol_path.resolve()
    protocol = FinanceStoppingShapeRedesignProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    excluded = _collect_excluded_identities(protocol.historical_population_references)
    pool = _load_evidence_pool(Path(protocol.source_finance_artifacts.path))
    builder = _CapabilityTaskBuilder(pool, sampling_salt=f"{run_id}:stopping-shape-redesign")
    used_ids = set(excluded["evidence_id"])
    used_versions = set(excluded["evidence_version_id"])
    tasks: list[StoppingShapeTask] = []
    instance_indices: dict[str, int] = {}
    statuses: dict[str, Literal["frozen_positive_control", "redesigned_failure_shape"]] = {}
    for design in protocol.shape_designs:
        for stratum_id, family, tier in protocol.structural_strata:
            for instance_index in range(TASKS_PER_STRATUM):
                task = _materialize_redesign_task(
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
                    raise ValueError("Stopping Shape redesign reused a historical task")
                if task.source_semantic_signature in excluded["source_semantic_signature"]:
                    raise ValueError("Stopping Shape redesign reused historical semantics")
                if task.materializer_hash in excluded["materializer_hash"]:
                    raise ValueError("Stopping Shape redesign reused a historical materializer")
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
    audit = make_stopping_shape_redesign_static_audit(
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
            prefix="finance_stopping_shape_redesign_population_implementation:",
        ),
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = FinanceStoppingShapeRedesignPopulation.model_construct(
        population_id="pending", **values
    )
    population = FinanceStoppingShapeRedesignPopulation(
        population_id=stopping_shape_redesign_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_shape_redesign_static_audit.json",
        audit.model_dump(mode="json"),
    )
    (output_dir / "finance_stopping_shape_redesign_population_report.md").write_text(
        _render_population_report(population), encoding="utf-8"
    )
    return population


def make_stopping_shape_redesign_static_audit(
    tasks: Sequence[StoppingShapeTask],
    protocol: FinanceStoppingShapeRedesignProtocol,
    *,
    excluded: Mapping[str, set[str]],
    task_stratum_instance_indices: Mapping[str, int],
    task_design_statuses: Mapping[
        str, Literal["frozen_positive_control", "redesigned_failure_shape"]
    ],
    task_expected_host_events: Mapping[str, tuple[str, str]],
) -> StoppingShapeRedesignStaticAudit:
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
    controls_unchanged = all(
        item.scenario.stopping_shape_decision_contract is None
        and item.shape_id in FROZEN_POSITIVE_CONTROLS
        for item in tasks
        if item.shape_id in FROZEN_POSITIVE_CONTROLS
    )
    failed_only_redesigned = all(
        (
            item.scenario.stopping_shape_decision_contract is not None
            and item.shape_id in REDESIGNED_FAILURE_SHAPES
        )
        == (item.shape_id in REDESIGNED_FAILURE_SHAPES)
        for item in tasks
    )
    public_contract = {
        item.artifact.artifact_id: _public_decision_contract_matches(
            item, design_by_shape[item.shape_id]
        )
        for item in tasks
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
        "positive_controls_unchanged": controls_unchanged,
        "failed_shapes_only_redesigned": failed_only_redesigned,
        "design_statuses": set(task_design_statuses) == task_ids
        and all(
            task_design_statuses[item.artifact.artifact_id]
            == design_by_shape[item.shape_id].design_status
            for item in tasks
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
        "within_population_evidence_disjoint": checks["within_evidence_disjoint"],
        "historical_task_disjoint": checks["historical_task_disjoint"],
        "historical_evidence_disjoint": checks["historical_evidence_disjoint"],
        "historical_evidence_version_disjoint": checks["historical_version_disjoint"],
        "historical_semantic_signature_disjoint": checks["historical_semantic_disjoint"],
        "historical_materializer_disjoint": checks["historical_materializer_disjoint"],
        "frozen_positive_controls_unchanged": controls_unchanged,
        "failed_shapes_only_redesigned": failed_only_redesigned,
        "exact_shape_stratum_redundancy": checks["shape_stratum_redundancy"],
        "task_expected_host_events_frozen_pre_api": checks["host_events_frozen_pre_api"],
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_stopping_shape_redesign_development"
            if not rejections
            else "stopping_shape_redesign_population_repair_only"
        ),
    }
    provisional = StoppingShapeRedesignStaticAudit.model_construct(audit_id="pending", **values)
    return StoppingShapeRedesignStaticAudit(
        audit_id=stopping_shape_redesign_static_audit_id(provisional), **values
    )


def _make_redesign_design(
    source: Any,
    source_result_admitted: bool,
) -> StoppingShapeRedesignDesign:
    shape_id = str(source.shape_id)
    decision = _decision_contract(shape_id)
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
    return StoppingShapeRedesignDesign(
        shape_id=shape_id,
        shape_role=source.shape_role,
        early_stop_consequence=source.early_stop_consequence,
        source_spec_id=source.source_spec_id,
        source_spec_hash=source.spec.spec_hash,
        source_result_admitted=source_result_admitted,
        design_status=(
            "frozen_positive_control"
            if shape_id in FROZEN_POSITIVE_CONTROLS
            else "redesigned_failure_shape"
        ),
        spec=spec,
        intervention_kind=cast(SubmechanismKind, spec.runtime_contract.intervention_kind),
        decision_contract=decision,
    )


def _decision_contract(
    shape_id: str,
) -> FinanceStoppingShapeDecisionContract | None:
    if shape_id in FROZEN_POSITIVE_CONTROLS:
        return None
    if shape_id == "partial_required_evidence":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="partial_evidence_count_only",
            missing_role_disclosure="count_only",
        )
    if shape_id == "single_dimension_conflict":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="single_conflict_two_action_one_step",
            conflict_dimensions=("source_definition_compatibility",),
            available_resolution_actions=(
                FinanceStoppingResolutionAction(
                    tool_id="normalize_metric_unit_period",
                    applicable_when=("source_definition_compatibility is conflicting"),
                ),
                FinanceStoppingResolutionAction(
                    tool_id="open_document",
                    applicable_when="source authority or provenance is unresolved",
                ),
            ),
            resolution_step_count=1,
        )
    if shape_id == "verified_extra_call_cost":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="standardized_relative_extra_call_cost",
            remaining_call_budget_fraction=0.25,
            remaining_token_budget_fraction=0.20,
            terminal_utility_loss=1.0,
        )
    raise ValueError(f"Stopping Shape has no redesign contract: {shape_id}")


def _materialize_redesign_task(
    *,
    builder: _CapabilityTaskBuilder,
    design: StoppingShapeRedesignDesign,
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
        gold_ids = {item.evidence_id for item in gold}
        gold_versions = {item.evidence_version_id for item in gold}
        if gold_ids & used_ids or gold_versions & used_versions:
            continue
        distractor = _select_distractor(
            spec,
            gold,
            evidence_pool,
            used_ids | gold_ids,
            used_versions | gold_versions,
            sampling_salt,
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
        base_scenario = _make_scenario(
            spec,
            gold,
            distractor,
            artifact.projected_expected_output,
        )
        scenario = base_scenario
        if design.decision_contract is not None:
            scenario = make_finance_submechanism_scenario(
                submechanism_id=base_scenario.submechanism_id,
                parent_mechanism_id=base_scenario.parent_mechanism_id,
                intervention_kind=base_scenario.intervention_kind,
                expected_host_events=base_scenario.expected_host_events,
                evidence_roles=base_scenario.evidence_roles,
                public_resolution_hint=_redesign_resolution_hint(design.shape_id),
                untrusted_candidate=base_scenario.untrusted_candidate,
                canonical_candidate=base_scenario.canonical_candidate,
                repair_target_field=base_scenario.repair_target_field,
                stopping_shape_decision_contract=design.decision_contract,
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
                "decision_contract": design.decision_contract,
            },
            prefix="finance_stopping_shape_redesign_semantics:",
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
            prefix="finance_stopping_shape_redesign_materializer:",
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
        "real Finance Evidence cannot support Stopping Shape redesign "
        f"{design.shape_id}/{stratum_id}/{instance_index}"
    )


def _redesign_resolution_hint(shape_id: str) -> str:
    hints = {
        "partial_required_evidence": (
            "The public completion state discloses counts only. Infer the unresolved "
            "evidence role from the task, retrieve it, and verify before finalizing."
        ),
        "single_dimension_conflict": (
            "One explicit source-definition compatibility conflict is present. Choose "
            "between the two public actions by matching their applicable_when condition."
        ),
        "verified_extra_call_cost": (
            "The result is verified complete. Any additional call consumes the frozen "
            "relative call and token budget and forfeits terminal utility."
        ),
    }
    return hints[shape_id]


def _public_decision_contract_matches(
    task: StoppingShapeTask,
    design: StoppingShapeRedesignDesign,
) -> bool:
    metadata = task.artifact.task.public.metadata
    parent = metadata.get(PUBLIC_SUBMECHANISM_METADATA_KEY)
    if not isinstance(parent, Mapping):
        return False
    observed = parent.get("stopping_shape_decision_contract")
    decision = design.decision_contract
    if decision is None:
        return observed is None
    expected = decision.model_dump(mode="json", exclude={"contract_kind"})
    expected["internal_shape_identity_disclosed"] = False
    text = json.dumps(
        task.artifact.task.public.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        observed == expected
        and "contract_kind" not in _mapping_keys(task.artifact.task.public.model_dump(mode="json"))
        and decision.contract_kind not in text
        and design.design_status not in text
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
    protocol: FinanceStoppingShapeRedesignProtocol,
) -> None:
    references = (
        protocol.source_v25_36_protocol,
        protocol.source_v25_36_population,
        protocol.source_v25_36_contract,
        protocol.source_v25_36_report,
        protocol.source_finance_artifacts,
        protocol.source_calibration_contract,
        *protocol.historical_population_references,
    )
    for reference in references:
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"frozen Stopping Shape redesign input changed: {reference.path}")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_population.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_redesign_protocol.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _render_population_report(
    population: FinanceStoppingShapeRedesignPopulation,
) -> str:
    lines = [
        "# Finance v25.37 Stopping Shape Redesign Population",
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
    parser = argparse.ArgumentParser(description="Prepare or build v25.37 Stopping Shape Redesign")
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
        protocol = prepare_stopping_shape_redesign_protocol(
            source_protocol_path=args.source_protocol,
            source_population_path=args.source_population,
            source_contract_path=args.source_contract,
            source_report_path=args.source_report,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(protocol.model_dump_json(indent=2))
    else:
        population = build_stopping_shape_redesign_population(
            protocol_path=args.protocol,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        print(population.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
