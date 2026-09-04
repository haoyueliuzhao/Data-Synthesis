from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task.program_depth import (
    admit_program_depth_metrics,
    derive_program_depth_metrics,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)

from . import models
from .archive import (
    ArchiveAdmissionError,
    archive_record_rows,
    archive_sha256,
    branch_bindings,
    reject_target_candidate,
    select_records,
    serial_candidate_rows,
    validate_archive_bytes,
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
        raise ValueError("external Archive-grounding audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT or _sha(directive) != (
        models.OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("Archive-grounding operator directive bytes differ")
    return (
        _identified(
            {
                "stage": models.STAGE,
                "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
                "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
                "operator_directive": models.OPERATOR_DIRECTIVE,
                "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
                "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
                "archive_selection_authorized": True,
                "registered_task_type_change_authorized": False,
                "registered_operation_change_authorized": False,
                "provider_execution_authorized": False,
                "gpu_execution_authorized": False,
                "online_generation_authorized": False,
                "benchmark_distribution_inference_authorized": False,
                "qa_release_authorized": False,
                "schema_version": "qa_archive_parameter_space_authorization.v1",
            },
            "authorization_id",
            "qa_archive_parameter_space_authorization:",
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
        raise ValueError("registered-Catalog independent-audit Freeze geometry differs")
    manifest = json.loads(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest["members"]}
    if (
        len(members) != models.PREDECESSOR_MEMBER_COUNT
        or int(manifest["member_bytes"]) != models.PREDECESSOR_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        raise ValueError("registered-Catalog independent-audit Manifest differs")
    for path, row in members.items():
        payload = files[path]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            raise ValueError(f"registered-Catalog independent member differs:{path}")
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
        or report["passed_count"] != 8
        or report["failed_count"] != 0
        or scope["audit_source_commit"] != models.PREDECESSOR_SOURCE_COMMIT
        or scope["audit_source_tree"] != models.PREDECESSOR_SOURCE_TREE
    ):
        raise ValueError("registered-Catalog independent decision authority differs")
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
            "catalog_integration_independently_confirmed": True,
            "formal_bytes_modified": False,
            "schema_version": "qa_archive_parameter_space_predecessor_freeze.v1",
        },
        "freeze_id",
        "qa_archive_parameter_space_predecessor_freeze:",
    )


def _source_binding(
    root: Path,
    authorization_id: str,
    source_commit: str,
    source_tree: str,
) -> dict[str, Any]:
    resolved_commit = _git_text(root, "rev-parse", f"{source_commit}^{{commit}}")
    resolved_tree = _git_text(root, "rev-parse", f"{resolved_commit}^{{tree}}")
    if source_commit != resolved_commit or source_tree != resolved_tree:
        raise ValueError("Archive-grounding source commit/tree relation differs")
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
            raise ValueError(f"Archive-grounding source member differs:{path}")
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
            "schema_version": "qa_archive_parameter_space_source_binding.v1",
        },
        "binding_id",
        "qa_archive_parameter_space_source_binding:",
    )


def _archive_binding(
    root: Path,
    authorization_id: str,
    source_commit: str,
    payload: bytes,
    records: list[Any],
) -> tuple[dict[str, Any], tuple[tuple[Any, dict[str, Any]], ...]]:
    validate_archive_bytes(payload)
    committed = _git(root, "show", f"{source_commit}:{models.ARCHIVE_PATH}")
    current = (root / models.ARCHIVE_PATH).read_bytes()
    if committed != payload or current != payload:
        raise ValueError("Archive committed/current bytes differ")
    blob = hashlib.sha1(
        f"blob {len(committed)}\0".encode("ascii") + committed,
        usedforsecurity=False,
    ).hexdigest()
    if blob != _git_text(root, "rev-parse", f"{source_commit}:{models.ARCHIVE_PATH}"):
        raise ValueError("Archive Git Blob relation differs")
    selected = select_records(records)
    selected_rows = archive_record_rows(selected)
    archive_id = f"qa_frozen_finqa_source_archive:{archive_sha256(payload)}"
    binding = _identified(
        {
            "authorization_id": authorization_id,
            "archive_id": archive_id,
            "relative_path": models.ARCHIVE_PATH,
            "sha256": archive_sha256(payload),
            "byte_count": len(payload),
            "record_count": len(records),
            "git_blob_oid": blob,
            "committed_current_bytes_equal": True,
            "selected_records": selected_rows,
            "selected_record_count": len(selected_rows),
            "selected_record_ids": tuple(row["record_id"] for row in selected_rows),
            "raw_financial_data_lake_used": False,
            "distribution_inference_performed": False,
            "archive_claim": "real_financial_document_snapshot_source_only",
            "schema_version": "qa_archive_source_binding.v1",
        },
        "binding_id",
        "qa_archive_source_binding:",
    )
    return binding, selected


