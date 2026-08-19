from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
    SourceArtifactFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingVerifierQualificationReport,
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskRecord,
    OperationClosureAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    INSTRUMENT_TASK_COUNT,
    INSTRUMENT_TASKS_PER_MECHANISM,
    V26_VERIFIER_IMPLEMENTATION_VERSION,
    VerifierBoundInstrumentPopulationReport,
    VerifierV2TaskReplayBinding,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
)
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
    make_agent_tool_observation,
)

V26_VERIFIER_BOUND_INSTRUMENT_CONTRACT_VERSION = "finance_v26_verifier_bound_instrument_contract.v1"
V26_VERIFIER_BOUND_INSTRUMENT_JOB_VERSION = "finance_v26_verifier_bound_instrument_job.v1"
V26_VERIFIER_BOUND_INSTRUMENT_MANIFEST_VERSION = "finance_v26_verifier_bound_instrument_manifest.v1"
V26_VERIFIER_BOUND_SOURCE_REPLAY_VERSION = "finance_v26_verifier_bound_source_replay.v1"
V26_VERIFIER_BOUND_COMPILER_REPLAY_VERSION = "finance_v26_verifier_bound_compiler_replay.v1"
V26_VERIFIER_BOUND_ISOLATION_VERSION = "finance_v26_verifier_bound_public_isolation.v1"
V26_VERIFIER_BOUND_MUTATION_VERSION = "finance_v26_verifier_bound_preflight_mutation.v1"
V26_VERIFIER_BOUND_PREFLIGHT_VERSION = "finance_v26_verifier_bound_instrument_preflight.v1"

INSTRUMENT_REPLICAS_PER_TASK: Literal[4] = 4
INSTRUMENT_JOB_COUNT: Literal[32] = 32
MAXIMUM_MODEL_TOKENS_PER_ROLLOUT: Literal[120000] = 120000
MAXIMUM_ESTIMATED_COST_USD = 2.0

IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/executable_task.py",
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
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
        "phase1_v26_public_operation_rematerialization.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_verifier_bound_instrument_preflight.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_verifier_bound_task_rematerialization.py"
    ),
    "src/trusted_synthesis/runtime/agent/public_operation.py",
    "src/trusted_synthesis/runtime/tools.py",
)

MutationKind = Literal[
    "wrong_environment",
    "changed_result",
    "action_bearing_repair",
]
SourceKind = Literal[
    "task_source",
    "task_detail",
    "task_implementation",
    "verifier_source",
    "verifier_detail",
    "historical_job_manifest",
]

