from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_failure_audit as failure,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_rematerialization as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    FINAL_FIELD_ORDER,
    FINAL_RESPONSE_PROTOCOL_VERSION,
    ExactFinalResponseGrammar,
    FinalResponseHostEnvelope,
    compile_exact_final_response_grammar,
    exact_final_response_payload,
    final_prompt_semantic_projection,
    make_final_response_host_envelope,
    parse_exact_final_response_payload,
    parse_prompt_only_reference_final_payload,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    ABI_RESCUE_LIMIT,
    SEMANTIC_RECOVERY_LIMIT,
    evaluate_canonical_action_proposal,
)

RUN_ID: Final = "finance_v26_122_final_grammar_privacy_rematerialization_v1_20260823"
NEXT_STAGE: Final = "privacy_first_exact_final_runner_preflight_only"
PREDECESSOR_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_121_semantic_action_calibration_failure_audit_v1_20260823"
)
STATIC_PREDECESSOR_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_118_semantic_action_rematerialization_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_122_final_grammar_privacy_rematerialization_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_final_grammar_privacy_rematerialization.py"
)
FINAL_GRAMMAR_PATH: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_exact_final_response_grammar.py"
)
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_semantic_action_failure_audit_report:"
    "62abced772e0b281912749f041e56ab1038b2cc76489da4157bfcb6265efcf5a"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_semantic_action_failure_transition:"
    "4f893fe1d7a4e9250e9685b55661c8cca3b9a8e2189ee6fdbe69cc514543ec9f"
)
EXPECTED_STATIC_REPORT_ID: Final = (
    "finance_v26_semantic_action_rematerialization_report:"
    "eb1820c71ac6a0a5b062d6c3db1f31768ed5dc9c68827d4dd79777f622ab0519"
)
EXPECTED_ACTION_PROTOCOL_ID: Final = (
    "finance_v26_semantic_action_protocol:"
    "3f178cb8af42b41809ea0d1c2324bfaf2ddfcdd732ad7cb570f2ccaec4ec8984"
)
EXPECTED_ACTION_GRAMMAR_ID: Final = (
    "prospective_semantic_action_response_grammar:"
    "bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82"
)
EXPECTED_CANDIDATE_AUDIT_ID: Final = (
    "finance_v26_candidate_space_authority:"
    "58dd1803e6802e48a39884097884c5f4f77d606537b31359e1e192c0515c315d"
)
EXPECTED_RESOURCE_ID: Final = (
    "finance_v26_semantic_action_resource_contract:"
    "358453a9075d5df7a158b9a11100bf27585dacde644f993058452a0f0a851bdf"
)
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_123_privacy_first_exact_final_runner_preflight_v1_20260823"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_124_exact_final_semantic_action_calibration_execution_v1_20260823"
)
PREDECESSOR_OUTPUTS: Final = (
    "destructive_audit.json",
    "failed_execution_lineage_audit.json",
    "final_response_interface_audit.json",
    "privacy_persistence_failure_audit.json",
    "prospective_transition_contract.json",
    "provider_telemetry_audit.json",
    "public_action_outcome_audit.json",
    "report.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_121_transitive_source",
        "v26_121_output",
        "v26_122_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[2523] = 2523
    predecessor_output_file_count: Literal[9] = 9
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2534] = 2534
    replay_pass_count: Literal[2534] = 2534
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2534, max_length=2534)
    replay_before_grammar_or_identity_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_final_grammar_source_replay.v1"] = (
        "finance_v26_final_grammar_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2534:
            raise ValueError("v26.122 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.122 source replay contains a hash mismatch")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_final_grammar_source_replay:"):
            raise ValueError("v26.122 source replay identity changed")
        return self


class FinalGrammarConstructibilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    response_protocol: Literal["prospective_exact_final_response.v1"] = (
        FINAL_RESPONSE_PROTOCOL_VERSION
    )
    final_state_count: Literal[48] = 48
    primary_prompt_count: Literal[48] = 48
    rescue_prompt_count: Literal[48] = 48
    prompt_only_primary_parse_count: Literal[48] = 48
    prompt_only_rescue_parse_count: Literal[48] = 48
    compiler_answer_match_count: Literal[96] = 96
    primary_rescue_semantic_projection_match_count: Literal[48] = 48
    rescue_json_lexical_cue_pass_count: Literal[48] = 48
    host_envelope_count: Literal[48] = 48
    host_metadata_absent_from_model_payload_count: Literal[96] = 96
    wrong_answer_schema_admission_count: Literal[48] = 48
    missing_field_rejection_count: Literal[48] = 48
    extra_field_rejection_count: Literal[48] = 48
    wrapper_rejection_count: Literal[48] = 48
    private_reasoning_field_rejection_count: Literal[48] = 48
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    model_generated_stage_protocol_or_parent_count: Literal[0] = 0
    host_answer_or_rationale_insertion_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_final_grammar_constructibility.v1"] = (
        "finance_v26_final_grammar_constructibility.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FinalGrammarConstructibilityAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_final_grammar_constructibility:"
        ):
            raise ValueError("v26.122 Final Grammar constructibility identity changed")
        return self


class SemanticActionPreservationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_static_report_id: str = EXPECTED_STATIC_REPORT_ID
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    candidate_space_authority_audit_id: str = EXPECTED_CANDIDATE_AUDIT_ID
    action_state_count: Literal[324] = 324
    exact_action_prompt_hash_match_count: Literal[324] = 324
    exact_candidate_presentation_match_count: Literal[324] = 324
    exact_reference_commit_match_count: Literal[324] = 324
    source_projection_match_count: Literal[24] = 24
    path_assignment_match_count: Literal[48] = 48
    job_assignment_and_seed_match_count: Literal[32] = 32
    model_profile_match_count: Literal[104] = 104
    completion_bound_preserved: Literal[True] = True
    rollout_ceiling_preserved: Literal[True] = True
    abi_rescue_limit_preserved: Literal[True] = True
    semantic_recovery_limit_preserved: Literal[True] = True
    stage_two_provider_call_bound_preserved: Literal[True] = True
    v26_120_outcome_used_for_selection: Literal[False] = False
    historical_result_reclassified: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_preservation.v1"] = (
        "finance_v26_semantic_action_preservation.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticActionPreservationAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_preservation:"
        ):
            raise ValueError("v26.122 semantic-action preservation identity changed")
        return self


class FinalGrammarResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_resource_contract_id: str = EXPECTED_RESOURCE_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    accounted_completion_bound_tokens: Literal[16385] = 16385
    prompt_upper_bound_bytes: Literal[60000] = 60000
    chat_envelope_tokens: Literal[256] = 256
    qualified_maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_primary_stage_one_requests: Literal[11] = 11
    maximum_abi_rescue_calls_per_job: Literal[1] = ABI_RESCUE_LIMIT
    maximum_semantic_recovery_calls_per_job: Literal[1] = SEMANTIC_RECOVERY_LIMIT
    maximum_stage_one_provider_calls: Literal[12] = 12
    maximum_stage_two_provider_calls: Literal[0] = 0
    maximum_static_complete_path_bound_tokens: int = Field(gt=260000, lt=400000)
    rollout_upper_bound_tokens: Literal[400000] = 400000
    minimum_static_headroom_tokens: int = Field(ge=20000)
    completion_and_rollout_bounds_changed: Literal[False] = False
    actual_provider_usage_charged_without_clipping: Literal[True] = True
    one_token_margin_accounting_only: Literal[True] = True
    two_or_more_excess_tokens_instrument_failure: Literal[True] = True
    final_primary_and_rescue_qualified_before_provider: Literal[True] = True
    schema_version: Literal["finance_v26_final_grammar_resource_contract.v1"] = (
        "finance_v26_final_grammar_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> FinalGrammarResourceContract:
        if (
            self.accounted_completion_bound_tokens
            != self.exact_request_completion_bound_tokens + self.provider_accounting_margin_tokens
            or self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests + self.maximum_abi_rescue_calls_per_job
            or self.minimum_static_headroom_tokens
            != self.rollout_upper_bound_tokens - self.maximum_static_complete_path_bound_tokens
        ):
            raise ValueError("v26.122 resource arithmetic changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_final_grammar_resource_contract:"
        ):
            raise ValueError("v26.122 resource Contract identity changed")
        return self


class FinalGrammarTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    final_response_protocol: Literal["prospective_exact_final_response.v1"] = (
        FINAL_RESPONSE_PROTOCOL_VERSION
    )
    candidate_space_authority_audit_id: str = EXPECTED_CANDIDATE_AUDIT_ID
    verifier_v3_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    measurement_object: Literal["canonical_action_execution_and_exact_final_response"] = (
        "canonical_action_execution_and_exact_final_response"
    )
    source_model_exposed_before_freeze: Literal[True] = True
    engineering_calibration_only: Literal[True] = True
    capability_reachability_state_or_release_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_final_grammar_task_package.v1"] = (
        "finance_v26_final_grammar_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> FinalGrammarTaskPackage:
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_final_grammar_task_package:"
        ):
            raise ValueError("v26.122 TaskPackage identity changed")
        return self


class FinalGrammarPathAudit(FrozenModel):
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    semantic_action_request_count: int = Field(gt=0)
    final_answer_request_count: Literal[1] = 1
    primary_stage_one_request_count: int = Field(gt=0, le=11)
    maximum_stage_one_provider_calls_with_recovery: int = Field(gt=0, le=12)
    stage_two_commit_count: int = Field(gt=0)
    stage_two_provider_call_count: Literal[0] = 0
    action_primary_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_host_envelope_id: str = Field(min_length=1)
    maximum_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, lt=400000)
    static_rollout_headroom_tokens: int = Field(ge=20000)
    prompt_ceiling_passed: Literal[True] = True
    rollout_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_final_grammar_path_audit.v1"] = (
        "finance_v26_final_grammar_path_audit.v1"
    )

    @model_validator(mode="after")
    def validate_path(self) -> FinalGrammarPathAudit:
        if (
            self.primary_stage_one_request_count
            != self.semantic_action_request_count + self.final_answer_request_count
            or self.maximum_stage_one_provider_calls_with_recovery
            != self.primary_stage_one_request_count + 2
            or self.stage_two_commit_count != self.semantic_action_request_count
        ):
            raise ValueError("v26.122 path request arithmetic changed")
        if self.path_audit_id != _identity(
            self, "path_audit_id", "finance_v26_final_grammar_path_audit:"
        ):
            raise ValueError("v26.122 Path identity changed")
        return self


class FinalGrammarExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_failure_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_static_contract_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    final_response_protocol: Literal["prospective_exact_final_response.v1"] = (
        FINAL_RESPONSE_PROTOCOL_VERSION
    )
    candidate_space_authority_audit_id: str = EXPECTED_CANDIDATE_AUDIT_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    exact_job_denominator: Literal[32] = 32
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    action_response_fields: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    final_response_fields: tuple[str, str] = FINAL_FIELD_ORDER
    final_host_metadata_not_model_generated: Literal[True] = True
    telemetry_persisted_before_payload_validation: Literal[True] = True
    invalid_payload_content_or_key_persistence_allowed: Literal[False] = False
    abi_rescue_limit: Literal[1] = ABI_RESCUE_LIMIT
    semantic_recovery_limit: Literal[1] = SEMANTIC_RECOVERY_LIMIT
    stage_two_provider_calls: Literal[0] = 0
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_final_grammar_execution_contract.v1"] = (
        "finance_v26_final_grammar_execution_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> FinalGrammarExecutionContract:
        if len(set(self.task_package_ids)) != 24 or len(set(self.path_audit_ids)) != 48:
            raise ValueError("v26.122 Contract denominator changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_final_grammar_execution_contract:"
        ):
            raise ValueError("v26.122 execution Contract identity changed")
        return self


