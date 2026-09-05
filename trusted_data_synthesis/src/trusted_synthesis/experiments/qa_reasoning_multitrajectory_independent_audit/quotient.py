"""Independent causal quotient reconstruction for the four own-trajectory replays.

The source rule is a five-vertex DAG.  This module enumerates its linear orders,
admits each result against its own independent replay, and derives semantic nodes
from actual action/observation/claim links before reading comparison projections.
No candidate quotient, partition, or execution helper is imported or called.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from itertools import permutations
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

# Independent primitive rule specification, in the frozen causal role order.
ROLES = (
    "comparability",
    "revenue_branch",
    "operating_income_branch",
    "branch_merge",
    "final_grounding",
)
PARENT_INDICES = ((), (0,), (0,), (1, 2), (3,))
PAYLOAD_DOMAIN = (
    (
        "comparable",
        "subject_id",
        "unit",
        "currency",
        "earlier_period",
        "later_period",
        "evidence_refs",
    ),
    ("operator_id", "program_node_id", "value", "unit", "evidence_refs"),
    ("operator_id", "program_node_id", "value", "unit", "evidence_refs"),
    ("operator_ids", "signed_gap", "absolute_growth_spread", "unit", "claim_refs", "evidence_refs"),
    (
        "program_execution_id",
        "verification_trajectory_id",
        "assessment_id",
        "final_answer",
        "citation_evidence_ids",
        "source_program_id",
        "source_program_hash",
    ),
)
EXCLUDED_FINAL = ("program_execution_id", "verification_trajectory_id", "assessment_id")
REPLAY_DOMAINS = (
    "trajectory",
    "envelopes",
    "executions",
    "observations",
    "updates",
    "qualification",
)


class IndependentQuotientError(ValueError):
    """An independently evaluated quotient relation did not hold."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _require(condition: bool, stage: str, reason: str) -> None:
    if not condition:
        raise IndependentQuotientError(stage, reason)


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    _require(isinstance(value, Mapping), "quotient.object", "typed object is required")
    return dict(value)


def _identified(payload: dict[str, Any], prefix: str, field: str = "content_id") -> dict[str, Any]:
    return {**payload, field: strict_canonical_hash(payload, prefix=prefix)}


def independent_contract() -> dict[str, Any]:
    """Construct the predeclared rule object solely from this source specification."""
    return _identified(
        {
            "schema_version": "qa_reasoning_multitrajectory_quotient_contract.v1",
            "projection_kind": "typed_semantic_causal_decision_graph",
            "canonical_decision_order": ROLES,
            "required_dependencies": {
                role: tuple(ROLES[parent] for parent in PARENT_INDICES[index])
                for index, role in enumerate(ROLES)
            },
            "payload_field_domain": dict(zip(ROLES, PAYLOAD_DOMAIN, strict=True)),
            "numeric_normalization": "finite_exact_decimal_no_rounding",
            "coverage_and_claim_order": "canonical_critical_decision_graph_order",
            "claim_reference_projection": "producer_decision_role",
            "independent_commuting_pair": (ROLES[1], ROLES[2]),
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
            "excluded_final_payload_fields": EXCLUDED_FINAL,
            "qualification_required_before_projection": True,
            "independent_actual_execution_replay_required": True,
            "distinct_trajectory_hash_is_not_distinct_quotient_authority": True,
            "postoutcome_contract_change_admitted": False,
            "negative_single_class_result_admitted": True,
            "claim_boundary": "finite_candidate_family_local_deterministic_constructibility",
        },
        "qa_reasoning_multitrajectory_quotient_contract:",
    )


def enumerate_schedules() -> tuple[tuple[str, ...], ...]:
    """Check all 5! orders against the five source dependency edges."""
    admitted = []
    for order in permutations(range(len(ROLES))):
        position = {node: index for index, node in enumerate(order)}
        if all(
            position[parent] < position[child]
            for child, parents in enumerate(PARENT_INDICES)
            for parent in parents
        ):
            admitted.append(tuple(f"D{node}" for node in order))
    return tuple(admitted)


