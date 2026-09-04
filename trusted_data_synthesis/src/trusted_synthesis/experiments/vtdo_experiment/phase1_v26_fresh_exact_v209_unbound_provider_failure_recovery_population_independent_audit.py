# ruff: noqa: E501, SLF001
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
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
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = models.RUN_ID
OUTPUT_DIR: Final = models.OUTPUT_DIR
V229_DIR: Final = models.V229_DIR
V226_DIR: Final = models.V226_DIR
V229_MODULE: Final = (
    "trusted_synthesis.experiments.vtdo_experiment."
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_"
    "recovery_population_preflight"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_"
    "independent_audit_models.py"
)
AUDIT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_"
    "independent_audit.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUDIT_FILE)))
V209_COMMIT: Final = "5809e9782515e55ee797b43730584d5d860aaa5c"
V226_COMMIT: Final = "a52df3e215f681a855bfdc94aafe9d699f08a59c"
V209_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_"
    "repair_preflight.py"
)
V209_MODELS_FILE: Final = V209_FILE.replace("_preflight.py", "_preflight_models.py")
V226_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair.py"
)
V226_MODELS_FILE: Final = V226_FILE.replace(".py", "_models.py")
FROZEN_RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime.py"
)
STEP_RUNTIME_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_all_typed_rejection_public_feedback_runtime.py"
)
DEPENDENCY_FILES: Final = tuple(
    sorted(
        (
            V209_FILE,
            V209_MODELS_FILE,
            V226_FILE,
            V226_MODELS_FILE,
            FROZEN_RUNTIME_FILE,
            STEP_RUNTIME_FILE,
        )
    )
)
V226_FILE_COUNT: Final = 3_428
V226_TOTAL_BYTES: Final = 99_765_014
V226_MEMBER_COUNT: Final = 3_427
V226_MEMBER_BYTES: Final = 99_047_004


class V230Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V230Error(stage, reason)


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


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ("git", *args), cwd=root, input=input_bytes, check=False, capture_output=True
    )
    if completed.returncode:
        _fail("source.git", completed.stderr.decode(errors="replace"))
    return completed.stdout


def _make(model_type: type[Any], values: dict[str, Any], field: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=model_type.prefix())


def _content_id(value: dict[str, Any], field: str, prefix: str) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != field}, prefix=prefix)


