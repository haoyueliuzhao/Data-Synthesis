from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from . import models

CANDIDATE_MODULE = "trusted_synthesis.experiments.qa_reasoning_contract_freeze.preflight"


class IndependentAuditError(ValueError):
    """An independently evaluated reasoning-contract boundary failed."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise IndependentAuditError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _identity(values: Mapping[str, Any], field: str, prefix: str) -> str:
    return strict_canonical_hash(
        {key: value for key, value in values.items() if key != field}, prefix=prefix
    )


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = _identity(result, field, prefix)
    return result


def _require_identity(value: Mapping[str, Any], field: str, prefix: str, stage: str) -> None:
    if value.get(field) != _identity(value, field, prefix):
        _fail(stage, f"content identity differs: {field}")


def _load(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("json.object", "expected a JSON object")
    return value


def _jsonl(payload: bytes) -> tuple[dict[str, Any], ...]:
    rows = tuple(_load(line) for line in payload.splitlines() if line)
    if not rows:
        _fail("jsonl.empty", "expected at least one JSONL row")
    return rows


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


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _authorization(review: bytes) -> tuple[dict[str, Any], bytes]:
    if len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT or _sha(review) != (
        models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.external_review", "external independent review bytes differ")
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
                "independent_rebuild_authorized": True,
                "candidate_formal_rewrite_authorized": False,
                "fixed_fixture_execution_authorized": False,
                "archive_read_or_expansion_authorized": False,
                "task_or_operation_registration_authorized": False,
                "provider_execution_authorized": False,
                "gpu_execution_authorized": False,
                "online_generation_authorized": False,
                "qa_release_authorized": False,
                "vtdo_authorized": False,
                "schema_version": "finance_qa_reasoning_contract_independent_authorization.v1",
            },
            "authorization_id",
            "finance_qa_reasoning_contract_independent_authorization:",
        ),
        directive,
    )


def _validate_manifest(
    files: Mapping[str, bytes],
    *,
    expected_file_count: int,
    expected_total_bytes: int,
    expected_member_count: int,
    expected_member_bytes: int,
    expected_manifest_bytes: int,
    expected_manifest_sha256: str,
    expected_manifest_id: str,
    expected_root_id: str,
    stage: str,
) -> dict[str, Any]:
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        len(files) != expected_file_count
        or sum(map(len, files.values())) != expected_total_bytes
        or len(manifest_payload) != expected_manifest_bytes
        or _sha(manifest_payload) != expected_manifest_sha256
    ):
        _fail(stage, "formal directory geometry or Manifest bytes differ")
    manifest = _load(manifest_payload)
    rows = manifest.get("members")
    if not isinstance(rows, list):
        _fail(stage, "Manifest members are absent")
    members = {str(row["relative_path"]): row for row in rows}
    if (
        len(members) != expected_member_count
        or int(manifest.get("member_bytes", -1)) != expected_member_bytes
        or set(members) != set(files) - {"artifact_manifest.json"}
        or manifest.get("manifest_id") != expected_manifest_id
        or manifest.get("artifact_root") != expected_root_id
        or manifest.get("self_excluding") is not True
    ):
        _fail(stage, "self-excluding Manifest domain differs")
    for relative_path, row in members.items():
        payload = files[relative_path]
        if int(row["byte_count"]) != len(payload) or row["sha256"] != _sha(payload):
            _fail(stage, f"Manifest member differs: {relative_path}")
    return manifest


def _validate_predecessor(root: Path) -> dict[str, Any]:
    directory = root / models.PREDECESSOR_DIRECTORY
    files = _files(directory)
    manifest = _load(files.get("artifact_manifest.json", b"{}"))
    gate = _load(files.get("gate_evaluation.json", b"{}"))
    decision = _load(files.get("decision.json", b"{}"))
    if (
        manifest.get("manifest_id") != models.PREDECESSOR_MANIFEST_ID
        or manifest.get("artifact_root") != models.PREDECESSOR_ROOT_ID
        or gate.get("gate_id") != models.PREDECESSOR_GATE_ID
        or decision.get("decision_id") != models.PREDECESSOR_DECISION_ID
        or gate.get("passed_count") != 7
        or gate.get("failed_count") != 1
        or decision.get("first_blocker") != "authoritative_gross_margin_target_evidence_absent"
    ):
        _fail("freeze.predecessor", "Archive-grounded negative predecessor differs")
    return {
        "directory": models.PREDECESSOR_DIRECTORY,
        "file_count": len(files),
        "total_bytes": sum(map(len, files.values())),
        "manifest_id": manifest["manifest_id"],
        "artifact_root": manifest["artifact_root"],
        "gate_id": gate["gate_id"],
        "decision_id": decision["decision_id"],
        "passed_gates": gate["passed_count"],
        "failed_gates": gate["failed_count"],
        "accepted_as_immutable_negative_result": True,
    }


def _candidate_source_authority(root: Path, source: Mapping[str, Any]) -> dict[str, Any]:
    commit = _git_text(
        root, "freeze.candidate_source", "rev-parse", f"{models.CANDIDATE_SOURCE_COMMIT}^{{commit}}"
    )
    tree = _git_text(root, "freeze.candidate_source", "rev-parse", f"{commit}^{{tree}}")
    if commit != models.CANDIDATE_SOURCE_COMMIT or tree != models.CANDIDATE_SOURCE_TREE:
        _fail("freeze.candidate_source", "candidate source commit/tree relation differs")
    recorded = source.get("members")
    if (
        not isinstance(recorded, list)
        or tuple(str(row.get("relative_path")) for row in recorded) != models.CANDIDATE_SOURCE_PATHS
    ):
        _fail("freeze.candidate_source", "candidate source member domain differs")
    for row in recorded:
        path = str(row["relative_path"])
        committed = _git(root, "freeze.candidate_source", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        blob = _git_text(root, "freeze.candidate_source", "rev-parse", f"{commit}:{path}")
        if (
            committed != current
            or blob != _git_blob_oid(committed)
            or row.get("git_blob_oid") != blob
            or row.get("sha256") != _sha(committed)
            or int(row.get("byte_count", -1)) != len(committed)
        ):
            _fail("freeze.candidate_source", f"candidate source bytes differ: {path}")
    if (
        source.get("binding_id") != models.CANDIDATE_SOURCE_BINDING_ID
        or source.get("resolved_commit") != commit
        or source.get("resolved_tree") != tree
        or source.get("all_current_bytes_equal_committed_bytes") is not True
    ):
        _fail("freeze.candidate_source", "candidate source Binding differs")
    return {
        "commit": commit,
        "tree": tree,
        "member_count": len(recorded),
        "committed_current_byte_matches": len(recorded),
        "declared_transitive_runtime_closure": False,
    }


def _freeze_candidate(root: Path, authorization_id: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    directory = root / models.CANDIDATE_DIRECTORY
    files = _files(directory)
    manifest = _validate_manifest(
        files,
        expected_file_count=models.CANDIDATE_FILE_COUNT,
        expected_total_bytes=models.CANDIDATE_TOTAL_BYTES,
        expected_member_count=models.CANDIDATE_MEMBER_COUNT,
        expected_member_bytes=models.CANDIDATE_MEMBER_BYTES,
        expected_manifest_bytes=models.CANDIDATE_MANIFEST_BYTE_COUNT,
        expected_manifest_sha256=models.CANDIDATE_MANIFEST_SHA256,
        expected_manifest_id=models.CANDIDATE_MANIFEST_ID,
        expected_root_id=models.CANDIDATE_ARTIFACT_ROOT,
        stage="freeze.candidate_manifest",
    )
    authorization = _load(files["authorization.json"])
    predecessor_freeze = _load(files["predecessor_freeze.json"])
    clarification = _load(files["scope_clarification.json"])
    source = _load(files["source_binding.json"])
    conformance = _load(files["conformance_audit.json"])
    negative = _load(files["negative_control_audit.json"])
    gate = _load(files["gate_evaluation.json"])
    decision = _load(files["decision.json"])
    transition = _load(files["transition.json"])
    report = _load(files["report.json"])
    identities = (
        (authorization.get("authorization_id"), models.CANDIDATE_AUTHORIZATION_ID),
        (predecessor_freeze.get("freeze_id"), models.CANDIDATE_PREDECESSOR_FREEZE_ID),
        (clarification.get("clarification_id"), models.CANDIDATE_SCOPE_CLARIFICATION_ID),
        (source.get("binding_id"), models.CANDIDATE_SOURCE_BINDING_ID),
        (conformance.get("audit_id"), models.CANDIDATE_CONFORMANCE_AUDIT_ID),
        (negative.get("audit_id"), models.CANDIDATE_NEGATIVE_AUDIT_ID),
        (
            _load(files["scope_boundary_audit.json"]).get("audit_id"),
            models.CANDIDATE_SCOPE_AUDIT_ID,
        ),
        (gate.get("gate_id"), models.CANDIDATE_GATE_ID),
        (decision.get("decision_id"), models.CANDIDATE_DECISION_ID),
        (transition.get("transition_id"), models.CANDIDATE_TRANSITION_ID),
        (report.get("report_id"), models.CANDIDATE_REPORT_ID),
    )
    if any(actual != expected for actual, expected in identities):
        _fail("freeze.candidate_identity", "candidate principal identity differs")
    expected_clarifications = {
        (
            "target_evidence_absence",
            "absent_from_current_admitted_frozen_finqa_table_cell_adapter_domain",
        ),
        ("g6_coverage", "coverage_among_nine_admitted_branch_cases_only"),
        (
            "semantic_operation_depth",
            "deterministic_answer_program_semantic_dependency_depth",
        ),
    }
    actual_clarifications = {
        (str(row["subject"]), str(row["narrow_meaning"]))
        for row in clarification.get("clarifications", ())
    }
    if (
        actual_clarifications != expected_clarifications
        or clarification.get("predecessor_formal_bytes_modified") is not False
        or conformance.get("scientific_object_count") != 13
        or conformance.get("contract_names") != list(models.CONTRACT_NAMES)
        or negative.get("attempted_count") != 10
        or negative.get("rejected_count") != 10
        or negative.get("accepted_count") != 0
        or gate.get("passed_count") != 8
        or gate.get("failed_count") != 0
        or transition.get("next_stage") != models.STAGE
        or transition.get("next_stage_authorized") is not True
    ):
        _fail("freeze.candidate_semantics", "candidate scoped decision differs")
    predecessor = _validate_predecessor(root)
    source_facts = _candidate_source_authority(root, source)
    return (
        _identified(
            {
                "authorization_id": authorization_id,
                "directory": models.CANDIDATE_DIRECTORY,
                "source_commit": models.CANDIDATE_SOURCE_COMMIT,
                "source_tree": models.CANDIDATE_SOURCE_TREE,
                "file_count": len(files),
                "total_bytes": sum(map(len, files.values())),
                "manifest_member_count": len(manifest["members"]),
                "manifest_member_bytes": manifest["member_bytes"],
                "manifest_sha256": _sha(files["artifact_manifest.json"]),
                "manifest_id": manifest["manifest_id"],
                "artifact_root": manifest["artifact_root"],
                "candidate_source": source_facts,
                "predecessor": predecessor,
                "candidate_gate_id": models.CANDIDATE_GATE_ID,
                "candidate_report_id": models.CANDIDATE_REPORT_ID,
                "candidate_gate_used_as_oracle": False,
                "candidate_report_used_as_oracle": False,
                "candidate_conformance_audit_used_as_input": False,
                "candidate_negative_audit_used_as_attack_oracle": False,
                "candidate_formal_writes": 0,
                "passed": True,
                "schema_version": "finance_qa_reasoning_contract_candidate_freeze_audit.v1",
            },
            "audit_id",
            "finance_qa_reasoning_contract_candidate_freeze_audit:",
        ),
        files,
    )


def _detached_rebuild(root: Path, freeze_id: str, saved: Mapping[str, bytes]) -> dict[str, Any]:
    archive = _git(
        root,
        "detached.archive",
        "archive",
        "--format=tar",
        models.CANDIDATE_SOURCE_COMMIT,
        "trusted_data_synthesis/src",
    )
    with TemporaryDirectory(prefix="qa-reasoning-contract-independent-") as temporary:
        temp_root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            all_members = bundle.getmembers()
            regular = tuple(member for member in all_members if member.isfile())
            if any(
                member.name.startswith("/") or ".." in Path(member.name).parts
                for member in all_members
            ):
                _fail("detached.archive", "detached source archive contains unsafe path")
            bundle.extractall(temp_root, filter="data")
        if len(regular) != 741:
            _fail("detached.archive_geometry", "detached source archive geometry differs")
        output = temp_root / "rebuilt"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(temp_root / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        command = (
            sys.executable,
            "-m",
            CANDIDATE_MODULE,
            "--repo-root",
            str(root),
            "--external-audit",
            str(root / models.CANDIDATE_DIRECTORY / "external_review.txt"),
            "--output-dir",
            str(output),
            "--source-commit",
            models.CANDIDATE_SOURCE_COMMIT,
            "--source-tree",
            models.CANDIDATE_SOURCE_TREE,
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
        path_matches = len(set(rebuilt) & set(saved))
        sha_matches = sum(
            _sha(rebuilt[path]) == _sha(saved[path]) for path in set(rebuilt) & set(saved)
        )
        byte_matches = sum(rebuilt[path] == saved[path] for path in set(rebuilt) & set(saved))
        if rebuilt != saved:
            _fail("detached.actual_bytes", "detached candidate rebuild bytes differ")
    return _identified(
        {
            "candidate_freeze_audit_id": freeze_id,
            "archived_source_file_count": len(regular),
            "subprocess_environment_keys": tuple(sorted(environment)),
            "credential_like_environment_keys": 0,
            "saved_file_count": len(saved),
            "rebuilt_file_count": len(rebuilt),
            "saved_bytes": sum(map(len, saved.values())),
            "rebuilt_bytes": sum(map(len, rebuilt.values())),
            "path_matches": path_matches,
            "sha256_matches": sha_matches,
            "actual_byte_matches": byte_matches,
            "candidate_builder_used_for_semantic_outcomes": False,
            "credential_lookups": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "finance_qa_reasoning_contract_detached_rebuild_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_detached_rebuild_audit:",
    )


def _audit_source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    commit = _git_text(root, "audit_source.commit", "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git_text(root, "audit_source.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != source_commit or tree != source_tree:
        _fail("audit_source.commit_tree", "audit source commit/tree relation differs")
    rows = []
    audit_tree: ast.Module | None = None
    for path in models.AUDIT_SOURCE_PATHS:
        committed = _git(root, "audit_source.member", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        blob = _git_text(root, "audit_source.member", "rev-parse", f"{commit}:{path}")
        if committed != current or blob != _git_blob_oid(committed):
            _fail("audit_source.member", f"audit source member differs: {path}")
        if path.endswith("/audit.py"):
            audit_tree = ast.parse(committed)
        rows.append(
            {
                "relative_path": path,
                "git_blob_oid": blob,
                "sha256": _sha(committed),
                "byte_count": len(committed),
                "committed_current_bytes_equal": True,
            }
        )
    if audit_tree is None:
        _fail("audit_source.helper_boundary", "audit implementation AST is absent")
    forbidden_imports = []
    forbidden_calls = []
    helper_names = {
        "build_contract_descriptors",
        "build_target_contract",
        "build_coverage_matrix",
        "build_conformance_objects",
        "admit_reasoning_action",
        "admit_observation_update",
        "admit_reasoning_trajectory",
        "admit_qualification",
        "admit_target_evidence",
        "quotient_signature",
        "require_distinct_quotient_states",
        "_negative_controls",
    }
    for node in ast.walk(audit_tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (
                "qa_reasoning_contract_freeze" in node.module
                and "independent_audit" not in node.module
            )
        ):
            forbidden_imports.append(node.module)
        if isinstance(node, ast.Import):
            forbidden_imports.extend(
                alias.name
                for alias in node.names
                if "qa_reasoning_contract_freeze" in alias.name
                and "independent_audit" not in alias.name
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
            "candidate_helper_imports": 0,
            "candidate_helper_calls": 0,
            "helper_boundary_passed": True,
            "schema_version": "finance_qa_reasoning_contract_independent_source_binding.v1",
        },
        "binding_id",
        "finance_qa_reasoning_contract_independent_source_binding:",
    )
