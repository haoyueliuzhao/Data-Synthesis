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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
    evaluate_joint_support_validity,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    MechanismId,
    make_noninterference_artifact_binding,
)
from trusted_synthesis.core.measurement.support import MeasurementSupportDecision
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as bounded,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_capability_postrun_audit as audit_predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_joint_support_verifier_preflight as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as old_capability,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_runner_preflight as prompt_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as s1_runner,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
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
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseGrammar,
    make_final_response_host_envelope,
    parse_prompt_only_reference_final_payload,
    render_exact_final_primary_prompt,
)
from trusted_synthesis.runtime.agent.prospective_measurement_support import (
    classify_non_observation_support,
    classify_public_observation_support,
    resolve_public_baseline_action_set,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    compile_qualified_final_response_grammar,
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
    SemanticActionResponseGrammar,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

RUN_ID: Final = "finance_v26_153_fresh_reachability_runner_preflight_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_153_fresh_reachability_runner_preflight_v1_20260826"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_reachability_runner_vnext.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_reachability_runner_preflight.py",
)
NEXT_STAGE: Final = "fresh_reachability_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = "finance_v26_153_fresh_reachability_runner_v1_20260826"
PROSPECTIVE_EXECUTION_RUN_ID: Final = "finance_v26_154_fresh_reachability_execution_v1_20260826"
PROSPECTIVE_REPORT_RUN_ID: Final = "finance_v26_154_fresh_reachability_execution_report_v1_20260826"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_fresh_capability_postrun_audit_report:"
    "933a824cf81fda37f2a965a8b61640b4bc772058f04b25cd9f6033a9bb965a17"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "821b65586bdb8f850724a34280f4cf6f5ff0d31d663afe33d82ac2d7bf8e1f45"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_fresh_capability_postrun_transition:"
    "303b783806e77e47c9ddd84aa5fb00c879abecd8b08e17c04e0e9b2981bb89d3"
)
EXPECTED_JOINT_CONTRACT_ID: Final = (
    "prospective_joint_support_validity_contract:"
    "40c88c6abb299b83ebae7644f3f5e3d964cdbf0a61bfe4cd3ae520a5593714b2"
)
EXPECTED_OLD_CAPABILITY_POPULATION_ID: Final = (
    "finance_v26_fresh_role_source_population:"
    "1e22847979b0927e1f772ab8b945dc4e57c2e0dc3b95f0673b1d1543470975e3"
)
EXPECTED_OLD_REACHABILITY_POPULATION_ID: Final = (
    "finance_v26_fresh_role_source_population:"
    "cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99"
)
EXPECTED_V132_DYNAMIC_ENVELOPE_ID: Final = (
    "finance_v26_dynamic_trajectory_envelope_audit:"
    "610bdc36d7850f153b6bd694c5f454b03610b9fcaa3666faddc0293fd5120e56"
)

MECHANISMS: Final = tuple(source_base.TARGET_MECHANISMS)
TIERS: Final = tuple(source_base.TIERS)
FRESHNESS_CHANNELS: Final = tuple(source_base.FRESHNESS_CHANNELS)
TASK_COUNT: Final = 12
PATH_COUNT: Final = 36
JOB_COUNT: Final = 360
UNCONDITIONAL_REPLICAS_PER_TASK: Final = 12
CONDITIONED_REPLICAS_PER_PATH: Final = 6
PROMPT_CEILING_BYTES: Final = 60_000
MAXIMUM_PRIMARY_REQUESTS: Final = 21
MAXIMUM_PROVIDER_CALLS: Final = 23
MAXIMUM_TRANSPORT_INVOCATIONS: Final = 24
ROLLOUT_BOUND_TOKENS: Final = 1_120_000
COMPLETION_REQUEST_BOUND: Final = 16_384
ACCOUNTED_COMPLETION_BOUND: Final = 16_385
CHAT_ENVELOPE_TOKENS: Final = 256


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and _sha256(path) == expected_sha256:
            return path
    raise ValueError(f"v26.153 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_152_transitive_source",
        "v26_152_output",
        "v26_153_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[10125] = 10125
    predecessor_output_file_count: Literal[9] = 9
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[10136] = 10136
    replay_pass_count: Literal[10136] = 10136
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=10136, max_length=10136)
    replay_before_reachability_input_load: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_fresh_reachability_source_replay.v1"] = (
        "finance_v26_fresh_reachability_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_reachability_source_replay:")
        ):
            raise ValueError("v26.153 source replay changed")
        return self


class FileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    comparisons: tuple[FileComparison, ...] = Field(min_length=9, max_length=9)
    predecessor_output_file_count: Literal[9] = 9
    byte_identical_file_count: Literal[9] = 9
    capability_measurement_gate_passed: Literal[True] = True
    reachability_minimum_support_gate_passed: Literal[True] = True
    historical_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_fresh_reachability_predecessor_integrity.v1"] = (
        "finance_v26_fresh_reachability_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_predecessor_integrity:",
        ):
            raise ValueError("v26.153 predecessor integrity changed")
        return self


class FrozenReachabilityInputAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    frozen_population_id: str = EXPECTED_OLD_REACHABILITY_POPULATION_ID
    frozen_capability_population_id: str = EXPECTED_OLD_CAPABILITY_POPULATION_ID
    source_frame_population_id: str = Field(min_length=1)
    original_role_source_selection_audit_id: str = Field(min_length=1)
    bindings: tuple[source_base.RoleSourceTaskBinding, ...] = Field(min_length=12, max_length=12)
    task_count: Literal[12] = 12
    mechanism_tier_cell_count: Literal[12] = 12
    source_task_artifact_count: Literal[12] = 12
    model_exposure_count_before_preflight: Literal[0] = 0
    selected_before_kernel_load: Literal[True] = True
    selected_before_capability_execution: Literal[True] = True
    capability_outcomes_used_for_selection: Literal[False] = False
    verifier_passability_used_for_selection: Literal[False] = False
    resource_values_used_for_selection: Literal[False] = False
    fresh_source_reselection_count: Literal[0] = 0
    frozen_population_bytes_preserved: Literal[True] = True
    cross_role_source_overlap_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["frozen_reachability_population_replayed"] = (
        "frozen_reachability_population_replayed"
    )
    schema_version: Literal["finance_v26_frozen_reachability_input_audit.v1"] = (
        "finance_v26_frozen_reachability_input_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenReachabilityInputAudit:
        cells = {(item.mechanism_id, item.tier) for item in self.bindings}
        if (
            len(cells) != 12
            or cells != {(mechanism, tier) for mechanism in MECHANISMS for tier in TIERS}
            or len({item.source_task_artifact_id for item in self.bindings}) != 12
            or any(item.role != "reachability" for item in self.bindings)
            or self.capability_outcomes_used_for_selection
            or self.fresh_source_reselection_count != 0
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_frozen_reachability_input_audit:")
        ):
            raise ValueError("v26.153 frozen Reachability input changed")
        return self


class FreshReachabilityTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    frozen_input_audit_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["reachability"] = "reachability"
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    operational_record: OperationalTaskRecord
    environment: AgentToolEnvironmentManifest
    prompt_contract: CompactPromptContract
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    measurement_support_contract_id: str = predecessor.EXPECTED_SUPPORT_CONTRACT_ID
    verifier_vnext_contract_id: str = Field(min_length=1)
    qualified_final_grammar_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = old_capability.EXPECTED_PROMPT_CONTRACT_ID
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    model_config_id: str = bounded.EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = bounded.EXPECTED_THINKING_BINDING_ID
    thinking_type: Literal["enabled"] = "enabled"
    compact_projection_protocol_id: str = bounded.EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = bounded.EXPECTED_S1_CANDIDATE_ID
    semantic_action_protocol_id: str = bounded.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_grammar_id: str = bounded.EXPECTED_ACTION_GRAMMAR_ID
    candidate_authority_preserved: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_fresh_reachability_task_package.v1"] = (
        "finance_v26_fresh_reachability_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> FreshReachabilityTaskPackage:
        if (
            self.operational_record.environment_manifest_id != self.environment.manifest_id
            or self.prompt_contract.role != "reachability"
            or self.task_package_id
            != _identity(self, "task_package_id", "finance_v26_fresh_reachability_task_package:")
        ):
            raise ValueError("v26.153 TaskPackage changed")
        return self


class TaskPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    frozen_input_audit_id: str = Field(min_length=1)
    packages: tuple[FreshReachabilityTaskPackage, ...] = Field(min_length=12, max_length=12)
    task_package_count: Literal[12] = 12
    mechanism_tier_cell_count: Literal[12] = 12
    old_task_package_overlap_count: Literal[0] = 0
    reachability_task_package_count: Literal[12] = 12
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> TaskPackageCatalog:
        if len(
            {item.task_package_id for item in self.packages}
        ) != 12 or self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_fresh_reachability_task_catalog:"
        ):
            raise ValueError("v26.153 TaskPackage Catalog changed")
        return self


class FreshReachabilityPath(FrozenModel):
    path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["reachability"] = "reachability"
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    path_strategy_id: PathStrategy
    public_path_condition: str = Field(min_length=1)
    public_condition_id: str = Field(min_length=1)
    reference_state_ids: tuple[str, ...] = Field(min_length=1)
    reference_proposal_ids: tuple[str, ...] = Field(min_length=1)
    reference_commit_ids: tuple[str, ...] = Field(min_length=1)
    reference_observation_ids: tuple[str, ...]
    measurement_support_decision_ids: tuple[str, ...] = Field(min_length=1)
    action_state_count: int = Field(ge=1)
    public_observation_count: int = Field(ge=0)
    maximum_candidate_count: int = Field(gt=0)
    maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0)
    maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0)
    maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0)
    final_primary_prompt_utf8_bytes: int = Field(gt=0)
    final_rescue_prompt_utf8_bytes: int = Field(gt=0)
    primary_request_count: int = Field(ge=2)
    maximum_provider_calls_with_recovery: int = Field(ge=4)
    maximum_transport_inclusive_invocations: int = Field(ge=5)
    static_complete_path_upper_bound_tokens: int = Field(gt=0)
    program_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    exact_state_candidate_commit_preserved: Literal[True] = True
    support_exit_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_path(self) -> FreshReachabilityPath:
        count = self.action_state_count
        if (
            len(self.reference_state_ids) != count
            or len(self.reference_proposal_ids) != count
            or len(self.reference_commit_ids) != count
            or len(self.reference_observation_ids) != count - 1
            or len(self.measurement_support_decision_ids) != count
            or self.primary_request_count != count + 1
            or self.maximum_provider_calls_with_recovery != self.primary_request_count + 2
            or self.maximum_transport_inclusive_invocations
            != self.maximum_provider_calls_with_recovery + 1
            or self.public_path_condition != self.path_strategy_id
            or self.maximum_action_primary_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.primary_request_count > MAXIMUM_PRIMARY_REQUESTS
            or self.static_complete_path_upper_bound_tokens >= ROLLOUT_BOUND_TOKENS
            or self.path_id != _identity(self, "path_id", "finance_v26_fresh_reachability_path:")
        ):
            raise ValueError("v26.153 Reachability Path changed")
        return self


class PathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    paths: tuple[FreshReachabilityPath, ...] = Field(min_length=36, max_length=36)
    path_count: Literal[36] = 36
    registered_state_count: int = Field(gt=0)
    maximum_candidate_count: int = Field(gt=0)
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    maximum_registered_path_tokens: int = Field(gt=0)
    old_path_overlap_count: Literal[0] = 0
    reachability_path_count: Literal[36] = 36
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> PathCatalog:
        if (
            len({item.path_id for item in self.paths}) != 36
            or self.registered_state_count != sum(item.action_state_count for item in self.paths)
            or self.catalog_id
            != _identity(self, "catalog_id", "finance_v26_fresh_reachability_path_catalog:")
        ):
            raise ValueError("v26.153 Path Catalog changed")
        return self


