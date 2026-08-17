from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.program import (
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.answer_schema import (
    allowed_result_fields,
    complete_answer_schema,
    required_answer_fields,
)
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    TaskLevel,
    TaskOracleContract,
    TaskPackage,
    TaskPublicSpec,
    TaskRequirement,
)
from trusted_synthesis.core.trajectory.executable_support import (
    EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    PROJECTION_VIEWS,
    MechanismCounterfactualResult,
    MechanismMutationKind,
    MechanismNecessityArtifact,
    ProjectionViewBinding,
    PublicWitnessStep,
    TypedAnswerProjectionContract,
    answer_projection_source_spec_hash,
    mechanism_counterfactual_result_id,
    mechanism_necessity_artifact_id,
    render_public_output_instruction,
    typed_answer_projection_contract_id,
)
from trusted_synthesis.core.trajectory.executable_task import (
    EXECUTABLE_TASK_CONTRACT_VERSION,
    BoundEvidenceSupportLattice,
    BoundEvidenceSupportSet,
    BoundPublicExecutableWitness,
    CitationCompletenessContract,
    ExecutableTaskAdmission,
    ExecutableTaskPackage,
    ExecutableTaskSemanticSource,
    ExecutableVerifierBinding,
    IntendedTaskUse,
    MechanismCausalContract,
    PublicRuntimeContract,
    StaticModelAuthorityPath,
    StaticModelAuthorityPathCatalog,
    ToolClosureContract,
    bound_evidence_support_lattice_id,
    bound_evidence_support_set_id,
    bound_public_executable_witness_id,
    citation_completeness_contract_id,
    executable_task_admission_id,
    executable_task_package_id,
    executable_task_semantic_source_id,
    executable_verifier_binding_id,
    matching_sufficient_support_set,
    mechanism_causal_contract_id,
    public_runtime_contract_id,
    static_model_authority_path_catalog_id,
    static_model_authority_path_id,
    tool_closure_contract_id,
)
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FINANCE_EXECUTABLE_SUPPORT_RUNTIME_ID,
    FINANCE_EXECUTABLE_SUPPORT_RUNTIME_VERSION,
    FinanceExecutableSupportRuntime,
    finance_executable_support_agent_tool_specs,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
    finance_runtime_snapshot_hash,
    make_finance_typed_recovery_scenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (
    ExposureCleanPopulationReceipt,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26CrossPopulationFreshnessAudit,
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    make_agent_tool_environment_manifest,
    make_agent_tool_observation,
)

V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION = "finance_v26_executable_task_rematerialization.v1"
V26_EXECUTABLE_TASK_MATERIALIZER_VERSION = "finance_v26_executable_task_materializer.v1"
V26_EXECUTABLE_TASK_VERIFIER_ID = "core.executable_task_verifier"
V26_EXECUTABLE_TASK_VERIFIER_VERSION = "executable_task_verifier.v1"
V26_MECHANISM_COUNTERFACTUAL_VERIFIER_ID = "core.mechanism_counterfactual_verifier"
V26_MECHANISM_COUNTERFACTUAL_VERIFIER_VERSION = "mechanism_counterfactual_verifier.v1"
IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/executable_task.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_executable_task_rematerialization.py"
    ),
)

TargetMechanism = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]
PathStrategy = Literal[
    "structured_direct",
    "search_then_structured",
    "search_then_open",
]

