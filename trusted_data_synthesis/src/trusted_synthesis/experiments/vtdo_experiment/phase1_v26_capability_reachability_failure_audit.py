from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import StaticModelAuthorityPathCatalog
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_postrun_audit import (  # noqa: E501
    AuthorityPreservingRolePostrunAuditReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_runner import (  # noqa: E501
    AuthorityPreservingRoleReport,
    EmpiricalRole,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    EmpiricalPilotRollout,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_result,
    public_operation_progress,
    public_operation_step_rejection,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
)

V26_FAILURE_AUDIT_VERSION = "finance_v26_capability_reachability_failure_audit.v1"
V26_CAPABILITY_FAILURE_DIAGNOSTIC_VERSION = "finance_v26_capability_failure_diagnostic.v1"
V26_CAPABILITY_CONVERSION_VERSION = "finance_v26_capability_conversion_summary.v1"
V26_STOPPING_CONTRAST_VERSION = "finance_v26_stopping_role_contrast.v1"
V26_VALID_MAPPING_DIAGNOSTIC_VERSION = "finance_v26_valid_mapping_diagnostic.v1"
V26_ROUTE_SUMMARY_VERSION = "finance_v26_reachability_route_summary.v1"
V26_STATE_SUPPORT_DIAGNOSTIC_VERSION = "finance_v26_state_support_diagnostic.v1"
V26_REPLAY_DIFFERENTIAL_VERSION = "finance_v26_verifier_replay_differential.v1"

_MECHANISMS = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
_PATH_STRATEGIES: tuple[PathStrategy, ...] = (
    "structured_direct",
    "search_then_structured",
    "search_then_open",
)
_IMPLEMENTATION_SOURCE_PATHS = (
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_capability_reachability_failure_audit.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_role_postrun_audit.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_role_runner.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)
_ACTION_BINDING_FIELDS = frozenset(
    {
        "available_resolution_actions",
        "correct_operator",
        "correct_parameters",
        "correct_tool_id",
        "expected_arguments",
        "operator",
        "parameters",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "suggested_argument_patch",
    }
)

ObservedCheckStatus = Literal["passed", "failed", "not_evaluated"]
CapabilityScope = Literal[
    "all_mechanisms",
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BoundFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ImplementationSource(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class ConditionalRate(FrozenModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    exact_fraction: str | None
    value: float | None

    @model_validator(mode="after")
    def validate_rate(self) -> ConditionalRate:
        if self.numerator > self.denominator:
            raise ValueError("conditional-rate numerator exceeds denominator")
        if self.denominator == 0:
            if self.exact_fraction is not None or self.value is not None:
                raise ValueError("zero-denominator conditional rate must remain undefined")
        else:
            expected = self.numerator / self.denominator
            if self.exact_fraction != f"{self.numerator}/{self.denominator}":
                raise ValueError("conditional-rate fraction is inconsistent")
            if self.value != expected:
                raise ValueError("conditional-rate value is inconsistent")
        return self


class CapabilityFailureDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    replicate_index: int = Field(ge=0, le=7)
    target_mechanism_occurred: bool
    completed_node_count: int = Field(ge=0)
    required_node_count: int = Field(ge=1)
    full_program_lineage_completed: bool
    terminal_operation_completed: bool
    exact_postterminal_verification_completed: bool
    independent_verifier_evaluated: bool
    evidence_support_status: ObservedCheckStatus
    answer_projection_status: ObservedCheckStatus
    failed_verifier_check_ids: tuple[str, ...]
    earliest_failure_stage: str = Field(min_length=1)
    failure_category: str = Field(min_length=1)
    failure_reason_family: str = Field(min_length=1)
    raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    historical_independent_validity: Literal[False] = False
    historical_outcome_rescored: Literal[False] = False
    schema_version: str = V26_CAPABILITY_FAILURE_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> CapabilityFailureDiagnostic:
        if self.independent_verifier_evaluated != (
            self.evidence_support_status != "not_evaluated"
            and self.answer_projection_status != "not_evaluated"
        ):
            raise ValueError("Capability verifier observability is inconsistent")
        if self.full_program_lineage_completed != (
            self.completed_node_count == self.required_node_count
        ):
            raise ValueError("Capability Program-closure count is inconsistent")
        if self.diagnostic_id != capability_failure_diagnostic_id(self):
            raise ValueError("Capability failure diagnostic identity is invalid")
        return self


class CapabilityConversionSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    scope: CapabilityScope
    rollout_count: Literal[24, 96]
    invalid_count: int = Field(ge=0)
    mechanism_success_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)
    valid_and_mechanism_success_count: int = Field(ge=0)
    valid_given_mechanism_success: ConditionalRate
    mechanism_success_given_valid: ConditionalRate
    local_success_invalid_count: int = Field(ge=0)
    local_success_program_closed_count: int = Field(ge=0)
    local_success_postterminal_verified_count: int = Field(ge=0)
    local_success_verifier_evaluated_count: int = Field(ge=0)
    invalid_earliest_failure_stage_counts: dict[str, int]
    local_success_failure_reason_counts: dict[str, int]
    evidence_support_status_counts: dict[ObservedCheckStatus, int]
    answer_projection_status_counts: dict[ObservedCheckStatus, int]
    diagnostic_only: Literal[True] = True
    creates_capability_support: Literal[False] = False
    schema_version: str = V26_CAPABILITY_CONVERSION_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> CapabilityConversionSummary:
        if self.invalid_count + self.independently_valid_count != self.rollout_count:
            raise ValueError("Capability conversion denominator is incomplete")
        if self.local_success_invalid_count != (
            self.mechanism_success_count - self.valid_and_mechanism_success_count
        ):
            raise ValueError("Capability local-success conversion count is inconsistent")
        if sum(self.invalid_earliest_failure_stage_counts.values()) != self.invalid_count:
            raise ValueError("Capability invalid failure-stage denominator is incomplete")
        if sum(self.evidence_support_status_counts.values()) != self.rollout_count:
            raise ValueError("Capability Evidence-status denominator is incomplete")
        if sum(self.answer_projection_status_counts.values()) != self.rollout_count:
            raise ValueError("Capability Answer-status denominator is incomplete")
        if self.summary_id != capability_conversion_summary_id(self):
            raise ValueError("Capability conversion identity is invalid")
        return self


class StoppingTaskProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    role: EmpiricalRole
    task_package_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    structural_signature: str = Field(min_length=1)
    required_node_count: int = Field(ge=1)
    public_variable_count: int = Field(ge=1)
    necessary_evidence_count: int = Field(ge=1)
    sufficient_support_set_size_range: tuple[int, int]
    operation_node_kind_counts: dict[str, int]
    allowed_tool_ids: tuple[str, ...]
    answer_field_ids: tuple[str, ...]
    rollout_count: int = Field(ge=1)
    sampling_mode_counts: dict[str, int]
    local_mechanism_success_count: int = Field(ge=0)
    full_program_lineage_count: int = Field(ge=0)
    postterminal_verification_count: int = Field(ge=0)
    verifier_evaluated_count: int = Field(ge=0)
    frozen_runtime_replay_failure_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_profile(self) -> StoppingTaskProfile:
        if sum(self.sampling_mode_counts.values()) != self.rollout_count:
            raise ValueError("Stopping task empirical denominator is incomplete")
        if self.profile_id != stopping_task_profile_id(self):
            raise ValueError("Stopping task profile identity is invalid")
        return self


class StoppingRoleSummary(FrozenModel):
    role: EmpiricalRole
    task_count: Literal[3] = 3
    rollout_count: Literal[24, 90]
    sampling_mode_counts: dict[str, int]
    local_mechanism_success_count: int = Field(ge=0)
    full_program_lineage_count: int = Field(ge=0)
    postterminal_verification_count: int = Field(ge=0)
    verifier_evaluated_count: int = Field(ge=0)
    frozen_runtime_replay_failure_count: int = Field(ge=0)
    sole_runtime_replay_blocker_count: int = Field(ge=0)
    independently_valid_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_summary(self) -> StoppingRoleSummary:
        if sum(self.sampling_mode_counts.values()) != self.rollout_count:
            raise ValueError("Stopping role empirical denominator is incomplete")
        return self


class StoppingRoleContrast(FrozenModel):
    contrast_id: str = Field(min_length=1)
    capability: StoppingRoleSummary
    reachability: StoppingRoleSummary
    task_profiles: tuple[StoppingTaskProfile, ...] = Field(min_length=6, max_length=6)
    shared_task_package_count: Literal[0] = 0
    shared_semantic_source_count: Literal[0] = 0
    shared_structural_signature_count: int = Field(ge=0, le=3)
    observed_validity_count_difference: int
    capability_zero_valid_interpretation_blocked_by_verifier_gap: bool
    role_population_and_condition_are_confounding: Literal[True] = True
    causal_task_structure_attribution_supported: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    conclusion: str = Field(min_length=1)
    schema_version: str = V26_STOPPING_CONTRAST_VERSION

    @model_validator(mode="after")
    def validate_contrast(self) -> StoppingRoleContrast:
        if self.observed_validity_count_difference != (
            self.reachability.independently_valid_count - self.capability.independently_valid_count
        ):
            raise ValueError("Stopping validity contrast is inconsistent")
        if self.contrast_id != stopping_role_contrast_id(self):
            raise ValueError("Stopping role contrast identity is invalid")
        return self


class ValidMappingDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    requested_static_path_id: str | None
    requested_path_strategy: PathStrategy | None
    requested_quotient_state_id: str | None
    actual_static_path_id: str = Field(min_length=1)
    actual_path_strategy: PathStrategy
    actual_quotient_state_id: str = Field(min_length=1)
    successful_precalculation_tool_ids: tuple[str, ...]
    route_adherent: bool | None
    on_target: bool | None
    off_target_mapper_dimensions: tuple[str, ...]
    decision_trace_hash: str = Field(min_length=1)
    trajectory_content_hash: str = Field(min_length=1)
    duplicate_decision_trace_within_actual_state: bool
    duplicate_content_within_actual_state: bool
    released_realization: bool
    historical_mapping_retained: Literal[True] = True
    schema_version: str = V26_VALID_MAPPING_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> ValidMappingDiagnostic:
        conditioned = self.sampling_mode == "reachability_conditioned"
        requested = (
            self.requested_static_path_id,
            self.requested_path_strategy,
            self.requested_quotient_state_id,
        )
        if conditioned != all(item is not None for item in requested):
            raise ValueError("valid mapping loses conditioned target identity")
        if conditioned != (self.route_adherent is not None and self.on_target is not None):
            raise ValueError("valid mapping target comparison is inconsistent")
        if self.on_target is True and self.off_target_mapper_dimensions:
            raise ValueError("On-target mapping has Off-target dimensions")
        if self.diagnostic_id != valid_mapping_diagnostic_id(self):
            raise ValueError("valid mapping diagnostic identity is invalid")
        return self


class ReachabilityRouteSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    requested_path_strategy: PathStrategy
    attempt_count: Literal[72] = 72
    observed_path_strategy_counts: dict[str, int]
    adherence_count: int = Field(ge=0, le=72)
    independently_valid_count: int = Field(ge=0, le=72)
    valid_actual_path_strategy_counts: dict[str, int]
    on_target_valid_count: int = Field(ge=0, le=72)
    off_target_valid_count: int = Field(ge=0, le=72)
    valid_unmapped_count: Literal[0] = 0
    route_condition_control_established: bool
    diagnostic_only: Literal[True] = True
    creates_state_support: Literal[False] = False
    schema_version: str = V26_ROUTE_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> ReachabilityRouteSummary:
        if sum(self.observed_path_strategy_counts.values()) != self.attempt_count:
            raise ValueError("Reachability route denominator is incomplete")
        if sum(self.valid_actual_path_strategy_counts.values()) != self.independently_valid_count:
            raise ValueError("Reachability valid-route denominator is incomplete")
        if (
            self.on_target_valid_count + self.off_target_valid_count + self.valid_unmapped_count
            != self.independently_valid_count
        ):
            raise ValueError("Reachability valid target denominator is incomplete")
        if self.summary_id != reachability_route_summary_id(self):
            raise ValueError("Reachability route summary identity is invalid")
        return self


class StateSupportDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    static_path_id: str = Field(min_length=1)
    path_strategy: PathStrategy
    quotient_state_id: str = Field(min_length=1)
    natural_hit_rollout_ids: tuple[str, ...]
    conditioned_on_target_rollout_ids: tuple[str, ...]
    released_rollout_ids: tuple[str, ...]
    natural_hit_count: int = Field(ge=0)
    conditioned_on_target_count: int = Field(ge=0)
    released_count: int = Field(ge=0)
    released_unique_content_count: int = Field(ge=0)
    released_unique_decision_trace_count: int = Field(ge=0)
    minimum_release_requirement: Literal[3] = 3
    release_shortfall: int = Field(ge=0, le=3)
    blockers: tuple[str, ...]
    admitted: Literal[False] = False
    historical_freeze_retained: Literal[True] = True
    schema_version: str = V26_STATE_SUPPORT_DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> StateSupportDiagnostic:
        if self.natural_hit_count != len(self.natural_hit_rollout_ids):
            raise ValueError("natural-hit rollout identity count is inconsistent")
        if self.conditioned_on_target_count != len(self.conditioned_on_target_rollout_ids):
            raise ValueError("conditioned On-target rollout identity count is inconsistent")
        if self.released_count != len(self.released_rollout_ids):
            raise ValueError("released rollout identity count is inconsistent")
        if self.release_shortfall != max(0, self.minimum_release_requirement - self.released_count):
            raise ValueError("released-realization shortfall is inconsistent")
        if self.diagnostic_id != state_support_diagnostic_id(self):
            raise ValueError("state-support diagnostic identity is invalid")
        return self


class VerifierReplayDifferential(FrozenModel):
    differential_id: str = Field(min_length=1)
    role: EmpiricalRole
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    frozen_failed_check_ids: tuple[str, ...]
    frozen_replay_failure_ids: tuple[str, ...]
    replay_mismatch_observation_indices: tuple[int, ...]
    mismatch_error_code_counts: dict[str, int]
    mismatch_tool_counts: dict[str, int]
    failed_mismatch_observations_action_neutral: bool
    authority_aligned_replay_passed: bool
    authority_aligned_replay_failure_ids: tuple[str, ...]
    runtime_replay_is_sole_frozen_blocker: bool
    prospective_repair_signal: bool
    historical_validity_reclassified: Literal[False] = False
    historical_state_mapping_created: Literal[False] = False
    schema_version: str = V26_REPLAY_DIFFERENTIAL_VERSION

    @model_validator(mode="after")
    def validate_differential(self) -> VerifierReplayDifferential:
        if "runtime_replay_passed" not in self.frozen_failed_check_ids:
            raise ValueError("Verifier differential lacks a frozen replay failure")
        if self.prospective_repair_signal != (
            bool(self.frozen_replay_failure_ids) and self.authority_aligned_replay_passed
        ):
            raise ValueError("Verifier prospective-repair signal is inconsistent")
        if self.differential_id != verifier_replay_differential_id(self):
            raise ValueError("Verifier replay differential identity is invalid")
        return self


class CapabilityReachabilityFailureAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    capability_source_report_id: str = Field(min_length=1)
    capability_source_report_sha256: str = Field(min_length=64, max_length=64)
    reachability_source_report_id: str = Field(min_length=1)
    reachability_source_report_sha256: str = Field(min_length=64, max_length=64)
    source_postrun_audit_report_id: str = Field(min_length=1)
    source_postrun_audit_report_sha256: str = Field(min_length=64, max_length=64)
    raw_artifact_replay_pass_count: Literal[456] = 456
    raw_artifact_count: Literal[456] = 456
    capability_rollout_count: Literal[96] = 96
    capability_invalid_count: Literal[92] = 92
    capability_independently_valid_count: Literal[4] = 4
    capability_mechanism_success_count: Literal[30] = 30
    reachability_rollout_count: Literal[360] = 360
    reachability_independently_valid_count: Literal[21] = 21
    reachability_mapped_valid_count: Literal[21] = 21
    natural_state_hit_count: Literal[5] = 5
    conditioned_on_target_count: Literal[2] = 2
    released_realization_count: Literal[2] = 2
    admitted_state_count: Literal[0] = 0
    admitted_task_count: Literal[0] = 0
    frozen_runtime_replay_failure_count: Literal[18] = 18
    authority_aligned_replay_pass_count: Literal[18] = 18
    sole_runtime_replay_blocker_count: Literal[15] = 15
    verifier_replay_contract_gap_observed: Literal[True] = True
    historical_capability_results_reclassified: Literal[False] = False
    historical_reachability_results_reclassified: Literal[False] = False
    historical_state_support_freeze_mutated: Literal[False] = False
    empirical_state_support_admitted: Literal[False] = False
    capability_confirmation_authorized: Literal[False] = False
    state_support_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["authority_preserving_verifier_replay_repair_only"] = (
        "authority_preserving_verifier_replay_repair_only"
    )
    source_artifact_files: tuple[BoundFile, ...] = Field(min_length=10)
    immutable_detail_files: tuple[BoundFile, ...] = Field(min_length=7, max_length=7)
    implementation_source_files: tuple[ImplementationSource, ...] = Field(
        min_length=6, max_length=6
    )
    api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    status: Literal["verifier_replay_contract_gap_observed"] = (
        "verifier_replay_contract_gap_observed"
    )
    schema_version: str = V26_FAILURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityReachabilityFailureAuditReport:
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(_IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("failure-audit implementation manifest is incomplete")
        expected_details = (
            "capability_conversion_summaries.json",
            "capability_failure_diagnostics.json",
            "reachability_route_summaries.json",
            "reachability_valid_mapping_diagnostics.json",
            "state_support_diagnostics.json",
            "stopping_role_contrast.json",
            "verifier_replay_differentials.json",
        )
        if tuple(item.relative_path for item in self.immutable_detail_files) != expected_details:
            raise ValueError("failure-audit detail manifest is incomplete")
        if self.report_id != capability_reachability_failure_audit_report_id(self):
            raise ValueError("Capability/Reachability failure-audit identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"failure-audit immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _rate(numerator: int, denominator: int) -> ConditionalRate:
    return ConditionalRate(
        numerator=numerator,
        denominator=denominator,
        exact_fraction=f"{numerator}/{denominator}" if denominator else None,
        value=numerator / denominator if denominator else None,
    )


def _bound_file(path: Path, package_root: Path, *, record_count: int | None = None) -> BoundFile:
    return BoundFile(
        relative_path=str(path.relative_to(package_root)),
        sha256=_sha256(path),
        record_count=_record_count(path) if record_count is None else record_count,
    )


def _detail_file(path: Path, output_dir: Path, record_count: int) -> BoundFile:
    return BoundFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=record_count,
    )


def _implementation_sources(package_root: Path) -> tuple[ImplementationSource, ...]:
    return tuple(
        ImplementationSource(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(_IMPLEMENTATION_SOURCE_PATHS)
    )


def _load_raw_payload(rollout: EmpiricalPilotRollout, run_dir: Path) -> dict[str, Any]:
    path = Path(rollout.raw_artifact_uri).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError as error:
        raise ValueError("failure-audit raw Artifact is outside its frozen run") from error
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rollout.raw_artifact_sha256:
        raise ValueError("failure-audit raw Artifact hash replay failed")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("failure-audit raw Artifact is not a JSON object")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("failure-audit raw Artifact is not canonical JSON")
    return cast(dict[str, Any], payload)


def _parse_observations(payload: Mapping[str, Any]) -> tuple[AgentToolObservation, ...]:
    failure = payload.get("failure_artifact")
    if isinstance(failure, Mapping):
        return tuple(
            AgentToolObservation.model_validate(item) for item in failure.get("observations") or ()
        )
    trajectory = payload.get("trajectory")
    if not isinstance(trajectory, Mapping):
        return ()
    output = []
    for step in trajectory.get("steps") or ():
        observation = step.get("observation") if isinstance(step, Mapping) else None
        if isinstance(observation, Mapping) and "observation_id" in observation:
            output.append(AgentToolObservation.model_validate(observation))
    return tuple(output)


def _contains_action_binding(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _ACTION_BINDING_FIELDS & set(value):
            return True
        return any(_contains_action_binding(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_action_binding(item) for item in value)
    return False


def _check_status(rollout: EmpiricalPilotRollout, check_id: str) -> ObservedCheckStatus:
    if rollout.verification is None:
        return "not_evaluated"
    return "passed" if rollout.verification.checks[check_id] else "failed"


def _failure_reason_family(rollout: EmpiricalPilotRollout) -> str:
    if rollout.verification is not None:
        return f"independent_verification:{rollout.verification.earliest_failure_stage}"
    attribution = rollout.failure_attribution or {}
    reason = str(attribution.get("reason") or "")
    patterns = (
        ("selected an unavailable tool", "unavailable_tool"),
        ("exceeded the frozen failed-tool budget", "failed_tool_budget"),
        ("exceeded the frozen model-token budget", "model_token_budget"),
        ("exhausted the frozen tool-call budget", "tool_call_budget"),
        ("exceeded the frozen stop-rejection budget", "stop_rejection_budget"),
        ("invalid JSON", "model_json_contract"),
    )
    for marker, family in patterns:
        if marker in reason:
            return family
    category = str(attribution.get("category") or "model_contract_failure")
    return category


def _failure_stage(rollout: EmpiricalPilotRollout) -> str:
    if rollout.verification is not None:
        return rollout.verification.earliest_failure_stage or "independent_verification"
    return "model_contract"


def _progress(
    record: OperationalTaskRecord,
    observations: Sequence[AgentToolObservation],
) -> Mapping[str, Any]:
    progress = public_operation_progress(record.task_package.task.public, tuple(observations))
    if progress is None:
        raise ValueError("failure audit lost the public Operation contract")
    return progress


def _capability_failure_diagnostics(
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[CapabilityFailureDiagnostic, ...]:
    output = []
    for rollout in rollouts:
        if rollout.terminal_category == "model_valid_trajectory":
            continue
        record = records[rollout.task_record_id]
        observations = _parse_observations(payloads[rollout.rollout_id])
        progress = _progress(record, observations)
        verification = rollout.verification
        failed_checks = tuple(
            sorted(
                key
                for key, passed in (verification.checks.items() if verification else ())
                if not passed
            )
        )
        values: dict[str, Any] = {
            "rollout_id": rollout.rollout_id,
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "replicate_index": rollout.replicate_index,
            "target_mechanism_occurred": rollout.mechanism_estimand.success,
            "completed_node_count": len(progress["completed_node_ids"]),
            "required_node_count": len(
                record.task_package.stop_readiness_contract.required_node_ids
            ),
            "full_program_lineage_completed": bool(progress["all_steps_completed"]),
            "terminal_operation_completed": bool(progress["terminal_node_completed"]),
            "exact_postterminal_verification_completed": bool(
                progress["verification_after_terminal_completed"]
            ),
            "independent_verifier_evaluated": verification is not None,
            "evidence_support_status": _check_status(rollout, "evidence_support_complete"),
            "answer_projection_status": _check_status(rollout, "answer_projection_complete"),
            "failed_verifier_check_ids": failed_checks,
            "earliest_failure_stage": _failure_stage(rollout),
            "failure_category": str(
                (rollout.failure_attribution or {}).get("category") or "model_contract_failure"
            ),
            "failure_reason_family": _failure_reason_family(rollout),
            "raw_artifact_sha256": rollout.raw_artifact_sha256,
        }
        provisional = CapabilityFailureDiagnostic.model_construct(diagnostic_id="pending", **values)
        output.append(
            CapabilityFailureDiagnostic(
                diagnostic_id=capability_failure_diagnostic_id(provisional), **values
            )
        )
    if len(output) != 92:
        raise ValueError("Capability failure audit lost the frozen 92-row denominator")
    return tuple(sorted(output, key=lambda item: item.diagnostic_id))


def _capability_conversion_summaries(
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[CapabilityConversionSummary, ...]:
    scopes: tuple[CapabilityScope, ...] = ("all_mechanisms", *_MECHANISMS)  # type: ignore[assignment]
    output = []
    for scope in scopes:
        rows = tuple(
            item for item in rollouts if scope == "all_mechanisms" or item.mechanism_id == scope
        )
        diagnostics = {
            item.rollout_id: _progress(
                records[item.task_record_id],
                _parse_observations(payloads[item.rollout_id]),
            )
            for item in rows
        }
        valid = tuple(item for item in rows if item.terminal_category == "model_valid_trajectory")
        local = tuple(item for item in rows if item.mechanism_estimand.success)
        joint = tuple(
            item
            for item in rows
            if item.mechanism_estimand.success
            and item.terminal_category == "model_valid_trajectory"
        )
        invalid = tuple(item for item in rows if item.terminal_category != "model_valid_trajectory")
        local_invalid = tuple(
            item
            for item in rows
            if item.mechanism_estimand.success
            and item.terminal_category != "model_valid_trajectory"
        )
        evidence = Counter(_check_status(item, "evidence_support_complete") for item in rows)
        answer = Counter(_check_status(item, "answer_projection_complete") for item in rows)
        values: dict[str, Any] = {
            "scope": scope,
            "rollout_count": len(rows),
            "invalid_count": len(invalid),
            "mechanism_success_count": len(local),
            "independently_valid_count": len(valid),
            "valid_and_mechanism_success_count": len(joint),
            "valid_given_mechanism_success": _rate(len(joint), len(local)),
            "mechanism_success_given_valid": _rate(len(joint), len(valid)),
            "local_success_invalid_count": len(local_invalid),
            "local_success_program_closed_count": sum(
                bool(diagnostics[item.rollout_id]["all_steps_completed"]) for item in local_invalid
            ),
            "local_success_postterminal_verified_count": sum(
                bool(diagnostics[item.rollout_id]["verification_after_terminal_completed"])
                for item in local_invalid
            ),
            "local_success_verifier_evaluated_count": sum(
                item.verification is not None for item in local_invalid
            ),
            "invalid_earliest_failure_stage_counts": dict(
                sorted(Counter(_failure_stage(item) for item in invalid).items())
            ),
            "local_success_failure_reason_counts": dict(
                sorted(Counter(_failure_reason_family(item) for item in local_invalid).items())
            ),
            "evidence_support_status_counts": {
                key: evidence[key] for key in ("passed", "failed", "not_evaluated")
            },
            "answer_projection_status_counts": {
                key: answer[key] for key in ("passed", "failed", "not_evaluated")
            },
        }
        provisional = CapabilityConversionSummary.model_construct(summary_id="pending", **values)
        output.append(
            CapabilityConversionSummary(
                summary_id=capability_conversion_summary_id(provisional), **values
            )
        )
    return tuple(output)


def _structural_signature(record: OperationalTaskRecord) -> str:
    package = record.task_package
    lattice = package.evidence_support_lattice
    values = {
        "required_node_count": len(package.stop_readiness_contract.required_node_ids),
        "public_variable_count": len(package.operation_contract.public_view.variables),
        "necessary_evidence_count": len(lattice.necessary_evidence_ids),
        "sufficient_support_set_sizes": sorted(
            len(item.evidence_ids) for item in lattice.sufficient_support_sets
        ),
        "operation_node_kind_counts": dict(
            sorted(
                Counter(
                    item.node_kind for item in package.operation_contract.public_view.nodes
                ).items()
            )
        ),
        "allowed_tool_ids": tuple(sorted(package.tool_closure.allowed_tool_ids)),
        "answer_field_ids": tuple(sorted(package.task.public.answer_schema)),
    }
    return canonical_hash(values, prefix="finance_v26_stopping_structural_signature:")


def _stopping_task_profile(
    *,
    role: EmpiricalRole,
    record: OperationalTaskRecord,
    rows: Sequence[EmpiricalPilotRollout],
    payloads: Mapping[str, Mapping[str, Any]],
) -> StoppingTaskProfile:
    package = record.task_package
    lattice = package.evidence_support_lattice
    support_sizes = tuple(len(item.evidence_ids) for item in lattice.sufficient_support_sets)
    progresses = tuple(
        _progress(record, _parse_observations(payloads[item.rollout_id])) for item in rows
    )
    values: dict[str, Any] = {
        "role": role,
        "task_package_id": package.package_id,
        "semantic_source_id": package.semantic_source.semantic_source_id,
        "structural_signature": _structural_signature(record),
        "required_node_count": len(package.stop_readiness_contract.required_node_ids),
        "public_variable_count": len(package.operation_contract.public_view.variables),
        "necessary_evidence_count": len(lattice.necessary_evidence_ids),
        "sufficient_support_set_size_range": (min(support_sizes), max(support_sizes)),
        "operation_node_kind_counts": dict(
            sorted(
                Counter(
                    item.node_kind for item in package.operation_contract.public_view.nodes
                ).items()
            )
        ),
        "allowed_tool_ids": tuple(sorted(package.tool_closure.allowed_tool_ids)),
        "answer_field_ids": tuple(sorted(package.task.public.answer_schema)),
        "rollout_count": len(rows),
        "sampling_mode_counts": dict(sorted(Counter(item.sampling_mode for item in rows).items())),
        "local_mechanism_success_count": sum(item.mechanism_estimand.success for item in rows),
        "full_program_lineage_count": sum(
            bool(progress["all_steps_completed"]) for progress in progresses
        ),
        "postterminal_verification_count": sum(
            bool(progress["verification_after_terminal_completed"]) for progress in progresses
        ),
        "verifier_evaluated_count": sum(item.verification is not None for item in rows),
        "frozen_runtime_replay_failure_count": sum(
            item.verification is not None and not item.verification.checks["runtime_replay_passed"]
            for item in rows
        ),
        "independently_valid_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in rows
        ),
    }
    provisional = StoppingTaskProfile.model_construct(profile_id="pending", **values)
    return StoppingTaskProfile(profile_id=stopping_task_profile_id(provisional), **values)


def _stopping_role_summary(
    role: EmpiricalRole,
    rows: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    payloads: Mapping[str, Mapping[str, Any]],
) -> StoppingRoleSummary:
    progresses = tuple(
        _progress(records[item.task_record_id], _parse_observations(payloads[item.rollout_id]))
        for item in rows
    )
    return StoppingRoleSummary(
        role=role,
        rollout_count=len(rows),
        sampling_mode_counts=dict(sorted(Counter(item.sampling_mode for item in rows).items())),
        local_mechanism_success_count=sum(item.mechanism_estimand.success for item in rows),
        full_program_lineage_count=sum(
            bool(progress["all_steps_completed"]) for progress in progresses
        ),
        postterminal_verification_count=sum(
            bool(progress["verification_after_terminal_completed"]) for progress in progresses
        ),
        verifier_evaluated_count=sum(item.verification is not None for item in rows),
        frozen_runtime_replay_failure_count=sum(
            item.verification is not None and not item.verification.checks["runtime_replay_passed"]
            for item in rows
        ),
        sole_runtime_replay_blocker_count=sum(
            item.verification is not None
            and {key for key, passed in item.verification.checks.items() if not passed}
            == {"runtime_replay_passed"}
            for item in rows
        ),
        independently_valid_count=sum(
            item.terminal_category == "model_valid_trajectory" for item in rows
        ),
    )


def _stopping_contrast(
    *,
    capability_rollouts: Sequence[EmpiricalPilotRollout],
    reachability_rollouts: Sequence[EmpiricalPilotRollout],
    capability_records: Mapping[str, OperationalTaskRecord],
    reachability_records: Mapping[str, OperationalTaskRecord],
    capability_payloads: Mapping[str, Mapping[str, Any]],
    reachability_payloads: Mapping[str, Mapping[str, Any]],
) -> StoppingRoleContrast:
    capability_rows = tuple(
        item for item in capability_rollouts if item.mechanism_id == "state_dependent_stopping"
    )
    reachability_rows = tuple(
        item for item in reachability_rollouts if item.mechanism_id == "state_dependent_stopping"
    )
    profiles = []
    for role, rows, records, payloads in (
        (
            "capability_development",
            capability_rows,
            capability_records,
            capability_payloads,
        ),
        (
            "state_reachability",
            reachability_rows,
            reachability_records,
            reachability_payloads,
        ),
    ):
        by_task: dict[str, list[EmpiricalPilotRollout]] = {}
        for item in rows:
            by_task.setdefault(item.task_record_id, []).append(item)
        for record_id, task_rows in sorted(by_task.items()):
            profiles.append(
                _stopping_task_profile(
                    role=cast(EmpiricalRole, role),
                    record=records[record_id],
                    rows=task_rows,
                    payloads=payloads,
                )
            )
    capability = _stopping_role_summary(
        "capability_development",
        capability_rows,
        capability_records,
        capability_payloads,
    )
    reachability = _stopping_role_summary(
        "state_reachability",
        reachability_rows,
        reachability_records,
        reachability_payloads,
    )
    capability_profiles = tuple(item for item in profiles if item.role == "capability_development")
    reachability_profiles = tuple(item for item in profiles if item.role == "state_reachability")
    values: dict[str, Any] = {
        "capability": capability,
        "reachability": reachability,
        "task_profiles": tuple(sorted(profiles, key=lambda item: item.profile_id)),
        "shared_task_package_count": len(
            {item.task_package_id for item in capability_profiles}
            & {item.task_package_id for item in reachability_profiles}
        ),
        "shared_semantic_source_count": len(
            {item.semantic_source_id for item in capability_profiles}
            & {item.semantic_source_id for item in reachability_profiles}
        ),
        "shared_structural_signature_count": len(
            {item.structural_signature for item in capability_profiles}
            & {item.structural_signature for item in reachability_profiles}
        ),
        "observed_validity_count_difference": (
            reachability.independently_valid_count - capability.independently_valid_count
        ),
        "capability_zero_valid_interpretation_blocked_by_verifier_gap": (
            capability.sole_runtime_replay_blocker_count > 0
        ),
        "conclusion": (
            "The frozen Capability Stopping zero cannot be attributed causally to task support: "
            "all eight local-success rows passed every non-replay verifier check, while the "
            "authority-preserving Runtime and frozen legacy replay disagreed. Role, Population, "
            "and conditioning also differ, so historical rows remain unchanged and a prospective "
            "Verifier repair must precede task-support redesign."
        ),
    }
    provisional = StoppingRoleContrast.model_construct(contrast_id="pending", **values)
    return StoppingRoleContrast(contrast_id=stopping_role_contrast_id(provisional), **values)


def _observed_mapper_path_strategy(observations: Sequence[AgentToolObservation]) -> str:
    successful = set()
    for item in observations:
        if item.call.tool_id == "calculator" and item.status == "succeeded":
            break
        if item.status == "succeeded":
            successful.add(item.call.tool_id)
    if "open_document" in successful:
        return "search_then_open"
    if "search_archive" in successful:
        return "search_then_structured"
    if "query_structured_fact" in successful:
        return "structured_direct"
    return "no_successful_precalculation_acquisition"


def _observed_condition_path_strategy(
    observations: Sequence[AgentToolObservation],
) -> str:
    successful = set()
    for item in observations:
        if item.call.tool_id == "calculator":
            break
        if item.status == "succeeded":
            successful.add(item.call.tool_id)
    if "open_document" in successful:
        return "search_then_open"
    if "search_archive" in successful:
        return "search_then_structured"
    if "query_structured_fact" in successful:
        return "structured_direct"
    return "no_successful_precalculation_acquisition"


def _valid_mapping_diagnostics(
    rollouts: Sequence[EmpiricalPilotRollout],
    payloads: Mapping[str, Mapping[str, Any]],
    released_rollout_ids: set[str],
) -> tuple[ValidMappingDiagnostic, ...]:
    valid = tuple(item for item in rollouts if item.terminal_category == "model_valid_trajectory")
    if len(valid) != 21 or any(item.path_assignment is None for item in valid):
        raise ValueError("Reachability valid-mapping denominator changed")
    trace_counts = Counter(
        (item.task_package_id, item.path_assignment.quotient_state_id, item.decision_trace_hash)
        for item in valid
        if item.path_assignment is not None
    )
    content_counts = Counter(
        (item.task_package_id, item.path_assignment.quotient_state_id, item.trajectory_content_hash)
        for item in valid
        if item.path_assignment is not None
    )
    output = []
    for rollout in valid:
        assignment = rollout.path_assignment
        if (
            assignment is None
            or rollout.decision_trace_hash is None
            or rollout.trajectory_content_hash is None
        ):
            raise ValueError("mapped valid rollout lacks frozen identity")
        observed = _observed_mapper_path_strategy(_parse_observations(payloads[rollout.rollout_id]))
        if observed != assignment.path_strategy:
            raise ValueError("Reachability Mapper does not replay from public tool milestones")
        conditioned = rollout.sampling_mode == "reachability_conditioned"
        dimensions = []
        if conditioned:
            if rollout.requested_static_path_id != assignment.static_path_id:
                dimensions.append("static_path_id")
            if rollout.requested_path_strategy != assignment.path_strategy:
                dimensions.append("path_strategy")
            if rollout.requested_quotient_state_id != assignment.quotient_state_id:
                dimensions.append("quotient_state_id")
        values: dict[str, Any] = {
            "rollout_id": rollout.rollout_id,
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "sampling_mode": rollout.sampling_mode,
            "requested_static_path_id": rollout.requested_static_path_id,
            "requested_path_strategy": rollout.requested_path_strategy,
            "requested_quotient_state_id": rollout.requested_quotient_state_id,
            "actual_static_path_id": assignment.static_path_id,
            "actual_path_strategy": assignment.path_strategy,
            "actual_quotient_state_id": assignment.quotient_state_id,
            "successful_precalculation_tool_ids": assignment.successful_precalculation_tool_ids,
            "route_adherent": (
                assignment.path_strategy == rollout.requested_path_strategy if conditioned else None
            ),
            "on_target": (
                assignment.quotient_state_id == rollout.requested_quotient_state_id
                if conditioned
                else None
            ),
            "off_target_mapper_dimensions": tuple(dimensions),
            "decision_trace_hash": rollout.decision_trace_hash,
            "trajectory_content_hash": rollout.trajectory_content_hash,
            "duplicate_decision_trace_within_actual_state": trace_counts[
                (rollout.task_package_id, assignment.quotient_state_id, rollout.decision_trace_hash)
            ]
            > 1,
            "duplicate_content_within_actual_state": content_counts[
                (
                    rollout.task_package_id,
                    assignment.quotient_state_id,
                    rollout.trajectory_content_hash,
                )
            ]
            > 1,
            "released_realization": rollout.rollout_id in released_rollout_ids,
        }
        provisional = ValidMappingDiagnostic.model_construct(diagnostic_id="pending", **values)
        output.append(
            ValidMappingDiagnostic(diagnostic_id=valid_mapping_diagnostic_id(provisional), **values)
        )
    return tuple(sorted(output, key=lambda item: item.diagnostic_id))


def _route_summaries(
    rollouts: Sequence[EmpiricalPilotRollout],
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[ReachabilityRouteSummary, ...]:
    output = []
    for strategy in _PATH_STRATEGIES:
        rows = tuple(
            item
            for item in rollouts
            if item.sampling_mode == "reachability_conditioned"
            and item.requested_path_strategy == strategy
        )
        observed = Counter(
            _observed_condition_path_strategy(_parse_observations(payloads[item.rollout_id]))
            for item in rows
        )
        valid = tuple(item for item in rows if item.terminal_category == "model_valid_trajectory")
        valid_routes = Counter(
            cast(Any, item.path_assignment).path_strategy
            for item in valid
            if item.path_assignment is not None
        )
        on_target = sum(
            item.path_assignment is not None
            and item.path_assignment.quotient_state_id == item.requested_quotient_state_id
            for item in valid
        )
        off_target = sum(
            item.path_assignment is not None
            and item.path_assignment.quotient_state_id != item.requested_quotient_state_id
            for item in valid
        )
        unmapped = sum(item.path_assignment is None for item in valid)
        values: dict[str, Any] = {
            "requested_path_strategy": strategy,
            "attempt_count": len(rows),
            "observed_path_strategy_counts": dict(sorted(observed.items())),
            "adherence_count": observed[strategy],
            "independently_valid_count": len(valid),
            "valid_actual_path_strategy_counts": dict(sorted(valid_routes.items())),
            "on_target_valid_count": on_target,
            "off_target_valid_count": off_target,
            "valid_unmapped_count": unmapped,
            "route_condition_control_established": on_target > 0,
        }
        provisional = ReachabilityRouteSummary.model_construct(summary_id="pending", **values)
        output.append(
            ReachabilityRouteSummary(
                summary_id=reachability_route_summary_id(provisional), **values
            )
        )
    return tuple(output)


def _state_support_diagnostics(
    *,
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    reachability_report: AuthorityPreservingRoleReport,
) -> tuple[StateSupportDiagnostic, ...]:
    by_state: dict[str, list[EmpiricalPilotRollout]] = {}
    for rollout in rollouts:
        if rollout.path_assignment is not None:
            by_state.setdefault(rollout.path_assignment.quotient_state_id, []).append(rollout)
    output = []
    for state in reachability_report.state_reachability_summaries:
        rows = by_state.get(state.quotient_state_id, [])
        natural = tuple(
            sorted(
                item.rollout_id
                for item in rows
                if item.sampling_mode == "reachability_unconditional"
            )
        )
        on_target = tuple(
            sorted(
                item.rollout_id
                for item in rows
                if item.sampling_mode == "reachability_conditioned"
                and item.requested_quotient_state_id == state.quotient_state_id
            )
        )
        released = tuple(state.released_rollout_ids)
        if not natural and not on_target and not released:
            continue
        released_rows = tuple(item for item in rows if item.rollout_id in set(released))
        record = records[next(item.task_record_id for item in rows)]
        values: dict[str, Any] = {
            "task_package_id": state.task_package_id,
            "mechanism_id": record.mechanism_id,
            "static_path_id": state.static_path_id,
            "path_strategy": state.path_strategy,
            "quotient_state_id": state.quotient_state_id,
            "natural_hit_rollout_ids": natural,
            "conditioned_on_target_rollout_ids": on_target,
            "released_rollout_ids": released,
            "natural_hit_count": len(natural),
            "conditioned_on_target_count": len(on_target),
            "released_count": len(released),
            "released_unique_content_count": len(
                {item.trajectory_content_hash for item in released_rows}
            ),
            "released_unique_decision_trace_count": len(
                {item.decision_trace_hash for item in released_rows}
            ),
            "release_shortfall": max(0, 3 - len(released)),
            "blockers": state.blockers,
            "admitted": state.admitted,
        }
        provisional = StateSupportDiagnostic.model_construct(diagnostic_id="pending", **values)
        output.append(
            StateSupportDiagnostic(diagnostic_id=state_support_diagnostic_id(provisional), **values)
        )
    return tuple(sorted(output, key=lambda item: item.diagnostic_id))


def _tool_result_payload(value: AgentToolResult | AgentToolObservation) -> dict[str, Any]:
    return {
        "status": value.status,
        "result": value.result,
        "evidence_ids": value.evidence_ids,
        "provenance_hashes": value.provenance_hashes,
        "host_events": value.host_events,
        "error_code": value.error_code,
        "error_message": value.error_message,
    }


def _canonical_tool_result_payload(
    value: AgentToolResult | AgentToolObservation,
) -> dict[str, Any]:
    return json.loads(json.dumps(_tool_result_payload(value), sort_keys=True))


def _call_signature(observation: AgentToolObservation) -> str:
    return canonical_hash(
        {
            "tool_id": observation.call.tool_id,
            "arguments": observation.call.arguments,
        },
        prefix="finance_v26_authority_aligned_failed_call:",
    )


def _semantic_replay(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
    *,
    authority_aligned: bool,
) -> tuple[bool, tuple[str, ...]]:
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )
    task = record.task_package.task.public
    failures: list[str] = []
    failed_signatures: set[str] = set()
    observed: list[AgentToolObservation] = []
    for index, observation in enumerate(observations):
        if observation.environment_manifest_id != environment.manifest_id:
            failures.append(f"observation:{index}:environment_identity")
            observed.append(observation)
            continue
        spec = environment.tools_by_id.get(observation.call.tool_id)
        if spec is None:
            failures.append(f"observation:{index}:unknown_tool")
            observed.append(observation)
            continue
        signature = _call_signature(observation)
        if signature in failed_signatures:
            replayed = AgentToolResult(
                status="failed",
                result={
                    "retry_contract": {
                        "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                        "suggested_argument_patch": {
                            "rule": (
                                "change at least one argument according to the latest public "
                                "error; the identical failed action remains blocked"
                            )
                        },
                    }
                },
                error_code="identical_failed_action_blocked",
                error_message="The Host blocked an identical failed action without executing it.",
            )
        else:
            candidate: AgentToolResult | None = agent_tool_argument_rejection(
                spec, observation.call
            )
            if candidate is None and authority_aligned:
                candidate = (
                    public_postcompletion_action_rejection(task, tuple(observed), observation.call)
                    or public_terminal_verification_rejection(
                        task, tuple(observed), observation.call
                    )
                    or public_operation_step_rejection(task, tuple(observed), observation.call)
                )
            replayed = candidate or runtime.execute(observation.call)
        if authority_aligned:
            replayed = public_action_neutral_repair_result(
                task,
                tuple(observed),
                observation.call,
                replayed,
            )
        if replayed.status == "succeeded":
            try:
                spec.validate_output(replayed.result)
            except ValueError as error:
                failures.append(f"observation:{index}:output_contract:{error}")
        if _canonical_tool_result_payload(replayed) != _canonical_tool_result_payload(observation):
            failures.append(f"observation:{index}:replay_mismatch")
        if observation.status == "succeeded":
            failed_signatures.clear()
        else:
            failed_signatures.add(signature)
        observed.append(observation)
    return not failures, tuple(failures)


def _frozen_semantic_replay(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> tuple[bool, tuple[str, ...]]:
    return _semantic_replay(record, environment, observations, authority_aligned=False)


def _authority_aligned_replay(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> tuple[bool, tuple[str, ...]]:
    return _semantic_replay(record, environment, observations, authority_aligned=True)


def _replay_differentials(
    *,
    role: EmpiricalRole,
    rollouts: Sequence[EmpiricalPilotRollout],
    records: Mapping[str, OperationalTaskRecord],
    environments: Mapping[str, AgentToolEnvironmentManifest],
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[VerifierReplayDifferential, ...]:
    output = []
    for rollout in rollouts:
        verification = rollout.verification
        if verification is None or verification.checks["runtime_replay_passed"]:
            continue
        record = records[rollout.task_record_id]
        environment = environments[record.environment_manifest_id]
        observations = _parse_observations(payloads[rollout.rollout_id])
        frozen_passed, frozen_failures = _frozen_semantic_replay(
            record,
            environment,
            observations,
        )
        if frozen_passed:
            raise ValueError("frozen verifier failure no longer replays")
        aligned_passed, aligned_failures = _authority_aligned_replay(
            record,
            environment,
            observations,
        )
        indices = tuple(
            sorted(
                {
                    int(match.group(1))
                    for failure in frozen_failures
                    if (match := re.match(r"observation:(\d+):replay_mismatch", failure))
                }
            )
        )
        mismatches = tuple(
            observations[index] for index in indices if 0 <= index < len(observations)
        )
        failed_mismatches = tuple(item for item in mismatches if item.status == "failed")
        failed_checks = tuple(
            sorted(key for key, passed in verification.checks.items() if not passed)
        )
        values: dict[str, Any] = {
            "role": role,
            "rollout_id": rollout.rollout_id,
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "mechanism_id": rollout.mechanism_id,
            "frozen_failed_check_ids": failed_checks,
            "frozen_replay_failure_ids": frozen_failures,
            "replay_mismatch_observation_indices": indices,
            "mismatch_error_code_counts": dict(
                sorted(Counter(item.error_code or "none" for item in mismatches).items())
            ),
            "mismatch_tool_counts": dict(
                sorted(Counter(item.call.tool_id for item in mismatches).items())
            ),
            "failed_mismatch_observations_action_neutral": bool(failed_mismatches)
            and all(not _contains_action_binding(item.result) for item in failed_mismatches),
            "authority_aligned_replay_passed": aligned_passed,
            "authority_aligned_replay_failure_ids": aligned_failures,
            "runtime_replay_is_sole_frozen_blocker": failed_checks == ("runtime_replay_passed",),
            "prospective_repair_signal": bool(frozen_failures) and aligned_passed,
        }
        provisional = VerifierReplayDifferential.model_construct(
            differential_id="pending", **values
        )
        output.append(
            VerifierReplayDifferential(
                differential_id=verifier_replay_differential_id(provisional), **values
            )
        )
    return tuple(sorted(output, key=lambda item: item.differential_id))


def _load_rollouts(run_dir: Path) -> tuple[EmpiricalPilotRollout, ...]:
    return tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((run_dir / "empirical_rollouts.json").read_text(encoding="utf-8"))
    )


def _load_environments(task_source_dir: Path) -> dict[str, AgentToolEnvironmentManifest]:
    values = tuple(
        AgentToolEnvironmentManifest.model_validate(item)
        for item in json.loads(
            (task_source_dir / "tool_environment_manifests.json").read_text(encoding="utf-8")
        )
    )
    return {item.manifest_id: item for item in values}


def _load_capability_records(task_source_dir: Path) -> tuple[OperationalTaskRecord, ...]:
    report = FreshCapabilityPopulationReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    records = tuple(report.task_records)
    if len(records) != 12:
        raise ValueError("failure audit lost the twelve fresh Capability tasks")
    return records


def _load_reachability_records(
    task_source_dir: Path,
) -> tuple[tuple[OperationalTaskRecord, ...], tuple[StaticModelAuthorityPathCatalog, ...]]:
    report = AuthorityPreservingHardeningReport.model_validate_json(
        (task_source_dir / "report.json").read_text(encoding="utf-8")
    )
    records = tuple(
        item for item in report.task_records if item.intended_use == "vtdo_multistate_candidate"
    )
    task_ids = {item.task_package.package_id for item in records}
    catalogs = tuple(
        item
        for item in (
            StaticModelAuthorityPathCatalog.model_validate(value)
            for value in json.loads(
                (task_source_dir / "static_model_authority_path_catalogs.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        if item.task_package_id in task_ids
    )
    if len(records) != 12 or len(catalogs) != 12:
        raise ValueError("failure audit lost the twelve VTDO tasks or 36 states")
    return records, catalogs


def _source_artifacts(
    *,
    package_root: Path,
    capability_run_dir: Path,
    capability_task_source_dir: Path,
    reachability_run_dir: Path,
    reachability_task_source_dir: Path,
    postrun_audit_dir: Path,
) -> tuple[BoundFile, ...]:
    paths = (
        capability_run_dir / "execution_contract.json",
        capability_run_dir / "job_manifest.json",
        capability_run_dir / "empirical_rollouts.json",
        capability_run_dir / "rollout_diagnostics.json",
        capability_run_dir / "report.json",
        capability_task_source_dir / "operational_task_records.json",
        capability_task_source_dir / "tool_environment_manifests.json",
        capability_task_source_dir / "report.json",
        reachability_run_dir / "execution_contract.json",
        reachability_run_dir / "job_manifest.json",
        reachability_run_dir / "empirical_rollouts.json",
        reachability_run_dir / "rollout_diagnostics.json",
        reachability_run_dir / "state_reachability_summaries.json",
        reachability_run_dir / "state_support_freeze.json",
        reachability_run_dir / "report.json",
        reachability_task_source_dir / "operational_task_records.json",
        reachability_task_source_dir / "static_model_authority_path_catalogs.json",
        reachability_task_source_dir / "tool_environment_manifests.json",
        reachability_task_source_dir / "report.json",
        postrun_audit_dir / "rollout_replay_audits.json",
        postrun_audit_dir / "report.json",
    )
    return tuple(
        sorted((_bound_file(path, package_root) for path in paths), key=lambda x: x.relative_path)
    )


def build_capability_reachability_failure_audit(
    *,
    run_id: str,
    capability_run_dir: Path,
    capability_task_source_dir: Path,
    reachability_run_dir: Path,
    reachability_task_source_dir: Path,
    postrun_audit_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> CapabilityReachabilityFailureAuditReport:
    capability_report = AuthorityPreservingRoleReport.model_validate_json(
        (capability_run_dir / "report.json").read_text(encoding="utf-8")
    )
    reachability_report = AuthorityPreservingRoleReport.model_validate_json(
        (reachability_run_dir / "report.json").read_text(encoding="utf-8")
    )
    postrun_report = AuthorityPreservingRolePostrunAuditReport.model_validate_json(
        (postrun_audit_dir / "report.json").read_text(encoding="utf-8")
    )
    capability_rollouts = _load_rollouts(capability_run_dir)
    reachability_rollouts = _load_rollouts(reachability_run_dir)
    if len(capability_rollouts) != 96 or len(reachability_rollouts) != 360:
        raise ValueError("failure audit source denominators changed")
    if any(
        item.terminal_category not in {"model_valid_trajectory", "model_invalid_trajectory"}
        for item in (*capability_rollouts, *reachability_rollouts)
    ):
        raise ValueError("failure audit source contains a Runtime or instrument failure")
    if (
        postrun_report.capability.source_report_id != capability_report.report_id
        or postrun_report.reachability.source_report_id != reachability_report.report_id
    ):
        raise ValueError("failure audit source reports differ from v26.73")
    freeze = reachability_report.state_support_freeze
    if freeze is None or freeze.status != "blocked" or freeze.admitted_task_count != 0:
        raise ValueError("failure audit must retain the blocked State Support Freeze")

    capability_records_tuple = _load_capability_records(capability_task_source_dir)
    reachability_records_tuple, _ = _load_reachability_records(reachability_task_source_dir)
    capability_records = {item.record_id: item for item in capability_records_tuple}
    reachability_records = {item.record_id: item for item in reachability_records_tuple}
    capability_environments = _load_environments(capability_task_source_dir)
    reachability_environments = _load_environments(reachability_task_source_dir)
    capability_payloads = {
        item.rollout_id: _load_raw_payload(item, capability_run_dir) for item in capability_rollouts
    }
    reachability_payloads = {
        item.rollout_id: _load_raw_payload(item, reachability_run_dir)
        for item in reachability_rollouts
    }

    capability_failures = _capability_failure_diagnostics(
        capability_rollouts,
        capability_records,
        capability_payloads,
    )
    conversions = _capability_conversion_summaries(
        capability_rollouts,
        capability_records,
        capability_payloads,
    )
    stopping = _stopping_contrast(
        capability_rollouts=capability_rollouts,
        reachability_rollouts=reachability_rollouts,
        capability_records=capability_records,
        reachability_records=reachability_records,
        capability_payloads=capability_payloads,
        reachability_payloads=reachability_payloads,
    )
    released_ids = {
        rollout_id
        for item in reachability_report.state_reachability_summaries
        for rollout_id in item.released_rollout_ids
    }
    mappings = _valid_mapping_diagnostics(
        reachability_rollouts,
        reachability_payloads,
        released_ids,
    )
    routes = _route_summaries(reachability_rollouts, reachability_payloads)
    states = _state_support_diagnostics(
        rollouts=reachability_rollouts,
        records=reachability_records,
        reachability_report=reachability_report,
    )
    differentials = (
        *_replay_differentials(
            role="capability_development",
            rollouts=capability_rollouts,
            records=capability_records,
            environments=capability_environments,
            payloads=capability_payloads,
        ),
        *_replay_differentials(
            role="state_reachability",
            rollouts=reachability_rollouts,
            records=reachability_records,
            environments=reachability_environments,
            payloads=reachability_payloads,
        ),
    )
    differentials = tuple(sorted(differentials, key=lambda item: item.differential_id))
    if len(differentials) != 18 or not all(
        item.prospective_repair_signal and item.failed_mismatch_observations_action_neutral
        for item in differentials
    ):
        raise ValueError("frozen Verifier replay gap does not reproduce prospectively")
    if sum(item.runtime_replay_is_sole_frozen_blocker for item in differentials) != 15:
        raise ValueError("frozen sole-replay-blocker denominator changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "capability_conversion_summaries.json": conversions,
        "capability_failure_diagnostics.json": capability_failures,
        "reachability_route_summaries.json": routes,
        "reachability_valid_mapping_diagnostics.json": mappings,
        "state_support_diagnostics.json": states,
        "stopping_role_contrast.json": stopping,
        "verifier_replay_differentials.json": differentials,
    }
    for relative, value in paths.items():
        payload: Any
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            payload = [item.model_dump(mode="json") for item in value]
        _write_json(output_dir / relative, payload)
    details = tuple(
        _detail_file(
            output_dir / relative,
            output_dir,
            1 if isinstance(value, BaseModel) else len(value),
        )
        for relative, value in sorted(paths.items())
    )
    source_files = _source_artifacts(
        package_root=package_root,
        capability_run_dir=capability_run_dir,
        capability_task_source_dir=capability_task_source_dir,
        reachability_run_dir=reachability_run_dir,
        reachability_task_source_dir=reachability_task_source_dir,
        postrun_audit_dir=postrun_audit_dir,
    )
    state_summaries = reachability_report.state_reachability_summaries
    natural_hits = sum(item.natural_on_state_hit_count for item in state_summaries)
    on_target = sum(item.conditioned_on_target_count for item in state_summaries)
    released = sum(item.released_count for item in state_summaries)
    values: dict[str, Any] = {
        "run_id": run_id,
        "capability_source_report_id": capability_report.report_id,
        "capability_source_report_sha256": _sha256(capability_run_dir / "report.json"),
        "reachability_source_report_id": reachability_report.report_id,
        "reachability_source_report_sha256": _sha256(reachability_run_dir / "report.json"),
        "source_postrun_audit_report_id": postrun_report.report_id,
        "source_postrun_audit_report_sha256": _sha256(postrun_audit_dir / "report.json"),
        "raw_artifact_replay_pass_count": len(capability_payloads) + len(reachability_payloads),
        "raw_artifact_count": len(capability_rollouts) + len(reachability_rollouts),
        "capability_rollout_count": len(capability_rollouts),
        "capability_invalid_count": len(capability_failures),
        "capability_independently_valid_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in capability_rollouts
        ),
        "capability_mechanism_success_count": sum(
            item.mechanism_estimand.success for item in capability_rollouts
        ),
        "reachability_rollout_count": len(reachability_rollouts),
        "reachability_independently_valid_count": sum(
            item.terminal_category == "model_valid_trajectory" for item in reachability_rollouts
        ),
        "reachability_mapped_valid_count": sum(
            item.path_assignment is not None for item in reachability_rollouts
        ),
        "natural_state_hit_count": natural_hits,
        "conditioned_on_target_count": on_target,
        "released_realization_count": released,
        "admitted_state_count": sum(item.admitted for item in state_summaries),
        "admitted_task_count": freeze.admitted_task_count,
        "frozen_runtime_replay_failure_count": len(differentials),
        "authority_aligned_replay_pass_count": sum(
            item.authority_aligned_replay_passed for item in differentials
        ),
        "sole_runtime_replay_blocker_count": sum(
            item.runtime_replay_is_sole_frozen_blocker for item in differentials
        ),
        "verifier_replay_contract_gap_observed": True,
        "source_artifact_files": source_files,
        "immutable_detail_files": details,
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = CapabilityReachabilityFailureAuditReport.model_construct(
        report_id="pending", **values
    )
    report = CapabilityReachabilityFailureAuditReport(
        report_id=capability_reachability_failure_audit_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def capability_failure_diagnostic_id(value: CapabilityFailureDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_capability_failure_diagnostic:",
    )


def capability_conversion_summary_id(value: CapabilityConversionSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_capability_conversion_summary:",
    )


def stopping_task_profile_id(value: StoppingTaskProfile) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"profile_id"}),
        prefix="finance_v26_stopping_task_profile:",
    )


def stopping_role_contrast_id(value: StoppingRoleContrast) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contrast_id"}),
        prefix="finance_v26_stopping_role_contrast:",
    )


def valid_mapping_diagnostic_id(value: ValidMappingDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_valid_mapping_diagnostic:",
    )


def reachability_route_summary_id(value: ReachabilityRouteSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="finance_v26_reachability_route_summary:",
    )


def state_support_diagnostic_id(value: StateSupportDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_state_support_diagnostic:",
    )


def verifier_replay_differential_id(value: VerifierReplayDifferential) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"differential_id"}),
        prefix="finance_v26_verifier_replay_differential:",
    )


def capability_reachability_failure_audit_report_id(
    value: CapabilityReachabilityFailureAuditReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_capability_reachability_failure_audit:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only root-cause audit of Finance v26.71 Capability and v26.72 Reachability"  # noqa: E501
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capability-run-dir", type=Path, required=True)
    parser.add_argument("--capability-task-source-dir", type=Path, required=True)
    parser.add_argument("--reachability-run-dir", type=Path, required=True)
    parser.add_argument("--reachability-task-source-dir", type=Path, required=True)
    parser.add_argument("--postrun-audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    report = build_capability_reachability_failure_audit(
        run_id=args.run_id,
        capability_run_dir=args.capability_run_dir,
        capability_task_source_dir=args.capability_task_source_dir,
        reachability_run_dir=args.reachability_run_dir,
        reachability_task_source_dir=args.reachability_task_source_dir,
        postrun_audit_dir=args.postrun_audit_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "status": report.status,
                "capability_invalid": report.capability_invalid_count,
                "mapped_valid": report.reachability_mapped_valid_count,
                "frozen_replay_failures": report.frozen_runtime_replay_failure_count,
                "authority_aligned_replay_passes": report.authority_aligned_replay_pass_count,
                "next_permitted_stage": report.next_permitted_stage,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
