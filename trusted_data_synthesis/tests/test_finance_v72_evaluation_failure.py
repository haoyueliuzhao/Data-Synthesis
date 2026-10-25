"""Changed parent/low-LR snapshots, exact new dose and paired effect semantics."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v72_evaluation as evaluation
import finqa_v72_failure_analysis as failure


@pytest.fixture
def stats(monkeypatch):
    path = Path(evaluation.__file__).with_name("finqa_v54_statistics.py")
    spec = importlib.util.spec_from_file_location("_v72_native_stats_test",path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(evaluation,"_original",lambda:SimpleNamespace(stats=module))
    return module


def row(state,task="a"):
    return dict(task_key=f"draw20260928/finqa/{task}",original_task_key=f"finqa/{task}",
        native=dict(status="unknown" if state=="UNKNOWN" else "invalid_prediction" if state=="I" else "scored",
            program_executable=None if state=="UNKNOWN" else state!="I",
            reason="missing_or_invalid_submission" if state=="I" else None,
            native=dict(execution_accuracy=None if state=="UNKNOWN" else int(state=="R"),
                        program_accuracy=None if state=="UNKNOWN" else int(state=="R"))))


def report(states):
    return dict(denominator=len(states),results=[row(state,str(index)) for index,state in enumerate(states)])


def test_fixed_three_job1886_dose_and_no_early_parent_score_selection():
    jobs = evaluation.planned_jobs()
    assert set(jobs)=={"step1192.dev_greedy","step1490.cal_greedy","step1490.dev_greedy"}
    assert sum(job["denominator"] for job in jobs.values())==1886
    assert jobs["step1192.dev_greedy"]["arm"]=="Parent1192"
    assert jobs["step1192.dev_greedy"]["algorithm"]=="inherited_parent_evaluation"
    assert all(job["arm"]=="LowLR1192" for key,job in jobs.items() if key.startswith("step1490"))
    contract=evaluation.evaluation_contract()
    assert contract["parent_dev_generation_may_overlap_low_lr_training"]
    assert not contract["parent_calibration_rescoring"] and not contract["high_lr_rescoring"]
    assert not contract["partial_scores_influence_training"] and not contract["Full1192_dev_generated"]
    assert contract["low_lr"]==1e-5 and contract["original_parent_lr"]==1e-4
    assert "all 4" in contract["before_private_scoring"]


def _fake_training(monkeypatch):
    original={"path":"original1192","actual_state_digest":"parent"}
    states={"original1192":{"step":1192,"lr":1e-4},"new1490":{"step":1490,"lr":1e-5},
            "intervened1192":{"step":1192,"lr":1e-5}}
    calls=[]
    def parent(state,rt):
        assert state["step"]==1192 and state["lr"]==1e-4
        calls.append("parent")
    def low(state,step,context,rt):
        assert state["step"]==step==1490 and state["lr"]==1e-5 and context=="fixed_context"
        calls.append("low")
    fake=SimpleNamespace(runtime=lambda:(None,"rt"),initial_checkpoint=lambda:original,
        read_checkpoint=lambda ref,rt:states[ref["path"]],validate_parent_state=parent,
        checked_window=lambda root,start:"fixed_context",validate_low_lr_state=low)
    monkeypatch.setitem(sys.modules,"finqa_v72_training",fake)
    return original,states,calls


def test_parent_generation_uses_original_state_and_low_endpoint_uses_intervened_learning_rule(monkeypatch):
    original,states,calls=_fake_training(monkeypatch)
    assert evaluation._snapshot_state(original,1192) is states["original1192"]
    assert evaluation._snapshot_state({"path":"new1490"},1490) is states["new1490"]
    assert calls==["parent","low"]


def test_parent_generation_rejects_intervention_checkpoint_even_at_same_step(monkeypatch):
    _fake_training(monkeypatch)
    with pytest.raises(ValueError,match="original high-lr1192"):
        evaluation._snapshot_state({"path":"intervened1192"},1192)


def test_parent_and_low_lr_model_point_identity_names_the_actual_condition():
    jobs=evaluation.planned_jobs()
    parent=evaluation._model_point_id(jobs["step1192.dev_greedy"],{"id":"p"},{"path":"parent"})
    low=evaluation._model_point_id(jobs["step1490.dev_greedy"],{"id":"p"},{"path":"low"})
    assert parent.startswith("v72-Parent1192-evaluation:")
    assert low.startswith("v72-LowLR1192-evaluation:") and parent!=low


def test_parent_snapshot_does_not_depend_on_new_training_exit(tmp_path,monkeypatch):
    original,_,_=_fake_training(monkeypatch)
    source=tmp_path/"oldV71"
    monkeypatch.setattr(evaluation.binding,"V71_ROOT",source)
    directory=source/"points/step0894/train"
    ref={"path":str(directory/"completed/record.json"),"sha256":"hash"}
    complete=dict(arm="Fixed894",initial_step=894,final_step=1192,optimizer_updates=298,
                  outer_updates=0,final_checkpoint=original)
    monkeypatch.setattr(evaluation,"checked",lambda path:
        {"id":evaluation.binding.V71_PROTOCOL_ID} if path==source/"protocol/record.json" else complete)
    monkeypatch.setattr(evaluation.binding,"entry",lambda path:ref)
    calls=[]
    def accepted(root,job,directory,protocol):
        calls.append((root,job))
        return {"result":ref},{"final_checkpoint":original,"branch_result":ref}
    monkeypatch.setattr(evaluation,"_accepted",accepted)
    result,proof=evaluation._training_snapshot(tmp_path,evaluation.planned_jobs()["step1192.dev_greedy"],
        {"initial_parent":{"checkpoint":original}})
    assert result==original and calls==[(source,"step894.train")]


@pytest.mark.parametrize("outer",[1,2])
def test_low_endpoint_rejects_new_outer(tmp_path,monkeypatch,outer):
    _fake_training(monkeypatch)
    completed=dict(protocol_id="P",status="COMPLETE",seed=137,arm="LowLR1192",
        initial_step=1192,final_step=1490,optimizer_updates=298,outer_updates=outer,
        fixed_distribution_digest="pi",distribution_digest="pi",final_checkpoint={})
    monkeypatch.setattr(evaluation,"checked",lambda path:completed)
    monkeypatch.setattr(evaluation,"_accepted",lambda *args:({}, {"final_checkpoint":{}}))
    with pytest.raises(ValueError,match="zero-outer"):
        evaluation._training_snapshot(tmp_path,evaluation.planned_jobs()["step1490.dev_greedy"],{"id":"P"})


def test_low_endpoint_metadata_rejects_unmodified_learning_rate(tmp_path,monkeypatch):
    _fake_training(monkeypatch)
    completed=dict(protocol_id="P",status="COMPLETE",seed=137,arm="LowLR1192",
        initial_step=1192,final_step=1490,optimizer_updates=298,outer_updates=0,
        learning_rate=1e-4,initial_learning_rate=1e-4,
        fixed_distribution_digest="pi",distribution_digest="pi",final_checkpoint={})
    monkeypatch.setattr(evaluation,"checked",lambda path:completed)
    monkeypatch.setattr(evaluation,"_accepted",lambda *args:({}, {"final_checkpoint":{}}))
    with pytest.raises(ValueError,match="low-lr"):
        evaluation._training_snapshot(tmp_path,evaluation.planned_jobs()["step1490.dev_greedy"],{"id":"P"})


def test_six_pair_orientations_and_program_gain_loss(stats):
    low,high,parent,baseline=report("RRW"),report("IWR"),report("RWI"),report("WWW")
    value=evaluation.compare_reports(low,high,parent,baseline)
    pairs=value["paired_execution"]
    assert len(pairs)==6
    assert (pairs["LowLR1490_minus_HighLR1490"]["new_correct"],
            pairs["LowLR1490_minus_HighLR1490"]["lost_correct"],
            pairs["LowLR1490_minus_HighLR1490"]["numerator"])==(2,1,1)
    assert pairs["LowLR1490_minus_HighLR1490"]["transitions"]["I->R"]==1
    assert pairs["LowLR1490_minus_parent1192"]["numerator"]==1
    assert pairs["HighLR1490_minus_parent1192"]["numerator"]==0
    assert pairs["parent1192_minus_baseline894"]["numerator"]==1
    assert value["paired_program_accuracy"]["LowLR1490_minus_HighLR1490"]["new_correct"]==2


def test_unknown_and_reordered_tasks_cannot_reduce_denominator(stats):
    with pytest.raises(ValueError,match="UNKNOWN"):
        evaluation.compare_reports(report(["R","UNKNOWN"]),report("RW"),report("IW"),report("WW"))
    wrong=report("RW");wrong["results"].reverse()
    with pytest.raises(ValueError,match="task/draw order"):
        evaluation.compare_reports(report("RW"),wrong,report("IW"),report("WW"))


@pytest.mark.parametrize("B,L,case",[(500,450,"reduction_mitigates_decline_but_does_not_retain_parent"),
    (500,500,"parent_total_retained_without_net_new_correct"),
    (500,501,"observed_correct_count_above_parent_and_original_endpoint"),
    (350,360,"preset_lr_reduction_not_higher_than_original_endpoint"),
    (500,377,"preset_lr_reduction_not_higher_than_original_endpoint")])
def test_all_three_estimands_and_original_window_decomposition(B,L,case):
    comparison=dict(denominator=883,native_metrics={name:{"execution_accuracy":{"correct":count}}
        for name,count in (("LowLR1490",L),("parent1192",B),("HighLR1490",377),("baseline894",525))})
    value=evaluation.primary_estimands(comparison)
    assert value["delta_LR"]["numerator"]==L-377
    assert value["delta_retention"]["numerator"]==L-B
    assert value["delta_old_window"]["numerator"]==377-B
    split=value["original_fixed_path_decomposition"]
    assert split["first_window"]+split["last_window"]==split["total"]==-148
    assert split["exact_count_identity"] and not split["internal_causal_share"]
    assert value["descriptive_count_case"]==case and value["advancement_threshold"] is None
    assert not value["learning_rate_optimality_identified"] and not value["small_net_count_is_stable_improvement"]


def _invalid(key,source,terminal,first=None):
    return dict(task_key=key,native_state="I",from_parent1192=source,terminal_category=terminal,
                first_failure_event=first)


def test_parent_R_to_invalid_and_terminal_missing_are_distinct_from_first_error():
    rows=[_invalid("one","R","missing_terminal_submission",{"category":"program_nonexecutable"}),
          _invalid("two","R","truncation_or_interaction_budget"),
          _invalid("three","I","program_nonexecutable")]
    value=failure.summarize_invalid(rows,source_field="from_parent1192")
    assert value["R_to_I_count"]==2 and value["R_to_I_missing_valid_submission"]==1
    assert value["first_failure_counts"]=={"program_nonexecutable":1,"none_observed":2}
    assert value["terminal_counts"]["missing_terminal_submission"]==1
    assert value["unobserved_first_failure_is_not_UNKNOWN"]


def test_invalid_overlap_does_not_confuse_net_count_and_same_failure_set():
    high=[_invalid("one","R","missing_terminal_submission"),_invalid("two","W","program_nonexecutable")]
    low=[_invalid("one","R","truncation_or_interaction_budget"),_invalid("three","R","missing_terminal_submission")]
    value=failure.invalid_overlap(high,low)
    assert (value["both"],value["HighLR_only"],value["LowLR_only"])==(1,1,1)
    assert value["same_terminal_category"]==0
    assert value["terminal_category_pairs"]=={"missing_terminal_submission->truncation_or_interaction_budget":1}


def test_failure_rule_reuses_frozen_classifier_without_new_sample_budget():
    value=failure.policy()
    assert value["inherited_V71_classification_rules"]["terminal_and_first_failure_separate"]
    assert value["new_qualitative_pairs_selected"]==0
    assert value["high_lr1490_labels_reused_without_reopening_old_episodes"]
    assert value["new_model_calls"]==value["new_scoring_calls"]==0


def test_legacy_baseline_without_status_still_requires_complete_native_metrics():
    original=report(["R"]*883)
    original.update(coordinate="seed137/C1",feedback_batch=1,metrics={"states":{"UNKNOWN":0}})
    new=dict(original,status="COMPLETE")
    assert len(failure.validate_comparison_reports(new,new,new,original))==883
    bad=dict(original,metrics={"states":{"UNKNOWN":1}})
    with pytest.raises(ValueError,match="baseline native metrics"):
        failure.validate_comparison_reports(new,new,new,bad)


def test_explicit_stop_precedes_private_scoring_runtime(tmp_path,monkeypatch):
    (tmp_path/"STOP").write_text("stop")
    monkeypatch.setattr(evaluation,"_protocol",lambda root:pytest.fail("must stop before protocol/private runtime"))
    with pytest.raises(ValueError,match="STOP"):
        evaluation.finish(tmp_path)
