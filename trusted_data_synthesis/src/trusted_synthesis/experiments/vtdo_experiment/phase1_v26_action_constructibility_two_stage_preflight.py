from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay_v3 import (  # noqa: E501
    AuthorityPreservingReplayV3Contract,
    make_authority_preserving_replay_v3_contract,
    replay_authority_preserving_observations_v3,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_binding_and_usage_semantics import (  # noqa: E501
    Exact16KPathAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_contracts import (  # noqa: E501
    Exact16KRawExecution,
    Exact16KRawProviderCall,
    load_canonical_json,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_execution import (  # noqa: E501
    _runtime,
    load_static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_postrun_audit import (  # noqa: E501
    PostrunAuditReport,
    PostrunSourceReplayAudit,
    ProspectiveTransitionContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    _execute_observation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    ThinkingRepairPathAudit,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_action_constructibility import (
    ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
    BoundedFailureSummary,
    DecisionCommitCompilation,
    PublicActionState,
    SemanticDecisionProposal,
    build_public_action_state,
    classify_prospective_response_failure,
    compile_semantic_decision,
    decompile_public_call,
    make_semantic_decision_proposal,
    public_reference_policy_proposal_from_prompt,
    render_action_constructible_decision_prompt,
    render_semantically_sufficient_final_rescue_prompt,
    resolve_model_selectable_tool_or_typed_failure,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

RUN_ID: Final[
    Literal["finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822"]
] = "finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822"
V26_105_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_105_thinking_16k_completion_calibration_execution_v1_20260822"
)
V26_106_DIR = (
    "artifacts/vtdo_experiment/"
    "finance_v26_106_thinking_16k_completion_calibration_postrun_audit_v2_20260822"
)
EXPECTED_V26_106_REPORT_ID = (
    "finance_v26_exact_16k_postrun_audit_report:"
    "ba83dc516a0d4dbdf527cd9f630fd2e1ea513c1855c566c751aad86235cd1fd8"
)
EXPECTED_V26_106_TRANSITION_ID = (
    "finance_v26_exact_16k_postrun_transition:"
    "3b521a4324e067c94fa19b219514a7b9666e4638b8f31b5d8472dd673564ee90"
)
NEXT_STAGE: Final[
    Literal["fresh_two_stage_profiles_taskpackage_contract_manifest_and_runner_preflight_only"]
] = "fresh_two_stage_profiles_taskpackage_contract_manifest_and_runner_preflight_only"

IMPLEMENTATION_SOURCE_PATHS = (
    ("src/trusted_synthesis/runtime/agent/prospective_action_constructibility.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_verifier_replay_v3.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_action_constructibility_two_stage_preflight.py"
    ),
)
V26_106_OUTPUT_NAMES = (
    "completion_outcome_audit.json",
    "destructive_audit.json",
    "dynamic_budget_audit.json",
    "execution_lineage_audit.json",
    "instrument_root_cause_audit.json",
    "prospective_transition_contract.json",
    "provider_telemetry_audit.json",
    "report.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


SourceKind = Literal[
    "v26_106_transitive_source",
    "v26_106_output",
    "v26_107_implementation",
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
            raise ValueError("v26.107 source replay changed")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=1872, max_length=1872)
    predecessor_transitive_file_count: Literal[1860] = 1860
    predecessor_output_file_count: Literal[9] = 9
    implementation_file_count: Literal[3] = 3
    replayed_file_count: Literal[1872] = 1872
    replay_pass_count: Literal[1872] = 1872
    replay_before_diagnostics: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_action_constructibility_source_replay.v1"] = (
        "finance_v26_action_constructibility_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.107 source replay paths are not canonical")
        if self.audit_id != source_replay_audit_id(self):
            raise ValueError("v26.107 source replay identity changed")
        return self


class HistoricalActionInterfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_106_REPORT_ID
    raw_execution_count: Literal[32] = 32
    provider_artifact_count: Literal[572] = 572
    calculator_observation_count: Literal[382] = 382
    calculator_job_count: Literal[30] = 30
    calculator_success_count: Literal[1] = 1
    calculator_success_job_count: Literal[1] = 1
    code_defined_ready_calculator_count: Literal[382] = 382
    code_defined_not_ready_calculator_count: Literal[0] = 0
    bare_operand_count: Literal[188] = 188
    operand_object_wrong_fields_count: Literal[158] = 158
    operand_type_or_count_error_count: Literal[22] = 22
    parameters_mismatch_count: Literal[12] = 12
    reference_or_order_mismatch_count: Literal[1] = 1
    exact_argument_match_count: Literal[1] = 1
    contradictory_tool_affordance_prompt_count: Literal[79] = 79
    contradictory_tool_affordance_job_count: Literal[12] = 12
    contradictory_tool_id: Literal["open_document"] = "open_document"
    runtime_unknown_tool_observation_count: Literal[2] = 2
    old_prompt_full_tool_input_contract_exposed: Literal[False] = False
    old_prompt_public_symbol_binding_table_exposed: Literal[False] = False
    old_static_witness_read_exact_arguments: Literal[True] = True
    historical_terminal_reclassified: Literal[False] = False
    dominant_engineering_root: Literal["model_visible_action_contract_not_wire_complete"] = (
        "model_visible_action_contract_not_wire_complete"
    )
    status: Literal["root_cause_refined"] = "root_cause_refined"
    schema_version: Literal["finance_v26_historical_action_interface_audit.v1"] = (
        "finance_v26_historical_action_interface_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalActionInterfaceAudit:
        if (
            self.bare_operand_count
            + self.operand_object_wrong_fields_count
            + self.operand_type_or_count_error_count
            + self.parameters_mismatch_count
            + self.reference_or_order_mismatch_count
            + self.exact_argument_match_count
            != self.calculator_observation_count
        ):
            raise ValueError("v26.107 Calculator shape partition changed")
        if self.audit_id != historical_action_interface_audit_id(self):
            raise ValueError("v26.107 historical interface identity changed")
        return self


class FailureTaxonomyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_106_REPORT_ID
    historical_invalid_response_contract_count: Literal[33] = 33
    public_json_payload_present_count: Literal[33] = 33
    decision_answer_during_decision_count: Literal[22] = 22
    public_prompt_echo_count: Literal[7] = 7
    unregistered_action_enum_count: Literal[3] = 3
    final_answer_scalar_count: Literal[1] = 1
    prospective_decision_phase_control_count: Literal[22] = 22
    prospective_prompt_echo_instruction_count: Literal[7] = 7
    prospective_response_serialization_count: Literal[4] = 4
    historical_completion_failure_count_changed: Literal[False] = False
    historical_job_terminal_changed: Literal[False] = False
    prospective_taxonomy_only: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_prospective_failure_taxonomy_audit.v1"] = (
        "finance_v26_prospective_failure_taxonomy_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FailureTaxonomyAudit:
        if (
            self.decision_answer_during_decision_count
            + self.public_prompt_echo_count
            + self.unregistered_action_enum_count
            + self.final_answer_scalar_count
            != self.historical_invalid_response_contract_count
        ):
            raise ValueError("v26.107 response-contract partition changed")
        if self.audit_id != failure_taxonomy_audit_id(self):
            raise ValueError("v26.107 failure taxonomy identity changed")
        return self


class VerifierReplayRow(FrozenModel):
    job_id: str = Field(min_length=1)
    replay_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    exact_unavailable_tool_failure_count: int = Field(ge=0)
    passed: Literal[True] = True


class VerifierV3ReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    rows: tuple[VerifierReplayRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    replay_pass_count: Literal[32] = 32
    exact_unavailable_tool_failure_count: Literal[2] = 2
    old_verifier_replay_failure_count: Literal[2] = 2
    prospective_verifier_replay_failure_count: Literal[0] = 0
    historical_terminal_reclassified: Literal[False] = False
    model_action_inserted_or_chosen_by_verifier: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_verifier_v3_replay_audit.v1"] = (
        "finance_v26_verifier_v3_replay_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> VerifierV3ReplayAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted({item.job_id for item in self.rows})
        ):
            raise ValueError("v26.107 Verifier rows are not canonical")
        if self.audit_id != verifier_v3_replay_audit_id(self):
            raise ValueError("v26.107 Verifier audit identity changed")
        return self


class ActionConstructibilityProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    predecessor_transition_contract_id: str = EXPECTED_V26_106_TRANSITION_ID
    public_action_state_protocol: Literal["prospective_public_action_constructibility.v1"] = (
        ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION
    )
    stage_one_name: Literal["thinking_semantic_decision_proposal"] = (
        "thinking_semantic_decision_proposal"
    )
    stage_one_model_owned_semantic_fields: tuple[str, ...] = (
        "decision_kind",
        "tool_id",
        "node_id",
        "operator_id",
        "operand_sources",
        "direct_arguments",
        "evidence_ids",
    )
    stage_one_thinking_enabled_required: Literal[True] = True
    stage_one_private_reasoning_may_cross_boundary: Literal[False] = False
    stage_one_public_proposal_only_crosses_boundary: Literal[True] = True
    stage_two_name: Literal["deterministic_decision_commit_compilation"] = (
        "deterministic_decision_commit_compilation"
    )
    stage_two_provider_call_required: Literal[False] = False
    stage_two_may_choose_tool_node_operator_or_operand: Literal[False] = False
    stage_two_reversible_wire_serialization_only: Literal[True] = True
    complete_tool_input_grammar_exposed: Literal[True] = True
    resolved_public_symbol_bindings_exposed: Literal[True] = True
    correct_hidden_semantic_choice_exposed: Literal[False] = False
    variable_tools_must_be_subset_of_public_tools: Literal[True] = True
    shared_runtime_verifier_availability_gate_required: Literal[True] = True
    bounded_failure_history_retains_exact_argument_values: Literal[False] = False
    final_rescue_must_retain_terminal_public_result: Literal[True] = True
    prospective_failure_taxonomy_split_required: Literal[True] = True
    fresh_stage_one_model_profile_materialized: Literal[False] = False
    fresh_stage_one_completion_and_usage_bounds_frozen: Literal[False] = False
    fresh_dynamic_rollout_budget_contract_frozen: Literal[False] = False
    fresh_taskpackage_contract_manifest_job_identities_materialized: Literal[False] = False
    runner_implemented_and_preflighted: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_action_constructibility_protocol.v1"] = (
        "finance_v26_action_constructibility_protocol.v1"
    )

    @model_validator(mode="after")
    def validate_protocol(self) -> ActionConstructibilityProtocol:
        if self.protocol_id != action_constructibility_protocol_id(self):
            raise ValueError("v26.107 protocol identity changed")
        return self


class ActionConstructibilityFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    compiler_path_count: Literal[48] = 48
    compiler_call_count: int = Field(gt=0)
    compiler_unique_public_state_count: int = Field(gt=0)
    compiler_acquisition_proposal_count: int = Field(gt=0)
    compiler_operation_proposal_count: int = Field(gt=0)
    compiler_verification_proposal_count: int = Field(gt=0)
    reversible_compilation_pass_count: int = Field(gt=0)
    variable_tool_subset_pass_count: int = Field(gt=0)
    maximum_action_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    prompt_only_reference_task_count: Literal[24] = 24
    prompt_only_reference_decision_count: Literal[138] = 138
    prompt_only_reference_prompt_parse_count: Literal[138] = 138
    prompt_only_reference_call_count: Literal[114] = 114
    prompt_only_reference_typed_refinement_count: Literal[6] = 6
    prompt_only_reference_final_ready_count: Literal[24] = 24
    prompt_only_reference_failure_count_other_than_typed_refinement: Literal[0] = 0
    prompt_only_reference_reads_private_task_or_expected_arguments: Literal[False] = False
    full_failed_argument_value_count_in_new_history: Literal[0] = 0
    private_or_oracle_field_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    compiler_fixture_empirical_rows: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_action_constructibility_fixture.v1"] = (
        "finance_v26_action_constructibility_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ActionConstructibilityFixtureAudit:
        if self.reversible_compilation_pass_count != self.compiler_call_count:
            raise ValueError("v26.107 reversible compilation denominator changed")
        if (
            self.compiler_acquisition_proposal_count
            + self.compiler_operation_proposal_count
            + self.compiler_verification_proposal_count
            != self.compiler_call_count
        ):
            raise ValueError("v26.107 semantic proposal partition changed")
        if (
            self.prompt_only_reference_decision_count
            != self.prompt_only_reference_call_count + self.prompt_only_reference_final_ready_count
            or self.prompt_only_reference_prompt_parse_count
            != self.prompt_only_reference_decision_count
        ):
            raise ValueError("v26.107 Prompt-only reference denominator changed")
        if self.audit_id != action_constructibility_fixture_audit_id(self):
            raise ValueError("v26.107 action fixture identity changed")
        return self


class FinalRescueSemanticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    compiler_path_count: Literal[48] = 48
    semantically_sufficient_rescue_count: Literal[48] = 48
    maximum_rescue_prompt_utf8_bytes: int = Field(gt=0, le=6144)
    historical_completed_raw_file: Literal["raw_execution/7a8f36f5fe3b2b80e72b.json"] = (
        "raw_execution/7a8f36f5fe3b2b80e72b.json"
    )
    historical_terminal_value: Literal["0.4107"] = "0.4107"
    historical_primary_answer_was_scalar: Literal[True] = True
    historical_rescue_answer_value: Literal["0.1"] = "0.1"
    historical_rescue_retained_terminal_value: Literal[False] = False
    repaired_rescue_retains_terminal_value: Literal[True] = True
    repaired_historical_rescue_prompt_utf8_bytes: int = Field(gt=0, le=6144)
    previous_final_content_reused: Literal[False] = False
    private_reasoning_reused: Literal[False] = False
    historical_terminal_reclassified: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_final_rescue_semantic_audit.v1"] = (
        "finance_v26_final_rescue_semantic_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FinalRescueSemanticAudit:
        if self.audit_id != final_rescue_semantic_audit_id(self):
            raise ValueError("v26.107 Final Rescue identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != mutation_result_id(self):
            raise ValueError("v26.107 mutation identity changed")
        return self


class DestructivePreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    rejected_mutation_count: Literal[30] = 30
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_action_constructibility_destructive.v1"] = (
        "finance_v26_action_constructibility_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructivePreflightAudit:
        if self.audit_id != destructive_preflight_audit_id(self):
            raise ValueError("v26.107 destructive identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ActionConstructibilityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal["finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822"] = (
        RUN_ID
    )
    predecessor_report_id: str = EXPECTED_V26_106_REPORT_ID
    predecessor_transition_contract_id: str = EXPECTED_V26_106_TRANSITION_ID
    source_replay_audit_id: str = Field(min_length=1)
    historical_action_interface_audit_id: str = Field(min_length=1)
    failure_taxonomy_audit_id: str = Field(min_length=1)
    verifier_v3_contract_id: str = Field(min_length=1)
    verifier_v3_replay_audit_id: str = Field(min_length=1)
    action_constructibility_protocol_id: str = Field(min_length=1)
    action_constructibility_fixture_audit_id: str = Field(min_length=1)
    final_rescue_semantic_audit_id: str = Field(min_length=1)
    destructive_preflight_audit_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    status: Literal["design_preflight_passed_execution_not_authorized"] = (
        "design_preflight_passed_execution_not_authorized"
    )
    next_permitted_stage: Literal[
        "fresh_two_stage_profiles_taskpackage_contract_manifest_and_runner_preflight_only"
    ] = NEXT_STAGE
    historical_v26_105_job_rerun_count: Literal[0] = 0
    historical_v26_105_terminal_reclassification_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    single_stage_32k_allowed: Literal[False] = False
    role_protocol_frozen: Literal[False] = False
    capability_execution_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    release_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_action_constructibility_preflight_report.v1"] = (
        "finance_v26_action_constructibility_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ActionConstructibilityPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.107 report details are not canonical")
        if self.report_id != action_constructibility_preflight_report_id(self):
            raise ValueError("v26.107 report identity changed")
        return self


class _PathBinding(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    exact_path: Exact16KPathAudit
    source_path: ThinkingRepairPathAudit
    record: OperationalTaskRecord
    environment: AgentToolEnvironmentManifest
    prompt_contract: CompactPromptContract
    compiler_trajectory: Trajectory


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def source_replay_audit_id(value: SourceReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_action_constructibility_source_replay:")


def historical_action_interface_audit_id(value: HistoricalActionInterfaceAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_historical_action_interface:")


def failure_taxonomy_audit_id(value: FailureTaxonomyAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_prospective_failure_taxonomy:")


def verifier_v3_replay_audit_id(value: VerifierV3ReplayAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_verifier_v3_replay_audit:")


def action_constructibility_protocol_id(value: ActionConstructibilityProtocol) -> str:
    return _identity(value, "protocol_id", "finance_v26_action_constructibility_protocol:")


def action_constructibility_fixture_audit_id(
    value: ActionConstructibilityFixtureAudit,
) -> str:
    return _identity(value, "audit_id", "finance_v26_action_constructibility_fixture:")


def final_rescue_semantic_audit_id(value: FinalRescueSemanticAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_final_rescue_semantic_audit:")


def mutation_result_id(value: MutationResult) -> str:
    return _identity(value, "mutation_id", "finance_v26_action_constructibility_mutation:")


def destructive_preflight_audit_id(value: DestructivePreflightAudit) -> str:
    return _identity(value, "audit_id", "finance_v26_action_constructibility_destructive:")


def action_constructibility_preflight_report_id(
    value: ActionConstructibilityPreflightReport,
) -> str:
    return _identity(value, "report_id", "finance_v26_action_constructibility_preflight_report:")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    payload = _canonical_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable v26.107 output changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_predecessor(
    package_root: Path,
) -> tuple[
    PostrunAuditReport,
    PostrunSourceReplayAudit,
    ProspectiveTransitionContract,
]:
    directory = package_root / V26_106_DIR
    report = PostrunAuditReport.model_validate(load_canonical_json(directory / "report.json"))
    replay = PostrunSourceReplayAudit.model_validate(
        load_canonical_json(directory / "source_replay_audit.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        load_canonical_json(directory / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_V26_106_REPORT_ID
        or report.source_replay_audit_id != replay.audit_id
        or report.prospective_transition_contract_id != transition.contract_id
        or transition.contract_id != EXPECTED_V26_106_TRANSITION_ID
        or transition.next_permitted_stage
        != (
            "authority_preserving_unknown_tool_replay_repair_and_"
            "true_two_stage_protocol_preflight_only"
        )
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.107 predecessor authorization changed")
    return report, replay, transition


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
    predecessor: PostrunSourceReplayAudit,
) -> SourceReplayAudit:
    rows: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = package_root / item.relative_path
        observed = _sha256(path)
        rows[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_106_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    for name in V26_106_OUTPUT_NAMES:
        relative = f"{V26_106_DIR}/{name}"
        path = package_root / relative
        digest = _sha256(path)
        rows[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_106_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        path = implementation_root / relative
        digest = _sha256(path)
        rows[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_107_implementation",
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


def _load_execution(
    package_root: Path,
) -> tuple[tuple[Exact16KRawExecution, ...], tuple[Exact16KRawProviderCall, ...]]:
    directory = package_root / V26_105_DIR
    raws = tuple(
        Exact16KRawExecution.model_validate(load_canonical_json(path))
        for path in sorted((directory / "raw_execution").glob("*.json"))
    )
    providers = tuple(
        Exact16KRawProviderCall.model_validate(load_canonical_json(path))
        for path in sorted((directory / "raw_provider_calls").glob("*/*.json"))
    )
    if len(raws) != 32 or len(providers) != 572:
        raise ValueError("v26.107 execution denominator changed")
    return raws, providers


def _path_binding(static: Any, exact_path: Exact16KPathAudit) -> _PathBinding:
    exact_8k = {item.audit_id: item for item in static.predecessor_exact_8k_paths}[
        exact_path.predecessor_path_audit_id
    ]
    bound = {item.audit_id: item for item in static.predecessor_bound_paths}[
        exact_8k.predecessor_path_audit_id
    ]
    source = {item.audit_id: item for item in static.source_registered_paths}[
        bound.predecessor_path_audit_id
    ]
    task = {item.task_package_id: item for item in static.task_packages}[exact_path.task_package_id]
    record = {item.record_id: item for item in static.records}[task.operational_record_id]
    environment = {item.manifest_id: item for item in static.environments}[
        task.environment_manifest_id
    ]
    prompt = {item.contract_id: item for item in static.prompt_contracts}[
        task.compact_prompt_contract_id
    ]
    budget_path = {item.audit_id: item for item in static.predecessor_budget_paths}[
        source.predecessor_path_audit_id
    ]
    trajectory = {item.trajectory_id: item for item in static.compiler_trajectories}[
        budget_path.compiler_trajectory_id
    ]
    if (
        source.path_strategy_id != exact_path.path_strategy_id
        or source.mechanism_id != exact_path.mechanism_id
        or record.environment_manifest_id != environment.manifest_id
        or trajectory.task_id != record.task_package.task.task_id
    ):
        raise ValueError("v26.107 path lineage changed")
    return _PathBinding(
        exact_path=exact_path,
        source_path=source,
        record=record,
        environment=environment,
        prompt_contract=prompt,
        compiler_trajectory=trajectory,
    )


def _expected_arguments(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("expected_arguments") or payload.get("argument_contract")
    if not isinstance(value, Mapping):
        raise ValueError("ready Calculator node lacks public argument semantics")
    return value


def _build_historical_interface(
    static: Any,
    raws: Sequence[Exact16KRawExecution],
    providers: Sequence[Exact16KRawProviderCall],
) -> HistoricalActionInterfaceAudit:
    shape_counts: Counter[str] = Counter()
    calculator_jobs: set[str] = set()
    successful_jobs: set[str] = set()
    ready_count = 0
    not_ready_count = 0
    unknown_count = 0
    for raw in raws:
        binding = _path_binding(
            static,
            next(item for item in static.path_audits if item.audit_id == raw.job.path_audit_id),
        )
        task = binding.record.task_package.task.public
        unknown_count += sum(
            item.error_code == "unknown_or_unselectable_tool" for item in raw.observations
        )
        for index, observation in enumerate(raw.observations):
            if observation.call.tool_id != "calculator":
                continue
            calculator_jobs.add(raw.job.job_id)
            progress = public_operation_progress(task, tuple(raw.observations[:index]))
            if progress is None:
                raise ValueError("v26.107 Calculator progress disappeared")
            ready = tuple(
                item
                for item in progress["ready_nodes"]
                if item.get("tool_id") == "calculator" and not item.get("unresolved_symbols")
            )
            if not ready:
                not_ready_count += 1
                continue
            ready_count += 1
            expected = _expected_arguments(ready[0])
            observed = observation.call.arguments
            operands = observed.get("operands")
            expected_operands = expected.get("operands")
            if (
                not isinstance(operands, list)
                or not isinstance(expected_operands, list)
                or len(operands) != len(expected_operands)
            ):
                shape_counts["operand_type_or_count"] += 1
            elif any(not isinstance(item, Mapping) for item in operands):
                shape_counts["bare_operand"] += 1
            elif any(
                set(item) != set(expected_item)
                for item, expected_item in zip(operands, expected_operands, strict=True)
            ):
                shape_counts["operand_object_wrong_fields"] += 1
            elif observed.get("parameters") != expected.get("parameters"):
                shape_counts["parameters_mismatch"] += 1
            elif operands != expected_operands:
                shape_counts["reference_or_order_mismatch"] += 1
            else:
                allowed = set(ready[0].get("allowed_operators") or (expected.get("operator"),))
                if observed.get("operator") not in allowed:
                    shape_counts["reference_or_order_mismatch"] += 1
                else:
                    shape_counts["exact_match"] += 1
                    if observation.status == "succeeded":
                        successful_jobs.add(raw.job.job_id)
    contradiction_rows = []
    for provider in providers:
        _, separator, raw_payload = provider.prompt.partition("\n")
        if not separator:
            continue
        payload = json.loads(raw_payload)
        if not isinstance(payload, Mapping):
            continue
        context = payload.get("public_context")
        if not isinstance(context, Mapping):
            continue
        raw_tools = context.get("tools")
        tools = {
            str(item.get("tool_id"))
            for item in raw_tools or ()
            if isinstance(item, Mapping) and item.get("tool_id")
        }
        operation = context.get("public_operation")
        variables = operation.get("variables") if isinstance(operation, Mapping) else None
        inconsistent = {
            str(tool_id)
            for variable in variables or ()
            if isinstance(variable, Mapping)
            for tool_id in variable.get("acquisition_tools") or ()
            if str(tool_id) not in tools
        }
        if inconsistent:
            contradiction_rows.append((provider.job_id, tuple(sorted(inconsistent))))
    if set(item[1] for item in contradiction_rows) != {("open_document",)}:
        raise ValueError("v26.107 contradictory tool identity changed")
    values = {
        "calculator_job_count": len(calculator_jobs),
        "calculator_success_job_count": len(successful_jobs),
        "code_defined_ready_calculator_count": ready_count,
        "code_defined_not_ready_calculator_count": not_ready_count,
        "bare_operand_count": shape_counts["bare_operand"],
        "operand_object_wrong_fields_count": shape_counts["operand_object_wrong_fields"],
        "operand_type_or_count_error_count": shape_counts["operand_type_or_count"],
        "parameters_mismatch_count": shape_counts["parameters_mismatch"],
        "reference_or_order_mismatch_count": shape_counts["reference_or_order_mismatch"],
        "exact_argument_match_count": shape_counts["exact_match"],
        "contradictory_tool_affordance_prompt_count": len(contradiction_rows),
        "contradictory_tool_affordance_job_count": len({item[0] for item in contradiction_rows}),
        "runtime_unknown_tool_observation_count": unknown_count,
    }
    provisional = HistoricalActionInterfaceAudit.model_construct(audit_id="pending", **values)
    return HistoricalActionInterfaceAudit(
        audit_id=historical_action_interface_audit_id(provisional),
        **values,
    )


def _provider_by_attempt(
    providers: Sequence[Exact16KRawProviderCall],
) -> dict[tuple[str, int], Exact16KRawProviderCall]:
    output = {(item.job_id, item.call_index): item for item in providers}
    if len(output) != len(providers):
        raise ValueError("v26.107 Provider call keys are duplicated")
    return output


def _build_failure_taxonomy(
    raws: Sequence[Exact16KRawExecution],
    providers: Sequence[Exact16KRawProviderCall],
) -> FailureTaxonomyAudit:
    provider_map = _provider_by_attempt(providers)
    subtype_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    row_count = 0
    for raw in raws:
        for attempt in raw.request_attempts:
            failure = attempt.failure_artifact
            if failure is None or failure.failure_type != "invalid_response_contract":
                continue
            if attempt.provider_call_index is None:
                raise ValueError("v26.107 invalid response lacks Provider parent")
            provider = provider_map[(raw.job.job_id, attempt.provider_call_index)]
            payload = provider.response_payload
            if not isinstance(payload, Mapping):
                raise ValueError("v26.107 invalid response lacks retained public JSON")
            classification = classify_prospective_response_failure(
                request_kind=attempt.request_kind,
                payload=payload,
                json_parse_succeeded=True,
            )
            family_counts[classification.family] += 1
            subtype_counts[classification.subtype] += 1
            row_count += 1
    values = {
        "historical_invalid_response_contract_count": row_count,
        "public_json_payload_present_count": row_count,
        "decision_answer_during_decision_count": subtype_counts[
            "answer_or_non_action_emitted_during_decision"
        ],
        "public_prompt_echo_count": subtype_counts["public_prompt_payload_echoed"],
        "unregistered_action_enum_count": subtype_counts["unregistered_decision_action_enum"],
        "final_answer_scalar_count": subtype_counts["final_answer_not_exact_object_contract"],
        "prospective_decision_phase_control_count": family_counts["decision_phase_control_failure"],
        "prospective_prompt_echo_instruction_count": family_counts[
            "prompt_echo_instruction_failure"
        ],
        "prospective_response_serialization_count": family_counts["response_serialization_failure"],
    }
    provisional = FailureTaxonomyAudit.model_construct(audit_id="pending", **values)
    return FailureTaxonomyAudit(audit_id=failure_taxonomy_audit_id(provisional), **values)


def _build_verifier_audit(
    static: Any,
    raws: Sequence[Exact16KRawExecution],
    contract: AuthorityPreservingReplayV3Contract,
) -> VerifierV3ReplayAudit:
    rows = []
    for raw in raws:
        path = next(item for item in static.path_audits if item.audit_id == raw.job.path_audit_id)
        binding = _path_binding(static, path)
        replay = replay_authority_preserving_observations_v3(
            contract,
            static.replay_contract,
            binding.record,
            binding.environment,
            raw.observations,
        )
        if not replay.passed:
            raise ValueError(f"v26.107 Verifier v3 failed: {replay.failure_ids}")
        rows.append(
            VerifierReplayRow(
                job_id=raw.job.job_id,
                replay_id=replay.replay_id,
                observation_count=replay.observation_count,
                exact_unavailable_tool_failure_count=(replay.exact_unavailable_tool_failure_count),
            )
        )
    rows = sorted(rows, key=lambda item: item.job_id)
    values = {
        "verifier_contract_id": contract.contract_id,
        "rows": tuple(rows),
        "replay_pass_count": sum(item.passed for item in rows),
        "exact_unavailable_tool_failure_count": sum(
            item.exact_unavailable_tool_failure_count for item in rows
        ),
    }
    provisional = VerifierV3ReplayAudit.model_construct(audit_id="pending", **values)
    return VerifierV3ReplayAudit(audit_id=verifier_v3_replay_audit_id(provisional), **values)


def _build_protocol() -> ActionConstructibilityProtocol:
    provisional = ActionConstructibilityProtocol.model_construct(protocol_id="pending")
    return ActionConstructibilityProtocol(
        protocol_id=action_constructibility_protocol_id(provisional)
    )


def _trajectory_observations(trajectory: Trajectory) -> tuple[AgentToolObservation, ...]:
    return tuple(
        AgentToolObservation.model_validate(item.observation)
        for item in trajectory.steps
        if item.tool_name is not None and item.observation is not None
    )


def _contains_forbidden_history_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("evidence:") or value.startswith("operation:")
    if isinstance(value, Mapping):
        return any(_contains_forbidden_history_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_history_value(item) for item in value)
    return False


def _build_action_fixture(
    static: Any,
    protocol: ActionConstructibilityProtocol,
) -> tuple[
    ActionConstructibilityFixtureAudit,
    PublicActionState,
    PublicActionState,
    PublicActionState,
    SemanticDecisionProposal,
    DecisionCommitCompilation,
]:
    proposal_counts: Counter[str] = Counter()
    state_ids: set[str] = set()
    compiler_calls = 0
    subset_passes = 0
    maximum_prompt_bytes = 0
    operation_state: PublicActionState | None = None
    terminal_state: PublicActionState | None = None
    operation_proposal: SemanticDecisionProposal | None = None
    operation_commit: DecisionCommitCompilation | None = None
    initial_state: PublicActionState | None = None
    for exact_path in static.path_audits:
        binding = _path_binding(static, exact_path)
        observations: list[AgentToolObservation] = []
        for step in binding.compiler_trajectory.steps:
            if step.tool_name is None:
                continue
            state = build_public_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
            )
            state = PublicActionState.model_validate_json(state.model_dump_json())
            if initial_state is None:
                initial_state = state
            prompt = render_action_constructible_decision_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=(
                    None
                    if binding.source_path.role == "capability"
                    else binding.source_path.path_strategy_id
                ),
            )
            maximum_prompt_bytes = max(maximum_prompt_bytes, len(prompt.encode("utf-8")))
            subset_passes += 1
            call = AgentToolCall(
                call_index=len(observations) + 1,
                tool_id=step.tool_name,
                arguments=step.tool_input,
            )
            proposal = decompile_public_call(state, call)
            commit = compile_semantic_decision(
                state,
                proposal,
                call_index=call.call_index,
            )
            if commit.call != call:
                raise ValueError("v26.107 compiler call changed after semantic roundtrip")
            proposal_counts[proposal.decision_kind] += 1
            compiler_calls += 1
            state_ids.add(state.state_id)
            if proposal.decision_kind == "execute_public_operation" and operation_state is None:
                operation_state = state
                operation_proposal = proposal
                operation_commit = commit
            if proposal.decision_kind == "verify_terminal_operation" and terminal_state is None:
                terminal_state = state
            observations.append(AgentToolObservation.model_validate(step.observation))
    seen_tasks: set[str] = set()
    reference_calls = 0
    reference_decisions = 0
    reference_refinements = 0
    reference_final_ready = 0
    other_reference_failures = 0
    exact_history_values = 0
    for exact_path in static.path_audits:
        binding = _path_binding(static, exact_path)
        task_key = binding.exact_path.task_package_id
        if task_key in seen_tasks:
            continue
        seen_tasks.add(task_key)
        reference_observations: list[AgentToolObservation] = []
        runtime = _runtime(binding.record, binding.environment)
        for _ in range(24):
            state = build_public_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(reference_observations),
            )
            state = PublicActionState.model_validate_json(state.model_dump_json())
            if any(
                _contains_forbidden_history_value(item.argument_shape)
                for item in state.bounded_failure_history
            ):
                exact_history_values += 1
            prompt = render_action_constructible_decision_prompt(
                instruction=binding.record.task_package.task.public.instruction,
                state=state,
                public_path_condition=(
                    None
                    if binding.source_path.role == "capability"
                    else binding.source_path.path_strategy_id
                ),
            )
            proposal = public_reference_policy_proposal_from_prompt(prompt)
            reference_decisions += 1
            commit = compile_semantic_decision(
                state,
                proposal,
                call_index=len(reference_observations) + 1,
            )
            if commit.call is None:
                if not state.final_answer_allowed:
                    raise ValueError("v26.107 fixture emitted final before readiness")
                reference_final_ready += 1
                break
            projection = CompletionProjection(
                request_kind="decision",
                action="call_tool",
                tool_id=commit.call.tool_id,
                arguments=commit.call.arguments,
            )
            observation = _execute_observation(
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(reference_observations),
                projection=projection,
            )
            reference_observations.append(observation)
            reference_calls += 1
            if observation.status == "failed":
                if observation.error_code == "typed_selector_requires_refinement":
                    reference_refinements += 1
                else:
                    other_reference_failures += 1
        else:
            raise ValueError("v26.107 public reference fixture exceeded its call bound")
    if any(
        item is None
        for item in (
            initial_state,
            operation_state,
            terminal_state,
            operation_proposal,
            operation_commit,
        )
    ):
        raise ValueError("v26.107 destructive fixture states are incomplete")
    values = {
        "protocol_id": protocol.protocol_id,
        "compiler_call_count": compiler_calls,
        "compiler_unique_public_state_count": len(state_ids),
        "compiler_acquisition_proposal_count": proposal_counts["acquire_public_input"],
        "compiler_operation_proposal_count": proposal_counts["execute_public_operation"],
        "compiler_verification_proposal_count": proposal_counts["verify_terminal_operation"],
        "reversible_compilation_pass_count": compiler_calls,
        "variable_tool_subset_pass_count": subset_passes,
        "maximum_action_prompt_utf8_bytes": maximum_prompt_bytes,
        "prompt_only_reference_decision_count": reference_decisions,
        "prompt_only_reference_prompt_parse_count": reference_decisions,
        "prompt_only_reference_call_count": reference_calls,
        "prompt_only_reference_typed_refinement_count": reference_refinements,
        "prompt_only_reference_final_ready_count": reference_final_ready,
        "prompt_only_reference_failure_count_other_than_typed_refinement": (
            other_reference_failures
        ),
        "full_failed_argument_value_count_in_new_history": exact_history_values,
    }
    provisional = ActionConstructibilityFixtureAudit.model_construct(
        audit_id="pending",
        **values,
    )
    audit = ActionConstructibilityFixtureAudit(
        audit_id=action_constructibility_fixture_audit_id(provisional),
        **values,
    )
    return (
        audit,
        cast(PublicActionState, initial_state),
        cast(PublicActionState, operation_state),
        cast(PublicActionState, terminal_state),
        cast(SemanticDecisionProposal, operation_proposal),
        cast(DecisionCommitCompilation, operation_commit),
    )


def _find_provider(
    providers: Sequence[Exact16KRawProviderCall],
    *,
    job_id: str,
    call_index: int,
) -> Exact16KRawProviderCall:
    matches = tuple(
        item for item in providers if item.job_id == job_id and item.call_index == call_index
    )
    if len(matches) != 1:
        raise ValueError("v26.107 historical Provider parent is not unique")
    return matches[0]


def _extract_terminal_value(value: Any) -> str | None:
    if isinstance(value, Mapping):
        output = value.get("output")
        if isinstance(output, Mapping) and "value" in output:
            return str(output["value"])
        for item in value.values():
            found = _extract_terminal_value(item)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _extract_terminal_value(item)
            if found is not None:
                return found
    return None


def _build_final_rescue_audit(
    static: Any,
    protocol: ActionConstructibilityProtocol,
    raws: Sequence[Exact16KRawExecution],
    providers: Sequence[Exact16KRawProviderCall],
) -> FinalRescueSemanticAudit:
    sizes = []
    for exact_path in static.path_audits:
        binding = _path_binding(static, exact_path)
        observations = _trajectory_observations(binding.compiler_trajectory)
        source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            observations,
            public_path_condition=(
                None
                if binding.source_path.role == "capability"
                else binding.source_path.path_strategy_id
            ),
        )
        rescue = render_semantically_sufficient_final_rescue_prompt(
            source,
            failure_type="invalid_response_contract",
        )
        payload = json.loads(rescue.partition("\n")[2])
        if not payload.get("terminal_result_projection"):
            raise ValueError("v26.107 Final Rescue lost public terminal semantics")
        sizes.append(len(rescue.encode("utf-8")))
    historical = next(
        item
        for item in raws
        if item.artifact_id.endswith(
            "9bb753726d56561562b7fb6e04ac96917621b313718b581775e6ce09d290d643"
        )
    )
    primary = next(
        item
        for item in historical.request_attempts
        if item.request_kind == "final_answer" and item.phase == "primary"
    )
    rescue_attempt = next(
        item
        for item in historical.request_attempts
        if item.request_kind == "final_answer" and item.phase == "rescue"
    )
    if primary.provider_call_index is None or rescue_attempt.provider_call_index is None:
        raise ValueError("v26.107 historical Final attempts lack Provider parents")
    primary_provider = _find_provider(
        providers,
        job_id=historical.job.job_id,
        call_index=primary.provider_call_index,
    )
    rescue_provider = _find_provider(
        providers,
        job_id=historical.job.job_id,
        call_index=rescue_attempt.provider_call_index,
    )
    repaired = render_semantically_sufficient_final_rescue_prompt(
        primary_provider.prompt,
        failure_type="invalid_response_contract",
    )
    repaired_payload = json.loads(repaired.partition("\n")[2])
    terminal_value = _extract_terminal_value(repaired_payload["terminal_result_projection"])
    primary_answer = (primary_provider.response_payload or {}).get("answer")
    rescue_answer = (rescue_provider.response_payload or {}).get("answer")
    rescue_value = rescue_answer.get("value") if isinstance(rescue_answer, Mapping) else None
    values = {
        "protocol_id": protocol.protocol_id,
        "maximum_rescue_prompt_utf8_bytes": max(sizes),
        "historical_terminal_value": str(terminal_value),
        "historical_primary_answer_was_scalar": not isinstance(primary_answer, Mapping),
        "historical_rescue_answer_value": str(rescue_value),
        "historical_rescue_retained_terminal_value": "0.4107" in rescue_provider.prompt,
        "repaired_rescue_retains_terminal_value": "0.4107" in repaired,
        "repaired_historical_rescue_prompt_utf8_bytes": len(repaired.encode("utf-8")),
    }
    provisional = FinalRescueSemanticAudit.model_construct(audit_id="pending", **values)
    return FinalRescueSemanticAudit(
        audit_id=final_rescue_semantic_audit_id(provisional),
        **values,
    )


def _expect_rejection(name: str, function: Callable[[], Any]) -> MutationResult:
    try:
        function()
    except (ValueError, TypeError, KeyError):
        values = {"mutation": name}
        provisional = MutationResult.model_construct(mutation_id="pending", **values)
        return MutationResult(mutation_id=mutation_result_id(provisional), **values)
    raise AssertionError(f"v26.107 destructive mutation passed: {name}")


def _replace_model(value: BaseModel, **updates: Any) -> dict[str, Any]:
    payload = value.model_dump(mode="json")
    payload.update(updates)
    return payload


def _build_destructive_audit(
    initial: PublicActionState,
    operation: PublicActionState,
    terminal: PublicActionState,
    proposal: SemanticDecisionProposal,
    commit: DecisionCommitCompilation,
    verifier_contract: AuthorityPreservingReplayV3Contract,
    environment: AgentToolEnvironmentManifest,
) -> DestructivePreflightAudit:
    grammar = operation.tool_grammars[0]
    operation_row = operation.ready_operations[0]
    wrong_state = "prospective_public_action_state:" + "0" * 64
    cases: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "stale_public_action_state_identity",
            lambda: PublicActionState.model_validate(
                _replace_model(operation, state_id=wrong_state)
            ),
        ),
        (
            "variable_tool_outside_public_grammar",
            lambda: PublicActionState.model_validate(
                _replace_model(operation, tool_grammars=(grammar,))
            ),
        ),
        (
            "duplicate_public_binding",
            lambda: PublicActionState.model_validate(
                _replace_model(
                    operation,
                    resolved_bindings=(
                        *operation.resolved_bindings,
                        operation.resolved_bindings[0],
                    ),
                )
            ),
        ),
        (
            "final_ready_without_public_source",
            lambda: PublicActionState.model_validate(
                _replace_model(operation, final_answer_allowed=True)
            ),
        ),
        (
            "private_expected_arguments_in_tool_grammar",
            lambda: PublicActionState.model_validate(
                _replace_model(
                    operation,
                    tool_grammars=(
                        {
                            **grammar.model_dump(mode="json"),
                            "input_contract": {"expected_arguments": "private"},
                            "required_input_fields": ("expected_arguments",),
                        },
                    ),
                )
            ),
        ),
        (
            "proposal_bound_to_another_state",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=wrong_state,
                    decision_kind=proposal.decision_kind,
                    tool_id=proposal.tool_id,
                    node_id=proposal.node_id,
                    operator_id=proposal.operator_id,
                    operand_sources=proposal.operand_sources,
                ),
                call_index=1,
            ),
        ),
        (
            "proposal_selects_unknown_tool",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="execute_public_operation",
                    tool_id="unknown_tool",
                    node_id=operation_row.node_id,
                    operator_id=proposal.operator_id,
                    operand_sources=proposal.operand_sources,
                ),
                call_index=1,
            ),
        ),
        (
            "proposal_selects_unready_node",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="execute_public_operation",
                    tool_id=proposal.tool_id,
                    node_id="unready_node",
                    operator_id=proposal.operator_id,
                    operand_sources=proposal.operand_sources,
                ),
                call_index=1,
            ),
        ),
        (
            "proposal_selects_unregistered_operator",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="execute_public_operation",
                    tool_id=proposal.tool_id,
                    node_id=proposal.node_id,
                    operator_id="unregistered_operator",
                    operand_sources=proposal.operand_sources,
                ),
                call_index=1,
            ),
        ),
        (
            "proposal_reverses_operand_order",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="execute_public_operation",
                    tool_id=proposal.tool_id,
                    node_id=proposal.node_id,
                    operator_id=proposal.operator_id,
                    operand_sources=tuple(reversed(proposal.operand_sources)),
                ),
                call_index=1,
            ),
        ),
        (
            "proposal_omits_operand_source",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="execute_public_operation",
                    tool_id=proposal.tool_id,
                    node_id=proposal.node_id,
                    operator_id=proposal.operator_id,
                    operand_sources=proposal.operand_sources[:-1],
                ),
                call_index=1,
            ),
        ),
        (
            "operation_proposed_before_public_bindings",
            lambda: compile_semantic_decision(
                initial,
                make_semantic_decision_proposal(
                    state_id=initial.state_id,
                    decision_kind="execute_public_operation",
                    tool_id=operation_row.tool_id,
                    node_id=operation_row.node_id,
                    operator_id=proposal.operator_id,
                    operand_sources=proposal.operand_sources,
                ),
                call_index=1,
            ),
        ),
        (
            "verification_before_terminal",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="verify_terminal_operation",
                    tool_id="cross_check_evidence",
                    evidence_ids=operation.selected_evidence_ids,
                ),
                call_index=1,
            ),
        ),
        (
            "verification_selects_unknown_evidence",
            lambda: compile_semantic_decision(
                terminal,
                make_semantic_decision_proposal(
                    state_id=terminal.state_id,
                    decision_kind="verify_terminal_operation",
                    tool_id="cross_check_evidence",
                    evidence_ids=("evidence:unknown",),
                ),
                call_index=1,
            ),
        ),
        (
            "verification_selects_wrong_tool",
            lambda: compile_semantic_decision(
                terminal,
                make_semantic_decision_proposal(
                    state_id=terminal.state_id,
                    decision_kind="verify_terminal_operation",
                    tool_id="calculator",
                    evidence_ids=terminal.selected_evidence_ids,
                ),
                call_index=1,
            ),
        ),
        (
            "final_answer_before_readiness",
            lambda: compile_semantic_decision(
                operation,
                make_semantic_decision_proposal(
                    state_id=operation.state_id,
                    decision_kind="emit_final_answer",
                ),
                call_index=1,
            ),
        ),
        (
            "acquisition_uses_operation_tool",
            lambda: compile_semantic_decision(
                initial,
                make_semantic_decision_proposal(
                    state_id=initial.state_id,
                    decision_kind="acquire_public_input",
                    tool_id="calculator",
                    direct_arguments={"operator": "difference", "operands": [], "parameters": {}},
                ),
                call_index=1,
            ),
        ),
        (
            "acquisition_missing_required_arguments",
            lambda: compile_semantic_decision(
                initial,
                make_semantic_decision_proposal(
                    state_id=initial.state_id,
                    decision_kind="acquire_public_input",
                    tool_id="query_structured_fact",
                    direct_arguments={},
                ),
                call_index=1,
            ),
        ),
        (
            "decompile_unknown_call",
            lambda: decompile_public_call(
                operation,
                AgentToolCall(call_index=1, tool_id="unknown_tool", arguments={}),
            ),
        ),
        (
            "stale_semantic_proposal_identity",
            lambda: SemanticDecisionProposal.model_validate(
                _replace_model(proposal, proposal_id="prospective_semantic_decision_proposal:bad")
            ),
        ),
        (
            "stale_decision_commit_identity",
            lambda: DecisionCommitCompilation.model_validate(
                _replace_model(commit, commit_id="prospective_decision_commit_compilation:bad")
            ),
        ),
        (
            "commit_call_semantics_changed",
            lambda: DecisionCommitCompilation.model_validate(
                _replace_model(
                    commit,
                    call={
                        **cast(AgentToolCall, commit.call).model_dump(mode="json"),
                        "tool_id": "changed_tool",
                    },
                )
            ),
        ),
        (
            "commit_action_without_call",
            lambda: DecisionCommitCompilation.model_validate(_replace_model(commit, call=None)),
        ),
        (
            "verifier_v3_stale_contract_identity",
            lambda: AuthorityPreservingReplayV3Contract.model_validate(
                _replace_model(verifier_contract, contract_id="bad")
            ),
        ),
        (
            "unknown_tool_typed_failure_changed",
            lambda: _assert_equal(
                _unavailable_error_code(environment),
                "changed_error_code",
            ),
        ),
        (
            "final_rescue_missing_json_payload",
            lambda: render_semantically_sufficient_final_rescue_prompt(
                "no payload",
                failure_type="invalid_response_contract",
            ),
        ),
        (
            "final_rescue_missing_terminal_progress",
            lambda: render_semantically_sufficient_final_rescue_prompt(
                "header\n{}",
                failure_type="invalid_response_contract",
            ),
        ),
        (
            "failure_summary_retains_exact_evidence_value",
            lambda: _assert_no_exact_history_value(
                BoundedFailureSummary(
                    failed_tool_id="calculator",
                    error_category="public_operation_node_contract",
                    latest_call_index=1,
                    blocked_call_signature_hash="hash",
                    argument_shape={"operand": "evidence:forbidden"},
                )
            ),
        ),
        (
            "proposal_missing_model_semantic_authority",
            lambda: SemanticDecisionProposal.model_validate(
                _replace_model(proposal, model_selected_every_semantic_field=False)
            ),
        ),
        (
            "commit_claims_compiler_semantic_selection",
            lambda: DecisionCommitCompilation.model_validate(
                _replace_model(
                    commit,
                    compiler_selected_tool_node_operator_or_operand=True,
                )
            ),
        ),
    )
    rows = tuple(_expect_rejection(name, function) for name, function in cases)
    values = {"mutation_results": rows}
    provisional = DestructivePreflightAudit.model_construct(audit_id="pending", **values)
    return DestructivePreflightAudit(
        audit_id=destructive_preflight_audit_id(provisional),
        **values,
    )


