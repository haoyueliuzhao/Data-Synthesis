from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.trajectory import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.state import (
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    recovery_scenario_from_metadata,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CAPABILITY_BOUNDARY_CONTRACT_VERSION,
    CapabilityRuntimeArm,
    FinanceCapabilityBoundaryContract,
    RuntimeTaskBinding,
    make_v25_native_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    BoundaryStage,
    CapabilityQualificationReport,
    CapabilityRolloutOutcome,
    CapabilityTierLocalizationReport,
    EmpiricalCapabilityInformationAudit,
    capability_rollout_outcome_id,
    make_empirical_information_audit,
    make_qualification_report,
    make_tier_localization_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FRONTIER_VERSION,
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
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
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentSolver,
    LLMAgentSolver,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.iterative import IterativeAgentFailureArtifact
from trusted_synthesis.runtime.agent.schema import (
    FailedActionPlan,
    HostInteractionProgress,
    ModelCallTelemetry,
)
from trusted_synthesis.runtime.tools import AgentToolObservation, InMemoryEvidenceToolRuntime

CAPABILITY_BOUNDARY_RUNNER_VERSION = "finance_capability_boundary_runner.v9"
CAPABILITY_BOUNDARY_RECORD_VERSION = "finance_capability_boundary_record.v9"
MODEL_CAPTURED_FAILURES = ("LLMClientError",)


class RolloutExecutionContract(Protocol):
    """Minimal immutable contract consumed by one capability rollout."""

    contract_id: str
    finance_archive_config_path: str
    protocol_profile: Any
    maximum_model_tokens_per_rollout: int


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityBoundaryRolloutRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    stage: BoundaryStage
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    replicate: int = Field(ge=0)
    attempt_id: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    model_config_hash: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_context_hash: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    protocol_profile_hash: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    trajectory: Trajectory | None = None
    agent_audit: dict[str, Any] | None = None
    observations: tuple[AgentToolObservation, ...] = ()
    verification: FactorialVerificationSummary | None = None
    verification_payload: dict[str, Any] | None = None
    state_assignment: TrajectoryStateAssignment | None = None
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    failure_artifact: IterativeAgentFailureArtifact | FailedActionPlan | None = None
    interaction_progress: HostInteractionProgress | None = None
    error_type: str | None = None
    error_message: str | None = None
    budget_exhausted: bool = False
    schema_version: str = CAPABILITY_BOUNDARY_RECORD_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> CapabilityBoundaryRolloutRecord:
        if self.schema_version != CAPABILITY_BOUNDARY_RECORD_VERSION:
            raise ValueError("boundary rollout record version is unsupported")
        if self.requested_model != EXPECTED_MODELS[self.model_arm.value]:
            raise ValueError("boundary rollout uses the wrong model")
        selected = {item.model_selected for item in self.telemetry if item.model_selected}
        if any(item.fallback_used for item in self.telemetry):
            raise ValueError("boundary rollout used a forbidden model fallback")
        if selected and selected != {self.requested_model}:
            raise ValueError("boundary rollout selected a model outside its frozen arm")

        if self.status == "completed":
            if self.trajectory is None or self.agent_audit is None or self.verification is None:
                raise ValueError("completed boundary rollout lacks execution or verification")
            if (
                self.error_type
                or self.error_message
                or self.failure_artifact
                or self.interaction_progress
            ):
                raise ValueError("completed boundary rollout contains a failure")
            if self.budget_exhausted:
                raise ValueError("completed boundary rollout claims budget exhaustion")
            if self.trajectory.task_id != self.task_id:
                raise ValueError("boundary rollout crosses task identities")
            if selected != {self.requested_model}:
                raise ValueError("completed boundary rollout lacks exact-model telemetry")
            if self.verification.valid != (self.state_assignment is not None):
                raise ValueError("only valid boundary rollouts may enter the state space")
            if (
                self.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL
                and self.observations
            ):
                raise ValueError("Direct fixed-retrieval rollout contains observations")
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
                raise ValueError("failed boundary rollout contains completed artifacts")
            if not self.error_type:
                raise ValueError("failed boundary rollout lacks an error type")
            if self.failure_artifact is not None and selected != {self.requested_model}:
                raise ValueError("typed model failure lacks exact-model telemetry")
        if self.record_id != capability_boundary_record_id(self):
            raise ValueError("boundary rollout identity is invalid")
        return self


def run_capability_boundary_stage(
    *,
    contract_path: Path,
    output_dir: Path,
    stage: BoundaryStage,
    workers: int,
) -> (
    CapabilityQualificationReport
    | CapabilityTierLocalizationReport
    | EmpiricalCapabilityInformationAudit
):
    if stage == BoundaryStage.BENEFICIARY_SCREENING:
        raise ValueError("Beneficiary screening uses the isolated local-GPU runner")
    if workers < 1:
        raise ValueError("boundary workers must be positive")
    contract = FinanceCapabilityBoundaryContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if contract.schema_version != CAPABILITY_BOUNDARY_CONTRACT_VERSION:
        raise ValueError("capability boundary contract version is unsupported")
    _verify_frozen_inputs(contract)
    if stage == BoundaryStage.PAIRED_CALIBRATION:
        qualification = _load_passing_qualification(output_dir, contract)
        localization = _load_passing_tier_localization(output_dir, contract, qualification)
        bindings = contract.calibration_bindings
        replicas = contract.calibration_replicas
    elif stage == BoundaryStage.TIER_LOCALIZATION:
        qualification = _load_passing_qualification(output_dir, contract)
        localization = None
        bindings = contract.localization_bindings
        replicas = contract.localization_replicas
    else:
        qualification = None
        localization = None
        bindings = contract.qualification_bindings
        replicas = contract.qualification_replicas
    population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        Path(contract.population_path).read_text(encoding="utf-8")
    )
    if population.schema_version != CAPABILITY_SENSITIVE_FRONTIER_VERSION:
        raise ValueError("capability population version is unsupported")
    tasks = {item.artifact_id: item for item in population.tasks}
    required_task_ids = {item.task_artifact_id for item in bindings}
    if not required_task_ids <= set(tasks):
        raise ValueError("boundary bindings reference missing task artifacts")
    run_identity = _run_identity(contract, stage, bindings, replicas)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"{stage.value}.checkpoint.jsonl"
    records_path = output_dir / f"{stage.value}_records.jsonl"
    outcomes_path = output_dir / f"{stage.value}_outcomes.jsonl"
    report_path = output_dir / f"finance_{stage.value}_report.json"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        bindings=bindings,
        replicas=replicas,
    )
    records = {_record_key(item): item for item in historical}
    jobs = tuple(
        (model, binding, replicate)
        for binding in sorted(bindings, key=lambda item: item.binding_id)
        for replicate in range(replicas)
        for model in ExplorerArm
    )
    pending = tuple(job for job in jobs if (job[0], job[1].binding_id, job[2]) not in records)
    print(
        f"[v25:{stage.value}] resuming {len(records)}/{len(jobs)}; "
        f"executing {len(pending)} with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    clients: dict[ExplorerArm, OpenAICompatibleJsonClient] = {}
    if pending:
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
        discovery_source = "live_provider"
    else:
        discovered, discovery_source = _replay_discovered_models(
            output_dir=output_dir,
            stage=stage,
            run_identity=run_identity,
        )
    for arm in ExplorerArm:
        if EXPECTED_MODELS[arm.value] not in discovered.get(arm, ()):
            raise ValueError(f"provider evidence does not contain frozen {arm.value} model")
    if pending:
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _run_one,
                    contract,
                    stage,
                    model,
                    binding,
                    tasks[binding.task_artifact_id],
                    replicate,
                    run_identity,
                    clients[model],
                ): (model, binding.binding_id, replicate)
                for model, binding, replicate in pending
            }
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                record = future.result()
                if key != _record_key(record):
                    raise ValueError("boundary worker returned another job identity")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                records[key] = record
                if index % 10 == 0 or index == len(futures):
                    print(
                        f"[v25:{stage.value}] completed {len(records)}/{len(jobs)}",
                        flush=True,
                    )
    ordered = tuple(
        records[(model, binding.binding_id, replicate)] for model, binding, replicate in jobs
    )
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    outcomes = tuple(_to_outcome(item, bindings) for item in ordered)
    _write_jsonl_atomic(outcomes_path, (item.model_dump(mode="json") for item in outcomes))
    report: (
        CapabilityQualificationReport
        | CapabilityTierLocalizationReport
        | EmpiricalCapabilityInformationAudit
    )
    if stage == BoundaryStage.RUNTIME_QUALIFICATION:
        report = make_qualification_report(contract, outcomes)
    elif stage == BoundaryStage.TIER_LOCALIZATION:
        if qualification is None:
            raise AssertionError("Tier Localization lost its Qualification authorization")
        report = make_tier_localization_report(contract, qualification, outcomes)
    else:
        if qualification is None or localization is None:
            raise AssertionError("Calibration lost its prerequisite authorization")
        report = make_empirical_information_audit(contract, qualification, outcomes)
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        output_dir / f"{stage.value}_run_manifest.json",
        {
            "run_identity": run_identity,
            "runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "contract_id": contract.contract_id,
            "stage": stage.value,
            "discovered_models": {arm.value: values for arm, values in discovered.items()},
            "model_discovery_source": discovery_source,
            "checkpoint_sha256": _sha256(checkpoint_path),
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(outcomes_path),
            "outcome_set_hash": report.outcome_set_hash,
            "report_id": getattr(report, "report_id", getattr(report, "audit_id", None)),
            "report_schema_version": report.schema_version,
            "report_sha256": _sha256(report_path),
        },
    )
    return report


