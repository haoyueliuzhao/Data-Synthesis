from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.public_operation import (
    OperationalExecutableTaskPackage,
    OperationalExecutableVerifierBinding,
    PublicOperationContractView,
    PublicOperationExecutionContract,
    PublicOperationInput,
    PublicOperationNode,
    PublicOperationNodeBinding,
    PublicOperationRuntimeProjection,
    PublicStopReadinessContract,
    operational_executable_task_package_id,
    operational_executable_verifier_binding_id,
    public_operation_contract_view_id,
    public_operation_execution_contract_id,
    public_operation_runtime_projection_id,
    public_stop_readiness_contract_id,
    public_stop_readiness_view,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_public_operation_builder as operation_builder,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    _harden_environment,
    _harden_record,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    VERIFIER_QUALIFICATION_DIR,
    _make_compact_prompt_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    IntendedTaskUse,
    TargetMechanism,
    _base_draft,
    _TaskDraft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    TARGET_MECHANISMS,
    OperationalTaskRecord,
    PathStrategy,
    operational_task_record_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    _execute_observation,
    _runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    _bind_verifier_v2,
    _load_and_replay_verifier_qualification,
    _task_replay_binding,
    _verifier_bound_environment,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_abi,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseGrammar,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CANONICAL_ACTION_VERSION,
    DecisionKind,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
    prompt_only_reference_proposal,
    render_semantic_action_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseGrammar,
    independently_enumerate_visible_actions,
    parse_prompt_only_reference_payload,
    validate_candidate_space_completeness,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionProjection,
)
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_130_role_kernel_scalability_design_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_130_role_kernel_scalability_design_v1_20260824"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_role_kernel_scalability_design.py"
)
PREDECESSOR_OUTPUT_NAMES: Final = (
    "capability_source_population.json",
    "destructive_audit.json",
    "fresh_source_sampling_frame.json",
    "historical_exposure_exclusion_audit.json",
    "kernel_compatibility_audit.json",
    "prospective_transition_contract.json",
    "reachability_source_population.json",
    "report.json",
    "role_source_selection_audit.json",
    "source_replay_audit.json",
)
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_role_kernel_compatibility_preflight_report:"
    "c7195e4ba2194a136b8d7a8c27b1148d909d1b8eb76e1214a366f696c4e66f00"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "4d12e4ce8a7d8856a041e8cf37570ac94162b6a9fe508c112fbf08462e81de90"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_role_kernel_transition:"
    "c889aaaaa31fb388ab54a2207baa2cb5e3bd0302b8510f5b8f119e09b118de55"
)
EXPECTED_SELECTION_AUDIT_ID: Final = (
    "finance_v26_role_source_selection_audit:"
    "c85191ff67118440ecf67d112406f44eee33e64b4e34d77bec88c22b72cfc9a9"
)
EXPECTED_CAPABILITY_POPULATION_ID: Final = (
    "finance_v26_fresh_role_source_population:"
    "1e22847979b0927e1f772ab8b945dc4e57c2e0dc3b95f0673b1d1543470975e3"
)
EXPECTED_REACHABILITY_POPULATION_ID: Final = (
    "finance_v26_fresh_role_source_population:"
    "cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99"
)
EXPECTED_CONTEXT_COMPATIBILITY_AUDIT_ID: Final = (
    "finance_v26_kernel_compatibility_audit:"
    "df94020f8c68e83ef25aa2f24c76f8b807b0cd9f5d2e309e4db695c9ae0bfd92"
)
EXPECTED_ENGINEERING_KERNEL_FREEZE_ID: Final = predecessor.EXPECTED_KERNEL_FREEZE_ID
EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID: Final = (
    predecessor.EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID
)
ACTION_GRAMMAR_PATH: Final = predecessor.ACTION_GRAMMAR_PATH
FINAL_GRAMMAR_PATH: Final = predecessor.FINAL_GRAMMAR_PATH
COMPLETION_REQUEST_BOUND: Final = predecessor.COMPLETION_REQUEST_BOUND
PROVIDER_ACCOUNTING_MARGIN: Final = predecessor.PROVIDER_ACCOUNTING_MARGIN
FROZEN_PROMPT_CEILING: Final = predecessor.PROMPT_CEILING_BYTES
FROZEN_PRIMARY_REQUEST_LIMIT: Final = predecessor.MAXIMUM_PRIMARY_REQUESTS
FROZEN_PROVIDER_CALL_LIMIT: Final = predecessor.MAXIMUM_PROVIDER_CALLS_WITH_RECOVERY
FROZEN_ROLLOUT_BOUND: Final = predecessor.ROLLOUT_BOUND
MINIMUM_HEADROOM: Final = predecessor.MINIMUM_HEADROOM
RESOURCE_QUANTUM: Final = 20_000
COMPACT_PROMPT_PROTOCOL: Final = "prospective_role_scalable_semantic_action_prompt.v1"
NEXT_STAGE: Final = (
    "fresh_role_scalable_kernel_taskpackage_contract_manifest_and_runner_preflight_only"
)

Role: TypeAlias = Literal["capability", "reachability"]
Tier: TypeAlias = Literal["easy_control", "frontier", "hard_control"]
ProjectionLabel = Literal["S0_capacity_only", "S1_lossless_compact"]
FailureDimension = Literal[
    "prompt_ceiling",
    "primary_request_limit",
    "provider_call_limit",
    "rollout_bound",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    provenance: Literal["transitive_predecessor", "predecessor_output", "implementation"]


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    transitive_entry_count: int = Field(ge=1)
    predecessor_output_count: Literal[10] = 10
    implementation_count: Literal[1] = 1
    replayed_file_count: int = Field(ge=12)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=12)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_role_scalability_source_replay.v1"] = (
        "finance_v26_role_scalability_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        if tuple(item.relative_path for item in self.entries) != tuple(
            sorted(item.relative_path for item in self.entries)
        ):
            raise ValueError("v26.130 source replay entries are not canonical")
        if len({item.relative_path for item in self.entries}) != len(self.entries):
            raise ValueError("v26.130 source replay paths are duplicated")
        counts = Counter(item.provenance for item in self.entries)
        if (
            counts["transitive_predecessor"] != self.transitive_entry_count
            or counts["predecessor_output"] != self.predecessor_output_count
            or counts["implementation"] != self.implementation_count
            or len(self.entries) != self.replayed_file_count
        ):
            raise ValueError("v26.130 source replay counts changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_role_scalability_source_replay:"
        ):
            raise ValueError("v26.130 source replay identity changed")
        return self


class FrozenPopulationReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_role_source_selection_audit_id: str = EXPECTED_SELECTION_AUDIT_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    reachability_population_id: str = EXPECTED_REACHABILITY_POPULATION_ID
    predecessor_context_compatibility_audit_id: str = EXPECTED_CONTEXT_COMPATIBILITY_AUDIT_ID
    capability_task_count: Literal[12] = 12
    reachability_task_count: Literal[12] = 12
    total_source_task_count: Literal[24] = 24
    tasks_per_role_mechanism_tier: Literal[1] = 1
    eight_channel_prior_overlap_count: Literal[0] = 0
    eight_channel_cross_role_overlap_count: Literal[0] = 0
    posthoc_task_deletion_count: Literal[0] = 0
    posthoc_task_substitution_count: Literal[0] = 0
    tier_change_count: Literal[0] = 0
    source_population_regenerated: Literal[False] = False
    model_outcomes_loaded_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_frozen_role_population_replay.v1"] = (
        "finance_v26_frozen_role_population_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenPopulationReplayAudit:
        if (
            self.capability_population_id != EXPECTED_CAPABILITY_POPULATION_ID
            or self.reachability_population_id != EXPECTED_REACHABILITY_POPULATION_ID
            or self.predecessor_role_source_selection_audit_id != EXPECTED_SELECTION_AUDIT_ID
            or self.predecessor_context_compatibility_audit_id
            != EXPECTED_CONTEXT_COMPATIBILITY_AUDIT_ID
        ):
            raise ValueError("v26.130 frozen Population binding changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_frozen_role_population_replay:"
        ):
            raise ValueError("v26.130 frozen Population replay identity changed")
        return self


class StateComplexityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    logical_index: int = Field(ge=0)
    candidate_count: int = Field(ge=1)
    s0_state_projection_utf8_bytes: int = Field(ge=1)
    s0_candidate_projection_utf8_bytes: int = Field(ge=1)
    s0_primary_prompt_utf8_bytes: int = Field(ge=1)
    s0_abi_rescue_prompt_utf8_bytes: int = Field(ge=1)
    s0_semantic_recovery_prompt_utf8_bytes: int = Field(ge=1)
    s1_state_projection_utf8_bytes: int = Field(ge=1)
    s1_candidate_projection_utf8_bytes: int = Field(ge=1)
    s1_primary_prompt_utf8_bytes: int = Field(ge=1)
    s1_abi_rescue_prompt_utf8_bytes: int = Field(ge=1)
    s1_semantic_recovery_prompt_utf8_bytes: int = Field(ge=1)
    exact_state_reconstruction_passed: Literal[True] = True
    exact_candidate_set_reconstruction_passed: Literal[True] = True
    exact_candidate_presentation_order_passed: Literal[True] = True
    exact_reference_proposal_passed: Literal[True] = True
    exact_stage_two_commit_passed: Literal[True] = True
    private_reasoning_fields: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> StateComplexityRow:
        if (
            self.s1_primary_prompt_utf8_bytes >= self.s0_primary_prompt_utf8_bytes
            or self.s1_abi_rescue_prompt_utf8_bytes >= self.s0_abi_rescue_prompt_utf8_bytes
            or self.s1_semantic_recovery_prompt_utf8_bytes
            >= self.s0_semantic_recovery_prompt_utf8_bytes
        ):
            raise ValueError("v26.130 compact Prompt is not strictly smaller")
        if self.row_id != _identity(
            self, "row_id", "finance_v26_role_scalability_state_complexity:"
        ):
            raise ValueError("v26.130 state-complexity identity changed")
        return self


class PathComplexityRow(FrozenModel):
    path_id: str = Field(min_length=1)
    capability_or_reachability_population_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    diagnostic_task_package_id: str = Field(min_length=1)
    diagnostic_environment_manifest_id: str = Field(min_length=1)
    role: Role
    mechanism_id: TargetMechanism
    tier: Tier
    path_strategy_id: PathStrategy
    source_program_node_count: int = Field(ge=1)
    source_public_evidence_count: int = Field(ge=1)
    source_target_evidence_count: int = Field(ge=1)
    action_state_count: int = Field(ge=1)
    public_tool_call_count: int = Field(ge=1)
    stage_two_commit_count: int = Field(ge=1)
    primary_request_count: int = Field(ge=2)
    maximum_provider_calls_with_abi_and_semantic_recovery: int = Field(ge=4)
    maximum_provider_invocations_with_transport_replacement: int = Field(ge=5)
    maximum_candidate_count: int = Field(ge=1)
    maximum_s0_candidate_projection_utf8_bytes: int = Field(ge=1)
    maximum_s1_candidate_projection_utf8_bytes: int = Field(ge=1)
    maximum_s0_prompt_utf8_bytes: int = Field(ge=1)
    maximum_s1_prompt_utf8_bytes: int = Field(ge=1)
    s0_static_complete_path_upper_bound_tokens: int = Field(gt=0)
    s1_static_complete_path_upper_bound_tokens: int = Field(gt=0)
    frozen_kernel_failure_dimensions: tuple[FailureDimension, ...]
    first_frozen_kernel_failure_dimension: FailureDimension | None
    frozen_kernel_compatible: bool
    states: tuple[StateComplexityRow, ...] = Field(min_length=1)
    candidate_authority_passed: Literal[True] = True
    stage_two_authority_passed: Literal[True] = True
    program_closed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    terminal_verification_ready: Literal[True] = True
    final_commit_reached: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> PathComplexityRow:
        if (
            self.action_state_count != len(self.states)
            or self.stage_two_commit_count != self.action_state_count
            or self.primary_request_count != self.action_state_count + 1
            or self.maximum_provider_calls_with_abi_and_semantic_recovery
            != self.primary_request_count + 2
            or self.maximum_provider_invocations_with_transport_replacement
            != self.maximum_provider_calls_with_abi_and_semantic_recovery + 1
        ):
            raise ValueError("v26.130 Path request arithmetic changed")
        expected_dimensions: list[FailureDimension] = []
        if self.maximum_s0_prompt_utf8_bytes > FROZEN_PROMPT_CEILING:
            expected_dimensions.append("prompt_ceiling")
        if self.primary_request_count > FROZEN_PRIMARY_REQUEST_LIMIT:
            expected_dimensions.append("primary_request_limit")
        if self.maximum_provider_calls_with_abi_and_semantic_recovery > FROZEN_PROVIDER_CALL_LIMIT:
            expected_dimensions.append("provider_call_limit")
        if (
            self.s0_static_complete_path_upper_bound_tokens >= FROZEN_ROLLOUT_BOUND
            or FROZEN_ROLLOUT_BOUND - self.s0_static_complete_path_upper_bound_tokens
            < MINIMUM_HEADROOM
        ):
            expected_dimensions.append("rollout_bound")
        expected = tuple(expected_dimensions)
        if (
            self.frozen_kernel_failure_dimensions != expected
            or self.first_frozen_kernel_failure_dimension != (expected[0] if expected else None)
            or self.frozen_kernel_compatible != (not expected)
            or self.maximum_s1_prompt_utf8_bytes >= self.maximum_s0_prompt_utf8_bytes
            or self.s1_static_complete_path_upper_bound_tokens
            >= self.s0_static_complete_path_upper_bound_tokens
        ):
            raise ValueError("v26.130 Path complexity classification changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_role_support_complexity_path:"):
            raise ValueError("v26.130 Path-complexity identity changed")
        return self


