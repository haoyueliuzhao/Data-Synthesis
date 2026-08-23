from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_preflight as recovery,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingVerificationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    evaluate_mechanism_estimand,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_128_transport_recovery_postrun_audit_v1_20260823"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_128_transport_recovery_postrun_audit_v1_20260823"
)
EXECUTION_DIR: Final = execution.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_transport_recovery_postrun_audit.py"
)
EXPECTED_EXECUTION_REPORT_ID: Final = (
    "finance_v26_transport_recovery_execution_report:"
    "df1540cbc8ef04a42b45ee3e683f502ee0956d83ed7344a35ad2c4254c4c1989"
)
EXPECTED_EXECUTION_SOURCE_REPLAY_ID: Final = (
    "finance_v26_recovery_execution_source_replay:"
    "15e4d107714efd56fdbd78dfb99f635a9050e33527392d88170d4e1d150ee4ff"
)
EXPECTED_RAW_LINEAGE_ID: Final = (
    "finance_v26_transport_recovery_raw_lineage:"
    "c2f0001f130b61265770783e2f2a4c710c3140d2798bcde6bdef7b2817411f18"
)
NEXT_STAGE: Final = (
    "fresh_unexposed_capability_and_reachability_population_"
    "kernel_binding_and_runner_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_127_transitive_source",
        "v26_127_execution_file",
        "v26_128_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class AuditSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    execution_source_replay_id: str = EXPECTED_EXECUTION_SOURCE_REPLAY_ID
    execution_transitive_file_count: Literal[2984] = 2984
    execution_file_count: Literal[149] = 149
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[3134] = 3134
    replay_pass_count: Literal[3134] = 3134
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3134, max_length=3134)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_postrun_source_replay.v1"] = (
        "finance_v26_transport_recovery_postrun_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> AuditSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.128 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.128 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_transport_recovery_postrun_source_replay:",
        ):
            raise ValueError("v26.128 source replay identity changed")
        return self


