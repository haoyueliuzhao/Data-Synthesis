# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_models as v224_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models as v233_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_postrun_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as v229_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as v213_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = models.RUN_ID
OUTPUT_DIR: Final = models.OUTPUT_DIR
V233_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_233_fresh_exact_v209_unbound_provider_failure_recovery_population_"
    "bound_online_execution_v1_20260904"
)
V229_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_"
    "and_recovery_population_preflight_v1_20260904"
)
V226_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_v1_20260904"
)
V213_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_213_fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_v1_20260902"
)
V195_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_"
    "postrun_independent_audit_models.py"
)
AUDIT_FILE: Final = MODELS_FILE.replace("_models.py", ".py")
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUDIT_FILE)))
V233_IMPLEMENTATION_FILES: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py",
)
EXTERNAL_REVIEW_FALLBACK: Final = Path(
    "/home/zhuxinrui/.codex/attachments/515ba512-5135-4e37-a2f3-3b01ea89b1d9/pasted-text.txt"
)


class V234Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V234Error(stage, reason)


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


def _git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ("git", *args), cwd=repository_root, check=False, capture_output=True
    )
    if completed.returncode:
        _fail("source.git", completed.stderr.decode(errors="replace"))
    return completed.stdout


def _make(model_type: type[Any], values: dict[str, Any], field: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=model_type.prefix())


def _exact_bytes(actual: bytes, value: BaseModel, stage: str) -> None:
    if actual != _encoded(value):
        _fail(stage, f"actual bytes differ:{type(value).__name__}")


def _safe_job(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class FrozenExecution:
    root: Path
    files: dict[str, bytes]
    preparation: v233_models.ExecutionPreparation
    consumption: v233_models.AuthorizationConsumptionReceipt
    run_start: v233_models.RecoveryRunStartReceipt
    summary_target: dict[str, Any]
    transition_target: dict[str, Any]
    record_payloads: dict[int, bytes]
    failure_payloads: dict[int, bytes]


@dataclass(frozen=True)
class RecoveryAuthorityData:
    audit: models.RecoveryAuthorityAudit
    source_rows: dict[int, v229_models.V226SourceRow]
    replay_rows: dict[int, v229_models.RequestReplayRow]
    recovery_jobs: dict[int, v229_models.RecoveryPopulationJob]
    historical_prefixes: dict[int, tuple[v224_models.ProviderCallDescriptor, ...]]


@dataclass(frozen=True)
class ProviderJournalData:
    audit: models.ProviderJournalAudit
    calls: dict[int, tuple[v224_models.ProviderCallDescriptor, ...]]
    response_payloads: dict[str, dict[str, Any]]
    error_payloads: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class TerminalData:
    audit: models.TerminalReconstructionAudit
    records: tuple[v233_models.RecoveryJobRecord, ...]


@dataclass(frozen=True)
class FailureData:
    audit: models.FailureReconstructionAudit
    records: tuple[v233_models.RecoveryFailureRecord, ...]


def _external_authorization(review: bytes) -> models.ExternalAuthorization:
    directive = models.OPERATOR_DIRECTIVE.encode()
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.review", "v26.233 external review bytes differ")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.directive", "operator directive bytes differ")
    return _make(models.ExternalAuthorization, {}, "authorization_id")


def _source_members(
    repository_root: Path, commit: str, paths: tuple[str, ...]
) -> tuple[models.SourceMember, ...]:
    rows: list[models.SourceMember] = []
    for relative_path in sorted(paths):
        committed = _git(repository_root, "show", f"{commit}:{relative_path}")
        current = (repository_root / relative_path).read_bytes()
        blob = _git(repository_root, "rev-parse", f"{commit}:{relative_path}").decode().strip()
        if committed != current:
            _fail("source.current_bytes", f"current source differs:{relative_path}")
        rows.append(
            models.SourceMember(
                relative_path=relative_path,
                git_blob_oid=blob,
                sha256=_sha(committed),
                byte_count=len(committed),
            )
        )
    return tuple(rows)


def _source_authority(
    repository_root: Path,
    authorization: models.ExternalAuthorization,
    source_identity: tuple[str, str],
) -> models.SourceAuthorityAudit:
    source_commit, source_tree = source_identity
    pairs = (
        (source_commit, source_tree),
        (models.V233_SOURCE_COMMIT, models.V233_SOURCE_TREE),
    )
    for commit, tree in pairs:
        resolved_commit = (
            _git(repository_root, "rev-parse", f"{commit}^{{commit}}").decode().strip()
        )
        resolved_tree = _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
        if resolved_commit != commit or resolved_tree != tree:
            _fail("source.commit_tree", f"commit/tree relation differs:{commit}")
    implementation_members = _source_members(repository_root, source_commit, IMPLEMENTATION_FILES)
    v233_members = _source_members(
        repository_root, models.V233_SOURCE_COMMIT, V233_IMPLEMENTATION_FILES
    )
    saved_source = v233_models.ExecutionSourceIdentity.model_validate(
        _load(repository_root / V233_DIR / "execution_source_identity.json")
    )
    expected_v233 = tuple((row.relative_path, row.sha256, row.byte_count) for row in v233_members)
    saved_v233 = tuple(
        (row.relative_path, row.sha256, row.byte_count) for row in saved_source.members
    )
    if (
        saved_source.source_commit != models.V233_SOURCE_COMMIT
        or saved_source.source_tree != models.V233_SOURCE_TREE
        or saved_v233 != expected_v233
    ):
        _fail("source.v233_saved", "saved v26.233 source identity differs")
    projection = tuple(row.model_dump(mode="json") for row in implementation_members)
    return _make(
        models.SourceAuthorityAudit,
        {
            "authorization_id": authorization.authorization_id,
            "source_commit": source_commit,
            "source_tree": source_tree,
            "implementation_members": implementation_members,
            "implementation_member_set_sha256": models.canonical_sha256(projection),
            "v233_source_members": v233_members,
        },
        "audit_id",
    )


