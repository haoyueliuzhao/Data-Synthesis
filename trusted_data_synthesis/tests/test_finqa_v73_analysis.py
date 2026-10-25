"""Bounded CPU JSON fixtures for full denominators, pairing and NA semantics."""
import copy
import importlib
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
a = importlib.import_module("finqa_v73_analysis")
m = importlib.import_module("finqa_v73_measurement")


def fixture():
    tasks = [dict(task_key=f"{group}{index:02}", group=group) for group in ("F", "K") for index in range(48)]
    logical, generation, probability = [], {}, {}
    for task in tasks:
        key, group = task["task_key"], task["group"]
        for source in a.MODELS:
            # Intentional source-history deduplication: logical labels are kept.
            logical.append(dict(task_key=key, source=source, context_id=key,
                old_response_sha256="old-response", old_response_token_ids_sha256=m.digest([1, 2])))
        for model in a.MODELS:
            category = "compliant_nonterminal_candidate" if model == "H" else "plain_no_tool_call" if model == "L" and group == "F" else "compliant_submit_candidate"
            generation[model, key] = dict(classification=dict(category=category,
                A=int(category in m.ACTION_CATEGORIES[:2]), S=int(category == m.ACTION_CATEGORIES[0])),
                raw_response_sha256="old-response", raw_generated_token_ids=[1, 2])
            value = {"P": 1.0, "H": 3.0, "L": 2.0}[model]
            groups = {name: dict(token_count=1, nll_sum=value, mean_nll=value, status="MEASURED") for name in m.TOKEN_GROUPS}
            groups["pre_action_text"] = dict(token_count=0, nll_sum=None, mean_nll=None, status="NA")
            probability[model, key] = dict(measurement=dict(grouping_id=key, groups=groups))
    return {"id": "protocol"}, dict(tasks=tasks, logical_rows=logical), generation, probability


def test_deduplicated_histories_preserve_full_F_K_matrices_and_primary_pair_direction():
    out = a.summarize(*fixture())
    assert out["status"] == "COMPLETE" and out["panel_denominator"] == 96
    f = out["panels"]["F"]
    assert f["single_response_action_matrix"]["H"]["P"]["A"]["complete_panel_rate"] == 1
    assert f["single_response_action_matrix"]["H"]["P"]["S"]["complete_panel_rate"] == 0
    assert f["primary_hP_paired_models"]["H_minus_P"]["A"]["complete_panel_net"] == 0
    assert f["primary_hP_paired_models"]["H_minus_P"]["S"]["lost"] == 48
    assert f["primary_hP_paired_models"]["L_minus_P"]["A"]["lost"] == 48
    assert f["paired_histories_at_fixed_model"]["P"]["hL_minus_hP"]["A"]["complete_panel_net"] == 0
    assert out["new_execution_accuracy_or_program_accuracy_computed"] is False
    assert out["automatic_followup_authorized"] is False


def test_missing_generation_keeps_48_denominator_and_is_not_no_tool_call_or_zero():
    protocol, inputs, generation, probability = fixture()
    del generation["L", "F00"]
    out = a.summarize(protocol, inputs, generation, probability)
    cell = out["panels"]["F"]["single_response_action_matrix"]["L"]["P"]
    assert cell["denominator"] == 48 and cell["unknown_count"] == 1
    assert cell["categories"]["plain_no_tool_call"] == 47
    assert cell["A"]["complete_panel_rate"] is None
    paired = out["panels"]["F"]["primary_hP_paired_models"]["L_minus_P"]
    assert paired["known_pair_count"] == 47 and paired["unknown_pair_count"] == 1
    assert paired["A"]["lost"] == 47 and paired["A"]["complete_panel_net"] is None
    assert out["status"] == "COMPLETE_WITH_UNKNOWN"


def test_missing_context_row_remains_unknown_in_all_model_rows():
    protocol, inputs, generation, probability = fixture()
    inputs["logical_rows"] = [row for row in inputs["logical_rows"] if (row["task_key"], row["source"]) != ("K00", "H")]
    out = a.summarize(protocol, inputs, generation, probability)
    for model in a.MODELS:
        assert out["panels"]["K"]["single_response_action_matrix"][model]["H"]["unknown_count"] == 1


def test_probability_groups_keep_NA_and_report_same_task_delta_sign():
    out = a.summarize(*fixture())
    panel = out["panels"]["F"]
    empty = panel["fixed_parent_response_probability"]["P"]["pre_action_text"]
    assert empty["NA_empty_group_sequences"] == 48 and empty["pooled_token_mean_nll"] is None
    paired = panel["paired_probability_changes"]["L_minus_H"]
    assert paired["action_structure"]["candidate_minus_reference_mean_nll"]["mean"] == -1
    assert paired["action_structure"]["negative_delta_count"] == 48
    assert paired["pre_action_text"]["NA_empty_group_pairs"] == 48
    assert paired["pre_action_text"]["candidate_minus_reference_mean_nll"]["mean"] is None


def test_missing_probability_is_UNKNOWN_instead_of_NA_or_zero():
    protocol, inputs, generation, probability = fixture()
    del probability["H", "F00"]
    out = a.summarize(protocol, inputs, generation, probability)
    model = out["panels"]["F"]["fixed_parent_response_probability"]["H"]
    assert model["pre_action_text"]["NA_empty_group_sequences"] == 47
    assert model["pre_action_text"]["UNKNOWN_sequences"] == 1
    assert model["action_structure"]["per_sequence_mean_nll"]["mean"] == 3
    pair = out["panels"]["F"]["paired_probability_changes"]["H_minus_P"]["action_structure"]
    assert pair["measured_pairs"] == 47 and pair["UNKNOWN_pairs"] == 1


def test_diagonal_mismatch_is_retained_not_replaced_or_retried():
    protocol, inputs, generation, probability = fixture()
    generation["P", "F00"]["raw_response_sha256"] = "different"
    generation["P", "F00"]["raw_generated_token_ids"] = [8, 9]
    out = a.summarize(protocol, inputs, generation, probability)
    diag = out["panels"]["F"]["source_model_source_history_reproduction"]["P"]
    assert diag["raw_identical"] == 47 and diag["raw_different"] == 1
    assert diag["token_ids_different"] == 1
    assert diag["historical_diagonal_is_selection_evidence_not_new_discovery"]


@pytest.mark.parametrize("mutation", ["wrong_group_size", "duplicate_logical", "wrong_A", "changed_target", "zero_filled_NA"])
def test_inconsistent_saved_contract_is_rejected_not_hidden_as_UNKNOWN(mutation):
    protocol, inputs, generation, probability = fixture()
    if mutation == "wrong_group_size":
        inputs["tasks"][0]["group"] = "K"
    elif mutation == "duplicate_logical":
        inputs["logical_rows"].append(copy.deepcopy(inputs["logical_rows"][0]))
    elif mutation == "wrong_A":
        generation["P", "F00"]["classification"]["A"] = 0
    elif mutation == "changed_target":
        probability["H", "F00"]["measurement"]["grouping_id"] = "different"
    else:
        probability["H", "F00"]["measurement"]["groups"]["pre_action_text"]["mean_nll"] = 0
    with pytest.raises(ValueError):
        a.summarize(protocol, inputs, generation, probability)
