from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as engineering_static,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as action_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_rematerialization as engineering,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponsePayload,
    ExactFinalResponseRejection,
    FinalResponseHostEnvelope,
    exact_final_response_payload,
    make_final_response_host_envelope,
    parse_exact_final_response_payload,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    CanonicalActionProposal,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
    make_canonical_action_proposal,
    prompt_only_reference_proposal,
    render_semantic_action_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_133_s1_representation_qualification_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_133_s1_representation_qualification_preflight_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_representation_qualification_preflight.py"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
ENGINEERING_SOURCE_DIR: Final = engineering_static.OUTPUT_DIR
NEXT_STAGE: Final = "s1_model_visible_representation_qualification_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_133_s1_representation_qualification_runner_v1_20260824"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_134_s1_representation_qualification_execution_v1_20260824"
)

PREDECESSOR_OUTPUT_NAMES: Final = (
    "bounded_dynamic_resource_contract.json",
    "bounded_dynamic_role_kernel.json",
    "bounded_dynamic_runner_contract.json",
    "bounded_dynamic_runner_preflight_audit.json",
    "deep_reconciliation_compiler_audit.json",
    "destructive_audit.json",
    "dynamic_trajectory_envelope_audit.json",
    "frozen_role_input_audit.json",
    "ordinary_detour_policy.json",
    "prospective_transition_contract.json",
    "reference_runner_fixture_audit.json",
    "report.json",
    "role_identity_chain.json",
    "role_path_catalog.json",
    "role_task_package_catalog.json",
    "source_replay_audit.json",
)

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_bounded_dynamic_role_preflight_report:"
    "cb509fe5dfed2ef5c399dc9781852c873b08f028960abf0e086124db6b67cb06"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "e60444665db0da325ced6427fd07a11139d2db8ba99cbca0b02b00db461ed2f9"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_bounded_dynamic_transition:"
    "819c102985dfb244e62bb05ceb46215b8c0a008dd8d4f69a12f821c8e4b1237a"
)
EXPECTED_PREDECESSOR_TRANSITION_SHA256: Final = (
    "8e3cce14e06518256297718551694fabc57898bed99e9dff8ad8f22ca2c6ac8e"
)
EXPECTED_PREDECESSOR_KERNEL_ID: Final = (
    "finance_v26_bounded_dynamic_role_kernel:"
    "6b40395f55211b036f570a53f7c89f157844c819cc7c0533c721f78465e3186c"
)
EXPECTED_PREDECESSOR_RESOURCE_ID: Final = (
    "finance_v26_bounded_dynamic_resource_contract:"
    "addc8f6b01bc1111dc23ee176b440518cc1016087c0e20669d1ae9ee5be97820"
)
EXPECTED_PREDECESSOR_POLICY_ID: Final = (
    "finance_v26_bounded_dynamic_interaction_policy:"
    "43126b403dd060baade1e5994306982159b02a0451865a9fda2c54da3fda2b0b"
)
EXPECTED_PREDECESSOR_RUNNER_ID: Final = (
    "finance_v26_bounded_dynamic_runner_contract:"
    "06a317c786050d812fc6ffafac9e0d7560c335f3b6742697d08ed413b798fd76"
)
EXPECTED_ENGINEERING_REPORT_ID: Final = (
    "finance_v26_final_grammar_rematerialization_report:"
    "d33708c242c6b6779c1f3e3c3911f4235abad570363478ab79e82617a37a971c"
)
EXPECTED_ENGINEERING_CONTRACT_ID: Final = (
    "finance_v26_final_grammar_execution_contract:"
    "5532a1f1ca600979f7541770606e7ce0a3b65c4a93f88a659e52e14ff7d6e27e"
)
EXPECTED_ENGINEERING_MANIFEST_ID: Final = (
    "finance_v26_final_grammar_manifest:"
    "fd4d78efa9374fc3de91ccca1a8242b7a6bee4bdcf4052ac8bbf6428bd95a5ee"
)
EXPECTED_ENGINEERING_RESOURCE_ID: Final = (
    "finance_v26_final_grammar_resource_contract:"
    "381e18dff5a538c50cc06aaae9c6c81d110d8214b8c7d3800820d4eb3f09e43c"
)
EXPECTED_S1_CANDIDATE_ID: Final = predecessor.EXPECTED_S1_CANDIDATE_ID
EXPECTED_COMPACT_PROTOCOL_ID: Final = predecessor.EXPECTED_COMPACT_PROTOCOL_ID
EXPECTED_ACTION_PROTOCOL_ID: Final = predecessor.EXPECTED_ACTION_PROTOCOL_ID
EXPECTED_ACTION_GRAMMAR_ID: Final = predecessor.EXPECTED_ACTION_GRAMMAR_ID
EXPECTED_FINAL_GRAMMAR_ID: Final = predecessor.EXPECTED_FINAL_GRAMMAR_ID
EXPECTED_STAGE_ONE_PROFILE_ID: Final = predecessor.EXPECTED_STAGE_ONE_PROFILE_ID
EXPECTED_STAGE_TWO_PROFILE_ID: Final = predecessor.EXPECTED_STAGE_TWO_PROFILE_ID
EXPECTED_MODEL_CONFIG_ID: Final = predecessor.EXPECTED_MODEL_CONFIG_ID
EXPECTED_THINKING_BINDING_ID: Final = predecessor.EXPECTED_THINKING_BINDING_ID
EXPECTED_CAPABILITY_POPULATION_ID: Final = predecessor.EXPECTED_CAPABILITY_POPULATION_ID
EXPECTED_REACHABILITY_POPULATION_ID: Final = predecessor.EXPECTED_REACHABILITY_POPULATION_ID

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
QUALIFICATION_JOB_COUNT: Final = 32
QUALIFICATION_TASK_COUNT: Final = 24
QUALIFICATION_PATH_COUNT: Final = 48
QUALIFICATION_STATE_COUNT: Final = 324
FIRST_ACTION_INTERFACE_MINIMUM: Final = 24
CELL_COVERAGE_MINIMUM: Final = 12
ROLE_CLASS_EXTERNAL_ACTION_COUNT: Final = 252

EXPECTED_DETOUR_PATH_ID: Final = (
    "finance_v26_final_grammar_path_audit:"
    "71744c11ae4a909d91b2c72e720287c254c22c7d15fae0c86e50d2391101ec29"
)
EXPECTED_DETOUR_STATE_ID: Final = (
    "prospective_semantic_action_state:"
    "5e68a00072bbea311b3a41ae656dd40a38a156fe96b9e770ff4215dc9e77765e"
)
EXPECTED_DETOUR_ACTION_ID: Final = (
    "prospective_canonical_public_action:"
    "25c471638ac6f85814331707d9b4a675c9d9e5a1a91e1519d7ce956f321c31b6"
)

SOURCE_CHANNELS: Final = (
    "source_task_artifact_id",
    "public_task_id",
    "semantic_source_id",
    "operational_record_id",
    "operational_task_package_id",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
)
PROGRESS_VECTOR_COMPONENTS: Final = (
    "unresolved_symbols",
    "operation_frontier_node_status_pairs",
    "terminal_operation_ref",
    "terminal_verification_completed",
    "final_answer_allowed",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_json_bytes(value) + b"\n")
    temporary.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    raise ValueError(f"v26.133 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_132_transitive_source",
        "v26_132_output",
        "v26_133_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(gt=0)
    mismatch_count: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_source_replay.v1"] = (
        "finance_v26_s1_qualification_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        if (
            self.replayed_file_count != len(self.entries)
            or len({item.relative_path for item in self.entries}) != len(self.entries)
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.133 source replay changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_source_replay:"
        ):
            raise ValueError("v26.133 source replay identity changed")
        return self


class FrozenPredecessorBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    bounded_dynamic_kernel_id: str = EXPECTED_PREDECESSOR_KERNEL_ID
    bounded_dynamic_resource_contract_id: str = EXPECTED_PREDECESSOR_RESOURCE_ID
    ordinary_detour_policy_id: str = EXPECTED_PREDECESSOR_POLICY_ID
    bounded_dynamic_runner_contract_id: str = EXPECTED_PREDECESSOR_RUNNER_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    reachability_population_id: str = EXPECTED_REACHABILITY_POPULATION_ID
    role_task_package_count: Literal[24] = 24
    role_path_count: Literal[48] = 48
    role_job_count: Literal[456] = 456
    s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    prompt_ceiling_bytes: Literal[60000] = 60000
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    rollout_upper_bound_tokens: Literal[1120000] = 1120000
    completion_request_bound_tokens: Literal[16384] = 16384
    maximum_abi_rescues: Literal[1] = 1
    maximum_semantic_recoveries: Literal[1] = 1
    maximum_transport_replacements: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    frozen_role_source_model_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_predecessor_binding.v1"] = (
        "finance_v26_s1_qualification_predecessor_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenPredecessorBindingAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_predecessor_binding:"
        ):
            raise ValueError("v26.133 predecessor binding identity changed")
        return self


class SeparationChannelRow(FrozenModel):
    channel: Literal[
        "source_task_artifact_id",
        "public_task_id",
        "semantic_source_id",
        "operational_record_id",
        "operational_task_package_id",
        "evidence_id",
        "evidence_version_id",
        "source_record_id",
    ]
    engineering_identity_count: int = Field(gt=0)
    role_identity_count: int = Field(gt=0)
    overlap_count: Literal[0] = 0


class QualificationSourceSeparationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    engineering_report_id: str = EXPECTED_ENGINEERING_REPORT_ID
    engineering_contract_id: str = EXPECTED_ENGINEERING_CONTRACT_ID
    engineering_manifest_id: str = EXPECTED_ENGINEERING_MANIFEST_ID
    engineering_resource_contract_id: str = EXPECTED_ENGINEERING_RESOURCE_ID
    engineering_task_package_count: Literal[24] = 24
    engineering_path_count: Literal[48] = 48
    engineering_predecessor_job_count: Literal[32] = 32
    engineering_source_model_exposed_count: Literal[24] = 24
    engineering_source_permanently_role_ineligible_count: Literal[24] = 24
    frozen_role_source_count: Literal[24] = 24
    frozen_role_source_model_exposure_count: Literal[0] = 0
    separation_channels: tuple[SeparationChannelRow, ...] = Field(min_length=8, max_length=8)
    role_class_external_action_count: Literal[252] = 252
    role_class_external_state_action_set_sha256: str = Field(min_length=64, max_length=64)
    engineering_state_overlap_with_role_class_external_states: Literal[0] = 0
    qualification_rows_capability_eligible: Literal[False] = False
    qualification_rows_reachability_eligible: Literal[False] = False
    qualification_rows_state_mapping_eligible: Literal[False] = False
    role_tasks_used_by_qualification_jobs: Literal[0] = 0
    role_external_frequency_has_online_opportunity_in_engineering_denominator: Literal[False] = (
        False
    )
    role_external_frequency_deferred_to_role_execution: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_source_separation.v1"] = (
        "finance_v26_s1_qualification_source_separation.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> QualificationSourceSeparationAudit:
        if tuple(item.channel for item in self.separation_channels) != SOURCE_CHANNELS or any(
            item.overlap_count for item in self.separation_channels
        ):
            raise ValueError("v26.133 engineering/role source separation changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_source_separation:"
        ):
            raise ValueError("v26.133 source-separation identity changed")
        return self


class PublicProgressVectorContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_policy_id: str = EXPECTED_PREDECESSOR_POLICY_ID
    component_order: tuple[str, ...] = PROGRESS_VECTOR_COMPONENTS
    unresolved_symbols_representation: Literal["ordered_public_tuple"] = "ordered_public_tuple"
    operation_frontier_representation: Literal["ordered_node_id_frontier_status_pairs"] = (
        "ordered_node_id_frontier_status_pairs"
    )
    terminal_operation_ref_nullable: Literal[True] = True
    terminal_verification_completed_boolean: Literal[True] = True
    final_answer_allowed_boolean: Literal[True] = True
    comparison_rule: Literal["canonical_componentwise_equality"] = (
        "canonical_componentwise_equality"
    )
    progress_requires_successful_public_observation: Literal[True] = True
    successful_observation_with_changed_vector_is_progress: Literal[True] = True
    successful_observation_with_unchanged_vector_is_detour_candidate: Literal[True] = True
    ordinary_detour_requires_non_reference_action: Literal[True] = True
    reference_action_from_frozen_public_ordinary_replan_policy: Literal[True] = True
    reference_policy_is_measurement_classifier_not_host_choice: Literal[True] = True
    failed_observation_is_ordinary_detour: Literal[False] = False
    retrieval_result_outside_components_is_diagnostic_only: Literal[True] = True
    unchanged_vector_means_action_useless: Literal[False] = False
    ordinary_detour_counted_after_tool_observation: Literal[True] = True
    second_detour_terminal_before_later_provider: Literal[True] = True
    schema_version: Literal["finance_v26_public_progress_vector_contract.v1"] = (
        "finance_v26_public_progress_vector_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PublicProgressVectorContract:
        if self.component_order != PROGRESS_VECTOR_COMPONENTS:
            raise ValueError("v26.133 public Progress Vector schema changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_public_progress_vector_contract:"
        ):
            raise ValueError("v26.133 Progress Vector Contract identity changed")
        return self


class S1StateBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    logical_state_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    candidate_count: int = Field(gt=0)
    presented_action_ids: tuple[str, ...] = Field(min_length=1)
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    abi_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    semantic_recovery_prompt_sha256: str = Field(min_length=64, max_length=64)
    primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    reference_action_id: str = Field(min_length=1)
    reference_decision_kind: str = Field(min_length=1)
    reversible_commit_id: str = Field(min_length=1)
    exact_state_reconstruction_passed: Literal[True] = True
    exact_candidate_set_and_order_passed: Literal[True] = True
    exact_reference_proposal_passed: Literal[True] = True
    exact_stage_two_commit_passed: Literal[True] = True
    full_object_fallback_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> S1StateBindingRow:
        if len(self.presented_action_ids) != self.candidate_count:
            raise ValueError("v26.133 S1 Candidate presentation changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_s1_qualification_state_binding:"):
            raise ValueError("v26.133 S1 state-row identity changed")
        return self


class S1QualificationPathAudit(FrozenModel):
    path_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    engineering_task_package_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    state_rows: tuple[S1StateBindingRow, ...] = Field(min_length=1)
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    primary_request_count: int = Field(gt=0, le=21)
    provider_call_count_with_recoveries: int = Field(gt=0, le=23)
    transport_inclusive_invocation_count: int = Field(gt=0, le=24)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, le=1120000)
    program_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_commit_reached: Literal[True] = True
    role_evidence_eligible: Literal[False] = False

    @model_validator(mode="after")
    def validate_path(self) -> S1QualificationPathAudit:
        if (
            self.primary_request_count != len(self.state_rows) + 1
            or self.provider_call_count_with_recoveries
            != self.primary_request_count + MAXIMUM_ABI_RESCUES + MAXIMUM_SEMANTIC_RECOVERIES
            or self.transport_inclusive_invocation_count
            != self.provider_call_count_with_recoveries + MAXIMUM_TRANSPORT_REPLACEMENTS
        ):
            raise ValueError("v26.133 S1 qualification path accounting changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_s1_qualification_path:"):
            raise ValueError("v26.133 S1 qualification Path identity changed")
        return self


