from __future__ import annotations

import argparse
import json
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_preflight as recovery,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_online as semantic_online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingVerificationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    MechanismEstimandOutcome,
    evaluate_mechanism_estimand,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_127_exact_failed_call_transport_recovery_execution_v1_20260823"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_127_exact_failed_call_transport_recovery_execution_v1_20260823"
)
PREFLIGHT_DIR: Final = recovery.OUTPUT_DIR
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_exact_failed_call_transport_recovery_online.py"
)
EXPECTED_PREFLIGHT_REPORT_ID: Final = (
    "finance_v26_transport_recovery_preflight_report:"
    "3728c94bbdbf5d676269f1460c07d826ad8e444693b0178d20584e4a61010c62"
)
EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID: Final = (
    "finance_v26_transport_recovery_source_replay:"
    "e901da4ebe91bdd9d846d44dac1fc8fc12a9dcfa0b46263b1fa79bb4cd9df83e"
)
EXPECTED_RECOVERY_CONTRACT_ID: Final = (
    "finance_v26_exact_failed_call_recovery_contract:"
    "b41d20f95d1c4245efc1a0468bb2d4161dfec0d2054f6812e68c2a262011048d"
)
EXPECTED_RECOVERY_MANIFEST_ID: Final = (
    "finance_v26_exact_failed_call_recovery_manifest:"
    "2e92bca0b3afc2081f6fa8e0ad5708ce3ae9b83a8ce451a108e17888301eb857"
)
EXPECTED_RECOVERY_RUNNER_ID: Final = (
    "finance_v26_exact_failed_call_recovery_runner_contract:"
    "8278ce674c4c097d59341bab28ccf9b8820b5d464739c16e6a2bae02dc7786a6"
)
EXPECTED_TRANSITION_ID: Final = (
    "finance_v26_transport_recovery_runner_transition:"
    "d54808d4d5523989466f0225892f0f037dbf312e93d0b6e17a40af16d0eb1eec"
)
POSTRUN_STAGE: Final = "exact_failed_call_transport_recovery_postrun_audit_only"
PREFLIGHT_OUTPUTS: Final = (
    "source_replay_audit.json",
    "recovery_contract.json",
    "recovery_job_manifest.json",
    "recovery_runner_contract.json",
    "prefix_replay_audit.json",
    "scripted_recovery_audit.json",
    "recovery_control_audit.json",
    "destructive_audit.json",
    "prospective_transition_contract.json",
    "report.json",
)

TerminalCategory = Literal[
    "model_valid_trajectory",
    "model_invalid_trajectory",
    "completion_unusable",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_126_transitive_source",
        "v26_126_output",
        "v26_127_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class RecoveryExecutionSourceReplay(FrozenModel):
    audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    preflight_source_replay_id: str = EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
    preflight_transitive_file_count: Literal[2973] = 2973
    preflight_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[2984] = 2984
    replay_pass_count: Literal[2984] = 2984
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=2984, max_length=2984)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_recovery_execution_source_replay.v1"] = (
        "finance_v26_recovery_execution_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryExecutionSourceReplay:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.127 source replay paths changed")
        if any(item.expected_sha256 != item.observed_sha256 for item in self.entries):
            raise ValueError("v26.127 source replay contains a hash mismatch")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_recovery_execution_source_replay:",
        ):
            raise ValueError("v26.127 source replay identity changed")
        return self


class PreexecutionPrefixRow(FrozenModel):
    recovery_job_id: str = Field(min_length=1)
    prefix_replay_id: str = Field(min_length=1)
    successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    exact_failed_prompt_sha256: str = Field(min_length=64, max_length=64)


class PreexecutionRecoveryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_recovery_job_count: Literal[10] = 10
    prefix_replay_pass_count: Literal[10] = 10
    exact_failed_request_rebinding_pass_count: Literal[10] = 10
    rows: tuple[PreexecutionPrefixRow, ...] = Field(min_length=10, max_length=10)
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_recovery_preexecution_audit.v1"] = (
        "finance_v26_recovery_preexecution_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PreexecutionRecoveryAudit:
        if tuple(item.recovery_job_id for item in self.rows) != tuple(
            sorted(item.recovery_job_id for item in self.rows)
        ):
            raise ValueError("v26.127 preexecution rows changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_recovery_preexecution_audit:",
        ):
            raise ValueError("v26.127 preexecution identity changed")
        return self


