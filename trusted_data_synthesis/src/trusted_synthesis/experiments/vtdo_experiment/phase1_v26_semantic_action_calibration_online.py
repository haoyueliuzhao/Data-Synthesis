from __future__ import annotations

import argparse
import json
import math
import tempfile
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as runner,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_execution import (  # noqa: E501
    _completed_verification,
    _telemetry_flags,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_rematerialization import (  # noqa: E501
    SemanticActionJob,
    SemanticActionStaticInputs,
    load_semantic_action_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_runner_preflight import (  # noqa: E501
    OutcomeMeasurementContract,
    ProspectiveTransitionContract,
    RunnerSourceReplayAudit,
    ScriptedSemanticActionClient,
    SemanticActionRunnerPreflightReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    _actual_route,
    _progress_diagnostic,
    _repetition_counts,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    SemanticActionState,
    build_semantic_action_state,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    prompt_only_reference_payload,
    render_exact_canonical_action_abi_rescue_prompt,
    render_exact_canonical_action_prompt,
    render_exact_canonical_action_semantic_recovery_prompt,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = runner.EXECUTION_RUN_ID
PREFLIGHT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_119_semantic_action_runner_preflight_v1_20260823"
)
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_120_semantic_action_calibration_execution_v1_20260823"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_semantic_action_calibration_online.py"
)
EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_semantic_action_runner_preflight_report:"
    "71f69695266d696ba8277d27a6882f9b7c6401c78de21350f27d7b3e20826b0b"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_semantic_action_runner_source_replay:"
    "299ddd17b1d86b80f2749732d3f40b47e052e26a1e8b19a5f580edf0c80c991c"
)
EXPECTED_RUNNER_CONTRACT_ID: Final = (
    "finance_v26_semantic_action_runner_contract:"
    "bc3a1ee31264087d00c75a05d5986427bbcfb68d7a5f291459206d6ff073a9a0"
)
EXPECTED_OUTCOME_CONTRACT_ID: Final = (
    "finance_v26_semantic_action_outcome_measurement:"
    "db0b46e21d40bcb048e883b4d6197f495d5251ed6cd05e5148449380f2b5a59e"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_semantic_action_runner_transition:"
    "59ee56a2043389ad7a65d459f11cce2f0d90faa5c343f73dcf7aaa11eb9dbf4b"
)
EXPECTED_MANIFEST_ID: Final = (
    "finance_v26_semantic_action_manifest:"
    "b517318004dfdc2ffce1de97e7a94acab9138ee2d0bca410da179a835ab88bcd"
)
EXPECTED_CANDIDATE_AUDIT_ID: Final = (
    "finance_v26_candidate_space_authority:"
    "58dd1803e6802e48a39884097884c5f4f77d606537b31359e1e192c0515c315d"
)
EXPECTED_RESOURCE_ID: Final = (
    "finance_v26_semantic_action_resource_contract:"
    "358453a9075d5df7a158b9a11100bf27585dacde644f993058452a0f0a851bdf"
)
EXPECTED_GRAMMAR_ID: Final = (
    "prospective_semantic_action_response_grammar:"
    "bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82"
)
POSTRUN_STAGE: Final = "semantic_action_calibration_postrun_audit_only"
PREFLIGHT_OUTPUTS: Final = (
    "certificate_usage_recovery_audit.json",
    "destructive_runner_audit.json",
    "outcome_measurement_contract.json",
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
        "v26_119_transitive_source",
        "v26_119_output",
        "v26_120_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class ExecutionSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[2217] = 2217
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2228] = 2228
    replay_pass_count: Literal[2228] = 2228
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2228, max_length=2228)
    replay_before_profile_parsing: Literal[True] = True
    replay_before_credential_lookup: Literal[True] = True
    replay_before_client_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_execution_source_replay.v1"] = (
        "finance_v26_semantic_action_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutionSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2228:
            raise ValueError("v26.120 source replay paths are not canonical and unique")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.120 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_execution_source_replay:"
        ):
            raise ValueError("v26.120 source replay identity changed")
        return self


class PreexecutionValidityRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    stage_one_scripted_provider_call_count: int = Field(gt=0, le=12)
    semantic_choice_count: int = Field(gt=0, le=11)
    stage_two_commit_count: int = Field(gt=0, le=11)
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
    semantic_choice_count: Literal[224] = 224
    stage_two_commit_count: Literal[224] = 224
    stage_two_provider_call_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    real_model_client_constructed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_preexecution_validity.v1"] = (
        "finance_v26_semantic_action_preexecution_validity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionValidityAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("v26.120 preexecution rows are not canonical")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_semantic_action_preexecution_validity:"
        ):
            raise ValueError("v26.120 preexecution validity identity changed")
        return self


class CandidatePresentationRow(FrozenModel):
    action_id: str = Field(min_length=1)
    zero_based_position: int = Field(ge=0, le=7)
    description_utf8_bytes: int = Field(gt=0)
    candidate_family: str = Field(min_length=1)
    prompt_only_reference: bool
    selected_by_model: bool


class ChoiceDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0, le=10)
    choice_phase: Literal["primary", "semantic_recovery"]
    response_attempt_phase: Literal["primary", "abi_rescue", "semantic_recovery"]
    public_state_id: str = Field(min_length=1)
    candidate_count: int = Field(ge=1, le=8)
    decision_load_natural_log: float = Field(ge=0.0)
    candidates: tuple[CandidatePresentationRow, ...] = Field(min_length=1, max_length=8)
    selected_action_id: str = Field(min_length=1)
    selected_zero_based_position: int | None = Field(default=None, ge=0, le=7)
    selected_description_utf8_bytes: int | None = Field(default=None, gt=0)
    selected_candidate_family: str | None = Field(default=None, min_length=1)
    selected_prompt_only_reference: bool | None = None
    visible_action_id_match: bool
    decision_kind_match: bool
    semantic_accepted: bool
    observation_status: Literal["succeeded", "failed"] | None = None
    public_progress_after_commit: bool | None = None
    completed_program_nodes_before: int = Field(ge=0)
    completed_program_nodes_after: int = Field(ge=0)
    program_node_progress: bool
    terminal_verification_ready_before: bool
    legal_no_progress_choice: bool
    ordinary_replan_after_legal_no_progress: bool
    schema_version: Literal["finance_v26_semantic_action_choice_diagnostic.v1"] = (
        "finance_v26_semantic_action_choice_diagnostic.v1"
    )

    @model_validator(mode="after")
    def validate_diagnostic(self) -> ChoiceDiagnostic:
        if (
            self.candidate_count != len(self.candidates)
            or tuple(item.zero_based_position for item in self.candidates)
            != tuple(range(self.candidate_count))
            or sum(item.selected_by_model for item in self.candidates)
            != int(self.visible_action_id_match)
            or sum(item.prompt_only_reference for item in self.candidates) != 1
        ):
            raise ValueError("v26.120 Candidate presentation denominator changed")
        selected = (
            self.candidates[self.selected_zero_based_position]
            if self.selected_zero_based_position is not None
            else None
        )
        if self.visible_action_id_match and (
            selected is None
            or selected.action_id != self.selected_action_id
            or selected.description_utf8_bytes != self.selected_description_utf8_bytes
            or selected.candidate_family != self.selected_candidate_family
            or selected.prompt_only_reference != self.selected_prompt_only_reference
            or not selected.selected_by_model
        ):
            raise ValueError("v26.120 selected Candidate diagnostic changed")
        if not self.visible_action_id_match and any(
            value is not None
            for value in (
                self.selected_zero_based_position,
                self.selected_description_utf8_bytes,
                self.selected_candidate_family,
                self.selected_prompt_only_reference,
            )
        ):
            raise ValueError("v26.120 invisible action acquired Candidate metadata")
        if self.program_node_progress != (
            self.completed_program_nodes_after > self.completed_program_nodes_before
        ):
            raise ValueError("v26.120 Program-node progress accounting changed")
        if self.diagnostic_id != _identity(
            self, "diagnostic_id", "finance_v26_semantic_action_choice_diagnostic:"
        ):
            raise ValueError("v26.120 choice-diagnostic identity changed")
        return self


class DecisionLoadSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    candidate_count: int = Field(ge=1, le=8)
    decision_load_natural_log: float = Field(ge=0.0)
    choice_count: int = Field(gt=0)
    semantic_accepted_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    public_progress_count: int = Field(ge=0)
    program_node_progress_count: int = Field(ge=0)
    selected_reference_count: int = Field(ge=0)
    singleton_interface_diagnostic: bool
    descriptive_only: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_decision_load_summary.v1"] = (
        "finance_v26_semantic_action_decision_load_summary.v1"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> DecisionLoadSummary:
        if self.singleton_interface_diagnostic != (self.candidate_count == 1):
            raise ValueError("v26.120 Singleton diagnostic accounting changed")
        if self.summary_id != _identity(
            self, "summary_id", "finance_v26_semantic_action_decision_load_summary:"
        ):
            raise ValueError("v26.120 Decision Load summary identity changed")
        return self


class SemanticActionJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: str = Field(min_length=1)
    terminal_category: TerminalCategory
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None = None
    provider_call_count: int = Field(ge=0, le=12)
    http_success_call_count: int = Field(ge=0, le=12)
    provider_total_tokens: int = Field(ge=0, le=400000)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=1, le=12)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    direct_usable_request_count: int = Field(ge=0, le=12)
    abi_rescued_usable_request_count: int = Field(ge=0, le=1)
    semantic_recovery_usable_request_count: int = Field(ge=0, le=1)
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    semantic_response_payload_count: int = Field(ge=0, le=12)
    exact_four_field_payload_count: int = Field(ge=0, le=12)
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
    final_answer_emitted: bool
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
    rollout_budget_passed: bool
    rollout_headroom_tokens: int = Field(ge=0, le=400000)
    stage_two_provider_call_count: Literal[0] = 0
    reversible_commit_passed: bool
    host_semantic_action_inserted: Literal[False] = False
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
    schema_version: Literal["finance_v26_semantic_action_job_result.v1"] = (
        "finance_v26_semantic_action_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> SemanticActionJobResult:
        if self.reasoning_tokens_total > self.completion_tokens_total:
            raise ValueError("v26.120 Reasoning Usage exceeds Completion Usage")
        if self.requested_path_adhered != (self.actual_route == self.requested_path_strategy_id):
            raise ValueError("v26.120 path-adherence accounting changed")
        if self.independent_validity != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("v26.120 valid-terminal accounting changed")
        if self.choice_diagnostic_count != len(self.choice_diagnostic_ids):
            raise ValueError("v26.120 choice-diagnostic denominator changed")
        if self.first_choice_present != bool(self.semantic_choice_count):
            raise ValueError("v26.120 first-choice presence changed")
        if not self.first_choice_present and any(
            (
                self.first_action_id_legal,
                self.first_action_semantically_accepted,
                self.first_action_public_progress,
                self.first_action_candidate_count is not None,
                self.first_action_zero_based_position is not None,
                self.first_action_candidate_family is not None,
                self.first_action_prompt_only_reference is not None,
            )
        ):
            raise ValueError("v26.120 absent first choice acquired outcome values")
        if self.semantic_recovery_used != bool(self.semantic_recovery_attempt_count):
            raise ValueError("v26.120 Semantic Recovery accounting changed")
        if self.result_id != _identity(
            self, "result_id", "finance_v26_semantic_action_job_result:"
        ):
            raise ValueError("v26.120 Job-result identity changed")
        return self


class SemanticActionCellSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    job_count: int = Field(ge=2)
    model_invalid_count: int = Field(ge=0)
    completion_unusable_count: int = Field(ge=0)
    typed_no_call_count: int = Field(ge=0)
    transport_failure_count: int = Field(ge=0)
    instrument_failure_count: int = Field(ge=0)
    first_action_legal_count: int = Field(ge=0)
    first_action_public_progress_count: int = Field(ge=0)
    semantic_recovery_job_count: int = Field(ge=0)
    program_closed_count: int = Field(ge=0)
    terminal_verification_completed_count: int = Field(ge=0)
    final_answer_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)
    requested_path_adherence_count: int = Field(ge=0)
    descriptive_only: Literal[True] = True
    schema_version: Literal["finance_v26_semantic_action_cell_summary.v1"] = (
        "finance_v26_semantic_action_cell_summary.v1"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> SemanticActionCellSummary:
        if self.summary_id != _identity(
            self, "summary_id", "finance_v26_semantic_action_cell_summary:"
        ):
            raise ValueError("v26.120 Cell-summary identity changed")
        return self


class SemanticActionRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = EXPECTED_RUNNER_CONTRACT_ID
    job_result_count: Literal[32] = 32
    raw_execution_count: Literal[32] = 32
    provider_call_count: int = Field(ge=0, le=384)
    unique_provider_artifact_id_count: int = Field(ge=0, le=384)
    file_count: int = Field(ge=32)
    files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=32)
    exact_byte_replay_pass_count: int = Field(ge=32)
    private_reasoning_payload_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_semantic_action_raw_lineage.v1"] = (
        "finance_v26_semantic_action_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticActionRawLineageAudit:
        if (
            self.file_count != len(self.files)
            or self.exact_byte_replay_pass_count != self.file_count
            or self.unique_provider_artifact_id_count != self.provider_call_count
        ):
            raise ValueError("v26.120 Raw Lineage denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_semantic_action_raw_lineage:"):
            raise ValueError("v26.120 Raw Lineage identity changed")
        return self