class IndependentRecoveryRow(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    formal_result_id: str = Field(min_length=1)
    successful_prefix_call_count: int = Field(ge=0, le=2)
    successor_call_count: int = Field(ge=1, le=12)
    exact_failed_call_replacement_count: Literal[1] = 1
    replacement_http_success: Literal[True] = True
    successor_total_tokens: int = Field(ge=0)
    original_failed_usage_imputed: Literal[False] = False
    program_closed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    postterminal_verification_completed: Literal[True] = True
    final_commit_count: Literal[1] = 1
    final_abi_crossed: bool
    answer_emitted: bool
    independent_validity: bool
    mechanism_success: bool
    terminal_category: Literal["model_valid_trajectory", "model_invalid_trajectory"]
    replay_v3_passed: Literal[True] = True
    exact_model_passed: Literal[True] = True
    thinking_continuity_passed: Literal[True] = True
    provider_usage_complete: Literal[True] = True
    privacy_pairing_passed: Literal[True] = True
    stage_two_provider_calls: Literal[0] = 0


class RawLineageReaudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_raw_lineage_id: str = EXPECTED_RAW_LINEAGE_ID
    execution_file_count: Literal[149] = 149
    top_level_file_count: Literal[9] = 9
    raw_execution_count: Literal[10] = 10
    successor_provider_envelope_count: Literal[65] = 65
    successor_payload_projection_count: Literal[65] = 65
    complete_provider_pair_count: Literal[65] = 65
    checkpoint_row_count: Literal[10] = 10
    job_result_count: Literal[10] = 10
    checkpoint_result_match_count: Literal[10] = 10
    raw_descriptor_match_count: Literal[10] = 10
    prefix_replay_match_count: Literal[10] = 10
    exact_replacement_binding_match_count: Literal[10] = 10
    replay_v3_pass_count: Literal[10] = 10
    formal_result_reproduction_count: Literal[10] = 10
    unique_envelope_id_count: Literal[65] = 65
    unique_projection_id_count: Literal[65] = 65
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    invalid_payload_key_persistence_count: Literal[0] = 0
    original_failed_usage_imputation_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    rows: tuple[IndependentRecoveryRow, ...] = Field(min_length=10, max_length=10)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_raw_lineage_reaudit.v1"] = (
        "finance_v26_transport_recovery_raw_lineage_reaudit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RawLineageReaudit:
        if tuple(item.recovery_job_id for item in self.rows) != tuple(
            sorted(item.recovery_job_id for item in self.rows)
        ):
            raise ValueError("v26.128 independent Recovery rows changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_transport_recovery_raw_lineage_reaudit:",
        ):
            raise ValueError("v26.128 Raw Lineage reaudit identity changed")
        return self


class TransportRecoveryOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_candidate_count: Literal[10] = 10
    recovery_job_count: Literal[10] = 10
    exact_failed_call_replacement_count: Literal[10] = 10
    replacement_http_success_count: Literal[10] = 10
    replacement_transport_failure_count: Literal[0] = 0
    successor_provider_call_count: Literal[65] = 65
    successor_http_success_count: Literal[65] = 65
    successor_transport_failure_count: Literal[0] = 0
    successor_instrument_failure_count: Literal[0] = 0
    successful_prefix_provider_call_count: Literal[6] = 6
    successful_prefix_calls_reissued: Literal[0] = 0
    frozen_historical_model_outcomes_rerun: Literal[0] = 0
    fresh_model_endpoint_count: Literal[10] = 10
    successor_prompt_tokens: Literal[206081] = 206081
    successor_completion_tokens: Literal[85491] = 85491
    successor_reasoning_tokens: Literal[77657] = 77657
    successor_total_tokens: Literal[291572] = 291572
    successor_estimated_cost_usd: Literal["0.04867940560000000394"] = "0.04867940560000000394"
    original_failed_http_success_usage_unknown_count: Literal[8] = 8
    original_failed_no_http_usage_unknown_count: Literal[2] = 2
    original_failed_usage_imputation_count: Literal[0] = 0
    combined_observable_billing_tokens_lower_bound: Literal[1094528] = 1094528
    combined_observable_cost_usd_lower_bound: Literal["0.19806934560000001800"] = (
        "0.19806934560000001800"
    )
    trajectory_accounting_separate_from_billing_lower_bound: Literal[True] = True
    stage_two_provider_call_count: Literal[0] = 0
    status: Literal["transport_recovery_completed"] = "transport_recovery_completed"
    schema_version: Literal["finance_v26_transport_recovery_outcome_audit.v1"] = (
        "finance_v26_transport_recovery_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> TransportRecoveryOutcomeAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_transport_recovery_outcome_audit:",
        ):
            raise ValueError("v26.128 Transport Recovery outcome identity changed")
        return self


class FullEndpointOutcomeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    frozen_historical_model_endpoint_count: Literal[22] = 22
    fresh_recovery_model_endpoint_count: Literal[10] = 10
    exact_model_endpoint_denominator: Literal[32] = 32
    program_closed_count: Literal[32] = 32
    terminal_node_completed_count: Literal[32] = 32
    postterminal_verification_completed_count: Literal[32] = 32
    final_commit_count: Literal[32] = 32
    exact_final_abi_crossed_count: Literal[26] = 26
    exact_final_abi_failed_count: Literal[6] = 6
    independently_valid_count: Literal[19] = 19
    model_invalid_count: Literal[13] = 13
    exact_abi_but_semantically_invalid_count: Literal[7] = 7
    endpoint_valid_fraction: Literal["0.59375"] = "0.59375"
    historical_valid_count: Literal[11] = 11
    historical_invalid_count: Literal[11] = 11
    recovery_valid_count: Literal[8] = 8
    recovery_invalid_count: Literal[2] = 2
    transport_failure_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    completion_unusable_count: Literal[0] = 0
    typed_budget_no_call_count: Literal[0] = 0
    historical_results_reclassified: Literal[False] = False
    exact_denominator_rate_estimable: Literal[True] = True
    engineering_calibration_only: Literal[True] = True
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_full_model_endpoint_outcome_audit.v1"] = (
        "finance_v26_full_model_endpoint_outcome_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FullEndpointOutcomeAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_full_model_endpoint_outcome_audit:",
        ):
            raise ValueError("v26.128 full endpoint identity changed")
        return self


class ModelInvalidLocalizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_model_invalid_count: Literal[2] = 2
    final_exact_key_set_but_answer_scalar_count: Literal[1] = 1
    final_scalar_value: Literal["0.00"] = "0.00"
    action_abi_rescue_consumed_before_final_count: Literal[1] = 1
    final_abi_rescue_available_count: Literal[0] = 0
    completed_answer_valid_but_mechanism_invalid_count: Literal[1] = 1
    completed_invalid_mechanism_id: Literal["failure_recovery"] = "failure_recovery"
    missing_failure_recovery_event_count: Literal[3] = 3
    missing_failure_recovery_events: tuple[str, str, str] = (
        "recovery_succeeded",
        "selector_revised",
        "typed_failure_observed",
    )
    historical_final_grammar_failure_count: Literal[5] = 5
    historical_exact_abi_semantic_failure_count: Literal[6] = 6
    additional_abi_rescue_supported: Literal[False] = False
    final_grammar_change_supported: Literal[False] = False
    semantic_action_or_candidate_change_supported: Literal[False] = False
    model_completion_or_rollout_change_supported: Literal[False] = False
    transport_or_instrument_cause_supported: Literal[False] = False
    outcomes_are_model_results: Literal[True] = True
    schema_version: Literal["finance_v26_recovery_model_invalid_localization.v1"] = (
        "finance_v26_recovery_model_invalid_localization.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ModelInvalidLocalizationAudit:
        if self.missing_failure_recovery_events != tuple(
            sorted(set(self.missing_failure_recovery_events))
        ):
            raise ValueError("v26.128 missing mechanism-event set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_recovery_model_invalid_localization:",
        ):
            raise ValueError("v26.128 invalid localization identity changed")
        return self


class EngineeringKernelFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    transport_recovery_outcome_audit_id: str = Field(min_length=1)
    full_endpoint_outcome_audit_id: str = Field(min_length=1)
    model_invalid_localization_audit_id: str = Field(min_length=1)
    semantic_action_protocol_id: str = recovery.static_stage.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = recovery.static_stage.EXPECTED_ACTION_GRAMMAR_ID
    candidate_space_authority_audit_id: str = recovery.static_stage.EXPECTED_CANDIDATE_AUDIT_ID
    exact_final_response_grammar_id: str = recovery.EXPECTED_FINAL_GRAMMAR_ID
    stage_one_profile_id: str = recovery.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = recovery.EXPECTED_STAGE_TWO_PROFILE_ID
    resource_contract_id: str = recovery.EXPECTED_RESOURCE_ID
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    rollout_upper_bound_tokens: Literal[400000] = 400000
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    stage_two_provider_call_upper_bound: Literal[0] = 0
    privacy_first_capture_required: Literal[True] = True
    exact_transport_failure_replacement_upper_bound: Literal[1] = 1
    transport_replacement_requires_fresh_pre_call_authority: Literal[True] = True
    exact_32_model_endpoint_denominator_complete: Literal[True] = True
    independent_validity_observed_count: Literal[19] = 19
    transport_recovery_completed: Literal[True] = True
    repeated_engineering_sources_role_eligible: Literal[False] = False
    fresh_unexposed_role_population_required: Literal[True] = True
    fresh_role_contract_manifest_job_and_runner_identities_required: Literal[True] = True
    complete_credential_free_role_runner_preflight_required: Literal[True] = True
    role_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    status: Literal["engineering_kernel_qualified_for_fresh_role_preflight"] = (
        "engineering_kernel_qualified_for_fresh_role_preflight"
    )
    schema_version: Literal["finance_v26_engineering_kernel_freeze.v1"] = (
        "finance_v26_engineering_kernel_freeze.v1"
    )

    @model_validator(mode="after")
    def validate_freeze(self) -> EngineeringKernelFreeze:
        if (
            self.semantic_action_protocol_id != recovery.static_stage.EXPECTED_ACTION_PROTOCOL_ID
            or self.semantic_action_response_grammar_id
            != recovery.static_stage.EXPECTED_ACTION_GRAMMAR_ID
            or self.candidate_space_authority_audit_id
            != recovery.static_stage.EXPECTED_CANDIDATE_AUDIT_ID
            or self.exact_final_response_grammar_id != recovery.EXPECTED_FINAL_GRAMMAR_ID
            or self.stage_one_profile_id != recovery.EXPECTED_STAGE_ONE_PROFILE_ID
            or self.stage_two_profile_id != recovery.EXPECTED_STAGE_TWO_PROFILE_ID
            or self.resource_contract_id != recovery.EXPECTED_RESOURCE_ID
        ):
            raise ValueError("v26.128 frozen engineering generation route changed")
        if self.freeze_id != _identity(
            self,
            "freeze_id",
            "finance_v26_engineering_kernel_freeze:",
        ):
            raise ValueError("v26.128 engineering Kernel Freeze identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    mutations: tuple[MutationResult, ...] = Field(min_length=12, max_length=12)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_postrun_destructive.v1"] = (
        "finance_v26_transport_recovery_postrun_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.128 destructive mutation names changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_transport_recovery_postrun_destructive:",
        ):
            raise ValueError("v26.128 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    engineering_kernel_freeze_id: str = Field(min_length=1)
    transport_recovery_outcome_audit_id: str = Field(min_length=1)
    full_endpoint_outcome_audit_id: str = Field(min_length=1)
    model_invalid_localization_audit_id: str = Field(min_length=1)
    status: Literal["engineering_kernel_qualified"] = "engineering_kernel_qualified"
    next_permitted_stage: str = NEXT_STAGE
    provider_calls_authorized: Literal[False] = False
    fresh_unexposed_capability_population_required: Literal[True] = True
    fresh_unexposed_reachability_population_required: Literal[True] = True
    fresh_kernel_bound_role_contract_manifest_jobs_and_runner_required: Literal[True] = True
    credential_free_role_runner_preflight_required: Literal[True] = True
    historical_engineering_source_reuse_authorized: Literal[False] = False
    historical_job_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    threshold_relaxation_or_posthoc_task_deletion_authorized: Literal[False] = False
    semantic_action_candidate_final_grammar_model_or_resource_change_authorized: Literal[False] = (
        False
    )
    capability_or_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_transport_recovery_postrun_transition.v1"] = (
        "finance_v26_transport_recovery_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_transport_recovery_postrun_transition:",
        ):
            raise ValueError("v26.128 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    execution_report_id: str = EXPECTED_EXECUTION_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    raw_lineage_reaudit_id: str = Field(min_length=1)
    transport_recovery_outcome_audit_id: str = Field(min_length=1)
    full_endpoint_outcome_audit_id: str = Field(min_length=1)
    model_invalid_localization_audit_id: str = Field(min_length=1)
    engineering_kernel_freeze_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=8, max_length=8)
    exact_model_endpoint_denominator: Literal[32] = 32
    independently_valid_count: Literal[19] = 19
    model_invalid_count: Literal[13] = 13
    transport_failure_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    status: Literal["engineering_kernel_qualified"] = "engineering_kernel_qualified"
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_transport_recovery_postrun_audit_report.v1"] = (
        "finance_v26_transport_recovery_postrun_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PostrunAuditReport:
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_transport_recovery_postrun_audit_report:",
        ):
            raise ValueError("v26.128 audit report identity changed")
        return self


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=legacy.sha256_file(path),
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
        if candidate.is_file() and legacy.sha256_file(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.128 cannot replay bound file: {relative_path}")


def build_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> AuditSourceReplay:
    predecessor = execution.RecoveryExecutionSourceReplay.model_validate(
        _load(execution_dir / "online_source_replay_audit.json")
    )
    report = execution.RecoveryExecutionReport.model_validate(_load(execution_dir / "report.json"))
    if (
        predecessor.audit_id != EXPECTED_EXECUTION_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or report.source_replay_audit_id != predecessor.audit_id
    ):
        raise ValueError("v26.128 predecessor execution identity changed")
    entries: dict[str, SourceReplayEntry] = {}
    for item in predecessor.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_127_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    execution_files = tuple(sorted(path for path in execution_dir.rglob("*") if path.is_file()))
    if len(execution_files) != 149:
        raise ValueError("v26.128 execution file denominator changed")
    for path in execution_files:
        relative = str(Path(EXECUTION_DIR) / path.relative_to(execution_dir))
        digest = legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_127_execution_file",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    digest = legacy.sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_128_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation_path.stat().st_size,
    )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = AuditSourceReplay.model_construct(audit_id="pending", **values)
    return AuditSourceReplay(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_postrun_source_replay:",
        ),
        **values,
    )


