from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer_semantics import (
    AnswerSemanticComparison,
    compare_answer_by_schema,
    make_answer_semantic_schema,
)
from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
    evaluate_joint_support_validity,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    ContextMechanismEvidence,
    MechanismId,
    ReconciliationMechanismEvidence,
    RecoveryMechanismEvidence,
    StoppingMechanismEvidence,
    make_noninterference_artifact_binding,
    qualify_context_mechanism,
    qualify_reconciliation_mechanism,
    qualify_recovery_mechanism,
    qualify_stopping_mechanism,
)
from trusted_synthesis.core.measurement.support import (
    MeasurementSupportDecision,
    classify_measurement_support,
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.core.trajectory.executable_task import matching_sufficient_support_set
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as semantic_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_verifier_vnext_contract_freeze as verifier_freeze,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    match_empirical_program,
    replay_authority_preserving_observations,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_measurement_support import (
    classify_non_observation_support,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    make_qualified_final_host_envelope,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    build_semantic_action_state,
)

RUN_ID: Final = "finance_v26_155_fresh_reachability_postrun_audit_v1_20260826"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_155_fresh_reachability_postrun_audit_v1_20260826"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_reachability_postrun_audit.py"
)
NEXT_STAGE: Final = (
    "fresh_valid_only_observed_reachability_state_mapping_contract_mapper_runner_preflight_only"
)

EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_fresh_reachability_execution_report:"
    "fc943b68e5fcd7063425eba3b9f189d86785820598cd8784154ef37e15e4b8aa"
)
EXPECTED_EXECUTION_REPORT_SHA256: Final = (
    "80d4fdf0f66dfae290f1518a66ef192d911786c8617d13338e12f027fb722918"
)
EXPECTED_EXECUTION_SOURCE_ID: Final = (
    "finance_v26_fresh_reachability_execution_source_replay:"
    "70da94ec0428dc2c8600b0f22b0b491af36932ba2fcd2bf125db459a17a517c6"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_fresh_reachability_raw_lineage:"
    "5ab68739abc8178b68278cb9baf2e677aa63d3968995bf9b5c003bcbcc6ef9db"
)
EXPECTED_MEASUREMENT_GATE_ID: Final = (
    "finance_v26_fresh_reachability_measurement_gate:"
    "80db69f55808caa428767cfbb14e4d29fe5ad37ff13ceb9eac2df651053a0c27"
)
EXPECTED_FROZEN_REACHABILITY_POPULATION_ID: Final = (
    "finance_v26_fresh_role_source_population:"
    "cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99"
)
EXPECTED_NONINTERFERENCE_CONTRACT_ID: Final = execution.EXPECTED_NONINTERFERENCE_CONTRACT_ID


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
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
    raise ValueError(f"v26.155 cannot replay bound source: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_154_transitive_source",
        "v26_154_execution_file",
        "v26_155_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class PostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_ID
    execution_transitive_file_count: int = Field(ge=1)
    execution_file_count: int = Field(ge=1)
    implementation_file_count: Literal[1] = 1
    replayed_file_count: int = Field(ge=3)
    replay_pass_count: int = Field(ge=3)
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3)
    replay_before_execution_result_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        counts = Counter(item.source_kind for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or self.replay_pass_count != self.replayed_file_count
            or counts["v26_154_transitive_source"] != self.execution_transitive_file_count
            or counts["v26_154_execution_file"] != self.execution_file_count
            or counts["v26_155_implementation"] != self.implementation_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.155 source replay changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_fresh_reachability_postrun_source_replay:"
        ):
            raise ValueError("v26.155 source replay identity changed")
        return self


class IndependentProviderArtifactAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    raw_lineage_audit_id: str = EXPECTED_RAW_LINEAGE_ID
    raw_execution_count: Literal[360] = 360
    checkpoint_result_count: Literal[360] = 360
    aggregate_result_count: Literal[360] = 360
    provider_envelope_count: int = Field(ge=0)
    public_projection_count: int = Field(ge=0)
    transport_invocation_count: int = Field(ge=0)
    validated_provider_pair_count: int = Field(ge=0)
    descriptor_byte_match_count: int = Field(ge=360)
    checkpoint_aggregate_exact_match_count: Literal[360] = 360
    raw_checkpoint_parent_match_count: Literal[360] = 360
    provider_call_count: int = Field(ge=0)
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_persistence_count: Literal[0] = 0
    raw_http_body_persistence_count: Literal[0] = 0
    raw_request_body_persistence_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    state_mapping_artifact_count: Literal[0] = 0
    provider_calls_during_audit: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentProviderArtifactAudit:
        if not (
            self.provider_call_count
            == self.provider_envelope_count
            == self.public_projection_count
            == self.validated_provider_pair_count
        ):
            raise ValueError("v26.155 Provider artifact denominator changed")
        if self.transport_invocation_count < self.provider_call_count:
            raise ValueError("v26.155 Transport denominator is smaller than Provider calls")
        if self.descriptor_byte_match_count != (
            self.raw_execution_count
            + self.provider_envelope_count
            + self.public_projection_count
            + self.transport_invocation_count
        ):
            raise ValueError("v26.155 descriptor denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_independent_provider_artifacts:",
        ):
            raise ValueError("v26.155 Provider artifact identity changed")
        return self


class IndependentProjectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    joint_contract_id: str = preflight.EXPECTED_JOINT_CONTRACT_ID
    measurement_result_count: Literal[360] = 360
    exact_checkpoint_projection_match_count: Literal[360] = 360
    exact_aggregate_projection_match_count: Literal[360] = 360
    exact_joint_result_match_count: Literal[360] = 360
    exact_route_binding_match_count: Literal[360] = 360
    exact_prompt_audit_match_count: int = Field(ge=0, le=360)
    null_prompt_audit_match_count: int = Field(ge=0, le=360)
    base_check_pass_counts: dict[str, int]
    required_base_check_count: Literal[14] = 14
    recomputed_results: tuple[execution.ReachabilityMeasurementResult, ...] = Field(
        min_length=360,
        max_length=360,
    )
    independent_projection_used_execution_projector: Literal[False] = False
    independent_projection_used_execution_gate: Literal[False] = False
    independent_projection_used_execution_summary_helpers: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentProjectionAudit:
        jobs = tuple(item.job_id for item in self.recomputed_results)
        if (
            len(set(jobs)) != 360
            or len(self.base_check_pass_counts) != 14
            or self.exact_prompt_audit_match_count + self.null_prompt_audit_match_count != 360
        ):
            raise ValueError("v26.155 independent projection denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_independent_projection:",
        ):
            raise ValueError("v26.155 independent projection identity changed")
        return self


class IndependentMeasurementGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    formal_measurement_gate_id: str = EXPECTED_MEASUREMENT_GATE_ID
    complete_raw_count: int = Field(ge=0, le=360)
    model_endpoint_count: int = Field(ge=0, le=360)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    instrument_failure_count: int = Field(ge=0, le=360)
    privacy_failure_count: int = Field(ge=0, le=360)
    exact_model_thinking_usage_failure_count: int = Field(ge=0, le=360)
    typed_budget_no_call_count: int = Field(ge=0, le=360)
    unresolved_transport_failure_count: int = Field(ge=0, le=360)
    failure_ids: tuple[str, ...]
    passed: bool
    reachability_estimands_authorized: bool
    state_mapping_eligibility_estimand_authorized: bool
    formal_gate_exact_match: Literal[True] = True
    noncompensatory: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentMeasurementGateAudit:
        checks = {
            "complete_raw_360_of_360": self.complete_raw_count == 360,
            "model_endpoint_360_of_360": self.model_endpoint_count == 360,
            "measurement_support_exit_zero": self.measurement_support_exit_count == 0,
            "instrument_failure_zero": self.instrument_failure_count == 0,
            "privacy_failure_zero": self.privacy_failure_count == 0,
            "exact_model_thinking_usage_failure_zero": (
                self.exact_model_thinking_usage_failure_count == 0
            ),
            "typed_budget_no_call_zero": self.typed_budget_no_call_count == 0,
            "unresolved_transport_failure_zero": self.unresolved_transport_failure_count == 0,
        }
        failures = tuple(sorted(name for name, passed in checks.items() if not passed))
        if (
            self.failure_ids != failures
            or self.passed != all(checks.values())
            or self.reachability_estimands_authorized != self.passed
            or self.state_mapping_eligibility_estimand_authorized != self.passed
        ):
            raise ValueError("v26.155 independent Measurement Gate changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_independent_measurement_gate:",
        ):
            raise ValueError("v26.155 Measurement Gate identity changed")
        return self


class IndependentEstimandAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    unconditional_task_summaries: tuple[execution.UnconditionalTaskSummary, ...] = Field(
        min_length=12,
        max_length=12,
    )
    conditioned_path_summaries: tuple[execution.ConditionedPathSummary, ...] = Field(
        min_length=36,
        max_length=36,
    )
    mechanism_summaries: tuple[execution.MechanismReachabilitySummary, ...] = Field(
        min_length=4,
        max_length=4,
    )
    task_count: Literal[12] = 12
    conditioned_path_count: Literal[36] = 36
    mechanism_count: Literal[4] = 4
    unconditional_task_summary_exact_match_count: Literal[12] = 12
    conditioned_path_summary_exact_match_count: Literal[36] = 36
    mechanism_summary_exact_match_count: Literal[4] = 4
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    state_mapping_eligible_count: int = Field(ge=0, le=360)
    unconditional_task_weighted_base_fraction: str | None
    unconditional_task_weighted_mechanism_fraction: str | None
    unconditional_task_weighted_qualified_fraction: str | None
    conditioned_path_weighted_base_fraction: str | None
    conditioned_path_weighted_mechanism_fraction: str | None
    conditioned_path_weighted_qualified_fraction: str | None
    reachability_estimands_authorized: bool
    task_is_primary_unconditional_sampling_unit: Literal[True] = True
    path_is_primary_conditioned_sampling_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    static_path_used_as_empirical_state: Literal[False] = False
    state_mapping_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentEstimandAudit:
        task_base = sum(item.base_valid_count for item in self.unconditional_task_summaries)
        task_mechanism = sum(
            item.mechanism_qualified_count for item in self.unconditional_task_summaries
        )
        task_qualified = sum(
            item.qualified_valid_count for item in self.unconditional_task_summaries
        )
        path_base = sum(item.base_valid_count for item in self.conditioned_path_summaries)
        path_mechanism = sum(
            item.mechanism_qualified_count for item in self.conditioned_path_summaries
        )
        path_qualified = sum(item.qualified_valid_count for item in self.conditioned_path_summaries)
        fractions = (
            self.unconditional_task_weighted_base_fraction,
            self.unconditional_task_weighted_mechanism_fraction,
            self.unconditional_task_weighted_qualified_fraction,
            self.conditioned_path_weighted_base_fraction,
            self.conditioned_path_weighted_mechanism_fraction,
            self.conditioned_path_weighted_qualified_fraction,
        )
        if (
            task_base + path_base != self.base_valid_count
            or task_mechanism + path_mechanism != self.mechanism_qualified_count
            or task_qualified + path_qualified != self.qualified_valid_count
            or self.state_mapping_eligible_count != self.qualified_valid_count
            or all(item is not None for item in fractions) != self.reachability_estimands_authorized
        ):
            raise ValueError("v26.155 independent estimand changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_fresh_reachability_independent_estimand:"
        ):
            raise ValueError("v26.155 independent estimand identity changed")
        return self


class IndependentValidityDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[360] = 360
    exact_model_endpoint_count: int = Field(ge=0, le=360)
    completed_model_endpoint_count: int = Field(ge=0, le=360)
    model_result_failure_count: int = Field(ge=0, le=360)
    other_model_endpoint_count: int = Field(ge=0, le=360)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    program_closed_count: int = Field(ge=0, le=360)
    terminal_verification_complete_count: int = Field(ge=0, le=360)
    exact_qualified_final_payload_count: int = Field(ge=0, le=360)
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    state_mapping_eligible_count: int = Field(ge=0, le=360)
    base_failed_check_counts: dict[str, int]
    mechanism_missing_event_counts: dict[str, int]
    terminal_failure_type_counts: dict[str, int]
    qualified_equals_base_and_mechanism_count: Literal[360] = 360
    support_or_integrity_rows_with_nonnull_validity: Literal[0] = 0
    historical_row_pooling_count: Literal[0] = 0
    formal_report_aggregate_match_count: int = Field(ge=1)
    observed_provider_call_count: int = Field(ge=0)
    observed_transport_invocation_count: int = Field(ge=0)
    observed_prompt_tokens: int = Field(ge=0)
    observed_completion_tokens: int = Field(ge=0)
    observed_reasoning_tokens: int = Field(ge=0)
    observed_total_tokens: int = Field(ge=0)
    observed_estimated_cost_usd: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentValidityDecompositionAudit:
        if (
            self.completed_model_endpoint_count
            + self.model_result_failure_count
            + self.other_model_endpoint_count
            != self.exact_model_endpoint_count
            or self.qualified_valid_count > self.base_valid_count
            or self.state_mapping_eligible_count != self.qualified_valid_count
        ):
            raise ValueError("v26.155 validity decomposition changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_validity_decomposition:",
        ):
            raise ValueError("v26.155 validity decomposition identity changed")
        return self


class SupportBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    ordinary_detour_allowance_exhausted_count: int = Field(ge=0, le=360)
    raw_native_instrument_integrity_true_count: int = Field(ge=0, le=360)
    formal_projected_instrument_failure_overlap_count: int = Field(ge=0, le=360)
    second_ordinary_detour_count: int = Field(ge=0, le=360)
    baseline_available_count: int = Field(ge=0, le=360)
    later_provider_call_count: Literal[0] = 0
    provider_token_overrun_count: Literal[0] = 0
    provider_call_overrun_count: Literal[0] = 0
    transport_invocation_overrun_count: Literal[0] = 0
    support_exit_job_ids: tuple[str, ...]
    support_exit_is_not_model_invalid: Literal[True] = True
    historical_projection_reclassified: Literal[False] = False
    reachability_frequency_estimate_authorized: bool
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> SupportBoundaryAudit:
        if (
            len(self.support_exit_job_ids) != self.measurement_support_exit_count
            or self.support_exit_job_ids != tuple(sorted(set(self.support_exit_job_ids)))
            or self.reachability_frequency_estimate_authorized
            != (self.measurement_support_exit_count == 0)
        ):
            raise ValueError("v26.155 support-boundary audit changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_fresh_reachability_support_boundary:",
        ):
            raise ValueError("v26.155 support-boundary identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    rejected_count: Literal[30] = 30
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.155 destructive mutation set changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_fresh_reachability_postrun_destructive:"
        ):
            raise ValueError("v26.155 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    independent_measurement_gate_id: str = Field(min_length=1)
    independent_estimand_audit_id: str = Field(min_length=1)
    independent_validity_decomposition_id: str = Field(min_length=1)
    support_boundary_audit_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    qualified_valid_count: int = Field(ge=0, le=360)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    reachability_estimands_authorized: bool
    valid_only_observed_state_mapping_preflight_authorized: bool
    state_mapping_execution_authorized: Literal[False] = False
    qualified_validity_true_required: Literal[True] = True
    support_or_integrity_row_mapping_forbidden: Literal[True] = True
    compiler_static_path_is_target_condition_not_empirical_state: Literal[True] = True
    mapping_must_bind_raw_trajectory_independent_validity_omega_route_path_and_prefix: Literal[
        True
    ] = True
    observed_state_support_not_frequency_estimate: Literal[True] = True
    reachability_rerun_recovery_or_pooling_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    status: Literal[
        "reachability_gate_passed_mapping_preflight_only",
        "reachability_gate_failed_observed_valid_mapping_preflight_only",
    ]

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        expected_status = (
            "reachability_gate_passed_mapping_preflight_only"
            if self.reachability_estimands_authorized
            else "reachability_gate_failed_observed_valid_mapping_preflight_only"
        )
        if (
            self.status != expected_status
            or self.valid_only_observed_state_mapping_preflight_authorized
            != (self.qualified_valid_count > 0)
        ):
            raise ValueError("v26.155 transition authorization changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_fresh_reachability_postrun_transition:",
        ):
            raise ValueError("v26.155 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    provider_artifact_audit_id: str = Field(min_length=1)
    independent_projection_audit_id: str = Field(min_length=1)
    independent_measurement_gate_id: str = Field(min_length=1)
    independent_estimand_audit_id: str = Field(min_length=1)
    validity_decomposition_audit_id: str = Field(min_length=1)
    support_boundary_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=9, max_length=9)
    exact_job_denominator: Literal[360] = 360
    measurement_gate_passed: bool
    reachability_estimands_authorized: bool
    base_valid_count: int = Field(ge=0, le=360)
    mechanism_qualified_count: int = Field(ge=0, le=360)
    qualified_valid_count: int = Field(ge=0, le=360)
    state_mapping_eligible_count: int = Field(ge=0, le=360)
    measurement_support_exit_count: int = Field(ge=0, le=360)
    valid_only_mapping_preflight_authorized: bool
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    state_mapping_contract_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal[
        "reachability_postrun_audit_passed",
        "reachability_postrun_audit_closed_failed_gate",
    ]

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        expected_status = (
            "reachability_postrun_audit_passed"
            if self.measurement_gate_passed
            else "reachability_postrun_audit_closed_failed_gate"
        )
        if (
            self.status != expected_status
            or self.reachability_estimands_authorized != self.measurement_gate_passed
            or self.state_mapping_eligible_count != self.qualified_valid_count
            or self.valid_only_mapping_preflight_authorized != (self.qualified_valid_count > 0)
        ):
            raise ValueError("v26.155 report decision changed")
        if self.report_id != _identity(
            self, "report_id", "finance_v26_fresh_reachability_postrun_audit_report:"
        ):
            raise ValueError("v26.155 report identity changed")
        return self


@dataclass(frozen=True)
class AuditInputs:
    report: execution.ReachabilityExecutionReport
    manifest: preflight.ReachabilityManifest
    tasks: preflight.TaskPackageCatalog
    paths: preflight.PathCatalog
    frozen_input: preflight.FrozenReachabilityInputAudit
    resource: preflight.ResourceContract
    runner_contract: preflight.RunnerContract
    joint_contract: JointSupportValidityContract
    grammar: QualifiedFinalResponseGrammar
    role_inputs: Any
    replay_contract: AuthorityPreservingReplayContract


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> PostrunSourceReplayAudit:
    prior = execution.ExecutionSourceReplayAudit.model_validate(
        _load(execution_dir / "execution_source_replay_audit.json")
    )
    if prior.audit_id != EXPECTED_EXECUTION_SOURCE_ID or len(prior.entries) != 10156:
        raise ValueError("v26.155 execution source replay identity changed")

    entries: list[SourceReplayEntry] = []
    for item in prior.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_154_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )

    execution_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if not execution_files or any(path.name.endswith(".tmp") for path in execution_files):
        raise ValueError("v26.155 execution file set is incomplete or noncanonical")
    for path in execution_files:
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_154_execution_file",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )

    implementation = implementation_root / IMPLEMENTATION_PATH
    if not implementation.is_file():
        raise ValueError("v26.155 implementation is missing")
    digest = _sha256(implementation)
    entries.append(
        SourceReplayEntry(
            relative_path=IMPLEMENTATION_PATH,
            source_kind="v26_155_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=implementation.stat().st_size,
        )
    )
    values: dict[str, Any] = {
        "execution_transitive_file_count": len(prior.entries),
        "execution_file_count": len(execution_files),
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
        "entries": tuple(sorted(entries, key=lambda item: item.relative_path)),
    }
    provisional = PostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return PostrunSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_postrun_source_replay:",
        ),
        **values,
    )


def _load_inputs(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> AuditInputs:
    report_path = execution_dir / "report.json"
    report = execution.ReachabilityExecutionReport.model_validate(_load(report_path))
    gate = execution.MeasurementGateAudit.model_validate(
        _load(execution_dir / "measurement_gate_audit.json")
    )
    raw_lineage = execution.RawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    manifest = preflight.ReachabilityManifest.model_validate(
        _load(execution_dir / "frozen_reachability_manifest.json")
    )
    tasks = preflight.TaskPackageCatalog.model_validate(
        _load(execution_dir / "frozen_reachability_task_package_catalog.json")
    )
    paths = preflight.PathCatalog.model_validate(
        _load(execution_dir / "frozen_reachability_path_catalog.json")
    )
    frozen_input = preflight.FrozenReachabilityInputAudit.model_validate(
        _load(execution_dir / "frozen_reachability_input_audit.json")
    )
    resource = preflight.ResourceContract.model_validate(
        _load(execution_dir / "frozen_reachability_resource_contract.json")
    )
    runner_contract = preflight.RunnerContract.model_validate(
        _load(execution_dir / "frozen_reachability_runner_contract.json")
    )
    joint_contract = JointSupportValidityContract.model_validate(
        _load(execution_dir / "frozen_joint_support_validity_contract.json")
    )
    grammar = QualifiedFinalResponseGrammar.model_validate(
        _load(execution_dir / "frozen_qualified_final_response_grammar.json")
    )
    noninterference_contract = (
        verifier_freeze.ResponsibilityAndNoninterferenceContract.model_validate(
            _load(execution_dir / "frozen_responsibility_noninterference_contract.json")
        )
    )
    role_inputs = preflight.old_capability._load_role_inputs(  # noqa: SLF001
        package_root=package_root,
        implementation_root=implementation_root,
    )
    _, replay_contract = preflight.bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        package_root / preflight.bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
        package_root,
    )
    if (
        _sha256(report_path) != EXPECTED_EXECUTION_REPORT_SHA256
        or report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or report.source_replay_audit_id != EXPECTED_EXECUTION_SOURCE_ID
        or report.raw_lineage_audit_id != EXPECTED_RAW_LINEAGE_ID
        or report.measurement_gate_audit_id != EXPECTED_MEASUREMENT_GATE_ID
        or report.next_permitted_stage != execution.POSTRUN_STAGE
        or report.complete_result_count != 360
        or report.complete_raw_count != 360
        or report.state_mapping_rows != 0
        or gate.audit_id != EXPECTED_MEASUREMENT_GATE_ID
        or raw_lineage.audit_id != EXPECTED_RAW_LINEAGE_ID
        or raw_lineage.raw_execution_count != 360
        or manifest.manifest_id != execution.EXPECTED_MANIFEST_ID
        or len(manifest.jobs) != 360
        or len(tasks.packages) != 12
        or len(paths.paths) != 36
        or frozen_input.audit_id != execution.EXPECTED_FROZEN_INPUT_ID
        or frozen_input.frozen_population_id != EXPECTED_FROZEN_REACHABILITY_POPULATION_ID
        or tasks.source_population_id != frozen_input.frozen_population_id
        or tasks.frozen_input_audit_id != frozen_input.audit_id
        or paths.task_package_catalog_id != tasks.catalog_id
        or manifest.source_population_id != frozen_input.frozen_population_id
        or manifest.frozen_input_audit_id != frozen_input.audit_id
        or any(item.frozen_input_audit_id != frozen_input.audit_id for item in tasks.packages)
        or any(
            item.candidate_presentation_parent_id != frozen_input.audit_id for item in manifest.jobs
        )
        or resource.contract_id != execution.EXPECTED_RESOURCE_CONTRACT_ID
        or runner_contract.contract_id != execution.EXPECTED_RUNNER_CONTRACT_ID
        or joint_contract.contract_id != preflight.EXPECTED_JOINT_CONTRACT_ID
        or grammar.grammar_id != runner_contract.qualified_final_grammar_id
        or noninterference_contract.contract_id != EXPECTED_NONINTERFERENCE_CONTRACT_ID
    ):
        raise ValueError("v26.155 frozen Reachability execution input changed")
    return AuditInputs(
        report=report,
        manifest=manifest,
        tasks=tasks,
        paths=paths,
        frozen_input=frozen_input,
        resource=resource,
        runner_contract=runner_contract,
        joint_contract=joint_contract,
        grammar=grammar,
        role_inputs=role_inputs,
        replay_contract=replay_contract,
    )