def _freeze_v233(
    repository_root: Path, source: models.SourceAuthorityAudit
) -> tuple[models.V233ExecutionFreezeAudit, FrozenExecution]:
    root = repository_root / V233_DIR
    files = _files(root)
    if (
        len(files) != models.V233_FILE_COUNT
        or sum(map(len, files.values())) != models.V233_TOTAL_BYTES
    ):
        _fail("freeze.geometry", "v26.233 execution directory geometry differs")
    manifest_name = "execution_artifact_manifest.json"
    manifest_bytes = files.get(manifest_name, b"")
    if (
        len(manifest_bytes) != models.V233_MANIFEST_BYTE_COUNT
        or _sha(manifest_bytes) != models.V233_MANIFEST_SHA256
    ):
        _fail("freeze.manifest_bytes", "v26.233 Manifest bytes differ")
    manifest = v224_models.ArtifactManifest.model_validate_json(manifest_bytes)
    member_files = {name: payload for name, payload in files.items() if name != manifest_name}
    rebuilt = v224_models.artifact_manifest(v233_models.RUN_ID, member_files)
    if (
        manifest.manifest_id != models.V233_MANIFEST_ID
        or manifest.artifact_root != models.V233_ARTIFACT_ROOT
        or manifest.file_count != models.V233_MANIFEST_MEMBER_COUNT
        or manifest.total_byte_count != models.V233_MANIFEST_MEMBER_BYTES
        or _encoded(rebuilt) != manifest_bytes
    ):
        _fail("freeze.manifest", "v26.233 self-excluding Manifest relation differs")
    members = {row.relative_path: row for row in manifest.members}
    if set(members) != set(member_files):
        _fail("freeze.member_paths", "v26.233 Manifest member path set differs")
    for relative_path, payload in member_files.items():
        row = members[relative_path]
        if row.sha256 != _sha(payload) or row.byte_count != len(payload):
            _fail("freeze.member_bytes", f"v26.233 Manifest member differs:{relative_path}")
    preparation = v233_models.ExecutionPreparation.model_validate_json(
        files["execution_preparation.json"]
    )
    consumption = v233_models.AuthorizationConsumptionReceipt.model_validate_json(
        files["authorization_consumption_receipt.json"]
    )
    run_start = v233_models.RecoveryRunStartReceipt.model_validate_json(
        files["recovery_run_start_receipt.json"]
    )
    if (
        consumption.preparation_id != preparation.preparation_id
        or run_start.preparation_id != preparation.preparation_id
        or run_start.consumption_receipt_id != consumption.receipt_id
        or run_start.execution_source_commit != models.V233_SOURCE_COMMIT
        or run_start.execution_source_tree != models.V233_SOURCE_TREE
        or consumption.resulting_consumption_count != 1
    ):
        _fail("freeze.ingress", "v26.233 consumption/Run Start relation differs")
    summary_target = _load_bytes(files["execution_summary.json"])
    transition_target = _load_bytes(files["prospective_transition.json"])
    if (
        summary_target.get("summary_id") != models.V233_SUMMARY_ID
        or transition_target.get("transition_id") != models.V233_TRANSITION_ID
    ):
        _fail("freeze.targets", "v26.233 Summary/Transition identity target differs")
    record_payloads = {
        int(Path(name).stem.split("_")[1]): payload
        for name, payload in files.items()
        if name.startswith("recovery_job_records/job_")
    }
    failure_payloads = {
        int(Path(name).stem.split("_")[1]): payload
        for name, payload in files.items()
        if name.startswith("recovery_failures/job_")
    }
    if (
        tuple(sorted(record_payloads)) != models.TERMINAL_ORDINALS
        or tuple(sorted(failure_payloads)) != models.FAILURE_ORDINALS
    ):
        _fail("freeze.record_paths", "v26.233 terminal/failure file partition differs")
    audit = _make(
        models.V233ExecutionFreezeAudit,
        {
            "source_authority_audit_id": source.audit_id,
            "summary_id": str(summary_target["summary_id"]),
            "transition_id": str(transition_target["transition_id"]),
        },
        "audit_id",
    )
    return audit, FrozenExecution(
        root=root,
        files=files,
        preparation=preparation,
        consumption=consumption,
        run_start=run_start,
        summary_target=summary_target,
        transition_target=transition_target,
        record_payloads=record_payloads,
        failure_payloads=failure_payloads,
    )


def _historical_descriptor(
    v226_root: Path, source_call: v229_models.ProviderCallAuthority
) -> v224_models.ProviderCallDescriptor:
    artifact_parent = Path(source_call.artifact_bindings[0].relative_path).parent
    descriptor_path = artifact_parent / f"call_{source_call.call_ordinal:02d}_descriptor.json"
    descriptor_bytes = (v226_root / descriptor_path).read_bytes()
    descriptor = v224_models.ProviderCallDescriptor.model_validate_json(descriptor_bytes)
    _exact_bytes(descriptor_bytes, descriptor, "recovery.historical_descriptor_bytes")
    pairs = (
        (descriptor.descriptor_id, source_call.descriptor_id),
        (descriptor.provider_call_id, source_call.provider_call_id),
        (descriptor.job_id, source_call.historical_job_id),
        (descriptor.call_ordinal, source_call.call_ordinal),
        (descriptor.status, source_call.status),
        (descriptor.request_sha256, source_call.request_sha256),
        (descriptor.response_sha256, source_call.response_sha256),
        (descriptor.error_sha256, source_call.error_sha256),
        (descriptor.input_tokens, source_call.input_tokens),
        (descriptor.output_tokens, source_call.output_tokens),
    )
    if any(actual != expected for actual, expected in pairs):
        _fail("recovery.historical_descriptor", "historical Provider relation differs")
    bindings = {row.relative_path: row for row in source_call.artifact_bindings}
    artifacts = {row.relative_path: row for row in descriptor.artifacts}
    if set(bindings) != set(artifacts):
        _fail("recovery.historical_artifact_paths", "historical artifact set differs")
    for relative_path, artifact in artifacts.items():
        payload = (v226_root / relative_path).read_bytes()
        binding = bindings[relative_path]
        if (
            artifact.artifact_id != binding.artifact_id
            or artifact.artifact_kind != binding.artifact_kind
            or artifact.sha256 != binding.sha256
            or artifact.byte_count != binding.byte_count
            or artifact.sha256 != _sha(payload)
            or artifact.byte_count != len(payload)
        ):
            _fail("recovery.historical_artifact", f"historical artifact differs:{relative_path}")
    return descriptor


def _record_dicts(frozen: FrozenExecution) -> dict[int, dict[str, Any]]:
    return {
        **{ordinal: _load_bytes(payload) for ordinal, payload in frozen.record_payloads.items()},
        **{ordinal: _load_bytes(payload) for ordinal, payload in frozen.failure_payloads.items()},
    }


