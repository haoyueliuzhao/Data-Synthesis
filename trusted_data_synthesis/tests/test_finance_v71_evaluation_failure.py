"""Focused changed contracts: zero-outer snapshots, paired metrics, explanations."""
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v71_evaluation as evaluation
import finqa_v71_failure_analysis as failure


@pytest.fixture
def stats(monkeypatch):
    path = Path(evaluation.__file__).with_name("finqa_v54_statistics.py")
    spec = importlib.util.spec_from_file_location("_v71_native_stats_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(evaluation, "_original", lambda: SimpleNamespace(stats=module))
    return module


def row(state, task="a"):
    return dict(task_key=f"draw20260928/finqa/{task}", original_task_key=f"finqa/{task}",
        native=dict(status="unknown" if state == "UNKNOWN" else "invalid_prediction" if state == "I" else "scored",
            program_executable=None if state == "UNKNOWN" else state != "I",
            reason="missing_or_invalid_submission" if state == "I" else None,
            native=dict(execution_accuracy=None if state == "UNKNOWN" else int(state == "R"),
                        program_accuracy=None if state == "UNKNOWN" else int(state == "R"))),
        actual_model_calls=1, stop_reason="no_tool_call")


def report(states):
    return dict(denominator=len(states), results=[row(state, str(i)) for i, state in enumerate(states)])


def test_exact_new_dose_and_readonly_comparator_contract():
    jobs = evaluation.planned_jobs()
    assert set(jobs) == {"step1192.cal_greedy", "step1490.cal_greedy", "step1490.dev_greedy"}
    assert sum(job["denominator"] for job in jobs.values()) == 1123
    assert all(job["arm"] == "Fixed894" and job["seed"] == 137 for job in jobs.values())
    contract = evaluation.evaluation_contract()
    assert contract["applied_new_outer_updates"] == 0
    assert not contract["Full_rescoring"] and not contract["baseline_rescoring"]
    assert not contract["dev1192_evaluated"] and not contract["intermediate_score_selection"]


def test_fixed_snapshot_checks_exact_distribution_after_loading(monkeypatch):
    state, context, calls = {"step": 1490, "arm": "C-only"}, {"fixed_pi": "pi0"}, []
    fake = SimpleNamespace(runtime=lambda: (None, "rt"), read_checkpoint=lambda ref, rt: state,
        validate_point_state=lambda value, step, rt: value,
        assert_fixed_state=lambda value, point, rt: calls.append((value, point, rt)))
    monkeypatch.setitem(sys.modules, "finqa_v71_training", fake)
    monkeypatch.setattr(evaluation, "checked", lambda path: context)
    assert evaluation._snapshot_state({"path": "endpoint"}, 1490) is state
    assert calls == [(state, context, "rt")]


@pytest.mark.parametrize("outers", [1, 2])
def test_generation_rejects_training_that_applied_any_outer(tmp_path, monkeypatch, outers):
    completed = dict(protocol_id="P", status="COMPLETE", seed=137, arm="Fixed894",
        initial_step=894, final_step=1192, optimizer_updates=298, outer_updates=outers,
        fixed_distribution_digest="pi", distribution_digest="pi", final_checkpoint={})
    monkeypatch.setattr(evaluation, "_accepted", lambda *a: ({}, {"final_checkpoint": {}}))
    monkeypatch.setattr(evaluation, "checked", lambda path: completed)
    with pytest.raises(ValueError, match="fixed-distribution"):
        evaluation._training_snapshot(tmp_path, evaluation.planned_jobs()["step1192.cal_greedy"], {"id": "P"})


def test_pairing_orientation_full_minus_fixed_and_both_vs_parent(stats):
    baseline, full, fixed = report("RWI"), report("IWR"), report("RRW")
    value = evaluation.compare_reports(fixed, full, baseline)
    pair = value["paired_execution"]["Full_minus_Fixed894"]
    assert (pair["new_correct"], pair["lost_correct"], pair["numerator"]) == (1, 2, -1)
    assert pair["transitions"]["R->I"] == 1 and pair["transitions"]["W->R"] == 1
    assert value["paired_execution"]["Fixed894_minus_baseline894"]["numerator"] == 1
    assert value["paired_program_accuracy"]["Full_minus_Fixed894"]["numerator"] == -1


def test_pairing_rejects_reordered_cohort_and_unknown(stats):
    full, fixed, baseline = report("RWI"), report("RWI"), report("RWI")
    full["results"].reverse()
    with pytest.raises(ValueError, match="task/draw order"):
        evaluation.compare_reports(fixed, full, baseline)
    with pytest.raises(ValueError, match="UNKNOWN"):
        evaluation.compare_reports(report(["R", "W", "UNKNOWN"]), baseline, baseline)


@pytest.mark.parametrize("H,case", [(525, "fixed_maintains_or_improves_baseline_Full_lower"),
    (400, "both_decline_Full_more"), (371, "equal_total_correct_not_equivalence"),
    (350, "Full_positive_increment_both_below_baseline")])
def test_both_primary_estimands_always_reported(H, case):
    value = evaluation.primary_estimands(dict(denominator=883, native_metrics={name:
        {"execution_accuracy": {"correct": count}} for name, count in
        (("Fixed894", H), ("Full", 371), ("baseline894", 525))}))
    assert value["delta_adaptive"]["numerator"] == 371 - H
    assert value["delta_fixed"]["numerator"] == H - 525
    assert value["descriptive_case"] == case and value["advancement_threshold"] is None
    assert not value["equality_implies_equivalence"]


def episode(turns, events=(), stop="no_tool_call"):
    return dict(dataset="finqa", task_id="a", turns=turns, tool_events=list(events),
                stop_reason=stop, actual_model_calls=len(turns), all_provider_calls_settled=True)


def turn(raw="plain text", calls=(), finish="stop", eos=True):
    return dict(raw_text=raw, tool_calls=list(calls), receipt=dict(call_id="call",
        raw_response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        raw_generated_token_ids=[1], finish_reason=finish, actual_eos=eos))


def test_first_recoverable_error_kept_separate_from_terminal_missing_submission():
    call = dict(call_id="one", name="run_program", arguments="{}")
    turns = [turn("tool", [call]), turn("plain")]
    events = [dict(call_id="one", name="run_program", is_error=True,
                   raw_output={"error": "ToolInputError", "message": "invalid linear FinQA program syntax"})]
    sample = row("I"); sample["actual_model_calls"] = 2
    value = failure.inspect_episode(sample, episode(turns, events),
        parse=lambda raw, prefix: ("G_accepted_tool_envelopes", [call]) if raw == "tool"
                                 else ("A_no_opening_envelope", []))
    assert value["first_failure_event"]["category"] == "program_nonexecutable"
    assert value["terminal_category"] == "missing_terminal_submission"


def test_length_boundary_and_bad_envelope_are_not_silently_merged():
    value = failure.inspect_episode(row("I"), episode([turn("<tool_call>", finish="length", eos=False)]),
        parse=lambda *a: ("E_missing_closing_envelope", []))
    assert value["terminal_category"] == "truncation_or_interaction_budget"
    assert value["first_failure_event"]["category"] == "invalid_envelope_or_arguments"
    assert len(value["all_observed_failures"]) == 2


def test_parser_disagreement_blocks_explanation_not_repair():
    with pytest.raises(ValueError, match="disagrees"):
        failure.inspect_episode(row("I"), episode([turn()]),
                                parse=lambda *a: ("G_accepted_tool_envelopes", [{"call_id": "extra"}]))


def test_nonexecutable_native_submission_is_terminal_even_without_prior_errors():
    sample = row("I"); sample["native"]["reason"] = "nonexecutable_submission"
    value = failure.inspect_episode(sample, episode([turn()]), parse=lambda *a: ("A_no_opening_envelope", []))
    assert value["terminal_category"] == "program_nonexecutable"


def test_example_selection_is_fixed_task_sort_and_never_depends_on_raw_content():
    before, after = [], []
    for start, end in (("R", "I"), ("W", "I"), ("I", "I"), ("R", "R")):
        for index in reversed(range(8)):
            task = start + end + str(index)
            before.append(row(start, task)); after.append(row(end, task))
    selected = failure.select_pairs(before, after)
    assert len(selected) == 24
    assert all(item["task_key"][-1] in "012345" for item in selected)


def test_explicit_stop_precedes_any_analysis_or_private_runtime(tmp_path, monkeypatch):
    (tmp_path / "STOP").write_text("stop")
    monkeypatch.setattr(evaluation, "_protocol", lambda root: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="STOP"):
        evaluation.finish(tmp_path)