class S1QualificationPathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    paths: tuple[S1QualificationPathAudit, ...] = Field(min_length=48, max_length=48)
    path_count: Literal[48] = 48
    state_count: Literal[324] = 324
    primary_reconstruction_pass_count: Literal[324] = 324
    abi_rescue_reconstruction_pass_count: Literal[324] = 324
    semantic_recovery_reconstruction_pass_count: Literal[324] = 324
    reversible_commit_pass_count: Literal[324] = 324
    maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_registered_path_static_tokens: int = Field(gt=0, le=1120000)
    full_object_fallback_count: Literal[0] = 0
    model_outcomes_used: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_path_catalog.v1"] = (
        "finance_v26_s1_qualification_path_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> S1QualificationPathCatalog:
        if (
            len(self.paths) != self.path_count
            or len({item.path_id for item in self.paths}) != self.path_count
            or sum(len(item.state_rows) for item in self.paths) != self.state_count
        ):
            raise ValueError("v26.133 S1 qualification Path denominator changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_s1_qualification_path_catalog:"
        ):
            raise ValueError("v26.133 S1 Path Catalog identity changed")
        return self


class S1QualificationResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_resource_contract_id: str = EXPECTED_PREDECESSOR_RESOURCE_ID
    prompt_upper_bound_bytes: Literal[60000] = 60000
    chat_envelope_tokens: Literal[256] = 256
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    accounted_completion_bound_tokens: Literal[16385] = 16385
    rollout_upper_bound_tokens: Literal[1120000] = 1120000
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    qualified_maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_registered_path_static_tokens: int = Field(gt=0, le=1120000)
    role_bounded_dynamic_maximum_static_tokens: Literal[1091306] = 1091306
    role_selected_headroom_tokens: Literal[28694] = 28694
    resource_values_changed_from_v26_132: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_s1_qualification_resource_contract.v1"] = (
        "finance_v26_s1_qualification_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> S1QualificationResourceContract:
        if (
            self.accounted_completion_bound_tokens
            != self.exact_request_completion_bound_tokens + self.provider_accounting_margin_tokens
            or self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests
            + self.maximum_abi_rescue_calls
            + self.maximum_semantic_recovery_calls
            or self.maximum_transport_inclusive_invocations
            != self.maximum_stage_one_provider_calls + self.maximum_transport_replacement_calls
        ):
            raise ValueError("v26.133 qualification resource arithmetic changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_qualification_resource_contract:"
        ):
            raise ValueError("v26.133 qualification Resource identity changed")
        return self


class S1RepresentationQualificationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_kernel_id: str = EXPECTED_PREDECESSOR_KERNEL_ID
    predecessor_resource_contract_id: str = EXPECTED_PREDECESSOR_RESOURCE_ID
    predecessor_policy_id: str = EXPECTED_PREDECESSOR_POLICY_ID
    source_separation_audit_id: str = Field(min_length=1)
    progress_vector_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    engineering_source_contract_id: str = EXPECTED_ENGINEERING_CONTRACT_ID
    engineering_source_manifest_id: str = EXPECTED_ENGINEERING_MANIFEST_ID
    qualification_object: Literal["flash_model_visible_s1_representation_usability"] = (
        "flash_model_visible_s1_representation_usability"
    )
    exact_job_denominator: Literal[32] = 32
    engineering_task_count: Literal[24] = 24
    engineering_path_count: Literal[48] = 48
    static_state_count: Literal[324] = 324
    first_action_interface_minimum_jobs: Literal[24] = 24
    required_mechanism_path_cell_coverage: Literal[12] = 12
    first_action_interface_definition: tuple[str, ...] = (
        "exact_four_field_action_abi",
        "current_state_binding",
        "visible_candidate_id_binding",
        "decision_kind_binding",
        "reversible_same_action_stage_two_commit",
    )
    program_progress_final_answer_and_independent_validity_are_separate: Literal[True] = True
    detour_terminal_is_measurement_support_exit: Literal[True] = True
    full_object_dynamic_fallback_authorized: Literal[False] = False
    role_task_provider_exposure_authorized: Literal[False] = False
    qualification_rows_role_or_state_eligible: Literal[False] = False
    task_or_s1_selection_from_future_outcomes_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_s1_representation_qualification_contract.v1"] = (
        "finance_v26_s1_representation_qualification_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> S1RepresentationQualificationContract:
        if (
            self.first_action_interface_minimum_jobs != FIRST_ACTION_INTERFACE_MINIMUM
            or self.required_mechanism_path_cell_coverage != CELL_COVERAGE_MINIMUM
        ):
            raise ValueError("v26.133 pre-registered representation Gate changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_representation_qualification_contract:"
        ):
            raise ValueError("v26.133 qualification Contract identity changed")
        return self


class S1QualificationJob(FrozenModel):
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    path_audit_id: str = Field(min_length=1)
    predecessor_path_audit_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    stage_one_profile_id: str = EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = EXPECTED_STAGE_TWO_PROFILE_ID
    semantic_action_protocol_id: str = EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = EXPECTED_FINAL_GRAMMAR_ID
    compact_projection_protocol_id: str = EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = EXPECTED_S1_CANDIDATE_ID
    resource_contract_id: str = Field(min_length=1)
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    source_model_exposed_before_freeze: Literal[True] = True
    engineering_qualification_only: Literal[True] = True
    capability_reachability_state_or_release_eligible: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_s1_qualification_job.v1"] = (
        "finance_v26_s1_qualification_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> S1QualificationJob:
        if self.job_id != _identity(self, "job_id", "finance_v26_s1_qualification_job:"):
            raise ValueError("v26.133 qualification Job identity changed")
        return self