class RecoveryJobResult(FrozenModel):
    result_id: str = Field(min_length=1)
    recovery_runner_contract_id: str = EXPECTED_RECOVERY_RUNNER_ID
    recovery_job_id: str = Field(min_length=1)
    recovery_candidate_id: str = Field(min_length=1)
    historical_job_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    requested_path_strategy_id: str = Field(min_length=1)
    terminal_category: TerminalCategory
    raw_terminal_disposition: str = Field(min_length=1)
    terminal_failure_type: str | None = None
    successful_prefix_provider_call_count: int = Field(ge=0, le=2)
    successor_provider_call_count: int = Field(ge=1, le=12)
    combined_trajectory_provider_call_count: int = Field(ge=1, le=12)
    exact_failed_call_replacement_count: Literal[1] = 1
    successor_http_success_call_count: int = Field(ge=0, le=12)
    successor_validated_public_payload_count: int = Field(ge=0, le=12)
    successor_privacy_rejected_payload_count: int = Field(ge=0, le=12)
    successor_provider_failure_no_payload_count: int = Field(ge=0, le=12)
    successor_prompt_tokens: int = Field(ge=0)
    successor_completion_tokens: int = Field(ge=0)
    successor_reasoning_tokens: int = Field(ge=0)
    successor_total_tokens: int = Field(ge=0)
    successor_estimated_cost_usd: str = Field(min_length=1)
    successful_prefix_tokens: int = Field(ge=0)
    combined_trajectory_tokens: int = Field(ge=0, le=400000)
    rollout_headroom_tokens: int = Field(ge=0, le=400000)
    original_failed_call_usage_unknown: Literal[True] = True
    original_failed_call_usage_imputed: Literal[False] = False
    primary_attempt_count: int = Field(ge=1, le=12)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    semantic_choice_count: int = Field(ge=0, le=11)
    stage_two_commit_count: int = Field(ge=0, le=11)
    observation_count: int = Field(ge=0, le=10)
    program_node_count: int = Field(ge=0)
    completed_program_node_count: int = Field(ge=0)
    program_closed: bool
    terminal_node_completed: bool
    postterminal_verification_completed: bool
    final_commit_count: int = Field(ge=0, le=1)
    final_request_attempt_count: int = Field(ge=0, le=2)
    exact_two_field_final_payload_count: int = Field(ge=0, le=1)
    final_abi_crossed: bool
    final_answer_emitted: bool
    final_answer_semantically_valid: bool
    independent_validity: bool
    mechanism_success: bool
    requested_path_adhered: bool
    replay_v3_passed: bool
    exact_model_passed: bool
    native_tool_absence_passed: bool
    thinking_continuity_passed: bool
    provider_usage_complete: bool
    fallback_absence_passed: bool
    fresh_invocation_binding_passed: bool
    historical_failed_request_binding_passed: bool
    privacy_artifact_pairing_passed: bool
    reversible_commit_passed: bool
    stage_two_provider_call_count: Literal[0] = 0
    verification_report: AuthorityPreservingVerificationReport | None = None
    mechanism_outcome: MechanismEstimandOutcome
    raw_execution_artifact: legacy.RawFileDescriptor
    engineering_calibration_only: Literal[True] = True
    capability_denominator_eligible: Literal[False] = False
    reachability_denominator_eligible: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    training_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_transport_recovery_job_result.v1"] = (
        "finance_v26_transport_recovery_job_result.v1"
    )

    @model_validator(mode="after")
    def validate_result(self) -> RecoveryJobResult:
        if self.combined_trajectory_provider_call_count != (
            self.successful_prefix_provider_call_count + self.successor_provider_call_count
        ):
            raise ValueError("v26.127 combined call denominator changed")
        if self.successor_provider_call_count != (
            self.successor_validated_public_payload_count
            + self.successor_privacy_rejected_payload_count
            + self.successor_provider_failure_no_payload_count
        ):
            raise ValueError("v26.127 successor Projection partition changed")
        if self.combined_trajectory_tokens != (
            self.successful_prefix_tokens + self.successor_total_tokens
        ):
            raise ValueError("v26.127 trajectory token accounting changed")
        if self.final_abi_crossed != bool(self.exact_two_field_final_payload_count):
            raise ValueError("v26.127 Final ABI accounting changed")
        if self.independent_validity != (self.terminal_category == "model_valid_trajectory"):
            raise ValueError("v26.127 valid terminal accounting changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "finance_v26_transport_recovery_job_result:",
        ):
            raise ValueError("v26.127 RecoveryJob result identity changed")
        return self


class RecoveryRawLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_recovery_job_count: Literal[10] = 10
    raw_execution_count: Literal[10] = 10
    successor_provider_call_count: int = Field(ge=10, le=120)
    successor_envelope_count: int = Field(ge=10, le=120)
    successor_projection_count: int = Field(ge=10, le=120)
    complete_pair_count: int = Field(ge=10, le=120)
    unique_envelope_id_count: int = Field(ge=10, le=120)
    unique_projection_id_count: int = Field(ge=10, le=120)
    original_failed_call_usage_imputation_count: Literal[0] = 0
    private_reasoning_payload_count: Literal[0] = 0
    invalid_payload_content_persistence_count: Literal[0] = 0
    invalid_payload_key_persistence_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    file_count: int = Field(ge=30)
    files: tuple[legacy.RawFileDescriptor, ...] = Field(min_length=30)
    exact_byte_replay_pass_count: int = Field(ge=30)
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_transport_recovery_raw_lineage.v1"] = (
        "finance_v26_transport_recovery_raw_lineage.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryRawLineageAudit:
        if (
            self.successor_provider_call_count != self.successor_envelope_count
            or self.successor_provider_call_count != self.successor_projection_count
            or self.successor_provider_call_count != self.complete_pair_count
            or self.unique_envelope_id_count != self.successor_provider_call_count
            or self.unique_projection_id_count != self.successor_provider_call_count
            or self.file_count != len(self.files)
            or self.exact_byte_replay_pass_count != self.file_count
        ):
            raise ValueError("v26.127 Raw Lineage denominator changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_transport_recovery_raw_lineage:",
        ):
            raise ValueError("v26.127 Raw Lineage identity changed")
        return self


class RecoveryExecutionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    preflight_report_id: str = EXPECTED_PREFLIGHT_REPORT_ID
    recovery_contract_id: str = EXPECTED_RECOVERY_CONTRACT_ID
    recovery_manifest_id: str = EXPECTED_RECOVERY_MANIFEST_ID
    recovery_runner_contract_id: str = EXPECTED_RECOVERY_RUNNER_ID
    preexecution_audit_id: str = Field(min_length=1)
    raw_lineage_audit_id: str = Field(min_length=1)
    exact_recovery_job_denominator: Literal[10] = 10
    completed_recovery_job_count: Literal[10] = 10
    recovery_terminal_counts: dict[str, int]
    successor_provider_call_count: int = Field(ge=10, le=120)
    successor_http_success_call_count: int = Field(ge=0, le=120)
    successor_prompt_tokens: int = Field(ge=0)
    successor_completion_tokens: int = Field(ge=0)
    successor_reasoning_tokens: int = Field(ge=0)
    successor_total_tokens: int = Field(ge=0)
    successor_estimated_cost_usd: str = Field(min_length=1)
    frozen_historical_model_outcome_count: Literal[22] = 22
    frozen_historical_valid_count: Literal[11] = 11
    frozen_historical_invalid_count: Literal[11] = 11
    fresh_model_outcome_count: int = Field(ge=0, le=10)
    fresh_valid_count: int = Field(ge=0, le=10)
    fresh_invalid_count: int = Field(ge=0, le=10)
    combined_model_outcome_count: int = Field(ge=22, le=32)
    combined_valid_count: int = Field(ge=11, le=21)
    combined_invalid_count: int = Field(ge=11, le=21)
    exact_32_model_endpoint_denominator_complete: bool
    original_failed_http_success_usage_unknown_count: Literal[8] = 8
    original_failed_no_http_usage_unknown_count: Literal[2] = 2
    original_failed_call_usage_imputation_count: Literal[0] = 0
    historical_observable_billing_tokens_lower_bound: Literal[802956] = 802956
    historical_observable_cost_usd_lower_bound: Literal["0.14938994000000001406"] = (
        "0.14938994000000001406"
    )
    combined_observable_billing_tokens_lower_bound: int = Field(ge=802956)
    combined_observable_cost_usd_lower_bound: str = Field(min_length=1)
    trajectory_resource_accounting_separate_from_billing_lower_bound: Literal[True] = True
    historical_jobs_rerun_or_reclassified: Literal[False] = False
    historical_model_outcomes_rerun_or_reclassified: Literal[False] = False
    stage_two_provider_call_count: Literal[0] = 0
    engineering_calibration_only: Literal[True] = True
    capability_rows: Literal[0] = 0
    reachability_rows: Literal[0] = 0
    state_mapping_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_contribution: Literal[0] = 0
    execution_status: Literal["completed_pending_independent_audit"] = (
        "completed_pending_independent_audit"
    )
    next_permitted_stage: str = POSTRUN_STAGE
    schema_version: Literal["finance_v26_transport_recovery_execution_report.v1"] = (
        "finance_v26_transport_recovery_execution_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RecoveryExecutionReport:
        if sum(self.recovery_terminal_counts.values()) != 10:
            raise ValueError("v26.127 Recovery terminal denominator changed")
        if self.combined_model_outcome_count != 22 + self.fresh_model_outcome_count:
            raise ValueError("v26.127 combined endpoint denominator changed")
        if self.combined_valid_count != 11 + self.fresh_valid_count:
            raise ValueError("v26.127 combined valid count changed")
        if self.combined_invalid_count != 11 + self.fresh_invalid_count:
            raise ValueError("v26.127 combined invalid count changed")
        if self.exact_32_model_endpoint_denominator_complete != (
            self.fresh_model_outcome_count == 10
        ):
            raise ValueError("v26.127 exact endpoint completion flag changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_transport_recovery_execution_report:",
        ):
            raise ValueError("v26.127 execution report identity changed")
        return self


class PreparedExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source_replay: RecoveryExecutionSourceReplay
    preflight_report: recovery.RecoveryPreflightReport
    recovery_contract: recovery.ExactFailedCallRecoveryContract
    recovery_manifest: recovery.ExactFailedCallRecoveryManifest
    runner_contract: recovery.ExactFailedCallRecoveryRunnerContract
    transition_contract: recovery.ProspectiveTransitionContract
    preexecution: PreexecutionRecoveryAudit
    static: Any
    historical_runner_contract: Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _descriptor(path: Path, output_dir: Path) -> legacy.RawFileDescriptor:
    return legacy.RawFileDescriptor(
        relative_path=str(path.resolve().relative_to(output_dir.resolve())),
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
    raise ValueError(f"v26.127 cannot replay bound file: {relative_path}")


def build_execution_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
    preflight_dir: Path,
) -> RecoveryExecutionSourceReplay:
    predecessor = recovery.RecoverySourceReplayAudit.model_validate(
        _load(preflight_dir / "source_replay_audit.json")
    )
    report = recovery.RecoveryPreflightReport.model_validate(_load(preflight_dir / "report.json"))
    if (
        predecessor.audit_id != EXPECTED_PREFLIGHT_SOURCE_REPLAY_ID
        or report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.source_replay_audit_id != predecessor.audit_id
    ):
        raise ValueError("v26.127 predecessor preflight identity changed")
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
            source_kind="v26_126_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=legacy.sha256_file(path),
            byte_count=path.stat().st_size,
        )
    details = {item.relative_path: item for item in report.detail_files}
    if set(PREFLIGHT_OUTPUTS) != {"report.json", *details}:
        raise ValueError("v26.127 predecessor output set changed")
    for name in PREFLIGHT_OUTPUTS:
        path = preflight_dir / name
        observed = legacy.sha256_file(path)
        if name != "report.json":
            expected = details[name]
            if expected.sha256 != observed or expected.byte_count != path.stat().st_size:
                raise ValueError("v26.127 predecessor detail binding changed")
        relative = str(Path(PREFLIGHT_DIR) / name)
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_126_output",
            expected_sha256=observed,
            observed_sha256=observed,
            byte_count=path.stat().st_size,
        )
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    digest = legacy.sha256_file(implementation_path)
    entries[IMPLEMENTATION_PATH] = SourceReplayEntry(
        relative_path=IMPLEMENTATION_PATH,
        source_kind="v26_127_implementation",
        expected_sha256=digest,
        observed_sha256=digest,
        byte_count=implementation_path.stat().st_size,
    )
    values = {"entries": tuple(entries[key] for key in sorted(entries))}
    provisional = RecoveryExecutionSourceReplay.model_construct(audit_id="pending", **values)
    return RecoveryExecutionSourceReplay(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_recovery_execution_source_replay:",
        ),
        **values,
    )


