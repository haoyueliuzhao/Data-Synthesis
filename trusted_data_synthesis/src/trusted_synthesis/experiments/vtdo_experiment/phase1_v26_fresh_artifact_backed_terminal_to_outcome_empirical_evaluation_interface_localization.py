# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.experiments.vtdo_experiment import (
    json_explicit_authoritative_execution_kernel as kernel,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_interface_localization_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight as v197,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution as v200,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution_models as v200_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_postrun_independent_audit_models as v201_models,
)

RUN_ID: Final = (
    "finance_v26_202_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_"
    "and_interface_localization_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V200_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_200_fresh_artifact_backed_terminal_to_outcome_exact_192_job_"
    "online_execution_v1_20260901"
)
V201_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_201_fresh_artifact_backed_terminal_to_outcome_postrun_"
    "independent_audit_v1_20260902"
)
V201_DECISION_ID: Final = (
    "finance_v26_201_postrun_independent_audit_decision:"
    "dbb4b76405df9b264679e987c9d75cce6d3375e0d82037323104e6b73b3587e9"
)
V201_BYTE_AUDIT_ID: Final = (
    "finance_v26_201_byte_reconstruction_audit:"
    "f2d6057508fbca3dc6e0939ac15817fbbab40cf9d1c687724aa0867ad24595d5"
)
V201_RESPONSE_AUDIT_ID: Final = (
    "finance_v26_201_response_interface_audit:"
    "afa82ffe7f7599a3a81dd98f6bff5836d3287ee006703415cc0f2262585d1690"
)
V201_ARTIFACT_MANIFEST_ID: Final = (
    "finance_v26_201_artifact_manifest:"
    "9c9e6d2adb452a24a07e549dc4f42aedae6305c7c0bc1d14891856bae272e73e"
)
V201_ARTIFACT_ROOT: Final = (
    "finance_v26_201_artifact_root:c71a937d2c444ca1fbca14cc3fc1a989e83a16690c2ff6d5579cee80f57bcbe8"
)
EXTERNAL_AUDIT_SHA256: Final = "b534d14cf53d5ed6fbb65f59647f8e244e220f3ea160f85b74ac47da2724034e"
EXTERNAL_AUDIT_BYTES: Final = 10_706
V195_AUTHORITY_SOURCE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/core/task/"
    "fresh_artifact_backed_outcome_authority.py"
)
ACTION_FIELDS: Final = ("action_id", "decision_kind", "protocol", "state_id")


class V202Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V202Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


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


def _git_identity(repository_root: Path) -> tuple[str, str]:
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
    if len(commit) != 40 or len(tree) != 40:
        _fail("source.identity", "v26.202 Git source identity differs")
    return commit, tree


def _authorization(audit_path: Path) -> tuple[models.ExternalAuditAuthorization, bytes]:
    payload = audit_path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        _fail("authorization", "v26.202 external Audit bytes differ")
    return (
        cast(
            models.ExternalAuditAuthorization,
            models.make_identity(
                models.ExternalAuditAuthorization,
                {
                    "audit_sha256": EXTERNAL_AUDIT_SHA256,
                    "audit_byte_count": EXTERNAL_AUDIT_BYTES,
                    "audit_decision": (
                        "v26_200_v26_201_accepted_with_estimand_correction_and_zero_provider_"
                        "exact_set_evaluation_interface_localization_only_authorized"
                    ),
                },
                field="authorization_id",
                prefix="finance_v26_202_external_audit_authorization:",
            ),
        ),
        payload,
    )