class S1QualificationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    predecessor_manifest_id: str = EXPECTED_ENGINEERING_MANIFEST_ID
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    jobs: tuple[S1QualificationJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_strategy_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_engineering_task_count: Literal[24] = 24
    exact_denominator: Literal[32] = 32
    predecessor_job_identity_overlap_count: Literal[0] = 0
    frozen_role_job_identity_overlap_count: Literal[0] = 0
    role_source_job_count: Literal[0] = 0
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_s1_qualification_manifest.v1"] = (
        "finance_v26_s1_qualification_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> S1QualificationManifest:
        if (
            len(self.jobs) != self.exact_denominator
            or len({item.job_id for item in self.jobs}) != self.exact_denominator
            or len({item.task_package_id for item in self.jobs})
            != self.distinct_engineering_task_count
            or len(self.cell_job_counts) != CELL_COVERAGE_MINIMUM
        ):
            raise ValueError("v26.133 qualification Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_s1_qualification_manifest:"
        ):
            raise ValueError("v26.133 qualification Manifest identity changed")
        return self


class S1QualificationOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_denominator: Literal[32] = 32
    gate_selected_before_qualification_outcomes: Literal[True] = True
    first_action_interface_minimum_jobs: Literal[24] = 24
    required_cell_coverage: Literal[12] = 12
    instrument_privacy_model_thinking_or_usage_failure_tolerance: Literal[0] = 0
    typed_terminals: tuple[str, ...] = (
        "completed_model_result",
        "model_result_failure",
        "typed_semantic_rejection",
        "ordinary_detour_allowance_exhausted",
        "typed_budget_no_call",
        "provider_transport_failure",
        "instrument_failure",
    )
    detour_terminal_counts_as_model_invalid: Literal[False] = False
    detour_terminal_counts_as_measurement_support_exit: Literal[True] = True
    exact_final_abi_and_answer_validity_reported_separately: Literal[True] = True
    zero_role_capability_reachability_state_mapping_rows: Literal[True] = True
    pass_authorizes_role_execution: Literal[False] = False
    pass_requires_independent_postrun_audit_before_role_transition: Literal[True] = True
    failure_authorizes_only_representation_root_cause_audit: Literal[True] = True
    schema_version: Literal["finance_v26_s1_qualification_outcome_contract.v1"] = (
        "finance_v26_s1_qualification_outcome_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> S1QualificationOutcomeContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_qualification_outcome_contract:"
        ):
            raise ValueError("v26.133 Outcome Contract identity changed")
        return self


class S1QualificationRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    progress_vector_contract_id: str = Field(min_length=1)
    runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    exact_job_denominator: Literal[32] = 32
    stage_one_profile_id: str = EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = EXPECTED_FINAL_GRAMMAR_ID
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    rollout_upper_bound_tokens: Literal[1120000] = 1120000
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    all_four_counters_independent: Literal[True] = True
    s1_only_model_visible_action_prompts: Literal[True] = True
    full_object_fallback_allowed: Literal[False] = False
    privacy_redacted_envelope_before_public_projection: Literal[True] = True
    invalid_payload_or_private_reasoning_persisted: Literal[False] = False
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    second_detour_terminal_after_observation_before_later_provider: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_s1_qualification_runner_contract.v1"] = (
        "finance_v26_s1_qualification_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> S1QualificationRunnerContract:
        if (
            self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests
            + self.maximum_abi_rescue_calls
            + self.maximum_semantic_recovery_calls
            or self.maximum_transport_inclusive_invocations
            != self.maximum_stage_one_provider_calls + self.maximum_transport_replacement_calls
        ):
            raise ValueError("v26.133 Runner counter bounds changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_qualification_runner_contract:"
        ):
            raise ValueError("v26.133 Runner Contract identity changed")
        return self


class TransportInvocationCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    inner_dynamic_certificate_id: str = Field(min_length=1)
    request_binding_certificate_id: str = Field(min_length=1)
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    transport_invocation_index: int = Field(ge=0, le=23)
    provider_calls_before_invocation: int = Field(ge=0, le=23)
    abi_rescue_count_before: int = Field(ge=0, le=1)
    semantic_recovery_count_before: int = Field(ge=0, le=1)
    transport_replacement_count_before: int = Field(ge=0, le=1)
    ordinary_detour_count_before: int = Field(ge=0, le=2)
    is_transport_replacement: bool
    exact_same_prepared_request_as_failed_transport: bool
    persisted_before_transport_invocation: Literal[True] = True
    stage_two_provider_calls_before_invocation: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_transport_invocation_certificate.v1"] = (
        "finance_v26_s1_transport_invocation_certificate.v1"
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> TransportInvocationCertificate:
        if self.is_transport_replacement != (self.transport_replacement_count_before == 1):
            raise ValueError("v26.133 Transport Replacement counter changed")
        if self.certificate_id != _identity(
            self, "certificate_id", "finance_v26_s1_transport_invocation_certificate:"
        ):
            raise ValueError("v26.133 Transport certificate identity changed")
        return self


class PublicProgressEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    logical_request_index: int = Field(ge=0)
    state_id_before: str = Field(min_length=1)
    state_id_after: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    reference_action_id: str = Field(min_length=1)
    selected_action_matches_reference: bool
    observation_succeeded: bool
    progress_vector_changed: bool
    ordinary_detour_observed: bool
    ordinary_detour_count_after: int = Field(ge=0, le=2)
    diagnostic_public_state_changed_outside_progress_vector: bool
    schema_version: Literal["finance_v26_s1_public_progress_event.v1"] = (
        "finance_v26_s1_public_progress_event.v1"
    )

    @model_validator(mode="after")
    def validate_event(self) -> PublicProgressEvent:
        if self.selected_action_matches_reference != (
            self.selected_action_id == self.reference_action_id
        ):
            raise ValueError("v26.133 reference-action diagnostic binding changed")
        if self.ordinary_detour_observed != (
            self.observation_succeeded
            and not self.progress_vector_changed
            and not self.selected_action_matches_reference
        ):
            raise ValueError("v26.133 Ordinary Detour classification changed")
        if self.event_id != _identity(self, "event_id", "finance_v26_s1_public_progress_event:"):
            raise ValueError("v26.133 Progress event identity changed")
        return self


QualificationTerminal = Literal[
    "completed_model_result",
    "model_result_failure",
    "typed_semantic_rejection",
    "ordinary_detour_allowance_exhausted",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class S1QualificationRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: S1QualificationJob
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    provider_envelope_artifacts: tuple[legacy.RawFileDescriptor, ...]
    public_payload_projection_artifacts: tuple[legacy.RawFileDescriptor, ...]
    transport_invocation_artifacts: tuple[legacy.RawFileDescriptor, ...]
    provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[privacy_runner.PrivacyFirstAttempt, ...]
    semantic_choices: tuple[action_execution.SemanticChoiceRecord, ...]
    commits: tuple[action_execution.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    progress_events: tuple[PublicProgressEvent, ...]
    completed_result: privacy_runner.PrivacyFirstCompletedResult | None = None
    terminal_disposition: QualificationTerminal
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    cumulative_provider_tokens: int = Field(ge=0, le=1120000)
    stage_one_provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    transport_replacement_attempt_count: int = Field(ge=0, le=1)
    ordinary_detour_count: int = Field(ge=0, le=2)
    privacy_rejected_payload_count: int = Field(ge=0)
    exact_four_field_action_payload_count: int = Field(ge=0)
    exact_two_field_final_payload_count: int = Field(ge=0, le=1)
    first_action_interface_qualified: bool
    role_class_external_action_opportunity_count: Literal[0] = 0
    role_class_external_action_selected_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    capability_reachability_state_mapping_eligible: Literal[False] = False
    later_provider_calls_after_detour_terminal: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_raw_execution.v1"] = (
        "finance_v26_s1_qualification_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_raw(self) -> S1QualificationRawExecution:
        if (
            len(self.provider_envelope_artifacts) != self.stage_one_provider_call_count
            or len(self.public_payload_projection_artifacts) != self.stage_one_provider_call_count
            or len(self.provider_telemetry) != self.stage_one_provider_call_count
            or len(self.transport_invocation_artifacts) != self.transport_inclusive_invocation_count
            or self.transport_replacement_attempt_count
            != self.transport_inclusive_invocation_count - self.stage_one_provider_call_count
        ):
            raise ValueError("v26.133 Raw Provider denominator changed")
        if self.terminal_disposition == "ordinary_detour_allowance_exhausted":
            if self.ordinary_detour_count != 2 or self.completed_result is not None:
                raise ValueError("v26.133 second-Detour terminal changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_s1_qualification_raw_execution:"
        ):
            raise ValueError("v26.133 Raw identity changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    scripted_job_count: Literal[32] = 32
    completed_job_count: Literal[32] = 32
    first_action_interface_qualified_count: Literal[32] = 32
    covered_mechanism_path_cell_count: Literal[12] = 12
    semantic_action_primary_count: Literal[224] = 224
    exact_four_field_action_payload_count: Literal[224] = 224
    reversible_commit_count: Literal[224] = 224
    public_observation_count: Literal[192] = 192
    final_primary_count: Literal[32] = 32
    exact_two_field_final_payload_count: Literal[32] = 32
    privacy_envelope_count: Literal[256] = 256
    public_projection_count: Literal[256] = 256
    envelope_before_projection_pass_count: Literal[256] = 256
    s1_action_prompt_count: Literal[224] = 224
    full_object_action_prompt_count: Literal[0] = 0
    raw_recovery_pass_count: Literal[32] = 32
    role_source_job_count: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)
    scripted_local_calls: Literal[256] = 256
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_runner_fixture.v1"] = (
        "finance_v26_s1_qualification_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_runner_fixture:"
        ):
            raise ValueError("v26.133 Runner fixture identity changed")
        return self


class RunnerControlRow(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    passed: Literal[True] = True
    metrics: dict[str, Any]

    @model_validator(mode="after")
    def validate_row(self) -> RunnerControlRow:
        if self.control_id != _identity(
            self, "control_id", "finance_v26_s1_qualification_runner_control_row:"
        ):
            raise ValueError("v26.133 Runner control identity changed")
        return self


class RunnerControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerControlRow, ...] = Field(min_length=13, max_length=13)
    control_count: Literal[13] = 13
    passed_control_count: Literal[13] = 13
    repeatable_detour_path_id: str = EXPECTED_DETOUR_PATH_ID
    repeatable_detour_state_id: str = EXPECTED_DETOUR_STATE_ID
    repeatable_detour_action_id: str = EXPECTED_DETOUR_ACTION_ID
    one_detour_completed: Literal[True] = True
    second_detour_terminal: Literal["ordinary_detour_allowance_exhausted"] = (
        "ordinary_detour_allowance_exhausted"
    )
    second_detour_model_proposal_observed: Literal[True] = True
    second_detour_tool_observation_observed: Literal[True] = True
    later_provider_calls_after_second_detour: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_runner_control_audit.v1"] = (
        "finance_v26_s1_qualification_runner_control_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerControlAudit:
        if (
            len(self.rows) != self.control_count
            or sum(item.passed for item in self.rows) != self.passed_control_count
        ):
            raise ValueError("v26.133 Runner controls changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_runner_control_audit:"
        ):
            raise ValueError("v26.133 Runner control audit identity changed")
        return self


class MutationResult(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=24, max_length=24)
    mutation_count: Literal[24] = 24
    rejection_count: Literal[24] = 24
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_s1_qualification_destructive.v1"] = (
        "finance_v26_s1_qualification_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len(self.mutations) != self.mutation_count:
            raise ValueError("v26.133 destructive denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_s1_qualification_destructive:"
        ):
            raise ValueError("v26.133 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    next_permitted_stage: str = NEXT_STAGE
    exact_manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    only_exact_fresh_32_job_engineering_manifest_authorized: Literal[True] = True
    provider_calls_authorized: Literal[True] = True
    role_provider_calls_authorized: Literal[False] = False
    capability_reachability_execution_authorized: Literal[False] = False
    role_state_mapping_training_release_or_production_authorized: Literal[False] = False
    full_object_fallback_or_s1_change_authorized: Literal[False] = False
    task_candidate_model_thinking_grammar_resource_or_counter_change_authorized: Literal[False] = (
        False
    )
    qualification_rows_role_or_state_eligible: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    status: Literal["passed_s1_qualification_runner_preflight"] = (
        "passed_s1_qualification_runner_preflight"
    )
    schema_version: Literal["finance_v26_s1_qualification_transition.v1"] = (
        "finance_v26_s1_qualification_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_s1_qualification_transition:"
        ):
            raise ValueError("v26.133 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class S1QualificationPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_binding_audit_id: str = Field(min_length=1)
    source_separation_audit_id: str = Field(min_length=1)
    progress_vector_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=14, max_length=14)
    engineering_task_count: Literal[24] = 24
    qualification_path_count: Literal[48] = 48
    static_state_count: Literal[324] = 324
    qualification_job_count: Literal[32] = 32
    scripted_fixture_job_count: Literal[32] = 32
    scripted_fixture_call_count: Literal[256] = 256
    first_action_interface_fixture_pass_count: Literal[32] = 32
    role_task_provider_exposure_count: Literal[0] = 0
    role_class_external_action_count_retained: Literal[252] = 252
    qualification_execution_authorized: Literal[False] = False
    qualification_execution_performed: Literal[False] = False
    role_execution_authorized: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["s1_representation_qualification_runner_preflight_passed"] = (
        "s1_representation_qualification_runner_preflight_passed"
    )
    schema_version: Literal["finance_v26_s1_qualification_preflight_report.v1"] = (
        "finance_v26_s1_qualification_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> S1QualificationPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_s1_qualification_preflight_report:"
        ):
            raise ValueError("v26.133 report identity changed")
        return self


@dataclass(frozen=True)
class _LoadedInputs:
    predecessor_report: predecessor.BoundedDynamicRolePreflightReport
    predecessor_transition: predecessor.ProspectiveTransitionContract
    predecessor_resource: predecessor.RoleScalableResourceContract
    predecessor_policy: predecessor.OrdinaryDetourPolicy
    predecessor_role_tasks: predecessor.RoleTaskPackageCatalog
    predecessor_dynamic: predecessor.DynamicTrajectoryEnvelopeAudit
    engineering: engineering_static.FinalGrammarStaticInputs
    engineering_materials: tuple[Any, ...]
    final_materials: tuple[Any, ...]


@dataclass(frozen=True)
class _CallOutcome:
    attempt: privacy_runner.PrivacyFirstAttempt
    payload: dict[str, Any] | None = None
    proposal: CanonicalActionProposal | None = None
    final_payload: ExactFinalResponsePayload | None = None


class _TransportReplacementExhausted(RuntimeError):
    pass


class _TransportInvocationLimit(RuntimeError):
    pass


def _raw_path(output_dir: Path, job: S1QualificationJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def _invocation_path(output_dir: Path, job: S1QualificationJob, index: int) -> Path:
    return (
        output_dir
        / "transport_invocation_certificates"
        / job.job_id.rsplit(":", 1)[-1]
        / f"invocation_{index:03d}.json"
    )


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


class _TransportAwareDelegate:
    def __init__(
        self,
        delegate: Any,
        *,
        runner_contract: S1QualificationRunnerContract,
        job: S1QualificationJob,
        output_dir: Path,
    ) -> None:
        self.config = delegate.config
        self._delegate = delegate
        self._runner_contract = runner_contract
        self._job = job
        self._output_dir = output_dir
        self._prepared: privacy_runner.PreparedPrivacyFirstRequest | None = None
        self._ordinary_detour_count_before = 0
        self._provider_calls_before = 0
        self._replacement_count = 0
        self._certificates: list[TransportInvocationCertificate] = []
        self._descriptors: list[legacy.RawFileDescriptor] = []

    @property
    def replacement_count(self) -> int:
        return self._replacement_count

    @property
    def invocation_count(self) -> int:
        return len(self._certificates)

    @property
    def descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return tuple(self._descriptors)

    def bind(
        self,
        prepared: privacy_runner.PreparedPrivacyFirstRequest,
        *,
        ordinary_detour_count_before: int,
        provider_calls_before: int,
    ) -> None:
        self._prepared = prepared
        self._ordinary_detour_count_before = ordinary_detour_count_before
        self._provider_calls_before = provider_calls_before

    def _certificate(self, *, replacement: bool) -> TransportInvocationCertificate:
        prepared = self._prepared
        if prepared is None or prepared.dynamic_certificate is None:
            raise ValueError("v26.133 Transport invocation lacks prepared certificates")
        if self.invocation_count >= MAXIMUM_TRANSPORT_INVOCATIONS:
            raise _TransportInvocationLimit("transport_inclusive_invocation_limit_exhausted")
        dynamic = prepared.dynamic_certificate
        values = {
            "runner_contract_id": self._runner_contract.contract_id,
            "job_id": self._job.job_id,
            "preparation_id": prepared.preparation_id,
            "inner_dynamic_certificate_id": dynamic.certificate_id,
            "request_binding_certificate_id": (prepared.request_binding_certificate.certificate_id),
            "request_prompt_sha256": legacy.sha256_text(prepared.prompt),
            "transport_invocation_index": self.invocation_count,
            "provider_calls_before_invocation": self._provider_calls_before,
            "abi_rescue_count_before": dynamic.abi_rescue_count_before,
            "semantic_recovery_count_before": dynamic.semantic_recovery_count_before,
            "transport_replacement_count_before": 1 if replacement else 0,
            "ordinary_detour_count_before": self._ordinary_detour_count_before,
            "is_transport_replacement": replacement,
            "exact_same_prepared_request_as_failed_transport": replacement,
        }
        provisional = TransportInvocationCertificate.model_construct(
            certificate_id="pending", **values
        )
        certificate = TransportInvocationCertificate(
            certificate_id=_identity(
                provisional,
                "certificate_id",
                "finance_v26_s1_transport_invocation_certificate:",
            ),
            **values,
        )
        path = _invocation_path(self._output_dir, self._job, self.invocation_count)
        _write_json_atomic(path, certificate)
        self._certificates.append(certificate)
        self._descriptors.append(_descriptor(path, self._output_dir))
        return certificate

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        self._certificate(replacement=False)
        try:
            return self._delegate.complete_json_certified(prompt, certificate)
        except legacy.LLMClientError as exc:
            if exc.telemetry:
                raise
            if self._replacement_count >= MAXIMUM_TRANSPORT_REPLACEMENTS:
                raise _TransportReplacementExhausted(
                    "single_transport_replacement_exhausted"
                ) from exc
            self._replacement_count += 1
            self._certificate(replacement=True)
            try:
                return self._delegate.complete_json_certified(prompt, certificate)
            except legacy.LLMClientError as replacement_exc:
                if replacement_exc.telemetry:
                    raise
                raise _TransportReplacementExhausted(
                    "single_transport_replacement_exhausted"
                ) from replacement_exc


class _S1Journal(privacy_runner.PrivacyFirstJournaledClient):
    def __init__(
        self,
        delegate: Any,
        *,
        runner_contract: S1QualificationRunnerContract,
        resource_contract: S1QualificationResourceContract,
        job: S1QualificationJob,
        output_dir: Path,
    ) -> None:
        self.transport_delegate = _TransportAwareDelegate(
            delegate,
            runner_contract=runner_contract,
            job=job,
            output_dir=output_dir,
        )
        self.ordinary_detour_count = 0
        super().__init__(
            self.transport_delegate,
            runner_contract=cast(Any, runner_contract),
            resource_contract=cast(Any, resource_contract),
            job=cast(Any, job),
            output_dir=output_dir,
        )

    @property
    def transport_invocation_descriptors(self) -> tuple[legacy.RawFileDescriptor, ...]:
        return self.transport_delegate.descriptors

    @property
    def transport_replacement_count(self) -> int:
        return self.transport_delegate.replacement_count

    @property
    def transport_invocation_count(self) -> int:
        return self.transport_delegate.invocation_count

    def invoke(
        self,
        prepared: privacy_runner.PreparedPrivacyFirstRequest,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        self.transport_delegate.bind(
            prepared,
            ordinary_detour_count_before=self.ordinary_detour_count,
            provider_calls_before=self.provider_call_count,
        )
        return super().invoke(prepared)


def _state_from_s1_prompt(prompt: str) -> tuple[SemanticActionState, Mapping[str, Any]]:
    payload = predecessor.predecessor._compact_prompt_payload(prompt)  # noqa: SLF001
    candidates = predecessor.predecessor._decode_compact_candidates(  # noqa: SLF001
        payload.get("visible_action_candidates")
    )
    state = predecessor.predecessor._decode_compact_state(  # noqa: SLF001
        payload.get("compact_public_state"),
        presented_candidates=candidates,
    )
    return state, payload


def _reference_proposal_from_s1_prompt(prompt: str) -> CanonicalActionProposal:
    state, payload = _state_from_s1_prompt(prompt)
    instruction = payload.get("instruction")
    condition = payload.get("public_path_condition")
    if not isinstance(instruction, str) or (
        condition is not None and not isinstance(condition, str)
    ):
        raise ValueError("v26.133 S1 scripted Prompt context changed")
    semantic_prompt = render_semantic_action_prompt(
        instruction=instruction,
        state=state,
        public_path_condition=condition,
    )
    return prompt_only_reference_proposal(semantic_prompt)


class ScriptedS1QualificationClient:
    def __init__(
        self,
        config: Any,
        *,
        final_answer: Mapping[str, Any],
        completion_tokens: int = 64,
        malformed_action_once: bool = False,
        semantic_rejection_once: bool = False,
        transport_failure_once: bool = False,
        privacy_failure_once: bool = False,
        force_action_id: str | None = None,
        force_action_uses: int = 0,
        wrong_final_answer: bool = False,
    ) -> None:
        self.config = config
        self._final_answer = json.loads(json.dumps(final_answer))
        self._completion_tokens = completion_tokens
        self._malformed_action_once = malformed_action_once
        self._semantic_rejection_once = semantic_rejection_once
        self._transport_failure_once = transport_failure_once
        self._privacy_failure_once = privacy_failure_once
        self._force_action_id = force_action_id
        self._force_action_uses = force_action_uses
        self._wrong_final_answer = wrong_final_answer
        self._malformed_used = False
        self._semantic_rejection_used = False
        self._transport_failure_used = False
        self._privacy_failure_used = False
        self.local_invocation_count = 0
        self.prompts: list[tuple[str, str, str]] = []

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        expected = legacy.certify_stage_one_request_pre_call(
            config=self.config,
            prompt=prompt,
            request_kind=certificate.request_kind,
            phase=certificate.phase,
        )
        if expected != certificate:
            raise legacy.LLMClientError("scripted S1 request certificate changed")
        self.local_invocation_count += 1
        self.prompts.append((certificate.request_kind, certificate.phase, prompt))
        if self._transport_failure_once and not self._transport_failure_used:
            self._transport_failure_used = True
            raise legacy.LLMClientError("scripted transport failure", telemetry=())
        if certificate.request_kind == "final_answer":
            answer = json.loads(json.dumps(self._final_answer))
            if self._wrong_final_answer:
                answer = {"result": {"wrong": "schema-valid-control"}, "citations": []}
            payload = exact_final_response_payload(
                answer,
                rationale_summary="Projected the verified public result.",
            )
        else:
            state, _ = _state_from_s1_prompt(prompt)
            reference = _reference_proposal_from_s1_prompt(prompt)
            if self._privacy_failure_once and not self._privacy_failure_used:
                self._privacy_failure_used = True
                payload = {
                    "reasoning_trace": "fixture private content must not persist",
                    "public_value": "fixture rejected key must not persist",
                }
            elif (
                self._malformed_action_once
                and not self._malformed_used
                and certificate.phase == "primary"
            ):
                self._malformed_used = True
                payload = {"state_id": state.state_id}
            elif (
                self._semantic_rejection_once
                and not self._semantic_rejection_used
                and certificate.phase == "primary"
            ):
                self._semantic_rejection_used = True
                other = next(
                    item
                    for item in (
                        "acquire_public_input",
                        "execute_public_operation",
                        "verify_terminal_operation",
                        "emit_final_answer",
                    )
                    if item != reference.decision_kind
                )
                payload = {
                    "state_id": state.state_id,
                    "action_id": reference.action_id,
                    "decision_kind": other,
                    "protocol": RESPONSE_PROTOCOL_VERSION,
                }
            else:
                proposal = reference
                if self._force_action_id is not None and self._force_action_uses > 0:
                    forced = next(
                        (
                            item
                            for item in state.action_candidates
                            if item.action_id == self._force_action_id
                        ),
                        None,
                    )
                    if forced is not None:
                        proposal = make_canonical_action_proposal(
                            state_id=state.state_id,
                            action_id=forced.action_id,
                            decision_kind=forced.decision_kind,
                        )
                        self._force_action_uses -= 1
                payload = {
                    "state_id": proposal.state_id,
                    "action_id": proposal.action_id,
                    "decision_kind": proposal.decision_kind,
                    "protocol": RESPONSE_PROTOCOL_VERSION,
                }
        prompt_tokens = len(prompt.encode("utf-8"))
        telemetry = legacy.ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested=legacy.STAGE_ONE_MODEL_ID,
            model_selected=legacy.STAGE_ONE_MODEL_ID,
            response_model=legacy.STAGE_ONE_MODEL_ID,
            request_hash=legacy.sha256_text(prompt),
            response_hash=canonical_hash(payload, prefix="scripted_s1_qualification_response:"),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(_json_bytes(payload)),
            reasoning_content_present=True,
            reasoning_content_length=32,
            reasoning_tokens=min(16, self._completion_tokens),
            prompt_tokens=prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_tokens=prompt_tokens + self._completion_tokens,
            estimated_cost=0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=0,
            fallback_used=False,
            discovery_attempted=False,
            discovered_model_count=0,
        )
        return payload, telemetry


def _attempt(
    *,
    prepared: privacy_runner.PreparedPrivacyFirstRequest,
    provider_call_index: int | None,
    disposition: Any,
    response_payload_present: bool,
    payload_projection_status: Any = None,
    exact_four_field_action_payload: bool = False,
    exact_two_field_final_payload: bool = False,
    failure_family: str | None = None,
    failure_subtype: str | None = None,
    completion_failure_type: str | None = None,
    error: str | None = None,
) -> privacy_runner.PrivacyFirstAttempt:
    return privacy_runner._make_attempt(  # noqa: SLF001
        prepared=prepared,
        provider_call_index=provider_call_index,
        disposition=disposition,
        response_payload_present=response_payload_present,
        payload_projection_status=payload_projection_status,
        exact_four_field_action_payload=exact_four_field_action_payload,
        exact_two_field_final_payload=exact_two_field_final_payload,
        failure_family=failure_family,
        failure_subtype=failure_subtype,
        completion_failure_type=completion_failure_type,
        error=error,
    )


def _invoke_once(
    ledger: _S1Journal,
    *,
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: privacy_runner.PublicAttemptPhase,
    primary_prompt: str,
    prompt: str,
    state: SemanticActionState | None,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    static: engineering_static.FinalGrammarStaticInputs,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> _CallOutcome:
    public_state_id = (
        state.state_id
        if state is not None
        else (
            final_response_host_envelope.terminal_state_id
            if final_response_host_envelope is not None
            else None
        )
    )
    prepared = ledger.prepare(
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=prompt,
        public_state_id=public_state_id,
        final_response_host_envelope=final_response_host_envelope,
        abi_rescue_count_before=abi_rescue_count,
        semantic_recovery_count_before=semantic_recovery_count,
    )
    before = ledger.provider_call_count
    try:
        payload, _ = ledger.invoke(prepared)
    except privacy_runner.BudgetNoCallError as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except privacy_runner.PayloadPrivacyProjectionError as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=False,
                payload_projection_status="privacy_rejected",
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            )
        )
    except _TransportReplacementExhausted as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="provider_transport_failure",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except _TransportInvocationLimit as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=None,
                disposition="typed_budget_no_call",
                response_payload_present=False,
                error=str(exc),
            )
        )
    except privacy_runner.InstrumentContractError as exc:
        index = before if ledger.provider_call_count > before else None
        status = ledger.projection_statuses[-1] if index is not None else None
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition="instrument_failure",
                response_payload_present=False,
                payload_projection_status=status,
                error=str(exc),
            )
        )
    except legacy.LLMClientError as exc:
        index = before if ledger.provider_call_count > before else None
        failure_type = (
            exc.failure_artifact.failure_type
            if isinstance(exc.failure_artifact, legacy.ProspectiveThinkingFailureArtifact)
            else type(exc).__name__
        )
        disposition = (
            "completion_failure"
            if exc.telemetry and all(item.http_success for item in exc.telemetry)
            else "provider_transport_failure"
        )
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=index,
                disposition=disposition,
                response_payload_present=False,
                payload_projection_status=(
                    "provider_failure_no_payload" if index is not None else None
                ),
                completion_failure_type=failure_type,
                error=str(exc),
            )
        )
    try:
        if request_kind == "semantic_proposal":
            proposal = parse_exact_canonical_action_payload(payload)
            return _CallOutcome(
                attempt=_attempt(
                    prepared=prepared,
                    provider_call_index=before,
                    disposition="usable",
                    response_payload_present=True,
                    payload_projection_status="validated_public_payload",
                    exact_four_field_action_payload=True,
                ),
                payload=payload,
                proposal=proposal,
            )
        if final_response_host_envelope is None:
            raise ValueError("v26.133 Final Parser lacks Host Envelope")
        final_payload = parse_exact_final_response_payload(
            payload,
            grammar=static.final_grammar,
            envelope=final_response_host_envelope,
        )
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="usable",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                exact_two_field_final_payload=True,
            ),
            payload=payload,
            final_payload=final_payload,
        )
    except (SemanticActionResponseRejection, ExactFinalResponseRejection) as exc:
        return _CallOutcome(
            attempt=_attempt(
                prepared=prepared,
                provider_call_index=before,
                disposition="model_result_failure",
                response_payload_present=True,
                payload_projection_status="validated_public_payload",
                failure_family=exc.family,
                failure_subtype=exc.subtype,
                error=str(exc),
            ),
            payload=payload,
        )


