"""Isolated measurement controls on copies; never additional legal model trajectories."""

import copy
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.measurement import _ordered_graph
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.comparison import (
    compare_projections,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.guards import (
    guard_report,
    measurement_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.projection import (
    action_alignment,
    final_alignment,
    no_effect_interval,
    project_entry,
    retained_proposal,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.source import load_inputs


@pytest.fixture(scope="module")
def inputs():
    with measurement_guard() as counts:
        result = load_inputs(Path(__file__).resolve().parents[2])
    assert guard_report(counts, "projection_controls_input")["all_zero"]
    return result


def entry(inputs, label):
    return next(e for e in inputs["entries"] if e["label"] == label)


def test_actual_three_and_twelve_clean_are_independent_sidecars(inputs):
    original = canonical_json_bytes(inputs["entries"])
    with measurement_guard() as counts:
        projections = [
            project_entry(e, quotient_rule(), inputs["condition"]["id"]) for e in inputs["entries"]
        ]
    assert guard_report(counts, "projection_controls")["all_zero"]
    assert canonical_json_bytes(inputs["entries"]) == original
    assert sum(p["supported"] for p in projections) == 15
    assert sum(p["old_projection_supported"] for p in projections) == 12
    assert sum(len(p["interpretation_ledger"]) for p in projections) == 7
    share = next(p for p in projections if p["label"] == "S02")
    assert len(share["behavior_projection"]["retained_interactions"]) == 1
    assert len(share["behavior_projection"]["nodes"]) == 3
    episode = share["behavior_projection"]["retained_interactions"][0]
    assert episode["next_actual_action"] == {"producer_action": "action:0"}
    assert episode["later_actual_action"] == {"producer_action": "action:1"}
    assert episode["next_claim_actual_input_consumers"] == []
    assert episode["next_claim_actual_judgment_consumers"] == []
    assert episode["next_claim_is_final_answer"] is False
    assert [part["event_role"] for part in episode["observed_order"]] == [
        "unadmitted_proposal_and_feedback",
        "different_admitted_action",
        "explicit_accept_update_and_claim",
        "later_actual_execution_of_proposed_operation_and_inputs",
    ]
    assert [r["disposition"] for r in share["interpretation_ledger"]] == [
        "retained_behavior_relation",
        "retained_behavior_relation",
        "protocol_alignment_nonclassifying",
        "protocol_alignment_nonclassifying",
        "protocol_alignment_nonclassifying",
    ]
    assert all(p["base_projection_unchanged"] for p in projections if p["supported"])


@pytest.mark.parametrize(
    "change", ["execution", "observation", "claim", "state", "intervening_admission"]
)
def test_forged_no_effect_is_not_reduced(inputs, change):
    events = copy.deepcopy(entry(inputs, "D01")["session"]["events"])
    if change == "state":
        events[6]["post_state"]["accepted_claims"][0]["proposition"]["output"] = {"value": "999"}
    elif change == "intervening_admission":
        events[6]["receipt"]["admitted"] = True
    else:
        events[6][change] = {"forged": True}
    with pytest.raises(ProtocolError):
        no_effect_interval(events, 6, 7)


def test_same_final_does_not_justify_changed_claim_or_input(inputs):
    events = copy.deepcopy(entry(inputs, "D01")["session"]["events"])
    events[6]["parsed"]["answer_claim_id"] = "different_answer_claim"
    with pytest.raises(ProtocolError):
        final_alignment(events[6], events[7])
    branch = copy.deepcopy(entry(inputs, "B01")["session"]["events"])
    branch[4]["parsed"]["inputs"][0]["ref_id"] = "different_actual_support"
    with pytest.raises(ProtocolError):
        action_alignment(branch[4], branch[5])


def test_quantization_is_existing_claim_alignment_not_fuzzy_equality(inputs):
    events = copy.deepcopy(entry(inputs, "S02")["session"]["events"])
    result = final_alignment(events[8], events[11])
    assert result["numeric_strings_equal"] is False
    assert result["projected_value"] == "93.508458"
    events[8]["parsed"]["result"]["value"] = "93.5084581"
    with pytest.raises(ProtocolError):
        final_alignment(events[8], events[11])


def test_share_cannot_skip_sum_to_reduce_ratio_proposal(inputs):
    events = entry(inputs, "S02")["session"]["events"]
    with pytest.raises(ProtocolError, match="intervening_admission"):
        no_effect_interval(events, 0, 4)


def test_repeat_multiplicity_not_a_behavior_class_but_proposal_change_retained(inputs):
    item = entry(inputs, "S02")
    events = copy.deepcopy(item["session"]["events"])
    producers = {b["action_submission_id"]: b["node_id"] for b in item["graph"]["event_bindings"]}
    first = retained_proposal(events[0], events[2], producers)
    assert first == retained_proposal(events[1], events[2], producers)
    events[1]["parsed"]["decision"]["obligation_id"] = "ratio"
    assert first != retained_proposal(events[1], events[2], producers)


def test_uninterpreted_success_stays_undetermined(inputs):
    item = copy.deepcopy(entry(inputs, "D01"))
    item["session"]["events"][6]["parsed"]["result"]["value"] = "126"
    projected = project_entry(item, quotient_rule(), inputs["condition"]["id"])
    assert not projected["supported"] and projected["status"] == "undetermined"
    assert projected["behavior_projection"] is None
    assert projected["source_non_accept_ledger"] == item["graph"]["non_accept_event_ledger"]


@pytest.mark.parametrize("change", ["remove_order", "reverse_order", "alpha_rename"])
def test_explicit_share_order_is_retained_but_alpha_names_are_not_classes(inputs, change):
    left = project_entry(entry(inputs, "S02"), quotient_rule(), inputs["condition"]["id"])
    fields = copy.deepcopy({k: v for k, v in left.items() if k not in {"id", "schema_version"}})
    behavior = fields["behavior_projection"]
    if change == "remove_order":
        behavior["retained_interactions"][0].pop("observed_order")
    elif change == "reverse_order":
        behavior["retained_interactions"][0]["observed_order"].reverse()
    else:
        fields["behavior_projection"] = _ordered_graph(
            behavior,
            {"action:0": "renamed:sum", "action:1": "renamed:ratio", "action:2": "renamed:percent"},
        )
    fields["control_evidence"] = True
    comparison = compare_projections(left, record("panel_quotient_projection", **fields))
    assert comparison["equivalent"] is (change == "alpha_rename")
