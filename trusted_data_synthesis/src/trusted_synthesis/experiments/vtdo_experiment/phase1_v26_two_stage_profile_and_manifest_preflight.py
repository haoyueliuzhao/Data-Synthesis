from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    ActionConstructibilityFixtureAudit,
    ActionConstructibilityPreflightReport,
    ActionConstructibilityProtocol,
    _path_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    SourceReplayAudit as V26107SourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay_v3 import (  # noqa: E501
    AuthorityPreservingReplayV3Contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_binding_and_usage_semantics import (  # noqa: E501
    Exact16KJob,
    Exact16KManifest,
    Exact16KPathAudit,
    Exact16KTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_execution import (  # noqa: E501
    load_static_inputs,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    DECISION_COMMIT_VERSION,
    build_public_action_state,
    render_action_constructible_decision_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    bind_prospective_thinking,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_108_two_stage_profile_and_manifest_preflight_v1_20260822"
NEXT_STAGE: Final = "two_stage_semantic_proposal_runner_preflight_only"
PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
PROFILE_SHA256: Final = "2043fac92b0ef286c368091eb2ec424489dd94e5b6bdf5954810ecdca403615f"
MODEL_CONFIG_ID: Final = (
    "agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015"
)
THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8"
)
THINKING_POLICY_ID: Final = (
    "prospective_thinking_mode_policy:"
    "b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f"
)
V26_107_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822"
)
EXPECTED_V26_107_REPORT_ID: Final = (
    "finance_v26_action_constructibility_preflight_report:"
    "ff0eb5409a770fb72381f93a83fff3726fa8f547d994796f247682c9f0516e19"
)
EXPECTED_PROTOCOL_ID: Final = (
    "finance_v26_action_constructibility_protocol:"
    "4044cdfbb3aa6526c5a9f8cc608a745ec55f3151cbd5e79a8e5af575737851e0"
)
EXPECTED_FIXTURE_ID: Final = (
    "finance_v26_action_constructibility_fixture:"
    "9b522aea28428f77261c5443da0b835f104f66f30506a0ba9847a847f1a04481"
)
EXPECTED_VERIFIER_V3_ID: Final = (
    "finance_v26_authority_verifier_contract_v3:"
    "478f7b6cd880f68865d94046bd66ff6e339f03814dec2b94f27d93d0a32bacfa"
)
STAGE_TWO_SOURCE_PATH: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_action_constructibility.py"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_two_stage_profile_and_manifest_preflight.py"
)
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_109_two_stage_semantic_proposal_runner_preflight_v1_20260822"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_110_two_stage_semantic_proposal_calibration_execution_v1_20260822"
)
V26_107_OUTPUTS: Final = (
    "action_constructibility_fixture_audit.json",
    "action_constructibility_protocol.json",
    "destructive_preflight_audit.json",
    "failure_taxonomy_audit.json",
    "final_rescue_semantic_audit.json",
    "historical_action_interface_audit.json",
    "report.json",
    "source_replay_audit.json",
    "verifier_v3_contract.json",
    "verifier_v3_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


SourceKind = Literal[
    "v26_107_transitive_source",
    "v26_107_output",
    "v26_108_profile",
    "v26_108_implementation",
]


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: SourceKind
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> SourceReplayEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("v26.108 source replay changed")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=1884, max_length=1884)
    predecessor_transitive_file_count: Literal[1872] = 1872
    predecessor_output_file_count: Literal[10] = 10
    profile_file_count: Literal[1] = 1
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[1884] = 1884
    replay_pass_count: Literal[1884] = 1884
    replay_before_profile_parsing: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_source_replay.v1"] = (
        "finance_v26_two_stage_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.108 source replay paths are not canonical")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("v26.108 source replay identity changed")
        return self


class StageOneThinkingProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    predecessor_protocol_id: str = EXPECTED_PROTOCOL_ID
    profile_relative_path: str = PROFILE_PATH
    profile_sha256: str = PROFILE_SHA256
    model_config_id: str = MODEL_CONFIG_ID
    thinking_policy_id: str = THINKING_POLICY_ID
    thinking_binding_id: str = THINKING_BINDING_ID
    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    max_output_tokens: Literal[16384] = 16384
    thinking_type: Literal["enabled"] = "enabled"
    response_format_type: Literal["json_object"] = "json_object"
    maximum_model_attempts: Literal[1] = 1
    generic_contract_repair_attempts: Literal[0] = 0
    fallback_model_count: Literal[0] = 0
    model_discovery_enabled: Literal[False] = False
    exact_requested_model_required: Literal[True] = True
    stage_one_owns_semantic_proposal: Literal[True] = True
    stage_one_owns_final_answer: Literal[True] = True
    private_reasoning_cross_stage_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_stage_one_thinking_profile.v1"] = (
        "finance_v26_stage_one_thinking_profile.v1"
    )

    @model_validator(mode="after")
    def validate_profile(self) -> StageOneThinkingProfile:
        if (
            self.profile_sha256 != PROFILE_SHA256
            or self.model_config_id != MODEL_CONFIG_ID
            or self.thinking_binding_id != THINKING_BINDING_ID
        ):
            raise ValueError("v26.108 Stage 1 profile binding changed")
        if self.profile_id != stage_one_profile_id(self):
            raise ValueError("v26.108 Stage 1 profile identity changed")
        return self


class StageTwoCommitProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    predecessor_protocol_id: str = EXPECTED_PROTOCOL_ID
    commit_schema_version: str = DECISION_COMMIT_VERSION
    compiler_source_relative_path: str = STAGE_TWO_SOURCE_PATH
    compiler_source_sha256: str = Field(min_length=64, max_length=64)
    deterministic_commit_only: Literal[True] = True
    reversible_mapping_required: Literal[True] = True
    compiler_may_choose_semantic_field: Literal[False] = False
    provider_profile_present: Literal[False] = False
    provider_call_upper_bound: Literal[0] = 0
    private_reasoning_input_allowed: Literal[False] = False
    schema_version: Literal["finance_v26_stage_two_commit_profile.v1"] = (
        "finance_v26_stage_two_commit_profile.v1"
    )

    @model_validator(mode="after")
    def validate_profile(self) -> StageTwoCommitProfile:
        if self.profile_id != stage_two_profile_id(self):
            raise ValueError("v26.108 Stage 2 profile identity changed")
        return self


class TwoStageResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_107_REPORT_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    accounted_completion_bound_tokens: Literal[16385] = 16385
    prompt_upper_bound_bytes: Literal[60000] = 60000
    rescue_prompt_upper_bound_bytes: Literal[6144] = 6144
    chat_envelope_tokens: Literal[256] = 256
    rollout_upper_bound_tokens: Literal[260000] = 260000
    maximum_primary_stage_one_requests: Literal[10] = 10
    maximum_rescue_calls_per_job: Literal[1] = 1
    maximum_stage_one_provider_calls: Literal[11] = 11
    maximum_stage_two_provider_calls: Literal[0] = 0
    final_answer_request_reserve_required: Literal[True] = True
    rescue_reserve_required_until_consumed: Literal[True] = True
    actual_provider_usage_charged_without_clipping: Literal[True] = True
    one_token_margin_accounting_only: Literal[True] = True
    one_token_margin_cannot_rescue_length_failure: Literal[True] = True
    two_or_more_excess_tokens_instrument_failure: Literal[True] = True
    denied_request_provider_call_count: Literal[0] = 0
    static_bound_derived_from_complete_compiler_paths: Literal[True] = True
    historical_v26_105_deficit_used_to_select_bound: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_resource_contract.v1"] = (
        "finance_v26_two_stage_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> TwoStageResourceContract:
        if self.accounted_completion_bound_tokens != (
            self.exact_request_completion_bound_tokens + self.provider_accounting_margin_tokens
        ):
            raise ValueError("v26.108 accounted Completion bound changed")
        if self.maximum_stage_one_provider_calls != (
            self.maximum_primary_stage_one_requests + self.maximum_rescue_calls_per_job
        ):
            raise ValueError("v26.108 Stage 1 call ceiling changed")
        if self.contract_id != two_stage_resource_contract_id(self):
            raise ValueError("v26.108 resource Contract identity changed")
        return self


class TwoStageTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    compact_prompt_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    action_constructibility_protocol_id: str = EXPECTED_PROTOCOL_ID
    verifier_v3_contract_id: str = EXPECTED_VERIFIER_V3_ID
    resource_contract_id: str = Field(min_length=1)
    source_model_exposed_before_freeze: Literal[True] = True
    source_claimed_fresh: Literal[False] = False
    engineering_calibration_only: Literal[True] = True
    capability_support_eligible: Literal[False] = False
    reachability_support_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_task_package.v1"] = (
        "finance_v26_two_stage_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> TwoStageTaskPackage:
        if self.task_package_id != two_stage_task_package_id(self):
            raise ValueError("v26.108 TaskPackage identity changed")
        return self


class TwoStagePathAudit(FrozenModel):
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal[
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    ]
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    compiler_tool_call_count: int = Field(gt=0)
    semantic_proposal_request_count: int = Field(gt=0)
    final_answer_request_count: Literal[1] = 1
    primary_stage_one_request_count: int = Field(gt=0, le=10)
    maximum_stage_one_provider_calls_with_rescue: int = Field(gt=0, le=11)
    stage_two_commit_count: int = Field(gt=0)
    stage_two_provider_call_count: Literal[0] = 0
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    rescue_prompt_upper_bound_bytes: Literal[6144] = 6144
    static_complete_path_upper_bound_tokens: int = Field(gt=0, le=260000)
    static_rollout_headroom_tokens: int = Field(ge=0)
    prompt_ceiling_passed: Literal[True] = True
    rollout_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_two_stage_path_audit.v1"] = (
        "finance_v26_two_stage_path_audit.v1"
    )

    @model_validator(mode="after")
    def validate_path(self) -> TwoStagePathAudit:
        if (
            self.semantic_proposal_request_count != self.compiler_tool_call_count + 1
            or self.primary_stage_one_request_count
            != self.semantic_proposal_request_count + self.final_answer_request_count
            or self.stage_two_commit_count != self.semantic_proposal_request_count
            or self.maximum_stage_one_provider_calls_with_rescue
            != self.primary_stage_one_request_count + 1
            or self.static_rollout_headroom_tokens
            != 260000 - self.static_complete_path_upper_bound_tokens
        ):
            raise ValueError("v26.108 Path request or resource arithmetic changed")
        if self.path_audit_id != two_stage_path_audit_id(self):
            raise ValueError("v26.108 Path identity changed")
        return self


class TwoStageExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_107_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    action_constructibility_protocol_id: str = EXPECTED_PROTOCOL_ID
    verifier_v3_contract_id: str = EXPECTED_VERIFIER_V3_ID
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    exact_job_denominator: Literal[32] = 32
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    stage_one_request_kinds: tuple[str, str] = ("semantic_proposal", "final_answer")
    stage_two_request_kind: Literal["deterministic_commit"] = "deterministic_commit"
    stage_two_provider_calls: Literal[0] = 0
    one_global_rescue: Literal[True] = True
    semantic_compile_rejection_is_model_result: Literal[True] = True
    response_serialization_failure_is_model_result: Literal[True] = True
    decision_phase_failure_is_model_result: Literal[True] = True
    prompt_echo_is_model_result: Literal[True] = True
    duplicate_failed_proposal_is_model_result: Literal[True] = True
    unknown_tool_typed_failure_is_runtime_result: Literal[True] = True
    raw_provider_persisted_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_execution_contract.v1"] = (
        "finance_v26_two_stage_execution_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> TwoStageExecutionContract:
        if len(set(self.task_package_ids)) != 24 or len(set(self.path_audit_ids)) != 48:
            raise ValueError("v26.108 Contract denominator changed")
        if self.contract_id != two_stage_execution_contract_id(self):
            raise ValueError("v26.108 execution Contract identity changed")
        return self


