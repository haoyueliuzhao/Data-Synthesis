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
    FINANCE_SUBMECHANISM_ORACLE_KEY,
    FinanceSubmechanismScenario,
    SubmechanismKind,
    submechanism_policy_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _candidate_iterator,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
    CapabilitySubmechanismSpec,
    _spec,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    _RECOVERY_BRANCH_KINDS,
    SubmechanismRuntimeReplay,
    _answer_contract_ready,
    _freeze_scenario,
    _make_scenario,
    _select_distractor,
    replay_submechanism_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_cross_population_stable_protocol import (  # noqa: E501
    FinanceCrossPopulationStableProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_cross_population_stable_support import (  # noqa: E501
    FinanceCrossPopulationStableContract,
    FinanceCrossPopulationStableReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    estimate_stable_subspace,
    principal_angles_degrees,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (  # noqa: E501
    _stable_rows,
)
from trusted_synthesis.hashing import canonical_hash

STOPPING_SHAPE_PROTOCOL_VERSION = "finance_stopping_shape_stability_protocol.v1"
STOPPING_SHAPE_POPULATION_VERSION = "finance_stopping_shape_population.v1"
STOPPING_SHAPE_TASK_VERSION = "finance_stopping_shape_task.v1"
STOPPING_SHAPE_AUDIT_VERSION = "finance_stopping_shape_static_audit.v1"
STOPPING_SHAPE_DIAGNOSTIC_VERSION = "finance_v25_35_sensitivity_diagnostic.v1"
STOPPING_SHAPE_EXPERIMENT_LABEL = "finance_v25_36_stopping_shape_stability_development"

STOPPING_PARENT_ID = "finance.state_dependent_control_and_stopping"
SHAPE_TASKS = 4
SHAPE_COUNT = 6
EXPECTED_TASK_COUNT = SHAPE_COUNT * SHAPE_TASKS
REPLICAS = 8
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * REPLICAS

STRUCTURAL_STRATA: tuple[tuple[str, str, DifficultyTier], ...] = (
    (
        "retrieval_join_frontier",
        "finance.multi_hop_retrieval_join",
        DifficultyTier.FRONTIER,
    ),
    (
        "calculation_chain_frontier",
        "finance.calculation_chain",
        DifficultyTier.FRONTIER,
    ),
    (
        "definition_reconciliation_frontier",
        "finance.definition_reconciliation",
        DifficultyTier.FRONTIER,
    ),
    (
        "verification_selection_frontier",
        "finance.verification_sensitive_selection",
        DifficultyTier.FRONTIER,
    ),
)

SHAPE_SOURCES: tuple[tuple[str, str, str, str], ...] = (
    (
        "partial_required_evidence",
        f"{STOPPING_PARENT_ID}.incomplete_continue",
        "boundary_candidate",
        "stopping before all required Evidence is retrieved invalidates the answer",
    ),
    (
        "authority_coverage_gap",
        f"{STOPPING_PARENT_ID}.uncertain_source_coverage",
        "boundary_candidate",
        "stopping before provenance inspection leaves source authority unresolved",
    ),
    (
        "single_dimension_conflict",
        "finance.cross_family_failure_recovery.evidence_conflict",
        "boundary_candidate",
        "stopping before one definition conflict is normalized invalidates comparison",
    ),
    (
        "contextual_resolution_choice",
        f"{STOPPING_PARENT_ID}.unresolved_conflict_cannot_stop",
        "boundary_candidate",
        "stopping before selecting the applicable public resolution action preserves conflict",
    ),
    (
        "verified_extra_call_error_risk",
        f"{STOPPING_PARENT_ID}.post_complete_error_risk",
        "runtime_control",
        "continuing after verified completion introduces an asymmetric integrity risk",
    ),
    (
        "verified_extra_call_cost",
        f"{STOPPING_PARENT_ID}.post_complete_cost",
        "runtime_control",
        "continuing after verified completion incurs a positive marginal cost",
    ),
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrozenArtifactReference(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    artifact_id: str = Field(min_length=1)


class StoppingShapeThresholds(FrozenModel):
    boundary_probability_lower: float = Field(default=0.125, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.875, ge=0, le=1)
    minimum_boundary_tasks_per_candidate_shape: int = Field(default=2, ge=1, le=4)
    minimum_nonzero_tasks_per_candidate_shape: int = Field(default=3, ge=1, le=4)
    minimum_effective_task_count: float = Field(default=2.0, ge=1, le=4)
    maximum_single_task_information_share: float = Field(default=0.60, gt=0, le=1)
    maximum_between_task_probability_range: float = Field(default=0.75, ge=0, le=1)
    minimum_control_shape_success_rate: float = Field(default=0.75, ge=0, le=1)
    minimum_runtime_execution_integrity: float = Field(default=1.0, ge=1, le=1)
    minimum_terminal_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=1, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_l0_l2_failure_count: int = Field(default=0, ge=0, le=0)
    bootstrap_replicates: int = Field(default=2_000, ge=500)
    bootstrap_seed: int = 20260816

    @model_validator(mode="after")
    def validate_thresholds(self) -> StoppingShapeThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("Stopping shape boundary interval is empty")
        return self


class StoppingShapeDesign(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    early_stop_consequence: str = Field(min_length=1)
    source_spec_id: str = Field(min_length=1)
    spec: CapabilitySubmechanismSpec
    intervention_kind: SubmechanismKind
    expected_task_instances: Literal[4] = 4

    @model_validator(mode="after")
    def validate_design(self) -> StoppingShapeDesign:
        if self.spec.parent_mechanism_id != STOPPING_PARENT_ID:
            raise ValueError("Stopping shape spec belongs to another parent")
        if self.spec.runtime_contract.intervention_kind != self.intervention_kind:
            raise ValueError("Stopping shape Runtime kind differs from its spec")
        if self.spec.runtime_contract.implementation_status != "host_and_materializer_implemented":
            raise ValueError("Stopping shape lacks implemented Host and materializer")
        return self


class ParentSensitivityRow(FrozenModel):
    parent_mechanism_id: str = Field(min_length=1)
    information_share: float = Field(ge=0, le=1)
    leave_one_parent_maximum_angle_degrees: float = Field(ge=0, le=90)


class TaskSensitivityRow(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    probability: float = Field(ge=0, le=1)
    fisher_weight: float = Field(ge=0, le=0.25)
    leave_one_task_maximum_angle_degrees: float = Field(ge=0, le=90)


class PopulationSensitivityRow(FrozenModel):
    population_id: str = Field(min_length=1)
    parent_rows: tuple[ParentSensitivityRow, ...] = Field(min_length=4, max_length=4)
    dominant_task_rows: tuple[TaskSensitivityRow, ...] = Field(min_length=1)
    maximum_non_stopping_parent_rotation_degrees: float = Field(ge=0, le=90)
    maximum_single_task_rotation_degrees: float = Field(ge=0, le=90)


class SourceSensitivityDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    population_rows: tuple[PopulationSensitivityRow, ...] = Field(min_length=3, max_length=3)
    stopping_only_explanation_rejected: bool
    single_task_dominance_observed: bool
    pooled_rescue_forbidden: Literal[True] = True
    schema_version: str = STOPPING_SHAPE_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> SourceSensitivityDiagnostic:
        if self.stopping_only_explanation_rejected != any(
            item.maximum_non_stopping_parent_rotation_degrees > 45.0
            for item in self.population_rows
        ):
            raise ValueError("Stopping-only sensitivity conclusion is inconsistent")
        if self.single_task_dominance_observed != any(
            item.maximum_single_task_rotation_degrees > 45.0 for item in self.population_rows
        ):
            raise ValueError("single-task sensitivity conclusion is inconsistent")
        if self.diagnostic_id != source_sensitivity_diagnostic_id(self):
            raise ValueError("source sensitivity diagnostic identity is invalid")
        return self


class FinanceStoppingShapeStabilityProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_36_stopping_shape_stability_development"] = (
        "finance_v25_36_stopping_shape_stability_development"
    )
    source_v25_35_protocol: FrozenArtifactReference
    source_v25_35_contract: FrozenArtifactReference
    source_v25_35_report: FrozenArtifactReference
    source_v25_35_behaviors: FrozenArtifactReference
    source_direction_report: FrozenArtifactReference
    source_finance_artifacts: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=33)
    source_sensitivity_diagnostic: SourceSensitivityDiagnostic
    shape_designs: tuple[StoppingShapeDesign, ...] = Field(
        min_length=SHAPE_COUNT, max_length=SHAPE_COUNT
    )
    structural_strata: tuple[tuple[str, str, DifficultyTier], ...] = STRUCTURAL_STRATA
    thresholds: StoppingShapeThresholds = Field(default_factory=StoppingShapeThresholds)
    tasks_per_shape: Literal[4] = 4
    task_count: Literal[24] = 24
    replicas: Literal[8] = 8
    rollout_count: Literal[192] = 192
    task_instance_sampling_unit: Literal["independent_finance_task"] = "independent_finance_task"
    same_task_replica_increase_forbidden: Literal[True] = True
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    posthoc_task_selection_authorized: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["stopping_shape_population_build"] = (
        "stopping_shape_population_build"
    )
    schema_version: str = STOPPING_SHAPE_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingShapeStabilityProtocol:
        if self.structural_strata != STRUCTURAL_STRATA:
            raise ValueError("Stopping shape structural strata changed")
        if len({item.shape_id for item in self.shape_designs}) != SHAPE_COUNT:
            raise ValueError("Stopping shape identities are duplicated")
        if len({item.intervention_kind for item in self.shape_designs}) != SHAPE_COUNT:
            raise ValueError("Stopping shape Runtime kinds are not structurally distinct")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Stopping shape historical populations are duplicated")
        if self.protocol_id != stopping_shape_protocol_id(self):
            raise ValueError("Stopping shape protocol identity is invalid")
        return self


class StoppingShapeDifficultyVector(FrozenModel):
    underlying_family: str = Field(min_length=1)
    tier: DifficultyTier
    program_node_count: int = Field(ge=1)
    program_depth: int = Field(ge=1)
    required_evidence_count: int = Field(ge=1)
    public_corpus_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    metric_count: int = Field(ge=1)
    period_count: int = Field(ge=1)
    resolution_action_count: int = Field(ge=0)
    resolution_chain_length: int = Field(ge=0)
    distractor_count: int = Field(ge=0)
    early_stop_consequence: str = Field(min_length=1)


class StoppingShapeTask(FrozenModel):
    task_record_id: str = Field(min_length=1)
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    stratum_id: str = Field(min_length=1)
    spec_hash: str = Field(min_length=1)
    artifact: CapabilitySensitiveTaskArtifact
    scenario: FinanceSubmechanismScenario
    runtime_replay: SubmechanismRuntimeReplay
    difficulty: StoppingShapeDifficultyVector
    source_semantic_signature: str = Field(min_length=1)
    materializer_hash: str = Field(min_length=1)
    schema_version: str = STOPPING_SHAPE_TASK_VERSION

    @model_validator(mode="after")
    def validate_task(self) -> StoppingShapeTask:
        if self.artifact.family != self.difficulty.underlying_family:
            raise ValueError("Stopping shape family differs from difficulty vector")
        if self.artifact.tier != self.difficulty.tier:
            raise ValueError("Stopping shape tier differs from difficulty vector")
        frozen = self.artifact.task.oracle.selection_contract.get(FINANCE_SUBMECHANISM_ORACLE_KEY)
        if frozen != self.scenario.model_dump(mode="json"):
            raise ValueError("Stopping shape task did not freeze its Runtime scenario")
        if not self.runtime_replay.passed or not self.artifact.verification.passed:
            raise ValueError("Stopping shape task lacks deterministic replay")
        if not _answer_contract_ready(self.artifact):
            raise ValueError("Stopping shape task lacks answer projection contract")
        if not _public_task_isolated(self):
            raise ValueError("Stopping shape task leaks Oracle or mechanism identity")
        if self.task_record_id != stopping_shape_task_id(self):
            raise ValueError("Stopping shape task identity is invalid")
        return self


class StoppingShapeStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: int = Field(ge=1)
    shape_task_counts: dict[str, int]
    stratum_task_counts: dict[str, int]
    intervention_kind_count: int = Field(ge=1)
    operation_replay_rate: float = Field(ge=0, le=1)
    host_replay_rate: float = Field(ge=0, le=1)
    public_oracle_isolation_rate: float = Field(ge=0, le=1)
    answer_contract_rate: float = Field(ge=0, le=1)
    within_population_evidence_disjoint: bool
    historical_evidence_disjoint: bool
    historical_evidence_version_disjoint: bool
    historical_semantic_signature_disjoint: bool
    historical_materializer_disjoint: bool
    distinct_task_instance_count: int = Field(ge=1)
    task_expected_host_events_frozen_pre_api: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_stopping_shape_development",
        "stopping_shape_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingShapeStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Stopping shape static decision is inconsistent")
        stage = (
            "flash_stopping_shape_development"
            if expected
            else "stopping_shape_population_repair_only"
        )
        if self.next_permitted_stage != stage:
            raise ValueError("Stopping shape static transition is not fail-closed")
        if self.audit_id != stopping_shape_static_audit_id(self):
            raise ValueError("Stopping shape static audit identity is invalid")
        return self


class FinanceStoppingShapePopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_path: str = Field(min_length=1)
    protocol_sha256: str = Field(min_length=64, max_length=64)
    protocol_id: str = Field(min_length=1)
    tasks: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_expected_host_events: dict[str, tuple[str, str]]
    static_audit: StoppingShapeStaticAudit
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
        "flash_stopping_shape_development",
        "stopping_shape_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingShapePopulation:
        task_ids = {item.artifact.artifact_id for item in self.tasks}
        if set(self.task_expected_host_events) != task_ids:
            raise ValueError("Stopping shape Host-event projection is incomplete")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("Stopping shape population transition differs from audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_shape_population_implementation:",
        ):
            raise ValueError("Stopping shape implementation identity is invalid")
        if self.population_id != stopping_shape_population_id(self):
            raise ValueError("Stopping shape population identity is invalid")
        return self


def source_sensitivity_diagnostic_id(value: SourceSensitivityDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v25_35_sensitivity_diagnostic:",
    )


def stopping_shape_protocol_id(value: FinanceStoppingShapeStabilityProtocol) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_stopping_shape_stability_protocol:",
    )


def stopping_shape_task_id(value: StoppingShapeTask) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"task_record_id"}),
        prefix="finance_stopping_shape_task:",
    )


