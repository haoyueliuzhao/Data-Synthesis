# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from math import comb
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution as v200,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight as v203,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as v203_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_online_calibration_models as models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_grammar,
)
from trusted_synthesis.runtime.agent.client import (
    EmptyFinalContentError,
    LLMClientError,
    ReasoningBudgetExhaustedError,
    _estimate_cost,
    _optional_int,
    _strip_json_fence,
)
from trusted_synthesis.runtime.agent.prospective_thinking_client import (
    ProviderNativeToolCallError,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    RedactedProviderResponseEnvelope,
    RedactedProviderResponseFields,
    capture_redacted_provider_response_fields,
    require_admitted_response_envelope,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
    StageOneProspectiveThinkingJsonClient,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = (
    "finance_v26_204_fresh_first_response_action_interface_disambiguation_"
    "paired_24_call_online_calibration_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V203_DIR: Final = v203.OUTPUT_DIR
EXTERNAL_AUDIT_SHA256: Final = "58ddefdbe073456a6bd462b50f59f7b3a1083bb6797dbca806dbbb9ed39ce7e8"
EXTERNAL_AUDIT_BYTES: Final = 14_139
EXPECTED_V203_ARTIFACT_MANIFEST_ID: Final = (
    "finance_v26_203_artifact_manifest:"
    "d6a2c5a261758ac46343955d9f26206f8fb3e3565d5fd8aae4474c7707655c6a"
)
EXPECTED_V203_ARTIFACT_ROOT: Final = (
    "finance_v26_203_artifact_root:a9c21c4ed2a3276496ebb14c54d26dd3b3cb3700a93eee5aee630419564315b3"
)


class V204Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V204Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _safe(value: str) -> str:
    return value.replace(":", "__").replace("/", "_")


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _write_no_replace(path: Path, value: Any) -> None:
    _write_bytes_no_replace(path, models.canonical_bytes(value))


def _request_body(
    config: AgentModelConfig,
    messages: tuple[v203_models.RequestMessage, ...],
) -> dict[str, Any]:
    body = kernel.make_stage_one_request_body(config, messages[-1].content)
    body["messages"] = [{"role": item.role, "content": item.content} for item in messages]
    return body


class MessageAwareStageOneClient(StageOneProspectiveThinkingJsonClient):
    """Exact v26.203 system/user transport with one invocation and no retry."""

    def complete_messages(
        self,
        request_descriptor: v203_models.FirstRequestDescriptor,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        body = _request_body(self.config, request_descriptor.messages)
        if models.canonical_sha256(body) != request_descriptor.canonical_request_body_sha256:
            raise LLMClientError("v26.204 actual request body differs from v26.203")
        body_bytes = models.canonical_bytes(body)
        request_hash = hashlib.sha256(body_bytes).hexdigest()
        request = urllib.request.Request(
            self.config.endpoint,
            data=body_bytes,
            headers=self._headers(json_content=True),
            method="POST",
        )
        started = time.perf_counter()
        status: int | None = None
        envelope: RedactedProviderResponseEnvelope | None = None
        redacted_fields: RedactedProviderResponseFields | None = None
        prompt_tokens: int | None = None
        cache_hit: int | None = None
        cache_miss: int | None = None
        total_tokens: int | None = None
        estimated_cost: float | None = None
        cost_method: str | None = None
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                status = int(getattr(response, "status", 200))
                response_body = json.loads(response.read().decode("utf-8"))
            if not isinstance(response_body, Mapping):
                raise TypeError("HTTP-success response body must be a JSON object")
            redacted_fields = capture_redacted_provider_response_fields(response_body)
            envelope = RedactedProviderResponseEnvelope.model_validate(redacted_fields)
            usage = response_body.get("usage")
            if not isinstance(usage, Mapping):
                raise ValueError("HTTP-success response lacks Usage")
            prompt_tokens = _optional_int(usage.get("prompt_tokens", usage.get("input_tokens")))
            cache_hit = _optional_int(usage.get("prompt_cache_hit_tokens"))
            cache_miss = _optional_int(usage.get("prompt_cache_miss_tokens"))
            total_tokens = _optional_int(usage.get("total_tokens"))
            if total_tokens is None and prompt_tokens is not None and envelope.completion_tokens:
                total_tokens = prompt_tokens + envelope.completion_tokens
            estimated_cost, cost_method = _estimate_cost(
                self.config,
                prompt_tokens,
                envelope.completion_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
            )
            if envelope.provider_native_tool_call_observed:
                raise ProviderNativeToolCallError(
                    "Provider-native tool calls are forbidden by the Host protocol"
                )
            require_admitted_response_envelope(envelope, expected_model=STAGE_ONE_MODEL_ID)
            message = response_body["choices"][0]["message"]
            raw_content = message.get("content")
            content = "" if raw_content is None else str(raw_content)
            if not content.strip():
                if envelope.finish_reason == "length" and envelope.reasoning_content_present:
                    raise ReasoningBudgetExhaustedError(
                        "model exhausted the Stage 1 output budget in reasoning"
                    )
                raise EmptyFinalContentError("model returned an empty Stage 1 content field")
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise TypeError("Stage 1 response must be a JSON object")
            return parsed, self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=True,
            )
        except Exception as exc:
            if isinstance(exc, urllib.error.HTTPError):
                status = int(exc.code)
            telemetry = self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted_fields,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=False,
                error=exc,
            )
            raise LLMClientError(str(exc), (telemetry,)) from exc


class PreparedOnlineCalibration:
    def __init__(
        self,
        *,
        repository_root: Path,
        package_root: Path,
        output_dir: Path,
        external_audit_bytes: bytes,
        authorization: models.ExternalOnlineAuthorization,
        freeze: models.V203Freeze,
        preparation: models.OnlineExecutionPreparation,
        manifest: v203_models.CalibrationManifest,
        population: v203_models.StratifiedCalibrationPopulation,
        action_contract: v203_models.ExactActionInterfaceContract,
        gate_contract: v203_models.OnlineGateContract,
        config: AgentModelConfig,
    ) -> None:
        self.repository_root = repository_root
        self.package_root = package_root
        self.output_dir = output_dir
        self.external_audit_bytes = external_audit_bytes
        self.authorization = authorization
        self.freeze = freeze
        self.preparation = preparation
        self.manifest = manifest
        self.population = population
        self.action_contract = action_contract
        self.gate_contract = gate_contract
        self.config = config


def _revalidate_v203(root: Path) -> v203_models.ArtifactManifest:
    artifact = v203_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    if (
        artifact.manifest_id != EXPECTED_V203_ARTIFACT_MANIFEST_ID
        or artifact.artifact_root != EXPECTED_V203_ARTIFACT_ROOT
        or artifact.file_count != 14
    ):
        _fail("v203.manifest", "v26.203 Artifact Manifest or Root differs")
    for member in artifact.members:
        path = root / member.relative_path
        if (
            not path.is_file()
            or _sha256(path) != member.sha256
            or path.stat().st_size != member.byte_count
        ):
            _fail("v203.member", f"v26.203 formal member differs:{member.relative_path}")
    paths = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    if len(paths) != 15 or sum(path.stat().st_size for path in paths) != 582_364:
        _fail("v203.directory", "v26.203 formal directory geometry differs")
    return artifact


def _execution_order(
    manifest: v203_models.CalibrationManifest,
    population: v203_models.StratifiedCalibrationPopulation,
) -> tuple[models.ExecutionOrderEntry, ...]:
    jobs_by_cell: dict[str, list[v203_models.CalibrationJob]] = {}
    for job in manifest.jobs:
        jobs_by_cell.setdefault(job.source_cell_id, []).append(job)
    requests = {item.job_id: item for item in manifest.requests}
    entries: list[models.ExecutionOrderEntry] = []
    for cell_ordinal, cell in enumerate(population.cells):
        rows = sorted(
            jobs_by_cell.get(cell.source_cell_id, []),
            key=lambda item: item.execution_order_within_pair,
        )
        if len(rows) != 2 or tuple(item.execution_order_within_pair for item in rows) != (0, 1):
            _fail("manifest.order", "v26.203 pair execution order differs")
        for job in rows:
            request = requests[job.job_id]
            entries.append(
                models.ExecutionOrderEntry(
                    ordinal=len(entries),
                    source_cell_ordinal=cell_ordinal,
                    job_id=job.job_id,
                    request_id=request.request_id,
                    pair_id=job.pair_id,
                    source_cell_id=job.source_cell_id,
                    arm=job.arm,
                    execution_order_within_pair=job.execution_order_within_pair,
                )
            )
    if sum(item.arm == "C" for item in entries[::2]) != 6:
        _fail("manifest.order", "v26.203 control/repair first-order balance differs")
    return tuple(entries)


def prepare_execution(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> PreparedOnlineCalibration:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    v203_root = package_root / V203_DIR
    audit_bytes = external_audit_path.read_bytes()
    if len(audit_bytes) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(audit_bytes) != (
        EXTERNAL_AUDIT_SHA256
    ):
        _fail("authorization.audit", "v26.204 external online Audit bytes differ")
    artifact = _revalidate_v203(v203_root)
    decision = v203_models.Decision.model_validate(_load(v203_root / "decision.json"))
    transition = v203_models.Transition.model_validate(
        _load(v203_root / "prospective_transition.json")
    )
    manifest = v203_models.CalibrationManifest.model_validate(
        _load(v203_root / "calibration_manifest.json")
    )
    population = v203_models.StratifiedCalibrationPopulation.model_validate(
        _load(v203_root / "stratified_calibration_population.json")
    )
    action_contract = v203_models.ExactActionInterfaceContract.model_validate(
        _load(v203_root / "exact_action_interface_contract.json")
    )
    gate_contract = v203_models.OnlineGateContract.model_validate(
        _load(v203_root / "online_gate_contract.json")
    )
    evidence = v203_models.EvidenceSchemaAudit.model_validate(
        _load(v203_root / "calibration_evidence_schema_audit.json")
    )
    profiles = tuple(
        v203_models.InterfaceProfile.model_validate(item)
        for item in _load(v203_root / "interface_profiles.json")["profiles"]
    )
    authorization = cast(
        models.ExternalOnlineAuthorization,
        models.make_identity(
            models.ExternalOnlineAuthorization,
            {
                "audit_sha256": EXTERNAL_AUDIT_SHA256,
                "v203_decision_id": decision.decision_id,
                "v203_transition_id": transition.transition_id,
                "v203_manifest_id": manifest.manifest_id,
                "v203_action_contract_id": action_contract.contract_id,
                "v203_gate_contract_id": gate_contract.contract_id,
            },
            field="authorization_id",
            prefix="finance_v26_204_external_online_authorization:",
        ),
    )
    freeze = cast(
        models.V203Freeze,
        models.make_identity(
            models.V203Freeze,
            {
                "authorization_id": authorization.authorization_id,
                "source_commit": "511b9603fe9cdced1b8ea49f5753515318c827e8",
                "source_tree": "2ba56b284f3b7119cce41bff33d70c9bf231b86b",
                "artifact_manifest_id": artifact.manifest_id,
                "artifact_root": artifact.artifact_root,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "population_id": population.population_id,
                "manifest_id": manifest.manifest_id,
                "action_contract_id": action_contract.contract_id,
                "evidence_schema_audit_id": evidence.audit_id,
                "gate_contract_id": gate_contract.contract_id,
            },
            field="freeze_id",
            prefix="finance_v26_204_v203_freeze:",
        ),
    )
    profile_payload = _load(package_root / v200.MODEL_PROFILE_PATH)
    config = v200.require_stage_one_model_config(
        AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    expected_config_sha = v203_models.canonical_sha256(config.model_dump(mode="json"))
    for job in manifest.jobs:
        if (
            job.model_config_id != config.public_manifest_hash
            or job.model_request_config_sha256 != expected_config_sha
            or job.provider_calls != 0
        ):
            _fail("manifest.model", f"v26.203 frozen model parent differs:{job.job_id}")
    for request in manifest.requests:
        if models.canonical_sha256(_request_body(config, request.messages)) != (
            request.canonical_request_body_sha256
        ):
            _fail("manifest.request", f"v26.203 request body differs:{request.job_id}")
    order = _execution_order(manifest, population)
    preparation = cast(
        models.OnlineExecutionPreparation,
        models.make_identity(
            models.OnlineExecutionPreparation,
            {
                "authorization_id": authorization.authorization_id,
                "v203_freeze_id": freeze.freeze_id,
                "manifest_id": manifest.manifest_id,
                "population_id": population.population_id,
                "action_contract_id": action_contract.contract_id,
                "evidence_schema_audit_id": evidence.audit_id,
                "gate_contract_id": gate_contract.contract_id,
                "interface_profile_ids": tuple(sorted(item.profile_id for item in profiles)),
                "execution_order": order,
            },
            field="preparation_id",
            prefix="finance_v26_204_online_execution_preparation:",
        ),
    )
    return PreparedOnlineCalibration(
        repository_root=repository_root,
        package_root=package_root,
        output_dir=output_dir.resolve(),
        external_audit_bytes=audit_bytes,
        authorization=authorization,
        freeze=freeze,
        preparation=preparation,
        manifest=manifest,
        population=population,
        action_contract=action_contract,
        gate_contract=gate_contract,
        config=config,
    )


class PrecredentialAuthorizationGuard:
    def __init__(self, authorization: models.ExternalOnlineAuthorization) -> None:
        self._authorization = authorization
        self._bytes = models.canonical_bytes(authorization)
        self._consumed = False

    def admit(
        self,
        *,
        candidate: models.ExternalOnlineAuthorization,
        candidate_bytes: bytes,
        preparation_id: str,
        requested_stage: str,
        requested_provider_calls: int,
    ) -> models.OnlineAuthorizationAdmission:
        if self._consumed:
            _fail("authorization.reuse", "v26.204 online Authorization is already consumed")
        if (
            candidate != self._authorization
            or candidate_bytes != self._bytes
            or requested_stage != models.CONSUMED_STAGE
            or requested_provider_calls != 24
        ):
            _fail("authorization.admission", "v26.204 online Authorization request differs")
        self._consumed = True
        return cast(
            models.OnlineAuthorizationAdmission,
            models.make_identity(
                models.OnlineAuthorizationAdmission,
                {
                    "authorization_id": candidate.authorization_id,
                    "preparation_id": preparation_id,
                    "canonical_authorization_sha256": _sha256_bytes(candidate_bytes),
                },
                field="admission_id",
                prefix="finance_v26_204_online_authorization_admission:",
            ),
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
        _fail("source.git", "v26.204 execution source tree has tracked changes")
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
    _fail("credential.lookup", f"missing credential environment variable:{key}")


def _outer_terminal(telemetry: ModelCallTelemetry) -> str:
    error = telemetry.error_type or "unknown_provider_failure"
    if error == "ReasoningBudgetExhaustedError":
        return "thinking_integrity_failure"
    if "Usage" in error:
        return "usage_integrity_failure"
    if "Thinking" in error:
        return "thinking_integrity_failure"
    if "Identity" in error or "Envelope" in error:
        return "provider_identity_failure"
    if not telemetry.http_success:
        return "provider_transport_failure"
    return "provider_response_contract_failure"


def _usage(telemetry: ModelCallTelemetry) -> dict[str, Any] | None:
    values = {
        "prompt_tokens": telemetry.prompt_tokens,
        "prompt_cache_hit_tokens": telemetry.prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": telemetry.prompt_cache_miss_tokens,
        "completion_tokens": telemetry.completion_tokens,
        "reasoning_tokens": telemetry.reasoning_tokens,
        "total_tokens": telemetry.total_tokens,
        "estimated_cost": telemetry.estimated_cost,
        "cost_estimation_method": telemetry.cost_estimation_method,
    }
    if all(value is None for value in values.values()):
        return None
    return values


def _schema_fields(
    request: v203_models.FirstRequestDescriptor,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    if request.arm == "C":
        root = json.loads(request.messages[0].content)["prompt_core"]["public_prompt"]
        semantic = root["task"]["semantic_task"]
        answer_fields = semantic["answer_fields"]
        output_fields = semantic["operator_output_fields"]
    else:
        root = json.loads(request.messages[1].content)
        metadata = root["verifier_internal_task_metadata"]
        answer_fields = metadata["answer_fields"]
        output_fields = metadata["operator_output_fields"]
    answer = tuple(sorted(str(item) for item in answer_fields))
    operation = tuple(
        sorted({tuple(sorted(str(item) for item in values)) for values in output_fields.values()})
    )
    return answer, operation


def _response_and_observation(
    *,
    job: v203_models.CalibrationJob,
    request: v203_models.FirstRequestDescriptor,
    cell: v203_models.SourceCell,
    payload: dict[str, Any] | None,
    terminal: str | None,
    telemetry: ModelCallTelemetry,
) -> tuple[
    v203_models.FirstResponseDescriptor,
    v203_models.FirstActionInterfaceObservation,
]:
    usage = _usage(telemetry)
    response_hash = (
        v203_models.canonical_sha256(payload)
        if payload is not None
        else v203_models.canonical_sha256(
            {"typed_outer_terminal": terminal, "telemetry": telemetry.model_dump(mode="json")}
        )
    )
    response = cast(
        v203_models.FirstResponseDescriptor,
        v203_models.make_identity(
            v203_models.FirstResponseDescriptor,
            {
                "job_id": job.job_id,
                "request_id": request.request_id,
                "source_cell_id": job.source_cell_id,
                "arm": job.arm,
                "evidence_kind": "empirical_calibration",
                "response_sha256": response_hash,
                "typed_outer_terminal": terminal,
                "exact_json_object": payload,
                "usage": usage,
                "thinking_present": telemetry.reasoning_content_present,
                "provider_call_count": 1,
            },
            field="response_id",
            prefix="fresh_first_response_descriptor:",
        ),
    )
    exact_abi = False
    action_reference: bool | None = None
    state_binding: bool | None = None
    if payload is not None:
        try:
            parsed = action_grammar.parse_exact_canonical_action_payload(payload)
        except action_grammar.SemanticActionResponseRejection:
            pass
        else:
            exact_abi = True
            action_reference = parsed.action_id in set(cell.candidate_action_ids)
            state_binding = parsed.state_id == cell.current_state_id
    answer_fields, operation_sets = _schema_fields(request)
    shape = tuple(sorted(payload)) if payload is not None else ()
    observation = cast(
        v203_models.FirstActionInterfaceObservation,
        v203_models.make_identity(
            v203_models.FirstActionInterfaceObservation,
            {
                "job_id": job.job_id,
                "request_id": request.request_id,
                "response_id": response.response_id,
                "source_cell_id": job.source_cell_id,
                "arm": job.arm,
                "evidence_kind": "empirical_calibration",
                "typed_outer_terminal": terminal,
                "exact_json_object": payload,
                "exact_four_field_abi_valid": exact_abi,
                "action_reference_valid": action_reference,
                "state_binding_valid": state_binding,
                "runtime_step_committed": None,
                "answer_schema_exact_match": payload is not None and shape == answer_fields,
                "operation_output_schema_exact_match": (
                    payload is not None and shape in operation_sets
                ),
                "usage": usage,
                "thinking_present": telemetry.reasoning_content_present,
            },
            field="observation_id",
            prefix="fresh_first_action_interface_observation:",
        ),
    )
    return response, observation


def _execute_one(
    *,
    prepared: PreparedOnlineCalibration,
    entry: models.ExecutionOrderEntry,
    run_start: models.RunStartReceipt,
    client: Any,
) -> tuple[models.PublicProviderCallRaw, models.CalibrationJobResult, models.ObservationRecord]:
    jobs = {item.job_id: item for item in prepared.manifest.jobs}
    requests = {item.job_id: item for item in prepared.manifest.requests}
    cells = {item.source_cell_id: item for item in prepared.population.cells}
    job = jobs[entry.job_id]
    request = requests[entry.job_id]
    cell = cells[entry.source_cell_id]
    payload: dict[str, Any] | None = None
    terminal: str | None = None
    exception_type: str | None = None
    exception_reason: str | None = None
    try:
        payload, telemetry = client.complete_messages(request)
    except LLMClientError as exc:
        if len(exc.telemetry) != 1:
            _fail("provider.telemetry", "v26.204 one-call failure lacks exact telemetry")
        telemetry = exc.telemetry[0]
        terminal = _outer_terminal(telemetry)
        exception_type = telemetry.error_type or type(exc).__name__
        exception_reason = _sha256_bytes(str(exc).encode("utf-8"))
    raw = cast(
        models.PublicProviderCallRaw,
        models.make_identity(
            models.PublicProviderCallRaw,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "authorization_id": prepared.authorization.authorization_id,
                "manifest_id": prepared.manifest.manifest_id,
                "ordinal": entry.ordinal,
                "job_id": job.job_id,
                "request_id": request.request_id,
                "source_cell_id": job.source_cell_id,
                "arm": job.arm,
                "raw_namespace": job.raw_namespace,
                "canonical_request_body_sha256": request.canonical_request_body_sha256,
                "public_response_object": payload,
                "typed_outer_terminal": terminal,
                "exception_type": exception_type,
                "exception_reason_sha256": exception_reason,
                "telemetry": telemetry,
            },
            field="raw_id",
            prefix="fresh_first_response_calibration_public_provider_raw:",
        ),
    )
    response, observation = _response_and_observation(
        job=job,
        request=request,
        cell=cell,
        payload=payload,
        terminal=terminal,
        telemetry=telemetry,
    )
    result = cast(
        models.CalibrationJobResult,
        models.make_identity(
            models.CalibrationJobResult,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "manifest_id": prepared.manifest.manifest_id,
                "ordinal": entry.ordinal,
                "job_id": job.job_id,
                "request_id": request.request_id,
                "source_cell_id": job.source_cell_id,
                "arm": job.arm,
                "raw_id": raw.raw_id,
                "result_namespace": job.result_namespace,
                "response": response,
            },
            field="result_id",
            prefix="fresh_first_response_calibration_job_result:",
        ),
    )
    record = cast(
        models.ObservationRecord,
        models.make_identity(
            models.ObservationRecord,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "manifest_id": prepared.manifest.manifest_id,
                "ordinal": entry.ordinal,
                "job_id": job.job_id,
                "raw_id": raw.raw_id,
                "result_id": result.result_id,
                "observation_namespace": job.observation_namespace,
                "observation": observation,
            },
            field="record_id",
            prefix="fresh_first_response_calibration_observation_record:",
        ),
    )
    return raw, result, record


def _mcnemar_p(repair_only: int, control_only: int) -> str:
    discordant = repair_only + control_only
    if discordant == 0:
        return "1"
    lower = min(repair_only, control_only)
    numerator = 2 * sum(comb(discordant, index) for index in range(lower + 1))
    denominator = 2**discordant
    value = min(Decimal(1), Decimal(numerator) / Decimal(denominator))
    return format(value, "f")


def _gate_evaluation(
    *,
    prepared: PreparedOnlineCalibration,
    run_start: models.RunStartReceipt,
    records: Sequence[models.ObservationRecord],
    paired: v203_models.ExactPairedCalibrationEvaluation,
) -> models.OnlineGateEvaluation:
    contract = prepared.gate_contract
    complete = len(records)
    g0 = complete == contract.g0_exact_job_raw_result_observation_count
    values = {
        "run_start_receipt_id": run_start.receipt_id,
        "manifest_id": prepared.manifest.manifest_id,
        "gate_contract_id": contract.contract_id,
        "paired_evaluation_id": paired.evaluation_id,
        "g0_actual_complete_evidence_count": complete,
        "g1_actual_paired_semantic_parent_mismatch_count": 0,
        "g2_actual_parser_grammar_candidate_change_count": 0,
        "g3_actual_repair_exact_action_abi_count": paired.repair_abi_success_count,
        "g4_actual_repair_reference_state_valid_count": (paired.repair_reference_state_valid_count),
        "g5_actual_paired_repair_only_abi_success_count": (
            paired.paired_repair_only_abi_success_count
        ),
        "g6_actual_paired_control_only_abi_success_count": (
            paired.paired_control_only_abi_success_count
        ),
        "g7_actual_adaptation_relaxation_retry_count": 0,
        "g8_actual_qa_mapper_state_contribution_vtdo_count": 0,
        "g0_passed": g0,
        "g1_passed": True,
        "g2_passed": True,
        "g3_passed": paired.repair_abi_success_count >= contract.g3_repair_exact_action_abi_minimum,
        "g4_passed": (
            paired.repair_reference_state_valid_count
            >= contract.g4_repair_reference_state_valid_minimum
        ),
        "g5_passed": (
            paired.paired_repair_only_abi_success_count
            >= contract.g5_paired_repair_only_abi_success_minimum
        ),
        "g6_passed": (
            paired.paired_control_only_abi_success_count
            <= contract.g6_paired_control_only_abi_success_maximum
        ),
        "g7_passed": True,
        "g8_passed": True,
        "all_gates_passed": False,
        "exact_mcnemar_supplementary_two_sided_p": _mcnemar_p(
            paired.paired_repair_only_abi_success_count,
            paired.paired_control_only_abi_success_count,
        ),
    }
    values["all_gates_passed"] = all(cast(bool, values[f"g{index}_passed"]) for index in range(9))
    return cast(
        models.OnlineGateEvaluation,
        models.make_identity(
            models.OnlineGateEvaluation,
            values,
            field="gate_evaluation_id",
            prefix="finance_v26_204_online_gate_evaluation:",
        ),
    )


def _artifact_manifest(root: Path) -> models.ExecutionArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "execution_artifact_manifest.json"
    )
    artifact_root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_204_execution_artifact_root:",
    )
    return cast(
        models.ExecutionArtifactManifest,
        models.make_identity(
            models.ExecutionArtifactManifest,
            {
                "run_id": RUN_ID,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": artifact_root,
            },
            field="manifest_id",
            prefix="finance_v26_204_execution_artifact_manifest:",
        ),
    )


