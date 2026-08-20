from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

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
    _harden_environment,
    _harden_record,
    _task_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
    compiler_witness_trajectory,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    RematerializedExecutableTaskRecord,
    V26ExecutableTaskRematerializationReport,
    _base_draft,
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
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (  # noqa: E501
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    FRESHNESS_CHANNELS,
    VerifierBoundInstrumentPopulationReport,
    VerifierBoundLineageAudit,
    VerifierBoundReconciliationSelectionAudit,
    VerifierBoundTaskLineage,
    VerifierV2TaskReplayBinding,
    _artifact_file,
    _bind_verifier_v2,
    _lineage,
    _load_and_replay_fresh_capability,
    _load_and_replay_verifier_qualification,
    _load_instrument_definition_pairs,
    _load_rows,
    _replay_manifested_files,
    _source_file,
    _task_replay_binding,
    _verifier_bound_environment,
    _write_json,
    _write_models,
    verifier_bound_lineage_audit_id,
    verifier_bound_reconciliation_selection_audit_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    IMPLEMENTATION_SOURCE_PATHS as V26_76_IMPLEMENTATION_SOURCE_PATHS,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    make_provider_token_budget_contract,
)
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_BUDGET_CLOSED_POPULATION_VERSION = (
    "finance_v26_budget_closed_verifier_bound_instrument_population.v1"
)
V26_BUDGET_CLOSED_FRESHNESS_VERSION = "finance_v26_budget_closed_verifier_bound_freshness.v1"

INSTRUMENT_TASK_COUNT: Literal[8] = 8
INSTRUMENT_TASKS_PER_MECHANISM: Literal[2] = 2
MAXIMUM_MODEL_TOKENS_PER_ROLLOUT: Literal[120000] = 120000
MAXIMUM_PROMPT_UTF8_BYTES: Literal[60000] = 60000
MAXIMUM_OUTPUT_TOKENS: Literal[4096] = 4096
PROVIDER_CHAT_ENVELOPE_TOKEN_UPPER_BOUND: Literal[256] = 256
CONTRACT_REPAIR_RESERVE_TOKENS: Literal[4096] = 4096
FINAL_ANSWER_RESERVE_TOKENS: Literal[4096] = 4096

IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            *V26_76_IMPLEMENTATION_SOURCE_PATHS,
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_closed_instrument.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_closed_task_rematerialization.py"
            ),
            "src/trusted_synthesis/runtime/agent/budget_closed.py",
        }
    )
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetClosedFreshnessChannelAudit(FrozenModel):
    channel: str = Field(min_length=1)
    prior_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)
    overlap_values: tuple[str, ...] = ()
    overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> BudgetClosedFreshnessChannelAudit:
        if self.channel not in FRESHNESS_CHANNELS:
            raise ValueError("budget-closed freshness contains an unknown channel")
        if self.overlap_values:
            raise ValueError("budget-closed freshness contains exposed identities")
        return self


class BudgetClosedFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    v26_56_report_id: str = Field(min_length=1)
    v26_65_report_id: str = Field(min_length=1)
    v26_69_report_id: str = Field(min_length=1)
    v26_76_report_id: str = Field(min_length=1)
    source_population_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    selection_salt: str = Field(min_length=1)
    channels: tuple[BudgetClosedFreshnessChannelAudit, ...] = Field(min_length=8, max_length=8)
    selected_task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    selected_nonreconciliation_source_task_count: Literal[6] = 6
    selected_reconciliation_evidence_count: Literal[8] = 8
    v26_76_task_package_exclusion_count: Literal[8] = 8
    v26_76_empirical_task_exposure_complete: Literal[True] = True
    historical_model_outcomes_used_for_selection: Literal[False] = False
    v26_81_diagnostic_candidates_used_for_selection: Literal[False] = False
    historical_trajectory_reuse_forbidden: Literal[True] = True
    generated_trajectory_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_CLOSED_FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetClosedFreshnessAudit:
        if tuple(item.channel for item in self.channels) != FRESHNESS_CHANNELS:
            raise ValueError("budget-closed freshness channels are incomplete")
        if self.source_population_ids != tuple(sorted(set(self.source_population_ids))):
            raise ValueError("budget-closed source Populations are not canonical")
        if self.audit_id != budget_closed_freshness_audit_id(self):
            raise ValueError("budget-closed freshness identity is invalid")
        return self


class BudgetClosedInstrumentPopulationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_v26_76_report_id: str = Field(min_length=1)
    source_v26_76_report_sha256: str = Field(min_length=64, max_length=64)
    verifier_qualification_report_id: str = Field(min_length=1)
    verifier_qualification_report_sha256: str = Field(min_length=64, max_length=64)
    qualified_replay_contract_id: str = Field(min_length=1)
    provider_token_budget_contract_id: str = Field(min_length=1)
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
    compiler_runtime_witness_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_replay_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_completed_scoring_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_trace_sidecar_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_witness_observation_count: int = Field(ge=64)
    compiler_empirical_row_count: Literal[0] = 0
    operation_closure_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    mechanism_necessity_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    operational_capability_eligible_count: Literal[8] = INSTRUMENT_TASK_COUNT
    legacy_operation_mutation_count: int = Field(ge=64)
    authority_verification_mutation_count: Literal[40] = 40
    task_record_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    task_package_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    environment_manifest_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    replay_binding_contract_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    compiler_trajectory_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    compiler_score_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=17)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(
        min_length=18, max_length=18
    )
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=18, max_length=18
    )
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    historical_diagnostic_candidates_reused: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["budget_closed_verifier_bound_instrument_preflight_only"] = (
        "budget_closed_verifier_bound_instrument_preflight_only"
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
    schema_version: str = V26_BUDGET_CLOSED_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetClosedInstrumentPopulationReport:
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("budget-closed Instrument mechanism quotas changed")
        groups = (
            self.task_record_ids,
            self.task_package_ids,
            self.environment_manifest_ids,
            self.replay_binding_contract_ids,
            self.compiler_trajectory_ids,
            self.compiler_score_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("budget-closed report identity sets are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != (
            IMPLEMENTATION_SOURCE_PATHS
        ):
            raise ValueError("budget-closed implementation manifest is incomplete")
        expected_details = (
            "authority_preserving_task_audits.json",
            "compiler_trajectories.json",
            "completed_compiler_trajectory_scores.json",
            "contract_lineage_audit.json",
            "definition_pair_capacity_audit.json",
            "mechanism_counterfactual_replays.json",
            "mechanism_necessity_artifacts.json",
            "operation_closure_audits.json",
            "operational_public_witnesses.json",
            "operational_task_admissions.json",
            "operational_task_records.json",
            "operational_witness_observations.json",
            "provider_token_budget_contract.json",
            "reconciliation_selection_audit.json",
            "source_freshness_audit.json",
            "static_model_authority_path_catalogs.json",
            "tool_environment_manifests.json",
            "verifier_v2_replay_bindings.json",
        )
        if tuple(item.relative_path for item in self.immutable_artifact_files) != (
            expected_details
        ):
            raise ValueError("budget-closed detail manifest is incomplete")
        if self.report_id != budget_closed_population_report_id(self):
            raise ValueError("budget-closed Population report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=path, sha256=_sha256(package_root / path))
        for path in IMPLEMENTATION_SOURCE_PATHS
    )


def _select_nonreconciliation_tasks(
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    *,
    excluded: Mapping[str, set[str]],
    sampling_salt: str,
) -> dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]]:
    output: dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    selected_evidence_ids: set[str] = set()
    selected_evidence_versions: set[str] = set()
    selected_source_records: set[str] = set()
    mechanisms = (
        "context_conditioned_action",
        "failure_recovery",
        "state_dependent_stopping",
    )
    for mechanism in mechanisms:
        family = MECHANISM_SOURCE_FAMILY[mechanism]
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
                prefix="finance_v26_budget_closed_source_rank:",
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