def _abi_rescue_allowed(attempt: privacy_runner.PrivacyFirstAttempt) -> bool:
    return attempt.disposition == "completion_failure" or (
        attempt.disposition == "model_result_failure"
        and attempt.failure_family in {"response_serialization_failure", "channel_parse_failure"}
    )


def _active_call(
    ledger: _S1Journal,
    *,
    attempts: list[privacy_runner.PrivacyFirstAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: Literal["primary", "semantic_recovery"],
    primary_prompt: str,
    state: SemanticActionState | None,
    presentation_salt: str | None,
    instruction: str | None,
    condition: str | None,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    static: engineering_static.FinalGrammarStaticInputs,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> tuple[_CallOutcome, int]:
    primary = _invoke_once(
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        final_response_host_envelope=final_response_host_envelope,
        static=static,
        abi_rescue_count=abi_rescue_count,
        semantic_recovery_count=semantic_recovery_count,
    )
    attempts.append(primary.attempt)
    if abi_rescue_count == 0 and _abi_rescue_allowed(primary.attempt):
        abi_rescue_count = 1
        family = primary.attempt.failure_family or "channel_parse_failure"
        subtype = (
            primary.attempt.failure_subtype
            or primary.attempt.completion_failure_type
            or "completion_failure"
        )
        if request_kind == "semantic_proposal":
            if state is None or presentation_salt is None or instruction is None:
                raise ValueError("v26.133 Action ABI Rescue lacks S1 state")
            rescue_prompt = predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
                phase="abi_rescue",
                instruction=instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                typed_failure={"family": family, "subtype": subtype},
                grammar=static.action_grammar,
            )
        else:
            rescue_prompt = render_exact_final_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
        rescue = _invoke_once(
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            public_attempt_phase="abi_rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            final_response_host_envelope=final_response_host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        attempts.append(rescue.attempt)
        return rescue, abi_rescue_count
    return primary, abi_rescue_count


def _terminal_from_attempt(attempt: privacy_runner.PrivacyFirstAttempt) -> QualificationTerminal:
    if attempt.disposition == "typed_budget_no_call":
        return "typed_budget_no_call"
    if attempt.disposition == "provider_transport_failure":
        return "provider_transport_failure"
    if attempt.disposition == "instrument_failure":
        return "instrument_failure"
    return "model_result_failure"


def _progress_event(
    *,
    logical_request_index: int,
    before: SemanticActionState,
    after: SemanticActionState,
    observation: AgentToolObservation,
    selected_action_id: str,
    reference_action_id: str,
    ordinary_detour_count_before: int,
) -> PublicProgressEvent:
    changed = predecessor._progress_vector(before) != predecessor._progress_vector(after)  # noqa: SLF001
    selected_matches_reference = selected_action_id == reference_action_id
    detour = observation.status == "succeeded" and not changed and not selected_matches_reference
    count_after = ordinary_detour_count_before + int(detour)
    values = {
        "logical_request_index": logical_request_index,
        "state_id_before": before.state_id,
        "state_id_after": after.state_id,
        "observation_id": observation.observation_id,
        "selected_action_id": selected_action_id,
        "reference_action_id": reference_action_id,
        "selected_action_matches_reference": selected_matches_reference,
        "observation_succeeded": observation.status == "succeeded",
        "progress_vector_changed": changed,
        "ordinary_detour_observed": detour,
        "ordinary_detour_count_after": count_after,
        "diagnostic_public_state_changed_outside_progress_vector": (
            before.state_id != after.state_id and not changed
        ),
    }
    provisional = PublicProgressEvent.model_construct(event_id="pending", **values)
    return PublicProgressEvent(
        event_id=_identity(provisional, "event_id", "finance_v26_s1_public_progress_event:"),
        **values,
    )


def _semantic_commit_record(
    *,
    logical_request_index: int,
    state: SemanticActionState,
    proposal: CanonicalActionProposal,
    commit: CanonicalActionCommit,
    stage_two_profile_id: str,
    provider_calls_before_commit: int,
) -> action_execution.SemanticActionCommitRecord:
    values = {
        "logical_request_index": logical_request_index,
        "public_state_id": state.state_id,
        "proposal": proposal,
        "commit": commit,
        "stage_two_profile_id": stage_two_profile_id,
        "provider_calls_before_commit": provider_calls_before_commit,
    }
    provisional = action_execution.SemanticActionCommitRecord.model_construct(
        record_id="pending", **values
    )
    return action_execution.SemanticActionCommitRecord(
        record_id=_identity(provisional, "record_id", "finance_v26_semantic_action_commit_record:"),
        **values,
    )


def execute_s1_qualification_job_raw(
    *,
    job: S1QualificationJob,
    old_job: engineering_static.FinalGrammarJob,
    runner_contract: S1QualificationRunnerContract,
    resource_contract: S1QualificationResourceContract,
    static: engineering_static.FinalGrammarStaticInputs,
    binding: legacy.RuntimeBinding,
    client: Any | None,
    output_dir: Path,
) -> S1QualificationRawExecution:
    raw_path = _raw_path(output_dir, job)
    if raw_path.exists():
        raw = S1QualificationRawExecution.model_validate(_load_json(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.133 Raw recovery crosses frozen identities")
        for descriptor in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
            *raw.transport_invocation_artifacts,
        ):
            path = output_dir / descriptor.relative_path
            if (
                not path.is_file()
                or _sha256(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError("v26.133 Raw recovery bytes changed")
        envelopes = tuple(
            privacy_runner.PrivacyFirstProviderEnvelope.model_validate(
                _load_json(output_dir / item.relative_path)
            )
            for item in raw.provider_envelope_artifacts
        )
        projections = tuple(
            privacy_runner.PublicPayloadProjection.model_validate(
                _load_json(output_dir / item.relative_path)
            )
            for item in raw.public_payload_projection_artifacts
        )
        for envelope, projection in zip(envelopes, projections, strict=True):
            privacy_runner.validate_provider_artifact_pair(envelope, projection)
        if tuple(item.provider_telemetry for item in envelopes) != raw.provider_telemetry:
            raise ValueError("v26.133 Raw recovery telemetry changed")
        return raw
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = _invocation_path(output_dir, job, 0).parent
    if any(
        directory.exists() and any(directory.iterdir())
        for directory in (envelope_dir, projection_dir, invocation_dir)
    ):
        raise ValueError("v26.133 orphan Provider or invocation artifact forbids retry")
    if client is None:
        raise ValueError("pending v26.133 qualification Job has no Stage 1 client")
    if (
        old_job.job_id != job.predecessor_job_id
        or old_job.task_package_id != job.task_package_id
        or old_job.path_audit_id != job.predecessor_path_audit_id
    ):
        raise ValueError("v26.133 qualification Job changed its engineering assignment")
    ledger = _S1Journal(
        client,
        runner_contract=runner_contract,
        resource_contract=resource_contract,
        job=job,
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)  # noqa: SLF001
    observations: list[AgentToolObservation] = []
    attempts: list[privacy_runner.PrivacyFirstAttempt] = []
    choices: list[action_execution.SemanticChoiceRecord] = []
    commits: list[action_execution.SemanticActionCommitRecord] = []
    semantic_rejections: list[PublicSemanticRejectionObservation] = []
    progress_events: list[PublicProgressEvent] = []
    abi_rescue_count = 0
    semantic_recovery_count = 0
    ordinary_detour_count = 0
    pending_semantic_recovery = False
    prior_rejected_action_id: str | None = None
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    terminal: QualificationTerminal = "model_result_failure"
    failure_type: str | None = None
    error: str | None = None
    completed: privacy_runner.PrivacyFirstCompletedResult | None = None
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    logical_index = 0
    for _ in range(resource_contract.maximum_primary_stage_one_requests - 1):
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(semantic_rejections),
        )
        presentation_salt = canonical_hash(
            {
                "qualification_job_id": job.job_id,
                "logical_request_index": logical_index,
                "state_id": state.state_id,
                "semantic_recovery_count": semantic_recovery_count,
                "ordinary_detour_count": ordinary_detour_count,
            },
            prefix="finance_v26_s1_qualification_candidate_presentation:",
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery" if pending_semantic_recovery else "primary"
        )
        typed_failure = None
        if pending_semantic_recovery:
            rejection = semantic_rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        prompt = predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
            phase=phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=static.action_grammar,
        )
        decoded_state, _ = predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
            prompt,
            presentation_salt=presentation_salt,
        )
        if decoded_state != state:
            raise ValueError("v26.133 online S1 Prompt changed current public state")
        diagnostic_reference = _reference_proposal_from_s1_prompt(prompt)
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = _active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            public_attempt_phase=phase,
            primary_prompt=prompt,
            state=state,
            presentation_salt=presentation_salt,
            instruction=binding.record.task_package.task.public.instruction,
            condition=condition,
            final_response_host_envelope=None,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        current_index = logical_index
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = _terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        selected = evaluate_canonical_action_proposal(
            state,
            proposal,
            call_index=len(observations) + 1,
        )
        if selected.rejection is not None:
            choices.append(
                action_execution._choice_record(  # noqa: SLF001
                    logical_request_index=current_index,
                    phase=phase,
                    state=state,
                    proposal=proposal,
                    commit=None,
                    rejection=selected.rejection,
                    prior_rejected_action_id=prior_rejected_action_id,
                    observation=None,
                    progress=None,
                )
            )
            if semantic_recovery_count == 0 and selected.rejection.semantic_recovery_available:
                semantic_recovery_count = 1
                semantic_rejections.append(selected.rejection)
                prior_rejected_action_id = proposal.action_id
                pending_semantic_recovery = True
                continue
            terminal = "typed_semantic_rejection"
            failure_type = "semantic_recovery_exhausted"
            error = selected.rejection.error_category
            break
        commit = selected.commit
        if commit is None:
            raise ValueError("accepted v26.133 action lacks a Commit")
        commits.append(
            _semantic_commit_record(
                logical_request_index=current_index,
                state=state,
                proposal=proposal,
                commit=commit,
                stage_two_profile_id=static.stage_two.profile_id,
                provider_calls_before_commit=ledger.provider_call_count,
            )
        )
        pending_semantic_recovery = False
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        detour_terminal = False
        if commit.call is not None:
            observation = legacy._execute_observation(  # noqa: SLF001
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=commit.call.tool_id,
                    arguments=commit.call.arguments,
                ),
            )
            observations.append(observation)
            after = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=tuple(semantic_rejections),
            )
            event = _progress_event(
                logical_request_index=current_index,
                before=state,
                after=after,
                observation=observation,
                selected_action_id=proposal.action_id,
                reference_action_id=diagnostic_reference.action_id,
                ordinary_detour_count_before=ordinary_detour_count,
            )
            progress_events.append(event)
            progress = event.progress_vector_changed
            ordinary_detour_count = event.ordinary_detour_count_after
            ledger.ordinary_detour_count = ordinary_detour_count
            detour_terminal = ordinary_detour_count > MAXIMUM_ORDINARY_DETOURS
        choices.append(
            action_execution._choice_record(  # noqa: SLF001
                logical_request_index=current_index,
                phase=phase,
                state=state,
                proposal=proposal,
                commit=commit,
                rejection=None,
                prior_rejected_action_id=prior_rejected_action_id,
                observation=observation,
                progress=progress,
            )
        )
        if detour_terminal:
            terminal = "ordinary_detour_allowance_exhausted"
            failure_type = "ordinary_detour_allowance_exhausted"
            error = "trajectory left the pre-registered T_dyn^(1) measurement support"
            break
        if commit.action == "emit_final":
            final_state = state
            final_commit = commit
            break
    else:
        terminal = "model_result_failure"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach Final within the frozen request limit"
    if (
        final_state is not None
        and final_commit is not None
        and terminal == "model_result_failure"
        and failure_type is None
    ):
        compact_source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        final_prompt = render_exact_final_primary_prompt(
            compact_source,
            grammar=static.final_grammar,
        )
        host_envelope = make_final_response_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=static.final_grammar,
        )
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = _active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            presentation_salt=None,
            instruction=None,
            condition=condition,
            final_response_host_envelope=host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.final_payload is not None:
            citations = legacy._selected_evidence_ids(observations)  # noqa: SLF001
            values = {
                "job_id": job.job_id,
                "answer": outcome.final_payload.answer,
                "rationale_summary": outcome.final_payload.rationale_summary,
                "cited_evidence_ids": citations,
                "final_attempt_id": outcome.attempt.attempt_id,
                "final_response_host_envelope": host_envelope,
            }
            provisional_completed = privacy_runner.PrivacyFirstCompletedResult.model_construct(
                result_id="pending", **values
            )
            completed = privacy_runner.PrivacyFirstCompletedResult(
                result_id=_identity(
                    provisional_completed,
                    "result_id",
                    "finance_v26_privacy_first_completed_result:",
                ),
                **values,
            )
            terminal = "completed_model_result"
        else:
            terminal = _terminal_from_attempt(outcome.attempt)
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
    if ledger.instrument_failures:
        terminal = "instrument_failure"
        failure_type = "provider_usage_or_binding_contract_failure"
        error = ";".join(ledger.instrument_failures)
        completed = None
    first_choice = choices[0] if choices else None
    first_interface = bool(
        first_choice is not None
        and first_choice.visible_action_id_match
        and first_choice.decision_kind_match
        and first_choice.semantic_accepted
        and first_choice.commit_id is not None
    )
    raw_values: dict[str, Any] = {
        "runner_contract_id": runner_contract.contract_id,
        "job": job,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "provider_envelope_artifacts": ledger.envelope_descriptors,
        "public_payload_projection_artifacts": ledger.projection_descriptors,
        "transport_invocation_artifacts": ledger.transport_invocation_descriptors,
        "provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "semantic_choices": tuple(choices),
        "commits": tuple(commits),
        "semantic_rejections": tuple(semantic_rejections),
        "observations": tuple(observations),
        "progress_events": tuple(progress_events),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "transport_inclusive_invocation_count": ledger.transport_invocation_count,
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in attempts
        ),
        "semantic_recovery_attempt_count": sum(
            item.public_attempt_phase == "semantic_recovery" for item in choices
        ),
        "transport_replacement_attempt_count": ledger.transport_replacement_count,
        "ordinary_detour_count": ordinary_detour_count,
        "privacy_rejected_payload_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload for item in attempts
        ),
        "exact_two_field_final_payload_count": sum(
            item.exact_two_field_final_payload for item in attempts
        ),
        "first_action_interface_qualified": first_interface,
    }
    provisional_raw = S1QualificationRawExecution.model_construct(
        artifact_id="pending", **raw_values
    )
    raw = S1QualificationRawExecution(
        artifact_id=_identity(
            provisional_raw,
            "artifact_id",
            "finance_v26_s1_qualification_raw_execution:",
        ),
        **raw_values,
    )
    _write_json_atomic(raw_path, raw)
    return raw


