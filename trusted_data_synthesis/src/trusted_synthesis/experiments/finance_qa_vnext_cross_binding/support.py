"""Actual support on a new role-bound instance, read from saved effects only."""

from __future__ import annotations

from typing import Any

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import record, require


def _one(values, predicate, code):
    found = [value for value in values if predicate(value)]
    require(len(found) == 1, "cross_binding_support." + code)
    return found[0]


def _node_trace(node_id, nodes, bindings, events):
    node = nodes[node_id]
    binding = _one(bindings, lambda item: item["node_id"] == node_id, "node_binding")
    action = _one(
        events,
        lambda item: item["submission"]["id"] == binding["action_submission_id"],
        "action_event",
    )
    update = _one(
        events,
        lambda item: item["submission"]["id"] == binding["update_submission_id"],
        "update_event",
    )
    execution, observation, claim = action["execution"], action["observation"], update["claim"]
    require(
        action["receipt"]["admitted"] is True
        and action["parsed"]["kind"] == "action"
        and execution["success"] is True
        and execution["id"] == binding["execution_id"] == observation["execution_id"]
        and execution["action_submission_id"] == action["submission"]["id"]
        and action["parsed"]["operation"]
        == execution["operation"]
        == node["operation"]
        == observation["selected_action"]["operation"]
        and observation["id"] == binding["observation_id"] == claim["observation_id"]
        and update["receipt"]["admitted"] is True
        and update["parsed"]["kind"] == "update"
        and update["parsed"]["disposition"] == "accept"
        and claim["status"] == "accepted"
        and claim["id"] == binding["accepted_claim_id"]
        and update["request"]["state"]["pending_observation"]["id"] == observation["id"]
        and claim["proposition"]
        == observation["proposition"]
        == node["proposition"]
        == execution["proposition"]
        and action["sequence"] == binding["sequence"] < update["sequence"],
        "cross_binding_support.actual_execution_explicit_update_claim_chain",
    )
    return {"node": node, "binding": binding, "action": action, "update": update, "claim": claim}


def _input(trace, role):
    return _one(trace["node"]["inputs"], lambda item: item["role"] == role, "graph_input_role")


def _resolved(trace, role):
    return _one(
        trace["action"]["execution"]["resolved_inputs"],
        lambda item: item["value"]["role"] == role,
        "resolved_input_role",
    )


def _consume(consumer, role, producer):
    graph_ref = _input(consumer, role)
    raw_ref = _one(
        consumer["action"]["parsed"]["inputs"],
        lambda item: item["role"] == role,
        "actual_input_role",
    )
    resolved = _resolved(consumer, role)
    claim = producer["claim"]
    require(
        graph_ref["kind"] == raw_ref["kind"] == resolved["value"]["kind"] == "claim"
        and graph_ref["reference"] == {"producer_action": producer["node"]["node_id"]}
        and raw_ref["ref_id"] == resolved["ref_id"] == resolved["value"]["ref_id"] == claim["id"]
        and resolved["value"]["producer_operation"] == producer["node"]["operation"]
        and resolved["value"]["value"] == claim["proposition"]["output"]["value"]
        and producer["node"]["node_id"] in consumer["node"]["input_dependencies"]
        and producer["update"]["sequence"] < consumer["action"]["sequence"]
        and any(
            item == claim for item in consumer["action"]["request"]["state"]["accepted_claims"]
        ),
        "cross_binding_support.actual_accepted_claim_consumption",
    )


def _trace_reference(trace):
    return {
        "node_id": trace["node"]["node_id"],
        "operation": trace["node"]["operation"],
        "action_submission_id": trace["action"]["submission"]["id"],
        "execution_id": trace["action"]["execution"]["id"],
        "observation_id": trace["action"]["observation"]["id"],
        "update_submission_id": trace["update"]["submission"]["id"],
        "accepted_claim_id": trace["claim"]["id"],
        "action_sequence": trace["action"]["sequence"],
        "update_sequence": trace["update"]["sequence"],
    }


