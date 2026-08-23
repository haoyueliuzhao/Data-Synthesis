from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    _path_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_execution import (  # noqa: E501
    load_exact_grammar_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_protocol_preflight import (  # noqa: E501
    SemanticActionPreflightReport,
    SemanticActionSourceReplay,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    StageOneThinkingProfile,
    StageTwoCommitProfile,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    sha256_file,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    ABI_RESCUE_LIMIT,
    SEMANTIC_RECOVERY_LIMIT,
    CanonicalActionProposal,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    FIELD_ORDER,
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseGrammar,
    assert_action_id_shape,
    candidate_prompt_utf8_bytes,
    compile_semantic_action_response_grammar,
    independently_enumerate_visible_actions,
    opaque_action_id,
    parse_exact_canonical_action_payload,
    parse_prompt_only_reference_payload,
    render_exact_canonical_action_abi_rescue_prompt,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
    validate_candidate_space_completeness,
)
from trusted_synthesis.runtime.tools import AgentToolCall, AgentToolObservation

RUN_ID: Final = "finance_v26_118_semantic_action_rematerialization_v1_20260823"
NEXT_STAGE: Final = "semantic_action_runner_preflight_only"
PREDECESSOR_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_117_semantic_action_protocol_preflight_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_118_semantic_action_rematerialization_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_rematerialization.py"
)
RESPONSE_GRAMMAR_PATH: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_semantic_action_response_grammar.py"
)
SEMANTIC_PROTOCOL_PATH: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_semantic_action_protocol.py"
)
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_semantic_action_preflight_report:"
    "876f4215157688cd420a1708ecd9f4f2d5527d40cd11db0e4828f920095ce362"
)
EXPECTED_PREDECESSOR_PROTOCOL_ID: Final = (
    "finance_v26_semantic_action_protocol:"
    "3f178cb8af42b41809ea0d1c2324bfaf2ddfcdd732ad7cb570f2ccaec4ec8984"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_semantic_action_transition:"
    "90567cb15885dadcd2340e394af572017118bae806d634f8cf0554841306290c"
)
PROSPECTIVE_RUNNER_RUN_ID: Final = "finance_v26_119_semantic_action_runner_preflight_v1_20260823"
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_120_semantic_action_calibration_execution_v1_20260823"
)
PREDECESSOR_OUTPUTS: Final = (
    "canonical_action_language_audit.json",
    "destructive_audit.json",
    "operation_frontier_audit.json",
    "prompt_only_path_control.json",
    "prospective_transition_contract.json",
    "report.json",
    "semantic_action_protocol_contract.json",
    "semantic_recovery_continuity_audit.json",
    "source_replay_audit.json",
    "stage_two_authority_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_117_transitive_source",
        "v26_117_output",
        "v26_118_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[2191] = 2191
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2203] = 2203
    replay_pass_count: Literal[2203] = 2203
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2203, max_length=2203)
    replay_before_candidate_or_resource_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_rematerialization_source_replay.v1"] = (
        "finance_v26_semantic_action_rematerialization_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2203:
            raise ValueError("v26.118 source replay paths are not canonical and unique")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.118 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_semantic_action_rematerialization_source_replay:",
        ):
            raise ValueError("v26.118 source replay identity changed")
        return self


class CandidateCountRow(FrozenModel):
    candidate_count: int = Field(gt=0)
    state_count: int = Field(gt=0)


class CandidateSpaceAuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    state_count: Literal[324] = 324
    public_input_signature_pass_count: Literal[1] = 1
    candidate_builder_scoped_function_audit_count: Literal[7] = 7
    forbidden_candidate_builder_symbol_read_count: Literal[0] = 0
    oracle_gold_reference_workflow_or_target_state_input_count: Literal[0] = 0
    independent_complete_enumeration_pass_count: Literal[324] = 324
    visible_acceptance_equality_pass_count: Literal[324] = 324
    candidate_count_rows: tuple[CandidateCountRow, ...] = Field(min_length=1)
    total_visible_candidate_count: int = Field(gt=324)
    minimum_candidate_count: int = Field(gt=0)
    maximum_candidate_count: int = Field(gt=1)
    maximum_candidate_list_utf8_bytes: int = Field(gt=0)
    multi_candidate_state_count: int = Field(gt=0)
    singleton_state_count: int = Field(gt=0)
    legal_distractor_count: int = Field(gt=0)
    alternate_acquisition_mode_distractor_count: int = Field(gt=0)
    alternate_operator_distractor_count: int = Field(gt=0)
    alternate_verification_subset_distractor_count: int = Field(gt=0)
    reference_action_first_in_multi_candidate_state_count: int = Field(ge=0)
    reference_action_shortest_in_multi_candidate_state_count: int = Field(ge=0)
    reference_action_position_count: int = Field(gt=1)
    order_permutation_trials: Literal[972] = 972
    order_permutation_semantic_match_count: Literal[972] = 972
    id_free_reference_policy_match_count: Literal[324] = 324
    opaque_id_substitution_trial_count: Literal[324] = 324
    opaque_id_substitution_pass_count: Literal[324] = 324
    opaque_id_static_decision_match_count: Literal[324] = 324
    opaque_id_canonical_commit_match_count: Literal[324] = 324
    opaque_id_relabeling_is_audit_only: Literal[True] = True
    production_host_alias_normalization_count: Literal[0] = 0
    uniform_content_address_shape_pass_count: int = Field(gt=324)
    dropped_distractor_mutation_rejected: Literal[True] = True
    correct_only_candidate_mutation_rejected: Literal[True] = True
    candidate_builder_uses_model_outcome: Literal[False] = False
    candidate_builder_uses_oracle_correctness: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_candidate_space_authority_audit.v1"] = (
        "finance_v26_candidate_space_authority_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CandidateSpaceAuthorityAudit:
        if (
            self.reference_action_first_in_multi_candidate_state_count
            >= self.multi_candidate_state_count
        ):
            raise ValueError("reference action is always first in multi-candidate states")
        if (
            self.reference_action_shortest_in_multi_candidate_state_count
            >= self.multi_candidate_state_count
        ):
            raise ValueError("reference action is always shortest in multi-candidate states")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_candidate_space_authority:"):
            raise ValueError("v26.118 Candidate-space authority identity changed")
        return self


class SemanticActionResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    accounted_completion_bound_tokens: Literal[16385] = 16385
    prompt_upper_bound_bytes: Literal[60000] = 60000
    chat_envelope_tokens: Literal[256] = 256
    qualified_maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_answer_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_primary_stage_one_requests: Literal[11] = 11
    maximum_abi_rescue_calls_per_job: Literal[1] = ABI_RESCUE_LIMIT
    maximum_semantic_recovery_calls_per_job: Literal[1] = SEMANTIC_RECOVERY_LIMIT
    maximum_stage_one_provider_calls: Literal[12] = 12
    maximum_stage_two_provider_calls: Literal[0] = 0
    maximum_static_complete_path_bound_tokens: int = Field(gt=260000)
    rollout_upper_bound_tokens: int = Field(gt=260000)
    rollout_rounding_quantum_tokens: Literal[20000] = 20000
    minimum_static_headroom_tokens: int = Field(ge=20000)
    candidate_space_not_compressed_to_preserve_old_bound: Literal[True] = True
    bound_derived_before_provider_behavior: Literal[True] = True
    bound_selected_from_future_model_success: Literal[False] = False
    actual_provider_usage_charged_without_clipping: Literal[True] = True
    one_token_margin_accounting_only: Literal[True] = True
    two_or_more_excess_tokens_instrument_failure: Literal[True] = True
    final_answer_reserve_required: Literal[True] = True
    abi_rescue_and_semantic_recovery_reserves_separate: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_resource_contract.v1"] = (
        "finance_v26_semantic_action_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticActionResourceContract:
        expected = (
            math.ceil(
                (
                    self.maximum_static_complete_path_bound_tokens
                    + self.rollout_rounding_quantum_tokens
                )
                / self.rollout_rounding_quantum_tokens
            )
            * self.rollout_rounding_quantum_tokens
        )
        if (
            self.accounted_completion_bound_tokens
            != self.exact_request_completion_bound_tokens + self.provider_accounting_margin_tokens
            or self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests + self.maximum_abi_rescue_calls_per_job
            or self.rollout_upper_bound_tokens != expected
            or self.minimum_static_headroom_tokens
            != self.rollout_upper_bound_tokens - self.maximum_static_complete_path_bound_tokens
        ):
            raise ValueError("v26.118 resource arithmetic changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_resource_contract:"
        ):
            raise ValueError("v26.118 resource Contract identity changed")
        return self


class SemanticActionTaskPackage(FrozenModel):
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
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    candidate_space_authority_audit_id: str = Field(min_length=1)
    verifier_v3_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    measurement_object: Literal["public_state_interpretation_and_canonical_action_selection"] = (
        "public_state_interpretation_and_canonical_action_selection"
    )
    source_model_exposed_before_freeze: Literal[True] = True
    engineering_calibration_only: Literal[True] = True
    capability_reachability_state_or_release_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_task_package.v1"] = (
        "finance_v26_semantic_action_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> SemanticActionTaskPackage:
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_semantic_action_task_package:"
        ):
            raise ValueError("v26.118 TaskPackage identity changed")
        return self


class SemanticActionPathAudit(FrozenModel):
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    compiler_trajectory_id: str = Field(min_length=1)
    role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    compiler_tool_call_count: int = Field(gt=0)
    semantic_action_request_count: int = Field(gt=0)
    final_answer_request_count: Literal[1] = 1
    primary_stage_one_request_count: int = Field(gt=0, le=11)
    maximum_stage_one_provider_calls_with_recovery: int = Field(gt=0, le=12)
    stage_two_commit_count: int = Field(gt=0)
    stage_two_provider_call_count: Literal[0] = 0
    primary_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    final_answer_prompt_sha256: str = Field(min_length=64, max_length=64)
    maximum_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_candidate_list_utf8_bytes: int = Field(gt=0)
    maximum_candidate_count: int = Field(gt=0)
    maximum_blocked_action_count: int = Field(ge=0)
    static_complete_path_upper_bound_tokens: int = Field(gt=0)
    static_rollout_headroom_tokens: int = Field(ge=0)
    prompt_ceiling_passed: Literal[True] = True
    rollout_ceiling_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_semantic_action_path_audit.v1"] = (
        "finance_v26_semantic_action_path_audit.v1"
    )

    @model_validator(mode="after")
    def validate_path(self) -> SemanticActionPathAudit:
        if (
            self.semantic_action_request_count != self.compiler_tool_call_count + 1
            or self.primary_stage_one_request_count
            != self.semantic_action_request_count + self.final_answer_request_count
            or self.maximum_stage_one_provider_calls_with_recovery
            != self.primary_stage_one_request_count + 2
            or self.stage_two_commit_count != self.semantic_action_request_count
        ):
            raise ValueError("v26.118 path request arithmetic changed")
        if self.path_audit_id != _identity(
            self, "path_audit_id", "finance_v26_semantic_action_path_audit:"
        ):
            raise ValueError("v26.118 Path identity changed")
        return self


class SemanticActionExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    candidate_space_authority_audit_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_audit_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    exact_job_denominator: Literal[32] = 32
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    model_response_fields: tuple[str, str, str, str] = FIELD_ORDER
    measurement_object: Literal["public_state_interpretation_and_canonical_action_selection"] = (
        "public_state_interpretation_and_canonical_action_selection"
    )
    action_protocol_and_recovery_policy_are_experimental_conditions: Literal[True] = True
    open_semantic_action_construction_claim_authorized: Literal[False] = False
    first_choice_and_eventual_recovery_outcomes_separate: Literal[True] = True
    abi_rescue_limit: Literal[1] = ABI_RESCUE_LIMIT
    semantic_recovery_limit: Literal[1] = SEMANTIC_RECOVERY_LIMIT
    stage_two_provider_calls: Literal[0] = 0
    raw_provider_persisted_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    private_reasoning_persistence_allowed: Literal[False] = False
    runner_implemented: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_execution_contract.v1"] = (
        "finance_v26_semantic_action_execution_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticActionExecutionContract:
        if len(set(self.task_package_ids)) != 24 or len(set(self.path_audit_ids)) != 48:
            raise ValueError("v26.118 Contract denominator changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_execution_contract:"
        ):
            raise ValueError("v26.118 execution Contract identity changed")
        return self


class SemanticActionJob(FrozenModel):
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
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    source_repeated_for_engineering_calibration: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_job.v1"] = (
        "finance_v26_semantic_action_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> SemanticActionJob:
        if self.job_id != _identity(self, "job_id", "finance_v26_semantic_action_job:"):
            raise ValueError("v26.118 Job identity changed")
        return self


class SemanticActionManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = EXPECTED_PREDECESSOR_PROTOCOL_ID
    response_grammar_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    jobs: tuple[SemanticActionJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    exact_denominator: Literal[32] = 32
    predecessor_job_identity_overlap_count: Literal[0] = 0
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_manifest.v1"] = (
        "finance_v26_semantic_action_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> SemanticActionManifest:
        if (
            len({item.job_id for item in self.jobs}) != 32
            or len({item.task_package_id for item in self.jobs}) != 24
        ):
            raise ValueError("v26.118 Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_semantic_action_manifest:"
        ):
            raise ValueError("v26.118 Manifest identity changed")
        return self


class CrossArtifactBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    task_parent_binding_pass_count: Literal[24] = 24
    path_parent_binding_pass_count: Literal[48] = 48
    job_parent_binding_pass_count: Literal[32] = 32
    profile_protocol_grammar_resource_binding_pass_count: Literal[104] = 104
    source_projection_match_count: Literal[24] = 24
    path_projection_match_count: Literal[48] = 48
    job_assignment_and_seed_match_count: Literal[32] = 32
    task_identity_overlap_with_v26_112: Literal[0] = 0
    path_identity_overlap_with_v26_112: Literal[0] = 0
    job_identity_overlap_with_v26_112: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_cross_binding.v1"] = (
        "finance_v26_semantic_action_cross_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CrossArtifactBindingAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_cross_binding:"
        ):
            raise ValueError("v26.118 cross-artifact binding identity changed")
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
    schema_version: Literal["finance_v26_semantic_action_rematerialization_destructive.v1"] = (
        "finance_v26_semantic_action_rematerialization_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 20:
            raise ValueError("v26.118 destructive controls are not canonical and unique")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_semantic_action_rematerialization_destructive:",
        ):
            raise ValueError("v26.118 destructive audit identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    status: Literal["passed_static_rematerialization"] = "passed_static_rematerialization"
    next_permitted_stage: str = NEXT_STAGE
    exact_credential_free_runner_preflight_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    candidate_protocol_resource_or_identity_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    host_semantic_choice_or_repair_authorized: Literal[False] = False
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_semantic_action_rematerialization_transition.v1"] = (
        "finance_v26_semantic_action_rematerialization_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_semantic_action_rematerialization_transition:"
        ):
            raise ValueError("v26.118 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SemanticActionRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    response_grammar_id: str = Field(min_length=1)
    candidate_space_authority_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    cross_artifact_binding_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=11, max_length=11)
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    job_count: Literal[32] = 32
    candidate_state_count: Literal[324] = 324
    four_field_prompt_parse_count: Literal[972] = 972
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_authorized: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_static_rematerialization"] = "passed_static_rematerialization"
    schema_version: Literal["finance_v26_semantic_action_rematerialization_report.v1"] = (
        "finance_v26_semantic_action_rematerialization_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> SemanticActionRematerializationReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_action_rematerialization_report:"
        ):
            raise ValueError("v26.118 report identity changed")
        return self


class SemanticActionStaticInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: SemanticActionRematerializationReport
    contract: SemanticActionExecutionContract
    manifest: SemanticActionManifest
    resource: SemanticActionResourceContract
    grammar: SemanticActionResponseGrammar
    tasks: tuple[SemanticActionTaskPackage, ...]
    paths: tuple[SemanticActionPathAudit, ...]
    stage_one: StageOneThinkingProfile
    stage_two: StageTwoCommitProfile
    agent_model_config: Any
    historical: Any


@dataclass(frozen=True)
class _PathMaterial:
    predecessor_path: Any
    binding: Any
    states: tuple[SemanticActionState, ...]
    primary_prompts: tuple[str, ...]
    abi_rescue_prompts: tuple[str, ...]
    semantic_recovery_prompts: tuple[str, ...]
    proposals: tuple[CanonicalActionProposal, ...]
    expected_calls: tuple[AgentToolCall | None, ...]
    final_answer_prompt: str
    static_upper_bound: int


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
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
        candidate = root / relative_path
        if candidate.is_file() and sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.118 cannot replay bound file: {relative_path}")


def _entry(path: Path, relative: str, kind: Any, expected: str | None = None) -> SourceReplayEntry:
    digest = sha256_file(path)
    return SourceReplayEntry(
        relative_path=relative,
        source_kind=kind,
        expected_sha256=expected or digest,
        observed_sha256=digest,
        byte_count=path.stat().st_size,
    )


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> tuple[SourceReplayAudit, SemanticActionPreflightReport]:
    predecessor_root = package_root / PREDECESSOR_DIR
    predecessor_source = SemanticActionSourceReplay.model_validate(
        _load_json(predecessor_root / "source_replay_audit.json")
    )
    predecessor_report = SemanticActionPreflightReport.model_validate(
        _load_json(predecessor_root / "report.json")
    )
    if (
        predecessor_report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or predecessor_report.protocol_id != EXPECTED_PREDECESSOR_PROTOCOL_ID
        or predecessor_report.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
    ):
        raise ValueError("v26.118 predecessor identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = _entry(
            path,
            item.relative_path,
            "v26_117_transitive_source",
            item.expected_sha256,
        )
    detail = {item.relative_path: item for item in predecessor_report.detail_files}
    for name in PREDECESSOR_OUTPUTS:
        path = predecessor_root / name
        if not path.is_file():
            raise ValueError("v26.118 predecessor output is missing")
        if name != "report.json":
            expected = detail.get(name)
            if (
                expected is None
                or expected.sha256 != sha256_file(path)
                or expected.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.118 predecessor detail binding changed")
        relative = str(Path(PREDECESSOR_DIR) / name)
        entries[relative] = _entry(path, relative, "v26_117_output")
    for relative in (IMPLEMENTATION_PATH, RESPONSE_GRAMMAR_PATH):
        path = implementation_root / relative
        entries[relative] = _entry(path, relative, "v26_118_implementation")
    ordered = tuple(entries[key] for key in sorted(entries))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return (
        SourceReplayAudit(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_semantic_action_rematerialization_source_replay:",
            ),
            **values,
        ),
        predecessor_report,
    )


def _prompt_candidates(prompt: str) -> tuple[dict[str, Any], ...]:
    raw = json.loads(prompt.partition("\n")[2])
    return tuple(dict(item) for item in raw["visible_action_candidates"])


def _select_prompt_candidate_without_action_id(prompt: str) -> dict[str, Any]:
    """Mirror the public reference policy without reading an action ID during selection."""

    payload = json.loads(prompt.partition("\n")[2])
    state = payload["public_state_without_candidate_order"]
    candidates = tuple(dict(item) for item in payload["visible_action_candidates"])
    instruction = str(payload["instruction"])
    condition = payload["public_path_condition"]
    unresolved = tuple(str(item) for item in state["unresolved_symbols"])
    selected: dict[str, Any] | None = None
    if unresolved:
        symbol = unresolved[0]
        available = tuple(
            item
            for item in candidates
            if item["decision_kind"] == "acquire_public_input"
            and tuple(item["target_source_symbols"]) == (symbol,)
        )
        by_mode = {str(item["acquisition_mode"]): item for item in available}
        blocked_modes = {
            str(item["acquisition_mode"])
            for item in state["blocked_actions"]
            if tuple(item["target_source_symbols"]) == (symbol,)
        }
        recovery_required = (
            "first exact selector attempt returns a typed recoverable failure"
            in instruction.casefold()
        )
        route = str(condition or "structured_direct")
        history = tuple(dict(item) for item in state["acquisition_history"])
        search_observed = any(
            item["acquisition_mode"] == "search_public_record"
            and symbol in item["target_source_symbols"]
            and item["status"] == "succeeded"
            for item in history
        )
        if "query_source_scoped" in blocked_modes:
            selected = by_mode.get("query_fully_qualified")
        elif (
            recovery_required
            and not any(
                item["error_category"] == "typed_selector_requires_refinement" for item in history
            )
            and not any(
                item["acquisition_mode"] in {"query_source_scoped", "query_fully_qualified"}
                and symbol in item["target_source_symbols"]
                for item in history
            )
        ):
            selected = by_mode.get(
                "search_public_record"
                if route != "structured_direct" and not search_observed
                else "query_source_scoped"
            )
        elif route == "structured_direct":
            selected = by_mode.get("query_fully_qualified")
        elif not search_observed:
            selected = by_mode.get("search_public_record")
        elif route == "search_then_structured":
            selected = by_mode.get("query_fully_qualified")
        else:
            selected = by_mode.get("open_public_document")
    else:
        executable = tuple(
            item for item in candidates if item["decision_kind"] == "execute_public_operation"
        )
        verification = tuple(
            item for item in candidates if item["decision_kind"] == "verify_terminal_operation"
        )
        final = tuple(item for item in candidates if item["decision_kind"] == "emit_final_answer")
        if executable:
            first_node_id = min(str(item["node_id"]) for item in executable)
            same_node = tuple(item for item in executable if str(item["node_id"]) == first_node_id)
            frontier = next(
                item
                for item in state["operation_frontier"]
                if str(item["node_id"]) == first_node_id and item["frontier_status"] == "executable"
            )
            output_schemas = dict(frontier["operator_output_schemas"])
            schema_matched = tuple(
                item
                for item in same_node
                if frontier["required_output_schema"] is not None
                and output_schemas.get(str(item["operator_id"]))
                == frontier["required_output_schema"]
            )
            selected = min(
                schema_matched or same_node,
                key=lambda item: str(item["operator_id"]),
            )
        elif verification:
            selected = max(verification, key=lambda item: len(item["evidence_reference_ids"]))
        elif len(final) == 1:
            selected = final[0]
    if selected is None:
        raise ValueError("ID-free Prompt policy cannot select a public semantic Candidate")
    return selected


