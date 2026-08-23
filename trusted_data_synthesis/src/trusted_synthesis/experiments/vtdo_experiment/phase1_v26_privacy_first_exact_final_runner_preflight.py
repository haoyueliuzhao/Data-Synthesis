from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as static_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_runner_preflight as predecessor_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    _completed_verification,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    exact_final_response_payload,
    make_final_response_host_envelope,
)

RUN_ID: Final = "finance_v26_123_privacy_first_exact_final_runner_preflight_v1_20260823"
NEXT_STAGE: Final = "exact_final_semantic_action_calibration_execution_only"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_123_privacy_first_exact_final_runner_preflight_v1_20260823"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_first_exact_final_execution.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_first_exact_final_runner_preflight.py",
)
EXPECTED_V26_122_REPORT_ID: Final = (
    "finance_v26_final_grammar_rematerialization_report:"
    "d33708c242c6b6779c1f3e3c3911f4235abad570363478ab79e82617a37a971c"
)
EXPECTED_V26_122_SOURCE_REPLAY_ID: Final = (
    "finance_v26_final_grammar_source_replay:"
    "18c18cc23dc1b77e2c352fb06d649cb642eb4d2c6936a426f24b93941fc9320f"
)
EXPECTED_V26_122_CONTRACT_ID: Final = (
    "finance_v26_final_grammar_execution_contract:"
    "5532a1f1ca600979f7541770606e7ce0a3b65c4a93f88a659e52e14ff7d6e27e"
)
EXPECTED_V26_122_MANIFEST_ID: Final = (
    "finance_v26_final_grammar_manifest:"
    "fd4d78efa9374fc3de91ccca1a8242b7a6bee4bdcf4052ac8bbf6428bd95a5ee"
)
EXPECTED_V26_122_RESOURCE_ID: Final = (
    "finance_v26_final_grammar_resource_contract:"
    "381e18dff5a538c50cc06aaae9c6c81d110d8214b8c7d3800820d4eb3f09e43c"
)
EXPECTED_FINAL_GRAMMAR_ID: Final = (
    "prospective_exact_final_response_grammar:"
    "5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403"
)
V26_122_OUTPUTS: Final = (
    "cross_artifact_binding_audit.json",
    "destructive_audit.json",
    "exact_final_response_grammar.json",
    "final_grammar_constructibility_audit.json",
    "final_grammar_execution_contract.json",
    "final_grammar_job_manifest.json",
    "final_grammar_path_audits.json",
    "final_grammar_resource_contract.json",
    "final_grammar_task_packages.json",
    "prospective_transition_contract.json",
    "report.json",
    "semantic_action_preservation_audit.json",
    "source_replay_audit.json",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_122_transitive_source",
        "v26_122_output",
        "v26_123_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RunnerSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_V26_122_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_V26_122_SOURCE_REPLAY_ID
    predecessor_transitive_file_count: Literal[2534] = 2534
    predecessor_output_file_count: Literal[13] = 13
    implementation_file_count: Literal[2] = 2
    replayed_file_count: Literal[2549] = 2549
    replay_pass_count: Literal[2549] = 2549
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2549, max_length=2549)
    replay_before_profile_credential_or_client: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_runner_source_replay.v1"] = (
        "finance_v26_privacy_first_runner_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))) or len(paths) != 2549:
            raise ValueError("v26.123 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.123 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_runner_source_replay:"
        ):
            raise ValueError("v26.123 source replay identity changed")
        return self


class RunnerBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    static_contract_id: str = EXPECTED_V26_122_CONTRACT_ID
    manifest_id: str = EXPECTED_V26_122_MANIFEST_ID
    resource_contract_id: str = EXPECTED_V26_122_RESOURCE_ID
    exact_final_response_grammar_id: str = EXPECTED_FINAL_GRAMMAR_ID
    semantic_action_protocol_id: str = static_stage.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = static_stage.EXPECTED_ACTION_GRAMMAR_ID
    exact_job_count: Literal[32] = 32
    task_binding_pass_count: Literal[24] = 24
    path_binding_pass_count: Literal[48] = 48
    job_binding_pass_count: Literal[32] = 32
    final_host_envelope_bound_before_provider: Literal[True] = True
    exact_model_bound: Literal[True] = True
    thinking_enabled_bound: Literal[True] = True
    completion_16k_bound: Literal[True] = True
    rollout_400k_bound: Literal[True] = True
    one_abi_and_one_semantic_recovery_bound: Literal[True] = True
    stage_two_provider_call_bound: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_runner_binding.v1"] = (
        "finance_v26_privacy_first_runner_binding.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerBindingAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_runner_binding:"
        ):
            raise ValueError("v26.123 Runner binding identity changed")
        return self


class RunnerFixtureRow(FrozenModel):
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    provider_call_count: int = Field(gt=0)
    semantic_choice_count: int = Field(gt=0)
    stage_two_commit_count: int = Field(gt=0)
    observation_count: int = Field(gt=0)
    final_payload_count: Literal[1] = 1
    independent_validity_passed: Literal[True] = True
    mechanism_success_passed: Literal[True] = True


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerFixtureRow, ...] = Field(min_length=32, max_length=32)
    job_count: Literal[32] = 32
    scripted_stage_one_call_count: Literal[256] = 256
    exact_action_payload_count: Literal[224] = 224
    exact_final_payload_count: Literal[32] = 32
    semantic_choice_count: Literal[224] = 224
    reversible_stage_two_commit_count: Literal[224] = 224
    observation_count: Literal[192] = 192
    program_closure_count: Literal[32] = 32
    terminal_verification_count: Literal[32] = 32
    independent_validity_pass_count: Literal[32] = 32
    mechanism_success_pass_count: Literal[32] = 32
    privacy_first_envelope_count: Literal[256] = 256
    public_payload_projection_count: Literal[256] = 256
    envelope_projection_parent_match_count: Literal[256] = 256
    envelope_before_projection_pass_count: Literal[256] = 256
    stage_two_provider_calls: Literal[0] = 0
    fixture_aggregate_sha256: str = Field(min_length=64, max_length=64)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_runner_fixture.v1"] = (
        "finance_v26_privacy_first_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if len({item.job_id for item in self.rows}) != 32:
            raise ValueError("v26.123 fixture Job denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_runner_fixture:"
        ):
            raise ValueError("v26.123 fixture identity changed")
        return self


class FinalInterfaceControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    primary_failure_count: Literal[1] = 1
    final_rescue_attempt_count: Literal[1] = 1
    final_rescue_json_lexical_cue_count: Literal[1] = 1
    primary_rescue_host_envelope_match_count: Literal[1] = 1
    final_rescue_exact_payload_count: Literal[1] = 1
    completed_after_final_rescue_count: Literal[1] = 1
    final_rescue_independent_validity_pass_count: Literal[1] = 1
    wrong_answer_exact_schema_admission_count: Literal[1] = 1
    wrong_answer_independent_validity_failure_count: Literal[1] = 1
    host_answer_or_rationale_insertion_count: Literal[0] = 0
    model_generated_stage_protocol_or_parent_count: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exact_final_interface_control.v1"] = (
        "finance_v26_exact_final_interface_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FinalInterfaceControlAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_exact_final_interface_control:"
        ):
            raise ValueError("v26.123 Final interface control identity changed")
        return self


class PrivacyFirstCaptureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    injected_http_success_call_count: Literal[1] = 1
    privacy_redacted_envelope_count: Literal[1] = 1
    privacy_rejected_projection_count: Literal[1] = 1
    complete_raw_execution_count: Literal[1] = 1
    model_result_terminal_count: Literal[1] = 1
    response_model_retained_count: Literal[1] = 1
    usage_retained_count: Literal[1] = 1
    finish_reason_retained_count: Literal[1] = 1
    public_content_hash_length_retained_count: Literal[1] = 1
    rejected_payload_content_persisted_count: Literal[0] = 0
    rejected_payload_key_persisted_count: Literal[0] = 0
    private_reasoning_content_or_hash_persisted_count: Literal[0] = 0
    payload_failure_deleted_call_count: Literal[0] = 0
    complete_raw_zero_call_recovery_count: Literal[1] = 1
    orphan_artifact_rejection_count: Literal[1] = 1
    stage_two_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_capture_control.v1"] = (
        "finance_v26_privacy_first_capture_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrivacyFirstCaptureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_capture_control:"
        ):
            raise ValueError("v26.123 privacy-first control identity changed")
        return self


class SemanticRecoveryControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    abi_rescue_count: Literal[1] = 1
    semantic_recovery_count: Literal[1] = 1
    first_choice_rejection_retained_count: Literal[1] = 1
    changed_action_after_rejection_count: Literal[1] = 1
    recovery_commit_count: Literal[1] = 1
    completed_after_combined_recovery_count: Literal[1] = 1
    both_counters_one_before_semantic_recovery_count: Literal[1] = 1
    correct_action_or_patch_exposed_count: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_semantic_recovery_control.v1"] = (
        "finance_v26_privacy_first_semantic_recovery_control.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticRecoveryControlAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_semantic_recovery_control:"
        ):
            raise ValueError("v26.123 Semantic Recovery control identity changed")
        return self


class CertificateUsageRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    completion_16384_admitted: Literal[True] = True
    completion_16385_admitted_and_charged: Literal[True] = True
    completion_16386_instrument_failure: Literal[True] = True
    calls_blocked_after_instrument_failure: Literal[True] = True
    oversized_prompt_rejected_before_provider: Literal[True] = True
    reused_preparation_rejected: Literal[True] = True
    insufficient_remaining_budget_rejected_before_provider: Literal[True] = True
    complete_raw_recovery_byte_identical: Literal[True] = True
    exact_model_usage_thinking_parent_pass_count: Literal[256] = 256
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_certificate_usage_recovery.v1"] = (
        "finance_v26_privacy_first_certificate_usage_recovery.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CertificateUsageRecoveryAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_first_certificate_usage_recovery:",
        ):
            raise ValueError("v26.123 certificate/Usage/recovery identity changed")
        return self


class OutcomeMeasurementContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    exact_manifest_id: str = EXPECTED_V26_122_MANIFEST_ID
    exact_job_denominator: Literal[32] = 32
    exact_action_abi_retained: Literal[True] = True
    visible_action_and_first_choice_acceptance_separate: Literal[True] = True
    legal_no_progress_and_semantic_rejection_separate: Literal[True] = True
    first_choice_and_eventual_recovery_separate: Literal[True] = True
    program_closure_and_terminal_verification_separate: Literal[True] = True
    exact_final_abi_and_answer_semantics_separate: Literal[True] = True
    grammar_valid_wrong_answer_remains_model_outcome: Literal[True] = True
    privacy_rejection_retains_call_and_resource_denominator: Literal[True] = True
    instrument_and_model_outcome_separate: Literal[True] = True
    independent_validity_required: Literal[True] = True
    historical_v26_120_rows_reclassified: Literal[False] = False
    same_distribution_as_v26_120_or_v26_114_claimed: Literal[False] = False
    schema_version: Literal["finance_v26_exact_final_outcome_measurement.v1"] = (
        "finance_v26_exact_final_outcome_measurement.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> OutcomeMeasurementContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_exact_final_outcome_measurement:"
        ):
            raise ValueError("v26.123 outcome measurement identity changed")
        return self