class FinalGrammarJob(FrozenModel):
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    source_repeated_for_engineering_calibration: Literal[True] = True
    schema_version: Literal["finance_v26_final_grammar_job.v1"] = "finance_v26_final_grammar_job.v1"

    @model_validator(mode="after")
    def validate_job(self) -> FinalGrammarJob:
        if self.job_id != _identity(self, "job_id", "finance_v26_final_grammar_job:"):
            raise ValueError("v26.122 Job identity changed")
        return self


class FinalGrammarManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    jobs: tuple[FinalGrammarJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    exact_denominator: Literal[32] = 32
    predecessor_job_identity_overlap_count: Literal[0] = 0
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_final_grammar_manifest.v1"] = (
        "finance_v26_final_grammar_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> FinalGrammarManifest:
        if (
            len({item.job_id for item in self.jobs}) != 32
            or len({item.task_package_id for item in self.jobs}) != 24
        ):
            raise ValueError("v26.122 Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_final_grammar_manifest:"
        ):
            raise ValueError("v26.122 Manifest identity changed")
        return self


class CrossArtifactBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    task_parent_binding_pass_count: Literal[24] = 24
    path_parent_binding_pass_count: Literal[48] = 48
    job_parent_binding_pass_count: Literal[32] = 32
    action_final_profile_resource_binding_pass_count: Literal[104] = 104
    source_projection_match_count: Literal[24] = 24
    path_projection_match_count: Literal[48] = 48
    job_assignment_and_seed_match_count: Literal[32] = 32
    task_identity_overlap_with_v26_118: Literal[0] = 0
    path_identity_overlap_with_v26_118: Literal[0] = 0
    job_identity_overlap_with_v26_118: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_final_grammar_cross_binding.v1"] = (
        "finance_v26_final_grammar_cross_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CrossArtifactBindingAudit:
        if self.audit_id != _identity(self, "audit_id", "finance_v26_final_grammar_cross_binding:"):
            raise ValueError("v26.122 cross-artifact binding identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[20] = 20
    rejection_count: Literal[20] = 20
    mutations: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_final_grammar_destructive.v1"] = (
        "finance_v26_final_grammar_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 20:
            raise ValueError("v26.122 destructive controls changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_final_grammar_destructive:"):
            raise ValueError("v26.122 destructive audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    status: Literal["passed_static_rematerialization"] = "passed_static_rematerialization"
    next_permitted_stage: str = NEXT_STAGE
    exact_credential_free_runner_preflight_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    semantic_action_candidate_model_or_resource_ceiling_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    host_semantic_choice_answer_or_repair_authorized: Literal[False] = False
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_final_grammar_transition.v1"] = (
        "finance_v26_final_grammar_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_final_grammar_transition:"
        ):
            raise ValueError("v26.122 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class FinalGrammarRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    exact_final_response_grammar_id: str = Field(min_length=1)
    grammar_constructibility_audit_id: str = Field(min_length=1)
    semantic_action_preservation_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    cross_artifact_binding_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=12, max_length=12)
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_authorized: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_static_rematerialization"] = "passed_static_rematerialization"
    schema_version: Literal["finance_v26_final_grammar_rematerialization_report.v1"] = (
        "finance_v26_final_grammar_rematerialization_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> FinalGrammarRematerializationReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_final_grammar_rematerialization_report:"
        ):
            raise ValueError("v26.122 report identity changed")
        return self


class FinalGrammarStaticInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: FinalGrammarRematerializationReport
    contract: FinalGrammarExecutionContract
    manifest: FinalGrammarManifest
    resource: FinalGrammarResourceContract
    final_grammar: ExactFinalResponseGrammar
    tasks: tuple[FinalGrammarTaskPackage, ...]
    paths: tuple[FinalGrammarPathAudit, ...]
    predecessor: predecessor.SemanticActionStaticInputs
    stage_one: Any
    stage_two: Any
    action_grammar: Any
    agent_model_config: Any


@dataclass(frozen=True)
class _FinalMaterial:
    predecessor_material: Any
    predecessor_path: predecessor.SemanticActionPathAudit
    envelope: FinalResponseHostEnvelope
    primary_prompt: str
    rescue_prompt: str
    static_upper_bound: int


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and legacy.sha256_file(path) == expected_sha256:
            return path
    raise ValueError(f"v26.122 cannot replay bound file: {relative_path}")


def _source_replay(
    package_root: Path,
    implementation_root: Path,
) -> tuple[SourceReplayAudit, failure.FailureAuditReport]:
    root = implementation_root / PREDECESSOR_DIR
    predecessor_source = failure.FailureSourceReplayAudit.model_validate(
        _load(root / "source_replay_audit.json")
    )
    report = failure.FailureAuditReport.model_validate(_load(root / "report.json"))
    transition = failure.ProspectiveTransitionContract.model_validate(
        _load(root / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or transition.next_permitted_stage != failure.NEXT_STAGE
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.122 predecessor authorization changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_121_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    for name in PREDECESSOR_OUTPUTS:
        path = root / name
        relative = str(Path(PREDECESSOR_DIR) / name)
        expected = details[name].sha256 if name in details else legacy.sha256_file(path)
        if name == "report.json":
            failure.FailureAuditReport.model_validate(_load(path))
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_121_output",
            expected_sha256=expected,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    for relative in (IMPLEMENTATION_PATH, FINAL_GRAMMAR_PATH):
        path = implementation_root / relative
        digest = legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_122_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return (
        SourceReplayAudit(
            audit_id=_identity(provisional, "audit_id", "finance_v26_final_grammar_source_replay:"),
            **values,
        ),
        report,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + 16385


def _build_final_materials(
    static: predecessor.SemanticActionStaticInputs,
    grammar: ExactFinalResponseGrammar,
) -> tuple[
    tuple[_FinalMaterial, ...],
    FinalGrammarConstructibilityAudit,
    SemanticActionPreservationAudit,
]:
    old_materials, _ = predecessor._build_materials(static.historical, static.grammar)
    old_paths = {item.predecessor_path_audit_id: item for item in static.paths}
    rows: list[_FinalMaterial] = []
    primary_parses = 0
    rescue_parses = 0
    answer_matches = 0
    semantic_matches = 0
    json_cues = 0
    host_absent = 0
    wrong_admitted = 0
    missing_rejected = 0
    extra_rejected = 0
    wrapper_rejected = 0
    private_rejected = 0
    action_hash_matches = 0
    commit_matches = 0
    for material in old_materials:
        intermediate_path = next(
            item
            for item in static.historical.paths
            if item.predecessor_path_audit_id == material.predecessor_path.audit_id
        )
        old_path = old_paths[intermediate_path.path_audit_id]
        observed_hashes = tuple(
            hashlib.sha256(item.encode("utf-8")).hexdigest() for item in material.primary_prompts
        )
        if observed_hashes != old_path.primary_prompt_sha256s:
            raise ValueError("v26.122 changed a Semantic Action Prompt or Candidate order")
        action_hash_matches += len(observed_hashes)
        state = material.states[-1]
        selected = evaluate_canonical_action_proposal(
            state,
            material.proposals[-1],
            call_index=len(material.expected_calls),
        )
        if selected.commit is None or selected.commit.action != "emit_final":
            raise ValueError("v26.122 predecessor path lacks its exact Final Commit")
        commit_matches += len(material.proposals)
        envelope = make_final_response_host_envelope(
            terminal_state_id=state.state_id,
            terminal_commit_id=selected.commit.commit_id,
            grammar=grammar,
        )
        primary = render_exact_final_primary_prompt(
            material.final_answer_prompt,
            grammar=grammar,
        )
        rescue = render_exact_final_rescue_prompt(
            primary,
            failure_family="response_serialization_failure",
            failure_subtype="final_response_not_exact_shared_grammar",
        )
        parsed_primary = parse_prompt_only_reference_final_payload(primary, envelope=envelope)
        parsed_rescue = parse_prompt_only_reference_final_payload(rescue, envelope=envelope)
        expected_answer = material.binding.compiler_trajectory.final_answer
        primary_parses += 1
        rescue_parses += 1
        answer_matches += int(parsed_primary.answer == expected_answer)
        answer_matches += int(parsed_rescue.answer == expected_answer)
        semantic_matches += int(
            final_prompt_semantic_projection(primary) == final_prompt_semantic_projection(rescue)
        )
        json_cues += int("json" in rescue.casefold())
        host_absent += int(
            not (
                set(parsed_primary.model_dump(mode="json"))
                & set(grammar.host_bound_metadata_fields)
            )
        )
        host_absent += int(
            not (
                set(parsed_rescue.model_dump(mode="json")) & set(grammar.host_bound_metadata_fields)
            )
        )
        wrong = parsed_primary.model_dump(mode="json")
        wrong_answer = dict(wrong["answer"])
        wrong_result = dict(wrong_answer["result"])
        first = next(iter(wrong_result))
        wrong_result[first] = "__schema_valid_but_semantically_wrong__"
        wrong_answer["result"] = wrong_result
        wrong["answer"] = wrong_answer
        parse_exact_final_response_payload(wrong, grammar=grammar, envelope=envelope)
        wrong_admitted += 1
        controls = (
            ("missing", {"answer": expected_answer}),
            (
                "extra",
                {
                    **parsed_primary.model_dump(mode="json"),
                    "protocol": grammar.response_protocol,
                },
            ),
            (
                "wrapper",
                {"final_response": parsed_primary.model_dump(mode="json")},
            ),
            (
                "private",
                {
                    "answer": {"reasoning_trace": "forbidden"},
                    "rationale_summary": "public",
                },
            ),
        )
        rejected: set[str] = set()
        for name, payload in controls:
            try:
                parse_exact_final_response_payload(
                    payload,
                    grammar=grammar,
                    envelope=envelope,
                )
            except Exception:
                rejected.add(name)
        missing_rejected += int("missing" in rejected)
        extra_rejected += int("extra" in rejected)
        wrapper_rejected += int("wrapper" in rejected)
        private_rejected += int("private" in rejected)
        abi_max = max(_request_bound(item) for item in material.abi_rescue_prompts)
        recovery_max = max(_request_bound(item) for item in material.semantic_recovery_prompts)
        static_upper = sum(_request_bound(item) for item in material.primary_prompts)
        static_upper += _request_bound(primary)
        static_upper += max(abi_max, _request_bound(rescue))
        static_upper += recovery_max
        rows.append(
            _FinalMaterial(
                predecessor_material=material,
                predecessor_path=old_path,
                envelope=envelope,
                primary_prompt=primary,
                rescue_prompt=rescue,
                static_upper_bound=static_upper,
            )
        )
    if (
        len(rows) != 48
        or primary_parses != 48
        or rescue_parses != 48
        or answer_matches != 96
        or semantic_matches != 48
        or json_cues != 48
        or host_absent != 96
        or wrong_admitted != 48
        or missing_rejected != 48
        or extra_rejected != 48
        or wrapper_rejected != 48
        or private_rejected != 48
        or action_hash_matches != 324
        or commit_matches != 324
    ):
        raise ValueError("v26.122 Final Grammar or Semantic Action control failed")
    grammar_values = {
        "grammar_id": grammar.grammar_id,
        "prompt_only_primary_parse_count": primary_parses,
        "prompt_only_rescue_parse_count": rescue_parses,
        "compiler_answer_match_count": answer_matches,
        "primary_rescue_semantic_projection_match_count": semantic_matches,
        "rescue_json_lexical_cue_pass_count": json_cues,
        "host_metadata_absent_from_model_payload_count": host_absent,
        "wrong_answer_schema_admission_count": wrong_admitted,
        "missing_field_rejection_count": missing_rejected,
        "extra_field_rejection_count": extra_rejected,
        "wrapper_rejection_count": wrapper_rejected,
        "private_reasoning_field_rejection_count": private_rejected,
        "maximum_primary_prompt_utf8_bytes": max(
            len(item.primary_prompt.encode("utf-8")) for item in rows
        ),
        "maximum_rescue_prompt_utf8_bytes": max(
            len(item.rescue_prompt.encode("utf-8")) for item in rows
        ),
    }
    grammar_provisional = FinalGrammarConstructibilityAudit.model_construct(
        audit_id="pending", **grammar_values
    )
    grammar_audit = FinalGrammarConstructibilityAudit(
        audit_id=_identity(
            grammar_provisional,
            "audit_id",
            "finance_v26_final_grammar_constructibility:",
        ),
        **grammar_values,
    )
    preservation_values = {
        "exact_action_prompt_hash_match_count": action_hash_matches,
        "exact_candidate_presentation_match_count": action_hash_matches,
        "exact_reference_commit_match_count": commit_matches,
    }
    preservation_provisional = SemanticActionPreservationAudit.model_construct(
        audit_id="pending", **preservation_values
    )
    preservation = SemanticActionPreservationAudit(
        audit_id=_identity(
            preservation_provisional,
            "audit_id",
            "finance_v26_semantic_action_preservation:",
        ),
        **preservation_values,
    )
    return tuple(rows), grammar_audit, preservation


def _build_resource(
    static: predecessor.SemanticActionStaticInputs,
    grammar: ExactFinalResponseGrammar,
    materials: Sequence[_FinalMaterial],
) -> FinalGrammarResourceContract:
    maximum = max(item.static_upper_bound for item in materials)
    values = {
        "exact_final_response_grammar_id": grammar.grammar_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "qualified_maximum_action_primary_prompt_utf8_bytes": (
            static.resource.qualified_maximum_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_action_abi_rescue_prompt_utf8_bytes": (
            static.resource.qualified_maximum_abi_rescue_prompt_utf8_bytes
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": (
            static.resource.qualified_maximum_semantic_recovery_prompt_utf8_bytes
        ),
        "qualified_maximum_final_primary_prompt_utf8_bytes": max(
            len(item.primary_prompt.encode("utf-8")) for item in materials
        ),
        "qualified_maximum_final_rescue_prompt_utf8_bytes": max(
            len(item.rescue_prompt.encode("utf-8")) for item in materials
        ),
        "maximum_static_complete_path_bound_tokens": maximum,
        "minimum_static_headroom_tokens": 400000 - maximum,
    }
    provisional = FinalGrammarResourceContract.model_construct(contract_id="pending", **values)
    return FinalGrammarResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_final_grammar_resource_contract:",
        ),
        **values,
    )


def _build_tasks(
    static: predecessor.SemanticActionStaticInputs,
    grammar: ExactFinalResponseGrammar,
    resource: FinalGrammarResourceContract,
) -> tuple[FinalGrammarTaskPackage, ...]:
    rows = []
    for old in static.tasks:
        values = {
            "predecessor_task_package_id": old.task_package_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "source_role": old.source_role,
            "mechanism_id": old.mechanism_id,
            "operational_record_id": old.operational_record_id,
            "operational_task_package_id": old.operational_task_package_id,
            "environment_manifest_id": old.environment_manifest_id,
            "semantic_source_id": old.semantic_source_id,
            "stage_one_profile_id": old.stage_one_profile_id,
            "stage_two_profile_id": old.stage_two_profile_id,
            "exact_final_response_grammar_id": grammar.grammar_id,
            "verifier_v3_contract_id": old.verifier_v3_contract_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = FinalGrammarTaskPackage.model_construct(task_package_id="pending", **values)
        rows.append(
            FinalGrammarTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_final_grammar_task_package:",
                ),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.task_package_id))


def _build_paths(
    grammar: ExactFinalResponseGrammar,
    resource: FinalGrammarResourceContract,
    tasks: Sequence[FinalGrammarTaskPackage],
    materials: Sequence[_FinalMaterial],
) -> tuple[FinalGrammarPathAudit, ...]:
    tasks_by_old = {item.predecessor_task_package_id: item for item in tasks}
    rows = []
    for item in materials:
        old = item.predecessor_path
        task = tasks_by_old[old.task_package_id]
        values = {
            "predecessor_path_audit_id": old.path_audit_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old.task_package_id,
            "compiler_trajectory_id": old.compiler_trajectory_id,
            "role": old.role,
            "mechanism_id": old.mechanism_id,
            "path_strategy_id": old.path_strategy_id,
            "exact_final_response_grammar_id": grammar.grammar_id,
            "resource_contract_id": resource.contract_id,
            "semantic_action_request_count": old.semantic_action_request_count,
            "primary_stage_one_request_count": old.semantic_action_request_count + 1,
            "maximum_stage_one_provider_calls_with_recovery": (
                old.semantic_action_request_count + 3
            ),
            "stage_two_commit_count": old.stage_two_commit_count,
            "action_primary_prompt_sha256s": old.primary_prompt_sha256s,
            "final_primary_prompt_sha256": hashlib.sha256(
                item.primary_prompt.encode("utf-8")
            ).hexdigest(),
            "final_rescue_prompt_sha256": hashlib.sha256(
                item.rescue_prompt.encode("utf-8")
            ).hexdigest(),
            "final_host_envelope_id": item.envelope.envelope_id,
            "maximum_prompt_utf8_bytes": max(
                old.maximum_primary_prompt_utf8_bytes,
                len(item.primary_prompt.encode("utf-8")),
                len(item.rescue_prompt.encode("utf-8")),
            ),
            "static_complete_path_upper_bound_tokens": item.static_upper_bound,
            "static_rollout_headroom_tokens": (
                resource.rollout_upper_bound_tokens - item.static_upper_bound
            ),
        }
        provisional = FinalGrammarPathAudit.model_construct(path_audit_id="pending", **values)
        rows.append(
            FinalGrammarPathAudit(
                path_audit_id=_identity(
                    provisional,
                    "path_audit_id",
                    "finance_v26_final_grammar_path_audit:",
                ),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda value: value.path_audit_id))


def _build_contract_manifest(
    replay: SourceReplayAudit,
    static: predecessor.SemanticActionStaticInputs,
    grammar: ExactFinalResponseGrammar,
    resource: FinalGrammarResourceContract,
    tasks: Sequence[FinalGrammarTaskPackage],
    paths: Sequence[FinalGrammarPathAudit],
) -> tuple[FinalGrammarExecutionContract, FinalGrammarManifest]:
    contract_values = {
        "predecessor_static_contract_id": static.contract.contract_id,
        "source_replay_audit_id": replay.audit_id,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in tasks)),
        "path_audit_ids": tuple(sorted(item.path_audit_id for item in paths)),
    }
    provisional_contract = FinalGrammarExecutionContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = FinalGrammarExecutionContract(
        contract_id=_identity(
            provisional_contract,
            "contract_id",
            "finance_v26_final_grammar_execution_contract:",
        ),
        **contract_values,
    )
    task_by_old = {item.predecessor_task_package_id: item for item in tasks}
    path_by_old = {item.predecessor_path_audit_id: item for item in paths}
    jobs = []
    for old in static.manifest.jobs:
        task = task_by_old[old.task_package_id]
        path = path_by_old[old.path_audit_id]
        values = {
            "predecessor_job_id": old.job_id,
            "contract_id": contract.contract_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old.task_package_id,
            "path_audit_id": path.path_audit_id,
            "predecessor_path_audit_id": old.path_audit_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "mechanism_id": old.mechanism_id,
            "path_strategy_id": old.path_strategy_id,
            "source_role": old.source_role,
            "job_seed": old.job_seed,
            "stage_one_profile_id": old.stage_one_profile_id,
            "stage_two_profile_id": old.stage_two_profile_id,
            "exact_final_response_grammar_id": grammar.grammar_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = FinalGrammarJob.model_construct(job_id="pending", **values)
        jobs.append(
            FinalGrammarJob(
                job_id=_identity(provisional, "job_id", "finance_v26_final_grammar_job:"),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    manifest_values = {
        "contract_id": contract.contract_id,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "stage_one_profile_id": static.stage_one.profile_id,
        "stage_two_profile_id": static.stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "jobs": ordered,
        "mechanism_job_counts": dict(
            sorted(Counter(item.mechanism_id for item in ordered).items())
        ),
        "path_job_counts": dict(sorted(Counter(item.path_strategy_id for item in ordered).items())),
        "cell_job_counts": dict(
            sorted(
                Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered).items()
            )
        ),
    }
    provisional_manifest = FinalGrammarManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    manifest = FinalGrammarManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_final_grammar_manifest:",
        ),
        **manifest_values,
    )
    return contract, manifest