def _opaque_relabel_prompt(prompt: str, opaque_ids: Mapping[str, str]) -> str:
    prefix, separator, raw_payload = prompt.partition("\n")
    if not separator:
        raise ValueError("opaque relabeling fixture lacks a Prompt payload")
    payload = json.loads(raw_payload)
    candidates = []
    for item in payload["visible_action_candidates"]:
        candidate = dict(item)
        candidate["action_id"] = opaque_ids[str(candidate["action_id"])]
        candidates.append(candidate)
    payload["visible_action_candidates"] = candidates
    return (
        prefix
        + "\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _candidate_semantics(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "action_id"}


def _different_decision(decision: str) -> Any:
    values = (
        "acquire_public_input",
        "execute_public_operation",
        "verify_terminal_operation",
        "emit_final_answer",
    )
    return next(item for item in values if item != decision)


def _build_materials(
    historical: Any,
    grammar: SemanticActionResponseGrammar,
) -> tuple[tuple[_PathMaterial, ...], dict[str, Any]]:
    materials: list[_PathMaterial] = []
    candidate_counts: Counter[int] = Counter()
    total_candidates = 0
    max_candidate_bytes = 0
    multi_states = 0
    singleton_states = 0
    distractors = 0
    acquisition_distractors = 0
    operator_distractors = 0
    verification_distractors = 0
    selected_first = 0
    selected_shortest = 0
    selected_positions: set[int] = set()
    permutation_matches = 0
    id_free_matches = 0
    opaque_matches = 0
    opaque_decision_matches = 0
    opaque_commit_matches = 0
    shape_passes = 0
    completeness = 0
    acceptance = 0
    for predecessor_path in historical.historical.path_audits:
        binding = _path_binding(historical.historical, predecessor_path)
        observations: list[AgentToolObservation] = []
        states: list[SemanticActionState] = []
        primary_prompts: list[str] = []
        abi_prompts: list[str] = []
        recovery_prompts: list[str] = []
        proposals: list[CanonicalActionProposal] = []
        expected_calls: list[AgentToolCall | None] = []
        condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        tool_steps = tuple(
            item for item in binding.compiler_trajectory.steps if item.tool_name is not None
        )
        for logical_index in range(len(tool_steps) + 1):
            state = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
            )
            validate_candidate_space_completeness(state)
            independent = independently_enumerate_visible_actions(state)
            if independent != state.action_candidates:
                raise ValueError("v26.118 independent Candidate enumeration changed")
            completeness += 1
            acceptance += int(
                tuple(item.action_id for item in independent)
                == tuple(item.action_id for item in state.action_candidates)
            )
            salt = canonical_hash(
                {
                    "path_id": predecessor_path.audit_id,
                    "state_id": state.state_id,
                    "logical_index": logical_index,
                },
                prefix="finance_v26_candidate_presentation_salt:",
            )
            prompt = render_exact_canonical_action_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=salt,
                grammar=grammar,
            )
            proposal = parse_prompt_only_reference_payload(prompt)
            id_free_selected = _select_prompt_candidate_without_action_id(prompt)
            if id_free_selected["action_id"] != proposal.action_id:
                raise ValueError("ID-free Prompt policy changed the reference semantic action")
            id_free_matches += 1
            result = evaluate_canonical_action_proposal(
                state, proposal, call_index=len(observations) + 1
            )
            expected_call = (
                AgentToolCall(
                    call_index=len(observations) + 1,
                    tool_id=str(tool_steps[logical_index].tool_name),
                    arguments=tool_steps[logical_index].tool_input,
                )
                if logical_index < len(tool_steps)
                else None
            )
            if (
                result.commit is None
                or result.commit.call != expected_call
                or result.rejection is not None
            ):
                raise ValueError("v26.118 Prompt-only proposal did not match Compiler")
            candidates = _prompt_candidates(prompt)
            candidate_ids = tuple(str(item["action_id"]) for item in candidates)
            selected_index = candidate_ids.index(proposal.action_id)
            selected_positions.add(selected_index)
            count = len(candidates)
            candidate_counts[count] += 1
            total_candidates += count
            max_candidate_bytes = max(max_candidate_bytes, candidate_prompt_utf8_bytes(prompt))
            shape_passes += count
            for action_id in candidate_ids:
                assert_action_id_shape(action_id)
            if count > 1:
                multi_states += 1
                distractors += count - 1
                selected_first += int(selected_index == 0)
                lengths = tuple(
                    len(
                        json.dumps(
                            item,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    )
                    for item in candidates
                )
                selected_shortest += int(lengths[selected_index] == min(lengths))
            else:
                singleton_states += 1
            selected = next(
                item for item in state.action_candidates if item.action_id == proposal.action_id
            )
            acquisition_distractors += sum(
                item.decision_kind == "acquire_public_input"
                and selected.decision_kind == "acquire_public_input"
                and item.target_source_symbols == selected.target_source_symbols
                and item.acquisition_mode != selected.acquisition_mode
                for item in state.action_candidates
            )
            operator_distractors += sum(
                item.decision_kind == "execute_public_operation"
                and selected.decision_kind == "execute_public_operation"
                and item.node_id == selected.node_id
                and item.operator_id != selected.operator_id
                for item in state.action_candidates
            )
            verification_distractors += sum(
                item.decision_kind == "verify_terminal_operation"
                and selected.decision_kind == "verify_terminal_operation"
                and item.evidence_reference_ids != selected.evidence_reference_ids
                for item in state.action_candidates
            )
            for variant in range(3):
                permuted = render_exact_canonical_action_prompt(
                    instruction=binding.record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=condition,
                    presentation_salt=f"{salt}|permutation|{variant}",
                    grammar=grammar,
                )
                variant_proposal = parse_prompt_only_reference_payload(permuted)
                if variant_proposal.action_id != proposal.action_id:
                    raise ValueError("Candidate order permutation changed semantic selection")
                permutation_matches += 1
            opaque = {
                item.action_id: opaque_action_id(item.action_id, salt=state.state_id)
                for item in state.action_candidates
            }
            if len(set(opaque.values())) != len(opaque) or any(
                len(key) != len(value) for key, value in opaque.items()
            ):
                raise ValueError("opaque action-ID relabeling is not bijective and length neutral")
            opaque_prompt = _opaque_relabel_prompt(prompt, opaque)
            opaque_selected = _select_prompt_candidate_without_action_id(opaque_prompt)
            if opaque_selected["action_id"] != opaque[proposal.action_id] or _candidate_semantics(
                opaque_selected
            ) != _candidate_semantics(id_free_selected):
                raise ValueError("opaque action-ID relabeling changed semantic selection")
            opaque_decision_matches += 1
            inverse_opaque = {value: key for key, value in opaque.items()}
            canonical_proposal = make_canonical_action_proposal(
                state_id=state.state_id,
                action_id=inverse_opaque[str(opaque_selected["action_id"])],
                decision_kind=opaque_selected["decision_kind"],
            )
            canonical_result = evaluate_canonical_action_proposal(
                state,
                canonical_proposal,
                call_index=len(observations) + 1,
            )
            if (
                canonical_result.rejection is not None
                or canonical_result.commit is None
                or canonical_result.commit.call != expected_call
            ):
                raise ValueError("audit-only opaque relabeling did not preserve exact Commit")
            opaque_commit_matches += 1
            opaque_matches += 1
            abi_prompt = render_exact_canonical_action_abi_rescue_prompt(
                prompt,
                failure_family="response_serialization_failure",
                failure_subtype="canonical_action_not_exact_four_field_grammar",
            )
            if parse_prompt_only_reference_payload(abi_prompt).action_id != proposal.action_id:
                raise ValueError("ABI Rescue changed semantic selection")
            rejected_proposal = make_canonical_action_proposal(
                state_id=state.state_id,
                action_id=proposal.action_id,
                decision_kind=_different_decision(proposal.decision_kind),
            )
            rejected = evaluate_canonical_action_proposal(
                state,
                rejected_proposal,
                call_index=len(observations) + 1,
            )
            if rejected.rejection is None or rejected.commit is not None or rejected.job_terminal:
                raise ValueError("synthetic semantic rejection did not remain nonterminal")
            recovery_state = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=(rejected.rejection,),
            )
            recovery_prompt = render_exact_canonical_action_semantic_recovery_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=recovery_state,
                public_path_condition=condition,
                presentation_salt=f"{salt}|semantic-recovery",
            )
            recovered_proposal = parse_prompt_only_reference_payload(recovery_prompt)
            recovered = evaluate_canonical_action_proposal(
                recovery_state,
                recovered_proposal,
                call_index=len(observations) + 1,
            )
            if recovered.commit is None or recovered.commit.call != expected_call:
                raise ValueError("semantic Recovery did not preserve exact Compiler action")
            states.append(state)
            primary_prompts.append(prompt)
            abi_prompts.append(abi_prompt)
            recovery_prompts.append(recovery_prompt)
            proposals.append(proposal)
            expected_calls.append(expected_call)
            if logical_index < len(tool_steps):
                observations.append(
                    AgentToolObservation.model_validate(tool_steps[logical_index].observation)
                )
        final_prompt = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )

        def request_bound(value: str) -> int:
            return len(value.encode("utf-8")) + 256 + 16385

        static_upper = sum(request_bound(item) for item in primary_prompts)
        static_upper += request_bound(final_prompt)
        static_upper += max(request_bound(item) for item in abi_prompts)
        static_upper += max(request_bound(item) for item in recovery_prompts)
        materials.append(
            _PathMaterial(
                predecessor_path=predecessor_path,
                binding=binding,
                states=tuple(states),
                primary_prompts=tuple(primary_prompts),
                abi_rescue_prompts=tuple(abi_prompts),
                semantic_recovery_prompts=tuple(recovery_prompts),
                proposals=tuple(proposals),
                expected_calls=tuple(expected_calls),
                final_answer_prompt=final_prompt,
                static_upper_bound=static_upper,
            )
        )
    if (
        len(materials) != 48
        or completeness != 324
        or acceptance != 324
        or permutation_matches != 972
        or id_free_matches != 324
        or opaque_matches != 324
        or opaque_decision_matches != 324
        or opaque_commit_matches != 324
    ):
        raise ValueError("v26.118 Candidate-space denominator changed")
    values = {
        "candidate_count_rows": tuple(
            CandidateCountRow(candidate_count=count, state_count=states)
            for count, states in sorted(candidate_counts.items())
        ),
        "total_visible_candidate_count": total_candidates,
        "minimum_candidate_count": min(candidate_counts),
        "maximum_candidate_count": max(candidate_counts),
        "maximum_candidate_list_utf8_bytes": max_candidate_bytes,
        "multi_candidate_state_count": multi_states,
        "singleton_state_count": singleton_states,
        "legal_distractor_count": distractors,
        "alternate_acquisition_mode_distractor_count": acquisition_distractors,
        "alternate_operator_distractor_count": operator_distractors,
        "alternate_verification_subset_distractor_count": verification_distractors,
        "reference_action_first_in_multi_candidate_state_count": selected_first,
        "reference_action_shortest_in_multi_candidate_state_count": selected_shortest,
        "reference_action_position_count": len(selected_positions),
        "id_free_reference_policy_match_count": id_free_matches,
        "opaque_id_substitution_trial_count": opaque_matches,
        "opaque_id_substitution_pass_count": opaque_matches,
        "opaque_id_static_decision_match_count": opaque_decision_matches,
        "opaque_id_canonical_commit_match_count": opaque_commit_matches,
        "uniform_content_address_shape_pass_count": shape_passes,
    }
    return tuple(materials), values