def _package_for_job(
    inputs: AuditInputs,
    job: preflight.FreshReachabilityJob,
) -> preflight.FreshReachabilityTaskPackage:
    package = next(
        (item for item in inputs.tasks.packages if item.task_package_id == job.task_package_id),
        None,
    )
    if (
        package is None
        or package.source_task_artifact_id != job.source_task_artifact_id
        or package.mechanism_id != job.mechanism_id
        or package.tier != job.tier
    ):
        raise ValueError("v26.155 Job is detached from its frozen TaskPackage")
    return package


def _path_for_job(
    inputs: AuditInputs,
    job: preflight.FreshReachabilityJob,
) -> preflight.FreshReachabilityPath | None:
    if job.sampling_mode == "reachability_unconditional":
        if any(
            item is not None
            for item in (
                job.requested_path_id,
                job.requested_path_strategy,
                job.public_path_condition,
                job.public_condition_id,
            )
        ):
            raise ValueError("v26.155 unconditional Job carries a route condition")
        return None
    path = next(
        (item for item in inputs.paths.paths if item.path_id == job.requested_path_id),
        None,
    )
    if (
        path is None
        or path.task_package_id != job.task_package_id
        or path.source_task_artifact_id != job.source_task_artifact_id
        or path.path_strategy_id != job.requested_path_strategy
        or path.public_path_condition != job.public_path_condition
        or path.public_condition_id != job.public_condition_id
    ):
        raise ValueError("v26.155 conditioned Job crossed its frozen Path")
    return path


def _provider_pairs(
    raw: runner_vnext.FreshReachabilityRawExecution,
    execution_dir: Path,
) -> tuple[
    tuple[privacy_runner.PrivacyFirstProviderEnvelope, privacy_runner.PublicPayloadProjection],
    ...,
]:
    envelopes: list[privacy_runner.PrivacyFirstProviderEnvelope] = []
    projections: list[privacy_runner.PublicPayloadProjection] = []
    for descriptor in raw.provider_envelope_artifacts:
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.155 Provider Envelope bytes changed")
        envelopes.append(privacy_runner.PrivacyFirstProviderEnvelope.model_validate(_load(path)))
    for descriptor in raw.public_payload_projection_artifacts:
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.155 public Projection bytes changed")
        projections.append(privacy_runner.PublicPayloadProjection.model_validate(_load(path)))
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        privacy_runner.validate_provider_artifact_pair(envelope, projection)
    for descriptor in raw.transport_invocation_artifacts:
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError("v26.155 Transport invocation bytes changed")
        certificate = preflight.s1_runner.TransportInvocationCertificate.model_validate(_load(path))
        if certificate.job_id != raw.job_id:
            raise ValueError("v26.155 Transport invocation crosses its Job")
    return pairs


def _endpoint_observed(raw: runner_vnext.FreshReachabilityRawExecution) -> bool:
    return raw.terminal_disposition not in {
        "measurement_support_exit",
        "typed_budget_no_call",
        "provider_transport_failure",
        "instrument_failure",
    }


def _support_decision(
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
) -> tuple[
    MeasurementSupportDecision,
    Literal["raw_last", "typed_detour_limit_exit", "endpoint_no_public_commit"],
]:
    if raw.measurement_support_decisions:
        decision = raw.measurement_support_decisions[-1]
        if (
            raw.terminal_disposition == "measurement_support_exit"
            and decision.status != "unavailable"
        ):
            event = make_measurement_support_event(
                event_kind="public_observation",
                public_state_id_before=decision.public_state_id,
                public_state_id_after=canonical_hash(
                    {"decision_id": decision.decision_id, "terminal": raw.terminal_disposition},
                    prefix="finance_v26_detour_limit_support_exit_state:",
                ),
                progress_vector_id_before=decision.progress_vector_id,
                progress_vector_id_after=decision.progress_vector_id,
                selected_action_id=decision.selected_action_id,
                observation_status="succeeded",
            )
            return (
                classify_measurement_support(
                    event,
                    baseline_resolver=lambda: make_baseline_resolution(
                        status="unavailable",
                        public_state_id=event.public_state_id_before,
                        progress_vector_id=event.progress_vector_id_before,
                        reason_code=(
                            raw.terminal_failure_type or "ordinary_detour_allowance_exhausted"
                        ),
                    ),
                ),
                "typed_detour_limit_exit",
            )
        return decision, "raw_last"
    state = build_semantic_action_state(
        package.operational_record.task_package.task.public,
        package.environment,
        (),
    )
    return (
        classify_non_observation_support(
            event_kind="non_public_commit",
            state=state,
            selected_action_id=None,
        ),
        "endpoint_no_public_commit",
    )


def _prompt_payload_sensitive_count(prompt: str, *, action: bool) -> int:
    if action:
        payload = preflight.prompt_base._privacy_safe_prompt_payload(  # noqa: SLF001
            prompt
        ).model_dump(mode="json")
    else:
        payload = runner_vnext._qualified_final_prompt_payload(prompt)  # noqa: SLF001
    return len(preflight.prompt_base._sensitive_key_paths(payload))  # noqa: SLF001


def _reconstruct_online_noninterference(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
    job: preflight.FreshReachabilityJob,
    inputs: AuditInputs,
) -> execution.OnlineNoninterferenceAudit:
    attempts_by_index: dict[int, list[Any]] = defaultdict(list)
    for attempt in raw.attempts:
        attempts_by_index[attempt.logical_request_index].append(attempt)
    choices = {item.logical_request_index: item for item in raw.semantic_choices}
    commits = {item.commit.commit_id: item for item in raw.commits}
    rejection_by_id = {item.rejection_id: item for item in raw.semantic_rejections}

    observations: list[Any] = []
    rejections: list[Any] = []
    matched = 0
    sensitive = 0
    final_state = None
    final_commit = None
    path = _path_for_job(inputs, job)
    binding = preflight._runtime_binding(  # noqa: SLF001
        package,
        inputs.frozen_input.audit_id,
        path_strategy_id=("unconditional" if path is None else path.path_strategy_id),
        public_path_condition=(None if path is None else path.public_path_condition),
    )

    for logical_index in sorted(attempts_by_index):
        group = attempts_by_index[logical_index]
        if group[0].request_kind != "semantic_proposal":
            continue
        state = build_semantic_action_state(
            package.operational_record.task_package.task.public,
            package.environment,
            tuple(observations),
            semantic_rejections=tuple(rejections),
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery"
            if group[0].public_attempt_phase == "semantic_recovery"
            else "primary"
        )
        typed_failure = None
        if phase == "semantic_recovery":
            if not rejections:
                raise ValueError("v26.155 Semantic Recovery Prompt lacks a public rejection")
            rejection = rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        salt = runner_vnext._presentation_salt(  # noqa: SLF001
            binding=binding,
            state=state,
            logical_index=logical_index,
        )
        primary = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
            phase=phase,
            instruction=package.operational_record.task_package.task.public.instruction,
            state=state,
            public_path_condition=job.public_path_condition,
            presentation_salt=salt,
            typed_failure=typed_failure,
            grammar=inputs.role_inputs.static.action_grammar,
        )
        for position, attempt in enumerate(group):
            expected = primary
            if attempt.public_attempt_phase == "abi_rescue":
                initial = group[0]
                expected = preflight.prompt_base.render_privacy_safe_s1_action_prompt(
                    phase="abi_rescue",
                    instruction=package.operational_record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=job.public_path_condition,
                    presentation_salt=salt,
                    typed_failure={
                        "family": initial.failure_family or "channel_parse_failure",
                        "subtype": (
                            initial.failure_subtype
                            or initial.completion_failure_type
                            or "completion_failure"
                        ),
                    },
                    grammar=inputs.role_inputs.static.action_grammar,
                )
            if (
                legacy.sha256_text(expected) != attempt.prompt_sha256
                or len(expected.encode("utf-8")) != attempt.prompt_utf8_bytes
            ):
                raise ValueError("v26.155 reached Action Prompt hash changed")
            matched += 1
            sensitive += _prompt_payload_sensitive_count(expected, action=True)
            if position > 1:
                raise ValueError("v26.155 Action request exceeded one ABI Rescue")

        choice = choices.get(logical_index)
        if choice is None:
            continue
        if choice.observation_status is not None:
            observation = raw.observations[len(observations)]
            if observation.status != choice.observation_status:
                raise ValueError("v26.155 Choice Observation binding changed")
            observations.append(observation)
        if choice.rejection_id is not None:
            rejection = rejection_by_id.get(choice.rejection_id)
            if rejection is None:
                raise ValueError("v26.155 Choice rejection binding changed")
            rejections.append(rejection)
        if choice.commit_id is not None:
            commit_record = commits.get(choice.commit_id)
            if commit_record is None:
                raise ValueError("v26.155 Choice Commit binding changed")
            if commit_record.commit.action == "emit_final":
                final_state = state
                final_commit = commit_record.commit

    final_groups = [
        (index, group)
        for index, group in sorted(attempts_by_index.items())
        if group[0].request_kind == "final_answer"
    ]
    if final_groups:
        if final_state is None or final_commit is None:
            raise ValueError("v26.155 Final Prompt lacks its model-selected Commit")
        compact = render_compact_final_prompt(
            package.prompt_contract.public_context,
            package.operational_record.task_package.task.public,
            tuple(observations),
            public_path_condition=job.public_path_condition,
        )
        primary = runner_vnext.render_qualified_final_primary_prompt(
            compact,
            grammar=inputs.grammar,
        )
        envelope = make_qualified_final_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=inputs.grammar,
        )
        for _, group in final_groups:
            for position, attempt in enumerate(group):
                expected = primary
                if attempt.public_attempt_phase == "abi_rescue":
                    initial = group[0]
                    expected = runner_vnext.render_qualified_final_rescue_prompt(
                        primary,
                        failure_family=initial.failure_family or "channel_parse_failure",
                        failure_subtype=(
                            initial.failure_subtype
                            or initial.completion_failure_type
                            or "completion_failure"
                        ),
                    )
                if (
                    legacy.sha256_text(expected) != attempt.prompt_sha256
                    or len(expected.encode("utf-8")) != attempt.prompt_utf8_bytes
                    or attempt.final_response_host_envelope_id != envelope.envelope_id
                ):
                    raise ValueError("v26.155 reached Final Prompt or Host Envelope changed")
                matched += 1
                sensitive += _prompt_payload_sensitive_count(expected, action=False)
                if position > 1:
                    raise ValueError("v26.155 Final request exceeded one ABI Rescue")

    if matched != len(raw.attempts) or sensitive:
        raise ValueError("v26.155 online Prompt noninterference failed")
    values: dict[str, Any] = {
        "qualified_final_grammar_id": inputs.grammar.grammar_id,
        "task_package_id": package.task_package_id,
        "job_id": raw.job_id,
        "reached_prompt_count": len(raw.attempts),
        "prompt_hash_match_count": matched,
    }
    provisional = execution.OnlineNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return execution.OnlineNoninterferenceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_online_noninterference:",
        ),
        **values,
    )


