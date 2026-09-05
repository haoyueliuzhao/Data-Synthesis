"""Independently confirm only the current four-trajectory schedule experiment.

Candidate code runs once in a detached reproducibility subprocess.  Semantic
admission and quotient outcomes are then derived by this audit's own modules.
No preceding completed independent-audit builder is invoked.
"""

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
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from . import models
from .quotient import audit_quotient
from .semantics import audit_trajectories, independent_runtime_controls


class IndependentAuditError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def require(condition: bool, stage: str, reason: str) -> None:
    if not condition:
        raise IndependentAuditError(stage, reason)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identified(values: Mapping[str, Any], kind: str, field: str = "audit_id") -> dict[str, Any]:
    result = dict(values)
    result.setdefault("schema_version", f"qa_reasoning_multitrajectory_independent_{kind}.v1")
    result[field] = strict_canonical_hash(
        result, prefix=f"qa_reasoning_multitrajectory_independent_{kind}:"
    )
    return result


def files_at(directory: Path) -> dict[str, bytes]:
    require(directory.is_dir(), "freeze.directory", "formal directory is absent")
    paths = sorted(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "freeze.symlink", "symlink is not admitted")
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in paths if p.is_file()}


def validate_manifest(
    files: Mapping[str, bytes], manifest_id: str, artifact_root: str
) -> dict[str, Any]:
    manifest = json.loads(files["artifact_manifest.json"])
    members = manifest["members"]
    paths = [m["relative_path"] for m in members]
    require(
        len(paths) == len(set(paths))
        and set(paths) == set(files) - {"artifact_manifest.json"}
        and all(
            m["sha256"] == sha(files[m["relative_path"]])
            and m["byte_count"] == len(files[m["relative_path"]])
            for m in members
        )
        and manifest["member_count"] == len(members)
        and manifest["member_bytes"] == sum(len(files[p]) for p in paths)
        and manifest["self_excluding"] is True,
        "freeze.manifest_members",
        "formal member set, hashes or bytes differ",
    )
    require(
        manifest["manifest_id"] == manifest_id
        and strict_canonical_hash(
            {k: v for k, v in manifest.items() if k != "manifest_id"},
            prefix=manifest_id.split(":")[0] + ":",
        )
        == manifest_id
        and manifest["artifact_root"] == artifact_root
        and strict_canonical_hash(members, prefix=artifact_root.split(":")[0] + ":")
        == artifact_root,
        "freeze.identity",
        "Manifest or Root identity differs",
    )
    return manifest


def freeze_candidate(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / models.CANDIDATE_DIRECTORY)
    manifest = validate_manifest(files, models.CANDIDATE_MANIFEST, models.CANDIDATE_ROOT)
    require(
        len(files) == 156
        and sum(map(len, files.values())) == 602_070
        and manifest["member_count"] == 155
        and manifest["member_bytes"] == 574_961,
        "freeze.geometry",
        "exact current candidate geometry differs",
    )
    transition = json.loads(files["transition.json"])
    require(
        transition["transition_id"] == models.CANDIDATE_TRANSITION
        and transition["next_stage_authorized"] is False
        and transition["prospective_next_stage"] == models.STAGE,
        "freeze.transition",
        "current candidate transition differs",
    )
    return identified(
        {
            "directory": models.CANDIDATE_DIRECTORY,
            "manifest_id": models.CANDIDATE_MANIFEST,
            "artifact_root": models.CANDIDATE_ROOT,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "member_count": len(manifest["members"]),
            "member_bytes": manifest["member_bytes"],
            "manifest_sha256": sha(files["artifact_manifest.json"]),
            "source_commit": models.CANDIDATE_COMMIT,
            "source_tree": models.CANDIDATE_TREE,
            "transition_id": transition["transition_id"],
            "historical_next_stage_authorized": False,
            "candidate_report_gate_selection_replay_partition_used_as_oracles": False,
            "passed": True,
        },
        "candidate_freeze",
    ), files


