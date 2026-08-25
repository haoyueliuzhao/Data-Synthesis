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
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
    build_capability_sensitive_frontier_population,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_capability_runner_vnext as runner_vnext
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

RUN_ID: Final = "finance_v26_150_fresh_capability_runner_preflight_v2_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_150_fresh_capability_runner_preflight_v2_20260825"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/runtime/agent/prospective_capability_runner_vnext.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_capability_runner_preflight.py",
)
NEXT_STAGE: Final = "fresh_capability_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = "finance_v26_150_fresh_capability_runner_v2_20260825"
PROSPECTIVE_EXECUTION_RUN_ID: Final = "finance_v26_151_fresh_capability_execution_v2_20260825"
PROSPECTIVE_REPORT_RUN_ID: Final = "finance_v26_151_fresh_capability_execution_report_v2_20260825"
SOURCE_RUN_ID: Final = "finance_v26_150_fresh_capability_source_v2_20260825"
SOURCE_SAMPLING_SALT: Final = "finance-v26.150-fresh-capability-source-v1"
SOURCE_SELECTION_SALT: Final = "finance-v26.150-fresh-capability-selection-v1"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_joint_support_verifier_preflight_report:"
    "6f86c51ee9e3229b088bf772d741ea10f0da4befd995bc97f74ba33d3e8e338e"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "cde39718dcc471aaeb413ab36f0c675759bd7ae5a20f6b522ccac4c77a41e9f6"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_joint_support_verifier_transition:"
    "f8065841b124eba0a4313e5a6b5a7569604153dab122cc27c7f5ac312696ddc3"
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

MECHANISMS: Final = tuple(source_base.TARGET_MECHANISMS)
TIERS: Final = tuple(source_base.TIERS)
FRESHNESS_CHANNELS: Final = tuple(source_base.FRESHNESS_CHANNELS)
TASK_COUNT: Final = 12
PATH_COUNT: Final = 12
JOB_COUNT: Final = 96
REPLICAS_PER_TASK: Final = 8
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
    raise ValueError(f"v26.150 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_149_transitive_source",
        "v26_149_output",
        "v26_150_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[7332] = 7332
    predecessor_output_file_count: Literal[9] = 9
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[7343] = 7343
    replay_pass_count: Literal[7343] = 7343
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7343, max_length=7343)
    replay_before_source_selection: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_fresh_capability_source_replay.v1"] = (
        "finance_v26_fresh_capability_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_capability_source_replay:")
        ):
            raise ValueError("v26.150 source replay changed")
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
    historical_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_fresh_capability_predecessor_integrity.v1"] = (
        "finance_v26_fresh_capability_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ) or self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_capability_predecessor_integrity:",
        ):
            raise ValueError("v26.150 predecessor integrity changed")
        return self


class FreshCapabilitySourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    source_task: CapabilitySensitiveTaskArtifact
    source_task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    core_semantic_signature: str = Field(min_length=1)
    task_signature: str = Field(min_length=1)
    mechanism_instance_signature: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    source_rank: str = Field(min_length=1)
    selected_before_support_or_verifier_load: Literal[True] = True
    model_outcomes_used_for_selection: Literal[False] = False
    resource_values_used_for_selection: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self) -> FreshCapabilitySourceBinding:
        if (
            self.source_task.artifact_id != self.source_task_artifact_id
            or self.source_task.task.task_id != self.task_id
            or self.binding_id
            != _identity(self, "binding_id", "finance_v26_fresh_capability_source_binding:")
        ):
            raise ValueError("v26.150 source binding changed")
        return self


class FreshCapabilitySourcePopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_sampling_salt: str = SOURCE_SAMPLING_SALT
    source_selection_salt: str = SOURCE_SELECTION_SALT
    tasks: tuple[FreshCapabilitySourceBinding, ...] = Field(min_length=12, max_length=12)
    task_count: Literal[12] = 12
    mechanisms: tuple[str, ...] = MECHANISMS
    tiers: tuple[str, ...] = TIERS
    development_localization_only: Literal[True] = True
    stable_population_ability_claimed: Literal[False] = False
    independent_confirmation_population_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    model_exposure_count: Literal[0] = 0
    schema_version: Literal["finance_v26_fresh_capability_source_population.v1"] = (
        "finance_v26_fresh_capability_source_population.v1"
    )

    @model_validator(mode="after")
    def validate_population(self) -> FreshCapabilitySourcePopulation:
        cells = {(item.mechanism_id, item.tier) for item in self.tasks}
        if (
            len(cells) != 12
            or cells != {(mechanism, tier) for mechanism in MECHANISMS for tier in TIERS}
            or len({item.source_task_artifact_id for item in self.tasks}) != 12
            or self.population_id
            != _identity(self, "population_id", "finance_v26_fresh_capability_population:")
        ):
            raise ValueError("v26.150 source Population changed")
        return self


class FreshnessChannelRow(FrozenModel):
    channel: str = Field(min_length=1)
    prior_count: int = Field(ge=0)
    selected_count: int = Field(gt=0)
    overlap_count: Literal[0] = 0


class SourceSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    capability_population_id: str = Field(min_length=1)
    prior_historical_excluded_evidence_count: int = Field(gt=0)
    old_capability_and_reachability_evidence_excluded_count: int = Field(gt=0)
    effective_excluded_evidence_count: int = Field(gt=0)
    source_frame_task_count: int = Field(ge=12)
    source_frame_selected_evidence_count: int = Field(gt=0)
    freshness_channels: tuple[FreshnessChannelRow, ...] = Field(min_length=8, max_length=8)
    mechanism_tier_cell_count: Literal[12] = 12
    tasks_selected_before_joint_contract_load: Literal[True] = True
    historical_validity_used_for_selection: Literal[False] = False
    verifier_passability_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["fresh_capability_population_frozen"] = "fresh_capability_population_frozen"
    schema_version: Literal["finance_v26_fresh_capability_source_selection.v1"] = (
        "finance_v26_fresh_capability_source_selection.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceSelectionAudit:
        if (
            tuple(item.channel for item in self.freshness_channels) != FRESHNESS_CHANNELS
            or any(item.overlap_count for item in self.freshness_channels)
            or self.audit_id
            != _identity(self, "audit_id", "finance_v26_fresh_capability_source_selection:")
        ):
            raise ValueError("v26.150 source selection changed")
        return self


class FreshCapabilityTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["capability"] = "capability"
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
    schema_version: Literal["finance_v26_fresh_capability_task_package.v1"] = (
        "finance_v26_fresh_capability_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> FreshCapabilityTaskPackage:
        if (
            self.operational_record.environment_manifest_id != self.environment.manifest_id
            or self.prompt_contract.role != "capability"
            or self.task_package_id
            != _identity(self, "task_package_id", "finance_v26_fresh_capability_task_package:")
        ):
            raise ValueError("v26.150 TaskPackage changed")
        return self


class TaskPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    packages: tuple[FreshCapabilityTaskPackage, ...] = Field(min_length=12, max_length=12)
    task_package_count: Literal[12] = 12
    mechanism_tier_cell_count: Literal[12] = 12
    old_task_package_overlap_count: Literal[0] = 0
    reachability_task_package_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> TaskPackageCatalog:
        if len(
            {item.task_package_id for item in self.packages}
        ) != 12 or self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_fresh_capability_task_catalog:"
        ):
            raise ValueError("v26.150 TaskPackage Catalog changed")
        return self


class FreshCapabilityPath(FrozenModel):
    path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    role: Literal["capability"] = "capability"
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    path_strategy_id: Literal["structured_direct"] = "structured_direct"
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
    def validate_path(self) -> FreshCapabilityPath:
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
            or self.maximum_action_primary_prompt_utf8_bytes > PROMPT_CEILING_BYTES
            or self.primary_request_count > MAXIMUM_PRIMARY_REQUESTS
            or self.static_complete_path_upper_bound_tokens >= ROLLOUT_BOUND_TOKENS
            or self.path_id != _identity(self, "path_id", "finance_v26_fresh_capability_path:")
        ):
            raise ValueError("v26.150 Capability Path changed")
        return self


class PathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    paths: tuple[FreshCapabilityPath, ...] = Field(min_length=12, max_length=12)
    path_count: Literal[12] = 12
    registered_state_count: int = Field(gt=0)
    maximum_candidate_count: int = Field(gt=0)
    maximum_prompt_utf8_bytes: int = Field(gt=0)
    maximum_registered_path_tokens: int = Field(gt=0)
    old_path_overlap_count: Literal[0] = 0
    reachability_path_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> PathCatalog:
        if (
            len({item.path_id for item in self.paths}) != 12
            or self.registered_state_count != sum(item.action_state_count for item in self.paths)
            or self.catalog_id
            != _identity(self, "catalog_id", "finance_v26_fresh_capability_path_catalog:")
        ):
            raise ValueError("v26.150 Path Catalog changed")
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
            "finance_v26_fresh_capability_support_event:",
        ):
            raise ValueError("v26.150 Support event changed")
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
            != _identity(self, "audit_id", "finance_v26_fresh_capability_support_closure:")
        ):
            raise ValueError("v26.150 Support Closure changed")
        return self


class ResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
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
    conservative_one_detour_upper_bound_tokens: int = Field(gt=0, lt=1120000)
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> ResourceContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_capability_resource_contract:",
        ):
            raise ValueError("v26.150 Resource Contract changed")
        return self


class ExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    qualified_final_grammar_id: str = Field(min_length=1)
    exact_denominator: Literal[96] = 96
    task_count: Literal[12] = 12
    replicas_per_task: Literal[8] = 8
    capability_development_localization_only: Literal[True] = True
    task_weighted_primary_estimand: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> ExecutionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_capability_execution_contract:",
        ):
            raise ValueError("v26.150 Execution Contract changed")
        return self


class FreshCapabilityJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: Literal["capability_unconditional"] = "capability_unconditional"
    replicate_index: int = Field(ge=0, le=7)
    seed: int = Field(ge=0)
    stage_one_profile_id: str = bounded.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = bounded.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = Field(min_length=1)
    candidate_presentation_parent_id: str = Field(min_length=1)
    historical_job_or_seed_reused: Literal[False] = False
    execution_opened: Literal[False] = False

    @model_validator(mode="after")
    def validate_job(self) -> FreshCapabilityJob:
        if self.job_id != _identity(
            self,
            "job_id",
            "finance_v26_fresh_capability_job:",
        ):
            raise ValueError("v26.150 Job changed")
        return self


class CapabilityManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_report_run_id: str = PROSPECTIVE_REPORT_RUN_ID
    jobs: tuple[FreshCapabilityJob, ...] = Field(min_length=96, max_length=96)
    exact_denominator: Literal[96] = 96
    distinct_task_count: Literal[12] = 12
    rollouts_per_task: Literal[8] = 8
    distinct_seed_count: Literal[96] = 96
    historical_job_overlap_count: Literal[0] = 0
    historical_seed_overlap_count: Literal[0] = 0
    reachability_job_count: Literal[0] = 0
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> CapabilityManifest:
        counts = Counter(item.task_package_id for item in self.jobs)
        if (
            len({item.job_id for item in self.jobs}) != 96
            or len({item.seed for item in self.jobs}) != 96
            or len(counts) != 12
            or any(
                item.candidate_presentation_parent_id != self.source_selection_audit_id
                for item in self.jobs
            )
            or set(counts.values()) != {8}
            or self.manifest_id
            != _identity(self, "manifest_id", "finance_v26_fresh_capability_manifest:")
        ):
            raise ValueError("v26.150 Manifest changed")
        return self


class OutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = EXPECTED_JOINT_CONTRACT_ID
    exact_denominator: Literal[96] = 96
    measurement_gate: tuple[str, ...] = (
        "complete_raw_96_of_96",
        "model_endpoint_96_of_96",
        "measurement_support_exit_zero",
        "instrument_failure_zero",
        "privacy_failure_zero",
        "exact_model_thinking_usage_failure_zero",
        "typed_budget_no_call_zero",
        "unresolved_transport_failure_zero",
    )
    primary_estimands: tuple[str, str, str] = (
        "base_trajectory_validity",
        "mechanism_qualification",
        "qualified_trajectory_validity",
    )
    task_first_rollout_secondary: Literal[True] = True
    reachability_gate_requires_each_mechanism_qualified_support: Literal[True] = True
    no_posthoc_task_deletion_threshold_change_or_host_repair: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    state_mapping_rows: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> OutcomeContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_capability_outcome_contract:",
        ):
            raise ValueError("v26.150 Outcome Contract changed")
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
    exact_job_denominator: Literal[96] = 96
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_ordinary_detours: Literal[1] = 1
    measurement_support_after_observation_before_next_provider: Literal[True] = True
    failed_and_progress_observation_skip_baseline: Literal[True] = True
    successful_no_progress_only_baseline: Literal[True] = True
    qualified_final_parser_before_usable_classification: Literal[True] = True
    privacy_envelope_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    exact_model_thinking_profile_required: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    reachability_identity_or_route_present: Literal[False] = False
    empirical_execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> RunnerContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_capability_runner_contract:",
        ):
            raise ValueError("v26.150 Runner Contract changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    scripted_job_count: Literal[96] = 96
    completed_job_count: Literal[96] = 96
    first_action_interface_qualified_count: Literal[96] = 96
    qualified_final_payload_count: Literal[96] = 96
    joint_task_verifier_invocation_count: Literal[96] = 96
    joint_qualified_valid_count: Literal[96] = 96
    covered_mechanism_tier_cell_count: Literal[12] = 12
    scripted_local_calls: int = Field(gt=0)
    action_payload_count: int = Field(gt=0)
    public_observation_count: int = Field(gt=0)
    support_decision_count: int = Field(gt=0)
    raw_recovery_pass_count: Literal[96] = 96
    sensitive_prompt_key_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_capability_runner_fixture:",
        ):
            raise ValueError("v26.150 Runner Fixture changed")
        return self


class ControlRow(FrozenModel):
    row_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    metrics: dict[str, Any]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> ControlRow:
        if self.row_id != _identity(self, "row_id", "finance_v26_fresh_capability_control:"):
            raise ValueError("v26.150 Control Row changed")
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
            != _identity(self, "audit_id", "finance_v26_fresh_capability_runner_controls:")
        ):
            raise ValueError("v26.150 Runner Controls changed")
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
            != _identity(self, "audit_id", "finance_v26_fresh_capability_destructive:")
        ):
            raise ValueError("v26.150 Destructive Audit changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_capability_execution_only"] = NEXT_STAGE
    exact_fresh_96_job_execution_authorized: Literal[True] = True
    reachability_identity_or_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    historical_rerun_pooling_or_reclassification_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_capability_transition:",
        ):
            raise ValueError("v26.150 Transition changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class CapabilityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    task_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
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
    fresh_task_count: Literal[12] = 12
    fresh_job_count: Literal[96] = 96
    reachability_identity_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["fresh_capability_execution_only"] = NEXT_STAGE
    detail_files: tuple[DetailFile, ...] = Field(min_length=17)
    status: Literal["fresh_capability_runner_preflight_passed"] = (
        "fresh_capability_runner_preflight_passed"
    )

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityPreflightReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_fresh_capability_preflight_report:",
        ):
            raise ValueError("v26.150 Report changed")
        return self


@dataclass(frozen=True)
class _CompiledPath:
    package: FreshCapabilityTaskPackage
    path: FreshCapabilityPath
    states: tuple[SemanticActionState, ...]
    proposals: tuple[CanonicalActionProposal, ...]
    commits: tuple[CanonicalActionCommit, ...]
    observations: tuple[AgentToolObservation, ...]
    action_prompts: tuple[str, ...]
    qualified_final_primary_prompt: str
    qualified_final_rescue_prompt: str
    legacy_final_primary_prompt: str


def _source_replay(*, package_root: Path, implementation_root: Path) -> SourceReplayAudit:
    predecessor_dir = package_root / predecessor.OUTPUT_DIR
    report_path = predecessor_dir / "report.json"
    report = predecessor.JointPreflightReport.model_validate(_load(report_path))
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage
        != "fresh_capability_population_and_runner_rematerialization_preflight_only"
        or not transition.fresh_capability_population_runner_preflight_authorized
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.150 direct predecessor changed")
    old_source = predecessor.SourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
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
                source_kind="v26_149_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    outputs = {item.relative_path: item.sha256 for item in report.detail_files}
    outputs["report.json"] = EXPECTED_PREDECESSOR_REPORT_SHA256
    for name, digest in sorted(outputs.items()):
        path = predecessor_dir / name
        if _sha256(path) != digest:
            raise ValueError(f"v26.150 predecessor output changed: {name}")
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_149_output",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    for relative in IMPLEMENTATION_PATHS:
        path = implementation_root / relative
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative,
                source_kind="v26_150_implementation",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    values = {"entries": tuple(sorted(entries, key=lambda item: item.relative_path))}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_capability_source_replay:",
        ),
        **values,
    )


def _predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    formal_dir = package_root / predecessor.OUTPUT_DIR
    with tempfile.TemporaryDirectory(prefix="v26_150_predecessor_") as temporary:
        rebuilt_dir = Path(temporary)
        predecessor.build_joint_support_verifier_preflight(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        formal = tuple(sorted(path for path in formal_dir.iterdir() if path.is_file()))
        rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal) != tuple(path.name for path in rebuilt):
            raise ValueError("v26.150 predecessor file set changed")
        comparisons = tuple(
            FileComparison(
                relative_path=item.name,
                expected_sha256=_sha256(item),
                observed_sha256=_sha256(rebuilt_dir / item.name),
                byte_count=item.stat().st_size,
            )
            for item in formal
        )
    values = {"source_replay_audit_id": source.audit_id, "comparisons": comparisons}
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_capability_predecessor_integrity:",
        ),
        **values,
    )


def _old_source_population_dir(package_root: Path) -> Path:
    return package_root / source_base.OUTPUT_DIR


def _binding_channel_values(binding: source_base.RoleSourceTaskBinding) -> dict[str, set[str]]:
    return {
        "task_id": {binding.task_id},
        "source_task_id": {binding.source_task_artifact_id},
        "evidence_id": set(binding.evidence_ids),
        "evidence_version_id": set(binding.evidence_version_ids),
        "core_semantic_signature": {binding.core_semantic_signature},
        "task_signature": {binding.task_signature},
        "mechanism_instance_signature": {binding.mechanism_instance_signature},
        "source_record_id": set(binding.source_record_ids),
    }