def _decimal_field_paths(expected: Mapping[str, Any]) -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for key, value in expected.items():
        if isinstance(value, bool) or value is None:
            continue
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if number.is_finite():
            paths.append((str(key),))
    return tuple(sorted(paths))


def _replace_runtime_references(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, Mapping):
        return {str(key): _replace_runtime_references(item, mapping) for key, item in value.items()}
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


def _verification_support_ids(observations: Sequence[Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(evidence_id)
                for item in observations
                if item.call.tool_id == "cross_check_evidence"
                and item.status == "succeeded"
                and item.result.get("verified") is True
                for evidence_id in item.result.get("support") or ()
            }
        )
    )


def _postcompletion_violation(observations: Sequence[Any]) -> bool:
    first_verified = next(
        (
            index
            for index, item in enumerate(observations)
            if item.call.tool_id == "cross_check_evidence"
            and item.status == "succeeded"
            and item.result.get("verified") is True
        ),
        None,
    )
    return bool(first_verified is not None and first_verified != len(observations) - 1)


def _call_signature(observation: Any) -> str:
    return canonical_hash(
        {"tool_id": observation.call.tool_id, "arguments": observation.call.arguments},
        prefix="finance_v26_fresh_reachability_mechanism_action:",
    )


def _mechanism_events(
    *,
    mechanism_id: MechanismId,
    record: Any,
    observations: Sequence[Any],
    completed: bool,
) -> tuple[str, ...]:
    def successful(tool: str) -> tuple[Any, ...]:
        return tuple(
            item
            for item in observations
            if item.call.tool_id == tool and item.status == "succeeded"
        )

    if mechanism_id == "context_conditioned_action":
        calculators = successful("calculator")
        private = record.mechanism_private_state
        expected = str(private.get("expected_first_action"))
        baseline = str(private.get("alternate_action"))
        actual = str(calculators[0].call.arguments.get("operator")) if calculators else baseline
        conditioned = actual if actual == expected else baseline
        return qualify_context_mechanism(
            ContextMechanismEvidence(
                frozen_context_pair_id=record.task_package.mechanism_contract.contract_id,
                baseline_action_id=baseline,
                conditioned_action_id=conditioned,
            )
        )

    if mechanism_id == "semantic_reconciliation":
        target = tuple(
            sorted(str(item) for item in record.mechanism_private_state["target_evidence_ids"])
        )
        normalized_by_reference: dict[str, str] = {}
        for item in successful("normalize_metric_unit_period"):
            reference = item.result.get("normalized_operation_ref")
            rows = item.result.get("normalized_values")
            if not reference or not isinstance(rows, list):
                continue
            evidence = {
                str(row["evidence_id"])
                for row in rows
                if isinstance(row, Mapping) and row.get("evidence_id")
            }
            if len(evidence) == 1:
                normalized_by_reference[str(reference)] = next(iter(evidence))
        consumed_references = {
            str(operand.get("operation_ref"))
            for item in successful("calculator")
            for operand in item.call.arguments.get("operands", ())
            if isinstance(operand, Mapping) and operand.get("operation_ref")
        }
        normalized = tuple(sorted(set(normalized_by_reference.values()) & set(target)))
        consumed = tuple(
            sorted(
                {
                    evidence
                    for reference, evidence in normalized_by_reference.items()
                    if reference in consumed_references and evidence in set(target)
                }
            )
        )
        extra = tuple(sorted(set(normalized_by_reference.values()) - set(target)))
        return qualify_reconciliation_mechanism(
            ReconciliationMechanismEvidence(
                target_evidence_ids=target,
                normalized_target_evidence_ids=normalized,
                consumed_normalization_evidence_ids=consumed,
                extra_legal_normalized_evidence_ids=extra,
            )
        )

    if mechanism_id == "failure_recovery":
        failures = tuple(
            (index, item)
            for index, item in enumerate(observations)
            if item.call.tool_id == "query_structured_fact"
            and item.status == "failed"
            and item.error_code == "typed_selector_requires_refinement"
        )
        failure_index = failures[0][0] if failures else None
        failed_signature = _call_signature(failures[0][1]) if failures else None
        revised_index = None
        revised_signature = None
        if failures:
            failure_index_value = failures[0][0]
            for index, item in enumerate(
                observations[failure_index_value + 1 :], failure_index_value + 1
            ):
                signature = _call_signature(item)
                if item.call.tool_id == "query_structured_fact" and signature != failed_signature:
                    revised_index = index
                    revised_signature = signature
                    break
        later_success = None
        if revised_index is not None:
            later_success = next(
                (
                    index
                    for index, item in enumerate(
                        observations[revised_index + 1 :], revised_index + 1
                    )
                    if item.status == "succeeded"
                ),
                None,
            )
        return qualify_recovery_mechanism(
            RecoveryMechanismEvidence(
                typed_failure_observation_index=failure_index,
                revised_action_observation_index=revised_index,
                later_success_observation_index=later_success,
                failed_action_signature=failed_signature,
                revised_action_signature=revised_signature,
            )
        )

    verified_indices = tuple(
        index
        for index, item in enumerate(observations)
        if item.call.tool_id == "cross_check_evidence"
        and item.status == "succeeded"
        and item.result.get("verified") is True
    )
    return qualify_stopping_mechanism(
        StoppingMechanismEvidence(
            completion_verified=bool(verified_indices),
            stopped_after_completion=bool(
                completed and verified_indices and verified_indices[-1] == len(observations) - 1
            ),
            postcompletion_violation=_postcompletion_violation(observations),
            stopping_failure_causal_group_id=f"{record.record_id}:stopping",
        )
    )


def _program_progress(record: Any, observations: Sequence[Any]) -> tuple[bool, bool]:
    _, _, program_closed, terminal_completed, verified = semantic_online._progress_diagnostic(  # noqa: SLF001
        record, cast(Any, tuple(observations))
    )
    return bool(program_closed and terminal_completed), bool(verified)


def _base_inputs(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    package: preflight.FreshReachabilityTaskPackage,
    replay: AuthorityPreservingReplayResult,
    noninterference: execution.OnlineNoninterferenceAudit,
) -> tuple[BaseValidityChecks, AnswerSemanticComparison]:
    record = package.operational_record
    observations = raw.observations
    program_complete, _, runtime_to_node, operation_lineage = match_empirical_program(
        cast(Any, record), observations
    )
    expected = cast(dict[str, Any], record.projected_expected_output)
    observed_result: Mapping[str, Any] | None = None
    model_citations: tuple[str, ...] = ()
    if raw.completed_result is not None:
        observed_result = raw.completed_result.final_payload.answer.result
        model_citations = tuple(
            sorted(
                {item.evidence_id for item in raw.completed_result.final_payload.answer.citations}
            )
        )
    normalized = (
        _project_answer(
            cast(
                Mapping[str, Any],
                _replace_runtime_references(observed_result, runtime_to_node),
            ),
            record.answer_projection,
        )
        if observed_result is not None
        else None
    )
    schema = make_answer_semantic_schema(
        required_result_fields=tuple(expected),
        decimal_field_paths=_decimal_field_paths(expected),
    )
    comparison = compare_answer_by_schema(normalized, expected, schema)

    lattice = record.task_package.evidence_support_lattice
    necessary = set(lattice.necessary_evidence_ids)
    selected = tuple(sorted(replay.selected_evidence_ids))
    selected_support = matching_sufficient_support_set(lattice, selected)
    citation_support = matching_sufficient_support_set(lattice, model_citations)
    verification_support = _verification_support_ids(observations)
    program_closed, terminal_verified = _program_progress(record, observations)
    checks = BaseValidityChecks(
        action_abi_complete=raw.first_action_interface_qualified,
        program_closed=program_closed,
        operation_lineage_complete=bool(program_complete and necessary <= set(operation_lineage)),
        required_evidence_support_complete=necessary <= set(selected),
        runtime_selected_support_complete=selected_support is not None,
        model_citation_complete=citation_support is not None,
        terminal_verification_complete=terminal_verified,
        final_abi_complete=bool(
            raw.completed_result is not None and raw.exact_qualified_final_payload_count == 1
        ),
        answer_schema_complete=comparison.answer_schema_match,
        answer_canonical_semantic_match=comparison.answer_canonical_semantic_match,
        reference_identity_match=comparison.reference_identity_match,
        verification_support_complete=necessary <= set(verification_support),
        no_postcompletion_violation=not _postcompletion_violation(observations),
        noninterference_artifact_bound=noninterference.passed,
    )
    return checks, comparison


