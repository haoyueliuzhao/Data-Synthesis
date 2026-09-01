from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    ComponentAttemptOutcome,
    JobBoundOutcomePayload,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    HardenedPublicObservation,
    StepRuntimeResult,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_preflight as v195_writer,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight as v197,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization as v199,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization_models as v199_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    parse_qualified_final_response,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneProspectiveThinkingJsonClient,
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = (
    "finance_v26_200_fresh_artifact_backed_terminal_to_outcome_exact_192_job_"
    "online_execution_v1_20260901"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_AUDIT_SHA256: Final = "fa4e19aee7dd71342671e10f0e223d40b3a636e5f19f0028799afde063e9243e"
EXTERNAL_AUDIT_BYTES: Final = 9_063
V199_REPORT_ID: Final = (
    "finance_v26_199_terminal_outcome_online_authorization_report:"
    "09fd76688a92e42efe0e7456283c4d3f09c42270e54f2aa0ee74143ea016892a"
)
V199_DECISION_ID: Final = (
    "finance_v26_199_online_authorization_decision:"
    "1321cb7fc2ed4f9cdc4f57c0c8c13e43354a551d8d7f9e4ffd6656d857cdc43d"
)
V199_TRANSITION_ID: Final = (
    "finance_v26_199_transition:c58fd5525394df82c032847a8126f6c2e72185d8ac378553dbf8c70b3b7e4c22"
)
V199_AUTHORIZATION_ID: Final = (
    "fresh_terminal_to_outcome_exact_online_execution_authorization:"
    "42aaca7f87e5766e7338c04a22d0eb49132a718e46506f4d1ca4459811cce600"
)
V199_SOURCE_COMMIT: Final = "5a2bc619292de2192cd54b6e60bfc115347f3cd8"
V199_SOURCE_TREE: Final = "805b5a757a2e21e316ce2bd1f3cfa41947a356e6"
V199_SEALED_ROOT: Final = (
    "finance_v26_199_sealed_evidence_artifact_root:"
    "bf4aa942af3665fe16f7458637d639f4633722e071db794bf7a334c2f59e8f41"
)
V199_DISTRIBUTION_ROOT: Final = (
    "finance_v26_199_distribution_artifact_root:"
    "bb52c6f850face7adfeb949313d02f7f9de8b49d3f9d10393c65d4f74da36e43"
)
MODEL_PROFILE_PATH: Final = "config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
MAX_WORKERS: Final = 8


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_no_replace(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (_canonical_json(value) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _safe(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _set_sha256(values: tuple[str, ...]) -> str:
    encoded = json.dumps(
        tuple(sorted(values)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(encoded)


@dataclass(frozen=True)
class JobParents:
    kernel_job: v194_models.AuthoritativeDevelopmentJob
    json_job: v192.JsonExplicitDevelopmentJob
    runtime_job: CapabilityDevelopmentJob


@dataclass(frozen=True)
class PreparedOnlineExecution:
    repository_root: Path
    package_root: Path
    output_dir: Path
    external_audit_path: Path
    external_audit_bytes: bytes
    external_decision: models.ExternalOnlineExecutionDecision
    v199_freeze: models.V199AuthorizationFreeze
    authorization: v199_models.ExactOnlineExecutionAuthorization
    preparation: models.ExactExecutionPreparation
    catalog: v194_models.AuthoritativeRunnerPackageCatalog
    manifest: v194_models.AuthoritativeDevelopmentManifest
    runner: v194_models.AuthoritativeRunnerContract
    execution: v194_models.AuthoritativeExecutionContract
    integration_contract: integration.TerminalOutcomeIntegrationContract
    terminal_registry: authority.FreshTerminalRegistry
    raw_contract: authority.FreshRawExecutionDescriptorContract
    result_contract: authority.FreshJobResultDescriptorContract
    trace_contract: authority.FreshJobBoundAttemptTraceContract
    outcome_contract: authority.FreshOutcomeRowContract
    evaluator_contract: authority.FreshExactEvidenceSetEvaluatorContract
    prompt_contract: v192.JsonExplicitPromptContract
    prompt_schema: v192.JsonExplicitPromptSchema
    runtime: v188.PreparedExecution
    job_parents: dict[str, JobParents]


class CountingStageOneClient:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.config = client.config
        self.provider_call_count = 0
        self.telemetry: list[ModelCallTelemetry] = []
        self._lock = threading.Lock()

    def complete_json_certified(self, prompt: str, certificate: Any) -> Any:
        with self._lock:
            self.provider_call_count += 1
        try:
            payload, telemetry = self._client.complete_json_certified(prompt, certificate)
        except LLMClientError as exc:
            with self._lock:
                self.telemetry.extend(exc.telemetry)
            raise
        with self._lock:
            self.telemetry.append(telemetry)
        return payload, telemetry


@dataclass(frozen=True)
class TerminalObservation:
    terminal_kind: integration.ReachableTerminalKind
    component_index: int
    component_key: str
    public_payload: integration.DispatchControlPayload | None = None
    exception_type: integration.ObservedExceptionType | None = None
    exception_reason_sha256: str | None = None


def _recursive_file_geometry(root: Path) -> tuple[int, int]:
    files = tuple(path for path in root.rglob("*") if path.is_file())
    return len(files), sum(path.stat().st_size for path in files)


def _external_decision() -> models.ExternalOnlineExecutionDecision:
    return cast(
        models.ExternalOnlineExecutionDecision,
        models.make_identity(
            models.ExternalOnlineExecutionDecision,
            {
                "audit_sha256": EXTERNAL_AUDIT_SHA256,
                "audit_decision": "v26_199_accepted_exact_online_execution_only",
                "v199_report_id": V199_REPORT_ID,
                "v199_decision_id": V199_DECISION_ID,
                "v199_transition_id": V199_TRANSITION_ID,
            },
            field="decision_id",
            prefix="finance_v26_200_external_online_execution_decision:",
        ),
    )


def prepare_execution(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> PreparedOnlineExecution:
    repository_root = repository_root.resolve()
    package_root = (repository_root / "trusted_data_synthesis").resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"one-shot v26.200 output already exists: {output_dir}")
    audit_bytes = external_audit_path.read_bytes()
    if len(audit_bytes) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(audit_bytes) != (
        EXTERNAL_AUDIT_SHA256
    ):
        raise ValueError("v26.200 external online-execution audit bytes differ")
    external_decision = _external_decision()

    v199_root = package_root / v199.OUTPUT_DIR
    count, byte_count = _recursive_file_geometry(v199_root)
    if (count, byte_count) != (16, 102_783):
        raise ValueError("v26.199 exact formal directory geometry differs")
    report199 = _load(v199_root / "report.json")
    decision199 = _load(v199_root / "online_authorization_decision.json")
    transition199 = _load(v199_root / "prospective_transition.json")
    sealed199 = _load(v199_root / "sealed_evidence_manifest.json")
    distribution199 = _load(v199_root / "artifact_manifest.json")
    authorization = v199_models.ExactOnlineExecutionAuthorization.model_validate(
        _load(v199_root / "exact_online_execution_authorization.json")
    )
    if (
        report199.get("report_id") != V199_REPORT_ID
        or decision199.get("decision_id") != V199_DECISION_ID
        or transition199.get("transition_id") != V199_TRANSITION_ID
        or authorization.authorization_id != V199_AUTHORIZATION_ID
        or report199.get("source_commit") != V199_SOURCE_COMMIT
        or report199.get("source_tree") != V199_SOURCE_TREE
        or sealed199.get("artifact_root") != V199_SEALED_ROOT
        or distribution199.get("artifact_root") != V199_DISTRIBUTION_ROOT
        or transition199.get("next_stage") != models.CONSUMED_STAGE
    ):
        raise ValueError("v26.199 authorization authority differs")
    v199_freeze = cast(
        models.V199AuthorizationFreeze,
        models.make_identity(
            models.V199AuthorizationFreeze,
            {
                "external_decision_id": external_decision.decision_id,
                "v199_report_id": V199_REPORT_ID,
                "v199_decision_id": V199_DECISION_ID,
                "v199_transition_id": V199_TRANSITION_ID,
                "authorization_id": authorization.authorization_id,
                "source_commit": V199_SOURCE_COMMIT,
                "source_tree": V199_SOURCE_TREE,
                "sealed_artifact_root": V199_SEALED_ROOT,
                "distribution_artifact_root": V199_DISTRIBUTION_ROOT,
                "exact_job_set_sha256": authorization.exact_job_set_sha256,
            },
            field="freeze_id",
            prefix="finance_v26_200_v199_authorization_freeze:",
        ),
    )

    parents = v197._load_parents(repository_root)  # noqa: SLF001
    catalog, manifest, runner, execution = cast(tuple[Any, ...], parents[:4])
    terminal_registry, raw_contract, result_contract = cast(tuple[Any, ...], parents[4:7])
    trace_contract, outcome_contract, evaluator_contract = cast(tuple[Any, ...], parents[7:10])
    integration_root = repository_root / v199.V197_DIR
    integration_contract = integration.TerminalOutcomeIntegrationContract.model_validate(
        _load(integration_root / "terminal_to_outcome_integration_contract.json")
    )
    prompt_root = repository_root / v199.V192_DIR
    prompt_contract = v192.JsonExplicitPromptContract.model_validate(
        _load(prompt_root / "json_explicit_prompt_contract.json")
    )
    prompt_schema = v192.JsonExplicitPromptSchema.model_validate(
        _load(prompt_root / "json_explicit_prompt_schema.json")
    )
    json_manifest = v192.JsonExplicitDevelopmentManifest.model_validate(
        _load(prompt_root / "json_explicit_development_manifest.json")
    )
    generation_profile = _load(prompt_root / "json_explicit_generation_profile.json")
    runtime = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir,
    )
    kernel_jobs = {item.job_id: item for item in manifest.jobs}
    json_jobs = {item.job_id: item for item in json_manifest.jobs}
    runtime_jobs = {item.job_id: item for item in runtime.frozen.manifest.jobs}
    mappings: dict[str, JobParents] = {}
    for job_id in manifest.expected_job_ids:
        kernel_job = kernel_jobs[job_id]
        json_job = json_jobs[kernel_job.source_job_id]
        runtime_job = runtime_jobs[json_job.source_job_id]
        if (
            kernel_job.replica_index != json_job.replica_index
            or json_job.replica_index != runtime_job.replica_index
            or json_job.execution_package_id != runtime_job.execution_package_id
            or json_job.capability_family != runtime_job.capability_family.value
            or json_job.depth != runtime_job.depth.value
        ):
            raise ValueError("v26.194 -> v26.192 -> Runtime Job mapping differs")
        frozen_runtime.prepare_job(runtime_job, runtime.runtime_catalog)
        mappings[job_id] = JobParents(kernel_job, json_job, runtime_job)
    if (
        tuple(sorted(mappings)) != authorization.exact_job_ids
        or _set_sha256(tuple(sorted(mappings))) != authorization.exact_job_set_sha256
        or integration_contract.contract_id != authorization.integration_contract_id
        or catalog.catalog_id != authorization.package_catalog_id
        or manifest.manifest_id != authorization.manifest_id
        or runner.runner_id != authorization.runner_id
        or execution.contract_id != authorization.execution_contract_id
        or prompt_contract.contract_id != v199.PROMPT_CONTRACT_ID
        or prompt_schema.schema_id != v199.PROMPT_SCHEMA_ID
        or generation_profile.get("profile_id") != authorization.generation_profile_id
        or terminal_registry.registry_id != authorization.terminal_registry_id
        or raw_contract.contract_id != authorization.raw_descriptor_contract_id
        or result_contract.contract_id != authorization.result_descriptor_contract_id
        or trace_contract.contract_id != authorization.attempt_trace_contract_id
        or outcome_contract.contract_id != authorization.outcome_row_contract_id
        or evaluator_contract.contract_id != authorization.evaluator_contract_id
    ):
        raise ValueError("v26.200 exact execution parent chain differs")
    preparation = cast(
        models.ExactExecutionPreparation,
        models.make_identity(
            models.ExactExecutionPreparation,
            {
                "external_decision_id": external_decision.decision_id,
                "v199_freeze_id": v199_freeze.freeze_id,
                "authorization_id": authorization.authorization_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "integration_contract_id": integration_contract.contract_id,
                "terminal_registry_id": terminal_registry.registry_id,
                "raw_contract_id": raw_contract.contract_id,
                "result_contract_id": result_contract.contract_id,
                "trace_contract_id": trace_contract.contract_id,
                "outcome_contract_id": outcome_contract.contract_id,
                "evaluator_contract_id": evaluator_contract.contract_id,
                "prompt_contract_id": prompt_contract.contract_id,
                "prompt_schema_id": prompt_schema.schema_id,
                "generation_profile_id": authorization.generation_profile_id,
                "model_config_id": authorization.model_config_id,
                "thinking_policy_id": authorization.thinking_policy_id,
                "exact_job_ids": authorization.exact_job_ids,
                "exact_job_set_sha256": authorization.exact_job_set_sha256,
            },
            field="preparation_id",
            prefix="finance_v26_200_exact_execution_preparation:",
        ),
    )
    return PreparedOnlineExecution(
        repository_root=repository_root,
        package_root=package_root,
        output_dir=output_dir,
        external_audit_path=external_audit_path.resolve(),
        external_audit_bytes=audit_bytes,
        external_decision=external_decision,
        v199_freeze=v199_freeze,
        authorization=authorization,
        preparation=preparation,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        integration_contract=integration_contract,
        terminal_registry=terminal_registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
        prompt_contract=prompt_contract,
        prompt_schema=prompt_schema,
        runtime=runtime,
        job_parents=mappings,
    )


def _attempt(values: dict[str, Any]) -> ComponentAttemptOutcome:
    return cast(
        ComponentAttemptOutcome,
        models.make_identity(
            ComponentAttemptOutcome,
            values,
            field="attempt_id",
            prefix="capability_component_attempt_outcome:",
        ),
    )


def _control(values: dict[str, Any]) -> integration.DispatchControlPayload:
    return cast(
        integration.DispatchControlPayload,
        authority.make_identity_model(
            integration.DispatchControlPayload,
            values,
            field="payload_id",
            prefix="terminal_dispatch_control_payload:",
        ),
    )


def _exception_terminal(exc: Exception) -> tuple[integration.ObservedExceptionType, str]:
    text = f"{type(exc).__name__}:{exc}".casefold()
    reason = _sha256_bytes(text.encode("utf-8"))
    if "privacy response rejected" in text:
        return "PrivacyProjectionRejected", reason
    if "reasoning" in text or "thinking" in text:
        return "ThinkingIntegrityError", reason
    if "usage" in text or "total_tokens" in text:
        return "UsageIntegrityError", reason
    if "model" in text and ("identity" in text or "mismatch" in text):
        return "ProviderIdentityIntegrityError", reason
    if "resource" in text or "budget" in text or "prompt" in text and "limit" in text:
        return "ResourceBudgetError", reason
    if isinstance(exc, LLMClientError):
        telemetry = exc.telemetry
        error_types = " ".join((item.error_type or "") for item in telemetry).casefold()
        if any((item.http_status or 0) >= 200 for item in telemetry):
            return "ProviderNoPayloadError", reason
        if any(
            token in error_types
            for token in (
                "urlerror",
                "httperror",
                "timeout",
                "connection",
                "incompleteread",
                "remotedisconnected",
            )
        ):
            return "ProviderTransportError", reason
        return "ProviderNoPayloadError", reason
    return "InstrumentIntegrityError", reason


def _public_observation(
    *,
    terminal_kind: integration.ReachableTerminalKind,
    component_index: int,
    component_key: str,
    source_outcome: JobBoundOutcomePayload | None,
) -> TerminalObservation:
    if terminal_kind == "first_response_abi_invalid":
        payload = _control({"phase": "primary_action", "response_abi_valid": False})
    elif terminal_kind == "first_action_reference_invalid":
        payload = _control(
            {
                "phase": "primary_action",
                "response_abi_valid": True,
                "action_reference_valid": False,
            }
        )
    elif terminal_kind in {
        "correction_response_abi_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
    }:
        values: dict[str, Any] = {
            "phase": "correction_action",
            "response_abi_valid": True,
            "action_reference_valid": True,
            "state_precondition_valid": False,
            "action_accepted": False,
            "correction_invoked": True,
            "correction_response_abi_valid": terminal_kind != "correction_response_abi_invalid",
        }
        if terminal_kind != "correction_response_abi_invalid":
            values["correction_action_reference_valid"] = (
                terminal_kind != "correction_action_reference_invalid"
            )
        if terminal_kind == "correction_attempt_typed_invalid":
            values["correction_state_precondition_valid"] = False
            values["correction_accepted"] = False
        payload = _control(values)
    elif terminal_kind == "final_response_abi_invalid":
        payload = _control(
            {
                "phase": "final",
                "task_completion": True,
                "final_response_abi_valid": False,
            }
        )
    elif terminal_kind in {"completed_qualified", "completed_invalid"}:
        if source_outcome is None:
            raise ValueError("completed terminal lacks frozen Runtime outcome")
        payload = _control(
            {
                "phase": "final",
                "task_completion": True,
                "task_verifier_invoked": True,
                "final_response_abi_valid": True,
                "final_result_id": source_outcome.final_result_id,
                "final_base_valid": source_outcome.final_base_valid,
                "final_mechanism_qualified": source_outcome.final_mechanism_qualified,
                "final_qualified_valid": source_outcome.final_qualified_valid,
            }
        )
    else:
        raise ValueError("outer terminal cannot be represented as public payload")
    return TerminalObservation(terminal_kind, component_index, component_key, payload)


def _source_outcome(
    attempts: list[ComponentAttemptOutcome],
    *,
    result: StepRuntimeResult | None,
    final_abi_valid: bool | None,
) -> JobBoundOutcomePayload:
    return v188._source_outcome(  # noqa: SLF001
        attempts=tuple(attempts),
        result=result,
        final_abi_valid=final_abi_valid,
    )


def _invoke(
    execution_kernel: kernel.AuthoritativeJsonExplicitExecutionKernel,
    *,
    job_id: str,
    request_index: int,
    prompt_kind: Literal["action", "correction", "final"],
    core: dict[str, Any] | str,
) -> dict[str, Any]:
    return execution_kernel.invoke(
        job_id=job_id,
        logical_request_index=request_index,
        prompt_kind=prompt_kind,
        public_attempt_phase=("semantic_recovery" if prompt_kind == "correction" else "primary"),
        core=core,
    )


def _execute_runtime(
    *,
    prepared: PreparedOnlineExecution,
    parents: JobParents,
    execution_kernel: kernel.AuthoritativeJsonExplicitExecutionKernel,
) -> tuple[
    TerminalObservation,
    tuple[ComponentAttemptOutcome, ...],
    JobBoundOutcomePayload | None,
    str | None,
]:
    context = frozen_runtime.prepare_job(parents.runtime_job, prepared.runtime.runtime_catalog)
    state = frozen_runtime._initialize(context)  # noqa: SLF001
    attempts: list[ComponentAttemptOutcome] = []
    request_index = 0
    result: StepRuntimeResult | None = None
    source_outcome: JobBoundOutcomePayload | None = None
    terminal: TerminalObservation | None = None
    error: str | None = None
    try:
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            component = state.ordered_components[component_index]
            prompt = step_runtime.render_next_prompt(state)
            rows = frozen_runtime._candidate_dispositions(state, prompt)  # noqa: SLF001
            response = _invoke(
                execution_kernel,
                job_id=parents.kernel_job.job_id,
                request_index=request_index,
                prompt_kind="action",
                core=v192._action_core(prompt, prepared.runtime),  # noqa: SLF001
            )
            request_index += 1
            try:
                proposal = parse_exact_canonical_action_payload(response)
            except SemanticActionResponseRejection:
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": False,
                            "first_action_acceptance_evaluable": False,
                            "first_action_accepted": False,
                            "correction_invoked": False,
                            "committed": False,
                            "terminal": True,
                        }
                    )
                )
                source_outcome = _source_outcome(attempts, result=None, final_abi_valid=None)
                terminal = _public_observation(
                    terminal_kind="first_response_abi_invalid",
                    component_index=component_index,
                    component_key=component.component_key,
                    source_outcome=source_outcome,
                )
                break
            first_row = next((row for row in rows if row.action_id == proposal.action_id), None)
            if (
                proposal.state_id != prompt.state.state_token
                or proposal.decision_kind != prepared.runtime.profile.action_response_decision_kind
                or first_row is None
            ):
                terminal = _public_observation(
                    terminal_kind="first_action_reference_invalid",
                    component_index=component_index,
                    component_key=component.component_key,
                    source_outcome=None,
                )
                break
            first_output = step_runtime.step(state, proposal.action_id)
            if isinstance(first_output, HardenedPublicObservation):
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": True,
                            "first_action_acceptance_evaluable": True,
                            "first_action_id": proposal.action_id,
                            "first_action_state_precondition_valid": (
                                first_row.acceptance.state_precondition_valid
                            ),
                            "first_action_accepted": True,
                            "first_observation_receipt_id": first_output.receipt_id,
                            "correction_invoked": False,
                            "committed": True,
                            "terminal": False,
                        }
                    )
                )
                continue
            feedback = state.public_feedback_by_component[component.component_key][0]
            correction_prompt = step_runtime.render_next_prompt(state)
            correction_rows = frozen_runtime._candidate_dispositions(  # noqa: SLF001
                state, correction_prompt
            )
            correction_response = _invoke(
                execution_kernel,
                job_id=parents.kernel_job.job_id,
                request_index=request_index,
                prompt_kind="correction",
                core=v192._action_core(correction_prompt, prepared.runtime),  # noqa: SLF001
            )
            request_index += 1
            try:
                corrected = parse_exact_canonical_action_payload(correction_response)
            except SemanticActionResponseRejection:
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": True,
                            "first_action_acceptance_evaluable": True,
                            "first_action_id": proposal.action_id,
                            "first_action_state_precondition_valid": False,
                            "first_action_accepted": False,
                            "first_rejection_code": first_row.acceptance.rejection_code,
                            "first_observation_receipt_id": (
                                first_output.public_observation_receipt_id
                            ),
                            "correction_invoked": True,
                            "correction_feedback_id": feedback.feedback_id,
                            "correction_response_abi_valid": False,
                            "corrected_action_acceptance_evaluable": False,
                            "corrected_action_accepted": False,
                            "correction_terminal_reason": ("correction_response_abi_invalid"),
                            "committed": False,
                            "terminal": True,
                        }
                    )
                )
                source_outcome = _source_outcome(attempts, result=None, final_abi_valid=None)
                terminal = _public_observation(
                    terminal_kind="correction_response_abi_invalid",
                    component_index=component_index,
                    component_key=component.component_key,
                    source_outcome=source_outcome,
                )
                break
            correction_row = next(
                (row for row in correction_rows if row.action_id == corrected.action_id), None
            )
            if (
                corrected.state_id != correction_prompt.state.state_token
                or corrected.decision_kind != prepared.runtime.profile.action_response_decision_kind
                or correction_row is None
            ):
                relation = (
                    "stale_action"
                    if corrected.state_id != correction_prompt.state.state_token
                    else "foreign_or_unbound_action"
                )
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": True,
                            "first_action_acceptance_evaluable": True,
                            "first_action_id": proposal.action_id,
                            "first_action_state_precondition_valid": False,
                            "first_action_accepted": False,
                            "first_rejection_code": first_row.acceptance.rejection_code,
                            "first_observation_receipt_id": (
                                first_output.public_observation_receipt_id
                            ),
                            "correction_invoked": True,
                            "correction_feedback_id": feedback.feedback_id,
                            "correction_response_abi_valid": True,
                            "corrected_action_id": corrected.action_id,
                            "corrected_action_relation": relation,
                            "corrected_action_acceptance_evaluable": False,
                            "corrected_action_accepted": False,
                            "correction_terminal_reason": ("correction_action_reference_invalid"),
                            "committed": False,
                            "terminal": True,
                        }
                    )
                )
                source_outcome = _source_outcome(attempts, result=None, final_abi_valid=None)
                terminal = _public_observation(
                    terminal_kind="correction_action_reference_invalid",
                    component_index=component_index,
                    component_key=component.component_key,
                    source_outcome=source_outcome,
                )
                break
            corrected_output = step_runtime.step(state, corrected.action_id)
            if isinstance(corrected_output, HardenedPublicObservation):
                relation = (
                    "reference"
                    if correction_row.source_choice_handle == component.reference_choice_handle
                    else "valid_nonreference"
                )
                attempts.append(
                    _attempt(
                        {
                            "component_index": component_index,
                            "component_key": component.component_key,
                            "reached_state_token": prompt.state.state_token,
                            "first_response_abi_valid": True,
                            "first_action_acceptance_evaluable": True,
                            "first_action_id": proposal.action_id,
                            "first_action_state_precondition_valid": False,
                            "first_action_accepted": False,
                            "first_rejection_code": first_row.acceptance.rejection_code,
                            "first_observation_receipt_id": (
                                first_output.public_observation_receipt_id
                            ),
                            "correction_invoked": True,
                            "correction_feedback_id": feedback.feedback_id,
                            "correction_response_abi_valid": True,
                            "corrected_action_id": corrected.action_id,
                            "corrected_action_relation": relation,
                            "corrected_action_acceptance_evaluable": True,
                            "corrected_action_accepted": True,
                            "correction_observation_receipt_id": corrected_output.receipt_id,
                            "committed": True,
                            "terminal": False,
                        }
                    )
                )
                continue
            relation_map = {
                "same_current_invalid": "same_current_invalid",
                "different_current_invalid": "different_current_invalid",
                "stale_action_id": "stale_action",
                "foreign_or_unbound_action_id": "foreign_or_unbound_action",
                "malformed_action_reference": "foreign_or_unbound_action",
            }
            relation = relation_map[corrected_output.second_response_class]
            typed = relation in {"same_current_invalid", "different_current_invalid"}
            correction_receipt = None
            if typed:
                correction_receipt = state.public_rejection_observations_by_component[
                    component.component_key
                ][-1].public_observation_receipt_id
            terminal_kind = cast(
                integration.ReachableTerminalKind, corrected_output.terminal_reason
            )
            attempts.append(
                _attempt(
                    {
                        "component_index": component_index,
                        "component_key": component.component_key,
                        "reached_state_token": prompt.state.state_token,
                        "first_response_abi_valid": True,
                        "first_action_acceptance_evaluable": True,
                        "first_action_id": proposal.action_id,
                        "first_action_state_precondition_valid": False,
                        "first_action_accepted": False,
                        "first_rejection_code": first_row.acceptance.rejection_code,
                        "first_observation_receipt_id": (
                            first_output.public_observation_receipt_id
                        ),
                        "correction_invoked": True,
                        "correction_feedback_id": feedback.feedback_id,
                        "correction_response_abi_valid": True,
                        "corrected_action_id": corrected.action_id,
                        "corrected_action_relation": relation,
                        "corrected_action_acceptance_evaluable": typed,
                        "corrected_action_accepted": False,
                        "correction_observation_receipt_id": correction_receipt,
                        "correction_terminal_reason": corrected_output.terminal_reason,
                        "committed": False,
                        "terminal": True,
                    }
                )
            )
            source_outcome = _source_outcome(attempts, result=None, final_abi_valid=None)
            terminal = _public_observation(
                terminal_kind=terminal_kind,
                component_index=component_index,
                component_key=component.component_key,
                source_outcome=source_outcome,
            )
            break
        if terminal is None:
            result = step_runtime.finalize(state)
            final_prompt, envelope = v188.render_final_prompt(
                context=context,
                result=result,
                grammar=prepared.runtime.final_grammar,
            )
            final_response = _invoke(
                execution_kernel,
                job_id=parents.kernel_job.job_id,
                request_index=request_index,
                prompt_kind="final",
                core=final_prompt,
            )
            try:
                parse_qualified_final_response(
                    final_response,
                    grammar=prepared.runtime.final_grammar,
                    envelope=envelope,
                )
            except Exception:
                source_outcome = _source_outcome(attempts, result=result, final_abi_valid=False)
                last = state.ordered_components[-1]
                terminal = _public_observation(
                    terminal_kind="final_response_abi_invalid",
                    component_index=len(state.ordered_components) - 1,
                    component_key=last.component_key,
                    source_outcome=source_outcome,
                )
            else:
                source_outcome = _source_outcome(attempts, result=result, final_abi_valid=True)
                terminal_kind = cast(
                    integration.ReachableTerminalKind, source_outcome.endpoint_kind
                )
                last = state.ordered_components[-1]
                terminal = _public_observation(
                    terminal_kind=terminal_kind,
                    component_index=len(state.ordered_components) - 1,
                    component_key=last.component_key,
                    source_outcome=source_outcome,
                )
    except Exception as exc:
        exception_type, reason = _exception_terminal(exc)
        index = min(state.current_index, len(state.ordered_components) - 1)
        component = state.ordered_components[index]
        mapping: dict[integration.ObservedExceptionType, integration.ReachableTerminalKind] = {
            "ProviderNoPayloadError": "provider_failure_no_payload",
            "ProviderTransportError": "provider_transport_failure",
            "PrivacyProjectionRejected": "privacy_rejection",
            "ResourceBudgetError": "resource_budget_exhausted",
            "InstrumentIntegrityError": "instrument_failure",
            "ProviderIdentityIntegrityError": "provider_identity_failure",
            "ThinkingIntegrityError": "thinking_integrity_failure",
            "UsageIntegrityError": "usage_integrity_failure",
        }
        terminal = TerminalObservation(
            mapping[exception_type],
            index,
            component.component_key,
            exception_type=exception_type,
            exception_reason_sha256=reason,
        )
        error = f"{type(exc).__name__}:{reason}"
    if terminal is None:
        raise RuntimeError("v26.200 Job did not produce one terminal observation")
    return terminal, tuple(attempts), source_outcome, error


