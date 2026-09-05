"""Independently verify the finite projection, relation and empirical denominators.

This module reads frozen public records.  It does not import or call the projector,
pair comparator, partition builder, old qualification checker, provider or runtime.
Canonical content identities establish bindings; retained labels and role edges,
not differing hashes, establish semantic comparison.
"""

from __future__ import annotations

import copy
import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from .models import number, record, require, structural_key

KINDS = {"evidence", "action", "execution", "observation", "update", "claim", "final"}
SET_FIELDS = {
    "evidence_refs",
    "claim_refs",
    "observation_refs",
    "lineage",
    "grounding",
    "citations",
}
SCALAR = {
    "value",
    "metric",
    "definition",
    "subject",
    "scope",
    "period",
    "unit",
    "currency",
    "lineage",
}
CONTROL_STATE = {"id", "last_feedback", "submission_count", "remaining_bounds"}
EFFECT_OBJECTS = ("execution", "observation", "claim", "final")


def _identity(obj: Mapping[str, Any]) -> None:
    require(isinstance(obj, Mapping), "independent.missing_record")
    identifier = obj.get("id")
    require(isinstance(identifier, str) and ":" in identifier, "independent.missing_identity")
    assert isinstance(identifier, str)
    body = {key: value for key, value in obj.items() if key != "id"}
    require(
        strict_canonical_hash(body, prefix=identifier.split(":", 1)[0] + ":") == identifier,
        "independent.content_identity",
    )


