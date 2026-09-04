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
    phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)

RUN_ID: Final = "finance_v26_228_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit_v1_20260904"
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
V227_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{models.V227_RUN_ID}"
V226_DIR: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_exact_192_job_replacement_online_execution_v1_20260904"
MODELS_FILE: Final = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit_models.py"
AUDIT_FILE: Final = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit.py"
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUDIT_FILE)))
V227_MODULE: Final = "trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_exact_v209_subsequent_action_evidence_domain_closure_preflight"
LAYER_KINDS: Final = ("raw", "result", "trace", "outcome", "checkpoint")
PARSER_TERMINAL: Final = "first_response_abi_invalid"
REFERENCE_TERMINAL: Final = "first_action_reference_invalid"
PARSER_POLICY: Final = (
    "fresh_kernel_terminal_policy:b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f"
)
REFERENCE_POLICY: Final = (
    "fresh_kernel_terminal_policy:443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b"
)
REGISTRY_FILE: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_195_fresh_artifact_backed_outcome_authority_preflight_v1_20260901/fresh_terminal_registry.json"


class V228Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V228Error(stage, reason)


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


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(("git", *args), cwd=root, check=False, capture_output=True)
    if result.returncode:
        _fail("source.git", result.stderr.decode(errors="replace"))
    return result.stdout


def _authorization(review: bytes) -> models.ExternalAuthorization:
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.review", "external review bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode()
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.directive", "operator directive bytes differ")
    return _make(
        models.ExternalAuthorization, {}, "authorization_id", models.ExternalAuthorization.prefix()
    )


def _source_identity(
    repository_root: Path, source_identity: tuple[str, str]
) -> models.SourceIdentity:
    commit, tree = source_identity
    if _git(repository_root, "rev-parse", f"{commit}^{{tree}}").decode().strip() != tree:
        _fail("source.commit_tree", "v26.228 source commit/tree relation differs")
    members: list[models.SourceMember] = []
    for relative_path in IMPLEMENTATION_FILES:
        committed = _git(repository_root, "show", f"{commit}:{relative_path}")
        working = (repository_root / relative_path).read_bytes()
        if committed != working:
            _fail("source.working_tree", f"v26.228 working source differs:{relative_path}")
        members.append(
            models.SourceMember(
                relative_path=relative_path, sha256=_sha(committed), byte_count=len(committed)
            )
        )
    member_rows = tuple(row.model_dump(mode="json") for row in members)
    return _make(
        models.SourceIdentity,
        {
            "source_commit": commit,
            "source_tree": tree,
            "implementation_members": tuple(members),
            "member_set_sha256": _sha(models.canonical_bytes(member_rows)),
        },
        "source_identity_id",
        models.SourceIdentity.prefix(),
    )


