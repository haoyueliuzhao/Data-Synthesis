from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from . import models
from .audit import (
    IndependentAuditError,
    _encoded,
    _fail,
    _identified,
    _load,
    _require_identity,
    _sha,
)

IDENTITIES: dict[str, tuple[str, str]] = {
    "answer_oracle_binding": ("binding_id", "answer_oracle_program_binding:"),
    "critical_decision_graph": ("graph_id", "critical_decision_graph:"),
    "initial_state": ("state_id", "public_reasoning_state:"),
    "reasoning_action": ("envelope_id", "reasoning_action_envelope:"),
    "action_execution": ("execution_id", "reasoning_action_execution:"),
    "observation": ("observation_id", "public_reasoning_observation:"),
    "observation_update": ("update_id", "observation_update:"),
    "next_state": ("state_id", "public_reasoning_state:"),
    "reasoning_trajectory": ("trajectory_id", "reasoning_trajectory:"),
    "answer_validity": ("report_id", "answer_validity_report:"),
    "trajectory_validity": (
        "report_id",
        "reasoning_trajectory_validity_report:",
    ),
    "qualification": ("qualification_id", "qualified_reasoning_trajectory:"),
    "depth_metrics": ("metrics_id", "reasoning_depth_metrics:"),
}


def _rehash(value: Mapping[str, Any], field: str, prefix: str, **updates: Any) -> dict[str, Any]:
    changed = copy.deepcopy(dict(value))
    changed.update(updates)
    changed.pop(field, None)
    return _identified(changed, field, prefix)


def _validate_graph(graph: Mapping[str, Any]) -> None:
    obligations = graph.get("obligations")
    if not isinstance(obligations, (list, tuple)) or not obligations:
        _fail("model.validation", "Critical Decision Graph has no obligation")
    identifiers = tuple(str(row.get("decision_id")) for row in obligations)
    if len(identifiers) != len(set(identifiers)):
        _fail("model.validation", "Critical Decision Graph repeats an obligation")
    for index, row in enumerate(obligations):
        dependencies = set(row.get("downstream_claim_dependencies", ()))
        if not dependencies <= set(identifiers[:index]):
            _fail("model.validation", "decision dependency is not topological")
        if row.get("required") and not row.get("counterfactual_intervention_ids"):
            _fail("model.validation", "required decision lacks direct intervention")


def _validate_envelope_shape(envelope: Mapping[str, Any]) -> None:
    action = envelope.get("action")
    if not isinstance(action, dict):
        _fail("model.validation", "Reasoning Action inner Action is absent")
    if not envelope.get("evidence_refs") or not envelope.get("decision_basis"):
        _fail("model.validation", "Reasoning Action has no grounded decision basis")
    if (
        envelope.get("selected_action_id") not in envelope.get("candidate_action_ids", ())
        or action.get("action_id") != envelope.get("selected_action_id")
        or action.get("state_id") != envelope.get("state_id")
        or envelope.get("private_chain_of_thought_present") is not False
    ):
        _fail("model.validation", "Reasoning Action shape differs")
    for edge in envelope.get("decision_basis", ()):
        if not edge.get("evidence_refs") and not edge.get("claim_refs"):
            _fail("model.validation", "decision basis has no visible reference")


def _validate_update_shape(update: Mapping[str, Any]) -> None:
    claims = tuple(update.get("accepted_claims", ())) + tuple(
        update.get("rejected_or_revised_claims", ())
    )
    if not claims or any(
        update.get("observation_id") not in claim.get("support_observation_refs", ())
        for claim in claims
    ):
        _fail("model.validation", "Claim Update is not bound to its Observation")