def _plain(obj: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(
        {key: value for key, value in obj.items() if key not in {"id", "schema_version"}}
    )


def _sets(value: Any, field: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {key: _sets(item, key) for key, item in value.items()}
    if isinstance(value, list):
        items = [_sets(item) for item in value]
        return sorted(items, key=structural_key) if field in SET_FIELDS else items
    return value


def _changes(left: Any, right: Any, path: str = "") -> list[str]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return [
            changed
            for key in sorted(set(left) | set(right))
            for changed in (
                [path + "/" + key]
                if key not in left or key not in right
                else _changes(left[key], right[key], path + "/" + key)
            )
        ]
    return [] if left == right else [path]


def _proposal_deltas(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    return _changes(
        _sets({key: value for key, value in before.items() if key != "state_id"}),
        _sets({key: value for key, value in after.items() if key != "state_id"}),
    )


def _knowledge(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in state.items() if key not in CONTROL_STATE},
        "retained_action_update_bounds": {
            key: value for key, value in state["remaining_bounds"].items() if key != "submissions"
        },
    }


def _correction(events: list[dict[str, Any]], index: int) -> dict[str, Any]:
    """Re-establish C0--C4 from actual before/after records, not an error label."""
    event = events[index]
    proposal = event["submission"]["parsed"]
    pre, post = event["request"]["state"], event["post_state"]
    following_index = next(
        (j for j in range(index + 1, len(events)) if events[j]["receipt"]["admitted"]), None
    )
    following = events[following_index] if following_index is not None else None
    after = following["submission"]["parsed"] if following is not None else None
    c0 = (
        event["receipt"]["admitted"] is False
        and event["receipt"]["dispatch_permitted"] is False
        and all(event.get(key) is None for key in EFFECT_OBJECTS)
        and _knowledge(pre) == _knowledge(post)
    )
    c1 = following_index is not None and all(
        _knowledge(item["request"]["state"]) == _knowledge(pre)
        and _knowledge(item["post_state"]) == _knowledge(pre)
        and item["receipt"]["admitted"] is False
        and all(item.get(key) is None for key in EFFECT_OBJECTS)
        for item in events[index:following_index]
    )
    if following is not None:
        c1 = c1 and _knowledge(following["request"]["state"]) == _knowledge(pre)
    c2 = after is not None and after["kind"] == proposal["kind"]
    delta = _proposal_deltas(proposal, after) if after is not None else []
    c3 = False
    if c2 and after is not None:
        kind = proposal["kind"]
        if kind == "action":
            stable = {"kind", "operation", "inputs", "parameters"}
            c3 = (
                event["receipt"]["code"] == "admission.public_basis"
                and all(proposal[key] == after[key] for key in stable)
                and bool(delta)
                and all(path.startswith("/public_basis/") for path in delta)
            )
        elif kind == "update":
            observation = pre["pending_observation"]
            c3 = (
                event["receipt"]["code"] == "admission.observed_claim_content"
                and observation is not None
                and proposal["observation_id"] == after["observation_id"] == observation["id"]
                and proposal["disposition"] == after["disposition"] == "accept"
                and _sets(proposal["public_basis"]) == _sets(after["public_basis"])
                and set(proposal["proposed_claim"]) == SCALAR
                and after["proposed_claim"] == observation["output"]
                and bool(delta)
                and set(delta).issubset({"/proposed_claim/value", "/proposed_claim/definition"})
            )
        elif kind == "final":
            c3 = (
                event["receipt"]["code"] == "admission.final_grounding"
                and proposal["answer_claim_id"] == after["answer_claim_id"]
                and proposal["answer"] == after["answer"]
                and bool(delta)
                and all(path == "/citations" or path.startswith("/public_basis/") for path in delta)
            )
    c4 = (
        post["submission_count"] == pre["submission_count"] + 1
        and post["remaining_bounds"]["submissions"] == pre["remaining_bounds"]["submissions"] - 1
        and event["provider_attempt"]["provider_attempts_consumed"] == 1
        and event["provider_attempt"]["mock_attempts_consumed"] == 0
    )
    return {
        "turn_index": index,
        "following_admitted_turn_index": following_index,
        "code": event["receipt"]["code"],
        "kind": proposal["kind"],
        "checks": {
            "C0_no_effects": c0,
            "C1_knowledge_state_stable": c1,
            "C2_next_admitted_same_kind": c2,
            "C3_allowed_alignment": c3,
            "C4_budget_recorded": c4,
        },
        "changed_fields": delta,
        "before_proposal": proposal,
        "after_proposal": after,
        "parent_ids": {
            "rejected_event_id": event["event"]["id"],
            "rejected_submission_id": event["submission"]["id"],
            "rejected_receipt_id": event["receipt"]["id"],
            "pre_state_id": pre["id"],
            "post_state_id": post["id"],
            "following_event_id": following["event"]["id"] if following is not None else None,
            "following_submission_id": following["submission"]["id"]
            if following is not None
            else None,
            "following_pre_state_id": (
                following["request"]["state"]["id"] if following is not None else None
            ),
        },
        "budget_impact": {
            "provider_attempts": 1,
            "submissions": 1,
            "pre_remaining_submissions": pre["remaining_bounds"]["submissions"],
            "post_remaining_submissions": post["remaining_bounds"]["submissions"],
        },
    }


def _binding(inputs: Mapping[str, Any], rules: Mapping[str, Any]) -> dict[str, Any]:
    context = inputs["context"]
    return {
        "task_id": context["task"]["id"],
        "public_context_id": context["id"],
        "protocol_id": inputs["protocol"]["id"],
        "model_configuration_id": inputs["model_config"]["id"],
        "pilot_registration_id": inputs["pilot_registration"]["id"],
        "measurement_contract_id": rules["id"],
        "numeric": copy.deepcopy(context["numeric"]),
        "answer_schema": copy.deepcopy(context["answer_schema"]),
        "shared_obligations": copy.deepcopy(context["shared_obligations"]),
        "generation_record_is_frozen_not_an_immutable_remote_weight_claim": True,
    }


def _scalar(value: Mapping[str, Any]) -> dict[str, Any]:
    require(set(value) == SCALAR, "independent.scalar_fields")
    return {
        **{key: item for key, item in value.items() if key != "lineage"},
        "value": number(value["value"]),
    }


def _expected_graph(
    inputs: Mapping[str, Any], session: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str, str]], dict[str, dict[str, Any]]]:
    """A separate event-to-label/edge specification, with no mapper calls."""
    expected: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, str]] = []
    provenance: dict[str, dict[str, Any]] = {}

    def node(
        obj: Mapping[str, Any],
        kind: str,
        semantics: dict[str, Any],
        index: int | None,
        event: Mapping[str, Any] | None,
        record_kind: str | None = None,
    ) -> str:
        identifier = obj["id"]
        require(identifier not in expected, "independent.duplicate_actual_node")
        expected[identifier] = {"kind": kind, "semantics": semantics}
        provenance[identifier] = {
            "turn_index": index,
            "record_kind": record_kind or kind,
            "record_id": identifier,
            "event_id": event["event"]["id"] if event is not None else None,
            "submission_id": event["submission"]["id"] if event is not None else None,
        }
        return identifier

    def edge(source: str, target: str, role: str) -> None:
        edges.append((source, target, role))

    for evidence in inputs["context"]["evidence"].values():
        semantics = _plain(evidence)
        if "value" in semantics:
            semantics["value"] = number(semantics["value"])
        if "source_references" in semantics:
            semantics["source_references"] = sorted(
                semantics["source_references"], key=structural_key
            )
        node(evidence, "evidence", semantics, None, None)
    for index, event in enumerate(session["records"]["events"]):
        if not event["receipt"]["admitted"]:
            continue
        submission = event["submission"]
        parsed = submission["parsed"]
        kind = parsed["kind"]
        if kind == "action":
            operation = parsed["operation"]
            contract = inputs["context"]["operations"][operation]
            action = node(
                submission,
                "action",
                {
                    "operation": operation,
                    "operation_contract": _plain(contract),
                    "parameters": copy.deepcopy(parsed["parameters"]),
                    "public_basis": {
                        key: value
                        for key, value in parsed["public_basis"].items()
                        if key not in {"evidence_refs", "claim_refs"}
                    },
                    "field_origin": submission["field_origin"],
                },
                index,
                event,
                "submission",
            )
            execution, observation = event["execution"], event["observation"]
            require(
                execution is not None
                and observation is not None
                and event["claim"] is None
                and event["final"] is None,
                "independent.action_effect_domain",
            )
            require(
                execution["submission_id"] == submission["id"]
                and execution["generator_turn_id"] == submission["generator_turn_id"]
                and observation["action_submission_id"] == submission["id"]
                and observation["execution_id"] == execution["id"]
                and execution["operation"] == observation["operation"] == operation
                and execution["operation_contract_id"] == contract["id"],
                "independent.actual_action_producer",
            )
            resolved = []
            for operand in execution["inputs"]:
                item = {
                    key: copy.deepcopy(value)
                    for key, value in operand.items()
                    if key not in {"ref_id", "lineage"}
                }
                if "value" in item:
                    item["value"] = number(item["value"])
                resolved.append(item)
            if operation == "relation_sum":
                resolved = [
                    *sorted(
                        (item for item in resolved if item["role"] == "member"), key=structural_key
                    ),
                    *(item for item in resolved if item["role"] != "member"),
                ]
            execution_key = node(
                execution,
                "execution",
                {
                    "operation": execution["operation"],
                    "operation_contract_id": execution["operation_contract_id"],
                    "parameters": copy.deepcopy(execution["parameters"]),
                    "resolved_inputs": resolved,
                    "output": _scalar(execution["output"]),
                    "field_origin": execution["field_origin"],
                },
                index,
                event,
            )
            observation_key = node(
                observation,
                "observation",
                {
                    "operation": observation["operation"],
                    "success": observation["success"],
                    "output": _scalar(observation["output"]),
                    "field_origin": observation["field_origin"],
                },
                index,
                event,
            )
            for position, (submitted, operand) in enumerate(
                zip(parsed["inputs"], execution["inputs"], strict=True)
            ):
                require(
                    all(submitted[key] == operand[key] for key in ("kind", "role", "ref_id")),
                    "independent.executed_operand_parent",
                )
                require(
                    operand["ref_id"] in expected
                    and expected[operand["ref_id"]]["kind"] == operand["kind"],
                    "independent.actual_support_available_before_use",
                )
                slot = (
                    "any"
                    if operation == "relation_sum" and operand["role"] == "member"
                    else str(position)
                )
                edge(operand["ref_id"], action, "operand:" + operand["role"] + ":" + slot)
                edge(
                    operand["ref_id"],
                    execution_key,
                    "resolved_operand:" + operand["role"] + ":" + slot,
                )
                for identifier in operand["lineage"]:
                    edge(identifier, execution_key, "input_lineage:" + operand["role"] + ":" + slot)
            for identifier in parsed["public_basis"]["evidence_refs"]:
                edge(identifier, action, "basis_evidence")
            for identifier in parsed["public_basis"]["claim_refs"]:
                edge(identifier, action, "basis_claim")
            edge(action, execution_key, "executes_proposal")
            edge(execution_key, observation_key, "produces_observation")
            for identifier in execution["output"]["lineage"]:
                edge(identifier, execution_key, "output_lineage")
            for identifier in observation["output"]["lineage"]:
                edge(identifier, observation_key, "output_lineage")
        elif kind == "update":
            require(
                parsed["disposition"] == "accept"
                and event["claim"] is not None
                and all(event[name] is None for name in ("execution", "observation", "final")),
                "independent.unsupported_meaningful_update",
            )
            update = node(
                submission,
                "update",
                {
                    "disposition": parsed["disposition"],
                    "proposed_claim": _scalar(parsed["proposed_claim"]),
                    "public_basis": {
                        key: value
                        for key, value in parsed["public_basis"].items()
                        if key not in {"evidence_refs", "observation_refs"}
                    },
                    "field_origin": submission["field_origin"],
                },
                index,
                event,
                "submission",
            )
            claim = event["claim"]
            pending = event["request"]["state"]["pending_observation"]
            require(
                pending is not None
                and pending["id"] == parsed["observation_id"]
                and pending["id"] in expected
                and expected[pending["id"]]["kind"] == "observation"
                and parsed["proposed_claim"] == pending["output"]
                and claim["update_submission_id"] == submission["id"]
                and claim["observation_id"] == pending["id"]
                and claim["producer_operation"] == pending["operation"]
                and claim["proposition"] == parsed["proposed_claim"]
                and claim["grounding"] == parsed["proposed_claim"]["lineage"],
                "independent.actual_acceptance_causality",
            )
            claim_key = node(
                claim,
                "claim",
                {
                    "task_id": claim["task_id"],
                    "status": claim["status"],
                    "producer_operation": claim["producer_operation"],
                    "proposition": _scalar(claim["proposition"]),
                    "field_origin": claim["field_origin"],
                },
                index,
                event,
            )
            edge(parsed["observation_id"], update, "updates_observation")
            for identifier in parsed["public_basis"]["observation_refs"]:
                edge(identifier, update, "basis_observation")
            for identifier in parsed["public_basis"]["evidence_refs"]:
                edge(identifier, update, "basis_evidence")
            for identifier in parsed["proposed_claim"]["lineage"]:
                edge(identifier, update, "proposed_lineage")
            edge(update, claim_key, "accepts_claim")
            edge(claim["observation_id"], claim_key, "claim_observation")
            for identifier in claim["grounding"]:
                edge(identifier, claim_key, "grounding")
            for identifier in claim["proposition"]["lineage"]:
                edge(identifier, claim_key, "proposition_lineage")
        elif kind == "final":
            final = event["final"]
            require(
                final is not None
                and all(event[name] is None for name in ("execution", "observation", "claim")),
                "independent.final_effect_domain",
            )
            require(
                final["submission_id"] == submission["id"]
                and final["answer_claim_id"] == parsed["answer_claim_id"]
                and final["answer"] == parsed["answer"]
                and final["citations"] == parsed["citations"]
                and final["answer_claim_id"] in expected
                and expected[final["answer_claim_id"]]["kind"] == "claim"
                and event["post_state"]["terminal"] == "final_submitted"
                and event["post_state"]["phase"] == "terminal",
                "independent.actual_final_causality",
            )
            final_key = node(
                final,
                "final",
                {
                    "task_id": final["task_id"],
                    "answer": {**final["answer"], "value": number(final["answer"]["value"])},
                    "public_basis": {
                        key: value
                        for key, value in parsed["public_basis"].items()
                        if key not in {"evidence_refs", "claim_refs"}
                    },
                    "field_origin": final["field_origin"],
                    "terminal": "final_submitted",
                },
                index,
                event,
            )
            edge(final["answer_claim_id"], final_key, "answer_claim")
            for identifier in parsed["public_basis"]["claim_refs"]:
                edge(identifier, final_key, "basis_claim")
            for identifier in final["citations"]:
                edge(identifier, final_key, "citation")
            for identifier in parsed["public_basis"]["evidence_refs"]:
                edge(identifier, final_key, "basis_evidence")
        else:
            require(False, "independent.unknown_admitted_kind")
    require(
        all(source in expected and target in expected for source, target, _ in edges),
        "independent.dangling_actual_dependency",
    )
    return expected, edges, provenance


