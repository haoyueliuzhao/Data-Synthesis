from __future__ import annotations

import ast
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from . import models
from .audit import _encoded, _fail, _git, _identified, _jsonl, _sha

CONTRACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "AnswerOracleProgramBindingContract",
        "scientific_object": "AnswerOracleProgramBindingV1",
        "model_class": "AnswerOracleProgramBindingV1",
        "invariants": (
            "answer correctness is recomputable from exact Evidence and Program",
            "citation and rounding authority are explicit",
            "the Oracle does not prescribe a unique reasoning route",
        ),
        "forbidden_substitutions": (
            "model reasoning trajectory",
            "private chain of thought",
            "single reference route",
        ),
        "claim_boundary": "answer correctness only; no reasoning-validity claim",
    },
    {
        "name": "CriticalDecisionGraphContract",
        "scientific_object": "CriticalDecisionGraphV1",
        "model_class": "CriticalDecisionGraphV1",
        "invariants": (
            "required decision obligations are unique and topologically ordered",
            "every required obligation has a direct counterfactual intervention",
            "multiple valid obligation orders may be admitted",
        ),
        "forbidden_substitutions": (
            "complete reference chain of thought",
            "language style",
            "answer Program node count",
        ),
        "claim_boundary": "critical public decision obligations only",
    },
    {
        "name": "PublicReasoningStateContract",
        "scientific_object": "PublicReasoningStateV1",
        "model_class": "PublicReasoningStateV1",
        "invariants": (
            "only currently visible Evidence and verified Claims are addressable",
            "available Actions and completed Actions are separate",
            "private reasoning content is never persisted",
        ),
        "forbidden_substitutions": (
            "future Observation",
            "cross-State Evidence",
            "private model reasoning",
        ),
        "claim_boundary": "public decision state, not hidden cognition",
    },
    {
        "name": "ReasoningActionEnvelopeContract",
        "scientific_object": "ReasoningActionEnvelopeV1",
        "model_class": "ReasoningActionEnvelopeV1",
        "invariants": (
            "structured reasoning and Action commit atomically before execution",
            "selected Action is among current candidates and equals the inner Action",
            "decision basis binds visible Evidence or verified Claims",
        ),
        "forbidden_substitutions": (
            "post-hoc rationale",
            "generic ungrounded rationale",
            "Action substitution",
        ),
        "claim_boundary": ("public structured decision record, never private chain of thought"),
    },
    {
        "name": "ObservationUpdateContract",
        "scientific_object": "ObservationUpdateV1",
        "model_class": "ObservationUpdateV1",
        "invariants": (
            "Update binds exact Envelope, execution, Observation, and next State",
            "every accepted/rejected/revised Claim cites the actual Observation",
            "remaining uncertainty and newly enabled Actions are explicit",
        ),
        "forbidden_substitutions": (
            "unbound Claim update",
            "Observation substitution",
            "silent State mutation",
        ),
        "claim_boundary": "public effect of an Observation on Claims and next State",
    },
    {
        "name": "ReasoningTrajectoryContract",
        "scientific_object": "ReasoningTrajectoryV1",
        "model_class": "ReasoningTrajectoryV1",
        "invariants": (
            "each step is State-Envelope-Execution-Observation-Update-State",
            "all ordered step domains have equal cardinality",
            "all required Critical Decision obligations are covered",
        ),
        "forbidden_substitutions": (
            "final rationale text",
            "cross-Job step",
            "missing obligation",
        ),
        "claim_boundary": ("time-ordered public reasoning/action/observation/update lineage"),
    },
    {
        "name": "ReasoningValidityContract",
        "scientific_object": (
            "AnswerValidityReportV1+TrajectoryValidityReportV1+QualifiedReasoningTrajectoryV1"
        ),
        "model_class": "QualifiedReasoningTrajectoryV1",
        "invariants": (
            "QA validity is source AND answer AND citation",
            "trajectory validity is preaction AND grounding AND reasoning-action AND "
            "observation-update AND critical coverage",
            "qualification is QA validity AND trajectory validity",
        ),
        "forbidden_substitutions": (
            "compensatory score",
            "correct-answer override",
            "fluent-language override",
        ),
        "claim_boundary": (
            "separate answer and trajectory validity with noncompensatory qualification"
        ),
    },
    {
        "name": "TargetEvidenceAuthorityContract",
        "scientific_object": "TargetEvidenceAuthorityContractV1",
        "model_class": "TargetEvidenceAuthorityContractV1",
        "invariants": (
            "target modality, source, issuer, as-of time, effective period, scope, unit, "
            "basis, and locator are bound",
            "registered margin target permits management target or company guidance only",
            "actual, consensus, peer benchmark, arbitrary constant, and derived margin "
            "are excluded",
        ),
        "forbidden_substitutions": (
            "observed actual",
            "analyst consensus",
            "arbitrary constant",
            "derived margin",
        ),
        "claim_boundary": ("authority for target-valued Evidence, not arithmetic correctness"),
    },
    {
        "name": "DepthMetricContract",
        "scientific_object": "ReasoningDepthMetricsV1",
        "model_class": "ReasoningDepthMetricsV1",
        "invariants": (
            "semantic-operation, reasoning, evidence-integration, and correction depths "
            "are distinct",
            "critical-decision coverage is derived from required obligations",
            "tokens and text length are never depth authority",
        ),
        "forbidden_substitutions": (
            "node count alias",
            "token count",
            "text length",
            "single undifferentiated depth",
        ),
        "claim_boundary": ("separate Program and public critical-reasoning measurements"),
    },
    {
        "name": "QATaskAndReasoningCoverageMatrixContract",
        "scientific_object": "QATaskAndReasoningCoverageMatrixV1",
        "model_class": "QATaskAndReasoningCoverageMatrixV1",
        "invariants": (
            "eight coverage axes remain explicit",
            "first future fixture layer contains four distinct archetypes",
            "a frozen matrix is not a measured coverage result",
        ),
        "forbidden_substitutions": (
            "task-count proxy",
            "maximum-depth proxy",
            "Benchmark-frequency claim",
        ),
        "claim_boundary": "future experimental design only; no coverage estimate",
    },
)