def normalize_decimal(value: Any) -> str:
    """Render a finite exact decimal without invoking context-dependent normalize."""
    _require(
        not isinstance(value, bool) and isinstance(value, (Decimal, str, int)),
        "quotient.numeric",
        "a public numeric value must have an exact decimal representation",
    )
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise IndependentQuotientError("quotient.numeric", "invalid decimal") from error
    _require(number.is_finite(), "quotient.numeric", "nonfinite decimal is not admitted")
    if number.is_zero():
        return "0"
    rendered = format(number, "f")
    whole, separator, fraction = rendered.partition(".")
    fraction = fraction.rstrip("0")
    return whole + (separator + fraction if fraction else "")


def _normalize(value: Any, producers: Mapping[str, str], field: str = "") -> Any:
    if field in {"value", "signed_gap", "absolute_growth_spread"}:
        return {"numeric_type": "exact_decimal", "value": normalize_decimal(value)}
    if isinstance(value, Mapping):
        return {key: _normalize(item, producers, key) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if field == "claim_refs":
            _require(
                len(set(value)) == len(value) and all(item in producers for item in value),
                "quotient.claim",
                "claim inputs need distinct actual producer identities",
            )
            return sorted((producers[item] for item in value), key=ROLES.index)
        items = [_normalize(item, producers) for item in value]
        if field in {"evidence_refs", "citation_evidence_ids", "citations"}:
            items.sort(key=canonical_json_bytes)
        return items
    return value


def _admit_replay(result: Mapping[str, Any]) -> dict[str, Any]:
    trajectory = _object(result["trajectory"])
    replay = _object(result["replay_audit"])
    qualification = _object(result["qualification"])
    answer = _object(result["answer_validity"])
    validity = _object(result["trajectory_validity"])
    for report, fields in (
        (replay, ("passed", "independent_replay")),
        (qualification, ("qualified", "qa_valid", "trajectory_valid")),
        (answer, ("source_valid", "answer_valid", "citation_valid", "qa_valid")),
        (
            validity,
            (
                "preaction_valid",
                "grounding_valid",
                "reasoning_action_valid",
                "observation_update_valid",
                "critical_coverage_valid",
                "trajectory_valid",
            ),
        ),
    ):
        _require(
            all(report.get(field) is True for field in fields),
            "quotient.own_replay",
            "independent qualification must pass",
        )
    _require(
        all(
            report.get("trajectory_id") == trajectory["trajectory_id"]
            for report in (replay, qualification, validity)
        )
        and qualification["answer_validity_report_id"] == answer["report_id"]
        and qualification["trajectory_validity_report_id"] == validity["report_id"]
        and qualification["task_instance_id"]
        == answer["task_instance_id"]
        == trajectory["task_instance_id"]
        and replay["replay_input_sha256"]
        == strict_canonical_hash({key: result[key] for key in REPLAY_DOMAINS}),
        "quotient.own_replay",
        "proof must bind this trajectory and all six actual replay domains",
    )
    return trajectory


def independent_projection(
    result: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive each semantic vertex from that replay's actual causal claim producer."""
    _require(
        canonical_json_bytes(contract) == canonical_json_bytes(independent_contract()),
        "quotient.predeclared_rules",
        "rules differ from their predeclared source",
    )
    trajectory = _admit_replay(result)
    graph = _object(result["graph"])
    obligations = [_object(item) for item in graph["obligations"]]
    _require(len(obligations) == len(ROLES), "quotient.graph", "five obligations are required")
    decision_roles = {
        item["decision_id"]: role for item, role in zip(obligations, ROLES, strict=True)
    }
    _require(
        len(decision_roles) == 5 and set(trajectory["covered_decision_ids"]) == set(decision_roles),
        "quotient.graph",
        "exact decision coverage is required",
    )
    for index, obligation in enumerate(obligations):
        _require(
            tuple(decision_roles[parent] for parent in obligation["downstream_claim_dependencies"])
            == tuple(ROLES[parent] for parent in PARENT_INDICES[index])
            and tuple(obligation["admissible_action_classes"])
            == (f"execute_{ROLES[index]}", f"reject_{ROLES[index]}")
            and obligation["required"] is True,
            "quotient.graph",
            "decision dependencies or action semantics changed",
        )
    groups = [
        [_object(item) for item in result[key]]
        for key in ("envelopes", "executions", "observations", "updates")
    ]
    _require(
        all(len(group) == 5 for group in groups),
        "quotient.runtime",
        "five complete execution steps are required",
    )
    producers: dict[str, str] = {}
    vertices: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for envelope, execution, observation, update in zip(*groups, strict=True):
        role = decision_roles.get(envelope["decision_id"])
        _require(
            role in ROLES and role not in vertices,
            "quotient.runtime",
            "each decision needs one actual execution",
        )
        assert role is not None
        claims = [_object(item) for item in update["accepted_claims"]]
        _require(
            len(claims) == 1
            and not update["rejected_or_revised_claims"]
            and update["parent_reasoning_action_id"] == envelope["envelope_id"]
            and update["observation_id"] == observation["observation_id"]
            and observation["parent_execution_id"] == execution["execution_id"]
            and execution["parent_envelope_id"] == envelope["envelope_id"]
            and execution["succeeded"] is True
            and _object(envelope["action"])["decision_kind"] == f"execute_{role}",
            "quotient.lineage",
            "actual action/execution/observation/update parents differ",
        )
        claim = claims[0]
        public_claim = _object(claim["public_claim"])
        _require(
            claim["claim_id"] not in producers
            and claim["disposition"] == "accepted"
            and public_claim["obligation_kind"] == role
            and tuple(claim["support_observation_refs"]) == (observation["observation_id"],)
            and canonical_json_bytes(public_claim["result"])
            == canonical_json_bytes(observation["public_payload"]),
            "quotient.claim",
            "accepted claim must bind its actual observed producer",
        )
        producers[claim["claim_id"]] = role
        vertices[role] = envelope, observation
    _require(
        set(trajectory["final_claim_refs"]) == set(producers),
        "quotient.claim",
        "final claims must equal the actual producer set",
    )
    package = _object(result["package"])
    task = _object(package["task"])
    binding = _object(package["binding_snapshot"])
    plan = _object(package["semantic_plan"])
    oracle = _object(result["oracle"])
    task_oracle = _object(task["oracle"])
    program = _object(task_oracle["task_program"])
    _require(
        graph["task_instance_id"]
        == oracle["task_instance_id"]
        == trajectory["task_instance_id"]
        == task["task_id"]
        and graph["answer_oracle_program_binding_id"]
        == trajectory["answer_oracle_program_binding_id"]
        == oracle["binding_id"]
        and graph["graph_id"] == trajectory["critical_decision_graph_id"]
        and oracle["evidence_binding_id"] == binding["evidence_binding_id"]
        and oracle["canonical_semantic_plan_id"] == plan["plan_id"],
        "quotient.task",
        "task, evidence, graph and Oracle authority must agree",
    )
    scope = {
        "task_instance_id": task["task_id"],
        "exact_task_sha256": strict_canonical_hash(task),
        "evidence_binding_id": binding["evidence_binding_id"],
        "evidence_role_bindings": binding["role_bindings"],
        "answer_oracle_binding_id": oracle["binding_id"],
        "critical_decision_graph_id": graph["graph_id"],
        "canonical_semantic_plan_id": plan["plan_id"],
        "source_program_id": program["program_id"],
        "source_program_sha256": strict_canonical_hash(program),
        "answer_schema": plan["answer_schema"],
        "citation_contract_id": oracle["citation_contract_id"],
        "citation_evidence_ids": sorted(task_oracle["gold_evidence_ids"]),
        "tolerance_and_rounding_contract": oracle["tolerance_and_rounding_contract"],
    }
    nodes = []
    for index, role in enumerate(ROLES):
        envelope, observation = vertices[role]
        payload = _object(observation["public_payload"])
        _require(
            set(payload) == set(PAYLOAD_DOMAIN[index]),
            "quotient.payload",
            "public semantic result field domain changed",
        )
        claim_roles = _normalize(envelope["claim_refs"], producers, "claim_refs")
        _require(
            tuple(claim_roles) == tuple(ROLES[parent] for parent in PARENT_INDICES[index]),
            "quotient.claim",
            "actual claim dependencies must match the causal graph",
        )
        evidence_inputs = tuple(
            {"role": evidence_role, "evidence_ids": tuple(binding["role_bindings"][evidence_role])}
            for evidence_role in obligations[index]["required_evidence_roles"]
            if evidence_role in binding["role_bindings"]
        )
        evidence_ids = {value for item in evidence_inputs for value in item["evidence_ids"]}
        _require(
            not evidence_ids or set(envelope["evidence_refs"]) == evidence_ids,
            "quotient.evidence",
            "evidence roles must bind the actual envelope inputs",
        )
        semantic_payload = {
            key: value
            for key, value in payload.items()
            if role != ROLES[-1] or key not in EXCLUDED_FINAL
        }
        nodes.append(
            {
                "decision_role": role,
                "action_semantic_kind": f"execute_{role}",
                "typed_evidence_inputs": evidence_inputs,
                "actual_evidence_refs": sorted(envelope["evidence_refs"]),
                "typed_claim_inputs": tuple(
                    {"producer_decision_role": parent} for parent in claim_roles
                ),
                "decision_dependencies": tuple(claim_roles),
                "produced_claim_type": obligations[index]["produced_claim_schema"],
                "public_result": _normalize(semantic_payload, producers),
            }
        )
    return _identified(
        {
            "schema_version": "qa_reasoning_multitrajectory_quotient.v1",
            "contract_id": contract["content_id"],
            "task_scope": scope,
            "decision_nodes": tuple(nodes),
            "causal_edges": tuple(
                {"from_decision": ROLES[parent], "to_decision": role}
                for index, role in enumerate(ROLES)
                for parent in PARENT_INDICES[index]
            ),
            "termination_mode": "qualified_final_answer",
        },
        "qa_reasoning_multitrajectory_quotient:",
    )


def independent_partition(
    results: Sequence[Mapping[str, Any]], projections: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Partition only within exact task identity; a cross-task class is no witness."""
    _require(
        len(results) == len(projections),
        "quotient.partition",
        "one projection per replay is required",
    )
    by_task: dict[str, list[tuple[str, str]]] = {}
    for result, projection in zip(results, projections, strict=True):
        trajectory = _admit_replay(result)
        task_id = trajectory["task_instance_id"]
        _require(
            projection["task_scope"]["task_instance_id"] == task_id,
            "quotient.partition",
            "cross-task projection substitution",
        )
        by_task.setdefault(task_id, []).append(
            (trajectory["trajectory_id"], projection["content_id"])
        )
    rows = []
    for task_id, members in sorted(by_task.items()):
        trajectory_ids = [item[0] for item in members]
        quotient_ids = [item[1] for item in members]
        count = len(set(quotient_ids))
        rows.append(
            {
                "task_id": task_id,
                "attempted_trajectories": len(members),
                "qualified_trajectories": len(members),
                "trajectory_ids": trajectory_ids,
                "distinct_trajectory_ids": len(set(trajectory_ids)),
                "quotient_ids": quotient_ids,
                "distinct_quotient_classes": count,
                "multiple_quotient_classes_witnessed": count >= 2,
                "interpretation": "local_deterministic_multiclass_witness"
                if count >= 2
                else "no_multiclass_witness_in_preregistered_schedule_family",
            }
        )
    return _identified(
        {
            "rows": rows,
            "task_count": len(rows),
            "qualified_trajectories": sum(len(group) for group in by_task.values()),
            "tasks_with_multiple_classes": sum(
                row["multiple_quotient_classes_witnessed"] for row in rows
            ),
            "cross_task_class_count_is_not_same_task_support": True,
            "model_probabilities_estimated": False,
            "schema_version": "qa_reasoning_multitrajectory_partition.v1",
        },
        "qa_reasoning_multitrajectory_partition:",
        "audit_id",
    )


def audit_quotient(
    *, candidate_files: Mapping[str, bytes], results: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Independently derive all quotient outcomes, then compare saved formal bytes."""
    contract = independent_contract()
    schedules = enumerate_schedules()
    _require(
        len(results) == 4 and len(schedules) == 2,
        "quotient.population",
        "four own replays and two DAG schedules are required",
    )
    projections = [independent_projection(result, contract) for result in results]
    partition = independent_partition(results, projections)
    for task_id in {row["task_id"] for row in partition["rows"]}:
        orders = tuple(
            tuple(result["schedule"])
            for result in results
            if _object(result["trajectory"])["task_instance_id"] == task_id
        )
        _require(
            set(orders) == set(schedules) and len(orders) == 2,
            "quotient.schedules",
            "each task must cover the two independently enumerated legal orders",
        )
    _require(
        canonical_json_bytes(contract) == candidate_files["quotient_contract.json"],
        "quotient.contract_comparison",
        "independently reconstructed rule bytes differ",
    )
    saved_projections = [
        json.loads(line) for line in candidate_files["quotient_projections.jsonl"].splitlines()
    ]
    _require(
        canonical_json_bytes(projections) == canonical_json_bytes(saved_projections),
        "quotient.projection_comparison",
        "independently projected semantic graph bytes differ",
    )
    _require(
        canonical_json_bytes(partition) == candidate_files["quotient_partition.json"],
        "quotient.partition_comparison",
        "independently derived per-task partition bytes differ",
    )
    controls = []
    changed = copy.deepcopy(contract)
    changed.pop("content_id")
    changed["outcome_selected_rule"] = "keep_schedule_to_force_two_classes"
    changed = _identified(changed, "qa_reasoning_multitrajectory_quotient_contract:")
    false_replay = dict(results[0])
    false_replay["replay_audit"] = {**_object(results[0]["replay_audit"]), "passed": False}
    reused_replay = {**results[1], "replay_audit": results[0]["replay_audit"]}
    crossed = list(projections)
    other_task = next(
        index
        for index, projection in enumerate(projections)
        if projection["task_scope"]["task_instance_id"]
        != projections[0]["task_scope"]["task_instance_id"]
    )
    crossed[0] = projections[other_task]
    for name, callback in (
        ("fully_rehashed_postoutcome_rule", lambda: independent_projection(results[0], changed)),
        ("false_own_replay", lambda: independent_projection(false_replay, contract)),
        ("other_schedule_replay_reused", lambda: independent_projection(reused_replay, contract)),
        ("cross_task_projection_substituted", lambda: independent_partition(results, crossed)),
    ):
        try:
            callback()
        except IndependentQuotientError as error:
            controls.append(
                {
                    "name": name,
                    "rejected": True,
                    "stage": error.stage,
                    "reason_sha256": strict_canonical_hash(str(error)),
                }
            )
        else:
            raise IndependentQuotientError("quotient.attack", f"control accepted: {name}")
    metamorphic = []
    for row in partition["rows"]:
        task_projections = [
            projection
            for projection in projections
            if projection["task_scope"]["task_instance_id"] == row["task_id"]
        ]
        _require(
            len(task_projections) == 2
            and canonical_json_bytes(task_projections[0])
            == canonical_json_bytes(task_projections[1]),
            "quotient.commutation_bytes",
            "same-task projection bytes differ",
        )
        _require(
            row["distinct_trajectory_ids"] == 2 and row["distinct_quotient_classes"] == 1,
            "quotient.commutation",
            "the two independent branch schedules must collapse",
        )
        metamorphic.append(
            {
                "task_id": row["task_id"],
                "distinct_trajectory_ids": 2,
                "equal_projection_bytes": True,
                "quotient_classes": 1,
            }
        )
    audit = _identified(
        {
            "schema_version": "qa_reasoning_multitrajectory_independent_quotient_audit.v1",
            "contract_id": contract["content_id"],
            "contract_actual_byte_match": True,
            "permutations_enumerated": 120,
            "dependency_edges": 5,
            "legal_schedules": schedules,
            "legal_schedule_count": len(schedules),
            "qualified_own_trajectory_projections": len(projections),
            "saved_projection_byte_matches": len(projections),
            "saved_partition_byte_match": True,
            "per_task_rows": partition["rows"],
            "distinct_cross_task_classes": len(
                {projection["content_id"] for projection in projections}
            ),
            "tasks_with_multiple_classes": partition["tasks_with_multiple_classes"],
            "schedule_commutation_metamorphic_controls": metamorphic,
            "negative_controls": controls,
            "negative_controls_rejected": len(controls),
            "negative_controls_accepted": 0,
            "fully_rehashed_rule_candidate_id": changed["content_id"],
            "candidate_helper_calls": 0,
            "candidate_outcome_oracle_calls": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "all_valid_semantic_trajectories_exhausted_claimed": False,
            "scientific_result": "two_valid_orders_one_class_per_fixed_task",
        },
        "qa_reasoning_multitrajectory_independent_quotient_audit:",
        "audit_id",
    )
    return audit, projections, partition