def _source_channels(records: Sequence[Any]) -> dict[str, set[str]]:
    return {
        "source_task_artifact_id": {
            item for record in records for item in record.source_task_artifact_ids
        },
        "public_task_id": {record.task_package.task.public.task_id for record in records},
        "semantic_source_id": {
            record.task_package.semantic_source.semantic_source_id for record in records
        },
        "operational_record_id": {record.record_id for record in records},
        "operational_task_package_id": {record.task_package.package_id for record in records},
        "evidence_id": {
            evidence.evidence_id
            for record in records
            for evidence in record.evidence_bundle.evidence
        },
        "evidence_version_id": {
            evidence.evidence_version_id
            for record in records
            for evidence in record.evidence_bundle.evidence
        },
        "source_record_id": {
            evidence.provenance.source_record_id
            for record in records
            for evidence in record.evidence_bundle.evidence
        },
    }


def _material_to_final_path_ids(
    static: engineering_static.FinalGrammarStaticInputs,
) -> dict[str, str]:
    first = {
        item.predecessor_path_audit_id: item.path_audit_id
        for item in static.predecessor.historical.paths
    }
    second = {
        item.predecessor_path_audit_id: item.path_audit_id for item in static.predecessor.paths
    }
    third = {item.predecessor_path_audit_id: item.path_audit_id for item in static.paths}
    return {old: third[second[middle]] for old, middle in first.items()}


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + 16_385