def _request_artifact_payload(
    root: Path, descriptor: v224_models.ProviderCallDescriptor
) -> dict[str, Any]:
    artifact = next(row for row in descriptor.artifacts if row.artifact_kind == "request_metadata")
    return _load(root / artifact.relative_path)


def _recovery_authority(
    repository_root: Path,
    frozen_audit: models.V233ExecutionFreezeAudit,
    frozen: FrozenExecution,
) -> RecoveryAuthorityData:
    v229_root = repository_root / V229_DIR
    v226_root = repository_root / V226_DIR
    population = v229_models.RecoveryPopulation.model_validate_json(
        (v229_root / "recovery_population.json").read_bytes()
    )
    replay = v229_models.RequestReplayAudit.model_validate_json(
        (v229_root / "request_replay_audit.json").read_bytes()
    )
    source_rows: dict[int, v229_models.V226SourceRow] = {}
    replay_rows = {row.job_ordinal: row for row in replay.rows}
    recovery_jobs = {row.candidate.job_ordinal: row for row in population.jobs}
    historical_prefixes: dict[int, tuple[v224_models.ProviderCallDescriptor, ...]] = {}
    record_dicts = _record_dicts(frozen)
    rows: list[models.RecoveryAuthorityRow] = []
    for ordinal in models.ALL_ORDINALS:
        source_payload = (v229_root / f"source_rows/job_{ordinal:03d}.json").read_bytes()
        source_row = v229_models.V226SourceRow.model_validate_json(source_payload)
        source_rows[ordinal] = source_row
        replay_row = replay_rows[ordinal]
        recovery_job = recovery_jobs[ordinal]
        candidate_payload = (v229_root / f"recovery_candidates/job_{ordinal:03d}.json").read_bytes()
        job_payload = (v229_root / f"recovery_jobs/job_{ordinal:03d}.json").read_bytes()
        _exact_bytes(source_payload, source_row, "recovery.source_row_bytes")
        _exact_bytes(candidate_payload, recovery_job.candidate, "recovery.candidate_bytes")
        _exact_bytes(job_payload, recovery_job, "recovery.job_bytes")
        failure_payload = (v226_root / source_row.failure_relative_path).read_bytes()
        failure = _load_bytes(failure_payload)
        if (
            len(failure_payload) != source_row.failure_file_byte_count
            or _sha(failure_payload) != source_row.failure_file_sha256
            or failure.get("record_id") != source_row.failure_record_id
            or models.canonical_sha256(failure) != source_row.failure_record_sha256
        ):
            _fail("recovery.v226_failure", f"v26.226 failure relation differs:{ordinal}")
        historical = tuple(
            _historical_descriptor(v226_root, call) for call in source_row.provider_calls
        )
        historical_prefixes[ordinal] = historical[:-1]
        if (
            replay_row.source_row_id != source_row.row_id
            or replay_row.historical_job_id != source_row.historical_job_id
            or replay_row.request_sha256s != tuple(call.request_sha256 for call in historical)
            or replay_row.response_sha256s
            != tuple(cast(str, call.response_sha256) for call in historical[:-1])
            or replay_row.failed_request_sha256 != source_row.failed_request_sha256
            or replay_row.failed_request_byte_count
            != source_row.provider_calls[-1].request_byte_count
        ):
            _fail("recovery.replay", f"v26.229 replay relation differs:{ordinal}")
        candidate = recovery_job.candidate
        if (
            candidate.source_row_id != source_row.row_id
            or candidate.historical_job_id != source_row.historical_job_id
            or candidate.exact_failed_request_sha256 != replay_row.failed_request_sha256
            or candidate.exact_failed_request_byte_count != replay_row.failed_request_byte_count
            or candidate.exact_failed_request_certificate_id
            != replay_row.failed_request_certificate_id
            or candidate.exact_failed_pre_transport_receipt_id
            != replay_row.failed_pre_transport_receipt_id
            or candidate.successful_prefix_call_count != len(historical) - 1
        ):
            _fail("recovery.candidate", f"Recovery Candidate relation differs:{ordinal}")
        fresh_call = v224_models.ProviderCallDescriptor.model_validate(
            record_dicts[ordinal]["provider_calls"][0]
        )
        request_metadata = _request_artifact_payload(frozen.root, fresh_call)
        if (
            fresh_call.request_sha256 != replay_row.failed_request_sha256
            or request_metadata.get("request_byte_count") != replay_row.failed_request_byte_count
            or request_metadata.get("certificate_id") != replay_row.failed_request_certificate_id
            or request_metadata.get("pre_transport_receipt_id")
            != replay_row.failed_pre_transport_receipt_id
        ):
            _fail("recovery.handoff", f"first fresh request handoff differs:{ordinal}")
        phase = replay_row.phases[-1]
        if phase not in {"first_action", "subsequent_action", "final"}:
            _fail("recovery.phase", f"captured failed phase differs:{ordinal}")
        rows.append(
            _make(
                models.RecoveryAuthorityRow,
                {
                    "job_ordinal": ordinal,
                    "historical_job_id": source_row.historical_job_id,
                    "recovery_candidate_id": candidate.candidate_id,
                    "recovery_job_id": recovery_job.recovery_job_id,
                    "source_row_id": source_row.row_id,
                    "failed_request_phase": phase,
                    "successful_prefix_projection_count": len(historical) - 1,
                    "historical_prefix_descriptor_count": len(historical) - 1,
                    "captured_failed_request_sha256": replay_row.failed_request_sha256,
                    "captured_failed_request_byte_count": replay_row.failed_request_byte_count,
                    "first_fresh_provider_call_id": fresh_call.provider_call_id,
                    "historical_prefix_actual_byte_matches": len(historical) - 1,
                },
                "row_id",
            )
        )
    source_ids = tuple(row.source_row_id for row in rows)
    audit = _make(
        models.RecoveryAuthorityAudit,
        {
            "v233_freeze_audit_id": frozen_audit.audit_id,
            "rows": tuple(rows),
            "exact_source_set_sha256": models.canonical_sha256(source_ids),
        },
        "audit_id",
    )
    return RecoveryAuthorityData(
        audit=audit,
        source_rows=source_rows,
        replay_rows=replay_rows,
        recovery_jobs=recovery_jobs,
        historical_prefixes=historical_prefixes,
    )


