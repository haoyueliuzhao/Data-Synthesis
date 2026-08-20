from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.executable_task import (
    matching_sufficient_support_set,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingReplayResult,
    replay_authority_preserving_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_recovery import (  # noqa: E501
    FAILED_EXECUTION_BINDING_ID,
    FAILED_EXPOSED_JOB_COUNT,
    FAILED_PROVIDER_CALL_COUNT,
    RECOVERY_IMPLEMENTATION_SOURCE_PATHS,
    UNOPENED_CONTINUATION_JOB_COUNT,
    BudgetRecoveryContract,
    BudgetRecoveryManifest,
    BudgetRecoveryPreflightReport,
    BudgetRecoveryRawExecution,
    BudgetRecoveryReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification import (  # noqa: E501
    EXPECTED_JOB_COUNT,
    BudgetClosedInstrumentRollout,
    BudgetClosedRawProviderCall,
    _provider_telemetry_equal_before_host_augmentation,
    provider_call_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    evaluate_mechanism_estimand,
    failure_artifact_mechanism_estimand,
    match_empirical_program,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    ImplementationSourceFile,
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation

EXPECTED_RECOVERY_PREFLIGHT_ID = (
    "finance_v26_budget_recovery_preflight:"
    "f3e1af83b0b380fd14602417fd3770df7e92a532a4196fb4651bc0ab1d6ad964"
)
EXPECTED_RECOVERY_CONTRACT_ID = (
    "finance_v26_budget_recovery_contract:"
    "5b3f9efe759d22b1159a3a854a3bb3f6628d80645c833e9c7c43d043ec15730f"
)
EXPECTED_RECOVERY_MANIFEST_ID = (
    "finance_v26_budget_recovery_manifest:"
    "19876887f71863af1152aa43ea9eda599a18baf3c468710b0c171b489164d3ee"
)
EXPECTED_RECOVERY_BINDING_ID = (
    "finance_v26_budget_recovery_execution_binding:"
    "69de2b9a62ae0e478a79247ee2eb6d8c09706e43c87b37d59ddd59d8f6b8de8c"
)
EXPECTED_RECOVERY_REPORT_ID = (
    "finance_v26_budget_recovery_report:"
    "4afbad8525b598269630912e79048490dbe4e3235d8789aad0f10b922798c4ea"
)
EXPECTED_TOTAL_PROVIDER_CALL_COUNT: Literal[241] = 241
EXPECTED_TOTAL_PROVIDER_TOKENS: Literal[2204169] = 2_204_169
EXPECTED_TOTAL_ESTIMATED_COST_USD = "0.268686852000000027363"
EXPECTED_CONTINUATION_PROVIDER_CALL_COUNT: Literal[89] = 89
EXPECTED_CONTINUATION_PROVIDER_TOKENS: Literal[823541] = 823_541
EXPECTED_CONTINUATION_ESTIMATED_COST_USD = "0.093130273600000008853"
EXPECTED_NO_CALL_COUNT: Literal[24] = 24
EXPECTED_MODEL_INVALID_COUNT: Literal[8] = 8

V26_BUDGET_POSTRUN_SOURCE_VERSION = "finance_v26_budget_postrun_source_replay.v1"
V26_BUDGET_POSTRUN_LINEAGE_VERSION = "finance_v26_budget_postrun_provider_lineage.v1"
V26_BUDGET_POSTRUN_TERMINAL_ROW_VERSION = "finance_v26_budget_postrun_terminal_row.v1"
V26_BUDGET_POSTRUN_TERMINAL_VERSION = "finance_v26_budget_postrun_terminal_audit.v1"
V26_BUDGET_POSTRUN_VERIFIER_ROW_VERSION = "finance_v26_budget_postrun_verifier_row.v1"
V26_BUDGET_POSTRUN_VERIFIER_VERSION = "finance_v26_budget_postrun_verifier_audit.v1"
V26_BUDGET_POSTRUN_AGGREGATE_VERSION = "finance_v26_budget_postrun_aggregate.v1"
V26_BUDGET_POSTRUN_REPORT_VERSION = "finance_v26_budget_postrun_audit_report.v1"

AUDIT_MODULE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_budget_closed_instrument_postrun_audit.py"
)
AUDIT_IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted({*RECOVERY_IMPLEMENTATION_SOURCE_PATHS, AUDIT_MODULE_PATH})
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BudgetPostrunSourceEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "recovery_preflight_source",
        "failed_execution_artifact",
        "recovery_execution_artifact",
        "postrun_implementation",
    ]
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> BudgetPostrunSourceEntry:
        if self.expected_sha256 != self.observed_sha256:
            raise ValueError("budget post-run source bytes changed")
        return self


class BudgetPostrunSourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_preflight_report_id: str = EXPECTED_RECOVERY_PREFLIGHT_ID
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    entries: tuple[BudgetPostrunSourceEntry, ...] = Field(min_length=1)
    replayed_file_count: int = Field(ge=1)
    replay_pass_count: int = Field(ge=1)
    source_replay_before_any_aggregate_reconstruction: Literal[True] = True
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_POSTRUN_SOURCE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetPostrunSourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("budget post-run source paths are not canonical")
        if self.replayed_file_count != len(self.entries) or (
            self.replay_pass_count != self.replayed_file_count
        ):
            raise ValueError("budget post-run source denominator changed")
        if self.audit_id != budget_postrun_source_audit_id(self):
            raise ValueError("budget post-run source audit identity is invalid")
        return self


class BudgetPostrunProviderLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_execution_binding_id: str = EXPECTED_RECOVERY_BINDING_ID
    observed_raw_execution_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_canonical_byte_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_execution_binding_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    zero_generation_replay_job_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    continuation_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    original_provider_artifact_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    continuation_provider_artifact_count: Literal[89] = EXPECTED_CONTINUATION_PROVIDER_CALL_COUNT
    total_provider_artifact_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    original_provider_exact_byte_pass_count: Literal[152] = FAILED_PROVIDER_CALL_COUNT
    provider_artifact_canonical_byte_pass_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_binding_pass_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_prompt_hash_pass_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_host_telemetry_pass_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_call_ids_unique: Literal[True] = True
    duplicate_provider_call_ids: tuple[str, ...] = ()
    lineage_failure_ids: tuple[str, ...] = ()
    historical_raw_lineage_audit_id: str = Field(min_length=1)
    historical_raw_lineage_status: Literal["passed"] = "passed"
    independently_reconstructed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_POSTRUN_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetPostrunProviderLineageAudit:
        if self.total_provider_artifact_count != (
            self.original_provider_artifact_count + self.continuation_provider_artifact_count
        ):
            raise ValueError("budget post-run Provider denominator changed")
        if self.audit_id != budget_postrun_lineage_audit_id(self):
            raise ValueError("budget post-run lineage identity is invalid")
        return self


class BudgetPostrunTerminalRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    recovery_role: Literal["zero_generation_replay", "unopened_model_continuation"]
    terminal_category: Literal["budget_exhausted_no_call", "model_invalid_trajectory"]
    core_terminal: Literal["model_invalid_resource_terminal", "invalid_trajectory"]
    provider_call_count: int = Field(ge=1)
    provider_total_tokens: int = Field(ge=1, le=120000)
    estimated_cost_usd: str = Field(min_length=1)
    certificate_count: int = Field(ge=1)
    permitted_request_count: int = Field(ge=1)
    denied_no_call_count: int = Field(ge=0, le=1)
    attempted_prompt_count: int = Field(ge=1)
    post_terminal_short_circuit_prompt_count: int = Field(ge=0, le=1)
    no_call_reason: str | None = None
    no_call_phase: str | None = None
    exact_model_identity: Literal[True] = True
    fallback_absent: Literal[True] = True
    successful_usage_complete: Literal[True] = True
    certificate_attempt_prefix_passed: Literal[True] = True
    permitted_certificate_provider_prompt_passed: Literal[True] = True
    usage_certificate_binding_passed: Literal[True] = True
    terminal_classification_reproduced: Literal[True] = True
    per_rollout_resource_gate_passed: Literal[True] = True
    schema_version: str = V26_BUDGET_POSTRUN_TERMINAL_ROW_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> BudgetPostrunTerminalRow:
        if self.provider_call_count != self.permitted_request_count:
            raise ValueError("budget post-run row Provider denominator changed")
        no_call = self.terminal_category == "budget_exhausted_no_call"
        if no_call:
            if (
                self.core_terminal != "model_invalid_resource_terminal"
                or self.denied_no_call_count != 1
                or self.certificate_count != self.provider_call_count + 1
                or self.attempted_prompt_count != self.certificate_count + 1
                or self.post_terminal_short_circuit_prompt_count != 1
                or self.no_call_reason is None
                or self.no_call_phase != "mid_rollout_budget_exhausted"
            ):
                raise ValueError("budget post-run typed no-call row changed")
        elif (
            self.core_terminal != "invalid_trajectory"
            or self.denied_no_call_count != 0
            or self.certificate_count != self.provider_call_count
            or self.attempted_prompt_count != self.certificate_count
            or self.post_terminal_short_circuit_prompt_count != 0
            or self.no_call_reason is not None
            or self.no_call_phase is not None
        ):
            raise ValueError("budget post-run model-invalid row changed")
        if self.row_id != budget_postrun_terminal_row_id(self):
            raise ValueError("budget post-run terminal row identity is invalid")
        return self


class BudgetPostrunTerminalAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[BudgetPostrunTerminalRow, ...] = Field(min_length=32, max_length=32)
    observed_job_count: Literal[32] = EXPECTED_JOB_COUNT
    typed_no_call_count: Literal[24] = EXPECTED_NO_CALL_COUNT
    model_invalid_trajectory_count: Literal[8] = EXPECTED_MODEL_INVALID_COUNT
    completed_trajectory_count: Literal[0] = 0
    runtime_failure_count: Literal[0] = 0
    instrument_failure_count: Literal[0] = 0
    provider_call_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_total_tokens: Literal[2204169] = EXPECTED_TOTAL_PROVIDER_TOKENS
    estimated_cost_usd: str = EXPECTED_TOTAL_ESTIMATED_COST_USD
    maximum_rollout_provider_tokens: int = Field(ge=1, le=120000)
    per_rollout_token_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    successful_usage_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    exact_model_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    fallback_count: Literal[0] = 0
    post_terminal_short_circuit_prompt_count: Literal[24] = EXPECTED_NO_CALL_COUNT
    aggregate_cost_gate_passed: Literal[True] = True
    all_budget_and_terminal_checks_passed: Literal[True] = True
    independently_reconstructed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_POSTRUN_TERMINAL_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetPostrunTerminalAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("budget post-run terminal rows are not canonical")
        if self.provider_call_count != sum(item.provider_call_count for item in self.rows):
            raise ValueError("budget post-run terminal call total changed")
        if self.provider_total_tokens != sum(item.provider_total_tokens for item in self.rows):
            raise ValueError("budget post-run terminal token total changed")
        if Decimal(self.estimated_cost_usd) != sum(
            (Decimal(item.estimated_cost_usd) for item in self.rows), Decimal("0")
        ):
            raise ValueError("budget post-run terminal cost total changed")
        if self.audit_id != budget_postrun_terminal_audit_id(self):
            raise ValueError("budget post-run terminal audit identity is invalid")
        return self


class BudgetPostrunVerifierRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    replay_result_id: str = Field(min_length=1)
    replay_passed: Literal[True] = True
    replay_result_exact_match: Literal[True] = True
    non_replay_checks: dict[str, bool]
    non_replay_gate_exact_match: Literal[True] = True
    mechanism_success: bool
    mechanism_result_exact_match: Literal[True] = True
    terminal_category: Literal["budget_exhausted_no_call", "model_invalid_trajectory"]
    terminal_reproduced: Literal[True] = True
    instrument_failure_channels_empty: Literal[True] = True
    report_failure_channels_empty: Literal[True] = True
    instrument_admitted: Literal[True] = True
    independently_reconstructed: Literal[True] = True
    schema_version: str = V26_BUDGET_POSTRUN_VERIFIER_ROW_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> BudgetPostrunVerifierRow:
        if self.row_id != budget_postrun_verifier_row_id(self):
            raise ValueError("budget post-run Verifier row identity is invalid")
        return self


class BudgetPostrunVerifierAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[BudgetPostrunVerifierRow, ...] = Field(min_length=32, max_length=32)
    observed_job_count: Literal[32] = EXPECTED_JOB_COUNT
    replay_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    replay_failure_count: Literal[0] = 0
    non_replay_gate_reconstruction_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    mechanism_reconstruction_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    terminal_reconstruction_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    instrument_admitted_count: Literal[32] = EXPECTED_JOB_COUNT
    completed_trajectory_count: Literal[0] = 0
    completed_shared_score_count: Literal[0] = 0
    independently_valid_trajectory_count: Literal[0] = 0
    state_mapping_permitted_count: Literal[0] = 0
    independently_reconstructed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_POSTRUN_VERIFIER_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetPostrunVerifierAudit:
        if tuple(item.job_id for item in self.rows) != tuple(
            sorted(item.job_id for item in self.rows)
        ):
            raise ValueError("budget post-run Verifier rows are not canonical")
        if self.audit_id != budget_postrun_verifier_audit_id(self):
            raise ValueError("budget post-run Verifier audit identity is invalid")
        return self


class BudgetPostrunAggregateReconstruction(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    completed_rollout_count: Literal[32] = EXPECTED_JOB_COUNT
    terminal_counts: dict[str, int]
    core_terminal_counts: dict[str, int]
    provider_call_count: Literal[241] = EXPECTED_TOTAL_PROVIDER_CALL_COUNT
    provider_total_tokens: Literal[2204169] = EXPECTED_TOTAL_PROVIDER_TOKENS
    estimated_cost_usd: str = EXPECTED_TOTAL_ESTIMATED_COST_USD
    zero_generation_replayed_job_count: Literal[20] = FAILED_EXPOSED_JOB_COUNT
    continuation_job_count: Literal[12] = UNOPENED_CONTINUATION_JOB_COUNT
    replay_pass_count: Literal[32] = EXPECTED_JOB_COUNT
    independent_non_replay_audit_count: Literal[32] = EXPECTED_JOB_COUNT
    instrument_admitted_count: Literal[32] = EXPECTED_JOB_COUNT
    raw_lineage_passed: Literal[True] = True
    resource_budget_passed: Literal[True] = True
    recovery_instrument_ready: Literal[True] = True
    historical_report_vector_exact_match: Literal[True] = True
    mismatch_fields: tuple[str, ...] = ()
    next_permitted_stage: Literal["fresh_capability_and_reachability_protocol_design_only"] = (
        "fresh_capability_and_reachability_protocol_design_only"
    )
    independently_reconstructed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_BUDGET_POSTRUN_AGGREGATE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BudgetPostrunAggregateReconstruction:
        if self.audit_id != budget_postrun_aggregate_audit_id(self):
            raise ValueError("budget post-run aggregate identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class BudgetPostrunAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    recovery_report_id: str = EXPECTED_RECOVERY_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    provider_lineage_audit_id: str = Field(min_length=1)
    budget_terminal_audit_id: str = Field(min_length=1)
    verifier_scoring_audit_id: str = Field(min_length=1)
    aggregate_reconstruction_audit_id: str = Field(min_length=1)
    immutable_detail_files: tuple[DetailFile, ...] = Field(min_length=5, max_length=5)
    model_client_constructed: Literal[False] = False
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    recovery_instrument_retained: Literal[True] = True
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal["fresh_capability_and_reachability_protocol_design_only"] = (
        "fresh_capability_and_reachability_protocol_design_only"
    )
    capability_development_execution_authorized: Literal[False] = False
    state_reachability_execution_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_BUDGET_POSTRUN_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BudgetPostrunAuditReport:
        names = tuple(item.relative_path for item in self.immutable_detail_files)
        if names != tuple(sorted(set(names))):
            raise ValueError("budget post-run detail files are not canonical")
        if self.report_id != budget_postrun_report_id(self):
            raise ValueError("budget post-run report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"immutable budget post-run JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def _relative_to_package(path: Path, package_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(package_root.resolve()))
    except ValueError as exc:
        raise ValueError(f"budget post-run source escapes package root: {path}") from exc


def _canonical_json_payload(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError(f"raw Artifact is not canonical JSON: {path}")
    if not isinstance(payload, dict):
        raise ValueError(f"raw Artifact is not a JSON object: {path}")
    return payload


def _load_rows(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list: {path}")
    return tuple(model.model_validate(item) for item in payload)


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=relative,
            sha256=_sha256(package_root / relative),
        )
        for relative in AUDIT_IMPLEMENTATION_SOURCE_PATHS
    )


def _build_source_replay(
    *,
    failed_run_dir: Path,
    recovery_preflight_dir: Path,
    recovery_dir: Path,
    package_root: Path,
) -> BudgetPostrunSourceReplayAudit:
    frozen = json.loads(
        (recovery_preflight_dir / "recovery_source_replay_audit.json").read_text(encoding="utf-8")
    )
    if frozen.get("status") != "passed" or not isinstance(frozen.get("entries"), list):
        raise ValueError("budget post-run received another preflight source audit")
    expected: dict[str, tuple[str, str]] = {}

    def register(relative: str, sha256: str, kind: str) -> None:
        prior = expected.get(relative)
        if prior is not None and prior[0] != sha256:
            raise ValueError(f"budget post-run source manifests disagree: {relative}")
        expected[relative] = prior or (sha256, kind)

    for item in frozen["entries"]:
        register(
            str(item["relative_path"]),
            str(item["expected_sha256"]),
            "recovery_preflight_source",
        )
    for root, kind in (
        (failed_run_dir, "failed_execution_artifact"),
        (recovery_preflight_dir, "recovery_preflight_source"),
        (recovery_dir, "recovery_execution_artifact"),
    ):
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            register(_relative_to_package(path, package_root), _sha256(path), kind)
    for descriptor in _implementation_sources(package_root):
        register(
            descriptor.relative_path,
            descriptor.sha256,
            "postrun_implementation",
        )
    entries = tuple(
        BudgetPostrunSourceEntry(
            relative_path=relative,
            expected_sha256=expected_sha,
            observed_sha256=_sha256(package_root / relative),
            byte_count=(package_root / relative).stat().st_size,
            source_kind=cast(Any, kind),
        )
        for relative, (expected_sha, kind) in sorted(expected.items())
    )
    values = {
        "entries": entries,
        "replayed_file_count": len(entries),
        "replay_pass_count": len(entries),
    }
    provisional = BudgetPostrunSourceReplayAudit.model_construct(audit_id="pending", **values)
    return BudgetPostrunSourceReplayAudit(
        audit_id=budget_postrun_source_audit_id(provisional), **values
    )


def _build_lineage_audit(
    *,
    failed_run_dir: Path,
    recovery_dir: Path,
    recovery_manifest: BudgetRecoveryManifest,
    recovery_report: BudgetRecoveryReport,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
) -> BudgetPostrunProviderLineageAudit:
    role_by_job = {item.original_job.job_id: item.recovery_role for item in recovery_manifest.jobs}
    raw_canonical = raw_binding = replay_jobs = continuation_jobs = 0
    original_count = continuation_count = original_exact = 0
    provider_canonical = provider_binding = prompt_hash_pass = telemetry_pass = 0
    provider_ids: list[str] = []
    failures: list[str] = []
    for rollout in rollouts:
        try:
            raw_path = Path(rollout.raw_execution_artifact_uri)
            payload = _canonical_json_payload(raw_path)
            raw = BudgetRecoveryRawExecution.model_validate(payload)
            raw_canonical += 1
            role = role_by_job[rollout.job_id]
            if (
                raw.recovery_execution_binding_id != EXPECTED_RECOVERY_BINDING_ID
                or raw.recovery_role != role
                or raw.job.job_id != rollout.job_id
                or _sha256(raw_path) != rollout.raw_execution_artifact_sha256
            ):
                raise ValueError("independent raw execution binding mismatch")
            raw_binding += 1
            replay = role == "zero_generation_replay"
            replay_jobs += int(replay)
            continuation_jobs += int(not replay)
            expected_binding = (
                FAILED_EXECUTION_BINDING_ID if replay else EXPECTED_RECOVERY_BINDING_ID
            )
            for index, descriptor in enumerate(raw.provider_call_artifacts):
                path = recovery_dir / descriptor.relative_path
                artifact_payload = _canonical_json_payload(path)
                artifact = BudgetClosedRawProviderCall.model_validate(artifact_payload)
                provider_canonical += 1
                expected_id = provider_call_id(rollout.job_id, index, artifact.provider_telemetry)
                if (
                    _sha256(path) != descriptor.sha256
                    or path.stat().st_size != descriptor.byte_count
                    or artifact.execution_binding_id != expected_binding
                    or artifact.job_id != rollout.job_id
                    or artifact.call_index != index
                    or artifact.provider_call_id != expected_id
                    or artifact.provider_call_id != rollout.provider_call_ids[index]
                ):
                    raise ValueError("independent Provider Artifact binding mismatch")
                provider_binding += 1
                if (
                    artifact.prompt_sha256 != _sha256_text(artifact.prompt)
                    or artifact.prompt != raw.provider_request_prompts[index]
                    or artifact.provider_telemetry.request_hash != artifact.prompt_sha256
                ):
                    raise ValueError("independent Provider Prompt hash mismatch")
                prompt_hash_pass += 1
                if (
                    not _provider_telemetry_equal_before_host_augmentation(
                        artifact.provider_telemetry, raw.host_telemetry[index]
                    )
                    or artifact.provider_telemetry != raw.provider_telemetry[index]
                ):
                    raise ValueError("independent Provider telemetry mismatch")
                telemetry_pass += 1
                if replay:
                    original_path = failed_run_dir / descriptor.relative_path
                    if original_path.read_bytes() != path.read_bytes():
                        raise ValueError("original Provider bytes changed in Recovery")
                    original_count += 1
                    original_exact += 1
                else:
                    continuation_count += 1
                provider_ids.append(artifact.provider_call_id)
            if len(raw.provider_call_ids) != rollout.provider_call_count:
                raise ValueError("independent raw Provider denominator mismatch")
        except Exception as exc:
            failures.append(
                canonical_hash(
                    {"job_id": rollout.job_id, "error": f"{type(exc).__name__}:{exc}"},
                    prefix="finance_v26_budget_postrun_lineage_failure:",
                )
            )
    duplicates = tuple(sorted(key for key, count in Counter(provider_ids).items() if count > 1))
    if failures:
        raise ValueError(f"budget post-run lineage failures: {failures}")
    values = {
        "raw_execution_canonical_byte_pass_count": raw_canonical,
        "raw_execution_binding_pass_count": raw_binding,
        "zero_generation_replay_job_count": replay_jobs,
        "continuation_job_count": continuation_jobs,
        "original_provider_artifact_count": original_count,
        "continuation_provider_artifact_count": continuation_count,
        "total_provider_artifact_count": len(provider_ids),
        "original_provider_exact_byte_pass_count": original_exact,
        "provider_artifact_canonical_byte_pass_count": provider_canonical,
        "provider_binding_pass_count": provider_binding,
        "provider_prompt_hash_pass_count": prompt_hash_pass,
        "provider_host_telemetry_pass_count": telemetry_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "lineage_failure_ids": tuple(failures),
        "historical_raw_lineage_audit_id": recovery_report.raw_lineage_audit.audit_id,
        "historical_raw_lineage_status": recovery_report.raw_lineage_audit.status,
    }
    provisional = BudgetPostrunProviderLineageAudit.model_construct(audit_id="pending", **values)
    return BudgetPostrunProviderLineageAudit(
        audit_id=budget_postrun_lineage_audit_id(provisional), **values
    )


def _usage_complete(telemetry: ModelCallTelemetry) -> bool:
    return bool(
        telemetry.http_success
        and telemetry.prompt_tokens is not None
        and telemetry.completion_tokens is not None
        and telemetry.total_tokens is not None
        and telemetry.prompt_tokens + telemetry.completion_tokens == telemetry.total_tokens
        and (
            telemetry.prompt_cache_hit_tokens is None
            and telemetry.prompt_cache_miss_tokens is None
            or telemetry.prompt_cache_hit_tokens is not None
            and telemetry.prompt_cache_miss_tokens is not None
            and telemetry.prompt_cache_hit_tokens + telemetry.prompt_cache_miss_tokens
            == telemetry.prompt_tokens
        )
    )


def _build_terminal_audit(
    *,
    recovery_manifest: BudgetRecoveryManifest,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
) -> BudgetPostrunTerminalAudit:
    role_by_job = {item.original_job.job_id: item.recovery_role for item in recovery_manifest.jobs}
    rows: list[BudgetPostrunTerminalRow] = []
    for rollout in rollouts:
        raw = BudgetRecoveryRawExecution.model_validate(
            _canonical_json_payload(Path(rollout.raw_execution_artifact_uri))
        )
        audit = raw.provider_budget_audit
        certificates = audit.certificates
        permitted = tuple(item for item in certificates if item.provider_call_permitted)
        provider_hashes = tuple(_sha256_text(item) for item in raw.provider_request_prompts)
        attempt_hashes = tuple(_sha256_text(item) for item in raw.attempted_model_prompts)
        total_tokens = sum(item.total_tokens or 0 for item in raw.provider_telemetry)
        estimated_cost = sum(
            (Decimal(str(item.estimated_cost or 0)) for item in raw.provider_telemetry),
            Decimal("0"),
        )
        exact_model = all(
            item.model_requested == "deepseek-v4-flash"
            and item.model_selected == "deepseek-v4-flash"
            and item.response_model == "deepseek-v4-flash"
            and item.http_success
            for item in raw.provider_telemetry
        )
        usage_complete = bool(
            all(_usage_complete(item) for item in raw.provider_telemetry)
            and audit.cumulative_provider_tokens == total_tokens
            and audit.provider_call_count == len(raw.provider_telemetry)
            and all(item.passed for item in audit.usage_records)
        )
        certificate_prefix = (
            tuple(item.request_hash for item in certificates)
            == (attempt_hashes[: len(certificates)])
        )
        permitted_match = tuple(item.request_hash for item in permitted) == provider_hashes
        usage_match = tuple(item.certificate_id for item in permitted) == tuple(
            item.certificate_id for item in audit.usage_records
        )
        no_call = audit.no_call_terminal is not None
        terminal = "budget_exhausted_no_call" if no_call else "model_invalid_trajectory"
        core = "model_invalid_resource_terminal" if no_call else "invalid_trajectory"
        expected_phase = "mid_rollout_budget_exhausted" if no_call else None
        terminal_match = bool(
            raw.solve_result is None
            and raw.failure_artifact is not None
            and rollout.terminal_category == terminal
            and rollout.core_terminal == core
            and rollout.no_call_terminal == audit.no_call_terminal
            and rollout.no_call_phase == expected_phase
        )
        resource_pass = bool(
            total_tokens <= 120000
            and audit.status == "passed"
            and usage_complete
            and not audit.contract_failure_ids
            and all(
                usage.total_tokens is not None
                and usage.total_tokens <= certificate.request_token_upper_bound
                and usage.prompt_tokens is not None
                and usage.prompt_tokens <= certificate.prompt_token_upper_bound
                and usage.completion_tokens is not None
                and usage.completion_tokens <= certificate.completion_token_upper_bound
                for certificate, usage in zip(permitted, audit.usage_records, strict=True)
            )
        )
        values = {
            "job_id": rollout.job_id,
            "recovery_role": role_by_job[rollout.job_id],
            "terminal_category": terminal,
            "core_terminal": core,
            "provider_call_count": len(raw.provider_telemetry),
            "provider_total_tokens": total_tokens,
            "estimated_cost_usd": str(estimated_cost),
            "certificate_count": len(certificates),
            "permitted_request_count": audit.permitted_request_count,
            "denied_no_call_count": audit.denied_no_call_count,
            "attempted_prompt_count": len(raw.attempted_model_prompts),
            "post_terminal_short_circuit_prompt_count": len(
                raw.post_terminal_short_circuit_prompts
            ),
            "no_call_reason": (
                audit.no_call_terminal.reason_code if audit.no_call_terminal else None
            ),
            "no_call_phase": expected_phase,
            "exact_model_identity": exact_model,
            "fallback_absent": not any(item.fallback_used for item in raw.provider_telemetry),
            "successful_usage_complete": usage_complete,
            "certificate_attempt_prefix_passed": certificate_prefix,
            "permitted_certificate_provider_prompt_passed": permitted_match,
            "usage_certificate_binding_passed": usage_match,
            "terminal_classification_reproduced": terminal_match,
            "per_rollout_resource_gate_passed": resource_pass,
        }
        provisional = BudgetPostrunTerminalRow.model_construct(row_id="pending", **values)
        rows.append(
            BudgetPostrunTerminalRow(row_id=budget_postrun_terminal_row_id(provisional), **values)
        )
    ordered = tuple(sorted(rows, key=lambda item: item.job_id))
    total_cost = sum((Decimal(item.estimated_cost_usd) for item in ordered), Decimal("0"))
    values = {
        "rows": ordered,
        "typed_no_call_count": sum(
            item.terminal_category == "budget_exhausted_no_call" for item in ordered
        ),
        "model_invalid_trajectory_count": sum(
            item.terminal_category == "model_invalid_trajectory" for item in ordered
        ),
        "provider_call_count": sum(item.provider_call_count for item in ordered),
        "provider_total_tokens": sum(item.provider_total_tokens for item in ordered),
        "estimated_cost_usd": str(total_cost),
        "maximum_rollout_provider_tokens": max(item.provider_total_tokens for item in ordered),
        "per_rollout_token_pass_count": sum(
            item.per_rollout_resource_gate_passed for item in ordered
        ),
        "successful_usage_pass_count": sum(item.successful_usage_complete for item in ordered),
        "exact_model_pass_count": sum(item.exact_model_identity for item in ordered),
        "fallback_count": sum(not item.fallback_absent for item in ordered),
        "post_terminal_short_circuit_prompt_count": sum(
            item.post_terminal_short_circuit_prompt_count for item in ordered
        ),
        "aggregate_cost_gate_passed": total_cost <= Decimal("2.0"),
        "all_budget_and_terminal_checks_passed": all(
            item.certificate_attempt_prefix_passed
            and item.permitted_certificate_provider_prompt_passed
            and item.usage_certificate_binding_passed
            and item.terminal_classification_reproduced
            and item.per_rollout_resource_gate_passed
            for item in ordered
        ),
    }
    provisional = BudgetPostrunTerminalAudit.model_construct(audit_id="pending", **values)
    return BudgetPostrunTerminalAudit(
        audit_id=budget_postrun_terminal_audit_id(provisional), **values
    )


def _observations(raw: BudgetRecoveryRawExecution) -> tuple[AgentToolObservation, ...]:
    if raw.solve_result is not None:
        return raw.solve_result.observations
    if raw.failure_artifact is not None:
        return raw.failure_artifact.observations
    return ()


def _independent_non_replay_checks(
    *,
    record: OperationalTaskRecord,
    raw: BudgetRecoveryRawExecution,
    replay: AuthorityPreservingReplayResult,
) -> tuple[dict[str, bool], Any]:
    observations = _observations(raw)
    program_complete, _, _, operation_lineage = match_empirical_program(record, observations)
    lattice = record.task_package.evidence_support_lattice
    selected_support = matching_sufficient_support_set(lattice, replay.selected_evidence_ids)
    citation_support = matching_sufficient_support_set(lattice, ())
    verification_support = tuple(
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
    no_postcompletion = first_verified is None or first_verified == len(observations) - 1
    necessary = set(lattice.necessary_evidence_ids)
    mechanism = (
        failure_artifact_mechanism_estimand(record, raw.failure_artifact)
        if raw.failure_artifact is not None
        else evaluate_mechanism_estimand(record, (), stopped_by_model=False)
    )
    checks = dict(
        sorted(
            {
                "model_input_noninterference_passed": (raw.recursive_noninterference_passed),
                "only_allowed_tools": {item.call.tool_id for item in observations}
                <= set(record.task_package.tool_closure.allowed_tool_ids),
                "operation_lineage_complete": program_complete
                and necessary <= set(operation_lineage),
                "evidence_support_complete": selected_support is not None,
                "verification_complete": necessary <= set(verification_support),
                "answer_projection_complete": ({} == record.projected_expected_output),
                "citation_complete": citation_support is not None,
                "mechanism_complete": mechanism.success,
                "no_postcompletion_violation": no_postcompletion,
            }.items()
        )
    )
    return checks, mechanism


def _build_verifier_audit(
    *,
    records: Sequence[OperationalTaskRecord],
    environments: Sequence[AgentToolEnvironmentManifest],
    replay_contract: AuthorityPreservingReplayContract,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
) -> BudgetPostrunVerifierAudit:
    record_by_id = {item.record_id: item for item in records}
    environment_by_id = {item.manifest_id: item for item in environments}
    rows: list[BudgetPostrunVerifierRow] = []
    for rollout in rollouts:
        raw = BudgetRecoveryRawExecution.model_validate(
            _canonical_json_payload(Path(rollout.raw_execution_artifact_uri))
        )
        record = record_by_id[rollout.task_record_id]
        environment = environment_by_id[rollout.environment_manifest_id]
        observations = _observations(raw)
        replay = replay_authority_preserving_observations(
            replay_contract,
            record,
            environment,
            observations,
        )
        if rollout.replay_result is None:
            raise ValueError("budget post-run rollout lost its Replay result")
        checks, mechanism = _independent_non_replay_checks(
            record=record,
            raw=raw,
            replay=replay,
        )
        non_replay = rollout.non_replay_gate_audit
        if non_replay is None:
            raise ValueError("budget post-run rollout lost its non-Replay audit")
        no_call = raw.provider_budget_audit.no_call_terminal is not None
        terminal = "budget_exhausted_no_call" if no_call else "model_invalid_trajectory"
        values = {
            "job_id": rollout.job_id,
            "task_package_id": rollout.task_package_id,
            "observation_count": len(observations),
            "replay_result_id": replay.replay_id,
            "replay_passed": replay.passed,
            "replay_result_exact_match": replay == rollout.replay_result,
            "non_replay_checks": checks,
            "non_replay_gate_exact_match": checks == non_replay.checks,
            "mechanism_success": mechanism.success,
            "mechanism_result_exact_match": mechanism == rollout.mechanism_estimand,
            "terminal_category": terminal,
            "terminal_reproduced": terminal == rollout.terminal_category,
            "instrument_failure_channels_empty": (rollout.failure_channels.instrument_gate_passed),
            "report_failure_channels_empty": (rollout.failure_channels.report_complete),
            "instrument_admitted": rollout.instrument_admitted,
        }
        provisional = BudgetPostrunVerifierRow.model_construct(row_id="pending", **values)
        rows.append(
            BudgetPostrunVerifierRow(row_id=budget_postrun_verifier_row_id(provisional), **values)
        )
    ordered = tuple(sorted(rows, key=lambda item: item.job_id))
    values = {
        "rows": ordered,
        "replay_pass_count": sum(item.replay_passed for item in ordered),
        "non_replay_gate_reconstruction_pass_count": sum(
            item.non_replay_gate_exact_match for item in ordered
        ),
        "mechanism_reconstruction_pass_count": sum(
            item.mechanism_result_exact_match for item in ordered
        ),
        "terminal_reconstruction_pass_count": sum(item.terminal_reproduced for item in ordered),
        "instrument_admitted_count": sum(item.instrument_admitted for item in ordered),
    }
    provisional = BudgetPostrunVerifierAudit.model_construct(audit_id="pending", **values)
    return BudgetPostrunVerifierAudit(
        audit_id=budget_postrun_verifier_audit_id(provisional), **values
    )


def _build_aggregate_reconstruction(
    *,
    recovery_report: BudgetRecoveryReport,
    lineage: BudgetPostrunProviderLineageAudit,
    terminal: BudgetPostrunTerminalAudit,
    verifier: BudgetPostrunVerifierAudit,
    rollouts: Sequence[BudgetClosedInstrumentRollout],
) -> BudgetPostrunAggregateReconstruction:
    observed: dict[str, Any] = {
        "completed_rollout_count": len(rollouts),
        "terminal_counts": dict(
            sorted(Counter(item.terminal_category for item in rollouts).items())
        ),
        "core_terminal_counts": dict(
            sorted(Counter(item.core_terminal for item in rollouts).items())
        ),
        "provider_call_count": terminal.provider_call_count,
        "provider_total_tokens": terminal.provider_total_tokens,
        "estimated_cost_usd": terminal.estimated_cost_usd,
        "zero_generation_replayed_job_count": lineage.zero_generation_replay_job_count,
        "continuation_job_count": lineage.continuation_job_count,
        "replay_pass_count": verifier.replay_pass_count,
        "independent_non_replay_audit_count": (verifier.non_replay_gate_reconstruction_pass_count),
        "instrument_admitted_count": verifier.instrument_admitted_count,
        "raw_lineage_passed": lineage.status == "passed",
        "resource_budget_passed": (
            terminal.status == "passed" and terminal.aggregate_cost_gate_passed
        ),
        "recovery_instrument_ready": bool(
            lineage.status == "passed"
            and terminal.status == "passed"
            and verifier.status == "passed"
            and verifier.instrument_admitted_count == EXPECTED_JOB_COUNT
        ),
        "next_permitted_stage": ("fresh_capability_and_reachability_protocol_design_only"),
    }
    historical: dict[str, Any] = {
        "completed_rollout_count": recovery_report.completed_rollout_count,
        "terminal_counts": recovery_report.terminal_counts,
        "core_terminal_counts": recovery_report.core_terminal_counts,
        "provider_call_count": recovery_report.total_provider_call_count,
        "provider_total_tokens": recovery_report.total_provider_tokens,
        "estimated_cost_usd": recovery_report.total_estimated_cost_usd,
        "zero_generation_replayed_job_count": (recovery_report.zero_generation_replayed_job_count),
        "continuation_job_count": recovery_report.continuation_model_job_count,
        "replay_pass_count": recovery_report.replay_pass_count,
        "independent_non_replay_audit_count": (recovery_report.independent_non_replay_audit_count),
        "instrument_admitted_count": sum(
            item.instrument_admitted for item in recovery_report.diagnostics
        ),
        "raw_lineage_passed": recovery_report.raw_lineage_audit.status == "passed",
        "resource_budget_passed": recovery_report.resource_budget_passed,
        "recovery_instrument_ready": recovery_report.recovery_instrument_ready,
        "next_permitted_stage": recovery_report.next_permitted_stage,
    }
    mismatch = tuple(sorted(key for key in observed if observed[key] != historical[key]))
    values = {
        **observed,
        "historical_report_vector_exact_match": not mismatch,
        "mismatch_fields": mismatch,
    }
    provisional = BudgetPostrunAggregateReconstruction.model_construct(audit_id="pending", **values)
    return BudgetPostrunAggregateReconstruction(
        audit_id=budget_postrun_aggregate_audit_id(provisional), **values
    )


def build_budget_closed_postrun_audit(
    *,
    failed_run_dir: Path,
    recovery_preflight_dir: Path,
    recovery_dir: Path,
    task_source_dir: Path,
    verifier_qualification_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> BudgetPostrunAuditReport:
    preflight = BudgetRecoveryPreflightReport.model_validate_json(
        (recovery_preflight_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = BudgetRecoveryContract.model_validate_json(
        (recovery_preflight_dir / "recovery_contract.json").read_text(encoding="utf-8")
    )
    manifest = BudgetRecoveryManifest.model_validate_json(
        (recovery_preflight_dir / "recovery_manifest.json").read_text(encoding="utf-8")
    )
    recovery_report = BudgetRecoveryReport.model_validate_json(
        (recovery_dir / "report.json").read_text(encoding="utf-8")
    )
    if (
        preflight.report_id != EXPECTED_RECOVERY_PREFLIGHT_ID
        or contract.contract_id != EXPECTED_RECOVERY_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_RECOVERY_MANIFEST_ID
        or recovery_report.report_id != EXPECTED_RECOVERY_REPORT_ID
        or recovery_report.recovery_execution_binding_id != EXPECTED_RECOVERY_BINDING_ID
    ):
        raise ValueError("budget post-run audit received another Recovery")
    frozen_contract = BudgetRecoveryContract.model_validate_json(
        (recovery_dir / "frozen_recovery_contract.json").read_text(encoding="utf-8")
    )
    frozen_manifest = BudgetRecoveryManifest.model_validate_json(
        (recovery_dir / "frozen_recovery_manifest.json").read_text(encoding="utf-8")
    )
    if frozen_contract != contract or frozen_manifest != manifest:
        raise ValueError("budget post-run Recovery inputs changed during execution")
    rollouts = cast(
        tuple[BudgetClosedInstrumentRollout, ...],
        _load_rows(recovery_dir / "rollout_aggregate.json", BudgetClosedInstrumentRollout),
    )
    if (
        len(rollouts) != EXPECTED_JOB_COUNT
        or len({item.job_id for item in rollouts}) != EXPECTED_JOB_COUNT
    ):
        raise ValueError("budget post-run Recovery denominator changed")
    checkpoint = tuple(
        BudgetClosedInstrumentRollout.model_validate_json(line)
        for line in (recovery_dir / "recovery_rollouts.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    if {item.rollout_id for item in checkpoint} != {item.rollout_id for item in rollouts}:
        raise ValueError("budget post-run checkpoint and aggregate differ")
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_rows(task_source_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_rows(
            task_source_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    replay_contract = AuthorityPreservingReplayContract.model_validate_json(
        (verifier_qualification_dir / "replay_contract.json").read_text(encoding="utf-8")
    )
    source = _build_source_replay(
        failed_run_dir=failed_run_dir,
        recovery_preflight_dir=recovery_preflight_dir,
        recovery_dir=recovery_dir,
        package_root=package_root,
    )
    lineage = _build_lineage_audit(
        failed_run_dir=failed_run_dir,
        recovery_dir=recovery_dir,
        recovery_manifest=manifest,
        recovery_report=recovery_report,
        rollouts=rollouts,
    )
    terminal = _build_terminal_audit(
        recovery_manifest=manifest,
        rollouts=rollouts,
    )
    verifier = _build_verifier_audit(
        records=records,
        environments=environments,
        replay_contract=replay_contract,
        rollouts=rollouts,
    )
    aggregate = _build_aggregate_reconstruction(
        recovery_report=recovery_report,
        lineage=lineage,
        terminal=terminal,
        verifier=verifier,
        rollouts=rollouts,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_payloads = {
        "aggregate_reconstruction.json": aggregate.model_dump(mode="json"),
        "budget_terminal_audit.json": terminal.model_dump(mode="json"),
        "provider_lineage_audit.json": lineage.model_dump(mode="json"),
        "source_replay_audit.json": source.model_dump(mode="json"),
        "verifier_scoring_audit.json": verifier.model_dump(mode="json"),
    }
    for relative, payload in detail_payloads.items():
        _write_json(output_dir / relative, payload)
    details = tuple(
        DetailFile(
            relative_path=relative,
            sha256=_sha256(output_dir / relative),
            byte_count=(output_dir / relative).stat().st_size,
        )
        for relative in sorted(detail_payloads)
    )
    report_values = {
        "source_replay_audit_id": source.audit_id,
        "provider_lineage_audit_id": lineage.audit_id,
        "budget_terminal_audit_id": terminal.audit_id,
        "verifier_scoring_audit_id": verifier.audit_id,
        "aggregate_reconstruction_audit_id": aggregate.audit_id,
        "immutable_detail_files": details,
    }
    provisional = BudgetPostrunAuditReport.model_construct(report_id="pending", **report_values)
    report = BudgetPostrunAuditReport(
        report_id=budget_postrun_report_id(provisional), **report_values
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def budget_postrun_source_audit_id(value: BudgetPostrunSourceReplayAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_postrun_source_replay:",
    )


def budget_postrun_lineage_audit_id(
    value: BudgetPostrunProviderLineageAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_postrun_provider_lineage:",
    )


def budget_postrun_terminal_row_id(value: BudgetPostrunTerminalRow) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_budget_postrun_terminal_row:",
    )


def budget_postrun_terminal_audit_id(value: BudgetPostrunTerminalAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_postrun_terminal_audit:",
    )


def budget_postrun_verifier_row_id(value: BudgetPostrunVerifierRow) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"row_id"}),
        prefix="finance_v26_budget_postrun_verifier_row:",
    )


def budget_postrun_verifier_audit_id(value: BudgetPostrunVerifierAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_postrun_verifier_audit:",
    )


def budget_postrun_aggregate_audit_id(
    value: BudgetPostrunAggregateReconstruction,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_budget_postrun_aggregate_reconstruction:",
    )


def budget_postrun_report_id(value: BudgetPostrunAuditReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_budget_closed_postrun_audit:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the v26.86 budget-closed Recovery without API calls"
    )
    parser.add_argument("--failed-run-dir", type=Path, required=True)
    parser.add_argument("--recovery-preflight-dir", type=Path, required=True)
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--task-source-dir", type=Path, required=True)
    parser.add_argument("--verifier-qualification-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path("."))
    args = parser.parse_args()
    report = build_budget_closed_postrun_audit(
        failed_run_dir=args.failed_run_dir,
        recovery_preflight_dir=args.recovery_preflight_dir,
        recovery_dir=args.recovery_dir,
        task_source_dir=args.task_source_dir,
        verifier_qualification_dir=args.verifier_qualification_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