def build_preexecution_audit(
    *,
    prepared: recovery.PreparedRecoveryPreflight,
    historical_execution_dir: Path,
) -> PreexecutionRecoveryAudit:
    rows: list[PreexecutionPrefixRow] = []
    for job in prepared.recovery_manifest.jobs:
        prefix = recovery.replay_successful_prefix(
            recovery_job=job,
            static=prepared.static,
            historical_runner_contract=prepared.historical_runner_contract,
            historical_execution_dir=historical_execution_dir,
        ).replay
        if (
            prefix.exact_failed_prompt_sha256 != job.exact_failed_request_prompt_sha256
            or prefix.exact_failed_dynamic_certificate_id != job.exact_failed_dynamic_certificate_id
            or prefix.exact_failed_request_binding_certificate_id
            != job.exact_failed_request_binding_certificate_id
            or prefix.exact_failed_resource_certificate_id
            != job.exact_failed_resource_certificate_id
            or prefix.historical_prefix_provider_calls_reissued
            or prefix.historical_failed_call_reissued
        ):
            raise ValueError("v26.127 exact failed request preexecution replay changed")
        rows.append(
            PreexecutionPrefixRow(
                recovery_job_id=job.recovery_job_id,
                prefix_replay_id=prefix.replay_id,
                successful_prefix_provider_call_count=(
                    prefix.successful_prefix_provider_call_count
                ),
                exact_failed_prompt_sha256=prefix.exact_failed_prompt_sha256,
            )
        )
    values = {"rows": tuple(rows)}
    provisional = PreexecutionRecoveryAudit.model_construct(audit_id="pending", **values)
    return PreexecutionRecoveryAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_recovery_preexecution_audit:",
        ),
        **values,
    )