def _actual_provider_call(
    root: Path, embedded: v224_models.ProviderCallDescriptor
) -> tuple[v224_models.ProviderCallDescriptor, dict[str, dict[str, Any]]]:
    parents = {Path(row.relative_path).parent for row in embedded.artifacts}
    if len(parents) != 1:
        _fail("provider.directory", "Provider descriptor crosses artifact directories")
    parent = next(iter(parents))
    descriptor_path = parent / f"call_{embedded.call_ordinal:02d}_descriptor.json"
    descriptor_bytes = (root / descriptor_path).read_bytes()
    actual = v224_models.ProviderCallDescriptor.model_validate_json(descriptor_bytes)
    if actual != embedded or descriptor_bytes != _encoded(actual):
        _fail("provider.descriptor", f"Provider descriptor bytes differ:{descriptor_path}")
    payloads: dict[str, dict[str, Any]] = {}
    for artifact in actual.artifacts:
        payload_bytes = (root / artifact.relative_path).read_bytes()
        if artifact.sha256 != _sha(payload_bytes) or artifact.byte_count != len(payload_bytes):
            _fail("provider.artifact", f"Provider artifact bytes differ:{artifact.relative_path}")
        payloads[artifact.artifact_kind] = _load_bytes(payload_bytes)
    if set(payloads) != (
        {"request_metadata", "response_metadata", "usage_metadata"}
        if actual.status == "succeeded"
        else {"request_metadata", "error_metadata", "usage_metadata"}
    ):
        _fail("provider.artifact_shape", "Provider artifact kind set differs")
    request = payloads["request_metadata"]
    if (
        request.get("provider_call_authorized") is not True
        or request.get("retry_authorized") is not False
        or request.get("raw_request_persisted") is not False
        or request.get("job_id") != actual.job_id
        or request.get("call_ordinal") != actual.call_ordinal
        or request.get("request_sha256") != actual.request_sha256
        or request.get("run_start_receipt_id") != actual.run_start_receipt_id
    ):
        _fail("provider.request_metadata", "Provider request metadata differs")
    outcome = payloads["response_metadata" if actual.status == "succeeded" else "error_metadata"]
    if (
        outcome.get("provider_call_id") != actual.provider_call_id
        or outcome.get("raw_provider_response_persisted") is not False
        or outcome.get("private_reasoning_persisted") is not False
    ):
        _fail("provider.outcome_metadata", "Provider outcome metadata differs")
    if actual.status == "succeeded":
        if (
            outcome.get("public_projection_sha256") != actual.response_sha256
            or models.canonical_sha256(outcome.get("public_projection")) != actual.response_sha256
        ):
            _fail("provider.response_metadata", "Provider response metadata differs")
    elif outcome.get("error_sha256") != actual.error_sha256 or outcome.get("error_type") is None:
        _fail("provider.error_metadata", "Provider error metadata differs")
    usage = payloads["usage_metadata"]
    telemetry = usage.get("telemetry", {})
    if (
        usage.get("provider_call_id") != actual.provider_call_id
        or telemetry.get("request_hash") != actual.request_sha256
        or telemetry.get("prompt_tokens") != actual.input_tokens
        or telemetry.get("completion_tokens") != actual.output_tokens
        or telemetry.get("total_tokens") != actual.input_tokens + actual.output_tokens
    ):
        _fail("provider.usage_metadata", "Provider Usage metadata differs")
    return actual, payloads


def _provider_journal(
    frozen: FrozenExecution, authority: RecoveryAuthorityData
) -> ProviderJournalData:
    all_records = _record_dicts(frozen)
    rows: list[models.ProviderCallAuditRow] = []
    calls: dict[int, tuple[v224_models.ProviderCallDescriptor, ...]] = {}
    response_payloads: dict[str, dict[str, Any]] = {}
    error_payloads: dict[str, dict[str, Any]] = {}
    descriptor_paths: set[str] = set()
    artifact_paths: set[str] = set()
    per_job: Counter[int] = Counter()
    for ordinal in models.ALL_ORDINALS:
        embedded_calls = tuple(
            v224_models.ProviderCallDescriptor.model_validate(row)
            for row in all_records[ordinal]["provider_calls"]
        )
        if tuple(row.call_ordinal for row in embedded_calls) != tuple(
            range(len(embedded_calls))
        ) or any(
            row.job_id != authority.recovery_jobs[ordinal].recovery_job_id for row in embedded_calls
        ):
            _fail("provider.call_geometry", f"Provider call geometry differs:{ordinal}")
        calls[ordinal] = embedded_calls
        per_job[len(embedded_calls)] += 1
        for call in embedded_calls:
            actual, payloads = _actual_provider_call(frozen.root, call)
            parent = Path(actual.artifacts[0].relative_path).parent
            descriptor_paths.add(
                (parent / f"call_{actual.call_ordinal:02d}_descriptor.json").as_posix()
            )
            artifact_paths.update(row.relative_path for row in actual.artifacts)
            outcome = payloads[
                "response_metadata" if actual.status == "succeeded" else "error_metadata"
            ]
            if actual.status == "succeeded":
                response_payloads[actual.provider_call_id] = outcome
                error_type = None
            else:
                error_payloads[actual.provider_call_id] = outcome
                error_type = str(outcome["error_type"])
            request = payloads["request_metadata"]
            rows.append(
                _make(
                    models.ProviderCallAuditRow,
                    {
                        "job_ordinal": ordinal,
                        "recovery_job_id": actual.job_id,
                        "provider_call_id": actual.provider_call_id,
                        "descriptor_id": actual.descriptor_id,
                        "call_ordinal": actual.call_ordinal,
                        "status": actual.status,
                        "request_sha256": actual.request_sha256,
                        "response_sha256": actual.response_sha256,
                        "error_sha256": actual.error_sha256,
                        "error_type": error_type,
                        "input_tokens": actual.input_tokens,
                        "output_tokens": actual.output_tokens,
                        "first_fresh_captured_request_handoff": actual.call_ordinal == 0,
                        "retry_authorized": cast(bool, request["retry_authorized"]),
                    },
                    "row_id",
                )
            )
    actual_descriptor_paths = {
        path.relative_to(frozen.root).as_posix()
        for path in (frozen.root / "provider_calls").rglob("call_*_descriptor.json")
    }
    actual_artifact_paths = {
        path.relative_to(frozen.root).as_posix()
        for path in (frozen.root / "provider_calls").rglob("call_*_metadata.json")
    }
    if descriptor_paths != actual_descriptor_paths or artifact_paths != actual_artifact_paths:
        _fail("provider.complete_set", "Provider descriptor/artifact set is not exact")
    error_types = Counter(row.error_type for row in rows if row.error_type is not None)
    audit = _make(
        models.ProviderJournalAudit,
        {
            "recovery_authority_audit_id": authority.audit.audit_id,
            "rows": tuple(rows),
            "reasoning_budget_error_count": error_types["ReasoningBudgetExhaustedError"],
            "json_decode_error_count": error_types["JSONDecodeError"],
            "per_job_call_count_distribution": dict(sorted(per_job.items())),
        },
        "audit_id",
    )
    return ProviderJournalData(
        audit=audit,
        calls=calls,
        response_payloads=response_payloads,
        error_payloads=error_payloads,
    )


