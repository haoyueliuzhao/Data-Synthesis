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
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as outcome_authority
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
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization as v223,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models as v223_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as v213_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_runtime as v213_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_models as v218_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_runtime as v218_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as v217_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime as v217_runtime,
)
from trusted_synthesis.runtime.agent.client import (
    EmptyFinalContentError,
    LLMClientError,
    ReasoningBudgetExhaustedError,
    _estimate_cost,
    _optional_int,
    _strip_json_fence,
)
from trusted_synthesis.runtime.agent.prospective_thinking_client import ProviderNativeToolCallError
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    RedactedProviderResponseEnvelope,
    RedactedProviderResponseFields,
    capture_redacted_provider_response_fields,
    require_admitted_response_envelope,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_ID,
    StageOneProspectiveThinkingJsonClient,
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID: Final = (
    "finance_v26_224_fresh_exact_v209_parent_bound_exact_192_job_online_execution_v1_20260903"
)
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
LEDGER_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/authorization_consumption_ledger"
)
V223_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_223_fresh_exact_v209_execution_condition_authoritative_parent_bound_"
    "online_execution_authorization_v1_20260903"
)
V220_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_220_fresh_repaired_upstream_terminal_domain_exact_registry_complement_"
    "bound_online_execution_authorization_v1_20260903"
)
V218_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_218_fresh_repaired_upstream_terminal_domain_exact_registry_complement_"
    "binding_preflight_v1_20260903"
)
V217_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_217_fresh_repaired_upstream_typed_failure_event_authority_and_"
    "artifact_backing_preflight_v1_20260903"
)
V213_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_213_fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_v1_20260902"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_final_request_"
    "contract_continuity_repair_preflight_v1_20260902"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
EXTERNAL_REVIEW_SHA256: Final = "10733a734b94693194eb85ac4ab0ee4fe475b48cf2cca5724c936308ed91cbb0"
EXTERNAL_REVIEW_BYTES: Final = 15_248
OPERATOR_DIRECTIVE: Final = "参照审计，并行开展实验"
MAX_WORKERS: Final = 8
V223_MANIFEST_FILE_SHA256: Final = (
    "49890a8de312ba0bf16f3263ea92a64c1e9e9c2775b425febb1ab3465a4de8fd"
)
V209_MANIFEST_FILE_SHA256: Final = (
    "6f691c0a0fecf7ca32ce1c59f9810e617c85aad201fe0d2afcada7073fa94300"
)


class V224Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


class UnboundExecutionFailure(RuntimeError):
    """A failure that has no authorized v26.213/v26.218 terminal source."""


def _fail(stage: str, reason: str) -> NoReturn:
    raise V224Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _durable_write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _verify_formal_directory(
    root: Path,
    *,
    file_count: int,
    total_bytes: int,
    member_count: int,
    member_bytes: int,
    manifest_id: str,
    artifact_root: str,
    manifest_file_sha256: str,
) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    manifest = cast(dict[str, Any], json.loads(files.get("artifact_manifest.json", b"{}")))
    members = cast(list[dict[str, Any]], manifest.get("members", []))
    names = tuple(str(item.get("relative_path", "")) for item in members)
    expected = tuple(sorted(set(files) - {"artifact_manifest.json"}))
    if (
        len(files) != file_count
        or sum(len(item) for item in files.values()) != total_bytes
        or len(members) != member_count
        or sum(int(item.get("byte_count", -1)) for item in members) != member_bytes
        or names != expected
        or _sha_bytes(files.get("artifact_manifest.json", b"")) != manifest_file_sha256
        or manifest.get("manifest_id") != manifest_id
        or manifest.get("artifact_root") != artifact_root
    ):
        _fail("freeze.geometry", f"formal directory differs:{root.name}")
    for item in members:
        payload = files[str(item["relative_path"])]
        if len(payload) != item["byte_count"] or _sha_bytes(payload) != item["sha256"]:
            _fail("freeze.member", f"formal member differs:{item['relative_path']}")
    return manifest


def _git_identity(repository_root: Path) -> tuple[str, str]:
    changed = subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if changed.strip():
        _fail("source.clean", "v26.224 execution requires a clean tracked source tree")
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ("git", "rev-parse", "HEAD^{tree}"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


@dataclass(frozen=True)
class FrozenBindings:
    main_dispatcher: v213_models.ObservationDerivedDispatcherBinding
    main_persistence: v213_models.ObservationBoundPersistenceBinding
    failure_complement: v218_models.ExactRegistryComplementBinding
    failure_composition: v218_models.CompositionContract
    failure_source_contract: v217_models.TypedFailureExitSurfaceContract
    event_source: v217_models.UpstreamEventSourceBinding
    upstream_observation: v217_models.UpstreamObservationBinding
    runner_observation: v217_models.RunnerObservationBinding
    failure_dispatcher: v217_models.DispatcherBinding
    failure_persistence: v217_models.PersistenceBinding
    terminal_registry: outcome_authority.FreshTerminalRegistry


@dataclass(frozen=True)
class PreparedExecution:
    repository_root: Path
    package_root: Path
    output_dir: Path
    ledger_path: Path
    external_review_bytes: bytes
    external_authorization: models.ExternalExecutionAuthorization
    v223_freeze: models.V223Freeze
    authorization: v223_models.ExactOnlineExecutionAuthorization
    authorization_file_bytes: bytes
    authorization_canonical_bytes: bytes
    admission: v223_models.OnlineAuthorizationAdmission
    composition: v223_models.OnlineExecutionCompositionContract
    preparation: models.ExecutionPreparation
    catalog: v209_models.ExecutableRunnerPackageCatalog
    manifest: v209_models.ExecutableDevelopmentManifest
    runner_contract: v209_models.ExecutableRunnerContract
    execution_contract: v209_models.ExecutableExecutionContract
    implementation: v209_models.ImplementationBinding
    frozen_parents: v209.FrozenParents
    runtime: v188.PreparedExecution
    config: AgentModelConfig
    bindings: FrozenBindings


def _external_authorization(review_bytes: bytes) -> models.ExternalExecutionAuthorization:
    if len(review_bytes) != EXTERNAL_REVIEW_BYTES or _sha_bytes(review_bytes) != (
        EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.review", "v26.223 external audit bytes differ")
    return models.make_identity(
        models.ExternalExecutionAuthorization,
        {
            "review_sha256": EXTERNAL_REVIEW_SHA256,
            "operator_directive_sha256": _sha_bytes(OPERATOR_DIRECTIVE.encode("utf-8")),
        },
        field="external_authorization_id",
        prefix="finance_v26_224_external_execution_authorization:",
    )


def _load_bindings(repository_root: Path) -> FrozenBindings:
    v220_composition = cast(
        dict[str, Any],
        _load(repository_root / V220_DIR / "online_execution_composition_contract.json"),
    )
    main_dispatcher = v213_models.ObservationDerivedDispatcherBinding.model_validate(
        _load(repository_root / V213_DIR / "observation_derived_dispatcher_binding.json")
    )
    main_persistence = v213_models.ObservationBoundPersistenceBinding.model_validate(
        _load(repository_root / V213_DIR / "observation_bound_persistence_binding.json")
    )
    failure_complement = v218_models.ExactRegistryComplementBinding.model_validate(
        _load(repository_root / V218_DIR / "exact_registry_complement_binding.json")
    )
    failure_composition = v218_models.CompositionContract.model_validate(
        _load(repository_root / V218_DIR / "composition_contract.json")
    )
    source_contract = v217_models.TypedFailureExitSurfaceContract.model_validate(
        _load(repository_root / V217_DIR / "typed_failure_exit_surface_contract.json")
    )
    event_source = v217_models.UpstreamEventSourceBinding.model_validate(
        _load(repository_root / V217_DIR / "upstream_event_source_binding.json")
    )
    upstream = v217_models.UpstreamObservationBinding.model_validate(
        _load(repository_root / V217_DIR / "upstream_observation_binding.json")
    )
    runner = v217_models.RunnerObservationBinding.model_validate(
        _load(repository_root / V217_DIR / "runner_observation_binding.json")
    )
    failure_dispatcher = v217_models.DispatcherBinding.model_validate(
        _load(repository_root / V217_DIR / "dispatcher_binding.json")
    )
    failure_persistence = v217_models.PersistenceBinding.model_validate(
        _load(repository_root / V217_DIR / "persistence_binding.json")
    )
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository_root / V195_DIR / "fresh_terminal_registry.json")
    )
    pairs = (
        (
            main_dispatcher.binding_id,
            v220_composition["exact_v213_main_dispatcher_binding_id"],
        ),
        (
            main_persistence.binding_id,
            v220_composition["exact_v213_main_persistence_binding_id"],
        ),
        (
            failure_complement.binding_id,
            v220_composition["exact_v218_failure_complement_binding_id"],
        ),
        (
            failure_composition.contract_id,
            v220_composition["exact_v218_failure_composition_contract_id"],
        ),
        (
            source_contract.contract_id,
            v220_composition["exact_v218_failure_source_contract_id"],
        ),
    )
    if any(actual != expected for actual, expected in pairs):
        _fail("freeze.bindings", "v26.213/v26.218 exact execution parent differs")
    v218_runtime.ExactRegistryComplementAuthority(
        registry=registry, expected_binding=failure_complement
    ).admit(failure_complement)
    return FrozenBindings(
        main_dispatcher=main_dispatcher,
        main_persistence=main_persistence,
        failure_complement=failure_complement,
        failure_composition=failure_composition,
        failure_source_contract=source_contract,
        event_source=event_source,
        upstream_observation=upstream,
        runner_observation=runner,
        failure_dispatcher=failure_dispatcher,
        failure_persistence=failure_persistence,
        terminal_registry=registry,
    )


