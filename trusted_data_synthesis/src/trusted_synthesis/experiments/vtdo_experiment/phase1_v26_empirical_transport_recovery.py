from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    EmpiricalPilotJobManifest,
    EmpiricalPilotRollout,
    EmpiricalSupportPilotContract,
    EmpiricalSupportPilotReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_runner import (
    _audit_raw_artifacts,
    _make_report,
    _replay_raw,
    _run_one,
    _unique_index,
    _write_json_atomic,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

V26_TRANSPORT_RECOVERY_VERSION = "finance_v26_empirical_transport_recovery.v1"
RETRYABLE_FAILURE_REASON: Literal[
    "LLMClientError:Agent provider omitted required token usage telemetry"
] = "LLMClientError:Agent provider omitted required token usage telemetry"
IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/runtime/agent/iterative.py",
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_pilot.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_support_runner.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_empirical_transport_recovery.py"
    ),
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImplementationSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class TransportRecoveryAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    source_job_manifest_id: str = Field(min_length=1)
    source_rollout_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    source_raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    source_failure_reason: Literal[
        "LLMClientError:Agent provider omitted required token usage telemetry"
    ] = RETRYABLE_FAILURE_REASON
    transient_failure_call_count: int = Field(ge=1)
    successful_recovery_call_count: int = Field(ge=1)
    repeated_request_hash_count: int = Field(ge=1)
    redacted_telemetry_hash: str = Field(min_length=1)
    authorized_retry_count: Literal[1] = 1
    authorized_job_ids: tuple[str, ...] = Field(min_length=1, max_length=1)
    retry_result_replaces_transport_invalid_denominator_only: Literal[True] = True
    model_invalid_outcomes_not_retryable: Literal[True] = True
    result_quality_blind_authorization: Literal[True] = True
    no_other_job_authorized: Literal[True] = True
    source_artifacts_immutable: Literal[True] = True
    implementation_source_files: tuple[ImplementationSourceFile, ...]
    status: Literal["authorized"] = "authorized"
    schema_version: str = V26_TRANSPORT_RECOVERY_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> TransportRecoveryAuthorization:
        if self.authorized_job_ids != (self.source_job_id,):
            raise ValueError("transport recovery authorizes another Job")
        paths = tuple(sorted(item.relative_path for item in self.implementation_source_files))
        if paths != tuple(sorted(IMPLEMENTATION_SOURCE_PATHS)):
            raise ValueError("transport recovery implementation manifest is incomplete")
        if self.authorization_id != transport_recovery_authorization_id(self):
            raise ValueError("transport recovery authorization identity is invalid")
        return self


class TransportRecoveryResult(FrozenModel):
    result_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_rollout_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    retry_index: Literal[1] = 1
    replacement_rollout: EmpiricalPilotRollout
    replacement_terminal_category: str = Field(min_length=1)
    provider_call_count: int = Field(ge=0)
    exact_requested_model: bool
    fallback_used: bool
    status: Literal["passed", "failed"]
    failure_reasons: tuple[str, ...]
    schema_version: str = V26_TRANSPORT_RECOVERY_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> TransportRecoveryResult:
        if self.replacement_rollout.job_id != self.source_job_id:
            raise ValueError("transport recovery result crosses Job identities")
        if self.replacement_terminal_category != self.replacement_rollout.terminal_category:
            raise ValueError("transport recovery terminal accounting is inconsistent")
        if self.provider_call_count != self.replacement_rollout.provider_call_count:
            raise ValueError("transport recovery Provider accounting is inconsistent")
        passed = (
            self.replacement_rollout.terminal_category
            in {"model_valid_trajectory", "model_invalid_trajectory"}
            and self.exact_requested_model
            and not self.fallback_used
            and self.replacement_rollout.recursive_noninterference_passed
            and self.replacement_rollout.condition_noninterference_passed
        )
        if self.status != ("passed" if passed else "failed"):
            raise ValueError("transport recovery status is inconsistent")
        if (self.status == "passed") == bool(self.failure_reasons):
            raise ValueError("transport recovery failure reasons are inconsistent")
        if self.result_id != transport_recovery_result_id(self):
            raise ValueError("transport recovery result identity is invalid")
        return self


class TransportRecoveredPilotReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    authorization: TransportRecoveryAuthorization
    recovery_result: TransportRecoveryResult | None = None
    corrected_pilot_report: EmpiricalSupportPilotReport | None = None
    corrected_rollout_set_hash: str | None = None
    source_rollout_count: Literal[456] = 456
    replacement_count: int = Field(ge=0, le=1)
    model_api_call_count: int = Field(ge=0)
    gpu_job_count: Literal[0] = 0
    wilson_boundary_clamp_applied: bool
    source_report_rewritten: Literal[False] = False
    source_raw_artifacts_rewritten: Literal[False] = False
    status: Literal["preflight", "completed", "blocked"]
    next_permitted_stage: str = Field(min_length=1)
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_TRANSPORT_RECOVERY_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> TransportRecoveredPilotReport:
        if self.status == "preflight":
            if self.recovery_result is not None or self.corrected_pilot_report is not None:
                raise ValueError("transport preflight contains an executed recovery")
            if self.replacement_count != 0 or self.model_api_call_count != 0:
                raise ValueError("transport preflight made a model call")
        else:
            if self.recovery_result is None or self.corrected_pilot_report is None:
                raise ValueError("executed transport recovery lacks corrected evidence")
            if self.replacement_count != 1:
                raise ValueError("transport recovery must replace exactly one denominator row")
            if self.model_api_call_count != self.recovery_result.provider_call_count:
                raise ValueError("transport recovery report Provider count is inconsistent")
            expected_status = (
                "completed"
                if self.recovery_result.status == "passed"
                and self.corrected_pilot_report.status == "completed"
                else "blocked"
            )
            if self.status != expected_status:
                raise ValueError("transport recovered report status is inconsistent")
        if self.report_id != transport_recovered_pilot_report_id(self):
            raise ValueError("transport recovered report identity is invalid")
        return self


def transport_recovery_authorization_id(value: TransportRecoveryAuthorization) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authorization_id"}),
        prefix="finance_v26_transport_recovery_authorization:",
    )


def transport_recovery_result_id(value: TransportRecoveryResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="finance_v26_transport_recovery_result:",
    )