def _freshness_audit(
    *,
    development: V26FreshTaskPopulation,
    report56: V26ExecutableTaskRematerializationReport,
    report65: AuthorityPreservingHardeningReport,
    report69: FreshCapabilityPopulationReport,
    report76: VerifierBoundInstrumentPopulationReport,
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    selection_salt: str,
    prior_values: Mapping[str, set[str]],
    selected_source_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    prior_records: Sequence[OperationalTaskRecord | RematerializedExecutableTaskRecord],
    selected_records: Sequence[OperationalTaskRecord],
) -> BudgetClosedFreshnessAudit:
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
            raise ValueError(f"budget-closed freshness channel {channel} overlaps history")
        channels.append(
            BudgetClosedFreshnessChannelAudit(
                channel=channel,
                prior_count=len(prior_items),
                selected_count=len(selected_items),
                prior_set_hash=canonical_hash(
                    {"channel": channel, "values": prior_items},
                    prefix="finance_v26_budget_closed_prior_set:",
                ),
                selected_set_hash=canonical_hash(
                    {"channel": channel, "values": selected_items},
                    prefix="finance_v26_budget_closed_selected_set:",
                ),
            )
        )
    values = {
        "development_population_id": development.population_id,
        "v26_56_report_id": report56.report_id,
        "v26_65_report_id": report65.report_id,
        "v26_69_report_id": report69.report_id,
        "v26_76_report_id": report76.report_id,
        "source_population_ids": tuple(sorted(item.population_id for item in sources)),
        "selection_salt": selection_salt,
        "channels": tuple(channels),
    }
    provisional = BudgetClosedFreshnessAudit.model_construct(audit_id="pending", **values)
    return BudgetClosedFreshnessAudit(
        audit_id=budget_closed_freshness_audit_id(provisional),
        **values,
    )