def _implementation_binding(
    repository_root: Path, source: models.SourceIdentity
) -> models.ImplementationBinding:
    required = (
        "_freeze_v227",
        "_detached_rebuild",
        "_source_partition",
        "_independent_replay",
        "_derive_evidence",
        "_reconstruct_layers",
        "_negative_controls",
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
    if not set(required).issubset(symbols):
        _fail("implementation.symbols", "required independent audit symbol is absent")
    forbidden = {
        "_verify_v226",
        "_host_failure_row",
        "_replay",
        "_evidence",
        "_five_layers",
        "_control",
        "_negative_audit",
    }
    if calls & forbidden:
        _fail("implementation.helper_boundary", "candidate helper call present")
    return _make(
        models.ImplementationBinding,
        {
            "source_identity_id": source.source_identity_id,
            "implementation_files": tuple(
                sorted(member.relative_path for member in source.implementation_members)
            ),
            "required_independent_symbols": required,
        },
        "binding_id",
        models.ImplementationBinding.prefix(),
    )


def _freeze_v227(
    repository_root: Path, authorization_id: str
) -> tuple[models.V227FreezeAudit, dict[str, bytes]]:
    root = repository_root / V227_DIR
    files = _files(root)
    if (
        len(files) != models.V227_FILE_COUNT
        or sum(map(len, files.values())) != models.V227_TOTAL_BYTES
    ):
        _fail("freeze.geometry", "v26.227 formal geometry differs")
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        _sha(manifest_payload) != models.V227_MANIFEST_SHA256
        or len(manifest_payload) != models.V227_MANIFEST_BYTE_COUNT
    ):
        _fail("freeze.manifest_bytes", "v26.227 Manifest file bytes differ")
    manifest = _load_bytes(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest.get("members", ())}
    if (
        manifest.get("manifest_id") != models.V227_MANIFEST_ID
        or manifest.get("artifact_root") != models.V227_ARTIFACT_ROOT
        or len(members) != models.V227_MEMBER_COUNT
        or manifest.get("total_member_bytes") != models.V227_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("freeze.manifest", "v26.227 Manifest/Root differs")
    for path, member in members.items():
        payload = files[path]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail("freeze.member", f"v26.227 member differs:{path}")
    decision = _load_bytes(files["decision.json"])
    transition = _load_bytes(files["prospective_transition.json"])
    source = _load_bytes(files["source_identity.json"])
    if (
        decision.get("decision_id") != models.V227_DECISION_ID
        or transition.get("transition_id") != models.V227_TRANSITION_ID
        or source.get("source_commit") != models.V227_SOURCE_COMMIT
        or source.get("source_tree") != models.V227_SOURCE_TREE
    ):
        _fail("freeze.authority", "v26.227 source/Decision/Transition differs")
    if (
        _git(repository_root, "rev-parse", f"{models.V227_SOURCE_COMMIT}^{{tree}}").decode().strip()
        != models.V227_SOURCE_TREE
    ):
        _fail("freeze.commit_tree", "v26.227 source commit/tree relation differs")
    audit = _make(
        models.V227FreezeAudit,
        {"authorization_id": authorization_id},
        "audit_id",
        models.V227FreezeAudit.prefix(),
    )
    return audit, files


def _detached_rebuild(
    repository_root: Path, freeze: models.V227FreezeAudit, saved: dict[str, bytes]
) -> tuple[models.DetachedRebuildAudit, dict[str, bytes]]:
    archive = _git(
        repository_root,
        "archive",
        "--format=tar",
        models.V227_SOURCE_COMMIT,
        "trusted_data_synthesis/src",
    )
    with TemporaryDirectory(prefix="finance-v26-228-detached-") as temp:
        temp_root = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            members = tuple(item for item in bundle.getmembers() if item.isfile())
            if any(
                item.name.startswith("/") or ".." in Path(item.name).parts
                for item in bundle.getmembers()
            ):
                _fail("detached.archive", "unsafe archived source path")
            bundle.extractall(temp_root, filter="data")
        if len(members) != 694:
            _fail("detached.archive_geometry", "detached source file count differs")
        output = temp_root / "rebuilt"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(temp_root / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        command = (
            sys.executable,
            "-m",
            V227_MODULE,
            "--repository-root",
            str(repository_root),
            "--output-dir",
            str(output),
            "--external-review",
            str(repository_root / V227_DIR / "external_review.txt"),
            "--source-commit",
            models.V227_SOURCE_COMMIT,
            "--source-tree",
            models.V227_SOURCE_TREE,
        )
        if set(env) != {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LC_ALL"} or any(
            token in key.casefold()
            for key in env
            for token in ("key", "token", "secret", "credential", "password")
        ):
            _fail("detached.environment", "detached environment is not minimal")
        completed = subprocess.run(
            command, cwd=temp_root, env=env, check=False, capture_output=True
        )
        if completed.returncode:
            _fail("detached.builder", completed.stderr.decode(errors="replace"))
        rebuilt = _files(output)
        if rebuilt != saved:
            _fail("detached.byte_equality", "detached v26.227 rebuild differs")
    audit = _make(
        models.DetachedRebuildAudit,
        {"v227_freeze_audit_id": freeze.audit_id, "archived_source_files": len(members)},
        "audit_id",
        models.DetachedRebuildAudit.prefix(),
    )
    return audit, rebuilt


@dataclass(frozen=True)
class SourceData:
    audit: models.SourcePartitionAudit
    records: tuple[v226_models.JobFailureRecord, ...]
    public_payloads: dict[int, tuple[dict[str, Any], ...]]


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


def _public_payloads(
    root: Path, record: v226_models.JobFailureRecord
) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    safe_job = _sha(record.job_id.encode())
    for expected_ordinal, call in enumerate(record.provider_calls):
        request_descriptors = tuple(
            item for item in call.artifacts if item.artifact_kind == "request_metadata"
        )
        response_descriptors = tuple(
            item for item in call.artifacts if item.artifact_kind == "response_metadata"
        )
        if (
            call.status != "succeeded"
            or call.call_ordinal != expected_ordinal
            or len(request_descriptors) != 1
            or len(response_descriptors) != 1
        ):
            _fail("source.call", "source call order/status/artifact geometry differs")
        request_descriptor = request_descriptors[0]
        expected_request_path = (
            f"provider_calls/{safe_job}/call_{expected_ordinal:02d}_request_metadata.json"
        )
        request_bytes = (root / request_descriptor.relative_path).read_bytes()
        request_metadata = _load_bytes(request_bytes)
        if (
            request_descriptor.relative_path != expected_request_path
            or request_descriptor.provider_call_id != call.provider_call_id
            or _sha(request_bytes) != request_descriptor.sha256
            or len(request_bytes) != request_descriptor.byte_count
            or request_metadata.get("call_ordinal") != expected_ordinal
            or request_metadata.get("request_sha256") != call.request_sha256
        ):
            _fail("source.request_metadata", "request metadata three-way relation differs")
        response_descriptor = response_descriptors[0]
        expected_response_path = (
            f"provider_calls/{safe_job}/call_{expected_ordinal:02d}_response_metadata.json"
        )
        response_bytes = (root / response_descriptor.relative_path).read_bytes()
        response_metadata = _load_bytes(response_bytes)
        projection = response_metadata.get("public_projection")
        if (
            response_descriptor.relative_path != expected_response_path
            or response_descriptor.provider_call_id != call.provider_call_id
            or _sha(response_bytes) != response_descriptor.sha256
            or len(response_bytes) != response_descriptor.byte_count
            or not isinstance(projection, dict)
            or projection != response_descriptor.public_projection
            or response_metadata.get("public_projection_sha256")
            != response_descriptor.public_projection_sha256
            or response_descriptor.public_projection_sha256 != call.response_sha256
            or response_descriptor.public_projection_sha256
            != _sha(models.canonical_bytes(projection))
            or response_metadata.get("provider_call_id") != call.provider_call_id
            or response_metadata.get("raw_provider_response_persisted") is not False
            or response_metadata.get("private_reasoning_persisted") is not False
        ):
            _fail("source.response_metadata", "response metadata relation differs")
        result.append(cast(dict[str, Any], projection))
    return tuple(result)


def _source_partition(
    repository_root: Path, freeze: models.V227FreezeAudit, saved: dict[str, bytes]
) -> SourceData:
    root = repository_root / V226_DIR
    summary = v226_models.ExecutionSummary.model_validate(_load(root / "execution_summary.json"))
    host: list[v226_models.JobFailureRecord] = []
    provider: list[v226_models.JobFailureRecord] = []
    host_projection: list[dict[str, Any]] = []
    provider_projection: list[dict[str, Any]] = []
    payloads: dict[int, tuple[dict[str, Any], ...]] = {}
    for embedded in sorted(summary.failure_records, key=lambda item: item.job_ordinal):
        path = f"job_failures/job_{embedded.job_ordinal:03d}.json"
        raw = (root / path).read_bytes()
        record = v226_models.JobFailureRecord.model_validate(_load_bytes(raw))
        if _encoded(record) != raw or record != embedded:
            _fail("source.failure_record", f"failure record differs:{path}")
        projection = _source_projection(path, raw, record)
        if record.failure_kind == "host_failure":
            host.append(record)
            host_projection.append(projection)
            payloads[record.job_ordinal] = _public_payloads(root, record)
        elif record.failure_kind == "unbound_provider_failure":
            provider.append(record)
            provider_projection.append(projection)
        else:
            _fail("source.failure_kind", "failure kind outside exact source partition")
    if tuple(row.job_ordinal for row in host) != models.HOST_ORDINALS or len(provider) != 33:
        _fail("source.partition", "3/33 source partition differs")
    host_sha = _sha(models.canonical_bytes(tuple(host_projection)))
    provider_sha = _sha(models.canonical_bytes(tuple(provider_projection)))
    v227_freeze = _load_bytes(saved["v226_freeze.json"])
    if host_sha != v227_freeze.get(
        "host_failure_source_set_sha256"
    ) or provider_sha != v227_freeze.get("unbound_provider_failure_exclusion_set_sha256"):
        _fail("source.set_equality", "independent source set differs from frozen set")
    rows = tuple(
        models.SourceRow(
            ordinal=row.job_ordinal,
            job_id=row.job_id,
            record_id=row.record_id,
            failure_kind=row.failure_kind,
            failure_file_sha256=_sha(
                (root / f"job_failures/job_{row.job_ordinal:03d}.json").read_bytes()
            ),
            failure_file_byte_count=len(
                (root / f"job_failures/job_{row.job_ordinal:03d}.json").read_bytes()
            ),
            provider_call_count=len(row.provider_calls),
            provider_call_ids=tuple(call.provider_call_id for call in row.provider_calls),
        )
        for row in host
    )
    audit = _make(
        models.SourcePartitionAudit,
        {
            "v227_freeze_audit_id": freeze.audit_id,
            "host_rows": rows,
            "host_source_set_sha256": host_sha,
            "exclusion_set_sha256": provider_sha,
        },
        "audit_id",
        models.SourcePartitionAudit.prefix(),
    )
    return SourceData(audit=audit, records=tuple(host), public_payloads=payloads)


def _registry_policies(repository_root: Path) -> dict[str, str]:
    payload = (repository_root / REGISTRY_FILE).read_bytes()
    value = _load_bytes(payload)
    if (
        _sha(payload) != models.TERMINAL_REGISTRY_FILE_SHA256
        or value.get("registry_id") != models.TERMINAL_REGISTRY_ID
    ):
        _fail("derivation.registry", "exact v26.195 Terminal Registry differs")
    policies = {
        str(row["terminal_kind"]): str(row["policy_id"])
        for row in value.get("policies", ())
        if isinstance(row, dict) and row.get("registration_status") == "reachable"
    }
    if (
        policies.get(PARSER_TERMINAL) != PARSER_POLICY
        or policies.get(REFERENCE_TERMINAL) != REFERENCE_POLICY
    ):
        _fail("derivation.registry_policy", "reachable terminal policy differs")
    return policies


@dataclass(frozen=True)
class ReplayData:
    audit: models.ReplayAndDerivationAudit
    hosts: dict[int, dict[str, Any]]
    evidence: dict[int, dict[str, Any]]
    decisions: dict[int, dict[str, Any]]
    authority: dict[str, bytes]


def _independent_replay(
    job: v209_models.ExecutableDevelopmentJob,
    payloads: tuple[dict[str, Any], ...],
    loaded: dict[str, Any],
) -> tuple[v209_models.ExecutableInvocationRecord, ...]:
    transport = v209.ScriptedTransport()
    for payload in payloads:
        transport.queue(payload)
    runner = v209._make_runner(
        transport=transport,
        config=loaded["config"],
        parents=loaded["parents"],
        prepared=loaded["runtime"],
        implementation_id=loaded["implementation"].implementation_id,
    )
    context = v209._context_for_job(job=job, parents=loaded["parents"], prepared=loaded["runtime"])
    state = frozen_runtime._initialize(context)
    records: list[v209_models.ExecutableInvocationRecord] = []
    index = 0
    while state.current_index < len(state.ordered_components):
        outcome = runner.invoke_action(job=job, invocation_index=index, state=state)
        records.append(outcome.record)
        index += 1
        if outcome.terminal is not None:
            break
        if outcome.record.action_accepted is True:
            continue
        if not isinstance(outcome.runtime_output, step_runtime.PublicTypedRejectionObservation):
            _fail("replay.action", "rejected Action lacks public feedback")
        correction = runner.invoke_correction(job=job, invocation_index=index, state=state)
        records.append(correction.record)
        index += 1
        if correction.terminal is not None or correction.record.action_accepted is not True:
            break
    if len(records) != len(payloads) or len(transport.dispatches) != len(payloads):
        _fail("replay.geometry", "independent replay geometry differs")
    return tuple(records)


def _host_dict(
    repository_root: Path,
    record: v226_models.JobFailureRecord,
    payloads: tuple[dict[str, Any], ...],
    saved_freeze: dict[str, Any],
) -> dict[str, Any]:
    raw_path = f"job_failures/job_{record.job_ordinal:03d}.json"
    raw = (repository_root / V226_DIR / raw_path).read_bytes()
    try:
        parse_exact_canonical_action_payload(payloads[-1])
    except SemanticActionResponseRejection:
        expected_kind = "subsequent_action_parser_rejection"
    else:
        expected_kind = "subsequent_action_reference_failure"
    value = {
        "row_id": "pending",
        "v226_freeze_id": saved_freeze["freeze_id"],
        "job_id": record.job_id,
        "job_ordinal": record.job_ordinal,
        "failure_record_id": record.record_id,
        "failure_relative_path": raw_path,
        "failure_file_sha256": _sha(raw),
        "failure_file_byte_count": len(raw),
        "failure_record": record.model_dump(mode="json", warnings=False),
        "failure_record_sha256": _sha(
            models.canonical_bytes(record.model_dump(mode="json", warnings=False))
        ),
        "public_payloads": payloads,
        "public_payload_sha256s": tuple(_sha(models.canonical_bytes(row)) for row in payloads),
        "expected_evidence_kind": expected_kind,
        "terminal_evidence_admitted_in_v226": False,
        "historical_terminal_added": False,
        "provider_calls": 0,
        "schema_version": "fresh_exact_v209_subsequent_action_evidence_domain_closure.v1",
    }
    value["row_id"] = _content_id(value, "row_id", "finance_v26_227_host_failure_row:")
    return value


def _content_id(value: dict[str, Any], field: str, prefix: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    from trusted_synthesis.hashing import canonical_hash

    return canonical_hash(payload, prefix=prefix)


def _derive_evidence(
    host: dict[str, Any],
    records: tuple[v209_models.ExecutableInvocationRecord, ...],
    saved_authorization: dict[str, Any],
    saved_source: dict[str, Any],
    registry_policies: dict[str, str],
    saved_binding: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if saved_binding is None:
        saved_binding = _load(Path(V227_DIR) / "dispatcher_binding.json")
    last = records[-1]
    payload = cast(dict[str, Any], host["public_payloads"][-1])
    if (
        tuple(row.invocation_index for row in records) != tuple(range(len(records)))
        or records[0].phase != "first_action"
        or last.phase != "subsequent_action"
        or any(row.job_id != host["job_id"] for row in records)
        or any(row.typed_terminal is not None for row in records[:-1])
        or any(not row.exact_response_parsed for row in records[:-1])
        or any(not row.current_state_and_candidate_or_final_envelope_valid for row in records[:-1])
        or any(not row.runtime_step_or_finalize_completed for row in records[:-1])
        or any(row.public_response_sha256 is None for row in records[:-1])
        or last.runtime_step_or_finalize_completed
        or last.action_accepted is not None
    ):
        _fail("evidence.prefix", "invocation prefix differs")
    common: dict[str, Any] = {
        "evidence_id": "pending",
        "external_authorization_id": saved_authorization["authorization_id"],
        "v226_freeze_id": host["v226_freeze_id"],
        "source_identity_id": saved_source["source_identity_id"],
        "host_failure_row_id": host["row_id"],
        "job_id": host["job_id"],
        "job_ordinal": host["job_ordinal"],
        "phase": "subsequent_action",
        "invocation_records": tuple(row.model_dump(mode="json", warnings=False) for row in records),
        "public_payload": payload,
        "public_payload_sha256": _sha(models.canonical_bytes(payload)),
        "current_state_id": last.current_state_id,
        "current_candidate_action_ids": last.candidate_action_ids,
        "observed_state_id": payload.get("state_id"),
        "observed_action_id": payload.get("action_id"),
        "caller_terminal_input": False,
        "provider_calls": 0,
        "schema_version": "fresh_exact_v209_subsequent_action_evidence_domain_closure.v1",
    }
    if host["expected_evidence_kind"] == "subsequent_action_parser_rejection":
        try:
            parse_exact_canonical_action_payload(payload)
        except SemanticActionResponseRejection as error:
            if (
                error.family != "response_serialization_failure"
                or error.subtype != "canonical_action_not_exact_four_field_grammar"
            ):
                _fail("evidence.parser", "parser rejection taxonomy differs")
        else:
            _fail("evidence.parser", "parser row unexpectedly accepted")
        if (
            len(payload) != 4
            or last.typed_terminal != PARSER_TERMINAL
            or last.exact_response_parsed
            or last.current_state_and_candidate_or_final_envelope_valid
            or payload.get("decision_kind") in {"execute_public_operation", "select_candidate"}
        ):
            _fail("evidence.parser_predicate", "parser Evidence predicate differs")
        common.update(
            {
                "evidence_kind": "subsequent_action_parser_rejection",
                "parser_exception_type": "SemanticActionResponseRejection",
                "parser_exception_family": "response_serialization_failure",
                "parser_exception_subtype": "canonical_action_not_exact_four_field_grammar",
                "parser_rejected": True,
            }
        )
        prefix = "finance_v26_227_parser_subsequent_action_evidence:"
        terminal, policy, rule = (
            PARSER_TERMINAL,
            registry_policies[PARSER_TERMINAL],
            "subsequent_action_exact_parser_rejection",
        )
    else:
        proposal = parse_exact_canonical_action_payload(payload)
        if (
            last.typed_terminal != REFERENCE_TERMINAL
            or not last.exact_response_parsed
            or last.current_state_and_candidate_or_final_envelope_valid
            or proposal.state_id != last.current_state_id
            or proposal.action_id in last.candidate_action_ids
        ):
            _fail("evidence.reference_predicate", "reference Evidence predicate differs")
        common.update(
            {
                "evidence_kind": "subsequent_action_reference_failure",
                "parser_accepted": True,
                "current_reference_valid": False,
            }
        )
        prefix = "finance_v26_227_reference_subsequent_action_evidence:"
        terminal, policy, rule = (
            REFERENCE_TERMINAL,
            registry_policies[REFERENCE_TERMINAL],
            "subsequent_action_parsed_reference_not_current",
        )
    common["evidence_id"] = _content_id(common, "evidence_id", prefix)
    binding = saved_binding
    decision: dict[str, Any] = {
        "decision_id": "pending",
        "dispatcher_binding_id": binding["binding_id"],
        "evidence": common,
        "evidence_sha256": _sha(models.canonical_bytes(common)),
        "job_id": host["job_id"],
        "job_ordinal": host["job_ordinal"],
        "phase": "subsequent_action",
        "terminal_kind": terminal,
        "terminal_policy_id": policy,
        "derivation_rule": rule,
        "phase_was_input": False,
        "terminal_kind_was_input": False,
        "terminal_policy_was_input": False,
        "caller_terminal_was_input": False,
        "provider_calls": 0,
        "schema_version": "fresh_exact_v209_subsequent_action_evidence_domain_closure.v1",
    }
    decision["decision_id"] = _content_id(
        decision, "decision_id", "finance_v26_227_subsequent_action_dispatcher_decision:"
    )
    return common, decision


def _replay_and_derive(
    repository_root: Path, source: SourceData, saved: dict[str, bytes], detached: dict[str, bytes]
) -> ReplayData:
    saved_auth = _load_bytes(saved["external_authorization.json"])
    saved_source = _load_bytes(saved["source_identity.json"])
    saved_freeze = _load_bytes(saved["v226_freeze.json"])
    saved_binding = _load_bytes(saved["dispatcher_binding.json"])
    registry_policies = _registry_policies(repository_root)
    with TemporaryDirectory(prefix="finance-v26-228-replay-") as temp:
        loaded = v226._load_exact_runtime(repository_root, Path(temp))
        jobs = {row.job_id: row for row in loaded["manifest"].jobs}
        rows: list[models.ReplayRow] = []
        hosts: dict[int, dict[str, Any]] = {}
        evidence: dict[int, dict[str, Any]] = {}
        decisions: dict[int, dict[str, Any]] = {}
        authority: dict[str, bytes] = {}
        for record in source.records:
            host = _host_dict(
                repository_root,
                record,
                source.public_payloads[record.job_ordinal],
                saved_freeze,
            )
            saved_host = saved[f"host_failure_rows/job_{record.job_ordinal:03d}.json"]
            if _encoded(host) != saved_host:
                _fail("source.host_row_bytes", "independent Host row differs")
            replay = _independent_replay(
                jobs[record.job_id], source.public_payloads[record.job_ordinal], loaded
            )
            request_matches = response_matches = 0
            for invocation, provider_call in zip(replay, record.provider_calls, strict=True):
                request_descriptor = next(
                    item
                    for item in provider_call.artifacts
                    if item.artifact_kind == "request_metadata"
                )
                metadata = _load(repository_root / V226_DIR / request_descriptor.relative_path)
                if (
                    invocation.canonical_request_body_sha256
                    == provider_call.request_sha256
                    == metadata["request_sha256"]
                ):
                    request_matches += 1
                if invocation.public_response_sha256 == provider_call.response_sha256:
                    response_matches += 1
            if request_matches != len(replay) or response_matches != len(replay):
                _fail("replay.hashes", "request/response hash relation differs")
            observed, decision = _derive_evidence(
                host,
                replay,
                saved_auth,
                saved_source,
                registry_policies,
                saved_binding,
            )
            safe_job = _sha(record.job_id.encode())
            observed_path = f"replay_evidence/observed/{safe_job}.json"
            decision_path = f"replay_evidence/decision/{safe_job}.json"
            if (
                _encoded(observed) != saved[observed_path]
                or _encoded(observed) != detached[observed_path]
                or _encoded(decision) != saved[decision_path]
                or _encoded(decision) != detached[decision_path]
            ):
                _fail("derivation.saved_detached_bytes", "independent Evidence/Decision differs")
            authority[host["row_id"]] = models.canonical_bytes(observed)
            (
                hosts[record.job_ordinal],
                evidence[record.job_ordinal],
                decisions[record.job_ordinal],
            ) = host, observed, decision
            rows.append(
                models.ReplayRow(
                    ordinal=record.job_ordinal,
                    job_id=record.job_id,
                    invocation_count=len(replay),
                    phases=tuple(row.phase for row in replay),
                    request_match_count=request_matches,
                    response_match_count=response_matches,
                    call_order_match=tuple(row.invocation_index for row in replay)
                    == tuple(range(len(replay))),
                    success_status_match=all(
                        call.status == "succeeded" for call in record.provider_calls
                    ),
                    last_state_id=replay[-1].current_state_id,
                    last_candidate_action_ids=replay[-1].candidate_action_ids,
                    evidence_kind=observed["evidence_kind"],
                    derived_terminal=decision["terminal_kind"],
                    terminal_policy_id=decision["terminal_policy_id"],
                    derivation_rule=decision["derivation_rule"],
                    evidence_id=observed["evidence_id"],
                    decision_id=decision["decision_id"],
                )
            )
    audit = _make(
        models.ReplayAndDerivationAudit,
        {"source_partition_audit_id": source.audit.audit_id, "rows": tuple(rows)},
        "audit_id",
        models.ReplayAndDerivationAudit.prefix(),
    )
    return ReplayData(
        audit=audit, hosts=hosts, evidence=evidence, decisions=decisions, authority=authority
    )


def _layer_dict(
    kind: str,
    host: dict[str, Any],
    evidence: dict[str, Any],
    decision: dict[str, Any],
    parent: dict[str, Any] | None,
) -> dict[str, Any]:
    sequence = LAYER_KINDS.index(kind)
    payload: dict[str, Any] = {
        "layer_kind": kind,
        "job_id": host["job_id"],
        "job_ordinal": host["job_ordinal"],
        "terminal_kind": decision["terminal_kind"],
        "terminal_policy_id": decision["terminal_policy_id"],
        "evidence_id": evidence["evidence_id"],
        "evidence_sha256": _sha(models.canonical_bytes(evidence)),
        "dispatcher_decision_id": decision["decision_id"],
        "parent_artifact_id": None if parent is None else parent["artifact_id"],
        "persisted_sequence": sequence,
        "formal_empirical_row": False,
    }
    if kind == "raw":
        payload["observed_evidence"] = evidence
        payload["host_failure_source"] = {
            "host_failure_row_id": host["row_id"],
            "failure_record_id": host["failure_record_id"],
            "failure_relative_path": host["failure_relative_path"],
            "failure_file_sha256": host["failure_file_sha256"],
        }
    elif kind == "result":
        payload["derived_decision"] = decision
    elif kind == "trace":
        payload["invocation_records"] = evidence["invocation_records"]
    elif kind == "outcome":
        payload["terminal_projection"] = {
            "terminal_kind": decision["terminal_kind"],
            "terminal_policy_id": decision["terminal_policy_id"],
            "derivation_rule": decision["derivation_rule"],
        }
    else:
        payload["closed_layer_ids"] = ()
    safe_job = _sha(host["job_id"].encode())
    relative_path = (
        f"replay_checkpoints/job_{host['job_ordinal']:03d}.json"
        if kind == "checkpoint"
        else f"replay_evidence/{kind}/{safe_job}.json"
    )
    value: dict[str, Any] = {
        "artifact_id": "pending",
        "layer_kind": kind,
        "external_authorization_id": evidence["external_authorization_id"],
        "v226_freeze_id": evidence["v226_freeze_id"],
        "source_identity_id": evidence["source_identity_id"],
        "host_failure_row_id": host["row_id"],
        "evidence_id": evidence["evidence_id"],
        "dispatcher_decision_id": decision["decision_id"],
        "job_id": host["job_id"],
        "job_ordinal": host["job_ordinal"],
        "terminal_kind": decision["terminal_kind"],
        "parent_artifact_id": None if parent is None else parent["artifact_id"],
        "payload": payload,
        "payload_sha256": _sha(models.canonical_bytes(payload)),
        "relative_path": relative_path,
        "persisted_sequence": sequence,
        "historical_v226_artifact": False,
        "formal_empirical_row": False,
        "provider_calls": 0,
        "schema_version": "fresh_exact_v209_subsequent_action_evidence_domain_closure.v1",
    }
    value["artifact_id"] = _content_id(
        value, "artifact_id", "finance_v26_227_replay_layer_artifact:"
    )
    return value


def _chain_layers(
    host: dict[str, Any], evidence: dict[str, Any], decision: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    made: list[dict[str, Any]] = []
    for kind in LAYER_KINDS:
        made.append(_layer_dict(kind, host, evidence, decision, made[-1] if made else None))
    checkpoint = copy.deepcopy(made[-1])
    checkpoint["payload"]["closed_layer_ids"] = tuple(row["artifact_id"] for row in made[:-1])
    checkpoint["payload_sha256"] = _sha(models.canonical_bytes(checkpoint["payload"]))
    checkpoint["artifact_id"] = _content_id(
        checkpoint, "artifact_id", "finance_v26_227_replay_layer_artifact:"
    )
    made[-1] = checkpoint
    return tuple(made)


def _reconstruct_layers(
    replay: ReplayData, saved: dict[str, bytes], detached: dict[str, bytes]
) -> models.LayerReconstructionAudit:
    matches: list[models.LayerMatch] = []
    for ordinal in models.HOST_ORDINALS:
        layers = _chain_layers(
            replay.hosts[ordinal], replay.evidence[ordinal], replay.decisions[ordinal]
        )
        for layer in layers:
            path = layer["relative_path"]
            rebuilt = _encoded(layer)
            if rebuilt != saved[path] or rebuilt != detached[path]:
                _fail("layers.byte_equality", f"independent layer differs:{path}")
            matches.append(
                models.LayerMatch(
                    ordinal=ordinal,
                    layer_kind=layer["layer_kind"],
                    relative_path=path,
                    artifact_id=layer["artifact_id"],
                    sha256=_sha(rebuilt),
                    byte_count=len(rebuilt),
                )
            )
    return _make(
        models.LayerReconstructionAudit,
        {"replay_audit_id": replay.audit.audit_id, "layers": tuple(matches)},
        "audit_id",
        models.LayerReconstructionAudit.prefix(),
    )


def _admit(
    evidence: dict[str, Any], *, authority: dict[str, bytes], host_row_ids: set[str]
) -> None:
    if evidence.get("host_failure_row_id") not in host_row_ids:
        _fail("admission.source_authority", "Evidence source is outside exact Host rows")
    records = tuple(
        v209_models.ExecutableInvocationRecord.model_validate(row)
        for row in evidence.get("invocation_records", ())
    )
    if (
        not records
        or tuple(row.invocation_index for row in records) != tuple(range(len(records)))
        or any(row.job_id != evidence.get("job_id") for row in records)
        or records[0].phase != "first_action"
        or any(row.typed_terminal is not None for row in records[:-1])
        or any(not row.exact_response_parsed for row in records[:-1])
        or any(not row.current_state_and_candidate_or_final_envelope_valid for row in records[:-1])
        or any(not row.runtime_step_or_finalize_completed for row in records[:-1])
    ):
        _fail("admission.invocation_prefix", "same-Job complete prefix differs")
    if evidence.get("phase") != "subsequent_action" or records[-1].phase != "subsequent_action":
        _fail("admission.phase", "phase differs")
    last = records[-1]
    if evidence.get("current_state_id") != last.current_state_id:
        _fail("admission.current_state", "stale State differs")
    if tuple(evidence.get("current_candidate_action_ids", ())) != last.candidate_action_ids:
        _fail("admission.current_candidates", "stale Candidates differ")
    payload = evidence.get("public_payload")
    if (
        not isinstance(payload, dict)
        or evidence.get("public_payload_sha256") != _sha(models.canonical_bytes(payload))
        or last.public_response_sha256 != evidence.get("public_payload_sha256")
        or evidence.get("observed_state_id") != payload.get("state_id")
        or evidence.get("observed_action_id") != payload.get("action_id")
    ):
        _fail("admission.public_response", "terminal public response binding differs")
    kind = evidence.get("evidence_kind")
    if kind == "subsequent_action_parser_rejection":
        try:
            parse_exact_canonical_action_payload(evidence["public_payload"])
        except SemanticActionResponseRejection:
            pass
        else:
            _fail("admission.evidence_variant", "parser variant carries accepted payload")
        if last.typed_terminal != PARSER_TERMINAL:
            _fail("admission.terminal", "parser terminal differs")
    elif kind == "subsequent_action_reference_failure":
        try:
            proposal = parse_exact_canonical_action_payload(evidence["public_payload"])
        except SemanticActionResponseRejection as error:
            raise V228Error(
                "admission.evidence_variant", "reference variant carries parser rejection"
            ) from error
        if (
            proposal.action_id in last.candidate_action_ids
            or last.typed_terminal != REFERENCE_TERMINAL
        ):
            _fail("admission.reference", "reference failure predicate differs")
    else:
        _fail("admission.evidence_variant", "Evidence kind differs")
    if authority.get(str(evidence["host_failure_row_id"])) != models.canonical_bytes(evidence):
        _fail("admission.replay_owned_bytes", "Evidence differs from independent replay authority")


def _capture(name: str, function: Any, *, rehashed_layers: int = 0) -> models.AttackResult:
    try:
        function()
    except Exception as error:  # noqa: BLE001 - diagnostic requires the actual exception type
        stage = error.stage if isinstance(error, V228Error) else "schema.validation"
        reason = error.reason if isinstance(error, V228Error) else str(error)
        return models.AttackResult(
            name=name,
            exception_type=type(error).__name__,
            rejection_stage=stage,
            reason_sha256=_sha(reason.encode()),
            candidate_rehashed_layers=rehashed_layers,
        )
    _fail("negative.accepted", f"negative control accepted:{name}")


def _negative_controls(
    repository_root: Path, replay: ReplayData, source: SourceData
) -> models.NegativeControlAudit:
    base = copy.deepcopy(replay.evidence[6])
    other = copy.deepcopy(replay.evidence[22])
    host_ids = set(replay.authority)

    def admit(value: dict[str, Any]) -> None:
        _admit(value, authority=replay.authority, host_row_ids=host_ids)

    attacks: list[models.AttackResult] = []
    value = copy.deepcopy(base)
    value["phase"] = "first_action"
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[0], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    value["evidence_kind"] = "subsequent_action_reference_failure"
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[1], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    value["invocation_records"] = (
        *value["invocation_records"][:-1],
        other["invocation_records"][-1],
    )
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[2], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    value["invocation_records"] = value["invocation_records"][1:]
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[3], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    value["current_state_id"] = value["invocation_records"][0]["current_state_id"]
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[4], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    value["current_candidate_action_ids"] = value["invocation_records"][0]["candidate_action_ids"]
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[5], lambda value=value: admit(value)))
    value = copy.deepcopy(base)
    last = copy.deepcopy(value["invocation_records"][-1])
    forged_payload = copy.deepcopy(value["public_payload"])
    forged_payload["decision_kind"] = "revise_selector"
    try:
        parse_exact_canonical_action_payload(forged_payload)
    except SemanticActionResponseRejection:
        pass
    else:
        _fail("negative.full_rehash_fixture", "forged payload must remain parser-invalid")
    forged_response_sha256 = _sha(models.canonical_bytes(forged_payload))
    last["public_response_sha256"] = forged_response_sha256
    last["invocation_id"] = _content_id(
        last, "invocation_id", "fresh_repaired_final_continuity_executable_invocation_record:"
    )
    value["invocation_records"] = (*value["invocation_records"][:-1], last)
    value["public_payload"] = forged_payload
    value["public_payload_sha256"] = forged_response_sha256
    value["evidence_id"] = _content_id(
        value, "evidence_id", "finance_v26_227_parser_subsequent_action_evidence:"
    )
    decision = copy.deepcopy(replay.decisions[6])
    decision["evidence"] = value
    decision["evidence_sha256"] = _sha(models.canonical_bytes(value))
    decision["decision_id"] = _content_id(
        decision, "decision_id", "finance_v26_227_subsequent_action_dispatcher_decision:"
    )
    forged_layers = _chain_layers(replay.hosts[6], value, decision)
    if len({row["artifact_id"] for row in forged_layers}) != 5 or tuple(
        row["parent_artifact_id"] for row in forged_layers
    ) != (None,) + tuple(row["artifact_id"] for row in forged_layers[:-1]):
        _fail("negative.full_rehash_fixture", "forged five-layer chain is inconsistent")
    attacks.append(
        _capture(
            models.NEGATIVE_CONTROL_NAMES[6], lambda value=value: admit(value), rehashed_layers=5
        )
    )
    provider_record = next(
        row
        for row in v226_models.ExecutionSummary.model_validate(
            _load(repository_root / V226_DIR / "execution_summary.json")
        ).failure_records
        if row.failure_kind == "unbound_provider_failure"
    )
    value = copy.deepcopy(base)
    value["host_failure_row_id"] = provider_record.record_id
    attacks.append(_capture(models.NEGATIVE_CONTROL_NAMES[7], lambda value=value: admit(value)))
    return _make(
        models.NegativeControlAudit,
        {"results": tuple(attacks)},
        "audit_id",
        models.NegativeControlAudit.prefix(),
    )


def _scope() -> models.ScopeBoundaryAudit:
    return _make(models.ScopeBoundaryAudit, {}, "audit_id", models.ScopeBoundaryAudit.prefix())


def _write(output_dir: Path, payloads: dict[str, bytes]) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        _fail("output.no_replace", "output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, payload in payloads.items():
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
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
    freeze, saved = _freeze_v227(repository_root, authorization.authorization_id)
    source = _source_identity(repository_root, source_identity)
    implementation = _implementation_binding(repository_root, source)
    detached, rebuilt = _detached_rebuild(repository_root, freeze, saved)
    partition = _source_partition(repository_root, freeze, saved)
    replay = _replay_and_derive(repository_root, partition, saved, rebuilt)
    layers = _reconstruct_layers(replay, saved, rebuilt)
    negative = _negative_controls(repository_root, replay, partition)
    scope = _scope()
    gates = (
        models.Gate(name=models.GATE_NAMES[0], evidence_ids=(freeze.audit_id,)),
        models.Gate(
            name=models.GATE_NAMES[1],
            evidence_ids=(detached.audit_id, source.source_identity_id, implementation.binding_id),
        ),
        models.Gate(name=models.GATE_NAMES[2], evidence_ids=(partition.audit.audit_id,)),
        models.Gate(name=models.GATE_NAMES[3], evidence_ids=(replay.audit.audit_id,)),
        models.Gate(name=models.GATE_NAMES[4], evidence_ids=(replay.audit.audit_id,)),
        models.Gate(name=models.GATE_NAMES[5], evidence_ids=(layers.audit_id,)),
        models.Gate(name=models.GATE_NAMES[6], evidence_ids=(negative.audit_id, scope.audit_id)),
    )
    gate = _make(
        models.GateEvaluation, {"gates": gates}, "evaluation_id", models.GateEvaluation.prefix()
    )
    decision = _make(
        models.Decision,
        {"gate_evaluation_id": gate.evaluation_id},
        "decision_id",
        models.Decision.prefix(),
    )
    transition = _make(
        models.Transition,
        {"decision_id": decision.decision_id},
        "transition_id",
        models.Transition.prefix(),
    )
    report = _make(
        models.Report,
        {
            "authorization_id": authorization.authorization_id,
            "source_identity_id": source.source_identity_id,
            "implementation_binding_id": implementation.binding_id,
            "freeze_audit_id": freeze.audit_id,
            "detached_rebuild_audit_id": detached.audit_id,
            "source_partition_audit_id": partition.audit.audit_id,
            "replay_and_derivation_audit_id": replay.audit.audit_id,
            "layer_reconstruction_audit_id": layers.audit_id,
            "negative_control_audit_id": negative.audit_id,
            "scope_boundary_audit_id": scope.audit_id,
            "gate_evaluation_id": gate.evaluation_id,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
        },
        "report_id",
        models.Report.prefix(),
    )
    payloads = {
        "external_review.txt": review,
        "operator_directive.txt": models.OPERATOR_DIRECTIVE.encode(),
        "external_authorization.json": _encoded(authorization),
        "source_identity.json": _encoded(source),
        "implementation_binding.json": _encoded(implementation),
        "v227_freeze_audit.json": _encoded(freeze),
        "detached_rebuild_audit.json": _encoded(detached),
        "source_partition_audit.json": _encoded(partition.audit),
        "replay_and_derivation_audit.json": _encoded(replay.audit),
        "layer_reconstruction_audit.json": _encoded(layers),
        "negative_control_audit.json": _encoded(negative),
        "scope_boundary_audit.json": _encoded(scope),
        "gate_evaluation.json": _encoded(gate),
        "decision.json": _encoded(decision),
        "prospective_transition.json": _encoded(transition),
        "report.json": _encoded(report),
    }
    manifest = models.artifact_manifest(RUN_ID, payloads)
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