def actual_support(entry: dict[str, Any], projection: dict[str, Any]) -> dict[str, Any]:
    """Read the actual Final <- percent <- ratio <- denominator path, never a route label."""
    q, reg, session = (entry[key] for key in ("qualification", "registration", "session"))
    fields = dict(
        label=entry["label"],
        profile=reg["profile"],
        profile_id=reg["profile_id"],
        model_configuration_id=reg["model_configuration_id"],
        qualification_id=q["id"],
        registration_id=reg["id"],
        session_id=q["session_id"],
        base_anchor_id=projection["id"],
        task_id=reg["task_id"],
        context_id=reg["context_id"],
        qualification_status=q["status"],
        qualified=q["qualified"],
        source_actual_graph_id=projection["source_actual_graph_id"],
        classification_uses_profile_name=False,
        operation_execution_or_qualification_calls=0,
    )
    if q["qualified"] is not True:
        return record(
            "cross_binding_support",
            **fields,
            support="ineligible",
            proof_verified=False,
            reason="not independently Qualified",
            trace=None,
        )
    trace: dict[str, Any] = {}
    try:
        graph = q["domain_audit"]["actual_decision_graph"]
        base = q["domain_audit"]["finite_projection"]
        nodes = {node["node_id"]: node for node in graph["nodes"]}
        require(len(nodes) == len(graph["nodes"]), "cross_binding_support.unique_nodes")
        events, bindings = session["events"], graph["event_bindings"]
        percent = _node_trace(
            base["final"]["answer_producer"]["producer_action"], nodes, bindings, events
        )
        require(
            percent["node"]["operation"] == "scale_percent",
            "cross_binding_support.final_percent_producer",
        )
        final = _one(
            events,
            lambda event: event["submission"]["id"] == session["final"]["submission_id"],
            "final_event",
        )
        require(
            final["receipt"]["admitted"] is True
            and final["parsed"]["kind"] == "final"
            and final["parsed"]["answer_claim_id"]
            == session["final"]["answer"]["answer_claim_id"]
            == percent["claim"]["id"]
            and percent["update"]["sequence"] < final["sequence"]
            and any(
                claim == percent["claim"] for claim in final["request"]["state"]["accepted_claims"]
            )
            and base["final"]["result"] == session["final"]["answer"]["result"],
            "cross_binding_support.actual_final_claim_consumption",
        )
        ratio_ref = _input(percent, "ratio")
        require(ratio_ref["kind"] == "claim", "cross_binding_support.percent_input_is_claim")
        ratio = _node_trace(ratio_ref["reference"]["producer_action"], nodes, bindings, events)
        require(
            ratio["node"]["operation"] == "share_ratio",
            "cross_binding_support.actual_ratio_producer",
        )
        _consume(percent, "ratio", ratio)
        denominator = _input(ratio, "denominator")
        evidence = ratio["action"]["request"]["context"]["evidence"]
        trace.update(
            percent=_trace_reference(percent),
            ratio=_trace_reference(ratio),
            final_submission_id=final["submission"]["id"],
            actual_denominator=denominator,
            actual_resolved_denominator=_resolved(ratio, "denominator"),
        )
        if denominator["kind"] == "evidence":
            raw = _one(
                ratio["action"]["parsed"]["inputs"],
                lambda item: item["role"] == "denominator",
                "denominator_role",
            )
            resolved = _resolved(ratio, "denominator")
            require(
                denominator["reference"] == {"evidence_id": evidence["disclosed_total"]["id"]}
                and raw["kind"] == resolved["value"]["kind"] == "evidence"
                and raw["ref_id"]
                == resolved["ref_id"]
                == resolved["value"]["ref_id"]
                == evidence["disclosed_total"]["id"]
                and resolved["value"]["value"] == evidence["disclosed_total"]["value"],
                "cross_binding_support.actual_disclosed_total_evidence",
            )
            support = "disclosed_total"
            trace["disclosed_total_evidence_id"] = evidence["disclosed_total"]["id"]
            trace["sum_operation_presence_is_reconstructed_support"] = False
        elif denominator["kind"] == "claim":
            total = _node_trace(
                denominator["reference"]["producer_action"], nodes, bindings, events
            )
            require(
                total["node"]["operation"] == "relation_sum"
                and total["claim"]["obligation_id"] == "total",
                "cross_binding_support.total_is_actual_relation_sum",
            )
            _consume(ratio, "denominator", total)
            operands = total["action"]["parsed"]["inputs"]
            require(
                {
                    item["ref_id"]
                    for item in operands
                    if item["role"] == "member" and item["kind"] == "evidence"
                }
                == set(evidence["composition_relation"]["member_ids"])
                and _one(operands, lambda item: item["role"] == "relation", "sum_relation")[
                    "ref_id"
                ]
                == evidence["composition_relation"]["id"],
                "cross_binding_support.public_members_and_relation",
            )
            support = "reconstructed_total"
            trace["total"] = _trace_reference(total)
            trace["accepted_total_claim_actually_consumed_by_ratio"] = True
        else:
            raise ProtocolError("cross_binding_support.unsupported_denominator_kind")
        return record(
            "cross_binding_support",
            **fields,
            support=support,
            proof_verified=True,
            reason=None,
            trace=trace,
        )
    except (ProtocolError, KeyError, TypeError, ValueError, IndexError, StopIteration) as error:
        return record(
            "cross_binding_support",
            **fields,
            support="other_or_undetermined",
            proof_verified=False,
            reason=str(error),
            trace=trace,
        )