def execute(
    *,
    prepared: PreparedOnlineCalibration,
    client_factory: Callable[[AgentModelConfig], Any] = MessageAwareStageOneClient,
    credential_loader: Callable[[Path, str], None] = _load_env_key,
    source_identity: tuple[str, str] | None = None,
) -> models.OnlineExecutionSummary:
    if prepared.output_dir.exists():
        _fail("output.exists", "v26.204 immutable output directory already exists")
    guard = PrecredentialAuthorizationGuard(prepared.authorization)
    authorization_bytes = models.canonical_bytes(prepared.authorization)
    admission = guard.admit(
        candidate=prepared.authorization,
        candidate_bytes=authorization_bytes,
        preparation_id=prepared.preparation.preparation_id,
        requested_stage=models.CONSUMED_STAGE,
        requested_provider_calls=24,
    )
    source_commit, source_tree = source_identity or _git_identity(prepared.repository_root)
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(
        prepared.output_dir / "external_audit.txt", prepared.external_audit_bytes
    )
    _write_no_replace(
        prepared.output_dir / "external_online_authorization.json", prepared.authorization
    )
    _write_no_replace(prepared.output_dir / "v26_203_freeze.json", prepared.freeze)
    _write_no_replace(
        prepared.output_dir / "online_execution_preparation.json", prepared.preparation
    )
    _write_no_replace(prepared.output_dir / "online_authorization_admission.json", admission)
    run_start = cast(
        models.RunStartReceipt,
        models.make_identity(
            models.RunStartReceipt,
            {
                "authorization_id": prepared.authorization.authorization_id,
                "admission_id": admission.admission_id,
                "preparation_id": prepared.preparation.preparation_id,
                "manifest_id": prepared.manifest.manifest_id,
                "exact_execution_order_sha256": models.canonical_sha256(
                    prepared.preparation.execution_order
                ),
                "execution_source_commit": source_commit,
                "execution_source_tree": source_tree,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            field="receipt_id",
            prefix="finance_v26_204_online_run_start_receipt:",
        ),
    )
    _write_no_replace(prepared.output_dir / "run_start_receipt.json", run_start)
    credential_loader(prepared.package_root, prepared.config.api_key_env)
    client = client_factory(prepared.config)
    raws: list[models.PublicProviderCallRaw] = []
    results: list[models.CalibrationJobResult] = []
    records: list[models.ObservationRecord] = []
    attempted = 0
    fatal: str | None = None
    status: models.ExecutionStatus = "completed"
    try:
        for entry in prepared.preparation.execution_order:
            attempted += 1
            raw, result, record = _execute_one(
                prepared=prepared,
                entry=entry,
                run_start=run_start,
                client=client,
            )
            _write_no_replace(prepared.output_dir / "raw" / f"job_{entry.ordinal:03d}.json", raw)
            _write_no_replace(
                prepared.output_dir / "results" / f"job_{entry.ordinal:03d}.json", result
            )
            _write_no_replace(
                prepared.output_dir / "observations" / f"job_{entry.ordinal:03d}.json", record
            )
            checkpoint = cast(
                models.ExecutionCheckpoint,
                models.make_identity(
                    models.ExecutionCheckpoint,
                    {
                        "run_start_receipt_id": run_start.receipt_id,
                        "ordinal": entry.ordinal,
                        "job_id": entry.job_id,
                        "raw_id": raw.raw_id,
                        "result_id": result.result_id,
                        "observation_record_id": record.record_id,
                    },
                    field="checkpoint_id",
                    prefix="finance_v26_204_online_execution_checkpoint:",
                ),
            )
            _write_no_replace(
                prepared.output_dir / "checkpoints" / f"job_{entry.ordinal:03d}.json",
                checkpoint,
            )
            raws.append(raw)
            results.append(result)
            records.append(record)
    except (KeyboardInterrupt, SystemExit):
        status = "interrupted"
        fatal = "operator_interruption"
    except Exception as exc:
        status = "failed"
        fatal = f"{type(exc).__name__}:{_sha256_bytes(str(exc).encode('utf-8'))}"
    paired: v203_models.ExactPairedCalibrationEvaluation | None = None
    gates: models.OnlineGateEvaluation | None = None
    if len(records) == 24:
        paired = models.make_paired_evaluation(
            manifest_id=prepared.manifest.manifest_id,
            observations=tuple(item.observation for item in records),
        )
        gates = _gate_evaluation(
            prepared=prepared,
            run_start=run_start,
            records=records,
            paired=paired,
        )
        _write_no_replace(prepared.output_dir / "exact_paired_calibration_evaluation.json", paired)
        _write_no_replace(prepared.output_dir / "online_gate_evaluation.json", gates)
    if len(records) != 24 and status == "completed":
        status = "failed"
    terminal_partition = dict(
        sorted(Counter(raw.typed_outer_terminal or "public_json_response" for raw in raws).items())
    )
    total_cost = sum(
        (Decimal(str(raw.telemetry.estimated_cost or 0)) for raw in raws),
        start=Decimal(0),
    )
    summary = cast(
        models.OnlineExecutionSummary,
        models.make_identity(
            models.OnlineExecutionSummary,
            {
                "run_start_receipt_id": run_start.receipt_id,
                "authorization_id": prepared.authorization.authorization_id,
                "manifest_id": prepared.manifest.manifest_id,
                "paired_evaluation_id": paired.evaluation_id if paired else None,
                "gate_evaluation_id": gates.gate_evaluation_id if gates else None,
                "execution_status": status,
                "attempted_job_count": attempted,
                "raw_count": len(raws),
                "result_count": len(results),
                "observation_count": len(records),
                "provider_calls": len(raws),
                "typed_outer_terminal_partition": terminal_partition,
                "total_usage_tokens": sum(raw.telemetry.total_tokens or 0 for raw in raws),
                "estimated_cost_usd": format(total_cost, "f"),
                "all_online_gates_passed": gates.all_gates_passed if gates else None,
            },
            field="summary_id",
            prefix="finance_v26_204_online_execution_summary:",
        ),
    )
    _write_no_replace(prepared.output_dir / "execution_summary.json", summary)
    _write_no_replace(
        prepared.output_dir / "prospective_transition.json",
        {
            "consumed_stage": models.CONSUMED_STAGE,
            "execution_status": status,
            "fatal_error": fatal,
            "online_gate_evaluation_id": gates.gate_evaluation_id if gates else None,
            "all_online_gates_passed": gates.all_gates_passed if gates else None,
            "next_stage": models.NEXT_STAGE,
            "postrun_independent_audit_only": True,
            "full_192_job_execution_authorized": False,
            "qa_mapper_state_contribution_vtdo_authorized": False,
        },
    )
    _write_no_replace(
        prepared.output_dir / "source_identity.json",
        {"commit": source_commit, "tree": source_tree},
    )
    artifact = _artifact_manifest(prepared.output_dir)
    _write_no_replace(prepared.output_dir / "execution_artifact_manifest.json", artifact)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute Finance v26.204 exact paired calibration")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    arguments = parser.parse_args()
    prepared = prepare_execution(
        repository_root=arguments.repository_root,
        output_dir=arguments.output_dir,
        external_audit_path=arguments.external_audit,
    )
    summary = execute(prepared=prepared)
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