def prepare_execution(
    *, repository_root: Path, output_dir: Path, external_review_path: Path
) -> PreparedExecution:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = output_dir.resolve()
    expected_output = (repository_root / OUTPUT_DIR).resolve()
    if output_dir != expected_output:
        _fail("scope.output", "live v26.224 output directory is fixed by the authorization")
    if output_dir.exists():
        raise FileExistsError(f"one-shot v26.224 output already exists:{output_dir}")
    review_bytes = external_review_path.read_bytes()
    external = _external_authorization(review_bytes)
    v223_root = repository_root / V223_DIR
    manifest223 = _verify_formal_directory(
        v223_root,
        file_count=17,
        total_bytes=136_590,
        member_count=16,
        member_bytes=133_829,
        manifest_id=models.V223_MANIFEST_ID,
        artifact_root=models.V223_ARTIFACT_ROOT,
        manifest_file_sha256=V223_MANIFEST_FILE_SHA256,
    )
    source223 = cast(dict[str, Any], _load(v223_root / "source_identity.json"))
    composition = v223_models.OnlineExecutionCompositionContract.model_validate(
        _load(v223_root / "online_execution_composition_contract.json")
    )
    authorization = v223_models.ExactOnlineExecutionAuthorization.model_validate(
        _load(v223_root / "exact_online_execution_authorization.json")
    )
    auth_file = (v223_root / "exact_online_execution_authorization.json").read_bytes()
    auth_canonical = v223_models.canonical_bytes(authorization)
    if (
        auth_file != auth_canonical + b"\n"
        or _sha_bytes(auth_file) != models.V223_AUTHORIZATION_SHA256
        or len(auth_file) != 35_090
        or source223.get("source_commit") != "5eed1e0bb56757e3046391a8d25d522dea577975"
        or source223.get("source_tree") != "119c4b0af09d958b34548933d55512bee5e5ac9b"
    ):
        _fail("freeze.v223", "v26.223 authorization bytes or source identity differs")
    freeze = models.make_identity(
        models.V223Freeze,
        {
            "external_authorization_id": external.external_authorization_id,
            "source_commit": source223["source_commit"],
            "source_tree": source223["source_tree"],
            "artifact_manifest_id": manifest223["manifest_id"],
            "artifact_root": manifest223["artifact_root"],
            "composition_contract_id": composition.contract_id,
            "authorization_id": authorization.authorization_id,
            "authorization_file_sha256": _sha_bytes(auth_file),
            "exact_job_set_sha256": authorization.exact_job_set_sha256,
        },
        field="freeze_id",
        prefix="finance_v26_224_v223_authorization_freeze:",
    )
    guard = v223_models.PrecredentialAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=auth_canonical,
    )
    admission = guard.admit(**v223._request(authorization))  # noqa: SLF001
    v209_root = repository_root / V209_DIR
    _verify_formal_directory(
        v209_root,
        file_count=21,
        total_bytes=44_916_386,
        member_count=20,
        member_bytes=44_912_918,
        manifest_id=v223_models.V209_MANIFEST_ID,
        artifact_root=v223_models.V209_ARTIFACT_ROOT,
        manifest_file_sha256=V209_MANIFEST_FILE_SHA256,
    )
    catalog = v209_models.ExecutableRunnerPackageCatalog.model_validate(
        _load(v209_root / "executable_runner_package_catalog.json")
    )
    manifest = v209_models.ExecutableDevelopmentManifest.model_validate(
        _load(v209_root / "executable_development_manifest.json")
    )
    runner = v209_models.ExecutableRunnerContract.model_validate(
        _load(v209_root / "executable_runner_contract.json")
    )
    execution = v209_models.ExecutableExecutionContract.model_validate(
        _load(v209_root / "executable_execution_contract.json")
    )
    implementation = v209_models.ImplementationBinding.model_validate(
        _load(v209_root / "implementation_binding.json")
    )
    if (
        manifest.manifest_id != authorization.v209_manifest_id
        or runner.runner_id != authorization.v209_runner_id
        or runner.package_catalog_id != catalog.catalog_id
        or runner.manifest_id != manifest.manifest_id
        or execution.contract_id != authorization.v209_execution_contract_id
        or execution.package_catalog_id != catalog.catalog_id
        or execution.manifest_id != manifest.manifest_id
        or execution.runner_id != runner.runner_id
        or tuple(sorted(item.job_id for item in manifest.jobs)) != authorization.exact_job_ids
    ):
        _fail("freeze.v209", "v26.209 exact Runner condition differs")
    bindings = _load_bindings(repository_root)
    saved_predecessor = cast(dict[str, Any], _load(v209_root / "predecessor_freeze.json"))
    parents = v209._predecessor_freeze(  # noqa: SLF001
        repository_root=repository_root,
        authorization_id=str(saved_predecessor["authorization_id"]),
    )
    runtime = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir / "runtime_reserved",
    )
    profile = cast(dict[str, Any], _load(repository_root / MODEL_PROFILE))
    config = require_stage_one_model_config(
        AgentModelConfig.model_validate(profile.get("model", profile))
    )
    preparation = models.make_identity(
        models.ExecutionPreparation,
        {
            "external_authorization_id": external.external_authorization_id,
            "v223_freeze_id": freeze.freeze_id,
            "authorization_id": authorization.authorization_id,
            "authorization_bytes_sha256": _sha_bytes(auth_file),
            "composition_contract_id": composition.contract_id,
            "exact_job_ids": authorization.exact_job_ids,
            "exact_job_set_sha256": authorization.exact_job_set_sha256,
            "main_terminal_kinds": composition.main_observation_terminal_kinds,
            "failure_terminal_kinds": composition.source_bound_failure_terminal_kinds,
        },
        field="preparation_id",
        prefix="finance_v26_224_execution_preparation:",
    )
    ledger_path = repository_root / LEDGER_DIR / f"{_safe(authorization.authorization_id)}.json"
    return PreparedExecution(
        repository_root=repository_root,
        package_root=package_root,
        output_dir=output_dir,
        ledger_path=ledger_path,
        external_review_bytes=review_bytes,
        external_authorization=external,
        v223_freeze=freeze,
        authorization=authorization,
        authorization_file_bytes=auth_file,
        authorization_canonical_bytes=auth_canonical,
        admission=admission,
        composition=composition,
        preparation=preparation,
        catalog=catalog,
        manifest=manifest,
        runner_contract=runner,
        execution_contract=execution,
        implementation=implementation,
        frozen_parents=parents,
        runtime=runtime,
        config=config,
        bindings=bindings,
    )


