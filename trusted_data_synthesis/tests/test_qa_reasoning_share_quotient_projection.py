"""Pure finite measurement controls; no new trajectory, adapter, QA or kernel call."""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as pilot_reader
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import (
    comparison,
    inputs,
    measurement,
    models,
    projection,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def prepared() -> dict[str, Any]:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("finite projection tests must not requalify or execute parent QA")

    with pytest.MonkeyPatch.context() as patch:
        for name in ("audit_records", "audit_session", "aggregate_pilot", "_output"):
            patch.setattr(pilot_reader, name, forbidden)
        frozen = inputs.load_inputs(ROOT)
        rules = models.measurement_contract()
        projected = [projection.project_session(frozen, item, rules) for item in frozen["sessions"]]
        pairs = comparison.compare_all(projected, rules)
        partition = measurement.build_partition(frozen, rules, projected, pairs)
        yield {
            "inputs": frozen,
            "rules": rules,
            "projections": projected,
            "pairs": pairs,
            "partition": partition,
        }
        inputs.assert_unchanged(ROOT, frozen)


def _reidentify(value: dict[str, Any]) -> dict[str, Any]:
    return models.record(
        "projection",
        **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
    )


def test_existing_five_qualified_graphs_map_but_m01_remains_nonqualified(
    prepared: dict[str, Any],
) -> None:
    projected = prepared["projections"]
    assert [item["status"] for item in projected] == ["not_qualified", *(["mapped"] * 5)]
    assert projected[0]["graph"] is None
    assert projected[0]["qualification_reused_not_reexecuted"] is True
    assert sum(len(item["event_decisions"]) for item in projected) == 51
    for item in projected[1:]:
        assert sum(node["kind"] == "final" for node in item["graph"]["nodes"]) == 1
        assert item["historical_support_description_used_as_class_authority"] is False
        assert item["statistics"]["new_provider_calls"] == 0
        assert item["statistics"]["new_candidate_runtime_executions"] == 0


def test_twelve_qualified_corrections_have_all_checks_while_six_m01_rejections_stay_excluded(
    prepared: dict[str, Any],
) -> None:
    rejected = prepared["projections"][0]["corrections"]
    corrections = [item for result in prepared["projections"][1:] for item in result["corrections"]]
    assert len(rejected) == 6 and len(corrections) == 12
    assert all(item["decision"] == "excluded_nonqualified" for item in rejected)
    assert all(item["decision"] == "reduce_protocol_correction" for item in corrections)
    assert all(all(item["checks"].values()) for item in corrections)
    assert all(item["raw_parent_evidence_retained"] is True for item in corrections)
    assert all(item["raw_rejection_is_an_accepted_proposition"] is False for item in corrections)
    assert all(item["budget_impact"]["provider_attempts"] == 1 for item in corrections)
    assert all(item["budget_impact"]["submissions"] == 1 for item in corrections)


def test_consistent_graph_key_renaming_has_a_complete_typed_edge_preserving_bijection(
    prepared: dict[str, Any],
) -> None:
    original = prepared["projections"][1]
    renamed = copy.deepcopy(original)
    renaming = {
        node["key"]: f"alpha_{index}" for index, node in enumerate(renamed["graph"]["nodes"])
    }
    for node in renamed["graph"]["nodes"]:
        node["key"] = renaming[node["key"]]
    for edge in renamed["graph"]["edges"]:
        edge["source"], edge["target"] = renaming[edge["source"]], renaming[edge["target"]]
    for row in renamed["node_provenance"]:
        row["key"] = renaming[row["key"]]
    renamed["graph"]["nodes"].reverse()
    renamed["graph"]["edges"].reverse()
    renamed["label"] = "nonsemantic display label"
    renamed = _reidentify(renamed)
    result = comparison.compare_projections(original, renamed, prepared["rules"])
    assert result["relation"] == models.EQUIVALENT
    assert result["difference_witness"] is None
    bijection = {row["left"]: row["right"] for row in result["bijection"]}
    assert set(bijection) == set(renaming)
    assert set(bijection.values()) == set(renaming.values())
    left_nodes = {node["key"]: node for node in original["graph"]["nodes"]}
    right_nodes = {node["key"]: node for node in renamed["graph"]["nodes"]}
    for left, right in bijection.items():
        assert left_nodes[left]["kind"] == right_nodes[right]["kind"]
        assert left_nodes[left]["semantics"] == right_nodes[right]["semantics"]
    transformed_edges = Counter(
        (bijection[e["source"]], bijection[e["target"]], e["role"])
        for e in original["graph"]["edges"]
    )
    assert transformed_edges == Counter(
        (e["source"], e["target"], e["role"]) for e in renamed["graph"]["edges"]
    )


def test_registered_set_reference_order_is_not_a_new_graph_semantics(
    prepared: dict[str, Any],
) -> None:
    def reverse_sets(value: Any, field: str = "") -> Any:
        if isinstance(value, dict):
            return {key: reverse_sets(item, key) for key, item in value.items()}
        if isinstance(value, list):
            converted = [reverse_sets(item) for item in value]
            return list(reversed(converted)) if field in projection.SET_FIELDS else converted
        return value

    session = copy.deepcopy(prepared["inputs"]["sessions"][2])
    session["records"] = reverse_sets(session["records"])
    alternate = projection.project_session(prepared["inputs"], session, prepared["rules"])
    assert alternate["status"] == "mapped"
    pair = comparison.compare_projections(prepared["projections"][2], alternate, prepared["rules"])
    assert pair["relation"] == models.EQUIVALENT


@pytest.mark.parametrize(("left", "right"), [("1.000", "1"), ("1e2", "100"), ("-0.00", "0")])
def test_decimal_surface_normalization_preserves_exact_equality(left: str, right: str) -> None:
    assert models.number(left) == models.number(right)


def test_early_rounding_is_not_decimal_equality_or_a_type_erasure() -> None:
    complete = "93.508458258836473662494842525099711181405583826159"
    rounded = "93.508458"
    assert models.number(complete) != models.number(rounded)
    assert models.structural_key("1") != models.structural_key(1)
    assert models.structural_key(True) != models.structural_key(1)


@pytest.mark.parametrize(
    "mutation", ["pending", "accepted_claim", "action_input", "final_claim", "effect"]
)
def test_semantic_changes_across_a_rejection_block_are_undetermined_not_corrections(
    prepared: dict[str, Any],
    mutation: str,
) -> None:
    if mutation in {"pending", "accepted_claim", "effect"}:
        records = copy.deepcopy(prepared["inputs"]["sessions"][2]["records"])
        index = 5
        if mutation == "pending":
            records["events"][index]["post_state"]["pending_observation"]["output"]["value"] = "1"
            failed_check = "C1_knowledge_state_stable"
        elif mutation == "accepted_claim":
            records["events"][index]["post_state"]["accepted_claims"][0]["proposition"]["value"] = (
                "1"
            )
            failed_check = "C1_knowledge_state_stable"
        else:
            records["events"][index]["execution"] = copy.deepcopy(records["events"][0]["execution"])
            records["events"][index]["event"]["execution_id"] = records["events"][0]["execution"][
                "id"
            ]
            failed_check = "C0_no_effects"
    elif mutation == "action_input":
        records = copy.deepcopy(prepared["inputs"]["sessions"][3]["records"])
        index = 2
        records["events"][3]["submission"]["parsed"]["inputs"][0]["ref_id"] = "changed_actual_input"
        failed_check = "C3_allowed_alignment"
    else:
        records = copy.deepcopy(prepared["inputs"]["sessions"][1]["records"])
        index = 4
        records["events"][6]["submission"]["parsed"]["answer_claim_id"] = "another_accepted_claim"
        failed_check = "C3_allowed_alignment"
    decision = projection.correction_decision(records, index, prepared["rules"], qualified=True)
    assert decision["decision"] == "undetermined"
    assert decision["checks"][failed_check] is False
    assert decision["raw_parent_evidence_retained"] is True


def test_update_observation_dependency_change_is_not_erased_by_equal_final_answer(
    prepared: dict[str, Any],
) -> None:
    original = prepared["projections"][1]
    changed = copy.deepcopy(original)
    edge = next(e for e in changed["graph"]["edges"] if e["role"] == "updates_observation")
    different_observation = next(
        node["key"]
        for node in changed["graph"]["nodes"]
        if node["kind"] == "observation" and node["key"] != edge["source"]
    )
    edge["source"] = different_observation
    changed = _reidentify(changed)
    pair = comparison.compare_projections(original, changed, prepared["rules"])
    assert pair["relation"] in {models.DIFFERENT, models.UNDETERMINED}
    assert pair["relation"] != models.EQUIVALENT
    if pair["relation"] == models.DIFFERENT:
        assert pair["difference_witness"]["kind"] == "edge_semantic_multiset"
        assert pair["difference_witness"]["graph_hash_or_node_count_is_authority"] is False


def test_m01_cannot_be_promoted_to_a_valid_assignment(prepared: dict[str, Any]) -> None:
    projected = copy.deepcopy(prepared["projections"])
    projected[0]["status"] = "mapped"
    projected[0] = _reidentify(projected[0])
    with pytest.raises(models.MeasurementError, match="partition.failed_session_assignment"):
        measurement.build_partition(
            prepared["inputs"], prepared["rules"], projected, prepared["pairs"]
        )
    partition = copy.deepcopy(prepared["partition"])
    invented = copy.deepcopy(partition["assignments"][0])
    invented["session_id"] = prepared["inputs"]["sessions"][0]["declaration"]["id"]
    partition["assignments"].append(invented)
    with pytest.raises(models.MeasurementError, match="measurement.assignment_conservation"):
        measurement.measure_empirical(prepared["inputs"], prepared["rules"], partition)


def test_one_uninterpreted_qualified_projection_preserves_all_five_unmapped_and_fixed_denominators(
    prepared: dict[str, Any],
) -> None:
    projected = copy.deepcopy(prepared["projections"])
    projected[2]["status"] = "undetermined"
    projected[2]["uninterpreted"] = [{"turn_index": 5, "code": "unit.unexplained_causality"}]
    projected[2] = _reidentify(projected[2])
    pairs = comparison.compare_all(projected, prepared["rules"])
    assert len(pairs) == 10
    assert sum(pair["relation"] == models.UNDETERMINED for pair in pairs) == 4
    partition = measurement.build_partition(prepared["inputs"], prepared["rules"], projected, pairs)
    result = measurement.measure_empirical(prepared["inputs"], prepared["rules"], partition)
    assert partition["complete"] is False
    assert partition["classes"] == partition["assignments"] == []
    assert len(partition["unmapped_session_ids"]) == 5
    assert result["q"]["exact"] == "5/6"
    assert result["registered_denominator"] == 6
    assert result["qualified_denominator"] == 5
    assert result["unmapped_count"] == 5 and result["mapped_count"] == 0
    assert result["conditional_total"]["exact"] == "0/5"
    assert result["unmapped_conditional"]["exact"] == "5/5"
    assert result["failure_frequency"]["exact"] == "1/6"
    assert result["conditional_distribution"] is None


def test_deleting_m01_cannot_renormalize_the_five_successes_to_a_new_population(
    prepared: dict[str, Any],
) -> None:
    reduced = {**prepared["inputs"], "sessions": prepared["inputs"]["sessions"][1:]}
    with pytest.raises(models.MeasurementError, match="partition.exact_six_outcomes"):
        measurement.build_partition(
            reduced, prepared["rules"], prepared["projections"][1:], prepared["pairs"]
        )
    with pytest.raises(models.MeasurementError, match="measurement.fixed_population"):
        measurement.measure_empirical(reduced, prepared["rules"], prepared["partition"])


def test_changing_registered_denominator_is_rejected(prepared: dict[str, Any]) -> None:
    changed_rules = copy.deepcopy(prepared["rules"])
    changed_rules["denominators"]["end_to_end"] = 5
    with pytest.raises(models.MeasurementError, match="measurement.fixed_population"):
        measurement.measure_empirical(prepared["inputs"], changed_rules, prepared["partition"])


def test_actual_reduced_value_changes_are_unaccepted_alignments_not_numeric_equivalences(
    prepared: dict[str, Any],
) -> None:
    changes = [
        item
        for result in prepared["projections"][1:]
        for item in result["corrections"]
        if item["kind"] == "update"
    ]
    assert len(changes) == 7
    for item in changes:
        assert item["decision"] == "reduce_protocol_correction"
        assert item["correction_content_is_exact_decimal_surface_equivalence"] is False
        assert item["raw_rejection_is_an_accepted_proposition"] is False
        before, after = item["before_proposal"], item["after_proposal"]
        assert before["observation_id"] == after["observation_id"]
        assert models.number(before["proposed_claim"]["value"]) != models.number(
            after["proposed_claim"]["value"]
        )


def test_finite_permutation_limit_returns_unknown_not_a_fabricated_difference(
    prepared: dict[str, Any],
) -> None:
    ambiguous = copy.deepcopy(prepared["projections"][1])
    ambiguous["graph"] = {
        "nodes": [
            {"key": f"n{index}", "kind": "claim", "semantics": {"value": "1"}} for index in range(7)
        ],
        "edges": [],
    }
    ambiguous = _reidentify(ambiguous)
    pair = comparison.compare_projections(ambiguous, ambiguous, prepared["rules"])
    assert pair["relation"] == models.UNDETERMINED
    assert pair["reason"] == "comparison.finite_permutation_bound"
    assert pair["difference_witness"] is None
