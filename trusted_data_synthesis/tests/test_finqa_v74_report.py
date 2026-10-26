"""Two pure controls for final-report gating and conditional interpretation."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
import finqa_v74_report as report


def test_report_cannot_read_interim_scores_before_COMPLETE():
    class Reader:
        def read(self,path):
            assert str(path).endswith("closeout/record.json")
            return dict(status="RUNNING",active_workers=1,accepted_jobs=[])
    with pytest.raises(ValueError,match="not complete"):
        report.extract(Path("/fixture"),reader=Reader())


def test_render_preserves_full_denominators_actual_cost_and_initial_history_caveat():
    states=dict(I=3,W=2,R=43,UNKNOWN=0)
    metric={name:dict(correct=43,complete_dataset_mean=43/48) for name in ("execution_accuracy","program_accuracy")}
    pair=dict(new_correct_known_pairs=43,lost_correct_known_pairs=0,numerator=43,difference=43/48,
              unknown_pair_count=0,program_accuracy=dict(new_correct_known_pairs=43,lost_correct_known_pairs=0))
    sub=dict(denominator=16,states=states,valid_terminal_submit_count=45,costs=dict(new_model_calls=2))
    direct=dict(denominator=45,native_nonexecutable=0,native_missing_or_invalid_submission=0,
                executable_wrong=2,executable_correct=43,unknown=0)
    panel=dict(metrics=metric,states=states,by_first_response={k:sub for k in report.CATEGORIES},
               original_submit_candidates=direct,paired_to_old_original={k:pair for k in ("P","L")})
    costs=dict(new_model_calls=31,new_tool_calls=209,reconstruction_tool_calls=158,reused_first_responses=192,
        reused_first_response_tool_calls=178,historical_model_calls_in_prefix=158,
        total_path_model_calls_including_prefix_and_reused=381,budget_exhausted=0,context_exceeded=0)
    final=dict(id="final",status="COMPLETE",panels={g:{d:panel for d in report.DIRECTIONS} for g in ("F","K")},
               costs=costs,unknown_native_results=0)
    context=dict(rows=[dict(group="F",source="hP",source_b_counts={"0":3,"1":44,"2":1},
        historical_tool_events=46,successful_run_program=45,failed_run_program=0,read_source=1,list_sources=0)],
        total_historical_tool_events=158,actual_prompt_token_identical_count=3,programs_and_outputs_identical_count=59,
        F_selected_clusters=48,K_selected_clusters=48,shared_F_K_cluster_count=9,union_source_cluster_count=87,
        nonterminal_b0_count=31,nonterminal_condition_count=31)
    execution=dict(closeout=dict(status="COMPLETE",finished_epoch=1792978200,actual_attempts=[{}]),
        worker=dict(launch=dict(gpu_index=6,started_epoch=1792978000),accepted=dict(attempt=1),
            actual_exit=dict(observed_epoch=1792978100),resources=dict(peak_allocated_bytes=16*1024**3,
                peak_rss_bytes=16*1024**3,minimum_boundary_free_bytes=20*1024**3,
                minimum_host_available_bytes=600*1024**3,all_gates_passed=True)))
    value=dict(final_summary=final,execution=execution,context_facts=context,execution_root="/fixture",
        protocol_id="protocol",source_commit="source",id="report",read_policy=dict(source_JSON_count=13))
    text=report.render_report(value)
    assert "实际新增P模型调用31次" in text and "工具状态重建158次" in text
    assert "31/31条来源b=0" in text and "旧L成绩仍是431/883" in text
    assert "合并87个独特簇" in text and "不证明历史是唯一根因" in text
    assert "无自身waitpid码，不补造" in text and "PA正确/分母" in text
    assert report.count(None)=="NA"