def build_budget_closed_instrument_population(
    *,
    run_id: str,
    development_population_path: Path,
    secondary_source_path: Path,
    tertiary_source_path: Path,
    tertiary_no_api_report_path: Path,
    quaternary_source_path: Path,
    quaternary_no_api_report_path: Path,
    v26_56_dir: Path,
    v26_65_dir: Path,
    v26_69_dir: Path,
    v26_76_dir: Path,
    verifier_qualification_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
    selection_salt: str,
    output_dir: Path,
    package_root: Path,
) -> BudgetClosedInstrumentPopulationReport:
    development = V26FreshTaskPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    if development.phase != "development":
        raise ValueError("budget-closed source is not the frozen Development role")
    development_tasks = load_v26_selected_source_tasks(development)
    primary_source_path = Path(development.source_population_path)
    if _sha256(primary_source_path) != development.source_population_sha256:
        raise ValueError("budget-closed primary source Population replay failed")
    sources = (
        _load_population(primary_source_path),
        _load_population(secondary_source_path),
        _load_population(tertiary_source_path),
        _load_population(quaternary_source_path),
    )
    if len({item.population_id for item in sources}) != 4:
        raise ValueError("budget-closed construction requires four source Populations")
    for source_path, receipt_path in (
        (tertiary_source_path, tertiary_no_api_report_path),
        (quaternary_source_path, quaternary_no_api_report_path),
    ):
        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected_source = receipt_path.parent / "population" / "confirmation_source.json"
        if (
            receipt_payload.get("model_api_calls") != 0
            or receipt_payload.get("gpu_jobs") != 0
            or source_path.resolve() != expected_source.resolve()
        ):
            raise ValueError("budget-closed additional source lacks its zero-API receipt")

    report56 = V26ExecutableTaskRematerializationReport.model_validate_json(
        (v26_56_dir / "report.json").read_text(encoding="utf-8")
    )
    records56 = _load_rows(
        v26_56_dir / "rematerialized_task_records.json",
        RematerializedExecutableTaskRecord,
    )
    _replay_manifested_files(v26_56_dir, report56.immutable_artifact_files)
    report65 = AuthorityPreservingHardeningReport.model_validate_json(
        (v26_65_dir / "report.json").read_text(encoding="utf-8")
    )
    records65 = _load_rows(
        v26_65_dir / "operational_task_records.json",
        OperationalTaskRecord,
    )
    _replay_manifested_files(v26_65_dir, report65.immutable_artifact_files)
    report69, records69 = _load_and_replay_fresh_capability(v26_69_dir, package_root)
    report76 = VerifierBoundInstrumentPopulationReport.model_validate_json(
        (v26_76_dir / "report.json").read_text(encoding="utf-8")
    )
    records76 = _load_rows(
        v26_76_dir / "operational_task_records.json",
        OperationalTaskRecord,
    )
    _replay_manifested_files(v26_76_dir, report76.immutable_artifact_files)
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        verifier_qualification_dir, package_root
    )
    qualification_path = verifier_qualification_dir / "report.json"
    qualification_sha256 = _sha256(qualification_path)

    all_source_tasks = tuple(item for source in sources for item in source.tasks)
    source_by_id = {item.artifact_id: item for item in all_source_tasks}
    historical_records = (*records56, *records65, *records69, *records76)
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
        _operational_record_values((*records65, *records69, *records76)),
    )
    selected_by_mechanism = _select_nonreconciliation_tasks(
        sources,
        excluded=prior_values,
        sampling_salt=selection_salt,
    )
    selected_source_tasks = tuple(
        item
        for mechanism in (
            "context_conditioned_action",
            "failure_recovery",
            "state_dependent_stopping",
        )
        for item in selected_by_mechanism[cast(TargetMechanism, mechanism)]
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
        raise ValueError("budget-closed Snapshot differs from its exposure receipt")
    definition_pairs, capacity_audit = _load_instrument_definition_pairs(
        snapshot_path=snapshot_path,
        receipt=receipt,
        exposure_receipt_path=exposure_receipt_path,
        additional_excluded_ids=(prior_values["evidence_id"] | base_selected_evidence_ids),
        sampling_salt=selection_salt,
    )
    instrument_pairs = definition_pairs[:4]
    selected_pair_evidence_ids = tuple(
        sorted(item.evidence_id for pair in instrument_pairs for item in pair.evidence)
    )
    selection_values = {
        "source_capacity_audit_id": capacity_audit.audit_id,
        "eligible_definition_pair_count": (capacity_audit.eligible_definition_pair_count),
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
        for task in selected_by_mechanism[cast(TargetMechanism, mechanism)]:
            drafts.append(
                _base_draft(
                    task,
                    mechanism_id=mechanism,
                    intended_use="capability_measurement",
                )
            )
    for index in range(INSTRUMENT_TASKS_PER_MECHANISM):
        drafts.append(
            _reconciliation_draft(
                instrument_pairs[index * 2],
                instrument_pairs[index * 2 + 1],
                intended_use="capability_measurement",
            )
        )
    drafts.sort(
        key=lambda item: (
            TARGET_MECHANISMS.index(item.mechanism_id),
            item.instruction,
        )
    )
    if Counter(item.mechanism_id for item in drafts) != Counter(
        {mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("budget-closed Instrument draft quotas are incomplete")

    budget_contract = make_provider_token_budget_contract(
        provider="deepseek",
        model_id="deepseek-v4-flash",
        maximum_total_tokens=MAXIMUM_MODEL_TOKENS_PER_ROLLOUT,
        maximum_prompt_utf8_bytes=MAXIMUM_PROMPT_UTF8_BYTES,
        maximum_output_tokens=MAXIMUM_OUTPUT_TOKENS,
        provider_chat_envelope_token_upper_bound=(PROVIDER_CHAT_ENVELOPE_TOKEN_UPPER_BOUND),
        contract_repair_reserve_tokens=CONTRACT_REPAIR_RESERVE_TOKENS,
        final_answer_reserve_tokens=FINAL_ANSWER_RESERVE_TOKENS,
    )

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
    compiler_trajectories = []
    compiler_scores: list[CompletedTrajectoryScore] = []
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
        replay = replay_authority_preserving_observations(
            replay_contract,
            record,
            environment,
            history,
        )
        if not replay.passed:
            raise ValueError("budget-closed Compiler Witness failed Verifier v2 Replay")
        trajectory = compiler_witness_trajectory(
            record=record,
            environment=environment,
            witness=witness,
            observations=history,
        )
        score = score_completed_trajectory(
            trajectory=trajectory,
            source_kind="compiler_fixture",
            replay_result_id=replay.replay_id,
            replay_passed=replay.passed,
            non_replay_checks={
                "action_neutral_repair": task_audit.repair_prompt_audit.status == "passed",
                "answer_projection": witness.answer_projection_complete,
                "citation": witness.citation_complete,
                "evidence_support": witness.evidence_support_complete,
                "mechanism": witness.mechanism_complete,
                "no_postcompletion_violation": (witness.no_postcompletion_violation),
                "operation_lineage": witness.operation_lineage_complete,
                "stop_readiness": task_audit.runtime_witness_stop_ready,
                "terminal_target": task_audit.exact_terminal_reference_accepted,
                "verification": witness.verification_complete,
            },
            independent_valid=witness.full_validity_passed,
            resource_budget_audit_id=budget_contract.contract_id,
            resource_budget_status="not_applicable_no_provider_calls",
        )
        if (
            score.core_terminal != "valid_trajectory"
            or not score.instrument_admitted
            or score.trace_sidecar is None
        ):
            raise ValueError("budget-closed Compiler completed scoring failed")
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
        compiler_trajectories.append(trajectory)
        compiler_scores.append(score)

    if len({item.task_package.package_id for item in records}) != INSTRUMENT_TASK_COUNT:
        raise ValueError("budget-closed construction produced duplicate TaskPackages")
    evidence_ids = [
        item.evidence_id for record in records for item in record.public_corpus.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("budget-closed Instrument tasks reuse Public Corpus Evidence")
    if set(report76.task_package_ids) & {item.task_package.package_id for item in records}:
        raise ValueError("budget-closed TaskPackages reuse v26.76 identities")

    freshness = _freshness_audit(
        development=development,
        report56=report56,
        report65=report65,
        report69=report69,
        report76=report76,
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
        "audits": output_dir / "authority_preserving_task_audits.json",
        "scores": output_dir / "completed_compiler_trajectory_scores.json",
        "trajectories": output_dir / "compiler_trajectories.json",
        "lineage": output_dir / "contract_lineage_audit.json",
        "capacity": output_dir / "definition_pair_capacity_audit.json",
        "counterfactuals": output_dir / "mechanism_counterfactual_replays.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "closures": output_dir / "operation_closure_audits.json",
        "witnesses": output_dir / "operational_public_witnesses.json",
        "admissions": output_dir / "operational_task_admissions.json",
        "records": output_dir / "operational_task_records.json",
        "observations": output_dir / "operational_witness_observations.json",
        "budget": output_dir / "provider_token_budget_contract.json",
        "reconciliation": output_dir / "reconciliation_selection_audit.json",
        "freshness": output_dir / "source_freshness_audit.json",
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "replay_bindings": output_dir / "verifier_v2_replay_bindings.json",
    }
    _write_models(paths["audits"], task_audits, "audit_id")
    _write_models(paths["scores"], compiler_scores, "score_id")
    _write_models(paths["trajectories"], compiler_trajectories, "trajectory_id")
    _write_json(paths["lineage"], lineage_audit.model_dump(mode="json"))
    _write_json(paths["capacity"], capacity_audit.model_dump(mode="json"))
    _write_models(paths["counterfactuals"], counterfactuals, "replay_id")
    _write_models(paths["necessities"], necessities, "artifact_id")
    _write_models(paths["closures"], closures, "audit_id")
    _write_models(paths["witnesses"], witnesses, "witness_id")
    _write_models(paths["admissions"], admissions, "admission_id")
    _write_models(paths["records"], records, "record_id")
    _write_models(paths["observations"], observations, "observation_id")
    _write_json(paths["budget"], budget_contract.model_dump(mode="json"))
    _write_json(
        paths["reconciliation"],
        reconciliation_selection.model_dump(mode="json"),
    )
    _write_json(paths["freshness"], freshness.model_dump(mode="json"))
    _write_models(paths["catalogs"], catalogs, "catalog_id")
    _write_models(paths["environments"], environments, "manifest_id")
    _write_models(paths["replay_bindings"], replay_bindings, "contract_id")
    counts = {
        "audits": len(task_audits),
        "scores": len(compiler_scores),
        "trajectories": len(compiler_trajectories),
        "lineage": 1,
        "capacity": 1,
        "counterfactuals": len(counterfactuals),
        "necessities": len(necessities),
        "closures": len(closures),
        "witnesses": len(witnesses),
        "admissions": len(admissions),
        "records": len(records),
        "observations": len(observations),
        "budget": 1,
        "reconciliation": 1,
        "freshness": 1,
        "catalogs": len(catalogs),
        "environments": len(environments),
        "replay_bindings": len(replay_bindings),
    }
    immutable_files = tuple(
        sorted(
            (_artifact_file(path, output_dir, counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    source_paths = (
        development_population_path,
        primary_source_path,
        secondary_source_path,
        tertiary_source_path,
        tertiary_no_api_report_path,
        quaternary_source_path,
        quaternary_no_api_report_path,
        v26_56_dir / "report.json",
        v26_56_dir / "rematerialized_task_records.json",
        v26_65_dir / "report.json",
        v26_65_dir / "operational_task_records.json",
        v26_69_dir / "report.json",
        v26_69_dir / "operational_task_records.json",
        v26_76_dir / "report.json",
        v26_76_dir / "operational_task_records.json",
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
        "source_v26_76_report_id": report76.report_id,
        "source_v26_76_report_sha256": _sha256(v26_76_dir / "report.json"),
        "verifier_qualification_report_id": qualification.report_id,
        "verifier_qualification_report_sha256": qualification_sha256,
        "qualified_replay_contract_id": replay_contract.contract_id,
        "provider_token_budget_contract_id": budget_contract.contract_id,
        "freshness_audit_id": freshness.audit_id,
        "reconciliation_selection_audit_id": reconciliation_selection.audit_id,
        "lineage_audit_id": lineage_audit.audit_id,
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "compiler_witness_observation_count": len(observations),
        "legacy_operation_mutation_count": sum(len(item.mutation_results) for item in closures),
        "task_record_ids": tuple(sorted(item.record_id for item in records)),
        "task_package_ids": tuple(sorted(item.task_package.package_id for item in records)),
        "environment_manifest_ids": tuple(sorted(item.manifest_id for item in environments)),
        "replay_binding_contract_ids": tuple(sorted(item.contract_id for item in replay_bindings)),
        "compiler_trajectory_ids": tuple(
            sorted(item.trajectory_id for item in compiler_trajectories)
        ),
        "compiler_score_ids": tuple(sorted(item.score_id for item in compiler_scores)),
        "source_artifact_files": source_files,
        "immutable_artifact_files": immutable_files,
        "implementation_source_files": _implementation_source_files(package_root),
    }
    if not all(item.status == "passed" for item in necessities):
        raise ValueError("budget-closed Mechanism Necessity did not pass")
    if not all(item.status == "passed" for item in closures):
        raise ValueError("budget-closed Operation Closure did not pass")
    if not all(item.operational_capability_eligible for item in admissions):
        raise ValueError("budget-closed capability admission did not pass")
    if any(item.operational_vtdo_candidate_eligible for item in admissions):
        raise ValueError("budget-closed Instrument Population crossed empirical roles")
    provisional = BudgetClosedInstrumentPopulationReport.model_construct(
        report_id="pending", **values
    )
    report = BudgetClosedInstrumentPopulationReport(
        report_id=budget_closed_population_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_closed_freshness_audit_id(
    value: BudgetClosedFreshnessAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_verifier_bound_freshness:",
    )


def budget_closed_population_report_id(
    value: BudgetClosedInstrumentPopulationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_closed_verifier_bound_instrument_population_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.82 fresh budget-closed Instrument Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--development-population", type=Path, required=True)
    parser.add_argument("--secondary-source", type=Path, required=True)
    parser.add_argument("--tertiary-source", type=Path, required=True)
    parser.add_argument("--tertiary-no-api-report", type=Path, required=True)
    parser.add_argument("--quaternary-source", type=Path, required=True)
    parser.add_argument("--quaternary-no-api-report", type=Path, required=True)
    parser.add_argument("--v26-56-dir", type=Path, required=True)
    parser.add_argument("--v26-65-dir", type=Path, required=True)
    parser.add_argument("--v26-69-dir", type=Path, required=True)
    parser.add_argument("--v26-76-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--exposure-receipt", type=Path, required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_budget_closed_instrument_population(
        run_id=args.run_id,
        development_population_path=args.development_population,
        secondary_source_path=args.secondary_source,
        tertiary_source_path=args.tertiary_source,
        tertiary_no_api_report_path=args.tertiary_no_api_report,
        quaternary_source_path=args.quaternary_source,
        quaternary_no_api_report_path=args.quaternary_no_api_report,
        v26_56_dir=args.v26_56_dir,
        v26_65_dir=args.v26_65_dir,
        v26_69_dir=args.v26_69_dir,
        v26_76_dir=args.v26_76_dir,
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