def _project_measurement_independently(
    *,
    raw: runner_vnext.FreshReachabilityRawExecution,
    job: preflight.FreshReachabilityJob,
    package: preflight.FreshReachabilityTaskPackage,
    inputs: AuditInputs,
    execution_dir: Path,
) -> execution.ReachabilityMeasurementResult:
    if raw.job_id != job.job_id or raw.job_payload != job.model_dump(mode="json"):
        raise ValueError("v26.155 Raw execution crossed its Job identity")
    _path_for_job(inputs, job)
    pairs = _provider_pairs(raw, execution_dir)
    projection_counts = Counter(item.projection_status for _, item in pairs)
    exact_model, fallback_absent, native_absent, thinking, usage = semantic_online._telemetry_flags(
        raw.provider_telemetry
    )  # noqa: SLF001
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
    pairing = bool(
        len(pairs)
        == len(raw.provider_envelope_artifacts)
        == len(raw.public_payload_projection_artifacts)
        == raw.stage_one_provider_call_count
        == len(raw.transport_invocation_artifacts)
    )
    reversible = all(
        item.reversible_same_action_id_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    resource_passed = bool(
        raw.cumulative_provider_tokens <= inputs.resource.rollout_upper_bound_tokens
        and raw.stage_one_provider_call_count <= inputs.resource.maximum_stage_one_provider_calls
        and raw.transport_inclusive_invocation_count
        <= inputs.resource.maximum_transport_inclusive_invocations
        and raw.ordinary_detour_count <= inputs.runner_contract.maximum_ordinary_detours
    )
    privacy_compliant = bool(
        raw.privacy_compliant
        and raw.privacy_rejected_payload_count == 0
        and projection_counts["privacy_rejected"] == 0
        and pairing
    )
    model_endpoint = _endpoint_observed(raw)
    support_available = bool(
        raw.measurement_support_available
        and raw.terminal_disposition != "measurement_support_exit"
        and all(item.status != "unavailable" for item in raw.measurement_support_decisions)
    )
    preliminary_instrument = bool(
        raw.instrument_integrity
        and raw.terminal_disposition != "instrument_failure"
        and exact_model
        and fallback_absent
        and native_absent
        and thinking
        and usage
        and dynamic
        and exact_request
        and pairing
        and reversible
        and resource_passed
        and raw.stage_two_provider_call_count == 0
    )

    prompt_audit: execution.OnlineNoninterferenceAudit | None = None
    replay: AuthorityPreservingReplayResult | None = None
    precheck_failures: list[str] = []
    if support_available and model_endpoint and preliminary_instrument and privacy_compliant:
        try:
            prompt_audit = _reconstruct_online_noninterference(
                raw=raw,
                package=package,
                job=job,
                inputs=inputs,
            )
        except Exception as error:
            precheck_failures.append(f"online_noninterference:{type(error).__name__}")
        try:
            candidate_replay = replay_authority_preserving_observations(
                inputs.replay_contract,
                package.operational_record,
                package.environment,
                raw.observations,
            )
            if candidate_replay.passed:
                replay = candidate_replay
            else:
                precheck_failures.extend(candidate_replay.failure_ids)
        except Exception as error:
            precheck_failures.append(f"runtime_replay:{type(error).__name__}")

    instrument = preliminary_instrument and not precheck_failures
    evaluable = bool(support_available and model_endpoint and instrument and privacy_compliant)
    if not evaluable:
        prompt_audit = None
        replay = None

    support_decision, support_source = _support_decision(raw, package)
    base_checks: BaseValidityChecks | None = None
    comparison: AnswerSemanticComparison | None = None
    binding = None
    observed_events: tuple[str, ...] = ()
    program_closed, terminal_verified = _program_progress(
        package.operational_record, raw.observations
    )
    if evaluable:
        if prompt_audit is None or replay is None:
            raise ValueError("v26.155 evaluable endpoint lacks verifier prerequisites")
        base_checks, comparison = _base_inputs(
            raw=raw,
            package=package,
            replay=replay,
            noninterference=prompt_audit,
        )
        binding = make_noninterference_artifact_binding(
            noninterference_contract_id=EXPECTED_NONINTERFERENCE_CONTRACT_ID,
            noninterference_audit_id=prompt_audit.audit_id,
            task_package_id=package.task_package_id,
        )
        observed_events = _mechanism_events(
            mechanism_id=package.mechanism_id,
            record=package.operational_record,
            observations=raw.observations,
            completed=raw.completed_result is not None,
        )

    joint = evaluate_joint_support_validity(
        contract=inputs.joint_contract,
        support_decision=support_decision,
        trajectory_id=raw.artifact_id,
        task_package_id=package.task_package_id,
        model_endpoint_observed=model_endpoint,
        instrument_integrity=instrument,
        privacy_compliant=privacy_compliant,
        mechanism_id=package.mechanism_id,
        base_checks=base_checks,
        noninterference_binding=binding,
        observed_mechanism_event_ids=observed_events,
    )

    gate_failures: list[str] = []
    if not support_available:
        gate_failures.append("measurement_support_exit")
    if not model_endpoint:
        gate_failures.append("model_endpoint_unobserved")
    if not instrument:
        gate_failures.append("instrument_failure")
    if not privacy_compliant:
        gate_failures.append("privacy_failure")
    if not (exact_model and thinking and usage):
        gate_failures.append("exact_model_thinking_usage_failure")
    if raw.terminal_disposition == "typed_budget_no_call":
        gate_failures.append("typed_budget_no_call")
    if raw.terminal_disposition == "provider_transport_failure":
        gate_failures.append("unresolved_transport_failure")

    cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "job_id": job.job_id,
        "task_package_id": job.task_package_id,
        "source_task_artifact_id": job.source_task_artifact_id,
        "mechanism_id": job.mechanism_id,
        "tier": job.tier,
        "sampling_mode": job.sampling_mode,
        "requested_path_id": job.requested_path_id,
        "requested_path_strategy": job.requested_path_strategy,
        "public_path_condition": job.public_path_condition,
        "public_condition_id": job.public_condition_id,
        "condition_binding_valid": True,
        "replicate_index": job.replicate_index,
        "seed": job.seed,
        "raw_execution_id": raw.artifact_id,
        "raw_execution_artifact": _descriptor(
            runner_vnext._raw_path(execution_dir, job),  # noqa: SLF001
            execution_dir,
        ),
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "execution_error": raw.execution_error,
        "measurement_support_available": support_available,
        "model_endpoint_observed": model_endpoint,
        "instrument_integrity": instrument,
        "privacy_compliant": privacy_compliant,
        "validity_evaluable": evaluable,
        "endpoint_projection_matches_raw": model_endpoint == raw.model_endpoint_observed,
        "support_decision_source": support_source,
        "support_decision": support_decision,
        "joint_result": joint,
        "online_noninterference_audit": prompt_audit,
        "runtime_replay": replay,
        "answer_comparison": comparison,
        "base_trajectory_validity": joint.base_report.valid,
        "mechanism_qualification": joint.mechanism_report.success,
        "qualified_trajectory_validity": joint.qualified_report.valid,
        "state_mapping_eligible": joint.state_mapping_eligible,
        "task_verifier_invocation_count": joint.task_verifier_invocation_count,
        "observed_mechanism_event_ids": observed_events,
        "first_action_interface_qualified": raw.first_action_interface_qualified,
        "program_closed": program_closed,
        "terminal_verification_complete": terminal_verified,
        "exact_qualified_final_payload_count": raw.exact_qualified_final_payload_count,
        "provider_call_count": raw.stage_one_provider_call_count,
        "transport_inclusive_invocation_count": raw.transport_inclusive_invocation_count,
        "provider_prompt_tokens": sum(item.prompt_tokens or 0 for item in raw.provider_telemetry),
        "provider_completion_tokens": sum(
            item.completion_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_reasoning_tokens": sum(
            item.reasoning_tokens or 0 for item in raw.provider_telemetry
        ),
        "provider_total_tokens": sum(item.total_tokens or 0 for item in raw.provider_telemetry),
        "estimated_cost_usd": format(cost, "f"),
        "exact_model_passed": exact_model,
        "fallback_absent": fallback_absent,
        "provider_native_tool_absent": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "dynamic_precall_binding_passed": dynamic,
        "exact_request_binding_passed": exact_request,
        "privacy_artifact_pairing_passed": pairing,
        "reversible_commit_integrity_passed": reversible,
        "rollout_budget_passed": resource_passed,
        "unresolved_transport_failure": raw.terminal_disposition == "provider_transport_failure",
        "typed_budget_no_call": raw.terminal_disposition == "typed_budget_no_call",
        "measurement_gate_failure_ids": tuple(sorted(set(gate_failures))),
    }
    provisional = execution.ReachabilityMeasurementResult.model_construct(
        result_id="pending", **values
    )
    return execution.ReachabilityMeasurementResult(
        result_id=_identity(
            provisional,
            "result_id",
            "finance_v26_fresh_reachability_measurement_result:",
        ),
        **values,
    )


def _independent_gate(
    results: Sequence[execution.ReachabilityMeasurementResult],
    *,
    formal_gate: execution.MeasurementGateAudit,
) -> IndependentMeasurementGateAudit:
    values: dict[str, Any] = {
        "complete_raw_count": len(results),
        "model_endpoint_count": sum(item.model_endpoint_observed for item in results),
        "measurement_support_exit_count": sum(
            not item.measurement_support_available for item in results
        ),
        "instrument_failure_count": sum(not item.instrument_integrity for item in results),
        "privacy_failure_count": sum(not item.privacy_compliant for item in results),
        "exact_model_thinking_usage_failure_count": sum(
            not (
                item.exact_model_passed
                and item.thinking_continuity_passed
                and item.provider_usage_complete
            )
            for item in results
        ),
        "typed_budget_no_call_count": sum(item.typed_budget_no_call for item in results),
        "unresolved_transport_failure_count": sum(
            item.unresolved_transport_failure for item in results
        ),
    }
    checks = {
        "complete_raw_360_of_360": values["complete_raw_count"] == 360,
        "model_endpoint_360_of_360": values["model_endpoint_count"] == 360,
        "measurement_support_exit_zero": values["measurement_support_exit_count"] == 0,
        "instrument_failure_zero": values["instrument_failure_count"] == 0,
        "privacy_failure_zero": values["privacy_failure_count"] == 0,
        "exact_model_thinking_usage_failure_zero": (
            values["exact_model_thinking_usage_failure_count"] == 0
        ),
        "typed_budget_no_call_zero": values["typed_budget_no_call_count"] == 0,
        "unresolved_transport_failure_zero": values["unresolved_transport_failure_count"] == 0,
    }
    values.update(
        {
            "failure_ids": tuple(sorted(name for name, passed in checks.items() if not passed)),
            "passed": all(checks.values()),
            "reachability_estimands_authorized": all(checks.values()),
            "state_mapping_eligibility_estimand_authorized": all(checks.values()),
        }
    )
    independent_payload = {
        "complete_raw_count": values["complete_raw_count"],
        "model_endpoint_count": values["model_endpoint_count"],
        "measurement_support_exit_count": values["measurement_support_exit_count"],
        "instrument_failure_count": values["instrument_failure_count"],
        "privacy_failure_count": values["privacy_failure_count"],
        "exact_model_thinking_usage_failure_count": values[
            "exact_model_thinking_usage_failure_count"
        ],
        "typed_budget_no_call_count": values["typed_budget_no_call_count"],
        "unresolved_transport_failure_count": values["unresolved_transport_failure_count"],
        "failure_ids": values["failure_ids"],
        "passed": values["passed"],
        "reachability_estimands_authorized": values["reachability_estimands_authorized"],
        "state_mapping_eligibility_estimand_authorized": values[
            "state_mapping_eligibility_estimand_authorized"
        ],
    }
    formal_payload = formal_gate.model_dump(
        mode="python",
        include=set(independent_payload),
    )
    if independent_payload != formal_payload:
        raise ValueError("v26.155 independent Measurement Gate differs from formal Gate")
    provisional = IndependentMeasurementGateAudit.model_construct(audit_id="pending", **values)
    return IndependentMeasurementGateAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_independent_measurement_gate:",
        ),
        **values,
    )