def _make_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    root = package_root / PREDECESSOR_DIR
    report_path = root / "report.json"
    transition_path = root / "prospective_transition_contract.json"
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or _sha256(transition_path) != EXPECTED_PREDECESSOR_TRANSITION_SHA256
    ):
        raise ValueError("v26.133 predecessor report or transition bytes changed")
    report = predecessor.BoundedDynamicRolePreflightReport.model_validate(_load_json(report_path))
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load_json(transition_path)
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or transition.next_permitted_stage != predecessor.NEXT_STAGE
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.133 predecessor authorization changed")
    predecessor_source = predecessor.SourceReplayAudit.model_validate(
        _load_json(root / "source_replay_audit.json")
    )
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_132_transitive_source",
            expected_sha256=item.sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    detail = {item.relative_path: item for item in report.detail_files}
    for name in PREDECESSOR_OUTPUT_NAMES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"v26.133 predecessor output is missing: {name}")
        if name != "report.json":
            expected = detail.get(name)
            if (
                expected is None
                or expected.sha256 != _sha256(path)
                or expected.byte_count != path.stat().st_size
            ):
                raise ValueError("v26.133 predecessor detail binding changed")
        relative = str(Path(PREDECESSOR_DIR) / name)
        digest = _sha256(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_132_output",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    path = implementation_root / IMPLEMENTATION_PATH
    digest = _sha256(path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_133_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=path.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    values = {"entries": ordered, "replayed_file_count": len(ordered)}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_s1_qualification_source_replay:"),
        **values,
    )


def _load_inputs(
    package_root: Path,
    implementation_root: Path,
) -> _LoadedInputs:
    root = package_root / PREDECESSOR_DIR
    report = predecessor.BoundedDynamicRolePreflightReport.model_validate(
        _load_json(root / "report.json")
    )
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load_json(root / "prospective_transition_contract.json")
    )
    resource = predecessor.RoleScalableResourceContract.model_validate(
        _load_json(root / "bounded_dynamic_resource_contract.json")
    )
    policy = predecessor.OrdinaryDetourPolicy.model_validate(
        _load_json(root / "ordinary_detour_policy.json")
    )
    role_tasks = predecessor.RoleTaskPackageCatalog.model_validate(
        _load_json(root / "role_task_package_catalog.json")
    )
    dynamic = predecessor.DynamicTrajectoryEnvelopeAudit.model_validate(
        _load_json(root / "dynamic_trajectory_envelope_audit.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or resource.contract_id != EXPECTED_PREDECESSOR_RESOURCE_ID
        or policy.policy_id != EXPECTED_PREDECESSOR_POLICY_ID
        or dynamic.ordinary_detour_policy_id != policy.policy_id
    ):
        raise ValueError("v26.133 predecessor scientific binding changed")
    static = engineering_static.load_final_grammar_static_inputs(
        package_root,
        implementation_root,
    )
    if (
        static.report.report_id != EXPECTED_ENGINEERING_REPORT_ID
        or static.contract.contract_id != EXPECTED_ENGINEERING_CONTRACT_ID
        or static.manifest.manifest_id != EXPECTED_ENGINEERING_MANIFEST_ID
        or static.resource.contract_id != EXPECTED_ENGINEERING_RESOURCE_ID
        or static.final_grammar.grammar_id != EXPECTED_FINAL_GRAMMAR_ID
        or static.stage_one.profile_id != EXPECTED_STAGE_ONE_PROFILE_ID
        or static.stage_two.profile_id != EXPECTED_STAGE_TWO_PROFILE_ID
    ):
        raise ValueError("v26.133 repeated engineering source binding changed")
    materials, _ = engineering._build_materials(  # noqa: SLF001
        static.predecessor.historical,
        static.action_grammar,
    )
    final_materials, _, _ = engineering_static._build_final_materials(  # noqa: SLF001
        static.predecessor,
        static.final_grammar,
    )
    return _LoadedInputs(
        predecessor_report=report,
        predecessor_transition=transition,
        predecessor_resource=resource,
        predecessor_policy=policy,
        predecessor_role_tasks=role_tasks,
        predecessor_dynamic=dynamic,
        engineering=static,
        engineering_materials=materials,
        final_materials=final_materials,
    )


def _make_predecessor_binding(loaded: _LoadedInputs) -> FrozenPredecessorBindingAudit:
    if (
        loaded.predecessor_resource.prompt_ceiling_bytes != PROMPT_CEILING_BYTES
        or loaded.predecessor_resource.maximum_primary_requests != MAXIMUM_PRIMARY_REQUESTS
        or loaded.predecessor_resource.maximum_provider_calls_with_recovery
        != MAXIMUM_PROVIDER_CALLS
        or loaded.predecessor_resource.maximum_transport_inclusive_invocations
        != MAXIMUM_TRANSPORT_INVOCATIONS
        or loaded.predecessor_resource.rollout_upper_bound_tokens != ROLLOUT_UPPER_BOUND_TOKENS
    ):
        raise ValueError("v26.133 changed a frozen v26.132 resource value")
    values: dict[str, Any] = {}
    provisional = FrozenPredecessorBindingAudit.model_construct(audit_id="pending", **values)
    return FrozenPredecessorBindingAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_predecessor_binding:",
        ),
        **values,
    )


def _make_source_separation(loaded: _LoadedInputs) -> QualificationSourceSeparationAudit:
    engineering_records = tuple(
        {
            item.binding.record.record_id: item.binding.record
            for item in loaded.engineering_materials
        }.values()
    )
    role_records = tuple(item.operational_record for item in loaded.predecessor_role_tasks.packages)
    if len(engineering_records) != 24 or len(role_records) != 24:
        raise ValueError("v26.133 source denominator changed")
    engineering_channels = _source_channels(engineering_records)
    role_channels = _source_channels(role_records)
    rows = tuple(
        SeparationChannelRow(
            channel=cast(Any, channel),
            engineering_identity_count=len(engineering_channels[channel]),
            role_identity_count=len(role_channels[channel]),
            overlap_count=cast(
                Literal[0],
                len(engineering_channels[channel] & role_channels[channel]),
            ),
        )
        for channel in SOURCE_CHANNELS
    )
    external = tuple(
        sorted(
            (item.state_id, item.action_id)
            for item in loaded.predecessor_dynamic.rows
            if item.outcome == "successful_no_progress_route_not_closable"
        )
    )
    if len(external) != ROLE_CLASS_EXTERNAL_ACTION_COUNT:
        raise ValueError("v26.133 role class-external denominator changed")
    engineering_states = {
        state.state_id for material in loaded.engineering_materials for state in material.states
    }
    external_states = {state_id for state_id, _ in external}
    values = {
        "separation_channels": rows,
        "role_class_external_state_action_set_sha256": hashlib.sha256(
            _json_bytes(external)
        ).hexdigest(),
        "engineering_state_overlap_with_role_class_external_states": cast(
            Literal[0], len(engineering_states & external_states)
        ),
    }
    provisional = QualificationSourceSeparationAudit.model_construct(audit_id="pending", **values)
    return QualificationSourceSeparationAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_source_separation:",
        ),
        **values,
    )


def _make_progress_contract() -> PublicProgressVectorContract:
    provisional = PublicProgressVectorContract.model_construct(contract_id="pending")
    return PublicProgressVectorContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_public_progress_vector_contract:",
        )
    )


def _make_path_catalog(loaded: _LoadedInputs) -> S1QualificationPathCatalog:
    static = loaded.engineering
    path_map = _material_to_final_path_ids(static)
    final_paths = {item.path_audit_id: item for item in static.paths}
    final_material_by_v118 = {
        item.predecessor_path.path_audit_id: item for item in loaded.final_materials
    }
    v118_by_v112 = {item.predecessor_path_audit_id: item for item in static.predecessor.paths}
    v112_by_old = {
        item.predecessor_path_audit_id: item for item in static.predecessor.historical.paths
    }
    paths: list[S1QualificationPathAudit] = []
    for material in loaded.engineering_materials:
        final_path_id = path_map[material.predecessor_path.audit_id]
        old_v112 = v112_by_old[material.predecessor_path.audit_id]
        old_v118 = v118_by_v112[old_v112.path_audit_id]
        final_path = final_paths[final_path_id]
        final_material = final_material_by_v118[old_v118.path_audit_id]
        binding = material.binding
        condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        rows: list[S1StateBindingRow] = []
        primary_prompts: list[str] = []
        abi_prompts: list[str] = []
        semantic_prompts: list[str] = []
        for index, (state, expected, expected_call) in enumerate(
            zip(material.states, material.proposals, material.expected_calls, strict=True)
        ):
            salt = canonical_hash(
                {
                    "predecessor_report_id": EXPECTED_PREDECESSOR_REPORT_ID,
                    "engineering_path_id": final_path_id,
                    "state_id": state.state_id,
                    "logical_index": index,
                },
                prefix="finance_v26_s1_qualification_candidate_presentation:",
            )
            prompts = {
                phase: predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
                    phase=cast(Any, phase),
                    instruction=binding.record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=condition,
                    presentation_salt=salt,
                    typed_failure=(
                        None
                        if phase == "primary"
                        else {
                            "family": (
                                "response_serialization_failure"
                                if phase == "abi_rescue"
                                else "semantic_action_rejection"
                            ),
                            "subtype": (
                                "canonical_action_not_exact_four_field_grammar"
                                if phase == "abi_rescue"
                                else "fixture_typed_semantic_rejection"
                            ),
                        }
                    ),
                    grammar=static.action_grammar,
                )
                for phase in ("primary", "abi_rescue", "semantic_recovery")
            }
            decoded: dict[str, tuple[SemanticActionState, tuple[Any, ...]]] = {}
            proposals: dict[str, CanonicalActionProposal] = {}
            for phase, prompt in prompts.items():
                decoded[phase] = predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                    prompt,
                    presentation_salt=salt,
                )
                proposals[phase] = predecessor.predecessor._compact_reference_proposal(  # noqa: SLF001
                    prompt,
                    presentation_salt=salt,
                )
            if any(value[0] != state for value in decoded.values()):
                raise ValueError("v26.133 S1 inverse changed exact state")
            if any(value != expected for value in proposals.values()):
                raise ValueError("v26.133 S1 Prompt reference proposal changed")
            selected = evaluate_canonical_action_proposal(
                state,
                expected,
                call_index=index + 1,
            )
            if (
                selected.commit is None
                or selected.rejection is not None
                or selected.commit.call != expected_call
            ):
                raise ValueError("v26.133 S1 Stage 2 Commit changed")
            presented = tuple(item.action_id for item in decoded["primary"][1])
            values = {
                "predecessor_path_audit_id": final_path.path_audit_id,
                "logical_state_index": index,
                "state_id": state.state_id,
                "candidate_count": len(presented),
                "presented_action_ids": presented,
                "primary_prompt_sha256": legacy.sha256_text(prompts["primary"]),
                "abi_rescue_prompt_sha256": legacy.sha256_text(prompts["abi_rescue"]),
                "semantic_recovery_prompt_sha256": legacy.sha256_text(prompts["semantic_recovery"]),
                "primary_prompt_utf8_bytes": len(prompts["primary"].encode("utf-8")),
                "abi_rescue_prompt_utf8_bytes": len(prompts["abi_rescue"].encode("utf-8")),
                "semantic_recovery_prompt_utf8_bytes": len(
                    prompts["semantic_recovery"].encode("utf-8")
                ),
                "reference_action_id": expected.action_id,
                "reference_decision_kind": expected.decision_kind,
                "reversible_commit_id": selected.commit.commit_id,
            }
            provisional_row = S1StateBindingRow.model_construct(row_id="pending", **values)
            rows.append(
                S1StateBindingRow(
                    row_id=_identity(
                        provisional_row,
                        "row_id",
                        "finance_v26_s1_qualification_state_binding:",
                    ),
                    **values,
                )
            )
            primary_prompts.append(prompts["primary"])
            abi_prompts.append(prompts["abi_rescue"])
            semantic_prompts.append(prompts["semantic_recovery"])
        final_primary = final_material.primary_prompt
        final_rescue = final_material.rescue_prompt
        static_upper = sum(_request_bound(item) for item in primary_prompts)
        static_upper += _request_bound(final_primary)
        static_upper += max(
            max(_request_bound(item) for item in abi_prompts),
            _request_bound(final_rescue),
        )
        static_upper += max(_request_bound(item) for item in semantic_prompts)
        primary_count = len(rows) + 1
        values = {
            "predecessor_path_audit_id": final_path.path_audit_id,
            "source_task_artifact_id": binding.record.source_task_artifact_ids[0],
            "engineering_task_package_id": final_path.task_package_id,
            "source_role": final_path.role,
            "mechanism_id": final_path.mechanism_id,
            "path_strategy_id": final_path.path_strategy_id,
            "state_rows": tuple(rows),
            "final_primary_prompt_sha256": legacy.sha256_text(final_primary),
            "final_rescue_prompt_sha256": legacy.sha256_text(final_rescue),
            "final_primary_prompt_utf8_bytes": len(final_primary.encode("utf-8")),
            "final_rescue_prompt_utf8_bytes": len(final_rescue.encode("utf-8")),
            "primary_request_count": primary_count,
            "provider_call_count_with_recoveries": primary_count + 2,
            "transport_inclusive_invocation_count": primary_count + 3,
            "static_complete_path_upper_bound_tokens": static_upper,
        }
        provisional_path = S1QualificationPathAudit.model_construct(path_id="pending", **values)
        paths.append(
            S1QualificationPathAudit(
                path_id=_identity(
                    provisional_path,
                    "path_id",
                    "finance_v26_s1_qualification_path:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(paths, key=lambda item: item.path_id))
    all_rows = tuple(row for path in ordered for row in path.state_rows)
    values = {
        "paths": ordered,
        "maximum_action_primary_prompt_utf8_bytes": max(
            item.primary_prompt_utf8_bytes for item in all_rows
        ),
        "maximum_action_abi_rescue_prompt_utf8_bytes": max(
            item.abi_rescue_prompt_utf8_bytes for item in all_rows
        ),
        "maximum_semantic_recovery_prompt_utf8_bytes": max(
            item.semantic_recovery_prompt_utf8_bytes for item in all_rows
        ),
        "maximum_final_primary_prompt_utf8_bytes": max(
            item.final_primary_prompt_utf8_bytes for item in ordered
        ),
        "maximum_final_rescue_prompt_utf8_bytes": max(
            item.final_rescue_prompt_utf8_bytes for item in ordered
        ),
        "maximum_registered_path_static_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in ordered
        ),
    }
    provisional = S1QualificationPathCatalog.model_construct(catalog_id="pending", **values)
    return S1QualificationPathCatalog(
        catalog_id=_identity(
            provisional, "catalog_id", "finance_v26_s1_qualification_path_catalog:"
        ),
        **values,
    )


def _make_resource_contract(
    catalog: S1QualificationPathCatalog,
) -> S1QualificationResourceContract:
    values = {
        "qualified_maximum_action_primary_prompt_utf8_bytes": (
            catalog.maximum_action_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_action_abi_rescue_prompt_utf8_bytes": (
            catalog.maximum_action_abi_rescue_prompt_utf8_bytes
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": (
            catalog.maximum_semantic_recovery_prompt_utf8_bytes
        ),
        "qualified_maximum_final_primary_prompt_utf8_bytes": (
            catalog.maximum_final_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_final_rescue_prompt_utf8_bytes": (
            catalog.maximum_final_rescue_prompt_utf8_bytes
        ),
        "maximum_registered_path_static_tokens": catalog.maximum_registered_path_static_tokens,
    }
    provisional = S1QualificationResourceContract.model_construct(contract_id="pending", **values)
    return S1QualificationResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_s1_qualification_resource_contract:",
        ),
        **values,
    )


