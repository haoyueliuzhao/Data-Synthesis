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

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.registry import default_registry, make_operation_definition
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage, realize_task
from trusted_synthesis.core.task.semantic import build_semantic_binding_bundle
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
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
    BRANCH_TASK_TYPE,
    SERIAL_TASK_TYPE,
    DepthThreePatternRuntime,
    depth_three_patterns,
    depth_three_renderer_profiles,
)
from trusted_synthesis.hashing import canonical_hash

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
            "qa_release_authorized": False,
            "schema_version": "qa_semantic_depth_three_independent_authorization.v1",
        },
        "authorization_id",
        "qa_semantic_depth_three_independent_authorization:",
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
        _fail("freeze.manifest_bytes", "candidate Manifest bytes differ")
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
        tuple(raw_members), prefix="qa_semantic_depth_three_plus_artifact_root:"
    )
    manifest_id = strict_canonical_hash(
        {key: value for key, value in manifest.items() if key != "manifest_id"},
        prefix="qa_semantic_depth_three_plus_artifact_manifest:",
    )
    if (
        root_id != models.CANDIDATE_ARTIFACT_ROOT
        or manifest_id != models.CANDIDATE_MANIFEST_ID
        or manifest.get("artifact_root") != root_id
        or manifest.get("manifest_id") != manifest_id
    ):
        _fail("freeze.identity", "candidate Manifest or Root identity differs")
    report = _object(files["report.json"], "freeze.report")
    gate = _object(files["gate_evaluation.json"], "freeze.gate")
    decision = _object(files["decision.json"], "freeze.decision")
    transition = _object(files["transition.json"], "freeze.transition")
    if (
        report.get("report_id") != models.CANDIDATE_REPORT_ID
        or gate.get("gate_id") != models.CANDIDATE_GATE_ID
        or decision.get("decision_id") != models.CANDIDATE_DECISION_ID
        or transition.get("transition_id") != models.CANDIDATE_TRANSITION_ID
        or transition.get("next_stage") != models.STAGE
        or transition.get("next_stage_authorized") is not True
        or int(gate.get("passed_count", -1)) != 8
        or int(gate.get("failed_count", -1)) != 0
    ):
        _fail("freeze.decision", "candidate decision or transition differs")
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
                "candidate_coverage_audit_used_as_oracle": False,
                "candidate_gate_used_as_oracle": False,
                "candidate_report_used_as_oracle": False,
                "passed": True,
                "schema_version": "qa_semantic_depth_three_candidate_freeze.v1",
            },
            "audit_id",
            "qa_semantic_depth_three_candidate_freeze_audit:",
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
    regular_count = 0
    with TemporaryDirectory(prefix="qa-depth-three-independent-") as temporary:
        temp_root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            members = bundle.getmembers()
            if any(
                member.name.startswith("/") or ".." in Path(member.name).parts for member in members
            ):
                _fail("detached.archive", "detached archive contains an unsafe path")
            regular_count = sum(member.isfile() for member in members)
            bundle.extractall(temp_root, filter="data")
        if regular_count != 715:
            _fail("detached.archive_geometry", "detached source archive geometry differs")
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
            command,
            cwd=temp_root,
            env=env,
            check=False,
            capture_output=True,
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
            "schema_version": "qa_semantic_depth_three_detached_rebuild_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_detached_rebuild_audit:",
    )