@dataclass(frozen=True)
class ProviderResponse:
    public_value: Any
    telemetry: ModelCallTelemetry
    redacted_fields: dict[str, Any]


class ExactRequestBodyDeepSeekClient(StageOneProspectiveThinkingJsonClient):
    """One exact-body call; it never rebuilds the v26.209 messages or retries."""

    def complete_body(self, body: Mapping[str, Any]) -> ProviderResponse:
        canonical = models.canonical_bytes(dict(body))
        if (
            body.get("model") != self.config.model
            or body.get("thinking") != {"type": "enabled"}
            or body.get("response_format") != {"type": "json_object"}
            or not isinstance(body.get("messages"), list)
        ):
            raise LLMClientError("v26.224 Provider request body differs from v26.209")
        request_hash = _sha_bytes(canonical)
        request = urllib.request.Request(
            self.config.endpoint,
            data=canonical,
            headers=self._headers(json_content=True),
            method="POST",
        )
        started = time.perf_counter()
        status: int | None = None
        envelope: RedactedProviderResponseEnvelope | None = None
        redacted: RedactedProviderResponseFields | None = None
        prompt_tokens: int | None = None
        cache_hit: int | None = None
        cache_miss: int | None = None
        total_tokens: int | None = None
        estimated_cost: float | None = None
        cost_method: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                response_body = json.loads(response.read().decode("utf-8"))
            if not isinstance(response_body, Mapping):
                raise TypeError("HTTP-success response body is not an object")
            redacted = capture_redacted_provider_response_fields(response_body)
            envelope = RedactedProviderResponseEnvelope.model_validate(redacted)
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
                        "model exhausted the output budget before public content"
                    )
                raise EmptyFinalContentError("model returned empty public content")
            public = json.loads(_strip_json_fence(content))
            telemetry = self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted,
                prompt_tokens=prompt_tokens,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                cost_estimation_method=cost_method,
                discovery_attempted=False,
                discovered_count=0,
                started=started,
                json_contract_success=isinstance(public, dict),
            )
            return ProviderResponse(
                public_value=public,
                telemetry=telemetry,
                redacted_fields=redacted.model_dump(mode="json", warnings=False),
            )
        except Exception as exc:
            if isinstance(exc, urllib.error.HTTPError):
                status = int(exc.code)
            telemetry = self._telemetry(
                request_hash=request_hash,
                model=STAGE_ONE_MODEL_ID,
                status=status,
                envelope=envelope,
                redacted_fields=redacted,
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
            failure = LLMClientError(
                str(exc),
                (telemetry,),
                failure_artifact=(
                    None if redacted is None else redacted.model_dump(mode="json", warnings=False)
                ),
            )
            raise failure from exc


class ProviderJournal:
    def __init__(self, *, root: Path, run_start: models.RunStartReceipt, job_id: str) -> None:
        self._root = root
        self._run_start = run_start
        self._job_id = job_id
        self.descriptors: list[models.ProviderCallDescriptor] = []

    def _artifact(
        self,
        *,
        provider_call_id: str,
        kind: str,
        relative_path: str,
        payload: bytes,
        public_projection: dict[str, Any] | None = None,
    ) -> models.ProviderCallArtifact:
        return models.make_identity(
            models.ProviderCallArtifact,
            {
                "provider_call_id": provider_call_id,
                "artifact_kind": kind,
                "relative_path": relative_path,
                "sha256": _sha_bytes(payload),
                "byte_count": len(payload),
                "public_projection": public_projection,
                "public_projection_sha256": (
                    None
                    if public_projection is None
                    else models.canonical_sha256(public_projection)
                ),
                "public_projection_present": public_projection is not None,
            },
            field="artifact_id",
            prefix="finance_v26_224_redacted_provider_call_artifact:",
        )

    def begin(
        self, *, dispatch: v209.TransportDispatch, call_ordinal: int
    ) -> tuple[str, str, models.ProviderCallArtifact]:
        request_bytes = v209_models.canonical_bytes(dict(dispatch.request_body))
        request_sha = _sha_bytes(request_bytes)
        intention = {
            "run_start_receipt_id": self._run_start.receipt_id,
            "job_id": self._job_id,
            "call_ordinal": call_ordinal,
            "request_sha256": request_sha,
            "request_byte_count": len(request_bytes),
            "certificate_id": dispatch.certificate.certificate_id,
            "pre_transport_receipt_id": dispatch.receipt.receipt_id,
            "provider_call_authorized": True,
            "retry_authorized": False,
            "raw_request_persisted": False,
            "schema_version": models.SCHEMA_VERSION,
        }
        payload = _encoded(intention)
        intention_sha = _sha_bytes(payload)
        provider_call_id = models.provider_call_identity(
            run_start_receipt_id=self._run_start.receipt_id,
            job_id=self._job_id,
            call_ordinal=call_ordinal,
            request_sha256=request_sha,
            intention_sha256=intention_sha,
        )
        relative = (
            f"provider_calls/{_safe(self._job_id)}/call_{call_ordinal:02d}_request_metadata.json"
        )
        _durable_write_no_replace(self._root / relative, payload)
        artifact = self._artifact(
            provider_call_id=provider_call_id,
            kind="request_metadata",
            relative_path=relative,
            payload=payload,
        )
        return provider_call_id, intention_sha, artifact

    def finish(
        self,
        *,
        provider_call_id: str,
        intention_sha: str,
        request_sha: str,
        call_ordinal: int,
        response: ProviderResponse | None,
        error: LLMClientError | None,
        request_artifact: models.ProviderCallArtifact,
    ) -> models.ProviderCallDescriptor:
        artifacts = [request_artifact]
        if response is not None:
            telemetry = response.telemetry
            sensitive = v217_runtime._contains_reasoning_key(response.public_value)  # noqa: SLF001
            public_projection = (
                response.public_value
                if isinstance(response.public_value, dict) and not sensitive
                else None
            )
            response_metadata = {
                "provider_call_id": provider_call_id,
                "redacted_response_fields": response.redacted_fields,
                "public_projection": public_projection,
                "public_projection_sha256": models.canonical_sha256(response.public_value),
                "public_projection_persisted": public_projection is not None,
                "classifier_sensitive_key_observed": sensitive,
                "raw_provider_response_persisted": False,
                "private_reasoning_persisted": False,
                "schema_version": models.SCHEMA_VERSION,
            }
            response_payload = _encoded(response_metadata)
            response_relative = (
                f"provider_calls/{_safe(self._job_id)}/"
                f"call_{call_ordinal:02d}_response_metadata.json"
            )
            _durable_write_no_replace(self._root / response_relative, response_payload)
            artifacts.append(
                self._artifact(
                    provider_call_id=provider_call_id,
                    kind="response_metadata",
                    relative_path=response_relative,
                    payload=response_payload,
                    public_projection=public_projection,
                )
            )
            error_sha = None
            response_sha = models.canonical_sha256(response.public_value)
            status: Literal["succeeded", "provider_error", "transport_error"] = "succeeded"
        else:
            assert error is not None and len(error.telemetry) == 1
            telemetry = error.telemetry[0]
            error_sha = _sha_bytes(f"{type(error).__name__}:{error}".encode())
            error_metadata = {
                "provider_call_id": provider_call_id,
                "error_type": telemetry.error_type or type(error).__name__,
                "error_sha256": error_sha,
                "http_status": telemetry.http_status,
                "http_success": telemetry.http_success,
                "redacted_response_fields": error.failure_artifact,
                "raw_provider_response_persisted": False,
                "private_reasoning_persisted": False,
                "schema_version": models.SCHEMA_VERSION,
            }
            error_payload = _encoded(error_metadata)
            error_relative = (
                f"provider_calls/{_safe(self._job_id)}/call_{call_ordinal:02d}_error_metadata.json"
            )
            _durable_write_no_replace(self._root / error_relative, error_payload)
            artifacts.append(
                self._artifact(
                    provider_call_id=provider_call_id,
                    kind="error_metadata",
                    relative_path=error_relative,
                    payload=error_payload,
                )
            )
            response_sha = None
            status = "provider_error" if telemetry.http_success else "transport_error"
        usage = {
            "provider_call_id": provider_call_id,
            "telemetry": telemetry.model_dump(mode="json", warnings=False),
            "schema_version": models.SCHEMA_VERSION,
        }
        usage_payload = _encoded(usage)
        usage_relative = (
            f"provider_calls/{_safe(self._job_id)}/call_{call_ordinal:02d}_usage_metadata.json"
        )
        _durable_write_no_replace(self._root / usage_relative, usage_payload)
        artifacts.append(
            self._artifact(
                provider_call_id=provider_call_id,
                kind="usage_metadata",
                relative_path=usage_relative,
                payload=usage_payload,
            )
        )
        descriptor = models.make_identity(
            models.ProviderCallDescriptor,
            {
                "provider_call_id": provider_call_id,
                "run_start_receipt_id": self._run_start.receipt_id,
                "job_id": self._job_id,
                "call_ordinal": call_ordinal,
                "intention_sha256": intention_sha,
                "status": status,
                "request_sha256": request_sha,
                "response_sha256": response_sha,
                "error_sha256": error_sha,
                "input_tokens": telemetry.prompt_tokens or 0,
                "output_tokens": telemetry.completion_tokens or 0,
                "artifacts": tuple(sorted(artifacts, key=lambda item: item.relative_path)),
            },
            field="descriptor_id",
            prefix="finance_v26_224_redacted_provider_call_descriptor:",
        )
        relative = f"provider_calls/{_safe(self._job_id)}/call_{call_ordinal:02d}_descriptor.json"
        _durable_write_no_replace(self._root / relative, _encoded(descriptor))
        self.descriptors.append(descriptor)
        return descriptor


class LiveV209Transport(v217_runtime.ExitTracingScriptedTransport):
    def __init__(
        self,
        *,
        source_exit_authority: v217_runtime.SourceExitProofAuthority,
        client: ExactRequestBodyDeepSeekClient,
        journal: ProviderJournal,
        job_id: str,
    ) -> None:
        super().__init__(source_exit_authority=source_exit_authority)
        self._client = client
        self._journal = journal
        self._job_id = job_id
        self._primary_request_count = 0
        self._total_usage_tokens = 0

    @property
    def provider_calls(self) -> tuple[models.ProviderCallDescriptor, ...]:
        return tuple(self._journal.descriptors)

    def send(self, dispatch: v209.TransportDispatch) -> Any:
        if (
            dispatch.receipt.certificate_id != dispatch.certificate.certificate_id
            or dispatch.receipt.request_id != dispatch.certificate.request_id
            or v209_models.canonical_sha256(dispatch.request_body)
            != dispatch.certificate.canonical_request_body_sha256
            or dispatch.certificate.job_id != self._job_id
        ):
            raise UnboundExecutionFailure("live Provider dispatch chain differs before HTTP")
        call_ordinal = len(self._journal.descriptors)
        messages = dispatch.request_body.get("messages")
        if (
            len(v209_models.canonical_bytes(messages)) > 60_000
            or call_ordinal >= 23
            or (dispatch.certificate.phase != "correction" and self._primary_request_count >= 21)
        ):
            raise UnboundExecutionFailure("v26.209 request/resource bound would be exceeded")
        if dispatch.certificate.phase != "correction":
            self._primary_request_count += 1
        call_id, intention_sha, request_artifact = self._journal.begin(
            dispatch=dispatch, call_ordinal=call_ordinal
        )
        request_sha = _sha_bytes(v209_models.canonical_bytes(dict(dispatch.request_body)))
        try:
            response = self._client.complete_body(dispatch.request_body)
        except LLMClientError as error:
            self._journal.finish(
                provider_call_id=call_id,
                intention_sha=intention_sha,
                request_sha=request_sha,
                call_ordinal=call_ordinal,
                response=None,
                error=error,
                request_artifact=request_artifact,
            )
            raise UnboundExecutionFailure(
                "Provider failure has no admitted v26.209 source terminal"
            ) from error
        self._journal.finish(
            provider_call_id=call_id,
            intention_sha=intention_sha,
            request_sha=request_sha,
            call_ordinal=call_ordinal,
            response=response,
            error=None,
            request_artifact=request_artifact,
        )
        self._total_usage_tokens += response.telemetry.total_tokens or 0
        if self._total_usage_tokens > 1_120_000:
            raise UnboundExecutionFailure("v26.209 rollout-token bound was exceeded")
        self.queue(response.public_value)
        return super().send(dispatch)


@dataclass(frozen=True)
class TerminalProjection:
    terminal_kind: models.TerminalKind
    terminal_source: models.TerminalSource
    evidence: BaseModel
    decision: BaseModel


def _failure_runtime(
    *, prepared: PreparedExecution, job_id: str, root: Path
) -> tuple[
    v218_runtime.LifetimeStableSourceExitProofAuthority,
    v217_runtime.RunnerFailureObservationAuthority,
    v217_runtime.ArtifactBackedExitDispatcher,
]:
    event_authority = v217_runtime.UpstreamEventArtifactAuthority(
        root=root, binding=prepared.bindings.event_source
    )
    upstream_authority = v217_runtime.ArtifactBackedUpstreamFailureAuthority(
        root=root, event_authority=event_authority
    )
    source_exit = v218_runtime.LifetimeStableSourceExitProofAuthority(
        contract=prepared.bindings.failure_source_contract,
        upstream_authority=upstream_authority,
    )
    runner_authority = v217_runtime.RunnerFailureObservationAuthority()
    dispatcher = v217_runtime.ArtifactBackedExitDispatcher(
        binding=prepared.bindings.failure_dispatcher,
        source_contract=prepared.bindings.failure_source_contract,
        runner_authority=runner_authority,
        upstream_authority=upstream_authority,
    )
    v218_runtime.ExactRegistryComplementAuthority(
        registry=prepared.bindings.terminal_registry,
        expected_binding=prepared.bindings.failure_complement,
    ).admit(prepared.bindings.failure_complement)
    return source_exit, runner_authority, dispatcher


def _online_runner(
    *,
    prepared: PreparedExecution,
    transport: LiveV209Transport,
    source_exit: v217_runtime.SourceExitProofAuthority,
    runner_authority: v217_runtime.RunnerFailureObservationAuthority,
) -> v217_runtime.ArtifactBackedExitProvenanceRunner:
    return v217_runtime.ArtifactBackedExitProvenanceRunner(
        source_exit_authority=source_exit,
        observation_authority=runner_authority,
        runner_binding_id=prepared.bindings.runner_observation.binding_id,
        source_contract_id=prepared.bindings.failure_source_contract.contract_id,
        transport=transport,
        config=prepared.config,
        profile=prepared.frozen_parents.profile,
        prepared=prepared.runtime,
        implementation_id=prepared.implementation.implementation_id,
        prompt_contract=prepared.frozen_parents.prompt_contract,
        prompt_schema=prepared.frozen_parents.prompt_schema,
    )


def _main_evidence(
    *,
    outcome: v209.InvocationOutcome,
    job_id: str,
    public_value: Any,
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
) -> v213_models.ObservedEvidence:
    record = outcome.record
    if not isinstance(public_value, dict):
        raise UnboundExecutionFailure("main terminal lacks a public JSON object")
    if outcome.final_result is not None:
        return v213_runtime._completed_evidence(  # noqa: SLF001
            job_id=job_id,
            records=records,
            final_payload=public_value,
            result=outcome.final_result,
        )
    if record.typed_terminal in {
        "first_response_abi_invalid",
        "correction_response_abi_invalid",
        "final_response_abi_invalid",
    }:
        if record.phase == "subsequent_action":
            raise UnboundExecutionFailure(
                "v26.213 parser evidence cannot bind a subsequent_action record"
            )
        return v213_runtime._parser_evidence(  # noqa: SLF001
            job_id=job_id,
            phase=("final" if record.phase == "final" else record.phase),
            outcome=outcome,
            payload=public_value,
        )
    if record.typed_terminal in {
        "first_action_reference_invalid",
        "correction_action_reference_invalid",
    }:
        if record.phase == "subsequent_action":
            raise UnboundExecutionFailure(
                "v26.213 reference evidence cannot bind a subsequent_action record"
            )
        return v213_runtime._reference_evidence(  # noqa: SLF001
            job_id=job_id,
            phase=record.phase,
            outcome=outcome,
            payload=public_value,
        )
    if (
        record.phase == "correction"
        and record.exact_response_parsed
        and record.current_state_and_candidate_or_final_envelope_valid
        and record.runtime_step_or_finalize_completed
        and record.action_accepted is False
        and outcome.runtime_output is not None
    ):
        return cast(
            v213_models.CorrectionBoundFailureEvidence,
            v213_models.make_identity(
                v213_models.CorrectionBoundFailureEvidence,
                {
                    "job_id": job_id,
                    "invocation_record": record.model_dump(mode="json", warnings=False),
                    "public_payload": public_value,
                    "correction_terminal": outcome.runtime_output.model_dump(
                        mode="json", warnings=False
                    ),
                },
                field="evidence_id",
                prefix="fresh_repaired_correction_bound_failure_evidence:",
            ),
        )
    raise UnboundExecutionFailure("Runner outcome lacks an admitted main evidence shape")


def _derive_terminal(
    *,
    prepared: PreparedExecution,
    outcome: v209.InvocationOutcome,
    job_id: str,
    public_value: Any,
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
    runner_authority: v217_runtime.RunnerFailureObservationAuthority,
    failure_dispatcher: v217_runtime.ArtifactBackedExitDispatcher,
) -> TerminalProjection:
    if outcome.terminal in models.FAILURE_TERMINAL_KINDS:
        observation = runner_authority.get(outcome.record.invocation_id)
        evidence = v217_runtime._evidence(observation)  # noqa: SLF001
        decision = failure_dispatcher.dispatch(evidence)
        if decision.terminal_kind != outcome.terminal:
            raise UnboundExecutionFailure("failure dispatcher differs from Runner terminal")
        projection = TerminalProjection(
            terminal_kind=cast(models.TerminalKind, decision.terminal_kind),
            terminal_source="v26_218_source_bound_failure",
            evidence=evidence,
            decision=decision,
        )
    else:
        evidence = _main_evidence(
            outcome=outcome,
            job_id=job_id,
            public_value=public_value,
            records=records,
        )
        dispatcher = v213_runtime.ObservationDerivedTerminalDispatcher(
            prepared.bindings.main_dispatcher
        )
        decision = dispatcher.dispatch(evidence)
        if decision.terminal_kind not in models.MAIN_TERMINAL_KINDS:
            raise UnboundExecutionFailure("v26.213 outer evidence surface is forbidden")
        projection = TerminalProjection(
            terminal_kind=cast(models.TerminalKind, decision.terminal_kind),
            terminal_source="current_state_runner_observation",
            evidence=evidence,
            decision=decision,
        )
    policies = {
        item.terminal_kind: item.policy_id
        for item in prepared.bindings.terminal_registry.policies
        if item.registration_status == "reachable"
    }
    if policies.get(projection.terminal_kind) != getattr(
        projection.decision, "terminal_policy_id", None
    ):
        raise UnboundExecutionFailure("derived terminal lacks exact v26.195 policy")
    return projection


def _payload_write(root: Path, relative: str, value: Any) -> tuple[str, int]:
    payload = _encoded(value)
    _durable_write_no_replace(root / relative, payload)
    if (root / relative).read_bytes() != payload:
        raise UnboundExecutionFailure("persisted layer bytes differ")
    return _sha_bytes(payload), len(payload)


def _persist_terminal_chain(
    *,
    prepared: PreparedExecution,
    run_start: models.RunStartReceipt,
    job: v209_models.ExecutableDevelopmentJob,
    job_ordinal: int,
    projection: TerminalProjection,
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
    provider_calls: tuple[models.ProviderCallDescriptor, ...],
    failure_dispatcher: v217_runtime.ArtifactBackedExitDispatcher,
) -> models.JobExecutionRecord:
    if projection.terminal_source == "current_state_runner_observation":
        rederived = v213_runtime.ObservationDerivedTerminalDispatcher(
            prepared.bindings.main_dispatcher
        ).dispatch(cast(v213_models.ObservedEvidence, projection.evidence))
        persistence_binding_id = prepared.bindings.main_persistence.binding_id
    else:
        v218_runtime.ExactRegistryComplementAuthority(
            registry=prepared.bindings.terminal_registry,
            expected_binding=prepared.bindings.failure_complement,
        ).admit(prepared.bindings.failure_complement)
        rederived = failure_dispatcher.dispatch(
            cast(v217_models.AuthenticatedTypedFailureEvidence, projection.evidence)
        )
        persistence_binding_id = prepared.bindings.failure_persistence.binding_id
    if models.canonical_bytes(rederived) != models.canonical_bytes(projection.decision):
        raise UnboundExecutionFailure("terminal decision rederivation differs before Raw")
    safe = _safe(job.job_id)
    call_ids = tuple(item.descriptor_id for item in provider_calls)
    evidence_payload = projection.evidence.model_dump(mode="json", warnings=False)
    decision_payload = projection.decision.model_dump(mode="json", warnings=False)
    raw_relative = f"evidence/raw/{safe}.json"
    raw_payload = {
        "run_start_receipt_id": run_start.receipt_id,
        "authorization_id": prepared.authorization.authorization_id,
        "job_id": job.job_id,
        "job_ordinal": job_ordinal,
        "raw_namespace": job.raw_namespace,
        "terminal_source": projection.terminal_source,
        "persistence_binding_id": persistence_binding_id,
        "observed_evidence": evidence_payload,
        "derived_terminal_decision": decision_payload,
        "invocation_records": tuple(
            item.model_dump(mode="json", warnings=False) for item in records
        ),
        "provider_call_descriptor_ids": call_ids,
        "formal_empirical_row": True,
        "schema_version": models.SCHEMA_VERSION,
    }
    raw_sha, raw_bytes = _payload_write(prepared.output_dir, raw_relative, raw_payload)
    raw = models.make_identity(
        models.RawExecutionDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "job_id": job.job_id,
            "namespace_id": job.raw_namespace,
            "relative_path": raw_relative,
            "terminal_kind": projection.terminal_kind,
            "terminal_source": projection.terminal_source,
            "provider_call_descriptor_ids": call_ids,
            "payload_sha256": raw_sha,
            "payload_byte_count": raw_bytes,
            "persisted_sequence": 0,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_raw_descriptor:",
    )
    result_relative = f"evidence/result/{safe}.json"
    qualified = bool(
        isinstance(projection.evidence, v213_models.CompletedRunnerEvidence)
        and projection.evidence.qualified_valid
    )
    result_payload = {
        "run_start_receipt_id": run_start.receipt_id,
        "job_id": job.job_id,
        "result_namespace": job.result_namespace,
        "raw_descriptor": raw.model_dump(mode="json", warnings=False),
        "terminal_kind": projection.terminal_kind,
        "qualified_valid": qualified,
        "formal_empirical_row": True,
        "schema_version": models.SCHEMA_VERSION,
    }
    result_sha, result_bytes = _payload_write(prepared.output_dir, result_relative, result_payload)
    result = models.make_identity(
        models.ResultDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "job_id": job.job_id,
            "namespace_id": job.result_namespace,
            "relative_path": result_relative,
            "terminal_kind": projection.terminal_kind,
            "raw_descriptor_id": raw.descriptor_id,
            "raw_namespace_id": raw.namespace_id,
            "raw_persisted_sequence": raw.persisted_sequence,
            "payload_sha256": result_sha,
            "payload_byte_count": result_bytes,
            "persisted_sequence": 1,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_result_descriptor:",
    )
    trace_relative = f"evidence/trace/{safe}.json"
    trace_payload = {
        "run_start_receipt_id": run_start.receipt_id,
        "job_id": job.job_id,
        "trace_namespace": job.trace_namespace,
        "raw_descriptor": raw.model_dump(mode="json", warnings=False),
        "result_descriptor": result.model_dump(mode="json", warnings=False),
        "invocation_records": tuple(
            item.model_dump(mode="json", warnings=False) for item in records
        ),
        "provider_calls": tuple(
            item.model_dump(mode="json", warnings=False) for item in provider_calls
        ),
        "terminal_kind": projection.terminal_kind,
        "formal_empirical_row": True,
        "schema_version": models.SCHEMA_VERSION,
    }
    trace_sha, trace_bytes = _payload_write(prepared.output_dir, trace_relative, trace_payload)
    trace = models.make_identity(
        models.TraceDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "job_id": job.job_id,
            "namespace_id": job.trace_namespace,
            "relative_path": trace_relative,
            "terminal_kind": projection.terminal_kind,
            "raw_descriptor_id": raw.descriptor_id,
            "raw_namespace_id": raw.namespace_id,
            "result_descriptor_id": result.descriptor_id,
            "result_namespace_id": result.namespace_id,
            "result_persisted_sequence": result.persisted_sequence,
            "provider_call_descriptor_ids": call_ids,
            "payload_sha256": trace_sha,
            "payload_byte_count": trace_bytes,
            "persisted_sequence": 2,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_trace_descriptor:",
    )
    outcome_relative = f"evidence/outcome/{safe}.json"
    outcome_payload = {
        "run_start_receipt_id": run_start.receipt_id,
        "job_id": job.job_id,
        "outcome_namespace": job.outcome_namespace,
        "trace_descriptor": trace.model_dump(mode="json", warnings=False),
        "terminal_kind": projection.terminal_kind,
        "qualified_valid": qualified,
        "formal_empirical_row": True,
        "schema_version": models.SCHEMA_VERSION,
    }
    outcome_sha, outcome_bytes = _payload_write(
        prepared.output_dir, outcome_relative, outcome_payload
    )
    outcome = models.make_identity(
        models.OutcomeDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "job_id": job.job_id,
            "namespace_id": job.outcome_namespace,
            "relative_path": outcome_relative,
            "terminal_kind": projection.terminal_kind,
            "trace_descriptor_id": trace.descriptor_id,
            "trace_namespace_id": trace.namespace_id,
            "trace_persisted_sequence": trace.persisted_sequence,
            "payload_sha256": outcome_sha,
            "payload_byte_count": outcome_bytes,
            "persisted_sequence": 3,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_outcome_descriptor:",
    )
    checkpoint_relative = f"checkpoints/job_{job_ordinal:03d}.json"
    checkpoint_payload = {
        "run_start_receipt_id": run_start.receipt_id,
        "authorization_id": prepared.authorization.authorization_id,
        "job_id": job.job_id,
        "job_ordinal": job_ordinal,
        "outcome_descriptor": outcome.model_dump(mode="json", warnings=False),
        "terminal_kind": projection.terminal_kind,
        "formal_empirical_row": True,
        "schema_version": models.SCHEMA_VERSION,
    }
    checkpoint_sha, checkpoint_bytes = _payload_write(
        prepared.output_dir, checkpoint_relative, checkpoint_payload
    )
    checkpoint = models.make_identity(
        models.CheckpointDescriptor,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "job_id": job.job_id,
            "job_ordinal": job_ordinal,
            "relative_path": checkpoint_relative,
            "terminal_kind": projection.terminal_kind,
            "outcome_descriptor_id": outcome.descriptor_id,
            "outcome_namespace_id": outcome.namespace_id,
            "outcome_persisted_sequence": outcome.persisted_sequence,
            "payload_sha256": checkpoint_sha,
            "payload_byte_count": checkpoint_bytes,
            "persisted_sequence": 4,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_checkpoint_descriptor:",
    )
    return models.make_identity(
        models.JobExecutionRecord,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "job_id": job.job_id,
            "job_ordinal": job_ordinal,
            "terminal_kind": projection.terminal_kind,
            "terminal_source": projection.terminal_source,
            "provider_calls": provider_calls,
            "raw": raw,
            "result": result,
            "trace": trace,
            "outcome": outcome,
            "checkpoint": checkpoint,
        },
        field="record_id",
        prefix="finance_v26_224_online_job_execution_record:",
    )


