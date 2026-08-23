from __future__ import annotations

import argparse
import json
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as static_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as predecessor_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingVerificationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = static_stage.PROSPECTIVE_EXECUTION_RUN_ID
PREFLIGHT_DIR: Final = preflight.OUTPUT_DIR
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_124_exact_final_semantic_action_calibration_execution_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_final_semantic_action_calibration_online.py"
)
EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_privacy_first_runner_preflight_report:"
    "85733321a455b6fe48d7065e85b3e0a77eb40de5a33f9673a41b9b1c2dd808f8"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_privacy_first_runner_source_replay:"
    "0ac972d842c153d56f427b33e9cac069ea6fd332c966b44813fa2ac63c8ac0ac"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_privacy_first_runner_contract:"
    "a1d2c225906c57742340cf34c07e6d8643bbc4ef293bcf357cecd29b13221a66"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_exact_final_outcome_measurement:"
    "60d018f6f0e9701cc2e5860ddad2649882bacbc4b30b30405fa9a764b1e975e9"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_privacy_first_runner_transition:"
    "60ff3fae5eba80f5a2ae7e27a20378e2ac5f1b950fa267a6cdb910df9c640c50"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_final_grammar_manifest:"
    "fd4d78efa9374fc3de91ccca1a8242b7a6bee4bdcf4052ac8bbf6428bd95a5ee"
)
EXPECTED_STATIC_CONTRACT_ID: Final = (
    "finance_v26_final_grammar_execution_contract:"
    "5532a1f1ca600979f7541770606e7ce0a3b65c4a93f88a659e52e14ff7d6e27e"
)
EXPECTED_RESOURCE_ID: Final = (
    "finance_v26_final_grammar_resource_contract:"
    "381e18dff5a538c50cc06aaae9c6c81d110d8214b8c7d3800820d4eb3f09e43c"
)
EXPECTED_FINAL_GRAMMAR_ID: Final = (
    "prospective_exact_final_response_grammar:"
    "5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403"
)
EXPECTED_ACTION_GRAMMAR_ID: Final = static_stage.EXPECTED_ACTION_GRAMMAR_ID
EXPECTED_CANDIDATE_AUDIT_ID: Final = static_stage.EXPECTED_CANDIDATE_AUDIT_ID
POSTRUN_STAGE: Final = "exact_final_semantic_action_calibration_postrun_audit_only"
PREFLIGHT_OUTPUTS: Final = (
    "certificate_usage_recovery_audit.json",
    "destructive_audit.json",
    "final_interface_control_audit.json",
    "outcome_measurement_contract.json",
    "privacy_first_capture_audit.json",
    "prospective_transition_contract.json",
    "report.json",
    "runner_binding_audit.json",
    "runner_contract.json",
    "runner_fixture_audit.json",
    "semantic_recovery_control_audit.json",
    "source_replay_audit.json",
)

TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "completion_unusable",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_123_transitive_source",
        "v26_123_output",
        "v26_124_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[2549] = 2549
    predecessor_output_file_count: Literal[12] = 12
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2562] = 2562
    replay_pass_count: Literal[2562] = 2562
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2562, max_length=2562)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_execution_source_replay.v1"] = (
        "finance_v26_exact_final_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2562:
            raise ValueError("v26.124 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.124 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_execution_source_replay:",
        ):
            raise ValueError("v26.124 source replay identity changed")
        return self


class PreexecutionValidityRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_scripted_provider_call_count: int = Field(gt=0, le=12)
    provider_envelope_count: int = Field(gt=0, le=12)
    public_payload_projection_count: int = Field(gt=0, le=12)
    semantic_choice_count: int = Field(gt=0, le=11)
    stage_two_commit_count: int = Field(gt=0, le=11)
    exact_two_field_final_payload_count: Literal[1] = 1
    replay_v3_passed: Literal[True] = True
    independent_validity_passed: Literal[True] = True
    mechanism_score_passed: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0


class PreexecutionValidityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    rows: tuple[PreexecutionValidityRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    completed_count: Literal[32] = 32
    replay_v3_pass_count: Literal[32] = 32
    independently_valid_count: Literal[32] = 32
    mechanism_success_count: Literal[32] = 32
    stage_one_scripted_provider_call_count: Literal[256] = 256
    provider_envelope_count: Literal[256] = 256
    public_payload_projection_count: Literal[256] = 256
    semantic_choice_count: Literal[224] = 224
    stage_two_commit_count: Literal[224] = 224
    exact_two_field_final_payload_count: Literal[32] = 32
    stage_two_provider_call_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_preexecution_validity.v1"] = (
        "finance_v26_exact_final_preexecution_validity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionValidityAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("v26.124 preexecution rows are not canonical")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_preexecution_validity:",
        ):
            raise ValueError("v26.124 preexecution validity identity changed")
        return self


class ExactFinalJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_measurement_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: str = Field(min_length=1)
    terminal_category: TerminalCategory
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None = None
    provider_call_count: int = Field(ge=0, le=12)
    provider_envelope_count: int = Field(ge=0, le=12)
    public_payload_projection_count: int = Field(ge=0, le=12)
    validated_public_payload_count: int = Field(ge=0, le=12)
    privacy_rejected_payload_count: int = Field(ge=0, le=12)
    provider_failure_no_payload_count: int = Field(ge=0, le=12)
    envelope_only_orphan_count: Literal[0] = 0
    projection_only_orphan_count: Literal[0] = 0
    http_success_call_count: int = Field(ge=0, le=12)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0, le=400000)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=1, le=12)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    semantic_response_payload_count: int = Field(ge=0, le=12)
    exact_four_field_action_payload_count: int = Field(ge=0, le=12)
    semantic_choice_count: int = Field(ge=0, le=11)
    visible_action_match_count: int = Field(ge=0, le=11)
    decision_kind_match_count: int = Field(ge=0, le=11)
    first_choice_acceptance_count: int = Field(ge=0, le=11)
    stage_two_commit_count: int = Field(ge=0, le=11)
    observation_count: int = Field(ge=0, le=10)
    successful_observation_count: int = Field(ge=0, le=10)
    failed_observation_count: int = Field(ge=0, le=10)
    public_progress_choice_count: int = Field(ge=0, le=10)
    program_node_progress_choice_count: int = Field(ge=0, le=10)
    choice_diagnostic_count: int = Field(ge=0, le=11)
    singleton_choice_count: int = Field(ge=0, le=11)
    multi_candidate_choice_count: int = Field(ge=0, le=11)
    candidate_count_distribution: dict[str, int]
    selected_prompt_only_reference_count: int = Field(ge=0, le=11)
    first_choice_present: bool
    first_action_id_legal: bool
    first_action_semantically_accepted: bool
    first_action_public_progress: bool
    first_action_candidate_count: int | None = Field(default=None, ge=1, le=8)
    first_action_zero_based_position: int | None = Field(default=None, ge=0, le=7)
    first_action_candidate_family: str | None = None
    first_action_prompt_only_reference: bool | None = None
    semantic_rejection_count: int = Field(ge=0, le=1)
    semantic_recovery_used: bool
    recovery_selected_different_action: bool
    recovery_committed: bool
    recovery_public_progress: bool
    legal_no_progress_choice_count: int = Field(ge=0, le=10)
    ordinary_replan_after_legal_no_progress_count: int = Field(ge=0, le=10)
    ordinary_replan_eventual_progress_count: int = Field(ge=0, le=10)
    terminal_verification_ready_choice_count: int = Field(ge=0, le=11)
    terminal_verification_choice_count: int = Field(ge=0, le=1)
    successful_terminal_verification_observation_count: int = Field(ge=0, le=1)
    final_commit_count: int = Field(ge=0, le=1)
    final_request_attempt_count: int = Field(ge=0, le=2)
    final_response_payload_count: int = Field(ge=0, le=2)
    exact_two_field_final_payload_count: int = Field(ge=0, le=1)
    final_primary_exact_payload: bool
    final_rescue_exact_payload: bool
    final_abi_crossed: bool
    final_answer_emitted: bool
    final_answer_semantically_valid: bool
    final_host_envelope_bound: bool
    rationale_summary_present: bool
    typed_no_call: bool
    completion_unusable: bool
    provider_transport_failure: bool
    instrument_failure: bool
    exact_model_passed: bool
    native_tool_absent: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absent: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    privacy_artifact_pairing_passed: bool
    rollout_budget_passed: bool
    rollout_headroom_tokens: int = Field(ge=0, le=400000)
    stage_two_provider_call_count: Literal[0] = 0
    reversible_commit_passed: bool
    repeated_call_signature_count: int = Field(ge=0)
    repeated_failed_call_signature_count: int = Field(ge=0)
    completed_program_node_count: int = Field(ge=0)
    program_node_count: int = Field(ge=0)
    program_closed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    mechanism_evaluated: bool
    mechanism_success: bool
    independent_validity: bool
    actual_route: str = Field(min_length=1)
    requested_path_adhered: bool
    replay_v3_passed: bool
    verification_report: AuthorityPreservingVerificationReport | None = None
    mechanism_outcome: MechanismEstimandOutcome
    choice_diagnostic_ids: tuple[str, ...]
    raw_execution_artifact: legacy.RawFileDescriptor
    engineering_calibration_only: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    training_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_exact_final_semantic_action_job_result.v1"] = (
        "finance_v26_exact_final_semantic_action_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> ExactFinalJobResult:
        if self.provider_reasoning_tokens > self.provider_completion_tokens:
            raise ValueError("v26.124 Reasoning Usage exceeds Completion Usage")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.124 Projection partition changed")
        if self.provider_envelope_count != self.provider_call_count or (
            self.public_payload_projection_count != self.provider_call_count
        ):
            raise ValueError("v26.124 complete Raw Provider denominator changed")
        if self.final_abi_crossed != bool(self.exact_two_field_final_payload_count):
            raise ValueError("v26.124 Final ABI accounting changed")
        if self.final_answer_emitted and not self.final_abi_crossed:
            raise ValueError("v26.124 Final answer bypassed the exact ABI")
        if self.final_answer_semantically_valid and not self.final_answer_emitted:
            raise ValueError("v26.124 Final semantic validity lacks an answer")
        if self.independent_validity != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("v26.124 valid-terminal accounting changed")
        if self.requested_path_adhered != (self.actual_route == self.requested_path_strategy_id):
            raise ValueError("v26.124 path-adherence accounting changed")
        if self.choice_diagnostic_count != len(self.choice_diagnostic_ids):
            raise ValueError("v26.124 Choice-diagnostic denominator changed")
        if self.first_choice_present != bool(self.semantic_choice_count):
            raise ValueError("v26.124 first-choice presence changed")
        if self.semantic_recovery_used != bool(self.semantic_recovery_attempt_count):
            raise ValueError("v26.124 Semantic Recovery accounting changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_exact_final_semantic_action_job_result:",
        ):
            raise ValueError("v26.124 Job-result identity changed")
        return self


class ExactFinalRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    job_result_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0, le=384)
    provider_envelope_count: int = Field(ge=0, le=384)
    public_payload_projection_count: int = Field(ge=0, le=384)
    complete_provider_pair_count: int = Field(ge=0, le=384)
    unique_provider_envelope_id_count: int = Field(ge=0, le=384)
    unique_payload_projection_id_count: int = Field(ge=0, le=384)
    validated_public_payload_count: int = Field(ge=0, le=384)
    privacy_rejected_payload_count: int = Field(ge=0, le=384)
    provider_failure_no_payload_count: int = Field(ge=0, le=384)
    envelope_only_orphan_count: Literal[0] = 0
    projection_only_orphan_count: Literal[0] = 0
    complete_raw_count: Literal[32] = 32
    whole_response_hash_for_privacy_rejection_count: int = Field(ge=0, le=384)
    file_count: int = Field(ge=32)
    files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=32)
    exact_byte_replay_pass_count: int = Field(ge=32)
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    invalid_payload_key_persistence_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_raw_lineage.v1"] = (
        "finance_v26_exact_final_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExactFinalRawLineageAudit:
        if (
            self.file_count != len(self.files)
            or self.exact_byte_replay_pass_count != self.file_count
            or self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_payload_projection_count
            or self.provider_call_count != self.complete_provider_pair_count
            or self.unique_provider_envelope_id_count != self.provider_call_count
            or self.unique_payload_projection_id_count != self.provider_call_count
            or self.provider_call_count
            != self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.124 Raw Lineage denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_exact_final_raw_lineage:",
        ):
            raise ValueError("v26.124 Raw Lineage identity changed")
        return self


class ExactFinalExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    outcome_measurement_contract_id: str = EXPECTED_OUTCOME_CONTRACT_ID
    preexecution_validity_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[32] = 32
    completed_job_result_count: Literal[32] = 32
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0, le=384)
    provider_envelope_count: int = Field(ge=0, le=384)
    public_payload_projection_count: int = Field(ge=0, le=384)
    validated_public_payload_count: int = Field(ge=0, le=384)
    privacy_rejected_payload_count: int = Field(ge=0, le=384)
    provider_failure_no_payload_count: int = Field(ge=0, le=384)
    envelope_only_orphan_count: Literal[0] = 0
    projection_only_orphan_count: Literal[0] = 0
    complete_raw_count: Literal[32] = 32
    http_success_call_count: int = Field(ge=0, le=384)
    provider_prompt_tokens: int = Field(ge=0)
    provider_completion_tokens: int = Field(ge=0)
    provider_reasoning_tokens: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=32, le=384)
    abi_rescue_attempt_count: int = Field(ge=0, le=32)
    semantic_recovery_attempt_count: int = Field(ge=0, le=32)
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    semantic_response_payload_count: int = Field(ge=0)
    exact_four_field_action_payload_count: int = Field(ge=0)
    semantic_choice_count: int = Field(ge=0)
    visible_action_id_match_count: int = Field(ge=0)
    decision_kind_match_count: int = Field(ge=0)
    first_choice_accepted_count: int = Field(ge=0)
    reversible_stage_two_commit_count: int = Field(ge=0)
    runtime_observation_count: int = Field(ge=0)
    successful_observation_count: int = Field(ge=0)
    failed_observation_count: int = Field(ge=0)
    public_progress_choice_count: int = Field(ge=0)
    program_node_progress_choice_count: int = Field(ge=0)
    candidate_choice_count: int = Field(ge=0)
    singleton_choice_count: int = Field(ge=0)
    multi_candidate_choice_count: int = Field(ge=0)
    candidate_count_distribution: dict[str, int]
    decision_load_summaries: tuple[predecessor_online.DecisionLoadSummary, ...]
    selected_prompt_only_reference_count: int = Field(ge=0)
    first_choice_present_job_count: int = Field(ge=0, le=32)
    first_action_id_legal_job_count: int = Field(ge=0, le=32)
    first_action_semantically_accepted_job_count: int = Field(ge=0, le=32)
    first_action_public_progress_job_count: int = Field(ge=0, le=32)
    semantic_rejection_count: int = Field(ge=0, le=32)
    semantic_recovery_job_count: int = Field(ge=0, le=32)
    recovery_selected_different_action_job_count: int = Field(ge=0, le=32)
    recovery_committed_job_count: int = Field(ge=0, le=32)
    recovery_public_progress_job_count: int = Field(ge=0, le=32)
    legal_no_progress_choice_count: int = Field(ge=0)
    ordinary_replan_after_legal_no_progress_count: int = Field(ge=0)
    ordinary_replan_eventual_progress_count: int = Field(ge=0)
    terminal_verification_choice_count: int = Field(ge=0, le=32)
    successful_terminal_verification_observation_count: int = Field(ge=0, le=32)
    final_commit_count: int = Field(ge=0, le=32)
    final_request_attempt_count: int = Field(ge=0, le=64)
    final_response_payload_count: int = Field(ge=0, le=64)
    exact_two_field_final_payload_count: int = Field(ge=0, le=32)
    final_primary_exact_payload_job_count: int = Field(ge=0, le=32)
    final_rescue_exact_payload_job_count: int = Field(ge=0, le=32)
    final_abi_crossed_job_count: int = Field(ge=0, le=32)
    final_answer_emitted_job_count: int = Field(ge=0, le=32)
    final_answer_semantically_valid_job_count: int = Field(ge=0, le=32)
    typed_no_call_job_count: int = Field(ge=0, le=32)
    completion_unusable_job_count: int = Field(ge=0, le=32)
    provider_transport_failure_job_count: int = Field(ge=0, le=32)
    instrument_failure_job_count: int = Field(ge=0, le=32)
    model_invalid_trajectory_count: int = Field(ge=0, le=32)
    program_closed_count: int = Field(ge=0, le=32)
    terminal_node_completed_count: int = Field(ge=0, le=32)
    postterminal_verification_completed_count: int = Field(ge=0, le=32)
    mechanism_success_count: int = Field(ge=0, le=32)
    independently_valid_trajectory_count: int = Field(ge=0, le=32)
    requested_path_adherence_count: int = Field(ge=0, le=32)
    cell_summaries: tuple[predecessor_online.SemanticActionCellSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    exact_model_passed: bool
    native_tool_absence_passed: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absence_passed: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    privacy_artifact_pairing_passed: bool
    empirical_budget_adequacy_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    stage_two_authority_passed: bool
    replay_v3_passed: bool
    exact_denominator_complete: Literal[True] = True
    first_choice_failure_retained_after_eventual_success: Literal[True] = True
    invalid_action_and_legal_no_progress_kept_separate: Literal[True] = True
    final_abi_and_answer_semantics_kept_separate: Literal[True] = True
    privacy_rejection_kept_in_model_and_resource_denominator: Literal[True] = True
    whole_response_hash_is_not_private_reasoning_field_hash: Literal[True] = True
    measured_object: Literal[
        "canonical_semantic_action_through_exact_final_answer_independent_validity"
    ] = "canonical_semantic_action_through_exact_final_answer_independent_validity"
    same_distribution_as_v26_120_or_v26_114_claimed: Literal[False] = False
    engineering_calibration_only: Literal[True] = True
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    execution_status: Literal["completed_pending_independent_audit"] = (
        "completed_pending_independent_audit"
    )
    next_permitted_stage: Literal["exact_final_semantic_action_calibration_postrun_audit_only"] = (
        POSTRUN_STAGE
    )
    schema_version: Literal["finance_v26_exact_final_semantic_action_execution_report.v1"] = (
        "finance_v26_exact_final_semantic_action_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ExactFinalExecutionReport:
        if sum(self.terminal_counts.values()) != 32:
            raise ValueError("v26.124 terminal denominator changed")
        if self.candidate_choice_count != (
            self.singleton_choice_count + self.multi_candidate_choice_count
        ):
            raise ValueError("v26.124 Candidate choice partition changed")
        if self.provider_call_count != (
            self.validated_public_payload_count
            + self.privacy_rejected_payload_count
            + self.provider_failure_no_payload_count
        ):
            raise ValueError("v26.124 Projection aggregate changed")
        if (
            self.provider_call_count != self.provider_envelope_count
            or self.provider_call_count != self.public_payload_projection_count
        ):
            raise ValueError("v26.124 privacy-first aggregate denominator changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_exact_final_semantic_action_execution_report:",
        ):
            raise ValueError("v26.124 execution-report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: ExecutionSourceReplayAudit
    preflight_report: preflight.PrivacyFirstRunnerPreflightReport
    runner_contract: runner.PrivacyFirstRunnerContract
    outcome_contract: preflight.OutcomeMeasurementContract
    transition_contract: preflight.ProspectiveTransitionContract
    preexecution_validity: PreexecutionValidityAudit
    static: static_stage.FinalGrammarStaticInputs


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
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
        if candidate.is_file() and legacy.sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.124 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    runner_preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    predecessor = preflight.RunnerSourceReplayAudit.model_validate(
        _load(runner_preflight_dir / "source_replay_audit.json")
    )
    report = preflight.PrivacyFirstRunnerPreflightReport.model_validate(
        _load(runner_preflight_dir / "report.json")
    )
    if (
        predecessor.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
    ):
        raise ValueError("v26.124 predecessor replay identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_123_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.124 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = runner_preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.124 predecessor output is missing: {name}")
        observed = legacy.sha256_file(path)
        if name != "report.json":
            expected = details[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.124 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_123_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = legacy.sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_124_implementation",
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=implementation_path.stat().st_size,
    )
    values: dict[str, Any] = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_execution_source_replay:",
        ),
        **values,
    )


def build_preexecution_validity_audit(
    *,
    static: static_stage.FinalGrammarStaticInputs,
    contract: runner.PrivacyFirstRunnerContract,
) -> PreexecutionValidityAudit:
    rows: list[PreexecutionValidityRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_124_preexecution_validity_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = runner.privacy_first_runtime_binding(static, job)
            raw = runner.execute_privacy_first_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=preflight.ScriptedPrivacyFirstClient(
                    static.agent_model_config,
                    final_answer=binding.compiler_trajectory.final_answer,
                ),
                output_dir=root,
            )
            replay = legacy.replay_v3(
                cast(Any, raw),
                static=static.predecessor.historical,
                binding=binding,
            )
            verification, mechanism = preflight._completed_verification(
                raw=cast(Any, raw),
                replay=replay,
                binding=binding,
            )
            exact_final = sum(
                item.exact_two_field_final_payload
                for item in raw.attempts
                if item.request_kind == "final_answer"
            )
            if (
                raw.terminal_disposition != "completed"
                or raw.completed_result is None
                or not replay.passed
                or not verification.valid
                or not mechanism.success
                or raw.stage_two_provider_call_count
                or raw.privacy_rejected_payload_count
                or len(raw.provider_envelope_artifacts) != raw.stage_one_provider_call_count
                or len(raw.public_payload_projection_artifacts) != raw.stage_one_provider_call_count
                or exact_final != 1
            ):
                raise ValueError(f"v26.124 preexecution Independent Validity failed: {job.job_id}")
            rows.append(
                PreexecutionValidityRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_scripted_provider_call_count=raw.stage_one_provider_call_count,
                    provider_envelope_count=len(raw.provider_envelope_artifacts),
                    public_payload_projection_count=len(raw.public_payload_projection_artifacts),
                    semantic_choice_count=len(raw.semantic_choices),
                    stage_two_commit_count=len(raw.commits),
                    exact_two_field_final_payload_count=1,
                )
            )
    values: dict[str, Any] = {
        "rows": tuple(rows),
        "stage_one_scripted_provider_call_count": sum(
            item.stage_one_scripted_provider_call_count for item in rows
        ),
        "provider_envelope_count": sum(item.provider_envelope_count for item in rows),
        "public_payload_projection_count": sum(
            item.public_payload_projection_count for item in rows
        ),
        "semantic_choice_count": sum(item.semantic_choice_count for item in rows),
        "stage_two_commit_count": sum(item.stage_two_commit_count for item in rows),
        "exact_two_field_final_payload_count": sum(
            item.exact_two_field_final_payload_count for item in rows
        ),
    }
    provisional = PreexecutionValidityAudit.model_construct(audit_id="pending", **values)
    return PreexecutionValidityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_preexecution_validity:",
        ),
        **values,
    )


