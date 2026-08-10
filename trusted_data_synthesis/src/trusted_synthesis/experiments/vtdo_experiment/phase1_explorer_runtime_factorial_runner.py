from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.state import (
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.core.trajectory.validity import TrajectoryValidityReport
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerificationReport,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import FinanceTaskStateArtifact
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_runtime_pilot import AgentPilotArm
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial import (
    EXPLORER_RUNTIME_FACTORIAL_CONTRACT_VERSION,
    FinanceExplorerRuntimeFactorialContract,
    scripted_tool_sequence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import _make_evaluator
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_MODELS,
    ExplorerArm,
    FinanceProFlashPilotContract,
    PairedTaskContract,
    PilotStage,
    _load_artifacts,
    _paired_runtime_context,
    _sha256,
    _write_json_atomic,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentSolver,
    LLMAgentSolver,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.iterative import IterativeAgentFailureArtifact
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolObservation, InMemoryEvidenceToolRuntime

FACTORIAL_ROLLOUT_RECORD_VERSION = "finance_explorer_runtime_rollout.v1"
FACTORIAL_STAGE_REPORT_VERSION = "finance_explorer_runtime_stage_report.v1"
FACTORIAL_RUNNER_VERSION = "finance_explorer_runtime_factorial_runner.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FactorialVerificationSummary(FrozenModel):
    verifier_kind: Literal["trajectory_validity", "finance_iterative"]
    report_id: str = Field(min_length=1)
    report_hash: str = Field(min_length=1)
    valid: bool
    answer_correct: bool
    evidence_provenance_completeness: float = Field(ge=0, le=1)
    verification_success: bool
    stop_decision_quality: bool
    failed_check_ids: tuple[str, ...] = ()


class FinanceFactorialRolloutRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: PilotStage
    model_arm: ExplorerArm
    runtime_arm: AgentPilotArm
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    attempt_id: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    model_config_hash: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    trajectory: Trajectory | None = None
    agent_audit: dict[str, Any] | None = None
    observations: tuple[AgentToolObservation, ...] = ()
    verification: FactorialVerificationSummary | None = None
    verification_payload: dict[str, Any] | None = None
    state_assignment: TrajectoryStateAssignment | None = None
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    failure_artifact: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    schema_version: str = FACTORIAL_ROLLOUT_RECORD_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> FinanceFactorialRolloutRecord:
        if self.requested_model != EXPECTED_MODELS[self.model_arm.value]:
            raise ValueError("factorial rollout uses the wrong model")
        if self.status == "completed":
            if not self.trajectory or not self.agent_audit or not self.verification:
                raise ValueError("completed factorial rollout lacks execution or verification")
            if self.verification.valid != (self.state_assignment is not None):
                raise ValueError("only valid factorial rollouts may enter the state space")
            if self.error_type or self.error_message or self.failure_artifact:
                raise ValueError("completed factorial rollout contains failure state")
            if self.trajectory.task_id != self.task_id:
                raise ValueError("factorial rollout crosses task identities")
            selected = {item.model_selected for item in self.telemetry if item.model_selected}
            if selected != {self.requested_model}:
                raise ValueError("factorial rollout did not use exactly its requested model")
            if any(item.fallback_used for item in self.telemetry):
                raise ValueError("factorial rollout used a forbidden model fallback")
            if self.runtime_arm == AgentPilotArm.DIRECT_BARE and self.observations:
                raise ValueError("Direct/Bare factorial rollout contains interactive observations")
            if self.runtime_arm != AgentPilotArm.DIRECT_BARE and not self.observations:
                raise ValueError("interactive factorial rollout lacks Host observations")
        else:
            if (
                any(
                    item is not None
                    for item in (
                        self.trajectory,
                        self.agent_audit,
                        self.verification,
                        self.verification_payload,
                        self.state_assignment,
                    )
                )
                or self.observations
            ):
                raise ValueError("failed factorial rollout contains completed artifacts")
            if not self.error_type:
                raise ValueError("failed factorial rollout lacks an error type")
        if self.record_id != factorial_rollout_record_id(self):
            raise ValueError("factorial rollout identity is invalid")
        return self


class TaskModelRuntimeMetrics(FrozenModel):
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    model_arm: ExplorerArm
    runtime_arm: AgentPilotArm
    attempted_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    natural_state_entropy: float = Field(ge=0)
    decision_trace_diversity_rate: float = Field(ge=0, le=1)
    tool_sequence_diversity_rate: float = Field(ge=0, le=1)
    nontrivial_state_count: int = Field(ge=0)


class ModelRuntimeSummary(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: AgentPilotArm
    task_count: int = Field(ge=1)
    attempted_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    api_call_success_count: int = Field(ge=0)
    json_contract_success_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    verification_success_count: int = Field(ge=0)
    stop_decision_quality_count: int = Field(ge=0)
    provenance_complete_sum: float = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    mean_accepted_states_per_task: float = Field(ge=0)
    mean_natural_state_entropy: float = Field(ge=0)
    mean_decision_trace_diversity_rate: float = Field(ge=0, le=1)
    mean_tool_sequence_diversity_rate: float = Field(ge=0, le=1)
    nontrivial_state_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    mean_api_latency_ms: float = Field(ge=0)
    failure_counts: dict[str, int]
    verifier_issue_counts: dict[str, int]

    @property
    def completion_rate(self) -> float:
        return self.completed_count / self.attempted_count

    @property
    def validity_rate(self) -> float:
        return self.valid_count / self.attempted_count

    @property
    def end_to_end_accuracy(self) -> float:
        return self.answer_correct_count / self.attempted_count

    @property
    def json_contract_success_rate(self) -> float:
        return (
            self.json_contract_success_count / self.api_call_count if self.api_call_count else 0.0
        )

    @property
    def tool_call_success_rate(self) -> float:
        return (
            self.successful_tool_call_count / self.tool_call_count if self.tool_call_count else 0.0
        )

    @property
    def provenance_completeness(self) -> float:
        return self.provenance_complete_sum / self.completed_count if self.completed_count else 0.0

    @property
    def nontrivial_state_rate(self) -> float:
        return self.nontrivial_state_count / self.valid_count if self.valid_count else 0.0


class FactorialGateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: dict[str, float]
    requirement: str = Field(min_length=1)


class FinanceFactorialStageReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    stage: PilotStage
    checkpoint_sha256: str = Field(min_length=64, max_length=64)
    rollout_records_sha256: str = Field(min_length=64, max_length=64)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    resumed_rollout_count: int = Field(ge=0)
    newly_executed_rollout_count: int = Field(ge=0)
    discovered_models_by_arm: dict[ExplorerArm, tuple[str, ...]]
    task_cell_metrics: tuple[TaskModelRuntimeMetrics, ...] = Field(min_length=1)
    model_runtime_summaries: tuple[ModelRuntimeSummary, ...] = Field(min_length=6, max_length=6)
    gates: tuple[FactorialGateResult, ...] = Field(min_length=1)
    decision: Literal[
        "continue_to_factorial_discovery",
        "stop_after_factorial_calibration",
        "advance_to_state_conditioning",
        "stop_after_factorial_discovery",
    ]
    next_permitted_stage: Literal[
        "factorial_unconditional_discovery",
        "protocol_repair_only",
        "state_conditioning_and_exact_target",
        "agent_environment_redesign",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    status: Literal["passed", "failed"]
    schema_version: str = FACTORIAL_STAGE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceFactorialStageReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("factorial stage report is incomplete")
        if self.resumed_rollout_count + self.newly_executed_rollout_count != (
            self.requested_rollout_count
        ):
            raise ValueError("factorial stage resume accounting is inconsistent")
        expected_cells = {(model, runtime) for model in ExplorerArm for runtime in AgentPilotArm}
        observed_cells = {
            (item.model_arm, item.runtime_arm) for item in self.model_runtime_summaries
        }
        if observed_cells != expected_cells:
            raise ValueError("factorial report lacks a Model x Runtime summary")
        passed = all(item.passed for item in self.gates)
        if passed != (self.status == "passed"):
            raise ValueError("factorial report status differs from its gates")
        if self.stage == PilotStage.CALIBRATION:
            expected_decision = (
                "continue_to_factorial_discovery" if passed else "stop_after_factorial_calibration"
            )
            expected_next = (
                "factorial_unconditional_discovery" if passed else "protocol_repair_only"
            )
        else:
            expected_decision = (
                "advance_to_state_conditioning" if passed else "stop_after_factorial_discovery"
            )
            expected_next = (
                "state_conditioning_and_exact_target" if passed else "agent_environment_redesign"
            )
        if self.decision != expected_decision or self.next_permitted_stage != expected_next:
            raise ValueError("factorial report violates its fail-closed transition")
        if self.report_id != factorial_stage_report_id(self):
            raise ValueError("factorial report identity is invalid")
        return self


def run_factorial_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    stage: PilotStage,
    workers: int,
) -> FinanceFactorialStageReport:
    if workers < 1:
        raise ValueError("factorial workers must be positive")
    contract = FinanceExplorerRuntimeFactorialContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if contract.schema_version != EXPLORER_RUNTIME_FACTORIAL_CONTRACT_VERSION:
        raise ValueError("factorial contract version is not supported")
    base_path = Path(contract.base_contract_path)
    if _sha256(base_path) != contract.base_contract_sha256:
        raise ValueError("factorial base contract changed after freeze")
    base = FinanceProFlashPilotContract.model_validate_json(base_path.read_text(encoding="utf-8"))
    if base.contract_id != contract.base_contract_id:
        raise ValueError("factorial base contract identity changed")
    if _sha256(Path(contract.finance_archive_config_path)) != (
        contract.finance_archive_config_sha256
    ):
        raise ValueError("factorial Archive config changed after freeze")
    if stage == PilotStage.DISCOVERY:
        _require_passing_calibration(output_dir, contract.contract_id)
    tasks = base.calibration_tasks if stage == PilotStage.CALIBRATION else base.discovery_tasks
    replicas = (
        contract.calibration_runs_per_task_model_runtime
        if stage == PilotStage.CALIBRATION
        else contract.discovery_runs_per_task_model_runtime
    )
    task_ids = {item.task_id for item in tasks}
    artifacts = _load_artifacts(Path(base.source_artifacts_path), task_ids)
    task_by_id = {item.task_id: item for item in tasks}
    model_contracts = {item.arm: item for item in base.model_contracts}
    clients = {
        arm: OpenAICompatibleJsonClient(item.config) for arm, item in model_contracts.items()
    }
    discovered = {arm: client.discover_models() for arm, client in clients.items()}
    for arm, models in discovered.items():
        if EXPECTED_MODELS[arm.value] not in models:
            raise ValueError(f"provider did not list the frozen {arm.value} model")
    run_identity = canonical_hash(
        {
            "contract_id": contract.contract_id,
            "stage": stage.value,
            "runner_version": FACTORIAL_RUNNER_VERSION,
            "task_ids": tuple(sorted(task_ids)),
            "replicas": replicas,
        },
        prefix="finance_explorer_runtime_factorial_run:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"factorial_{stage.value}.checkpoint.jsonl"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        task_ids=task_ids,
        replicas=replicas,
    )
    records = {_record_key(item): item for item in historical}
    all_jobs = [
        (model, runtime, task_id, replicate)
        for task_id in sorted(task_ids)
        for replicate in range(replicas)
        for model in ExplorerArm
        for runtime in AgentPilotArm
    ]
    jobs = [item for item in all_jobs if item not in records]
    completed = len(records)
    print(
        f"[factorial:{stage.value}] resuming {completed}/{len(all_jobs)}; "
        f"executing {len(jobs)} jobs with {workers} workers",
        flush=True,
    )
    if jobs:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
            future_map = {
                executor.submit(
                    _run_one,
                    contract,
                    base,
                    stage,
                    model,
                    runtime,
                    artifacts[task_id],
                    task_by_id[task_id],
                    replicate,
                    run_identity,
                    clients[model],
                ): job
                for job in jobs
                for model, runtime, task_id, replicate in (job,)
            }
            for future in as_completed(future_map):
                key = future_map[future]
                record = future.result()
                records[key] = record
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                completed += 1
                if completed == len(all_jobs) or completed % max(1, min(workers, 12)) == 0:
                    print(
                        f"[factorial:{stage.value}] completed {completed}/{len(all_jobs)}",
                        flush=True,
                    )
    ordered = tuple(records[item] for item in all_jobs)
    records_path = output_dir / f"factorial_{stage.value}_rollouts.jsonl"
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    report = _build_report(
        contract,
        base,
        stage,
        ordered,
        checkpoint_path=checkpoint_path,
        records_path=records_path,
        historical_count=len(historical),
        discovered=discovered,
        run_identity=run_identity,
    )
    _write_json_atomic(
        output_dir / f"finance_factorial_{stage.value}_report.json",
        report.model_dump(mode="json"),
    )
    return report


def _run_one(
    contract: FinanceExplorerRuntimeFactorialContract,
    base: FinanceProFlashPilotContract,
    stage: PilotStage,
    model_arm: ExplorerArm,
    runtime_arm: AgentPilotArm,
    artifact: FinanceTaskStateArtifact,
    task_contract: PairedTaskContract,
    replicate: int,
    run_identity: str,
    client: OpenAICompatibleJsonClient,
) -> FinanceFactorialRolloutRecord:
    attempt_id = canonical_hash(
        {
            "run_identity": run_identity,
            "model_arm": model_arm.value,
            "runtime_arm": runtime_arm.value,
            "task_id": task_contract.task_id,
            "replicate": replicate,
            "seed": base.random_seed,
        },
        prefix="finance_factorial_rollout_attempt:",
    )
    base_values = {
        "run_identity": run_identity,
        "contract_id": contract.contract_id,
        "stage": stage,
        "model_arm": model_arm,
        "runtime_arm": runtime_arm,
        "task_id": task_contract.task_id,
        "task_family": task_contract.family,
        "replicate": replicate,
        "attempt_id": attempt_id,
        "requested_model": EXPECTED_MODELS[model_arm.value],
        "model_config_hash": client.config.public_manifest_hash,
        "schema_version": FACTORIAL_ROLLOUT_RECORD_VERSION,
    }
    try:
        if runtime_arm == AgentPilotArm.DIRECT_BARE:
            context = artifact.omega
            result = LLMAgentSolver(client, default_registry()).solve_with_audit(
                context.task.public,
                InMemoryEvidenceToolRuntime(context.public_corpus),
            )
            validity = _make_evaluator(Path(contract.finance_archive_config_path)).evaluate(
                context,
                result.trajectory,
            )
            verification = _bare_verification_summary(validity)
            assignment = (
                map_trajectory_to_state(
                    context,
                    result.trajectory,
                    program_node_aliases=validity.program_node_mapping,
                )
                if validity.valid
                else None
            )
            trajectory = result.trajectory
            audit = result.audit.model_dump(mode="json")
            observations: tuple[AgentToolObservation, ...] = ()
            telemetry = result.audit.telemetry
            verification_payload = validity.model_dump(mode="json")
        else:
            context, manifest = _paired_runtime_context(artifact)
            runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest)
            sequence = (
                scripted_tool_sequence(task_contract.family)
                if runtime_arm == AgentPilotArm.SCRIPTED_TOOL
                else ()
            )
            result = IterativeAgentSolver(
                client,
                mode=(
                    "scripted_tool"
                    if runtime_arm == AgentPilotArm.SCRIPTED_TOOL
                    else "autonomous_agent"
                ),
                maximum_total_tokens=base.maximum_model_tokens_per_rollout,
                scripted_tool_sequence=sequence,
            ).solve_with_audit(context.task.public, runtime)
            validity = FinanceIterativeAgentVerifier().verify(
                context,
                context.public_corpus,
                manifest,
                result,
            )
            verification = _iterative_verification_summary(validity)
            assignment = (
                map_trajectory_to_state(context, result.trajectory) if validity.valid else None
            )
            trajectory = result.trajectory
            audit = result.audit.model_dump(mode="json")
            observations = result.observations
            telemetry = result.audit.telemetry
            verification_payload = validity.model_dump(mode="json")
        values = {
            **base_values,
            "status": "completed",
            "trajectory": trajectory,
            "agent_audit": audit,
            "observations": observations,
            "verification": verification,
            "verification_payload": verification_payload,
            "state_assignment": assignment,
            "telemetry": telemetry,
            "failure_artifact": None,
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:
        telemetry = tuple(getattr(exc, "telemetry", ()))
        failure = getattr(exc, "failure_artifact", None)
        values = {
            **base_values,
            "status": "failed",
            "trajectory": None,
            "agent_audit": None,
            "observations": (),
            "verification": None,
            "verification_payload": None,
            "state_assignment": None,
            "telemetry": telemetry,
            "failure_artifact": (
                failure.model_dump(mode="json")
                if isinstance(failure, IterativeAgentFailureArtifact)
                else None
            ),
            "error_type": type(exc).__name__,
            "error_message": _safe_error_message(exc),
        }
    provisional = FinanceFactorialRolloutRecord.model_construct(record_id="pending", **values)
    return FinanceFactorialRolloutRecord(
        record_id=factorial_rollout_record_id(provisional),
        **values,
    )


def _bare_verification_summary(
    report: TrajectoryValidityReport,
) -> FactorialVerificationSummary:
    return FactorialVerificationSummary(
        verifier_kind="trajectory_validity",
        report_id=report.report_id,
        report_hash=canonical_hash(report, prefix="factorial_bare_verification:"),
        valid=report.valid,
        answer_correct=report.component_validity.get("answer_and_claim", 0.0) == 1.0,
        evidence_provenance_completeness=report.component_validity.get("evidence", 0.0),
        verification_success=report.attributes.verification_degree > 0,
        stop_decision_quality=report.component_validity.get("program_execution", 0.0) == 1.0,
        failed_check_ids=report.failed_check_ids,
    )


def _iterative_verification_summary(
    report: FinanceIterativeAgentVerificationReport,
) -> FactorialVerificationSummary:
    failed = tuple(item.check_id for item in report.checks if not item.passed)
    return FactorialVerificationSummary(
        verifier_kind="finance_iterative",
        report_id=report.report_id,
        report_hash=canonical_hash(report, prefix="factorial_iterative_verification:"),
        valid=report.valid,
        answer_correct=_candidate_check(report, "answer_correct"),
        evidence_provenance_completeness=report.evidence_provenance_completeness,
        verification_success=_candidate_check(report, "verification_succeeded"),
        stop_decision_quality=_candidate_check(report, "stop_after_successful_verification"),
        failed_check_ids=failed,
    )


def _candidate_check(report: FinanceIterativeAgentVerificationReport, check_id: str) -> bool:
    return any(item.check_id == check_id and item.passed for item in report.checks)


def factorial_rollout_record_id(value: FinanceFactorialRolloutRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_explorer_runtime_rollout:",
    )


def factorial_stage_report_id(value: FinanceFactorialStageReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_explorer_runtime_stage_report:",
    )


def _record_key(
    record: FinanceFactorialRolloutRecord,
) -> tuple[ExplorerArm, AgentPilotArm, str, int]:
    return record.model_arm, record.runtime_arm, record.task_id, record.replicate


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    task_ids: set[str],
    replicas: int,
) -> tuple[FinanceFactorialRolloutRecord, ...]:
    if not path.exists():
        return ()
    records = tuple(
        FinanceFactorialRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    keys: set[tuple[ExplorerArm, AgentPilotArm, str, int]] = set()
    for record in records:
        if record.run_identity != run_identity:
            raise ValueError("factorial checkpoint belongs to another run")
        key = _record_key(record)
        if key in keys:
            raise ValueError("factorial checkpoint contains duplicate attempts")
        keys.add(key)
        if record.task_id not in task_ids or not 0 <= record.replicate < replicas:
            raise ValueError("factorial checkpoint contains an unknown job")
    return records


def _build_report(
    contract: FinanceExplorerRuntimeFactorialContract,
    base: FinanceProFlashPilotContract,
    stage: PilotStage,
    records: tuple[FinanceFactorialRolloutRecord, ...],
    *,
    checkpoint_path: Path,
    records_path: Path,
    historical_count: int,
    discovered: dict[ExplorerArm, tuple[str, ...]],
    run_identity: str,
) -> FinanceFactorialStageReport:
    tasks = base.calibration_tasks if stage == PilotStage.CALIBRATION else base.discovery_tasks
    task_family = {item.task_id: item.family for item in tasks}
    grouped: defaultdict[
        tuple[str, ExplorerArm, AgentPilotArm], list[FinanceFactorialRolloutRecord]
    ] = defaultdict(list)
    for record in records:
        grouped[(record.task_id, record.model_arm, record.runtime_arm)].append(record)
    task_metrics = tuple(
        _task_metrics(
            task_id,
            task_family[task_id],
            model,
            runtime,
            tuple(grouped[(task_id, model, runtime)]),
        )
        for task_id in sorted(task_family)
        for model in ExplorerArm
        for runtime in AgentPilotArm
    )
    summaries = tuple(
        _model_runtime_summary(model, runtime, records, task_metrics)
        for model in ExplorerArm
        for runtime in AgentPilotArm
    )
    gates = (
        _calibration_gates(contract, summaries, discovered)
        if stage == PilotStage.CALIBRATION
        else _discovery_gates(contract, base, summaries, task_metrics)
    )
    passed = all(item.passed for item in gates)
    if stage == PilotStage.CALIBRATION:
        decision = (
            "continue_to_factorial_discovery" if passed else "stop_after_factorial_calibration"
        )
        next_stage = "factorial_unconditional_discovery" if passed else "protocol_repair_only"
    else:
        decision = "advance_to_state_conditioning" if passed else "stop_after_factorial_discovery"
        next_stage = (
            "state_conditioning_and_exact_target" if passed else "agent_environment_redesign"
        )
    values = {
        "contract_id": contract.contract_id,
        "run_identity": run_identity,
        "stage": stage,
        "checkpoint_sha256": _sha256(checkpoint_path),
        "rollout_records_sha256": _sha256(records_path),
        "requested_rollout_count": len(records),
        "recorded_rollout_count": len(records),
        "resumed_rollout_count": historical_count,
        "newly_executed_rollout_count": len(records) - historical_count,
        "discovered_models_by_arm": discovered,
        "task_cell_metrics": task_metrics,
        "model_runtime_summaries": summaries,
        "gates": gates,
        "decision": decision,
        "next_permitted_stage": next_stage,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
        "status": "passed" if passed else "failed",
        "schema_version": FACTORIAL_STAGE_REPORT_VERSION,
    }
    provisional = FinanceFactorialStageReport.model_construct(report_id="pending", **values)
    return FinanceFactorialStageReport(
        report_id=factorial_stage_report_id(provisional),
        **values,
    )


def _task_metrics(
    task_id: str,
    family: str,
    model: ExplorerArm,
    runtime: AgentPilotArm,
    records: tuple[FinanceFactorialRolloutRecord, ...],
) -> TaskModelRuntimeMetrics:
    completed = tuple(item for item in records if item.status == "completed")
    valid = tuple(item for item in completed if item.verification and item.verification.valid)
    states = Counter(
        item.state_assignment.state.state_id for item in valid if item.state_assignment is not None
    )
    decision_hashes = {
        trajectory_decision_trace_hash(item.trajectory) for item in valid if item.trajectory
    }
    tool_sequences = {
        tuple(step.tool_name for step in item.trajectory.steps if step.tool_name)
        for item in valid
        if item.trajectory
    }
    return TaskModelRuntimeMetrics(
        task_id=task_id,
        task_family=family,
        model_arm=model,
        runtime_arm=runtime,
        attempted_count=len(records),
        completed_count=len(completed),
        valid_count=len(valid),
        answer_correct_count=sum(
            bool(item.verification and item.verification.answer_correct) for item in completed
        ),
        accepted_state_count=len(states),
        natural_state_entropy=_entropy(states),
        decision_trace_diversity_rate=len(decision_hashes) / len(valid) if valid else 0.0,
        tool_sequence_diversity_rate=len(tool_sequences) / len(valid) if valid else 0.0,
        nontrivial_state_count=sum(_nontrivial_agent_state(item) for item in valid),
    )


def _model_runtime_summary(
    model: ExplorerArm,
    runtime: AgentPilotArm,
    records: tuple[FinanceFactorialRolloutRecord, ...],
    task_metrics: tuple[TaskModelRuntimeMetrics, ...],
) -> ModelRuntimeSummary:
    selected = tuple(
        item for item in records if item.model_arm == model and item.runtime_arm == runtime
    )
    completed = tuple(item for item in selected if item.status == "completed")
    metrics = tuple(
        item for item in task_metrics if item.model_arm == model and item.runtime_arm == runtime
    )
    telemetry = tuple(item for record in selected for item in record.telemetry)
    observations = tuple(item for record in completed for item in record.observations)
    failures = Counter(
        item.error_type or "unknown_failure" for item in selected if item.status == "failed"
    )
    issues = Counter(
        check_id
        for item in completed
        if item.verification
        for check_id in item.verification.failed_check_ids
    )
    latencies = [item.latency_ms for item in telemetry if item.latency_ms is not None]
    return ModelRuntimeSummary(
        model_arm=model,
        runtime_arm=runtime,
        task_count=len(metrics),
        attempted_count=len(selected),
        completed_count=len(completed),
        valid_count=sum(bool(item.verification and item.verification.valid) for item in completed),
        answer_correct_count=sum(
            bool(item.verification and item.verification.answer_correct) for item in completed
        ),
        api_call_count=len(telemetry),
        api_call_success_count=sum(item.http_success for item in telemetry),
        json_contract_success_count=sum(item.json_contract_success for item in telemetry),
        tool_call_count=len(observations),
        successful_tool_call_count=sum(item.status == "succeeded" for item in observations),
        verification_success_count=sum(
            bool(item.verification and item.verification.verification_success) for item in completed
        ),
        stop_decision_quality_count=sum(
            bool(item.verification and item.verification.stop_decision_quality)
            for item in completed
        ),
        provenance_complete_sum=sum(
            item.verification.evidence_provenance_completeness
            for item in completed
            if item.verification
        ),
        accepted_state_count=sum(item.accepted_state_count for item in metrics),
        mean_accepted_states_per_task=_mean([float(item.accepted_state_count) for item in metrics]),
        mean_natural_state_entropy=_mean([item.natural_state_entropy for item in metrics]),
        mean_decision_trace_diversity_rate=_mean(
            [item.decision_trace_diversity_rate for item in metrics]
        ),
        mean_tool_sequence_diversity_rate=_mean(
            [item.tool_sequence_diversity_rate for item in metrics]
        ),
        nontrivial_state_count=sum(item.nontrivial_state_count for item in metrics),
        total_model_tokens=sum(item.total_tokens or 0 for item in telemetry),
        estimated_cost_usd=sum(item.estimated_cost or 0 for item in telemetry),
        mean_api_latency_ms=_mean([float(item) for item in latencies]),
        failure_counts=dict(sorted(failures.items())),
        verifier_issue_counts=dict(sorted(issues.items())),
    )


def _calibration_gates(
    contract: FinanceExplorerRuntimeFactorialContract,
    summaries: tuple[ModelRuntimeSummary, ...],
    discovered: dict[ExplorerArm, tuple[str, ...]],
) -> tuple[FactorialGateResult, ...]:
    threshold = contract.thresholds
    model_gate = all(EXPECTED_MODELS[arm.value] in models for arm, models in discovered.items())
    completion = min(item.completion_rate for item in summaries)
    json_rate = min(item.json_contract_success_rate for item in summaries)
    valid_min = min(item.valid_count for item in summaries)
    interactive = tuple(item for item in summaries if item.runtime_arm != AgentPilotArm.DIRECT_BARE)
    tool_rate = min(item.tool_call_success_rate for item in interactive)
    return (
        FactorialGateResult(
            gate_id="requested_models_discovered",
            passed=model_gate,
            observed={"exact_model_fraction": float(model_gate)},
            requirement="both exact DeepSeek model IDs must be listed",
        ),
        FactorialGateResult(
            gate_id="all_model_runtime_cells_complete",
            passed=completion >= threshold.minimum_calibration_completion_rate,
            observed={"minimum_cell_completion_rate": completion},
            requirement=f">={threshold.minimum_calibration_completion_rate}",
        ),
        FactorialGateResult(
            gate_id="json_contract_smoke",
            passed=json_rate >= threshold.minimum_calibration_json_contract_rate,
            observed={"minimum_cell_json_contract_rate": json_rate},
            requirement=f">={threshold.minimum_calibration_json_contract_rate}",
        ),
        FactorialGateResult(
            gate_id="independent_validity_smoke",
            passed=valid_min >= threshold.minimum_valid_trajectories_per_model_runtime,
            observed={"minimum_valid_count_per_model_runtime": float(valid_min)},
            requirement=f">={threshold.minimum_valid_trajectories_per_model_runtime}",
        ),
        FactorialGateResult(
            gate_id="interactive_tool_execution_smoke",
            passed=tool_rate >= threshold.minimum_interactive_tool_success_rate,
            observed={"minimum_interactive_tool_success_rate": tool_rate},
            requirement=f">={threshold.minimum_interactive_tool_success_rate}",
        ),
    )


def _discovery_gates(
    contract: FinanceExplorerRuntimeFactorialContract,
    base: FinanceProFlashPilotContract,
    summaries: tuple[ModelRuntimeSummary, ...],
    task_metrics: tuple[TaskModelRuntimeMetrics, ...],
) -> tuple[FactorialGateResult, ...]:
    by_cell = {(item.model_arm, item.runtime_arm): item for item in summaries}
    gates: list[FactorialGateResult] = []
    for model in ExplorerArm:
        scripted = by_cell[(model, AgentPilotArm.SCRIPTED_TOOL)]
        autonomous = by_cell[(model, AgentPilotArm.AUTONOMOUS_AGENT)]
        validity_drop = max(0.0, scripted.validity_rate - autonomous.validity_rate)
        model_metrics = {
            (item.task_id, item.runtime_arm): item
            for item in task_metrics
            if item.model_arm == model
        }
        improved = sum(
            _diversity_improved(
                model_metrics[(task_id, AgentPilotArm.SCRIPTED_TOOL)],
                model_metrics[(task_id, AgentPilotArm.AUTONOMOUS_AGENT)],
                contract.thresholds,
            )
            for task_id in {item.task_id for item in task_metrics}
        ) / len({item.task_id for item in task_metrics})
        gates.extend(
            (
                FactorialGateResult(
                    gate_id=f"{model.value}_autonomous_validity",
                    passed=autonomous.validity_rate
                    >= contract.thresholds.minimum_autonomous_validity_rate,
                    observed={"validity_rate": autonomous.validity_rate},
                    requirement=f">={contract.thresholds.minimum_autonomous_validity_rate}",
                ),
                FactorialGateResult(
                    gate_id=f"{model.value}_autonomous_validity_drop_vs_scripted",
                    passed=validity_drop
                    <= contract.thresholds.maximum_autonomous_validity_drop_vs_scripted,
                    observed={"validity_drop": validity_drop},
                    requirement=f"<={contract.thresholds.maximum_autonomous_validity_drop_vs_scripted}",
                ),
                FactorialGateResult(
                    gate_id=f"{model.value}_autonomous_diversity",
                    passed=improved
                    >= contract.thresholds.minimum_autonomous_diversity_task_fraction,
                    observed={"paired_task_improvement_fraction": improved},
                    requirement=f">={contract.thresholds.minimum_autonomous_diversity_task_fraction}",
                ),
                FactorialGateResult(
                    gate_id=f"{model.value}_nontrivial_autonomous_states",
                    passed=autonomous.nontrivial_state_rate
                    >= contract.thresholds.minimum_nontrivial_autonomous_state_rate,
                    observed={"nontrivial_state_rate": autonomous.nontrivial_state_rate},
                    requirement=f">={contract.thresholds.minimum_nontrivial_autonomous_state_rate}",
                ),
            )
        )
    pro = by_cell[(ExplorerArm.PRO, AgentPilotArm.AUTONOMOUS_AGENT)]
    flash = by_cell[(ExplorerArm.FLASH, AgentPilotArm.AUTONOMOUS_AGENT)]
    flash_drop = max(0.0, pro.validity_rate - flash.validity_rate)
    gates.extend(
        (
            FactorialGateResult(
                gate_id="flash_autonomous_minimum_validity",
                passed=flash.validity_rate >= base.thresholds.minimum_flash_validity_rate,
                observed={"flash_validity_rate": flash.validity_rate},
                requirement=f">={base.thresholds.minimum_flash_validity_rate}",
            ),
            FactorialGateResult(
                gate_id="flash_autonomous_validity_drop_vs_pro",
                passed=flash_drop <= base.thresholds.maximum_flash_validity_drop_vs_pro,
                observed={"validity_drop": flash_drop},
                requirement=f"<={base.thresholds.maximum_flash_validity_drop_vs_pro}",
            ),
        )
    )
    return tuple(gates)


def _diversity_improved(
    scripted: TaskModelRuntimeMetrics,
    autonomous: TaskModelRuntimeMetrics,
    thresholds: Any,
) -> bool:
    return bool(
        autonomous.accepted_state_count
        >= scripted.accepted_state_count + thresholds.minimum_autonomous_accepted_state_gain
        or autonomous.natural_state_entropy
        >= scripted.natural_state_entropy + thresholds.minimum_autonomous_state_entropy_gain
        or autonomous.decision_trace_diversity_rate >= scripted.decision_trace_diversity_rate + 0.10
    )


def _nontrivial_agent_state(record: FinanceFactorialRolloutRecord) -> bool:
    if record.runtime_arm != AgentPilotArm.AUTONOMOUS_AGENT or not record.trajectory:
        return False
    tools = [item.call.tool_id for item in record.observations]
    search_arguments = {
        canonical_hash(item.call.arguments, prefix="factorial_search_arguments:")
        for item in record.observations
        if item.call.tool_id == "search_archive"
    }
    recovered = any(
        current.status == "failed"
        and any(later.status == "succeeded" for later in record.observations[index + 1 :])
        for index, current in enumerate(record.observations)
    )
    return bool(
        len(search_arguments) >= 2
        or recovered
        or "cross_check_evidence" in tools
        or len(set(tools)) >= 4
    )


def _require_passing_calibration(output_dir: Path, contract_id: str) -> None:
    path = output_dir / "finance_factorial_calibration_report.json"
    if not path.exists():
        raise ValueError("factorial discovery requires a frozen calibration report")
    report = FinanceFactorialStageReport.model_validate_json(path.read_text(encoding="utf-8"))
    if report.contract_id != contract_id or report.status != "passed":
        raise ValueError("factorial discovery is not authorized by calibration")


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((count / total) * math.log(count / total) for count in counts.values())


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_error_message(exc: Exception) -> str:
    value = " ".join(str(exc).split())[:500]
    value = re.sub(r"sk-[A-Za-z0-9._-]+", "[REDACTED]", value)
    return value or type(exc).__name__


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_jsonl_atomic(path: Path, payloads: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Finance Explorer x Runtime factorial")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(item.value for item in PilotStage), required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    report = run_factorial_stage(
        contract_path=args.contract,
        output_dir=args.output_dir,
        stage=PilotStage(args.stage),
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