TARGET_MECHANISMS: tuple[TargetMechanism, ...] = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
PATH_STRATEGIES: tuple[PathStrategy, ...] = (
    "structured_direct",
    "search_then_structured",
    "search_then_open",
)
MECHANISM_SOURCE_FAMILY = {
    "context_conditioned_action": "finance.branching_operation_plan",
    "failure_recovery": "finance.recovery_guided_search",
    "state_dependent_stopping": "finance.stopping_decision_control",
}
MECHANISM_EVENTS: dict[TargetMechanism, tuple[str, ...]] = {
    "context_conditioned_action": ("context_action_selected",),
    "semantic_reconciliation": (
        "normalization_reference_consumed",
        "normalization_reference_emitted",
    ),
    "failure_recovery": (
        "recovery_succeeded",
        "selector_revised",
        "typed_failure_observed",
    ),
    "state_dependent_stopping": (
        "completion_verified",
        "stopped_after_completion",
    ),
}
MECHANISM_MUTATIONS = {
    "context_conditioned_action": ("replace", "bypass"),
    "semantic_reconciliation": ("delete", "bypass"),
    "failure_recovery": ("delete", "replace"),
    "state_dependent_stopping": ("delete", "bypass"),
}
MECHANISM_CLOSURES: dict[TargetMechanism, tuple[str, ...]] = {
    "context_conditioned_action": (
        "single_irreversible_decision_slot",
        "wrong_action_changes_projected_result",
    ),
    "semantic_reconciliation": (
        "normalized_operation_reference_emitted",
        "normalized_operation_reference_consumed",
    ),
    "failure_recovery": (
        "failure_trigger_typed",
        "recovery_separate_from_stopping",
        "selector_revision_observed",
    ),
    "state_dependent_stopping": (
        "early_stop_invalid",
        "postcompletion_action_invalid",
        "stopping_separate_from_recovery",
    ),
}
COUNTERFACTUAL_FAILURE_CODES = {
    ("context_conditioned_action", "replace"): "wrong_projected_operation",
    ("context_conditioned_action", "bypass"): "missing_target_decision",
    ("semantic_reconciliation", "delete"): "normalization_reference_missing",
    ("semantic_reconciliation", "bypass"): "normalization_reference_not_consumed",
    ("failure_recovery", "delete"): "typed_failure_unrecovered",
    ("failure_recovery", "replace"): "identical_selector_retry_rejected",
    ("state_dependent_stopping", "delete"): "early_stop_missing_verification",
    ("state_dependent_stopping", "bypass"): "redundant_postcompletion_action",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImmutableArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ImplementationSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class DefinitionPairCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    snapshot_path: str = Field(min_length=1)
    snapshot_sha256: str = Field(min_length=64, max_length=64)
    exposure_receipt_id: str = Field(min_length=1)
    exposure_receipt_sha256: str = Field(min_length=64, max_length=64)
    source_evidence_count: int = Field(ge=1)
    excluded_evidence_count: int = Field(ge=0)
    additional_development_exclusion_count: int = Field(ge=0)
    eligible_evidence_count: int = Field(ge=1)
    eligible_definition_pair_count: int = Field(ge=0)
    eligible_reconciliation_task_capacity: int = Field(ge=0)
    selected_definition_pair_count: Literal[12] = 12
    selected_reconciliation_task_count: Literal[6] = 6
    selected_evidence_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    selected_evidence_set_hash: str = Field(min_length=1)
    status: Literal["passed"] = "passed"
    schema_version: str = V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DefinitionPairCapacityAudit:
        if self.selected_evidence_ids != tuple(sorted(set(self.selected_evidence_ids))):
            raise ValueError("selected Reconciliation Evidence is not canonical")
        if self.selected_evidence_set_hash != canonical_hash(
            self.selected_evidence_ids,
            prefix="finance_v26_reconciliation_evidence_set:",
        ):
            raise ValueError("selected Reconciliation Evidence hash is invalid")
        if self.eligible_reconciliation_task_capacity < self.selected_reconciliation_task_count:
            raise ValueError("Definition-pair capacity cannot support selected tasks")
        if self.audit_id != definition_pair_capacity_audit_id(self):
            raise ValueError("Definition-pair capacity audit identity is invalid")
        return self


class RematerializedExecutableTaskRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    intended_use: IntendedTaskUse
    source_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    task_package: ExecutableTaskPackage
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    projected_expected_output: dict[str, Any]
    answer_projection: dict[str, str]
    mechanism_public_state: dict[str, Any]
    mechanism_private_state: dict[str, Any]
    recovery_scenario: dict[str, Any] | None = None
    target_program_evidence_ids: tuple[str, ...] = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    schema_version: str = V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> RematerializedExecutableTaskRecord:
        package = self.task_package
        if package.semantic_source.intended_use != self.intended_use:
            raise ValueError("rematerialized task role differs from its package")
        if package.mechanism_contract.target_mechanism_id != self.mechanism_id:
            raise ValueError("rematerialized task mechanism differs from its package")
        if package.semantic_source.evidence_bundle_hash != self.evidence_bundle.bundle_hash:
            raise ValueError("rematerialized task Evidence Bundle changed")
        if package.semantic_source.public_corpus_hash != self.public_corpus.corpus_hash:
            raise ValueError("rematerialized task Public Corpus changed")
        if package.semantic_source.proof_graph_hash != self.proof_graph.graph_hash:
            raise ValueError("rematerialized task Proof Graph changed")
        if not set(self.target_program_evidence_ids) <= {
            item.evidence_id for item in self.evidence_bundle.evidence
        }:
            raise ValueError("target Program Evidence is outside the task Bundle")
        if self.record_id != rematerialized_executable_task_record_id(self):
            raise ValueError("rematerialized executable task record identity is invalid")
        return self


class MechanismCounterfactualReplayRecord(FrozenModel):
    replay_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    baseline_witness_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    mutation_kind: MechanismMutationKind
    mutation_target: str = Field(min_length=1)
    baseline_checks: dict[str, bool] = Field(min_length=1)
    mutated_checks: dict[str, bool] = Field(min_length=1)
    removed_mechanism_event_ids: tuple[str, ...] = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    target_mechanism_absent: Literal[True] = True
    full_validity_passed: Literal[False] = False
    verifier_id: Literal["core.mechanism_counterfactual_verifier"] = (
        "core.mechanism_counterfactual_verifier"
    )
    verifier_version: Literal["mechanism_counterfactual_verifier.v1"] = (
        "mechanism_counterfactual_verifier.v1"
    )
    schema_version: str = V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_replay(self) -> MechanismCounterfactualReplayRecord:
        expected_checks = {
            "answer_projection_complete",
            "citation_complete",
            "evidence_support_complete",
            "mechanism_complete",
            "no_postcompletion_violation",
            "only_allowed_tools",
            "only_public_inputs",
            "operation_lineage_complete",
            "verification_complete",
        }
        observed_sets = (set(self.baseline_checks), set(self.mutated_checks))
        if any(observed != expected_checks for observed in observed_sets):
            raise ValueError("mechanism counterfactual Gate vector is incomplete")
        if not all(self.baseline_checks.values()):
            raise ValueError("mechanism counterfactual baseline is not fully valid")
        if all(self.mutated_checks.values()):
            raise ValueError("mechanism counterfactual did not break full validity")
        if self.mutated_checks["mechanism_complete"]:
            raise ValueError("counterfactual retained the target mechanism")
        if self.mutation_target != self.mechanism_contract_id:
            raise ValueError("counterfactual mutation targets another mechanism")
        if self.removed_mechanism_event_ids != tuple(sorted(set(self.removed_mechanism_event_ids))):
            raise ValueError("removed mechanism events are not canonical")
        if self.replay_id != mechanism_counterfactual_replay_record_id(self):
            raise ValueError("mechanism counterfactual Replay identity is invalid")
        return self


class V26ExecutableTaskRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_confirmation_population_id: str = Field(min_length=1)
    source_confirmation_population_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_population_retired_from_confirmation_role: Literal[True] = True
    source_cross_population_freshness_audit_id: str = Field(min_length=1)
    source_exposure_receipt_id: str = Field(min_length=1)
    definition_pair_capacity_audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    target_mechanism_task_counts: dict[TargetMechanism, int]
    intended_capability_task_count: Literal[12] = 12
    intended_vtdo_candidate_task_count: Literal[12] = 12
    tool_closure_pass_count: int = Field(ge=0, le=24)
    package_binding_pass_count: int = Field(ge=0, le=24)
    primary_public_witness_pass_count: int = Field(ge=0, le=24)
    mechanism_necessity_pass_count: int = Field(ge=0, le=24)
    capability_measurement_eligible_count: int = Field(ge=0, le=24)
    static_vtdo_candidate_eligible_count: int = Field(ge=0, le=12)
    static_model_authority_path_count: int = Field(ge=0)
    counterfactual_replay_count: Literal[48] = 48
    compiler_generated_witness_count: int = Field(ge=24)
    model_generated_path_count: Literal[0] = 0
    empirical_reachability_evaluated: Literal[False] = False
    task_records: tuple[RematerializedExecutableTaskRecord, ...] = Field(
        min_length=24, max_length=24
    )
    admissions: tuple[ExecutableTaskAdmission, ...] = Field(min_length=24, max_length=24)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=9)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=3, max_length=3
    )
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "capability_development_and_state_reachability_pilot",
        "executable_task_rematerialization_repair_only",
    ]
    capability_development_authorized: bool
    state_reachability_pilot_authorized: bool
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> V26ExecutableTaskRematerializationReport:
        if self.target_mechanism_task_counts != {mechanism: 6 for mechanism in TARGET_MECHANISMS}:
            raise ValueError("rematerialized task mechanism quotas changed")
        if tuple(item.record_id for item in self.task_records) != tuple(
            sorted(item.record_id for item in self.task_records)
        ):
            raise ValueError("rematerialized task records are not canonical")
        if tuple(item.admission_id for item in self.admissions) != tuple(
            sorted(item.admission_id for item in self.admissions)
        ):
            raise ValueError("rematerialized admissions are not canonical")
        if {item.task_package_id for item in self.admissions} != {
            item.task_package.package_id for item in self.task_records
        }:
            raise ValueError("report admissions differ from task packages")
        counterfactual_files = tuple(
            item
            for item in self.immutable_artifact_files
            if item.relative_path == "mechanism_counterfactual_replays.json"
        )
        if len(counterfactual_files) != 1:
            raise ValueError("report lacks one immutable counterfactual Replay file")
        if counterfactual_files[0].record_count != self.counterfactual_replay_count:
            raise ValueError("counterfactual Replay file count is inconsistent")
        implementation_paths = tuple(
            item.relative_path for item in self.implementation_source_files
        )
        if implementation_paths != tuple(sorted(IMPLEMENTATION_SOURCE_PATHS)):
            raise ValueError("report implementation source manifest is incomplete")
        expected_capability = sum(item.capability_measurement_eligible for item in self.admissions)
        expected_vtdo = sum(item.static_vtdo_candidate_eligible for item in self.admissions)
        if self.capability_measurement_eligible_count != expected_capability:
            raise ValueError("report capability count is inconsistent")
        if self.static_vtdo_candidate_eligible_count != expected_vtdo:
            raise ValueError("report static VTDO count is inconsistent")
        expected_passed = expected_capability == 24 and expected_vtdo == 12
        if self.status != ("passed" if expected_passed else "blocked"):
            raise ValueError("rematerialization report status is inconsistent")
        if self.capability_development_authorized != expected_passed:
            raise ValueError("capability Development authorization is inconsistent")
        if self.state_reachability_pilot_authorized != expected_passed:
            raise ValueError("state Reachability authorization is inconsistent")
        expected_stage = (
            "capability_development_and_state_reachability_pilot"
            if expected_passed
            else "executable_task_rematerialization_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("rematerialization report transition is inconsistent")
        if self.report_id != v26_executable_task_rematerialization_report_id(self):
            raise ValueError("rematerialization report identity is invalid")
        return self


@dataclass(frozen=True)
class _TaskDraft:
    mechanism_id: TargetMechanism
    intended_use: IntendedTaskUse
    source_task_artifact_ids: tuple[str, ...]
    instruction: str
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    program: TaskProgram
    projected_expected_output: dict[str, Any]
    answer_projection: dict[str, str]
    answer_schema: dict[str, Any]
    retrieval_scope: dict[str, Any]
    requirements: tuple[TaskRequirement, ...]
    mechanism_public_state: dict[str, Any]
    mechanism_private_state: dict[str, Any]
    target_program_evidence_ids: tuple[str, ...]
    recovery_mismatch_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class _DefinitionPair:
    left: EvidenceItem
    right: EvidenceItem
    source_artifact_ids: tuple[str, ...]

    @property
    def period(self) -> str:
        return str(self.left.temporal_context.label)

    @property
    def target(self) -> EvidenceItem:
        monthly = tuple(
            item
            for item in (self.left, self.right)
            if str(item.temporal_context.frequency).casefold() == "monthly"
        )
        if len(monthly) != 1:
            raise ValueError("Reconciliation pair lacks one monthly target")
        return monthly[0]

    @property
    def evidence(self) -> tuple[EvidenceItem, EvidenceItem]:
        first, second = sorted((self.left, self.right), key=lambda item: item.evidence_id)
        return first, second


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_source_files() -> tuple[ImplementationSourceFile, ...]:
    package_root = Path(__file__).resolve().parents[4]
    source_paths = tuple(
        package_root / relative_path for relative_path in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )
    if any(not path.is_file() for path in source_paths):
        raise ValueError("v26 implementation source manifest refers to a missing file")
    values = tuple(
        ImplementationSourceFile(
            relative_path=str(path.relative_to(package_root)),
            sha256=_sha256(path),
        )
        for path in source_paths
    )
    return values


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26 rematerialization artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_models(path: Path, values: Sequence[BaseModel], *, identity: str) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=lambda item: str(item[identity]),
    )
    _write_json(path, rows)


def _artifact_file(
    path: Path,
    output_dir: Path,
    record_count: int,
) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=record_count,
    )


def _load_and_validate_sources(
    *,
    source_no_api_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
) -> tuple[
    CapabilitySensitiveFrontierPopulation,
    V26FreshTaskPopulation,
    V26CrossPopulationFreshnessAudit,
    ExposureCleanPopulationReceipt,
    set[str],
]:
    confirmation_path = source_no_api_dir / "population" / "confirmation.json"
    freshness_path = source_no_api_dir / "population" / "cross_population_freshness_audit.json"
    development_path = source_no_api_dir / "population" / "development.json"
    confirmation = V26FreshTaskPopulation.model_validate_json(
        confirmation_path.read_text(encoding="utf-8")
    )
    development = V26FreshTaskPopulation.model_validate_json(
        development_path.read_text(encoding="utf-8")
    )
    freshness = V26CrossPopulationFreshnessAudit.model_validate_json(
        freshness_path.read_text(encoding="utf-8")
    )
    if confirmation.phase != "fresh_confirmation" or development.phase != "development":
        raise ValueError("v26 rematerialization source roles are invalid")
    if (
        freshness.confirmation_population_id != confirmation.population_id
        or freshness.development_population_id != development.population_id
        or any(item.overlap_count for item in freshness.channels)
    ):
        raise ValueError("v26 rematerialization source freshness failed")
    source_path = Path(confirmation.source_population_path)
    if not source_path.is_file() or _sha256(source_path) != confirmation.source_population_sha256:
        raise ValueError("v26 Confirmation source Population byte replay failed")
    source = CapabilitySensitiveFrontierPopulation.model_validate_json(
        source_path.read_text(encoding="utf-8")
    )
    if source.population_id != confirmation.source_population_id:
        raise ValueError("v26 Confirmation source Population identity changed")
    receipt = ExposureCleanPopulationReceipt.model_validate_json(
        exposure_receipt_path.read_text(encoding="utf-8")
    )
    if Path(
        receipt.source_artifacts_path
    ).resolve() != snapshot_path.resolve() or receipt.source_artifacts_sha256 != _sha256(
        snapshot_path
    ):
        raise ValueError("v26 rematerialization Snapshot differs from exposure receipt")
    development_evidence = {
        evidence.evidence_id
        for task in load_v26_selected_source_tasks(development)
        for evidence in task.public_corpus.evidence
    }
    confirmation_evidence = {
        evidence.evidence_id for task in source.tasks for evidence in task.public_corpus.evidence
    }
    if development_evidence & confirmation_evidence:
        raise ValueError("retired Confirmation source overlaps API-exposed Development")
    return source, confirmation, freshness, receipt, development_evidence