def _terminal_policy_authority(repository_root: Path) -> tuple[str, str, dict[str, str]]:
    registry = _load(repository_root / V195_DIR / "fresh_terminal_registry.json")
    dispatcher = v213_models.ObservationDerivedDispatcherBinding.model_validate(
        _load(repository_root / V213_DIR / "observation_derived_dispatcher_binding.json")
    )
    persistence = v213_models.ObservationBoundPersistenceBinding.model_validate(
        _load(repository_root / V213_DIR / "observation_bound_persistence_binding.json")
    )
    policies = {
        str(row["terminal_kind"]): str(row["policy_id"])
        for row in registry["policies"]
        if row["registration_status"] == "reachable"
    }
    if registry.get("registry_id") != dispatcher.source_v195_terminal_registry_id or set(
        dispatcher.terminal_kinds
    ) != set(policies):
        _fail("terminal.policy_authority", "Registry/Dispatcher terminal authority differs")
    return dispatcher.binding_id, persistence.binding_id, policies


def _derive_terminal_decision(
    evidence: Any, dispatcher_id: str, policies: dict[str, str]
) -> v213_models.DerivedTerminalDecision:
    if isinstance(evidence, v213_models.CompletedRunnerEvidence):
        terminal = "completed_qualified" if evidence.qualified_valid else "completed_invalid"
        rule = "final_base_and_mechanism_conjunction"
    elif isinstance(evidence, v213_models.FinalParserRejectionEvidence):
        terminal = "final_response_abi_invalid"
        rule = "final_parser_validation_rejection"
    else:
        _fail("terminal.evidence_kind", f"unadmitted terminal evidence:{type(evidence).__name__}")
    return v213_models.DerivedTerminalDecision.model_validate(
        {
            "decision_id": canonical_hash(
                {
                    "dispatcher_binding_id": dispatcher_id,
                    "evidence_id": evidence.evidence_id,
                    "evidence_sha256": models.canonical_sha256(evidence),
                    "job_id": evidence.job_id,
                    "terminal_kind": terminal,
                    "terminal_policy_id": policies[terminal],
                    "derivation_rule": rule,
                    "terminal_label_was_input": False,
                    "provider_calls": 0,
                    "schema_version": v213_models.SCHEMA_VERSION,
                },
                prefix="fresh_repaired_derived_terminal_decision:",
            ),
            "dispatcher_binding_id": dispatcher_id,
            "evidence_id": evidence.evidence_id,
            "evidence_sha256": models.canonical_sha256(evidence),
            "job_id": evidence.job_id,
            "terminal_kind": terminal,
            "terminal_policy_id": policies[terminal],
            "derivation_rule": rule,
            "terminal_label_was_input": False,
            "provider_calls": 0,
            "schema_version": v213_models.SCHEMA_VERSION,
        }
    )


def _layer_namespace(recovery_job_id: str, kind: str) -> str:
    return canonical_hash(
        {
            "recovery_job_id": recovery_job_id,
            "layer_kind": kind,
            "schema_version": v233_models.SCHEMA_VERSION,
        },
        prefix=f"finance_v26_233_recovery_{kind}_namespace:",
    )


def _layer_descriptor(
    *,
    frozen: FrozenExecution,
    recovery_job: v229_models.RecoveryPopulationJob,
    kind: str,
    sequence: int,
    terminal_kind: str,
    terminal_source: str,
    parents: tuple[v233_models.RecoveryLayerDescriptor, ...],
    provider_calls: tuple[v224_models.ProviderCallDescriptor, ...],
    payload: dict[str, Any],
) -> v233_models.RecoveryLayerDescriptor:
    relative_path = f"recovery_evidence/{kind}/{_safe_job(recovery_job.recovery_job_id)}.json"
    payload_bytes = _encoded(payload)
    actual_payload = frozen.files.get(relative_path)
    if actual_payload != payload_bytes:
        _fail("terminal.layer_payload", f"Recovery layer payload differs:{relative_path}")
    return v233_models.make_identity(
        v233_models.RecoveryLayerDescriptor,
        {
            "run_start_receipt_id": frozen.run_start.receipt_id,
            "recovery_job_id": recovery_job.recovery_job_id,
            "historical_job_id": recovery_job.candidate.historical_job_id,
            "job_ordinal": recovery_job.candidate.job_ordinal,
            "layer_kind": kind,
            "namespace_id": _layer_namespace(recovery_job.recovery_job_id, kind),
            "relative_path": relative_path,
            "terminal_kind": terminal_kind,
            "terminal_source": terminal_source,
            "parent_descriptor_ids": tuple(row.descriptor_id for row in parents),
            "provider_call_descriptor_ids": tuple(row.descriptor_id for row in provider_calls),
            "payload_sha256": _sha(payload_bytes),
            "payload_byte_count": len(payload_bytes),
            "persisted_sequence": sequence,
        },
        field="descriptor_id",
        prefix=v233_models.RecoveryLayerDescriptor.prefix(),
    )