_PRIVATE_PUBLIC_KEYS = frozenset(
    {
        "expected_operator_id",
        "mechanism_private_state",
        "qualified_replay_contract_id",
        "qualified_verifier_report_id",
        "semantic_source_id",
        "source_program_node_id",
        "task_replay_binding_contract_id",
        "target_program_evidence_ids",
        "verifier_binding_id",
        "verifier_implementation_id",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: SourceKind
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("source replay entry hash changed")
        return self


class VerifierBoundSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    verifier_qualification_report_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=30)
    replayed_file_count: int = Field(ge=30)
    replay_pass_count: int = Field(ge=30)
    source_replay_before_client_construction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_VERIFIER_BOUND_SOURCE_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierBoundSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("source replay entries are not canonical")
        if self.replayed_file_count != len(self.entries):
            raise ValueError("source replay denominator changed")
        if self.replay_pass_count != self.replayed_file_count:
            raise ValueError("source replay is incomplete")
        if self.audit_id != verifier_bound_source_replay_audit_id(self):
            raise ValueError("Verifier-bound source replay identity is invalid")
        return self


class VerifierBoundInstrumentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    task_source_report_sha256: str = Field(min_length=64, max_length=64)
    verifier_qualification_report_id: str = Field(min_length=1)
    verifier_qualification_report_sha256: str = Field(min_length=64, max_length=64)
    qualified_replay_contract_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    task_record_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    task_package_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    environment_manifest_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    replay_binding_contract_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    mechanism_task_counts: dict[str, int]
    expected_job_count: Literal[32] = INSTRUMENT_JOB_COUNT
    replicas_per_task: Literal[4] = INSTRUMENT_REPLICAS_PER_TASK
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, str]
    provider_route_hash: str = Field(min_length=1)
    verifier_manifest: dict[str, Any]
    verifier_manifest_hash: str = Field(min_length=1)
    maximum_total_model_tokens_per_rollout: Literal[120000] = MAXIMUM_MODEL_TOKENS_PER_ROLLOUT
    maximum_total_estimated_cost_usd: float = Field(
        default=MAXIMUM_ESTIMATED_COST_USD, gt=0.0, le=2.0
    )
    measurement_instrument_only: Literal[True] = True
    model_comparison_forbidden: Literal[True] = True
    raw_first_provider_and_prompt_telemetry: Literal[True] = True
    runtime_verifier_semantic_commutativity_required: Literal[True] = True
    action_neutral_repair_audit_per_rollout: Literal[True] = True
    terminal_target_audit_per_rollout: Literal[True] = True
    stop_readiness_audit_per_rollout: Literal[True] = True
    non_replay_gates_independently_computed: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    historical_diagnostic_candidates_forbidden: Literal[True] = True
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=20)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=10, max_length=10
    )
    schema_version: str = V26_VERIFIER_BOUND_INSTRUMENT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> VerifierBoundInstrumentContract:
        groups = (
            self.task_record_ids,
            self.task_package_ids,
            self.environment_manifest_ids,
            self.replay_binding_contract_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("Instrument Contract identity sets are not canonical")
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("Instrument Contract mechanism quotas changed")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("Instrument Contract model identity changed")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != self.fallback_models:
            raise ValueError("Instrument Contract fallback policy changed")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("Instrument Contract does not fail closed on model mismatch")
        if self.maximum_total_estimated_cost_usd != MAXIMUM_ESTIMATED_COST_USD:
            raise ValueError("Instrument Contract resource ceiling changed")
        if self.model_config_hash != canonical_hash(
            self.model_invocation_config,
            prefix="finance_v26_verifier_bound_instrument_model_config:",
        ):
            raise ValueError("Instrument Contract model config hash is invalid")
        if self.provider_route_hash != canonical_hash(
            self.provider_route,
            prefix="finance_v26_verifier_bound_instrument_provider_route:",
        ):
            raise ValueError("Instrument Contract Provider route hash is invalid")
        if self.verifier_manifest_hash != canonical_hash(
            self.verifier_manifest,
            prefix="finance_v26_verifier_bound_instrument_verifier_manifest:",
        ):
            raise ValueError("Instrument Contract Verifier manifest hash is invalid")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("Instrument Contract implementation manifest is incomplete")
        if self.contract_id != verifier_bound_instrument_contract_id(self):
            raise ValueError("Verifier-bound Instrument Contract identity is invalid")
        return self


class VerifierBoundInstrumentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    sampling_mode: Literal["instrument_unconditional"] = "instrument_unconditional"
    empirical_role: Literal["instrument_requalification"] = "instrument_requalification"
    schema_version: str = V26_VERIFIER_BOUND_INSTRUMENT_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> VerifierBoundInstrumentJob:
        if self.job_id != verifier_bound_instrument_job_id(self):
            raise ValueError("Verifier-bound Instrument Job identity is invalid")
        return self


class VerifierBoundInstrumentJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    jobs: tuple[VerifierBoundInstrumentJob, ...] = Field(min_length=32, max_length=32)
    schema_version: str = V26_VERIFIER_BOUND_INSTRUMENT_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> VerifierBoundInstrumentJobManifest:
        if any(item.contract_id != self.contract_id for item in self.jobs):
            raise ValueError("Instrument Job Manifest crosses Contracts")
        identities = tuple(item.job_id for item in self.jobs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("Instrument Job identities are not canonical")
        task_counts = Counter(item.task_package_id for item in self.jobs)
        if len(task_counts) != INSTRUMENT_TASK_COUNT or set(task_counts.values()) != {
            INSTRUMENT_REPLICAS_PER_TASK
        }:
            raise ValueError("Instrument Job task denominators changed")
        if self.manifest_id != verifier_bound_instrument_manifest_id(self):
            raise ValueError("Verifier-bound Instrument Manifest identity is invalid")
        return self


class CompilerReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    witness_id: str = Field(min_length=1)
    observation_count: int = Field(ge=1)
    replay_result_id: str = Field(min_length=1)
    replay_failure_ids: tuple[str, ...] = ()
    all_observations_replayed: Literal[True] = True
    runtime_verifier_semantically_equal: Literal[True] = True
    compiler_witness_excluded_from_empirical_counts: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = V26_VERIFIER_BOUND_COMPILER_REPLAY_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompilerReplayAudit:
        if self.replay_failure_ids:
            raise ValueError("Compiler Witness Replay contains failures")
        if self.audit_id != compiler_replay_audit_id(self):
            raise ValueError("Compiler Replay audit identity is invalid")
        return self


class PublicPrivateIsolationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    forbidden_key_paths: tuple[str, ...] = ()
    private_identity_paths: tuple[str, ...] = ()
    verifier_binding_hidden_from_public_task: Literal[True] = True
    replay_contract_hidden_from_public_task: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = V26_VERIFIER_BOUND_ISOLATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicPrivateIsolationAudit:
        if self.forbidden_key_paths or self.private_identity_paths:
            raise ValueError("public Task exposes a private Verifier binding")
        if self.audit_id != public_private_isolation_audit_id(self):
            raise ValueError("Public/private isolation audit identity is invalid")
        return self


class PreflightMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mutation_kind: MutationKind
    source_observation_id: str = Field(min_length=1)
    mutated_observation_id: str = Field(min_length=1)
    mutated_observation_content_address_valid: Literal[True] = True
    baseline_replay_passed: Literal[True] = True
    replay_failure_ids: tuple[str, ...] = Field(min_length=1)
    mutation_rejected: Literal[True] = True
    model_trajectory_mutated: Literal[False] = False
    schema_version: str = V26_VERIFIER_BOUND_MUTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PreflightMutationAudit:
        expected_fragment = (
            "environment_identity"
            if self.mutation_kind == "wrong_environment"
            else "replay_mismatch"
        )
        if not any(expected_fragment in item for item in self.replay_failure_ids):
            raise ValueError("preflight mutation failed for another reason")
        if self.source_observation_id == self.mutated_observation_id:
            raise ValueError("preflight mutation reused an Observation identity")
        if self.audit_id != preflight_mutation_audit_id(self):
            raise ValueError("Preflight mutation audit identity is invalid")
        return self


class VerifierBoundInstrumentPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    verifier_qualification_report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    mechanism_task_counts: dict[str, int]
    expected_job_count: Literal[32] = INSTRUMENT_JOB_COUNT
    fresh_job_count: Literal[32] = INSTRUMENT_JOB_COUNT
    source_file_replay_pass_count: int = Field(ge=30)
    task_binding_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    verifier_v2_binding_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_runtime_witness_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_witness_observation_count: int = Field(ge=64)
    public_private_isolation_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    action_neutral_repair_audit_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    wrong_environment_mutation_reject_count: Literal[8] = INSTRUMENT_TASK_COUNT
    changed_result_mutation_reject_count: Literal[8] = INSTRUMENT_TASK_COUNT
    action_bearing_repair_mutation_reject_count: Literal[8] = INSTRUMENT_TASK_COUNT
    destructive_replay_mutation_reject_count: Literal[24] = 24
    terminal_reference_mutation_reject_count: Literal[24] = 24
    early_verification_mutation_reject_count: Literal[8] = INSTRUMENT_TASK_COUNT
    postcompletion_action_mutation_reject_count: Literal[8] = INSTRUMENT_TASK_COUNT
    authority_terminal_mutation_reject_count: Literal[40] = 40
    legacy_operation_mutation_reject_count: int = Field(ge=64)
    historical_job_manifest_count: int = Field(ge=4)
    historical_job_identity_overlap_count: Literal[0] = 0
    raw_first_path_collision_count: Literal[0] = 0
    independent_byte_rebuild_required: Literal[True] = True
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=20)
    immutable_detail_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=6, max_length=6)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=10, max_length=10
    )
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["fresh_verifier_v2_bound_instrument_requalification_only"] = (
        "fresh_verifier_v2_bound_instrument_requalification_only"
    )
    instrument_requalification_authorized: Literal[True] = True
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_VERIFIER_BOUND_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> VerifierBoundInstrumentPreflightReport:
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("Preflight report mechanism quotas changed")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("Preflight implementation manifest is incomplete")
        expected_details = (
            "compiler_replay_audits.json",
            "destructive_mutation_audits.json",
            "execution_contract.json",
            "job_manifest.json",
            "public_private_isolation_audits.json",
            "source_replay_audit.json",
        )
        if tuple(item.relative_path for item in self.immutable_detail_files) != expected_details:
            raise ValueError("Preflight detail manifest is incomplete")
        if self.report_id != verifier_bound_preflight_report_id(self):
            raise ValueError("Verifier-bound Instrument Preflight report identity is invalid")
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
            raise ValueError(f"Verifier-bound Preflight immutable JSON changed: {path}")
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
    try:
        relative_path = str(path.resolve().relative_to(package_root.resolve()))
    except ValueError:
        relative_path = f"external_task_source/{path.name}"
    return SourceArtifactFile(
        relative_path=relative_path,
        sha256=_sha256(path),
        record_count=_record_count(path),
    )


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _detail_file(path: Path, output_dir: Path, count: int) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def _register_replay_entry(
    entries: dict[str, SourceReplayEntry],
    *,
    path: Path,
    package_root: Path,
    expected_sha256: str,
    source_kind: SourceKind,
) -> None:
    if not path.is_file():
        raise ValueError(f"Preflight source file is missing: {path}")
    try:
        relative_path = str(path.resolve().relative_to(package_root.resolve()))
    except ValueError:
        relative_path = f"external_task_source/{path.name}"
    observed = _sha256(path)
    if observed != expected_sha256:
        raise ValueError(f"Preflight source replay failed: {path}")
    entry = SourceReplayEntry(
        relative_path=relative_path,
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=observed,
        byte_count=path.stat().st_size,
        passed=True,
    )
    prior = entries.get(relative_path)
    if prior is not None and prior.expected_sha256 != entry.expected_sha256:
        raise ValueError(f"Preflight source manifests disagree: {relative_path}")
    if prior is None:
        entries[relative_path] = entry