def stopping_shape_static_audit_id(value: StoppingShapeStaticAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_stopping_shape_static_audit:",
    )


def stopping_shape_population_id(value: FinanceStoppingShapePopulation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_stopping_shape_population:",
    )


def prepare_stopping_shape_protocol(
    *,
    source_v25_35_protocol_path: Path,
    source_v25_35_contract_path: Path,
    source_v25_35_report_path: Path,
    source_v25_35_behaviors_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStoppingShapeStabilityProtocol:
    if output_path.exists():
        raise ValueError("Stopping shape protocol is immutable")
    paths = tuple(
        item.resolve()
        for item in (
            source_v25_35_protocol_path,
            source_v25_35_contract_path,
            source_v25_35_report_path,
            source_v25_35_behaviors_path,
        )
    )
    source_protocol = FinanceCrossPopulationStableProtocol.model_validate_json(
        paths[0].read_text(encoding="utf-8")
    )
    source_contract = FinanceCrossPopulationStableContract.model_validate_json(
        paths[1].read_text(encoding="utf-8")
    )
    source_report = FinanceCrossPopulationStableReport.model_validate_json(
        paths[2].read_text(encoding="utf-8")
    )
    if source_report.contract_id != source_contract.contract_id:
        raise ValueError("v25.35 report and contract lineage differ")
    if not (
        source_report.all_population_runtime_ready
        and not source_report.development_admitted
        and not source_report.fresh_confirmation_preparation_authorized
        and source_report.next_permitted_stage == "stable_support_redesign_only"
    ):
        raise ValueError("v25.35 did not authorize stable-support redesign")
    direction_path = Path(source_contract.population_references[0].path)
    first_population = json.loads(direction_path.read_text(encoding="utf-8"))
    direction_source = Path(str(first_population["source_direction_report_path"])).resolve()
    artifacts_source = Path(str(first_population["source_artifacts_path"])).resolve()
    calibration_source = Path(source_contract.source_calibration_contract.path).resolve()
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        direction_source.read_text(encoding="utf-8")
    )
    designs = _make_shape_designs(direction)
    historical = _historical_references(source_protocol, source_contract)
    diagnostic = _make_source_sensitivity_diagnostic(
        source_contract,
        Path(paths[3]),
    )
    values = {
        "run_id": run_id,
        "source_v25_35_protocol": _reference(paths[0], source_protocol.protocol_id),
        "source_v25_35_contract": _reference(paths[1], source_contract.contract_id),
        "source_v25_35_report": _reference(paths[2], source_report.report_id),
        "source_v25_35_behaviors": _reference(
            paths[3],
            canonical_hash(_sha256(paths[3]), prefix="finance_v25_35_behavior_artifact:"),
        ),
        "source_direction_report": _reference(direction_source, direction.report_id),
        "source_finance_artifacts": _reference(
            artifacts_source,
            canonical_hash(_sha256(artifacts_source), prefix="finance_evidence_union_artifact:"),
        ),
        "source_calibration_contract": _reference(
            calibration_source, source_contract.source_calibration_contract.artifact_id
        ),
        "historical_population_references": historical,
        "source_sensitivity_diagnostic": diagnostic,
        "shape_designs": designs,
    }
    provisional = FinanceStoppingShapeStabilityProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceStoppingShapeStabilityProtocol(
        protocol_id=stopping_shape_protocol_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    _write_json(
        output_path.with_name("finance_v25_35_sensitivity_diagnostic.json"),
        diagnostic.model_dump(mode="json"),
    )
    return protocol


def build_stopping_shape_population(
    *,
    protocol_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceStoppingShapePopulation:
    output_path = output_dir / "finance_stopping_shape_population.json"
    if output_path.exists():
        raise ValueError("Stopping shape population is immutable")
    protocol_path = protocol_path.resolve()
    protocol = FinanceStoppingShapeStabilityProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    excluded = _collect_excluded_identities(protocol.historical_population_references)
    pool = _load_evidence_pool(Path(protocol.source_finance_artifacts.path))
    builder = _CapabilityTaskBuilder(pool, sampling_salt=f"{run_id}:stopping-shape")
    used_ids = set(excluded["evidence_id"])
    used_versions = set(excluded["evidence_version_id"])
    tasks: list[StoppingShapeTask] = []
    for design in protocol.shape_designs:
        for stratum_id, family, tier in protocol.structural_strata:
            task = _materialize_shape_task(
                builder=builder,
                design=design,
                stratum_id=stratum_id,
                family=family,
                tier=tier,
                evidence_pool=tuple(pool.public.values()),
                used_ids=used_ids,
                used_versions=used_versions,
                sampling_salt=f"{run_id}:{design.shape_id}:{stratum_id}",
            )
            if task.source_semantic_signature in excluded["source_semantic_signature"]:
                raise ValueError("Stopping shape reused a historical semantic signature")
            if task.materializer_hash in excluded["materializer_hash"]:
                raise ValueError("Stopping shape reused a historical materializer")
            tasks.append(task)
            used_ids.update(item.evidence_id for item in task.artifact.public_corpus.evidence)
            used_versions.update(
                item.evidence_version_id for item in task.artifact.public_corpus.evidence
            )
    frozen_tasks = tuple(tasks)
    host_events = {
        item.artifact.artifact_id: item.scenario.expected_host_events for item in frozen_tasks
    }
    audit = make_stopping_shape_static_audit(
        frozen_tasks,
        protocol,
        excluded=excluded,
        task_expected_host_events=host_events,
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "protocol_path": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "protocol_id": protocol.protocol_id,
        "tasks": frozen_tasks,
        "task_expected_host_events": host_events,
        "static_audit": audit,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_shape_population_implementation:",
        ),
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = FinanceStoppingShapePopulation.model_construct(population_id="pending", **values)
    population = FinanceStoppingShapePopulation(
        population_id=stopping_shape_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_shape_static_audit.json",
        audit.model_dump(mode="json"),
    )
    (output_dir / "finance_stopping_shape_population_report.md").write_text(
        _render_population_report(population), encoding="utf-8"
    )
    return population


def make_stopping_shape_static_audit(
    tasks: Sequence[StoppingShapeTask],
    protocol: FinanceStoppingShapeStabilityProtocol,
    *,
    excluded: Mapping[str, set[str]],
    task_expected_host_events: Mapping[str, tuple[str, str]],
) -> StoppingShapeStaticAudit:
    shape_counts = Counter(item.shape_id for item in tasks)
    stratum_counts = Counter(item.stratum_id for item in tasks)
    evidence = [item for task in tasks for item in task.artifact.public_corpus.evidence]
    semantic = {item.source_semantic_signature for item in tasks}
    materializers = {item.materializer_hash for item in tasks}
    task_ids = {item.artifact.artifact_id for item in tasks}
    checks = {
        "complete_task_count": len(tasks) == EXPECTED_TASK_COUNT,
        "shape_redundancy": set(shape_counts) == {item.shape_id for item in protocol.shape_designs}
        and set(shape_counts.values()) == {SHAPE_TASKS},
        "stratum_balance": set(stratum_counts) == {item[0] for item in protocol.structural_strata}
        and set(stratum_counts.values()) == {SHAPE_COUNT},
        "distinct_runtime_kinds": len({item.scenario.intervention_kind for item in tasks})
        == SHAPE_COUNT,
        "operation_replay": all(item.artifact.verification.passed for item in tasks),
        "host_replay": all(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation": all(_public_task_isolated(item) for item in tasks),
        "answer_contract": all(_answer_contract_ready(item.artifact) for item in tasks),
        "within_evidence_disjoint": len(evidence) == len({item.evidence_id for item in evidence}),
        "historical_evidence_disjoint": not {item.evidence_id for item in evidence}
        & excluded["evidence_id"],
        "historical_version_disjoint": not {item.evidence_version_id for item in evidence}
        & excluded["evidence_version_id"],
        "historical_semantic_disjoint": not semantic & excluded["source_semantic_signature"],
        "historical_materializer_disjoint": not materializers & excluded["materializer_hash"],
        "distinct_task_instances": len(task_ids) == EXPECTED_TASK_COUNT,
        "host_events_frozen_pre_api": set(task_expected_host_events) == task_ids,
        "frontier_only": all(item.artifact.tier == DifficultyTier.FRONTIER for item in tasks),
    }
    rejections = tuple(sorted(key for key, passed in checks.items() if not passed))
    values = {
        "task_count": len(tasks),
        "shape_task_counts": dict(sorted(shape_counts.items())),
        "stratum_task_counts": dict(sorted(stratum_counts.items())),
        "intervention_kind_count": len({item.scenario.intervention_kind for item in tasks}),
        "operation_replay_rate": _rate(item.artifact.verification.passed for item in tasks),
        "host_replay_rate": _rate(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation_rate": _rate(_public_task_isolated(item) for item in tasks),
        "answer_contract_rate": _rate(_answer_contract_ready(item.artifact) for item in tasks),
        "within_population_evidence_disjoint": checks["within_evidence_disjoint"],
        "historical_evidence_disjoint": checks["historical_evidence_disjoint"],
        "historical_evidence_version_disjoint": checks["historical_version_disjoint"],
        "historical_semantic_signature_disjoint": checks["historical_semantic_disjoint"],
        "historical_materializer_disjoint": checks["historical_materializer_disjoint"],
        "distinct_task_instance_count": len(task_ids),
        "task_expected_host_events_frozen_pre_api": checks["host_events_frozen_pre_api"],
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_stopping_shape_development"
            if not rejections
            else "stopping_shape_population_repair_only"
        ),
    }
    provisional = StoppingShapeStaticAudit.model_construct(audit_id="pending", **values)
    return StoppingShapeStaticAudit(audit_id=stopping_shape_static_audit_id(provisional), **values)


def _make_shape_designs(
    direction: CapabilitySubmechanismDirectionReport,
) -> tuple[StoppingShapeDesign, ...]:
    by_id = {item.submechanism_id: item for item in direction.candidate_specs}
    designs: list[StoppingShapeDesign] = []
    for shape_id, source_id, role, consequence in SHAPE_SOURCES:
        try:
            source = by_id[source_id]
        except KeyError as exc:
            raise ValueError(f"Stopping shape source spec is missing: {source_id}") from exc
        runtime = source.runtime_contract.model_copy(
            update={
                "implementation_status": "host_and_materializer_implemented",
                "implementation_id": (
                    "finance_capability_submechanism_runtime.v10:"
                    f"{source.runtime_contract.intervention_kind}"
                ),
            }
        )
        spec = _spec(
            STOPPING_PARENT_ID,
            shape_id,
            f"Stopping: {source.title}",
            source.action_graph,
            source.evidence_dependencies,
            runtime,
            tuple(dict.fromkeys((*source.diagnostic_outcomes, "stopping"))),
        )
        designs.append(
            StoppingShapeDesign(
                shape_id=shape_id,
                shape_role=cast(Literal["boundary_candidate", "runtime_control"], role),
                early_stop_consequence=consequence,
                source_spec_id=source_id,
                spec=spec,
                intervention_kind=cast(SubmechanismKind, spec.runtime_contract.intervention_kind),
            )
        )
    return tuple(designs)


def _materialize_shape_task(
    *,
    builder: _CapabilityTaskBuilder,
    design: StoppingShapeDesign,
    stratum_id: str,
    family: str,
    tier: DifficultyTier,
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
        scenario = _make_scenario(
            spec,
            gold,
            distractor,
            artifact.projected_expected_output,
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
                "gold_versions": tuple(item.evidence_version_id for item in gold),
                "program": program,
                "projection": projection,
                "spec_hash": spec.spec_hash,
            },
            prefix="finance_stopping_shape_semantics:",
        )
        difficulty = _difficulty_vector(
            design,
            artifact,
            spec,
            family=family,
            tier=tier,
        )
        materializer_hash = canonical_hash(
            {
                "shape_id": design.shape_id,
                "stratum_id": stratum_id,
                "spec_hash": spec.spec_hash,
                "artifact_id": artifact.artifact_id,
                "scenario": scenario,
                "difficulty": difficulty,
                "policy": submechanism_policy_manifest()[scenario.intervention_kind],
            },
            prefix="finance_stopping_shape_materializer:",
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
        f"real Finance Evidence cannot support Stopping shape {design.shape_id}/{stratum_id}"
    )


def _difficulty_vector(
    design: StoppingShapeDesign,
    artifact: CapabilitySensitiveTaskArtifact,
    spec: CapabilitySubmechanismSpec,
    *,
    family: str,
    tier: DifficultyTier,
) -> StoppingShapeDifficultyVector:
    program = artifact.task.oracle.task_program
    depth: dict[str, int] = {}
    for node in program.nodes:
        depth[node.node_id] = 1 + max((depth[item] for item in node.dependencies), default=0)
    evidence = tuple(artifact.evidence_bundle.evidence)
    public_evidence = tuple(artifact.public_corpus.evidence)
    policy = submechanism_policy_manifest()[
        cast(SubmechanismKind, spec.runtime_contract.intervention_kind)
    ]
    action_count = len(tuple(policy["resolution_tools"]))
    if spec.runtime_contract.intervention_kind == "unresolved_conflict_cannot_stop":
        action_count = 3
    action_nodes = {item.node_id: item for item in spec.action_graph.nodes}
    chain = 0
    current = spec.runtime_contract.resolution_node_id
    while current in action_nodes:
        chain += 1
        dependencies = action_nodes[current].depends_on
        if not dependencies:
            break
        current = dependencies[0]
        if current == spec.runtime_contract.trigger_node_id:
            chain += 1
            break
    return StoppingShapeDifficultyVector(
        underlying_family=family,
        tier=tier,
        program_node_count=len(program.nodes),
        program_depth=max(depth.values()),
        required_evidence_count=len(evidence),
        public_corpus_count=len(public_evidence),
        source_count=len({item.source.source_id for item in evidence}),
        metric_count=len({item.predicate for item in evidence}),
        period_count=len(
            {
                (
                    item.temporal_context.label,
                    item.temporal_context.valid_from,
                    item.temporal_context.valid_to,
                    item.temporal_context.observed_at,
                )
                for item in evidence
            }
        ),
        resolution_action_count=action_count,
        resolution_chain_length=chain,
        distractor_count=len(public_evidence) - len(evidence),
        early_stop_consequence=design.early_stop_consequence,
    )


def _make_source_sensitivity_diagnostic(
    contract: FinanceCrossPopulationStableContract,
    behavior_path: Path,
) -> SourceSensitivityDiagnostic:
    behaviors = tuple(
        SubmechanismBehaviorObservation.model_validate_json(line)
        for line in behavior_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    population_rows: list[PopulationSensitivityRow] = []
    for reference in contract.population_references:
        payload = json.loads(Path(reference.path).read_text(encoding="utf-8"))
        population_id = str(payload["population_id"])
        task_ids = {str(item["artifact"]["artifact_id"]) for item in payload["tasks"]}
        rows, complete = _stable_rows(
            contract,
            tuple(item for item in behaviors if item.task_artifact_id in task_ids),
        )
        if len(complete) != len(task_ids):
            raise ValueError("v25.35 sensitivity diagnostic has incomplete task rows")
        full = estimate_stable_subspace(rows, contract.stable_subspace_policy)
        parent_rows: list[ParentSensitivityRow] = []
        for parent in sorted({item.parent_mechanism_id for item in rows}):
            reduced = estimate_stable_subspace(
                tuple(item for item in rows if item.parent_mechanism_id != parent),
                contract.stable_subspace_policy,
            )
            angle = max(principal_angles_degrees(full.claimed_basis, reduced.claimed_basis))
            parent_rows.append(
                ParentSensitivityRow(
                    parent_mechanism_id=parent,
                    information_share=full.parent_information_share[parent],
                    leave_one_parent_maximum_angle_degrees=angle,
                )
            )
        task_rows: list[TaskSensitivityRow] = []
        for row in rows:
            reduced = estimate_stable_subspace(
                tuple(item for item in rows if item.task_id != row.task_id),
                contract.stable_subspace_policy,
            )
            angle = max(principal_angles_degrees(full.claimed_basis, reduced.claimed_basis))
            task_rows.append(
                TaskSensitivityRow(
                    task_artifact_id=row.task_id,
                    submechanism_id=row.submechanism_id,
                    probability=row.probability,
                    fisher_weight=row.probability * (1.0 - row.probability),
                    leave_one_task_maximum_angle_degrees=angle,
                )
            )
        dominant = tuple(
            sorted(
                task_rows,
                key=lambda item: (
                    -item.leave_one_task_maximum_angle_degrees,
                    item.task_artifact_id,
                ),
            )[:6]
        )
        non_stopping = max(
            item.leave_one_parent_maximum_angle_degrees
            for item in parent_rows
            if item.parent_mechanism_id != STOPPING_PARENT_ID
        )
        population_rows.append(
            PopulationSensitivityRow(
                population_id=population_id,
                parent_rows=tuple(parent_rows),
                dominant_task_rows=dominant,
                maximum_non_stopping_parent_rotation_degrees=non_stopping,
                maximum_single_task_rotation_degrees=max(
                    item.leave_one_task_maximum_angle_degrees for item in task_rows
                ),
            )
        )
    values = {
        "source_contract_id": contract.contract_id,
        "population_rows": tuple(population_rows),
        "stopping_only_explanation_rejected": any(
            item.maximum_non_stopping_parent_rotation_degrees > 45.0 for item in population_rows
        ),
        "single_task_dominance_observed": any(
            item.maximum_single_task_rotation_degrees > 45.0 for item in population_rows
        ),
    }
    provisional = SourceSensitivityDiagnostic.model_construct(diagnostic_id="pending", **values)
    return SourceSensitivityDiagnostic(
        diagnostic_id=source_sensitivity_diagnostic_id(provisional), **values
    )


def _historical_references(
    source_protocol: FinanceCrossPopulationStableProtocol,
    source_contract: FinanceCrossPopulationStableContract,
) -> tuple[FrozenArtifactReference, ...]:
    raw = [
        *(
            FrozenArtifactReference(**item.model_dump())
            for item in source_protocol.historical_population_references
        ),
        *(
            FrozenArtifactReference(**item.model_dump())
            for item in source_contract.population_references
        ),
    ]
    by_id = {item.artifact_id: item for item in raw}
    if len(by_id) != len(raw):
        raise ValueError("v25.36 historical exclusion set contains duplicate populations")
    return tuple(sorted(by_id.values(), key=lambda item: item.artifact_id))


def _collect_excluded_identities(
    references: Sequence[FrozenArtifactReference],
) -> dict[str, set[str]]:
    identities: dict[str, set[str]] = {
        "evidence_id": set(),
        "evidence_version_id": set(),
        "source_semantic_signature": set(),
        "materializer_hash": set(),
        "artifact_id": set(),
    }
    for reference in references:
        path = Path(reference.path)
        if _sha256(path) != reference.sha256:
            raise ValueError(f"historical population hash changed: {path}")
        _collect_identity(json.loads(path.read_text(encoding="utf-8")), identities)
    return identities


def _collect_identity(value: Any, identities: dict[str, set[str]]) -> None:
    if isinstance(value, Mapping):
        for key in identities:
            raw = value.get(key)
            if isinstance(raw, str):
                identities[key].add(raw)
        for item in value.values():
            _collect_identity(item, identities)
    elif isinstance(value, list):
        for item in value:
            _collect_identity(item, identities)


def _public_task_isolated(task: StoppingShapeTask) -> bool:
    public = task.artifact.task.public.model_dump(mode="json")
    text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    forbidden_keys = {
        "scenario_id",
        "submechanism_id",
        "parent_mechanism_id",
        "intervention_kind",
        "canonical_candidate",
        "repair_target_field",
        "evidence_roles",
    }
    keys = _mapping_keys(public)
    forbidden_values = {
        task.scenario.scenario_id,
        task.scenario.submechanism_id,
        task.scenario.parent_mechanism_id,
        task.scenario.intervention_kind,
        *(item.evidence_id for item in task.artifact.public_corpus.evidence),
        *(item.evidence_version_id for item in task.artifact.public_corpus.evidence),
    }
    return (
        FINANCE_SUBMECHANISM_ORACLE_KEY in task.artifact.task.oracle.selection_contract
        and FINANCE_SUBMECHANISM_ORACLE_KEY not in text
        and not (keys & forbidden_keys)
        and not any(value in text for value in forbidden_values)
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


def _verify_protocol_inputs(protocol: FinanceStoppingShapeStabilityProtocol) -> None:
    references = (
        protocol.source_v25_35_protocol,
        protocol.source_v25_35_contract,
        protocol.source_v25_35_report,
        protocol.source_v25_35_behaviors,
        protocol.source_direction_report,
        protocol.source_finance_artifacts,
        protocol.source_calibration_contract,
        *protocol.historical_population_references,
    )
    for reference in references:
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"frozen Stopping-shape input changed: {reference.path}")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_population.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability_protocol.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _render_population_report(population: FinanceStoppingShapePopulation) -> str:
    lines = [
        "# Finance v25.36 Stopping Shape Population",
        "",
        f"- Population: `{population.population_id}`",
        f"- Tasks: `{len(population.tasks)}`",
        f"- Static ready: `{str(population.static_audit.ready).lower()}`",
        f"- Next stage: `{population.next_permitted_stage}`",
        "",
        "| Shape | Stratum | Family | Program nodes | Program depth | Actions |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in population.tasks:
        lines.append(
            f"| `{item.shape_id}` | `{item.stratum_id}` | `{item.artifact.family}` | "
            f"{item.difficulty.program_node_count} | {item.difficulty.program_depth} | "
            f"{item.difficulty.resolution_action_count} |"
        )
    return "\n".join(lines) + "\n"


def _rate(values: Sequence[bool] | Any) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or build v25.36 Stopping Shape Development"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-protocol", required=True, type=Path)
    prepare.add_argument("--source-contract", required=True, type=Path)
    prepare.add_argument("--source-report", required=True, type=Path)
    prepare.add_argument("--source-behaviors", required=True, type=Path)
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
        protocol = prepare_stopping_shape_protocol(
            source_v25_35_protocol_path=args.source_protocol,
            source_v25_35_contract_path=args.source_contract,
            source_v25_35_report_path=args.source_report,
            source_v25_35_behaviors_path=args.source_behaviors,
            output_path=args.output,
            run_id=args.run_id,
        )
        print(protocol.model_dump_json(indent=2))
    else:
        population = build_stopping_shape_population(
            protocol_path=args.protocol,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        print(population.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
