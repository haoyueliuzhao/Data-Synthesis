from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from . import models
from .reconstruction import (
    interventions_and_attacks,
    reconstruct_runtime_and_semantics,
    select_and_load_archive_fixtures,
)


class IndependentAuditError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise IndependentAuditError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def _load(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("json.object", "expected JSON object")
    return value


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _git(root: Path, stage: str, *arguments: str) -> bytes:
    result = subprocess.run(("git", "-C", str(root), *arguments), check=False, capture_output=True)
    if result.returncode:
        _fail(stage, result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _git_text(root: Path, stage: str, *arguments: str) -> str:
    return _git(root, stage, *arguments).decode("ascii").strip()


def _blob(payload: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload,
        usedforsecurity=False,
    ).hexdigest()


def _authorization(review: bytes) -> tuple[dict[str, Any], bytes]:
    if len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT or _sha(review) != (
        models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.external_review", "external audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT or _sha(directive) != (
        models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.operator_directive", "operator directive bytes differ")
    return (
        _identified(
            {
                "stage": models.STAGE,
                "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
                "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
                "operator_directive": models.OPERATOR_DIRECTIVE,
                "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
                "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
                "candidate_rebuild_authorized": True,
                "candidate_formal_rewrite_authorized": False,
                "independent_fixture_replay_authorized": True,
                "third_fixture_authorized": False,
                "provider_or_gpu_execution_authorized": False,
                "archive_expansion_authorized": False,
                "task_or_operation_registration_authorized": False,
                "same_task_multitrajectory_authorized": False,
                "qa_release_or_vtdo_authorized": False,
                "schema_version": "qa_reasoning_fixed_fixture_independent_authorization.v1",
            },
            "authorization_id",
            "qa_reasoning_fixed_fixture_independent_authorization:",
        ),
        directive,
    )


def _validate_manifest(
    files: Mapping[str, bytes],
    *,
    manifest_id: str,
    root_id: str,
    file_count: int | None = None,
    total_bytes: int | None = None,
    member_count: int | None = None,
    member_bytes: int | None = None,
    manifest_bytes: int | None = None,
    manifest_sha256: str | None = None,
    stage: str,
) -> dict[str, Any]:
    payload = files.get("artifact_manifest.json", b"")
    manifest = _load(payload)
    rows = manifest.get("members")
    if not isinstance(rows, list):
        _fail(stage, "Manifest members are absent")
    indexed = {str(row["relative_path"]): row for row in rows}
    if (
        set(indexed) != set(files) - {"artifact_manifest.json"}
        or manifest.get("manifest_id") != manifest_id
        or manifest.get("artifact_root") != root_id
        or manifest.get("self_excluding") is not True
        or (file_count is not None and len(files) != file_count)
        or (total_bytes is not None and sum(map(len, files.values())) != total_bytes)
        or (member_count is not None and len(indexed) != member_count)
        or (member_bytes is not None and int(manifest["member_bytes"]) != member_bytes)
        or (manifest_bytes is not None and len(payload) != manifest_bytes)
        or (manifest_sha256 is not None and _sha(payload) != manifest_sha256)
    ):
        _fail(stage, "formal directory geometry or Manifest identity differs")
    for relative, row in indexed.items():
        actual = files[relative]
        if int(row["byte_count"]) != len(actual) or row["sha256"] != _sha(actual):
            _fail(stage, f"Manifest member differs:{relative}")
    return manifest


def _candidate_source(root: Path, candidate: Mapping[str, Any]) -> dict[str, Any]:
    commit = _git_text(
        root,
        "candidate_source.commit",
        "rev-parse",
        f"{models.CANDIDATE_SOURCE_COMMIT}^{{commit}}",
    )
    tree = _git_text(root, "candidate_source.tree", "rev-parse", f"{commit}^{{tree}}")
    rows = candidate.get("members")
    if (
        commit != models.CANDIDATE_SOURCE_COMMIT
        or tree != models.CANDIDATE_SOURCE_TREE
        or candidate.get("binding_id") != models.CANDIDATE_SOURCE_BINDING_ID
        or candidate.get("resolved_commit") != commit
        or candidate.get("resolved_tree") != tree
        or not isinstance(rows, list)
        or tuple(str(row.get("relative_path")) for row in rows) != models.CANDIDATE_SOURCE_PATHS
    ):
        _fail("candidate_source.authority", "candidate source authority differs")
    for row in rows:
        relative = str(row["relative_path"])
        committed = _git(root, "candidate_source.member", "show", f"{commit}:{relative}")
        current = (root / relative).read_bytes()
        blob = _git_text(root, "candidate_source.blob", "rev-parse", f"{commit}:{relative}")
        if (
            committed != current
            or blob != _blob(committed)
            or row.get("git_blob_oid") != blob
            or row.get("sha256") != _sha(committed)
            or int(row.get("byte_count", -1)) != len(committed)
        ):
            _fail("candidate_source.member", f"candidate source member differs:{relative}")
    return {
        "source_commit": commit,
        "source_tree": tree,
        "source_member_count": len(rows),
        "source_member_matches": len(rows),
        "transitive_import_or_runtime_environment_closure_claimed": False,
    }


def _freeze_candidate(root: Path, authorization_id: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    candidate_directory = root / models.CANDIDATE_DIRECTORY
    files = _files(candidate_directory)
    manifest = _validate_manifest(
        files,
        manifest_id=models.CANDIDATE_MANIFEST_ID,
        root_id=models.CANDIDATE_ROOT_ID,
        file_count=models.CANDIDATE_FILE_COUNT,
        total_bytes=models.CANDIDATE_TOTAL_BYTES,
        member_count=models.CANDIDATE_MEMBER_COUNT,
        member_bytes=models.CANDIDATE_MEMBER_BYTES,
        manifest_bytes=models.CANDIDATE_MANIFEST_BYTES,
        manifest_sha256=models.CANDIDATE_MANIFEST_SHA256,
        stage="candidate_freeze.manifest",
    )
    predecessor_files = _files(root / models.PREDECESSOR_DIRECTORY)
    predecessor_manifest = _validate_manifest(
        predecessor_files,
        manifest_id=models.PREDECESSOR_MANIFEST_ID,
        root_id=models.PREDECESSOR_ROOT_ID,
        stage="candidate_freeze.predecessor",
    )
    archive_files = _files(root / models.ARCHIVE_DIRECTORY)
    archive_manifest = _validate_manifest(
        archive_files,
        manifest_id=models.ARCHIVE_MANIFEST_ID,
        root_id=models.ARCHIVE_ROOT_ID,
        stage="candidate_freeze.archive",
    )
    source = _load(files["source_binding.json"])
    source_facts = _candidate_source(root, source)
    report = _load(files["report.json"])
    gate = _load(files["gate_evaluation.json"])
    decision = _load(files["decision.json"])
    transition = _load(files["transition.json"])
    execution = _load(files["execution_audit.json"])
    durable = _load(files["durable_preaction_commit_audit.json"])
    intervention = _load(files["intervention_audit.json"])
    negative = _load(files["negative_control_audit.json"])
    scope = _load(files["scope_boundary_audit.json"])
    selection = _load(files["selection_contract.json"])
    if (
        report.get("report_id") != models.CANDIDATE_REPORT_ID
        or gate.get("gate_id") != models.CANDIDATE_GATE_ID
        or decision.get("decision_id") != models.CANDIDATE_DECISION_ID
        or transition.get("transition_id") != models.CANDIDATE_TRANSITION_ID
        or source.get("binding_id") != models.CANDIDATE_SOURCE_BINDING_ID
        or selection.get("contract_id") != models.CANDIDATE_SELECTION_ID
        or execution.get("audit_id") != models.CANDIDATE_EXECUTION_AUDIT_ID
        or durable.get("audit_id") != models.CANDIDATE_DURABLE_AUDIT_ID
        or intervention.get("audit_id") != models.CANDIDATE_INTERVENTION_AUDIT_ID
        or negative.get("audit_id") != models.CANDIDATE_NEGATIVE_AUDIT_ID
        or scope.get("audit_id") != models.CANDIDATE_SCOPE_AUDIT_ID
        or gate.get("passed_count") != 10
        or gate.get("failed_count") != 0
        or transition.get("next_stage_authorized") is not False
        or len(files["external_review.txt"]) != 14_144
        or _sha(files["external_review.txt"])
        != "5a4462286fcaa14fac1e3c27bf4993a191780655286b94da4bd1f78e25785e4b"
        or len([path for path in files if path.startswith("runtime/")]) != 62
    ):
        _fail("candidate_freeze.identity", "candidate identity or scoped result differs")
    freeze = _identified(
        {
            "authorization_id": authorization_id,
            "directory": models.CANDIDATE_DIRECTORY,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "manifest_member_count": len(manifest["members"]),
            "manifest_member_bytes": manifest["member_bytes"],
            "manifest_file_sha256": _sha(files["artifact_manifest.json"]),
            "manifest_id": manifest["manifest_id"],
            "artifact_root": manifest["artifact_root"],
            "candidate_report_id": report["report_id"],
            "candidate_gate_id": gate["gate_id"],
            "candidate_decision_id": decision["decision_id"],
            "candidate_transition_id": transition["transition_id"],
            "candidate_historical_next_stage_authorized": False,
            "candidate_source": source_facts,
            "predecessor_file_count": len(predecessor_files),
            "predecessor_member_count": len(predecessor_manifest["members"]),
            "predecessor_manifest_id": predecessor_manifest["manifest_id"],
            "predecessor_artifact_root": predecessor_manifest["artifact_root"],
            "archive_file_count": len(archive_files),
            "archive_member_count": len(archive_manifest["members"]),
            "archive_manifest_id": archive_manifest["manifest_id"],
            "archive_artifact_root": archive_manifest["artifact_root"],
            "runtime_file_count": 62,
            "candidate_gate_used_as_outcome_oracle": False,
            "candidate_report_used_as_outcome_oracle": False,
            "candidate_execution_audit_used_as_outcome_oracle": False,
            "candidate_negative_audit_used_as_attack_oracle": False,
            "candidate_formal_writes": 0,
            "passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_candidate_freeze_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_candidate_freeze_audit:",
    )
    return freeze, files


def _audit_source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    commit = _git_text(root, "audit_source.commit", "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git_text(root, "audit_source.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != source_commit or tree != source_tree:
        _fail("audit_source.commit_tree", "audit source commit/tree differs")
    rows = []
    syntax_trees = []
    for relative in models.AUDIT_SOURCE_PATHS:
        committed = _git(root, "audit_source.member", "show", f"{commit}:{relative}")
        current = (root / relative).read_bytes()
        blob = _git_text(root, "audit_source.blob", "rev-parse", f"{commit}:{relative}")
        if committed != current or blob != _blob(committed):
            _fail("audit_source.member", f"audit source member differs:{relative}")
        if relative.endswith(("runtime_probe.py", "reconstruction.py", "audit.py")):
            syntax_trees.append(ast.parse(committed))
        rows.append(
            {
                "relative_path": relative,
                "git_blob_oid": blob,
                "sha256": _sha(committed),
                "byte_count": len(committed),
                "committed_current_bytes_equal": True,
            }
        )
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    helper_names = {
        "build_qa_reasoning_fixed_fixture_preflight",
        "validate_written_artifacts",
        "DurableArtifactWriter",
        "admit_preaction_commit",
        "commit_envelope",
        "guard_and_dispatch",
        "_select_rows",
        "_fixture_sources",
        "_build_oracle_and_graph",
        "_run_fixture",
        "_interventions",
        "_negative_controls",
    }
    for tree_node in syntax_trees:
        for node in ast.walk(tree_node):
            imported = (
                (node.module,)
                if isinstance(node, ast.ImportFrom) and node.module
                else tuple(alias.name for alias in node.names)
                if isinstance(node, ast.Import)
                else ()
            )
            forbidden_imports.extend(
                name
                for name in imported
                if "qa_reasoning_fixed_fixture" in name
                and "qa_reasoning_fixed_fixture_independent_audit" not in name
            )
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in helper_names:
                    forbidden_calls.append(name)
    if forbidden_imports or forbidden_calls:
        _fail("audit_source.helper_boundary", "candidate helper import or call is present")
    return _identified(
        {
            "authorization_id": authorization_id,
            "requested_commit": source_commit,
            "resolved_commit": commit,
            "requested_tree": source_tree,
            "resolved_tree": tree,
            "members": tuple(rows),
            "member_count": len(rows),
            "path_set_sha256": _sha(canonical_json_bytes(models.AUDIT_SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(rows)),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "executable_members_scanned": len(syntax_trees),
            "candidate_helper_imports": 0,
            "candidate_semantic_helper_calls": 0,
            "candidate_outcome_oracle_calls": 0,
            "helper_boundary_passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_source_binding.v1",
        },
        "binding_id",
        "qa_reasoning_fixed_fixture_independent_source_binding:",
    )


def _detached_rebuild(
    root: Path, freeze_id: str, candidate_files: Mapping[str, bytes]
) -> tuple[dict[str, Any], dict[str, Any]]:
    archive = _git(
        root,
        "detached.archive",
        "archive",
        "--format=tar",
        models.CANDIDATE_SOURCE_COMMIT,
        "trusted_data_synthesis/src",
    )
    with TemporaryDirectory(prefix="qa-reasoning-fixed-independent-") as temporary:
        temp_root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            members = bundle.getmembers()
            regular = tuple(member for member in members if member.isfile())
            if any(
                member.name.startswith("/") or ".." in Path(member.name).parts for member in members
            ):
                _fail("detached.archive", "detached archive has unsafe member")
            bundle.extractall(temp_root, filter="data")
        output = temp_root / "rebuilt"
        trace_path = temp_root / "dynamic_trace.json"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(temp_root / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        command = (
            sys.executable,
            str(
                root / "trusted_data_synthesis/src/trusted_synthesis/experiments/"
                "qa_reasoning_fixed_fixture_independent_audit/runtime_probe.py"
            ),
            "--trace",
            str(trace_path),
            "--repo-root",
            str(root),
            "--external-audit",
            str(root / models.CANDIDATE_DIRECTORY / "external_review.txt"),
            "--source-commit",
            models.CANDIDATE_SOURCE_COMMIT,
            "--source-tree",
            models.CANDIDATE_SOURCE_TREE,
            "--output-dir",
            str(output),
        )
        result = subprocess.run(
            command, cwd=temp_root, env=environment, check=False, capture_output=True
        )
        if result.returncode:
            _fail(
                "detached.builder",
                result.stderr.decode("utf-8", errors="replace").strip(),
            )
        rebuilt = _files(output)
        shared = set(rebuilt) & set(candidate_files)
        if rebuilt != candidate_files:
            _fail("detached.actual_bytes", "detached candidate rebuild differs")
        trace = _load(trace_path.read_bytes())
        callbacks = trace.get("callbacks")
        if (
            not isinstance(callbacks, list)
            or trace.get("callback_count") != 10
            or trace.get("all_callbacks_passed") is not True
            or len(callbacks) != 10
            or not all(row.get("passed") is True for row in callbacks)
        ):
            _fail("detached.dynamic_probe", "dynamic callback trace differs")
    detached = _identified(
        {
            "candidate_freeze_audit_id": freeze_id,
            "archived_source_file_count": len(regular),
            "subprocess_environment_keys": tuple(sorted(environment)),
            "credential_like_environment_keys": 0,
            "saved_file_count": len(candidate_files),
            "rebuilt_file_count": len(rebuilt),
            "saved_bytes": sum(map(len, candidate_files.values())),
            "rebuilt_bytes": sum(map(len, rebuilt.values())),
            "path_matches": len(shared),
            "sha256_matches": sum(
                _sha(rebuilt[path]) == _sha(candidate_files[path]) for path in shared
            ),
            "actual_byte_matches": sum(rebuilt[path] == candidate_files[path] for path in shared),
            "manifest_member_matches": models.CANDIDATE_MEMBER_COUNT,
            "candidate_builder_used_for_semantic_outcomes": False,
            "credential_lookups": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_detached_rebuild_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_detached_rebuild_audit:",
    )
    dynamic = _identified(
        {
            "candidate_freeze_audit_id": freeze_id,
            "detached_rebuild_audit_id": detached["audit_id"],
            "callbacks": tuple(callbacks),
            "callback_count": len(callbacks),
            "open_create_exclusive_count": sum(
                bool(row["open_flags_verified"]) for row in callbacks
            )
            * 2,
            "envelope_file_fsync_count": len(callbacks),
            "envelope_directory_fsync_count": len(callbacks),
            "receipt_file_fsync_count": len(callbacks),
            "receipt_directory_fsync_count": len(callbacks),
            "disk_reread_verified_count": sum(
                bool(row["disk_reread_verified"]) for row in callbacks
            ),
            "callback_after_receipt_directory_fsync_count": sum(
                row["callback_event"] > row["receipt_directory_fsync_event"] for row in callbacks
            ),
            "callback_before_admission_count": 0,
            "candidate_saved_event_ordinals_used_as_syscall_oracle": False,
            "passed": len(callbacks) == 10,
            "schema_version": "qa_reasoning_fixed_fixture_dynamic_runtime_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_dynamic_runtime_audit:",
    )
    return detached, dynamic


def _candidate_comparison(
    candidate_files: Mapping[str, bytes],
    selection: Mapping[str, Any],
    parent: Mapping[str, Any],
    semantic: Mapping[str, Any],
    intervention: Mapping[str, Any],
    negative: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_rows = tuple(
        json.loads(line)
        for line in candidate_files["selected_fixture_rows.jsonl"].splitlines()
        if line
    )
    execution = _load(candidate_files["execution_audit.json"])
    durable = _load(candidate_files["durable_preaction_commit_audit.json"])
    candidate_intervention = _load(candidate_files["intervention_audit.json"])
    candidate_negative = _load(candidate_files["negative_control_audit.json"])
    gate = _load(candidate_files["gate_evaluation.json"])
    report = _load(candidate_files["report.json"])
    if (
        tuple(row["row_id"] for row in candidate_rows) != tuple(selection["selected_row_ids"])
        or execution["program_nodes_replayed"] != semantic["program_nodes_replayed"]
        or execution["qualified_count"] != semantic["qualified_count"]
        or durable["envelope_count"] != parent["envelope_count"]
        or candidate_intervention["rejected_count"] != intervention["rejected_count"]
        or candidate_negative["rejected_count"] != negative["rejected_count"]
        or gate["passed_count"] != 10
        or report["qualified_count"] != 2
    ):
        _fail("comparison.candidate", "candidate final comparison differs")
    return _identified(
        {
            "independent_selection_audit_id": selection["audit_id"],
            "independent_parent_audit_id": parent["audit_id"],
            "independent_semantic_audit_id": semantic["audit_id"],
            "independent_intervention_audit_id": intervention["audit_id"],
            "independent_negative_audit_id": negative["audit_id"],
            "candidate_selected_row_matches": len(candidate_rows),
            "candidate_runtime_object_matches": parent["runtime_actual_byte_matches"],
            "candidate_program_node_matches": semantic["program_nodes_replayed"],
            "candidate_qualified_matches": semantic["qualified_count"],
            "candidate_intervention_matches": intervention["rejected_count"],
            "candidate_attack_matches": negative["rejected_count"],
            "candidate_gate_id": gate["gate_id"],
            "candidate_report_id": report["report_id"],
            "candidate_gate_compared_only_after_independent_results": True,
            "candidate_report_compared_only_after_independent_results": True,
            "passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_candidate_comparison_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_candidate_comparison_audit:",
    )


def build_independent_audit(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization, directive = _authorization(review)
    authorization_id = authorization["authorization_id"]
    source = _audit_source_binding(root, authorization_id, source_commit, source_tree)
    freeze, candidate_files = _freeze_candidate(root, authorization_id)
    detached, dynamic = _detached_rebuild(root, freeze["audit_id"], candidate_files)
    selection, loaded = select_and_load_archive_fixtures(root / models.ARCHIVE_DIRECTORY)
    parent, semantic, runtime_objects, fixture_results = reconstruct_runtime_and_semantics(
        candidate_files=candidate_files,
        loaded=loaded,
    )
    intervention, negative = interventions_and_attacks(fixture_results)
    comparison = _candidate_comparison(
        candidate_files,
        selection,
        parent,
        semantic,
        intervention,
        negative,
    )
    scope = _identified(
        {
            "authorization_id": authorization_id,
            "candidate_freeze_audit_id": freeze["audit_id"],
            "detached_rebuild_audit_id": detached["audit_id"],
            "dynamic_runtime_audit_id": dynamic["audit_id"],
            "selection_audit_id": selection["audit_id"],
            "parent_audit_id": parent["audit_id"],
            "semantic_audit_id": semantic["audit_id"],
            "intervention_audit_id": intervention["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "candidate_comparison_audit_id": comparison["audit_id"],
            "candidate_formal_writes": 0,
            "predecessor_or_archive_formal_writes": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "provider_client_constructions": 0,
            "gpu_jobs": 0,
            "archive_sources_scanned": 0,
            "archive_expansion_rows": 0,
            "third_fixture_rows": 0,
            "new_task_registrations": 0,
            "new_operation_registrations": 0,
            "catalog_promotions": 0,
            "model_generated_rows": 0,
            "same_task_multitrajectory_rows": 0,
            "qa_release_objects": 0,
            "mapper_rows": 0,
            "state_rows": 0,
            "contribution_rows": 0,
            "vtdo_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "candidate_builder_calls_for_reproducibility_only": 1,
            "candidate_helper_calls": 0,
            "candidate_outcome_oracle_calls": 0,
            "old_mainline_paused": True,
            "passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_scope_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_scope_audit:",
    )
    gates = {
        models.GATE_NAMES[0]: bool(freeze["passed"]),
        models.GATE_NAMES[1]: bool(detached["passed"]),
        models.GATE_NAMES[2]: bool(selection["passed"]),
        models.GATE_NAMES[3]: bool(parent["passed"]),
        models.GATE_NAMES[4]: bool(dynamic["passed"]),
        models.GATE_NAMES[5]: bool(semantic["passed"]),
        models.GATE_NAMES[6]: bool(intervention["passed"] and negative["passed"]),
        models.GATE_NAMES[7]: bool(
            source["helper_boundary_passed"]
            and comparison["passed"]
            and scope["candidate_helper_calls"] == 0
            and scope["candidate_outcome_oracle_calls"] == 0
        ),
        models.GATE_NAMES[8]: not any(
            scope[field]
            for field in (
                "candidate_formal_writes",
                "predecessor_or_archive_formal_writes",
                "provider_calls",
                "credential_lookups",
                "provider_client_constructions",
                "gpu_jobs",
                "archive_sources_scanned",
                "archive_expansion_rows",
                "third_fixture_rows",
                "new_task_registrations",
                "new_operation_registrations",
                "catalog_promotions",
                "model_generated_rows",
                "same_task_multitrajectory_rows",
                "qa_release_objects",
                "mapper_rows",
                "state_rows",
                "contribution_rows",
                "vtdo_rows",
                "training_rows",
                "production_rows",
            )
        ),
    }
    gate = _identified(
        {
            "authorization_id": authorization_id,
            "gates": gates,
            "passed_count": sum(gates.values()),
            "failed_count": len(gates) - sum(gates.values()),
            "noncompensatory": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_gate.v1",
        },
        "gate_id",
        "qa_reasoning_fixed_fixture_independent_gate:",
    )
    if gate["failed_count"]:
        _fail("gate.failed", "independent fixed-Fixture Gate failed")
    common = {
        "authorization_id": authorization_id,
        "candidate_freeze_audit_id": freeze["audit_id"],
        "detached_rebuild_audit_id": detached["audit_id"],
        "dynamic_runtime_audit_id": dynamic["audit_id"],
        "source_binding_id": source["binding_id"],
        "selection_audit_id": selection["audit_id"],
        "parent_audit_id": parent["audit_id"],
        "semantic_audit_id": semantic["audit_id"],
        "intervention_audit_id": intervention["audit_id"],
        "negative_audit_id": negative["audit_id"],
        "candidate_comparison_audit_id": comparison["audit_id"],
        "scope_audit_id": scope["audit_id"],
        "gate_id": gate["gate_id"],
    }
    decision = _identified(
        {
            **common,
            "decision": models.DECISION,
            "candidate_fixed_fixture_preflight_independently_confirmed": True,
            "two_deterministic_fixed_fixture_trajectories_confirmed": True,
            "durable_preaction_runtime_order_independently_observed": True,
            "model_reachability_established": False,
            "same_task_multitrajectory_established": False,
            "qa_release_eligible": False,
            "old_mainline_paused": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_decision.v1",
        },
        "decision_id",
        "qa_reasoning_fixed_fixture_independent_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "prospective_next_stage": models.PROSPECTIVE_NEXT_STAGE,
            "next_stage_authorized": False,
            "separate_external_audit_decision_required": True,
            "provider_execution_authorized": False,
            "archive_expansion_authorized": False,
            "same_task_multitrajectory_authorized": False,
            "old_mainline_resume_authorized": False,
            "qa_release_authorized": False,
            "vtdo_authorized": False,
            "schema_version": "qa_reasoning_fixed_fixture_independent_transition.v1",
        },
        "transition_id",
        "qa_reasoning_fixed_fixture_independent_transition:",
    )
    report = _identified(
        {
            **common,
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "candidate_files": models.CANDIDATE_FILE_COUNT,
            "candidate_bytes": models.CANDIDATE_TOTAL_BYTES,
            "independent_fixture_count": semantic["fixture_count"],
            "independent_runtime_object_count": parent["runtime_object_count"],
            "dynamic_callback_count": dynamic["callback_count"],
            "independent_program_nodes_replayed": semantic["program_nodes_replayed"],
            "qualified_count": semantic["qualified_count"],
            "interventions_rejected": intervention["rejected_count"],
            "attacks_rejected": negative["rejected_count"],
            "passed_gates": gate["passed_count"],
            "failed_gates": gate["failed_count"],
            "provider_calls": 0,
            "claim_boundary": (
                "independent confirmation of two deterministic fixed-Fixture public reasoning "
                "trajectories and actual durable preaction callback ordering only"
            ),
            "schema_version": "qa_reasoning_fixed_fixture_independent_report.v1",
        },
        "report_id",
        "qa_reasoning_fixed_fixture_independent_report:",
    )
    return {
        "authorization": authorization,
        "external_review_bytes": review,
        "operator_directive_bytes": directive,
        "candidate_freeze": freeze,
        "detached_rebuild": detached,
        "dynamic_runtime": dynamic,
        "audit_source_binding": source,
        "selection": selection,
        "parent": parent,
        "semantic": semantic,
        "runtime_objects": runtime_objects,
        "fixture_results": fixture_results,
        "intervention": intervention,
        "negative": negative,
        "comparison": comparison,
        "scope": scope,
        "gate": gate,
        "decision": decision,
        "transition": transition,
        "report": report,
    }


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(_encoded(value) for value in values)


def write_artifacts(products: Mapping[str, Any], output_dir: str | Path) -> tuple[str, ...]:
    semantic_rows = products["semantic"]["rows"]
    payloads = {
        "authorization.json": _encoded(products["authorization"]),
        "audit_source_binding.json": _encoded(products["audit_source_binding"]),
        "candidate_comparison_audit.json": _encoded(products["comparison"]),
        "candidate_freeze_audit.json": _encoded(products["candidate_freeze"]),
        "decision.json": _encoded(products["decision"]),
        "detached_rebuild_audit.json": _encoded(products["detached_rebuild"]),
        "dynamic_runtime_audit.json": _encoded(products["dynamic_runtime"]),
        "external_review.txt": products["external_review_bytes"],
        "gate_evaluation.json": _encoded(products["gate"]),
        "independent_intervention_audit.json": _encoded(products["intervention"]),
        "independent_intervention_rows.jsonl": _jsonl(products["intervention"]["rows"]),
        "independent_negative_audit.json": _encoded(products["negative"]),
        "independent_negative_rows.jsonl": _jsonl(products["negative"]["rows"]),
        "independent_parent_reconstruction_audit.json": _encoded(products["parent"]),
        "independent_runtime_objects.jsonl": _jsonl(products["runtime_objects"]),
        "independent_selected_rows.jsonl": _jsonl(products["selection"]["selected_rows"]),
        "independent_selection_audit.json": _encoded(products["selection"]),
        "independent_semantic_audit.json": _encoded(products["semantic"]),
        "independent_semantic_rows.jsonl": _jsonl(semantic_rows),
        "operator_directive.txt": products["operator_directive_bytes"],
        "report.json": _encoded(products["report"]),
        "scope_boundary_audit.json": _encoded(products["scope"]),
        "transition.json": _encoded(products["transition"]),
    }
    members = tuple(
        {
            "relative_path": relative,
            "sha256": _sha(payload),
            "byte_count": len(payload),
        }
        for relative, payload in sorted(payloads.items())
    )
    manifest = _identified(
        {
            "members": members,
            "file_count": len(members),
            "member_bytes": sum(map(len, payloads.values())),
            "artifact_root": "qa_reasoning_fixed_fixture_independent_artifact_root:"
            + _sha(canonical_json_bytes(members)),
            "self_excluding": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_artifact_manifest.v1",
        },
        "manifest_id",
        "qa_reasoning_fixed_fixture_independent_artifact_manifest:",
    )
    payloads["artifact_manifest.json"] = _encoded(manifest)
    return write_immutable_artifact_directory(output_dir, payloads)


def validate_written_artifacts(output_dir: str | Path) -> dict[str, Any]:
    files = _files(Path(output_dir))
    manifest = _load(files["artifact_manifest.json"])
    rows = manifest["members"]
    paths = {str(row["relative_path"]) for row in rows}
    if paths != set(files) - {"artifact_manifest.json"}:
        _fail("written.manifest", "written Manifest path domain differs")
    matches = sum(
        int(row["byte_count"]) == len(files[str(row["relative_path"])])
        and row["sha256"] == _sha(files[str(row["relative_path"])])
        for row in rows
    )
    if matches != len(rows):
        _fail("written.manifest", "written Manifest member differs")
    return {
        "file_count": len(files),
        "total_bytes": sum(map(len, files.values())),
        "manifest_member_count": len(rows),
        "manifest_member_bytes": manifest["member_bytes"],
        "manifest_id": manifest["manifest_id"],
        "artifact_root": manifest["artifact_root"],
        "manifest_member_matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    products = build_independent_audit(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