def _graph_shape(
    graph: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], Counter[tuple[str, str, str]]]:
    nodes: dict[str, dict[str, Any]] = {}
    for node in graph["nodes"]:
        require(
            set(node) == {"key", "kind", "semantics"}
            and isinstance(node["key"], str)
            and node["key"] not in nodes
            and node["kind"] in KINDS,
            "independent.graph_node_domain",
        )
        nodes[node["key"]] = {"kind": node["kind"], "semantics": node["semantics"]}
        structural_key(node["semantics"])
    edges: Counter[tuple[str, str, str]] = Counter()
    for edge in graph["edges"]:
        require(
            set(edge) == {"source", "target", "role"}
            and edge["source"] in nodes
            and edge["target"] in nodes
            and isinstance(edge["role"], str),
            "independent.graph_edge_domain",
        )
        edges[(edge["source"], edge["target"], edge["role"])] += 1
    return nodes, edges


def _verify_graph(
    inputs: Mapping[str, Any], session: Mapping[str, Any], projection: Mapping[str, Any]
) -> None:
    expected, actual_edges, expected_provenance = _expected_graph(inputs, session)
    nodes, edges = _graph_shape(projection["graph"])
    mapping = {}
    for row in projection["node_provenance"]:
        identifier = row["record_id"]
        require(
            identifier in expected and identifier not in mapping, "independent.provenance_domain"
        )
        require(
            all(row.get(key) == value for key, value in expected_provenance[identifier].items()),
            "independent.provenance_parent",
        )
        require(
            row["key"] in nodes and nodes[row["key"]] == expected[identifier],
            "independent.node_semantics",
        )
        mapping[identifier] = row["key"]
    require(
        set(mapping) == set(expected)
        and set(mapping.values()) == set(nodes)
        and len(mapping) == len(nodes),
        "independent.complete_node_coverage",
    )
    translated = Counter(
        (mapping[source], mapping[target], role) for source, target, role in actual_edges
    )
    require(edges == translated, "independent.complete_role_edge_coverage")


