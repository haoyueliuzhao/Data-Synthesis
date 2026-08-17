from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    EmpiricalPilotRollout,
    PathStrategy,
    RematerializedExecutableTaskRecord,
    TargetMechanism,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_runner import (
    _replay_raw,
    _write_json_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_transport_recovery import (
    TransportRecoveredPilotReport,
)
from trusted_synthesis.hashing import canonical_hash

V26_EMPIRICAL_FAILURE_AUDIT_VERSION = "finance_v26_empirical_failure_audit.v1"
IMPLEMENTATION_SOURCE_PATH = (
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_empirical_failure_audit.py"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RolloutFailureDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    rollout_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    sampling_mode: str = Field(min_length=1)
    terminal_category: str = Field(min_length=1)
    complete_trajectory_present: bool
    earliest_failure_stage: str = Field(min_length=1)
    failed_check_ids: tuple[str, ...]
    matched_program_node_count: int = Field(ge=0)
    expected_program_node_count: int = Field(ge=1)
    operation_lineage_complete: bool
    evidence_support_complete: bool
    verification_complete: bool
    answer_projection_complete: bool
    mechanism_complete: bool
    verified_before_program_complete: bool
    answer_passed_without_program_complete: bool
    requested_path_strategy: PathStrategy | None = None
    observed_precalculation_strategy: PathStrategy | None = None
    conditioned_behavior_match: bool | None = None
    raw_artifact_sha256: str = Field(min_length=64, max_length=64)
    compiler_witness_counted: Literal[False] = False
    schema_version: str = V26_EMPIRICAL_FAILURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> RolloutFailureDiagnostic:
        if self.conditioned_behavior_match is not None and self.requested_path_strategy is None:
            raise ValueError("conditioned behavior match lacks a requested strategy")
        if self.matched_program_node_count > self.expected_program_node_count:
            raise ValueError("matched Program node count exceeds the frozen Program")
        if self.verified_before_program_complete != (
            self.verification_complete and not self.operation_lineage_complete
        ):
            raise ValueError("premature verification diagnostic is inconsistent")
        if self.answer_passed_without_program_complete != (
            self.answer_projection_complete and not self.operation_lineage_complete
        ):
            raise ValueError("answer-without-Program diagnostic is inconsistent")
        if self.diagnostic_id != rollout_failure_diagnostic_id(self):
            raise ValueError("rollout failure diagnostic identity is invalid")
        return self


class ConditionBehaviorSummary(FrozenModel):
    requested_strategy: PathStrategy
    rollout_count: Literal[72] = 72
    observed_strategy_counts: dict[str, int]
    matching_behavior_count: int = Field(ge=0, le=72)
    matching_behavior_rate: float = Field(ge=0, le=1)
    independently_valid_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_summary(self) -> ConditionBehaviorSummary:
        if sum(self.observed_strategy_counts.values()) != self.rollout_count:
            raise ValueError("condition behavior denominator is inconsistent")
        expected = self.observed_strategy_counts.get(self.requested_strategy, 0)
        if self.matching_behavior_count != expected:
            raise ValueError("condition behavior match count is inconsistent")
        if self.matching_behavior_rate != self.matching_behavior_count / self.rollout_count:
            raise ValueError("condition behavior match rate is inconsistent")
        return self


class MechanismProgressSummary(FrozenModel):
    mechanism_id: TargetMechanism
    rollout_count: Literal[114] = 114
    complete_trajectory_count: int = Field(ge=0, le=114)
    model_contract_failure_count: int = Field(ge=0, le=114)
    mechanism_success_count: int = Field(ge=0, le=114)
    operation_lineage_complete_count: int = Field(ge=0, le=114)
    evidence_support_complete_count: int = Field(ge=0, le=114)
    verification_complete_count: int = Field(ge=0, le=114)
    answer_projection_complete_count: int = Field(ge=0, le=114)
    independent_valid_count: Literal[0] = 0
    matched_program_node_counts: dict[int, int]

    @model_validator(mode="after")
    def validate_summary(self) -> MechanismProgressSummary:
        if self.complete_trajectory_count + self.model_contract_failure_count != 114:
            raise ValueError("mechanism trajectory denominator is inconsistent")
        if sum(self.matched_program_node_counts.values()) != self.complete_trajectory_count:
            raise ValueError("mechanism Program-progress denominator is inconsistent")
        return self


class EmpiricalFailureAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_recovered_report_id: str = Field(min_length=1)
    source_recovered_report_sha256: str = Field(min_length=64, max_length=64)
    source_corrected_pilot_report_id: str = Field(min_length=1)
    source_corrected_rollouts_sha256: str = Field(min_length=64, max_length=64)
    source_corrected_rollout_set_hash: str = Field(min_length=1)
    rollout_count: Literal[456] = 456
    raw_replay_pass_count: int = Field(ge=0, le=456)
    complete_trajectory_count: int = Field(ge=0, le=456)
    model_contract_failure_count: int = Field(ge=0, le=456)
    earliest_failure_stage_counts: dict[str, int]
    failed_check_counts: dict[str, int]
    matched_program_node_counts: dict[int, int]
    completed_operation_lineage_failure_count: int = Field(ge=0, le=456)
    verified_before_program_complete_count: int = Field(ge=0, le=456)
    answer_passed_without_program_complete_count: int = Field(ge=0, le=456)
    mechanism_success_without_validity_count: int = Field(ge=0, le=456)
    condition_behavior_summaries: tuple[ConditionBehaviorSummary, ...] = Field(
        min_length=3, max_length=3
    )
    natural_precalculation_strategy_counts: dict[str, int]
    mechanism_progress_summaries: tuple[MechanismProgressSummary, ...] = Field(
        min_length=4, max_length=4
    )
    task_count: Literal[24] = 24
    public_operation_execution_contract_task_count: int = Field(ge=0, le=24)
    missing_public_operation_execution_contract_task_count: int = Field(ge=0, le=24)
    compiler_witness_count: Literal[0] = 0
    implementation_source_sha256: str = Field(min_length=64, max_length=64)
    status: Literal["public_operation_contract_gap_observed"] = (
        "public_operation_contract_gap_observed"
    )
    next_permitted_stage: Literal["fresh_public_operation_contract_rematerialization_only"] = (
        "fresh_public_operation_contract_rematerialization_only"
    )
    model_api_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_EMPIRICAL_FAILURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> EmpiricalFailureAuditReport:
        if self.raw_replay_pass_count != self.rollout_count:
            raise ValueError("failure audit did not replay every raw Artifact")
        if self.complete_trajectory_count + self.model_contract_failure_count != 456:
            raise ValueError("failure audit trajectory denominator is inconsistent")
        if sum(self.earliest_failure_stage_counts.values()) != 456:
            raise ValueError("failure cascade does not account for every rollout")
        if sum(self.matched_program_node_counts.values()) != self.complete_trajectory_count:
            raise ValueError("Program-progress denominator is inconsistent")
        if (
            self.public_operation_execution_contract_task_count
            + (self.missing_public_operation_execution_contract_task_count)
            != 24
        ):
            raise ValueError("public Operation-contract task denominator is inconsistent")
        if self.report_id != empirical_failure_audit_report_id(self):
            raise ValueError("empirical failure audit report identity is invalid")
        return self


def rollout_failure_diagnostic_id(value: RolloutFailureDiagnostic) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"diagnostic_id"}),
        prefix="finance_v26_rollout_failure_diagnostic:",
    )


