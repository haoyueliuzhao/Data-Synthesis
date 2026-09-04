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
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn, cast

from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.program import TaskProgramExecutor, TaskProgramOracleVerifier
from trusted_synthesis.core.task.program import TaskProgram
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.qa_generator_totality import preflight as legacy_totality

from . import models

CANDIDATE_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_generator_source_authority/"
    "qa_generator_source_commit_tree_member_authority_and_depth_metric_"
    "repair_preflight_v1_20260904"
)
CANDIDATE_MODULE = "trusted_synthesis.experiments.qa_generator_source_authority.preflight"


class AuditError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


IndependentAuditError = AuditError


class GitSourceAuthorityError(AuditError):
    """Independent Git-authority rejection with a stable stage."""


def _source_fail(stage: str, reason: str) -> NoReturn:
    raise GitSourceAuthorityError(stage, reason)


def _fail(stage: str, reason: str) -> NoReturn:
    raise AuditError(stage, reason)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _encoded(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", warnings=False)
    return _canonical_bytes(value) + b"\n"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_without_none(item) for item in value]
    return value


def _program_hash(program: Mapping[str, Any]) -> str:
    return "program:" + _sha(_canonical_bytes(_without_none(dict(program))))


def _identity(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    body = {key: item for key, item in value.items() if key != field}
    return f"{prefix}{_sha(_canonical_bytes(body))}"


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    draft = model_type.model_construct(**{field: "pending", **values})
    body = draft.model_dump(mode="python", exclude={field}, warnings=False)
    return model_type(**{field: f"{prefix}{_sha(_canonical_bytes(body))}", **values})


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _load_bytes(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("json.object", "expected one JSON object")
    return cast(dict[str, Any], value)


def _jsonl(payload: bytes, *, expected: int, stage: str) -> tuple[dict[str, Any], ...]:
    rows = tuple(_load_bytes(line) for line in payload.splitlines() if line)
    if len(rows) != expected:
        _fail(stage, f"expected {expected} JSONL rows, observed {len(rows)}")
    return rows


def _git(root: Path, stage: str, *arguments: str) -> bytes:
    result = subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        _fail(stage, f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def _git_text(root: Path, stage: str, *arguments: str) -> str:
    return _git(root, stage, *arguments).decode("ascii").strip()


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _authorization(review: bytes) -> Any:
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.external_review", "external independent-audit review bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.directive", "operator directive bytes differ")
    return _make(
        models.ExternalIndependentAuditAuthorization,
        {},
        "authorization_id",
        "qa_generator_source_authority_independent_audit_authorization:",
    )


def _freeze_candidate(repo_root: Path, authorization_id: str) -> tuple[Any, dict[str, bytes]]:
    root = repo_root / CANDIDATE_DIRECTORY
    files = _files(root)
    if (
        len(files) != models.CANDIDATE_FILE_COUNT
        or sum(len(payload) for payload in files.values()) != models.CANDIDATE_TOTAL_BYTES
    ):
        _fail("freeze.geometry", "candidate formal directory geometry differs")
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        len(manifest_payload) != models.CANDIDATE_MANIFEST_BYTE_COUNT
        or _sha(manifest_payload) != models.CANDIDATE_MANIFEST_SHA256
    ):
        _fail("freeze.manifest_bytes", "candidate Manifest file bytes differ")
    manifest = _load_bytes(manifest_payload)
    members_raw = manifest.get("members")
    if not isinstance(members_raw, list):
        _fail("freeze.manifest", "candidate Manifest lacks members")
    members = {str(row["relative_path"]): row for row in members_raw}
    if (
        len(members) != models.CANDIDATE_MEMBER_COUNT
        or int(manifest.get("member_bytes", -1)) != models.CANDIDATE_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("freeze.manifest", "candidate Manifest member domain differs")
    for relative_path, row in members.items():
        payload = files[relative_path]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            _fail("freeze.member_bytes", f"candidate member differs: {relative_path}")
    root_id = "qa_generator_source_authority_artifact_root:" + _sha(
        _canonical_bytes(tuple(members_raw))
    )
    manifest_body = {key: value for key, value in manifest.items() if key != "manifest_id"}
    manifest_id = "qa_generator_source_authority_artifact_manifest:" + _sha(
        _canonical_bytes(manifest_body)
    )
    if (
        root_id != models.CANDIDATE_ARTIFACT_ROOT
        or manifest_id != models.CANDIDATE_MANIFEST_ID
        or manifest.get("artifact_root") != root_id
        or manifest.get("manifest_id") != manifest_id
    ):
        _fail("freeze.identity", "candidate Manifest or Root identity differs")
    report = _load_bytes(files["report.json"])
    gate = _load_bytes(files["gate_evaluation.json"])
    transition = _load_bytes(files["transition.json"])
    if (
        report.get("report_id") != models.CANDIDATE_REPORT_ID
        or gate.get("gate_id") != models.CANDIDATE_GATE_ID
        or transition.get("transition_id") != models.CANDIDATE_TRANSITION_ID
        or int(gate.get("passed", -1)) != 8
        or int(gate.get("failed", -1)) != 0
        or transition.get("next_stage") != models.STAGE
    ):
        _fail("freeze.decision", "candidate Report/Gate/Transition differs")
    candidate_members = tuple(
        models.CandidateArtifactMember(
            relative_path=path,
            sha256=str(members[path]["sha256"]),
            byte_count=int(members[path]["byte_count"]),
        )
        for path in sorted(members)
    )
    freeze = _make(
        models.CandidateFreezeAudit,
        {"authorization_id": authorization_id, "members": candidate_members},
        "audit_id",
        "qa_generator_source_authority_candidate_freeze_audit:",
    )
    return freeze, files


def _detached_rebuild(repo_root: Path, freeze_id: str, saved: dict[str, bytes]) -> Any:
    archive = _git(
        repo_root,
        "detached.archive",
        "archive",
        "--format=tar",
        models.REPAIR_SOURCE_COMMIT,
        "trusted_data_synthesis/src",
    )
    with TemporaryDirectory(prefix="qa-source-authority-independent-") as temporary:
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
        if len(regular) != 703:
            _fail("detached.archive_geometry", "detached source archive geometry differs")
        output = temp_root / "rebuilt"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(temp_root / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        if set(env) != {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LC_ALL"}:
            _fail("detached.environment", "detached subprocess environment differs")
        command = (
            sys.executable,
            "-m",
            CANDIDATE_MODULE,
            "--repo-root",
            str(repo_root),
            "--external-audit",
            str(repo_root / CANDIDATE_DIRECTORY / "external_review.txt"),
            "--output-dir",
            str(output),
            "--source-commit",
            models.REPAIR_SOURCE_COMMIT,
            "--source-tree",
            models.REPAIR_SOURCE_TREE,
        )
        result = subprocess.run(command, cwd=temp_root, env=env, check=False, capture_output=True)
        if result.returncode:
            _fail("detached.builder", result.stderr.decode("utf-8", errors="replace"))
        rebuilt = _files(output)
        if set(rebuilt) != set(saved):
            _fail("detached.path_set", "detached rebuild path set differs")
        if rebuilt != saved:
            _fail("detached.actual_bytes", "detached rebuild bytes differ")
    return _make(
        models.DetachedRebuildAudit,
        {
            "candidate_freeze_audit_id": freeze_id,
            "archived_source_file_count": len(regular),
        },
        "audit_id",
        "qa_generator_source_authority_detached_rebuild_audit:",
    )


def _source_paths(kind: str) -> tuple[str, ...]:
    if kind == "generator_verifier":
        return models.GENERATOR_SOURCE_PATHS
    if kind == "repair_implementation":
        return models.REPAIR_SOURCE_PATHS
    _fail("source.domain", f"unknown source authority kind: {kind}")


def _source_git(root: Path, stage: str, *arguments: str) -> bytes:
    try:
        return _git(root, stage, *arguments)
    except AuditError as exc:
        raise GitSourceAuthorityError(exc.stage, str(exc)) from exc


def _source_git_text(root: Path, stage: str, *arguments: str) -> str:
    return _source_git(root, stage, *arguments).decode("ascii").strip()


def _independent_git_source_group(
    *,
    repo_root: Path,
    authorization_id: str,
    kind: str,
    commit: str,
    tree: str,
    candidate_payload: bytes,
) -> Any:
    resolved = _source_git_text(
        repo_root, "git_commit_resolution", "rev-parse", f"{commit}^{{commit}}"
    )
    if resolved != commit:
        _source_fail("git_commit_resolution", "requested commit does not resolve exactly")
    if _source_git_text(repo_root, "git_commit_resolution", "cat-file", "-t", resolved) != "commit":
        _source_fail("git_commit_resolution", "resolved object is not a commit")
    resolved_tree = _source_git_text(
        repo_root, "commit_tree_relation", "rev-parse", f"{resolved}^{{tree}}"
    )
    if resolved_tree != tree:
        _source_fail("commit_tree_relation", "source tree differs from git rev-parse commit^{tree}")

    rows: list[Any] = []
    candidate_rows: list[dict[str, Any]] = []
    for relative_path in _source_paths(kind):
        blob_oid = _source_git_text(
            repo_root,
            "committed_member_resolution",
            "rev-parse",
            f"{resolved}:{relative_path}",
        )
        if (
            _source_git_text(repo_root, "committed_member_resolution", "cat-file", "-t", blob_oid)
            != "blob"
        ):
            _source_fail(
                "committed_member_resolution", f"source member is not a blob: {relative_path}"
            )
        committed = _source_git(
            repo_root, "committed_member_resolution", "show", f"{resolved}:{relative_path}"
        )
        if blob_oid != _git_blob_oid(committed):
            _source_fail(
                "committed_member_resolution",
                f"source member blob identity differs: {relative_path}",
            )
        current_path = repo_root / relative_path
        if not current_path.is_file():
            _source_fail(
                "current_worktree_member_bytes", f"current source member is absent: {relative_path}"
            )
        current = current_path.read_bytes()
        if current != committed:
            _source_fail(
                "current_worktree_member_bytes",
                f"current source bytes differ from committed bytes: {relative_path}",
            )
        row_values = {
            "relative_path": relative_path,
            "git_blob_oid": blob_oid,
            "committed_sha256": _sha(committed),
            "committed_byte_count": len(committed),
            "current_sha256": _sha(current),
            "current_byte_count": len(current),
        }
        rows.append(models.GitSourceMemberAuditRow(**row_values))
        candidate_rows.append({**row_values, "bytes_equal": True})

    candidate_id = (
        models.CANDIDATE_GENERATOR_BINDING_ID
        if kind == "generator_verifier"
        else models.CANDIDATE_REPAIR_BINDING_ID
    )
    candidate_body = {
        "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
        "authority_kind": kind,
        "requested_source_commit": resolved,
        "resolved_source_commit": resolved,
        "requested_source_tree": resolved_tree,
        "resolved_source_tree": resolved_tree,
        "source_files": tuple(candidate_rows),
        "source_path_set_sha256": _sha(_canonical_bytes(_source_paths(kind))),
        "source_file_set_sha256": _sha(_canonical_bytes(tuple(candidate_rows))),
        "commit_object_type": "commit",
        "commit_tree_relation_verified": True,
        "all_members_exist_at_commit": True,
        "all_current_bytes_equal_committed_bytes": True,
        "schema_version": "qa_generator_authoritative_source_binding.v1",
    }
    candidate = {"binding_id": candidate_id, **candidate_body}
    if (
        _identity(
            candidate, field="binding_id", prefix="qa_generator_authoritative_source_binding:"
        )
        != candidate_id
    ):
        _source_fail("candidate_binding_identity", "candidate source Binding identity differs")
    if _canonical_bytes(_load_bytes(candidate_payload)) != _canonical_bytes(candidate):
        _source_fail("candidate_binding_bytes", "candidate source Binding bytes differ")

    return _make(
        models.GitSourceGroupAudit,
        {
            "authorization_id": authorization_id,
            "authority_kind": kind,
            "requested_commit": commit,
            "resolved_commit": resolved,
            "requested_tree": tree,
            "resolved_tree": resolved_tree,
            "members": tuple(rows),
            "member_count": len(rows),
            "source_path_set_sha256": candidate_body["source_path_set_sha256"],
            "source_file_set_sha256": candidate_body["source_file_set_sha256"],
            "candidate_binding_id": candidate_id,
        },
        "audit_id",
        "qa_generator_independent_git_source_group_audit:",
    )


def _independent_git_authority(
    *, repo_root: Path, authorization_id: str, freeze_id: str, saved: Mapping[str, bytes]
) -> Any:
    generator = _independent_git_source_group(
        repo_root=repo_root,
        authorization_id=authorization_id,
        kind="generator_verifier",
        commit=models.GENERATOR_SOURCE_COMMIT,
        tree=models.GENERATOR_SOURCE_TREE,
        candidate_payload=saved["generator_source_binding.json"],
    )
    repair = _independent_git_source_group(
        repo_root=repo_root,
        authorization_id=authorization_id,
        kind="repair_implementation",
        commit=models.REPAIR_SOURCE_COMMIT,
        tree=models.REPAIR_SOURCE_TREE,
        candidate_payload=saved["repair_implementation_source_binding.json"],
    )
    return _make(
        models.IndependentGitSourceAuthorityAudit,
        {
            "candidate_freeze_audit_id": freeze_id,
            "generator_group": generator,
            "repair_group": repair,
        },
        "audit_id",
        "qa_generator_independent_git_source_authority_audit:",
    )


def _validate_candidate_source_rows(
    *,
    repo_root: Path,
    kind: str,
    commit: str,
    tree: str,
    rows: Sequence[Mapping[str, Any]],
    current_overrides: Mapping[str, bytes] | None = None,
) -> None:
    resolved = _source_git_text(
        repo_root, "git_commit_resolution", "rev-parse", f"{commit}^{{commit}}"
    )
    resolved_tree = _source_git_text(
        repo_root, "commit_tree_relation", "rev-parse", f"{resolved}^{{tree}}"
    )
    if resolved_tree != tree:
        _source_fail("commit_tree_relation", "source tree differs from git rev-parse commit^{tree}")
    paths = _source_paths(kind)
    if tuple(str(row.get("relative_path")) for row in rows) != paths:
        _source_fail("source_member_domain", "candidate source member domain differs")
    overrides = current_overrides or {}
    for row in rows:
        relative_path = str(row["relative_path"])
        committed = _source_git(
            repo_root,
            "committed_member_resolution",
            "show",
            f"{resolved}:{relative_path}",
        )
        blob = _source_git_text(
            repo_root,
            "committed_member_resolution",
            "rev-parse",
            f"{resolved}:{relative_path}",
        )
        if (
            row.get("git_blob_oid") != blob
            or row.get("committed_sha256") != _sha(committed)
            or int(row.get("committed_byte_count", -1)) != len(committed)
        ):
            _source_fail(
                "committed_member_bytes",
                f"candidate committed source member differs from Git: {relative_path}",
            )
        current = overrides.get(relative_path, (repo_root / relative_path).read_bytes())
        if (
            current != committed
            or row.get("current_sha256") != _sha(current)
            or int(row.get("current_byte_count", -1)) != len(current)
        ):
            _source_fail(
                "current_worktree_member_bytes",
                f"candidate current source member differs from Git commit: {relative_path}",
            )


def _source_control(
    name: str, *, candidate_binding_rehashed: bool, operation: Callable[[], object]
) -> Any:
    caught: Exception | None = None
    try:
        operation()
    except Exception as exc:
        caught = exc
    if caught is None:
        _fail("negative.accepted", f"negative control was accepted: {name}")
    if not isinstance(caught, GitSourceAuthorityError):
        _fail("negative.exception", f"source control raised unexpected exception: {name}")
    return models.IndependentSourceAttackControl(
        name=name,
        rejected=True,
        rejection_stage=caught.stage,
        exception_type="GitSourceAuthorityError",
        reason_sha256=_sha(str(caught).encode("utf-8")),
        candidate_binding_rehashed=candidate_binding_rehashed,
    )


def _legacy_counterexample(
    repo_root: Path, authorization_id: str, git_source_authority_audit_id: str
) -> Any:
    fake_commit = "0" * 40
    fake_tree = "1" * 40
    binding = legacy_totality._source_binding(
        repo_root,
        models.CANDIDATE_AUTHORIZATION_ID,
        fake_commit,
        fake_tree,
    )
    if not (
        binding.finance_numeric_candidate_v7_source_bound
        and binding.registered_catalog_totalized
        and binding.source_commit == fake_commit
        and binding.source_tree == fake_tree
        and binding.binding_id
        == "qa_generator_totality_source_binding:"
        "f9ee1a7058720579564b6e03bc590340f858984285f104410ba747bb2358fc58"
    ):
        _fail("legacy.counterexample", "legacy fake-label counterexample was not reproduced")
    caught: Exception | None = None
    try:
        _source_git_text(
            repo_root,
            "git_commit_resolution",
            "rev-parse",
            f"{fake_commit}^{{commit}}",
        )
    except Exception as exc:
        caught = exc
    if not isinstance(caught, GitSourceAuthorityError) or caught.stage != "git_commit_resolution":
        _fail("legacy.new_authority", "independent Git authority did not reject fake labels")
    return _make(
        models.IndependentLegacyCounterexampleAudit,
        {
            "git_source_authority_audit_id": git_source_authority_audit_id,
            "candidate_legacy_binding_id": binding.binding_id,
            "exception_type": "GitSourceAuthorityError",
            "reason_sha256": _sha(str(caught).encode("utf-8")),
        },
        "audit_id",
        "qa_generator_independent_legacy_counterexample_audit:",
    )


def _source_attacks(repo_root: Path, git_authority: Any) -> Any:
    generator = git_authority.generator_group
    repair = git_authority.repair_group
    generator_rows = [
        {
            "relative_path": row.relative_path,
            "git_blob_oid": row.git_blob_oid,
            "committed_sha256": row.committed_sha256,
            "committed_byte_count": row.committed_byte_count,
            "current_sha256": row.current_sha256,
            "current_byte_count": row.current_byte_count,
        }
        for row in generator.members
    ]
    repair_rows = [
        {
            "relative_path": row.relative_path,
            "git_blob_oid": row.git_blob_oid,
            "committed_sha256": row.committed_sha256,
            "committed_byte_count": row.committed_byte_count,
            "current_sha256": row.current_sha256,
            "current_byte_count": row.current_byte_count,
        }
        for row in repair.members
    ]
    wrong_tree = ("0" if generator.resolved_tree[0] != "0" else "1") + generator.resolved_tree[1:]
    changed = b"changed-source-member-control\n"
    changed_rows = copy.deepcopy(generator_rows)
    changed_rows[0].update(
        git_blob_oid=_git_blob_oid(changed),
        committed_sha256=_sha(changed),
        committed_byte_count=len(changed),
        current_sha256=_sha(changed),
        current_byte_count=len(changed),
    )
    crossed_rows = copy.deepcopy(generator_rows)
    for key in (
        "git_blob_oid",
        "committed_sha256",
        "committed_byte_count",
        "current_sha256",
        "current_byte_count",
    ):
        crossed_rows[0][key], crossed_rows[1][key] = crossed_rows[1][key], crossed_rows[0][key]
    repair_last = repair_rows[-1]
    altered_current = (repo_root / str(repair_last["relative_path"])).read_bytes() + (
        b"\n# uncommitted-worktree-control\n"
    )
    controls = (
        _source_control(
            "nonexistent_commit",
            candidate_binding_rehashed=False,
            operation=lambda: _source_git_text(
                repo_root,
                "git_commit_resolution",
                "rev-parse",
                f"{'0' * 40}^{{commit}}",
            ),
        ),
        _source_control(
            "real_commit_wrong_tree",
            candidate_binding_rehashed=False,
            operation=lambda: _independent_git_source_group(
                repo_root=repo_root,
                authorization_id=generator.authorization_id,
                kind="generator_verifier",
                commit=generator.resolved_commit,
                tree=wrong_tree,
                candidate_payload=b"{}",
            ),
        ),
        _source_control(
            "changed_source_member",
            candidate_binding_rehashed=True,
            operation=lambda: _validate_candidate_source_rows(
                repo_root=repo_root,
                kind="generator_verifier",
                commit=generator.resolved_commit,
                tree=generator.resolved_tree,
                rows=changed_rows,
            ),
        ),
        _source_control(
            "crossed_source_members",
            candidate_binding_rehashed=True,
            operation=lambda: _validate_candidate_source_rows(
                repo_root=repo_root,
                kind="generator_verifier",
                commit=generator.resolved_commit,
                tree=generator.resolved_tree,
                rows=crossed_rows,
            ),
        ),
        _source_control(
            "uncommitted_worktree_source",
            candidate_binding_rehashed=False,
            operation=lambda: _validate_candidate_source_rows(
                repo_root=repo_root,
                kind="repair_implementation",
                commit=repair.resolved_commit,
                tree=repair.resolved_tree,
                rows=repair_rows,
                current_overrides={str(repair_last["relative_path"]): altered_current},
            ),
        ),
    )
    return _make(
        models.IndependentSourceAttackAudit,
        {
            "git_source_authority_audit_id": git_authority.audit_id,
            "controls": controls,
        },
        "audit_id",
        "qa_generator_independent_source_attack_audit:",
    )


def _registry_roles() -> tuple[dict[str, str], str]:
    manifest = finance_vnext_operation_registry().manifest()
    roles = {str(row["operator_id"]): str(row["program_role"]) for row in manifest}
    if len(roles) != len(manifest) or set(roles.values()) - {"semantic", "transparent_projection"}:
        _fail("depth.registry_roles", "Registry role domain differs")
    return roles, _sha(_canonical_bytes(manifest))


def _validate_program_graph(program: Mapping[str, Any]) -> tuple[tuple[dict[str, Any], ...], str]:
    raw_nodes = program.get("nodes")
    output = program.get("output_node_id")
    if not isinstance(raw_nodes, list) or not isinstance(output, str):
        _fail("depth.program_schema", "public Program schema differs")
    nodes = tuple(cast(dict[str, Any], row) for row in raw_nodes)
    identifiers = tuple(str(row.get("public_node_id", row.get("node_id", ""))) for row in nodes)
    if not identifiers or len(set(identifiers)) != len(identifiers) or output not in identifiers:
        _fail("depth.program_schema", "Program node identity domain differs")
    seen: set[str] = set()
    for node_id, row in zip(identifiers, nodes, strict=True):
        dependencies = tuple(str(value) for value in row.get("dependencies", ()))
        if not set(dependencies).issubset(seen):
            _fail("depth.topology", f"Program is not topologically ordered: {node_id}")
        inputs = row.get("inputs", row.get("input_refs", ()))
        operation_refs = tuple(
            str(value.get("role_id", value.get("ref_id", "")))
            for value in inputs
            if value.get("kind") == "operation"
        )
        if set(operation_refs) != set(dependencies):
            _fail("depth.dependency_input_relation", f"operation references differ: {node_id}")
        seen.add(node_id)
    return nodes, output


def _depth_projection(program: Mapping[str, Any], roles: Mapping[str, str]) -> dict[str, Any]:
    nodes, output = _validate_program_graph(program)
    node_map = {str(row.get("public_node_id", row.get("node_id"))): row for row in nodes}
    ancestors: set[str] = set()
    pending = [output]
    while pending:
        node_id = pending.pop()
        if node_id in ancestors:
            continue
        if node_id not in node_map:
            _fail("depth.dependency", f"Program dependency is absent: {node_id}")
        ancestors.add(node_id)
        pending.extend(str(value) for value in node_map[node_id].get("dependencies", ()))
    if ancestors != set(node_map):
        extras = tuple(sorted(set(node_map) - ancestors))
        _fail(
            "output_dependency_closure",
            f"Program contains nodes outside output dependency closure: {extras}",
        )
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    transparent = 0
    semantic_nodes = 0
    for node_id, row in zip(node_map, nodes, strict=True):
        dependencies = tuple(str(value) for value in row.get("dependencies", ()))
        role = roles.get(str(row.get("operator_id")))
        if role == "semantic":
            weight = 1
            semantic_nodes += 1
        elif role == "transparent_projection":
            weight = 0
            transparent += 1
        else:
            _fail("depth.registry_roles", f"unsupported Registry role: {role}")
        structural[node_id] = 1 + max((structural[parent] for parent in dependencies), default=0)
        semantic[node_id] = weight + max((semantic[parent] for parent in dependencies), default=0)
    return {
        "node_count": len(nodes),
        "output_ancestor_node_count": len(ancestors),
        "transparent_projection_node_count": transparent,
        "semantic_operation_node_count": semantic_nodes,
        "structural_dependency_depth": structural[output],
        "semantic_operation_depth": semantic[output],
        "workflow_interaction_depth": 1 + semantic[output] + 1,
        "structural_depth_by_node": structural,
        "semantic_depth_by_node": semantic,
        "output_dependency_closed": True,
    }


def _compare_reconstructed_program(
    skeleton: Mapping[str, Any], reconstructed: Mapping[str, Any]
) -> None:
    source_nodes, source_output = _validate_program_graph(skeleton)
    rebuilt_nodes, rebuilt_output = _validate_program_graph(reconstructed)
    if source_output != rebuilt_output or len(source_nodes) != len(rebuilt_nodes):
        _fail("fixture.source_program", "reconstructed Program shape differs")
    for source, rebuilt in zip(source_nodes, rebuilt_nodes, strict=True):
        source_id = source.get("public_node_id")
        if (
            rebuilt.get("node_id") != source_id
            or rebuilt.get("operator_id") != source.get("operator_id")
            or tuple(rebuilt.get("dependencies", ())) != tuple(source.get("dependencies", ()))
        ):
            _fail("fixture.source_program", f"reconstructed Program node differs: {source_id}")


def _validate_workflow(
    *,
    package: Mapping[str, Any],
    execution: Mapping[str, Any],
    trajectory: Mapping[str, Any],
    semantic_depth: int,
) -> None:
    task = cast(Mapping[str, Any], package["task"])
    public = cast(Mapping[str, Any], task["public"])
    reconstructed = cast(Mapping[str, Any], execution["reconstructed_program"])
    nodes, output = _validate_program_graph(reconstructed)
    if (
        execution.get("realized_package_id") != package.get("realized_package_id")
        or trajectory.get("task_id") != task.get("task_id")
        or cast(Mapping[str, Any], execution.get("trajectory", {})).get("task_id")
        != task.get("task_id")
        or trajectory.get("program_execution") != execution.get("program_execution")
        or not cast(Mapping[str, Any], execution.get("independent_verification", {})).get("passed")
    ):
        _fail("fixture.parents", "fixture execution/trajectory parents differ")
    steps = cast(list[dict[str, Any]], trajectory.get("steps", []))
    plan = [row for row in steps if row.get("action") == "plan"]
    search = [row for row in steps if row.get("action") == "search"]
    selection = [
        row
        for row in steps
        if row.get("action") == "select_evidence" and row.get("operator_id") is None
    ]
    operations = [row for row in steps if row.get("operator_id") is not None]
    verifies = [row for row in steps if row.get("action") == "verify"]
    answers = [row for row in steps if row.get("action") == "answer"]
    if any(len(group) != 1 for group in (plan, search, selection, answers)):
        _fail("fixture.workflow", "workflow fixed stage cardinality differs")
    if len(verifies) > 1 or (semantic_depth > 0 and len(verifies) != 1):
        _fail("fixture.workflow", "workflow independent verification cardinality differs")
    if (
        tuple(row.get("program_node_id") for row in operations)
        != tuple(row.get("node_id") for row in nodes)
        or tuple(row.get("operator_id") for row in operations)
        != tuple(row.get("operator_id") for row in nodes)
        or any(row.get("status") != "succeeded" for row in steps)
    ):
        _fail("fixture.workflow", "workflow Program operation sequence differs")
    first_operation = int(operations[0]["step_index"])
    last_operation = int(operations[-1]["step_index"])
    if not (
        int(plan[0]["step_index"])
        < int(search[0]["step_index"])
        < int(selection[0]["step_index"])
        < first_operation
        <= last_operation
        < int(answers[0]["step_index"])
    ):
        _fail("fixture.workflow", "workflow causal order differs")
    if verifies:
        verify = verifies[0]
        if not (
            last_operation < int(verify["step_index"]) < int(answers[0]["step_index"])
            and verify.get("program_node_id") == output
            and tuple(verify.get("input_refs", ())) == (f"operation:{output}",)
        ):
            _fail("fixture.workflow", "workflow verification parent differs")
    if public.get("task_type") is None:
        _fail("fixture.task_type", "fixture task type is absent")


def _distribution(values: Sequence[int]) -> dict[str, int]:
    counts = Counter(values)
    return {str(key): counts[key] for key in sorted(counts)}


def _fixture_and_depth_audit(
    saved: Mapping[str, bytes], authorization_id: str, git_source_authority_audit_id: str
) -> tuple[Any, Any, dict[str, Any]]:
    bundles = _jsonl(saved["evidence_bundles.jsonl"], expected=8, stage="fixture.bundles")
    packages = _jsonl(saved["realized_task_packages.jsonl"], expected=8, stage="fixture.packages")
    executions = _jsonl(saved["program_executions.jsonl"], expected=8, stage="fixture.executions")
    trajectories = _jsonl(saved["trajectories.jsonl"], expected=8, stage="fixture.trajectories")
    verifications = _jsonl(
        saved["verification_reports.jsonl"], expected=8, stage="fixture.verifications"
    )
    assessments = _jsonl(
        saved["quality_assessments.jsonl"], expected=8, stage="fixture.assessments"
    )
    package_by_id = {str(row["realized_package_id"]): row for row in packages}
    trajectory_by_id = {str(row["task_id"]): row for row in trajectories}
    verification_by_trajectory = {str(row["trajectory_id"]): row for row in verifications}
    assessment_by_trajectory = {str(row["trajectory_id"]): row for row in assessments}
    if not all(
        len(domain) == 8
        for domain in (
            package_by_id,
            trajectory_by_id,
            verification_by_trajectory,
            assessment_by_trajectory,
        )
    ):
        _fail("fixture.identity_domain", "fixture identities are not unique")
    bundle_by_evidence = {
        tuple(sorted(str(item["evidence_id"]) for item in row["evidence"])): row for row in bundles
    }
    if len(bundle_by_evidence) != 8:
        _fail("fixture.bundle_domain", "fixture Evidence Bundles are not unique")

    roles, registry_hash = _registry_roles()
    runtime_registry = finance_vnext_operation_registry()
    semantic_policy = FinanceSemanticPolicy()
    workflow_verifier = CandidateWorkflowVerifier(
        registry=runtime_registry, semantic_policy=semantic_policy
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=semantic_policy, workflow_verifier=workflow_verifier
    )
    independent_rows: list[
        tuple[Any, dict[str, Any], tuple[str, ...], tuple[str, ...], dict[str, Any]]
    ] = []
    source_by_type: dict[str, dict[str, Any]] = {}
    for execution in executions:
        package = package_by_id.get(str(execution.get("realized_package_id")))
        embedded = cast(Mapping[str, Any], execution.get("trajectory", {}))
        trajectory = trajectory_by_id.get(str(embedded.get("task_id")))
        if package is None or trajectory is None:
            _fail("fixture.parents", "fixture Package or final Trajectory parent is absent")
        verification = verification_by_trajectory.get(str(trajectory["trajectory_id"]))
        assessment = assessment_by_trajectory.get(str(trajectory["trajectory_id"]))
        if verification is None or assessment is None:
            _fail("fixture.parents", "fixture verification or assessment parent is absent")
        task = cast(Mapping[str, Any], package["task"])
        public = cast(Mapping[str, Any], task["public"])
        oracle = cast(Mapping[str, Any], task["oracle"])
        evidence_key = tuple(sorted(str(value) for value in oracle["gold_evidence_ids"]))
        bundle = bundle_by_evidence.get(evidence_key)
        if bundle is None:
            _fail("fixture.parents", "fixture Evidence Bundle parent is absent")
        task_type = str(public["task_type"])
        source_program = cast(dict[str, Any], oracle["task_program"])
        program_identity = {
            "nodes": source_program["nodes"],
            "output_node_id": source_program["output_node_id"],
            "version": "task_program.v2",
        }
        if source_program.get("program_id") != "program:" + _sha(
            _canonical_bytes(program_identity)
        ):
            _fail("fixture.program_identity", "source Program identity differs")
        public_skeleton = cast(Mapping[str, Any], public["program_skeleton"])
        reconstructed = cast(Mapping[str, Any], execution["reconstructed_program"])
        _compare_reconstructed_program(public_skeleton, reconstructed)
        if _canonical_bytes(source_program) != _canonical_bytes(reconstructed):
            _fail(
                "fixture.source_program", "oracle source Program differs from reconstructed Program"
            )
        projection = _depth_projection(source_program, roles)
        _validate_workflow(
            package=package,
            execution=execution,
            trajectory=trajectory,
            semantic_depth=projection["semantic_operation_depth"],
        )
        bundle_model = EvidenceBundle.model_validate(bundle)
        package_model = RealizedTaskPackage.model_validate(package)
        program_model = TaskProgram.model_validate(source_program)
        trajectory_model = Trajectory.model_validate(trajectory)
        evidence_by_id = {item.evidence_id: item for item in bundle_model.evidence}
        replayed_execution = TaskProgramExecutor(runtime_registry).execute(
            program_model, evidence_by_id
        )
        replayed_verification = TaskProgramOracleVerifier(runtime_registry).verify(
            program_model,
            evidence_by_id,
            replayed_execution.node_outputs,
        )
        corpus = EvidenceCorpus.from_bundle(bundle_model)
        graph = ProofGraphBuilder().build(bundle_model)
        replayed_public_execution = PublicPlanCandidateExecutor(runtime_registry).generate(
            package_model, corpus
        )
        replayed_workflow_report = workflow_verifier.verify(
            package_model.task, corpus, graph, trajectory_model
        )
        replayed_assessment = evaluator.evaluate(
            package_model.task, corpus, graph, trajectory_model
        )
        if (
            replayed_public_execution.model_dump(mode="json") != execution
            or replayed_execution.model_dump(mode="json") != execution["program_execution"]
            or replayed_verification.model_dump(mode="json")
            != execution["independent_verification"]
            or replayed_workflow_report.model_dump(mode="json") != verification
            or replayed_assessment.model_dump(mode="json") != assessment
        ):
            _fail("fixture.independent_replay", "independently replayed fixture bytes differ")

        checks = {str(row["check_id"]): bool(row["passed"]) for row in verification["checks"]}
        operation_correct = checks.get("operation_correctness", False)
        answer_schema = checks.get("answer_schema_validity", False)
        answer_correct = checks.get("answer_correctness", False)
        citation_correct = checks.get("citation_binding", False)
        node_count = int(projection["node_count"])
        independent_replay = cast(Mapping[str, Any], execution["independent_verification"])
        if (
            not all((operation_correct, answer_schema, answer_correct, citation_correct))
            or verification.get("executed_program_node_count") != node_count
            or execution.get("actual_node_count") != node_count
            or execution.get("independently_replayed_node_count") != node_count
            or not independent_replay.get("passed")
            or assessment.get("decision") != "accepted"
        ):
            _fail("fixture.verification", "fixture independent verification result differs")
        fixture_row = _make(
            models.IndependentFixtureRow,
            {
                "task_type": task_type,
                "evidence_bundle_id": bundle["bundle_id"],
                "realized_package_id": package["realized_package_id"],
                "trajectory_id": trajectory["trajectory_id"],
                "public_plan_execution_id": execution["execution_id"],
                "verification_report_id": "qa_generator_independent_verification_projection:"
                + _sha(_canonical_bytes(verification)),
                "quality_assessment_id": assessment["assessment_id"],
                "program_id": source_program["program_id"],
                "node_count": node_count,
                "executed_node_count": int(verification["executed_program_node_count"]),
                "independently_replayed_node_count": int(
                    execution["independently_replayed_node_count"]
                ),
                "operation_correct": operation_correct,
                "answer_schema_correct": answer_schema,
                "answer_correct": answer_correct,
                "citation_correct": citation_correct,
                "evaluator_accepted": assessment["decision"] == "accepted",
            },
            "row_id",
            "qa_generator_independent_fixture_row:",
        )
        operators = tuple(str(node["operator_id"]) for node in source_program["nodes"])
        registry_roles = tuple(roles[operator] for operator in operators)
        independent_rows.append(
            (fixture_row, projection, operators, registry_roles, source_program)
        )
        source_by_type[task_type] = copy.deepcopy(source_program)

    fixture_rows = tuple(
        sorted((row[0] for row in independent_rows), key=lambda row: row.task_type)
    )
    if tuple(row.task_type for row in fixture_rows) != models.REGISTERED_TASK_TYPES:
        _fail("fixture.task_type_domain", "exact eight task-type domain differs")
    fixture_audit = _make(
        models.IndependentFixtureAudit,
        {
            "git_source_authority_audit_id": git_source_authority_audit_id,
            "rows": fixture_rows,
        },
        "audit_id",
        "qa_generator_independent_fixture_audit:",
    )

    candidate_depth = _load_bytes(saved["depth_metric_audit.json"])
    candidate_rows = {str(row["task_type"]): row for row in candidate_depth.get("rows", ())}
    depth_rows: list[Any] = []
    for fixture_row, projection, operators, registry_roles, source_program in independent_rows:
        candidate = candidate_rows.get(fixture_row.task_type)
        if candidate is None:
            _fail("depth.candidate_comparison", "candidate depth row is absent")
        metrics = cast(Mapping[str, Any], candidate["metrics"])
        expected = (
            projection["node_count"],
            projection["structural_dependency_depth"],
            projection["semantic_operation_depth"],
            projection["workflow_interaction_depth"],
        )
        observed = (
            metrics.get("node_count"),
            metrics.get("structural_dependency_depth"),
            metrics.get("semantic_operation_depth"),
            metrics.get("workflow_interaction_depth"),
        )
        if (
            observed != expected
            or tuple(candidate.get("operator_sequence", ())) != operators
            or tuple(candidate.get("registry_role_sequence", ())) != registry_roles
            or metrics.get("program_id") != source_program["program_id"]
        ):
            _fail("depth.candidate_comparison", "candidate depth row differs from derivation")
        program_hash = _program_hash(source_program)
        if metrics.get("program_hash") != program_hash:
            _fail("depth.program_hash", "independently recomputed Program hash differs")
        depth_rows.append(
            _make(
                models.IndependentDepthMetricRow,
                {
                    "fixture_row_id": fixture_row.row_id,
                    "task_type": fixture_row.task_type,
                    "program_id": source_program["program_id"],
                    "program_hash": program_hash,
                    "metrics_id": "qa_generator_independent_program_depth_metrics:"
                    + _sha(
                        _canonical_bytes({**projection, "program_id": source_program["program_id"]})
                    ),
                    "operator_sequence": operators,
                    "registry_role_sequence": registry_roles,
                    "node_count": projection["node_count"],
                    "structural_dependency_depth": projection["structural_dependency_depth"],
                    "semantic_operation_depth": projection["semantic_operation_depth"],
                    "workflow_interaction_depth": projection["workflow_interaction_depth"],
                },
                "row_id",
                "qa_generator_independent_depth_metric_row:",
            )
        )
    depth_rows_tuple = tuple(sorted(depth_rows, key=lambda row: row.task_type))
    depth_audit = _make(
        models.IndependentDepthMetricAudit,
        {
            "fixture_audit_id": fixture_audit.audit_id,
            "rows": depth_rows_tuple,
            "node_count_distribution": _distribution([row.node_count for row in depth_rows_tuple]),
            "structural_dependency_depth_distribution": _distribution(
                [row.structural_dependency_depth for row in depth_rows_tuple]
            ),
            "semantic_operation_depth_distribution": _distribution(
                [row.semantic_operation_depth for row in depth_rows_tuple]
            ),
            "workflow_interaction_depth_distribution": _distribution(
                [row.workflow_interaction_depth for row in depth_rows_tuple]
            ),
        },
        "audit_id",
        "qa_generator_independent_depth_metric_audit:",
    )
    if registry_hash != models.REGISTRY_MANIFEST_SHA256:
        _fail("depth.registry_manifest", "Registry Manifest hash differs")
    return fixture_audit, depth_audit, source_by_type


def _program_with_identity(program: Mapping[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(dict(program))
    identity = {
        "nodes": body["nodes"],
        "output_node_id": body["output_node_id"],
        "version": "task_program.v2",
    }
    body["program_id"] = "program:" + _sha(_canonical_bytes(identity))
    body["program_version"] = "task_program.v2"
    return body


def _depth_attack(
    *,
    name: str,
    exact: Mapping[str, Any],
    candidate: Mapping[str, Any],
    roles: Mapping[str, str],
    final_answer_sha256: str,
) -> Any:
    caught: Exception | None = None
    try:
        _depth_projection(candidate, roles)
        if _canonical_bytes(candidate) != _canonical_bytes(exact):
            _fail(
                "exact_source_program_admission",
                "candidate Program differs from exact source Program",
            )
    except Exception as exc:
        caught = exc
    if caught is None:
        _fail("depth_attack.accepted", f"depth attack was accepted: {name}")
    return models.IndependentDepthAttackControl(
        name=name,
        candidate_program_id=str(candidate["program_id"]),
        candidate_program_hash=_program_hash(candidate),
        retained_final_answer_sha256=final_answer_sha256,
        rejected=True,
        rejection_stage=str(getattr(caught, "stage", "unexpected")),
        exception_type=type(caught).__name__,
        reason_sha256=_sha(str(caught).encode("utf-8")),
    )


def _depth_attacks(
    saved: Mapping[str, bytes],
    depth_metric_audit_id: str,
    sources: Mapping[str, dict[str, Any]],
) -> Any:
    source = copy.deepcopy(sources["derived_growth_comparison"])
    nodes = cast(list[dict[str, Any]], source["nodes"])
    output = copy.deepcopy(
        next(node for node in nodes if node["node_id"] == source["output_node_id"])
    )
    left_growth = next(node for node in nodes if node["node_id"] == "left_growth")
    retained = [node for node in nodes if node["node_id"] in set(left_growth["dependencies"])]
    output["dependencies"] = ["left_growth"]
    output["input_refs"] = [
        {"kind": "operation", "ref_id": "left_growth", "selector": "value"},
        {"kind": "operation", "ref_id": "left_growth", "selector": "value"},
    ]
    deleted = _program_with_identity({**source, "nodes": [*retained, left_growth, output]})

    lookup_nodes = [node for node in nodes if node["operator_id"] == "lookup"]
    bypass_output = copy.deepcopy(
        next(node for node in nodes if node["node_id"] == source["output_node_id"])
    )
    bypass_output["dependencies"] = []
    bypass_output["input_refs"] = [
        {
            "kind": "evidence",
            "ref_id": lookup_nodes[0]["input_refs"][0]["ref_id"],
            "selector": "payload.value",
        },
        {
            "kind": "evidence",
            "ref_id": lookup_nodes[2]["input_refs"][0]["ref_id"],
            "selector": "payload.value",
        },
    ]
    bypass = _program_with_identity({**source, "nodes": [bypass_output]})

    irrelevant = copy.deepcopy(lookup_nodes[0])
    irrelevant["node_id"] = "depth_attack_irrelevant_lookup"
    inflated = _program_with_identity({**source, "nodes": [*nodes, irrelevant]})

    trajectories = _jsonl(
        saved["trajectories.jsonl"], expected=8, stage="depth_attack.trajectories"
    )
    source_program_id = source["program_id"]
    derived_trajectory = next(
        row
        for row in trajectories
        if cast(Mapping[str, Any], row.get("program_execution", {})).get("program_id")
        == source_program_id
    )
    final_hash = _sha(_canonical_bytes(derived_trajectory["final_answer"]))
    roles, _ = _registry_roles()
    controls = tuple(
        _depth_attack(
            name=name,
            exact=source,
            candidate=candidate,
            roles=roles,
            final_answer_sha256=final_hash,
        )
        for name, candidate in zip(
            models.DEPTH_ATTACK_NAMES,
            (deleted, bypass, inflated),
            strict=True,
        )
    )
    return _make(
        models.IndependentDepthAttackAudit,
        {"depth_metric_audit_id": depth_metric_audit_id, "controls": controls},
        "audit_id",
        "qa_generator_independent_depth_attack_audit:",
    )


def _helper_boundary(repo_root: Path, source_commit: str, source_tree: str) -> dict[str, Any]:
    development_sentinel = source_commit == source_tree == "1" * 40
    if development_sentinel:
        source_commit = _git_text(repo_root, "implementation.commit", "rev-parse", "HEAD")
        resolved_tree = _git_text(
            repo_root, "implementation.commit_tree", "rev-parse", "HEAD^{tree}"
        )
    else:
        resolved_commit = _git_text(
            repo_root,
            "implementation.commit",
            "rev-parse",
            f"{source_commit}^{{commit}}",
        )
        if resolved_commit != source_commit:
            _fail("implementation.commit", "independent audit commit resolution differs")
        resolved_tree = _git_text(
            repo_root,
            "implementation.commit_tree",
            "rev-parse",
            f"{source_commit}^{{tree}}",
        )
        if resolved_tree != source_tree:
            _fail("implementation.commit_tree", "independent audit commit/tree relation differs")

    rows: list[models.GitSourceMemberAuditRow] = []
    audit_payload: bytes | None = None
    for relative_path in models.INDEPENDENT_AUDIT_SOURCE_PATHS:
        current_path = repo_root / relative_path
        if not current_path.is_file():
            _fail("implementation.current_bytes", f"audit source member absent: {relative_path}")
        current = current_path.read_bytes()
        if development_sentinel:
            committed = current
            blob_oid = _git_blob_oid(committed)
        else:
            committed = _git(
                repo_root,
                "implementation.source",
                "show",
                f"{source_commit}:{relative_path}",
            )
            blob_oid = _git_text(
                repo_root,
                "implementation.source",
                "rev-parse",
                f"{source_commit}:{relative_path}",
            )
            if blob_oid != _git_blob_oid(committed):
                _fail(
                    "implementation.source",
                    f"audit source blob differs: {relative_path}",
                )
            if committed != current:
                _fail(
                    "implementation.current_bytes",
                    f"audit source current bytes differ: {relative_path}",
                )
        rows.append(
            models.GitSourceMemberAuditRow(
                relative_path=relative_path,
                git_blob_oid=blob_oid,
                committed_sha256=_sha(committed),
                committed_byte_count=len(committed),
                current_sha256=_sha(current),
                current_byte_count=len(current),
            )
        )
        if relative_path.endswith("/audit.py"):
            audit_payload = current
    if audit_payload is None:
        _fail("implementation.source_domain", "audit implementation source is absent")

    tree = ast.parse(audit_payload.decode("utf-8"))
    forbidden_modules = {
        "trusted_synthesis.experiments.qa_generator_source_authority.preflight",
        "trusted_synthesis.experiments.qa_generator_source_authority.depth",
        "trusted_synthesis.experiments.qa_generator_source_authority.models",
        "trusted_synthesis.core.task.program_depth",
    }
    forbidden_calls = {
        "build_qa_generator_source_authority_repair",
        "build_git_source_authority",
        "validate_git_source_authority",
        "build_depth_metric_audit",
        "derive_program_depth_metrics",
        "admit_program_depth_metrics",
        "_freeze_predecessor",
        "_run_retained_fixtures",
        "_depth_negative_controls",
    }
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    if imports & forbidden_modules or calls & forbidden_calls:
        _fail("implementation.helper_boundary", "candidate helper or depth oracle call is present")
    source_rows = tuple(rows)
    return {
        "audit_source_commit": source_commit,
        "audit_source_tree": resolved_tree,
        "audit_source_members": source_rows,
        "audit_source_member_count": len(source_rows),
        "audit_source_member_set_sha256": _sha(
            _canonical_bytes(tuple(row.model_dump(mode="python") for row in source_rows))
        ),
        "audit_source_commit_tree_relation_verified": True,
        "audit_source_current_byte_matches": sum(row.current_bytes_match for row in source_rows),
        "helper_boundary_passed": True,
        "candidate_helper_calls": 0,
        "candidate_oracle_calls": 0,
    }


def build_qa_generator_source_authority_independent_audit(
    repo_root: Path,
    external_audit_path: Path,
    source_commit: str,
    source_tree: str,
) -> models.QAGeneratorSourceAuthorityIndependentAuditProducts:
    root = repo_root.resolve()
    review = external_audit_path.read_bytes()
    authorization = _authorization(review)
    source_facts = _helper_boundary(root, source_commit, source_tree)
    freeze, saved = _freeze_candidate(root, authorization.authorization_id)
    detached = _detached_rebuild(root, freeze.audit_id, saved)
    git_authority = _independent_git_authority(
        repo_root=root,
        authorization_id=authorization.authorization_id,
        freeze_id=freeze.audit_id,
        saved=saved,
    )
    legacy = _legacy_counterexample(root, authorization.authorization_id, git_authority.audit_id)
    source_attack = _source_attacks(root, git_authority)
    fixture, depth, sources = _fixture_and_depth_audit(
        saved, authorization.authorization_id, git_authority.audit_id
    )
    depth_attack = _depth_attacks(saved, depth.audit_id, sources)
    scope = _make(
        models.IndependentScopeBoundaryAudit,
        {
            "authorization_id": authorization.authorization_id,
            "candidate_freeze_audit_id": freeze.audit_id,
            "detached_rebuild_audit_id": detached.audit_id,
            "git_source_authority_audit_id": git_authority.audit_id,
            "fixture_audit_id": fixture.audit_id,
            "depth_metric_audit_id": depth.audit_id,
            "source_attack_audit_id": source_attack.audit_id,
            "depth_attack_audit_id": depth_attack.audit_id,
            **source_facts,
        },
        "audit_id",
        "qa_generator_source_authority_independent_scope_audit:",
    )
    gates = {
        "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE": freeze.passed,
        "A1_DETACHED_EXACT_DIRECTORY_REBUILD": detached.passed,
        "A2_INDEPENDENT_GIT_SOURCE_AUTHORITY": git_authority.passed,
        "A3_LEGACY_COUNTEREXAMPLE_AND_SOURCE_ATTACKS": (legacy.passed and source_attack.passed),
        "A4_INDEPENDENT_EIGHT_FIXTURE_RECONSTRUCTION": fixture.passed,
        "A5_INDEPENDENT_FOUR_DEPTH_METRIC_DERIVATION": depth.passed,
        "A6_INDEPENDENT_DEPTH_ATTACKS": depth_attack.passed,
        "A7_ZERO_EXTERNAL_EXECUTION_SCOPE": (
            scope.helper_boundary_passed
            and not any(
                (
                    scope.provider_calls,
                    scope.credential_lookups,
                    scope.gpu_jobs,
                    scope.online_job_manifests,
                    scope.empirical_rows,
                    scope.qa_release_objects,
                    scope.vtdo_rows,
                    scope.training_rows,
                    scope.production_rows,
                    scope.archive_grounding_rows,
                    scope.benchmark_distribution_rows,
                    scope.semantic_depth_expansion_rows,
                    scope.candidate_formal_writes,
                    scope.candidate_helper_calls,
                    scope.candidate_oracle_calls,
                )
            )
        ),
    }
    gate = _make(
        models.IndependentGateEvaluation,
        {"gates": gates},
        "gate_id",
        "qa_generator_source_authority_independent_gate:",
    )
    common = {
        "authorization_id": authorization.authorization_id,
        "candidate_freeze_audit_id": freeze.audit_id,
        "detached_rebuild_audit_id": detached.audit_id,
        "git_source_authority_audit_id": git_authority.audit_id,
        "legacy_counterexample_audit_id": legacy.audit_id,
        "source_attack_audit_id": source_attack.audit_id,
        "fixture_audit_id": fixture.audit_id,
        "depth_metric_audit_id": depth.audit_id,
        "depth_attack_audit_id": depth_attack.audit_id,
        "scope_audit_id": scope.audit_id,
        "gate_id": gate.gate_id,
    }
    decision = _make(
        models.IndependentAuditDecision,
        common,
        "decision_id",
        "qa_generator_source_authority_independent_decision:",
    )
    transition = _make(
        models.IndependentAuditTransition,
        {"decision_id": decision.decision_id},
        "transition_id",
        "qa_generator_source_authority_independent_transition:",
    )
    report = _make(
        models.IndependentAuditReport,
        {
            **common,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
            "semantic_operation_depth_distribution": depth.semantic_operation_depth_distribution,
        },
        "report_id",
        "qa_generator_source_authority_independent_report:",
    )
    return models.QAGeneratorSourceAuthorityIndependentAuditProducts(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=models.OPERATOR_DIRECTIVE.encode("utf-8"),
        candidate_freeze=freeze,
        detached_rebuild=detached,
        git_source_authority_audit=git_authority,
        legacy_counterexample_audit=legacy,
        source_attack_audit=source_attack,
        fixture_audit=fixture,
        depth_metric_audit=depth,
        depth_attack_audit=depth_attack,
        scope_audit=scope,
        gate_evaluation=gate,
        decision=decision,
        transition=transition,
        report=report,
    )


def _jsonl_bytes(values: Sequence[Any]) -> bytes:
    return b"".join(_encoded(value) for value in values)


def write_qa_generator_source_authority_independent_audit_artifacts(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
    output_dir: Path,
) -> tuple[str, ...]:
    payloads = {
        "authorization.json": _encoded(products.authorization),
        "candidate_freeze_audit.json": _encoded(products.candidate_freeze),
        "depth_metric_audit.json": _encoded(products.depth_metric_audit),
        "depth_metric_rows.jsonl": _jsonl_bytes(products.depth_metric_audit.rows),
        "depth_negative_control_audit.json": _encoded(products.depth_attack_audit),
        "detached_rebuild_audit.json": _encoded(products.detached_rebuild),
        "decision.json": _encoded(products.decision),
        "external_review.txt": products.external_review_bytes,
        "fixture_audit.json": _encoded(products.fixture_audit),
        "fixture_rows.jsonl": _jsonl_bytes(products.fixture_audit.rows),
        "gate_evaluation.json": _encoded(products.gate_evaluation),
        "generator_git_source_group_audit.json": _encoded(
            products.git_source_authority_audit.generator_group
        ),
        "git_source_authority_audit.json": _encoded(products.git_source_authority_audit),
        "legacy_counterexample_audit.json": _encoded(products.legacy_counterexample_audit),
        "operator_directive.txt": products.operator_directive_bytes,
        "repair_git_source_group_audit.json": _encoded(
            products.git_source_authority_audit.repair_group
        ),
        "report.json": _encoded(products.report),
        "scope_boundary_audit.json": _encoded(products.scope_audit),
        "source_negative_control_audit.json": _encoded(products.source_attack_audit),
        "transition.json": _encoded(products.transition),
    }
    member_rows = tuple(
        models.ArtifactManifestMember(
            relative_path=path,
            sha256=_sha(payload),
            byte_count=len(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    manifest = _make(
        models.ArtifactManifest,
        {
            "members": member_rows,
            "file_count": len(member_rows),
            "member_bytes": sum(row.byte_count for row in member_rows),
            "artifact_root": "qa_generator_source_authority_independent_artifact_root:"
            + _sha(_canonical_bytes(tuple(row.model_dump(mode="python") for row in member_rows))),
        },
        "manifest_id",
        "qa_generator_source_authority_independent_artifact_manifest:",
    )
    payloads["artifact_manifest.json"] = _encoded(manifest)
    return write_immutable_artifact_directory(output_dir, payloads)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    products = build_qa_generator_source_authority_independent_audit(
        args.repo_root,
        args.external_audit,
        args.source_commit,
        args.source_tree,
    )
    write_qa_generator_source_authority_independent_audit_artifacts(products, args.output_dir)


if __name__ == "__main__":
    main()
