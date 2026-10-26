"""CPU controls for mixed-lineage native score barriers, denominators and costs."""
import copy
import importlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
e = importlib.import_module("finqa_v74_evaluation")
spec = importlib.util.spec_from_file_location("_v74_stats_test", Path(e.__file__).with_name("finqa_v54_statistics.py"))
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


def native(state):
    return dict(status="unknown" if state == "UNKNOWN" else "invalid_prediction" if state == "I" else "scored",
        program_executable=None if state == "UNKNOWN" else state != "I",
        reason="nonexecutable_submission" if state == "I" else "test_unknown" if state == "UNKNOWN" else None,
        native=dict(execution_accuracy=None if state == "UNKNOWN" else int(state == "R"),
                    program_accuracy=None if state == "UNKNOWN" else int(state == "R")))


def fixture():
    tasks = [dict(task_key=f"draw/{group}{n:02d}", original_task_key=f"finqa/{group}{n:02d}",
                  group=group, source_group={"group": f"shared{n}", "level": "report"})
             for group in e.GROUPS for n in range(48)]
    conditions, rows, outcomes = [], [], {}
    for direction in e.DIRECTIONS:
        for task in tasks:
            n = int(task["task_key"][-2:])
            counts = e.EXPECTED[direction, task["group"]]
            category = e.CATEGORIES[0] if n < counts[0] else e.CATEGORIES[1] if n < sum(counts[:2]) else e.CATEGORIES[2]
            first_b = 2 if direction == "L_from_P" else 0
            c = dict(task, condition_id=direction+task["task_key"], direction=direction,
                     first_action_category=category, source_turn_index=first_b,
                     remaining_model_calls=31-first_b if category == e.CATEGORIES[1] else 0)
            calls = 2 if category == e.CATEGORIES[1] else 0
            stop = "no_tool_call" if category == e.CATEGORIES[2] else "final_answer"
            events = [] if stop == "no_tool_call" else [dict(name="submit_program",is_error=False,
                raw_output={"program": "subtract(8, 2)"})]
            outcome = dict(protocol_id="p",inputs_id="i",condition_id=c["condition_id"],status="COMPLETE",
                episode=dict(stop_reason=stop,tool_events=events,final_program="subtract(8, 2)",
                    all_provider_calls_settled=True,actual_model_calls=first_b+1+calls),
                new_model_calls=calls,new_tool_calls=calls+int(category!=e.CATEGORIES[2]),
                reconstruction_tool_calls=first_b,reused_first_response_tool_calls=int(category!=e.CATEGORIES[2]),
                budget_exhausted=False)
            row=e._row(c,outcome,native("I" if stop=="no_tool_call" else "R"))
            conditions.append(c);rows.append(row);outcomes[c["condition_id"]]=outcome
    old={name:dict(results=[dict(task,native=native("I" if name=="L" and task["group"]=="F" else "R"))
                                for task in tasks]) for name in ("P","L")}
    return {"id":"i","tasks":tasks,"conditions":conditions,"context_structure":{"intersection_count":48}}, rows, old, outcomes


def test_fixed192_full_denominators_direct_and_nonterminal_readouts():
    bundle,rows,old,_=fixture()
    out=e.summarize(bundle,rows,old,stats=stats)
    assert out["status"]=="COMPLETE" and out["logical_native_scores"]==192
    assert out["panels"]["F"]["L_from_P"]["metrics"]["states"]==dict(I=3,W=0,R=45,UNKNOWN=0)
    panel=out["panels"]["F"]["P_from_L"]
    assert panel["by_first_response"][e.CATEGORIES[1]]["correct_terminal_results"]==26
    assert panel["paired_to_old_original"]["L"]["new_correct_known_pairs"]==38
    assert panel["paired_to_old_original"]["P"]["lost_correct_known_pairs"]==10
    assert not out["automatic_training_gate"] and not out["old_L_dev431_of883_changed"]


def test_new_computation_cost_separates_prefix_reuse_and_tools():
    bundle,rows,old,_=fixture();out=e.summarize(bundle,rows,old,stats=stats)
    costs=out["costs"]
    assert costs["new_model_calls"]==62 and costs["reused_first_responses"]==192
    assert costs["historical_model_calls_in_prefix"]==192
    assert costs["total_path_model_calls_including_prefix_and_reused"]==446
    assert costs["reconstruction_tool_calls"]==192 and costs["new_tool_calls"]==240
    assert costs["reused_first_response_tool_calls"]==178