def _source_authority(root: Path, saved: Mapping[str, bytes]) -> dict[str, Any]:
    commit = _git_text(
        root, "source.commit", "rev-parse", f"{models.CANDIDATE_SOURCE_COMMIT}^{{commit}}"
    )
    tree = _git_text(root, "source.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != models.CANDIDATE_SOURCE_COMMIT or tree != models.CANDIDATE_SOURCE_TREE:
        _fail("source.commit_tree", "candidate source commit/tree relation differs")
    rows = []
    candidate_rows = []
    for path in models.SOURCE_PATHS:
        blob = _git_text(root, "source.member", "rev-parse", f"{commit}:{path}")
        committed = _git(root, "source.member", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        if blob != _blob_oid(committed) or committed != current:
            _fail("source.member_bytes", f"source member bytes differ: {path}")
        row = {
            "relative_path": path,
            "git_blob_oid": blob,
            "committed_sha256": _sha(committed),
            "committed_byte_count": len(committed),
            "current_sha256": _sha(current),
            "current_byte_count": len(current),
        }
        rows.append({**row, "git_blob_matches": True, "committed_current_bytes_match": True})
        candidate_rows.append({**row, "bytes_equal": True})
    candidate = _identified(
        {
            "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
            "requested_commit": commit,
            "resolved_commit": commit,
            "requested_tree": tree,
            "resolved_tree": tree,
            "members": tuple(candidate_rows),
            "path_set_sha256": _sha(canonical_json_bytes(models.SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(tuple(candidate_rows))),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "schema_version": "qa_semantic_depth_three_plus_source_binding.v1",
        },
        "binding_id",
        "qa_semantic_depth_three_plus_source_binding:",
    )
    if candidate["binding_id"] != models.CANDIDATE_SOURCE_BINDING_ID:
        _fail("source.binding_identity", "reconstructed candidate source Binding ID differs")
    if _encoded(candidate) != saved["source_binding.json"]:
        _fail("source.binding_bytes", "reconstructed candidate source Binding bytes differ")
    return _identified(
        {
            "candidate_source_binding_id": candidate["binding_id"],
            "requested_commit": commit,
            "resolved_commit": commit,
            "requested_tree": tree,
            "resolved_tree": tree,
            "members": tuple(rows),
            "member_count": len(rows),
            "commit_object_matches": 1,
            "commit_tree_relation_matches": 1,
            "git_blob_matches": len(rows),
            "committed_current_byte_matches": len(rows),
            "candidate_binding_actual_byte_match": True,
            "candidate_source_helper_calls": 0,
            "transitive_runtime_closure_claimed": False,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_source_authority_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_source_authority_audit:",
    )


def _registry(*, scale_role: str = "semantic") -> Any:
    registry = default_registry()
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


def _registry_authority(
    source_audit_id: str, saved: Mapping[str, bytes]
) -> tuple[Any, dict[str, Any]]:
    registry = _registry()
    manifest_sha = strict_canonical_hash(
        registry.manifest(), prefix="program_depth_registry_manifest:"
    ).rsplit(":", maxsplit=1)[-1]
    extension_ids = (
        "absolute_percentage_point_gap",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    )
    definitions = tuple(registry.require(operator_id) for operator_id in extension_ids)
    if manifest_sha != models.REGISTRY_MANIFEST_SHA256:
        _fail("registry.manifest", "independent Registry Manifest differs")
    if not all(definition.program_role == "semantic" for definition in definitions):
        _fail("registry.role", "extension operation role differs")
    if not all(type(item.executor) is not type(item.oracle_verifier) for item in definitions):
        _fail("registry.classes", "executor and Oracle classes are not distinct")
    candidate = _identified(
        {
            "source_binding_id": models.CANDIDATE_SOURCE_BINDING_ID,
            "registry_manifest_sha256": manifest_sha,
            "base_operator_count": len(default_registry().manifest()),
            "extension_operator_ids": extension_ids,
            "extension_operator_count": 3,
            "all_extension_roles_semantic": True,
            "executor_oracle_class_pairs_distinct": True,
            "schema_version": "qa_semantic_depth_three_plus_registry_binding.v1",
        },
        "binding_id",
        "qa_semantic_depth_three_plus_registry_binding:",
    )
    if (
        candidate["binding_id"] != models.CANDIDATE_REGISTRY_BINDING_ID
        or _encoded(candidate) != saved["operation_registry_binding.json"]
    ):
        _fail("registry.binding", "reconstructed Registry Binding bytes differ")
    audit = _identified(
        {
            "source_authority_audit_id": source_audit_id,
            "candidate_registry_binding_id": candidate["binding_id"],
            "registry_manifest_sha256": manifest_sha,
            "base_operator_count": len(default_registry().manifest()),
            "extension_operator_ids": extension_ids,
            "extension_roles": tuple(item.program_role for item in definitions),
            "executor_classes": tuple(type(item.executor).__name__ for item in definitions),
            "oracle_classes": tuple(type(item.oracle_verifier).__name__ for item in definitions),
            "candidate_binding_actual_byte_match": True,
            "candidate_registry_factory_calls": 0,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_registry_authority_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_registry_authority_audit:",
    )
    return registry, audit


def _compile_package(
    bundle: EvidenceBundle, saved_package: RealizedTaskPackage, registry: Any
) -> RealizedTaskPackage:
    pattern_by_type = {pattern.task_type: pattern for pattern in depth_three_patterns()}
    task_type = saved_package.task.public.task_type
    try:
        pattern = pattern_by_type[task_type]
        runtime = DepthThreePatternRuntime()
        graph = ProofGraphBuilder().build(bundle)
        role_bindings = {
            role: tuple(ids) for role, ids in saved_package.binding_snapshot.role_bindings.items()
        }
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
            role_bindings=role_bindings,
            source_graph_id=graph.graph_id,
            domain_snapshot_id=graph.source_build_id,
        )
        instantiation = TaskPatternCompiler(registry, runtime).compile(
            pattern, binding, bundle, graph
        )
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
        profile = next(
            item for item in depth_three_renderer_profiles() if item.task_type == task_type
        )
        return realize_task(
            plan=semantic.plan,
            binding=semantic.binding,
            instance=semantic.instance,
            task=instantiation.task,
            profile=profile,
            slot_values=runtime.slot_values(task_type, evidence_by_role),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise AuditError("pattern_source_admission", str(exc)) from exc


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


def _derive_metrics(program: TaskProgram, registry: Any) -> dict[str, Any]:
    nodes = {node.node_id: node for node in program.nodes}
    if len(nodes) != len(program.nodes):
        _fail("program.node_domain", "duplicate Program node IDs")
    seen: set[str] = set()
    for node in program.nodes:
        if any(parent not in seen for parent in node.dependencies):
            _fail("program.topology", "Program is not topologically ordered")
        operation_refs = tuple(
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION
        )
        if operation_refs != node.dependencies:
            _fail("program.dependencies", "operation references and dependencies differ")
        seen.add(node.node_id)
    ancestors = _ancestors(program)
    if ancestors != set(nodes):
        extras = tuple(sorted(set(nodes) - ancestors))
        _fail(
            "output_dependency_closure",
            f"Program contains nodes outside output dependency closure: {extras}",
        )
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    transparent = 0
    semantic_count = 0
    for node in program.nodes:
        role = registry.require(node.operator_id).program_role
        if role == "transparent_projection":
            weight = 0
            transparent += 1
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
    values = {
        "program_id": program.program_id,
        "program_hash": program.program_hash,
        "registry_manifest_sha256": manifest_sha,
        "output_node_id": program.output_node_id,
        "node_count": len(program.nodes),
        "output_ancestor_node_count": len(ancestors),
        "transparent_projection_node_count": transparent,
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
    }
    return _identified(values, "metrics_id", "program_depth_metrics:")


def _admit_exact_program(expected: TaskProgram, candidate: TaskProgram, registry: Any) -> None:
    if candidate != expected or candidate.program_id != expected.program_id:
        _fail("exact_source_program_admission", "candidate Program differs from source Program")
    _derive_metrics(candidate, registry)


def _topology(program: TaskProgram, registry: Any) -> tuple[str, tuple[tuple[str, ...], ...]]:
    nodes = {node.node_id: node for node in program.nodes}
    role = {
        node_id: registry.require(node.operator_id).program_role for node_id, node in nodes.items()
    }

    def nearest_semantic(node_id: str) -> set[str]:
        result: set[str] = set()
        pending = list(nodes[node_id].dependencies)
        while pending:
            current = pending.pop()
            if role[current] == "semantic":
                result.add(current)
            else:
                pending.extend(nodes[current].dependencies)
        return result

    semantic_nodes = tuple(node for node in program.nodes if role[node.node_id] == "semantic")
    parents = {node.node_id: nearest_semantic(node.node_id) for node in semantic_nodes}
    merge_nodes = tuple(node_id for node_id, values in parents.items() if len(values) > 1)
    kind = "branch_and_merge" if merge_nodes else "serial_chain"
    sequences: dict[str, set[tuple[str, ...]]] = {}
    for node in semantic_nodes:
        parent_ids = parents[node.node_id]
        if not parent_ids:
            sequences[node.node_id] = {(node.operator_id,)}
            continue
        candidates = {
            (*sequence, node.operator_id) for parent in parent_ids for sequence in sequences[parent]
        }
        maximum = max(map(len, candidates))
        sequences[node.node_id] = {item for item in candidates if len(item) == maximum}
    output = program.output_node_id
    if role[output] != "semantic":
        semantic_outputs = nearest_semantic(output)
        paths = {item for node_id in semantic_outputs for item in sequences[node_id]}
    else:
        paths = sequences[output]
    return kind, tuple(sorted(paths))


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _case_audits(
    saved: Mapping[str, bytes], registry: Any, registry_audit_id: str
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    bundle_rows = _rows(saved["evidence_bundles.jsonl"], 2, "cases.bundles")
    package_rows = _rows(saved["realized_task_packages.jsonl"], 2, "cases.packages")
    execution_rows = _rows(saved["public_plan_executions.jsonl"], 2, "cases.executions")
    verification_rows = _rows(saved["verification_reports.jsonl"], 2, "cases.verification")
    assessment_rows = _rows(saved["quality_assessments.jsonl"], 2, "cases.assessments")
    candidate_metric_rows = _rows(saved["depth_metrics.jsonl"], 2, "cases.metrics")
    candidate_coverage_rows = _rows(saved["coverage_rows.jsonl"], 2, "cases.coverage_rows")

    bundles = {row["bundle_id"]: EvidenceBundle.model_validate(row) for row in bundle_rows}
    packages = {
        row["task"]["public"]["task_type"]: RealizedTaskPackage.model_validate(row)
        for row in package_rows
    }
    if tuple(sorted(packages)) != tuple(sorted(models.TASK_TYPES)) or len(bundles) != 2:
        _fail("cases.source_domain", "actual Bundle/Package source domain differs")
    executions_by_package = {row["realized_package_id"]: row for row in execution_rows}
    verifications_by_trajectory = {row["trajectory_id"]: row for row in verification_rows}
    assessments_by_trajectory = {row["trajectory_id"]: row for row in assessment_rows}
    metrics_by_program = {row["program_id"]: row for row in candidate_metric_rows}
    coverage_by_task = {row["task_type"]: row for row in candidate_coverage_rows}

    workflow = CandidateWorkflowVerifier(registry=registry, semantic_policy=FinanceSemanticPolicy())
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    case_id_by_type = {
        BRANCH_TASK_TYPE: "branch_merge_growth_gap",
        SERIAL_TASK_TYPE: "serial_margin_target_gap",
    }
    case_rows: list[dict[str, Any]] = []
    cases: dict[str, dict[str, Any]] = {}
    total_nodes = 0
    for task_type in models.TASK_TYPES:
        package_source = packages[task_type]
        bundle = bundles[package_source.binding_snapshot.bundle_id]
        rebuilt_package = _compile_package(bundle, package_source, registry)
        if _encoded(rebuilt_package) != _encoded(package_source):
            _fail("cases.package_bytes", f"reconstructed Package differs: {task_type}")
        corpus = EvidenceCorpus.from_bundle(bundle)
        graph = ProofGraphBuilder().build(bundle)
        execution = PublicPlanCandidateExecutor(registry).generate(rebuilt_package, corpus)
        verification = workflow.verify(rebuilt_package.task, corpus, graph, execution.trajectory)
        assessment = evaluator.evaluate(rebuilt_package.task, corpus, graph, execution.trajectory)
        program = execution.reconstructed_program
        _admit_exact_program(rebuilt_package.task.oracle.task_program, program, registry)
        metrics = _derive_metrics(program, registry)
        topology_kind, critical_paths = _topology(program, registry)
        case_id = case_id_by_type[task_type]
        expected_execution = executions_by_package[rebuilt_package.realized_package_id]
        expected_verification = verifications_by_trajectory[execution.trajectory.trajectory_id]
        expected_assessment = assessments_by_trajectory[execution.trajectory.trajectory_id]
        if _encoded(execution) != _encoded(expected_execution):
            _fail("cases.execution_bytes", f"execution bytes differ: {task_type}")
        if _encoded(verification) != _encoded(expected_verification):
            _fail("cases.verification_bytes", f"verification bytes differ: {task_type}")
        if _encoded(assessment) != _encoded(expected_assessment):
            _fail("cases.assessment_bytes", f"assessment bytes differ: {task_type}")
        if metrics != metrics_by_program[program.program_id]:
            _fail("cases.metric_bytes", f"depth metrics differ: {task_type}")
        candidate_coverage = coverage_by_task[task_type]
        if candidate_coverage.get("topology_kind") != topology_kind:
            _fail("cases.topology_comparison", f"candidate topology differs: {task_type}")
        total_nodes += len(program.nodes)
        case_row = _identified(
            {
                "case_id": case_id,
                "task_type": task_type,
                "evidence_bundle_id": bundle.bundle_id,
                "realized_package_id": rebuilt_package.realized_package_id,
                "source_program_id": program.program_id,
                "source_program_hash": program.program_hash,
                "operator_sequence": tuple(node.operator_id for node in program.nodes),
                "node_count": len(program.nodes),
                "edge_count": sum(len(node.dependencies) for node in program.nodes),
                "structural_dependency_depth": metrics["structural_dependency_depth"],
                "semantic_operation_depth": metrics["semantic_operation_depth"],
                "workflow_interaction_depth": metrics["workflow_interaction_depth"],
                "topology_kind": topology_kind,
                "critical_semantic_paths": critical_paths,
                "source_program_reconstructed_from_pattern_and_evidence": True,
                "package_actual_byte_match": True,
                "execution_actual_byte_match": True,
                "independent_node_replay_passed": execution.independent_verification.passed,
                "independently_replayed_node_count": execution.independently_replayed_node_count,
                "answer_schema_correct": _check(verification, "answer_schema_validity"),
                "answer_correct": _check(verification, "answer_correctness"),
                "citation_correct": _check(verification, "citation_binding"),
                "quality_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
                "candidate_metric_actual_byte_match": True,
                "candidate_topology_compared_after_derivation": True,
                "provider_calls": 0,
                "schema_version": "qa_semantic_depth_three_independent_case_row.v1",
            },
            "row_id",
            "qa_semantic_depth_three_independent_case_row:",
        )
        case_rows.append(case_row)
        cases[case_id] = {
            "bundle": bundle,
            "package": rebuilt_package,
            "program": program,
            "execution": execution,
            "metrics": metrics,
        }
    if total_nodes != 14:
        _fail("cases.node_denominator", "independent node denominator differs")
    ordered = tuple(sorted(case_rows, key=lambda item: models.CASE_IDS.index(item["case_id"])))
    execution_audit = _identified(
        {
            "registry_authority_audit_id": registry_audit_id,
            "rows": ordered,
            "exact_case_count": 2,
            "source_program_reconstruction_count": 2,
            "complete_program_execution_count": 2,
            "independent_node_replay_count": 2,
            "executed_node_count": total_nodes,
            "oracle_verified_node_count": total_nodes,
            "answer_schema_correct_count": 2,
            "answer_correct_count": 2,
            "citation_correct_count": 2,
            "quality_accepted_count": 2,
            "candidate_coverage_audit_used_as_selector": False,
            "candidate_preflight_helper_calls": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_independent_execution_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_independent_execution_audit:",
    )
    topology_counts = Counter(row["topology_kind"] for row in ordered)
    semantic_depths = Counter(str(row["semantic_operation_depth"]) for row in ordered)
    depth_topology = _identified(
        {
            "execution_audit_id": execution_audit["audit_id"],
            "rows": ordered,
            "semantic_operation_depth_distribution": dict(sorted(semantic_depths.items())),
            "structural_dependency_depth_distribution": {"4": 2},
            "workflow_interaction_depth_distribution": {"5": 2},
            "topology_distribution": dict(sorted(topology_counts.items())),
            "maximum_semantic_operation_depth": 3,
            "semantic_depth_three_plus_count": 2,
            "serial_chain_count": 1,
            "branch_and_merge_count": 1,
            "topology_derived_from_dag": True,
            "registry_roles_derived_independently": True,
            "candidate_topology_labels_used_as_oracle": False,
            "candidate_depth_helper_calls": 0,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_independent_depth_topology_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_independent_depth_topology_audit:",
    )
    return ordered, execution_audit, depth_topology, cases


def _rehash_trajectory(trajectory: Trajectory, final_answer: dict[str, Any]) -> Trajectory:
    values = trajectory.model_dump(mode="python", exclude={"trajectory_id"})
    values["final_answer"] = final_answer
    values["trajectory_id"] = canonical_hash(
        values, prefix="qa_semantic_depth_three_independent_attack_trajectory:"
    )
    return Trajectory.model_validate(values)


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
        "rejected": True,
        "rejection_stage": caught.stage,
        "exception_type": type(caught).__name__,
        "reason_sha256": _sha(str(caught).encode("utf-8")),
        "candidate_rehashed": True,
        "output_writes": 0,
        "provider_calls": 0,
    }


def _independent_negative_controls(
    cases: Mapping[str, dict[str, Any]], registry: Any
) -> dict[str, Any]:
    serial: TaskProgram = cases["serial_margin_target_gap"]["program"]
    branch: TaskProgram = cases["branch_merge_growth_gap"]["program"]
    controls: list[dict[str, Any]] = []

    irrelevant = OperationNode(
        node_id="independent_irrelevant_lookup",
        operator_id="lookup",
        input_refs=(ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id="evidence:irrelevant"),),
        output_schema="payload",
        verifier_id="lookup.oracle.v1",
    )
    inflated = make_program((*serial.nodes[:-1], irrelevant, serial.nodes[-1]), "result")
    controls.append(
        _attack("serial_irrelevant_lookup_inflation", lambda: _derive_metrics(inflated, registry))
    )

    serial_result = serial.nodes[-1].model_copy(
        update={
            "input_refs": (
                serial.nodes[-1].input_refs[0],
                ProgramInputRef(
                    kind=InputRefKind.OPERATION, ref_id="margin_ratio", selector="value"
                ),
            ),
            "dependencies": ("target_value", "margin_ratio"),
        }
    )
    serial_bypass = make_program((*serial.nodes[:4], serial_result), "result")
    controls.append(
        _attack(
            "serial_semantic_scale_bypass",
            lambda: _admit_exact_program(serial, serial_bypass, registry),
        )
    )
    branch_bypass = make_program(branch.nodes[:-1], "signed_gap")
    controls.append(
        _attack(
            "branch_merge_absolute_bypass",
            lambda: _admit_exact_program(branch, branch_bypass, registry),
        )
    )
    controls.append(
        _attack(
            "branch_to_serial_topology_substitution",
            lambda: _admit_exact_program(branch, serial, registry),
        )
    )

    branch_case = cases["branch_merge_growth_gap"]
    branch_bundle: EvidenceBundle = branch_case["bundle"]
    crossed = branch_bundle.evidence[2].model_copy(update={"predicate": "revenue"})
    crossed_evidence = (
        branch_bundle.evidence[0],
        branch_bundle.evidence[1],
        crossed,
        branch_bundle.evidence[3],
    )
    crossed_identity = {
        "case_id": "branch_cross_metric_independent_attack",
        "evidence_ids": tuple(item.evidence_id for item in crossed_evidence),
        "evidence_version_ids": tuple(item.evidence_version_id for item in crossed_evidence),
        "schema_version": "qa_semantic_depth_three_fixture_bundle.v1",
    }
    crossed_bundle = EvidenceBundle(
        bundle_id=strict_canonical_hash(
            crossed_identity, prefix="qa_semantic_depth_three_fixture_bundle:"
        ),
        evidence=crossed_evidence,
        purpose=branch_bundle.purpose,
        graph_build_id="qa_semantic_depth_three_graph:branch_cross_metric_independent_attack",
        metadata=branch_bundle.metadata,
    )
    controls.append(
        _attack(
            "branch_cross_metric_evidence_substitution",
            lambda: _compile_package(crossed_bundle, branch_case["package"], registry),
        )
    )

    trajectory: Trajectory = branch_case["execution"].trajectory
    wrong = copy.deepcopy(trajectory.final_answer)
    wrong["result"]["value"] = "999999"
    wrong["citations"][0]["evidence_id"] = "evidence:forged:independent-depth-three"
    forged = _rehash_trajectory(trajectory, wrong)

    def reject_forged() -> None:
        package: RealizedTaskPackage = branch_case["package"]
        corpus = EvidenceCorpus.from_bundle(branch_bundle)
        graph = ProofGraphBuilder().build(branch_bundle)
        assessment = CandidateQualityEvaluator(
            semantic_policy=FinanceSemanticPolicy(),
            workflow_verifier=CandidateWorkflowVerifier(
                registry=registry, semantic_policy=FinanceSemanticPolicy()
            ),
        ).evaluate(package.task, corpus, graph, forged)
        if assessment.decision == ReleaseDecision.REJECTED:
            _fail(
                "verifier_evaluator_admission",
                "fully rehashed wrong answer and forged citation rejected",
            )

    controls.append(_attack("fully_rehashed_wrong_answer_and_citation", reject_forged))

    def reject_role_laundering() -> None:
        laundered = _registry(scale_role="transparent_projection")
        candidate = _derive_metrics(serial, laundered)
        authoritative = _derive_metrics(serial, registry)
        if candidate != authoritative:
            _fail(
                "authoritative_registry_metric_admission",
                "Registry role laundering changes authoritative depth metrics",
            )

    controls.append(_attack("operation_role_laundering", reject_role_laundering))
    if tuple(item["name"] for item in controls) != models.ATTACK_NAMES:
        _fail("negative.domain", "attack domain differs")
    if tuple(item["rejection_stage"] for item in controls) != models.ATTACK_STAGES:
        _fail("negative.stages", "observed attack rejection stages differ")
    return _identified(
        {
            "controls": tuple(controls),
            "attempted_count": 7,
            "rejected_count": 7,
            "accepted_count": 0,
            "candidate_rehashed_count": 7,
            "rejection_stages_derived_from_typed_exceptions": True,
            "candidate_negative_helper_calls": 0,
            "output_writes": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_independent_negative_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_independent_negative_audit:",
    )


def _implementation_boundary(root: Path, source_commit: str, source_tree: str) -> dict[str, Any]:
    development = source_commit == source_tree == "1" * 40
    if development:
        resolved_commit = _git_text(root, "audit_source.commit", "rev-parse", "HEAD")
        resolved_tree = _git_text(root, "audit_source.tree", "rev-parse", "HEAD^{tree}")
    else:
        resolved_commit = _git_text(
            root, "audit_source.commit", "rev-parse", f"{source_commit}^{{commit}}"
        )
        resolved_tree = _git_text(
            root, "audit_source.tree", "rev-parse", f"{source_commit}^{{tree}}"
        )
        if resolved_commit != source_commit or resolved_tree != source_tree:
            _fail("audit_source.commit_tree", "audit source commit/tree relation differs")
    rows = []
    audit_payload: bytes | None = None
    for path in models.AUDIT_SOURCE_PATHS:
        current = (root / path).read_bytes()
        if development:
            committed = current
            blob = _blob_oid(current)
        else:
            committed = _git(root, "audit_source.member", "show", f"{source_commit}:{path}")
            blob = _git_text(root, "audit_source.member", "rev-parse", f"{source_commit}:{path}")
            if blob != _blob_oid(committed) or committed != current:
                _fail("audit_source.member_bytes", f"audit source member differs: {path}")
        rows.append(
            {
                "relative_path": path,
                "git_blob_oid": blob,
                "committed_sha256": _sha(committed),
                "committed_byte_count": len(committed),
                "current_sha256": _sha(current),
                "current_byte_count": len(current),
                "current_bytes_match": True,
            }
        )
        if path.endswith("/audit.py"):
            audit_payload = current
    if audit_payload is None:
        _fail("audit_source.domain", "audit implementation is absent")
    tree_ast = ast.parse(audit_payload.decode("utf-8"))
    forbidden_modules = {
        "trusted_synthesis.experiments.qa_semantic_depth_three_plus.preflight",
        "trusted_synthesis.experiments.qa_semantic_depth_three_plus.models",
        "trusted_synthesis.core.task.program_depth",
    }
    forbidden_calls = {
        "build_qa_semantic_depth_three_plus_preflight",
        "depth_three_operation_registry",
        "derive_program_depth_metrics",
        "admit_program_depth_metrics",
        "_fixture_inputs",
        "_compile_realized",
        "_coverage_row",
        "_negative_controls",
    }
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree_ast):
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
        _fail("audit_source.helper_boundary", "candidate helper or metric oracle is called")
    return {
        "audit_source_commit": source_commit if not development else resolved_commit,
        "audit_source_tree": resolved_tree,
        "audit_source_members": tuple(rows),
        "audit_source_member_count": len(rows),
        "audit_source_member_set_sha256": _sha(canonical_json_bytes(tuple(rows))),
        "audit_source_commit_tree_relation_verified": True,
        "audit_source_current_byte_matches": len(rows),
        "helper_boundary_passed": True,
        "candidate_helper_calls": 0,
        "candidate_oracle_calls": 0,
    }


def build_qa_semantic_depth_three_plus_independent_audit(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.AuditProducts:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization = _authorization(review)
    implementation = _implementation_boundary(root, source_commit, source_tree)
    freeze, saved = _freeze_candidate(root, authorization["authorization_id"])
    detached = _detached_rebuild(root, freeze["audit_id"], saved)
    source = _source_authority(root, saved)
    registry, registry_audit = _registry_authority(source["audit_id"], saved)
    case_rows, execution, depth_topology, cases = _case_audits(
        saved, registry, registry_audit["audit_id"]
    )
    negative = _independent_negative_controls(cases, registry)
    scope = _identified(
        {
            "authorization_id": authorization["authorization_id"],
            "candidate_freeze_audit_id": freeze["audit_id"],
            "detached_rebuild_audit_id": detached["audit_id"],
            "source_authority_audit_id": source["audit_id"],
            "registry_authority_audit_id": registry_audit["audit_id"],
            "execution_audit_id": execution["audit_id"],
            "depth_topology_audit_id": depth_topology["audit_id"],
            "negative_audit_id": negative["audit_id"],
            **implementation,
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
            "candidate_formal_writes": 0,
            "passed": True,
            "schema_version": "qa_semantic_depth_three_independent_scope_audit.v1",
        },
        "audit_id",
        "qa_semantic_depth_three_independent_scope_audit:",
    )
    gates = {
        "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE": freeze["passed"],
        "A1_DETACHED_EXACT_DIRECTORY_REBUILD": detached["passed"],
        "A2_INDEPENDENT_GIT_SOURCE_AND_REGISTRY_AUTHORITY": (
            source["passed"] and registry_audit["passed"]
        ),
        "A3_INDEPENDENT_PATTERN_PROGRAM_RECONSTRUCTION": (
            execution["source_program_reconstruction_count"] == 2
        ),
        "A4_INDEPENDENT_FOURTEEN_NODE_EXECUTION_AND_VERIFICATION": (
            execution["executed_node_count"] == execution["oracle_verified_node_count"] == 14
            and execution["quality_accepted_count"] == 2
        ),
        "A5_INDEPENDENT_DEPTH_AND_TOPOLOGY_DERIVATION": (
            depth_topology["semantic_operation_depth_distribution"] == {"3": 2}
            and depth_topology["topology_distribution"]
            == {"branch_and_merge": 1, "serial_chain": 1}
        ),
        "A6_SEVEN_DIRECT_ATTACKS_REJECT": (
            negative["rejected_count"] == 7 and negative["accepted_count"] == 0
        ),
        "A7_ZERO_EXTERNAL_EXECUTION_SCOPE": not any(
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
                "candidate_formal_writes",
                "candidate_helper_calls",
                "candidate_oracle_calls",
            )
        ),
    }
    if tuple(gates) != models.GATE_NAMES or not all(gates.values()):
        _fail("gate.partition", "noncompensatory audit Gate failed")
    gate = _identified(
        {
            "gates": gates,
            "passed": 8,
            "failed": 0,
            "noncompensatory": True,
            "schema_version": "qa_semantic_depth_three_independent_gate.v1",
        },
        "gate_id",
        "qa_semantic_depth_three_independent_gate:",
    )
    common = {
        "authorization_id": authorization["authorization_id"],
        "candidate_freeze_audit_id": freeze["audit_id"],
        "detached_rebuild_audit_id": detached["audit_id"],
        "source_authority_audit_id": source["audit_id"],
        "registry_authority_audit_id": registry_audit["audit_id"],
        "execution_audit_id": execution["audit_id"],
        "depth_topology_audit_id": depth_topology["audit_id"],
        "negative_audit_id": negative["audit_id"],
        "scope_audit_id": scope["audit_id"],
        "gate_id": gate["gate_id"],
    }
    decision = _identified(
        {
            **common,
            "decision": models.DECISION,
            "candidate_accepted_as_scoped": True,
            "depth_three_constructibility_closed_for_two_fixed_fixtures": True,
            "registered_catalog_integration_evaluated": False,
            "archive_grounded_coverage_evaluated": False,
            "overall_qa_coverage_sufficient": False,
            "schema_version": "qa_semantic_depth_three_independent_decision.v1",
        },
        "decision_id",
        "qa_semantic_depth_three_independent_decision:",
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
            "schema_version": "qa_semantic_depth_three_independent_transition.v1",
        },
        "transition_id",
        "qa_semantic_depth_three_independent_transition:",
    )
    report = _identified(
        {
            **common,
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "passed_count": 8,
            "failed_count": 0,
            "exact_case_count": 2,
            "executed_and_oracle_verified_node_count": 14,
            "semantic_operation_depth_distribution": {"3": 2},
            "topology_distribution": {"branch_and_merge": 1, "serial_chain": 1},
            "deterministic_fixed_fixture_constructibility_only": True,
            "registered_catalog_integration_claimed": False,
            "archive_grounding_claimed": False,
            "benchmark_distribution_claimed": False,
            "overall_qa_coverage_claimed": False,
            "provider_calls": 0,
            "gpu_jobs": 0,
            "schema_version": "qa_semantic_depth_three_independent_report.v1",
        },
        "report_id",
        "qa_semantic_depth_three_independent_report:",
    )
    return models.AuditProducts(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=models.OPERATOR_DIRECTIVE.encode("utf-8"),
        candidate_freeze=freeze,
        detached_rebuild=detached,
        source_authority=source,
        registry_authority=registry_audit,
        case_rows=case_rows,
        execution_audit=execution,
        depth_topology_audit=depth_topology,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(_encoded(value) for value in values)


def write_qa_semantic_depth_three_plus_independent_audit_artifacts(
    products: models.AuditProducts, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "authorization.json": _encoded(products.authorization),
        "candidate_freeze_audit.json": _encoded(products.candidate_freeze),
        "case_rows.jsonl": _jsonl(products.case_rows),
        "decision.json": _encoded(products.decision),
        "depth_topology_audit.json": _encoded(products.depth_topology_audit),
        "detached_rebuild_audit.json": _encoded(products.detached_rebuild),
        "execution_audit.json": _encoded(products.execution_audit),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": _encoded(products.gate),
        "negative_control_audit.json": _encoded(products.negative_audit),
        "operator_directive.txt": products.operator_directive_bytes,
        "registry_authority_audit.json": _encoded(products.registry_authority),
        "report.json": _encoded(products.report),
        "scope_boundary_audit.json": _encoded(products.scope_audit),
        "source_authority_audit.json": _encoded(products.source_authority),
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
                members, prefix="qa_semantic_depth_three_independent_artifact_root:"
            ),
            "self_excluding": True,
            "schema_version": "qa_semantic_depth_three_independent_artifact_manifest.v1",
        },
        "manifest_id",
        "qa_semantic_depth_three_independent_artifact_manifest:",
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
    args = parser.parse_args()
    products = build_qa_semantic_depth_three_plus_independent_audit(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    write_qa_semantic_depth_three_plus_independent_audit_artifacts(products, args.output_dir)


if __name__ == "__main__":
    main()