def _checkpoint_rows(path: Path) -> tuple[execution.RecoveryJobResult, ...]:
    return tuple(
        execution.RecoveryJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _independent_rows(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
) -> tuple[
    tuple[IndependentRecoveryRow, ...],
    tuple[recovery.RecoveryRawExecution, ...],
    tuple[execution.RecoveryJobResult, ...],
]:
    prepared = recovery.load_prepared_recovery(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=package_root / execution.PREFLIGHT_DIR,
    )
    formal_results = tuple(
        execution.RecoveryJobResult.model_validate(item)
        for item in _load(execution_dir / "recovery_job_results.json")
    )
    checkpoint = _checkpoint_rows(execution_dir / "recovery_job_results.checkpoint.jsonl")
    if formal_results != checkpoint or len(formal_results) != 10:
        raise ValueError("v26.128 checkpoint and result denominator changed")
    result_by_job = {item.recovery_job_id: item for item in formal_results}
    rows: list[IndependentRecoveryRow] = []
    raws: list[recovery.RecoveryRawExecution] = []
    for job in prepared.recovery_manifest.jobs:
        formal = result_by_job[job.recovery_job_id]
        raw_path = recovery.recovery_raw_path(execution_dir, job)
        raw = recovery.RecoveryRawExecution.model_validate(_load(raw_path))
        if formal.raw_execution_artifact != _descriptor(raw_path, execution_dir):
            raise ValueError("v26.128 formal Raw descriptor changed")
        prefix = recovery.replay_successful_prefix(
            recovery_job=job,
            static=prepared.static,
            historical_runner_contract=prepared.historical_runner_contract,
            historical_execution_dir=package_root / recovery.HISTORICAL_EXECUTION_DIR,
        )
        if prefix.replay != raw.prefix_replay:
            raise ValueError("v26.128 historical prefix replay changed")
        pairs = recovery._load_recovery_pairs(raw, execution_dir)
        if not pairs:
            raise ValueError("v26.128 RecoveryJob lacks its exact replacement")
        replacement = pairs[0][0]
        if (
            not replacement.invocation_certificate.exact_failed_call_replacement
            or replacement.prompt_sha256 != job.exact_failed_request_prompt_sha256
            or replacement.historical_dynamic_certificate.certificate_id
            != job.exact_failed_dynamic_certificate_id
            or replacement.request_binding_certificate.certificate_id
            != job.exact_failed_request_binding_certificate_id
            or replacement.resource_certificate_id != job.exact_failed_resource_certificate_id
            or not replacement.provider_telemetry.http_success
        ):
            raise ValueError("v26.128 exact replacement binding changed")
        binding = recovery.historical_runner.privacy_first_runtime_binding(
            prepared.static, job.historical_job
        )
        replay = legacy.replay_v3(
            cast(Any, raw),
            static=prepared.static.predecessor.historical,
            binding=binding,
        )
        mechanism = evaluate_mechanism_estimand(
            cast(Any, binding.record),
            raw.observations,
            stopped_by_model=raw.completed_result is not None,
        )
        verification: AuthorityPreservingVerificationReport | None = None
        if raw.completed_result is not None:
            verification, mechanism = recovery._completed_verification(
                raw=cast(Any, raw),
                replay=replay,
                binding=binding,
            )
        combined_telemetry = (
            *raw.historical_prefix_provider_telemetry,
            *raw.successor_provider_telemetry,
        )
        exact_model, fallback, native, thinking, usage = execution.semantic_online._telemetry_flags(
            combined_telemetry
        )
        completed_nodes, node_count, program_closed, terminal_completed, verified = (
            execution.semantic_online._progress_diagnostic(binding.record, raw.observations)
        )
        final_commits = sum(item.commit.action == "emit_final" for item in raw.commits)
        final_abi = any(
            item.exact_two_field_final_payload
            for item in raw.attempts
            if item.request_kind == "final_answer"
        )
        valid = bool(verification is not None and verification.valid)
        terminal: Literal["model_valid_trajectory", "model_invalid_trajectory"] = (
            "model_valid_trajectory" if valid else "model_invalid_trajectory"
        )
        privacy_pairing = (
            len(pairs)
            == len(raw.successor_provider_envelope_artifacts)
            == len(raw.successor_payload_projection_artifacts)
            == raw.successor_provider_call_count
        )
        if (
            not replay.passed
            or not exact_model
            or not fallback
            or not native
            or not thinking
            or not usage
            or not privacy_pairing
            or raw.original_failed_call_usage_imputed
            or raw.stage_two_provider_call_count
            or not program_closed
            or not terminal_completed
            or not verified
            or final_commits != 1
            or completed_nodes != node_count
        ):
            raise ValueError("v26.128 independent Recovery admission failed")
        if (
            formal.terminal_category != terminal
            or formal.successful_prefix_provider_call_count
            != raw.historical_successful_prefix_provider_call_count
            or formal.successor_provider_call_count != raw.successor_provider_call_count
            or formal.successor_total_tokens
            != sum(item.total_tokens or 0 for item in raw.successor_provider_telemetry)
            or formal.program_closed != program_closed
            or formal.terminal_node_completed != terminal_completed
            or formal.postterminal_verification_completed != verified
            or formal.final_commit_count != final_commits
            or formal.final_abi_crossed != final_abi
            or formal.final_answer_emitted != (raw.completed_result is not None)
            or formal.independent_validity != valid
            or formal.mechanism_success != mechanism.success
            or formal.replay_v3_passed != replay.passed
        ):
            raise ValueError("v26.128 independent Recovery result differs from formal result")
        rows.append(
            IndependentRecoveryRow(
                recovery_job_id=job.recovery_job_id,
                historical_job_id=job.historical_job.job_id,
                raw_execution_id=raw.artifact_id,
                formal_result_id=formal.result_id,
                successful_prefix_call_count=(raw.historical_successful_prefix_provider_call_count),
                successor_call_count=raw.successor_provider_call_count,
                replacement_http_success=True,
                successor_total_tokens=formal.successor_total_tokens,
                program_closed=True,
                terminal_node_completed=True,
                postterminal_verification_completed=True,
                final_commit_count=1,
                final_abi_crossed=final_abi,
                answer_emitted=raw.completed_result is not None,
                independent_validity=valid,
                mechanism_success=mechanism.success,
                terminal_category=terminal,
                replay_v3_passed=True,
                exact_model_passed=True,
                thinking_continuity_passed=True,
                provider_usage_complete=True,
                privacy_pairing_passed=True,
            )
        )
        raws.append(raw)
    return tuple(rows), tuple(raws), formal_results


def _build_raw_reaudit(
    *,
    rows: Sequence[IndependentRecoveryRow],
    raws: Sequence[recovery.RecoveryRawExecution],
    formal_results: Sequence[execution.RecoveryJobResult],
    execution_dir: Path,
) -> RawLineageReaudit:
    formal = execution.RecoveryRawLineageAudit.model_validate(
        _load(execution_dir / "raw_lineage_audit.json")
    )
    if formal.audit_id != EXPECTED_RAW_LINEAGE_ID:
        raise ValueError("v26.128 predecessor Raw Lineage identity changed")
    envelopes: list[str] = []
    projections: list[str] = []
    private_count = 0
    invalid_content_count = 0
    invalid_key_count = 0
    imputation_count = 0
    for raw in raws:
        pairs = recovery._load_recovery_pairs(raw, execution_dir)
        for envelope, projection in pairs:
            envelopes.append(envelope.envelope_id)
            projections.append(projection.projection_id)
            private_count += int(
                envelope.private_reasoning_content_persisted
                or envelope.private_reasoning_content_hashed
                or projection.private_reasoning_content_persisted
            )
            invalid_content_count += int(
                envelope.payload_content_persisted or projection.invalid_payload_content_persisted
            )
            invalid_key_count += int(projection.invalid_payload_key_persisted)
        imputation_count += int(raw.original_failed_call_usage_imputed)
    checkpoint = _checkpoint_rows(execution_dir / "recovery_job_results.checkpoint.jsonl")
    if tuple(formal_results) != checkpoint:
        raise ValueError("v26.128 checkpoint results changed")
    if (
        formal.successor_provider_call_count != len(envelopes)
        or formal.successor_envelope_count != len(envelopes)
        or formal.successor_projection_count != len(projections)
        or formal.unique_envelope_id_count != len(set(envelopes))
        or formal.unique_projection_id_count != len(set(projections))
        or formal.private_reasoning_payload_count != private_count
        or formal.invalid_payload_content_persistence_count != invalid_content_count
        or formal.invalid_payload_key_persistence_count != invalid_key_count
        or formal.original_failed_call_usage_imputation_count != imputation_count
    ):
        raise ValueError("v26.128 independent Raw Lineage differs from formal audit")
    values = {
        "rows": tuple(rows),
        "unique_envelope_id_count": len(set(envelopes)),
        "unique_projection_id_count": len(set(projections)),
        "private_reasoning_payload_count": private_count,
        "invalid_payload_content_persistence_count": invalid_content_count,
        "invalid_payload_key_persistence_count": invalid_key_count,
        "original_failed_usage_imputation_count": imputation_count,
    }
    provisional = RawLineageReaudit.model_construct(audit_id="pending", **values)
    return RawLineageReaudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_raw_lineage_reaudit:",
        ),
        **values,
    )


