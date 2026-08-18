from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_support import MechanismNecessityArtifact
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
    AuthorityPreservingTaskAudit,
    SourceArtifactFile,
    TaskContractLineage,
    _harden_environment,
    _harden_record,
    _lineage,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    RematerializedExecutableTaskRecord,
    V26ExecutableTaskRematerializationReport,
    _base_draft,
    _load_definition_pairs,
    _reconciliation_draft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (  # noqa: E501
    ExposureCleanPopulationReceipt,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_builder import (  # noqa: E501
    _load_population,
    _merge_values,
    _record_evidence_values,
    _select_source_tasks,
    _source_task_values,
    _upgrade_task,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    FRESHNESS_CHANNELS,
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (  # noqa: E501
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

V26_FRESH_CAPABILITY_POPULATION_VERSION = "finance_v26_fresh_capability_population.v1"
V26_FRESH_CAPABILITY_FRESHNESS_VERSION = "finance_v26_fresh_capability_freshness.v1"
V26_CAPABILITY_RECONCILIATION_SELECTION_VERSION = (
    "finance_v26_capability_reconciliation_selection.v1"
)
V26_CAPABILITY_LINEAGE_AUDIT_VERSION = "finance_v26_capability_lineage_audit.v1"

CAPABILITY_TASKS_PER_MECHANISM: Literal[3] = 3
CAPABILITY_TASK_COUNT: Literal[12] = 12

IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    "src/trusted_synthesis/domains/finance/public_tool_results.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_operation_hardening.py"
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
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
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
FRESH_CAPABILITY_CHANNELS: tuple[FreshnessChannel, ...] = (
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


class FreshCapabilityChannelAudit(FrozenModel):
    channel: FreshnessChannel
    prior_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)
    overlap_values: tuple[str, ...] = ()
    overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> FreshCapabilityChannelAudit:
        if self.overlap_values:
            raise ValueError("fresh capability channel contains prior identities")
        return self


class FreshCapabilityFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    v26_56_report_id: str = Field(min_length=1)
    v26_65_report_id: str = Field(min_length=1)
    source_population_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    selection_salt: str = Field(min_length=1)
    channels: tuple[FreshCapabilityChannelAudit, ...] = Field(min_length=8, max_length=8)
    selected_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    selected_nonreconciliation_source_task_count: Literal[9] = 9
    selected_reconciliation_evidence_count: Literal[12] = 12
    selected_source_record_overlap_count: Literal[0] = 0
    source_container_reuse_policy: Literal[
        "immutable_container_shared_rows_must_be_identity_disjoint"
    ] = "immutable_container_shared_rows_must_be_identity_disjoint"
    historical_model_outcomes_used_for_selection: Literal[False] = False
    historical_trajectory_reuse_forbidden: Literal[True] = True
    generated_trajectory_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_FRESH_CAPABILITY_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FreshCapabilityFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESH_CAPABILITY_CHANNELS:
            raise ValueError("fresh capability channels are incomplete or noncanonical")
        if self.source_population_ids != tuple(sorted(set(self.source_population_ids))):
            raise ValueError("fresh capability source populations are not canonical")
        if self.audit_id != fresh_capability_freshness_audit_id(self):
            raise ValueError("fresh capability freshness identity is invalid")
        return self


class CapabilityReconciliationSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_capacity_audit_id: str = Field(min_length=1)
    eligible_definition_pair_count: int = Field(ge=6)
    eligible_reconciliation_task_capacity: int = Field(ge=3)
    source_selected_pair_count: Literal[12] = 12
    capability_selected_pair_count: Literal[6] = 6
    capability_task_count: Literal[3] = 3
    selected_evidence_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    selection_policy: Literal[
        "first_six_canonical_period_order_from_frozen_twelve_pair_capacity_selection"
    ] = "first_six_canonical_period_order_from_frozen_twelve_pair_capacity_selection"
    status: Literal["passed"] = "passed"
    schema_version: str = V26_CAPABILITY_RECONCILIATION_SELECTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityReconciliationSelectionAudit:
        if self.selected_evidence_ids != tuple(sorted(set(self.selected_evidence_ids))):
            raise ValueError("capability Reconciliation Evidence is duplicated")
        if self.audit_id != capability_reconciliation_selection_audit_id(self):
            raise ValueError("capability Reconciliation selection identity is invalid")
        return self


class CapabilityContractLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_lineages: tuple[TaskContractLineage, ...] = Field(min_length=12, max_length=12)
    source_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    hardened_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    source_model_outcome_count: Literal[0] = 0
    source_model_outcomes_used: Literal[False] = False
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_CAPABILITY_LINEAGE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityContractLineageAudit:
        if tuple(item.lineage_id for item in self.task_lineages) != tuple(
            sorted(item.lineage_id for item in self.task_lineages)
        ):
            raise ValueError("capability task lineages are not canonical")
        if self.audit_id != capability_contract_lineage_audit_id(self):
            raise ValueError("capability lineage audit identity is invalid")
        return self


class FreshCapabilityPopulationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    reconciliation_selection_audit_id: str = Field(min_length=1)
    lineage_audit_id: str = Field(min_length=1)
    mechanism_task_counts: dict[str, int]
    task_count: Literal[12] = CAPABILITY_TASK_COUNT
    capability_task_count: Literal[12] = CAPABILITY_TASK_COUNT
    vtdo_candidate_task_count: Literal[0] = 0
    fresh_task_package_count: Literal[12] = CAPABILITY_TASK_COUNT
    action_neutral_repair_contract_count: Literal[12] = CAPABILITY_TASK_COUNT
    terminal_verification_target_count: Literal[12] = CAPABILITY_TASK_COUNT
    repair_prompt_audit_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    terminal_verification_audit_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    operation_closure_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    public_witness_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    compiler_generated_witness_count: Literal[12] = CAPABILITY_TASK_COUNT
    compiler_witness_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    mechanism_necessity_pass_count: Literal[12] = CAPABILITY_TASK_COUNT
    operational_capability_eligible_count: Literal[12] = CAPABILITY_TASK_COUNT
    operational_vtdo_candidate_eligible_count: Literal[0] = 0
    static_model_authority_path_count: Literal[0] = 0
    legacy_operation_mutation_count: int = Field(ge=96)
    authority_verification_mutation_count: Literal[60] = 60
    task_records: tuple[OperationalTaskRecord, ...] = Field(min_length=12, max_length=12)
    admissions: tuple[OperationalTaskAdmission, ...] = Field(min_length=12, max_length=12)
    task_audits: tuple[AuthorityPreservingTaskAudit, ...] = Field(min_length=12, max_length=12)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=10)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=14)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=11, max_length=11
    )
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["authority_preserving_role_runner_preflight_only"] = (
        "authority_preserving_role_runner_preflight_only"
    )
    role_runner_preflight_authorized: Literal[True] = True
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_FRESH_CAPABILITY_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FreshCapabilityPopulationReport:
        if self.mechanism_task_counts != {
            mechanism: CAPABILITY_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("fresh capability mechanism quotas changed")
        groups = (
            tuple(item.record_id for item in self.task_records),
            tuple(item.admission_id for item in self.admissions),
            tuple(item.audit_id for item in self.task_audits),
        )
        if any(group != tuple(sorted(group)) for group in groups):
            raise ValueError("fresh capability report details are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("fresh capability implementation manifest is incomplete")
        if self.report_id != fresh_capability_population_report_id(self):
            raise ValueError("fresh capability report identity is invalid")
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
            raise ValueError(f"fresh capability immutable JSON changed: {path}")
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


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
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


def _operational_record_values(
    records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
) -> dict[str, set[str]]:
    return {
        "source_task_artifact_id": {
            value for record in records for value in record.source_task_artifact_ids
        },
        "source_task_semantic_signature": set(),
        "source_task_hash": set(),
        "evidence_id": {
            item.evidence_id for record in records for item in record.public_corpus.evidence
        },
        "evidence_version_id": {
            item.evidence_version_id for record in records for item in record.public_corpus.evidence
        },
        "source_record_id": {
            item.provenance.source_record_id
            for record in records
            for item in record.public_corpus.evidence
        },
    }


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def _replay_manifested_files(
    source_dir: Path,
    descriptors: Sequence[Any],
) -> None:
    for item in descriptors:
        path = source_dir / item.relative_path
        if (
            not path.is_file()
            or _sha256(path) != item.sha256
            or _record_count(path) != item.record_count
        ):
            raise ValueError(f"fresh capability source Artifact replay failed: {path}")


def _freshness_audit(
    *,
    development: V26FreshTaskPopulation,
    report56: V26ExecutableTaskRematerializationReport,
    report65: AuthorityPreservingHardeningReport,
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    selection_salt: str,
    prior_values: Mapping[str, set[str]],
    selected_source_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    prior_records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
    selected_records: Sequence[OperationalTaskRecord],
) -> FreshCapabilityFreshnessAudit:
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
        **{channel: set(prior_values[channel]) for channel in FRESHNESS_CHANNELS},
        "semantic_source_id": {
            item.task_package.semantic_source.semantic_source_id for item in prior_records
        },
        "task_package_id": {item.task_package.package_id for item in prior_records},
    }
    channels = []
    for channel in FRESH_CAPABILITY_CHANNELS:
        prior_items = tuple(sorted(prior[channel]))
        selected_items = tuple(sorted(selected[channel]))
        overlap = tuple(sorted(set(prior_items) & set(selected_items)))
        if overlap:
            raise ValueError(f"fresh capability channel {channel} overlaps historical inputs")
        channels.append(
            FreshCapabilityChannelAudit(
                channel=channel,
                prior_count=len(prior_items),
                selected_count=len(selected_items),
                prior_set_hash=canonical_hash(
                    {"channel": channel, "values": prior_items},
                    prefix="finance_v26_capability_prior_set:",
                ),
                selected_set_hash=canonical_hash(
                    {"channel": channel, "values": selected_items},
                    prefix="finance_v26_capability_selected_set:",
                ),
                overlap_values=(),
                overlap_count=0,
            )
        )
    values = {
        "development_population_id": development.population_id,
        "v26_56_report_id": report56.report_id,
        "v26_65_report_id": report65.report_id,
        "source_population_ids": tuple(sorted(item.population_id for item in sources)),
        "selection_salt": selection_salt,
        "channels": tuple(channels),
        "selected_reconciliation_evidence_count": sum(
            len(item.public_corpus.evidence)
            for item in selected_records
            if item.mechanism_id == "semantic_reconciliation"
        ),
    }
    provisional = FreshCapabilityFreshnessAudit.model_construct(audit_id="pending", **values)
    return FreshCapabilityFreshnessAudit(
        audit_id=fresh_capability_freshness_audit_id(provisional),
        **values,
    )


def build_fresh_capability_population(
    *,
    run_id: str,
    development_population_path: Path,
    secondary_source_path: Path,
    tertiary_source_path: Path,
    tertiary_no_api_report_path: Path,
    v26_56_dir: Path,
    v26_65_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
    selection_salt: str,
    output_dir: Path,
    package_root: Path,
) -> FreshCapabilityPopulationReport:
    development = V26FreshTaskPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    if development.phase != "development":
        raise ValueError("fresh capability source is not the frozen Development role")
    development_tasks = load_v26_selected_source_tasks(development)
    primary_source_path = Path(development.source_population_path)
    if _sha256(primary_source_path) != development.source_population_sha256:
        raise ValueError("fresh capability primary source Population replay failed")
    sources = (
        _load_population(primary_source_path),
        _load_population(secondary_source_path),
        _load_population(tertiary_source_path),
    )
    if len({item.population_id for item in sources}) != 3:
        raise ValueError("fresh capability requires three independently identified sources")
    tertiary_receipt = json.loads(tertiary_no_api_report_path.read_text(encoding="utf-8"))
    expected_tertiary = (
        tertiary_no_api_report_path.parent / "population" / "confirmation_source.json"
    )
    if (
        tertiary_receipt.get("model_api_calls") != 0
        or tertiary_receipt.get("gpu_jobs") != 0
        or tertiary_source_path.resolve() != expected_tertiary.resolve()
    ):
        raise ValueError("fresh capability tertiary source lacks a zero-API receipt")

    report56 = V26ExecutableTaskRematerializationReport.model_validate_json(
        (v26_56_dir / "report.json").read_text(encoding="utf-8")
    )
    records56 = tuple(
        RematerializedExecutableTaskRecord.model_validate(item)
        for item in json.loads(
            (v26_56_dir / "rematerialized_task_records.json").read_text(encoding="utf-8")
        )
    )
    _replay_manifested_files(v26_56_dir, report56.immutable_artifact_files)
    report65 = AuthorityPreservingHardeningReport.model_validate_json(
        (v26_65_dir / "report.json").read_text(encoding="utf-8")
    )
    records65 = tuple(
        OperationalTaskRecord.model_validate(item)
        for item in json.loads(
            (v26_65_dir / "operational_task_records.json").read_text(encoding="utf-8")
        )
    )
    _replay_manifested_files(v26_65_dir, report65.immutable_artifact_files)

    all_source_tasks = tuple(item for source in sources for item in source.tasks)
    source_by_id = {item.artifact_id: item for item in all_source_tasks}
    historical_source_ids = {
        value for record in (*records56, *records65) for value in record.source_task_artifact_ids
    }
    historical_source_tasks = tuple(
        source_by_id[value] for value in sorted(historical_source_ids) if value in source_by_id
    )
    prior_values = _merge_values(
        _source_task_values(development_tasks),
        _source_task_values(historical_source_tasks),
        _record_evidence_values(records56),
        _operational_record_values(records65),
    )
    selected_pool = _select_source_tasks(
        sources,
        excluded=prior_values,
        sampling_salt=selection_salt,
    )
    selected_by_mechanism = {
        mechanism: selected_pool[mechanism][:CAPABILITY_TASKS_PER_MECHANISM]
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
    if Path(
        receipt.source_artifacts_path
    ).resolve() != snapshot_path.resolve() or receipt.source_artifacts_sha256 != _sha256(
        snapshot_path
    ):
        raise ValueError("fresh capability Snapshot differs from its exposure receipt")
    definition_pairs, capacity_audit = _load_definition_pairs(
        snapshot_path=snapshot_path,
        receipt=receipt,
        exposure_receipt_path=exposure_receipt_path,
        additional_excluded_ids=prior_values["evidence_id"] | base_selected_evidence_ids,
        sampling_salt=selection_salt,
    )
    capability_pairs = definition_pairs[:6]
    pair_evidence_ids = tuple(
        sorted(item.evidence_id for pair in capability_pairs for item in pair.evidence)
    )
    selection_values = {
        "source_capacity_audit_id": capacity_audit.audit_id,
        "eligible_definition_pair_count": capacity_audit.eligible_definition_pair_count,
        "eligible_reconciliation_task_capacity": (
            capacity_audit.eligible_reconciliation_task_capacity
        ),
        "selected_evidence_ids": pair_evidence_ids,
    }
    selection_provisional = CapabilityReconciliationSelectionAudit.model_construct(
        audit_id="pending", **selection_values
    )
    reconciliation_selection = CapabilityReconciliationSelectionAudit(
        audit_id=capability_reconciliation_selection_audit_id(selection_provisional),
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
                _base_draft(
                    task,
                    mechanism_id=mechanism,
                    intended_use="capability_measurement",
                )
            )
    for index in range(CAPABILITY_TASKS_PER_MECHANISM):
        drafts.append(
            _reconciliation_draft(
                capability_pairs[index * 2],
                capability_pairs[index * 2 + 1],
                intended_use="capability_measurement",
            )
        )
    drafts.sort(key=lambda item: (TARGET_MECHANISMS.index(item.mechanism_id), item.instruction))
    if Counter(item.mechanism_id for item in drafts) != Counter(
        {mechanism: CAPABILITY_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("fresh capability draft quotas are incomplete")

    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    closures: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    task_audits: list[AuthorityPreservingTaskAudit] = []
    lineages: list[TaskContractLineage] = []
    for draft in drafts:
        source_record, source_environment = _upgrade_task(draft)
        environment = _harden_environment(source_environment)
        record = _harden_record(source_record, environment)
        witness, history = compile_operational_witness(
            record,
            environment,
            strategy="structured_direct",
        )
        necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
            record,
            (witness,),
        )
        closure = build_operation_closure_audit(
            record,
            (witness,),
            (history,),
            necessity,
            catalog,
        )
        admission = build_operational_admission(
            record,
            witness,
            necessity,
            catalog,
            closure,
        )
        task_audit = _task_audit(
            record,
            environment,
            witness,
            history,
            necessity,
            closure,
        )
        records.append(record)
        environments.append(environment)
        witnesses.append(witness)
        observations.extend(history)
        necessities.append(necessity)
        counterfactuals.extend(task_counterfactuals)
        catalogs.append(catalog)
        closures.append(closure)
        admissions.append(admission)
        task_audits.append(task_audit)
        lineages.append(_lineage(source_record, record))

    if len({item.task_package.package_id for item in records}) != CAPABILITY_TASK_COUNT:
        raise ValueError("fresh capability produced duplicate TaskPackage identities")
    evidence_ids = [
        item.evidence_id for record in records for item in record.public_corpus.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("fresh capability tasks reuse Public Corpus Evidence")
    if any(item.intended_use != "capability_measurement" for item in records):
        raise ValueError("fresh capability Population contains another registered role")
    if any(item.paths or item.status != "not_required" for item in catalogs):
        raise ValueError("fresh capability task unexpectedly carries a VTDO path catalog")

    freshness = _freshness_audit(
        development=development,
        report56=report56,
        report65=report65,
        sources=sources,
        selection_salt=selection_salt,
        prior_values=prior_values,
        selected_source_tasks=selected_source_tasks,
        prior_records=(*records56, *records65),
        selected_records=records,
    )
    ordered_lineages = tuple(sorted(lineages, key=lambda item: item.lineage_id))
    lineage_values = {"task_lineages": ordered_lineages}
    lineage_provisional = CapabilityContractLineageAudit.model_construct(
        audit_id="pending", **lineage_values
    )
    lineage_audit = CapabilityContractLineageAudit(
        audit_id=capability_contract_lineage_audit_id(lineage_provisional),
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
        "freshness_audit_id": freshness.audit_id,
        "reconciliation_selection_audit_id": reconciliation_selection.audit_id,
        "lineage_audit_id": lineage_audit.audit_id,
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "legacy_operation_mutation_count": sum(len(item.mutation_results) for item in closures),
        "task_records": tuple(sorted(records, key=lambda item: item.record_id)),
        "admissions": tuple(sorted(admissions, key=lambda item: item.admission_id)),
        "task_audits": tuple(sorted(task_audits, key=lambda item: item.audit_id)),
        "source_artifact_files": source_files,
        "immutable_artifact_files": immutable_files,
        "implementation_source_files": _implementation_source_files(package_root),
    }
    if not all(item.status == "passed" for item in necessities):
        raise ValueError("fresh capability Mechanism Necessity did not pass")
    if not all(item.status == "passed" for item in closures):
        raise ValueError("fresh capability Operation Closure did not pass")
    if not all(item.operational_capability_eligible for item in admissions):
        raise ValueError("fresh capability admission did not pass")
    if any(item.operational_vtdo_candidate_eligible for item in admissions):
        raise ValueError("fresh capability admission crossed empirical roles")
    provisional = FreshCapabilityPopulationReport.model_construct(report_id="pending", **values)
    report = FreshCapabilityPopulationReport(
        report_id=fresh_capability_population_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def fresh_capability_freshness_audit_id(value: FreshCapabilityFreshnessAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_fresh_capability_freshness:",
    )


def capability_reconciliation_selection_audit_id(
    value: CapabilityReconciliationSelectionAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_capability_reconciliation_selection:",
    )


def capability_contract_lineage_audit_id(value: CapabilityContractLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_capability_lineage_audit:",
    )


def fresh_capability_population_report_id(value: FreshCapabilityPopulationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_fresh_capability_population_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.69 fresh authority-preserving Capability Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--development-population", type=Path, required=True)
    parser.add_argument("--secondary-source", type=Path, required=True)
    parser.add_argument("--tertiary-source", type=Path, required=True)
    parser.add_argument("--tertiary-no-api-report", type=Path, required=True)
    parser.add_argument("--v26-56-dir", type=Path, required=True)
    parser.add_argument("--v26-65-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--exposure-receipt", type=Path, required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_fresh_capability_population(
        run_id=args.run_id,
        development_population_path=args.development_population,
        secondary_source_path=args.secondary_source,
        tertiary_source_path=args.tertiary_source,
        tertiary_no_api_report_path=args.tertiary_no_api_report,
        v26_56_dir=args.v26_56_dir,
        v26_65_dir=args.v26_65_dir,
        snapshot_path=args.snapshot,
        exposure_receipt_path=args.exposure_receipt,
        selection_salt=args.selection_salt,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
