"""V75 selection has no outcome input, keeps task/source boundaries and caps."""
from pathlib import Path
import copy
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v75_collection as collection


def rows():
    return [dict(task_id=str(i),task_key='finqa/'+str(i),original_task_key='finqa/'+str(i),
        source_group=dict(group='report'+str(i//2),level='report'),company='C'+str(i%3),report='report'+str(i//2)) for i in range(300)]


def test_fixed_cluster_round_robin_ignores_candidate_input_order():
    source=rows();selected=collection.select(source)
    assert selected==collection.select(list(reversed(source)))
    assert len(selected)==128 and len({r['source_group']['group'] for r in selected})==128
    assert source==rows()


def test_selection_rejects_duplicate_missing_or_altered_budget():
    for value,count in ((rows()[:127],128),(rows(),129),(rows()+[rows()[0]],128)):
        with pytest.raises(ValueError):collection.select(value,count)


def test_fixed_shards_cover_each_task_once_per_phase_and_no_new_budget():
    selected=collection.select(rows());jobs=collection.jobs(dict(tasks=selected))
    assert len(jobs)==6 and sum(j['maximum_model_calls'] for j in jobs.values())==12160
    for phase in collection.PHASES:
        matching=[j for j in jobs.values() if j['phase']==phase]
        task_ids=[key for j in matching for key in j['task_ids']]
        assert len(task_ids)==len(set(task_ids))==128
        assert set(task_ids)=={r['task_id'] for r in selected}
    assert jobs['L.initial.shard0']['task_ids']==jobs['P.initial.shard0']['task_ids']==jobs['P.post.shard0']['task_ids']


def test_source_overlap_not_hidden_by_distinct_task_ids():
    selected=rows()[:1];development=copy.deepcopy(selected);development[0].update(task_id='new',original_task_key='finqa/new')
    result=collection.overlap(selected,rows(),development,development)
    row=result['selected128_vs_development883']
    assert row['task_id_overlap']==[] and row['source_cluster_count']==row['report_count']==1
    assert result['task_disjointness_not_report_or_company_independence']


def test_collection_role_is_sft_with_original_native_greedy_limits():
    cfg=collection.config()
    assert (cfg['role'],cfg['tier'],cfg['max_steps'],cfg['max_new_tokens'],cfg['context_limit'])==('sft','EVAL_NATIVE',32,2048,24576)
    assert cfg['temperature']==0.0 and cfg['top_p']==1.0 and cfg['top_k']==0