def _make_qualification_contract(
    *,
    source: QualificationSourceSeparationAudit,
    progress: PublicProgressVectorContract,
    catalog: S1QualificationPathCatalog,
    resource: S1QualificationResourceContract,
) -> S1RepresentationQualificationContract:
    values = {
        "source_separation_audit_id": source.audit_id,
        "progress_vector_contract_id": progress.contract_id,
        "path_catalog_id": catalog.catalog_id,
        "resource_contract_id": resource.contract_id,
    }
    provisional = S1RepresentationQualificationContract.model_construct(
        contract_id="pending", **values
    )
    return S1RepresentationQualificationContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_s1_representation_qualification_contract:",
        ),
        **values,
    )


def _make_manifest(
    *,
    loaded: _LoadedInputs,
    contract: S1RepresentationQualificationContract,
    catalog: S1QualificationPathCatalog,
    resource: S1QualificationResourceContract,
) -> S1QualificationManifest:
    path_by_old = {item.predecessor_path_audit_id: item for item in catalog.paths}
    jobs: list[S1QualificationJob] = []
    for old in loaded.engineering.manifest.jobs:
        path = path_by_old[old.path_audit_id]
        values = {
            "predecessor_job_id": old.job_id,
            "contract_id": contract.contract_id,
            "task_package_id": old.task_package_id,
            "path_audit_id": path.path_id,
            "predecessor_path_audit_id": old.path_audit_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "mechanism_id": old.mechanism_id,
            "path_strategy_id": old.path_strategy_id,
            "source_role": old.source_role,
            "job_seed": old.job_seed,
            "resource_contract_id": resource.contract_id,
        }
        provisional = S1QualificationJob.model_construct(job_id="pending", **values)
        jobs.append(
            S1QualificationJob(
                job_id=_identity(provisional, "job_id", "finance_v26_s1_qualification_job:"),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    mechanism = Counter(item.mechanism_id for item in ordered)
    strategies = Counter(item.path_strategy_id for item in ordered)
    cells = Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered)
    values = {
        "contract_id": contract.contract_id,
        "resource_contract_id": resource.contract_id,
        "path_catalog_id": catalog.catalog_id,
        "jobs": ordered,
        "mechanism_job_counts": dict(sorted(mechanism.items())),
        "path_strategy_job_counts": dict(sorted(strategies.items())),
        "cell_job_counts": dict(sorted(cells.items())),
    }
    provisional = S1QualificationManifest.model_construct(manifest_id="pending", **values)
    return S1QualificationManifest(
        manifest_id=_identity(provisional, "manifest_id", "finance_v26_s1_qualification_manifest:"),
        **values,
    )


def _make_outcome_contract(
    contract: S1RepresentationQualificationContract,
    manifest: S1QualificationManifest,
) -> S1QualificationOutcomeContract:
    values = {
        "qualification_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
    }
    provisional = S1QualificationOutcomeContract.model_construct(contract_id="pending", **values)
    return S1QualificationOutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_s1_qualification_outcome_contract:",
        ),
        **values,
    )


def _make_runner_contract(
    *,
    contract: S1RepresentationQualificationContract,
    manifest: S1QualificationManifest,
    outcome: S1QualificationOutcomeContract,
    resource: S1QualificationResourceContract,
    progress: PublicProgressVectorContract,
) -> S1QualificationRunnerContract:
    values = {
        "qualification_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "resource_contract_id": resource.contract_id,
        "progress_vector_contract_id": progress.contract_id,
    }
    provisional = S1QualificationRunnerContract.model_construct(contract_id="pending", **values)
    return S1QualificationRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_s1_qualification_runner_contract:",
        ),
        **values,
    )


def _job_context(
    loaded: _LoadedInputs,
    job: S1QualificationJob,
) -> tuple[engineering_static.FinalGrammarJob, legacy.RuntimeBinding]:
    old = next(
        item for item in loaded.engineering.manifest.jobs if item.job_id == job.predecessor_job_id
    )
    binding = privacy_runner.privacy_first_runtime_binding(loaded.engineering, old)
    return old, binding


def _fixture_hash(raws: Sequence[S1QualificationRawExecution]) -> str:
    return hashlib.sha256(_json_bytes([item.model_dump(mode="json") for item in raws])).hexdigest()


def _make_runner_fixture(
    *,
    loaded: _LoadedInputs,
    manifest: S1QualificationManifest,
    resource: S1QualificationResourceContract,
    runner_contract: S1QualificationRunnerContract,
) -> RunnerFixtureAudit:
    raws: list[S1QualificationRawExecution] = []
    all_prompts: list[tuple[str, str, str]] = []
    with tempfile.TemporaryDirectory(prefix="v26_133_fixture_") as temporary:
        root = Path(temporary)
        for job in manifest.jobs:
            old, binding = _job_context(loaded, job)
            client = ScriptedS1QualificationClient(
                loaded.engineering.agent_model_config,
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = execute_s1_qualification_job_raw(
                job=job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=client,
                output_dir=root,
            )
            if raw.terminal_disposition != "completed_model_result":
                raise ValueError(
                    "v26.133 scripted reference Job did not complete: "
                    f"{job.job_id} {raw.terminal_disposition} "
                    f"{raw.terminal_failure_type} {raw.execution_error}"
                )
            recovered = execute_s1_qualification_job_raw(
                job=job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=None,
                output_dir=root,
            )
            if recovered.model_dump(mode="json") != raw.model_dump(mode="json"):
                raise ValueError("v26.133 scripted Raw recovery changed")
            raws.append(raw)
            all_prompts.extend(client.prompts)
    action_attempts = sum(item.exact_four_field_action_payload_count for item in raws)
    commits = sum(len(item.commits) for item in raws)
    observations = sum(len(item.observations) for item in raws)
    final_payloads = sum(item.exact_two_field_final_payload_count for item in raws)
    calls = sum(item.stage_one_provider_call_count for item in raws)
    s1_prompts = sum(
        request_kind == "semantic_proposal"
        and "prospective_role_scalable_semantic_action_prompt.v1" in prompt
        for request_kind, _, prompt in all_prompts
    )
    values = {
        "runner_contract_id": runner_contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "semantic_action_primary_count": action_attempts,
        "exact_four_field_action_payload_count": action_attempts,
        "reversible_commit_count": commits,
        "public_observation_count": observations,
        "exact_two_field_final_payload_count": final_payloads,
        "privacy_envelope_count": calls,
        "public_projection_count": calls,
        "envelope_before_projection_pass_count": calls,
        "s1_action_prompt_count": s1_prompts,
        "fixture_hash": _fixture_hash(raws),
        "scripted_local_calls": calls,
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_runner_fixture:",
        ),
        **values,
    )


def _control_row(name: str, metrics: Mapping[str, Any]) -> RunnerControlRow:
    values = {"control_name": name, "metrics": dict(metrics)}
    provisional = RunnerControlRow.model_construct(control_id="pending", **values)
    return RunnerControlRow(
        control_id=_identity(
            provisional,
            "control_id",
            "finance_v26_s1_qualification_runner_control_row:",
        ),
        **values,
    )


def _run_control_job(
    *,
    loaded: _LoadedInputs,
    job: S1QualificationJob,
    resource: S1QualificationResourceContract,
    runner_contract: S1QualificationRunnerContract,
    root: Path,
    **client_kwargs: Any,
) -> tuple[S1QualificationRawExecution, ScriptedS1QualificationClient]:
    old, binding = _job_context(loaded, job)
    client = ScriptedS1QualificationClient(
        loaded.engineering.agent_model_config,
        final_answer=binding.compiler_trajectory.final_answer,
        **client_kwargs,
    )
    raw = execute_s1_qualification_job_raw(
        job=job,
        old_job=old,
        runner_contract=runner_contract,
        resource_contract=resource,
        static=loaded.engineering,
        binding=binding,
        client=client,
        output_dir=root,
    )
    return raw, client


