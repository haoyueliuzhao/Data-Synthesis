"""Pure CPU tests for the new cross-history prefix and dose contract."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v74_inputs as inputs


@pytest.mark.parametrize("prior,category,expected", [
    (0, "compliant_nonterminal_candidate", 31),
    (7, "compliant_nonterminal_candidate", 24),
    (31, "compliant_nonterminal_candidate", 0),
    (0, "compliant_submit_candidate", 0),
    (0, "plain_no_tool_call", 0),
])
def test_original_budget_counts_prefix_and_reused_response(prior, category, expected):
    assert inputs.residual_budget(prior, category) == expected


@pytest.mark.parametrize("prior", [-1, 32, 1.0, True])
def test_invalid_source_call_index_cannot_receive_fresh_budget(prior):
    with pytest.raises(ValueError):
        inputs.residual_budget(prior, "compliant_nonterminal_candidate")


def fixture_episode():
    identity = dict(point_id="original-source-P", parameter_digest="theta-P")
    turns, settlements, events = [], [], []
    for index in range(3):
        call = dict(call_id=f"original-call-{index}", name="run_program",
                    arguments=dict(program=f"add({index}, 1)"))
        turns.append(dict(raw_text=f"untouched original turn {index}", tool_calls=[call],
            receipt=dict(identity=identity, request_sha256=f"original-request-{index}"),
            provider_metadata=dict(invocation_id=f"original-invocation-{index}")))
        settlements.append(dict(state="returned", actual_model_calls=1,
            evidence=dict(invocation_id=f"original-invocation-{index}",
                harness_invocation=dict(turn_index=index, point_id="original-source-P"))))
        events.append(dict(call_id=call["call_id"], name=call["name"], is_error=False,
            executed_arguments=call["arguments"], raw_output=dict(result=index+1),
            visible_output=f"{index+1}", invocation_id=f"tool-invocation-{index}"))
    return dict(provider=identity, all_provider_calls_settled=True, turns=turns,
        tool_events=events, call_settlements=settlements,
        final_answer="FUTURE ANSWER MUST NOT ENTER PREFIX", final_program="add(900, 900)")


def test_prefix_excludes_current_turn_future_answers_and_preserves_identities():
    episode = fixture_episode()
    source = copy.deepcopy(episode)
    prefix = inputs.prefix_before(episode, 1, episode["provider"])
    assert prefix == dict(prefix_turns=episode["turns"][:1],
        prefix_events=episode["tool_events"][:1], prefix_settlements=episode["call_settlements"][:1])
    assert episode == source
    assert "FUTURE" not in str(prefix)
    prefix["prefix_turns"][0]["receipt"]["identity"]["point_id"] = "mutated copy"
    assert episode == source


def test_first_request_has_no_invented_history_or_settlements():
    episode = fixture_episode()
    assert inputs.prefix_before(episode, 0, episode["provider"]) == dict(
        prefix_turns=[], prefix_events=[], prefix_settlements=[])


@pytest.mark.parametrize("mutation", ["event_reorder", "foreign_receipt", "already_terminal", "unsettled", "duplicate_settlement"])
def test_unverifiable_history_blocks_instead_of_substituting(mutation):
    episode = fixture_episode()
    if mutation == "event_reorder":
        episode["tool_events"].reverse()
    elif mutation == "foreign_receipt":
        episode["turns"][0]["receipt"]["identity"] = dict(point_id="another")
    elif mutation == "already_terminal":
        episode["tool_events"][0]["name"] = "submit_program"
    elif mutation == "unsettled":
        episode["call_settlements"][0]["state"] = "unknown"
    else:
        episode["call_settlements"].append(copy.deepcopy(episode["call_settlements"][0]))
    with pytest.raises(ValueError):
        inputs.prefix_before(episode, 1, episode["provider"])


def test_context_comparison_uses_exact_tokens_and_does_not_equate_empty_computation():
    task = dict(task_key="task", group="F", source_group=dict(group="cluster"))
    parent = dict(prefix_events=[], prompt_input_ids=[10, 11], original_request=dict(messages=["a"]))
    parent["history_structure"] = inputs.history_structure(0, [], parent["prompt_input_ids"])
    low = copy.deepcopy(parent)
    low["prompt_input_ids"] = [10, 12]
    low["history_structure"] = inputs.history_structure(0, [], low["prompt_input_ids"])
    value = inputs.context_comparison(task, parent, low)
    assert value["programs_and_outputs_identical"] is True
    assert value["actual_prompt_tokens_identical"] is False
    assert value["empty_program_sequences_are_reported_as_empty_not_evidence_of_shared_computation"]


def test_native_error_events_are_retained_in_structure():
    episode = fixture_episode()
    event = episode["tool_events"][0]
    event["is_error"] = True
    value = inputs.history_structure(1, [event], [10])
    assert value["had_failed_run_program"] is True
    assert value["had_successful_run_program"] is False
    assert value["run_program_error_count"] == 1
    assert value["executed_programs_and_outputs"][0]["is_error"] is True


def panel():
    result = []
    for (direction, group), counts in inputs.EXPECTED_ACTION_COUNTS.items():
        for category, count in zip(inputs.ACTION_ORDER, counts, strict=True):
            for index in range(count):
                key = f"{group}-{sum(counts[:inputs.ACTION_ORDER.index(category)]) + index}"
                result.append(dict(condition_id=f"{direction}-{key}", task_key=key,
                    direction=direction, group=group,
                    actor_model="P" if direction == "P_from_L" else "L",
                    first_action_category=category,
                    remaining_model_calls=inputs.residual_budget(0, category)))
    return result


def test_exact_panel_preserves192_conditions_with961_cap():
    value = inputs.panel_budget(panel())
    assert (value["unique_tasks"], value["conditional_trajectories"], value["direct_submit_candidates"],
            value["continued_nonterminal_branches"], value["no_tool_call_terminations"],
            value["exact_new_model_call_upper_bound"]) == (96, 192, 147, 31, 14, 961)


def test_missing_condition_blocks_without_dropping_from_denominator():
    rows = panel()
    rows.pop()
    with pytest.raises(ValueError):
        inputs.panel_budget(rows)


def test_L_nonterminal_cannot_create_new_L_inference_budget():
    rows = panel()
    row = next(r for r in rows if r["first_action_category"] == "compliant_nonterminal_candidate")
    row["actor_model"] = "L"
    with pytest.raises(ValueError):
        inputs.panel_budget(rows)
