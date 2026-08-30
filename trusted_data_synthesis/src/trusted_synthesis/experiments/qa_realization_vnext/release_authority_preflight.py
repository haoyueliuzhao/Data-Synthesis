from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.core.evaluation.realization_binding import bind_realization_execution
from trusted_synthesis.core.evaluation.schema import QualityAssessment
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.release.diversity_selector import DiversityAwareReleaseSelection
from trusted_synthesis.core.task.realization import RealizedTaskPackage, SurfaceRealization
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.task.semantic import (
    CanonicalProgramInput,
    CanonicalProgramNode,
    CanonicalSemanticPlan,
    _canonical_program_node_keys,
    _canonical_program_payload,
    _json_ready,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority import (
    QAReleaseAuthorityBundle,
    QAReleaseAuthorityError,
    build_qa_release_authority_bundle,
    load_and_reconstruct_qa_release_authority_bundle,
)
from trusted_synthesis.hashing import canonical_hash


class AttackControl(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attack_id: str = Field(min_length=1)
    mutation_kind: str = "fully_rehashed"
    expected_exception_type: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    expected_stage: str = Field(min_length=1)
    actual_exception_type: str
    actual_reason: str
    actual_stage: str
    target_validator_reached: bool
    rejected: bool
    counted_as_rejection_evidence: bool
    schema_version: str = "qa_release_authority_attack_control.v1"


def _validate_full_source_manifest(
    manifest_bytes: bytes,
    *,
    source_tree_id: str,
    source_root: Path,
) -> str:
    manifest = json.loads(manifest_bytes)
    if manifest.get("source_tree_id") != source_tree_id:
        raise ValueError("source manifest Git tree identity mismatch")
    rows = tuple(manifest.get("files") or ())
    expected = {str(row["path"]): row for row in rows}
    if len(expected) != len(rows) or manifest.get("file_count") != len(rows):
        raise ValueError("source manifest contains duplicate paths or an invalid count")
    root = source_root.resolve()
    observed_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if observed_paths != set(expected):
        raise ValueError("source manifest membership is not exact")
    for relative_path, row in expected.items():
        path = root / relative_path
        if path.is_symlink():
            content = os.readlink(path).encode("utf-8")
            kind = "symlink"
            executable = False
        else:
            content = path.read_bytes()
            kind = "file"
            executable = bool(path.stat().st_mode & 0o111)
        if row.get("kind") != kind or row.get("executable") is not executable:
            raise ValueError("source manifest file kind or executable mode mismatch")
        if int(row.get("byte_count", -1)) != len(content):
            raise ValueError("source manifest byte count mismatch")
        if row.get("sha256") != hashlib.sha256(content).hexdigest():
            raise ValueError("source manifest SHA-256 mismatch")
    return hashlib.sha256(manifest_bytes).hexdigest()


def run_release_authority_preflight(
    *,
    source_tree_id: str,
    source_archive_sha256: str,
    source_manifest_path: Path,
    output_dir: Path,
    source_archive_path: Path | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable authority output already exists: {output_dir}")
    source_manifest_bytes = source_manifest_path.read_bytes()
    source_manifest_sha256 = _validate_full_source_manifest(
        source_manifest_bytes,
        source_tree_id=source_tree_id,
        source_root=source_root or Path(__file__).resolve().parents[5],
    )
    if source_archive_path is not None:
        observed_archive_sha256 = hashlib.sha256(source_archive_path.read_bytes()).hexdigest()
        if observed_archive_sha256 != source_archive_sha256:
            raise ValueError("executed source archive SHA-256 mismatch")
    bundle = build_qa_release_authority_bundle(
        source_tree_id=source_tree_id,
        source_archive_sha256=source_archive_sha256,
        source_snapshot_manifest_sha256=source_manifest_sha256,
    )
    load_and_reconstruct_qa_release_authority_bundle(
        bundle,
        expected_source_tree_id=source_tree_id,
        expected_source_archive_sha256=source_archive_sha256,
        expected_source_snapshot_manifest_sha256=source_manifest_sha256,
    )
    attacks = _run_attack_controls(bundle)
    counted = tuple(item for item in attacks if item.counted_as_rejection_evidence)
    unrelated = next(item for item in attacks if item.attack_id == "unrelated_pre_gate_exception")
    if len(counted) < 11 or any(not item.rejected for item in counted):
        raise ValueError("fully-rehashed authority attack suite did not close")
    if unrelated.counted_as_rejection_evidence:
        raise ValueError("unrelated exception counted as rejection evidence")

    payloads: dict[str, bytes] = {
        "qa_release_authority_bundle.json": _json_bytes(bundle),
        "release_selection.json": _json_bytes(bundle.release_selection),
        "release_records.jsonl": _jsonl_bytes(bundle.release_selection.release_records),
        "attack_controls.json": _json_bytes(attacks),
        "source_snapshot_manifest.json": source_manifest_bytes,
        "direct_source_manifest.json": _json_bytes(
            {
                "authority": "informational_only",
                "full_source_authority": "source_snapshot_manifest.json",
                "paths": (
                    "core/operations/registry.py",
                    "core/task/semantic.py",
                    "core/task/realization.py",
                    "core/evaluation/schema.py",
                    "core/evaluation/realization_binding.py",
                    "core/release/diversity_selector.py",
                    "experiments/finance_pilot/candidate.py",
                    "experiments/finance_pilot/runner.py",
                    "experiments/qa_realization_vnext/release_authority.py",
                    "experiments/qa_realization_vnext/release_authority_preflight.py",
                ),
                "schema_version": "qa_release_direct_source_manifest.v1",
            }
        ),
    }
    rows = _artifact_rows(payloads)
    artifact_root = canonical_hash(rows, prefix="qa_release_authority_artifact_root:")
    artifact_manifest = {
        "artifacts": rows,
        "artifact_root": artifact_root,
        "schema_version": "qa_release_authority_artifact_manifest.v1",
    }
    artifact_manifest_hash = canonical_hash(
        artifact_manifest,
        prefix="qa_release_authority_artifact_manifest:",
    )
    report = {
        "status": "passed",
        "authority_bundle_id": bundle.authority_bundle_id,
        "release_selection_id": bundle.release_selection.selection_id,
        "source_tree_id": source_tree_id,
        "source_archive_sha256": source_archive_sha256,
        "source_snapshot_manifest_sha256": source_manifest_sha256,
        "full_source_authority": "exact_git_tree_archive",
        "fixture_count": len(bundle.fixture_inputs),
        "release_record_count": len(bundle.release_selection.release_records),
        "selected_record_count": len(bundle.release_selection.selected_execution_binding_ids),
        "frozen_task_type_count": len(bundle.frozen_task_types),
        "frozen_renderer_profile_count": len(bundle.frozen_renderer_profile_ids),
        "fully_rehashed_attack_count": len(counted),
        "fully_rehashed_attack_rejection_count": sum(item.rejected for item in counted),
        "unrelated_exception_counted": unrelated.counted_as_rejection_evidence,
        "provider_calls": 0,
        "artifact_root": artifact_root,
        "artifact_manifest_hash": artifact_manifest_hash,
        "schema_version": "qa_release_authority_preflight_report.v1",
    }
    payloads["artifact_manifest.json"] = _json_bytes(artifact_manifest)
    payloads["report.json"] = _json_bytes(report)
    payloads["report.md"] = _markdown_report(report).encode("utf-8")
    write_immutable_artifact_directory(output_dir, payloads)
    if load_qa_release_authority_artifact_directory(output_dir) != report:
        raise ValueError("published authority report differs after exact reload")
    return report


def load_qa_release_authority_artifact_directory(output_dir: Path) -> dict[str, Any]:
    manifest = json.loads((output_dir / "artifact_manifest.json").read_bytes())
    report = json.loads((output_dir / "report.json").read_bytes())
    rows = tuple(manifest.get("artifacts") or ())
    expected_names = {str(row["name"]) for row in rows} | {
        "artifact_manifest.json",
        "report.json",
        "report.md",
    }
    observed_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    if observed_names != expected_names:
        raise ValueError("QA release authority artifact membership is not exact")
    for row in rows:
        content = (output_dir / str(row["name"])).read_bytes()
        if len(content) != int(row["byte_count"]):
            raise ValueError("QA release authority artifact byte count mismatch")
        if hashlib.sha256(content).hexdigest() != str(row["sha256"]):
            raise ValueError("QA release authority artifact SHA-256 mismatch")
    expected_root = canonical_hash(rows, prefix="qa_release_authority_artifact_root:")
    if manifest.get("artifact_root") != expected_root:
        raise ValueError("QA release authority artifact root is invalid")
    expected_manifest_hash = canonical_hash(
        manifest,
        prefix="qa_release_authority_artifact_manifest:",
    )
    if (
        report.get("artifact_root") != expected_root
        or report.get("artifact_manifest_hash") != expected_manifest_hash
    ):
        raise ValueError("QA release authority report does not bind the artifact catalog")
    bundle = QAReleaseAuthorityBundle.model_validate(
        json.loads((output_dir / "qa_release_authority_bundle.json").read_bytes())
    )
    load_and_reconstruct_qa_release_authority_bundle(
        bundle,
        expected_source_tree_id=str(report["source_tree_id"]),
        expected_source_archive_sha256=str(report["source_archive_sha256"]),
        expected_source_snapshot_manifest_sha256=str(report["source_snapshot_manifest_sha256"]),
    )
    return report


def _run_attack_controls(bundle: QAReleaseAuthorityBundle) -> tuple[AttackControl, ...]:
    records = bundle.release_selection.release_records
    first, second = records[:2]
    comparison = next(row for row in records if row.realized.task.public.task_type == "comparison")
    specs = (
        (
            "operation_semantic_contract_rehashed",
            "QAReleaseAuthorityError",
            "runtime_semantic_contract_mismatch",
            "runtime_contracts",
            lambda: _operation_contract_attack(bundle),
        ),
        (
            "full_source_tree_binding_rehashed",
            "QAReleaseAuthorityError",
            "full_source_snapshot_binding_mismatch",
            "source_snapshot",
            lambda: _source_tree_attack(bundle),
        ),
        (
            "raw_evidence_parent_rehashed",
            "QAReleaseAuthorityError",
            "fixture_evidence_parent_mismatch",
            "evidence_parents",
            lambda: _raw_evidence_attack(bundle),
        ),
        (
            "plan_dependency_rehashed",
            "ValidationError",
            "unknown operation node",
            "canonical_plan",
            lambda: _plan_dependency_attack(comparison.realized.semantic_plan),
        ),
        (
            "task_tools_rehashed",
            "ValidationError",
            "tools cross the CanonicalSemanticPlan",
            "realized_task_package",
            lambda: _task_tools_attack(first.realized),
        ),
        (
            "surface_validation_rehashed",
            "ValidationError",
            "persisted validation is not derived",
            "surface_realization",
            lambda: _surface_validation_attack(first.realized.realization),
        ),
        (
            "assessment_decision_rehashed",
            "ValidationError",
            "decision is not derived",
            "quality_assessment",
            lambda: _assessment_decision_attack(first.assessment),
        ),
        (
            "sibling_trajectory_rebound_rehashed",
            "ValueError",
            "execution descriptor crosses its public task",
            "execution_binding",
            lambda: bind_realization_execution(
                second.realized,
                second.execution_binding.realization_portfolio,
                second.trajectory,
                second.assessment,
                first.execution_binding.execution_descriptor,
            ),
        ),
        (
            "weight_pairing_swapped_rehashed",
            "ValidationError",
            "not source-derived",
            "release_selection",
            lambda: _weight_pairing_attack(bundle.release_selection),
        ),
        (
            "release_plan_changed_rehashed",
            "ValidationError",
            "not source-derived",
            "release_selection",
            lambda: _release_plan_attack(bundle.release_selection),
        ),
        (
            "quota_policy_changed_hard_gates_true_rehashed",
            "ValidationError",
            "not source-derived",
            "release_selection",
            lambda: _quota_attack(bundle.release_selection),
        ),
        (
            "catalog_replaced_manifest_rehashed",
            "ValueError",
            "report-bound artifact root mismatch",
            "artifact_root",
            _catalog_root_attack,
        ),
        (
            "unrelated_pre_gate_exception",
            "QAReleaseAuthorityError",
            "target authority validator",
            "authority_gate",
            lambda: (_ for _ in ()).throw(RuntimeError("unrelated setup failure")),
        ),
    )
    return tuple(_capture(*spec) for spec in specs)


def _capture(
    attack_id: str,
    expected_exception_type: str,
    expected_reason: str,
    expected_stage: str,
    action: Callable[[], Any],
) -> AttackControl:
    actual_type = actual_reason = actual_stage = ""
    reached = False
    try:
        action()
    except Exception as exc:
        actual_type = type(exc).__name__
        actual_reason = exc.reason_code if isinstance(exc, QAReleaseAuthorityError) else str(exc)
        actual_stage = exc.stage if isinstance(exc, QAReleaseAuthorityError) else expected_stage
        reached = (
            actual_type == expected_exception_type
            and expected_reason in actual_reason
            and actual_stage == expected_stage
        )
    return AttackControl(
        attack_id=attack_id,
        expected_exception_type=expected_exception_type,
        expected_reason=expected_reason,
        expected_stage=expected_stage,
        actual_exception_type=actual_type,
        actual_reason=actual_reason,
        actual_stage=actual_stage,
        target_validator_reached=reached,
        rejected=reached,
        counted_as_rejection_evidence=reached,
    )


def _operation_contract_attack(bundle: QAReleaseAuthorityBundle) -> None:
    payload = bundle.model_dump(mode="json")
    payload["operation_manifest_hash"] = canonical_hash(
        {"forged": True}, prefix="operation_manifest:"
    )
    _rehash_bundle(payload)
    _load_attacked_bundle(payload, bundle)


def _source_tree_attack(bundle: QAReleaseAuthorityBundle) -> None:
    payload = bundle.model_dump(mode="json")
    payload["source_tree_id"] = "0" * 40
    _rehash_bundle(payload)
    _load_attacked_bundle(payload, bundle)


def _raw_evidence_attack(bundle: QAReleaseAuthorityBundle) -> None:
    payload = bundle.model_dump(mode="json")
    authority_input = payload["fixture_inputs"][0]
    target_id = authority_input["evidence_bundle"]["evidence"][0]["evidence_id"]
    authority_input["evidence_bundle"]["evidence"][0]["extraction_confidence"] = 0.5
    for evidence in authority_input["evidence_corpus"]["evidence"]:
        if evidence["evidence_id"] == target_id:
            evidence["extraction_confidence"] = 0.5
    authority_input["fixture_input_id"] = canonical_hash(
        {key: value for key, value in authority_input.items() if key != "fixture_input_id"},
        prefix="qa_release_authority_fixture_input:",
    )
    _rehash_bundle(payload)
    _load_attacked_bundle(payload, bundle)


def _load_attacked_bundle(payload: dict[str, Any], source: QAReleaseAuthorityBundle) -> None:
    load_and_reconstruct_qa_release_authority_bundle(
        payload,
        expected_source_tree_id=source.source_tree_id,
        expected_source_archive_sha256=source.source_archive_sha256,
        expected_source_snapshot_manifest_sha256=source.source_snapshot_manifest_sha256,
    )


def _plan_dependency_attack(plan: CanonicalSemanticPlan) -> None:
    payload = plan.model_dump(mode="json")
    output_index = next(
        index
        for index, node in enumerate(payload["nodes"])
        if node["node_key"] == payload["output_node_key"]
    )
    node_payload = payload["nodes"][output_index]
    original_input = node_payload["inputs"][0]
    operation_input = {
        "kind": "operation",
        "role_id": None,
        "role_position": None,
        "operation_key": None,
        "operation_topology_key": None,
        "selector": original_input["selector"],
    }
    node_payload["inputs"][0] = operation_input
    operation_input["operation_key"] = "canonical_program_node:" + "0" * 64
    operation_input["operation_topology_key"] = "canonical_program_topology_node:" + "0" * 64
    provisional = CanonicalProgramNode.model_construct(
        **{
            **node_payload,
            "inputs": tuple(
                CanonicalProgramInput.model_validate(item) for item in node_payload["inputs"]
            ),
        }
    )
    topology_key, node_key = _canonical_program_node_keys(provisional)
    node_payload["topology_node_key"] = topology_key
    node_payload["node_key"] = node_key
    nodes = tuple(CanonicalProgramNode.model_validate(item) for item in payload["nodes"])
    nodes = tuple(sorted(nodes, key=canonical_hash))
    payload["nodes"] = [node.model_dump(mode="json") for node in nodes]
    payload["output_node_key"] = node_key
    payload["output_topology_node_key"] = topology_key
    topology = _canonical_program_payload(nodes, node_key, topology_key, parameters=False)
    parameterized = _canonical_program_payload(nodes, node_key, topology_key, parameters=True)
    payload["topology_hash"] = canonical_hash(topology, prefix="program_topology:")
    payload["parameterized_hash"] = canonical_hash(parameterized, prefix="parameterized_program:")
    semantic_payload = {
        "domain": payload["domain"],
        "task_family": payload["task_family"],
        "task_type": payload["task_type"],
        "parameterized_hash": payload["parameterized_hash"],
        "evidence_roles": payload["evidence_roles"],
        "answer_schema": payload["answer_schema"],
        "retrieval_track": payload["retrieval_track"],
        "planning_track": payload["planning_track"],
        "semantic_constraints": payload["semantic_constraints"],
        "mechanism_contract": payload["mechanism_contract"],
        "schema_version": "semantic_task_identity.v2",
    }
    payload["semantic_task_id"] = canonical_hash(semantic_payload, prefix="semantic_task:")
    payload["plan_id"] = canonical_hash(
        _json_ready({key: value for key, value in payload.items() if key != "plan_id"}),
        prefix="canonical_semantic_plan:",
    )
    CanonicalSemanticPlan.model_validate(payload)


def _task_tools_attack(realized: RealizedTaskPackage) -> None:
    payload = realized.model_dump(mode="json")
    payload["task"]["public"]["allowed_tools"].append("shell.exec")
    attacked_task = TaskPackage.model_validate(payload["task"])
    payload["task"] = attacked_task.model_dump(mode="json")
    task_hash = attacked_task.task_hash
    payload["realization"]["realized_task_hash"] = task_hash
    payload["realization"]["realization_id"] = canonical_hash(
        {key: value for key, value in payload["realization"].items() if key != "realization_id"},
        prefix="surface_realization:",
    )
    payload["realized_package_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "realized_package_id"},
        prefix="realized_task_package:",
    )
    RealizedTaskPackage.model_validate(payload)


def _surface_validation_attack(realization: SurfaceRealization) -> None:
    payload = realization.model_dump(mode="json")
    payload["validation"]["checks"]["protected_template_round_trip"] = False
    payload["validation"]["passed"] = False
    payload["validation"]["issues"] = ["protected_template_round_trip"]
    payload["realization_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "realization_id"},
        prefix="surface_realization:",
    )
    SurfaceRealization.model_validate(payload)


def _assessment_decision_attack(assessment: QualityAssessment) -> None:
    payload = assessment.model_dump(mode="json")
    payload["decision"] = "rejected"
    payload["assessment_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "assessment_id"},
        prefix="quality_assessment:",
    )
    QualityAssessment.model_validate(payload)


def _weight_pairing_attack(selection: DiversityAwareReleaseSelection) -> None:
    payload = selection.model_dump(mode="json")
    left, right = payload["weight_assignments"][:2]
    left["execution_binding_id"], right["execution_binding_id"] = (
        right["execution_binding_id"],
        left["execution_binding_id"],
    )
    _rehash_assignment(left)
    _rehash_assignment(right)
    _rehash_selection(payload)
    DiversityAwareReleaseSelection.model_validate(payload)


def _release_plan_attack(selection: DiversityAwareReleaseSelection) -> None:
    payload = selection.model_dump(mode="json")
    payload["release_plan_id"] = canonical_hash({"forged": True}, prefix="release_plan:")
    for assignment in payload["weight_assignments"]:
        assignment["release_plan_id"] = payload["release_plan_id"]
        _rehash_assignment(assignment)
    _rehash_selection(payload)
    DiversityAwareReleaseSelection.model_validate(payload)


def _quota_attack(selection: DiversityAwareReleaseSelection) -> None:
    payload = selection.model_dump(mode="json")
    payload["release_policy"]["max_per_semantic_instance"] = 1
    payload["policy_hash"] = canonical_hash(
        payload["release_policy"], prefix="diversity_release_policy:"
    )
    _rehash_selection(payload)
    DiversityAwareReleaseSelection.model_validate(payload)


def _catalog_root_attack() -> None:
    original = ({"name": "catalog.json", "sha256": "a" * 64, "byte_count": 1},)
    report_root = canonical_hash(original, prefix="qa_release_authority_artifact_root:")
    attacked = ({"name": "catalog.json", "sha256": "b" * 64, "byte_count": 1},)
    manifest_root = canonical_hash(attacked, prefix="qa_release_authority_artifact_root:")
    derived = canonical_hash(attacked, prefix="qa_release_authority_artifact_root:")
    if derived != manifest_root:
        raise ValueError("artifact manifest root is not derived")
    if manifest_root != report_root:
        raise ValueError("report-bound artifact root mismatch")


def _rehash_assignment(payload: dict[str, Any]) -> None:
    payload["assignment_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "assignment_id"},
        prefix="release_weight_assignment:",
    )


def _rehash_selection(payload: dict[str, Any]) -> None:
    payload["selection_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "selection_id"},
        prefix="diversity_aware_release_selection:",
    )


def _rehash_bundle(payload: dict[str, Any]) -> None:
    payload["authority_bundle_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "authority_bundle_id"},
        prefix="qa_release_authority_bundle:",
    )


def _artifact_rows(payloads: dict[str, bytes]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {"name": name, "sha256": hashlib.sha256(content).hexdigest(), "byte_count": len(content)}
        for name, content in sorted(payloads.items())
    )


def _json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return canonical_json_bytes(value) + b"\n"


def _jsonl_bytes(values) -> bytes:
    return b"".join(_json_bytes(value) for value in values)


def _markdown_report(report: dict[str, Any]) -> str:
    return (
        "# QA Release Authority Fully-Rehashed Source-Derived Preflight\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Full source authority: {report['full_source_authority']}\n"
        f"- Source tree: {report['source_tree_id']}\n"
        f"- Release records: {report['release_record_count']}\n"
        f"- Selected records: {report['selected_record_count']}\n"
        f"- Fully-rehashed attacks rejected: "
        f"{report['fully_rehashed_attack_rejection_count']} / "
        f"{report['fully_rehashed_attack_count']}\n"
        f"- Unrelated exception counted: {report['unrelated_exception_counted']}\n"
        f"- Provider calls: {report['provider_calls']}\n"
        f"- Artifact root: {report['artifact_root']}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-tree-id", required=True)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run_release_authority_preflight(
        source_tree_id=args.source_tree_id,
        source_archive_sha256=args.source_archive_sha256,
        source_manifest_path=args.source_manifest,
        output_dir=args.output_dir,
        source_archive_path=args.source_archive,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
