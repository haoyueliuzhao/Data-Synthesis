from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.trajectory.executable_task import (
    ExecutableTaskAdmission,
    StaticModelAuthorityPathCatalog,
    matching_sufficient_support_set,
)
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FINANCE_EXECUTABLE_SUPPORT_RUNTIME_ID,
    FINANCE_EXECUTABLE_SUPPORT_RUNTIME_VERSION,
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    PATH_STRATEGIES,
    TARGET_MECHANISMS,
    PathStrategy,
    RematerializedExecutableTaskRecord,
    TargetMechanism,
    V26ExecutableTaskRematerializationReport,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    IterativeAgentFailureArtifact,
    IterativeAgentSolveResult,
    PublicAgentScaffoldCompiler,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    agent_tool_argument_rejection,
)

V26_EMPIRICAL_SUPPORT_PILOT_VERSION = "finance_v26_empirical_support_pilot.v1"
V26_EMPIRICAL_SUPPORT_CONTRACT_VERSION = "finance_v26_empirical_support_contract.v1"
V26_EMPIRICAL_EXECUTABLE_VERIFIER_VERSION: Literal["executable_task_verifier.v1"] = (
    "executable_task_verifier.v1"
)
V26_EMPIRICAL_PATH_MAPPER_VERSION = "finance_v26_empirical_path_mapper.v1"
V26_REACHABILITY_CONDITION_VERSION = "finance_v26_public_reachability_condition.v1"

CAPABILITY_ROLLOUTS_PER_TASK: Literal[8] = 8
NATURAL_ROLLOUTS_PER_TASK: Literal[12] = 12
CONDITIONED_ROLLOUTS_PER_STATE: Literal[6] = 6
MINIMUM_RELEASED_REALIZATIONS: Literal[3] = 3
MAXIMUM_ESTIMATED_ATTEMPTS_FOR_THREE = 60.0
MAXIMUM_TOTAL_MODEL_TOKENS = 120_000
MAXIMUM_TOTAL_ESTIMATED_COST_USD = 25.0

SamplingMode = Literal[
    "capability_unconditional",
    "reachability_unconditional",
    "reachability_conditioned",
]
RolloutTerminal = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "runtime_failure",
    "instrument_failure",
]
PilotStatus = Literal["preflight", "partial", "completed", "blocked"]

IMPLEMENTATION_SOURCE_PATHS = (
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_runner.py"),
)

VERIFICATION_CHECK_IDS = (
    "runtime_replay_passed",
    "model_input_noninterference_passed",
    "only_allowed_tools",
    "operation_lineage_complete",
    "evidence_support_complete",
    "verification_complete",
    "answer_projection_complete",
    "citation_complete",
    "mechanism_complete",
    "no_postcompletion_violation",
)

FAILURE_STAGE_ORDER = (
    ("runtime_replay_passed", "runtime_replay"),
    ("model_input_noninterference_passed", "model_input_noninterference"),
    ("only_allowed_tools", "tool_authority"),
    ("evidence_support_complete", "evidence_selection"),
    ("operation_lineage_complete", "operation_execution"),
    ("verification_complete", "verification"),
    ("answer_projection_complete", "answer_projection"),
    ("citation_complete", "citation"),
    ("mechanism_complete", "target_mechanism"),
    ("no_postcompletion_violation", "postcompletion_control"),
)

PUBLIC_CONDITION_TEXT: dict[PathStrategy, str] = {
    "structured_direct": (
        "When the public selectors are sufficient, prefer direct typed record selection "
        "without preliminary archive discovery."
    ),
    "search_then_structured": (
        "Use broad public discovery to identify candidate records, then bind chosen Evidence "
        "through exact typed record selection before calculation."
    ),
    "search_then_open": (
        "Use broad public discovery and inspect public document locations to bind Evidence "
        "before calculation."
    ),
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImplementationSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class SourceArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class PublicReachabilityCondition(FrozenModel):
    condition_id: str = Field(min_length=1)
    strategy: PathStrategy
    public_payload: dict[str, Any]
    public_payload_hash: str = Field(min_length=1)
    exposes_target_state_id: Literal[False] = False
    exposes_static_path_id: Literal[False] = False
    exposes_compiler_witness_id: Literal[False] = False
    exposes_gold_evidence_id: Literal[False] = False
    exposes_hidden_program: Literal[False] = False
    exposes_complete_action_sequence: Literal[False] = False
    schema_version: str = V26_REACHABILITY_CONDITION_VERSION

    @model_validator(mode="after")
    def validate_condition(self) -> PublicReachabilityCondition:
        if self.public_payload != public_reachability_condition_payload(self.strategy):
            raise ValueError("public reachability condition differs from its frozen strategy")
        if self.public_payload_hash != canonical_hash(
            self.public_payload,
            prefix="finance_v26_public_reachability_condition_payload:",
        ):
            raise ValueError("public reachability condition payload hash is invalid")
        serialized = json.dumps(self.public_payload, ensure_ascii=False, sort_keys=True).casefold()
        forbidden = (
            "quotient_state",
            "state_id",
            "path_id",
            "compiler_witness",
            "gold_evidence",
            "hidden_program",
            "action_sequence",
            "tool_sequence",
            "evidence:finance:",
        )
        if any(item in serialized for item in forbidden):
            raise ValueError("public reachability condition exposes a forbidden identity")
        if self.condition_id != public_reachability_condition_id(self):
            raise ValueError("public reachability condition identity is invalid")
        return self


class ReachabilityConditionScaffold(PublicAgentScaffoldCompiler):
    """Broad public behavior guidance rather than a compiler path recipe."""

    def __init__(self, condition: PublicReachabilityCondition) -> None:
        self._condition = condition

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(
            {
                "version": V26_REACHABILITY_CONDITION_VERSION,
                "condition_id": self._condition.condition_id,
                "public_payload_hash": self._condition.public_payload_hash,
                "dynamic_fields": (),
            },
            prefix="finance_v26_reachability_scaffold_manifest:",
        )

    def compile_public_context(
        self,
        *,
        task: Any,
        tool_environment: Mapping[str, Any],
        observations: tuple[AgentToolObservation, ...],
        stop_rejections: tuple[Any, ...],
    ) -> Mapping[str, Any]:
        del task, tool_environment, observations, stop_rejections
        return dict(self._condition.public_payload)


class EmpiricalSupportPilotContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=4)
    source_capability_task_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    source_vtdo_candidate_task_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    source_static_state_ids: tuple[str, ...] = Field(min_length=36, max_length=36)
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, Any]
    provider_route_hash: str = Field(min_length=1)
    capability_rollouts_per_task: Literal[8] = CAPABILITY_ROLLOUTS_PER_TASK
    natural_rollouts_per_task: Literal[12] = NATURAL_ROLLOUTS_PER_TASK
    conditioned_rollouts_per_state: Literal[6] = CONDITIONED_ROLLOUTS_PER_STATE
    capability_job_count: Literal[96] = 96
    natural_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    expected_rollout_count: Literal[456] = 456
    minimum_released_realizations_per_state: Literal[3] = MINIMUM_RELEASED_REALIZATIONS
    maximum_estimated_attempts_for_three: float = MAXIMUM_ESTIMATED_ATTEMPTS_FOR_THREE
    maximum_total_model_tokens_per_rollout: int = MAXIMUM_TOTAL_MODEL_TOKENS
    maximum_total_estimated_cost_usd: float = MAXIMUM_TOTAL_ESTIMATED_COST_USD
    verifier_manifest: dict[str, Any]
    verifier_manifest_hash: str = Field(min_length=1)
    mapper_manifest: dict[str, Any]
    mapper_manifest_hash: str = Field(min_length=1)
    condition_manifest: dict[str, Any]
    condition_manifest_hash: str = Field(min_length=1)
    compiler_witnesses_excluded_from_empirical_counts: Literal[True] = True
    capability_and_reachability_denominators_separate: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    natural_and_conditioned_hits_separate: Literal[True] = True
    task_is_primary_sampling_unit: Literal[True] = True
    rollout_is_secondary_sampling_unit: Literal[True] = True
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    implementation_source_files: tuple[ImplementationSourceFile, ...]
    schema_version: str = V26_EMPIRICAL_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> EmpiricalSupportPilotContract:
        if self.source_capability_task_ids != tuple(sorted(set(self.source_capability_task_ids))):
            raise ValueError("capability task identities are not canonical")
        if self.source_vtdo_candidate_task_ids != tuple(
            sorted(set(self.source_vtdo_candidate_task_ids))
        ):
            raise ValueError("VTDO candidate task identities are not canonical")
        if set(self.source_capability_task_ids) & set(self.source_vtdo_candidate_task_ids):
            raise ValueError("capability and VTDO task roles overlap")
        if self.source_static_state_ids != tuple(sorted(set(self.source_static_state_ids))):
            raise ValueError("static state identities are not canonical")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("pilot model config differs from frozen Flash identity")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != self.fallback_models:
            raise ValueError("pilot fallback model contract is inconsistent")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("pilot must fail closed on requested-model mismatch")
        manifests = (
            ("model_config", self.model_invocation_config, self.model_config_hash),
            ("provider_route", self.provider_route, self.provider_route_hash),
            ("verifier", self.verifier_manifest, self.verifier_manifest_hash),
            ("mapper", self.mapper_manifest, self.mapper_manifest_hash),
            ("condition", self.condition_manifest, self.condition_manifest_hash),
        )
        for label, payload, observed in manifests:
            expected = canonical_hash(payload, prefix=f"finance_v26_empirical_{label}:")
            if observed != expected:
                raise ValueError(f"pilot {label} hash is invalid")
        implementation_paths = tuple(
            sorted(item.relative_path for item in self.implementation_source_files)
        )
        if implementation_paths != tuple(sorted(IMPLEMENTATION_SOURCE_PATHS)):
            raise ValueError("pilot implementation source manifest is incomplete")
        if len(implementation_paths) != len(set(implementation_paths)):
            raise ValueError("pilot implementation source manifest is duplicated")
        if self.contract_id != empirical_support_pilot_contract_id(self):
            raise ValueError("empirical support pilot contract identity is invalid")
        return self