def prepare_execution(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> PreparedExecution:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        runner_preflight_dir=runner_preflight_dir,
    )
    runner.write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source.model_dump(mode="json"),
    )
    report = preflight.PrivacyFirstRunnerPreflightReport.model_validate(
        _load(runner_preflight_dir / "report.json")
    )
    contract = runner.PrivacyFirstRunnerContract.model_validate(
        _load(runner_preflight_dir / "runner_contract.json")
    )
    outcome = preflight.OutcomeMeasurementContract.model_validate(
        _load(runner_preflight_dir / "outcome_measurement_contract.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(runner_preflight_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.outcome_measurement_contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.status != "passed_exact_runner_preflight"
        or report.next_permitted_stage != "exact_final_semantic_action_calibration_execution_only"
        or report.exact_job_count != 32
        or report.provider_calls
        or report.stage_two_provider_calls
        or contract.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or not transition.provider_calls_authorized
        or not transition.only_exact_fresh_32_job_manifest_authorized
        or transition.next_permitted_stage
        != "exact_final_semantic_action_calibration_execution_only"
    ):
        raise ValueError("v26.124 predecessor authorization changed")
    static = static_stage.load_final_grammar_static_inputs(package_root, implementation_root)
    if (
        runner.make_privacy_first_runner_contract(static) != contract
        or static.manifest.manifest_id != EXPECTED_MANIFEST_ID
        or static.contract.contract_id != EXPECTED_STATIC_CONTRACT_ID
        or static.resource.contract_id != EXPECTED_RESOURCE_ID
        or static.final_grammar.grammar_id != EXPECTED_FINAL_GRAMMAR_ID
        or static.action_grammar.grammar_id != EXPECTED_ACTION_GRAMMAR_ID
        or static.contract.candidate_space_authority_audit_id != EXPECTED_CANDIDATE_AUDIT_ID
        or static.manifest.prospective_execution_run_id != RUN_ID
        or static.resource.rollout_upper_bound_tokens != 400000
        or len(static.manifest.jobs) != 32
        or len({item.job_id for item in static.manifest.jobs}) != 32
        or static.stage_two.provider_call_upper_bound != 0
    ):
        raise ValueError("v26.124 static execution denominator changed")
    preexecution = build_preexecution_validity_audit(static=static, contract=contract)
    outputs: tuple[tuple[str, Any], ...] = (
        ("runner_contract.json", contract),
        ("outcome_measurement_contract.json", outcome),
        ("frozen_final_grammar_job_manifest.json", static.manifest),
        ("frozen_semantic_action_response_grammar.json", static.action_grammar),
        ("frozen_exact_final_response_grammar.json", static.final_grammar),
        ("preexecution_independent_validity_audit.json", preexecution),
    )
    for name, value in outputs:
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        runner.write_json_atomic(output_dir / name, payload)
    return PreparedExecution(
        source_replay=source,
        preflight_report=report,
        runner_contract=contract,
        outcome_contract=outcome,
        transition_contract=transition,
        preexecution_validity=preexecution,
        static=static,
    )


def _provider_pairs(
    raw: runner.PrivacyFirstRawExecution,
    output_dir: Path,
) -> tuple[tuple[runner.PrivacyFirstProviderEnvelope, runner.PublicPayloadProjection], ...]:
    envelopes: list[runner.PrivacyFirstProviderEnvelope] = []
    projections: list[runner.PublicPayloadProjection] = []
    for descriptor in raw.provider_envelope_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or legacy.sha256_file(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.124 Provider Envelope binding changed")
        envelopes.append(runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = output_dir / descriptor.relative_path
        if (
            not path.is_file()
            or legacy.sha256_file(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.124 Payload Projection binding changed")
        projections.append(runner.PublicPayloadProjection.model_validate(_load(path)))
    if len(envelopes) != len(projections):
        raise ValueError("v26.124 Envelope/Projection denominator diverged")
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _choice_diagnostics(
    *,
    raw: runner.PrivacyFirstRawExecution,
    prepared: PreparedExecution,
    binding: Any,
) -> tuple[predecessor_online.ChoiceDiagnostic, ...]:
    adapter = SimpleNamespace(grammar=prepared.static.action_grammar)
    return predecessor_online.build_choice_diagnostics(
        raw=cast(Any, raw),
        static=cast(Any, adapter),
        binding=binding,
    )


def project_job_result(
    *,
    raw: runner.PrivacyFirstRawExecution,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[ExactFinalJobResult, tuple[predecessor_online.ChoiceDiagnostic, ...]]:
    binding = runner.privacy_first_runtime_binding(prepared.static, raw.job)
    replay = legacy.replay_v3(
        cast(Any, raw),
        static=prepared.static.predecessor.historical,
        binding=binding,
    )
    mechanism = evaluate_mechanism_estimand(
        cast(Any, binding.record),
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    verification: AuthorityPreservingVerificationReport | None = None
    if raw.completed_result is not None:
        verification, mechanism = preflight._completed_verification(
            raw=cast(Any, raw),
            replay=replay,
            binding=binding,
        )
    diagnostics = _choice_diagnostics(raw=raw, prepared=prepared, binding=binding)
    pairs = _provider_pairs(raw, output_dir)
    projection_counts = Counter(projection.projection_status for _, projection in pairs)
    exact_model, fallback_absent, native_absent, thinking, usage = (
        predecessor_online._telemetry_flags(raw.provider_telemetry)
    )
    dynamic = all(
        item.dynamic_certificate_id is not None and item.resource_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    exact_request = all(
        item.request_binding_certificate_id is not None
        for item in raw.attempts
        if item.provider_call_made
    )
    privacy_pairing = bool(
        len(pairs)
        == len(raw.provider_envelope_artifacts)
        == len(raw.public_payload_projection_artifacts)
        == raw.stage_one_provider_call_count
    )
    reversible = all(
        item.reversible_same_action_id_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    instrument = bool(
        raw.terminal_disposition == "instrument_failure"
        or not exact_model
        or not fallback_absent
        or not native_absent
        or not thinking
        or not usage
        or not dynamic
        or not exact_request
        or not privacy_pairing
        or not reversible
        or not replay.passed
        or raw.stage_two_provider_call_count
        or raw.cumulative_provider_tokens > 400000
    )
    transport = raw.terminal_disposition == "provider_transport_failure"
    typed = raw.terminal_disposition == "typed_budget_no_call"
    completion = raw.terminal_disposition == "completion_unusable"
    answer_semantically_valid = bool(verification is not None and verification.valid)
    valid = bool(
        answer_semantically_valid
        and not instrument
        and not transport
        and not typed
        and not completion
    )
    terminal: TerminalCategory
    if instrument:
        terminal = "instrument_failure"
    elif transport:
        terminal = "provider_transport_failure"
    elif typed:
        terminal = "typed_budget_no_call"
    elif completion:
        terminal = "completion_unusable"
    elif valid:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    semantic_attempts = tuple(
        item for item in raw.attempts if item.request_kind == "semantic_proposal"
    )
    final_attempts = tuple(item for item in raw.attempts if item.request_kind == "final_answer")
    completion_counts = Counter(
        str(item.completion_failure_type)
        for item in raw.attempts
        if item.completion_failure_type is not None
    )
    family_counts = Counter(
        str(item.failure_family) for item in raw.attempts if item.failure_family is not None
    )
    subtype_counts = Counter(
        str(item.failure_subtype) for item in raw.attempts if item.failure_subtype is not None
    )
    repeated, repeated_failed = predecessor_online._repetition_counts(raw.observations)
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        predecessor_online._progress_diagnostic(binding.record, raw.observations)
    )
    route = predecessor_online._actual_route(raw.observations)
    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    first_choice = raw.semantic_choices[0] if raw.semantic_choices else None
    first_diagnostic = diagnostics[0] if diagnostics else None
    if (first_choice is None) != (first_diagnostic is None):
        raise ValueError("v26.124 first Choice and diagnostic diverged")
    recovery_choices = tuple(
        item for item in raw.semantic_choices if item.public_attempt_phase == "semantic_recovery"
    )
    if len(recovery_choices) > 1:
        raise ValueError("v26.124 Semantic Recovery Choice denominator changed")
    recovery = recovery_choices[0] if recovery_choices else None
    legal_no_progress_positions = tuple(
        index for index, item in enumerate(diagnostics) if item.legal_no_progress_choice
    )
    eventual_progress = sum(
        any(later.public_progress_after_commit is True for later in diagnostics[index + 1 :])
        for index in legal_no_progress_positions
    )
    terminal_verification_choices = tuple(
        item
        for item in diagnostics
        if item.selected_candidate_family == "verify_terminal_operation" and item.semantic_accepted
    )
    final_commits = tuple(item for item in raw.commits if item.commit.action == "emit_final")
    candidate_distribution = Counter(str(item.candidate_count) for item in diagnostics)
    exact_final_attempts = tuple(
        item for item in final_attempts if item.exact_two_field_final_payload
    )
    values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "provider_call_count": raw.stage_one_provider_call_count,
        "provider_envelope_count": len(raw.provider_envelope_artifacts),
        "public_payload_projection_count": len(raw.public_payload_projection_artifacts),
        "validated_public_payload_count": projection_counts["validated_public_payload"],
        "privacy_rejected_payload_count": projection_counts["privacy_rejected"],
        "provider_failure_no_payload_count": projection_counts["provider_failure_no_payload"],
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "provider_prompt_tokens": sum(item.prompt_tokens or 0 for item in raw.provider_telemetry),
        "provider_completion_tokens": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_reasoning_tokens": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in raw.provider_telemetry
        ),
        "primary_attempt_count": sum(
            item.public_attempt_phase == "primary" for item in raw.attempts
        ),
        "abi_rescue_attempt_count": raw.abi_rescue_attempt_count,
        "semantic_recovery_attempt_count": raw.semantic_recovery_attempt_count,
        "completion_failure_counts": dict(sorted(completion_counts.items())),
        "model_failure_family_counts": dict(sorted(family_counts.items())),
        "model_failure_subtype_counts": dict(sorted(subtype_counts.items())),
        "semantic_response_payload_count": sum(
            item.response_payload_present for item in semantic_attempts
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload for item in semantic_attempts
        ),
        "semantic_choice_count": len(raw.semantic_choices),
        "visible_action_match_count": sum(
            item.visible_action_id_match for item in raw.semantic_choices
        ),
        "decision_kind_match_count": sum(item.decision_kind_match for item in raw.semantic_choices),
        "first_choice_acceptance_count": sum(
            item.public_attempt_phase == "primary" and item.semantic_accepted
            for item in raw.semantic_choices
        ),
        "stage_two_commit_count": len(raw.commits),
        "observation_count": len(raw.observations),
        "successful_observation_count": sum(
            item.status == "succeeded" for item in raw.observations
        ),
        "failed_observation_count": sum(item.status == "failed" for item in raw.observations),
        "public_progress_choice_count": sum(
            item.public_progress_after_commit is True for item in raw.semantic_choices
        ),
        "program_node_progress_choice_count": sum(
            item.program_node_progress for item in diagnostics
        ),
        "choice_diagnostic_count": len(diagnostics),
        "singleton_choice_count": sum(item.candidate_count == 1 for item in diagnostics),
        "multi_candidate_choice_count": sum(item.candidate_count > 1 for item in diagnostics),
        "candidate_count_distribution": dict(sorted(candidate_distribution.items())),
        "selected_prompt_only_reference_count": sum(
            item.selected_prompt_only_reference is True for item in diagnostics
        ),
        "first_choice_present": first_choice is not None,
        "first_action_id_legal": bool(
            first_choice is not None and first_choice.visible_action_id_match
        ),
        "first_action_semantically_accepted": bool(
            first_choice is not None and first_choice.semantic_accepted
        ),
        "first_action_public_progress": bool(
            first_choice is not None and first_choice.public_progress_after_commit is True
        ),
        "first_action_candidate_count": (
            first_diagnostic.candidate_count if first_diagnostic is not None else None
        ),
        "first_action_zero_based_position": (
            first_diagnostic.selected_zero_based_position if first_diagnostic is not None else None
        ),
        "first_action_candidate_family": (
            first_diagnostic.selected_candidate_family if first_diagnostic is not None else None
        ),
        "first_action_prompt_only_reference": (
            first_diagnostic.selected_prompt_only_reference
            if first_diagnostic is not None
            else None
        ),
        "semantic_rejection_count": len(raw.semantic_rejections),
        "semantic_recovery_used": bool(raw.semantic_recovery_attempt_count),
        "recovery_selected_different_action": bool(
            recovery is not None and recovery.different_action_after_rejection
        ),
        "recovery_committed": bool(recovery is not None and recovery.semantic_accepted),
        "recovery_public_progress": bool(
            recovery is not None and recovery.public_progress_after_commit is True
        ),
        "legal_no_progress_choice_count": len(legal_no_progress_positions),
        "ordinary_replan_after_legal_no_progress_count": sum(
            item.ordinary_replan_after_legal_no_progress for item in diagnostics
        ),
        "ordinary_replan_eventual_progress_count": eventual_progress,
        "terminal_verification_ready_choice_count": sum(
            item.terminal_verification_ready_before for item in diagnostics
        ),
        "terminal_verification_choice_count": len(terminal_verification_choices),
        "successful_terminal_verification_observation_count": sum(
            item.observation_status == "succeeded" for item in terminal_verification_choices
        ),
        "final_commit_count": len(final_commits),
        "final_request_attempt_count": len(final_attempts),
        "final_response_payload_count": sum(
            item.response_payload_present for item in final_attempts
        ),
        "exact_two_field_final_payload_count": len(exact_final_attempts),
        "final_primary_exact_payload": any(
            item.public_attempt_phase == "primary" for item in exact_final_attempts
        ),
        "final_rescue_exact_payload": any(
            item.public_attempt_phase == "abi_rescue" for item in exact_final_attempts
        ),
        "final_abi_crossed": bool(exact_final_attempts),
        "final_answer_emitted": raw.completed_result is not None,
        "final_answer_semantically_valid": answer_semantically_valid,
        "final_host_envelope_bound": bool(final_attempts)
        and all(item.final_response_host_envelope_id is not None for item in final_attempts),
        "rationale_summary_present": bool(
            raw.completed_result is not None and raw.completed_result.rationale_summary
        ),
        "typed_no_call": typed,
        "completion_unusable": completion,
        "provider_transport_failure": transport,
        "instrument_failure": instrument,
        "exact_model_passed": exact_model,
        "native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "fallback_absent": fallback_absent,
        "dynamic_precall_binding_passed": dynamic,
        "exact_request_binding_passed": exact_request,
        "privacy_artifact_pairing_passed": privacy_pairing,
        "rollout_budget_passed": raw.cumulative_provider_tokens <= 400000,
        "rollout_headroom_tokens": 400000 - raw.cumulative_provider_tokens,
        "reversible_commit_passed": reversible,
        "repeated_call_signature_count": repeated,
        "repeated_failed_call_signature_count": repeated_failed,
        "completed_program_node_count": completed_nodes,
        "program_node_count": node_count,
        "program_closed": program_closed,
        "terminal_node_completed": terminal_completed,
        "postterminal_verification_completed": verified,
        "mechanism_evaluated": mechanism.evaluated,
        "mechanism_success": mechanism.success,
        "independent_validity": valid,
        "actual_route": route,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "replay_v3_passed": replay.passed,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "choice_diagnostic_ids": tuple(item.diagnostic_id for item in diagnostics),
        "raw_execution_artifact": _descriptor(
            runner.raw_execution_path(output_dir, raw.job), output_dir
        ),
    }
    provisional = ExactFinalJobResult.model_construct(result_id="pending", **values)
    return (
        ExactFinalJobResult(
            result_id=_identity(
                provisional,
                "result_id",
                "finance_v26_exact_final_semantic_action_job_result:",
            ),
            **values,
        ),
        diagnostics,
    )


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _recursive_keys(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(key for item in value for key in _recursive_keys(item))
    return ()


def raw_lineage_audit(
    *,
    results: Sequence[ExactFinalJobResult],
    raw_by_job: Mapping[str, runner.PrivacyFirstRawExecution],
    output_dir: Path,
) -> ExactFinalRawLineageAudit:
    files: list[legacy.RawFileDescriptor] = []
    envelope_ids: list[str] = []
    projection_ids: list[str] = []
    status_counts: Counter[str] = Counter()
    private_hits = 0
    privacy_hash_count = 0
    bound_envelope_paths: set[str] = set()
    bound_projection_paths: set[str] = set()
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = runner.raw_execution_path(output_dir, raw.job)
        replayed = runner.PrivacyFirstRawExecution.model_validate(_load(raw_path))
        if replayed.model_dump(mode="json") != raw.model_dump(mode="json"):
            raise ValueError(f"v26.124 Raw replay changed: {result.job_id}")
        files.append(_descriptor(raw_path, output_dir))
        pairs = _provider_pairs(raw, output_dir)
        for envelope, projection in pairs:
            envelope_path = (
                output_dir
                / raw.provider_envelope_artifacts[envelope.provider_call_index].relative_path
            )
            projection_path = (
                output_dir
                / raw.public_payload_projection_artifacts[
                    projection.provider_call_index
                ].relative_path
            )
            bound_envelope_paths.add(str(envelope_path.resolve()))
            bound_projection_paths.add(str(projection_path.resolve()))
            envelope_payload = _load(envelope_path)
            projection_payload = _load(projection_path)
            forbidden = {"private_reasoning", "reasoning_content", "reasoning_trace"}
            private_hits += int(bool(forbidden & set(_recursive_keys(envelope_payload))))
            private_hits += int(bool(forbidden & set(_recursive_keys(projection_payload))))
            envelope_ids.append(envelope.envelope_id)
            projection_ids.append(projection.projection_id)
            status_counts[projection.projection_status] += 1
            if projection.projection_status == "privacy_rejected":
                privacy_hash_count += int(envelope.public_content_hash is not None)
            files.append(_descriptor(envelope_path, output_dir))
            files.append(_descriptor(projection_path, output_dir))
    all_envelope_paths = {
        str(path.resolve())
        for path in (output_dir / "raw_provider_envelopes").glob("*/call_*.json")
    }
    all_projection_paths = {
        str(path.resolve())
        for path in (output_dir / "public_payload_projections").glob("*/call_*.json")
    }
    envelope_orphans = len(all_envelope_paths - bound_envelope_paths)
    projection_orphans = len(all_projection_paths - bound_projection_paths)
    ordered = tuple(sorted(files, key=lambda item: item.relative_path))
    values: dict[str, Any] = {
        "provider_call_count": len(envelope_ids),
        "provider_envelope_count": len(envelope_ids),
        "public_payload_projection_count": len(projection_ids),
        "complete_provider_pair_count": len(envelope_ids),
        "unique_provider_envelope_id_count": len(set(envelope_ids)),
        "unique_payload_projection_id_count": len(set(projection_ids)),
        "validated_public_payload_count": status_counts["validated_public_payload"],
        "privacy_rejected_payload_count": status_counts["privacy_rejected"],
        "provider_failure_no_payload_count": status_counts["provider_failure_no_payload"],
        "envelope_only_orphan_count": envelope_orphans,
        "projection_only_orphan_count": projection_orphans,
        "whole_response_hash_for_privacy_rejection_count": privacy_hash_count,
        "file_count": len(ordered),
        "files": ordered,
        "exact_byte_replay_pass_count": len(ordered),
        "private_reasoning_payload_count": private_hits,
    }
    provisional = ExactFinalRawLineageAudit.model_construct(audit_id="pending", **values)
    return ExactFinalRawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_exact_final_raw_lineage:",
        ),
        **values,
    )


def _aggregate_counter(
    results: Sequence[ExactFinalJobResult],
    field: str,
) -> dict[str, int]:
    keys = {key for item in results for key in cast(dict[str, int], getattr(item, field))}
    return {
        key: sum(cast(dict[str, int], getattr(item, field)).get(key, 0) for item in results)
        for key in sorted(keys)
    }


def make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[ExactFinalJobResult],
    diagnostics: Sequence[predecessor_online.ChoiceDiagnostic],
    lineage: ExactFinalRawLineageAudit,
) -> ExactFinalExecutionReport:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    candidate_distribution = Counter(str(item.candidate_count) for item in diagnostics)
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    values: dict[str, Any] = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_validity_audit_id": prepared.preexecution_validity.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "provider_envelope_count": lineage.provider_envelope_count,
        "public_payload_projection_count": lineage.public_payload_projection_count,
        "validated_public_payload_count": lineage.validated_public_payload_count,
        "privacy_rejected_payload_count": lineage.privacy_rejected_payload_count,
        "provider_failure_no_payload_count": lineage.provider_failure_no_payload_count,
        "envelope_only_orphan_count": lineage.envelope_only_orphan_count,
        "projection_only_orphan_count": lineage.projection_only_orphan_count,
        "complete_raw_count": lineage.complete_raw_count,
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_prompt_tokens": sum(item.provider_prompt_tokens for item in results),
        "provider_completion_tokens": sum(item.provider_completion_tokens for item in results),
        "provider_reasoning_tokens": sum(item.provider_reasoning_tokens for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "primary_attempt_count": sum(item.primary_attempt_count for item in results),
        "abi_rescue_attempt_count": sum(item.abi_rescue_attempt_count for item in results),
        "semantic_recovery_attempt_count": sum(
            item.semantic_recovery_attempt_count for item in results
        ),
        "completion_failure_counts": _aggregate_counter(results, "completion_failure_counts"),
        "model_failure_family_counts": _aggregate_counter(results, "model_failure_family_counts"),
        "model_failure_subtype_counts": _aggregate_counter(results, "model_failure_subtype_counts"),
        "semantic_response_payload_count": sum(
            item.semantic_response_payload_count for item in results
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload_count for item in results
        ),
        "semantic_choice_count": sum(item.semantic_choice_count for item in results),
        "visible_action_id_match_count": sum(item.visible_action_match_count for item in results),
        "decision_kind_match_count": sum(item.decision_kind_match_count for item in results),
        "first_choice_accepted_count": sum(item.first_choice_acceptance_count for item in results),
        "reversible_stage_two_commit_count": sum(item.stage_two_commit_count for item in results),
        "runtime_observation_count": sum(item.observation_count for item in results),
        "successful_observation_count": sum(item.successful_observation_count for item in results),
        "failed_observation_count": sum(item.failed_observation_count for item in results),
        "public_progress_choice_count": sum(item.public_progress_choice_count for item in results),
        "program_node_progress_choice_count": sum(
            item.program_node_progress_choice_count for item in results
        ),
        "candidate_choice_count": len(diagnostics),
        "singleton_choice_count": sum(item.candidate_count == 1 for item in diagnostics),
        "multi_candidate_choice_count": sum(item.candidate_count > 1 for item in diagnostics),
        "candidate_count_distribution": dict(sorted(candidate_distribution.items())),
        "decision_load_summaries": predecessor_online._decision_load_summaries(diagnostics),
        "selected_prompt_only_reference_count": sum(
            item.selected_prompt_only_reference is True for item in diagnostics
        ),
        "first_choice_present_job_count": sum(item.first_choice_present for item in results),
        "first_action_id_legal_job_count": sum(item.first_action_id_legal for item in results),
        "first_action_semantically_accepted_job_count": sum(
            item.first_action_semantically_accepted for item in results
        ),
        "first_action_public_progress_job_count": sum(
            item.first_action_public_progress for item in results
        ),
        "semantic_rejection_count": sum(item.semantic_rejection_count for item in results),
        "semantic_recovery_job_count": sum(item.semantic_recovery_used for item in results),
        "recovery_selected_different_action_job_count": sum(
            item.recovery_selected_different_action for item in results
        ),
        "recovery_committed_job_count": sum(item.recovery_committed for item in results),
        "recovery_public_progress_job_count": sum(
            item.recovery_public_progress for item in results
        ),
        "legal_no_progress_choice_count": sum(
            item.legal_no_progress_choice_count for item in results
        ),
        "ordinary_replan_after_legal_no_progress_count": sum(
            item.ordinary_replan_after_legal_no_progress_count for item in results
        ),
        "ordinary_replan_eventual_progress_count": sum(
            item.ordinary_replan_eventual_progress_count for item in results
        ),
        "terminal_verification_choice_count": sum(
            item.terminal_verification_choice_count for item in results
        ),
        "successful_terminal_verification_observation_count": sum(
            item.successful_terminal_verification_observation_count for item in results
        ),
        "final_commit_count": sum(item.final_commit_count for item in results),
        "final_request_attempt_count": sum(item.final_request_attempt_count for item in results),
        "final_response_payload_count": sum(item.final_response_payload_count for item in results),
        "exact_two_field_final_payload_count": sum(
            item.exact_two_field_final_payload_count for item in results
        ),
        "final_primary_exact_payload_job_count": sum(
            item.final_primary_exact_payload for item in results
        ),
        "final_rescue_exact_payload_job_count": sum(
            item.final_rescue_exact_payload for item in results
        ),
        "final_abi_crossed_job_count": sum(item.final_abi_crossed for item in results),
        "final_answer_emitted_job_count": sum(item.final_answer_emitted for item in results),
        "final_answer_semantically_valid_job_count": sum(
            item.final_answer_semantically_valid for item in results
        ),
        "typed_no_call_job_count": sum(item.typed_no_call for item in results),
        "completion_unusable_job_count": sum(item.completion_unusable for item in results),
        "provider_transport_failure_job_count": sum(
            item.provider_transport_failure for item in results
        ),
        "instrument_failure_job_count": sum(item.instrument_failure for item in results),
        "model_invalid_trajectory_count": sum(
            item.terminal_category == "model_invalid_trajectory" for item in results
        ),
        "program_closed_count": sum(item.program_closed for item in results),
        "terminal_node_completed_count": sum(item.terminal_node_completed for item in results),
        "postterminal_verification_completed_count": sum(
            item.postterminal_verification_completed for item in results
        ),
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
        "cell_summaries": predecessor_online._cell_summaries(cast(Any, results)),
        "exact_model_passed": all(item.exact_model_passed for item in results),
        "native_tool_absence_passed": all(item.native_tool_absent for item in results),
        "thinking_continuity_passed": all(item.thinking_continuity_passed for item in results),
        "provider_usage_complete": all(item.provider_usage_complete for item in results),
        "fallback_absence_passed": all(item.fallback_absent for item in results),
        "dynamic_precall_binding_passed": all(
            item.dynamic_precall_binding_passed for item in results
        ),
        "exact_request_binding_passed": all(item.exact_request_binding_passed for item in results),
        "privacy_artifact_pairing_passed": all(
            item.privacy_artifact_pairing_passed for item in results
        ),
        "empirical_budget_adequacy_passed": not any(item.typed_no_call for item in results),
        "stage_two_authority_passed": all(item.reversible_commit_passed for item in results),
        "replay_v3_passed": all(item.replay_v3_passed for item in results),
    }
    provisional = ExactFinalExecutionReport.model_construct(report_id="pending", **values)
    return ExactFinalExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_exact_final_semantic_action_execution_report:",
        ),
        **values,
    )


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[ExactFinalJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        ExactFinalJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.static.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.124 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.124 checkpoint crosses the frozen denominator")
        raw_path = runner.raw_execution_path(output_dir, job)
        if (
            not raw_path.is_file()
            or legacy.sha256_file(raw_path) != result.raw_execution_artifact.sha256
        ):
            raise ValueError("v26.124 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[
    [AgentModelConfig, static_stage.FinalGrammarJob, Any],
    Any,
]


def _default_client_factory(
    config: AgentModelConfig,
    _job: static_stage.FinalGrammarJob,
    _binding: Any,
) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: static_stage.FinalGrammarJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[
    ExactFinalJobResult,
    runner.PrivacyFirstRawExecution,
    tuple[predecessor_online.ChoiceDiagnostic, ...],
]:
    binding = runner.privacy_first_runtime_binding(prepared.static, job)
    client = (
        None
        if client_factory is None
        else client_factory(prepared.static.agent_model_config, job, binding)
    )
    raw = runner.execute_privacy_first_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        static=prepared.static,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    result, diagnostics = project_job_result(
        raw=raw,
        prepared=prepared,
        output_dir=output_dir,
    )
    return result, raw, diagnostics


def _write_checkpoint(path: Path, rows: Sequence[ExactFinalJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _assert_no_orphan_artifacts(output_dir: Path, job: static_stage.FinalGrammarJob) -> None:
    envelope_dir = runner.provider_envelope_path(output_dir, job, 0).parent
    projection_dir = runner.payload_projection_path(output_dir, job, 0).parent
    envelope_count = len(tuple(envelope_dir.glob("call_*.json"))) if envelope_dir.exists() else 0
    projection_count = (
        len(tuple(projection_dir.glob("call_*.json"))) if projection_dir.exists() else 0
    )
    if envelope_count or projection_count:
        raise ValueError(
            "orphan v26.124 privacy-first Artifacts forbid retry: "
            f"job={job.job_id} envelopes={envelope_count} projections={projection_count}"
        )


def run_exact_final_semantic_action_calibration(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> ExactFinalExecutionReport:
    prepared = prepare_execution(
        runner_preflight_dir=runner_preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "exact_final_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.static.manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.124 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = ExactFinalExecutionReport.model_validate(_load(report_path))
        if (
            report.runner_contract_id != prepared.runner_contract.contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.124 completed report crosses frozen bindings")
        return report
    raw_recovery_jobs = [
        item for item in pending if runner.raw_execution_path(output_dir, item).exists()
    ]
    model_pending_jobs = [
        item for item in pending if not runner.raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        _assert_no_orphan_artifacts(output_dir, job)
    print(
        f"[v26.124] resuming {len(completed)}/32; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, runner.PrivacyFirstRawExecution] = {}
    diagnostics_by_job: dict[str, tuple[predecessor_online.ChoiceDiagnostic, ...]] = {}
    for job in jobs:
        path = runner.raw_execution_path(output_dir, job)
        if path.exists() and job.job_id in completed:
            raw = runner.PrivacyFirstRawExecution.model_validate(_load(path))
            raw_by_job[job.job_id] = raw
            diagnostics_by_job[job.job_id] = _choice_diagnostics(
                raw=raw,
                prepared=prepared,
                binding=runner.privacy_first_runtime_binding(prepared.static, job),
            )
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            result, raw, diagnostics = future.result()
            with lock:
                completed[job.job_id] = result
                raw_by_job[job.job_id] = raw
                diagnostics_by_job[job.job_id] = diagnostics
                ordered = tuple(completed[item.job_id] for item in jobs if item.job_id in completed)
                _write_checkpoint(checkpoint_path, ordered)
                print(
                    f"[v26.124] completed {len(completed)}/32 "
                    f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                    f"terminal={result.terminal_category} "
                    f"final_abi={result.final_abi_crossed} "
                    f"calls={result.provider_call_count}",
                    flush=True,
                )
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 32:
        raise ValueError("v26.124 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.job_id,
            runner.PrivacyFirstRawExecution.model_validate(
                _load(runner.raw_execution_path(output_dir, job))
            ),
        )
        diagnostics_by_job.setdefault(
            job.job_id,
            _choice_diagnostics(
                raw=raw_by_job[job.job_id],
                prepared=prepared,
                binding=runner.privacy_first_runtime_binding(prepared.static, job),
            ),
        )
    diagnostics = tuple(diagnostic for job in jobs for diagnostic in diagnostics_by_job[job.job_id])
    lineage = raw_lineage_audit(
        results=results,
        raw_by_job=raw_by_job,
        output_dir=output_dir,
    )
    report = make_execution_report(
        prepared=prepared,
        results=results,
        diagnostics=diagnostics,
        lineage=lineage,
    )
    runner.write_json_atomic(
        output_dir / "exact_final_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    runner.write_json_atomic(
        output_dir / "semantic_action_choice_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )
    runner.write_json_atomic(
        output_dir / "raw_lineage_audit.json",
        lineage.model_dump(mode="json"),
    )
    runner.write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.124 Final-Grammar Semantic Action calibration"
    )
    parser.add_argument(
        "--runner-preflight-dir",
        type=Path,
        default=package_default / PREFLIGHT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_execution(
            runner_preflight_dir=args.runner_preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "runner_contract_id": prepared.runner_contract.contract_id,
                    "outcome_measurement_contract_id": prepared.outcome_contract.contract_id,
                    "preexecution_validity_audit_id": (prepared.preexecution_validity.audit_id),
                    "expected_jobs": len(prepared.static.manifest.jobs),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "stage_two_provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_exact_final_semantic_action_calibration(
        runner_preflight_dir=args.runner_preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