def _candidate_source_dependency_audit(implementation_root: Path) -> tuple[int, int, int]:
    module_path = implementation_root / SEMANTIC_PROTOCOL_PATH
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden = {
        "correct_answer",
        "gold_evidence_ids",
        "oracle",
        "oracle_program",
        "reference_workflow",
        "target_evidence_ids",
        "target_quotient_state",
    }
    audited_names = {
        "_base_action_candidates",
        "_blocked_calls",
        "_document_references",
        "_load_contracts",
        "_operation_frontier",
        "_source_references",
        "build_semantic_action_state",
    }
    audited_functions = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in audited_names
    )
    forbidden_reads = 0
    for function in audited_functions:
        for node in ast.walk(function):
            value: str | None = None
            if isinstance(node, ast.Attribute):
                value = node.attr
            elif isinstance(node, ast.Name):
                value = node.id
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
            forbidden_reads += int(value is not None and value.casefold() in forbidden)
    signature = inspect.signature(build_semantic_action_state)
    expected = ("task", "environment", "observations", "semantic_rejections", "stage_tool_ids")
    signature_pass = int(tuple(signature.parameters) == expected)
    return signature_pass, len(audited_functions), forbidden_reads


def _reidentity_state(raw: dict[str, Any]) -> SemanticActionState:
    raw = dict(raw)
    raw["state_id"] = canonical_hash(
        {key: value for key, value in raw.items() if key != "state_id"},
        prefix="prospective_semantic_action_state:",
    )
    return SemanticActionState.model_validate(raw)


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except (ValueError, TypeError):
        return MutationResult(name=name)
    raise ValueError(f"v26.118 destructive mutation passed: {name}")