def _build_cross(
    static: predecessor.SemanticActionStaticInputs,
    grammar: ExactFinalResponseGrammar,
    resource: FinalGrammarResourceContract,
    tasks: Sequence[FinalGrammarTaskPackage],
    paths: Sequence[FinalGrammarPathAudit],
    contract: FinalGrammarExecutionContract,
    manifest: FinalGrammarManifest,
) -> CrossArtifactBindingAudit:
    task_by_id = {item.task_package_id: item for item in tasks}
    path_by_id = {item.path_audit_id: item for item in paths}
    old_tasks = {item.task_package_id: item for item in static.tasks}
    old_paths = {item.path_audit_id: item for item in static.paths}
    old_jobs = {item.job_id: item for item in static.manifest.jobs}
    source_matches = sum(
        (
            item.source_task_artifact_id,
            item.source_role,
            item.mechanism_id,
            item.operational_record_id,
            item.semantic_source_id,
        )
        == (
            old_tasks[item.predecessor_task_package_id].source_task_artifact_id,
            old_tasks[item.predecessor_task_package_id].source_role,
            old_tasks[item.predecessor_task_package_id].mechanism_id,
            old_tasks[item.predecessor_task_package_id].operational_record_id,
            old_tasks[item.predecessor_task_package_id].semantic_source_id,
        )
        for item in tasks
    )
    path_matches = sum(
        (
            item.compiler_trajectory_id,
            item.role,
            item.mechanism_id,
            item.path_strategy_id,
            item.action_primary_prompt_sha256s,
        )
        == (
            old_paths[item.predecessor_path_audit_id].compiler_trajectory_id,
            old_paths[item.predecessor_path_audit_id].role,
            old_paths[item.predecessor_path_audit_id].mechanism_id,
            old_paths[item.predecessor_path_audit_id].path_strategy_id,
            old_paths[item.predecessor_path_audit_id].primary_prompt_sha256s,
        )
        for item in paths
    )
    job_matches = sum(
        (
            item.source_task_artifact_id,
            item.mechanism_id,
            item.path_strategy_id,
            item.source_role,
            item.job_seed,
        )
        == (
            old_jobs[item.predecessor_job_id].source_task_artifact_id,
            old_jobs[item.predecessor_job_id].mechanism_id,
            old_jobs[item.predecessor_job_id].path_strategy_id,
            old_jobs[item.predecessor_job_id].source_role,
            old_jobs[item.predecessor_job_id].job_seed,
        )
        for item in manifest.jobs
    )
    parent_tasks = sum(item.predecessor_task_package_id in old_tasks for item in tasks)
    parent_paths = sum(
        item.task_package_id in task_by_id and item.predecessor_path_audit_id in old_paths
        for item in paths
    )
    parent_jobs = sum(
        item.task_package_id in task_by_id
        and item.path_audit_id in path_by_id
        and item.contract_id == contract.contract_id
        and item.predecessor_job_id in old_jobs
        for item in manifest.jobs
    )
    bindings = sum(
        item.exact_final_response_grammar_id == grammar.grammar_id
        and item.resource_contract_id == resource.contract_id
        for item in (*tasks, *paths, *manifest.jobs)
    )
    values = {
        "task_parent_binding_pass_count": parent_tasks,
        "path_parent_binding_pass_count": parent_paths,
        "job_parent_binding_pass_count": parent_jobs,
        "action_final_profile_resource_binding_pass_count": bindings,
        "source_projection_match_count": source_matches,
        "path_projection_match_count": path_matches,
        "job_assignment_and_seed_match_count": job_matches,
        "task_identity_overlap_with_v26_118": len(
            {item.task_package_id for item in tasks} & set(old_tasks)
        ),
        "path_identity_overlap_with_v26_118": len(
            {item.path_audit_id for item in paths} & set(old_paths)
        ),
        "job_identity_overlap_with_v26_118": len(
            {item.job_id for item in manifest.jobs} & set(old_jobs)
        ),
    }
    provisional = CrossArtifactBindingAudit.model_construct(audit_id="pending", **values)
    return CrossArtifactBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_final_grammar_cross_binding:",
        ),
        **values,
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except Exception:
        return MutationResult(name=name)
    raise ValueError(f"v26.122 destructive mutation was accepted: {name}")


