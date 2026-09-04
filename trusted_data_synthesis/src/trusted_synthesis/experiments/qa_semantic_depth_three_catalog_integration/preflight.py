from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task.program_depth import (
    admit_program_depth_metrics,
    derive_program_depth_metrics,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy

from . import models
from .catalog import (
    CatalogAdmissionError,
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    catalog_manifest_sha256,
    historical_catalog_snapshot,
    validate_catalog_rows,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", "-C", str(root), *arguments), check=True, capture_output=True
    ).stdout


def _git_text(root: Path, *arguments: str) -> str:
    return _git(root, *arguments).decode("ascii").strip()


def _authorization(review: bytes) -> tuple[dict[str, Any], bytes]:
    if len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT or _sha(review) != (
        models.EXTERNAL_REVIEW_SHA256
    ):
        raise ValueError("external registered-Catalog audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT or _sha(directive) != (
        models.OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("registered-Catalog operator directive bytes differ")
    return (
        _identified(
            {
                "stage": models.STAGE,
                "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
                "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
                "operator_directive": models.OPERATOR_DIRECTIVE,
                "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
                "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
                "provider_execution_authorized": False,
                "gpu_execution_authorized": False,
                "archive_selection_authorized": False,
                "benchmark_estimation_authorized": False,
                "catalog_promotion_authorized": False,
                "qa_release_authorized": False,
                "schema_version": "qa_registered_catalog_integration_authorization.v1",
            },
            "authorization_id",
            "qa_registered_catalog_integration_authorization:",
        ),
        directive,
    )


def _freeze_predecessor(root: Path, authorization_id: str) -> dict[str, Any]:
    directory = root / models.PREDECESSOR_DIRECTORY
    files = _files(directory)
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        len(files) != models.PREDECESSOR_FILE_COUNT
        or sum(map(len, files.values())) != models.PREDECESSOR_TOTAL_BYTES
        or len(manifest_payload) != models.PREDECESSOR_MANIFEST_BYTES
        or _sha(manifest_payload) != models.PREDECESSOR_MANIFEST_SHA256
    ):
        raise ValueError("depth-three independent-audit Freeze geometry differs")
    manifest = json.loads(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest["members"]}
    if (
        len(members) != models.PREDECESSOR_MEMBER_COUNT
        or int(manifest["member_bytes"]) != models.PREDECESSOR_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        raise ValueError("depth-three independent-audit Manifest domain differs")
    for path, row in members.items():
        payload = files[path]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            raise ValueError(f"depth-three independent-audit member differs:{path}")
    report = json.loads(files["report.json"])
    gate = json.loads(files["gate_evaluation.json"])
    decision = json.loads(files["decision.json"])
    transition = json.loads(files["transition.json"])
    scope = json.loads(files["scope_boundary_audit.json"])
    if (
        manifest["manifest_id"] != models.PREDECESSOR_MANIFEST_ID
        or manifest["artifact_root"] != models.PREDECESSOR_ROOT_ID
        or report["report_id"] != models.PREDECESSOR_REPORT_ID
        or gate["gate_id"] != models.PREDECESSOR_GATE_ID
        or decision["decision_id"] != models.PREDECESSOR_DECISION_ID
        or transition["transition_id"] != models.PREDECESSOR_TRANSITION_ID
        or transition["prospective_next_stage"] != models.STAGE
        or transition["next_stage_authorized"] is not False
        or gate["passed"] != 8
        or gate["failed"] != 0
        or scope["audit_source_commit"] != models.PREDECESSOR_SOURCE_COMMIT
        or scope["audit_source_tree"] != models.PREDECESSOR_SOURCE_TREE
    ):
        raise ValueError("depth-three independent-audit decision authority differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "directory": models.PREDECESSOR_DIRECTORY,
            "source_commit": models.PREDECESSOR_SOURCE_COMMIT,
            "source_tree": models.PREDECESSOR_SOURCE_TREE,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "manifest_member_count": len(members),
            "manifest_member_bytes": sum(int(row["byte_count"]) for row in members.values()),
            "manifest_file_sha256": _sha(manifest_payload),
            "manifest_id": models.PREDECESSOR_MANIFEST_ID,
            "artifact_root": models.PREDECESSOR_ROOT_ID,
            "report_id": models.PREDECESSOR_REPORT_ID,
            "gate_id": models.PREDECESSOR_GATE_ID,
            "decision_id": models.PREDECESSOR_DECISION_ID,
            "transition_id": models.PREDECESSOR_TRANSITION_ID,
            "semantic_depth_distribution": {"3": 2},
            "topology_distribution": {"branch_and_merge": 1, "serial_chain": 1},
            "registered_catalog_integration_evaluated": False,
            "formal_bytes_modified": False,
            "schema_version": "qa_registered_catalog_predecessor_freeze.v1",
        },
        "freeze_id",
        "qa_registered_catalog_predecessor_freeze:",
    )


def _source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    resolved_commit = _git_text(root, "rev-parse", f"{source_commit}^{{commit}}")
    resolved_tree = _git_text(root, "rev-parse", f"{resolved_commit}^{{tree}}")
    if source_commit != resolved_commit or source_tree != resolved_tree:
        raise ValueError("registered-Catalog source commit/tree relation differs")
    members = []
    for path in models.SOURCE_PATHS:
        committed = _git(root, "show", f"{resolved_commit}:{path}")
        current = (root / path).read_bytes()
        blob = hashlib.sha1(
            f"blob {len(committed)}\0".encode("ascii") + committed,
            usedforsecurity=False,
        ).hexdigest()
        if (
            blob != _git_text(root, "rev-parse", f"{resolved_commit}:{path}")
            or committed != current
        ):
            raise ValueError(f"registered-Catalog source member differs:{path}")
        members.append(
            {
                "relative_path": path,
                "git_blob_oid": blob,
                "sha256": _sha(committed),
                "byte_count": len(committed),
                "committed_current_bytes_equal": True,
            }
        )
    return _identified(
        {
            "authorization_id": authorization_id,
            "requested_commit": source_commit,
            "resolved_commit": resolved_commit,
            "requested_tree": source_tree,
            "resolved_tree": resolved_tree,
            "members": tuple(members),
            "member_count": len(members),
            "path_set_sha256": _sha(canonical_json_bytes(models.SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(members)),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "schema_version": "qa_registered_catalog_source_binding.v1",
        },
        "binding_id",
        "qa_registered_catalog_source_binding:",
    )


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _integration(
    authorization_id: str,
    catalog: RegisteredFinanceQACatalog,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, Any]]:
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    receipts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    products: dict[str, Any] = {}
    case_by_task = {
        "derived_growth_absolute_spread": "branch_merge_growth_gap",
        "registered_margin_target_gap": "serial_margin_target_gap",
    }
    for task_type in models.EXTENSION_TASK_TYPES:
        bundle, roles = catalog.control_input(task_type)
        resolved, package = catalog.compile_control(task_type, bundle, roles)
        corpus = EvidenceCorpus.from_bundle(bundle)
        graph = ProofGraphBuilder().build(bundle)
        execution = PublicPlanCandidateExecutor(catalog.registry).generate(package, corpus)
        catalog.admit_package(task_type, resolved.receipt, package)
        verification = workflow.verify(package.task, corpus, graph, execution.trajectory)
        assessment = evaluator.evaluate(package.task, corpus, graph, execution.trajectory)
        metrics = derive_program_depth_metrics(execution.reconstructed_program, catalog.registry)
        admit_program_depth_metrics(
            expected_program=package.task.oracle.task_program,
            candidate_program=execution.reconstructed_program,
            candidate_metrics=metrics,
            registry=catalog.registry,
        )
        case_id = case_by_task[task_type]
        row = _identified(
            {
                "authorization_id": authorization_id,
                "catalog_id": catalog.descriptor["catalog_id"],
                "resolution_receipt_id": resolved.receipt["receipt_id"],
                "case_id": case_id,
                "task_type": task_type,
                "pattern_id": resolved.pattern.pattern_id,
                "pattern_hash": resolved.pattern.pattern_hash,
                "renderer_profile_id": resolved.renderer.profile_id,
                "runtime_id": resolved.runtime.runtime_id,
                "evidence_bundle_id": bundle.bundle_id,
                "realized_package_id": package.realized_package_id,
                "source_program_id": execution.reconstructed_program.program_id,
                "source_program_hash": execution.reconstructed_program.program_hash,
                "execution_id": execution.execution_id,
                "verification_trajectory_id": verification.trajectory_id,
                "assessment_id": assessment.assessment_id,
                "depth_metrics_id": metrics.metrics_id,
                "semantic_operation_depth": metrics.semantic_operation_depth,
                "structural_dependency_depth": metrics.structural_dependency_depth,
                "workflow_interaction_depth": metrics.workflow_interaction_depth,
                "catalog_lookup_passed": True,
                "pattern_selection_passed": True,
                "evidence_binding_passed": True,
                "program_compilation_passed": True,
                "protected_realization_passed": package.realization.validation.passed,
                "program_execution_complete": len(execution.program_execution.node_outputs)
                == len(execution.reconstructed_program.nodes),
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
        receipts.append(resolved.receipt)
        rows.append(row)
        products[case_id] = {
            "bundle": bundle,
            "package": package,
            "execution": execution,
            "verification": verification,
            "assessment": assessment,
            "metrics": metrics,
        }
    ordered = tuple(products[case_id] for case_id in models.CASE_IDS)
    runtime_products = {
        "bundles": tuple(item["bundle"] for item in ordered),
        "packages": tuple(item["package"] for item in ordered),
        "executions": tuple(item["execution"] for item in ordered),
        "verification_reports": tuple(item["verification"] for item in ordered),
        "assessments": tuple(item["assessment"] for item in ordered),
        "depth_metrics": tuple(item["metrics"] for item in ordered),
    }
    return tuple(receipts), tuple(rows), runtime_products


def _negative_controls(
    authorization_id: str,
    descriptor: dict[str, Any],
    catalog: RegisteredFinanceQACatalog,
    package: Any,
) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def reject(name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except (CatalogAdmissionError, ValueError, KeyError) as exc:
            stage = exc.stage if isinstance(exc, CatalogAdmissionError) else "registry.register"
            controls.append(
                {
                    "name": name,
                    "rejection_stage": stage,
                    "exception_type": type(exc).__name__,
                    "reason_sha256": _sha(str(exc).encode()),
                    "rejected": True,
                    "output_writes": 0,
                    "provider_calls": 0,
                }
            )
            return
        raise ValueError(f"registered-Catalog negative control accepted:{name}")

    tasks = tuple(dict(row) for row in descriptor["task_registrations"])
    operations = tuple(dict(row) for row in descriptor["operation_registrations"])
    reject("task_type_alias", lambda: catalog.resolve("registered_margin_gap"))
    reject(
        "missing_task_registration",
        lambda: validate_catalog_rows(
            tuple(row for row in tasks if row["task_type"] != "registered_margin_target_gap"),
            operations,
        ),
    )
    reject(
        "duplicate_task_registration",
        lambda: validate_catalog_rows((*tasks, dict(tasks[-1])), operations),
    )
    reject(
        "missing_operation_registration",
        lambda: validate_catalog_rows(
            tasks,
            tuple(row for row in operations if row["operator_id"] != "scale_ratio_percent"),
        ),
    )
    reject(
        "duplicate_operation_registration",
        lambda: validate_catalog_rows(tasks, (*operations, dict(operations[-1]))),
    )
    wrong_role = tuple(
        {**row, "program_role": "transparent_projection"}
        if row["operator_id"] == "scale_ratio_percent"
        else row
        for row in operations
    )
    reject("wrong_operation_role", lambda: validate_catalog_rows(tasks, wrong_role))
    reject(
        "catalog_bypass_without_resolution_receipt",
        lambda: catalog.admit_package("derived_growth_absolute_spread", None, package),
    )
    crossed_tasks = tuple(
        {**row, "pattern_hash": "program:crossed"}
        if row["task_type"] == "registered_margin_target_gap"
        else row
        for row in tasks
    )
    reject("crossed_pattern_registration", lambda: validate_catalog_rows(crossed_tasks, operations))
    return _identified(
        {
            "authorization_id": authorization_id,
            "catalog_id": descriptor["catalog_id"],
            "controls": tuple(controls),
            "attempted_count": len(controls),
            "rejected_count": sum(row["rejected"] for row in controls),
            "accepted_count": 0,
            "output_writes": 0,
            "provider_calls": 0,
            "schema_version": "qa_registered_catalog_negative_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_negative_audit:",
    )


def build_qa_semantic_depth_three_catalog_integration_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.Products:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization, directive = _authorization(review)
    predecessor = _freeze_predecessor(root, authorization["authorization_id"])
    source = _source_binding(root, authorization["authorization_id"], source_commit, source_tree)
    historical = historical_catalog_snapshot()
    descriptor = build_catalog_descriptor(historical["snapshot_id"])
    catalog = RegisteredFinanceQACatalog(descriptor)
    receipts, rows, runtime = _integration(authorization["authorization_id"], catalog)
    integration = _identified(
        {
            "authorization_id": authorization["authorization_id"],
            "predecessor_freeze_id": predecessor["freeze_id"],
            "source_binding_id": source["binding_id"],
            "historical_catalog_snapshot_id": historical["snapshot_id"],
            "catalog_id": descriptor["catalog_id"],
            "catalog_manifest_sha256": catalog_manifest_sha256(descriptor),
            "rows": rows,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "total_task_count": 10,
            "extension_operation_count": 3,
            "task_registration_counts": {task_type: 1 for task_type in models.EXTENSION_TASK_TYPES},
            "operation_registration_counts": {
                operator_id: 1 for operator_id in models.EXTENSION_OPERATION_IDS
            },
            "catalog_resolution_count": len(receipts),
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
    negative = _negative_controls(
        authorization["authorization_id"], descriptor, catalog, runtime["packages"][0]
    )
    scope = _identified(
        {
            "authorization_id": authorization["authorization_id"],
            "integration_audit_id": integration["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "historical_catalog_modified": False,
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
            "claim_is_catalog_integration_preflight_only": True,
            "schema_version": "qa_registered_catalog_scope_audit.v1",
        },
        "audit_id",
        "qa_registered_catalog_scope_audit:",
    )
    gates = {
        "G0_exact_external_scope_and_predecessor_freeze": True,
        "G1_historical_eight_type_catalog_immutable": historical["historical_objects_modified"]
        is False,
        "G2_fresh_versioned_catalog_and_exact_registrations": (
            descriptor["extension_task_count"] == 2
            and descriptor["extension_operation_count"] == 3
            and descriptor["catalog_promoted"] is False
        ),
        "G3_catalog_lookup_pattern_renderer_runtime_relations": len(receipts) == 2,
        "G4_catalog_mediated_program_execution_2_of_2": all(
            row["program_execution_complete"] and row["independent_node_replay_passed"]
            for row in rows
        ),
        "G5_answer_schema_answer_citation_evaluator_2_of_2": all(
            row["answer_schema_correct"]
            and row["answer_correct"]
            and row["citation_correct"]
            and row["evaluator_accepted"]
            for row in rows
        ),
        "G6_eight_catalog_authority_attacks_reject": (
            negative["rejected_count"] == 8 and negative["accepted_count"] == 0
        ),
        "G7_zero_external_execution_and_release_scope": not any(
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
            )
        ),
    }
    gate = _identified(
        {
            "gates": gates,
            "passed_count": sum(gates.values()),
            "failed_count": len(gates) - sum(gates.values()),
            "noncompensatory": True,
            "schema_version": "qa_registered_catalog_gate.v1",
        },
        "gate_id",
        "qa_registered_catalog_gate:",
    )
    if gate["failed_count"]:
        raise ValueError("registered-Catalog noncompensatory Gate failed")
    decision = _identified(
        {
            "gate_id": gate["gate_id"],
            "decision": models.DECISION,
            "registered_catalog_integration_closed_for_exact_two_fixtures": True,
            "archive_grounding_established": False,
            "benchmark_distribution_established": False,
            "overall_qa_sufficiency_established": False,
            "qa_release_eligible": False,
            "schema_version": "qa_registered_catalog_decision.v1",
        },
        "decision_id",
        "qa_registered_catalog_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "next_stage": models.NEXT_STAGE,
            "next_stage_authorized": True,
            "provider_execution_authorized": False,
            "gpu_execution_authorized": False,
            "archive_selection_authorized": False,
            "benchmark_estimation_authorized": False,
            "catalog_promotion_authorized": False,
            "qa_release_authorized": False,
            "schema_version": "qa_registered_catalog_transition.v1",
        },
        "transition_id",
        "qa_registered_catalog_transition:",
    )
    report = _identified(
        {
            "authorization_id": authorization["authorization_id"],
            "predecessor_freeze_id": predecessor["freeze_id"],
            "source_binding_id": source["binding_id"],
            "historical_catalog_snapshot_id": historical["snapshot_id"],
            "catalog_id": descriptor["catalog_id"],
            "integration_audit_id": integration["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "historical_task_count": 8,
            "extension_task_count": 2,
            "extension_operation_count": 3,
            "catalog_mediated_execution_count": 2,
            "semantic_depth_distribution": {"3": 2},
            "negative_controls": 8,
            "provider_calls": 0,
            "scope_claim": "deterministic_registered_catalog_integration_preflight_only",
            "schema_version": "qa_registered_catalog_report.v1",
        },
        "report_id",
        "qa_registered_catalog_report:",
    )
    return models.Products(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        predecessor_freeze=predecessor,
        source_binding=source,
        historical_catalog_freeze=historical,
        catalog_descriptor=descriptor,
        discovery_receipts=receipts,
        integration_rows=rows,
        integration_audit=integration,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
        **runtime,
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def write_qa_semantic_depth_three_catalog_integration_artifacts(
    products: models.Products, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "catalog_descriptor.json": canonical_json_bytes(products.catalog_descriptor) + b"\n",
        "catalog_discovery_receipts.jsonl": _jsonl(products.discovery_receipts),
        "catalog_integration_audit.json": canonical_json_bytes(products.integration_audit) + b"\n",
        "catalog_integration_rows.jsonl": _jsonl(products.integration_rows),
        "decision.json": canonical_json_bytes(products.decision) + b"\n",
        "depth_metrics.jsonl": _jsonl(products.depth_metrics),
        "evidence_bundles.jsonl": _jsonl(products.bundles),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(products.gate) + b"\n",
        "historical_catalog_freeze.json": canonical_json_bytes(products.historical_catalog_freeze)
        + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_audit) + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "predecessor_freeze.json": canonical_json_bytes(products.predecessor_freeze) + b"\n",
        "public_plan_executions.jsonl": _jsonl(products.executions),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "realized_task_packages.jsonl": _jsonl(products.packages),
        "report.json": canonical_json_bytes(products.report) + b"\n",
        "scope_boundary_audit.json": canonical_json_bytes(products.scope_audit) + b"\n",
        "source_binding.json": canonical_json_bytes(products.source_binding) + b"\n",
        "transition.json": canonical_json_bytes(products.transition) + b"\n",
        "verification_reports.jsonl": _jsonl(products.verification_reports),
    }
    members = tuple(
        {
            "relative_path": path,
            "sha256": _sha(payload),
            "byte_count": len(payload),
        }
        for path, payload in sorted(payloads.items())
    )
    body = {
        "members": members,
        "file_count": len(members),
        "member_bytes": sum(map(len, payloads.values())),
        "artifact_root": strict_canonical_hash(
            members, prefix="qa_registered_catalog_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "qa_registered_catalog_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    body, prefix="qa_registered_catalog_artifact_manifest:"
                ),
                **body,
            }
        )
        + b"\n"
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    arguments = parser.parse_args()
    products = build_qa_semantic_depth_three_catalog_integration_preflight(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_qa_semantic_depth_three_catalog_integration_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