def _candidate_mutation_state(
    state: SemanticActionState, *, correct_only: bool
) -> SemanticActionState:
    raw = state.model_dump(mode="json")
    candidates = list(raw["action_candidates"])
    if len(candidates) < 2:
        raise ValueError("Candidate mutation fixture requires a distractor")
    raw["action_candidates"] = candidates[:1] if correct_only else candidates[1:]
    return _reidentity_state(raw)


def _build_candidate_audit(
    materials: Sequence[_PathMaterial],
    raw_values: Mapping[str, Any],
    grammar: SemanticActionResponseGrammar,
    implementation_root: Path,
) -> tuple[CandidateSpaceAuthorityAudit, SemanticActionState]:
    signature_pass, audited_functions, forbidden_reads = _candidate_source_dependency_audit(
        implementation_root
    )
    multi_state = next(
        state
        for material in materials
        for state in material.states
        if len(state.action_candidates) > 1
    )
    dropped = _candidate_mutation_state(multi_state, correct_only=False)
    correct_only = _candidate_mutation_state(multi_state, correct_only=True)
    dropped_rejected = False
    correct_only_rejected = False
    try:
        validate_candidate_space_completeness(dropped)
    except ValueError:
        dropped_rejected = True
    try:
        validate_candidate_space_completeness(correct_only)
    except ValueError:
        correct_only_rejected = True
    values = {
        "response_grammar_id": grammar.grammar_id,
        "public_input_signature_pass_count": signature_pass,
        "candidate_builder_scoped_function_audit_count": audited_functions,
        "forbidden_candidate_builder_symbol_read_count": forbidden_reads,
        "independent_complete_enumeration_pass_count": 324,
        "visible_acceptance_equality_pass_count": 324,
        **dict(raw_values),
        "dropped_distractor_mutation_rejected": dropped_rejected,
        "correct_only_candidate_mutation_rejected": correct_only_rejected,
    }
    provisional = CandidateSpaceAuthorityAudit.model_construct(audit_id="pending", **values)
    return (
        CandidateSpaceAuthorityAudit(
            audit_id=_identity(provisional, "audit_id", "finance_v26_candidate_space_authority:"),
            **values,
        ),
        multi_state,
    )


def _build_resource(
    historical: Any,
    grammar: SemanticActionResponseGrammar,
    materials: Sequence[_PathMaterial],
) -> SemanticActionResourceContract:
    maximum = max(item.static_upper_bound for item in materials)
    rollout = math.ceil((maximum + 20000) / 20000) * 20000
    values = {
        "stage_one_profile_id": historical.stage_one.profile_id,
        "stage_two_profile_id": historical.stage_two.profile_id,
        "response_grammar_id": grammar.grammar_id,
        "qualified_maximum_primary_prompt_utf8_bytes": max(
            len(prompt.encode("utf-8"))
            for material in materials
            for prompt in material.primary_prompts
        ),
        "qualified_maximum_abi_rescue_prompt_utf8_bytes": max(
            len(prompt.encode("utf-8"))
            for material in materials
            for prompt in material.abi_rescue_prompts
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": max(
            len(prompt.encode("utf-8"))
            for material in materials
            for prompt in material.semantic_recovery_prompts
        ),
        "qualified_maximum_final_answer_prompt_utf8_bytes": max(
            len(material.final_answer_prompt.encode("utf-8")) for material in materials
        ),
        "maximum_static_complete_path_bound_tokens": maximum,
        "rollout_upper_bound_tokens": rollout,
        "minimum_static_headroom_tokens": rollout - maximum,
    }
    provisional = SemanticActionResourceContract.model_construct(contract_id="pending", **values)
    return SemanticActionResourceContract(
        contract_id=_identity(
            provisional, "contract_id", "finance_v26_semantic_action_resource_contract:"
        ),
        **values,
    )


def _build_tasks(
    historical: Any,
    grammar: SemanticActionResponseGrammar,
    candidate: CandidateSpaceAuthorityAudit,
    resource: SemanticActionResourceContract,
) -> tuple[SemanticActionTaskPackage, ...]:
    rows = []
    for old in historical.tasks:
        values = {
            "predecessor_task_package_id": old.task_package_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "source_role": old.source_role,
            "mechanism_id": old.mechanism_id,
            "operational_record_id": old.operational_record_id,
            "operational_task_package_id": old.operational_task_package_id,
            "environment_manifest_id": old.environment_manifest_id,
            "semantic_source_id": old.semantic_source_id,
            "stage_one_profile_id": historical.stage_one.profile_id,
            "stage_two_profile_id": historical.stage_two.profile_id,
            "response_grammar_id": grammar.grammar_id,
            "candidate_space_authority_audit_id": candidate.audit_id,
            "verifier_v3_contract_id": old.verifier_v3_contract_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = SemanticActionTaskPackage.model_construct(task_package_id="pending", **values)
        rows.append(
            SemanticActionTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_semantic_action_task_package:",
                ),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.task_package_id))


def _build_paths(
    historical: Any,
    grammar: SemanticActionResponseGrammar,
    resource: SemanticActionResourceContract,
    tasks: Sequence[SemanticActionTaskPackage],
    materials: Sequence[_PathMaterial],
) -> tuple[SemanticActionPathAudit, ...]:
    task_by_old = {item.predecessor_task_package_id: item for item in tasks}
    rows = []
    for material in materials:
        old = next(
            item
            for item in historical.paths
            if item.predecessor_path_audit_id == material.predecessor_path.audit_id
        )
        task = task_by_old[old.task_package_id]
        all_prompts = (*material.primary_prompts, material.final_answer_prompt)
        values = {
            "predecessor_path_audit_id": old.path_audit_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old.task_package_id,
            "compiler_trajectory_id": old.compiler_trajectory_id,
            "role": old.role,
            "mechanism_id": old.mechanism_id,
            "path_strategy_id": old.path_strategy_id,
            "stage_one_profile_id": historical.stage_one.profile_id,
            "stage_two_profile_id": historical.stage_two.profile_id,
            "response_grammar_id": grammar.grammar_id,
            "resource_contract_id": resource.contract_id,
            "compiler_tool_call_count": old.compiler_tool_call_count,
            "semantic_action_request_count": len(material.primary_prompts),
            "primary_stage_one_request_count": len(all_prompts),
            "maximum_stage_one_provider_calls_with_recovery": len(all_prompts) + 2,
            "stage_two_commit_count": len(material.primary_prompts),
            "primary_prompt_sha256s": tuple(
                hashlib.sha256(item.encode("utf-8")).hexdigest()
                for item in material.primary_prompts
            ),
            "final_answer_prompt_sha256": hashlib.sha256(
                material.final_answer_prompt.encode("utf-8")
            ).hexdigest(),
            "maximum_primary_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in all_prompts
            ),
            "maximum_abi_rescue_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in material.abi_rescue_prompts
            ),
            "maximum_semantic_recovery_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in material.semantic_recovery_prompts
            ),
            "maximum_candidate_list_utf8_bytes": max(
                candidate_prompt_utf8_bytes(item) for item in material.primary_prompts
            ),
            "maximum_candidate_count": max(len(item.action_candidates) for item in material.states),
            "maximum_blocked_action_count": max(
                len(item.blocked_actions) for item in material.states
            ),
            "static_complete_path_upper_bound_tokens": material.static_upper_bound,
            "static_rollout_headroom_tokens": (
                resource.rollout_upper_bound_tokens - material.static_upper_bound
            ),
        }
        provisional = SemanticActionPathAudit.model_construct(path_audit_id="pending", **values)
        rows.append(
            SemanticActionPathAudit(
                path_audit_id=_identity(
                    provisional,
                    "path_audit_id",
                    "finance_v26_semantic_action_path_audit:",
                ),
                **values,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.path_audit_id))