class TwoStageJob(FrozenModel):
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
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    source_repeated_for_engineering_calibration: Literal[True] = True
    schema_version: Literal["finance_v26_two_stage_job.v1"] = "finance_v26_two_stage_job.v1"

    @model_validator(mode="after")
    def validate_job(self) -> TwoStageJob:
        if self.job_id != two_stage_job_id(self):
            raise ValueError("v26.108 Job identity changed")
        return self


class TwoStageManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    jobs: tuple[TwoStageJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    exact_denominator: Literal[32] = 32
    predecessor_job_identity_overlap_count: Literal[0] = 0
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_two_stage_manifest.v1"] = (
        "finance_v26_two_stage_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> TwoStageManifest:
        if (
            len({item.job_id for item in self.jobs}) != 32
            or len({item.task_package_id for item in self.jobs}) != 24
        ):
            raise ValueError("v26.108 Manifest denominator changed")
        if self.manifest_id != two_stage_manifest_id(self):
            raise ValueError("v26.108 Manifest identity changed")
        return self


class DesignPreservationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_semantic_projection_pass_count: Literal[24] = 24
    path_strategy_and_compiler_projection_pass_count: Literal[48] = 48
    job_assignment_and_seed_projection_pass_count: Literal[32] = 32
    source_task_count: Literal[24] = 24
    source_model_exposed_count: Literal[24] = 24
    source_claimed_fresh_count: Literal[0] = 0
    task_package_identity_overlap_count: Literal[0] = 0
    path_identity_overlap_count: Literal[0] = 0
    job_identity_overlap_count: Literal[0] = 0
    selection_changed: Literal[False] = False
    seed_changed: Literal[False] = False
    path_assignment_changed: Literal[False] = False
    empirical_outcomes_used: Literal[False] = False
    role_or_state_evidence_eligible_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_design_preservation.v1"] = (
        "finance_v26_two_stage_design_preservation.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DesignPreservationAudit:
        if self.audit_id != design_preservation_audit_id(self):
            raise ValueError("v26.108 design-preservation identity changed")
        return self


class CrossArtifactBindingRow(FrozenModel):
    entity_kind: Literal["task_package", "path", "job"]
    entity_id: str = Field(min_length=1)
    parent_ids: tuple[str, ...] = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    passed: Literal[True] = True


class CrossArtifactBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[CrossArtifactBindingRow, ...] = Field(min_length=104, max_length=104)
    task_package_row_count: Literal[24] = 24
    path_row_count: Literal[48] = 48
    job_row_count: Literal[32] = 32
    passed_row_count: Literal[104] = 104
    manifest_contract_binding_passed: Literal[True] = True
    all_parent_memberships_closed: Literal[True] = True
    static_execution_identity_chain_closed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_cross_artifact_binding.v1"] = (
        "finance_v26_two_stage_cross_artifact_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CrossArtifactBindingAudit:
        if tuple(item.entity_id for item in self.rows) != tuple(
            sorted({item.entity_id for item in self.rows})
        ):
            raise ValueError("v26.108 cross-artifact rows are not canonical")
        if self.audit_id != cross_artifact_binding_audit_id(self):
            raise ValueError("v26.108 cross-artifact identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("v26.108 mutation identity changed")
        return self


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    rejected_mutation_count: Literal[30] = 30
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_two_stage_static_destructive.v1"] = (
        "finance_v26_two_stage_static_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("v26.108 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class TwoStageStaticPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_V26_107_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    design_preservation_audit_id: str = Field(min_length=1)
    cross_artifact_binding_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=11, max_length=11)
    status: Literal["static_binding_passed_runner_not_preflighted"] = (
        "static_binding_passed_runner_not_preflighted"
    )
    next_permitted_stage: str = NEXT_STAGE
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    runner_implemented: Literal[False] = False
    execution_authorized: Literal[False] = False
    single_stage_32k_allowed: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_two_stage_static_preflight_report.v1"] = (
        "finance_v26_two_stage_static_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> TwoStageStaticPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.108 report details are not canonical")
        if self.report_id != two_stage_static_report_id(self):
            raise ValueError("v26.108 report identity changed")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def source_replay_audit_id(value: SourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_source_replay:")


def stage_one_profile_id(value: StageOneThinkingProfile) -> str:
    return _identity(value, "profile_id", "finance_v26_stage_one_thinking_profile:")


def stage_two_profile_id(value: StageTwoCommitProfile) -> str:
    return _identity(value, "profile_id", "finance_v26_stage_two_commit_profile:")


def two_stage_resource_contract_id(value: TwoStageResourceContract) -> str:
    return _identity(value, "contract_id", "finance_v26_two_stage_resource_contract:")


def two_stage_task_package_id(value: TwoStageTaskPackage) -> str:
    return _identity(value, "task_package_id", "finance_v26_two_stage_task_package:")


def two_stage_path_audit_id(value: TwoStagePathAudit) -> str:
    return _identity(value, "path_audit_id", "finance_v26_two_stage_path_audit:")


def two_stage_execution_contract_id(value: TwoStageExecutionContract) -> str:
    return _identity(value, "contract_id", "finance_v26_two_stage_execution_contract:")


def two_stage_job_id(value: TwoStageJob) -> str:
    return _identity(value, "job_id", "finance_v26_two_stage_job:")


def two_stage_manifest_id(value: TwoStageManifest) -> str:
    return _identity(value, "manifest_id", "finance_v26_two_stage_manifest:")


def design_preservation_audit_id(value: DesignPreservationAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_design_preservation:")


def cross_artifact_binding_audit_id(value: CrossArtifactBindingAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_cross_artifact_binding:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_two_stage_static_mutation:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_two_stage_static_destructive:")


def two_stage_static_report_id(value: TwoStageStaticPreflightReport) -> str:
    return _identity(value, "report_id", "finance_v26_two_stage_static_preflight_report:")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    value = _jsonable(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    payload = _canonical_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable v26.108 output changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _load_predecessor(
    package_root: Path,
) -> tuple[
    ActionConstructibilityPreflightReport,
    V26107SourceReplayAudit,
    ActionConstructibilityProtocol,
    ActionConstructibilityFixtureAudit,
    AuthorityPreservingReplayV3Contract,
]:
    directory = package_root / V26_107_DIR
    report = ActionConstructibilityPreflightReport.model_validate(
        _load_json(directory / "report.json")
    )
    replay = V26107SourceReplayAudit.model_validate(
        _load_json(directory / "source_replay_audit.json")
    )
    protocol = ActionConstructibilityProtocol.model_validate(
        _load_json(directory / "action_constructibility_protocol.json")
    )
    fixture = ActionConstructibilityFixtureAudit.model_validate(
        _load_json(directory / "action_constructibility_fixture_audit.json")
    )
    verifier = AuthorityPreservingReplayV3Contract.model_validate(
        _load_json(directory / "verifier_v3_contract.json")
    )
    if (
        report.report_id != EXPECTED_V26_107_REPORT_ID
        or report.source_replay_audit_id != replay.audit_id
        or report.action_constructibility_protocol_id != protocol.protocol_id
        or report.action_constructibility_fixture_audit_id != fixture.audit_id
        or report.verifier_v3_contract_id != verifier.contract_id
        or protocol.protocol_id != EXPECTED_PROTOCOL_ID
        or fixture.audit_id != EXPECTED_FIXTURE_ID
        or verifier.contract_id != EXPECTED_VERIFIER_V3_ID
        or report.next_permitted_stage
        != "fresh_two_stage_profiles_taskpackage_contract_manifest_and_runner_preflight_only"
        or report.model_api_calls != 0
    ):
        raise ValueError("v26.108 predecessor authorization changed")
    return report, replay, protocol, fixture, verifier


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
    predecessor: V26107SourceReplayAudit,
) -> SourceReplayAudit:
    rows: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = package_root / item.relative_path
        rows[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_107_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    for name in V26_107_OUTPUTS:
        relative = f"{V26_107_DIR}/{name}"
        path = package_root / relative
        digest = _sha256(path)
        rows[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_107_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    for relative, kind in (
        (PROFILE_PATH, "v26_108_profile"),
        (IMPLEMENTATION_PATH, "v26_108_implementation"),
    ):
        path = implementation_root / relative
        digest = _sha256(path)
        rows[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind=cast(SourceKind, kind),
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    values = {
        "predecessor_source_replay_id": predecessor.audit_id,
        "entries": tuple(rows[key] for key in sorted(rows)),
    }
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(audit_id=source_replay_audit_id(provisional), **values)


def _load_stage_one_config(implementation_root: Path) -> AgentModelConfig:
    path = implementation_root / PROFILE_PATH
    if _sha256(path) != PROFILE_SHA256:
        raise ValueError("v26.108 Stage 1 Profile bytes changed")
    raw = _load_json(path)
    if not isinstance(raw, Mapping) or not isinstance(raw.get("model"), Mapping):
        raise ValueError("v26.108 Stage 1 Profile payload changed")
    config = AgentModelConfig.model_validate(raw["model"])
    binding = bind_prospective_thinking(config)
    if (
        config.public_manifest_hash != MODEL_CONFIG_ID
        or binding.binding_id != THINKING_BINDING_ID
        or config.max_output_tokens != 16384
        or config.auto_discover_models
        or config.contract_repair_attempts != 0
        or config.maximum_model_attempts != 1
        or config.fallback_models
        or not config.require_requested_model
        or config.request_body_overrides.get("thinking") != {"type": "enabled"}
    ):
        raise ValueError("v26.108 Stage 1 Profile route changed")
    return config


def _build_profiles(
    implementation_root: Path,
) -> tuple[StageOneThinkingProfile, StageTwoCommitProfile]:
    _load_stage_one_config(implementation_root)
    stage_one_provisional = StageOneThinkingProfile.model_construct(profile_id="pending")
    stage_one = StageOneThinkingProfile(profile_id=stage_one_profile_id(stage_one_provisional))
    source = implementation_root / STAGE_TWO_SOURCE_PATH
    values = {"compiler_source_sha256": _sha256(source)}
    stage_two_provisional = StageTwoCommitProfile.model_construct(
        profile_id="pending",
        **values,
    )
    stage_two = StageTwoCommitProfile(
        profile_id=stage_two_profile_id(stage_two_provisional),
        **values,
    )
    return stage_one, stage_two


def _build_resource(
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
) -> TwoStageResourceContract:
    values = {
        "stage_one_profile_id": stage_one.profile_id,
        "stage_two_profile_id": stage_two.profile_id,
    }
    provisional = TwoStageResourceContract.model_construct(
        contract_id="pending",
        **values,
    )
    return TwoStageResourceContract(
        contract_id=two_stage_resource_contract_id(provisional),
        **values,
    )


def _build_task_packages(
    predecessor: Sequence[Exact16KTaskPackage],
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
) -> tuple[TwoStageTaskPackage, ...]:
    rows = []
    for item in predecessor:
        values = {
            "predecessor_task_package_id": item.task_package_id,
            "source_task_artifact_id": item.source_task_artifact_id,
            "source_role": item.source_role,
            "mechanism_id": item.mechanism_id,
            "operational_record_id": item.operational_record_id,
            "operational_task_package_id": item.operational_task_package_id,
            "environment_manifest_id": item.environment_manifest_id,
            "semantic_source_id": item.semantic_source_id,
            "compact_prompt_contract_id": item.compact_prompt_contract_id,
            "stage_one_profile_id": stage_one.profile_id,
            "stage_two_profile_id": stage_two.profile_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = TwoStageTaskPackage.model_construct(
            task_package_id="pending",
            **values,
        )
        rows.append(
            TwoStageTaskPackage(
                task_package_id=two_stage_task_package_id(provisional),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.task_package_id))


def _path_prompts(static: Any, path: Exact16KPathAudit) -> tuple[str, ...]:
    binding = _path_binding(static, path)
    observations: list[AgentToolObservation] = []
    prompts = []
    condition = (
        None if binding.source_path.role == "capability" else binding.source_path.path_strategy_id
    )
    for step in binding.compiler_trajectory.steps:
        if step.tool_name is None:
            continue
        state = build_public_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
        )
        prompts.append(
            render_action_constructible_decision_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
            )
        )
        observations.append(AgentToolObservation.model_validate(step.observation))
    final_state = build_public_action_state(
        binding.record.task_package.task.public,
        binding.environment,
        tuple(observations),
    )
    if not final_state.final_answer_allowed:
        raise ValueError("v26.108 Compiler Path did not reach Final Ready")
    prompts.append(
        render_action_constructible_decision_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=final_state,
            public_path_condition=condition,
        )
    )
    prompts.append(
        render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
    )
    return tuple(prompts)


def _build_paths(
    static: Any,
    tasks: Sequence[TwoStageTaskPackage],
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
) -> tuple[TwoStagePathAudit, ...]:
    task_map = {item.predecessor_task_package_id: item for item in tasks}
    rows = []
    for item in static.path_audits:
        binding = _path_binding(static, item)
        prompts = _path_prompts(static, item)
        compiler_calls = sum(
            step.tool_name is not None for step in binding.compiler_trajectory.steps
        )
        primary_requests = len(prompts)
        upper = sum(
            len(prompt.encode("utf-8"))
            + resource.chat_envelope_tokens
            + resource.accounted_completion_bound_tokens
            for prompt in prompts
        )
        upper += (
            resource.rescue_prompt_upper_bound_bytes
            + resource.chat_envelope_tokens
            + resource.accounted_completion_bound_tokens
        )
        task = task_map[item.task_package_id]
        values = {
            "predecessor_path_audit_id": item.audit_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": item.task_package_id,
            "compiler_trajectory_id": binding.compiler_trajectory.trajectory_id,
            "role": item.role,
            "mechanism_id": item.mechanism_id,
            "path_strategy_id": item.path_strategy_id,
            "stage_one_profile_id": stage_one.profile_id,
            "stage_two_profile_id": stage_two.profile_id,
            "resource_contract_id": resource.contract_id,
            "compiler_tool_call_count": compiler_calls,
            "semantic_proposal_request_count": compiler_calls + 1,
            "primary_stage_one_request_count": primary_requests,
            "maximum_stage_one_provider_calls_with_rescue": primary_requests + 1,
            "stage_two_commit_count": compiler_calls + 1,
            "maximum_primary_prompt_utf8_bytes": max(
                len(prompt.encode("utf-8")) for prompt in prompts
            ),
            "static_complete_path_upper_bound_tokens": upper,
            "static_rollout_headroom_tokens": resource.rollout_upper_bound_tokens - upper,
        }
        provisional = TwoStagePathAudit.model_construct(
            path_audit_id="pending",
            **values,
        )
        rows.append(
            TwoStagePathAudit(
                path_audit_id=two_stage_path_audit_id(provisional),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.path_audit_id))


def _build_contract(
    replay: SourceReplayAudit,
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
) -> TwoStageExecutionContract:
    values = {
        "source_replay_audit_id": replay.audit_id,
        "stage_one_profile_id": stage_one.profile_id,
        "stage_two_profile_id": stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in tasks)),
        "path_audit_ids": tuple(sorted(item.path_audit_id for item in paths)),
    }
    provisional = TwoStageExecutionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return TwoStageExecutionContract(
        contract_id=two_stage_execution_contract_id(provisional),
        **values,
    )


def _build_jobs(
    predecessor: Exact16KManifest,
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    contract: TwoStageExecutionContract,
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
) -> tuple[TwoStageJob, ...]:
    task_map = {item.predecessor_task_package_id: item for item in tasks}
    path_map = {item.predecessor_path_audit_id: item for item in paths}
    rows = []
    for item in predecessor.jobs:
        task = task_map[item.task_package_id]
        path = path_map[item.path_audit_id]
        values = {
            "predecessor_job_id": item.job_id,
            "contract_id": contract.contract_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": item.task_package_id,
            "path_audit_id": path.path_audit_id,
            "predecessor_path_audit_id": item.path_audit_id,
            "source_task_artifact_id": item.source_task_artifact_id,
            "mechanism_id": item.mechanism_id,
            "path_strategy_id": item.path_strategy_id,
            "source_role": item.source_role,
            "job_seed": item.job_seed,
            "stage_one_profile_id": stage_one.profile_id,
            "stage_two_profile_id": stage_two.profile_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = TwoStageJob.model_construct(job_id="pending", **values)
        rows.append(
            TwoStageJob(
                job_id=two_stage_job_id(provisional),
                **values,
            )
        )
    return tuple(rows)


def _build_manifest(
    predecessor: Exact16KManifest,
    jobs: Sequence[TwoStageJob],
    contract: TwoStageExecutionContract,
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
) -> TwoStageManifest:
    mechanism = Counter(item.mechanism_id for item in jobs)
    path = Counter(item.path_strategy_id for item in jobs)
    cells = Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in jobs)
    values = {
        "contract_id": contract.contract_id,
        "stage_one_profile_id": stage_one.profile_id,
        "stage_two_profile_id": stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "jobs": tuple(jobs),
        "mechanism_job_counts": dict(sorted(mechanism.items())),
        "path_job_counts": dict(sorted(path.items())),
        "cell_job_counts": dict(sorted(cells.items())),
        "predecessor_job_identity_overlap_count": len(
            {item.job_id for item in jobs} & {item.job_id for item in predecessor.jobs}
        ),
    }
    provisional = TwoStageManifest.model_construct(manifest_id="pending", **values)
    return TwoStageManifest(
        manifest_id=two_stage_manifest_id(provisional),
        **values,
    )


def _build_design_audit(
    predecessor_tasks: Sequence[Exact16KTaskPackage],
    predecessor_paths: Sequence[Exact16KPathAudit],
    predecessor_jobs: Sequence[Exact16KJob],
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    jobs: Sequence[TwoStageJob],
) -> DesignPreservationAudit:
    task_map = {item.task_package_id: item for item in predecessor_tasks}
    path_map = {item.audit_id: item for item in predecessor_paths}
    job_map = {item.job_id: item for item in predecessor_jobs}
    task_pass = sum(
        (
            item.source_task_artifact_id,
            item.source_role,
            item.mechanism_id,
            item.operational_record_id,
            item.operational_task_package_id,
            item.environment_manifest_id,
            item.semantic_source_id,
            item.compact_prompt_contract_id,
        )
        == (
            task_map[item.predecessor_task_package_id].source_task_artifact_id,
            task_map[item.predecessor_task_package_id].source_role,
            task_map[item.predecessor_task_package_id].mechanism_id,
            task_map[item.predecessor_task_package_id].operational_record_id,
            task_map[item.predecessor_task_package_id].operational_task_package_id,
            task_map[item.predecessor_task_package_id].environment_manifest_id,
            task_map[item.predecessor_task_package_id].semantic_source_id,
            task_map[item.predecessor_task_package_id].compact_prompt_contract_id,
        )
        for item in tasks
    )
    path_pass = sum(
        (
            item.role,
            item.mechanism_id,
            item.path_strategy_id,
        )
        == (
            path_map[item.predecessor_path_audit_id].role,
            path_map[item.predecessor_path_audit_id].mechanism_id,
            path_map[item.predecessor_path_audit_id].path_strategy_id,
        )
        for item in paths
    )
    job_pass = sum(
        (
            item.mechanism_id,
            item.path_strategy_id,
            item.source_role,
            item.job_seed,
        )
        == (
            job_map[item.predecessor_job_id].mechanism_id,
            job_map[item.predecessor_job_id].path_strategy_id,
            job_map[item.predecessor_job_id].source_role,
            job_map[item.predecessor_job_id].job_seed,
        )
        for item in jobs
    )
    values = {
        "task_semantic_projection_pass_count": task_pass,
        "path_strategy_and_compiler_projection_pass_count": path_pass,
        "job_assignment_and_seed_projection_pass_count": job_pass,
        "task_package_identity_overlap_count": len(
            {item.task_package_id for item in tasks}
            & {item.task_package_id for item in predecessor_tasks}
        ),
        "path_identity_overlap_count": len(
            {item.path_audit_id for item in paths} & {item.audit_id for item in predecessor_paths}
        ),
        "job_identity_overlap_count": len(
            {item.job_id for item in jobs} & {item.job_id for item in predecessor_jobs}
        ),
    }
    provisional = DesignPreservationAudit.model_construct(audit_id="pending", **values)
    return DesignPreservationAudit(
        audit_id=design_preservation_audit_id(provisional),
        **values,
    )


def _build_cross_audit(
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    jobs: Sequence[TwoStageJob],
    contract: TwoStageExecutionContract,
    manifest: TwoStageManifest,
) -> CrossArtifactBindingAudit:
    if (
        manifest.contract_id != contract.contract_id
        or manifest.stage_one_profile_id != contract.stage_one_profile_id
        or manifest.stage_two_profile_id != contract.stage_two_profile_id
        or manifest.resource_contract_id != contract.resource_contract_id
    ):
        raise ValueError("v26.108 Manifest parent binding changed")
    task_ids = set(contract.task_package_ids)
    path_ids = set(contract.path_audit_ids)
    rows: list[CrossArtifactBindingRow] = []
    for item in tasks:
        if item.task_package_id not in task_ids:
            raise ValueError("v26.108 TaskPackage absent from Contract")
        rows.append(
            CrossArtifactBindingRow(
                entity_kind="task_package",
                entity_id=item.task_package_id,
                parent_ids=(item.predecessor_task_package_id,),
                stage_one_profile_id=item.stage_one_profile_id,
                stage_two_profile_id=item.stage_two_profile_id,
                resource_contract_id=item.resource_contract_id,
            )
        )
    for item in paths:
        if item.path_audit_id not in path_ids or item.task_package_id not in task_ids:
            raise ValueError("v26.108 Path parent membership changed")
        rows.append(
            CrossArtifactBindingRow(
                entity_kind="path",
                entity_id=item.path_audit_id,
                parent_ids=(item.task_package_id, item.predecessor_path_audit_id),
                stage_one_profile_id=item.stage_one_profile_id,
                stage_two_profile_id=item.stage_two_profile_id,
                resource_contract_id=item.resource_contract_id,
            )
        )
    manifest_ids = {item.job_id for item in manifest.jobs}
    for item in jobs:
        if (
            item.job_id not in manifest_ids
            or item.contract_id != contract.contract_id
            or item.task_package_id not in task_ids
            or item.path_audit_id not in path_ids
        ):
            raise ValueError("v26.108 Job parent membership changed")
        rows.append(
            CrossArtifactBindingRow(
                entity_kind="job",
                entity_id=item.job_id,
                parent_ids=(
                    item.contract_id,
                    item.task_package_id,
                    item.path_audit_id,
                    item.predecessor_job_id,
                ),
                stage_one_profile_id=item.stage_one_profile_id,
                stage_two_profile_id=item.stage_two_profile_id,
                resource_contract_id=item.resource_contract_id,
            )
        )
    values = {"rows": tuple(sorted(rows, key=lambda item: item.entity_id))}
    provisional = CrossArtifactBindingAudit.model_construct(audit_id="pending", **values)
    return CrossArtifactBindingAudit(
        audit_id=cross_artifact_binding_audit_id(provisional),
        **values,
    )


def _expect_rejection(name: str, function: Callable[[], Any]) -> MutationResult:
    try:
        function()
    except (ValueError, KeyError, TypeError):
        provisional = MutationResult.model_construct(
            mutation_id="pending",
            mutation=name,
        )
        return MutationResult(
            mutation_id=mutation_result_id(provisional),
            mutation=name,
        )
    raise AssertionError(f"v26.108 mutation passed: {name}")


def _rehash(model: BaseModel, field: str, identity: Callable[[Any], str], **updates: Any) -> Any:
    provisional = model.model_copy(update={field: "pending", **updates})
    payload = model.model_dump(mode="python")
    payload.update(updates)
    payload[field] = identity(provisional)
    return type(model).model_validate(payload)


def _build_destructive(
    replay: SourceReplayAudit,
    stage_one: StageOneThinkingProfile,
    stage_two: StageTwoCommitProfile,
    resource: TwoStageResourceContract,
    tasks: Sequence[TwoStageTaskPackage],
    paths: Sequence[TwoStagePathAudit],
    contract: TwoStageExecutionContract,
    jobs: Sequence[TwoStageJob],
    manifest: TwoStageManifest,
) -> DestructivePreflightAudit:
    task = tasks[0]
    path = next(item for item in paths if item.task_package_id == task.task_package_id)
    job = next(item for item in jobs if item.task_package_id == task.task_package_id)
    cases: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "stale_source_replay_identity",
            lambda: SourceReplayAudit.model_validate(
                {**replay.model_dump(mode="json"), "audit_id": "changed"}
            ),
        ),
        (
            "changed_stage_one_profile_sha",
            lambda: StageOneThinkingProfile.model_validate(
                {**stage_one.model_dump(mode="json"), "profile_sha256": "0" * 64}
            ),
        ),
        (
            "stage_one_thinking_disabled",
            lambda: StageOneThinkingProfile.model_validate(
                {**stage_one.model_dump(mode="json"), "thinking_type": "disabled"}
            ),
        ),
        (
            "stage_one_model_discovery_enabled",
            lambda: StageOneThinkingProfile.model_validate(
                {**stage_one.model_dump(mode="json"), "model_discovery_enabled": True}
            ),
        ),
        (
            "stage_one_generic_repair_enabled",
            lambda: StageOneThinkingProfile.model_validate(
                {**stage_one.model_dump(mode="json"), "generic_contract_repair_attempts": 1}
            ),
        ),
        (
            "stage_two_provider_profile_added",
            lambda: StageTwoCommitProfile.model_validate(
                {**stage_two.model_dump(mode="json"), "provider_profile_present": True}
            ),
        ),
        (
            "stage_two_provider_call_added",
            lambda: StageTwoCommitProfile.model_validate(
                {**stage_two.model_dump(mode="json"), "provider_call_upper_bound": 1}
            ),
        ),
        (
            "stage_two_semantic_selection_enabled",
            lambda: StageTwoCommitProfile.model_validate(
                {**stage_two.model_dump(mode="json"), "compiler_may_choose_semantic_field": True}
            ),
        ),
        (
            "resource_completion_32k",
            lambda: TwoStageResourceContract.model_validate(
                {
                    **resource.model_dump(mode="json"),
                    "exact_request_completion_bound_tokens": 32768,
                }
            ),
        ),
        (
            "resource_rollout_240k",
            lambda: TwoStageResourceContract.model_validate(
                {**resource.model_dump(mode="json"), "rollout_upper_bound_tokens": 240000}
            ),
        ),
        (
            "resource_stage_two_provider_call",
            lambda: TwoStageResourceContract.model_validate(
                {**resource.model_dump(mode="json"), "maximum_stage_two_provider_calls": 1}
            ),
        ),
        (
            "resource_usage_clipping",
            lambda: TwoStageResourceContract.model_validate(
                {
                    **resource.model_dump(mode="json"),
                    "actual_provider_usage_charged_without_clipping": False,
                }
            ),
        ),
        (
            "resource_historical_deficit_selection",
            lambda: TwoStageResourceContract.model_validate(
                {
                    **resource.model_dump(mode="json"),
                    "historical_v26_105_deficit_used_to_select_bound": True,
                }
            ),
        ),
        (
            "task_claimed_fresh",
            lambda: TwoStageTaskPackage.model_validate(
                {**task.model_dump(mode="json"), "source_claimed_fresh": True}
            ),
        ),
        (
            "task_role_evidence_enabled",
            lambda: TwoStageTaskPackage.model_validate(
                {**task.model_dump(mode="json"), "capability_support_eligible": True}
            ),
        ),
        (
            "task_profile_parent_changed",
            lambda: _build_cross_audit(
                tuple(
                    _rehash(
                        item,
                        "task_package_id",
                        two_stage_task_package_id,
                        stage_one_profile_id="changed",
                    )
                    if item == task
                    else item
                    for item in tasks
                ),
                paths,
                jobs,
                contract,
                manifest,
            ),
        ),
        (
            "path_task_parent_changed",
            lambda: _build_cross_audit(
                tasks,
                tuple(
                    _rehash(
                        item,
                        "path_audit_id",
                        two_stage_path_audit_id,
                        task_package_id="changed",
                    )
                    if item == path
                    else item
                    for item in paths
                ),
                jobs,
                contract,
                manifest,
            ),
        ),
        (
            "path_stage_two_call_added",
            lambda: TwoStagePathAudit.model_validate(
                {**path.model_dump(mode="json"), "stage_two_provider_call_count": 1}
            ),
        ),
        (
            "path_request_arithmetic_changed",
            lambda: TwoStagePathAudit.model_validate(
                {
                    **path.model_dump(mode="json"),
                    "semantic_proposal_request_count": path.semantic_proposal_request_count + 1,
                }
            ),
        ),
        (
            "path_rollout_headroom_changed",
            lambda: TwoStagePathAudit.model_validate(
                {
                    **path.model_dump(mode="json"),
                    "static_rollout_headroom_tokens": path.static_rollout_headroom_tokens + 1,
                }
            ),
        ),
        (
            "contract_task_membership_changed",
            lambda: _build_cross_audit(
                tasks,
                paths,
                jobs,
                _rehash(
                    contract,
                    "contract_id",
                    two_stage_execution_contract_id,
                    task_package_ids=contract.task_package_ids[1:] + ("changed",),
                ),
                manifest,
            ),
        ),
        (
            "contract_instrument_misclassification",
            lambda: TwoStageExecutionContract.model_validate(
                {
                    **contract.model_dump(mode="json"),
                    "semantic_compile_rejection_is_model_result": False,
                }
            ),
        ),
        (
            "contract_private_reasoning_enabled",
            lambda: TwoStageExecutionContract.model_validate(
                {
                    **contract.model_dump(mode="json"),
                    "private_reasoning_persistence_allowed": True,
                }
            ),
        ),
        (
            "job_contract_parent_changed",
            lambda: _build_cross_audit(
                tasks,
                paths,
                tuple(
                    _rehash(
                        item,
                        "job_id",
                        two_stage_job_id,
                        contract_id="changed",
                    )
                    if item == job
                    else item
                    for item in jobs
                ),
                contract,
                manifest,
            ),
        ),
        (
            "job_seed_resampled",
            lambda: _build_cross_audit(
                tasks,
                paths,
                tuple(
                    _rehash(
                        item,
                        "job_id",
                        two_stage_job_id,
                        job_seed=job.job_seed + 1,
                    )
                    if item == job
                    else item
                    for item in jobs
                ),
                contract,
                manifest,
            ),
        ),
        (
            "manifest_contract_parent_changed",
            lambda: _build_cross_audit(
                tasks,
                paths,
                jobs,
                contract,
                _rehash(
                    manifest,
                    "manifest_id",
                    two_stage_manifest_id,
                    contract_id="changed",
                ),
            ),
        ),
        (
            "manifest_job_removed",
            lambda: TwoStageManifest.model_validate(
                {**manifest.model_dump(mode="json"), "jobs": manifest.jobs[:-1]}
            ),
        ),
        (
            "manifest_execution_authorized",
            lambda: TwoStageManifest.model_validate(
                {**manifest.model_dump(mode="json"), "execution_authorized": True}
            ),
        ),
        (
            "manifest_job_identity_overlap",
            lambda: TwoStageManifest.model_validate(
                {
                    **manifest.model_dump(mode="json"),
                    "predecessor_job_identity_overlap_count": 1,
                }
            ),
        ),
        (
            "profile_protocol_parent_changed",
            lambda: StageOneThinkingProfile.model_validate(
                {**stage_one.model_dump(mode="json"), "predecessor_protocol_id": "changed"}
            ),
        ),
    )
    results = tuple(_expect_rejection(name, function) for name, function in cases)
    provisional = DestructivePreflightAudit.model_construct(
        audit_id="pending",
        mutation_results=results,
    )
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        mutation_results=results,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build(
    output_dir: Path,
    *,
    package_root: Path,
    implementation_root: Path,
) -> TwoStageStaticPreflightReport:
    predecessor_report, predecessor_replay, _, _, _ = _load_predecessor(package_root)
    replay = _build_source_replay(package_root, implementation_root, predecessor_replay)
    stage_one, stage_two = _build_profiles(implementation_root)
    resource = _build_resource(stage_one, stage_two)
    static = load_static_inputs(package_root)
    tasks = _build_task_packages(static.task_packages, stage_one, stage_two, resource)
    paths = _build_paths(static, tasks, stage_one, stage_two, resource)
    contract = _build_contract(replay, tasks, paths, stage_one, stage_two, resource)
    jobs = _build_jobs(
        static.predecessor_manifest,
        tasks,
        paths,
        contract,
        stage_one,
        stage_two,
        resource,
    )
    manifest = _build_manifest(
        static.predecessor_manifest,
        jobs,
        contract,
        stage_one,
        stage_two,
        resource,
    )
    design = _build_design_audit(
        static.task_packages,
        static.path_audits,
        static.predecessor_manifest.jobs,
        tasks,
        paths,
        jobs,
    )
    cross = _build_cross_audit(tasks, paths, jobs, contract, manifest)
    destructive = _build_destructive(
        replay,
        stage_one,
        stage_two,
        resource,
        tasks,
        paths,
        contract,
        jobs,
        manifest,
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("cross_artifact_binding_audit.json", cross),
        ("design_preservation_audit.json", design),
        ("destructive_preflight_audit.json", destructive),
        ("source_replay_audit.json", replay),
        ("stage_one_thinking_profile.json", stage_one),
        ("stage_two_commit_profile.json", stage_two),
        ("two_stage_execution_contract.json", contract),
        ("two_stage_job_manifest.json", manifest),
        ("two_stage_path_audits.json", paths),
        ("two_stage_resource_contract.json", resource),
        ("two_stage_task_packages.json", tasks),
    )
    for name, value in outputs:
        _write_json(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "predecessor_report_id": predecessor_report.report_id,
        "source_replay_audit_id": replay.audit_id,
        "stage_one_profile_id": stage_one.profile_id,
        "stage_two_profile_id": stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "design_preservation_audit_id": design.audit_id,
        "cross_artifact_binding_audit_id": cross.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = TwoStageStaticPreflightReport.model_construct(
        report_id="pending",
        **values,
    )
    report = TwoStageStaticPreflightReport(
        report_id=two_stage_static_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--implementation-root", type=Path)
    args = parser.parse_args()
    implementation_root = (
        args.implementation_root
        if args.implementation_root is not None
        else Path(__file__).resolve().parents[4]
    )
    package_root = args.package_root if args.package_root is not None else implementation_root
    report = build(
        args.output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
