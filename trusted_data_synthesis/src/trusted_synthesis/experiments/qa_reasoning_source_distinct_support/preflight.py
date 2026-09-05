"""Complete the bounded source branch; do not manufacture absent execution inputs."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    git,
    sha,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from . import models
from .contracts import inspect_registry
from .models import UninstantiatedDecision, identified, require
from .source import ARCHIVE_PATH, scan_archive, selection_policy

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_source_distinct_support/"
    + name
    for name in ("__init__.py", "models.py", "contracts.py", "source.py", "preflight.py")
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "canonical_json.py",
        "core/operations/registry.py",
        "core/operations/schema.py",
        "core/operations/executors/numeric.py",
        "core/operations/verifiers/numeric.py",
        "domains/finance/operations.py",
        "experiments/qa_semantic_depth_three_plus/operations.py",
        "experiments/qa_semantic_depth_three_catalog_integration/catalog.py",
        "experiments/qa_reasoning_finite_comparison/inputs.py",
        "experiments/qa_reasoning_fixed_fixture/runtime.py",
    )
)


def authorization(review: bytes) -> dict[str, Any]:
    require(
        len(review) == models.REVIEW_BYTES and sha(review) == models.REVIEW_SHA256,
        "authorization.review",
        "exact source-distinct-support external review differs",
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
            "review_byte_count": len(review),
            "operator_directive": models.DIRECTIVE,
            "directive_sha256": sha(directive),
            "review_access": (
                "report_review_public_decimal_recalculation_no_repository_artifact_replay"
            ),
            "closed_predecessor_topic": "fixed_six_trajectory_finite_public_behavior_comparison",
            "maximum_new_tasks": 1,
            "maximum_new_candidate_runtime_executions": 2,
            "runtime_requires_complete_source_and_shared_contract_admission": True,
            "one_bounded_existing_archive_inspection_only": True,
            "no_source_means_uninstantiated_not_substitution_or_unbounded_search": True,
            "Provider_credential_GPU_limits": [0, 0, 0],
            "benchmark_training_Release_or_VTDO_permission": False,
            "old_mainline": "remains_paused",
        },
        "authorization",
        "authorization_id",
    )


def freeze_parent(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / models.PREDECESSOR)
    manifest = validate_manifest(files, models.PREDECESSOR_MANIFEST, models.PREDECESSOR_ROOT)
    require(
        len(files) == 27
        and sum(map(len, files.values())) == 8_384_212
        and manifest["member_count"] == 26
        and manifest["member_bytes"] == 8_380_170,
        "freeze.geometry",
        "frozen finite-comparison directory differs",
    )
    require(
        git(root, "rev-parse", f"{models.PREDECESSOR_COMMIT}^{{tree}}").decode().strip()
        == models.PREDECESSOR_TREE,
        "freeze.source",
        "predecessor exact source commit/tree differs",
    )
    report, decision, transition, gate = (
        json.loads(files[name + ".json"])
        for name in ("report", "decision", "transition", "gate_evaluation")
    )
    require(
        decision["primary_class_counts_by_task"] == {"F1": 1, "F2": 1}
        and gate["passed"] == 4
        and gate["failed"] == gate["unknown"] == 0
        and transition["next_stage_authorized"] is False
        and transition["stop_expanding_lookup_deletion_direct_reference_label_and_schedule_axes"]
        is True,
        "freeze.decision",
        "closed historical decision or boundary differs",
    )
    return identified(
        {
            "directory": models.PREDECESSOR,
            "manifest_id": models.PREDECESSOR_MANIFEST,
            "artifact_root": models.PREDECESSOR_ROOT,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "member_count": 26,
            "member_bytes": 8_380_170,
            "source_commit": models.PREDECESSOR_COMMIT,
            "source_tree": models.PREDECESSOR_TREE,
            "report_id": report["report_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "historical_classes_by_task": {"F1": 1, "F2": 1},
            "historical_next_stage_authorized": False,
            "old_builder_runtime_validator_or_comparator_calls": 0,
            "historical_formal_writes": 0,
            "passed": True,
        },
        "predecessor_freeze",
    ), files


def helper_boundary() -> dict[str, Any]:
    forbidden_calls = {
        "run_candidate",
        "build_family",
        "source_inventory",
        "build_comparison",
        "load_inputs",
        "revalidate_six",
        "validate_candidate",
        "compare_graphs",
        "compare_family",
        "execute",
        "verify",
        "derive_expected",
        "urlopen",
        "send",
        "getenv",
        "load_dotenv",
        "make_program",
    }
    paths = sorted(Path(__file__).parent.glob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                require(
                    name not in forbidden_calls,
                    "scope.source_only",
                    f"execution call forbidden in source-only branch: {name}",
                )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                require(
                    not module.endswith(
                        (
                            "qa_reasoning_candidate_family.runtime",
                            "qa_reasoning_candidate_family.source",
                            "qa_reasoning_candidate_family.validation",
                            "qa_reasoning_finite_comparison.preflight",
                            "qa_reasoning_finite_comparison.comparison",
                        )
                    ),
                    "scope.imports",
                    "old experimental execution helper imported",
                )
    return {
        "scanned_members": [p.name for p in paths],
        "forbidden_experimental_calls": 0,
        "passed": True,
    }


def null_boundary_controls(base: dict[str, Any]) -> dict[str, Any]:
    cases = []
    for name, patch in (
        ("missing_source_is_not_W_zero", {"scientific_witness": 0}),
        ("missing_source_is_not_W_one", {"scientific_witness": 1}),
        ("missing_source_is_not_one_class", {"formal_semantic_class_count": 1}),
        ("missing_source_is_not_runtime_execution", {"candidate_runtime_executions": 1}),
        ("missing_source_is_not_two_route_success", {"two_route_constructibility_passed": True}),
    ):
        try:
            UninstantiatedDecision.model_validate({**base, **patch})
        except ValidationError as error:
            rejected = True
            reasons = [
                {"location": list(row["loc"]), "type": row["type"]} for row in error.errors()
            ]
        else:
            rejected, reasons = False, []
        cases.append(
            {
                "name": name,
                "rejected": rejected,
                "schema_reasons": reasons,
                "scope": "source_result_schema_control_not_financial_runtime_attack",
                "new_task_or_runtime_or_class_witness": False,
            }
        )
    return identified(
        {
            "cases": cases,
            "attempted": len(cases),
            "rejected": sum(row["rejected"] for row in cases),
            "passed": all(row["rejected"] for row in cases),
            "uninstantiated_runtime_controls_executed": 0,
        },
        "null_boundary_controls",
    )


def _jsonl(writer: DurableArtifactWriter, name: str, rows: list[dict[str, Any]]) -> None:
    writer.write_bytes(name, b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def finish_manifest(writer: DurableArtifactWriter, report_id: str) -> dict[str, Any]:
    files = files_at(writer.root)
    members = [
        {"relative_path": p, "sha256": sha(data), "byte_count": len(data)}
        for p, data in sorted(files.items())
    ]
    manifest = identified(
        {
            "members": members,
            "member_count": len(members),
            "member_bytes": sum(map(len, files.values())),
            "self_excluding": True,
            "report_id": report_id,
            "artifact_root": strict_canonical_hash(
                members, prefix="qa_source_distinct_support_root:"
            ),
        },
        "manifest",
        "manifest_id",
    )
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


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
    auth = authorization(review)
    freeze, old_files = freeze_parent(root)
    source = identified(
        {
            "implementation": source_group(root, source_commit, source_tree, SOURCE_PATHS),
            "declared_references": source_group(
                root, models.REFERENCE_COMMIT, models.REFERENCE_TREE, REFERENCE_PATHS
            ),
            "archive_git_member": source_group(
                root, models.REFERENCE_COMMIT, models.REFERENCE_TREE, (ARCHIVE_PATH,)
            ),
            "transitive_import_or_runtime_environment_closure_claimed": False,
        },
        "source_authority",
    )
    boundary = helper_boundary()
    policy = identified(
        {
            "policy": selection_policy(),
            "external_authorization_id": auth["authorization_id"],
            "known_page_annotations_are_not_blind_discovery": True,
            "formal_rebuild_reproduces_the_one_completed_source_inspection": True,
        },
        "source_policy",
    )
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", models.DIRECTIVE.encode())
    for name, obj in (
        ("authorization", auth),
        ("predecessor_freeze", freeze),
        ("source_authority", source),
        ("source_policy", policy),
    ):
        writer.write_json(name + ".json", obj)
    receipt = identified(
        {
            "policy_id": policy["audit_id"],
            "policy_sha256": sha(writer.read_bytes("source_policy.json")),
            "write_events": list(writer.events),
            "source_replay_started": False,
            "candidate_outcomes_seen": 0,
            "known_source_annotations": True,
        },
        "policy_freeze_receipt",
    )
    writer.write_json("policy_freeze_receipt.json", receipt)
    frozen_policy = writer.read_bytes("source_policy.json")
    census = scan_archive(root)
    require(
        census["status"] == "source_not_instantiated"
        and census["fully_instantiated_binding_count"] == 0
        and census["selected_binding"] is None
        and census["scientific_witness"] is None
        and census["same_report_income_check"]["income_source_hit_count"] == 0,
        "source.branch",
        "the admitted source-only branch no longer matches actual source findings",
    )
    registry = inspect_registry(root)
    writer.write_json("primitive_contract_inspection.json", registry)
    _jsonl(writer, "archive_record_catalog.jsonl", census["record_catalog"])
    _jsonl(writer, "candidate_source_dispositions.jsonl", census["candidate_dispositions"])
    _jsonl(writer, "source_relation_witnesses.jsonl", census["source_relation_witnesses"])
    writer.write_json("same_report_income_check.json", census["same_report_income_check"])
    summary = identified(
        {
            k: v
            for k, v in census.items()
            if k
            not in (
                "record_catalog",
                "candidate_dispositions",
                "source_relation_witnesses",
                "same_report_income_check",
            )
        },
        "source_census_summary",
    )
    writer.write_json("source_census_summary.json", summary)
    domain = UninstantiatedDecision(
        supported_revenue_partition_pages=census["source_relation_witness_count"],
        missing_required_roles=("income_earlier", "income_later"),
        scope_qualified_missing_fact=(
            "Real two-component revenue source relations are present, but no complete "
            "two-period operating-income binding is supplied by the admitted same-report "
            "table/text source domain."
        ),
    ).model_dump(mode="python")
    null_controls = null_boundary_controls(domain)
    writer.write_json("null_boundary_controls.json", null_controls)
    require(
        null_controls["passed"],
        "gate.null_boundary",
        "source absence admitted a fabricated scientific result",
    )
    immutable = (
        files_at(root / models.PREDECESSOR) == old_files
        and sha((root / ARCHIVE_PATH).read_bytes()) == census["archive_sha256"]
    )
    require(
        immutable and writer.read_bytes("source_policy.json") == frozen_policy,
        "scope.immutable",
        "historical input or fixed source policy changed",
    )
    scope = identified(
        {
            "stage": models.STAGE,
            "source_inspection_scope_completed": True,
            "two_route_experiment_instantiated": False,
            "new_task_instances": 0,
            "new_candidate_declarations": 0,
            "new_qa_evidence_bundles": 0,
            "candidate_runtime_executions": 0,
            "own_validations": 0,
            "finite_comparisons": 0,
            "primitive_executor_calls": 0,
            "primitive_oracle_calls": 0,
            "Provider_calls": 0,
            "credential_lookups": 0,
            "GPU_jobs": 0,
            "new_primitive_or_catalog_registration": 0,
            "external_source_reads": 0,
            "deprecated_raw_financial_data_lake_reads": 0,
            "benchmark_qa_gold_fields_used_for_selection": False,
            "whole_archive_container_read_for_hash_and_source_projection": True,
            "benchmark_frequency_or_model_probability_estimates": 0,
            "new_online_authorizations": 0,
            "QA_release_VTDO_training_production_rows": 0,
            "old_mainline": "remains_paused",
            "historical_formal_bytes_unchanged": immutable,
            "helper_boundary": boundary,
        },
        "scope",
    )
    writer.write_json("scope.json", scope)
    gate = identified(
        {
            "rows": [
                {"gate": "G0_exact_external_scope_and_closed_predecessor_freeze", "status": "PASS"},
                {
                    "gate": "G1_fixed_archive_source_census_and_evidence_of_missing_roles",
                    "status": "PASS",
                },
                {"gate": "G2_one_complete_new_task_support_binding", "status": "NOT_INSTANTIATED"},
                {
                    "gate": "G3_two_own_qualified_routes_and_finite_separation",
                    "status": "NOT_RUN_SOURCE_UNAVAILABLE",
                },
                {"gate": "G4_null_witness_and_zero_execution_boundary", "status": "PASS"},
            ],
            "passed": 3,
            "failed": 0,
            "not_instantiated": 1,
            "not_run": 1,
            "complete_two_route_preflight_passed": False,
            "source_branch_completed_as_scoped": True,
            "not_instantiated_is_not_W_zero_or_multi_class_success": True,
        },
        "gate",
        "gate_id",
    )
    writer.write_json("gate_evaluation.json", gate)
    decision = identified(
        {
            **domain,
            "gate_id": gate["gate_id"],
            "source_census_id": summary["audit_id"],
            "decision": "source_not_instantiated_required_two_period_operating_income_unbound",
        },
        "decision",
        "decision_id",
    )
    writer.write_json("decision.json", decision)
    transition = identified(
        {
            "completed_stage": models.STAGE,
            "decision_id": decision["decision_id"],
            "completed_scope": (
                "one_bounded_existing_archive_source_inspection_and_gap_localization"
            ),
            "new_support_route_experiment_instantiated": False,
            "next_stage_authorized": False,
            "prospective_next_stage": None,
            "new_external_scope_decision_required": True,
            "unresolved_facts": ["two_period_operating_income_for_the_supported_revenue_partition"],
            "external_source_supplement_or_task_redesign_not_executed": True,
            "repeat_closed_lookup_label_schedule_axes": False,
            "mechanical_repeat_independent_audit_required": False,
            "old_mainline": "remains_paused",
        },
        "transition",
        "transition_id",
    )
    writer.write_json("transition.json", transition)
    report = identified(
        {
            "stage": models.STAGE,
            "authorization_id": auth["authorization_id"],
            "predecessor_freeze_id": freeze["audit_id"],
            "source_authority_id": source["audit_id"],
            "source_policy_id": policy["audit_id"],
            "source_census_id": summary["audit_id"],
            "primitive_contract_inspection_id": registry["audit_id"],
            "null_controls_id": null_controls["audit_id"],
            "scope_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "status": "source_not_instantiated",
            "scientific_witness": None,
            "formal_semantic_class_count": None,
            "source_records": census["archive_record_count"],
            "structural_candidate_records": census["structural_candidate_count"],
            "unique_candidate_pages": census["unique_candidate_source_page_count"],
            "supported_revenue_partition_pages": census["source_relation_witness_count"],
            "same_report_records_checked_for_income": census["same_report_income_check"][
                "source_record_count"
            ],
            "new_task_instances": 0,
            "new_candidate_runtime_executions": 0,
            "source_branch_complete": True,
            "two_route_experiment_complete": False,
            "scope_limitation": (
                "Known source annotations and the fixed exactly-two-component table/text adapter; "
                "not global source absence or nonexistence of distinct valid behaviors."
            ),
        },
        "report",
        "report_id",
    )
    writer.write_json("report.json", report)
    manifest = finish_manifest(writer, report["report_id"])
    return {
        "writer": writer,
        "authorization": auth,
        "freeze": freeze,
        "source_authority": source,
        "policy": policy,
        "receipt": receipt,
        "census": census,
        "summary": summary,
        "registry": registry,
        "null_controls": null_controls,
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
    result = build_preflight(
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
