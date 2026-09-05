"""Isolated finite-measurement controls; no synthetic case is a model sample."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .comparison import compare_all, compare_projections
from .measurement import build_partition, measure_empirical
from .models import DIFFERENT, EQUIVALENT, UNDETERMINED, MeasurementError, record, require
from .projection import correction_decision, project_session


def _reidentify(kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    return record(
        kind, **{key: value for key, value in obj.items() if key not in {"id", "schema_version"}}
    )


def _reverse_sets(value: Any, field: str = "") -> Any:
    fields = {
        "evidence_refs",
        "claim_refs",
        "observation_refs",
        "lineage",
        "grounding",
        "citations",
    }
    if isinstance(value, dict):
        return {key: _reverse_sets(item, key) for key, item in value.items()}
    if isinstance(value, list):
        result = [_reverse_sets(item) for item in value]
        return list(reversed(result)) if field in fields else result
    return value


def _decimal_surface(value: Any, field: str = "") -> Any:
    if isinstance(value, dict):
        return {key: _decimal_surface(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_surface(item) for item in value]
    if field == "value" and isinstance(value, str):
        return value + "0" if "." in value else value + ".0"
    return value


def run_controls(
    inputs: Mapping[str, Any],
    rules: Mapping[str, Any],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    partition: dict[str, Any],
) -> dict[str, Any]:
    """Counterfactual copies are explicit measurement premises, not newly Qualified trajectories."""
    by_label = {session["label"]: session for session in inputs["sessions"]}
    projected = {projection["label"]: projection for projection in projections}
    results: list[dict[str, Any]] = []

    def save(name: str, expected: str, actual: str, base: str, delta: Any, witness: Any) -> None:
        results.append(
            record(
                "control",
                name=name,
                expected=expected,
                actual=actual,
                passed=actual == expected,
                base_session_id=by_label[base]["declaration"]["id"],
                base_projection_id=projected[base]["id"],
                input_delta=delta,
                result=witness,
                interpretation=(
                    "isolated counterfactual measurement control, "
                    "not a new own-qualified model execution"
                ),
                qualified_scientific_sample=False,
                assignments_added_to_formal_partition=0,
                provider_calls=0,
                candidate_runtime_executions=0,
            )
        )

    base = projected["M06"]
    renamed = copy.deepcopy(base)
    rename_map = {
        node["key"]: f"renamed_node_{i:02d}" for i, node in enumerate(renamed["graph"]["nodes"])
    }
    for node in renamed["graph"]["nodes"]:
        node["key"] = rename_map[node["key"]]
    for edge in renamed["graph"]["edges"]:
        edge["source"], edge["target"] = rename_map[edge["source"]], rename_map[edge["target"]]
    for provenance in renamed["node_provenance"]:
        provenance["key"] = rename_map[provenance["key"]]
    renamed["graph"]["nodes"].reverse()
    renamed["graph"]["edges"].reverse()
    renamed["label"] = "display_label_has_no_class_authority"
    renamed = _reidentify("projection", renamed)
    result = compare_projections(base, renamed, rules)
    save(
        "consistent_graph_key_and_display_rename",
        EQUIVALENT,
        result["relation"],
        "M06",
        {"complete_key_bijection": rename_map, "reverse_serialization_order": True},
        result,
    )

    for name, transform in (
        ("declared_set_order", _reverse_sets),
        ("exact_decimal_surface", _decimal_surface),
    ):
        changed_session = copy.deepcopy(by_label["M06"])
        changed_session["records"] = transform(changed_session["records"])
        changed = project_session(inputs, changed_session, rules)
        result = compare_projections(base, changed, rules)
        save(
            name,
            EQUIVALENT,
            result["relation"],
            "M06",
            {
                "operation": name,
                "synthetic_saved_record_copy": True,
                "new_qualification_claimed": False,
            },
            result,
        )

    for name, role in (
        ("actual_denominator_use_edge", "operand:denominator:1"),
        ("observation_update_causality_edge", "updates_observation"),
    ):
        changed = copy.deepcopy(base)
        edge = next(edge for edge in changed["graph"]["edges"] if edge["role"] == role)
        before = copy.deepcopy(edge)
        if role.startswith("operand"):
            edge["source"] = inputs["context"]["evidence"]["freight"]["id"]
        else:
            observations = [
                node["key"] for node in changed["graph"]["nodes"] if node["kind"] == "observation"
            ]
            edge["source"] = next(key for key in observations if key != edge["source"])
        changed = _reidentify("projection", changed)
        result = compare_projections(base, changed, rules)
        save(
            name,
            DIFFERENT,
            result["relation"],
            "M06",
            {"edge_before": before, "edge_after": edge, "Final_answer_unchanged": True},
            result,
        )

    for name in (
        "accepted_claim_changes_during_rejection",
        "pending_observation_changes_during_rejection",
        "actual_action_operand_switch",
        "Final_answer_claim_switch",
    ):
        label, index = (
            ("M03", 5)
            if name.startswith(("accepted", "pending"))
            else ("M04", 2)
            if name.startswith("actual")
            else ("M02", 4)
        )
        changed_records = copy.deepcopy(by_label[label]["records"])
        event = changed_records["events"][index]
        if name.startswith("accepted"):
            event["post_state"]["accepted_claims"][0]["proposition"]["value"] = "0"
            delta = {
                "turn_index": index,
                "path": "post_state.accepted_claims[0].proposition.value",
                "new_value": "0",
            }
        elif name.startswith("pending"):
            event["post_state"]["pending_observation"]["output"]["value"] = "0"
            delta = {
                "turn_index": index,
                "path": "post_state.pending_observation.output.value",
                "new_value": "0",
            }
        elif name.startswith("actual"):
            replacement = {
                "kind": "evidence",
                "role": "ratio",
                "ref_id": inputs["context"]["evidence"]["total"]["id"],
            }
            event["submission"]["parsed"]["inputs"][0] = replacement
            delta = {
                "turn_index": index,
                "path": "submission.parsed.inputs[0]",
                "new_value": replacement,
            }
        else:
            replacement_id = changed_records["events"][3]["post_state"]["accepted_claims"][0]["id"]
            event["submission"]["parsed"]["answer_claim_id"] = replacement_id
            delta = {
                "turn_index": index,
                "path": "submission.parsed.answer_claim_id",
                "new_value": replacement_id,
            }
        result = correction_decision(changed_records, index, rules, qualified=True)
        save(name, UNDETERMINED, result["decision"], label, delta, result)

    failed_projections = copy.deepcopy(projections)
    failed_projections[0]["status"] = "mapped"
    failed_projections[0]["graph"] = copy.deepcopy(base["graph"])
    failed_projections[0] = _reidentify("projection", failed_projections[0])
    try:
        build_partition(inputs, rules, failed_projections, pairs)
        actual, code = "accepted", None
    except MeasurementError as error:
        actual, code = "rejected", error.code
    save(
        "failed_M01_forced_into_valid_domain",
        "rejected",
        actual,
        "M01",
        {"status": "mapped", "borrowed_success_graph": base["id"]},
        {"code": code},
    )

    unknown = copy.deepcopy(projections)
    unknown[1]["status"] = UNDETERMINED
    unknown[1]["uninterpreted"] = [{"turn_index": None, "code": "control.unsupported_semantics"}]
    unknown[1] = _reidentify("projection", unknown[1])
    unknown_pairs = compare_all(unknown, rules)
    unknown_partition = build_partition(inputs, rules, unknown, unknown_pairs)
    unknown_measurement = measure_empirical(inputs, rules, unknown_partition)
    kept = (
        unknown_partition["complete"] is False
        and unknown_partition["assignments"] == []
        and unknown_measurement["registered_denominator"] == 6
        and unknown_measurement["qualified_denominator"] == 5
        and unknown_measurement["unmapped_count"] == 5
        and unknown_measurement["mapped_count"] == 0
        and unknown_measurement["conditional_distribution"] is None
        and unknown_measurement["q"]["exact"] == "5/6"
    )
    save(
        "unknown_mapping_keeps_original_denominators",
        "preserved_unknown",
        "preserved_unknown" if kept else "invalid",
        "M02",
        {"projection_status": UNDETERMINED},
        {"partition": unknown_partition, "measurement": unknown_measurement},
    )

    wrong_inputs = dict(inputs)
    wrong_inputs["sessions"] = inputs["sessions"][1:]
    try:
        measure_empirical(wrong_inputs, rules, partition)
        actual, code = "accepted", None
    except MeasurementError as error:
        actual, code = "rejected", error.code
    save(
        "remove_failure_and_change_six_denominator",
        "rejected",
        actual,
        "M01",
        {"remove_session_id": by_label["M01"]["declaration"]["id"]},
        {"code": code},
    )
    require(len(results) == 12, "controls.finite_control_inventory")
    return record(
        "controls",
        measurement_contract_id=rules["id"],
        controls=results,
        passed=sum(control["passed"] for control in results),
        failed=sum(not control["passed"] for control in results),
        scientific_samples_added=0,
        formal_pairs_added=0,
        provider_calls=0,
        candidate_runtime_executions=0,
        old_adapter_audit_rerun=False,
    )