def _source_replay_audit(
    *,
    task_source_dir: Path,
    task_report: VerifierBoundInstrumentPopulationReport,
    verifier_qualification_dir: Path,
    qualification: AuthorityPreservingVerifierQualificationReport,
    historical_job_manifest_paths: Sequence[Path],
    package_root: Path,
) -> VerifierBoundSourceReplayAudit:
    entries: dict[str, SourceReplayEntry] = {}
    task_report_path = task_source_dir / "report.json"
    _register_replay_entry(
        entries,
        path=task_report_path,
        package_root=package_root,
        expected_sha256=_sha256(task_report_path),
        source_kind="task_source",
    )
    for item in task_report.source_artifact_files:
        _register_replay_entry(
            entries,
            path=package_root / item.relative_path,
            package_root=package_root,
            expected_sha256=item.sha256,
            source_kind="task_source",
        )
    for item in task_report.immutable_artifact_files:
        _register_replay_entry(
            entries,
            path=task_source_dir / item.relative_path,
            package_root=package_root,
            expected_sha256=item.sha256,
            source_kind="task_detail",
        )
    for item in task_report.implementation_source_files:
        _register_replay_entry(
            entries,
            path=package_root / item.relative_path,
            package_root=package_root,
            expected_sha256=item.sha256,
            source_kind="task_implementation",
        )
    qualification_path = verifier_qualification_dir / "report.json"
    _register_replay_entry(
        entries,
        path=qualification_path,
        package_root=package_root,
        expected_sha256=task_report.verifier_qualification_report_sha256,
        source_kind="verifier_source",
    )
    for item in qualification.immutable_detail_files:
        _register_replay_entry(
            entries,
            path=verifier_qualification_dir / item.relative_path,
            package_root=package_root,
            expected_sha256=item.sha256,
            source_kind="verifier_detail",
        )
    for path in historical_job_manifest_paths:
        _register_replay_entry(
            entries,
            path=path,
            package_root=package_root,
            expected_sha256=_sha256(path),
            source_kind="historical_job_manifest",
        )
    ordered = tuple(entries[path] for path in sorted(entries))
    values = {
        "task_source_report_id": task_report.report_id,
        "verifier_qualification_report_id": qualification.report_id,
        "entries": ordered,
        "replayed_file_count": len(ordered),
        "replay_pass_count": len(ordered),
    }
    provisional = VerifierBoundSourceReplayAudit.model_construct(audit_id="pending", **values)
    return VerifierBoundSourceReplayAudit(
        audit_id=verifier_bound_source_replay_audit_id(provisional),
        **values,
    )