def _candidate_model_fields(root: Path) -> dict[str, tuple[str, ...]]:
    path = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "qa_reasoning_contract_freeze/models.py"
    )
    source = _git(
        root,
        "contracts.source_fields",
        "show",
        f"{models.CANDIDATE_SOURCE_COMMIT}:{path}",
    )
    tree = ast.parse(source)
    fields: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            fields[node.name] = tuple(
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            )
    return fields


def reconstruct_contracts(
    root: Path,
    authorization_id: str,
    saved: Mapping[str, bytes],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    fields = _candidate_model_fields(root)
    descriptors = []
    for spec in CONTRACT_SPECS:
        model_class = str(spec["model_class"])
        required_fields = fields.get(model_class)
        if not required_fields:
            _fail("contracts.source_fields", f"source model fields absent: {model_class}")
        descriptors.append(
            _identified(
                {
                    "name": spec["name"],
                    "version": "1.0.0",
                    "scientific_object": spec["scientific_object"],
                    "required_fields": required_fields,
                    "invariants": spec["invariants"],
                    "forbidden_substitutions": spec["forbidden_substitutions"],
                    "claim_boundary": spec["claim_boundary"],
                    "schema_version": "finance_qa_reasoning_contract_descriptor.v1",
                },
                "contract_id",
                "finance_qa_reasoning_contract_descriptor:",
            )
        )
    rebuilt = tuple(descriptors)
    candidate = _jsonl(saved["contract_descriptors.jsonl"])
    matches = sum(
        _encoded(left) == _encoded(right) for left, right in zip(rebuilt, candidate, strict=True)
    )
    if (
        tuple(row["name"] for row in rebuilt) != models.CONTRACT_NAMES
        or len(candidate) != 10
        or matches != 10
    ):
        _fail("contracts.candidate_bytes", "independent Contract descriptors differ")
    audit = _identified(
        {
            "authorization_id": authorization_id,
            "candidate_source_commit": models.CANDIDATE_SOURCE_COMMIT,
            "contract_names": models.CONTRACT_NAMES,
            "contract_ids": tuple(row["contract_id"] for row in rebuilt),
            "source_model_classes": tuple(str(row["model_class"]) for row in CONTRACT_SPECS),
            "source_fields_derived_with_ast": True,
            "independently_reconstructed_count": len(rebuilt),
            "candidate_actual_byte_matches": matches,
            "candidate_contract_helper_calls": 0,
            "candidate_conformance_audit_used_as_input": False,
            "passed": True,
            "schema_version": "finance_qa_reasoning_contract_reconstruction_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_reconstruction_audit:",
    )
    return rebuilt, audit


def build_target_contract() -> dict[str, Any]:
    return _identified(
        {
            "allowed_modalities": ("management_target", "company_guidance"),
            "forbidden_modalities": (
                "observed_actual",
                "analyst_consensus",
                "peer_benchmark",
                "arbitrary_constant",
                "derived_margin",
            ),
            "required_fields": (
                "metric_definition_id",
                "target_modality",
                "source_authority",
                "issuer_or_author",
                "statement_as_of",
                "effective_period",
                "entity_scope",
                "unit",
                "gaap_or_non_gaap_basis",
                "exact_text_or_table_locator",
                "source_document_id",
            ),
            "same_entity_period_required": True,
            "schema_version": "target_evidence_authority_contract.v1",
        },
        "contract_id",
        "target_evidence_authority_contract:",
    )


def build_coverage_matrix() -> dict[str, Any]:
    axes = {
        "task_family": (
            "retrieval",
            "ratio",
            "comparison",
            "selection",
            "ranking",
            "reconciliation",
            "target_gap",
            "conflict_or_insufficiency",
        ),
        "program_topology": (
            "single",
            "serial",
            "branch_and_merge",
            "select_then_lookup",
            "correction",
        ),
        "evidence_modality": ("table_cell", "narrative_statement", "cross_document"),
        "temporal_structure": ("single_period", "paired_period", "multi_period"),
        "entity_structure": ("single_entity", "cross_entity"),
        "reasoning_obligation": (
            "definition_alignment",
            "period_alignment",
            "operation_choice",
            "evidence_sufficiency",
            "conflict_resolution",
        ),
        "answer_shape": ("scalar", "comparison", "ranking", "structured_explanation"),
        "trajectory_structure": (
            "direct",
            "alternative_valid_path",
            "correction",
            "abstention",
        ),
    }
    cells = (
        {
            "cell_id": "future:serial_derivation",
            "archetype": "serial_derivation",
            "task_family": "ratio_and_period_change",
            "program_topology": "serial",
            "evidence_modality": "table_cell",
            "temporal_structure": "paired_period",
            "entity_structure": "single_entity",
            "reasoning_obligation": "period_and_definition_alignment",
            "answer_shape": "scalar",
            "trajectory_structure": "alternative_valid_path",
            "future_fixture_only": True,
        },
        {
            "cell_id": "future:branch_and_merge",
            "archetype": "branch_and_merge",
            "task_family": "comparison",
            "program_topology": "branch_and_merge",
            "evidence_modality": "table_cell",
            "temporal_structure": "paired_period",
            "entity_structure": "single_entity",
            "reasoning_obligation": "branch_selection_and_merge",
            "answer_shape": "scalar",
            "trajectory_structure": "alternative_valid_path",
            "future_fixture_only": True,
        },
        {
            "cell_id": "future:select_then_lookup",
            "archetype": "select_then_lookup",
            "task_family": "selection",
            "program_topology": "select_then_lookup",
            "evidence_modality": "table_cell",
            "temporal_structure": "multi_period",
            "entity_structure": "single_entity",
            "reasoning_obligation": "operation_choice_and_secondary_lookup",
            "answer_shape": "structured_explanation",
            "trajectory_structure": "direct",
            "future_fixture_only": True,
        },
        {
            "cell_id": "future:evidence_insufficiency_or_correction",
            "archetype": "evidence_insufficiency_or_correction",
            "task_family": "conflict_or_insufficiency",
            "program_topology": "correction",
            "evidence_modality": "narrative_statement",
            "temporal_structure": "single_period",
            "entity_structure": "single_entity",
            "reasoning_obligation": "evidence_sufficiency",
            "answer_shape": "structured_explanation",
            "trajectory_structure": "abstention_or_correction",
            "future_fixture_only": True,
        },
    )
    return _identified(
        {
            "axis_values": axes,
            "minimum_constructive_cells": cells,
            "coverage_measured": False,
            "benchmark_frequency_claimed": False,
            "schema_version": "qa_task_and_reasoning_coverage_matrix.v1",
        },
        "matrix_id",
        "qa_task_and_reasoning_coverage_matrix:",
    )


def build_scientific_objects() -> dict[str, dict[str, Any]]:
    task_id = "fixture:contract_conformance_task"
    oracle = _identified(
        {
            "task_instance_id": task_id,
            "evidence_binding_id": "evidence_binding:contract_fixture",
            "canonical_semantic_plan_id": "semantic_plan:contract_fixture",
            "expected_answer_schema": {"type": "scalar", "required": ("value", "unit")},
            "recompute_contract_id": "recompute:exact_decimal.v1",
            "citation_contract_id": "citation:complete_selected_evidence.v1",
            "tolerance_and_rounding_contract": {
                "mode": "exact_decimal",
                "tolerance": "0",
            },
            "is_answer_correctness_oracle_only": True,
            "prescribes_unique_reasoning_path": False,
            "schema_version": "answer_oracle_program_binding.v1",
        },
        "binding_id",
        "answer_oracle_program_binding:",
    )
    obligation = {
        "decision_id": "decision:align_period_and_definition",
        "trigger_state_predicate": "evidence_available_and_alignment_unverified",
        "subgoal": "verify period and metric-definition comparability before calculation",
        "unresolved_uncertainty_type": "period_and_definition_alignment",
        "required_evidence_roles": ("metric_earlier", "metric_later"),
        "admissible_action_classes": ("verify_public_evidence_alignment",),
        "admissible_alternative_action_ids": (
            "action:verify_alignment_primary",
            "action:verify_alignment_alternative",
        ),
        "forbidden_shortcut_classes": (
            "calculate_before_alignment",
            "future_evidence_reference",
        ),
        "produced_claim_schema": {
            "type": "comparability_claim",
            "required": ("comparable",),
        },
        "downstream_claim_dependencies": (),
        "required": True,
        "counterfactual_intervention_ids": (
            "intervention:swap_period",
            "intervention:change_metric_definition",
        ),
    }
    graph = _identified(
        {
            "task_instance_id": task_id,
            "answer_oracle_program_binding_id": oracle["binding_id"],
            "obligations": (obligation,),
            "allows_multiple_valid_orders": True,
            "language_realization_is_authority": False,
            "schema_version": "critical_decision_graph.v1",
        },
        "graph_id",
        "critical_decision_graph:",
    )
    state0 = _identified(
        {
            "task_instance_id": task_id,
            "sequence_index": 0,
            "available_evidence_refs": ("evidence:earlier", "evidence:later"),
            "verified_claim_refs": (),
            "current_subgoal": obligation["subgoal"],
            "remaining_uncertainties": (obligation["unresolved_uncertainty_type"],),
            "available_action_ids": obligation["admissible_alternative_action_ids"],
            "completed_action_refs": (),
            "observation_refs": (),
            "private_reasoning_content_present": False,
            "schema_version": "public_reasoning_state.v1",
        },
        "state_id",
        "public_reasoning_state:",
    )
    envelope = _identified(
        {
            "task_instance_id": task_id,
            "state_id": state0["state_id"],
            "decision_graph_id": graph["graph_id"],
            "decision_id": obligation["decision_id"],
            "subgoal": obligation["subgoal"],
            "evidence_refs": state0["available_evidence_refs"],
            "claim_refs": (),
            "unresolved_uncertainty": obligation["unresolved_uncertainty_type"],
            "candidate_action_ids": state0["available_action_ids"],
            "selected_action_id": "action:verify_alignment_primary",
            "decision_basis": (
                {
                    "relation": "requires",
                    "subject_ref": "claim:period_and_definition_comparable",
                    "evidence_refs": state0["available_evidence_refs"],
                    "claim_refs": (),
                },
            ),
            "expected_effect": "produce a public comparability Claim",
            "action": {
                "state_id": state0["state_id"],
                "action_id": "action:verify_alignment_primary",
                "decision_kind": "verify_public_evidence_alignment",
                "protocol": "finance_reasoning_action.v1",
            },
            "preaction_commit_sequence": 0,
            "protocol": "finance_public_critical_reasoning.v1",
            "private_chain_of_thought_present": False,
            "schema_version": "reasoning_action_envelope.v1",
        },
        "envelope_id",
        "reasoning_action_envelope:",
    )
    execution = _identified(
        {
            "task_instance_id": task_id,
            "parent_envelope_id": envelope["envelope_id"],
            "state_id": state0["state_id"],
            "action_id": envelope["selected_action_id"],
            "execution_sequence": 1,
            "succeeded": True,
            "public_result_hash": hashlib.sha256(b"comparable:true").hexdigest(),
            "schema_version": "reasoning_action_execution.v1",
        },
        "execution_id",
        "reasoning_action_execution:",
    )
    public_payload = {"comparable": True, "mismatches": ()}
    observation = _identified(
        {
            "task_instance_id": task_id,
            "parent_execution_id": execution["execution_id"],
            "state_id": state0["state_id"],
            "observation_sequence": 1,
            "public_payload": public_payload,
            "public_payload_hash": hashlib.sha256(canonical_json_bytes(public_payload)).hexdigest(),
            "schema_version": "public_reasoning_observation.v1",
        },
        "observation_id",
        "public_reasoning_observation:",
    )
    claim = {
        "claim_id": "claim:period_and_definition_comparable",
        "disposition": "accepted",
        "support_observation_refs": (observation["observation_id"],),
        "public_claim": {"comparable": True},
    }
    state1 = _identified(
        {
            "task_instance_id": task_id,
            "sequence_index": 1,
            "available_evidence_refs": state0["available_evidence_refs"],
            "verified_claim_refs": (claim["claim_id"],),
            "current_subgoal": "proceed to the answer Operation",
            "remaining_uncertainties": (),
            "available_action_ids": ("action:execute_answer_operation",),
            "completed_action_refs": (execution["execution_id"],),
            "observation_refs": (observation["observation_id"],),
            "private_reasoning_content_present": False,
            "schema_version": "public_reasoning_state.v1",
        },
        "state_id",
        "public_reasoning_state:",
    )
    update = _identified(
        {
            "task_instance_id": task_id,
            "parent_reasoning_action_id": envelope["envelope_id"],
            "action_execution_id": execution["execution_id"],
            "observation_id": observation["observation_id"],
            "accepted_claims": (claim,),
            "rejected_or_revised_claims": (),
            "remaining_uncertainties": (),
            "newly_enabled_actions": state1["available_action_ids"],
            "next_subgoal": state1["current_subgoal"],
            "next_state_id": state1["state_id"],
            "update_sequence": 1,
            "schema_version": "observation_update.v1",
        },
        "update_id",
        "observation_update:",
    )
    trajectory = _identified(
        {
            "task_instance_id": task_id,
            "initial_state_id": state0["state_id"],
            "ordered_reasoning_action_ids": (envelope["envelope_id"],),
            "ordered_action_execution_ids": (execution["execution_id"],),
            "ordered_observation_ids": (observation["observation_id"],),
            "ordered_observation_update_ids": (update["update_id"],),
            "final_claim_refs": (claim["claim_id"],),
            "final_answer_ref": "answer:contract_fixture",
            "critical_decision_graph_id": graph["graph_id"],
            "answer_oracle_program_binding_id": oracle["binding_id"],
            "covered_decision_ids": (obligation["decision_id"],),
            "wording_fingerprint": "wording:fixture-a",
            "schema_version": "reasoning_trajectory.v1",
        },
        "trajectory_id",
        "reasoning_trajectory:",
    )
    answer = _identified(
        {
            "task_instance_id": task_id,
            "source_valid": True,
            "answer_valid": True,
            "citation_valid": True,
            "qa_valid": True,
            "schema_version": "answer_validity_report.v1",
        },
        "report_id",
        "answer_validity_report:",
    )
    trajectory_validity = _identified(
        {
            "trajectory_id": trajectory["trajectory_id"],
            "preaction_valid": True,
            "grounding_valid": True,
            "reasoning_action_valid": True,
            "observation_update_valid": True,
            "critical_coverage_valid": True,
            "trajectory_valid": True,
            "schema_version": "reasoning_trajectory_validity_report.v1",
        },
        "report_id",
        "reasoning_trajectory_validity_report:",
    )
    qualification = _identified(
        {
            "task_instance_id": task_id,
            "trajectory_id": trajectory["trajectory_id"],
            "answer_validity_report_id": answer["report_id"],
            "trajectory_validity_report_id": trajectory_validity["report_id"],
            "qa_valid": answer["qa_valid"],
            "trajectory_valid": trajectory_validity["trajectory_valid"],
            "qualified": True,
            "schema_version": "qualified_reasoning_trajectory.v1",
        },
        "qualification_id",
        "qualified_reasoning_trajectory:",
    )
    depth = _identified(
        {
            "task_instance_id": task_id,
            "trajectory_id": trajectory["trajectory_id"],
            "semantic_operation_depth": 3,
            "reasoning_depth": 1,
            "evidence_integration_depth": 2,
            "correction_depth": 0,
            "required_decision_count": 1,
            "covered_required_decision_count": 1,
            "critical_decision_coverage": 1.0,
            "metrics_noninterchangeable": True,
            "token_count_used_as_depth": False,
            "text_length_used_as_depth": False,
            "schema_version": "reasoning_depth_metrics.v1",
        },
        "metrics_id",
        "reasoning_depth_metrics:",
    )
    return {
        "answer_oracle_binding": oracle,
        "critical_decision_graph": graph,
        "initial_state": state0,
        "reasoning_action": envelope,
        "action_execution": execution,
        "observation": observation,
        "observation_update": update,
        "next_state": state1,
        "reasoning_trajectory": trajectory,
        "answer_validity": answer,
        "trajectory_validity": trajectory_validity,
        "qualification": qualification,
        "depth_metrics": depth,
    }


OBJECT_PATHS: dict[str, str] = {
    "answer_oracle_binding": "answer_oracle_program_binding.json",
    "critical_decision_graph": "critical_decision_graph.json",
    "initial_state": "initial_public_reasoning_state.json",
    "reasoning_action": "reasoning_action_envelope.json",
    "action_execution": "action_execution.json",
    "observation": "public_observation.json",
    "observation_update": "observation_update.json",
    "next_state": "next_public_reasoning_state.json",
    "reasoning_trajectory": "reasoning_trajectory.json",
    "answer_validity": "answer_validity_report.json",
    "trajectory_validity": "trajectory_validity_report.json",
    "qualification": "qualified_reasoning_trajectory.json",
    "depth_metrics": "depth_metrics.json",
}

OBJECT_ID_FIELDS: dict[str, str] = {
    "answer_oracle_binding": "binding_id",
    "critical_decision_graph": "graph_id",
    "initial_state": "state_id",
    "reasoning_action": "envelope_id",
    "action_execution": "execution_id",
    "observation": "observation_id",
    "observation_update": "update_id",
    "next_state": "state_id",
    "reasoning_trajectory": "trajectory_id",
    "answer_validity": "report_id",
    "trajectory_validity": "report_id",
    "qualification": "qualification_id",
    "depth_metrics": "metrics_id",
}


def compare_scientific_objects(
    authorization_id: str,
    objects: Mapping[str, dict[str, Any]],
    saved: Mapping[str, bytes],
) -> dict[str, Any]:
    if tuple(objects) != models.OBJECT_NAMES:
        _fail("objects.denominator", "scientific object denominator differs")
    rows = []
    for name in models.OBJECT_NAMES:
        path = OBJECT_PATHS[name]
        value = objects[name]
        matches = _encoded(value) == saved[path]
        if not matches:
            _fail("objects.candidate_bytes", f"scientific object differs: {name}")
        field = OBJECT_ID_FIELDS[name]
        rows.append(
            {
                "object_name": name,
                "candidate_path": path,
                "object_id": value[field],
                "payload_sha256": _sha(_encoded(value)),
                "byte_count": len(_encoded(value)),
                "candidate_actual_bytes_match": matches,
            }
        )
    return _identified(
        {
            "authorization_id": authorization_id,
            "rows": tuple(rows),
            "declared_object_names": models.OBJECT_NAMES,
            "independently_reconstructed_count": len(rows),
            "candidate_actual_byte_matches": len(rows),
            "primitive_synthetic_input_sets": 1,
            "candidate_object_builder_calls": 0,
            "candidate_conformance_audit_used_as_input": False,
            "passed": True,
            "schema_version": "finance_qa_reasoning_object_reconstruction_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_object_reconstruction_audit:",
    )