def _build_transport_outcome(
    *,
    rows: Sequence[IndependentRecoveryRow],
    raws: Sequence[recovery.RecoveryRawExecution],
    formal_results: Sequence[execution.RecoveryJobResult],
    execution_dir: Path,
) -> TransportRecoveryOutcomeAudit:
    report = execution.RecoveryExecutionReport.model_validate(_load(execution_dir / "report.json"))
    successor = tuple(item for raw in raws for item in raw.successor_provider_telemetry)
    replacements = tuple(recovery._load_recovery_pairs(raw, execution_dir)[0][0] for raw in raws)
    cost = sum(
        (Decimal(item.successor_estimated_cost_usd) for item in formal_results),
        Decimal("0"),
    )
    if (
        report.report_id != EXPECTED_EXECUTION_REPORT_ID
        or len(rows) != 10
        or len(replacements) != 10
        or not all(item.provider_telemetry.http_success for item in replacements)
        or len(successor) != 65
        or not all(item.http_success for item in successor)
        or sum(item.prompt_tokens or 0 for item in successor) != 206081
        or sum(item.completion_tokens or 0 for item in successor) != 85491
        or sum(item.reasoning_tokens or 0 for item in successor) != 77657
        or sum(item.total_tokens or 0 for item in successor) != 291572
        or format(cost, "f") != "0.04867940560000000394"
        or sum(item.successful_prefix_call_count for item in rows) != 6
        or any(
            item.terminal_category not in {"model_valid_trajectory", "model_invalid_trajectory"}
            for item in rows
        )
        or report.original_failed_call_usage_imputation_count
    ):
        raise ValueError("v26.128 Transport Recovery outcome reconstruction changed")
    values: dict[str, Any] = {}
    provisional = TransportRecoveryOutcomeAudit.model_construct(audit_id="pending", **values)
    return TransportRecoveryOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_outcome_audit:",
        ),
        **values,
    )