class SemanticActionExecutionReport(FrozenModel):
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
    http_success_call_count: int = Field(ge=0, le=384)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str = Field(min_length=1)
    reasoning_content_length_total: int = Field(ge=0)
    reasoning_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    primary_attempt_count: int = Field(ge=32, le=384)
    abi_rescue_attempt_count: int = Field(ge=0, le=32)
    semantic_recovery_attempt_count: int = Field(ge=0, le=32)
    completion_failure_counts: dict[str, int]
    model_failure_family_counts: dict[str, int]
    model_failure_subtype_counts: dict[str, int]
    provider_response_count: int = Field(ge=0)
    exact_four_field_proposal_count: int = Field(ge=0)
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
    decision_load_summaries: tuple[DecisionLoadSummary, ...]
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
    terminal_verification_ready_choice_count: int = Field(ge=0)
    terminal_verification_choice_count: int = Field(ge=0, le=32)
    successful_terminal_verification_observation_count: int = Field(ge=0, le=32)
    final_commit_count: int = Field(ge=0, le=32)
    final_answer_count: int = Field(ge=0, le=32)
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
    cell_summaries: tuple[SemanticActionCellSummary, ...] = Field(min_length=12, max_length=12)
    exact_model_passed: bool
    native_tool_absence_passed: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absence_passed: bool
    dynamic_precall_binding_passed: bool
    exact_request_binding_passed: bool
    empirical_budget_adequacy_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    stage_two_authority_passed: bool
    replay_v3_passed: bool
    exact_denominator_complete: Literal[True] = True
    first_choice_failure_retained_after_eventual_success: Literal[True] = True
    invalid_action_and_legal_no_progress_kept_separate: Literal[True] = True
    measured_object: Literal[
        "state_interpretation_and_action_selection_in_canonical_public_action_space"
    ] = "state_interpretation_and_action_selection_in_canonical_public_action_space"
    same_distribution_as_v26_114_claimed: Literal[False] = False
    general_model_ability_increase_claimed: Literal[False] = False
    candidate_completeness_implies_capability_sensitivity: Literal[False] = False
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
    next_permitted_stage: Literal["semantic_action_calibration_postrun_audit_only"] = POSTRUN_STAGE
    schema_version: Literal["finance_v26_semantic_action_execution_report.v1"] = (
        "finance_v26_semantic_action_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> SemanticActionExecutionReport:
        if sum(self.terminal_counts.values()) != 32:
            raise ValueError("v26.120 terminal denominator changed")
        if self.candidate_choice_count != (
            self.singleton_choice_count + self.multi_candidate_choice_count
        ):
            raise ValueError("v26.120 Candidate choice partition changed")
        if self.report_id != _identity(
            self, "report_id", "finance_v26_semantic_action_execution_report:"
        ):
            raise ValueError("v26.120 execution-report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: ExecutionSourceReplayAudit
    preflight_report: SemanticActionRunnerPreflightReport
    runner_contract: runner.SemanticActionRunnerContract
    outcome_contract: OutcomeMeasurementContract
    transition_contract: ProspectiveTransitionContract
    preexecution_validity: PreexecutionValidityAudit
    static: SemanticActionStaticInputs


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
    raise ValueError(f"v26.120 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    runner_preflight_dir: Path,
) -> ExecutionSourceReplayAudit:
    predecessor = RunnerSourceReplayAudit.model_validate(
        _load(runner_preflight_dir / "source_replay_audit.json")
    )
    report = SemanticActionRunnerPreflightReport.model_validate(
        _load(runner_preflight_dir / "report.json")
    )
    if (
        predecessor.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
    ):
        raise ValueError("v26.120 predecessor replay identity changed")
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
            source_kind="v26_119_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    detail = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *detail}:
        raise ValueError("v26.120 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = runner_preflight_dir / name
        if not path.is_file():
            raise ValueError(f"v26.120 predecessor output is missing: {name}")
        observed = legacy.sha256_file(path)
        if name != "report.json":
            expected = detail[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.120 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_119_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    observed = legacy.sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_120_implementation",
        expected_sha256=observed,
        observed_sha256=observed,
        byte_count=implementation_path.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values: dict[str, Any] = {"entries": ordered}
    provisional = ExecutionSourceReplayAudit.model_construct(audit_id="pending", **values)
    return ExecutionSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_execution_source_replay:",
        ),
        **values,
    )


def build_preexecution_validity_audit(
    *,
    static: SemanticActionStaticInputs,
    contract: runner.SemanticActionRunnerContract,
) -> PreexecutionValidityAudit:
    rows: list[PreexecutionValidityRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_120_preexecution_validity_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = runner.semantic_action_runtime_binding(static, job)
            raw = runner.execute_semantic_action_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=ScriptedSemanticActionClient(
                    static.agent_model_config,
                    final_answer=binding.compiler_trajectory.final_answer,
                ),
                output_dir=root,
            )
            replay = legacy.replay_v3(raw, static=static.historical, binding=binding)
            verification, mechanism = _completed_verification(
                raw=raw,
                replay=replay,
                binding=binding,
            )
            if (
                raw.terminal_disposition != "completed"
                or raw.completed_result is None
                or not replay.passed
                or not verification.valid
                or not mechanism.success
                or raw.stage_two_provider_call_count
                or raw.semantic_rejections
            ):
                raise ValueError(f"v26.120 preexecution Independent Validity failed: {job.job_id}")
            rows.append(
                PreexecutionValidityRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    stage_one_scripted_provider_call_count=raw.stage_one_provider_call_count,
                    semantic_choice_count=len(raw.semantic_choices),
                    stage_two_commit_count=len(raw.commits),
                )
            )
    values: dict[str, Any] = {
        "rows": tuple(rows),
        "stage_one_scripted_provider_call_count": sum(
            item.stage_one_scripted_provider_call_count for item in rows
        ),
        "semantic_choice_count": sum(item.semantic_choice_count for item in rows),
        "stage_two_commit_count": sum(item.stage_two_commit_count for item in rows),
    }
    provisional = PreexecutionValidityAudit.model_construct(audit_id="pending", **values)
    return PreexecutionValidityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_preexecution_validity:",
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
    source_replay = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        runner_preflight_dir=runner_preflight_dir,
    )
    runner.write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        source_replay.model_dump(mode="json"),
    )
    report = SemanticActionRunnerPreflightReport.model_validate(
        _load(runner_preflight_dir / "report.json")
    )
    contract = runner.SemanticActionRunnerContract.model_validate(
        _load(runner_preflight_dir / "runner_contract.json")
    )
    outcome = OutcomeMeasurementContract.model_validate(
        _load(runner_preflight_dir / "outcome_measurement_contract.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        _load(runner_preflight_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.runner_contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or report.outcome_measurement_contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.status != "passed_runner_preflight"
        or report.next_permitted_stage != "semantic_action_calibration_execution_only"
        or report.exact_job_denominator != 32
        or report.provider_calls
        or report.stage_two_provider_calls
        or contract.contract_id != EXPECTED_RUNNER_CONTRACT_ID
        or outcome.contract_id != EXPECTED_OUTCOME_CONTRACT_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or not transition.exact_manifest_execution_authorized
        or transition.next_permitted_stage != "semantic_action_calibration_execution_only"
    ):
        raise ValueError("v26.120 predecessor authorization changed")
    static = load_semantic_action_static_inputs(package_root, implementation_root)
    if (
        runner.make_semantic_action_runner_contract(static) != contract
        or static.manifest.manifest_id != EXPECTED_MANIFEST_ID
        or static.contract.candidate_space_authority_audit_id != EXPECTED_CANDIDATE_AUDIT_ID
        or static.resource.contract_id != EXPECTED_RESOURCE_ID
        or static.grammar.grammar_id != EXPECTED_GRAMMAR_ID
        or static.resource.rollout_upper_bound_tokens != 400000
        or len(static.manifest.jobs) != 32
        or len({item.job_id for item in static.manifest.jobs}) != 32
        or static.stage_two.provider_call_upper_bound != 0
    ):
        raise ValueError("v26.120 static execution denominator changed")
    preexecution = build_preexecution_validity_audit(static=static, contract=contract)
    runner.write_json_atomic(output_dir / "runner_contract.json", contract.model_dump(mode="json"))
    runner.write_json_atomic(
        output_dir / "outcome_measurement_contract.json",
        outcome.model_dump(mode="json"),
    )
    runner.write_json_atomic(
        output_dir / "frozen_semantic_action_job_manifest.json",
        static.manifest.model_dump(mode="json"),
    )
    runner.write_json_atomic(
        output_dir / "frozen_semantic_action_response_grammar.json",
        static.grammar.model_dump(mode="json"),
    )
    runner.write_json_atomic(
        output_dir / "preexecution_independent_validity_audit.json",
        preexecution.model_dump(mode="json"),
    )
    return PreparedExecution(
        source_replay=source_replay,
        preflight_report=report,
        runner_contract=contract,
        outcome_contract=outcome,
        transition_contract=transition,
        preexecution_validity=preexecution,
        static=static,
    )


def _prompt_payload(prompt: str) -> dict[str, Any]:
    _, separator, raw = prompt.partition("\n")
    if not separator:
        raise ValueError("v26.120 semantic-action Prompt lacks a JSON payload")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("v26.120 semantic-action Prompt payload is not an object")
    return cast(dict[str, Any], value)


def _candidate_family(candidate: Mapping[str, Any]) -> str:
    decision = str(candidate.get("decision_kind"))
    if decision == "acquire_public_input":
        mode = candidate.get("acquisition_mode")
        return f"{decision}/{mode}"
    if decision == "execute_public_operation":
        operator = candidate.get("operator_id") or "registered_default"
        return f"{decision}/{operator}"
    return decision


def _choice_prompt(
    *,
    raw: runner.SemanticActionRawExecution,
    choice: runner.SemanticChoiceRecord,
    state: SemanticActionState,
    binding: Any,
    grammar: Any,
    semantic_recovery_count: int,
) -> tuple[str, Literal["primary", "abi_rescue", "semantic_recovery"]]:
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    presentation_salt = canonical_hash(
        {
            "job_id": raw.job.job_id,
            "logical_request_index": choice.logical_request_index,
            "state_id": state.state_id,
            "semantic_recovery_count": semantic_recovery_count,
        },
        prefix="finance_v26_runner_candidate_presentation:",
    )
    primary = (
        render_exact_canonical_action_semantic_recovery_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
        )
        if choice.public_attempt_phase == "semantic_recovery"
        else render_exact_canonical_action_prompt(
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            grammar=grammar,
        )
    )
    attempts = tuple(
        item
        for item in raw.attempts
        if item.request_kind == "semantic_proposal"
        and item.logical_request_index == choice.logical_request_index
    )
    usable = tuple(item for item in attempts if item.disposition == "usable")
    if len(usable) != 1:
        raise ValueError("v26.120 accepted Choice lacks one usable response attempt")
    active = usable[0]
    prompt = primary
    phase: Literal["primary", "abi_rescue", "semantic_recovery"] = choice.public_attempt_phase
    if active.public_attempt_phase == "abi_rescue":
        initial = attempts[0]
        family = initial.failure_family or "channel_parse_failure"
        subtype = initial.failure_subtype or initial.completion_failure_type or "completion_failure"
        prompt = render_exact_canonical_action_abi_rescue_prompt(
            primary,
            failure_family=family,
            failure_subtype=subtype,
        )
        phase = "abi_rescue"
    if legacy.sha256_text(prompt) != active.prompt_sha256:
        raise ValueError("v26.120 reconstructed Choice Prompt differs from certified bytes")
    return prompt, phase