class SupportClosureEventRow(FrozenModel):
    row_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    observation_status: str | None
    successor_available: bool
    decision: MeasurementSupportDecision
    host_exception: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> SupportClosureEventRow:
        if self.row_id != _identity(
            self,
            "row_id",
            "finance_v26_fresh_reachability_support_event:",
        ):
            raise ValueError("v26.153 Support event changed")
        return self


class SupportClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    support_contract_id: str = predecessor.EXPECTED_SUPPORT_CONTRACT_ID
    path_catalog_id: str = Field(min_length=1)
    unique_state_count: int = Field(gt=0)
    candidate_event_count: int = Field(gt=0)
    typed_decision_count: int = Field(gt=0)
    failed_observation_event_count: int = Field(ge=0)
    failed_observation_baseline_call_count: Literal[0] = 0
    progress_observation_baseline_call_count: Literal[0] = 0
    successful_no_progress_event_count: int = Field(ge=0)
    successful_no_progress_baseline_call_count: int = Field(ge=0)
    ordinary_detour_event_count: int = Field(ge=0)
    typed_support_exit_count: int = Field(ge=0)
    host_exception_count: Literal[0] = 0
    event_rows: tuple[SupportClosureEventRow, ...] = Field(min_length=1)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> SupportClosureAudit:
        if (
            self.typed_decision_count != self.candidate_event_count
            or self.successful_no_progress_baseline_call_count
            != self.successful_no_progress_event_count
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_reachability_support_closure:")
        ):
            raise ValueError("v26.153 Support Closure changed")
        return self


class ReachabilityDetourQualificationRow(FrozenModel):
    row_id: str = Field(min_length=1)
    support_closure_row_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    state_id: str = Field(min_length=1)
    selected_action_id: str = Field(min_length=1)
    primary_request_count: int = Field(ge=2, le=21)
    provider_call_count_with_recoveries: int = Field(ge=4, le=23)
    transport_inclusive_invocation_count: int = Field(ge=5, le=24)
    maximum_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, lt=1120000)
    selected_rollout_headroom_tokens: int = Field(ge=20000)
    detour_observation_succeeded: Literal[True] = True
    progress_vector_unchanged: Literal[True] = True
    ordinary_replan_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_commit_reached: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> ReachabilityDetourQualificationRow | None:
        if (
            self.provider_call_count_with_recoveries != self.primary_request_count + 2
            or self.transport_inclusive_invocation_count
            != self.provider_call_count_with_recoveries + 1
            or self.selected_rollout_headroom_tokens
            != ROLLOUT_BOUND_TOKENS - self.static_complete_path_upper_bound_tokens
            or self.row_id
            != _identity(
                self,
                "row_id",
                "finance_v26_fresh_reachability_detour_qualification:",
            )
        ):
            raise ValueError("v26.153 Detour qualification row changed")
        return self


class ReachabilityDetourQualificationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_dynamic_envelope_audit_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    rows: tuple[ReachabilityDetourQualificationRow, ...] = Field(min_length=1)
    candidate_detour_count: int = Field(gt=0)
    qualified_closed_row_count: int = Field(gt=0)
    ordinary_replan_not_closed_count: int = Field(ge=0)
    distinct_path_count: int = Field(gt=0, le=36)
    maximum_primary_requests: int = Field(ge=2, le=21)
    maximum_provider_calls: int = Field(ge=4, le=23)
    maximum_transport_invocations: int = Field(ge=5, le=24)
    maximum_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_static_tokens: int = Field(gt=0, lt=1100000)
    minimum_rollout_headroom_tokens: int = Field(ge=20000)
    all_qualified_rows_closed_under_current_prompt_and_final_grammar: Literal[True] = True
    class_external_rows_retained_as_diagnostic: Literal[True] = True
    provider_calls: Literal[0] = 0
    status: Literal["current_reachability_detours_requalified"] = (
        "current_reachability_detours_requalified"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ReachabilityDetourQualificationAudit:
        if (
            len({item.row_id for item in self.rows}) != len(self.rows)
            or self.qualified_closed_row_count != len(self.rows)
            or self.candidate_detour_count
            != self.qualified_closed_row_count + self.ordinary_replan_not_closed_count
            or self.maximum_static_tokens
            != max(item.static_complete_path_upper_bound_tokens for item in self.rows)
            or self.minimum_rollout_headroom_tokens
            != min(item.selected_rollout_headroom_tokens for item in self.rows)
            or self.audit_id
            != _identity(
                self,
                "audit_id",
                "finance_v26_fresh_reachability_detour_audit:",
            )
        ):
            raise ValueError("v26.153 Detour qualification audit changed")
        return self


class ResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
    detour_qualification_audit_id: str = Field(min_length=1)
    prompt_upper_bound_bytes: Literal[60000] = PROMPT_CEILING_BYTES
    maximum_primary_stage_one_requests: Literal[21] = MAXIMUM_PRIMARY_REQUESTS
    maximum_stage_one_provider_calls: Literal[23] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[24] = MAXIMUM_TRANSPORT_INVOCATIONS
    rollout_upper_bound_tokens: Literal[1120000] = ROLLOUT_BOUND_TOKENS
    accounted_completion_bound_tokens: Literal[16385] = ACCOUNTED_COMPLETION_BOUND
    chat_envelope_tokens: Literal[256] = CHAT_ENVELOPE_TOKENS
    qualified_maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    measured_maximum_reference_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    measured_maximum_reference_path_tokens: int = Field(gt=0, lt=1120000)
    conservative_one_detour_upper_bound_tokens: int = Field(gt=0, lt=1100000)
    selected_rollout_headroom_tokens: int = Field(ge=20000)
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> ResourceContract:
        if (
            self.selected_rollout_headroom_tokens
            != self.rollout_upper_bound_tokens - self.conservative_one_detour_upper_bound_tokens
            or self.contract_id
            != _identity(
                self,
                "contract_id",
                "finance_v26_fresh_reachability_resource_contract:",
            )
        ):
            raise ValueError("v26.153 Resource Contract changed")
        return self


class ExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_population_id: str = EXPECTED_OLD_REACHABILITY_POPULATION_ID
    frozen_input_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    qualified_final_grammar_id: str = Field(min_length=1)
    exact_denominator: Literal[360] = JOB_COUNT
    task_count: Literal[12] = TASK_COUNT
    registered_path_count: Literal[36] = PATH_COUNT
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    unconditional_replicas_per_task: Literal[12] = UNCONDITIONAL_REPLICAS_PER_TASK
    conditioned_replicas_per_path: Literal[6] = CONDITIONED_REPLICAS_PER_PATH
    role: Literal["reachability"] = "reachability"
    unconditional_and_conditioned_estimands_separate: Literal[True] = True
    compiler_static_route_is_not_empirical_state: Literal[True] = True
    valid_only_state_mapping_deferred: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> ExecutionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_reachability_execution_contract:",
        ):
            raise ValueError("v26.153 Execution Contract changed")
        return self


SamplingMode = Literal["reachability_unconditional", "reachability_conditioned"]


class FreshReachabilityJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0, le=11)
    seed: int = Field(ge=0)
    requested_path_id: str | None
    requested_path_strategy: PathStrategy | None
    public_path_condition: str | None
    public_condition_id: str | None
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    candidate_presentation_parent_id: str = Field(min_length=1)
    historical_job_identity_reused: Literal[False] = False
    frozen_v26_132_seed_preserved: Literal[True] = True
    execution_opened: Literal[False] = False

    @model_validator(mode="after")
    def validate_job(self) -> FreshReachabilityJob:
        conditioned = self.sampling_mode == "reachability_conditioned"
        conditional = (
            self.requested_path_id,
            self.requested_path_strategy,
            self.public_path_condition,
            self.public_condition_id,
        )
        if conditioned != all(item is not None for item in conditional):
            raise ValueError("v26.153 conditioned Job binding changed")
        if not conditioned and any(item is not None for item in conditional):
            raise ValueError("v26.153 unconditional Job carries a Path condition")
        if conditioned and self.replicate_index >= CONDITIONED_REPLICAS_PER_PATH:
            raise ValueError("v26.153 conditioned replicate denominator changed")
        if self.job_id != _identity(
            self,
            "job_id",
            "finance_v26_fresh_reachability_job:",
        ):
            raise ValueError("v26.153 Job changed")
        return self


class ReachabilityManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_population_id: str = EXPECTED_OLD_REACHABILITY_POPULATION_ID
    frozen_input_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_report_run_id: str = PROSPECTIVE_REPORT_RUN_ID
    jobs: tuple[FreshReachabilityJob, ...] = Field(min_length=360, max_length=360)
    exact_denominator: Literal[360] = JOB_COUNT
    distinct_task_count: Literal[12] = TASK_COUNT
    distinct_path_count: Literal[36] = PATH_COUNT
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    distinct_seed_count: Literal[360] = JOB_COUNT
    historical_job_overlap_count: Literal[0] = 0
    preserved_v26_132_seed_count: Literal[360] = JOB_COUNT
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> ReachabilityManifest:
        task_counts = Counter(item.task_package_id for item in self.jobs)
        modes = Counter(item.sampling_mode for item in self.jobs)
        paths = Counter(
            cast(str, item.requested_path_id)
            for item in self.jobs
            if item.sampling_mode == "reachability_conditioned"
        )
        if (
            len({item.job_id for item in self.jobs}) != JOB_COUNT
            or len({item.seed for item in self.jobs}) != JOB_COUNT
            or len(task_counts) != TASK_COUNT
            or set(task_counts.values()) != {30}
            or modes
            != Counter({"reachability_unconditional": 144, "reachability_conditioned": 216})
            or len(paths) != PATH_COUNT
            or set(paths.values()) != {CONDITIONED_REPLICAS_PER_PATH}
            or any(
                item.candidate_presentation_parent_id != self.frozen_input_audit_id
                for item in self.jobs
            )
            or self.manifest_id
            != _identity(self, "manifest_id", "finance_v26_fresh_reachability_manifest:")
        ):
            raise ValueError("v26.153 Manifest changed")
        return self


class OutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    exact_denominator: Literal[360] = JOB_COUNT
    measurement_gate: tuple[str, ...] = (
        "complete_raw_360_of_360",
        "model_endpoint_360_of_360",
        "measurement_support_exit_zero",
        "instrument_failure_zero",
        "privacy_failure_zero",
        "exact_model_thinking_usage_failure_zero",
        "typed_budget_no_call_zero",
        "unresolved_transport_failure_zero",
    )
    primary_estimands: tuple[str, str, str] = (
        "unconditional_qualified_reachability",
        "conditioned_qualified_reachability",
        "qualified_state_mapping_eligibility",
    )
    task_and_path_primary_rollout_secondary: Literal[True] = True
    static_route_condition_not_accepted_as_empirical_state: Literal[True] = True
    state_mapping_eligibility_requires_qualified_valid_true: Literal[True] = True
    no_posthoc_task_deletion_threshold_change_or_host_repair: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    state_mapping_rows: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> OutcomeContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_reachability_outcome_contract:",
        ):
            raise ValueError("v26.153 Outcome Contract changed")
        return self


class RunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    qualified_final_grammar_id: str = Field(min_length=1)
    runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    exact_job_denominator: Literal[360] = JOB_COUNT
    maximum_primary_stage_one_requests: Literal[21] = MAXIMUM_PRIMARY_REQUESTS
    maximum_stage_one_provider_calls: Literal[23] = MAXIMUM_PROVIDER_CALLS
    maximum_transport_inclusive_invocations: Literal[24] = MAXIMUM_TRANSPORT_INVOCATIONS
    maximum_ordinary_detours: Literal[1] = 1
    measurement_support_after_observation_before_next_provider: Literal[True] = True
    failed_and_progress_observation_skip_baseline: Literal[True] = True
    successful_no_progress_only_baseline: Literal[True] = True
    qualified_final_parser_before_usable_classification: Literal[True] = True
    privacy_envelope_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    exact_model_thinking_profile_required: Literal[True] = True
    condition_bound_before_provider_invocation: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    reachability_identity_or_route_present: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> RunnerContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_reachability_runner_contract:",
        ):
            raise ValueError("v26.153 Runner Contract changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    scripted_job_count: Literal[360] = JOB_COUNT
    completed_job_count: Literal[360] = JOB_COUNT
    first_action_interface_qualified_count: Literal[360] = JOB_COUNT
    qualified_final_payload_count: Literal[360] = JOB_COUNT
    joint_task_verifier_invocation_count: Literal[360] = JOB_COUNT
    joint_qualified_valid_count: Literal[360] = JOB_COUNT
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    covered_mechanism_tier_cell_count: Literal[12] = 12
    covered_conditioned_path_count: Literal[36] = PATH_COUNT
    scripted_local_calls: int = Field(gt=0)
    action_payload_count: int = Field(gt=0)
    public_observation_count: int = Field(gt=0)
    support_decision_count: int = Field(gt=0)
    raw_recovery_pass_count: Literal[360] = JOB_COUNT
    sensitive_prompt_key_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_runner_fixture:",
        ):
            raise ValueError("v26.153 Runner Fixture changed")
        return self


class ControlRow(FrozenModel):
    row_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    metrics: dict[str, Any]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> ControlRow:
        if self.row_id != _identity(self, "row_id", "finance_v26_fresh_reachability_control:"):
            raise ValueError("v26.153 Control Row changed")
        return self


class RunnerControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[ControlRow, ...] = Field(min_length=20)
    control_count: int = Field(ge=20)
    passed_count: int = Field(ge=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerControlAudit:
        if (
            self.control_count != len(self.rows)
            or self.passed_count != self.control_count
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_reachability_runner_controls:")
        ):
            raise ValueError("v26.153 Runner Controls changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=30)
    mutation_count: int = Field(ge=30)
    rejected_count: int = Field(ge=30)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            self.mutation_count != len(self.mutations)
            or self.rejected_count != self.mutation_count
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_reachability_destructive:")
        ):
            raise ValueError("v26.153 Destructive Audit changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_reachability_execution_only"] = NEXT_STAGE
    exact_fresh_360_job_execution_authorized: Literal[True] = True
    state_mapping_contract_or_rows_authorized: Literal[False] = False
    historical_rerun_pooling_or_reclassification_authorized: Literal[False] = False
    task_path_condition_grammar_model_resource_change_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_reachability_transition:",
        ):
            raise ValueError("v26.153 Transition changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class ReachabilityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    source_population_id: str = EXPECTED_OLD_REACHABILITY_POPULATION_ID
    frozen_input_audit_id: str = Field(min_length=1)
    task_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
    detour_qualification_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    fresh_task_package_count: Literal[12] = TASK_COUNT
    fresh_path_count: Literal[36] = PATH_COUNT
    fresh_job_count: Literal[360] = JOB_COUNT
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["fresh_reachability_execution_only"] = NEXT_STAGE
    detail_files: tuple[DetailFile, ...] = Field(min_length=18)
    status: Literal["fresh_reachability_runner_preflight_passed"] = (
        "fresh_reachability_runner_preflight_passed"
    )

    @model_validator(mode="after")
    def validate_report(self) -> ReachabilityPreflightReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_fresh_reachability_preflight_report:",
        ):
            raise ValueError("v26.153 Report changed")
        return self


@dataclass(frozen=True)
class _CompiledPath:
    package: FreshReachabilityTaskPackage
    path: FreshReachabilityPath | None
    path_strategy_id: str
    public_path_condition: str | None
    states: tuple[SemanticActionState, ...]
    proposals: tuple[CanonicalActionProposal, ...]
    commits: tuple[CanonicalActionCommit, ...]
    observations: tuple[AgentToolObservation, ...]
    action_prompts: tuple[str, ...]
    qualified_final_primary_prompt: str
    qualified_final_rescue_prompt: str
    legacy_final_primary_prompt: str


@dataclass(frozen=True)
class _FrozenReachabilityInputs:
    population: source_base.FreshRoleSourcePopulation
    source_tasks: dict[str, CapabilitySensitiveTaskArtifact]
    selection: source_base.RoleSourceSelectionAudit
    frame_population_id: str


def _source_replay(*, package_root: Path, implementation_root: Path) -> SourceReplayAudit:
    predecessor_dir = package_root / audit_predecessor.OUTPUT_DIR
    report_path = predecessor_dir / "report.json"
    transition_path = predecessor_dir / "prospective_transition_contract.json"
    report = audit_predecessor.PostrunAuditReport.model_validate(_load(report_path))
    transition = audit_predecessor.ProspectiveTransitionContract.model_validate(
        _load(transition_path)
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or report.next_permitted_stage != audit_predecessor.NEXT_STAGE
        or not report.measurement_gate_passed
        or not report.reachability_minimum_support_gate_passed
        or report.reachability_identity_count != 0
        or report.state_mapping_row_count != 0
    ):
        raise ValueError("v26.153 direct predecessor changed")
    old_source = audit_predecessor.PostrunSourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    if old_source.replayed_file_count != 10125:
        raise ValueError("v26.153 predecessor replay denominator changed")
    entries: list[SourceReplayEntry] = []
    for item in old_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_152_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    output_names = tuple(item.relative_path for item in report.detail_files) + ("report.json",)
    if len(output_names) != 9 or len(set(output_names)) != 9:
        raise ValueError("v26.153 predecessor output denominator changed")
    for name in output_names:
        path = predecessor_dir / name
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_152_output",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    for relative_path in IMPLEMENTATION_PATHS:
        path = implementation_root / relative_path
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative_path,
                source_kind="v26_153_implementation",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_source_replay:",
        ),
        **values,
    )


def _predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    formal_dir = package_root / audit_predecessor.OUTPUT_DIR
    with tempfile.TemporaryDirectory(prefix="v26_153_predecessor_") as temporary:
        rebuilt_dir = Path(temporary)
        audit_predecessor.build_postrun_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            execution_dir=package_root / audit_predecessor.execution.OUTPUT_DIR,
            output_dir=rebuilt_dir,
        )
        formal_names = tuple(sorted(path.name for path in formal_dir.iterdir() if path.is_file()))
        rebuilt_names = tuple(sorted(path.name for path in rebuilt_dir.iterdir() if path.is_file()))
        if formal_names != rebuilt_names or len(formal_names) != 9:
            raise ValueError("v26.153 predecessor reconstruction denominator changed")
        comparisons = tuple(
            FileComparison(
                relative_path=name,
                expected_sha256=_sha256(formal_dir / name),
                observed_sha256=_sha256(rebuilt_dir / name),
                byte_count=(formal_dir / name).stat().st_size,
                byte_identical=cast(
                    Literal[True],
                    (formal_dir / name).read_bytes() == (rebuilt_dir / name).read_bytes(),
                ),
            )
            for name in formal_names
        )
    if any(not item.byte_identical for item in comparisons):
        raise ValueError("v26.153 predecessor output bytes changed")
    values = {
        "source_replay_audit_id": source.audit_id,
        "comparisons": comparisons,
    }
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_predecessor_integrity:",
        ),
        **values,
    )


def _load_frozen_reachability_inputs(
    *,
    package_root: Path,
    source: SourceReplayAudit,
) -> tuple[_FrozenReachabilityInputs, FrozenReachabilityInputAudit]:
    design_dir = package_root / bounded.predecessor.OUTPUT_DIR
    design_source = bounded.predecessor.SourceReplayAudit.model_validate(
        _load(design_dir / "source_replay_audit.json")
    )
    frozen, _ = bounded.predecessor._load_frozen_inputs(  # noqa: SLF001
        predecessor_dir=package_root / source_base.OUTPUT_DIR,
        source_replay=design_source,
    )
    population = frozen.reachability
    if (
        population.population_id != EXPECTED_OLD_REACHABILITY_POPULATION_ID
        or frozen.capability.population_id != EXPECTED_OLD_CAPABILITY_POPULATION_ID
        or population.role != "reachability"
        or population.model_api_calls != 0
        or population.empirical_rows != 0
    ):
        raise ValueError("v26.153 frozen Reachability Population changed")
    capability_population = (
        audit_predecessor.execution.preflight.FreshCapabilitySourcePopulation.model_validate(
            _load(
                package_root
                / audit_predecessor.execution.preflight.OUTPUT_DIR
                / "fresh_capability_source_population.json"
            )
        )
    )
    reachability_tasks = tuple(
        frozen.tasks[item.source_task_artifact_id] for item in population.tasks
    )
    reachability_channels = source_base._source_task_channels(reachability_tasks)  # noqa: SLF001
    capability_channels = source_base._source_task_channels(  # noqa: SLF001
        tuple(item.source_task for item in capability_population.tasks)
    )
    overlap_count = sum(
        len(reachability_channels[key] & capability_channels[key]) for key in FRESHNESS_CHANNELS
    )
    if overlap_count != 0:
        raise ValueError("v26.153 frozen Reachability sources overlap v26.150 Capability")
    ordered_bindings = tuple(sorted(population.tasks, key=lambda item: item.binding_id))
    values = {
        "source_replay_audit_id": source.audit_id,
        "source_frame_population_id": frozen.frame.population_id,
        "original_role_source_selection_audit_id": frozen.selection.audit_id,
        "bindings": ordered_bindings,
        "cross_role_source_overlap_count": overlap_count,
    }
    provisional = FrozenReachabilityInputAudit.model_construct(audit_id="pending", **values)
    audit = FrozenReachabilityInputAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_frozen_reachability_input_audit:",
        ),
        **values,
    )
    return (
        _FrozenReachabilityInputs(
            population=population,
            source_tasks={item.artifact_id: item for item in reachability_tasks},
            selection=frozen.selection,
            frame_population_id=frozen.frame.population_id,
        ),
        audit,
    )


def _load_joint_contract(package_root: Path) -> JointSupportValidityContract:
    contract = JointSupportValidityContract.model_validate(
        _load(package_root / predecessor.OUTPUT_DIR / "joint_support_validity_contract.json")
    )
    if contract.contract_id != EXPECTED_JOINT_CONTRACT_ID:
        raise ValueError("v26.153 Joint Contract changed")
    return contract


def _make_task_catalog(
    *,
    package_root: Path,
    inputs: _FrozenReachabilityInputs,
    frozen_input: FrozenReachabilityInputAudit,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
) -> TaskPackageCatalog:
    qualification, replay_contract = bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        package_root / bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    qualification_sha = _sha256(
        package_root / bounded.predecessor.VERIFIER_QUALIFICATION_DIR / "report.json"
    )
    packages: list[FreshReachabilityTaskPackage] = []
    for binding in inputs.population.tasks:
        source_task = inputs.source_tasks[binding.source_task_artifact_id]
        draft = bounded.predecessor._role_draft(  # noqa: SLF001
            source_task,
            role="reachability",
            mechanism=binding.mechanism_id,
        )
        source_record, source_environment = bounded.predecessor._upgrade_role_task(draft)  # noqa: SLF001
        environment = bounded.predecessor._verifier_bound_environment(  # noqa: SLF001
            bounded.predecessor._harden_environment(source_environment)  # noqa: SLF001
        )
        authority_record = bounded.predecessor._harden_record(  # noqa: SLF001
            source_record, environment
        )
        replay_binding = bounded.predecessor._task_replay_binding(  # noqa: SLF001
            authority_record,
            environment,
            qualification,
            qualification_sha,
            replay_contract,
        )
        record = bounded.predecessor._bind_verifier_v2(  # noqa: SLF001
            authority_record,
            replay_binding,
        )
        prompt_contract = bounded.predecessor._make_compact_prompt_contract(  # noqa: SLF001
            role="reachability",
            record=record,
            environment=environment,
        )
        values = {
            "source_population_id": inputs.population.population_id,
            "frozen_input_audit_id": frozen_input.audit_id,
            "source_binding_id": binding.binding_id,
            "source_task_artifact_id": source_task.artifact_id,
            "mechanism_id": binding.mechanism_id,
            "tier": binding.tier,
            "operational_record": record,
            "environment": environment,
            "prompt_contract": prompt_contract,
            "joint_support_validity_contract_id": joint.contract_id,
            "verifier_vnext_contract_id": joint.verifier_vnext_contract_id,
            "qualified_final_grammar_id": grammar.grammar_id,
        }
        provisional = FreshReachabilityTaskPackage.model_construct(
            task_package_id="pending", **values
        )
        packages.append(
            FreshReachabilityTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_fresh_reachability_task_package:",
                ),
                **values,
            )
        )
    values = {
        "source_population_id": inputs.population.population_id,
        "frozen_input_audit_id": frozen_input.audit_id,
        "packages": tuple(sorted(packages, key=lambda item: item.task_package_id)),
    }
    provisional = TaskPackageCatalog.model_construct(catalog_id="pending", **values)
    return TaskPackageCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_fresh_reachability_task_catalog:",
        ),
        **values,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + CHAT_ENVELOPE_TOKENS + ACCOUNTED_COMPLETION_BOUND