def prepare_execution(
    *,
    preflight_dir: Path,
    historical_execution_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
) -> PreparedExecution:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = build_execution_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    frozen = recovery.load_prepared_recovery(
        package_root=package_root,
        implementation_root=implementation_root,
        preflight_dir=preflight_dir,
    )
    report = recovery.RecoveryPreflightReport.model_validate(_load(preflight_dir / "report.json"))
    transition = recovery.ProspectiveTransitionContract.model_validate(
        _load(preflight_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREFLIGHT_REPORT_ID
        or report.recovery_contract_id != EXPECTED_RECOVERY_CONTRACT_ID
        or report.recovery_manifest_id != EXPECTED_RECOVERY_MANIFEST_ID
        or report.recovery_runner_contract_id != EXPECTED_RECOVERY_RUNNER_ID
        or report.transition_contract_id != EXPECTED_TRANSITION_ID
        or report.status != "passed_exact_transport_recovery_preflight"
        or report.next_permitted_stage != recovery.NEXT_STAGE
        or report.real_provider_calls
        or report.stage_two_provider_calls
        or frozen.recovery_contract.contract_id != EXPECTED_RECOVERY_CONTRACT_ID
        or frozen.recovery_manifest.manifest_id != EXPECTED_RECOVERY_MANIFEST_ID
        or frozen.runner_contract.runner_contract_id != EXPECTED_RECOVERY_RUNNER_ID
        or transition.contract_id != EXPECTED_TRANSITION_ID
        or not transition.provider_calls_authorized
        or not transition.only_exact_ten_recovery_job_manifest_authorized
        or transition.successful_prefix_provider_calls_authorized
        or len(frozen.recovery_manifest.jobs) != 10
    ):
        raise ValueError("v26.127 predecessor online authorization changed")
    preexecution = build_preexecution_audit(
        prepared=frozen,
        historical_execution_dir=historical_execution_dir,
    )
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("online_source_replay_audit.json", source),
        ("recovery_contract.json", frozen.recovery_contract),
        ("frozen_recovery_job_manifest.json", frozen.recovery_manifest),
        ("recovery_runner_contract.json", frozen.runner_contract),
        ("preexecution_prefix_replay_audit.json", preexecution),
    )
    for name, value in outputs:
        recovery._write_json_atomic(output_dir / name, value.model_dump(mode="json"))
    return PreparedExecution(
        source_replay=source,
        preflight_report=report,
        recovery_contract=frozen.recovery_contract,
        recovery_manifest=frozen.recovery_manifest,
        runner_contract=frozen.runner_contract,
        transition_contract=transition,
        preexecution=preexecution,
        static=frozen.static,
        historical_runner_contract=frozen.historical_runner_contract,
    )