def build_choice_diagnostics(
    *,
    raw: runner.SemanticActionRawExecution,
    static: SemanticActionStaticInputs,
    binding: Any,
) -> tuple[ChoiceDiagnostic, ...]:
    observations: list[Any] = []
    rejections: list[Any] = []
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}
    diagnostics: list[ChoiceDiagnostic] = []
    previous_legal_no_progress = False
    for choice in raw.semantic_choices:
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        if state.state_id != choice.state_id:
            raise ValueError("v26.120 reconstructed Choice state differs from Raw binding")
        prompt, response_phase = _choice_prompt(
            raw=raw,
            choice=choice,
            state=state,
            binding=binding,
            grammar=static.grammar,
            semantic_recovery_count=len(rejections),
        )
        payload = _prompt_payload(prompt)
        visible = payload.get("visible_action_candidates")
        if not isinstance(visible, list) or not visible:
            raise ValueError("v26.120 Prompt omits its visible Candidate set")
        reference = prompt_only_reference_payload(prompt)
        reference_action_id = str(reference["action_id"])
        candidate_rows: list[CandidatePresentationRow] = []
        selected_position: int | None = None
        selected_bytes: int | None = None
        selected_family: str | None = None
        selected_reference: bool | None = None
        for position, raw_candidate in enumerate(visible):
            if not isinstance(raw_candidate, Mapping):
                raise ValueError("v26.120 visible Candidate is not an object")
            candidate = dict(raw_candidate)
            action_id = str(candidate.get("action_id"))
            description_bytes = len(_canonical_bytes(candidate))
            family = _candidate_family(candidate)
            is_reference = action_id == reference_action_id
            is_selected = action_id == choice.selected_action_id
            candidate_rows.append(
                CandidatePresentationRow(
                    action_id=action_id,
                    zero_based_position=position,
                    description_utf8_bytes=description_bytes,
                    candidate_family=family,
                    prompt_only_reference=is_reference,
                    selected_by_model=is_selected,
                )
            )
            if is_selected:
                selected_position = position
                selected_bytes = description_bytes
                selected_family = family
                selected_reference = is_reference
        before_nodes = _progress_diagnostic(binding.record, tuple(observations))[0]
        if choice.observation_status is not None:
            observation_index = len(observations)
            if observation_index >= len(raw.observations):
                raise ValueError("v26.120 Choice references a missing Observation")
            observation = raw.observations[observation_index]
            if observation.status != choice.observation_status:
                raise ValueError("v26.120 Choice Observation status changed")
            observations.append(observation)
        after_nodes = _progress_diagnostic(binding.record, tuple(observations))[0]
        legal_no_progress = bool(
            choice.semantic_accepted
            and choice.observation_status is not None
            and choice.public_progress_after_commit is False
        )
        values: dict[str, Any] = {
            "job_id": raw.job.job_id,
            "logical_request_index": choice.logical_request_index,
            "choice_phase": choice.public_attempt_phase,
            "response_attempt_phase": response_phase,
            "public_state_id": state.state_id,
            "candidate_count": len(candidate_rows),
            "decision_load_natural_log": math.log(len(candidate_rows)),
            "candidates": tuple(candidate_rows),
            "selected_action_id": choice.selected_action_id,
            "selected_zero_based_position": selected_position,
            "selected_description_utf8_bytes": selected_bytes,
            "selected_candidate_family": selected_family,
            "selected_prompt_only_reference": selected_reference,
            "visible_action_id_match": choice.visible_action_id_match,
            "decision_kind_match": choice.decision_kind_match,
            "semantic_accepted": choice.semantic_accepted,
            "observation_status": choice.observation_status,
            "public_progress_after_commit": choice.public_progress_after_commit,
            "completed_program_nodes_before": before_nodes,
            "completed_program_nodes_after": after_nodes,
            "program_node_progress": after_nodes > before_nodes,
            "terminal_verification_ready_before": any(
                item.candidate_family == "verify_terminal_operation" for item in candidate_rows
            ),
            "legal_no_progress_choice": legal_no_progress,
            "ordinary_replan_after_legal_no_progress": previous_legal_no_progress,
        }
        provisional = ChoiceDiagnostic.model_construct(diagnostic_id="pending", **values)
        diagnostics.append(
            ChoiceDiagnostic(
                diagnostic_id=_identity(
                    provisional,
                    "diagnostic_id",
                    "finance_v26_semantic_action_choice_diagnostic:",
                ),
                **values,
            )
        )
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.120 Choice rejection lacks its public Observation")
            rejections.append(rejection)
        previous_legal_no_progress = legal_no_progress
    if len(observations) != len(raw.observations):
        raise ValueError("v26.120 Choice diagnostics did not consume every Observation")
    return tuple(diagnostics)