def _v201_freeze(
    package_root: Path,
    authorization_id: str,
) -> tuple[
    models.V201AuditFreeze,
    v201_models.ByteReconstructionAudit,
    v201_models.ResponseInterfaceAudit,
]:
    root = package_root / V201_DIR
    files = tuple(path for path in root.rglob("*") if path.is_file())
    if len(files) != 8 or sum(path.stat().st_size for path in files) != 285_649:
        _fail("v201.geometry", "v26.201 exact formal directory geometry differs")
    manifest = v201_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    members = {item.relative_path: item for item in manifest.members}
    actual = {
        path.relative_to(root).as_posix(): path
        for path in files
        if path.name != "artifact_manifest.json"
    }
    if (
        manifest.manifest_id != V201_ARTIFACT_MANIFEST_ID
        or manifest.artifact_root != V201_ARTIFACT_ROOT
        or set(members) != set(actual)
        or any(
            _sha256(actual[name]) != item.sha256 or actual[name].stat().st_size != item.byte_count
            for name, item in members.items()
        )
    ):
        _fail("v201.artifact", "v26.201 exact Artifact Manifest or bytes differ")
    decision = v201_models.PostrunIndependentAuditDecision.model_validate(
        _load(root / "independent_audit_decision.json")
    )
    byte_audit = v201_models.ByteReconstructionAudit.model_validate(
        _load(root / "byte_reconstruction_audit.json")
    )
    response = v201_models.ResponseInterfaceAudit.model_validate(
        _load(root / "response_interface_audit.json")
    )
    source = _load(root / "source_identity.json")
    if (
        decision.decision_id != V201_DECISION_ID
        or byte_audit.audit_id != V201_BYTE_AUDIT_ID
        or response.audit_id != V201_RESPONSE_AUDIT_ID
        or source
        != {
            "source_commit": "42d071da62bfc538e555fbb4200c02627113913a",
            "source_tree": "87ca269b075f629d9b36c21764536c5953a4ecb7",
        }
    ):
        _fail("v201.identity", "v26.201 exact decision or source identity differs")
    freeze = cast(
        models.V201AuditFreeze,
        models.make_identity(
            models.V201AuditFreeze,
            {
                "authorization_id": authorization_id,
                "v201_decision_id": decision.decision_id,
                "v201_byte_reconstruction_audit_id": byte_audit.audit_id,
                "v201_response_interface_audit_id": response.audit_id,
                "v201_artifact_manifest_id": manifest.manifest_id,
                "v201_artifact_root": manifest.artifact_root,
                "v201_source_commit": source["source_commit"],
                "v201_source_tree": source["source_tree"],
            },
            field="freeze_id",
            prefix="finance_v26_202_v201_audit_freeze:",
        ),
    )
    return freeze, byte_audit, response


def _load_records(v200_root: Path) -> tuple[v200_models.OnlineJobExecutionRecord, ...]:
    paths = tuple(sorted((v200_root / "job_records").glob("*.json")))
    if len(paths) != 192:
        _fail("evidence.denominator", "exact empirical record denominator differs")
    return tuple(v200_models.OnlineJobExecutionRecord.model_validate(_load(path)) for path in paths)


def _strict_empirical_rows(
    *,
    records: Sequence[v200_models.OnlineJobExecutionRecord],
    expected_job_ids: tuple[str, ...],
    v201_rows: dict[str, v201_models.IndependentJobAuditRow],
    v200_root: Path,
    terminal_registry: authority.FreshTerminalRegistry,
    raw_contract: authority.FreshRawExecutionDescriptorContract,
    result_contract: authority.FreshJobResultDescriptorContract,
    trace_contract: authority.FreshJobBoundAttemptTraceContract,
    outcome_contract: authority.FreshOutcomeRowContract,
) -> tuple[models.EmpiricalEvidenceSetRow, ...]:
    if len(records) != 192:
        _fail("evidence.denominator", "exact empirical record denominator differs")
    strict = tuple(
        v200_models.OnlineJobExecutionRecord.model_validate(
            item.model_dump(mode="json", warnings=False)
        )
        for item in records
    )
    by_job: dict[str, v200_models.OnlineJobExecutionRecord] = {}
    for item in strict:
        if item.job_id in by_job:
            _fail("evidence.duplicate", "exact empirical evidence repeats a Job")
        by_job[item.job_id] = item
    if set(by_job) != set(expected_job_ids) or set(v201_rows) != set(expected_job_ids):
        _fail("evidence.job_set", "exact empirical Job set differs from Manifest")
    reachable = {
        item.terminal_kind
        for item in terminal_registry.policies
        if item.registration_status == "reachable"
    }
    output: list[models.EmpiricalEvidenceSetRow] = []
    for job_id in expected_job_ids:
        record = by_job[job_id]
        bundle = record.bundle
        audited = v201_rows[job_id]
        raw_path = v200_root / "fresh_outcome_artifacts" / bundle.raw.artifact_relative_path
        result_path = v200_root / "fresh_outcome_artifacts" / bundle.result.artifact_relative_path
        raw_bytes = raw_path.read_bytes()
        result_bytes = result_path.read_bytes()
        raw_payload = v200_models.EmpiricalIntegratedRawPayload.model_validate_json(raw_bytes)
        result_payload = authority.FreshJobResultPayload.model_validate_json(result_bytes)
        if (
            bundle.raw.descriptor_contract_id != raw_contract.contract_id
            or bundle.result.descriptor_contract_id != result_contract.contract_id
            or bundle.trace.trace_contract_id != trace_contract.contract_id
            or bundle.row.outcome_contract_id != outcome_contract.contract_id
            or bundle.raw.evidence_kind != "empirical_execution"
            or bundle.result.evidence_kind != "empirical_execution"
            or bundle.trace.evidence_kind != "empirical_execution"
            or bundle.row.evidence_kind != "empirical_execution"
            or not bundle.row.formal_empirical_row
            or record.terminal_kind not in reachable
            or raw_payload.terminal_kind != record.terminal_kind
            or result_payload.terminal_kind != record.terminal_kind
            or bundle.row.terminal_kind != record.terminal_kind
            or _sha256_bytes(raw_bytes) != bundle.raw.artifact_sha256
            or len(raw_bytes) != bundle.raw.artifact_byte_count
            or _sha256_bytes(result_bytes) != bundle.result.artifact_sha256
            or len(result_bytes) != bundle.result.artifact_byte_count
            or bundle.result.raw_execution_id != bundle.raw.raw_execution_id
            or bundle.trace.raw_execution_id != bundle.raw.raw_execution_id
            or bundle.trace.result_id != bundle.result.result_id
            or bundle.row.raw_execution_id != bundle.raw.raw_execution_id
            or bundle.row.result_id != bundle.result.result_id
            or bundle.row.trace_id != bundle.trace.trace_id
            or audited.raw_execution_id != bundle.raw.raw_execution_id
            or audited.result_id != bundle.result.result_id
            or audited.trace_id != bundle.trace.trace_id
            or audited.outcome_row_id != bundle.row.row_id
            or audited.exact_action_abi_crossed
            or bundle.row.final_qualified_valid is True
        ):
            _fail("evidence.parent", f"exact empirical Bundle differs:{job_id}")
        output.append(
            cast(
                models.EmpiricalEvidenceSetRow,
                models.make_identity(
                    models.EmpiricalEvidenceSetRow,
                    {
                        "job_id": job_id,
                        "package_id": record.package_id,
                        "replica_index": record.replica_index,
                        "terminal_kind": record.terminal_kind,
                        "raw_execution_id": bundle.raw.raw_execution_id,
                        "result_id": bundle.result.result_id,
                        "trace_id": bundle.trace.trace_id,
                        "outcome_row_id": bundle.row.row_id,
                    },
                    field="evaluation_row_id",
                    prefix="finance_v26_202_empirical_evidence_set_row:",
                ),
            )
        )
    return tuple(output)