def _provider_artifact_ids(root: Path, job_id: str) -> tuple[str, ...]:
    safe = _safe(job_id)
    paths = tuple(
        sorted(
            (
                *(root / "envelopes" / safe).glob("*.json"),
                *(root / "projections" / safe).glob("*.json"),
            ),
            key=lambda item: item.as_posix(),
        )
    )
    return tuple(f"sha256:{_sha256(path)}" for path in paths)


def _build_record(
    *,
    prepared: PreparedOnlineExecution,
    parents: JobParents,
    run_start: models.RunStartReceipt,
    admission: v199_models.OnlineAuthorizationAdmission,
    terminal: TerminalObservation,
    attempts: tuple[ComponentAttemptOutcome, ...],
    source_outcome: JobBoundOutcomePayload | None,
    execution_kernel: kernel.AuthoritativeJsonExplicitExecutionKernel,
    counting_client: CountingStageOneClient,
    error: str | None,
) -> models.OnlineJobExecutionRecord:
    receipts = execution_kernel.receipts
    dispatch_values: dict[str, Any] = {
        "integration_contract_id": prepared.integration_contract.contract_id,
        "authorization_admission_id": admission.admission_id,
        "job_id": parents.kernel_job.job_id,
        "component_index": terminal.component_index,
        "component_key": terminal.component_key,
        "invocation_receipt_ids": tuple(item.receipt_id for item in receipts[-1:]),
        "public_payload": terminal.public_payload,
        "public_payload_sha256": (
            _sha256_bytes(integration._canonical_bytes(terminal.public_payload))  # noqa: SLF001
            if terminal.public_payload is not None
            else None
        ),
        "exception_type": terminal.exception_type,
        "exception_reason_sha256": terminal.exception_reason_sha256,
    }
    dispatcher_evidence = cast(
        integration.TerminalExecutionEvidence,
        authority.make_identity_model(
            integration.TerminalExecutionEvidence,
            dispatch_values,
            field="evidence_id",
            prefix="production_terminal_execution_evidence:",
        ),
    )
    dispatcher = integration.AuthoritativeTerminalDispatcher(
        integration_contract=prepared.integration_contract,
        terminal_registry=prepared.terminal_registry,
    )
    decision = dispatcher.dispatch(dispatcher_evidence)
    if decision.terminal_kind != terminal.terminal_kind:
        raise ValueError("actual Runtime and exact v26.197 dispatcher terminals differ")
    token_usage = sum(item.total_tokens or 0 for item in counting_client.telemetry)
    empirical_evidence = cast(
        models.EmpiricalTerminalExecutionEvidence,
        models.make_identity(
            models.EmpiricalTerminalExecutionEvidence,
            {
                "dispatcher_evidence_id": dispatcher_evidence.evidence_id,
                "integration_contract_id": prepared.integration_contract.contract_id,
                "online_admission_id": admission.admission_id,
                "job_id": parents.kernel_job.job_id,
                "component_index": terminal.component_index,
                "component_key": terminal.component_key,
                "invocation_receipt_ids": tuple(item.receipt_id for item in receipts),
                "public_terminal_projection": terminal.public_payload,
                "exception_type": terminal.exception_type,
                "exception_reason_sha256": terminal.exception_reason_sha256,
                "provider_call_count": counting_client.provider_call_count,
                "cumulative_tokens": token_usage,
            },
            field="evidence_id",
            prefix="empirical_terminal_execution_evidence:",
        ),
    )
    kernel_root = prepared.output_dir / "kernel_artifacts"
    provider_artifacts = _provider_artifact_ids(kernel_root, parents.kernel_job.job_id)
    raw_payload = cast(
        models.EmpiricalIntegratedRawPayload,
        models.make_identity(
            models.EmpiricalIntegratedRawPayload,
            {
                "job_id": parents.kernel_job.job_id,
                "execution_contract_id": prepared.execution.contract_id,
                "terminal_registry_id": prepared.terminal_registry.registry_id,
                "integration_contract_id": prepared.integration_contract.contract_id,
                "online_authorization_id": prepared.authorization.authorization_id,
                "online_admission_id": admission.admission_id,
                "terminal_kind": decision.terminal_kind,
                "component_attempts": attempts,
                "source_outcome": source_outcome,
                "terminal_evidence": empirical_evidence,
                "terminal_decision": decision,
                "provider_artifact_ids": provider_artifacts,
                "model_response_present": any(
                    item.http_success for item in counting_client.telemetry
                ),
                "token_usage": token_usage,
                "provider_calls": counting_client.provider_call_count,
                "execution_error": error,
                "provider_telemetry": tuple(
                    item.model_dump(mode="json") for item in counting_client.telemetry
                ),
            },
            field="payload_id",
            prefix="fresh_kernel_raw_execution_payload:",
        ),
    )
    fresh_root = prepared.output_dir / "fresh_outcome_artifacts"
    writer = v195_writer.FreshOutcomeArtifactWriter(fresh_root)
    raw_sha, raw_bytes = writer.write_raw(
        job_id=parents.kernel_job.job_id,
        payload=raw_payload,  # type: ignore[arg-type]
    )
    raw_path = authority.expected_raw_artifact_filename_from_id(parents.kernel_job.job_id)
    raw_descriptor = cast(
        authority.FreshRawExecutionDescriptor,
        authority.make_identity_model(
            authority.FreshRawExecutionDescriptor,
            {
                "descriptor_contract_id": prepared.raw_contract.contract_id,
                "evidence_kind": "empirical_execution",
                "job_id": parents.kernel_job.job_id,
                "manifest_id": prepared.manifest.manifest_id,
                "runner_id": prepared.runner.runner_id,
                "execution_contract_id": prepared.execution.contract_id,
                "package_id": parents.kernel_job.package_id,
                "replica_index": parents.kernel_job.replica_index,
                "raw_namespace": parents.kernel_job.raw_namespace,
                "artifact_relative_path": raw_path,
                "artifact_sha256": raw_sha,
                "artifact_byte_count": raw_bytes,
                "payload_id": raw_payload.payload_id,
            },
            field="raw_execution_id",
            prefix="fresh_kernel_raw_execution_descriptor:",
        ),
    )
    validity = integration._terminal_validity(dispatcher_evidence, decision)  # noqa: SLF001
    result_payload = cast(
        authority.FreshJobResultPayload,
        authority.make_identity_model(
            authority.FreshJobResultPayload,
            {
                "evidence_kind": "empirical_execution",
                "job_id": parents.kernel_job.job_id,
                "raw_execution_id": raw_descriptor.raw_execution_id,
                "execution_contract_id": prepared.execution.contract_id,
                "terminal_registry_id": prepared.terminal_registry.registry_id,
                "terminal_kind": decision.terminal_kind,
                "validity": validity,
            },
            field="payload_id",
            prefix="fresh_kernel_job_result_payload:",
        ),
    )
    result_sha, result_bytes = writer.write_result(
        job_id=parents.kernel_job.job_id,
        payload=result_payload,
    )
    writer.assert_closed()
    result_path = authority.expected_result_artifact_filename_from_id(parents.kernel_job.job_id)
    result_descriptor = cast(
        authority.FreshJobResultDescriptor,
        authority.make_identity_model(
            authority.FreshJobResultDescriptor,
            {
                "descriptor_contract_id": prepared.result_contract.contract_id,
                "evidence_kind": "empirical_execution",
                "job_id": parents.kernel_job.job_id,
                "raw_execution_id": raw_descriptor.raw_execution_id,
                "execution_contract_id": prepared.execution.contract_id,
                "result_namespace": parents.kernel_job.result_namespace,
                "artifact_relative_path": result_path,
                "artifact_sha256": result_sha,
                "artifact_byte_count": result_bytes,
                "payload_id": result_payload.payload_id,
            },
            field="result_id",
            prefix="fresh_kernel_job_result_descriptor:",
        ),
    )
    loci = integration._failure_loci(  # noqa: SLF001
        decision=decision,
        evidence=dispatcher_evidence,
        source_descriptor_id=result_descriptor.result_id,
    )
    trace = cast(
        models.EmpiricalIntegratedAttemptTrace,
        models.make_identity(
            models.EmpiricalIntegratedAttemptTrace,
            {
                "trace_contract_id": prepared.trace_contract.contract_id,
                "integration_contract_id": prepared.integration_contract.contract_id,
                "online_admission_id": admission.admission_id,
                "job_id": parents.kernel_job.job_id,
                "raw_execution_id": raw_descriptor.raw_execution_id,
                "result_id": result_descriptor.result_id,
                "terminal_kind": decision.terminal_kind,
                "terminal_evidence_id": empirical_evidence.evidence_id,
                "terminal_decision_id": decision.decision_id,
                "component_attempts": attempts,
                "failure_loci": loci,
                "correction_count": sum(int(item.correction_invoked) for item in attempts),
                "provider_call_count": counting_client.provider_call_count,
            },
            field="trace_id",
            prefix="fresh_kernel_job_bound_attempt_trace:",
        ),
    )
    row = cast(
        authority.FreshOutcomeRow,
        authority.make_identity_model(
            authority.FreshOutcomeRow,
            {
                "outcome_contract_id": prepared.outcome_contract.contract_id,
                "evidence_kind": "empirical_execution",
                "job_id": parents.kernel_job.job_id,
                "manifest_id": prepared.manifest.manifest_id,
                "runner_id": prepared.runner.runner_id,
                "execution_contract_id": prepared.execution.contract_id,
                "package_id": parents.kernel_job.package_id,
                "replica_index": parents.kernel_job.replica_index,
                "raw_execution_id": raw_descriptor.raw_execution_id,
                "result_id": result_descriptor.result_id,
                "trace_id": trace.trace_id,
                "terminal_registry_id": prepared.terminal_registry.registry_id,
                "terminal_kind": decision.terminal_kind,
                "correction_count": trace.correction_count,
                "task_completion": validity.task_completion,
                "task_verifier_invoked": validity.task_verifier_invoked,
                "final_result_id": validity.final_result_id,
                "final_base_valid": validity.final_base_valid,
                "final_mechanism_qualified": validity.final_mechanism_qualified,
                "final_qualified_valid": validity.final_qualified_valid,
                "failure_locus_ids": tuple(item.locus_id for item in loci),
                "formal_empirical_row": True,
            },
            field="row_id",
            prefix="fresh_kernel_outcome_row:",
        ),
    )
    bundle = models.empirical_bundle(
        raw=raw_descriptor,
        result=result_descriptor,
        trace=trace,
        row=row,
    )
    return cast(
        models.OnlineJobExecutionRecord,
        models.make_identity(
            models.OnlineJobExecutionRecord,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "authorization_id": prepared.authorization.authorization_id,
                "job_id": parents.kernel_job.job_id,
                "source_json_job_id": parents.json_job.job_id,
                "source_runtime_job_id": parents.runtime_job.job_id,
                "package_id": parents.kernel_job.package_id,
                "replica_index": parents.kernel_job.replica_index,
                "capability_family": parents.json_job.capability_family,
                "observation_depth": parents.json_job.depth,
                "terminal_kind": decision.terminal_kind,
                "bundle": bundle,
                "kernel_invocation_receipt_ids": tuple(item.receipt_id for item in receipts),
                "provider_call_count": counting_client.provider_call_count,
                "cumulative_tokens": token_usage,
                "execution_error": error,
            },
            field="record_id",
            prefix="finance_v26_200_online_job_execution_record:",
        ),
    )


