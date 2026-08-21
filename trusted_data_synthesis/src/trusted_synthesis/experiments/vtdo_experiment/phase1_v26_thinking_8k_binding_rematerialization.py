from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_execution_binding_preflight import (  # noqa: E501
    ExecutionBindingPreflightReport,
    ExecutionBindingSourceReplayAudit,
    ProspectiveExecutionRebindingContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_bound_redesign_preflight import (  # noqa: E501
    CandidatePathBudget,
    CompletionBoundContract,
    CompletionBoundJob,
    CompletionBoundManifest,
    CompletionBoundPathAudit,
    CompletionBoundPreflightReport,
    CompletionBoundTaskPackage,
    DynamicRescueCoverageAudit,
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

RUN_ID: Final = "finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822"
PROSPECTIVE_RUNNER_PREFLIGHT_RUN_ID: Final = (
    "finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822"
)
PROSPECTIVE_EXECUTION_REPORT_RUN_ID: Final = (
    "finance_v26_101_thinking_8k_completion_calibration_execution_report_v1_20260822"
)
NEXT_PERMITTED_STAGE: Final = "thinking_8k_completion_calibration_runner_and_preflight_only"

EXPECTED_V26_98_REPORT_ID: Final = (
    "finance_v26_8k_execution_binding_preflight_report:"
    "61d98194329348a5d0e6e915025276f524aec4b25a13807bed08644b34e6ebc4"
)
EXPECTED_V26_98_TRANSITION_ID: Final = (
    "finance_v26_8k_execution_binding_transition:"
    "5aa2371756e3478f862a172d83d61b21291e8cfe11c9d100db0a448ab448fd58"
)
EXPECTED_V26_98_REPORT_SHA256: Final = (
    "7900c8306ac9b4ae5e094ade72684575555f92dd20675afa93a81a570f2efde2"
)
EXPECTED_V26_97_REPORT_ID: Final = (
    "finance_v26_completion_bound_preflight_report:"
    "09cfd5171d2cd29dd36ab51d5124900f513cbaac3a9fcd0f96aa0fdcb66d7486"
)
EXPECTED_V26_97_CONTRACT_ID: Final = (
    "finance_v26_completion_bound_contract:"
    "cf71fa07ae0be111c1e2843b14c1a8f6f3903371a365396da2c749217401ada4"
)
EXPECTED_V26_97_MANIFEST_ID: Final = (
    "finance_v26_completion_bound_manifest:"
    "11b3bb1f686f52f6c673f5e59b30757104d1769aaec0bae51eba4c4f25dbbdae"
)
EXPECTED_BOUND_PROTOCOL_ID: Final = (
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
EXPECTED_4K_MODEL_CONFIG_ID: Final = (
    "agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1"
)
EXPECTED_4K_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d"
)
EXPECTED_8K_MODEL_CONFIG_ID: Final = (
    "agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e"
)
EXPECTED_8K_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57"
)
EXPECTED_THINKING_POLICY_ID: Final = (
    "prospective_thinking_mode_policy:"
    "b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f"
)
EXPECTED_RESPONSE_PROTOCOL_ID: Final = (
    "prospective_thinking_completion_protocol:"
    "4fd11877d7a7ed795efc80e07382cea4dd2ba7c3915bfe05439665301084f5f1"
)
EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID: Final = (
    "finance_v26_thinking_telemetry_repair_contract:"
    "10f084cc4aac9172cede50ab7f0fbaf339997c9a1cac43f74aed8f107d886343"
)

V26_97_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822"
)
V26_98_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822"
)
OLD_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_thinking_v1.json"
PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_thinking_8k_v1.json"
IMPLEMENTATION_SOURCE_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_thinking_8k_binding_rematerialization.py"
)

SOURCE_VERSION: Final[Literal["finance_v26_exact_8k_source_replay.v1"]] = (
    "finance_v26_exact_8k_source_replay.v1"
)
PROFILE_VERSION: Final[Literal["finance_v26_exact_8k_profile_binding.v1"]] = (
    "finance_v26_exact_8k_profile_binding.v1"
)
TASK_VERSION: Final[Literal["finance_v26_exact_8k_task_package.v1"]] = (
    "finance_v26_exact_8k_task_package.v1"
)
PATH_VERSION: Final[Literal["finance_v26_exact_8k_path_audit.v1"]] = (
    "finance_v26_exact_8k_path_audit.v1"
)
CONTRACT_VERSION: Final[Literal["finance_v26_exact_8k_completion_contract.v1"]] = (
    "finance_v26_exact_8k_completion_contract.v1"
)
JOB_VERSION: Final[Literal["finance_v26_exact_8k_job.v1"]] = "finance_v26_exact_8k_job.v1"
MANIFEST_VERSION: Final[Literal["finance_v26_exact_8k_manifest.v1"]] = (
    "finance_v26_exact_8k_manifest.v1"
)
PRESERVATION_VERSION: Final[Literal["finance_v26_exact_8k_design_preservation.v1"]] = (
    "finance_v26_exact_8k_design_preservation.v1"
)
BINDING_VERSION: Final[Literal["finance_v26_exact_8k_cross_artifact_binding.v1"]] = (
    "finance_v26_exact_8k_cross_artifact_binding.v1"
)
FRESHNESS_VERSION: Final[Literal["finance_v26_exact_8k_freshness.v1"]] = (
    "finance_v26_exact_8k_freshness.v1"
)
DESTRUCTIVE_VERSION: Final[Literal["finance_v26_exact_8k_destructive.v1"]] = (
    "finance_v26_exact_8k_destructive.v1"
)
REPORT_VERSION: Final[Literal["finance_v26_exact_8k_rematerialization_report.v1"]] = (
    "finance_v26_exact_8k_rematerialization_report.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_98_transitive_source",
        "v26_98_output",
        "v26_99_implementation",
        "v26_99_profile",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.99 source replay changed")
        return self


class Exact8KSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_98_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_98_TRANSITION_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=755, max_length=755)
    predecessor_transitive_source_count: Literal[746] = 746
    predecessor_output_count: Literal[7] = 7
    implementation_source_count: Literal[1] = 1
    persisted_profile_count: Literal[1] = 1
    replayed_file_count: Literal[755] = 755
    replay_pass_count: Literal[755] = 755
    replay_before_rematerialization: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_8k_source_replay.v1"] = SOURCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 755:
            raise ValueError("v26.99 source replay denominator is not canonical")
        if self.audit_id != exact_8k_source_replay_id(self):
            raise ValueError("v26.99 source replay identity mismatch")
        return self


class Exact8KProfileBinding(FrozenModel):
    binding_audit_id: str = Field(min_length=1)
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    predecessor_profile_relative_path: str = OLD_PROFILE_PATH
    predecessor_profile_sha256: str = Field(min_length=64, max_length=64)
    differing_model_fields: tuple[Literal["max_output_tokens"], ...] = ("max_output_tokens",)
    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    thinking_type: Literal["enabled"] = "enabled"
    max_output_tokens: Literal[8192] = 8192
    predecessor_max_output_tokens: Literal[4096] = 4096
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    predecessor_model_config_id: str = EXPECTED_4K_MODEL_CONFIG_ID
    thinking_policy_id: str = EXPECTED_THINKING_POLICY_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    predecessor_thinking_binding_id: str = EXPECTED_4K_THINKING_BINDING_ID
    selected_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    candidate_completion_upper_bound_tokens: Literal[8192] = 8192
    candidate_rollout_upper_bound_tokens: Literal[160000] = 160000
    exact_8k_profile_persisted: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_profile_binding.v1"] = PROFILE_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> Exact8KProfileBinding:
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.thinking_policy_id != EXPECTED_THINKING_POLICY_ID
            or self.predecessor_model_config_id != EXPECTED_4K_MODEL_CONFIG_ID
            or self.predecessor_thinking_binding_id != EXPECTED_4K_THINKING_BINDING_ID
            or self.selected_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        ):
            raise ValueError("v26.99 exact 8K profile identity changed")
        if self.binding_audit_id != exact_8k_profile_binding_id(self):
            raise ValueError("v26.99 profile-binding identity mismatch")
        return self


class Exact8KTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_repair_task_package_id: str = Field(min_length=1)
    source_role_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    completion_response_protocol_id: str = EXPECTED_RESPONSE_PROTOCOL_ID
    completion_bound_protocol_id: str = EXPECTED_BOUND_PROTOCOL_ID
    selected_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_policy_id: str = EXPECTED_THINKING_POLICY_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    response_telemetry_contract_id: str = EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    rescue_prompt_upper_bound_bytes: Literal[6144] = 6144
    maximum_rescue_calls: Literal[1] = 1
    source_model_exposed_before_freeze: bool
    source_task_claimed_fresh: Literal[False] = False
    engineering_calibration_only: Literal[True] = True
    empirical_capability_support_eligible: Literal[False] = False
    empirical_reachability_support_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_task_package.v1"] = TASK_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> Exact8KTaskPackage:
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.thinking_policy_id != EXPECTED_THINKING_POLICY_ID
            or self.selected_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or self.completion_response_protocol_id != EXPECTED_RESPONSE_PROTOCOL_ID
            or self.completion_bound_protocol_id != EXPECTED_BOUND_PROTOCOL_ID
            or self.response_telemetry_contract_id != EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID
        ):
            raise ValueError("v26.99 TaskPackage exact 8K binding changed")
        if self.task_package_id != exact_8k_task_package_id(self):
            raise ValueError("v26.99 TaskPackage identity mismatch")
        return self