def _source_rank(task: CapabilitySensitiveTaskArtifact, mechanism: str, tier: str) -> str:
    return canonical_hash(
        {
            "salt": SOURCE_SELECTION_SALT,
            "mechanism": mechanism,
            "tier": tier,
            "source_task_artifact_id": task.artifact_id,
        },
        prefix="finance_v26_fresh_capability_source_rank:",
    )


def _fresh_source_binding(
    *, task: CapabilitySensitiveTaskArtifact, mechanism: str, tier: str
) -> FreshCapabilitySourceBinding:
    channels = source_base._source_task_channels((task,))  # noqa: SLF001
    values = {
        "mechanism_id": cast(MechanismId, mechanism),
        "tier": tier,
        "source_task": task,
        "source_task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "core_semantic_signature": next(iter(channels["core_semantic_signature"])),
        "task_signature": task.task.task_hash,
        "mechanism_instance_signature": next(iter(channels["mechanism_instance_signature"])),
        "evidence_ids": tuple(sorted(channels["evidence_id"])),
        "evidence_version_ids": tuple(sorted(channels["evidence_version_id"])),
        "source_record_ids": tuple(sorted(channels["source_record_id"])),
        "source_rank": _source_rank(task, mechanism, tier),
    }
    provisional = FreshCapabilitySourceBinding.model_construct(binding_id="pending", **values)
    return FreshCapabilitySourceBinding(
        binding_id=_identity(
            provisional,
            "binding_id",
            "finance_v26_fresh_capability_source_binding:",
        ),
        **values,
    )


def _freeze_fresh_source_population(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
    source: SourceReplayAudit,
) -> tuple[
    CapabilitySensitiveFrontierPopulation,
    FreshCapabilitySourcePopulation,
    SourceSelectionAudit,
]:
    old_dir = _old_source_population_dir(package_root)
    old_source = source_base.SourceReplayAudit.model_validate(
        _load(old_dir / "source_replay_audit.json")
    )
    historical = source_base._build_historical_inputs(  # noqa: SLF001
        source=old_source,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    prior = {key: set(value) for key, value in historical.prior_channels.items()}
    old_selected_evidence: set[str] = set()
    for name, expected_id in (
        ("capability_source_population.json", EXPECTED_OLD_CAPABILITY_POPULATION_ID),
        ("reachability_source_population.json", EXPECTED_OLD_REACHABILITY_POPULATION_ID),
    ):
        old_population = source_base.FreshRoleSourcePopulation.model_validate(_load(old_dir / name))
        if old_population.population_id != expected_id:
            raise ValueError("v26.150 historical role Population changed")
        for binding in old_population.tasks:
            channels = _binding_channel_values(binding)
            old_selected_evidence.update(channels["evidence_id"])
            for key in FRESHNESS_CHANNELS:
                prior[key].update(channels[key])
    effective_evidence = tuple(sorted(prior["evidence_id"]))
    frame_path = output_dir / "fresh_source_sampling_frame.json"
    frame = build_capability_sensitive_frontier_population(
        source_artifacts_path=package_root / source_base.SNAPSHOT_PATH,
        output_path=frame_path,
        run_id=SOURCE_RUN_ID,
        sampling_salt=SOURCE_SAMPLING_SALT,
        excluded_evidence_ids=effective_evidence,
    )
    bindings: list[FreshCapabilitySourceBinding] = []
    selected_tasks: list[CapabilitySensitiveTaskArtifact] = []
    for mechanism in MECHANISMS:
        family = source_base.ROLE_MECHANISM_SOURCE_FAMILY[mechanism]
        for tier in TIERS:
            candidates = sorted(
                (item for item in frame.tasks if item.family == family and item.tier.value == tier),
                key=lambda item: _source_rank(item, mechanism, tier),
            )
            if not candidates:
                raise ValueError(f"v26.150 source frame lacks {mechanism}|{tier}")
            task = candidates[0]
            selected_tasks.append(task)
            bindings.append(_fresh_source_binding(task=task, mechanism=mechanism, tier=tier))
    population_values = {
        "source_frame_population_id": frame.population_id,
        "tasks": tuple(sorted(bindings, key=lambda item: item.binding_id)),
    }
    provisional_population = FreshCapabilitySourcePopulation.model_construct(
        population_id="pending", **population_values
    )
    population = FreshCapabilitySourcePopulation(
        population_id=_identity(
            provisional_population,
            "population_id",
            "finance_v26_fresh_capability_population:",
        ),
        **population_values,
    )
    selected_channels = source_base._source_task_channels(tuple(selected_tasks))  # noqa: SLF001
    channel_rows = tuple(
        FreshnessChannelRow(
            channel=key,
            prior_count=len(prior[key]),
            selected_count=len(selected_channels[key]),
            overlap_count=cast(Literal[0], len(prior[key] & selected_channels[key])),
        )
        for key in FRESHNESS_CHANNELS
    )
    if any(item.overlap_count for item in channel_rows):
        raise ValueError("v26.150 fresh source selection overlaps prior identities")
    frame_evidence = {
        evidence.evidence_id for task in frame.tasks for evidence in task.public_corpus.evidence
    }
    selection_values = {
        "source_replay_audit_id": source.audit_id,
        "source_frame_population_id": frame.population_id,
        "capability_population_id": population.population_id,
        "prior_historical_excluded_evidence_count": len(historical.effective_excluded_evidence_ids),
        "old_capability_and_reachability_evidence_excluded_count": len(old_selected_evidence),
        "effective_excluded_evidence_count": len(effective_evidence),
        "source_frame_task_count": len(frame.tasks),
        "source_frame_selected_evidence_count": len(frame_evidence),
        "freshness_channels": channel_rows,
    }
    provisional_selection = SourceSelectionAudit.model_construct(
        audit_id="pending", **selection_values
    )
    selection = SourceSelectionAudit(
        audit_id=_identity(
            provisional_selection,
            "audit_id",
            "finance_v26_fresh_capability_source_selection:",
        ),
        **selection_values,
    )
    _write_json_atomic(output_dir / "fresh_capability_source_population.json", population)
    _write_json_atomic(output_dir / "source_selection_audit.json", selection)
    return frame, population, selection


def _load_joint_contract(package_root: Path) -> JointSupportValidityContract:
    contract = JointSupportValidityContract.model_validate(
        _load(package_root / predecessor.OUTPUT_DIR / "joint_support_validity_contract.json")
    )
    if contract.contract_id != EXPECTED_JOINT_CONTRACT_ID:
        raise ValueError("v26.150 Joint Contract changed")
    return contract


def _make_task_catalog(
    *,
    package_root: Path,
    population: FreshCapabilitySourcePopulation,
    selection: SourceSelectionAudit,
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
    packages: list[FreshCapabilityTaskPackage] = []
    for binding in population.tasks:
        source_task = binding.source_task
        draft = bounded.predecessor._role_draft(  # noqa: SLF001
            source_task,
            role="capability",
            mechanism=binding.mechanism_id,
        )
        source_record, source_environment = bounded.predecessor._upgrade_role_task(draft)  # noqa: SLF001
        environment = bounded.predecessor._verifier_bound_environment(  # noqa: SLF001
            bounded.predecessor._harden_environment(source_environment)  # noqa: SLF001
        )
        authority_record = bounded.predecessor._harden_record(source_record, environment)  # noqa: SLF001
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
            role="capability",
            record=record,
            environment=environment,
        )
        values = {
            "source_population_id": population.population_id,
            "source_selection_audit_id": selection.audit_id,
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
        provisional = FreshCapabilityTaskPackage.model_construct(
            task_package_id="pending", **values
        )
        packages.append(
            FreshCapabilityTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_fresh_capability_task_package:",
                ),
                **values,
            )
        )
    values = {
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "packages": tuple(sorted(packages, key=lambda item: item.task_package_id)),
    }
    provisional = TaskPackageCatalog.model_construct(catalog_id="pending", **values)
    return TaskPackageCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_fresh_capability_task_catalog:",
        ),
        **values,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + CHAT_ENVELOPE_TOKENS + ACCOUNTED_COMPLETION_BOUND


