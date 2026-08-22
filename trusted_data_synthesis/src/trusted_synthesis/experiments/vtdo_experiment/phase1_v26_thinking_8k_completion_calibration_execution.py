from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    BudgetQualifiedPathAudit,
    CompactPromptContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_binding_rematerialization import (  # noqa: E501
    EXPECTED_8K_MODEL_CONFIG_ID,
    EXPECTED_8K_THINKING_BINDING_ID,
    EXPECTED_BOUND_PROTOCOL_ID,
    EXPECTED_INITIAL_CANDIDATE_ID,
    Exact8KCompletionContract,
    Exact8KCrossArtifactBindingAudit,
    Exact8KJob,
    Exact8KManifest,
    Exact8KPathAudit,
    Exact8KProfileBinding,
    Exact8KRematerializationReport,
    Exact8KTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_completion_calibration_contracts import (  # noqa: E501
    EXECUTION_RUN_ID,
    EXPECTED_V26_99_CONTRACT_ID,
    EXPECTED_V26_99_CROSS_BINDING_ID,
    EXPECTED_V26_99_MANIFEST_ID,
    EXPECTED_V26_99_REPORT_ID,
    RUNNER_PREFLIGHT_RUN_ID,
    V26_90_DIR,
    V26_94_DIR,
    V26_97_DIR,
    V26_99_DIR,
    AttemptDisposition,
    AttemptPhase,
    Exact8KExecutionContract,
    Exact8KExecutionReport,
    Exact8KOutcomeInterpretationContract,
    Exact8KRawExecution,
    Exact8KRawLineageAudit,
    Exact8KRawProviderCall,
    Exact8KRequestAttempt,
    Exact8KRunnerPreflightReport,
    Exact8KRunnerSourceReplayAudit,
    Prepared8KRequest,
    canonical_bytes,
    exact_8k_execution_report_id,
    exact_8k_provider_call_id,
    exact_8k_raw_execution_id,
    exact_8k_raw_lineage_audit_id,
    exact_8k_raw_provider_call_id,
    exact_8k_request_attempt_id,
    load_canonical_json,
    prepared_8k_request_id,
    sha256,
    sha256_text,
    validate_runner_source_replay,
    write_json_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_bound_redesign_preflight import (  # noqa: E501
    CompletionBoundPathAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    RawFileDescriptor,
    ThinkingRepairCompletedResult,
    ThinkingRepairJobResult,
    ThinkingRepairLogicalRequest,
    _cell_summaries,
    _execute_observation,
    _runtime,
    _score_raw_execution,
    _selected_evidence_ids,
    thinking_repair_completed_result_id,
    thinking_repair_logical_request_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    ThinkingRepairPathAudit,
    ThinkingRepairTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    _load_and_replay_verifier_qualification,
)
from trusted_synthesis.runtime.agent import LLMClientError
from trusted_synthesis.runtime.agent.budget_closed import (
    ProviderBudgetNoCallTerminal,
    ProviderTokenBudgetAudit,
    ProviderTokenBudgetCertificate,
    ProviderTokenBudgetContract,
    ProviderTokenUsageRecord,
    provider_budget_no_call_terminal_id,
    provider_token_budget_audit_id,
    provider_token_budget_certificate_id,
    provider_token_usage_record_id,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    compact_public_progress,
    render_compact_decision_prompt,
    render_compact_final_prompt,
)
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.prospective_thinking_8k_client import (
    EXACT_8K_MAX_TOKENS,
    EXACT_8K_MODEL_ID,
    EXACT_8K_PROFILE_SHA256,
    Exact8KProspectiveThinkingJsonClient,
    certify_exact_8k_request_pre_call,
    require_exact_8k_model_config,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionProjection,
    CompletionRequestKind,
    ProspectiveThinkingFailureArtifact,
    RedactedProviderResponseEnvelope,
    make_prospective_thinking_failure_artifact,
    project_model_completion,
    render_primary_completion_prompt,
    serialize_validated_failure_artifact,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    ProspectiveThinkingCompletionBoundProtocol,
    certify_dynamic_primary_pre_call,
    certify_dynamic_rescue_pre_call,
    render_bounded_rescue_completion_prompt,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest, AgentToolObservation


class _StaticInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    predecessor_report: Exact8KRematerializationReport
    predecessor_contract: Exact8KCompletionContract
    predecessor_manifest: Exact8KManifest
    profile_binding: Exact8KProfileBinding
    cross_binding: Exact8KCrossArtifactBindingAudit
    task_packages: tuple[Exact8KTaskPackage, ...]
    path_audits: tuple[Exact8KPathAudit, ...]
    predecessor_bound_paths: tuple[CompletionBoundPathAudit, ...]
    source_task_packages: tuple[ThinkingRepairTaskPackage, ...]
    source_registered_paths: tuple[ThinkingRepairPathAudit, ...]
    records: tuple[OperationalTaskRecord, ...]
    environments: tuple[AgentToolEnvironmentManifest, ...]
    prompt_contracts: tuple[CompactPromptContract, ...]
    predecessor_budget_paths: tuple[BudgetQualifiedPathAudit, ...]
    compiler_trajectories: tuple[Trajectory, ...]
    completion_bound_protocol: ProspectiveThinkingCompletionBoundProtocol
    replay_contract: AuthorityPreservingReplayContract
    agent_model_config: AgentModelConfig


class PreparedInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    preflight_report: Exact8KRunnerPreflightReport
    execution_contract: Exact8KExecutionContract
    interpretation_contract: Exact8KOutcomeInterpretationContract
    source_replay: Exact8KRunnerSourceReplayAudit
    provider_budget_contract: ProviderTokenBudgetContract
    static: _StaticInputs

    @property
    def replay_contract(self) -> AuthorityPreservingReplayContract:
        return self.static.replay_contract


class RuntimeBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    task_package: Exact8KTaskPackage
    exact_path: Exact8KPathAudit
    source_registered_path: ThinkingRepairPathAudit
    record: OperationalTaskRecord
    environment: AgentToolEnvironmentManifest
    prompt_contract: CompactPromptContract
    compiler_trajectory: Trajectory


def _load_models(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON array: {path}")
    return tuple(model.model_validate(item) for item in payload)


def load_static_inputs(package_root: Path) -> _StaticInputs:
    predecessor_dir = package_root / V26_99_DIR
    report = Exact8KRematerializationReport.model_validate(
        load_canonical_json(predecessor_dir / "report.json")
    )
    contract = Exact8KCompletionContract.model_validate(
        load_canonical_json(predecessor_dir / "exact_8k_completion_contract.json")
    )
    manifest = Exact8KManifest.model_validate(
        load_canonical_json(predecessor_dir / "exact_8k_job_manifest.json")
    )
    profile_binding = Exact8KProfileBinding.model_validate(
        load_canonical_json(predecessor_dir / "exact_8k_profile_binding.json")
    )
    cross = Exact8KCrossArtifactBindingAudit.model_validate(
        load_canonical_json(predecessor_dir / "cross_artifact_binding_audit.json")
    )
    task_packages = cast(
        tuple[Exact8KTaskPackage, ...],
        _load_models(predecessor_dir / "exact_8k_task_packages.json", Exact8KTaskPackage),
    )
    paths = cast(
        tuple[Exact8KPathAudit, ...],
        _load_models(predecessor_dir / "exact_8k_path_audits.json", Exact8KPathAudit),
    )

    v26_97_dir = package_root / V26_97_DIR
    bound_paths = cast(
        tuple[CompletionBoundPathAudit, ...],
        _load_models(
            v26_97_dir / "completion_bound_path_audits.json",
            CompletionBoundPathAudit,
        ),
    )
    protocol = ProspectiveThinkingCompletionBoundProtocol.model_validate(
        load_canonical_json(v26_97_dir / "completion_bound_protocol.json")
    )
    v26_94_dir = package_root / V26_94_DIR
    source_tasks = cast(
        tuple[ThinkingRepairTaskPackage, ...],
        _load_models(
            v26_94_dir / "thinking_repair_task_packages.json",
            ThinkingRepairTaskPackage,
        ),
    )
    source_paths = cast(
        tuple[ThinkingRepairPathAudit, ...],
        _load_models(
            v26_94_dir / "thinking_repair_path_audits.json",
            ThinkingRepairPathAudit,
        ),
    )
    v26_90_dir = package_root / V26_90_DIR
    records = cast(
        tuple[OperationalTaskRecord, ...],
        _load_models(v26_90_dir / "operational_task_records.json", OperationalTaskRecord),
    )
    environments = cast(
        tuple[AgentToolEnvironmentManifest, ...],
        _load_models(
            v26_90_dir / "tool_environment_manifests.json",
            AgentToolEnvironmentManifest,
        ),
    )
    prompt_contracts = cast(
        tuple[CompactPromptContract, ...],
        _load_models(v26_90_dir / "compact_prompt_contracts.json", CompactPromptContract),
    )
    budget_paths = cast(
        tuple[BudgetQualifiedPathAudit, ...],
        _load_models(
            v26_90_dir / "budget_qualified_path_audits.json",
            BudgetQualifiedPathAudit,
        ),
    )
    trajectories = cast(
        tuple[Trajectory, ...],
        _load_models(v26_90_dir / "compiler_trajectories.json", Trajectory),
    )
    profile_path = package_root / profile_binding.profile_relative_path
    if sha256(profile_path) != EXACT_8K_PROFILE_SHA256:
        raise ValueError("v26.100 persisted exact 8K profile bytes changed")
    profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    model_config = require_exact_8k_model_config(
        AgentModelConfig.model_validate(profile_payload["model"])
    )
    _, replay_contract = _load_and_replay_verifier_qualification(
        package_root
        / (
            "artifacts/vtdo_experiment/"
            "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
        ),
        package_root,
    )
    if (
        report.report_id != EXPECTED_V26_99_REPORT_ID
        or contract.contract_id != EXPECTED_V26_99_CONTRACT_ID
        or manifest.manifest_id != EXPECTED_V26_99_MANIFEST_ID
        or cross.audit_id != EXPECTED_V26_99_CROSS_BINDING_ID
        or manifest.contract_id != contract.contract_id
        or tuple(item.job_id for item in manifest.jobs) != cross.manifest_job_ids
        or not cross.static_execution_identity_chain_closed
        or protocol.protocol_id != EXPECTED_BOUND_PROTOCOL_ID
        or protocol.initial_candidate_id != EXPECTED_INITIAL_CANDIDATE_ID
        or model_config.public_manifest_hash != EXPECTED_8K_MODEL_CONFIG_ID
        or bind_prospective_thinking(model_config).binding_id != EXPECTED_8K_THINKING_BINDING_ID
        or manifest.fallback_job_count != 0
    ):
        raise ValueError("v26.100 static exact 8K predecessor binding changed")
    static = _StaticInputs(
        predecessor_report=report,
        predecessor_contract=contract,
        predecessor_manifest=manifest,
        profile_binding=profile_binding,
        cross_binding=cross,
        task_packages=task_packages,
        path_audits=paths,
        predecessor_bound_paths=bound_paths,
        source_task_packages=source_tasks,
        source_registered_paths=source_paths,
        records=records,
        environments=environments,
        prompt_contracts=prompt_contracts,
        predecessor_budget_paths=budget_paths,
        compiler_trajectories=trajectories,
        completion_bound_protocol=protocol,
        replay_contract=replay_contract,
        agent_model_config=model_config,
    )
    for job in manifest.jobs:
        runtime_binding(static, job)
    return static


def runtime_binding(inputs: _StaticInputs, job: Exact8KJob) -> RuntimeBinding:
    tasks = {item.task_package_id: item for item in inputs.task_packages}
    exact_paths = {item.audit_id: item for item in inputs.path_audits}
    bound_paths = {item.audit_id: item for item in inputs.predecessor_bound_paths}
    source_tasks = {item.task_package_id: item for item in inputs.source_task_packages}
    source_paths = {item.audit_id: item for item in inputs.source_registered_paths}
    records = {item.record_id: item for item in inputs.records}
    environments = {item.manifest_id: item for item in inputs.environments}
    prompts = {item.contract_id: item for item in inputs.prompt_contracts}
    budget_paths = {item.audit_id: item for item in inputs.predecessor_budget_paths}
    trajectories = {item.trajectory_id: item for item in inputs.compiler_trajectories}

    task = tasks[job.task_package_id]
    exact_path = exact_paths[job.path_audit_id]
    bound_path = bound_paths[exact_path.predecessor_path_audit_id]
    source_path = source_paths[bound_path.predecessor_path_audit_id]
    source_task = source_tasks[task.source_repair_task_package_id]
    record = records[task.operational_record_id]
    environment = environments[task.environment_manifest_id]
    prompt = prompts[task.compact_prompt_contract_id]
    budget_path = budget_paths[source_path.predecessor_path_audit_id]
    trajectory = trajectories[budget_path.compiler_trajectory_id]
    if (
        job.contract_id != inputs.predecessor_contract.contract_id
        or exact_path.task_package_id != task.task_package_id
        or source_path.repair_task_package_id != source_task.task_package_id
        or source_task.task_package_id != task.source_repair_task_package_id
        or exact_path.path_strategy_id != job.path_strategy_id
        or source_path.path_strategy_id != job.path_strategy_id
        or exact_path.mechanism_id != job.mechanism_id
        or source_path.mechanism_id != job.mechanism_id
        or record.task_package.package_id != task.operational_task_package_id
        or record.environment_manifest_id != environment.manifest_id
        or prompt.operational_task_package_id != record.task_package.package_id
        or trajectory.task_id != record.task_package.task.task_id
    ):
        raise ValueError(f"v26.100 runtime binding changed for Job {job.job_id}")
    return RuntimeBinding(
        task_package=task,
        exact_path=exact_path,
        source_registered_path=source_path,
        record=record,
        environment=environment,
        prompt_contract=prompt,
        compiler_trajectory=trajectory,
    )


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _descriptor(path: Path, root: Path) -> RawFileDescriptor:
    return RawFileDescriptor(
        relative_path=_relative(path, root),
        sha256=sha256(path),
        byte_count=path.stat().st_size,
    )


def raw_provider_path(output_dir: Path, job: Exact8KJob, call_index: int) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_provider_calls" / job_hash / f"call_{call_index:04d}.json"


def raw_execution_path(output_dir: Path, job: Exact8KJob) -> Path:
    job_hash = hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "raw_execution" / f"{job_hash}.json"


def _envelope_from_telemetry(
    telemetry: ModelCallTelemetry,
) -> RedactedProviderResponseEnvelope | None:
    payload = telemetry.response_shape.get("redacted_response_envelope")
    if not isinstance(payload, Mapping):
        return None
    try:
        return RedactedProviderResponseEnvelope.model_validate(payload)
    except ValidationError:
        return None


def _completion_failure_artifact(
    *,
    failure_type: CompletionFailureKind,
    telemetry: ModelCallTelemetry,
) -> ProspectiveThinkingFailureArtifact | None:
    envelope = _envelope_from_telemetry(telemetry)
    if envelope is None:
        return None
    artifact = make_prospective_thinking_failure_artifact(
        failure_type=failure_type,
        request_hash=telemetry.request_hash,
        response_envelope=envelope,
    )
    serialize_validated_failure_artifact(artifact)
    return artifact


class JournaledExact8KClient:
    """Prepare all certificates, then invoke and persist one redacted Provider result."""

    def __init__(
        self,
        delegate: Any,
        *,
        execution_contract: Exact8KExecutionContract,
        job: Exact8KJob,
        provider_contract: ProviderTokenBudgetContract,
        completion_protocol: ProspectiveThinkingCompletionBoundProtocol,
        output_dir: Path,
    ) -> None:
        config = require_exact_8k_model_config(delegate.config)
        if (
            config.public_manifest_hash != execution_contract.model_config_id
            or bind_prospective_thinking(config).binding_id
            != execution_contract.thinking_binding_id
            or provider_contract.contract_id != execution_contract.provider_budget_contract_id
            or provider_contract.maximum_output_tokens != 8192
            or provider_contract.maximum_total_tokens != 160000
            or completion_protocol.protocol_id != execution_contract.completion_bound_protocol_id
            or job.candidate_id != completion_protocol.initial_candidate_id
        ):
            raise ValueError("v26.100 journal client differs from the frozen exact 8K route")
        self._delegate = delegate
        self._execution_contract = execution_contract
        self._job = job
        self._provider_contract = provider_contract
        self._completion_protocol = completion_protocol
        self._output_dir = output_dir
        self._certificates: list[ProviderTokenBudgetCertificate] = []
        self._usage_records: list[ProviderTokenUsageRecord] = []
        self._telemetry: list[ModelCallTelemetry] = []
        self._prompts: list[str] = []
        self._descriptors: list[RawFileDescriptor] = []
        self._provider_call_ids: list[str] = []
        self._contract_failure_ids: set[str] = set()
        self._no_call_terminal: ProviderBudgetNoCallTerminal | None = None
        self._used_preparations: set[str] = set()
        self._cumulative_tokens = 0

    @property
    def config(self) -> AgentModelConfig:
        return self._delegate.config

    @property
    def provider_call_count(self) -> int:
        return len(self._telemetry)

    @property
    def cumulative_tokens(self) -> int:
        return self._cumulative_tokens

    @property
    def telemetry(self) -> tuple[ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    @property
    def prompts(self) -> tuple[str, ...]:
        return tuple(self._prompts)

    @property
    def descriptors(self) -> tuple[RawFileDescriptor, ...]:
        return tuple(self._descriptors)

    @property
    def provider_call_ids(self) -> tuple[str, ...]:
        return tuple(self._provider_call_ids)

    @property
    def no_call_terminal(self) -> ProviderBudgetNoCallTerminal | None:
        return self._no_call_terminal

    def _reserves(
        self,
        *,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        rescue_available_before: bool,
    ) -> tuple[int, int]:
        repair = (
            self._execution_contract.completion_rescue_reserve_tokens
            if phase == "primary" and rescue_available_before
            else 0
        )
        final = (
            self._execution_contract.final_answer_reserve_tokens
            if request_kind == "decision"
            else 0
        )
        return repair, final

    def _provider_certificate(
        self,
        prompt: str,
        *,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        rescue_available_before: bool,
    ) -> ProviderTokenBudgetCertificate:
        contract = self._provider_contract
        prompt_bytes = len(prompt.encode("utf-8"))
        prompt_upper = prompt_bytes + contract.provider_chat_envelope_token_upper_bound
        request_upper = prompt_upper + contract.maximum_output_tokens
        repair, final = self._reserves(
            phase=phase,
            request_kind=request_kind,
            rescue_available_before=rescue_available_before,
        )
        projected_without_reserve = self._cumulative_tokens + request_upper
        projected = projected_without_reserve + repair + final
        denial: (
            Literal[
                "oversized_prompt",
                "request_bound_exceeds_remaining_budget",
                "required_reserve_not_available",
            ]
            | None
        ) = None
        if prompt_bytes > contract.maximum_prompt_utf8_bytes:
            denial = "oversized_prompt"
        elif projected_without_reserve > contract.maximum_total_tokens:
            denial = "request_bound_exceeds_remaining_budget"
        elif projected > contract.maximum_total_tokens:
            denial = "required_reserve_not_available"
        values = {
            "contract_id": contract.contract_id,
            "request_index": len(self._certificates),
            "request_kind": "contract_repair" if phase == "rescue" else request_kind,
            "repaired_request_kind": request_kind if phase == "rescue" else None,
            "request_hash": sha256_text(prompt),
            "prompt_utf8_bytes": prompt_bytes,
            "prompt_token_upper_bound": prompt_upper,
            "completion_token_upper_bound": contract.maximum_output_tokens,
            "request_token_upper_bound": request_upper,
            "cumulative_provider_tokens_before": self._cumulative_tokens,
            "contract_repair_reserve_tokens": repair,
            "final_answer_reserve_tokens": final,
            "required_reserve_tokens": repair + final,
            "projected_upper_total": projected,
            "maximum_total_tokens": contract.maximum_total_tokens,
            "decision": "denied_no_call" if denial is not None else "allowed",
            "denial_reason": denial,
            "provider_call_permitted": denial is None,
        }
        provisional = ProviderTokenBudgetCertificate.model_construct(
            certificate_id="pending",
            **values,
        )
        return ProviderTokenBudgetCertificate(
            certificate_id=provider_token_budget_certificate_id(provisional),
            **values,
        )

    def prepare_request(
        self,
        *,
        phase: AttemptPhase,
        request_kind: CompletionRequestKind,
        primary_prompt: str,
        prompt: str,
        failure_type: CompletionFailureKind | None,
        rescue_available_before: bool,
    ) -> Prepared8KRequest:
        if self._contract_failure_ids or self._no_call_terminal is not None:
            raise ValueError("v26.100 cannot prepare after a terminal budget state")
        request_binding = certify_exact_8k_request_pre_call(
            config=self.config,
            prompt=prompt,
            profile_sha256=EXACT_8K_PROFILE_SHA256,
        )
        provider_certificate = self._provider_certificate(
            prompt,
            phase=phase,
            request_kind=request_kind,
            rescue_available_before=rescue_available_before,
        )
        self._certificates.append(provider_certificate)
        dynamic = None
        if provider_certificate.provider_call_permitted:
            reserves = provider_certificate.required_reserve_tokens
            if phase == "primary":
                dynamic = certify_dynamic_primary_pre_call(
                    protocol=self._completion_protocol,
                    candidate_id=self._job.candidate_id,
                    request_kind=request_kind,
                    primary_prompt=primary_prompt,
                    cumulative_usage_tokens_before_request=self._cumulative_tokens,
                    required_future_reserve_tokens=reserves,
                )
            else:
                if failure_type is None:
                    raise ValueError("v26.100 Rescue preparation lacks a failure type")
                rendered, dynamic = certify_dynamic_rescue_pre_call(
                    protocol=self._completion_protocol,
                    candidate_id=self._job.candidate_id,
                    request_kind=request_kind,
                    primary_prompt=primary_prompt,
                    failure_type=failure_type,
                    cumulative_usage_tokens_before_request=self._cumulative_tokens,
                    required_future_reserve_tokens=reserves,
                )
                if rendered != prompt:
                    raise ValueError("v26.100 prepared Rescue differs from the bounded renderer")
        values = {
            "request_index": provider_certificate.request_index,
            "phase": phase,
            "request_kind": request_kind,
            "primary_prompt": primary_prompt,
            "prompt": prompt,
            "failure_type": failure_type,
            "dynamic_certificate": dynamic,
            "request_binding_certificate": request_binding,
            "provider_budget_certificate": provider_certificate,
            "all_provider_certificates_complete": dynamic is not None,
            "provider_invocation_authorized": bool(
                dynamic is not None and provider_certificate.provider_call_permitted
            ),
        }
        provisional = Prepared8KRequest.model_construct(preparation_id="pending", **values)
        return Prepared8KRequest(
            preparation_id=prepared_8k_request_id(provisional),
            **values,
        )

    def _persist_provider_call(
        self,
        *,
        logical_request_index: int,
        prepared: Prepared8KRequest,
        payload: dict[str, Any] | None,
        telemetry: ModelCallTelemetry,
        failure_artifact: ProspectiveThinkingFailureArtifact | None,
    ) -> None:
        if prepared.dynamic_certificate is None:
            raise ValueError("v26.100 cannot persist an uncertified Provider call")
        call_index = len(self._telemetry)
        provider_call_id = exact_8k_provider_call_id(
            self._job.job_id,
            call_index,
            telemetry,
            prepared.request_binding_certificate.certificate_id,
        )
        values = {
            "execution_contract_id": self._execution_contract.contract_id,
            "job_id": self._job.job_id,
            "logical_request_index": logical_request_index,
            "call_index": call_index,
            "phase": prepared.phase,
            "request_kind": prepared.request_kind,
            "provider_call_id": provider_call_id,
            "prompt": prepared.prompt,
            "prompt_sha256": sha256_text(prepared.prompt),
            "dynamic_certificate": prepared.dynamic_certificate,
            "request_binding_certificate": prepared.request_binding_certificate,
            "provider_budget_certificate_id": (prepared.provider_budget_certificate.certificate_id),
            "response_payload": payload,
            "provider_telemetry": telemetry,
            "failure_artifact": failure_artifact,
        }
        provisional = Exact8KRawProviderCall.model_construct(artifact_id="pending", **values)
        artifact = Exact8KRawProviderCall(
            artifact_id=exact_8k_raw_provider_call_id(provisional),
            **values,
        )
        path = raw_provider_path(self._output_dir, self._job, call_index)
        write_json_atomic(path, artifact.model_dump(mode="json"))
        self._telemetry.append(telemetry)
        self._prompts.append(prepared.prompt)
        self._descriptors.append(_descriptor(path, self._output_dir))
        self._provider_call_ids.append(provider_call_id)

    def _record_usage(
        self,
        prepared: Prepared8KRequest,
        telemetry: ModelCallTelemetry,
    ) -> None:
        certificate = prepared.provider_budget_certificate
        checks: dict[str, bool] = {
            "request_hash_match": telemetry.request_hash == certificate.request_hash,
            "requested_model_match": telemetry.model_requested == EXACT_8K_MODEL_ID,
            "selected_model_match": telemetry.model_selected == EXACT_8K_MODEL_ID,
            "fallback_absent": not telemetry.fallback_used,
            "request_binding_exact_8k": (
                prepared.request_binding_certificate.request_max_tokens == 8192
            ),
        }
        counted = 0
        if telemetry.http_success:
            prompt_tokens = telemetry.prompt_tokens
            completion_tokens = telemetry.completion_tokens
            total_tokens = telemetry.total_tokens
            checks.update(
                {
                    "successful_usage_present": (
                        prompt_tokens is not None
                        and completion_tokens is not None
                        and total_tokens is not None
                    ),
                    "prompt_completion_sum_match": (
                        prompt_tokens is not None
                        and completion_tokens is not None
                        and total_tokens is not None
                        and prompt_tokens + completion_tokens == total_tokens
                    ),
                    "prompt_upper_bound_respected": (
                        prompt_tokens is not None
                        and prompt_tokens <= certificate.prompt_token_upper_bound
                    ),
                    "completion_upper_bound_respected": (
                        completion_tokens is not None and completion_tokens <= 8192
                    ),
                    "request_upper_bound_respected": (
                        total_tokens is not None
                        and total_tokens <= certificate.request_token_upper_bound
                    ),
                    "rollout_ceiling_respected": (
                        total_tokens is not None
                        and self._cumulative_tokens + total_tokens <= 160000
                    ),
                }
            )
            if telemetry.prompt_cache_hit_tokens is not None or (
                telemetry.prompt_cache_miss_tokens is not None
            ):
                checks["cache_partition_sum_match"] = bool(
                    prompt_tokens is not None
                    and telemetry.prompt_cache_hit_tokens is not None
                    and telemetry.prompt_cache_miss_tokens is not None
                    and telemetry.prompt_cache_hit_tokens + telemetry.prompt_cache_miss_tokens
                    == prompt_tokens
                )
            if total_tokens is not None:
                counted = total_tokens
        ordered = dict(sorted(checks.items()))
        failures = tuple(f"resource_budget:{key}" for key, passed in ordered.items() if not passed)
        cumulative_after = self._cumulative_tokens + counted
        values = {
            "contract_id": self._provider_contract.contract_id,
            "certificate_id": certificate.certificate_id,
            "request_index": certificate.request_index,
            "request_hash": certificate.request_hash,
            "http_success": telemetry.http_success,
            "prompt_tokens": telemetry.prompt_tokens,
            "completion_tokens": telemetry.completion_tokens,
            "total_tokens": telemetry.total_tokens,
            "counted_tokens": counted,
            "cumulative_provider_tokens_after": cumulative_after,
            "validation_checks": ordered,
            "failure_ids": failures,
            "passed": not failures,
        }
        provisional = ProviderTokenUsageRecord.model_construct(record_id="pending", **values)
        record = ProviderTokenUsageRecord(
            record_id=provider_token_usage_record_id(provisional),
            **values,
        )
        self._usage_records.append(record)
        self._cumulative_tokens = cumulative_after
        self._contract_failure_ids.update(failures)

    def invoke(
        self,
        prepared: Prepared8KRequest,
        *,
        logical_request_index: int,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if prepared.preparation_id in self._used_preparations:
            raise LLMClientError("v26.100 prepared request cannot be invoked twice")
        self._used_preparations.add(prepared.preparation_id)
        certificate = prepared.provider_budget_certificate
        if not certificate.provider_call_permitted:
            values = {
                "contract_id": self._provider_contract.contract_id,
                "denied_certificate_id": certificate.certificate_id,
                "request_index": certificate.request_index,
                "request_kind": certificate.request_kind,
                "request_hash": certificate.request_hash,
                "reason_code": certificate.denial_reason,
            }
            provisional = ProviderBudgetNoCallTerminal.model_construct(
                terminal_id="pending",
                **values,
            )
            self._no_call_terminal = ProviderBudgetNoCallTerminal(
                terminal_id=provider_budget_no_call_terminal_id(provisional),
                **values,
            )
            raise LLMClientError(
                f"Provider call denied before invocation: {certificate.denial_reason}"
            )
        if not prepared.provider_invocation_authorized or prepared.dynamic_certificate is None:
            raise LLMClientError("v26.100 Provider invocation lacks all pre-call certificates")
        try:
            payload, telemetry = self._delegate.complete_json_certified(
                prepared.prompt,
                prepared.request_binding_certificate,
            )
        except LLMClientError as exc:
            if len(exc.telemetry) > 1:
                self._contract_failure_ids.add("resource_budget:multiple_model_attempts")
            artifact = (
                exc.failure_artifact
                if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
                else None
            )
            for item in exc.telemetry:
                self._persist_provider_call(
                    logical_request_index=logical_request_index,
                    prepared=prepared,
                    payload=None,
                    telemetry=item,
                    failure_artifact=artifact,
                )
                self._record_usage(prepared, item)
            if self._contract_failure_ids:
                raise LLMClientError(
                    "v26.100 Provider budget or binding Contract failed",
                    exc.telemetry,
                    failure_artifact=artifact,
                ) from exc
            raise
        self._persist_provider_call(
            logical_request_index=logical_request_index,
            prepared=prepared,
            payload=payload,
            telemetry=telemetry,
            failure_artifact=None,
        )
        self._record_usage(prepared, telemetry)
        if self._contract_failure_ids:
            raise LLMClientError(
                "v26.100 Provider budget or binding Contract failed",
                (telemetry,),
            )
        return payload, telemetry

    def audit(self) -> ProviderTokenBudgetAudit:
        failures = tuple(sorted(self._contract_failure_ids))
        values = {
            "contract_id": self._provider_contract.contract_id,
            "certificates": tuple(self._certificates),
            "usage_records": tuple(self._usage_records),
            "no_call_terminal": self._no_call_terminal,
            "actual_request_prompt_hashes": tuple(sha256_text(item) for item in self._prompts),
            "provider_call_count": len(self._usage_records),
            "permitted_request_count": sum(
                item.provider_call_permitted for item in self._certificates
            ),
            "denied_no_call_count": sum(
                not item.provider_call_permitted for item in self._certificates
            ),
            "cumulative_provider_tokens": self._cumulative_tokens,
            "maximum_total_tokens": self._provider_contract.maximum_total_tokens,
            "contract_failure_ids": failures,
            "all_provider_calls_precertified": len(self._usage_records)
            <= sum(item.provider_call_permitted for item in self._certificates),
            "strict_budget_closed": not failures,
            "status": "failed" if failures else "passed",
        }
        provisional = ProviderTokenBudgetAudit.model_construct(audit_id="pending", **values)
        return ProviderTokenBudgetAudit(
            audit_id=provider_token_budget_audit_id(provisional),
            **values,
        )


def _safe_error(error: Exception) -> str:
    return f"{type(error).__name__}: {str(error)[:500]}"


def _attempt_disposition_from_error(
    exc: LLMClientError,
    *,
    ledger: JournaledExact8KClient,
) -> tuple[AttemptDisposition, ProspectiveThinkingFailureArtifact | None]:
    if ledger.no_call_terminal is not None and not exc.telemetry:
        return "typed_budget_no_call", None
    artifact = (
        exc.failure_artifact
        if isinstance(exc.failure_artifact, ProspectiveThinkingFailureArtifact)
        else None
    )
    if artifact is not None and artifact.failure_type in {
        "empty_final_content",
        "invalid_json",
        "invalid_response_contract",
        "length_truncated_content",
        "reasoning_only_length_truncation",
    }:
        return "completion_failure", artifact
    if exc.telemetry and not all(item.http_success for item in exc.telemetry):
        return "provider_transport_failure", artifact
    return "instrument_failure", artifact


def request_attempt(
    *,
    ledger: JournaledExact8KClient,
    source_path: ThinkingRepairPathAudit,
    logical_index: int,
    request_kind: CompletionRequestKind,
    phase: AttemptPhase,
    primary_prompt: str,
    prompt: str,
    failure_type: CompletionFailureKind | None,
    rescue_available_before: bool,
) -> Exact8KRequestAttempt:
    provider_index_before = ledger.provider_call_count
    registered = (
        source_path.request_audits[logical_index]
        if logical_index < len(source_path.request_audits)
        else None
    )
    prepared: Prepared8KRequest | None = None
    provider_call_made = False
    projection: CompletionProjection | None = None
    failure_artifact: ProspectiveThinkingFailureArtifact | None = None
    disposition: AttemptDisposition = "instrument_failure"
    error: str | None = None
    payload_present = False
    try:
        prepared = ledger.prepare_request(
            phase=phase,
            request_kind=request_kind,
            primary_prompt=primary_prompt,
            prompt=prompt,
            failure_type=failure_type,
            rescue_available_before=rescue_available_before,
        )
        payload, telemetry = ledger.invoke(prepared, logical_request_index=logical_index)
        provider_call_made = ledger.provider_call_count > provider_index_before
        payload_present = True
        try:
            projection = project_model_completion(request_kind, payload)
            disposition = "usable"
        except ValueError as exc:
            error = _safe_error(exc)
            failure_artifact = _completion_failure_artifact(
                failure_type="invalid_response_contract",
                telemetry=telemetry,
            )
            disposition = (
                "completion_failure" if failure_artifact is not None else "instrument_failure"
            )
    except LLMClientError as exc:
        provider_call_made = ledger.provider_call_count > provider_index_before
        disposition, failure_artifact = _attempt_disposition_from_error(exc, ledger=ledger)
        error = _safe_error(exc)
    except Exception as exc:
        provider_call_made = ledger.provider_call_count > provider_index_before
        disposition = "instrument_failure"
        error = _safe_error(exc)
    values = {
        "logical_request_index": logical_index,
        "provider_call_index": provider_index_before if provider_call_made else None,
        "phase": phase,
        "request_kind": request_kind,
        "prompt_sha256": sha256_text(prompt),
        "prompt_utf8_bytes": len(prompt.encode("utf-8")),
        "dynamic_certificate": prepared.dynamic_certificate if prepared is not None else None,
        "request_binding_certificate": (
            prepared.request_binding_certificate if prepared is not None else None
        ),
        "provider_budget_certificate_id": (
            prepared.provider_budget_certificate.certificate_id if prepared is not None else None
        ),
        "precall_certificates_complete": bool(
            prepared is not None and prepared.all_provider_certificates_complete
        ),
        "registered_request_present": registered is not None,
        "registered_request_kind_match": (
            registered is not None and registered.request_kind == request_kind
        ),
        "registered_primary_prompt_match": (
            phase == "primary"
            and registered is not None
            and registered.primary_prompt_sha256 == sha256_text(prompt)
        ),
        "rescue_prompt_within_absolute_ceiling": (
            len(prompt.encode("utf-8")) <= 6144 if phase == "rescue" else None
        ),
        "provider_call_made": provider_call_made,
        "response_payload_present": payload_present,
        "completion_projection": projection,
        "failure_artifact": failure_artifact,
        "disposition": disposition,
        "error": error,
    }
    provisional = Exact8KRequestAttempt.model_construct(attempt_id="pending", **values)
    return Exact8KRequestAttempt(
        attempt_id=exact_8k_request_attempt_id(provisional),
        **values,
    )


def _logical_request(
    *,
    logical_index: int,
    request_kind: CompletionRequestKind,
    source_prompt: str,
    primary: Exact8KRequestAttempt,
    rescue: Exact8KRequestAttempt | None,
) -> ThinkingRepairLogicalRequest:
    if primary.disposition == "usable":
        outcome = "direct_usable"
    elif rescue is not None and rescue.disposition == "usable":
        outcome = "rescued_usable"
    else:
        terminal = rescue or primary
        outcome = {
            "completion_failure": "terminal_completion_unusable",
            "provider_transport_failure": "terminal_provider_transport_failure",
            "typed_budget_no_call": "terminal_typed_budget_no_call",
            "instrument_failure": "terminal_instrument_failure",
        }[terminal.disposition]
    initial = (
        cast(CompletionFailureKind, primary.failure_artifact.failure_type)
        if rescue is not None and primary.failure_artifact is not None
        else None
    )
    values = {
        "logical_request_index": logical_index,
        "request_kind": request_kind,
        "source_prompt_sha256": sha256_text(source_prompt),
        "primary_attempt_id": primary.attempt_id,
        "rescue_attempt_id": rescue.attempt_id if rescue is not None else None,
        "rescue_used": rescue is not None,
        "initial_failure_type": initial,
        "outcome": outcome,
        "usable": outcome in {"direct_usable", "rescued_usable"},
    }
    provisional = ThinkingRepairLogicalRequest.model_construct(request_id="pending", **values)
    return ThinkingRepairLogicalRequest(
        request_id=thinking_repair_logical_request_id(provisional),
        **values,
    )


def _source_prompt(
    *,
    request_kind: CompletionRequestKind,
    prompt_contract: CompactPromptContract,
    record: OperationalTaskRecord,
    observations: Sequence[AgentToolObservation],
    source_path: ThinkingRepairPathAudit,
) -> str:
    public_condition = None if source_path.role == "capability" else source_path.path_strategy_id
    if request_kind == "final_answer":
        return render_compact_final_prompt(
            prompt_contract.public_context,
            record.task_package.task.public,
            tuple(observations),
            public_path_condition=public_condition,
        )
    return render_compact_decision_prompt(
        prompt_contract.public_context,
        record.task_package.task.public,
        tuple(observations),
        public_path_condition=public_condition,
    )


def _terminal_disposition(attempt: Exact8KRequestAttempt) -> str:
    return {
        "typed_budget_no_call": "typed_budget_no_call",
        "completion_failure": "completion_unusable",
        "provider_transport_failure": "provider_transport_failure",
        "instrument_failure": "instrument_failure",
    }[attempt.disposition]


def _load_raw_execution(path: Path) -> Exact8KRawExecution:
    return Exact8KRawExecution.model_validate(load_canonical_json(path))


def execute_exact_8k_job_raw(
    *,
    job: Exact8KJob,
    execution_contract: Exact8KExecutionContract,
    provider_contract: ProviderTokenBudgetContract,
    completion_protocol: ProspectiveThinkingCompletionBoundProtocol,
    binding: RuntimeBinding,
    client: Any | None,
    output_dir: Path,
) -> Exact8KRawExecution:
    raw_path = raw_execution_path(output_dir, job)
    if raw_path.exists():
        raw = _load_raw_execution(raw_path)
        if raw.execution_contract_id != execution_contract.contract_id or raw.job != job:
            raise ValueError("v26.101 raw-only recovery crosses frozen identities")
        return raw
    provider_dir = raw_provider_path(output_dir, job, 0).parent
    if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
        raise ValueError(
            "orphan v26.101 Provider Artifacts exist without a Raw Execution; "
            "automatic model retry is forbidden"
        )
    if client is None:
        raise ValueError("pending v26.101 Job has no model client")
    if (
        job.contract_id != execution_contract.predecessor_contract_id
        or job.task_package_id != binding.task_package.task_package_id
        or job.path_audit_id != binding.exact_path.audit_id
        or job.source_task_artifact_id != binding.task_package.source_task_artifact_id
        or job.path_strategy_id != binding.source_registered_path.path_strategy_id
        or binding.record.task_package.package_id
        != binding.prompt_contract.operational_task_package_id
        or binding.record.environment_manifest_id != binding.environment.manifest_id
    ):
        raise ValueError("v26.101 execution inputs differ from the frozen Job")

    ledger = JournaledExact8KClient(
        client,
        execution_contract=execution_contract,
        job=job,
        provider_contract=provider_contract,
        completion_protocol=completion_protocol,
        output_dir=output_dir,
    )
    runtime = _runtime(binding.record, binding.environment)
    observations: list[AgentToolObservation] = []
    attempts: list[Exact8KRequestAttempt] = []
    logical_requests: list[ThinkingRepairLogicalRequest] = []
    completed: ThinkingRepairCompletedResult | None = None
    terminal = "model_invalid"
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    rescue_used = False
    maximum_logical_requests = binding.environment.maximum_tool_calls + 1

    for logical_index in range(maximum_logical_requests):
        progress = compact_public_progress(
            binding.record.task_package.task.public,
            tuple(observations),
        )
        request_kind: CompletionRequestKind = (
            "final_answer" if progress["final_answer_allowed"] else "decision"
        )
        source_prompt = _source_prompt(
            request_kind=request_kind,
            prompt_contract=binding.prompt_contract,
            record=binding.record,
            observations=observations,
            source_path=binding.source_registered_path,
        )
        primary_prompt = render_primary_completion_prompt(request_kind, source_prompt)
        primary = request_attempt(
            ledger=ledger,
            source_path=binding.source_registered_path,
            logical_index=logical_index,
            request_kind=request_kind,
            phase="primary",
            primary_prompt=primary_prompt,
            prompt=primary_prompt,
            failure_type=None,
            rescue_available_before=not rescue_used,
        )
        attempts.append(primary)
        rescue: Exact8KRequestAttempt | None = None
        active = primary
        if primary.disposition == "completion_failure" and not rescue_used:
            if primary.failure_artifact is None:
                raise ValueError("v26.101 Completion failure lacks a Rescue type")
            failure_type = cast(CompletionFailureKind, primary.failure_artifact.failure_type)
            rescue_used = True
            rescue_prompt = render_bounded_rescue_completion_prompt(
                request_kind,
                primary_prompt,
                failure_type,
            )
            rescue = request_attempt(
                ledger=ledger,
                source_path=binding.source_registered_path,
                logical_index=logical_index,
                request_kind=request_kind,
                phase="rescue",
                primary_prompt=primary_prompt,
                prompt=rescue_prompt,
                failure_type=failure_type,
                rescue_available_before=False,
            )
            attempts.append(rescue)
            active = rescue
        logical = _logical_request(
            logical_index=logical_index,
            request_kind=request_kind,
            source_prompt=source_prompt,
            primary=primary,
            rescue=rescue,
        )
        logical_requests.append(logical)
        if active.disposition != "usable":
            terminal = _terminal_disposition(active)
            terminal_failure_type = (
                active.failure_artifact.failure_type
                if active.failure_artifact is not None
                else active.disposition
            )
            execution_error = active.error
            break
        projection = cast(CompletionProjection, active.completion_projection)
        if request_kind == "decision":
            observations.append(
                _execute_observation(
                    record=binding.record,
                    environment=binding.environment,
                    runtime=runtime,
                    observations=observations,
                    projection=projection,
                )
            )
            if len(observations) >= binding.environment.maximum_tool_calls:
                next_progress = compact_public_progress(
                    binding.record.task_package.task.public,
                    tuple(observations),
                )
                if not next_progress["final_answer_allowed"]:
                    terminal = "model_invalid"
                    execution_error = "model exhausted the frozen public tool-call budget"
                    break
            continue
        citations = _selected_evidence_ids(observations)
        if not citations:
            terminal = "model_invalid"
            execution_error = "final answer has no successfully selected public Evidence"
            break
        completed_values = {
            "job_id": job.job_id,
            "observations": tuple(observations),
            "answer": projection.answer or {},
            "cited_evidence_ids": citations,
            "final_request_id": logical.request_id,
        }
        provisional_completed = ThinkingRepairCompletedResult.model_construct(
            result_id="pending",
            **completed_values,
        )
        completed = ThinkingRepairCompletedResult(
            result_id=thinking_repair_completed_result_id(provisional_completed),
            **completed_values,
        )
        terminal = "completed"
        break

    budget_audit = ledger.audit()
    if budget_audit.status != "passed":
        terminal = "instrument_failure"
        terminal_failure_type = "provider_budget_contract_failure"
        execution_error = ";".join(budget_audit.contract_failure_ids)
        completed = None
    raw_values = {
        "execution_contract_id": execution_contract.contract_id,
        "job": job,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "path_audit_id": binding.exact_path.audit_id,
        "source_registered_path_audit_id": binding.source_registered_path.audit_id,
        "provider_call_artifacts": ledger.descriptors,
        "provider_call_ids": ledger.provider_call_ids,
        "provider_telemetry": ledger.telemetry,
        "provider_prompts": ledger.prompts,
        "request_attempts": tuple(attempts),
        "logical_requests": tuple(logical_requests),
        "provider_budget_audit": budget_audit,
        "observations": tuple(observations),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": terminal_failure_type,
        "execution_error": execution_error,
        "rescue_attempt_count": sum(item.phase == "rescue" for item in attempts),
        "rescue_provider_call_count": sum(
            item.phase == "rescue" and item.provider_call_made for item in attempts
        ),
    }
    provisional_raw = Exact8KRawExecution.model_construct(artifact_id="pending", **raw_values)
    raw = Exact8KRawExecution(
        artifact_id=exact_8k_raw_execution_id(provisional_raw),
        **raw_values,
    )
    write_json_atomic(raw_path, raw.model_dump(mode="json"))
    return raw


def score_exact_8k_raw_execution(
    *,
    raw: Exact8KRawExecution,
    prepared: Any,
    binding: RuntimeBinding,
    output_dir: Path,
) -> ThinkingRepairJobResult:
    return _score_raw_execution(
        raw=cast(Any, raw),
        prepared=cast(Any, prepared),
        record=binding.record,
        environment=binding.environment,
        output_dir=output_dir,
    )


def _cp_upper(failures: int, denominator: int, *, alpha: float = 0.05) -> float:
    if not 0 <= failures <= denominator or denominator <= 0:
        raise ValueError("invalid Clopper-Pearson inputs")
    if failures == denominator:
        return 1.0
    if failures == 0:
        return 1.0 - alpha ** (1.0 / denominator)

    def cdf(probability: float) -> float:
        return sum(
            comb(denominator, index)
            * probability**index
            * (1.0 - probability) ** (denominator - index)
            for index in range(failures + 1)
        )

    low = failures / denominator
    high = 1.0
    for _ in range(160):
        middle = (low + high) / 2.0
        if cdf(middle) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _next_transition(
    interpretation: Exact8KOutcomeInterpretationContract,
    results: Sequence[ThinkingRepairJobResult],
) -> str:
    if any(item.provider_transport_failure for item in results):
        return interpretation.transport_failure_transition
    instrument = [item for item in results if item.terminal_category == "instrument_failure"]
    if instrument:
        if all(item.telemetry_only_failure for item in instrument):
            return interpretation.telemetry_only_failure_transition
        return interpretation.other_instrument_failure_transition
    if any(item.typed_no_call for item in results):
        return interpretation.dynamic_budget_failure_transition
    if any(item.completion_unusable for item in results):
        observed = {
            key
            for item in results
            for key, count in item.completion_failure_counts.items()
            if count
        }
        if observed & {"length_truncated_content", "reasoning_only_length_truncation"}:
            return interpretation.length_failure_transition
        return interpretation.nonlength_completion_failure_transition
    return interpretation.pass_transition


def raw_lineage_audit(
    *,
    prepared: Any,
    results: Sequence[ThinkingRepairJobResult],
    raw_by_job: Mapping[str, Exact8KRawExecution],
    output_dir: Path,
) -> Exact8KRawLineageAudit:
    files: list[RawFileDescriptor] = []
    provider_ids: list[str] = []
    private_hits = 0
    for result in results:
        raw = raw_by_job[result.job_id]
        path = raw_execution_path(output_dir, raw.job)
        replayed = _load_raw_execution(path)
        if replayed.model_dump(mode="json") != raw.model_dump(mode="json"):
            raise ValueError(f"v26.101 Raw Execution replay changed: {result.job_id}")
        files.append(_descriptor(path, output_dir))
        provider_ids.extend(raw.provider_call_ids)
        for descriptor in raw.provider_call_artifacts:
            provider_path = output_dir / descriptor.relative_path
            payload = load_canonical_json(provider_path)
            reparsed = Exact8KRawProviderCall.model_validate(payload)
            if (
                sha256(provider_path) != descriptor.sha256
                or reparsed.provider_call_id not in raw.provider_call_ids
            ):
                raise ValueError("v26.101 Provider Artifact binding changed")
            private_hits += int(
                any(
                    str(key) in {"private_reasoning", "reasoning_content"}
                    for key in _recursive_keys(payload)
                )
            )
            files.append(_descriptor(provider_path, output_dir))
    ordered = tuple(sorted(files, key=lambda item: item.relative_path))
    values = {
        "execution_contract_id": prepared.execution_contract.contract_id,
        "provider_call_count": len(provider_ids),
        "unique_provider_call_count": len(set(provider_ids)),
        "files": ordered,
        "private_reasoning_payload_count": private_hits,
        "exact_byte_replay_pass_count": len(ordered),
    }
    provisional = Exact8KRawLineageAudit.model_construct(audit_id="pending", **values)
    return Exact8KRawLineageAudit(
        audit_id=exact_8k_raw_lineage_audit_id(provisional),
        **values,
    )


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _recursive_keys(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(key for item in value for key in _recursive_keys(item))
    return ()


def make_execution_report(
    *,
    prepared: Any,
    results: Sequence[ThinkingRepairJobResult],
    lineage: Exact8KRawLineageAudit,
    raw_by_job: Mapping[str, Exact8KRawExecution],
) -> Exact8KExecutionReport:
    typed = sum(item.typed_no_call for item in results)
    completion = sum(item.completion_unusable for item in results)
    transport = sum(item.provider_transport_failure for item in results)
    instrument = sum(item.terminal_category == "instrument_failure" for item in results)
    telemetry_only = sum(item.telemetry_only_failure for item in results)
    usage_complete = all(item.provider_usage_complete for item in results)
    telemetry_pass = all(
        item.exact_model_passed
        and item.native_tool_absent
        and item.thinking_continuity_passed
        and item.fallback_absent
        for item in results
    )
    exact_request_pass = all(
        attempt.request_binding_certificate is not None
        and attempt.request_binding_certificate.request_max_tokens == 8192
        for raw in raw_by_job.values()
        for attempt in raw.request_attempts
        if attempt.provider_call_made
    )
    dynamic_pass = all(
        attempt.dynamic_certificate is not None and attempt.precall_certificates_complete
        for raw in raw_by_job.values()
        for attempt in raw.request_attempts
        if attempt.provider_call_made
    )
    budget_gate = typed == 0
    completion_gate = completion == 0
    execution_integrity = not (transport or instrument) and usage_complete
    passed = (
        budget_gate
        and completion_gate
        and telemetry_pass
        and execution_integrity
        and exact_request_pass
        and dynamic_pass
    )
    program_closed = sum(item.program_closed for item in results)
    if not (telemetry_pass and execution_integrity and exact_request_pass and dynamic_pass):
        behavior = "instrument_or_transport_failed"
    elif completion:
        behavior = "completion_channel_failed"
    elif program_closed == 0:
        behavior = "completion_channel_passed_behavior_floor"
    else:
        behavior = "completion_channel_passed_behavior_nonfloor"
    completion_failures = Counter(
        {
            key: sum(item.completion_failure_counts.get(key, 0) for item in results)
            for key in {key for item in results for key in item.completion_failure_counts}
        }
    )
    cost = sum((Decimal(item.estimated_cost_usd) for item in results), Decimal("0"))
    values = {
        "execution_contract_id": prepared.execution_contract.contract_id,
        "preflight_report_id": prepared.preflight_report.report_id,
        "outcome_interpretation_contract_id": prepared.interpretation_contract.contract_id,
        "raw_lineage_audit_id": lineage.audit_id,
        "terminal_counts": dict(
            sorted(Counter(item.terminal_category for item in results).items())
        ),
        "provider_call_count": sum(item.provider_call_count for item in results),
        "http_success_call_count": sum(item.http_success_call_count for item in results),
        "provider_total_tokens": sum(item.provider_total_tokens for item in results),
        "provider_usage_complete": usage_complete,
        "estimated_cost_usd": format(cost, "f"),
        "reasoning_content_length_total": sum(
            item.reasoning_content_length_total for item in results
        ),
        "reasoning_tokens_total": sum(item.reasoning_tokens_total for item in results),
        "completion_tokens_total": sum(item.completion_tokens_total for item in results),
        "logical_request_count": sum(item.logical_request_count for item in results),
        "rescue_provider_call_count": sum(item.rescue_call_count for item in results),
        "completion_failure_counts": dict(sorted(completion_failures.items())),
        "typed_no_call_job_count": typed,
        "typed_no_call_cp95_upper_32": _cp_upper(typed, 32),
        "typed_no_call_gate_passed": budget_gate,
        "completion_unusable_job_count": completion,
        "completion_unusable_cp95_upper_32": _cp_upper(completion, 32),
        "completion_usability_gate_passed": completion_gate,
        "provider_transport_failure_job_count": transport,
        "instrument_failure_job_count": instrument,
        "telemetry_only_failure_job_count": telemetry_only,
        "program_closed_count": program_closed,
        "mechanism_success_count": sum(item.mechanism_success for item in results),
        "independently_valid_trajectory_count": sum(item.independent_validity for item in results),
        "requested_path_adherence_count": sum(item.requested_path_adhered for item in results),
        "cell_summaries": _cell_summaries(results),
        "exact_8k_request_binding_passed": exact_request_pass,
        "dynamic_precall_binding_passed": dynamic_pass,
        "empirical_budget_adequacy_passed": budget_gate,
        "completion_usability_passed": completion_gate,
        "response_telemetry_instrument_passed": telemetry_pass,
        "execution_integrity_passed": execution_integrity,
        "behavior_interpretation": behavior,
        "status": "passed" if passed else "blocked",
        "next_permitted_stage": _next_transition(
            prepared.interpretation_contract,
            results,
        ),
    }
    provisional = Exact8KExecutionReport.model_construct(report_id="pending", **values)
    return Exact8KExecutionReport(
        report_id=exact_8k_execution_report_id(provisional),
        **values,
    )


def prepare_exact_8k_execution(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> PreparedInputs:
    report = Exact8KRunnerPreflightReport.model_validate(
        load_canonical_json(runner_preflight_dir / "report.json")
    )
    replay = Exact8KRunnerSourceReplayAudit.model_validate(
        load_canonical_json(runner_preflight_dir / "source_replay_audit.json")
    )
    validate_runner_source_replay(replay, package_root)
    interpretation = Exact8KOutcomeInterpretationContract.model_validate(
        load_canonical_json(runner_preflight_dir / "outcome_interpretation_contract.json")
    )
    provider_contract = ProviderTokenBudgetContract.model_validate(
        load_canonical_json(runner_preflight_dir / "provider_token_budget_contract.json")
    )
    execution_contract = Exact8KExecutionContract.model_validate(
        load_canonical_json(runner_preflight_dir / "execution_contract.json")
    )
    if (
        report.run_id != RUNNER_PREFLIGHT_RUN_ID
        or report.execution_run_id != EXECUTION_RUN_ID
        or report.source_replay_audit_id != replay.audit_id
        or report.outcome_interpretation_contract_id != interpretation.contract_id
        or report.provider_budget_contract_id != provider_contract.contract_id
        or report.execution_contract_id != execution_contract.contract_id
        or not report.exact_8k_execution_authorized
        or execution_contract.source_replay_audit_id != replay.audit_id
        or execution_contract.provider_budget_contract_id != provider_contract.contract_id
        or execution_contract.runner_implementation_source_files
        != report.implementation_source_files
    ):
        raise ValueError("v26.100 preflight binding changed before execution")
    static = load_static_inputs(package_root)
    if (
        execution_contract.predecessor_contract_id != static.predecessor_contract.contract_id
        or execution_contract.predecessor_manifest_id != static.predecessor_manifest.manifest_id
        or execution_contract.predecessor_cross_binding_id != static.cross_binding.audit_id
        or execution_contract.job_ids
        != tuple(sorted(item.job_id for item in static.predecessor_manifest.jobs))
        or provider_contract.maximum_output_tokens != EXACT_8K_MAX_TOKENS
        or provider_contract.maximum_total_tokens != 160000
    ):
        raise ValueError("v26.101 execution denominator differs from v26.99/v26.100")
    prepared = PreparedInputs(
        preflight_report=report,
        execution_contract=execution_contract,
        interpretation_contract=interpretation,
        source_replay=replay,
        provider_budget_contract=provider_contract,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output_dir / "online_source_replay_audit.json",
        replay.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "execution_contract.json",
        execution_contract.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "frozen_exact_8k_completion_contract.json",
        static.predecessor_contract.model_dump(mode="json"),
    )
    write_json_atomic(
        output_dir / "frozen_exact_8k_job_manifest.json",
        static.predecessor_manifest.model_dump(mode="json"),
    )
    return prepared


def _load_checkpoint(
    path: Path,
    *,
    prepared: PreparedInputs,
    output_dir: Path,
) -> tuple[ThinkingRepairJobResult, ...]:
    if not path.exists():
        return ()
    rows = tuple(
        ThinkingRepairJobResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    jobs = {item.job_id: item for item in prepared.static.predecessor_manifest.jobs}
    if len({item.job_id for item in rows}) != len(rows):
        raise ValueError("v26.101 checkpoint contains duplicate Jobs")
    for result in rows:
        job = jobs.get(result.job_id)
        if job is None or result.execution_contract_id != prepared.execution_contract.contract_id:
            raise ValueError("v26.101 checkpoint crosses the frozen denominator")
        path = raw_execution_path(output_dir, job)
        if sha256(path) != result.raw_execution_artifact.sha256:
            raise ValueError("v26.101 checkpoint Raw binding changed")
    return rows


def _run_one_job(
    *,
    job: Exact8KJob,
    prepared: PreparedInputs,
    client: Any | None,
    output_dir: Path,
) -> tuple[ThinkingRepairJobResult, Exact8KRawExecution]:
    binding = runtime_binding(prepared.static, job)
    raw = execute_exact_8k_job_raw(
        job=job,
        execution_contract=prepared.execution_contract,
        provider_contract=prepared.provider_budget_contract,
        completion_protocol=prepared.static.completion_bound_protocol,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    result = score_exact_8k_raw_execution(
        raw=raw,
        prepared=prepared,
        binding=binding,
        output_dir=output_dir,
    )
    return result, raw


def run_exact_8k_completion_calibration(
    *,
    runner_preflight_dir: Path,
    output_dir: Path,
    package_root: Path,
    workers: int,
    client_factory: Callable[[AgentModelConfig], Any] = Exact8KProspectiveThinkingJsonClient,
) -> Exact8KExecutionReport:
    prepared = prepare_exact_8k_execution(
        runner_preflight_dir=runner_preflight_dir,
        output_dir=output_dir,
        package_root=package_root,
    )
    checkpoint_path = output_dir / "exact_8k_job_results.checkpoint.jsonl"
    existing = _load_checkpoint(
        checkpoint_path,
        prepared=prepared,
        output_dir=output_dir,
    )
    completed = {item.job_id: item for item in existing}
    jobs = prepared.static.predecessor_manifest.jobs
    pending = [item for item in jobs if item.job_id not in completed]
    report_path = output_dir / "report.json"
    if pending and report_path.exists():
        raise ValueError("v26.101 completed report exists while Jobs remain pending")
    if not pending and report_path.exists():
        report = Exact8KExecutionReport.model_validate(load_canonical_json(report_path))
        if report.execution_contract_id != prepared.execution_contract.contract_id:
            raise ValueError("v26.101 completed report crosses execution Contracts")
        return report
    raw_recovery_jobs = [item for item in pending if raw_execution_path(output_dir, item).exists()]
    model_pending_jobs = [
        item for item in pending if not raw_execution_path(output_dir, item).exists()
    ]
    for job in model_pending_jobs:
        provider_dir = raw_provider_path(output_dir, job, 0).parent
        if provider_dir.exists() and any(provider_dir.glob("call_*.json")):
            raise ValueError("orphan v26.101 Provider Artifacts require a fresh Recovery Contract")
    client: Any | None = (
        client_factory(prepared.static.agent_model_config) if model_pending_jobs else None
    )
    print(
        f"[v26.101] resuming {len(completed)}/32; "
        f"raw-only recovery {len(raw_recovery_jobs)}; "
        f"executing {len(model_pending_jobs)} Jobs with {workers} workers",
        flush=True,
    )
    raw_by_job: dict[str, Exact8KRawExecution] = {}
    for job in jobs:
        path = raw_execution_path(output_dir, job)
        if path.exists() and job.job_id in completed:
            raw_by_job[job.job_id] = _load_raw_execution(path)
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending) or 1))) as executor:
        future_map = {
            executor.submit(
                _run_one_job,
                job=job,
                prepared=prepared,
                client=None if job in raw_recovery_jobs else client,
                output_dir=output_dir,
            ): job
            for job in pending
        }
        for future in as_completed(future_map):
            job = future_map[future]
            result, raw = future.result()
            with lock:
                completed[job.job_id] = result
                raw_by_job[job.job_id] = raw
                ordered = [completed[item.job_id] for item in jobs if item.job_id in completed]
                payload = b"\n".join(
                    canonical_bytes(item.model_dump(mode="json")) for item in ordered
                )
                if payload:
                    payload += b"\n"
                checkpoint_path.write_bytes(payload)
    results = tuple(completed[item.job_id] for item in jobs)
    if len(results) != 32:
        raise ValueError("v26.101 execution denominator is incomplete")
    for job in jobs:
        raw_by_job.setdefault(job.job_id, _load_raw_execution(raw_execution_path(output_dir, job)))
    lineage = raw_lineage_audit(
        prepared=prepared,
        results=results,
        raw_by_job=raw_by_job,
        output_dir=output_dir,
    )
    report = make_execution_report(
        prepared=prepared,
        results=results,
        lineage=lineage,
        raw_by_job=raw_by_job,
    )
    write_json_atomic(
        output_dir / "exact_8k_job_results.json",
        [item.model_dump(mode="json") for item in results],
    )
    write_json_atomic(output_dir / "raw_lineage_audit.json", lineage.model_dump(mode="json"))
    write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the exact v26.101 Thinking 8K Completion calibration"
    )
    parser.add_argument("--runner-preflight-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        prepared = prepare_exact_8k_execution(
            runner_preflight_dir=args.runner_preflight_dir,
            output_dir=args.output_dir,
            package_root=args.package_root,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "execution_contract_id": prepared.execution_contract.contract_id,
                    "expected_jobs": len(prepared.static.predecessor_manifest.jobs),
                    "model_client_constructed": False,
                    "provider_calls": 0,
                },
                indent=2,
            )
        )
        return
    report = run_exact_8k_completion_calibration(
        runner_preflight_dir=args.runner_preflight_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
        workers=args.workers,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