def _model_invocation_config() -> dict[str, Any]:
    return {
        "api_key_env": "DEEPSEEK_API_KEY",
        "auto_discover_models": True,
        "contract_repair_attempts": 1,
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "extra_headers": {},
        "fallback_models": [],
        "input_cache_hit_cost_per_million": 0.0028,
        "input_cache_miss_cost_per_million": 0.14,
        "input_cost_per_million": 0.0,
        "interaction_protocol": "host_instrumented",
        "max_output_tokens": 4096,
        "maximum_model_attempts": 1,
        "model": "deepseek-v4-flash",
        "models_endpoint": "https://api.deepseek.com/models",
        "output_cost_per_million": 0.28,
        "preferred_model_patterns": [],
        "pricing_checked_at": "2026-08-11",
        "pricing_source_url": "https://api-docs.deepseek.com/quick_start/pricing",
        "provider": "deepseek",
        "request_body_overrides": {"thinking": {"type": "disabled"}, "top_p": 0.9},
        "require_requested_model": True,
        "temperature": 0.6,
        "timeout_seconds": 180.0,
    }


def _build_contract(
    *,
    run_id: str,
    task_source_dir: Path,
    task_report: VerifierBoundInstrumentPopulationReport,
    qualification_dir: Path,
    qualification: AuthorityPreservingVerifierQualificationReport,
    replay_contract: AuthorityPreservingReplayContract,
    source_replay: VerifierBoundSourceReplayAudit,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    historical_job_manifest_paths: Sequence[Path],
    package_root: Path,
) -> VerifierBoundInstrumentContract:
    model_config = _model_invocation_config()
    provider_route = {
        "endpoint_host": "api.deepseek.com",
        "model": "deepseek-v4-flash",
        "provider": "deepseek",
    }
    verifier_manifest = {
        "qualified_replay_contract_id": replay_contract.contract_id,
        "qualified_verifier_report_id": qualification.report_id,
        "task_replay_binding_contract_ids": tuple(sorted(item.contract_id for item in bindings)),
        "verifier_implementation_version": V26_VERIFIER_IMPLEMENTATION_VERSION,
    }
    source_paths = tuple(
        sorted(
            {
                task_source_dir / "report.json",
                *(
                    task_source_dir / item.relative_path
                    for item in task_report.immutable_artifact_files
                ),
                qualification_dir / "report.json",
                qualification_dir / "replay_contract.json",
                *historical_job_manifest_paths,
            },
            key=lambda item: str(item),
        )
    )
    values = {
        "run_id": run_id,
        "task_source_report_id": task_report.report_id,
        "task_source_report_sha256": _sha256(task_source_dir / "report.json"),
        "verifier_qualification_report_id": qualification.report_id,
        "verifier_qualification_report_sha256": _sha256(qualification_dir / "report.json"),
        "qualified_replay_contract_id": replay_contract.contract_id,
        "source_replay_audit_id": source_replay.audit_id,
        "task_record_ids": tuple(sorted(item.record_id for item in records)),
        "task_package_ids": tuple(sorted(item.task_package.package_id for item in records)),
        "environment_manifest_ids": tuple(sorted(item.manifest_id for item in environments)),
        "replay_binding_contract_ids": tuple(sorted(item.contract_id for item in bindings)),
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "model_invocation_config": model_config,
        "model_config_hash": canonical_hash(
            model_config,
            prefix="finance_v26_verifier_bound_instrument_model_config:",
        ),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route,
            prefix="finance_v26_verifier_bound_instrument_provider_route:",
        ),
        "verifier_manifest": verifier_manifest,
        "verifier_manifest_hash": canonical_hash(
            verifier_manifest,
            prefix="finance_v26_verifier_bound_instrument_verifier_manifest:",
        ),
        "source_artifact_files": tuple(_source_file(path, package_root) for path in source_paths),
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = VerifierBoundInstrumentContract.model_construct(contract_id="pending", **values)
    return VerifierBoundInstrumentContract(
        contract_id=verifier_bound_instrument_contract_id(provisional),
        **values,
    )