def project_job_result(
    *,
    raw: runner.SemanticActionRawExecution,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[SemanticActionJobResult, tuple[ChoiceDiagnostic, ...]]:
    binding = runner.semantic_action_runtime_binding(prepared.static, raw.job)
    replay = legacy.replay_v3(raw, static=prepared.static.historical, binding=binding)
    mechanism = evaluate_mechanism_estimand(
        cast(Any, binding.record),
        raw.observations,
        stopped_by_model=raw.completed_result is not None,
    )
    verification: AuthorityPreservingVerificationReport | None = None
    if raw.completed_result is not None:
        verification, mechanism = _completed_verification(
            raw=raw,
            replay=replay,
            binding=binding,
        )
    diagnostics = build_choice_diagnostics(
        raw=raw,
        static=prepared.static,
        binding=binding,
    )
    exact_model, fallback_absent, native_absent, thinking, usage = _telemetry_flags(
        raw.provider_telemetry
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
        or not reversible
        or not replay.passed
        or raw.stage_two_provider_call_count
        or raw.cumulative_provider_tokens > 400000
    )
    transport = raw.terminal_disposition == "provider_transport_failure"
    typed = raw.terminal_disposition == "typed_budget_no_call"
    completion = raw.terminal_disposition == "completion_unusable"
    valid = bool(
        verification is not None
        and verification.valid
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
    repeated, repeated_failed = _repetition_counts(raw.observations)
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        _progress_diagnostic(binding.record, raw.observations)
    )
    route = _actual_route(raw.observations)
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
        raise ValueError("v26.120 first Choice and diagnostic diverged")
    recovery_choices = tuple(
        item for item in raw.semantic_choices if item.public_attempt_phase == "semantic_recovery"
    )
    if len(recovery_choices) > 1:
        raise ValueError("v26.120 Semantic Recovery Choice denominator changed")
    recovery = recovery_choices[0] if recovery_choices else None
    recovery_attempt_count = int(
        any(item.public_attempt_phase == "semantic_recovery" for item in raw.attempts)
    )
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
    values: dict[str, Any] = {
        "job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "provider_call_count": raw.stage_one_provider_call_count,
        "http_success_call_count": sum(item.http_success for item in raw.provider_telemetry),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length or 0 for item in raw.provider_telemetry
        ),
        "reasoning_tokens_total": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "completion_tokens_total": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "primary_attempt_count": sum(
            item.public_attempt_phase == "primary" for item in raw.attempts
        ),
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in raw.attempts
        ),
        "semantic_recovery_attempt_count": recovery_attempt_count,
        "direct_usable_request_count": sum(
            item.public_attempt_phase == "primary" and item.disposition == "usable"
            for item in raw.attempts
        ),
        "abi_rescued_usable_request_count": sum(
            item.public_attempt_phase == "abi_rescue" and item.disposition == "usable"
            for item in raw.attempts
        ),
        "semantic_recovery_usable_request_count": sum(
            item.public_attempt_phase == "semantic_recovery" and item.disposition == "usable"
            for item in raw.attempts
        ),
        "completion_failure_counts": dict(sorted(completion_counts.items())),
        "model_failure_family_counts": dict(sorted(family_counts.items())),
        "model_failure_subtype_counts": dict(sorted(subtype_counts.items())),
        "semantic_response_payload_count": sum(
            item.response_payload_present for item in semantic_attempts
        ),
        "exact_four_field_payload_count": sum(
            item.exact_four_field_payload for item in semantic_attempts
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
        "semantic_recovery_used": bool(recovery_attempt_count),
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
        "final_answer_emitted": raw.completed_result is not None,
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
    provisional = SemanticActionJobResult.model_construct(result_id="pending", **values)
    return (
        SemanticActionJobResult(
            result_id=_identity(
                provisional,
                "result_id",
                "finance_v26_semantic_action_job_result:",
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
    results: Sequence[SemanticActionJobResult],
    raw_by_job: Mapping[str, runner.SemanticActionRawExecution],
    output_dir: Path,
) -> SemanticActionRawLineageAudit:
    files: list[legacy.RawFileDescriptor] = []
    provider_ids: list[str] = []
    private_hits = 0
    for result in results:
        raw = raw_by_job[result.job_id]
        raw_path = runner.raw_execution_path(output_dir, raw.job)
        replayed = runner.SemanticActionRawExecution.model_validate(_load(raw_path))
        if replayed.model_dump(mode="json") != raw.model_dump(mode="json"):
            raise ValueError(f"v26.120 Raw replay changed: {result.job_id}")
        files.append(_descriptor(raw_path, output_dir))
        for descriptor in raw.provider_call_artifacts:
            path = output_dir / descriptor.relative_path
            payload = _load(path)
            artifact = runner.RawActionProviderCall.model_validate(payload)
            if (
                legacy.sha256_file(path) != descriptor.sha256
                or descriptor.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.120 Provider Artifact binding changed")
            provider_ids.append(artifact.artifact_id)
            private_hits += int(
                any(
                    key in {"private_reasoning", "reasoning_content"}
                    for key in _recursive_keys(payload)
                )
            )
            files.append(_descriptor(path, output_dir))
    ordered = tuple(sorted(files, key=lambda item: item.relative_path))
    values: dict[str, Any] = {
        "provider_call_count": len(provider_ids),
        "unique_provider_artifact_id_count": len(set(provider_ids)),
        "file_count": len(ordered),
        "files": ordered,
        "exact_byte_replay_pass_count": len(ordered),
        "private_reasoning_payload_count": private_hits,
    }
    provisional = SemanticActionRawLineageAudit.model_construct(audit_id="pending", **values)
    return SemanticActionRawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_semantic_action_raw_lineage:",
        ),
        **values,
    )


def _cell_summaries(
    results: Sequence[SemanticActionJobResult],
) -> tuple[SemanticActionCellSummary, ...]:
    cells: dict[tuple[str, str], list[SemanticActionJobResult]] = defaultdict(list)
    for item in results:
        cells[(item.mechanism_id, item.requested_path_strategy_id)].append(item)
    summaries: list[SemanticActionCellSummary] = []
    for (mechanism, path), rows in sorted(cells.items()):
        values: dict[str, Any] = {
            "mechanism_id": mechanism,
            "path_strategy_id": path,
            "job_count": len(rows),
            "model_invalid_count": sum(
                item.terminal_category == "model_invalid_trajectory" for item in rows
            ),
            "completion_unusable_count": sum(item.completion_unusable for item in rows),
            "typed_no_call_count": sum(item.typed_no_call for item in rows),
            "transport_failure_count": sum(item.provider_transport_failure for item in rows),
            "instrument_failure_count": sum(item.instrument_failure for item in rows),
            "first_action_legal_count": sum(item.first_action_id_legal for item in rows),
            "first_action_public_progress_count": sum(
                item.first_action_public_progress for item in rows
            ),
            "semantic_recovery_job_count": sum(item.semantic_recovery_used for item in rows),
            "program_closed_count": sum(item.program_closed for item in rows),
            "terminal_verification_completed_count": sum(
                item.postterminal_verification_completed for item in rows
            ),
            "final_answer_count": sum(item.final_answer_emitted for item in rows),
            "mechanism_success_count": sum(item.mechanism_success for item in rows),
            "independently_valid_count": sum(item.independent_validity for item in rows),
            "requested_path_adherence_count": sum(item.requested_path_adhered for item in rows),
        }
        provisional = SemanticActionCellSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            SemanticActionCellSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_semantic_action_cell_summary:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _decision_load_summaries(
    diagnostics: Sequence[ChoiceDiagnostic],
) -> tuple[DecisionLoadSummary, ...]:
    groups: dict[int, list[ChoiceDiagnostic]] = defaultdict(list)
    for item in diagnostics:
        groups[item.candidate_count].append(item)
    summaries: list[DecisionLoadSummary] = []
    for candidate_count, rows in sorted(groups.items()):
        values: dict[str, Any] = {
            "candidate_count": candidate_count,
            "decision_load_natural_log": math.log(candidate_count),
            "choice_count": len(rows),
            "semantic_accepted_count": sum(item.semantic_accepted for item in rows),
            "observation_count": sum(item.observation_status is not None for item in rows),
            "public_progress_count": sum(
                item.public_progress_after_commit is True for item in rows
            ),
            "program_node_progress_count": sum(item.program_node_progress for item in rows),
            "selected_reference_count": sum(
                item.selected_prompt_only_reference is True for item in rows
            ),
            "singleton_interface_diagnostic": candidate_count == 1,
        }
        provisional = DecisionLoadSummary.model_construct(summary_id="pending", **values)
        summaries.append(
            DecisionLoadSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_semantic_action_decision_load_summary:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _aggregate_counter(results: Sequence[SemanticActionJobResult], field: str) -> dict[str, int]:
    keys = {key for item in results for key in cast(dict[str, int], getattr(item, field))}
    return {
        key: sum(cast(dict[str, int], getattr(item, field)).get(key, 0) for item in results)
        for key in sorted(keys)
    }


def make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[SemanticActionJobResult],
    diagnostics: Sequence[ChoiceDiagnostic],
    lineage: SemanticActionRawLineageAudit,
) -> SemanticActionExecutionReport:
    terminal_counts = dict(sorted(Counter(item.terminal_category for item in results).items()))
    candidate_distribution = Counter(str(item.candidate_count) for item in diagnostics)
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    values: dict[str, Any] = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_validity_audit_id": prepared.preexecution_validity.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "terminal_counts": terminal_counts,
        "provider_call_count": sum(item.provider_call_count for item in results),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens_total for item in results),
        "completion_tokens_total": sum(item.completion_tokens_total for item in results),
        "primary_attempt_count": sum(item.primary_attempt_count for item in results),
        "abi_rescue_attempt_count": sum(item.abi_rescue_attempt_count for item in results),
        "semantic_recovery_attempt_count": sum(
            item.semantic_recovery_attempt_count for item in results
        ),
        "completion_failure_counts": _aggregate_counter(results, "completion_failure_counts"),
        "model_failure_family_counts": _aggregate_counter(results, "model_failure_family_counts"),
        "model_failure_subtype_counts": _aggregate_counter(results, "model_failure_subtype_counts"),
        "provider_response_count": sum(item.http_success_call_count for item in results),
        "exact_four_field_proposal_count": sum(
            item.exact_four_field_payload_count for item in results
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
        "decision_load_summaries": _decision_load_summaries(diagnostics),
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
        "terminal_verification_ready_choice_count": sum(
            item.terminal_verification_ready_choice_count for item in results
        ),
        "terminal_verification_choice_count": sum(
            item.terminal_verification_choice_count for item in results
        ),
        "successful_terminal_verification_observation_count": sum(
            item.successful_terminal_verification_observation_count for item in results
        ),
        "final_commit_count": sum(item.final_commit_count for item in results),
        "final_answer_count": sum(item.final_answer_emitted for item in results),
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
        "cell_summaries": _cell_summaries(results),
        "exact_model_passed": all(item.exact_model_passed for item in results),
        "native_tool_absence_passed": all(item.native_tool_absent for item in results),
        "thinking_continuity_passed": all(item.thinking_continuity_passed for item in results),
        "provider_usage_complete": all(item.provider_usage_complete for item in results),
        "fallback_absence_passed": all(item.fallback_absent for item in results),
        "dynamic_precall_binding_passed": all(
            item.dynamic_precall_binding_passed for item in results
        ),
        "exact_request_binding_passed": all(item.exact_request_binding_passed for item in results),
        "empirical_budget_adequacy_passed": not any(item.typed_no_call for item in results),
        "stage_two_authority_passed": all(
            item.reversible_commit_passed and not item.host_semantic_action_inserted
            for item in results
        ),
        "replay_v3_passed": all(item.replay_v3_passed for item in results),
    }
    provisional = SemanticActionExecutionReport.model_construct(report_id="pending", **values)
    return SemanticActionExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_semantic_action_execution_report:",
        ),
        **values,
    )


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[SemanticActionJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        SemanticActionJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.static.manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.120 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.120 checkpoint crosses the frozen denominator")
        raw_path = runner.raw_execution_path(output_dir, job)
        if (
            not raw_path.is_file()
            or legacy.sha256_file(raw_path) != result.raw_execution_artifact.sha256
        ):
            raise ValueError("v26.120 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[[AgentModelConfig, SemanticActionJob, Any], Any]


def _default_client_factory(
    config: AgentModelConfig,
    _job: SemanticActionJob,
    _binding: Any,
) -> StageOneProspectiveThinkingJsonClient:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: SemanticActionJob,
    prepared: PreparedExecution,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[
    SemanticActionJobResult,
    runner.SemanticActionRawExecution,
    tuple[ChoiceDiagnostic, ...],
]:
    binding = runner.semantic_action_runtime_binding(prepared.static, job)
    client = (
        None
        if client_factory is None
        else client_factory(prepared.static.agent_model_config, job, binding)
    )
    raw = runner.execute_semantic_action_job_raw(
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


def _write_checkpoint(path: Path, rows: Sequence[SemanticActionJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def run_semantic_action_calibration(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> SemanticActionExecutionReport:
    prepared = prepare_execution(
        runner_preflight_dir=runner_preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "semantic_action_job_results.checkpoint.jsonl"
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
        raise ValueError("v26.120 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = SemanticActionExecutionReport.model_validate(_load(report_path))
        if report.runner_contract_id != prepared.runner_contract.contract_id:
            raise ValueError("v26.120 completed report crosses Runner Contracts")
        return report
    raw_recovery_jobs = [
        item for item in pending if runner.raw_execution_path(output_dir, item).exists()
    ]
    model_pending_jobs = [
        item for item in pending if not runner.raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        provider_dir = runner.raw_provider_path(output_dir, job, 0).parent
        if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
            raise ValueError("orphan v26.120 Provider Artifacts require a fresh Recovery Contract")
    print(
        f"[v26.120] resuming {len(completed)}/32; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, runner.SemanticActionRawExecution] = {}
    diagnostics_by_job: dict[str, tuple[ChoiceDiagnostic, ...]] = {}
    for job in jobs:
        path = runner.raw_execution_path(output_dir, job)
        if path.exists() and job.job_id in completed:
            raw = runner.SemanticActionRawExecution.model_validate(_load(path))
            raw_by_job[job.job_id] = raw
            diagnostics_by_job[job.job_id] = build_choice_diagnostics(
                raw=raw,
                static=prepared.static,
                binding=runner.semantic_action_runtime_binding(prepared.static, job),
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
                    f"[v26.120] completed {len(completed)}/32 "
                    f"{job.job_id.rsplit(':', 1)[-1][:12]} "
                    f"terminal={result.terminal_category} "
                    f"calls={result.provider_call_count}",
                    flush=True,
                )
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 32:
        raise ValueError("v26.120 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.job_id,
            runner.SemanticActionRawExecution.model_validate(
                _load(runner.raw_execution_path(output_dir, job))
            ),
        )
        diagnostics_by_job.setdefault(
            job.job_id,
            build_choice_diagnostics(
                raw=raw_by_job[job.job_id],
                static=prepared.static,
                binding=runner.semantic_action_runtime_binding(prepared.static, job),
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
        output_dir / "semantic_action_job_results.json",
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
        description="Run the exact v26.120 Canonical Semantic Action calibration"
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
                    "outcome_measurement_contract_id": (prepared.outcome_contract.contract_id),
                    "preexecution_validity_audit_id": (prepared.preexecution_validity.audit_id),
                    "expected_jobs": len(prepared.static.manifest.jobs),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_semantic_action_calibration(
        runner_preflight_dir=args.runner_preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