class EmpiricalPilotJob(FrozenModel):
    job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    intended_use: Literal["capability_measurement", "vtdo_multistate_candidate"]
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0)
    requested_static_path_id: str | None = None
    requested_path_strategy: PathStrategy | None = None
    requested_quotient_state_id: str | None = None
    public_condition_id: str | None = None
    schema_version: str = V26_EMPIRICAL_SUPPORT_PILOT_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> EmpiricalPilotJob:
        conditioned = self.sampling_mode == "reachability_conditioned"
        condition_values = (
            self.requested_static_path_id,
            self.requested_path_strategy,
            self.requested_quotient_state_id,
            self.public_condition_id,
        )
        if conditioned and not all(value is not None for value in condition_values):
            raise ValueError("conditioned job identity is incomplete")
        if not conditioned and any(value is not None for value in condition_values):
            raise ValueError("unconditional job unexpectedly carries a target state")
        if self.sampling_mode == "capability_unconditional":
            if self.intended_use != "capability_measurement" or self.replicate_index >= 8:
                raise ValueError("capability job role or replicate is invalid")
        elif self.intended_use != "vtdo_multistate_candidate":
            raise ValueError("reachability job does not use a VTDO candidate")
        elif self.sampling_mode == "reachability_unconditional" and self.replicate_index >= 12:
            raise ValueError("natural reachability replicate exceeds its denominator")
        elif conditioned and self.replicate_index >= 6:
            raise ValueError("conditioned reachability replicate exceeds its denominator")
        if self.job_id != empirical_pilot_job_id(self):
            raise ValueError("empirical pilot job identity is invalid")
        return self


class EmpiricalPilotJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    jobs: tuple[EmpiricalPilotJob, ...] = Field(min_length=456, max_length=456)
    schema_version: str = V26_EMPIRICAL_SUPPORT_PILOT_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> EmpiricalPilotJobManifest:
        if any(item.contract_id != self.contract_id for item in self.jobs):
            raise ValueError("job manifest crosses pilot contracts")
        ids = tuple(item.job_id for item in self.jobs)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("job manifest identities are not canonical")
        modes = Counter(item.sampling_mode for item in self.jobs)
        if modes != Counter(
            {
                "capability_unconditional": 96,
                "reachability_unconditional": 144,
                "reachability_conditioned": 216,
            }
        ):
            raise ValueError("job manifest denominators are incomplete")
        if self.manifest_id != empirical_pilot_job_manifest_id(self):
            raise ValueError("empirical pilot job manifest identity is invalid")
        return self


class MechanismEstimandOutcome(FrozenModel):
    mechanism_id: TargetMechanism
    estimand_id: str = Field(min_length=1)
    evaluated: bool
    success: bool
    observed_event_ids: tuple[str, ...]
    missing_event_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_outcome(self) -> MechanismEstimandOutcome:
        if self.success and not self.evaluated:
            raise ValueError("unevaluated mechanism estimand cannot pass")
        if self.success == bool(self.missing_event_ids):
            raise ValueError("mechanism success differs from missing events")
        if self.observed_event_ids != tuple(sorted(set(self.observed_event_ids))):
            raise ValueError("mechanism events are not canonical")
        return self


class ExecutableAgentVerificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    verifier_binding_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    checks: dict[str, bool]
    selected_evidence_ids: tuple[str, ...]
    operation_lineage_evidence_ids: tuple[str, ...]
    verification_support_ids: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    satisfying_selected_support_set_id: str | None = None
    satisfying_citation_support_set_id: str | None = None
    mechanism_event_ids: tuple[str, ...]
    normalized_answer: dict[str, Any]
    matched_program_node_ids: tuple[str, ...]
    earliest_failure_stage: str | None = None
    valid: bool
    verifier_implementation_id: Literal["core.executable_task_verifier"] = (
        "core.executable_task_verifier"
    )
    verifier_version: Literal["executable_task_verifier.v1"] = (
        V26_EMPIRICAL_EXECUTABLE_VERIFIER_VERSION
    )
    schema_version: str = V26_EMPIRICAL_SUPPORT_PILOT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ExecutableAgentVerificationReport:
        if set(self.checks) != set(VERIFICATION_CHECK_IDS):
            raise ValueError("empirical executable verification Gate vector is incomplete")
        if self.valid != all(self.checks.values()):
            raise ValueError("empirical executable verification validity is inconsistent")
        if self.earliest_failure_stage != _earliest_failure_stage(self.checks):
            raise ValueError("empirical executable verification failure stage is inconsistent")
        if self.report_id != executable_agent_verification_report_id(self):
            raise ValueError("empirical executable verification identity is invalid")
        return self


class EmpiricalPathAssignment(FrozenModel):
    assignment_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    static_path_id: str = Field(min_length=1)
    path_strategy: PathStrategy
    quotient_state_id: str = Field(min_length=1)
    successful_precalculation_tool_ids: tuple[str, ...]
    mapping_rule: Literal["open_precedes_search_precedes_direct_on_valid_trajectory"] = (
        "open_precedes_search_precedes_direct_on_valid_trajectory"
    )
    model_generated: Literal[True] = True
    compiler_witness_counted: Literal[False] = False
    mapper_version: str = V26_EMPIRICAL_PATH_MAPPER_VERSION

    @model_validator(mode="after")
    def validate_assignment(self) -> EmpiricalPathAssignment:
        if self.assignment_id != empirical_path_assignment_id(self):
            raise ValueError("empirical path assignment identity is invalid")
        return self