class Exact8KPathAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal[
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    ]
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    primary_request_count: int = Field(gt=0)
    compiler_state_row_ids: tuple[str, ...] = Field(min_length=1)
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=6144)
    candidate_budgets: tuple[CandidatePathBudget, CandidatePathBudget]
    initial_candidate_passed: Literal[True] = True
    fallback_candidate_passed_static_only: Literal[True] = True
    prompt_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_path_audit.v1"] = PATH_VERSION

    @model_validator(mode="after")
    def validate_path(self) -> Exact8KPathAudit:
        if self.primary_request_count != len(self.compiler_state_row_ids):
            raise ValueError("v26.99 path request count changed")
        if tuple(item.completion_upper_bound_tokens for item in self.candidate_budgets) != (
            8192,
            16384,
        ):
            raise ValueError("v26.99 path candidate ladder changed")
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        ):
            raise ValueError("v26.99 path profile binding changed")
        if self.audit_id != exact_8k_path_audit_id(self):
            raise ValueError("v26.99 path identity mismatch")
        return self


class Exact8KCompletionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_98_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_98_TRANSITION_ID
    predecessor_completion_contract_id: str = EXPECTED_V26_97_CONTRACT_ID
    source_replay_audit_id: str = Field(min_length=1)
    profile_binding_audit_id: str = Field(min_length=1)
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_policy_id: str = EXPECTED_THINKING_POLICY_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    completion_response_protocol_id: str = EXPECTED_RESPONSE_PROTOCOL_ID
    completion_bound_protocol_id: str = EXPECTED_BOUND_PROTOCOL_ID
    response_telemetry_contract_id: str = EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID
    dynamic_rescue_coverage_audit_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    initial_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    fallback_candidate_id: str = EXPECTED_FALLBACK_CANDIDATE_ID
    prospective_runner_preflight_run_id: str = PROSPECTIVE_RUNNER_PREFLIGHT_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_execution_report_run_id: str = PROSPECTIVE_EXECUTION_REPORT_RUN_ID
    exact_job_denominator: Literal[32] = 32
    initial_completion_upper_bound_tokens: Literal[8192] = 8192
    initial_rollout_upper_bound_tokens: Literal[160000] = 160000
    fallback_completion_upper_bound_tokens: Literal[16384] = 16384
    fallback_rollout_upper_bound_tokens: Literal[240000] = 240000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    rescue_prompt_upper_bound_bytes: Literal[6144] = 6144
    maximum_rescue_calls_per_job: Literal[1] = 1
    fallback_jobs_materialized: Literal[0] = 0
    automatic_bound_escalation_allowed: Literal[False] = False
    zero_failure_completion_gate_retained: Literal[True] = True
    zero_failure_typed_no_call_gate_retained: Literal[True] = True
    transport_and_telemetry_failures_separate: Literal[True] = True
    semantic_validity_cannot_rescue_failure_gates: Literal[True] = True
    any_initial_length_failure_next_stage: Literal["fresh_16k_completion_preflight_only"] = (
        "fresh_16k_completion_preflight_only"
    )
    any_initial_nonlength_completion_failure_next_stage: Literal[
        "completion_contract_root_cause_audit_only"
    ] = "completion_contract_root_cause_audit_only"
    fully_passing_initial_denominator_next_stage: Literal["thinking_role_protocol_freeze_only"] = (
        "thinking_role_protocol_freeze_only"
    )
    runner_implementation_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_completion_contract.v1"] = CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> Exact8KCompletionContract:
        if len(set(self.task_package_ids)) != 24 or len(set(self.path_audit_ids)) != 48:
            raise ValueError("v26.99 Contract identity denominator changed")
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.thinking_policy_id != EXPECTED_THINKING_POLICY_ID
            or self.initial_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or self.fallback_candidate_id != EXPECTED_FALLBACK_CANDIDATE_ID
            or self.completion_response_protocol_id != EXPECTED_RESPONSE_PROTOCOL_ID
            or self.completion_bound_protocol_id != EXPECTED_BOUND_PROTOCOL_ID
            or self.response_telemetry_contract_id != EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID
        ):
            raise ValueError("v26.99 Contract profile binding changed")
        if self.contract_id != exact_8k_contract_id(self):
            raise ValueError("v26.99 Contract identity mismatch")
        return self


class Exact8KJob(FrozenModel):
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal[
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    ]
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    maximum_rescue_calls: Literal[1] = 1
    thinking_type: Literal["enabled"] = "enabled"
    source_repeated_for_engineering_calibration: Literal[True] = True
    schema_version: Literal["finance_v26_exact_8k_job.v1"] = JOB_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> Exact8KJob:
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        ):
            raise ValueError("v26.99 Job exact profile binding changed")
        if self.job_id != exact_8k_job_id(self):
            raise ValueError("v26.99 Job identity mismatch")
        return self


