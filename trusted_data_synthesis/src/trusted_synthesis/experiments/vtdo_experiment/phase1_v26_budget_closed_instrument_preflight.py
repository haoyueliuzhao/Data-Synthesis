from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
    SourceArtifactFile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingVerifierQualificationReport,
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
    InstrumentFailureChannels,
    SchemaClosedTraceSidecar,
    build_instrument_failure_channels,
    compiler_witness_trajectory,
    score_completed_trajectory,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_task_rematerialization import (  # noqa: E501
    CONTRACT_REPAIR_RESERVE_TOKENS,
    FINAL_ANSWER_RESERVE_TOKENS,
    INSTRUMENT_TASK_COUNT,
    INSTRUMENT_TASKS_PER_MECHANISM,
    MAXIMUM_MODEL_TOKENS_PER_ROLLOUT,
    MAXIMUM_OUTPUT_TOKENS,
    MAXIMUM_PROMPT_UTF8_BYTES,
    PROVIDER_CHAT_ENVELOPE_TOKEN_UPPER_BOUND,
    BudgetClosedInstrumentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    SourceReplayEntry,
    VerifierBoundSourceReplayAudit,
    _compiler_replay_audits,
    _detail_file,
    _isolation_audits,
    _model_invocation_config,
    _mutation_audits,
    _register_replay_entry,
    _validate_task_bindings,
    verifier_bound_source_replay_audit_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    VerifierV2TaskReplayBinding,
    _load_rows,
    _record_count,
    _write_json,
    _write_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    BudgetClosedJsonClient,
    ProviderTokenBudgetContract,
    make_provider_token_budget_contract,
)
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

V26_BUDGET_CLOSED_INSTRUMENT_CONTRACT_VERSION = "finance_v26_budget_closed_instrument_contract.v1"
V26_BUDGET_CLOSED_INSTRUMENT_JOB_VERSION = "finance_v26_budget_closed_instrument_job.v1"
V26_BUDGET_CLOSED_INSTRUMENT_MANIFEST_VERSION = "finance_v26_budget_closed_instrument_manifest.v1"
V26_BUDGET_CLOSED_COMPILER_SCORING_AUDIT_VERSION = (
    "finance_v26_budget_closed_compiler_scoring_audit.v1"
)
V26_BUDGET_CLOSED_BUDGET_MUTATION_VERSION = "finance_v26_budget_closed_budget_mutation.v1"
V26_BUDGET_CLOSED_SCORING_MUTATION_VERSION = "finance_v26_budget_closed_scoring_mutation.v1"
V26_BUDGET_CLOSED_PREFLIGHT_VERSION = "finance_v26_budget_closed_instrument_preflight.v1"

INSTRUMENT_REPLICAS_PER_TASK: Literal[4] = 4
INSTRUMENT_JOB_COUNT: Literal[32] = 32
MAXIMUM_ESTIMATED_COST_USD: Final = 2.0

BudgetMutationKind = Literal[
    "exact_boundary",
    "one_token_over",
    "changed_usage",
    "missing_usage",
    "oversized_prompt",
    "final_answer_reserve_insufficient",
    "contract_repair_reserve_insufficient",
]
ScoringMutationKind = Literal[
    "legacy_observation_id_access",
    "trajectory_step_schema_change",
    "failure_namespace_cross_contamination",
]

IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
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
                "phase1_v26_budget_closed_instrument.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_closed_instrument_preflight.py"
            ),
            (
                "src/trusted_synthesis/experiments/vtdo_experiment/"
                "phase1_v26_budget_closed_task_rematerialization.py"
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
            "src/trusted_synthesis/runtime/agent/budget_closed.py",
            "src/trusted_synthesis/runtime/agent/public_operation.py",
            "src/trusted_synthesis/runtime/tools.py",
        }
    )
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetClosedInstrumentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    task_source_report_sha256: str = Field(min_length=64, max_length=64)
    verifier_qualification_report_id: str = Field(min_length=1)
    verifier_qualification_report_sha256: str = Field(min_length=64, max_length=64)
    qualified_replay_contract_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    provider_token_budget_contract: ProviderTokenBudgetContract
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
    maximum_total_estimated_cost_usd: float = Field(gt=0.0, le=2.0)
    measurement_instrument_only: Literal[True] = True
    raw_first_provider_and_prompt_telemetry: Literal[True] = True
    provider_and_host_telemetry_separately_bound: Literal[True] = True
    pre_call_budget_certificate_required: Literal[True] = True
    typed_no_call_terminal_required: Literal[True] = True
    successful_usage_required: Literal[True] = True
    completed_trace_shared_scoring_required: Literal[True] = True
    core_terminal_frozen_before_sidecar: Literal[True] = True
    failure_namespaces_separated: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    historical_diagnostic_candidates_forbidden: Literal[True] = True
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=30)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=14, max_length=14
    )
    schema_version: str = V26_BUDGET_CLOSED_INSTRUMENT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BudgetClosedInstrumentContract:
        groups = (
            self.task_record_ids,
            self.task_package_ids,
            self.environment_manifest_ids,
            self.replay_binding_contract_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("budget-closed Contract identity sets are not canonical")
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("budget-closed Contract mechanism quotas changed")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("budget-closed Contract model identity changed")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != (self.fallback_models):
            raise ValueError("budget-closed Contract fallback policy changed")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("budget-closed Contract permits model mismatch")
        if self.model_invocation_config.get("maximum_model_attempts") != 1:
            raise ValueError("budget-closed Contract permits multiple model attempts")
        if self.model_invocation_config.get("max_output_tokens") != (
            self.provider_token_budget_contract.maximum_output_tokens
        ):
            raise ValueError("budget-closed model and budget output bounds differ")
        budget = self.provider_token_budget_contract
        if (
            budget.maximum_total_tokens != MAXIMUM_MODEL_TOKENS_PER_ROLLOUT
            or budget.maximum_prompt_utf8_bytes != MAXIMUM_PROMPT_UTF8_BYTES
            or budget.maximum_output_tokens != MAXIMUM_OUTPUT_TOKENS
            or budget.provider_chat_envelope_token_upper_bound
            != PROVIDER_CHAT_ENVELOPE_TOKEN_UPPER_BOUND
            or budget.contract_repair_reserve_tokens != CONTRACT_REPAIR_RESERVE_TOKENS
            or budget.final_answer_reserve_tokens != FINAL_ANSWER_RESERVE_TOKENS
        ):
            raise ValueError("budget-closed Provider resource policy changed")
        if self.maximum_total_estimated_cost_usd != MAXIMUM_ESTIMATED_COST_USD:
            raise ValueError("budget-closed aggregate cost ceiling changed")
        if self.model_config_hash != canonical_hash(
            self.model_invocation_config,
            prefix="finance_v26_budget_closed_model_config:",
        ):
            raise ValueError("budget-closed model config hash is invalid")
        if self.provider_route_hash != canonical_hash(
            self.provider_route,
            prefix="finance_v26_budget_closed_provider_route:",
        ):
            raise ValueError("budget-closed Provider route hash is invalid")
        if self.verifier_manifest_hash != canonical_hash(
            self.verifier_manifest,
            prefix="finance_v26_budget_closed_verifier_manifest:",
        ):
            raise ValueError("budget-closed Verifier manifest hash is invalid")
        if tuple(item.relative_path for item in self.implementation_source_files) != (
            IMPLEMENTATION_SOURCE_PATHS
        ):
            raise ValueError("budget-closed Contract implementation manifest is incomplete")
        if self.contract_id != budget_closed_instrument_contract_id(self):
            raise ValueError("budget-closed Instrument Contract identity is invalid")
        return self


class BudgetClosedInstrumentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    replay_binding_contract_id: str = Field(min_length=1)
    provider_token_budget_contract_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, lt=4)
    sampling_mode: Literal["instrument_unconditional"] = "instrument_unconditional"
    empirical_role: Literal["instrument_requalification"] = "instrument_requalification"
    schema_version: str = V26_BUDGET_CLOSED_INSTRUMENT_JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> BudgetClosedInstrumentJob:
        if self.job_id != budget_closed_instrument_job_id(self):
            raise ValueError("budget-closed Instrument Job identity is invalid")
        return self


class BudgetClosedInstrumentJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    jobs: tuple[BudgetClosedInstrumentJob, ...] = Field(min_length=32, max_length=32)
    schema_version: str = V26_BUDGET_CLOSED_INSTRUMENT_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> BudgetClosedInstrumentJobManifest:
        if any(item.contract_id != self.contract_id for item in self.jobs):
            raise ValueError("budget-closed Job Manifest crosses Contracts")
        identities = tuple(item.job_id for item in self.jobs)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("budget-closed Job identities are not canonical")
        task_counts = Counter(item.task_package_id for item in self.jobs)
        if len(task_counts) != INSTRUMENT_TASK_COUNT or set(task_counts.values()) != {
            INSTRUMENT_REPLICAS_PER_TASK
        }:
            raise ValueError("budget-closed Job task denominator changed")
        if self.manifest_id != budget_closed_instrument_manifest_id(self):
            raise ValueError("budget-closed Instrument Manifest identity is invalid")
        return self


class CompilerCompletedScoringAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    witness_id: str = Field(min_length=1)
    observation_count: int = Field(ge=1)
    replay_result_id: str = Field(min_length=1)
    frozen_trajectory_id: str = Field(min_length=1)
    reconstructed_trajectory_id: str = Field(min_length=1)
    frozen_score_id: str = Field(min_length=1)
    reconstructed_score_id: str = Field(min_length=1)
    replay_passed: Literal[True] = True
    trajectory_byte_semantics_reproduced: Literal[True] = True
    completed_scoring_reproduced: Literal[True] = True
    trace_sidecar_passed: Literal[True] = True
    failure_channels_empty: Literal[True] = True
    compiler_fixture_excluded_from_empirical_counts: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_CLOSED_COMPILER_SCORING_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CompilerCompletedScoringAudit:
        if self.frozen_trajectory_id != self.reconstructed_trajectory_id:
            raise ValueError("Compiler trajectory reconstruction changed identity")
        if self.frozen_score_id != self.reconstructed_score_id:
            raise ValueError("Compiler completed scoring changed identity")
        if self.audit_id != compiler_completed_scoring_audit_id(self):
            raise ValueError("Compiler completed-scoring audit identity is invalid")
        return self


class BudgetClosureMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_kind: BudgetMutationKind
    expected_behavior: Literal[
        "provider_call_allowed",
        "typed_no_call",
        "budget_contract_failed",
    ]
    observed_behavior: Literal[
        "provider_call_allowed",
        "typed_no_call",
        "budget_contract_failed",
    ]
    provider_call_count: int = Field(ge=0, le=1)
    no_call_reason: str | None = None
    budget_failure_ids: tuple[str, ...] = ()
    mutation_rejected: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = V26_BUDGET_CLOSED_BUDGET_MUTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetClosureMutationAudit:
        if self.expected_behavior != self.observed_behavior:
            raise ValueError("budget mutation produced another behavior")
        if self.observed_behavior == "provider_call_allowed" and self.provider_call_count != 1:
            raise ValueError("exact-boundary positive control made another call count")
        if self.observed_behavior == "typed_no_call" and (
            self.provider_call_count != 0 or self.no_call_reason is None
        ):
            raise ValueError("budget no-call mutation was not rejected before Provider")
        if self.observed_behavior == "budget_contract_failed" and (
            self.provider_call_count != 1 or not self.budget_failure_ids
        ):
            raise ValueError("budget Usage mutation did not fail after one Provider response")
        if self.audit_id != budget_closure_mutation_audit_id(self):
            raise ValueError("budget mutation audit identity is invalid")
        return self


class ScoringFailureChannelMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_kind: ScoringMutationKind
    baseline_core_terminal: Literal["valid_trajectory"] = "valid_trajectory"
    observed_core_terminal: Literal["valid_trajectory"] = "valid_trajectory"
    report_completeness_blocked: bool
    raw_lineage_passed: Literal[True] = True
    mutation_rejected: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = V26_BUDGET_CLOSED_SCORING_MUTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScoringFailureChannelMutationAudit:
        if self.mutation_kind == "legacy_observation_id_access":
            if not self.report_completeness_blocked:
                raise ValueError("sidecar mutation did not block report completeness")
        elif self.report_completeness_blocked:
            raise ValueError("schema mutation unexpectedly produced a report sidecar")
        if self.audit_id != scoring_failure_channel_mutation_audit_id(self):
            raise ValueError("scoring mutation audit identity is invalid")
        return self


class BudgetClosedInstrumentPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_source_report_id: str = Field(min_length=1)
    verifier_qualification_report_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    provider_token_budget_contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    task_count: Literal[8] = INSTRUMENT_TASK_COUNT
    mechanism_task_counts: dict[str, int]
    expected_job_count: Literal[32] = INSTRUMENT_JOB_COUNT
    fresh_job_count: Literal[32] = INSTRUMENT_JOB_COUNT
    source_file_replay_pass_count: int = Field(ge=50)
    task_binding_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    verifier_v2_binding_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_runtime_witness_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_witness_observation_count: int = Field(ge=64)
    compiler_replay_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_completed_scoring_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_trace_sidecar_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    compiler_empirical_row_count: Literal[0] = 0
    public_private_isolation_pass_count: Literal[8] = INSTRUMENT_TASK_COUNT
    destructive_replay_mutation_reject_count: Literal[24] = 24
    budget_mutation_case_count: Literal[7] = 7
    budget_mutation_pass_count: Literal[7] = 7
    scoring_mutation_case_count: Literal[3] = 3
    scoring_mutation_pass_count: Literal[3] = 3
    lineage_scoring_failure_namespace_separated: Literal[True] = True
    authority_terminal_mutation_reject_count: Literal[40] = 40
    legacy_operation_mutation_reject_count: int = Field(ge=64)
    historical_job_manifest_count: int = Field(ge=6)
    historical_job_identity_count: int = Field(ge=1)
    historical_job_identity_overlap_count: Literal[0] = 0
    raw_first_path_collision_count: Literal[0] = 0
    independent_byte_rebuild_required: Literal[True] = True
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=30)
    immutable_detail_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=9, max_length=9)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=14, max_length=14
    )
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "fresh_budget_closed_verifier_bound_instrument_requalification_only"
    ] = "fresh_budget_closed_verifier_bound_instrument_requalification_only"
    instrument_requalification_authorized: Literal[True] = True
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_BUDGET_CLOSED_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetClosedInstrumentPreflightReport:
        if self.mechanism_task_counts != {
            mechanism: INSTRUMENT_TASKS_PER_MECHANISM for mechanism in TARGET_MECHANISMS
        }:
            raise ValueError("budget-closed Preflight mechanism quotas changed")
        if tuple(item.relative_path for item in self.implementation_source_files) != (
            IMPLEMENTATION_SOURCE_PATHS
        ):
            raise ValueError("budget-closed Preflight implementation manifest is incomplete")
        expected_details = (
            "budget_closure_mutation_audits.json",
            "compiler_completed_scoring_audits.json",
            "compiler_replay_audits.json",
            "destructive_replay_mutation_audits.json",
            "execution_contract.json",
            "job_manifest.json",
            "public_private_isolation_audits.json",
            "scoring_failure_channel_mutation_audits.json",
            "source_replay_audit.json",
        )
        if tuple(item.relative_path for item in self.immutable_detail_files) != (expected_details):
            raise ValueError("budget-closed Preflight detail manifest is incomplete")
        if self.report_id != budget_closed_preflight_report_id(self):
            raise ValueError("budget-closed Preflight report identity is invalid")
        return self