class EmpiricalPilotRollout(FrozenModel):
    rollout_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_record_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    intended_use: Literal["capability_measurement", "vtdo_multistate_candidate"]
    sampling_mode: SamplingMode
    replicate_index: int = Field(ge=0)
    requested_static_path_id: str | None = None
    requested_path_strategy: PathStrategy | None = None
    requested_quotient_state_id: str | None = None
    public_condition_id: str | None = None
    terminal_category: RolloutTerminal
    provider_call_ids: tuple[str, ...]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    provider_usage_complete: bool
    estimated_cost_usd: str
    exact_requested_model: bool
    fallback_used: bool
    actual_prompt_hashes: tuple[str, ...]
    recursive_noninterference_passed: bool
    condition_noninterference_passed: bool
    verification: ExecutableAgentVerificationReport | None = None
    mechanism_estimand: MechanismEstimandOutcome
    path_assignment: EmpiricalPathAssignment | None = None
    trajectory_id: str | None = None
    trajectory_content_hash: str | None = None
    decision_trace_hash: str | None = None
    model_generated: bool
    raw_artifact_uri: str = Field(min_length=1)
    raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    failure_attribution: dict[str, Any] | None = None
    schema_version: str = V26_EMPIRICAL_SUPPORT_PILOT_VERSION

    @model_validator(mode="after")
    def validate_rollout(self) -> EmpiricalPilotRollout:
        conditioned = self.sampling_mode == "reachability_conditioned"
        requested = (
            self.requested_static_path_id,
            self.requested_path_strategy,
            self.requested_quotient_state_id,
            self.public_condition_id,
        )
        if conditioned != all(value is not None for value in requested):
            raise ValueError("typed rollout loses its conditioned target identity")
        if not conditioned and any(value is not None for value in requested):
            raise ValueError("unconditional rollout unexpectedly carries a target state")
        valid = bool(self.verification and self.verification.valid)
        if valid != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("rollout terminal differs from independent verification")
        if self.path_assignment is not None:
            if not valid or self.intended_use != "vtdo_multistate_candidate":
                raise ValueError("path assignment requires a valid VTDO candidate trajectory")
            if self.path_assignment.task_package_id != self.task_package_id:
                raise ValueError("path assignment crosses task identities")
            if self.path_assignment.trajectory_id != self.trajectory_id:
                raise ValueError("path assignment crosses trajectory identities")
        if self.provider_call_count != len(self.provider_call_ids):
            raise ValueError("Provider call accounting is inconsistent")
        if self.fallback_used or not self.exact_requested_model:
            if self.terminal_category == "model_valid_trajectory":
                raise ValueError("wrong-model rollout cannot be independently valid")
        if self.rollout_id != empirical_pilot_rollout_id(self):
            raise ValueError("empirical pilot rollout identity is invalid")
        return self


class RawArtifactIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    expected_rollout_count: Literal[456] = 456
    observed_rollout_count: int = Field(ge=0, le=456)
    byte_hash_pass_count: int = Field(ge=0)
    identity_pass_count: int = Field(ge=0)
    prompt_hash_pass_count: int = Field(ge=0)
    side_channel_pass_count: int = Field(ge=0)
    noninterference_pass_count: int = Field(ge=0)
    condition_noninterference_pass_count: int = Field(ge=0)
    provider_call_ids_unique: bool
    duplicate_provider_call_ids: tuple[str, ...]
    failed_artifacts: tuple[str, ...]
    status: Literal["passed", "partial", "failed"]

    @model_validator(mode="after")
    def validate_audit(self) -> RawArtifactIntegrityAudit:
        all_pass = (
            self.byte_hash_pass_count
            == self.identity_pass_count
            == self.prompt_hash_pass_count
            == self.side_channel_pass_count
            == self.noninterference_pass_count
            == self.condition_noninterference_pass_count
            == self.observed_rollout_count
        )
        complete = self.observed_rollout_count == self.expected_rollout_count
        expected = (
            "passed"
            if complete and all_pass and self.provider_call_ids_unique and not self.failed_artifacts
            else "partial"
            if all_pass and self.provider_call_ids_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected:
            raise ValueError("raw Artifact integrity status is inconsistent")
        if self.audit_id != raw_artifact_integrity_audit_id(self):
            raise ValueError("raw Artifact integrity audit identity is invalid")
        return self


class CapabilityTaskSummary(FrozenModel):
    task_package_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    attempted_count: Literal[8] = 8
    runtime_eligible_count: int = Field(ge=0, le=8)
    model_contract_failure_count: int = Field(ge=0, le=8)
    runtime_or_instrument_failure_count: int = Field(ge=0, le=8)
    mechanism_evaluable_count: int = Field(ge=0, le=8)
    mechanism_success_count: int = Field(ge=0, le=8)
    independent_valid_count: int = Field(ge=0, le=8)
    mechanism_success_rate: float = Field(ge=0, le=1)
    valid_rate: float = Field(ge=0, le=1)
    valid_given_mechanism_success_rate: float | None = Field(default=None, ge=0, le=1)
    mechanism_wilson_lcb95: float = Field(ge=0, le=1)
    mechanism_wilson_ucb95: float = Field(ge=0, le=1)
    valid_wilson_lcb95: float = Field(ge=0, le=1)
    valid_wilson_ucb95: float = Field(ge=0, le=1)
    boundary_response: bool
    earliest_failure_stage_counts: dict[str, int]


class CapabilityMechanismSummary(FrozenModel):
    mechanism_id: TargetMechanism
    task_count: Literal[3] = 3
    rollout_count: Literal[24] = 24
    mechanism_success_count: int = Field(ge=0, le=24)
    independent_valid_count: int = Field(ge=0, le=24)
    boundary_task_count: int = Field(ge=0, le=3)
    task_mechanism_success_range: tuple[float, float]
    task_validity_range: tuple[float, float]


class StateReachabilitySummary(FrozenModel):
    task_package_id: str = Field(min_length=1)
    static_path_id: str = Field(min_length=1)
    path_strategy: PathStrategy
    quotient_state_id: str = Field(min_length=1)
    natural_attempted_count: Literal[12] = 12
    natural_valid_count: int = Field(ge=0, le=12)
    natural_on_state_hit_count: int = Field(ge=0, le=12)
    requested_count: Literal[6] = 6
    conditioned_attempted_count: Literal[6] = 6
    conditioned_valid_count: int = Field(ge=0, le=6)
    conditioned_on_target_count: int = Field(ge=0, le=6)
    conditioned_off_target_count: int = Field(ge=0, le=6)
    conditioned_valid_unmapped_count: int = Field(ge=0, le=6)
    duplicate_content_count: int = Field(ge=0, le=6)
    duplicate_decision_trace_count: int = Field(ge=0, le=6)
    released_count: int = Field(ge=0, le=6)
    released_rollout_ids: tuple[str, ...]
    conditioned_acceptance_rate: float = Field(ge=0, le=1)
    conditioned_acceptance_lcb95: float = Field(ge=0, le=1)
    conditioned_acceptance_ucb95: float = Field(ge=0, le=1)
    estimated_attempts_for_three_releases: float | None = Field(default=None, ge=0)
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str
    natural_hit_passed: bool
    conditioned_lcb_passed: bool
    independent_realization_yield_passed: bool
    stable_remapping_passed: bool
    model_generated_only_passed: bool
    budget_passed: bool
    admitted: bool
    blockers: tuple[str, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> StateReachabilitySummary:
        if self.released_count != len(self.released_rollout_ids):
            raise ValueError("released realization accounting is inconsistent")
        checks = (
            self.natural_hit_passed,
            self.conditioned_lcb_passed,
            self.independent_realization_yield_passed,
            self.stable_remapping_passed,
            self.model_generated_only_passed,
            self.budget_passed,
        )
        if self.admitted != all(checks):
            raise ValueError("state admission differs from its frozen Gate vector")
        if self.admitted == bool(self.blockers):
            raise ValueError("state blockers differ from admission")
        return self


class TaskStateSupportSummary(FrozenModel):
    task_package_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    registered_state_count: Literal[3] = 3
    admitted_state_count: int = Field(ge=0, le=3)
    admitted_state_ids: tuple[str, ...]
    all_three_states_admitted: bool

    @model_validator(mode="after")
    def validate_task_summary(self) -> TaskStateSupportSummary:
        if self.admitted_state_count != len(self.admitted_state_ids):
            raise ValueError("task state-support count is inconsistent")
        if self.all_three_states_admitted != (self.admitted_state_count == 3):
            raise ValueError("task three-state admission is inconsistent")
        return self


class EmpiricalStateSupportFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_summaries: tuple[TaskStateSupportSummary, ...] = Field(min_length=12, max_length=12)
    admitted_task_count: int = Field(ge=0, le=12)
    global_support_admitted: bool
    compiler_witness_count: Literal[0] = 0
    status: Literal["admitted", "blocked"]
    next_transition: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_freeze(self) -> EmpiricalStateSupportFreeze:
        count = sum(item.all_three_states_admitted for item in self.task_summaries)
        if self.admitted_task_count != count:
            raise ValueError("state-support Freeze task count is inconsistent")
        if self.global_support_admitted != (count == 12):
            raise ValueError("global state support does not require all frozen candidates")
        if self.status != ("admitted" if self.global_support_admitted else "blocked"):
            raise ValueError("state-support Freeze status is inconsistent")
        if self.freeze_id != empirical_state_support_freeze_id(self):
            raise ValueError("empirical state-support Freeze identity is invalid")
        return self


class EmpiricalSupportPilotReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_manifest_id: str = Field(min_length=1)
    discovered_models: tuple[str, ...]
    expected_rollout_count: Literal[456] = 456
    completed_rollout_count: int = Field(ge=0, le=456)
    sampling_mode_counts: dict[str, int]
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    provider_total_tokens: int = Field(ge=0)
    estimated_cost_usd: str
    raw_integrity_audit: RawArtifactIntegrityAudit
    capability_task_summaries: tuple[CapabilityTaskSummary, ...]
    capability_mechanism_summaries: tuple[CapabilityMechanismSummary, ...]
    state_reachability_summaries: tuple[StateReachabilitySummary, ...]
    state_support_freeze: EmpiricalStateSupportFreeze | None = None
    capability_development_complete: bool
    state_reachability_complete: bool
    status: PilotStatus
    next_permitted_stage: str = Field(min_length=1)
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_EMPIRICAL_SUPPORT_PILOT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> EmpiricalSupportPilotReport:
        if sum(self.sampling_mode_counts.values()) != self.completed_rollout_count:
            raise ValueError("pilot sampling-mode denominator is inconsistent")
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("pilot terminal denominator is inconsistent")
        if self.capability_development_complete != (
            self.sampling_mode_counts.get("capability_unconditional", 0) == 96
        ):
            raise ValueError("capability Development completion is inconsistent")
        reachability_complete = (
            self.sampling_mode_counts.get("reachability_unconditional", 0) == 144
            and self.sampling_mode_counts.get("reachability_conditioned", 0) == 216
        )
        if self.state_reachability_complete != reachability_complete:
            raise ValueError("state Reachability completion is inconsistent")
        if self.state_support_freeze is not None and not reachability_complete:
            raise ValueError("partial Reachability cannot produce a state-support Freeze")
        if self.report_id != empirical_support_pilot_report_id(self):
            raise ValueError("empirical support pilot report identity is invalid")
        return self


def public_reachability_condition_payload(strategy: PathStrategy) -> dict[str, Any]:
    return {
        "condition_version": V26_REACHABILITY_CONDITION_VERSION,
        "behavior_axis": "public_evidence_acquisition_style",
        "behavior_request": PUBLIC_CONDITION_TEXT[strategy],
        "public_constraints": [
            "Use only task-visible selectors and public tool observations.",
            "Keep calculation, verification, recovery, and stopping decisions model-owned.",
            "Return an answer only after the public completion requirements are satisfied.",
        ],
        "posthoc_acceptance": (
            "The Host independently verifies complete validity and acquisition behavior."
        ),
    }


def make_public_reachability_condition(strategy: PathStrategy) -> PublicReachabilityCondition:
    payload = public_reachability_condition_payload(strategy)
    values = {
        "strategy": strategy,
        "public_payload": payload,
        "public_payload_hash": canonical_hash(
            payload,
            prefix="finance_v26_public_reachability_condition_payload:",
        ),
    }
    provisional = PublicReachabilityCondition.model_construct(condition_id="pending", **values)
    return PublicReachabilityCondition(
        condition_id=public_reachability_condition_id(provisional),
        **values,
    )


def public_reachability_condition_id(value: PublicReachabilityCondition) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"condition_id"}),
        prefix="finance_v26_public_reachability_condition:",
    )