def _validate_object_shapes(objects: Mapping[str, Mapping[str, Any]]) -> None:
    for name, value in objects.items():
        field, prefix = IDENTITIES[name]
        _require_identity(value, field, prefix, "objects.identity")
    graph = objects["critical_decision_graph"]
    _validate_graph(graph)
    for state_name in ("initial_state", "next_state"):
        state = objects[state_name]
        domains = (
            state.get("available_evidence_refs", ()),
            state.get("verified_claim_refs", ()),
            state.get("available_action_ids", ()),
            state.get("completed_action_refs", ()),
            state.get("observation_refs", ()),
        )
        if (
            any(len(values) != len(set(values)) for values in domains)
            or state.get("private_reasoning_content_present") is not False
        ):
            _fail("model.validation", "Public Reasoning State domain differs")
    _validate_envelope_shape(objects["reasoning_action"])
    observation = objects["observation"]
    if (
        observation.get("public_payload_hash")
        != hashlib.sha256(canonical_json_bytes(observation.get("public_payload"))).hexdigest()
    ):
        _fail("model.validation", "Public Observation payload hash differs")
    _validate_update_shape(objects["observation_update"])
    trajectory = objects["reasoning_trajectory"]
    lengths = {
        len(trajectory.get("ordered_reasoning_action_ids", ())),
        len(trajectory.get("ordered_action_execution_ids", ())),
        len(trajectory.get("ordered_observation_ids", ())),
        len(trajectory.get("ordered_observation_update_ids", ())),
    }
    if len(lengths) != 1:
        _fail("model.validation", "Reasoning Trajectory chain cardinality differs")
    answer = objects["answer_validity"]
    if answer.get("qa_valid") != all(
        bool(answer.get(field)) for field in ("source_valid", "answer_valid", "citation_valid")
    ):
        _fail("model.validation", "QA validity is not a conjunction")
    validity = objects["trajectory_validity"]
    if validity.get("trajectory_valid") != all(
        bool(validity.get(field))
        for field in (
            "preaction_valid",
            "grounding_valid",
            "reasoning_action_valid",
            "observation_update_valid",
            "critical_coverage_valid",
        )
    ):
        _fail("model.validation", "trajectory validity is not a conjunction")
    qualification = objects["qualification"]
    if qualification.get("qualified") != (
        qualification.get("qa_valid") and qualification.get("trajectory_valid")
    ):
        _fail("model.validation", "qualification is not a conjunction")


def _validate_reasoning_action(
    envelope: Mapping[str, Any],
    state: Mapping[str, Any],
    graph: Mapping[str, Any],
    execution: Mapping[str, Any] | None = None,
) -> None:
    obligations = {str(row["decision_id"]): row for row in graph.get("obligations", ())}
    obligation = obligations.get(str(envelope.get("decision_id")))
    if (
        envelope.get("task_instance_id") != state.get("task_instance_id")
        or graph.get("task_instance_id") != state.get("task_instance_id")
        or envelope.get("state_id") != state.get("state_id")
    ):
        _fail("reasoning.state_binding", "Reasoning Action crosses State authority")
    if obligation is None:
        _fail("reasoning.decision_obligation", "Reasoning Action has no obligation")
    if not set(envelope.get("evidence_refs", ())) <= set(
        state.get("available_evidence_refs", ())
    ) or not set(envelope.get("claim_refs", ())) <= set(state.get("verified_claim_refs", ())):
        _fail("reasoning.visible_refs", "Reasoning Action uses unavailable reference")
    if (
        envelope.get("subgoal") != obligation.get("subgoal")
        or envelope.get("unresolved_uncertainty") != obligation.get("unresolved_uncertainty_type")
        or envelope.get("selected_action_id") not in state.get("available_action_ids", ())
        or envelope.get("selected_action_id")
        not in obligation.get("admissible_alternative_action_ids", ())
    ):
        _fail("reasoning.decision_alignment", "Reasoning Action differs from obligation")
    if execution is not None:
        if int(envelope.get("preaction_commit_sequence", -1)) >= int(
            execution.get("execution_sequence", -1)
        ):
            _fail("reasoning.preaction_commit", "reasoning is not pre-action")
        if (
            execution.get("parent_envelope_id") != envelope.get("envelope_id")
            or execution.get("state_id") != envelope.get("state_id")
            or execution.get("action_id") != envelope.get("selected_action_id")
        ):
            _fail("reasoning.action_consistency", "selected and executed Actions differ")