def _runtime_binding(
    package: FreshReachabilityTaskPackage,
    frozen_input_id: str,
    *,
    path_strategy_id: str,
    public_path_condition: str | None,
) -> runner_vnext.FreshReachabilityRuntimeBinding:
    return runner_vnext.FreshReachabilityRuntimeBinding(
        package=package,
        record=package.operational_record,
        environment=package.environment,
        prompt_contract=package.prompt_contract,
        source_selection_id=frozen_input_id,
        path_strategy_id=path_strategy_id,
        public_path_condition=public_path_condition,
    )


def _compile_path(
    *,
    package: FreshReachabilityTaskPackage,
    frozen_input_id: str,
    path_strategy_id: str,
    public_path_condition: str | None,
    materialize_registered_path: bool,
    action_grammar: SemanticActionResponseGrammar,
    old_final_grammar: ExactFinalResponseGrammar,
    qualified_grammar: QualifiedFinalResponseGrammar,
) -> _CompiledPath:
    binding = _runtime_binding(
        package,
        frozen_input_id,
        path_strategy_id=path_strategy_id,
        public_path_condition=public_path_condition,
    )
    record = package.operational_record
    environment = package.environment
    runtime = bounded.predecessor._runtime(record, environment)  # noqa: SLF001
    states: list[SemanticActionState] = []
    proposals: list[CanonicalActionProposal] = []
    commits: list[CanonicalActionCommit] = []
    observations: list[AgentToolObservation] = []
    primary_prompts: list[str] = []
    abi_prompts: list[str] = []
    semantic_prompts: list[str] = []
    support: list[MeasurementSupportDecision] = []
    candidate_counts: list[int] = []
    for logical_index in range(128):
        state = build_semantic_action_state(
            record.task_package.task.public,
            environment,
            tuple(observations),
        )
        salt = runner_vnext._presentation_salt(  # noqa: SLF001
            binding=binding,
            state=state,
            logical_index=logical_index,
        )
        prompts = {
            phase: prompt_base.render_privacy_safe_s1_action_prompt(
                phase=phase,
                instruction=record.task_package.task.public.instruction,
                state=state,
                public_path_condition=public_path_condition,
                presentation_salt=salt,
                typed_failure=(
                    None if phase == "primary" else {"family": "fixture", "subtype": "fixture"}
                ),
                grammar=action_grammar,
            )
            for phase in prompt_base.PROMPT_PHASES
        }
        primary_prompts.append(prompts["primary"])
        abi_prompts.append(prompts["abi_rescue"])
        semantic_prompts.append(prompts["semantic_recovery"])
        states.append(state)
        candidate_counts.append(len(state.action_candidates))
        proposal = s1_runner._reference_proposal_from_s1_prompt(  # noqa: SLF001
            prompts["primary"]
        )
        selected = evaluate_canonical_action_proposal(
            state,
            proposal,
            call_index=len(observations) + 1,
        )
        if selected.commit is None or selected.rejection is not None:
            raise ValueError("v26.153 reference Proposal did not Commit")
        commit = selected.commit
        proposals.append(proposal)
        commits.append(commit)
        if commit.action == "emit_final":
            support.append(
                classify_non_observation_support(
                    event_kind="final_commit",
                    state=state,
                    selected_action_id=proposal.action_id,
                )
            )
            break
        if commit.call is None:
            raise ValueError("v26.153 non-final reference Commit lacks call")
        observation = bounded.predecessor._execute_observation(  # noqa: SLF001
            record=record,
            environment=environment,
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
            record.task_package.task.public,
            environment,
            tuple(observations),
        )
        if proposal.decision_kind == "verify_terminal_operation":
            decision = classify_non_observation_support(
                event_kind="terminal_verification",
                state=state,
                state_after=after,
                selected_action_id=proposal.action_id,
            )
        else:
            decision = classify_public_observation_support(
                state_before=state,
                state_after=after,
                selected_action_id=proposal.action_id,
                observation_status=observation.status,
            )
        if decision.status == "unavailable":
            raise ValueError("v26.153 reference Path leaves Measurement Support")
        support.append(decision)
    else:
        raise ValueError("v26.153 reference Path did not close")
    compact = render_compact_final_prompt(
        package.prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=public_path_condition,
    )
    qualified_primary = runner_vnext.render_qualified_final_primary_prompt(
        compact,
        grammar=qualified_grammar,
    )
    qualified_rescue = runner_vnext.render_qualified_final_rescue_prompt(
        qualified_primary,
        failure_family="response_serialization_failure",
        failure_subtype="response_not_exact_qualified_grammar",
    )
    legacy_primary = render_exact_final_primary_prompt(compact, grammar=old_final_grammar)
    primary_requests = len(states) + 1
    static_upper = sum(_request_bound(item) for item in primary_prompts)
    static_upper += _request_bound(qualified_primary)
    static_upper += max(
        max(_request_bound(item) for item in abi_prompts),
        _request_bound(qualified_rescue),
    )
    static_upper += max(_request_bound(item) for item in semantic_prompts)
    path: FreshReachabilityPath | None = None
    if materialize_registered_path:
        if public_path_condition is None or path_strategy_id not in PATH_STRATEGIES:
            raise ValueError("v26.153 registered Path lacks an exact public condition")
        condition_id = canonical_hash(
            {
                "frozen_input_audit_id": frozen_input_id,
                "task_package_id": package.task_package_id,
                "path_strategy_id": path_strategy_id,
                "public_path_condition": public_path_condition,
            },
            prefix="finance_v26_fresh_reachability_public_condition:",
        )
        values = {
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "path_strategy_id": cast(PathStrategy, path_strategy_id),
            "public_path_condition": public_path_condition,
            "public_condition_id": condition_id,
            "reference_state_ids": tuple(item.state_id for item in states),
            "reference_proposal_ids": tuple(item.proposal_id for item in proposals),
            "reference_commit_ids": tuple(item.commit_id for item in commits),
            "reference_observation_ids": tuple(item.observation_id for item in observations),
            "measurement_support_decision_ids": tuple(item.decision_id for item in support),
            "action_state_count": len(states),
            "public_observation_count": len(observations),
            "maximum_candidate_count": max(candidate_counts),
            "maximum_action_primary_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in primary_prompts
            ),
            "maximum_action_abi_rescue_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in abi_prompts
            ),
            "maximum_semantic_recovery_prompt_utf8_bytes": max(
                len(item.encode("utf-8")) for item in semantic_prompts
            ),
            "final_primary_prompt_utf8_bytes": len(qualified_primary.encode("utf-8")),
            "final_rescue_prompt_utf8_bytes": len(qualified_rescue.encode("utf-8")),
            "primary_request_count": primary_requests,
            "maximum_provider_calls_with_recovery": primary_requests + 2,
            "maximum_transport_inclusive_invocations": primary_requests + 3,
            "static_complete_path_upper_bound_tokens": static_upper,
        }
        provisional = FreshReachabilityPath.model_construct(path_id="pending", **values)
        path = FreshReachabilityPath(
            path_id=_identity(
                provisional,
                "path_id",
                "finance_v26_fresh_reachability_path:",
            ),
            **values,
        )
    return _CompiledPath(
        package=package,
        path=path,
        path_strategy_id=path_strategy_id,
        public_path_condition=public_path_condition,
        states=tuple(states),
        proposals=tuple(proposals),
        commits=tuple(commits),
        observations=tuple(observations),
        action_prompts=tuple(primary_prompts),
        qualified_final_primary_prompt=qualified_primary,
        qualified_final_rescue_prompt=qualified_rescue,
        legacy_final_primary_prompt=legacy_primary,
    )


def _make_paths(
    *,
    tasks: TaskPackageCatalog,
    frozen_input: FrozenReachabilityInputAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
) -> tuple[PathCatalog, tuple[_CompiledPath, ...], tuple[_CompiledPath, ...]]:
    registered = tuple(
        _compile_path(
            package=package,
            frozen_input_id=frozen_input.audit_id,
            path_strategy_id=strategy,
            public_path_condition=strategy,
            materialize_registered_path=True,
            action_grammar=static.action_grammar,
            old_final_grammar=static.final_grammar,
            qualified_grammar=grammar,
        )
        for package in tasks.packages
        for strategy in PATH_STRATEGIES
    )
    unconditional = tuple(
        _compile_path(
            package=package,
            frozen_input_id=frozen_input.audit_id,
            path_strategy_id="unconditional",
            public_path_condition=None,
            materialize_registered_path=False,
            action_grammar=static.action_grammar,
            old_final_grammar=static.final_grammar,
            qualified_grammar=grammar,
        )
        for package in tasks.packages
    )
    paths = tuple(
        sorted(
            (cast(FreshReachabilityPath, item.path) for item in registered),
            key=lambda item: item.path_id,
        )
    )
    values = {
        "task_package_catalog_id": tasks.catalog_id,
        "paths": paths,
        "registered_state_count": sum(item.action_state_count for item in paths),
        "maximum_candidate_count": max(item.maximum_candidate_count for item in paths),
        "maximum_prompt_utf8_bytes": max(
            max(
                cast(FreshReachabilityPath, item.path).maximum_action_primary_prompt_utf8_bytes,
                cast(FreshReachabilityPath, item.path).maximum_action_abi_rescue_prompt_utf8_bytes,
                cast(FreshReachabilityPath, item.path).maximum_semantic_recovery_prompt_utf8_bytes,
                cast(FreshReachabilityPath, item.path).final_primary_prompt_utf8_bytes,
                cast(FreshReachabilityPath, item.path).final_rescue_prompt_utf8_bytes,
            )
            for item in registered
        ),
        "maximum_registered_path_tokens": max(
            cast(FreshReachabilityPath, item.path).static_complete_path_upper_bound_tokens
            for item in registered
        ),
    }
    provisional = PathCatalog.model_construct(catalog_id="pending", **values)
    catalog = PathCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_fresh_reachability_path_catalog:",
        ),
        **values,
    )
    by_id = {cast(FreshReachabilityPath, item.path).path_id: item for item in registered}
    ordered_registered = tuple(by_id[item.path_id] for item in catalog.paths)
    return catalog, ordered_registered, unconditional