def _canonical_graph(graph: Mapping[str, Any], limit: int) -> tuple[dict[str, Any] | None, int]:
    """Independent finite canonicalization used solely to verify State objects."""
    nodes, edges = _graph_shape(graph)
    by_label: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for key, label in nodes.items():
        by_label[structural_key(label)].append(key)
    groups = [by_label[label] for label in sorted(by_label)]
    count = math.prod(math.factorial(len(group)) for group in groups)
    if count > limit:
        return None, count
    best: dict[str, Any] | None = None
    best_key: tuple[Any, ...] | None = None
    for combination in itertools.product(*(itertools.permutations(group) for group in groups)):
        order = tuple(key for group in combination for key in group)
        positions = {key: index for index, key in enumerate(order)}
        candidate = {
            "nodes": [copy.deepcopy(nodes[key]) for key in order],
            "edges": sorted(
                [
                    {"source": positions[source], "target": positions[target], "role": role}
                    for (source, target, role), multiplicity in edges.items()
                    for _ in range(multiplicity)
                ],
                key=structural_key,
            ),
        }
        current = structural_key(candidate)
        if best_key is None or current < best_key:
            best, best_key = candidate, current
    return best, count


def _verify_projection(
    inputs: Mapping[str, Any],
    rules: Mapping[str, Any],
    session: Mapping[str, Any],
    projection: Mapping[str, Any],
    condition: Mapping[str, Any],
) -> None:
    _identity(projection)
    declaration, qualification = session["declaration"], session["qualification"]
    require(
        projection["schema_version"] == "share_quotient_projection.v1"
        and projection["label"] == session["label"]
        and projection["session_id"] == declaration["id"]
        and projection["qualification_id"] == qualification["id"]
        and projection["session_manifest_id"] == session["records"]["manifest"]["id"]
        and projection["measurement_contract_id"] == rules["id"]
        and projection["condition"] == condition,
        "independent.projection_binding",
    )
    status = projection["status"]
    qualified = qualification["qualified"] is True
    require(
        status in ({"mapped", "undetermined"} if qualified else {"not_qualified"}),
        "independent.qualified_projection_domain",
    )
    events = session["records"]["events"]
    correction_by_index = {}
    for correction in projection["corrections"]:
        _identity(correction)
        index = correction["turn_index"]
        require(
            type(index) is int
            and 0 <= index < len(events)
            and index not in correction_by_index
            and events[index]["receipt"]["admitted"] is False,
            "independent.correction_domain",
        )
        actual = _correction(events, index)
        require(
            all(correction.get(key) == value for key, value in actual.items()),
            "independent.correction_factual_witness",
        )
        allowed = all(actual["checks"].values())
        decision = correction["decision"]
        require(
            decision == "excluded_nonqualified"
            if not qualified
            else decision == ("reduce_protocol_correction" if allowed else "undetermined"),
            "independent.correction_decision",
        )
        if qualified and not allowed:
            require(status == "undetermined", "independent.meaningful_change_erased")
        correction_by_index[index] = correction
    require(
        set(correction_by_index)
        == {index for index, event in enumerate(events) if event["receipt"]["admitted"] is False},
        "independent.complete_rejection_coverage",
    )
    decisions = projection["event_decisions"]
    require(len(decisions) == len(events), "independent.complete_event_coverage")
    for index, (event, decision) in enumerate(zip(events, decisions, strict=True)):
        correction = correction_by_index.get(index)
        expected = (
            "excluded_nonqualified"
            if not qualified
            else correction["decision"]
            if correction is not None
            else "retain_task_semantics"
        )
        require(
            decision["turn_index"] == index
            and decision["event_id"] == event["event"]["id"]
            and decision["submission_id"] == event["submission"]["id"]
            and decision["receipt_id"] == event["receipt"]["id"]
            and decision["kind"] == event["submission"]["parsed"]["kind"]
            and decision["disposition"] == expected
            and decision["correction_id"] == (correction["id"] if correction is not None else None),
            "independent.event_decision_parent",
        )
    statistics = projection["statistics"]
    require(
        statistics["historical_provider_attempts"] == qualification["provider_attempts"]
        and statistics["original_submissions"] == len(events)
        and statistics["admitted_events"] == sum(event["receipt"]["admitted"] for event in events)
        and statistics["rejections"] == len(correction_by_index)
        and statistics["reduced_corrections"]
        == sum(
            row["decision"] == "reduce_protocol_correction" for row in correction_by_index.values()
        )
        and statistics["new_provider_calls"] == statistics["new_candidate_runtime_executions"] == 0
        and projection["qualification_reused_not_reexecuted"] is True
        and projection["historical_support_description_used_as_class_authority"] is False,
        "independent.projection_accounting",
    )
    if status == "mapped":
        require(not projection["uninterpreted"], "independent.uninterpreted_mapped")
        _verify_graph(inputs, session, projection)
    elif status == "not_qualified":
        require(
            projection["graph"] is None and not projection["node_provenance"],
            "independent.failed_session_has_valid_graph",
        )
    else:
        require(bool(projection["uninterpreted"]), "independent.unknown_without_reason")


