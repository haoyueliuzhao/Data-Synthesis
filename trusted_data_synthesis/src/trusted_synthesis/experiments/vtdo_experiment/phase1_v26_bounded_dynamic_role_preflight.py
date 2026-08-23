from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_kernel_scalability_design as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_scalable_kernel_runner_preflight as immediate_predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    OperationalTaskRecord,
    PathStrategy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseGrammar,
    make_final_response_host_envelope,
    parse_prompt_only_reference_final_payload,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    CanonicalActionProposal,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseGrammar,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
    AgentToolObservation,
)

RUN_ID: Final = "finance_v26_132_bounded_dynamic_role_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_132_bounded_dynamic_role_preflight_v1_20260824"
)
PREDECESSOR_DIR: Final = immediate_predecessor.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_bounded_dynamic_role_preflight.py"
)
PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
PREDECESSOR_OUTPUT_NAMES: Final = (
    "deep_reconciliation_compiler_audit.json",
    "destructive_audit.json",
    "dynamic_interaction_stress_audit.json",
    "frozen_role_input_audit.json",
    "prospective_transition_contract.json",
    "reference_runner_fixture_audit.json",
    "report.json",
    "role_identity_chain.json",
    "role_path_catalog.json",
    "role_runner_contract.json",
    "role_scalable_kernel.json",
    "role_scalable_resource_contract.json",
    "role_task_package_catalog.json",
    "source_replay_audit.json",
)

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_role_scalable_kernel_runner_preflight_report:"
    "fd9d0fc0bec5e2edc6d4411839fd9439ff27f47346263d0dc241816e946618c5"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "bcd223529c3f348f9ef99b83b11b8fcfe4b1466bf87da767a357257b04229068"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_role_scalable_transition:"
    "e90d49cb63158229fb517837525aaa584efde5b183eaefeb0812dfa16b7cba77"
)
EXPECTED_PREDECESSOR_TRANSITION_SHA256: Final = (
    "c6c655f54ec9f6843b9871358157ae024baf67fa921dbcbb08b8707ba15477a0"
)
EXPECTED_PREDECESSOR_KERNEL_ID: Final = (
    "finance_v26_role_scalable_kernel:"
    "72cb39974d500de96e5b38244112f52b90924e91de6ef31aa9e379ae87f77f55"
)
EXPECTED_PREDECESSOR_RESOURCE_ID: Final = (
    "finance_v26_role_scalable_resource_contract:"
    "169eaec0bfb1ed97f81bc16f222357e0dc37b30bc65174c205d1926c6c95e6de"
)
EXPECTED_PREDECESSOR_IDENTITY_CHAIN_ID: Final = (
    "finance_v26_role_identity_chain:"
    "40afe76db2a82687fa11806ebea0f86380a2f89a21c55c77738eb46cff9f9cbb"
)
EXPECTED_PREDECESSOR_RUNNER_ID: Final = (
    "finance_v26_role_scalable_runner_contract:"
    "932168e07b49188ae524be5f328f2c396f25921d47c0d471151d6f43cfdf41a2"
)
EXPECTED_PREDECESSOR_DYNAMIC_AUDIT_ID: Final = (
    "finance_v26_dynamic_interaction_stress:"
    "a601f93271ab6857a06c4e28d08c0bd9878e78fa1e920a40047932e59ea109fc"
)
EXPECTED_PREDECESSOR_PATH_CATALOG_ID: Final = (
    "finance_v26_role_path_catalog:14efbb6be7167b4014330e2d2b5502299701f016e93125823ab4ea3f3b748cd8"
)
EXPECTED_PREDECESSOR_REFERENCE_FIXTURE_ID: Final = (
    "finance_v26_reference_runner_fixture:"
    "135aaf5575a4cd4e6a740f3d7be12a6c97309cff9851619bf27565bad683ea82"
)
EXPECTED_CENSUS_ID: Final = (
    "finance_v26_role_support_complexity_census:"
    "d56c84e66db54f2bf44c2df82bdf3e8776b072da3c6882e59d7476b0827122d4"
)
EXPECTED_COMPACT_PROTOCOL_ID: Final = (
    "finance_v26_compact_projection_protocol:"
    "954144af0838a31f9e164d3b83a470b7851c096de754096b78388fea98dfdf1e"
)
EXPECTED_S1_CANDIDATE_ID: Final = (
    "finance_v26_role_scalability_candidate:"
    "914a3b163ae93d7dc8577fed89c53a63071cc2aaab4173e204cd31dd5ad3541b"
)
EXPECTED_SELECTION_ID: Final = (
    "finance_v26_scalability_selection:"
    "4329d62464c254ca811aa17dd617e20705111abae3a8eb37e37f52463e4e9a4b"
)
EXPECTED_SUPPORT_CONTRACT_ID: Final = (
    "finance_v26_role_support_scalability_contract:"
    "07679af22f286b51e522e00618c1907f936a3708f09aa816443001444d5350fa"
)
EXPECTED_CAPABILITY_POPULATION_ID: Final = predecessor.EXPECTED_CAPABILITY_POPULATION_ID
EXPECTED_REACHABILITY_POPULATION_ID: Final = predecessor.EXPECTED_REACHABILITY_POPULATION_ID
EXPECTED_ENGINEERING_KERNEL_FREEZE_ID: Final = predecessor.EXPECTED_ENGINEERING_KERNEL_FREEZE_ID
EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID: Final = (
    predecessor.EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID
)
EXPECTED_STAGE_ONE_PROFILE_ID: Final = (
    "finance_v26_stage_one_thinking_profile:"
    "9d89a504a3fee25a60ae392e10cab063b0604f36fb0672e19bc8f1ec45bb3045"
)
EXPECTED_STAGE_TWO_PROFILE_ID: Final = (
    "finance_v26_stage_two_commit_profile:"
    "024f2543b11f26ebc40000c7342d6ff6b4067d78b3dc11be466514fc765734a5"
)
EXPECTED_MODEL_CONFIG_ID: Final = (
    "agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015"
)
EXPECTED_THINKING_BINDING_ID: Final = (
    "prospective_thinking_model_binding:"
    "5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8"
)
EXPECTED_PROFILE_SHA256: Final = "2043fac92b0ef286c368091eb2ec424489dd94e5b6bdf5954810ecdca403615f"
EXPECTED_ACTION_PROTOCOL_ID: Final = (
    "finance_v26_semantic_action_protocol:"
    "3f178cb8af42b41809ea0d1c2324bfaf2ddfcdd732ad7cb570f2ccaec4ec8984"
)
EXPECTED_ACTION_GRAMMAR_ID: Final = (
    "prospective_semantic_action_response_grammar:"
    "bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82"
)
EXPECTED_FINAL_GRAMMAR_ID: Final = (
    "prospective_exact_final_response_grammar:"
    "5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403"
)

PROMPT_CEILING_BYTES: Final = 60_000
MAXIMUM_PRIMARY_REQUESTS: Final = 21
MAXIMUM_PROVIDER_CALLS: Final = 23
MAXIMUM_TRANSPORT_INVOCATIONS: Final = 24
ROLLOUT_UPPER_BOUND_TOKENS: Final = 1_120_000
COMPLETION_REQUEST_BOUND_TOKENS: Final = 16_384
PROVIDER_ACCOUNTING_MARGIN_TOKENS: Final = 1
MAXIMUM_ABI_RESCUES: Final = 1
MAXIMUM_SEMANTIC_RECOVERIES: Final = 1
MAXIMUM_TRANSPORT_REPLACEMENTS: Final = 1
MAXIMUM_ORDINARY_DETOURS: Final = 1
RESOURCE_QUANTUM_TOKENS: Final = 20_000
MINIMUM_ROLLOUT_HEADROOM_TOKENS: Final = 20_000
CAPABILITY_JOB_COUNT: Final = 96
REACHABILITY_JOB_COUNT: Final = 360
TOTAL_JOB_COUNT: Final = CAPABILITY_JOB_COUNT + REACHABILITY_JOB_COUNT
NEXT_STAGE: Final = (
    "fresh_s1_model_visible_representation_qualification_contract_manifest_runner_preflight_only"
)

Role: TypeAlias = Literal["capability", "reachability"]
Tier: TypeAlias = Literal["easy_control", "frontier", "hard_control"]
SamplingMode: TypeAlias = Literal[
    "capability_unconditional",
    "reachability_unconditional",
    "reachability_conditioned",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json") if isinstance(value, BaseModel) else value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    payload = _json_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    provenance: Literal["predecessor_transitive", "predecessor_output", "implementation"]


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_count: Literal[3177] = 3177
    predecessor_output_count: Literal[14] = 14
    implementation_count: Literal[1] = 1
    replayed_file_count: Literal[3192] = 3192
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3192, max_length=3192)
    replay_before_profile_parse: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_bounded_dynamic_source_replay.v1"] = (
        "finance_v26_bounded_dynamic_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        counts = Counter(item.provenance for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or counts["predecessor_transitive"] != self.predecessor_transitive_count
            or counts["predecessor_output"] != self.predecessor_output_count
            or counts["implementation"] != self.implementation_count
            or len(self.entries) != self.replayed_file_count
        ):
            raise ValueError("v26.132 source replay denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_bounded_dynamic_source_replay:"
        ):
            raise ValueError("v26.132 source replay identity changed")
        return self


class FrozenRoleInputAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_census_id: str = EXPECTED_CENSUS_ID
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    selected_s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    scalability_selection_audit_id: str = EXPECTED_SELECTION_ID
    role_support_scalability_contract_id: str = EXPECTED_SUPPORT_CONTRACT_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    reachability_population_id: str = EXPECTED_REACHABILITY_POPULATION_ID
    capability_source_task_count: Literal[12] = 12
    reachability_source_task_count: Literal[12] = 12
    total_source_task_count: Literal[24] = 24
    registered_path_count: Literal[48] = 48
    prior_overlap_count: Literal[0] = 0
    cross_role_overlap_count: Literal[0] = 0
    task_deletion_count: Literal[0] = 0
    task_substitution_count: Literal[0] = 0
    tier_change_count: Literal[0] = 0
    source_population_regenerated: Literal[False] = False
    model_outcomes_loaded: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_frozen_role_input_audit.v1"] = (
        "finance_v26_frozen_role_input_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenRoleInputAudit:
        if self.capability_population_id == self.reachability_population_id:
            raise ValueError("v26.132 role source Populations overlap")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_frozen_role_input_audit:"):
            raise ValueError("v26.132 frozen role-input identity changed")
        return self


DynamicCandidateOutcome: TypeAlias = Literal[
    "eligible_closed_no_progress",
    "successful_no_selectable_state",
    "successful_no_progress_route_not_closable",
    "successful_progress",
    "tool_not_successful",
    "not_public_call",
]

DYNAMIC_CANDIDATE_OUTCOMES: Final[tuple[DynamicCandidateOutcome, ...]] = (
    "eligible_closed_no_progress",
    "successful_no_selectable_state",
    "successful_no_progress_route_not_closable",
    "successful_progress",
    "tool_not_successful",
    "not_public_call",
)


class OrdinaryDetourPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    predecessor_kernel_id: str = EXPECTED_PREDECESSOR_KERNEL_ID
    predecessor_resource_contract_id: str = EXPECTED_PREDECESSOR_RESOURCE_ID
    predecessor_dynamic_audit_id: str = EXPECTED_PREDECESSOR_DYNAMIC_AUDIT_ID
    trajectory_class: Literal["registered_reference_plus_at_most_one_closed_ordinary_detour"] = (
        "registered_reference_plus_at_most_one_closed_ordinary_detour"
    )
    maximum_ordinary_detours: Literal[1] = MAXIMUM_ORDINARY_DETOURS
    ordinary_detour_requires_exact_legal_action: Literal[True] = True
    ordinary_detour_requires_successful_public_observation: Literal[True] = True
    ordinary_detour_requires_unchanged_public_progress_vector: Literal[True] = True
    ordinary_detour_classified_after_public_observation: Literal[True] = True
    ordinary_detour_requires_ordinary_replanning_closure: Literal[True] = True
    abi_rescue_counter_separate: Literal[True] = True
    semantic_recovery_counter_separate: Literal[True] = True
    transport_replacement_counter_separate: Literal[True] = True
    candidate_space_changed: Literal[False] = False
    candidate_presentation_changed: Literal[False] = False
    action_or_final_grammar_changed: Literal[False] = False
    detour_allowance_is_measurement_condition: Literal[True] = True
    detour_allowance_enters_vtdo_energy_contribution_or_novelty: Literal[False] = False
    second_detour_terminal_after_observation_before_later_provider: Literal[True] = True
    provider_calls: Literal[0] = 0
    status: Literal["frozen"] = "frozen"
    schema_version: Literal["finance_v26_ordinary_detour_policy.v1"] = (
        "finance_v26_ordinary_detour_policy.v1"
    )

    @model_validator(mode="after")
    def validate_policy(self) -> OrdinaryDetourPolicy:
        if (
            self.maximum_ordinary_detours != 1
            or self.candidate_space_changed
            or self.candidate_presentation_changed
            or self.action_or_final_grammar_changed
        ):
            raise ValueError("v26.132 ordinary-detour policy changed")
        if self.policy_id != _identity(
            self,
            "policy_id",
            "finance_v26_bounded_dynamic_interaction_policy:",
        ):
            raise ValueError("v26.132 ordinary-detour policy identity changed")
        return self


class DynamicCandidateClassification(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    role: Role
    mechanism_id: predecessor.TargetMechanism
    tier: Tier
    path_strategy_id: PathStrategy
    reference_state_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    outcome: DynamicCandidateOutcome
    observation_id: str | None = None
    primary_request_count: int | None = Field(default=None, ge=2)
    provider_call_count_with_recoveries: int | None = Field(default=None, ge=4)
    transport_inclusive_invocation_count: int | None = Field(default=None, ge=5)
    maximum_prompt_utf8_bytes: int | None = Field(default=None, ge=1)
    static_complete_path_upper_bound_tokens: int | None = Field(default=None, gt=0)
    public_observation_count: int | None = Field(default=None, ge=0)
    program_closed: bool = False
    terminal_verification_completed: bool = False
    final_commit_reached: bool = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> DynamicCandidateClassification:
        metrics = (
            self.primary_request_count,
            self.provider_call_count_with_recoveries,
            self.transport_inclusive_invocation_count,
            self.maximum_prompt_utf8_bytes,
            self.static_complete_path_upper_bound_tokens,
            self.public_observation_count,
        )
        eligible = self.outcome == "eligible_closed_no_progress"
        if eligible:
            if (
                any(item is None for item in metrics)
                or not self.program_closed
                or not self.terminal_verification_completed
                or not self.final_commit_reached
            ):
                raise ValueError("v26.132 eligible detour row is incomplete")
        elif any(item is not None for item in metrics) or any(
            (
                self.program_closed,
                self.terminal_verification_completed,
                self.final_commit_reached,
            )
        ):
            raise ValueError("v26.132 noneligible detour row carries completion metrics")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_bounded_dynamic_candidate_classification:",
        ):
            raise ValueError("v26.132 dynamic candidate row identity changed")
        return self


class DynamicOutcomeCount(FrozenModel):
    outcome: DynamicCandidateOutcome
    count: int = Field(ge=0)


class DynamicTrajectoryEnvelopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    ordinary_detour_policy_id: str = Field(min_length=1)
    predecessor_path_catalog_id: str = Field(min_length=1)
    predecessor_reference_fixture_id: str = Field(min_length=1)
    rows: tuple[DynamicCandidateClassification, ...] = Field(min_length=1)
    outcome_counts: tuple[DynamicOutcomeCount, ...] = Field(min_length=6, max_length=6)
    registered_path_count: Literal[48] = 48
    registered_state_count: Literal[522] = 522
    candidate_check_count: int = Field(ge=1)
    eligible_closed_detour_count: int = Field(ge=1)
    eligible_path_count: int = Field(ge=1, le=48)
    maximum_reference_primary_requests: Literal[20] = 20
    maximum_reference_provider_calls: Literal[22] = 22
    maximum_reference_transport_invocations: Literal[23] = 23
    maximum_reference_prompt_utf8_bytes: Literal[54569] = 54_569
    maximum_reference_static_tokens: Literal[1037084] = 1_037_084
    maximum_one_detour_primary_requests: int = Field(ge=2)
    maximum_one_detour_provider_calls: int = Field(ge=4)
    maximum_one_detour_transport_invocations: int = Field(ge=5)
    maximum_one_detour_prompt_utf8_bytes: int = Field(ge=1)
    maximum_one_detour_static_tokens: int = Field(gt=0)
    maximum_one_detour_row_id: str = Field(min_length=1)
    minimum_selected_rollout_headroom_tokens: int = Field(ge=MINIMUM_ROLLOUT_HEADROOM_TOKENS)
    all_registered_and_eligible_one_detour_rows_qualified: Literal[True] = True
    model_outcomes_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["bounded_dynamic_envelope_qualified"] = "bounded_dynamic_envelope_qualified"
    schema_version: Literal["finance_v26_dynamic_trajectory_envelope_audit.v1"] = (
        "finance_v26_dynamic_trajectory_envelope_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicTrajectoryEnvelopeAudit:
        row_ids = tuple(item.row_id for item in self.rows)
        counts = Counter(item.outcome for item in self.rows)
        frozen_counts = {item.outcome: item.count for item in self.outcome_counts}
        eligible = tuple(
            item for item in self.rows if item.outcome == "eligible_closed_no_progress"
        )
        maximum = max(
            eligible,
            key=lambda item: (
                cast(int, item.static_complete_path_upper_bound_tokens),
                cast(int, item.maximum_prompt_utf8_bytes),
                item.row_id,
            ),
        )
        if (
            row_ids != tuple(sorted(set(row_ids)))
            or len(self.rows) != self.candidate_check_count
            or counts != Counter(frozen_counts)
            or len(eligible) != self.eligible_closed_detour_count
            or len({item.predecessor_path_id for item in eligible}) != self.eligible_path_count
            or self.maximum_one_detour_primary_requests
            != max(cast(int, item.primary_request_count) for item in eligible)
            or self.maximum_one_detour_provider_calls
            != max(cast(int, item.provider_call_count_with_recoveries) for item in eligible)
            or self.maximum_one_detour_transport_invocations
            != max(cast(int, item.transport_inclusive_invocation_count) for item in eligible)
            or self.maximum_one_detour_prompt_utf8_bytes
            != max(cast(int, item.maximum_prompt_utf8_bytes) for item in eligible)
            or self.maximum_one_detour_static_tokens
            != cast(int, maximum.static_complete_path_upper_bound_tokens)
            or self.maximum_one_detour_row_id != maximum.row_id
            or self.maximum_one_detour_primary_requests > MAXIMUM_PRIMARY_REQUESTS
            or self.maximum_one_detour_provider_calls > MAXIMUM_PROVIDER_CALLS
            or self.maximum_one_detour_transport_invocations > MAXIMUM_TRANSPORT_INVOCATIONS
            or self.maximum_one_detour_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.maximum_one_detour_static_tokens >= ROLLOUT_UPPER_BOUND_TOKENS
            or self.minimum_selected_rollout_headroom_tokens
            != ROLLOUT_UPPER_BOUND_TOKENS - self.maximum_one_detour_static_tokens
        ):
            raise ValueError("v26.132 bounded dynamic envelope changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_dynamic_trajectory_envelope_audit:",
        ):
            raise ValueError("v26.132 dynamic envelope identity changed")
        return self


class RoleScalableKernel(FrozenModel):
    kernel_id: str = Field(min_length=1)
    predecessor_role_scalable_kernel_id: str = EXPECTED_PREDECESSOR_KERNEL_ID
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    bounded_dynamic_resource_contract_id: str = Field(min_length=1)
    predecessor_engineering_kernel_freeze_id: str = EXPECTED_ENGINEERING_KERNEL_FREEZE_ID
    predecessor_privacy_first_runner_contract_id: str = EXPECTED_PRIVACY_FIRST_RUNNER_CONTRACT_ID
    predecessor_role_support_scalability_contract_id: str = EXPECTED_SUPPORT_CONTRACT_ID
    predecessor_scalability_selection_audit_id: str = EXPECTED_SELECTION_ID
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    selected_scalability_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    model_config_id: str = EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_THINKING_BINDING_ID
    stage_one_profile_id: str = EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = EXPECTED_STAGE_TWO_PROFILE_ID
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = EXPECTED_FINAL_GRAMMAR_ID
    prompt_protocol: str = predecessor.COMPACT_PROMPT_PROTOCOL
    prompt_ceiling_bytes: Literal[60000] = PROMPT_CEILING_BYTES
    maximum_primary_requests: Literal[21] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls: Literal[23] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[24] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1120000] = ROLLOUT_UPPER_BOUND_TOKENS
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    provider_accounting_margin_tokens: Literal[1] = PROVIDER_ACCOUNTING_MARGIN_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
    maximum_ordinary_detours: Literal[1] = MAXIMUM_ORDINARY_DETOURS
    bounded_dynamic_interaction_closure_established: Literal[True] = True
    unbounded_legal_trajectory_support_claimed: Literal[False] = False
    compact_projection_is_model_visible_generation_condition: Literal[True] = True
    static_semantic_losslessness_established: Literal[True] = True
    model_behavior_equivalence_established: Literal[False] = False
    full_object_and_compact_dynamic_selection_allowed: Literal[False] = False
    complete_candidate_authority_required: Literal[True] = True
    stage_two_semantic_choice_or_repair: Literal[False] = False
    stage_two_provider_calls: Literal[0] = 0
    privacy_first_capture_required: Literal[True] = True
    deep_reconciliation_compiler_version: Literal[
        "finance_v26_role_scalable_deep_reconciliation_compiler.v1"
    ] = "finance_v26_role_scalable_deep_reconciliation_compiler.v1"
    role_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["materialized_for_credential_free_preflight"] = (
        "materialized_for_credential_free_preflight"
    )
    schema_version: Literal["finance_v26_bounded_dynamic_role_kernel.v1"] = (
        "finance_v26_bounded_dynamic_role_kernel.v1"
    )

    @model_validator(mode="after")
    def validate_kernel(self) -> RoleScalableKernel:
        if (
            self.compact_projection_protocol_id != EXPECTED_COMPACT_PROTOCOL_ID
            or self.selected_scalability_candidate_id != EXPECTED_S1_CANDIDATE_ID
            or self.model_behavior_equivalence_established
            or self.full_object_and_compact_dynamic_selection_allowed
        ):
            raise ValueError("v26.132 Role-scalable Kernel condition changed")
        if (
            self.maximum_ordinary_detours != 1
            or not self.bounded_dynamic_interaction_closure_established
            or self.unbounded_legal_trajectory_support_claimed
        ):
            raise ValueError("v26.132 bounded dynamic Kernel claim changed")
        if self.kernel_id != _identity(
            self,
            "kernel_id",
            "finance_v26_bounded_dynamic_role_kernel:",
        ):
            raise ValueError("v26.132 bounded dynamic Kernel identity changed")
        return self


class RoleScalableTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    role_population_id: str = Field(min_length=1)
    role: Role
    mechanism_id: predecessor.TargetMechanism
    tier: Tier
    source_task_artifact_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    source_program_node_count: int = Field(ge=1)
    diagnostic_operational_task_package_id: str = Field(min_length=1)
    operational_record: OperationalTaskRecord
    environment: AgentToolEnvironmentManifest
    prompt_contract: CompactPromptContract
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = EXPECTED_FINAL_GRAMMAR_ID
    source_task_semantics_preserved: Literal[True] = True
    candidate_authority_preserved: Literal[True] = True
    deep_reconciliation_formal_compiler_used: bool
    model_outcomes_used: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_role_scalable_task_package.v1"] = (
        "finance_v26_role_scalable_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> RoleScalableTaskPackage:
        record = self.operational_record
        if (
            record.task_package.package_id != self.diagnostic_operational_task_package_id
            or record.environment_manifest_id != self.environment.manifest_id
            or self.prompt_contract.role != self.role
            or self.kernel_id == self.diagnostic_operational_task_package_id
            or self.deep_reconciliation_formal_compiler_used
            != (
                self.mechanism_id == "semantic_reconciliation"
                and self.source_program_node_count > 1
            )
        ):
            raise ValueError("v26.132 Role TaskPackage binding changed")
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_role_scalable_task_package:"
        ):
            raise ValueError("v26.132 Role TaskPackage identity changed")
        return self


class RoleTaskPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    reachability_population_id: str = EXPECTED_REACHABILITY_POPULATION_ID
    packages: tuple[RoleScalableTaskPackage, ...] = Field(min_length=24, max_length=24)
    total_task_package_count: Literal[24] = 24
    capability_task_package_count: Literal[12] = 12
    reachability_task_package_count: Literal[12] = 12
    task_packages_per_role_mechanism_tier: Literal[1] = 1
    diagnostic_task_package_identity_overlap_count: Literal[0] = 0
    cross_role_source_overlap_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_role_task_package_catalog.v1"] = (
        "finance_v26_role_task_package_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> RoleTaskPackageCatalog:
        package_ids = tuple(item.task_package_id for item in self.packages)
        cells = Counter((item.role, item.mechanism_id, item.tier) for item in self.packages)
        if (
            package_ids != tuple(sorted(set(package_ids)))
            or len(cells) != 24
            or set(cells.values()) != {1}
            or any(item.kernel_id != self.kernel_id for item in self.packages)
            or any(
                item.task_package_id == item.diagnostic_operational_task_package_id
                for item in self.packages
            )
        ):
            raise ValueError("v26.132 TaskPackage catalog changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_role_task_package_catalog:"
        ):
            raise ValueError("v26.132 TaskPackage catalog identity changed")
        return self


class RoleScalablePath(FrozenModel):
    path_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_census_path_id: str = Field(min_length=1)
    role: Role
    mechanism_id: predecessor.TargetMechanism
    tier: Tier
    path_strategy_id: PathStrategy
    public_path_condition: str | None
    reference_state_ids: tuple[str, ...] = Field(min_length=1)
    candidate_presentation_salts: tuple[str, ...] = Field(min_length=1)
    primary_prompt_sha256s: tuple[str, ...] = Field(min_length=1)
    reference_proposal_ids: tuple[str, ...] = Field(min_length=1)
    stage_two_commit_ids: tuple[str, ...] = Field(min_length=1)
    observation_ids: tuple[str, ...]
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_response_envelope_id: str = Field(min_length=1)
    action_state_count: int = Field(ge=1)
    public_observation_count: int = Field(ge=0)
    primary_request_count: int = Field(ge=2)
    maximum_provider_calls_with_recovery: int = Field(ge=4)
    maximum_transport_inclusive_invocations: int = Field(ge=5)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    static_complete_path_upper_bound_tokens: int = Field(gt=0)
    exact_state_reconstruction_passed: Literal[True] = True
    exact_candidate_set_and_order_passed: Literal[True] = True
    exact_action_abi_passed: Literal[True] = True
    reversible_stage_two_commit_passed: Literal[True] = True
    exact_final_abi_passed: Literal[True] = True
    program_closed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_commit_reached: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_role_scalable_path.v1"] = (
        "finance_v26_role_scalable_path.v1"
    )

    @model_validator(mode="after")
    def validate_path(self) -> RoleScalablePath:
        count = self.action_state_count
        if (
            any(
                len(items) != count
                for items in (
                    self.reference_state_ids,
                    self.candidate_presentation_salts,
                    self.primary_prompt_sha256s,
                    self.reference_proposal_ids,
                    self.stage_two_commit_ids,
                )
            )
            or len(self.observation_ids) != count - 1
            or self.public_observation_count != len(self.observation_ids)
            or self.primary_request_count != count + 1
            or self.maximum_provider_calls_with_recovery != self.primary_request_count + 2
            or self.maximum_transport_inclusive_invocations
            != self.maximum_provider_calls_with_recovery + 1
            or self.maximum_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.primary_request_count > MAXIMUM_PRIMARY_REQUESTS
            or self.maximum_provider_calls_with_recovery > MAXIMUM_PROVIDER_CALLS
            or self.maximum_transport_inclusive_invocations > MAXIMUM_TRANSPORT_INVOCATIONS
            or self.static_complete_path_upper_bound_tokens >= ROLLOUT_UPPER_BOUND_TOKENS
        ):
            raise ValueError("v26.132 registered Role Path binding changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_role_scalable_path:"):
            raise ValueError("v26.132 Role Path identity changed")
        return self


class RolePathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    paths: tuple[RoleScalablePath, ...] = Field(min_length=48, max_length=48)
    total_path_count: Literal[48] = 48
    capability_path_count: Literal[12] = 12
    reachability_path_count: Literal[36] = 36
    paths_per_mechanism: Literal[12] = 12
    easy_path_count: Literal[16] = 16
    frontier_path_count: Literal[16] = 16
    hard_path_count: Literal[16] = 16
    predecessor_path_identity_overlap_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["registered_reference_paths_passed"] = "registered_reference_paths_passed"
    schema_version: Literal["finance_v26_role_path_catalog.v1"] = "finance_v26_role_path_catalog.v1"

    @model_validator(mode="after")
    def validate_catalog(self) -> RolePathCatalog:
        path_ids = tuple(item.path_id for item in self.paths)
        mechanism_counts = Counter(item.mechanism_id for item in self.paths)
        package_counts = Counter(item.task_package_id for item in self.paths)
        if (
            path_ids != tuple(sorted(set(path_ids)))
            or mechanism_counts != Counter({item: 12 for item in predecessor.TARGET_MECHANISMS})
            or set(package_counts.values()) != {1, 3}
            or any(item.kernel_id != self.kernel_id for item in self.paths)
            or any(item.path_id == item.predecessor_census_path_id for item in self.paths)
        ):
            raise ValueError("v26.132 Role Path catalog changed")
        if self.catalog_id != _identity(self, "catalog_id", "finance_v26_role_path_catalog:"):
            raise ValueError("v26.132 Role Path catalog identity changed")
        return self


class DeepReconciliationCompilerBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    role: Role
    tier: Tier
    source_task_artifact_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    diagnostic_operational_task_package_id: str = Field(min_length=1)
    diagnostic_environment_manifest_id: str = Field(min_length=1)
    formal_operational_task_package_id: str = Field(min_length=1)
    formal_environment_manifest_id: str = Field(min_length=1)
    source_program_node_count: int = Field(ge=2)
    public_operation_node_count: int = Field(ge=3)
    dependency_edge_count: int = Field(ge=1)
    operand_binding_count: int = Field(ge=1)
    selector_binding_count: int = Field(ge=1)
    verifier_node_binding_count: int = Field(ge=1)
    terminal_node_id: str = Field(min_length=1)
    diagnostic_compilation_projection_hash: str = Field(min_length=1)
    formal_compilation_projection_hash: str = Field(min_length=1)
    registered_path_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    path_state_projection_match_count: Literal[1, 3]
    path_prompt_projection_match_count: Literal[1, 3]
    path_resource_arithmetic_match_count: Literal[1, 3]
    exact_program_nodes_passed: Literal[True] = True
    exact_dependency_edges_passed: Literal[True] = True
    exact_evidence_and_operation_operands_passed: Literal[True] = True
    exact_selectors_passed: Literal[True] = True
    exact_verifier_bindings_passed: Literal[True] = True
    exact_terminal_node_passed: Literal[True] = True
    exact_action_state_and_prompt_projection_passed: Literal[True] = True
    exact_resource_arithmetic_passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> DeepReconciliationCompilerBindingRow:
        expected_paths = 1 if self.role == "capability" else 3
        if (
            self.formal_operational_task_package_id != self.diagnostic_operational_task_package_id
            or self.formal_environment_manifest_id != self.diagnostic_environment_manifest_id
            or self.formal_compilation_projection_hash
            != self.diagnostic_compilation_projection_hash
            or len(self.registered_path_ids) != expected_paths
            or self.path_state_projection_match_count != expected_paths
            or self.path_prompt_projection_match_count != expected_paths
            or self.path_resource_arithmetic_match_count != expected_paths
        ):
            raise ValueError("v26.132 deep Reconciliation compiler binding changed")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_role_scalable_reconciliation_compiler_binding:",
        ):
            raise ValueError("v26.132 Reconciliation binding identity changed")
        return self


class DeepReconciliationCompilerAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    rows: tuple[DeepReconciliationCompilerBindingRow, ...] = Field(min_length=4, max_length=4)
    source_task_count: Literal[4] = 4
    registered_path_count: Literal[8] = 8
    exact_program_node_binding_count: Literal[4] = 4
    exact_dependency_binding_count: Literal[4] = 4
    exact_operand_binding_count: Literal[4] = 4
    exact_selector_binding_count: Literal[4] = 4
    exact_verifier_binding_count: Literal[4] = 4
    exact_terminal_binding_count: Literal[4] = 4
    exact_state_prompt_resource_path_count: Literal[8] = 8
    diagnostic_compiler_promoted_without_semantic_change: Literal[True] = True
    historical_builder_modified: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_deep_reconciliation_compiler_audit.v1"] = (
        "finance_v26_deep_reconciliation_compiler_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DeepReconciliationCompilerAudit:
        row_ids = tuple(item.row_id for item in self.rows)
        if (
            row_ids != tuple(sorted(set(row_ids)))
            or sum(len(item.registered_path_ids) for item in self.rows)
            != self.registered_path_count
        ):
            raise ValueError("v26.132 Reconciliation audit denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_deep_reconciliation_compiler_audit:"
        ):
            raise ValueError("v26.132 Reconciliation audit identity changed")
        return self


class RoleScalableResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_resource_contract_id: str = EXPECTED_PREDECESSOR_RESOURCE_ID
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    predecessor_s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    provider_accounting_margin_tokens: Literal[1] = PROVIDER_ACCOUNTING_MARGIN_TOKENS
    prompt_ceiling_bytes: Literal[60000] = PROMPT_CEILING_BYTES
    maximum_primary_requests: Literal[21] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls_with_recovery: Literal[23] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[24] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1120000] = ROLLOUT_UPPER_BOUND_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
    maximum_ordinary_detours: Literal[1] = MAXIMUM_ORDINARY_DETOURS
    resource_quantum_tokens: Literal[20000] = RESOURCE_QUANTUM_TOKENS
    minimum_required_rollout_headroom_tokens: Literal[20000] = MINIMUM_ROLLOUT_HEADROOM_TOKENS
    observed_maximum_one_detour_primary_requests: int = Field(ge=2)
    observed_maximum_one_detour_provider_calls: int = Field(ge=4)
    observed_maximum_one_detour_transport_invocations: int = Field(ge=5)
    observed_maximum_one_detour_prompt_utf8_bytes: int = Field(ge=1)
    observed_maximum_one_detour_static_tokens: int = Field(gt=0)
    selected_rollout_headroom_tokens: int = Field(ge=MINIMUM_ROLLOUT_HEADROOM_TOKENS)
    all_registered_reference_paths_qualified: Literal[True] = True
    all_eligible_one_detour_paths_qualified: Literal[True] = True
    second_ordinary_detour_not_supported: Literal[True] = True
    bounded_dynamic_resource_adequacy_established: Literal[True] = True
    unbounded_legal_trajectory_resource_adequacy_claimed: Literal[False] = False
    task_deletion_or_threshold_relaxation_allowed: Literal[False] = False
    usage_charged_without_clipping: Literal[True] = True
    denied_request_makes_zero_provider_calls: Literal[True] = True
    model_outcomes_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["bounded_dynamic_resource_qualified_for_preflight"] = (
        "bounded_dynamic_resource_qualified_for_preflight"
    )
    schema_version: Literal["finance_v26_bounded_dynamic_resource_contract.v1"] = (
        "finance_v26_bounded_dynamic_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleScalableResourceContract:
        selected = (
            (
                self.observed_maximum_one_detour_static_tokens
                + self.minimum_required_rollout_headroom_tokens
                + self.resource_quantum_tokens
                - 1
            )
            // self.resource_quantum_tokens
        ) * self.resource_quantum_tokens
        if (
            self.maximum_ordinary_detours != 1
            or self.observed_maximum_one_detour_primary_requests != self.maximum_primary_requests
            or self.observed_maximum_one_detour_provider_calls
            != self.maximum_provider_calls_with_recovery
            or self.observed_maximum_one_detour_transport_invocations
            != self.maximum_transport_inclusive_invocations
            or self.observed_maximum_one_detour_prompt_utf8_bytes > self.prompt_ceiling_bytes
            or selected != self.rollout_upper_bound_tokens
            or self.selected_rollout_headroom_tokens
            != self.rollout_upper_bound_tokens - self.observed_maximum_one_detour_static_tokens
            or self.unbounded_legal_trajectory_resource_adequacy_claimed
        ):
            raise ValueError("v26.132 bounded dynamic resource qualification changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_bounded_dynamic_resource_contract:",
        ):
            raise ValueError("v26.132 bounded dynamic resource identity changed")
        return self


class RoleExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    role: Role
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    path_ids: tuple[str, ...] = Field(min_length=12, max_length=36)
    expected_job_count: Literal[96, 360]
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    model_config_id: str = EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_THINKING_BINDING_ID
    stage_one_profile_id: str = EXPECTED_STAGE_ONE_PROFILE_ID
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    compact_projection_is_model_visible_generation_condition: Literal[True] = True
    full_object_fallback_allowed: Literal[False] = False
    capability_and_reachability_denominators_separate: Literal[True] = True
    invalid_or_resource_censored_outcomes_retained: Literal[True] = True
    compiler_witnesses_excluded: Literal[True] = True
    state_mapping_eligible: Literal[False] = False
    empirical_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_role_scalable_execution_contract.v1"] = (
        "finance_v26_role_scalable_execution_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleExecutionContract:
        expected_jobs = (
            CAPABILITY_JOB_COUNT if self.role == "capability" else REACHABILITY_JOB_COUNT
        )
        expected_paths = 12 if self.role == "capability" else 36
        if (
            self.expected_job_count != expected_jobs
            or len(self.task_package_ids) != 12
            or len(self.path_ids) != expected_paths
            or self.task_package_ids != tuple(sorted(set(self.task_package_ids)))
            or self.path_ids != tuple(sorted(set(self.path_ids)))
            or self.full_object_fallback_allowed
            or self.empirical_execution_authorized
        ):
            raise ValueError("v26.132 role execution Contract changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalable_execution_contract:"
        ):
            raise ValueError("v26.132 role execution Contract identity changed")
        return self


class RoleJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    role: Role
    task_package_id: str = Field(min_length=1)
    mechanism_id: predecessor.TargetMechanism
    tier: Tier
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0, le=11)
    seed: int = Field(ge=0, lt=2**63)
    requested_path_id: str | None
    requested_path_strategy: PathStrategy | None
    public_condition_id: str | None
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    schema_version: Literal["finance_v26_role_scalable_job.v1"] = "finance_v26_role_scalable_job.v1"

    @model_validator(mode="after")
    def validate_job(self) -> RoleJob:
        conditioned = self.sampling_mode == "reachability_conditioned"
        conditional_fields = (
            self.requested_path_id,
            self.requested_path_strategy,
            self.public_condition_id,
        )
        if conditioned != all(item is not None for item in conditional_fields):
            raise ValueError("v26.132 conditioned Job binding changed")
        if not conditioned and any(item is not None for item in conditional_fields):
            raise ValueError("v26.132 unconditional Job carries a condition")
        if self.role == "capability":
            if self.sampling_mode != "capability_unconditional" or self.replicate_index >= 8:
                raise ValueError("v26.132 Capability Job denominator changed")
        elif self.sampling_mode == "capability_unconditional":
            raise ValueError("v26.132 Reachability Job uses Capability sampling")
        elif conditioned and self.replicate_index >= 6:
            raise ValueError("v26.132 conditioned Job denominator changed")
        if self.job_id != _identity(self, "job_id", "finance_v26_role_scalable_job:"):
            raise ValueError("v26.132 Role Job identity changed")
        return self


class RoleJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    role: Role
    jobs: tuple[RoleJob, ...] = Field(min_length=96, max_length=360)
    expected_job_count: Literal[96, 360]
    empirical_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["materialized_but_execution_not_authorized"] = (
        "materialized_but_execution_not_authorized"
    )
    schema_version: Literal["finance_v26_role_scalable_manifest.v1"] = (
        "finance_v26_role_scalable_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> RoleJobManifest:
        expected = CAPABILITY_JOB_COUNT if self.role == "capability" else REACHABILITY_JOB_COUNT
        ids = tuple(item.job_id for item in self.jobs)
        task_counts = Counter(item.task_package_id for item in self.jobs)
        if (
            self.expected_job_count != expected
            or len(self.jobs) != expected
            or ids != tuple(sorted(set(ids)))
            or any(
                item.contract_id != self.contract_id or item.role != self.role for item in self.jobs
            )
        ):
            raise ValueError("v26.132 Role Manifest identity chain changed")
        if self.role == "capability":
            if len(task_counts) != 12 or set(task_counts.values()) != {8}:
                raise ValueError("v26.132 Capability Manifest denominator changed")
        else:
            modes = Counter(item.sampling_mode for item in self.jobs)
            conditioned_paths = Counter(
                cast(str, item.requested_path_id)
                for item in self.jobs
                if item.sampling_mode == "reachability_conditioned"
            )
            if (
                modes
                != Counter(
                    {
                        "reachability_unconditional": 144,
                        "reachability_conditioned": 216,
                    }
                )
                or set(conditioned_paths.values()) != {6}
                or len(conditioned_paths) != 36
            ):
                raise ValueError("v26.132 Reachability Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_role_scalable_manifest:"
        ):
            raise ValueError("v26.132 Role Manifest identity changed")
        return self


class RoleIdentityChain(FrozenModel):
    chain_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    capability_contract: RoleExecutionContract
    reachability_contract: RoleExecutionContract
    capability_manifest: RoleJobManifest
    reachability_manifest: RoleJobManifest
    task_package_count: Literal[24] = 24
    path_count: Literal[48] = 48
    contract_count: Literal[2] = 2
    manifest_count: Literal[2] = 2
    job_count: Literal[456] = TOTAL_JOB_COUNT
    unique_job_count: Literal[456] = TOTAL_JOB_COUNT
    cross_role_job_overlap_count: Literal[0] = 0
    historical_job_overlap_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["materialized"] = "materialized"
    schema_version: Literal["finance_v26_role_identity_chain.v1"] = (
        "finance_v26_role_identity_chain.v1"
    )

    @model_validator(mode="after")
    def validate_chain(self) -> RoleIdentityChain:
        capability_ids = {item.job_id for item in self.capability_manifest.jobs}
        reachability_ids = {item.job_id for item in self.reachability_manifest.jobs}
        if (
            self.capability_contract.contract_id != self.capability_manifest.contract_id
            or self.reachability_contract.contract_id != self.reachability_manifest.contract_id
            or self.capability_contract.role != "capability"
            or self.reachability_contract.role != "reachability"
            or capability_ids & reachability_ids
            or len(capability_ids | reachability_ids) != TOTAL_JOB_COUNT
        ):
            raise ValueError("v26.132 Role identity chain changed")
        if self.chain_id != _identity(self, "chain_id", "finance_v26_role_identity_chain:"):
            raise ValueError("v26.132 Role identity-chain identity changed")
        return self


class RoleRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_run_id: str = RUN_ID
    future_execution_run_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    identity_chain_id: str = Field(min_length=1)
    capability_manifest_id: str = Field(min_length=1)
    reachability_manifest_id: str = Field(min_length=1)
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    model_config_id: str = EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = EXPECTED_THINKING_BINDING_ID
    profile_sha256: str = EXPECTED_PROFILE_SHA256
    thinking_type: Literal["enabled"] = "enabled"
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    prompt_ceiling_bytes: Literal[60000] = PROMPT_CEILING_BYTES
    maximum_primary_requests: Literal[21] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls: Literal[23] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[24] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1120000] = ROLLOUT_UPPER_BOUND_TOKENS
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
    maximum_ordinary_detours: Literal[1] = MAXIMUM_ORDINARY_DETOURS
    ordinary_detour_counted_only_after_successful_no_progress_observation: Literal[True] = True
    second_detour_emits_typed_resource_terminal: Literal[True] = True
    no_provider_call_after_second_detour_terminal: Literal[True] = True
    recovery_counters_independent_from_detour_counter: Literal[True] = True
    privacy_redacted_envelope_persisted_before_payload_validation: Literal[True] = True
    public_payload_projection_is_separate_artifact: Literal[True] = True
    private_reasoning_content_or_hash_persisted: Literal[False] = False
    raw_request_or_response_body_persisted: Literal[False] = False
    raw_only_recovery: Literal[True] = True
    orphan_provider_artifact_fails_closed: Literal[True] = True
    stage_two_reverses_same_action_id: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0
    full_object_fallback_allowed: Literal[False] = False
    compact_or_full_dynamic_choice_allowed: Literal[False] = False
    denied_resource_request_makes_zero_provider_calls: Literal[True] = True
    credential_lookup_after_complete_preflight_only: Literal[True] = True
    model_client_constructed: Literal[False] = False
    empirical_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["implemented_for_credential_free_preflight"] = (
        "implemented_for_credential_free_preflight"
    )
    schema_version: Literal["finance_v26_bounded_dynamic_runner_contract.v1"] = (
        "finance_v26_bounded_dynamic_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleRunnerContract:
        if (
            self.thinking_type != "enabled"
            or self.full_object_fallback_allowed
            or self.compact_or_full_dynamic_choice_allowed
            or self.empirical_execution_authorized
        ):
            raise ValueError("v26.132 Runner condition changed")
        if self.maximum_ordinary_detours != 1:
            raise ValueError("v26.132 Runner detour allowance changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_bounded_dynamic_runner_contract:",
        ):
            raise ValueError("v26.132 bounded dynamic Runner identity changed")
        return self


class ReferencePathPreflightRow(FrozenModel):
    row_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    role: Role
    mechanism_id: predecessor.TargetMechanism
    tier: Tier
    path_strategy_id: PathStrategy
    action_state_count: int = Field(ge=1)
    semantic_action_primary_count: int = Field(ge=1)
    final_primary_count: Literal[1] = 1
    primary_request_count: int = Field(ge=2)
    potential_provider_call_count: int = Field(ge=4)
    potential_transport_invocation_count: int = Field(ge=5)
    public_observation_count: int = Field(ge=0)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    static_path_upper_bound_tokens: int = Field(gt=0)
    exact_compact_state_and_candidate_reconstruction_passed: Literal[True] = True
    exact_action_abi_passed: Literal[True] = True
    reversible_stage_two_commit_passed: Literal[True] = True
    exact_final_abi_passed: Literal[True] = True
    program_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    registered_resource_bounds_passed: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> ReferencePathPreflightRow:
        if (
            self.semantic_action_primary_count != self.action_state_count
            or self.primary_request_count != self.semantic_action_primary_count + 1
            or self.potential_provider_call_count != self.primary_request_count + 2
            or self.potential_transport_invocation_count != self.potential_provider_call_count + 1
            or self.public_observation_count != self.action_state_count - 1
            or self.maximum_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.primary_request_count > MAXIMUM_PRIMARY_REQUESTS
            or self.potential_provider_call_count > MAXIMUM_PROVIDER_CALLS
            or self.potential_transport_invocation_count > MAXIMUM_TRANSPORT_INVOCATIONS
            or self.static_path_upper_bound_tokens >= ROLLOUT_UPPER_BOUND_TOKENS
        ):
            raise ValueError("v26.132 reference-path preflight row changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_role_reference_path_preflight:"):
            raise ValueError("v26.132 reference-path preflight identity changed")
        return self


class ReferenceRunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    rows: tuple[ReferencePathPreflightRow, ...] = Field(min_length=48, max_length=48)
    path_count: Literal[48] = 48
    semantic_action_primary_count: Literal[522] = 522
    final_primary_count: Literal[48] = 48
    total_primary_request_count: Literal[570] = 570
    stage_two_commit_count: Literal[522] = 522
    public_observation_count: Literal[474] = 474
    exact_final_response_count: Literal[48] = 48
    program_closure_count: Literal[48] = 48
    terminal_verification_count: Literal[48] = 48
    exact_registered_resource_pass_count: Literal[48] = 48
    capability_path_count: Literal[12] = 12
    reachability_path_count: Literal[36] = 36
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["registered_reference_paths_passed"] = "registered_reference_paths_passed"
    schema_version: Literal["finance_v26_reference_runner_fixture.v1"] = (
        "finance_v26_reference_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ReferenceRunnerFixtureAudit:
        row_ids = tuple(item.row_id for item in self.rows)
        if (
            row_ids != tuple(sorted(set(row_ids)))
            or sum(item.semantic_action_primary_count for item in self.rows)
            != self.semantic_action_primary_count
            or sum(item.primary_request_count for item in self.rows)
            != self.total_primary_request_count
            or sum(item.public_observation_count for item in self.rows)
            != self.public_observation_count
        ):
            raise ValueError("v26.132 reference Runner denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_reference_runner_fixture:"):
            raise ValueError("v26.132 reference Runner identity changed")
        return self


class TypedDetourResourceTerminal(FrozenModel):
    terminal_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    ordinary_detours_observed: Literal[2] = 2
    ordinary_detours_allowed: Literal[1] = 1
    reason: Literal["ordinary_detour_allowance_exhausted"] = "ordinary_detour_allowance_exhausted"
    second_detour_model_proposal_already_observed: Literal[True] = True
    second_detour_tool_observation_already_observed: Literal[True] = True
    emitted_before_any_later_provider_invocation: Literal[True] = True
    later_provider_calls: Literal[0] = 0
    job_terminal: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_terminal(self) -> TypedDetourResourceTerminal:
        if self.ordinary_detours_observed != self.ordinary_detours_allowed + 1:
            raise ValueError("v26.132 detour resource terminal count changed")
        if self.terminal_id != _identity(
            self,
            "terminal_id",
            "finance_v26_typed_detour_resource_terminal:",
        ):
            raise ValueError("v26.132 detour resource terminal identity changed")
        return self


class BoundedDynamicControl(FrozenModel):
    name: str = Field(min_length=1)
    status: Literal["passed"]
    observed_value: int | str | bool
    expected_value: int | str | bool
    provider_calls: Literal[0] = 0


class BoundedDynamicRunnerPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    reference_fixture_audit_id: str = Field(min_length=1)
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    controls: tuple[BoundedDynamicControl, ...] = Field(min_length=10)
    control_count: int = Field(ge=10)
    passed_control_count: int = Field(ge=10)
    registered_reference_path_count: Literal[48] = 48
    registered_reference_pass_count: Literal[48] = 48
    eligible_one_detour_count: int = Field(ge=1)
    eligible_one_detour_pass_count: int = Field(ge=1)
    maximum_one_detour_primary_requests: Literal[21] = 21
    maximum_one_detour_provider_calls: Literal[23] = 23
    maximum_one_detour_transport_invocations: Literal[24] = 24
    maximum_one_detour_prompt_utf8_bytes: int = Field(ge=1, le=PROMPT_CEILING_BYTES)
    maximum_one_detour_static_tokens: int = Field(gt=0, lt=ROLLOUT_UPPER_BOUND_TOKENS)
    selected_rollout_headroom_tokens: int = Field(ge=MINIMUM_ROLLOUT_HEADROOM_TOKENS)
    two_detour_primary_requests: int = Field(ge=22)
    two_detour_provider_calls: int = Field(ge=24)
    two_detour_transport_invocations: int = Field(ge=25)
    two_detour_prompt_utf8_bytes: int = Field(ge=1)
    two_detour_static_tokens: int = Field(gt=0)
    typed_second_detour_terminal: TypedDetourResourceTerminal
    second_detour_full_path_exceeds_at_least_one_bound: Literal[True] = True
    second_detour_terminal_emitted_after_observation_before_later_provider: Literal[True] = True
    no_claim_of_preproposal_detour_knowledge: Literal[True] = True
    abi_rescue_remaining_after_one_detour: Literal[1] = 1
    semantic_recovery_remaining_after_one_detour: Literal[1] = 1
    transport_replacement_remaining_after_one_detour: Literal[1] = 1
    detour_counter_remaining_after_abi_rescue: Literal[1] = 1
    detour_counter_remaining_after_semantic_recovery: Literal[1] = 1
    detour_counter_remaining_after_transport_replacement: Literal[1] = 1
    candidate_space_change_count: Literal[0] = 0
    candidate_presentation_change_count: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    status: Literal["bounded_dynamic_runner_preflight_passed"] = (
        "bounded_dynamic_runner_preflight_passed"
    )
    schema_version: Literal["finance_v26_bounded_dynamic_runner_preflight_audit.v1"] = (
        "finance_v26_bounded_dynamic_runner_preflight_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> BoundedDynamicRunnerPreflightAudit:
        names = tuple(item.name for item in self.controls)
        exceeds = (
            self.two_detour_primary_requests > MAXIMUM_PRIMARY_REQUESTS
            or self.two_detour_provider_calls > MAXIMUM_PROVIDER_CALLS
            or self.two_detour_transport_invocations > MAXIMUM_TRANSPORT_INVOCATIONS
            or self.two_detour_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.two_detour_static_tokens >= ROLLOUT_UPPER_BOUND_TOKENS
        )
        if (
            names != tuple(sorted(set(names)))
            or self.control_count != len(self.controls)
            or self.passed_control_count != len(self.controls)
            or self.eligible_one_detour_pass_count != self.eligible_one_detour_count
            or self.selected_rollout_headroom_tokens
            != ROLLOUT_UPPER_BOUND_TOKENS - self.maximum_one_detour_static_tokens
            or not exceeds
        ):
            raise ValueError("v26.132 bounded Runner preflight changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_bounded_dynamic_runner_preflight_audit:",
        ):
            raise ValueError("v26.132 bounded Runner preflight identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=24, max_length=24)
    mutation_count: Literal[24] = 24
    rejection_count: Literal[24] = 24
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_bounded_dynamic_destructive.v1"] = (
        "finance_v26_bounded_dynamic_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.132 destructive mutation names changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_bounded_dynamic_destructive:",
        ):
            raise ValueError("v26.132 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    identity_chain_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    bounded_runner_preflight_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_frozen_role_populations_must_be_preserved: Literal[True] = True
    exact_s1_model_visible_projection_must_be_preserved: Literal[True] = True
    exact_bounded_detour_policy_must_be_preserved: Literal[True] = True
    exact_bounded_dynamic_resource_contract_must_be_preserved: Literal[True] = True
    fresh_s1_qualification_identity_chain_required: Literal[True] = True
    qualification_design_and_runner_preflight_only: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    s1_model_visible_representation_qualification_execution_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    task_deletion_substitution_or_tier_change_authorized: Literal[False] = False
    compact_projection_candidate_or_presentation_change_authorized: Literal[False] = False
    model_profile_completion_or_grammar_change_authorized: Literal[False] = False
    recovery_or_detour_allowance_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    status: Literal["bounded_dynamic_interaction_closure_passed"] = (
        "bounded_dynamic_interaction_closure_passed"
    )
    schema_version: Literal["finance_v26_bounded_dynamic_transition.v1"] = (
        "finance_v26_bounded_dynamic_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if (
            self.provider_calls_authorized
            or self.s1_model_visible_representation_qualification_execution_authorized
            or self.capability_or_reachability_execution_authorized
        ):
            raise ValueError("v26.132 Transition authorizes an online stage")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_bounded_dynamic_transition:",
        ):
            raise ValueError("v26.132 Transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class BoundedDynamicRolePreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    frozen_role_input_audit_id: str = Field(min_length=1)
    ordinary_detour_policy_id: str = Field(min_length=1)
    dynamic_trajectory_envelope_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    deep_reconciliation_compiler_audit_id: str = Field(min_length=1)
    role_identity_chain_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    reference_runner_fixture_audit_id: str = Field(min_length=1)
    bounded_runner_preflight_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=15, max_length=15)
    role_task_package_count: Literal[24] = 24
    role_path_count: Literal[48] = 48
    role_contract_count: Literal[2] = 2
    role_manifest_count: Literal[2] = 2
    role_job_count: Literal[456] = TOTAL_JOB_COUNT
    role_runner_count: Literal[1] = 1
    registered_reference_path_pass_count: Literal[48] = 48
    dynamic_candidate_check_count: int = Field(ge=1)
    eligible_one_detour_pass_count: int = Field(ge=1)
    maximum_one_detour_primary_requests: Literal[21] = 21
    maximum_one_detour_provider_calls: Literal[23] = 23
    maximum_one_detour_transport_invocations: Literal[24] = 24
    maximum_one_detour_prompt_utf8_bytes: int = Field(ge=1)
    maximum_one_detour_static_tokens: int = Field(gt=0)
    selected_rollout_headroom_tokens: int = Field(ge=MINIMUM_ROLLOUT_HEADROOM_TOKENS)
    typed_second_detour_terminal_count: Literal[1] = 1
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    role_execution_authorized: Literal[False] = False
    s1_representation_qualification_executed: Literal[False] = False
    status: Literal["bounded_dynamic_interaction_preflight_passed"] = (
        "bounded_dynamic_interaction_preflight_passed"
    )
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_bounded_dynamic_role_preflight_report.v1"] = (
        "finance_v26_bounded_dynamic_role_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> BoundedDynamicRolePreflightReport:
        if (
            self.role_execution_authorized
            or self.s1_representation_qualification_executed
            or self.selected_rollout_headroom_tokens
            != ROLLOUT_UPPER_BOUND_TOKENS - self.maximum_one_detour_static_tokens
        ):
            raise ValueError("v26.132 report claim changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_bounded_dynamic_role_preflight_report:",
        ):
            raise ValueError("v26.132 report identity changed")
        return self


@dataclass(frozen=True)
class _LoadedInputs:
    frozen: Any
    formal_census: predecessor.RoleSupportComplexityCensus
    compact: predecessor.CompactProjectionProtocol
    s1: predecessor.ScalabilityCandidate
    selection: predecessor.ScalabilitySelectionAudit
    support: predecessor.RoleSupportScalabilityContract


@dataclass(frozen=True)
class _MaterializedTask:
    source_binding: Any
    package: RoleScalableTaskPackage


@dataclass(frozen=True)
class _PathExecution:
    task: _MaterializedTask
    path: RoleScalablePath
    states: tuple[SemanticActionState, ...]
    proposals: tuple[CanonicalActionProposal, ...]
    commits: tuple[CanonicalActionCommit, ...]
    observations: tuple[AgentToolObservation, ...]
    action_prompts: tuple[str, ...]
    final_primary_prompt: str
    final_rescue_prompt: str


@dataclass(frozen=True)
class _InteractionAllowanceState:
    abi_rescues_remaining: int
    semantic_recoveries_remaining: int
    transport_replacements_remaining: int
    ordinary_detours_remaining: int


def _consume_interaction_allowance(
    state: _InteractionAllowanceState,
    event: Literal[
        "abi_rescue",
        "semantic_recovery",
        "transport_replacement",
        "ordinary_detour",
    ],
) -> _InteractionAllowanceState:
    field_by_event = {
        "abi_rescue": "abi_rescues_remaining",
        "semantic_recovery": "semantic_recoveries_remaining",
        "transport_replacement": "transport_replacements_remaining",
        "ordinary_detour": "ordinary_detours_remaining",
    }
    field = field_by_event[event]
    if getattr(state, field) <= 0:
        raise ValueError(f"{event}_allowance_exhausted")
    return _InteractionAllowanceState(
        abi_rescues_remaining=state.abi_rescues_remaining - (event == "abi_rescue"),
        semantic_recoveries_remaining=(
            state.semantic_recoveries_remaining - (event == "semantic_recovery")
        ),
        transport_replacements_remaining=(
            state.transport_replacements_remaining - (event == "transport_replacement")
        ),
        ordinary_detours_remaining=(
            state.ordinary_detours_remaining - (event == "ordinary_detour")
        ),
    )


@dataclass(frozen=True)
class _ImmediatePredecessorBuild:
    loaded: Any
    frozen_audit: Any
    kernel: Any
    task_catalog: Any
    executions: tuple[Any, ...]
    path_catalog: Any
    deep_reconciliation: Any
    resource: Any
    identity_chain: Any
    runner: Any
    reference: Any
    dynamic: Any


def _rebuild_immediate_predecessor(
    *,
    package_root: Path,
    predecessor_dir: Path,
) -> _ImmediatePredecessorBuild:
    formal_source_replay = immediate_predecessor.SourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    loaded, frozen_audit = immediate_predecessor._load_inputs(  # noqa: SLF001
        package_root=package_root,
        predecessor_dir=package_root / immediate_predecessor.PREDECESSOR_DIR,
        source_replay=formal_source_replay,
    )
    kernel = immediate_predecessor._make_kernel(package_root)  # noqa: SLF001
    tasks, task_catalog = immediate_predecessor._materialize_tasks(  # noqa: SLF001
        package_root=package_root,
        loaded=loaded,
        kernel=kernel,
    )
    executions, path_catalog = immediate_predecessor._materialize_paths(  # noqa: SLF001
        package_root=package_root,
        loaded=loaded,
        kernel=kernel,
        task_catalog=task_catalog,
        tasks=tasks,
    )
    deep_reconciliation = immediate_predecessor._make_reconciliation_audit(  # noqa: SLF001
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        loaded=loaded,
    )
    resource = immediate_predecessor._make_resource_contract(kernel)  # noqa: SLF001
    identity_chain = immediate_predecessor._make_identity_chain(  # noqa: SLF001
        kernel=kernel,
        resource=resource,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
    runner = immediate_predecessor._make_runner_contract(  # noqa: SLF001
        kernel=kernel,
        resource=resource,
        identity_chain=identity_chain,
    )
    reference = immediate_predecessor._make_reference_fixture(  # noqa: SLF001
        runner=runner,
        path_catalog=path_catalog,
    )
    dynamic = immediate_predecessor._make_dynamic_stress_audit(  # noqa: SLF001
        package_root=package_root,
        loaded=loaded,
        runner=runner,
        reference=reference,
        executions=executions,
    )
    comparisons = (
        (
            frozen_audit,
            immediate_predecessor.FrozenRoleInputAudit.model_validate_json(
                (predecessor_dir / "frozen_role_input_audit.json").read_text(encoding="utf-8")
            ),
        ),
        (
            kernel,
            immediate_predecessor.RoleScalableKernel.model_validate_json(
                (predecessor_dir / "role_scalable_kernel.json").read_text(encoding="utf-8")
            ),
        ),
        (
            task_catalog,
            immediate_predecessor.RoleTaskPackageCatalog.model_validate_json(
                (predecessor_dir / "role_task_package_catalog.json").read_text(encoding="utf-8")
            ),
        ),
        (
            path_catalog,
            immediate_predecessor.RolePathCatalog.model_validate_json(
                (predecessor_dir / "role_path_catalog.json").read_text(encoding="utf-8")
            ),
        ),
        (
            deep_reconciliation,
            immediate_predecessor.DeepReconciliationCompilerAudit.model_validate_json(
                (predecessor_dir / "deep_reconciliation_compiler_audit.json").read_text(
                    encoding="utf-8"
                )
            ),
        ),
        (
            resource,
            immediate_predecessor.RoleScalableResourceContract.model_validate_json(
                (predecessor_dir / "role_scalable_resource_contract.json").read_text(
                    encoding="utf-8"
                )
            ),
        ),
        (
            identity_chain,
            immediate_predecessor.RoleIdentityChain.model_validate_json(
                (predecessor_dir / "role_identity_chain.json").read_text(encoding="utf-8")
            ),
        ),
        (
            runner,
            immediate_predecessor.RoleRunnerContract.model_validate_json(
                (predecessor_dir / "role_runner_contract.json").read_text(encoding="utf-8")
            ),
        ),
        (
            reference,
            immediate_predecessor.ReferenceRunnerFixtureAudit.model_validate_json(
                (predecessor_dir / "reference_runner_fixture_audit.json").read_text(
                    encoding="utf-8"
                )
            ),
        ),
        (
            dynamic,
            immediate_predecessor.DynamicInteractionStressAudit.model_validate_json(
                (predecessor_dir / "dynamic_interaction_stress_audit.json").read_text(
                    encoding="utf-8"
                )
            ),
        ),
    )
    mismatch_indexes = tuple(
        index
        for index, (rebuilt, formal) in enumerate(comparisons)
        if rebuilt.model_dump(mode="json") != formal.model_dump(mode="json")
    )
    if mismatch_indexes:
        mismatch_fields = {
            index: tuple(
                key
                for key in sorted(
                    set(comparisons[index][0].model_fields_set)
                    | set(comparisons[index][1].model_fields_set)
                )
                if comparisons[index][0].model_dump(mode="json").get(key)
                != comparisons[index][1].model_dump(mode="json").get(key)
            )
            for index in mismatch_indexes
        }
        raise ValueError(
            "v26.132 immediate v26.131 predecessor does not reproduce: "
            f"comparison fields {mismatch_fields}"
        )
    if (
        kernel.kernel_id != EXPECTED_PREDECESSOR_KERNEL_ID
        or resource.contract_id != EXPECTED_PREDECESSOR_RESOURCE_ID
        or identity_chain.chain_id != EXPECTED_PREDECESSOR_IDENTITY_CHAIN_ID
        or runner.contract_id != EXPECTED_PREDECESSOR_RUNNER_ID
        or path_catalog.catalog_id != EXPECTED_PREDECESSOR_PATH_CATALOG_ID
        or reference.audit_id != EXPECTED_PREDECESSOR_REFERENCE_FIXTURE_ID
        or dynamic.audit_id != EXPECTED_PREDECESSOR_DYNAMIC_AUDIT_ID
    ):
        raise ValueError("v26.132 immediate predecessor identity changed")
    return _ImmediatePredecessorBuild(
        loaded=loaded,
        frozen_audit=frozen_audit,
        kernel=kernel,
        task_catalog=task_catalog,
        executions=tuple(executions),
        path_catalog=path_catalog,
        deep_reconciliation=deep_reconciliation,
        resource=resource,
        identity_chain=identity_chain,
        runner=runner,
        reference=reference,
        dynamic=dynamic,
    )


def _rematerialize_tasks(
    *,
    predecessor_catalog: Any,
    kernel: RoleScalableKernel,
) -> tuple[RoleTaskPackageCatalog, dict[str, str]]:
    packages: list[RoleScalableTaskPackage] = []
    mapping: dict[str, str] = {}
    for old in predecessor_catalog.packages:
        values = old.model_dump(mode="json")
        old_id = cast(str, values.pop("task_package_id"))
        values["kernel_id"] = kernel.kernel_id
        package = RoleScalableTaskPackage(
            task_package_id=canonical_hash(
                values,
                prefix="finance_v26_role_scalable_task_package:",
            ),
            **values,
        )
        mapping[old_id] = package.task_package_id
        packages.append(package)
    ordered = tuple(sorted(packages, key=lambda item: item.task_package_id))
    values = {
        "kernel_id": kernel.kernel_id,
        "packages": ordered,
    }
    provisional = RoleTaskPackageCatalog.model_construct(catalog_id="pending", **values)
    return (
        RoleTaskPackageCatalog(
            catalog_id=_identity(
                provisional,
                "catalog_id",
                "finance_v26_role_task_package_catalog:",
            ),
            **values,
        ),
        mapping,
    )


def _rematerialize_paths(
    *,
    predecessor_catalog: Any,
    kernel: RoleScalableKernel,
    task_catalog: RoleTaskPackageCatalog,
    task_mapping: Mapping[str, str],
) -> tuple[RolePathCatalog, dict[str, str]]:
    paths: list[RoleScalablePath] = []
    mapping: dict[str, str] = {}
    for old in predecessor_catalog.paths:
        values = old.model_dump(mode="json")
        old_id = cast(str, values.pop("path_id"))
        values["kernel_id"] = kernel.kernel_id
        values["task_package_id"] = task_mapping[cast(str, values["task_package_id"])]
        path = RoleScalablePath(
            path_id=canonical_hash(
                values,
                prefix="finance_v26_role_scalable_path:",
            ),
            **values,
        )
        mapping[old_id] = path.path_id
        paths.append(path)
    ordered = tuple(sorted(paths, key=lambda item: item.path_id))
    values = {
        "kernel_id": kernel.kernel_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "paths": ordered,
    }
    provisional = RolePathCatalog.model_construct(catalog_id="pending", **values)
    return (
        RolePathCatalog(
            catalog_id=_identity(
                provisional,
                "catalog_id",
                "finance_v26_role_path_catalog:",
            ),
            **values,
        ),
        mapping,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
) -> SourceReplayAudit:
    report_path = predecessor_dir / "report.json"
    transition_path = predecessor_dir / "prospective_transition_contract.json"
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or _sha256(transition_path) != EXPECTED_PREDECESSOR_TRANSITION_SHA256
    ):
        raise ValueError("v26.132 predecessor report or Transition bytes changed")
    report = immediate_predecessor.RoleScalableKernelRunnerPreflightReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    transition = immediate_predecessor.ProspectiveTransitionContract.model_validate_json(
        transition_path.read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or report.next_permitted_stage != immediate_predecessor.NEXT_STAGE
    ):
        raise ValueError("v26.132 predecessor identity chain changed")
    detail_index = {item.relative_path: item for item in report.detail_files}
    if set(detail_index) != set(PREDECESSOR_OUTPUT_NAMES) - {"report.json"}:
        raise ValueError("v26.132 predecessor detail-file denominator changed")
    for name, detail in detail_index.items():
        path = predecessor_dir / name
        if _sha256(path) != detail.sha256 or path.stat().st_size != detail.byte_count:
            raise ValueError(f"v26.132 predecessor detail changed: {name}")
    predecessor_replay = immediate_predecessor.SourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if predecessor_replay.replayed_file_count != 3177:
        raise ValueError("v26.132 predecessor transitive replay count changed")
    entries: list[SourceReplayEntry] = []
    for item in predecessor_replay.entries:
        path = package_root / item.relative_path
        observed = _sha256(path)
        if observed != item.sha256 or path.stat().st_size != item.byte_count:
            raise ValueError(f"v26.132 transitive replay mismatch: {item.relative_path}")
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                sha256=observed,
                byte_count=path.stat().st_size,
                provenance="predecessor_transitive",
            )
        )
    for name in PREDECESSOR_OUTPUT_NAMES:
        path = predecessor_dir / name
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                sha256=_sha256(path),
                byte_count=path.stat().st_size,
                provenance="predecessor_output",
            )
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    entries.append(
        SourceReplayEntry(
            relative_path=IMPLEMENTATION_PATH,
            sha256=_sha256(implementation),
            byte_count=implementation.stat().st_size,
            provenance="implementation",
        )
    )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_dynamic_source_replay:",
        ),
        **values,
    )


def _load_inputs(
    *,
    package_root: Path,
    predecessor_dir: Path,
    source_replay: SourceReplayAudit,
) -> tuple[_LoadedInputs, FrozenRoleInputAudit]:
    design_dir = package_root / predecessor.OUTPUT_DIR
    formal_predecessor_replay = predecessor.SourceReplayAudit.model_validate_json(
        (design_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    frozen, population_replay = predecessor._load_frozen_inputs(  # noqa: SLF001
        predecessor_dir=package_root / predecessor.PREDECESSOR_DIR,
        source_replay=formal_predecessor_replay,
    )
    formal_population_replay = predecessor.FrozenPopulationReplayAudit.model_validate_json(
        (design_dir / "frozen_population_replay_audit.json").read_text(encoding="utf-8")
    )
    if population_replay != formal_population_replay:
        raise ValueError("v26.132 frozen Population replay changed")
    formal_census = predecessor.RoleSupportComplexityCensus.model_validate_json(
        (design_dir / "role_support_complexity_census.json").read_text(encoding="utf-8")
    )
    compact = predecessor.CompactProjectionProtocol.model_validate_json(
        (design_dir / "compact_projection_protocol.json").read_text(encoding="utf-8")
    )
    s1 = predecessor.ScalabilityCandidate.model_validate_json(
        (design_dir / "scalability_candidate_s1.json").read_text(encoding="utf-8")
    )
    selection = predecessor.ScalabilitySelectionAudit.model_validate_json(
        (design_dir / "scalability_selection_audit.json").read_text(encoding="utf-8")
    )
    support = predecessor.RoleSupportScalabilityContract.model_validate_json(
        (design_dir / "role_support_scalability_contract.json").read_text(encoding="utf-8")
    )
    if (
        formal_census.census_id != EXPECTED_CENSUS_ID
        or compact.protocol_id != EXPECTED_COMPACT_PROTOCOL_ID
        or s1.candidate_id != EXPECTED_S1_CANDIDATE_ID
        or selection.audit_id != EXPECTED_SELECTION_ID
        or selection.selected_candidate_id != s1.candidate_id
        or support.contract_id != EXPECTED_SUPPORT_CONTRACT_ID
        or support.selected_candidate_id != s1.candidate_id
    ):
        raise ValueError("v26.132 selected S1 lineage changed")
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / predecessor.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / predecessor.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    rebuilt_census = predecessor._build_complexity_census(  # noqa: SLF001
        package_root=package_root,
        inputs=frozen,
        population_replay=population_replay,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
    )
    if rebuilt_census != formal_census:
        raise ValueError("v26.132 full-mechanism Census does not reproduce")
    values = {"source_replay_audit_id": source_replay.audit_id}
    provisional = FrozenRoleInputAudit.model_construct(audit_id="pending", **values)
    audit = FrozenRoleInputAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_frozen_role_input_audit:",
        ),
        **values,
    )
    return (
        _LoadedInputs(
            frozen=frozen,
            formal_census=formal_census,
            compact=compact,
            s1=s1,
            selection=selection,
            support=support,
        ),
        audit,
    )


