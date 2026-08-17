from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.core.trajectory.scaffolding import (
    SCAFFOLD_LEVELS,
    CapabilityAwarePublicProjection,
    CapabilityScaffoldAdmissionArtifact,
    CapabilityScaffoldLadderCompilation,
    CompiledPublicStateSummary,
    ScaffoldLevel,
    make_compiled_task_condition_lineage,
)
from trusted_synthesis.core.trajectory.specification import (
    make_trajectory_verification_context,
)
from trusted_synthesis.core.trajectory.state import (
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.domains.finance.agent_tools import (
    FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
    finance_archive_agent_tool_specs,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
    FinanceArchiveInteractiveToolRuntime,
    capability_mechanism_scenario_from_oracle,
    finance_runtime_snapshot_hash,
    recovery_scenario_from_metadata,
)
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (
    CapabilityHeterogeneousMainlineProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    BridgeDevelopmentAuthorization,
    BridgeExecutionManifest,
    BridgeMechanism,
    BridgeRolloutObservation,
    BridgeRolloutTerminal,
    CompilerAssistedBridgeContract,
    CompilerAssistedBridgeSupportFreeze,
    aggregate_bridge_cell_observation,
    freeze_compiler_assisted_bridge_support,
    make_bridge_execution_manifest,
    make_bridge_rollout_observation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_rollout import (
    V26_BRIDGE_ESTIMAND_EVALUATOR_VERSION,
    V26_BRIDGE_FIXED_POLICY_VERSION,
    BridgeRawIntegrityAudit,
    BridgeScaffoldSnapshot,
    HistoricalApiExposureAudit,
    HistoricalApiRecordManifest,
    LivePublicScaffoldCompiler,
    audit_historical_api_exposure,
    bridge_raw_integrity_audit_id,
    build_historical_api_record_manifest,
    evaluate_bridge_estimands,
    make_provider_call_ids,
    replay_raw_payload,
    unevaluated_bridge_estimands,
    write_raw_payload_first,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
    v26_freshness_channel_values,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_stage_router import (
    V26StageLedger,
    advance_v26_stage,
    make_v26_stage_artifact_reference,
    write_v26_stage_ledger,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    IterativeAgentFailureArtifact,
    IterativeAgentProtocolProfile,
    IterativeAgentSolver,
    LLMClientError,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
    ITERATIVE_AGENT_PLAN_PROMPT_VERSION,
    ITERATIVE_AGENT_SOLVER_VERSION,
    model_input_projection_manifest,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import make_agent_tool_environment_manifest

V26_BRIDGE_RUNNER_VERSION = "finance_v26_bridge_rollout_runner.v2"
V26_BRIDGE_EXECUTION_CONTRACT_VERSION = "finance_v26_bridge_execution_contract.v1"
V26_BRIDGE_RUN_REPORT_VERSION = "finance_v26_bridge_run_report.v1"

DEFAULT_MAXIMUM_TOOL_CALLS = 24
DEFAULT_MAXIMUM_FAILED_TOOL_CALLS = 5
DEFAULT_MAXIMUM_OBSERVATION_BYTES = 1_000_000
DEFAULT_MAXIMUM_MODEL_TOKENS = 120_000
DEFAULT_TOOL_TIMEOUT_SECONDS = 30.0


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BridgeExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    bridge_contract_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    development_authorization_id: str = Field(min_length=1)
    historical_record_manifest_id: str = Field(min_length=1)
    historical_exposure_audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    scaffold_levels: tuple[ScaffoldLevel, ...] = SCAFFOLD_LEVELS
    rollouts_per_task_level: Literal[6] = 6
    task_level_cell_count: Literal[96] = 96
    rollout_identity_count: Literal[576] = 576
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    fallback_models: tuple[str, ...] = ()
    require_requested_model: Literal[True] = True
    model_invocation_config: dict[str, Any]
    model_config_hash: str = Field(min_length=1)
    provider_route: dict[str, Any]
    provider_route_hash: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    maximum_tool_calls: int = Field(default=DEFAULT_MAXIMUM_TOOL_CALLS, ge=1)
    maximum_failed_tool_calls: int = Field(default=DEFAULT_MAXIMUM_FAILED_TOOL_CALLS, ge=0)
    maximum_observation_bytes: int = Field(default=DEFAULT_MAXIMUM_OBSERVATION_BYTES, ge=1)
    maximum_model_tokens: int = Field(default=DEFAULT_MAXIMUM_MODEL_TOKENS, ge=1)
    tool_timeout_seconds: float = Field(default=DEFAULT_TOOL_TIMEOUT_SECONDS, gt=0)
    prompt_manifest: dict[str, Any]
    prompt_manifest_hash: str = Field(min_length=1)
    runtime_manifest: dict[str, Any]
    runtime_manifest_hash: str = Field(min_length=1)
    estimand_evaluator_manifest: dict[str, Any]
    estimand_evaluator_manifest_hash: str = Field(min_length=1)
    raw_artifact_precedes_typed_observation: Literal[True] = True
    task_is_primary_sampling_unit: Literal[True] = True
    rollout_is_secondary_sampling_unit: Literal[True] = True
    per_task_scaffold_selection_forbidden: Literal[True] = True
    schema_version: str = V26_BRIDGE_EXECUTION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BridgeExecutionContract:
        expected = {
            "model_config": (self.model_invocation_config, self.model_config_hash),
            "provider_route": (self.provider_route, self.provider_route_hash),
            "prompt_manifest": (self.prompt_manifest, self.prompt_manifest_hash),
            "runtime_manifest": (self.runtime_manifest, self.runtime_manifest_hash),
            "estimand_evaluator_manifest": (
                self.estimand_evaluator_manifest,
                self.estimand_evaluator_manifest_hash,
            ),
        }
        for label, (payload, observed_hash) in expected.items():
            if observed_hash != canonical_hash(payload, prefix=f"finance_v26_{label}:"):
                raise ValueError(f"v26 Bridge {label} hash is invalid")
        if self.model_invocation_config.get("model") != self.model_id:
            raise ValueError("v26 Bridge model config differs from its frozen model")
        if tuple(self.model_invocation_config.get("fallback_models", ())) != self.fallback_models:
            raise ValueError("v26 Bridge fallback model contract is inconsistent")
        if self.model_invocation_config.get("require_requested_model") is not True:
            raise ValueError("v26 Bridge must fail closed when Flash is unavailable")
        observed_budgets = (
            self.maximum_tool_calls,
            self.maximum_failed_tool_calls,
            self.maximum_observation_bytes,
            self.maximum_model_tokens,
            self.tool_timeout_seconds,
        )
        expected_budgets = (
            DEFAULT_MAXIMUM_TOOL_CALLS,
            DEFAULT_MAXIMUM_FAILED_TOOL_CALLS,
            DEFAULT_MAXIMUM_OBSERVATION_BYTES,
            DEFAULT_MAXIMUM_MODEL_TOKENS,
            DEFAULT_TOOL_TIMEOUT_SECONDS,
        )
        if observed_budgets != expected_budgets:
            raise ValueError("v26 Bridge resource budgets differ from the frozen contract")
        if self.contract_id != bridge_execution_contract_id(self):
            raise ValueError("v26 Bridge execution contract identity is invalid")
        return self


class BridgeRunReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    historical_exposure_audit_id: str = Field(min_length=1)
    discovered_models: tuple[str, ...]
    expected_rollout_count: Literal[576] = 576
    completed_rollout_count: int = Field(ge=0, le=576)
    terminal_counts: dict[str, int]
    provider_call_count: int = Field(ge=0)
    raw_integrity_audit: BridgeRawIntegrityAudit
    bridge_support_freeze_id: str | None = None
    selected_scaffold_by_mechanism: dict[str, str | None]
    status: Literal["partial", "completed", "blocked"]
    next_permitted_stage: str = Field(min_length=1)
    schema_version: str = V26_BRIDGE_RUN_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> BridgeRunReport:
        if sum(self.terminal_counts.values()) != self.completed_rollout_count:
            raise ValueError("v26 Bridge terminal accounting is inconsistent")
        if self.status == "completed" and self.completed_rollout_count != 576:
            raise ValueError("completed v26 Bridge report lacks the full denominator")
        if self.report_id != bridge_run_report_id(self):
            raise ValueError("v26 Bridge report identity is invalid")
        return self


def bridge_execution_contract_id(value: BridgeExecutionContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v26_bridge_execution_contract:",
    )


def bridge_run_report_id(value: BridgeRunReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_bridge_run_report:",
    )


def build_bridge_execution_contract(
    *,
    run_id: str,
    protocol: CapabilityHeterogeneousMainlineProtocol,
    population: V26FreshTaskPopulation,
    authorization: BridgeDevelopmentAuthorization,
    exposure_audit: HistoricalApiExposureAudit,
    model_config: AgentModelConfig,
) -> BridgeExecutionContract:
    if exposure_audit.status != "passed":
        raise ValueError("historical API exposure audit blocks Bridge execution")
    public_model = model_config.model_dump(mode="json")
    provider_route = {
        "provider": model_config.provider,
        "endpoint_host": _endpoint_host(model_config.endpoint),
        "route_id": canonical_hash(
            {
                "provider": model_config.provider,
                "endpoint_host": _endpoint_host(model_config.endpoint),
                "model": model_config.model,
            },
            prefix="finance_v26_provider_route:",
        ),
    }
    prompt_manifest = {
        "template_id": "finance_v26_bridge_host_instrumented",
        "plan_prompt_version": ITERATIVE_AGENT_PLAN_PROMPT_VERSION,
        "decision_prompt_version": ITERATIVE_AGENT_DECISION_PROMPT_VERSION,
        "model_input_projection": model_input_projection_manifest(),
    }
    runtime_manifest = {
        "runner_version": V26_BRIDGE_RUNNER_VERSION,
        "solver_version": ITERATIVE_AGENT_SOLVER_VERSION,
        "finance_runtime_version": FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION,
        "finance_verifier_version": FINANCE_ITERATIVE_AGENT_VERIFIER_VERSION,
        "finance_toolset_version": FINANCE_ARCHIVE_AGENT_TOOLSET_VERSION,
        "runtime_id": protocol.capability_bridge.runtime_id,
        "maximum_tool_calls": DEFAULT_MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": DEFAULT_MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_observation_bytes": DEFAULT_MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens": DEFAULT_MAXIMUM_MODEL_TOKENS,
        "tool_timeout_seconds": DEFAULT_TOOL_TIMEOUT_SECONDS,
    }
    evaluator_manifest = {
        "version": V26_BRIDGE_ESTIMAND_EVALUATOR_VERSION,
        "fixed_policy_version": V26_BRIDGE_FIXED_POLICY_VERSION,
        "task_primary_sampling_unit": True,
        "rollout_secondary_sampling_unit": True,
        "definitions": {
            "context_action_alignment": "first successful tool matches frozen public query stage",
            "counterfactual_branch_flip": (
                "independently valid trajectory executes at least the frozen operation-branch count"
            ),
            "semantic_reconciliation": (
                "independently valid trajectory executes public semantic normalization"
            ),
            "failure_recovery": "a failed public action is followed by a successful action",
            "stopping_calibration": (
                "model continues while incomplete and stops after sufficient successful work"
            ),
        },
        "fixed_policy": "lexicographically first allowed tool followed by immediate stop",
    }
    values: dict[str, Any] = {
        "run_id": run_id,
        "protocol_id": protocol.protocol_id,
        "bridge_contract_id": protocol.capability_bridge.contract_id,
        "development_population_id": population.population_id,
        "development_authorization_id": authorization.authorization_id,
        "historical_record_manifest_id": exposure_audit.record_manifest.manifest_id,
        "historical_exposure_audit_id": exposure_audit.audit_id,
        "model_invocation_config": public_model,
        "model_config_hash": canonical_hash(public_model, prefix="finance_v26_model_config:"),
        "provider_route": provider_route,
        "provider_route_hash": canonical_hash(provider_route, prefix="finance_v26_provider_route:"),
        "protocol_profile": IterativeAgentProtocolProfile(),
        "prompt_manifest": prompt_manifest,
        "prompt_manifest_hash": canonical_hash(
            prompt_manifest, prefix="finance_v26_prompt_manifest:"
        ),
        "runtime_manifest": runtime_manifest,
        "runtime_manifest_hash": canonical_hash(
            runtime_manifest, prefix="finance_v26_runtime_manifest:"
        ),
        "estimand_evaluator_manifest": evaluator_manifest,
        "estimand_evaluator_manifest_hash": canonical_hash(
            evaluator_manifest,
            prefix="finance_v26_estimand_evaluator_manifest:",
        ),
        "schema_version": V26_BRIDGE_EXECUTION_CONTRACT_VERSION,
    }
    provisional = BridgeExecutionContract.model_construct(contract_id="pending", **values)
    return BridgeExecutionContract(
        contract_id=bridge_execution_contract_id(provisional),
        **values,
    )


def run_bridge_development(
    *,
    run_id: str,
    no_api_dir: Path,
    model_config_path: Path,
    artifact_root: Path,
    output_dir: Path,
    workers: int,
    job_limit: int | None = None,
    smoke_one_per_cell: bool = False,
    audit_only: bool = False,
) -> BridgeRunReport:
    inputs = _load_inputs(no_api_dir)
    (
        protocol,
        population,
        source_tasks,
        compiled,
        ladders,
        admissions,
        authorization,
        ledger,
    ) = inputs
    model_payload = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(model_payload.get("model", model_payload))
    if job_limit is not None and smoke_one_per_cell:
        raise ValueError("job_limit and smoke_one_per_cell are mutually exclusive")
    output_dir.mkdir(parents=True, exist_ok=True)
    record_manifest_path = output_dir / "historical_api_record_manifest.json"
    if record_manifest_path.exists():
        record_manifest = HistoricalApiRecordManifest.model_validate_json(
            record_manifest_path.read_text(encoding="utf-8")
        )
    else:
        record_manifest = build_historical_api_record_manifest(
            artifact_root=artifact_root,
            output_path=record_manifest_path,
        )
    exposure_path = output_dir / "historical_api_exposure_audit.json"
    exposure = audit_historical_api_exposure(
        current_population_id=population.population_id,
        current_identity_channels=v26_freshness_channel_values(population, source_tasks),
        current_instructions=tuple(item.task.public.instruction for item in source_tasks),
        record_manifest=record_manifest,
        output_path=exposure_path,
    )
    contract = build_bridge_execution_contract(
        run_id=run_id,
        protocol=protocol,
        population=population,
        authorization=authorization,
        exposure_audit=exposure,
        model_config=model_config,
    )
    _write_json_atomic(output_dir / "execution_contract.json", contract.model_dump(mode="json"))
    jobs = _build_jobs(population, source_tasks, compiled, ladders, admissions)
    if len(jobs) != 576:
        raise ValueError("v26 Bridge job manifest does not contain 576 identities")
    _write_json_atomic(output_dir / "job_manifest.json", {"jobs": [item[0] for item in jobs]})

    if audit_only:
        raw_audit = _audit_raw_artifacts((), expected_count=576)
        report = _make_run_report(
            run_id=run_id,
            contract=contract,
            exposure=exposure,
            discovered_models=(),
            observations=(),
            raw_audit=raw_audit,
            support_freeze=None,
            status="partial",
            next_stage="model_discovery_and_stratified_smoke",
        )
        _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
        return report

    client = OpenAICompatibleJsonClient(model_config)
    discovered_models = client.discover_models()
    if contract.model_id not in discovered_models:
        raise ValueError("frozen Flash model is unavailable from the Provider")

    checkpoint = output_dir / "rollout_observations.checkpoint.jsonl"
    existing = _load_checkpoint(checkpoint, contract)
    records = {(_rollout_key(item)): item for item in existing}
    pending = [job for job in jobs if _job_key(job[0]) not in records]
    if smoke_one_per_cell:
        pending = _one_pending_job_per_cell(pending)
    elif job_limit is not None:
        pending = pending[: max(0, job_limit)]
    print(
        f"[v26-bridge] resuming {len(records)}/576; executing {len(pending)} "
        f"jobs with {workers} workers",
        flush=True,
    )
    lock = threading.Lock()
    executor = ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1)))
    future_map = {
        executor.submit(
            _run_one,
            job=job,
            contract=contract,
            bridge_contract=protocol.capability_bridge,
            authorization=authorization,
            client=client,
            output_dir=output_dir,
        ): job[0]
        for job in pending
    }
    completed = len(records)
    try:
        for future in as_completed(future_map):
            try:
                observation = future.result()
            except Exception as exc:
                failed_identity = future_map[future]
                failure_payload = {
                    "failure_id": canonical_hash(
                        {
                            "run_id": run_id,
                            "rollout_identity": failed_identity,
                            "error": _safe_error(exc),
                        },
                        prefix="v26_bridge_runner_failure:",
                    ),
                    "run_id": run_id,
                    "rollout_identity": failed_identity,
                    "error": _safe_error(exc),
                }
                _append_jsonl(
                    output_dir / "runner_failures.checkpoint.jsonl",
                    failure_payload,
                )
                for queued_future in future_map:
                    if queued_future is not future:
                        queued_future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                raise RuntimeError(
                    "v26 Bridge worker failed after raw-first capture; pending jobs cancelled"
                ) from exc
            key = _rollout_key(observation)
            with lock:
                if key in records:
                    raise ValueError("v26 Bridge produced a duplicate rollout identity")
                records[key] = observation
                _append_jsonl(checkpoint, observation.model_dump(mode="json"))
                completed += 1
            if completed % max(1, workers) == 0 or completed == 576:
                print(f"[v26-bridge] completed {completed}/576", flush=True)
    except Exception:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    ordered = tuple(
        sorted(
            (records[_job_key(item[0])] for item in jobs if _job_key(item[0]) in records),
            key=lambda item: item.rollout_id,
        )
    )
    observations_path = output_dir / "bridge_rollouts.json"
    _write_json_atomic(
        observations_path,
        [item.model_dump(mode="json") for item in ordered],
    )
    raw_audit = _audit_raw_artifacts(ordered, expected_count=576)
    _write_json_atomic(output_dir / "raw_integrity_audit.json", raw_audit.model_dump(mode="json"))
    support_freeze: CompilerAssistedBridgeSupportFreeze | None = None
    selections: dict[str, str | None] = {}
    next_stage = "bridge_rollout_resume"
    status: Literal["partial", "completed", "blocked"] = "partial"
    if len(ordered) == 576:
        if raw_audit.status != "passed":
            status = "blocked"
            next_stage = "raw_integrity_repair_only"
        else:
            ledger = advance_v26_stage(
                ledger,
                stage="bridge_rollout",
                artifacts=(make_v26_stage_artifact_reference("bridge_rollout", observations_path),),
                model_api_calls=sum(len(item.provider_call_ids) for item in ordered),
            )
            write_v26_stage_ledger(ledger, output_dir / "ledger_after_bridge_rollout.json")
            cells = tuple(
                sorted(
                    (
                        aggregate_bridge_cell_observation(
                            contract_id=protocol.capability_bridge.contract_id,
                            phase_authorization_id=authorization.authorization_id,
                            phase="development",
                            mechanism_id=mechanism,
                            scaffold_level=level,
                            rollout_observations=tuple(
                                item
                                for item in ordered
                                if item.mechanism_id == mechanism and item.scaffold_level == level
                            ),
                        )
                        for mechanism in BRIDGE_MECHANISMS
                        for level in SCAFFOLD_LEVELS
                    ),
                    key=lambda item: item.observation_id,
                )
            )
            cells_path = output_dir / "bridge_cells.json"
            _write_json_atomic(cells_path, [item.model_dump(mode="json") for item in cells])
            ledger = advance_v26_stage(
                ledger,
                stage="bridge_aggregation",
                artifacts=(make_v26_stage_artifact_reference("bridge_cell", cells_path),),
            )
            support_freeze = freeze_compiler_assisted_bridge_support(
                protocol.capability_bridge,
                authorization,
                cells,
            )
            freeze_path = output_dir / "bridge_support_freeze.json"
            _write_json_atomic(freeze_path, support_freeze.model_dump(mode="json"))
            ledger = advance_v26_stage(
                ledger,
                stage="bridge_support_freeze",
                artifacts=(
                    make_v26_stage_artifact_reference("bridge_support_freeze", freeze_path),
                ),
            )
            write_v26_stage_ledger(ledger, output_dir / "finance_v26_stage_ledger.json")
            selections = {
                item.mechanism_id: item.selected_scaffold_level
                for item in support_freeze.selections
            }
            status = "completed"
            next_stage = support_freeze.next_transition
    report = _make_run_report(
        run_id=run_id,
        contract=contract,
        exposure=exposure,
        discovered_models=discovered_models,
        observations=ordered,
        raw_audit=raw_audit,
        support_freeze=support_freeze,
        status=status,
        next_stage=next_stage,
        selections=selections,
    )
    _write_json_atomic(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def _run_one(
    *,
    job: tuple[dict[str, Any], Any, Any, Any, Any, Any],
    contract: BridgeExecutionContract,
    bridge_contract: CompilerAssistedBridgeContract,
    authorization: BridgeDevelopmentAuthorization,
    client: OpenAICompatibleJsonClient,
    output_dir: Path,
) -> BridgeRolloutObservation:
    identity, source_task, compiled, ladder, projection, admission = job
    level = cast(ScaffoldLevel, identity["scaffold_level"])
    mechanism = cast(BridgeMechanism, identity["mechanism_id"])
    lineage = make_compiled_task_condition_lineage(ladder, admission, scaffold_level=level)
    context = make_trajectory_verification_context(
        compiled.task,
        compiled.evidence_bundle,
        compiled.public_corpus,
        compiled.proof_graph,
        compiled.quality_contract,
        compiled.oracle_execution_specification,
    )
    recovery = recovery_scenario_from_metadata(context.task.public.metadata)
    capability = capability_mechanism_scenario_from_oracle(context.task.oracle.selection_contract)
    manifest = _tool_manifest(
        context=context,
        projection=projection,
        recovery=recovery,
        capability=capability,
    )
    runtime = FinanceArchiveInteractiveToolRuntime(
        context.public_corpus,
        manifest,
        recovery_scenario=recovery,
        capability_scenario=capability,
    )
    scaffold = LivePublicScaffoldCompiler(projection) if level != "gamma_0" else None
    execution_manifest = _execution_manifest(
        contract=contract,
        bridge_contract=bridge_contract,
        lineage=lineage,
        projection=projection,
        tool_manifest=manifest,
        scaffold=scaffold,
    )
    result = None
    verification = None
    failure_artifact: IterativeAgentFailureArtifact | None = None
    terminal: BridgeRolloutTerminal
    failure_reason: str | None = None
    failure_detail: str | None = None
    telemetry: tuple[Any, ...] = ()
    try:
        result = IterativeAgentSolver(
            client,
            mode="autonomous_agent",
            maximum_total_tokens=contract.maximum_model_tokens,
            protocol_profile=contract.protocol_profile,
            public_scaffold_compiler=scaffold,
        ).solve_with_audit(context.task.public, runtime)
        telemetry = result.audit.telemetry
        verification = FinanceIterativeAgentVerifier().verify(
            context,
            context.public_corpus,
            manifest,
            result,
        )
        terminal = "model_valid_trajectory" if verification.valid else "model_invalid_trajectory"
    except LLMClientError as exc:
        telemetry = exc.telemetry
        failure_artifact = (
            exc.failure_artifact
            if isinstance(exc.failure_artifact, IterativeAgentFailureArtifact)
            else None
        )
        terminal = (
            "model_invalid_trajectory"
            if _captured_llm_failure_is_model_outcome(telemetry, failure_artifact)
            else "runtime_failure"
        )
        failure_detail = _safe_error(exc)
        failure_reason = failure_detail if terminal == "runtime_failure" else None
    except Exception as exc:
        terminal = "instrument_failure"
        failure_detail = _safe_error(exc)
        failure_reason = failure_detail
    telemetry_payload = tuple(item.model_dump(mode="json") for item in telemetry)
    call_ids = make_provider_call_ids(
        rollout_identity={key: value for key, value in identity.items() if key != "ladder"},
        telemetry=telemetry_payload,
    )
    valid = bool(verification and verification.valid)
    assignment = map_trajectory_to_state(context, result.trajectory) if valid and result else None
    if result is not None:
        trace_hash = trajectory_decision_trace_hash(result.trajectory)
    elif terminal == "model_invalid_trajectory" and failure_artifact is not None:
        trace_hash = canonical_hash(
            {"failure_artifact_id": failure_artifact.artifact_id},
            prefix="trajectory_decision_trace:",
        )
    else:
        trace_hash = None
    if result is not None:
        estimands = evaluate_bridge_estimands(
            mechanism_id=mechanism,
            source_task=source_task,
            observations=result.observations,
            trajectory_steps=tuple(
                item.model_dump(mode="json") for item in result.trajectory.steps
            ),
            independent_validity_passed=valid,
            stopped_by_model=result.audit.stopped_by_model,
            stop_rejection_count=len(result.audit.stop_rejections),
        )
    elif terminal == "model_invalid_trajectory" and failure_artifact is not None:
        estimands = evaluate_bridge_estimands(
            mechanism_id=mechanism,
            source_task=source_task,
            observations=failure_artifact.observations,
            trajectory_steps=tuple(
                item.model_dump(mode="json") for item in failure_artifact.decisions
            ),
            independent_validity_passed=False,
            stopped_by_model=False,
            stop_rejection_count=len(failure_artifact.stop_rejections),
        )
    else:
        estimands = unevaluated_bridge_estimands(mechanism)
    summary: CompiledPublicStateSummary | None = (
        scaffold.final_summary if scaffold is not None and scaffold.snapshots else None
    )
    prompt_rows = (
        result.audit.model_request_prompts
        if result is not None
        else failure_artifact.model_request_prompts
        if failure_artifact is not None
        else ()
    )
    prompt_hashes = tuple(hashlib.sha256(item.encode("utf-8")).hexdigest() for item in prompt_rows)
    raw_path = _raw_path(output_dir, identity)
    raw_payload: dict[str, Any] = {
        "task_id": lineage.task_id,
        "mechanism_id": mechanism,
        "scaffold_level": level,
        "replicate_index": identity["replicate_index"],
        "compiled_task_condition_id": lineage.compiled_task_condition_id,
        "condition_lineage": lineage.model_dump(mode="json"),
        "execution_manifest": execution_manifest.model_dump(mode="json"),
        "execution_manifest_id": execution_manifest.manifest_id,
        "provider_call_ids": list(call_ids),
        "provider_telemetry": telemetry_payload,
        "actual_model_request_prompts": list(prompt_rows),
        "actual_model_request_prompt_hashes": list(prompt_hashes),
        "scaffold_snapshots": (
            [item.model_dump(mode="json") for item in scaffold.snapshots]
            if scaffold is not None
            else []
        ),
        "actual_public_summary_hashes": (
            [item.model_visible_payload_hash for item in scaffold.snapshots]
            if scaffold is not None
            else []
        ),
        "public_state_summary": summary.model_dump(mode="json") if summary else None,
        "terminal_category": terminal,
        "independent_verification": (
            verification.model_dump(mode="json") if verification is not None else None
        ),
        "trajectory": result.trajectory.model_dump(mode="json") if result else None,
        "agent_audit": result.audit.model_dump(mode="json") if result else None,
        "failure_artifact": failure_artifact.model_dump(mode="json") if failure_artifact else None,
        "quotient_state_id": assignment.state.state_id if assignment else None,
        "decision_trace_hash": trace_hash,
        "estimand_outcomes": [item.model_dump(mode="json") for item in estimands],
        "recursive_noninterference_passed": bool(
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
        ),
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
        "failure_attribution": _failure_attribution(
            terminal=terminal,
            verification=verification,
            failure_reason=failure_detail,
        ),
        "failure_reason": failure_reason,
    }
    raw_sha = write_raw_payload_first(raw_path, raw_payload)
    observation = make_bridge_rollout_observation(
        contract_id=bridge_contract.contract_id,
        phase_authorization_id=authorization.authorization_id,
        phase="development",
        mechanism_id=mechanism,
        scaffold_level=level,
        replicate_index=identity["replicate_index"],
        condition_lineage=lineage,
        execution_manifest=execution_manifest,
        provider_call_ids=call_ids,
        public_state_summary=summary,
        terminal_category=terminal,
        independent_validity_passed=valid,
        quotient_state_id=assignment.state.state_id if assignment else None,
        decision_trace_hash=trace_hash,
        estimand_outcomes=estimands,
        raw_payload=raw_payload,
        raw_artifact_uri=str(raw_path.resolve()),
        failure_reason=failure_reason,
    )
    if observation.raw_artifact_sha256 != raw_sha:
        raise ValueError("typed Bridge rollout differs from raw-first Artifact bytes")
    return observation


def _make_run_report(
    *,
    run_id: str,
    contract: BridgeExecutionContract,
    exposure: HistoricalApiExposureAudit,
    discovered_models: tuple[str, ...],
    observations: tuple[BridgeRolloutObservation, ...],
    raw_audit: BridgeRawIntegrityAudit,
    support_freeze: CompilerAssistedBridgeSupportFreeze | None,
    status: Literal["partial", "completed", "blocked"],
    next_stage: str,
    selections: dict[str, str | None] | None = None,
) -> BridgeRunReport:
    terminal_counts = Counter(item.terminal_category for item in observations)
    values: dict[str, Any] = {
        "run_id": run_id,
        "execution_contract_id": contract.contract_id,
        "historical_exposure_audit_id": exposure.audit_id,
        "discovered_models": discovered_models,
        "completed_rollout_count": len(observations),
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "provider_call_count": sum(len(item.provider_call_ids) for item in observations),
        "raw_integrity_audit": raw_audit,
        "bridge_support_freeze_id": support_freeze.freeze_id if support_freeze else None,
        "selected_scaffold_by_mechanism": selections or {},
        "status": status,
        "next_permitted_stage": next_stage,
        "schema_version": V26_BRIDGE_RUN_REPORT_VERSION,
    }
    provisional = BridgeRunReport.model_construct(report_id="pending", **values)
    return BridgeRunReport(report_id=bridge_run_report_id(provisional), **values)


def _one_pending_job_per_cell(
    jobs: list[tuple[dict[str, Any], Any, Any, Any, Any, Any]],
) -> list[tuple[dict[str, Any], Any, Any, Any, Any, Any]]:
    selected = []
    observed_cells: set[tuple[str, str]] = set()
    for job in jobs:
        identity = job[0]
        cell = (identity["mechanism_id"], identity["scaffold_level"])
        if cell in observed_cells:
            continue
        selected.append(job)
        observed_cells.add(cell)
    return selected


def _load_inputs(no_api_dir: Path) -> tuple[Any, ...]:
    ledger = V26StageLedger.model_validate_json(
        (no_api_dir / "finance_v26_stage_ledger.json").read_text(encoding="utf-8")
    )
    protocol_path = Path(ledger.protocol_reference.path)
    protocol = CapabilityHeterogeneousMainlineProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    population = V26FreshTaskPopulation.model_validate_json(
        (no_api_dir / "population" / "development.json").read_text(encoding="utf-8")
    )
    source_tasks = load_v26_selected_source_tasks(population)
    compiled = tuple(
        CompiledProofCarryingArtifacts.model_validate(item)
        for item in json.loads(
            (no_api_dir / "joint" / "compiled_proof_artifacts.json").read_text(encoding="utf-8")
        )
    )
    ladders = tuple(
        CapabilityScaffoldLadderCompilation.model_validate(item)
        for item in json.loads(
            (no_api_dir / "scaffold" / "ladders.json").read_text(encoding="utf-8")
        )
    )
    admissions = tuple(
        CapabilityScaffoldAdmissionArtifact.model_validate(item)
        for item in json.loads(
            (no_api_dir / "scaffold" / "admissions.json").read_text(encoding="utf-8")
        )
    )
    authorization = BridgeDevelopmentAuthorization.model_validate_json(
        (no_api_dir / "bridge" / "development_authorization.json").read_text(encoding="utf-8")
    )
    if not (len(source_tasks) == len(compiled) == len(ladders) == len(admissions) == 24):
        raise ValueError("v26 Bridge frozen task bundle cardinality is invalid")
    return (
        protocol,
        population,
        source_tasks,
        compiled,
        ladders,
        admissions,
        authorization,
        ledger,
    )


def _build_jobs(
    population: V26FreshTaskPopulation,
    source_tasks: tuple[Any, ...],
    compiled: tuple[Any, ...],
    ladders: tuple[Any, ...],
    admissions: tuple[Any, ...],
) -> tuple[tuple[dict[str, Any], Any, Any, Any, Any, Any], ...]:
    source_by_id = _index_unique(
        source_tasks, key=lambda item: item.artifact_id, label="source task"
    )
    compiled_by_task_id = _index_unique(
        compiled, key=lambda item: item.task.task_id, label="compiled task"
    )
    ladder_by_task_id = _index_unique(
        ladders,
        key=lambda item: item.projections[0].base_runtime_projection.task_id,
        label="scaffold ladder task",
    )
    admission_by_ladder_id = _index_unique(
        admissions, key=lambda item: item.ladder_id, label="scaffold admission"
    )
    expected_source_ids = {item.source_task_artifact_id for item in population.tasks}
    if set(source_by_id) != expected_source_ids:
        raise ValueError("v26 Bridge source task identities are incomplete or extraneous")
    expected_task_ids = {source_by_id[item].task.task_id for item in expected_source_ids}
    if set(compiled_by_task_id) != expected_task_ids or set(ladder_by_task_id) != expected_task_ids:
        raise ValueError("v26 Bridge compiled task identities are incomplete or extraneous")
    if set(admission_by_ladder_id) != {item.ladder_id for item in ladders}:
        raise ValueError("v26 Bridge scaffold admission identities are incomplete or extraneous")

    jobs = []
    for root in population.tasks:
        source = source_by_id[root.source_task_artifact_id]
        task_id = source.task.task_id
        artifacts = compiled_by_task_id[task_id]
        ladder = ladder_by_task_id[task_id]
        admission = admission_by_ladder_id[ladder.ladder_id]
        if (
            root.source_task_artifact_id != source.artifact_id
            or artifacts.task.task_id != ladder.projections[0].base_runtime_projection.task_id
            or admission.ladder_id != ladder.ladder_id
        ):
            raise ValueError("v26 Bridge task bundle lineage is inconsistent")
        for projection in ladder.projections:
            for replicate in range(6):
                identity = {
                    "task_id": artifacts.task.task_id,
                    "source_task_artifact_id": source.artifact_id,
                    "mechanism_id": root.mechanism_id,
                    "scaffold_level": projection.scaffold_level,
                    "compiled_task_condition_id": projection.compiled_task_condition_id,
                    "replicate_index": replicate,
                }
                jobs.append((identity, source, artifacts, ladder, projection, admission))
    return tuple(jobs)


def _index_unique(
    items: tuple[Any, ...],
    *,
    key: Callable[[Any], str],
    label: str,
) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for item in items:
        identity = str(key(item))
        if identity in indexed:
            raise ValueError(f"v26 Bridge {label} identity is duplicated")
        indexed[identity] = item
    return indexed


def _tool_manifest(*, context: Any, projection: Any, recovery: Any, capability: Any) -> Any:
    allowed = tuple(projection.base_runtime_projection.allowed_tools)
    specs = tuple(item for item in finance_archive_agent_tool_specs() if item.tool_id in allowed)
    if tuple(sorted(item.tool_id for item in specs)) != tuple(sorted(allowed)):
        raise ValueError("v26 Bridge projection refers to an unknown Finance tool")
    corpus = context.public_corpus
    snapshot_id = str(corpus.build_id or f"corpus:{corpus.corpus_id}")
    return make_agent_tool_environment_manifest(
        environment_id=f"finance_v26_bridge:{projection.compiled_task_condition_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        snapshot_id=snapshot_id,
        snapshot_hash=finance_runtime_snapshot_hash(corpus.corpus_hash, recovery, capability),
        network_policy="forbidden",
        tools=specs,
        maximum_tool_calls=DEFAULT_MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=DEFAULT_MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=DEFAULT_MAXIMUM_OBSERVATION_BYTES,
        tool_timeout_seconds=DEFAULT_TOOL_TIMEOUT_SECONDS,
    )


def _execution_manifest(
    *,
    contract: BridgeExecutionContract,
    bridge_contract: CompilerAssistedBridgeContract,
    lineage: Any,
    projection: CapabilityAwarePublicProjection,
    tool_manifest: Any,
    scaffold: LivePublicScaffoldCompiler | None,
) -> BridgeExecutionManifest:
    prompt = {
        **contract.prompt_manifest,
        "scaffold_compiler_manifest_hash": scaffold.manifest_hash if scaffold else None,
        "scaffold_payload_hash": projection.scaffold_payload_hash,
    }
    tools = {
        "manifest_id": tool_manifest.manifest_id,
        "allowed_tools": sorted(item.tool_id for item in tool_manifest.tools),
        "environment_manifest": tool_manifest.model_dump(mode="json"),
        "tool_spec_hashes": {item.tool_id: item.spec_hash for item in tool_manifest.tools},
    }
    return make_bridge_execution_manifest(
        contract_id=bridge_contract.contract_id,
        condition_lineage=lineage,
        model_id=contract.model_id,
        model_config=contract.model_invocation_config,
        provider_route=contract.provider_route,
        prompt_manifest=prompt,
        runtime_id=bridge_contract.runtime_id,
        tool_manifest=tools,
    )


def _audit_raw_artifacts(
    observations: tuple[BridgeRolloutObservation, ...], *, expected_count: int
) -> BridgeRawIntegrityAudit:
    byte_pass = identity_pass = prompt_pass = 0
    scaffold_pass = side_channel_pass = noninterference_pass = 0
    failures: list[str] = []
    all_calls: list[str] = []
    for item in observations:
        try:
            payload = replay_raw_payload(Path(item.raw_artifact_uri), item.raw_artifact_sha256)
            byte_pass += 1
            if (
                payload["task_id"] == item.task_id
                and payload["terminal_category"] == item.terminal_category
                and payload["execution_manifest_id"] == item.execution_manifest.manifest_id
                and tuple(payload["provider_call_ids"]) == item.provider_call_ids
            ):
                identity_pass += 1
            else:
                raise ValueError("raw identity mismatch")
            prompts = tuple(payload["actual_model_request_prompts"])
            hashes = tuple(hashlib.sha256(value.encode("utf-8")).hexdigest() for value in prompts)
            typed_audit = payload["agent_audit"] or payload["failure_artifact"]
            expected_prompt_hashes = (
                tuple(typed_audit["model_request_prompt_hashes"]) if typed_audit is not None else ()
            )
            if (
                hashes
                == tuple(payload["actual_model_request_prompt_hashes"])
                == expected_prompt_hashes
            ):
                prompt_pass += 1
            else:
                raise ValueError("raw prompt hash mismatch")
            snapshots = tuple(
                BridgeScaffoldSnapshot.model_validate(value)
                for value in payload["scaffold_snapshots"]
            )
            summary_hashes = tuple(item.model_visible_payload_hash for item in snapshots)
            summary_payload = payload["public_state_summary"]
            summary_valid = (
                not snapshots and summary_payload is None and item.scaffold_rank == 0
            ) or (
                bool(snapshots)
                and summary_payload is not None
                and snapshots[-1].summary.summary_id == summary_payload["summary_id"]
                and item.scaffold_rank > 0
            )
            if summary_valid and summary_hashes == tuple(payload["actual_public_summary_hashes"]):
                scaffold_pass += 1
            else:
                raise ValueError("raw scaffold hash mismatch")
            expected_host = (
                tuple(typed_audit["host_event_side_channel_hashes"])
                if typed_audit is not None
                else ()
            )
            expected_internal = (
                tuple(typed_audit["internal_tool_result_hashes"]) if typed_audit is not None else ()
            )
            if (
                tuple(payload["host_event_side_channel_hashes"]) == expected_host
                and tuple(payload["internal_tool_result_hashes"]) == expected_internal
            ):
                side_channel_pass += 1
            else:
                raise ValueError("raw Host/internal side-channel hash mismatch")
            attestation_count = (
                len(typed_audit["model_request_prompt_noninterference_attestation_hashes"])
                if typed_audit is not None
                else 0
            )
            if payload["recursive_noninterference_passed"] is True and attestation_count == len(
                prompts
            ):
                noninterference_pass += 1
            else:
                raise ValueError("raw noninterference failed")
            all_calls.extend(item.provider_call_ids)
        except Exception:
            failures.append(item.raw_artifact_uri)
    duplicates = tuple(sorted(key for key, count in Counter(all_calls).items() if count > 1))
    all_pass = (
        byte_pass
        == identity_pass
        == prompt_pass
        == scaffold_pass
        == side_channel_pass
        == noninterference_pass
        == len(observations)
    )
    status: Literal["passed", "partial", "failed"] = (
        "passed"
        if len(observations) == expected_count and all_pass and not duplicates and not failures
        else "partial"
        if all_pass and not duplicates and not failures
        else "failed"
    )
    values = {
        "raw_artifact_count": len(observations),
        "expected_raw_artifact_count": expected_count,
        "byte_hash_pass_count": byte_pass,
        "identity_pass_count": identity_pass,
        "prompt_hash_pass_count": prompt_pass,
        "scaffold_hash_pass_count": scaffold_pass,
        "side_channel_hash_pass_count": side_channel_pass,
        "noninterference_pass_count": noninterference_pass,
        "provider_call_id_unique": not duplicates,
        "duplicate_provider_call_ids": duplicates,
        "failed_artifacts": tuple(failures),
        "status": status,
    }
    provisional = BridgeRawIntegrityAudit.model_construct(audit_id="pending", **values)
    return BridgeRawIntegrityAudit(audit_id=bridge_raw_integrity_audit_id(provisional), **values)


def _load_checkpoint(
    path: Path, contract: BridgeExecutionContract
) -> tuple[BridgeRolloutObservation, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        BridgeRolloutObservation.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if any(item.execution_manifest.model_id != contract.model_id for item in rows):
        raise ValueError("v26 Bridge checkpoint uses another model")
    keys = [_rollout_key(item) for item in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("v26 Bridge checkpoint contains duplicate rollout identities")
    for item in rows:
        replay_raw_payload(Path(item.raw_artifact_uri), item.raw_artifact_sha256)
    return rows


def _rollout_key(item: BridgeRolloutObservation) -> tuple[str, str, int]:
    return (
        item.condition_lineage.compiled_task_condition_id,
        item.scaffold_level,
        item.replicate_index,
    )


def _job_key(identity: dict[str, Any]) -> tuple[str, str, int]:
    return (
        identity["compiled_task_condition_id"],
        identity["scaffold_level"],
        identity["replicate_index"],
    )


def _captured_llm_failure_is_model_outcome(
    telemetry: tuple[Any, ...],
    failure_artifact: IterativeAgentFailureArtifact | None,
) -> bool:
    return bool(
        failure_artifact is not None and telemetry and all(item.http_success for item in telemetry)
    )


def _failure_attribution(
    *,
    terminal: BridgeRolloutTerminal,
    verification: Any,
    failure_reason: str | None,
) -> dict[str, Any] | None:
    if terminal == "model_valid_trajectory":
        return None
    if terminal == "model_invalid_trajectory":
        if verification is None:
            return {
                "category": "model_contract_failure",
                "reason": failure_reason or "model_contract_exhausted",
            }
        failed_check_ids = (
            sorted(str(item.check_id) for item in verification.checks if not item.passed)
            if verification is not None
            else []
        )
        return {
            "category": "independent_verification_failed",
            "failed_check_ids": failed_check_ids,
        }
    return {
        "category": terminal,
        "reason": failure_reason or "runtime_did_not_provide_a_reason",
    }


def _raw_path(output_dir: Path, identity: dict[str, Any]) -> Path:
    task_digest = hashlib.sha256(identity["task_id"].encode("utf-8")).hexdigest()[:16]
    return (
        output_dir
        / "raw"
        / identity["mechanism_id"]
        / task_digest
        / identity["scaffold_level"]
        / f"replicate_{identity['replicate_index']}.json"
    )


def _endpoint_host(endpoint: str) -> str:
    return endpoint.split("//", 1)[-1].split("/", 1)[0]


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
    parser = argparse.ArgumentParser(description="Run authorized v26 Bridge Development")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--no-api-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--job-limit", type=int)
    parser.add_argument("--smoke-one-per-cell", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_bridge_development(
        run_id=args.run_id,
        no_api_dir=args.no_api_dir,
        model_config_path=args.model_config,
        artifact_root=args.artifact_root,
        output_dir=args.output_dir,
        workers=args.workers,
        job_limit=args.job_limit,
        smoke_one_per_cell=args.smoke_one_per_cell,
        audit_only=args.audit_only,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