def _identified(value: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = _content_id(result, field, prefix)
    return result


def _verify_manifest(
    root: Path,
    name: str,
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
    manifest = _load_bytes(files.get(name, b""))
    members = {str(row["relative_path"]): row for row in manifest.get("members", ())}
    if (
        manifest.get("manifest_id") != manifest_id
        or manifest.get("artifact_root") != artifact_root
        or manifest.get("self_excluding") is not True
        or manifest.get("total_member_bytes") != member_bytes
        or len(members) != member_count
        or set(members) != set(files) - {name}
    ):
        _fail("freeze.manifest", f"Manifest relation differs:{root}")
    for relative_path, row in members.items():
        payload = files[relative_path]
        if row.get("sha256") != _sha(payload) or row.get("byte_count") != len(payload):
            _fail("freeze.member", f"Manifest member differs:{relative_path}")
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


def _source_identity(
    repository_root: Path, source_identity: tuple[str, str]
) -> models.SourceIdentity:
    commit, tree = source_identity
    resolved_commit = _git(repository_root, "rev-parse", f"{commit}^{{commit}}").decode().strip()
    resolved_tree = _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    if resolved_commit != commit or resolved_tree != tree:
        _fail("source.commit_tree", "independent audit commit/tree relation differs")
    members: list[models.SourceMember] = []
    for relative_path in IMPLEMENTATION_FILES:
        committed = _git(repository_root, "show", f"{commit}:{relative_path}")
        current = (repository_root / relative_path).read_bytes()
        oid = _git(repository_root, "rev-parse", f"{commit}:{relative_path}").decode().strip()
        if committed != current:
            _fail("source.current_bytes", f"current source differs:{relative_path}")
        members.append(
            models.SourceMember(
                relative_path=relative_path,
                git_blob_oid=oid,
                sha256=_sha(committed),
                byte_count=len(committed),
            )
        )
    rows = tuple(row.model_dump(mode="json") for row in members)
    return _make(
        models.SourceIdentity,
        {
            "source_commit": commit,
            "source_tree": tree,
            "implementation_members": tuple(members),
            "member_set_sha256": _sha(models.canonical_bytes(rows)),
        },
        "source_identity_id",
    )


def _implementation_binding(
    repository_root: Path, source: models.SourceIdentity
) -> models.ImplementationBinding:
    required = (
        "_freeze_v229",
        "_detached_rebuild",
        "_dependency_closure",
        "_independent_source_and_journal",
        "_independent_replay",
        "_independent_identifiability",
        "_independent_recovery_population",
        "_independent_negative_controls",
        "_scope",
    )
    trees = tuple(ast.parse((repository_root / path).read_text()) for path in IMPLEMENTATION_FILES)
    symbols = {
        node.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "_source_authority",
        "_call_authority",
        "_request_replay",
        "_identifiability",
        "_recovery_population",
        "_negative_controls",
        "_gates",
    }
    if not set(required).issubset(symbols):
        _fail("implementation.symbols", "independent audit symbol is absent")
    if calls & forbidden:
        _fail("implementation.helper_boundary", "v26.229 candidate helper call present")
    return _make(
        models.ImplementationBinding,
        {
            "source_identity_id": source.source_identity_id,
            "required_independent_symbols": required,
        },
        "binding_id",
    )


def _freeze_v229(
    repository_root: Path, authorization_id: str
) -> tuple[models.V229FreezeAudit, dict[str, bytes]]:
    root = repository_root / V229_DIR
    files, _manifest = _verify_manifest(
        root,
        "artifact_manifest.json",
        file_count=models.V229_FILE_COUNT,
        total_bytes=models.V229_TOTAL_BYTES,
        member_count=models.V229_MEMBER_COUNT,
        member_bytes=models.V229_MEMBER_BYTES,
        manifest_id=models.V229_MANIFEST_ID,
        artifact_root=models.V229_ARTIFACT_ROOT,
    )
    manifest_payload = files["artifact_manifest.json"]
    if (
        len(manifest_payload) != models.V229_MANIFEST_BYTE_COUNT
        or _sha(manifest_payload) != models.V229_MANIFEST_SHA256
    ):
        _fail("freeze.manifest_bytes", "v26.229 Manifest bytes differ")
    source = _load_bytes(files["source_identity.json"])
    report = _load_bytes(files["report.json"])
    gate = _load_bytes(files["gate_evaluation.json"])
    decision = _load_bytes(files["decision.json"])
    transition = _load_bytes(files["transition.json"])
    if (
        source.get("source_commit") != models.V229_SOURCE_COMMIT
        or source.get("source_tree") != models.V229_SOURCE_TREE
        or report.get("report_id") != models.V229_REPORT_ID
        or gate.get("evaluation_id") != models.V229_GATE_ID
        or decision.get("decision_id") != models.V229_DECISION_ID
        or transition.get("transition_id") != models.V229_TRANSITION_ID
        or transition.get("next_stage") != models.CONSUMED_STAGE
        or transition.get("next_stage_authorized") is not False
    ):
        _fail("freeze.authority", "v26.229 source/Report/Gate/Decision/Transition differs")
    if (
        _git(repository_root, "rev-parse", f"{models.V229_SOURCE_COMMIT}^{{tree}}").decode().strip()
        != models.V229_SOURCE_TREE
    ):
        _fail("freeze.commit_tree", "v26.229 commit/tree relation differs")
    audit = _make(models.V229FreezeAudit, {"authorization_id": authorization_id}, "audit_id")
    return audit, files


def _detached_rebuild(
    repository_root: Path,
    freeze: models.V229FreezeAudit,
    saved: dict[str, bytes],
) -> tuple[models.DetachedRebuildAudit, dict[str, bytes]]:
    archive = _git(
        repository_root,
        "archive",
        "--format=tar",
        models.V229_SOURCE_COMMIT,
        "trusted_data_synthesis/src",
    )
    with TemporaryDirectory(prefix="finance-v26-230-detached-") as temp:
        temp_root = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            all_members = bundle.getmembers()
            regular = tuple(row for row in all_members if row.isfile())
            if any(row.name.startswith("/") or ".." in Path(row.name).parts for row in all_members):
                _fail("detached.archive", "unsafe source archive")
            bundle.extractall(temp_root, filter="data")
        output = temp_root / "rebuilt"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(temp_root / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        if set(env) != {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LC_ALL"} or any(
            token in key.casefold()
            for key in env
            for token in ("key", "token", "secret", "credential", "password")
        ):
            _fail("detached.environment", "detached environment is not minimal")
        command = (
            sys.executable,
            "-m",
            V229_MODULE,
            "--repository-root",
            str(repository_root),
            "--output-dir",
            str(output),
            "--external-review",
            str(repository_root / V229_DIR / "external_review.txt"),
            "--source-commit",
            models.V229_SOURCE_COMMIT,
            "--source-tree",
            models.V229_SOURCE_TREE,
        )
        completed = subprocess.run(
            command, cwd=temp_root, env=env, check=False, capture_output=True
        )
        if completed.returncode:
            _fail("detached.builder", completed.stderr.decode(errors="replace"))
        rebuilt = _files(output)
        if rebuilt != saved:
            _fail("detached.byte_equality", "detached v26.229 rebuild differs")
    return (
        _make(
            models.DetachedRebuildAudit,
            {
                "freeze_audit_id": freeze.audit_id,
                "archived_source_file_count": len(regular),
            },
            "audit_id",
        ),
        rebuilt,
    )


def _dependency_closure(
    repository_root: Path, source: models.SourceIdentity
) -> models.DependencyClosureAudit:
    members: list[models.DependencyMember] = []
    for relative_path in DEPENDENCY_FILES:
        v229_bytes = _git(repository_root, "show", f"{models.V229_SOURCE_COMMIT}:{relative_path}")
        current = (repository_root / relative_path).read_bytes()
        v229_oid = (
            _git(repository_root, "rev-parse", f"{models.V229_SOURCE_COMMIT}:{relative_path}")
            .decode()
            .strip()
        )
        current_oid = _git(repository_root, "hash-object", relative_path).decode().strip()
        parent_commit: str | None = None
        parent_oid: str | None = None
        parent_match = False
        if relative_path == V209_FILE:
            parent_commit = V209_COMMIT
        elif relative_path == V226_FILE:
            parent_commit = V226_COMMIT
        if parent_commit is not None:
            parent = _git(repository_root, "show", f"{parent_commit}:{relative_path}")
            parent_oid = (
                _git(repository_root, "rev-parse", f"{parent_commit}:{relative_path}")
                .decode()
                .strip()
            )
            parent_match = parent == v229_bytes
        if current != v229_bytes or (parent_commit is not None and not parent_match):
            _fail("dependency.bytes", f"replay dependency differs:{relative_path}")
        members.append(
            models.DependencyMember(
                relative_path=relative_path,
                v229_blob_oid=v229_oid,
                current_blob_oid=current_oid,
                frozen_parent_commit=parent_commit,
                frozen_parent_blob_oid=parent_oid,
                sha256=_sha(v229_bytes),
                byte_count=len(v229_bytes),
                frozen_parent_match=parent_match,
            )
        )
    return _make(
        models.DependencyClosureAudit,
        {
            "source_identity_id": source.source_identity_id,
            "members": tuple(members),
            "member_count": len(members),
            "v229_current_matches": len(members),
            "frozen_parent_matches": sum(row.frozen_parent_match for row in members),
        },
        "audit_id",
    )


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


def _one_artifact(call: v226_models.ProviderCallDescriptor, kind: str) -> Any:
    rows = tuple(row for row in call.artifacts if row.artifact_kind == kind)
    if len(rows) != 1:
        _fail("journal.artifact_geometry", f"expected exactly one {kind}")
    return rows[0]


def _candidate_artifact_binding(
    root: Path, descriptor: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = (root / descriptor.relative_path).read_bytes()
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
        _fail("journal.artifact_bytes", f"Provider artifact differs:{descriptor.relative_path}")
    binding = {
        "artifact_id": descriptor.artifact_id,
        "provider_call_id": descriptor.provider_call_id,
        "artifact_kind": descriptor.artifact_kind,
        "relative_path": descriptor.relative_path,
        "sha256": descriptor.sha256,
        "byte_count": descriptor.byte_count,
        "public_projection_sha256": descriptor.public_projection_sha256,
        "canonical_bytes_match": True,
        "descriptor_bytes_match": True,
    }
    return binding, value


def _candidate_call(
    root: Path,
    record: v226_models.JobFailureRecord,
    call: v226_models.ProviderCallDescriptor,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    request_descriptor = _one_artifact(call, "request_metadata")
    descriptor_path = request_descriptor.relative_path.replace(
        "_request_metadata.json", "_descriptor.json"
    )
    descriptor_payload = (root / descriptor_path).read_bytes()
    if descriptor_payload != _encoded(call):
        _fail("journal.descriptor_bytes", f"descriptor differs:{descriptor_path}")
    bindings: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {}
    for artifact in call.artifacts:
        binding, value = _candidate_artifact_binding(root, artifact)
        bindings.append(binding)
        values[artifact.artifact_kind] = value
    request = values["request_metadata"]
    usage = values["usage_metadata"]
    telemetry = cast(dict[str, Any], usage.get("telemetry", {}))
    response = values.get("response_metadata")
    error = values.get("error_metadata")
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
        _fail("journal.call_relation", "request/Usage/descriptor relation differs")
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
            _fail("journal.success_relation", "successful Provider relation differs")
    elif (
        call.status != "provider_error"
        or error is None
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
        _fail("journal.error_relation", "failed Provider relation differs")
    authority = {
        "provider_call_id": call.provider_call_id,
        "descriptor_id": call.descriptor_id,
        "run_start_receipt_id": call.run_start_receipt_id,
        "historical_job_id": record.job_id,
        "call_ordinal": call.call_ordinal,
        "status": call.status,
        "request_sha256": call.request_sha256,
        "request_byte_count": int(request["request_byte_count"]),
        "intention_sha256": call.intention_sha256,
        "certificate_id": str(request["certificate_id"]),
        "pre_transport_receipt_id": str(request["pre_transport_receipt_id"]),
        "response_sha256": call.response_sha256,
        "error_sha256": call.error_sha256,
        "error_type": None if error is None else str(error["error_type"]),
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "artifact_bindings": tuple(bindings),
        "relation_closed": True,
    }
    return authority, response, error


@dataclass(frozen=True)
class IndependentSourceData:
    partition: models.SourcePartitionAudit
    journal: models.JournalAudit
    records: tuple[v226_models.JobFailureRecord, ...]
    candidate_rows: tuple[dict[str, Any], ...]
    candidate_source_audit: dict[str, Any]
    candidate_journal: dict[str, Any]
    public_prefixes: dict[int, tuple[dict[str, Any], ...]]
    error_metadata: dict[int, dict[str, Any]]


def _independent_source_and_journal(
    repository_root: Path,
    freeze: models.V229FreezeAudit,
    saved: dict[str, bytes],
) -> IndependentSourceData:
    root = repository_root / V226_DIR
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
    candidate_freeze = _load_bytes(saved["v228_freeze.json"])
    candidate_source_identity = _load_bytes(saved["source_identity.json"])
    provider_records: list[v226_models.JobFailureRecord] = []
    provider_projection: list[dict[str, Any]] = []
    host_projection: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    independent_rows: list[models.SourceRow] = []
    calls_for_audit: list[models.JournalCall] = []
    relation_projection: list[dict[str, Any]] = []
    prefixes: dict[int, tuple[dict[str, Any], ...]] = {}
    errors: dict[int, dict[str, Any]] = {}
    host_ordinals: list[int] = []
    response_count = 0
    for embedded in sorted(summary.failure_records, key=lambda row: row.job_ordinal):
        relative_path = f"job_failures/job_{embedded.job_ordinal:03d}.json"
        raw = files[relative_path]
        record = v226_models.JobFailureRecord.model_validate(_load_bytes(raw))
        if raw != _encoded(record) or record != embedded:
            _fail("source.failure_record", f"failure record differs:{relative_path}")
        projection = _source_projection(relative_path, raw, record)
        if record.failure_kind == "host_failure":
            host_ordinals.append(record.job_ordinal)
            host_projection.append(projection)
            continue
        if record.failure_kind != "unbound_provider_failure":
            _fail("source.failure_kind", "unexpected failure kind")
        provider_projection.append(projection)
        provider_records.append(record)
        candidate_calls: list[dict[str, Any]] = []
        public_prefix: list[dict[str, Any]] = []
        last_error: dict[str, Any] | None = None
        for expected_ordinal, call in enumerate(record.provider_calls):
            if call.call_ordinal != expected_ordinal:
                _fail("journal.call_order", "Provider call ordinal is not contiguous")
            authority, response, error = _candidate_call(root, record, call)
            candidate_calls.append(authority)
            relation_projection.append(authority)
            artifact_paths = tuple(row["relative_path"] for row in authority["artifact_bindings"])
            artifact_hashes = tuple(row["sha256"] for row in authority["artifact_bindings"])
            calls_for_audit.append(
                models.JournalCall(
                    job_ordinal=record.job_ordinal,
                    call_ordinal=call.call_ordinal,
                    provider_call_id=call.provider_call_id,
                    descriptor_id=call.descriptor_id,
                    status=cast(Any, call.status),
                    request_sha256=call.request_sha256,
                    request_byte_count=int(authority["request_byte_count"]),
                    certificate_id=str(authority["certificate_id"]),
                    pre_transport_receipt_id=str(authority["pre_transport_receipt_id"]),
                    response_sha256=call.response_sha256,
                    error_sha256=call.error_sha256,
                    error_type=authority["error_type"],
                    artifact_paths=cast(tuple[str, str, str], artifact_paths),
                    artifact_sha256s=cast(tuple[str, str, str], artifact_hashes),
                )
            )
            if response is not None:
                public_prefix.append(cast(dict[str, Any], response["public_projection"]))
                response_count += 1
            if error is not None:
                last_error = error
        if last_error is None or len(candidate_calls) != len(public_prefix) + 1:
            _fail("source.failed_prefix", "failed Provider prefix geometry differs")
        error_type = str(last_error["error_type"])
        if error_type not in {"ReasoningBudgetExhaustedError", "JSONDecodeError"}:
            _fail("source.error_type", "Provider failure type outside exact population")
        failure_class = (
            "reasoning_budget_exhausted_normalized_public_content_empty"
            if error_type == "ReasoningBudgetExhaustedError"
            else "json_decode_failure_exact_syntax_unavailable"
        )
        candidate_row = _identified(
            {
                "row_id": "pending",
                "v228_freeze_id": candidate_freeze["freeze_id"],
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
                "failure_kind": "unbound_provider_failure",
                "job_error_sha256": record.error_sha256,
                "provider_calls": tuple(candidate_calls),
                "successful_prefix_call_count": len(public_prefix),
                "failed_call_ordinal": candidate_calls[-1]["call_ordinal"],
                "failed_provider_call_id": candidate_calls[-1]["provider_call_id"],
                "failed_descriptor_id": candidate_calls[-1]["descriptor_id"],
                "failed_request_sha256": candidate_calls[-1]["request_sha256"],
                "failure_class": failure_class,
                "historical_terminal_evidence_admitted": False,
                "historical_five_layer_evidence_admitted": False,
                "recovery_attempted": False,
            },
            "row_id",
            "finance_v26_229_v226_source_row:",
        )
        candidate_path = f"source_rows/job_{record.job_ordinal:03d}.json"
        if _encoded(candidate_row) != saved[candidate_path]:
            _fail("source.candidate_row", f"candidate source row differs:{candidate_path}")
        candidate_rows.append(candidate_row)
        independent_rows.append(
            models.SourceRow(
                job_ordinal=record.job_ordinal,
                historical_job_id=record.job_id,
                failure_record_id=record.record_id,
                failure_kind="unbound_provider_failure",
                failure_relative_path=relative_path,
                failure_file_sha256=_sha(raw),
                failure_file_byte_count=len(raw),
                provider_call_count=len(candidate_calls),
                successful_prefix_call_count=len(public_prefix),
                failed_call_ordinal=int(candidate_calls[-1]["call_ordinal"]),
                failed_provider_call_id=str(candidate_calls[-1]["provider_call_id"]),
                failed_descriptor_id=str(candidate_calls[-1]["descriptor_id"]),
                failed_request_sha256=str(candidate_calls[-1]["request_sha256"]),
                failure_class=cast(Any, failure_class),
                candidate_source_row_id=str(candidate_row["row_id"]),
            )
        )
        prefixes[record.job_ordinal] = tuple(public_prefix)
        errors[record.job_ordinal] = last_error
    provider_sha = _sha(models.canonical_bytes(tuple(provider_projection)))
    host_sha = _sha(models.canonical_bytes(tuple(host_projection)))
    if (
        tuple(host_ordinals) != models.HOST_ORDINALS
        or tuple(row.job_ordinal for row in independent_rows) != models.PROVIDER_ORDINALS
        or provider_sha != models.V226_PROVIDER_SOURCE_SET_SHA256
        or len(calls_for_audit) != 88
        or response_count != 55
    ):
        _fail("source.partition", "exact 3/33 partition or 88-call geometry differs")
    candidate_source_audit = _identified(
        {
            "audit_id": "pending",
            "source_identity_id": candidate_source_identity["source_identity_id"],
            "v228_freeze_id": candidate_freeze["freeze_id"],
            "v226_manifest_id": models.V226_MANIFEST_ID,
            "v226_artifact_root": models.V226_ARTIFACT_ROOT,
            "v226_summary_id": models.V226_SUMMARY_ID,
            "v226_transition_id": models.V226_TRANSITION_ID,
            "source_rows": tuple(candidate_rows),
            "exact_source_count": 33,
            "excluded_host_failure_count": 3,
            "source_row_id_set_sha256": _sha(
                models.canonical_bytes(tuple(row["row_id"] for row in candidate_rows))
            ),
            "v226_actual_source_projection_sha256": provider_sha,
            "v228_exclusion_set_sha256": models.V226_PROVIDER_SOURCE_SET_SHA256,
            "v228_exclusion_set_match": True,
            "excluded_host_set_sha256": host_sha,
            "source_and_exclusion_exact_set_equality": True,
            "historical_v26_226_mutation_count": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "passed": True,
        },
        "audit_id",
        "finance_v26_229_v226_source_authority_audit:",
    )
    if _encoded(candidate_source_audit) != saved["v226_source_authority_audit.json"]:
        _fail("source.candidate_audit", "candidate source authority bytes differ")
    candidate_journal = _identified(
        {
            "audit_id": "pending",
            "source_authority_audit_id": candidate_source_audit["audit_id"],
            "predecessor_provider_census_id": models.V226_PROVIDER_CENSUS_ID,
            "source_row_ids": tuple(sorted(row["row_id"] for row in candidate_rows)),
            "provider_descriptor_count": 88,
            "request_metadata_count": 88,
            "response_metadata_count": 55,
            "error_metadata_count": 33,
            "usage_metadata_count": 88,
            "reasoning_budget_error_count": 31,
            "json_decode_error_count": 2,
            "relation_set_sha256": _sha(models.canonical_bytes(tuple(relation_projection))),
            "relation_closed": True,
            "orphan_request_intent_count": 0,
            "orphan_descriptor_count": 0,
            "invalid_relation_count": 0,
            "raw_request_count": 0,
            "raw_provider_response_count": 0,
            "private_reasoning_content_count": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "passed": True,
        },
        "audit_id",
        "finance_v26_229_provider_journal_authority:",
    )
    if _encoded(candidate_journal) != saved["provider_journal_authority.json"]:
        _fail("journal.candidate_audit", "candidate Journal bytes differ")
    partition = _make(
        models.SourcePartitionAudit,
        {
            "freeze_audit_id": freeze.audit_id,
            "host_ordinals": tuple(host_ordinals),
            "provider_ordinals": tuple(row.job_ordinal for row in independent_rows),
            "rows": tuple(independent_rows),
        },
        "audit_id",
    )
    journal = _make(
        models.JournalAudit,
        {
            "source_partition_audit_id": partition.audit_id,
            "calls": tuple(calls_for_audit),
            "relation_set_sha256": _sha(models.canonical_bytes(tuple(relation_projection))),
        },
        "audit_id",
    )
    return IndependentSourceData(
        partition=partition,
        journal=journal,
        records=tuple(provider_records),
        candidate_rows=tuple(candidate_rows),
        candidate_source_audit=candidate_source_audit,
        candidate_journal=candidate_journal,
        public_prefixes=prefixes,
        error_metadata=errors,
    )


class _CapturedFailedRequest(RuntimeError):
    pass


class _IndependentCaptureTransport:
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
        raise _CapturedFailedRequest("stop before failed-call response projection")


@dataclass(frozen=True)
class IndependentReplayData:
    audit: models.ReplayAudit
    candidate_audit: dict[str, Any]
    candidate_rows: dict[int, dict[str, Any]]


def _independent_replay(
    repository_root: Path,
    source: IndependentSourceData,
    saved: dict[str, bytes],
) -> IndependentReplayData:
    candidate_rows: list[dict[str, Any]] = []
    independent_rows: list[models.ReplayRow] = []
    with TemporaryDirectory(prefix="finance-v26-230-runtime-") as temp:
        loaded = v226._load_exact_runtime(repository_root, Path(temp))
        jobs = {job.job_id: job for job in loaded["manifest"].jobs}
        for source_row, candidate_source, record in zip(
            source.partition.rows, source.candidate_rows, source.records, strict=True
        ):
            transport = _IndependentCaptureTransport(source.public_prefixes[record.job_ordinal])
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
            successful: list[v209_models.ExecutableInvocationRecord] = []
            invocation_index = 0
            target = len(record.provider_calls)
            captured = False
            while (
                state.current_index < len(state.ordered_components)
                and len(transport.dispatches) < target
            ):
                try:
                    outcome = runner.invoke_action(
                        job=job, invocation_index=invocation_index, state=state
                    )
                except _CapturedFailedRequest:
                    captured = True
                    break
                successful.append(outcome.record)
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
                except _CapturedFailedRequest:
                    captured = True
                    break
                successful.append(correction.record)
                invocation_index += 1
                if correction.terminal is not None or correction.record.action_accepted is not True:
                    _fail("replay.correction", "successful correction prefix differs")
            if not captured and len(transport.dispatches) < target:
                try:
                    runner.invoke_final(
                        job=job,
                        invocation_index=invocation_index,
                        state=state,
                        context=context,
                    )
                except _CapturedFailedRequest:
                    captured = True
            if (
                not captured
                or len(transport.dispatches) != target
                or len(successful) != target - 1
                or tuple(row.invocation_index for row in successful) != tuple(range(target - 1))
            ):
                _fail("replay.geometry", "request replay geometry differs")
            request_matches = 0
            response_matches = 0
            candidate_calls = cast(tuple[dict[str, Any], ...], candidate_source["provider_calls"])
            for index, (dispatch, call) in enumerate(
                zip(transport.dispatches, candidate_calls, strict=True)
            ):
                request_bytes = models.canonical_bytes(dict(dispatch.request_body))
                if (
                    _sha(request_bytes) == call["request_sha256"]
                    and len(request_bytes) == call["request_byte_count"]
                    and dispatch.certificate.certificate_id == call["certificate_id"]
                    and dispatch.receipt.receipt_id == call["pre_transport_receipt_id"]
                    and dispatch.certificate.job_id == record.job_id
                ):
                    request_matches += 1
                if index < source_row.successful_prefix_call_count:
                    invocation = successful[index]
                    if (
                        invocation.canonical_request_body_sha256 == call["request_sha256"]
                        and invocation.public_response_sha256 == call["response_sha256"]
                        and invocation.phase == dispatch.certificate.phase
                    ):
                        response_matches += 1
            if request_matches != target or response_matches != len(successful):
                _fail("replay.authority", "request or public-prefix relation differs")
            last = transport.dispatches[-1]
            candidate_row = {
                "source_row_id": candidate_source["row_id"],
                "historical_job_id": record.job_id,
                "job_ordinal": record.job_ordinal,
                "invocation_count": target,
                "successful_invocation_ids": tuple(row.invocation_id for row in successful),
                "phases": tuple(row.phase for row in successful) + (last.certificate.phase,),
                "request_sha256s": tuple(
                    v209_models.canonical_sha256(dict(row.request_body))
                    for row in transport.dispatches
                ),
                "response_sha256s": tuple(
                    row.public_response_sha256
                    for row in successful
                    if row.public_response_sha256 is not None
                ),
                "successful_prefix_call_count": len(successful),
                "failed_call_ordinal": source_row.failed_call_ordinal,
                "exact_request_match_count": request_matches,
                "exact_response_match_count": response_matches,
                "failed_request_certificate_id": last.certificate.certificate_id,
                "failed_pre_transport_receipt_id": last.receipt.receipt_id,
                "failed_request_sha256": v209_models.canonical_sha256(dict(last.request_body)),
                "failed_request_byte_count": len(
                    v209_models.canonical_bytes(dict(last.request_body))
                ),
                "persisted_public_prefix_only": True,
                "failed_request_capture_stopped_before_response_projection": True,
                "failed_call_response_supplied_to_replay": False,
                "historical_terminal_record_created_for_failed_call": False,
                "historical_provider_calls_reissued": 0,
                "provider_calls": 0,
            }
            saved_candidate_replay = _load_bytes(saved["request_replay_audit.json"])
            saved_by_ordinal = {
                int(row["job_ordinal"]): row for row in saved_candidate_replay["rows"]
            }
            if _encoded(candidate_row) != _encoded(saved_by_ordinal[record.job_ordinal]):
                _fail("replay.candidate_row", f"candidate replay row differs:{record.job_ordinal}")
            candidate_rows.append(candidate_row)
            independent_rows.append(
                models.ReplayRow(
                    job_ordinal=record.job_ordinal,
                    source_row_id=str(candidate_source["row_id"]),
                    invocation_count=target,
                    successful_prefix_call_count=len(successful),
                    phases=cast(tuple[str, ...], candidate_row["phases"]),
                    request_sha256s=cast(tuple[str, ...], candidate_row["request_sha256s"]),
                    response_sha256s=cast(tuple[str, ...], candidate_row["response_sha256s"]),
                    successful_invocation_ids=cast(
                        tuple[str, ...], candidate_row["successful_invocation_ids"]
                    ),
                    failed_request_sha256=str(candidate_row["failed_request_sha256"]),
                    failed_request_byte_count=int(candidate_row["failed_request_byte_count"]),
                    failed_request_certificate_id=str(
                        candidate_row["failed_request_certificate_id"]
                    ),
                    failed_pre_transport_receipt_id=str(
                        candidate_row["failed_pre_transport_receipt_id"]
                    ),
                    request_matches=request_matches,
                    response_matches=response_matches,
                )
            )
    phase_partition = tuple(row.phases[-1] for row in independent_rows)
    if (
        phase_partition.count("first_action") != 3
        or phase_partition.count("subsequent_action") != 25
        or phase_partition.count("final") != 5
        or phase_partition.count("correction") != 0
    ):
        _fail("replay.phase_partition", "failed request phase partition differs")
    candidate_audit = _identified(
        {
            "audit_id": "pending",
            "source_authority_audit_id": source.candidate_source_audit["audit_id"],
            "provider_journal_authority_id": source.candidate_journal["audit_id"],
            "rows": tuple(candidate_rows),
            "exact_job_count": 33,
            "exact_failed_request_match_count": 33,
            "historical_provider_calls_reissued": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "passed": True,
        },
        "audit_id",
        "finance_v26_229_request_replay_audit:",
    )
    if _encoded(candidate_audit) != saved["request_replay_audit.json"]:
        _fail("replay.candidate_audit", "candidate replay Audit bytes differ")
    audit = _make(
        models.ReplayAudit,
        {
            "journal_audit_id": source.journal.audit_id,
            "rows": tuple(independent_rows),
        },
        "audit_id",
    )
    return IndependentReplayData(
        audit=audit,
        candidate_audit=candidate_audit,
        candidate_rows={
            row.job_ordinal: candidate
            for row, candidate in zip(independent_rows, candidate_rows, strict=True)
        },
    )


@dataclass(frozen=True)
class IndependentIdentifiabilityData:
    audit: models.IdentifiabilityAudit
    candidate_audit: dict[str, Any]
    candidate_rows: dict[int, dict[str, Any]]


def _independent_identifiability(
    source: IndependentSourceData, saved: dict[str, bytes]
) -> IndependentIdentifiabilityData:
    source_by_ordinal = {row.job_ordinal: row for row in source.partition.rows}
    candidate_source_by_ordinal = {int(row["job_ordinal"]): row for row in source.candidate_rows}
    candidate_rows: list[dict[str, Any]] = []
    independent_rows: list[models.IdentifiabilityRow] = []
    saved_audit = _load_bytes(saved["identifiability_audit.json"])
    saved_by_ordinal = {int(row["job_ordinal"]): row for row in saved_audit["rows"]}
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
            or ((not reasoning) and ordinal not in (62, 139))
        ):
            _fail("identifiability.source", "persisted response diagnostics differ")
        source_row = source_by_ordinal[ordinal]
        candidate_source = candidate_source_by_ordinal[ordinal]
        candidate_row = _identified(
            {
                "row_id": "pending",
                "source_row_id": candidate_source["row_id"],
                "historical_job_id": source_row.historical_job_id,
                "job_ordinal": ordinal,
                "failure_class": source_row.failure_class,
                "error_type": error_type,
                "public_content_sha256": str(redacted["public_content_sha256"]),
                "public_content_length": int(redacted["public_content_length"]),
                "finish_reason": str(redacted["finish_reason"]),
                "failure_semantics_identifiable": reasoning,
                "exact_json_syntax_identifiable": False,
                "exact_json_response_bytes_persisted": False,
                "exact_json_response_bytes_guessed": False,
                "fresh_request_recovery_eligibility_identifiable": True,
            },
            "row_id",
            "finance_v26_229_identifiability_row:",
        )
        if _encoded(candidate_row) != _encoded(saved_by_ordinal[ordinal]):
            _fail("identifiability.candidate_row", f"candidate row differs:{ordinal}")
        candidate_rows.append(candidate_row)
        independent_rows.append(
            models.IdentifiabilityRow(
                job_ordinal=ordinal,
                source_row_id=str(candidate_source["row_id"]),
                candidate_row_id=str(candidate_row["row_id"]),
                error_type=cast(Any, error_type),
                failure_class=source_row.failure_class,
                public_content_sha256=str(redacted["public_content_sha256"]),
                public_content_length=int(redacted["public_content_length"]),
                finish_reason=cast(Any, str(redacted["finish_reason"])),
                failure_semantics_identifiable=reasoning,
            )
        )
    candidate_rows.sort(key=lambda row: str(row["row_id"]))
    candidate_audit = _identified(
        {
            "audit_id": "pending",
            "source_authority_audit_id": source.candidate_source_audit["audit_id"],
            "rows": tuple(candidate_rows),
            "exact_source_count": 33,
            "identifiable_reasoning_budget_count": 31,
            "unidentifiable_json_syntax_count": 2,
            "exact_json_response_bytes_persisted_count": 0,
            "exact_json_response_bytes_guessed_count": 0,
            "recovery_request_authority_identifiable_count": 33,
            "provider_calls": 0,
            "passed": True,
        },
        "audit_id",
        "finance_v26_229_identifiability_audit:",
    )
    if _encoded(candidate_audit) != saved["identifiability_audit.json"]:
        _fail("identifiability.candidate_audit", "candidate identifiability bytes differ")
    audit = _make(
        models.IdentifiabilityAudit,
        {
            "source_partition_audit_id": source.partition.audit_id,
            "rows": tuple(independent_rows),
        },
        "audit_id",
    )
    return IndependentIdentifiabilityData(
        audit=audit,
        candidate_audit=candidate_audit,
        candidate_rows={int(row["job_ordinal"]): row for row in candidate_rows},
    )


@dataclass(frozen=True)
class IndependentRecoveryData:
    audit: models.RecoveryPopulationAudit
    candidate_contract: dict[str, Any]
    candidate_population: dict[str, Any]
    candidate_jobs: tuple[dict[str, Any], ...]


def _independent_recovery_population(
    source: IndependentSourceData,
    replay: IndependentReplayData,
    identifiability: IndependentIdentifiabilityData,
    saved: dict[str, bytes],
) -> IndependentRecoveryData:
    source_by_ordinal = {int(row["job_ordinal"]): row for row in source.candidate_rows}
    candidates: list[dict[str, Any]] = []
    for ordinal in models.PROVIDER_ORDINALS:
        source_row = source_by_ordinal[ordinal]
        replay_row = replay.candidate_rows[ordinal]
        identifiable = identifiability.candidate_rows[ordinal]
        candidate = _identified(
            {
                "candidate_id": "pending",
                "source_authority_audit_id": source.candidate_source_audit["audit_id"],
                "provider_journal_authority_id": source.candidate_journal["audit_id"],
                "request_replay_audit_id": replay.candidate_audit["audit_id"],
                "identifiability_audit_id": identifiability.candidate_audit["audit_id"],
                "source_row_id": source_row["row_id"],
                "identifiability_row_id": identifiable["row_id"],
                "historical_job_id": source_row["historical_job_id"],
                "job_ordinal": ordinal,
                "failure_record_id": source_row["failure_record_id"],
                "successful_prefix_call_count": source_row["successful_prefix_call_count"],
                "successful_prefix_provider_call_ids": tuple(
                    call["provider_call_id"] for call in source_row["provider_calls"][:-1]
                ),
                "failed_provider_call_id": source_row["failed_provider_call_id"],
                "failed_descriptor_id": source_row["failed_descriptor_id"],
                "exact_failed_request_sha256": replay_row["failed_request_sha256"],
                "exact_failed_request_byte_count": replay_row["failed_request_byte_count"],
                "exact_failed_request_certificate_id": replay_row["failed_request_certificate_id"],
                "exact_failed_pre_transport_receipt_id": replay_row[
                    "failed_pre_transport_receipt_id"
                ],
                "failure_class": source_row["failure_class"],
                "historical_json_syntax_detail_available": False,
                "historical_response_content_guessed": False,
                "historical_job_identity_retained_only_as_parent": True,
                "historical_job_reclassified": False,
                "replacement_or_recovery_attempted": False,
                "provider_calls_authorized": False,
                "online_execution_authorized": False,
            },
            "candidate_id",
            "finance_v26_229_recovery_candidate:",
        )
        if _encoded(candidate) != saved[f"recovery_candidates/job_{ordinal:03d}.json"]:
            _fail("recovery.candidate_bytes", f"candidate differs:{ordinal}")
        candidates.append(candidate)
    candidates.sort(key=lambda row: str(row["candidate_id"]))
    contract = _identified(
        {
            "contract_id": "pending",
            "source_authority_audit_id": source.candidate_source_audit["audit_id"],
            "provider_journal_authority_id": source.candidate_journal["audit_id"],
            "request_replay_audit_id": replay.candidate_audit["audit_id"],
            "identifiability_audit_id": identifiability.candidate_audit["audit_id"],
            "candidate_ids": tuple(row["candidate_id"] for row in candidates),
            "exact_candidate_count": 33,
            "fresh_recovery_job_identity_required": True,
            "historical_job_identity_parent_only": True,
            "exact_successful_prefix_and_failed_request_binding_required": True,
            "historical_response_reconstruction_required": False,
            "unknown_json_response_invention_allowed": False,
            "historical_job_rerun_or_reclassification_allowed": False,
            "historical_v26_226_mutation_allowed": False,
            "empirical_row_creation_allowed": False,
            "provider_calls_authorized": False,
            "credential_lookups_authorized": False,
            "recovery_execution_authorized": False,
            "online_authorization_created": False,
        },
        "contract_id",
        "finance_v26_229_recovery_contract:",
    )
    if _encoded(contract) != saved["recovery_contract.json"]:
        _fail("recovery.contract_bytes", "candidate Recovery Contract differs")
    jobs: list[dict[str, Any]] = []
    for candidate in candidates:
        job = _identified(
            {
                "recovery_job_id": "pending",
                "recovery_contract_id": contract["contract_id"],
                "candidate": candidate,
                "historical_job_identity_retained_only_as_parent": True,
                "historical_job_reclassified": False,
                "successful_prefix_provider_calls_authorized": 0,
                "failed_request_reissue_authorized": 0,
                "replacement_response_authorization_count": 0,
                "recovery_execution_authorized": False,
                "provider_calls_authorized": False,
            },
            "recovery_job_id",
            "finance_v26_229_recovery_job:",
        )
        ordinal = int(candidate["job_ordinal"])
        if _encoded(job) != saved[f"recovery_jobs/job_{ordinal:03d}.json"]:
            _fail("recovery.job_bytes", f"Recovery Job differs:{ordinal}")
        jobs.append(job)
    jobs.sort(key=lambda row: str(row["recovery_job_id"]))
    population = _identified(
        {
            "population_id": "pending",
            "recovery_contract_id": contract["contract_id"],
            "jobs": tuple(jobs),
            "exact_job_count": 33,
            "fresh_recovery_job_identity_count": 33,
            "historical_job_identity_overlap_count": 0,
            "identifiable_reasoning_budget_count": 31,
            "unidentifiable_json_syntax_count": 2,
            "provider_calls_authorized": False,
            "recovery_execution_authorized": False,
            "online_authorization_created": False,
        },
        "population_id",
        "finance_v26_229_recovery_population:",
    )
    if _encoded(population) != saved["recovery_population.json"]:
        _fail("recovery.population_bytes", "candidate Recovery Population differs")
    historical = (
        {row.historical_job_id for row in source.partition.rows}
        | {row.failure_record_id for row in source.partition.rows}
        | {call.provider_call_id for call in source.journal.calls}
    )
    recovery_ids = {str(job["recovery_job_id"]) for job in jobs}
    if recovery_ids & historical:
        _fail("recovery.identity_overlap", "Recovery identity overlaps historical identity")
    rows = tuple(
        sorted(
            (
                models.RecoveryMatchRow(
                    job_ordinal=int(job["candidate"]["job_ordinal"]),
                    source_row_id=str(job["candidate"]["source_row_id"]),
                    candidate_id=str(job["candidate"]["candidate_id"]),
                    recovery_job_id=str(job["recovery_job_id"]),
                    historical_job_id=str(job["candidate"]["historical_job_id"]),
                    failure_record_id=str(job["candidate"]["failure_record_id"]),
                    exact_failed_request_sha256=str(
                        job["candidate"]["exact_failed_request_sha256"]
                    ),
                    successful_prefix_call_count=int(
                        job["candidate"]["successful_prefix_call_count"]
                    ),
                )
                for job in jobs
            ),
            key=lambda row: row.job_ordinal,
        )
    )
    audit = _make(
        models.RecoveryPopulationAudit,
        {
            "source_partition_audit_id": source.partition.audit_id,
            "replay_audit_id": replay.audit.audit_id,
            "identifiability_audit_id": identifiability.audit.audit_id,
            "rows": rows,
        },
        "audit_id",
    )
    return IndependentRecoveryData(
        audit=audit,
        candidate_contract=contract,
        candidate_population=population,
        candidate_jobs=tuple(jobs),
    )


def _admit_independent_candidate(
    candidate: dict[str, Any],
    source: IndependentSourceData,
    recovery: IndependentRecoveryData,
) -> None:
    exact_ordinals = models.PROVIDER_ORDINALS
    exact_prefixes = tuple(
        tuple(call.provider_call_id for call in source.journal.calls if call.job_ordinal == ordinal)
        for ordinal in exact_ordinals
    )
    exact_hashes = tuple(row.failed_request_sha256 for row in source.partition.rows)
    exact_descriptors = tuple(row.failed_descriptor_id for row in source.partition.rows)
    exact_artifacts = tuple(
        tuple(zip(call.artifact_paths, call.artifact_sha256s, strict=True))
        for call in source.journal.calls
    )
    exact_recovery_ids = tuple(str(job["recovery_job_id"]) for job in recovery.candidate_jobs)
    exact_parents = tuple(
        (str(job["candidate"]["candidate_id"]), str(job["candidate"]["source_row_id"]))
        for job in recovery.candidate_jobs
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
    if candidate["recovery_candidate_parents"] != exact_parents:
        _fail("admission.source_parent", "Recovery Candidate source parent differs")
    historical = (
        {row.historical_job_id for row in source.partition.rows}
        | {row.failure_record_id for row in source.partition.rows}
        | {call.provider_call_id for call in source.journal.calls}
    )
    if set(candidate["recovery_job_ids"]) & historical:
        _fail("admission.fresh_identity", "historical identity reused")


def _capture_attack(name: str, action: Any) -> models.AttackResult:
    try:
        action()
    except V230Error as error:
        return models.AttackResult(
            attack_name=name,
            rejection_stage=error.stage,
            reason_sha256=_sha(error.reason.encode()),
        )
    _fail("negative.control", f"attack unexpectedly admitted:{name}")


def _independent_negative_controls(
    source: IndependentSourceData, recovery: IndependentRecoveryData
) -> models.NegativeControlAudit:
    positive: dict[str, Any] = {
        "provider_calls_authorized": False,
        "online_execution_authorized": False,
        "source_ordinals": models.PROVIDER_ORDINALS,
        "provider_call_prefixes": tuple(
            tuple(
                call.provider_call_id
                for call in source.journal.calls
                if call.job_ordinal == ordinal
            )
            for ordinal in models.PROVIDER_ORDINALS
        ),
        "failed_request_sha256s": tuple(row.failed_request_sha256 for row in source.partition.rows),
        "failed_descriptor_ids": tuple(row.failed_descriptor_id for row in source.partition.rows),
        "artifact_relations": tuple(
            tuple(zip(call.artifact_paths, call.artifact_sha256s, strict=True))
            for call in source.journal.calls
        ),
        "json_response_bytes": None,
        "json_syntax_identifiable": False,
        "recovery_job_ids": tuple(str(job["recovery_job_id"]) for job in recovery.candidate_jobs),
        "recovery_candidate_parents": tuple(
            (
                str(job["candidate"]["candidate_id"]),
                str(job["candidate"]["source_row_id"]),
            )
            for job in recovery.candidate_jobs
        ),
        "candidate_identity": "pending",
    }
    attacks = {name: copy.deepcopy(positive) for name in models.NEGATIVE_CONTROL_NAMES}
    attacks["authorize_online_execution"]["online_execution_authorized"] = True
    attacks["authorize_provider_call"]["provider_calls_authorized"] = True
    descriptors = list(attacks["cross_job_provider_descriptor"]["failed_descriptor_ids"])
    descriptors[0], descriptors[1] = descriptors[1], descriptors[0]
    attacks["cross_job_provider_descriptor"]["failed_descriptor_ids"] = tuple(descriptors)
    recovery_ids = list(attacks["duplicate_recovery_job"]["recovery_job_ids"])
    recovery_ids[-1] = recovery_ids[0]
    attacks["duplicate_recovery_job"]["recovery_job_ids"] = tuple(recovery_ids)
    hashes = list(attacks["failed_request_hash_replaced"]["failed_request_sha256s"])
    hashes[0] = _sha(b"replaced failed request")
    attacks["failed_request_hash_replaced"]["failed_request_sha256s"] = tuple(hashes)
    reused = list(attacks["historical_job_identity_reused"]["recovery_job_ids"])
    reused[0] = source.partition.rows[0].historical_job_id
    attacks["historical_job_identity_reused"]["recovery_job_ids"] = tuple(reused)
    ordinals = list(attacks["host_failure_substituted"]["source_ordinals"])
    ordinals[0] = models.HOST_ORDINALS[0]
    attacks["host_failure_substituted"]["source_ordinals"] = tuple(ordinals)
    attacks["invent_json_response_bytes"]["json_response_bytes"] = b'{"invented":true}'.hex()
    prefixes = list(attacks["provider_call_prefix_truncated"]["provider_call_prefixes"])
    prefixes[0] = prefixes[0][:-1]
    attacks["provider_call_prefix_truncated"]["provider_call_prefixes"] = tuple(prefixes)
    attacks["reclassify_json_syntax_as_identifiable"]["json_syntax_identifiable"] = True
    removed = list(attacks["remove_recovery_job"]["recovery_job_ids"])
    attacks["remove_recovery_job"]["recovery_job_ids"] = tuple(removed[:-1])
    relations = list(attacks["swap_error_or_usage_artifact"]["artifact_relations"])
    relations[0], relations[-1] = relations[-1], relations[0]
    attacks["swap_error_or_usage_artifact"]["artifact_relations"] = tuple(relations)
    results: list[models.AttackResult] = []
    for name in models.NEGATIVE_CONTROL_NAMES:
        candidate = attacks[name]
        candidate["candidate_identity"] = _sha(
            models.canonical_bytes(
                {key: value for key, value in candidate.items() if key != "candidate_identity"}
            )
        )
        results.append(
            _capture_attack(
                name,
                lambda candidate=candidate: _admit_independent_candidate(
                    candidate, source, recovery
                ),
            )
        )
    return _make(
        models.NegativeControlAudit,
        {
            "source_partition_audit_id": source.partition.audit_id,
            "recovery_population_audit_id": recovery.audit.audit_id,
            "results": tuple(results),
        },
        "audit_id",
    )


def _scope() -> models.ScopeBoundaryAudit:
    return _make(models.ScopeBoundaryAudit, {}, "audit_id")


def _write(output_dir: Path, payloads: dict[str, bytes]) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        _fail("output.no_replace", "output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, payload in sorted(payloads.items()):
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    review = external_review_path.read_bytes()
    authorization = _authorization(review)
    source_identity_object = _source_identity(repository_root, source_identity)
    implementation = _implementation_binding(repository_root, source_identity_object)
    freeze, saved = _freeze_v229(repository_root, authorization.authorization_id)
    detached, _rebuilt = _detached_rebuild(repository_root, freeze, saved)
    dependencies = _dependency_closure(repository_root, source_identity_object)
    source = _independent_source_and_journal(repository_root, freeze, saved)
    replay = _independent_replay(repository_root, source, saved)
    identifiability = _independent_identifiability(source, saved)
    recovery = _independent_recovery_population(source, replay, identifiability, saved)
    negative = _independent_negative_controls(source, recovery)
    scope = _scope()
    gates = (
        models.Gate(name=models.GATE_NAMES[0], evidence_ids=(freeze.audit_id,)),
        models.Gate(
            name=models.GATE_NAMES[1],
            evidence_ids=(
                detached.audit_id,
                source_identity_object.source_identity_id,
                implementation.binding_id,
                dependencies.audit_id,
            ),
        ),
        models.Gate(name=models.GATE_NAMES[2], evidence_ids=(source.partition.audit_id,)),
        models.Gate(name=models.GATE_NAMES[3], evidence_ids=(source.journal.audit_id,)),
        models.Gate(name=models.GATE_NAMES[4], evidence_ids=(replay.audit.audit_id,)),
        models.Gate(
            name=models.GATE_NAMES[5],
            evidence_ids=(identifiability.audit.audit_id, recovery.audit.audit_id),
        ),
        models.Gate(name=models.GATE_NAMES[6], evidence_ids=(negative.audit_id,)),
        models.Gate(name=models.GATE_NAMES[7], evidence_ids=(scope.audit_id,)),
    )
    gate = _make(models.GateEvaluation, {"gates": gates}, "evaluation_id")
    decision = _make(models.Decision, {"gate_evaluation_id": gate.evaluation_id}, "decision_id")
    transition = _make(models.Transition, {"decision_id": decision.decision_id}, "transition_id")
    report = _make(
        models.Report,
        {
            "authorization_id": authorization.authorization_id,
            "source_identity_id": source_identity_object.source_identity_id,
            "implementation_binding_id": implementation.binding_id,
            "v229_freeze_audit_id": freeze.audit_id,
            "detached_rebuild_audit_id": detached.audit_id,
            "dependency_closure_audit_id": dependencies.audit_id,
            "source_partition_audit_id": source.partition.audit_id,
            "journal_audit_id": source.journal.audit_id,
            "replay_audit_id": replay.audit.audit_id,
            "identifiability_audit_id": identifiability.audit.audit_id,
            "recovery_population_audit_id": recovery.audit.audit_id,
            "negative_control_audit_id": negative.audit_id,
            "scope_boundary_audit_id": scope.audit_id,
            "gate_evaluation_id": gate.evaluation_id,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
        },
        "report_id",
    )
    payloads = {
        "external_review.txt": review,
        "operator_directive.txt": models.OPERATOR_DIRECTIVE.encode(),
        "external_authorization.json": _encoded(authorization),
        "source_identity.json": _encoded(source_identity_object),
        "implementation_binding.json": _encoded(implementation),
        "v229_freeze_audit.json": _encoded(freeze),
        "detached_rebuild_audit.json": _encoded(detached),
        "dependency_closure_audit.json": _encoded(dependencies),
        "source_partition_audit.json": _encoded(source.partition),
        "provider_journal_audit.json": _encoded(source.journal),
        "request_replay_audit.json": _encoded(replay.audit),
        "identifiability_audit.json": _encoded(identifiability.audit),
        "recovery_population_audit.json": _encoded(recovery.audit),
        "negative_control_audit.json": _encoded(negative),
        "scope_boundary_audit.json": _encoded(scope),
        "gate_evaluation.json": _encoded(gate),
        "decision.json": _encoded(decision),
        "transition.json": _encoded(transition),
        "report.json": _encoded(report),
    }
    manifest = models.artifact_manifest(payloads)
    payloads["artifact_manifest.json"] = _encoded(manifest)
    _write(output_dir, payloads)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )


if __name__ == "__main__":
    main()