def _unconditional_task_summaries(
    results: Sequence[execution.ReachabilityMeasurementResult],
    *,
    authorized: bool,
) -> tuple[execution.UnconditionalTaskSummary, ...]:
    grouped: dict[str, list[execution.ReachabilityMeasurementResult]] = defaultdict(list)
    for item in results:
        if item.sampling_mode == "reachability_unconditional":
            grouped[item.task_package_id].append(item)
    if len(grouped) != 12 or sum(map(len, grouped.values())) != 144:
        raise ValueError("v26.155 unconditional Task denominator changed")
    summaries: list[execution.UnconditionalTaskSummary] = []
    for task_package_id in sorted(grouped):
        rows = grouped[task_package_id]
        if len(rows) != 12:
            raise ValueError("v26.155 unconditional Task lacks twelve replicas")
        first = rows[0]
        base = sum(item.base_trajectory_validity is True for item in rows)
        mechanism = sum(item.mechanism_qualification is True for item in rows)
        qualified = sum(item.qualified_trajectory_validity is True for item in rows)
        values: dict[str, Any] = {
            "task_package_id": task_package_id,
            "source_task_artifact_id": first.source_task_artifact_id,
            "mechanism_id": first.mechanism_id,
            "tier": first.tier,
            "model_endpoint_count": sum(item.model_endpoint_observed for item in rows),
            "evaluable_count": sum(item.validity_evaluable for item in rows),
            "base_valid_count": base,
            "mechanism_qualified_count": mechanism,
            "qualified_valid_count": qualified,
            "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in rows),
            "base_fraction": f"{base}/12" if authorized else None,
            "mechanism_fraction": f"{mechanism}/12" if authorized else None,
            "qualified_fraction": f"{qualified}/12" if authorized else None,
            "terminal_counts": dict(
                sorted(Counter(item.raw_terminal_disposition for item in rows).items())
            ),
            "estimand_authorized": authorized,
        }
        provisional = execution.UnconditionalTaskSummary.model_construct(
            summary_id="pending", **values
        )
        summaries.append(
            execution.UnconditionalTaskSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_unconditional_task_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _conditioned_path_summaries(
    results: Sequence[execution.ReachabilityMeasurementResult],
    *,
    authorized: bool,
) -> tuple[execution.ConditionedPathSummary, ...]:
    grouped: dict[str, list[execution.ReachabilityMeasurementResult]] = defaultdict(list)
    for item in results:
        if item.sampling_mode == "reachability_conditioned":
            grouped[cast(str, item.requested_path_id)].append(item)
    if len(grouped) != 36 or sum(map(len, grouped.values())) != 216:
        raise ValueError("v26.155 conditioned Path denominator changed")
    summaries: list[execution.ConditionedPathSummary] = []
    for path_id in sorted(grouped):
        rows = grouped[path_id]
        if len(rows) != 6:
            raise ValueError("v26.155 conditioned Path lacks six replicas")
        first = rows[0]
        strategy = cast(preflight.PathStrategy, first.requested_path_strategy)
        condition = cast(str, first.public_path_condition)
        condition_id = cast(str, first.public_condition_id)
        if any(
            (
                item.requested_path_strategy,
                item.public_path_condition,
                item.public_condition_id,
            )
            != (strategy, condition, condition_id)
            for item in rows
        ):
            raise ValueError("v26.155 conditioned Path rows crossed route bindings")
        base = sum(item.base_trajectory_validity is True for item in rows)
        mechanism = sum(item.mechanism_qualification is True for item in rows)
        qualified = sum(item.qualified_trajectory_validity is True for item in rows)
        values: dict[str, Any] = {
            "path_id": path_id,
            "path_strategy_id": strategy,
            "public_path_condition": condition,
            "public_condition_id": condition_id,
            "task_package_id": first.task_package_id,
            "source_task_artifact_id": first.source_task_artifact_id,
            "mechanism_id": first.mechanism_id,
            "tier": first.tier,
            "model_endpoint_count": sum(item.model_endpoint_observed for item in rows),
            "evaluable_count": sum(item.validity_evaluable for item in rows),
            "base_valid_count": base,
            "mechanism_qualified_count": mechanism,
            "qualified_valid_count": qualified,
            "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in rows),
            "base_fraction": f"{base}/6" if authorized else None,
            "mechanism_fraction": f"{mechanism}/6" if authorized else None,
            "qualified_fraction": f"{qualified}/6" if authorized else None,
            "terminal_counts": dict(
                sorted(Counter(item.raw_terminal_disposition for item in rows).items())
            ),
            "estimand_authorized": authorized,
        }
        provisional = execution.ConditionedPathSummary.model_construct(
            summary_id="pending", **values
        )
        summaries.append(
            execution.ConditionedPathSummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_conditioned_path_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


SummaryCountField = Literal[
    "base_valid_count",
    "mechanism_qualified_count",
    "qualified_valid_count",
]


def _mean_primary_fraction(
    rows: Sequence[execution.UnconditionalTaskSummary] | Sequence[execution.ConditionedPathSummary],
    field: SummaryCountField,
    *,
    denominator: int,
) -> str:
    total = sum(Decimal(getattr(item, field)) / Decimal(denominator) for item in rows)
    return format(total / Decimal(len(rows)), "f")


def _mechanism_summaries(
    tasks: Sequence[execution.UnconditionalTaskSummary],
    paths: Sequence[execution.ConditionedPathSummary],
    *,
    authorized: bool,
) -> tuple[execution.MechanismReachabilitySummary, ...]:
    task_groups: dict[MechanismId, list[execution.UnconditionalTaskSummary]] = defaultdict(list)
    path_groups: dict[MechanismId, list[execution.ConditionedPathSummary]] = defaultdict(list)
    for item in tasks:
        task_groups[item.mechanism_id].append(item)
    for item in paths:
        path_groups[item.mechanism_id].append(item)
    summaries: list[execution.MechanismReachabilitySummary] = []
    for mechanism_id in sorted(task_groups):
        task_rows = task_groups[mechanism_id]
        path_rows = path_groups[mechanism_id]
        if len(task_rows) != 3 or len(path_rows) != 9:
            raise ValueError("v26.155 Mechanism Task/Path partition changed")
        values: dict[str, Any] = {
            "mechanism_id": mechanism_id,
            "unconditional_base_valid_count": sum(item.base_valid_count for item in task_rows),
            "unconditional_mechanism_qualified_count": sum(
                item.mechanism_qualified_count for item in task_rows
            ),
            "unconditional_qualified_valid_count": sum(
                item.qualified_valid_count for item in task_rows
            ),
            "conditioned_base_valid_count": sum(item.base_valid_count for item in path_rows),
            "conditioned_mechanism_qualified_count": sum(
                item.mechanism_qualified_count for item in path_rows
            ),
            "conditioned_qualified_valid_count": sum(
                item.qualified_valid_count for item in path_rows
            ),
            "tasks_with_unconditional_qualified_trajectory": sum(
                item.qualified_valid_count > 0 for item in task_rows
            ),
            "paths_with_conditioned_qualified_trajectory": sum(
                item.qualified_valid_count > 0 for item in path_rows
            ),
            "unconditional_task_weighted_qualified_fraction": (
                _mean_primary_fraction(task_rows, "qualified_valid_count", denominator=12)
                if authorized
                else None
            ),
            "conditioned_path_weighted_qualified_fraction": (
                _mean_primary_fraction(path_rows, "qualified_valid_count", denominator=6)
                if authorized
                else None
            ),
            "estimand_authorized": authorized,
        }
        provisional = execution.MechanismReachabilitySummary.model_construct(
            summary_id="pending", **values
        )
        summaries.append(
            execution.MechanismReachabilitySummary(
                summary_id=_identity(
                    provisional,
                    "summary_id",
                    "finance_v26_fresh_reachability_mechanism_estimand:",
                ),
                **values,
            )
        )
    return tuple(summaries)


def _projection_audit(
    *,
    inputs: AuditInputs,
    execution_dir: Path,
) -> tuple[
    IndependentProjectionAudit,
    tuple[runner_vnext.FreshReachabilityRawExecution, ...],
]:
    checkpoint_rows = tuple(
        execution.ReachabilityMeasurementResult.model_validate_json(line)
        for line in (execution_dir / "fresh_reachability_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    aggregate_payload = _load(execution_dir / "fresh_reachability_measurement_results.json")
    if not isinstance(aggregate_payload, list):
        raise ValueError("v26.155 aggregate measurement payload is not a list")
    aggregate_rows = tuple(
        execution.ReachabilityMeasurementResult.model_validate(item) for item in aggregate_payload
    )
    prompt_payload = _load(execution_dir / "online_noninterference_audits.json")
    if not isinstance(prompt_payload, list):
        raise ValueError("v26.155 Prompt audit payload is not a list")
    formal_prompts = tuple(
        execution.OnlineNoninterferenceAudit.model_validate(item) for item in prompt_payload
    )
    checkpoint_by_job = {item.job_id: item for item in checkpoint_rows}
    aggregate_by_job = {item.job_id: item for item in aggregate_rows}
    formal_prompt_by_job = {item.job_id: item for item in formal_prompts}
    jobs = tuple(inputs.manifest.jobs)
    if not (len(checkpoint_by_job) == len(aggregate_by_job) == len(jobs) == 360):
        raise ValueError("v26.155 checkpoint/aggregate denominator changed")

    recomputed: list[execution.ReachabilityMeasurementResult] = []
    raws: list[runner_vnext.FreshReachabilityRawExecution] = []
    base_pass_counts: Counter[str] = Counter({name: 0 for name in BaseValidityChecks.model_fields})
    prompt_match_count = 0
    null_prompt_match_count = 0
    for index, job in enumerate(jobs, start=1):
        raw_path = runner_vnext._raw_path(execution_dir, job)  # noqa: SLF001
        if not raw_path.is_file():
            raise ValueError(f"v26.155 Raw is missing: {job.job_id}")
        raw = runner_vnext.FreshReachabilityRawExecution.model_validate(_load(raw_path))
        result = _project_measurement_independently(
            raw=raw,
            job=job,
            package=_package_for_job(inputs, job),
            inputs=inputs,
            execution_dir=execution_dir,
        )
        checkpoint = checkpoint_by_job[job.job_id]
        aggregate = aggregate_by_job[job.job_id]
        if _canonical_bytes(result) != _canonical_bytes(checkpoint):
            raise ValueError(f"v26.155 checkpoint projection changed: {job.job_id}")
        if _canonical_bytes(result) != _canonical_bytes(aggregate):
            raise ValueError(f"v26.155 aggregate projection changed: {job.job_id}")
        if result.joint_result.result_id != checkpoint.joint_result.result_id:
            raise ValueError(f"v26.155 joint result changed: {job.job_id}")
        prompt = result.online_noninterference_audit
        formal_prompt = formal_prompt_by_job.get(job.job_id)
        if prompt is None:
            if formal_prompt is not None:
                raise ValueError(f"v26.155 null Prompt audit mismatch: {job.job_id}")
            null_prompt_match_count += 1
        else:
            if prompt != formal_prompt:
                raise ValueError(f"v26.155 online Prompt audit changed: {job.job_id}")
            prompt_match_count += 1
        checks = result.joint_result.base_report.checks
        if checks is not None:
            base_pass_counts.update(
                name for name, passed in checks.model_dump(mode="python").items() if passed
            )
        recomputed.append(result)
        raws.append(raw)
        if index % 24 == 0:
            print(f"[v26.155] independent Raw projection {index}/360 exact", flush=True)

    if set(formal_prompt_by_job) != {
        item.job_id for item in recomputed if item.online_noninterference_audit is not None
    }:
        raise ValueError("v26.155 formal Prompt audit set changed")
    values: dict[str, Any] = {
        "exact_prompt_audit_match_count": prompt_match_count,
        "null_prompt_audit_match_count": null_prompt_match_count,
        "base_check_pass_counts": dict(sorted(base_pass_counts.items())),
        "recomputed_results": tuple(recomputed),
    }
    provisional = IndependentProjectionAudit.model_construct(audit_id="pending", **values)
    return (
        IndependentProjectionAudit(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_fresh_reachability_independent_projection:",
            ),
            **values,
        ),
        tuple(raws),
    )


def _provider_artifact_audit(
    *,
    execution_dir: Path,
    results: Sequence[execution.ReachabilityMeasurementResult],
    raws: Sequence[runner_vnext.FreshReachabilityRawExecution],
) -> IndependentProviderArtifactAudit:
    lineage = execution.RawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    if lineage.audit_id != EXPECTED_RAW_LINEAGE_ID:
        raise ValueError("v26.155 formal Raw lineage identity changed")

    raw_descriptors = tuple(item.raw_execution_artifact for item in results)
    provider_descriptors = tuple(
        descriptor
        for raw in raws
        for descriptor in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
            *raw.transport_invocation_artifacts,
        )
    )
    expected = {
        (item.relative_path, item.sha256, item.byte_count)
        for item in (*lineage.raw_descriptors, *lineage.provider_artifact_descriptors)
    }
    observed = {
        (item.relative_path, item.sha256, item.byte_count)
        for item in (*raw_descriptors, *provider_descriptors)
    }
    if expected != observed or len(observed) != len(raw_descriptors) + len(provider_descriptors):
        raise ValueError("v26.155 Raw Lineage descriptor set changed")
    for descriptor in (*raw_descriptors, *provider_descriptors):
        path = execution_dir / descriptor.relative_path
        if (
            not path.is_file()
            or _sha256(path) != descriptor.sha256
            or path.stat().st_size != descriptor.byte_count
        ):
            raise ValueError(f"v26.155 descriptor bytes changed: {descriptor.relative_path}")
    if (
        _canonical_bytes(tuple(results))
        != (execution_dir / "fresh_reachability_measurement_results.json").read_bytes()
    ):
        raise ValueError("v26.155 checkpoint and aggregate result bytes changed")
    if any(
        raw.artifact_id != result.raw_execution_id
        for raw, result in zip(raws, results, strict=True)
    ):
        raise ValueError("v26.155 Raw/checkpoint parent binding changed")

    provider_calls = sum(raw.stage_one_provider_call_count for raw in raws)
    transport_calls = sum(raw.transport_inclusive_invocation_count for raw in raws)
    values: dict[str, Any] = {
        "provider_envelope_count": sum(len(raw.provider_envelope_artifacts) for raw in raws),
        "public_projection_count": sum(
            len(raw.public_payload_projection_artifacts) for raw in raws
        ),
        "transport_invocation_count": transport_calls,
        "validated_provider_pair_count": provider_calls,
        "descriptor_byte_match_count": len(observed),
        "provider_call_count": provider_calls,
    }
    provisional = IndependentProviderArtifactAudit.model_construct(audit_id="pending", **values)
    return IndependentProviderArtifactAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_independent_provider_artifacts:",
        ),
        **values,
    )


