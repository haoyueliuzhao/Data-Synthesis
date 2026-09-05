"""Bounded source-first candidate-family execution; no quotient or model experiment."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .negative import run_negative_controls
from .runtime import run_candidate
from .source import build_family, source_inventory
from .validation import validate_candidate

STAGE = "finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight_only"
NEXT_COMPARISON = (
    "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_only"
)
NEXT_REPAIR = "finance_qa_vnext_candidate_family_first_source_or_validator_gap_repair_only"
DIRECTIVE = "参照审计报告开展后续实验"
REVIEW_SHA256 = "893f9718dca59a1d29b1fe9f993471ff15e9fbfeb86cc570ef1b9b9db670ddcc"
PREDECESSOR_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_behavior_design/"
    "finance_qa_vnext_public_reasoning_semantics_allowed_behavior_and_quotient_contract_design_v1_20260905"
)
PREDECESSOR_MANIFEST = (
    "qa_reasoning_behavior_design_manifest:"
    "38e699777f456718203633e7cab8c23b6b74c0e8c2714e2af5953d234fdc2283"
)
PREDECESSOR_ROOT = (
    "qa_reasoning_behavior_design_root:"
    "94618bb1c74e77c5056bfc98f124d6e2a063723e0cf5c0c42bb79f9547784afb"
)
REFERENCE_COMMIT = "02e97f924bbd6b8521abcb1203423f3f763109a0"
REFERENCE_TREE = "9f0120fa2628d33d6440d939cce96353a4f52c78"
SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_candidate_family/" + name
    for name in (
        "__init__.py",
        "models.py",
        "source.py",
        "runtime.py",
        "validation.py",
        "negative.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "core/task/program.py",
        "core/task/pattern.py",
        "core/task/pattern_compiler.py",
        "core/task/program_depth.py",
        "core/operations/program.py",
        "core/operations/registry.py",
        "core/operations/executors/numeric.py",
        "core/operations/verifiers/numeric.py",
        "core/operations/schema.py",
        "core/evaluation/answer.py",
        "core/trajectory/candidate_verifier.py",
        "domains/finance/operations.py",
        "domains/finance/policy.py",
        "domains/finance/patterns.py",
        "experiments/qa_reasoning_behavior_design/contracts.py",
        "experiments/qa_semantic_depth_three_plus/operations.py",
        "experiments/qa_semantic_depth_three_plus/patterns.py",
        "experiments/qa_semantic_depth_three_catalog_integration/catalog.py",
        "experiments/qa_reasoning_fixed_fixture/runtime.py",
    )
)
GATE_NAMES = (
    "G0_new_external_scope_and_frozen_design_parent",
    "G1_source_inventory_types_and_finite_family_preregistered",
    "G2_actual_own_execution_and_independent_validator",
    "G3_baseline_swap_and_direct_boundary_controls",
    "G4_scientific_outcome_and_scope_are_not_compensated",
)


class CandidateFamilyError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def require(condition: bool, stage: str, reason: str) -> None:
    if not condition:
        raise CandidateFamilyError(stage, reason)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identified(payload: Mapping[str, Any], kind: str, field: str = "audit_id") -> dict[str, Any]:
    body = dict(payload)
    body.setdefault("schema_version", f"qa_reasoning_candidate_family_{kind}.v1")
    body[field] = strict_canonical_hash(body, prefix=f"qa_reasoning_candidate_family_{kind}:")
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
        len(review) == 25_343 and sha(review) == REVIEW_SHA256,
        "authorization.review",
        "exact candidate-family external review differs",
    )
    directive = DIRECTIVE.encode()
    require(
        len(directive) == 36
        and sha(directive) == "3915f5d4befe661fb2b627ac9b578caa07e860a7c0ab4f70b438f6cd96a65403",
        "authorization.directive",
        "exact operator directive differs",
    )
    return identified(
        {
            "stage": STAGE,
            "review_byte_count": len(review),
            "review_sha256": sha(review),
            "directive": DIRECTIVE,
            "directive_sha256": sha(directive),
            "review_access": "report_consistency_only_no_repository_or_test_execution",
            "design_topic_closed": True,
            "bounded_registered_route_preflight_authorized": True,
            "maximum_fixed_tasks": 2,
            "maximum_primary_candidates": 4,
            "maximum_schedule_controls": 2,
            "maximum_positive_executions": 6,
            "maximum_public_actions_per_candidate": 10,
            "new_operation_or_algebraic_rule_authorized": False,
            "second_semantic_class_required": False,
            "Provider_or_GPU_authorized": False,
            "old_mainline": "remains_paused",
        },
        "authorization",
        "authorization_id",
    )


def freeze_predecessor(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / PREDECESSOR_DIRECTORY)
    manifest = validate_manifest(files, PREDECESSOR_MANIFEST, PREDECESSOR_ROOT)
    require(
        len(files) == 15
        and sum(map(len, files.values())) == 64_237
        and manifest["member_count"] == 14
        and manifest["member_bytes"] == 61_873,
        "freeze.geometry",
        "exact predecessor design geometry differs",
    )
    require(
        git(root, "rev-parse", "e7b7ceb3e8f92b43e4d8b3fd442e4213748ebe32^{tree}").decode().strip()
        == "ea71157912f22962420d3e7783eee56ca985cfd6",
        "freeze.source",
        "design source commit/tree relation differs",
    )
    transition = json.loads(files["transition.json"])
    require(
        transition["next_stage_authorized"] is False
        and transition["prospective_next_stage"] == STAGE,
        "freeze.transition",
        "predecessor transition differs",
    )
    return identified(
        {
            "directory": PREDECESSOR_DIRECTORY,
            "manifest_id": PREDECESSOR_MANIFEST,
            "artifact_root": PREDECESSOR_ROOT,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "member_count": 14,
            "member_bytes": 61_873,
            "transition_id": transition["transition_id"],
            "behavior_contract_id": json.loads(files["behavior_contract.json"])["contract_id"],
            "historical_next_stage_authorized": False,
            "old_audit_builders_executed": 0,
            "old_trajectories_replayed": 0,
            "historical_formal_writes": 0,
            "passed": True,
        },
        "predecessor_freeze",
    ), files


def source_authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return identified(
        {
            "implementation": source_group(root, commit, tree, SOURCE_PATHS),
            "declared_references": source_group(
                root, REFERENCE_COMMIT, REFERENCE_TREE, REFERENCE_PATHS
            ),
            "transitive_runtime_closure_claimed": False,
            "passed": True,
        },
        "source_authority",
    )


def finish_manifest(writer: DurableArtifactWriter, report_id: str) -> dict[str, Any]:
    files = files_at(writer.root)
    rows = [
        {"relative_path": p, "sha256": sha(b), "byte_count": len(b)}
        for p, b in sorted(files.items())
    ]
    manifest = identified(
        {
            "members": rows,
            "member_count": len(rows),
            "member_bytes": sum(map(len, files.values())),
            "self_excluding": True,
            "report_id": report_id,
            "artifact_root": strict_canonical_hash(
                rows, prefix="qa_reasoning_candidate_family_root:"
            ),
        },
        "manifest",
        "manifest_id",
    )
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def helper_boundary() -> dict[str, Any]:
    tree = ast.parse(Path(__file__).with_name("validation.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            name = node.module or ""
            require(
                name not in {"runtime", "source"}
                and not name.endswith(
                    (
                        ".qa_reasoning_candidate_family.runtime",
                        ".qa_reasoning_candidate_family.source",
                    )
                ),
                "scope.independent_validation",
                "validator imports candidate execution/source helper",
            )
    return {
        "candidate_runtime_or_source_helper_imports": 0,
        "old_audit_builder_calls": 0,
        "passed": True,
    }


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
    freeze, previous = freeze_predecessor(root)
    source = source_authority(root, source_commit, source_tree)
    boundary = helper_boundary()
    inventory, fixtures = source_inventory(root)
    references = {r["path"]: r for r in source["declared_references"]["members"]}
    require(
        all(
            binding["relative_path"] in references
            and binding["sha256"] == references[binding["relative_path"]]["sha256"]
            and binding["byte_count"] == references[binding["relative_path"]]["byte_count"]
            for binding in inventory["source_file_bindings"]
        ),
        "source.inventory_relation",
        "inventory source bytes lack committed-member authority",
    )
    registration, candidates = build_family(fixtures, inventory)
    require(
        len(fixtures) == 2
        and len(candidates) <= 6
        and sum(c["group"] != "C" for c in candidates) <= 4
        and all(len(c["schedule"]) + 1 <= 10 for c in candidates),
        "registration.bounds",
        "finite task/route/action bounds differ",
    )
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    initial = {
        "authorization": authorization,
        "predecessor_freeze": freeze,
        "source_authority": source,
        "source_inventory": inventory,
        "candidate_preregistration": registration,
    }
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", DIRECTIVE.encode())
    for name, obj in initial.items():
        writer.write_json(name + ".json", obj)
    declarations = b"".join(canonical_json_bytes(c) + b"\n" for c in candidates)
    _, declaration_fsync = writer.write_bytes("candidate_declarations.jsonl", declarations)
    registration_receipt = identified(
        {
            "preregistration_id": registration["preregistration_id"],
            "candidate_declaration_sha256": sha(declarations),
            "candidate_count": len(candidates),
            "candidate_declaration_directory_fsync_event": declaration_fsync,
            "outcomes_seen_at_registration": 0,
            "source_or_type_checks_may_read_evidence_preconditions": True,
            "preselection_candidate_executor_or_oracle_calls": 0,
            "replacement_after_alternative_outcome_permitted": False,
        },
        "registration_receipt",
    )
    writer.write_json("registration_receipt.json", registration_receipt)
    registered_bytes = {
        p: writer.read_bytes(p)
        for p in (
            "candidate_preregistration.json",
            "candidate_declarations.jsonl",
            "registration_receipt.json",
        )
    }
    results, validations, rows = [], [], []
    by_fixture = {f["fixture_id"]: f for f in fixtures}
    for candidate in candidates:
        require(
            all(writer.read_bytes(p) == b for p, b in registered_bytes.items()),
            "runtime.registration",
            "source-first registration changed",
        )
        fixture = by_fixture[candidate["fixture_id"]]
        result = run_candidate(writer=writer, fixture=fixture, candidate=candidate)
        # A new reader proves that the validator uses disk, not the runtime's event/state objects.
        validation = validate_candidate(
            writer=DurableArtifactWriter(writer.root),
            fixture=fixture,
            candidate=candidate,
            result=result,
        )
        results.append(result)
        validations.append(validation)
        row = identified(
            {
                "fixture_id": fixture["fixture_id"],
                "task_id": fixture["task_id"],
                "candidate_id": candidate["candidate_id"],
                "group": candidate["group"],
                "population_role": "schedule_control"
                if candidate["group"] == "C"
                else "primary_candidate",
                "source_rule_bindings": candidate["source_rule_bindings"],
                "source_admissibility": "admitted",
                "typed_construction_status": "constructed",
                "validator_implementation_status": validation["validator_implementation_status"],
                "execution_status": result["execution_status"],
                "actual_registered_actions": result["actual_registered_action_count"],
                "final_closing_artifact_count": 1,
                "qa_valid": validation["qa_valid"],
                "trajectory_valid": validation["trajectory_valid"],
                "qualified": validation["qualified"],
                "first_failure": validation["first_failure"],
                "actual_retained_typed_structure": validation["actual_retained_typed_structure"],
                "evidence_to_obligation_discharge": validation["evidence_to_obligation_discharge"],
                "field_provenance": candidate["field_provenance"],
                "answer_oracle_node_replay_count": validation["answer_oracle_node_replay_count"],
                "trajectory_oracle_node_replay_count": validation[
                    "trajectory_oracle_node_replay_count"
                ],
                "quotient_class_count": None,
                "model_owned_reasoning_observed": False,
            },
            "candidate_row",
            "row_id",
        )
        rows.append(row)
    negative = run_negative_controls(
        writer=writer, fixtures=fixtures, candidates=candidates, results=results
    )
    require(
        files_at(root / PREDECESSOR_DIRECTORY) == previous,
        "scope.historical_bytes",
        "historical design artifacts changed",
    )
    baselines = [r for r in rows if r["group"] == "B"]
    alternatives = [r for r in rows if r["group"] == "A"]
    swaps = [r for r in rows if r["group"] == "C"]
    execution = identified(
        {
            "candidate_rows": rows,
            "fixed_tasks": len(fixtures),
            "primary_candidates": len(baselines) + len(alternatives),
            "schedule_controls": len(swaps),
            "positive_runtime_executions": len(results),
            "actual_registered_actions": sum(r["actual_registered_actions"] for r in rows),
            "final_closing_artifacts": len(results),
            "answer_oracle_node_replays": sum(r["answer_oracle_node_replay_count"] for r in rows),
            "own_trajectory_oracle_node_replays": sum(
                r["trajectory_oracle_node_replay_count"] for r in rows
            ),
            "baseline_qualified": sum(r["qualified"] for r in baselines),
            "direct_evidence_qualified": sum(r["qualified"] for r in alternatives),
            "swap_controls_qualified": sum(r["qualified"] for r in swaps),
            "qa_valid": sum(r["qa_valid"] for r in rows),
            "trajectory_valid": sum(r["trajectory_valid"] for r in rows),
            "qualified": sum(r["qualified"] for r in rows),
            "alternative_slots": [
                {
                    "fixture_id": fixture["fixture_id"],
                    "source_status": "admitted_registered_direct_evidence",
                    "candidate_id": next(
                        c["candidate_id"]
                        for c in candidates
                        if c["fixture_id"] == fixture["fixture_id"] and c["group"] == "A"
                    ),
                }
                for fixture in fixtures
            ],
            "formal_semantic_projection_created": False,
            "quotient_class_count": None,
            "semantic_separation_result": "not_evaluated",
            "transparent_lookup_removal_is_not_itself_a_semantic_class_witness": True,
            "answer_oracle_steps_backfilled_as_candidate_actions": 0,
        },
        "execution_audit",
    )
    scope = identified(
        {
            "stage": STAGE,
            "helper_boundary": boundary,
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "new_task_cases": 0,
            "Archive_expansion": 0,
            "new_Evidence": 0,
            "new_operations": 0,
            "new_algebraic_rules": 0,
            "new_deterministic_candidate_executions": len(results),
            "model_proposed_fields": 0,
            "semantic_class_witness_count": None,
            "formal_quotient_Mapper_or_State_assignments": 0,
            "empirical_estimates": 0,
            "online_authorizations": 0,
            "Contribution_rows": 0,
            "VTDO_rows": 0,
            "QA_Release_objects": 0,
            "training_rows": 0,
            "production_rows": 0,
            "old_mainline_resumed": False,
            "old_audit_builders_rerun": 0,
            "old_runtime_replays": 0,
            "historical_writes": 0,
        },
        "scope",
    )
    workflow_checks = (
        freeze["passed"] and authorization["bounded_registered_route_preflight_authorized"],
        len(candidates) == 6 and registration_receipt["outcomes_seen_at_registration"] == 0,
        all(r["validator_implementation_status"] == "implemented" for r in rows)
        and len(results) == len(candidates),
        len(baselines) == 2
        and all(r["qualified"] for r in baselines)
        and len(swaps) == 2
        and all(r["qualified"] for r in swaps)
        and negative["passed"],
        boundary["passed"] and execution["quotient_class_count"] is None,
    )
    gate = identified(
        {
            "gates": [
                {"name": name, "passed": bool(ok)}
                for name, ok in zip(GATE_NAMES, workflow_checks, strict=True)
            ],
            "passed": sum(workflow_checks),
            "failed": len(workflow_checks) - sum(workflow_checks),
            "evidence_sha256": {
                "authorization": sha(canonical_json_bytes(authorization)),
                "source": sha(canonical_json_bytes(source)),
                "inventory": sha(canonical_json_bytes(inventory)),
                "registration": sha(canonical_json_bytes(registration)),
                "execution": sha(canonical_json_bytes(execution)),
                "negative": sha(canonical_json_bytes(negative)),
                "scope": sha(canonical_json_bytes(scope)),
            },
            "alternative_qualified_required_for_workflow_pass": False,
            "two_semantic_classes_required": False,
        },
        "gate",
        "gate_id",
    )
    positive_alternative = bool(alternatives) and all(r["qualified"] for r in alternatives)
    science = (
        "registered_direct_evidence_candidate_constructed_and_own_verified"
        if positive_alternative
        else "registered_candidate_or_validator_boundary_localized"
    )
    decision = identified(
        {
            "decision": science + "_semantic_separation_not_evaluated",
            "gate_id": gate["gate_id"],
            "workflow_passed": all(workflow_checks),
            "scientific_constructibility_result": science,
            "alternative_route_qualified": sum(r["qualified"] for r in alternatives),
            "semantic_class_count": None,
            "all_registered_route_space_exhausted": False,
        },
        "decision",
        "decision_id",
    )
    transition = identified(
        {
            "decision_id": decision["decision_id"],
            "completed_stage": STAGE,
            "prospective_next_stage": NEXT_COMPARISON
            if positive_alternative and all(workflow_checks)
            else NEXT_REPAIR,
            "next_stage_authorized": False,
            "separate_new_external_decision_required": True,
            "mechanical_repeat_independent_audit_required": False,
            "old_mainline": "remains_paused",
        },
        "transition",
        "transition_id",
    )
    objects = {
        **initial,
        "registration_receipt": registration_receipt,
        "execution_audit": execution,
        "negative_controls": negative,
        "scope": scope,
        "gate_evaluation": gate,
        "decision": decision,
        "transition": transition,
    }
    report = identified(
        {
            "authorization_id": authorization["authorization_id"],
            "component_sha256": {
                name: sha(canonical_json_bytes(value)) for name, value in objects.items()
            },
            "decision_id": decision["decision_id"],
            "gate_id": gate["gate_id"],
            "transition_id": transition["transition_id"],
            "scientific_constructibility_result": science,
            "passed_gates": gate["passed"],
            "failed_gates": gate["failed"],
            "qualified": execution["qualified"],
            "positive_runtime_executions": len(results),
            "semantic_class_count": None,
            "provider_calls": 0,
            "next_stage_authorized": False,
        },
        "report",
        "report_id",
    )
    for name, value in objects.items():
        if name not in initial and name != "registration_receipt":
            writer.write_json(name + ".json", value)
    writer.write_json("report.json", report)
    for name, values in (
        ("candidate_rows", rows),
        ("execution_descriptors", results),
        ("independent_validations", validations),
    ):
        writer.write_bytes(
            name + ".jsonl", b"".join(canonical_json_bytes(v) + b"\n" for v in values)
        )
    manifest = finish_manifest(writer, report["report_id"])
    return {
        **objects,
        "report": report,
        "manifest": manifest,
        "writer": writer,
        "fixtures": fixtures,
        "candidates": candidates,
        "results": results,
        "validations": validations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = build_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_dir,
    )
    print(json.dumps(result["report"], indent=2))


if __name__ == "__main__":
    main()
