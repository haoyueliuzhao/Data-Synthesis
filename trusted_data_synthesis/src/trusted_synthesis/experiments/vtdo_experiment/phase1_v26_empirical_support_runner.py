from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.core.trajectory.state import trajectory_decision_trace_hash
from trusted_synthesis.domains.finance.executable_support_runtime import (
    FinanceExecutableSupportRuntime,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceTypedRecoveryScenario,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    MAXIMUM_TOTAL_ESTIMATED_COST_USD,
    CapabilityMechanismSummary,
    CapabilityTaskSummary,
    EmpiricalPilotJob,
    EmpiricalPilotJobManifest,
    EmpiricalPilotRollout,
    EmpiricalStateSupportFreeze,
    EmpiricalSupportPilotContract,
    EmpiricalSupportPilotReport,
    MechanismEstimandOutcome,
    RawArtifactIntegrityAudit,
    ReachabilityConditionScaffold,
    StateReachabilitySummary,
    aggregate_capability_mechanisms,
    aggregate_capability_tasks,
    aggregate_state_reachability,
    build_empirical_pilot_job_manifest,
    build_empirical_support_pilot_contract,
    empirical_pilot_rollout_id,
    empirical_support_pilot_report_id,
    evaluate_mechanism_estimand,
    failure_artifact_mechanism_estimand,
    freeze_empirical_state_support,
    load_v26_56_inputs,
    make_public_reachability_condition,
    map_valid_trajectory_to_static_path,
    raw_artifact_integrity_audit_id,
    verify_empirical_agent_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    RematerializedExecutableTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentFailureArtifact,
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
    LLMClientError,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

DEFAULT_WORKERS = 24


class _RawFirstRecordingClient:
    """Retain every attempted prompt and telemetry row across unexpected Host failures."""

    def __init__(self, delegate: OpenAICompatibleJsonClient) -> None:
        self._delegate = delegate
        self.telemetry: list[ModelCallTelemetry] = []
        self.prompts: list[str] = []

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        try:
            payload, telemetry = self._delegate.complete_json(prompt)
        except LLMClientError as exc:
            self.telemetry.extend(exc.telemetry)
            self.prompts.extend(prompt for _ in exc.telemetry)
            raise
        self.telemetry.append(telemetry)
        self.prompts.append(prompt)
        return payload, telemetry


def run_empirical_support_pilot(
    *,
    run_id: str,
    source_dir: Path,
    model_config_path: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    job_limit: int | None = None,
    audit_only: bool = False,
) -> EmpiricalSupportPilotReport:
    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    report56, records, environments, catalogs, _ = load_v26_56_inputs(source_dir)
    del report56
    contract = build_empirical_support_pilot_contract(
        run_id=run_id,
        source_dir=source_dir,
        model_config=model_config,
        package_root=package_root,
    )
    manifest = build_empirical_pilot_job_manifest(contract, records, catalogs)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "execution_contract.json", contract.model_dump(mode="json"))
    _write_json_atomic(output_dir / "job_manifest.json", manifest.model_dump(mode="json"))

    if audit_only:
        raw_audit = _audit_raw_artifacts(())
        result = _make_report(
            contract=contract,
            manifest=manifest,
            discovered_models=(),
            rollouts=(),
            raw_audit=raw_audit,
            records=records,
            catalogs=catalogs,
            status="preflight",
            next_stage="model_discovery_and_parallel_execution",
        )
        _write_json_atomic(output_dir / "report.json", result.model_dump(mode="json"))
        return result

    client = OpenAICompatibleJsonClient(model_config)
    discovered_models = client.discover_models()
    if contract.model_id not in discovered_models:
        raise ValueError("frozen DeepSeek V4-Flash identity is unavailable")

    record_by_id = _unique_index(records, "record_id")
    environment_by_id = _unique_index(environments, "manifest_id")
    catalog_by_task = _unique_index(catalogs, "task_package_id")
    checkpoint_path = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_checkpoint(checkpoint_path, contract, manifest)
    completed = {item.job_id: item for item in existing}
    pending = [item for item in manifest.jobs if item.job_id not in completed]
    if job_limit is not None:
        pending = pending[: max(0, job_limit)]
    print(
        f"[v26.57] resuming {len(completed)}/456; executing {len(pending)} jobs "
        f"with {workers} workers",
        flush=True,
    )
    lock = threading.Lock()
    executor = ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1)))
    future_map = {
        executor.submit(
            _run_one,
            job=job,
            contract=contract,
            record=record_by_id[job.task_record_id],
            environment=environment_by_id[record_by_id[job.task_record_id].environment_manifest_id],
            catalog=catalog_by_task[job.task_package_id],
            client=client,
            output_dir=output_dir,
        ): job
        for job in pending
    }
    try:
        for future in as_completed(future_map):
            job = future_map[future]
            try:
                rollout = future.result()
            except Exception as exc:
                _append_jsonl(
                    output_dir / "runner_failures.checkpoint.jsonl",
                    {
                        "failure_id": canonical_hash(
                            {
                                "contract_id": contract.contract_id,
                                "job_id": job.job_id,
                                "error": _safe_error(exc),
                            },
                            prefix="finance_v26_empirical_runner_failure:",
                        ),
                        "job_id": job.job_id,
                        "error": _safe_error(exc),
                    },
                )
                for queued in future_map:
                    if queued is not future:
                        queued.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                raise RuntimeError(
                    "v26.57 worker failed after raw-first capture; pending jobs cancelled"
                ) from exc
            with lock:
                if rollout.job_id in completed:
                    raise ValueError("v26.57 produced a duplicate job result")
                completed[rollout.job_id] = rollout
                _append_jsonl(checkpoint_path, rollout.model_dump(mode="json"))
            count = len(completed)
            if count % max(1, workers) == 0 or count == 456:
                print(f"[v26.57] completed {count}/456", flush=True)
    except Exception:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    ordered = tuple(completed[item.job_id] for item in manifest.jobs if item.job_id in completed)
    _write_json_atomic(
        output_dir / "empirical_rollouts.json",
        [item.model_dump(mode="json") for item in ordered],
    )
    raw_audit = _audit_raw_artifacts(ordered)
    _write_json_atomic(output_dir / "raw_integrity_audit.json", raw_audit.model_dump(mode="json"))
    complete = len(ordered) == 456
    resource_ok = sum(Decimal(item.estimated_cost_usd) for item in ordered) <= Decimal(
        str(MAXIMUM_TOTAL_ESTIMATED_COST_USD)
    )
    instrument_ok = raw_audit.status == "passed" and all(
        item.terminal_category not in {"runtime_failure", "instrument_failure"}
        and item.exact_requested_model
        and not item.fallback_used
        for item in ordered
    )
    status: Literal["partial", "completed", "blocked"]
    if not complete:
        status = "partial"
        next_stage = "empirical_pilot_resume_only"
    elif not resource_ok:
        status = "blocked"
        next_stage = "resource_budget_audit_only"
    elif not instrument_ok:
        status = "blocked"
        next_stage = "instrument_or_transport_repair_only"
    else:
        status = "completed"
        next_stage = "derive_from_state_support_freeze"
    result = _make_report(
        contract=contract,
        manifest=manifest,
        discovered_models=discovered_models,
        rollouts=ordered,
        raw_audit=raw_audit,
        records=records,
        catalogs=catalogs,
        status=status,
        next_stage=next_stage,
    )
    _write_json_atomic(output_dir / "report.json", result.model_dump(mode="json"))
    return result