class Exact8KManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    predecessor_manifest_id: str = EXPECTED_V26_97_MANIFEST_ID
    contract_id: str = Field(min_length=1)
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    prospective_runner_preflight_run_id: str = PROSPECTIVE_RUNNER_PREFLIGHT_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    maximum_rescue_calls_per_job: Literal[1] = 1
    jobs: tuple[Exact8KJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    fallback_job_count: Literal[0] = 0
    predecessor_job_identity_overlap_count: Literal[0] = 0
    historical_v26_95_job_overlap_count: Literal[0] = 0
    exact_denominator_frozen: Literal[32] = 32
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_manifest.v1"] = MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> Exact8KManifest:
        if len({item.job_id for item in self.jobs}) != 32:
            raise ValueError("v26.99 Jobs are not unique")
        if len({item.task_package_id for item in self.jobs}) != 24:
            raise ValueError("v26.99 Manifest does not cover all TaskPackages")
        if self.mechanism_job_counts != {
            "context_conditioned_action": 8,
            "failure_recovery": 8,
            "semantic_reconciliation": 8,
            "state_dependent_stopping": 8,
        }:
            raise ValueError("v26.99 mechanism balance changed")
        if self.path_job_counts != {
            "search_then_open": 12,
            "search_then_structured": 8,
            "structured_direct": 12,
        }:
            raise ValueError("v26.99 path balance changed")
        if len(self.cell_job_counts) != 12 or set(self.cell_job_counts.values()) - {2, 3}:
            raise ValueError("v26.99 cell balance changed")
        if (
            self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        ):
            raise ValueError("v26.99 Manifest exact profile binding changed")
        if self.manifest_id != exact_8k_manifest_id(self):
            raise ValueError("v26.99 Manifest identity mismatch")
        return self


class TaskPackagePreservationRow(FrozenModel):
    predecessor_task_package_id: str = Field(min_length=1)
    successor_task_package_id: str = Field(min_length=1)
    predecessor_semantic_projection_sha256: str = Field(min_length=64, max_length=64)
    successor_semantic_projection_sha256: str = Field(min_length=64, max_length=64)
    only_execution_binding_and_identity_changed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> TaskPackagePreservationRow:
        if self.predecessor_task_package_id == self.successor_task_package_id:
            raise ValueError("v26.99 TaskPackage reused the predecessor identity")
        if self.predecessor_semantic_projection_sha256 != self.successor_semantic_projection_sha256:
            raise ValueError("v26.99 TaskPackage semantic projection changed")
        return self


class PathPreservationRow(FrozenModel):
    predecessor_path_audit_id: str = Field(min_length=1)
    successor_path_audit_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    successor_task_package_id: str = Field(min_length=1)
    predecessor_static_projection_sha256: str = Field(min_length=64, max_length=64)
    successor_static_projection_sha256: str = Field(min_length=64, max_length=64)
    prompt_and_budget_values_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> PathPreservationRow:
        if self.predecessor_path_audit_id == self.successor_path_audit_id:
            raise ValueError("v26.99 Path reused the predecessor identity")
        if self.predecessor_static_projection_sha256 != self.successor_static_projection_sha256:
            raise ValueError("v26.99 Path static projection changed")
        return self


class JobPreservationRow(FrozenModel):
    manifest_index: int = Field(ge=0, lt=32)
    predecessor_job_id: str = Field(min_length=1)
    successor_job_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    successor_task_package_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    successor_path_audit_id: str = Field(min_length=1)
    predecessor_seed: int = Field(ge=0)
    successor_seed: int = Field(ge=0)
    predecessor_assignment_projection_sha256: str = Field(min_length=64, max_length=64)
    successor_assignment_projection_sha256: str = Field(min_length=64, max_length=64)
    seed_and_assignment_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> JobPreservationRow:
        if self.predecessor_job_id == self.successor_job_id:
            raise ValueError("v26.99 Job reused the predecessor identity")
        if self.predecessor_seed != self.successor_seed:
            raise ValueError("v26.99 Job seed changed")
        if (
            self.predecessor_assignment_projection_sha256
            != self.successor_assignment_projection_sha256
        ):
            raise ValueError("v26.99 Job assignment changed")
        return self


class Exact8KDesignPreservationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_rows: tuple[TaskPackagePreservationRow, ...] = Field(
        min_length=24,
        max_length=24,
    )
    path_rows: tuple[PathPreservationRow, ...] = Field(min_length=48, max_length=48)
    job_rows: tuple[JobPreservationRow, ...] = Field(min_length=32, max_length=32)
    frozen_protocol_id: str = EXPECTED_BOUND_PROTOCOL_ID
    frozen_protocol_sha256: str = Field(min_length=64, max_length=64)
    frozen_dynamic_rescue_audit_id: str = Field(min_length=1)
    frozen_dynamic_rescue_sha256: str = Field(min_length=64, max_length=64)
    frozen_response_telemetry_contract_id: str = EXPECTED_RESPONSE_TELEMETRY_CONTRACT_ID
    frozen_initial_candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    frozen_fallback_candidate_id: str = EXPECTED_FALLBACK_CANDIDATE_ID
    task_package_semantic_pass_count: Literal[24] = 24
    path_prompt_budget_pass_count: Literal[48] = 48
    job_seed_assignment_pass_count: Literal[32] = 32
    source_task_selection_change_count: Literal[0] = 0
    path_selection_change_count: Literal[0] = 0
    job_assignment_change_count: Literal[0] = 0
    seed_value_change_count: Literal[0] = 0
    mechanism_path_layout_change_count: Literal[0] = 0
    prompt_or_rescue_change_count: Literal[0] = 0
    response_telemetry_change_count: Literal[0] = 0
    semantic_outcomes_used_for_rematerialization: Literal[False] = False
    schema_version: Literal["finance_v26_exact_8k_design_preservation.v1"] = PRESERVATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KDesignPreservationAudit:
        if tuple(item.manifest_index for item in self.job_rows) != tuple(range(32)):
            raise ValueError("v26.99 Job preservation order changed")
        if len({item.successor_task_package_id for item in self.task_package_rows}) != 24:
            raise ValueError("v26.99 TaskPackage preservation denominator changed")
        if len({item.successor_path_audit_id for item in self.path_rows}) != 48:
            raise ValueError("v26.99 Path preservation denominator changed")
        if self.audit_id != exact_8k_preservation_audit_id(self):
            raise ValueError("v26.99 preservation audit identity mismatch")
        return self


class CrossArtifactBindingRow(FrozenModel):
    artifact_kind: Literal["task_package", "path", "job"]
    artifact_id: str = Field(min_length=1)
    contract_id: str | None = None
    task_package_id: str = Field(min_length=1)
    path_audit_id: str | None = None
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    exact_static_binding_closed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> CrossArtifactBindingRow:
        if (
            self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
        ):
            raise ValueError("v26.99 cross-artifact binding row changed")
        if self.artifact_kind == "task_package" and (
            self.artifact_id != self.task_package_id
            or self.contract_id is not None
            or self.path_audit_id is not None
        ):
            raise ValueError("v26.99 TaskPackage cross-artifact lineage changed")
        if self.artifact_kind == "path" and (
            self.artifact_id != self.path_audit_id or self.contract_id is not None
        ):
            raise ValueError("v26.99 Path cross-artifact lineage changed")
        if self.artifact_kind == "job" and (self.contract_id is None or self.path_audit_id is None):
            raise ValueError("v26.99 Job cross-artifact lineage changed")
        return self


class Exact8KCrossArtifactBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    profile_binding_audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    candidate_id: str = EXPECTED_INITIAL_CANDIDATE_ID
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = Field(min_length=64, max_length=64)
    model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_8K_THINKING_BINDING_ID
    completion_upper_bound_tokens: Literal[8192] = 8192
    rollout_upper_bound_tokens: Literal[160000] = 160000
    contract_task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    contract_path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    manifest_contract_id: str = Field(min_length=1)
    manifest_job_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    rows: tuple[CrossArtifactBindingRow, ...] = Field(min_length=104, max_length=104)
    task_package_binding_pass_count: Literal[24] = 24
    path_binding_pass_count: Literal[48] = 48
    job_binding_pass_count: Literal[32] = 32
    contract_binding_passed: Literal[True] = True
    manifest_binding_passed: Literal[True] = True
    static_execution_identity_chain_closed: Literal[True] = True
    required_future_client_model_config_id: str = EXPECTED_8K_MODEL_CONFIG_ID
    required_future_client_max_tokens: Literal[8192] = 8192
    actual_client_binding_deferred_to_runner_preflight: Literal[True] = True
    runner_implementation_materialized: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_cross_artifact_binding.v1"] = BINDING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KCrossArtifactBindingAudit:
        counts = Counter(item.artifact_kind for item in self.rows)
        if counts != {"task_package": 24, "path": 48, "job": 32}:
            raise ValueError("v26.99 cross-artifact denominator changed")
        if len({item.artifact_id for item in self.rows}) != 104:
            raise ValueError("v26.99 cross-artifact identities are not unique")
        if any(item.profile_sha256 != self.profile_sha256 for item in self.rows):
            raise ValueError("v26.99 cross-artifact profile hash changed")
        task_rows = tuple(item for item in self.rows if item.artifact_kind == "task_package")
        path_rows = tuple(item for item in self.rows if item.artifact_kind == "path")
        job_rows = tuple(item for item in self.rows if item.artifact_kind == "job")
        task_ids = {item.artifact_id for item in task_rows}
        path_ids = {item.artifact_id for item in path_rows}
        path_to_task = {cast(str, item.path_audit_id): item.task_package_id for item in path_rows}
        if self.contract_task_package_ids != tuple(sorted(task_ids)):
            raise ValueError("v26.99 Contract TaskPackage lineage changed")
        if self.contract_path_audit_ids != tuple(sorted(path_ids)):
            raise ValueError("v26.99 Contract Path lineage changed")
        if self.manifest_contract_id != self.contract_id:
            raise ValueError("v26.99 Manifest Contract lineage changed")
        if self.manifest_job_ids != tuple(item.artifact_id for item in job_rows):
            raise ValueError("v26.99 Manifest Job lineage changed")
        if any(item.task_package_id not in task_ids for item in path_rows):
            raise ValueError("v26.99 Path references an unknown TaskPackage")
        if any(
            item.contract_id != self.contract_id
            or item.task_package_id not in task_ids
            or item.path_audit_id not in path_ids
            or path_to_task[cast(str, item.path_audit_id)] != item.task_package_id
            for item in job_rows
        ):
            raise ValueError("v26.99 Job parent lineage changed")
        if (
            self.candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
            or self.model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
            or self.thinking_binding_id != EXPECTED_8K_THINKING_BINDING_ID
            or self.required_future_client_model_config_id != EXPECTED_8K_MODEL_CONFIG_ID
        ):
            raise ValueError("v26.99 cross-artifact top-level binding changed")
        if self.audit_id != exact_8k_cross_artifact_audit_id(self):
            raise ValueError("v26.99 cross-artifact audit identity mismatch")
        return self


class Exact8KFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_task_package_overlap_count: Literal[0] = 0
    predecessor_path_audit_overlap_count: Literal[0] = 0
    predecessor_job_overlap_count: Literal[0] = 0
    predecessor_contract_overlap_count: Literal[0] = 0
    predecessor_manifest_overlap_count: Literal[0] = 0
    predecessor_future_execution_run_id_reused: Literal[False] = False
    fresh_task_package_identity_count: Literal[24] = 24
    fresh_path_audit_identity_count: Literal[48] = 48
    fresh_job_identity_count: Literal[32] = 32
    preserved_seed_value_count: Literal[32] = 32
    model_exposed_source_task_count: Literal[22] = 22
    model_unexposed_source_task_count: Literal[2] = 2
    fallback_16k_job_count: Literal[0] = 0
    historical_job_rerun_count: Literal[0] = 0
    historical_result_reclassification_count: Literal[0] = 0
    source_tasks_claimed_fresh: Literal[False] = False
    repeated_sources_engineering_only: Literal[True] = True
    schema_version: Literal["finance_v26_exact_8k_freshness.v1"] = FRESHNESS_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KFreshnessAudit:
        if self.audit_id != exact_8k_freshness_audit_id(self):
            raise ValueError("v26.99 freshness identity mismatch")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    failure_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mutation(self) -> MutationResult:
        if self.mutation_id != exact_8k_mutation_id(self):
            raise ValueError("v26.99 mutation identity mismatch")
        return self


class Exact8KDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=25, max_length=25)
    rejected_mutation_count: Literal[25] = 25
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: Literal["finance_v26_exact_8k_destructive.v1"] = DESTRUCTIVE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> Exact8KDestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))) or not all(
            item.rejected for item in self.mutation_results
        ):
            raise ValueError("v26.99 destructive controls changed")
        if self.audit_id != exact_8k_destructive_audit_id(self):
            raise ValueError("v26.99 destructive audit identity mismatch")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class Exact8KRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_V26_98_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    profile_binding_audit_id: str = Field(min_length=1)
    completion_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    preservation_audit_id: str = Field(min_length=1)
    cross_artifact_binding_audit_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=10, max_length=10)
    replayed_source_file_count: Literal[755] = 755
    exact_8k_profile_count: Literal[1] = 1
    exact_8k_task_package_count: Literal[24] = 24
    exact_8k_path_audit_count: Literal[48] = 48
    exact_8k_job_count: Literal[32] = 32
    preserved_seed_count: Literal[32] = 32
    static_cross_artifact_binding_pass_count: Literal[104] = 104
    static_execution_identity_chain_closed: Literal[True] = True
    runner_implementation_materialized: Literal[False] = False
    execution_authorized: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    role_protocol_frozen: Literal[False] = False
    capability_development_authorized: Literal[False] = False
    state_reachability_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "thinking_8k_completion_calibration_runner_and_preflight_only"
    ] = NEXT_PERMITTED_STAGE
    schema_version: Literal["finance_v26_exact_8k_rematerialization_report.v1"] = REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Exact8KRematerializationReport:
        if self.run_id != RUN_ID or self.next_permitted_stage != NEXT_PERMITTED_STAGE:
            raise ValueError("v26.99 report transition changed")
        if self.report_id != exact_8k_report_id(self):
            raise ValueError("v26.99 report identity mismatch")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def exact_8k_source_replay_id(value: Exact8KSourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_source_replay:")


def exact_8k_profile_binding_id(value: Exact8KProfileBinding) -> str:
    return _identity(value, "binding_audit_id", "finance_v26_exact_8k_profile_binding:")


def exact_8k_task_package_id(value: Exact8KTaskPackage) -> str:
    return _identity(value, "task_package_id", "finance_v26_exact_8k_task_package:")


def exact_8k_path_audit_id(value: Exact8KPathAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_path_audit:")


def exact_8k_contract_id(value: Exact8KCompletionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_exact_8k_completion_contract:")


def exact_8k_job_id(value: Exact8KJob) -> str:
    return _identity(value, "job_id", "finance_v26_exact_8k_job:")


def exact_8k_manifest_id(value: Exact8KManifest) -> str:
    return _identity(value, "manifest_id", "finance_v26_exact_8k_manifest:")


def exact_8k_preservation_audit_id(value: Exact8KDesignPreservationAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_design_preservation:")


def exact_8k_cross_artifact_audit_id(value: Exact8KCrossArtifactBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_cross_artifact_binding:")


def exact_8k_freshness_audit_id(value: Exact8KFreshnessAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_freshness:")


def exact_8k_mutation_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_exact_8k_mutation:")


def exact_8k_destructive_audit_id(value: Exact8KDestructiveAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_exact_8k_destructive:")


def exact_8k_report_id(value: Exact8KRematerializationReport) -> str:
    return _identity(value, "report_id", "finance_v26_exact_8k_rematerialization_report:")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load_canonical_json(path: Path) -> Any:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if raw != _canonical_bytes(payload):
        raise ValueError(f"noncanonical v26.99 source JSON: {path}")
    return payload


def _write_json(path: Path, value: Any) -> None:
    raw = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"immutable v26.99 output changed: {path}")
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
        "v26_98_transitive_source",
        "v26_98_output",
        "v26_99_implementation",
        "v26_99_profile",
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


def _load_v26_98(
    package_root: Path,
) -> tuple[
    ExecutionBindingPreflightReport,
    ExecutionBindingSourceReplayAudit,
    ProspectiveExecutionRebindingContract,
]:
    directory = package_root / V26_98_DIR
    report = ExecutionBindingPreflightReport.model_validate_json(
        (directory / "report.json").read_text(encoding="utf-8")
    )
    source = ExecutionBindingSourceReplayAudit.model_validate_json(
        (directory / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    transition = ProspectiveExecutionRebindingContract.model_validate_json(
        (directory / "prospective_rebinding_contract.json").read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_V26_98_REPORT_ID
        or transition.contract_id != EXPECTED_V26_98_TRANSITION_ID
        or report.next_permitted_stage
        != "fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only"
        or transition.next_permitted_stage != report.next_permitted_stage
        or source.replayed_file_count != 746
        or report.model_api_calls
        or report.gpu_jobs
    ):
        raise ValueError("v26.99 predecessor authorization changed")
    return report, source, transition


def _build_source_replay(package_root: Path) -> Exact8KSourceReplayAudit:
    report, predecessor, _ = _load_v26_98(package_root)
    entries = [
        _source_entry(
            path=package_root / item.relative_path,
            package_root=package_root,
            source_kind="v26_98_transitive_source",
            expected_sha256=item.expected_sha256,
        )
        for item in predecessor.entries
    ]
    predecessor_files = sorted(
        path for path in (package_root / V26_98_DIR).iterdir() if path.is_file()
    )
    if len(predecessor_files) != 7:
        raise ValueError("v26.98 output denominator changed")
    expected_output_hashes = {item.relative_path: item.sha256 for item in report.detail_files}
    expected_output_hashes["report.json"] = EXPECTED_V26_98_REPORT_SHA256
    if set(expected_output_hashes) != {path.name for path in predecessor_files}:
        raise ValueError("v26.98 report does not bind the exact output denominator")
    for path in predecessor_files:
        _load_canonical_json(path)
        entries.append(
            _source_entry(
                path=path,
                package_root=package_root,
                source_kind="v26_98_output",
                expected_sha256=expected_output_hashes[path.name],
            )
        )
    implementation_root = Path(__file__).resolve().parents[4]
    implementation_path = implementation_root / IMPLEMENTATION_SOURCE_PATH
    profile_path = implementation_root / PROFILE_PATH
    entries.append(
        _source_entry(
            path=implementation_path,
            package_root=package_root,
            source_kind="v26_99_implementation",
            expected_sha256=_sha256(implementation_path),
            relative_path=IMPLEMENTATION_SOURCE_PATH,
        )
    )
    entries.append(
        _source_entry(
            path=profile_path,
            package_root=package_root,
            source_kind="v26_99_profile",
            expected_sha256=_sha256(profile_path),
            relative_path=PROFILE_PATH,
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    audit_values: dict[str, Any] = {"entries": ordered}
    provisional = Exact8KSourceReplayAudit.model_construct(
        audit_id="pending",
        **audit_values,
    )
    return Exact8KSourceReplayAudit(
        audit_id=exact_8k_source_replay_id(provisional),
        **audit_values,
    )


def _load_v26_97(
    package_root: Path,
) -> tuple[
    CompletionBoundPreflightReport,
    ProspectiveThinkingCompletionBoundProtocol,
    DynamicRescueCoverageAudit,
    tuple[CompletionBoundTaskPackage, ...],
    tuple[CompletionBoundPathAudit, ...],
    CompletionBoundContract,
    CompletionBoundManifest,
]:
    directory = package_root / V26_97_DIR
    report = CompletionBoundPreflightReport.model_validate_json(
        (directory / "report.json").read_text(encoding="utf-8")
    )
    protocol = ProspectiveThinkingCompletionBoundProtocol.model_validate_json(
        (directory / "completion_bound_protocol.json").read_text(encoding="utf-8")
    )
    dynamic = DynamicRescueCoverageAudit.model_validate_json(
        (directory / "dynamic_rescue_coverage_audit.json").read_text(encoding="utf-8")
    )
    task_packages = cast(
        tuple[CompletionBoundTaskPackage, ...],
        _rows(directory / "completion_bound_task_packages.json", CompletionBoundTaskPackage),
    )
    paths = cast(
        tuple[CompletionBoundPathAudit, ...],
        _rows(directory / "completion_bound_path_audits.json", CompletionBoundPathAudit),
    )
    contract = CompletionBoundContract.model_validate_json(
        (directory / "completion_bound_contract.json").read_text(encoding="utf-8")
    )
    manifest = CompletionBoundManifest.model_validate_json(
        (directory / "completion_bound_job_manifest.json").read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_V26_97_REPORT_ID
        or protocol.protocol_id != EXPECTED_BOUND_PROTOCOL_ID
        or protocol.initial_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        or protocol.fallback_candidate_id != EXPECTED_FALLBACK_CANDIDATE_ID
        or contract.contract_id != EXPECTED_V26_97_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_97_MANIFEST_ID
        or len(task_packages) != 24
        or len(paths) != 48
        or len(manifest.jobs) != 32
        or dynamic.total_rescue_projection_count != 2400
    ):
        raise ValueError("v26.99 v26.97 design source changed")
    return report, protocol, dynamic, task_packages, paths, contract, manifest


def _load_profile(
    package_root: Path,
) -> tuple[
    AgentModelConfig,
    ProspectiveThinkingModelBinding,
    AgentModelConfig,
    ProspectiveThinkingModelBinding,
]:
    implementation_root = Path(__file__).resolve().parents[4]
    old_payload = json.loads((package_root / OLD_PROFILE_PATH).read_text(encoding="utf-8"))
    new_payload = json.loads((implementation_root / PROFILE_PATH).read_text(encoding="utf-8"))
    if (
        not isinstance(old_payload, Mapping)
        or not isinstance(new_payload, Mapping)
        or not isinstance(old_payload.get("model"), Mapping)
        or not isinstance(new_payload.get("model"), Mapping)
    ):
        raise ValueError("v26.99 profile lacks a model object")
    old_config = require_prospective_thinking(AgentModelConfig.model_validate(old_payload["model"]))
    new_config = require_prospective_thinking(AgentModelConfig.model_validate(new_payload["model"]))
    old_binding = bind_prospective_thinking(old_config)
    new_binding = bind_prospective_thinking(new_config)
    old_values = old_config.model_dump(mode="json")
    new_values = new_config.model_dump(mode="json")
    differing_fields = tuple(
        sorted(
            key
            for key in set(old_values) | set(new_values)
            if old_values.get(key) != new_values.get(key)
        )
    )
    if (
        differing_fields != ("max_output_tokens",)
        or old_config.max_output_tokens != 4096
        or new_config.max_output_tokens != 8192
        or old_config.public_manifest_hash != EXPECTED_4K_MODEL_CONFIG_ID
        or new_config.public_manifest_hash != EXPECTED_8K_MODEL_CONFIG_ID
        or old_binding.binding_id != EXPECTED_4K_THINKING_BINDING_ID
        or new_binding.binding_id != EXPECTED_8K_THINKING_BINDING_ID
        or new_binding.policy_id != EXPECTED_THINKING_POLICY_ID
    ):
        raise ValueError("v26.99 persisted profile is not the exact 8K successor")
    return old_config, old_binding, new_config, new_binding


def _build_profile_binding(package_root: Path) -> Exact8KProfileBinding:
    old_config, old_binding, new_config, new_binding = _load_profile(package_root)
    implementation_root = Path(__file__).resolve().parents[4]
    profile_values: dict[str, Any] = {
        "profile_sha256": _sha256(implementation_root / PROFILE_PATH),
        "predecessor_profile_sha256": _sha256(package_root / OLD_PROFILE_PATH),
        "model_config_id": new_config.public_manifest_hash,
        "predecessor_model_config_id": old_config.public_manifest_hash,
        "thinking_policy_id": new_binding.policy_id,
        "thinking_binding_id": new_binding.binding_id,
        "predecessor_thinking_binding_id": old_binding.binding_id,
    }
    provisional = Exact8KProfileBinding.model_construct(
        binding_audit_id="pending",
        **profile_values,
    )
    return Exact8KProfileBinding(
        binding_audit_id=exact_8k_profile_binding_id(provisional),
        **profile_values,
    )


def _build_task_packages(
    predecessor_packages: Sequence[CompletionBoundTaskPackage],
    profile: Exact8KProfileBinding,
) -> tuple[Exact8KTaskPackage, ...]:
    output = []
    for predecessor in predecessor_packages:
        package_values: dict[str, Any] = {
            "predecessor_task_package_id": predecessor.task_package_id,
            "source_repair_task_package_id": predecessor.source_repair_task_package_id,
            "source_role_task_package_id": predecessor.source_role_task_package_id,
            "source_task_artifact_id": predecessor.source_task_artifact_id,
            "source_role": predecessor.source_role,
            "mechanism_id": predecessor.mechanism_id,
            "operational_record_id": predecessor.operational_record_id,
            "operational_task_package_id": predecessor.operational_task_package_id,
            "environment_manifest_id": predecessor.environment_manifest_id,
            "semantic_source_id": predecessor.semantic_source_id,
            "compact_prompt_contract_id": predecessor.compact_prompt_contract_id,
            "completion_bound_protocol_id": predecessor.completion_bound_protocol_id,
            "selected_candidate_id": predecessor.selected_candidate_id,
            "profile_sha256": profile.profile_sha256,
            "model_config_id": profile.model_config_id,
            "thinking_policy_id": profile.thinking_policy_id,
            "thinking_binding_id": profile.thinking_binding_id,
            "source_model_exposed_before_freeze": predecessor.source_model_exposed_before_freeze,
        }
        provisional = Exact8KTaskPackage.model_construct(
            task_package_id="pending",
            **package_values,
        )
        output.append(
            Exact8KTaskPackage(
                task_package_id=exact_8k_task_package_id(provisional),
                **package_values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.task_package_id))


def _build_path_audits(
    predecessor_paths: Sequence[CompletionBoundPathAudit],
    task_packages: Sequence[Exact8KTaskPackage],
    profile: Exact8KProfileBinding,
) -> tuple[Exact8KPathAudit, ...]:
    package_by_predecessor = {item.predecessor_task_package_id: item for item in task_packages}
    output = []
    for predecessor in predecessor_paths:
        package = package_by_predecessor[predecessor.task_package_id]
        path_values: dict[str, Any] = {
            "predecessor_path_audit_id": predecessor.audit_id,
            "task_package_id": package.task_package_id,
            "predecessor_task_package_id": predecessor.task_package_id,
            "source_task_artifact_id": predecessor.source_task_artifact_id,
            "role": predecessor.role,
            "mechanism_id": predecessor.mechanism_id,
            "path_strategy_id": predecessor.path_strategy_id,
            "profile_sha256": profile.profile_sha256,
            "model_config_id": profile.model_config_id,
            "thinking_binding_id": profile.thinking_binding_id,
            "primary_request_count": predecessor.primary_request_count,
            "compiler_state_row_ids": predecessor.compiler_state_row_ids,
            "maximum_primary_prompt_utf8_bytes": (predecessor.maximum_primary_prompt_utf8_bytes),
            "maximum_rescue_prompt_utf8_bytes": (predecessor.maximum_rescue_prompt_utf8_bytes),
            "candidate_budgets": predecessor.candidate_budgets,
        }
        provisional = Exact8KPathAudit.model_construct(
            audit_id="pending",
            **path_values,
        )
        output.append(
            Exact8KPathAudit(
                audit_id=exact_8k_path_audit_id(provisional),
                **path_values,
            )
        )
    return tuple(sorted(output, key=lambda item: item.audit_id))


def _build_contract(
    *,
    source: Exact8KSourceReplayAudit,
    profile: Exact8KProfileBinding,
    predecessor_contract: CompletionBoundContract,
    dynamic: DynamicRescueCoverageAudit,
    task_packages: Sequence[Exact8KTaskPackage],
    paths: Sequence[Exact8KPathAudit],
) -> Exact8KCompletionContract:
    if (
        predecessor_contract.dynamic_rescue_coverage_audit_id != dynamic.audit_id
        or predecessor_contract.initial_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        or predecessor_contract.fallback_candidate_id != EXPECTED_FALLBACK_CANDIDATE_ID
    ):
        raise ValueError("v26.99 predecessor Contract design changed")
    contract_values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "profile_binding_audit_id": profile.binding_audit_id,
        "profile_sha256": profile.profile_sha256,
        "model_config_id": profile.model_config_id,
        "thinking_policy_id": profile.thinking_policy_id,
        "thinking_binding_id": profile.thinking_binding_id,
        "dynamic_rescue_coverage_audit_id": dynamic.audit_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in task_packages)),
        "path_audit_ids": tuple(sorted(item.audit_id for item in paths)),
    }
    provisional = Exact8KCompletionContract.model_construct(
        contract_id="pending",
        **contract_values,
    )
    return Exact8KCompletionContract(
        contract_id=exact_8k_contract_id(provisional),
        **contract_values,
    )


def _build_manifest(
    *,
    predecessor_manifest: CompletionBoundManifest,
    contract: Exact8KCompletionContract,
    task_packages: Sequence[Exact8KTaskPackage],
    paths: Sequence[Exact8KPathAudit],
    profile: Exact8KProfileBinding,
) -> Exact8KManifest:
    package_by_predecessor = {item.predecessor_task_package_id: item for item in task_packages}
    path_by_predecessor = {item.predecessor_path_audit_id: item for item in paths}
    jobs = []
    for predecessor in predecessor_manifest.jobs:
        package = package_by_predecessor[predecessor.task_package_id]
        path = path_by_predecessor[predecessor.path_audit_id]
        job_values: dict[str, Any] = {
            "predecessor_job_id": predecessor.job_id,
            "contract_id": contract.contract_id,
            "task_package_id": package.task_package_id,
            "predecessor_task_package_id": predecessor.task_package_id,
            "path_audit_id": path.audit_id,
            "predecessor_path_audit_id": predecessor.path_audit_id,
            "source_task_artifact_id": predecessor.source_task_artifact_id,
            "mechanism_id": predecessor.mechanism_id,
            "path_strategy_id": predecessor.path_strategy_id,
            "source_role": predecessor.source_role,
            "job_seed": predecessor.job_seed,
            "profile_sha256": profile.profile_sha256,
            "model_config_id": profile.model_config_id,
            "thinking_binding_id": profile.thinking_binding_id,
        }
        provisional_job = Exact8KJob.model_construct(job_id="pending", **job_values)
        jobs.append(
            Exact8KJob(
                job_id=exact_8k_job_id(provisional_job),
                **job_values,
            )
        )
    ordered_jobs = tuple(jobs)
    if tuple(item.job_seed for item in ordered_jobs) != tuple(
        item.job_seed for item in predecessor_manifest.jobs
    ):
        raise ValueError("v26.99 changed Job seeds")
    manifest_values: dict[str, Any] = {
        "contract_id": contract.contract_id,
        "profile_sha256": profile.profile_sha256,
        "model_config_id": profile.model_config_id,
        "thinking_binding_id": profile.thinking_binding_id,
        "jobs": ordered_jobs,
        "mechanism_job_counts": predecessor_manifest.mechanism_job_counts,
        "path_job_counts": predecessor_manifest.path_job_counts,
        "cell_job_counts": predecessor_manifest.cell_job_counts,
    }
    provisional_manifest = Exact8KManifest.model_construct(
        manifest_id="pending",
        **manifest_values,
    )
    return Exact8KManifest(
        manifest_id=exact_8k_manifest_id(provisional_manifest),
        **manifest_values,
    )


def _task_semantic_projection(
    value: CompletionBoundTaskPackage | Exact8KTaskPackage,
) -> dict[str, Any]:
    return {
        "source_repair_task_package_id": value.source_repair_task_package_id,
        "source_role_task_package_id": value.source_role_task_package_id,
        "source_task_artifact_id": value.source_task_artifact_id,
        "source_role": value.source_role,
        "mechanism_id": value.mechanism_id,
        "operational_record_id": value.operational_record_id,
        "operational_task_package_id": value.operational_task_package_id,
        "environment_manifest_id": value.environment_manifest_id,
        "semantic_source_id": value.semantic_source_id,
        "compact_prompt_contract_id": value.compact_prompt_contract_id,
        "completion_bound_protocol_id": value.completion_bound_protocol_id,
        "selected_candidate_id": value.selected_candidate_id,
        "source_model_exposed_before_freeze": value.source_model_exposed_before_freeze,
        "source_task_claimed_fresh": value.source_task_claimed_fresh,
        "engineering_calibration_only": value.engineering_calibration_only,
        "empirical_capability_support_eligible": value.empirical_capability_support_eligible,
        "empirical_reachability_support_eligible": value.empirical_reachability_support_eligible,
    }


def _path_static_projection(value: CompletionBoundPathAudit | Exact8KPathAudit) -> dict[str, Any]:
    return {
        "source_task_artifact_id": value.source_task_artifact_id,
        "role": value.role,
        "mechanism_id": value.mechanism_id,
        "path_strategy_id": value.path_strategy_id,
        "primary_request_count": value.primary_request_count,
        "compiler_state_row_ids": value.compiler_state_row_ids,
        "maximum_primary_prompt_utf8_bytes": value.maximum_primary_prompt_utf8_bytes,
        "maximum_rescue_prompt_utf8_bytes": value.maximum_rescue_prompt_utf8_bytes,
        "candidate_budgets": [item.model_dump(mode="json") for item in value.candidate_budgets],
        "initial_candidate_passed": value.initial_candidate_passed,
        "fallback_candidate_passed_static_only": (value.fallback_candidate_passed_static_only),
        "prompt_ceiling_passed": value.prompt_ceiling_passed,
        "provider_calls": value.provider_calls,
        "empirical_rows": value.empirical_rows,
    }


def _job_assignment_projection(value: CompletionBoundJob | Exact8KJob) -> dict[str, Any]:
    return {
        "source_task_artifact_id": value.source_task_artifact_id,
        "mechanism_id": value.mechanism_id,
        "path_strategy_id": value.path_strategy_id,
        "source_role": value.source_role,
        "job_seed": value.job_seed,
        "candidate_id": value.candidate_id,
        "completion_upper_bound_tokens": value.completion_upper_bound_tokens,
        "rollout_upper_bound_tokens": value.rollout_upper_bound_tokens,
        "maximum_rescue_calls": value.maximum_rescue_calls,
        "thinking_type": value.thinking_type,
        "source_repeated_for_engineering_calibration": (
            value.source_repeated_for_engineering_calibration
        ),
    }


def _build_preservation_audit(
    *,
    package_root: Path,
    predecessor_packages: Sequence[CompletionBoundTaskPackage],
    task_packages: Sequence[Exact8KTaskPackage],
    predecessor_paths: Sequence[CompletionBoundPathAudit],
    paths: Sequence[Exact8KPathAudit],
    predecessor_manifest: CompletionBoundManifest,
    manifest: Exact8KManifest,
    dynamic: DynamicRescueCoverageAudit,
) -> Exact8KDesignPreservationAudit:
    task_by_predecessor = {item.predecessor_task_package_id: item for item in task_packages}
    task_rows = tuple(
        TaskPackagePreservationRow(
            predecessor_task_package_id=item.task_package_id,
            successor_task_package_id=task_by_predecessor[item.task_package_id].task_package_id,
            predecessor_semantic_projection_sha256=_projection_sha256(
                _task_semantic_projection(item)
            ),
            successor_semantic_projection_sha256=_projection_sha256(
                _task_semantic_projection(task_by_predecessor[item.task_package_id])
            ),
        )
        for item in sorted(predecessor_packages, key=lambda row: row.task_package_id)
    )
    path_by_predecessor = {item.predecessor_path_audit_id: item for item in paths}
    path_rows = tuple(
        PathPreservationRow(
            predecessor_path_audit_id=item.audit_id,
            successor_path_audit_id=path_by_predecessor[item.audit_id].audit_id,
            predecessor_task_package_id=item.task_package_id,
            successor_task_package_id=path_by_predecessor[item.audit_id].task_package_id,
            predecessor_static_projection_sha256=_projection_sha256(_path_static_projection(item)),
            successor_static_projection_sha256=_projection_sha256(
                _path_static_projection(path_by_predecessor[item.audit_id])
            ),
        )
        for item in sorted(predecessor_paths, key=lambda row: row.audit_id)
    )
    job_rows = tuple(
        JobPreservationRow(
            manifest_index=index,
            predecessor_job_id=predecessor.job_id,
            successor_job_id=successor.job_id,
            predecessor_task_package_id=predecessor.task_package_id,
            successor_task_package_id=successor.task_package_id,
            predecessor_path_audit_id=predecessor.path_audit_id,
            successor_path_audit_id=successor.path_audit_id,
            predecessor_seed=predecessor.job_seed,
            successor_seed=successor.job_seed,
            predecessor_assignment_projection_sha256=_projection_sha256(
                _job_assignment_projection(predecessor)
            ),
            successor_assignment_projection_sha256=_projection_sha256(
                _job_assignment_projection(successor)
            ),
        )
        for index, (predecessor, successor) in enumerate(
            zip(predecessor_manifest.jobs, manifest.jobs, strict=True)
        )
    )
    protocol_path = package_root / V26_97_DIR / "completion_bound_protocol.json"
    dynamic_path = package_root / V26_97_DIR / "dynamic_rescue_coverage_audit.json"
    preservation_values: dict[str, Any] = {
        "task_package_rows": task_rows,
        "path_rows": path_rows,
        "job_rows": job_rows,
        "frozen_protocol_sha256": _sha256(protocol_path),
        "frozen_dynamic_rescue_audit_id": dynamic.audit_id,
        "frozen_dynamic_rescue_sha256": _sha256(dynamic_path),
    }
    provisional = Exact8KDesignPreservationAudit.model_construct(
        audit_id="pending",
        **preservation_values,
    )
    return Exact8KDesignPreservationAudit(
        audit_id=exact_8k_preservation_audit_id(provisional),
        **preservation_values,
    )


def _build_cross_artifact_audit(
    *,
    profile: Exact8KProfileBinding,
    task_packages: Sequence[Exact8KTaskPackage],
    paths: Sequence[Exact8KPathAudit],
    contract: Exact8KCompletionContract,
    manifest: Exact8KManifest,
) -> Exact8KCrossArtifactBindingAudit:
    task_ids = {item.task_package_id for item in task_packages}
    path_ids = {item.audit_id for item in paths}
    path_by_id = {item.audit_id: item for item in paths}
    if (
        profile.max_output_tokens != contract.initial_completion_upper_bound_tokens
        or profile.candidate_rollout_upper_bound_tokens
        != contract.initial_rollout_upper_bound_tokens
        or profile.selected_candidate_id != contract.initial_candidate_id
        or contract.profile_sha256 != profile.profile_sha256
        or manifest.profile_sha256 != profile.profile_sha256
        or contract.model_config_id != profile.model_config_id
        or manifest.model_config_id != profile.model_config_id
        or contract.thinking_binding_id != profile.thinking_binding_id
        or manifest.thinking_binding_id != profile.thinking_binding_id
        or manifest.contract_id != contract.contract_id
        or set(contract.task_package_ids) != task_ids
        or set(contract.path_audit_ids) != path_ids
    ):
        raise ValueError("v26.99 Contract or Manifest binding is not closed")
    if any(item.task_package_id not in task_ids for item in paths):
        raise ValueError("v26.99 Path references an unknown TaskPackage")
    if any(
        item.contract_id != contract.contract_id
        or item.task_package_id not in task_ids
        or item.path_audit_id not in path_ids
        or path_by_id[item.path_audit_id].task_package_id != item.task_package_id
        for item in manifest.jobs
    ):
        raise ValueError("v26.99 Job parent lineage is not closed")
    rows = tuple(
        [
            CrossArtifactBindingRow(
                artifact_kind="task_package",
                artifact_id=item.task_package_id,
                task_package_id=item.task_package_id,
                candidate_id=item.selected_candidate_id,
                profile_sha256=item.profile_sha256,
                model_config_id=item.model_config_id,
                thinking_binding_id=item.thinking_binding_id,
                completion_upper_bound_tokens=item.completion_upper_bound_tokens,
                rollout_upper_bound_tokens=item.rollout_upper_bound_tokens,
            )
            for item in sorted(task_packages, key=lambda row: row.task_package_id)
        ]
        + [
            CrossArtifactBindingRow(
                artifact_kind="path",
                artifact_id=item.audit_id,
                task_package_id=item.task_package_id,
                path_audit_id=item.audit_id,
                candidate_id=item.candidate_id,
                profile_sha256=item.profile_sha256,
                model_config_id=item.model_config_id,
                thinking_binding_id=item.thinking_binding_id,
                completion_upper_bound_tokens=item.completion_upper_bound_tokens,
                rollout_upper_bound_tokens=item.rollout_upper_bound_tokens,
            )
            for item in sorted(paths, key=lambda row: row.audit_id)
        ]
        + [
            CrossArtifactBindingRow(
                artifact_kind="job",
                artifact_id=item.job_id,
                contract_id=item.contract_id,
                task_package_id=item.task_package_id,
                path_audit_id=item.path_audit_id,
                candidate_id=item.candidate_id,
                profile_sha256=item.profile_sha256,
                model_config_id=item.model_config_id,
                thinking_binding_id=item.thinking_binding_id,
                completion_upper_bound_tokens=item.completion_upper_bound_tokens,
                rollout_upper_bound_tokens=item.rollout_upper_bound_tokens,
            )
            for item in manifest.jobs
        ]
    )
    binding_values: dict[str, Any] = {
        "profile_binding_audit_id": profile.binding_audit_id,
        "contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "profile_sha256": profile.profile_sha256,
        "model_config_id": profile.model_config_id,
        "thinking_binding_id": profile.thinking_binding_id,
        "contract_task_package_ids": contract.task_package_ids,
        "contract_path_audit_ids": contract.path_audit_ids,
        "manifest_contract_id": manifest.contract_id,
        "manifest_job_ids": tuple(item.job_id for item in manifest.jobs),
        "rows": rows,
    }
    provisional = Exact8KCrossArtifactBindingAudit.model_construct(
        audit_id="pending",
        **binding_values,
    )
    return Exact8KCrossArtifactBindingAudit(
        audit_id=exact_8k_cross_artifact_audit_id(provisional),
        **binding_values,
    )


def _build_freshness_audit(
    *,
    predecessor_packages: Sequence[CompletionBoundTaskPackage],
    task_packages: Sequence[Exact8KTaskPackage],
    predecessor_paths: Sequence[CompletionBoundPathAudit],
    paths: Sequence[Exact8KPathAudit],
    predecessor_contract: CompletionBoundContract,
    contract: Exact8KCompletionContract,
    predecessor_manifest: CompletionBoundManifest,
    manifest: Exact8KManifest,
) -> Exact8KFreshnessAudit:
    if set(item.task_package_id for item in predecessor_packages) & set(
        item.task_package_id for item in task_packages
    ):
        raise ValueError("v26.99 reused a v26.97 TaskPackage identity")
    if set(item.audit_id for item in predecessor_paths) & set(item.audit_id for item in paths):
        raise ValueError("v26.99 reused a v26.97 Path identity")
    if set(item.job_id for item in predecessor_manifest.jobs) & set(
        item.job_id for item in manifest.jobs
    ):
        raise ValueError("v26.99 reused a v26.97 Job identity")
    if (
        predecessor_contract.contract_id == contract.contract_id
        or predecessor_manifest.manifest_id == manifest.manifest_id
        or predecessor_contract.prospective_execution_run_id
        == contract.prospective_execution_run_id
        or tuple(item.job_seed for item in predecessor_manifest.jobs)
        != tuple(item.job_seed for item in manifest.jobs)
    ):
        raise ValueError("v26.99 freshness or seed preservation changed")
    exposed_count = sum(item.source_model_exposed_before_freeze for item in task_packages)
    freshness_values = {
        "model_exposed_source_task_count": exposed_count,
        "model_unexposed_source_task_count": len(task_packages) - exposed_count,
    }
    provisional = Exact8KFreshnessAudit.model_construct(
        audit_id="pending",
        **freshness_values,
    )
    return Exact8KFreshnessAudit(
        audit_id=exact_8k_freshness_audit_id(provisional),
        **freshness_values,
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except Exception as exc:
        mutation_values: dict[str, Any] = {
            "mutation_name": name,
            "failure_type": type(exc).__name__,
        }
        provisional = MutationResult.model_construct(
            mutation_id="pending",
            **mutation_values,
        )
        return MutationResult(
            mutation_id=exact_8k_mutation_id(provisional),
            **mutation_values,
        )
    raise ValueError(f"v26.99 destructive mutation accepted: {name}")


def _validated_update(model: BaseModel, **updates: Any) -> Any:
    payload = model.model_dump(mode="json")
    payload.update(updates)
    return type(model).model_validate(payload)


def _build_destructive_audit(
    *,
    profile: Exact8KProfileBinding,
    task_packages: Sequence[Exact8KTaskPackage],
    paths: Sequence[Exact8KPathAudit],
    contract: Exact8KCompletionContract,
    manifest: Exact8KManifest,
    binding: Exact8KCrossArtifactBindingAudit,
) -> Exact8KDestructiveAudit:
    task = task_packages[0]
    path = paths[0]
    job = manifest.jobs[0]

    def rehashed_task(**updates: Any) -> Exact8KTaskPackage:
        values = task.model_dump(mode="python")
        values.pop("task_package_id")
        values.update(updates)
        provisional = Exact8KTaskPackage.model_construct(
            task_package_id="pending",
            **values,
        )
        return Exact8KTaskPackage(
            task_package_id=exact_8k_task_package_id(provisional),
            **values,
        )

    def rehashed_path(**updates: Any) -> Exact8KPathAudit:
        values = path.model_dump(mode="python")
        values.pop("audit_id")
        values["candidate_budgets"] = path.candidate_budgets
        values.update(updates)
        provisional = Exact8KPathAudit.model_construct(audit_id="pending", **values)
        return Exact8KPathAudit(
            audit_id=exact_8k_path_audit_id(provisional),
            **values,
        )

    def rehashed_contract(**updates: Any) -> Exact8KCompletionContract:
        values = contract.model_dump(mode="python")
        values.pop("contract_id")
        values.update(updates)
        provisional = Exact8KCompletionContract.model_construct(
            contract_id="pending",
            **values,
        )
        return Exact8KCompletionContract(
            contract_id=exact_8k_contract_id(provisional),
            **values,
        )

    def rehashed_job(**updates: Any) -> Exact8KJob:
        values = job.model_dump(mode="python")
        values.pop("job_id")
        values.update(updates)
        provisional = Exact8KJob.model_construct(job_id="pending", **values)
        return Exact8KJob(job_id=exact_8k_job_id(provisional), **values)

    def rehashed_manifest(**updates: Any) -> Exact8KManifest:
        values = manifest.model_dump(mode="python")
        values.pop("manifest_id")
        values["jobs"] = manifest.jobs
        values.update(updates)
        provisional = Exact8KManifest.model_construct(manifest_id="pending", **values)
        return Exact8KManifest(
            manifest_id=exact_8k_manifest_id(provisional),
            **values,
        )

    def manifest_with_first_job(first_job: Exact8KJob) -> Exact8KManifest:
        return rehashed_manifest(jobs=(first_job, *manifest.jobs[1:]))

    mutations = tuple(
        sorted(
            (
                _expect_rejection(
                    "cross_artifact_client_constructed",
                    lambda: _validated_update(binding, model_client_constructed=True),
                ),
                _expect_rejection(
                    "cross_artifact_provider_call",
                    lambda: _validated_update(binding, provider_calls=1),
                ),
                _expect_rejection(
                    "cross_contract_task_lineage_rebound",
                    lambda: _build_cross_artifact_audit(
                        profile=profile,
                        task_packages=task_packages,
                        paths=paths,
                        contract=rehashed_contract(
                            task_package_ids=(
                                "finance_v26_exact_8k_task_package:unknown",
                                *contract.task_package_ids[1:],
                            )
                        ),
                        manifest=manifest,
                    ),
                ),
                _expect_rejection(
                    "cross_job_path_lineage_rebound",
                    lambda: _build_cross_artifact_audit(
                        profile=profile,
                        task_packages=task_packages,
                        paths=paths,
                        contract=contract,
                        manifest=manifest_with_first_job(
                            rehashed_job(path_audit_id="finance_v26_exact_8k_path_audit:unknown")
                        ),
                    ),
                ),
                _expect_rejection(
                    "cross_manifest_contract_lineage_rebound",
                    lambda: _build_cross_artifact_audit(
                        profile=profile,
                        task_packages=task_packages,
                        paths=paths,
                        contract=contract,
                        manifest=rehashed_manifest(
                            contract_id="finance_v26_exact_8k_completion_contract:unknown",
                        ),
                    ),
                ),
                _expect_rejection(
                    "cross_path_task_lineage_rebound",
                    lambda: _build_cross_artifact_audit(
                        profile=profile,
                        task_packages=task_packages,
                        paths=(
                            rehashed_path(
                                task_package_id="finance_v26_exact_8k_task_package:unknown"
                            ),
                            *paths[1:],
                        ),
                        contract=contract,
                        manifest=manifest,
                    ),
                ),
                _expect_rejection(
                    "cross_task_profile_hash_rebound",
                    lambda: _build_cross_artifact_audit(
                        profile=profile,
                        task_packages=(
                            rehashed_task(profile_sha256="0" * 64),
                            *task_packages[1:],
                        ),
                        paths=paths,
                        contract=contract,
                        manifest=manifest,
                    ),
                ),
                _expect_rejection(
                    "contract_candidate_changed",
                    lambda: _validated_update(contract, initial_candidate_id="changed"),
                ),
                _expect_rejection(
                    "contract_model_config_mismatch",
                    lambda: _validated_update(
                        contract,
                        model_config_id=EXPECTED_4K_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "contract_rollout_changed",
                    lambda: _validated_update(
                        contract,
                        initial_rollout_upper_bound_tokens=160001,
                    ),
                ),
                _expect_rejection(
                    "contract_runner_materialized",
                    lambda: _validated_update(
                        contract,
                        runner_implementation_materialized=True,
                    ),
                ),
                _expect_rejection(
                    "job_assignment_changed",
                    lambda: _validated_update(job, mechanism_id="changed"),
                ),
                _expect_rejection(
                    "job_model_config_mismatch",
                    lambda: _validated_update(
                        job,
                        model_config_id=EXPECTED_4K_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "job_seed_changed",
                    lambda: _validated_update(job, job_seed=job.job_seed + 1),
                ),
                _expect_rejection(
                    "manifest_fallback_job_inserted",
                    lambda: _validated_update(manifest, fallback_job_count=1),
                ),
                _expect_rejection(
                    "path_completion_changed",
                    lambda: _validated_update(path, completion_upper_bound_tokens=4096),
                ),
                _expect_rejection(
                    "path_model_config_mismatch",
                    lambda: _validated_update(
                        path,
                        model_config_id=EXPECTED_4K_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "path_predecessor_identity_reused",
                    lambda: _validated_update(
                        path,
                        audit_id=path.predecessor_path_audit_id,
                    ),
                ),
                _expect_rejection(
                    "profile_4k_completion_restored",
                    lambda: _validated_update(profile, max_output_tokens=4096),
                ),
                _expect_rejection(
                    "profile_4k_model_config_reused",
                    lambda: _validated_update(
                        profile,
                        model_config_id=EXPECTED_4K_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "profile_4k_thinking_binding_reused",
                    lambda: _validated_update(
                        profile,
                        thinking_binding_id=EXPECTED_4K_THINKING_BINDING_ID,
                    ),
                ),
                _expect_rejection(
                    "task_4k_completion_restored",
                    lambda: _validated_update(task, completion_upper_bound_tokens=4096),
                ),
                _expect_rejection(
                    "task_4k_model_config_reused",
                    lambda: _validated_update(
                        task,
                        model_config_id=EXPECTED_4K_MODEL_CONFIG_ID,
                    ),
                ),
                _expect_rejection(
                    "task_4k_thinking_binding_reused",
                    lambda: _validated_update(
                        task,
                        thinking_binding_id=EXPECTED_4K_THINKING_BINDING_ID,
                    ),
                ),
                _expect_rejection(
                    "task_predecessor_identity_reused",
                    lambda: _validated_update(
                        task,
                        task_package_id=task.predecessor_task_package_id,
                    ),
                ),
            ),
            key=lambda item: item.mutation_name,
        )
    )
    destructive_values: dict[str, Any] = {"mutation_results": mutations}
    provisional = Exact8KDestructiveAudit.model_construct(
        audit_id="pending",
        **destructive_values,
    )
    return Exact8KDestructiveAudit(
        audit_id=exact_8k_destructive_audit_id(provisional),
        **destructive_values,
    )


def _detail(path: Path, output_dir: Path, count: int) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=count,
    )


def build_thinking_8k_binding_rematerialization(
    *,
    run_id: str,
    output_dir: Path,
    package_root: Path,
) -> Exact8KRematerializationReport:
    if run_id != RUN_ID:
        raise ValueError("v26.99 run identity changed")
    source = _build_source_replay(package_root)
    profile = _build_profile_binding(package_root)
    (
        _,
        _,
        dynamic,
        predecessor_packages,
        predecessor_paths,
        predecessor_contract,
        predecessor_manifest,
    ) = _load_v26_97(package_root)
    task_packages = _build_task_packages(predecessor_packages, profile)
    paths = _build_path_audits(predecessor_paths, task_packages, profile)
    contract = _build_contract(
        source=source,
        profile=profile,
        predecessor_contract=predecessor_contract,
        dynamic=dynamic,
        task_packages=task_packages,
        paths=paths,
    )
    manifest = _build_manifest(
        predecessor_manifest=predecessor_manifest,
        contract=contract,
        task_packages=task_packages,
        paths=paths,
        profile=profile,
    )
    preservation = _build_preservation_audit(
        package_root=package_root,
        predecessor_packages=predecessor_packages,
        task_packages=task_packages,
        predecessor_paths=predecessor_paths,
        paths=paths,
        predecessor_manifest=predecessor_manifest,
        manifest=manifest,
        dynamic=dynamic,
    )
    binding = _build_cross_artifact_audit(
        profile=profile,
        task_packages=task_packages,
        paths=paths,
        contract=contract,
        manifest=manifest,
    )
    freshness = _build_freshness_audit(
        predecessor_packages=predecessor_packages,
        task_packages=task_packages,
        predecessor_paths=predecessor_paths,
        paths=paths,
        predecessor_contract=predecessor_contract,
        contract=contract,
        predecessor_manifest=predecessor_manifest,
        manifest=manifest,
    )
    destructive = _build_destructive_audit(
        profile=profile,
        task_packages=task_packages,
        paths=paths,
        contract=contract,
        manifest=manifest,
        binding=binding,
    )
    details: tuple[tuple[str, BaseModel | Sequence[BaseModel], int], ...] = (
        ("source_replay_audit.json", source, len(source.entries)),
        ("exact_8k_profile_binding.json", profile, 1),
        ("exact_8k_task_packages.json", task_packages, len(task_packages)),
        ("exact_8k_path_audits.json", paths, len(paths)),
        ("exact_8k_completion_contract.json", contract, 1),
        ("exact_8k_job_manifest.json", manifest, len(manifest.jobs)),
        (
            "design_preservation_audit.json",
            preservation,
            len(preservation.task_package_rows)
            + len(preservation.path_rows)
            + len(preservation.job_rows),
        ),
        ("cross_artifact_binding_audit.json", binding, len(binding.rows)),
        ("freshness_audit.json", freshness, 1),
        (
            "destructive_preflight_audit.json",
            destructive,
            len(destructive.mutation_results),
        ),
    )
    for name, payload, _ in details:
        if isinstance(payload, BaseModel):
            value: Any = payload.model_dump(mode="json")
        else:
            value = [item.model_dump(mode="json") for item in payload]
        _write_json(output_dir / name, value)
    detail_files = tuple(
        _detail(output_dir / name, output_dir, count) for name, _, count in sorted(details)
    )
    report_values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "profile_binding_audit_id": profile.binding_audit_id,
        "completion_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "preservation_audit_id": preservation.audit_id,
        "cross_artifact_binding_audit_id": binding.audit_id,
        "freshness_audit_id": freshness.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "detail_files": detail_files,
    }
    provisional_report = Exact8KRematerializationReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = Exact8KRematerializationReport(
        report_id=exact_8k_report_id(provisional_report),
        **report_values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the v26.99 exact 8K execution-binding rematerialization"
    )
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_thinking_8k_binding_rematerialization(
        run_id=args.run_id,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