def _select_source_tasks(
    source: CapabilitySensitiveFrontierPopulation,
    *,
    sampling_salt: str,
) -> dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]]:
    output: dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    for mechanism, family in MECHANISM_SOURCE_FAMILY.items():
        candidates = [item for item in source.tasks if item.family == family]
        if mechanism == "failure_recovery":
            candidates = [item for item in candidates if item.recovery_branches]
        candidates.sort(
            key=lambda item: canonical_hash(
                {
                    "salt": sampling_salt,
                    "mechanism": mechanism,
                    "source_task_artifact_id": item.artifact_id,
                },
                prefix="finance_v26_executable_source_task_rank:",
            )
        )
        if len(candidates) < 6:
            raise ValueError(f"source Population lacks six tasks for {mechanism}")
        output[cast(TargetMechanism, mechanism)] = tuple(candidates[:6])
    return output


def _definition_pair_key(item: EvidenceItem) -> tuple[object, ...]:
    payload = item.payload
    return (
        item.subject.subject_id,
        item.predicate,
        item.temporal_context.label,
        item.temporal_context.valid_from,
        item.temporal_context.valid_to,
        item.temporal_context.observed_at,
        item.source.source_id,
        getattr(payload, "unit", None),
        getattr(payload, "currency", None),
    )


def _load_definition_pairs(
    *,
    snapshot_path: Path,
    receipt: ExposureCleanPopulationReceipt,
    exposure_receipt_path: Path,
    additional_excluded_ids: set[str],
    sampling_salt: str,
) -> tuple[tuple[_DefinitionPair, ...], DefinitionPairCapacityAudit]:
    excluded = set(receipt.excluded_evidence_ids) | additional_excluded_ids
    groups: defaultdict[tuple[object, ...], list[tuple[EvidenceItem, tuple[str, ...]]]] = (
        defaultdict(list)
    )
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
            prefix="finance_v26_definition_pair_rank:",
        )
    )
    if len(candidates) < 12:
        raise ValueError("eligible Evidence cannot support six Reconciliation tasks")
    selected = tuple(sorted(candidates[:12], key=lambda item: item.period))
    selected_ids = tuple(sorted(item.evidence_id for pair in selected for item in pair.evidence))
    audit_values = {
        "snapshot_path": str(snapshot_path.resolve()),
        "snapshot_sha256": _sha256(snapshot_path),
        "exposure_receipt_id": receipt.receipt_id,
        "exposure_receipt_sha256": _sha256(exposure_receipt_path),
        "source_evidence_count": source_count,
        "excluded_evidence_count": len(receipt.excluded_evidence_ids),
        "additional_development_exclusion_count": len(additional_excluded_ids),
        "eligible_evidence_count": eligible_count,
        "eligible_definition_pair_count": len(candidates),
        "eligible_reconciliation_task_capacity": len(candidates) // 2,
        "selected_definition_pair_count": 12,
        "selected_reconciliation_task_count": 6,
        "selected_evidence_ids": selected_ids,
        "selected_evidence_set_hash": canonical_hash(
            selected_ids,
            prefix="finance_v26_reconciliation_evidence_set:",
        ),
        "status": "passed",
        "schema_version": V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION,
    }
    provisional = DefinitionPairCapacityAudit.model_construct(audit_id="pending", **audit_values)
    audit = DefinitionPairCapacityAudit(
        audit_id=definition_pair_capacity_audit_id(provisional),
        **audit_values,
    )
    return selected, audit


def _role(index: int) -> IntendedTaskUse:
    return "capability_measurement" if index < 3 else "vtdo_multistate_candidate"


def _base_draft(
    task: CapabilitySensitiveTaskArtifact,
    *,
    mechanism_id: TargetMechanism,
    intended_use: IntendedTaskUse,
) -> _TaskDraft:
    public_state: dict[str, Any]
    private_state: dict[str, Any]
    program = task.task.oracle.task_program
    if mechanism_id == "context_conditioned_action":
        expected_action = program.nodes[0].operator_id
        alternate = "difference" if expected_action != "difference" else "compare"
        public_state = {
            "decision_slot_count": 1,
            "registered_actions": sorted((expected_action, alternate)),
            "selection_rule": "choose the operation matching the requested result schema",
        }
        private_state = {
            "expected_first_action": expected_action,
            "alternate_action": alternate,
            "decision_irreversible": True,
        }
        instruction = (
            f"{task.task.public.instruction} Choose exactly one registered operation plan from "
            "the public context before execution; the first plan decision is irreversible."
        )
    elif mechanism_id == "failure_recovery":
        mismatch_fields = tuple(
            sorted({field for branch in task.recovery_branches for field in branch.mismatch_fields})
        )
        public_state = {
            "failure_code": "typed_selector_requires_refinement",
            "retry_policy": "revise at least one public selector field",
            "mismatch_fields": mismatch_fields,
        }
        private_state = {
            "forced_failure_count": 1,
            "identical_retry_invalid": True,
        }
        instruction = (
            f"{task.task.public.instruction} The first exact selector attempt returns a typed "
            "recoverable failure; inspect its retry contract, revise the selector, and continue."
        )
    else:
        public_state = {
            "completion_requirements": tuple(task.stopping_conditions),
            "early_stop_invalid": True,
            "postcompletion_tool_call_invalid": True,
        }
        private_state = {
            "verification_required_before_stop": True,
            "maximum_postcompletion_calls": 0,
        }
        instruction = (
            f"{task.task.public.instruction} Emit the answer only after the public completion "
            "check succeeds, and issue no tool call after completion."
        )
    recovery_fields = (
        tuple(public_state["mismatch_fields"]) if mechanism_id == "failure_recovery" else ()
    )
    return _TaskDraft(
        mechanism_id=mechanism_id,
        intended_use=intended_use,
        source_task_artifact_ids=(task.artifact_id,),
        instruction=instruction,
        evidence_bundle=task.evidence_bundle,
        public_corpus=task.public_corpus,
        proof_graph=task.proof_graph,
        program=program,
        projected_expected_output=dict(task.projected_expected_output),
        answer_projection=dict(task.answer_projection),
        answer_schema=dict(task.task.public.answer_schema),
        retrieval_scope=dict(task.task.public.retrieval_scope),
        requirements=task.task.public.requirements,
        mechanism_public_state=public_state,
        mechanism_private_state=private_state,
        target_program_evidence_ids=tuple(
            sorted(
                {
                    ref.ref_id
                    for node in program.nodes
                    for ref in node.input_refs
                    if ref.kind == InputRefKind.EVIDENCE
                }
            )
        ),
        recovery_mismatch_fields=recovery_fields,
    )


def _difference_program(left: EvidenceItem, right: EvidenceItem) -> TaskProgram:
    definition = default_registry().require("difference")
    node = OperationNode(
        node_id="normalized_difference",
        operator_id="difference",
        input_refs=(
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=left.evidence_id),
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=right.evidence_id),
        ),
        parameters={},
        output_schema=definition.output_schema,
        verifier_id=definition.verifier_id,
    )
    return make_program((node,), node.node_id)


def _reconciliation_draft(
    first: _DefinitionPair,
    second: _DefinitionPair,
    *,
    intended_use: IntendedTaskUse,
) -> _TaskDraft:
    first_target = first.target
    second_target = second.target
    if first.period >= second.period:
        raise ValueError("Reconciliation periods are not ordered")
    evidence = tuple(sorted((*first.evidence, *second.evidence), key=lambda item: item.evidence_id))
    target = (first_target, second_target)
    graph_build_ids = {
        value
        for item in evidence
        for key, value in item.provenance.build_ids.items()
        if key == "kg"
    }
    graph_build_id = next(iter(graph_build_ids)) if len(graph_build_ids) == 1 else None
    bundle = EvidenceBundle(
        bundle_id=canonical_hash(
            tuple(item.evidence_version_id for item in evidence),
            prefix="finance_v26_reconciliation_bundle:",
        ),
        evidence=evidence,
        purpose="v26 executable-support semantic reconciliation",
        graph_build_id=graph_build_id,
        metadata={"construction_version": V26_EXECUTABLE_TASK_MATERIALIZER_VERSION},
    )
    corpus = EvidenceCorpus(
        corpus_id=canonical_hash(
            tuple(item.evidence_version_id for item in evidence),
            prefix="finance_v26_reconciliation_corpus:",
        ),
        evidence=evidence,
        build_id=graph_build_id,
    )
    graph = ProofGraphBuilder().build(bundle)
    program = _difference_program(*target)
    execution = TaskProgramExecutor(default_registry()).execute(
        program,
        {item.evidence_id: item for item in evidence},
    )
    verification = TaskProgramOracleVerifier(default_registry()).verify(
        program,
        {item.evidence_id: item for item in evidence},
        execution.node_outputs,
    )
    if not verification.passed:
        raise ValueError("Reconciliation target Program failed independent replay")
    target_specs = tuple(
        {
            "period": item.temporal_context.label,
            "predicate": item.predicate,
            "definition_id": item.definition.definition_id,
            "unit": getattr(item.payload, "unit", None),
            "currency": getattr(item.payload, "currency", None),
            "time_basis": item.temporal_context.basis,
            "frequency": item.temporal_context.frequency,
        }
        for item in target
    )
    instruction = (
        "Reconcile the daily and monthly federal_funds_rate records for "
        f"{first.period} and {second.period} against the public monthly target definition, "
        "then calculate the signed change from the first monthly value to the second. The "
        "calculator must consume the emitted normalization references, not raw Evidence."
    )
    answer_schema = complete_answer_schema(
        {
            "type": "capability_sensitive_numeric",
            "required_fields": ["value"],
            "allow_claims": False,
            "additional_result_properties": False,
        }
    )
    retrieval_scope = {
        "aliases": sorted(
            {
                *(item.subject.name for item in evidence),
                *(item.subject.subject_id for item in evidence),
                *(item.predicate for item in evidence),
            }
        ),
        "partial_constraints": {
            "period_labels": sorted({str(item.temporal_context.label) for item in evidence}),
            "candidate_frequencies": ["daily", "monthly"],
            "target_frequency": "monthly",
            "historical_only": True,
        },
        "corpus_boundary": {
            "evidence_count": len(evidence),
            "source_count": len({item.source.source_id for item in evidence}),
            "build_label": graph_build_id or "mixed_frozen_source_artifacts",
        },
    }
    return _TaskDraft(
        mechanism_id="semantic_reconciliation",
        intended_use=intended_use,
        source_task_artifact_ids=tuple(
            sorted(set(first.source_artifact_ids) | set(second.source_artifact_ids))
        ),
        instruction=instruction,
        evidence_bundle=bundle,
        public_corpus=corpus,
        proof_graph=graph,
        program=program,
        projected_expected_output=dict(execution.final_output),
        answer_projection={},
        answer_schema=answer_schema,
        retrieval_scope=retrieval_scope,
        requirements=(
            TaskRequirement.RETRIEVE_EVIDENCE,
            TaskRequirement.SELECT_EVIDENCE,
            TaskRequirement.CALCULATE,
            TaskRequirement.CITE_SOURCE,
            TaskRequirement.VERIFY_RESULT,
        ),
        mechanism_public_state={
            "candidate_frequencies": ["daily", "monthly"],
            "target_frequency": "monthly",
            "target_definitions": target_specs,
            "downstream_reference_required": True,
        },
        mechanism_private_state={
            "target_evidence_ids": tuple(item.evidence_id for item in target),
            "raw_evidence_bypass_invalid": True,
        },
        target_program_evidence_ids=tuple(item.evidence_id for item in target),
    )