def empirical_support_pilot_contract_id(value: EmpiricalSupportPilotContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_empirical_support_contract:",
    )


def empirical_pilot_job_id(value: EmpiricalPilotJob) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"job_id"}),
        prefix="finance_v26_empirical_pilot_job:",
    )


def empirical_pilot_job_manifest_id(value: EmpiricalPilotJobManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_empirical_pilot_job_manifest:",
    )


def executable_agent_verification_report_id(
    value: ExecutableAgentVerificationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_empirical_executable_verification:",
    )


def empirical_path_assignment_id(value: EmpiricalPathAssignment) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"assignment_id"}),
        prefix="finance_v26_empirical_path_assignment:",
    )


def empirical_pilot_rollout_id(value: EmpiricalPilotRollout) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"rollout_id"}),
        prefix="finance_v26_empirical_pilot_rollout:",
    )


def raw_artifact_integrity_audit_id(value: RawArtifactIntegrityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_empirical_raw_integrity_audit:",
    )


def empirical_state_support_freeze_id(value: EmpiricalStateSupportFreeze) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"freeze_id"}),
        prefix="finance_v26_empirical_state_support_freeze:",
    )


def empirical_support_pilot_report_id(value: EmpiricalSupportPilotReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_empirical_support_pilot_report:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=relative, sha256=_sha256(package_root / relative))
        for relative in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def load_v26_56_inputs(
    source_dir: Path,
) -> tuple[
    V26ExecutableTaskRematerializationReport,
    tuple[RematerializedExecutableTaskRecord, ...],
    tuple[AgentToolEnvironmentManifest, ...],
    tuple[StaticModelAuthorityPathCatalog, ...],
    tuple[ExecutableTaskAdmission, ...],
]:
    report_path = source_dir / "report.json"
    report = V26ExecutableTaskRematerializationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if not (
        report.status == "passed"
        and report.capability_development_authorized
        and report.state_reachability_pilot_authorized
        and not report.fresh_confirmation_authorized
    ):
        raise ValueError("v26.56 report does not authorize the empirical Pilot")
    descriptors = {item.relative_path: item for item in report.immutable_artifact_files}
    required = {
        "rematerialized_task_records.json",
        "tool_environment_manifests.json",
        "static_model_authority_path_catalogs.json",
        "task_admissions.json",
    }
    if not required <= set(descriptors):
        raise ValueError("v26.56 source Artifact manifest is incomplete")
    for relative, descriptor in descriptors.items():
        path = source_dir / relative
        if not path.is_file() or _sha256(path) != descriptor.sha256:
            raise ValueError(f"v26.56 source Artifact replay failed: {relative}")

    records = tuple(
        RematerializedExecutableTaskRecord.model_validate(item)
        for item in json.loads(
            (source_dir / "rematerialized_task_records.json").read_text(encoding="utf-8")
        )
    )
    environments = tuple(
        AgentToolEnvironmentManifest.model_validate(item)
        for item in json.loads(
            (source_dir / "tool_environment_manifests.json").read_text(encoding="utf-8")
        )
    )
    catalogs = tuple(
        StaticModelAuthorityPathCatalog.model_validate(item)
        for item in json.loads(
            (source_dir / "static_model_authority_path_catalogs.json").read_text(encoding="utf-8")
        )
    )
    admissions = tuple(
        ExecutableTaskAdmission.model_validate(item)
        for item in json.loads((source_dir / "task_admissions.json").read_text(encoding="utf-8"))
    )
    if not (len(records) == len(environments) == len(catalogs) == len(admissions) == 24):
        raise ValueError("v26.56 empirical source bundle cardinality is invalid")
    report_records = {item.record_id: item for item in report.task_records}
    if {item.record_id: item for item in records} != report_records:
        raise ValueError("v26.56 detail task records differ from the frozen report")
    environment_ids = {item.manifest_id for item in environments}
    if {item.environment_manifest_id for item in records} != environment_ids:
        raise ValueError("v26.56 environment identities are incomplete or extraneous")
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    admission_by_task = {item.task_package_id: item for item in admissions}
    if len(catalog_by_task) != 24 or len(admission_by_task) != 24:
        raise ValueError("v26.56 task catalogs or admissions are duplicated")
    for record in records:
        task_id = record.task_package.package_id
        catalog = catalog_by_task[task_id]
        admission = admission_by_task[task_id]
        if record.intended_use == "capability_measurement":
            if catalog.status != "not_required" or not admission.capability_measurement_eligible:
                raise ValueError("v26.56 capability task is not statically admitted")
        elif catalog.status != "passed" or not admission.static_vtdo_candidate_eligible:
            raise ValueError("v26.56 VTDO candidate is not statically admitted")
    return report, records, environments, catalogs, admissions