def _run_one(
    contract: RolloutExecutionContract,
    stage: BoundaryStage,
    model_arm: ExplorerArm,
    binding: RuntimeTaskBinding,
    task: CapabilitySensitiveTaskArtifact,
    replicate: int,
    run_identity: str,
    client: OpenAICompatibleJsonClient,
) -> CapabilityBoundaryRolloutRecord:
    attempt_id = canonical_hash(
        {
            "run_identity": run_identity,
            "model_arm": model_arm.value,
            "binding_id": binding.binding_id,
            "replicate": replicate,
        },
        prefix="finance_v25_boundary_attempt:",
    )
    context, manifest, reference = make_v25_native_runtime_context(
        task, binding.runtime_arm, contract.protocol_profile
    )
    _verify_runtime_binding(binding, context, manifest, reference)
    base = {
        "run_identity": run_identity,
        "contract_id": contract.contract_id,
        "stage": stage,
        "binding_id": binding.binding_id,
        "task_artifact_id": binding.task_artifact_id,
        "task_id": binding.task_id,
        "family": binding.family,
        "model_arm": model_arm,
        "runtime_arm": binding.runtime_arm,
        "replicate": replicate,
        "attempt_id": attempt_id,
        "requested_model": EXPECTED_MODELS[model_arm.value],
        "model_config_hash": client.config.public_manifest_hash,
        "omega_context_id": context.context_id,
        "omega_context_hash": canonical_hash(context, prefix="v25_runtime_omega:"),
        "environment_manifest_id": manifest.manifest_id,
        "environment_manifest_hash": canonical_hash(manifest, prefix="v25_tool_environment:"),
        "protocol_profile_hash": contract.protocol_profile.profile_hash,
    }
    try:
        if binding.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
            if (
                context.task.public.retrieval_track != RetrievalTrack.RESOLVED
                or context.task.public.planning_track != PlanningTrack.PLAN_GIVEN
            ):
                raise ValueError("Direct Runtime did not freeze retrieval and planning")
            result = LLMAgentSolver(client, default_registry()).solve_with_audit(
                context.task.public,
                InMemoryEvidenceToolRuntime(context.evidence_bundle),
            )
            validity = _make_evaluator(Path(contract.finance_archive_config_path)).evaluate(
                context, result.trajectory
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
            verification_payload = validity.model_dump(mode="json")
        else:
            runtime = FinanceArchiveInteractiveToolRuntime(
                context.public_corpus,
                manifest,
                recovery_scenario=recovery_scenario_from_metadata(
                    context.task.public.metadata
                ),
            )
            result = IterativeAgentSolver(
                client,
                mode=(
                    "scripted_tool"
                    if binding.runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL
                    else "autonomous_agent"
                ),
                maximum_total_tokens=contract.maximum_model_tokens_per_rollout,
                scripted_tool_sequence=(
                    binding.scripted_compilation.tool_sequence
                    if binding.scripted_compilation is not None
                    else ()
                ),
                protocol_profile=contract.protocol_profile,
            ).solve_with_audit(context.task.public, runtime)
            validity = FinanceIterativeAgentVerifier().verify(
                context, context.public_corpus, manifest, result
            )
            verification = _iterative_verification_summary(validity)
            assignment = (
                map_trajectory_to_state(context, result.trajectory) if validity.valid else None
            )
            observations = result.observations
            verification_payload = validity.model_dump(mode="json")
        values = {
            **base,
            "status": "completed",
            "trajectory": result.trajectory,
            "agent_audit": result.audit.model_dump(mode="json"),
            "observations": observations,
            "verification": verification,
            "verification_payload": verification_payload,
            "state_assignment": assignment,
            "telemetry": result.audit.telemetry,
            "failure_artifact": None,
            "interaction_progress": None,
            "error_type": None,
            "error_message": None,
            "budget_exhausted": False,
        }
    except Exception as exc:
        failure = getattr(exc, "failure_artifact", None)
        progress = getattr(exc, "interaction_progress", None)
        values = {
            **base,
            "status": "failed",
            "trajectory": None,
            "agent_audit": None,
            "observations": (),
            "verification": None,
            "verification_payload": None,
            "state_assignment": None,
            "telemetry": tuple(getattr(exc, "telemetry", ())),
            "failure_artifact": (
                failure
                if isinstance(failure, (IterativeAgentFailureArtifact, FailedActionPlan))
                else None
            ),
            "interaction_progress": (
                progress if isinstance(progress, HostInteractionProgress) else None
            ),
            "error_type": type(exc).__name__,
            "error_message": _safe_error_message(exc),
            "budget_exhausted": _is_budget_exhaustion(str(exc)),
        }
    provisional = CapabilityBoundaryRolloutRecord.model_construct(record_id="pending", **values)
    return CapabilityBoundaryRolloutRecord(
        record_id=capability_boundary_record_id(provisional), **values
    )


def _to_outcome(
    record: CapabilityBoundaryRolloutRecord,
    bindings: tuple[RuntimeTaskBinding, ...],
) -> CapabilityRolloutOutcome:
    binding = next(item for item in bindings if item.binding_id == record.binding_id)
    completed = record.status == "completed"
    telemetry = record.telemetry
    verification = record.verification
    audit = record.agent_audit or {}
    model_captured_failure = _captured_failure_authority(record, binding)
    terminal = completed or model_captured_failure
    observations = _all_observations(record)
    bounded_tool_resolutions, infrastructure_failures = _tool_resolution_counts(observations)
    valid = bool(completed and verification and verification.valid)
    answer_correct = bool(completed and verification and verification.answer_correct)
    observations_succeeded = all(item.status == "succeeded" for item in observations)
    tool_semantic = bool(
        completed
        and verification
        and observations_succeeded
        and verification.evidence_provenance_completeness == 1.0
    )
    query_reformulated = _query_reformulated(observations)
    recovery_opportunity = any(item.status == "failed" for item in observations)
    recovery_success = bool(
        completed
        and valid
        and recovery_opportunity
        and int(audit.get("error_recovery_count", 0)) > 0
    )
    authority = _authority_integrity(record, binding)
    values = {
        "contract_id": record.contract_id,
        "stage": record.stage,
        "binding_id": record.binding_id,
        "task_artifact_id": record.task_artifact_id,
        "family": record.family,
        "model_arm": record.model_arm,
        "runtime_arm": record.runtime_arm,
        "replicate": record.replicate,
        "completed": terminal,
        "raw_json_contract_success": bool(telemetry)
        and all(item.json_contract_success for item in telemetry),
        "bounded_json_resolution_success": terminal,
        "api_call_count": len(telemetry),
        "json_contract_success_count": sum(item.json_contract_success for item in telemetry),
        "contract_repair_count": _contract_repairs(audit, telemetry),
        "tool_call_count": len(observations),
        "semantically_successful_tool_call_count": sum(
            item.status == "succeeded" for item in observations
        ),
        "bounded_tool_resolution_count": bounded_tool_resolutions,
        "runtime_infrastructure_failure_count": infrastructure_failures,
        "final_answer_emitted": bool(record.trajectory and record.trajectory.final_answer),
        "terminal_result_emitted": terminal,
        "observation_replay_success": _observation_replay(record, observations, binding),
        "authority_integrity_success": authority or _captured_failure_authority(record, binding),
        "host_verification_repair_count": int(audit.get("host_forced_verification_call_count", 0)),
        "budget_exhausted": record.budget_exhausted,
        "deterministic_valid": valid,
        "semantic_answer_correct": answer_correct,
        "valid_success": valid and answer_correct,
        "tool_semantic_success": tool_semantic,
        "verification_success": bool(
            completed and verification and verification.verification_success
        ),
        "query_reformulated": query_reformulated,
        "recovery_opportunity": recovery_opportunity,
        "recovery_success": recovery_success,
        "stop_quality_success": bool(
            completed and verification and verification.stop_decision_quality
        ),
        "state_id": (record.state_assignment.state.state_id if record.state_assignment else None),
        "decision_trace_hash": (
            trajectory_decision_trace_hash(record.trajectory)
            if record.trajectory is not None
            else None
        ),
        "tool_sequence_hash": (
            canonical_hash(
                tuple(item.call.tool_id for item in observations),
                prefix="capability_tool_sequence:",
            )
            if observations
            else None
        ),
        "total_model_tokens": sum(item.total_tokens or 0 for item in telemetry),
        "estimated_cost_usd": sum(item.estimated_cost or 0 for item in telemetry),
        "mean_api_latency_ms": _mean(
            [float(item.latency_ms) for item in telemetry if item.latency_ms is not None]
        ),
    }
    provisional = CapabilityRolloutOutcome.model_construct(outcome_id="pending", **values)
    return CapabilityRolloutOutcome(outcome_id=capability_rollout_outcome_id(provisional), **values)


def _verify_runtime_binding(
    binding: RuntimeTaskBinding,
    context: Any,
    manifest: Any,
    reference: Any,
) -> None:
    observed = {
        "omega_context_id": context.context_id,
        "omega_context_hash": canonical_hash(context, prefix="v25_runtime_omega:"),
        "quality_contract_id": context.quality_contract.contract_id,
        "quality_contract_hash": context.quality_contract.contract_hash,
        "reference_trajectory_id": reference.trajectory_id,
        "reference_trajectory_hash": reference.trajectory_hash,
        "environment_manifest_id": manifest.manifest_id,
        "environment_manifest_hash": canonical_hash(manifest, prefix="v25_tool_environment:"),
        "public_allowed_tools": context.task.public.allowed_tools,
    }
    expected = {key: getattr(binding, key) for key in observed}
    if observed != expected:
        raise ValueError("runtime reconstruction differs from the frozen binding")


def _verify_frozen_inputs(contract: FinanceCapabilityBoundaryContract) -> None:
    paths = (
        (Path(contract.population_path), contract.population_sha256),
        (Path(contract.model_source_contract_path), contract.model_source_contract_sha256),
        (Path(contract.finance_archive_config_path), contract.finance_archive_config_sha256),
    )
    for path, expected in paths:
        if _sha256(path) != expected:
            raise ValueError(f"frozen capability input changed: {path}")


def _load_passing_qualification(
    output_dir: Path,
    contract: FinanceCapabilityBoundaryContract,
) -> CapabilityQualificationReport:
    stage = BoundaryStage.RUNTIME_QUALIFICATION
    report_path = output_dir / "finance_runtime_qualification_report.json"
    checkpoint_path = output_dir / f"{stage.value}.checkpoint.jsonl"
    records_path = output_dir / f"{stage.value}_records.jsonl"
    outcomes_path = output_dir / f"{stage.value}_outcomes.jsonl"
    manifest_path = output_dir / f"{stage.value}_run_manifest.json"
    required = (report_path, checkpoint_path, records_path, outcomes_path, manifest_path)
    if any(not path.is_file() for path in required):
        raise ValueError("calibration requires a complete frozen Qualification run")

    expected_run_identity = _run_identity(
        contract,
        stage,
        contract.qualification_bindings,
        contract.qualification_replicas,
    )
    checkpoint_records = _load_checkpoint(
        checkpoint_path,
        run_identity=expected_run_identity,
        bindings=contract.qualification_bindings,
        replicas=contract.qualification_replicas,
    )
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    expected_jobs = {
        (model, binding.binding_id, replicate)
        for model in ExplorerArm
        for binding in contract.qualification_bindings
        for replicate in range(contract.qualification_replicas)
    }
    if {_record_key(item) for item in records} != expected_jobs or len(records) != len(
        expected_jobs
    ):
        raise ValueError("Qualification records do not exactly cover frozen jobs")
    if {item.record_id for item in checkpoint_records} != {item.record_id for item in records}:
        raise ValueError("Qualification checkpoint and canonical records disagree")

    outcomes = tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    recomputed_outcomes = tuple(
        _to_outcome(item, contract.qualification_bindings) for item in records
    )
    if {item.outcome_id for item in outcomes} != {
        item.outcome_id for item in recomputed_outcomes
    } or len(outcomes) != len(recomputed_outcomes):
        raise ValueError("Qualification outcomes do not replay from canonical records")
    report = CapabilityQualificationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    recomputed_report = make_qualification_report(contract, recomputed_outcomes)
    if report != recomputed_report or report.status != "passed":
        raise ValueError("calibration Qualification is not authorized by replay")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = {
        "run_identity": expected_run_identity,
        "runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
        "contract_id": contract.contract_id,
        "stage": stage.value,
        "checkpoint_sha256": _sha256(checkpoint_path),
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "outcome_set_hash": report.outcome_set_hash,
        "report_id": report.report_id,
        "report_schema_version": report.schema_version,
        "report_sha256": _sha256(report_path),
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise ValueError("Qualification run manifest failed immutable lineage replay")
    return report


def _load_passing_tier_localization(
    output_dir: Path,
    contract: FinanceCapabilityBoundaryContract,
    qualification: CapabilityQualificationReport,
) -> CapabilityTierLocalizationReport:
    stage = BoundaryStage.TIER_LOCALIZATION
    report_path = output_dir / "finance_tier_localization_report.json"
    checkpoint_path = output_dir / f"{stage.value}.checkpoint.jsonl"
    records_path = output_dir / f"{stage.value}_records.jsonl"
    outcomes_path = output_dir / f"{stage.value}_outcomes.jsonl"
    manifest_path = output_dir / f"{stage.value}_run_manifest.json"
    required = (report_path, checkpoint_path, records_path, outcomes_path, manifest_path)
    if any(not path.is_file() for path in required):
        raise ValueError("calibration requires a complete frozen Tier Localization run")
    expected_run_identity = _run_identity(
        contract,
        stage,
        contract.localization_bindings,
        contract.localization_replicas,
    )
    checkpoint_records = _load_checkpoint(
        checkpoint_path,
        run_identity=expected_run_identity,
        bindings=contract.localization_bindings,
        replicas=contract.localization_replicas,
    )
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    expected_jobs = {
        (model, binding.binding_id, replicate)
        for model in ExplorerArm
        for binding in contract.localization_bindings
        for replicate in range(contract.localization_replicas)
    }
    if {_record_key(item) for item in records} != expected_jobs or len(records) != len(
        expected_jobs
    ):
        raise ValueError("Tier Localization records do not exactly cover frozen jobs")
    if {item.record_id for item in checkpoint_records} != {item.record_id for item in records}:
        raise ValueError("Tier Localization checkpoint and canonical records disagree")
    outcomes = tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    recomputed_outcomes = tuple(
        _to_outcome(item, contract.localization_bindings) for item in records
    )
    if {item.outcome_id for item in outcomes} != {
        item.outcome_id for item in recomputed_outcomes
    } or len(outcomes) != len(recomputed_outcomes):
        raise ValueError("Tier Localization outcomes do not replay from canonical records")
    report = CapabilityTierLocalizationReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    recomputed_report = make_tier_localization_report(
        contract, qualification, recomputed_outcomes
    )
    if (
        report != recomputed_report
        or report.next_permitted_stage != "paired_capability_calibration"
    ):
        raise ValueError("paired calibration is not authorized by Tier Localization replay")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = {
        "run_identity": expected_run_identity,
        "runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
        "contract_id": contract.contract_id,
        "stage": stage.value,
        "checkpoint_sha256": _sha256(checkpoint_path),
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "outcome_set_hash": report.outcome_set_hash,
        "report_id": report.report_id,
        "report_schema_version": report.schema_version,
        "report_sha256": _sha256(report_path),
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise ValueError("Tier Localization manifest failed immutable lineage replay")
    return report


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    bindings: tuple[RuntimeTaskBinding, ...],
    replicas: int,
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    if not path.exists():
        return ()
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    binding_ids = {item.binding_id for item in bindings}
    keys = set()
    for record in records:
        key = _record_key(record)
        if key in keys:
            raise ValueError("boundary checkpoint contains duplicate jobs")
        keys.add(key)
        if (
            record.run_identity != run_identity
            or record.binding_id not in binding_ids
            or not 0 <= record.replicate < replicas
        ):
            raise ValueError("boundary checkpoint contains an unknown job")
    return records


def _replay_discovered_models(
    *,
    output_dir: Path,
    stage: BoundaryStage,
    run_identity: str,
) -> tuple[dict[ExplorerArm, tuple[str, ...]], str]:
    path = output_dir / f"{stage.value}_run_manifest.json"
    if not path.is_file():
        return (
            {arm: (EXPECTED_MODELS[arm.value],) for arm in ExplorerArm},
            "checkpoint_contract_replay",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("run_identity") != run_identity or payload.get("stage") != stage.value:
        raise ValueError("existing boundary run manifest belongs to another run")
    raw = payload.get("discovered_models")
    if not isinstance(raw, dict):
        raise ValueError("existing boundary run manifest lacks model discovery evidence")
    discovered = {arm: tuple(str(item) for item in raw.get(arm.value, ())) for arm in ExplorerArm}
    return discovered, "frozen_run_manifest"


def _authority_integrity(
    record: CapabilityBoundaryRolloutRecord,
    binding: RuntimeTaskBinding,
) -> bool:
    if not record.status == "completed":
        return False
    if binding.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        return not record.observations
    audit = record.agent_audit or {}
    stopped = bool(audit.get("stopped_by_model"))
    forced = bool(audit.get("host_forced_final_answer"))
    stopping_integrity = stopped != forced
    if binding.runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL:
        return stopping_integrity and _scripted_tool_authority(
            record.observations,
            (
                binding.scripted_compilation.tool_sequence
                if binding.scripted_compilation is not None
                else ()
            ),
            require_complete=True,
        )
    return stopping_integrity


def _all_observations(
    record: CapabilityBoundaryRolloutRecord,
) -> tuple[AgentToolObservation, ...]:
    if record.observations:
        return record.observations
    if not isinstance(record.failure_artifact, IterativeAgentFailureArtifact):
        return ()
    return record.failure_artifact.observations


def _tool_resolution_counts(
    observations: tuple[AgentToolObservation, ...],
) -> tuple[int, int]:
    infrastructure_failures = sum(
        bool(item.error_code and item.error_code.startswith("runtime_exception:"))
        for item in observations
    )
    return len(observations) - infrastructure_failures, infrastructure_failures


def _query_reformulated(observations: tuple[AgentToolObservation, ...]) -> bool:
    queries = [
        canonical_hash(item.call.arguments, prefix="capability_search_arguments:")
        for item in observations
        if item.call.tool_id in {"search_archive", "query_structured_fact"}
    ]
    return len(queries) >= 2 and len(set(queries)) >= 2


def _captured_failure_authority(
    record: CapabilityBoundaryRolloutRecord,
    binding: RuntimeTaskBinding,
) -> bool:
    artifact = record.failure_artifact
    if record.error_type not in MODEL_CAPTURED_FAILURES or artifact is None:
        return False
    if binding.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        progress = record.interaction_progress
        return bool(
            isinstance(artifact, FailedActionPlan)
            and artifact.task_id == record.task_id
            and artifact.failure_category == "semantic_action"
            and progress is not None
            and progress.action_plan_attempted
            and progress.action_plan_contract_succeeded
            and not progress.host_execution_evaluable
        )
    if not isinstance(artifact, IterativeAgentFailureArtifact):
        return False
    expected_mode = (
        "scripted_tool"
        if binding.runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL
        else "autonomous_agent"
    )
    artifact_authorized = (
        artifact.environment_manifest_id == binding.environment_manifest_id
        and artifact.mode == expected_mode
        and artifact.task_id == record.task_id
        and artifact.protocol_profile_hash == record.protocol_profile_hash
    )
    if not artifact_authorized:
        return False
    if binding.runtime_arm == CapabilityRuntimeArm.SCRIPTED_TOOL:
        return _scripted_tool_authority(
            artifact.observations,
            (
                binding.scripted_compilation.tool_sequence
                if binding.scripted_compilation is not None
                else ()
            ),
            require_complete=False,
        )
    return True


def _scripted_tool_authority(
    observations: tuple[AgentToolObservation, ...],
    sequence: tuple[str, ...],
    *,
    require_complete: bool,
) -> bool:
    successful_step = 0
    for observation in observations:
        if successful_step >= len(sequence):
            return False
        if observation.call.tool_id != sequence[successful_step]:
            return False
        successful_step += int(observation.status == "succeeded")
    return not require_complete or successful_step == len(sequence)


def _observation_replay(
    record: CapabilityBoundaryRolloutRecord,
    observations: tuple[AgentToolObservation, ...],
    binding: RuntimeTaskBinding,
) -> bool:
    if record.status != "completed":
        return _captured_failure_authority(record, binding)
    if record.runtime_arm == CapabilityRuntimeArm.DIRECT_FIXED_RETRIEVAL:
        return not observations
    observed = tuple(item.observation_id for item in observations)
    return observed == tuple((record.agent_audit or {}).get("observation_ids", ()))


def _contract_repairs(audit: dict[str, Any], telemetry: tuple[ModelCallTelemetry, ...]) -> int:
    value = audit.get("contract_repair_count")
    if isinstance(value, int):
        return value
    total = sum(
        int(audit.get(key, 0))
        for key in (
            "search_contract_repair_count",
            "action_contract_repair_count",
            "answer_contract_repair_count",
        )
    )
    return total or sum(item.http_success and not item.json_contract_success for item in telemetry)


def _run_identity(
    contract: FinanceCapabilityBoundaryContract,
    stage: BoundaryStage,
    bindings: tuple[RuntimeTaskBinding, ...],
    replicas: int,
) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "stage": stage.value,
            "runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "binding_ids": tuple(sorted(item.binding_id for item in bindings)),
            "replicas": replicas,
        },
        prefix="finance_capability_boundary_run:",
    )


def _record_key(
    record: CapabilityBoundaryRolloutRecord,
) -> tuple[ExplorerArm, str, int]:
    return record.model_arm, record.binding_id, record.replicate


def capability_boundary_record_id(value: CapabilityBoundaryRolloutRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_capability_boundary_record:",
    )


def _safe_error_message(exc: Exception) -> str:
    value = re.sub(
        r"(?i)(api[_ -]?key|authorization|bearer)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        str(exc),
    )
    return value[:2_000]


def _is_budget_exhaustion(message: str) -> bool:
    lowered = message.casefold()
    return (
        "budget" in lowered
        and "failed-tool" not in lowered
        and any(item in lowered for item in ("token", "tool-call", "observation"))
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_jsonl_atomic(path: Path, payloads: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the v25-native capability boundary")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=("qualification", "localization", "calibration"),
        required=True,
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    stage = {
        "qualification": BoundaryStage.RUNTIME_QUALIFICATION,
        "localization": BoundaryStage.TIER_LOCALIZATION,
        "calibration": BoundaryStage.PAIRED_CALIBRATION,
    }[args.stage]
    report = run_capability_boundary_stage(
        contract_path=args.contract,
        output_dir=args.output_dir,
        stage=stage,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