def transport_recovered_pilot_report_id(value: TransportRecoveredPilotReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_transport_recovered_pilot_report:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implementation_sources(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(relative_path=value, sha256=_sha256(package_root / value))
        for value in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _load_source(
    source_dir: Path,
) -> tuple[
    EmpiricalSupportPilotReport,
    EmpiricalSupportPilotContract,
    EmpiricalPilotJobManifest,
    tuple[EmpiricalPilotRollout, ...],
]:
    report = EmpiricalSupportPilotReport.model_validate_json(
        (source_dir / "report.json").read_text(encoding="utf-8")
    )
    contract = EmpiricalSupportPilotContract.model_validate_json(
        (source_dir / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = EmpiricalPilotJobManifest.model_validate_json(
        (source_dir / "job_manifest.json").read_text(encoding="utf-8")
    )
    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads((source_dir / "empirical_rollouts.json").read_text(encoding="utf-8"))
    )
    if report.completed_rollout_count != len(rollouts) or len(rollouts) != 456:
        raise ValueError("transport recovery source lacks the complete denominator")
    if report.raw_integrity_audit.status != "passed":
        raise ValueError("transport recovery source failed raw integrity")
    if report.contract_id != contract.contract_id or report.job_manifest_id != manifest.manifest_id:
        raise ValueError("transport recovery source identities are inconsistent")
    if {item.job_id for item in rollouts} != {item.job_id for item in manifest.jobs}:
        raise ValueError("transport recovery source Job denominator is inconsistent")
    return report, contract, manifest, rollouts


def build_transport_recovery_authorization(
    *,
    run_id: str,
    source_dir: Path,
    package_root: Path,
) -> TransportRecoveryAuthorization:
    report, contract, manifest, rollouts = _load_source(source_dir)
    failures = tuple(item for item in rollouts if item.terminal_category == "runtime_failure")
    if len(failures) != 1:
        raise ValueError("transport recovery requires exactly one Runtime failure")
    if any(item.terminal_category == "instrument_failure" for item in rollouts):
        raise ValueError("transport recovery cannot repair an instrument failure")
    source = failures[0]
    if source.failure_attribution != {
        "category": "runtime_failure",
        "reason": RETRYABLE_FAILURE_REASON,
    }:
        raise ValueError("Runtime failure is outside the frozen recovery reason")
    if source.job_id not in {item.job_id for item in manifest.jobs}:
        raise ValueError("Runtime failure is outside the frozen Job manifest")
    raw = _replay_raw(Path(source.raw_artifact_uri), source.raw_artifact_sha256)
    if raw.get("trajectory") is not None or raw.get("failure_artifact") is None:
        raise ValueError("transport recovery source contains a completed trajectory")
    telemetry = tuple(dict(item) for item in raw["provider_telemetry"])
    transient = tuple(item for item in telemetry if item.get("http_success") is not True)
    successes = tuple(item for item in telemetry if item.get("http_success") is True)
    request_counts = Counter(str(item.get("request_hash")) for item in telemetry)
    repeated = sum(count > 1 for count in request_counts.values())
    if not transient or not successes or repeated < 1:
        raise ValueError("Runtime failure lacks a recovered transient request")
    redacted = tuple(
        {
            "request_hash": item.get("request_hash"),
            "response_hash": item.get("response_hash"),
            "http_status": item.get("http_status"),
            "http_success": item.get("http_success"),
            "error_type": item.get("error_type"),
            "total_tokens": item.get("total_tokens"),
        }
        for item in telemetry
    )
    values = {
        "run_id": run_id,
        "source_report_id": report.report_id,
        "source_report_sha256": _sha256(source_dir / "report.json"),
        "source_contract_id": contract.contract_id,
        "source_job_manifest_id": manifest.manifest_id,
        "source_rollout_id": source.rollout_id,
        "source_job_id": source.job_id,
        "source_raw_artifact_sha256": source.raw_artifact_sha256,
        "transient_failure_call_count": len(transient),
        "successful_recovery_call_count": len(successes),
        "repeated_request_hash_count": repeated,
        "redacted_telemetry_hash": canonical_hash(
            redacted, prefix="finance_v26_transport_recovery_telemetry:"
        ),
        "authorized_job_ids": (source.job_id,),
        "implementation_source_files": _implementation_sources(package_root),
    }
    provisional = TransportRecoveryAuthorization.model_construct(
        authorization_id="pending", **values
    )
    return TransportRecoveryAuthorization(
        authorization_id=transport_recovery_authorization_id(provisional),
        **values,
    )


def run_transport_recovery(
    *,
    run_id: str,
    source_dir: Path,
    v26_56_source_dir: Path,
    model_config_path: Path,
    output_dir: Path,
    package_root: Path,
    audit_only: bool = False,
) -> TransportRecoveredPilotReport:
    source_report, contract, manifest, rollouts = _load_source(source_dir)
    authorization = build_transport_recovery_authorization(
        run_id=run_id,
        source_dir=source_dir,
        package_root=package_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        output_dir / "transport_recovery_authorization.json",
        authorization.model_dump(mode="json"),
    )
    if audit_only:
        values = {
            "run_id": run_id,
            "source_report_id": source_report.report_id,
            "source_report_sha256": authorization.source_report_sha256,
            "authorization": authorization,
            "replacement_count": 0,
            "model_api_call_count": 0,
            "wilson_boundary_clamp_applied": False,
            "status": "preflight",
            "next_permitted_stage": "single_authorized_transport_retry",
        }
        provisional = TransportRecoveredPilotReport.model_construct(report_id="pending", **values)
        report = TransportRecoveredPilotReport(
            report_id=transport_recovered_pilot_report_id(provisional),
            **values,
        )
        _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
        return report

    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    if model_config.model != contract.model_id:
        raise ValueError("transport recovery model differs from the source contract")
    from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
        load_v26_56_inputs,
    )

    _, records, environments, catalogs, _ = load_v26_56_inputs(v26_56_source_dir)
    jobs = {item.job_id: item for item in manifest.jobs}
    record_by_id = _unique_index(records, "record_id")
    environment_by_id = _unique_index(environments, "manifest_id")
    catalog_by_task = _unique_index(catalogs, "task_package_id")
    job = jobs[authorization.source_job_id]
    record = record_by_id[job.task_record_id]
    result_path = output_dir / "transport_recovery_result.json"
    if result_path.exists():
        recovery_result = TransportRecoveryResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        if recovery_result.authorization_id != authorization.authorization_id:
            raise ValueError("existing transport recovery result uses another authorization")
    else:
        client = OpenAICompatibleJsonClient(model_config)
        discovered = client.discover_models()
        if contract.model_id not in discovered:
            raise ValueError("frozen Flash model is unavailable for transport recovery")
        replacement = _run_one(
            job=job,
            contract=contract,
            record=record,
            environment=environment_by_id[record.environment_manifest_id],
            catalog=catalog_by_task[job.task_package_id],
            client=client,
            output_dir=output_dir,
            raw_namespace="transport_recovery_raw",
        )
        passed = (
            replacement.terminal_category in {"model_valid_trajectory", "model_invalid_trajectory"}
            and replacement.exact_requested_model
            and not replacement.fallback_used
            and replacement.recursive_noninterference_passed
            and replacement.condition_noninterference_passed
        )
        blockers = []
        if replacement.terminal_category not in {
            "model_valid_trajectory",
            "model_invalid_trajectory",
        }:
            blockers.append("retry_did_not_produce_model_outcome")
        if not replacement.exact_requested_model or replacement.fallback_used:
            blockers.append("retry_model_identity_failed")
        if not replacement.recursive_noninterference_passed:
            blockers.append("retry_recursive_noninterference_failed")
        if not replacement.condition_noninterference_passed:
            blockers.append("retry_condition_noninterference_failed")
        result_values = {
            "authorization_id": authorization.authorization_id,
            "source_rollout_id": authorization.source_rollout_id,
            "source_job_id": authorization.source_job_id,
            "replacement_rollout": replacement,
            "replacement_terminal_category": replacement.terminal_category,
            "provider_call_count": replacement.provider_call_count,
            "exact_requested_model": replacement.exact_requested_model,
            "fallback_used": replacement.fallback_used,
            "status": "passed" if passed else "failed",
            "failure_reasons": tuple(sorted(blockers)),
        }
        provisional_result = TransportRecoveryResult.model_construct(
            result_id="pending", **result_values
        )
        recovery_result = TransportRecoveryResult(
            result_id=transport_recovery_result_id(provisional_result),
            **result_values,
        )
        _write_json_atomic(result_path, recovery_result.model_dump(mode="json"))

    replacement = recovery_result.replacement_rollout
    corrected = tuple(
        replacement if item.job_id == authorization.source_job_id else item for item in rollouts
    )
    if (
        len(corrected) != 456
        or sum(item.rollout_id == replacement.rollout_id for item in corrected) != 1
    ):
        raise ValueError("transport recovery replacement denominator is invalid")
    _write_json_atomic(
        output_dir / "corrected_empirical_rollouts.json",
        [item.model_dump(mode="json") for item in corrected],
    )
    raw_audit = _audit_raw_artifacts(corrected)
    corrected_status: Literal["completed", "blocked"] = (
        "completed"
        if recovery_result.status == "passed" and raw_audit.status == "passed"
        else "blocked"
    )
    corrected_report = _make_report(
        contract=contract,
        manifest=manifest,
        discovered_models=(contract.model_id,),
        rollouts=corrected,
        raw_audit=raw_audit,
        records=records,
        catalogs=catalogs,
        status=corrected_status,
        next_stage=(
            "derive_from_state_support_freeze"
            if corrected_status == "completed"
            else "transport_recovery_failed"
        ),
    )
    _write_json_atomic(
        output_dir / "corrected_pilot_report.json",
        corrected_report.model_dump(mode="json"),
    )
    wrapper_status: Literal["completed", "blocked"] = (
        "completed"
        if recovery_result.status == "passed" and corrected_report.status == "completed"
        else "blocked"
    )
    values = {
        "run_id": run_id,
        "source_report_id": source_report.report_id,
        "source_report_sha256": authorization.source_report_sha256,
        "authorization": authorization,
        "recovery_result": recovery_result,
        "corrected_pilot_report": corrected_report,
        "corrected_rollout_set_hash": canonical_hash(
            tuple(item.rollout_id for item in corrected),
            prefix="finance_v26_corrected_rollout_set:",
        ),
        "replacement_count": 1,
        "model_api_call_count": recovery_result.provider_call_count,
        "wilson_boundary_clamp_applied": True,
        "status": wrapper_status,
        "next_permitted_stage": (
            corrected_report.next_permitted_stage
            if wrapper_status == "completed"
            else "transport_recovery_failed"
        ),
    }
    provisional = TransportRecoveredPilotReport.model_construct(report_id="pending", **values)
    report = TransportRecoveredPilotReport(
        report_id=transport_recovered_pilot_report_id(provisional),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Authorize and execute the single v26.57 transport recovery"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--v26-56-source-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_transport_recovery(
        run_id=args.run_id,
        source_dir=args.source_dir,
        v26_56_source_dir=args.v26_56_source_dir,
        model_config_path=args.model_config,
        output_dir=args.output_dir,
        package_root=args.package_root,
        audit_only=args.audit_only,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