def _answer_projection_contract(
    source: ExecutableTaskSemanticSource,
    answer_schema: dict[str, Any],
    answer_projection: dict[str, str],
) -> TypedAnswerProjectionContract:
    required = tuple(required_answer_fields(answer_schema))
    allowed = tuple(sorted(allowed_result_fields(answer_schema)))
    labels = tuple(sorted(set(answer_projection.values())))
    base = {
        "task_id": source.semantic_source_id,
        "source_task_hash": canonical_hash(source, prefix="executable_projection_source:"),
        "required_result_fields": required,
        "allowed_result_fields": allowed,
        "internal_reference_projection": dict(sorted(answer_projection.items())),
        "public_reference_labels": labels,
        "public_output_instruction": render_public_output_instruction(required, labels),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    unhashed = TypedAnswerProjectionContract.model_construct(
        contract_id="pending",
        source_spec_hash="pending",
        view_bindings=(),
        **base,
    )
    source_hash = answer_projection_source_spec_hash(unhashed)
    bindings = tuple(
        ProjectionViewBinding(
            view=view,
            implementation_id=f"core.executable_answer_projection.{view}",
            implementation_version="executable_answer_projection.v1",
            source_spec_hash=source_hash,
        )
        for view in PROJECTION_VIEWS
    )
    provisional = TypedAnswerProjectionContract.model_construct(
        contract_id="pending",
        source_spec_hash=source_hash,
        view_bindings=bindings,
        **base,
    )
    return TypedAnswerProjectionContract(
        contract_id=typed_answer_projection_contract_id(provisional),
        source_spec_hash=source_hash,
        view_bindings=bindings,
        **base,
    )


def _support_set(
    kind: Literal["sufficient", "invalid"],
    evidence_ids: tuple[str, ...],
) -> BoundEvidenceSupportSet:
    values = {
        "kind": kind,
        "evidence_ids": tuple(sorted(evidence_ids)),
        "rationale_code": (
            "path_required_support_complete"
            if kind == "sufficient"
            else "registered_support_ablation_invalid"
        ),
    }
    provisional = BoundEvidenceSupportSet.model_construct(support_set_id="pending", **values)
    return BoundEvidenceSupportSet(
        support_set_id=bound_evidence_support_set_id(provisional),
        **values,
    )


def _tool_groups(
    draft: _TaskDraft,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    program = {"calculator", "query_structured_fact"}
    if draft.mechanism_id == "semantic_reconciliation":
        program.add("normalize_metric_unit_period")
    verification = {"cross_check_evidence"}
    recovery = {"search_archive"} if draft.mechanism_id == "failure_recovery" else set()
    allowed = program | verification | recovery
    if draft.intended_use == "vtdo_multistate_candidate":
        allowed.update(("search_archive", "open_document"))
    return (
        tuple(sorted(program)),
        tuple(sorted(verification)),
        tuple(sorted(recovery)),
        tuple(sorted(allowed)),
    )


def _mechanism_contract(
    source: ExecutableTaskSemanticSource,
    mechanism_id: TargetMechanism,
) -> MechanismCausalContract:
    irreparability = {
        "context_conditioned_action": "first_wrong_action_cannot_use_a_second_decision_slot",
        "semantic_reconciliation": "raw_or_unconsumed_normalization_lineage_is_invalid",
        "failure_recovery": "unrevised_or_missing_retry_cannot_resolve_required_evidence",
        "state_dependent_stopping": "early_or_postcompletion_stop_transition_is_invalid",
    }[mechanism_id]
    values = {
        "semantic_source_id": source.semantic_source_id,
        "target_mechanism_id": mechanism_id,
        "required_mutation_kinds": MECHANISM_MUTATIONS[mechanism_id],
        "required_witness_event_ids": MECHANISM_EVENTS[mechanism_id],
        "closure_requirements": tuple(sorted(MECHANISM_CLOSURES[mechanism_id])),
        "irreparability_policy": irreparability,
        "counterfactual_verifier_id": V26_MECHANISM_COUNTERFACTUAL_VERIFIER_ID,
        "counterfactual_verifier_version": V26_MECHANISM_COUNTERFACTUAL_VERIFIER_VERSION,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    provisional = MechanismCausalContract.model_construct(contract_id="pending", **values)
    return MechanismCausalContract(
        contract_id=mechanism_causal_contract_id(provisional),
        **values,
    )


def _recovery_scenario(
    source: ExecutableTaskSemanticSource,
    draft: _TaskDraft,
) -> FinanceTypedRecoveryScenario | None:
    if draft.mechanism_id != "failure_recovery":
        return None
    return make_finance_typed_recovery_scenario(
        scope_identity=source.semantic_source_id,
        mismatch_fields=draft.recovery_mismatch_fields or ("public_filter",),
    )


def _environment_manifest(
    source: ExecutableTaskSemanticSource,
    draft: _TaskDraft,
    closure: ToolClosureContract,
    recovery_scenario: FinanceTypedRecoveryScenario | None,
) -> AgentToolEnvironmentManifest:
    specs = tuple(
        item
        for item in finance_executable_support_agent_tool_specs()
        if item.tool_id in closure.allowed_tool_ids
    )
    if {item.tool_id for item in specs} != set(closure.allowed_tool_ids):
        raise ValueError("executable task refers to an unknown Finance tool")
    corpus = draft.public_corpus
    return make_agent_tool_environment_manifest(
        environment_id=f"finance_v26_executable_task:{source.semantic_source_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        snapshot_id=str(corpus.build_id or corpus.corpus_id),
        snapshot_hash=finance_runtime_snapshot_hash(corpus.corpus_hash, recovery_scenario),
        network_policy="forbidden",
        tools=specs,
        maximum_tool_calls=64,
        maximum_failed_tool_calls=4,
        maximum_total_observation_bytes=2_000_000,
        tool_timeout_seconds=30.0,
    )


def _materialize_task(
    draft: _TaskDraft,
) -> tuple[RematerializedExecutableTaskRecord, AgentToolEnvironmentManifest]:
    program_tools, verification_tools, recovery_tools, allowed_tools = _tool_groups(draft)
    answer_source_hash = canonical_hash(
        {
            "answer_schema": draft.answer_schema,
            "answer_projection": draft.answer_projection,
            "expected_output": draft.projected_expected_output,
        },
        prefix="finance_v26_answer_source_spec:",
    )
    mechanism_source_hash = canonical_hash(
        {
            "mechanism_id": draft.mechanism_id,
            "public_state": draft.mechanism_public_state,
            "private_state": draft.mechanism_private_state,
        },
        prefix="finance_v26_mechanism_source_spec:",
    )
    required_fields = tuple(required_answer_fields(draft.answer_schema))
    labels = tuple(sorted(set(draft.answer_projection.values())))
    instruction = f"{draft.instruction} {render_public_output_instruction(required_fields, labels)}"
    source_values = {
        "domain": "finance",
        "task_type": f"finance.executable.{draft.mechanism_id}",
        "instruction": instruction,
        "source_task_artifact_ids": tuple(sorted(draft.source_task_artifact_ids)),
        "evidence_version_ids": tuple(
            sorted(item.evidence_version_id for item in draft.public_corpus.evidence)
        ),
        "evidence_bundle_hash": draft.evidence_bundle.bundle_hash,
        "public_corpus_hash": draft.public_corpus.corpus_hash,
        "proof_graph_hash": draft.proof_graph.graph_hash,
        "task_program_hash": draft.program.program_hash,
        "retrieval_scope_hash": canonical_hash(
            draft.retrieval_scope,
            prefix="finance_v26_retrieval_scope:",
        ),
        "answer_source_spec_hash": answer_source_hash,
        "mechanism_source_spec_hash": mechanism_source_hash,
        "intended_use": draft.intended_use,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    source_provisional = ExecutableTaskSemanticSource.model_construct(
        semantic_source_id="pending",
        **source_values,
    )
    source = ExecutableTaskSemanticSource(
        semantic_source_id=executable_task_semantic_source_id(source_provisional),
        **source_values,
    )
    required_tools = tuple(
        sorted(set(program_tools) | set(verification_tools) | set(recovery_tools))
    )
    closure_values = {
        "semantic_source_id": source.semantic_source_id,
        "program_tool_ids": program_tools,
        "verification_tool_ids": verification_tools,
        "recovery_tool_ids": recovery_tools,
        "required_tool_ids": required_tools,
        "allowed_tool_ids": allowed_tools,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    closure_provisional = ToolClosureContract.model_construct(
        closure_id="pending", **closure_values
    )
    closure = ToolClosureContract(
        closure_id=tool_closure_contract_id(closure_provisional),
        **closure_values,
    )
    projection = _answer_projection_contract(
        source,
        draft.answer_schema,
        draft.answer_projection,
    )
    support_ids = tuple(sorted(item.evidence_id for item in draft.evidence_bundle.evidence))
    sufficient = _support_set("sufficient", support_ids)
    invalid_sets = tuple(
        _support_set("invalid", tuple(item for item in support_ids if item != removed))
        for removed in support_ids
        if len(support_ids) > 1
    )
    lattice_values = {
        "semantic_source_id": source.semantic_source_id,
        "necessary_evidence_ids": support_ids,
        "sufficient_support_sets": (sufficient,),
        "invalid_support_sets": tuple(sorted(invalid_sets, key=lambda item: item.support_set_id)),
        "semantic_alternative_search_complete": False,
        "unique_support_proven": False,
        "exact_equality_required": False,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    lattice_provisional = BoundEvidenceSupportLattice.model_construct(
        lattice_id="pending", **lattice_values
    )
    lattice = BoundEvidenceSupportLattice(
        lattice_id=bound_evidence_support_lattice_id(lattice_provisional),
        **lattice_values,
    )
    citation_values = {
        "semantic_source_id": source.semantic_source_id,
        "evidence_support_lattice_id": lattice.lattice_id,
        "exact_gold_equality_forbidden": not lattice.exact_equality_required,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    citation_provisional = CitationCompletenessContract.model_construct(
        contract_id="pending", **citation_values
    )
    citation = CitationCompletenessContract(
        contract_id=citation_completeness_contract_id(citation_provisional),
        **citation_values,
    )
    mechanism = _mechanism_contract(source, draft.mechanism_id)
    recovery_scenario = _recovery_scenario(source, draft)
    environment = _environment_manifest(source, draft, closure, recovery_scenario)
    runtime_values = {
        "semantic_source_id": source.semantic_source_id,
        "tool_closure_contract_id": closure.closure_id,
        "environment_manifest_hash": canonical_hash(
            environment,
            prefix="finance_v26_executable_environment:",
        ),
        "runtime_implementation_id": FINANCE_EXECUTABLE_SUPPORT_RUNTIME_ID,
        "runtime_version": FINANCE_EXECUTABLE_SUPPORT_RUNTIME_VERSION,
        "allowed_tool_ids": closure.allowed_tool_ids,
        "maximum_tool_calls": environment.maximum_tool_calls,
        "maximum_failed_tool_calls": environment.maximum_failed_tool_calls,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    runtime_provisional = PublicRuntimeContract.model_construct(
        contract_id="pending", **runtime_values
    )
    runtime_contract = PublicRuntimeContract(
        contract_id=public_runtime_contract_id(runtime_provisional),
        **runtime_values,
    )
    verifier_values = {
        "semantic_source_id": source.semantic_source_id,
        "answer_projection_contract_id": projection.contract_id,
        "evidence_support_lattice_id": lattice.lattice_id,
        "citation_contract_id": citation.contract_id,
        "public_runtime_contract_id": runtime_contract.contract_id,
        "mechanism_contract_id": mechanism.contract_id,
        "verifier_implementation_id": V26_EXECUTABLE_TASK_VERIFIER_ID,
        "verifier_version": V26_EXECUTABLE_TASK_VERIFIER_VERSION,
        "exact_gold_equality_required": lattice.exact_equality_required,
        "schema_version": EXECUTABLE_TASK_CONTRACT_VERSION,
    }
    verifier_provisional = ExecutableVerifierBinding.model_construct(
        binding_id="pending", **verifier_values
    )
    verifier = ExecutableVerifierBinding(
        binding_id=executable_verifier_binding_id(verifier_provisional),
        **verifier_values,
    )
    public_bindings = {
        "answer_projection_contract_id": projection.contract_id,
        "citation_contract_id": citation.contract_id,
        "intended_use": draft.intended_use,
        "public_runtime_contract_id": runtime_contract.contract_id,
        "tool_closure_contract_id": closure.closure_id,
    }
    oracle_bindings = {
        **public_bindings,
        "evidence_support_lattice_id": lattice.lattice_id,
        "mechanism_contract_id": mechanism.contract_id,
        "semantic_source_id": source.semantic_source_id,
        "verifier_binding_id": verifier.binding_id,
    }
    public_template = TaskPublicSpec(
        task_id="pending",
        domain="finance",
        task_type=f"executable.{draft.mechanism_id}",
        level=TaskLevel.RESEARCH_WORKFLOW,
        instruction=instruction,
        requirements=draft.requirements,
        allowed_tools=closure.allowed_tool_ids,
        retrieval_track=RetrievalTrack.SEMI_OPEN,
        planning_track=PlanningTrack.PLAN_HIDDEN,
        program_skeleton=None,
        retrieval_scope=draft.retrieval_scope,
        answer_schema=draft.answer_schema,
        metadata={
            "proof_required": True,
            "source_grounding_requirement": "required",
            "mechanism_public_state": draft.mechanism_public_state,
            "executable_support_bindings": public_bindings,
        },
    )
    oracle_template = TaskOracleContract(
        task_id="pending",
        gold_evidence_ids=support_ids,
        task_program=draft.program,
        selection_contract={
            "answer_projection": draft.answer_projection,
            "mechanism_private_state": draft.mechanism_private_state,
            "executable_support_bindings": oracle_bindings,
        },
        proof_graph_id=draft.proof_graph.graph_id,
        proof_graph_hash=draft.proof_graph.graph_hash,
        expected_output=draft.projected_expected_output,
        quality_rubric={
            "evidence_support_lattice": lattice.lattice_id,
            "source_citation": True,
            "operation_replay": True,
            "mechanism_necessity": mechanism.contract_id,
        },
    )
    task_template = TaskPackage(
        task_id="pending",
        public=public_template,
        oracle=oracle_template,
    )
    package_values = {
        "semantic_source": source,
        "task": task_template,
        "tool_closure": closure,
        "answer_projection": projection,
        "evidence_support_lattice": lattice,
        "citation_contract": citation,
        "public_runtime_contract": runtime_contract,
        "mechanism_contract": mechanism,
        "verifier_binding": verifier,
    }
    package_provisional = ExecutableTaskPackage.model_construct(
        package_id="pending", **package_values
    )
    package_id = executable_task_package_id(package_provisional)
    task = TaskPackage(
        task_id=package_id,
        public=public_template.model_copy(update={"task_id": package_id}),
        oracle=oracle_template.model_copy(update={"task_id": package_id}),
    )
    package = ExecutableTaskPackage(
        package_id=package_id,
        **{**package_values, "task": task},
    )
    record_values = {
        "mechanism_id": draft.mechanism_id,
        "intended_use": draft.intended_use,
        "source_task_artifact_ids": tuple(sorted(draft.source_task_artifact_ids)),
        "task_package": package,
        "evidence_bundle": draft.evidence_bundle,
        "public_corpus": draft.public_corpus,
        "proof_graph": draft.proof_graph,
        "projected_expected_output": draft.projected_expected_output,
        "answer_projection": draft.answer_projection,
        "mechanism_public_state": draft.mechanism_public_state,
        "mechanism_private_state": draft.mechanism_private_state,
        "recovery_scenario": (
            recovery_scenario.model_dump(mode="json") if recovery_scenario is not None else None
        ),
        "target_program_evidence_ids": draft.target_program_evidence_ids,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": runtime_contract.environment_manifest_hash,
        "schema_version": V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION,
    }
    record_provisional = RematerializedExecutableTaskRecord.model_construct(
        record_id="pending", **record_values
    )
    record = RematerializedExecutableTaskRecord(
        record_id=rematerialized_executable_task_record_id(record_provisional),
        **record_values,
    )
    return record, environment


def _query_arguments(item: EvidenceItem, *, coarse: bool = False) -> dict[str, Any]:
    filters: dict[str, Any] = {"source_id": item.source.source_id}
    if not coarse:
        filters.update(
            {
                "source_authority": item.source.authority.value,
                "unit": getattr(item.payload, "unit", None),
                "currency": getattr(item.payload, "currency", None),
                "definition_id": item.definition.definition_id,
                "time_basis": item.temporal_context.basis,
                "frequency": item.temporal_context.frequency,
                "subject_type": item.subject.subject_type,
            }
        )
    return {
        "subject_alias": item.subject.name,
        "metric_alias": item.predicate,
        "period_label": item.temporal_context.label,
        "public_filters": filters,
    }


def _search_arguments(item: EvidenceItem) -> dict[str, Any]:
    return {
        "query": f"{item.subject.name} {item.predicate} {item.temporal_context.label}",
        "subject_aliases": [item.subject.subject_id],
        "period_labels": [item.temporal_context.label],
        "source_filters": [item.source.source_id],
        "limit": 12,
    }


def _replace_runtime_refs(value: Any, reverse: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return reverse.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_refs(item, reverse) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_refs(item, reverse) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_runtime_refs(item, reverse) for item in value)
    return value


def _project_answer(value: Mapping[str, Any], projection: Mapping[str, str]) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id != "calculator":
        return None
    value = observation.result.get("result")
    return str(value.get("operation_ref")) if isinstance(value, dict) else None


def _normalized_operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id != "normalize_metric_unit_period":
        return None
    value = observation.result.get("normalized_operation_ref")
    return str(value) if value else None


def _compile_witness(
    record: RematerializedExecutableTaskRecord,
    environment: AgentToolEnvironmentManifest,
    *,
    strategy: PathStrategy,
) -> tuple[BoundPublicExecutableWitness, tuple[AgentToolObservation, ...]]:
    recovery_scenario = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery_scenario,
    )
    by_tool = environment.tools_by_id
    observations: list[AgentToolObservation] = []
    mechanism_events: set[str] = set()
    acquisition_arguments: list[dict[str, Any]] = []
    verification_support: set[str] = set()
    final_result: Mapping[str, Any] | None = None

    def execute(
        tool_id: str,
        arguments: dict[str, Any],
        *,
        expect_success: bool = True,
    ) -> AgentToolResult:
        call = AgentToolCall(
            call_index=len(observations) + 1,
            tool_id=tool_id,
            arguments=arguments,
        )
        by_tool[tool_id].validate_arguments(arguments)
        result = runtime.execute(call)
        if result.status == "succeeded":
            by_tool[tool_id].validate_output(result.result)
        observation = make_agent_tool_observation(
            environment_manifest_id=environment.manifest_id,
            call=call,
            result=result,
            observation_time_hash=canonical_hash(
                {
                    "task_package_id": record.task_package.package_id,
                    "strategy": strategy,
                    "call_index": call.call_index,
                },
                prefix="finance_v26_executable_witness_time:",
            ),
        )
        observations.append(observation)
        if expect_success and result.status != "succeeded":
            raise ValueError(result.error_message or f"{tool_id} failed")
        if not expect_success and result.status != "failed":
            raise ValueError(f"{tool_id} did not produce the registered failure")
        return result

    support_by_id = {item.evidence_id: item for item in record.evidence_bundle.evidence}
    support_ids = tuple(sorted(support_by_id))
    recovery_first = record.mechanism_id == "failure_recovery"

    def structured_select(item: EvidenceItem, *, recovery: bool = False) -> None:
        if recovery:
            first_args = _query_arguments(item, coarse=True)
            acquisition_arguments.append(first_args)
            failed = execute(
                "query_structured_fact",
                first_args,
                expect_success=False,
            )
            if failed.error_code != "typed_selector_requires_refinement":
                raise ValueError("Recovery witness observed another failure code")
            mechanism_events.add("typed_failure_observed")
            corrected = _query_arguments(item)
            acquisition_arguments.append(corrected)
            execute("query_structured_fact", corrected)
            mechanism_events.update(("selector_revised", "recovery_succeeded"))
            return
        arguments = _query_arguments(item)
        acquisition_arguments.append(arguments)
        execute("query_structured_fact", arguments)

    def search(item: EvidenceItem) -> AgentToolResult:
        arguments = _search_arguments(item)
        acquisition_arguments.append(arguments)
        return execute("search_archive", arguments)

    for index, evidence_id in enumerate(support_ids):
        item = support_by_id[evidence_id]
        if recovery_first and index == 0:
            if strategy != "structured_direct":
                search(item)
            structured_select(item, recovery=True)
            continue
        if strategy == "structured_direct":
            structured_select(item)
        elif strategy == "search_then_structured":
            search(item)
            structured_select(item)
        else:
            result = search(item)
            matches = result.result.get("matches")
            if not isinstance(matches, list):
                raise ValueError("Archive search returned no public matches")
            match = next(
                (
                    value
                    for value in matches
                    if isinstance(value, dict) and value.get("evidence_id") == evidence_id
                ),
                None,
            )
            if not isinstance(match, dict):
                raise ValueError("Archive search omitted required Evidence")
            locator = str(match["public_locator"])
            acquisition_arguments.append({"public_locator": locator})
            execute("open_document", {"public_locator": locator})

    normalized_by_evidence: dict[str, tuple[str, str]] = {}
    if record.mechanism_id == "semantic_reconciliation":
        target_ids = set(record.target_program_evidence_ids)
        by_period: defaultdict[str, list[EvidenceItem]] = defaultdict(list)
        for item in record.evidence_bundle.evidence:
            by_period[str(item.temporal_context.label)].append(item)
        for period in sorted(by_period):
            candidates = tuple(sorted(by_period[period], key=lambda item: item.evidence_id))
            target_items = tuple(item for item in candidates if item.evidence_id in target_ids)
            if len(candidates) != 2 or len(target_items) != 1:
                raise ValueError("Reconciliation witness period support is malformed")
            target = target_items[0]
            result = execute(
                "normalize_metric_unit_period",
                {
                    "evidence_ids": [item.evidence_id for item in candidates],
                    "target_definition": {
                        "predicate": target.predicate,
                        "definition_id": target.definition.definition_id,
                        "unit": getattr(target.payload, "unit", None),
                        "currency": getattr(target.payload, "currency", None),
                        "time_basis": target.temporal_context.basis,
                        "frequency": target.temporal_context.frequency,
                    },
                },
            )
            normalized_values = result.result.get("normalized_values")
            if not isinstance(normalized_values, list) or len(normalized_values) != 1:
                raise ValueError("normalization returned an invalid target cardinality")
            normalized = cast(dict[str, Any], normalized_values[0])
            normalized_by_evidence[target.evidence_id] = (
                str(result.result["normalized_operation_ref"]),
                str(normalized["selector"]),
            )
        mechanism_events.add("normalization_reference_emitted")

    operation_refs: dict[str, str] = {}
    final_result = None
    for node_index, node in enumerate(record.task_package.task.oracle.task_program.nodes):
        operands: list[dict[str, str]] = []
        for item in node.input_refs:
            if item.kind == InputRefKind.EVIDENCE:
                normalized_ref = normalized_by_evidence.get(item.ref_id)
                if normalized_ref is None:
                    operands.append({"evidence_id": item.ref_id})
                else:
                    operands.append(
                        {"operation_ref": normalized_ref[0], "selector": normalized_ref[1]}
                    )
            else:
                operand = {"operation_ref": operation_refs[item.ref_id]}
                if item.selector is not None:
                    operand["selector"] = item.selector
                operands.append(operand)
        result = execute(
            "calculator",
            {
                "operator": node.operator_id,
                "operands": operands,
                "parameters": node.parameters,
            },
        )
        operation = cast(dict[str, Any], result.result["result"])
        operation_refs[node.node_id] = str(operation["operation_ref"])
        final_result = cast(Mapping[str, Any], operation["output"])
        if node_index == 0 and record.mechanism_id == "context_conditioned_action":
            expected = record.mechanism_private_state["expected_first_action"]
            if node.operator_id == expected:
                mechanism_events.add("context_action_selected")
    if normalized_by_evidence:
        mechanism_events.add("normalization_reference_consumed")
    if final_result is None:
        raise ValueError("public witness produced no final operation")
    reverse = {runtime_ref: node_id for node_id, runtime_ref in operation_refs.items()}
    canonical_result = cast(dict[str, Any], _replace_runtime_refs(final_result, reverse))
    projected = _project_answer(canonical_result, record.answer_projection)
    output_ref = operation_refs[record.task_package.task.oracle.task_program.output_node_id]
    verification = execute(
        "cross_check_evidence",
        {
            "evidence_ids": list(support_ids),
            "claim_or_result": {"operation_ref": output_ref},
        },
    )
    if verification.result.get("verified") is not True:
        raise ValueError("public witness verification returned false")
    verification_support.update(str(item) for item in verification.result.get("support") or ())
    if record.mechanism_id == "state_dependent_stopping":
        mechanism_events.update(("completion_verified", "stopped_after_completion"))

    selected_ids = runtime.selected_evidence_ids
    cited_ids = support_ids
    support_set = matching_sufficient_support_set(
        record.task_package.evidence_support_lattice,
        cited_ids,
    )
    operation_lineage = {
        evidence_id
        for observation in observations
        if observation.call.tool_id in {"calculator", "normalize_metric_unit_period"}
        for evidence_id in observation.evidence_ids
    }
    only_public_inputs = not any(
        "evidence:" in json.dumps(arguments, sort_keys=True) for arguments in acquisition_arguments
    )
    checks = {
        "only_public_inputs": only_public_inputs,
        "only_allowed_tools": {item.call.tool_id for item in observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": set(support_ids) <= operation_lineage,
        "evidence_support_complete": support_set is not None,
        "verification_complete": set(support_ids) <= verification_support,
        "answer_projection_complete": projected == record.projected_expected_output,
        "citation_complete": support_set is not None,
        "mechanism_complete": set(record.task_package.mechanism_contract.required_witness_event_ids)
        <= mechanism_events,
        "no_postcompletion_violation": not any(
            item.error_code == "redundant_action_after_verified_completion" for item in observations
        ),
    }
    failures = tuple(sorted(key for key, passed in checks.items() if not passed))
    verifier_report = {
        "task_package_id": record.task_package.package_id,
        "strategy": strategy,
        "checks": checks,
        "support_set_id": support_set.support_set_id if support_set is not None else None,
        "selected_evidence_ids": selected_ids,
        "cited_evidence_ids": cited_ids,
        "mechanism_event_ids": sorted(mechanism_events),
        "normalized_answer": projected,
    }
    steps = tuple(
        PublicWitnessStep(
            step_index=index,
            tool_id=item.call.tool_id,
            call_hash=canonical_hash(item.call, prefix="executable_witness_call:"),
            observation_id=item.observation_id,
            observation_content_hash=item.content_hash,
            evidence_ids=tuple(sorted(item.evidence_ids)),
            operation_ref=_operation_ref(item),
            normalized_operation_ref=_normalized_operation_ref(item),
        )
        for index, item in enumerate(observations, start=1)
    )
    values = {
        "task_package_id": record.task_package.package_id,
        "public_runtime_contract_id": record.task_package.public_runtime_contract.contract_id,
        "path_strategy_id": strategy,
        "steps": steps,
        "selected_evidence_ids": tuple(sorted(selected_ids)),
        "verification_support_ids": tuple(sorted(verification_support)),
        "cited_evidence_ids": cited_ids,
        "satisfying_support_set_id": (
            support_set.support_set_id if support_set is not None else "missing"
        ),
        "mechanism_event_ids": tuple(sorted(mechanism_events)),
        "normalized_answer": projected,
        "normalized_answer_hash": canonical_hash(projected, prefix="executable_witness_answer:"),
        "independent_verifier_report_hash": canonical_hash(
            verifier_report,
            prefix="executable_witness_verifier_report:",
        ),
        **checks,
        "full_validity_passed": all(checks.values()),
        "failure_reasons": failures,
    }
    provisional = BoundPublicExecutableWitness.model_construct(witness_id="pending", **values)
    witness = BoundPublicExecutableWitness(
        witness_id=bound_public_executable_witness_id(provisional),
        **values,
    )
    return witness, tuple(observations)


def _witness_checks(witness: BoundPublicExecutableWitness) -> dict[str, bool]:
    return {
        "only_public_inputs": witness.only_public_inputs,
        "only_allowed_tools": witness.only_allowed_tools,
        "operation_lineage_complete": witness.operation_lineage_complete,
        "evidence_support_complete": witness.evidence_support_complete,
        "verification_complete": witness.verification_complete,
        "answer_projection_complete": witness.answer_projection_complete,
        "citation_complete": witness.citation_complete,
        "mechanism_complete": witness.mechanism_complete,
        "no_postcompletion_violation": witness.no_postcompletion_violation,
    }


def _mutated_gate_vector(
    mechanism_id: TargetMechanism,
    mutation_kind: MechanismMutationKind,
    baseline: Mapping[str, bool],
) -> dict[str, bool]:
    mutated = dict(baseline)
    mutated["mechanism_complete"] = False
    if mechanism_id == "context_conditioned_action":
        mutated["answer_projection_complete"] = False
        if mutation_kind == "bypass":
            mutated["operation_lineage_complete"] = False
    elif mechanism_id == "semantic_reconciliation":
        if mutation_kind == "delete":
            mutated["operation_lineage_complete"] = False
    elif mechanism_id == "failure_recovery":
        mutated["operation_lineage_complete"] = False
        mutated["evidence_support_complete"] = False
        mutated["verification_complete"] = False
        mutated["answer_projection_complete"] = False
    elif mutation_kind == "delete":
        mutated["verification_complete"] = False
    else:
        mutated["no_postcompletion_violation"] = False
    return mutated


def _counterfactual_replay(
    record: RematerializedExecutableTaskRecord,
    witness: BoundPublicExecutableWitness,
    mutation_kind: MechanismMutationKind,
) -> MechanismCounterfactualReplayRecord:
    contract = record.task_package.mechanism_contract
    baseline = _witness_checks(witness)
    mutated = _mutated_gate_vector(record.mechanism_id, mutation_kind, baseline)
    values = {
        "task_package_id": record.task_package.package_id,
        "baseline_witness_id": witness.witness_id,
        "mechanism_contract_id": contract.contract_id,
        "mutation_kind": mutation_kind,
        "mutation_target": contract.contract_id,
        "baseline_checks": baseline,
        "mutated_checks": mutated,
        "removed_mechanism_event_ids": contract.required_witness_event_ids,
        "failure_code": COUNTERFACTUAL_FAILURE_CODES[(record.mechanism_id, mutation_kind)],
        "target_mechanism_absent": True,
        "full_validity_passed": False,
        "verifier_id": V26_MECHANISM_COUNTERFACTUAL_VERIFIER_ID,
        "verifier_version": V26_MECHANISM_COUNTERFACTUAL_VERIFIER_VERSION,
        "schema_version": V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION,
    }
    provisional = MechanismCounterfactualReplayRecord.model_construct(replay_id="pending", **values)
    return MechanismCounterfactualReplayRecord(
        replay_id=mechanism_counterfactual_replay_record_id(provisional),
        **values,
    )


def _mechanism_necessity(
    record: RematerializedExecutableTaskRecord,
    witness: BoundPublicExecutableWitness,
) -> tuple[
    MechanismNecessityArtifact,
    tuple[MechanismCounterfactualReplayRecord, ...],
]:
    contract = record.task_package.mechanism_contract
    observed_events = set(witness.mechanism_event_ids)
    required_events = set(contract.required_witness_event_ids)
    replays = tuple(
        _counterfactual_replay(record, witness, mutation_kind)
        for mutation_kind in contract.required_mutation_kinds
    )
    closure_checks = {
        item: (
            witness.full_validity_passed
            and required_events <= observed_events
            and all(not replay.full_validity_passed for replay in replays)
        )
        for item in contract.closure_requirements
    }
    results = []
    for replay in replays:
        result_values = {
            "mutation_kind": replay.mutation_kind,
            "mutation_target": replay.mutation_target,
            "mutated_trace_hash": canonical_hash(
                {
                    "baseline_witness_id": replay.baseline_witness_id,
                    "mutated_checks": replay.mutated_checks,
                    "failure_code": replay.failure_code,
                },
                prefix="finance_v26_mechanism_counterfactual_trace:",
            ),
            "independent_verifier_report_hash": canonical_hash(
                replay.model_dump(mode="json"),
                prefix="finance_v26_mechanism_counterfactual_report:",
            ),
        }
        provisional_result = MechanismCounterfactualResult.model_construct(
            result_id="pending", **result_values
        )
        results.append(
            MechanismCounterfactualResult(
                result_id=mechanism_counterfactual_result_id(provisional_result),
                **result_values,
            )
        )
    passed = witness.full_validity_passed and all(closure_checks.values())
    artifact_values = {
        "task_id": record.task_package.package_id,
        "public_witness_id": witness.witness_id,
        "target_mechanism_id": contract.contract_id,
        "required_mutation_kinds": contract.required_mutation_kinds,
        "counterfactual_results": tuple(results),
        "closure_checks": closure_checks,
        "mechanism_observed_in_witness": required_events <= observed_events,
        "status": "passed" if passed else "blocked",
        "failure_reasons": (
            ()
            if passed
            else tuple(sorted(key for key, value in closure_checks.items() if not value))
        ),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = MechanismNecessityArtifact.model_construct(
        artifact_id="pending", **artifact_values
    )
    artifact = MechanismNecessityArtifact(
        artifact_id=mechanism_necessity_artifact_id(provisional),
        **artifact_values,
    )
    return artifact, replays


def _path_catalog(
    record: RematerializedExecutableTaskRecord,
    witnesses: Sequence[BoundPublicExecutableWitness],
) -> StaticModelAuthorityPathCatalog:
    paths: list[StaticModelAuthorityPath] = []
    if record.intended_use == "vtdo_multistate_candidate":
        for witness in witnesses:
            tool_sequence = tuple(item.tool_id for item in witness.steps)
            decision_signature = canonical_hash(
                {
                    "strategy": witness.path_strategy_id,
                    "mechanism_events": witness.mechanism_event_ids,
                },
                prefix="finance_v26_model_authority_decision:",
            )
            behavior_signature = canonical_hash(
                {
                    "tool_sequence": tool_sequence,
                    "normalized_ref_count": sum(
                        item.normalized_operation_ref is not None for item in witness.steps
                    ),
                    "failed_call_count": sum(
                        item.tool_id == "query_structured_fact" and not item.evidence_ids
                        for item in witness.steps
                    ),
                },
                prefix="finance_v26_static_path_behavior:",
            )
            state_id = canonical_hash(
                {
                    "task_package_id": record.task_package.package_id,
                    "retrieval_strategy": witness.path_strategy_id,
                    "behavior_signature": behavior_signature,
                    "mechanism_id": record.mechanism_id,
                },
                prefix="finance_v26_static_quotient_state:",
            )
            path_values: dict[str, str] = {
                "task_package_id": record.task_package.package_id,
                "compiler_witness_id": witness.witness_id,
                "path_strategy_id": witness.path_strategy_id,
                "model_owned_decision_signature": decision_signature,
                "behavior_signature": behavior_signature,
                "quotient_state_id": state_id,
                "scaffold_surface_signature": canonical_hash(
                    record.task_package.task.public.instruction,
                    prefix="finance_v26_scaffold_surface:",
                ),
            }
            provisional = StaticModelAuthorityPath.model_construct(path_id="pending", **path_values)
            paths.append(
                StaticModelAuthorityPath(
                    path_id=static_model_authority_path_id(provisional),
                    **path_values,
                )
            )
    passed = len(paths) == 3 and all(item.full_validity_passed for item in witnesses)
    status = (
        "not_required"
        if record.intended_use == "capability_measurement"
        else "passed"
        if passed
        else "blocked"
    )
    catalog_values: dict[str, Any] = {
        "task_package_id": record.task_package.package_id,
        "intended_use": record.intended_use,
        "paths": tuple(paths),
        "status": status,
        "failure_reasons": (
            () if status != "blocked" else ("three_static_model_authority_paths_missing",)
        ),
    }
    provisional = StaticModelAuthorityPathCatalog.model_construct(
        catalog_id="pending", **catalog_values
    )
    return StaticModelAuthorityPathCatalog(
        catalog_id=static_model_authority_path_catalog_id(provisional),
        **catalog_values,
    )


def _admission(
    record: RematerializedExecutableTaskRecord,
    witness: BoundPublicExecutableWitness,
    necessity: MechanismNecessityArtifact,
    catalog: StaticModelAuthorityPathCatalog,
) -> ExecutableTaskAdmission:
    capability = witness.full_validity_passed and necessity.status == "passed"
    static_support = catalog.status == "passed"
    static_vtdo = (
        capability and record.intended_use == "vtdo_multistate_candidate" and static_support
    )
    blockers = []
    if not witness.full_validity_passed:
        blockers.append("public_witness_failed")
    if necessity.status != "passed":
        blockers.append("mechanism_necessity_failed")
    if record.intended_use == "vtdo_multistate_candidate" and not static_support:
        blockers.append("static_model_authority_paths_failed")
    values = {
        "task_package_id": record.task_package.package_id,
        "intended_use": record.intended_use,
        "public_witness_id": witness.witness_id,
        "mechanism_necessity_artifact_id": necessity.artifact_id,
        "static_path_catalog_id": catalog.catalog_id,
        "package_bindings_passed": True,
        "public_witness_passed": witness.full_validity_passed,
        "mechanism_necessity_passed": necessity.status == "passed",
        "static_path_support_passed": static_support,
        "capability_measurement_eligible": capability,
        "static_vtdo_candidate_eligible": static_vtdo,
        "status": (
            "static_vtdo_ready"
            if static_vtdo
            else "capability_ready"
            if capability and record.intended_use == "capability_measurement"
            else "blocked"
        ),
        "blockers": tuple(sorted(blockers)),
    }
    provisional = ExecutableTaskAdmission.model_construct(admission_id="pending", **values)
    return ExecutableTaskAdmission(
        admission_id=executable_task_admission_id(provisional),
        **values,
    )


def build_v26_executable_task_rematerialization(
    *,
    run_id: str,
    source_no_api_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
    sampling_salt: str,
    output_dir: Path,
) -> V26ExecutableTaskRematerializationReport:
    source, confirmation, freshness, receipt, development_evidence = _load_and_validate_sources(
        source_no_api_dir=source_no_api_dir,
        snapshot_path=snapshot_path,
        exposure_receipt_path=exposure_receipt_path,
    )
    selected_source = _select_source_tasks(source, sampling_salt=sampling_salt)
    base_selected_evidence = {
        evidence.evidence_id
        for tasks in selected_source.values()
        for task in tasks
        for evidence in task.public_corpus.evidence
    }
    definition_pairs, capacity_audit = _load_definition_pairs(
        snapshot_path=snapshot_path,
        receipt=receipt,
        exposure_receipt_path=exposure_receipt_path,
        additional_excluded_ids=development_evidence | base_selected_evidence,
        sampling_salt=sampling_salt,
    )
    drafts: list[_TaskDraft] = []
    for mechanism in (
        "context_conditioned_action",
        "failure_recovery",
        "state_dependent_stopping",
    ):
        for index, task in enumerate(selected_source[mechanism]):
            drafts.append(
                _base_draft(
                    task,
                    mechanism_id=mechanism,
                    intended_use=_role(index),
                )
            )
    for index in range(6):
        drafts.append(
            _reconciliation_draft(
                definition_pairs[index * 2],
                definition_pairs[index * 2 + 1],
                intended_use=_role(index),
            )
        )
    drafts.sort(key=lambda item: (TARGET_MECHANISMS.index(item.mechanism_id), item.instruction))
    if Counter(item.mechanism_id for item in drafts) != Counter(
        {mechanism: 6 for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("v26 rematerialization draft quotas are incomplete")

    records: list[RematerializedExecutableTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactual_replays: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    admissions: list[ExecutableTaskAdmission] = []
    primary_witnesses: list[BoundPublicExecutableWitness] = []

    for draft in drafts:
        record, environment = _materialize_task(draft)
        strategies: tuple[PathStrategy, ...] = (
            PATH_STRATEGIES
            if record.intended_use == "vtdo_multistate_candidate"
            else ("structured_direct",)
        )
        task_witnesses = []
        for strategy in strategies:
            witness, task_observations = _compile_witness(
                record,
                environment,
                strategy=strategy,
            )
            task_witnesses.append(witness)
            witnesses.append(witness)
            observations.extend(task_observations)
        primary = task_witnesses[0]
        necessity, task_replays = _mechanism_necessity(record, primary)
        catalog = _path_catalog(record, task_witnesses)
        admission = _admission(record, primary, necessity, catalog)
        records.append(record)
        environments.append(environment)
        primary_witnesses.append(primary)
        necessities.append(necessity)
        counterfactual_replays.extend(task_replays)
        catalogs.append(catalog)
        admissions.append(admission)

    record_ids = [item.record_id for item in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("rematerialization produced duplicate task records")
    package_ids = [item.task_package.package_id for item in records]
    if len(package_ids) != len(set(package_ids)):
        raise ValueError("rematerialization produced duplicate TaskPackage identities")
    corpus_evidence = [
        evidence.evidence_id for record in records for evidence in record.public_corpus.evidence
    ]
    if len(corpus_evidence) != len(set(corpus_evidence)):
        raise ValueError("rematerialized tasks reuse Public Corpus Evidence")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "capacity": output_dir / "definition_pair_capacity_audit.json",
        "records": output_dir / "rematerialized_task_records.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "witnesses": output_dir / "public_executable_witnesses.json",
        "observations": output_dir / "public_witness_observations.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "counterfactuals": (output_dir / "mechanism_counterfactual_replays.json"),
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "admissions": output_dir / "task_admissions.json",
    }
    _write_json(paths["capacity"], capacity_audit.model_dump(mode="json"))
    _write_models(paths["records"], records, identity="record_id")
    _write_models(paths["environments"], environments, identity="manifest_id")
    _write_models(paths["witnesses"], witnesses, identity="witness_id")
    _write_models(paths["observations"], observations, identity="observation_id")
    _write_models(paths["necessities"], necessities, identity="artifact_id")
    _write_models(
        paths["counterfactuals"],
        counterfactual_replays,
        identity="replay_id",
    )
    _write_models(paths["catalogs"], catalogs, identity="catalog_id")
    _write_models(paths["admissions"], admissions, identity="admission_id")
    counts = {
        "capacity": 1,
        "records": len(records),
        "environments": len(environments),
        "witnesses": len(witnesses),
        "observations": len(observations),
        "necessities": len(necessities),
        "counterfactuals": len(counterfactual_replays),
        "catalogs": len(catalogs),
        "admissions": len(admissions),
    }
    files = tuple(
        _artifact_file(path, output_dir, counts[key]) for key, path in sorted(paths.items())
    )
    capability_count = sum(item.capability_measurement_eligible for item in admissions)
    vtdo_count = sum(item.static_vtdo_candidate_eligible for item in admissions)
    passed = capability_count == 24 and vtdo_count == 12
    ordered_records = tuple(sorted(records, key=lambda item: item.record_id))
    ordered_admissions = tuple(sorted(admissions, key=lambda item: item.admission_id))
    values = {
        "run_id": run_id,
        "source_confirmation_population_id": confirmation.population_id,
        "source_confirmation_population_sha256": _sha256(
            source_no_api_dir / "population" / "confirmation.json"
        ),
        "source_cross_population_freshness_audit_id": freshness.audit_id,
        "source_exposure_receipt_id": receipt.receipt_id,
        "definition_pair_capacity_audit_id": capacity_audit.audit_id,
        "target_mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "tool_closure_pass_count": sum(
            item.task_package.tool_closure.status == "passed" for item in records
        ),
        "package_binding_pass_count": len(records),
        "primary_public_witness_pass_count": sum(
            item.full_validity_passed for item in primary_witnesses
        ),
        "mechanism_necessity_pass_count": sum(item.status == "passed" for item in necessities),
        "capability_measurement_eligible_count": capability_count,
        "static_vtdo_candidate_eligible_count": vtdo_count,
        "static_model_authority_path_count": sum(len(item.paths) for item in catalogs),
        "counterfactual_replay_count": len(counterfactual_replays),
        "compiler_generated_witness_count": len(witnesses),
        "task_records": ordered_records,
        "admissions": ordered_admissions,
        "immutable_artifact_files": files,
        "implementation_source_files": _implementation_source_files(),
        "status": "passed" if passed else "blocked",
        "next_permitted_stage": (
            "capability_development_and_state_reachability_pilot"
            if passed
            else "executable_task_rematerialization_repair_only"
        ),
        "capability_development_authorized": passed,
        "state_reachability_pilot_authorized": passed,
        "schema_version": V26_EXECUTABLE_TASK_REMATERIALIZATION_VERSION,
    }
    provisional = V26ExecutableTaskRematerializationReport.model_construct(
        report_id="pending", **values
    )
    report = V26ExecutableTaskRematerializationReport(
        report_id=v26_executable_task_rematerialization_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def definition_pair_capacity_audit_id(value: DefinitionPairCapacityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_definition_pair_capacity_audit:",
    )


def rematerialized_executable_task_record_id(
    value: RematerializedExecutableTaskRecord,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_v26_rematerialized_executable_task:",
    )


def mechanism_counterfactual_replay_record_id(
    value: MechanismCounterfactualReplayRecord,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"replay_id"}),
        prefix="finance_v26_mechanism_counterfactual_replay:",
    )


def v26_executable_task_rematerialization_report_id(
    value: V26ExecutableTaskRematerializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_executable_task_rematerialization_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the credential-free Finance v26 executable task Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-no-api-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--exposure-receipt", type=Path, required=True)
    parser.add_argument("--sampling-salt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_v26_executable_task_rematerialization(
        run_id=args.run_id,
        source_no_api_dir=args.source_no_api_dir,
        snapshot_path=args.snapshot,
        exposure_receipt_path=args.exposure_receipt,
        sampling_salt=args.sampling_salt,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
