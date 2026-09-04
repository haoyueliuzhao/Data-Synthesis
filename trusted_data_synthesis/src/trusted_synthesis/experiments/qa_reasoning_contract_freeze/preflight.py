from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from . import models
from .contracts import (
    ReasoningContractAdmissionError,
    admit_qualification,
    admit_reasoning_action,
    admit_reasoning_trajectory,
    admit_target_evidence,
    build_conformance_objects,
    build_contract_descriptors,
    build_coverage_matrix,
    build_target_contract,
    identified,
    require_distinct_quotient_states,
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
        raise ValueError("external reasoning-bearing QA audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT or _sha(directive) != (
        models.OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("reasoning-bearing QA operator directive bytes differ")
    return (
        _identified(
            {
                "stage": models.STAGE,
                "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
                "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
                "operator_directive": models.OPERATOR_DIRECTIVE,
                "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
                "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
                "scientific_object_contract_freeze_authorized": True,
                "current_archive_preflight_rerun_authorized": False,
                "current_formal_artifact_rewrite_authorized": False,
                "archive_expansion_authorized": False,
                "task_semantic_redesign_authorized": False,
                "fixed_fixture_execution_authorized": False,
                "provider_execution_authorized": False,
                "gpu_execution_authorized": False,
                "online_generation_authorized": False,
                "qa_release_authorized": False,
                "vtdo_authorized": False,
                "schema_version": "finance_qa_reasoning_contract_freeze_authorization.v1",
            },
            "authorization_id",
            "finance_qa_reasoning_contract_freeze_authorization:",
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
        raise ValueError("Archive constructibility predecessor geometry differs")
    manifest = json.loads(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest["members"]}
    if (
        len(members) != models.PREDECESSOR_MEMBER_COUNT
        or int(manifest["member_bytes"]) != models.PREDECESSOR_MEMBER_BYTES
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        raise ValueError("Archive constructibility predecessor Manifest differs")
    for path, row in members.items():
        payload = files[path]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            raise ValueError(f"Archive constructibility predecessor member differs:{path}")
    report = json.loads(files["report.json"])
    gate = json.loads(files["gate_evaluation.json"])
    decision = json.loads(files["decision.json"])
    transition = json.loads(files["transition.json"])
    scope = json.loads(files["scope_boundary_audit.json"])
    parameter = json.loads(files["parameter_space_audit.json"])
    if (
        manifest["manifest_id"] != models.PREDECESSOR_MANIFEST_ID
        or manifest["artifact_root"] != models.PREDECESSOR_ROOT_ID
        or report["report_id"] != models.PREDECESSOR_REPORT_ID
        or gate["gate_id"] != models.PREDECESSOR_GATE_ID
        or decision["decision_id"] != models.PREDECESSOR_DECISION_ID
        or transition["transition_id"] != models.PREDECESSOR_TRANSITION_ID
        or gate["passed_count"] != 7
        or gate["failed_count"] != 1
        or gate["failed_gate_ids"]
        != ["G4_both_registered_depth_three_types_have_multiple_archive_bindings"]
        or decision["first_blocker"] != "authoritative_gross_margin_target_evidence_absent"
        or parameter["task_constructible_counts"]
        != {"derived_growth_absolute_spread": 9, "registered_margin_target_gap": 0}
        or scope["provider_calls"] != 0
    ):
        raise ValueError("Archive constructibility negative decision authority differs")
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
            "accepted_as_valid_negative_result": True,
            "scientific_gate_failed_at_g4": True,
            "current_stage_rerun_required": False,
            "formal_artifact_rewrite_performed": False,
            "schema_version": "finance_qa_reasoning_contract_predecessor_freeze.v1",
        },
        "freeze_id",
        "finance_qa_reasoning_contract_predecessor_freeze:",
    )


def _scope_clarification(predecessor_freeze_id: str) -> dict[str, Any]:
    return _identified(
        {
            "predecessor_freeze_id": predecessor_freeze_id,
            "clarifications": (
                {
                    "subject": "target_evidence_absence",
                    "narrow_meaning": (
                        "absent_from_current_admitted_frozen_finqa_table_cell_adapter_domain"
                    ),
                    "forbidden_broad_meaning": "absent_from_all_real_world_financial_sources",
                },
                {
                    "subject": "g6_coverage",
                    "narrow_meaning": "coverage_among_nine_admitted_branch_cases_only",
                    "forbidden_broad_meaning": "coverage_shared_by_both_registered_task_types",
                },
                {
                    "subject": "semantic_operation_depth",
                    "narrow_meaning": "deterministic_answer_program_semantic_dependency_depth",
                    "forbidden_broad_meaning": "model_reasoning_or_critical_decision_depth",
                },
            ),
            "archive_bindings_are_distinct_task_instances": True,
            "same_task_multitrajectory_support_established": False,
            "predecessor_formal_bytes_modified": False,
            "schema_version": "finance_qa_archive_negative_result_scope_clarification.v1",
        },
        "clarification_id",
        "finance_qa_archive_negative_result_scope_clarification:",
    )


def _source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    resolved_commit = _git_text(root, "rev-parse", f"{source_commit}^{{commit}}")
    resolved_tree = _git_text(root, "rev-parse", f"{resolved_commit}^{{tree}}")
    if source_commit != resolved_commit or source_tree != resolved_tree:
        raise ValueError("reasoning Contract source commit/tree relation differs")
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
            raise ValueError(f"reasoning Contract source member differs:{path}")
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
            "schema_version": "finance_qa_reasoning_contract_source_binding.v1",
        },
        "binding_id",
        "finance_qa_reasoning_contract_source_binding:",
    )


def _replace_identified(model: Any, field: str, prefix: str, **updates: Any) -> Any:
    values = {name: getattr(model, name) for name in type(model).model_fields if name != field}
    values.update(updates)
    return identified(type(model), values, field, prefix)


def _negative_controls(
    authorization_id: str,
    objects: Mapping[str, Any],
    target_contract: models.TargetEvidenceAuthorityContractV1,
) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def reject(name: str, expected_stage: str, action: Callable[[], Any]) -> None:
        try:
            action()
        except (ReasoningContractAdmissionError, ValidationError, ValueError) as exc:
            stage = (
                exc.stage
                if isinstance(exc, ReasoningContractAdmissionError)
                else "model.validation"
            )
            if stage != expected_stage:
                raise ValueError(
                    f"reasoning attack rejected at {stage}, expected {expected_stage}:{name}"
                ) from exc
            controls.append(
                {
                    "name": name,
                    "rejection_stage": stage,
                    "exception_type": type(exc).__name__,
                    "reason_sha256": _sha(str(exc).encode("utf-8")),
                    "rejected": True,
                    "output_writes": 0,
                    "provider_calls": 0,
                }
            )
            return
        raise ValueError(f"reasoning Contract attack accepted:{name}")

    envelope = objects["reasoning_action"]
    state = objects["initial_state"]
    graph = objects["critical_decision_graph"]
    execution = objects["action_execution"]
    observation = objects["observation"]
    update = objects["observation_update"]
    trajectory = objects["reasoning_trajectory"]
    answer = objects["answer_validity"]
    trajectory_validity = objects["trajectory_validity"]

    late = _replace_identified(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        preaction_commit_sequence=execution.execution_sequence,
    )
    reject(
        "post_action_reasoning_backfill",
        "reasoning.preaction_commit",
        lambda: admit_reasoning_action(late, state, graph, execution),
    )
    reject(
        "generic_rationale_without_evidence",
        "model.validation",
        lambda: _replace_identified(
            envelope,
            "envelope_id",
            "reasoning_action_envelope:",
            evidence_refs=(),
            decision_basis=(),
        ),
    )
    crossed_state = _replace_identified(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        state_id="public_reasoning_state:crossed",
        action=envelope.action.model_copy(update={"state_id": "public_reasoning_state:crossed"}),
    )
    reject(
        "cross_state_reasoning",
        "reasoning.state_binding",
        lambda: admit_reasoning_action(crossed_state, state, graph),
    )
    crossed_execution = _replace_identified(
        execution,
        "execution_id",
        "reasoning_action_execution:",
        action_id="action:verify_alignment_alternative",
    )
    reject(
        "reasoning_action_mismatch",
        "reasoning.action_consistency",
        lambda: admit_reasoning_action(envelope, state, graph, crossed_execution),
    )
    future_ref = _replace_identified(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        evidence_refs=(*envelope.evidence_refs, "evidence:future_observation"),
    )
    reject(
        "future_evidence_reference",
        "reasoning.visible_refs",
        lambda: admit_reasoning_action(future_ref, state, graph),
    )
    bad_claim = update.accepted_claims[0].model_copy(
        update={"support_observation_refs": ("observation:crossed",)}
    )
    reject(
        "observation_claim_update_mismatch",
        "model.validation",
        lambda: _replace_identified(
            update,
            "update_id",
            "observation_update:",
            accepted_claims=(bad_claim,),
        ),
    )
    actual = models.TargetEvidenceCandidateV1(
        evidence_id="evidence:observed_actual_margin",
        task_instance_id="fixture:target_gap",
        metric_definition_id="gross_margin.v1",
        target_modality="observed_actual",
        source_authority="issuer_filing",
        issuer_or_author="Example Issuer",
        statement_as_of="2026-01-01",
        effective_period="FY2026",
        entity_scope="Example Issuer consolidated",
        unit="percent",
        gaap_or_non_gaap_basis="GAAP",
        exact_text_or_table_locator="table:actual_margin:R2C3",
        source_document_id="document:example",
    )
    reject(
        "actual_margin_relabelled_as_target",
        "target.modality",
        lambda: admit_target_evidence(actual, target_contract),
    )
    missing = _replace_identified(
        trajectory,
        "trajectory_id",
        "reasoning_trajectory:",
        covered_decision_ids=("decision:unrelated",),
    )
    reject(
        "correct_final_with_missing_decision_obligation",
        "reasoning.critical_coverage",
        lambda: admit_reasoning_trajectory(
            missing, graph, (envelope,), (execution,), (observation,), (update,)
        ),
    )
    invalid_answer = identified(
        models.AnswerValidityReportV1,
        {
            "task_instance_id": answer.task_instance_id,
            "source_valid": True,
            "answer_valid": False,
            "citation_valid": False,
            "qa_valid": False,
        },
        "report_id",
        "answer_validity_report:",
    )
    nonqualified = identified(
        models.QualifiedReasoningTrajectoryV1,
        {
            "task_instance_id": trajectory.task_instance_id,
            "trajectory_id": trajectory.trajectory_id,
            "answer_validity_report_id": invalid_answer.report_id,
            "trajectory_validity_report_id": trajectory_validity.report_id,
            "qa_valid": False,
            "trajectory_valid": True,
            "qualified": False,
        },
        "qualification_id",
        "qualified_reasoning_trajectory:",
    )
    reject(
        "valid_reasoning_with_invalid_final_or_citation",
        "reasoning.qualification",
        lambda: admit_qualification(nonqualified, invalid_answer, trajectory_validity),
    )
    paraphrase = _replace_identified(
        trajectory,
        "trajectory_id",
        "reasoning_trajectory:",
        wording_fingerprint="wording:fixture-b",
    )
    reject(
        "paraphrase_only_trajectories_as_distinct_quotient_states",
        "reasoning.quotient_state",
        lambda: require_distinct_quotient_states(trajectory, paraphrase),
    )
    if tuple(row["name"] for row in controls) != models.ATTACK_NAMES:
        raise ValueError("reasoning Contract attack domain differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "controls": tuple(controls),
            "attempted_count": len(controls),
            "rejected_count": sum(bool(row["rejected"]) for row in controls),
            "accepted_count": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "schema_version": "finance_qa_reasoning_contract_negative_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_negative_audit:",
    )


def build_finance_qa_reasoning_contract_freeze(
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
    clarification = _scope_clarification(predecessor["freeze_id"])
    source = _source_binding(root, authorization_id, source_commit, source_tree)
    descriptors = build_contract_descriptors()
    target_contract = build_target_contract()
    coverage_matrix = build_coverage_matrix()
    objects = build_conformance_objects()
    object_ids = {
        key: next(
            value
            for field, value in item.model_dump(mode="json").items()
            if field.endswith("_id") and field in type(item).model_fields
        )
        for key, item in objects.items()
    }
    conformance = _identified(
        {
            "authorization_id": authorization_id,
            "source_binding_id": source["binding_id"],
            "contract_ids": tuple(item.contract_id for item in descriptors),
            "contract_count": len(descriptors),
            "contract_names": tuple(item.name for item in descriptors),
            "scientific_object_ids": object_ids,
            "scientific_object_count": len(objects),
            "state_reasoning_action_execution_observation_update_state_chains": 1,
            "preaction_commits": 1,
            "post_action_reasoning_backfills": 0,
            "answer_oracle_prescribes_unique_reasoning_path": False,
            "private_chain_of_thought_fields": 0,
            "qa_and_trajectory_validity_separate": True,
            "qualification_noncompensatory": True,
            "target_allowed_modalities": target_contract.allowed_modalities,
            "target_forbidden_modalities": target_contract.forbidden_modalities,
            "depth_metric_names": (
                "semantic_operation_depth",
                "reasoning_depth",
                "evidence_integration_depth",
                "correction_depth",
                "critical_decision_coverage",
            ),
            "depth_metrics_noninterchangeable": True,
            "coverage_matrix_axis_count": len(coverage_matrix.axis_values),
            "future_minimum_fixture_archetype_count": len(
                coverage_matrix.minimum_constructive_cells
            ),
            "model_capability_measured": False,
            "schema_version": "finance_qa_reasoning_contract_conformance_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_conformance_audit:",
    )
    negative = _negative_controls(authorization_id, objects, target_contract)
    scope = _identified(
        {
            "authorization_id": authorization_id,
            "predecessor_freeze_id": predecessor["freeze_id"],
            "scope_clarification_id": clarification["clarification_id"],
            "source_binding_id": source["binding_id"],
            "conformance_audit_id": conformance["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "predecessor_formal_writes": 0,
            "archive_reads": 0,
            "archive_expansions": 0,
            "provider_calls": 0,
            "credential_lookups": 0,
            "gpu_jobs": 0,
            "online_jobs": 0,
            "model_responses": 0,
            "fixed_fixture_qa_executions": 0,
            "empirical_rows": 0,
            "benchmark_distribution_rows": 0,
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
            "claim_is_contract_freeze_only": True,
            "schema_version": "finance_qa_reasoning_contract_scope_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_scope_audit:",
    )
    gates = {
        "G0_exact_external_scope_and_valid_negative_predecessor_freeze": True,
        "G1_three_bounded_scope_clarifications_and_zero_predecessor_rewrite": (
            len(clarification["clarifications"]) == 3
            and clarification["predecessor_formal_bytes_modified"] is False
        ),
        "G2_exact_source_and_ten_contract_descriptors": (
            source["all_current_bytes_equal_committed_bytes"]
            and conformance["contract_count"] == len(models.CONTRACT_NAMES) == 10
            and conformance["contract_names"] == models.CONTRACT_NAMES
        ),
        "G3_answer_oracle_and_critical_decision_graph_separated": (
            objects["answer_oracle_binding"].prescribes_unique_reasoning_path is False
            and objects["critical_decision_graph"].allows_multiple_valid_orders
            and objects["critical_decision_graph"].answer_oracle_program_binding_id
            == objects["answer_oracle_binding"].binding_id
        ),
        "G4_preaction_reasoning_action_observation_update_state_chain": (
            objects["reasoning_action"].preaction_commit_sequence
            < objects["action_execution"].execution_sequence
            and objects["observation_update"].next_state_id == objects["next_state"].state_id
            and conformance["state_reasoning_action_execution_observation_update_state_chains"] == 1
        ),
        "G5_noncompensatory_validity_target_depth_and_coverage_contracts": (
            objects["qualification"].qualified
            and objects["depth_metrics"].metrics_noninterchangeable
            and set(target_contract.allowed_modalities) == {"management_target", "company_guidance"}
            and coverage_matrix.coverage_measured is False
        ),
        "G6_ten_direct_contract_counterexamples_reject": (
            negative["rejected_count"] == len(models.ATTACK_NAMES)
            and negative["accepted_count"] == 0
        ),
        "G7_zero_execution_archive_release_and_vtdo_scope": not any(
            scope[key]
            for key in (
                "predecessor_formal_writes",
                "archive_reads",
                "archive_expansions",
                "provider_calls",
                "credential_lookups",
                "gpu_jobs",
                "online_jobs",
                "model_responses",
                "fixed_fixture_qa_executions",
                "empirical_rows",
                "benchmark_distribution_rows",
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
            )
        ),
    }
    gate = _identified(
        {
            "gates": gates,
            "passed_count": sum(gates.values()),
            "failed_count": len(gates) - sum(gates.values()),
            "noncompensatory": True,
            "schema_version": "finance_qa_reasoning_contract_gate.v1",
        },
        "gate_id",
        "finance_qa_reasoning_contract_gate:",
    )
    if gate["failed_count"]:
        raise ValueError("reasoning-bearing scientific-object Contract Gate failed")
    decision = _identified(
        {
            "gate_id": gate["gate_id"],
            "decision": models.DECISION,
            "current_archive_negative_result_retained": True,
            "answer_program_and_reasoning_trajectory_separated": True,
            "public_reasoning_contracts_frozen": True,
            "target_evidence_authority_contract_frozen": True,
            "depth_metrics_separated": True,
            "coverage_matrix_frozen_not_measured": True,
            "fixed_fixture_constructibility_established": False,
            "archive_grounded_reasoning_trajectory_established": False,
            "model_capability_established": False,
            "qa_release_eligible": False,
            "schema_version": "finance_qa_reasoning_contract_decision.v1",
        },
        "decision_id",
        "finance_qa_reasoning_contract_decision:",
    )
    transition = _identified(
        {
            "decision_id": decision["decision_id"],
            "next_stage": models.NEXT_STAGE,
            "next_stage_authorized": True,
            "independent_audit_only": True,
            "fixed_fixture_execution_authorized": False,
            "archive_expansion_authorized": False,
            "provider_execution_authorized": False,
            "online_calibration_authorized": False,
            "qa_release_authorized": False,
            "vtdo_authorized": False,
            "schema_version": "finance_qa_reasoning_contract_transition.v1",
        },
        "transition_id",
        "finance_qa_reasoning_contract_transition:",
    )
    report = _identified(
        {
            "authorization_id": authorization_id,
            "predecessor_freeze_id": predecessor["freeze_id"],
            "scope_clarification_id": clarification["clarification_id"],
            "source_binding_id": source["binding_id"],
            "contract_ids": tuple(item.contract_id for item in descriptors),
            "target_contract_id": target_contract.contract_id,
            "coverage_matrix_id": coverage_matrix.matrix_id,
            "conformance_audit_id": conformance["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "decision": models.DECISION,
            "contract_count": len(descriptors),
            "scientific_object_count": len(objects),
            "negative_controls": negative["attempted_count"],
            "provider_calls": 0,
            "claim_boundary": "scientific_object_and_contract_freeze_only",
            "schema_version": "finance_qa_reasoning_contract_report.v1",
        },
        "report_id",
        "finance_qa_reasoning_contract_report:",
    )
    return models.Products(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        predecessor_freeze=predecessor,
        scope_clarification=clarification,
        source_binding=source,
        contract_descriptors=descriptors,
        target_contract=target_contract,
        coverage_matrix=coverage_matrix,
        conformance_audit=conformance,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
        **objects,
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def write_finance_qa_reasoning_contract_freeze_artifacts(
    products: models.Products, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "action_execution.json": canonical_json_bytes(products.action_execution) + b"\n",
        "answer_oracle_program_binding.json": canonical_json_bytes(products.answer_oracle_binding)
        + b"\n",
        "answer_validity_report.json": canonical_json_bytes(products.answer_validity) + b"\n",
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "contract_descriptors.jsonl": _jsonl(products.contract_descriptors),
        "conformance_audit.json": canonical_json_bytes(products.conformance_audit) + b"\n",
        "coverage_matrix.json": canonical_json_bytes(products.coverage_matrix) + b"\n",
        "critical_decision_graph.json": canonical_json_bytes(products.critical_decision_graph)
        + b"\n",
        "decision.json": canonical_json_bytes(products.decision) + b"\n",
        "depth_metrics.json": canonical_json_bytes(products.depth_metrics) + b"\n",
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(products.gate) + b"\n",
        "initial_public_reasoning_state.json": canonical_json_bytes(products.initial_state) + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_audit) + b"\n",
        "next_public_reasoning_state.json": canonical_json_bytes(products.next_state) + b"\n",
        "observation_update.json": canonical_json_bytes(products.observation_update) + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "predecessor_freeze.json": canonical_json_bytes(products.predecessor_freeze) + b"\n",
        "public_observation.json": canonical_json_bytes(products.observation) + b"\n",
        "qualified_reasoning_trajectory.json": canonical_json_bytes(products.qualification) + b"\n",
        "reasoning_action_envelope.json": canonical_json_bytes(products.reasoning_action) + b"\n",
        "reasoning_trajectory.json": canonical_json_bytes(products.reasoning_trajectory) + b"\n",
        "scope_boundary_audit.json": canonical_json_bytes(products.scope_audit) + b"\n",
        "scope_clarification.json": canonical_json_bytes(products.scope_clarification) + b"\n",
        "source_binding.json": canonical_json_bytes(products.source_binding) + b"\n",
        "target_evidence_authority_contract.json": canonical_json_bytes(products.target_contract)
        + b"\n",
        "trajectory_validity_report.json": canonical_json_bytes(products.trajectory_validity)
        + b"\n",
        "transition.json": canonical_json_bytes(products.transition) + b"\n",
        "report.json": canonical_json_bytes(products.report) + b"\n",
    }
    members = tuple(
        {"relative_path": path, "sha256": _sha(payload), "byte_count": len(payload)}
        for path, payload in sorted(payloads.items())
    )
    body = {
        "members": members,
        "file_count": len(members),
        "member_bytes": sum(map(len, payloads.values())),
        "artifact_root": strict_canonical_hash(
            members, prefix="finance_qa_reasoning_contract_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "finance_qa_reasoning_contract_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    body, prefix="finance_qa_reasoning_contract_artifact_manifest:"
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
    products = build_finance_qa_reasoning_contract_freeze(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_finance_qa_reasoning_contract_freeze_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