class CandidateDistributionRow(FrozenModel):
    candidate_count: int = Field(ge=1)
    state_count: int = Field(ge=1)


class RoleSupportComplexityCensus(FrozenModel):
    census_id: str = Field(min_length=1)
    frozen_population_replay_audit_id: str = Field(min_length=1)
    engineering_kernel_freeze_id: str = EXPECTED_ENGINEERING_KERNEL_FREEZE_ID
    role_source_task_count: Literal[24] = 24
    capability_source_task_count: Literal[12] = 12
    reachability_source_task_count: Literal[12] = 12
    diagnostic_path_count: Literal[48] = 48
    capability_path_count: Literal[12] = 12
    reachability_path_count: Literal[36] = 36
    evaluated_mechanism_count: Literal[4] = 4
    evaluated_mechanisms: tuple[TargetMechanism, ...] = TARGET_MECHANISMS
    easy_path_count: Literal[16] = 16
    frontier_path_count: Literal[16] = 16
    hard_path_count: Literal[16] = 16
    frozen_kernel_compatible_path_count: int = Field(ge=0)
    frozen_kernel_incompatible_path_count: int = Field(ge=1)
    prompt_ceiling_failure_count: int = Field(ge=0)
    primary_request_limit_failure_count: int = Field(ge=0)
    provider_call_limit_failure_count: int = Field(ge=0)
    rollout_bound_failure_count: int = Field(ge=0)
    maximum_candidate_count: int = Field(ge=1)
    maximum_s0_candidate_projection_utf8_bytes: int = Field(ge=1)
    maximum_s1_candidate_projection_utf8_bytes: int = Field(ge=1)
    maximum_s0_prompt_utf8_bytes: int = Field(ge=1)
    maximum_s1_prompt_utf8_bytes: int = Field(ge=1)
    maximum_primary_request_count: int = Field(ge=1)
    maximum_provider_call_count: int = Field(ge=1)
    maximum_s0_static_path_upper_bound_tokens: int = Field(gt=0)
    maximum_s1_static_path_upper_bound_tokens: int = Field(gt=0)
    candidate_distribution: tuple[CandidateDistributionRow, ...] = Field(min_length=1)
    paths: tuple[PathComplexityRow, ...] = Field(min_length=48, max_length=48)
    v26_129_context_path_reproduction_passed: Literal[True] = True
    full_mechanism_fail_fast_disabled: Literal[True] = True
    role_task_package_count: Literal[0] = 0
    role_manifest_count: Literal[0] = 0
    role_job_count: Literal[0] = 0
    role_runner_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["full_role_support_complexity_measured"] = (
        "full_role_support_complexity_measured"
    )
    schema_version: Literal["finance_v26_role_support_complexity_census.v1"] = (
        "finance_v26_role_support_complexity_census.v1"
    )

    @model_validator(mode="after")
    def validate_census(self) -> RoleSupportComplexityCensus:
        rows = self.paths
        if (
            len({item.path_id for item in rows}) != self.diagnostic_path_count
            or sum(item.role == "capability" for item in rows) != self.capability_path_count
            or sum(item.role == "reachability" for item in rows) != self.reachability_path_count
            or sum(item.tier == "easy_control" for item in rows) != self.easy_path_count
            or sum(item.tier == "frontier" for item in rows) != self.frontier_path_count
            or sum(item.tier == "hard_control" for item in rows) != self.hard_path_count
            or {item.mechanism_id for item in rows} != set(self.evaluated_mechanisms)
            or any(
                sum(item.mechanism_id == mechanism for item in rows) != 12
                for mechanism in self.evaluated_mechanisms
            )
            or self.frozen_kernel_compatible_path_count
            != sum(item.frozen_kernel_compatible for item in rows)
            or self.frozen_kernel_incompatible_path_count
            != sum(not item.frozen_kernel_compatible for item in rows)
            or self.prompt_ceiling_failure_count
            != sum("prompt_ceiling" in item.frozen_kernel_failure_dimensions for item in rows)
            or self.primary_request_limit_failure_count
            != sum(
                "primary_request_limit" in item.frozen_kernel_failure_dimensions for item in rows
            )
            or self.provider_call_limit_failure_count
            != sum("provider_call_limit" in item.frozen_kernel_failure_dimensions for item in rows)
            or self.rollout_bound_failure_count
            != sum("rollout_bound" in item.frozen_kernel_failure_dimensions for item in rows)
            or self.maximum_candidate_count != max(item.maximum_candidate_count for item in rows)
            or self.maximum_s0_candidate_projection_utf8_bytes
            != max(item.maximum_s0_candidate_projection_utf8_bytes for item in rows)
            or self.maximum_s1_candidate_projection_utf8_bytes
            != max(item.maximum_s1_candidate_projection_utf8_bytes for item in rows)
            or self.maximum_s0_prompt_utf8_bytes
            != max(item.maximum_s0_prompt_utf8_bytes for item in rows)
            or self.maximum_s1_prompt_utf8_bytes
            != max(item.maximum_s1_prompt_utf8_bytes for item in rows)
            or self.maximum_primary_request_count
            != max(item.primary_request_count for item in rows)
            or self.maximum_provider_call_count
            != max(item.maximum_provider_calls_with_abi_and_semantic_recovery for item in rows)
            or self.maximum_s0_static_path_upper_bound_tokens
            != max(item.s0_static_complete_path_upper_bound_tokens for item in rows)
            or self.maximum_s1_static_path_upper_bound_tokens
            != max(item.s1_static_complete_path_upper_bound_tokens for item in rows)
        ):
            raise ValueError("v26.130 complexity Census aggregate changed")
        if self.census_id != _identity(
            self, "census_id", "finance_v26_role_support_complexity_census:"
        ):
            raise ValueError("v26.130 complexity Census identity changed")
        return self


class CompactProjectionProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    protocol_version: str = COMPACT_PROMPT_PROTOCOL
    source_census_id: str = Field(min_length=1)
    state_control_count: int = Field(ge=1)
    primary_prompt_control_count: int = Field(ge=1)
    abi_rescue_prompt_control_count: int = Field(ge=1)
    semantic_recovery_prompt_control_count: int = Field(ge=1)
    exact_state_reconstruction_count: int = Field(ge=1)
    exact_candidate_set_reconstruction_count: int = Field(ge=1)
    exact_candidate_order_reconstruction_count: int = Field(ge=1)
    exact_reference_proposal_count: int = Field(ge=1)
    exact_stage_two_commit_count: int = Field(ge=1)
    full_candidate_authority_preserved: Literal[True] = True
    canonical_action_ids_unchanged: Literal[True] = True
    candidate_deletion_count: Literal[0] = 0
    candidate_substitution_count: Literal[0] = 0
    stage_two_semantic_choice_or_repair: Literal[False] = False
    stage_two_provider_calls: Literal[0] = 0
    fixed_state_invariants_host_bound: Literal[True] = True
    typed_columnar_tables_reversible: Literal[True] = True
    private_reasoning_content_or_hash_persisted: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_compact_projection_protocol.v1"] = (
        "finance_v26_compact_projection_protocol.v1"
    )

    @model_validator(mode="after")
    def validate_protocol(self) -> CompactProjectionProtocol:
        expected = self.state_control_count
        if any(
            value != expected
            for value in (
                self.primary_prompt_control_count,
                self.abi_rescue_prompt_control_count,
                self.semantic_recovery_prompt_control_count,
                self.exact_state_reconstruction_count,
                self.exact_candidate_set_reconstruction_count,
                self.exact_candidate_order_reconstruction_count,
                self.exact_reference_proposal_count,
                self.exact_stage_two_commit_count,
            )
        ):
            raise ValueError("v26.130 compact projection control denominator changed")
        if self.protocol_id != _identity(
            self, "protocol_id", "finance_v26_compact_projection_protocol:"
        ):
            raise ValueError("v26.130 compact projection identity changed")
        return self


class ScalabilityCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    label: ProjectionLabel
    source_census_id: str = Field(min_length=1)
    compact_projection_protocol_id: str | None
    semantic_action_protocol_unchanged: Literal[True] = True
    semantic_action_response_grammar_unchanged: Literal[True] = True
    exact_final_response_grammar_unchanged: Literal[True] = True
    candidate_set_unchanged: Literal[True] = True
    canonical_action_ids_unchanged: Literal[True] = True
    interaction_stage_count_unchanged: Literal[True] = True
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND
    prompt_ceiling_bytes: int = Field(ge=FROZEN_PROMPT_CEILING)
    maximum_primary_requests: int = Field(gt=FROZEN_PRIMARY_REQUEST_LIMIT)
    maximum_provider_calls_with_recovery: int = Field(gt=FROZEN_PROVIDER_CALL_LIMIT)
    maximum_provider_invocations_with_transport_replacement: int = Field(ge=1)
    rollout_upper_bound_tokens: int = Field(gt=FROZEN_ROLLOUT_BOUND)
    measured_maximum_prompt_utf8_bytes: int = Field(ge=1)
    measured_maximum_primary_requests: int = Field(ge=1)
    measured_maximum_provider_calls: int = Field(ge=1)
    measured_maximum_static_path_upper_bound_tokens: int = Field(gt=0)
    minimum_static_headroom_tokens: int = Field(ge=MINIMUM_HEADROOM)
    qualified_path_count: Literal[48] = 48
    failed_path_count: Literal[0] = 0
    resource_values_selected_without_model_outcomes: Literal[True] = True
    role_task_package_count: Literal[0] = 0
    role_job_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["statically_qualified"] = "statically_qualified"
    schema_version: Literal["finance_v26_scalability_candidate.v1"] = (
        "finance_v26_scalability_candidate.v1"
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> ScalabilityCandidate:
        if (
            (self.label == "S0_capacity_only") != (self.compact_projection_protocol_id is None)
            or self.maximum_provider_invocations_with_transport_replacement
            != self.maximum_provider_calls_with_recovery + 1
            or self.measured_maximum_prompt_utf8_bytes >= self.prompt_ceiling_bytes
            or self.measured_maximum_primary_requests > self.maximum_primary_requests
            or self.measured_maximum_provider_calls > self.maximum_provider_calls_with_recovery
            or self.measured_maximum_static_path_upper_bound_tokens
            + self.minimum_static_headroom_tokens
            > self.rollout_upper_bound_tokens
        ):
            raise ValueError("v26.130 scalability Candidate resource qualification changed")
        if self.candidate_id != _identity(
            self, "candidate_id", "finance_v26_role_scalability_candidate:"
        ):
            raise ValueError("v26.130 scalability Candidate identity changed")
        return self


class ScalabilitySelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_census_id: str = Field(min_length=1)
    s0_candidate_id: str = Field(min_length=1)
    s1_candidate_id: str = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1)
    selected_label: Literal["S1_lossless_compact"] = "S1_lossless_compact"
    preregistered_rule_order: tuple[str, ...] = (
        "all_frozen_role_paths_qualified",
        "candidate_authority_and_reversible_commit_preserved",
        "model_outcomes_not_used",
        "resource_vector_pareto_dominance",
        "structural_simplicity_tiebreak_only",
    )
    s0_all_paths_qualified: Literal[True] = True
    s1_all_paths_qualified: Literal[True] = True
    s1_semantic_equivalence_passed: Literal[True] = True
    s1_request_count_no_worse: Literal[True] = True
    s1_provider_call_count_no_worse: Literal[True] = True
    s1_prompt_ceiling_strictly_lower: Literal[True] = True
    s1_rollout_bound_strictly_lower: Literal[True] = True
    model_outcomes_loaded_for_selection: Literal[False] = False
    posthoc_candidate_added_count: Literal[0] = 0
    status: Literal["S1_selected_by_static_pareto_rule"] = "S1_selected_by_static_pareto_rule"
    schema_version: Literal["finance_v26_scalability_selection.v1"] = (
        "finance_v26_scalability_selection.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ScalabilitySelectionAudit:
        if self.selected_candidate_id != self.s1_candidate_id:
            raise ValueError("v26.130 selected Candidate is not S1")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_scalability_selection:"):
            raise ValueError("v26.130 scalability selection identity changed")
        return self


class RoleSupportScalabilityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_census_id: str = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1)
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    reachability_population_id: str = EXPECTED_REACHABILITY_POPULATION_ID
    support_task_count: Literal[24] = 24
    support_path_count: Literal[48] = 48
    semantics_preserved_path_count: Literal[48] = 48
    authority_preserved_path_count: Literal[48] = 48
    prompt_bound_passed_path_count: Literal[48] = 48
    request_bound_passed_path_count: Literal[48] = 48
    provider_call_bound_passed_path_count: Literal[48] = 48
    rollout_bound_passed_path_count: Literal[48] = 48
    support_admission_condition_only: Literal[True] = True
    energy_reward_or_contribution_term_added: Literal[False] = False
    capability_or_reachability_measured: Literal[False] = False
    state_mapping_or_vtdo_update_performed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["role_support_scalability_statically_closed"] = (
        "role_support_scalability_statically_closed"
    )
    schema_version: Literal["finance_v26_role_support_scalability_contract.v1"] = (
        "finance_v26_role_support_scalability_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleSupportScalabilityContract:
        if (
            self.capability_population_id != EXPECTED_CAPABILITY_POPULATION_ID
            or self.reachability_population_id != EXPECTED_REACHABILITY_POPULATION_ID
        ):
            raise ValueError("v26.130 role-support Population binding changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_support_scalability_contract:"
        ):
            raise ValueError("v26.130 role-support scalability identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    role_jobs_materialized_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[18] = 18
    rejection_count: Literal[18] = 18
    mutations: tuple[MutationResult, ...] = Field(min_length=18, max_length=18)
    provider_calls: Literal[0] = 0
    role_jobs_materialized: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_role_scalability_destructive.v1"] = (
        "finance_v26_role_scalability_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.130 destructive mutation names changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_role_scalability_destructive:"
        ):
            raise ValueError("v26.130 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    scalability_selection_audit_id: str = Field(min_length=1)
    selected_scalability_candidate_id: str = Field(min_length=1)
    role_support_scalability_contract_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_frozen_role_populations_must_be_preserved: Literal[True] = True
    fresh_role_scalable_kernel_identity_required: Literal[True] = True
    fresh_taskpackage_contract_manifest_job_and_runner_identities_required: Literal[True] = True
    credential_free_runner_preflight_required_before_provider_call: Literal[True] = True
    kernel_and_role_identity_chain_preflight_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    posthoc_task_deletion_substitution_or_tier_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    additional_scalability_candidate_authorized: Literal[False] = False
    model_outcome_based_selection_authorized: Literal[False] = False
    status: Literal["role_scalability_design_closed"] = "role_scalability_design_closed"
    schema_version: Literal["finance_v26_role_scalability_transition.v1"] = (
        "finance_v26_role_scalability_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalability_transition:"
        ):
            raise ValueError("v26.130 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RoleKernelScalabilityDesignReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    frozen_population_replay_audit_id: str = Field(min_length=1)
    complexity_census_id: str = Field(min_length=1)
    compact_projection_protocol_id: str = Field(min_length=1)
    s0_candidate_id: str = Field(min_length=1)
    s1_candidate_id: str = Field(min_length=1)
    scalability_selection_audit_id: str = Field(min_length=1)
    role_support_scalability_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=10, max_length=10)
    frozen_role_source_task_count: Literal[24] = 24
    full_mechanism_path_count: Literal[48] = 48
    selected_scalability_candidate: Literal["S1_lossless_compact"] = "S1_lossless_compact"
    role_task_package_count: Literal[0] = 0
    role_contract_count: Literal[0] = 0
    role_manifest_count: Literal[0] = 0
    role_job_count: Literal[0] = 0
    role_runner_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["role_scalability_design_passed"] = "role_scalability_design_passed"
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_role_kernel_scalability_design_report.v1"] = (
        "finance_v26_role_kernel_scalability_design_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RoleKernelScalabilityDesignReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_role_kernel_scalability_design_report:"
        ):
            raise ValueError("v26.130 report identity changed")
        return self


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26.130 artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
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
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.130 cannot replay bound file: {relative_path}")


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
) -> SourceReplayAudit:
    predecessor_source = predecessor.SourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    predecessor_report = predecessor.RoleKernelCompatibilityPreflightReport.model_validate_json(
        (predecessor_dir / "report.json").read_text(encoding="utf-8")
    )
    predecessor_transition = predecessor.ProspectiveTransitionContract.model_validate_json(
        (predecessor_dir / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    if (
        predecessor_report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or _sha256(predecessor_dir / "report.json") != EXPECTED_PREDECESSOR_REPORT_SHA256
        or predecessor_report.source_replay_audit_id != predecessor_source.audit_id
        or predecessor_transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or predecessor_transition.next_permitted_stage
        != "frozen_role_population_kernel_scalability_design_only"
    ):
        raise ValueError("v26.130 predecessor identity chain changed")
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
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
            provenance="transitive_predecessor",
        )
    observed_names = tuple(
        sorted(path.name for path in predecessor_dir.iterdir() if path.is_file())
    )
    if observed_names != PREDECESSOR_OUTPUT_NAMES:
        raise ValueError("v26.130 predecessor output file set changed")
    detail_hashes = {item.relative_path: item.sha256 for item in predecessor_report.detail_files}
    if set(detail_hashes) != set(PREDECESSOR_OUTPUT_NAMES) - {"report.json"}:
        raise ValueError("v26.130 predecessor report detail-file set changed")
    for name in PREDECESSOR_OUTPUT_NAMES:
        path = predecessor_dir / name
        digest = _sha256(path)
        if name != "report.json" and detail_hashes[name] != digest:
            raise ValueError(f"v26.130 predecessor detail hash changed: {name}")
        relative = str(Path(PREDECESSOR_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            sha256=digest,
            byte_count=path.stat().st_size,
            provenance="predecessor_output",
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        sha256=_sha256(implementation_path),
        byte_count=implementation_path.stat().st_size,
        provenance="implementation",
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values = {
        "transitive_entry_count": len(predecessor_source.entries),
        "replayed_file_count": len(ordered),
        "entries": ordered,
    }
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_role_scalability_source_replay:",
        ),
        **values,
    )


class _FrozenInputs:
    def __init__(
        self,
        *,
        frame: CapabilitySensitiveFrontierPopulation,
        capability: predecessor.FreshRoleSourcePopulation,
        reachability: predecessor.FreshRoleSourcePopulation,
        selection: predecessor.RoleSourceSelectionAudit,
        context_compatibility: predecessor.KernelCompatibilityAudit,
    ) -> None:
        self.frame = frame
        self.capability = capability
        self.reachability = reachability
        self.selection = selection
        self.context_compatibility = context_compatibility
        self.tasks = {item.artifact_id: item for item in frame.tasks}


def _load_frozen_inputs(
    *,
    predecessor_dir: Path,
    source_replay: SourceReplayAudit,
) -> tuple[_FrozenInputs, FrozenPopulationReplayAudit]:
    frame = CapabilitySensitiveFrontierPopulation.model_validate_json(
        (predecessor_dir / "fresh_source_sampling_frame.json").read_text(encoding="utf-8")
    )
    capability = predecessor.FreshRoleSourcePopulation.model_validate_json(
        (predecessor_dir / "capability_source_population.json").read_text(encoding="utf-8")
    )
    reachability = predecessor.FreshRoleSourcePopulation.model_validate_json(
        (predecessor_dir / "reachability_source_population.json").read_text(encoding="utf-8")
    )
    selection = predecessor.RoleSourceSelectionAudit.model_validate_json(
        (predecessor_dir / "role_source_selection_audit.json").read_text(encoding="utf-8")
    )
    context = predecessor.KernelCompatibilityAudit.model_validate_json(
        (predecessor_dir / "kernel_compatibility_audit.json").read_text(encoding="utf-8")
    )
    if (
        capability.population_id != EXPECTED_CAPABILITY_POPULATION_ID
        or reachability.population_id != EXPECTED_REACHABILITY_POPULATION_ID
        or selection.audit_id != EXPECTED_SELECTION_AUDIT_ID
        or context.audit_id != EXPECTED_CONTEXT_COMPATIBILITY_AUDIT_ID
        or selection.capability_population_id != capability.population_id
        or selection.reachability_population_id != reachability.population_id
        or context.capability_population_id != capability.population_id
        or context.reachability_population_id != reachability.population_id
    ):
        raise ValueError("v26.130 frozen role Population identity chain changed")
    bindings = (*capability.tasks, *reachability.tasks)
    if len(bindings) != 24 or len({item.source_task_artifact_id for item in bindings}) != 24:
        raise ValueError("v26.130 frozen role source denominator changed")
    if any(
        item.source_task_artifact_id not in {task.artifact_id for task in frame.tasks}
        for item in bindings
    ):
        raise ValueError("v26.130 frozen role source is absent from the Sampling Frame")
    counts = Counter((item.role, item.mechanism_id, item.tier) for item in bindings)
    if set(counts.values()) != {1} or len(counts) != 24:
        raise ValueError("v26.130 role x mechanism x tier balance changed")
    values = {"source_replay_audit_id": source_replay.audit_id}
    provisional = FrozenPopulationReplayAudit.model_construct(audit_id="pending", **values)
    audit = FrozenPopulationReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_frozen_role_population_replay:",
        ),
        **values,
    )
    return (
        _FrozenInputs(
            frame=frame,
            capability=capability,
            reachability=reachability,
            selection=selection,
            context_compatibility=context,
        ),
        audit,
    )


def _target_evidence_ids(task: CapabilitySensitiveTaskArtifact) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                ref.ref_id
                for node in task.task.oracle.task_program.nodes
                for ref in node.input_refs
                if ref.kind == InputRefKind.EVIDENCE
            }
        )
    )