def build_empirical_support_pilot_contract(
    *,
    run_id: str,
    source_dir: Path,
    model_config: AgentModelConfig,
    package_root: Path,
) -> EmpiricalSupportPilotContract:
    report, records, _, catalogs, _ = load_v26_56_inputs(source_dir)
    capability_ids = tuple(
        sorted(
            item.task_package.package_id
            for item in records
            if item.intended_use == "capability_measurement"
        )
    )
    vtdo_ids = tuple(
        sorted(
            item.task_package.package_id
            for item in records
            if item.intended_use == "vtdo_multistate_candidate"
        )
    )
    states = tuple(sorted(path.quotient_state_id for item in catalogs for path in item.paths))
    source_files = tuple(
        SourceArtifactFile(
            relative_path=item.relative_path,
            sha256=item.sha256,
            record_count=item.record_count,
        )
        for item in sorted(report.immutable_artifact_files, key=lambda value: value.relative_path)
        if item.relative_path
        in {
            "rematerialized_task_records.json",
            "tool_environment_manifests.json",
            "static_model_authority_path_catalogs.json",
            "task_admissions.json",
        }
    )
    public_model = model_config.model_dump(mode="json")
    provider_route = {
        "provider": model_config.provider,
        "endpoint_host": model_config.endpoint.split("//", 1)[-1].split("/", 1)[0],
        "model": model_config.model,
    }
    verifier = {
        "implementation_id": "core.executable_task_verifier",
        "version": V26_EMPIRICAL_EXECUTABLE_VERIFIER_VERSION,
        "runtime_id": FINANCE_EXECUTABLE_SUPPORT_RUNTIME_ID,
        "runtime_version": FINANCE_EXECUTABLE_SUPPORT_RUNTIME_VERSION,
        "check_ids": VERIFICATION_CHECK_IDS,
        "failure_stage_order": tuple(item[1] for item in FAILURE_STAGE_ORDER),
        "citation_rule": "contains_registered_sufficient_set",
        "exact_gold_equality": False,
        "complete_invalid_outcomes_retained": True,
    }
    mapper = {
        "version": V26_EMPIRICAL_PATH_MAPPER_VERSION,
        "eligible_input": "independently_valid_model_generated_trajectory_only",
        "classification_precedence": (
            "successful_open_document_before_first_calculation",
            "successful_search_archive_before_first_calculation",
            "successful_query_structured_fact_before_first_calculation",
        ),
        "state_identity_source": "frozen_v26_56_static_catalog",
        "compiler_witness_counted": False,
    }
    conditions = tuple(make_public_reachability_condition(item) for item in PATH_STRATEGIES)
    condition = {
        "version": V26_REACHABILITY_CONDITION_VERSION,
        "conditions": [item.model_dump(mode="json") for item in conditions],
        "forbidden_disclosures": (
            "target_state_id",
            "static_path_id",
            "compiler_witness_id",
            "Gold Evidence ID",
            "hidden Program",
            "complete action sequence",
        ),
        "posthoc_acceptance": "independent validity and empirical mapper agreement",
    }
    values: dict[str, Any] = {
        "run_id": run_id,
        "source_report_id": report.report_id,
        "source_report_sha256": _sha256(source_dir / "report.json"),
        "source_artifact_files": source_files,
        "source_capability_task_ids": capability_ids,
        "source_vtdo_candidate_task_ids": vtdo_ids,
        "source_static_state_ids": states,
        "model_invocation_config": public_model,
        "model_config_hash": canonical_hash(
            public_model, prefix="finance_v26_empirical_model_config:"
        ),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(
            provider_route, prefix="finance_v26_empirical_provider_route:"
        ),
        "verifier_manifest": verifier,
        "verifier_manifest_hash": canonical_hash(
            verifier, prefix="finance_v26_empirical_verifier:"
        ),
        "mapper_manifest": mapper,
        "mapper_manifest_hash": canonical_hash(mapper, prefix="finance_v26_empirical_mapper:"),
        "condition_manifest": condition,
        "condition_manifest_hash": canonical_hash(
            condition, prefix="finance_v26_empirical_condition:"
        ),
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = EmpiricalSupportPilotContract.model_construct(contract_id="pending", **values)
    return EmpiricalSupportPilotContract(
        contract_id=empirical_support_pilot_contract_id(provisional),
        **values,
    )


def build_empirical_pilot_job_manifest(
    contract: EmpiricalSupportPilotContract,
    records: Sequence[RematerializedExecutableTaskRecord],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
) -> EmpiricalPilotJobManifest:
    catalog_by_task = {item.task_package_id: item for item in catalogs}
    conditions = {item: make_public_reachability_condition(item) for item in PATH_STRATEGIES}
    jobs: list[EmpiricalPilotJob] = []

    def add(values: dict[str, Any]) -> None:
        provisional = EmpiricalPilotJob.model_construct(job_id="pending", **values)
        jobs.append(EmpiricalPilotJob(job_id=empirical_pilot_job_id(provisional), **values))

    for record in sorted(records, key=lambda item: item.task_package.package_id):
        common = {
            "contract_id": contract.contract_id,
            "task_record_id": record.record_id,
            "task_package_id": record.task_package.package_id,
            "mechanism_id": record.mechanism_id,
            "intended_use": record.intended_use,
        }
        if record.intended_use == "capability_measurement":
            for replicate in range(CAPABILITY_ROLLOUTS_PER_TASK):
                add(
                    {
                        **common,
                        "sampling_mode": "capability_unconditional",
                        "replicate_index": replicate,
                    }
                )
            continue
        for replicate in range(NATURAL_ROLLOUTS_PER_TASK):
            add(
                {
                    **common,
                    "sampling_mode": "reachability_unconditional",
                    "replicate_index": replicate,
                }
            )
        catalog = catalog_by_task[record.task_package.package_id]
        paths = {cast(PathStrategy, item.path_strategy_id): item for item in catalog.paths}
        if set(paths) != set(PATH_STRATEGIES):
            raise ValueError("VTDO candidate lacks the three frozen path strategies")
        for strategy in PATH_STRATEGIES:
            path = paths[strategy]
            condition = conditions[strategy]
            for replicate in range(CONDITIONED_ROLLOUTS_PER_STATE):
                add(
                    {
                        **common,
                        "sampling_mode": "reachability_conditioned",
                        "replicate_index": replicate,
                        "requested_static_path_id": path.path_id,
                        "requested_path_strategy": strategy,
                        "requested_quotient_state_id": path.quotient_state_id,
                        "public_condition_id": condition.condition_id,
                    }
                )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    values = {"contract_id": contract.contract_id, "jobs": ordered}
    provisional = EmpiricalPilotJobManifest.model_construct(manifest_id="pending", **values)
    return EmpiricalPilotJobManifest(
        manifest_id=empirical_pilot_job_manifest_id(provisional),
        **values,
    )


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


def _call_signature(observation: AgentToolObservation) -> str:
    return canonical_hash(
        {
            "tool_id": observation.call.tool_id,
            "arguments": observation.call.arguments,
        },
        prefix="finance_v26_empirical_failed_call:",
    )


def replay_empirical_observations(
    record: RematerializedExecutableTaskRecord,
    environment: AgentToolEnvironmentManifest,
    observations: Sequence[AgentToolObservation],
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
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
    failures: list[str] = []
    failed_signatures: set[str] = set()
    for index, observation in enumerate(observations):
        if observation.environment_manifest_id != environment.manifest_id:
            failures.append(f"observation:{index}:environment_identity")
            continue
        spec = environment.tools_by_id.get(observation.call.tool_id)
        if spec is None:
            failures.append(f"observation:{index}:unknown_tool")
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
                error_message=("The Host blocked an identical failed action without executing it."),
            )
        else:
            replayed = agent_tool_argument_rejection(spec, observation.call) or runtime.execute(
                observation.call
            )
        if replayed.status == "succeeded":
            try:
                spec.validate_output(replayed.result)
            except ValueError as exc:
                failures.append(f"observation:{index}:output_contract:{exc}")
        if _tool_result_payload(replayed) != _tool_result_payload(observation):
            failures.append(f"observation:{index}:replay_mismatch")
        if observation.status == "succeeded":
            failed_signatures.clear()
        else:
            failed_signatures.add(signature)
    return not failures, tuple(sorted(runtime.selected_evidence_ids)), tuple(failures)


def _successful_observations(
    observations: Sequence[AgentToolObservation], tool_id: str
) -> tuple[AgentToolObservation, ...]:
    return tuple(
        item for item in observations if item.call.tool_id == tool_id and item.status == "succeeded"
    )


def evaluate_mechanism_estimand(
    record: RematerializedExecutableTaskRecord,
    observations: Sequence[AgentToolObservation],
    *,
    stopped_by_model: bool,
) -> MechanismEstimandOutcome:
    events: set[str] = set()
    mechanism = record.mechanism_id
    calculators = _successful_observations(observations, "calculator")
    normalizers = _successful_observations(observations, "normalize_metric_unit_period")
    verifiers = tuple(
        item
        for item in _successful_observations(observations, "cross_check_evidence")
        if item.result.get("verified") is True
    )
    if mechanism == "context_conditioned_action":
        evaluated = bool(calculators)
        if calculators and calculators[0].call.arguments.get("operator") == (
            record.mechanism_private_state.get("expected_first_action")
        ):
            events.add("context_action_selected")
        estimand_id = "irreversible_context_action_selected"
    elif mechanism == "semantic_reconciliation":
        evaluated = bool(normalizers or calculators)
        normalized_refs = {
            str(item.result.get("normalized_operation_ref"))
            for item in normalizers
            if item.result.get("normalized_operation_ref")
        }
        if len(normalized_refs) >= 2:
            events.add("normalization_reference_emitted")
        consumed = {
            str(operand.get("operation_ref"))
            for item in calculators
            for operand in item.call.arguments.get("operands", ())
            if isinstance(operand, Mapping) and operand.get("operation_ref") in normalized_refs
        }
        if normalized_refs and consumed == normalized_refs:
            events.add("normalization_reference_consumed")
        estimand_id = "normalization_reference_chain_complete"
    elif mechanism == "failure_recovery":
        failures = tuple(
            (index, item)
            for index, item in enumerate(observations)
            if item.call.tool_id == "query_structured_fact"
            and item.status == "failed"
            and item.error_code == "typed_selector_requires_refinement"
        )
        evaluated = bool(failures)
        if failures:
            events.add("typed_failure_observed")
            first_index, first = failures[0]
            later = tuple(
                item
                for item in observations[first_index + 1 :]
                if item.call.tool_id == "query_structured_fact"
                and item.call.arguments != first.call.arguments
            )
            if later:
                events.add("selector_revised")
            if any(item.status == "succeeded" for item in later):
                events.add("recovery_succeeded")
        estimand_id = "typed_failure_recovery_complete"
    else:
        evaluated = bool(verifiers)
        if verifiers:
            events.add("completion_verified")
            final_verification_index = max(
                index for index, item in enumerate(observations) if item in verifiers
            )
            if stopped_by_model and final_verification_index == len(observations) - 1:
                events.add("stopped_after_completion")
        estimand_id = "verified_completion_then_immediate_stop"
    required = set(record.task_package.mechanism_contract.required_witness_event_ids)
    missing = tuple(sorted(required - events))
    return MechanismEstimandOutcome(
        mechanism_id=mechanism,
        estimand_id=estimand_id,
        evaluated=evaluated,
        success=evaluated and not missing,
        observed_event_ids=tuple(sorted(events)),
        missing_event_ids=missing,
    )


def _normalized_ref_evidence(
    observations: Sequence[AgentToolObservation],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in _successful_observations(observations, "normalize_metric_unit_period"):
        reference = item.result.get("normalized_operation_ref")
        normalized = item.result.get("normalized_values")
        if not reference or not isinstance(normalized, list) or len(normalized) != 1:
            continue
        row = normalized[0]
        if isinstance(row, Mapping) and row.get("evidence_id"):
            values[str(reference)] = str(row["evidence_id"])
    return values


def _operand_matches(
    operand: Any,
    expected_ref: Any,
    operation_refs: Mapping[str, str],
    normalized_refs: Mapping[str, str],
) -> bool:
    if not isinstance(operand, Mapping):
        return False
    if expected_ref.kind == InputRefKind.EVIDENCE:
        if operand.get("evidence_id") == expected_ref.ref_id:
            return True
        operation_ref = operand.get("operation_ref")
        return bool(
            operation_ref
            and normalized_refs.get(str(operation_ref)) == expected_ref.ref_id
            and operand.get("selector") == "normalized_inputs.target"
        )
    expected_operation = operation_refs.get(expected_ref.ref_id)
    return bool(
        expected_operation
        and operand.get("operation_ref") == expected_operation
        and (expected_ref.selector is None or operand.get("selector") == expected_ref.selector)
    )


def match_empirical_program(
    record: RematerializedExecutableTaskRecord,
    observations: Sequence[AgentToolObservation],
) -> tuple[bool, tuple[str, ...], dict[str, str], tuple[str, ...]]:
    calculators = _successful_observations(observations, "calculator")
    normalized_refs = _normalized_ref_evidence(observations)
    operation_refs: dict[str, str] = {}
    runtime_to_node: dict[str, str] = {}
    matched: list[str] = []
    evidence_lineage: set[str] = {
        str(evidence_id)
        for observation in _successful_observations(observations, "normalize_metric_unit_period")
        for evidence_id in observation.evidence_ids
    }
    search_start = 0
    for node in record.task_package.task.oracle.task_program.nodes:
        found = None
        for index in range(search_start, len(calculators)):
            observation = calculators[index]
            arguments = observation.call.arguments
            operands = arguments.get("operands")
            if (
                arguments.get("operator") != node.operator_id
                or arguments.get("parameters") != node.parameters
                or not isinstance(operands, list)
                or len(operands) != len(node.input_refs)
            ):
                continue
            if not all(
                _operand_matches(operand, expected, operation_refs, normalized_refs)
                for operand, expected in zip(operands, node.input_refs, strict=True)
            ):
                continue
            result = observation.result.get("result")
            if not isinstance(result, Mapping) or not result.get("operation_ref"):
                continue
            found = (index, observation, str(result["operation_ref"]))
            break
        if found is None:
            break
        index, observation, operation_ref = found
        search_start = index + 1
        operation_refs[node.node_id] = operation_ref
        runtime_to_node[operation_ref] = node.node_id
        matched.append(node.node_id)
        evidence_lineage.update(str(item) for item in observation.evidence_ids)
    complete = len(matched) == len(record.task_package.task.oracle.task_program.nodes)
    return complete, tuple(matched), runtime_to_node, tuple(sorted(evidence_lineage))


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_references(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_references(item, mapping) for item in value]
    return value


def _project_answer(value: Mapping[str, Any], projection: Mapping[str, str]) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _answer_and_citations(
    result: IterativeAgentSolveResult,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    final = result.trajectory.final_answer
    answer = final.get("result") if isinstance(final, Mapping) else None
    citations = final.get("citations") if isinstance(final, Mapping) else None
    if not isinstance(answer, Mapping) or not isinstance(citations, list):
        return {}, ()
    evidence_ids = tuple(
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, Mapping) and item.get("evidence_id")
    )
    return dict(answer), evidence_ids


def _earliest_failure_stage(checks: Mapping[str, bool]) -> str | None:
    return next((stage for check, stage in FAILURE_STAGE_ORDER if not checks[check]), None)


def verify_empirical_agent_result(
    record: RematerializedExecutableTaskRecord,
    environment: AgentToolEnvironmentManifest,
    result: IterativeAgentSolveResult,
) -> ExecutableAgentVerificationReport:
    replay_passed, selected_ids, _ = replay_empirical_observations(
        record, environment, result.observations
    )
    program_complete, matched_nodes, runtime_to_node, operation_lineage = match_empirical_program(
        record, result.observations
    )
    answer, citations = _answer_and_citations(result)
    normalized_answer = _project_answer(
        cast(dict[str, Any], _replace_runtime_references(answer, runtime_to_node)),
        record.answer_projection,
    )
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(lattice, selected_ids)
    citation_support = matching_sufficient_support_set(lattice, citations)
    verification_support = tuple(
        sorted(
            {
                str(evidence_id)
                for item in _successful_observations(result.observations, "cross_check_evidence")
                if item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )
    mechanism = evaluate_mechanism_estimand(
        record,
        result.observations,
        stopped_by_model=result.audit.stopped_by_model,
    )
    first_verified = next(
        (
            index
            for index, item in enumerate(result.observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    no_postcompletion = first_verified is None or first_verified == len(result.observations) - 1
    necessary = set(lattice.necessary_evidence_ids)
    noninterference = bool(
        result.audit.public_state_condition_hash is None
        and len(result.audit.model_request_prompts)
        == len(result.audit.model_request_prompt_noninterference_attestation_hashes)
    )
    checks = {
        "runtime_replay_passed": replay_passed,
        "model_input_noninterference_passed": noninterference,
        "only_allowed_tools": {item.call.tool_id for item in result.observations}
        <= set(record.task_package.tool_closure.allowed_tool_ids),
        "operation_lineage_complete": program_complete and necessary <= set(operation_lineage),
        "evidence_support_complete": selected_support is not None,
        "verification_complete": necessary <= set(verification_support),
        "answer_projection_complete": normalized_answer == record.projected_expected_output,
        "citation_complete": citation_support is not None,
        "mechanism_complete": mechanism.success,
        "no_postcompletion_violation": no_postcompletion,
    }
    values = {
        "task_package_id": record.task_package.package_id,
        "verifier_binding_id": record.task_package.verifier_binding.binding_id,
        "trajectory_id": result.trajectory.trajectory_id,
        "checks": checks,
        "selected_evidence_ids": selected_ids,
        "operation_lineage_evidence_ids": operation_lineage,
        "verification_support_ids": verification_support,
        "cited_evidence_ids": citations,
        "satisfying_selected_support_set_id": (
            selected_support.support_set_id if selected_support is not None else None
        ),
        "satisfying_citation_support_set_id": (
            citation_support.support_set_id if citation_support is not None else None
        ),
        "mechanism_event_ids": mechanism.observed_event_ids,
        "normalized_answer": normalized_answer,
        "matched_program_node_ids": matched_nodes,
        "earliest_failure_stage": _earliest_failure_stage(checks),
        "valid": all(checks.values()),
    }
    provisional = ExecutableAgentVerificationReport.model_construct(report_id="pending", **values)
    return ExecutableAgentVerificationReport(
        report_id=executable_agent_verification_report_id(provisional),
        **values,
    )


def map_valid_trajectory_to_static_path(
    record: RematerializedExecutableTaskRecord,
    catalog: StaticModelAuthorityPathCatalog,
    result: IterativeAgentSolveResult,
    verification: ExecutableAgentVerificationReport,
) -> EmpiricalPathAssignment | None:
    if not verification.valid or catalog.intended_use != "vtdo_multistate_candidate":
        return None
    successful_before_calculation: list[str] = []
    for item in result.observations:
        if item.call.tool_id == "calculator" and item.status == "succeeded":
            break
        if item.status == "succeeded":
            successful_before_calculation.append(item.call.tool_id)
    tools = set(successful_before_calculation)
    strategy: PathStrategy | None = (
        "search_then_open"
        if "open_document" in tools
        else "search_then_structured"
        if "search_archive" in tools
        else "structured_direct"
        if "query_structured_fact" in tools
        else None
    )
    if strategy is None:
        return None
    paths = {cast(PathStrategy, item.path_strategy_id): item for item in catalog.paths}
    path = paths.get(strategy)
    if path is None:
        return None
    values = {
        "task_package_id": record.task_package.package_id,
        "trajectory_id": result.trajectory.trajectory_id,
        "static_path_id": path.path_id,
        "path_strategy": strategy,
        "quotient_state_id": path.quotient_state_id,
        "successful_precalculation_tool_ids": tuple(successful_before_calculation),
    }
    provisional = EmpiricalPathAssignment.model_construct(assignment_id="pending", **values)
    return EmpiricalPathAssignment(
        assignment_id=empirical_path_assignment_id(provisional),
        **values,
    )


def failure_artifact_mechanism_estimand(
    record: RematerializedExecutableTaskRecord,
    artifact: IterativeAgentFailureArtifact,
) -> MechanismEstimandOutcome:
    return evaluate_mechanism_estimand(
        record,
        artifact.observations,
        stopped_by_model=False,
    )


def wilson_interval(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 1.0
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper


def _rollout_failure_stage(item: EmpiricalPilotRollout) -> str:
    if item.terminal_category == "model_valid_trajectory":
        return "valid"
    if item.verification is not None:
        return item.verification.earliest_failure_stage or "independent_verification"
    if item.terminal_category == "model_invalid_trajectory":
        return "model_contract"
    return item.terminal_category


def aggregate_capability_tasks(
    rollouts: Sequence[EmpiricalPilotRollout],
) -> tuple[CapabilityTaskSummary, ...]:
    rows = [item for item in rollouts if item.sampling_mode == "capability_unconditional"]
    by_task: dict[str, list[EmpiricalPilotRollout]] = {}
    for item in rows:
        by_task.setdefault(item.task_package_id, []).append(item)
    summaries = []
    for task_id, task_rows in sorted(by_task.items()):
        if len(task_rows) != CAPABILITY_ROLLOUTS_PER_TASK:
            raise ValueError("capability task lacks its frozen rollout denominator")
        runtime_eligible = sum(
            item.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in task_rows
        )
        mechanism_evaluable = sum(item.mechanism_estimand.evaluated for item in task_rows)
        mechanism_success = sum(item.mechanism_estimand.success for item in task_rows)
        valid = sum(item.terminal_category == "model_valid_trajectory" for item in task_rows)
        mechanism_interval = wilson_interval(mechanism_success, len(task_rows))
        valid_interval = wilson_interval(valid, len(task_rows))
        mechanism_rate = mechanism_success / len(task_rows)
        valid_rate = valid / len(task_rows)
        failures = Counter(_rollout_failure_stage(item) for item in task_rows)
        summaries.append(
            CapabilityTaskSummary(
                task_package_id=task_id,
                mechanism_id=task_rows[0].mechanism_id,
                runtime_eligible_count=runtime_eligible,
                model_contract_failure_count=sum(
                    _rollout_failure_stage(item) == "model_contract" for item in task_rows
                ),
                runtime_or_instrument_failure_count=len(task_rows) - runtime_eligible,
                mechanism_evaluable_count=mechanism_evaluable,
                mechanism_success_count=mechanism_success,
                independent_valid_count=valid,
                mechanism_success_rate=mechanism_rate,
                valid_rate=valid_rate,
                valid_given_mechanism_success_rate=(
                    valid / mechanism_success if mechanism_success else None
                ),
                mechanism_wilson_lcb95=mechanism_interval[0],
                mechanism_wilson_ucb95=mechanism_interval[1],
                valid_wilson_lcb95=valid_interval[0],
                valid_wilson_ucb95=valid_interval[1],
                boundary_response=(0.125 <= mechanism_rate <= 0.875),
                earliest_failure_stage_counts=dict(sorted(failures.items())),
            )
        )
    if len(summaries) != 12:
        raise ValueError("capability Development lacks twelve task summaries")
    return tuple(summaries)


def aggregate_capability_mechanisms(
    tasks: Sequence[CapabilityTaskSummary],
) -> tuple[CapabilityMechanismSummary, ...]:
    output = []
    for mechanism in TARGET_MECHANISMS:
        rows = tuple(item for item in tasks if item.mechanism_id == mechanism)
        if len(rows) != 3:
            raise ValueError("capability mechanism lacks three independent tasks")
        mechanism_rates = tuple(item.mechanism_success_rate for item in rows)
        validity_rates = tuple(item.valid_rate for item in rows)
        output.append(
            CapabilityMechanismSummary(
                mechanism_id=mechanism,
                mechanism_success_count=sum(item.mechanism_success_count for item in rows),
                independent_valid_count=sum(item.independent_valid_count for item in rows),
                boundary_task_count=sum(item.boundary_response for item in rows),
                task_mechanism_success_range=(min(mechanism_rates), max(mechanism_rates)),
                task_validity_range=(min(validity_rates), max(validity_rates)),
            )
        )
    return tuple(output)


def aggregate_state_reachability(
    rollouts: Sequence[EmpiricalPilotRollout],
    catalogs: Sequence[StaticModelAuthorityPathCatalog],
) -> tuple[StateReachabilitySummary, ...]:
    natural = [item for item in rollouts if item.sampling_mode == "reachability_unconditional"]
    conditioned = [item for item in rollouts if item.sampling_mode == "reachability_conditioned"]
    output: list[StateReachabilitySummary] = []
    for catalog in sorted(catalogs, key=lambda item: item.task_package_id):
        if catalog.intended_use != "vtdo_multistate_candidate":
            continue
        natural_rows = [item for item in natural if item.task_package_id == catalog.task_package_id]
        if len(natural_rows) != NATURAL_ROLLOUTS_PER_TASK:
            raise ValueError("VTDO candidate lacks its natural rollout denominator")
        for path in sorted(catalog.paths, key=lambda item: item.path_strategy_id):
            rows = [
                item
                for item in conditioned
                if item.task_package_id == catalog.task_package_id
                and item.requested_static_path_id == path.path_id
            ]
            if len(rows) != CONDITIONED_ROLLOUTS_PER_STATE:
                raise ValueError("state lacks its conditioned rollout denominator")
            rows.sort(key=lambda item: item.replicate_index)
            natural_valid = sum(
                item.terminal_category == "model_valid_trajectory" for item in natural_rows
            )
            natural_hits = sum(
                item.path_assignment is not None
                and item.path_assignment.quotient_state_id == path.quotient_state_id
                for item in natural_rows
            )
            valid = sum(item.terminal_category == "model_valid_trajectory" for item in rows)
            on_target = [
                item
                for item in rows
                if item.path_assignment is not None
                and item.path_assignment.quotient_state_id == path.quotient_state_id
            ]
            off_target = sum(
                item.path_assignment is not None
                and item.path_assignment.quotient_state_id != path.quotient_state_id
                for item in rows
            )
            unmapped = sum(
                item.terminal_category == "model_valid_trajectory" and item.path_assignment is None
                for item in rows
            )
            seen_content: set[str] = set()
            seen_traces: set[str] = set()
            released: list[EmpiricalPilotRollout] = []
            duplicate_content = duplicate_trace = 0
            for item in on_target:
                content = item.trajectory_content_hash or ""
                trace = item.decision_trace_hash or ""
                content_duplicate = not content or content in seen_content
                trace_duplicate = not trace or trace in seen_traces
                duplicate_content += int(content_duplicate)
                duplicate_trace += int(trace_duplicate)
                if content_duplicate or trace_duplicate:
                    continue
                seen_content.add(content)
                seen_traces.add(trace)
                released.append(item)
            rate = len(on_target) / len(rows)
            lower, upper = wilson_interval(len(on_target), len(rows))
            estimated_attempts = MINIMUM_RELEASED_REALIZATIONS / rate if rate > 0 else None
            natural_pass = natural_hits >= 1
            lcb_pass = lower > 0.0
            yield_pass = len(released) >= MINIMUM_RELEASED_REALIZATIONS
            remap_pass = all(
                item.path_assignment is not None
                and item.path_assignment.path_strategy == path.path_strategy_id
                and item.path_assignment.quotient_state_id == path.quotient_state_id
                for item in released
            )
            generated_pass = all(item.model_generated for item in released)
            budget_pass = bool(
                estimated_attempts is not None
                and estimated_attempts <= MAXIMUM_ESTIMATED_ATTEMPTS_FOR_THREE
            )
            checks = {
                "natural_hit_missing": natural_pass,
                "conditioned_acceptance_lcb_not_positive": lcb_pass,
                "three_independent_realizations_missing": yield_pass,
                "stable_remapping_failed": remap_pass,
                "non_model_realization_detected": generated_pass,
                "materialization_budget_exceeded": budget_pass,
            }
            blockers = tuple(sorted(key for key, passed in checks.items() if not passed))
            output.append(
                StateReachabilitySummary(
                    task_package_id=catalog.task_package_id,
                    static_path_id=path.path_id,
                    path_strategy=cast(PathStrategy, path.path_strategy_id),
                    quotient_state_id=path.quotient_state_id,
                    natural_valid_count=natural_valid,
                    natural_on_state_hit_count=natural_hits,
                    conditioned_valid_count=valid,
                    conditioned_on_target_count=len(on_target),
                    conditioned_off_target_count=off_target,
                    conditioned_valid_unmapped_count=unmapped,
                    duplicate_content_count=duplicate_content,
                    duplicate_decision_trace_count=duplicate_trace,
                    released_count=len(released),
                    released_rollout_ids=tuple(item.rollout_id for item in released),
                    conditioned_acceptance_rate=rate,
                    conditioned_acceptance_lcb95=lower,
                    conditioned_acceptance_ucb95=upper,
                    estimated_attempts_for_three_releases=estimated_attempts,
                    provider_call_count=sum(item.provider_call_count for item in rows),
                    provider_total_tokens=sum(item.provider_total_tokens for item in rows),
                    estimated_cost_usd=str(sum(float(item.estimated_cost_usd) for item in rows)),
                    natural_hit_passed=natural_pass,
                    conditioned_lcb_passed=lcb_pass,
                    independent_realization_yield_passed=yield_pass,
                    stable_remapping_passed=remap_pass,
                    model_generated_only_passed=generated_pass,
                    budget_passed=budget_pass,
                    admitted=not blockers,
                    blockers=blockers,
                )
            )
    if len(output) != 36:
        raise ValueError("state Reachability aggregation lacks 36 registered states")
    return tuple(output)


def freeze_empirical_state_support(
    contract: EmpiricalSupportPilotContract,
    state_summaries: Sequence[StateReachabilitySummary],
    records: Sequence[RematerializedExecutableTaskRecord],
) -> EmpiricalStateSupportFreeze:
    mechanism_by_task = {
        item.task_package.package_id: item.mechanism_id
        for item in records
        if item.intended_use == "vtdo_multistate_candidate"
    }
    tasks = []
    for task_id, mechanism in sorted(mechanism_by_task.items()):
        rows = tuple(item for item in state_summaries if item.task_package_id == task_id)
        if len(rows) != 3:
            raise ValueError("state-support Freeze task lacks three registered states")
        admitted = tuple(sorted(item.quotient_state_id for item in rows if item.admitted))
        tasks.append(
            TaskStateSupportSummary(
                task_package_id=task_id,
                mechanism_id=mechanism,
                admitted_state_count=len(admitted),
                admitted_state_ids=admitted,
                all_three_states_admitted=len(admitted) == 3,
            )
        )
    count = sum(item.all_three_states_admitted for item in tasks)
    global_admitted = count == 12
    values = {
        "contract_id": contract.contract_id,
        "task_summaries": tuple(tasks),
        "admitted_task_count": count,
        "global_support_admitted": global_admitted,
        "status": "admitted" if global_admitted else "blocked",
        "next_transition": (
            "fresh_confirmation_protocol_design_only"
            if global_admitted
            else "capability_task_or_reachability_condition_redesign_only"
        ),
    }
    provisional = EmpiricalStateSupportFreeze.model_construct(freeze_id="pending", **values)
    return EmpiricalStateSupportFreeze(
        freeze_id=empirical_state_support_freeze_id(provisional),
        **values,
    )
