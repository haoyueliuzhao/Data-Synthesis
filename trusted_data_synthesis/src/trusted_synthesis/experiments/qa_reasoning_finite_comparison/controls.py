"""Isolated projection controls; these are never additional Qualified traces."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .comparison import (
    DIFFERENT,
    EQUIVALENT,
    UNDETERMINED,
    compare_graphs,
    partition_task,
)
from .projection import transparent_lookup_check


def _copy(graph: Mapping[str, Any], name: str) -> dict[str, Any]:
    projected = deepcopy(dict(graph))
    projected.setdefault("audit", {})["projection_unit_control"] = name
    projected["admission"]["control_only"] = True
    projected["admission"]["basis"] = "isolated_projection_fixture_not_new_qualified_trajectory"
    return projected


def _final_semantics(graph: Mapping[str, Any]) -> list[Any]:
    return [deepcopy(node["attrs"]) for node in graph["nodes"] if node["kind"] == "final"]


def _find_field(value: Any, field: str, path: str = "attrs") -> tuple[dict[str, Any], str] | None:
    if isinstance(value, dict):
        if field in value:
            return value, f"{path}.{field}"
        for key, child in value.items():
            found = _find_field(child, field, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_field(child, field, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _first_decimal(value: Any, path: str = "attrs") -> tuple[dict[str, Any], str] | None:
    if isinstance(value, dict):
        if value.get("numeric_type") == "exact_decimal":
            return value, f"{path}.value"
        for key, child in value.items():
            found = _first_decimal(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _first_decimal(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _rename_ids(graph: Mapping[str, Any]) -> dict[str, Any]:
    renamed = _copy(graph, "consistent_id_renaming")
    mapping = {
        node["id"]: f"projection-control-node-{index:03d}"
        for index, node in enumerate(reversed(renamed["nodes"]))
    }
    for node in renamed["nodes"]:
        node["id"] = mapping[node["id"]]
    for edge in renamed["edges"]:
        edge["source"] = mapping[edge["source"]]
        edge["target"] = mapping[edge["target"]]
    renamed["audit"]["id_renaming"] = mapping
    return renamed


def run_projection_controls(
    graphs: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Exercise rule risks by copying actual projections, without any Runtime."""
    cases: list[dict[str, Any]] = []
    if "F1" not in graphs or "B" not in graphs["F1"]:
        return {
            "schema": "finite_projection_unit_controls.v1",
            "passed": False,
            "cases": [],
            "issues": ["F1/B actual projection required"],
            "new_qualified_trajectories": 0,
            "provider_calls": 0,
        }
    base = graphs["F1"]["B"]

    def record(
        name: str,
        group: str,
        left: Mapping[str, Any],
        right: Mapping[str, Any],
        expected: str | None,
        **kwargs: Any,
    ) -> None:
        result = compare_graphs(left, right, **kwargs)
        correct = result["status"] == expected
        if expected == DIFFERENT:
            correct = correct and bool(result["retained_differences"])
        if expected == EQUIVALENT:
            proof = result.get("correspondence") or {}
            correct = correct and all(
                proof.get(field) is True
                for field in (
                    "complete_node_bijection_verified",
                    "all_node_attributes_verified",
                    "all_directed_edges_forward_verified",
                    "all_directed_edges_backward_verified",
                )
            )
        cases.append(
            {
                "name": name,
                "group": group,
                "expected": expected,
                "observed": result["status"],
                "passed": bool(correct),
                "final_semantics_unchanged": _final_semantics(left) == _final_semantics(right),
                "control_scope": "isolated_projection_unit_control",
                "qualified_trajectory": False,
                "comparison": result,
            }
        )

    record(
        "consistent_node_and_edge_id_renaming",
        "operational_invariance",
        base,
        _rename_ids(base),
        EQUIVALENT,
    )
    relabelled = _copy(base, "pure_route_label")
    relabelled["audit"]["route_label"] = "decorative-route-label-with-no-semantic-authority"
    relabelled["audit"]["group"] = "not-a-new-candidate"
    record("pure_route_label", "operational_invariance", base, relabelled, EQUIVALENT)
    reordered = _copy(base, "serialization_order")
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    record("graph_serialization_order", "operational_invariance", base, reordered, EQUIVALENT)
    for fixture_id in ("F1", "F2"):
        if {"B", "C"} <= set(graphs.get(fixture_id, {})):
            record(
                f"{fixture_id}_actual_independent_growth_schedule",
                "operational_invariance",
                graphs[fixture_id]["B"],
                graphs[fixture_id]["C"],
                EQUIVALENT,
            )

    changed_source = _copy(base, "same_answer_changed_source")
    evidence = next((node for node in changed_source["nodes"] if node["kind"] == "evidence"), None)
    source_field = None if evidence is None else _find_field(evidence["attrs"], "source_id")
    if source_field is None or evidence is None:
        cases.append(
            {
                "name": "same_answer_changed_evidence_source",
                "group": "retained_difference",
                "passed": False,
                "issues": ["actual retained Evidence source_id not located"],
            }
        )
    else:
        source_field[0]["source_id"] = (
            str(source_field[0]["source_id"]) + ":isolated-projection-control"
        )
        record(
            "same_answer_changed_evidence_source",
            "retained_difference",
            base,
            changed_source,
            DIFFERENT,
        )
        cases[-1]["mutation_path"] = f"nodes[{evidence['id']}].{source_field[1]}"

    changed_roles = _copy(base, "same_answer_ordered_roles")
    reference = next(
        (
            e
            for e in changed_roles["edges"]
            if e["kind"] == "operand" and e["role"] == "reference_percent"
        ),
        None,
    )
    observed = next(
        (
            e
            for e in changed_roles["edges"]
            if e["kind"] == "operand"
            and e["role"] == "observed_percent"
            and (reference is None or e["target"] == reference["target"])
        ),
        None,
    )
    if reference is None or observed is None:
        cases.append(
            {
                "name": "same_answer_changed_ordered_roles",
                "group": "retained_difference",
                "passed": False,
                "issues": ["actual signed gap ordered input edges not located"],
            }
        )
    else:
        reference["role"], observed["role"] = observed["role"], reference["role"]
        record(
            "same_answer_changed_ordered_roles",
            "retained_difference",
            base,
            changed_roles,
            DIFFERENT,
        )
        cases[-1]["mutation_path"] = f"operand_edges[target={reference['target']}].role"

    decimal_left, decimal_equal, decimal_different = (
        _copy(base, name)
        for name in (
            "high_precision_decimal_base",
            "high_precision_decimal_surface",
            "high_precision_decimal_difference",
        )
    )
    values = [
        _first_decimal(graph["nodes"]) for graph in (decimal_left, decimal_equal, decimal_different)
    ]
    if any(value is None for value in values):
        cases.append(
            {
                "name": "exact_decimal_precision",
                "group": "retained_difference",
                "passed": False,
                "issues": ["explicit exact decimal semantic field not located"],
            }
        )
    else:
        for item, value in zip(
            values,
            (
                "1.123456789012345678901234567890123456789",
                "1.123456789012345678901234567890123456789000",
                "1.123456789012345678901234567890123456788",
            ),
            strict=True,
        ):
            assert item is not None
            item[0]["value"] = value
        record(
            "exact_decimal_trailing_zero_surface",
            "operational_invariance",
            decimal_left,
            decimal_equal,
            EQUIVALENT,
        )
        record(
            "exact_decimal_beyond_28_digits_difference",
            "retained_difference",
            decimal_left,
            decimal_different,
            DIFFERENT,
        )

    reductions = base.get("normalization", {}).get("reductions", [])
    facts = next(
        (
            row.get("facts")
            for row in reductions
            if isinstance(row, Mapping) and isinstance(row.get("facts"), Mapping)
        ),
        None,
    )
    if facts is None:
        cases.append(
            {
                "name": "transparent_with_extra_retained_effect",
                "group": "transparent_effect_guard",
                "passed": False,
                "issues": ["actual transparent lookup condition witness missing"],
            }
        )
    else:
        original = transparent_lookup_check(facts)
        changed = deepcopy(facts)
        # Mutate the actual State witness, and let the checker recompute effects.
        # No summary condition flags are set by this control.
        changed["no_extra_retained_effects"]["after_state"]["additional_validation_outcome"] = {
            "conclusion": "control-only-new-knowledge",
            "retained": True,
        }
        guarded = transparent_lookup_check(changed)
        cases.append(
            {
                "name": "transparent_with_extra_retained_effect",
                "group": "transparent_effect_guard",
                "expected": "ineligible_or_undetermined",
                "observed": guarded,
                "passed": original.get("eligible") is True and guarded.get("eligible") is not True,
                "control_scope": "isolated_transparent_lookup_rule_witness_control",
                "qualified_trajectory": False,
                "original_check": original,
                "mutated_actual_condition_input": changed,
                "condition_recomputed_from_actual_state": True,
                "mutation_path": (
                    "no_extra_retained_effects.after_state.additional_validation_outcome"
                ),
            }
        )

    unknown = _copy(base, "unsupported_node_kind")
    unknown["nodes"][0]["kind"] = "unregistered_public_behavior_structure"
    record("unsupported_structure", "unknown_or_missing", base, unknown, UNDETERMINED)
    missing = _copy(base, "missing_required_semantics")
    missing_evidence = next(node for node in missing["nodes"] if node["kind"] == "evidence")
    del missing_evidence["attrs"]["record"]
    record("missing_required_evidence_record", "unknown_or_missing", base, missing, UNDETERMINED)

    missing_version = _copy(base, "missing_operation_semantic_version")
    operation = next(node for node in missing_version["nodes"] if node["kind"] == "operation")
    del operation["attrs"]["contract"]["semantic_version"]
    record(
        "missing_nested_operation_version",
        "unknown_or_missing",
        base,
        missing_version,
        UNDETERMINED,
    )
    missing_claim_role = _copy(base, "missing_claim_semantic_role")
    claim = next(
        node
        for node in missing_claim_role["nodes"]
        if node["kind"] == "claim" and node["attrs"]["semantic"]["kind"] == "growth_percent"
    )
    del claim["attrs"]["semantic"]["earlier_role"]
    record(
        "missing_nested_claim_operand_role",
        "unknown_or_missing",
        base,
        missing_claim_role,
        UNDETERMINED,
    )
    missing_selector = _copy(base, "missing_operand_selector")
    operand = next(edge for edge in missing_selector["edges"] if edge["kind"] == "operand")
    del operand["attrs"]["selector"]
    record(
        "missing_nested_operand_selector",
        "unknown_or_missing",
        base,
        missing_selector,
        UNDETERMINED,
    )
    unknown_attrs = _copy(base, "unknown_typed_decision_field")
    decision = next(node for node in unknown_attrs["nodes"] if node["kind"] == "decision")
    decision["attrs"]["unregistered_public_reasoning"] = "must not silently disappear"
    record(
        "unsupported_retained_attribute", "unknown_or_missing", base, unknown_attrs, UNDETERMINED
    )

    unsupported_schema = _copy(base, "unsupported_schema")
    unsupported_schema["schema"] = "unregistered_graph_schema.v999"
    record("unsupported_schema", "unknown_or_missing", base, unsupported_schema, UNDETERMINED)
    missing_normalization = _copy(base, "missing_normalization")
    missing_normalization["normalization"] = None
    record(
        "missing_normalization_record",
        "unknown_or_missing",
        base,
        missing_normalization,
        UNDETERMINED,
    )
    record(
        "unfinished_finite_search",
        "unknown_or_missing",
        base,
        _rename_ids(base),
        UNDETERMINED,
        max_search_states=0,
    )
    rejected = _copy(base, "input_not_admitted")
    rejected["admission"] = {
        "admitted": False,
        "issues": ["projection control: input failed own qualification"],
    }
    record("unadmitted_input_not_a_new_class", "unknown_or_missing", base, rejected, None)

    unresolved = partition_task(
        [
            {"left_group": "B", "right_group": "C", "status": EQUIVALENT},
            {"left_group": "B", "right_group": "A", "status": UNDETERMINED},
            {"left_group": "A", "right_group": "C", "status": UNDETERMINED},
        ]
    )
    contradictory = partition_task(
        [
            {"left_group": "B", "right_group": "C", "status": EQUIVALENT},
            {"left_group": "B", "right_group": "A", "status": EQUIVALENT},
            {"left_group": "A", "right_group": "C", "status": DIFFERENT},
        ]
    )
    for name, partition_result in (
        ("undetermined_relation_keeps_class_count_null", unresolved),
        ("contradictory_relation_cannot_form_partition", contradictory),
    ):
        cases.append(
            {
                "name": name,
                "group": "unknown_or_missing",
                "expected": "class_count_null",
                "passed": partition_result["formal_semantic_class_count"] is None
                and not partition_result["complete"],
                "observed": partition_result,
                "control_scope": "isolated_relation_unit_control",
                "qualified_trajectory": False,
            }
        )
    group_names = (
        "operational_invariance",
        "retained_difference",
        "transparent_effect_guard",
        "unknown_or_missing",
    )
    groups = [
        {
            "group": group,
            "case_count": sum(row["group"] == group for row in cases),
            "passed": all(row["passed"] for row in cases if row["group"] == group),
        }
        for group in group_names
    ]
    return {
        "schema": "finite_projection_unit_controls.v1",
        "passed": all(row["passed"] for row in cases),
        "case_count": len(cases),
        "groups": groups,
        "cases": cases,
        "new_qualified_trajectories": 0,
        "new_candidate_declarations": 0,
        "new_runtime_executions": 0,
        "provider_calls": 0,
        "controls_are_semantic_class_witnesses": False,
        "scope": (
            "isolated_mutations_of_saved_public_graphs_and_rule_witnesses_"
            "not_full_chain_runtime_tampering"
        ),
    }