def _failure_record(
    *,
    prepared: PreparedExecution,
    run_start: models.RunStartReceipt,
    job_id: str,
    job_ordinal: int,
    error: BaseException,
    provider_calls: tuple[models.ProviderCallDescriptor, ...],
) -> models.JobFailureRecord:
    provider_failed = any(item.status != "succeeded" for item in provider_calls)
    return models.make_identity(
        models.JobFailureRecord,
        {
            "run_start_receipt_id": run_start.receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "job_id": job_id,
            "job_ordinal": job_ordinal,
            "failure_kind": ("unbound_provider_failure" if provider_failed else "host_failure"),
            "error_sha256": _sha_bytes(
                f"{type(error).__module__}:{type(error).__qualname__}:{error}".encode()
            ),
            "provider_calls": provider_calls,
        },
        field="record_id",
        prefix="finance_v26_224_job_failure_record:",
    )


def _execute_job(
    *,
    prepared: PreparedExecution,
    run_start: models.RunStartReceipt,
    job: v209_models.ExecutableDevelopmentJob,
    job_ordinal: int,
    client: ExactRequestBodyDeepSeekClient,
) -> models.JobExecutionRecord | models.JobFailureRecord:
    transport: LiveV209Transport | None = None
    try:
        authority_root = prepared.output_dir / "source_authority" / _safe(job.job_id)
        source_exit, runner_authority, failure_dispatcher = _failure_runtime(
            prepared=prepared, job_id=job.job_id, root=authority_root
        )
        journal = ProviderJournal(root=prepared.output_dir, run_start=run_start, job_id=job.job_id)
        transport = LiveV209Transport(
            source_exit_authority=source_exit,
            client=client,
            journal=journal,
            job_id=job.job_id,
        )
        runner = _online_runner(
            prepared=prepared,
            transport=transport,
            source_exit=source_exit,
            runner_authority=runner_authority,
        )
        context = v209._context_for_job(  # noqa: SLF001
            job=job,
            parents=prepared.frozen_parents,
            prepared=prepared.runtime,
        )
        state = frozen_runtime._initialize(context)  # noqa: SLF001
        records: list[v209_models.ExecutableInvocationRecord] = []
        invocation_index = 0
        projection: TerminalProjection | None = None
        while state.current_index < len(state.ordered_components):
            action = runner.invoke_action(job=job, invocation_index=invocation_index, state=state)
            invocation_index += 1
            records.append(action.record)
            if action.terminal is not None:
                projection = _derive_terminal(
                    prepared=prepared,
                    outcome=action,
                    job_id=job.job_id,
                    public_value=transport.last_response,
                    records=tuple(records),
                    runner_authority=runner_authority,
                    failure_dispatcher=failure_dispatcher,
                )
                break
            if action.record.action_accepted is True:
                continue
            if not isinstance(action.runtime_output, step_runtime.PublicTypedRejectionObservation):
                raise UnboundExecutionFailure(
                    "nonterminal Action rejection lacks public typed feedback"
                )
            correction = runner.invoke_correction(
                job=job, invocation_index=invocation_index, state=state
            )
            invocation_index += 1
            records.append(correction.record)
            if correction.terminal is not None:
                projection = _derive_terminal(
                    prepared=prepared,
                    outcome=correction,
                    job_id=job.job_id,
                    public_value=transport.last_response,
                    records=tuple(records),
                    runner_authority=runner_authority,
                    failure_dispatcher=failure_dispatcher,
                )
                break
            if correction.record.action_accepted is True:
                continue
            projection = _derive_terminal(
                prepared=prepared,
                outcome=correction,
                job_id=job.job_id,
                public_value=transport.last_response,
                records=tuple(records),
                runner_authority=runner_authority,
                failure_dispatcher=failure_dispatcher,
            )
            break
        if projection is None:
            final = runner.invoke_final(
                job=job,
                invocation_index=invocation_index,
                state=state,
                context=context,
            )
            records.append(final.record)
            projection = _derive_terminal(
                prepared=prepared,
                outcome=final,
                job_id=job.job_id,
                public_value=transport.last_response,
                records=tuple(records),
                runner_authority=runner_authority,
                failure_dispatcher=failure_dispatcher,
            )
        if len(transport.provider_calls) != len(records):
            raise UnboundExecutionFailure("Runner invocation and Provider-call counts differ")
        return _persist_terminal_chain(
            prepared=prepared,
            run_start=run_start,
            job=job,
            job_ordinal=job_ordinal,
            projection=projection,
            records=tuple(records),
            provider_calls=transport.provider_calls,
            failure_dispatcher=failure_dispatcher,
        )
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        calls = () if transport is None else transport.provider_calls
        return _failure_record(
            prepared=prepared,
            run_start=run_start,
            job_id=job.job_id,
            job_ordinal=job_ordinal,
            error=error,
            provider_calls=calls,
        )


