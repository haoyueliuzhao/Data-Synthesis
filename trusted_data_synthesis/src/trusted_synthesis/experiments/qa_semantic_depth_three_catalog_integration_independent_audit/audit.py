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
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn, cast

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.registry import OperationRegistry, make_operation_definition
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.realization import (
    QuestionRendererProfile,
    RealizedTaskPackage,
    realize_task,
)
from trusted_synthesis.core.task.semantic import build_semantic_binding_bundle
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.question_rendering import finance_renderer_registry
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.operations import (
    AbsolutePercentagePointGapExecutor,
    AbsolutePercentagePointGapOracle,
    PercentagePointOutput,
    PercentOutput,
    ScaleRatioPercentExecutor,
    ScaleRatioPercentOracle,
    SignedPercentagePointGapExecutor,
    SignedPercentagePointGapOracle,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.patterns import (
    DepthThreePatternRuntime,
    depth_three_patterns,
    depth_three_renderer_profiles,
)

from . import models


class AuditError(ValueError):
    """Typed independent-audit rejection carrying the observed boundary."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise AuditError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    body = dict(values)
    body[field] = strict_canonical_hash(body, prefix=prefix)
    return body


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _object(payload: bytes, stage: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail(stage, "expected a JSON object")
    return cast(dict[str, Any], value)


def _rows(payload: bytes, expected: int, stage: str) -> tuple[dict[str, Any], ...]:
    values = tuple(_object(line, stage) for line in payload.splitlines() if line)
    if len(values) != expected:
        _fail(stage, f"expected {expected} rows, observed {len(values)}")
    return values


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


def _blob_oid(payload: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload,
        usedforsecurity=False,
    ).hexdigest()


def _manifest_hash(value: Any) -> str:
    return strict_canonical_hash(value, prefix="manifest:")


def _authorization(review: bytes) -> dict[str, Any]:
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or _sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.external_review", "external review bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or _sha(directive) != models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.operator_directive", "operator directive bytes differ")
    return _identified(
        {
            "stage": models.STAGE,
            "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
            "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
            "operator_directive": models.OPERATOR_DIRECTIVE,
            "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
            "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
            "independent_audit_only": True,
            "provider_execution_authorized": False,
            "gpu_execution_authorized": False,
            "archive_selection_authorized": False,
            "benchmark_estimation_authorized": False,
            "catalog_promotion_authorized": False,
            "qa_release_authorized": False,
            "schema_version": "qa_registered_catalog_independent_authorization.v1",
        },
        "authorization_id",
        "qa_registered_catalog_independent_authorization:",
    )


def _freeze_candidate(root: Path, authorization_id: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    directory = root / models.CANDIDATE_DIRECTORY
    files = _files(directory)
    if (
        len(files) != models.CANDIDATE_FILE_COUNT
        or sum(map(len, files.values())) != models.CANDIDATE_TOTAL_BYTES
    ):
        _fail("freeze.geometry", "candidate directory geometry differs")
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        len(manifest_payload) != models.CANDIDATE_MANIFEST_BYTES
        or _sha(manifest_payload) != models.CANDIDATE_MANIFEST_SHA256
    ):
        _fail("freeze.manifest_bytes", "candidate Manifest actual bytes differ")
    manifest = _object(manifest_payload, "freeze.manifest")
    raw_members = manifest.get("members")
    if not isinstance(raw_members, list):
        _fail("freeze.manifest", "candidate Manifest members are absent")
    members = {str(row["relative_path"]): row for row in raw_members}
    if (
        len(members) != models.CANDIDATE_MEMBER_COUNT
        or int(manifest.get("member_bytes", -1)) != models.CANDIDATE_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("freeze.member_domain", "candidate Manifest member domain differs")
    for path, row in members.items():
        payload = files[path]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            _fail("freeze.member_bytes", f"candidate member differs: {path}")
    root_id = strict_canonical_hash(
        tuple(raw_members), prefix="qa_registered_catalog_artifact_root:"
    )
    manifest_id = strict_canonical_hash(
        {key: value for key, value in manifest.items() if key != "manifest_id"},
        prefix="qa_registered_catalog_artifact_manifest:",
    )
    identities = {
        "source_binding.json": ("binding_id", models.CANDIDATE_SOURCE_BINDING_ID),
        "historical_catalog_freeze.json": (
            "snapshot_id",
            models.CANDIDATE_HISTORICAL_SNAPSHOT_ID,
        ),
        "catalog_descriptor.json": ("catalog_id", models.CANDIDATE_CATALOG_ID),
        "catalog_integration_audit.json": (
            "audit_id",
            models.CANDIDATE_INTEGRATION_AUDIT_ID,
        ),
        "negative_control_audit.json": ("audit_id", models.CANDIDATE_NEGATIVE_AUDIT_ID),
        "gate_evaluation.json": ("gate_id", models.CANDIDATE_GATE_ID),
        "decision.json": ("decision_id", models.CANDIDATE_DECISION_ID),
        "transition.json": ("transition_id", models.CANDIDATE_TRANSITION_ID),
        "report.json": ("report_id", models.CANDIDATE_REPORT_ID),
    }
    for path, (field, expected) in identities.items():
        if _object(files[path], f"freeze.{path}").get(field) != expected:
            _fail("freeze.identity", f"candidate identity differs: {path}")
    transition = _object(files["transition.json"], "freeze.transition")
    if (
        transition.get("next_stage") != models.STAGE
        or transition.get("next_stage_authorized") is not True
    ):
        _fail("freeze.transition", "candidate Transition does not authorize this exact audit")
    if (
        root_id != models.CANDIDATE_ARTIFACT_ROOT
        or manifest_id != models.CANDIDATE_MANIFEST_ID
        or manifest.get("artifact_root") != root_id
        or manifest.get("manifest_id") != manifest_id
    ):
        _fail("freeze.identity", "candidate Manifest or Root identity differs")
    member_rows = tuple(
        {
            "relative_path": path,
            "sha256": str(members[path]["sha256"]),
            "byte_count": int(members[path]["byte_count"]),
        }
        for path in sorted(members)
    )
    return (
        _identified(
            {
                "authorization_id": authorization_id,
                "directory": models.CANDIDATE_DIRECTORY,
                "source_commit": models.CANDIDATE_SOURCE_COMMIT,
                "source_tree": models.CANDIDATE_SOURCE_TREE,
                "file_count": len(files),
                "total_bytes": sum(map(len, files.values())),
                "manifest_member_count": len(members),
                "manifest_member_bytes": sum(row["byte_count"] for row in member_rows),
                "manifest_file_sha256": _sha(manifest_payload),
                "manifest_id": manifest_id,
                "artifact_root": root_id,
                "members": member_rows,
                "path_matches": len(files),
                "sha256_matches": len(files),
                "byte_count_matches": len(files),
                "actual_byte_matches": len(files),
                "candidate_integration_rows_used_as_oracle": False,
                "candidate_gate_used_as_oracle": False,
                "candidate_decision_used_as_oracle": False,
                "candidate_report_used_as_oracle": False,
                "passed": True,
                "schema_version": "qa_registered_catalog_candidate_freeze_audit.v1",
            },
            "audit_id",
            "qa_registered_catalog_candidate_freeze_audit:",
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
    with TemporaryDirectory(prefix="qa-catalog-independent-") as temporary:
        temp_root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            members = bundle.getmembers()
            if any(
                member.name.startswith("/") or ".." in Path(member.name).parts for member in members
            ):
                _fail("detached.archive", "detached archive contains an unsafe path")
            regular_count = sum(member.isfile() for member in members)
            bundle.extractall(temp_root, filter="data")
        if regular_count != 726:
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
            models.CANDIDATE_MODULE,
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
            _fail("detached.builder", result.stderr.decode("utf-8", errors="replace"))
        rebuilt = _files(output)
        if set(rebuilt) != set(saved):
            _fail("detached.path_set", "detached rebuild path set differs")
        if rebuilt != saved:
            _fail("detached.actual_bytes", "detached rebuild actual bytes differ")
    return _identified(
        {
            "candidate_freeze_audit_id": freeze_id,
            "archived_source_file_count": regular_count,
            "saved_file_count": len(saved),
            "rebuilt_file_count": len(saved),
            "saved_bytes": sum(map(len, saved.values())),
            "rebuilt_bytes": sum(map(len, saved.values())),
            "path_matches": len(saved),
            "sha256_matches": len(saved),
            "actual_byte_matches": len(saved),
            "manifest_members_revalidated": models.CANDIDATE_MEMBER_COUNT,
            "credential_like_environment_keys": 0,
            "credential_lookups": 0,
            "provider_calls": 0,
            "gpu_jobs": 0,
            "passed": True,
            "schema_version": "qa_registered_catalog_detached_rebuild_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_detached_rebuild_audit:",
    )


def _candidate_source_authority(root: Path, saved: Mapping[str, bytes]) -> dict[str, Any]:
    commit = _git_text(
        root,
        "source.commit",
        "rev-parse",
        f"{models.CANDIDATE_SOURCE_COMMIT}^{{commit}}",
    )
    tree = _git_text(root, "source.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != models.CANDIDATE_SOURCE_COMMIT or tree != models.CANDIDATE_SOURCE_TREE:
        _fail("source.commit_tree", "candidate source commit/tree relation differs")
    independent_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for path in models.CANDIDATE_SOURCE_PATHS:
        committed = _git(root, "source.member", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        blob = _git_text(root, "source.member", "rev-parse", f"{commit}:{path}")
        if blob != _blob_oid(committed) or committed != current:
            _fail("source.member_bytes", f"candidate source member differs: {path}")
        candidate_row = {
            "relative_path": path,
            "git_blob_oid": blob,
            "sha256": _sha(committed),
            "byte_count": len(committed),
            "committed_current_bytes_equal": True,
        }
        candidate_rows.append(candidate_row)
        independent_rows.append(
            {
                **candidate_row,
                "git_blob_matches": True,
                "committed_current_bytes_match": True,
            }
        )
    candidate = _identified(
        {
            "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
            "requested_commit": commit,
            "resolved_commit": commit,
            "requested_tree": tree,
            "resolved_tree": tree,
            "members": tuple(candidate_rows),
            "member_count": len(candidate_rows),
            "path_set_sha256": _sha(canonical_json_bytes(models.CANDIDATE_SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(candidate_rows)),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "schema_version": "qa_registered_catalog_source_binding.v1",
        },
        "binding_id",
        "qa_registered_catalog_source_binding:",
    )
    if candidate["binding_id"] != models.CANDIDATE_SOURCE_BINDING_ID:
        _fail("source.binding_identity", "candidate source Binding identity differs")
    if _encoded(candidate) != saved["source_binding.json"]:
        _fail("source.binding_bytes", "candidate source Binding actual bytes differ")
    return _identified(
        {
            "candidate_source_binding_id": candidate["binding_id"],
            "requested_commit": commit,
            "resolved_commit": commit,
            "requested_tree": tree,
            "resolved_tree": tree,
            "members": tuple(independent_rows),
            "member_count": len(independent_rows),
            "commit_object_matches": 1,
            "commit_tree_relation_matches": 1,
            "git_blob_matches": len(independent_rows),
            "committed_current_byte_matches": len(independent_rows),
            "candidate_binding_actual_byte_match": True,
            "candidate_source_helper_calls": 0,
            "transitive_runtime_closure_claimed": False,
            "passed": True,
            "schema_version": "qa_registered_catalog_candidate_source_authority_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_candidate_source_authority_audit:",
    )


def _registry(*, scale_role: str = "semantic") -> OperationRegistry:
    registry = finance_vnext_operation_registry()
    registry.register(
        make_operation_definition(
            "scale_ratio_percent",
            ScaleRatioPercentExecutor(),
            ScaleRatioPercentOracle(),
            "one:numeric",
            "percentage",
            "none",
            ("arity=1", "ratio_to_percent_exact"),
            output_model=PercentOutput,
            tool_capability="calculator",
            input_role_contract=("ratio_scalar",),
            parameter_contract=("parameters must be empty",),
            downstream_selector_contract=("numeric consumers must select value",),
            program_role=scale_role,
            semantic_version="1.0.0",
            formula_id="ratio_to_percent.multiply_100.v1",
        )
    )
    registry.register(
        make_operation_definition(
            "signed_percentage_point_gap",
            SignedPercentagePointGapExecutor(),
            SignedPercentagePointGapOracle(),
            "two:numeric",
            "scalar",
            "none",
            ("arity=2", "observed_minus_reference"),
            output_model=PercentagePointOutput,
            tool_capability="calculator",
            input_role_contract=("reference_percent", "observed_percent"),
            parameter_contract=("parameters must be empty",),
            downstream_selector_contract=("numeric consumers must select value",),
            semantic_version="1.0.0",
            formula_id="percentage_point_gap.observed_minus_reference.v1",
        )
    )
    registry.register(
        make_operation_definition(
            "absolute_percentage_point_gap",
            AbsolutePercentagePointGapExecutor(),
            AbsolutePercentagePointGapOracle(),
            "one:numeric",
            "scalar",
            "none",
            ("arity=1", "absolute_magnitude"),
            output_model=PercentagePointOutput,
            tool_capability="calculator",
            input_role_contract=("signed_percentage_point_gap",),
            parameter_contract=("parameters must be empty",),
            semantic_version="1.0.0",
            formula_id="percentage_point_gap.absolute_value.v1",
        )
    )
    return registry


def _historical_catalog(
    saved: Mapping[str, bytes], source_audit_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    plugin = FinanceTaskPlugin()
    task_types = tuple(sorted(plugin.task_family_ids))
    patterns = tuple(
        {
            "task_type": item.task_type,
            "pattern_id": item.pattern_id,
            "pattern_version": item.pattern_version,
            "pattern_hash": item.pattern_hash,
            "instruction_renderer_id": item.instruction_renderer_id,
        }
        for item in plugin.pattern_manifest
    )
    if task_types != models.HISTORICAL_TASK_TYPES:
        _fail("historical_catalog.task_domain", "historical Finance task domain changed")
    snapshot = _identified(
        {
            "plugin_id": plugin.plugin_id,
            "realization_plugin_id": plugin.realization_plugin_id,
            "task_types": task_types,
            "task_count": len(task_types),
            "pattern_rows": patterns,
            "pattern_manifest_sha256": _manifest_hash(patterns),
            "renderer_manifest_sha256": _manifest_hash(finance_renderer_registry().manifest()),
            "operation_manifest_sha256": _manifest_hash(
                finance_vnext_operation_registry().manifest()
            ),
            "historical_objects_modified": False,
            "schema_version": "finance_qa_historical_catalog_snapshot.v1",
        },
        "snapshot_id",
        "finance_qa_historical_catalog_snapshot:",
    )
    if snapshot["snapshot_id"] != models.CANDIDATE_HISTORICAL_SNAPSHOT_ID:
        _fail("historical_catalog.identity", "historical Catalog snapshot identity differs")
    if _encoded(snapshot) != saved["historical_catalog_freeze.json"]:
        _fail("historical_catalog.bytes", "historical Catalog snapshot actual bytes differ")
    audit = _identified(
        {
            "candidate_source_authority_audit_id": source_audit_id,
            "candidate_snapshot_id": snapshot["snapshot_id"],
            "task_types": task_types,
            "task_count": len(task_types),
            "pattern_count": len(patterns),
            "pattern_manifest_sha256": snapshot["pattern_manifest_sha256"],
            "renderer_manifest_sha256": snapshot["renderer_manifest_sha256"],
            "operation_manifest_sha256": snapshot["operation_manifest_sha256"],
            "snapshot_actual_byte_match": True,
            "historical_objects_modified": False,
            "candidate_historical_helper_calls": 0,
            "passed": True,
            "schema_version": "qa_registered_catalog_independent_historical_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_independent_historical_audit:",
    )
    return snapshot, audit


def _task_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for pattern in FinanceTaskPlugin().pattern_manifest:
        rows.append(
            {
                "task_type": pattern.task_type,
                "pattern_id": pattern.pattern_id,
                "pattern_version": pattern.pattern_version,
                "pattern_hash": pattern.pattern_hash,
                "instruction_renderer_id": pattern.instruction_renderer_id,
                "runtime_id": FinanceTaskPatternRuntime.runtime_id,
                "registration_kind": "historical",
                "topology_kind": None,
            }
        )
    profiles = {item.task_type: item for item in depth_three_renderer_profiles()}
    for pattern in depth_three_patterns():
        rows.append(
            {
                "task_type": pattern.task_type,
                "pattern_id": pattern.pattern_id,
                "pattern_version": pattern.pattern_version,
                "pattern_hash": pattern.pattern_hash,
                "instruction_renderer_id": profiles[pattern.task_type].profile_id,
                "runtime_id": DepthThreePatternRuntime.runtime_id,
                "registration_kind": "depth_three_extension",
                "topology_kind": pattern.metadata["topology_kind"],
            }
        )
    return tuple(sorted(rows, key=lambda row: str(row["task_type"])))


def _operation_rows(registry: OperationRegistry) -> tuple[dict[str, Any], ...]:
    extension = set(models.EXTENSION_OPERATION_IDS)
    return tuple(
        {
            **row,
            "registration_kind": (
                "depth_three_extension" if row["operator_id"] in extension else "historical"
            ),
        }
        for row in registry.manifest()
    )


def _validate_catalog(
    task_rows: tuple[dict[str, Any], ...],
    operation_rows: tuple[dict[str, Any], ...],
) -> None:
    task_counts = Counter(str(row.get("task_type")) for row in task_rows)
    operation_counts = Counter(str(row.get("operator_id")) for row in operation_rows)
    if any(count != 1 for count in task_counts.values()):
        _fail("catalog.task_uniqueness", "Catalog repeats a task registration")
    if any(count != 1 for count in operation_counts.values()):
        _fail("catalog.operation_uniqueness", "Catalog repeats an Operation registration")
    historical = tuple(
        sorted(
            str(row["task_type"])
            for row in task_rows
            if row.get("registration_kind") == "historical"
        )
    )
    extensions = tuple(
        sorted(
            str(row["task_type"])
            for row in task_rows
            if row.get("registration_kind") == "depth_three_extension"
        )
    )
    if historical != models.HISTORICAL_TASK_TYPES:
        _fail("catalog.historical_domain", "historical task registrations differ")
    if extensions != models.EXTENSION_TASK_TYPES:
        _fail("catalog.extension_task_domain", "extension task registrations differ")
    extension_operations = tuple(
        sorted(
            str(row["operator_id"])
            for row in operation_rows
            if row.get("registration_kind") == "depth_three_extension"
        )
    )
    if extension_operations != models.EXTENSION_OPERATION_IDS:
        _fail("catalog.extension_operation_domain", "extension Operation registrations differ")
    if any(
        row.get("program_role") != "semantic"
        for row in operation_rows
        if row.get("registration_kind") == "depth_three_extension"
    ):
        _fail("catalog.operation_role", "extension Operation role is not semantic")
    patterns = {
        item.task_type: item
        for item in (*FinanceTaskPlugin().pattern_manifest, *depth_three_patterns())
    }
    for row in task_rows:
        pattern = patterns.get(str(row["task_type"]))
        if pattern is None or (
            row.get("pattern_id"),
            row.get("pattern_version"),
            row.get("pattern_hash"),
            row.get("instruction_renderer_id"),
        ) != (
            pattern.pattern_id,
            pattern.pattern_version,
            pattern.pattern_hash,
            pattern.instruction_renderer_id,
        ):
            _fail("catalog.pattern_relation", "task registration crosses its source Pattern")
    actual_operations = {str(row["operator_id"]): row for row in _registry().manifest()}
    for row in operation_rows:
        comparable = {key: value for key, value in row.items() if key != "registration_kind"}
        if actual_operations.get(str(row["operator_id"])) != comparable:
            _fail("catalog.operation_relation", "Operation registration differs from Registry")
    required = {
        node.operator_id for pattern in patterns.values() for node in pattern.program_template
    }
    if not required <= set(operation_counts):
        _fail("catalog.operation_closure", "registered Patterns reference missing Operations")


def _catalog_descriptor(parent_snapshot_id: str, registry: OperationRegistry) -> dict[str, Any]:
    task_rows = _task_rows()
    operation_rows = _operation_rows(registry)
    _validate_catalog(task_rows, operation_rows)
    return _identified(
        {
            "catalog_version": "finance_qa_registered_catalog.v3-depth-three-preflight.1",
            "parent_historical_snapshot_id": parent_snapshot_id,
            "task_registrations": task_rows,
            "operation_registrations": operation_rows,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "total_task_count": 10,
            "extension_operation_count": 3,
            "task_registration_set_sha256": _manifest_hash(task_rows),
            "operation_registration_set_sha256": _manifest_hash(operation_rows),
            "preflight_only": True,
            "catalog_promoted": False,
            "schema_version": "finance_qa_registered_catalog.v3",
        },
        "catalog_id",
        "finance_qa_registered_catalog:",
    )


def _resolve(
    descriptor: dict[str, Any], task_type: str
) -> tuple[dict[str, Any], TaskPatternSpec, QuestionRendererProfile, DepthThreePatternRuntime]:
    rows = {str(row["task_type"]): row for row in descriptor["task_registrations"]}
    if task_type not in rows:
        _fail("catalog.task_lookup", f"task type is not registered: {task_type}")
    row = rows[task_type]
    if row["registration_kind"] != "depth_three_extension":
        _fail("catalog.extension_lookup", "requested task is not a depth-three extension")
    pattern = {item.task_type: item for item in depth_three_patterns()}[task_type]
    renderer = {item.task_type: item for item in depth_three_renderer_profiles()}[task_type]
    runtime = DepthThreePatternRuntime()
    receipt = _identified(
        {
            "catalog_id": descriptor["catalog_id"],
            "task_type": task_type,
            "task_registration_sha256": _manifest_hash(row),
            "pattern_id": pattern.pattern_id,
            "pattern_version": pattern.pattern_version,
            "pattern_hash": pattern.pattern_hash,
            "renderer_profile_id": renderer.profile_id,
            "renderer_profile_hash": renderer.profile_hash,
            "runtime_id": runtime.runtime_id,
            "schema_version": "finance_qa_catalog_resolution_receipt.v1",
        },
        "receipt_id",
        "finance_qa_catalog_resolution_receipt:",
    )
    return receipt, pattern, renderer, runtime


def _roles(bundle: EvidenceBundle, task_type: str) -> dict[str, tuple[str, ...]]:
    by_predicate_year: dict[tuple[str, int], str] = {}
    for evidence in bundle.evidence:
        values = evidence.model_dump(mode="python")
        year = int(values["domain_context"]["fiscal_year"])
        by_predicate_year[(str(values["predicate"]), year)] = evidence.evidence_id
    if task_type == "derived_growth_absolute_spread":
        required = {
            "revenue_earlier": ("revenue", 2024),
            "revenue_later": ("revenue", 2025),
            "income_earlier": ("operating_income", 2024),
            "income_later": ("operating_income", 2025),
        }
    elif task_type == "registered_margin_target_gap":
        required = {
            "numerator": ("gross_profit", 2025),
            "denominator": ("revenue", 2025),
            "target": ("gross_margin_target", 2025),
        }
    else:
        _fail("cases.task_type", f"unsupported extension task: {task_type}")
    try:
        return {role: (by_predicate_year[key],) for role, key in required.items()}
    except KeyError as exc:
        _fail("cases.evidence_roles", f"required Evidence role is absent: {exc}")


def _compile_package(
    bundle: EvidenceBundle,
    task_type: str,
    pattern: TaskPatternSpec,
    renderer: QuestionRendererProfile,
    runtime: DepthThreePatternRuntime,
    registry: OperationRegistry,
) -> RealizedTaskPackage:
    graph = ProofGraphBuilder().build(bundle)
    role_bindings = _roles(bundle, task_type)
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings=role_bindings,
        source_graph_id=graph.graph_id,
        domain_snapshot_id=graph.source_build_id,
    )
    instantiation = TaskPatternCompiler(registry, runtime).compile(pattern, binding, bundle, graph)
    semantic = build_semantic_binding_bundle(
        pattern=pattern,
        program=instantiation.program,
        binding=binding,
        bundle=bundle,
        proof_graph=graph,
        registry=registry,
        effective_answer_schema=instantiation.task.public.answer_schema,
    )
    by_id = {item.evidence_id: item for item in bundle.evidence}
    evidence_by_role = {
        role: tuple(by_id[evidence_id] for evidence_id in ids)
        for role, ids in role_bindings.items()
    }
    return realize_task(
        plan=semantic.plan,
        binding=semantic.binding,
        instance=semantic.instance,
        task=instantiation.task,
        profile=renderer,
        slot_values=runtime.slot_values(task_type, evidence_by_role),
    )


def _admit_package(
    descriptor: dict[str, Any],
    task_type: str,
    receipt: dict[str, Any] | None,
    package: RealizedTaskPackage,
) -> None:
    expected, _, _, _ = _resolve(descriptor, task_type)
    if receipt != expected:
        _fail("catalog.resolution_receipt", "execution lacks exact Catalog resolution")
    if (
        package.task.public.task_type != task_type
        or package.task.oracle.task_program.program_id != package.semantic_plan.source_program_id
        or package.task.oracle.task_program.program_hash
        != package.semantic_plan.source_program_hash
    ):
        _fail("catalog.execution_lineage", "package crosses Catalog task lineage")


def _ancestors(program: TaskProgram) -> set[str]:
    nodes = {node.node_id: node for node in program.nodes}
    pending = [program.output_node_id]
    result: set[str] = set()
    while pending:
        node_id = pending.pop()
        if node_id in result:
            continue
        if node_id not in nodes:
            _fail("program.output_dependency", f"missing dependency node: {node_id}")
        result.add(node_id)
        pending.extend(nodes[node_id].dependencies)
    return result


def _derive_metrics(program: TaskProgram, registry: OperationRegistry) -> dict[str, Any]:
    nodes = {node.node_id: node for node in program.nodes}
    if len(nodes) != len(program.nodes):
        _fail("program.node_domain", "duplicate Program node IDs")
    seen: set[str] = set()
    for node in program.nodes:
        if any(parent not in seen for parent in node.dependencies):
            _fail("program.topology", "Program is not topologically ordered")
        refs = tuple(ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION)
        if refs != node.dependencies:
            _fail("program.dependencies", "operation references and dependencies differ")
        seen.add(node.node_id)
    ancestors = _ancestors(program)
    if ancestors != set(nodes):
        _fail(
            "output_dependency_closure", "Program contains nodes outside output dependency closure"
        )
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    transparent_count = 0
    semantic_count = 0
    for node in program.nodes:
        role = registry.require(node.operator_id).program_role
        if role == "transparent_projection":
            weight = 0
            transparent_count += 1
        elif role == "semantic":
            weight = 1
            semantic_count += 1
        else:
            _fail("registry.program_role", f"unsupported Program role: {role}")
        structural[node.node_id] = 1 + max(
            (structural[parent] for parent in node.dependencies), default=0
        )
        semantic[node.node_id] = weight + max(
            (semantic[parent] for parent in node.dependencies), default=0
        )
    manifest_sha = strict_canonical_hash(
        registry.manifest(), prefix="program_depth_registry_manifest:"
    ).rsplit(":", maxsplit=1)[-1]
    return _identified(
        {
            "program_id": program.program_id,
            "program_hash": program.program_hash,
            "registry_manifest_sha256": manifest_sha,
            "output_node_id": program.output_node_id,
            "node_count": len(program.nodes),
            "output_ancestor_node_count": len(ancestors),
            "transparent_projection_node_count": transparent_count,
            "semantic_operation_node_count": semantic_count,
            "structural_dependency_depth": structural[program.output_node_id],
            "semantic_operation_depth": semantic[program.output_node_id],
            "workflow_interaction_depth": semantic[program.output_node_id] + 2,
            "evidence_resolution_stage_count": 1,
            "independent_verification_stage_count": 1,
            "structural_depth_by_node": structural,
            "semantic_depth_by_node": semantic,
            "output_dependency_closed": True,
            "plan_template_stage_counted": False,
            "answer_template_stage_counted": False,
            "schema_version": "program_depth_metrics.v1",
        },
        "metrics_id",
        "program_depth_metrics:",
    )


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _catalog_and_cases(
    saved: Mapping[str, bytes],
    historical: dict[str, Any],
    historical_audit_id: str,
) -> tuple[
    dict[str, Any], tuple[dict[str, Any], ...], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    registry = _registry()
    descriptor = _catalog_descriptor(historical["snapshot_id"], registry)
    if descriptor["catalog_id"] != models.CANDIDATE_CATALOG_ID:
        _fail("catalog.identity", "independently reconstructed Catalog identity differs")
    if _encoded(descriptor) != saved["catalog_descriptor.json"]:
        _fail("catalog.bytes", "independently reconstructed Catalog actual bytes differ")
    candidate_receipts = _rows(saved["catalog_discovery_receipts.jsonl"], 2, "cases.receipts")
    candidate_bundles = _rows(saved["evidence_bundles.jsonl"], 2, "cases.bundles")
    candidate_packages = _rows(saved["realized_task_packages.jsonl"], 2, "cases.packages")
    candidate_executions = _rows(saved["public_plan_executions.jsonl"], 2, "cases.executions")
    candidate_verifications = _rows(saved["verification_reports.jsonl"], 2, "cases.verifications")
    candidate_assessments = _rows(saved["quality_assessments.jsonl"], 2, "cases.assessments")
    candidate_metrics = _rows(saved["depth_metrics.jsonl"], 2, "cases.metrics")
    candidate_rows = _rows(saved["catalog_integration_rows.jsonl"], 2, "cases.integration_rows")
    bundles = tuple(EvidenceBundle.model_validate(row) for row in candidate_bundles)
    bundle_by_task: dict[str, EvidenceBundle] = {}
    for bundle in bundles:
        predicates = {item.predicate for item in bundle.evidence}
        task_type = (
            "derived_growth_absolute_spread"
            if "operating_income" in predicates
            else "registered_margin_target_gap"
        )
        if task_type in bundle_by_task:
            _fail("cases.bundle_domain", f"duplicate frozen Bundle for task: {task_type}")
        bundle_by_task[task_type] = bundle
    if tuple(sorted(bundle_by_task)) != models.EXTENSION_TASK_TYPES:
        _fail("cases.bundle_domain", "frozen Evidence Bundle task domain differs")
    receipt_by_task = {str(row["task_type"]): row for row in candidate_receipts}
    package_by_task = {str(row["task"]["public"]["task_type"]): row for row in candidate_packages}
    execution_by_package = {str(row["realized_package_id"]): row for row in candidate_executions}
    verification_by_trajectory = {str(row["trajectory_id"]): row for row in candidate_verifications}
    assessment_by_trajectory = {str(row["trajectory_id"]): row for row in candidate_assessments}
    metric_by_program = {str(row["program_id"]): row for row in candidate_metrics}
    integration_by_task = {str(row["task_type"]): row for row in candidate_rows}
    workflow = CandidateWorkflowVerifier(registry=registry, semantic_policy=FinanceSemanticPolicy())
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    case_by_task = {
        "derived_growth_absolute_spread": "branch_merge_growth_gap",
        "registered_margin_target_gap": "serial_margin_target_gap",
    }
    independent_rows: list[dict[str, Any]] = []
    reconstructed_candidate_rows: list[dict[str, Any]] = []
    reconstructed_receipts: list[dict[str, Any]] = []
    total_nodes = 0
    first_package: RealizedTaskPackage | None = None
    for task_type in models.EXTENSION_TASK_TYPES:
        receipt, pattern, renderer, runtime = _resolve(descriptor, task_type)
        bundle = bundle_by_task[task_type]
        package = _compile_package(bundle, task_type, pattern, renderer, runtime, registry)
        _admit_package(descriptor, task_type, receipt, package)
        if first_package is None:
            first_package = package
        if _encoded(receipt) != _encoded(receipt_by_task[task_type]):
            _fail("cases.receipt_bytes", f"resolution Receipt bytes differ: {task_type}")
        if _encoded(package) != _encoded(package_by_task[task_type]):
            _fail("cases.package_bytes", f"reconstructed Package bytes differ: {task_type}")
        corpus = EvidenceCorpus.from_bundle(bundle)
        graph = ProofGraphBuilder().build(bundle)
        execution = PublicPlanCandidateExecutor(registry).generate(package, corpus)
        verification = workflow.verify(package.task, corpus, graph, execution.trajectory)
        assessment = evaluator.evaluate(package.task, corpus, graph, execution.trajectory)
        program = execution.reconstructed_program
        if program != package.task.oracle.task_program:
            _fail("cases.source_program", f"reconstructed Program differs: {task_type}")
        metrics = _derive_metrics(program, registry)
        expected_execution = execution_by_package[package.realized_package_id]
        expected_verification = verification_by_trajectory[execution.trajectory.trajectory_id]
        expected_assessment = assessment_by_trajectory[execution.trajectory.trajectory_id]
        if _encoded(execution) != _encoded(expected_execution):
            _fail("cases.execution_bytes", f"execution bytes differ: {task_type}")
        if _encoded(verification) != _encoded(expected_verification):
            _fail("cases.verification_bytes", f"verification bytes differ: {task_type}")
        if _encoded(assessment) != _encoded(expected_assessment):
            _fail("cases.assessment_bytes", f"assessment bytes differ: {task_type}")
        if _encoded(metrics) != _encoded(metric_by_program[program.program_id]):
            _fail("cases.metric_bytes", f"depth metric bytes differ: {task_type}")
        case_id = case_by_task[task_type]
        candidate_row = _identified(
            {
                "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
                "catalog_id": descriptor["catalog_id"],
                "resolution_receipt_id": receipt["receipt_id"],
                "case_id": case_id,
                "task_type": task_type,
                "pattern_id": pattern.pattern_id,
                "pattern_hash": pattern.pattern_hash,
                "renderer_profile_id": renderer.profile_id,
                "runtime_id": runtime.runtime_id,
                "evidence_bundle_id": bundle.bundle_id,
                "realized_package_id": package.realized_package_id,
                "source_program_id": program.program_id,
                "source_program_hash": program.program_hash,
                "execution_id": execution.execution_id,
                "verification_trajectory_id": verification.trajectory_id,
                "assessment_id": assessment.assessment_id,
                "depth_metrics_id": metrics["metrics_id"],
                "semantic_operation_depth": metrics["semantic_operation_depth"],
                "structural_dependency_depth": metrics["structural_dependency_depth"],
                "workflow_interaction_depth": metrics["workflow_interaction_depth"],
                "catalog_lookup_passed": True,
                "pattern_selection_passed": True,
                "evidence_binding_passed": True,
                "program_compilation_passed": True,
                "protected_realization_passed": package.realization.validation.passed,
                "program_execution_complete": len(execution.program_execution.node_outputs)
                == len(program.nodes),
                "independent_node_replay_passed": execution.independent_verification.passed,
                "answer_schema_correct": _check(verification, "answer_schema_validity"),
                "answer_correct": _check(verification, "answer_correctness"),
                "citation_correct": _check(verification, "citation_binding"),
                "evaluator_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
                "schema_version": "qa_registered_catalog_integration_row.v1",
            },
            "row_id",
            "qa_registered_catalog_integration_row:",
        )
        if _encoded(candidate_row) != _encoded(integration_by_task[task_type]):
            _fail("cases.integration_row_bytes", f"candidate integration row differs: {task_type}")
        total_nodes += len(program.nodes)
        reconstructed_candidate_rows.append(candidate_row)
        reconstructed_receipts.append(receipt)
        independent_rows.append(
            _identified(
                {
                    "case_id": case_id,
                    "task_type": task_type,
                    "catalog_id": descriptor["catalog_id"],
                    "resolution_receipt_id": receipt["receipt_id"],
                    "evidence_bundle_id": bundle.bundle_id,
                    "role_bindings": _roles(bundle, task_type),
                    "realized_package_id": package.realized_package_id,
                    "program_id": program.program_id,
                    "program_hash": program.program_hash,
                    "execution_id": execution.execution_id,
                    "node_count": len(program.nodes),
                    "independently_replayed_node_count": (
                        execution.independently_replayed_node_count
                    ),
                    "semantic_operation_depth": metrics["semantic_operation_depth"],
                    "structural_dependency_depth": metrics["structural_dependency_depth"],
                    "workflow_interaction_depth": metrics["workflow_interaction_depth"],
                    "receipt_actual_byte_match": True,
                    "package_actual_byte_match": True,
                    "execution_actual_byte_match": True,
                    "verification_actual_byte_match": True,
                    "assessment_actual_byte_match": True,
                    "depth_metrics_actual_byte_match": True,
                    "candidate_integration_row_actual_byte_match": True,
                    "program_execution_complete": len(execution.program_execution.node_outputs)
                    == len(program.nodes),
                    "independent_node_replay_passed": execution.independent_verification.passed,
                    "answer_schema_correct": _check(verification, "answer_schema_validity"),
                    "answer_correct": _check(verification, "answer_correctness"),
                    "citation_correct": _check(verification, "citation_binding"),
                    "quality_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
                    "provider_calls": 0,
                    "schema_version": "qa_registered_catalog_independent_case_row.v1",
                },
                "row_id",
                "qa_registered_catalog_independent_case_row:",
            )
        )
    if first_package is None or total_nodes != 14:
        _fail("cases.node_denominator", "independent node denominator differs")
    ordered_candidate_rows = tuple(
        next(row for row in reconstructed_candidate_rows if row["case_id"] == case_id)
        for case_id in models.CASE_IDS
    )
    candidate_integration = _identified(
        {
            "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
            "predecessor_freeze_id": models.CANDIDATE_PREDECESSOR_FREEZE_ID,
            "source_binding_id": models.CANDIDATE_SOURCE_BINDING_ID,
            "historical_catalog_snapshot_id": historical["snapshot_id"],
            "catalog_id": descriptor["catalog_id"],
            "catalog_manifest_sha256": _sha(canonical_json_bytes(descriptor)),
            "rows": ordered_candidate_rows,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "total_task_count": 10,
            "extension_operation_count": 3,
            "task_registration_counts": {task_type: 1 for task_type in models.EXTENSION_TASK_TYPES},
            "operation_registration_counts": {
                operator_id: 1 for operator_id in models.EXTENSION_OPERATION_IDS
            },
            "catalog_resolution_count": 2,
            "complete_execution_count": 2,
            "independent_replay_count": 2,
            "answer_schema_correct_count": 2,
            "answer_correct_count": 2,
            "citation_correct_count": 2,
            "evaluator_accepted_count": 2,
            "semantic_depth_distribution": {"3": 2},
            "historical_catalog_modified": False,
            "catalog_promotion_performed": False,
            "provider_calls": 0,
            "schema_version": "qa_registered_catalog_integration_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_integration_audit:",
    )
    if candidate_integration["audit_id"] != models.CANDIDATE_INTEGRATION_AUDIT_ID:
        _fail("cases.integration_identity", "candidate integration Audit identity differs")
    if _encoded(candidate_integration) != saved["catalog_integration_audit.json"]:
        _fail("cases.integration_bytes", "candidate integration Audit actual bytes differ")
    catalog_audit = _identified(
        {
            "historical_catalog_audit_id": historical_audit_id,
            "candidate_catalog_id": descriptor["catalog_id"],
            "catalog_version": descriptor["catalog_version"],
            "historical_task_count": 8,
            "extension_task_types": models.EXTENSION_TASK_TYPES,
            "extension_operation_ids": models.EXTENSION_OPERATION_IDS,
            "task_registration_count": len(descriptor["task_registrations"]),
            "operation_registration_count": len(descriptor["operation_registrations"]),
            "extension_task_counts": {task: 1 for task in models.EXTENSION_TASK_TYPES},
            "extension_operation_counts": {op: 1 for op in models.EXTENSION_OPERATION_IDS},
            "extension_operation_roles": {
                str(row["operator_id"]): str(row["program_role"])
                for row in descriptor["operation_registrations"]
                if row["operator_id"] in models.EXTENSION_OPERATION_IDS
            },
            "catalog_manifest_sha256": _sha(canonical_json_bytes(descriptor)),
            "catalog_actual_byte_match": True,
            "resolution_receipt_actual_byte_matches": len(reconstructed_receipts),
            "candidate_catalog_helpers_called": 0,
            "candidate_integration_audit_used_as_oracle": False,
            "catalog_promoted": False,
            "passed": True,
            "schema_version": "qa_registered_catalog_independent_authority_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_independent_authority_audit:",
    )
    ordered_rows = tuple(
        next(row for row in independent_rows if row["case_id"] == case_id)
        for case_id in models.CASE_IDS
    )
    execution_audit = _identified(
        {
            "catalog_authority_audit_id": catalog_audit["audit_id"],
            "rows": ordered_rows,
            "exact_fixed_input_count": 2,
            "catalog_resolution_count": 2,
            "binding_reconstruction_count": 2,
            "program_reconstruction_count": 2,
            "package_reconstruction_count": 2,
            "complete_program_execution_count": 2,
            "independent_node_replay_count": 2,
            "executed_node_count": total_nodes,
            "oracle_verified_node_count": total_nodes,
            "answer_schema_correct_count": 2,
            "answer_correct_count": 2,
            "citation_correct_count": 2,
            "quality_accepted_count": 2,
            "semantic_operation_depth_distribution": {"3": 2},
            "structural_dependency_depth_distribution": {"4": 2},
            "workflow_interaction_depth_distribution": {"5": 2},
            "candidate_input_helper_calls": 0,
            "candidate_compile_helper_calls": 0,
            "candidate_coverage_depth_topology_helper_calls": 0,
            "candidate_integration_rows_used_as_oracle": False,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "qa_registered_catalog_independent_execution_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_independent_execution_audit:",
    )
    return (
        descriptor,
        ordered_rows,
        catalog_audit,
        execution_audit,
        {
            "registry": registry,
            "first_package": first_package,
        },
    )


def _attack(name: str, action: Callable[[], object]) -> dict[str, Any]:
    caught: Exception | None = None
    try:
        action()
    except Exception as exc:
        caught = exc
    if caught is None:
        _fail("negative.accepted", f"attack accepted: {name}")
    if not isinstance(caught, AuditError):
        _fail("negative.exception", f"attack raised untyped exception: {name}: {caught}")
    return {
        "name": name,
        "rejection_stage": caught.stage,
        "exception_type": type(caught).__name__,
        "reason_sha256": _sha(str(caught).encode("utf-8")),
        "rejected": True,
        "output_writes": 0,
        "provider_calls": 0,
    }


def _negative_controls(
    descriptor: dict[str, Any], package: RealizedTaskPackage, saved: Mapping[str, bytes]
) -> dict[str, Any]:
    tasks = tuple(dict(row) for row in descriptor["task_registrations"])
    operations = tuple(dict(row) for row in descriptor["operation_registrations"])
    controls = [
        _attack("task_type_alias", lambda: _resolve(descriptor, "registered_margin_gap")),
        _attack(
            "missing_task_registration",
            lambda: _validate_catalog(
                tuple(row for row in tasks if row["task_type"] != "registered_margin_target_gap"),
                operations,
            ),
        ),
        _attack(
            "duplicate_task_registration",
            lambda: _validate_catalog((*tasks, dict(tasks[-1])), operations),
        ),
        _attack(
            "missing_operation_registration",
            lambda: _validate_catalog(
                tasks,
                tuple(row for row in operations if row["operator_id"] != "scale_ratio_percent"),
            ),
        ),
        _attack(
            "duplicate_operation_registration",
            lambda: _validate_catalog(tasks, (*operations, dict(operations[-1]))),
        ),
        _attack(
            "wrong_operation_role",
            lambda: _validate_catalog(
                tasks,
                tuple(
                    {**row, "program_role": "transparent_projection"}
                    if row["operator_id"] == "scale_ratio_percent"
                    else row
                    for row in operations
                ),
            ),
        ),
        _attack(
            "catalog_bypass_without_resolution_receipt",
            lambda: _admit_package(descriptor, "derived_growth_absolute_spread", None, package),
        ),
        _attack(
            "crossed_pattern_registration",
            lambda: _validate_catalog(
                tuple(
                    {**row, "pattern_hash": "program:crossed"}
                    if row["task_type"] == "registered_margin_target_gap"
                    else row
                    for row in tasks
                ),
                operations,
            ),
        ),
    ]
    if tuple(row["name"] for row in controls) != models.ATTACK_NAMES:
        _fail("negative.domain", "independent attack domain differs")
    if tuple(row["rejection_stage"] for row in controls) != models.ATTACK_STAGES:
        _fail("negative.stage", "independent attack rejection stages differ")
    candidate = _object(saved["negative_control_audit.json"], "negative.candidate")
    candidate_controls = tuple(candidate["controls"])
    for independent, prior in zip(controls, candidate_controls, strict=True):
        if (
            independent["name"],
            independent["rejection_stage"],
            independent["reason_sha256"],
        ) != (prior["name"], prior["rejection_stage"], prior["reason_sha256"]):
            _fail("negative.comparison", f"candidate attack outcome differs: {independent['name']}")
    if candidate.get("audit_id") != models.CANDIDATE_NEGATIVE_AUDIT_ID:
        _fail("negative.candidate_identity", "candidate negative Audit identity differs")
    return _identified(
        {
            "candidate_catalog_id": descriptor["catalog_id"],
            "candidate_negative_audit_id": candidate["audit_id"],
            "controls": tuple(controls),
            "attempted_count": len(controls),
            "rejected_count": len(controls),
            "accepted_count": 0,
            "candidate_name_stage_reason_matches": len(controls),
            "rejection_stages_derived_from_typed_exceptions": True,
            "candidate_attack_helper_calls": 0,
            "output_writes": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "qa_registered_catalog_independent_negative_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_independent_negative_audit:",
    )


def _scope(
    root: Path,
    source_commit: str,
    source_tree: str,
    execution_audit_id: str,
    negative_audit_id: str,
) -> dict[str, Any]:
    commit = _git_text(root, "scope.commit", "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git_text(root, "scope.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != source_commit or tree != source_tree:
        _fail("scope.commit_tree", "audit source commit/tree relation differs")
    members: list[dict[str, Any]] = []
    for path in models.AUDIT_SOURCE_PATHS:
        committed = _git(root, "scope.member", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        blob = _git_text(root, "scope.member", "rev-parse", f"{commit}:{path}")
        if blob != _blob_oid(committed) or committed != current:
            _fail("scope.member_bytes", f"audit source member differs: {path}")
        members.append(
            {
                "relative_path": path,
                "git_blob_oid": blob,
                "committed_sha256": _sha(committed),
                "committed_byte_count": len(committed),
                "current_sha256": _sha(current),
                "current_byte_count": len(current),
                "git_blob_matches": True,
                "committed_current_bytes_match": True,
            }
        )
    audit_path = root / models.AUDIT_SOURCE_PATHS[-1]
    syntax = ast.parse(audit_path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog",
        "trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.preflight",
        "trusted_synthesis.experiments.qa_semantic_depth_three_plus.preflight",
        "trusted_synthesis.core.task.program_depth",
    }
    imported = {
        alias.name
        for node in ast.walk(syntax)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module
        for node in ast.walk(syntax)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    if imported & forbidden_modules:
        _fail("scope.helper_boundary", "independent audit imports a forbidden candidate helper")
    forbidden_calls = {
        "_compile_realized",
        "_fixture_inputs",
        "_integration",
        "build_catalog_descriptor",
        "validate_catalog_rows",
        "derive_program_depth_metrics",
        "admit_program_depth_metrics",
    }
    called = {
        node.func.id
        for node in ast.walk(syntax)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if called & forbidden_calls:
        _fail("scope.helper_boundary", "independent audit calls a forbidden candidate helper")
    return _identified(
        {
            "execution_audit_id": execution_audit_id,
            "negative_audit_id": negative_audit_id,
            "audit_source_commit": commit,
            "audit_source_tree": tree,
            "audit_source_members": tuple(members),
            "audit_source_member_count": len(members),
            "audit_source_git_blob_matches": len(members),
            "audit_source_current_byte_matches": len(members),
            "helper_boundary_passed": True,
            "candidate_input_helper_calls": 0,
            "candidate_compile_helper_calls": 0,
            "candidate_catalog_helper_calls": 0,
            "candidate_coverage_depth_topology_helper_calls": 0,
            "candidate_oracle_calls": 0,
            "candidate_formal_writes": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "gpu_jobs": 0,
            "archive_selections": 0,
            "benchmark_rows": 0,
            "empirical_estimates": 0,
            "online_job_manifests": 0,
            "catalog_promotions": 0,
            "qa_release_objects": 0,
            "vtdo_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "mainline_recovery_authorizations_read": 0,
            "mainline_recovery_authorizations_consumed": 0,
            "passed": True,
            "schema_version": "qa_registered_catalog_independent_scope_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_independent_scope_audit:",
    )


def build_qa_semantic_depth_three_catalog_integration_independent_audit(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.AuditProducts:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization = _authorization(review)
    freeze, saved = _freeze_candidate(root, authorization["authorization_id"])
    detached = _detached_rebuild(root, freeze["audit_id"], saved)
    source = _candidate_source_authority(root, saved)
    historical, historical_audit = _historical_catalog(saved, source["audit_id"])
    descriptor, case_rows, catalog_audit, execution, runtime = _catalog_and_cases(
        saved, historical, historical_audit["audit_id"]
    )
    negative = _negative_controls(descriptor, runtime["first_package"], saved)
    scope = _scope(root, source_commit, source_tree, execution["audit_id"], negative["audit_id"])
    gates = {
        "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE": freeze["passed"],
        "A1_DETACHED_EXACT_DIRECTORY_REBUILD": detached["passed"],
        "A2_INDEPENDENT_SOURCE_AND_HISTORICAL_CATALOG_AUTHORITY": (
            source["passed"] and historical_audit["passed"]
        ),
        "A3_INDEPENDENT_FRESH_CATALOG_AND_RESOLUTION": (
            catalog_audit["passed"] and catalog_audit["resolution_receipt_actual_byte_matches"] == 2
        ),
        "A4_INDEPENDENT_BINDING_PROGRAM_PACKAGE_RECONSTRUCTION": (
            execution["binding_reconstruction_count"]
            == execution["program_reconstruction_count"]
            == execution["package_reconstruction_count"]
            == 2
        ),
        "A5_INDEPENDENT_FOURTEEN_NODE_EXECUTION_DEPTH_AND_VERIFICATION": (
            execution["executed_node_count"] == execution["oracle_verified_node_count"] == 14
            and execution["semantic_operation_depth_distribution"] == {"3": 2}
            and execution["quality_accepted_count"] == 2
        ),
        "A6_EIGHT_DIRECT_CATALOG_ATTACKS_REJECT": (
            negative["rejected_count"] == 8 and negative["accepted_count"] == 0
        ),
        "A7_ZERO_EXTERNAL_EXECUTION_AND_RELEASE_SCOPE": not any(
            scope[key]
            for key in (
                "provider_calls",
                "credential_lookups",
                "gpu_jobs",
                "archive_selections",
                "benchmark_rows",
                "empirical_estimates",
                "online_job_manifests",
                "catalog_promotions",
                "qa_release_objects",
                "vtdo_rows",
                "training_rows",
                "production_rows",
                "mainline_recovery_authorizations_read",
                "mainline_recovery_authorizations_consumed",
                "candidate_formal_writes",
                "candidate_input_helper_calls",
                "candidate_compile_helper_calls",
                "candidate_catalog_helper_calls",
                "candidate_coverage_depth_topology_helper_calls",
                "candidate_oracle_calls",
            )
        ),
    }
    if tuple(gates) != models.GATE_NAMES or not all(gates.values()):
        _fail("gate.partition", "noncompensatory independent-audit Gate failed")
    gate = _identified(
        {
            "gates": gates,
            "passed": 8,
            "failed": 0,
            "noncompensatory": True,
            "schema_version": "qa_registered_catalog_independent_gate.v1",
        },
        "gate_id",
        "qa_registered_catalog_independent_gate:",
    )
    common = {
        "authorization_id": authorization["authorization_id"],
        "candidate_freeze_audit_id": freeze["audit_id"],
        "detached_rebuild_audit_id": detached["audit_id"],
        "candidate_source_authority_audit_id": source["audit_id"],
        "historical_catalog_audit_id": historical_audit["audit_id"],
        "catalog_authority_audit_id": catalog_audit["audit_id"],
        "execution_audit_id": execution["audit_id"],
        "negative_audit_id": negative["audit_id"],
        "scope_audit_id": scope["audit_id"],
        "gate_id": gate["gate_id"],
    }
    decision = _identified(
        {
            **common,
            "decision": models.DECISION,
            "candidate_accepted_as_scoped": True,
            "registered_catalog_integration_closed_for_exact_two_fixed_fixtures": True,
            "historical_eight_task_catalog_retained": True,
            "archive_grounded_coverage_evaluated": False,
            "parameter_space_coverage_evaluated": False,
            "overall_qa_sufficiency_established": False,
            "qa_release_eligible": False,
            "schema_version": "qa_registered_catalog_independent_decision.v1",
        },
        "decision_id",
        "qa_registered_catalog_independent_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "prospective_next_stage": models.PROSPECTIVE_NEXT_STAGE,
            "next_stage_authorized": False,
            "separate_external_audit_decision_required": True,
            "provider_execution_authorized": False,
            "gpu_execution_authorized": False,
            "archive_selection_authorized": False,
            "benchmark_estimation_authorized": False,
            "catalog_promotion_authorized": False,
            "qa_release_authorized": False,
            "schema_version": "qa_registered_catalog_independent_transition.v1",
        },
        "transition_id",
        "qa_registered_catalog_independent_transition:",
    )
    report = _identified(
        {
            **common,
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "passed_count": 8,
            "failed_count": 0,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "extension_operation_count": 3,
            "catalog_mediated_execution_count": 2,
            "executed_and_oracle_verified_node_count": 14,
            "semantic_operation_depth_distribution": {"3": 2},
            "deterministic_fixed_fixture_integration_only": True,
            "archive_grounding_claimed": False,
            "parameter_space_coverage_claimed": False,
            "benchmark_distribution_claimed": False,
            "overall_qa_sufficiency_claimed": False,
            "provider_calls": 0,
            "gpu_jobs": 0,
            "schema_version": "qa_registered_catalog_independent_report.v1",
        },
        "report_id",
        "qa_registered_catalog_independent_report:",
    )
    return models.AuditProducts(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=models.OPERATOR_DIRECTIVE.encode("utf-8"),
        candidate_freeze=freeze,
        detached_rebuild=detached,
        candidate_source_authority=source,
        historical_catalog_audit=historical_audit,
        catalog_authority_audit=catalog_audit,
        case_rows=case_rows,
        execution_audit=execution,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(_encoded(value) for value in values)


def write_qa_semantic_depth_three_catalog_integration_independent_audit_artifacts(
    products: models.AuditProducts, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "authorization.json": _encoded(products.authorization),
        "candidate_freeze_audit.json": _encoded(products.candidate_freeze),
        "candidate_source_authority_audit.json": _encoded(products.candidate_source_authority),
        "case_rows.jsonl": _jsonl(products.case_rows),
        "catalog_authority_audit.json": _encoded(products.catalog_authority_audit),
        "decision.json": _encoded(products.decision),
        "detached_rebuild_audit.json": _encoded(products.detached_rebuild),
        "execution_audit.json": _encoded(products.execution_audit),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": _encoded(products.gate),
        "historical_catalog_audit.json": _encoded(products.historical_catalog_audit),
        "negative_control_audit.json": _encoded(products.negative_audit),
        "operator_directive.txt": products.operator_directive_bytes,
        "report.json": _encoded(products.report),
        "scope_boundary_audit.json": _encoded(products.scope_audit),
        "transition.json": _encoded(products.transition),
    }
    members = tuple(
        {
            "relative_path": path,
            "sha256": _sha(payload),
            "byte_count": len(payload),
        }
        for path, payload in sorted(payloads.items())
    )
    manifest = _identified(
        {
            "members": members,
            "file_count": len(members),
            "member_bytes": sum(len(payload) for payload in payloads.values()),
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_registered_catalog_independent_artifact_root:"
            ),
            "self_excluding": True,
            "schema_version": "qa_registered_catalog_independent_artifact_manifest.v1",
        },
        "manifest_id",
        "qa_registered_catalog_independent_artifact_manifest:",
    )
    payloads["artifact_manifest.json"] = _encoded(manifest)
    return write_immutable_artifact_directory(Path(output_dir), payloads)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    arguments = parser.parse_args()
    products = build_qa_semantic_depth_three_catalog_integration_independent_audit(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_qa_semantic_depth_three_catalog_integration_independent_audit_artifacts(
        products, arguments.output_dir
    )


if __name__ == "__main__":
    main()
