# ruff: noqa: E501, SLF001
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair as v226,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models as v226_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)

RUN_ID: Final = models.RUN_ID
OUTPUT_DIR: Final = models.OUTPUT_DIR
MODELS_FILE: Final = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models.py"
PREFLIGHT_FILE: Final = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight.py"
IMPLEMENTATION_FILES: Final = (MODELS_FILE, PREFLIGHT_FILE)
V226_FILE_COUNT: Final = 3_428
V226_TOTAL_BYTES: Final = 99_765_014
V226_MEMBER_COUNT: Final = 3_427
V226_MEMBER_BYTES: Final = 99_047_004
V228_FILE_COUNT: Final = 17
V228_TOTAL_BYTES: Final = 45_679
V228_MEMBER_COUNT: Final = 16
V228_MEMBER_BYTES: Final = 42_978
V228_MANIFEST_SHA256: Final = "42b3ded8192a175bc6a69636cc3a798073d0cc25a8785e540b903bbbc26501ae"
V228_MANIFEST_BYTES: Final = 2_701
V228_EXCLUSION_SHA256: Final = "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
HOST_ORDINALS: Final = (6, 22, 149)
JSON_ORDINALS: Final = (62, 139)


class V229Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V229Error(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _load_bytes(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("json.object", "expected one JSON object")
    return cast(dict[str, Any], value)


def _load(path: Path) -> dict[str, Any]:
    return _load_bytes(path.read_bytes())


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _make(model_type: type[Any], values: dict[str, Any], field: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=model_type.prefix())


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(("git", *args), cwd=root, check=False, capture_output=True)
    if result.returncode:
        _fail("source.git", result.stderr.decode(errors="replace"))
    return result.stdout


def _verify_manifest(
    root: Path,
    manifest_name: str,
    *,
    file_count: int,
    total_bytes: int,
    member_count: int,
    member_bytes: int,
    manifest_id: str,
    artifact_root: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files = _files(root)
    if len(files) != file_count or sum(map(len, files.values())) != total_bytes:
        _fail("freeze.geometry", f"formal directory geometry differs:{root}")
    manifest = _load_bytes(files.get(manifest_name, b""))
    members = {str(row["relative_path"]): row for row in manifest.get("members", ())}
    if (
        manifest.get("manifest_id") != manifest_id
        or manifest.get("artifact_root") != artifact_root
        or manifest.get("self_excluding") is not True
        or manifest.get("total_member_bytes") != member_bytes
        or len(members) != member_count
        or set(members) != set(files) - {manifest_name}
    ):
        _fail("freeze.manifest", f"Manifest relation differs:{root}")
    for path, row in members.items():
        payload = files[path]
        if row.get("sha256") != _sha(payload) or row.get("byte_count") != len(payload):
            _fail("freeze.member", f"Manifest member differs:{path}")
    return files, manifest


def _authorization(review: bytes) -> models.ExternalAuthorization:
    directive = models.OPERATOR_DIRECTIVE.encode()
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.review", "external review bytes differ")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.directive", "operator directive bytes differ")
    return _make(models.ExternalAuthorization, {}, "authorization_id")


def _source_identity(repository_root: Path, commit: str, tree: str) -> models.SourceIdentity:
    if _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip() != tree:
        _fail("source.commit_tree", "source commit/tree relation differs")
    members: list[dict[str, Any]] = []
    for path in IMPLEMENTATION_FILES:
        committed = _git(repository_root, "show", f"{commit}:{path}")
        working = (repository_root / path).read_bytes()
        if committed != working:
            _fail("source.working_tree", f"working source differs:{path}")
        members.append(
            {"relative_path": path, "sha256": _sha(committed), "byte_count": len(committed)}
        )
    by_path = {row["relative_path"]: row for row in members}
    return _make(
        models.SourceIdentity,
        {
            "source_commit": commit,
            "source_tree": tree,
            "model_relative_path": MODELS_FILE,
            "model_sha256": by_path[MODELS_FILE]["sha256"],
            "model_byte_count": by_path[MODELS_FILE]["byte_count"],
            "preflight_relative_path": PREFLIGHT_FILE,
            "preflight_sha256": by_path[PREFLIGHT_FILE]["sha256"],
            "preflight_byte_count": by_path[PREFLIGHT_FILE]["byte_count"],
            "ordered_member_set_sha256": _sha(models.canonical_bytes(tuple(members))),
        },
        "source_identity_id",
    )


def _freeze_v228(repository_root: Path, authorization_id: str) -> models.V228Freeze:
    files, _manifest = _verify_manifest(
        repository_root / models.V228_DIR,
        "artifact_manifest.json",
        file_count=V228_FILE_COUNT,
        total_bytes=V228_TOTAL_BYTES,
        member_count=V228_MEMBER_COUNT,
        member_bytes=V228_MEMBER_BYTES,
        manifest_id=models.V228_MANIFEST_ID,
        artifact_root=models.V228_ARTIFACT_ROOT,
    )
    if (
        _sha(files["artifact_manifest.json"]) != V228_MANIFEST_SHA256
        or len(files["artifact_manifest.json"]) != V228_MANIFEST_BYTES
    ):
        _fail("freeze.v228_manifest_bytes", "v26.228 Manifest bytes differ")
    report = _load_bytes(files["report.json"])
    decision = _load_bytes(files["decision.json"])
    transition = _load_bytes(files["prospective_transition.json"])
    if (
        report.get("report_id") != models.V228_REPORT_ID
        or decision.get("decision_id") != models.V228_DECISION_ID
        or transition.get("transition_id") != models.V228_TRANSITION_ID
        or transition.get("next_stage") != models.CONSUMED_STAGE
        or transition.get("next_stage_authorized") is not False
    ):
        _fail("freeze.v228_semantics", "v26.228 Decision/Transition differs")
    return _make(models.V228Freeze, {"authorization_id": authorization_id}, "freeze_id")


def _source_projection(
    relative_path: str, payload: bytes, record: v226_models.JobFailureRecord
) -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "sha256": _sha(payload),
        "byte_count": len(payload),
        "record_sha256": _sha(
            models.canonical_bytes(record.model_dump(mode="json", warnings=False))
        ),
        "record_id": record.record_id,
        "job_id": record.job_id,
        "job_ordinal": record.job_ordinal,
        "failure_kind": record.failure_kind,
        "error_sha256": record.error_sha256,
        "provider_call_ids": tuple(call.provider_call_id for call in record.provider_calls),
    }


def _exactly_one(call: v226_models.ProviderCallDescriptor, kind: str) -> Any:
    rows = tuple(item for item in call.artifacts if item.artifact_kind == kind)
    if len(rows) != 1:
        _fail("source.artifact_geometry", f"expected one {kind}")
    return rows[0]


def _artifact_binding(root: Path, descriptor: Any) -> tuple[models.ArtifactBinding, dict[str, Any]]:
    path = root / descriptor.relative_path
    payload = path.read_bytes()
    value = _load_bytes(payload)
    if (
        payload != _encoded(value)
        or _sha(payload) != descriptor.sha256
        or len(payload) != descriptor.byte_count
        or (
            "provider_call_id" in value
            and value.get("provider_call_id") != descriptor.provider_call_id
        )
        or value.get("raw_provider_response_persisted") not in (None, False)
        or value.get("private_reasoning_persisted") not in (None, False)
    ):
        _fail("source.artifact_bytes", f"Provider artifact differs:{descriptor.relative_path}")
    return models.ArtifactBinding(
        artifact_id=descriptor.artifact_id,
        provider_call_id=descriptor.provider_call_id,
        artifact_kind=descriptor.artifact_kind,
        relative_path=descriptor.relative_path,
        sha256=descriptor.sha256,
        byte_count=descriptor.byte_count,
        public_projection_sha256=descriptor.public_projection_sha256,
    ), value


def _call_authority(
    root: Path, record: v226_models.JobFailureRecord, call: v226_models.ProviderCallDescriptor
) -> tuple[models.ProviderCallAuthority, dict[str, Any] | None, dict[str, Any] | None]:
    request_descriptor = _exactly_one(call, "request_metadata")
    descriptor_path = request_descriptor.relative_path.replace(
        "_request_metadata.json", "_descriptor.json"
    )
    descriptor_payload = (root / descriptor_path).read_bytes()
    if descriptor_payload != _encoded(call):
        _fail("source.descriptor_bytes", f"Provider descriptor differs:{descriptor_path}")
    bindings: list[models.ArtifactBinding] = []
    values: dict[str, dict[str, Any]] = {}
    for artifact in call.artifacts:
        binding, value = _artifact_binding(root, artifact)
        bindings.append(binding)
        values[artifact.artifact_kind] = value
    request = values["request_metadata"]
    usage = values["usage_metadata"]
    telemetry = cast(dict[str, Any], usage.get("telemetry", {}))
    error = values.get("error_metadata")
    response = values.get("response_metadata")
    if (
        request.get("job_id") != record.job_id
        or request.get("call_ordinal") != call.call_ordinal
        or request.get("request_sha256") != call.request_sha256
        or request.get("run_start_receipt_id") != call.run_start_receipt_id
        or request.get("raw_request_persisted") is not False
        or request.get("retry_authorized") is not False
        or telemetry.get("request_hash") != call.request_sha256
        or telemetry.get("prompt_tokens") != call.input_tokens
        or telemetry.get("completion_tokens") != call.output_tokens
        or telemetry.get("http_success") is not True
        or telemetry.get("http_status") != 200
    ):
        _fail("source.call_relation", "request/Usage/descriptor relation differs")
    if call.status == "succeeded":
        if (
            response is None
            or response.get("public_projection_sha256") != call.response_sha256
            or not isinstance(response.get("public_projection"), dict)
            or _sha(models.canonical_bytes(response["public_projection"])) != call.response_sha256
            or telemetry.get("response_hash")
            != response.get("redacted_response_fields", {}).get("public_content_sha256")
            or telemetry.get("error_type") is not None
        ):
            _fail("source.success_relation", "successful Provider relation differs")
    elif (
        error is None
        or error.get("error_sha256") != call.error_sha256
        or error.get("error_type") != telemetry.get("error_type")
        or error.get("http_status") != 200
        or error.get("http_success") is not True
        or error.get("raw_provider_response_persisted") is not False
        or error.get("private_reasoning_persisted") is not False
        or telemetry.get("response_shape", {})
        .get("redacted_response_envelope", {})
        .get("raw_http_body_persisted")
        is not False
    ):
        _fail("source.error_relation", "failed Provider relation differs")
    return (
        models.ProviderCallAuthority(
            provider_call_id=call.provider_call_id,
            descriptor_id=call.descriptor_id,
            run_start_receipt_id=call.run_start_receipt_id,
            historical_job_id=record.job_id,
            call_ordinal=call.call_ordinal,
            status=call.status,
            request_sha256=call.request_sha256,
            request_byte_count=int(request["request_byte_count"]),
            intention_sha256=call.intention_sha256,
            certificate_id=str(request["certificate_id"]),
            pre_transport_receipt_id=str(request["pre_transport_receipt_id"]),
            response_sha256=call.response_sha256,
            error_sha256=call.error_sha256,
            error_type=None if error is None else str(error["error_type"]),
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            artifact_bindings=tuple(bindings),
        ),
        response,
        error,
    )


@dataclass(frozen=True)
class SourceData:
    audit: models.V226SourceAuthorityAudit
    journal: models.ProviderJournalAuthority
    records: tuple[v226_models.JobFailureRecord, ...]
    public_prefixes: dict[int, tuple[dict[str, Any], ...]]
    error_metadata: dict[int, dict[str, Any]]


def _source_authority(
    repository_root: Path, freeze: models.V228Freeze, source_identity_id: str
) -> SourceData:
    root = repository_root / models.V226_DIR
    files, _manifest = _verify_manifest(
        root,
        "execution_artifact_manifest.json",
        file_count=V226_FILE_COUNT,
        total_bytes=V226_TOTAL_BYTES,
        member_count=V226_MEMBER_COUNT,
        member_bytes=V226_MEMBER_BYTES,
        manifest_id=models.V226_MANIFEST_ID,
        artifact_root=models.V226_ARTIFACT_ROOT,
    )
    summary = v226_models.ExecutionSummary.model_validate(
        _load_bytes(files["execution_summary.json"])
    )
    transition = _load_bytes(files["prospective_transition.json"])
    census = _load_bytes(files["provider_intent_census.json"])
    if (
        summary.summary_id != models.V226_SUMMARY_ID
        or summary.failure_partition != {"unbound_provider_failure": 33, "host_failure": 3}
        or summary.execution_status != "incomplete"
        or transition.get("transition_id") != models.V226_TRANSITION_ID
        or census.get("census_id") != models.V226_PROVIDER_CENSUS_ID
    ):
        _fail("source.v226_freeze", "v26.226 summary/transition/census differs")
    provider_records: list[v226_models.JobFailureRecord] = []
    provider_projection: list[dict[str, Any]] = []
    host_projection: list[dict[str, Any]] = []
    rows: list[models.V226SourceRow] = []
    prefixes: dict[int, tuple[dict[str, Any], ...]] = {}
    errors: dict[int, dict[str, Any]] = {}
    relation_projection: list[dict[str, Any]] = []
    total_calls = response_count = 0
    for embedded in sorted(summary.failure_records, key=lambda item: item.job_ordinal):
        relative_path = f"job_failures/job_{embedded.job_ordinal:03d}.json"
        raw = files[relative_path]
        record = v226_models.JobFailureRecord.model_validate(_load_bytes(raw))
        if raw != _encoded(record) or record != embedded:
            _fail("source.failure_record", f"failure record differs:{relative_path}")
        projection = _source_projection(relative_path, raw, record)
        if record.failure_kind == "host_failure":
            host_projection.append(projection)
            continue
        if record.failure_kind != "unbound_provider_failure":
            _fail("source.failure_kind", "unexpected failure kind")
        calls: list[models.ProviderCallAuthority] = []
        public_prefix: list[dict[str, Any]] = []
        last_error: dict[str, Any] | None = None
        for expected_ordinal, call in enumerate(record.provider_calls):
            if call.call_ordinal != expected_ordinal:
                _fail("source.call_order", "Provider call order differs")
            authority, response, error = _call_authority(root, record, call)
            calls.append(authority)
            relation_projection.append(authority.model_dump(mode="json", warnings=False))
            total_calls += 1
            if response is not None:
                public_prefix.append(cast(dict[str, Any], response["public_projection"]))
                response_count += 1
            if error is not None:
                last_error = error
        if last_error is None or len(calls) != len(public_prefix) + 1:
            _fail("source.failed_prefix", "failed Provider prefix geometry differs")
        if last_error["error_type"] not in {"ReasoningBudgetExhaustedError", "JSONDecodeError"}:
            _fail("source.error_type", "Provider failure type outside exact population")
        failure_class: models.FailureClass = (
            "reasoning_budget_exhausted_normalized_public_content_empty"
            if last_error["error_type"] == "ReasoningBudgetExhaustedError"
            else "json_decode_failure_exact_syntax_unavailable"
        )
        row = _make(
            models.V226SourceRow,
            {
                "v228_freeze_id": freeze.freeze_id,
                "historical_job_id": record.job_id,
                "job_ordinal": record.job_ordinal,
                "failure_record_id": record.record_id,
                "failure_relative_path": relative_path,
                "failure_file_sha256": _sha(raw),
                "failure_file_byte_count": len(raw),
                "failure_record_sha256": _sha(
                    models.canonical_bytes(record.model_dump(mode="json", warnings=False))
                ),
                "run_start_receipt_id": record.run_start_receipt_id,
                "authorization_id": record.authorization_id,
                "provider_calls": tuple(calls),
                "successful_prefix_call_count": len(public_prefix),
                "failed_call_ordinal": calls[-1].call_ordinal,
                "failed_provider_call_id": calls[-1].provider_call_id,
                "failed_descriptor_id": calls[-1].descriptor_id,
                "failed_request_sha256": calls[-1].request_sha256,
                "failure_class": failure_class,
            },
            "row_id",
        )
        rows.append(row)
        prefixes[record.job_ordinal] = tuple(public_prefix)
        errors[record.job_ordinal] = last_error
        provider_records.append(record)
        provider_projection.append(projection)
    provider_sha = _sha(models.canonical_bytes(tuple(provider_projection)))
    host_sha = _sha(models.canonical_bytes(tuple(host_projection)))
    if (
        len(rows) != 33
        or tuple(row.job_ordinal for row in rows) != tuple(sorted(row.job_ordinal for row in rows))
        or tuple(
            row.job_ordinal for row in summary.failure_records if row.failure_kind == "host_failure"
        )
        != HOST_ORDINALS
        or provider_sha != V228_EXCLUSION_SHA256
        or total_calls != 88
        or response_count != 55
    ):
        _fail("source.partition", "exact 3/33 source partition or 88-call journal differs")
    audit = _make(
        models.V226SourceAuthorityAudit,
        {
            "source_identity_id": source_identity_id,
            "v228_freeze_id": freeze.freeze_id,
            "source_rows": tuple(rows),
            "source_row_id_set_sha256": models.canonical_sha256(tuple(row.row_id for row in rows)),
            "v226_actual_source_projection_sha256": provider_sha,
            "v228_exclusion_set_sha256": V228_EXCLUSION_SHA256,
            "v228_exclusion_set_match": True,
            "excluded_host_set_sha256": host_sha,
        },
        "audit_id",
    )
    journal = _make(
        models.ProviderJournalAuthority,
        {
            "source_authority_audit_id": audit.audit_id,
            "source_row_ids": tuple(sorted(row.row_id for row in rows)),
            "provider_descriptor_count": total_calls,
            "request_metadata_count": total_calls,
            "response_metadata_count": response_count,
            "usage_metadata_count": total_calls,
            "relation_set_sha256": _sha(models.canonical_bytes(tuple(relation_projection))),
        },
        "audit_id",
    )
    return SourceData(
        audit=audit,
        journal=journal,
        records=tuple(provider_records),
        public_prefixes=prefixes,
        error_metadata=errors,
    )


class _CaptureFailedRequest(RuntimeError):
    pass


class _CaptureTransport:
    def __init__(self, public_prefix: tuple[dict[str, Any], ...]) -> None:
        self._public_prefix = list(public_prefix)
        self.dispatches: list[v209.TransportDispatch] = []

    def send(self, dispatch: v209.TransportDispatch) -> dict[str, Any]:
        if (
            dispatch.receipt.certificate_id != dispatch.certificate.certificate_id
            or dispatch.receipt.request_id != dispatch.certificate.request_id
            or v209_models.canonical_sha256(dict(dispatch.request_body))
            != dispatch.certificate.canonical_request_body_sha256
        ):
            _fail("replay.transport_chain", "capture transport request chain differs")
        self.dispatches.append(dispatch)
        if self._public_prefix:
            return self._public_prefix.pop(0)
        raise _CaptureFailedRequest("capture failed request before response projection")


def _request_replay(repository_root: Path, source: SourceData) -> models.RequestReplayAudit:
    with TemporaryDirectory(prefix="finance-v26-229-runtime-") as temp:
        loaded = v226._load_exact_runtime(repository_root, Path(temp))
        jobs = {job.job_id: job for job in loaded["manifest"].jobs}
        rows: list[models.RequestReplayRow] = []
        for source_row, record in zip(source.audit.source_rows, source.records, strict=True):
            transport = _CaptureTransport(source.public_prefixes[record.job_ordinal])
            runner = v209._make_runner(
                transport=transport,
                config=loaded["config"],
                parents=loaded["parents"],
                prepared=loaded["runtime"],
                implementation_id=loaded["implementation"].implementation_id,
            )
            job = jobs[record.job_id]
            context = v209._context_for_job(
                job=job, parents=loaded["parents"], prepared=loaded["runtime"]
            )
            state = frozen_runtime._initialize(context)
            successful_records: list[v209_models.ExecutableInvocationRecord] = []
            invocation_index = 0
            target = len(record.provider_calls)
            captured_failure = False
            while (
                state.current_index < len(state.ordered_components)
                and len(transport.dispatches) < target
            ):
                try:
                    outcome = runner.invoke_action(
                        job=job, invocation_index=invocation_index, state=state
                    )
                except _CaptureFailedRequest:
                    captured_failure = True
                    break
                successful_records.append(outcome.record)
                invocation_index += 1
                if outcome.terminal is not None:
                    _fail("replay.prefix_terminal", "successful source prefix terminalized")
                if outcome.record.action_accepted is True:
                    continue
                if not isinstance(
                    outcome.runtime_output, step_runtime.PublicTypedRejectionObservation
                ):
                    _fail("replay.action", "rejected Action lacks public feedback")
                try:
                    correction = runner.invoke_correction(
                        job=job, invocation_index=invocation_index, state=state
                    )
                except _CaptureFailedRequest:
                    captured_failure = True
                    break
                successful_records.append(correction.record)
                invocation_index += 1
                if correction.terminal is not None or correction.record.action_accepted is not True:
                    _fail("replay.correction", "successful correction prefix differs")
            if not captured_failure and len(transport.dispatches) < target:
                try:
                    runner.invoke_final(
                        job=job,
                        invocation_index=invocation_index,
                        state=state,
                        context=context,
                    )
                except _CaptureFailedRequest:
                    captured_failure = True
            if (
                not captured_failure
                or len(transport.dispatches) != target
                or len(successful_records) != target - 1
                or tuple(row.invocation_index for row in successful_records)
                != tuple(range(target - 1))
            ):
                _fail("replay.geometry", "request replay geometry differs")
            request_matches = response_matches = 0
            for index, (dispatch, call) in enumerate(
                zip(transport.dispatches, source_row.provider_calls, strict=True)
            ):
                request_bytes = models.canonical_bytes(dict(dispatch.request_body))
                if (
                    _sha(request_bytes) == call.request_sha256
                    and len(request_bytes) == call.request_byte_count
                    and dispatch.certificate.certificate_id == call.certificate_id
                    and dispatch.receipt.receipt_id == call.pre_transport_receipt_id
                    and dispatch.certificate.job_id == record.job_id
                ):
                    request_matches += 1
                if index < source_row.successful_prefix_call_count:
                    invocation = successful_records[index]
                    if (
                        invocation.canonical_request_body_sha256 == call.request_sha256
                        and invocation.public_response_sha256 == call.response_sha256
                        and invocation.phase == dispatch.certificate.phase
                    ):
                        response_matches += 1
            if (
                request_matches != target
                or response_matches != source_row.successful_prefix_call_count
            ):
                _fail("replay.authority", "request or public-prefix relation differs")
            last_dispatch = transport.dispatches[-1]
            rows.append(
                models.RequestReplayRow(
                    source_row_id=source_row.row_id,
                    historical_job_id=record.job_id,
                    job_ordinal=record.job_ordinal,
                    invocation_count=target,
                    successful_invocation_ids=tuple(
                        item.invocation_id for item in successful_records
                    ),
                    phases=tuple(item.phase for item in successful_records)
                    + (last_dispatch.certificate.phase,),
                    request_sha256s=tuple(
                        v209_models.canonical_sha256(dict(item.request_body))
                        for item in transport.dispatches
                    ),
                    response_sha256s=tuple(
                        item.public_response_sha256
                        for item in successful_records
                        if item.public_response_sha256 is not None
                    ),
                    successful_prefix_call_count=source_row.successful_prefix_call_count,
                    failed_call_ordinal=source_row.failed_call_ordinal,
                    exact_request_match_count=request_matches,
                    exact_response_match_count=response_matches,
                    failed_request_certificate_id=last_dispatch.certificate.certificate_id,
                    failed_pre_transport_receipt_id=last_dispatch.receipt.receipt_id,
                    failed_request_sha256=v209_models.canonical_sha256(
                        dict(last_dispatch.request_body)
                    ),
                    failed_request_byte_count=len(
                        v209_models.canonical_bytes(dict(last_dispatch.request_body))
                    ),
                )
            )
    phases = tuple(row.phases[-1] for row in rows)
    if (
        phases.count("first_action") != 3
        or phases.count("subsequent_action") != 25
        or phases.count("final") != 5
        or phases.count("correction") != 0
    ):
        _fail("replay.phase_partition", "failed request phase partition differs")
    return _make(
        models.RequestReplayAudit,
        {
            "source_authority_audit_id": source.audit.audit_id,
            "provider_journal_authority_id": source.journal.audit_id,
            "rows": tuple(rows),
        },
        "audit_id",
    )


def _identifiability(source: SourceData) -> models.IdentifiabilityAudit:
    rows: list[models.IdentifiabilityRow] = []
    source_by_ordinal = {row.job_ordinal: row for row in source.audit.source_rows}
    for ordinal, error in sorted(source.error_metadata.items()):
        redacted = cast(dict[str, Any], error["redacted_response_fields"])
        error_type = str(error["error_type"])
        reasoning = error_type == "ReasoningBudgetExhaustedError"
        if (
            error_type not in {"ReasoningBudgetExhaustedError", "JSONDecodeError"}
            or (
                reasoning
                and (
                    redacted.get("public_content_length") != 0
                    or redacted.get("public_content_sha256") != _sha(b"")
                    or redacted.get("finish_reason") != "length"
                )
            )
            or ((not reasoning) and ordinal not in JSON_ORDINALS)
        ):
            _fail("identifiability.source", "persisted response identifiability differs")
        source_row = source_by_ordinal[ordinal]
        rows.append(
            _make(
                models.IdentifiabilityRow,
                {
                    "source_row_id": source_row.row_id,
                    "historical_job_id": source_row.historical_job_id,
                    "job_ordinal": ordinal,
                    "failure_class": source_row.failure_class,
                    "error_type": error_type,
                    "public_content_sha256": str(redacted["public_content_sha256"]),
                    "public_content_length": int(redacted["public_content_length"]),
                    "finish_reason": str(redacted["finish_reason"]),
                    "failure_semantics_identifiable": reasoning,
                    "exact_json_syntax_identifiable": False,
                },
                "row_id",
            )
        )
    rows = sorted(rows, key=lambda item: item.row_id)
    if len(rows) != 33 or sum(item.error_type == "JSONDecodeError" for item in rows) != 2:
        _fail("identifiability.partition", "31/2 identifiability partition differs")
    return _make(
        models.IdentifiabilityAudit,
        {
            "source_authority_audit_id": source.audit.audit_id,
            "rows": tuple(rows),
        },
        "audit_id",
    )


@dataclass(frozen=True)
class RecoveryData:
    candidates: tuple[models.RecoveryCandidate, ...]
    contract: models.RecoveryContract
    population: models.RecoveryPopulation


def _recovery_population(
    source: SourceData,
    replay: models.RequestReplayAudit,
    identifiability: models.IdentifiabilityAudit,
) -> RecoveryData:
    replay_by_ordinal = {row.job_ordinal: row for row in replay.rows}
    identifiability_by_ordinal = {row.job_ordinal: row for row in identifiability.rows}
    candidates: list[models.RecoveryCandidate] = []
    for row in source.audit.source_rows:
        replay_row = replay_by_ordinal[row.job_ordinal]
        identifiable = identifiability_by_ordinal[row.job_ordinal]
        candidates.append(
            _make(
                models.RecoveryCandidate,
                {
                    "source_authority_audit_id": source.audit.audit_id,
                    "provider_journal_authority_id": source.journal.audit_id,
                    "request_replay_audit_id": replay.audit_id,
                    "identifiability_audit_id": identifiability.audit_id,
                    "source_row_id": row.row_id,
                    "identifiability_row_id": identifiable.row_id,
                    "historical_job_id": row.historical_job_id,
                    "job_ordinal": row.job_ordinal,
                    "failure_record_id": row.failure_record_id,
                    "successful_prefix_call_count": row.successful_prefix_call_count,
                    "successful_prefix_provider_call_ids": tuple(
                        call.provider_call_id for call in row.provider_calls[:-1]
                    ),
                    "failed_provider_call_id": row.failed_provider_call_id,
                    "failed_descriptor_id": row.failed_descriptor_id,
                    "exact_failed_request_sha256": replay_row.failed_request_sha256,
                    "exact_failed_request_byte_count": replay_row.failed_request_byte_count,
                    "exact_failed_request_certificate_id": replay_row.failed_request_certificate_id,
                    "exact_failed_pre_transport_receipt_id": replay_row.failed_pre_transport_receipt_id,
                    "failure_class": row.failure_class,
                    "historical_json_syntax_detail_available": False,
                },
                "candidate_id",
            )
        )
    candidates_tuple = tuple(sorted(candidates, key=lambda item: item.candidate_id))
    contract = _make(
        models.RecoveryContract,
        {
            "source_authority_audit_id": source.audit.audit_id,
            "provider_journal_authority_id": source.journal.audit_id,
            "request_replay_audit_id": replay.audit_id,
            "identifiability_audit_id": identifiability.audit_id,
            "candidate_ids": tuple(item.candidate_id for item in candidates_tuple),
        },
        "contract_id",
    )
    jobs = tuple(
        sorted(
            (
                _make(
                    models.RecoveryPopulationJob,
                    {
                        "recovery_contract_id": contract.contract_id,
                        "candidate": candidate,
                    },
                    "recovery_job_id",
                )
                for candidate in candidates_tuple
            ),
            key=lambda item: item.recovery_job_id,
        )
    )
    population = _make(
        models.RecoveryPopulation,
        {"recovery_contract_id": contract.contract_id, "jobs": jobs},
        "population_id",
    )
    all_historical_ids = (
        {row.failure_record_id for row in source.audit.source_rows}
        | {call.provider_call_id for row in source.audit.source_rows for call in row.provider_calls}
        | {row.historical_job_id for row in source.audit.source_rows}
    )
    if {job.recovery_job_id for job in jobs} & all_historical_ids:
        _fail("population.identity_overlap", "fresh recovery identity overlaps historical identity")
    return RecoveryData(candidates=candidates_tuple, contract=contract, population=population)


def _admit_negative_candidate(
    candidate: dict[str, Any],
    source: SourceData,
    recovery: RecoveryData,
) -> None:
    exact_ordinals = tuple(row.job_ordinal for row in source.audit.source_rows)
    exact_prefixes = tuple(
        tuple(call.provider_call_id for call in row.provider_calls)
        for row in source.audit.source_rows
    )
    exact_hashes = tuple(row.failed_request_sha256 for row in source.audit.source_rows)
    exact_descriptors = tuple(row.failed_descriptor_id for row in source.audit.source_rows)
    exact_artifacts = tuple(
        tuple(
            (item.artifact_kind, item.relative_path, item.sha256, item.byte_count)
            for item in call.artifact_bindings
        )
        for row in source.audit.source_rows
        for call in row.provider_calls
    )
    exact_recovery_ids = tuple(job.recovery_job_id for job in recovery.population.jobs)
    exact_candidate_parents = tuple(
        (job.candidate.candidate_id, job.candidate.source_row_id)
        for job in recovery.population.jobs
    )
    if candidate["provider_calls_authorized"] or candidate["online_execution_authorized"]:
        _fail("admission.scope", "Provider or online execution expansion rejected")
    if candidate["source_ordinals"] != exact_ordinals:
        _fail(
            "admission.source_partition", "source population differs from actual v26.226 partition"
        )
    if candidate["provider_call_prefixes"] != exact_prefixes:
        _fail("admission.call_prefix", "ordered Provider-call prefix differs")
    if candidate["failed_request_sha256s"] != exact_hashes:
        _fail("admission.replay_owned_request", "failed request hash differs from replay authority")
    if candidate["failed_descriptor_ids"] != exact_descriptors:
        _fail("admission.source_parent", "failed descriptor parent differs")
    if candidate["artifact_relations"] != exact_artifacts:
        _fail("admission.source_owned_bytes", "error/Usage artifact relation differs")
    if candidate["json_response_bytes"] is not None:
        _fail(
            "admission.persisted_content_absence", "unpersisted JSON response bytes were invented"
        )
    if candidate["json_syntax_identifiable"]:
        _fail("admission.identifiability", "JSON syntax was reclassified without source bytes")
    if candidate["recovery_job_ids"] != exact_recovery_ids:
        if (
            len(candidate["recovery_job_ids"]) != 33
            or len(set(candidate["recovery_job_ids"])) != 33
        ):
            _fail("admission.population_set", "Recovery Population cardinality/uniqueness differs")
        _fail("admission.fresh_identity", "Recovery Job identity differs")
    if candidate["recovery_candidate_parents"] != exact_candidate_parents:
        _fail("admission.source_parent", "Recovery Candidate source parent differs")
    historical = (
        {row.historical_job_id for row in source.audit.source_rows}
        | {row.failure_record_id for row in source.audit.source_rows}
        | {call.provider_call_id for row in source.audit.source_rows for call in row.provider_calls}
    )
    if set(candidate["recovery_job_ids"]) & historical:
        _fail("admission.fresh_identity", "historical identity reused")
    candidate["candidate_identity"] = models.canonical_sha256(
        {key: value for key, value in candidate.items() if key != "candidate_identity"}
    )


def _negative_controls(source: SourceData, recovery: RecoveryData) -> models.NegativeControlAudit:
    positive: dict[str, Any] = {
        "provider_calls_authorized": False,
        "online_execution_authorized": False,
        "source_ordinals": tuple(row.job_ordinal for row in source.audit.source_rows),
        "provider_call_prefixes": tuple(
            tuple(call.provider_call_id for call in row.provider_calls)
            for row in source.audit.source_rows
        ),
        "failed_request_sha256s": tuple(
            row.failed_request_sha256 for row in source.audit.source_rows
        ),
        "failed_descriptor_ids": tuple(
            row.failed_descriptor_id for row in source.audit.source_rows
        ),
        "artifact_relations": tuple(
            tuple(
                (item.artifact_kind, item.relative_path, item.sha256, item.byte_count)
                for item in call.artifact_bindings
            )
            for row in source.audit.source_rows
            for call in row.provider_calls
        ),
        "json_response_bytes": None,
        "json_syntax_identifiable": False,
        "recovery_job_ids": tuple(job.recovery_job_id for job in recovery.population.jobs),
        "recovery_candidate_parents": tuple(
            (job.candidate.candidate_id, job.candidate.source_row_id)
            for job in recovery.population.jobs
        ),
        "candidate_identity": "pending",
    }
    attacks: dict[str, dict[str, Any]] = {}
    for name in models.NEGATIVE_CONTROL_NAMES:
        attacks[name] = copy.deepcopy(positive)
    attacks["authorize_online_execution"]["online_execution_authorized"] = True
    attacks["authorize_provider_call"]["provider_calls_authorized"] = True
    descriptor_ids = list(attacks["cross_job_provider_descriptor"]["failed_descriptor_ids"])
    descriptor_ids[0], descriptor_ids[1] = descriptor_ids[1], descriptor_ids[0]
    attacks["cross_job_provider_descriptor"]["failed_descriptor_ids"] = tuple(descriptor_ids)
    recovery_ids = list(attacks["duplicate_recovery_job"]["recovery_job_ids"])
    recovery_ids[-1] = recovery_ids[0]
    attacks["duplicate_recovery_job"]["recovery_job_ids"] = tuple(recovery_ids)
    hashes = list(attacks["failed_request_hash_replaced"]["failed_request_sha256s"])
    hashes[0] = _sha(b"replaced failed request")
    attacks["failed_request_hash_replaced"]["failed_request_sha256s"] = tuple(hashes)
    reused = list(attacks["historical_job_identity_reused"]["recovery_job_ids"])
    reused[0] = source.audit.source_rows[0].historical_job_id
    attacks["historical_job_identity_reused"]["recovery_job_ids"] = tuple(reused)
    ordinals = list(attacks["host_failure_substituted"]["source_ordinals"])
    ordinals[0] = HOST_ORDINALS[0]
    attacks["host_failure_substituted"]["source_ordinals"] = tuple(ordinals)
    attacks["invent_json_response_bytes"]["json_response_bytes"] = b'{"invented":true}'.hex()
    prefixes = list(attacks["provider_call_prefix_truncated"]["provider_call_prefixes"])
    prefixes[0] = prefixes[0][:-1]
    attacks["provider_call_prefix_truncated"]["provider_call_prefixes"] = tuple(prefixes)
    attacks["reclassify_json_syntax_as_identifiable"]["json_syntax_identifiable"] = True
    removed = list(attacks["remove_recovery_job"]["recovery_job_ids"])
    attacks["remove_recovery_job"]["recovery_job_ids"] = tuple(removed[:-1])
    artifact_relations = list(attacks["swap_error_or_usage_artifact"]["artifact_relations"])
    artifact_relations[0], artifact_relations[-1] = (
        artifact_relations[-1],
        artifact_relations[0],
    )
    attacks["swap_error_or_usage_artifact"]["artifact_relations"] = tuple(artifact_relations)
    results: list[models.NegativeControlResult] = []
    for name in models.NEGATIVE_CONTROL_NAMES:
        candidate = attacks[name]
        candidate["candidate_identity"] = models.canonical_sha256(
            {key: value for key, value in candidate.items() if key != "candidate_identity"}
        )
        try:
            _admit_negative_candidate(candidate, source, recovery)
        except V229Error as error:
            results.append(
                models.NegativeControlResult(
                    attack_name=name,
                    rejection_stage=error.stage,
                    reason_sha256=_sha(error.reason.encode()),
                )
            )
        else:
            _fail("negative.control", f"attack unexpectedly admitted:{name}")
    return _make(
        models.NegativeControlAudit,
        {
            "source_authority_audit_id": source.audit.audit_id,
            "recovery_population_id": recovery.population.population_id,
            "results": tuple(results),
        },
        "audit_id",
    )


def _scope() -> models.ScopeBoundaryAudit:
    return _make(models.ScopeBoundaryAudit, {}, "audit_id")


def _gates(
    authorization: models.ExternalAuthorization,
    source_identity: models.SourceIdentity,
    freeze: models.V228Freeze,
    source: SourceData,
    replay: models.RequestReplayAudit,
    identifiability: models.IdentifiabilityAudit,
    recovery: RecoveryData,
    negative: models.NegativeControlAudit,
    scope: models.ScopeBoundaryAudit,
) -> models.GateEvaluation:
    evidence = (
        (authorization.authorization_id, source_identity.source_identity_id, freeze.freeze_id),
        (source.audit.audit_id,),
        (source.journal.audit_id,),
        (replay.audit_id,),
        (
            identifiability.audit_id,
            recovery.contract.contract_id,
            recovery.population.population_id,
        ),
        (negative.audit_id, scope.audit_id),
    )
    gates = tuple(
        models.Gate(name=name, evidence_ids=evidence[index])
        for index, name in enumerate(models.GATE_NAMES)
    )
    return _make(models.GateEvaluation, {"gates": gates}, "evaluation_id")


def _write_payloads(output_dir: Path, payloads: dict[str, bytes]) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        _fail("output.nonempty", f"output directory is not empty:{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, payload in sorted(payloads.items()):
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review: bytes | None = None,
    source_commit: str | None = None,
    source_tree: str | None = None,
    external_review_path: Path | None = None,
    source_identity: tuple[str, str] | None = None,
) -> models.Report:
    if external_review is None:
        if external_review_path is None:
            _fail("authorization.input", "external review input is absent")
        external_review = external_review_path.read_bytes()
    if source_identity is not None:
        source_commit, source_tree = source_identity
    if source_commit is None or source_tree is None:
        _fail("source.input", "source commit/tree input is absent")
    authorization = _authorization(external_review)
    source_identity = _source_identity(repository_root, source_commit, source_tree)
    freeze = _freeze_v228(repository_root, authorization.authorization_id)
    source = _source_authority(repository_root, freeze, source_identity.source_identity_id)
    replay = _request_replay(repository_root, source)
    identifiability = _identifiability(source)
    recovery = _recovery_population(source, replay, identifiability)
    negative = _negative_controls(source, recovery)
    scope = _scope()
    gate = _gates(
        authorization,
        source_identity,
        freeze,
        source,
        replay,
        identifiability,
        recovery,
        negative,
        scope,
    )
    decision = _make(models.Decision, {"gate_evaluation_id": gate.evaluation_id}, "decision_id")
    transition = _make(models.Transition, {"decision_id": decision.decision_id}, "transition_id")
    report = _make(
        models.Report,
        {
            "authorization_id": authorization.authorization_id,
            "source_identity_id": source_identity.source_identity_id,
            "v228_freeze_id": freeze.freeze_id,
            "source_authority_audit_id": source.audit.audit_id,
            "provider_journal_authority_id": source.journal.audit_id,
            "request_replay_audit_id": replay.audit_id,
            "identifiability_audit_id": identifiability.audit_id,
            "recovery_contract_id": recovery.contract.contract_id,
            "recovery_population_id": recovery.population.population_id,
            "negative_control_audit_id": negative.audit_id,
            "scope_boundary_audit_id": scope.audit_id,
            "gate_evaluation_id": gate.evaluation_id,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
        },
        "report_id",
    )
    payloads: dict[str, bytes] = {
        "external_review.txt": external_review,
        "operator_directive.txt": models.OPERATOR_DIRECTIVE.encode(),
        "external_authorization.json": _encoded(authorization),
        "source_identity.json": _encoded(source_identity),
        "v228_freeze.json": _encoded(freeze),
        "v226_source_authority_audit.json": _encoded(source.audit),
        "provider_journal_authority.json": _encoded(source.journal),
        "request_replay_audit.json": _encoded(replay),
        "identifiability_audit.json": _encoded(identifiability),
        "recovery_contract.json": _encoded(recovery.contract),
        "recovery_population.json": _encoded(recovery.population),
        "negative_control_audit.json": _encoded(negative),
        "scope_boundary_audit.json": _encoded(scope),
        "gate_evaluation.json": _encoded(gate),
        "decision.json": _encoded(decision),
        "transition.json": _encoded(transition),
        "report.json": _encoded(report),
    }
    for row in source.audit.source_rows:
        payloads[f"source_rows/job_{row.job_ordinal:03d}.json"] = _encoded(row)
    for candidate in recovery.candidates:
        payloads[f"recovery_candidates/job_{candidate.job_ordinal:03d}.json"] = _encoded(candidate)
    for job in recovery.population.jobs:
        payloads[f"recovery_jobs/job_{job.candidate.job_ordinal:03d}.json"] = _encoded(job)
    manifest = models.artifact_manifest(payloads)
    payloads["artifact_manifest.json"] = _encoded(manifest)
    _write_payloads(output_dir, payloads)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Finance v26.229 zero-Provider recovery-Population preflight"
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
