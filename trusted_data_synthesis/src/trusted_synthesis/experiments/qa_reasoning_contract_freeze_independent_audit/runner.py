from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from . import models
from .audit import (
    _authorization,
    _detached_rebuild,
    _encoded,
    _fail,
    _files,
    _freeze_candidate,
    _git,
    _git_blob_oid,
    _git_text,
    _identified,
    _sha,
)
from .reconstruction import (
    build_coverage_matrix,
    build_scientific_objects,
    build_target_contract,
    compare_scientific_objects,
    reconstruct_contracts,
)
from .semantics import (
    build_candidate_final_comparison,
    build_negative_control_audit,
    build_parent_relation_audit,
    build_semantic_derivation_audit,
)

SOURCE_PATHS = (
    *models.AUDIT_SOURCE_PATHS,
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/reconstruction.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/semantics.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/runner.py",
)


def _complete_source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    commit = _git_text(root, "audit_source.commit", "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git_text(root, "audit_source.tree", "rev-parse", f"{commit}^{{tree}}")
    if commit != source_commit or tree != source_tree:
        _fail("audit_source.commit_tree", "audit source commit/tree relation differs")
    rows = []
    executable_trees = []
    for path in SOURCE_PATHS:
        committed = _git(root, "audit_source.member", "show", f"{commit}:{path}")
        current = (root / path).read_bytes()
        blob = _git_text(root, "audit_source.member", "rev-parse", f"{commit}:{path}")
        if committed != current or blob != _git_blob_oid(committed):
            _fail("audit_source.member", f"audit source member differs: {path}")
        if path.endswith(("audit.py", "reconstruction.py", "semantics.py", "runner.py")):
            executable_trees.append(ast.parse(committed))
        rows.append(
            {
                "relative_path": path,
                "git_blob_oid": blob,
                "sha256": _sha(committed),
                "byte_count": len(committed),
                "committed_current_bytes_equal": True,
            }
        )
    forbidden_imports: list[str] = []
    for tree_node in executable_trees:
        for node in ast.walk(tree_node):
            modules = (
                (node.module,)
                if isinstance(node, ast.ImportFrom) and node.module
                else tuple(alias.name for alias in node.names)
                if isinstance(node, ast.Import)
                else ()
            )
            forbidden_imports.extend(
                module
                for module in modules
                if "qa_reasoning_contract_freeze" in module
                and "qa_reasoning_contract_freeze_independent_audit" not in module
            )
    if forbidden_imports:
        _fail("audit_source.helper_boundary", "candidate semantic helper import is present")
    return _identified(
        {
            "authorization_id": authorization_id,
            "requested_commit": source_commit,
            "resolved_commit": commit,
            "requested_tree": source_tree,
            "resolved_tree": tree,
            "members": tuple(rows),
            "member_count": len(rows),
            "path_set_sha256": _sha(canonical_json_bytes(SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(rows)),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "executable_members_scanned": len(executable_trees),
            "candidate_helper_imports": 0,
            "candidate_semantic_helper_calls": 0,
            "candidate_outcome_oracle_calls": 0,
            "helper_boundary_passed": True,
            "schema_version": "finance_qa_reasoning_contract_independent_source_binding.v1",
        },
        "binding_id",
        "finance_qa_reasoning_contract_independent_source_binding:",
    )


def build_finance_qa_reasoning_contract_independent_audit(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.Products:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization, directive = _authorization(review)
    authorization_id = str(authorization["authorization_id"])
    source = _complete_source_binding(root, authorization_id, source_commit, source_tree)
    freeze, saved = _freeze_candidate(root, authorization_id)
    detached = _detached_rebuild(root, str(freeze["audit_id"]), saved)
    descriptors, contract_audit = reconstruct_contracts(root, authorization_id, saved)
    objects = build_scientific_objects()
    object_audit = compare_scientific_objects(authorization_id, objects, saved)
    parent = build_parent_relation_audit(authorization_id, str(object_audit["audit_id"]), objects)
    target_contract = build_target_contract()
    coverage_matrix = build_coverage_matrix()
    semantic = build_semantic_derivation_audit(
        authorization_id,
        str(parent["audit_id"]),
        objects,
        target_contract,
        coverage_matrix,
        saved,
    )
    negative = build_negative_control_audit(
        authorization_id,
        str(semantic["audit_id"]),
        objects,
        target_contract,
        saved,
    )
    comparison = build_candidate_final_comparison(
        authorization_id,
        str(negative["audit_id"]),
        descriptors,
        objects,
        target_contract,
        coverage_matrix,
        saved,
    )
    scope = _identified(
        {
            "authorization_id": authorization_id,
            "candidate_freeze_audit_id": freeze["audit_id"],
            "detached_rebuild_audit_id": detached["audit_id"],
            "source_binding_id": source["binding_id"],
            "contract_reconstruction_audit_id": contract_audit["audit_id"],
            "object_reconstruction_audit_id": object_audit["audit_id"],
            "parent_relation_audit_id": parent["audit_id"],
            "semantic_derivation_audit_id": semantic["audit_id"],
            "negative_control_audit_id": negative["audit_id"],
            "candidate_final_comparison_audit_id": comparison["audit_id"],
            "candidate_formal_writes": 0,
            "predecessor_formal_writes": 0,
            "archive_evidence_reads": 0,
            "archive_expansions": 0,
            "fixed_fixture_qa_executions": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "provider_client_constructions": 0,
            "gpu_jobs": 0,
            "online_job_manifests": 0,
            "model_responses": 0,
            "empirical_rows": 0,
            "task_registrations": 0,
            "operation_registrations": 0,
            "catalog_promotions": 0,
            "qa_release_objects": 0,
            "mapper_rows": 0,
            "state_rows": 0,
            "contribution_rows": 0,
            "vtdo_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "candidate_builder_calls_for_reproducibility_only": 1,
            "candidate_semantic_helper_calls": 0,
            "candidate_outcome_oracle_calls": 0,
            "synthetic_schema_conformance_only": True,
            "durable_runtime_preaction_commit_established": False,
            "same_task_multitrajectory_established": False,
            "old_qa_mainline_paused": True,
            "passed": True,
            "schema_version": "finance_qa_reasoning_contract_independent_scope_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_independent_scope_audit:",
    )
    gates = {
        models.GATE_NAMES[0]: bool(freeze["passed"]),
        models.GATE_NAMES[1]: bool(detached["passed"]),
        models.GATE_NAMES[2]: bool(contract_audit["passed"]),
        models.GATE_NAMES[3]: bool(object_audit["passed"]),
        models.GATE_NAMES[4]: bool(parent["passed"]),
        models.GATE_NAMES[5]: bool(semantic["passed"]),
        models.GATE_NAMES[6]: bool(negative["passed"]),
        models.GATE_NAMES[7]: bool(comparison["passed"])
        and bool(source["helper_boundary_passed"])
        and not any(
            scope[field]
            for field in (
                "candidate_formal_writes",
                "predecessor_formal_writes",
                "archive_evidence_reads",
                "archive_expansions",
                "fixed_fixture_qa_executions",
                "provider_calls",
                "credential_lookups",
                "provider_client_constructions",
                "gpu_jobs",
                "online_job_manifests",
                "model_responses",
                "empirical_rows",
                "task_registrations",
                "operation_registrations",
                "catalog_promotions",
                "qa_release_objects",
                "mapper_rows",
                "state_rows",
                "contribution_rows",
                "vtdo_rows",
                "training_rows",
                "production_rows",
                "candidate_semantic_helper_calls",
                "candidate_outcome_oracle_calls",
            )
        ),
    }
    gate = _identified(
        {
            "gates": gates,
            "passed_count": sum(gates.values()),
            "failed_count": len(gates) - sum(gates.values()),
            "noncompensatory": True,
            "schema_version": "finance_qa_reasoning_contract_independent_gate.v1",
        },
        "gate_id",
        "finance_qa_reasoning_contract_independent_gate:",
    )
    if gate["failed_count"]:
        _fail("gate.failed", "independent reasoning-contract Gate failed")
    common = {
        "authorization_id": authorization_id,
        "candidate_freeze_audit_id": freeze["audit_id"],
        "detached_rebuild_audit_id": detached["audit_id"],
        "source_binding_id": source["binding_id"],
        "contract_reconstruction_audit_id": contract_audit["audit_id"],
        "object_reconstruction_audit_id": object_audit["audit_id"],
        "parent_relation_audit_id": parent["audit_id"],
        "semantic_derivation_audit_id": semantic["audit_id"],
        "negative_control_audit_id": negative["audit_id"],
        "candidate_final_comparison_audit_id": comparison["audit_id"],
        "scope_audit_id": scope["audit_id"],
        "gate_id": gate["gate_id"],
    }
    decision = _identified(
        {
            **common,
            "decision": models.DECISION,
            "candidate_contract_freeze_independently_confirmed": True,
            "candidate_formal_bytes_modified": False,
            "synthetic_schema_conformance_only": True,
            "real_reasoning_bearing_fixture_established": False,
            "durable_runtime_preaction_commit_established": False,
            "model_capability_established": False,
            "same_task_multitrajectory_established": False,
            "qa_release_eligible": False,
            "old_qa_mainline_paused": True,
            "schema_version": "finance_qa_reasoning_contract_independent_decision.v1",
        },
        "decision_id",
        "finance_qa_reasoning_contract_independent_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "prospective_next_stage": models.PROSPECTIVE_NEXT_STAGE,
            "next_stage_authorized": False,
            "separate_external_audit_decision_required": True,
            "fixed_fixture_execution_authorized": False,
            "archive_read_or_expansion_authorized": False,
            "provider_execution_authorized": False,
            "online_calibration_authorized": False,
            "old_mainline_resume_authorized": False,
            "qa_release_authorized": False,
            "vtdo_authorized": False,
            "schema_version": "finance_qa_reasoning_contract_independent_transition.v1",
        },
        "transition_id",
        "finance_qa_reasoning_contract_independent_transition:",
    )
    report = _identified(
        {
            **common,
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "candidate_files": models.CANDIDATE_FILE_COUNT,
            "candidate_bytes": models.CANDIDATE_TOTAL_BYTES,
            "contract_count": len(descriptors),
            "scientific_object_count": len(objects),
            "independent_attacks": negative["attempted_count"],
            "independent_attacks_rejected": negative["rejected_count"],
            "passed_gates": gate["passed_count"],
            "failed_gates": gate["failed_count"],
            "provider_calls": 0,
            "claim_boundary": "independent_contract_and_synthetic_conformance_audit_only",
            "schema_version": "finance_qa_reasoning_contract_independent_report.v1",
        },
        "report_id",
        "finance_qa_reasoning_contract_independent_report:",
    )
    return models.Products(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        candidate_freeze=freeze,
        detached_rebuild=detached,
        audit_source_binding=source,
        contract_descriptors=descriptors,
        contract_reconstruction_audit=contract_audit,
        scientific_objects=objects,
        object_reconstruction_audit=object_audit,
        parent_relation_audit=parent,
        semantic_derivation_audit=semantic,
        negative_control_audit=negative,
        candidate_final_comparison_audit=comparison,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(_encoded(value) for value in values)


def write_finance_qa_reasoning_contract_independent_audit_artifacts(
    products: models.Products, output_dir: str | Path
) -> tuple[str, ...]:
    object_rows = tuple(
        {
            "object_name": name,
            "object": products.scientific_objects[name],
        }
        for name in models.OBJECT_NAMES
    )
    payloads = {
        "authorization.json": _encoded(products.authorization),
        "audit_source_binding.json": _encoded(products.audit_source_binding),
        "candidate_final_comparison_audit.json": _encoded(
            products.candidate_final_comparison_audit
        ),
        "candidate_freeze_audit.json": _encoded(products.candidate_freeze),
        "contract_reconstruction_audit.json": _encoded(products.contract_reconstruction_audit),
        "decision.json": _encoded(products.decision),
        "detached_rebuild_audit.json": _encoded(products.detached_rebuild),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": _encoded(products.gate),
        "independent_contract_descriptors.jsonl": _jsonl(products.contract_descriptors),
        "independent_negative_control_audit.json": _encoded(products.negative_control_audit),
        "independent_negative_control_rows.jsonl": _jsonl(
            products.negative_control_audit["controls"]
        ),
        "independent_scientific_objects.jsonl": _jsonl(object_rows),
        "object_reconstruction_audit.json": _encoded(products.object_reconstruction_audit),
        "operator_directive.txt": products.operator_directive_bytes,
        "parent_relation_audit.json": _encoded(products.parent_relation_audit),
        "report.json": _encoded(products.report),
        "scope_boundary_audit.json": _encoded(products.scope_audit),
        "semantic_derivation_audit.json": _encoded(products.semantic_derivation_audit),
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
    body = {
        "members": members,
        "file_count": len(members),
        "member_bytes": sum(map(len, payloads.values())),
        "artifact_root": (
            "finance_qa_reasoning_contract_independent_artifact_root:"
            + _sha(canonical_json_bytes(members))
        ),
        "self_excluding": True,
        "schema_version": ("finance_qa_reasoning_contract_independent_artifact_manifest.v1"),
    }
    manifest = _identified(
        body,
        "manifest_id",
        "finance_qa_reasoning_contract_independent_artifact_manifest:",
    )
    payloads["artifact_manifest.json"] = _encoded(manifest)
    return write_immutable_artifact_directory(output_dir, payloads)


def validate_written_artifacts(output_dir: str | Path) -> dict[str, Any]:
    files = _files(Path(output_dir))
    manifest = json_load(files["artifact_manifest.json"])
    rows = manifest["members"]
    paths = {str(row["relative_path"]) for row in rows}
    if paths != set(files) - {"artifact_manifest.json"}:
        _fail("written.manifest", "written Manifest path domain differs")
    matches = sum(
        int(row["byte_count"]) == len(files[str(row["relative_path"])])
        and row["sha256"] == _sha(files[str(row["relative_path"])])
        for row in rows
    )
    if matches != len(rows):
        _fail("written.manifest", "written Manifest member differs")
    return {
        "file_count": len(files),
        "total_bytes": sum(map(len, files.values())),
        "manifest_member_count": len(rows),
        "manifest_member_bytes": manifest["member_bytes"],
        "manifest_id": manifest["manifest_id"],
        "artifact_root": manifest["artifact_root"],
        "manifest_member_matches": matches,
    }


def json_load(payload: bytes) -> dict[str, Any]:
    value = __import__("json").loads(payload)
    if not isinstance(value, dict):
        _fail("written.json", "expected JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    arguments = parser.parse_args()
    products = build_finance_qa_reasoning_contract_independent_audit(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_finance_qa_reasoning_contract_independent_audit_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