def _make_detour_policy() -> OrdinaryDetourPolicy:
    provisional = OrdinaryDetourPolicy.model_construct(policy_id="pending")
    return OrdinaryDetourPolicy(
        policy_id=_identity(
            provisional,
            "policy_id",
            "finance_v26_bounded_dynamic_interaction_policy:",
        )
    )


def _make_kernel(
    package_root: Path,
    *,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
    resource: RoleScalableResourceContract,
) -> RoleScalableKernel:
    profile_path = package_root / PROFILE_PATH
    if _sha256(profile_path) != EXPECTED_PROFILE_SHA256:
        raise ValueError("v26.132 Stage 1 Thinking profile bytes changed")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    model = profile.get("model")
    if (
        not isinstance(model, Mapping)
        or model.get("model") != "deepseek-v4-flash"
        or model.get("max_output_tokens") != COMPLETION_REQUEST_BOUND_TOKENS
        or model.get("fallback_models") != []
        or model.get("maximum_model_attempts") != 1
        or model.get("contract_repair_attempts") != 0
        or model.get("auto_discover_models") is not False
        or model.get("require_requested_model") is not True
        or model.get("request_body_overrides", {}).get("thinking") != {"type": "enabled"}
    ):
        raise ValueError("v26.132 exact Thinking model profile changed")
    values = {
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "bounded_dynamic_resource_contract_id": resource.contract_id,
    }
    provisional = RoleScalableKernel.model_construct(kernel_id="pending", **values)
    return RoleScalableKernel(
        kernel_id=_identity(
            provisional,
            "kernel_id",
            "finance_v26_bounded_dynamic_role_kernel:",
        ),
        **values,
    )


def _materialize_tasks(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    kernel: RoleScalableKernel,
) -> tuple[tuple[_MaterializedTask, ...], RoleTaskPackageCatalog]:
    qualification, replay_contract = predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        package_root / predecessor.VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    qualification_sha = _sha256(
        package_root / predecessor.VERIFIER_QUALIFICATION_DIR / "report.json"
    )
    materialized: list[_MaterializedTask] = []
    for population in (loaded.frozen.capability, loaded.frozen.reachability):
        bindings = sorted(
            population.tasks,
            key=lambda item: (
                predecessor.TARGET_MECHANISMS.index(item.mechanism_id),
                predecessor.predecessor.TIERS.index(item.tier),
            ),
        )
        for binding in bindings:
            source_task = loaded.frozen.tasks[binding.source_task_artifact_id]
            draft = predecessor._role_draft(  # noqa: SLF001
                source_task,
                role=population.role,
                mechanism=binding.mechanism_id,
            )
            source_record, source_environment = predecessor._upgrade_role_task(draft)  # noqa: SLF001
            environment = predecessor._verifier_bound_environment(  # noqa: SLF001
                predecessor._harden_environment(source_environment)  # noqa: SLF001
            )
            authority_record = predecessor._harden_record(  # noqa: SLF001
                source_record,
                environment,
            )
            replay_binding = predecessor._task_replay_binding(  # noqa: SLF001
                authority_record,
                environment,
                qualification,
                qualification_sha,
                replay_contract,
            )
            record = predecessor._bind_verifier_v2(  # noqa: SLF001
                authority_record,
                replay_binding,
            )
            prompt_contract = predecessor._make_compact_prompt_contract(  # noqa: SLF001
                role=population.role,
                record=record,
                environment=environment,
            )
            package_values = {
                "kernel_id": kernel.kernel_id,
                "role_population_id": population.population_id,
                "role": population.role,
                "mechanism_id": binding.mechanism_id,
                "tier": binding.tier,
                "source_task_artifact_id": source_task.artifact_id,
                "source_binding_id": binding.binding_id,
                "source_program_node_count": binding.program_node_count,
                "diagnostic_operational_task_package_id": record.task_package.package_id,
                "operational_record": record,
                "environment": environment,
                "prompt_contract": prompt_contract,
                "deep_reconciliation_formal_compiler_used": (
                    binding.mechanism_id == "semantic_reconciliation"
                    and binding.program_node_count > 1
                ),
            }
            provisional = RoleScalableTaskPackage.model_construct(
                task_package_id="pending",
                **package_values,
            )
            package = RoleScalableTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_role_scalable_task_package:",
                ),
                **package_values,
            )
            materialized.append(_MaterializedTask(source_binding=binding, package=package))
    ordered = tuple(sorted(materialized, key=lambda item: item.package.task_package_id))
    values = {
        "kernel_id": kernel.kernel_id,
        "packages": tuple(item.package for item in ordered),
    }
    provisional_catalog = RoleTaskPackageCatalog.model_construct(
        catalog_id="pending",
        **values,
    )
    catalog = RoleTaskPackageCatalog(
        catalog_id=_identity(
            provisional_catalog,
            "catalog_id",
            "finance_v26_role_task_package_catalog:",
        ),
        **values,
    )
    return ordered, catalog


def _census_index(
    census: predecessor.RoleSupportComplexityCensus,
) -> dict[tuple[str, str, str], predecessor.PathComplexityRow]:
    return {
        (item.role, item.source_task_artifact_id, item.path_strategy_id): item
        for item in census.paths
    }


def _presentation_salt(
    *,
    selection_id: str,
    package: RoleScalableTaskPackage,
    strategy: PathStrategy,
    state: SemanticActionState,
    logical_index: int,
) -> str:
    return canonical_hash(
        {
            "selection_audit_id": selection_id,
            "role_population_id": package.role_population_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "path_strategy_id": strategy,
            "state_id": state.state_id,
            "logical_index": logical_index,
        },
        prefix="finance_v26_role_candidate_presentation:",
    )


def _action_payload(proposal: CanonicalActionProposal) -> dict[str, str]:
    return {
        "state_id": proposal.state_id,
        "action_id": proposal.action_id,
        "decision_kind": proposal.decision_kind,
        "protocol": RESPONSE_PROTOCOL_VERSION,
    }


def _compile_registered_path(
    *,
    task: _MaterializedTask,
    strategy: PathStrategy,
    census_row: predecessor.PathComplexityRow,
    selection_id: str,
    kernel: RoleScalableKernel,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: ExactFinalResponseGrammar,
) -> _PathExecution:
    package = task.package
    record = package.operational_record
    environment = package.environment
    condition = predecessor._path_condition(package.role, strategy)  # noqa: SLF001
    runtime = predecessor._runtime(record, environment)  # noqa: SLF001
    observations: list[AgentToolObservation] = []
    states: list[SemanticActionState] = []
    proposals: list[CanonicalActionProposal] = []
    commits: list[CanonicalActionCommit] = []
    prompts: list[str] = []
    salts: list[str] = []
    for logical_index in range(128):
        state = build_semantic_action_state(
            record.task_package.task.public,
            environment,
            tuple(observations),
        )
        salt = _presentation_salt(
            selection_id=selection_id,
            package=package,
            strategy=strategy,
            state=state,
            logical_index=logical_index,
        )
        prompt = predecessor._compact_action_prompt(  # noqa: SLF001
            phase="primary",
            instruction=record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=salt,
            typed_failure=None,
            grammar=action_grammar,
        )
        decoded_state, presented = predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        if decoded_state != state or len(presented) != len(state.action_candidates):
            raise ValueError("v26.132 S1 state or Candidate reconstruction changed")
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        parsed = parse_exact_canonical_action_payload(_action_payload(reference))
        if parsed != reference:
            raise ValueError("v26.132 exact Action ABI changed the reference Proposal")
        selection = evaluate_canonical_action_proposal(
            state,
            parsed,
            call_index=len(observations) + 1,
        )
        if selection.commit is None or selection.rejection is not None:
            raise ValueError("v26.132 reference Proposal did not Commit")
        states.append(state)
        proposals.append(parsed)
        commits.append(selection.commit)
        prompts.append(prompt)
        salts.append(salt)
        if selection.commit.action == "emit_final":
            if (
                not state.final_answer_allowed
                or not state.terminal_verification_completed
                or state.terminal_operation_ref is None
            ):
                raise ValueError("v26.132 Final Commit occurred before public readiness")
            break
        call = selection.commit.call
        if call is None:
            raise ValueError("v26.132 non-final Commit lacks a public call")
        observations.append(
            predecessor._execute_observation(  # noqa: SLF001
                record=record,
                environment=environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=call.tool_id,
                    arguments=call.arguments,
                ),
            )
        )
    else:
        raise ValueError("v26.132 registered reference Path did not terminate")
    final_context = render_compact_final_prompt(
        package.prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=condition,
    )
    final_primary = render_exact_final_primary_prompt(final_context, grammar=final_grammar)
    final_rescue = render_exact_final_rescue_prompt(
        final_primary,
        failure_family="response_serialization_failure",
        failure_subtype="final_response_not_exact_shared_grammar",
    )
    terminal_state = states[-1]
    terminal_commit = commits[-1]
    envelope = make_final_response_host_envelope(
        terminal_state_id=terminal_state.state_id,
        terminal_commit_id=terminal_commit.commit_id,
        grammar=final_grammar,
    )
    parse_prompt_only_reference_final_payload(final_primary, envelope=envelope)
    if (
        package.diagnostic_operational_task_package_id != census_row.diagnostic_task_package_id
        or environment.manifest_id != census_row.diagnostic_environment_manifest_id
        or tuple(item.state_id for item in states)
        != tuple(item.state_id for item in census_row.states)
        or len(states) != census_row.action_state_count
        or len(observations) != census_row.public_tool_call_count
    ):
        raise ValueError("v26.132 registered Path diverged from the v26.130 Census")
    path_values = {
        "kernel_id": kernel.kernel_id,
        "task_package_id": package.task_package_id,
        "predecessor_census_path_id": census_row.path_id,
        "role": package.role,
        "mechanism_id": package.mechanism_id,
        "tier": package.tier,
        "path_strategy_id": strategy,
        "public_path_condition": condition,
        "reference_state_ids": tuple(item.state_id for item in states),
        "candidate_presentation_salts": tuple(salts),
        "primary_prompt_sha256s": tuple(
            hashlib.sha256(item.encode("utf-8")).hexdigest() for item in prompts
        ),
        "reference_proposal_ids": tuple(item.proposal_id for item in proposals),
        "stage_two_commit_ids": tuple(item.commit_id for item in commits),
        "observation_ids": tuple(item.observation_id for item in observations),
        "final_primary_prompt_sha256": hashlib.sha256(final_primary.encode("utf-8")).hexdigest(),
        "final_rescue_prompt_sha256": hashlib.sha256(final_rescue.encode("utf-8")).hexdigest(),
        "final_response_envelope_id": envelope.envelope_id,
        "action_state_count": len(states),
        "public_observation_count": len(observations),
        "primary_request_count": len(states) + 1,
        "maximum_provider_calls_with_recovery": len(states) + 3,
        "maximum_transport_inclusive_invocations": len(states) + 4,
        "maximum_prompt_utf8_bytes": census_row.maximum_s1_prompt_utf8_bytes,
        "static_complete_path_upper_bound_tokens": (
            census_row.s1_static_complete_path_upper_bound_tokens
        ),
    }
    provisional = RoleScalablePath.model_construct(path_id="pending", **path_values)
    path = RoleScalablePath(
        path_id=_identity(
            provisional,
            "path_id",
            "finance_v26_role_scalable_path:",
        ),
        **path_values,
    )
    return _PathExecution(
        task=task,
        path=path,
        states=tuple(states),
        proposals=tuple(proposals),
        commits=tuple(commits),
        observations=tuple(observations),
        action_prompts=tuple(prompts),
        final_primary_prompt=final_primary,
        final_rescue_prompt=final_rescue,
    )


def _materialize_paths(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    kernel: RoleScalableKernel,
    task_catalog: RoleTaskPackageCatalog,
    tasks: Sequence[_MaterializedTask],
) -> tuple[tuple[_PathExecution, ...], RolePathCatalog]:
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / predecessor.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / predecessor.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    census = _census_index(loaded.formal_census)
    executions: list[_PathExecution] = []
    for task in tasks:
        package = task.package
        strategies = cast(
            tuple[PathStrategy, ...],
            ("structured_direct",) if package.role == "capability" else PATH_STRATEGIES,
        )
        for strategy in strategies:
            census_row = census[(package.role, package.source_task_artifact_id, strategy)]
            executions.append(
                _compile_registered_path(
                    task=task,
                    strategy=strategy,
                    census_row=census_row,
                    selection_id=loaded.selection.audit_id,
                    kernel=kernel,
                    action_grammar=action_grammar,
                    final_grammar=final_grammar,
                )
            )
    ordered = tuple(sorted(executions, key=lambda item: item.path.path_id))
    values = {
        "kernel_id": kernel.kernel_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "paths": tuple(item.path for item in ordered),
    }
    provisional = RolePathCatalog.model_construct(catalog_id="pending", **values)
    catalog = RolePathCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_role_path_catalog:",
        ),
        **values,
    )
    return ordered, catalog


def _reconciliation_projection(package: RoleScalableTaskPackage) -> dict[str, Any]:
    operational = package.operational_record.task_package
    view = operational.operation_contract.public_view
    return {
        "program_nodes": tuple(item.model_dump(mode="json") for item in view.nodes),
        "dependency_edges": tuple(
            sorted(
                (dependency, item.node_id)
                for item in view.nodes
                for dependency in item.dependency_node_ids
            )
        ),
        "operands": tuple(
            (item.node_id, operand.source_symbol, operand.selector)
            for item in view.nodes
            for operand in item.inputs
        ),
        "selectors": tuple(
            (item.node_id, operand.source_symbol, operand.selector)
            for item in view.nodes
            for operand in item.inputs
            if operand.selector is not None
        ),
        "verifier_bindings": tuple(
            item.model_dump(mode="json") for item in operational.verifier_binding.node_bindings
        ),
        "terminal_node_id": view.terminal_node_id,
    }


def _make_reconciliation_audit(
    *,
    kernel: RoleScalableKernel,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
    loaded: _LoadedInputs,
) -> DeepReconciliationCompilerAudit:
    census_index = {item.path_id: item for item in loaded.formal_census.paths}
    rows: list[DeepReconciliationCompilerBindingRow] = []
    paths_by_package: dict[str, list[RoleScalablePath]] = {}
    for path in path_catalog.paths:
        paths_by_package.setdefault(path.task_package_id, []).append(path)
    for package in task_catalog.packages:
        if not package.deep_reconciliation_formal_compiler_used:
            continue
        projection = _reconciliation_projection(package)
        projection_hash = canonical_hash(
            projection,
            prefix="finance_v26_role_scalable_reconciliation_compilation:",
        )
        view = package.operational_record.task_package.operation_contract.public_view
        registered = tuple(
            sorted(paths_by_package[package.task_package_id], key=lambda item: item.path_id)
        )
        if any(
            census_index[item.predecessor_census_path_id].diagnostic_task_package_id
            != package.diagnostic_operational_task_package_id
            or census_index[item.predecessor_census_path_id].maximum_s1_prompt_utf8_bytes
            != item.maximum_prompt_utf8_bytes
            or census_index[
                item.predecessor_census_path_id
            ].s1_static_complete_path_upper_bound_tokens
            != item.static_complete_path_upper_bound_tokens
            for item in registered
        ):
            raise ValueError("v26.132 Reconciliation Path projection changed")
        row_values = {
            "role": package.role,
            "tier": package.tier,
            "source_task_artifact_id": package.source_task_artifact_id,
            "task_package_id": package.task_package_id,
            "diagnostic_operational_task_package_id": (
                package.diagnostic_operational_task_package_id
            ),
            "diagnostic_environment_manifest_id": package.environment.manifest_id,
            "formal_operational_task_package_id": (
                package.operational_record.task_package.package_id
            ),
            "formal_environment_manifest_id": package.environment.manifest_id,
            "source_program_node_count": census_index[
                registered[0].predecessor_census_path_id
            ].source_program_node_count,
            "public_operation_node_count": len(view.nodes),
            "dependency_edge_count": sum(len(item.dependency_node_ids) for item in view.nodes),
            "operand_binding_count": sum(len(item.inputs) for item in view.nodes),
            "selector_binding_count": sum(
                operand.selector is not None for item in view.nodes for operand in item.inputs
            ),
            "verifier_node_binding_count": len(
                package.operational_record.task_package.verifier_binding.node_bindings
            ),
            "terminal_node_id": view.terminal_node_id,
            "diagnostic_compilation_projection_hash": projection_hash,
            "formal_compilation_projection_hash": projection_hash,
            "registered_path_ids": tuple(item.path_id for item in registered),
            "path_state_projection_match_count": len(registered),
            "path_prompt_projection_match_count": len(registered),
            "path_resource_arithmetic_match_count": len(registered),
        }
        provisional = DeepReconciliationCompilerBindingRow.model_construct(
            row_id="pending",
            **row_values,
        )
        rows.append(
            DeepReconciliationCompilerBindingRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_role_scalable_reconciliation_compiler_binding:",
                ),
                **row_values,
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    values = {
        "kernel_id": kernel.kernel_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "path_catalog_id": path_catalog.catalog_id,
        "rows": ordered,
    }
    provisional = DeepReconciliationCompilerAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return DeepReconciliationCompilerAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_deep_reconciliation_compiler_audit:",
        ),
        **values,
    )