def _run_one(
    *,
    job: EmpiricalPilotJob,
    contract: EmpiricalSupportPilotContract,
    record: RematerializedExecutableTaskRecord,
    environment: AgentToolEnvironmentManifest,
    catalog: Any,
    client: OpenAICompatibleJsonClient,
    output_dir: Path,
    raw_namespace: str = "raw",
) -> EmpiricalPilotRollout:
    if record.task_package.package_id != job.task_package_id:
        raise ValueError("job and rematerialized task identities differ")
    if record.environment_manifest_id != environment.manifest_id:
        raise ValueError("job environment identity changed before execution")
    observed_environment_hash = canonical_hash(
        environment,
        prefix="finance_v26_executable_environment:",
    )
    if observed_environment_hash != record.environment_manifest_hash:
        raise ValueError("job environment bytes changed before execution")
    if (
        record.environment_manifest_hash
        != record.task_package.public_runtime_contract.environment_manifest_hash
    ):
        raise ValueError("task Runtime binding changed before execution")
    recovery = (
        FinanceTypedRecoveryScenario.model_validate(record.recovery_scenario)
        if record.recovery_scenario is not None
        else None
    )
    runtime = FinanceExecutableSupportRuntime(
        record.public_corpus,
        environment,
        recovery_scenario=recovery,
    )
    condition = (
        make_public_reachability_condition(job.requested_path_strategy)
        if job.requested_path_strategy is not None
        else None
    )
    if condition is not None and condition.condition_id != job.public_condition_id:
        raise ValueError("job public condition identity changed")
    scaffold = ReachabilityConditionScaffold(condition) if condition is not None else None
    result = None
    verification = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    terminal: Literal[
        "model_valid_trajectory",
        "model_invalid_trajectory",
        "runtime_failure",
        "instrument_failure",
    ]
    failure_attribution: dict[str, Any] | None = None
    recording_client = _RawFirstRecordingClient(client)
    try:
        result = IterativeAgentSolver(
            recording_client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.maximum_total_model_tokens_per_rollout,
            protocol_profile=IterativeAgentProtocolProfile(),
            public_scaffold_compiler=scaffold,
        ).solve_with_audit(record.task_package.task.public, runtime)
        telemetry = result.audit.telemetry
        verification = verify_empirical_agent_result(record, environment, result)
        terminal = "model_valid_trajectory" if verification.valid else "model_invalid_trajectory"
        if not verification.valid:
            failure_attribution = {
                "category": "independent_verification_failed",
                "earliest_failure_stage": verification.earliest_failure_stage,
                "failed_check_ids": sorted(
                    key for key, passed in verification.checks.items() if not passed
                ),
            }
    except LLMClientError as exc:
        telemetry = exc.telemetry
        failure_artifact = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        terminal = (
            "model_invalid_trajectory"
            if _captured_failure_is_model_outcome(telemetry, failure_artifact)
            else "runtime_failure"
        )
        failure_attribution = {
            "category": "model_contract_failure"
            if terminal == "model_invalid_trajectory"
            else "runtime_failure",
            "reason": _safe_error(exc),
        }
    except Exception as exc:
        telemetry = tuple(recording_client.telemetry)
        terminal = "instrument_failure"
        failure_attribution = {
            "category": "instrument_failure",
            "reason": _safe_error(exc),
            "raw_first_provider_call_count": len(recording_client.telemetry),
        }

    if result is not None:
        mechanism = evaluate_mechanism_estimand(
            record,
            result.observations,
            stopped_by_model=result.audit.stopped_by_model,
        )
    elif failure_artifact is not None:
        mechanism = failure_artifact_mechanism_estimand(record, failure_artifact)
    else:
        mechanism = _empty_mechanism_outcome(record)
    assignment = (
        map_valid_trajectory_to_static_path(record, catalog, result, verification)
        if result is not None and verification is not None and verification.valid
        else None
    )
    telemetry_payload = tuple(item.model_dump(mode="json") for item in telemetry)
    call_ids = _provider_call_ids(job, telemetry_payload)
    prompt_rows = (
        result.audit.model_request_prompts
        if result is not None
        else failure_artifact.model_request_prompts
        if failure_artifact is not None
        else tuple(recording_client.prompts)
    )
    prompt_hashes = tuple(hashlib.sha256(item.encode("utf-8")).hexdigest() for item in prompt_rows)
    recursive_noninterference = bool(
        (
            result is not None
            and len(prompt_rows)
            == len(result.audit.model_request_prompt_noninterference_attestation_hashes)
        )
        or (
            failure_artifact is not None
            and len(prompt_rows)
            == len(failure_artifact.model_request_prompt_noninterference_attestation_hashes)
        )
        or (result is None and failure_artifact is None and not prompt_rows)
    )
    condition_noninterference = _condition_noninterference(
        job=job,
        condition=condition,
        record=record,
        prompts=prompt_rows,
    )
    total_tokens = sum(item.total_tokens or 0 for item in telemetry)
    usage_complete = bool(telemetry) and all(item.total_tokens is not None for item in telemetry)
    estimated_cost = sum(
        (
            Decimal(str(item.estimated_cost))
            for item in telemetry
            if item.estimated_cost is not None
        ),
        Decimal("0"),
    )
    exact_model = bool(telemetry) and all(
        item.model_selected == contract.model_id
        and item.model_requested == contract.model_id
        and item.http_success
        for item in telemetry
    )
    fallback_used = any(item.fallback_used for item in telemetry)
    trajectory_id = result.trajectory.trajectory_id if result is not None else None
    trajectory_content_hash = (
        canonical_hash(
            result.trajectory.model_dump(mode="json", exclude={"trajectory_id"}),
            prefix="finance_v26_empirical_trajectory_content:",
        )
        if result is not None
        else None
    )
    decision_trace = (
        trajectory_decision_trace_hash(result.trajectory) if result is not None else None
    )
    raw_payload = {
        "contract_id": contract.contract_id,
        "job": job.model_dump(mode="json"),
        "task_record_id": record.record_id,
        "task_package_id": record.task_package.package_id,
        "environment_manifest_id": environment.manifest_id,
        "public_condition": condition.model_dump(mode="json") if condition else None,
        "public_scaffold_manifest_hash": scaffold.manifest_hash if scaffold else None,
        "provider_call_ids": list(call_ids),
        "provider_telemetry": telemetry_payload,
        "actual_model_request_prompts": list(prompt_rows),
        "actual_model_request_prompt_hashes": list(prompt_hashes),
        "terminal_category": terminal,
        "trajectory": result.trajectory.model_dump(mode="json") if result else None,
        "agent_audit": result.audit.model_dump(mode="json") if result else None,
        "failure_artifact": failure_artifact.model_dump(mode="json") if failure_artifact else None,
        "independent_verification": verification.model_dump(mode="json") if verification else None,
        "mechanism_estimand": mechanism.model_dump(mode="json"),
        "path_assignment": assignment.model_dump(mode="json") if assignment else None,
        "recursive_noninterference_passed": recursive_noninterference,
        "condition_noninterference_passed": condition_noninterference,
        "host_event_side_channel_hashes": (
            list(result.audit.host_event_side_channel_hashes)
            if result
            else list(failure_artifact.host_event_side_channel_hashes)
            if failure_artifact
            else []
        ),
        "internal_tool_result_hashes": (
            list(result.audit.internal_tool_result_hashes)
            if result
            else list(failure_artifact.internal_tool_result_hashes)
            if failure_artifact
            else []
        ),
        "failure_attribution": failure_attribution,
    }
    raw_path = _raw_path(output_dir, job, namespace=raw_namespace)
    raw_sha = _write_raw_first(raw_path, raw_payload)
    values = {
        "contract_id": contract.contract_id,
        "job_id": job.job_id,
        "task_record_id": job.task_record_id,
        "task_package_id": job.task_package_id,
        "mechanism_id": job.mechanism_id,
        "intended_use": job.intended_use,
        "sampling_mode": job.sampling_mode,
        "replicate_index": job.replicate_index,
        "requested_static_path_id": job.requested_static_path_id,
        "requested_path_strategy": job.requested_path_strategy,
        "requested_quotient_state_id": job.requested_quotient_state_id,
        "public_condition_id": job.public_condition_id,
        "terminal_category": terminal,
        "provider_call_ids": call_ids,
        "provider_call_count": len(call_ids),
        "provider_total_tokens": total_tokens,
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": str(estimated_cost),
        "exact_requested_model": exact_model,
        "fallback_used": fallback_used,
        "actual_prompt_hashes": prompt_hashes,
        "recursive_noninterference_passed": recursive_noninterference,
        "condition_noninterference_passed": condition_noninterference,
        "verification": verification,
        "mechanism_estimand": mechanism,
        "path_assignment": assignment,
        "trajectory_id": trajectory_id,
        "trajectory_content_hash": trajectory_content_hash,
        "decision_trace_hash": decision_trace,
        "model_generated": bool(call_ids) and terminal.startswith("model_"),
        "raw_artifact_uri": str(raw_path.resolve()),
        "raw_artifact_sha256": raw_sha,
        "failure_attribution": failure_attribution,
    }
    provisional = EmpiricalPilotRollout.model_construct(rollout_id="pending", **values)
    return EmpiricalPilotRollout(
        rollout_id=empirical_pilot_rollout_id(provisional),
        **values,
    )