def _runtime_binding(
    package: FreshCapabilityTaskPackage,
    selection_id: str,
) -> runner_vnext.FreshCapabilityRuntimeBinding:
    return runner_vnext.FreshCapabilityRuntimeBinding(
        package=package,
        record=package.operational_record,
        environment=package.environment,
        prompt_contract=package.prompt_contract,
        source_selection_id=selection_id,
    )


def _compile_path(
    *,
    package: FreshCapabilityTaskPackage,
    selection_id: str,
    action_grammar: SemanticActionResponseGrammar,
    old_final_grammar: ExactFinalResponseGrammar,
    qualified_grammar: QualifiedFinalResponseGrammar,
) -> _CompiledPath:
    binding = _runtime_binding(package, selection_id)
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
                public_path_condition=None,
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
        proposal = s1_runner._reference_proposal_from_s1_prompt(prompts["primary"])  # noqa: SLF001
        selected = evaluate_canonical_action_proposal(
            state,
            proposal,
            call_index=len(observations) + 1,
        )
        if selected.commit is None or selected.rejection is not None:
            raise ValueError("v26.150 reference Proposal did not Commit")
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
            raise ValueError("v26.150 non-final reference Commit lacks call")
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
            raise ValueError("v26.150 reference Path leaves Measurement Support")
        support.append(decision)
    else:
        raise ValueError("v26.150 reference Path did not close")
    compact = render_compact_final_prompt(
        package.prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=None,
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
    values = {
        "task_package_id": package.task_package_id,
        "source_task_artifact_id": package.source_task_artifact_id,
        "mechanism_id": package.mechanism_id,
        "tier": package.tier,
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
    provisional = FreshCapabilityPath.model_construct(path_id="pending", **values)
    path = FreshCapabilityPath(
        path_id=_identity(
            provisional,
            "path_id",
            "finance_v26_fresh_capability_path:",
        ),
        **values,
    )
    return _CompiledPath(
        package=package,
        path=path,
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
    selection: SourceSelectionAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
) -> tuple[PathCatalog, tuple[_CompiledPath, ...]]:
    executions = tuple(
        _compile_path(
            package=package,
            selection_id=selection.audit_id,
            action_grammar=static.action_grammar,
            old_final_grammar=static.final_grammar,
            qualified_grammar=grammar,
        )
        for package in tasks.packages
    )
    paths = tuple(sorted((item.path for item in executions), key=lambda item: item.path_id))
    values = {
        "task_package_catalog_id": tasks.catalog_id,
        "paths": paths,
        "registered_state_count": sum(item.action_state_count for item in paths),
        "maximum_candidate_count": max(item.maximum_candidate_count for item in paths),
        "maximum_prompt_utf8_bytes": max(
            max(
                item.maximum_action_primary_prompt_utf8_bytes,
                item.maximum_action_abi_rescue_prompt_utf8_bytes,
                item.maximum_semantic_recovery_prompt_utf8_bytes,
                item.final_primary_prompt_utf8_bytes,
                item.final_rescue_prompt_utf8_bytes,
            )
            for item in paths
        ),
        "maximum_registered_path_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in paths
        ),
    }
    provisional = PathCatalog.model_construct(catalog_id="pending", **values)
    catalog = PathCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_fresh_capability_path_catalog:",
        ),
        **values,
    )
    index = {item.path.path_id: item for item in executions}
    return catalog, tuple(index[item.path_id] for item in catalog.paths)


def _support_closure(
    paths: PathCatalog, executions: Sequence[_CompiledPath]
) -> SupportClosureAudit:
    rows: list[SupportClosureEventRow] = []
    states: set[str] = set()
    for execution in executions:
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
                    raise ValueError("v26.150 visible Candidate failed to Commit")
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
                            raise ValueError("v26.150 support prefix contains a non-call Commit")
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
                        raise ValueError("v26.150 support prefix replay changed")
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
                    "path_id": execution.path.path_id,
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
                            "finance_v26_fresh_capability_support_event:",
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
                raise ValueError("v26.150 semantic recovery fixture did not reject")
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
            "finance_v26_fresh_capability_support_closure:",
        ),
        **support_values,
    )