def _project_job_result(
    *,
    raw: recovery.RecoveryRawExecution,
    prepared: PreparedExecution,
    output_dir: Path,
) -> RecoveryJobResult:
    binding = recovery.historical_runner.privacy_first_runtime_binding(prepared.static, raw.job)
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
    pairs = recovery._load_recovery_pairs(raw, output_dir)
    projection_counts = Counter(projection.projection_status for _, projection in pairs)
    combined_telemetry = (
        *raw.historical_prefix_provider_telemetry,
        *raw.successor_provider_telemetry,
    )
    exact_model, fallback_absent, native_absent, thinking, usage = semantic_online._telemetry_flags(
        combined_telemetry
    )
    fresh_invocation = bool(pairs) and all(
        envelope.invocation_certificate.recovery_job_id == raw.recovery_job.recovery_job_id
        and envelope.invocation_certificate.recovery_candidate_id
        == raw.recovery_job.candidate.candidate_id
        and envelope.invocation_certificate.exact_failed_call_replacement == (index == 0)
        and envelope.recovery_provider_call_index == index
        for index, (envelope, _) in enumerate(pairs)
    )
    first_envelope = pairs[0][0] if pairs else None
    failed_request_binding = bool(
        first_envelope is not None
        and first_envelope.prompt_sha256 == raw.recovery_job.exact_failed_request_prompt_sha256
        and first_envelope.historical_dynamic_certificate.certificate_id
        == raw.recovery_job.exact_failed_dynamic_certificate_id
        and first_envelope.request_binding_certificate.certificate_id
        == raw.recovery_job.exact_failed_request_binding_certificate_id
        and first_envelope.resource_certificate_id
        == raw.recovery_job.exact_failed_resource_certificate_id
    )
    privacy_pairing = bool(
        len(pairs)
        == len(raw.successor_provider_envelope_artifacts)
        == len(raw.successor_payload_projection_artifacts)
        == raw.successor_provider_call_count
    )
    reversible = all(
        item.reversible_same_action_id_passed
        and not item.semantic_choice_inserted_by_host
        and item.stage_two_provider_calls == 0
        for item in raw.commits
    )
    instrument = bool(
        raw.terminal_disposition == "instrument_failure"
        or not exact_model
        or not fallback_absent
        or not native_absent
        or not thinking
        or not usage
        or not fresh_invocation
        or not failed_request_binding
        or not privacy_pairing
        or not reversible
        or not replay.passed
        or raw.stage_two_provider_call_count
        or raw.cumulative_provider_tokens > 400000
        or raw.original_failed_call_usage_imputed
    )
    transport = raw.terminal_disposition == "provider_transport_failure"
    typed = raw.terminal_disposition == "typed_budget_no_call"
    completion = raw.terminal_disposition == "completion_unusable"
    answer_valid = bool(verification is not None and verification.valid)
    valid = bool(answer_valid and not instrument and not transport and not typed and not completion)
    terminal: TerminalCategory
    if instrument:
        terminal = "instrument_failure"
    elif transport:
        terminal = "provider_transport_failure"
    elif typed:
        terminal = "typed_budget_no_call"
    elif completion:
        terminal = "completion_unusable"
    elif valid:
        terminal = "model_valid_trajectory"
    else:
        terminal = "model_invalid_trajectory"
    completed_nodes, node_count, program_closed, terminal_completed, verified = (
        semantic_online._progress_diagnostic(binding.record, raw.observations)
    )
    route = semantic_online._actual_route(raw.observations)
    final_attempts = tuple(item for item in raw.attempts if item.request_kind == "final_answer")
    exact_final = tuple(item for item in final_attempts if item.exact_two_field_final_payload)
    successor_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in raw.successor_provider_telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    values: dict[str, Any] = {
        "recovery_job_id": raw.recovery_job.recovery_job_id,
        "recovery_candidate_id": raw.recovery_job.candidate.candidate_id,
        "historical_job_id": raw.job.job_id,
        "source_task_artifact_id": raw.job.source_task_artifact_id,
        "mechanism_id": raw.job.mechanism_id,
        "requested_path_strategy_id": raw.job.path_strategy_id,
        "terminal_category": terminal,
        "raw_terminal_disposition": raw.terminal_disposition,
        "terminal_failure_type": raw.terminal_failure_type,
        "successful_prefix_provider_call_count": (
            raw.historical_successful_prefix_provider_call_count
        ),
        "successor_provider_call_count": raw.successor_provider_call_count,
        "combined_trajectory_provider_call_count": raw.stage_one_provider_call_count,
        "successor_http_success_call_count": sum(
            item.http_success for item in raw.successor_provider_telemetry
        ),
        "successor_validated_public_payload_count": projection_counts["validated_public_payload"],
        "successor_privacy_rejected_payload_count": projection_counts["privacy_rejected"],
        "successor_provider_failure_no_payload_count": projection_counts[
            "provider_failure_no_payload"
        ],
        "successor_prompt_tokens": sum(
            item.prompt_tokens or 0 for item in raw.successor_provider_telemetry
        ),
        "successor_completion_tokens": sum(
            item.completion_tokens or 0 for item in raw.successor_provider_telemetry
        ),
        "successor_reasoning_tokens": sum(
            item.reasoning_tokens or 0 for item in raw.successor_provider_telemetry
        ),
        "successor_total_tokens": sum(
            item.total_tokens or 0 for item in raw.successor_provider_telemetry
        ),
        "successor_estimated_cost_usd": format(successor_cost, "f"),
        "successful_prefix_tokens": raw.historical_successful_prefix_tokens,
        "combined_trajectory_tokens": raw.cumulative_provider_tokens,
        "rollout_headroom_tokens": 400000 - raw.cumulative_provider_tokens,
        "primary_attempt_count": sum(
            item.public_attempt_phase == "primary" for item in raw.attempts
        ),
        "abi_rescue_attempt_count": raw.abi_rescue_attempt_count,
        "semantic_recovery_attempt_count": raw.semantic_recovery_attempt_count,
        "semantic_choice_count": len(raw.semantic_choices),
        "stage_two_commit_count": len(raw.commits),
        "observation_count": len(raw.observations),
        "program_node_count": node_count,
        "completed_program_node_count": completed_nodes,
        "program_closed": program_closed,
        "terminal_node_completed": terminal_completed,
        "postterminal_verification_completed": verified,
        "final_commit_count": sum(item.commit.action == "emit_final" for item in raw.commits),
        "final_request_attempt_count": len(final_attempts),
        "exact_two_field_final_payload_count": len(exact_final),
        "final_abi_crossed": bool(exact_final),
        "final_answer_emitted": raw.completed_result is not None,
        "final_answer_semantically_valid": answer_valid,
        "independent_validity": valid,
        "mechanism_success": mechanism.success,
        "requested_path_adhered": route == raw.job.path_strategy_id,
        "replay_v3_passed": replay.passed,
        "exact_model_passed": exact_model,
        "native_tool_absence_passed": native_absent,
        "thinking_continuity_passed": thinking,
        "provider_usage_complete": usage,
        "fallback_absence_passed": fallback_absent,
        "fresh_invocation_binding_passed": fresh_invocation,
        "historical_failed_request_binding_passed": failed_request_binding,
        "privacy_artifact_pairing_passed": privacy_pairing,
        "reversible_commit_passed": reversible,
        "verification_report": verification,
        "mechanism_outcome": mechanism,
        "raw_execution_artifact": _descriptor(
            recovery.recovery_raw_path(output_dir, raw.recovery_job), output_dir
        ),
    }
    provisional = RecoveryJobResult.model_construct(result_id="pending", **values)
    return RecoveryJobResult(
        result_id=_identity(
            provisional,
            "result_id",
            "finance_v26_transport_recovery_job_result:",
        ),
        **values,
    )


