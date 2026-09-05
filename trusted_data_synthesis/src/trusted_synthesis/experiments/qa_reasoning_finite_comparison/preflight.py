"""Freeze rules, reread six admitted trajectories, and measure six same-task pairs."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .comparison import compare_family
from .controls import run_projection_controls
from .inputs import (
    DESIGN_DIRECTORY,
    PREDECESSOR,
    REFERENCE_COMMIT,
    files_at,
    git,
    identified,
    load_inputs,
    require,
    revalidate_six,
    sha,
    source_group,
    validate_manifest,
)
from .projection import project_runtime
from .rules import DIRECTIVE, STAGE, authorize, measurement_contract

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_finite_comparison/"
    + name
    for name in (
        "__init__.py",
        "inputs.py",
        "rules.py",
        "projection.py",
        "comparison.py",
        "controls.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "canonical_json.py",
        "core/evidence/schema.py",
        "core/task/realization.py",
    )
)


def helper_boundary() -> dict[str, Any]:
    forbidden = {
        "run_candidate",
        "build_family",
        "source_inventory",
        "build_preflight",
        "run_fixed_fixture",
        "run_negative_controls",
        "execute",
        "send",
        "urlopen",
        "getenv",
        "load_dotenv",
    }
    seen = []
    for path in sorted(Path(__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                require(
                    name not in forbidden,
                    "scope.call_boundary",
                    f"forbidden executable call {name}",
                )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                require(
                    not module.endswith(
                        (
                            "qa_reasoning_candidate_family.runtime",
                            "qa_reasoning_candidate_family.source",
                            "qa_reasoning_candidate_family.preflight",
                        )
                    ),
                    "scope.import_boundary",
                    "candidate constructor/runtime/builder import forbidden",
                )
        seen.append(path.name)
    return {
        "scanned_members": seen,
        "old_runtime_builder_or_candidate_source_calls": 0,
        "network_credential_or_registered_executor_calls": 0,
        "read_only_validator_permitted": True,
        "passed": True,
    }


def implementation_authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return identified(
        {
            "implementation": source_group(root, commit, tree, SOURCE_PATHS),
            "additional_direct_references": source_group(
                root,
                REFERENCE_COMMIT,
                git(root, "rev-parse", f"{REFERENCE_COMMIT}^{{tree}}").decode().strip(),
                REFERENCE_PATHS,
            ),
            "predecessor_declared_26_members_revalidated_in_input_freeze": True,
            "transitive_import_or_runtime_environment_closure_claimed": False,
        },
        "source_authority",
    )


def _jsonl(writer: DurableArtifactWriter, path: str, rows: list[dict[str, Any]]) -> None:
    writer.write_bytes(path, b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def _manifest(writer: DurableArtifactWriter, report_id: str) -> dict[str, Any]:
    files = files_at(writer.root)
    members = [
        {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
        for path, data in sorted(files.items())
    ]
    from trusted_synthesis.canonical_json import strict_canonical_hash

    manifest = identified(
        {
            "members": members,
            "member_count": len(members),
            "member_bytes": sum(map(len, files.values())),
            "self_excluding": True,
            "report_id": report_id,
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_reasoning_finite_comparison_root:"
            ),
        },
        "manifest",
        "manifest_id",
    )
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_comparison(
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
    source = implementation_authority(root, source_commit, source_tree)
    boundary = helper_boundary()
    inputs = load_inputs(root)
    contract = measurement_contract(inputs)
    population = identified(
        {
            "input_freeze_id": inputs["freeze"]["audit_id"],
            "measurement_contract_id": contract["contract_id"],
            "selection": "all six exact previously frozen B/A/C; no reselection",
            "members": [
                {
                    "fixture_id": v["fixture"]["fixture_id"],
                    "task_id": v["fixture"]["task_id"],
                    "candidate_id": v["candidate"]["candidate_id"],
                    "group": v["candidate"]["group"],
                    "population_role": v["row"]["population_role"],
                    "frozen_row_id": v["row"]["row_id"],
                    "frozen_execution_descriptor_sha256": sha(canonical_json_bytes(v["execution"])),
                }
                for v in inputs["selected"]
            ],
            "pair_order": [
                [f, a, b] for f in ("F1", "F2") for a, b in (("B", "C"), ("B", "A"), ("A", "C"))
            ],
            "known_candidates": True,
            "data_blind": False,
            "new_candidate_declarations": 0,
        },
        "measurement_population",
    )
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", DIRECTIVE.encode())
    for name, obj in (
        ("authorization", authorization),
        ("source_authority", source),
        ("input_freeze", inputs["freeze"]),
        ("measurement_contract", contract),
        ("measurement_population", population),
    ):
        writer.write_json(name + ".json", obj)
    receipt = identified(
        {
            "measurement_contract_id": contract["contract_id"],
            "population_id": population["audit_id"],
            "contract_sha256": sha(writer.read_bytes("measurement_contract.json")),
            "population_sha256": sha(writer.read_bytes("measurement_population.json")),
            "durable_rule_write_events": list(writer.events),
            "comparator_calls_before_freeze": 0,
            "candidate_outcomes_already_known": True,
            "outcome_based_rule_revision_permitted": False,
        },
        "rule_freeze_receipt",
    )
    writer.write_json("rule_freeze_receipt.json", receipt)
    rules_before = {
        p: writer.read_bytes(p)
        for p in (
            "measurement_contract.json",
            "measurement_population.json",
            "rule_freeze_receipt.json",
        )
    }
    validations, revalidation = revalidate_six(inputs)
    _jsonl(writer, "input_revalidations.jsonl", validations)
    writer.write_json("input_revalidation_audit.json", revalidation)
    graphs: dict[str, dict[str, Any]] = {"F1": {}, "F2": {}}
    projections: list[dict[str, Any]] = []
    reductions: list[dict[str, Any]] = []
    graph_rows: list[dict[str, Any]] = []
    for item, validation in zip(inputs["selected"], validations, strict=True):
        fixture, execution = item["fixture"], item["execution"]
        graph = project_runtime(
            fixture,
            execution,
            reader=inputs["reader"],
            validation=validation,
            operation_contracts=inputs["operation_contracts"],
        )
        fixture_id, group = fixture["fixture_id"], execution["group"]
        graphs[fixture_id][group] = graph
        projection = identified(
            {
                "measurement_contract_id": contract["contract_id"],
                "candidate_id": execution["candidate_id"],
                "fixture_id": fixture_id,
                "population_role": item["row"]["population_role"],
                "graph": graph,
            },
            "projection",
            "projection_id",
        )
        projections.append(projection)
        writer.write_json(f"projections/{fixture_id}_{group}.json", projection)
        current = graph["normalization"]["reductions"]
        reductions.extend(
            {
                "fixture_id": fixture_id,
                "group": group,
                "projection_id": projection["projection_id"],
                **r,
            }
            for r in current
        )
        graph_rows.append(
            {
                "fixture_id": fixture_id,
                "group": group,
                "projection_id": projection["projection_id"],
                "raw_registered_actions": execution["actual_registered_action_count"],
                "projected_nodes": len(graph["nodes"]),
                "projected_edges": len(graph["edges"]),
                "lookup_instances_checked": len(current),
                "lookup_instances_contractible": sum(r["eligible"] for r in current),
                "input_admitted": graph["admission"]["admitted"],
                "full_public_projection_complete": graph["normalization"]["complete"],
                "issues": graph["normalization"]["issues"],
            }
        )
    projection_audit = identified(
        {
            "measurement_contract_id": contract["contract_id"],
            "rows": graph_rows,
            "lookup_instances_checked": len(reductions),
            "lookup_instances_contractible": sum(r["eligible"] for r in reductions),
            "actual_candidate_executions": 0,
            "original_actions_preserved": 40,
            "original_final_artifacts_preserved": 6,
            "projection_executor_and_oracle_calls": 0,
            "full_public_projection_complete": all(
                r["full_public_projection_complete"] for r in graph_rows
            ),
        },
        "projection_audit",
    )
    _jsonl(writer, "lookup_contraction_witnesses.jsonl", reductions)
    writer.write_json("projection_audit.json", projection_audit)
    require(
        all(writer.read_bytes(p) == b for p, b in rules_before.items()),
        "rules.frozen",
        "rules or measured population changed before comparison",
    )
    family = compare_family(graphs)
    lookup_ids = {
        (p["fixture_id"], p["graph"]["audit"]["group"]): p["projection_id"] for p in projections
    }
    pairs = [
        identified(
            {
                "measurement_contract_id": contract["contract_id"],
                "left_projection_id": lookup_ids[(row["fixture_id"], row["left_group"])],
                "right_projection_id": lookup_ids[(row["fixture_id"], row["right_group"])],
                **row,
            },
            "pair",
            "pair_id",
        )
        for row in family["pairs"]
    ]
    _jsonl(writer, "pair_results.jsonl", pairs)
    comparison = identified(
        {
            "measurement_contract_id": contract["contract_id"],
            "pair_ids": [r["pair_id"] for r in pairs],
            "pair_status_counts": dict(Counter(str(r["status"]) for r in pairs)),
            **{k: v for k, v in family.items() if k != "pairs"},
        },
        "finite_comparison",
    )
    writer.write_json("finite_comparison.json", comparison)
    controls = identified(run_projection_controls(graphs), "projection_controls")
    writer.write_json("projection_controls.json", controls)
    immutable = (
        files_at(root / PREDECESSOR) == inputs["files"]
        and files_at(root / inputs["archive_directory"]) == inputs["archive_files"]
        and files_at(root / DESIGN_DIRECTORY) == inputs["design_files"]
    )
    require(immutable, "scope.frozen_bytes", "a frozen historical input changed")
    require(
        all(writer.read_bytes(p) == b for p, b in rules_before.items()),
        "rules.frozen",
        "post-result rule change",
    )
    scope = identified(
        {
            "stage": STAGE,
            "new_candidate_declarations": 0,
            "new_runtime_executions": 0,
            "old_experiment_builder_calls": 0,
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "new_tasks_or_evidence_or_operations": 0,
            "cross_task_pairs": 0,
            "input_read_only_validations": 6,
            "input_own_route_oracle_nodes": revalidation["own_route_oracle_nodes"],
            "input_answer_oracle_nodes": revalidation["answer_oracle_nodes"],
            "projection_and_comparison_arithmetic_executor_calls": 0,
            "unit_controls_are_projection_only_not_qualified_witnesses": True,
            "historical_formal_bytes_unchanged": immutable,
            "model_owned_reasoning_or_reachability_claimed": False,
            "frequency_Contribution_training_utility_estimates": 0,
            "Mapper_or_State_assignments": 0,
            "QA_release_or_VTDO_or_production_rows": 0,
            "old_mainline": "remains_paused",
            "helper_boundary": boundary,
        },
        "scope",
    )
    writer.write_json("scope.json", scope)
    gates = [
        {"gate": "G0_exact_frozen_own_qualified_input_domain", "status": "PASS"},
        {
            "gate": "G1_source_and_actual_effect_bound_public_projection",
            "status": "PASS" if projection_audit["full_public_projection_complete"] else "UNKNOWN",
        },
        {
            "gate": "G2_six_witnessed_pairs_consistency_and_direct_controls",
            "status": "FAIL"
            if not controls["passed"]
            else ("PASS" if family["comparison_closed"] else "UNKNOWN"),
        },
        {"gate": "G3_no_new_execution_and_scientific_scope_boundary", "status": "PASS"},
    ]
    gate = identified(
        {
            "rows": gates,
            "passed": sum(g["status"] == "PASS" for g in gates),
            "failed": sum(g["status"] == "FAIL" for g in gates),
            "unknown": sum(g["status"] == "UNKNOWN" for g in gates),
            "second_class_is_not_required": True,
            "unknown_is_not_compensated_as_complete": True,
        },
        "gate",
        "gate_id",
    )
    writer.write_json("gate_evaluation.json", gate)
    closed = gate["passed"] == 4 and family["comparison_closed"]
    class_counts = {p["fixture_id"]: p["formal_semantic_class_count"] for p in family["partitions"]}
    if not closed:
        outcome = "finite_public_behavior_comparison_not_closed_explicit_unresolved_locations"
    elif all(n == 1 for n in class_counts.values()):
        outcome = (
            "fixed_family_lookup_forwarding_direct_evidence_and_independent_sc"
            "hedule_one_retained_class_per_task"
        )
    else:
        outcome = (
            "fixed_own_qualified_family_retained_semantic_separation_witnessed"
            "_not_model_reachability"
        )
    decision = identified(
        {
            "stage": STAGE,
            "decision": outcome,
            "gate_id": gate["gate_id"],
            "complete_semantic_comparison": closed,
            "primary_class_counts_by_task": class_counts,
            "schedule_controls_are_not_independent_strategies": True,
            "global_semantic_uniqueness_claim": False,
            "data_blind_confirmation_claim": False,
            "new_model_or_training_result": False,
        },
        "decision",
        "decision_id",
    )
    writer.write_json("decision.json", decision)
    transition = identified(
        {
            "completed_stage": STAGE,
            "decision_id": decision["decision_id"],
            "closed_object": "finite_six_trajectory_semantic_comparison" if closed else None,
            "next_stage_authorized": False,
            "prospective_next_stage": None,
            "separate_new_external_decision_required": True,
            "mechanical_repeat_independent_audit_required": False,
            "stop_expanding_lookup_deletion_direct_reference_label_and_schedule_axes": closed
            and all(n == 1 for n in class_counts.values()),
            "if_undetermined_only_localize_missing_field_or_rule": not closed,
            "old_mainline": "remains_paused",
        },
        "transition",
        "transition_id",
    )
    writer.write_json("transition.json", transition)
    report = identified(
        {
            "stage": STAGE,
            "authorization_id": authorization["authorization_id"],
            "input_freeze_id": inputs["freeze"]["audit_id"],
            "source_authority_id": source["audit_id"],
            "measurement_contract_id": contract["contract_id"],
            "rule_freeze_receipt_id": receipt["audit_id"],
            "input_revalidation_id": revalidation["audit_id"],
            "projection_audit_id": projection_audit["audit_id"],
            "finite_comparison_id": comparison["audit_id"],
            "projection_controls_id": controls["audit_id"],
            "scope_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": outcome,
            "primary_class_counts_by_task": class_counts,
            "comparison_closed": closed,
            "new_candidate_runtime_executions": 0,
            "Provider_calls": 0,
            "scope_limitation": (
                "known finite family only; no global uniqueness, model "
                "reachability, frequencies or training utility"
            ),
        },
        "report",
        "report_id",
    )
    writer.write_json("report.json", report)
    manifest = _manifest(writer, report["report_id"])
    return {
        "writer": writer,
        "authorization": authorization,
        "source_authority": source,
        "input_freeze": inputs["freeze"],
        "contract": contract,
        "receipt": receipt,
        "validations": validations,
        "revalidation": revalidation,
        "graphs": graphs,
        "projection_audit": projection_audit,
        "reductions": reductions,
        "family": family,
        "comparison": comparison,
        "pairs": pairs,
        "controls": controls,
        "scope": scope,
        "gate": gate,
        "decision": decision,
        "transition": transition,
        "report": report,
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("repo-root", "external-audit", "source-commit", "source-tree", "output-dir"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    result = build_comparison(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_dir,
    )
    print(result["decision"]["decision"])
    print(result["manifest"]["manifest_id"])


if __name__ == "__main__":
    main()
