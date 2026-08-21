from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_bound_redesign_preflight import (  # noqa: E501
    CompletionBoundContract,
    CompletionBoundManifest,
    CompletionBoundPathAudit,
    CompletionBoundPreflightReport,
    CompletionBoundSourceReplayAudit,
    CompletionBoundTaskPackage,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_thinking import (
    ProspectiveThinkingModelBinding,
    bind_prospective_thinking,
    require_prospective_thinking,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    ProspectiveThinkingCompletionBoundProtocol,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822"
NEXT_PERMITTED_STAGE: Final = (
    "fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only"
)

EXPECTED_V26_97_REPORT_ID: Final = (
    "finance_v26_completion_bound_preflight_report:"
    "09cfd5171d2cd29dd36ab51d5124900f513cbaac3a9fcd0f96aa0fdcb66d7486"
)
EXPECTED_V26_97_REPORT_SHA256: Final = (
    "b9c4407710ce3e3f886c2273a51e80405aef6da3a0f3277e891de233d36a8b24"
)
EXPECTED_V26_97_CONTRACT_ID: Final = (
    "finance_v26_completion_bound_contract:"
    "cf71fa07ae0be111c1e2843b14c1a8f6f3903371a365396da2c749217401ada4"
)
EXPECTED_V26_97_MANIFEST_ID: Final = (
    "finance_v26_completion_bound_manifest:"
    "11b3bb1f686f52f6c673f5e59b30757104d1769aaec0bae51eba4c4f25dbbdae"
)
EXPECTED_PROTOCOL_ID: Final = (
    "prospective_thinking_completion_bound_protocol:"
    "178f682e29a7f8bb19ec7e5bba87b68ea2777ea37539fab007ead74456995b50"
)
EXPECTED_INITIAL_CANDIDATE_ID: Final = (
    "prospective_completion_bound_candidate:"
    "f62cca7bf763864c8c1be10138afa68999b434a6110f16b711a5abedae6ae838"
)
EXPECTED_FALLBACK_CANDIDATE_ID: Final = (
    "prospective_completion_bound_candidate:"
    "6dfb2358d92a7b1e39a8cf741033e43974dad1a77114d01533ef673115a59dc2"
)
EXPECTED_FROZEN_MODEL_CONFIG_ID: Final = (
    "agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1"
)
EXPECTED_FROZEN_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d"
)
EXPECTED_DERIVED_8K_MODEL_CONFIG_ID: Final = (
    "agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e"
)
EXPECTED_DERIVED_8K_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57"
)

V26_97_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822"
)
MODEL_PROFILE_PATH = "config/deepseek_v4_flash_agent_thinking_v1.json"
IMPLEMENTATION_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_execution_binding_preflight.py"
)

SOURCE_REPLAY_VERSION: Final[Literal["finance_v26_8k_execution_binding_source_replay.v1"]] = (
    "finance_v26_8k_execution_binding_source_replay.v1"
)
PROFILE_AUDIT_VERSION: Final[Literal["finance_v26_8k_execution_profile_binding_audit.v1"]] = (
    "finance_v26_8k_execution_profile_binding_audit.v1"
)
JOB_AUDIT_VERSION: Final[Literal["finance_v26_8k_job_execution_binding_audit.v1"]] = (
    "finance_v26_8k_job_execution_binding_audit.v1"
)
ROOT_CAUSE_VERSION: Final[Literal["finance_v26_8k_execution_binding_root_cause.v1"]] = (
    "finance_v26_8k_execution_binding_root_cause.v1"
)
TRANSITION_VERSION: Final[Literal["finance_v26_8k_execution_binding_transition.v1"]] = (
    "finance_v26_8k_execution_binding_transition.v1"
)
DESTRUCTIVE_VERSION: Final[Literal["finance_v26_8k_execution_binding_destructive.v1"]] = (
    "finance_v26_8k_execution_binding_destructive.v1"
)
REPORT_VERSION: Final[Literal["finance_v26_8k_execution_binding_preflight_report.v1"]] = (
    "finance_v26_8k_execution_binding_preflight_report.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_97_transitive_source",
        "v26_97_output",
        "v26_98_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.98 source replay changed")
        return self


class ExecutionBindingSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_97_REPORT_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=746, max_length=746)
    transitive_source_file_count: Literal[733] = 733
    predecessor_output_file_count: Literal[12] = 12
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[746] = 746
    replay_pass_count: Literal[746] = 746
    replay_before_profile_audit: Literal[True] = True
    model_client_constructed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_8k_execution_binding_source_replay.v1"] = (
        SOURCE_REPLAY_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionBindingSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != self.replayed_file_count:
            raise ValueError("v26.98 replay paths are not a unique canonical denominator")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("v26.98 source replay identity mismatch")
        return self


class TaskPackageExecutionBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    selected_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    required_completion_upper_bound_tokens: Literal[8192] = 8192
    bound_model_config_id: str = EXPECTED_FROZEN_MODEL_CONFIG_ID
    bound_thinking_binding_id: str = EXPECTED_FROZEN_THINKING_BINDING_ID
    bound_model_config_max_output_tokens: Literal[4096] = 4096
    bound_profile_matches_task_package: Literal[True] = True
    bound_profile_matches_selected_candidate: Literal[False] = False
    derived_8k_model_config_id: str = EXPECTED_DERIVED_8K_MODEL_CONFIG_ID
    derived_8k_thinking_binding_id: str = EXPECTED_DERIVED_8K_THINKING_BINDING_ID
    derived_8k_profile_matches_selected_candidate: Literal[True] = True
    derived_8k_config_matches_task_package_binding: Literal[False] = False
    derived_8k_thinking_matches_task_package_binding: Literal[False] = False
    exact_execution_binding_closed: Literal[False] = False
    schema_version: Literal["finance_v26_8k_taskpackage_execution_binding.v1"] = (
        "finance_v26_8k_taskpackage_execution_binding.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> TaskPackageExecutionBindingRow:
        if self.bound_model_config_id == self.derived_8k_model_config_id:
            raise ValueError("4K and 8K model config identities unexpectedly coincide")
        if self.bound_thinking_binding_id == self.derived_8k_thinking_binding_id:
            raise ValueError("4K and 8K Thinking binding identities unexpectedly coincide")
        if self.row_id != task_package_binding_row_id(self):
            raise ValueError("TaskPackage execution-binding row identity mismatch")
        return self


class ExecutionProfileBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_97_REPORT_ID
    protocol_id: str = EXPECTED_PROTOCOL_ID
    selected_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    task_package_rows: tuple[TaskPackageExecutionBindingRow, ...] = Field(
        min_length=24,
        max_length=24,
    )
    task_package_count: Literal[24] = 24
    task_package_bound_to_4096_config_count: Literal[24] = 24
    task_package_bound_to_8192_config_count: Literal[0] = 0
    exact_8k_task_package_binding_count: Literal[0] = 0
    frozen_profile_path: str = MODEL_PROFILE_PATH
    frozen_profile_provider: Literal["deepseek"] = "deepseek"
    frozen_profile_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    frozen_profile_thinking_type: Literal["enabled"] = "enabled"
    frozen_profile_max_output_tokens: Literal[4096] = 4096
    frozen_model_config_id: str = EXPECTED_FROZEN_MODEL_CONFIG_ID
    frozen_thinking_binding_id: str = EXPECTED_FROZEN_THINKING_BINDING_ID
    derived_8k_profile_materialized: Literal[False] = False
    derived_8k_profile_max_output_tokens: Literal[8192] = 8192
    derived_8k_model_config_id: str = EXPECTED_DERIVED_8K_MODEL_CONFIG_ID
    derived_8k_thinking_binding_id: str = EXPECTED_DERIVED_8K_THINKING_BINDING_ID
    model_config_identity_changes_with_completion_bound: Literal[True] = True
    thinking_binding_identity_changes_with_model_config: Literal[True] = True
    exact_execution_profile_binding_passed: Literal[False] = False
    schema_version: Literal["finance_v26_8k_execution_profile_binding_audit.v1"] = (
        PROFILE_AUDIT_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionProfileBindingAudit:
        if len({item.task_package_id for item in self.task_package_rows}) != 24:
            raise ValueError("v26.98 TaskPackage binding rows are not unique")
        if any(item.exact_execution_binding_closed for item in self.task_package_rows):
            raise ValueError("v26.98 unexpectedly found an executable TaskPackage")
        if self.audit_id != profile_binding_audit_id(self):
            raise ValueError("v26.98 profile-binding audit identity mismatch")
        return self


class JobExecutionBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    manifest_index: int = Field(ge=0, lt=32)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    job_completion_upper_bound_tokens: Literal[8192] = 8192
    job_rollout_upper_bound_tokens: Literal[160000] = 160000
    task_package_model_config_max_output_tokens: Literal[4096] = 4096
    completion_bound_difference_tokens: Literal[4096] = 4096
    exact_model_config_id_required_but_unbound: str = EXPECTED_DERIVED_8K_MODEL_CONFIG_ID
    exact_thinking_binding_id_required_but_unbound: str = EXPECTED_DERIVED_8K_THINKING_BINDING_ID
    exact_execution_binding_closed: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_8k_job_execution_binding.v1"] = (
        "finance_v26_8k_job_execution_binding.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> JobExecutionBindingRow:
        if (
            self.job_completion_upper_bound_tokens
            - self.task_package_model_config_max_output_tokens
            != 4096
        ):
            raise ValueError("v26.98 Job/Profile Completion difference changed")
        if self.row_id != job_binding_row_id(self):
            raise ValueError("Job execution-binding row identity mismatch")
        return self


class JobExecutionBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = EXPECTED_V26_97_MANIFEST_ID
    rows: tuple[JobExecutionBindingRow, ...] = Field(min_length=32, max_length=32)
    manifest_job_count: Literal[32] = 32
    job_requiring_8192_completion_count: Literal[32] = 32
    job_with_exact_8192_task_package_profile_count: Literal[0] = 0
    job_with_profile_binding_mismatch_count: Literal[32] = 32
    job_authorized_for_provider_call_count: Literal[0] = 0
    fallback_16k_job_count: Literal[0] = 0
    historical_job_rerun_count: Literal[0] = 0
    schema_version: Literal["finance_v26_8k_job_execution_binding_audit.v1"] = JOB_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> JobExecutionBindingAudit:
        if tuple(item.manifest_index for item in self.rows) != tuple(range(32)):
            raise ValueError("v26.98 Job binding rows changed Manifest order")
        if len({item.job_id for item in self.rows}) != 32:
            raise ValueError("v26.98 Job binding rows are not unique")
        if self.audit_id != job_binding_audit_id(self):
            raise ValueError("v26.98 Job binding audit identity mismatch")
        return self


class ExecutionBindingRootCauseAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    profile_binding_audit_id: str = Field(min_length=1)
    job_binding_audit_id: str = Field(min_length=1)
    frozen_task_package_model_config_tokens: Literal[4096] = 4096
    selected_candidate_completion_tokens: Literal[8192] = 8192
    completion_difference_tokens: Literal[4096] = 4096
    candidate_field_can_override_agent_model_config_identity: Literal[False] = False
    request_max_tokens_override_without_new_config_allowed: Literal[False] = False
    exact_v26_97_manifest_runner_constructible: Literal[False] = False
    runner_implementation_materialized: Literal[False] = False
    execution_preflight_passed: Literal[False] = False
    v26_97_static_candidate_and_path_claims_retained: Literal[True] = True
    v26_97_historical_artifacts_mutated: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    root_cause: Literal["completion_candidate_not_bound_to_taskpackage_model_config"] = (
        "completion_candidate_not_bound_to_taskpackage_model_config"
    )
    schema_version: Literal["finance_v26_8k_execution_binding_root_cause.v1"] = ROOT_CAUSE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionBindingRootCauseAudit:
        if self.audit_id != root_cause_audit_id(self):
            raise ValueError("v26.98 root-cause identity mismatch")
        return self


class ProspectiveExecutionRebindingContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_97_REPORT_ID
    root_cause_audit_id: str = Field(min_length=1)
    frozen_protocol_id: str = EXPECTED_PROTOCOL_ID
    frozen_initial_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    frozen_fallback_candidate_id: str = EXPECTED_FALLBACK_CANDIDATE_ID
    fresh_8k_model_profile_required: Literal[True] = True
    fresh_thinking_binding_required: Literal[True] = True
    fresh_task_package_identity_count_required: Literal[24] = 24
    fresh_path_audit_identity_count_required: Literal[48] = 48
    fresh_contract_required: Literal[True] = True
    fresh_manifest_required: Literal[True] = True
    fresh_job_identity_count_required: Literal[32] = 32
    preserved_fresh_seed_count_required: Literal[32] = 32
    fresh_future_execution_identity_required: Literal[True] = True
    fresh_report_identity_required: Literal[True] = True
    source_task_selection_change_allowed: Literal[False] = False
    path_selection_change_allowed: Literal[False] = False
    job_assignment_change_allowed: Literal[False] = False
    seed_value_change_allowed: Literal[False] = False
    mechanism_path_cell_layout_change_allowed: Literal[False] = False
    completion_candidate_change_allowed: Literal[False] = False
    rollout_ceiling_change_allowed: Literal[False] = False
    rescue_renderer_change_allowed: Literal[False] = False
    rescue_absolute_ceiling_change_allowed: Literal[False] = False
    response_telemetry_contract_change_allowed: Literal[False] = False
    semantic_outcomes_used_for_rebinding: Literal[False] = False
    old_task_package_identity_reuse_allowed: Literal[False] = False
    old_path_audit_identity_reuse_allowed: Literal[False] = False
    old_contract_manifest_or_job_identity_reuse_allowed: Literal[False] = False
    runner_materialization_before_rebinding_pass_allowed: Literal[False] = False
    provider_calls_allowed: Literal[False] = False
    fallback_16k_jobs_allowed: Literal[False] = False
    capability_or_reachability_evidence_allowed: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal[
        "fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only"
    ] = NEXT_PERMITTED_STAGE
    schema_version: Literal["finance_v26_8k_execution_binding_transition.v1"] = TRANSITION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveExecutionRebindingContract:
        if self.next_permitted_stage != NEXT_PERMITTED_STAGE:
            raise ValueError("v26.98 transition changed")
        if self.contract_id != transition_contract_id(self):
            raise ValueError("v26.98 transition Contract identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mutation(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("v26.98 mutation identity mismatch")
        return self


class ExecutionBindingDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    rejected_mutation_count: Literal[12] = 12
    model_client_constructed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_8k_execution_binding_destructive.v1"] = DESTRUCTIVE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionBindingDestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))) or not all(
            item.rejected for item in self.mutation_results
        ):
            raise ValueError("v26.98 destructive controls changed")
        if self.audit_id != destructive_audit_id(self):
            raise ValueError("v26.98 destructive identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ExecutionBindingPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_V26_97_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    profile_binding_audit_id: str = Field(min_length=1)
    job_binding_audit_id: str = Field(min_length=1)
    root_cause_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=6, max_length=6)
    source_file_count: Literal[746] = 746
    task_package_count: Literal[24] = 24
    job_count: Literal[32] = 32
    exact_8k_task_package_binding_count: Literal[0] = 0
    blocked_job_count: Literal[32] = 32
    runner_implementation_materialized: Literal[False] = False
    execution_contract_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    model_client_constructed: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["blocked_preflight"] = "blocked_preflight"
    failure_type: Literal["execution_profile_binding_failure"] = "execution_profile_binding_failure"
    next_permitted_stage: Literal[
        "fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only"
    ] = NEXT_PERMITTED_STAGE
    role_protocol_frozen: Literal[False] = False
    capability_development_authorized: Literal[False] = False
    state_reachability_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_8k_execution_binding_preflight_report.v1"] = REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ExecutionBindingPreflightReport:
        if self.run_id != RUN_ID or self.next_permitted_stage != NEXT_PERMITTED_STAGE:
            raise ValueError("v26.98 report transition changed")
        if self.report_id != preflight_report_id(self):
            raise ValueError("v26.98 report identity mismatch")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def source_replay_audit_id(value: ExecutionBindingSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_8k_execution_binding_source_replay:")


def task_package_binding_row_id(value: TaskPackageExecutionBindingRow) -> str:
    return _identity(value, "row_id", "finance_v26_8k_taskpackage_execution_binding:")


def profile_binding_audit_id(value: ExecutionProfileBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_8k_execution_profile_binding_audit:")


def job_binding_row_id(value: JobExecutionBindingRow) -> str:
    return _identity(value, "row_id", "finance_v26_8k_job_execution_binding:")


def job_binding_audit_id(value: JobExecutionBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_8k_job_execution_binding_audit:")


def root_cause_audit_id(value: ExecutionBindingRootCauseAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_8k_execution_binding_root_cause:")


def transition_contract_id(value: ProspectiveExecutionRebindingContract) -> str:
    return _identity(value, "contract_id", "finance_v26_8k_execution_binding_transition:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_8k_execution_binding_mutation:")


def destructive_audit_id(value: ExecutionBindingDestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_8k_execution_binding_destructive:")


def preflight_report_id(value: ExecutionBindingPreflightReport) -> str:
    return _identity(value, "report_id", "finance_v26_8k_execution_binding_preflight_report:")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"noncanonical v26.98 source JSON: {path}")
    return payload


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.98 output changed: {path}")
    path.write_bytes(raw)


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected list source at {path}")
    return tuple(model.model_validate(item) for item in payload)


def _source_entry(
    *,
    path: Path,
    package_root: Path,
    source_kind: Literal[
        "v26_97_transitive_source",
        "v26_97_output",
        "v26_98_implementation",
    ],
    expected_sha256: str,
    relative_path: str | None = None,
) -> SourceReplayEntry:
    return SourceReplayEntry(
        relative_path=relative_path or _relative(path, package_root),
        source_kind=source_kind,
        expected_sha256=expected_sha256,
        observed_sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _load_predecessor(
    package_root: Path,
) -> tuple[CompletionBoundPreflightReport, CompletionBoundSourceReplayAudit]:
    directory = package_root / V26_97_DIR
    report = CompletionBoundPreflightReport.model_validate_json(
        (directory / "report.json").read_text(encoding="utf-8")
    )
    replay = CompletionBoundSourceReplayAudit.model_validate_json(
        (directory / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_V26_97_REPORT_ID
        or report.next_permitted_stage
        != "thinking_8k_completion_calibration_runner_and_preflight_only"
        or report.execution_runner_materialized
        or report.execution_authorized
        or replay.replayed_file_count != 733
    ):
        raise ValueError("v26.98 predecessor authorization changed")
    return report, replay


def _build_source_replay(package_root: Path) -> ExecutionBindingSourceReplayAudit:
    report, predecessor = _load_predecessor(package_root)
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            package_root=package_root,
            source_kind="v26_97_transitive_source",
            expected_sha256=item.expected_sha256,
        )
        for item in predecessor.entries
    ]
    predecessor_files = sorted(
        path for path in (package_root / V26_97_DIR).iterdir() if path.is_file()
    )
    if len(predecessor_files) != 12:
        raise ValueError("v26.97 output denominator changed")
    expected_output_hashes = {item.relative_path: item.sha256 for item in report.detail_files}
    expected_output_hashes["report.json"] = EXPECTED_V26_97_REPORT_SHA256
    if set(expected_output_hashes) != {path.name for path in predecessor_files}:
        raise ValueError("v26.97 report does not bind the exact output denominator")
    for path in predecessor_files:
        _load_canonical_json(path)
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_97_output",
                expected_sha256=expected_output_hashes[path.name],
            )
        )
    implementation_root = Path(__file__).resolve().parents[4]
    implementation_path = implementation_root / IMPLEMENTATION_SOURCE_PATH
    entries.append(
        _source_entry(
            path=implementation_path,
            package_root=package_root,
            source_kind="v26_98_implementation",
            expected_sha256=_sha256(implementation_path),
            relative_path=IMPLEMENTATION_SOURCE_PATH,
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = ExecutionBindingSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionBindingSourceReplayAudit(
        audit_id=source_replay_audit_id(provisional),
        **values,
    )


def _load_v26_97_design(
    package_root: Path,
) -> tuple[
    CompletionBoundContract,
    CompletionBoundManifest,
    ProspectiveThinkingCompletionBoundProtocol,
    tuple[CompletionBoundTaskPackage, ...],
    tuple[CompletionBoundPathAudit, ...],
]:
    directory = package_root / V26_97_DIR
    contract = CompletionBoundContract.model_validate_json(
        (directory / "completion_bound_contract.json").read_text(encoding="utf-8")
    )
    manifest = CompletionBoundManifest.model_validate_json(
        (directory / "completion_bound_job_manifest.json").read_text(encoding="utf-8")
    )
    protocol = ProspectiveThinkingCompletionBoundProtocol.model_validate_json(
        (directory / "completion_bound_protocol.json").read_text(encoding="utf-8")
    )
    packages = tuple(
        CompletionBoundTaskPackage.model_validate(item)
        for item in json.loads(
            (directory / "completion_bound_task_packages.json").read_text(encoding="utf-8")
        )
    )
    paths = tuple(
        CompletionBoundPathAudit.model_validate(item)
        for item in json.loads(
            (directory / "completion_bound_path_audits.json").read_text(encoding="utf-8")
        )
    )
    if (
        contract.contract_id != EXPECTED_V26_97_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_97_MANIFEST_ID
        or protocol.protocol_id != EXPECTED_PROTOCOL_ID
        or protocol.initial_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        or protocol.fallback_candidate_id != EXPECTED_FALLBACK_CANDIDATE_ID
        or len(packages) != 24
        or len(paths) != 48
        or len(manifest.jobs) != 32
    ):
        raise ValueError("v26.97 frozen execution design changed")
    return contract, manifest, protocol, packages, paths


def _load_profiles(
    package_root: Path,
) -> tuple[
    AgentModelConfig,
    ProspectiveThinkingModelBinding,
    AgentModelConfig,
    ProspectiveThinkingModelBinding,
]:
    payload = json.loads((package_root / MODEL_PROFILE_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or not isinstance(payload.get("model"), Mapping):
        raise ValueError("Thinking profile lacks a model object")
    frozen = require_prospective_thinking(AgentModelConfig.model_validate(payload["model"]))
    frozen_binding = bind_prospective_thinking(frozen)
    values = frozen.model_dump(mode="python")
    values["max_output_tokens"] = 8192
    derived = require_prospective_thinking(AgentModelConfig.model_validate(values))
    derived_binding = bind_prospective_thinking(derived)
    if (
        frozen.max_output_tokens != 4096
        or frozen.public_manifest_hash != EXPECTED_FROZEN_MODEL_CONFIG_ID
        or frozen_binding.binding_id != EXPECTED_FROZEN_THINKING_BINDING_ID
        or derived.max_output_tokens != 8192
        or derived.public_manifest_hash != EXPECTED_DERIVED_8K_MODEL_CONFIG_ID
        or derived_binding.binding_id != EXPECTED_DERIVED_8K_THINKING_BINDING_ID
    ):
        raise ValueError("v26.98 profile identity reconstruction changed")
    return frozen, frozen_binding, derived, derived_binding


def _build_profile_audit(package_root: Path) -> ExecutionProfileBindingAudit:
    _, _, protocol, packages, _ = _load_v26_97_design(package_root)
    frozen, frozen_binding, derived, derived_binding = _load_profiles(package_root)
    rows = []
    for package in sorted(packages, key=lambda item: item.task_package_id):
        if (
            package.selected_candidate_id != protocol.initial_candidate_id
            or package.model_config_id != frozen.public_manifest_hash
            or package.thinking_binding_id != frozen_binding.binding_id
        ):
            raise ValueError("v26.97 TaskPackage profile binding changed")
        row_values = {
            "task_package_id": package.task_package_id,
            "bound_model_config_id": package.model_config_id,
            "bound_thinking_binding_id": package.thinking_binding_id,
            "derived_8k_model_config_id": derived.public_manifest_hash,
            "derived_8k_thinking_binding_id": derived_binding.binding_id,
        }
        provisional = TaskPackageExecutionBindingRow.model_construct(
            row_id="pending",
            **row_values,
        )
        rows.append(
            TaskPackageExecutionBindingRow(
                row_id=task_package_binding_row_id(provisional),
                **row_values,
            )
        )
    audit_values = {"task_package_rows": tuple(rows)}
    provisional = ExecutionProfileBindingAudit.model_construct(
        audit_id="pending",
        **audit_values,
    )
    return ExecutionProfileBindingAudit(
        audit_id=profile_binding_audit_id(provisional),
        **audit_values,
    )


def _build_job_audit(package_root: Path) -> JobExecutionBindingAudit:
    _, manifest, _, packages, _ = _load_v26_97_design(package_root)
    package_by_id = {item.task_package_id: item for item in packages}
    rows = []
    for index, job in enumerate(manifest.jobs):
        package = package_by_id[job.task_package_id]
        if (
            job.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or job.completion_upper_bound_tokens != 8192
            or job.rollout_upper_bound_tokens != 160000
            or package.model_config_id != EXPECTED_FROZEN_MODEL_CONFIG_ID
        ):
            raise ValueError("v26.97 Job/Profile binding changed")
        values = {
            "manifest_index": index,
            "job_id": job.job_id,
            "task_package_id": job.task_package_id,
        }
        provisional = JobExecutionBindingRow.model_construct(row_id="pending", **values)
        rows.append(JobExecutionBindingRow(row_id=job_binding_row_id(provisional), **values))
    values = {"rows": tuple(rows)}
    provisional = JobExecutionBindingAudit.model_construct(audit_id="pending", **values)
    return JobExecutionBindingAudit(
        audit_id=job_binding_audit_id(provisional),
        **values,
    )


def _build_root_cause(
    profile: ExecutionProfileBindingAudit,
    jobs: JobExecutionBindingAudit,
) -> ExecutionBindingRootCauseAudit:
    values = {
        "profile_binding_audit_id": profile.audit_id,
        "job_binding_audit_id": jobs.audit_id,
    }
    provisional = ExecutionBindingRootCauseAudit.model_construct(audit_id="pending", **values)
    return ExecutionBindingRootCauseAudit(
        audit_id=root_cause_audit_id(provisional),
        **values,
    )


def _build_transition(
    root_cause: ExecutionBindingRootCauseAudit,
) -> ProspectiveExecutionRebindingContract:
    values = {"root_cause_audit_id": root_cause.audit_id}
    provisional = ProspectiveExecutionRebindingContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveExecutionRebindingContract(
        contract_id=transition_contract_id(provisional),
        **values,
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except Exception as exc:
        values = {"mutation_name": name, "failure_type": type(exc).__name__}
        provisional = MutationResult.model_construct(mutation_id="pending", **values)
        return MutationResult(
            mutation_id=mutation_result_id(provisional),
            **values,
        )
    raise ValueError(f"destructive mutation was accepted: {name}")


def _validated_update(model: BaseModel, **updates: Any) -> Any:
    payload = model.model_dump(mode="json")
    payload.update(updates)
    return type(model).model_validate(payload)


def _build_destructive(
    profile: ExecutionProfileBindingAudit,
    jobs: JobExecutionBindingAudit,
    root_cause: ExecutionBindingRootCauseAudit,
    transition: ProspectiveExecutionRebindingContract,
) -> ExecutionBindingDestructiveAudit:
    sample_package = profile.task_package_rows[0]
    sample_job = jobs.rows[0]
    mutations = tuple(
        sorted(
            (
                _expect_rejection(
                    "candidate_field_overrides_model_config_identity",
                    lambda: _validated_update(
                        root_cause,
                        candidate_field_can_override_agent_model_config_identity=True,
                    ),
                ),
                _expect_rejection(
                    "claim_4k_profile_matches_8k_candidate",
                    lambda: _validated_update(
                        sample_package,
                        bound_profile_matches_selected_candidate=True,
                    ),
                ),
                _expect_rejection(
                    "claim_exact_8k_taskpackage_binding",
                    lambda: _validated_update(sample_package, exact_execution_binding_closed=True),
                ),
                _expect_rejection(
                    "derived_8k_config_reuses_old_identity",
                    lambda: _validated_update(
                        sample_package,
                        derived_8k_model_config_id=EXPECTED_FROZEN_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "derived_8k_thinking_reuses_old_binding",
                    lambda: _validated_update(
                        sample_package,
                        derived_8k_thinking_binding_id=EXPECTED_FROZEN_THINKING_BINDING_ID,
                    ),
                ),
                _expect_rejection(
                    "job_provider_call_authorized",
                    lambda: _validated_update(sample_job, provider_call_authorized=True),
                ),
                _expect_rejection(
                    "old_taskpackage_identity_reuse",
                    lambda: _validated_update(
                        transition,
                        old_task_package_identity_reuse_allowed=True,
                    ),
                ),
                _expect_rejection(
                    "old_path_identity_reuse",
                    lambda: _validated_update(
                        transition,
                        old_path_audit_identity_reuse_allowed=True,
                    ),
                ),
                _expect_rejection(
                    "old_execution_identity_reuse",
                    lambda: _validated_update(
                        transition,
                        old_contract_manifest_or_job_identity_reuse_allowed=True,
                    ),
                ),
                _expect_rejection(
                    "runner_materialized_before_rebinding",
                    lambda: _validated_update(
                        transition,
                        runner_materialization_before_rebinding_pass_allowed=True,
                    ),
                ),
                _expect_rejection(
                    "fallback_16k_jobs_inserted",
                    lambda: _validated_update(transition, fallback_16k_jobs_allowed=True),
                ),
                _expect_rejection(
                    "semantic_evidence_authorization",
                    lambda: _validated_update(
                        transition,
                        capability_or_reachability_evidence_allowed=True,
                    ),
                ),
            ),
            key=lambda item: item.mutation_name,
        )
    )
    values = {"mutation_results": mutations}
    provisional = ExecutionBindingDestructiveAudit.model_construct(audit_id="pending", **values)
    return ExecutionBindingDestructiveAudit(
        audit_id=destructive_audit_id(provisional),
        **values,
    )


def _detail(path: Path, output_dir: Path, count: int) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def build_thinking_8k_execution_binding_preflight(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> ExecutionBindingPreflightReport:
    if run_id != RUN_ID:
        raise ValueError("v26.98 run identity changed")
    source = _build_source_replay(package_root)
    profile = _build_profile_audit(package_root)
    jobs = _build_job_audit(package_root)
    root_cause = _build_root_cause(profile, jobs)
    transition = _build_transition(root_cause)
    destructive = _build_destructive(profile, jobs, root_cause, transition)
    details: tuple[tuple[str, BaseModel, int], ...] = (
        ("source_replay_audit.json", source, len(source.entries)),
        ("execution_profile_binding_audit.json", profile, len(profile.task_package_rows)),
        ("job_execution_binding_audit.json", jobs, len(jobs.rows)),
        ("execution_binding_root_cause_audit.json", root_cause, 1),
        ("prospective_rebinding_contract.json", transition, 1),
        ("destructive_preflight_audit.json", destructive, len(destructive.mutation_results)),
    )
    for name, model, _ in details:
        _write_json(output_dir / name, model.model_dump(mode="json"))
    detail_files = tuple(
        _detail(output_dir / name, output_dir, count) for name, _, count in sorted(details)
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "profile_binding_audit_id": profile.audit_id,
        "job_binding_audit_id": jobs.audit_id,
        "root_cause_audit_id": root_cause.audit_id,
        "transition_contract_id": transition.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": detail_files,
    }
    provisional = ExecutionBindingPreflightReport.model_construct(report_id="pending", **values)
    report = ExecutionBindingPreflightReport(
        report_id=preflight_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the v26.98 8K execution-profile binding preflight"
    )
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_thinking_8k_execution_binding_preflight(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