def _build_endpoint_outcome(
    *,
    rows: Sequence[IndependentRecoveryRow],
    package_root: Path,
) -> FullEndpointOutcomeAudit:
    historical = recovery.historical_audit.FinalOutcomeAudit.model_validate(
        _load(package_root / recovery.HISTORICAL_AUDIT_DIR / "final_outcome_audit.json")
    )
    valid = sum(item.independent_validity for item in rows)
    invalid = len(rows) - valid
    final_abi = sum(item.final_abi_crossed for item in rows)
    if (
        historical.complete_model_outcome_job_count != 22
        or historical.program_closed_model_outcome_count != 22
        or historical.terminal_node_completed_model_outcome_count != 22
        or historical.terminal_verification_completed_model_outcome_count != 22
        or historical.final_commit_model_outcome_count != 22
        or historical.final_answer_emitted_count != 17
        or historical.independently_valid_answer_count != 11
        or len(rows) != 10
        or not all(item.program_closed for item in rows)
        or not all(item.terminal_node_completed for item in rows)
        or not all(item.postterminal_verification_completed for item in rows)
        or valid != 8
        or invalid != 2
        or final_abi != 9
    ):
        raise ValueError("v26.128 full endpoint denominator changed")
    values: dict[str, Any] = {}
    provisional = FullEndpointOutcomeAudit.model_construct(audit_id="pending", **values)
    return FullEndpointOutcomeAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_full_model_endpoint_outcome_audit:",
        ),
        **values,
    )