def _empty_mechanism_outcome(
    record: RematerializedExecutableTaskRecord,
) -> MechanismEstimandOutcome:
    return evaluate_mechanism_estimand(record, (), stopped_by_model=False)


def _condition_noninterference(
    *,
    job: EmpiricalPilotJob,
    condition: Any,
    record: RematerializedExecutableTaskRecord,
    prompts: tuple[str, ...],
) -> bool:
    if job.sampling_mode != "reachability_conditioned":
        return condition is None
    if condition is None or not prompts:
        return False
    initial = prompts[0]
    forbidden_values = tuple(
        value
        for value in (
            job.requested_static_path_id,
            job.requested_quotient_state_id,
            *record.target_program_evidence_ids,
        )
        if value
    )
    return bool(
        condition.public_payload["behavior_request"] in initial
        and all(str(value) not in initial for value in forbidden_values)
        and "compiler_witness" not in initial.casefold()
        and "hidden program" not in initial.casefold()
        and "gold evidence" not in initial.casefold()
    )


def _captured_failure_is_model_outcome(
    telemetry: tuple[ModelCallTelemetry, ...],
    artifact: IterativeAgentFailureArtifact | None,
) -> bool:
    return bool(artifact is not None and telemetry and all(item.http_success for item in telemetry))


def _provider_call_ids(
    job: EmpiricalPilotJob, telemetry: tuple[dict[str, Any], ...]
) -> tuple[str, ...]:
    return tuple(
        canonical_hash(
            {
                "job_id": job.job_id,
                "call_index": index,
                "request_hash": row.get("request_hash"),
                "response_hash": row.get("response_hash"),
                "model_selected": row.get("model_selected"),
                "http_status": row.get("http_status"),
            },
            prefix="finance_v26_empirical_provider_call:",
        )
        for index, row in enumerate(telemetry)
    )