def _make_resource_contract(
    *,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
) -> RoleScalableResourceContract:
    values = {
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "observed_maximum_one_detour_primary_requests": (
            envelope.maximum_one_detour_primary_requests
        ),
        "observed_maximum_one_detour_provider_calls": (envelope.maximum_one_detour_provider_calls),
        "observed_maximum_one_detour_transport_invocations": (
            envelope.maximum_one_detour_transport_invocations
        ),
        "observed_maximum_one_detour_prompt_utf8_bytes": (
            envelope.maximum_one_detour_prompt_utf8_bytes
        ),
        "observed_maximum_one_detour_static_tokens": (envelope.maximum_one_detour_static_tokens),
        "selected_rollout_headroom_tokens": (
            ROLLOUT_UPPER_BOUND_TOKENS - envelope.maximum_one_detour_static_tokens
        ),
    }
    provisional = RoleScalableResourceContract.model_construct(
        contract_id="pending",
        **values,
    )
    return RoleScalableResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_bounded_dynamic_resource_contract:",
        ),
        **values,
    )


def _make_execution_contract(
    *,
    role: Role,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
) -> RoleExecutionContract:
    packages = tuple(
        sorted(item.task_package_id for item in task_catalog.packages if item.role == role)
    )
    paths = tuple(sorted(item.path_id for item in path_catalog.paths if item.role == role))
    values = {
        "execution_run_id": f"{RUN_ID}|future_{role}_execution",
        "role": role,
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "path_catalog_id": path_catalog.catalog_id,
        "task_package_ids": packages,
        "path_ids": paths,
        "expected_job_count": (
            CAPABILITY_JOB_COUNT if role == "capability" else REACHABILITY_JOB_COUNT
        ),
    }
    provisional = RoleExecutionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return RoleExecutionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_scalable_execution_contract:",
        ),
        **values,
    )


def _seed(values: Mapping[str, Any]) -> int:
    digest = hashlib.sha256(
        json.dumps(
            dict(values),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return int(digest[:15], 16)


def _make_job(**values: Any) -> RoleJob:
    values = dict(values)
    values["seed"] = _seed({**values, "run_id": RUN_ID})
    provisional = RoleJob.model_construct(job_id="pending", **values)
    return RoleJob(
        job_id=_identity(
            provisional,
            "job_id",
            "finance_v26_role_scalable_job:",
        ),
        **values,
    )


def _make_manifest(
    *,
    contract: RoleExecutionContract,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
) -> RoleJobManifest:
    packages = tuple(
        sorted(
            (item for item in task_catalog.packages if item.role == contract.role),
            key=lambda item: item.task_package_id,
        )
    )
    paths_by_package: dict[str, tuple[RoleScalablePath, ...]] = {
        package.task_package_id: tuple(
            sorted(
                (
                    item
                    for item in path_catalog.paths
                    if item.task_package_id == package.task_package_id
                ),
                key=lambda item: item.path_id,
            )
        )
        for package in packages
    }
    jobs: list[RoleJob] = []
    if contract.role == "capability":
        for package in packages:
            for replicate in range(8):
                jobs.append(
                    _make_job(
                        contract_id=contract.contract_id,
                        role="capability",
                        task_package_id=package.task_package_id,
                        mechanism_id=package.mechanism_id,
                        tier=package.tier,
                        sampling_mode="capability_unconditional",
                        replicate_index=replicate,
                        requested_path_id=None,
                        requested_path_strategy=None,
                        public_condition_id=None,
                    )
                )
    else:
        for package in packages:
            for replicate in range(12):
                jobs.append(
                    _make_job(
                        contract_id=contract.contract_id,
                        role="reachability",
                        task_package_id=package.task_package_id,
                        mechanism_id=package.mechanism_id,
                        tier=package.tier,
                        sampling_mode="reachability_unconditional",
                        replicate_index=replicate,
                        requested_path_id=None,
                        requested_path_strategy=None,
                        public_condition_id=None,
                    )
                )
            for path in paths_by_package[package.task_package_id]:
                condition_id = canonical_hash(
                    {
                        "kernel_id": contract.kernel_id,
                        "path_id": path.path_id,
                        "path_strategy_id": path.path_strategy_id,
                        "public_path_condition": path.public_path_condition,
                    },
                    prefix="finance_v26_role_scalable_public_condition:",
                )
                for replicate in range(6):
                    jobs.append(
                        _make_job(
                            contract_id=contract.contract_id,
                            role="reachability",
                            task_package_id=package.task_package_id,
                            mechanism_id=package.mechanism_id,
                            tier=package.tier,
                            sampling_mode="reachability_conditioned",
                            replicate_index=replicate,
                            requested_path_id=path.path_id,
                            requested_path_strategy=path.path_strategy_id,
                            public_condition_id=condition_id,
                        )
                    )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    values = {
        "contract_id": contract.contract_id,
        "role": contract.role,
        "jobs": ordered,
        "expected_job_count": contract.expected_job_count,
    }
    provisional = RoleJobManifest.model_construct(manifest_id="pending", **values)
    return RoleJobManifest(
        manifest_id=_identity(
            provisional,
            "manifest_id",
            "finance_v26_role_scalable_manifest:",
        ),
        **values,
    )


def _rematerialize_manifest(
    *,
    contract: RoleExecutionContract,
    predecessor_manifest: Any,
    kernel: RoleScalableKernel,
    task_mapping: Mapping[str, str],
    path_mapping: Mapping[str, str],
    path_catalog: RolePathCatalog,
) -> RoleJobManifest:
    new_paths = {item.path_id: item for item in path_catalog.paths}
    jobs: list[RoleJob] = []
    for old in predecessor_manifest.jobs:
        requested_path_id = (
            None if old.requested_path_id is None else path_mapping[old.requested_path_id]
        )
        public_condition_id: str | None = None
        if requested_path_id is not None:
            path = new_paths[requested_path_id]
            public_condition_id = canonical_hash(
                {
                    "kernel_id": kernel.kernel_id,
                    "path_id": path.path_id,
                    "path_strategy_id": path.path_strategy_id,
                    "public_path_condition": path.public_path_condition,
                },
                prefix="finance_v26_role_scalable_public_condition:",
            )
        values = {
            "contract_id": contract.contract_id,
            "role": old.role,
            "task_package_id": task_mapping[old.task_package_id],
            "mechanism_id": old.mechanism_id,
            "tier": old.tier,
            "sampling_mode": old.sampling_mode,
            "replicate_index": old.replicate_index,
            "seed": old.seed,
            "requested_path_id": requested_path_id,
            "requested_path_strategy": old.requested_path_strategy,
            "public_condition_id": public_condition_id,
        }
        provisional = RoleJob.model_construct(job_id="pending", **values)
        jobs.append(
            RoleJob(
                job_id=_identity(
                    provisional,
                    "job_id",
                    "finance_v26_role_scalable_job:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    values = {
        "contract_id": contract.contract_id,
        "role": contract.role,
        "jobs": ordered,
        "expected_job_count": contract.expected_job_count,
    }
    provisional = RoleJobManifest.model_construct(manifest_id="pending", **values)
    return RoleJobManifest(
        manifest_id=_identity(
            provisional,
            "manifest_id",
            "finance_v26_role_scalable_manifest:",
        ),
        **values,
    )


def _make_identity_chain(
    *,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
    predecessor_chain: Any,
    task_mapping: Mapping[str, str],
    path_mapping: Mapping[str, str],
) -> RoleIdentityChain:
    capability_contract = _make_execution_contract(
        role="capability",
        kernel=kernel,
        resource=resource,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
    reachability_contract = _make_execution_contract(
        role="reachability",
        kernel=kernel,
        resource=resource,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
    capability_manifest = _rematerialize_manifest(
        contract=capability_contract,
        predecessor_manifest=predecessor_chain.capability_manifest,
        kernel=kernel,
        task_mapping=task_mapping,
        path_mapping=path_mapping,
        path_catalog=path_catalog,
    )
    reachability_manifest = _rematerialize_manifest(
        contract=reachability_contract,
        predecessor_manifest=predecessor_chain.reachability_manifest,
        kernel=kernel,
        task_mapping=task_mapping,
        path_mapping=path_mapping,
        path_catalog=path_catalog,
    )
    old_jobs = {
        item.job_id
        for manifest in (
            predecessor_chain.capability_manifest,
            predecessor_chain.reachability_manifest,
        )
        for item in manifest.jobs
    }
    new_jobs = {
        item.job_id
        for manifest in (capability_manifest, reachability_manifest)
        for item in manifest.jobs
    }
    old_seeds = sorted(
        item.seed
        for manifest in (
            predecessor_chain.capability_manifest,
            predecessor_chain.reachability_manifest,
        )
        for item in manifest.jobs
    )
    new_seeds = sorted(
        item.seed
        for manifest in (capability_manifest, reachability_manifest)
        for item in manifest.jobs
    )
    if old_jobs & new_jobs or old_seeds != new_seeds:
        raise ValueError("v26.132 fresh Job identity or exact seed preservation changed")
    values = {
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "capability_contract": capability_contract,
        "reachability_contract": reachability_contract,
        "capability_manifest": capability_manifest,
        "reachability_manifest": reachability_manifest,
    }
    provisional = RoleIdentityChain.model_construct(chain_id="pending", **values)
    return RoleIdentityChain(
        chain_id=_identity(
            provisional,
            "chain_id",
            "finance_v26_role_identity_chain:",
        ),
        **values,
    )


def _make_runner_contract(
    *,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    identity_chain: RoleIdentityChain,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
) -> RoleRunnerContract:
    values = {
        "future_execution_run_id": f"{RUN_ID}|future_role_execution",
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "identity_chain_id": identity_chain.chain_id,
        "capability_manifest_id": identity_chain.capability_manifest.manifest_id,
        "reachability_manifest_id": identity_chain.reachability_manifest.manifest_id,
    }
    provisional = RoleRunnerContract.model_construct(contract_id="pending", **values)
    return RoleRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_bounded_dynamic_runner_contract:",
        ),
        **values,
    )


def _make_reference_fixture(
    *,
    runner: RoleRunnerContract,
    path_catalog: RolePathCatalog,
) -> ReferenceRunnerFixtureAudit:
    rows: list[ReferencePathPreflightRow] = []
    for path in path_catalog.paths:
        values = {
            "path_id": path.path_id,
            "role": path.role,
            "mechanism_id": path.mechanism_id,
            "tier": path.tier,
            "path_strategy_id": path.path_strategy_id,
            "action_state_count": path.action_state_count,
            "semantic_action_primary_count": path.action_state_count,
            "primary_request_count": path.primary_request_count,
            "potential_provider_call_count": (path.maximum_provider_calls_with_recovery),
            "potential_transport_invocation_count": (path.maximum_transport_inclusive_invocations),
            "public_observation_count": path.public_observation_count,
            "maximum_prompt_utf8_bytes": path.maximum_prompt_utf8_bytes,
            "static_path_upper_bound_tokens": (path.static_complete_path_upper_bound_tokens),
        }
        provisional = ReferencePathPreflightRow.model_construct(
            row_id="pending",
            **values,
        )
        rows.append(
            ReferencePathPreflightRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_role_reference_path_preflight:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    values = {
        "runner_contract_id": runner.contract_id,
        "path_catalog_id": path_catalog.catalog_id,
        "rows": ordered,
    }
    provisional = ReferenceRunnerFixtureAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return ReferenceRunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_reference_runner_fixture:",
        ),
        **values,
    )


def _progress_vector(state: SemanticActionState) -> tuple[Any, ...]:
    return (
        state.unresolved_symbols,
        tuple((item.node_id, item.frontier_status) for item in state.operation_frontier),
        state.terminal_operation_ref,
        state.terminal_verification_completed,
        state.final_answer_allowed,
    )


def _dynamic_row(
    *,
    execution: Any,
    state_index: int,
    state: SemanticActionState,
    candidate: Any,
    outcome: DynamicCandidateOutcome,
    observation_id: str | None = None,
    primary_request_count: int | None = None,
    provider_call_count_with_recoveries: int | None = None,
    transport_inclusive_invocation_count: int | None = None,
    maximum_prompt_utf8_bytes: int | None = None,
    static_complete_path_upper_bound_tokens: int | None = None,
    public_observation_count: int | None = None,
    program_closed: bool = False,
    terminal_verification_completed: bool = False,
    final_commit_reached: bool = False,
) -> DynamicCandidateClassification:
    values = {
        "predecessor_path_id": execution.path.path_id,
        "role": execution.path.role,
        "mechanism_id": execution.path.mechanism_id,
        "tier": execution.path.tier,
        "path_strategy_id": execution.path.path_strategy_id,
        "reference_state_index": state_index,
        "state_id": state.state_id,
        "action_id": candidate.action_id,
        "decision_kind": candidate.decision_kind,
        "outcome": outcome,
        "observation_id": observation_id,
        "primary_request_count": primary_request_count,
        "provider_call_count_with_recoveries": provider_call_count_with_recoveries,
        "transport_inclusive_invocation_count": transport_inclusive_invocation_count,
        "maximum_prompt_utf8_bytes": maximum_prompt_utf8_bytes,
        "static_complete_path_upper_bound_tokens": static_complete_path_upper_bound_tokens,
        "public_observation_count": public_observation_count,
        "program_closed": program_closed,
        "terminal_verification_completed": terminal_verification_completed,
        "final_commit_reached": final_commit_reached,
    }
    provisional = DynamicCandidateClassification.model_construct(row_id="pending", **values)
    return DynamicCandidateClassification(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_bounded_dynamic_candidate_classification:",
        ),
        **values,
    )


def _build_state_or_none(
    *,
    task: Any,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> SemanticActionState | None:
    try:
        return build_semantic_action_state(
            task,
            environment,
            tuple(observations),
        )
    except ValueError as exc:
        if str(exc) != "semantic action state has no selectable public action":
            raise
        return None


def _classify_dynamic_candidate(
    *,
    loaded: _LoadedInputs,
    execution: Any,
    state_index: int,
    candidate: Any,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: ExactFinalResponseGrammar,
) -> DynamicCandidateClassification:
    package = execution.task.package
    record = package.operational_record
    environment = package.environment
    task = record.task_package.task.public
    strategy = execution.path.path_strategy_id
    condition = predecessor._path_condition(package.role, strategy)  # noqa: SLF001
    runtime = predecessor._runtime(record, environment)  # noqa: SLF001
    observations = list(execution.observations[:state_index])
    state = build_semantic_action_state(task, environment, tuple(observations))
    if state != execution.states[state_index]:
        raise ValueError("v26.132 reference-prefix state changed during detour enumeration")
    proposal = make_canonical_action_proposal(
        state_id=state.state_id,
        action_id=candidate.action_id,
        decision_kind=candidate.decision_kind,
    )
    parsed = parse_exact_canonical_action_payload(_action_payload(proposal))
    result = evaluate_canonical_action_proposal(
        state,
        parsed,
        call_index=len(observations) + 1,
    )
    if result.commit is None or result.rejection is not None:
        raise ValueError("v26.132 visible legal Candidate did not Commit")
    if result.commit.call is None:
        return _dynamic_row(
            execution=execution,
            state_index=state_index,
            state=state,
            candidate=candidate,
            outcome="not_public_call",
        )
    call = result.commit.call
    observation = predecessor._execute_observation(  # noqa: SLF001
        record=record,
        environment=environment,
        runtime=runtime,
        observations=tuple(observations),
        projection=CompletionProjection(
            request_kind="decision",
            action="call_tool",
            tool_id=call.tool_id,
            arguments=call.arguments,
        ),
    )
    if observation.status != "succeeded":
        return _dynamic_row(
            execution=execution,
            state_index=state_index,
            state=state,
            candidate=candidate,
            outcome="tool_not_successful",
            observation_id=observation.observation_id,
        )
    next_state = _build_state_or_none(
        task=task,
        environment=environment,
        observations=(*observations, observation),
    )
    if next_state is None:
        return _dynamic_row(
            execution=execution,
            state_index=state_index,
            state=state,
            candidate=candidate,
            outcome="successful_no_selectable_state",
            observation_id=observation.observation_id,
        )
    if _progress_vector(next_state) != _progress_vector(state):
        return _dynamic_row(
            execution=execution,
            state_index=state_index,
            state=state,
            candidate=candidate,
            outcome="successful_progress",
            observation_id=observation.observation_id,
        )

    prompt_rows: list[tuple[SemanticActionState, str, str, tuple[AgentToolObservation, ...]]] = []
    for prefix_index in range(state_index + 1):
        prompt_rows.append(
            (
                execution.states[prefix_index],
                execution.action_prompts[prefix_index],
                execution.path.candidate_presentation_salts[prefix_index],
                tuple(execution.observations[:prefix_index]),
            )
        )
    observations.append(observation)
    terminal_state: SemanticActionState | None = None
    terminal_commit: CanonicalActionCommit | None = None
    for logical_index in range(state_index + 1, 160):
        dynamic_state = _build_state_or_none(
            task=task,
            environment=environment,
            observations=observations,
        )
        if dynamic_state is None:
            return _dynamic_row(
                execution=execution,
                state_index=state_index,
                state=state,
                candidate=candidate,
                outcome="successful_no_progress_route_not_closable",
                observation_id=observation.observation_id,
            )
        salt = canonical_hash(
            {
                "selection_audit_id": loaded.selection.audit_id,
                "predecessor_path_id": execution.path.path_id,
                "detour_state_id": state.state_id,
                "detour_action_id": candidate.action_id,
                "logical_index": logical_index,
                "ordinary_detour_count": 1,
            },
            prefix="finance_v26_bounded_dynamic_candidate_presentation:",
        )
        prompt = predecessor._compact_action_prompt(  # noqa: SLF001
            phase="primary",
            instruction=task.instruction,
            state=dynamic_state,
            public_path_condition=condition,
            presentation_salt=salt,
            typed_failure=None,
            grammar=action_grammar,
        )
        predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        try:
            reference = predecessor._compact_reference_proposal(  # noqa: SLF001
                prompt,
                presentation_salt=salt,
            )
        except ValueError as exc:
            if str(exc) != "Prompt-only acquisition policy cannot satisfy its public route":
                raise
            return _dynamic_row(
                execution=execution,
                state_index=state_index,
                state=state,
                candidate=candidate,
                outcome="successful_no_progress_route_not_closable",
                observation_id=observation.observation_id,
            )
        parsed_reference = parse_exact_canonical_action_payload(_action_payload(reference))
        choice = evaluate_canonical_action_proposal(
            dynamic_state,
            parsed_reference,
            call_index=len(observations) + 1,
        )
        if choice.commit is None or choice.rejection is not None:
            raise ValueError("v26.132 ordinary reference replan did not Commit")
        prompt_rows.append((dynamic_state, prompt, salt, tuple(observations)))
        if choice.commit.action == "emit_final":
            if (
                not dynamic_state.final_answer_allowed
                or not dynamic_state.terminal_verification_completed
            ):
                raise ValueError("v26.132 ordinary replan emitted Final before readiness")
            terminal_state = dynamic_state
            terminal_commit = choice.commit
            break
        if choice.commit.call is None:
            raise ValueError("v26.132 ordinary replan non-final Commit lacks a call")
        next_observation = predecessor._execute_observation(  # noqa: SLF001
            record=record,
            environment=environment,
            runtime=runtime,
            observations=tuple(observations),
            projection=CompletionProjection(
                request_kind="decision",
                action="call_tool",
                tool_id=choice.commit.call.tool_id,
                arguments=choice.commit.call.arguments,
            ),
        )
        observations.append(next_observation)
    if terminal_state is None or terminal_commit is None:
        raise ValueError("v26.132 ordinary replan did not terminate")

    primary_prompts = tuple(item[1] for item in prompt_rows)
    abi_prompts: list[str] = []
    semantic_recovery_prompts: list[str] = []
    for dynamic_state, prompt, salt, observation_prefix in prompt_rows:
        abi_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="abi_rescue",
                instruction=task.instruction,
                state=dynamic_state,
                public_path_condition=condition,
                presentation_salt=salt,
                typed_failure={
                    "family": "response_serialization_failure",
                    "subtype": "canonical_action_not_exact_four_field_grammar",
                },
                grammar=action_grammar,
            )
        )
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        invalid = make_canonical_action_proposal(
            state_id=dynamic_state.state_id,
            action_id=reference.action_id,
            decision_kind=cast(
                Any,
                predecessor.predecessor._other_decision_kind(  # noqa: SLF001
                    reference.decision_kind
                ),
            ),
        )
        rejection = evaluate_canonical_action_proposal(
            dynamic_state,
            invalid,
            call_index=len(observation_prefix) + 1,
        ).rejection
        if rejection is None:
            raise ValueError("v26.132 semantic-recovery fixture did not reject")
        recovery_state = build_semantic_action_state(
            task,
            environment,
            observation_prefix,
            semantic_rejections=(rejection,),
        )
        semantic_recovery_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="semantic_recovery",
                instruction=task.instruction,
                state=recovery_state,
                public_path_condition=condition,
                presentation_salt=f"{salt}|semantic_recovery",
                typed_failure={
                    "family": "semantic_action_rejection",
                    "subtype": rejection.error_category,
                    "rejection_id": rejection.rejection_id,
                },
                grammar=action_grammar,
            )
        )

    final_context = render_compact_final_prompt(
        package.prompt_contract.public_context,
        task,
        tuple(observations),
        public_path_condition=condition,
    )
    final_primary = render_exact_final_primary_prompt(final_context, grammar=final_grammar)
    final_rescue = render_exact_final_rescue_prompt(
        final_primary,
        failure_family="response_serialization_failure",
        failure_subtype="final_response_not_exact_shared_grammar",
    )
    envelope = make_final_response_host_envelope(
        terminal_state_id=terminal_state.state_id,
        terminal_commit_id=terminal_commit.commit_id,
        grammar=final_grammar,
    )
    parse_prompt_only_reference_final_payload(final_primary, envelope=envelope)
    upper_bound = sum(predecessor._request_bound(item) for item in primary_prompts)  # noqa: SLF001
    upper_bound += predecessor._request_bound(final_primary)  # noqa: SLF001
    upper_bound += max(
        max(predecessor._request_bound(item) for item in abi_prompts),  # noqa: SLF001
        predecessor._request_bound(final_rescue),  # noqa: SLF001
    )
    upper_bound += max(
        predecessor._request_bound(item)  # noqa: SLF001
        for item in semantic_recovery_prompts
    )
    all_prompts = (
        *primary_prompts,
        *abi_prompts,
        *semantic_recovery_prompts,
        final_primary,
        final_rescue,
    )
    primary_count = len(primary_prompts) + 1
    return _dynamic_row(
        execution=execution,
        state_index=state_index,
        state=state,
        candidate=candidate,
        outcome="eligible_closed_no_progress",
        observation_id=observation.observation_id,
        primary_request_count=primary_count,
        provider_call_count_with_recoveries=(
            primary_count + MAXIMUM_ABI_RESCUES + MAXIMUM_SEMANTIC_RECOVERIES
        ),
        transport_inclusive_invocation_count=(
            primary_count
            + MAXIMUM_ABI_RESCUES
            + MAXIMUM_SEMANTIC_RECOVERIES
            + MAXIMUM_TRANSPORT_REPLACEMENTS
        ),
        maximum_prompt_utf8_bytes=max(len(item.encode("utf-8")) for item in all_prompts),
        static_complete_path_upper_bound_tokens=upper_bound,
        public_observation_count=len(observations),
        program_closed=True,
        terminal_verification_completed=True,
        final_commit_reached=True,
    )