def _load_env_key(package_root: Path, key: str) -> None:
    if os.environ.get(key):
        return
    candidates = (package_root.parent / ".env", package_root / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                os.environ[key] = value.strip().strip('"').strip("'")
                return
    _fail("credential.lookup", f"missing credential environment variable:{key}")


def _consume_authorization(
    *, prepared: PreparedExecution, source_identity: tuple[str, str]
) -> tuple[models.AuthorizationConsumptionReceipt, models.RunStartReceipt]:
    consumption = models.make_identity(
        models.AuthorizationConsumptionReceipt,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "external_authorization_id": (
                prepared.external_authorization.external_authorization_id
            ),
            "authorization_id": prepared.authorization.authorization_id,
            "authorization_bytes_sha256": _sha_bytes(prepared.authorization_file_bytes),
            "consumed_at_utc": _utc_now(),
        },
        field="receipt_id",
        prefix="finance_v26_224_authorization_consumption_receipt:",
    )
    _durable_write_no_replace(prepared.ledger_path, _encoded(consumption))
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _durable_write_no_replace(
        prepared.output_dir / "authorization_consumption_receipt.json",
        _encoded(consumption),
    )
    ledger_descriptor = {
        "authorization_id": prepared.authorization.authorization_id,
        "ledger_relative_path": prepared.ledger_path.relative_to(
            prepared.repository_root
        ).as_posix(),
        "ledger_sha256": _sha_file(prepared.ledger_path),
        "ledger_byte_count": prepared.ledger_path.stat().st_size,
        "receipt_id": consumption.receipt_id,
        "authorization_reusable": False,
        "schema_version": models.SCHEMA_VERSION,
    }
    _durable_write_no_replace(
        prepared.output_dir / "authorization_consumption_ledger_descriptor.json",
        _encoded(ledger_descriptor),
    )
    run_start = models.make_identity(
        models.RunStartReceipt,
        {
            "consumption_receipt_id": consumption.receipt_id,
            "preparation_id": prepared.preparation.preparation_id,
            "authorization_id": prepared.authorization.authorization_id,
            "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
            "execution_source_commit": source_identity[0],
            "execution_source_tree": source_identity[1],
            "started_at_utc": _utc_now(),
        },
        field="receipt_id",
        prefix="finance_v26_224_run_start_receipt:",
    )
    if prepared.ledger_path.read_bytes() != _encoded(consumption):
        _fail("ingress.ledger", "authorization consumption ledger bytes differ")
    _durable_write_no_replace(prepared.output_dir / "run_start_receipt.json", _encoded(run_start))
    return consumption, run_start