def test_unknown_score_keeps48_and_blocks_paired_complete_panel_effect():
    bundle,rows,old,_=fixture();rows[0]["native"]=native("UNKNOWN")
    out=e.summarize(bundle,rows,old,stats=stats)
    panel=out["panels"]["F"]["L_from_P"]
    assert out["status"]=="COMPLETE_WITH_UNKNOWN" and out["unknown_native_results"]==1
    assert panel["metrics"]["execution_accuracy"]["denominator"]==48
    assert panel["metrics"]["execution_accuracy"]["complete_dataset_mean"] is None
    assert panel["paired_to_old_original"]["P"]["difference"] is None
    assert panel["paired_to_old_original"]["P"]["program_accuracy"]["complete_panel_net"] is None


def test_submit_static_legality_executable_wrong_and_nonexecution_are_separate():
    bundle,rows,old,_=fixture()
    rows[0]["native"]=native("W");rows[1]["native"]=native("I")
    out=e.summarize(bundle,rows,old,stats=stats)
    direct=out["panels"]["F"]["L_from_P"]["original_submit_candidates"]
    assert direct==dict(denominator=45,native_nonexecutable=1,native_missing_or_invalid_submission=0,
        executable_wrong=1,executable_correct=43,unknown=0,static_legality_is_not_native_correctness=True)


def test_empty_predeclared_subgroup_is_NA_not_zero_accuracy():
    bundle,rows,old,_=fixture();out=e.summarize(bundle,rows,old,stats=stats)
    empty=out["panels"]["K"]["L_from_P"]["by_first_response"][e.CATEGORIES[1]]
    assert empty["denominator"]==0 and empty["metrics"]["execution_accuracy"] is None
    assert empty["metrics"]["status"]=="NA_EMPTY_PREDECLARED_SUBGROUP"


@pytest.mark.parametrize("mutation",["missing_condition","duplicate_condition","changed_first_class","wrong_group"])
def test_frozen_cohort_or_action_count_cannot_silently_change(mutation):
    bundle,rows,old,_=fixture()
    if mutation=="missing_condition":bundle["conditions"].pop()
    elif mutation=="duplicate_condition":bundle["conditions"][-1]=copy.deepcopy(bundle["conditions"][0])
    elif mutation=="changed_first_class":bundle["conditions"][0]["first_action_category"]=e.CATEGORIES[1]
    else:bundle["tasks"][0]["group"]="K"
    with pytest.raises(ValueError):e.summarize(bundle,rows,old,stats=stats)


def test_native_row_retains_original_budget_not_fresh32_calls():
    bundle,_,_,outcomes=fixture()
    condition=next(c for c in bundle["conditions"] if c["first_action_category"]==e.CATEGORIES[1])
    c=copy.deepcopy(condition);c["source_turn_index"]=29;c["remaining_model_calls"]=2
    outcome=copy.deepcopy(outcomes[c["condition_id"]]);outcome["episode"]["actual_model_calls"]=32
    assert e._row(c,outcome,native("R"))["maximum_new_model_calls"]==2
    outcome["new_model_calls"]=3;outcome["episode"]["actual_model_calls"]=33
    with pytest.raises(ValueError,match="residual"):e._row(c,outcome,native("R"))


def test_no_call_or_submit_cannot_receive_second_chance():
    bundle,_,_,outcomes=fixture();c=bundle["conditions"][0]
    outcome=copy.deepcopy(outcomes[c["condition_id"]]);outcome["new_model_calls"]=1
    outcome["episode"]["actual_model_calls"]+=1
    with pytest.raises(ValueError):e._row(c,outcome,native("R"))


def test_missing_or_unsettled_terminal_blocks_before_runtime_or_private_access(monkeypatch,tmp_path):
    bundle,_,_,outcomes=fixture()
    fake=SimpleNamespace(ROOT=tmp_path,read_ref=lambda _:{"protocol_id":"p","active_workers":[],
                         "accepted_jobs":{"P.continuation":{}}})
    monkeypatch.setattr(e,"_binding",lambda:fake)
    monkeypatch.setattr(e,"_runtime",lambda:pytest.fail("must not load private scorer before complete terminal roster"))
    outcomes.pop(next(iter(outcomes)))
    with pytest.raises(ValueError,match="all192"):e.evaluate({"id":"p"},bundle,outcomes,
        all_jobs_exit_barrier={"path":"barrier","sha256":"sha"},root=tmp_path)