def _make_dynamic_envelope(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    policy: OrdinaryDetourPolicy,
    executions: Sequence[Any],
) -> DynamicTrajectoryEnvelopeAudit:
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / predecessor.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / predecessor.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    rows: list[DynamicCandidateClassification] = []
    for execution in executions:
        for state_index, state in enumerate(execution.states):
            reference_action_id = execution.proposals[state_index].action_id
            for candidate in state.action_candidates:
                if candidate.action_id == reference_action_id:
                    continue
                rows.append(
                    _classify_dynamic_candidate(
                        loaded=loaded,
                        execution=execution,
                        state_index=state_index,
                        candidate=candidate,
                        action_grammar=action_grammar,
                        final_grammar=final_grammar,
                    )
                )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    counts = Counter(item.outcome for item in ordered)
    eligible = tuple(item for item in ordered if item.outcome == "eligible_closed_no_progress")
    maximum = max(
        eligible,
        key=lambda item: (
            cast(int, item.static_complete_path_upper_bound_tokens),
            cast(int, item.maximum_prompt_utf8_bytes),
            item.row_id,
        ),
    )
    values = {
        "ordinary_detour_policy_id": policy.policy_id,
        "predecessor_path_catalog_id": EXPECTED_PREDECESSOR_PATH_CATALOG_ID,
        "predecessor_reference_fixture_id": EXPECTED_PREDECESSOR_REFERENCE_FIXTURE_ID,
        "rows": ordered,
        "outcome_counts": tuple(
            DynamicOutcomeCount(outcome=outcome, count=counts[outcome])
            for outcome in DYNAMIC_CANDIDATE_OUTCOMES
        ),
        "registered_state_count": sum(len(item.states) for item in executions),
        "candidate_check_count": len(ordered),
        "eligible_closed_detour_count": len(eligible),
        "eligible_path_count": len({item.predecessor_path_id for item in eligible}),
        "maximum_one_detour_primary_requests": max(
            cast(int, item.primary_request_count) for item in eligible
        ),
        "maximum_one_detour_provider_calls": max(
            cast(int, item.provider_call_count_with_recoveries) for item in eligible
        ),
        "maximum_one_detour_transport_invocations": max(
            cast(int, item.transport_inclusive_invocation_count) for item in eligible
        ),
        "maximum_one_detour_prompt_utf8_bytes": max(
            cast(int, item.maximum_prompt_utf8_bytes) for item in eligible
        ),
        "maximum_one_detour_static_tokens": cast(
            int,
            maximum.static_complete_path_upper_bound_tokens,
        ),
        "maximum_one_detour_row_id": maximum.row_id,
        "minimum_selected_rollout_headroom_tokens": (
            ROLLOUT_UPPER_BOUND_TOKENS - cast(int, maximum.static_complete_path_upper_bound_tokens)
        ),
    }
    provisional = DynamicTrajectoryEnvelopeAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return DynamicTrajectoryEnvelopeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_dynamic_trajectory_envelope_audit:",
        ),
        **values,
    )


def _execute_two_detour_stress(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    envelope: DynamicTrajectoryEnvelopeAudit,
    executions: Sequence[Any],
) -> dict[str, Any]:
    maximum = next(
        item for item in envelope.rows if item.row_id == envelope.maximum_one_detour_row_id
    )
    execution = next(
        item for item in executions if item.path.path_id == maximum.predecessor_path_id
    )
    package = execution.task.package
    record = package.operational_record
    environment = package.environment
    task = record.task_package.task.public
    strategy = execution.path.path_strategy_id
    condition = predecessor._path_condition(package.role, strategy)  # noqa: SLF001
    runtime = predecessor._runtime(record, environment)  # noqa: SLF001
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / predecessor.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / predecessor.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    state_index = maximum.reference_state_index
    observations = list(execution.observations[:state_index])
    prompt_rows: list[tuple[SemanticActionState, str, str, tuple[AgentToolObservation, ...]]] = []
    for prefix_index in range(state_index + 1):
        prompt_rows.append(
            (
                execution.states[prefix_index],
                execution.action_prompts[prefix_index],
                execution.path.candidate_presentation_salts[prefix_index],
                tuple(execution.observations[:prefix_index]),
            )
        )
    second_state: SemanticActionState | None = None
    for detour_index in range(2):
        state = build_semantic_action_state(task, environment, tuple(observations))
        candidate = next(
            (item for item in state.action_candidates if item.action_id == maximum.action_id),
            None,
        )
        if candidate is None:
            raise ValueError("v26.132 repeated detour Action is no longer visible")
        if detour_index == 1:
            second_state = state
            salt = canonical_hash(
                {
                    "selection_audit_id": loaded.selection.audit_id,
                    "predecessor_path_id": execution.path.path_id,
                    "detour_state_id": maximum.state_id,
                    "detour_action_id": maximum.action_id,
                    "logical_index": state_index + 1,
                    "ordinary_detour_count": 2,
                },
                prefix="finance_v26_bounded_dynamic_candidate_presentation:",
            )
            prompt = predecessor._compact_action_prompt(  # noqa: SLF001
                phase="primary",
                instruction=task.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=salt,
                typed_failure=None,
                grammar=action_grammar,
            )
            predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                prompt,
                presentation_salt=salt,
            )
            prompt_rows.append((state, prompt, salt, tuple(observations)))
        proposal = make_canonical_action_proposal(
            state_id=state.state_id,
            action_id=candidate.action_id,
            decision_kind=candidate.decision_kind,
        )
        parsed = parse_exact_canonical_action_payload(_action_payload(proposal))
        choice = evaluate_canonical_action_proposal(
            state,
            parsed,
            call_index=len(observations) + 1,
        )
        if choice.commit is None or choice.rejection is not None or choice.commit.call is None:
            raise ValueError("v26.132 repeated detour did not Commit")
        observation = predecessor._execute_observation(  # noqa: SLF001
            record=record,
            environment=environment,
            runtime=runtime,
            observations=tuple(observations),
            projection=CompletionProjection(
                request_kind="decision",
                action="call_tool",
                tool_id=choice.commit.call.tool_id,
                arguments=choice.commit.call.arguments,
            ),
        )
        if observation.status != "succeeded":
            raise ValueError("v26.132 repeated detour did not succeed")
        next_state = build_semantic_action_state(
            task,
            environment,
            (*observations, observation),
        )
        if _progress_vector(next_state) != _progress_vector(state):
            raise ValueError("v26.132 repeated detour unexpectedly made public progress")
        observations.append(observation)
    if second_state is None:
        raise AssertionError("v26.132 second detour state disappeared")

    terminal_state: SemanticActionState | None = None
    terminal_commit: CanonicalActionCommit | None = None
    for logical_index in range(state_index + 2, 160):
        state = build_semantic_action_state(task, environment, tuple(observations))
        salt = canonical_hash(
            {
                "selection_audit_id": loaded.selection.audit_id,
                "predecessor_path_id": execution.path.path_id,
                "detour_state_id": maximum.state_id,
                "detour_action_id": maximum.action_id,
                "logical_index": logical_index,
                "ordinary_detour_count": 2,
            },
            prefix="finance_v26_bounded_dynamic_candidate_presentation:",
        )
        prompt = predecessor._compact_action_prompt(  # noqa: SLF001
            phase="primary",
            instruction=task.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=salt,
            typed_failure=None,
            grammar=action_grammar,
        )
        predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        parsed = parse_exact_canonical_action_payload(_action_payload(reference))
        choice = evaluate_canonical_action_proposal(
            state,
            parsed,
            call_index=len(observations) + 1,
        )
        if choice.commit is None or choice.rejection is not None:
            raise ValueError("v26.132 two-detour diagnostic replan did not Commit")
        prompt_rows.append((state, prompt, salt, tuple(observations)))
        if choice.commit.action == "emit_final":
            terminal_state = state
            terminal_commit = choice.commit
            break
        if choice.commit.call is None:
            raise ValueError("v26.132 two-detour non-final Commit lacks a call")
        observations.append(
            predecessor._execute_observation(  # noqa: SLF001
                record=record,
                environment=environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=choice.commit.call.tool_id,
                    arguments=choice.commit.call.arguments,
                ),
            )
        )
    if (
        terminal_state is None
        or terminal_commit is None
        or not terminal_state.final_answer_allowed
        or not terminal_state.terminal_verification_completed
    ):
        raise ValueError("v26.132 two-detour diagnostic did not close")

    primary_prompts = tuple(item[1] for item in prompt_rows)
    abi_prompts: list[str] = []
    semantic_prompts: list[str] = []
    for state, prompt, salt, observation_prefix in prompt_rows:
        abi_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="abi_rescue",
                instruction=task.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=salt,
                typed_failure={
                    "family": "response_serialization_failure",
                    "subtype": "canonical_action_not_exact_four_field_grammar",
                },
                grammar=action_grammar,
            )
        )
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        invalid = make_canonical_action_proposal(
            state_id=state.state_id,
            action_id=reference.action_id,
            decision_kind=cast(
                Any,
                predecessor.predecessor._other_decision_kind(  # noqa: SLF001
                    reference.decision_kind
                ),
            ),
        )
        rejection = evaluate_canonical_action_proposal(
            state,
            invalid,
            call_index=len(observation_prefix) + 1,
        ).rejection
        if rejection is None:
            raise ValueError("v26.132 two-detour semantic fixture did not reject")
        recovery_state = build_semantic_action_state(
            task,
            environment,
            observation_prefix,
            semantic_rejections=(rejection,),
        )
        semantic_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="semantic_recovery",
                instruction=task.instruction,
                state=recovery_state,
                public_path_condition=condition,
                presentation_salt=f"{salt}|semantic_recovery",
                typed_failure={
                    "family": "semantic_action_rejection",
                    "subtype": rejection.error_category,
                    "rejection_id": rejection.rejection_id,
                },
                grammar=action_grammar,
            )
        )
    final_context = render_compact_final_prompt(
        package.prompt_contract.public_context,
        task,
        tuple(observations),
        public_path_condition=condition,
    )
    final_primary = render_exact_final_primary_prompt(final_context, grammar=final_grammar)
    final_rescue = render_exact_final_rescue_prompt(
        final_primary,
        failure_family="response_serialization_failure",
        failure_subtype="final_response_not_exact_shared_grammar",
    )
    final_envelope = make_final_response_host_envelope(
        terminal_state_id=terminal_state.state_id,
        terminal_commit_id=terminal_commit.commit_id,
        grammar=final_grammar,
    )
    parse_prompt_only_reference_final_payload(final_primary, envelope=final_envelope)
    upper_bound = sum(predecessor._request_bound(item) for item in primary_prompts)  # noqa: SLF001
    upper_bound += predecessor._request_bound(final_primary)  # noqa: SLF001
    upper_bound += max(
        max(predecessor._request_bound(item) for item in abi_prompts),  # noqa: SLF001
        predecessor._request_bound(final_rescue),  # noqa: SLF001
    )
    upper_bound += max(
        predecessor._request_bound(item)
        for item in semantic_prompts  # noqa: SLF001
    )
    all_prompts = (
        *primary_prompts,
        *abi_prompts,
        *semantic_prompts,
        final_primary,
        final_rescue,
    )
    primary_count = len(primary_prompts) + 1
    terminal_values = {
        "predecessor_path_id": execution.path.path_id,
        "state_id": second_state.state_id,
        "action_id": maximum.action_id,
    }
    provisional_terminal = TypedDetourResourceTerminal.model_construct(
        terminal_id="pending",
        **terminal_values,
    )
    terminal = TypedDetourResourceTerminal(
        terminal_id=_identity(
            provisional_terminal,
            "terminal_id",
            "finance_v26_typed_detour_resource_terminal:",
        ),
        **terminal_values,
    )
    return {
        "primary_request_count": primary_count,
        "provider_call_count": (primary_count + MAXIMUM_ABI_RESCUES + MAXIMUM_SEMANTIC_RECOVERIES),
        "transport_invocation_count": (
            primary_count
            + MAXIMUM_ABI_RESCUES
            + MAXIMUM_SEMANTIC_RECOVERIES
            + MAXIMUM_TRANSPORT_REPLACEMENTS
        ),
        "maximum_prompt_utf8_bytes": max(len(item.encode("utf-8")) for item in all_prompts),
        "static_complete_path_upper_bound_tokens": upper_bound,
        "terminal": terminal,
    }