def _build_job_manifest(
    contract: VerifierBoundInstrumentContract,
    records: Sequence[OperationalTaskRecord],
    bindings: Sequence[VerifierV2TaskReplayBinding],
) -> VerifierBoundInstrumentJobManifest:
    binding_by_source = {item.semantic_source_id: item for item in bindings}
    jobs = []
    for record in records:
        package = record.task_package
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        for replicate_index in range(INSTRUMENT_REPLICAS_PER_TASK):
            values = {
                "contract_id": contract.contract_id,
                "task_record_id": record.record_id,
                "task_package_id": package.package_id,
                "environment_manifest_id": record.environment_manifest_id,
                "replay_binding_contract_id": binding.contract_id,
                "mechanism_id": record.mechanism_id,
                "replicate_index": replicate_index,
            }
            provisional = VerifierBoundInstrumentJob.model_construct(job_id="pending", **values)
            jobs.append(
                VerifierBoundInstrumentJob(
                    job_id=verifier_bound_instrument_job_id(provisional),
                    **values,
                )
            )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    values = {"contract_id": contract.contract_id, "jobs": ordered}
    provisional_manifest = VerifierBoundInstrumentJobManifest.model_construct(
        manifest_id="pending", **values
    )
    return VerifierBoundInstrumentJobManifest(
        manifest_id=verifier_bound_instrument_manifest_id(provisional_manifest),
        **values,
    )