def _catalog_freeze(root: Path, authorization_id: str) -> tuple[dict[str, Any], Any]:
    path = root / models.CATALOG_DIRECTORY / "catalog_descriptor.json"
    payload = path.read_bytes()
    if len(payload) != models.CATALOG_DESCRIPTOR_BYTE_COUNT or _sha(payload) != (
        models.CATALOG_DESCRIPTOR_SHA256
    ):
        raise ValueError("registered Catalog descriptor bytes differ")
    candidate = json.loads(payload)
    historical = historical_catalog_snapshot()
    rebuilt = build_catalog_descriptor(historical["snapshot_id"])
    if (
        canonical_json_bytes(candidate) != canonical_json_bytes(rebuilt)
        or candidate["catalog_id"] != models.CATALOG_ID
    ):
        raise ValueError("registered Catalog reconstruction differs")
    catalog = RegisteredFinanceQACatalog(rebuilt)
    return (
        _identified(
            {
                "authorization_id": authorization_id,
                "catalog_id": rebuilt["catalog_id"],
                "catalog_descriptor_sha256": _sha(payload),
                "catalog_descriptor_byte_count": len(payload),
                "historical_catalog_snapshot_id": historical["snapshot_id"],
                "historical_task_count": rebuilt["historical_task_count"],
                "extension_task_count": rebuilt["extension_task_count"],
                "total_task_count": rebuilt["total_task_count"],
                "extension_operation_count": rebuilt["extension_operation_count"],
                "extension_task_types": models.EXTENSION_TASK_TYPES,
                "catalog_reconstructed_actual_bytes_equal": True,
                "catalog_modified": False,
                "schema_version": "qa_archive_parameter_space_catalog_freeze.v1",
            },
            "freeze_id",
            "qa_archive_parameter_space_catalog_freeze:",
        ),
        catalog,
    )


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _execute_branch_cases(
    *,
    authorization_id: str,
    archive_binding_id: str,
    catalog: RegisteredFinanceQACatalog,
    candidates: tuple[tuple[str, EvidenceBundle, dict[str, tuple[str, ...]], dict[str, Any]], ...],
) -> tuple[tuple[dict[str, Any], ...], dict[str, tuple[Any, ...]]]:
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    rows: list[dict[str, Any]] = []
    products: dict[str, list[Any]] = defaultdict(list)
    for case_id, bundle, role_bindings, metadata in candidates:
        resolved, package = catalog.compile_control(
            "derived_growth_absolute_spread", bundle, role_bindings
        )
        corpus = EvidenceCorpus.from_bundle(bundle)
        graph = ProofGraphBuilder().build(bundle)
        execution = PublicPlanCandidateExecutor(catalog.registry).generate(package, corpus)
        catalog.admit_package("derived_growth_absolute_spread", resolved.receipt, package)
        verification = workflow.verify(package.task, corpus, graph, execution.trajectory)
        assessment = evaluator.evaluate(package.task, corpus, graph, execution.trajectory)
        metrics = derive_program_depth_metrics(execution.reconstructed_program, catalog.registry)
        admitted = admit_program_depth_metrics(
            expected_program=package.task.oracle.task_program,
            candidate_program=execution.reconstructed_program,
            candidate_metrics=metrics,
            registry=catalog.registry,
        )
        row = _identified(
            {
                "authorization_id": authorization_id,
                "archive_binding_id": archive_binding_id,
                "catalog_id": catalog.descriptor["catalog_id"],
                "case_id": case_id,
                "task_type": "derived_growth_absolute_spread",
                "topology_kind": "branch_and_merge",
                **metadata,
                "available_role_count": 4,
                "required_role_count": 4,
                "archive_role_complete": True,
                "constructible": True,
                "typed_blocker": None,
                "resolution_receipt_id": resolved.receipt["receipt_id"],
                "evidence_bundle_id": bundle.bundle_id,
                "binding_snapshot_id": package.binding_snapshot.binding_snapshot_id,
                "realized_package_id": package.realized_package_id,
                "source_program_id": execution.reconstructed_program.program_id,
                "source_program_hash": execution.reconstructed_program.program_hash,
                "execution_id": execution.execution_id,
                "verification_trajectory_id": verification.trajectory_id,
                "assessment_id": assessment.assessment_id,
                "depth_metrics_id": admitted.metrics_id,
                "node_count": len(execution.reconstructed_program.nodes),
                "semantic_operation_depth": admitted.semantic_operation_depth,
                "program_execution_complete": len(execution.program_execution.node_outputs)
                == len(execution.reconstructed_program.nodes),
                "independent_node_replay_passed": execution.independent_verification.passed,
                "answer_schema_correct": _check(verification, "answer_schema_validity"),
                "answer_correct": _check(verification, "answer_correctness"),
                "citation_correct": _check(verification, "citation_binding"),
                "evaluator_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
                "schema_version": "qa_archive_parameter_case_row.v1",
            },
            "row_id",
            "qa_archive_parameter_case_row:",
        )
        rows.append(row)
        for key, value in (
            ("bundles", bundle),
            ("discovery_receipts", resolved.receipt),
            ("packages", package),
            ("executions", execution),
            ("verification_reports", verification),
            ("assessments", assessment),
            ("depth_metrics", admitted),
        ):
            products[key].append(value)
    return tuple(rows), {key: tuple(values) for key, values in products.items()}