def _evaluation(
    *,
    repository_root: Path,
    authorization: models.ExternalAuditAuthorization,
    freeze: models.V201AuditFreeze,
    byte_audit: v201_models.ByteReconstructionAudit,
    records: Sequence[v200_models.OnlineJobExecutionRecord],
    v200_root: Path,
) -> tuple[models.ExactEmpiricalEvidenceSetEvaluation, tuple[Any, ...]]:
    parents = v197._load_parents(repository_root)  # noqa: SLF001
    catalog, manifest, runner, execution = cast(tuple[Any, ...], parents[:4])
    registry, raw_contract, result_contract = cast(tuple[Any, ...], parents[4:7])
    trace_contract, outcome_contract, evaluator_contract = cast(tuple[Any, ...], parents[7:10])
    authority._validated_parents(  # noqa: SLF001
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
    )
    evaluator_source = inspect.getsource(authority.evaluate_fresh_evidence_set).encode("utf-8")
    if (
        'expected_evidence_kind != "scripted_preflight_control"' not in evaluator_source.decode()
        or evaluator_contract.empirical_evaluation_authorized
        or evaluator_contract.empirical_estimate_materialized
    ):
        _fail("evaluator.compatibility", "frozen v26.195 empirical compatibility fact differs")
    audited_rows = {item.job_id: item for item in byte_audit.rows}
    rows = _strict_empirical_rows(
        records=records,
        expected_job_ids=manifest.expected_job_ids,
        v201_rows=audited_rows,
        v200_root=v200_root,
        terminal_registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
    )
    terminal_counts = Counter(item.terminal_kind for item in rows)
    if terminal_counts != Counter(
        {"first_response_abi_invalid": 188, "thinking_integrity_failure": 4}
    ):
        _fail("evaluation.partition", "exact empirical terminal partition differs")
    evaluation = cast(
        models.ExactEmpiricalEvidenceSetEvaluation,
        models.make_identity(
            models.ExactEmpiricalEvidenceSetEvaluation,
            {
                "authorization_id": authorization.authorization_id,
                "v201_freeze_id": freeze.freeze_id,
                "frozen_v195_evaluator_contract_id": evaluator_contract.contract_id,
                "frozen_v195_evaluator_source_sha256": _sha256_bytes(evaluator_source),
                "rows": rows,
            },
            field="evaluation_id",
            prefix="finance_v26_202_exact_empirical_evidence_set_evaluation:",
        ),
    )
    return evaluation, parents