def _terminal_reconstruction(
    repository_root: Path,
    frozen: FrozenExecution,
    authority: RecoveryAuthorityData,
    journal: ProviderJournalData,
) -> TerminalData:
    dispatcher_id, persistence_id, policies = _terminal_policy_authority(repository_root)
    rows: list[models.TerminalReconstructionRow] = []
    records: list[v233_models.RecoveryJobRecord] = []
    for ordinal in models.TERMINAL_ORDINALS:
        record = v233_models.RecoveryJobRecord.model_validate_json(frozen.record_payloads[ordinal])
        recovery_job = authority.recovery_jobs[ordinal]
        replay = authority.replay_rows[ordinal]
        calls = journal.calls[ordinal]
        raw_path = record.layers[0].relative_path
        raw = _load_bytes(frozen.files[raw_path])
        invocation_values = tuple(raw["invocation_records"])
        invocations = tuple(
            v209_models.ExecutableInvocationRecord.model_validate(value)
            for value in invocation_values
        )
        if (
            tuple(row.invocation_index for row in invocations) != tuple(range(len(invocations)))
            or any(row.job_id != recovery_job.candidate.historical_job_id for row in invocations)
            or len(invocations) != replay.successful_prefix_call_count + len(calls)
        ):
            _fail("terminal.invocations", f"terminal invocation geometry differs:{ordinal}")
        historic = authority.historical_prefixes[ordinal]
        for index, invocation in enumerate(invocations):
            descriptor = historic[index] if index < len(historic) else calls[index - len(historic)]
            expected_response = descriptor.response_sha256
            if (
                invocation.canonical_request_body_sha256 != descriptor.request_sha256
                or invocation.certificate_id
                != _request_artifact_payload(
                    repository_root / (V226_DIR if index < len(historic) else V233_DIR),
                    descriptor,
                )["certificate_id"]
                or invocation.pre_transport_receipt_id
                != _request_artifact_payload(
                    repository_root / (V226_DIR if index < len(historic) else V233_DIR),
                    descriptor,
                )["pre_transport_receipt_id"]
                or invocation.public_response_sha256 != expected_response
                or expected_response is None
            ):
                _fail("terminal.invocation_authority", f"invocation authority differs:{ordinal}")
        evidence = v213_models.OBSERVED_EVIDENCE_ADAPTER.validate_python(raw["observed_evidence"])
        decision = _derive_terminal_decision(evidence, dispatcher_id, policies)
        saved_decision = v213_models.DerivedTerminalDecision.model_validate(
            raw["derived_terminal_decision"]
        )
        if (
            models.canonical_bytes(evidence) != models.canonical_bytes(raw["observed_evidence"])
            or models.canonical_bytes(decision) != models.canonical_bytes(saved_decision)
            or decision.terminal_kind != record.terminal_kind
            or record.terminal_source != "current_state_runner_observation"
        ):
            _fail("terminal.derivation", f"terminal derivation differs:{ordinal}")
        common = {
            "run_start_receipt_id": frozen.run_start.receipt_id,
            "authorization_id": v233_models.AUTHORIZATION_ID,
            "recovery_job_id": recovery_job.recovery_job_id,
            "recovery_candidate_id": recovery_job.candidate.candidate_id,
            "historical_job_id": recovery_job.candidate.historical_job_id,
            "job_ordinal": ordinal,
            "successful_prefix_projection_count": replay.successful_prefix_call_count,
            "successful_prefix_provider_reissue_count": 0,
            "exact_failed_request_reissue_count": 1,
            "terminal_kind": decision.terminal_kind,
            "terminal_source": "current_state_runner_observation",
            "formal_empirical_row": False,
            "historical_v26_226_mutation": False,
            "schema_version": v233_models.SCHEMA_VERSION,
        }
        raw_descriptor = _layer_descriptor(
            frozen=frozen,
            recovery_job=recovery_job,
            kind="raw",
            sequence=0,
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            parents=(),
            provider_calls=calls,
            payload={
                **common,
                "persistence_binding_id": persistence_id,
                "source_row_id": replay.source_row_id,
                "observed_evidence": evidence.model_dump(mode="json", warnings=False),
                "derived_terminal_decision": decision.model_dump(mode="json", warnings=False),
                "invocation_records": invocation_values,
                "fresh_provider_calls": tuple(
                    row.model_dump(mode="json", warnings=False) for row in calls
                ),
            },
        )
        result_descriptor = _layer_descriptor(
            frozen=frozen,
            recovery_job=recovery_job,
            kind="result",
            sequence=1,
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            parents=(raw_descriptor,),
            provider_calls=calls,
            payload={**common, "raw_descriptor": raw_descriptor.model_dump(mode="json")},
        )
        trace_descriptor = _layer_descriptor(
            frozen=frozen,
            recovery_job=recovery_job,
            kind="trace",
            sequence=2,
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            parents=(raw_descriptor, result_descriptor),
            provider_calls=calls,
            payload={
                **common,
                "raw_descriptor": raw_descriptor.model_dump(mode="json"),
                "result_descriptor": result_descriptor.model_dump(mode="json"),
                "invocation_records": invocation_values,
                "fresh_provider_calls": tuple(
                    row.model_dump(mode="json", warnings=False) for row in calls
                ),
            },
        )
        outcome_descriptor = _layer_descriptor(
            frozen=frozen,
            recovery_job=recovery_job,
            kind="outcome",
            sequence=3,
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            parents=(trace_descriptor,),
            provider_calls=calls,
            payload={**common, "trace_descriptor": trace_descriptor.model_dump(mode="json")},
        )
        checkpoint_descriptor = _layer_descriptor(
            frozen=frozen,
            recovery_job=recovery_job,
            kind="checkpoint",
            sequence=4,
            terminal_kind=decision.terminal_kind,
            terminal_source="current_state_runner_observation",
            parents=(outcome_descriptor,),
            provider_calls=calls,
            payload={**common, "outcome_descriptor": outcome_descriptor.model_dump(mode="json")},
        )
        layers = (
            raw_descriptor,
            result_descriptor,
            trace_descriptor,
            outcome_descriptor,
            checkpoint_descriptor,
        )
        if tuple(row.model_dump(mode="json") for row in layers) != tuple(
            row.model_dump(mode="json") for row in record.layers
        ):
            _fail("terminal.layer_descriptors", f"layer descriptors differ:{ordinal}")
        rebuilt_record = v233_models.make_identity(
            v233_models.RecoveryJobRecord,
            {
                "run_start_receipt_id": frozen.run_start.receipt_id,
                "authorization_id": v233_models.AUTHORIZATION_ID,
                "recovery_job_id": recovery_job.recovery_job_id,
                "recovery_candidate_id": recovery_job.candidate.candidate_id,
                "historical_job_id": recovery_job.candidate.historical_job_id,
                "job_ordinal": ordinal,
                "failed_request_phase": replay.phases[-1],
                "successful_prefix_projection_count": replay.successful_prefix_call_count,
                "provider_calls": calls,
                "terminal_kind": decision.terminal_kind,
                "terminal_source": "current_state_runner_observation",
                "invocation_record_count": len(invocations),
                "layers": layers,
            },
            field="record_id",
            prefix=v233_models.RecoveryJobRecord.prefix(),
        )
        _exact_bytes(frozen.record_payloads[ordinal], rebuilt_record, "terminal.record_bytes")
        records.append(rebuilt_record)
        rows.append(
            _make(
                models.TerminalReconstructionRow,
                {
                    "job_ordinal": ordinal,
                    "recovery_job_id": recovery_job.recovery_job_id,
                    "historical_job_id": recovery_job.candidate.historical_job_id,
                    "evidence_kind": evidence.evidence_kind,
                    "evidence_id": evidence.evidence_id,
                    "decision_id": decision.decision_id,
                    "terminal_kind": decision.terminal_kind,
                    "terminal_policy_id": decision.terminal_policy_id,
                    "derivation_rule": decision.derivation_rule,
                    "invocation_record_count": len(invocations),
                    "successful_prefix_projection_count": replay.successful_prefix_call_count,
                    "fresh_provider_call_count": len(calls),
                    "invocation_public_projection_matches": len(invocations),
                    "layer_descriptor_ids": tuple(row.descriptor_id for row in layers),
                },
                "row_id",
            )
        )
    audit = _make(
        models.TerminalReconstructionAudit,
        {"provider_journal_audit_id": journal.audit.audit_id, "rows": tuple(rows)},
        "audit_id",
    )
    return TerminalData(audit=audit, records=tuple(records))