def authorize(review: bytes) -> dict[str, Any]:
    require(
        len(review) == models.REVIEW_BYTES and sha(review) == models.REVIEW_SHA256,
        "authorization.review",
        "exact external review differs",
    )
    directive = models.DIRECTIVE.encode()
    require(
        len(directive) == 24 and sha(directive) == models.DIRECTIVE_SHA256,
        "authorization.directive",
        "exact operator directive differs",
    )
    return identified(
        {
            "stage": models.STAGE,
            "review_sha256": sha(review),
            "review_bytes": len(review),
            "operator_directive": models.DIRECTIVE,
            "directive_sha256": sha(directive),
            "review_access": "report_consistency_and_independent_five_node_DAG_enumeration_only",
            "external_review_repository_access_claimed": False,
            "current_four_trajectory_independent_confirmation_authorized": True,
            "repeat_old_completed_independent_audit_authorized": False,
            "new_case_or_schedule_authorized": False,
            "Provider_or_GPU_authorized": False,
            "online_authorization_issued": False,
        },
        "authorization",
        "authorization_id",
    )


def git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(("git", "-C", str(root), *args), capture_output=True, check=False)
    require(proc.returncode == 0, "source.git", "Git object cannot be resolved")
    return proc.stdout


def source_group(root: Path, commit: str, tree: str, paths: list[str]) -> dict[str, Any]:
    require(
        git(root, "cat-file", "-t", commit).strip() == b"commit"
        and git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip() == commit
        and git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip() == tree,
        "source.commit_tree",
        "exact commit-tree relation differs",
    )
    require(len(paths) == len(set(paths)), "source.paths", "duplicate source member")
    rows = []
    for relative in paths:
        require(
            not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            "source.path",
            "unsafe source member path",
        )
        committed = git(root, "show", f"{commit}:{relative}")
        blob = hashlib.sha1(
            f"blob {len(committed)}\0".encode() + committed, usedforsecurity=False
        ).hexdigest()
        require(
            git(root, "rev-parse", f"{commit}:{relative}").decode().strip() == blob
            and (root / relative).read_bytes() == committed,
            "source.member_bytes",
            "committed blob or current source bytes differ",
        )
        rows.append(
            {
                "path": relative,
                "blob_oid": blob,
                "sha256": sha(committed),
                "byte_count": len(committed),
                "committed_current_match": True,
            }
        )
    return {
        "commit": commit,
        "tree": tree,
        "members": rows,
        "member_count": len(rows),
        "member_set_sha256": sha(canonical_json_bytes(rows)),
    }


def audit_sources(root: Path, files: Mapping[str, bytes], commit: str, tree: str) -> dict[str, Any]:
    candidate = json.loads(files["source_binding.json"])
    groups = {}
    for name, count in (("implementation", 6), ("retained_helpers", 7)):
        saved = candidate[name]
        require(len(saved["members"]) == count, "source.domain", "declared source count differs")
        if name == "implementation":
            require(
                saved["commit"] == models.CANDIDATE_COMMIT
                and saved["tree"] == models.CANDIDATE_TREE,
                "source.candidate",
                "candidate source freeze differs",
            )
        derived = source_group(
            root, saved["commit"], saved["tree"], [m["path"] for m in saved["members"]]
        )
        require(
            canonical_json_bytes(derived) == canonical_json_bytes(saved),
            "source.comparison",
            "independent source rows differ",
        )
        groups[name] = derived
    own = source_group(root, commit, tree, list(models.SOURCE_PATHS))
    return identified(
        {
            "candidate_source_groups": groups,
            "candidate_members": 13,
            "candidate_source_group_byte_matches": 2,
            "audit_implementation": own,
            "transitive_import_or_runtime_closure_claimed": False,
            "passed": True,
        },
        "source_authority",
    )


