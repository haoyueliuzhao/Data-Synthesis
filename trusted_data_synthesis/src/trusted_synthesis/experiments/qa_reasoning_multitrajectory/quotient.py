"""Predeclared semantic quotient for the two frozen reasoning-bearing tasks.

The quotient retains the typed causal decision graph and its actual public results.
The order of independent revenue and operating-income callbacks is operational
lineage, not a new semantic decision.  This rule is fixed without inspecting any
candidate outcome.  Qualification and independent replay must precede projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

DECISION_KINDS = (
    "comparability",
    "revenue_branch",
    "operating_income_branch",
    "branch_merge",
    "final_grounding",
)
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "comparability": (),
    "revenue_branch": ("comparability",),
    "operating_income_branch": ("comparability",),
    "branch_merge": ("revenue_branch", "operating_income_branch"),
    "final_grounding": ("branch_merge",),
}
PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    "comparability": (
        "comparable",
        "subject_id",
        "unit",
        "currency",
        "earlier_period",
        "later_period",
        "evidence_refs",
    ),
    "revenue_branch": ("operator_id", "program_node_id", "value", "unit", "evidence_refs"),
    "operating_income_branch": (
        "operator_id",
        "program_node_id",
        "value",
        "unit",
        "evidence_refs",
    ),
    "branch_merge": (
        "operator_ids",
        "signed_gap",
        "absolute_growth_spread",
        "unit",
        "claim_refs",
        "evidence_refs",
    ),
    "final_grounding": (
        "program_execution_id",
        "verification_trajectory_id",
        "assessment_id",
        "final_answer",
        "citation_evidence_ids",
        "source_program_id",
        "source_program_hash",
    ),
}
OPERATIONAL_FINAL_FIELDS = (
    "program_execution_id",
    "verification_trajectory_id",
    "assessment_id",
)
NUMERIC_FIELDS = frozenset({"value", "signed_gap", "absolute_growth_spread"})


class QuotientAdmissionError(ValueError):
    """The candidate did not enter the frozen semantic quotient domain."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise QuotientAdmissionError(stage, reason)