def _raw_path(output_dir: Path, job: EmpiricalPilotJob, *, namespace: str = "raw") -> Path:
    task_hash = hashlib.sha256(job.task_package_id.encode("utf-8")).hexdigest()[:16]
    state = job.requested_path_strategy or "unconditional"
    return (
        output_dir
        / namespace
        / job.sampling_mode
        / task_hash
        / state
        / f"replicate_{job.replicate_index}.json"
    )


def _write_raw_first(path: Path, payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    if path.exists():
        if path.read_bytes() != serialized:
            raise ValueError("raw Artifact identity already exists with different bytes")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(serialized)
    temporary.replace(path)
    return digest


def _replay_raw(path: Path, expected_sha256: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("raw Artifact byte hash replay failed")
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("raw Artifact is not canonically serialized")
    return payload


def _audit_raw_artifacts(
    rollouts: tuple[EmpiricalPilotRollout, ...],
) -> RawArtifactIntegrityAudit:
    byte_pass = identity_pass = prompt_pass = side_pass = noninterference_pass = 0
    condition_pass = 0
    failures: list[str] = []
    provider_calls: list[str] = []
    for item in rollouts:
        try:
            payload = _replay_raw(Path(item.raw_artifact_uri), item.raw_artifact_sha256)
            byte_pass += 1
            if (
                payload["contract_id"] == item.contract_id
                and payload["job"]["job_id"] == item.job_id
                and payload["task_package_id"] == item.task_package_id
                and payload["terminal_category"] == item.terminal_category
                and tuple(payload["provider_call_ids"]) == item.provider_call_ids
            ):
                identity_pass += 1
            else:
                raise ValueError("raw identity mismatch")
            prompts = tuple(payload["actual_model_request_prompts"])
            hashes = tuple(hashlib.sha256(value.encode("utf-8")).hexdigest() for value in prompts)
            if (
                hashes
                == tuple(payload["actual_model_request_prompt_hashes"])
                == item.actual_prompt_hashes
            ):
                prompt_pass += 1
            else:
                raise ValueError("raw prompt hash mismatch")
            typed = payload["agent_audit"] or payload["failure_artifact"]
            expected_host = tuple(typed["host_event_side_channel_hashes"]) if typed else ()
            expected_internal = tuple(typed["internal_tool_result_hashes"]) if typed else ()
            if (
                tuple(payload["host_event_side_channel_hashes"]) == expected_host
                and tuple(payload["internal_tool_result_hashes"]) == expected_internal
            ):
                side_pass += 1
            else:
                raise ValueError("raw side-channel mismatch")
            if (
                payload["recursive_noninterference_passed"] is True
                and item.recursive_noninterference_passed is True
            ):
                noninterference_pass += 1
            else:
                raise ValueError("raw recursive noninterference mismatch")
            if (
                payload["condition_noninterference_passed"] is True
                and item.condition_noninterference_passed is True
            ):
                condition_pass += 1
            else:
                raise ValueError("raw condition noninterference mismatch")
            provider_calls.extend(item.provider_call_ids)
        except Exception:
            failures.append(item.raw_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(provider_calls).items() if count > 1))
    all_pass = (
        byte_pass
        == identity_pass
        == prompt_pass
        == side_pass
        == noninterference_pass
        == condition_pass
        == len(rollouts)
    )
    status = (
        "passed"
        if len(rollouts) == 456 and all_pass and not duplicates and not failures
        else "partial"
        if all_pass and not duplicates and not failures
        else "failed"
    )
    values = {
        "observed_rollout_count": len(rollouts),
        "byte_hash_pass_count": byte_pass,
        "identity_pass_count": identity_pass,
        "prompt_hash_pass_count": prompt_pass,
        "side_channel_pass_count": side_pass,
        "noninterference_pass_count": noninterference_pass,
        "condition_noninterference_pass_count": condition_pass,
        "provider_call_ids_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(failures),
        "status": status,
    }
    provisional = RawArtifactIntegrityAudit.model_construct(audit_id="pending", **values)
    return RawArtifactIntegrityAudit(
        audit_id=raw_artifact_integrity_audit_id(provisional),
        **values,
    )


def _make_report(
    *,
    contract: EmpiricalSupportPilotContract,
    manifest: EmpiricalPilotJobManifest,
    discovered_models: tuple[str, ...],
    rollouts: tuple[EmpiricalPilotRollout, ...],
    raw_audit: RawArtifactIntegrityAudit,
    records: tuple[RematerializedExecutableTaskRecord, ...],
    catalogs: tuple[Any, ...],
    status: Literal["preflight", "partial", "completed", "blocked"],
    next_stage: str,
) -> EmpiricalSupportPilotReport:
    mode_counts = Counter(item.sampling_mode for item in rollouts)
    capability_complete = mode_counts["capability_unconditional"] == 96
    reachability_complete = (
        mode_counts["reachability_unconditional"] == 144
        and mode_counts["reachability_conditioned"] == 216
    )
    capability_tasks: tuple[CapabilityTaskSummary, ...] = ()
    capability_mechanisms: tuple[CapabilityMechanismSummary, ...] = ()
    state_summaries: tuple[StateReachabilitySummary, ...] = ()
    support_freeze: EmpiricalStateSupportFreeze | None = None
    if capability_complete:
        capability_tasks = aggregate_capability_tasks(rollouts)
        capability_mechanisms = aggregate_capability_mechanisms(capability_tasks)
    if reachability_complete:
        state_summaries = aggregate_state_reachability(rollouts, catalogs)
        support_freeze = freeze_empirical_state_support(contract, state_summaries, records)
        if status == "completed":
            next_stage = support_freeze.next_transition
    values = {
        "run_id": contract.run_id,
        "contract_id": contract.contract_id,
        "job_manifest_id": manifest.manifest_id,
        "discovered_models": discovered_models,
        "completed_rollout_count": len(rollouts),
        "sampling_mode_counts": dict(sorted(mode_counts.items())),
        "terminal_counts": dict(
            sorted(Counter(item.terminal_category for item in rollouts).items())
        ),
        "provider_call_count": sum(item.provider_call_count for item in rollouts),
        "provider_total_tokens": sum(item.provider_total_tokens for item in rollouts),
        "estimated_cost_usd": str(
            sum((Decimal(item.estimated_cost_usd) for item in rollouts), Decimal("0"))
        ),
        "raw_integrity_audit": raw_audit,
        "capability_task_summaries": capability_tasks,
        "capability_mechanism_summaries": capability_mechanisms,
        "state_reachability_summaries": state_summaries,
        "state_support_freeze": support_freeze,
        "capability_development_complete": capability_complete,
        "state_reachability_complete": reachability_complete,
        "status": status,
        "next_permitted_stage": next_stage,
    }
    provisional = EmpiricalSupportPilotReport.model_construct(report_id="pending", **values)
    return EmpiricalSupportPilotReport(
        report_id=empirical_support_pilot_report_id(provisional),
        **values,
    )


def _load_checkpoint(
    path: Path,
    contract: EmpiricalSupportPilotContract,
    manifest: EmpiricalPilotJobManifest,
) -> tuple[EmpiricalPilotRollout, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        EmpiricalPilotRollout.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("checkpoint contains duplicate job identities")
    for item in rows:
        job = jobs.get(item.job_id)
        if job is None or item.contract_id != contract.contract_id:
            raise ValueError("checkpoint contains a foreign job or contract")
        if item.task_package_id != job.task_package_id or item.sampling_mode != job.sampling_mode:
            raise ValueError("checkpoint job lineage changed")
        _replay_raw(Path(item.raw_artifact_uri), item.raw_artifact_sha256)
    return rows


def _unique_index(items: tuple[Any, ...], attribute: str) -> dict[str, Any]:
    output = {str(getattr(item, attribute)): item for item in items}
    if len(output) != len(items):
        raise ValueError(f"duplicate source identity for {attribute}")
    return output


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}:{str(exc)[:500]}"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Finance v26.57 capability and empirical state-support Pilot"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--job-limit", type=int)
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_empirical_support_pilot(
        run_id=args.run_id,
        source_dir=args.source_dir,
        model_config_path=args.model_config,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
        job_limit=args.job_limit,
        audit_only=args.audit_only,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