def _failure_reconstruction(
    frozen: FrozenExecution,
    authority: RecoveryAuthorityData,
    journal: ProviderJournalData,
) -> FailureData:
    rows: list[models.FailureReconstructionRow] = []
    records: list[v233_models.RecoveryFailureRecord] = []
    for ordinal in models.FAILURE_ORDINALS:
        saved = v233_models.RecoveryFailureRecord.model_validate_json(
            frozen.failure_payloads[ordinal]
        )
        recovery_job = authority.recovery_jobs[ordinal]
        replay = authority.replay_rows[ordinal]
        calls = journal.calls[ordinal]
        if any(row.status != "succeeded" for row in calls[:-1]) or calls[-1].status == "succeeded":
            _fail("failure.call_partition", f"failure call partition differs:{ordinal}")
        error = journal.error_payloads[calls[-1].provider_call_id]
        redacted = cast(dict[str, Any], error["redacted_response_fields"])
        if (
            error["error_type"] not in {"ReasoningBudgetExhaustedError", "JSONDecodeError"}
            or saved.failure_kind != "unbound_provider_failure"
            or saved.terminal_evidence_admitted
            or saved.five_layer_evidence_admitted
        ):
            _fail("failure.semantic_boundary", f"failure semantic boundary differs:{ordinal}")
        rebuilt = v233_models.make_identity(
            v233_models.RecoveryFailureRecord,
            {
                "run_start_receipt_id": frozen.run_start.receipt_id,
                "authorization_id": v233_models.AUTHORIZATION_ID,
                "recovery_job_id": recovery_job.recovery_job_id,
                "recovery_candidate_id": recovery_job.candidate.candidate_id,
                "historical_job_id": recovery_job.candidate.historical_job_id,
                "job_ordinal": ordinal,
                "failed_request_phase": replay.phases[-1],
                "successful_prefix_projection_count": replay.successful_prefix_call_count,
                "provider_calls": calls,
                "failure_kind": "unbound_provider_failure",
                "error_sha256": authority.source_rows[ordinal].job_error_sha256,
            },
            field="record_id",
            prefix=v233_models.RecoveryFailureRecord.prefix(),
        )
        _exact_bytes(frozen.failure_payloads[ordinal], rebuilt, "failure.record_bytes")
        records.append(rebuilt)
        rows.append(
            _make(
                models.FailureReconstructionRow,
                {
                    "job_ordinal": ordinal,
                    "recovery_job_id": recovery_job.recovery_job_id,
                    "historical_job_id": recovery_job.candidate.historical_job_id,
                    "failed_request_phase": replay.phases[-1],
                    "fresh_provider_call_count": len(calls),
                    "final_call_ordinal": calls[-1].call_ordinal,
                    "final_provider_call_id": calls[-1].provider_call_id,
                    "final_error_type": error["error_type"],
                    "final_error_sha256": error["error_sha256"],
                    "completion_tokens": redacted["completion_tokens"],
                    "reasoning_tokens": redacted["reasoning_tokens"],
                    "response_model": redacted["response_model"],
                },
                "row_id",
            )
        )
    audit = _make(
        models.FailureReconstructionAudit,
        {"provider_journal_audit_id": journal.audit.audit_id, "rows": tuple(rows)},
        "audit_id",
    )
    return FailureData(audit=audit, records=tuple(records))