def _estimand_audit(
    *,
    results: Sequence[execution.ReachabilityMeasurementResult],
    execution_dir: Path,
    report: execution.ReachabilityExecutionReport,
    gate: IndependentMeasurementGateAudit,
) -> IndependentEstimandAudit:
    tasks = _unconditional_task_summaries(results, authorized=gate.passed)
    paths = _conditioned_path_summaries(results, authorized=gate.passed)
    mechanisms = _mechanism_summaries(tasks, paths, authorized=gate.passed)
    if (
        _canonical_bytes(tasks)
        != (execution_dir / "unconditional_task_estimand_summaries.json").read_bytes()
    ):
        raise ValueError("v26.155 unconditional Task summary bytes changed")
    if (
        _canonical_bytes(paths)
        != (execution_dir / "conditioned_path_estimand_summaries.json").read_bytes()
    ):
        raise ValueError("v26.155 conditioned Path summary bytes changed")
    if (
        _canonical_bytes(mechanisms)
        != (execution_dir / "mechanism_estimand_summaries.json").read_bytes()
    ):
        raise ValueError("v26.155 mechanism summary bytes changed")
    if (
        tasks != report.unconditional_task_summaries
        or paths != report.conditioned_path_summaries
        or mechanisms != report.mechanism_summaries
    ):
        raise ValueError("v26.155 report summary binding changed")
    values: dict[str, Any] = {
        "unconditional_task_summaries": tasks,
        "conditioned_path_summaries": paths,
        "mechanism_summaries": mechanisms,
        "base_valid_count": sum(item.base_trajectory_validity is True for item in results),
        "mechanism_qualified_count": sum(item.mechanism_qualification is True for item in results),
        "qualified_valid_count": sum(
            item.qualified_trajectory_validity is True for item in results
        ),
        "state_mapping_eligible_count": sum(item.state_mapping_eligible for item in results),
        "unconditional_task_weighted_base_fraction": (
            _mean_primary_fraction(tasks, "base_valid_count", denominator=12)
            if gate.passed
            else None
        ),
        "unconditional_task_weighted_mechanism_fraction": (
            _mean_primary_fraction(tasks, "mechanism_qualified_count", denominator=12)
            if gate.passed
            else None
        ),
        "unconditional_task_weighted_qualified_fraction": (
            _mean_primary_fraction(tasks, "qualified_valid_count", denominator=12)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_base_fraction": (
            _mean_primary_fraction(paths, "base_valid_count", denominator=6)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_mechanism_fraction": (
            _mean_primary_fraction(paths, "mechanism_qualified_count", denominator=6)
            if gate.passed
            else None
        ),
        "conditioned_path_weighted_qualified_fraction": (
            _mean_primary_fraction(paths, "qualified_valid_count", denominator=6)
            if gate.passed
            else None
        ),
        "reachability_estimands_authorized": gate.passed,
    }
    formal_values = report.model_dump(mode="python", include=set(values))
    if formal_values != values:
        raise ValueError("v26.155 independently reconstructed estimands changed")
    provisional = IndependentEstimandAudit.model_construct(audit_id="pending", **values)
    return IndependentEstimandAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_independent_estimand:",
        ),
        **values,
    )


def _validity_decomposition(
    *,
    results: Sequence[execution.ReachabilityMeasurementResult],
    report: execution.ReachabilityExecutionReport,
    gate: IndependentMeasurementGateAudit,
    estimand: IndependentEstimandAudit,
) -> IndependentValidityDecompositionAudit:
    base_failures: Counter[str] = Counter()
    mechanism_missing: Counter[str] = Counter()
    terminal_failure_types: Counter[str] = Counter()
    for item in results:
        base_failures.update(item.joint_result.base_report.failed_check_ids)
        mechanism_missing.update(item.joint_result.mechanism_report.missing_event_ids)
        terminal_failure_types.update((item.terminal_failure_type or "none",))
    unconditional = tuple(
        item for item in results if item.sampling_mode == "reachability_unconditional"
    )
    conditioned = tuple(
        item for item in results if item.sampling_mode == "reachability_conditioned"
    )
    report_values: dict[str, Any] = {
        "terminal_counts": dict(
            sorted(Counter(item.raw_terminal_disposition for item in results).items())
        ),
        "measurement_gate_passed": gate.passed,
        "reachability_estimands_authorized": gate.reachability_estimands_authorized,
        "base_valid_count": estimand.base_valid_count,
        "mechanism_qualified_count": estimand.mechanism_qualified_count,
        "qualified_valid_count": estimand.qualified_valid_count,
        "state_mapping_eligible_count": estimand.state_mapping_eligible_count,
        "unconditional_base_valid_count": sum(
            item.base_trajectory_validity is True for item in unconditional
        ),
        "unconditional_mechanism_qualified_count": sum(
            item.mechanism_qualification is True for item in unconditional
        ),
        "unconditional_qualified_valid_count": sum(
            item.qualified_trajectory_validity is True for item in unconditional
        ),
        "conditioned_base_valid_count": sum(
            item.base_trajectory_validity is True for item in conditioned
        ),
        "conditioned_mechanism_qualified_count": sum(
            item.mechanism_qualification is True for item in conditioned
        ),
        "conditioned_qualified_valid_count": sum(
            item.qualified_trajectory_validity is True for item in conditioned
        ),
        "unconditional_task_weighted_base_fraction": (
            estimand.unconditional_task_weighted_base_fraction
        ),
        "unconditional_task_weighted_mechanism_fraction": (
            estimand.unconditional_task_weighted_mechanism_fraction
        ),
        "unconditional_task_weighted_qualified_fraction": (
            estimand.unconditional_task_weighted_qualified_fraction
        ),
        "conditioned_path_weighted_base_fraction": (
            estimand.conditioned_path_weighted_base_fraction
        ),
        "conditioned_path_weighted_mechanism_fraction": (
            estimand.conditioned_path_weighted_mechanism_fraction
        ),
        "conditioned_path_weighted_qualified_fraction": (
            estimand.conditioned_path_weighted_qualified_fraction
        ),
        "provider_call_count": sum(item.provider_call_count for item in results),
        "transport_inclusive_invocation_count": sum(
            item.transport_inclusive_invocation_count for item in results
        ),
        "provider_prompt_tokens": sum(item.provider_prompt_tokens for item in results),
        "provider_completion_tokens": sum(item.provider_completion_tokens for item in results),
        "provider_reasoning_tokens": sum(item.provider_reasoning_tokens for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "estimated_cost_usd": format(
            sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0")),
            "f",
        ),
    }
    if report.model_dump(mode="python", include=set(report_values)) != report_values:
        raise ValueError("v26.155 independently reconstructed report aggregates changed")
    endpoint_count = sum(item.model_endpoint_observed for item in results)
    completed_count = sum(
        item.raw_terminal_disposition == "completed_model_endpoint" for item in results
    )
    model_failure_count = sum(
        item.raw_terminal_disposition == "model_result_failure" for item in results
    )
    values: dict[str, Any] = {
        "exact_model_endpoint_count": endpoint_count,
        "completed_model_endpoint_count": completed_count,
        "model_result_failure_count": model_failure_count,
        "other_model_endpoint_count": endpoint_count - completed_count - model_failure_count,
        "measurement_support_exit_count": sum(
            item.raw_terminal_disposition == "measurement_support_exit" for item in results
        ),
        "program_closed_count": sum(item.program_closed for item in results),
        "terminal_verification_complete_count": sum(
            item.terminal_verification_complete for item in results
        ),
        "exact_qualified_final_payload_count": sum(
            item.exact_qualified_final_payload_count for item in results
        ),
        "base_valid_count": estimand.base_valid_count,
        "mechanism_qualified_count": estimand.mechanism_qualified_count,
        "qualified_valid_count": estimand.qualified_valid_count,
        "state_mapping_eligible_count": estimand.state_mapping_eligible_count,
        "base_failed_check_counts": dict(sorted(base_failures.items())),
        "mechanism_missing_event_counts": dict(sorted(mechanism_missing.items())),
        "terminal_failure_type_counts": dict(sorted(terminal_failure_types.items())),
        "formal_report_aggregate_match_count": len(report_values),
        "observed_provider_call_count": report_values["provider_call_count"],
        "observed_transport_invocation_count": report_values[
            "transport_inclusive_invocation_count"
        ],
        "observed_prompt_tokens": report_values["provider_prompt_tokens"],
        "observed_completion_tokens": report_values["provider_completion_tokens"],
        "observed_reasoning_tokens": report_values["provider_reasoning_tokens"],
        "observed_total_tokens": report_values["provider_total_tokens"],
        "observed_estimated_cost_usd": report_values["estimated_cost_usd"],
        "qualified_equals_base_and_mechanism_count": sum(
            (
                item.qualified_trajectory_validity
                == bool(item.base_trajectory_validity and item.mechanism_qualification)
            )
            if item.validity_evaluable
            else (
                item.base_trajectory_validity is None
                and item.mechanism_qualification is None
                and item.qualified_trajectory_validity is None
            )
            for item in results
        ),
        "support_or_integrity_rows_with_nonnull_validity": sum(
            (not item.validity_evaluable)
            and (
                item.base_trajectory_validity is not None
                or item.mechanism_qualification is not None
                or item.qualified_trajectory_validity is not None
            )
            for item in results
        ),
    }
    provisional = IndependentValidityDecompositionAudit.model_construct(
        audit_id="pending", **values
    )
    return IndependentValidityDecompositionAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_validity_decomposition:",
        ),
        **values,
    )