def execute_job(
    *,
    prepared: PreparedOnlineExecution,
    parents: JobParents,
    run_start: models.RunStartReceipt,
    admission: v199_models.OnlineAuthorizationAdmission,
    config: AgentModelConfig,
    client_factory: Any = StageOneProspectiveThinkingJsonClient,
) -> models.OnlineJobExecutionRecord:
    counting = CountingStageOneClient(client_factory(config))
    certified = kernel.ProductionStageOneClientAdapter(counting)  # type: ignore[arg-type]
    kernel_writer = kernel.NoReplaceKernelJournalWriter(prepared.output_dir / "kernel_artifacts")
    execution_kernel = kernel.AuthoritativeJsonExplicitExecutionKernel(
        execution_contract_id=prepared.execution.contract_id,
        runner_id=prepared.runner.runner_id,
        manifest_id=prepared.manifest.manifest_id,
        prompt_contract=prepared.prompt_contract,
        prompt_schema=prepared.prompt_schema,
        client=certified,
        writer=kernel_writer,
    )
    terminal, attempts, source_outcome, error = _execute_runtime(
        prepared=prepared,
        parents=parents,
        execution_kernel=execution_kernel,
    )
    execution_kernel.assert_closed()
    return _build_record(
        prepared=prepared,
        parents=parents,
        run_start=run_start,
        admission=admission,
        terminal=terminal,
        attempts=attempts,
        source_outcome=source_outcome,
        execution_kernel=execution_kernel,
        counting_client=counting,
        error=error,
    )


