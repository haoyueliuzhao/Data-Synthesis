from __future__ import annotations

import argparse
import hashlib
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

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.state import (
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.domains.finance.agent_tools import (
    FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
    FinanceArchiveInteractiveToolRuntime,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import FinanceTaskStateArtifact
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    CAPABILITY_LADDER_CONTRACT_VERSION,
    CAPABILITY_LADDER_RUNNER_VERSION,
    DifficultyTier,
    FinanceCapabilityLadderContract,
    RuntimeTaskContract,
    capability_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial import (
    SCRIPTED_TOOL_POLICY_VERSION,
    scripted_tool_policy_hash,
    scripted_tool_sequence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_explorer_runtime_factorial_runner import (
    FactorialVerificationSummary,
    _bare_verification_summary,
    _iterative_verification_summary,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import _make_evaluator
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_MODELS,
    ExplorerArm,
    _load_artifacts,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentSolver,
    LLMAgentSolver,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_SOLVER_VERSION,
    IterativeAgentFailureArtifact,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolObservation, InMemoryEvidenceToolRuntime

CAPABILITY_LADDER_ROLLOUT_VERSION = "finance_capability_ladder_rollout.v3"
CAPABILITY_LADDER_STAGE_REPORT_VERSION = "finance_capability_ladder_stage_report.v3"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityStage(str, Enum):
    RUNTIME_QUALIFICATION = "runtime_qualification"
    CAPABILITY_CALIBRATION = "capability_calibration"


class CapabilityRuntimeArm(str, Enum):
    DIRECT_FIXED_RETRIEVAL = "direct_fixed_retrieval"
    SCRIPTED_TOOL = "scripted_tool"
    AUTONOMOUS_AGENT = "autonomous_agent"


class CapabilityRolloutRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: CapabilityStage
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    runtime_task_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    difficulty_tier: DifficultyTier
    difficulty_vector_hash: str = Field(min_length=1)
    protocol_profile_hash: str = Field(min_length=1)
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
    budget_exhausted: bool = False
    schema_version: str = CAPABILITY_LADDER_ROLLOUT_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> CapabilityRolloutRecord:
        if self.requested_model != EXPECTED_MODELS[self.model_arm.value]:
            raise ValueError("capability rollout uses the wrong model")
        if self.status == "completed":
            if self.trajectory is None or self.agent_audit is None or self.verification is None:
                raise ValueError("completed capability rollout lacks execution or verification")
            if self.error_type or self.error_message or self.failure_artifact:
                raise ValueError("completed capability rollout contains a failure")
            if self.budget_exhausted:
                raise ValueError("completed capability rollout claims budget exhaustion")
            if self.trajectory.task_id != self.task_id:
                raise ValueError("capability rollout crosses task identities")
            selected = {item.model_selected for item in self.telemetry if item.model_selected}
            if selected != {self.requested_model}:
                raise ValueError("capability rollout did not use exactly its requested model")
            if any(item.fallback_used for item in self.telemetry):
                raise ValueError("capability rollout used a forbidden model fallback")
            if self.verification.valid != (self.state_assignment is not None):
                raise ValueError("only valid capability rollouts may enter the state space")
            if self.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
                if self.observations:
                    raise ValueError("Direct fixed-retrieval control has interactive observations")
            elif not self.observations:
                raise ValueError("interactive capability rollout lacks Host observations")
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
                raise ValueError("failed capability rollout contains completed artifacts")
            if not self.error_type:
                raise ValueError("failed capability rollout lacks an error type")
        if self.record_id != capability_rollout_record_id(self):
            raise ValueError("capability rollout identity is invalid")
        return self


class CapabilityCellSummary(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    task_count: int = Field(ge=1)
    attempted_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    answer_correct_count: int = Field(ge=0)
    final_answer_emission_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    json_contract_success_count: int = Field(ge=0)
    contract_repair_count: int = Field(ge=0)
    host_forced_verification_call_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    observation_replay_count: int = Field(ge=0)
    authority_integrity_count: int = Field(ge=0)
    budget_exhaustion_count: int = Field(ge=0)
    accepted_state_count: int = Field(ge=0)
    mean_state_entropy: float = Field(ge=0)
    mean_decision_trace_diversity: float = Field(ge=0, le=1)
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
    def answer_accuracy(self) -> float:
        return self.answer_correct_count / self.attempted_count

    @property
    def final_answer_emission_rate(self) -> float:
        return self.final_answer_emission_count / self.attempted_count

    @property
    def raw_json_contract_rate(self) -> float:
        return (
            self.json_contract_success_count / self.api_call_count if self.api_call_count else 0.0
        )

    @property
    def bounded_json_contract_resolution_rate(self) -> float:
        logical_calls = self.api_call_count - self.contract_repair_count
        return self.json_contract_success_count / logical_calls if logical_calls > 0 else 0.0

    @property
    def tool_technical_success_rate(self) -> float:
        return (
            self.successful_tool_call_count / self.tool_call_count if self.tool_call_count else 0.0
        )

    @property
    def host_verification_repair_rate(self) -> float:
        return self.host_forced_verification_call_count / self.attempted_count

    @property
    def observation_replay_rate(self) -> float:
        return self.observation_replay_count / self.completed_count if self.completed_count else 0.0

    @property
    def authority_integrity_rate(self) -> float:
        return (
            self.authority_integrity_count / self.completed_count if self.completed_count else 0.0
        )


class CapabilityGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    passed: bool
    observed: dict[str, float]
    requirement: str = Field(min_length=1)


class CapabilityStageReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    stage: CapabilityStage
    checkpoint_sha256: str = Field(min_length=64, max_length=64)
    rollout_records_sha256: str = Field(min_length=64, max_length=64)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    resumed_rollout_count: int = Field(ge=0)
    newly_executed_rollout_count: int = Field(ge=0)
    discovered_models_by_arm: dict[ExplorerArm, tuple[str, ...]]
    cell_summaries: tuple[CapabilityCellSummary, ...] = Field(min_length=4, max_length=6)
    gates: tuple[CapabilityGate, ...] = Field(min_length=1)
    semantic_ladder_audit_hash: str = Field(min_length=1)
    semantic_frontier_ready: bool
    decision: Literal[
        "advance_to_capability_calibration",
        "advance_to_frontier_task_construction",
        "stop_for_protocol_repair",
        "advance_to_beneficiary_screening",
        "redesign_capability_ladder",
    ]
    next_permitted_stage: Literal[
        "capability_calibration",
        "frontier_task_construction_only",
        "protocol_repair_only",
        "beneficiary_frontier_screening",
        "task_ladder_redesign_only",
    ]
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    status: Literal["passed", "failed"]
    schema_version: str = CAPABILITY_LADDER_STAGE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityStageReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("capability stage report is incomplete")
        if self.resumed_rollout_count + self.newly_executed_rollout_count != (
            self.requested_rollout_count
        ):
            raise ValueError("capability stage resume accounting is inconsistent")
        expected_runtimes = (
            {CapabilityRuntimeArm.SCRIPTED_TOOL, CapabilityRuntimeArm.AUTONOMOUS_AGENT}
            if self.stage == CapabilityStage.RUNTIME_QUALIFICATION
            else set(CapabilityRuntimeArm)
        )
        expected_cells = {
            (model, runtime) for model in ExplorerArm for runtime in expected_runtimes
        }
        observed_cells = {(item.model_arm, item.runtime_arm) for item in self.cell_summaries}
        if observed_cells != expected_cells:
            raise ValueError("capability report lacks a Model x Runtime cell")
        passed = all(item.passed for item in self.gates)
        if passed != (self.status == "passed"):
            raise ValueError("capability report status differs from its gates")
        if self.stage == CapabilityStage.RUNTIME_QUALIFICATION:
            if not passed:
                expected_decision = "stop_for_protocol_repair"
                expected_next = "protocol_repair_only"
            elif self.semantic_frontier_ready:
                expected_decision = "advance_to_capability_calibration"
                expected_next = "capability_calibration"
            else:
                expected_decision = "advance_to_frontier_task_construction"
                expected_next = "frontier_task_construction_only"
        else:
            if not self.semantic_frontier_ready:
                raise ValueError("capability calibration used an unauthorized semantic ladder")
            expected_decision = (
                "advance_to_beneficiary_screening" if passed else "redesign_capability_ladder"
            )
            expected_next = (
                "beneficiary_frontier_screening" if passed else "task_ladder_redesign_only"
            )
        if self.decision != expected_decision or self.next_permitted_stage != expected_next:
            raise ValueError("capability report violates its fail-closed transition")
        if self.report_id != capability_stage_report_id(self):
            raise ValueError("capability report identity is invalid")
        return self


def _capability_run_identity(
    contract: FinanceCapabilityLadderContract,
    stage: CapabilityStage,
    tasks: tuple[RuntimeTaskContract, ...],
    runtimes: tuple[CapabilityRuntimeArm, ...],
    replicas: int,
) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "stage": stage.value,
            "runner_version": CAPABILITY_LADDER_RUNNER_VERSION,
            "runtime_task_ids": tuple(sorted(item.runtime_task_id for item in tasks)),
            "replicas": replicas,
            "runtimes": tuple(item.value for item in runtimes),
        },
        prefix="finance_capability_ladder_run:",
    )


def run_capability_ladder_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    stage: CapabilityStage,
    workers: int,
) -> CapabilityStageReport:
    if workers < 1:
        raise ValueError("capability workers must be positive")
    contract = FinanceCapabilityLadderContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if contract.schema_version != CAPABILITY_LADDER_CONTRACT_VERSION:
        raise ValueError("capability ladder contract version is unsupported")
    _verify_frozen_inputs(contract)
    if stage == CapabilityStage.CAPABILITY_CALIBRATION:
        _require_passing_qualification(output_dir, contract)
    tasks = (
        contract.qualification_tasks
        if stage == CapabilityStage.RUNTIME_QUALIFICATION
        else contract.frontier_tasks
    )
    runtimes = (
        (CapabilityRuntimeArm.SCRIPTED_TOOL, CapabilityRuntimeArm.AUTONOMOUS_AGENT)
        if stage == CapabilityStage.RUNTIME_QUALIFICATION
        else tuple(CapabilityRuntimeArm)
    )
    replicas = (
        contract.qualification_runs_per_task_model_runtime
        if stage == CapabilityStage.RUNTIME_QUALIFICATION
        else contract.capability_runs_per_task_model_runtime
    )
    task_by_id = {item.task_id: item for item in tasks}
    artifacts = _load_artifacts(Path(contract.source_artifacts_path), set(task_by_id))
    run_identity = _capability_run_identity(contract, stage, tasks, runtimes, replicas)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"{stage.value}.checkpoint.jsonl"
    records_path = output_dir / f"{stage.value}_rollouts.jsonl"
    report_path = output_dir / f"finance_{stage.value}_report.json"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        task_ids=set(task_by_id),
        replicas=replicas,
        runtimes=set(runtimes),
    )
    records = {_record_key(item): item for item in historical}
    all_jobs = [
        (model, runtime, task_id, replicate)
        for task_id in sorted(task_by_id)
        for replicate in range(replicas)
        for model in ExplorerArm
        for runtime in runtimes
    ]
    jobs = [item for item in all_jobs if item not in records]
    completed = len(records)
    print(
        f"[capability:{stage.value}] resuming {completed}/{len(all_jobs)}; "
        f"executing {len(jobs)} jobs with {workers} workers",
        flush=True,
    )
    if not jobs and report_path.exists():
        ordered = tuple(records[item] for item in all_jobs)
        report = CapabilityStageReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        _validate_completed_stage_report_metadata(
            report,
            contract=contract,
            stage=stage,
            run_identity=run_identity,
            expected_rollout_count=len(all_jobs),
            checkpoint_path=checkpoint_path,
        )
        if records_path.exists() and report.rollout_records_sha256 != _sha256(records_path):
            raise ValueError("completed capability report rollout hash changed")
        _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
        _validate_completed_stage_report(
            report,
            contract=contract,
            stage=stage,
            run_identity=run_identity,
            expected_rollout_count=len(all_jobs),
            checkpoint_path=checkpoint_path,
            records_path=records_path,
        )
        print(
            f"[capability:{stage.value}] returning frozen completed report {report.report_id}",
            flush=True,
        )
        return report

    model_contracts = {item.arm: item for item in contract.model_contracts}
    clients = {
        arm: OpenAICompatibleJsonClient(
            item.config.model_copy(
                update={"contract_repair_attempts": contract.model_contract_repair_attempts}
            )
        )
        for arm, item in model_contracts.items()
    }
    discovered = {arm: client.discover_models() for arm, client in clients.items()}
    for arm, models in discovered.items():
        if EXPECTED_MODELS[arm.value] not in models:
            raise ValueError(f"provider did not list the frozen {arm.value} model")
    if jobs:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
            future_map = {
                executor.submit(
                    _run_one,
                    contract,
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
                if completed == len(all_jobs) or completed % max(1, min(workers, 24)) == 0:
                    print(
                        f"[capability:{stage.value}] completed {completed}/{len(all_jobs)}",
                        flush=True,
                    )
    ordered = tuple(records[item] for item in all_jobs)
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    report = _build_report(
        contract,
        stage,
        ordered,
        checkpoint_path=checkpoint_path,
        records_path=records_path,
        historical_count=len(historical),
        discovered=discovered,
        run_identity=run_identity,
    )
    _write_json_atomic(
        report_path,
        report.model_dump(mode="json"),
    )
    return report


def _validate_completed_stage_report(
    report: CapabilityStageReport,
    *,
    contract: FinanceCapabilityLadderContract,
    stage: CapabilityStage,
    run_identity: str,
    expected_rollout_count: int,
    checkpoint_path: Path,
    records_path: Path,
) -> None:
    _validate_completed_stage_report_metadata(
        report,
        contract=contract,
        stage=stage,
        run_identity=run_identity,
        expected_rollout_count=expected_rollout_count,
        checkpoint_path=checkpoint_path,
    )
    if report.rollout_records_sha256 != _sha256(records_path):
        raise ValueError("completed capability report rollout hash changed")


def _validate_completed_stage_report_metadata(
    report: CapabilityStageReport,
    *,
    contract: FinanceCapabilityLadderContract,
    stage: CapabilityStage,
    run_identity: str,
    expected_rollout_count: int,
    checkpoint_path: Path,
) -> None:
    if report.contract_id != contract.contract_id:
        raise ValueError("completed capability report belongs to another contract")
    if report.run_identity != run_identity or report.stage != stage:
        raise ValueError("completed capability report belongs to another stage run")
    if (
        report.requested_rollout_count != expected_rollout_count
        or report.recorded_rollout_count != expected_rollout_count
    ):
        raise ValueError("completed capability report has the wrong rollout denominator")
    if report.checkpoint_sha256 != _sha256(checkpoint_path):
        raise ValueError("completed capability report checkpoint hash changed")
    if report.semantic_ladder_audit_hash != contract.semantic_ladder_audit.audit_hash:
        raise ValueError("completed capability report uses another semantic ladder audit")


def _run_one(
    contract: FinanceCapabilityLadderContract,
    stage: CapabilityStage,
    model_arm: ExplorerArm,
    runtime_arm: CapabilityRuntimeArm,
    artifact: FinanceTaskStateArtifact,
    task_contract: RuntimeTaskContract,
    replicate: int,
    run_identity: str,
    client: OpenAICompatibleJsonClient,
) -> CapabilityRolloutRecord:
    attempt_id = canonical_hash(
        {
            "run_identity": run_identity,
            "model_arm": model_arm.value,
            "runtime_arm": runtime_arm.value,
            "runtime_task_id": task_contract.runtime_task_id,
            "replicate": replicate,
            "seed": contract.random_seed,
        },
        prefix="finance_capability_rollout_attempt:",
    )
    base_values = {
        "run_identity": run_identity,
        "contract_id": contract.contract_id,
        "stage": stage,
        "model_arm": model_arm,
        "runtime_arm": runtime_arm,
        "runtime_task_id": task_contract.runtime_task_id,
        "task_id": task_contract.task_id,
        "task_family": task_contract.family,
        "difficulty_tier": task_contract.tier,
        "difficulty_vector_hash": task_contract.difficulty.vector_hash,
        "protocol_profile_hash": contract.protocol_profile.profile_hash,
        "replicate": replicate,
        "attempt_id": attempt_id,
        "requested_model": EXPECTED_MODELS[model_arm.value],
        "model_config_hash": client.config.public_manifest_hash,
        "schema_version": CAPABILITY_LADDER_ROLLOUT_VERSION,
    }
    try:
        context, manifest = capability_runtime_context(
            artifact,
            task_contract.tier,
            contract.protocol_profile,
        )
        _verify_runtime_task(task_contract, context, manifest, contract)
        if runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
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
            observations: tuple[AgentToolObservation, ...] = ()
            telemetry = result.audit.telemetry
            audit = result.audit.model_dump(mode="json")
            verification_payload = validity.model_dump(mode="json")
            trajectory = result.trajectory
        else:
            runtime = FinanceArchiveInteractiveToolRuntime(context.public_corpus, manifest)
            sequence = (
                scripted_tool_sequence(task_contract.family)
                if runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL
                else ()
            )
            result = IterativeAgentSolver(
                client,
                mode=(
                    "scripted_tool"
                    if runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL
                    else "autonomous_agent"
                ),
                maximum_total_tokens=contract.maximum_model_tokens_per_rollout,
                scripted_tool_sequence=sequence,
                protocol_profile=contract.protocol_profile,
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
            observations = result.observations
            telemetry = result.audit.telemetry
            audit = result.audit.model_dump(mode="json")
            verification_payload = validity.model_dump(mode="json")
            trajectory = result.trajectory
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
            "budget_exhausted": False,
        }
    except Exception as exc:
        telemetry = tuple(getattr(exc, "telemetry", ()))
        failure = getattr(exc, "failure_artifact", None)
        message = _safe_error_message(exc)
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
            "error_message": message,
            "budget_exhausted": _is_budget_exhaustion(message),
        }
    provisional = CapabilityRolloutRecord.model_construct(record_id="pending", **values)
    return CapabilityRolloutRecord(
        record_id=capability_rollout_record_id(provisional),
        **values,
    )


def capability_rollout_record_id(value: CapabilityRolloutRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_capability_ladder_rollout:",
    )


def capability_stage_report_id(value: CapabilityStageReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_ladder_stage_report:",
    )


def _verify_frozen_inputs(contract: FinanceCapabilityLadderContract) -> None:
    current_versions = {
        "toolset_version": FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
        "runtime_version": FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
        "solver_version": ITERATIVE_AGENT_SOLVER_VERSION,
        "verifier_version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
        "scripted_tool_policy_version": SCRIPTED_TOOL_POLICY_VERSION,
    }
    frozen_versions = {
        "toolset_version": contract.toolset_version,
        "runtime_version": contract.runtime_version,
        "solver_version": contract.solver_version,
        "verifier_version": contract.verifier_version,
        "scripted_tool_policy_version": contract.scripted_tool_policy_version,
    }
    if frozen_versions != current_versions:
        raise ValueError("frozen capability implementation versions are stale")
    if contract.scripted_tool_policy_hash != scripted_tool_policy_hash():
        raise ValueError("frozen scripted tool policy changed")
    if contract.verifier_manifest_hash != FinanceIterativeAgentVerifier().manifest_hash:
        raise ValueError("frozen iterative verifier manifest changed")
    paths = (
        (Path(contract.source_artifacts_path), contract.source_artifacts_sha256),
        (Path(contract.model_source_contract_path), contract.model_source_contract_sha256),
        (Path(contract.finance_archive_config_path), contract.finance_archive_config_sha256),
    )
    for path, expected in paths:
        if _sha256(path) != expected:
            raise ValueError(f"frozen capability input changed: {path}")
    for item in contract.exclusions:
        if _sha256(Path(item.path)) != item.sha256:
            raise ValueError(f"frozen capability exclusion changed: {item.path}")


def _verify_runtime_task(
    frozen: RuntimeTaskContract,
    context: Any,
    manifest: Any,
    contract: FinanceCapabilityLadderContract,
) -> None:
    if context.context_id != frozen.runtime_omega_context_id:
        raise ValueError("runtime context differs from the frozen ladder")
    if manifest.manifest_id != frozen.tool_environment_manifest_id:
        raise ValueError("runtime tool environment differs from the frozen ladder")
    if canonical_hash(context.task.public, prefix="capability_public_task_view:") != (
        frozen.public_task_view_hash
    ):
        raise ValueError("public task view differs from the frozen ladder")
    if frozen.protocol_profile_hash != contract.protocol_profile.profile_hash:
        raise ValueError("runtime task uses another protocol profile")


def _record_key(
    record: CapabilityRolloutRecord,
) -> tuple[ExplorerArm, CapabilityRuntimeArm, str, int]:
    return record.model_arm, record.runtime_arm, record.task_id, record.replicate


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    task_ids: set[str],
    replicas: int,
    runtimes: set[CapabilityRuntimeArm],
) -> tuple[CapabilityRolloutRecord, ...]:
    if not path.exists():
        return ()
    records = tuple(
        CapabilityRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    keys: set[tuple[ExplorerArm, CapabilityRuntimeArm, str, int]] = set()
    for record in records:
        if record.run_identity != run_identity:
            raise ValueError("capability checkpoint belongs to another run")
        key = _record_key(record)
        if key in keys:
            raise ValueError("capability checkpoint contains duplicate attempts")
        keys.add(key)
        if (
            record.task_id not in task_ids
            or record.runtime_arm not in runtimes
            or not 0 <= record.replicate < replicas
        ):
            raise ValueError("capability checkpoint contains an unknown job")
    return records


def _build_report(
    contract: FinanceCapabilityLadderContract,
    stage: CapabilityStage,
    records: tuple[CapabilityRolloutRecord, ...],
    *,
    checkpoint_path: Path,
    records_path: Path,
    historical_count: int,
    discovered: dict[ExplorerArm, tuple[str, ...]],
    run_identity: str,
) -> CapabilityStageReport:
    runtimes = (
        (CapabilityRuntimeArm.SCRIPTED_TOOL, CapabilityRuntimeArm.AUTONOMOUS_AGENT)
        if stage == CapabilityStage.RUNTIME_QUALIFICATION
        else tuple(CapabilityRuntimeArm)
    )
    summaries = tuple(
        _cell_summary(model, runtime, records) for model in ExplorerArm for runtime in runtimes
    )
    gates = (
        _qualification_gates(contract, summaries, discovered)
        if stage == CapabilityStage.RUNTIME_QUALIFICATION
        else _capability_gates(contract, summaries)
    )
    passed = all(item.passed for item in gates)
    if stage == CapabilityStage.RUNTIME_QUALIFICATION:
        if not passed:
            decision = "stop_for_protocol_repair"
            next_stage = "protocol_repair_only"
        elif contract.semantic_ladder_audit.semantic_frontier_ready:
            decision = "advance_to_capability_calibration"
            next_stage = "capability_calibration"
        else:
            decision = "advance_to_frontier_task_construction"
            next_stage = "frontier_task_construction_only"
    else:
        decision = "advance_to_beneficiary_screening" if passed else "redesign_capability_ladder"
        next_stage = "beneficiary_frontier_screening" if passed else "task_ladder_redesign_only"
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
        "cell_summaries": summaries,
        "gates": gates,
        "semantic_ladder_audit_hash": contract.semantic_ladder_audit.audit_hash,
        "semantic_frontier_ready": contract.semantic_ladder_audit.semantic_frontier_ready,
        "decision": decision,
        "next_permitted_stage": next_stage,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
        "status": "passed" if passed else "failed",
        "schema_version": CAPABILITY_LADDER_STAGE_REPORT_VERSION,
    }
    provisional = CapabilityStageReport.model_construct(report_id="pending", **values)
    return CapabilityStageReport(report_id=capability_stage_report_id(provisional), **values)


def _cell_summary(
    model: ExplorerArm,
    runtime: CapabilityRuntimeArm,
    records: tuple[CapabilityRolloutRecord, ...],
) -> CapabilityCellSummary:
    selected = tuple(
        item for item in records if item.model_arm == model and item.runtime_arm == runtime
    )
    completed = tuple(item for item in selected if item.status == "completed")
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
    by_task: defaultdict[str, list[CapabilityRolloutRecord]] = defaultdict(list)
    for item in selected:
        by_task[item.task_id].append(item)
    state_counts: list[int] = []
    entropies: list[float] = []
    trace_diversities: list[float] = []
    for task_records in by_task.values():
        valid = [item for item in task_records if item.state_assignment is not None]
        states = Counter(
            item.state_assignment.state.state_id
            for item in valid
            if item.state_assignment is not None
        )
        traces = {
            trajectory_decision_trace_hash(item.trajectory)
            for item in valid
            if item.trajectory is not None
        }
        state_counts.append(len(states))
        entropies.append(_entropy(states))
        trace_diversities.append(len(traces) / len(valid) if valid else 0.0)
    latencies = [item.latency_ms for item in telemetry if item.latency_ms is not None]
    return CapabilityCellSummary(
        model_arm=model,
        runtime_arm=runtime,
        task_count=len(by_task),
        attempted_count=len(selected),
        completed_count=len(completed),
        valid_count=sum(bool(item.verification and item.verification.valid) for item in completed),
        answer_correct_count=sum(
            bool(item.verification and item.verification.answer_correct) for item in completed
        ),
        final_answer_emission_count=sum(
            bool(item.trajectory and item.trajectory.final_answer) for item in completed
        ),
        api_call_count=len(telemetry),
        json_contract_success_count=sum(item.json_contract_success for item in telemetry),
        contract_repair_count=sum(_contract_repairs(item) for item in selected),
        tool_call_count=len(observations),
        host_forced_verification_call_count=sum(
            int((item.agent_audit or {}).get("host_forced_verification_call_count", 0))
            for item in completed
        ),
        successful_tool_call_count=sum(item.status == "succeeded" for item in observations),
        observation_replay_count=sum(_observation_replay_ok(item) for item in completed),
        authority_integrity_count=sum(_authority_integrity_ok(item) for item in completed),
        budget_exhaustion_count=sum(item.budget_exhausted for item in selected),
        accepted_state_count=sum(state_counts),
        mean_state_entropy=_mean(entropies),
        mean_decision_trace_diversity=_mean(trace_diversities),
        total_model_tokens=sum(item.total_tokens or 0 for item in telemetry),
        estimated_cost_usd=sum(item.estimated_cost or 0 for item in telemetry),
        mean_api_latency_ms=_mean([float(item) for item in latencies]),
        failure_counts=dict(sorted(failures.items())),
        verifier_issue_counts=dict(sorted(issues.items())),
    )


def _qualification_gates(
    contract: FinanceCapabilityLadderContract,
    summaries: tuple[CapabilityCellSummary, ...],
    discovered: dict[ExplorerArm, tuple[str, ...]],
) -> tuple[CapabilityGate, ...]:
    threshold = contract.runtime_qualification_thresholds
    model_gate = all(EXPECTED_MODELS[arm.value] in values for arm, values in discovered.items())
    completion = min(item.completion_rate for item in summaries)
    json_rate = min(item.raw_json_contract_rate for item in summaries)
    bounded_json_rate = min(item.bounded_json_contract_resolution_rate for item in summaries)
    tool_rate = min(item.tool_technical_success_rate for item in summaries)
    answer_rate = min(item.final_answer_emission_rate for item in summaries)
    replay_rate = min(item.observation_replay_rate for item in summaries)
    authority_rate = min(item.authority_integrity_rate for item in summaries)
    exhausted = sum(item.budget_exhaustion_count for item in summaries)
    host_repair_rate = max(
        item.host_verification_repair_rate
        for item in summaries
        if item.runtime_arm == CapabilityRuntimeArm.AUTONOMOUS_AGENT
    )
    return (
        CapabilityGate(
            gate_id="requested_models_discovered",
            passed=model_gate,
            observed={"exact_model_fraction": float(model_gate)},
            requirement="both exact DeepSeek model IDs must be listed",
        ),
        CapabilityGate(
            gate_id="bounded_repair_completion",
            passed=completion >= threshold.minimum_completion_rate,
            observed={"minimum_cell_completion_rate": completion},
            requirement=f">={threshold.minimum_completion_rate}",
        ),
        CapabilityGate(
            gate_id="raw_json_response_contract",
            passed=json_rate >= threshold.minimum_raw_json_contract_rate,
            observed={"minimum_cell_api_json_rate": json_rate},
            requirement=f">={threshold.minimum_raw_json_contract_rate}",
        ),
        CapabilityGate(
            gate_id="bounded_json_contract_resolution",
            passed=bounded_json_rate >= threshold.minimum_bounded_json_resolution_rate,
            observed={"minimum_cell_bounded_json_resolution_rate": bounded_json_rate},
            requirement=f">={threshold.minimum_bounded_json_resolution_rate}",
        ),
        CapabilityGate(
            gate_id="tool_technical_success",
            passed=tool_rate >= threshold.minimum_tool_technical_success_rate,
            observed={"minimum_cell_tool_success_rate": tool_rate},
            requirement=f">={threshold.minimum_tool_technical_success_rate}",
        ),
        CapabilityGate(
            gate_id="final_answer_emission",
            passed=answer_rate >= threshold.minimum_final_answer_emission_rate,
            observed={"minimum_cell_final_answer_rate": answer_rate},
            requirement=f">={threshold.minimum_final_answer_emission_rate}",
        ),
        CapabilityGate(
            gate_id="no_budget_exhaustion",
            passed=exhausted <= threshold.maximum_budget_exhaustion_count,
            observed={"budget_exhaustion_count": float(exhausted)},
            requirement=f"<={threshold.maximum_budget_exhaustion_count}",
        ),
        CapabilityGate(
            gate_id="observation_replay",
            passed=replay_rate >= threshold.minimum_observation_replay_rate,
            observed={"minimum_cell_replay_rate": replay_rate},
            requirement=f">={threshold.minimum_observation_replay_rate}",
        ),
        CapabilityGate(
            gate_id="host_model_authority_integrity",
            passed=authority_rate >= threshold.minimum_authority_integrity_rate,
            observed={"minimum_cell_authority_integrity_rate": authority_rate},
            requirement=f">={threshold.minimum_authority_integrity_rate}",
        ),
        CapabilityGate(
            gate_id="bounded_host_verification_repair",
            passed=host_repair_rate <= threshold.maximum_host_verification_repair_rate,
            observed={"maximum_cell_host_verification_repair_rate": host_repair_rate},
            requirement=f"<={threshold.maximum_host_verification_repair_rate}",
        ),
    )


def _capability_gates(
    contract: FinanceCapabilityLadderContract,
    summaries: tuple[CapabilityCellSummary, ...],
) -> tuple[CapabilityGate, ...]:
    by_cell = {(item.model_arm, item.runtime_arm): item for item in summaries}
    threshold = contract.capability_calibration_thresholds
    pro = by_cell[(ExplorerArm.PRO, CapabilityRuntimeArm.AUTONOMOUS_AGENT)]
    flash = by_cell[(ExplorerArm.FLASH, CapabilityRuntimeArm.AUTONOMOUS_AGENT)]
    pro_direct = by_cell[(ExplorerArm.PRO, CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL)]
    flash_direct = by_cell[(ExplorerArm.FLASH, CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL)]
    model_gap = pro.validity_rate - flash.validity_rate
    autonomy_gain = max(
        pro.validity_rate - pro_direct.validity_rate,
        flash.validity_rate - flash_direct.validity_rate,
    )
    return (
        CapabilityGate(
            gate_id="pro_frontier_interval",
            passed=threshold.minimum_pro_autonomous_validity
            <= pro.validity_rate
            <= threshold.maximum_pro_autonomous_validity,
            observed={"pro_autonomous_validity": pro.validity_rate},
            requirement=(
                f"[{threshold.minimum_pro_autonomous_validity},"
                f"{threshold.maximum_pro_autonomous_validity}]"
            ),
        ),
        CapabilityGate(
            gate_id="flash_frontier_interval",
            passed=threshold.minimum_flash_autonomous_validity
            <= flash.validity_rate
            <= threshold.maximum_flash_autonomous_validity,
            observed={"flash_autonomous_validity": flash.validity_rate},
            requirement=(
                f"[{threshold.minimum_flash_autonomous_validity},"
                f"{threshold.maximum_flash_autonomous_validity}]"
            ),
        ),
        CapabilityGate(
            gate_id="paired_pro_flash_model_gap",
            passed=model_gap >= threshold.minimum_paired_model_gap,
            observed={"pro_minus_flash_validity": model_gap},
            requirement=f">={threshold.minimum_paired_model_gap}",
        ),
        CapabilityGate(
            gate_id="autonomous_agent_necessity",
            passed=autonomy_gain >= threshold.minimum_autonomy_necessity_gain,
            observed={"maximum_autonomy_gain_vs_fixed_retrieval": autonomy_gain},
            requirement=f">={threshold.minimum_autonomy_necessity_gain}",
        ),
    )


def _contract_repairs(record: CapabilityRolloutRecord) -> int:
    if record.agent_audit is not None:
        value = record.agent_audit.get("contract_repair_count")
        if isinstance(value, int):
            return value
        return sum(
            int(record.agent_audit.get(key, 0))
            for key in (
                "search_contract_repair_count",
                "action_contract_repair_count",
                "answer_contract_repair_count",
            )
        )
    return sum(item.http_success and not item.json_contract_success for item in record.telemetry)


def _observation_replay_ok(record: CapabilityRolloutRecord) -> bool:
    if record.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        return True
    if record.agent_audit is None:
        return False
    observed = tuple(item.observation_id for item in record.observations)
    return observed == tuple(record.agent_audit.get("observation_ids", ()))


def _authority_integrity_ok(record: CapabilityRolloutRecord) -> bool:
    if record.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        return True
    if record.agent_audit is None:
        return False
    stopped = bool(record.agent_audit.get("stopped_by_model"))
    forced = bool(record.agent_audit.get("host_forced_final_answer"))
    return stopped != forced


def _is_budget_exhaustion(message: str) -> bool:
    lowered = message.casefold()
    return "budget" in lowered and any(
        item in lowered for item in ("token", "tool", "observation", "failed")
    )


def _require_passing_qualification(
    output_dir: Path,
    contract: FinanceCapabilityLadderContract,
) -> None:
    path = output_dir / "finance_runtime_qualification_report.json"
    if not path.exists():
        raise ValueError("capability calibration requires a frozen qualification report")
    report = CapabilityStageReport.model_validate_json(path.read_text(encoding="utf-8"))
    stage = CapabilityStage.RUNTIME_QUALIFICATION
    runtimes = (CapabilityRuntimeArm.SCRIPTED_TOOL, CapabilityRuntimeArm.AUTONOMOUS_AGENT)
    replicas = contract.qualification_runs_per_task_model_runtime
    _validate_completed_stage_report(
        report,
        contract=contract,
        stage=stage,
        run_identity=_capability_run_identity(
            contract, stage, contract.qualification_tasks, runtimes, replicas
        ),
        expected_rollout_count=(
            len(contract.qualification_tasks) * len(tuple(ExplorerArm)) * len(runtimes) * replicas
        ),
        checkpoint_path=output_dir / f"{stage.value}.checkpoint.jsonl",
        records_path=output_dir / f"{stage.value}_rollouts.jsonl",
    )
    if report.status != "passed":
        raise ValueError("capability calibration is not authorized by Runtime qualification")
    if not contract.semantic_ladder_audit.semantic_frontier_ready:
        raise ValueError("capability calibration requires a true semantic Frontier")


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Finance v24 capability ladder")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=tuple(item.value for item in CapabilityStage),
        required=True,
    )
    parser.add_argument("--workers", type=int, default=24)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = run_capability_ladder_stage(
        contract_path=args.contract,
        output_dir=args.output_dir,
        stage=CapabilityStage(args.stage),
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