def _validate_observation_update(
    update: Mapping[str, Any],
    envelope: Mapping[str, Any],
    execution: Mapping[str, Any],
    observation: Mapping[str, Any],
    next_state: Mapping[str, Any],
) -> None:
    if (
        update.get("task_instance_id") != envelope.get("task_instance_id")
        or update.get("parent_reasoning_action_id") != envelope.get("envelope_id")
        or update.get("action_execution_id") != execution.get("execution_id")
        or update.get("observation_id") != observation.get("observation_id")
        or observation.get("parent_execution_id") != execution.get("execution_id")
        or update.get("next_state_id") != next_state.get("state_id")
        or update.get("update_sequence") != observation.get("observation_sequence")
        or next_state.get("sequence_index") != update.get("update_sequence")
    ):
        _fail("reasoning.observation_update", "Observation Update lineage differs")
    accepted = {str(row["claim_id"]) for row in update.get("accepted_claims", ())}
    if not accepted <= set(next_state.get("verified_claim_refs", ())):
        _fail("reasoning.claim_update", "accepted Claim is absent from next State")


def _validate_trajectory(
    trajectory: Mapping[str, Any],
    graph: Mapping[str, Any],
    envelope: Mapping[str, Any],
    execution: Mapping[str, Any],
    observation: Mapping[str, Any],
    update: Mapping[str, Any],
) -> None:
    if (
        trajectory.get("task_instance_id") != graph.get("task_instance_id")
        or trajectory.get("critical_decision_graph_id") != graph.get("graph_id")
        or tuple(trajectory.get("ordered_reasoning_action_ids", ()))
        != (envelope.get("envelope_id"),)
        or tuple(trajectory.get("ordered_action_execution_ids", ()))
        != (execution.get("execution_id"),)
        or tuple(trajectory.get("ordered_observation_ids", ()))
        != (observation.get("observation_id"),)
        or tuple(trajectory.get("ordered_observation_update_ids", ())) != (update.get("update_id"),)
    ):
        _fail("reasoning.trajectory_lineage", "Reasoning Trajectory lineage differs")
    required = {
        str(row["decision_id"]) for row in graph.get("obligations", ()) if row.get("required")
    }
    if not required <= set(trajectory.get("covered_decision_ids", ())):
        _fail("reasoning.critical_coverage", "required decision is missing")


def _validate_qualification(
    qualification: Mapping[str, Any],
    answer: Mapping[str, Any],
    trajectory_validity: Mapping[str, Any],
) -> None:
    if (
        qualification.get("answer_validity_report_id") != answer.get("report_id")
        or qualification.get("trajectory_validity_report_id")
        != trajectory_validity.get("report_id")
        or qualification.get("qa_valid") != answer.get("qa_valid")
        or qualification.get("trajectory_valid") != trajectory_validity.get("trajectory_valid")
        or qualification.get("qualified") is not True
    ):
        _fail("reasoning.qualification", "QA and trajectory validity do not qualify")