def build_raw_lineage_audit(
    *,
    raws: Sequence[recovery.RecoveryRawExecution],
    output_dir: Path,
) -> RecoveryRawLineageAudit:
    descriptors: list[legacy.RawFileDescriptor] = []
    envelope_ids: list[str] = []
    projection_ids: list[str] = []
    provider_calls = 0
    for raw in raws:
        raw_path = recovery.recovery_raw_path(output_dir, raw.recovery_job)
        descriptors.append(_descriptor(raw_path, output_dir))
        pairs = recovery._load_recovery_pairs(raw, output_dir)
        provider_calls += len(pairs)
        for envelope, projection in pairs:
            envelope_path = (
                output_dir
                / raw.successor_provider_envelope_artifacts[
                    envelope.recovery_provider_call_index
                ].relative_path
            )
            projection_path = (
                output_dir
                / raw.successor_payload_projection_artifacts[
                    projection.recovery_provider_call_index
                ].relative_path
            )
            descriptors.extend(
                (_descriptor(envelope_path, output_dir), _descriptor(projection_path, output_dir))
            )
            envelope_ids.append(envelope.envelope_id)
            projection_ids.append(projection.projection_id)
            if (
                envelope.private_reasoning_content_persisted
                or envelope.private_reasoning_content_hashed
                or envelope.payload_content_persisted
                or projection.invalid_payload_content_persisted
                or projection.invalid_payload_key_persisted
                or projection.private_reasoning_content_persisted
                or raw.original_failed_call_usage_imputed
            ):
                raise ValueError("v26.127 privacy or Usage-imputation lineage breach")
    ordered = tuple(sorted(descriptors, key=lambda item: item.relative_path))
    values = {
        "successor_provider_call_count": provider_calls,
        "successor_envelope_count": len(envelope_ids),
        "successor_projection_count": len(projection_ids),
        "complete_pair_count": provider_calls,
        "unique_envelope_id_count": len(set(envelope_ids)),
        "unique_projection_id_count": len(set(projection_ids)),
        "file_count": len(ordered),
        "files": ordered,
        "exact_byte_replay_pass_count": len(ordered),
    }
    provisional = RecoveryRawLineageAudit.model_construct(audit_id="pending", **values)
    return RecoveryRawLineageAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_transport_recovery_raw_lineage:",
        ),
        **values,
    )


def _make_execution_report(
    *,
    prepared: PreparedExecution,
    results: Sequence[RecoveryJobResult],
    lineage: RecoveryRawLineageAudit,
) -> RecoveryExecutionReport:
    terminal_counts = Counter(item.terminal_category for item in results)
    successor_cost = sum(
        (Decimal(item.successor_estimated_cost_usd) for item in results),
        Decimal("0"),
    )
    successor_tokens = sum(item.successor_total_tokens for item in results)
    fresh_valid = terminal_counts["model_valid_trajectory"]
    fresh_invalid = terminal_counts["model_invalid_trajectory"]
    fresh_model = fresh_valid + fresh_invalid
    historical_cost = Decimal("0.14938994000000001406")
    values = {
        "source_replay_audit_id": prepared.source_replay.audit_id,
        "preexecution_audit_id": prepared.preexecution.audit_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "recovery_terminal_counts": dict(sorted(terminal_counts.items())),
        "successor_provider_call_count": sum(
            item.successor_provider_call_count for item in results
        ),
        "successor_http_success_call_count": sum(
            item.successor_http_success_call_count for item in results
        ),
        "successor_prompt_tokens": sum(item.successor_prompt_tokens for item in results),
        "successor_completion_tokens": sum(item.successor_completion_tokens for item in results),
        "successor_reasoning_tokens": sum(item.successor_reasoning_tokens for item in results),
        "successor_total_tokens": successor_tokens,
        "successor_estimated_cost_usd": format(successor_cost, "f"),
        "fresh_model_outcome_count": fresh_model,
        "fresh_valid_count": fresh_valid,
        "fresh_invalid_count": fresh_invalid,
        "combined_model_outcome_count": 22 + fresh_model,
        "combined_valid_count": 11 + fresh_valid,
        "combined_invalid_count": 11 + fresh_invalid,
        "exact_32_model_endpoint_denominator_complete": fresh_model == 10,
        "combined_observable_billing_tokens_lower_bound": 802956 + successor_tokens,
        "combined_observable_cost_usd_lower_bound": format(historical_cost + successor_cost, "f"),
    }
    provisional = RecoveryExecutionReport.model_construct(report_id="pending", **values)
    return RecoveryExecutionReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_transport_recovery_execution_report:",
        ),
        **values,
    )


def _write_checkpoint(path: Path, rows: Sequence[RecoveryJobResult]) -> None:
    payload = b"\n".join(_canonical_bytes(item.model_dump(mode="json")) for item in rows)
    if payload:
        payload += b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedExecution,
    output_dir: Path,
) -> tuple[RecoveryJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        RecoveryJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.recovery_job_id: item for item in prepared.recovery_manifest.jobs}
    if len({item.recovery_job_id for item in rows}) != len(rows):
        raise ValueError("v26.127 checkpoint contains duplicate RecoveryJobs")
    for result in rows:
        job = jobs.get(result.recovery_job_id)
        if job is None or result.recovery_runner_contract_id != EXPECTED_RECOVERY_RUNNER_ID:
            raise ValueError("v26.127 checkpoint crosses the frozen denominator")
        raw_path = recovery.recovery_raw_path(output_dir, job)
        if (
            not raw_path.is_file()
            or legacy.sha256_file(raw_path) != result.raw_execution_artifact.sha256
            or raw_path.stat().st_size != result.raw_execution_artifact.byte_count
        ):
            raise ValueError("v26.127 checkpoint Raw binding changed")
    return rows


ClientFactory = Callable[
    [AgentModelConfig, recovery.ExactFailedCallRecoveryJob, Any],
    Any,
]


def _default_client_factory(
    config: AgentModelConfig,
    _job: recovery.ExactFailedCallRecoveryJob,
    _binding: Any,
) -> Any:
    return StageOneProspectiveThinkingJsonClient(config)