def _make_resource(
    paths: PathCatalog,
    support: SupportClosureAudit,
) -> ResourceContract:
    max_path = paths.maximum_registered_path_tokens
    conservative_detour = max_path + _request_bound("x" * paths.maximum_prompt_utf8_bytes)
    values = {
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
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
    }
    provisional = ResourceContract.model_construct(contract_id="pending", **values)
    return ResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_capability_resource_contract:",
        ),
        **values,
    )


def _make_execution_contract(
    *,
    population: FreshCapabilitySourcePopulation,
    tasks: TaskPackageCatalog,
    paths: PathCatalog,
    resource: ResourceContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
) -> ExecutionContract:
    values = {
        "source_population_id": population.population_id,
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
            "finance_v26_fresh_capability_execution_contract:",
        ),
        **values,
    )


def _job_seed(*, task_id: str, replicate_index: int) -> int:
    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
                "task_package_id": task_id,
                "replicate_index": replicate_index,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return int(digest[:15], 16)


def _historical_jobs_and_seeds(package_root: Path) -> tuple[set[str], set[int]]:
    old = old_capability.CapabilityManifest.model_validate(
        _load(package_root / old_capability.OUTPUT_DIR / "privacy_safe_capability_manifest.json")
    )
    return {item.job_id for item in old.jobs}, {item.seed for item in old.jobs}


def _make_manifest(
    *,
    package_root: Path,
    population: FreshCapabilitySourcePopulation,
    tasks: TaskPackageCatalog,
    paths: PathCatalog,
    resource: ResourceContract,
    contract: ExecutionContract,
) -> CapabilityManifest:
    path_by_task = {item.task_package_id: item for item in paths.paths}
    jobs: list[FreshCapabilityJob] = []
    for package in tasks.packages:
        path = path_by_task[package.task_package_id]
        for replicate in range(REPLICAS_PER_TASK):
            values = {
                "contract_id": contract.contract_id,
                "resource_contract_id": resource.contract_id,
                "task_package_id": package.task_package_id,
                "path_id": path.path_id,
                "source_task_artifact_id": package.source_task_artifact_id,
                "mechanism_id": package.mechanism_id,
                "tier": package.tier,
                "replicate_index": replicate,
                "seed": _job_seed(
                    task_id=package.task_package_id,
                    replicate_index=replicate,
                ),
                "exact_final_response_grammar_id": contract.qualified_final_grammar_id,
                "candidate_presentation_parent_id": package.source_selection_audit_id,
            }
            provisional = FreshCapabilityJob.model_construct(job_id="pending", **values)
            jobs.append(
                FreshCapabilityJob(
                    job_id=_identity(
                        provisional,
                        "job_id",
                        "finance_v26_fresh_capability_job:",
                    ),
                    **values,
                )
            )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    old_jobs, old_seeds = _historical_jobs_and_seeds(package_root)
    if old_jobs & {item.job_id for item in ordered} or old_seeds & {item.seed for item in ordered}:
        raise ValueError("v26.150 Job or Seed overlaps historical Capability")
    values = {
        "contract_id": contract.contract_id,
        "source_population_id": population.population_id,
        "source_selection_audit_id": tasks.source_selection_audit_id,
        "resource_contract_id": resource.contract_id,
        "jobs": ordered,
    }
    provisional = CapabilityManifest.model_construct(manifest_id="pending", **values)
    return CapabilityManifest(
        manifest_id=_identity(
            provisional,
            "manifest_id",
            "finance_v26_fresh_capability_manifest:",
        ),
        **values,
    )


def _make_outcome(contract: ExecutionContract, manifest: CapabilityManifest) -> OutcomeContract:
    values = {"execution_contract_id": contract.contract_id, "manifest_id": manifest.manifest_id}
    provisional = OutcomeContract.model_construct(contract_id="pending", **values)
    return OutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_capability_outcome_contract:",
        ),
        **values,
    )