def test_active_worker_blocks_before_private_score(monkeypatch,tmp_path):
    bundle,_,_,outcomes=fixture()
    fake=SimpleNamespace(ROOT=tmp_path,read_ref=lambda _:{"protocol_id":"p","active_workers":[123],
                         "accepted_jobs":{"P.continuation":{}}})
    monkeypatch.setattr(e,"_binding",lambda:fake)
    monkeypatch.setattr(e,"_runtime",lambda:pytest.fail("private runtime must not be reached"))
    with pytest.raises(ValueError,match="actually exited"):e.evaluate({"id":"p"},bundle,outcomes,
        all_jobs_exit_barrier={"path":"barrier","sha256":"sha"},root=tmp_path)


def test_native_scorer_does_not_force_a_single_provider_across_mixed_turns():
    # This fixture changes only top-level successor descriptor. Original turns,
    # receipts and settlement contents remain untouched; native math is identical.
    from test_finance_v7_public_reasoning import mocked_episode
    from test_finance_public_reasoning import call
    from test_finance_research_datasets import finqa_record
    from trusted_synthesis.finance_research.datasets import adapt_finqa
    from trusted_synthesis.finance_research.v6_task import score_public_reasoning_program
    bundle=adapt_finqa([finqa_record()],split="train",revision="V74-synthetic-native-control")[0]
    episode,_=mocked_episode(bundle,[("R: Compute the difference.",[call("run_program",{"program":"subtract(8, 2)"})]),
                                    ("U: Submit observed calculation.",[call("submit_program",{"program":"subtract(8, 2)"})])])
    mixed=episode.model_copy(update={"provider":episode.provider.model_copy(update={"point_id":"explicit-successor"})})
    assert mixed.turns==episode.turns and mixed.call_settlements==episode.call_settlements
    score=score_public_reasoning_program(bundle,mixed)
    assert score["status"]=="scored" and score["native"]==dict(execution_accuracy=1.0,program_accuracy=1.0)


def test_durable_native_rows_reused_without_rescoring_or_reopening_private_refs(monkeypatch,tmp_path):
    import hashlib
    import json
    bundle,_,old,outcomes=fixture()
    bundle["old_scores"]={name:{"path":name} for name in ("P","L")}
    barrier={"protocol_id":"p","active_workers":[],"accepted_jobs":{"P.continuation":{}}}
    def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    def read(path):return json.loads(Path(path).read_text())
    def publish(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        obj=dict(value,id=digest(value));path.write_text(json.dumps(obj));return obj
    fake=SimpleNamespace(ROOT=tmp_path,read_ref=lambda ref:old[ref["path"]] if ref["path"] in old else barrier,
        checked=read,publish=publish,digest=digest,
        entry=lambda path:{"path":str(path),"sha256":digest(read(path)),"id":read(path)["id"]})
    monkeypatch.setattr(e,"_binding",lambda:fake)
    from trusted_synthesis.finance_research import settlement
    monkeypatch.setattr(settlement,"episode_is_complete",lambda _:True)
    score_calls=[];private_reads=[]
    final=SimpleNamespace(score_public_reasoning_program=lambda task,episode:score_calls.append(task) or native("R"))
    contracts=SimpleNamespace(Episode=SimpleNamespace(model_validate=lambda obj:obj))
    monkeypatch.setattr(e,"_runtime",lambda:(SimpleNamespace(stats=stats),final,contracts))
    def bundles(*args):
        private_reads.append(True)
        return {c["original_task_key"]:c["original_task_key"] for c in bundle["conditions"]}
    monkeypatch.setattr(e,"_load_bundles",bundles)
    ref={"path":"barrier","sha256":"sha"}
    first=e.evaluate({"id":"p"},bundle,outcomes,all_jobs_exit_barrier=ref,root=tmp_path)
    assert len(score_calls)==192 and len(private_reads)==1
    second=e.evaluate({"id":"p"},bundle,outcomes,all_jobs_exit_barrier=ref,root=tmp_path)
    assert second==first and len(score_calls)==192 and len(private_reads)==1
