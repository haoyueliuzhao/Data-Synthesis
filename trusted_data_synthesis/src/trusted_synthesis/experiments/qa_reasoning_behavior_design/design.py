"""Freeze behavior/quotient design without running a new trajectory or old audit."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from .contracts import build_contract, run_design_controls
from .models import DesignChangeRequest

STAGE = (
    "finance_qa_vnext_public_reasoning_semantics_allowed_behavior_and_quotient_contract_design_only"
)
NEXT_CANDIDATE = (
    "finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight_only"
)
REVIEW_SHA256 = "5bb6c8fd48bc953be1130d07ce6542320e55d855240f84277fb49c52070e3e38"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
PREDECESSOR_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_multitrajectory_independent_audit/"
    "finance_qa_vnext_reasoning_bearing_same_task_multitrajectory_quotient_constructibility_"
    "preflight_independent_audit_v1_20260905"
)
PREDECESSOR_MANIFEST = (
    "qa_reasoning_multitrajectory_independent_manifest:"
    "496945ece1995fca7f5c789f0ecd71ca44c8f6907401c659e3aaa3b8d467f064"
)
PREDECESSOR_ROOT = (
    "qa_reasoning_multitrajectory_independent_root:"
    "c1465cfcfef7de2c8c3d8c70f1743150bce67222840f783e37f97b87078f3197"
)
PREDECESSOR_COMMIT = "7ef2b7287ddd9f87e286d580d3445a42259b80b0"
PREDECESSOR_TREE = "761defd8404b1d27ed41a2d25d83c38550efc896"
SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_behavior_design/" + p
    for p in ("__init__.py", "models.py", "contracts.py", "design.py")
)
GATE_NAMES = (
    "G0_new_external_design_scope_and_closed_predecessor",
    "G1_exact_design_and_declared_reference_source_authority",
    "G2_task_verification_invariants_separate_from_selected_behavior",
    "G3_predeclared_equivalence_and_conditional_difference_rules",
    "G4_model_and_Host_responsibilities_explicit",
    "G5_retained_historical_independent_schedule_collapse",
    "G6_local_design_controls_and_invalid_claim_rejection",
    "G7_zero_new_trajectory_model_and_release_scope",
)


class BehaviorDesignError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def require(condition: bool, stage: str, reason: str) -> None:
    if not condition:
        raise BehaviorDesignError(stage, reason)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identified(payload: Mapping[str, Any], kind: str, field: str = "audit_id") -> dict[str, Any]:
    body = dict(payload)
    body.setdefault("schema_version", f"qa_reasoning_behavior_design_{kind}.v1")
    body[field] = strict_canonical_hash(body, prefix=f"qa_reasoning_behavior_design_{kind}:")
    return body


def files_at(directory: Path) -> dict[str, bytes]:
    require(directory.is_dir(), "freeze.directory", "formal directory missing")
    paths = sorted(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "freeze.symlink", "symlinks forbidden")
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in paths if p.is_file()}


def validate_manifest(files: Mapping[str, bytes], manifest_id: str, root_id: str) -> dict[str, Any]:
    manifest = json.loads(files["artifact_manifest.json"])
    rows = manifest["members"]
    paths = [r["relative_path"] for r in rows]
    require(
        len(paths) == len(set(paths))
        and set(paths) == set(files) - {"artifact_manifest.json"}
        and manifest["member_count"] == len(rows)
        and manifest["member_bytes"] == sum(len(files[p]) for p in paths)
        and manifest["self_excluding"] is True
        and all(
            r["sha256"] == sha(files[r["relative_path"]])
            and r["byte_count"] == len(files[r["relative_path"]])
            for r in rows
        ),
        "freeze.members",
        "Manifest members or actual bytes differ",
    )
    require(
        manifest["manifest_id"] == manifest_id
        and manifest["artifact_root"] == root_id
        and strict_canonical_hash(
            {k: v for k, v in manifest.items() if k != "manifest_id"},
            prefix=manifest_id.split(":")[0] + ":",
        )
        == manifest_id
        and strict_canonical_hash(rows, prefix=root_id.split(":")[0] + ":") == root_id,
        "freeze.identity",
        "exact Manifest/Root identity differs",
    )
    return manifest


def git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(("git", "-C", str(root), *arguments), capture_output=True, check=False)
    require(result.returncode == 0, "source.git", "Git identity does not resolve")
    return result.stdout


def source_group(root: Path, commit: str, tree: str, paths: tuple[str, ...]) -> dict[str, Any]:
    require(
        git(root, "cat-file", "-t", commit).strip() == b"commit"
        and git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip() == commit
        and git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip() == tree,
        "source.commit_tree",
        "commit/tree relation differs",
    )
    rows = []
    for path in paths:
        committed = git(root, "show", f"{commit}:{path}")
        blob = hashlib.sha1(
            f"blob {len(committed)}\0".encode() + committed, usedforsecurity=False
        ).hexdigest()
        require(
            git(root, "rev-parse", f"{commit}:{path}").decode().strip() == blob
            and (root / path).read_bytes() == committed,
            "source.member",
            "committed/blob/current bytes differ",
        )
        rows.append(
            {
                "path": path,
                "blob_oid": blob,
                "sha256": sha(committed),
                "byte_count": len(committed),
                "committed_current_equal": True,
            }
        )
    return {
        "commit": commit,
        "tree": tree,
        "members": rows,
        "member_count": len(rows),
        "member_set_sha256": sha(canonical_json_bytes(rows)),
    }


def authorize(review: bytes) -> dict[str, Any]:
    require(
        len(review) == 13_357 and sha(review) == REVIEW_SHA256,
        "authorization.review",
        "exact external design review differs",
    )
    require(
        len(DIRECTIVE.encode()) == 24 and sha(DIRECTIVE.encode()) == DIRECTIVE_SHA256,
        "authorization.directive",
        "exact directive differs",
    )
    return identified(
        {
            "stage": STAGE,
            "review_bytes": len(review),
            "review_sha256": sha(review),
            "directive": DIRECTIVE,
            "directive_sha256": DIRECTIVE_SHA256,
            "review_access": (
                "report_review_DAG_enumeration_and_quantity_checks_no_repository_access"
            ),
            "current_audit_topic": "closed_as_scoped",
            "mandatory_revision": "none",
            "design_only_authorized": True,
            "runtime_authorization_issued_or_consumed": False,
            "repeat_same_independent_audit_authorized": False,
            "second_semantic_class_required": False,
            "Provider_or_GPU_authorized": False,
        },
        "authorization",
        "authorization_id",
    )


def freeze_predecessor(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / PREDECESSOR_DIRECTORY)
    manifest = validate_manifest(files, PREDECESSOR_MANIFEST, PREDECESSOR_ROOT)
    require(
        len(files) == 18
        and sum(map(len, files.values())) == 126_608
        and manifest["member_count"] == 17
        and manifest["member_bytes"] == 123_729,
        "freeze.geometry",
        "exact closed predecessor geometry differs",
    )
    require(
        git(root, "rev-parse", PREDECESSOR_COMMIT + "^{tree}").decode().strip() == PREDECESSOR_TREE,
        "freeze.source_relation",
        "predecessor source relation differs",
    )
    transition = json.loads(files["transition.json"])
    decision = json.loads(files["decision.json"])
    require(
        transition["next_stage_authorized"] is False
        and transition["prospective_next_stage"] == STAGE
        and decision["quotient_classes_per_task"] == [1, 1],
        "freeze.closed_scope",
        "closed predecessor boundary differs",
    )
    return identified(
        {
            "directory": PREDECESSOR_DIRECTORY,
            "manifest_id": PREDECESSOR_MANIFEST,
            "artifact_root": PREDECESSOR_ROOT,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "member_count": 17,
            "member_bytes": 123_729,
            "source_commit": PREDECESSOR_COMMIT,
            "source_tree": PREDECESSOR_TREE,
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "historical_next_stage_authorized": False,
            "current_audit_topic": "closed_as_scoped",
            "old_audit_builder_calls": 0,
            "old_runtime_replays": 0,
            "historical_writes": 0,
            "passed": True,
        },
        "predecessor_freeze",
    ), files


def retained_schedule_control(files: Mapping[str, bytes]) -> dict[str, Any]:
    projections = [
        json.loads(p) for p in files["independent_quotient_projections.jsonl"].splitlines()
    ]
    partition = json.loads(files["independent_quotient_partition.json"])
    groups: dict[str, list[dict[str, Any]]] = {}
    for projection in projections:
        content_id = projection["content_id"]
        require(
            strict_canonical_hash(
                {k: v for k, v in projection.items() if k != "content_id"},
                prefix=content_id.split(":")[0] + ":",
            )
            == content_id,
            "retained.projection_identity",
            "frozen causal projection identity differs",
        )
        task_id = projection["task_scope"]["task_instance_id"]
        groups.setdefault(task_id, []).append(projection)
    require(
        len(projections) == 4 and len(groups) == 2,
        "retained.task_domain",
        "exact two historical task groups differ",
    )
    rows = []
    for task_id, values in sorted(groups.items()):
        require(
            len(values) == 2 and canonical_json_bytes(values[0]) == canonical_json_bytes(values[1]),
            "retained.schedule_collapse",
            "historical same-task commutation no longer collapses",
        )
        saved = next(row for row in partition["rows"] if row["task_id"] == task_id)
        require(
            saved["distinct_trajectory_ids"] == 2 and saved["distinct_quotient_classes"] == 1,
            "retained.partition",
            "historical partition differs",
        )
        rows.append(
            {
                "task_id": task_id,
                "historical_projection_id": values[0]["content_id"],
                "same_task_projection_byte_equal": True,
                "historical_quotient_classes": 1,
            }
        )
    return identified(
        {
            "rows": rows,
            "retained_task_count": len(rows),
            "retained_projection_count": 4,
            "historical_comparison_only": True,
            "new_trajectory_executions": 0,
            "new_qualification_oracle_calls": 0,
            "new_semantic_class_witnesses": 0,
            "does_not_claim_future_quotient_separation_tested": True,
            "passed": True,
        },
        "retained_commutation",
    )


def boundary_audit() -> dict[str, Any]:
    inspected = []
    for name in ("models.py", "contracts.py", "design.py"):
        tree = ast.parse(Path(__file__).with_name(name).read_text())
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            elif isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            require(
                not any(module.startswith("trusted_synthesis.experiments.") for module in imports),
                "scope.old_experiment_import",
                "design must not import old experiment execution",
            )
        inspected.append(name)
    return {
        "inspected_members": inspected,
        "old_experiment_imports": 0,
        "old_builder_calls": 0,
        "new_runtime_executions": 0,
        "passed": True,
    }


def write_formal(output: Path, payloads: dict[str, bytes], report_id: str) -> dict[str, Any]:
    require(not output.exists(), "output.no_replace", "formal output already exists")
    members = [
        {"relative_path": p, "sha256": sha(b), "byte_count": len(b)}
        for p, b in sorted(payloads.items())
    ]
    manifest = identified(
        {
            "members": members,
            "member_count": len(members),
            "self_excluding": True,
            "member_bytes": sum(map(len, payloads.values())),
            "report_id": report_id,
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_reasoning_behavior_design_root:"
            ),
        },
        "manifest",
        "manifest_id",
    )
    output.mkdir(parents=True, exist_ok=False)
    ordered = [
        *sorted(payloads.items()),
        ("artifact_manifest.json", canonical_json_bytes(manifest)),
    ]
    for name, content in ordered:
        with (output / name).open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    validate_manifest(files_at(output), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_design(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization = authorize(review)
    freeze, previous = freeze_predecessor(root)
    implementation = source_group(root, source_commit, source_tree, SOURCE_PATHS)
    reference_groups = [
        source_group(
            root,
            "47cbc12d2684409f58b64f1e41c6a117da251949",
            "30004dcb093ec13a1c839c3765089d79700b92ef",
            (
                "trusted_data_synthesis/src/trusted_synthesis/experiments/"
                "qa_reasoning_multitrajectory/quotient.py",
            ),
        ),
        source_group(
            root,
            "a3c430a79a5b43597d93e26aab6df40436de8b2b",
            "68715d5076008e74c45e2af901cf6ca2fec378ed",
            tuple(
                "trusted_data_synthesis/src/trusted_synthesis/experiments/"
                "qa_reasoning_contract_freeze/" + name
                for name in ("models.py", "contracts.py")
            ),
        ),
    ]
    source = identified(
        {
            "implementation": implementation,
            "declared_reference_sources": reference_groups,
            "reference_modules_executed": 0,
            "transitive_runtime_closure_claimed": False,
            "passed": True,
        },
        "source_authority",
    )
    contract = build_contract()
    controls = run_design_controls(contract)
    retained = retained_schedule_control(previous)
    boundary = boundary_audit()
    require(controls["passed"], "gate.design_controls", "design controls failed")
    require(
        files_at(root / PREDECESSOR_DIRECTORY) == previous,
        "scope.predecessor_unchanged",
        "historical formal bytes changed",
    )
    scope = identified(
        {
            "stage": STAGE,
            "boundary": boundary,
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "new_task_cases": 0,
            "new_trajectory_executions": 0,
            "new_qualified_trajectories": 0,
            "semantic_class_witnesses": 0,
            "model_owned_decisions_observed": 0,
            "Archive_selections": 0,
            "Benchmark_rows": 0,
            "online_authorizations": 0,
            "empirical_estimates": 0,
            "Mapper_assignments": 0,
            "State_assignments": 0,
            "Contribution_rows": 0,
            "VTDO_rows": 0,
            "QA_Release_objects": 0,
            "training_rows": 0,
            "production_rows": 0,
            "old_mainline_resumed": False,
            "historical_audit_topic_closed": True,
            "prior_audit_builders_executed": 0,
            "design_rule_probes_are_not_experimental_trajectories": True,
            "passed": True,
        },
        "scope",
    )
    evidence = {
        "authorization": authorization,
        "predecessor_freeze": freeze,
        "source_authority": source,
        "behavior_contract": contract,
        "design_controls": controls,
        "retained_commutation": retained,
        "scope": scope,
    }
    invariants = controls["contract_invariants"]
    checks = (
        authorization["design_only_authorized"]
        and freeze["passed"]
        and invariants["closed_historical_audit"],
        source["passed"],
        invariants["task_behavior_disjoint"]
        and invariants["oracle_not_unique_route"]
        and invariants["noncompensatory_validity"]
        and invariants["evidence_and_update_boundaries"],
        invariants["commutation_conditional"]
        and invariants["conditional_semantic_separation"]
        and all(row["passed"] for row in controls["equivalence_controls"])
        and all(row["passed"] for row in controls["conditional_separation_controls"]),
        invariants["role_responsibility_explicit"],
        retained["passed"],
        controls["passed"] and all(row["passed"] for row in controls["rejected_controls"]),
        scope["passed"] and invariants["design_not_measured"],
    )
    require(all(checks), "gate.noncompensatory", "design consistency Gate failed")
    gate = identified(
        {
            "gates": [
                {"name": n, "passed": bool(ok)} for n, ok in zip(GATE_NAMES, checks, strict=True)
            ],
            "evidence_sha256": {
                name: sha(canonical_json_bytes(value)) for name, value in evidence.items()
            },
            "passed": sum(checks),
            "failed": len(checks) - sum(checks),
            "second_semantic_class_required_for_passing": False,
        },
        "gate",
        "gate_id",
    )
    decision = identified(
        {
            "decision": (
                "public_reasoning_behavior_and_quotient_semantics_design_frozen_not_executed"
            ),
            "gate_id": gate["gate_id"],
            "prior_independent_confirmation_closed": True,
            "new_semantic_class_witnesses": 0,
            "model_reasoning_observed": False,
            "same_task_multiclass_support": "not_witnessed_in_retained_family",
            "design_consistency_is_not_behavioral_validity": True,
        },
        "decision",
        "decision_id",
    )
    transition = identified(
        {
            "decision_id": decision["decision_id"],
            "completed_stage": STAGE,
            "prospective_next_stage": NEXT_CANDIDATE,
            "next_stage_authorized": False,
            "separate_new_external_decision_required": True,
            "repeat_closed_same_task_independent_audit_required": False,
            "future_first_object": "typed_candidate_family_source_and_validator_constructibility",
            "old_mainline": "remains_paused",
            "forbidden": [
                "Provider_or_GPU",
                "online_generation",
                "runtime_authorization",
                "new_actual_trajectory_in_design",
                "forced_second_class",
                "Mapper_State",
                "Contribution_VTDO",
                "QA_Release",
                "training",
                "production",
            ],
        },
        "transition",
        "transition_id",
    )
    objects = {**evidence, "gate_evaluation": gate, "decision": decision, "transition": transition}
    report = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "component_sha256": {
                name: sha(canonical_json_bytes(value)) for name, value in objects.items()
            },
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "passed_gates": gate["passed"],
            "failed_gates": gate["failed"],
            "new_trajectory_rows": 0,
            "new_semantic_classes": 0,
            "provider_calls": 0,
            "next_stage_authorized": False,
            "scientific_claim": (
                "design_semantics_and_role_responsibility_only_no_constructibility_result"
            ),
        },
        "report",
        "report_id",
    )
    objects["report"] = report
    payloads = {name + ".json": canonical_json_bytes(value) for name, value in objects.items()}
    payloads["design_change_request_schema.json"] = canonical_json_bytes(
        DesignChangeRequest.model_json_schema()
    )
    payloads["external_review.txt"] = review
    payloads["operator_directive.txt"] = DIRECTIVE.encode()
    manifest = write_formal(Path(output_directory), payloads, report["report_id"])
    return {**objects, "manifest": manifest, "output_directory": Path(output_directory)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_design(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_dir,
    )
    print(json.dumps(products["report"], indent=2))


if __name__ == "__main__":
    main()