class MutationResult(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0
    stage_two_provider_calls_before_rejection: Literal[0] = 0


class DestructiveRunnerAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_count: Literal[20] = 20
    rejection_count: Literal[20] = 20
    mutations: tuple[MutationResult, ...] = Field(min_length=20, max_length=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_first_runner_destructive.v1"] = (
        "finance_v26_privacy_first_runner_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveRunnerAudit:
        names = tuple(item.name for item in self.mutations)
        if names != tuple(sorted(set(names))) or len(names) != 20:
            raise ValueError("v26.123 destructive controls changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_first_runner_destructive:"
        ):
            raise ValueError("v26.123 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_measurement_contract_id: str = Field(min_length=1)
    exact_manifest_id: str = EXPECTED_V26_122_MANIFEST_ID
    status: Literal["passed_exact_runner_preflight"] = "passed_exact_runner_preflight"
    next_permitted_stage: str = NEXT_STAGE
    provider_calls_authorized: Literal[True] = True
    only_exact_fresh_32_job_manifest_authorized: Literal[True] = True
    semantic_action_candidate_model_completion_rollout_or_recovery_change_authorized: Literal[
        False
    ] = False
    historical_v26_120_rerun_recovery_continuation_or_reclassification_authorized: Literal[
        False
    ] = False
    host_semantic_choice_answer_or_repair_authorized: Literal[False] = False
    role_state_training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_first_runner_transition.v1"] = (
        "finance_v26_privacy_first_runner_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_first_runner_transition:"
        ):
            raise ValueError("v26.123 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PrivacyFirstRunnerPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_binding_audit_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    final_interface_control_audit_id: str = Field(min_length=1)
    privacy_first_capture_audit_id: str = Field(min_length=1)
    semantic_recovery_control_audit_id: str = Field(min_length=1)
    certificate_usage_recovery_audit_id: str = Field(min_length=1)
    outcome_measurement_contract_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=11, max_length=11)
    exact_job_count: Literal[32] = 32
    scripted_provider_call_count: Literal[256] = 256
    privacy_first_envelope_count: Literal[256] = 256
    public_payload_projection_count: Literal[256] = 256
    independent_validity_pass_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    execution_authorized: Literal[True] = True
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["passed_exact_runner_preflight"] = "passed_exact_runner_preflight"
    schema_version: Literal["finance_v26_privacy_first_runner_preflight_report.v1"] = (
        "finance_v26_privacy_first_runner_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PrivacyFirstRunnerPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_privacy_first_runner_preflight_report:"
        ):
            raise ValueError("v26.123 report identity changed")
        return self


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and legacy.sha256_file(path) == expected_sha256:
            return path
    raise ValueError(f"v26.123 cannot replay bound file: {relative_path}")


def _build_source_replay(
    package_root: Path,
    implementation_root: Path,
) -> RunnerSourceReplayAudit:
    root = implementation_root / static_stage.OUTPUT_DIR
    predecessor_source = static_stage.SourceReplayAudit.model_validate(
        _load(root / "source_replay_audit.json")
    )
    report = static_stage.FinalGrammarRematerializationReport.model_validate(
        _load(root / "report.json")
    )
    if (
        predecessor_source.audit_id != EXPECTED_V26_122_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_V26_122_REPORT_ID
        or report.execution_contract_id != EXPECTED_V26_122_CONTRACT_ID
        or report.manifest_id != EXPECTED_V26_122_MANIFEST_ID
        or report.resource_contract_id != EXPECTED_V26_122_RESOURCE_ID
        or report.exact_final_response_grammar_id != EXPECTED_FINAL_GRAMMAR_ID
        or report.next_permitted_stage != static_stage.NEXT_STAGE
        or report.execution_authorized
    ):
        raise ValueError("v26.123 predecessor identity or transition changed")
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
            source_kind="v26_122_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    for name in V26_122_OUTPUTS:
        path = root / name
        relative = str(Path(static_stage.OUTPUT_DIR) / name)
        expected = details[name].sha256 if name in details else legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_122_output",
            expected_sha256=expected,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    for relative in IMPLEMENTATION_PATHS:
        path = implementation_root / relative
        digest = legacy.sha256_file(path)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_123_implementation",
            expected_sha256=digest,
            observed_sha256=digest,
            byte_count=path.stat().st_size,
        )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = RunnerSourceReplayAudit.model_construct(audit_id="pending", **values)
    return RunnerSourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_first_runner_source_replay:",
        ),
        **values,
    )


class ScriptedPrivacyFirstClient(predecessor_preflight.ScriptedSemanticActionClient):
    def __init__(
        self,
        config: legacy.AgentModelConfig,
        *,
        final_answer: Mapping[str, Any] | None = None,
        completion_tokens: int = 64,
        combined_recovery_control: bool = False,
        final_primary_failure_once: bool = False,
        wrong_final_answer: bool = False,
        privacy_failure_first_call: bool = False,
    ) -> None:
        super().__init__(
            config,
            final_answer=final_answer,
            completion_tokens=completion_tokens,
            combined_recovery_control=combined_recovery_control,
        )
        self._final_primary_failure_once = final_primary_failure_once
        self._final_primary_failure_used = False
        self._wrong_final_answer = wrong_final_answer
        self._privacy_failure_first_call = privacy_failure_first_call
        self._privacy_failure_used = False
        self.prompts: list[tuple[str, str, str]] = []

    def complete_json_certified(
        self,
        prompt: str,
        certificate: legacy.StageOneRequestBindingCertificate,
    ) -> tuple[dict[str, Any], legacy.ModelCallTelemetry]:
        payload, telemetry = super().complete_json_certified(prompt, certificate)
        self.prompts.append((certificate.request_kind, certificate.phase, prompt))
        if self._privacy_failure_first_call and not self._privacy_failure_used:
            self._privacy_failure_used = True
            payload = {
                "reasoning_trace": "fixture content must not persist",
                "public_value": "fixture rejected key must not persist",
            }
        elif certificate.request_kind == "final_answer":
            answer = json.loads(json.dumps(self._final_answer))
            if self._wrong_final_answer:
                result = dict(answer["result"])
                first = next(iter(result))
                result[first] = "__schema_valid_semantic_error__"
                answer["result"] = result
            if (
                self._final_primary_failure_once
                and not self._final_primary_failure_used
                and certificate.phase == "primary"
            ):
                self._final_primary_failure_used = True
                payload = {"answer": answer}
            else:
                payload = exact_final_response_payload(
                    answer,
                    rationale_summary="Projected the verified public result.",
                )
        telemetry = telemetry.model_copy(
            update={
                "response_hash": canonical_hash(payload, prefix="scripted_privacy_first_response:"),
                "response_content_length": len(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ),
            }
        )
        return payload, telemetry