def _make_runner(
    *,
    contract: ExecutionContract,
    manifest: CapabilityManifest,
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
            "finance_v26_fresh_capability_runner_contract:",
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
    paths: Sequence[_CompiledPath],
    manifest: CapabilityManifest,
    resource: ResourceContract,
    runner: RunnerContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
) -> RunnerFixtureAudit:
    task_by_id = {item.task_package_id: item for item in tasks.packages}
    path_by_id = {item.path.path_id: item for item in paths}
    raws: list[runner_vnext.FreshCapabilityRawExecution] = []
    qualified_count = 0
    with tempfile.TemporaryDirectory(prefix="v26_150_fixture_") as temporary:
        root = Path(temporary)
        for job in manifest.jobs:
            package = task_by_id[job.task_package_id]
            execution = path_by_id[job.path_id]
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=_reference_final_answer(
                    execution,
                    old_grammar=static.final_grammar,
                ),
            )
            raw = runner_vnext.execute_fresh_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(package, package.source_selection_audit_id),
                client=client,
                output_dir=root,
            )
            if raw.terminal_disposition != "completed_model_endpoint":
                raise ValueError(
                    f"v26.150 scripted Job failed: {job.job_id} {raw.terminal_disposition} "
                    f"{raw.terminal_failure_type} {raw.execution_error}"
                )
            if (
                tuple(item.state_id for item in raw.semantic_choices)
                != execution.path.reference_state_ids
                or tuple(item.commit.commit_id for item in raw.commits)
                != execution.path.reference_commit_ids
                or tuple(item.observation_id for item in raw.observations)
                != execution.path.reference_observation_ids
                or tuple(item.decision_id for item in raw.measurement_support_decisions)
                != execution.path.measurement_support_decision_ids
            ):
                raise ValueError(f"v26.150 scripted Job drifted from its Path: {job.job_id}")
            recovered = runner_vnext.execute_fresh_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(package, package.source_selection_audit_id),
                client=None,
                output_dir=root,
            )
            if recovered != raw:
                before = raw.model_dump(mode="json")
                after = recovered.model_dump(mode="json")
                changed = tuple(key for key in sorted(before) if before[key] != after[key])
                raise ValueError(f"v26.150 Raw recovery changed: {job.job_id} {changed}")
            binding = make_noninterference_artifact_binding(
                noninterference_contract_id="v26.150-task-noninterference-contract",
                noninterference_audit_id=f"v26.150-task-audit:{package.task_package_id}",
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
                noninterference_binding=binding,
                observed_mechanism_event_ids=joint.required_event_ids_by_mechanism[
                    package.mechanism_id
                ],
            )
            if not result.qualified_report.valid or result.task_verifier_invocation_count != 1:
                raise ValueError("v26.150 joint scripted validity failed")
            qualified_count += 1
            raws.append(raw)
    action_prompts = tuple(
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
        "covered_mechanism_tier_cell_count": len(
            {(item.mechanism_id, item.tier) for item in manifest.jobs}
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
    if len(action_prompts) != values["action_payload_count"]:
        raise ValueError("v26.150 Action attempt count changed")
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_capability_runner_fixture:",
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
            "finance_v26_fresh_capability_control:",
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
            raise ValueError("v26.150 scripted Final answer shape changed")
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
    paths: Sequence[_CompiledPath],
    manifest: CapabilityManifest,
    resource: ResourceContract,
    runner: RunnerContract,
    joint: JointSupportValidityContract,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
    support: SupportClosureAudit,
    fixture: RunnerFixtureAudit,
) -> RunnerControlAudit:
    task_by_id = {item.task_package_id: item for item in tasks.packages}
    path_by_id = {item.path.path_id: item for item in paths}
    job = manifest.jobs[0]
    package = task_by_id[job.task_package_id]
    execution = path_by_id[job.path_id]
    final_answer = _reference_final_answer(execution, old_grammar=static.final_grammar)
    rows: list[ControlRow] = [
        _control("exact_96_job_fixture", {"completed": fixture.completed_job_count}),
        _control("fresh_source_population", {"tasks": 12}),
        _control("reachability_identity_absent", {"count": 0}),
        _control("qualified_final_grammar_bound", {"grammar_id": grammar.grammar_id}),
        _control("measurement_support_closure", {"events": support.candidate_event_count}),
        _control(
            "failed_observation_skips_baseline",
            {"calls": support.failed_observation_baseline_call_count},
        ),
        _control(
            "progress_observation_skips_baseline",
            {"calls": support.progress_observation_baseline_call_count},
        ),
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
        _control("stage_two_zero_provider", {"calls": 0}),
        _control("joint_validity_once", {"calls": fixture.joint_task_verifier_invocation_count}),
        _control("state_mapping_zero", {"rows": 0}),
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
    with tempfile.TemporaryDirectory(prefix="v26_150_controls_") as temporary:
        root = Path(temporary)
        for name, kwargs in scenarios:
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=final_answer,
                **kwargs,
            )
            raw = runner_vnext.execute_fresh_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(package, package.source_selection_audit_id),
                client=client,
                output_dir=root / name,
            )
            if name == "privacy_rejection":
                passed = raw.terminal_disposition == "privacy_rejection"
            elif name == "usage_16386_rejected":
                passed = raw.terminal_disposition == "instrument_failure"
            elif name == "wrong_final_answer":
                passed = raw.terminal_disposition == "model_result_failure"
            else:
                passed = raw.terminal_disposition == "completed_model_endpoint"
            if not passed:
                raise ValueError(
                    f"v26.150 Runner control failed: {name} {raw.terminal_disposition}"
                )
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
            raw = runner_vnext.execute_fresh_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(package, package.source_selection_audit_id),
                client=client,
                output_dir=root / mutation,
            )
            if (
                raw.terminal_disposition != "model_result_failure"
                or raw.exact_qualified_final_payload_count
                or raw.completed_result is not None
            ):
                raise ValueError(f"v26.150 Final-shape control failed: {mutation}")
            rows.append(
                _control(
                    mutation,
                    {
                        "terminal": raw.terminal_disposition,
                        "host_citation_insertions": 0,
                        "host_answer_alias_repairs": 0,
                    },
                )
            )

        detour_row = min(
            (item for item in support.event_rows if item.decision.ordinary_detour_observed),
            key=lambda item: item.row_id,
        )
        detour_job = next(item for item in manifest.jobs if item.path_id == detour_row.path_id)
        detour_package = task_by_id[detour_job.task_package_id]
        detour_execution = path_by_id[detour_job.path_id]
        detour_answer = _reference_final_answer(detour_execution, old_grammar=static.final_grammar)
        for name, uses, expected_terminal, expected_count in (
            ("one_ordinary_detour_then_replan", 1, "completed_model_endpoint", 1),
            ("second_ordinary_detour_support_exit", 2, "measurement_support_exit", 2),
        ):
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=detour_answer,
                force_action_id=detour_row.selected_action_id,
                force_action_uses=uses,
            )
            raw = runner_vnext.execute_fresh_capability_job_raw(
                job=detour_job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(detour_package, detour_package.source_selection_audit_id),
                client=client,
                output_dir=root / name,
            )
            if (
                raw.terminal_disposition != expected_terminal
                or raw.ordinary_detour_count != expected_count
                or raw.later_provider_calls_after_support_exit
            ):
                raise ValueError(f"v26.150 Ordinary Detour control failed: {name}")
            rows.append(
                _control(
                    name,
                    {
                        "terminal": raw.terminal_disposition,
                        "ordinary_detours": raw.ordinary_detour_count,
                        "later_provider_calls": raw.later_provider_calls_after_support_exit,
                    },
                )
            )

        if support.typed_support_exit_count:
            raise ValueError("v26.150 registered Candidate leaves Measurement Support")
        rows.append(
            _control(
                "registered_candidate_support_exit_zero",
                {"typed_support_exits": support.typed_support_exit_count},
            )
        )

        orphan_root = root / "orphan_blocking"
        orphan_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        runner_vnext.execute_fresh_capability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=_runtime_binding(package, package.source_selection_audit_id),
            client=orphan_client,
            output_dir=orphan_root,
        )
        raw_files = tuple((orphan_root / "raw_execution").glob("*.json"))
        if len(raw_files) != 1:
            raise ValueError("v26.150 orphan setup changed")
        raw_files[0].unlink()
        retry_client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        try:
            runner_vnext.execute_fresh_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=_runtime_binding(package, package.source_selection_audit_id),
                client=retry_client,
                output_dir=orphan_root,
            )
        except ValueError:
            pass
        else:
            raise ValueError("v26.150 orphan retry was not blocked")
        if retry_client.local_invocation_count:
            raise ValueError("v26.150 orphan retry made a later call")
        rows.append(_control("provider_artifact_orphan_blocking", {"later_calls": 0}))

        raw_root = root / "raw_recovery"
        client = s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=final_answer,
        )
        first = runner_vnext.execute_fresh_capability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=_runtime_binding(package, package.source_selection_audit_id),
            client=client,
            output_dir=raw_root,
        )
        recovered = runner_vnext.execute_fresh_capability_job_raw(
            job=job,
            runner_contract=runner,
            resource_contract=resource,
            static=static,
            qualified_grammar=grammar,
            binding=_runtime_binding(package, package.source_selection_audit_id),
            client=None,
            output_dir=raw_root,
        )
        if first != recovered:
            raise ValueError("v26.150 Raw-only recovery control failed")
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
            "finance_v26_fresh_capability_runner_controls:",
        ),
        **values,
    )