class _FixtureBudgetClient:
    def __init__(
        self,
        *,
        maximum_output_tokens: int,
        prompt_tokens: int = 1,
        completion_tokens: int = 1,
        total_tokens: int | None = 2,
    ) -> None:
        self.calls: list[str] = []
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._total_tokens = total_tokens
        self._config = AgentModelConfig(
            provider="fixture",
            endpoint="https://fixture.invalid/v1/chat/completions",
            model="fixture-model",
            api_key_env="FIXTURE_API_KEY",
            max_output_tokens=maximum_output_tokens,
            maximum_model_attempts=1,
            fallback_models=(),
            require_requested_model=True,
        )

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.calls.append(prompt)
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return {"value": 1}, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            response_model="fixture-model",
            request_hash=request_hash,
            response_hash="response:fixture",
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=(self._prompt_tokens if self._total_tokens is not None else None),
            completion_tokens=(self._completion_tokens if self._total_tokens is not None else None),
            total_tokens=self._total_tokens,
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_sources(
    package_root: Path,
) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=path,
            sha256=_sha256(package_root / path),
        )
        for path in IMPLEMENTATION_SOURCE_PATHS
    )


def _validate_task_source_files(
    task_source_dir: Path,
    task_report: BudgetClosedInstrumentPopulationReport,
) -> None:
    for item in task_report.immutable_artifact_files:
        path = task_source_dir / item.relative_path
        if _sha256(path) != item.sha256:
            raise ValueError(f"budget-closed Task detail replay failed: {path}")


def _source_replay_audit(
    *,
    task_source_dir: Path,
    task_report: BudgetClosedInstrumentPopulationReport,
    verifier_qualification_dir: Path,
    qualification: AuthorityPreservingVerifierQualificationReport,
    historical_job_manifest_paths: Sequence[Path],
    package_root: Path,
) -> VerifierBoundSourceReplayAudit:
    entries: dict[str, SourceReplayEntry] = {}
    report_path = task_source_dir / "report.json"
    _register_replay_entry(
        entries,
        path=report_path,
        package_root=package_root,
        expected_sha256=_sha256(report_path),
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
    for relative_path in IMPLEMENTATION_SOURCE_PATHS:
        path = package_root / relative_path
        _register_replay_entry(
            entries,
            path=path,
            package_root=package_root,
            expected_sha256=_sha256(path),
            source_kind="task_implementation",
        )
    qualification_path = verifier_qualification_dir / "report.json"
    _register_replay_entry(
        entries,
        path=qualification_path,
        package_root=package_root,
        expected_sha256=_sha256(qualification_path),
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


def _contract_source_file(
    entry: SourceReplayEntry,
    *,
    task_source_dir: Path,
    package_root: Path,
) -> SourceArtifactFile:
    if entry.relative_path.startswith("external_task_source/"):
        path = task_source_dir / Path(entry.relative_path).name
    else:
        path = package_root / entry.relative_path
    source = SourceArtifactFile(
        relative_path=entry.relative_path,
        sha256=_sha256(path),
        record_count=_record_count(path),
    )
    if source.sha256 != entry.observed_sha256:
        raise ValueError("v26.83 Contract source binding disagrees with source replay")
    return source


def _build_contract(
    *,
    run_id: str,
    task_source_dir: Path,
    task_report: BudgetClosedInstrumentPopulationReport,
    qualification_dir: Path,
    qualification: AuthorityPreservingVerifierQualificationReport,
    replay_contract: AuthorityPreservingReplayContract,
    source_replay: VerifierBoundSourceReplayAudit,
    budget_contract: ProviderTokenBudgetContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    bindings: Sequence[VerifierV2TaskReplayBinding],
    package_root: Path,
) -> BudgetClosedInstrumentContract:
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
        "completed_trace_scorer": "schema_closed_shared_post_replay.v1",
        "failure_namespace_policy": "strictly_separated.v1",
    }
    source_files = tuple(
        _contract_source_file(
            item,
            task_source_dir=task_source_dir,
            package_root=package_root,
        )
        for item in source_replay.entries
        if item.source_kind != "task_implementation"
    )
    values = {
        "run_id": run_id,
        "task_source_report_id": task_report.report_id,
        "task_source_report_sha256": _sha256(task_source_dir / "report.json"),
        "verifier_qualification_report_id": qualification.report_id,
        "verifier_qualification_report_sha256": _sha256(qualification_dir / "report.json"),
        "qualified_replay_contract_id": replay_contract.contract_id,
        "source_replay_audit_id": source_replay.audit_id,
        "provider_token_budget_contract": budget_contract,
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
            prefix="finance_v26_budget_closed_model_config:",
        ),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route,
            prefix="finance_v26_budget_closed_provider_route:",
        ),
        "verifier_manifest": verifier_manifest,
        "verifier_manifest_hash": canonical_hash(
            verifier_manifest,
            prefix="finance_v26_budget_closed_verifier_manifest:",
        ),
        "maximum_total_estimated_cost_usd": MAXIMUM_ESTIMATED_COST_USD,
        "source_artifact_files": source_files,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = BudgetClosedInstrumentContract.model_construct(contract_id="pending", **values)
    return BudgetClosedInstrumentContract(
        contract_id=budget_closed_instrument_contract_id(provisional),
        **values,
    )


def _build_job_manifest(
    contract: BudgetClosedInstrumentContract,
    records: Sequence[OperationalTaskRecord],
    bindings: Sequence[VerifierV2TaskReplayBinding],
) -> BudgetClosedInstrumentJobManifest:
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
                "provider_token_budget_contract_id": (
                    contract.provider_token_budget_contract.contract_id
                ),
                "mechanism_id": record.mechanism_id,
                "replicate_index": replicate_index,
            }
            provisional = BudgetClosedInstrumentJob.model_construct(job_id="pending", **values)
            jobs.append(
                BudgetClosedInstrumentJob(
                    job_id=budget_closed_instrument_job_id(provisional),
                    **values,
                )
            )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    values = {"contract_id": contract.contract_id, "jobs": ordered}
    provisional = BudgetClosedInstrumentJobManifest.model_construct(manifest_id="pending", **values)
    return BudgetClosedInstrumentJobManifest(
        manifest_id=budget_closed_instrument_manifest_id(provisional),
        **values,
    )