def _build_contract_manifest(
    replay: SourceReplayAudit,
    historical: Any,
    grammar: SemanticActionResponseGrammar,
    candidate: CandidateSpaceAuthorityAudit,
    resource: SemanticActionResourceContract,
    tasks: Sequence[SemanticActionTaskPackage],
    paths: Sequence[SemanticActionPathAudit],
) -> tuple[SemanticActionExecutionContract, SemanticActionManifest]:
    contract_values = {
        "source_replay_audit_id": replay.audit_id,
        "response_grammar_id": grammar.grammar_id,
        "candidate_space_authority_audit_id": candidate.audit_id,
        "stage_one_profile_id": historical.stage_one.profile_id,
        "stage_two_profile_id": historical.stage_two.profile_id,
        "resource_contract_id": resource.contract_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in tasks)),
        "path_audit_ids": tuple(sorted(item.path_audit_id for item in paths)),
    }
    provisional_contract = SemanticActionExecutionContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = SemanticActionExecutionContract(
        contract_id=_identity(
            provisional_contract,
            "contract_id",
            "finance_v26_semantic_action_execution_contract:",
        ),
        **contract_values,
    )
    task_by_old = {item.predecessor_task_package_id: item for item in tasks}
    path_by_old = {item.predecessor_path_audit_id: item for item in paths}
    jobs = []
    for old in historical.manifest.jobs:
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
            "stage_one_profile_id": historical.stage_one.profile_id,
            "stage_two_profile_id": historical.stage_two.profile_id,
            "response_grammar_id": grammar.grammar_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = SemanticActionJob.model_construct(job_id="pending", **values)
        jobs.append(
            SemanticActionJob(
                job_id=_identity(provisional, "job_id", "finance_v26_semantic_action_job:"),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    manifest_values = {
        "contract_id": contract.contract_id,
        "response_grammar_id": grammar.grammar_id,
        "stage_one_profile_id": historical.stage_one.profile_id,
        "stage_two_profile_id": historical.stage_two.profile_id,
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
    provisional_manifest = SemanticActionManifest.model_construct(
        manifest_id="pending", **manifest_values
    )
    manifest = SemanticActionManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_semantic_action_manifest:",
        ),
        **manifest_values,
    )
    return contract, manifest


def _build_cross(
    historical: Any,
    grammar: SemanticActionResponseGrammar,
    resource: SemanticActionResourceContract,
    tasks: Sequence[SemanticActionTaskPackage],
    paths: Sequence[SemanticActionPathAudit],
    contract: SemanticActionExecutionContract,
    manifest: SemanticActionManifest,
) -> CrossArtifactBindingAudit:
    old_tasks = {item.task_package_id: item for item in historical.tasks}
    old_paths = {item.path_audit_id: item for item in historical.paths}
    old_jobs = {item.job_id: item for item in historical.manifest.jobs}
    source_matches = sum(
        item.source_task_artifact_id
        == old_tasks[item.predecessor_task_package_id].source_task_artifact_id
        and item.semantic_source_id
        == old_tasks[item.predecessor_task_package_id].semantic_source_id
        for item in tasks
    )
    path_matches = sum(
        item.compiler_trajectory_id
        == old_paths[item.predecessor_path_audit_id].compiler_trajectory_id
        and item.path_strategy_id == old_paths[item.predecessor_path_audit_id].path_strategy_id
        for item in paths
    )
    job_matches = sum(
        item.job_seed == old_jobs[item.predecessor_job_id].job_seed
        and item.path_strategy_id == old_jobs[item.predecessor_job_id].path_strategy_id
        for item in manifest.jobs
    )
    bound = sum(
        item.response_grammar_id == grammar.grammar_id
        and item.resource_contract_id == resource.contract_id
        for item in (*tasks, *paths, *manifest.jobs)
    )
    values = {
        "source_projection_match_count": source_matches,
        "path_projection_match_count": path_matches,
        "job_assignment_and_seed_match_count": job_matches,
        "profile_protocol_grammar_resource_binding_pass_count": bound,
        "task_identity_overlap_with_v26_112": len(
            {item.task_package_id for item in tasks} & set(old_tasks)
        ),
        "path_identity_overlap_with_v26_112": len(
            {item.path_audit_id for item in paths} & set(old_paths)
        ),
        "job_identity_overlap_with_v26_112": len(
            {item.job_id for item in manifest.jobs} & set(old_jobs)
        ),
    }
    if (
        contract.task_package_ids != tuple(sorted(item.task_package_id for item in tasks))
        or contract.path_audit_ids != tuple(sorted(item.path_audit_id for item in paths))
        or manifest.contract_id != contract.contract_id
    ):
        raise ValueError("v26.118 cross-artifact parent binding changed")
    provisional = CrossArtifactBindingAudit.model_construct(audit_id="pending", **values)
    return CrossArtifactBindingAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_semantic_action_cross_binding:"),
        **values,
    )