def _git_identity(repository_root: Path) -> tuple[str, str]:
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if changed.strip():
        raise ValueError("v26.200 execution source tree has tracked changes")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


def _load_env_key(package_root: Path, key: str) -> None:
    if os.environ.get(key):
        return
    path = package_root.parent / ".env"
    if not path.is_file():
        path = package_root / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            os.environ[key] = value.strip().strip('"').strip("'")
            return
    raise ValueError(f"missing credential environment variable: {key}")


def _artifact_manifest(root: Path) -> models.ExecutionArtifactManifest:
    members = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "execution_artifact_manifest.json":
            continue
        members.append(
            models.ExecutionArtifactMember(
                relative_path=path.relative_to(root).as_posix(),
                sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    member_tuple = tuple(members)
    artifact_root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in member_tuple),
        prefix="finance_v26_200_execution_artifact_root:",
    )
    return cast(
        models.ExecutionArtifactManifest,
        models.make_identity(
            models.ExecutionArtifactManifest,
            {
                "run_id": RUN_ID,
                "members": member_tuple,
                "file_count": len(member_tuple),
                "total_byte_count": sum(item.byte_count for item in member_tuple),
                "artifact_root": artifact_root,
            },
            field="manifest_id",
            prefix="finance_v26_200_execution_artifact_manifest:",
        ),
    )