def _role_draft(
    task: CapabilitySensitiveTaskArtifact,
    *,
    role: Role,
    mechanism: TargetMechanism,
) -> _TaskDraft:
    intended_use: IntendedTaskUse = (
        "capability_measurement" if role == "capability" else "vtdo_multistate_candidate"
    )
    if mechanism != "semantic_reconciliation":
        return _base_draft(
            task,
            mechanism_id=mechanism,
            intended_use=intended_use,
        )
    base = _base_draft(
        task,
        mechanism_id="state_dependent_stopping",
        intended_use=intended_use,
    )
    evidence_by_id = {item.evidence_id: item for item in task.public_corpus.evidence}
    target_ids = _target_evidence_ids(task)
    targets = tuple(evidence_by_id[evidence_id] for evidence_id in target_ids)
    periods = tuple(str(item.temporal_context.label) for item in targets)
    if len(set(periods)) != len(periods):
        raise ValueError("v26.130 deep Reconciliation target periods are not unique")
    target_definitions = tuple(
        {
            "period": item.temporal_context.label,
            "predicate": item.predicate,
            "definition_id": item.definition.definition_id,
            "unit": getattr(item.payload, "unit", None),
            "currency": getattr(item.payload, "currency", None),
            "time_basis": item.temporal_context.basis,
            "frequency": item.temporal_context.frequency,
        }
        for item in targets
    )
    return replace(
        base,
        mechanism_id="semantic_reconciliation",
        instruction=(
            f"{task.task.public.instruction} Normalize every required public record against "
            "its registered metric, definition, unit, currency, period basis, and frequency. "
            "Every original Program node must consume emitted normalization or downstream "
            "Operation references rather than raw Evidence."
        ),
        mechanism_public_state={
            "target_definitions": target_definitions,
            "downstream_reference_required": True,
            "raw_evidence_bypass_invalid": True,
        },
        mechanism_private_state={
            "target_evidence_ids": target_ids,
            "raw_evidence_bypass_invalid": True,
        },
        target_program_evidence_ids=target_ids,
    )


def _deep_reconciliation_operation_nodes(
    draft: _TaskDraft,
    evidence_to_symbol: Mapping[str, str],
) -> tuple[tuple[PublicOperationNode, ...], tuple[PublicOperationNodeBinding, ...]]:
    evidence_by_id = {item.evidence_id: item for item in draft.public_corpus.evidence}
    target_specs = {
        str(item["period"]): dict(item)
        for item in cast(
            Sequence[Mapping[str, Any]],
            draft.mechanism_public_state["target_definitions"],
        )
    }
    target_ids = tuple(draft.target_program_evidence_ids)
    target_periods = {
        str(evidence_by_id[evidence_id].temporal_context.label) for evidence_id in target_ids
    }
    if target_periods != set(target_specs):
        raise ValueError("v26.130 deep Reconciliation target definition coverage changed")
    normalization_nodes: list[PublicOperationNode] = []
    bindings: list[PublicOperationNodeBinding] = []
    evidence_to_normalized_symbol: dict[str, str] = {}
    evidence_to_normalization_node: dict[str, str] = {}
    for index, evidence_id in enumerate(target_ids, start=1):
        evidence = evidence_by_id[evidence_id]
        period = str(evidence.temporal_context.label)
        target = target_specs[period]
        node_id = f"operation_stage_{index:02d}"
        output_symbol = f"normalized_reference_{index:02d}"
        evidence_to_normalized_symbol[evidence_id] = output_symbol
        evidence_to_normalization_node[evidence_id] = node_id
        normalization_nodes.append(
            PublicOperationNode(
                node_id=node_id,
                node_kind="normalization",
                semantic_role=f"required_definition_normalization_{index:02d}",
                tool_id="normalize_metric_unit_period",
                inputs=(PublicOperationInput(source_symbol=evidence_to_symbol[evidence_id]),),
                output_symbol=output_symbol,
                operator_choice_mode="not_applicable",
                normalization_target={
                    key: target[key]
                    for key in (
                        "predicate",
                        "definition_id",
                        "unit",
                        "currency",
                        "time_basis",
                        "frequency",
                    )
                },
            )
        )
        bindings.append(PublicOperationNodeBinding(public_node_id=node_id))
    source_nodes = tuple(draft.program.nodes)
    offset = len(normalization_nodes)
    public_ids = {
        node.node_id: f"operation_stage_{offset + index:02d}"
        for index, node in enumerate(source_nodes, start=1)
    }
    output_symbols = {
        node.node_id: (
            "terminal_operation_result"
            if node.node_id == draft.program.output_node_id
            else f"intermediate_result_{index:02d}"
        )
        for index, node in enumerate(source_nodes, start=1)
    }
    calculation_nodes: list[PublicOperationNode] = []
    for index, node in enumerate(source_nodes, start=1):
        inputs: list[PublicOperationInput] = []
        dependencies = {public_ids[value] for value in node.dependencies}
        for ref in node.input_refs:
            selector: str | None
            if ref.kind == InputRefKind.EVIDENCE:
                source_symbol = evidence_to_normalized_symbol[ref.ref_id]
                dependencies.add(evidence_to_normalization_node[ref.ref_id])
                selector = "normalized_inputs.target"
            else:
                source_symbol = output_symbols[ref.ref_id]
                dependencies.add(public_ids[ref.ref_id])
                selector = ref.selector
            inputs.append(PublicOperationInput(source_symbol=source_symbol, selector=selector))
        is_terminal = node.node_id == draft.program.output_node_id
        calculation_nodes.append(
            PublicOperationNode(
                node_id=public_ids[node.node_id],
                node_kind="calculation",
                semantic_role=(
                    "terminal_answer_operation"
                    if is_terminal
                    else f"required_reconciled_calculation_stage_{index:02d}"
                ),
                tool_id="calculator",
                dependency_node_ids=tuple(sorted(dependencies)),
                inputs=tuple(inputs),
                output_symbol=output_symbols[node.node_id],
                allowed_operator_ids=(node.operator_id,),
                operator_choice_mode="fixed_semantics",
                parameters=dict(node.parameters),
                terminal=is_terminal,
            )
        )
        bindings.append(
            PublicOperationNodeBinding(
                public_node_id=public_ids[node.node_id],
                source_program_node_id=node.node_id,
                expected_operator_id=node.operator_id,
            )
        )
    return (
        tuple(sorted((*normalization_nodes, *calculation_nodes), key=lambda item: item.node_id)),
        tuple(sorted(bindings, key=lambda item: item.public_node_id)),
    )


def _deep_reconciliation_operation_contracts(
    draft: _TaskDraft,
    semantic_source_id: str,
) -> tuple[
    PublicOperationExecutionContract,
    PublicStopReadinessContract,
    PublicOperationRuntimeProjection,
    tuple[PublicOperationNodeBinding, ...],
]:
    variables, evidence_to_symbol = operation_builder._public_variables(draft)  # noqa: SLF001
    nodes, bindings = _deep_reconciliation_operation_nodes(draft, evidence_to_symbol)
    terminal_id = next(item.node_id for item in nodes if item.terminal)
    view_values = {
        "variables": variables,
        "nodes": nodes,
        "terminal_node_id": terminal_id,
    }
    view_provisional = PublicOperationContractView.model_construct(view_id="pending", **view_values)
    view = PublicOperationContractView(
        view_id=public_operation_contract_view_id(view_provisional),
        **view_values,
    )
    operation_values = {
        "semantic_source_id": semantic_source_id,
        "source_program_dag_hash": draft.program.program_hash,
        "source_verifier_dag_hash": operation_builder._source_verifier_dag_hash(  # noqa: SLF001
            draft.program
        ),
        "public_view": view,
        "public_view_hash": canonical_hash(view, prefix="public_operation_contract_view:"),
    }
    operation_provisional = PublicOperationExecutionContract.model_construct(
        contract_id="pending", **operation_values
    )
    operation = PublicOperationExecutionContract(
        contract_id=public_operation_execution_contract_id(operation_provisional),
        **operation_values,
    )
    stop_values = {
        "semantic_source_id": semantic_source_id,
        "operation_contract_id": operation.contract_id,
        "required_node_ids": tuple(item.node_id for item in nodes),
        "terminal_node_id": terminal_id,
    }
    stop_provisional = PublicStopReadinessContract.model_construct(
        contract_id="pending", **stop_values
    )
    stop = PublicStopReadinessContract(
        contract_id=public_stop_readiness_contract_id(stop_provisional),
        **stop_values,
    )
    projection_values = {
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "visible_progress_fields": tuple(
            sorted(
                (
                    "completed_node_ids",
                    "ready_nodes",
                    "remaining_node_ids",
                    "stop_ready",
                    "terminal_node_completed",
                    "unresolved_variable_requirements",
                    "verification_after_terminal_completed",
                )
            )
        ),
        "hidden_binding_fields": tuple(
            sorted(
                (
                    "evidence_symbol_bindings",
                    "expected_operator_ids",
                    "next_required_action",
                    "ready_node_argument_contracts",
                    "ready_node_parameters",
                    "ready_node_tool_ids",
                    "source_program_node_ids",
                    "verifier_ids",
                )
            )
        ),
    }
    projection_provisional = PublicOperationRuntimeProjection.model_construct(
        projection_id="pending", **projection_values
    )
    projection = PublicOperationRuntimeProjection(
        projection_id=public_operation_runtime_projection_id(projection_provisional),
        **projection_values,
    )
    return operation, stop, projection, bindings


def _upgrade_deep_reconciliation_task(
    draft: _TaskDraft,
) -> tuple[OperationalTaskRecord, Any]:
    base_record, environment = operation_builder._materialize_task(draft)  # noqa: SLF001
    base = base_record.task_package
    operation, stop, runtime_projection, node_bindings = _deep_reconciliation_operation_contracts(
        draft,
        base.semantic_source.semantic_source_id,
    )
    verifier_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "public_runtime_contract_id": base.public_runtime_contract.contract_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "runtime_projection_id": runtime_projection.projection_id,
        "source_program_dag_hash": operation.source_program_dag_hash,
        "source_verifier_dag_hash": operation.source_verifier_dag_hash,
        "node_bindings": node_bindings,
        "verifier_implementation_id": operation_builder.V26_OPERATIONAL_VERIFIER_ID,
        "verifier_version": operation_builder.V26_OPERATIONAL_VERIFIER_VERSION,
        "exact_gold_equality_required": base.evidence_support_lattice.exact_equality_required,
    }
    verifier_provisional = OperationalExecutableVerifierBinding.model_construct(
        binding_id="pending", **verifier_values
    )
    verifier = OperationalExecutableVerifierBinding(
        binding_id=operational_executable_verifier_binding_id(verifier_provisional),
        **verifier_values,
    )
    public_bindings = {
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "intended_use": draft.intended_use,
        "operation_contract_id": operation.contract_id,
        "public_runtime_contract_id": base.public_runtime_contract.contract_id,
        "runtime_projection_id": runtime_projection.projection_id,
        "stop_readiness_contract_id": stop.contract_id,
        "tool_closure_contract_id": base.tool_closure.closure_id,
    }
    oracle_bindings = {
        **public_bindings,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "verifier_binding_id": verifier.binding_id,
    }
    metadata = dict(base.task.public.metadata)
    metadata.pop("agent_contract_guidance", None)
    metadata["executable_support_bindings"] = public_bindings
    metadata["agent_contract_guidance"] = {
        "public_operation_execution_contract": operation.public_view.model_dump(mode="json"),
        "public_stop_readiness_contract": public_stop_readiness_view(stop).model_dump(mode="json"),
        "answer_observation_constraints": operation_builder._answer_observation_constraints(  # noqa: SLF001
            draft
        ),
    }
    public_template = base.task.public.model_copy(
        update={"task_id": "pending", "metadata": metadata}
    )
    selection_contract = dict(base.task.oracle.selection_contract)
    selection_contract["executable_support_bindings"] = oracle_bindings
    oracle_template = base.task.oracle.model_copy(
        update={"task_id": "pending", "selection_contract": selection_contract}
    )
    task_template = TaskPackage(
        task_id="pending",
        public=public_template,
        oracle=oracle_template,
    )
    package_values = {
        "semantic_source": base.semantic_source,
        "task": task_template,
        "tool_closure": base.tool_closure,
        "answer_projection": base.answer_projection,
        "evidence_support_lattice": base.evidence_support_lattice,
        "citation_contract": base.citation_contract,
        "public_runtime_contract": base.public_runtime_contract,
        "mechanism_contract": base.mechanism_contract,
        "operation_contract": operation,
        "stop_readiness_contract": stop,
        "runtime_projection": runtime_projection,
        "verifier_binding": verifier,
        "schema_version": operation_builder.OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION,
    }
    package_provisional = OperationalExecutableTaskPackage.model_construct(
        package_id="pending", **package_values
    )
    package_id = operational_executable_task_package_id(package_provisional)
    task = TaskPackage(
        task_id=package_id,
        public=public_template.model_copy(update={"task_id": package_id}),
        oracle=oracle_template.model_copy(update={"task_id": package_id}),
    )
    package = OperationalExecutableTaskPackage(
        package_id=package_id,
        **{**package_values, "task": task},
    )
    record_values = {
        "mechanism_id": draft.mechanism_id,
        "intended_use": draft.intended_use,
        "source_task_artifact_ids": tuple(sorted(draft.source_task_artifact_ids)),
        "task_package": package,
        "evidence_bundle": draft.evidence_bundle,
        "public_corpus": draft.public_corpus,
        "proof_graph": draft.proof_graph,
        "projected_expected_output": draft.projected_expected_output,
        "answer_projection": draft.answer_projection,
        "mechanism_public_state": draft.mechanism_public_state,
        "mechanism_private_state": draft.mechanism_private_state,
        "recovery_scenario": base_record.recovery_scenario,
        "target_program_evidence_ids": draft.target_program_evidence_ids,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": base.public_runtime_contract.environment_manifest_hash,
        "schema_version": operation_builder.V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    }
    record_provisional = OperationalTaskRecord.model_construct(record_id="pending", **record_values)
    record = OperationalTaskRecord(
        record_id=operational_task_record_id(record_provisional),
        **record_values,
    )
    return record, environment


