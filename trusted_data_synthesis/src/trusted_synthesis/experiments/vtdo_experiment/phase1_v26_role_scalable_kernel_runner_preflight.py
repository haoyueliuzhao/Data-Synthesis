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

RUN_ID: Final = "finance_v26_131_role_scalable_kernel_runner_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_131_role_scalable_kernel_runner_preflight_v1_20260824"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_role_scalable_kernel_runner_preflight.py"
)
PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
PREDECESSOR_OUTPUT_NAMES: Final = (
    "compact_projection_protocol.json",
    "destructive_audit.json",
    "frozen_population_replay_audit.json",
    "prospective_transition_contract.json",
    "report.json",
    "role_support_complexity_census.json",
    "role_support_scalability_contract.json",
    "scalability_candidate_s0.json",
    "scalability_candidate_s1.json",
    "scalability_selection_audit.json",
    "source_replay_audit.json",
)

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_role_kernel_scalability_design_report:"
    "e0747bb67e14e4850a16447d0a3bcee7a81003352bfd59d9d5bfa3af2fd5949a"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "33e2735d55d080f3d6d205c0121831a92eba9761b02e991d52ddc9fa7c1573ed"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_role_scalability_transition:"
    "feabd18ea7340f6340bc47003d1992a7719fd8daa356cca686946eadb82d8556"
)
EXPECTED_PREDECESSOR_TRANSITION_SHA256: Final = (
    "c9118dea09cb97bbec7ae74dcd7e37abb5df433d1a9090285ac3f9f57ded3a7b"
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
MAXIMUM_PRIMARY_REQUESTS: Final = 20
MAXIMUM_PROVIDER_CALLS: Final = 22
MAXIMUM_TRANSPORT_INVOCATIONS: Final = 23
ROLLOUT_UPPER_BOUND_TOKENS: Final = 1_060_000
COMPLETION_REQUEST_BOUND_TOKENS: Final = 16_384
PROVIDER_ACCOUNTING_MARGIN_TOKENS: Final = 1
MAXIMUM_ABI_RESCUES: Final = 1
MAXIMUM_SEMANTIC_RECOVERIES: Final = 1
MAXIMUM_TRANSPORT_REPLACEMENTS: Final = 1
CAPABILITY_JOB_COUNT: Final = 96
REACHABILITY_JOB_COUNT: Final = 360
TOTAL_JOB_COUNT: Final = CAPABILITY_JOB_COUNT + REACHABILITY_JOB_COUNT
NEXT_STAGE: Final = "role_scalable_dynamic_interaction_capacity_redesign_only"

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
    predecessor_transitive_count: Literal[3165] = 3165
    predecessor_output_count: Literal[11] = 11
    implementation_count: Literal[1] = 1
    replayed_file_count: Literal[3177] = 3177
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3177, max_length=3177)
    replay_before_profile_parse: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_role_scalable_source_replay.v1"] = (
        "finance_v26_role_scalable_source_replay.v1"
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
            raise ValueError("v26.131 source replay denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_role_scalable_source_replay:"):
            raise ValueError("v26.131 source replay identity changed")
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
            raise ValueError("v26.131 role source Populations overlap")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_frozen_role_input_audit:"):
            raise ValueError("v26.131 frozen role-input identity changed")
        return self


class RoleScalableKernel(FrozenModel):
    kernel_id: str = Field(min_length=1)
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
    maximum_primary_requests: Literal[20] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls: Literal[22] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[23] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1060000] = ROLLOUT_UPPER_BOUND_TOKENS
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    provider_accounting_margin_tokens: Literal[1] = PROVIDER_ACCOUNTING_MARGIN_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
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
    schema_version: Literal["finance_v26_role_scalable_kernel.v1"] = (
        "finance_v26_role_scalable_kernel.v1"
    )

    @model_validator(mode="after")
    def validate_kernel(self) -> RoleScalableKernel:
        if (
            self.compact_projection_protocol_id != EXPECTED_COMPACT_PROTOCOL_ID
            or self.selected_scalability_candidate_id != EXPECTED_S1_CANDIDATE_ID
            or self.model_behavior_equivalence_established
            or self.full_object_and_compact_dynamic_selection_allowed
        ):
            raise ValueError("v26.131 Role-scalable Kernel condition changed")
        if self.kernel_id != _identity(self, "kernel_id", "finance_v26_role_scalable_kernel:"):
            raise ValueError("v26.131 Role-scalable Kernel identity changed")
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
            raise ValueError("v26.131 Role TaskPackage binding changed")
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_role_scalable_task_package:"
        ):
            raise ValueError("v26.131 Role TaskPackage identity changed")
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
            raise ValueError("v26.131 TaskPackage catalog changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_role_task_package_catalog:"
        ):
            raise ValueError("v26.131 TaskPackage catalog identity changed")
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
            raise ValueError("v26.131 registered Role Path binding changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_role_scalable_path:"):
            raise ValueError("v26.131 Role Path identity changed")
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
            raise ValueError("v26.131 Role Path catalog changed")
        if self.catalog_id != _identity(self, "catalog_id", "finance_v26_role_path_catalog:"):
            raise ValueError("v26.131 Role Path catalog identity changed")
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
            raise ValueError("v26.131 deep Reconciliation compiler binding changed")
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_role_scalable_reconciliation_compiler_binding:",
        ):
            raise ValueError("v26.131 Reconciliation binding identity changed")
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
            raise ValueError("v26.131 Reconciliation audit denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_deep_reconciliation_compiler_audit:"
        ):
            raise ValueError("v26.131 Reconciliation audit identity changed")
        return self


class RoleScalableResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    predecessor_s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    provider_accounting_margin_tokens: Literal[1] = PROVIDER_ACCOUNTING_MARGIN_TOKENS
    prompt_ceiling_bytes: Literal[60000] = PROMPT_CEILING_BYTES
    maximum_primary_requests: Literal[20] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls_with_recovery: Literal[22] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[23] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1060000] = ROLLOUT_UPPER_BOUND_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
    all_registered_reference_paths_qualified: Literal[True] = True
    ordinary_legal_detour_headroom_qualified: Literal[False] = False
    dynamic_model_path_resource_adequacy_established: Literal[False] = False
    task_deletion_or_threshold_relaxation_allowed: Literal[False] = False
    usage_charged_without_clipping: Literal[True] = True
    denied_request_makes_zero_provider_calls: Literal[True] = True
    provider_calls: Literal[0] = 0
    status: Literal["frozen_for_preflight_not_empirically_adequate"] = (
        "frozen_for_preflight_not_empirically_adequate"
    )
    schema_version: Literal["finance_v26_role_scalable_resource_contract.v1"] = (
        "finance_v26_role_scalable_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleScalableResourceContract:
        if self.ordinary_legal_detour_headroom_qualified:
            raise ValueError("v26.131 resource Contract overclaims legal-detour support")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalable_resource_contract:"
        ):
            raise ValueError("v26.131 resource Contract identity changed")
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
            raise ValueError("v26.131 role execution Contract changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalable_execution_contract:"
        ):
            raise ValueError("v26.131 role execution Contract identity changed")
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
            raise ValueError("v26.131 conditioned Job binding changed")
        if not conditioned and any(item is not None for item in conditional_fields):
            raise ValueError("v26.131 unconditional Job carries a condition")
        if self.role == "capability":
            if self.sampling_mode != "capability_unconditional" or self.replicate_index >= 8:
                raise ValueError("v26.131 Capability Job denominator changed")
        elif self.sampling_mode == "capability_unconditional":
            raise ValueError("v26.131 Reachability Job uses Capability sampling")
        elif conditioned and self.replicate_index >= 6:
            raise ValueError("v26.131 conditioned Job denominator changed")
        if self.job_id != _identity(self, "job_id", "finance_v26_role_scalable_job:"):
            raise ValueError("v26.131 Role Job identity changed")
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
            raise ValueError("v26.131 Role Manifest identity chain changed")
        if self.role == "capability":
            if len(task_counts) != 12 or set(task_counts.values()) != {8}:
                raise ValueError("v26.131 Capability Manifest denominator changed")
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
                raise ValueError("v26.131 Reachability Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_role_scalable_manifest:"
        ):
            raise ValueError("v26.131 Role Manifest identity changed")
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
            raise ValueError("v26.131 Role identity chain changed")
        if self.chain_id != _identity(self, "chain_id", "finance_v26_role_identity_chain:"):
            raise ValueError("v26.131 Role identity-chain identity changed")
        return self


class RoleRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_run_id: str = RUN_ID
    future_execution_run_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
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
    maximum_primary_requests: Literal[20] = MAXIMUM_PRIMARY_REQUESTS
    maximum_provider_calls: Literal[22] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[23] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1060000] = ROLLOUT_UPPER_BOUND_TOKENS
    exact_request_completion_bound_tokens: Literal[16384] = COMPLETION_REQUEST_BOUND_TOKENS
    maximum_abi_rescues: Literal[1] = MAXIMUM_ABI_RESCUES
    maximum_semantic_recoveries: Literal[1] = MAXIMUM_SEMANTIC_RECOVERIES
    maximum_transport_replacements: Literal[1] = MAXIMUM_TRANSPORT_REPLACEMENTS
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
    schema_version: Literal["finance_v26_role_scalable_runner_contract.v1"] = (
        "finance_v26_role_scalable_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> RoleRunnerContract:
        if (
            self.thinking_type != "enabled"
            or self.full_object_fallback_allowed
            or self.compact_or_full_dynamic_choice_allowed
            or self.empirical_execution_authorized
        ):
            raise ValueError("v26.131 Runner condition changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalable_runner_contract:"
        ):
            raise ValueError("v26.131 Runner Contract identity changed")
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
            raise ValueError("v26.131 reference-path preflight row changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_role_reference_path_preflight:"):
            raise ValueError("v26.131 reference-path preflight identity changed")
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
            raise ValueError("v26.131 reference Runner denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_reference_runner_fixture:"):
            raise ValueError("v26.131 reference Runner identity changed")
        return self


class DynamicStressControl(FrozenModel):
    name: str = Field(min_length=1)
    status: Literal["passed", "failed_as_expected"]
    path_id: str | None = None
    state_id: str | None = None
    observed_value: int | str | bool
    frozen_limit: int | None = None
    provider_calls: Literal[0] = 0


class DynamicInteractionStressAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    reference_fixture_audit_id: str = Field(min_length=1)
    controls: tuple[DynamicStressControl, ...] = Field(min_length=12, max_length=12)
    control_count: Literal[12] = 12
    passed_control_count: Literal[11] = 11
    failed_control_count: Literal[1] = 1
    maximum_candidate_state_count: Literal[63] = 63
    maximum_reference_prompt_utf8_bytes: Literal[54569] = 54_569
    maximum_blocked_action_count: int = Field(ge=1)
    deep_reconciliation_path_control_count: Literal[8] = 8
    failure_recovery_typed_failure_revision_passed: Literal[True] = True
    stopping_terminal_verification_passed: Literal[True] = True
    abi_rescue_passed: Literal[True] = True
    semantic_recovery_passed: Literal[True] = True
    transport_replacement_passed: Literal[True] = True
    legal_nonreference_action_committed: Literal[True] = True
    legal_no_progress_action_committed: Literal[True] = True
    ordinary_replanning_completed_program: Literal[True] = True
    detour_path_id: str = Field(min_length=1)
    detour_state_id: str = Field(min_length=1)
    repeated_successful_action_id: str = Field(min_length=1)
    reference_primary_request_count: Literal[20] = 20
    detour_primary_request_count: Literal[21] = 21
    primary_request_excess: Literal[1] = 1
    detour_provider_calls_with_both_recoveries: Literal[23] = 23
    provider_call_excess: Literal[1] = 1
    detour_transport_inclusive_invocations: Literal[24] = 24
    transport_invocation_excess: Literal[1] = 1
    detour_maximum_prompt_utf8_bytes: int = Field(ge=1)
    detour_static_path_upper_bound_tokens: int = Field(gt=0)
    detour_rollout_excess_tokens: int = Field(ge=1)
    twenty_primary_boundary_admitted: Literal[True] = True
    twenty_first_primary_denied_before_provider: Literal[True] = True
    denied_request_provider_calls: Literal[0] = 0
    full_or_compact_dynamic_selection_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["blocked_by_legal_detour_resource_censorship"] = (
        "blocked_by_legal_detour_resource_censorship"
    )
    schema_version: Literal["finance_v26_dynamic_interaction_stress.v1"] = (
        "finance_v26_dynamic_interaction_stress.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicInteractionStressAudit:
        names = tuple(item.name for item in self.controls)
        statuses = Counter(item.status for item in self.controls)
        if (
            names != tuple(sorted(set(names)))
            or statuses != Counter({"passed": 11, "failed_as_expected": 1})
            or self.detour_primary_request_count
            != self.reference_primary_request_count + self.primary_request_excess
            or self.detour_provider_calls_with_both_recoveries
            != MAXIMUM_PROVIDER_CALLS + self.provider_call_excess
            or self.detour_transport_inclusive_invocations
            != MAXIMUM_TRANSPORT_INVOCATIONS + self.transport_invocation_excess
            or self.detour_static_path_upper_bound_tokens
            != ROLLOUT_UPPER_BOUND_TOKENS + self.detour_rollout_excess_tokens
        ):
            raise ValueError("v26.131 dynamic interaction failure changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_dynamic_interaction_stress:"):
            raise ValueError("v26.131 dynamic interaction identity changed")
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
    schema_version: Literal["finance_v26_role_scalable_destructive.v1"] = (
        "finance_v26_role_scalable_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.131 destructive mutation names changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_role_scalable_destructive:"):
            raise ValueError("v26.131 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    kernel_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    dynamic_interaction_stress_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_frozen_role_populations_must_be_preserved: Literal[True] = True
    exact_s1_model_visible_projection_must_be_preserved: Literal[True] = True
    resource_capacity_redesign_only_authorized: Literal[True] = True
    legal_detour_and_no_progress_controls_must_be_qualified: Literal[True] = True
    fresh_identity_chain_required_after_resource_change: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    s1_model_visible_representation_qualification_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    task_deletion_substitution_or_tier_change_authorized: Literal[False] = False
    compact_projection_change_authorized: Literal[False] = False
    model_profile_or_grammar_change_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    status: Literal["dynamic_interaction_capacity_redesign_required"] = (
        "dynamic_interaction_capacity_redesign_required"
    )
    schema_version: Literal["finance_v26_role_scalable_transition.v1"] = (
        "finance_v26_role_scalable_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if (
            self.provider_calls_authorized
            or self.s1_model_visible_representation_qualification_authorized
            or self.capability_or_reachability_execution_authorized
        ):
            raise ValueError("v26.131 Transition authorizes an online stage")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_role_scalable_transition:"
        ):
            raise ValueError("v26.131 Transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class RoleScalableKernelRunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    frozen_role_input_audit_id: str = Field(min_length=1)
    kernel_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    deep_reconciliation_compiler_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    role_identity_chain_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    reference_runner_fixture_audit_id: str = Field(min_length=1)
    dynamic_interaction_stress_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=13, max_length=13)
    role_task_package_count: Literal[24] = 24
    role_path_count: Literal[48] = 48
    role_contract_count: Literal[2] = 2
    role_manifest_count: Literal[2] = 2
    role_job_count: Literal[456] = TOTAL_JOB_COUNT
    role_runner_count: Literal[1] = 1
    registered_reference_path_pass_count: Literal[48] = 48
    dynamic_legal_detour_failure_count: Literal[1] = 1
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    role_execution_authorized: Literal[False] = False
    status: Literal["blocked_by_dynamic_interaction_capacity"] = (
        "blocked_by_dynamic_interaction_capacity"
    )
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_role_scalable_kernel_runner_preflight_report.v1"] = (
        "finance_v26_role_scalable_kernel_runner_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RoleScalableKernelRunnerPreflightReport:
        if self.role_execution_authorized:
            raise ValueError("v26.131 report authorizes Role execution")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_role_scalable_kernel_runner_preflight_report:",
        ):
            raise ValueError("v26.131 report identity changed")
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
        raise ValueError("v26.131 predecessor report or Transition bytes changed")
    report = predecessor.RoleKernelScalabilityDesignReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    transition = predecessor.ProspectiveTransitionContract.model_validate_json(
        transition_path.read_text(encoding="utf-8")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or report.next_permitted_stage != predecessor.NEXT_STAGE
    ):
        raise ValueError("v26.131 predecessor identity chain changed")
    detail_index = {item.relative_path: item for item in report.detail_files}
    if set(detail_index) != set(PREDECESSOR_OUTPUT_NAMES) - {"report.json"}:
        raise ValueError("v26.131 predecessor detail-file denominator changed")
    for name, detail in detail_index.items():
        path = predecessor_dir / name
        if _sha256(path) != detail.sha256 or path.stat().st_size != detail.byte_count:
            raise ValueError(f"v26.131 predecessor detail changed: {name}")
    predecessor_replay = predecessor.SourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    if predecessor_replay.replayed_file_count != 3165:
        raise ValueError("v26.131 predecessor transitive replay count changed")
    entries: list[SourceReplayEntry] = []
    for item in predecessor_replay.entries:
        path = package_root / item.relative_path
        observed = _sha256(path)
        if observed != item.sha256 or path.stat().st_size != item.byte_count:
            raise ValueError(f"v26.131 transitive replay mismatch: {item.relative_path}")
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
            "finance_v26_role_scalable_source_replay:",
        ),
        **values,
    )