def _blocked_serial_rows(
    *,
    authorization_id: str,
    archive_binding_id: str,
    catalog_id: str,
    candidates: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    rows = []
    for candidate in candidates:
        rows.append(
            _identified(
                {
                    "authorization_id": authorization_id,
                    "archive_binding_id": archive_binding_id,
                    "catalog_id": catalog_id,
                    "topology_kind": "serial_chain",
                    **candidate,
                    "available_role_count": 2,
                    "required_role_count": 3,
                    "resolution_receipt_id": None,
                    "evidence_bundle_id": None,
                    "binding_snapshot_id": None,
                    "realized_package_id": None,
                    "source_program_id": None,
                    "source_program_hash": None,
                    "execution_id": None,
                    "verification_trajectory_id": None,
                    "assessment_id": None,
                    "depth_metrics_id": None,
                    "node_count": 0,
                    "semantic_operation_depth": None,
                    "program_execution_complete": False,
                    "independent_node_replay_passed": False,
                    "answer_schema_correct": False,
                    "answer_correct": False,
                    "citation_correct": False,
                    "evaluator_accepted": False,
                },
                "row_id",
                "qa_archive_parameter_case_row:",
            )
        )
    return tuple(rows)


def aggregate_case_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("parameter-space aggregation requires case rows")
    case_ids = tuple(str(row["case_id"]) for row in rows)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("parameter-space case IDs are not unique")
    by_task: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[str(row["task_type"])].append(row)
    if tuple(sorted(by_task)) != models.EXTENSION_TASK_TYPES:
        raise ValueError("parameter-space task domain differs")
    constructible = [row for row in rows if bool(row["constructible"])]
    blocked = [row for row in rows if not bool(row["constructible"])]
    task_candidate_counts = {key: len(by_task[key]) for key in sorted(by_task)}
    task_constructible_counts = {
        key: sum(bool(row["constructible"]) for row in by_task[key]) for key in sorted(by_task)
    }
    task_binding_counts = {
        key: len(
            {
                str(row["binding_snapshot_id"])
                for row in by_task[key]
                if row["binding_snapshot_id"] is not None
            }
        )
        for key in sorted(by_task)
    }
    task_entity_counts = {
        key: len({str(row["subject_id"]) for row in by_task[key]}) for key in sorted(by_task)
    }
    semantic_depth_distribution = Counter(
        int(row["semantic_operation_depth"])
        for row in constructible
        if row["semantic_operation_depth"] is not None
    )
    relationship_distribution = Counter(
        str(row["numeric_relationship"])
        for row in constructible
        if row.get("numeric_relationship") is not None
    )
    all_execution_checks = all(
        bool(row[key])
        for row in constructible
        for key in (
            "archive_role_complete",
            "program_execution_complete",
            "independent_node_replay_passed",
            "answer_schema_correct",
            "answer_correct",
            "citation_correct",
            "evaluator_accepted",
        )
    )
    return {
        "case_count": len(rows),
        "constructible_count": len(constructible),
        "blocked_count": len(blocked),
        "task_candidate_counts": task_candidate_counts,
        "task_constructible_counts": task_constructible_counts,
        "task_distinct_binding_counts": task_binding_counts,
        "task_entity_counts": task_entity_counts,
        "semantic_depth_distribution": {
            str(key): semantic_depth_distribution[key]
            for key in sorted(semantic_depth_distribution)
        },
        "numeric_relationship_distribution": {
            key: relationship_distribution[key] for key in sorted(relationship_distribution)
        },
        "complete_execution_count": sum(
            bool(row["program_execution_complete"]) for row in constructible
        ),
        "independent_replay_count": sum(
            bool(row["independent_node_replay_passed"]) for row in constructible
        ),
        "answer_schema_correct_count": sum(
            bool(row["answer_schema_correct"]) for row in constructible
        ),
        "answer_correct_count": sum(bool(row["answer_correct"]) for row in constructible),
        "citation_correct_count": sum(bool(row["citation_correct"]) for row in constructible),
        "evaluator_accepted_count": sum(bool(row["evaluator_accepted"]) for row in constructible),
        "all_constructible_rows_pass_execution_and_verification": all_execution_checks,
        "both_task_types_have_multiple_distinct_bindings": all(
            task_binding_counts[task_type] >= 2 for task_type in models.EXTENSION_TASK_TYPES
        ),
        "blocked_reason_counts": dict(
            sorted(Counter(str(row["typed_blocker"]) for row in blocked).items())
        ),
        "aggregation_source_row_ids_sha256": _sha(
            canonical_json_bytes(tuple(str(row["row_id"]) for row in rows))
        ),
        "aggregation_is_programmatic": True,
        "fixed_case_count_constants_used": False,
        "schema_version": "qa_archive_parameter_space_aggregate.v1",
    }


def admit_aggregate(candidate: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    if dict(candidate) != aggregate_case_rows(rows):
        raise ValueError("programmatic case-row aggregate differs")


def _attack_bundle(case_id: str, evidence: tuple[EvidenceItem, ...]) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=strict_canonical_hash(
            {
                "case_id": case_id,
                "evidence_ids": tuple(item.evidence_id for item in evidence),
                "schema_version": "qa_archive_attack_bundle.v1",
            },
            prefix="qa_archive_attack_bundle:",
        ),
        evidence=evidence,
        purpose="Archive-grounding negative control",
        graph_build_id=f"qa_archive_attack_graph:{case_id}",
        metadata={"attack": True},
    )


def _negative_controls(
    *,
    authorization_id: str,
    archive_payload: bytes,
    records: list[Any],
    archive_record_rows_value: tuple[dict[str, Any], ...],
    catalog: RegisteredFinanceQACatalog,
    branch_candidates: tuple[
        tuple[str, EvidenceBundle, dict[str, tuple[str, ...]], dict[str, Any]], ...
    ],
    case_rows: tuple[dict[str, Any], ...],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def reject(name: str, action: Callable[[], Any]) -> None:
        try:
            action()
        except (ArchiveAdmissionError, ValueError, KeyError) as exc:
            controls.append(
                {
                    "name": name,
                    "rejection_stage": (
                        exc.stage
                        if isinstance(exc, ArchiveAdmissionError)
                        else "aggregate.admission"
                    ),
                    "exception_type": type(exc).__name__,
                    "reason_sha256": _sha(str(exc).encode("utf-8")),
                    "rejected": True,
                    "output_writes": 0,
                    "provider_calls": 0,
                }
            )
            return
        raise ValueError(f"Archive parameter-space negative control accepted:{name}")

    reject("archive_byte_mutation", lambda: validate_archive_bytes(archive_payload + b"\n"))

    crossed_records = copy.deepcopy(records)
    next(row for row in crossed_records if row.get("id") == models.SOURCE_RECORD_IDS[0])["id"] = (
        "CDW/2017/page_38.pdf-crossed"
    )
    reject("source_record_substitution", lambda: select_records(crossed_records))

    changed_cell = copy.deepcopy(records)
    next(row for row in changed_cell if row.get("id") == models.SOURCE_RECORD_IDS[0])["table_ori"][
        2
    ][0] = "Revenue"
    reject("source_cell_mutation", lambda: select_records(changed_cell))

    _, first_bundle, first_roles, _ = branch_candidates[0]
    _, other_bundle, _, _ = next(
        item
        for item in branch_candidates
        if item[1].evidence[0].subject.subject_id != first_bundle.evidence[0].subject.subject_id
    )
    cross_evidence = (
        first_bundle.evidence[0],
        first_bundle.evidence[1],
        other_bundle.evidence[2],
        other_bundle.evidence[3],
    )
    cross_bundle = _attack_bundle("cross_entity", cross_evidence)
    cross_roles = {
        "revenue_earlier": (cross_evidence[0].evidence_id,),
        "revenue_later": (cross_evidence[1].evidence_id,),
        "income_earlier": (cross_evidence[2].evidence_id,),
        "income_later": (cross_evidence[3].evidence_id,),
    }
    reject(
        "cross_entity_binding",
        lambda: catalog.compile_control(
            "derived_growth_absolute_spread", cross_bundle, cross_roles
        ),
    )

    reversed_roles = {
        "revenue_earlier": first_roles["revenue_later"],
        "revenue_later": first_roles["revenue_earlier"],
        "income_earlier": first_roles["income_later"],
        "income_later": first_roles["income_earlier"],
    }
    reject(
        "reversed_period_binding",
        lambda: catalog.compile_control(
            "derived_growth_absolute_spread", first_bundle, reversed_roles
        ),
    )

    numerator = first_bundle.evidence[0]
    fabricated = numerator.model_copy(
        update={
            "predicate": "gross_margin_target",
            "payload": ScalarObservation(value=Decimal("45"), unit="percent"),
            "source_locator": numerator.source_locator.model_copy(update={"row": "constant"}),
        }
    )
    reject(
        "fabricated_target_constant",
        lambda: reject_target_candidate(
            evidence=fabricated, selected_records=archive_record_rows_value
        ),
    )
    derived = fabricated.model_copy(
        update={
            "epistemic_status": EpistemicStatus.DERIVED,
            "source_locator": numerator.source_locator.model_copy(update={"row": "Gross profit"}),
            "provenance": numerator.provenance.model_copy(
                update={"parent_evidence_ids": (numerator.evidence_id,)}
            ),
        }
    )
    reject(
        "derived_margin_relabelled_as_target",
        lambda: reject_target_candidate(
            evidence=derived, selected_records=archive_record_rows_value
        ),
    )

    fixed = dict(aggregate)
    fixed["constructible_count"] = 12
    reject("fixed_aggregate_injection", lambda: admit_aggregate(fixed, case_rows))
    omitted = tuple(row for row in case_rows if row["constructible"])
    reject("failed_serial_rows_omitted", lambda: admit_aggregate(aggregate, omitted))

    if tuple(row["name"] for row in controls) != models.NEGATIVE_CONTROL_NAMES:
        raise ValueError("Archive negative-control domain differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "controls": tuple(controls),
            "attempted_count": len(controls),
            "rejected_count": sum(bool(row["rejected"]) for row in controls),
            "accepted_count": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "schema_version": "qa_archive_parameter_space_negative_audit.v1",
        },
        "audit_id",
        "qa_archive_parameter_space_negative_audit:",
    )


def build_qa_semantic_depth_three_archive_grounding_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.Products:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization, directive = _authorization(review)
    authorization_id = authorization["authorization_id"]
    predecessor = _freeze_predecessor(root, authorization_id)
    source = _source_binding(root, authorization_id, source_commit, source_tree)
    archive_payload = (root / models.ARCHIVE_PATH).read_bytes()
    records = json.loads(archive_payload)
    if not isinstance(records, list):
        raise ValueError("frozen Archive is not a record list")
    archive, selected = _archive_binding(
        root, authorization_id, source_commit, archive_payload, records
    )
    selected_rows = archive_record_rows(selected)
    catalog_freeze, catalog = _catalog_freeze(root, authorization_id)

    branch_candidates = branch_bindings(selected, archive["archive_id"])
    branch_rows, runtime = _execute_branch_cases(
        authorization_id=authorization_id,
        archive_binding_id=archive["binding_id"],
        catalog=catalog,
        candidates=branch_candidates,
    )
    serial_candidates = serial_candidate_rows(selected, archive["archive_id"])
    serial_rows = _blocked_serial_rows(
        authorization_id=authorization_id,
        archive_binding_id=archive["binding_id"],
        catalog_id=catalog.descriptor["catalog_id"],
        candidates=serial_candidates,
    )
    case_rows = tuple(sorted((*branch_rows, *serial_rows), key=lambda row: row["case_id"]))
    aggregate = aggregate_case_rows(case_rows)
    parameter_space = _identified(
        {
            "authorization_id": authorization_id,
            "predecessor_freeze_id": predecessor["freeze_id"],
            "source_binding_id": source["binding_id"],
            "archive_binding_id": archive["binding_id"],
            "catalog_freeze_id": catalog_freeze["freeze_id"],
            "rows": case_rows,
            **aggregate,
            "archive_record_count": len(selected_rows),
            "archive_entity_count": len({row["subject_id"] for row in selected_rows}),
            "branch_adjacent_period_count": sum(
                bool(row.get("adjacent_periods")) for row in branch_rows
            ),
            "branch_near_equal_growth_count": sum(
                bool(row.get("near_equal_growth")) for row in branch_rows
            ),
            "no_target_labelled_table_rows_in_complete_archive": not any(
                isinstance(table_row, list)
                and table_row
                and "target" in str(table_row[0]).casefold()
                for record in records
                for table_row in record.get("table_ori", [])
            ),
            "archive_grounding_established_for_branch_task": (
                aggregate["task_distinct_binding_counts"]["derived_growth_absolute_spread"] >= 2
            ),
            "archive_grounding_established_for_serial_task": (
                aggregate["task_distinct_binding_counts"]["registered_margin_target_gap"] >= 2
            ),
            "benchmark_distribution_inference_performed": False,
            "schema_version": "qa_archive_parameter_space_audit.v1",
        },
        "audit_id",
        "qa_archive_parameter_space_audit:",
    )
    negative = _negative_controls(
        authorization_id=authorization_id,
        archive_payload=archive_payload,
        records=records,
        archive_record_rows_value=selected_rows,
        catalog=catalog,
        branch_candidates=branch_candidates,
        case_rows=case_rows,
        aggregate=aggregate,
    )
    scope = _identified(
        {
            "authorization_id": authorization_id,
            "parameter_space_audit_id": parameter_space["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "archive_records_read": len(records),
            "archive_records_selected": len(selected_rows),
            "archive_evidence_bundles_materialized": len(runtime["bundles"]),
            "raw_financial_data_lake_reads": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "gpu_jobs": 0,
            "online_generation_jobs": 0,
            "benchmark_distribution_rows": 0,
            "empirical_frequency_estimates": 0,
            "new_task_type_registrations": 0,
            "new_operation_registrations": 0,
            "catalog_promotions": 0,
            "qa_release_objects": 0,
            "vtdo_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "claim_is_archive_constructibility_preflight_only": True,
            "schema_version": "qa_archive_parameter_space_scope_audit.v1",
        },
        "audit_id",
        "qa_archive_parameter_space_scope_audit:",
    )
    relationship_kinds = set(aggregate["numeric_relationship_distribution"])
    gates = {
        "G0_exact_external_scope_and_predecessor_freeze": True,
        "G1_exact_git_source_archive_and_catalog_authority": (
            source["all_current_bytes_equal_committed_bytes"]
            and archive["committed_current_bytes_equal"]
            and catalog_freeze["catalog_reconstructed_actual_bytes_equal"]
        ),
        "G2_exact_ten_task_ten_operation_catalog_retained": (
            catalog_freeze["total_task_count"] == 10
            and catalog_freeze["extension_task_count"] == 2
            and catalog_freeze["extension_operation_count"] == 3
            and catalog_freeze["catalog_modified"] is False
        ),
        "G3_complete_frozen_parameter_grid_and_programmatic_aggregation": (
            aggregate["case_count"] == len(branch_candidates) + len(serial_candidates)
            and aggregate["aggregation_is_programmatic"]
            and not aggregate["fixed_case_count_constants_used"]
        ),
        "G4_both_registered_depth_three_types_have_multiple_archive_bindings": aggregate[
            "both_task_types_have_multiple_distinct_bindings"
        ],
        "G5_every_admitted_case_executes_and_verifies": (
            aggregate["constructible_count"] > 0
            and aggregate["complete_execution_count"] == aggregate["constructible_count"]
            and aggregate["independent_replay_count"] == aggregate["constructible_count"]
            and aggregate["answer_schema_correct_count"] == aggregate["constructible_count"]
            and aggregate["answer_correct_count"] == aggregate["constructible_count"]
            and aggregate["citation_correct_count"] == aggregate["constructible_count"]
            and aggregate["evaluator_accepted_count"] == aggregate["constructible_count"]
            and aggregate["semantic_depth_distribution"] == {"3": len(branch_rows)}
        ),
        "G6_cross_entity_period_relationship_and_edge_coverage": (
            aggregate["task_entity_counts"]["derived_growth_absolute_spread"] >= 2
            and aggregate["task_distinct_binding_counts"]["derived_growth_absolute_spread"] >= 6
            and relationship_kinds == {"both_negative", "both_positive", "mixed_sign"}
            and parameter_space["branch_adjacent_period_count"] > 0
            and parameter_space["branch_near_equal_growth_count"] > 0
        ),
        "G7_nine_attacks_reject_and_zero_external_execution_scope": (
            negative["rejected_count"] == len(models.NEGATIVE_CONTROL_NAMES)
            and negative["accepted_count"] == 0
            and not any(
                scope[key]
                for key in (
                    "raw_financial_data_lake_reads",
                    "provider_calls",
                    "credential_lookups",
                    "gpu_jobs",
                    "online_generation_jobs",
                    "benchmark_distribution_rows",
                    "empirical_frequency_estimates",
                    "new_task_type_registrations",
                    "new_operation_registrations",
                    "catalog_promotions",
                    "qa_release_objects",
                    "vtdo_rows",
                    "training_rows",
                    "production_rows",
                )
            )
        ),
    }
    gate = _identified(
        {
            "gates": gates,
            "passed_count": sum(gates.values()),
            "failed_count": len(gates) - sum(gates.values()),
            "failed_gate_ids": tuple(key for key, value in gates.items() if not value),
            "noncompensatory": True,
            "schema_version": "qa_archive_parameter_space_gate.v1",
        },
        "gate_id",
        "qa_archive_parameter_space_gate:",
    )
    if gate["passed_count"] != 7 or gate["failed_gate_ids"] != (
        "G4_both_registered_depth_three_types_have_multiple_archive_bindings",
    ):
        raise ValueError("Archive parameter-space result differs from exact observed partition")
    decision = _identified(
        {
            "gate_id": gate["gate_id"],
            "decision": models.DECISION,
            "archive_grounding_established_for_branch_task": True,
            "archive_grounding_established_for_serial_task": False,
            "both_registered_task_types_constructible": False,
            "first_blocker": "authoritative_gross_margin_target_evidence_absent",
            "synthetic_target_substitution_permitted": False,
            "general_qa_coverage_established": False,
            "benchmark_distribution_established": False,
            "qa_release_eligible": False,
            "schema_version": "qa_archive_parameter_space_decision.v1",
        },
        "decision_id",
        "qa_archive_parameter_space_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "prospective_next_stage": models.PROSPECTIVE_NEXT_STAGE,
            "next_stage_authorized": False,
            "separate_external_audit_decision_required": True,
            "provider_execution_authorized": False,
            "archive_expansion_authorized": False,
            "task_semantic_redesign_authorized": False,
            "online_generation_authorized": False,
            "benchmark_distribution_inference_authorized": False,
            "qa_release_authorized": False,
            "schema_version": "qa_archive_parameter_space_transition.v1",
        },
        "transition_id",
        "qa_archive_parameter_space_transition:",
    )
    report = _identified(
        {
            "authorization_id": authorization_id,
            "predecessor_freeze_id": predecessor["freeze_id"],
            "source_binding_id": source["binding_id"],
            "archive_binding_id": archive["binding_id"],
            "catalog_freeze_id": catalog_freeze["freeze_id"],
            "parameter_space_audit_id": parameter_space["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "case_count": aggregate["case_count"],
            "constructible_count": aggregate["constructible_count"],
            "blocked_count": aggregate["blocked_count"],
            "task_constructible_counts": aggregate["task_constructible_counts"],
            "task_distinct_binding_counts": aggregate["task_distinct_binding_counts"],
            "semantic_depth_distribution": aggregate["semantic_depth_distribution"],
            "numeric_relationship_distribution": aggregate["numeric_relationship_distribution"],
            "passed_count": gate["passed_count"],
            "failed_count": gate["failed_count"],
            "first_blocker": decision["first_blocker"],
            "provider_calls": 0,
            "scope_claim": "archive_grounded_parameter_space_constructibility_preflight_only",
            "schema_version": "qa_archive_parameter_space_report.v1",
        },
        "report_id",
        "qa_archive_parameter_space_report:",
    )
    return models.Products(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        predecessor_freeze=predecessor,
        source_binding=source,
        archive_binding=archive,
        archive_records=selected_rows,
        catalog_freeze=catalog_freeze,
        case_rows=case_rows,
        parameter_space_audit=parameter_space,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
        bundles=runtime["bundles"],
        discovery_receipts=runtime["discovery_receipts"],
        packages=runtime["packages"],
        executions=runtime["executions"],
        verification_reports=runtime["verification_reports"],
        assessments=runtime["assessments"],
        depth_metrics=runtime["depth_metrics"],
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def write_qa_semantic_depth_three_archive_grounding_artifacts(
    products: models.Products, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "archive_binding.json": canonical_json_bytes(products.archive_binding) + b"\n",
        "archive_records.jsonl": _jsonl(products.archive_records),
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "catalog_freeze.json": canonical_json_bytes(products.catalog_freeze) + b"\n",
        "catalog_resolution_receipts.jsonl": _jsonl(products.discovery_receipts),
        "decision.json": canonical_json_bytes(products.decision) + b"\n",
        "depth_metrics.jsonl": _jsonl(products.depth_metrics),
        "evidence_bundles.jsonl": _jsonl(products.bundles),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(products.gate) + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_audit) + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "parameter_case_rows.jsonl": _jsonl(products.case_rows),
        "parameter_space_audit.json": canonical_json_bytes(products.parameter_space_audit) + b"\n",
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
            members, prefix="qa_archive_parameter_space_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "qa_archive_parameter_space_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    body, prefix="qa_archive_parameter_space_artifact_manifest:"
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
    products = build_qa_semantic_depth_three_archive_grounding_preflight(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_qa_semantic_depth_three_archive_grounding_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