def _exact_partition(
    frozen: FrozenExecution,
    authority: RecoveryAuthorityData,
    journal: ProviderJournalData,
    terminal: TerminalData,
    failure: FailureData,
) -> models.ExactPartitionAudit:
    records = terminal.records
    failures = failure.records
    calls = tuple(call for item in (*records, *failures) for call in item.provider_calls)
    terminal_partition = {kind: 0 for kind in v224_models.TERMINAL_KINDS}
    for row in records:
        terminal_partition[row.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for row in failures:
        failure_partition[row.failure_kind] += 1
    phase_partition = {"first_action": 0, "subsequent_action": 0, "final": 0}
    for row in (*records, *failures):
        phase_partition[row.failed_request_phase] += 1
    summary = v233_models.make_identity(
        v233_models.ExecutionSummary,
        {
            "preparation_id": frozen.preparation.preparation_id,
            "consumption_receipt_id": frozen.consumption.receipt_id,
            "run_start_receipt_id": frozen.run_start.receipt_id,
            "execution_status": "incomplete",
            "records": records,
            "failures": failures,
            "terminal_record_count": len(records),
            "failure_record_count": len(failures),
            "provider_call_count": len(calls),
            "input_tokens": sum(row.input_tokens for row in calls),
            "output_tokens": sum(row.output_tokens for row in calls),
            "terminal_partition": terminal_partition,
            "failure_partition": failure_partition,
            "failed_request_phase_partition": phase_partition,
            "five_layer_file_count": len(records) * 5,
        },
        field="summary_id",
        prefix=v233_models.ExecutionSummary.prefix(),
    )
    transition = v233_models.make_identity(
        v233_models.Transition,
        {
            "summary_id": summary.summary_id,
            "execution_status": "incomplete",
            "status": "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
        },
        field="transition_id",
        prefix=v233_models.Transition.prefix(),
    )
    if (
        _encoded(summary) != frozen.files["execution_summary.json"]
        or _encoded(transition) != frozen.files["prospective_transition.json"]
    ):
        _fail("partition.saved_targets", "independently rebuilt Summary/Transition differs")
    return _make(
        models.ExactPartitionAudit,
        {
            "recovery_authority_audit_id": authority.audit.audit_id,
            "terminal_audit_id": terminal.audit.audit_id,
            "failure_audit_id": failure.audit.audit_id,
            "exact_job_ordinals": models.ALL_ORDINALS,
            "terminal_ordinals": models.TERMINAL_ORDINALS,
            "failure_ordinals": models.FAILURE_ORDINALS,
            "terminal_partition": terminal_partition,
            "failure_partition": failure_partition,
            "failed_request_phase_partition": phase_partition,
        },
        "audit_id",
    )


def _scope(
    repository_root: Path, partition: models.ExactPartitionAudit
) -> models.ScopeBoundaryAudit:
    tree = ast.parse((repository_root / AUDIT_FILE).read_text())
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    called_names = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden_import = (
        "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution"
    )
    forbidden_calls = {
        "prepare_execution",
        "execute",
        "_execute_job",
        "_persist_chain",
        "_derive_recovery_terminal",
        "complete_body",
        "complete_json",
        "urlopen",
    }
    if (
        any(name.endswith(forbidden_import) for name in imported_modules)
        or forbidden_import in imported_names
        or called_names & forbidden_calls
    ):
        _fail("scope.implementation", "external-execution or candidate-helper boundary differs")
    return _make(
        models.ScopeBoundaryAudit,
        {"exact_partition_audit_id": partition.audit_id},
        "audit_id",
    )


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(output_dir)
    review = external_review_path.read_bytes()
    authorization = _external_authorization(review)
    source = _source_authority(repository_root, authorization, source_identity)
    freeze, frozen = _freeze_v233(repository_root, source)
    recovery = _recovery_authority(repository_root, freeze, frozen)
    provider = _provider_journal(frozen, recovery)
    terminal = _terminal_reconstruction(repository_root, frozen, recovery, provider)
    failure = _failure_reconstruction(frozen, recovery, provider)
    partition = _exact_partition(frozen, recovery, provider, terminal, failure)
    scope = _scope(repository_root, partition)
    gate = _make(
        models.GateEvaluation,
        {
            "rows": (
                models.GateRow(gate="A0", description="exact external scope and source authority"),
                models.GateRow(gate="A1", description="actual Manifest and all 380 members"),
                models.GateRow(gate="A2", description="33 source rows, 55 prefixes, 33 handoffs"),
                models.GateRow(
                    gate="A3", description="64 actual Provider descriptors and artifacts"
                ),
                models.GateRow(gate="A4", description="16 terminals and 80 five-layer files"),
                models.GateRow(gate="A5", description="17 failures and exact 33-record partition"),
                models.GateRow(
                    gate="A6", description="zero Provider, mutation, backfill, estimate"
                ),
            )
        },
        "gate_id",
    )
    decision = _make(
        models.IndependentAuditDecision,
        {
            "gate_id": gate.gate_id,
            "decision": (
                "v26_233_exact_33_job_recovery_attempt_execution_independently_confirmed_"
                "terminal_evidence_set_incomplete"
            ),
        },
        "decision_id",
    )
    transition = _make(models.Transition, {"decision_id": decision.decision_id}, "transition_id")
    report = _make(
        models.Report,
        {
            "authorization_id": authorization.authorization_id,
            "source_authority_audit_id": source.audit_id,
            "v233_freeze_audit_id": freeze.audit_id,
            "recovery_authority_audit_id": recovery.audit.audit_id,
            "provider_journal_audit_id": provider.audit.audit_id,
            "terminal_reconstruction_audit_id": terminal.audit.audit_id,
            "failure_reconstruction_audit_id": failure.audit.audit_id,
            "exact_partition_audit_id": partition.audit_id,
            "scope_audit_id": scope.audit_id,
            "gate_id": gate.gate_id,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
        },
        "report_id",
    )
    payloads = {
        "external_review.txt": review,
        "operator_directive.txt": models.OPERATOR_DIRECTIVE.encode(),
        "external_authorization.json": _encoded(authorization),
        "source_authority_audit.json": _encoded(source),
        "v233_execution_freeze_audit.json": _encoded(freeze),
        "recovery_authority_audit.json": _encoded(recovery.audit),
        "provider_journal_audit.json": _encoded(provider.audit),
        "terminal_reconstruction_audit.json": _encoded(terminal.audit),
        "failure_reconstruction_audit.json": _encoded(failure.audit),
        "exact_partition_audit.json": _encoded(partition),
        "scope_boundary_audit.json": _encoded(scope),
        "gate_evaluation.json": _encoded(gate),
        "independent_audit_decision.json": _encoded(decision),
        "prospective_transition.json": _encoded(transition),
        "independent_audit_report.json": _encoded(report),
    }
    manifest = models.artifact_manifest(payloads)
    output_dir.mkdir(parents=True)
    for name, payload in payloads.items():
        _write(output_dir / name, payload)
    _write(output_dir / "artifact_manifest.json", _encoded(manifest))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-review", type=Path, default=EXTERNAL_REVIEW_FALLBACK)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-tree")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    commit = args.source_commit or _git(root, "rev-parse", "HEAD").decode().strip()
    tree = args.source_tree or _git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    output = args.output_dir or root / OUTPUT_DIR
    report = build(
        repository_root=root,
        output_dir=output,
        external_review_path=args.external_review,
        source_identity=(commit, tree),
    )
    print(models.canonical_bytes(report).decode())


if __name__ == "__main__":
    main()
