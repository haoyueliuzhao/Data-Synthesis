from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any, NoReturn, TypeVar

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from . import models

ModelT = TypeVar("ModelT", bound=BaseModel)


class ReasoningContractAdmissionError(ValueError):
    """A vNext reasoning-bearing scientific object failed a typed Contract boundary."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise ReasoningContractAdmissionError(stage, reason)


def identified(model_type: type[ModelT], values: dict[str, Any], field: str, prefix: str) -> ModelT:
    provisional = model_type.model_construct(**values, **{field: "pending"})
    payload = provisional.model_dump(mode="python", exclude={field})
    payload[field] = strict_canonical_hash(payload, prefix=prefix)
    return model_type.model_validate(payload)


def build_contract_descriptors() -> tuple[models.ContractDescriptor, ...]:
    specifications = (
        (
            "AnswerOracleProgramBindingContract",
            "AnswerOracleProgramBindingV1",
            models.AnswerOracleProgramBindingV1,
            (
                "answer correctness is recomputable from exact Evidence and Program",
                "citation and rounding authority are explicit",
                "the Oracle does not prescribe a unique reasoning route",
            ),
            ("model reasoning trajectory", "private chain of thought", "single reference route"),
            "answer correctness only; no reasoning-validity claim",
        ),
        (
            "CriticalDecisionGraphContract",
            "CriticalDecisionGraphV1",
            models.CriticalDecisionGraphV1,
            (
                "required decision obligations are unique and topologically ordered",
                "every required obligation has a direct counterfactual intervention",
                "multiple valid obligation orders may be admitted",
            ),
            ("complete reference chain of thought", "language style", "answer Program node count"),
            "critical public decision obligations only",
        ),
        (
            "PublicReasoningStateContract",
            "PublicReasoningStateV1",
            models.PublicReasoningStateV1,
            (
                "only currently visible Evidence and verified Claims are addressable",
                "available Actions and completed Actions are separate",
                "private reasoning content is never persisted",
            ),
            ("future Observation", "cross-State Evidence", "private model reasoning"),
            "public decision state, not hidden cognition",
        ),
        (
            "ReasoningActionEnvelopeContract",
            "ReasoningActionEnvelopeV1",
            models.ReasoningActionEnvelopeV1,
            (
                "structured reasoning and Action commit atomically before execution",
                "selected Action is among current candidates and equals the inner Action",
                "decision basis binds visible Evidence or verified Claims",
            ),
            ("post-hoc rationale", "generic ungrounded rationale", "Action substitution"),
            "public structured decision record, never private chain of thought",
        ),
        (
            "ObservationUpdateContract",
            "ObservationUpdateV1",
            models.ObservationUpdateV1,
            (
                "Update binds exact Envelope, execution, Observation, and next State",
                "every accepted/rejected/revised Claim cites the actual Observation",
                "remaining uncertainty and newly enabled Actions are explicit",
            ),
            ("unbound Claim update", "Observation substitution", "silent State mutation"),
            "public effect of an Observation on Claims and next State",
        ),
        (
            "ReasoningTrajectoryContract",
            "ReasoningTrajectoryV1",
            models.ReasoningTrajectoryV1,
            (
                "each step is State-Envelope-Execution-Observation-Update-State",
                "all ordered step domains have equal cardinality",
                "all required Critical Decision obligations are covered",
            ),
            ("final rationale text", "cross-Job step", "missing obligation"),
            "time-ordered public reasoning/action/observation/update lineage",
        ),
        (
            "ReasoningValidityContract",
            "AnswerValidityReportV1+TrajectoryValidityReportV1+QualifiedReasoningTrajectoryV1",
            models.QualifiedReasoningTrajectoryV1,
            (
                "QA validity is source AND answer AND citation",
                "trajectory validity is preaction AND grounding AND reasoning-action AND "
                "observation-update AND critical coverage",
                "qualification is QA validity AND trajectory validity",
            ),
            ("compensatory score", "correct-answer override", "fluent-language override"),
            "separate answer and trajectory validity with noncompensatory qualification",
        ),
        (
            "TargetEvidenceAuthorityContract",
            "TargetEvidenceAuthorityContractV1",
            models.TargetEvidenceAuthorityContractV1,
            (
                "target modality, source, issuer, as-of time, effective period, scope, unit, "
                "basis, and locator are bound",
                "registered margin target permits management target or company guidance only",
                "actual, consensus, peer benchmark, arbitrary constant, and derived margin "
                "are excluded",
            ),
            ("observed actual", "analyst consensus", "arbitrary constant", "derived margin"),
            "authority for target-valued Evidence, not arithmetic correctness",
        ),
        (
            "DepthMetricContract",
            "ReasoningDepthMetricsV1",
            models.ReasoningDepthMetricsV1,
            (
                "semantic-operation, reasoning, evidence-integration, and correction depths "
                "are distinct",
                "critical-decision coverage is derived from required obligations",
                "tokens and text length are never depth authority",
            ),
            ("node count alias", "token count", "text length", "single undifferentiated depth"),
            "separate Program and public critical-reasoning measurements",
        ),
        (
            "QATaskAndReasoningCoverageMatrixContract",
            "QATaskAndReasoningCoverageMatrixV1",
            models.QATaskAndReasoningCoverageMatrixV1,
            (
                "eight coverage axes remain explicit",
                "first future fixture layer contains four distinct archetypes",
                "a frozen matrix is not a measured coverage result",
            ),
            ("task-count proxy", "maximum-depth proxy", "Benchmark-frequency claim"),
            "future experimental design only; no coverage estimate",
        ),
    )
    descriptors = []
    for name, scientific_object, model_type, invariants, forbidden, boundary in specifications:
        required_fields = tuple(model_type.model_fields)
        descriptors.append(
            identified(
                models.ContractDescriptor,
                {
                    "name": name,
                    "scientific_object": scientific_object,
                    "required_fields": required_fields,
                    "invariants": invariants,
                    "forbidden_substitutions": forbidden,
                    "claim_boundary": boundary,
                },
                "contract_id",
                "finance_qa_reasoning_contract_descriptor:",
            )
        )
    if tuple(item.name for item in descriptors) != models.CONTRACT_NAMES:
        raise ValueError("reasoning Contract descriptor domain differs")
    return tuple(descriptors)


def build_target_contract() -> models.TargetEvidenceAuthorityContractV1:
    return identified(
        models.TargetEvidenceAuthorityContractV1,
        {},
        "contract_id",
        "target_evidence_authority_contract:",
    )


def build_coverage_matrix() -> models.QATaskAndReasoningCoverageMatrixV1:
    cells = (
        models.CoverageMatrixCellV1(
            cell_id="future:serial_derivation",
            archetype="serial_derivation",
            task_family="ratio_and_period_change",
            program_topology="serial",
            evidence_modality="table_cell",
            temporal_structure="paired_period",
            entity_structure="single_entity",
            reasoning_obligation="period_and_definition_alignment",
            answer_shape="scalar",
            trajectory_structure="alternative_valid_path",
        ),
        models.CoverageMatrixCellV1(
            cell_id="future:branch_and_merge",
            archetype="branch_and_merge",
            task_family="comparison",
            program_topology="branch_and_merge",
            evidence_modality="table_cell",
            temporal_structure="paired_period",
            entity_structure="single_entity",
            reasoning_obligation="branch_selection_and_merge",
            answer_shape="scalar",
            trajectory_structure="alternative_valid_path",
        ),
        models.CoverageMatrixCellV1(
            cell_id="future:select_then_lookup",
            archetype="select_then_lookup",
            task_family="selection",
            program_topology="select_then_lookup",
            evidence_modality="table_cell",
            temporal_structure="multi_period",
            entity_structure="single_entity",
            reasoning_obligation="operation_choice_and_secondary_lookup",
            answer_shape="structured_explanation",
            trajectory_structure="direct",
        ),
        models.CoverageMatrixCellV1(
            cell_id="future:evidence_insufficiency_or_correction",
            archetype="evidence_insufficiency_or_correction",
            task_family="conflict_or_insufficiency",
            program_topology="correction",
            evidence_modality="narrative_statement",
            temporal_structure="single_period",
            entity_structure="single_entity",
            reasoning_obligation="evidence_sufficiency",
            answer_shape="structured_explanation",
            trajectory_structure="abstention_or_correction",
        ),
    )
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
    return identified(
        models.QATaskAndReasoningCoverageMatrixV1,
        {"axis_values": axes, "minimum_constructive_cells": cells},
        "matrix_id",
        "qa_task_and_reasoning_coverage_matrix:",
    )


def build_conformance_objects() -> dict[str, BaseModel]:
    task_id = "fixture:contract_conformance_task"
    oracle = identified(
        models.AnswerOracleProgramBindingV1,
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
        },
        "binding_id",
        "answer_oracle_program_binding:",
    )
    obligation = models.CriticalDecisionObligationV1(
        decision_id="decision:align_period_and_definition",
        trigger_state_predicate="evidence_available_and_alignment_unverified",
        subgoal="verify period and metric-definition comparability before calculation",
        unresolved_uncertainty_type="period_and_definition_alignment",
        required_evidence_roles=("metric_earlier", "metric_later"),
        admissible_action_classes=("verify_public_evidence_alignment",),
        admissible_alternative_action_ids=(
            "action:verify_alignment_primary",
            "action:verify_alignment_alternative",
        ),
        forbidden_shortcut_classes=("calculate_before_alignment", "future_evidence_reference"),
        produced_claim_schema={"type": "comparability_claim", "required": ("comparable",)},
        counterfactual_intervention_ids=(
            "intervention:swap_period",
            "intervention:change_metric_definition",
        ),
    )
    graph = identified(
        models.CriticalDecisionGraphV1,
        {
            "task_instance_id": task_id,
            "answer_oracle_program_binding_id": oracle.binding_id,
            "obligations": (obligation,),
        },
        "graph_id",
        "critical_decision_graph:",
    )
    state0 = identified(
        models.PublicReasoningStateV1,
        {
            "task_instance_id": task_id,
            "sequence_index": 0,
            "available_evidence_refs": ("evidence:earlier", "evidence:later"),
            "verified_claim_refs": (),
            "current_subgoal": obligation.subgoal,
            "remaining_uncertainties": (obligation.unresolved_uncertainty_type,),
            "available_action_ids": obligation.admissible_alternative_action_ids,
        },
        "state_id",
        "public_reasoning_state:",
    )
    envelope = identified(
        models.ReasoningActionEnvelopeV1,
        {
            "task_instance_id": task_id,
            "state_id": state0.state_id,
            "decision_graph_id": graph.graph_id,
            "decision_id": obligation.decision_id,
            "subgoal": obligation.subgoal,
            "evidence_refs": state0.available_evidence_refs,
            "unresolved_uncertainty": obligation.unresolved_uncertainty_type,
            "candidate_action_ids": state0.available_action_ids,
            "selected_action_id": "action:verify_alignment_primary",
            "decision_basis": (
                models.DecisionBasisEdgeV1(
                    relation="requires",
                    subject_ref="claim:period_and_definition_comparable",
                    evidence_refs=state0.available_evidence_refs,
                ),
            ),
            "expected_effect": "produce a public comparability Claim",
            "action": models.PublicActionV1(
                state_id=state0.state_id,
                action_id="action:verify_alignment_primary",
                decision_kind="verify_public_evidence_alignment",
            ),
            "preaction_commit_sequence": 0,
        },
        "envelope_id",
        "reasoning_action_envelope:",
    )
    execution = identified(
        models.ActionExecutionV1,
        {
            "task_instance_id": task_id,
            "parent_envelope_id": envelope.envelope_id,
            "state_id": state0.state_id,
            "action_id": envelope.selected_action_id,
            "execution_sequence": 1,
            "succeeded": True,
            "public_result_hash": hashlib.sha256(b"comparable:true").hexdigest(),
        },
        "execution_id",
        "reasoning_action_execution:",
    )
    public_payload = {"comparable": True, "mismatches": ()}
    observation = identified(
        models.PublicObservationV1,
        {
            "task_instance_id": task_id,
            "parent_execution_id": execution.execution_id,
            "state_id": state0.state_id,
            "observation_sequence": 1,
            "public_payload": public_payload,
            "public_payload_hash": hashlib.sha256(canonical_json_bytes(public_payload)).hexdigest(),
        },
        "observation_id",
        "public_reasoning_observation:",
    )
    claim = models.ClaimUpdateV1(
        claim_id="claim:period_and_definition_comparable",
        disposition="accepted",
        support_observation_refs=(observation.observation_id,),
        public_claim={"comparable": True},
    )
    state1 = identified(
        models.PublicReasoningStateV1,
        {
            "task_instance_id": task_id,
            "sequence_index": 1,
            "available_evidence_refs": state0.available_evidence_refs,
            "verified_claim_refs": (claim.claim_id,),
            "current_subgoal": "proceed to the answer Operation",
            "remaining_uncertainties": (),
            "available_action_ids": ("action:execute_answer_operation",),
            "completed_action_refs": (execution.execution_id,),
            "observation_refs": (observation.observation_id,),
        },
        "state_id",
        "public_reasoning_state:",
    )
    update = identified(
        models.ObservationUpdateV1,
        {
            "task_instance_id": task_id,
            "parent_reasoning_action_id": envelope.envelope_id,
            "action_execution_id": execution.execution_id,
            "observation_id": observation.observation_id,
            "accepted_claims": (claim,),
            "remaining_uncertainties": (),
            "newly_enabled_actions": state1.available_action_ids,
            "next_subgoal": state1.current_subgoal,
            "next_state_id": state1.state_id,
            "update_sequence": 1,
        },
        "update_id",
        "observation_update:",
    )
    trajectory = identified(
        models.ReasoningTrajectoryV1,
        {
            "task_instance_id": task_id,
            "initial_state_id": state0.state_id,
            "ordered_reasoning_action_ids": (envelope.envelope_id,),
            "ordered_action_execution_ids": (execution.execution_id,),
            "ordered_observation_ids": (observation.observation_id,),
            "ordered_observation_update_ids": (update.update_id,),
            "final_claim_refs": (claim.claim_id,),
            "final_answer_ref": "answer:contract_fixture",
            "critical_decision_graph_id": graph.graph_id,
            "answer_oracle_program_binding_id": oracle.binding_id,
            "covered_decision_ids": (obligation.decision_id,),
            "wording_fingerprint": "wording:fixture-a",
        },
        "trajectory_id",
        "reasoning_trajectory:",
    )
    answer_validity = identified(
        models.AnswerValidityReportV1,
        {
            "task_instance_id": task_id,
            "source_valid": True,
            "answer_valid": True,
            "citation_valid": True,
            "qa_valid": True,
        },
        "report_id",
        "answer_validity_report:",
    )
    trajectory_validity = identified(
        models.TrajectoryValidityReportV1,
        {
            "trajectory_id": trajectory.trajectory_id,
            "preaction_valid": True,
            "grounding_valid": True,
            "reasoning_action_valid": True,
            "observation_update_valid": True,
            "critical_coverage_valid": True,
            "trajectory_valid": True,
        },
        "report_id",
        "reasoning_trajectory_validity_report:",
    )
    qualification = identified(
        models.QualifiedReasoningTrajectoryV1,
        {
            "task_instance_id": task_id,
            "trajectory_id": trajectory.trajectory_id,
            "answer_validity_report_id": answer_validity.report_id,
            "trajectory_validity_report_id": trajectory_validity.report_id,
            "qa_valid": answer_validity.qa_valid,
            "trajectory_valid": trajectory_validity.trajectory_valid,
            "qualified": True,
        },
        "qualification_id",
        "qualified_reasoning_trajectory:",
    )
    depth = identified(
        models.ReasoningDepthMetricsV1,
        {
            "task_instance_id": task_id,
            "trajectory_id": trajectory.trajectory_id,
            "semantic_operation_depth": 3,
            "reasoning_depth": 1,
            "evidence_integration_depth": 2,
            "correction_depth": 0,
            "required_decision_count": 1,
            "covered_required_decision_count": 1,
            "critical_decision_coverage": 1.0,
        },
        "metrics_id",
        "reasoning_depth_metrics:",
    )
    admit_reasoning_action(envelope, state0, graph, execution)
    admit_observation_update(update, envelope, execution, observation, state1)
    admit_reasoning_trajectory(
        trajectory, graph, (envelope,), (execution,), (observation,), (update,)
    )
    admit_qualification(qualification, answer_validity, trajectory_validity)
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
        "answer_validity": answer_validity,
        "trajectory_validity": trajectory_validity,
        "qualification": qualification,
        "depth_metrics": depth,
    }


def admit_reasoning_action(
    envelope: models.ReasoningActionEnvelopeV1,
    state: models.PublicReasoningStateV1,
    graph: models.CriticalDecisionGraphV1,
    execution: models.ActionExecutionV1 | None = None,
) -> None:
    obligations = {item.decision_id: item for item in graph.obligations}
    obligation = obligations.get(envelope.decision_id)
    if (
        envelope.task_instance_id != state.task_instance_id
        or graph.task_instance_id != state.task_instance_id
        or envelope.state_id != state.state_id
    ):
        _fail("reasoning.state_binding", "Reasoning Action crosses task or State authority")
    if obligation is None:
        _fail("reasoning.decision_obligation", "Reasoning Action names no graph obligation")
    if not set(envelope.evidence_refs) <= set(state.available_evidence_refs) or not set(
        envelope.claim_refs
    ) <= set(state.verified_claim_refs):
        _fail("reasoning.visible_refs", "Reasoning Action references unavailable Evidence or Claim")
    if (
        envelope.subgoal != obligation.subgoal
        or envelope.unresolved_uncertainty != obligation.unresolved_uncertainty_type
        or envelope.selected_action_id not in state.available_action_ids
        or envelope.selected_action_id not in obligation.admissible_alternative_action_ids
    ):
        _fail("reasoning.decision_alignment", "Reasoning Action differs from current obligation")
    if execution is not None:
        if envelope.preaction_commit_sequence >= execution.execution_sequence:
            _fail("reasoning.preaction_commit", "reasoning was not committed before execution")
        if (
            execution.parent_envelope_id != envelope.envelope_id
            or execution.state_id != envelope.state_id
            or execution.action_id != envelope.selected_action_id
        ):
            _fail(
                "reasoning.action_consistency", "reasoning-selected Action differs from execution"
            )


def admit_observation_update(
    update: models.ObservationUpdateV1,
    envelope: models.ReasoningActionEnvelopeV1,
    execution: models.ActionExecutionV1,
    observation: models.PublicObservationV1,
    next_state: models.PublicReasoningStateV1,
) -> None:
    if (
        update.task_instance_id != envelope.task_instance_id
        or update.parent_reasoning_action_id != envelope.envelope_id
        or update.action_execution_id != execution.execution_id
        or update.observation_id != observation.observation_id
        or observation.parent_execution_id != execution.execution_id
        or update.next_state_id != next_state.state_id
        or update.update_sequence != observation.observation_sequence
        or next_state.sequence_index != update.update_sequence
    ):
        _fail("reasoning.observation_update", "Observation Update lineage differs")
    accepted_ids = {item.claim_id for item in update.accepted_claims}
    if not accepted_ids <= set(next_state.verified_claim_refs):
        _fail("reasoning.claim_update", "accepted Claim is absent from next State")


def admit_reasoning_trajectory(
    trajectory: models.ReasoningTrajectoryV1,
    graph: models.CriticalDecisionGraphV1,
    envelopes: Sequence[models.ReasoningActionEnvelopeV1],
    executions: Sequence[models.ActionExecutionV1],
    observations: Sequence[models.PublicObservationV1],
    updates: Sequence[models.ObservationUpdateV1],
) -> None:
    if (
        trajectory.task_instance_id != graph.task_instance_id
        or trajectory.critical_decision_graph_id != graph.graph_id
        or tuple(item.envelope_id for item in envelopes) != trajectory.ordered_reasoning_action_ids
        or tuple(item.execution_id for item in executions)
        != trajectory.ordered_action_execution_ids
        or tuple(item.observation_id for item in observations) != trajectory.ordered_observation_ids
        or tuple(item.update_id for item in updates) != trajectory.ordered_observation_update_ids
    ):
        _fail("reasoning.trajectory_lineage", "Reasoning Trajectory ordered lineage differs")
    required = {item.decision_id for item in graph.obligations if item.required}
    if not required <= set(trajectory.covered_decision_ids):
        _fail("reasoning.critical_coverage", "required Critical Decision obligation is missing")


def admit_qualification(
    qualification: models.QualifiedReasoningTrajectoryV1,
    answer: models.AnswerValidityReportV1,
    trajectory: models.TrajectoryValidityReportV1,
) -> None:
    if (
        qualification.answer_validity_report_id != answer.report_id
        or qualification.trajectory_validity_report_id != trajectory.report_id
        or qualification.qa_valid != answer.qa_valid
        or qualification.trajectory_valid != trajectory.trajectory_valid
        or not qualification.qualified
    ):
        _fail("reasoning.qualification", "QA and trajectory validity do not jointly qualify")


def admit_target_evidence(
    candidate: models.TargetEvidenceCandidateV1,
    contract: models.TargetEvidenceAuthorityContractV1,
) -> None:
    if candidate.target_modality not in contract.allowed_modalities:
        _fail("target.modality", "target Evidence modality is not authorized")
    values = candidate.model_dump(mode="python")
    if any(not values[field] for field in contract.required_fields):
        _fail("target.required_fields", "target Evidence authority field is absent")


def quotient_signature(trajectory: models.ReasoningTrajectoryV1) -> str:
    return strict_canonical_hash(
        {
            "task_instance_id": trajectory.task_instance_id,
            "critical_decision_graph_id": trajectory.critical_decision_graph_id,
            "covered_decision_ids": trajectory.covered_decision_ids,
            "reasoning_action_count": len(trajectory.ordered_reasoning_action_ids),
            "action_execution_count": len(trajectory.ordered_action_execution_ids),
            "observation_update_count": len(trajectory.ordered_observation_update_ids),
            "final_claim_refs": trajectory.final_claim_refs,
            "termination_mode": "final_answer",
        },
        prefix="reasoning_trajectory_quotient_state:",
    )


def require_distinct_quotient_states(
    left: models.ReasoningTrajectoryV1, right: models.ReasoningTrajectoryV1
) -> None:
    if quotient_signature(left) == quotient_signature(right):
        _fail("reasoning.quotient_state", "wording-only trajectories share one quotient State")
