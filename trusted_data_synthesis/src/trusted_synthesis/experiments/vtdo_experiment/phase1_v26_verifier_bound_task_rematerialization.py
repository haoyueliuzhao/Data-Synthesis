from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.executable_support import MechanismNecessityArtifact
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.core.trajectory.public_operation import (
    OperationalExecutableTaskPackage,
    OperationalExecutableVerifierBinding,
    operational_executable_task_package_id,
    operational_executable_verifier_binding_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
    AuthorityPreservingTaskAudit,
    SourceArtifactFile,
    _harden_environment,
    _harden_record,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingVerifierQualificationReport,
    ImplementationSource,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    RematerializedExecutableTaskRecord,
    V26ExecutableTaskRematerializationReport,
    _base_draft,
    _definition_pair_key,
    _DefinitionPair,
    _reconciliation_draft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (  # noqa: E501
    ExposureCleanPopulationReceipt,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityPopulationReport,
    _operational_record_values,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (  # noqa: E501
    FRESHNESS_CHANNELS as SOURCE_FRESHNESS_CHANNELS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (
    MECHANISM_SOURCE_FAMILY,
    _load_population,
    _merge_values,
    _record_evidence_values,
    _source_task_values,
    _upgrade_task,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    TargetMechanism,
    operational_task_record_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (  # noqa: E501
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    make_agent_tool_environment_manifest,
)

V26_VERIFIER_BOUND_POPULATION_VERSION = "finance_v26_verifier_bound_instrument_population.v1"
V26_VERIFIER_BOUND_FRESHNESS_VERSION = "finance_v26_verifier_bound_freshness.v1"
V26_VERIFIER_BOUND_RECONCILIATION_VERSION = "finance_v26_verifier_bound_reconciliation_selection.v1"
V26_VERIFIER_BOUND_DEFINITION_CAPACITY_VERSION = (
    "finance_v26_verifier_bound_definition_pair_capacity.v1"
)
V26_VERIFIER_BOUND_REPLAY_BINDING_VERSION = "finance_v26_authority_preserving_replay_binding.v1"
V26_VERIFIER_BOUND_LINEAGE_VERSION = "finance_v26_verifier_bound_task_lineage.v1"
V26_VERIFIER_BOUND_RECORD_VERSION = "finance_v26_verifier_bound_operational_task.v1"
V26_VERIFIER_IMPLEMENTATION_ID: Literal["core.authority_preserving_executable_task_verifier"] = (
    "core.authority_preserving_executable_task_verifier"
)
V26_VERIFIER_IMPLEMENTATION_VERSION: Literal["authority_preserving_executable_task_verifier.v2"] = (
    "authority_preserving_executable_task_verifier.v2"
)

INSTRUMENT_TASKS_PER_MECHANISM: Literal[2] = 2
INSTRUMENT_TASK_COUNT: Literal[8] = 8

IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/task/schema.py",
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    "src/trusted_synthesis/domains/finance/public_tool_results.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_operation_hardening.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_verifier_replay.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_executable_task_rematerialization.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_capability_population.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_builder.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_public_operation_rematerialization.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_witness.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_verifier_bound_task_rematerialization.py"
    ),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
    "src/trusted_synthesis/runtime/tools.py",
)

FreshnessChannel = Literal[
    "source_task_artifact_id",
    "source_task_semantic_signature",
    "source_task_hash",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
    "semantic_source_id",
    "task_package_id",
]
FRESHNESS_CHANNELS: tuple[FreshnessChannel, ...] = (
    "source_task_artifact_id",
    "source_task_semantic_signature",
    "source_task_hash",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
    "semantic_source_id",
    "task_package_id",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VerifierBoundChannelAudit(FrozenModel):
    channel: FreshnessChannel
    prior_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)
    overlap_values: tuple[str, ...] = ()
    overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> VerifierBoundChannelAudit:
        if self.overlap_values:
            raise ValueError("Verifier-bound freshness channel contains prior identities")
        return self


class VerifierBoundFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    v26_56_report_id: str = Field(min_length=1)
    v26_65_report_id: str = Field(min_length=1)
    v26_69_report_id: str = Field(min_length=1)
    source_population_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    selection_salt: str = Field(min_length=1)
    channels: tuple[VerifierBoundChannelAudit, ...] = Field(min_length=8, max_length=8)
    selected_task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    selected_nonreconciliation_source_task_count: Literal[6] = 6
    selected_reconciliation_evidence_count: Literal[8] = 8
    historical_model_outcomes_used_for_selection: Literal[False] = False
    historical_diagnostic_candidates_used_for_selection: Literal[False] = False
    historical_trajectory_reuse_forbidden: Literal[True] = True
    generated_trajectory_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESHNESS_CHANNELS:
            raise ValueError("Verifier-bound freshness channels are incomplete")
        if self.source_population_ids != tuple(sorted(set(self.source_population_ids))):
            raise ValueError("Verifier-bound source populations are not canonical")
        if self.audit_id != verifier_bound_freshness_audit_id(self):
            raise ValueError("Verifier-bound freshness identity is invalid")
        return self


class VerifierBoundReconciliationSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_capacity_audit_id: str = Field(min_length=1)
    eligible_definition_pair_count: int = Field(ge=4)
    eligible_reconciliation_task_capacity: int = Field(ge=2)
    instrument_selected_pair_count: Literal[4] = 4
    instrument_task_count: Literal[2] = 2
    selected_evidence_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    selection_policy: Literal[
        "first_four_canonical_period_order_after_frozen_identity_exclusions"
    ] = "first_four_canonical_period_order_after_frozen_identity_exclusions"
    historical_outcomes_consulted: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_RECONCILIATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundReconciliationSelectionAudit:
        if self.selected_evidence_ids != tuple(sorted(set(self.selected_evidence_ids))):
            raise ValueError("Verifier-bound Reconciliation Evidence is duplicated")
        if self.audit_id != verifier_bound_reconciliation_selection_audit_id(self):
            raise ValueError("Verifier-bound Reconciliation selection identity is invalid")
        return self


class VerifierBoundDefinitionPairCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    snapshot_path: str = Field(min_length=1)
    snapshot_sha256: str = Field(min_length=64, max_length=64)
    exposure_receipt_id: str = Field(min_length=1)
    exposure_receipt_sha256: str = Field(min_length=64, max_length=64)
    source_evidence_count: int = Field(ge=1)
    excluded_evidence_count: int = Field(ge=0)
    additional_exclusion_count: int = Field(ge=0)
    eligible_evidence_count: int = Field(ge=1)
    eligible_definition_pair_count: int = Field(ge=4)
    eligible_reconciliation_task_capacity: int = Field(ge=2)
    selected_definition_pair_count: Literal[4] = 4
    selected_reconciliation_task_count: Literal[2] = 2
    selected_evidence_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    selected_evidence_set_hash: str = Field(min_length=1)
    historical_outcomes_consulted: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_DEFINITION_CAPACITY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundDefinitionPairCapacityAudit:
        if self.selected_evidence_ids != tuple(sorted(set(self.selected_evidence_ids))):
            raise ValueError("Verifier-bound Definition-pair Evidence is not canonical")
        if self.selected_evidence_set_hash != canonical_hash(
            self.selected_evidence_ids,
            prefix="finance_v26_verifier_bound_reconciliation_evidence_set:",
        ):
            raise ValueError("Verifier-bound Definition-pair Evidence hash is invalid")
        if self.eligible_reconciliation_task_capacity < self.selected_reconciliation_task_count:
            raise ValueError("Verifier-bound Definition-pair capacity is insufficient")
        if self.audit_id != verifier_bound_definition_pair_capacity_audit_id(self):
            raise ValueError("Verifier-bound Definition-pair capacity identity is invalid")
        return self


class VerifierV2TaskReplayBinding(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    qualified_verifier_report_id: str = Field(min_length=1)
    qualified_verifier_report_sha256: str = Field(min_length=64, max_length=64)
    qualified_replay_contract_id: str = Field(min_length=1)
    public_operation_contract_id: str = Field(min_length=1)
    action_neutral_repair_contract_id: str = Field(min_length=1)
    terminal_verification_target_id: str = Field(min_length=1)
    public_runtime_contract_id: str = Field(min_length=1)
    stop_readiness_contract_id: str = Field(min_length=1)
    runtime_projection_id: str = Field(min_length=1)
    answer_projection_contract_id: str = Field(min_length=1)
    evidence_support_lattice_id: str = Field(min_length=1)
    citation_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    source_program_dag_hash: str = Field(min_length=1)
    source_verifier_dag_hash: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    verifier_implementation_id: Literal["core.authority_preserving_executable_task_verifier"] = (
        V26_VERIFIER_IMPLEMENTATION_ID
    )
    verifier_implementation_version: Literal["authority_preserving_executable_task_verifier.v2"] = (
        V26_VERIFIER_IMPLEMENTATION_VERSION
    )
    replay_execution_order: tuple[str, ...] = Field(min_length=9, max_length=9)
    failed_result_projection: Literal["typed_action_neutral_semantics_only"] = (
        "typed_action_neutral_semantics_only"
    )
    comparison_rule: Literal["canonical_json_semantic_equality"] = (
        "canonical_json_semantic_equality"
    )
    qualified_implementation_sources: tuple[ImplementationSource, ...] = Field(
        min_length=5, max_length=5
    )
    schema_version: str = V26_VERIFIER_BOUND_REPLAY_BINDING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> VerifierV2TaskReplayBinding:
        if self.contract_id != verifier_v2_task_replay_binding_id(self):
            raise ValueError("Verifier v2 task Replay binding identity is invalid")
        return self


class VerifierBoundTaskLineage(FrozenModel):
    lineage_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    verifier_bound_record_id: str = Field(min_length=1)
    source_task_package_id: str = Field(min_length=1)
    verifier_bound_task_package_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    semantic_source_unchanged: Literal[True] = True
    operation_contract_identity_fresh: Literal[True] = True
    public_runtime_contract_identity_fresh: Literal[True] = True
    stop_readiness_contract_identity_fresh: Literal[True] = True
    action_neutral_repair_contract_identity_fresh: Literal[True] = True
    terminal_verification_target_identity_fresh: Literal[True] = True
    runtime_projection_identity_fresh: Literal[True] = True
    verifier_binding_identity_fresh: Literal[True] = True
    environment_manifest_identity_fresh: Literal[True] = True
    task_package_identity_fresh: Literal[True] = True
    record_identity_fresh: Literal[True] = True
    source_task_outcomes_used: Literal[False] = False
    schema_version: str = V26_VERIFIER_BOUND_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_lineage(self) -> VerifierBoundTaskLineage:
        if self.source_record_id == self.verifier_bound_record_id:
            raise ValueError("Verifier-bound record identity was reused")
        if self.source_task_package_id == self.verifier_bound_task_package_id:
            raise ValueError("Verifier-bound TaskPackage identity was reused")
        if self.lineage_id != verifier_bound_task_lineage_id(self):
            raise ValueError("Verifier-bound task lineage identity is invalid")
        return self


class VerifierBoundLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_lineages: tuple[VerifierBoundTaskLineage, ...] = Field(min_length=8, max_length=8)
    source_task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    verifier_bound_task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    source_model_outcome_count: Literal[0] = 0
    source_model_outcomes_used: Literal[False] = False
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundLineageAudit:
        identities = tuple(item.lineage_id for item in self.task_lineages)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("Verifier-bound task lineages are not canonical")
        if self.audit_id != verifier_bound_lineage_audit_id(self):
            raise ValueError("Verifier-bound lineage audit identity is invalid")
        return self


class VerifierBoundInstrumentPopulationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_v26_69_report_id: str = Field(min_length=1)
    source_v26_69_report_sha256: str = Field(min_length=64, max_length=64)
    verifier_qualification_report_id: str = Field(min_length=1)
    verifier_qualification_report_sha256: str = Field(min_length=64, max_length=64)
    qualified_replay_contract_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    reconciliation_selection_audit_id: str = Field(min_length=1)
    lineage_audit_id: str = Field(min_length=1)
    mechanism_task_counts: dict[str, int]
    task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    instrument_task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    fresh_task_package_count: Literal[8] = INSTRUMENT_TASK_COUNT
    verifier_v2_replay_binding_count: Literal[8] = INSTRUMENT_TASK_COUNT
    action_neutral_repair_contract_count: Literal[8] = INSTRUMENT_TASK_COUNT
    terminal_verification_target_count: Literal[8] = INSTRUMENT_TASK_COUNT
    repair_prompt_audit_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    terminal_verification_audit_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    operation_closure_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    public_witness_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_generated_witness_count: Literal[8] = INSTRUMENT_TASK_COUNT
    mechanism_necessity_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    operational_capability_eligible_count: Literal[8] = INSTRUMENT_TASK_COUNT
    legacy_operation_mutation_count: int = Field(ge=64)
    authority_verification_mutation_count: Literal[40] = 40
    task_record_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    task_package_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    environment_manifest_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    replay_binding_contract_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=15)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=14)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=15, max_length=15
    )
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    historical_diagnostic_candidates_reused: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["verifier_v2_bound_instrument_preflight_only"] = (
        "verifier_v2_bound_instrument_preflight_only"
    )
    instrument_preflight_authorized: Literal[True] = True
    instrument_requalification_authorized: Literal[False] = False
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_VERIFIER_BOUND_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> VerifierBoundInstrumentPopulationReport:
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("Verifier-bound Instrument mechanism quotas changed")
        groups = (
            self.task_record_ids,
            self.task_package_ids,
            self.environment_manifest_ids,
            self.replay_binding_contract_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("Verifier-bound report identity sets are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("Verifier-bound implementation manifest is incomplete")
        if self.report_id != verifier_bound_population_report_id(self):
            raise ValueError("Verifier-bound Instrument Population report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"Verifier-bound immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _write_models(path: Path, values: Sequence[BaseModel], identity: str) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=lambda item: str(item[identity]),
    )
    _write_json(path, rows)


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def _source_file(path: Path, package_root: Path) -> SourceArtifactFile:
    return SourceArtifactFile(
        relative_path=str(path.resolve().relative_to(package_root.resolve())),
        sha256=_sha256(path),
        record_count=_record_count(path),
    )


def _artifact_file(path: Path, output_dir: Path, count: int) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _replay_manifested_files(source_dir: Path, descriptors: Sequence[Any]) -> None:
    for item in descriptors:
        path = source_dir / item.relative_path
        if (
            not path.is_file()
            or _sha256(path) != item.sha256
            or _record_count(path) != item.record_count
        ):
            raise ValueError(f"Verifier-bound source Artifact replay failed: {path}")


def _replay_package_files(package_root: Path, descriptors: Sequence[Any]) -> None:
    for item in descriptors:
        path = package_root / item.relative_path
        if not path.is_file() or _sha256(path) != item.sha256:
            raise ValueError(f"Verifier-bound package source replay failed: {path}")
        if hasattr(item, "record_count") and _record_count(path) != item.record_count:
            raise ValueError(f"Verifier-bound package source count changed: {path}")


def _load_and_replay_verifier_qualification(
    verifier_qualification_dir: Path,
    package_root: Path,
) -> tuple[AuthorityPreservingVerifierQualificationReport, AuthorityPreservingReplayContract]:
    report = AuthorityPreservingVerifierQualificationReport.model_validate_json(
        (verifier_qualification_dir / "report.json").read_text(encoding="utf-8")
    )
    _replay_manifested_files(verifier_qualification_dir, report.immutable_detail_files)
    _replay_package_files(package_root, report.source_artifact_files)
    _replay_package_files(package_root, report.implementation_source_files)
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    if report.replay_contract != replay_contract:
        raise ValueError("Verifier qualification report binds another Replay Contract")
    return report, replay_contract


def _load_and_replay_fresh_capability(
    source_dir: Path,
    package_root: Path,
) -> tuple[FreshCapabilityPopulationReport, tuple[OperationalTaskRecord, ...]]:
    report = FreshCapabilityPopulationReport.model_validate_json(
        (source_dir / "report.json").read_text(encoding="utf-8")
    )
    _replay_manifested_files(source_dir, report.immutable_artifact_files)
    _replay_package_files(package_root, report.source_artifact_files)
    _replay_package_files(package_root, report.implementation_source_files)
    records = _load_rows(source_dir / "operational_task_records.json", OperationalTaskRecord)
    if len(records) != 12:
        raise ValueError("fresh Capability source record denominator changed")
    return report, records


def _verifier_bound_environment(
    source: AgentToolEnvironmentManifest,
) -> AgentToolEnvironmentManifest:
    return make_agent_tool_environment_manifest(
        environment_id=f"{source.environment_id}.verifier_v2_bound_v1",
        corpus_id=source.corpus_id,
        corpus_hash=source.corpus_hash,
        snapshot_id=source.snapshot_id,
        snapshot_hash=source.snapshot_hash,
        network_policy=source.network_policy,
        tools=source.tools,
        maximum_tool_calls=source.maximum_tool_calls,
        maximum_failed_tool_calls=source.maximum_failed_tool_calls,
        maximum_total_observation_bytes=source.maximum_total_observation_bytes,
        tool_timeout_seconds=source.tool_timeout_seconds,
    )


def _task_replay_binding(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    qualification: AuthorityPreservingVerifierQualificationReport,
    qualification_sha256: str,
    replay_contract: AuthorityPreservingReplayContract,
) -> VerifierV2TaskReplayBinding:
    package = record.task_package
    repair = package.action_neutral_repair_contract
    target = package.terminal_verification_target
    if repair is None or target is None:
        raise ValueError("Verifier v2 binding requires authority-preserving task contracts")
    values = {
        "semantic_source_id": package.semantic_source.semantic_source_id,
        "qualified_verifier_report_id": qualification.report_id,
        "qualified_verifier_report_sha256": qualification_sha256,
        "qualified_replay_contract_id": replay_contract.contract_id,
        "public_operation_contract_id": package.operation_contract.contract_id,
        "action_neutral_repair_contract_id": repair.contract_id,
        "terminal_verification_target_id": target.target_id,
        "public_runtime_contract_id": package.public_runtime_contract.contract_id,
        "stop_readiness_contract_id": package.stop_readiness_contract.contract_id,
        "runtime_projection_id": package.runtime_projection.projection_id,
        "answer_projection_contract_id": package.answer_projection.contract_id,
        "evidence_support_lattice_id": package.evidence_support_lattice.lattice_id,
        "citation_contract_id": package.citation_contract.contract_id,
        "mechanism_contract_id": package.mechanism_contract.contract_id,
        "source_program_dag_hash": package.operation_contract.source_program_dag_hash,
        "source_verifier_dag_hash": package.operation_contract.source_verifier_dag_hash,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": record.environment_manifest_hash,
        "replay_execution_order": replay_contract.replay_execution_order,
        "qualified_implementation_sources": qualification.implementation_source_files,
    }
    provisional = VerifierV2TaskReplayBinding.model_construct(contract_id="pending", **values)
    return VerifierV2TaskReplayBinding(
        contract_id=verifier_v2_task_replay_binding_id(provisional),
        **values,
    )


def _bind_verifier_v2(
    source: OperationalTaskRecord,
    replay_binding: VerifierV2TaskReplayBinding,
) -> OperationalTaskRecord:
    base = source.task_package
    prior_verifier = base.verifier_binding
    verifier_values = {
        "semantic_source_id": prior_verifier.semantic_source_id,
        "answer_projection_contract_id": prior_verifier.answer_projection_contract_id,
        "evidence_support_lattice_id": prior_verifier.evidence_support_lattice_id,
        "citation_contract_id": prior_verifier.citation_contract_id,
        "public_runtime_contract_id": prior_verifier.public_runtime_contract_id,
        "mechanism_contract_id": prior_verifier.mechanism_contract_id,
        "operation_contract_id": prior_verifier.operation_contract_id,
        "stop_readiness_contract_id": prior_verifier.stop_readiness_contract_id,
        "runtime_projection_id": prior_verifier.runtime_projection_id,
        "action_neutral_repair_contract_id": prior_verifier.action_neutral_repair_contract_id,
        "terminal_verification_target_id": prior_verifier.terminal_verification_target_id,
        "source_program_dag_hash": prior_verifier.source_program_dag_hash,
        "source_verifier_dag_hash": prior_verifier.source_verifier_dag_hash,
        "node_bindings": prior_verifier.node_bindings,
        "verifier_implementation_id": replay_binding.contract_id,
        "verifier_version": V26_VERIFIER_IMPLEMENTATION_VERSION,
        "evidence_acceptance_rule": prior_verifier.evidence_acceptance_rule,
        "exact_gold_equality_required": prior_verifier.exact_gold_equality_required,
        "schema_version": prior_verifier.schema_version,
    }
    verifier_provisional = OperationalExecutableVerifierBinding.model_construct(
        binding_id="pending", **verifier_values
    )
    verifier = OperationalExecutableVerifierBinding(
        binding_id=operational_executable_verifier_binding_id(verifier_provisional),
        **verifier_values,
    )

    public_template = base.task.public.model_copy(update={"task_id": "pending"})
    selection_contract = dict(base.task.oracle.selection_contract)
    executable_bindings = dict(selection_contract["executable_support_bindings"])
    executable_bindings["verifier_binding_id"] = verifier.binding_id
    selection_contract["executable_support_bindings"] = executable_bindings
    selection_contract["authority_preserving_verifier_v2_binding"] = {
        "task_replay_binding_contract_id": replay_binding.contract_id,
        "qualified_replay_contract_id": replay_binding.qualified_replay_contract_id,
        "qualified_verifier_report_id": replay_binding.qualified_verifier_report_id,
        "verifier_implementation_id": replay_binding.verifier_implementation_id,
        "verifier_implementation_version": replay_binding.verifier_implementation_version,
    }
    oracle_template = base.task.oracle.model_copy(
        update={"task_id": "pending", "selection_contract": selection_contract}
    )
    task_template = TaskPackage(
        task_id="pending",
        public=public_template,
        oracle=oracle_template,
    )
    package_values = {
        "semantic_source": base.semantic_source,
        "task": task_template,
        "tool_closure": base.tool_closure,
        "answer_projection": base.answer_projection,
        "evidence_support_lattice": base.evidence_support_lattice,
        "citation_contract": base.citation_contract,
        "public_runtime_contract": base.public_runtime_contract,
        "mechanism_contract": base.mechanism_contract,
        "operation_contract": base.operation_contract,
        "stop_readiness_contract": base.stop_readiness_contract,
        "runtime_projection": base.runtime_projection,
        "verifier_binding": verifier,
        "action_neutral_repair_contract": base.action_neutral_repair_contract,
        "terminal_verification_target": base.terminal_verification_target,
        "schema_version": base.schema_version,
    }
    package_provisional = OperationalExecutableTaskPackage.model_construct(
        package_id="pending", **package_values
    )
    package_id = operational_executable_task_package_id(package_provisional)
    task = TaskPackage(
        task_id=package_id,
        public=public_template.model_copy(update={"task_id": package_id}),
        oracle=oracle_template.model_copy(update={"task_id": package_id}),
    )
    package = OperationalExecutableTaskPackage(
        package_id=package_id,
        **{**package_values, "task": task},
    )
    record_values = {
        "mechanism_id": source.mechanism_id,
        "intended_use": source.intended_use,
        "source_task_artifact_ids": source.source_task_artifact_ids,
        "task_package": package,
        "evidence_bundle": source.evidence_bundle,
        "public_corpus": source.public_corpus,
        "proof_graph": source.proof_graph,
        "projected_expected_output": source.projected_expected_output,
        "answer_projection": source.answer_projection,
        "mechanism_public_state": source.mechanism_public_state,
        "mechanism_private_state": source.mechanism_private_state,
        "recovery_scenario": source.recovery_scenario,
        "target_program_evidence_ids": source.target_program_evidence_ids,
        "environment_manifest_id": source.environment_manifest_id,
        "environment_manifest_hash": source.environment_manifest_hash,
        "compiler_reference_policy": source.compiler_reference_policy,
        "compiler_witness_model_generated": source.compiler_witness_model_generated,
        "schema_version": V26_VERIFIER_BOUND_RECORD_VERSION,
    }
    record_provisional = OperationalTaskRecord.model_construct(record_id="pending", **record_values)
    return OperationalTaskRecord(
        record_id=operational_task_record_id(record_provisional),
        **record_values,
    )


def _lineage(
    source: OperationalTaskRecord,
    verifier_bound: OperationalTaskRecord,
    replay_binding: VerifierV2TaskReplayBinding,
) -> VerifierBoundTaskLineage:
    old = source.task_package
    new = verifier_bound.task_package
    old_repair = old.action_neutral_repair_contract
    new_repair = new.action_neutral_repair_contract
    old_target = old.terminal_verification_target
    new_target = new.terminal_verification_target
    values = {
        "source_record_id": source.record_id,
        "verifier_bound_record_id": verifier_bound.record_id,
        "source_task_package_id": old.package_id,
        "verifier_bound_task_package_id": new.package_id,
        "semantic_source_id": new.semantic_source.semantic_source_id,
        "replay_binding_contract_id": replay_binding.contract_id,
        "semantic_source_unchanged": (
            old.semantic_source.semantic_source_id == new.semantic_source.semantic_source_id
        ),
        "operation_contract_identity_fresh": (
            old.operation_contract.contract_id != new.operation_contract.contract_id
        ),
        "public_runtime_contract_identity_fresh": (
            old.public_runtime_contract.contract_id != new.public_runtime_contract.contract_id
        ),
        "stop_readiness_contract_identity_fresh": (
            old.stop_readiness_contract.contract_id != new.stop_readiness_contract.contract_id
        ),
        "action_neutral_repair_contract_identity_fresh": (
            (old_repair is None and new_repair is not None)
            or (
                old_repair is not None
                and new_repair is not None
                and old_repair.contract_id != new_repair.contract_id
            )
        ),
        "terminal_verification_target_identity_fresh": (
            (old_target is None and new_target is not None)
            or (
                old_target is not None
                and new_target is not None
                and old_target.target_id != new_target.target_id
            )
        ),
        "runtime_projection_identity_fresh": (
            old.runtime_projection.projection_id != new.runtime_projection.projection_id
        ),
        "verifier_binding_identity_fresh": (
            old.verifier_binding.binding_id != new.verifier_binding.binding_id
        ),
        "environment_manifest_identity_fresh": (
            source.environment_manifest_id != verifier_bound.environment_manifest_id
        ),
        "task_package_identity_fresh": old.package_id != new.package_id,
        "record_identity_fresh": source.record_id != verifier_bound.record_id,
    }
    provisional = VerifierBoundTaskLineage.model_construct(lineage_id="pending", **values)
    return VerifierBoundTaskLineage(
        lineage_id=verifier_bound_task_lineage_id(provisional),
        **values,
    )


def _freshness_audit(
    *,
    development: V26FreshTaskPopulation,
    report56: V26ExecutableTaskRematerializationReport,
    report65: AuthorityPreservingHardeningReport,
    report69: FreshCapabilityPopulationReport,
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    selection_salt: str,
    prior_values: Mapping[str, set[str]],
    selected_source_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    prior_records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
    selected_records: Sequence[OperationalTaskRecord],
) -> VerifierBoundFreshnessAudit:
    selected_base = _source_task_values(selected_source_tasks)
    selected: dict[str, set[str]] = {
        **selected_base,
        "evidence_id": {
            item.evidence_id
            for record in selected_records
            for item in record.public_corpus.evidence
        },
        "evidence_version_id": {
            item.evidence_version_id
            for record in selected_records
            for item in record.public_corpus.evidence
        },
        "source_record_id": {
            item.provenance.source_record_id
            for record in selected_records
            for item in record.public_corpus.evidence
        },
        "semantic_source_id": {
            item.task_package.semantic_source.semantic_source_id for item in selected_records
        },
        "task_package_id": {item.task_package.package_id for item in selected_records},
    }
    prior: dict[str, set[str]] = {
        **{channel: set(prior_values[channel]) for channel in SOURCE_FRESHNESS_CHANNELS},
        "semantic_source_id": {
            item.task_package.semantic_source.semantic_source_id for item in prior_records
        },
        "task_package_id": {item.task_package.package_id for item in prior_records},
    }
    channels = []
    for channel in FRESHNESS_CHANNELS:
        prior_items = tuple(sorted(prior[channel]))
        selected_items = tuple(sorted(selected[channel]))
        overlap = tuple(sorted(set(prior_items) & set(selected_items)))
        if overlap:
            raise ValueError(f"Verifier-bound freshness channel {channel} overlaps history")
        channels.append(
            VerifierBoundChannelAudit(
                channel=channel,
                prior_count=len(prior_items),
                selected_count=len(selected_items),
                prior_set_hash=canonical_hash(
                    {"channel": channel, "values": prior_items},
                    prefix="finance_v26_verifier_bound_prior_set:",
                ),
                selected_set_hash=canonical_hash(
                    {"channel": channel, "values": selected_items},
                    prefix="finance_v26_verifier_bound_selected_set:",
                ),
            )
        )
    values = {
        "development_population_id": development.population_id,
        "v26_56_report_id": report56.report_id,
        "v26_65_report_id": report65.report_id,
        "v26_69_report_id": report69.report_id,
        "source_population_ids": tuple(sorted(item.population_id for item in sources)),
        "selection_salt": selection_salt,
        "channels": tuple(channels),
    }
    provisional = VerifierBoundFreshnessAudit.model_construct(audit_id="pending", **values)
    return VerifierBoundFreshnessAudit(
        audit_id=verifier_bound_freshness_audit_id(provisional),
        **values,
    )


def _load_instrument_definition_pairs(
    *,
    snapshot_path: Path,
    receipt: ExposureCleanPopulationReceipt,
    exposure_receipt_path: Path,
    additional_excluded_ids: set[str],
    sampling_salt: str,
) -> tuple[
    tuple[_DefinitionPair, ...],
    VerifierBoundDefinitionPairCapacityAudit,
]:
    excluded = set(receipt.excluded_evidence_ids) | additional_excluded_ids
    groups: defaultdict[
        tuple[object, ...],
        list[tuple[EvidenceItem, tuple[str, ...]]],
    ] = defaultdict(list)
    source_count = 0
    eligible_count = 0
    with snapshot_path.open(encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            source_count += 1
            evidence = EvidenceItem.model_validate(payload["evidence"])
            if evidence.evidence_id in excluded:
                continue
            eligible_count += 1
            groups[_definition_pair_key(evidence)].append(
                (evidence, tuple(sorted(payload["source_artifact_ids"])))
            )
    candidates: list[_DefinitionPair] = []
    for group_rows in groups.values():
        by_definition = {
            item.definition.definition_id: (item, sources) for item, sources in group_rows
        }
        definitions = sorted(
            definition_id for definition_id in by_definition if definition_id is not None
        )
        if len(definitions) != 2 or len(definitions) != len(by_definition):
            continue
        left, left_sources = by_definition[definitions[0]]
        right, right_sources = by_definition[definitions[1]]
        frequencies = {
            str(left.temporal_context.frequency).casefold(),
            str(right.temporal_context.frequency).casefold(),
        }
        if frequencies != {"daily", "monthly"}:
            continue
        if left.domain_context.get("semantic_equivalence_group_id") != right.domain_context.get(
            "semantic_equivalence_group_id"
        ) or Decimal(str(left.payload.value)) != Decimal(str(right.payload.value)):
            continue
        candidates.append(
            _DefinitionPair(
                left=left,
                right=right,
                source_artifact_ids=tuple(sorted(set(left_sources) | set(right_sources))),
            )
        )
    candidates.sort(
        key=lambda item: canonical_hash(
            {
                "salt": sampling_salt,
                "versions": tuple(value.evidence_version_id for value in item.evidence),
            },
            prefix="finance_v26_verifier_bound_definition_pair_rank:",
        )
    )
    if len(candidates) < 4:
        raise ValueError("eligible Evidence cannot support two fresh Reconciliation tasks")
    selected = tuple(sorted(candidates[:4], key=lambda item: item.period))
    selected_ids = tuple(sorted(item.evidence_id for pair in selected for item in pair.evidence))
    audit_values = {
        "snapshot_path": str(snapshot_path.resolve()),
        "snapshot_sha256": _sha256(snapshot_path),
        "exposure_receipt_id": receipt.receipt_id,
        "exposure_receipt_sha256": _sha256(exposure_receipt_path),
        "source_evidence_count": source_count,
        "excluded_evidence_count": len(receipt.excluded_evidence_ids),
        "additional_exclusion_count": len(additional_excluded_ids),
        "eligible_evidence_count": eligible_count,
        "eligible_definition_pair_count": len(candidates),
        "eligible_reconciliation_task_capacity": len(candidates) // 2,
        "selected_evidence_ids": selected_ids,
        "selected_evidence_set_hash": canonical_hash(
            selected_ids,
            prefix="finance_v26_verifier_bound_reconciliation_evidence_set:",
        ),
    }
    provisional = VerifierBoundDefinitionPairCapacityAudit.model_construct(
        audit_id="pending", **audit_values
    )
    audit = VerifierBoundDefinitionPairCapacityAudit(
        audit_id=verifier_bound_definition_pair_capacity_audit_id(provisional),
        **audit_values,
    )
    return selected, audit


def _select_instrument_source_tasks(
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    *,
    excluded: Mapping[str, set[str]],
    sampling_salt: str,
) -> dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]]:
    output: dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    selected_evidence_ids: set[str] = set()
    selected_evidence_versions: set[str] = set()
    selected_source_records: set[str] = set()
    for mechanism, family in MECHANISM_SOURCE_FAMILY.items():
        candidates = [task for source in sources for task in source.tasks if task.family == family]
        if mechanism == "failure_recovery":
            candidates = [item for item in candidates if item.recovery_branches]
        eligible = []
        for item in candidates:
            values = _source_task_values((item,))
            if any(values[channel] & excluded[channel] for channel in SOURCE_FRESHNESS_CHANNELS):
                continue
            eligible.append(item)
        eligible.sort(
            key=lambda item: canonical_hash(
                {
                    "salt": sampling_salt,
                    "mechanism": mechanism,
                    "source_task_artifact_id": item.artifact_id,
                },
                prefix="finance_v26_verifier_bound_source_rank:",
            )
        )
        selected = []
        for item in eligible:
            evidence_ids = {value.evidence_id for value in item.public_corpus.evidence}
            versions = {value.evidence_version_id for value in item.public_corpus.evidence}
            source_records = {
                value.provenance.source_record_id for value in item.public_corpus.evidence
            }
            if (
                evidence_ids & selected_evidence_ids
                or versions & selected_evidence_versions
                or source_records & selected_source_records
            ):
                continue
            selected.append(item)
            selected_evidence_ids.update(evidence_ids)
            selected_evidence_versions.update(versions)
            selected_source_records.update(source_records)
            if len(selected) == INSTRUMENT_TASKS_PER_MECHANISM:
                break
        if len(selected) != INSTRUMENT_TASKS_PER_MECHANISM:
            raise ValueError(
                f"fresh source capacity cannot supply two Instrument tasks for {mechanism}"
            )
        output[cast(TargetMechanism, mechanism)] = tuple(selected)
    return output


def build_verifier_bound_instrument_population(
    *,
    run_id: str,
    development_population_path: Path,
    secondary_source_path: Path,
    tertiary_source_path: Path,
    tertiary_no_api_report_path: Path,
    v26_56_dir: Path,
    v26_65_dir: Path,
    v26_69_dir: Path,
    verifier_qualification_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
    selection_salt: str,
    output_dir: Path,
    package_root: Path,
) -> VerifierBoundInstrumentPopulationReport:
    development = V26FreshTaskPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    if development.phase != "development":
        raise ValueError("Verifier-bound source is not the frozen Development role")
    development_tasks = load_v26_selected_source_tasks(development)
    primary_source_path = Path(development.source_population_path)
    if _sha256(primary_source_path) != development.source_population_sha256:
        raise ValueError("Verifier-bound primary source Population replay failed")
    sources = (
        _load_population(primary_source_path),
        _load_population(secondary_source_path),
        _load_population(tertiary_source_path),
    )
    if len({item.population_id for item in sources}) != 3:
        raise ValueError("Verifier-bound construction requires three source Populations")
    tertiary_receipt = json.loads(tertiary_no_api_report_path.read_text(encoding="utf-8"))
    expected_tertiary = (
        tertiary_no_api_report_path.parent / "population" / "confirmation_source.json"
    )
    if (
        tertiary_receipt.get("model_api_calls") != 0
        or tertiary_receipt.get("gpu_jobs") != 0
        or tertiary_source_path.resolve() != expected_tertiary.resolve()
    ):
        raise ValueError("Verifier-bound tertiary source lacks its zero-API receipt")

    report56 = V26ExecutableTaskRematerializationReport.model_validate_json(
        (v26_56_dir / "report.json").read_text(encoding="utf-8")
    )
    records56 = _load_rows(
        v26_56_dir / "rematerialized_task_records.json", RematerializedExecutableTaskRecord
    )
    _replay_manifested_files(v26_56_dir, report56.immutable_artifact_files)
    report65 = AuthorityPreservingHardeningReport.model_validate_json(
        (v26_65_dir / "report.json").read_text(encoding="utf-8")
    )
    records65 = _load_rows(v26_65_dir / "operational_task_records.json", OperationalTaskRecord)
    _replay_manifested_files(v26_65_dir, report65.immutable_artifact_files)
    report69, records69 = _load_and_replay_fresh_capability(v26_69_dir, package_root)
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        verifier_qualification_dir, package_root
    )
    qualification_path = verifier_qualification_dir / "report.json"
    qualification_sha256 = _sha256(qualification_path)

    all_source_tasks = tuple(item for source in sources for item in source.tasks)
    source_by_id = {item.artifact_id: item for item in all_source_tasks}
    historical_records = (*records56, *records65, *records69)
    historical_source_ids = {
        value for record in historical_records for value in record.source_task_artifact_ids
    }
    historical_source_tasks = tuple(
        source_by_id[value] for value in sorted(historical_source_ids) if value in source_by_id
    )
    prior_values = _merge_values(
        _source_task_values(development_tasks),
        _source_task_values(historical_source_tasks),
        _record_evidence_values(records56),
        _operational_record_values((*records65, *records69)),
    )
    selected_pool = _select_instrument_source_tasks(
        sources,
        excluded=prior_values,
        sampling_salt=selection_salt,
    )
    selected_by_mechanism = {
        mechanism: selected_pool[mechanism][:INSTRUMENT_TASKS_PER_MECHANISM]
        for mechanism in (
            "context_conditioned_action",
            "failure_recovery",
            "state_dependent_stopping",
        )
    }
    selected_source_tasks = tuple(
        item
        for mechanism in (
            "context_conditioned_action",
            "failure_recovery",
            "state_dependent_stopping",
        )
        for item in selected_by_mechanism[mechanism]
    )
    base_selected_evidence_ids = {
        item.evidence_id for task in selected_source_tasks for item in task.public_corpus.evidence
    }
    receipt = ExposureCleanPopulationReceipt.model_validate_json(
        exposure_receipt_path.read_text(encoding="utf-8")
    )
    if Path(receipt.source_artifacts_path).resolve() != snapshot_path.resolve() or (
        receipt.source_artifacts_sha256 != _sha256(snapshot_path)
    ):
        raise ValueError("Verifier-bound Snapshot differs from its exposure receipt")
    definition_pairs, capacity_audit = _load_instrument_definition_pairs(
        snapshot_path=snapshot_path,
        receipt=receipt,
        exposure_receipt_path=exposure_receipt_path,
        additional_excluded_ids=prior_values["evidence_id"] | base_selected_evidence_ids,
        sampling_salt=selection_salt,
    )
    instrument_pairs = definition_pairs[:4]
    selected_pair_evidence_ids = tuple(
        sorted(item.evidence_id for pair in instrument_pairs for item in pair.evidence)
    )
    selection_values = {
        "source_capacity_audit_id": capacity_audit.audit_id,
        "eligible_definition_pair_count": capacity_audit.eligible_definition_pair_count,
        "eligible_reconciliation_task_capacity": (
            capacity_audit.eligible_reconciliation_task_capacity
        ),
        "selected_evidence_ids": selected_pair_evidence_ids,
    }
    selection_provisional = VerifierBoundReconciliationSelectionAudit.model_construct(
        audit_id="pending", **selection_values
    )
    reconciliation_selection = VerifierBoundReconciliationSelectionAudit(
        audit_id=verifier_bound_reconciliation_selection_audit_id(selection_provisional),
        **selection_values,
    )

    drafts = []
    for mechanism in (
        "context_conditioned_action",
        "failure_recovery",
        "state_dependent_stopping",
    ):
        for task in selected_by_mechanism[mechanism]:
            drafts.append(
                _base_draft(task, mechanism_id=mechanism, intended_use="capability_measurement")
            )
    for index in range(INSTRUMENT_TASKS_PER_MECHANISM):
        drafts.append(
            _reconciliation_draft(
                instrument_pairs[index * 2],
                instrument_pairs[index * 2 + 1],
                intended_use="capability_measurement",
            )
        )
    drafts.sort(key=lambda item: (TARGET_MECHANISMS.index(item.mechanism_id), item.instruction))
    if Counter(item.mechanism_id for item in drafts) != Counter(
        {mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("Verifier-bound Instrument draft quotas are incomplete")

    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    replay_bindings: list[VerifierV2TaskReplayBinding] = []
    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    closures: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    task_audits: list[AuthorityPreservingTaskAudit] = []
    lineages: list[VerifierBoundTaskLineage] = []
    for draft in drafts:
        source_record, source_environment = _upgrade_task(draft)
        authority_environment = _harden_environment(source_environment)
        environment = _verifier_bound_environment(authority_environment)
        authority_record = _harden_record(source_record, environment)
        replay_binding = _task_replay_binding(
            authority_record,
            environment,
            qualification,
            qualification_sha256,
            replay_contract,
        )
        record = _bind_verifier_v2(authority_record, replay_binding)
        witness, history = compile_operational_witness(
            record,
            environment,
            strategy="structured_direct",
        )
        necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
            record, (witness,)
        )
        closure = build_operation_closure_audit(record, (witness,), (history,), necessity, catalog)
        admission = build_operational_admission(record, witness, necessity, catalog, closure)
        task_audit = _task_audit(record, environment, witness, history, necessity, closure)
        records.append(record)
        environments.append(environment)
        replay_bindings.append(replay_binding)
        witnesses.append(witness)
        observations.extend(history)
        necessities.append(necessity)
        counterfactuals.extend(task_counterfactuals)
        catalogs.append(catalog)
        closures.append(closure)
        admissions.append(admission)
        task_audits.append(task_audit)
        lineages.append(_lineage(source_record, record, replay_binding))

    if len({item.task_package.package_id for item in records}) != INSTRUMENT_TASK_COUNT:
        raise ValueError("Verifier-bound construction produced duplicate TaskPackages")
    evidence_ids = [
        item.evidence_id for record in records for item in record.public_corpus.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Verifier-bound Instrument tasks reuse Public Corpus Evidence")
    binding_by_source = {item.semantic_source_id: item for item in replay_bindings}
    for record in records:
        package = record.task_package
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        oracle_binding = package.task.oracle.selection_contract.get(
            "authority_preserving_verifier_v2_binding"
        )
        if (
            package.verifier_binding.verifier_implementation_id != binding.contract_id
            or package.verifier_binding.verifier_version != V26_VERIFIER_IMPLEMENTATION_VERSION
            or not isinstance(oracle_binding, Mapping)
            or oracle_binding.get("task_replay_binding_contract_id") != binding.contract_id
        ):
            raise ValueError("TaskPackage did not freeze its Verifier v2 Replay binding")

    freshness = _freshness_audit(
        development=development,
        report56=report56,
        report65=report65,
        report69=report69,
        sources=sources,
        selection_salt=selection_salt,
        prior_values=prior_values,
        selected_source_tasks=selected_source_tasks,
        prior_records=historical_records,
        selected_records=records,
    )
    ordered_lineages = tuple(sorted(lineages, key=lambda item: item.lineage_id))
    lineage_values = {"task_lineages": ordered_lineages}
    lineage_provisional = VerifierBoundLineageAudit.model_construct(
        audit_id="pending", **lineage_values
    )
    lineage_audit = VerifierBoundLineageAudit(
        audit_id=verifier_bound_lineage_audit_id(lineage_provisional),
        **lineage_values,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "freshness": output_dir / "source_freshness_audit.json",
        "capacity": output_dir / "definition_pair_capacity_audit.json",
        "reconciliation": output_dir / "reconciliation_selection_audit.json",
        "lineage": output_dir / "contract_lineage_audit.json",
        "records": output_dir / "operational_task_records.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "replay_bindings": output_dir / "verifier_v2_replay_bindings.json",
        "witnesses": output_dir / "operational_public_witnesses.json",
        "observations": output_dir / "operational_witness_observations.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "counterfactuals": output_dir / "mechanism_counterfactual_replays.json",
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "closures": output_dir / "operation_closure_audits.json",
        "admissions": output_dir / "operational_task_admissions.json",
        "audits": output_dir / "authority_preserving_task_audits.json",
    }
    _write_json(paths["freshness"], freshness.model_dump(mode="json"))
    _write_json(paths["capacity"], capacity_audit.model_dump(mode="json"))
    _write_json(paths["reconciliation"], reconciliation_selection.model_dump(mode="json"))
    _write_json(paths["lineage"], lineage_audit.model_dump(mode="json"))
    _write_models(paths["records"], records, "record_id")
    _write_models(paths["environments"], environments, "manifest_id")
    _write_models(paths["replay_bindings"], replay_bindings, "contract_id")
    _write_models(paths["witnesses"], witnesses, "witness_id")
    _write_models(paths["observations"], observations, "observation_id")
    _write_models(paths["necessities"], necessities, "artifact_id")
    _write_models(paths["counterfactuals"], counterfactuals, "replay_id")
    _write_models(paths["catalogs"], catalogs, "catalog_id")
    _write_models(paths["closures"], closures, "audit_id")
    _write_models(paths["admissions"], admissions, "admission_id")
    _write_models(paths["audits"], task_audits, "audit_id")
    counts = {
        "freshness": 1,
        "capacity": 1,
        "reconciliation": 1,
        "lineage": 1,
        "records": len(records),
        "environments": len(environments),
        "replay_bindings": len(replay_bindings),
        "witnesses": len(witnesses),
        "observations": len(observations),
        "necessities": len(necessities),
        "counterfactuals": len(counterfactuals),
        "catalogs": len(catalogs),
        "closures": len(closures),
        "admissions": len(admissions),
        "audits": len(task_audits),
    }
    immutable_files = tuple(
        _artifact_file(path, output_dir, counts[key]) for key, path in sorted(paths.items())
    )
    source_paths = (
        development_population_path,
        primary_source_path,
        secondary_source_path,
        tertiary_source_path,
        tertiary_no_api_report_path,
        v26_56_dir / "report.json",
        v26_56_dir / "rematerialized_task_records.json",
        v26_65_dir / "report.json",
        v26_65_dir / "operational_task_records.json",
        v26_69_dir / "report.json",
        v26_69_dir / "operational_task_records.json",
        verifier_qualification_dir / "report.json",
        verifier_qualification_dir / "replay_contract.json",
        snapshot_path,
        exposure_receipt_path,
    )
    source_files = tuple(
        sorted(
            (_source_file(path, package_root) for path in source_paths),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "run_id": run_id,
        "source_v26_69_report_id": report69.report_id,
        "source_v26_69_report_sha256": _sha256(v26_69_dir / "report.json"),
        "verifier_qualification_report_id": qualification.report_id,
        "verifier_qualification_report_sha256": qualification_sha256,
        "qualified_replay_contract_id": replay_contract.contract_id,
        "freshness_audit_id": freshness.audit_id,
        "reconciliation_selection_audit_id": reconciliation_selection.audit_id,
        "lineage_audit_id": lineage_audit.audit_id,
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "legacy_operation_mutation_count": sum(len(item.mutation_results) for item in closures),
        "task_record_ids": tuple(sorted(item.record_id for item in records)),
        "task_package_ids": tuple(sorted(item.task_package.package_id for item in records)),
        "environment_manifest_ids": tuple(sorted(item.manifest_id for item in environments)),
        "replay_binding_contract_ids": tuple(sorted(item.contract_id for item in replay_bindings)),
        "source_artifact_files": source_files,
        "immutable_artifact_files": immutable_files,
        "implementation_source_files": _implementation_source_files(package_root),
    }
    if not all(item.status == "passed" for item in necessities):
        raise ValueError("Verifier-bound Mechanism Necessity did not pass")
    if not all(item.status == "passed" for item in closures):
        raise ValueError("Verifier-bound Operation Closure did not pass")
    if not all(item.operational_capability_eligible for item in admissions):
        raise ValueError("Verifier-bound capability admission did not pass")
    if any(item.operational_vtdo_candidate_eligible for item in admissions):
        raise ValueError("Verifier-bound Instrument Population crossed empirical roles")
    provisional = VerifierBoundInstrumentPopulationReport.model_construct(
        report_id="pending", **values
    )
    report = VerifierBoundInstrumentPopulationReport(
        report_id=verifier_bound_population_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def verifier_bound_freshness_audit_id(value: VerifierBoundFreshnessAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_freshness:",
    )


def verifier_bound_reconciliation_selection_audit_id(
    value: VerifierBoundReconciliationSelectionAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_reconciliation_selection:",
    )


def verifier_bound_definition_pair_capacity_audit_id(
    value: VerifierBoundDefinitionPairCapacityAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_definition_pair_capacity:",
    )


def verifier_v2_task_replay_binding_id(value: VerifierV2TaskReplayBinding) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_verifier_v2_task_replay_binding:",
    )


def verifier_bound_task_lineage_id(value: VerifierBoundTaskLineage) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"lineage_id"}),
        prefix="finance_v26_verifier_bound_task_lineage:",
    )


def verifier_bound_lineage_audit_id(value: VerifierBoundLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_lineage_audit:",
    )


def verifier_bound_population_report_id(
    value: VerifierBoundInstrumentPopulationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_instrument_population_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.76 fresh Verifier-v2-bound Instrument Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--development-population", type=Path, required=True)
    parser.add_argument("--secondary-source", type=Path, required=True)
    parser.add_argument("--tertiary-source", type=Path, required=True)
    parser.add_argument("--tertiary-no-api-report", type=Path, required=True)
    parser.add_argument("--v26-56-dir", type=Path, required=True)
    parser.add_argument("--v26-65-dir", type=Path, required=True)
    parser.add_argument("--v26-69-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--exposure-receipt", type=Path, required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_verifier_bound_instrument_population(
        run_id=args.run_id,
        development_population_path=args.development_population,
        secondary_source_path=args.secondary_source,
        tertiary_source_path=args.tertiary_source,
        tertiary_no_api_report_path=args.tertiary_no_api_report,
        v26_56_dir=args.v26_56_dir,
        v26_65_dir=args.v26_65_dir,
        v26_69_dir=args.v26_69_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        snapshot_path=args.snapshot,
        exposure_receipt_path=args.exposure_receipt,
        selection_salt=args.selection_salt,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