def _fixture_hash(raws: Sequence[runner.PrivacyFirstRawExecution]) -> str:
    return hashlib.sha256(
        json.dumps(
            [item.model_dump(mode="json") for item in raws],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _build_binding(
    static: static_stage.FinalGrammarStaticInputs,
    contract: runner.PrivacyFirstRunnerContract,
) -> RunnerBindingAudit:
    if (
        static.contract.contract_id != EXPECTED_V26_122_CONTRACT_ID
        or static.manifest.manifest_id != EXPECTED_V26_122_MANIFEST_ID
        or static.resource.contract_id != EXPECTED_V26_122_RESOURCE_ID
        or static.final_grammar.grammar_id != EXPECTED_FINAL_GRAMMAR_ID
        or contract.predecessor_static_contract_id != static.contract.contract_id
        or contract.predecessor_manifest_id != static.manifest.manifest_id
        or contract.semantic_action_protocol_id != static.contract.semantic_action_protocol_id
        or contract.semantic_action_response_grammar_id
        != static.contract.semantic_action_response_grammar_id
        or contract.exact_final_response_grammar_id != static.final_grammar.grammar_id
        or contract.candidate_space_authority_audit_id
        != static.contract.candidate_space_authority_audit_id
        or contract.stage_one_profile_id != static.stage_one.profile_id
        or contract.stage_two_profile_id != static.stage_two.profile_id
        or contract.resource_contract_id != static.resource.contract_id
        or contract.exact_job_denominator != len(static.manifest.jobs)
        or contract.exact_request_completion_bound_tokens
        != static.resource.exact_request_completion_bound_tokens
        or contract.rollout_upper_bound_tokens != static.resource.rollout_upper_bound_tokens
    ):
        raise ValueError("v26.123 Runner does not bind the exact v26.122 chain")
    values = {"runner_contract_id": contract.contract_id}
    provisional = RunnerBindingAudit.model_construct(audit_id="pending", **values)
    return RunnerBindingAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_privacy_first_runner_binding:"),
        **values,
    )


def _provider_pairs(
    raw: runner.PrivacyFirstRawExecution,
    root: Path,
) -> tuple[tuple[runner.PrivacyFirstProviderEnvelope, runner.PublicPayloadProjection], ...]:
    envelopes = tuple(
        runner.PrivacyFirstProviderEnvelope.model_validate(
            legacy.load_canonical_json(root / item.relative_path)
        )
        for item in raw.provider_envelope_artifacts
    )
    projections = tuple(
        runner.PublicPayloadProjection.model_validate(
            legacy.load_canonical_json(root / item.relative_path)
        )
        for item in raw.public_payload_projection_artifacts
    )
    if len(envelopes) != len(projections):
        raise ValueError("v26.123 Envelope/Projection denominator diverged")
    pairs = tuple(zip(envelopes, projections, strict=True))
    for envelope, projection in pairs:
        runner.validate_provider_artifact_pair(envelope, projection)
    return pairs


def _single_ledger_call(
    static: static_stage.FinalGrammarStaticInputs,
    contract: runner.PrivacyFirstRunnerContract,
    job: static_stage.FinalGrammarJob,
    root: Path,
    completion_tokens: int,
) -> tuple[bool, int, runner.PrivacyFirstJournaledClient]:
    client = ScriptedPrivacyFirstClient(
        static.agent_model_config,
        final_answer={"result": {"value": "fixture"}, "citations": [{"evidence_id": "fixture"}]},
        completion_tokens=completion_tokens,
    )
    ledger = runner.PrivacyFirstJournaledClient(
        client,
        runner_contract=contract,
        resource_contract=static.resource,
        job=job,
        output_dir=root,
    )
    host = make_final_response_host_envelope(
        terminal_state_id="fixture-terminal-state",
        terminal_commit_id="fixture-terminal-commit",
        grammar=static.final_grammar,
    )
    prompt = "Return exactly one JSON object with answer and rationale_summary."
    prepared = ledger.prepare(
        logical_request_index=0,
        request_kind="final_answer",
        public_attempt_phase="primary",
        primary_prompt=prompt,
        prompt=prompt,
        public_state_id=host.terminal_state_id,
        final_response_host_envelope=host,
        abi_rescue_count_before=1,
        semantic_recovery_count_before=1,
    )
    try:
        ledger.invoke(prepared)
    except runner.InstrumentContractError:
        return False, ledger.cumulative_tokens, ledger
    return True, ledger.cumulative_tokens, ledger


def _build_controls(
    static: static_stage.FinalGrammarStaticInputs,
    contract: runner.PrivacyFirstRunnerContract,
) -> tuple[
    RunnerFixtureAudit,
    FinalInterfaceControlAudit,
    PrivacyFirstCaptureAudit,
    SemanticRecoveryControlAudit,
    CertificateUsageRecoveryAudit,
    runner.PrivacyFirstRawExecution,
    runner.PrivacyFirstProviderEnvelope,
    runner.PublicPayloadProjection,
]:
    raws: list[runner.PrivacyFirstRawExecution] = []
    rows: list[RunnerFixtureRow] = []
    calls = 0
    action_payloads = 0
    final_payloads = 0
    choices = 0
    commits = 0
    observations = 0
    parent_matches = 0
    order_passes = 0
    exact_parent_passes = 0
    observation_projection = (
        predecessor_preflight.exact_preflight.legacy_preflight._observation_semantic_projection
    )
    with tempfile.TemporaryDirectory(prefix="v26_123_runner_fixture_") as temporary:
        root = Path(temporary)
        for job in sorted(static.manifest.jobs, key=lambda item: item.job_id):
            binding = runner.privacy_first_runtime_binding(static, job)
            client = ScriptedPrivacyFirstClient(
                static.agent_model_config,
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = runner.execute_privacy_first_job_raw(
                job=job,
                runner_contract=contract,
                static=static,
                binding=binding,
                client=client,
                output_dir=root,
            )
            expected_observations = (
                predecessor_preflight.exact_preflight.legacy_preflight._compiler_observations(
                    binding
                )
            )
            replay = legacy.replay_v3(
                raw,
                static=static.predecessor.historical,
                binding=binding,
            )
            verification, mechanism = _completed_verification(
                raw=raw, replay=replay, binding=binding
            )
            if (
                raw.terminal_disposition != "completed"
                or raw.completed_result is None
                or raw.completed_result.answer != binding.compiler_trajectory.final_answer
                or observation_projection(raw.observations)
                != observation_projection(expected_observations)
                or not replay.passed
                or not verification.valid
                or not mechanism.success
                or raw.semantic_rejections
                or raw.privacy_rejected_payload_count
            ):
                raise ValueError(f"v26.123 direct Runner fixture failed: {job.job_id}")
            pairs = _provider_pairs(raw, root)
            job_final = 0
            for envelope, projection in pairs:
                calls += 1
                parent_matches += int(
                    projection.provider_envelope_id == envelope.envelope_id
                    and envelope.runner_contract_id == contract.contract_id
                    and envelope.job_id == job.job_id
                )
                order_passes += int(
                    envelope.persisted_before_payload_validation
                    and projection.validation_performed_after_envelope_persistence
                )
                exact_parent_passes += int(
                    envelope.provider_telemetry.model_requested == legacy.STAGE_ONE_MODEL_ID
                    and envelope.provider_telemetry.model_selected == legacy.STAGE_ONE_MODEL_ID
                    and envelope.provider_telemetry.response_model == legacy.STAGE_ONE_MODEL_ID
                    and envelope.provider_telemetry.reasoning_content_present
                    and (envelope.provider_telemetry.reasoning_tokens or 0) > 0
                    and envelope.provider_telemetry.total_tokens is not None
                )
                payload = projection.response_payload or {}
                if envelope.request_kind == "semantic_proposal":
                    if set(payload) != {
                        "state_id",
                        "action_id",
                        "decision_kind",
                        "protocol",
                    }:
                        raise ValueError("v26.123 Action payload shape changed")
                    action_payloads += 1
                else:
                    if set(payload) != {"answer", "rationale_summary"}:
                        raise ValueError("v26.123 Final payload shape changed")
                    final_payloads += 1
                    job_final += 1
            choices += len(raw.semantic_choices)
            commits += len(raw.commits)
            observations += len(raw.observations)
            rows.append(
                RunnerFixtureRow(
                    job_id=job.job_id,
                    raw_execution_id=raw.artifact_id,
                    provider_call_count=raw.stage_one_provider_call_count,
                    semantic_choice_count=len(raw.semantic_choices),
                    stage_two_commit_count=len(raw.commits),
                    observation_count=len(raw.observations),
                    final_payload_count=job_final,
                )
            )
            raws.append(raw)
        if (
            calls != 256
            or action_payloads != 224
            or final_payloads != 32
            or choices != 224
            or commits != 224
            or observations != 192
            or parent_matches != 256
            or order_passes != 256
            or exact_parent_passes != 256
        ):
            raise ValueError("v26.123 direct fixture denominator changed")
        sample = raws[0]
        sample_binding = runner.privacy_first_runtime_binding(static, sample.job)
        recovered = runner.execute_privacy_first_job_raw(
            job=sample.job,
            runner_contract=contract,
            static=static,
            binding=sample_binding,
            client=None,
            output_dir=root,
        )
        final_root = root / "final_rescue_control"
        final_client = ScriptedPrivacyFirstClient(
            static.agent_model_config,
            final_answer=sample_binding.compiler_trajectory.final_answer,
            final_primary_failure_once=True,
        )
        final_raw = runner.execute_privacy_first_job_raw(
            job=sample.job,
            runner_contract=contract,
            static=static,
            binding=sample_binding,
            client=final_client,
            output_dir=final_root,
        )
        final_attempts = tuple(
            item for item in final_raw.attempts if item.request_kind == "final_answer"
        )
        final_replay = legacy.replay_v3(
            final_raw,
            static=static.predecessor.historical,
            binding=sample_binding,
        )
        final_verification, _ = _completed_verification(
            raw=final_raw, replay=final_replay, binding=sample_binding
        )
        final_prompts = tuple(
            prompt for kind, _, prompt in final_client.prompts if kind == "final_answer"
        )
        if (
            len(final_attempts) != 2
            or final_attempts[0].disposition != "model_result_failure"
            or final_attempts[1].disposition != "usable"
            or final_attempts[0].final_response_host_envelope_id
            != final_attempts[1].final_response_host_envelope_id
            or len(final_prompts) != 2
            or "json" not in final_prompts[1].casefold()
            or final_raw.terminal_disposition != "completed"
            or not final_verification.valid
        ):
            raise ValueError("v26.123 Final Rescue control failed")
        wrong_root = root / "wrong_final_control"
        wrong_client = ScriptedPrivacyFirstClient(
            static.agent_model_config,
            final_answer=sample_binding.compiler_trajectory.final_answer,
            wrong_final_answer=True,
        )
        wrong_raw = runner.execute_privacy_first_job_raw(
            job=sample.job,
            runner_contract=contract,
            static=static,
            binding=sample_binding,
            client=wrong_client,
            output_dir=wrong_root,
        )
        wrong_replay = legacy.replay_v3(
            wrong_raw,
            static=static.predecessor.historical,
            binding=sample_binding,
        )
        wrong_verification, _ = _completed_verification(
            raw=wrong_raw, replay=wrong_replay, binding=sample_binding
        )
        if (
            wrong_raw.terminal_disposition != "completed"
            or wrong_raw.completed_result is None
            or wrong_raw.completed_result.answer == sample_binding.compiler_trajectory.final_answer
            or wrong_verification.valid
        ):
            raise ValueError("v26.123 wrong-answer separation control failed")
        privacy_job = raws[1].job
        privacy_binding = runner.privacy_first_runtime_binding(static, privacy_job)
        privacy_root = root / "privacy_control"
        privacy_client = ScriptedPrivacyFirstClient(
            static.agent_model_config,
            privacy_failure_first_call=True,
        )
        privacy_raw = runner.execute_privacy_first_job_raw(
            job=privacy_job,
            runner_contract=contract,
            static=static,
            binding=privacy_binding,
            client=privacy_client,
            output_dir=privacy_root,
        )
        privacy_pairs = _provider_pairs(privacy_raw, privacy_root)
        privacy_envelope, privacy_projection = privacy_pairs[0]
        serialized_envelope = (
            privacy_root / privacy_raw.provider_envelope_artifacts[0].relative_path
        ).read_text(encoding="utf-8")
        serialized_projection = (
            privacy_root / privacy_raw.public_payload_projection_artifacts[0].relative_path
        ).read_text(encoding="utf-8")
        recovered_privacy = runner.execute_privacy_first_job_raw(
            job=privacy_job,
            runner_contract=contract,
            static=static,
            binding=privacy_binding,
            client=None,
            output_dir=privacy_root,
        )
        orphan_root = root / "orphan_control"
        orphan_path = runner.provider_envelope_path(orphan_root, privacy_job, 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            runner.execute_privacy_first_job_raw(
                job=privacy_job,
                runner_contract=contract,
                static=static,
                binding=privacy_binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            orphan_rejected = True
        else:
            orphan_rejected = False
        if (
            privacy_raw.terminal_disposition != "model_result"
            or privacy_raw.stage_one_provider_call_count != 1
            or privacy_raw.privacy_rejected_payload_count != 1
            or privacy_projection.projection_status != "privacy_rejected"
            or privacy_projection.response_payload is not None
            or privacy_envelope.provider_telemetry.response_model != legacy.STAGE_ONE_MODEL_ID
            or privacy_envelope.provider_telemetry.total_tokens is None
            or privacy_envelope.public_content_hash is None
            or privacy_envelope.public_content_length is None
            or "reasoning_trace" in serialized_envelope
            or "reasoning_trace" in serialized_projection
            or "fixture rejected key must not persist" in serialized_envelope
            or "fixture rejected key must not persist" in serialized_projection
            or recovered_privacy != privacy_raw
            or not orphan_rejected
        ):
            raise ValueError("v26.123 privacy-first capture control failed")
        recovery_sample = next(
            item for item in raws if item.semantic_choices[0].public_progress_after_commit is True
        )
        recovery_binding = runner.privacy_first_runtime_binding(static, recovery_sample.job)
        recovery_root = root / "combined_recovery"
        recovery_client = ScriptedPrivacyFirstClient(
            static.agent_model_config,
            final_answer=recovery_binding.compiler_trajectory.final_answer,
            combined_recovery_control=True,
        )
        recovery_raw = runner.execute_privacy_first_job_raw(
            job=recovery_sample.job,
            runner_contract=contract,
            static=static,
            binding=recovery_binding,
            client=recovery_client,
            output_dir=recovery_root,
        )
        recovery_choices = tuple(
            item
            for item in recovery_raw.semantic_choices
            if item.public_attempt_phase == "semantic_recovery"
        )
        recovery_pairs = _provider_pairs(recovery_raw, recovery_root)
        semantic_envelope = next(
            envelope
            for envelope, _ in recovery_pairs
            if envelope.public_attempt_phase == "semantic_recovery"
        )
        rejection = recovery_raw.semantic_rejections[0]
        if (
            recovery_raw.terminal_disposition != "completed"
            or recovery_raw.abi_rescue_attempt_count != 1
            or recovery_raw.semantic_recovery_attempt_count != 1
            or len(recovery_raw.semantic_rejections) != 1
            or len(recovery_choices) != 1
            or recovery_choices[0].different_action_after_rejection is not True
            or semantic_envelope.dynamic_certificate.abi_rescue_count_before != 1
            or semantic_envelope.dynamic_certificate.semantic_recovery_count_before != 1
        ):
            raise ValueError("v26.123 combined recovery control failed")
        control_client = ScriptedPrivacyFirstClient(static.agent_model_config)
        control_ledger = runner.PrivacyFirstJournaledClient(
            control_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "precall_controls",
        )
        oversized_prompt = "x" * 60001
        oversized = control_ledger.prepare(
            logical_request_index=0,
            request_kind="semantic_proposal",
            public_attempt_phase="primary",
            primary_prompt=oversized_prompt,
            prompt=oversized_prompt,
            public_state_id="fixture-state",
            final_response_host_envelope=None,
            abi_rescue_count_before=0,
            semantic_recovery_count_before=0,
        )
        before = control_client.call_count
        try:
            control_ledger.invoke(oversized)
        except Exception:
            pass
        oversized_rejected = control_client.call_count == before
        host = make_final_response_host_envelope(
            terminal_state_id="fixture-terminal-state",
            terminal_commit_id="fixture-terminal-commit",
            grammar=static.final_grammar,
        )
        reusable_prompt = "Return exactly one JSON object with answer and rationale_summary."
        reusable = control_ledger.prepare(
            logical_request_index=1,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=reusable_prompt,
            prompt=reusable_prompt,
            public_state_id=host.terminal_state_id,
            final_response_host_envelope=host,
            abi_rescue_count_before=1,
            semantic_recovery_count_before=1,
        )
        control_ledger.invoke(reusable)
        try:
            control_ledger.invoke(reusable)
        except runner.InstrumentContractError:
            reuse_rejected = True
        else:
            reuse_rejected = False
        budget_client = ScriptedPrivacyFirstClient(
            static.agent_model_config, completion_tokens=16385
        )
        budget_ledger = runner.PrivacyFirstJournaledClient(
            budget_client,
            runner_contract=contract,
            resource_contract=static.resource,
            job=sample.job,
            output_dir=root / "budget_control",
        )
        large_prompt = "Return JSON. " + "b" * 58987
        budget_denied = False
        for index in range(10):
            prepared = budget_ledger.prepare(
                logical_request_index=index,
                request_kind="final_answer",
                public_attempt_phase="primary",
                primary_prompt=large_prompt,
                prompt=large_prompt,
                public_state_id=host.terminal_state_id,
                final_response_host_envelope=host,
                abi_rescue_count_before=1,
                semantic_recovery_count_before=1,
            )
            try:
                budget_ledger.invoke(prepared)
            except Exception:
                budget_denied = not prepared.resource_certificate.provider_call_permitted
                break
        admitted_16384, charged_16384, _ = _single_ledger_call(
            static, contract, sample.job, root / "usage_16384", 16384
        )
        admitted_16385, charged_16385, _ = _single_ledger_call(
            static, contract, sample.job, root / "usage_16385", 16385
        )
        admitted_16386, _, failed_ledger = _single_ledger_call(
            static, contract, sample.job, root / "usage_16386", 16386
        )
        try:
            _single_ledger_call(
                static,
                contract,
                sample.job,
                root / "usage_after_failure",
                64,
            ) if not failed_ledger.instrument_failures else failed_ledger.prepare(
                logical_request_index=1,
                request_kind="final_answer",
                public_attempt_phase="primary",
                primary_prompt=reusable_prompt,
                prompt=reusable_prompt,
                public_state_id=host.terminal_state_id,
                final_response_host_envelope=host,
                abi_rescue_count_before=1,
                semantic_recovery_count_before=1,
            )
        except runner.InstrumentContractError:
            blocked_after_failure = True
        else:
            blocked_after_failure = False
        fixture_values = {
            "runner_contract_id": contract.contract_id,
            "rows": tuple(rows),
            "fixture_aggregate_sha256": _fixture_hash(raws),
        }
        fixture_provisional = RunnerFixtureAudit.model_construct(
            audit_id="pending", **fixture_values
        )
        fixture = RunnerFixtureAudit(
            audit_id=_identity(
                fixture_provisional,
                "audit_id",
                "finance_v26_privacy_first_runner_fixture:",
            ),
            **fixture_values,
        )
        final_values = {"runner_contract_id": contract.contract_id}
        final_provisional = FinalInterfaceControlAudit.model_construct(
            audit_id="pending", **final_values
        )
        final_audit = FinalInterfaceControlAudit(
            audit_id=_identity(
                final_provisional,
                "audit_id",
                "finance_v26_exact_final_interface_control:",
            ),
            **final_values,
        )
        privacy_values = {"runner_contract_id": contract.contract_id}
        privacy_provisional = PrivacyFirstCaptureAudit.model_construct(
            audit_id="pending", **privacy_values
        )
        privacy_audit = PrivacyFirstCaptureAudit(
            audit_id=_identity(
                privacy_provisional,
                "audit_id",
                "finance_v26_privacy_first_capture_control:",
            ),
            **privacy_values,
        )
        recovery_values = {
            "runner_contract_id": contract.contract_id,
            "correct_action_or_patch_exposed_count": int(
                rejection.correct_tool_exposed
                or rejection.correct_node_exposed
                or rejection.correct_operator_exposed
                or rejection.correct_operand_exposed
                or rejection.correct_evidence_exposed
            ),
        }
        recovery_provisional = SemanticRecoveryControlAudit.model_construct(
            audit_id="pending", **recovery_values
        )
        recovery_audit = SemanticRecoveryControlAudit(
            audit_id=_identity(
                recovery_provisional,
                "audit_id",
                "finance_v26_privacy_first_semantic_recovery_control:",
            ),
            **recovery_values,
        )
        certificate_values = {
            "runner_contract_id": contract.contract_id,
            "completion_16384_admitted": admitted_16384 and charged_16384 > 16384,
            "completion_16385_admitted_and_charged": (
                admitted_16385 and charged_16385 > charged_16384
            ),
            "completion_16386_instrument_failure": not admitted_16386,
            "calls_blocked_after_instrument_failure": blocked_after_failure,
            "oversized_prompt_rejected_before_provider": oversized_rejected,
            "reused_preparation_rejected": reuse_rejected,
            "insufficient_remaining_budget_rejected_before_provider": budget_denied,
            "complete_raw_recovery_byte_identical": recovered == sample,
            "exact_model_usage_thinking_parent_pass_count": exact_parent_passes,
        }
        certificate_provisional = CertificateUsageRecoveryAudit.model_construct(
            audit_id="pending", **certificate_values
        )
        certificate_audit = CertificateUsageRecoveryAudit(
            audit_id=_identity(
                certificate_provisional,
                "audit_id",
                "finance_v26_privacy_first_certificate_usage_recovery:",
            ),
            **certificate_values,
        )
        return (
            fixture,
            final_audit,
            privacy_audit,
            recovery_audit,
            certificate_audit,
            sample,
            privacy_envelope,
            privacy_projection,
        )


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except Exception:
        return MutationResult(name=name)
    raise ValueError(f"v26.123 destructive mutation was accepted: {name}")


def _reidentified_contract(
    contract: runner.PrivacyFirstRunnerContract,
    **updates: Any,
) -> runner.PrivacyFirstRunnerContract:
    provisional = contract.model_copy(update={**updates, "contract_id": "pending"})
    values = provisional.model_dump(mode="json")
    values["contract_id"] = _identity(
        provisional,
        "contract_id",
        "finance_v26_privacy_first_runner_contract:",
    )
    return runner.PrivacyFirstRunnerContract.model_validate(values)


def _reidentified_envelope(
    envelope: runner.PrivacyFirstProviderEnvelope,
    **updates: Any,
) -> runner.PrivacyFirstProviderEnvelope:
    provisional = envelope.model_copy(update={**updates, "envelope_id": "pending"})
    values = provisional.model_dump(mode="json")
    values["envelope_id"] = _identity(
        provisional,
        "envelope_id",
        "finance_v26_privacy_first_provider_envelope:",
    )
    return runner.PrivacyFirstProviderEnvelope.model_validate(values)


def _reidentified_projection(
    projection: runner.PublicPayloadProjection,
    **updates: Any,
) -> runner.PublicPayloadProjection:
    provisional = projection.model_copy(update={**updates, "projection_id": "pending"})
    values = provisional.model_dump(mode="json")
    values["projection_id"] = _identity(
        provisional,
        "projection_id",
        "finance_v26_public_payload_projection:",
    )
    return runner.PublicPayloadProjection.model_validate(values)


def _build_destructive(
    static: static_stage.FinalGrammarStaticInputs,
    contract: runner.PrivacyFirstRunnerContract,
    raw: runner.PrivacyFirstRawExecution,
    envelope: runner.PrivacyFirstProviderEnvelope,
    projection: runner.PublicPayloadProjection,
) -> DestructiveRunnerAudit:
    completed_result = raw.completed_result
    if completed_result is None:
        raise ValueError("destructive Runner audit requires one completed fixture")
    actions: dict[str, Callable[[], Any]] = {
        "candidate_authority_change": lambda: _build_binding(
            static,
            _reidentified_contract(contract, candidate_space_authority_audit_id="changed"),
        ),
        "completion_bound_change": lambda: runner.PrivacyFirstRunnerContract.model_validate(
            {
                **contract.model_dump(mode="json"),
                "exact_request_completion_bound_tokens": 32768,
            }
        ),
        "envelope_after_projection": lambda: runner.PrivacyFirstProviderEnvelope.model_validate(
            {
                **envelope.model_dump(mode="json"),
                "persisted_before_payload_validation": False,
            }
        ),
        "envelope_content_hash_change": lambda: _reidentified_envelope(
            envelope, public_content_hash="changed"
        ),
        "envelope_payload_insertion": lambda: runner.PrivacyFirstProviderEnvelope.model_validate(
            {**envelope.model_dump(mode="json"), "response_payload": {"forbidden": True}}
        ),
        "envelope_prompt_change": lambda: _reidentified_envelope(envelope, prompt_sha256="0" * 64),
        "final_grammar_change": lambda: _build_binding(
            static,
            _reidentified_contract(contract, exact_final_response_grammar_id="changed"),
        ),
        "host_answer_insertion": lambda: runner.PrivacyFirstCompletedResult.model_validate(
            {
                **completed_result.model_dump(mode="json"),
                "host_answer_or_rationale_inserted": True,
            }
        ),
        "invalid_key_persistence": lambda: runner.PublicPayloadProjection.model_validate(
            {
                **projection.model_dump(mode="json"),
                "invalid_payload_key_persisted": True,
            }
        ),
        "invalid_payload_persistence": lambda: runner.PublicPayloadProjection.model_validate(
            {
                **projection.model_dump(mode="json"),
                "response_payload": {"reasoning_trace": "forbidden"},
            }
        ),
        "model_profile_change": lambda: _build_binding(
            static,
            _reidentified_contract(contract, stage_one_profile_id="changed"),
        ),
        "private_reasoning_hash": lambda: runner.PrivacyFirstProviderEnvelope.model_validate(
            {
                **envelope.model_dump(mode="json"),
                "private_reasoning_content_hashed": True,
            }
        ),
        "projection_parent_change": lambda: runner.validate_provider_artifact_pair(
            envelope,
            _reidentified_projection(projection, provider_envelope_id="changed"),
        ),
        "raw_envelope_deletion": lambda: runner.PrivacyFirstRawExecution.model_validate(
            {
                **raw.model_dump(mode="json"),
                "provider_envelope_artifacts": list(raw.provider_envelope_artifacts[1:]),
            }
        ),
        "raw_projection_deletion": lambda: runner.PrivacyFirstRawExecution.model_validate(
            {
                **raw.model_dump(mode="json"),
                "public_payload_projection_artifacts": list(
                    raw.public_payload_projection_artifacts[1:]
                ),
            }
        ),
        "recovery_limit_change": lambda: runner.PrivacyFirstRunnerContract.model_validate(
            {**contract.model_dump(mode="json"), "maximum_abi_rescue_calls": 2}
        ),
        "resource_ceiling_change": lambda: runner.PrivacyFirstRunnerContract.model_validate(
            {**contract.model_dump(mode="json"), "rollout_upper_bound_tokens": 420000}
        ),
        "stage_two_provider_route": lambda: runner.PrivacyFirstRunnerContract.model_validate(
            {
                **contract.model_dump(mode="json"),
                "stage_two_provider_call_upper_bound": 1,
            }
        ),
        "validated_private_payload": lambda: runner.PublicPayloadProjection.model_validate(
            {
                **projection.model_dump(mode="json"),
                "projection_status": "validated_public_payload",
                "response_payload": {"reasoning_trace": "forbidden"},
                "failure_family": None,
                "failure_subtype": None,
            }
        ),
        "wrong_job_parent": lambda: _reidentified_envelope(envelope, job_id="changed"),
    }
    mutations = tuple(_expect_rejection(name, actions[name]) for name in sorted(actions))
    values = {"mutations": mutations}
    provisional = DestructiveRunnerAudit.model_construct(audit_id="pending", **values)
    return DestructiveRunnerAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_first_runner_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=legacy.sha256_file(path),
        byte_count=path.stat().st_size,
    )


def build(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> PrivacyFirstRunnerPreflightReport:
    source = _build_source_replay(package_root, implementation_root)
    static = static_stage.load_final_grammar_static_inputs(package_root, implementation_root)
    contract = runner.make_privacy_first_runner_contract(static)
    binding = _build_binding(static, contract)
    (
        fixture,
        final_control,
        privacy_control,
        semantic_recovery,
        certificate,
        sample_raw,
        sample_envelope,
        sample_projection,
    ) = _build_controls(static, contract)
    outcome_values = {"runner_contract_id": contract.contract_id}
    outcome_provisional = OutcomeMeasurementContract.model_construct(
        contract_id="pending", **outcome_values
    )
    outcome = OutcomeMeasurementContract(
        contract_id=_identity(
            outcome_provisional,
            "contract_id",
            "finance_v26_exact_final_outcome_measurement:",
        ),
        **outcome_values,
    )
    destructive = _build_destructive(
        static,
        contract,
        sample_raw,
        sample_envelope,
        sample_projection,
    )
    transition_values = {
        "runner_contract_id": contract.contract_id,
        "outcome_measurement_contract_id": outcome.contract_id,
    }
    transition_provisional = ProspectiveTransitionContract.model_construct(
        contract_id="pending", **transition_values
    )
    transition = ProspectiveTransitionContract(
        contract_id=_identity(
            transition_provisional,
            "contract_id",
            "finance_v26_privacy_first_runner_transition:",
        ),
        **transition_values,
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("source_replay_audit.json", source),
        ("runner_contract.json", contract),
        ("runner_binding_audit.json", binding),
        ("runner_fixture_audit.json", fixture),
        ("final_interface_control_audit.json", final_control),
        ("privacy_first_capture_audit.json", privacy_control),
        ("semantic_recovery_control_audit.json", semantic_recovery),
        ("certificate_usage_recovery_audit.json", certificate),
        ("outcome_measurement_contract.json", outcome),
        ("destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs:
        _write(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in outputs)
    values = {
        "source_replay_audit_id": source.audit_id,
        "runner_contract_id": contract.contract_id,
        "runner_binding_audit_id": binding.audit_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "final_interface_control_audit_id": final_control.audit_id,
        "privacy_first_capture_audit_id": privacy_control.audit_id,
        "semantic_recovery_control_audit_id": semantic_recovery.audit_id,
        "certificate_usage_recovery_audit_id": certificate.audit_id,
        "outcome_measurement_contract_id": outcome.contract_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = PrivacyFirstRunnerPreflightReport.model_construct(report_id="pending", **values)
    report = PrivacyFirstRunnerPreflightReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_privacy_first_runner_preflight_report:",
        ),
        **values,
    )
    _write(output_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credential-free v26.123 privacy-first exact Final Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument(
        "--implementation-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--output-dir", type=Path, default=Path(OUTPUT_DIR))
    args = parser.parse_args()
    report = build(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
