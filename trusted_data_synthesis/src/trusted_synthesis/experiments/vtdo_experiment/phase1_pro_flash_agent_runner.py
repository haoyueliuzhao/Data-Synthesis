from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.specification import make_omega_component_manifest
from trusted_synthesis.core.trajectory.state import (
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerificationReport,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import FinanceTaskStateArtifact
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    EXPECTED_MODELS,
    PRO_FLASH_PILOT_CONTRACT_VERSION,
    ExplorerArm,
    FinanceProFlashPilotContract,
    PairedTaskContract,
    _load_artifacts,
    _paired_runtime_context,
    _sha256,
    _write_json_atomic,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentSolver,
    IterativeAgentSolveResult,
    LLMClientError,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

PRO_FLASH_ROLLOUT_RECORD_VERSION = "finance_pro_flash_rollout_record.v1"
PRO_FLASH_STAGE_REPORT_VERSION = "finance_pro_flash_stage_report.v1"
PRO_FLASH_RUNNER_VERSION = "finance_pro_flash_paired_runner.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PilotStage(str, Enum):
    CALIBRATION = "calibration"
    DISCOVERY = "discovery"


class FinanceProFlashRolloutRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: PilotStage
    arm: ExplorerArm
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    attempt_id: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    model_config_hash: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    solve_result: IterativeAgentSolveResult | None = None
    verification_report: FinanceIterativeAgentVerificationReport | None = None
    state_assignment: TrajectoryStateAssignment | None = None
    failure_telemetry: tuple[ModelCallTelemetry, ...] = ()
    error_type: str | None = None
    error_message: str | None = None
    schema_version: str = PRO_FLASH_ROLLOUT_RECORD_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> FinanceProFlashRolloutRecord:
        if self.requested_model != EXPECTED_MODELS[self.arm.value]:
            raise ValueError("paired rollout uses the wrong arm model")
        if self.status == "completed":
            if self.solve_result is None or self.verification_report is None:
                raise ValueError("completed paired rollout lacks execution or verification")
            if self.failure_telemetry or self.error_type or self.error_message:
                raise ValueError("completed paired rollout contains failure telemetry")
            if self.verification_report.valid != (self.state_assignment is not None):
                raise ValueError("only valid paired rollouts may enter the quotient state space")
            if self.solve_result.trajectory.task_id != self.task_id:
                raise ValueError("paired rollout crosses task identities")
            selected_models = {item.model_selected for item in self.solve_result.audit.telemetry}
            if selected_models != {self.requested_model}:
                raise ValueError("paired rollout did not use exactly its requested model")
            if any(item.fallback_used for item in self.solve_result.audit.telemetry):
                raise ValueError("paired rollout used a forbidden model fallback")
        else:
            if self.solve_result or self.verification_report or self.state_assignment:
                raise ValueError("failed paired rollout contains completed artifacts")
            if not self.error_type:
                raise ValueError("failed paired rollout lacks an error type")
        if self.record_id != finance_pro_flash_rollout_record_id(self):
            raise ValueError("paired rollout record identity is invalid")
        return self


class TaskArmStageMetrics(FrozenModel):
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    arm: ExplorerArm
    attempted_rollout_count: int = Field(ge=1)
    completed_rollout_count: int = Field(ge=0)
    valid_rollout_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    natural_state_entropy: float = Field(ge=0)
    decision_trace_diversity_rate: float = Field(ge=0, le=1)
    tool_sequence_diversity_rate: float = Field(ge=0, le=1)
    query_reformulation_count: int = Field(ge=0)
    recovery_opportunity_count: int = Field(ge=0)
    successful_recovery_count: int = Field(ge=0)
    verification_action_count: int = Field(ge=0)
    stop_decision_quality_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_metrics(self) -> TaskArmStageMetrics:
        if self.valid_rollout_count > self.completed_rollout_count:
            raise ValueError("valid paired rollouts exceed completed rollouts")
        if self.completed_rollout_count > self.attempted_rollout_count:
            raise ValueError("completed paired rollouts exceed attempts")
        if self.answer_correct_count > self.completed_rollout_count:
            raise ValueError("correct paired answers exceed completed rollouts")
        if self.successful_recovery_count > self.recovery_opportunity_count:
            raise ValueError("successful recoveries exceed recovery opportunities")
        return self


class ExplorerArmStageSummary(FrozenModel):
    arm: ExplorerArm
    attempted_rollout_count: int = Field(ge=1)
    completed_rollout_count: int = Field(ge=0)
    valid_rollout_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    api_call_success_count: int = Field(ge=0)
    json_contract_success_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    verification_action_count: int = Field(ge=0)
    stop_decision_quality_count: int = Field(ge=0)
    provenance_complete_sum: float = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    mean_accepted_states_per_task: float = Field(ge=0)
    mean_natural_state_entropy: float = Field(ge=0)
    mean_decision_trace_diversity_rate: float = Field(ge=0, le=1)
    mean_tool_sequence_diversity_rate: float = Field(ge=0, le=1)
    query_reformulation_count: int = Field(ge=0)
    recovery_opportunity_count: int = Field(ge=0)
    successful_recovery_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    mean_api_latency_ms: float = Field(ge=0)
    failure_counts: dict[str, int]
    verifier_issue_counts: dict[str, int]

    @property
    def rollout_contract_success_rate(self) -> float:
        return self.completed_rollout_count / self.attempted_rollout_count

    @property
    def validity_rate(self) -> float:
        return self.valid_rollout_count / self.attempted_rollout_count

    @property
    def end_to_end_accuracy(self) -> float:
        return self.answer_correct_count / self.attempted_rollout_count

    @property
    def api_call_success_rate(self) -> float:
        return self.api_call_success_count / self.api_call_count if self.api_call_count else 0.0

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
    def evidence_provenance_completeness(self) -> float:
        return (
            self.provenance_complete_sum / self.completed_rollout_count
            if self.completed_rollout_count
            else 0.0
        )

    @property
    def error_recovery_rate(self) -> float | None:
        return (
            self.successful_recovery_count / self.recovery_opportunity_count
            if self.recovery_opportunity_count
            else None
        )


class PilotGateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: dict[str, float]
    requirement: str = Field(min_length=1)


class FinanceProFlashStageReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    stage: PilotStage
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    checkpoint_sha256: str = Field(min_length=64, max_length=64)
    rollout_records_sha256: str = Field(min_length=64, max_length=64)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    resumed_rollout_count: int = Field(ge=0)
    newly_executed_rollout_count: int = Field(ge=0)
    discovered_models_by_arm: dict[ExplorerArm, tuple[str, ...]]
    task_arm_metrics: tuple[TaskArmStageMetrics, ...] = Field(min_length=1)
    arm_summaries: tuple[ExplorerArmStageSummary, ...] = Field(min_length=2, max_length=2)
    paired_diversity_improvement_task_fraction: float = Field(ge=0, le=1)
    mean_state_entropy_gain_flash_minus_pro: float
    mean_accepted_state_gain_flash_minus_pro: float
    gates: tuple[PilotGateResult, ...] = Field(min_length=1)
    decision: Literal[
        "continue_to_discovery",
        "stop_after_calibration",
        "advance_to_state_conditioning",
        "stop_after_discovery",
    ]
    next_permitted_stage: Literal[
        "paired_unconditional_discovery",
        "protocol_repair_only",
        "state_conditioning_and_exact_target",
        "experiment_stopped",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    status: Literal["passed", "failed"]
    schema_version: str = PRO_FLASH_STAGE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceProFlashStageReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("paired stage report is incomplete")
        if self.resumed_rollout_count + self.newly_executed_rollout_count != (
            self.requested_rollout_count
        ):
            raise ValueError("paired stage resume accounting is inconsistent")
        if {item.arm for item in self.arm_summaries} != set(ExplorerArm):
            raise ValueError("paired stage report lacks an arm summary")
        passed = all(item.passed for item in self.gates)
        if passed != (self.status == "passed"):
            raise ValueError("paired stage status differs from its gates")
        if self.stage == PilotStage.CALIBRATION:
            expected_decision = "continue_to_discovery" if passed else "stop_after_calibration"
            expected_next = "paired_unconditional_discovery" if passed else "protocol_repair_only"
        else:
            expected_decision = (
                "advance_to_state_conditioning" if passed else "stop_after_discovery"
            )
            expected_next = (
                "state_conditioning_and_exact_target" if passed else "experiment_stopped"
            )
        if self.decision != expected_decision or self.next_permitted_stage != expected_next:
            raise ValueError("paired stage report violates its fail-closed transition")
        if self.report_id != finance_pro_flash_stage_report_id(self):
            raise ValueError("paired stage report identity is invalid")
        return self


def run_pro_flash_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    stage: PilotStage,
    workers: int,
) -> FinanceProFlashStageReport:
    if workers < 1:
        raise ValueError("paired Pilot workers must be positive")
    contract = FinanceProFlashPilotContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if contract.schema_version != PRO_FLASH_PILOT_CONTRACT_VERSION:
        raise ValueError("paired Pilot contract version is not supported")
    source_path = Path(contract.source_artifacts_path)
    if _sha256(source_path) != contract.source_artifacts_sha256:
        raise ValueError("paired Pilot source Artifact changed after contract freeze")
    task_contracts = (
        contract.calibration_tasks if stage == PilotStage.CALIBRATION else contract.discovery_tasks
    )
    replicas = (
        contract.calibration_runs_per_task_arm
        if stage == PilotStage.CALIBRATION
        else contract.unconditional_runs_per_task_arm
    )
    task_ids = {item.task_id for item in task_contracts}
    artifacts = _load_artifacts(source_path, task_ids)
    task_contract_by_id = {item.task_id: item for item in task_contracts}
    for task_id, artifact in artifacts.items():
        _validate_runtime_identity(artifact, task_contract_by_id[task_id])

    model_by_arm = {item.arm: item for item in contract.model_contracts}
    clients = {
        arm: OpenAICompatibleJsonClient(model_contract.config)
        for arm, model_contract in model_by_arm.items()
    }
    discovered_models = {arm: client.discover_models() for arm, client in clients.items()}
    for arm, models in discovered_models.items():
        if EXPECTED_MODELS[arm.value] not in models:
            raise ValueError(f"provider did not list the frozen {arm.value} model")

    run_identity = canonical_hash(
        {
            "contract_id": contract.contract_id,
            "stage": stage.value,
            "runner_version": PRO_FLASH_RUNNER_VERSION,
            "task_ids": tuple(sorted(task_ids)),
            "replicas": replicas,
        },
        prefix="finance_pro_flash_stage_run:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"{stage.value}_rollouts.checkpoint.jsonl"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        task_ids=task_ids,
        replicas=replicas,
    )
    records_by_key = {_record_key(item): item for item in historical}
    all_jobs = [
        (arm, task_id, replicate)
        for task_id in sorted(task_ids)
        for replicate in range(replicas)
        for arm in ExplorerArm
    ]
    jobs = [job for job in all_jobs if job not in records_by_key]
    completed = len(records_by_key)
    print(
        f"[{stage.value}] resuming {completed}/{len(all_jobs)}; "
        f"executing {len(jobs)} jobs with {workers} workers",
        flush=True,
    )
    if jobs:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
            future_map = {
                executor.submit(
                    _run_one,
                    contract,
                    stage,
                    arm,
                    artifacts[task_id],
                    task_contract_by_id[task_id],
                    replicate,
                    run_identity,
                    clients[arm],
                ): (arm, task_id, replicate)
                for arm, task_id, replicate in jobs
            }
            for future in as_completed(future_map):
                key = future_map[future]
                record = future.result()
                records_by_key[key] = record
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                completed += 1
                if completed == len(all_jobs) or completed % max(1, min(20, workers)) == 0:
                    print(f"[{stage.value}] completed {completed}/{len(all_jobs)}", flush=True)

    records = tuple(records_by_key[job] for job in all_jobs)
    records_path = output_dir / f"{stage.value}_rollouts.jsonl"
    _write_jsonl_atomic(
        records_path,
        (item.model_dump(mode="json") for item in records),
    )
    report = _build_stage_report(
        contract,
        stage,
        records,
        checkpoint_path=checkpoint_path,
        records_path=records_path,
        historical_count=len(historical),
        discovered_models=discovered_models,
        run_identity=run_identity,
    )
    _write_json_atomic(
        output_dir / f"finance_pro_flash_{stage.value}_report.json",
        report.model_dump(mode="json"),
    )
    return report


def _run_one(
    contract: FinanceProFlashPilotContract,
    stage: PilotStage,
    arm: ExplorerArm,
    artifact: FinanceTaskStateArtifact,
    task_contract: PairedTaskContract,
    replicate: int,
    run_identity: str,
    client: OpenAICompatibleJsonClient,
) -> FinanceProFlashRolloutRecord:
    attempt_id = canonical_hash(
        {
            "run_identity": run_identity,
            "arm": arm.value,
            "task_id": task_contract.task_id,
            "replicate": replicate,
            "random_seed": contract.random_seed,
        },
        prefix="finance_pro_flash_rollout_attempt:",
    )
    base_values = {
        "run_identity": run_identity,
        "contract_id": contract.contract_id,
        "stage": stage,
        "arm": arm,
        "task_id": task_contract.task_id,
        "task_family": task_contract.family,
        "replicate": replicate,
        "attempt_id": attempt_id,
        "requested_model": EXPECTED_MODELS[arm.value],
        "model_config_hash": client.config.public_manifest_hash,
        "schema_version": PRO_FLASH_ROLLOUT_RECORD_VERSION,
    }
    try:
        context, manifest = _paired_runtime_context(artifact)
        runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest)
        solver = IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.maximum_model_tokens_per_rollout,
        )
        result = solver.solve_with_audit(context.task.public, runtime)
        verification = FinanceIterativeAgentVerifier().verify(
            context,
            context.public_corpus,
            manifest,
            result,
        )
        assignment = (
            map_trajectory_to_state(context, result.trajectory) if verification.valid else None
        )
        values = {
            **base_values,
            "status": "completed",
            "solve_result": result,
            "verification_report": verification,
            "state_assignment": assignment,
            "failure_telemetry": (),
            "error_type": None,
            "error_message": None,
        }
    except Exception as exc:
        telemetry = exc.telemetry if isinstance(exc, LLMClientError) else ()
        values = {
            **base_values,
            "status": "failed",
            "solve_result": None,
            "verification_report": None,
            "state_assignment": None,
            "failure_telemetry": telemetry,
            "error_type": type(exc).__name__,
            "error_message": _safe_error_message(exc),
        }
    provisional = FinanceProFlashRolloutRecord.model_construct(record_id="pending", **values)
    return FinanceProFlashRolloutRecord(
        record_id=finance_pro_flash_rollout_record_id(provisional),
        **values,
    )