def _build_destructive(
    grammar: ExactFinalResponseGrammar,
    envelope: FinalResponseHostEnvelope,
    resource: FinalGrammarResourceContract,
    task: FinalGrammarTaskPackage,
    path: FinalGrammarPathAudit,
    contract: FinalGrammarExecutionContract,
    job: FinalGrammarJob,
    manifest: FinalGrammarManifest,
) -> DestructiveAudit:
    valid_payload = exact_final_response_payload(
        {"result": {"value": "fixture"}, "citations": [{"evidence_id": "fixture"}]},
        rationale_summary="public fixture",
    )

    def parse(value: Mapping[str, Any]) -> Any:
        return parse_exact_final_response_payload(value, grammar=grammar, envelope=envelope)

    actions: dict[str, Callable[[], Any]] = {
        "candidate_authority_change": lambda: FinalGrammarExecutionContract.model_validate(
            {
                **contract.model_dump(mode="json"),
                "candidate_space_authority_audit_id": "changed",
            }
        ),
        "completion_bound_change": lambda: FinalGrammarResourceContract.model_validate(
            {
                **resource.model_dump(mode="json"),
                "exact_request_completion_bound_tokens": 32768,
            }
        ),
        "extra_final_field": lambda: parse({**valid_payload, "protocol": "forbidden"}),
        "final_grammar_change": lambda: ExactFinalResponseGrammar.model_validate(
            {**grammar.model_dump(mode="json"), "response_protocol": "changed"}
        ),
        "host_answer_insertion": lambda: FinalResponseHostEnvelope.model_validate(
            {
                **envelope.model_dump(mode="json"),
                "host_supplies_answer_or_rationale": True,
            }
        ),
        "host_envelope_grammar_change": lambda: FinalResponseHostEnvelope.model_validate(
            {**envelope.model_dump(mode="json"), "grammar_id": "changed"}
        ),
        "job_identity_reuse": lambda: FinalGrammarJob.model_validate(
            {**job.model_dump(mode="json"), "job_id": job.predecessor_job_id}
        ),
        "manifest_historical_job_insertion": lambda: FinalGrammarManifest.model_validate(
            {
                **manifest.model_dump(mode="json"),
                "jobs": [
                    {
                        **item.model_dump(mode="json"),
                        "job_id": item.predecessor_job_id,
                    }
                    for item in manifest.jobs
                ],
            }
        ),
        "missing_final_field": lambda: parse({"answer": valid_payload["answer"]}),
        "model_generated_protocol": lambda: parse(
            {**valid_payload, "protocol": grammar.response_protocol}
        ),
        "model_generated_stage": lambda: parse({**valid_payload, "stage": "final_answer"}),
        "path_identity_reuse": lambda: FinalGrammarPathAudit.model_validate(
            {**path.model_dump(mode="json"), "path_audit_id": path.predecessor_path_audit_id}
        ),
        "private_reasoning_field": lambda: parse(
            {
                "answer": {"reasoning_trace": "forbidden"},
                "rationale_summary": "public",
            }
        ),
        "recovery_limit_change": lambda: FinalGrammarExecutionContract.model_validate(
            {**contract.model_dump(mode="json"), "abi_rescue_limit": 2}
        ),
        "resource_ceiling_change": lambda: FinalGrammarResourceContract.model_validate(
            {**resource.model_dump(mode="json"), "rollout_upper_bound_tokens": 420000}
        ),
        "stage_two_provider_route": lambda: FinalGrammarExecutionContract.model_validate(
            {**contract.model_dump(mode="json"), "stage_two_provider_calls": 1}
        ),
        "task_identity_reuse": lambda: FinalGrammarTaskPackage.model_validate(
            {
                **task.model_dump(mode="json"),
                "task_package_id": task.predecessor_task_package_id,
            }
        ),
        "task_model_profile_change": lambda: FinalGrammarTaskPackage.model_validate(
            {**task.model_dump(mode="json"), "stage_one_profile_id": "changed"}
        ),
        "wrapper_final_payload": lambda: parse({"final_response": valid_payload}),
        "wrong_host_parent": lambda: FinalResponseHostEnvelope.model_validate(
            {**envelope.model_dump(mode="json"), "terminal_state_id": "changed"}
        ),
    }
    mutations = tuple(_expect_rejection(name, actions[name]) for name in sorted(actions))
    values = {"mutations": mutations}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_final_grammar_destructive:"),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def load_final_grammar_static_inputs(
    package_root: Path,
    implementation_root: Path,
) -> FinalGrammarStaticInputs:
    root = implementation_root / OUTPUT_DIR
    report = FinalGrammarRematerializationReport.model_validate(_load(root / "report.json"))
    contract = FinalGrammarExecutionContract.model_validate(
        _load(root / "final_grammar_execution_contract.json")
    )
    manifest = FinalGrammarManifest.model_validate(_load(root / "final_grammar_job_manifest.json"))
    resource = FinalGrammarResourceContract.model_validate(
        _load(root / "final_grammar_resource_contract.json")
    )
    grammar = ExactFinalResponseGrammar.model_validate(
        _load(root / "exact_final_response_grammar.json")
    )
    tasks = tuple(
        FinalGrammarTaskPackage.model_validate(item)
        for item in _load(root / "final_grammar_task_packages.json")
    )
    paths = tuple(
        FinalGrammarPathAudit.model_validate(item)
        for item in _load(root / "final_grammar_path_audits.json")
    )
    old = predecessor.load_semantic_action_static_inputs(package_root, implementation_root)
    if (
        report.execution_contract_id != contract.contract_id
        or report.manifest_id != manifest.manifest_id
        or report.resource_contract_id != resource.contract_id
        or report.exact_final_response_grammar_id != grammar.grammar_id
        or manifest.contract_id != contract.contract_id
        or contract.resource_contract_id != resource.contract_id
        or contract.exact_final_response_grammar_id != grammar.grammar_id
        or report.next_permitted_stage != NEXT_STAGE
        or report.execution_authorized
    ):
        raise ValueError("v26.122 static identity chain changed")
    return FinalGrammarStaticInputs(
        report=report,
        contract=contract,
        manifest=manifest,
        resource=resource,
        final_grammar=grammar,
        tasks=tasks,
        paths=paths,
        predecessor=old,
        stage_one=old.stage_one,
        stage_two=old.stage_two,
        action_grammar=old.grammar,
        agent_model_config=old.agent_model_config,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> FinalGrammarRematerializationReport:
    replay, _ = _source_replay(package_root, implementation_root)
    old = predecessor.load_semantic_action_static_inputs(package_root, implementation_root)
    if (
        old.report.report_id != EXPECTED_STATIC_REPORT_ID
        or old.contract.semantic_action_protocol_id != EXPECTED_ACTION_PROTOCOL_ID
        or old.grammar.grammar_id != EXPECTED_ACTION_GRAMMAR_ID
        or old.contract.candidate_space_authority_audit_id != EXPECTED_CANDIDATE_AUDIT_ID
        or old.resource.contract_id != EXPECTED_RESOURCE_ID
    ):
        raise ValueError("v26.122 frozen Semantic Action baseline changed")
    grammar = compile_exact_final_response_grammar()
    materials, grammar_audit, preservation = _build_final_materials(old, grammar)
    resource = _build_resource(old, grammar, materials)
    tasks = _build_tasks(old, grammar, resource)
    paths = _build_paths(grammar, resource, tasks, materials)
    contract, manifest = _build_contract_manifest(replay, old, grammar, resource, tasks, paths)
    cross = _build_cross(old, grammar, resource, tasks, paths, contract, manifest)
    destructive = _build_destructive(
        grammar,
        materials[0].envelope,
        resource,
        tasks[0],
        paths[0],
        contract,
        manifest.jobs[0],
        manifest,
    )
    transition_provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            transition_provisional,
            "contract_id",
            "finance_v26_final_grammar_transition:",
        )
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", replay),
        ("exact_final_response_grammar.json", grammar),
        ("final_grammar_constructibility_audit.json", grammar_audit),
        ("semantic_action_preservation_audit.json", preservation),
        ("final_grammar_resource_contract.json", resource),
        ("final_grammar_task_packages.json", [item.model_dump(mode="json") for item in tasks]),
        ("final_grammar_path_audits.json", [item.model_dump(mode="json") for item in paths]),
        ("final_grammar_execution_contract.json", contract),
        ("final_grammar_job_manifest.json", manifest),
        ("cross_artifact_binding_audit.json", cross),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": replay.audit_id,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "grammar_constructibility_audit_id": grammar_audit.audit_id,
        "semantic_action_preservation_audit_id": preservation.audit_id,
        "resource_contract_id": resource.contract_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "cross_artifact_binding_audit_id": cross.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = FinalGrammarRematerializationReport.model_construct(report_id="pending", **values)
    report = FinalGrammarRematerializationReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_final_grammar_rematerialization_report:",
        ),
        **values,
    )
    _write(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credential-free v26.122 exact Final Grammar rematerialization"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