def _upgrade_role_task(
    draft: _TaskDraft,
) -> tuple[OperationalTaskRecord, Any]:
    if draft.mechanism_id == "semantic_reconciliation" and len(draft.program.nodes) > 1:
        return _upgrade_deep_reconciliation_task(draft)
    return operation_builder._upgrade_task(draft)  # noqa: SLF001


_FIXED_STATE_FIELDS: Final = {
    "visible_candidate_set_equals_validator_acceptance_set": True,
    "acceptance_uses_only_state_and_proposal": True,
    "stage_two_semantic_choice_or_repair": False,
    "stage_two_provider_calls": 0,
    "schema_version": "prospective_semantic_action_state.v1",
}
_CANDIDATE_DEFAULTS: Final[dict[str, Any]] = {
    "tool_id": None,
    "target_source_symbols": [],
    "acquisition_mode": None,
    "acquisition_record": None,
    "document_reference_id": None,
    "node_id": None,
    "operator_id": None,
    "source_reference_ids": [],
    "evidence_reference_ids": [],
    "wire_argument_fields": [],
    "model_selects_this_complete_semantic_action": True,
    "low_level_argument_values_model_generated": False,
    "schema_version": CANONICAL_ACTION_VERSION,
}
_CANDIDATE_FIELDS: Final = {
    "acquire_public_input": (
        "presentation_index",
        "action_id",
        "tool_id",
        "target_source_symbols",
        "acquisition_mode",
        "acquisition_record",
        "document_reference_id",
        "wire_argument_fields",
    ),
    "execute_public_operation": (
        "presentation_index",
        "action_id",
        "tool_id",
        "node_id",
        "operator_id",
        "source_reference_ids",
        "wire_argument_fields",
    ),
    "verify_terminal_operation": (
        "presentation_index",
        "action_id",
        "tool_id",
        "evidence_reference_ids",
        "wire_argument_fields",
    ),
    "emit_final_answer": ("presentation_index", "action_id"),
}