def _compiler_replay_audits(
    *,
    replay_contract: AuthorityPreservingReplayContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    witnesses: Sequence[BoundPublicExecutableWitness],
    observations: Sequence[AgentToolObservation],
) -> tuple[CompilerReplayAudit, ...]:
    environment_by_id = {item.manifest_id: item for item in environments}
    binding_by_source = {item.semantic_source_id: item for item in bindings}
    witness_by_task = {item.task_package_id: item for item in witnesses}
    observation_by_id = {item.observation_id: item for item in observations}
    audits = []
    for record in records:
        package = record.task_package
        witness = witness_by_task[package.package_id]
        history = tuple(observation_by_id[item.observation_id] for item in witness.steps)
        result = replay_authority_preserving_observations(
            replay_contract,
            record,
            environment_by_id[record.environment_manifest_id],
            history,
        )
        if not result.passed or result.replayed_observation_count != len(history):
            raise ValueError(f"Compiler Witness Replay failed: {package.package_id}")
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        values = {
            "task_package_id": package.package_id,
            "replay_binding_contract_id": binding.contract_id,
            "witness_id": witness.witness_id,
            "observation_count": len(history),
            "replay_result_id": result.replay_id,
            "replay_failure_ids": result.failure_ids,
        }
        provisional = CompilerReplayAudit.model_construct(audit_id="pending", **values)
        audits.append(
            CompilerReplayAudit(
                audit_id=compiler_replay_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(audits, key=lambda item: item.audit_id))


def _forbidden_key_paths(value: Any, path: str = "public") -> tuple[str, ...]:
    output: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key) in _PRIVATE_PUBLIC_KEYS:
                output.append(child)
            output.extend(_forbidden_key_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            output.extend(_forbidden_key_paths(item, f"{path}[{index}]"))
    return tuple(output)


def _private_identity_paths(
    value: Any,
    private_values: set[str],
    path: str = "public",
) -> tuple[str, ...]:
    output: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            output.extend(_private_identity_paths(item, private_values, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            output.extend(_private_identity_paths(item, private_values, f"{path}[{index}]"))
    elif isinstance(value, str) and value in private_values:
        output.append(path)
    return tuple(output)


def _isolation_audits(
    records: Sequence[OperationalTaskRecord],
    bindings: Sequence[VerifierV2TaskReplayBinding],
) -> tuple[PublicPrivateIsolationAudit, ...]:
    binding_by_source = {item.semantic_source_id: item for item in bindings}
    audits = []
    for record in records:
        package = record.task_package
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        public = package.task.public.model_dump(mode="json")
        forbidden = _forbidden_key_paths(public)
        private_values = {
            package.semantic_source.semantic_source_id,
            package.verifier_binding.binding_id,
            binding.contract_id,
            binding.qualified_replay_contract_id,
            binding.qualified_verifier_report_id,
            binding.source_program_dag_hash,
            binding.source_verifier_dag_hash,
        }
        identities = _private_identity_paths(public, private_values)
        if forbidden or identities:
            raise ValueError(f"public Task exposes private binding: {package.package_id}")
        values = {
            "task_package_id": package.package_id,
            "replay_binding_contract_id": binding.contract_id,
            "forbidden_key_paths": forbidden,
            "private_identity_paths": identities,
        }
        provisional = PublicPrivateIsolationAudit.model_construct(audit_id="pending", **values)
        audits.append(
            PublicPrivateIsolationAudit(
                audit_id=public_private_isolation_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(audits, key=lambda item: item.audit_id))


def _observation_result(observation: AgentToolObservation) -> AgentToolResult:
    return AgentToolResult(
        status=observation.status,
        result=observation.result,
        evidence_ids=observation.evidence_ids,
        provenance_hashes=observation.provenance_hashes,
        host_events=observation.host_events,
        error_code=observation.error_code,
        error_message=observation.error_message,
    )


def _changed_result_observation(observation: AgentToolObservation) -> AgentToolObservation:
    payload = json.loads(json.dumps(observation.result, sort_keys=True))
    payload["preflight_changed_result"] = True
    result = _observation_result(observation).model_copy(update={"result": payload})
    return make_agent_tool_observation(
        environment_manifest_id=observation.environment_manifest_id,
        call=observation.call,
        result=result,
        observation_time_hash=canonical_hash(
            {
                "source_observation_id": observation.observation_id,
                "mutation_kind": "changed_result",
            },
            prefix="finance_v26_verifier_bound_mutation_time:",
        ),
    )


def _wrong_environment_observation(
    observation: AgentToolObservation,
    wrong_environment_id: str,
) -> AgentToolObservation:
    return make_agent_tool_observation(
        environment_manifest_id=wrong_environment_id,
        call=observation.call,
        result=_observation_result(observation),
        observation_time_hash=canonical_hash(
            {
                "source_observation_id": observation.observation_id,
                "mutation_kind": "wrong_environment",
                "wrong_environment_id": wrong_environment_id,
            },
            prefix="finance_v26_verifier_bound_mutation_time:",
        ),
    )


def _action_bearing_pair(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> tuple[AgentToolObservation, AgentToolObservation]:
    call = AgentToolCall(call_index=1, tool_id="calculator", arguments={})
    raw = agent_tool_argument_rejection(environment.tools_by_id["calculator"], call)
    if raw is None:
        raise ValueError("calculator empty-argument mutation did not fail")
    projected = public_action_neutral_repair_result(
        record.task_package.task.public,
        (),
        call,
        raw,
    )
    time_hash = canonical_hash(
        {"task_package_id": record.task_package.package_id, "kind": "repair_baseline"},
        prefix="finance_v26_verifier_bound_mutation_time:",
    )
    baseline = make_agent_tool_observation(
        environment_manifest_id=environment.manifest_id,
        call=call,
        result=projected,
        observation_time_hash=time_hash,
    )
    payload = json.loads(json.dumps(projected.result, sort_keys=True))
    retry = dict(payload["retry_contract"])
    retry["suggested_argument_patch"] = {
        "operator": "add",
        "parameters": {"values": [1, 2]},
    }
    payload["retry_contract"] = retry
    mutated_result = projected.model_copy(update={"result": payload})
    mutated = make_agent_tool_observation(
        environment_manifest_id=environment.manifest_id,
        call=call,
        result=mutated_result,
        observation_time_hash=canonical_hash(
            {"task_package_id": record.task_package.package_id, "kind": "action_bearing"},
            prefix="finance_v26_verifier_bound_mutation_time:",
        ),
    )
    return baseline, mutated


def _mutation_audit(
    *,
    replay_contract: AuthorityPreservingReplayContract,
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    source: AgentToolObservation,
    mutated: AgentToolObservation,
    mutation_kind: MutationKind,
) -> PreflightMutationAudit:
    baseline = replay_authority_preserving_observations(
        replay_contract, record, environment, (source,)
    )
    result = replay_authority_preserving_observations(
        replay_contract, record, environment, (mutated,)
    )
    if not baseline.passed or result.passed:
        raise ValueError(f"Preflight mutation did not form a valid contrast: {mutation_kind}")
    values = {
        "task_package_id": record.task_package.package_id,
        "mutation_kind": mutation_kind,
        "source_observation_id": source.observation_id,
        "mutated_observation_id": mutated.observation_id,
        "replay_failure_ids": result.failure_ids,
    }
    provisional = PreflightMutationAudit.model_construct(audit_id="pending", **values)
    return PreflightMutationAudit(
        audit_id=preflight_mutation_audit_id(provisional),
        **values,
    )


def _mutation_audits(
    *,
    replay_contract: AuthorityPreservingReplayContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    witnesses: Sequence[BoundPublicExecutableWitness],
    observations: Sequence[AgentToolObservation],
) -> tuple[PreflightMutationAudit, ...]:
    environment_by_id = {item.manifest_id: item for item in environments}
    witness_by_task = {item.task_package_id: item for item in witnesses}
    observation_by_id = {item.observation_id: item for item in observations}
    ordered_environment_ids = tuple(sorted(environment_by_id))
    audits = []
    for record in records:
        environment = environment_by_id[record.environment_manifest_id]
        witness = witness_by_task[record.task_package.package_id]
        source = observation_by_id[witness.steps[0].observation_id]
        wrong_environment_id = next(
            item for item in ordered_environment_ids if item != environment.manifest_id
        )
        audits.append(
            _mutation_audit(
                replay_contract=replay_contract,
                record=record,
                environment=environment,
                source=source,
                mutated=_wrong_environment_observation(source, wrong_environment_id),
                mutation_kind="wrong_environment",
            )
        )
        audits.append(
            _mutation_audit(
                replay_contract=replay_contract,
                record=record,
                environment=environment,
                source=source,
                mutated=_changed_result_observation(source),
                mutation_kind="changed_result",
            )
        )
        repair_baseline, action_bearing = _action_bearing_pair(record, environment)
        audits.append(
            _mutation_audit(
                replay_contract=replay_contract,
                record=record,
                environment=environment,
                source=repair_baseline,
                mutated=action_bearing,
                mutation_kind="action_bearing_repair",
            )
        )
    return tuple(sorted(audits, key=lambda item: item.audit_id))


def _historical_job_ids(paths: Sequence[Path]) -> set[str]:
    output: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError(f"historical Job Manifest is malformed: {path}")
        identities = {str(item["job_id"]) for item in jobs}
        if len(identities) != len(jobs):
            raise ValueError(f"historical Job Manifest contains duplicates: {path}")
        output.update(identities)
    return output


def _validate_task_bindings(
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    task_audits: Sequence[AuthorityPreservingTaskAudit],
) -> None:
    environment_by_id = {item.manifest_id: item for item in environments}
    binding_by_source = {item.semantic_source_id: item for item in bindings}
    audit_by_task = {item.task_package_id: item for item in task_audits}
    for record in records:
        package = record.task_package
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        environment = environment_by_id[record.environment_manifest_id]
        task_audit = audit_by_task[package.package_id]
        repair = package.action_neutral_repair_contract
        target = package.terminal_verification_target
        if repair is None or target is None:
            raise ValueError("Preflight task lacks authority-preserving contracts")
        oracle_binding = package.task.oracle.selection_contract.get(
            "authority_preserving_verifier_v2_binding"
        )
        if (
            package.verifier_binding.verifier_implementation_id != binding.contract_id
            or package.verifier_binding.verifier_version != V26_VERIFIER_IMPLEMENTATION_VERSION
            or binding.environment_manifest_id != environment.manifest_id
            or binding.environment_manifest_hash != record.environment_manifest_hash
            or binding.public_operation_contract_id != package.operation_contract.contract_id
            or binding.action_neutral_repair_contract_id != repair.contract_id
            or binding.terminal_verification_target_id != target.target_id
            or not isinstance(oracle_binding, Mapping)
            or oracle_binding.get("task_replay_binding_contract_id") != binding.contract_id
            or task_audit.status != "passed"
            or task_audit.repair_prompt_audit.action_binding_paths
        ):
            raise ValueError(f"Preflight task binding failed: {package.package_id}")


def build_verifier_bound_instrument_preflight(
    *,
    run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    historical_job_manifest_paths: Sequence[Path],
    output_dir: Path,
    package_root: Path,
) -> VerifierBoundInstrumentPreflightReport:
    task_report = VerifierBoundInstrumentPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    qualification = AuthorityPreservingVerifierQualificationReport.model_validate_json(
        (verifier_qualification_dir / "report.json").read_text(encoding="utf-8")
    )
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    if (
        task_report.verifier_qualification_report_id != qualification.report_id
        or task_report.qualified_replay_contract_id != replay_contract.contract_id
        or qualification.replay_contract != replay_contract
    ):
        raise ValueError("Preflight task source binds another Verifier qualification")
    records = _load_rows(task_source_dir / "operational_task_records.json", OperationalTaskRecord)
    environments = _load_rows(
        task_source_dir / "tool_environment_manifests.json", AgentToolEnvironmentManifest
    )
    bindings = _load_rows(
        task_source_dir / "verifier_v2_replay_bindings.json", VerifierV2TaskReplayBinding
    )
    witnesses = _load_rows(
        task_source_dir / "operational_public_witnesses.json", BoundPublicExecutableWitness
    )
    observations = _load_rows(
        task_source_dir / "operational_witness_observations.json", AgentToolObservation
    )
    task_audits = _load_rows(
        task_source_dir / "authority_preserving_task_audits.json", AuthorityPreservingTaskAudit
    )
    closures = _load_rows(task_source_dir / "operation_closure_audits.json", OperationClosureAudit)
    groups = (records, environments, bindings, witnesses, task_audits, closures)
    if any(len(group) != INSTRUMENT_TASK_COUNT for group in groups):
        raise ValueError("Preflight task source denominator changed")
    _validate_task_bindings(records, environments, bindings, task_audits)

    source_replay = _source_replay_audit(
        task_source_dir=task_source_dir,
        task_report=task_report,
        verifier_qualification_dir=verifier_qualification_dir,
        qualification=qualification,
        historical_job_manifest_paths=historical_job_manifest_paths,
        package_root=package_root,
    )
    contract = _build_contract(
        run_id=run_id,
        task_source_dir=task_source_dir,
        task_report=task_report,
        qualification_dir=verifier_qualification_dir,
        qualification=qualification,
        replay_contract=replay_contract,
        source_replay=source_replay,
        records=records,
        environments=environments,
        bindings=bindings,
        historical_job_manifest_paths=historical_job_manifest_paths,
        package_root=package_root,
    )
    manifest = _build_job_manifest(contract, records, bindings)
    compiler_audits = _compiler_replay_audits(
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        bindings=bindings,
        witnesses=witnesses,
        observations=observations,
    )
    isolation_audits = _isolation_audits(records, bindings)
    mutation_audits = _mutation_audits(
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        witnesses=witnesses,
        observations=observations,
    )
    historical_ids = _historical_job_ids(historical_job_manifest_paths)
    new_ids = {item.job_id for item in manifest.jobs}
    overlap = new_ids & historical_ids
    if overlap:
        raise ValueError("Preflight Instrument Job identities overlap historical Jobs")
    terminal_kinds = Counter(
        mutation.mutation_kind for audit in task_audits for mutation in audit.verification_mutations
    )
    if terminal_kinds != Counter(
        {
            "missing_terminal_reference": 8,
            "wrong_terminal_reference": 8,
            "extra_terminal_claim_field": 8,
            "verification_before_terminal": 8,
            "postcompletion_action": 8,
        }
    ):
        raise ValueError("Preflight authority/terminal mutation matrix changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "source_replay": output_dir / "source_replay_audit.json",
        "contract": output_dir / "execution_contract.json",
        "manifest": output_dir / "job_manifest.json",
        "compiler": output_dir / "compiler_replay_audits.json",
        "isolation": output_dir / "public_private_isolation_audits.json",
        "mutations": output_dir / "destructive_mutation_audits.json",
    }
    _write_json(paths["source_replay"], source_replay.model_dump(mode="json"))
    _write_json(paths["contract"], contract.model_dump(mode="json"))
    _write_json(paths["manifest"], manifest.model_dump(mode="json"))
    _write_models(paths["compiler"], compiler_audits, "audit_id")
    _write_models(paths["isolation"], isolation_audits, "audit_id")
    _write_models(paths["mutations"], mutation_audits, "audit_id")
    detail_counts = {
        "source_replay": 1,
        "contract": 1,
        "manifest": 1,
        "compiler": len(compiler_audits),
        "isolation": len(isolation_audits),
        "mutations": len(mutation_audits),
    }
    detail_files = tuple(
        sorted(
            (_detail_file(path, output_dir, detail_counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    mutation_counts = Counter(item.mutation_kind for item in mutation_audits)
    values = {
        "run_id": run_id,
        "task_source_report_id": task_report.report_id,
        "verifier_qualification_report_id": qualification.report_id,
        "source_replay_audit_id": source_replay.audit_id,
        "contract_id": contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "mechanism_task_counts": task_report.mechanism_task_counts,
        "source_file_replay_pass_count": source_replay.replay_pass_count,
        "compiler_witness_observation_count": sum(
            item.observation_count for item in compiler_audits
        ),
        "wrong_environment_mutation_reject_count": mutation_counts["wrong_environment"],
        "changed_result_mutation_reject_count": mutation_counts["changed_result"],
        "action_bearing_repair_mutation_reject_count": mutation_counts["action_bearing_repair"],
        "legacy_operation_mutation_reject_count": sum(
            len(item.mutation_results) for item in closures
        ),
        "historical_job_manifest_count": len(historical_job_manifest_paths),
        "source_artifact_files": contract.source_artifact_files,
        "immutable_detail_files": detail_files,
        "implementation_source_files": contract.implementation_source_files,
    }
    provisional = VerifierBoundInstrumentPreflightReport.model_construct(
        report_id="pending", **values
    )
    report = VerifierBoundInstrumentPreflightReport(
        report_id=verifier_bound_preflight_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def verifier_bound_source_replay_audit_id(value: VerifierBoundSourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_source_replay:",
    )


def verifier_bound_instrument_contract_id(value: VerifierBoundInstrumentContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_verifier_bound_instrument_contract:",
    )


def verifier_bound_instrument_job_id(value: VerifierBoundInstrumentJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"job_id"}),
        prefix="finance_v26_verifier_bound_instrument_job:",
    )


def verifier_bound_instrument_manifest_id(
    value: VerifierBoundInstrumentJobManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_verifier_bound_instrument_manifest:",
    )


def compiler_replay_audit_id(value: CompilerReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_compiler_replay:",
    )


def public_private_isolation_audit_id(value: PublicPrivateIsolationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_public_isolation:",
    )


def preflight_mutation_audit_id(value: PreflightMutationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_verifier_bound_preflight_mutation:",
    )


def verifier_bound_preflight_report_id(
    value: VerifierBoundInstrumentPreflightReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_verifier_bound_instrument_preflight:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.77 Verifier-v2-bound Instrument Preflight"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument(
        "--historical-job-manifest",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_verifier_bound_instrument_preflight(
        run_id=args.run_id,
        task_source_dir=args.task_source_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        historical_job_manifest_paths=tuple(args.historical_job_manifest),
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