def _support_closure(
    paths: PathCatalog, executions: Sequence[_CompiledPath]
) -> SupportClosureAudit:
    rows: list[SupportClosureEventRow] = []
    states: set[str] = set()
    for execution in executions:
        registered_path = cast(FreshReachabilityPath, execution.path)
        package = execution.package
        record = package.operational_record
        environment = package.environment
        for state_index, state in enumerate(execution.states):
            states.add(state.state_id)
            resolve_public_baseline_action_set(state)
            prefix = execution.observations[:state_index]
            for candidate in state.action_candidates:
                proposal = make_canonical_action_proposal(
                    state_id=state.state_id,
                    action_id=candidate.action_id,
                    decision_kind=candidate.decision_kind,
                )
                selected = evaluate_canonical_action_proposal(
                    state,
                    proposal,
                    call_index=state_index + 1,
                )
                if selected.commit is None or selected.rejection is not None:
                    raise ValueError("v26.153 visible Candidate failed to Commit")
                commit = selected.commit
                observation_status: str | None = None
                successor = True
                if commit.call is None:
                    decision = classify_non_observation_support(
                        event_kind=(
                            "final_commit" if commit.action == "emit_final" else "non_public_commit"
                        ),
                        state=state,
                        selected_action_id=candidate.action_id,
                    )
                else:
                    runtime = bounded.predecessor._runtime(record, environment)  # noqa: SLF001
                    replayed_prefix: list[AgentToolObservation] = []
                    for prefix_commit in execution.commits[:state_index]:
                        if prefix_commit.call is None:
                            raise ValueError("v26.153 support prefix contains a non-call Commit")
                        replayed_prefix.append(
                            bounded.predecessor._execute_observation(  # noqa: SLF001
                                record=record,
                                environment=environment,
                                runtime=runtime,
                                observations=tuple(replayed_prefix),
                                projection=CompletionProjection(
                                    request_kind="decision",
                                    action="call_tool",
                                    tool_id=prefix_commit.call.tool_id,
                                    arguments=prefix_commit.call.arguments,
                                ),
                            )
                        )
                    if tuple(replayed_prefix) != tuple(prefix):
                        raise ValueError("v26.153 support prefix replay changed")
                    observation = bounded.predecessor._execute_observation(  # noqa: SLF001
                        record=record,
                        environment=environment,
                        runtime=runtime,
                        observations=tuple(replayed_prefix),
                        projection=CompletionProjection(
                            request_kind="decision",
                            action="call_tool",
                            tool_id=commit.call.tool_id,
                            arguments=commit.call.arguments,
                        ),
                    )
                    observation_status = observation.status
                    try:
                        after = build_semantic_action_state(
                            record.task_package.task.public,
                            environment,
                            (*prefix, observation),
                        )
                    except ValueError as exc:
                        if str(exc) != "semantic action state has no selectable public action":
                            raise
                        after = None
                        successor = False
                    if after is None:
                        decision = runner_vnext._unavailable_support(  # noqa: SLF001
                            before=state,
                            selected_action_id=candidate.action_id,
                            observation_status=cast(Any, observation.status),
                        )
                    elif candidate.decision_kind == "verify_terminal_operation":
                        decision = classify_non_observation_support(
                            event_kind="terminal_verification",
                            state=state,
                            state_after=after,
                            selected_action_id=candidate.action_id,
                        )
                    else:
                        decision = classify_public_observation_support(
                            state_before=state,
                            state_after=after,
                            selected_action_id=candidate.action_id,
                            observation_status=observation.status,
                        )
                values = {
                    "path_id": registered_path.path_id,
                    "state_id": state.state_id,
                    "selected_action_id": candidate.action_id,
                    "observation_status": observation_status,
                    "successor_available": successor,
                    "decision": decision,
                }
                provisional = SupportClosureEventRow.model_construct(row_id="pending", **values)
                rows.append(
                    SupportClosureEventRow(
                        row_id=_identity(
                            provisional,
                            "row_id",
                            "finance_v26_fresh_reachability_support_event:",
                        ),
                        **values,
                    )
                )
            reference = execution.proposals[state_index]
            wrong_kind = next(
                item
                for item in (
                    "acquire_public_input",
                    "execute_public_operation",
                    "verify_terminal_operation",
                    "emit_final_answer",
                )
                if item != reference.decision_kind
            )
            rejection = evaluate_canonical_action_proposal(
                state,
                make_canonical_action_proposal(
                    state_id=state.state_id,
                    action_id=reference.action_id,
                    decision_kind=cast(Any, wrong_kind),
                ),
                call_index=state_index + 1,
            ).rejection
            if rejection is None:
                raise ValueError("v26.153 semantic recovery fixture did not reject")
            recovery_state = build_semantic_action_state(
                record.task_package.task.public,
                environment,
                tuple(execution.observations[:state_index]),
                semantic_rejections=(rejection,),
            )
            states.add(recovery_state.state_id)
            resolve_public_baseline_action_set(recovery_state)
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    failed = tuple(item for item in ordered if item.observation_status == "failed")
    progress = tuple(
        item
        for item in ordered
        if item.observation_status == "succeeded" and item.decision.reason_code == "public_progress"
    )
    no_progress = tuple(
        item
        for item in ordered
        if item.observation_status == "succeeded" and item.decision.baseline_classifier_invoked
    )
    support_values: dict[str, Any] = {
        "path_catalog_id": paths.catalog_id,
        "unique_state_count": len(states),
        "candidate_event_count": len(ordered),
        "typed_decision_count": len(ordered),
        "failed_observation_event_count": len(failed),
        "failed_observation_baseline_call_count": sum(
            item.decision.baseline_classifier_invoked for item in failed
        ),
        "progress_observation_baseline_call_count": sum(
            item.decision.baseline_classifier_invoked for item in progress
        ),
        "successful_no_progress_event_count": len(no_progress),
        "successful_no_progress_baseline_call_count": sum(
            item.decision.baseline_classifier_invoked for item in no_progress
        ),
        "ordinary_detour_event_count": sum(
            item.decision.ordinary_detour_observed for item in ordered
        ),
        "typed_support_exit_count": sum(item.decision.status == "unavailable" for item in ordered),
        "event_rows": ordered,
    }
    provisional = SupportClosureAudit.model_construct(audit_id="pending", **support_values)
    return SupportClosureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_support_closure:",
        ),
        **support_values,
    )


def _detour_prompt_bundle(
    *,
    binding: runner_vnext.FreshReachabilityRuntimeBinding,
    state: SemanticActionState,
    logical_index: int,
    static: Any,
) -> dict[str, str]:
    salt = runner_vnext._presentation_salt(  # noqa: SLF001
        binding=binding,
        state=state,
        logical_index=logical_index,
    )
    return {
        phase: prompt_base.render_privacy_safe_s1_action_prompt(
            phase=phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=binding.public_path_condition,
            presentation_salt=salt,
            typed_failure=(
                None if phase == "primary" else {"family": "fixture", "subtype": "fixture"}
            ),
            grammar=static.action_grammar,
        )
        for phase in prompt_base.PROMPT_PHASES
    }


def _qualify_detour_row(
    *,
    support_row: SupportClosureEventRow,
    execution: _CompiledPath,
    frozen_input: FrozenReachabilityInputAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
) -> ReachabilityDetourQualificationRow | None:
    path = cast(FreshReachabilityPath, execution.path)
    index = next(
        (i for i, item in enumerate(execution.states) if item.state_id == support_row.state_id), -1
    )
    if index < 0:
        raise ValueError("v26.153 Detour row state changed")
    binding = _runtime_binding(
        execution.package,
        frozen_input.audit_id,
        path_strategy_id=execution.path_strategy_id,
        public_path_condition=execution.public_path_condition,
    )
    record = execution.package.operational_record
    environment = execution.package.environment
    runtime = bounded.predecessor._runtime(record, environment)  # noqa: SLF001
    observations = list(execution.observations[:index])
    prompt_bundles = [
        _detour_prompt_bundle(
            binding=binding,
            state=state,
            logical_index=logical_index,
            static=static,
        )
        for logical_index, state in enumerate(execution.states[: index + 1])
    ]
    state = execution.states[index]
    candidate = next(
        (
            item
            for item in state.action_candidates
            if item.action_id == support_row.selected_action_id
        ),
        None,
    )
    if candidate is None:
        raise ValueError("v26.153 frozen Detour action is not visible")
    proposal = make_canonical_action_proposal(
        state_id=state.state_id,
        action_id=candidate.action_id,
        decision_kind=candidate.decision_kind,
    )
    selected = evaluate_canonical_action_proposal(
        state,
        proposal,
        call_index=len(observations) + 1,
    )
    if selected.commit is None or selected.commit.call is None or selected.rejection is not None:
        raise ValueError("v26.153 frozen Detour action did not Commit")
    observation = bounded.predecessor._execute_observation(  # noqa: SLF001
        record=record,
        environment=environment,
        runtime=runtime,
        observations=tuple(observations),
        projection=CompletionProjection(
            request_kind="decision",
            action="call_tool",
            tool_id=selected.commit.call.tool_id,
            arguments=selected.commit.call.arguments,
        ),
    )
    observations.append(observation)
    try:
        after = build_semantic_action_state(
            record.task_package.task.public,
            environment,
            tuple(observations),
        )
    except ValueError as exc:
        if str(exc) == "semantic action state has no selectable public action":
            return None
        raise
    support = classify_public_observation_support(
        state_before=state,
        state_after=after,
        selected_action_id=proposal.action_id,
        observation_status=observation.status,
    )
    if (
        observation.status != "succeeded"
        or not support.ordinary_detour_observed
        or support.decision_id != support_row.decision.decision_id
    ):
        raise ValueError("v26.153 frozen Detour no longer qualifies")
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    for logical_index in range(index + 1, MAXIMUM_PRIMARY_REQUESTS):
        try:
            state = build_semantic_action_state(
                record.task_package.task.public,
                environment,
                tuple(observations),
            )
        except ValueError as exc:
            if str(exc) == "semantic action state has no selectable public action":
                return None
            raise
        prompts = _detour_prompt_bundle(
            binding=binding,
            state=state,
            logical_index=logical_index,
            static=static,
        )
        prompt_bundles.append(prompts)
        try:
            reference = s1_runner._reference_proposal_from_s1_prompt(  # noqa: SLF001
                prompts["primary"]
            )
        except ValueError as exc:
            if str(exc) in {
                "Prompt-only policy has no acquisition candidate",
                "Prompt-only acquisition policy cannot satisfy its public route",
                "Prompt-only policy has no canonical next action",
            }:
                return None
            raise
        selected = evaluate_canonical_action_proposal(
            state,
            reference,
            call_index=len(observations) + 1,
        )
        if selected.commit is None or selected.rejection is not None:
            return None
        if selected.commit.action == "emit_final":
            final_state = state
            final_commit = selected.commit
            break
        if selected.commit.call is None:
            raise ValueError("v26.153 ordinary replan lacks a public call")
        observations.append(
            bounded.predecessor._execute_observation(  # noqa: SLF001
                record=record,
                environment=environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=selected.commit.call.tool_id,
                    arguments=selected.commit.call.arguments,
                ),
            )
        )
    if final_state is None or final_commit is None:
        return None
    compact = render_compact_final_prompt(
        execution.package.prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=execution.public_path_condition,
    )
    final_primary = runner_vnext.render_qualified_final_primary_prompt(
        compact,
        grammar=grammar,
    )
    final_rescue = runner_vnext.render_qualified_final_rescue_prompt(
        final_primary,
        failure_family="response_serialization_failure",
        failure_subtype="response_not_exact_qualified_grammar",
    )
    primary_prompts = [item["primary"] for item in prompt_bundles]
    abi_prompts = [item["abi_rescue"] for item in prompt_bundles]
    semantic_prompts = [item["semantic_recovery"] for item in prompt_bundles]
    static_tokens = sum(_request_bound(item) for item in primary_prompts)
    static_tokens += _request_bound(final_primary)
    static_tokens += max(
        max(_request_bound(item) for item in abi_prompts),
        _request_bound(final_rescue),
    )
    static_tokens += max(_request_bound(item) for item in semantic_prompts)
    primary_requests = len(primary_prompts) + 1
    maximum_prompt = max(
        *(len(item.encode("utf-8")) for item in primary_prompts),
        *(len(item.encode("utf-8")) for item in abi_prompts),
        *(len(item.encode("utf-8")) for item in semantic_prompts),
        len(final_primary.encode("utf-8")),
        len(final_rescue.encode("utf-8")),
    )
    values = {
        "support_closure_row_id": support_row.row_id,
        "path_id": path.path_id,
        "source_task_artifact_id": path.source_task_artifact_id,
        "path_strategy_id": path.path_strategy_id,
        "state_id": support_row.state_id,
        "selected_action_id": support_row.selected_action_id,
        "primary_request_count": primary_requests,
        "provider_call_count_with_recoveries": primary_requests + 2,
        "transport_inclusive_invocation_count": primary_requests + 3,
        "maximum_prompt_utf8_bytes": maximum_prompt,
        "static_complete_path_upper_bound_tokens": static_tokens,
        "selected_rollout_headroom_tokens": ROLLOUT_BOUND_TOKENS - static_tokens,
    }
    provisional = ReachabilityDetourQualificationRow.model_construct(row_id="pending", **values)
    return ReachabilityDetourQualificationRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_fresh_reachability_detour_qualification:",
        ),
        **values,
    )