def _columnar_encode(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _columnar_encode(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        items = [_columnar_encode(item) for item in value]
        if items and all(isinstance(item, Mapping) for item in items):
            keys = tuple(sorted(cast(Mapping[str, Any], items[0])))
            if all(tuple(sorted(cast(Mapping[str, Any], item))) == keys for item in items):
                table = {
                    "$table": {
                        "columns": keys,
                        "rows": [
                            [cast(Mapping[str, Any], item)[key] for key in keys] for item in items
                        ],
                    }
                }
                if len(_json_bytes(table)) < len(_json_bytes(items)):
                    return table
        return items
    return value


def _columnar_decode(value: Any) -> Any:
    if isinstance(value, Mapping):
        if set(value) == {"$table"}:
            table = value["$table"]
            if not isinstance(table, Mapping) or set(table) != {"columns", "rows"}:
                raise ValueError("v26.130 compact table envelope is malformed")
            columns = table["columns"]
            rows = table["rows"]
            if not isinstance(columns, list) or not isinstance(rows, list):
                raise ValueError("v26.130 compact table columns or rows are malformed")
            if len(set(columns)) != len(columns) or not all(
                isinstance(key, str) for key in columns
            ):
                raise ValueError("v26.130 compact table columns are not unique strings")
            output = []
            for row in rows:
                if not isinstance(row, list) or len(row) != len(columns):
                    raise ValueError("v26.130 compact table row width changed")
                output.append(
                    {key: _columnar_decode(item) for key, item in zip(columns, row, strict=True)}
                )
            return output
        return {str(key): _columnar_decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_columnar_decode(item) for item in value]
    return value


def _compact_candidates(
    state: SemanticActionState,
    presentation_salt: str,
) -> dict[str, Any]:
    presented = action_abi._presentation_order(  # noqa: SLF001
        state.action_candidates,
        presentation_salt,
    )
    groups: dict[str, list[list[Any]]] = {key: [] for key in _CANDIDATE_FIELDS}
    for index, candidate in enumerate(presented):
        payload = candidate.model_dump(mode="json")
        fields = _CANDIDATE_FIELDS[candidate.decision_kind]
        row = []
        for field in fields:
            row.append(index if field == "presentation_index" else payload[field])
        groups[candidate.decision_kind].append(row)
    return {
        "group_order": tuple(_CANDIDATE_FIELDS),
        "groups": {
            key: {
                "columns": _CANDIDATE_FIELDS[key],
                "rows": rows,
            }
            for key, rows in groups.items()
            if rows
        },
        "fixed_candidate_contract": {
            "model_selects_this_complete_semantic_action": True,
            "low_level_argument_values_model_generated": False,
            "schema_version": CANONICAL_ACTION_VERSION,
        },
    }


def _decode_compact_candidates(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, Mapping) or set(value) != {
        "group_order",
        "groups",
        "fixed_candidate_contract",
    }:
        raise ValueError("v26.130 compact Candidate envelope is malformed")
    if tuple(value["group_order"]) != tuple(_CANDIDATE_FIELDS):
        raise ValueError("v26.130 compact Candidate group order changed")
    if value["fixed_candidate_contract"] != {
        "model_selects_this_complete_semantic_action": True,
        "low_level_argument_values_model_generated": False,
        "schema_version": CANONICAL_ACTION_VERSION,
    }:
        raise ValueError("v26.130 compact Candidate fixed contract changed")
    presented: list[tuple[int, Any]] = []
    groups = value["groups"]
    if not isinstance(groups, Mapping):
        raise ValueError("v26.130 compact Candidate groups are malformed")
    for decision_kind, table in groups.items():
        if decision_kind not in _CANDIDATE_FIELDS or not isinstance(table, Mapping):
            raise ValueError("v26.130 compact Candidate group is unknown")
        fields = _CANDIDATE_FIELDS[decision_kind]
        if tuple(table.get("columns", ())) != fields or not isinstance(table.get("rows"), list):
            raise ValueError("v26.130 compact Candidate table changed")
        for row in table["rows"]:
            if not isinstance(row, list) or len(row) != len(fields):
                raise ValueError("v26.130 compact Candidate row width changed")
            projected = dict(zip(fields, row, strict=True))
            index = int(projected.pop("presentation_index"))
            payload = {
                **_CANDIDATE_DEFAULTS,
                **projected,
                "decision_kind": decision_kind,
            }
            candidate = action_abi.CanonicalPublicAction.model_validate(payload)
            presented.append((index, candidate))
    ordered = tuple(item for _, item in sorted(presented, key=lambda pair: pair[0]))
    if tuple(index for index, _ in sorted(presented)) != tuple(range(len(ordered))):
        raise ValueError("v26.130 compact Candidate presentation indexes changed")
    return ordered


def _compact_state_projection(state: SemanticActionState) -> dict[str, Any]:
    payload = state.model_dump(mode="json", exclude={"action_candidates", *_FIXED_STATE_FIELDS})
    return {
        "state": _columnar_encode(payload),
        "fixed_state_invariants": _FIXED_STATE_FIELDS,
    }


def _decode_compact_state(
    value: Any,
    *,
    presented_candidates: Sequence[Any],
) -> SemanticActionState:
    if not isinstance(value, Mapping) or set(value) != {"state", "fixed_state_invariants"}:
        raise ValueError("v26.130 compact state envelope is malformed")
    if value["fixed_state_invariants"] != _FIXED_STATE_FIELDS:
        raise ValueError("v26.130 compact state invariants changed")
    decoded = _columnar_decode(value["state"])
    if not isinstance(decoded, Mapping):
        raise ValueError("v26.130 decoded compact state is malformed")
    candidates = tuple(sorted(presented_candidates, key=lambda item: item.action_id))
    return SemanticActionState.model_validate(
        {
            **decoded,
            **_FIXED_STATE_FIELDS,
            "action_candidates": candidates,
        }
    )


def _compact_action_prompt(
    *,
    phase: Literal["primary", "abi_rescue", "semantic_recovery"],
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    typed_failure: Mapping[str, Any] | None,
    grammar: SemanticActionResponseGrammar,
) -> str:
    validate_candidate_space_completeness(state)
    payload = {
        "prompt_protocol": f"{COMPACT_PROMPT_PROTOCOL}.{phase}",
        "semantic_action_protocol": action_abi.SEMANTIC_ACTION_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "compact_public_state": _compact_state_projection(state),
        "visible_action_candidates": _compact_candidates(state, presentation_salt),
        "candidate_presentation": {
            "order_is_semantically_neutral": True,
            "presentation_salt_sha256": hashlib.sha256(
                presentation_salt.encode("utf-8")
            ).hexdigest(),
        },
        "typed_failure": dict(typed_failure) if typed_failure is not None else None,
        "response_grammar": action_abi._model_visible_grammar(grammar),  # noqa: SLF001
        "lossless_projection_contract": {
            "exact_state_reconstruction_required": True,
            "exact_candidate_set_reconstruction_required": True,
            "exact_action_ids_unchanged": True,
            "stage_two_semantic_choice_or_repair": False,
        },
        "previous_response_content_reused": False,
        "private_reasoning_reused": False,
    }
    prefix = {
        "primary": "Select one visible action and return exactly one four-field JSON object.",
        "abi_rescue": (
            "Correct only the response ABI and return exactly one four-field JSON object."
        ),
        "semantic_recovery": (
            "Use the public rejection and select one visible action as a four-field JSON object."
        ),
    }[phase]
    return prefix + "\n" + _json_bytes(payload).decode("utf-8")


def _compact_prompt_payload(prompt: str) -> dict[str, Any]:
    _, separator, serialized = prompt.partition("\n")
    if separator != "\n":
        raise ValueError("v26.130 compact Prompt envelope is malformed")
    value = json.loads(serialized)
    if not isinstance(value, dict):
        raise ValueError("v26.130 compact Prompt payload is not an object")
    return value


def _decode_compact_prompt_with_expected_salt(
    prompt: str,
    *,
    presentation_salt: str,
) -> tuple[SemanticActionState, tuple[Any, ...]]:
    payload = _compact_prompt_payload(prompt)
    candidates = _decode_compact_candidates(payload.get("visible_action_candidates"))
    state = _decode_compact_state(
        payload.get("compact_public_state"),
        presented_candidates=candidates,
    )
    expected = action_abi._presentation_order(  # noqa: SLF001
        state.action_candidates,
        presentation_salt,
    )
    if candidates != expected:
        raise ValueError("v26.130 compact Candidate presentation order changed")
    expected_salt_hash = hashlib.sha256(presentation_salt.encode("utf-8")).hexdigest()
    presentation = payload.get("candidate_presentation")
    if (
        not isinstance(presentation, Mapping)
        or presentation.get("presentation_salt_sha256") != expected_salt_hash
        or presentation.get("order_is_semantically_neutral") is not True
    ):
        raise ValueError("v26.130 compact Candidate presentation binding changed")
    return state, candidates


def _compact_reference_proposal(
    prompt: str,
    *,
    presentation_salt: str,
) -> Any:
    payload = _compact_prompt_payload(prompt)
    state, _ = _decode_compact_prompt_with_expected_salt(
        prompt,
        presentation_salt=presentation_salt,
    )
    instruction = payload.get("instruction")
    condition = payload.get("public_path_condition")
    if not isinstance(instruction, str) or (
        condition is not None and not isinstance(condition, str)
    ):
        raise ValueError("v26.130 compact Prompt public context is malformed")
    semantic_prompt = render_semantic_action_prompt(
        instruction=instruction,
        state=state,
        public_path_condition=condition,
    )
    proposal = prompt_only_reference_proposal(semantic_prompt)
    if proposal.action_id not in {item.action_id for item in state.action_candidates}:
        raise ValueError("v26.130 compact Reference Policy selected an invisible action")
    return proposal


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + COMPLETION_REQUEST_BOUND + PROVIDER_ACCOUNTING_MARGIN


def _section_bytes(prompt: str, key: str) -> int:
    return len(_json_bytes(_compact_prompt_payload(prompt)[key]))


def _path_condition(role: Role, strategy: PathStrategy) -> str | None:
    return None if role == "capability" else strategy


def _failure_dimensions(
    *,
    maximum_prompt: int,
    primary_requests: int,
    provider_calls: int,
    upper_bound: int,
) -> tuple[FailureDimension, ...]:
    failures: list[FailureDimension] = []
    if maximum_prompt > FROZEN_PROMPT_CEILING:
        failures.append("prompt_ceiling")
    if primary_requests > FROZEN_PRIMARY_REQUEST_LIMIT:
        failures.append("primary_request_limit")
    if provider_calls > FROZEN_PROVIDER_CALL_LIMIT:
        failures.append("provider_call_limit")
    if upper_bound >= FROZEN_ROLLOUT_BOUND or FROZEN_ROLLOUT_BOUND - upper_bound < MINIMUM_HEADROOM:
        failures.append("rollout_bound")
    return tuple(failures)


def _context_reproduction_index(
    inputs: _FrozenInputs,
) -> dict[tuple[str, str, str], predecessor.KernelPathCompatibilityRow]:
    return {
        (item.role, item.source_task_artifact_id, item.path_strategy_id): item
        for item in inputs.context_compatibility.paths
    }


def _build_complexity_census(
    *,
    package_root: Path,
    inputs: _FrozenInputs,
    population_replay: FrozenPopulationReplayAudit,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: ExactFinalResponseGrammar,
) -> RoleSupportComplexityCensus:
    qualification, replay_contract = _load_and_replay_verifier_qualification(
        package_root / VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    qualification_sha = _sha256(package_root / VERIFIER_QUALIFICATION_DIR / "report.json")
    context_index = _context_reproduction_index(inputs)
    reproduced_context_keys: set[tuple[str, str, str]] = set()
    rows: list[PathComplexityRow] = []
    candidate_counts: Counter[int] = Counter()
    for population in (inputs.capability, inputs.reachability):
        bindings = sorted(
            population.tasks,
            key=lambda item: (
                TARGET_MECHANISMS.index(item.mechanism_id),
                predecessor.TIERS.index(item.tier),
            ),
        )
        for binding in bindings:
            task = inputs.tasks[binding.source_task_artifact_id]
            draft = _role_draft(
                task,
                role=population.role,
                mechanism=binding.mechanism_id,
            )
            source_record, source_environment = _upgrade_role_task(draft)
            authority_environment = _harden_environment(source_environment)
            environment = _verifier_bound_environment(authority_environment)
            authority_record = _harden_record(source_record, environment)
            replay_binding = _task_replay_binding(
                authority_record,
                environment,
                qualification,
                qualification_sha,
                replay_contract,
            )
            record = _bind_verifier_v2(authority_record, replay_binding)
            prompt_contract = _make_compact_prompt_contract(
                role=population.role,
                record=record,
                environment=environment,
            )
            strategies = cast(
                tuple[PathStrategy, ...],
                ("structured_direct",) if population.role == "capability" else PATH_STRATEGIES,
            )
            for strategy in strategies:
                condition = _path_condition(population.role, strategy)
                runtime = _runtime(record, environment)
                observations: list[AgentToolObservation] = []
                state_rows: list[StateComplexityRow] = []
                s0_primary_prompts: list[str] = []
                s0_abi_prompts: list[str] = []
                s0_recovery_prompts: list[str] = []
                s1_primary_prompts: list[str] = []
                s1_abi_prompts: list[str] = []
                s1_recovery_prompts: list[str] = []
                for logical_index in range(128):
                    try:
                        state = build_semantic_action_state(
                            record.task_package.task.public,
                            environment,
                            tuple(observations),
                        )
                    except ValueError as exc:
                        observation_summary = tuple(
                            (item.call.tool_id, item.status, item.error_code)
                            for item in observations
                        )
                        raise ValueError(
                            "v26.130 cannot construct a selectable public state for "
                            f"{population.role}/{binding.mechanism_id}/{binding.tier}/"
                            f"{strategy}/step-{logical_index}: {exc}; observations="
                            f"{observation_summary}"
                        ) from exc
                    validate_candidate_space_completeness(state)
                    if independently_enumerate_visible_actions(state) != state.action_candidates:
                        raise ValueError("v26.130 independent Candidate enumeration changed")
                    candidate_counts[len(state.action_candidates)] += 1
                    salt = canonical_hash(
                        {
                            "selection_audit_id": inputs.selection.audit_id,
                            "role_population_id": population.population_id,
                            "source_task_artifact_id": task.artifact_id,
                            "path_strategy_id": strategy,
                            "state_id": state.state_id,
                            "logical_index": logical_index,
                        },
                        prefix="finance_v26_role_candidate_presentation:",
                    )
                    primary0 = predecessor._measurement_action_prompt(  # noqa: SLF001
                        phase="primary",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=None,
                        grammar=action_grammar,
                    )
                    predecessor._assert_exact_kernel_prompt_gate(  # noqa: SLF001
                        primary0,
                        phase="primary",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=None,
                        grammar=action_grammar,
                    )
                    primary1 = _compact_action_prompt(
                        phase="primary",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=None,
                        grammar=action_grammar,
                    )
                    decoded_state, _ = _decode_compact_prompt_with_expected_salt(
                        primary1,
                        presentation_salt=salt,
                    )
                    if decoded_state != state:
                        raise ValueError("v26.130 compact Primary state reconstruction changed")
                    proposal0 = parse_prompt_only_reference_payload(primary0)
                    proposal1 = _compact_reference_proposal(
                        primary1,
                        presentation_salt=salt,
                    )
                    if proposal0 != proposal1:
                        raise ValueError("v26.130 S0/S1 Reference Proposal changed")
                    result0 = evaluate_canonical_action_proposal(
                        state,
                        proposal0,
                        call_index=len(observations) + 1,
                    )
                    result1 = evaluate_canonical_action_proposal(
                        decoded_state,
                        proposal1,
                        call_index=len(observations) + 1,
                    )
                    if (
                        result0 != result1
                        or result0.commit is None
                        or result0.rejection is not None
                    ):
                        raise ValueError("v26.130 S0/S1 Stage 2 Commit changed")
                    abi_failure = {
                        "family": "response_serialization_failure",
                        "subtype": "canonical_action_not_exact_four_field_grammar",
                    }
                    abi0 = predecessor._measurement_action_prompt(  # noqa: SLF001
                        phase="abi_rescue",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=abi_failure,
                        grammar=action_grammar,
                    )
                    abi1 = _compact_action_prompt(
                        phase="abi_rescue",
                        instruction=record.task_package.task.public.instruction,
                        state=state,
                        public_path_condition=condition,
                        presentation_salt=salt,
                        typed_failure=abi_failure,
                        grammar=action_grammar,
                    )
                    if (
                        _decode_compact_prompt_with_expected_salt(
                            abi1,
                            presentation_salt=salt,
                        )[0]
                        != state
                    ):
                        raise ValueError("v26.130 compact ABI Rescue state changed")
                    invalid = make_canonical_action_proposal(
                        state_id=state.state_id,
                        action_id=proposal0.action_id,
                        decision_kind=cast(
                            DecisionKind,
                            predecessor._other_decision_kind(proposal0.decision_kind),  # noqa: SLF001
                        ),
                    )
                    rejection = evaluate_canonical_action_proposal(
                        state,
                        invalid,
                        call_index=len(observations) + 1,
                    ).rejection
                    if rejection is None:
                        raise ValueError("v26.130 semantic rejection control was accepted")
                    recovery_state = build_semantic_action_state(
                        record.task_package.task.public,
                        environment,
                        tuple(observations),
                        semantic_rejections=(rejection,),
                    )
                    recovery_salt = f"{salt}|semantic_recovery"
                    recovery_failure = {
                        "family": "semantic_action_rejection",
                        "subtype": rejection.error_category,
                        "rejection_id": rejection.rejection_id,
                    }
                    recovery0 = predecessor._measurement_action_prompt(  # noqa: SLF001
                        phase="semantic_recovery",
                        instruction=record.task_package.task.public.instruction,
                        state=recovery_state,
                        public_path_condition=condition,
                        presentation_salt=recovery_salt,
                        typed_failure=recovery_failure,
                        grammar=action_grammar,
                    )
                    recovery1 = _compact_action_prompt(
                        phase="semantic_recovery",
                        instruction=record.task_package.task.public.instruction,
                        state=recovery_state,
                        public_path_condition=condition,
                        presentation_salt=recovery_salt,
                        typed_failure=recovery_failure,
                        grammar=action_grammar,
                    )
                    if (
                        _decode_compact_prompt_with_expected_salt(
                            recovery1,
                            presentation_salt=recovery_salt,
                        )[0]
                        != recovery_state
                    ):
                        raise ValueError("v26.130 compact Semantic Recovery state changed")
                    state_values = {
                        "state_id": state.state_id,
                        "logical_index": logical_index,
                        "candidate_count": len(state.action_candidates),
                        "s0_state_projection_utf8_bytes": len(
                            _json_bytes(action_abi._state_projection(state))  # noqa: SLF001
                        ),
                        "s0_candidate_projection_utf8_bytes": (
                            action_abi.candidate_prompt_utf8_bytes(primary0)
                        ),
                        "s0_primary_prompt_utf8_bytes": len(primary0.encode("utf-8")),
                        "s0_abi_rescue_prompt_utf8_bytes": len(abi0.encode("utf-8")),
                        "s0_semantic_recovery_prompt_utf8_bytes": len(recovery0.encode("utf-8")),
                        "s1_state_projection_utf8_bytes": _section_bytes(
                            primary1, "compact_public_state"
                        ),
                        "s1_candidate_projection_utf8_bytes": _section_bytes(
                            primary1, "visible_action_candidates"
                        ),
                        "s1_primary_prompt_utf8_bytes": len(primary1.encode("utf-8")),
                        "s1_abi_rescue_prompt_utf8_bytes": len(abi1.encode("utf-8")),
                        "s1_semantic_recovery_prompt_utf8_bytes": len(recovery1.encode("utf-8")),
                    }
                    state_provisional = StateComplexityRow.model_construct(
                        row_id="pending",
                        **state_values,
                    )
                    state_rows.append(
                        StateComplexityRow(
                            row_id=_identity(
                                state_provisional,
                                "row_id",
                                "finance_v26_role_scalability_state_complexity:",
                            ),
                            **state_values,
                        )
                    )
                    s0_primary_prompts.append(primary0)
                    s0_abi_prompts.append(abi0)
                    s0_recovery_prompts.append(recovery0)
                    s1_primary_prompts.append(primary1)
                    s1_abi_prompts.append(abi1)
                    s1_recovery_prompts.append(recovery1)
                    if result0.commit.action == "emit_final":
                        if (
                            not state.final_answer_allowed
                            or not state.terminal_verification_completed
                            or state.terminal_operation_ref is None
                        ):
                            raise ValueError("v26.130 Final Commit occurred before readiness")
                        break
                    if result0.commit.call is None:
                        raise ValueError("v26.130 non-final Commit lacks a public call")
                    observations.append(
                        _execute_observation(
                            record=record,
                            environment=environment,
                            runtime=runtime,
                            observations=tuple(observations),
                            projection=CompletionProjection(
                                request_kind="decision",
                                action="call_tool",
                                tool_id=result0.commit.call.tool_id,
                                arguments=result0.commit.call.arguments,
                            ),
                        )
                    )
                else:
                    raise ValueError("v26.130 Prompt-only reference path did not terminate")
                final_context = render_compact_final_prompt(
                    prompt_contract.public_context,
                    record.task_package.task.public,
                    tuple(observations),
                    public_path_condition=condition,
                )
                final_primary = render_exact_final_primary_prompt(
                    final_context,
                    grammar=final_grammar,
                )
                final_rescue = render_exact_final_rescue_prompt(
                    final_primary,
                    failure_family="response_serialization_failure",
                    failure_subtype="final_response_not_exact_shared_grammar",
                )
                s0_upper = sum(_request_bound(item) for item in s0_primary_prompts)
                s0_upper += _request_bound(final_primary)
                s0_upper += max(
                    max(_request_bound(item) for item in s0_abi_prompts),
                    _request_bound(final_rescue),
                )
                s0_upper += max(_request_bound(item) for item in s0_recovery_prompts)
                s1_upper = sum(_request_bound(item) for item in s1_primary_prompts)
                s1_upper += _request_bound(final_primary)
                s1_upper += max(
                    max(_request_bound(item) for item in s1_abi_prompts),
                    _request_bound(final_rescue),
                )
                s1_upper += max(_request_bound(item) for item in s1_recovery_prompts)
                s0_all_prompts = (
                    *s0_primary_prompts,
                    *s0_abi_prompts,
                    *s0_recovery_prompts,
                    final_primary,
                    final_rescue,
                )
                s1_all_prompts = (
                    *s1_primary_prompts,
                    *s1_abi_prompts,
                    *s1_recovery_prompts,
                    final_primary,
                    final_rescue,
                )
                maximum_s0_prompt = max(len(item.encode("utf-8")) for item in s0_all_prompts)
                maximum_s1_prompt = max(len(item.encode("utf-8")) for item in s1_all_prompts)
                primary_requests = len(s0_primary_prompts) + 1
                provider_calls = primary_requests + 2
                failures = _failure_dimensions(
                    maximum_prompt=maximum_s0_prompt,
                    primary_requests=primary_requests,
                    provider_calls=provider_calls,
                    upper_bound=s0_upper,
                )
                path_values = {
                    "capability_or_reachability_population_id": population.population_id,
                    "source_task_artifact_id": task.artifact_id,
                    "diagnostic_task_package_id": record.task_package.package_id,
                    "diagnostic_environment_manifest_id": environment.manifest_id,
                    "role": population.role,
                    "mechanism_id": binding.mechanism_id,
                    "tier": binding.tier,
                    "path_strategy_id": strategy,
                    "source_program_node_count": len(task.task.oracle.task_program.nodes),
                    "source_public_evidence_count": len(task.public_corpus.evidence),
                    "source_target_evidence_count": len(_target_evidence_ids(task)),
                    "action_state_count": len(state_rows),
                    "public_tool_call_count": len(observations),
                    "stage_two_commit_count": len(state_rows),
                    "primary_request_count": primary_requests,
                    "maximum_provider_calls_with_abi_and_semantic_recovery": provider_calls,
                    "maximum_provider_invocations_with_transport_replacement": provider_calls + 1,
                    "maximum_candidate_count": max(item.candidate_count for item in state_rows),
                    "maximum_s0_candidate_projection_utf8_bytes": max(
                        item.s0_candidate_projection_utf8_bytes for item in state_rows
                    ),
                    "maximum_s1_candidate_projection_utf8_bytes": max(
                        item.s1_candidate_projection_utf8_bytes for item in state_rows
                    ),
                    "maximum_s0_prompt_utf8_bytes": maximum_s0_prompt,
                    "maximum_s1_prompt_utf8_bytes": maximum_s1_prompt,
                    "s0_static_complete_path_upper_bound_tokens": s0_upper,
                    "s1_static_complete_path_upper_bound_tokens": s1_upper,
                    "frozen_kernel_failure_dimensions": failures,
                    "first_frozen_kernel_failure_dimension": failures[0] if failures else None,
                    "frozen_kernel_compatible": not failures,
                    "states": tuple(state_rows),
                }
                path_provisional = PathComplexityRow.model_construct(
                    path_id="pending",
                    **path_values,
                )
                path_row = PathComplexityRow(
                    path_id=_identity(
                        path_provisional,
                        "path_id",
                        "finance_v26_role_support_complexity_path:",
                    ),
                    **path_values,
                )
                rows.append(path_row)
                if binding.mechanism_id == "context_conditioned_action":
                    key = (population.role, task.artifact_id, strategy)
                    prior = context_index[key]
                    if (
                        path_row.diagnostic_task_package_id != prior.diagnostic_task_package_id
                        or path_row.diagnostic_environment_manifest_id
                        != prior.diagnostic_environment_manifest_id
                        or path_row.action_state_count != prior.action_state_count
                        or path_row.public_tool_call_count != prior.public_tool_call_count
                        or path_row.maximum_candidate_count != prior.maximum_candidate_count
                        or path_row.maximum_s0_candidate_projection_utf8_bytes
                        != prior.maximum_candidate_list_utf8_bytes
                        or path_row.maximum_s0_prompt_utf8_bytes != prior.maximum_prompt_utf8_bytes
                        or path_row.primary_request_count != prior.primary_request_count
                        or path_row.maximum_provider_calls_with_abi_and_semantic_recovery
                        != prior.maximum_provider_calls_with_abi_and_semantic_recovery
                        or path_row.s0_static_complete_path_upper_bound_tokens
                        != prior.static_complete_path_upper_bound_tokens
                        or path_row.frozen_kernel_compatible != prior.kernel_compatible
                    ):
                        raise ValueError("v26.130 does not reproduce the v26.129 Context Gate")
                    reproduced_context_keys.add(key)
    if reproduced_context_keys != set(context_index):
        raise ValueError("v26.130 Context reproduction denominator changed")
    ordered = tuple(sorted(rows, key=lambda item: item.path_id))
    census_values = {
        "frozen_population_replay_audit_id": population_replay.audit_id,
        "frozen_kernel_compatible_path_count": sum(
            item.frozen_kernel_compatible for item in ordered
        ),
        "frozen_kernel_incompatible_path_count": sum(
            not item.frozen_kernel_compatible for item in ordered
        ),
        "prompt_ceiling_failure_count": sum(
            "prompt_ceiling" in item.frozen_kernel_failure_dimensions for item in ordered
        ),
        "primary_request_limit_failure_count": sum(
            "primary_request_limit" in item.frozen_kernel_failure_dimensions for item in ordered
        ),
        "provider_call_limit_failure_count": sum(
            "provider_call_limit" in item.frozen_kernel_failure_dimensions for item in ordered
        ),
        "rollout_bound_failure_count": sum(
            "rollout_bound" in item.frozen_kernel_failure_dimensions for item in ordered
        ),
        "maximum_candidate_count": max(item.maximum_candidate_count for item in ordered),
        "maximum_s0_candidate_projection_utf8_bytes": max(
            item.maximum_s0_candidate_projection_utf8_bytes for item in ordered
        ),
        "maximum_s1_candidate_projection_utf8_bytes": max(
            item.maximum_s1_candidate_projection_utf8_bytes for item in ordered
        ),
        "maximum_s0_prompt_utf8_bytes": max(item.maximum_s0_prompt_utf8_bytes for item in ordered),
        "maximum_s1_prompt_utf8_bytes": max(item.maximum_s1_prompt_utf8_bytes for item in ordered),
        "maximum_primary_request_count": max(item.primary_request_count for item in ordered),
        "maximum_provider_call_count": max(
            item.maximum_provider_calls_with_abi_and_semantic_recovery for item in ordered
        ),
        "maximum_s0_static_path_upper_bound_tokens": max(
            item.s0_static_complete_path_upper_bound_tokens for item in ordered
        ),
        "maximum_s1_static_path_upper_bound_tokens": max(
            item.s1_static_complete_path_upper_bound_tokens for item in ordered
        ),
        "candidate_distribution": tuple(
            CandidateDistributionRow(candidate_count=count, state_count=states)
            for count, states in sorted(candidate_counts.items())
        ),
        "paths": ordered,
    }
    provisional = RoleSupportComplexityCensus.model_construct(
        census_id="pending",
        **census_values,
    )
    return RoleSupportComplexityCensus(
        census_id=_identity(
            provisional,
            "census_id",
            "finance_v26_role_support_complexity_census:",
        ),
        **census_values,
    )


def _strict_prompt_ceiling(maximum_prompt: int) -> int:
    return max(
        FROZEN_PROMPT_CEILING,
        math.ceil((maximum_prompt + 1) / RESOURCE_QUANTUM) * RESOURCE_QUANTUM,
    )


def _qualified_rollout_bound(maximum_upper_bound: int) -> int:
    return max(
        FROZEN_ROLLOUT_BOUND + RESOURCE_QUANTUM,
        math.ceil((maximum_upper_bound + MINIMUM_HEADROOM) / RESOURCE_QUANTUM) * RESOURCE_QUANTUM,
    )


def _make_compact_protocol(
    census: RoleSupportComplexityCensus,
) -> CompactProjectionProtocol:
    state_count = sum(item.action_state_count for item in census.paths)
    values = {
        "source_census_id": census.census_id,
        "state_control_count": state_count,
        "primary_prompt_control_count": state_count,
        "abi_rescue_prompt_control_count": state_count,
        "semantic_recovery_prompt_control_count": state_count,
        "exact_state_reconstruction_count": state_count,
        "exact_candidate_set_reconstruction_count": state_count,
        "exact_candidate_order_reconstruction_count": state_count,
        "exact_reference_proposal_count": state_count,
        "exact_stage_two_commit_count": state_count,
    }
    provisional = CompactProjectionProtocol.model_construct(protocol_id="pending", **values)
    return CompactProjectionProtocol(
        protocol_id=_identity(
            provisional,
            "protocol_id",
            "finance_v26_compact_projection_protocol:",
        ),
        **values,
    )


def _make_candidate(
    *,
    label: ProjectionLabel,
    census: RoleSupportComplexityCensus,
    compact_protocol: CompactProjectionProtocol,
) -> ScalabilityCandidate:
    if label == "S0_capacity_only":
        maximum_prompt = census.maximum_s0_prompt_utf8_bytes
        maximum_upper_bound = census.maximum_s0_static_path_upper_bound_tokens
        protocol_id = None
    else:
        maximum_prompt = census.maximum_s1_prompt_utf8_bytes
        maximum_upper_bound = census.maximum_s1_static_path_upper_bound_tokens
        protocol_id = compact_protocol.protocol_id
    prompt_ceiling = _strict_prompt_ceiling(maximum_prompt)
    rollout_bound = _qualified_rollout_bound(maximum_upper_bound)
    values = {
        "label": label,
        "source_census_id": census.census_id,
        "compact_projection_protocol_id": protocol_id,
        "prompt_ceiling_bytes": prompt_ceiling,
        "maximum_primary_requests": census.maximum_primary_request_count,
        "maximum_provider_calls_with_recovery": census.maximum_provider_call_count,
        "maximum_provider_invocations_with_transport_replacement": (
            census.maximum_provider_call_count + 1
        ),
        "rollout_upper_bound_tokens": rollout_bound,
        "measured_maximum_prompt_utf8_bytes": maximum_prompt,
        "measured_maximum_primary_requests": census.maximum_primary_request_count,
        "measured_maximum_provider_calls": census.maximum_provider_call_count,
        "measured_maximum_static_path_upper_bound_tokens": maximum_upper_bound,
        "minimum_static_headroom_tokens": rollout_bound - maximum_upper_bound,
    }
    provisional = ScalabilityCandidate.model_construct(candidate_id="pending", **values)
    return ScalabilityCandidate(
        candidate_id=_identity(
            provisional,
            "candidate_id",
            "finance_v26_role_scalability_candidate:",
        ),
        **values,
    )


def _make_selection(
    *,
    census: RoleSupportComplexityCensus,
    s0: ScalabilityCandidate,
    s1: ScalabilityCandidate,
) -> ScalabilitySelectionAudit:
    if (
        s1.maximum_primary_requests > s0.maximum_primary_requests
        or s1.maximum_provider_calls_with_recovery > s0.maximum_provider_calls_with_recovery
        or s1.prompt_ceiling_bytes >= s0.prompt_ceiling_bytes
        or s1.rollout_upper_bound_tokens >= s0.rollout_upper_bound_tokens
    ):
        raise ValueError("v26.130 S1 does not statically dominate S0")
    values = {
        "source_census_id": census.census_id,
        "s0_candidate_id": s0.candidate_id,
        "s1_candidate_id": s1.candidate_id,
        "selected_candidate_id": s1.candidate_id,
    }
    provisional = ScalabilitySelectionAudit.model_construct(audit_id="pending", **values)
    return ScalabilitySelectionAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_scalability_selection:",
        ),
        **values,
    )


def _make_support_contract(
    *,
    census: RoleSupportComplexityCensus,
    selection: ScalabilitySelectionAudit,
) -> RoleSupportScalabilityContract:
    values = {
        "source_census_id": census.census_id,
        "selected_candidate_id": selection.selected_candidate_id,
    }
    provisional = RoleSupportScalabilityContract.model_construct(
        contract_id="pending",
        **values,
    )
    return RoleSupportScalabilityContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_support_scalability_contract:",
        ),
        **values,
    )