def _compiler_completed_scoring_audits(
    *,
    replay_contract: AuthorityPreservingReplayContract,
    budget_contract: ProviderTokenBudgetContract,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    witnesses: Sequence[BoundPublicExecutableWitness],
    observations: Sequence[AgentToolObservation],
    frozen_trajectories: Sequence[Trajectory],
    frozen_scores: Sequence[CompletedTrajectoryScore],
    task_audits: Sequence[AuthorityPreservingTaskAudit],
) -> tuple[CompilerCompletedScoringAudit, ...]:
    environment_by_id = {item.manifest_id: item for item in environments}
    witness_by_task = {item.task_package_id: item for item in witnesses}
    observation_by_id = {item.observation_id: item for item in observations}
    trajectory_by_task = {item.task_id: item for item in frozen_trajectories}
    score_by_trajectory = {item.trajectory_id: item for item in frozen_scores}
    task_audit_by_package = {item.task_package_id: item for item in task_audits}
    output = []
    for record in records:
        package = record.task_package
        witness = witness_by_task[package.package_id]
        history = tuple(observation_by_id[item.observation_id] for item in witness.steps)
        environment = environment_by_id[record.environment_manifest_id]
        replay = replay_authority_preserving_observations(
            replay_contract,
            record,
            environment,
            history,
        )
        if not replay.passed:
            raise ValueError("v26.83 Compiler Replay failed")
        reconstructed_trajectory = compiler_witness_trajectory(
            record=record,
            environment=environment,
            witness=witness,
            observations=history,
        )
        frozen_trajectory = trajectory_by_task[record.task_package.task.public.task_id]
        if reconstructed_trajectory.model_dump(mode="json") != frozen_trajectory.model_dump(
            mode="json"
        ):
            raise ValueError("v26.83 Compiler trajectory bytes did not reproduce")
        task_audit = task_audit_by_package[package.package_id]
        reconstructed_score = score_completed_trajectory(
            trajectory=reconstructed_trajectory,
            source_kind="compiler_fixture",
            replay_result_id=replay.replay_id,
            replay_passed=replay.passed,
            non_replay_checks={
                "action_neutral_repair": task_audit.repair_prompt_audit.status == "passed",
                "answer_projection": witness.answer_projection_complete,
                "citation": witness.citation_complete,
                "evidence_support": witness.evidence_support_complete,
                "mechanism": witness.mechanism_complete,
                "no_postcompletion_violation": witness.no_postcompletion_violation,
                "operation_lineage": witness.operation_lineage_complete,
                "stop_readiness": task_audit.runtime_witness_stop_ready,
                "terminal_target": task_audit.exact_terminal_reference_accepted,
                "verification": witness.verification_complete,
            },
            independent_valid=witness.full_validity_passed,
            resource_budget_audit_id=budget_contract.contract_id,
            resource_budget_status="not_applicable_no_provider_calls",
        )
        frozen_score = score_by_trajectory[frozen_trajectory.trajectory_id]
        if reconstructed_score.model_dump(mode="json") != frozen_score.model_dump(mode="json"):
            raise ValueError("v26.83 Compiler completed score did not reproduce")
        if reconstructed_score.trace_sidecar is None:
            raise ValueError("v26.83 Compiler trace sidecar is absent")
        failures = reconstructed_score.failure_channels
        values = {
            "task_package_id": package.package_id,
            "witness_id": witness.witness_id,
            "observation_count": len(history),
            "replay_result_id": replay.replay_id,
            "frozen_trajectory_id": frozen_trajectory.trajectory_id,
            "reconstructed_trajectory_id": reconstructed_trajectory.trajectory_id,
            "frozen_score_id": frozen_score.score_id,
            "reconstructed_score_id": reconstructed_score.score_id,
            "failure_channels_empty": not any(
                (
                    failures.raw_lineage_failures,
                    failures.provider_capture_failures,
                    failures.runtime_replay_failures,
                    failures.scoring_core_failures,
                    failures.diagnostic_sidecar_failures,
                    failures.resource_failures,
                    failures.report_aggregation_failures,
                )
            ),
        }
        provisional = CompilerCompletedScoringAudit.model_construct(audit_id="pending", **values)
        output.append(
            CompilerCompletedScoringAudit(
                audit_id=compiler_completed_scoring_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _fixture_budget_contract(
    *,
    maximum_total_tokens: int,
    maximum_prompt_utf8_bytes: int = 10_000,
    repair_reserve: int = 3,
    final_reserve: int = 5,
) -> ProviderTokenBudgetContract:
    return make_provider_token_budget_contract(
        provider="fixture",
        model_id="fixture-model",
        maximum_total_tokens=maximum_total_tokens,
        maximum_prompt_utf8_bytes=maximum_prompt_utf8_bytes,
        maximum_output_tokens=4,
        provider_chat_envelope_token_upper_bound=2,
        contract_repair_reserve_tokens=repair_reserve,
        final_answer_reserve_tokens=final_reserve,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 6


def _budget_mutation_audits() -> tuple[BudgetClosureMutationAudit, ...]:
    plan = (
        "Return only one compact JSON object with exactly these keys: plan_summary, "
        "subgoal_labels, stop_conditions."
    )
    decision = "Return only one compact JSON object. Choose one next public action."
    final = "Return only one JSON object with exactly rationale_summary, answer, and citations."
    repair = "\nCONTRACT_REPAIR_JSON:\n{}"
    output = []

    def append(
        *,
        mutation_kind: BudgetMutationKind,
        expected_behavior: str,
        client: BudgetClosedJsonClient,
        provider: _FixtureBudgetClient,
        prompt: str,
    ) -> None:
        try:
            client.complete_json(prompt)
        except LLMClientError:
            pass
        audit = client.audit()
        if audit.no_call_terminal is not None:
            observed = "typed_no_call"
            no_call_reason = audit.no_call_terminal.reason_code
        elif audit.status == "failed":
            observed = "budget_contract_failed"
            no_call_reason = None
        else:
            observed = "provider_call_allowed"
            no_call_reason = None
        values = {
            "mutation_kind": mutation_kind,
            "expected_behavior": expected_behavior,
            "observed_behavior": observed,
            "provider_call_count": len(provider.calls),
            "no_call_reason": no_call_reason,
            "budget_failure_ids": audit.contract_failure_ids,
        }
        provisional = BudgetClosureMutationAudit.model_construct(audit_id="pending", **values)
        output.append(
            BudgetClosureMutationAudit(
                audit_id=budget_closure_mutation_audit_id(provisional),
                **values,
            )
        )

    exact_prompt = final + repair
    exact_provider = _FixtureBudgetClient(maximum_output_tokens=4)
    append(
        mutation_kind="exact_boundary",
        expected_behavior="provider_call_allowed",
        client=BudgetClosedJsonClient(
            exact_provider,
            _fixture_budget_contract(
                maximum_total_tokens=_request_bound(exact_prompt),
                repair_reserve=0,
                final_reserve=0,
            ),
        ),
        provider=exact_provider,
        prompt=exact_prompt,
    )
    over_provider = _FixtureBudgetClient(maximum_output_tokens=4)
    append(
        mutation_kind="one_token_over",
        expected_behavior="typed_no_call",
        client=BudgetClosedJsonClient(
            over_provider,
            _fixture_budget_contract(
                maximum_total_tokens=_request_bound(exact_prompt) - 1,
                repair_reserve=0,
                final_reserve=0,
            ),
        ),
        provider=over_provider,
        prompt=exact_prompt,
    )
    changed_provider = _FixtureBudgetClient(
        maximum_output_tokens=4,
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=3,
    )
    append(
        mutation_kind="changed_usage",
        expected_behavior="budget_contract_failed",
        client=BudgetClosedJsonClient(
            changed_provider,
            _fixture_budget_contract(maximum_total_tokens=1_000),
        ),
        provider=changed_provider,
        prompt=plan,
    )
    missing_provider = _FixtureBudgetClient(
        maximum_output_tokens=4,
        total_tokens=None,
    )
    append(
        mutation_kind="missing_usage",
        expected_behavior="budget_contract_failed",
        client=BudgetClosedJsonClient(
            missing_provider,
            _fixture_budget_contract(maximum_total_tokens=1_000),
        ),
        provider=missing_provider,
        prompt=plan,
    )
    oversized_provider = _FixtureBudgetClient(maximum_output_tokens=4)
    append(
        mutation_kind="oversized_prompt",
        expected_behavior="typed_no_call",
        client=BudgetClosedJsonClient(
            oversized_provider,
            _fixture_budget_contract(
                maximum_total_tokens=1_000,
                maximum_prompt_utf8_bytes=3,
            ),
        ),
        provider=oversized_provider,
        prompt=plan,
    )
    final_reserve_provider = _FixtureBudgetClient(maximum_output_tokens=4)
    append(
        mutation_kind="final_answer_reserve_insufficient",
        expected_behavior="typed_no_call",
        client=BudgetClosedJsonClient(
            final_reserve_provider,
            _fixture_budget_contract(
                maximum_total_tokens=_request_bound(decision) + 3 + 5 - 1,
            ),
        ),
        provider=final_reserve_provider,
        prompt=decision,
    )
    repair_reserve_provider = _FixtureBudgetClient(maximum_output_tokens=4)
    append(
        mutation_kind="contract_repair_reserve_insufficient",
        expected_behavior="typed_no_call",
        client=BudgetClosedJsonClient(
            repair_reserve_provider,
            _fixture_budget_contract(
                maximum_total_tokens=_request_bound(final) + 3 - 1,
            ),
        ),
        provider=repair_reserve_provider,
        prompt=final,
    )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _scoring_mutation_audits(
    trajectory: Trajectory,
) -> tuple[ScoringFailureChannelMutationAudit, ...]:
    output = []

    def fail_sidecar(_: Trajectory) -> SchemaClosedTraceSidecar:
        raise AttributeError("TrajectoryStep has no observation_id")

    sidecar_failure = score_completed_trajectory(
        trajectory=trajectory,
        source_kind="model_generated",
        replay_result_id="preflight_mutation_replay:passed",
        replay_passed=True,
        non_replay_checks={"all_non_replay_gates": True},
        independent_valid=True,
        resource_budget_audit_id="preflight_mutation_budget:passed",
        resource_budget_status="passed",
        sidecar_builder=fail_sidecar,
    )
    if (
        sidecar_failure.core_terminal != "valid_trajectory"
        or sidecar_failure.failure_channels.report_complete
        or sidecar_failure.instrument_admitted
        or sidecar_failure.failure_channels.raw_lineage_failures
    ):
        raise ValueError("legacy sidecar failure reclassified the core terminal")
    mutation_values = {
        "mutation_kind": "legacy_observation_id_access",
        "observed_core_terminal": sidecar_failure.core_terminal,
        "report_completeness_blocked": True,
    }
    provisional = ScoringFailureChannelMutationAudit.model_construct(
        audit_id="pending", **mutation_values
    )
    output.append(
        ScoringFailureChannelMutationAudit(
            audit_id=scoring_failure_channel_mutation_audit_id(provisional),
            **mutation_values,
        )
    )

    baseline = score_completed_trajectory(
        trajectory=trajectory,
        source_kind="model_generated",
        replay_result_id="preflight_mutation_replay:passed",
        replay_passed=True,
        non_replay_checks={"all_non_replay_gates": True},
        independent_valid=True,
        resource_budget_audit_id="preflight_mutation_budget:passed",
        resource_budget_status="passed",
    )
    if baseline.trace_sidecar is None:
        raise ValueError("scoring mutation baseline lacks its sidecar")
    schema_payload = baseline.trace_sidecar.model_dump(mode="json")
    schema_payload["trajectory_step_schema_fields"][-1] = "observation_id"
    schema_payload["sidecar_id"] = "finance_v26_schema_closed_trace_sidecar:tampered"
    try:
        SchemaClosedTraceSidecar.model_validate(schema_payload)
    except ValidationError:
        pass
    else:
        raise ValueError("TrajectoryStep schema mutation did not fail closed")
    schema_values = {
        "mutation_kind": "trajectory_step_schema_change",
        "observed_core_terminal": baseline.core_terminal,
        "report_completeness_blocked": False,
    }
    provisional = ScoringFailureChannelMutationAudit.model_construct(
        audit_id="pending", **schema_values
    )
    output.append(
        ScoringFailureChannelMutationAudit(
            audit_id=scoring_failure_channel_mutation_audit_id(provisional),
            **schema_values,
        )
    )

    channels = build_instrument_failure_channels(scoring_core_failures=("scoring_core:fixture",))
    channel_payload = channels.model_dump(mode="json")
    channel_payload["raw_lineage_failures"] = ["scoring_core:fixture"]
    channel_payload["channel_id"] = "finance_v26_budget_closed_failure_channels:tampered"
    try:
        InstrumentFailureChannels.model_validate(channel_payload)
    except ValidationError:
        pass
    else:
        raise ValueError("failure namespace contamination did not fail closed")
    namespace_values = {
        "mutation_kind": "failure_namespace_cross_contamination",
        "observed_core_terminal": baseline.core_terminal,
        "report_completeness_blocked": False,
    }
    provisional = ScoringFailureChannelMutationAudit.model_construct(
        audit_id="pending", **namespace_values
    )
    output.append(
        ScoringFailureChannelMutationAudit(
            audit_id=scoring_failure_channel_mutation_audit_id(provisional),
            **namespace_values,
        )
    )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _historical_job_ids(paths: Sequence[Path]) -> set[str]:
    output: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key in {"job_id", "recovery_job_id"} and isinstance(item, str):
                    output.add(item)
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("jobs"), list):
            raise ValueError(f"historical Job Manifest is malformed: {path}")
        collect(payload["jobs"])
    return output


def build_budget_closed_instrument_preflight(
    *,
    run_id: str,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    historical_job_manifest_paths: Sequence[Path],
    output_dir: Path,
    package_root: Path,
) -> BudgetClosedInstrumentPreflightReport:
    task_report = BudgetClosedInstrumentPopulationReport.model_validate_json(
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
    ):
        raise ValueError("v26.83 source and qualified Verifier v2 disagree")
    _validate_task_source_files(task_source_dir, task_report)
    records = _load_rows(
        task_source_dir / "operational_task_records.json",
        OperationalTaskRecord,
    )
    environments = _load_rows(
        task_source_dir / "tool_environment_manifests.json",
        AgentToolEnvironmentManifest,
    )
    bindings = _load_rows(
        task_source_dir / "verifier_v2_replay_bindings.json",
        VerifierV2TaskReplayBinding,
    )
    witnesses = _load_rows(
        task_source_dir / "operational_public_witnesses.json",
        BoundPublicExecutableWitness,
    )
    observations = _load_rows(
        task_source_dir / "operational_witness_observations.json",
        AgentToolObservation,
    )
    task_audits = _load_rows(
        task_source_dir / "authority_preserving_task_audits.json",
        AuthorityPreservingTaskAudit,
    )
    frozen_trajectories = _load_rows(
        task_source_dir / "compiler_trajectories.json",
        Trajectory,
    )
    frozen_scores = _load_rows(
        task_source_dir / "completed_compiler_trajectory_scores.json",
        CompletedTrajectoryScore,
    )
    budget_contract = ProviderTokenBudgetContract.model_validate_json(
        (task_source_dir / "provider_token_budget_contract.json").read_text(encoding="utf-8")
    )
    if budget_contract.contract_id != task_report.provider_token_budget_contract_id:
        raise ValueError("v26.83 Task source lost its Provider budget Contract")

    source_replay = _source_replay_audit(
        task_source_dir=task_source_dir,
        task_report=task_report,
        verifier_qualification_dir=verifier_qualification_dir,
        qualification=qualification,
        historical_job_manifest_paths=historical_job_manifest_paths,
        package_root=package_root,
    )
    _validate_task_bindings(records, environments, bindings, task_audits)
    compiler_replays = _compiler_replay_audits(
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        bindings=bindings,
        witnesses=witnesses,
        observations=observations,
    )
    compiler_scoring = _compiler_completed_scoring_audits(
        replay_contract=replay_contract,
        budget_contract=budget_contract,
        records=records,
        environments=environments,
        witnesses=witnesses,
        observations=observations,
        frozen_trajectories=frozen_trajectories,
        frozen_scores=frozen_scores,
        task_audits=task_audits,
    )
    isolation = _isolation_audits(records, bindings)
    replay_mutations = _mutation_audits(
        replay_contract=replay_contract,
        records=records,
        environments=environments,
        witnesses=witnesses,
        observations=observations,
    )
    budget_mutations = _budget_mutation_audits()
    scoring_mutations = _scoring_mutation_audits(frozen_trajectories[0])

    contract = _build_contract(
        run_id=run_id,
        task_source_dir=task_source_dir,
        task_report=task_report,
        qualification_dir=verifier_qualification_dir,
        qualification=qualification,
        replay_contract=replay_contract,
        source_replay=source_replay,
        budget_contract=budget_contract,
        records=records,
        environments=environments,
        bindings=bindings,
        package_root=package_root,
    )
    manifest = _build_job_manifest(contract, records, bindings)
    historical_ids = _historical_job_ids(historical_job_manifest_paths)
    overlap = historical_ids & {item.job_id for item in manifest.jobs}
    if overlap:
        raise ValueError("v26.83 Job identities overlap historical Manifests")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "budget": output_dir / "budget_closure_mutation_audits.json",
        "scoring": output_dir / "compiler_completed_scoring_audits.json",
        "compiler": output_dir / "compiler_replay_audits.json",
        "replay_mutations": output_dir / "destructive_replay_mutation_audits.json",
        "contract": output_dir / "execution_contract.json",
        "manifest": output_dir / "job_manifest.json",
        "isolation": output_dir / "public_private_isolation_audits.json",
        "scoring_mutations": output_dir / "scoring_failure_channel_mutation_audits.json",
        "source_replay": output_dir / "source_replay_audit.json",
    }
    _write_models(paths["budget"], budget_mutations, "audit_id")
    _write_models(paths["scoring"], compiler_scoring, "audit_id")
    _write_models(paths["compiler"], compiler_replays, "audit_id")
    _write_models(paths["replay_mutations"], replay_mutations, "audit_id")
    _write_json(paths["contract"], contract.model_dump(mode="json"))
    _write_json(paths["manifest"], manifest.model_dump(mode="json"))
    _write_models(paths["isolation"], isolation, "audit_id")
    _write_models(paths["scoring_mutations"], scoring_mutations, "audit_id")
    _write_json(paths["source_replay"], source_replay.model_dump(mode="json"))
    counts = {
        "budget": len(budget_mutations),
        "scoring": len(compiler_scoring),
        "compiler": len(compiler_replays),
        "replay_mutations": len(replay_mutations),
        "contract": 1,
        "manifest": 1,
        "isolation": len(isolation),
        "scoring_mutations": len(scoring_mutations),
        "source_replay": 1,
    }
    immutable_files = tuple(
        sorted(
            (_detail_file(path, output_dir, counts[key]) for key, path in paths.items()),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "run_id": run_id,
        "task_source_report_id": task_report.report_id,
        "verifier_qualification_report_id": qualification.report_id,
        "source_replay_audit_id": source_replay.audit_id,
        "contract_id": contract.contract_id,
        "provider_token_budget_contract_id": budget_contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "mechanism_task_counts": task_report.mechanism_task_counts,
        "source_file_replay_pass_count": source_replay.replay_pass_count,
        "compiler_witness_observation_count": len(observations),
        "historical_job_manifest_count": len(historical_job_manifest_paths),
        "historical_job_identity_count": len(historical_ids),
        "legacy_operation_mutation_reject_count": (task_report.legacy_operation_mutation_count),
        "source_artifact_files": contract.source_artifact_files,
        "immutable_detail_files": immutable_files,
        "implementation_source_files": contract.implementation_source_files,
    }
    provisional = BudgetClosedInstrumentPreflightReport.model_construct(
        report_id="pending", **values
    )
    report = BudgetClosedInstrumentPreflightReport(
        report_id=budget_closed_preflight_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_closed_instrument_contract_id(
    value: BudgetClosedInstrumentContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_budget_closed_instrument_contract:",
    )


def budget_closed_instrument_job_id(value: BudgetClosedInstrumentJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"job_id"}),
        prefix="finance_v26_budget_closed_instrument_job:",
    )


def budget_closed_instrument_manifest_id(
    value: BudgetClosedInstrumentJobManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_budget_closed_instrument_manifest:",
    )


def compiler_completed_scoring_audit_id(
    value: CompilerCompletedScoringAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_compiler_scoring_audit:",
    )


def budget_closure_mutation_audit_id(
    value: BudgetClosureMutationAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_budget_mutation:",
    )


def scoring_failure_channel_mutation_audit_id(
    value: ScoringFailureChannelMutationAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_closed_scoring_mutation:",
    )


def budget_closed_preflight_report_id(
    value: BudgetClosedInstrumentPreflightReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_closed_instrument_preflight:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Finance v26.83 budget-closed Instrument preflight"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument(
        "--historical-job-manifest",
        action="append",
        type=Path,
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    report = build_budget_closed_instrument_preflight(
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