def _make_detour_audit(
    *,
    package_root: Path,
    paths: PathCatalog,
    executions: Sequence[_CompiledPath],
    frozen_input: FrozenReachabilityInputAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
    support: SupportClosureAudit,
) -> ReachabilityDetourQualificationAudit:
    old_dir = package_root / bounded.OUTPUT_DIR
    old_audit = bounded.DynamicTrajectoryEnvelopeAudit.model_validate(
        _load(old_dir / "dynamic_trajectory_envelope_audit.json")
    )
    if old_audit.audit_id != EXPECTED_V132_DYNAMIC_ENVELOPE_ID:
        raise ValueError("v26.153 predecessor dynamic envelope changed")
    current = {cast(FreshReachabilityPath, item.path).path_id: item for item in executions}
    candidates = tuple(
        item for item in support.event_rows if item.decision.ordinary_detour_observed
    )
    if len(candidates) != support.ordinary_detour_event_count:
        raise ValueError("v26.153 current Detour denominator changed")
    qualified: list[ReachabilityDetourQualificationRow] = []
    ordinary_replan_not_closed_count = 0
    for item in candidates:
        execution = current.get(item.path_id)
        if execution is None:
            raise ValueError("v26.153 current Detour Path changed")
        row = _qualify_detour_row(
            support_row=item,
            execution=execution,
            frozen_input=frozen_input,
            static=static,
            grammar=grammar,
        )
        if row is None:
            ordinary_replan_not_closed_count += 1
        else:
            qualified.append(row)
    rows = tuple(sorted(qualified, key=lambda item: item.row_id))
    if not rows:
        raise ValueError("v26.153 has no closed current Reachability Detour")
    values = {
        "predecessor_dynamic_envelope_audit_id": old_audit.audit_id,
        "support_closure_audit_id": support.audit_id,
        "path_catalog_id": paths.catalog_id,
        "rows": rows,
        "candidate_detour_count": len(candidates),
        "qualified_closed_row_count": len(rows),
        "ordinary_replan_not_closed_count": ordinary_replan_not_closed_count,
        "distinct_path_count": len({item.path_id for item in rows}),
        "maximum_primary_requests": max(item.primary_request_count for item in rows),
        "maximum_provider_calls": max(item.provider_call_count_with_recoveries for item in rows),
        "maximum_transport_invocations": max(
            item.transport_inclusive_invocation_count for item in rows
        ),
        "maximum_prompt_utf8_bytes": max(item.maximum_prompt_utf8_bytes for item in rows),
        "maximum_static_tokens": max(item.static_complete_path_upper_bound_tokens for item in rows),
        "minimum_rollout_headroom_tokens": min(
            item.selected_rollout_headroom_tokens for item in rows
        ),
    }
    provisional = ReachabilityDetourQualificationAudit.model_construct(audit_id="pending", **values)
    return ReachabilityDetourQualificationAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_detour_audit:",
        ),
        **values,
    )


def _make_resource(
    paths: PathCatalog,
    support: SupportClosureAudit,
    detours: ReachabilityDetourQualificationAudit,
) -> ResourceContract:
    max_path = paths.maximum_registered_path_tokens
    conservative_detour = detours.maximum_static_tokens
    values = {
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
        "detour_qualification_audit_id": detours.audit_id,
        "qualified_maximum_action_abi_rescue_prompt_utf8_bytes": max(
            item.maximum_action_abi_rescue_prompt_utf8_bytes for item in paths.paths
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": max(
            item.maximum_semantic_recovery_prompt_utf8_bytes for item in paths.paths
        ),
        "qualified_maximum_final_primary_prompt_utf8_bytes": max(
            item.final_primary_prompt_utf8_bytes for item in paths.paths
        ),
        "qualified_maximum_final_rescue_prompt_utf8_bytes": max(
            item.final_rescue_prompt_utf8_bytes for item in paths.paths
        ),
        "measured_maximum_reference_prompt_utf8_bytes": paths.maximum_prompt_utf8_bytes,
        "measured_maximum_reference_path_tokens": max_path,
        "conservative_one_detour_upper_bound_tokens": conservative_detour,
        "selected_rollout_headroom_tokens": ROLLOUT_BOUND_TOKENS - conservative_detour,
    }
    provisional = ResourceContract.model_construct(contract_id="pending", **values)
    return ResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_resource_contract:",
        ),
        **values,
    )


def _make_execution_contract(
    *,
    frozen_input: FrozenReachabilityInputAudit,
    tasks: TaskPackageCatalog,
    paths: PathCatalog,
    resource: ResourceContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
) -> ExecutionContract:
    values = {
        "frozen_input_audit_id": frozen_input.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "resource_contract_id": resource.contract_id,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "joint_support_validity_contract_id": joint.contract_id,
        "qualified_final_grammar_id": grammar.grammar_id,
    }
    provisional = ExecutionContract.model_construct(contract_id="pending", **values)
    return ExecutionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_execution_contract:",
        ),
        **values,
    )


def _frozen_reachability_schedule(
    package_root: Path,
) -> tuple[tuple[dict[str, Any], ...], set[str]]:
    old_dir = package_root / bounded.OUTPUT_DIR
    task_catalog = bounded.RoleTaskPackageCatalog.model_validate(
        _load(old_dir / "role_task_package_catalog.json")
    )
    path_catalog = bounded.RolePathCatalog.model_validate(_load(old_dir / "role_path_catalog.json"))
    chain = bounded.RoleIdentityChain.model_validate(_load(old_dir / "role_identity_chain.json"))
    old_tasks = {
        item.task_package_id: item for item in task_catalog.packages if item.role == "reachability"
    }
    old_paths = {item.path_id: item for item in path_catalog.paths if item.role == "reachability"}
    rows: list[dict[str, Any]] = []
    for old in chain.reachability_manifest.jobs:
        old_task = old_tasks[old.task_package_id]
        strategy = None
        if old.requested_path_id is not None:
            strategy = old_paths[old.requested_path_id].path_strategy_id
        rows.append(
            {
                "old_job_id": old.job_id,
                "source_task_artifact_id": old_task.source_task_artifact_id,
                "sampling_mode": old.sampling_mode,
                "replicate_index": old.replicate_index,
                "seed": old.seed,
                "requested_path_strategy": strategy,
            }
        )
    ordered = tuple(
        sorted(
            rows,
            key=lambda item: (
                item["source_task_artifact_id"],
                item["sampling_mode"],
                item["requested_path_strategy"] or "",
                item["replicate_index"],
            ),
        )
    )
    if len(ordered) != JOB_COUNT or len({item["seed"] for item in ordered}) != JOB_COUNT:
        raise ValueError("v26.153 frozen Reachability seed schedule changed")
    return ordered, {cast(str, item["old_job_id"]) for item in ordered}


def _make_manifest(
    *,
    package_root: Path,
    frozen_input: FrozenReachabilityInputAudit,
    tasks: TaskPackageCatalog,
    paths: PathCatalog,
    resource: ResourceContract,
    contract: ExecutionContract,
) -> ReachabilityManifest:
    package_by_source = {item.source_task_artifact_id: item for item in tasks.packages}
    path_by_source_strategy = {
        (item.source_task_artifact_id, item.path_strategy_id): item for item in paths.paths
    }
    schedule, old_job_ids = _frozen_reachability_schedule(package_root)
    jobs: list[FreshReachabilityJob] = []
    for row in schedule:
        source_id = cast(str, row["source_task_artifact_id"])
        package = package_by_source[source_id]
        strategy = cast(PathStrategy | None, row["requested_path_strategy"])
        path = None if strategy is None else path_by_source_strategy[(source_id, strategy)]
        values = {
            "contract_id": contract.contract_id,
            "resource_contract_id": resource.contract_id,
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": source_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "sampling_mode": row["sampling_mode"],
            "replicate_index": row["replicate_index"],
            "seed": row["seed"],
            "requested_path_id": None if path is None else path.path_id,
            "requested_path_strategy": strategy,
            "public_path_condition": None if path is None else path.public_path_condition,
            "public_condition_id": None if path is None else path.public_condition_id,
            "exact_final_response_grammar_id": contract.qualified_final_grammar_id,
            "candidate_presentation_parent_id": frozen_input.audit_id,
        }
        provisional = FreshReachabilityJob.model_construct(job_id="pending", **values)
        jobs.append(
            FreshReachabilityJob(
                job_id=_identity(
                    provisional,
                    "job_id",
                    "finance_v26_fresh_reachability_job:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    if old_job_ids & {item.job_id for item in ordered}:
        raise ValueError("v26.153 Job identity overlaps v26.132")
    values = {
        "contract_id": contract.contract_id,
        "frozen_input_audit_id": frozen_input.audit_id,
        "resource_contract_id": resource.contract_id,
        "jobs": ordered,
    }
    provisional = ReachabilityManifest.model_construct(manifest_id="pending", **values)
    return ReachabilityManifest(
        manifest_id=_identity(
            provisional,
            "manifest_id",
            "finance_v26_fresh_reachability_manifest:",
        ),
        **values,
    )


def _make_outcome(contract: ExecutionContract, manifest: ReachabilityManifest) -> OutcomeContract:
    values = {"execution_contract_id": contract.contract_id, "manifest_id": manifest.manifest_id}
    provisional = OutcomeContract.model_construct(contract_id="pending", **values)
    return OutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_outcome_contract:",
        ),
        **values,
    )


def _make_runner(
    *,
    contract: ExecutionContract,
    manifest: ReachabilityManifest,
    outcome: OutcomeContract,
    resource: ResourceContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
) -> RunnerContract:
    values = {
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "resource_contract_id": resource.contract_id,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "joint_support_validity_contract_id": joint.contract_id,
        "qualified_final_grammar_id": grammar.grammar_id,
    }
    provisional = RunnerContract.model_construct(contract_id="pending", **values)
    return RunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_runner_contract:",
        ),
        **values,
    )


def _reference_final_answer(
    execution: _CompiledPath,
    *,
    old_grammar: ExactFinalResponseGrammar,
) -> Mapping[str, Any]:
    envelope = make_final_response_host_envelope(
        terminal_state_id=execution.states[-1].state_id,
        terminal_commit_id=execution.commits[-1].commit_id,
        grammar=old_grammar,
    )
    payload = parse_prompt_only_reference_final_payload(
        execution.legacy_final_primary_prompt,
        envelope=envelope,
    )
    return runner_vnext.qualified_reference_final_answer(
        legacy_answer=cast(Mapping[str, Any], payload.answer),
        observations=execution.observations,
    )


