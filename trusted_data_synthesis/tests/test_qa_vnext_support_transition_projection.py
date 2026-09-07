"""Typed-retention controls on source copies, never new model or qualification evidence."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.projection import final_alignment
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.comparison import (
    comparison_contract,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.guards import (
    guard_report,
    measurement_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.projection import (
    grounding_assertions,
    project_entry,
    support_transition,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.rules import measurement_rule
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.source import load_inputs
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.stage import (
    _target,
    freeze_condition,
)


@pytest.fixture(scope="module")
def data():
    with measurement_guard() as counts:
        inputs = load_inputs(Path(__file__).resolve().parents[2])
        rule = measurement_rule()
        condition = freeze_condition(inputs, rule, record("implementation", control_evidence=True))
        contract = comparison_contract(condition, inputs["generation_condition"], rule)
    assert guard_report(counts, "constructed_input_binding")["all_zero"]
    return inputs, rule, condition, contract


def entry(data, label):
    return next(e for e in data[0]["entries"] if e["label"] == label)


def test_all_seven_retained_fourteen_old_interpretations_reused(data):
    inputs, rule, condition, contract = data
    original = canonical_json_bytes(inputs["entries"])
    with measurement_guard() as counts:
        projected = [
            project_entry(e, condition, inputs["generation_condition"], rule, contract)
            for e in inputs["entries"]
        ]
    assert guard_report(counts, "new_relation_projection")["all_zero"]
    assert canonical_json_bytes(inputs["entries"]) == original
    assert sum(p["supported"] for p in projected) == 3
    assert sum(p["newly_interpreted_event_count"] for p in projected) == 7
    assert sum(p["reused_interpretation_count"] for p in projected) == 14
    for item, result in zip(inputs["entries"], projected, strict=True):
        if item["qualification"]["qualified"]:
            assert result["base_nodes_and_final_unchanged"]
            old = {r["sequence"]: r for r in item["old_projection"]["interpretation_ledger"]}
            for row in result["interpretation_ledger"]:
                if old[row["sequence"]]["disposition"] != "undetermined":
                    assert canonical_json_bytes(row) == canonical_json_bytes(old[row["sequence"]])
        else:
            assert result["status"] == "ineligible"
    e04 = next(p for p in projected if p["label"] == "E04")
    assert e04["behavior_projection"] == entry(data, "E04")["old_behavior"]
    e02 = next(p for p in projected if p["label"] == "E02")
    assert [r["kind"] for r in e02["behavior_projection"]["retained_interactions"]] == [
        "support_choice_transition_after_unadmitted_proposal",
        "same_answer_grounding_assertion_correction",
    ]


def test_support_transition_separates_order_from_new_claim_dependency(data):
    relation, proof = support_transition(entry(data, "N03"), 0)
    assert relation["unadmitted_proposal_was_executed"] is False
    assert relation["reconstruction_changes_execution_state"] is True
    assert relation["denominator_transition"]["inputs_are_equal"] is False
    assert relation["denominator_transition"]["before"]["kind"] == "evidence"
    assert relation["denominator_transition"]["after"] == {
        "kind": "claim",
        "reference": {"producer_action": "action:0"},
    }
    assert relation["real_input_dependency"]["consumer"] == {"producer_action": "action:1"}
    assert proof["no_effect_interval_end_exclusive"] == 1
    assert proof["actual_total"]["action_sequence"] == 1
    assert proof["actual_total"]["update_sequence"] < proof["actual_ratio"]["action_sequence"]


@pytest.mark.parametrize(
    "mutation",
    ["fake_execution", "fake_admission", "remove_sum", "unaccepted_claim", "wrong_resolved_ref"],
)
def test_false_execution_or_false_claim_consumption_is_not_interpreted(data, mutation):
    item = copy.deepcopy(entry(data, "N03"))
    events = item["session"]["events"]
    if mutation == "fake_execution":
        events[0]["execution"] = {"forged": True}
    elif mutation == "fake_admission":
        events[0]["receipt"]["admitted"] = True
    elif mutation == "remove_sum":
        item["graph"]["nodes"] = item["graph"]["nodes"][1:]
    elif mutation == "unaccepted_claim":
        events[3]["request"]["state"]["accepted_claims"] = []
    else:
        ref = next(
            r
            for r in events[3]["execution"]["resolved_inputs"]
            if r["value"]["role"] == "denominator"
        )
        ref["ref_id"] = "forged_claim_reference"
    with pytest.raises(ProtocolError):
        support_transition(item, 0)


def test_rejected_grounding_is_not_redundant_citation_or_actual_uses(data):
    item = entry(data, "E02")
    events = item["session"]["events"]
    with pytest.raises(ProtocolError, match="new_or_replaced_citation_support"):
        final_alignment(events[8], events[15])
    before = canonical_json_bytes(item["graph"]["nodes"])
    relation, detail = grounding_assertions(item)
    assert canonical_json_bytes(item["graph"]["nodes"]) == before
    assert detail["all_source_sequences"] == list(range(8, 16))
    assert detail["new_event_sequences"] == [8, 10, 11, 13]
    assert len(detail["original_assertions"]) == 8
    assert len(relation["assertion_sequence"]) == 6
    assert [a["assertion_kind"] for a in relation["assertion_sequence"]] == [
        "incorrect_support_assertion",
        "actual_lineage_assertion",
    ] * 3
    context = events[8]["request"]["context"]
    assert detail["original_assertions"][0]["missing"] == [context["evidence"]["other"]["id"]]
    assert detail["original_assertions"][0]["extra"] == [context["evidence"]["total"]["id"]]
    assert detail["original_assertions"][-1]["receipt"]["admitted"] is True
    assert relation["assertions_are_not_actual_input_dependencies"] is True


def test_registered_set_order_and_surface_value_changes_do_not_make_new_assertion_states(data):
    original = entry(data, "E02")
    first, _ = grounding_assertions(original)
    changed = copy.deepcopy(original)
    for event in changed["session"]["events"][8:]:
        event["parsed"]["citations"].reverse()
    second, _ = grounding_assertions(changed)
    assert first == second
    # T11/T12 are distinct original submissions and result representations, same assertion state.
    _, detail = grounding_assertions(original)
    a, b = detail["original_assertions"][2:4]
    assert a["original_result"] != b["original_result"]
    assert a["normalized_assertion_index"] == b["normalized_assertion_index"]


@pytest.mark.parametrize("mutation", ["near_value", "new_citation", "new_accepted_claim"])
def test_unknown_or_unbound_assertion_changes_stay_outside_rule(data, mutation):
    item = copy.deepcopy(entry(data, "E02"))
    events = item["session"]["events"]
    if mutation == "near_value":
        events[8]["parsed"]["result"]["value"] = "93.5084581"
    elif mutation == "new_citation":
        events[8]["parsed"]["citations"].append("unbound_external_evidence")
    else:
        events[8]["post_state"]["accepted_claims"].append({"forged": True})
    with pytest.raises(ProtocolError):
        grounding_assertions(item)


def test_new_rule_does_not_edit_generation_rule_or_five_failures(data):
    inputs, rule, condition, _ = data
    assert condition["generation_condition_id"] == inputs["generation_condition"]["id"]
    assert condition["original_generation_rule_id"] == rule["extends_rule_id"]
    assert condition["rule_id"] != inputs["generation_condition"]["rule_id"]
    assert len(condition["qualified_qualification_ids"]) == 3
    assert sum(not r["qualified"] for r in condition["frozen_outcomes"]) == 5


def test_output_cannot_target_old_generation_or_representation_directory(tmp_path):
    with pytest.raises(ProtocolError):
        _target(
            tmp_path, tmp_path / "trusted_data_synthesis/artifacts/qa_vnext_support_exploration"
        )