def _make_runner_controls(
    *,
    loaded: _LoadedInputs,
    manifest: S1QualificationManifest,
    resource: S1QualificationResourceContract,
    runner_contract: S1QualificationRunnerContract,
) -> RunnerControlAudit:
    ordinary_job = manifest.jobs[0]
    detour_job = next(
        item for item in manifest.jobs if item.predecessor_path_audit_id == EXPECTED_DETOUR_PATH_ID
    )
    rows: list[RunnerControlRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_133_controls_") as temporary:
        base = Path(temporary)
        abi, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "abi",
            malformed_action_once=True,
        )
        if (
            abi.terminal_disposition != "completed_model_result"
            or abi.abi_rescue_attempt_count != 1
        ):
            raise ValueError("v26.133 ABI Rescue control failed")
        rows.append(_control_row("s1_exact_abi_rescue", {"abi_rescues": 1}))

        semantic, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "semantic",
            semantic_rejection_once=True,
        )
        if (
            semantic.terminal_disposition != "completed_model_result"
            or semantic.semantic_recovery_attempt_count != 1
            or semantic.abi_rescue_attempt_count != 0
        ):
            raise ValueError("v26.133 Semantic Recovery control failed")
        rows.append(
            _control_row(
                "semantic_recovery_counter_separate",
                {"semantic_recoveries": 1, "abi_rescues": 0},
            )
        )

        transport, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "transport",
            transport_failure_once=True,
        )
        if (
            transport.terminal_disposition != "completed_model_result"
            or transport.transport_replacement_attempt_count != 1
            or transport.transport_inclusive_invocation_count
            != transport.stage_one_provider_call_count + 1
        ):
            raise ValueError("v26.133 Transport Replacement control failed")
        rows.append(
            _control_row(
                "transport_replacement_counter_separate",
                {
                    "transport_replacements": 1,
                    "provider_calls": transport.stage_one_provider_call_count,
                    "transport_invocations": transport.transport_inclusive_invocation_count,
                },
            )
        )

        privacy, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "privacy",
            privacy_failure_once=True,
        )
        privacy_bytes = b"".join(
            (base / "privacy" / item.relative_path).read_bytes()
            for item in privacy.provider_envelope_artifacts
        )
        projection_bytes = b"".join(
            (base / "privacy" / item.relative_path).read_bytes()
            for item in privacy.public_payload_projection_artifacts
        )
        if (
            privacy.privacy_rejected_payload_count != 1
            or b"fixture private content" in privacy_bytes + projection_bytes
            or b"reasoning_trace" in privacy_bytes + projection_bytes
        ):
            raise ValueError("v26.133 privacy-first rejection control failed")
        rows.append(_control_row("privacy_first_envelope_projection", {"rejections": 1}))

        for tokens in (16_384, 16_385):
            usage, _ = _run_control_job(
                loaded=loaded,
                job=ordinary_job,
                resource=resource,
                runner_contract=runner_contract,
                root=base / f"usage_{tokens}",
                completion_tokens=tokens,
            )
            if usage.terminal_disposition != "completed_model_result":
                raise ValueError("v26.133 admitted Usage boundary failed")
        rejected_usage, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "usage_16386",
            completion_tokens=16_386,
        )
        if rejected_usage.terminal_disposition != "instrument_failure":
            raise ValueError("v26.133 rejected Usage boundary failed")
        rows.append(
            _control_row(
                "completion_usage_boundaries",
                {"admitted": [16384, 16385], "instrument_failure": 16386},
            )
        )

        one_detour, _ = _run_control_job(
            loaded=loaded,
            job=detour_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "one_detour",
            force_action_id=EXPECTED_DETOUR_ACTION_ID,
            force_action_uses=1,
        )
        if (
            one_detour.terminal_disposition != "completed_model_result"
            or one_detour.ordinary_detour_count != 1
            or one_detour.abi_rescue_attempt_count
            or one_detour.semantic_recovery_attempt_count
            or one_detour.transport_replacement_attempt_count
        ):
            raise ValueError("v26.133 one-Detour control failed")
        rows.append(
            _control_row(
                "one_ordinary_detour_then_replan",
                {
                    "ordinary_detours": 1,
                    "other_recovery_counters": [0, 0, 0],
                },
            )
        )

        two_detour, _ = _run_control_job(
            loaded=loaded,
            job=detour_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "two_detour",
            force_action_id=EXPECTED_DETOUR_ACTION_ID,
            force_action_uses=2,
        )
        if (
            two_detour.terminal_disposition != "ordinary_detour_allowance_exhausted"
            or two_detour.ordinary_detour_count != 2
            or len(two_detour.progress_events) < 2
            or not two_detour.progress_events[-1].ordinary_detour_observed
            or two_detour.later_provider_calls_after_detour_terminal != 0
        ):
            raise ValueError("v26.133 second-Detour terminal control failed")
        rows.append(
            _control_row(
                "second_detour_typed_measurement_terminal",
                {
                    "ordinary_detours_observed": 2,
                    "later_provider_calls": 0,
                    "proposal_and_tool_observation_retained": True,
                },
            )
        )

        wrong, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "wrong_final",
            wrong_final_answer=True,
        )
        if (
            wrong.terminal_disposition != "completed_model_result"
            or not wrong.first_action_interface_qualified
            or wrong.exact_two_field_final_payload_count != 1
        ):
            raise ValueError("v26.133 wrong-answer separation control failed")
        rows.append(
            _control_row(
                "representation_abi_separate_from_answer_validity",
                {"exact_final_abi": 1, "answer_validity_used_for_representation_gate": False},
            )
        )

        old, binding = _job_context(loaded, ordinary_job)
        recovered = execute_s1_qualification_job_raw(
            job=ordinary_job,
            old_job=old,
            runner_contract=runner_contract,
            resource_contract=resource,
            static=loaded.engineering,
            binding=binding,
            client=None,
            output_dir=base / "abi",
        )
        if recovered.model_dump(mode="json") != abi.model_dump(mode="json"):
            raise ValueError("v26.133 control Raw recovery changed")
        rows.append(_control_row("complete_raw_zero_call_recovery", {"recovered": 1}))

        orphan_root = base / "orphan"
        orphan_path = privacy_runner.provider_envelope_path(orphan_root, cast(Any, ordinary_job), 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            execute_s1_qualification_job_raw(
                job=ordinary_job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            pass
        else:
            raise ValueError("v26.133 orphan artifact did not fail closed")
        rows.append(_control_row("orphan_artifact_blocks_retry", {"rejected": 1}))

        rows.append(
            _control_row(
                "s1_only_no_full_object_fallback",
                {"s1_candidate_id": EXPECTED_S1_CANDIDATE_ID, "fallback_count": 0},
            )
        )
        rows.append(
            _control_row(
                "role_class_external_frequency_opportunity_separation",
                {
                    "retained_role_external_actions": ROLE_CLASS_EXTERNAL_ACTION_COUNT,
                    "engineering_online_opportunities": 0,
                    "zero_opportunity_is_not_zero_frequency": True,
                },
            )
        )
        rows.append(
            _control_row(
                "resource_and_counter_vector_exact",
                {
                    "resource": [60000, 21, 23, 24, 1120000],
                    "counters": [1, 1, 1, 1],
                },
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.control_id))
    values = {"runner_contract_id": runner_contract.contract_id, "rows": ordered}
    provisional = RunnerControlAudit.model_construct(audit_id="pending", **values)
    return RunnerControlAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_s1_qualification_runner_control_audit:",
        ),
        **values,
    )


def _expect_rejected(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except (ValueError, TypeError):
        return MutationResult(mutation=name)
    raise ValueError(f"v26.133 destructive mutation was accepted: {name}")


def _make_destructive(
    *,
    source: QualificationSourceSeparationAudit,
    progress: PublicProgressVectorContract,
    catalog: S1QualificationPathCatalog,
    resource: S1QualificationResourceContract,
    contract: S1RepresentationQualificationContract,
    manifest: S1QualificationManifest,
    outcome: S1QualificationOutcomeContract,
    runner: S1QualificationRunnerContract,
) -> DestructiveAudit:
    callbacks: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "source_overlap_injection",
            lambda: QualificationSourceSeparationAudit.model_validate(
                source.model_copy(
                    update={
                        "separation_channels": (
                            source.separation_channels[0].model_copy(update={"overlap_count": 1}),
                            *source.separation_channels[1:],
                        )
                    }
                ).model_dump(mode="json")
            ),
        ),
        (
            "role_task_qualification_injection",
            lambda: QualificationSourceSeparationAudit.model_validate(
                source.model_copy(update={"role_tasks_used_by_qualification_jobs": 1}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "role_external_zero_opportunity_as_zero_frequency",
            lambda: QualificationSourceSeparationAudit.model_validate(
                source.model_copy(
                    update={
                        "role_external_frequency_has_online_opportunity_"
                        "in_engineering_denominator": True
                    }
                ).model_dump(mode="json")
            ),
        ),
        (
            "progress_vector_component_deletion",
            lambda: PublicProgressVectorContract.model_validate(
                progress.model_copy(
                    update={"component_order": progress.component_order[:-1]}
                ).model_dump(mode="json")
            ),
        ),
        (
            "progress_comparison_rule_change",
            lambda: PublicProgressVectorContract.model_validate(
                progress.model_copy(update={"comparison_rule": "set_equality"}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "unchanged_vector_called_useless",
            lambda: PublicProgressVectorContract.model_validate(
                progress.model_copy(
                    update={"unchanged_vector_means_action_useless": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "full_object_path_fallback",
            lambda: S1StateBindingRow.model_validate(
                catalog.paths[0]
                .state_rows[0]
                .model_copy(update={"full_object_fallback_used": True})
                .model_dump(mode="json")
            ),
        ),
        (
            "s1_path_state_deletion",
            lambda: S1QualificationPathCatalog.model_validate(
                catalog.model_copy(update={"paths": catalog.paths[:-1]}).model_dump(mode="json")
            ),
        ),
        (
            "prompt_ceiling_change",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(update={"prompt_upper_bound_bytes": 60001}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "primary_request_change",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(update={"maximum_primary_stage_one_requests": 22}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "provider_call_change",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(update={"maximum_stage_one_provider_calls": 24}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "transport_invocation_change",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(
                    update={"maximum_transport_inclusive_invocations": 25}
                ).model_dump(mode="json")
            ),
        ),
        (
            "rollout_change",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(update={"rollout_upper_bound_tokens": 1140000}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "second_detour_authorization",
            lambda: S1QualificationResourceContract.model_validate(
                resource.model_copy(update={"maximum_ordinary_detours": 2}).model_dump(mode="json")
            ),
        ),
        (
            "full_object_dynamic_fallback",
            lambda: S1RepresentationQualificationContract.model_validate(
                contract.model_copy(
                    update={"full_object_dynamic_fallback_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "role_provider_exposure",
            lambda: S1RepresentationQualificationContract.model_validate(
                contract.model_copy(
                    update={"role_task_provider_exposure_authorized": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "qualification_role_eligibility",
            lambda: S1RepresentationQualificationContract.model_validate(
                contract.model_copy(
                    update={"qualification_rows_role_or_state_eligible": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "qualification_threshold_relaxation",
            lambda: S1RepresentationQualificationContract.model_validate(
                contract.model_copy(update={"first_action_interface_minimum_jobs": 23}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "manifest_job_deletion",
            lambda: S1QualificationManifest.model_validate(
                manifest.model_copy(update={"jobs": manifest.jobs[:-1]}).model_dump(mode="json")
            ),
        ),
        (
            "manifest_role_source_job",
            lambda: S1QualificationManifest.model_validate(
                manifest.model_copy(update={"role_source_job_count": 1}).model_dump(mode="json")
            ),
        ),
        (
            "detour_terminal_as_model_invalid",
            lambda: S1QualificationOutcomeContract.model_validate(
                outcome.model_copy(
                    update={"detour_terminal_counts_as_model_invalid": True}
                ).model_dump(mode="json")
            ),
        ),
        (
            "counter_coupling",
            lambda: S1QualificationRunnerContract.model_validate(
                runner.model_copy(update={"all_four_counters_independent": False}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "stage_two_provider_route",
            lambda: S1QualificationRunnerContract.model_validate(
                runner.model_copy(update={"stage_two_provider_call_upper_bound": 1}).model_dump(
                    mode="json"
                )
            ),
        ),
        (
            "preflight_execution_authorization",
            lambda: S1QualificationRunnerContract.model_validate(
                runner.model_copy(update={"empirical_execution_authorized": True}).model_dump(
                    mode="json"
                )
            ),
        ),
    )
    mutations = tuple(_expect_rejected(name, callback) for name, callback in callbacks)
    values = {"mutations": mutations}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_s1_qualification_destructive:"),
        **values,
    )


def _make_transition(
    manifest: S1QualificationManifest,
    runner: S1QualificationRunnerContract,
    outcome: S1QualificationOutcomeContract,
) -> ProspectiveTransitionContract:
    values = {
        "exact_manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional, "contract_id", "finance_v26_s1_qualification_transition:"
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> S1QualificationPreflightReport:
    source_replay = _make_source_replay(package_root, implementation_root)
    loaded = _load_inputs(package_root, implementation_root)
    predecessor_binding = _make_predecessor_binding(loaded)
    source_separation = _make_source_separation(loaded)
    progress = _make_progress_contract()
    catalog = _make_path_catalog(loaded)
    resource = _make_resource_contract(catalog)
    contract = _make_qualification_contract(
        source=source_separation,
        progress=progress,
        catalog=catalog,
        resource=resource,
    )
    manifest = _make_manifest(
        loaded=loaded,
        contract=contract,
        catalog=catalog,
        resource=resource,
    )
    outcome = _make_outcome_contract(contract, manifest)
    runner = _make_runner_contract(
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        resource=resource,
        progress=progress,
    )
    fixture = _make_runner_fixture(
        loaded=loaded,
        manifest=manifest,
        resource=resource,
        runner_contract=runner,
    )
    controls = _make_runner_controls(
        loaded=loaded,
        manifest=manifest,
        resource=resource,
        runner_contract=runner,
    )
    destructive = _make_destructive(
        source=source_separation,
        progress=progress,
        catalog=catalog,
        resource=resource,
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        runner=runner,
    )
    transition = _make_transition(manifest, runner, outcome)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source_replay),
        ("frozen_predecessor_binding_audit.json", predecessor_binding),
        ("qualification_source_separation_audit.json", source_separation),
        ("public_progress_vector_contract.json", progress),
        ("s1_qualification_path_catalog.json", catalog),
        ("s1_qualification_resource_contract.json", resource),
        ("s1_representation_qualification_contract.json", contract),
        ("s1_qualification_manifest.json", manifest),
        ("s1_qualification_outcome_contract.json", outcome),
        ("s1_qualification_runner_contract.json", runner),
        ("s1_runner_fixture_audit.json", fixture),
        ("s1_runner_control_audit.json", controls),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for name, value in detail_values:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in sorted(detail_values))
    values = {
        "source_replay_audit_id": source_replay.audit_id,
        "predecessor_binding_audit_id": predecessor_binding.audit_id,
        "source_separation_audit_id": source_separation.audit_id,
        "progress_vector_contract_id": progress.contract_id,
        "path_catalog_id": catalog.catalog_id,
        "resource_contract_id": resource.contract_id,
        "qualification_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "runner_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = S1QualificationPreflightReport.model_construct(report_id="pending", **values)
    report = S1QualificationPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_s1_qualification_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