def _base_checks() -> BaseValidityChecks:
    return BaseValidityChecks.model_validate(
        {item: True for item in predecessor.predecessor.BASE_CHECK_IDS}
    )


def _make_fixture(
    *,
    tasks: TaskPackageCatalog,
    registered_paths: Sequence[_CompiledPath],
    unconditional_paths: Sequence[_CompiledPath],
    manifest: ReachabilityManifest,
    resource: ResourceContract,
    runner: RunnerContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
) -> RunnerFixtureAudit:
    task_by_id = {item.task_package_id: item for item in tasks.packages}
    path_by_id = {cast(FreshReachabilityPath, item.path).path_id: item for item in registered_paths}
    unconditional_by_task = {item.package.task_package_id: item for item in unconditional_paths}
    raws: list[runner_vnext.FreshReachabilityRawExecution] = []
    qualified_count = 0
    with tempfile.TemporaryDirectory(prefix="v26_153_fixture_") as temporary:
        root = Path(temporary)
        for job in manifest.jobs:
            package = task_by_id[job.task_package_id]
            execution = (
                unconditional_by_task[job.task_package_id]
                if job.requested_path_id is None
                else path_by_id[job.requested_path_id]
            )
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=_reference_final_answer(
                    execution,
                    old_grammar=static.final_grammar,
                ),
            )
            binding = _runtime_binding(
                package,
                package.frozen_input_audit_id,
                path_strategy_id=execution.path_strategy_id,
                public_path_condition=execution.public_path_condition,
            )
            raw = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=client,
                output_dir=root,
            )
            if raw.terminal_disposition != "completed_model_endpoint":
                raise ValueError(
                    f"v26.153 scripted Job failed: {job.job_id} {raw.terminal_disposition} "
                    f"{raw.terminal_failure_type} {raw.execution_error}"
                )
            if (
                tuple(item.state_id for item in raw.semantic_choices)
                != tuple(item.state_id for item in execution.states)
                or tuple(item.commit.commit_id for item in raw.commits)
                != tuple(item.commit_id for item in execution.commits)
                or tuple(item.observation_id for item in raw.observations)
                != tuple(item.observation_id for item in execution.observations)
            ):
                raise ValueError(f"v26.153 scripted Job drifted from its condition: {job.job_id}")
            recovered = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=None,
                output_dir=root,
            )
            if recovered != raw:
                raise ValueError(f"v26.153 Raw recovery changed: {job.job_id}")
            noninterference = make_noninterference_artifact_binding(
                noninterference_contract_id="v26.153-task-noninterference-contract",
                noninterference_audit_id=f"v26.153-task-audit:{package.task_package_id}",
                task_package_id=package.task_package_id,
            )
            result = evaluate_joint_support_validity(
                contract=joint,
                support_decision=raw.measurement_support_decisions[-1],
                trajectory_id=raw.artifact_id,
                task_package_id=package.task_package_id,
                model_endpoint_observed=True,
                instrument_integrity=True,
                privacy_compliant=True,
                mechanism_id=package.mechanism_id,
                base_checks=_base_checks(),
                noninterference_binding=noninterference,
                observed_mechanism_event_ids=joint.required_event_ids_by_mechanism[
                    package.mechanism_id
                ],
            )
            if not result.qualified_report.valid or result.task_verifier_invocation_count != 1:
                raise ValueError("v26.153 joint scripted validity failed")
            qualified_count += 1
            raws.append(raw)
    action_attempts = tuple(
        item for raw in raws for item in raw.attempts if item.request_kind == "semantic_proposal"
    )
    values = {
        "runner_contract_id": runner.contract_id,
        "manifest_id": manifest.manifest_id,
        "completed_job_count": sum(
            item.terminal_disposition == "completed_model_endpoint" for item in raws
        ),
        "first_action_interface_qualified_count": sum(
            item.first_action_interface_qualified for item in raws
        ),
        "qualified_final_payload_count": sum(
            item.exact_qualified_final_payload_count for item in raws
        ),
        "joint_task_verifier_invocation_count": len(raws),
        "joint_qualified_valid_count": qualified_count,
        "unconditional_job_count": sum(
            item.sampling_mode == "reachability_unconditional" for item in manifest.jobs
        ),
        "conditioned_job_count": sum(
            item.sampling_mode == "reachability_conditioned" for item in manifest.jobs
        ),
        "covered_mechanism_tier_cell_count": len(
            {(item.mechanism_id, item.tier) for item in manifest.jobs}
        ),
        "covered_conditioned_path_count": len(
            {item.requested_path_id for item in manifest.jobs if item.requested_path_id is not None}
        ),
        "scripted_local_calls": sum(item.stage_one_provider_call_count for item in raws),
        "action_payload_count": sum(item.exact_four_field_action_payload_count for item in raws),
        "public_observation_count": sum(len(item.observations) for item in raws),
        "support_decision_count": sum(len(item.measurement_support_decisions) for item in raws),
        "raw_recovery_pass_count": len(raws),
        "sensitive_prompt_key_count": 0,
        "fixture_hash": hashlib.sha256(
            _canonical_bytes([item.model_dump(mode="json") for item in raws])
        ).hexdigest(),
    }
    if len(action_attempts) != values["action_payload_count"]:
        raise ValueError("v26.153 Action attempt count changed")
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_runner_fixture:",
        ),
        **values,
    )


def _control(name: str, metrics: Mapping[str, Any]) -> ControlRow:
    values = {"name": name, "metrics": dict(metrics)}
    provisional = ControlRow.model_construct(row_id="pending", **values)
    return ControlRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_fresh_reachability_control:",
        ),
        **values,
    )


class _FinalShapeMutationClient(s1_runner.ScriptedS1QualificationClient):
    def __init__(
        self,
        config: Any,
        *,
        final_answer: Mapping[str, Any],
        mutation: Literal["missing_citations", "flat_answer_alias"],
    ) -> None:
        super().__init__(config, final_answer=final_answer)
        self._final_mutation = mutation

    def complete_json_certified(
        self,
        prompt: str,
        certificate: Any,
    ) -> tuple[dict[str, Any], Any]:
        payload, telemetry = super().complete_json_certified(prompt, certificate)
        if certificate.request_kind != "final_answer":
            return payload, telemetry
        answer = payload.get("answer")
        if not isinstance(answer, dict):
            raise ValueError("v26.153 scripted Final answer shape changed")
        if self._final_mutation == "missing_citations":
            answer.pop("citations", None)
        else:
            result: Any = answer.get("result")
            while isinstance(result, dict) and set(result) == {"result", "citations"}:
                result = result.get("result")
            payload["answer"] = result
        return payload, telemetry


def _make_controls(
    *,
    tasks: TaskPackageCatalog,
    registered_paths: Sequence[_CompiledPath],
    unconditional_paths: Sequence[_CompiledPath],
    manifest: ReachabilityManifest,
    resource: ResourceContract,
    runner: RunnerContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
    support: SupportClosureAudit,
    fixture: RunnerFixtureAudit,
) -> RunnerControlAudit:
    task_by_id = {item.task_package_id: item for item in tasks.packages}
    path_by_id = {cast(FreshReachabilityPath, item.path).path_id: item for item in registered_paths}
    unconditional_by_task = {item.package.task_package_id: item for item in unconditional_paths}
    job = next(item for item in manifest.jobs if item.requested_path_id is not None)
    package = task_by_id[job.task_package_id]
    execution = path_by_id[cast(str, job.requested_path_id)]
    binding = _runtime_binding(
        package,
        package.frozen_input_audit_id,
        path_strategy_id=execution.path_strategy_id,
        public_path_condition=execution.public_path_condition,
    )
    final_answer = _reference_final_answer(execution, old_grammar=static.final_grammar)
    rows: list[ControlRow] = [
        _control("exact_360_job_fixture", {"completed": fixture.completed_job_count}),
        _control("frozen_source_population", {"tasks": 12, "reselected": 0}),
        _control("registered_reachability_paths", {"paths": len(registered_paths)}),
        _control("unconditional_runtime_controls", {"paths": len(unconditional_paths)}),
        _control("unconditional_job_denominator", {"jobs": manifest.unconditional_job_count}),
        _control("conditioned_job_denominator", {"jobs": manifest.conditioned_job_count}),
        _control("qualified_final_grammar_bound", {"grammar_id": grammar.grammar_id}),
        _control("measurement_support_closure", {"events": support.candidate_event_count}),
        _control("failed_observation_skips_baseline", {"calls": 0}),
        _control("progress_observation_skips_baseline", {"calls": 0}),
        _control(
            "no_progress_invokes_baseline",
            {"calls": support.successful_no_progress_baseline_call_count},
        ),
        _control("exact_model_thinking_profile", {"thinking_type": "enabled"}),
        _control(
            "resource_maximum_prompt",
            {"bytes": resource.measured_maximum_reference_prompt_utf8_bytes},
        ),
        _control(
            "resource_reference_path", {"tokens": resource.measured_maximum_reference_path_tokens}
        ),
        _control(
            "resource_one_detour", {"tokens": resource.conservative_one_detour_upper_bound_tokens}
        ),
        _control("condition_bound_before_provider", {"condition": job.public_path_condition}),
        _control("stage_two_zero_provider", {"calls": 0}),
        _control(
            "joint_validity_once_per_fixture",
            {"calls": fixture.joint_task_verifier_invocation_count},
        ),
        _control("state_mapping_zero", {"rows": fixture.state_mapping_rows}),
        _control("static_route_not_empirical_state", {"substitution_rows": 0}),
    ]
    scenarios: tuple[tuple[str, dict[str, Any]], ...] = (
        ("action_abi_rescue", {"malformed_action_once": True}),
        ("semantic_recovery", {"semantic_rejection_once": True}),
        ("transport_replacement", {"transport_failure_once": True}),
        ("privacy_rejection", {"privacy_failure_once": True}),
        ("usage_16384", {"completion_tokens": 16_384}),
        ("usage_16385", {"completion_tokens": 16_385}),
        ("usage_16386_rejected", {"completion_tokens": 16_386}),
        ("wrong_final_answer", {"wrong_final_answer": True}),
    )
    with tempfile.TemporaryDirectory(prefix="v26_153_controls_") as temporary:
        root = Path(temporary)
        for name, kwargs in scenarios:
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=final_answer,
                **kwargs,
            )
            raw = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=client,
                output_dir=root / name,
            )
            expected = {
                "privacy_rejection": "privacy_rejection",
                "usage_16386_rejected": "instrument_failure",
                "wrong_final_answer": "model_result_failure",
            }.get(name, "completed_model_endpoint")
            if raw.terminal_disposition != expected:
                raise ValueError(f"v26.153 Runner control failed: {name}")
            rows.append(
                _control(
                    name,
                    {
                        "terminal": raw.terminal_disposition,
                        "abi_rescues": raw.abi_rescue_attempt_count,
                        "semantic_recoveries": raw.semantic_recovery_attempt_count,
                        "transport_replacements": raw.transport_replacement_attempt_count,
                    },
                )
            )
        for mutation in ("missing_citations", "flat_answer_alias"):
            client = _FinalShapeMutationClient(
                static.agent_model_config,
                final_answer=final_answer,
                mutation=mutation,
            )
            raw = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=client,
                output_dir=root / mutation,
            )
            if (
                raw.terminal_disposition != "model_result_failure"
                or raw.completed_result is not None
            ):
                raise ValueError(f"v26.153 Final-shape control failed: {mutation}")
            rows.append(
                _control(mutation, {"terminal": raw.terminal_disposition, "host_repair": 0})
            )
        unconditional_job = next(
            item for item in manifest.jobs if item.sampling_mode == "reachability_unconditional"
        )
        unconditional_package = task_by_id[unconditional_job.task_package_id]
        unconditional_execution = unconditional_by_task[unconditional_job.task_package_id]
        unconditional_binding = _runtime_binding(
            unconditional_package,
            unconditional_package.frozen_input_audit_id,
            path_strategy_id="unconditional",
            public_path_condition=None,
        )
        unconditional_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=_reference_final_answer(
                unconditional_execution,
                old_grammar=static.final_grammar,
            ),
        )
        unconditional_raw = runner_vnext.execute_fresh_reachability_job_raw(
            job=unconditional_job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=unconditional_binding,
            client=unconditional_client,
            output_dir=root / "unconditional_no_condition",
        )
        if unconditional_raw.terminal_disposition != "completed_model_endpoint":
            raise ValueError("v26.153 unconditional control failed")
        rows.append(_control("unconditional_no_condition", {"condition": None}))
        orphan_root = root / "orphan_blocking"
        orphan_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        runner_vnext.execute_fresh_reachability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=binding,
            client=orphan_client,
            output_dir=orphan_root,
        )
        raw_files = tuple((orphan_root / "raw_execution").glob("*.json"))
        if len(raw_files) != 1:
            raise ValueError("v26.153 orphan setup changed")
        raw_files[0].unlink()
        retry_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        try:
            runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=retry_client,
                output_dir=orphan_root,
            )
        except ValueError:
            pass
        else:
            raise ValueError("v26.153 orphan retry was not blocked")
        if retry_client.local_invocation_count:
            raise ValueError("v26.153 orphan retry made a later call")
        rows.append(_control("provider_artifact_orphan_blocking", {"later_calls": 0}))
        raw_root = root / "raw_recovery"
        raw_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        first = runner_vnext.execute_fresh_reachability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=binding,
            client=raw_client,
            output_dir=raw_root,
        )
        recovered = runner_vnext.execute_fresh_reachability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=binding,
            client=None,
            output_dir=raw_root,
        )
        if first != recovered:
            raise ValueError("v26.153 Raw-only recovery control failed")
        rows.append(_control("raw_only_recovery", {"provider_calls": 0}))
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    values = {
        "runner_contract_id": runner.contract_id,
        "rows": ordered,
        "control_count": len(ordered),
        "passed_count": len(ordered),
    }
    provisional = RunnerControlAudit.model_construct(audit_id="pending", **values)
    return RunnerControlAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_runner_controls:",
        ),
        **values,
    )