def _validate_runtime_identity(
    artifact: FinanceTaskStateArtifact,
    expected: PairedTaskContract,
) -> None:
    context, manifest = _paired_runtime_context(artifact)
    observed = {
        "task_id": context.task.task_id,
        "family": artifact.pattern_id,
        "source_artifact_id": artifact.artifact_id,
        "source_omega_context_id": artifact.omega.context_id,
        "paired_omega_context_id": context.context_id,
        "paired_omega_manifest_id": make_omega_component_manifest(context).manifest_id,
        "public_corpus_id": context.public_corpus.corpus_id,
        "public_corpus_hash": context.public_corpus.corpus_hash,
        "tool_environment_manifest_id": manifest.manifest_id,
        "gold_evidence_count": len(context.task.oracle.gold_evidence_ids),
        "public_evidence_count": len(context.public_corpus.evidence),
    }
    if observed != expected.model_dump(mode="json"):
        raise ValueError("paired task runtime identity differs from the frozen contract")


def finance_pro_flash_rollout_record_id(value: FinanceProFlashRolloutRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_pro_flash_rollout_record:",
    )


def finance_pro_flash_stage_report_id(value: FinanceProFlashStageReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_pro_flash_stage_report:",
    )


def _record_key(record: FinanceProFlashRolloutRecord) -> tuple[ExplorerArm, str, int]:
    return record.arm, record.task_id, record.replicate


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    task_ids: set[str],
    replicas: int,
) -> tuple[FinanceProFlashRolloutRecord, ...]:
    if not path.exists():
        return ()
    records = tuple(
        FinanceProFlashRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    keys: set[tuple[ExplorerArm, str, int]] = set()
    for record in records:
        if record.run_identity != run_identity:
            raise ValueError("paired Pilot checkpoint belongs to another run")
        key = _record_key(record)
        if key in keys:
            raise ValueError("paired Pilot checkpoint contains duplicate attempts")
        keys.add(key)
        if record.task_id not in task_ids or not 0 <= record.replicate < replicas:
            raise ValueError("paired Pilot checkpoint contains an unknown job")
    return records


def _build_stage_report(
    contract: FinanceProFlashPilotContract,
    stage: PilotStage,
    records: tuple[FinanceProFlashRolloutRecord, ...],
    *,
    checkpoint_path: Path,
    records_path: Path,
    historical_count: int,
    discovered_models: dict[ExplorerArm, tuple[str, ...]],
    run_identity: str,
) -> FinanceProFlashStageReport:
    tasks = (
        contract.calibration_tasks if stage == PilotStage.CALIBRATION else contract.discovery_tasks
    )
    task_family = {item.task_id: item.family for item in tasks}
    expected_replicas = (
        contract.calibration_runs_per_task_arm
        if stage == PilotStage.CALIBRATION
        else contract.unconditional_runs_per_task_arm
    )
    expected_keys = {
        (arm, task.task_id, replicate)
        for task in tasks
        for arm in ExplorerArm
        for replicate in range(expected_replicas)
    }
    if {_record_key(item) for item in records} != expected_keys or len(records) != len(
        expected_keys
    ):
        raise ValueError("paired stage records do not exactly cover the frozen jobs")
    grouped: defaultdict[tuple[str, ExplorerArm], list[FinanceProFlashRolloutRecord]] = defaultdict(
        list
    )
    for record in records:
        grouped[(record.task_id, record.arm)].append(record)
    task_metrics = tuple(
        _task_arm_metrics(task_id, task_family[task_id], arm, tuple(grouped[(task_id, arm)]))
        for task_id in sorted(task_family)
        for arm in ExplorerArm
    )
    summaries = tuple(_arm_summary(arm, records, task_metrics) for arm in ExplorerArm)
    summary_by_arm = {item.arm: item for item in summaries}
    metrics_by_key = {(item.task_id, item.arm): item for item in task_metrics}
    diversity_improved = sum(
        _task_diversity_improved(
            metrics_by_key[(task_id, ExplorerArm.PRO)],
            metrics_by_key[(task_id, ExplorerArm.FLASH)],
        )
        for task_id in task_family
    )
    paired_fraction = diversity_improved / len(task_family)
    pro = summary_by_arm[ExplorerArm.PRO]
    flash = summary_by_arm[ExplorerArm.FLASH]
    entropy_gain = flash.mean_natural_state_entropy - pro.mean_natural_state_entropy
    state_gain = flash.mean_accepted_states_per_task - pro.mean_accepted_states_per_task
    gates = (
        _calibration_gates(records, task_family, discovered_models)
        if stage == PilotStage.CALIBRATION
        else _discovery_gates(
            contract,
            pro,
            flash,
            paired_fraction=paired_fraction,
            entropy_gain=entropy_gain,
            state_gain=state_gain,
        )
    )
    passed = all(item.passed for item in gates)
    if stage == PilotStage.CALIBRATION:
        decision = "continue_to_discovery" if passed else "stop_after_calibration"
        next_stage = "paired_unconditional_discovery" if passed else "protocol_repair_only"
    else:
        decision = "advance_to_state_conditioning" if passed else "stop_after_discovery"
        next_stage = "state_conditioning_and_exact_target" if passed else "experiment_stopped"
    values = {
        "contract_id": contract.contract_id,
        "run_identity": run_identity,
        "stage": stage,
        "source_artifacts_sha256": contract.source_artifacts_sha256,
        "checkpoint_sha256": _sha256(checkpoint_path),
        "rollout_records_sha256": _sha256(records_path),
        "requested_rollout_count": len(expected_keys),
        "recorded_rollout_count": len(records),
        "resumed_rollout_count": historical_count,
        "newly_executed_rollout_count": len(records) - historical_count,
        "discovered_models_by_arm": discovered_models,
        "task_arm_metrics": task_metrics,
        "arm_summaries": summaries,
        "paired_diversity_improvement_task_fraction": paired_fraction,
        "mean_state_entropy_gain_flash_minus_pro": entropy_gain,
        "mean_accepted_state_gain_flash_minus_pro": state_gain,
        "gates": gates,
        "decision": decision,
        "next_permitted_stage": next_stage,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "status": "passed" if passed else "failed",
        "schema_version": PRO_FLASH_STAGE_REPORT_VERSION,
    }
    provisional = FinanceProFlashStageReport.model_construct(report_id="pending", **values)
    return FinanceProFlashStageReport(
        report_id=finance_pro_flash_stage_report_id(provisional),
        **values,
    )


def _task_arm_metrics(
    task_id: str,
    family: str,
    arm: ExplorerArm,
    records: tuple[FinanceProFlashRolloutRecord, ...],
) -> TaskArmStageMetrics:
    completed = tuple(item for item in records if item.status == "completed")
    valid = tuple(
        item
        for item in completed
        if item.verification_report is not None and item.verification_report.valid
    )
    states = Counter(
        item.state_assignment.state.state_id for item in valid if item.state_assignment is not None
    )
    decision_hashes = {
        trajectory_decision_trace_hash(item.solve_result.trajectory)
        for item in valid
        if item.solve_result is not None
    }
    tool_sequences = {
        tuple(observation.call.tool_id for observation in item.solve_result.observations)
        for item in valid
        if item.solve_result is not None
    }
    recovery_opportunities = sum(
        bool(item.solve_result and item.solve_result.audit.failed_tool_call_count)
        for item in completed
    )
    successful_recoveries = sum(
        bool(item.solve_result and item.solve_result.audit.error_recovery_count)
        for item in completed
        if item.solve_result and item.solve_result.audit.failed_tool_call_count
    )
    return TaskArmStageMetrics(
        task_id=task_id,
        task_family=family,
        arm=arm,
        attempted_rollout_count=len(records),
        completed_rollout_count=len(completed),
        valid_rollout_count=len(valid),
        answer_correct_count=sum(_check_passed(item, "answer_correct") for item in completed),
        accepted_state_count=len(states),
        natural_state_entropy=_entropy(states),
        decision_trace_diversity_rate=len(decision_hashes) / len(valid) if valid else 0.0,
        tool_sequence_diversity_rate=len(tool_sequences) / len(valid) if valid else 0.0,
        query_reformulation_count=sum(_query_reformulated(item) for item in completed),
        recovery_opportunity_count=recovery_opportunities,
        successful_recovery_count=successful_recoveries,
        verification_action_count=sum(_used_verification(item) for item in completed),
        stop_decision_quality_count=sum(
            _check_passed(item, "stop_after_successful_verification") for item in completed
        ),
    )


def _arm_summary(
    arm: ExplorerArm,
    records: tuple[FinanceProFlashRolloutRecord, ...],
    task_metrics: tuple[TaskArmStageMetrics, ...],
) -> ExplorerArmStageSummary:
    arm_records = tuple(item for item in records if item.arm == arm)
    completed = tuple(item for item in arm_records if item.status == "completed")
    telemetry = tuple(item for record in arm_records for item in _record_telemetry(record))
    observations = tuple(
        observation
        for record in completed
        if record.solve_result is not None
        for observation in record.solve_result.observations
    )
    arm_metrics = tuple(item for item in task_metrics if item.arm == arm)
    failures = Counter(
        item.error_type or "unknown_failure" for item in arm_records if item.status == "failed"
    )
    issues = Counter(
        check.check_id
        for item in completed
        if item.verification_report is not None
        for check in item.verification_report.checks
        if not check.passed
    )
    latencies = [item.latency_ms for item in telemetry if item.latency_ms is not None]
    return ExplorerArmStageSummary(
        arm=arm,
        attempted_rollout_count=len(arm_records),
        completed_rollout_count=len(completed),
        valid_rollout_count=sum(
            bool(item.verification_report and item.verification_report.valid) for item in completed
        ),
        api_call_count=len(telemetry),
        api_call_success_count=sum(item.http_success for item in telemetry),
        json_contract_success_count=sum(item.json_contract_success for item in telemetry),
        answer_correct_count=sum(_check_passed(item, "answer_correct") for item in completed),
        tool_call_count=len(observations),
        successful_tool_call_count=sum(item.status == "succeeded" for item in observations),
        verification_action_count=sum(_used_verification(item) for item in completed),
        stop_decision_quality_count=sum(
            _check_passed(item, "stop_after_successful_verification") for item in completed
        ),
        provenance_complete_sum=sum(
            item.verification_report.evidence_provenance_completeness
            for item in completed
            if item.verification_report is not None
        ),
        accepted_state_count=sum(item.accepted_state_count for item in arm_metrics),
        mean_accepted_states_per_task=_mean(
            [float(item.accepted_state_count) for item in arm_metrics]
        ),
        mean_natural_state_entropy=_mean([item.natural_state_entropy for item in arm_metrics]),
        mean_decision_trace_diversity_rate=_mean(
            [item.decision_trace_diversity_rate for item in arm_metrics]
        ),
        mean_tool_sequence_diversity_rate=_mean(
            [item.tool_sequence_diversity_rate for item in arm_metrics]
        ),
        query_reformulation_count=sum(item.query_reformulation_count for item in arm_metrics),
        recovery_opportunity_count=sum(item.recovery_opportunity_count for item in arm_metrics),
        successful_recovery_count=sum(item.successful_recovery_count for item in arm_metrics),
        total_model_tokens=sum(item.total_tokens or 0 for item in telemetry),
        estimated_cost_usd=sum(item.estimated_cost or 0 for item in telemetry),
        mean_api_latency_ms=_mean([float(item) for item in latencies]),
        failure_counts=dict(sorted(failures.items())),
        verifier_issue_counts=dict(sorted(issues.items())),
    )


def _calibration_gates(
    records: tuple[FinanceProFlashRolloutRecord, ...],
    family_by_id: dict[str, str],
    discovered_models: dict[ExplorerArm, tuple[str, ...]],
) -> tuple[PilotGateResult, ...]:
    model_gate = all(
        EXPECTED_MODELS[arm.value] in models for arm, models in discovered_models.items()
    )
    coverage: dict[tuple[str, ExplorerArm], int] = Counter(
        (family_by_id[item.task_id], item.arm) for item in records if item.status == "completed"
    )
    family_arm_gate = all(
        coverage.get((family, arm), 0) >= 1 for family in EXPECTED_FAMILIES for arm in ExplorerArm
    )
    valid_by_arm = Counter(
        item.arm
        for item in records
        if item.verification_report is not None and item.verification_report.valid
    )
    validity_gate = all(valid_by_arm[arm] >= 1 for arm in ExplorerArm)
    return (
        PilotGateResult(
            gate_id="requested_models_discovered",
            passed=model_gate,
            observed={"exact_model_fraction": float(model_gate)},
            requirement="both frozen model IDs must be listed by the provider",
        ),
        PilotGateResult(
            gate_id="contract_completion_by_family_arm",
            passed=family_arm_gate,
            observed={
                "covered_family_arm_cells": float(sum(value >= 1 for value in coverage.values()))
            },
            requirement="at least one completed rollout in every Family x Arm cell",
        ),
        PilotGateResult(
            gate_id="independent_validity_smoke",
            passed=validity_gate,
            observed={arm.value: float(valid_by_arm[arm]) for arm in ExplorerArm},
            requirement="each arm must produce at least one independently valid trajectory",
        ),
    )


def _discovery_gates(
    contract: FinanceProFlashPilotContract,
    pro: ExplorerArmStageSummary,
    flash: ExplorerArmStageSummary,
    *,
    paired_fraction: float,
    entropy_gain: float,
    state_gain: float,
) -> tuple[PilotGateResult, ...]:
    threshold = contract.thresholds
    validity_drop = max(0.0, pro.validity_rate - flash.validity_rate)
    diversity_gain = (
        entropy_gain >= threshold.minimum_mean_state_entropy_gain
        or state_gain >= threshold.minimum_mean_accepted_state_gain
    )
    return (
        PilotGateResult(
            gate_id="flash_minimum_validity",
            passed=flash.validity_rate >= threshold.minimum_flash_validity_rate,
            observed={"flash_validity_rate": flash.validity_rate},
            requirement=f">={threshold.minimum_flash_validity_rate}",
        ),
        PilotGateResult(
            gate_id="flash_validity_drop_vs_pro",
            passed=validity_drop <= threshold.maximum_flash_validity_drop_vs_pro,
            observed={"validity_drop": validity_drop},
            requirement=f"<={threshold.maximum_flash_validity_drop_vs_pro}",
        ),
        PilotGateResult(
            gate_id="flash_tool_execution",
            passed=(flash.tool_call_success_rate >= threshold.minimum_flash_tool_call_success_rate),
            observed={"flash_tool_call_success_rate": flash.tool_call_success_rate},
            requirement=f">={threshold.minimum_flash_tool_call_success_rate}",
        ),
        PilotGateResult(
            gate_id="flash_provenance",
            passed=(
                flash.evidence_provenance_completeness
                >= threshold.minimum_flash_provenance_completeness
            ),
            observed={
                "flash_evidence_provenance_completeness": (flash.evidence_provenance_completeness)
            },
            requirement=f">={threshold.minimum_flash_provenance_completeness}",
        ),
        PilotGateResult(
            gate_id="flash_end_to_end_accuracy",
            passed=flash.end_to_end_accuracy >= threshold.minimum_flash_end_to_end_accuracy,
            observed={"flash_end_to_end_accuracy": flash.end_to_end_accuracy},
            requirement=f">={threshold.minimum_flash_end_to_end_accuracy}",
        ),
        PilotGateResult(
            gate_id="paired_task_diversity_improvement",
            passed=paired_fraction >= threshold.minimum_paired_diversity_task_fraction,
            observed={"improved_task_fraction": paired_fraction},
            requirement=f">={threshold.minimum_paired_diversity_task_fraction}",
        ),
        PilotGateResult(
            gate_id="aggregate_state_diversity_gain",
            passed=diversity_gain,
            observed={"entropy_gain": entropy_gain, "accepted_state_gain": state_gain},
            requirement=(
                f"entropy_gain>={threshold.minimum_mean_state_entropy_gain} or "
                f"state_gain>={threshold.minimum_mean_accepted_state_gain}"
            ),
        ),
    )


def _task_diversity_improved(
    pro: TaskArmStageMetrics,
    flash: TaskArmStageMetrics,
) -> bool:
    return bool(
        flash.accepted_state_count > pro.accepted_state_count
        or flash.natural_state_entropy >= pro.natural_state_entropy + 0.05
        or flash.decision_trace_diversity_rate >= pro.decision_trace_diversity_rate + 0.10
    )


def _check_passed(record: FinanceProFlashRolloutRecord, check_id: str) -> bool:
    report = record.verification_report
    return bool(report and any(item.check_id == check_id and item.passed for item in report.checks))


def _query_reformulated(record: FinanceProFlashRolloutRecord) -> bool:
    if record.solve_result is None:
        return False
    queries = [
        canonical_hash(item.call.arguments, prefix="paired_search_arguments:")
        for item in record.solve_result.observations
        if item.call.tool_id == "search_archive"
    ]
    return len(queries) >= 2 and len(set(queries)) >= 2


def _used_verification(record: FinanceProFlashRolloutRecord) -> bool:
    return bool(
        record.solve_result
        and any(
            item.call.tool_id == "cross_check_evidence" for item in record.solve_result.observations
        )
    )


def _record_telemetry(record: FinanceProFlashRolloutRecord) -> tuple[ModelCallTelemetry, ...]:
    if record.solve_result is not None:
        return record.solve_result.audit.telemetry
    return record.failure_telemetry


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
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the frozen Finance Pro/Flash paired Pilot")
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=tuple(item.value for item in PilotStage))
    parser.add_argument("--workers", type=int, default=16)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = run_pro_flash_stage(
        contract_path=args.contract,
        output_dir=args.output_dir,
        stage=PilotStage(args.stage),
        workers=args.workers,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