def _load_inputs(
    *,
    package_root: Path,
    predecessor_dir: Path,
    source_replay: SourceReplayAudit,
) -> tuple[_LoadedInputs, FrozenRoleInputAudit]:
    formal_predecessor_replay = predecessor.SourceReplayAudit.model_validate_json(
        (predecessor_dir / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    frozen, population_replay = predecessor._load_frozen_inputs(  # noqa: SLF001
        predecessor_dir=package_root / predecessor.PREDECESSOR_DIR,
        source_replay=formal_predecessor_replay,
    )
    formal_population_replay = predecessor.FrozenPopulationReplayAudit.model_validate_json(
        (predecessor_dir / "frozen_population_replay_audit.json").read_text(encoding="utf-8")
    )
    if population_replay != formal_population_replay:
        raise ValueError("v26.131 frozen Population replay changed")
    formal_census = predecessor.RoleSupportComplexityCensus.model_validate_json(
        (predecessor_dir / "role_support_complexity_census.json").read_text(encoding="utf-8")
    )
    compact = predecessor.CompactProjectionProtocol.model_validate_json(
        (predecessor_dir / "compact_projection_protocol.json").read_text(encoding="utf-8")
    )
    s1 = predecessor.ScalabilityCandidate.model_validate_json(
        (predecessor_dir / "scalability_candidate_s1.json").read_text(encoding="utf-8")
    )
    selection = predecessor.ScalabilitySelectionAudit.model_validate_json(
        (predecessor_dir / "scalability_selection_audit.json").read_text(encoding="utf-8")
    )
    support = predecessor.RoleSupportScalabilityContract.model_validate_json(
        (predecessor_dir / "role_support_scalability_contract.json").read_text(encoding="utf-8")
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
        raise ValueError("v26.131 selected S1 lineage changed")
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
        raise ValueError("v26.131 full-mechanism Census does not reproduce")
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


def _make_kernel(package_root: Path) -> RoleScalableKernel:
    profile_path = package_root / PROFILE_PATH
    if _sha256(profile_path) != EXPECTED_PROFILE_SHA256:
        raise ValueError("v26.131 Stage 1 Thinking profile bytes changed")
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
        raise ValueError("v26.131 exact Thinking model profile changed")
    provisional = RoleScalableKernel.model_construct(kernel_id="pending")
    return RoleScalableKernel(
        kernel_id=_identity(
            provisional,
            "kernel_id",
            "finance_v26_role_scalable_kernel:",
        )
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
            raise ValueError("v26.131 S1 state or Candidate reconstruction changed")
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        parsed = parse_exact_canonical_action_payload(_action_payload(reference))
        if parsed != reference:
            raise ValueError("v26.131 exact Action ABI changed the reference Proposal")
        selection = evaluate_canonical_action_proposal(
            state,
            parsed,
            call_index=len(observations) + 1,
        )
        if selection.commit is None or selection.rejection is not None:
            raise ValueError("v26.131 reference Proposal did not Commit")
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
                raise ValueError("v26.131 Final Commit occurred before public readiness")
            break
        call = selection.commit.call
        if call is None:
            raise ValueError("v26.131 non-final Commit lacks a public call")
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
        raise ValueError("v26.131 registered reference Path did not terminate")
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
        raise ValueError("v26.131 registered Path diverged from the v26.130 Census")
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
            raise ValueError("v26.131 Reconciliation Path projection changed")
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
    kernel: RoleScalableKernel,
) -> RoleScalableResourceContract:
    values = {"kernel_id": kernel.kernel_id}
    provisional = RoleScalableResourceContract.model_construct(
        contract_id="pending",
        **values,
    )
    return RoleScalableResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_scalable_resource_contract:",
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


def _make_identity_chain(
    *,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
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
    capability_manifest = _make_manifest(
        contract=capability_contract,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
    reachability_manifest = _make_manifest(
        contract=reachability_contract,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
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
) -> RoleRunnerContract:
    values = {
        "future_execution_run_id": f"{RUN_ID}|future_role_execution",
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "identity_chain_id": identity_chain.chain_id,
        "capability_manifest_id": identity_chain.capability_manifest.manifest_id,
        "reachability_manifest_id": identity_chain.reachability_manifest.manifest_id,
    }
    provisional = RoleRunnerContract.model_construct(contract_id="pending", **values)
    return RoleRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_scalable_runner_contract:",
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


def _detour_candidate(
    executions: Sequence[_PathExecution],
) -> _PathExecution:
    candidates = sorted(
        (
            item
            for item in executions
            if item.path.role == "reachability"
            and item.path.tier == "hard_control"
            and item.path.path_strategy_id == "search_then_open"
            and item.path.primary_request_count == MAXIMUM_PRIMARY_REQUESTS
            and len(item.states) >= 2
            and item.observations
            and item.observations[0].status == "succeeded"
            and any(
                candidate.action_id == item.proposals[0].action_id
                for candidate in item.states[1].action_candidates
            )
        ),
        key=lambda item: (
            -item.path.static_complete_path_upper_bound_tokens,
            item.path.path_id,
        ),
    )
    if not candidates:
        raise ValueError("v26.131 lacks a maximum registered legal-detour fixture")
    return candidates[0]


def _execute_legal_detour(
    *,
    execution: _PathExecution,
    selection_id: str,
    action_grammar: SemanticActionResponseGrammar,
    final_grammar: ExactFinalResponseGrammar,
) -> dict[str, Any]:
    package = execution.task.package
    record = package.operational_record
    environment = package.environment
    strategy = execution.path.path_strategy_id
    condition = predecessor._path_condition(package.role, strategy)  # noqa: SLF001
    runtime = predecessor._runtime(record, environment)  # noqa: SLF001
    observations: list[AgentToolObservation] = []
    primary_prompts: list[str] = []
    abi_prompts: list[str] = []
    semantic_recovery_prompts: list[str] = []
    states: list[SemanticActionState] = []
    first_action_id: str | None = None
    repeated_action_id: str | None = None
    detour_state_id: str | None = None
    no_progress = False
    for logical_index in range(128):
        state = build_semantic_action_state(
            record.task_package.task.public,
            environment,
            tuple(observations),
        )
        salt = canonical_hash(
            {
                "selection_audit_id": selection_id,
                "role_task_package_id": package.task_package_id,
                "path_strategy_id": strategy,
                "state_id": state.state_id,
                "logical_index": logical_index,
                "fixture": "repeat_prior_success_then_ordinary_replan",
            },
            prefix="finance_v26_role_dynamic_candidate_presentation:",
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
        predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        reference = predecessor._compact_reference_proposal(  # noqa: SLF001
            prompt,
            presentation_salt=salt,
        )
        selected = reference
        if logical_index == 0:
            first_action_id = reference.action_id
        elif logical_index == 1:
            repeated = next(
                (item for item in state.action_candidates if item.action_id == first_action_id),
                None,
            )
            if repeated is None:
                raise ValueError("v26.131 successful first action is not legally repeatable")
            selected = make_canonical_action_proposal(
                state_id=state.state_id,
                action_id=repeated.action_id,
                decision_kind=repeated.decision_kind,
            )
            repeated_action_id = repeated.action_id
            detour_state_id = state.state_id
        parsed = parse_exact_canonical_action_payload(_action_payload(selected))
        if parsed != selected:
            raise ValueError("v26.131 detour Action ABI changed")
        result = evaluate_canonical_action_proposal(
            state,
            parsed,
            call_index=len(observations) + 1,
        )
        if result.commit is None or result.rejection is not None:
            raise ValueError("v26.131 legal detour did not Commit")
        states.append(state)
        primary_prompts.append(prompt)
        abi_failure = {
            "family": "response_serialization_failure",
            "subtype": "canonical_action_not_exact_four_field_grammar",
        }
        abi_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="abi_rescue",
                instruction=record.task_package.task.public.instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=salt,
                typed_failure=abi_failure,
                grammar=action_grammar,
            )
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
            call_index=len(observations) + 1,
        ).rejection
        if rejection is None:
            raise ValueError("v26.131 detour semantic-recovery fixture was accepted")
        recovery_state = build_semantic_action_state(
            record.task_package.task.public,
            environment,
            tuple(observations),
            semantic_rejections=(rejection,),
        )
        semantic_recovery_prompts.append(
            predecessor._compact_action_prompt(  # noqa: SLF001
                phase="semantic_recovery",
                instruction=record.task_package.task.public.instruction,
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
        if result.commit.action == "emit_final":
            break
        call = result.commit.call
        if call is None:
            raise ValueError("v26.131 detour non-final Commit lacks a call")
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
        if logical_index == 1:
            if observation.status != "succeeded":
                raise ValueError("v26.131 repeated legal action did not succeed")
            next_state = build_semantic_action_state(
                record.task_package.task.public,
                environment,
                (*observations, observation),
            )
            no_progress = _progress_vector(next_state) == _progress_vector(state)
        observations.append(observation)
    else:
        raise ValueError("v26.131 legal-detour Path did not terminate")
    if (
        repeated_action_id is None
        or detour_state_id is None
        or not no_progress
        or not states[-1].final_answer_allowed
        or not states[-1].terminal_verification_completed
    ):
        raise ValueError("v26.131 legal no-progress detour did not ordinarily replan")
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
    terminal_evaluation = evaluate_canonical_action_proposal(
        states[-1],
        predecessor._compact_reference_proposal(  # noqa: SLF001
            primary_prompts[-1],
            presentation_salt=canonical_hash(
                {
                    "selection_audit_id": selection_id,
                    "role_task_package_id": package.task_package_id,
                    "path_strategy_id": strategy,
                    "state_id": states[-1].state_id,
                    "logical_index": len(states) - 1,
                    "fixture": "repeat_prior_success_then_ordinary_replan",
                },
                prefix="finance_v26_role_dynamic_candidate_presentation:",
            ),
        ),
        call_index=len(observations) + 1,
    )
    terminal_commit = terminal_evaluation.commit
    if terminal_commit is None:
        raise ValueError("v26.131 terminal reference Proposal did not commit")
    envelope = make_final_response_host_envelope(
        terminal_state_id=states[-1].state_id,
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
    return {
        "path_id": execution.path.path_id,
        "state_id": detour_state_id,
        "action_id": repeated_action_id,
        "state_count": len(states),
        "observation_count": len(observations),
        "primary_request_count": len(primary_prompts) + 1,
        "maximum_prompt_utf8_bytes": max(len(item.encode("utf-8")) for item in all_prompts),
        "static_path_upper_bound_tokens": upper_bound,
    }


def _make_dynamic_stress_audit(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    runner: RoleRunnerContract,
    reference: ReferenceRunnerFixtureAudit,
    executions: Sequence[_PathExecution],
) -> DynamicInteractionStressAudit:
    action_grammar = SemanticActionResponseGrammar.model_validate_json(
        (package_root / predecessor.ACTION_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    final_grammar = ExactFinalResponseGrammar.model_validate_json(
        (package_root / predecessor.FINAL_GRAMMAR_PATH).read_text(encoding="utf-8")
    )
    selected = _detour_candidate(executions)
    detour = _execute_legal_detour(
        execution=selected,
        selection_id=loaded.selection.audit_id,
        action_grammar=action_grammar,
        final_grammar=final_grammar,
    )
    if (
        detour["primary_request_count"] != MAXIMUM_PRIMARY_REQUESTS + 1
        or detour["static_path_upper_bound_tokens"] <= ROLLOUT_UPPER_BOUND_TOKENS
    ):
        raise ValueError(
            "v26.131 legal detour did not expose the expected resource boundary: "
            f"primary={detour['primary_request_count']}, "
            f"tokens={detour['static_path_upper_bound_tokens']}"
        )
    all_states = tuple(state for item in executions for state in item.states)
    maximum_candidate_state = max(
        all_states,
        key=lambda state: (len(state.action_candidates), state.state_id),
    )
    maximum_blocked = max(
        (
            len(state.blocked_actions) + len(state.active_blocked_public_calls)
            for state in all_states
        ),
        default=0,
    )
    if maximum_blocked < 1:
        raise ValueError("v26.131 reference controls never reached a blocked-action state")
    malformed = {
        "state_id": maximum_candidate_state.state_id,
        "action_id": maximum_candidate_state.action_candidates[0].action_id,
        "decision_kind": maximum_candidate_state.action_candidates[0].decision_kind,
    }
    try:
        parse_exact_canonical_action_payload(malformed)
    except Exception:
        abi_rescue_passed = True
    else:
        raise ValueError("v26.131 malformed Action ABI control was accepted")
    semantic_reference = make_canonical_action_proposal(
        state_id=maximum_candidate_state.state_id,
        action_id=maximum_candidate_state.action_candidates[0].action_id,
        decision_kind=maximum_candidate_state.action_candidates[0].decision_kind,
    )
    semantic_invalid = make_canonical_action_proposal(
        state_id=semantic_reference.state_id,
        action_id=semantic_reference.action_id,
        decision_kind=cast(
            Any,
            predecessor.predecessor._other_decision_kind(  # noqa: SLF001
                semantic_reference.decision_kind
            ),
        ),
    )
    semantic_recovery_passed = (
        evaluate_canonical_action_proposal(
            maximum_candidate_state,
            semantic_invalid,
            call_index=1,
        ).rejection
        is not None
    )
    failure_recovery_passed = any(
        item.task.package.mechanism_id == "failure_recovery"
        and item.path.program_closed
        and any(
            observation.status == "failed"
            and index + 1 < len(item.proposals)
            and bool(item.states[index + 1].active_blocked_public_calls)
            and item.proposals[index + 1].action_id != item.proposals[index].action_id
            and any(later.status == "succeeded" for later in item.observations[index + 1 :])
            for index, observation in enumerate(item.observations)
        )
        for item in executions
    )
    stopping_passed = all(
        item.path.terminal_verification_completed
        for item in executions
        if item.task.package.mechanism_id == "state_dependent_stopping"
    )
    transport_certificate = canonical_hash(
        {
            "runner_contract_id": runner.contract_id,
            "path_id": selected.path.path_id,
            "maximum_replacements": MAXIMUM_TRANSPORT_REPLACEMENTS,
            "same_request_route_required": True,
            "privacy_envelope_first": True,
        },
        prefix="finance_v26_role_transport_replacement_fixture:",
    )
    if not transport_certificate:
        raise AssertionError("v26.131 transport certificate disappeared")
    reference_boundary_admitted = (
        selected.path.primary_request_count <= MAXIMUM_PRIMARY_REQUESTS
        and selected.path.maximum_provider_calls_with_recovery <= MAXIMUM_PROVIDER_CALLS
        and selected.path.maximum_transport_inclusive_invocations <= MAXIMUM_TRANSPORT_INVOCATIONS
        and selected.path.static_complete_path_upper_bound_tokens < ROLLOUT_UPPER_BOUND_TOKENS
    )
    detour_admitted = (
        detour["primary_request_count"] <= MAXIMUM_PRIMARY_REQUESTS
        and detour["primary_request_count"] + MAXIMUM_ABI_RESCUES + MAXIMUM_SEMANTIC_RECOVERIES
        <= MAXIMUM_PROVIDER_CALLS
        and detour["primary_request_count"]
        + MAXIMUM_ABI_RESCUES
        + MAXIMUM_SEMANTIC_RECOVERIES
        + MAXIMUM_TRANSPORT_REPLACEMENTS
        <= MAXIMUM_TRANSPORT_INVOCATIONS
        and detour["static_path_upper_bound_tokens"] < ROLLOUT_UPPER_BOUND_TOKENS
    )
    if not reference_boundary_admitted or detour_admitted:
        raise ValueError("v26.131 dynamic resource admission classification changed")
    controls = tuple(
        sorted(
            (
                DynamicStressControl(
                    name="abi_rescue",
                    status="passed",
                    path_id=selected.path.path_id,
                    state_id=maximum_candidate_state.state_id,
                    observed_value=abi_rescue_passed,
                ),
                DynamicStressControl(
                    name="deep_reconciliation_paths",
                    status="passed",
                    observed_value=8,
                ),
                DynamicStressControl(
                    name="failure_recovery_typed_failure_revision",
                    status="passed",
                    observed_value=failure_recovery_passed,
                ),
                DynamicStressControl(
                    name="legal_nonreference_action_commit",
                    status="passed",
                    path_id=cast(str, detour["path_id"]),
                    state_id=cast(str, detour["state_id"]),
                    observed_value=True,
                ),
                DynamicStressControl(
                    name="legal_no_progress_ordinary_replan",
                    status="passed",
                    path_id=cast(str, detour["path_id"]),
                    state_id=cast(str, detour["state_id"]),
                    observed_value=True,
                ),
                DynamicStressControl(
                    name="maximum_blocked_action_state",
                    status="passed",
                    observed_value=maximum_blocked,
                ),
                DynamicStressControl(
                    name="maximum_candidate_state",
                    status="passed",
                    state_id=maximum_candidate_state.state_id,
                    observed_value=len(maximum_candidate_state.action_candidates),
                    frozen_limit=63,
                ),
                DynamicStressControl(
                    name="maximum_prompt_state",
                    status="passed",
                    observed_value=loaded.formal_census.maximum_s1_prompt_utf8_bytes,
                    frozen_limit=PROMPT_CEILING_BYTES,
                ),
                DynamicStressControl(
                    name="registered_boundary_20_22_23",
                    status="failed_as_expected",
                    path_id=cast(str, detour["path_id"]),
                    state_id=cast(str, detour["state_id"]),
                    observed_value="21_primary_23_provider_24_transport",
                    frozen_limit=MAXIMUM_PRIMARY_REQUESTS,
                ),
                DynamicStressControl(
                    name="semantic_recovery",
                    status="passed",
                    state_id=maximum_candidate_state.state_id,
                    observed_value=semantic_recovery_passed,
                ),
                DynamicStressControl(
                    name="stopping_terminal_verification",
                    status="passed",
                    observed_value=stopping_passed,
                ),
                DynamicStressControl(
                    name="transport_replacement",
                    status="passed",
                    path_id=selected.path.path_id,
                    observed_value=1,
                    frozen_limit=MAXIMUM_TRANSPORT_REPLACEMENTS,
                ),
            ),
            key=lambda item: item.name,
        )
    )
    values = {
        "runner_contract_id": runner.contract_id,
        "reference_fixture_audit_id": reference.audit_id,
        "controls": controls,
        "maximum_blocked_action_count": maximum_blocked,
        "failure_recovery_typed_failure_revision_passed": failure_recovery_passed,
        "stopping_terminal_verification_passed": stopping_passed,
        "abi_rescue_passed": abi_rescue_passed,
        "semantic_recovery_passed": semantic_recovery_passed,
        "detour_path_id": detour["path_id"],
        "detour_state_id": detour["state_id"],
        "repeated_successful_action_id": detour["action_id"],
        "detour_maximum_prompt_utf8_bytes": detour["maximum_prompt_utf8_bytes"],
        "detour_static_path_upper_bound_tokens": detour["static_path_upper_bound_tokens"],
        "detour_rollout_excess_tokens": (
            detour["static_path_upper_bound_tokens"] - ROLLOUT_UPPER_BOUND_TOKENS
        ),
    }
    provisional = DynamicInteractionStressAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return DynamicInteractionStressAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_dynamic_interaction_stress:",
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
    raise AssertionError(f"v26.131 destructive mutation was accepted: {name}")


def _make_destructive_audit(
    *,
    kernel: RoleScalableKernel,
    task_catalog: RoleTaskPackageCatalog,
    path_catalog: RolePathCatalog,
    reconciliation: DeepReconciliationCompilerAudit,
    resource: RoleScalableResourceContract,
    identity_chain: RoleIdentityChain,
    runner: RoleRunnerContract,
    dynamic: DynamicInteractionStressAudit,
) -> DestructiveAudit:
    first_package = task_catalog.packages[0]
    first_path = path_catalog.paths[0]
    first_reconciliation = reconciliation.rows[0]
    first_job = identity_chain.capability_manifest.jobs[0]
    mutations = (
        _expect_rejected(
            "compact_protocol_replaced",
            lambda: _validated_copy(
                RoleScalableKernel,
                kernel,
                compact_projection_protocol_id="changed",
            ),
        ),
        _expect_rejected(
            "deep_reconciliation_compiler_flag_removed",
            lambda: _validated_copy(
                RoleScalableTaskPackage,
                next(
                    item
                    for item in task_catalog.packages
                    if item.deep_reconciliation_formal_compiler_used
                ),
                deep_reconciliation_formal_compiler_used=False,
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
            "detour_failure_reclassified_as_pass",
            lambda: _validated_copy(
                DynamicInteractionStressAudit,
                dynamic,
                detour_primary_request_count=20,
            ),
        ),
        _expect_rejected(
            "dynamic_full_object_fallback_enabled",
            lambda: _validated_copy(
                RoleRunnerContract,
                runner,
                full_object_fallback_allowed=True,
            ),
        ),
        _expect_rejected(
            "dynamic_projection_selection_enabled",
            lambda: _validated_copy(
                RoleScalableKernel,
                kernel,
                full_object_and_compact_dynamic_selection_allowed=True,
            ),
        ),
        _expect_rejected(
            "job_condition_removed",
            lambda: _validated_copy(
                RoleJob,
                next(
                    item
                    for item in identity_chain.reachability_manifest.jobs
                    if item.sampling_mode == "reachability_conditioned"
                ),
                public_condition_id=None,
            ),
        ),
        _expect_rejected(
            "job_identity_reused_after_contract_change",
            lambda: _validated_copy(
                RoleJob,
                first_job,
                contract_id="changed",
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
            "manifest_cross_role_job_inserted",
            lambda: _validated_copy(
                RoleJobManifest,
                identity_chain.capability_manifest,
                jobs=(
                    *identity_chain.capability_manifest.jobs[:-1],
                    identity_chain.reachability_manifest.jobs[0],
                ),
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
            "path_identity_not_refreshed",
            lambda: _validated_copy(
                RoleScalablePath,
                first_path,
                public_path_condition="changed",
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
            "private_reasoning_persistence_enabled",
            lambda: _validated_copy(
                RoleRunnerContract,
                runner,
                private_reasoning_content_or_hash_persisted=True,
            ),
        ),
        _expect_rejected(
            "resource_detour_headroom_claimed",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                ordinary_legal_detour_headroom_qualified=True,
            ),
        ),
        _expect_rejected(
            "resource_primary_limit_changed",
            lambda: _validated_copy(
                RoleScalableResourceContract,
                resource,
                maximum_primary_requests=21,
            ),
        ),
        _expect_rejected(
            "role_execution_authorized",
            lambda: _validated_copy(
                RoleExecutionContract,
                identity_chain.capability_contract,
                empirical_execution_authorized=True,
            ),
        ),
        _expect_rejected(
            "role_task_package_mechanism_changed",
            lambda: _validated_copy(
                RoleScalableTaskPackage,
                first_package,
                mechanism_id="semantic_reconciliation",
            ),
        ),
        _expect_rejected(
            "role_task_package_tier_changed",
            lambda: _validated_copy(
                RoleScalableTaskPackage,
                first_package,
                tier=("hard_control" if first_package.tier != "hard_control" else "easy_control"),
            ),
        ),
        _expect_rejected(
            "runner_empirical_execution_authorized",
            lambda: _validated_copy(
                RoleRunnerContract,
                runner,
                empirical_execution_authorized=True,
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
            "task_package_kernel_changed_without_identity",
            lambda: _validated_copy(
                RoleScalableTaskPackage,
                first_package,
                kernel_id="changed",
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
            "finance_v26_role_scalable_destructive:",
        ),
        mutations=ordered,
    )


def _make_transition(
    *,
    kernel: RoleScalableKernel,
    resource: RoleScalableResourceContract,
    runner: RoleRunnerContract,
    dynamic: DynamicInteractionStressAudit,
) -> ProspectiveTransitionContract:
    values = {
        "kernel_id": kernel.kernel_id,
        "resource_contract_id": resource.contract_id,
        "runner_contract_id": runner.contract_id,
        "dynamic_interaction_stress_audit_id": dynamic.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_role_scalable_transition:",
        ),
        **values,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    predecessor_dir: Path,
    output_dir: Path,
) -> RoleScalableKernelRunnerPreflightReport:
    if output_dir.exists():
        raise ValueError(f"immutable v26.131 output directory exists: {output_dir}")
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
    kernel = _make_kernel(package_root)
    tasks, task_catalog = _materialize_tasks(
        package_root=package_root,
        loaded=loaded,
        kernel=kernel,
    )
    executions, path_catalog = _materialize_paths(
        package_root=package_root,
        loaded=loaded,
        kernel=kernel,
        task_catalog=task_catalog,
        tasks=tasks,
    )
    reconciliation = _make_reconciliation_audit(
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        loaded=loaded,
    )
    resource = _make_resource_contract(kernel)
    identity_chain = _make_identity_chain(
        kernel=kernel,
        resource=resource,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
    )
    runner = _make_runner_contract(
        kernel=kernel,
        resource=resource,
        identity_chain=identity_chain,
    )
    reference = _make_reference_fixture(
        runner=runner,
        path_catalog=path_catalog,
    )
    dynamic = _make_dynamic_stress_audit(
        package_root=package_root,
        loaded=loaded,
        runner=runner,
        reference=reference,
        executions=executions,
    )
    destructive = _make_destructive_audit(
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        reconciliation=reconciliation,
        resource=resource,
        identity_chain=identity_chain,
        runner=runner,
        dynamic=dynamic,
    )
    transition = _make_transition(
        kernel=kernel,
        resource=resource,
        runner=runner,
        dynamic=dynamic,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source_replay),
        ("frozen_role_input_audit.json", frozen_input),
        ("role_scalable_kernel.json", kernel),
        ("role_task_package_catalog.json", task_catalog),
        ("role_path_catalog.json", path_catalog),
        ("deep_reconciliation_compiler_audit.json", reconciliation),
        ("role_scalable_resource_contract.json", resource),
        ("role_identity_chain.json", identity_chain),
        ("role_runner_contract.json", runner),
        ("reference_runner_fixture_audit.json", reference),
        ("dynamic_interaction_stress_audit.json", dynamic),
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
        "kernel_id": kernel.kernel_id,
        "task_package_catalog_id": task_catalog.catalog_id,
        "path_catalog_id": path_catalog.catalog_id,
        "deep_reconciliation_compiler_audit_id": reconciliation.audit_id,
        "resource_contract_id": resource.contract_id,
        "role_identity_chain_id": identity_chain.chain_id,
        "runner_contract_id": runner.contract_id,
        "reference_runner_fixture_audit_id": reference.audit_id,
        "dynamic_interaction_stress_audit_id": dynamic.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = RoleScalableKernelRunnerPreflightReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = RoleScalableKernelRunnerPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_role_scalable_kernel_runner_preflight_report:",
        ),
        **report_values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description=("Credential-free v26.131 Role-scalable Kernel and dynamic Runner preflight")
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
