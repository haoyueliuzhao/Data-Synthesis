"""Bounded same-Task scheduling experiment with a pre-outcome causal quotient."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture_independent_audit import (
    models as previous,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture_independent_audit import (
    reconstruction as fixture_sources,
)

from . import models
from .quotient import build_quotient_contract, project_quotient
from .runtime import run_trajectory
from .validation import validate_trajectory


class PreflightError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def as_dict(value: Any) -> dict[str, Any]:
    return json.loads(canonical_json_bytes(value))


def files_at(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(("git", "-C", str(root), *args), capture_output=True, check=False)
    if proc.returncode:
        raise PreflightError("source.git", "Git source relation cannot be resolved")
    return proc.stdout


def source_group(root: Path, commit: str, tree: str, paths: tuple[str, ...]) -> dict[str, Any]:
    if (
        git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip() != commit
        or git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip() != tree
    ):
        raise PreflightError("source.commit_tree", "commit/tree relation differs")
    rows = []
    for relative in paths:
        payload = git(root, "show", f"{commit}:{relative}")
        blob = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload, usedforsecurity=False
        ).hexdigest()
        if (root / relative).read_bytes() != payload or (
            git(root, "rev-parse", f"{commit}:{relative}").decode().strip() != blob
        ):
            raise PreflightError("source.member_bytes", f"source differs:{relative}")
        rows.append(
            {
                "path": relative,
                "blob_oid": blob,
                "sha256": sha(payload),
                "byte_count": len(payload),
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


def freeze_directory(
    root: Path, relative: str, manifest_id: str, root_id: str, count: int, byte_count: int
) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / relative)
    manifest = json.loads(files["artifact_manifest.json"])
    rows = manifest["members"]
    paths = [row["relative_path"] for row in rows]
    if (
        len(files) != count
        or sum(map(len, files.values())) != byte_count
        or len(paths) != len(set(paths))
        or set(paths) != set(files) - {"artifact_manifest.json"}
        or manifest["manifest_id"] != manifest_id
        or manifest["artifact_root"] != root_id
        or strict_canonical_hash(
            {k: v for k, v in manifest.items() if k != "manifest_id"},
            prefix=manifest_id.split(":")[0] + ":",
        )
        != manifest_id
        or any(
            row["sha256"] != sha(files[row["relative_path"]])
            or row["byte_count"] != len(files[row["relative_path"]])
            for row in rows
        )
        or manifest["member_bytes"] != sum(len(files[p]) for p in paths)
    ):
        raise PreflightError("freeze.manifest", "formal parent path/byte/identity differs")
    root_prefix = root_id.split(":")[0] + ":"
    if root_id not in (
        strict_canonical_hash(rows, prefix=root_prefix),
        strict_canonical_hash({"members": rows}, prefix=root_prefix),
    ):
        raise PreflightError("freeze.root", "formal parent Root differs")
    return {
        "directory": relative,
        "manifest_id": manifest_id,
        "artifact_root": root_id,
        "file_count": count,
        "total_bytes": byte_count,
        "member_count": len(rows),
        "member_bytes": manifest["member_bytes"],
        "manifest_sha256": sha(files["artifact_manifest.json"]),
    }, files


def authorize(review: bytes) -> dict[str, Any]:
    directive = models.DIRECTIVE.encode()
    if len(review) != models.REVIEW_BYTES or sha(review) != models.REVIEW_SHA256:
        raise PreflightError("authorization.review", "external review differs")
    if len(directive) != 24 or sha(directive) != models.DIRECTIVE_SHA256:
        raise PreflightError("authorization.directive", "operator directive differs")
    return identified(
        {
            "stage": models.STAGE,
            "review_sha256": sha(review),
            "review_bytes": len(review),
            "operator_directive": models.DIRECTIVE,
            "directive_sha256": sha(directive),
            "external_review_access": "report_consistency_only",
            "same_task_multitrajectory_authorized": True,
            "fixed_tasks": 2,
            "candidate_schedules_per_task": 2,
            "Provider_or_GPU_authorized": False,
            "old_mainline_resume_authorized": False,
            "historical_transition_rewrite_authorized": False,
            "schema_version": "qa_reasoning_multitrajectory_authorization.v1",
        },
        "authorization_id",
        "qa_reasoning_multitrajectory_authorization:",
    )


def preregister(
    authorization: dict[str, Any], loaded: tuple[tuple[Any, ...], ...], contract: dict[str, Any]
) -> dict[str, Any]:
    parents = []
    for row, bundle, package, *_ in loaded:
        parents.append(
            {
                "case_id": row["case_id"],
                "row_id": row["row_id"],
                "task_id": package.task.task_id,
                "task_bytes_sha256": sha(canonical_json_bytes(package.task)),
                "package_id": package.realized_package_id,
                "package_bytes_sha256": sha(canonical_json_bytes(package)),
                "bundle_id": bundle.bundle_id,
                "bundle_bytes_sha256": sha(canonical_json_bytes(bundle)),
                "answer_program_id": package.task.oracle.task_program.program_id,
                "schedules": models.SCHEDULES,
            }
        )
    if len(parents) != 2 or tuple(p["row_id"] for p in parents) != previous.SELECTED_ROW_IDS:
        raise PreflightError("registration.tasks", "exact two-task scope differs")
    return identified(
        {
            "authorization_id": authorization["authorization_id"],
            "quotient_contract_id": contract["content_id"],
            "task_parents": parents,
            "schedule_family": "two_topological_orders_of_frozen_D0_D4_execute_actions",
            "outcomes_seen_at_registration": 0,
            "negative_quotient_result_is_permitted": True,
            "all_legal_trajectories_exhausted_claimed": False,
            "schema_version": "qa_reasoning_multitrajectory_preregistration.v1",
        },
        "registration_id",
        "qa_reasoning_multitrajectory_preregistration:",
    )


def partition_tasks(
    results: list[dict[str, Any]], projections: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    task_ids = sorted({as_dict(result["trajectory"])["task_instance_id"] for result in results})
    for task_id in task_ids:
        indices = [
            i
            for i, result in enumerate(results)
            if as_dict(result["trajectory"])["task_instance_id"] == task_id
        ]
        identifiers = [as_dict(results[i]["trajectory"])["trajectory_id"] for i in indices]
        classes = sorted({projections[i]["content_id"] for i in indices})
        rows.append(
            {
                "task_id": task_id,
                "attempted_trajectories": len(indices),
                "qualified_trajectories": sum(
                    bool(results[i]["replay_audit"]["passed"]) for i in indices
                ),
                "trajectory_ids": identifiers,
                "distinct_trajectory_ids": len(set(identifiers)),
                "quotient_ids": [projections[i]["content_id"] for i in indices],
                "distinct_quotient_classes": len(classes),
                "multiple_quotient_classes_witnessed": len(classes) >= 2,
                "interpretation": "local_deterministic_multiclass_witness"
                if len(classes) >= 2
                else "no_multiclass_witness_in_preregistered_schedule_family",
            }
        )
    return identified(
        {
            "rows": rows,
            "task_count": len(rows),
            "qualified_trajectories": sum(row["qualified_trajectories"] for row in rows),
            "tasks_with_multiple_classes": sum(
                row["multiple_quotient_classes_witnessed"] for row in rows
            ),
            "cross_task_class_count_is_not_same_task_support": True,
            "model_probabilities_estimated": False,
            "schema_version": "qa_reasoning_multitrajectory_partition.v1",
        },
        "audit_id",
        "qa_reasoning_multitrajectory_partition:",
    )


def negative_controls(
    writer: DurableArtifactWriter,
    results: list[dict[str, Any]],
    loaded: tuple[tuple[Any, ...], ...],
    contract: dict[str, Any],
) -> dict[str, Any]:
    controls = []

    def reject(name: str, callback: Any) -> None:
        try:
            callback()
        except (ValueError, FileExistsError) as error:
            controls.append(
                {
                    "name": name,
                    "rejected": True,
                    "exception": type(error).__name__,
                    "stage": getattr(error, "stage", "schema_admission"),
                }
            )
        else:
            raise PreflightError("controls.accepted", f"control unexpectedly accepted:{name}")

    modified_contract = copy.deepcopy(contract)
    modified_contract["outcome_selected_rule"] = "keep_schedule_to_force_two_classes"
    modified_contract["content_id"] = strict_canonical_hash(
        {k: v for k, v in modified_contract.items() if k != "content_id"},
        prefix="qa_reasoning_multitrajectory_quotient_contract:",
    )
    reject(
        "post_outcome_quotient_rule_substitution",
        lambda: project_quotient(results[0], modified_contract),
    )
    invalid = copy.deepcopy(results[0])
    invalid["replay_audit"] = {"passed": False}
    reject("unverified_trajectory_quotient_admission", lambda: project_quotient(invalid, contract))
    # Source-specific runtime mutations are made only in scratch copies.
    mutations = (
        ("missing_durable_receipt", "preaction_commit_receipt", "remove"),
        ("rehashed_single_observation_wrong_result", "observation", "payload"),
        ("rehashed_single_envelope_future_evidence", "envelope", "future"),
        ("rehashed_single_update_cross_task", "update", "cross_task"),
        ("rehashed_single_execution_wrong_action", "action_execution", "action"),
    )
    for name, suffix, kind in mutations:
        with TemporaryDirectory(prefix="qa-multitrajectory-control-") as temporary:
            scratch = Path(temporary) / "copy"
            shutil.copytree(writer.root / "runtime", scratch / "runtime")
            target = next(
                p
                for p in sorted(scratch.rglob(f"step_00*_{suffix}.json"))
                if "fixture_1" in p.as_posix()
            )
            if kind == "remove":
                target.rename(target.with_suffix(".withheld"))
            else:
                obj = json.loads(target.read_bytes())
                identity_field, prefix = {
                    "payload": ("observation_id", "public_reasoning_observation:"),
                    "future": ("envelope_id", "reasoning_action_envelope:"),
                    "cross_task": ("update_id", "observation_update:"),
                    "action": ("execution_id", "reasoning_action_execution:"),
                }[kind]
                if kind == "payload":
                    obj["public_payload"]["comparable"] = False
                    obj["public_payload_hash"] = sha(canonical_json_bytes(obj["public_payload"]))
                elif kind == "future":
                    obj["evidence_refs"].append("evidence:future_unobserved")
                elif kind == "cross_task":
                    obj["task_instance_id"] = loaded[1][2].task.task_id
                else:
                    obj["action_id"] = "action:unselected"
                obj[identity_field] = strict_canonical_hash(
                    {k: v for k, v in obj.items() if k != identity_field}, prefix=prefix
                )
                target.write_bytes(canonical_json_bytes(obj))
            scratch_writer = DurableArtifactWriter(scratch)
            scratch_writer.events = copy.deepcopy(writer.events)
            reject(
                name,
                lambda sw=scratch_writer: validate_trajectory(
                    writer=sw, result=results[0], loaded=loaded[0]
                ),
            )
    duplicate = results[0]["receipts"][0]
    original = writer.read_bytes(as_dict(duplicate)["envelope_relative_path"])
    reject(
        "no_replace_original_envelope",
        lambda: writer.write_bytes(as_dict(duplicate)["envelope_relative_path"], b"replacement"),
    )
    if writer.read_bytes(as_dict(duplicate)["envelope_relative_path"]) != original:
        raise PreflightError("controls.no_replace", "original bytes changed")
    return identified(
        {
            "controls": controls,
            "attempted": len(controls),
            "rejected": len(controls),
            "accepted": 0,
            "formal_attack_writes": 0,
            "Provider_calls": 0,
            "schema_version": "qa_reasoning_multitrajectory_negative_audit.v1",
        },
        "audit_id",
        "qa_reasoning_multitrajectory_negative_audit:",
    )


def build_preflight(
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
    freeze, predecessor_files = freeze_directory(
        root,
        models.PREDECESSOR_DIRECTORY,
        models.PREDECESSOR_MANIFEST,
        models.PREDECESSOR_ROOT,
        24,
        198_117,
    )
    transition = json.loads(predecessor_files["transition.json"])
    decision = json.loads(predecessor_files["decision.json"])
    if (
        transition["transition_id"] != models.PREDECESSOR_TRANSITION
        or transition["next_stage_authorized"] is not False
        or decision["decision_id"] != models.PREDECESSOR_DECISION
    ):
        raise PreflightError("freeze.transition", "historical decision/transition differs")
    candidate, _ = freeze_directory(
        root,
        previous.CANDIDATE_DIRECTORY,
        previous.CANDIDATE_MANIFEST_ID,
        previous.CANDIDATE_ROOT_ID,
        88,
        217_567,
    )
    archive, _ = freeze_directory(
        root,
        previous.ARCHIVE_DIRECTORY,
        previous.ARCHIVE_MANIFEST_ID,
        previous.ARCHIVE_ROOT_ID,
        24,
        784_989,
    )
    source = identified(
        {
            "implementation": source_group(root, source_commit, source_tree, models.SOURCE_PATHS),
            "retained_helpers": source_group(
                root,
                models.PREDECESSOR_SOURCE_COMMIT,
                models.PREDECESSOR_SOURCE_TREE,
                models.REUSED_SOURCE_PATHS,
            ),
            "transitive_runtime_closure_claimed": False,
            "schema_version": "qa_reasoning_multitrajectory_source.v1",
        },
        "binding_id",
        "qa_reasoning_multitrajectory_source:",
    )
    selection, loaded = fixture_sources.select_and_load_archive_fixtures(
        root / previous.ARCHIVE_DIRECTORY
    )
    quotient_contract = build_quotient_contract()
    registration = preregister(authorization, loaded, quotient_contract)
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    for name, payload in (
        ("external_review.txt", review),
        ("operator_directive.txt", models.DIRECTIVE.encode()),
    ):
        writer.write_bytes(name, payload)
    initial_objects = {
        "authorization": authorization,
        "predecessor_freeze": freeze,
        "fixed_fixture_freeze": candidate,
        "archive_freeze": archive,
        "source_binding": source,
        "selection_audit": selection,
        "quotient_contract": quotient_contract,
        "preregistration": registration,
    }
    for name, obj in initial_objects.items():
        writer.write_json(name + ".json", obj)
    registration_event = len(writer.events)
    results = []
    projections = []
    replay_audits = []
    for fixture_index, fixture in enumerate(loaded, 1):
        for schedule_index, schedule in enumerate(models.SCHEDULES, 1):
            prefix = f"runtime/fixture_{fixture_index}/schedule_{schedule_index}"
            result = run_trajectory(
                writer=writer,
                runtime_prefix=prefix,
                loaded=fixture,
                schedule=schedule,
            )
            replay = validate_trajectory(writer=writer, result=result, loaded=fixture)
            result["replay_audit"] = replay
            if not replay["passed"]:
                raise PreflightError("replay.invalid", "fresh trajectory did not qualify")
            projection = project_quotient(result, quotient_contract)
            results.append(result)
            projections.append(projection)
            replay_audits.append(replay)
    partition = partition_tasks(results, projections)
    controls = negative_controls(writer, results, loaded, quotient_contract)
    callbacks = [event for event in writer.events if event["kind"] == "action_dispatch"]
    precommit_order = all(row["event_ordinal"] > registration_event for row in callbacks)
    if writer.read_bytes("quotient_contract.json") != canonical_json_bytes(quotient_contract):
        raise PreflightError("registration.changed", "quotient changed after execution")
    if writer.read_bytes("preregistration.json") != canonical_json_bytes(registration):
        raise PreflightError("registration.changed", "schedule family changed after execution")
    runtime_files = files_at(writer.root / "runtime")
    depth_rows = [as_dict(result["depth"]) for result in results]
    scope = identified(
        {
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "archive_expansion": 0,
            "new_tasks": 0,
            "new_operations": 0,
            "third_fixture": 0,
            "old_mainline_resumed": False,
            "model_generated_trajectories": 0,
            "same_task_deterministic_trajectories": len(results),
            "QA_Release": 0,
            "Mapper": 0,
            "VTDO_State": 0,
            "Contribution": 0,
            "VTDO": 0,
            "training": 0,
            "production": 0,
            "schema_version": "qa_reasoning_multitrajectory_scope.v1",
        },
        "audit_id",
        "qa_reasoning_multitrajectory_scope:",
    )
    predicates = (
        True,
        len(loaded) == 2,
        precommit_order,
        len(callbacks) == 20 and len(runtime_files) == 124,
        len(replay_audits) == 4 and all(a["passed"] for a in replay_audits),
        all(
            (
                d["semantic_operation_depth"],
                d["reasoning_depth"],
                d["evidence_integration_depth"],
                d["correction_depth"],
                d["critical_decision_coverage"],
            )
            == (3, 4, 4, 0, 1.0)
            for d in depth_rows
        ),
        len(partition["rows"]) == 2
        and all(r["qualified_trajectories"] == 2 for r in partition["rows"]),
        controls["attempted"] == controls["rejected"] == 8,
        scope["Provider_calls"] == scope["GPU_jobs"] == scope["new_tasks"] == 0,
    )
    gate = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "source_binding_id": source["binding_id"],
            "preregistration_id": registration["registration_id"],
            "quotient_contract_id": quotient_contract["content_id"],
            "partition_audit_id": partition["audit_id"],
            "independent_replay_audit_ids": [a["audit_id"] for a in replay_audits],
            "negative_audit_id": controls["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gates": dict(zip(models.GATE_NAMES, predicates, strict=True)),
            "passed": sum(predicates),
            "failed": len(predicates) - sum(predicates),
            "noncompensatory": True,
            "multiple_quotient_classes_is_scientific_outcome_not_workflow_gate": True,
            "schema_version": "qa_reasoning_multitrajectory_gate.v1",
        },
        "gate_id",
        "qa_reasoning_multitrajectory_gate:",
    )
    if not all(predicates):
        raise PreflightError("gate.failed", "same-task preflight gate failed")
    outcome = (
        "local_deterministic_same_task_multiple_quotient_classes_witnessed"
        if partition["tasks_with_multiple_classes"]
        else "no_same_task_multiple_quotient_classes_witnessed_in_frozen_schedule_family"
    )
    decision = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "gate_id": gate["gate_id"],
            "partition_id": partition["audit_id"],
            "scientific_outcome": outcome,
            "preflight_completed": True,
            "independent_audit_required": True,
            "model_reachability_established": False,
            "schema_version": "qa_reasoning_multitrajectory_decision.v1",
        },
        "decision_id",
        "qa_reasoning_multitrajectory_decision:",
    )
    successor = identified(
        {
            "decision_id": decision["decision_id"],
            "prospective_next_stage": models.NEXT_STAGE,
            "next_stage_authorized": False,
            "separate_external_decision_required": True,
            "Provider_authorized": False,
            "old_mainline_resume_authorized": False,
            "schema_version": "qa_reasoning_multitrajectory_transition.v1",
        },
        "transition_id",
        "qa_reasoning_multitrajectory_transition:",
    )
    report = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "source_binding_id": source["binding_id"],
            "preregistration_id": registration["registration_id"],
            "predecessor_manifest_id": models.PREDECESSOR_MANIFEST,
            "predecessor_decision_id": models.PREDECESSOR_DECISION,
            "predecessor_transition_id": models.PREDECESSOR_TRANSITION,
            "archive_root": archive["artifact_root"],
            "independent_replay_audit_ids": [a["audit_id"] for a in replay_audits],
            "scope_audit_id": scope["audit_id"],
            "quotient_contract_id": quotient_contract["content_id"],
            "partition_id": partition["audit_id"],
            "negative_id": controls["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": successor["transition_id"],
            "scientific_outcome": outcome,
            "task_count": 2,
            "trajectory_count": len(results),
            "runtime_file_count": len(runtime_files),
            "durable_callback_count": len(callbacks),
            "Program_nodes_replayed": sum(
                a["program_nodes_independently_replayed"] for a in replay_audits
            ),
            "registered_before_first_callback": precommit_order,
            "tasks_with_multiple_quotient_classes": partition["tasks_with_multiple_classes"],
            "Provider_calls": 0,
            "passed_gates": gate["passed"],
            "failed_gates": gate["failed"],
            "schema_version": "qa_reasoning_multitrajectory_report.v1",
        },
        "report_id",
        "qa_reasoning_multitrajectory_report:",
    )
    output_objects = {
        "quotient_partition": partition,
        "negative_audit": controls,
        "scope_audit": scope,
        "gate_evaluation": gate,
        "decision": decision,
        "transition": successor,
        "report": report,
    }
    for name, obj in output_objects.items():
        writer.write_json(name + ".json", obj)
    for name, values in {
        "reasoning_trajectories": [r["trajectory"] for r in results],
        "answer_validity": [r["answer_validity"] for r in results],
        "trajectory_validity": [r["trajectory_validity"] for r in results],
        "qualified_trajectories": [r["qualification"] for r in results],
        "critical_decision_graphs": [r["graph"] for r in results[::2]],
        "answer_oracle_bindings": [r["oracle"] for r in results[::2]],
        "program_executions": [r["core"]["execution"] for r in results],
        "verification_reports": [r["core"]["verification"] for r in results],
        "quality_assessments": [r["core"]["assessment"] for r in results],
        "durable_observations": [o for r in results for o in r["durable_observations"]],
        "depth_metrics": depth_rows,
        "independent_replays": replay_audits,
        "quotient_projections": projections,
        "runtime_events": writer.events.copy(),
    }.items():
        writer.write_bytes(
            name + ".jsonl", b"".join(canonical_json_bytes(value) + b"\n" for value in values)
        )
    payloads = files_at(writer.root)
    members = [
        {"relative_path": path, "sha256": sha(payload), "byte_count": len(payload)}
        for path, payload in sorted(payloads.items())
    ]
    manifest = identified(
        {
            "report_id": report["report_id"],
            "members": members,
            "self_excluding": True,
            "member_count": len(members),
            "member_bytes": sum(map(len, payloads.values())),
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_reasoning_multitrajectory_root:"
            ),
            "schema_version": "qa_reasoning_multitrajectory_manifest.v1",
        },
        "manifest_id",
        "qa_reasoning_multitrajectory_manifest:",
    )
    writer.write_json("artifact_manifest.json", manifest)
    return {
        **initial_objects,
        **output_objects,
        "manifest": manifest,
        "results": results,
        "projections": projections,
        "writer": writer,
        "loaded": loaded,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_dir,
    )
    print(json.dumps(products["report"], indent=2))


if __name__ == "__main__":
    main()