def _request_identity(
    *,
    prepared: v200.PreparedOnlineExecution,
    job_id: str,
    prompt: str,
    config: v200.AgentModelConfig,
) -> tuple[kernel.PreparedKernelRequest, dict[str, Any]]:
    body = kernel.make_stage_one_request_body(config, prompt)
    body_sha = _sha256_bytes(_canonical_bytes(body))
    certificate = kernel.certify_stage_one_request_pre_call(
        config=config,
        prompt=prompt,
        request_kind="semantic_proposal",
        phase="primary",
    )
    if certificate.canonical_request_body_sha256 != body_sha:
        _fail("prompt.request_body", "reconstructed request body differs from certificate")
    resource = cast(
        kernel.KernelResourceCertificate,
        models.make_identity(
            kernel.KernelResourceCertificate,
            {
                "execution_contract_id": prepared.execution.contract_id,
                "job_id": job_id,
                "logical_request_index": 0,
                "prompt_sha256": certificate.prompt_sha256,
                "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                "provider_calls_before": 0,
                "transport_invocations_before": 0,
            },
            field="certificate_id",
            prefix="authoritative_kernel_resource_certificate:",
        ),
    )
    dynamic = cast(
        kernel.KernelDynamicRequestCertificate,
        models.make_identity(
            kernel.KernelDynamicRequestCertificate,
            {
                "execution_contract_id": prepared.execution.contract_id,
                "runner_id": prepared.runner.runner_id,
                "manifest_id": prepared.manifest.manifest_id,
                "job_id": job_id,
                "logical_request_index": 0,
                "prompt_kind": "action",
                "request_kind": "semantic_proposal",
                "public_attempt_phase": "primary",
                "prompt_sha256": certificate.prompt_sha256,
                "request_body_sha256": body_sha,
                "request_binding_certificate_id": certificate.certificate_id,
                "resource_certificate_id": resource.certificate_id,
            },
            field="certificate_id",
            prefix="authoritative_kernel_dynamic_request_certificate:",
        ),
    )
    request = cast(
        kernel.PreparedKernelRequest,
        models.make_identity(
            kernel.PreparedKernelRequest,
            {
                "job_id": job_id,
                "logical_request_index": 0,
                "prompt_kind": "action",
                "rendered_prompt": prompt,
                "canonical_request_body_sha256": body_sha,
                "request_binding_certificate": certificate,
                "resource_certificate": resource,
                "dynamic_certificate": dynamic,
            },
            field="preparation_id",
            prefix="authoritative_kernel_prepared_request:",
        ),
    )
    return request, body