def empirical_failure_audit_report_id(value: EmpiricalFailureAuditReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_empirical_failure_audit:",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_observations(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    trajectory = raw.get("trajectory")
    if isinstance(trajectory, dict):
        output = []
        for step in trajectory.get("steps") or ():
            observation = step.get("observation") if isinstance(step, dict) else None
            if isinstance(observation, dict) and isinstance(observation.get("call"), dict):
                output.append(observation)
        return tuple(output)
    failure = raw.get("failure_artifact")
    if isinstance(failure, dict):
        return tuple(item for item in failure.get("observations") or () if isinstance(item, dict))
    return ()


def _observed_strategy(observations: tuple[dict[str, Any], ...]) -> PathStrategy | None:
    tools = []
    for item in observations:
        call = item.get("call") or {}
        tool = call.get("tool_id")
        if tool == "calculator" and item.get("status") == "succeeded":
            break
        if item.get("status") == "succeeded":
            tools.append(str(tool))
    return cast(
        PathStrategy | None,
        "search_then_open"
        if "open_document" in tools
        else "search_then_structured"
        if "search_archive" in tools
        else "structured_direct"
        if "query_structured_fact" in tools
        else None,
    )


def _diagnostic(
    rollout: EmpiricalPilotRollout,
    raw: dict[str, Any],
    expected_node_count: int,
) -> RolloutFailureDiagnostic:
    verification = rollout.verification
    checks = verification.checks if verification is not None else {}
    failed = tuple(sorted(key for key, value in checks.items() if not value))
    stage = (
        verification.earliest_failure_stage
        if verification is not None
        else "model_contract"
        if rollout.terminal_category == "model_invalid_trajectory"
        else rollout.terminal_category
    )
    if stage is None:
        stage = "unexpected_valid"
    matched = len(verification.matched_program_node_ids) if verification is not None else 0
    operation = bool(checks.get("operation_lineage_complete"))
    evidence = bool(checks.get("evidence_support_complete"))
    verified = bool(checks.get("verification_complete"))
    answer = bool(checks.get("answer_projection_complete"))
    mechanism = rollout.mechanism_estimand.success
    observed = _observed_strategy(_extract_observations(raw))
    conditioned_match = (
        observed == rollout.requested_path_strategy
        if rollout.requested_path_strategy is not None
        else None
    )
    values = {
        "rollout_id": rollout.rollout_id,
        "job_id": rollout.job_id,
        "task_package_id": rollout.task_package_id,
        "mechanism_id": rollout.mechanism_id,
        "sampling_mode": rollout.sampling_mode,
        "terminal_category": rollout.terminal_category,
        "complete_trajectory_present": verification is not None,
        "earliest_failure_stage": stage,
        "failed_check_ids": failed,
        "matched_program_node_count": matched,
        "expected_program_node_count": expected_node_count,
        "operation_lineage_complete": operation,
        "evidence_support_complete": evidence,
        "verification_complete": verified,
        "answer_projection_complete": answer,
        "mechanism_complete": mechanism,
        "verified_before_program_complete": verified and not operation,
        "answer_passed_without_program_complete": answer and not operation,
        "requested_path_strategy": rollout.requested_path_strategy,
        "observed_precalculation_strategy": observed,
        "conditioned_behavior_match": conditioned_match,
        "raw_artifact_sha256": rollout.raw_artifact_sha256,
    }
    provisional = RolloutFailureDiagnostic.model_construct(diagnostic_id="pending", **values)
    return RolloutFailureDiagnostic(
        diagnostic_id=rollout_failure_diagnostic_id(provisional),
        **values,
    )


def build_empirical_failure_audit(
    *,
    run_id: str,
    source_recovery_dir: Path,
    v26_56_source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> EmpiricalFailureAuditReport:
    recovered_path = source_recovery_dir / "report.json"
    recovered = TransportRecoveredPilotReport.model_validate_json(
        recovered_path.read_text(encoding="utf-8")
    )
    if recovered.status != "completed" or recovered.corrected_pilot_report is None:
        raise ValueError("failure audit requires a completed transport-recovered Pilot")
    corrected_path = source_recovery_dir / "corrected_empirical_rollouts.json"
    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads(corrected_path.read_text(encoding="utf-8"))
    )
    records = tuple(
        RematerializedExecutableTaskRecord.model_validate(item)
        for item in json.loads(
            (v26_56_source_dir / "rematerialized_task_records.json").read_text(encoding="utf-8")
        )
    )
    record_by_task = {item.task_package.package_id: item for item in records}
    if len(rollouts) != 456 or len(record_by_task) != 24:
        raise ValueError("failure audit source denominator is invalid")
    diagnostics = []
    for rollout in rollouts:
        raw = _replay_raw(Path(rollout.raw_artifact_uri), rollout.raw_artifact_sha256)
        if raw.get("job", {}).get("job_id") != rollout.job_id:
            raise ValueError("failure audit raw Job identity changed")
        record = record_by_task[rollout.task_package_id]
        diagnostics.append(
            _diagnostic(
                rollout,
                raw,
                len(record.task_package.task.oracle.task_program.nodes),
            )
        )
    diagnostics.sort(key=lambda item: item.diagnostic_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        output_dir / "rollout_failure_diagnostics.json",
        [item.model_dump(mode="json") for item in diagnostics],
    )

    cascade = Counter(item.earliest_failure_stage for item in diagnostics)
    failed_checks = Counter(check for item in diagnostics for check in item.failed_check_ids)
    matched = Counter(
        item.matched_program_node_count for item in diagnostics if item.complete_trajectory_present
    )
    conditioned_summaries = []
    for strategy in (
        "structured_direct",
        "search_then_structured",
        "search_then_open",
    ):
        rows = [item for item in diagnostics if item.requested_path_strategy == strategy]
        observed = Counter(item.observed_precalculation_strategy or "unmapped" for item in rows)
        matches = sum(item.conditioned_behavior_match is True for item in rows)
        conditioned_summaries.append(
            ConditionBehaviorSummary(
                requested_strategy=cast(PathStrategy, strategy),
                observed_strategy_counts=dict(sorted(observed.items())),
                matching_behavior_count=matches,
                matching_behavior_rate=matches / len(rows),
            )
        )
    natural = Counter(
        item.observed_precalculation_strategy or "unmapped"
        for item in diagnostics
        if item.sampling_mode == "reachability_unconditional"
    )
    mechanism_summaries = []
    for mechanism in (
        "context_conditioned_action",
        "semantic_reconciliation",
        "failure_recovery",
        "state_dependent_stopping",
    ):
        rows = [item for item in diagnostics if item.mechanism_id == mechanism]
        completed = [item for item in rows if item.complete_trajectory_present]
        mechanism_summaries.append(
            MechanismProgressSummary(
                mechanism_id=cast(TargetMechanism, mechanism),
                complete_trajectory_count=len(completed),
                model_contract_failure_count=len(rows) - len(completed),
                mechanism_success_count=sum(item.mechanism_complete for item in rows),
                operation_lineage_complete_count=sum(
                    item.operation_lineage_complete for item in rows
                ),
                evidence_support_complete_count=sum(
                    item.evidence_support_complete for item in rows
                ),
                verification_complete_count=sum(item.verification_complete for item in rows),
                answer_projection_complete_count=sum(
                    item.answer_projection_complete for item in rows
                ),
                matched_program_node_counts=dict(
                    sorted(Counter(item.matched_program_node_count for item in completed).items())
                ),
            )
        )
    public_contract_count = sum(
        "operation_execution_contract" in item.task_package.task.public.metadata for item in records
    )
    values = {
        "run_id": run_id,
        "source_recovered_report_id": recovered.report_id,
        "source_recovered_report_sha256": _sha256(recovered_path),
        "source_corrected_pilot_report_id": recovered.corrected_pilot_report.report_id,
        "source_corrected_rollouts_sha256": _sha256(corrected_path),
        "source_corrected_rollout_set_hash": recovered.corrected_rollout_set_hash,
        "raw_replay_pass_count": len(diagnostics),
        "complete_trajectory_count": sum(item.complete_trajectory_present for item in diagnostics),
        "model_contract_failure_count": sum(
            not item.complete_trajectory_present for item in diagnostics
        ),
        "earliest_failure_stage_counts": dict(sorted(cascade.items())),
        "failed_check_counts": dict(sorted(failed_checks.items())),
        "matched_program_node_counts": dict(sorted(matched.items())),
        "completed_operation_lineage_failure_count": sum(
            item.complete_trajectory_present and not item.operation_lineage_complete
            for item in diagnostics
        ),
        "verified_before_program_complete_count": sum(
            item.verified_before_program_complete for item in diagnostics
        ),
        "answer_passed_without_program_complete_count": sum(
            item.answer_passed_without_program_complete for item in diagnostics
        ),
        "mechanism_success_without_validity_count": sum(
            item.mechanism_complete for item in diagnostics
        ),
        "condition_behavior_summaries": tuple(conditioned_summaries),
        "natural_precalculation_strategy_counts": dict(sorted(natural.items())),
        "mechanism_progress_summaries": tuple(mechanism_summaries),
        "public_operation_execution_contract_task_count": public_contract_count,
        "missing_public_operation_execution_contract_task_count": 24 - public_contract_count,
        "implementation_source_sha256": _sha256(package_root / IMPLEMENTATION_SOURCE_PATH),
    }
    provisional = EmpiricalFailureAuditReport.model_construct(report_id="pending", **values)
    report = EmpiricalFailureAuditReport(
        report_id=empirical_failure_audit_report_id(provisional),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit v26.58 empirical failure cascade without model calls"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-recovery-dir", type=Path, required=True)
    parser.add_argument("--v26-56-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = build_empirical_failure_audit(
        run_id=args.run_id,
        source_recovery_dir=args.source_recovery_dir,
        v26_56_source_dir=args.v26_56_source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