def _reidentify_and_validate(
    model: BaseModel,
    *,
    identity_field: str,
    prefix: str,
    updates: Mapping[str, Any],
) -> None:
    payload = model.model_dump(mode="json")
    payload.update(updates)
    identity_payload = dict(payload)
    identity_payload.pop(identity_field, None)
    payload[identity_field] = canonical_hash(identity_payload, prefix=prefix)
    model_type = type(model)
    model_type.model_validate(payload)


def _expect_rejected(name: str, callback: Any) -> MutationResult:
    try:
        callback()
    except Exception:
        return MutationResult(name=name)
    raise ValueError(f"v26.130 destructive mutation was accepted: {name}")


def _build_destructive(
    *,
    population_replay: FrozenPopulationReplayAudit,
    census: RoleSupportComplexityCensus,
    compact: CompactProjectionProtocol,
    s0: ScalabilityCandidate,
    s1: ScalabilityCandidate,
    selection: ScalabilitySelectionAudit,
    support: RoleSupportScalabilityContract,
) -> DestructiveAudit:
    first_path = census.paths[0]
    first_state = first_path.states[0]
    mutations = (
        _expect_rejected(
            "additional_scalability_candidate_inserted",
            lambda: ScalabilitySelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "posthoc_candidate_added_count": 1,
                }
            ),
        ),
        _expect_rejected(
            "candidate_authority_reconstruction_failed",
            lambda: StateComplexityRow.model_validate(
                {
                    **first_state.model_dump(mode="json"),
                    "exact_candidate_set_reconstruction_passed": False,
                }
            ),
        ),
        _expect_rejected(
            "capability_population_changed",
            lambda: _reidentify_and_validate(
                population_replay,
                identity_field="audit_id",
                prefix="finance_v26_frozen_role_population_replay:",
                updates={"capability_population_id": "changed"},
            ),
        ),
        _expect_rejected(
            "census_path_deleted",
            lambda: _reidentify_and_validate(
                census,
                identity_field="census_id",
                prefix="finance_v26_role_support_complexity_census:",
                updates={"paths": census.model_dump(mode="json")["paths"][:-1]},
            ),
        ),
        _expect_rejected(
            "compact_prompt_not_strictly_smaller",
            lambda: _reidentify_and_validate(
                first_state,
                identity_field="row_id",
                prefix="finance_v26_role_scalability_state_complexity:",
                updates={"s1_primary_prompt_utf8_bytes": first_state.s0_primary_prompt_utf8_bytes},
            ),
        ),
        _expect_rejected(
            "compact_protocol_candidate_deletion",
            lambda: CompactProjectionProtocol.model_validate(
                {
                    **compact.model_dump(mode="json"),
                    "candidate_deletion_count": 1,
                }
            ),
        ),
        _expect_rejected(
            "context_reproduction_relabelled_failed",
            lambda: RoleSupportComplexityCensus.model_validate(
                {
                    **census.model_dump(mode="json"),
                    "v26_129_context_path_reproduction_passed": False,
                }
            ),
        ),
        _expect_rejected(
            "model_outcome_based_selection",
            lambda: ScalabilitySelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "model_outcomes_loaded_for_selection": True,
                }
            ),
        ),
        _expect_rejected(
            "provider_call_authorized",
            lambda: ProspectiveTransitionContract.model_validate(
                {
                    "contract_id": "pending",
                    "scalability_selection_audit_id": selection.audit_id,
                    "selected_scalability_candidate_id": s1.candidate_id,
                    "role_support_scalability_contract_id": support.contract_id,
                    "provider_calls_authorized": True,
                }
            ),
        ),
        _expect_rejected(
            "reachability_population_changed",
            lambda: _reidentify_and_validate(
                population_replay,
                identity_field="audit_id",
                prefix="finance_v26_frozen_role_population_replay:",
                updates={"reachability_population_id": "changed"},
            ),
        ),
        _expect_rejected(
            "role_support_path_count_reduced",
            lambda: RoleSupportScalabilityContract.model_validate(
                {
                    **support.model_dump(mode="json"),
                    "support_path_count": 47,
                }
            ),
        ),
        _expect_rejected(
            "s0_primary_request_bound_below_measurement",
            lambda: _reidentify_and_validate(
                s0,
                identity_field="candidate_id",
                prefix="finance_v26_role_scalability_candidate:",
                updates={"maximum_primary_requests": s0.measured_maximum_primary_requests - 1},
            ),
        ),
        _expect_rejected(
            "s0_prompt_ceiling_below_measurement",
            lambda: _reidentify_and_validate(
                s0,
                identity_field="candidate_id",
                prefix="finance_v26_role_scalability_candidate:",
                updates={"prompt_ceiling_bytes": s0.measured_maximum_prompt_utf8_bytes},
            ),
        ),
        _expect_rejected(
            "s0_provider_call_bound_below_measurement",
            lambda: _reidentify_and_validate(
                s0,
                identity_field="candidate_id",
                prefix="finance_v26_role_scalability_candidate:",
                updates={
                    "maximum_provider_calls_with_recovery": (s0.measured_maximum_provider_calls - 1)
                },
            ),
        ),
        _expect_rejected(
            "s0_rollout_bound_below_headroom",
            lambda: _reidentify_and_validate(
                s0,
                identity_field="candidate_id",
                prefix="finance_v26_role_scalability_candidate:",
                updates={
                    "rollout_upper_bound_tokens": (
                        s0.measured_maximum_static_path_upper_bound_tokens + MINIMUM_HEADROOM - 1
                    ),
                    "minimum_static_headroom_tokens": MINIMUM_HEADROOM - 1,
                },
            ),
        ),
        _expect_rejected(
            "s1_compact_protocol_removed",
            lambda: _reidentify_and_validate(
                s1,
                identity_field="candidate_id",
                prefix="finance_v26_role_scalability_candidate:",
                updates={"compact_projection_protocol_id": None},
            ),
        ),
        _expect_rejected(
            "s1_selection_replaced_by_s0",
            lambda: ScalabilitySelectionAudit.model_validate(
                {
                    **selection.model_dump(mode="json"),
                    "selected_candidate_id": s0.candidate_id,
                    "selected_label": "S0_capacity_only",
                }
            ),
        ),
        _expect_rejected(
            "stage_two_provider_route_inserted",
            lambda: CompactProjectionProtocol.model_validate(
                {
                    **compact.model_dump(mode="json"),
                    "stage_two_provider_calls": 1,
                }
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_role_scalability_destructive:",
        ),
        **values,
    )