def _reject(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except (ValueError, ValidationError) as exc:
        return MutationResult(mutation_name=name, failure_type=type(exc).__name__)
    raise ValueError(f"v26.153 destructive mutation passed: {name}")


def _revalidate_with(value: BaseModel, **updates: Any) -> BaseModel:
    payload = value.model_dump(mode="json")
    payload.update(updates)
    return type(value).model_validate(payload)


def _make_destructive(
    *,
    frozen_input: FrozenReachabilityInputAudit,
    tasks: TaskPackageCatalog,
    paths: PathCatalog,
    manifest: ReachabilityManifest,
    resource: ResourceContract,
    runner: RunnerContract,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    package = tasks.packages[0]
    path = paths.paths[0]
    unconditional = next(
        item for item in manifest.jobs if item.sampling_mode == "reachability_unconditional"
    )
    conditioned = next(
        item for item in manifest.jobs if item.sampling_mode == "reachability_conditioned"
    )
    mutations: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "frozen_population_changed",
            lambda: _revalidate_with(frozen_input, frozen_population_id="changed"),
        ),
        (
            "capability_outcome_selected_source",
            lambda: _revalidate_with(frozen_input, capability_outcomes_used_for_selection=True),
        ),
        (
            "verifier_selected_source",
            lambda: _revalidate_with(frozen_input, verifier_passability_used_for_selection=True),
        ),
        (
            "resource_selected_source",
            lambda: _revalidate_with(frozen_input, resource_values_used_for_selection=True),
        ),
        (
            "source_reselection",
            lambda: _revalidate_with(frozen_input, fresh_source_reselection_count=1),
        ),
        (
            "source_overlap",
            lambda: _revalidate_with(frozen_input, cross_role_source_overlap_count=1),
        ),
        ("task_role_changed", lambda: _revalidate_with(package, role="capability")),
        (
            "task_mechanism_changed",
            lambda: _revalidate_with(package, mechanism_id="failure_recovery"),
        ),
        ("task_tier_changed", lambda: _revalidate_with(package, tier="hard_control")),
        (
            "task_identity_reused",
            lambda: _revalidate_with(
                package, task_package_id=package.operational_record.task_package.package_id
            ),
        ),
        ("task_deleted", lambda: _revalidate_with(tasks, packages=tasks.packages[1:])),
        ("path_condition_changed", lambda: _revalidate_with(path, public_path_condition="other")),
        (
            "path_strategy_changed",
            lambda: _revalidate_with(
                path,
                path_strategy_id=next(
                    item for item in PATH_STRATEGIES if item != path.path_strategy_id
                ),
            ),
        ),
        (
            "path_condition_id_changed",
            lambda: _revalidate_with(path, public_condition_id="changed"),
        ),
        ("path_identity_reused", lambda: _revalidate_with(path, path_id="old")),
        ("path_deleted", lambda: _revalidate_with(paths, paths=paths.paths[1:])),
        (
            "resource_prompt_threshold",
            lambda: _revalidate_with(resource, prompt_upper_bound_bytes=60001),
        ),
        (
            "resource_rollout_threshold",
            lambda: _revalidate_with(resource, rollout_upper_bound_tokens=1140000),
        ),
        ("resource_detour_count", lambda: _revalidate_with(resource, maximum_ordinary_detours=2)),
        (
            "unconditional_condition_inserted",
            lambda: _revalidate_with(unconditional, requested_path_id=path.path_id),
        ),
        (
            "conditioned_condition_removed",
            lambda: _revalidate_with(conditioned, requested_path_id=None),
        ),
        ("conditioned_replicate_changed", lambda: _revalidate_with(conditioned, replicate_index=6)),
        ("job_seed_changed", lambda: _revalidate_with(conditioned, seed=conditioned.seed + 1)),
        ("job_identity_reused", lambda: _revalidate_with(conditioned, job_id="old")),
        ("manifest_job_deleted", lambda: _revalidate_with(manifest, jobs=manifest.jobs[1:])),
        (
            "manifest_population_changed",
            lambda: _revalidate_with(manifest, source_population_id="changed"),
        ),
        (
            "manifest_execution_opened",
            lambda: _revalidate_with(manifest, execution_authorized=True),
        ),
        (
            "runner_condition_unbound",
            lambda: _revalidate_with(runner, condition_bound_before_provider_invocation=False),
        ),
        (
            "runner_reachability_route_removed",
            lambda: _revalidate_with(runner, reachability_identity_or_route_present=False),
        ),
        (
            "runner_stage_two_route",
            lambda: _revalidate_with(runner, stage_two_provider_call_upper_bound=1),
        ),
        (
            "runner_execution_authorized_early",
            lambda: _revalidate_with(runner, empirical_execution_authorized=True),
        ),
        (
            "transition_state_mapping_enabled",
            lambda: _revalidate_with(transition, state_mapping_contract_or_rows_authorized=True),
        ),
        (
            "transition_historical_pooling",
            lambda: _revalidate_with(
                transition, historical_rerun_pooling_or_reclassification_authorized=True
            ),
        ),
        (
            "transition_protocol_change",
            lambda: _revalidate_with(
                transition, task_path_condition_grammar_model_resource_change_authorized=True
            ),
        ),
    )
    rows = tuple(_reject(name, action) for name, action in mutations)
    values = {
        "mutations": rows,
        "mutation_count": len(rows),
        "rejected_count": len(rows),
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_destructive:",
        ),
        **values,
    )


def _transition(
    contract: ExecutionContract,
    manifest: ReachabilityManifest,
    runner: RunnerContract,
    outcome: OutcomeContract,
) -> ProspectiveTransitionContract:
    values = {
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_fresh_reachability_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> ReachabilityPreflightReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    print(
        f"[v26.153] source replay {source.replay_pass_count}/{source.replayed_file_count} exact",
        flush=True,
    )
    predecessor_integrity = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source=source,
    )
    frozen_inputs, frozen_input = _load_frozen_reachability_inputs(
        package_root=package_root,
        source=source,
    )

    # The exact frozen source denominator is closed before any current Support or Verifier load.
    joint = _load_joint_contract(package_root)
    grammar = compile_qualified_final_response_grammar()
    role_inputs = old_capability._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    static = role_inputs.static
    tasks = _make_task_catalog(
        package_root=package_root,
        inputs=frozen_inputs,
        frozen_input=frozen_input,
        joint=joint,
        grammar=grammar,
    )
    paths, registered, unconditional = _make_paths(
        tasks=tasks,
        frozen_input=frozen_input,
        static=static,
        grammar=grammar,
    )
    support = _support_closure(paths, registered)
    detours = _make_detour_audit(
        package_root=package_root,
        paths=paths,
        executions=registered,
        frozen_input=frozen_input,
        static=static,
        grammar=grammar,
        support=support,
    )
    resource = _make_resource(paths, support, detours)
    contract = _make_execution_contract(
        frozen_input=frozen_input,
        tasks=tasks,
        paths=paths,
        resource=resource,
        joint=joint,
        grammar=grammar,
    )
    manifest = _make_manifest(
        package_root=package_root,
        frozen_input=frozen_input,
        tasks=tasks,
        paths=paths,
        resource=resource,
        contract=contract,
    )
    outcome = _make_outcome(contract, manifest)
    runner = _make_runner(
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        resource=resource,
        joint=joint,
        grammar=grammar,
    )
    fixture = _make_fixture(
        tasks=tasks,
        registered_paths=registered,
        unconditional_paths=unconditional,
        manifest=manifest,
        resource=resource,
        runner=runner,
        joint=joint,
        grammar=grammar,
        static=static,
    )
    controls = _make_controls(
        tasks=tasks,
        registered_paths=registered,
        unconditional_paths=unconditional,
        manifest=manifest,
        resource=resource,
        runner=runner,
        grammar=grammar,
        static=static,
        support=support,
        fixture=fixture,
    )
    transition = _transition(contract, manifest, runner, outcome)
    destructive = _make_destructive(
        frozen_input=frozen_input,
        tasks=tasks,
        paths=paths,
        manifest=manifest,
        resource=resource,
        runner=runner,
        transition=transition,
    )
    prospective_execution_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner.contract_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_fresh_reachability_execution:",
    )
    prospective_report_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_fresh_reachability_execution_report:",
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("destructive_audit.json", destructive),
        ("detour_qualification_audit.json", detours),
        ("frozen_reachability_input_audit.json", frozen_input),
        ("joint_support_validity_contract.json", joint),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("prospective_transition_contract.json", transition),
        ("qualified_final_response_grammar.json", grammar),
        ("reachability_execution_contract.json", contract),
        ("reachability_manifest.json", manifest),
        ("reachability_outcome_contract.json", outcome),
        ("reachability_path_catalog.json", paths),
        ("reachability_resource_contract.json", resource),
        ("reachability_runner_contract.json", runner),
        ("reachability_runner_control_audit.json", controls),
        ("reachability_runner_fixture_audit.json", fixture),
        ("reachability_task_package_catalog.json", tasks),
        ("source_replay_audit.json", source),
        ("support_closure_audit.json", support),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_integrity_audit_id": predecessor_integrity.audit_id,
        "frozen_input_audit_id": frozen_input.audit_id,
        "task_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
        "detour_qualification_audit_id": detours.audit_id,
        "resource_contract_id": resource.contract_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "runner_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "prospective_execution_id": prospective_execution_id,
        "prospective_report_id": prospective_report_id,
        "detail_files": details,
    }
    provisional = ReachabilityPreflightReport.model_construct(report_id="pending", **values)
    report = ReachabilityPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_fresh_reachability_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.153 fresh Reachability Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_fresh_reachability_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