def _field_sets(
    semantic_task: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    answer_fields = tuple(sorted(str(item) for item in semantic_task["answer_fields"]))
    output_fields = semantic_task["operator_output_fields"]
    if not isinstance(output_fields, dict):
        _fail("prompt.schema", "operator-output field registry differs")
    field_sets = tuple(
        sorted({tuple(sorted(str(item) for item in values)) for values in output_fields.values()})
    )
    return answer_fields, field_sets


def _assert_prompt_match(rendered: str, envelope: dict[str, Any]) -> None:
    telemetry = envelope.get("telemetry")
    if not isinstance(telemetry, dict) or telemetry.get("request_hash") != _sha256_bytes(
        rendered.encode("utf-8")
    ):
        _fail("prompt.hash", "reconstructed first Prompt request hash differs")


def _localization(
    *,
    repository_root: Path,
    output_dir: Path,
    authorization: models.ExternalAuditAuthorization,
    evaluation: models.ExactEmpiricalEvidenceSetEvaluation,
    records: Sequence[v200_models.OnlineJobExecutionRecord],
    v200_root: Path,
) -> models.FirstResponseInterfaceLocalization:
    prepared = v200.prepare_execution(
        repository_root=repository_root,
        output_dir=output_dir,
        external_audit_path=v200_root / "external_v26_199_execution_audit.txt",
    )
    profile_payload = _load(prepared.package_root / v200.MODEL_PROFILE_PATH)
    config = v200.require_stage_one_model_config(
        v200.AgentModelConfig.model_validate(profile_payload.get("model", profile_payload))
    )
    record_map = {item.job_id: item for item in records}
    prompt_rows: list[models.FirstPromptLocalizationRow] = []
    answer_count: Counter[str] = Counter()
    operation_count: Counter[str] = Counter()
    action_count: Counter[str] = Counter()
    candidate_count: Counter[str] = Counter()
    actual_count: Counter[str] = Counter()
    response_shapes: Counter[tuple[str, ...]] = Counter()
    for job_id in prepared.authorization.exact_job_ids:
        parents = prepared.job_parents[job_id]
        context = v200.frozen_runtime.prepare_job(
            parents.runtime_job,
            prepared.runtime.runtime_catalog,
        )
        state = v200.frozen_runtime._initialize(context)  # noqa: SLF001
        public_prompt = v200.step_runtime.render_next_prompt(state)
        core = v200.v192._action_core(public_prompt, prepared.runtime)  # noqa: SLF001
        rendered = v200.v192._render_prompt(  # noqa: SLF001
            prompt_kind="action",
            core=core,
            contract=prepared.prompt_contract,
            schema=prepared.prompt_schema,
        )
        request, body = _request_identity(
            prepared=prepared,
            job_id=job_id,
            prompt=rendered,
            config=config,
        )
        envelope_path = v200_root / "kernel_artifacts" / "envelopes" / _safe(job_id) / "000.json"
        envelope: dict[str, Any] | None = None
        observed_prompt_sha: str
        if envelope_path.is_file():
            envelope = _load(envelope_path)
            _assert_prompt_match(rendered, envelope)
            observed_prompt_sha = envelope["telemetry"]["request_hash"]
            if (
                envelope.get("preparation_id") != request.preparation_id
                or envelope.get("dynamic_certificate_id")
                != request.dynamic_certificate.certificate_id
            ):
                _fail(
                    "prompt.request_identity",
                    f"reconstructed request identity differs:{job_id}",
                )
        else:
            record = record_map[job_id]
            raw_path = (
                v200_root / "fresh_outcome_artifacts" / record.bundle.raw.artifact_relative_path
            )
            raw = v200_models.EmpiricalIntegratedRawPayload.model_validate_json(
                raw_path.read_bytes()
            )
            if (
                record.terminal_kind != "thinking_integrity_failure"
                or len(raw.provider_telemetry) != 1
            ):
                _fail("prompt.envelope", f"unexpected absent envelope:{job_id}")
            observed_prompt_sha = str(raw.provider_telemetry[0]["request_hash"])
            if observed_prompt_sha != _sha256_bytes(rendered.encode("utf-8")):
                _fail("prompt.hash", "reconstructed first Prompt request hash differs")
        if body.get("messages") != [{"role": "user", "content": rendered}]:
            _fail("prompt.request_body", f"reconstructed user message differs:{job_id}")
        projection_path = (
            v200_root / "kernel_artifacts" / "projections" / _safe(job_id) / "000.json"
        )
        shape: tuple[str, ...] | None = None
        if projection_path.is_file():
            projection = _load(projection_path)
            payload = projection.get("payload")
            if not isinstance(payload, dict):
                _fail("prompt.response", "v26.200 public response payload differs")
            shape = tuple(sorted(str(item) for item in payload))
            response_shapes[shape] += 1
            actual_count.update(shape)
        prompt_payload = json.loads(rendered)
        public = prompt_payload["prompt_core"]["public_prompt"]
        semantic = public["task"]["semantic_task"]
        response_abi = prompt_payload["prompt_core"]["response_abi"]
        answer_fields, operation_sets = _field_sets(semantic)
        candidate_fields = tuple(
            sorted({str(key) for item in public["candidates"] for key in item})
        )
        direct_action = tuple(sorted(set(response_abi) - {"grammar_id"}))
        if direct_action != ("decision_kind", "protocol", "state_id") or (
            "action_id" not in candidate_fields
        ):
            _fail("prompt.action_abi", "direct response ABI or Candidate Action ID differs")
        answer_count.update(set(answer_fields))
        operation_count.update({field for fields in operation_sets for field in fields})
        action_count.update(direct_action)
        candidate_count.update(set(candidate_fields))
        answer_offset = rendered.index('"answer_fields"')
        operation_offset = rendered.index('"operator_output_fields"')
        candidate_offset = rendered.index('"candidates"')
        response_offset = rendered.index('"response_abi"')
        provider_section = rendered.index('"provider_output_protocol"')
        instruction_offset = rendered.index('"instruction"', provider_section)
        row = cast(
            models.FirstPromptLocalizationRow,
            models.make_identity(
                models.FirstPromptLocalizationRow,
                {
                    "job_id": job_id,
                    "package_id": record_map[job_id].package_id,
                    "replica_index": record_map[job_id].replica_index,
                    "prompt_sha256": _sha256_bytes(rendered.encode("utf-8")),
                    "actual_request_sha256": observed_prompt_sha,
                    "prompt_byte_count": len(rendered.encode("utf-8")),
                    "prepared_request_id": request.preparation_id,
                    "observed_prepared_request_id": (
                        envelope["preparation_id"] if envelope is not None else None
                    ),
                    "dynamic_certificate_id": request.dynamic_certificate.certificate_id,
                    "observed_dynamic_certificate_id": (
                        envelope["dynamic_certificate_id"] if envelope is not None else None
                    ),
                    "persisted_envelope_present": envelope is not None,
                    "prepared_request_identity_match": (True if envelope is not None else None),
                    "dynamic_certificate_identity_match": (True if envelope is not None else None),
                    "response_payload_key_shape": shape,
                    "answer_fields": answer_fields,
                    "operation_output_field_sets": operation_sets,
                    "candidate_fields": candidate_fields,
                    "response_matches_answer_schema": shape == answer_fields,
                    "response_matches_operation_output_schema": shape in operation_sets,
                    "answer_schema_offset": answer_offset,
                    "operation_output_schema_offset": operation_offset,
                    "candidate_schema_offset": candidate_offset,
                    "response_abi_offset": response_offset,
                    "provider_instruction_offset": instruction_offset,
                },
                field="row_id",
                prefix="finance_v26_202_first_prompt_localization_row:",
            ),
        )
        prompt_rows.append(row)
    all_fields = tuple(
        sorted(
            set(actual_count)
            | set(answer_count)
            | set(operation_count)
            | set(ACTION_FIELDS)
            | set(candidate_count)
        )
    )
    field_sources: list[models.FieldSourceRow] = []
    for field in all_fields:
        in_task = answer_count[field] > 0 or operation_count[field] > 0
        in_action = action_count[field] > 0
        in_candidate = candidate_count[field] > 0
        if in_task and (in_action or in_candidate):
            source = "mixed_visible_sources"
        elif in_task:
            source = "task_answer_or_operation_output"
        elif in_action:
            source = "action_abi"
        elif in_candidate:
            source = "candidate_representation"
        else:
            source = "unlocated_visible_field"
        field_sources.append(
            cast(
                models.FieldSourceRow,
                models.make_identity(
                    models.FieldSourceRow,
                    {
                        "field_name": field,
                        "actual_response_count": actual_count[field],
                        "answer_schema_prompt_count": answer_count[field],
                        "operation_output_schema_prompt_count": operation_count[field],
                        "action_abi_prompt_count": action_count[field],
                        "candidate_representation_prompt_count": candidate_count[field],
                        "source_classification": source,
                    },
                    field="field_source_id",
                    prefix="finance_v26_202_field_source_row:",
                ),
            )
        )
    rows = tuple(sorted(prompt_rows, key=lambda item: item.job_id))
    answer_matches = sum(item.response_matches_answer_schema for item in rows)
    operation_matches = sum(item.response_matches_operation_output_schema for item in rows)
    either_matches = sum(
        item.response_matches_answer_schema or item.response_matches_operation_output_schema
        for item in rows
    )
    required_sources = {item.field_name: item for item in field_sources}
    if (
        response_shapes[("difference", "higher_ref")] != 128
        or response_shapes[("value",)] != 39
        or either_matches < 167
        or any(
            required_sources[name].source_classification != "task_answer_or_operation_output"
            for name in ("difference", "higher_ref", "value")
        )
    ):
        _fail("prompt.localization", "registered competing-Schema overlap differs")
    return cast(
        models.FirstResponseInterfaceLocalization,
        models.make_identity(
            models.FirstResponseInterfaceLocalization,
            {
                "authorization_id": authorization.authorization_id,
                "evaluation_id": evaluation.evaluation_id,
                "prompt_rows": rows,
                "field_sources": tuple(field_sources),
                "response_exact_answer_schema_match_count": answer_matches,
                "response_exact_operation_output_schema_match_count": operation_matches,
                "response_exact_answer_or_operation_match_count": either_matches,
            },
            field="audit_id",
            prefix="finance_v26_202_first_response_interface_localization:",
        ),
    )


def _capture_attack(
    *,
    name: str,
    target: str,
    expected_fragment: str,
    invoke: Callable[[], Any],
) -> models.AttackResult:
    try:
        invoke()
    except (ValueError, ValidationError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"v26.202 attack rejected unexpectedly:{name}:{exc}") from exc
        reason = str(exc)
    else:
        raise AssertionError(f"v26.202 attack was accepted:{name}")
    return cast(
        models.AttackResult,
        models.make_identity(
            models.AttackResult,
            {
                "attack_name": name,
                "target": target,
                "expected_reason": expected_fragment,
                "actual_reason": reason,
            },
            field="attack_id",
            prefix="finance_v26_202_attack:",
        ),
    )


def _reject_adapter(enabled: bool) -> None:
    if enabled:
        _fail("historical.adapter", "historical response adaptation is forbidden")


def _destructive_audit(
    *,
    audit_bytes: bytes,
    evaluation: models.ExactEmpiricalEvidenceSetEvaluation,
    localization: models.FirstResponseInterfaceLocalization,
    records: tuple[v200_models.OnlineJobExecutionRecord, ...],
    expected_job_ids: tuple[str, ...],
    v201_rows: dict[str, v201_models.IndependentJobAuditRow],
    v200_root: Path,
    parents: tuple[Any, ...],
) -> models.DestructiveAudit:
    registry, raw_contract, result_contract = cast(tuple[Any, ...], parents[4:7])
    trace_contract, outcome_contract = cast(tuple[Any, ...], parents[7:9])

    def validate(changed: Sequence[v200_models.OnlineJobExecutionRecord]) -> Any:
        return _strict_empirical_rows(
            records=changed,
            expected_job_ids=expected_job_ids,
            v201_rows=v201_rows,
            v200_root=v200_root,
            terminal_registry=registry,
            raw_contract=raw_contract,
            result_contract=result_contract,
            trace_contract=trace_contract,
            outcome_contract=outcome_contract,
        )

    attacks: list[models.AttackResult] = []
    attacks.append(
        _capture_attack(
            name="missing_manifest_job",
            target="exact_set",
            expected_fragment="denominator",
            invoke=lambda: validate(records[1:]),
        )
    )
    attacks.append(
        _capture_attack(
            name="duplicate_job_replaces_last",
            target="exact_set",
            expected_fragment="repeats a Job",
            invoke=lambda: validate((*records[:-1], records[0])),
        )
    )
    attacks.append(
        _capture_attack(
            name="thinking_rows_excluded",
            target="end_to_end_denominator",
            expected_fragment="denominator",
            invoke=lambda: validate(
                tuple(
                    item for item in records if item.terminal_kind != "thinking_integrity_failure"
                )
            ),
        )
    )
    changed = records[0].model_dump(mode="python", warnings=False)
    changed["terminal_kind"] = "completed_qualified"
    attacks.append(
        _capture_attack(
            name="terminal_reclassification",
            target="empirical_row",
            expected_fragment="crosses its evidence bundle",
            invoke=lambda: validate(
                (
                    v200_models.OnlineJobExecutionRecord.model_construct(**changed),
                    *records[1:],
                )
            ),
        )
    )
    first_prompt = localization.prompt_rows[0]
    first_envelope = _load(
        v200_root / "kernel_artifacts" / "envelopes" / _safe(first_prompt.job_id) / "000.json"
    )
    attacks.append(
        _capture_attack(
            name="prompt_byte_mutation",
            target="first_prompt",
            expected_fragment="request hash differs",
            invoke=lambda: _assert_prompt_match("mutated", first_envelope),
        )
    )
    second_envelope = _load(
        v200_root
        / "kernel_artifacts"
        / "envelopes"
        / _safe(localization.prompt_rows[1].job_id)
        / "000.json"
    )
    attacks.append(
        _capture_attack(
            name="cross_job_request_envelope",
            target="first_prompt",
            expected_fragment="request hash differs",
            invoke=lambda: _assert_prompt_match(
                json.dumps({"sha": first_prompt.prompt_sha256}), second_envelope
            ),
        )
    )
    attacks.append(
        _capture_attack(
            name="historical_payload_action_adapter",
            target="historical_response",
            expected_fragment="adaptation is forbidden",
            invoke=lambda: _reject_adapter(True),
        )
    )
    attacks.append(
        _capture_attack(
            name="external_audit_byte_mutation",
            target="authorization",
            expected_fragment="external Audit bytes differ",
            invoke=lambda: _authorization_bytes_for_attack(audit_bytes + b"\n"),
        )
    )
    return cast(
        models.DestructiveAudit,
        models.make_identity(
            models.DestructiveAudit,
            {
                "evaluation_id": evaluation.evaluation_id,
                "localization_id": localization.audit_id,
                "attacks": tuple(attacks),
            },
            field="audit_id",
            prefix="finance_v26_202_destructive_audit:",
        ),
    )


def _authorization_bytes_for_attack(payload: bytes) -> None:
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        _fail("authorization", "v26.202 external Audit bytes differ")


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"v26.202 output already exists:{output_dir}")
    authorization, audit_bytes = _authorization(external_audit_path)
    freeze, byte_audit, _ = _v201_freeze(package_root, authorization.authorization_id)
    v200_root = package_root / V200_DIR
    records = _load_records(v200_root)
    evaluation, parents = _evaluation(
        repository_root=repository_root,
        authorization=authorization,
        freeze=freeze,
        byte_audit=byte_audit,
        records=records,
        v200_root=v200_root,
    )
    localization = _localization(
        repository_root=repository_root,
        output_dir=output_dir,
        authorization=authorization,
        evaluation=evaluation,
        records=records,
        v200_root=v200_root,
    )
    manifest = parents[1]
    destructive = _destructive_audit(
        audit_bytes=audit_bytes,
        evaluation=evaluation,
        localization=localization,
        records=records,
        expected_job_ids=manifest.expected_job_ids,
        v201_rows={item.job_id: item for item in byte_audit.rows},
        v200_root=v200_root,
        parents=parents,
    )
    decision = cast(
        models.Decision,
        models.make_identity(
            models.Decision,
            {
                "authorization_id": authorization.authorization_id,
                "evaluation_id": evaluation.evaluation_id,
                "localization_id": localization.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "decision": (
                    "end_to_end_zero_capability_rates_materialized_and_first_response_"
                    "interface_structurally_localized"
                ),
            },
            field="decision_id",
            prefix="finance_v26_202_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        models.make_identity(
            models.Transition,
            {"decision_id": decision.decision_id},
            field="transition_id",
            prefix="finance_v26_202_transition:",
        ),
    )
    source_commit, source_tree = _git_identity(repository_root)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(output_dir / "external_audit.txt", audit_bytes)
    _write_no_replace(output_dir / "external_authorization.json", authorization)
    _write_no_replace(output_dir / "v26_201_audit_freeze.json", freeze)
    _write_no_replace(output_dir / "exact_empirical_evidence_set_evaluation.json", evaluation)
    _write_no_replace(output_dir / "first_response_interface_localization.json", localization)
    _write_no_replace(output_dir / "destructive_audit.json", destructive)
    _write_no_replace(output_dir / "decision.json", decision)
    _write_no_replace(output_dir / "prospective_transition.json", transition)
    report = {
        "run_id": RUN_ID,
        "consumed_stage": models.CONSUMED_STAGE,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "authorization_id": authorization.authorization_id,
        "v201_freeze_id": freeze.freeze_id,
        "evaluation_id": evaluation.evaluation_id,
        "localization_id": localization.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "decision_id": decision.decision_id,
        "transition_id": transition.transition_id,
        "exact_job_count": 192,
        "q_first_fraction": "0/192",
        "q_bounded_correction_fraction": "0/192",
        "post_action_abi_denominator": 0,
        "post_action_abi_conditional_semantic_fraction": None,
        "first_response_action_interface_admission": "0/192",
        "response_exact_answer_schema_match_count": (
            localization.response_exact_answer_schema_match_count
        ),
        "response_exact_operation_output_schema_match_count": (
            localization.response_exact_operation_output_schema_match_count
        ),
        "response_exact_answer_or_operation_match_count": (
            localization.response_exact_answer_or_operation_match_count
        ),
        "structural_competing_schema_overlap_confirmed": True,
        "causal_attribution_proven": False,
        "provider_calls": 0,
        "rerun_recovery_historical_adaptation_count": 0,
        "mapper_state_frequency_contribution_vtdo_rows": 0,
        "decision": decision.decision,
        "next_decision": transition.next_decision,
        "schema_version": models.SCHEMA_VERSION,
    }
    _write_no_replace(output_dir / "report.json", report)
    _write_no_replace(
        output_dir / "source_identity.json",
        {"source_commit": source_commit, "source_tree": source_tree},
    )
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(output_dir).as_posix(),
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in output_dir.rglob("*") if item.is_file())
    )
    artifact_manifest = models.artifact_manifest(run_id=RUN_ID, members=members)
    _write_no_replace(output_dir / "artifact_manifest.json", artifact_manifest)
    return {
        **report,
        "artifact_manifest_id": artifact_manifest.manifest_id,
        "artifact_root": artifact_manifest.artifact_root,
    }


def _default_output(package_root: Path) -> Path:
    return package_root / OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    package_root = repository_root / "trusted_data_synthesis"
    output_dir = (args.output_dir or _default_output(package_root)).resolve()
    print(
        _canonical_json(
            build(
                repository_root=repository_root,
                output_dir=output_dir,
                external_audit_path=args.external_audit.resolve(),
            )
        )
    )


if __name__ == "__main__":
    main()