def _object(value: Any, field: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return dict(value)
    _fail("quotient.object", f"{field} is not a typed object")


def _objects(value: Any, field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        _fail("quotient.object", f"{field} is not an object sequence")
    return tuple(_object(item, field) for item in value)


def _identified(payload: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {**payload, "content_id": strict_canonical_hash(payload, prefix=prefix)}


def build_quotient_contract() -> dict[str, Any]:
    """Return outcome-independent rules to persist before any trajectory executes."""
    return _identified(
        {
            "schema_version": "qa_reasoning_multitrajectory_quotient_contract.v1",
            "projection_kind": "typed_semantic_causal_decision_graph",
            "canonical_decision_order": DECISION_KINDS,
            "required_dependencies": DEPENDENCIES,
            "payload_field_domain": PAYLOAD_FIELDS,
            "numeric_normalization": "finite_exact_decimal_no_rounding",
            "coverage_and_claim_order": "canonical_critical_decision_graph_order",
            "claim_reference_projection": "producer_decision_role",
            "independent_commuting_pair": ("revenue_branch", "operating_income_branch"),
            "retained_scope": (
                "exact_task",
                "evidence_binding",
                "exact_evidence_role_bindings",
                "answer_oracle",
                "source_program",
                "answer_schema",
                "citation_evidence",
                "critical_decision_graph",
            ),
            "retained_decision_fields": (
                "decision_role",
                "action_semantic_kind",
                "typed_evidence_inputs",
                "typed_claim_inputs",
                "decision_dependencies",
                "produced_claim_type",
                "public_numeric_and_grounding_result",
            ),
            "excluded_operational_fields": (
                "execution_schedule",
                "wording",
                "runtime_object_ids",
                "sequence_numbers",
                "durable_artifact_paths",
                "fsync_event_numbers",
            ),
            "excluded_final_payload_fields": OPERATIONAL_FINAL_FIELDS,
            "qualification_required_before_projection": True,
            "independent_actual_execution_replay_required": True,
            "distinct_trajectory_hash_is_not_distinct_quotient_authority": True,
            "postoutcome_contract_change_admitted": False,
            "negative_single_class_result_admitted": True,
            "claim_boundary": "finite_candidate_family_local_deterministic_constructibility",
        },
        "qa_reasoning_multitrajectory_quotient_contract:",
    )


def _decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        _fail("quotient.numeric_type", "public numeric value is not exact Decimal-compatible")
    try:
        number = Decimal(value)
    except InvalidOperation:
        _fail("quotient.numeric_type", "public numeric value cannot be parsed")
    if not number.is_finite():
        _fail("quotient.numeric_type", "public numeric value is not finite")
    if number == 0:
        return "0"
    # Formatting and trimming avoid context-dependent Decimal.normalize rounding.
    result = format(number, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _canonical_result(value: Any, claim_producers: Mapping[str, str], *, field: str = "") -> Any:
    if field in NUMERIC_FIELDS:
        return {"numeric_type": "exact_decimal", "value": _decimal(value)}
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_result(item, claim_producers, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        if field == "claim_refs":
            if len(value) != len(set(value)) or any(item not in claim_producers for item in value):
                _fail("quotient.claim_authority", "claim reference has no unique actual producer")
            return sorted((claim_producers[item] for item in value), key=DECISION_KINDS.index)
        projected = [_canonical_result(item, claim_producers) for item in value]
        if field in {"evidence_refs", "citation_evidence_ids", "citations"}:
            return sorted(projected, key=canonical_json_bytes)
        return projected
    return value


def _qualified_result(result: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    trajectory = _object(result.get("trajectory"), "trajectory")
    qualification = _object(result.get("qualification"), "qualification")
    answer = _object(result.get("answer_validity"), "answer_validity")
    validity = _object(result.get("trajectory_validity"), "trajectory_validity")
    replay = _object(result.get("replay_audit"), "replay_audit")
    if (
        any(
            qualification.get(key) is not True
            for key in ("qualified", "qa_valid", "trajectory_valid")
        )
        or any(
            answer.get(key) is not True
            for key in ("source_valid", "answer_valid", "citation_valid", "qa_valid")
        )
        or any(
            validity.get(key) is not True
            for key in (
                "preaction_valid",
                "grounding_valid",
                "reasoning_action_valid",
                "observation_update_valid",
                "critical_coverage_valid",
                "trajectory_valid",
            )
        )
        or replay.get("passed") is not True
        or replay.get("trajectory_id") != trajectory.get("trajectory_id")
        or replay.get("replay_input_sha256")
        != strict_canonical_hash(
            {
                key: result.get(key)
                for key in (
                    "trajectory",
                    "envelopes",
                    "executions",
                    "observations",
                    "updates",
                    "qualification",
                )
            }
        )
        or qualification.get("trajectory_id") != trajectory.get("trajectory_id")
        or validity.get("trajectory_id") != trajectory.get("trajectory_id")
        or qualification.get("answer_validity_report_id") != answer.get("report_id")
        or qualification.get("trajectory_validity_report_id") != validity.get("report_id")
        or qualification.get("task_instance_id") != trajectory.get("task_instance_id")
        or answer.get("task_instance_id") != trajectory.get("task_instance_id")
    ):
        _fail("quotient.qualified_replay", "qualification and independent replay must pass first")
    return trajectory, replay


def _scope(result: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    package = _object(result.get("package"), "package")
    task = _object(package.get("task"), "task")
    oracle = _object(result.get("oracle"), "oracle")
    binding = _object(package.get("binding_snapshot"), "binding_snapshot")
    semantic_plan = _object(package.get("semantic_plan"), "semantic_plan")
    task_oracle = _object(task.get("oracle"), "task.oracle")
    program = _object(task_oracle.get("task_program"), "task.oracle.task_program")
    if (
        graph.get("task_instance_id") != task.get("task_id")
        or oracle.get("task_instance_id") != task.get("task_id")
        or graph.get("answer_oracle_program_binding_id") != oracle.get("binding_id")
        or oracle.get("evidence_binding_id") != binding.get("evidence_binding_id")
        or oracle.get("canonical_semantic_plan_id") != semantic_plan.get("plan_id")
    ):
        _fail("quotient.task_scope", "exact task and its Oracle/Program parents differ")
    return {
        "task_instance_id": task["task_id"],
        "exact_task_sha256": strict_canonical_hash(task),
        "evidence_binding_id": binding["evidence_binding_id"],
        "evidence_role_bindings": binding["role_bindings"],
        "answer_oracle_binding_id": oracle["binding_id"],
        "critical_decision_graph_id": graph["graph_id"],
        "canonical_semantic_plan_id": semantic_plan["plan_id"],
        "source_program_id": program["program_id"],
        "source_program_sha256": strict_canonical_hash(program),
        "answer_schema": semantic_plan["answer_schema"],
        "citation_contract_id": oracle["citation_contract_id"],
        "citation_evidence_ids": sorted(task_oracle["gold_evidence_ids"]),
        "tolerance_and_rounding_contract": oracle["tolerance_and_rounding_contract"],
    }


def project_quotient(result: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    """Project a freshly executed, independently replayed Qualified trajectory.

    Runtime object identities remain in the trajectory's lineage.  Semantic input
    claims are replaced by their actual producer decision roles, then decisions
    are emitted in frozen CDG order.  Swapping D1 and D2 consequently collapses.
    """
    if canonical_json_bytes(contract) != canonical_json_bytes(build_quotient_contract()):
        _fail("quotient.predeclared_contract", "candidate quotient rules differ from frozen rules")
    trajectory, _ = _qualified_result(result)
    graph = _object(result.get("graph"), "graph")
    obligations = _objects(graph.get("obligations"), "graph.obligations")
    if len(obligations) != len(DECISION_KINDS):
        _fail("quotient.decision_domain", "the exact five-decision domain is required")
    decision_roles = {
        obligation["decision_id"]: kind
        for obligation, kind in zip(obligations, DECISION_KINDS, strict=True)
    }
    if len(decision_roles) != 5 or set(trajectory.get("covered_decision_ids", ())) != set(
        decision_roles
    ):
        _fail("quotient.decision_domain", "required decision coverage differs")
    for obligation, kind in zip(obligations, DECISION_KINDS, strict=True):
        dependencies = tuple(
            decision_roles.get(parent) for parent in obligation["downstream_claim_dependencies"]
        )
        if (
            dependencies != DEPENDENCIES[kind]
            or tuple(obligation["admissible_action_classes"])
            != (f"execute_{kind}", f"reject_{kind}")
            or obligation.get("required") is not True
        ):
            _fail("quotient.decision_domain", "decision semantics or source dependencies differ")

    envelopes = _objects(result.get("envelopes"), "envelopes")
    observations = _objects(result.get("observations"), "observations")
    updates = _objects(result.get("updates"), "updates")
    executions = _objects(result.get("executions"), "executions")
    if {len(envelopes), len(observations), len(updates), len(executions)} != {5}:
        _fail("quotient.runtime_domain", "five complete action/observation/update steps required")
    claim_producers: dict[str, str] = {}
    steps: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    for envelope, observation, update, execution in zip(
        envelopes, observations, updates, executions, strict=True
    ):
        resolved_kind = decision_roles.get(envelope.get("decision_id"))
        if resolved_kind is None or resolved_kind in steps:
            _fail("quotient.runtime_domain", "runtime decision has no unique CDG obligation")
        kind = resolved_kind
        claims = _objects(update.get("accepted_claims"), "update.accepted_claims")
        if (
            len(claims) != 1
            or update.get("rejected_or_revised_claims")
            or update.get("parent_reasoning_action_id") != envelope.get("envelope_id")
            or update.get("observation_id") != observation.get("observation_id")
            or observation.get("parent_execution_id") != execution.get("execution_id")
            or execution.get("parent_envelope_id") != envelope.get("envelope_id")
            or execution.get("succeeded") is not True
            or _object(envelope.get("action"), "envelope.action").get("decision_kind")
            != f"execute_{kind}"
        ):
            _fail("quotient.runtime_lineage", "actual qualified public decision lineage differs")
        claim = claims[0]
        claim_id = claim["claim_id"]
        public_claim = _object(claim.get("public_claim"), "claim.public_claim")
        if (
            claim_id in claim_producers
            or public_claim.get("obligation_kind") != kind
            or claim.get("disposition") != "accepted"
            or tuple(claim.get("support_observation_refs", ())) != (observation["observation_id"],)
            or canonical_json_bytes(public_claim.get("result"))
            != canonical_json_bytes(observation.get("public_payload"))
        ):
            _fail("quotient.claim_authority", "claim does not derive from its actual Observation")
        claim_producers[claim_id] = kind
        steps[kind] = envelope, observation, public_claim
    if set(trajectory.get("final_claim_refs", ())) != set(claim_producers):
        _fail("quotient.claim_authority", "final Claim domain differs from actual producers")

    scope = _scope(result, graph)
    if (
        trajectory.get("task_instance_id") != scope["task_instance_id"]
        or trajectory.get("critical_decision_graph_id") != graph["graph_id"]
        or trajectory.get("answer_oracle_program_binding_id") != scope["answer_oracle_binding_id"]
    ):
        _fail("quotient.task_scope", "trajectory Task differs from source Task")
    role_bindings = _object(scope["evidence_role_bindings"], "evidence_role_bindings")
    nodes: list[dict[str, Any]] = []
    for obligation, kind in zip(obligations, DECISION_KINDS, strict=True):
        envelope, observation, _ = steps[kind]
        payload = _object(observation.get("public_payload"), "observation.public_payload")
        if set(payload) != set(PAYLOAD_FIELDS[kind]):
            _fail(
                "quotient.public_result_schema", "public result has an unregistered semantic field"
            )
        dependencies = tuple(
            _canonical_result(envelope.get("claim_refs", ()), claim_producers, field="claim_refs")
        )
        if dependencies != DEPENDENCIES[kind]:
            _fail("quotient.claim_authority", "actual Claim dependencies differ from the CDG")
        typed_evidence_inputs = tuple(
            {"role": role, "evidence_ids": tuple(role_bindings[role])}
            for role in obligation["required_evidence_roles"]
            if role in role_bindings
        )
        expected_evidence = {
            evidence_id for item in typed_evidence_inputs for evidence_id in item["evidence_ids"]
        }
        if expected_evidence and set(envelope.get("evidence_refs", ())) != expected_evidence:
            _fail(
                "quotient.evidence_authority", "typed Evidence input differs from actual Envelope"
            )
        public_result = {
            key: value
            for key, value in payload.items()
            if not (kind == "final_grounding" and key in OPERATIONAL_FINAL_FIELDS)
        }
        nodes.append(
            {
                "decision_role": kind,
                "action_semantic_kind": f"execute_{kind}",
                "typed_evidence_inputs": typed_evidence_inputs,
                "actual_evidence_refs": sorted(envelope.get("evidence_refs", ())),
                "typed_claim_inputs": tuple(
                    {"producer_decision_role": role} for role in dependencies
                ),
                "decision_dependencies": dependencies,
                "produced_claim_type": obligation["produced_claim_schema"],
                "public_result": _canonical_result(public_result, claim_producers),
            }
        )
    return _identified(
        {
            "schema_version": "qa_reasoning_multitrajectory_quotient.v1",
            "contract_id": contract["content_id"],
            "task_scope": scope,
            "decision_nodes": tuple(nodes),
            "causal_edges": tuple(
                {"from_decision": parent, "to_decision": kind}
                for kind in DECISION_KINDS
                for parent in DEPENDENCIES[kind]
            ),
            "termination_mode": "qualified_final_answer",
        },
        "qa_reasoning_multitrajectory_quotient:",
    )