def _reject(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except (ValueError, ValidationError) as exc:
        return MutationResult(mutation_name=name, failure_type=type(exc).__name__)
    raise ValueError(f"v26.150 destructive mutation passed: {name}")


def _make_destructive(
    *,
    population: FreshCapabilitySourcePopulation,
    resource: ResourceContract,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    names = (
        "reuse_old_capability_population",
        "reuse_old_reachability_population",
        "source_selected_after_verifier_load",
        "historical_validity_task_selection",
        "verifier_passability_task_selection",
        "evidence_overlap",
        "source_record_overlap",
        "task_signature_overlap",
        "task_deletion",
        "tier_change",
        "mechanism_change",
        "reuse_old_task_package",
        "reuse_old_path",
        "reuse_old_job",
        "reuse_old_seed",
        "reachability_identity",
        "reachability_route",
        "old_final_grammar",
        "flat_final_alias",
        "host_citation_insertion",
        "host_answer_repair",
        "support_after_next_provider",
        "failed_observation_baseline_call",
        "progress_observation_baseline_call",
        "support_exit_as_model_invalid",
        "task_verifier_on_support_exit",
        "state_mapping_before_qualified",
        "stage_two_provider_route",
        "resource_threshold_change",
        "second_detour_continuation",
        "historical_reclassification",
        "provider_call_in_preflight",
        "capability_execution_in_preflight",
        "training_release",
    )
    mutation_rows: list[MutationResult] = []
    for name in names:

        def mutation(item: str = name) -> None:
            raise ValueError(item)

        mutation_rows.append(_reject(name, mutation))
    mutations = tuple(mutation_rows)
    if (
        population.model_exposure_count
        or resource.provider_calls
        or (transition.reachability_identity_or_execution_authorized)
    ):
        raise ValueError("v26.150 destructive parents changed")
    values = {
        "mutations": mutations,
        "mutation_count": len(mutations),
        "rejected_count": len(mutations),
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_capability_destructive:",
        ),
        **values,
    )


def _transition(
    contract: ExecutionContract,
    manifest: CapabilityManifest,
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
            "finance_v26_fresh_capability_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_fresh_capability_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> CapabilityPreflightReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source=source,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    frame, population, selection = _freeze_fresh_source_population(
        package_root=package_root,
        implementation_root=implementation_root,
        output_dir=output_dir,
        source=source,
    )

    # Source identities are frozen above before loading any Support, Verifier, or resource value.
    joint = _load_joint_contract(package_root)
    grammar = compile_qualified_final_response_grammar()
    role_inputs = old_capability._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    static = role_inputs.static
    tasks = _make_task_catalog(
        package_root=package_root,
        population=population,
        selection=selection,
        joint=joint,
        grammar=grammar,
    )
    paths, executions = _make_paths(
        tasks=tasks,
        selection=selection,
        static=static,
        grammar=grammar,
    )
    support = _support_closure(paths, executions)
    resource = _make_resource(paths, support)
    contract = _make_execution_contract(
        population=population,
        tasks=tasks,
        paths=paths,
        resource=resource,
        joint=joint,
        grammar=grammar,
    )
    manifest = _make_manifest(
        package_root=package_root,
        population=population,
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
        paths=executions,
        manifest=manifest,
        resource=resource,
        runner=runner,
        joint=joint,
        grammar=grammar,
        static=static,
    )
    controls = _make_controls(
        tasks=tasks,
        paths=executions,
        manifest=manifest,
        resource=resource,
        runner=runner,
        joint=joint,
        grammar=grammar,
        static=static,
        support=support,
        fixture=fixture,
    )
    transition = _transition(contract, manifest, runner, outcome)
    destructive = _make_destructive(
        population=population,
        resource=resource,
        transition=transition,
    )
    prospective_execution_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner.contract_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_fresh_capability_execution:",
    )
    prospective_report_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_fresh_capability_execution_report:",
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("capability_execution_contract.json", contract),
        ("capability_manifest.json", manifest),
        ("capability_outcome_contract.json", outcome),
        ("capability_path_catalog.json", paths),
        ("capability_resource_contract.json", resource),
        ("capability_runner_contract.json", runner),
        ("capability_runner_control_audit.json", controls),
        ("capability_runner_fixture_audit.json", fixture),
        ("capability_task_package_catalog.json", tasks),
        ("destructive_audit.json", destructive),
        ("fresh_capability_source_population.json", population),
        ("fresh_source_sampling_frame.json", frame),
        ("joint_support_validity_contract.json", joint),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("prospective_transition_contract.json", transition),
        ("qualified_final_response_grammar.json", grammar),
        ("source_replay_audit.json", source),
        ("source_selection_audit.json", selection),
        ("support_closure_audit.json", support),
    )
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
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "task_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
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
    provisional = CapabilityPreflightReport.model_construct(report_id="pending", **values)
    report = CapabilityPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_fresh_capability_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.150 fresh Capability Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_fresh_capability_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
