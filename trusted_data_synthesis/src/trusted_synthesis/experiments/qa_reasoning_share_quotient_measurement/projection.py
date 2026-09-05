"""Finite event interpretation with explicit, evidence-bearing correction decisions.

This module reads already-qualified saved records. It never executes a kernel,
requalifies a candidate or turns rejected proposed content into an accepted fact.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .models import (
    NONSEMANTIC_STATE_FIELDS,
    SCALAR_FIELDS,
    MeasurementError,
    condition_binding,
    measurement_contract,
    number,
    record,
    require,
    structural_key,
)

SET_FIELDS = {
    "evidence_refs",
    "claim_refs",
    "observation_refs",
    "lineage",
    "grounding",
    "citations",
}


def _sets(obj: Any, field: str = "") -> Any:
    if isinstance(obj, dict):
        return {key: _sets(value, key) for key, value in obj.items()}
    if isinstance(obj, list):
        values = [_sets(value) for value in obj]
        return sorted(values, key=structural_key) if field in SET_FIELDS else values
    return obj


def _without(obj: Mapping[str, Any], *fields: str) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in obj.items() if key not in fields}


def _scalar(obj: Mapping[str, Any]) -> dict[str, Any]:
    require(set(obj) == SCALAR_FIELDS, "projection.unsupported_scalar_fields")
    require(len(obj["lineage"]) == len(set(obj["lineage"])), "projection.duplicate_lineage")
    return {**_without(obj, "lineage", "value"), "value": number(obj["value"])}


def _knowledge(state: Mapping[str, Any]) -> dict[str, Any]:
    result = _without(state, *NONSEMANTIC_STATE_FIELDS)
    result["remaining_action_update_bounds"] = {
        key: state["remaining_bounds"][key] for key in ("actions", "updates")
    }
    return result


def _pre(records: Mapping[str, Any], index: int) -> dict[str, Any]:
    return records["initial_state"] if index == 0 else records["events"][index - 1]["post_state"]


def _deltas(left: Any, right: Any, path: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key == "state_id" and not path:
                continue
            child = path + "/" + key
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_deltas(left[key], right[key], child))
        return paths
    return [] if structural_key(left) == structural_key(right) else [path or "/"]


def _alignment(
    kind: str, before: dict[str, Any], after: dict[str, Any], state: dict[str, Any]
) -> bool:
    left, right = _sets(before), _sets(after)
    if kind == "action":
        return _without(left, "state_id", "public_basis") == _without(
            right, "state_id", "public_basis"
        )
    if kind == "update":
        pending = state["pending_observation"]
        if not pending or before["disposition"] != "accept" or after["disposition"] != "accept":
            return False
        if before["observation_id"] != pending["id"] or after["observation_id"] != pending["id"]:
            return False
        if _without(left, "state_id", "proposed_claim") != _without(
            right, "state_id", "proposed_claim"
        ):
            return False
        return _without(left["proposed_claim"], "value", "definition") == _without(
            right["proposed_claim"], "value", "definition"
        ) and right["proposed_claim"] == _sets(pending["output"])
    if kind == "final":
        if _without(left, "state_id", "citations", "public_basis") != _without(
            right, "state_id", "citations", "public_basis"
        ):
            return False
        claims = {claim["id"]: claim for claim in state["accepted_claims"]}
        claim = claims.get(after["answer_claim_id"])
        if claim is None:
            return False
        return (
            sorted(after["citations"]) == sorted(claim["grounding"])
            and sorted(after["public_basis"]["evidence_refs"]) == sorted(claim["grounding"])
            and after["public_basis"]["claim_refs"] == [claim["id"]]
        )
    return False


def correction_decision(
    records: Mapping[str, Any], index: int, rules: Mapping[str, Any], *, qualified: bool
) -> dict[str, Any]:
    """Classify one rejection only after checking the actual following event block."""
    events = records["events"]
    event = events[index]
    require(event["receipt"]["admitted"] is False, "correction.not_rejected")
    before = event["submission"]["parsed"]
    kind = before["kind"]
    state, post = _pre(records, index), event["post_state"]
    following = next(
        (j for j in range(index + 1, len(events)) if events[j]["receipt"]["admitted"]), None
    )
    after = events[following]["submission"]["parsed"] if following is not None else None
    end = following if following is not None else len(events)
    no_effects = all(
        events[j]["receipt"]["admitted"] is False
        and all(
            events[j][field] is None for field in ("execution", "observation", "claim", "final")
        )
        and all(
            events[j]["event"][field + "_id"] is None
            for field in ("execution", "observation", "claim", "final")
        )
        for j in range(index, end)
    )
    stable = all(
        _knowledge(events[j]["post_state"]) == _knowledge(state) for j in range(index, end)
    )
    same_kind = after is not None and after["kind"] == kind
    alignment = False
    if same_kind and after is not None:
        try:
            alignment = event["receipt"]["code"] in rules["reducible_receipt_codes"].get(
                kind, []
            ) and _alignment(kind, before, after, state)
        except (KeyError, TypeError, ValueError):
            alignment = False
    budget = (
        post["submission_count"] == state["submission_count"] + 1
        and post["remaining_bounds"]["submissions"] == state["remaining_bounds"]["submissions"] - 1
        and event.get("provider_attempt") is not None
    )
    checks = {
        "C0_no_effects": no_effects,
        "C1_knowledge_state_stable": stable,
        "C2_next_admitted_same_kind": same_kind,
        "C3_allowed_alignment": alignment,
        "C4_budget_recorded": budget,
    }
    decision = (
        "excluded_nonqualified"
        if not qualified
        else "reduce_protocol_correction"
        if all(checks.values())
        else "undetermined"
    )
    return record(
        "correction",
        turn_index=index,
        following_admitted_turn_index=following,
        code=event["receipt"]["code"],
        kind=kind,
        decision=decision,
        checks=checks,
        changed_fields=_deltas(_sets(before), _sets(after)) if after is not None else [],
        before_proposal=before,
        after_proposal=after,
        parent_ids={
            "rejected_event_id": event["event"]["id"],
            "rejected_submission_id": event["submission"]["id"],
            "rejected_receipt_id": event["receipt"]["id"],
            "pre_state_id": state["id"],
            "post_state_id": post["id"],
            "following_event_id": events[following]["event"]["id"]
            if following is not None
            else None,
            "following_submission_id": events[following]["submission"]["id"]
            if following is not None
            else None,
            "following_pre_state_id": _pre(records, following)["id"]
            if following is not None
            else None,
        },
        budget_impact={
            "provider_attempts": 1,
            "submissions": 1,
            "pre_remaining_submissions": state["remaining_bounds"]["submissions"],
            "post_remaining_submissions": post["remaining_bounds"]["submissions"],
        },
        raw_rejection_is_an_accepted_proposition=False,
        raw_parent_evidence_retained=True,
        correction_content_is_exact_decimal_surface_equivalence=False,
    )


class _GraphBuilder:
    def __init__(self, context: Mapping[str, Any]) -> None:
        self.context = context
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.provenance: list[dict[str, Any]] = []
        self.by_key: dict[str, dict[str, Any]] = {}
        for evidence in context["evidence"].values():
            semantics = _without(evidence, "id", "schema_version")
            semantics["source_references"] = sorted(
                semantics["source_references"], key=structural_key
            )
            if "value" in semantics:
                semantics["value"] = number(semantics["value"])
            self.node(evidence["id"], "evidence", semantics, None, "evidence", evidence["id"], None)

    def node(
        self,
        key: str,
        kind: str,
        semantics: dict[str, Any],
        index: int | None,
        record_kind: str,
        record_id: str,
        event: dict[str, Any] | None,
    ) -> None:
        require(key not in self.by_key, "projection.duplicate_node")
        node = {"key": key, "kind": kind, "semantics": semantics}
        structural_key(semantics)
        self.nodes.append(node)
        self.by_key[key] = node
        self.provenance.append(
            {
                "key": key,
                "turn_index": index,
                "record_kind": record_kind,
                "record_id": record_id,
                "event_id": event["event"]["id"] if event is not None else None,
                "submission_id": event["submission"]["id"] if event is not None else None,
            }
        )

    def edge(self, source: str, target: str, role: str) -> None:
        require(
            source in self.by_key and target in self.by_key, "projection.unavailable_dependency"
        )
        self.edges.append({"source": source, "target": target, "role": role})

    def refs(self, refs: list[str], target: str, role: str, expected_kind: str) -> None:
        require(len(refs) == len(set(refs)), "projection.duplicate_set_reference")
        for ref in refs:
            require(
                ref in self.by_key and self.by_key[ref]["kind"] == expected_kind,
                "projection.reference_kind",
            )
            self.edge(ref, target, role)

    def add_action(self, event: dict[str, Any], index: int, pre: dict[str, Any]) -> None:
        submission, execution, observation = (
            event["submission"],
            event["execution"],
            event["observation"],
        )
        proposal = submission["parsed"]
        require(
            set(proposal)
            == {"kind", "state_id", "operation", "inputs", "parameters", "public_basis"},
            "projection.action_fields",
        )
        require(
            execution is not None
            and observation is not None
            and event["claim"] is None
            and event["final"] is None,
            "projection.action_objects",
        )
        op = proposal["operation"]
        require(op in self.context["operations"], "projection.operation_unregistered")
        contract = self.context["operations"][op]
        require(
            execution["operation"] == op
            and execution["operation_contract_id"] == contract["id"]
            and execution["parameters"] == proposal["parameters"],
            "projection.action_execution_semantics",
        )
        require(
            execution["submission_id"] == submission["id"]
            and observation["execution_id"] == execution["id"]
            and observation["action_submission_id"] == submission["id"],
            "projection.action_producer",
        )
        require(
            observation["output"] == execution["output"]
            and observation["operation"] == op
            and observation["success"] is True,
            "projection.observation_content",
        )
        require(
            [i["role"] for i in proposal["inputs"]] == contract["input_roles"],
            "projection.ordered_roles",
        )
        require(len(proposal["inputs"]) == len(execution["inputs"]), "projection.input_totality")
        require(
            set(proposal["public_basis"])
            == {"relation", "evidence_refs", "claim_refs", "intended_metric"},
            "projection.action_basis_fields",
        )
        self.node(
            submission["id"],
            "action",
            {
                "operation": op,
                "operation_contract": _without(contract, "id", "schema_version"),
                "parameters": proposal["parameters"],
                "public_basis": _without(proposal["public_basis"], "evidence_refs", "claim_refs"),
                "field_origin": submission["field_origin"],
            },
            index,
            "submission",
            submission["id"],
            event,
        )
        resolved = []
        for operand in execution["inputs"]:
            item = _without(operand, "ref_id", "lineage")
            if "value" in item:
                item["value"] = number(item["value"])
            resolved.append(item)
        if op == "relation_sum":
            resolved = [*sorted(resolved[:2], key=structural_key), resolved[2]]
        self.node(
            execution["id"],
            "execution",
            {
                "operation": op,
                "operation_contract_id": execution["operation_contract_id"],
                "parameters": execution["parameters"],
                "resolved_inputs": resolved,
                "output": _scalar(execution["output"]),
                "field_origin": execution["field_origin"],
            },
            index,
            "execution",
            execution["id"],
            event,
        )
        self.node(
            observation["id"],
            "observation",
            {
                "operation": op,
                "success": observation["success"],
                "output": _scalar(observation["output"]),
                "field_origin": observation["field_origin"],
            },
            index,
            "observation",
            observation["id"],
            event,
        )
        for slot, (operand, actual) in enumerate(
            zip(proposal["inputs"], execution["inputs"], strict=True)
        ):
            require(
                set(operand) == {"kind", "ref_id", "role"}
                and all(actual[k] == operand[k] for k in operand),
                "projection.actual_input_binding",
            )
            require(operand["kind"] in {"evidence", "claim"}, "projection.operand_kind")
            require(
                self.by_key.get(operand["ref_id"], {}).get("kind") == operand["kind"],
                "projection.unaccepted_operand",
            )
            if operand["kind"] == "claim":
                require(
                    operand["ref_id"] in {c["id"] for c in pre["accepted_claims"]},
                    "projection.claim_not_preaccepted",
                )
            position = "any" if op == "relation_sum" and operand["role"] == "member" else str(slot)
            suffix = operand["role"] + ":" + position
            self.edge(operand["ref_id"], submission["id"], "operand:" + suffix)
            self.edge(operand["ref_id"], execution["id"], "resolved_operand:" + suffix)
            self.refs(actual["lineage"], execution["id"], "input_lineage:" + suffix, "evidence")
        self.refs(
            proposal["public_basis"]["evidence_refs"],
            submission["id"],
            "basis_evidence",
            "evidence",
        )
        self.refs(proposal["public_basis"]["claim_refs"], submission["id"], "basis_claim", "claim")
        self.edge(submission["id"], execution["id"], "executes_proposal")
        self.edge(execution["id"], observation["id"], "produces_observation")
        self.refs(execution["output"]["lineage"], execution["id"], "output_lineage", "evidence")
        self.refs(observation["output"]["lineage"], observation["id"], "output_lineage", "evidence")
        require(
            event["post_state"]["pending_observation"] == observation
            and event["post_state"]["accepted_claims"] == pre["accepted_claims"],
            "projection.action_implicit_acceptance",
        )

    def add_update(self, event: dict[str, Any], index: int, pre: dict[str, Any]) -> None:
        submission, claim = event["submission"], event["claim"]
        proposal = submission["parsed"]
        require(
            set(proposal)
            == {
                "kind",
                "state_id",
                "observation_id",
                "disposition",
                "proposed_claim",
                "public_basis",
            },
            "projection.update_fields",
        )
        require(proposal["disposition"] == "accept", "projection.meaningful_reject_not_erased")
        observation = pre["pending_observation"]
        require(
            observation is not None and proposal["observation_id"] == observation["id"],
            "projection.update_observation_target",
        )
        require(
            claim is not None
            and event["execution"] is None
            and event["observation"] is None
            and event["final"] is None,
            "projection.update_objects",
        )
        require(
            _sets(proposal["proposed_claim"])
            == _sets(observation["output"])
            == _sets(claim["proposition"]),
            "projection.explicit_complete_acceptance",
        )
        require(
            claim["observation_id"] == observation["id"]
            and claim["update_submission_id"] == submission["id"]
            and claim["status"] == "accepted",
            "projection.claim_update_causality",
        )
        require(
            set(proposal["public_basis"]) == {"relation", "evidence_refs", "observation_refs"},
            "projection.update_basis_fields",
        )
        self.node(
            submission["id"],
            "update",
            {
                "disposition": proposal["disposition"],
                "proposed_claim": _scalar(proposal["proposed_claim"]),
                "public_basis": _without(
                    proposal["public_basis"], "evidence_refs", "observation_refs"
                ),
                "field_origin": submission["field_origin"],
            },
            index,
            "submission",
            submission["id"],
            event,
        )
        self.node(
            claim["id"],
            "claim",
            {
                "task_id": claim["task_id"],
                "status": claim["status"],
                "producer_operation": claim["producer_operation"],
                "proposition": _scalar(claim["proposition"]),
                "field_origin": claim["field_origin"],
            },
            index,
            "claim",
            claim["id"],
            event,
        )
        self.edge(observation["id"], submission["id"], "updates_observation")
        self.refs(
            proposal["public_basis"]["observation_refs"],
            submission["id"],
            "basis_observation",
            "observation",
        )
        self.refs(
            proposal["public_basis"]["evidence_refs"],
            submission["id"],
            "basis_evidence",
            "evidence",
        )
        self.refs(
            proposal["proposed_claim"]["lineage"], submission["id"], "proposed_lineage", "evidence"
        )
        self.edge(submission["id"], claim["id"], "accepts_claim")
        self.edge(observation["id"], claim["id"], "claim_observation")
        self.refs(claim["grounding"], claim["id"], "grounding", "evidence")
        self.refs(claim["proposition"]["lineage"], claim["id"], "proposition_lineage", "evidence")
        require(
            event["post_state"]["pending_observation"] is None
            and event["post_state"]["accepted_claims"] == [*pre["accepted_claims"], claim],
            "projection.meaningful_claim_revision_not_erased",
        )

    def add_final(self, event: dict[str, Any], index: int, pre: dict[str, Any]) -> None:
        submission, final = event["submission"], event["final"]
        proposal = submission["parsed"]
        require(
            set(proposal)
            == {"kind", "state_id", "answer_claim_id", "answer", "citations", "public_basis"},
            "projection.final_fields",
        )
        require(
            final is not None
            and all(event[k] is None for k in ("execution", "observation", "claim")),
            "projection.final_objects",
        )
        require(
            all(proposal[k] == final[k] for k in ("answer_claim_id", "answer", "citations")),
            "projection.final_proposal_binding",
        )
        require(
            proposal["answer_claim_id"] in {claim["id"] for claim in pre["accepted_claims"]},
            "projection.final_unaccepted_claim",
        )
        require(
            set(proposal["public_basis"]) == {"relation", "evidence_refs", "claim_refs"},
            "projection.final_basis_fields",
        )
        self.node(
            final["id"],
            "final",
            {
                "task_id": final["task_id"],
                "answer": {**final["answer"], "value": number(final["answer"]["value"])},
                "public_basis": _without(proposal["public_basis"], "evidence_refs", "claim_refs"),
                "field_origin": final["field_origin"],
                "terminal": "final_submitted",
            },
            index,
            "final",
            final["id"],
            event,
        )
        self.edge(final["answer_claim_id"], final["id"], "answer_claim")
        self.refs(proposal["public_basis"]["claim_refs"], final["id"], "basis_claim", "claim")
        self.refs(
            proposal["public_basis"]["evidence_refs"], final["id"], "basis_evidence", "evidence"
        )
        self.refs(final["citations"], final["id"], "citation", "evidence")
        require(
            event["post_state"]["accepted_claims"] == pre["accepted_claims"]
            and event["post_state"]["phase"] == "terminal"
            and event["post_state"]["terminal"] == "final_submitted",
            "projection.final_state",
        )


def project_session(
    inputs: Mapping[str, Any], session: Mapping[str, Any], rules: Mapping[str, Any]
) -> dict[str, Any]:
    require(rules == measurement_contract(), "projection.rules_substitution")
    audit, records = session["qualification"], session["records"]
    require(
        audit["session_id"] == session["declaration"]["id"]
        and audit["session_manifest_id"] == records["manifest"]["id"],
        "projection.qualification_binding",
    )
    qualified = audit["qualified"] is True and audit["Y"] == 1
    require(
        audit["evidence_complete"] is True and audit["protocol_valid"] is True,
        "projection.unclosed_input",
    )
    if qualified:
        require(
            audit["qa_valid"] is True and audit["valid_final"] is True,
            "projection.invalid_qualified_input",
        )
    graph = _GraphBuilder(inputs["context"]) if qualified else None
    corrections, decisions, uninterpreted = [], [], []
    for index, event in enumerate(records["events"]):
        proposal = event["submission"]["parsed"]
        correction = None
        if not event["receipt"]["admitted"]:
            correction = correction_decision(records, index, rules, qualified=qualified)
            corrections.append(correction)
            disposition = correction["decision"]
            if disposition == "undetermined":
                uninterpreted.append(
                    {"turn_index": index, "code": "projection.unexplained_rejection_causality"}
                )
        elif not qualified:
            disposition = "excluded_nonqualified"
        else:
            disposition = "retain_task_semantics"
            try:
                assert graph is not None
                pre = _pre(records, index)
                require(
                    proposal["state_id"] == pre["id"]
                    and event["event"]["pre_state_id"] == pre["id"],
                    "projection.pre_action_state",
                )
                kind = proposal["kind"]
                require(kind in {"action", "update", "final"}, "projection.unknown_event_kind")
                getattr(graph, "add_" + kind)(event, index, pre)
            except (MeasurementError, KeyError, TypeError, IndexError) as error:
                disposition = "undetermined"
                uninterpreted.append(
                    {
                        "turn_index": index,
                        "code": getattr(error, "code", "projection.unsupported_event"),
                    }
                )
        decisions.append(
            {
                "turn_index": index,
                "event_id": event["event"]["id"],
                "submission_id": event["submission"]["id"],
                "receipt_id": event["receipt"]["id"],
                "kind": proposal["kind"],
                "disposition": disposition,
                "correction_id": correction["id"] if correction else None,
            }
        )
    if qualified and graph is not None:
        final_count = sum(node["kind"] == "final" for node in graph.nodes)
        if final_count != 1:
            uninterpreted.append({"turn_index": None, "code": "projection.final_totality"})
    return record(
        "projection",
        label=session["label"],
        session_id=session["declaration"]["id"],
        qualification_id=audit["id"],
        session_manifest_id=records["manifest"]["id"],
        measurement_contract_id=rules["id"],
        condition=condition_binding(inputs, rules),
        status="not_qualified" if not qualified else "undetermined" if uninterpreted else "mapped",
        graph={"nodes": graph.nodes, "edges": graph.edges} if graph is not None else None,
        node_provenance=graph.provenance if graph is not None else [],
        event_decisions=decisions,
        corrections=corrections,
        uninterpreted=uninterpreted,
        statistics={
            "historical_provider_attempts": audit["provider_attempts"],
            "original_submissions": len(records["events"]),
            "admitted_events": sum(e["receipt"]["admitted"] for e in records["events"]),
            "rejections": len(corrections),
            "reduced_corrections": sum(
                c["decision"] == "reduce_protocol_correction" for c in corrections
            ),
            "new_provider_calls": 0,
            "new_candidate_runtime_executions": 0,
        },
        qualification_reused_not_reexecuted=True,
        historical_support_description_used_as_class_authority=False,
    )