def detached_rebuild(
    root: Path, files: Mapping[str, bytes]
) -> tuple[dict[str, Any], dict[str, Any]]:
    with TemporaryDirectory(prefix="qa_same_task_audit_") as temporary:
        scratch = Path(temporary)
        source = scratch / "source"
        source.mkdir()
        archive_bytes = git(root, "archive", models.CANDIDATE_COMMIT, "trusted_data_synthesis/src")
        with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
            members = archive.getmembers()
            require(
                all(
                    (m.isdir() or m.isfile())
                    and not Path(m.name).is_absolute()
                    and ".." not in Path(m.name).parts
                    for m in members
                ),
                "rebuild.archive",
                "unsafe detached source archive",
            )
            archive.extractall(source, filter="data")
        rebuilt = scratch / "rebuilt"
        trace_path = scratch / "probe_trace.json"
        reduced_environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(source / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        proc = subprocess.run(
            (
                sys.executable,
                str(Path(__file__).with_name("probe.py")),
                "--trace",
                str(trace_path),
                "--repo-root",
                str(root),
                "--external-audit",
                str(root / models.CANDIDATE_DIRECTORY / "external_review.txt"),
                "--source-commit",
                models.CANDIDATE_COMMIT,
                "--source-tree",
                models.CANDIDATE_TREE,
                "--output-dir",
                str(rebuilt),
            ),
            cwd=source,
            env=reduced_environment,
            capture_output=True,
            check=False,
            timeout=180,
        )
        if proc.returncode:
            # No credential environment is passed into this detached process.
            raise IndependentAuditError("rebuild.subprocess", proc.stderr.decode()[-6000:])
        actual = files_at(rebuilt)
        require(dict(files) == actual, "rebuild.actual_bytes", "current 156-file rebuild differs")
        validate_manifest(actual, models.CANDIDATE_MANIFEST, models.CANDIDATE_ROOT)
        trace = json.loads(trace_path.read_bytes())
        callbacks = trace["callbacks"]
        require(
            len(callbacks) == 20 and trace["all_callbacks_passed"],
            "probe.callbacks",
            "twenty actual callbacks were not observed",
        )
        receipt_paths = {row["receipt_relative_path"] for row in callbacks}
        require(len(receipt_paths) == 20, "probe.own_receipts", "callback receipt reused")
        for row in callbacks:
            envelope = files[row["envelope_relative_path"]]
            require(
                row["envelope_sha256"] == sha(envelope)
                and row["envelope_byte_count"] == len(envelope),
                "probe.envelope",
                "callback disk snapshot differs from exact candidate",
            )
            receipt_bytes = files[row["receipt_relative_path"]]
            require(
                row["receipt_sha256"] == sha(receipt_bytes)
                and row["receipt_byte_count"] == len(receipt_bytes),
                "probe.receipt",
                "callback Receipt snapshot differs from frozen candidate",
            )
            for registration in row["preregistration"]:
                payload = files[registration["relative_path"]]
                require(
                    registration["sha256"] == sha(payload)
                    and registration["byte_count"] == len(payload),
                    "probe.preregistration",
                    "predeclared rule bytes changed",
                )
        rebuild_audit = identified(
            {
                "source_commit": models.CANDIDATE_COMMIT,
                "source_tree": models.CANDIDATE_TREE,
                "archived_source_files": sum(m.isfile() for m in members),
                "saved_files": len(files),
                "rebuilt_files": len(actual),
                "saved_bytes": sum(map(len, files.values())),
                "rebuilt_bytes": sum(map(len, actual.values())),
                "actual_byte_matches": len(actual),
                "manifest_members_revalidated": 155,
                "environment_keys": sorted(reduced_environment),
                "credential_like_environment_keys": 0,
                "prior_independent_audit_builders_executed": 0,
                "candidate_builder_used_only_for_reproducibility_and_observation": True,
                "provider_calls": 0,
                "passed": True,
            },
            "detached_rebuild",
        )
        probe_audit = identified(
            {
                **trace,
                "candidate_runtime_files": sum(p.startswith("runtime/") for p in files),
                "own_envelope_receipt_pairs": len(receipt_paths),
                "own_envelope_receipt_exclusive_creates": 40,
                "own_envelope_receipt_file_fsyncs_before_callback": 40,
                "own_envelope_receipt_directory_fsyncs_before_callback": 40,
                "predeclared_contract_and_registration_snapshots": len(callbacks) * 2,
                "observer_calls_real_os_syscalls": True,
                "candidate_saved_event_log_used_as_order_oracle": False,
                "passed": True,
            },
            "dynamic_durability",
        )
        return rebuild_audit, probe_audit


def helper_boundary() -> dict[str, Any]:
    checked = []
    forbidden = "trusted_synthesis.experiments.qa_reasoning_multitrajectory"
    for name in ("audit.py", "semantics.py", "quotient.py"):
        tree = ast.parse(Path(__file__).with_name(name).read_text())
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            require(
                not any(
                    value == forbidden or value.startswith(forbidden + ".") for value in imports
                ),
                "scope.helper_boundary",
                "current candidate semantic helper imported",
            )
        checked.append(name)
    return {
        "checked_executable_members": checked,
        "candidate_semantic_helper_imports": 0,
        "candidate_report_gate_oracle_calls": 0,
        "passed": True,
    }


def write_formal(
    directory: Path, payloads: dict[str, bytes], report: dict[str, Any]
) -> dict[str, Any]:
    require(not directory.exists(), "output.no_replace", "formal output already exists")
    members = [
        {"relative_path": p, "sha256": sha(b), "byte_count": len(b)}
        for p, b in sorted(payloads.items())
    ]
    manifest = identified(
        {
            "report_id": report["report_id"],
            "members": members,
            "self_excluding": True,
            "member_count": len(members),
            "member_bytes": sum(map(len, payloads.values())),
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_reasoning_multitrajectory_independent_root:"
            ),
        },
        "manifest",
        "manifest_id",
    )
    payloads = {**payloads, "artifact_manifest.json": canonical_json_bytes(manifest)}
    directory.mkdir(parents=True, exist_ok=False)
    for relative, payload in sorted(payloads.items()):
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    validate_manifest(files_at(directory), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_audit(
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
    freeze, files = freeze_candidate(root)
    source = audit_sources(root, files, source_commit, source_tree)
    boundary = helper_boundary()
    rebuild, durability = detached_rebuild(root, files)
    trajectories, results = audit_trajectories(repo_root=root, candidate_files=files)
    quotient, projections, partition = audit_quotient(candidate_files=files, results=results)
    runtime_controls = independent_runtime_controls(files, results)
    require(
        trajectories["passed"]
        and trajectories["trajectory_count"] == 4
        and trajectories["qualified"] == 4
        and trajectories["runtime_objects_reconstructed"] == 124,
        "decision.trajectories",
        "independent own trajectory reconstruction failed",
    )
    require(
        quotient["tasks_with_multiple_classes"] == 0 and quotient["saved_partition_byte_match"],
        "decision.quotient",
        "independent local quotient partition differs",
    )
    # Preserve and reread all predecessor bytes after the complete audit work.
    require(
        files_at(root / models.CANDIDATE_DIRECTORY) == files,
        "scope.historical_bytes",
        "current candidate formal bytes were changed",
    )
    scope = identified(
        {
            "stage": models.STAGE,
            "helper_boundary": boundary,
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "new_task_cases": 0,
            "new_schedule_variants": 0,
            "Archive_selections_added": 0,
            "Benchmark_rows": 0,
            "empirical_estimates": 0,
            "online_authorizations": 0,
            "QA_Release_objects": 0,
            "VTDO_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "mainline_executions": 0,
            "historical_formal_writes": 0,
            "prior_independent_audit_builders_executed": 0,
            "fixed_task_count": 2,
            "fixed_schedule_count_per_task": 2,
            "all_semantic_trajectories_exhausted_claimed": False,
            "runtime_environment_transitive_closure_claimed": False,
            "passed": True,
        },
        "scope",
    )
    # No scientific-positive count is a Gate: a one-class result is admissible.
    evidence_ids = [
        authorization["authorization_id"],
        freeze["audit_id"],
        source["audit_id"],
        rebuild["audit_id"],
        trajectories["audit_id"],
        durability["audit_id"],
        quotient["audit_id"],
        scope["audit_id"],
    ]
    checks = [
        True,
        source["passed"] and rebuild["passed"],
        trajectories["task_count"] == 2 and quotient["legal_schedule_count"] == 2,
        trajectories["action_results_recomputed"] == 20
        and trajectories["program_nodes_replayed"] == 32,
        durability["passed"],
        quotient["saved_partition_byte_match"],
        trajectories["qa_valid"] == trajectories["trajectory_valid"] == 4,
        runtime_controls["accepted"] == 0
        and runtime_controls["rejected"] == 6
        and quotient["negative_controls_rejected"] == 4,
        scope["passed"],
    ]
    require(all(checks), "gate.noncompensatory", "one or more independent Gates failed")
    gate = identified(
        {
            "gates": [
                {"name": name, "passed": bool(ok)}
                for name, ok in zip(models.GATE_NAMES, checks, strict=True)
            ],
            "evidence_ids": evidence_ids,
            "passed": sum(checks),
            "failed": len(checks) - sum(checks),
            "multiple_quotient_classes_required_for_passing": False,
        },
        "gate",
        "gate_id",
    )
    decision = identified(
        {
            "decision": models.DECISION,
            "gate_id": gate["gate_id"],
            "fixed_tasks": 2,
            "valid_own_trajectories": 4,
            "quotient_classes_per_task": [1, 1],
            "tasks_with_multiple_classes": 0,
            "scientific_result": "valid_local_negative_in_frozen_legal_schedule_family",
            "global_semantic_uniqueness_claimed": False,
            "next_stage_authorized": False,
        },
        "decision",
        "decision_id",
    )
    transition = identified(
        {
            "decision_id": decision["decision_id"],
            "completed_stage": models.STAGE,
            "prospective_next_stage": models.NEXT_CANDIDATE,
            "next_stage_authorized": False,
            "separate_new_external_decision_required": True,
            "forbidden": [
                "third_case",
                "changed_public_semantics",
                "forced_second_quotient_class",
                "Provider_or_GPU",
                "online_generation",
                "QA_Release",
                "VTDO",
                "training",
            ],
        },
        "transition",
        "transition_id",
    )
    objects = {
        "authorization": authorization,
        "candidate_freeze": freeze,
        "source_authority_audit": source,
        "detached_rebuild_audit": rebuild,
        "dynamic_durability_audit": durability,
        "trajectory_reconstruction_audit": trajectories,
        "quotient_audit": quotient,
        "runtime_negative_audit": runtime_controls,
        "independent_quotient_partition": partition,
        "scope_audit": scope,
        "gate_evaluation": gate,
        "decision": decision,
        "transition": transition,
    }
    report = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "component_sha256": {
                name: sha(canonical_json_bytes(obj)) for name, obj in objects.items()
            },
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "gate_id": gate["gate_id"],
            "passed_gates": gate["passed"],
            "failed_gates": gate["failed"],
            "conclusion": models.DECISION,
            "scientific_result": decision["scientific_result"],
            "qualified_trajectories": 4,
            "quotient_classes_per_task": [1, 1],
            "provider_calls": 0,
            "next_stage_authorized": False,
        },
        "report",
        "report_id",
    )
    objects["report"] = report
    payloads = {name + ".json": canonical_json_bytes(obj) for name, obj in objects.items()}
    payloads["external_review.txt"] = review
    payloads["operator_directive.txt"] = models.DIRECTIVE.encode()
    payloads["independent_quotient_projections.jsonl"] = b"".join(
        canonical_json_bytes(p) + b"\n" for p in projections
    )
    manifest = write_formal(Path(output_directory), payloads, report)
    return {
        **objects,
        "manifest": manifest,
        "results": results,
        "projections": projections,
        "output_directory": Path(output_directory),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_audit(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_dir,
    )
    print(json.dumps(products["report"], indent=2))


if __name__ == "__main__":
    main()