def execute(
    *,
    prepared: PreparedOnlineExecution,
    workers: int = MAX_WORKERS,
    client_factory: Any = StageOneProspectiveThinkingJsonClient,
) -> models.OnlineExecutionSummary:
    guard = v199_models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=prepared.authorization,
        expected_authorization_bytes=v199_models.canonical_bytes(prepared.authorization),
    )
    admission = guard.admit(**v199._request_arguments(prepared.authorization))  # noqa: SLF001
    source_commit, source_tree = _git_identity(prepared.repository_root)
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(
        prepared.output_dir / "external_v26_199_execution_audit.txt",
        prepared.external_audit_bytes,
    )
    _write_no_replace(
        prepared.output_dir / "external_execution_decision.json", prepared.external_decision
    )
    _write_no_replace(
        prepared.output_dir / "v26_199_authorization_freeze.json", prepared.v199_freeze
    )
    _write_no_replace(
        prepared.output_dir / "exact_execution_preparation.json", prepared.preparation
    )
    _write_no_replace(
        prepared.output_dir / "exact_online_execution_authorization.json", prepared.authorization
    )
    _write_no_replace(prepared.output_dir / "online_authorization_admission.json", admission)
    run_start = cast(
        models.RunStartReceipt,
        models.make_identity(
            models.RunStartReceipt,
            {
                "external_decision_id": prepared.external_decision.decision_id,
                "authorization_id": prepared.authorization.authorization_id,
                "admission_id": admission.admission_id,
                "manifest_id": prepared.manifest.manifest_id,
                "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
                "execution_source_commit": source_commit,
                "execution_source_tree": source_tree,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            field="receipt_id",
            prefix="finance_v26_200_online_run_start_receipt:",
        ),
    )
    _write_no_replace(prepared.output_dir / "run_start_receipt.json", run_start)

    profile_payload = _load(prepared.package_root / MODEL_PROFILE_PATH)
    config = require_stage_one_model_config(
        AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    _load_env_key(prepared.package_root, config.api_key_env)
    records: dict[str, models.OnlineJobExecutionRecord] = {}
    attempted: set[str] = set()
    fatal: str | None = None
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for job_id in prepared.authorization.exact_job_ids:
                attempted.add(job_id)
                future = pool.submit(
                    execute_job,
                    prepared=prepared,
                    parents=prepared.job_parents[job_id],
                    run_start=run_start,
                    admission=admission,
                    config=config,
                    client_factory=client_factory,
                )
                futures[future] = job_id
            for future in as_completed(futures):
                job_id = futures[future]
                try:
                    record = future.result()
                except (KeyboardInterrupt, SystemExit):
                    fatal = "operator_interruption"
                    continue
                except Exception as exc:
                    if fatal is None:
                        fatal = f"{type(exc).__name__}:{_sha256_bytes(str(exc).encode('utf-8'))}"
                    continue
                records[job_id] = record
                _write_no_replace(
                    prepared.output_dir / "job_records" / f"{_safe(job_id)}.json",
                    record,
                )
                ordinal = prepared.authorization.exact_job_ids.index(job_id)
                checkpoint = cast(
                    models.ExecutionCheckpoint,
                    models.make_identity(
                        models.ExecutionCheckpoint,
                        {
                            "run_start_receipt_id": run_start.receipt_id,
                            "ordinal": ordinal,
                            "job_id": job_id,
                            "record_id": record.record_id,
                            "terminal_kind": record.terminal_kind,
                            "raw_execution_id": record.bundle.raw.raw_execution_id,
                            "result_id": record.bundle.result.result_id,
                        },
                        field="checkpoint_id",
                        prefix="finance_v26_200_online_execution_checkpoint:",
                    ),
                )
                _write_no_replace(
                    prepared.output_dir / "checkpoints" / f"job_{ordinal:03d}.json",
                    checkpoint,
                )
    except (KeyboardInterrupt, SystemExit):
        fatal = "operator_interruption"
    except Exception as exc:
        fatal = f"{type(exc).__name__}:{_sha256_bytes(str(exc).encode('utf-8'))}"
    ordered_records = tuple(records[key] for key in sorted(records))
    status: Literal["completed", "failed", "interrupted"]
    if fatal == "operator_interruption":
        status = "interrupted"
    elif fatal is not None or len(ordered_records) != 192:
        status = "failed"
    else:
        status = "completed"
    summary = cast(
        models.OnlineExecutionSummary,
        models.make_identity(
            models.OnlineExecutionSummary,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "authorization_id": prepared.authorization.authorization_id,
                "manifest_id": prepared.manifest.manifest_id,
                "runner_id": prepared.runner.runner_id,
                "execution_contract_id": prepared.execution.contract_id,
                "integration_contract_id": prepared.integration_contract.contract_id,
                "execution_status": status,
                "attempted_job_count": len(attempted),
                "completed_job_record_count": len(ordered_records),
                "raw_count": len(ordered_records),
                "result_count": len(ordered_records),
                "outcome_count": len(ordered_records),
                "terminal_partition": dict(
                    sorted(Counter(item.terminal_kind for item in ordered_records).items())
                ),
                "provider_calls": sum(item.provider_call_count for item in ordered_records),
                "total_usage_tokens": sum(item.cumulative_tokens for item in ordered_records),
                "next_stage": models.NEXT_STAGE,
            },
            field="summary_id",
            prefix="finance_v26_200_online_execution_summary:",
        ),
    )
    _write_no_replace(prepared.output_dir / "execution_summary.json", summary)
    _write_no_replace(
        prepared.output_dir / "prospective_transition.json",
        {
            "consumed_stage": models.CONSUMED_STAGE,
            "execution_status": status,
            "fatal_error": fatal,
            "next_stage": models.NEXT_STAGE,
            "additional_provider_calls_authorized": False,
            "replacement_rerun_authorized": False,
            "recovery_execution_authorized": False,
            "empirical_estimation_authorized": False,
            "mapper_state_frequency_contribution_vtdo_authorized": False,
        },
    )
    artifact_manifest = _artifact_manifest(prepared.output_dir)
    _write_no_replace(prepared.output_dir / "execution_artifact_manifest.json", artifact_manifest)
    return summary


def _default_output(repository_root: Path) -> Path:
    return repository_root / "trusted_data_synthesis" / OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    output_dir = (args.output_dir or _default_output(repository_root)).resolve()
    prepared = prepare_execution(
        repository_root=repository_root,
        output_dir=output_dir,
        external_audit_path=args.external_audit,
    )
    if args.prepare_only:
        print(_canonical_json(prepared.preparation))
        return
    print(_canonical_json(execute(prepared=prepared, workers=args.workers)))


if __name__ == "__main__":
    main()