def _build_invalid_localization(
    *,
    rows: Sequence[IndependentRecoveryRow],
    raws: Sequence[recovery.RecoveryRawExecution],
    execution_dir: Path,
) -> ModelInvalidLocalizationAudit:
    invalid = tuple(item for item in rows if not item.independent_validity)
    if len(invalid) != 2:
        raise ValueError("v26.128 successor invalid denominator changed")
    by_id = {raw.recovery_job.recovery_job_id: raw for raw in raws}
    final_invalid = next(item for item in invalid if not item.final_abi_crossed)
    mechanism_invalid = next(item for item in invalid if item.final_abi_crossed)
    final_raw = by_id[final_invalid.recovery_job_id]
    mechanism_raw = by_id[mechanism_invalid.recovery_job_id]
    final_pairs = recovery._load_recovery_pairs(final_raw, execution_dir)
    final_projection = next(
        projection
        for envelope, projection in final_pairs
        if envelope.request_kind == "final_answer"
    )
    payload = final_projection.response_payload
    action_rescues = tuple(
        item
        for item in final_raw.attempts
        if item.request_kind == "semantic_proposal" and item.public_attempt_phase == "abi_rescue"
    )
    binding = recovery.historical_runner.privacy_first_runtime_binding(
        recovery.static_stage.load_final_grammar_static_inputs(
            execution_dir.parents[2], execution_dir.parents[2]
        ),
        mechanism_raw.job,
    )
    mechanism = evaluate_mechanism_estimand(
        cast(Any, binding.record),
        mechanism_raw.observations,
        stopped_by_model=True,
    )
    if (
        payload is None
        or set(payload) != {"answer", "rationale_summary"}
        or payload["answer"] != "0.00"
        or len(action_rescues) != 1
        or any(
            item.request_kind == "final_answer" and item.public_attempt_phase == "abi_rescue"
            for item in final_raw.attempts
        )
        or mechanism.success
        or mechanism.mechanism_id != "failure_recovery"
        or tuple(mechanism.missing_event_ids)
        != ("recovery_succeeded", "selector_revised", "typed_failure_observed")
        or mechanism_raw.completed_result is None
    ):
        raise ValueError("v26.128 model-invalid localization changed")
    values: dict[str, Any] = {}
    provisional = ModelInvalidLocalizationAudit.model_construct(audit_id="pending", **values)
    return ModelInvalidLocalizationAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_recovery_model_invalid_localization:",
        ),
        **values,
    )


def _make_kernel_freeze(
    transport: TransportRecoveryOutcomeAudit,
    endpoint: FullEndpointOutcomeAudit,
    invalid: ModelInvalidLocalizationAudit,
) -> EngineeringKernelFreeze:
    values = {
        "transport_recovery_outcome_audit_id": transport.audit_id,
        "full_endpoint_outcome_audit_id": endpoint.audit_id,
        "model_invalid_localization_audit_id": invalid.audit_id,
    }
    provisional = EngineeringKernelFreeze.model_construct(freeze_id="pending", **values)
    return EngineeringKernelFreeze(
        freeze_id=_identity(
            provisional,
            "freeze_id",
            "finance_v26_engineering_kernel_freeze:",
        ),
        **values,
    )


def _reidentify(
    payload: dict[str, Any],
    *,
    identity_field: str,
    prefix: str,
) -> dict[str, Any]:
    return {
        **payload,
        identity_field: canonical_hash(
            {key: value for key, value in payload.items() if key != identity_field},
            prefix=prefix,
        ),
    }


def _expect_rejected(
    model_type: type[BaseModel],
    payload: dict[str, Any],
    name: str,
) -> MutationResult:
    try:
        model_type.model_validate(payload)
    except (TypeError, ValueError):
        return MutationResult(name=name)
    raise ValueError(f"v26.128 destructive mutation was accepted: {name}")