def _run_one_job(
    *,
    job: recovery.ExactFailedCallRecoveryJob,
    prepared: PreparedExecution,
    historical_execution_dir: Path,
    client_factory: ClientFactory | None,
    output_dir: Path,
) -> tuple[RecoveryJobResult, recovery.RecoveryRawExecution]:
    binding = recovery.historical_runner.privacy_first_runtime_binding(
        prepared.static, job.historical_job
    )
    client = (
        None
        if client_factory is None
        else client_factory(prepared.static.agent_model_config, job, binding)
    )
    raw = recovery.execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=historical_execution_dir,
        client=client,
        output_dir=output_dir,
    )
    result = _project_job_result(raw=raw, prepared=prepared, output_dir=output_dir)
    return result, raw


def run_recovery_execution(
    *,
    preflight_dir: Path,
    historical_execution_dir: Path,
    output_dir: Path,
    package_root: Path,
    implementation_root: Path,
    workers: int,
    client_factory: ClientFactory = _default_client_factory,
) -> RecoveryExecutionReport:
    prepared = prepare_execution(
        preflight_dir=preflight_dir,
        historical_execution_dir=historical_execution_dir,
        output_dir=output_dir,
        package_root=package_root,
        implementation_root=implementation_root,
    )
    checkpoint_path = output_dir / "recovery_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.recovery_job_id: item for item in existing}
    jobs = prepared.recovery_manifest.jobs
    pending = [item for item in jobs if item.recovery_job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.127 completed report exists while RecoveryJobs remain pending")
    if not pending and report_path.exists():
        report = RecoveryExecutionReport.model_validate(_load(report_path))
        if (
            report.recovery_runner_contract_id != prepared.runner_contract.runner_contract_id
            or report.source_replay_audit_id != prepared.source_replay.audit_id
        ):
            raise ValueError("v26.127 completed report crosses frozen bindings")
        return report
    raw_recovery_jobs = [
        item for item in pending if recovery.recovery_raw_path(output_dir, item).exists()
    ]
    model_pending_jobs = [
        item for item in pending if not recovery.recovery_raw_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        recovery._assert_no_recovery_orphans(output_dir, job)
    print(
        f"[v26.127] resuming {len(completed)}/10; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} RecoveryJobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, recovery.RecoveryRawExecution] = {}
    for job in jobs:
        path = recovery.recovery_raw_path(output_dir, job)
        if path.exists() and job.recovery_job_id in completed:
            raw_by_job[job.recovery_job_id] = recovery.RecoveryRawExecution.model_validate(
                _load(path)
            )
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                historical_execution_dir=historical_execution_dir,
                client_factory=(None if job in raw_recovery_jobs else client_factory),
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            result, raw = future.result()
            with lock:
                completed[job.recovery_job_id] = result
                raw_by_job[job.recovery_job_id] = raw
                ordered = tuple(
                    completed[item.recovery_job_id]
                    for item in jobs
                    if item.recovery_job_id in completed
                )
                _write_checkpoint(checkpoint_path, ordered)
                print(
                    f"[v26.127] completed {len(completed)}/10 "
                    f"{job.recovery_job_id.rsplit(':', 1)[-1][:12]} "
                    f"terminal={result.terminal_category} "
                    f"final_abi={result.final_abi_crossed} "
                    f"successor_calls={result.successor_provider_call_count}",
                    flush=True,
                )
    results = tuple(completed[item.recovery_job_id] for item in jobs)
    if len(results) != 10:
        raise ValueError("v26.127 RecoveryJob denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(
            job.recovery_job_id,
            recovery.RecoveryRawExecution.model_validate(
                _load(recovery.recovery_raw_path(output_dir, job))
            ),
        )
    raws = tuple(raw_by_job[item.recovery_job_id] for item in jobs)
    lineage = build_raw_lineage_audit(raws=raws, output_dir=output_dir)
    report = _make_execution_report(
        prepared=prepared,
        results=results,
        lineage=lineage,
    )
    recovery._write_json_atomic(
        output_dir / "recovery_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    recovery._write_json_atomic(
        output_dir / "raw_lineage_audit.json", lineage.model_dump(mode="json")
    )
    recovery._write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Run the exact v26.127 failed-call Transport Recovery denominator"
    )
    parser.add_argument("--preflight-dir", type=Path, default=package_default / PREFLIGHT_DIR)
    parser.add_argument(
        "--historical-execution-dir",
        type=Path,
        default=package_default / recovery.HISTORICAL_EXECUTION_DIR,
    )
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_execution(
            preflight_dir=args.preflight_dir,
            historical_execution_dir=args.historical_execution_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
            implementation_root=args.implementation_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "source_replay_audit_id": prepared.source_replay.audit_id,
                    "recovery_runner_contract_id": (prepared.runner_contract.runner_contract_id),
                    "preexecution_audit_id": prepared.preexecution.audit_id,
                    "expected_recovery_jobs": len(prepared.recovery_manifest.jobs),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                    "stage_two_provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_recovery_execution(
        preflight_dir=args.preflight_dir,
        historical_execution_dir=args.historical_execution_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