def _validate_target(candidate: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    if candidate.get("target_modality") not in contract.get("allowed_modalities", ()):
        _fail("target.modality", "target Evidence modality is not authorized")
    if any(not candidate.get(field) for field in contract.get("required_fields", ())):
        _fail("target.required_fields", "target Evidence authority field is absent")


def _quotient_signature(trajectory: Mapping[str, Any]) -> str:
    return strict_canonical_hash(
        {
            "task_instance_id": trajectory.get("task_instance_id"),
            "critical_decision_graph_id": trajectory.get("critical_decision_graph_id"),
            "covered_decision_ids": trajectory.get("covered_decision_ids"),
            "reasoning_action_count": len(trajectory.get("ordered_reasoning_action_ids", ())),
            "action_execution_count": len(trajectory.get("ordered_action_execution_ids", ())),
            "observation_update_count": len(trajectory.get("ordered_observation_update_ids", ())),
            "final_claim_refs": trajectory.get("final_claim_refs"),
            "termination_mode": "final_answer",
        },
        prefix="reasoning_trajectory_quotient_state:",
    )


def build_parent_relation_audit(
    authorization_id: str,
    object_audit_id: str,
    objects: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    _validate_object_shapes(objects)
    envelope = objects["reasoning_action"]
    execution = objects["action_execution"]
    observation = objects["observation"]
    update = objects["observation_update"]
    _validate_reasoning_action(
        envelope,
        objects["initial_state"],
        objects["critical_decision_graph"],
        execution,
    )
    _validate_observation_update(update, envelope, execution, observation, objects["next_state"])
    _validate_trajectory(
        objects["reasoning_trajectory"],
        objects["critical_decision_graph"],
        envelope,
        execution,
        observation,
        update,
    )
    _validate_qualification(
        objects["qualification"],
        objects["answer_validity"],
        objects["trajectory_validity"],
    )
    return _identified(
        {
            "authorization_id": authorization_id,
            "object_reconstruction_audit_id": object_audit_id,
            "parent_order": (
                "public_reasoning_state",
                "reasoning_action_envelope",
                "action_execution",
                "public_observation",
                "observation_update",
                "next_public_reasoning_state",
            ),
            "state_to_envelope": True,
            "envelope_precedes_execution": True,
            "execution_to_observation": True,
            "observation_to_update": True,
            "update_to_next_state": True,
            "trajectory_lineage_exact": True,
            "required_decisions_covered": True,
            "private_chain_of_thought_fields": 0,
            "durable_runtime_commit_claimed": False,
            "candidate_admission_helper_calls": 0,
            "passed": True,
            "schema_version": "finance_qa_reasoning_parent_relation_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_parent_relation_audit:",
    )


def _decision_depth(obligations: Sequence[Mapping[str, Any]]) -> int:
    depths: dict[str, int] = {}
    for obligation in obligations:
        identifier = str(obligation["decision_id"])
        dependencies = tuple(obligation.get("downstream_claim_dependencies", ()))
        depths[identifier] = 1 + max((depths[str(parent)] for parent in dependencies), default=0)
    return max(depths.values(), default=0)


def build_semantic_derivation_audit(
    authorization_id: str,
    parent_audit_id: str,
    objects: Mapping[str, dict[str, Any]],
    target_contract: Mapping[str, Any],
    coverage_matrix: Mapping[str, Any],
    saved: Mapping[str, bytes],
) -> dict[str, Any]:
    answer = objects["answer_validity"]
    trajectory_validity = objects["trajectory_validity"]
    qualification = objects["qualification"]
    qa_valid = all(
        bool(answer[field]) for field in ("source_valid", "answer_valid", "citation_valid")
    )
    trajectory_valid = all(
        bool(trajectory_validity[field])
        for field in (
            "preaction_valid",
            "grounding_valid",
            "reasoning_action_valid",
            "observation_update_valid",
            "critical_coverage_valid",
        )
    )
    qualified = qa_valid and trajectory_valid
    if (
        qa_valid != answer["qa_valid"]
        or trajectory_valid != trajectory_validity["trajectory_valid"]
        or qualified != qualification["qualified"]
    ):
        _fail("derivation.validity", "noncompensatory validity differs")
    allowed = tuple(target_contract["allowed_modalities"])
    forbidden = tuple(target_contract["forbidden_modalities"])
    if (
        set(allowed) != {"management_target", "company_guidance"}
        or set(allowed) & set(forbidden)
        or set(forbidden)
        != {
            "observed_actual",
            "analyst_consensus",
            "peer_benchmark",
            "arbitrary_constant",
            "derived_margin",
        }
    ):
        _fail("derivation.target", "target modality partition differs")
    graph = objects["critical_decision_graph"]
    trajectory = objects["reasoning_trajectory"]
    update = objects["observation_update"]
    required = {str(row["decision_id"]) for row in graph["obligations"] if row["required"]}
    covered = required & set(trajectory["covered_decision_ids"])
    derived_metrics = {
        "semantic_operation_depth": 3,
        "reasoning_depth": _decision_depth(graph["obligations"]),
        "evidence_integration_depth": len(set(objects["reasoning_action"]["evidence_refs"])),
        "correction_depth": len(update["rejected_or_revised_claims"]),
        "required_decision_count": len(required),
        "covered_required_decision_count": len(covered),
        "critical_decision_coverage": len(covered) / len(required),
    }
    depth = objects["depth_metrics"]
    if any(depth[key] != value for key, value in derived_metrics.items()):
        _fail("derivation.depth", "independently derived depth metric differs")
    expected_axes = {
        "task_family",
        "program_topology",
        "evidence_modality",
        "temporal_structure",
        "entity_structure",
        "reasoning_obligation",
        "answer_shape",
        "trajectory_structure",
    }
    archetypes = {str(row["archetype"]) for row in coverage_matrix["minimum_constructive_cells"]}
    if (
        set(coverage_matrix["axis_values"]) != expected_axes
        or archetypes
        != {
            "serial_derivation",
            "branch_and_merge",
            "select_then_lookup",
            "evidence_insufficiency_or_correction",
        }
        or coverage_matrix["coverage_measured"] is not False
        or coverage_matrix["benchmark_frequency_claimed"] is not False
    ):
        _fail("derivation.coverage", "coverage design matrix differs")
    target_match = _encoded(target_contract) == saved["target_evidence_authority_contract.json"]
    matrix_match = _encoded(coverage_matrix) == saved["coverage_matrix.json"]
    if not target_match or not matrix_match:
        _fail("derivation.candidate_bytes", "target or coverage candidate bytes differ")
    return _identified(
        {
            "authorization_id": authorization_id,
            "parent_relation_audit_id": parent_audit_id,
            "qa_validity_formula": "source_valid AND answer_valid AND citation_valid",
            "trajectory_validity_formula": (
                "preaction_valid AND grounding_valid AND reasoning_action_valid AND "
                "observation_update_valid AND critical_coverage_valid"
            ),
            "qualification_formula": "qa_valid AND trajectory_valid",
            "qa_valid": qa_valid,
            "trajectory_valid": trajectory_valid,
            "qualified": qualified,
            "target_allowed_modalities": allowed,
            "target_forbidden_modalities": forbidden,
            "target_contract_candidate_bytes_match": target_match,
            "derived_depth_metrics": derived_metrics,
            "semantic_operation_depth_source": (
                "declared_synthetic_answer_program_conformance_primitive"
            ),
            "semantic_operation_depth_used_as_reasoning_depth": False,
            "token_or_text_measure_used_as_depth": False,
            "coverage_axis_count": len(expected_axes),
            "coverage_archetype_count": len(archetypes),
            "coverage_measured": False,
            "benchmark_frequency_claimed": False,
            "coverage_matrix_candidate_bytes_match": matrix_match,
            "candidate_semantic_helper_calls": 0,
            "passed": True,
            "schema_version": "finance_qa_reasoning_semantic_derivation_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_semantic_derivation_audit:",
    )


def build_negative_control_audit(
    authorization_id: str,
    semantic_audit_id: str,
    objects: Mapping[str, dict[str, Any]],
    target_contract: Mapping[str, Any],
    saved: Mapping[str, bytes],
) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def reject(name: str, expected_stage: str, action: Callable[[], object]) -> None:
        caught: Exception | None = None
        try:
            action()
        except Exception as exc:
            caught = exc
        if not isinstance(caught, IndependentAuditError):
            _fail("negative.exception", f"independent attack did not reject: {name}")
        if caught.stage != expected_stage:
            _fail(
                "negative.stage",
                f"attack {name} rejected at {caught.stage}, expected {expected_stage}",
            )
        controls.append(
            {
                "name": name,
                "rejection_stage": caught.stage,
                "exception_type": type(caught).__name__,
                "reason_sha256": _sha(str(caught).encode("utf-8")),
                "candidate_object_rehashed": True,
                "rejected": True,
                "output_writes": 0,
                "provider_calls": 0,
            }
        )

    graph = objects["critical_decision_graph"]
    state = objects["initial_state"]
    envelope = objects["reasoning_action"]
    execution = objects["action_execution"]
    observation = objects["observation"]
    update = objects["observation_update"]
    trajectory = objects["reasoning_trajectory"]
    late = _rehash(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        preaction_commit_sequence=execution["execution_sequence"],
    )
    reject(
        models.ATTACK_NAMES[0],
        models.ATTACK_STAGES[0],
        lambda: _validate_reasoning_action(late, state, graph, execution),
    )
    generic = _rehash(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        evidence_refs=(),
        decision_basis=(),
    )
    reject(
        models.ATTACK_NAMES[1],
        models.ATTACK_STAGES[1],
        lambda: _validate_envelope_shape(generic),
    )
    crossed_action = copy.deepcopy(envelope["action"])
    crossed_action["state_id"] = "public_reasoning_state:crossed"
    crossed = _rehash(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        state_id="public_reasoning_state:crossed",
        action=crossed_action,
    )
    reject(
        models.ATTACK_NAMES[2],
        models.ATTACK_STAGES[2],
        lambda: _validate_reasoning_action(crossed, state, graph),
    )
    changed_execution = _rehash(
        execution,
        "execution_id",
        "reasoning_action_execution:",
        action_id="action:verify_alignment_alternative",
    )
    reject(
        models.ATTACK_NAMES[3],
        models.ATTACK_STAGES[3],
        lambda: _validate_reasoning_action(envelope, state, graph, changed_execution),
    )
    future = _rehash(
        envelope,
        "envelope_id",
        "reasoning_action_envelope:",
        evidence_refs=(*envelope["evidence_refs"], "evidence:future_observation"),
    )
    reject(
        models.ATTACK_NAMES[4],
        models.ATTACK_STAGES[4],
        lambda: _validate_reasoning_action(future, state, graph),
    )
    bad_claim = copy.deepcopy(update["accepted_claims"][0])
    bad_claim["support_observation_refs"] = ("observation:crossed",)
    bad_update = _rehash(
        update,
        "update_id",
        "observation_update:",
        accepted_claims=(bad_claim,),
    )
    reject(
        models.ATTACK_NAMES[5],
        models.ATTACK_STAGES[5],
        lambda: _validate_update_shape(bad_update),
    )
    actual = {
        "evidence_id": "evidence:observed_actual_margin",
        "task_instance_id": "fixture:target_gap",
        "metric_definition_id": "gross_margin.v1",
        "target_modality": "observed_actual",
        "source_authority": "issuer_filing",
        "issuer_or_author": "Example Issuer",
        "statement_as_of": "2026-01-01",
        "effective_period": "FY2026",
        "entity_scope": "Example Issuer consolidated",
        "unit": "percent",
        "gaap_or_non_gaap_basis": "GAAP",
        "exact_text_or_table_locator": "table:actual_margin:R2C3",
        "source_document_id": "document:example",
    }
    reject(
        models.ATTACK_NAMES[6],
        models.ATTACK_STAGES[6],
        lambda: _validate_target(actual, target_contract),
    )
    missing = _rehash(
        trajectory,
        "trajectory_id",
        "reasoning_trajectory:",
        covered_decision_ids=("decision:unrelated",),
    )
    reject(
        models.ATTACK_NAMES[7],
        models.ATTACK_STAGES[7],
        lambda: _validate_trajectory(missing, graph, envelope, execution, observation, update),
    )
    invalid_answer = _identified(
        {
            "task_instance_id": objects["answer_validity"]["task_instance_id"],
            "source_valid": True,
            "answer_valid": False,
            "citation_valid": False,
            "qa_valid": False,
            "schema_version": "answer_validity_report.v1",
        },
        "report_id",
        "answer_validity_report:",
    )
    nonqualified = _identified(
        {
            "task_instance_id": trajectory["task_instance_id"],
            "trajectory_id": trajectory["trajectory_id"],
            "answer_validity_report_id": invalid_answer["report_id"],
            "trajectory_validity_report_id": objects["trajectory_validity"]["report_id"],
            "qa_valid": False,
            "trajectory_valid": True,
            "qualified": False,
            "schema_version": "qualified_reasoning_trajectory.v1",
        },
        "qualification_id",
        "qualified_reasoning_trajectory:",
    )
    reject(
        models.ATTACK_NAMES[8],
        models.ATTACK_STAGES[8],
        lambda: _validate_qualification(
            nonqualified, invalid_answer, objects["trajectory_validity"]
        ),
    )
    paraphrase = _rehash(
        trajectory,
        "trajectory_id",
        "reasoning_trajectory:",
        wording_fingerprint="wording:fixture-b",
    )

    def require_distinct() -> None:
        if _quotient_signature(trajectory) == _quotient_signature(paraphrase):
            _fail("reasoning.quotient_state", "wording-only trajectories are one State")

    reject(models.ATTACK_NAMES[9], models.ATTACK_STAGES[9], require_distinct)
    if tuple(row["name"] for row in controls) != models.ATTACK_NAMES:
        _fail("negative.domain", "independent attack domain differs")
    candidate = _load(saved["negative_control_audit.json"])
    candidate_pairs = tuple(
        (str(row["name"]), str(row["rejection_stage"])) for row in candidate.get("controls", ())
    )
    independent_pairs = tuple((str(row["name"]), str(row["rejection_stage"])) for row in controls)
    if candidate_pairs != independent_pairs:
        _fail("negative.candidate_comparison", "candidate attack stage domain differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "semantic_derivation_audit_id": semantic_audit_id,
            "controls": tuple(controls),
            "attempted_count": len(controls),
            "rejected_count": len(controls),
            "accepted_count": 0,
            "candidate_name_and_stage_matches": len(controls),
            "candidate_reason_hashes_used_as_oracle": False,
            "candidate_attack_helper_calls": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "passed": True,
            "schema_version": "finance_qa_reasoning_independent_negative_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_independent_negative_audit:",
    )


def build_candidate_final_comparison(
    authorization_id: str,
    negative_audit_id: str,
    descriptors: Sequence[Mapping[str, Any]],
    objects: Mapping[str, dict[str, Any]],
    target_contract: Mapping[str, Any],
    coverage_matrix: Mapping[str, Any],
    saved: Mapping[str, bytes],
) -> dict[str, Any]:
    object_ids = {name: objects[name][IDENTITIES[name][0]] for name in models.OBJECT_NAMES}
    expected_conformance = _identified(
        {
            "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
            "source_binding_id": models.CANDIDATE_SOURCE_BINDING_ID,
            "contract_ids": tuple(row["contract_id"] for row in descriptors),
            "contract_count": len(descriptors),
            "contract_names": models.CONTRACT_NAMES,
            "scientific_object_ids": object_ids,
            "scientific_object_count": len(objects),
            "state_reasoning_action_execution_observation_update_state_chains": 1,
            "preaction_commits": 1,
            "post_action_reasoning_backfills": 0,
            "answer_oracle_prescribes_unique_reasoning_path": False,
            "private_chain_of_thought_fields": 0,
            "qa_and_trajectory_validity_separate": True,
            "qualification_noncompensatory": True,
            "target_allowed_modalities": target_contract["allowed_modalities"],
            "target_forbidden_modalities": target_contract["forbidden_modalities"],
            "depth_metric_names": (
                "semantic_operation_depth",
                "reasoning_depth",
                "evidence_integration_depth",
                "correction_depth",
                "critical_decision_coverage",
            ),
            "depth_metrics_noninterchangeable": True,
            "coverage_matrix_axis_count": len(coverage_matrix["axis_values"]),
            "future_minimum_fixture_archetype_count": len(
                coverage_matrix["minimum_constructive_cells"]
            ),
            "model_capability_measured": False,
            "schema_version": "finance_qa_reasoning_contract_conformance_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_contract_conformance_audit:",
    )
    expected_gate = _identified(
        {
            "gates": {
                "G0_exact_external_scope_and_valid_negative_predecessor_freeze": True,
                "G1_three_bounded_scope_clarifications_and_zero_predecessor_rewrite": True,
                "G2_exact_source_and_ten_contract_descriptors": True,
                "G3_answer_oracle_and_critical_decision_graph_separated": True,
                "G4_preaction_reasoning_action_observation_update_state_chain": True,
                "G5_noncompensatory_validity_target_depth_and_coverage_contracts": True,
                "G6_ten_direct_contract_counterexamples_reject": True,
                "G7_zero_execution_archive_release_and_vtdo_scope": True,
            },
            "passed_count": 8,
            "failed_count": 0,
            "noncompensatory": True,
            "schema_version": "finance_qa_reasoning_contract_gate.v1",
        },
        "gate_id",
        "finance_qa_reasoning_contract_gate:",
    )
    expected_report = _identified(
        {
            "authorization_id": models.CANDIDATE_AUTHORIZATION_ID,
            "predecessor_freeze_id": models.CANDIDATE_PREDECESSOR_FREEZE_ID,
            "scope_clarification_id": models.CANDIDATE_SCOPE_CLARIFICATION_ID,
            "source_binding_id": models.CANDIDATE_SOURCE_BINDING_ID,
            "contract_ids": tuple(row["contract_id"] for row in descriptors),
            "target_contract_id": target_contract["contract_id"],
            "coverage_matrix_id": coverage_matrix["matrix_id"],
            "conformance_audit_id": expected_conformance["audit_id"],
            "negative_audit_id": models.CANDIDATE_NEGATIVE_AUDIT_ID,
            "scope_audit_id": models.CANDIDATE_SCOPE_AUDIT_ID,
            "gate_id": expected_gate["gate_id"],
            "decision_id": models.CANDIDATE_DECISION_ID,
            "transition_id": models.CANDIDATE_TRANSITION_ID,
            "decision": (
                "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_"
                "freeze_passed_independent_audit_required"
            ),
            "contract_count": 10,
            "scientific_object_count": 13,
            "negative_controls": 10,
            "provider_calls": 0,
            "claim_boundary": "scientific_object_and_contract_freeze_only",
            "schema_version": "finance_qa_reasoning_contract_report.v1",
        },
        "report_id",
        "finance_qa_reasoning_contract_report:",
    )
    comparisons = {
        "conformance_audit": _encoded(expected_conformance) == saved["conformance_audit.json"],
        "gate_evaluation": _encoded(expected_gate) == saved["gate_evaluation.json"],
        "report": _encoded(expected_report) == saved["report.json"],
    }
    if not all(comparisons.values()):
        _fail("candidate.final_comparison", "candidate outcome object differs")
    decision = _load(saved["decision.json"])
    transition = _load(saved["transition.json"])
    if (
        decision.get("decision_id") != models.CANDIDATE_DECISION_ID
        or transition.get("transition_id") != models.CANDIDATE_TRANSITION_ID
    ):
        _fail("candidate.final_comparison", "candidate Decision or Transition differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "independent_negative_audit_id": negative_audit_id,
            "comparison_order": "after_all_independent_derivations_and_attacks",
            "candidate_actual_byte_comparisons": comparisons,
            "candidate_decision_identity_match": True,
            "candidate_transition_identity_match": True,
            "candidate_conformance_audit_used_as_input": False,
            "candidate_gate_used_as_oracle": False,
            "candidate_report_used_as_oracle": False,
            "candidate_attack_reason_hashes_used_as_oracle": False,
            "passed": True,
            "schema_version": "finance_qa_reasoning_candidate_final_comparison_audit.v1",
        },
        "audit_id",
        "finance_qa_reasoning_candidate_final_comparison_audit:",
    )