def _build_destructive(
    transport: TransportRecoveryOutcomeAudit,
    endpoint: FullEndpointOutcomeAudit,
    invalid: ModelInvalidLocalizationAudit,
    kernel: EngineeringKernelFreeze,
) -> DestructiveAudit:
    mutations: list[MutationResult] = []
    payload = transport.model_dump(mode="json")
    payload["exact_failed_call_replacement_count"] = 9
    mutations.append(
        _expect_rejected(
            TransportRecoveryOutcomeAudit,
            payload,
            "replacement_denominator_reduced",
        )
    )
    payload = transport.model_dump(mode="json")
    payload["original_failed_usage_imputation_count"] = 1
    mutations.append(
        _expect_rejected(
            TransportRecoveryOutcomeAudit,
            payload,
            "unknown_original_usage_imputed",
        )
    )
    payload = transport.model_dump(mode="json")
    payload["successor_transport_failure_count"] = 1
    mutations.append(
        _expect_rejected(
            TransportRecoveryOutcomeAudit,
            payload,
            "transport_failure_inserted",
        )
    )
    payload = endpoint.model_dump(mode="json")
    payload["exact_model_endpoint_denominator"] = 31
    mutations.append(
        _expect_rejected(
            FullEndpointOutcomeAudit,
            payload,
            "endpoint_denominator_reduced",
        )
    )
    payload = endpoint.model_dump(mode="json")
    payload["independently_valid_count"] = 20
    mutations.append(
        _expect_rejected(
            FullEndpointOutcomeAudit,
            payload,
            "model_invalid_row_reclassified",
        )
    )
    payload = endpoint.model_dump(mode="json")
    payload["historical_results_reclassified"] = True
    mutations.append(
        _expect_rejected(
            FullEndpointOutcomeAudit,
            payload,
            "historical_results_reclassified",
        )
    )
    payload = invalid.model_dump(mode="json")
    payload["additional_abi_rescue_supported"] = True
    mutations.append(
        _expect_rejected(
            ModelInvalidLocalizationAudit,
            payload,
            "additional_abi_rescue_authorized",
        )
    )
    payload = invalid.model_dump(mode="json")
    payload["outcomes_are_model_results"] = False
    mutations.append(
        _expect_rejected(
            ModelInvalidLocalizationAudit,
            payload,
            "model_result_reclassified_as_instrument",
        )
    )
    payload = kernel.model_dump(mode="json")
    payload["stage_one_profile_id"] = "finance_v26_stage_one_thinking_profile:" + "f" * 64
    mutations.append(
        _expect_rejected(
            EngineeringKernelFreeze,
            _reidentify(
                payload,
                identity_field="freeze_id",
                prefix="finance_v26_engineering_kernel_freeze:",
            ),
            "model_profile_changed",
        )
    )
    payload = kernel.model_dump(mode="json")
    payload["maximum_abi_rescue_calls"] = 2
    mutations.append(
        _expect_rejected(
            EngineeringKernelFreeze,
            payload,
            "abi_rescue_bound_changed",
        )
    )
    payload = kernel.model_dump(mode="json")
    payload["role_execution_authorized"] = True
    mutations.append(
        _expect_rejected(
            EngineeringKernelFreeze,
            payload,
            "role_execution_bypassed_preflight",
        )
    )
    payload = kernel.model_dump(mode="json")
    payload["repeated_engineering_sources_role_eligible"] = True
    mutations.append(
        _expect_rejected(
            EngineeringKernelFreeze,
            payload,
            "engineering_sources_reused_for_roles",
        )
    )
    ordered = tuple(sorted(mutations, key=lambda item: item.name))
    values = {"mutations": ordered}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_postrun_destructive:",
        ),
        **values,
    )


def build_audit(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    output_dir: Path,
) -> PostrunAuditReport:
    source = build_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    rows, raws, formal_results = _independent_rows(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
    )
    raw = _build_raw_reaudit(
        rows=rows,
        raws=raws,
        formal_results=formal_results,
        execution_dir=execution_dir,
    )
    transport = _build_transport_outcome(
        rows=rows,
        raws=raws,
        formal_results=formal_results,
        execution_dir=execution_dir,
    )
    endpoint = _build_endpoint_outcome(rows=rows, package_root=package_root)
    invalid = _build_invalid_localization(
        rows=rows,
        raws=raws,
        execution_dir=execution_dir,
    )
    kernel = _make_kernel_freeze(transport, endpoint, invalid)
    destructive = _build_destructive(transport, endpoint, invalid, kernel)
    transition_values = {
        "engineering_kernel_freeze_id": kernel.freeze_id,
        "transport_recovery_outcome_audit_id": transport.audit_id,
        "full_endpoint_outcome_audit_id": endpoint.audit_id,
        "model_invalid_localization_audit_id": invalid.audit_id,
    }
    provisional_transition = ProspectiveTransitionContract.model_construct(
        contract_id="pending", **transition_values
    )
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            provisional_transition,
            "contract_id",
            "finance_v26_transport_recovery_postrun_transition:",
        ),
        **transition_values,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("source_replay_audit.json", source),
        ("raw_lineage_reaudit.json", raw),
        ("transport_recovery_outcome_audit.json", transport),
        ("full_endpoint_outcome_audit.json", endpoint),
        ("model_invalid_localization_audit.json", invalid),
        ("engineering_kernel_freeze.json", kernel),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        recovery._write_json_atomic(output_dir / name, value.model_dump(mode="json"))
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "raw_lineage_reaudit_id": raw.audit_id,
        "transport_recovery_outcome_audit_id": transport.audit_id,
        "full_endpoint_outcome_audit_id": endpoint.audit_id,
        "model_invalid_localization_audit_id": invalid.audit_id,
        "engineering_kernel_freeze_id": kernel.freeze_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional_report = PostrunAuditReport.model_construct(report_id="pending", **report_values)
    report = PostrunAuditReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_transport_recovery_postrun_audit_report:",
        ),
        **report_values,
    )
    recovery._write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.128 Transport Recovery postrun audit"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--execution-dir", type=Path, default=package_default / EXECUTION_DIR)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_audit(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