def _support_boundary(
    *,
    results: Sequence[execution.ReachabilityMeasurementResult],
    raws: Sequence[runner_vnext.FreshReachabilityRawExecution],
    inputs: AuditInputs,
) -> SupportBoundaryAudit:
    raw_by_job = {item.job_id: item for item in raws}
    support_rows = tuple(
        item for item in results if item.raw_terminal_disposition == "measurement_support_exit"
    )
    support_raws = tuple(raw_by_job[item.job_id] for item in support_rows)
    values: dict[str, Any] = {
        "measurement_support_exit_count": len(support_rows),
        "ordinary_detour_allowance_exhausted_count": sum(
            item.terminal_failure_type == "ordinary_detour_allowance_exhausted"
            for item in support_rows
        ),
        "raw_native_instrument_integrity_true_count": sum(
            item.instrument_integrity for item in support_raws
        ),
        "formal_projected_instrument_failure_overlap_count": sum(
            not item.instrument_integrity for item in support_rows
        ),
        "second_ordinary_detour_count": sum(
            item.ordinary_detour_count == 2 for item in support_raws
        ),
        "baseline_available_count": sum(
            bool(item.measurement_support_decisions)
            and item.measurement_support_decisions[-1].status == "available"
            for item in support_raws
        ),
        "later_provider_call_count": sum(
            item.later_provider_calls_after_support_exit for item in support_raws
        ),
        "provider_token_overrun_count": sum(
            item.cumulative_provider_tokens > inputs.resource.rollout_upper_bound_tokens
            for item in support_raws
        ),
        "provider_call_overrun_count": sum(
            item.stage_one_provider_call_count > inputs.resource.maximum_stage_one_provider_calls
            for item in support_raws
        ),
        "transport_invocation_overrun_count": sum(
            item.transport_inclusive_invocation_count
            > inputs.resource.maximum_transport_inclusive_invocations
            for item in support_raws
        ),
        "support_exit_job_ids": tuple(sorted(item.job_id for item in support_rows)),
        "reachability_frequency_estimate_authorized": len(support_rows) == 0,
    }
    provisional = SupportBoundaryAudit.model_construct(audit_id="pending", **values)
    return SupportBoundaryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_support_boundary:",
        ),
        **values,
    )


def _destructive(
    gate: IndependentMeasurementGateAudit,
    estimand: IndependentEstimandAudit,
    decomposition: IndependentValidityDecompositionAudit,
) -> DestructiveAudit:
    if decomposition.qualified_valid_count != estimand.qualified_valid_count:
        raise ValueError("v26.155 destructive baseline changed")
    names = (
        "audit_mapping_by_saved_assignment_fields_only",
        "authorize_reachability_frequency_after_failed_gate",
        "change_detour_allowance_after_outcome",
        "change_model_or_thinking_profile",
        "change_prompt_candidate_or_grammar",
        "classify_support_exit_as_model_invalid",
        "construct_provider_client_during_audit",
        "count_support_exit_as_independent_instrument_cause",
        "infer_or_recover_missing_model_endpoint",
        "map_base_valid_mechanism_invalid_row",
        "map_capability_row_into_reachability",
        "map_model_invalid_row",
        "map_static_path_as_empirical_state",
        "map_support_or_integrity_exit",
        "omit_mapper_contract_binding",
        "omit_omega_task_context_binding",
        "omit_path_catalog_binding",
        "omit_qualified_validity_report_binding",
        "omit_raw_observation_prefix_hash",
        "omit_route_condition_binding",
        "omit_structural_state_binding",
        "omit_trajectory_content_hash",
        "pool_historical_or_capability_rows",
        "repair_or_replace_model_action",
        "rerun_support_exit_job",
        "run_state_mapping_during_postrun_audit",
        "treat_assignment_count_as_unique_state_count",
        "treat_eligibility_count_as_mapping_count",
        "write_private_reasoning_or_hash",
        "write_training_release_or_production_rows",
    )
    if len(names) != 30 or len(set(names)) != 30:
        raise ValueError("v26.155 destructive mutation set is malformed")
    values: dict[str, Any] = {
        "mutation_results": tuple(MutationResult(mutation_name=name) for name in sorted(names))
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_fresh_reachability_postrun_destructive:",
        ),
        **values,
    )


def _transition(
    gate: IndependentMeasurementGateAudit,
    estimand: IndependentEstimandAudit,
    decomposition: IndependentValidityDecompositionAudit,
    support: SupportBoundaryAudit,
) -> ProspectiveTransitionContract:
    mapping_preflight = bool(
        decomposition.qualified_valid_count > 0
        and decomposition.support_or_integrity_rows_with_nonnull_validity == 0
    )
    if not mapping_preflight:
        raise ValueError("v26.155 has no independently qualified row for Mapper preflight")
    values: dict[str, Any] = {
        "independent_measurement_gate_id": gate.audit_id,
        "independent_estimand_audit_id": estimand.audit_id,
        "independent_validity_decomposition_id": decomposition.audit_id,
        "support_boundary_audit_id": support.audit_id,
        "qualified_valid_count": decomposition.qualified_valid_count,
        "measurement_support_exit_count": support.measurement_support_exit_count,
        "reachability_estimands_authorized": gate.reachability_estimands_authorized,
        "valid_only_observed_state_mapping_preflight_authorized": mapping_preflight,
        "status": (
            "reachability_gate_passed_mapping_preflight_only"
            if gate.passed
            else "reachability_gate_failed_observed_valid_mapping_preflight_only"
        ),
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_fresh_reachability_postrun_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_postrun_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> PostrunAuditReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    print(
        f"[v26.155] source replay {source.replay_pass_count}/{source.replayed_file_count} exact",
        flush=True,
    )
    inputs = _load_inputs(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    projection, raws = _projection_audit(inputs=inputs, execution_dir=execution_dir)
    results = projection.recomputed_results
    provider = _provider_artifact_audit(
        execution_dir=execution_dir,
        results=results,
        raws=raws,
    )
    formal_gate = execution.MeasurementGateAudit.model_validate(
        _load(execution_dir / "measurement_gate_audit.json")
    )
    gate = _independent_gate(results, formal_gate=formal_gate)
    estimand = _estimand_audit(
        results=results,
        execution_dir=execution_dir,
        report=inputs.report,
        gate=gate,
    )
    support = _support_boundary(results=results, raws=raws, inputs=inputs)
    decomposition = _validity_decomposition(
        results=results,
        report=inputs.report,
        gate=gate,
        estimand=estimand,
    )
    destructive = _destructive(gate, estimand, decomposition)
    transition = _transition(gate, estimand, decomposition, support)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("destructive_audit.json", destructive),
        ("independent_estimand_audit.json", estimand),
        ("independent_measurement_gate_audit.json", gate),
        ("independent_projection_audit.json", projection),
        ("independent_provider_artifact_audit.json", provider),
        ("prospective_transition_contract.json", transition),
        ("support_boundary_audit.json", support),
        ("source_replay_audit.json", source),
        ("validity_decomposition_audit.json", decomposition),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values: dict[str, Any] = {
        "source_replay_audit_id": source.audit_id,
        "provider_artifact_audit_id": provider.audit_id,
        "independent_projection_audit_id": projection.audit_id,
        "independent_measurement_gate_id": gate.audit_id,
        "independent_estimand_audit_id": estimand.audit_id,
        "validity_decomposition_audit_id": decomposition.audit_id,
        "support_boundary_audit_id": support.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "measurement_gate_passed": gate.passed,
        "reachability_estimands_authorized": gate.reachability_estimands_authorized,
        "base_valid_count": decomposition.base_valid_count,
        "mechanism_qualified_count": decomposition.mechanism_qualified_count,
        "qualified_valid_count": decomposition.qualified_valid_count,
        "state_mapping_eligible_count": decomposition.state_mapping_eligible_count,
        "measurement_support_exit_count": support.measurement_support_exit_count,
        "valid_only_mapping_preflight_authorized": (
            transition.valid_only_observed_state_mapping_preflight_authorized
        ),
        "status": (
            "reachability_postrun_audit_passed"
            if gate.passed
            else "reachability_postrun_audit_closed_failed_gate"
        ),
        "detail_files": details,
    }
    provisional = PostrunAuditReport.model_construct(report_id="pending", **values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_fresh_reachability_postrun_audit_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Independently audit the exact v26.154 fresh Reachability denominator"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument(
        "--execution-dir",
        type=Path,
        default=package_default / execution.OUTPUT_DIR,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_default / OUTPUT_DIR,
    )
    args = parser.parse_args()
    report = build_postrun_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