def _write_ingress_evidence(prepared: PreparedExecution) -> None:
    values: dict[str, bytes] = {
        "external_review.txt": prepared.external_review_bytes,
        "operator_authorization.txt": OPERATOR_DIRECTIVE.encode("utf-8"),
        "external_execution_authorization.json": _encoded(prepared.external_authorization),
        "v223_authorization_freeze.json": _encoded(prepared.v223_freeze),
        "execution_preparation.json": _encoded(prepared.preparation),
        "exact_v223_online_execution_authorization.json": (prepared.authorization_file_bytes),
        "v223_online_execution_composition_contract.json": _encoded(prepared.composition),
        "precredential_authorization_admission.json": _encoded(prepared.admission),
    }
    for name, payload in values.items():
        _durable_write_no_replace(prepared.output_dir / name, payload)


def _artifact_manifest(root: Path) -> models.ArtifactManifest:
    payloads = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != "execution_artifact_manifest.json"
    }
    return models.artifact_manifest(RUN_ID, payloads)


def execute(
    *,
    prepared: PreparedExecution,
    workers: int = MAX_WORKERS,
    client_factory: type[ExactRequestBodyDeepSeekClient] = ExactRequestBodyDeepSeekClient,
) -> models.ExecutionSummary:
    if workers < 1 or workers > 32:
        _fail("scope.workers", "v26.224 worker count must be in [1,32]")
    source_identity = _git_identity(prepared.repository_root)
    consumption, run_start = _consume_authorization(
        prepared=prepared, source_identity=source_identity
    )
    _write_ingress_evidence(prepared)
    _load_env_key(prepared.package_root, prepared.config.api_key_env)
    client = client_factory(prepared.config)
    jobs_by_id = {item.job_id: item for item in prepared.manifest.jobs}
    ordered_jobs = tuple(jobs_by_id[job_id] for job_id in prepared.authorization.exact_job_ids)
    outputs: dict[int, models.JobExecutionRecord | models.JobFailureRecord] = {}
    pending: dict[Future[models.JobExecutionRecord | models.JobFailureRecord], int] = {}
    next_ordinal = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while next_ordinal < min(workers, len(ordered_jobs)):
            ordinal = next_ordinal
            pending[
                pool.submit(
                    _execute_job,
                    prepared=prepared,
                    run_start=run_start,
                    job=ordered_jobs[ordinal],
                    job_ordinal=ordinal,
                    client=client,
                )
            ] = ordinal
            next_ordinal += 1
        while pending:
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                ordinal = pending.pop(future)
                output = future.result()
                outputs[ordinal] = output
                directory = (
                    "job_records"
                    if isinstance(output, models.JobExecutionRecord)
                    else "job_failures"
                )
                _durable_write_no_replace(
                    prepared.output_dir / directory / f"job_{ordinal:03d}.json",
                    _encoded(output),
                )
                if next_ordinal < len(ordered_jobs):
                    queued = next_ordinal
                    pending[
                        pool.submit(
                            _execute_job,
                            prepared=prepared,
                            run_start=run_start,
                            job=ordered_jobs[queued],
                            job_ordinal=queued,
                            client=client,
                        )
                    ] = queued
                    next_ordinal += 1
    if tuple(sorted(outputs)) != tuple(range(192)):
        _fail("execution.coverage", "exact 192-Job one-shot scheduling did not close")
    records = tuple(
        cast(models.JobExecutionRecord, outputs[index])
        for index in sorted(outputs)
        if isinstance(outputs[index], models.JobExecutionRecord)
    )
    failures = tuple(
        cast(models.JobFailureRecord, outputs[index])
        for index in sorted(outputs)
        if isinstance(outputs[index], models.JobFailureRecord)
    )
    all_calls = tuple(call for item in (*records, *failures) for call in item.provider_calls)
    terminal_partition = {kind: 0 for kind in models.TERMINAL_KINDS}
    for record in records:
        terminal_partition[record.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for failure in failures:
        failure_partition[failure.failure_kind] += 1
    status: Literal["completed", "incomplete"] = "completed" if not failures else "incomplete"
    summary = models.make_identity(
        models.ExecutionSummary,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "consumption_receipt_id": consumption.receipt_id,
            "run_start_receipt_id": run_start.receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_status": status,
            "records": records,
            "failure_records": failures,
            "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
            "completed_job_record_count": len(records),
            "failure_record_count": len(failures),
            "raw_count": len(records),
            "result_count": len(records),
            "trace_count": len(records),
            "outcome_count": len(records),
            "checkpoint_count": len(records),
            "terminal_partition": terminal_partition,
            "failure_partition": failure_partition,
            "provider_call_count": len(all_calls),
            "input_tokens": sum(item.input_tokens for item in all_calls),
            "output_tokens": sum(item.output_tokens for item in all_calls),
        },
        field="summary_id",
        prefix="finance_v26_224_execution_summary:",
    )
    _durable_write_no_replace(prepared.output_dir / "execution_summary.json", _encoded(summary))
    transition = models.make_identity(
        models.Transition,
        {
            "summary_id": summary.summary_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_status": summary.execution_status,
            "status": (
                "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
                if status == "completed"
                else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            ),
        },
        field="transition_id",
        prefix="finance_v26_224_transition:",
    )
    _durable_write_no_replace(
        prepared.output_dir / "prospective_transition.json", _encoded(transition)
    )
    artifact = _artifact_manifest(prepared.output_dir)
    _durable_write_no_replace(
        prepared.output_dir / "execution_artifact_manifest.json", _encoded(artifact)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    prepared = prepare_execution(
        repository_root=repository_root,
        output_dir=repository_root / OUTPUT_DIR,
        external_review_path=args.external_audit,
    )
    if args.prepare_only:
        print(models.canonical_bytes(prepared.preparation).decode("utf-8"))
        return
    summary = execute(prepared=prepared, workers=args.workers)
    print(models.canonical_bytes(summary).decode("utf-8"))


if __name__ == "__main__":
    main()