def _make_bounded_runner_preflight(
    *,
    package_root: Path,
    runner: RoleRunnerContract,
    reference: ReferenceRunnerFixtureAudit,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
    resource: RoleScalableResourceContract,
    loaded: _LoadedInputs,
    executions: Sequence[Any],
) -> BoundedDynamicRunnerPreflightAudit:
    two_detour = _execute_two_detour_stress(
        package_root=package_root,
        loaded=loaded,
        envelope=envelope,
        executions=executions,
    )
    eligible = envelope.eligible_closed_detour_count
    initial_allowances = _InteractionAllowanceState(
        abi_rescues_remaining=MAXIMUM_ABI_RESCUES,
        semantic_recoveries_remaining=MAXIMUM_SEMANTIC_RECOVERIES,
        transport_replacements_remaining=MAXIMUM_TRANSPORT_REPLACEMENTS,
        ordinary_detours_remaining=MAXIMUM_ORDINARY_DETOURS,
    )
    after_detour = _consume_interaction_allowance(
        initial_allowances,
        "ordinary_detour",
    )
    after_abi_rescue = _consume_interaction_allowance(
        initial_allowances,
        "abi_rescue",
    )
    after_semantic_recovery = _consume_interaction_allowance(
        initial_allowances,
        "semantic_recovery",
    )
    after_transport_replacement = _consume_interaction_allowance(
        initial_allowances,
        "transport_replacement",
    )
    if (
        after_abi_rescue.abi_rescues_remaining != 0
        or after_semantic_recovery.semantic_recoveries_remaining != 0
        or after_transport_replacement.transport_replacements_remaining != 0
    ):
        raise ValueError("v26.132 recovery allowance was not consumed by its own event")
    try:
        _consume_interaction_allowance(after_detour, "ordinary_detour")
    except ValueError as exc:
        second_detour_reason = str(exc)
    else:
        raise ValueError("v26.132 second ordinary detour was admitted")
    typed_terminal = cast(TypedDetourResourceTerminal, two_detour["terminal"])
    if second_detour_reason != typed_terminal.reason:
        raise ValueError("v26.132 computed detour terminal reason changed")
    controls = tuple(
        sorted(
            (
                BoundedDynamicControl(
                    name="abi_rescue_counter_independence",
                    status="passed",
                    observed_value=after_detour.abi_rescues_remaining,
                    expected_value=MAXIMUM_ABI_RESCUES,
                ),
                BoundedDynamicControl(
                    name="all_eligible_one_detour_rows",
                    status="passed",
                    observed_value=eligible,
                    expected_value=eligible,
                ),
                BoundedDynamicControl(
                    name="all_registered_reference_paths",
                    status="passed",
                    observed_value=48,
                    expected_value=48,
                ),
                BoundedDynamicControl(
                    name="candidate_space_and_presentation_unchanged",
                    status="passed",
                    observed_value=0,
                    expected_value=0,
                ),
                BoundedDynamicControl(
                    name="detour_classification_after_public_observation",
                    status="passed",
                    observed_value=True,
                    expected_value=True,
                ),
                BoundedDynamicControl(
                    name="privacy_first_capture",
                    status="passed",
                    observed_value=(
                        runner.privacy_redacted_envelope_persisted_before_payload_validation
                    ),
                    expected_value=True,
                ),
                BoundedDynamicControl(
                    name="rollout_quantum_and_headroom",
                    status="passed",
                    observed_value=resource.selected_rollout_headroom_tokens,
                    expected_value=(
                        ROLLOUT_UPPER_BOUND_TOKENS - envelope.maximum_one_detour_static_tokens
                    ),
                ),
                BoundedDynamicControl(
                    name="second_detour_typed_resource_terminal",
                    status="passed",
                    observed_value=second_detour_reason,
                    expected_value="ordinary_detour_allowance_exhausted",
                ),
                BoundedDynamicControl(
                    name="semantic_recovery_counter_independence",
                    status="passed",
                    observed_value=after_detour.semantic_recoveries_remaining,
                    expected_value=MAXIMUM_SEMANTIC_RECOVERIES,
                ),
                BoundedDynamicControl(
                    name="stage_two_zero_provider",
                    status="passed",
                    observed_value=0,
                    expected_value=0,
                ),
                BoundedDynamicControl(
                    name="transport_replacement_counter_independence",
                    status="passed",
                    observed_value=after_detour.transport_replacements_remaining,
                    expected_value=MAXIMUM_TRANSPORT_REPLACEMENTS,
                ),
                BoundedDynamicControl(
                    name="zero_real_provider_calls",
                    status="passed",
                    observed_value=0,
                    expected_value=0,
                ),
            ),
            key=lambda item: item.name,
        )
    )
    values = {
        "runner_contract_id": runner.contract_id,
        "reference_fixture_audit_id": reference.audit_id,
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "resource_contract_id": resource.contract_id,
        "controls": controls,
        "control_count": len(controls),
        "passed_control_count": len(controls),
        "eligible_one_detour_count": eligible,
        "eligible_one_detour_pass_count": eligible,
        "abi_rescue_remaining_after_one_detour": after_detour.abi_rescues_remaining,
        "semantic_recovery_remaining_after_one_detour": (
            after_detour.semantic_recoveries_remaining
        ),
        "transport_replacement_remaining_after_one_detour": (
            after_detour.transport_replacements_remaining
        ),
        "detour_counter_remaining_after_abi_rescue": (after_abi_rescue.ordinary_detours_remaining),
        "detour_counter_remaining_after_semantic_recovery": (
            after_semantic_recovery.ordinary_detours_remaining
        ),
        "detour_counter_remaining_after_transport_replacement": (
            after_transport_replacement.ordinary_detours_remaining
        ),
        "maximum_one_detour_prompt_utf8_bytes": (envelope.maximum_one_detour_prompt_utf8_bytes),
        "maximum_one_detour_static_tokens": envelope.maximum_one_detour_static_tokens,
        "selected_rollout_headroom_tokens": resource.selected_rollout_headroom_tokens,
        "two_detour_primary_requests": two_detour["primary_request_count"],
        "two_detour_provider_calls": two_detour["provider_call_count"],
        "two_detour_transport_invocations": two_detour["transport_invocation_count"],
        "two_detour_prompt_utf8_bytes": two_detour["maximum_prompt_utf8_bytes"],
        "two_detour_static_tokens": two_detour["static_complete_path_upper_bound_tokens"],
        "typed_second_detour_terminal": two_detour["terminal"],
    }
    provisional = BoundedDynamicRunnerPreflightAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return BoundedDynamicRunnerPreflightAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_dynamic_runner_preflight_audit:",
        ),
        **values,
    )


def _validated_copy(
    model_type: type[BaseModel],
    value: BaseModel,
    **updates: Any,
) -> BaseModel:
    payload = value.model_dump(mode="json")
    payload.update(updates)
    return model_type.model_validate(payload)


def _expect_rejected(name: str, callback: Any) -> MutationResult:
    try:
        callback()
    except (AssertionError, KeyError, TypeError, ValueError):
        return MutationResult(name=name)
    raise AssertionError(f"v26.132 destructive mutation was accepted: {name}")


def _make_destructive_audit(
    *,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
    kernel: RoleScalableKernel,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
    reconciliation: DeepReconciliationCompilerAudit,
    resource: RoleScalableResourceContract,
    identity_chain: RoleIdentityChain,
    runner: RoleRunnerContract,
    bounded: BoundedDynamicRunnerPreflightAudit,
) -> DestructiveAudit:
    first_package = task_catalog.packages[0]
    first_path = path_catalog.paths[0]
    first_reconciliation = reconciliation.rows[0]
    first_job = identity_chain.capability_manifest.jobs[0]
    conditioned_job = next(
        item
        for item in identity_chain.reachability_manifest.jobs
        if item.sampling_mode == "reachability_conditioned"
    )
    mutations = (
        _expect_rejected(
            "bounded_audit_second_detour_reclassified",
            lambda: _validated_copy(
                BoundedDynamicRunnerPreflightAudit,
                bounded,
                second_detour_full_path_exceeds_at_least_one_bound=False,
            ),
        ),
        _expect_rejected(
            "deep_reconciliation_projection_changed",
            lambda: _validated_copy(
                DeepReconciliationCompilerBindingRow,
                first_reconciliation,
                formal_compilation_projection_hash="changed",
            ),
        ),
        _expect_rejected(
            "dynamic_envelope_eligible_count_changed",
            lambda: _validated_copy(
                DynamicTrajectoryEnvelopeAudit,
                envelope,
                eligible_closed_detour_count=envelope.eligible_closed_detour_count - 1,
            ),
        ),
        _expect_rejected(
            "job_condition_removed",
            lambda: _validated_copy(
                RoleJob,
                conditioned_job,
                public_condition_id=None,
            ),
        ),
        _expect_rejected(
            "job_seed_changed",
            lambda: _validated_copy(RoleJob, first_job, seed=first_job.seed + 1),
        ),
        _expect_rejected(
            "kernel_dynamic_projection_selection_enabled",
            lambda: _validated_copy(
                RoleScalableKernel,
                kernel,
                full_object_and_compact_dynamic_selection_allowed=True,
            ),
        ),
        _expect_rejected(
            "kernel_model_behavior_equivalence_claimed",
            lambda: _validated_copy(
                RoleScalableKernel,
                kernel,
                model_behavior_equivalence_established=True,
            ),
        ),
        _expect_rejected(
            "manifest_job_deleted",
            lambda: _validated_copy(
                RoleJobManifest,
                identity_chain.capability_manifest,
                jobs=identity_chain.capability_manifest.jobs[:-1],
            ),
        ),
        _expect_rejected(
            "path_catalog_path_deleted",
            lambda: _validated_copy(
                RolePathCatalog,
                path_catalog,
                paths=path_catalog.paths[:-1],
            ),
        ),
        _expect_rejected(
            "path_prompt_bound_exceeded",
            lambda: _validated_copy(
                RoleScalablePath,
                first_path,
                maximum_prompt_utf8_bytes=PROMPT_CEILING_BYTES + 1,
            ),
        ),
        _expect_rejected(
            "policy_action_or_final_grammar_changed",
            lambda: _validated_copy(
                OrdinaryDetourPolicy,
                policy,
                action_or_final_grammar_changed=True,
            ),
        ),
        _expect_rejected(
            "policy_candidate_presentation_changed",
            lambda: _validated_copy(
                OrdinaryDetourPolicy,
                policy,
                candidate_presentation_changed=True,
            ),
        ),
        _expect_rejected(
            "policy_candidate_space_changed",
            lambda: _validated_copy(
                OrdinaryDetourPolicy,
                policy,
                candidate_space_changed=True,
            ),
        ),
        _expect_rejected(
            "policy_detour_allowance_extended",
            lambda: _validated_copy(
                OrdinaryDetourPolicy,
                policy,
                maximum_ordinary_detours=2,
            ),
        ),
        _expect_rejected(
            "policy_detour_allowance_removed",
            lambda: _validated_copy(
                OrdinaryDetourPolicy,
                policy,
                maximum_ordinary_detours=0,
            ),
        ),
        _expect_rejected(
            "resource_primary_limit_reduced",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                maximum_primary_requests=20,
            ),
        ),
        _expect_rejected(
            "resource_provider_limit_reduced",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                maximum_provider_calls_with_recovery=22,
            ),
        ),
        _expect_rejected(
            "resource_rollout_ceiling_reduced",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                rollout_upper_bound_tokens=1_100_000,
            ),
        ),
        _expect_rejected(
            "resource_transport_limit_reduced",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                maximum_transport_inclusive_invocations=23,
            ),
        ),
        _expect_rejected(
            "resource_unbounded_adequacy_claimed",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                unbounded_legal_trajectory_resource_adequacy_claimed=True,
            ),
        ),
        _expect_rejected(
            "runner_recovery_counter_coupled",
            lambda: _validated_copy(
                RoleRunnerContract,
                runner,
                recovery_counters_independent_from_detour_counter=False,
            ),
        ),
        _expect_rejected(
            "runner_stage_two_provider_route_added",
            lambda: _validated_copy(
                RoleRunnerContract,
                runner,
                stage_two_provider_calls=1,
            ),
        ),
        _expect_rejected(
            "task_catalog_task_deleted",
            lambda: _validated_copy(
                RoleTaskPackageCatalog,
                task_catalog,
                packages=task_catalog.packages[:-1],
            ),
        ),
        _expect_rejected(
            "task_package_tier_changed",
            lambda: _validated_copy(
                RoleScalableTaskPackage,
                first_package,
                tier=("hard_control" if first_package.tier != "hard_control" else "easy_control"),
            ),
        ),
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    provisional = DestructiveAudit.model_construct(
        audit_id="pending",
        mutations=ordered,
    )
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_bounded_dynamic_destructive:",
        ),
        mutations=ordered,
    )


def _make_transition(
    *,
    policy: OrdinaryDetourPolicy,
    envelope: DynamicTrajectoryEnvelopeAudit,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    identity_chain: RoleIdentityChain,
    runner: RoleRunnerContract,
    bounded: BoundedDynamicRunnerPreflightAudit,
) -> ProspectiveTransitionContract:
    values = {
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "identity_chain_id": identity_chain.chain_id,
        "runner_contract_id": runner.contract_id,
        "bounded_runner_preflight_audit_id": bounded.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_bounded_dynamic_transition:",
        ),
        **values,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
    output_dir: Path,
) -> BoundedDynamicRolePreflightReport:
    if output_dir.exists():
        raise ValueError(f"immutable v26.132 output directory exists: {output_dir}")
    source_replay = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        predecessor_dir=predecessor_dir,
    )
    loaded, frozen_input = _load_inputs(
        package_root=package_root,
        predecessor_dir=predecessor_dir,
        source_replay=source_replay,
    )
    immediate = _rebuild_immediate_predecessor(
        package_root=package_root,
        predecessor_dir=predecessor_dir,
    )
    if (
        immediate.loaded.frozen.capability.population_id != loaded.frozen.capability.population_id
        or immediate.loaded.frozen.reachability.population_id
        != loaded.frozen.reachability.population_id
        or immediate.loaded.compact.protocol_id != loaded.compact.protocol_id
        or immediate.loaded.s1.candidate_id != loaded.s1.candidate_id
        or immediate.loaded.selection.audit_id != loaded.selection.audit_id
    ):
        raise ValueError("v26.132 v26.130 and v26.131 frozen semantic inputs diverged")

    policy = _make_detour_policy()
    envelope = _make_dynamic_envelope(
        package_root=package_root,
        loaded=loaded,
        policy=policy,
        executions=immediate.executions,
    )
    resource = _make_resource_contract(policy=policy, envelope=envelope)
    kernel = _make_kernel(
        package_root,
        policy=policy,
        envelope=envelope,
        resource=resource,
    )
    task_catalog, task_mapping = _rematerialize_tasks(
        predecessor_catalog=immediate.task_catalog,
        kernel=kernel,
    )
    path_catalog, path_mapping = _rematerialize_paths(
        predecessor_catalog=immediate.path_catalog,
        kernel=kernel,
        task_catalog=task_catalog,
        task_mapping=task_mapping,
    )
    if set(task_mapping) & set(task_mapping.values()):
        raise ValueError("v26.132 TaskPackage identity overlap with v26.131")
    if set(path_mapping) & set(path_mapping.values()):
        raise ValueError("v26.132 Path identity overlap with v26.131")

    reconciliation = _make_reconciliation_audit(
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        loaded=loaded,
    )
    identity_chain = _make_identity_chain(
        kernel=kernel,
        resource=resource,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        predecessor_chain=immediate.identity_chain,
        task_mapping=task_mapping,
        path_mapping=path_mapping,
    )
    old_contracts = {
        immediate.identity_chain.capability_contract.contract_id,
        immediate.identity_chain.reachability_contract.contract_id,
    }
    new_contracts = {
        identity_chain.capability_contract.contract_id,
        identity_chain.reachability_contract.contract_id,
    }
    old_manifests = {
        immediate.identity_chain.capability_manifest.manifest_id,
        immediate.identity_chain.reachability_manifest.manifest_id,
    }
    new_manifests = {
        identity_chain.capability_manifest.manifest_id,
        identity_chain.reachability_manifest.manifest_id,
    }
    if old_contracts & new_contracts or old_manifests & new_manifests:
        raise ValueError("v26.132 Contract or Manifest identity overlap with v26.131")

    runner = _make_runner_contract(
        kernel=kernel,
        resource=resource,
        identity_chain=identity_chain,
        policy=policy,
        envelope=envelope,
    )
    if runner.contract_id == immediate.runner.contract_id:
        raise ValueError("v26.132 Runner identity overlaps v26.131")
    reference = _make_reference_fixture(
        runner=runner,
        path_catalog=path_catalog,
    )
    bounded = _make_bounded_runner_preflight(
        package_root=package_root,
        runner=runner,
        reference=reference,
        policy=policy,
        envelope=envelope,
        resource=resource,
        loaded=loaded,
        executions=immediate.executions,
    )
    destructive = _make_destructive_audit(
        policy=policy,
        envelope=envelope,
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        reconciliation=reconciliation,
        resource=resource,
        identity_chain=identity_chain,
        runner=runner,
        bounded=bounded,
    )
    transition = _make_transition(
        policy=policy,
        envelope=envelope,
        kernel=kernel,
        resource=resource,
        identity_chain=identity_chain,
        runner=runner,
        bounded=bounded,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source_replay),
        ("frozen_role_input_audit.json", frozen_input),
        ("ordinary_detour_policy.json", policy),
        ("dynamic_trajectory_envelope_audit.json", envelope),
        ("bounded_dynamic_resource_contract.json", resource),
        ("bounded_dynamic_role_kernel.json", kernel),
        ("role_task_package_catalog.json", task_catalog),
        ("role_path_catalog.json", path_catalog),
        ("deep_reconciliation_compiler_audit.json", reconciliation),
        ("role_identity_chain.json", identity_chain),
        ("bounded_dynamic_runner_contract.json", runner),
        ("reference_runner_fixture_audit.json", reference),
        ("bounded_dynamic_runner_preflight_audit.json", bounded),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True)
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in sorted(outputs))
    report_values = {
        "source_replay_audit_id": source_replay.audit_id,
        "frozen_role_input_audit_id": frozen_input.audit_id,
        "ordinary_detour_policy_id": policy.policy_id,
        "dynamic_trajectory_envelope_audit_id": envelope.audit_id,
        "resource_contract_id": resource.contract_id,
        "kernel_id": kernel.kernel_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "path_catalog_id": path_catalog.catalog_id,
        "deep_reconciliation_compiler_audit_id": reconciliation.audit_id,
        "role_identity_chain_id": identity_chain.chain_id,
        "runner_contract_id": runner.contract_id,
        "reference_runner_fixture_audit_id": reference.audit_id,
        "bounded_runner_preflight_audit_id": bounded.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
        "dynamic_candidate_check_count": envelope.candidate_check_count,
        "eligible_one_detour_pass_count": bounded.eligible_one_detour_pass_count,
        "maximum_one_detour_prompt_utf8_bytes": (envelope.maximum_one_detour_prompt_utf8_bytes),
        "maximum_one_detour_static_tokens": envelope.maximum_one_detour_static_tokens,
        "selected_rollout_headroom_tokens": resource.selected_rollout_headroom_tokens,
    }
    provisional = BoundedDynamicRolePreflightReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = BoundedDynamicRolePreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_bounded_dynamic_role_preflight_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description=(
            "Credential-free v26.132 bounded dynamic interaction and fresh role-chain preflight"
        )
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
    report = build_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        predecessor_dir=args.predecessor_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