def _build_destructive(
    grammar: SemanticActionResponseGrammar,
    resource: SemanticActionResourceContract,
    task: SemanticActionTaskPackage,
    path: SemanticActionPathAudit,
    contract: SemanticActionExecutionContract,
    job: SemanticActionJob,
    manifest: SemanticActionManifest,
    multi_state: SemanticActionState,
) -> DestructiveAudit:
    proposal = make_canonical_action_proposal(
        state_id=multi_state.state_id,
        action_id=multi_state.action_candidates[0].action_id,
        decision_kind=multi_state.action_candidates[0].decision_kind,
    )
    payload = {
        "state_id": proposal.state_id,
        "action_id": proposal.action_id,
        "decision_kind": proposal.decision_kind,
        "protocol": RESPONSE_PROTOCOL_VERSION,
    }

    def stale(model: BaseModel, **updates: Any) -> BaseModel:
        raw = model.model_dump(mode="json")
        raw.update(updates)
        return type(model).model_validate(raw)

    mutations = (
        _expect_rejection(
            "candidate_correct_only",
            lambda: validate_candidate_space_completeness(
                _candidate_mutation_state(multi_state, correct_only=True)
            ),
        ),
        _expect_rejection(
            "candidate_distractor_deleted",
            lambda: validate_candidate_space_completeness(
                _candidate_mutation_state(multi_state, correct_only=False)
            ),
        ),
        _expect_rejection(
            "candidate_private_oracle_field",
            lambda: stale(
                multi_state.action_candidates[0],
                oracle_program="operation_stage_01",
            ),
        ),
        _expect_rejection(
            "execution_contract_authorized_early",
            lambda: stale(contract, execution_authorized=True),
        ),
        _expect_rejection(
            "execution_contract_open_construction_claim",
            lambda: stale(contract, open_semantic_action_construction_claim_authorized=True),
        ),
        _expect_rejection(
            "job_contract_parent_changed",
            lambda: stale(job, contract_id="finance_v26_semantic_action_execution_contract:x"),
        ),
        _expect_rejection(
            "job_identity_reused",
            lambda: stale(job, job_id=job.predecessor_job_id),
        ),
        _expect_rejection(
            "manifest_authorized_early",
            lambda: stale(manifest, execution_authorized=True),
        ),
        _expect_rejection(
            "path_resource_parent_changed",
            lambda: stale(path, resource_contract_id="finance_v26_semantic_action_resource:x"),
        ),
        _expect_rejection(
            "resource_bound_not_static_derived",
            lambda: stale(resource, bound_derived_before_provider_behavior=False),
        ),
        _expect_rejection(
            "resource_completion_bound_changed",
            lambda: stale(resource, exact_request_completion_bound_tokens=32768),
        ),
        _expect_rejection(
            "resource_recovery_counters_coupled",
            lambda: stale(resource, abi_rescue_and_semantic_recovery_reserves_separate=False),
        ),
        _expect_rejection(
            "resource_rollout_bound_changed",
            lambda: stale(
                resource,
                rollout_upper_bound_tokens=resource.rollout_upper_bound_tokens + 1,
            ),
        ),
        _expect_rejection(
            "response_action_id_missing",
            lambda: parse_exact_canonical_action_payload(
                {key: value for key, value in payload.items() if key != "action_id"}
            ),
        ),
        _expect_rejection(
            "response_extra_stage",
            lambda: parse_exact_canonical_action_payload(
                {**payload, "stage": "semantic_decision_proposal"}
            ),
        ),
        _expect_rejection(
            "response_protocol_changed",
            lambda: parse_exact_canonical_action_payload({**payload, "protocol": "changed"}),
        ),
        _expect_rejection(
            "response_wrapper_added",
            lambda: parse_exact_canonical_action_payload({"proposal": payload}),
        ),
        _expect_rejection(
            "stage_two_provider_route",
            lambda: stale(contract, stage_two_provider_calls=1),
        ),
        _expect_rejection(
            "task_candidate_authority_parent_changed",
            lambda: stale(task, candidate_space_authority_audit_id="changed"),
        ),
        _expect_rejection(
            "wrong_response_grammar_identity",
            lambda: stale(grammar, grammar_id="prospective_semantic_action_response_grammar:x"),
        ),
    )
    values = {"mutations": tuple(sorted(mutations, key=lambda item: item.name))}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_rematerialization_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    raw = _load_json(path)
    if not isinstance(raw, list):
        raise ValueError("v26.118 model collection is not a list")
    return tuple(model.model_validate(item) for item in raw)


def load_semantic_action_static_inputs(
    package_root: Path,
    implementation_root: Path,
) -> SemanticActionStaticInputs:
    root = implementation_root / OUTPUT_DIR
    report = SemanticActionRematerializationReport.model_validate(_load_json(root / "report.json"))
    contract = SemanticActionExecutionContract.model_validate(
        _load_json(root / "semantic_action_execution_contract.json")
    )
    manifest = SemanticActionManifest.model_validate(
        _load_json(root / "semantic_action_job_manifest.json")
    )
    resource = SemanticActionResourceContract.model_validate(
        _load_json(root / "semantic_action_resource_contract.json")
    )
    grammar = SemanticActionResponseGrammar.model_validate(
        _load_json(root / "semantic_action_response_grammar.json")
    )
    tasks = tuple(
        SemanticActionTaskPackage.model_validate(item)
        for item in _load_json(root / "semantic_action_task_packages.json")
    )
    paths = tuple(
        SemanticActionPathAudit.model_validate(item)
        for item in _load_json(root / "semantic_action_path_audits.json")
    )
    historical, _ = load_exact_grammar_static_inputs(package_root, implementation_root)
    if (
        report.execution_contract_id != contract.contract_id
        or report.manifest_id != manifest.manifest_id
        or report.resource_contract_id != resource.contract_id
        or report.response_grammar_id != grammar.grammar_id
        or manifest.contract_id != contract.contract_id
        or contract.resource_contract_id != resource.contract_id
        or contract.response_grammar_id != grammar.grammar_id
        or report.next_permitted_stage != NEXT_STAGE
        or report.execution_authorized
    ):
        raise ValueError("v26.118 static identity chain changed")
    return SemanticActionStaticInputs(
        report=report,
        contract=contract,
        manifest=manifest,
        resource=resource,
        grammar=grammar,
        tasks=tasks,
        paths=paths,
        stage_one=historical.stage_one,
        stage_two=historical.stage_two,
        agent_model_config=historical.agent_model_config,
        historical=historical,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> SemanticActionRematerializationReport:
    replay, predecessor = _build_source_replay(package_root, implementation_root)
    if predecessor.next_permitted_stage != (
        "fresh_semantic_action_protocol_taskpackage_contract_manifest_and_runner_preflight_only"
    ):
        raise ValueError("v26.118 predecessor transition changed")
    historical, _ = load_exact_grammar_static_inputs(package_root, implementation_root)
    grammar = compile_semantic_action_response_grammar()
    materials, candidate_values = _build_materials(historical, grammar)
    candidate, multi_state = _build_candidate_audit(
        materials,
        candidate_values,
        grammar,
        implementation_root,
    )
    resource = _build_resource(historical, grammar, materials)
    tasks = _build_tasks(historical, grammar, candidate, resource)
    paths = _build_paths(historical, grammar, resource, tasks, materials)
    contract, manifest = _build_contract_manifest(
        replay,
        historical,
        grammar,
        candidate,
        resource,
        tasks,
        paths,
    )
    cross = _build_cross(
        historical,
        grammar,
        resource,
        tasks,
        paths,
        contract,
        manifest,
    )
    destructive = _build_destructive(
        grammar,
        resource,
        tasks[0],
        paths[0],
        contract,
        manifest.jobs[0],
        manifest,
        multi_state,
    )
    transition_provisional = ProspectiveTransitionContract.model_construct(contract_id="pending")
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            transition_provisional,
            "contract_id",
            "finance_v26_semantic_action_rematerialization_transition:",
        )
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", replay),
        ("semantic_action_response_grammar.json", grammar),
        ("candidate_space_authority_audit.json", candidate),
        ("semantic_action_resource_contract.json", resource),
        ("semantic_action_task_packages.json", [item.model_dump(mode="json") for item in tasks]),
        ("semantic_action_path_audits.json", [item.model_dump(mode="json") for item in paths]),
        ("semantic_action_execution_contract.json", contract),
        ("semantic_action_job_manifest.json", manifest),
        ("cross_artifact_binding_audit.json", cross),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": replay.audit_id,
        "response_grammar_id": grammar.grammar_id,
        "candidate_space_authority_audit_id": candidate.audit_id,
        "resource_contract_id": resource.contract_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "cross_artifact_binding_audit_id": cross.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = SemanticActionRematerializationReport.model_construct(
        report_id="pending", **values
    )
    report = SemanticActionRematerializationReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_semantic_action_rematerialization_report:",
        ),
        **values,
    )
    _write_json(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credential-free v26.118 Semantic Action rematerialization"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root", type=Path, default=Path(__file__).resolve().parents[4]
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