def _assert_equal(actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError("destructive equality control rejected")


def _assert_no_exact_history_value(value: BoundedFailureSummary) -> None:
    if _contains_forbidden_history_value(value.argument_shape):
        raise ValueError("failure-history exact value rejected")


def _unavailable_error_code(environment: AgentToolEnvironmentManifest) -> str:
    _, failure = resolve_model_selectable_tool_or_typed_failure(
        environment,
        AgentToolCall(call_index=1, tool_id="unknown", arguments={}),
    )
    if failure is None or failure.error_code is None:
        raise ValueError("shared availability gate did not return a typed failure")
    return failure.error_code


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
) -> ActionConstructibilityPreflightReport:
    predecessor_report, predecessor_replay, _ = _load_predecessor(package_root)
    replay = _build_source_replay(package_root, implementation_root, predecessor_replay)
    static = load_static_inputs(package_root)
    raws, providers = _load_execution(package_root)
    historical = _build_historical_interface(static, raws, providers)
    taxonomy = _build_failure_taxonomy(raws, providers)
    verifier_contract = make_authority_preserving_replay_v3_contract(static.replay_contract)
    verifier_audit = _build_verifier_audit(static, raws, verifier_contract)
    protocol = _build_protocol()
    (
        fixture,
        initial_state,
        operation_state,
        terminal_state,
        operation_proposal,
        operation_commit,
    ) = _build_action_fixture(static, protocol)
    final_rescue = _build_final_rescue_audit(static, protocol, raws, providers)
    destructive = _build_destructive_audit(
        initial_state,
        operation_state,
        terminal_state,
        operation_proposal,
        operation_commit,
        verifier_contract,
        static.environments[0],
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("action_constructibility_fixture_audit.json", fixture),
        ("action_constructibility_protocol.json", protocol),
        ("destructive_preflight_audit.json", destructive),
        ("failure_taxonomy_audit.json", taxonomy),
        ("final_rescue_semantic_audit.json", final_rescue),
        ("historical_action_interface_audit.json", historical),
        ("source_replay_audit.json", replay),
        ("verifier_v3_contract.json", verifier_contract),
        ("verifier_v3_replay_audit.json", verifier_audit),
    )
    for name, value in outputs:
        _write_json(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "predecessor_report_id": predecessor_report.report_id,
        "source_replay_audit_id": replay.audit_id,
        "historical_action_interface_audit_id": historical.audit_id,
        "failure_taxonomy_audit_id": taxonomy.audit_id,
        "verifier_v3_contract_id": verifier_contract.contract_id,
        "verifier_v3_replay_audit_id": verifier_audit.audit_id,
        "action_constructibility_protocol_id": protocol.protocol_id,
        "action_constructibility_fixture_audit_id": fixture.audit_id,
        "final_rescue_semantic_audit_id": final_rescue.audit_id,
        "destructive_preflight_audit_id": destructive.audit_id,
        "detail_files": details,
    }
    provisional = ActionConstructibilityPreflightReport.model_construct(
        report_id="pending",
        **values,
    )
    report = ActionConstructibilityPreflightReport(
        report_id=action_constructibility_preflight_report_id(provisional),
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