def _make_transition(
    *,
    selection: ScalabilitySelectionAudit,
    support: RoleSupportScalabilityContract,
) -> ProspectiveTransitionContract:
    values = {
        "scalability_selection_audit_id": selection.audit_id,
        "selected_scalability_candidate_id": selection.selected_candidate_id,
        "role_support_scalability_contract_id": support.contract_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_scalability_transition:",
        ),
        **values,
    )


def build_design(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
    output_dir: Path,
) -> RoleKernelScalabilityDesignReport:
    if output_dir.exists():
        raise ValueError(f"immutable v26.130 output directory exists: {output_dir}")
    source_replay = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=predecessor_dir,
    )
    inputs, population_replay = _load_frozen_inputs(
        predecessor_dir=predecessor_dir,
        source_replay=source_replay,
    )
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    census = _build_complexity_census(
        package_root=package_root,
        inputs=inputs,
        population_replay=population_replay,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
    )
    compact = _make_compact_protocol(census)
    s0 = _make_candidate(
        label="S0_capacity_only",
        census=census,
        compact_protocol=compact,
    )
    s1 = _make_candidate(
        label="S1_lossless_compact",
        census=census,
        compact_protocol=compact,
    )
    selection = _make_selection(census=census, s0=s0, s1=s1)
    support = _make_support_contract(census=census, selection=selection)
    destructive = _build_destructive(
        population_replay=population_replay,
        census=census,
        compact=compact,
        s0=s0,
        s1=s1,
        selection=selection,
        support=support,
    )
    transition = _make_transition(selection=selection, support=support)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source_replay),
        ("frozen_population_replay_audit.json", population_replay),
        ("role_support_complexity_census.json", census),
        ("compact_projection_protocol.json", compact),
        ("scalability_candidate_s0.json", s0),
        ("scalability_candidate_s1.json", s1),
        ("scalability_selection_audit.json", selection),
        ("role_support_scalability_contract.json", support),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True)
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in sorted(outputs))
    report_values = {
        "source_replay_audit_id": source_replay.audit_id,
        "frozen_population_replay_audit_id": population_replay.audit_id,
        "complexity_census_id": census.census_id,
        "compact_projection_protocol_id": compact.protocol_id,
        "s0_candidate_id": s0.candidate_id,
        "s1_candidate_id": s1.candidate_id,
        "scalability_selection_audit_id": selection.audit_id,
        "role_support_scalability_contract_id": support.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = RoleKernelScalabilityDesignReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = RoleKernelScalabilityDesignReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_role_kernel_scalability_design_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.130 role Kernel scalability design"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--predecessor-dir",
        type=Path,
        default=package_default / PREDECESSOR_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_design(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        predecessor_dir=args.predecessor_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