def _semantic_counters(
    graph: Mapping[str, Any],
    edge_mode: bool,
) -> tuple[Counter[tuple[Any, ...]], dict[tuple[Any, ...], dict[str, Any]]]:
    nodes, edges = _graph_shape(graph)
    counts: Counter[tuple[Any, ...]] = Counter()
    labels = {}
    if edge_mode:
        for (source, target, role), multiplicity in edges.items():
            label = {"source": nodes[source], "target": nodes[target], "role": role}
            key = structural_key(label)
            counts[key] += multiplicity
            labels[key] = label
    else:
        for label in nodes.values():
            key = structural_key(label)
            counts[key] += 1
            labels[key] = label
    return counts, labels


def _difference_rows(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    edge_mode: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left_counts, left_labels = _semantic_counters(left, edge_mode)
    right_counts, right_labels = _semantic_counters(right, edge_mode)
    return (
        sorted(
            [
                {**left_labels[key], "multiplicity": count}
                for key, count in (left_counts - right_counts).items()
            ],
            key=structural_key,
        ),
        sorted(
            [
                {**right_labels[key], "multiplicity": count}
                for key, count in (right_counts - left_counts).items()
            ],
            key=structural_key,
        ),
    )


def _verify_bijection(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    left_nodes, left_edges = _graph_shape(left)
    right_nodes, right_edges = _graph_shape(right)
    mapping = {}
    for row in rows:
        require(
            set(row) == {"left", "right"}
            and row["left"] in left_nodes
            and row["right"] in right_nodes
            and row["left"] not in mapping,
            "independent.bijection_domain",
        )
        require(
            left_nodes[row["left"]] == right_nodes[row["right"]], "independent.bijection_labels"
        )
        mapping[row["left"]] = row["right"]
    require(
        set(mapping) == set(left_nodes)
        and set(mapping.values()) == set(right_nodes)
        and len(mapping) == len(right_nodes),
        "independent.bijection_total_injective",
    )
    translated: Counter[tuple[str, str, str]] = Counter()
    for (source, target, role), count in left_edges.items():
        translated[(mapping[source], mapping[target], role)] += count
    require(translated == right_edges, "independent.bijection_all_edges")


def _verify_pairs(
    rules: Mapping[str, Any],
    qualified_ids: list[str],
    projections: dict[str, dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> tuple[dict[frozenset[str], str], dict[str, dict[str, Any] | None]]:
    expected_domain = {frozenset(pair) for pair in itertools.combinations(qualified_ids, 2)}
    relations = {}
    canonical: dict[str, dict[str, Any] | None] = {}
    permutation_counts: dict[str, int | None] = {}
    for identifier in qualified_ids:
        projection = projections[identifier]
        if projection["status"] == "mapped":
            canonical[identifier], permutation_counts[identifier] = _canonical_graph(
                projection["graph"], rules["canonical_permutation_limit"]
            )
        else:
            canonical[identifier], permutation_counts[identifier] = None, None
    for pair in pairs:
        _identity(pair)
        left, right = pair["left_session_id"], pair["right_session_id"]
        key = frozenset((left, right))
        require(key in expected_domain and key not in relations, "independent.exact_pair_domain")
        require(
            pair["schema_version"] == "share_quotient_pair.v1"
            and pair["left_projection_id"] == projections[left]["id"]
            and pair["right_projection_id"] == projections[right]["id"]
            and pair["measurement_contract_id"] == rules["id"],
            "independent.pair_binding",
        )
        relation = pair["relation"]
        require(
            relation in {"equivalent", "different_retained_semantics", "undetermined"},
            "independent.pair_relation_domain",
        )
        relations[key] = relation
        fully_mapped = projections[left]["status"] == projections[right]["status"] == "mapped"
        if not fully_mapped:
            require(relation == "undetermined", "independent.unknown_pair_filled")
        if fully_mapped:
            require(
                pair["canonical_search"]["left_permutations"] == permutation_counts[left]
                and pair["canonical_search"]["right_permutations"] == permutation_counts[right],
                "independent.canonical_search_budget",
            )
        if relation == "equivalent":
            require(pair["difference_witness"] is None, "independent.equivalence_has_difference")
            _verify_bijection(
                projections[left]["graph"], projections[right]["graph"], pair["bijection"]
            )
        elif relation == "different_retained_semantics":
            require(not pair["bijection"], "independent.difference_has_bijection")
            witness = pair["difference_witness"]
            require(
                isinstance(witness, Mapping)
                and witness["kind"] in {"node_semantic_multiset", "edge_semantic_multiset"},
                "independent.explicit_difference_required",
            )
            left_only, right_only = _difference_rows(
                projections[left]["graph"],
                projections[right]["graph"],
                witness["kind"] == "edge_semantic_multiset",
            )
            require(bool(left_only or right_only), "independent.hash_only_difference")
            require(
                sorted(witness["left_only"], key=structural_key) == left_only
                and sorted(witness["right_only"], key=structural_key) == right_only,
                "independent.retained_difference_witness",
            )
        else:
            require(
                not pair["bijection"]
                and pair["difference_witness"] is None
                and bool(pair["reason"]),
                "independent.unknown_pair_claims",
            )
    require(
        set(relations) == expected_domain and len(pairs) == 10, "independent.complete_ten_pairs"
    )
    return relations, canonical


def _verify_partition(
    condition: Mapping[str, Any],
    rules: Mapping[str, Any],
    sessions: dict[str, dict[str, Any]],
    projections: dict[str, dict[str, Any]],
    relations: dict[frozenset[str], str],
    canonical: dict[str, dict[str, Any] | None],
    partition: Mapping[str, Any],
) -> dict[str, int]:
    _identity(partition)
    qualified = [key for key, session in sessions.items() if session["qualification"]["qualified"]]
    excluded = [key for key in sessions if key not in qualified]
    require(
        partition["schema_version"] == "share_quotient_partition.v1"
        and partition["condition"] == condition
        and partition["measurement_contract_id"] == rules["id"]
        and set(partition["excluded_session_ids"]) == set(excluded)
        and len(partition["excluded_session_ids"]) == len(excluded),
        "independent.partition_binding",
    )
    reflexive = all(projections[key]["status"] == "mapped" for key in qualified)
    all_determined = all(value != "undetermined" for value in relations.values())
    transitive: bool | None = None
    if all_determined:
        transitive = all(
            relations[frozenset((a, c))] == "equivalent"
            for a, b, c in itertools.permutations(qualified, 3)
            if relations[frozenset((a, b))] == relations[frozenset((b, c))] == "equivalent"
        )
    require(
        partition["relation_checks"]
        == {
            "complete_pairs": True,
            "reflexive": reflexive,
            "symmetric": True,
            "transitive": transitive,
        },
        "independent.relation_laws",
    )
    complete = (
        reflexive
        and all_determined
        and transitive is True
        and all(canonical[key] is not None for key in qualified)
    )
    require(partition["complete"] is complete, "independent.partition_complete_definition")
    if not complete:
        require(
            not partition["classes"]
            and not partition["assignments"]
            and partition["class_count"] is None
            and set(partition["unmapped_session_ids"]) == set(qualified)
            and len(partition["unmapped_session_ids"]) == len(qualified),
            "independent.partial_partition_not_fabricated",
        )
        return {}
    require(not partition["unmapped_session_ids"], "independent.complete_partition_has_unknown")
    membership = {}
    counts = {}
    for group in partition["classes"]:
        state = group["state"]
        _identity(state)
        state_id = group["state_id"]
        representative = group["representative_session_id"]
        members = group["members"]
        require(
            state["schema_version"] == "share_quotient_quotient_state.v1"
            and state_id == state["id"]
            and state_id not in counts
            and state["condition"] == condition
            and representative in members
            and representative in qualified
            and bool(members)
            and len(members) == len(set(members))
            and state["graph"] == canonical[representative],
            "independent.quotient_state_semantics",
        )
        for member in members:
            require(
                member in qualified
                and member not in membership
                and canonical[member] == state["graph"],
                "independent.class_membership_semantics",
            )
            membership[member] = state_id
        counts[state_id] = len(members)
    require(
        set(membership) == set(qualified) and partition["class_count"] == len(counts),
        "independent.complete_class_partition",
    )
    for pair, relation in relations.items():
        left, right = tuple(pair)
        require(
            (membership[left] == membership[right]) is (relation == "equivalent"),
            "independent.partition_pair_consistency",
        )
    assigned = set()
    for assignment in partition["assignments"]:
        _identity(assignment)
        identifier = assignment["session_id"]
        require(
            identifier in membership and identifier not in assigned, "independent.assignment_domain"
        )
        session, projection = sessions[identifier], projections[identifier]
        require(
            assignment["schema_version"] == "share_quotient_assignment.v1"
            and assignment["condition"] == condition
            and assignment["state_id"] == membership[identifier]
            and assignment["projection_id"] == projection["id"]
            and assignment["qualification_id"] == session["qualification"]["id"]
            and assignment["session_manifest_id"] == session["records"]["manifest"]["id"],
            "independent.assignment_binding",
        )
        assigned.add(identifier)
    require(assigned == set(qualified), "independent.assignment_coverage")
    return counts


def _ratio(actual: Mapping[str, Any], numerator: int, denominator: int) -> None:
    require(
        type(actual["numerator"]) is int
        and type(actual["denominator"]) is int
        and actual["numerator"] == numerator
        and actual["denominator"] == denominator
        and actual["exact"] == f"{numerator}/{denominator}"
        and actual["value"] == (numerator / denominator if denominator else None),
        "independent.exact_empirical_ratio",
    )


def _verify_measurement(
    condition: Mapping[str, Any],
    sessions: dict[str, dict[str, Any]],
    partition: Mapping[str, Any],
    counts: dict[str, int],
    measurement: Mapping[str, Any],
) -> None:
    _identity(measurement)
    qualified = sum(session["qualification"]["qualified"] is True for session in sessions.values())
    mapped = sum(counts.values())
    total = len(sessions)
    require(
        measurement["schema_version"] == "share_quotient_empirical_measurement.v1"
        and measurement["condition"] == condition
        and measurement["registered_denominator"] == total == 6
        and measurement["qualified_denominator"] == measurement["qualified_count"] == qualified == 5
        and measurement["mapped_count"] == mapped
        and measurement["unmapped_count"] == qualified - mapped
        and measurement["failed_count"] == total - qualified == 1
        and measurement["complete"] is partition["complete"]
        and measurement["old_quotient_mapping"] is False
        and measurement["population_probability_claimed"] is False
        and measurement["training_target_distribution"] is False
        and measurement["new_provider_calls"] == measurement["mock_sessions_in_denominator"] == 0
        and measurement["historical_provider_attempts"]
        == sum(session["records"]["manifest"]["provider_attempts"] for session in sessions.values())
        == 51,
        "independent.empirical_domain",
    )
    _ratio(measurement["q"], qualified, total)
    _ratio(measurement["joint_total"], mapped, total)
    _ratio(measurement["conditional_total"], mapped, qualified)
    _ratio(measurement["unmapped_conditional"], qualified - mapped, qualified)
    _ratio(measurement["failure_frequency"], total - qualified, total)
    found = set()
    for frequency in measurement["state_frequencies"]:
        identifier = frequency["state_id"]
        require(
            identifier in counts
            and identifier not in found
            and frequency["count"] == counts[identifier],
            "independent.state_frequency_counts",
        )
        _ratio(frequency["joint"], counts[identifier], total)
        _ratio(frequency["conditional"], counts[identifier], qualified)
        found.add(identifier)
    require(found == set(counts), "independent.state_frequency_coverage")
    require(
        measurement["conditional_distribution"]
        == (measurement["state_frequencies"] if partition["complete"] else None),
        "independent.unknown_distribution_not_renormalized",
    )


def audit_measurement(
    inputs: dict[str, Any],
    rules: dict[str, Any],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    partition: dict[str, Any],
    measurement: dict[str, Any],
) -> dict[str, Any]:
    """Check the finite measurement without asking any model or semantic producer."""
    checks: list[str] = []
    errors: list[dict[str, str]] = []
    stage = "input_domain"
    try:
        _identity(rules)
        require(
            rules["schema_version"] == "share_quotient_measurement_contract.v1"
            and rules["denominators"]
            == {"end_to_end": 6, "joint_state_frequency": 6, "success_conditioned": 5}
            and set(rules["node_kinds"]) == KINDS
            and set(rules["set_order_fields"]) == SET_FIELDS
            and rules["canonical_permutation_limit"] == 4096
            and rules["class_count_pass_requirement"] is None
            and rules["expected_two_classes_is_a_gate"] is False
            and rules["old_quotient_state_ids_reused"] is False,
            "independent.supported_measurement_rules",
        )
        for key in ("context", "protocol", "model_config", "pilot_registration"):
            _identity(inputs[key])
        condition = _binding(inputs, rules)
        ordered = inputs["sessions"]
        require(
            len(ordered) == 6
            and [session["label"] for session in ordered]
            == [f"M{index:02d}" for index in range(1, 7)],
            "independent.exact_six_sessions",
        )
        sessions = {}
        for session in ordered:
            declaration, qualification, records = (
                session["declaration"],
                session["qualification"],
                session["records"],
            )
            for obj in (declaration, qualification, records["manifest"], records["stop"]):
                _identity(obj)
            identifier = declaration["id"]
            require(
                identifier not in sessions
                and qualification["session_id"] == identifier
                and qualification["session_manifest_id"] == records["manifest"]["id"]
                and records["manifest"]["session_id"] == identifier
                and qualification["origin"] == "model"
                and qualification["evidence_complete"] is True
                and qualification["protocol_valid"] is True
                and qualification["persisted_artifact_validation"] is True
                and qualification["qualified"]
                is (qualification["valid_final"] is True and qualification["qa_valid"] is True)
                and type(qualification["Y"]) is int
                and qualification["Y"] == int(qualification["qualified"]),
                "independent.original_qualification_binding",
            )
            manifest, stop, initial = records["manifest"], records["stop"], records["initial_state"]
            require(
                declaration["label"] == session["label"]
                and declaration["generator_origin"] == manifest["origin"] == "model"
                and declaration["protocol_id"]
                == qualification["protocol_id"]
                == manifest["protocol_id"]
                == inputs["protocol"]["id"]
                and declaration["model_configuration_id"]
                == qualification["model_configuration_id"]
                == manifest["model_configuration_id"]
                == inputs["model_config"]["id"]
                and qualification["adapter_binding_id"]
                == manifest["generator_binding_id"]
                == inputs["pilot_registration"]["adapter_binding_id"]
                and manifest["public_context_id"]
                == initial["context_id"]
                == inputs["context"]["id"]
                and all(
                    initial[key] == inputs["context"][key]
                    for key in (
                        "task",
                        "numeric",
                        "operations",
                        "evidence",
                        "answer_schema",
                        "shared_obligations",
                    )
                )
                and qualification["session_stop_id"] == stop["id"]
                and stop["session_id"] == identifier
                and qualification["terminal_reason"] == stop["terminal"]
                and stop["terminal_recorded"] is True
                and stop["state_id"] == records["events"][-1]["post_state"]["id"]
                and manifest["generator_callbacks"]
                == qualification["callback_attempts"]
                == stop["callback_attempts"]
                == len(records["events"])
                and manifest["provider_attempts"]
                == qualification["provider_attempts"]
                == stop["provider_attempts"]
                and manifest["public_submission_attempts"]
                == qualification["public_submission_attempts"]
                == stop["public_submission_attempts"],
                "independent.frozen_generation_and_stop_binding",
            )
            sessions[identifier] = session
        require(
            list(sessions) == inputs["pilot_registration"]["session_ids"]
            and [session["qualification"]["Y"] for session in ordered] == [0, 1, 1, 1, 1, 1]
            and sum(len(session["records"]["events"]) for session in ordered) == 51,
            "independent.frozen_outcome_population",
        )
        checks.append(stage)
        stage = "event_projection_and_corrections"
        by_id = {}
        for projection in projections:
            identifier = projection["session_id"]
            require(
                identifier in sessions and identifier not in by_id,
                "independent.projection_population",
            )
            _verify_projection(inputs, rules, sessions[identifier], projection, condition)
            by_id[identifier] = projection
        require(set(by_id) == set(sessions), "independent.complete_six_outcomes")
        checks.append(stage)
        stage = "ten_pair_semantic_witnesses"
        qualified_ids = [
            identifier
            for identifier, session in sessions.items()
            if session["qualification"]["qualified"]
        ]
        relations, canonical = _verify_pairs(rules, qualified_ids, by_id, pairs)
        checks.append(stage)
        stage = "relation_partition_and_assignments"
        counts = _verify_partition(
            condition, rules, sessions, by_id, relations, canonical, partition
        )
        checks.append(stage)
        stage = "empirical_denominators"
        _verify_measurement(condition, sessions, partition, counts, measurement)
        checks.append(stage)
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError, RecursionError) as error:
        errors.append({"stage": stage, "reason": str(error)})
    return record(
        "independent_validation",
        passed=not errors,
        checks=checks,
        errors=errors,
        provider_calls=0,
        credential_reads=0,
        new_candidate_runtime_executions=0,
        original_qualification_reexecuted=False,
        calls_projection_comparison_measurement_or_controls=False,
        graph_hash_used_as_semantic_authority=False,
        support_description_used_as_class_authority=False,
        private_reasoning_examined=False,
    )
