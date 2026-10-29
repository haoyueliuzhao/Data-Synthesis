"""Targeted CPU controls for V76 fixed endpoints, complete barriers and repair."""
from pathlib import Path
from types import SimpleNamespace
import copy
import importlib.util
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v76_binding as b
import finqa_v76_evaluation as e
import finqa_v76_analysis as a
import finqa_v76_preflight as p
import finqa_v75_analysis as previous
spec=importlib.util.spec_from_file_location('_v76_test_stats',Path(e.__file__).with_name('finqa_v54_statistics.py'))
stats=importlib.util.module_from_spec(spec);spec.loader.exec_module(stats)


def native(state):
    return dict(status='unknown' if state=='UNKNOWN' else 'invalid_prediction' if state=='I' else 'scored',
        program_executable=None if state=='UNKNOWN' else state!='I',
        native=dict(execution_accuracy=None if state=='UNKNOWN' else int(state=='R'),
                    program_accuracy=None if state=='UNKNOWN' else int(state=='R')))


def row(i,state='R'):
    return dict(task_key=f'draw20260928/finqa/C{i//4}/2000/task{i}',original_task_key=f'finqa/C{i//4}/2000/task{i}',
        native=native(state),source_group=dict(group=f'finqa:report:C{i//4}/2000',level='report'),
        stop_reason='no_tool_call' if state=='I' else 'final_answer',
        tool_call_count=0 if state=='I' else 1,actual_model_calls=1)


def report(step,correct):
    rows=[row(i,'R' if i<correct else 'I') for i in range(883)]
    return dict(step=step,denominator=883,results=rows,metrics=stats.native_metrics(rows,883))


def reports():
    return ({'A1490':report(1490,560),'A1788':report(1788,570),'D1788':report(1788,550)},
            {'S':report(1490,557),'P':report(1192,536),'B':report(1490,431)})


def stats_proxy(calls=None):
    def cluster(vectors,groups):
        if calls is not None:calls.append((vectors,groups))
        return dict(status='COMPLETE' if vectors else 'INCOMPLETE',comparisons={},same_weights_all_seeds_and_arms=True)
    return SimpleNamespace(native_state=stats.native_state,native_metrics=stats.native_metrics,
        paired_transitions=stats.paired_transitions,source_cluster_sensitivity=cluster)


def test_fixed_six_shards_exact_three_endpoints_and_dependencies():
    jobs=e.planned_jobs()
    assert len(jobs)==6 and sum(j['denominator'] for j in jobs.values())==2649
    assert {(j['arm'],j['step']) for j in jobs.values()}=={('A',1490),('A',1788),('D',1788)}
    assert jobs['A.step1490.dev_greedy.shard0']['dependencies']==['step1192.train']
    assert jobs['A.step1788.dev_greedy.shard0']['dependencies']==['step1490.train']
    assert jobs['D.step1788.dev_greedy.shard0']['dependencies']==['D.step1490.train']
    full=dict(denominator=883,tasks=[str(i) for i in range(883)],source_groups={str(i):str(i//4) for i in range(883)})
    halves=[e.shard_cohort(full,i) for i in (0,1)]
    assert [x['denominator'] for x in halves]==[442,441]
    assert not set(halves[0]['tasks'])&set(halves[1]['tasks'])
    assert set(halves[0]['tasks']+halves[1]['tasks'])==set(full['tasks'])
    altered=copy.deepcopy(next(iter(jobs.values())));altered['config']['temperature']=.5
    with pytest.raises(ValueError):e._job(altered)
    with pytest.raises(ValueError):e.panel_config('calibration')


def test_primary_contrast_is_final_adaptive_minus_same_length_fixed():
    new,old=reports();calls=[]
    out=a.compare_reports(new,old,stats=stats_proxy(calls),previous=previous)
    assert out['paired']['adaptive_A1788_minus_D1788']['execution_accuracy']['numerator']==20
    assert out['paired']['fixed_continuation_D1788_minus_S1490']['execution_accuracy']['numerator']==-7
    assert out['paired']['first_window_A1490_minus_S1490']['execution_accuracy']['numerator']==3
    assert out['paired']['final_A1788_minus_P1192']['execution_accuracy']['numerator']==34
    assert len(calls)==1 and len(calls[0][0])==10
    assert all('B1490' not in key for key in calls[0][0])
    assert out['historical_B1490_not_algorithm_control'] and not out['automatic_followup']


def test_unknown_preserves883_and_omits_only_affected_cluster_vectors():
    new,old=reports();new['A1788']['results'][0]['native']=native('UNKNOWN');calls=[]
    out=a.compare_reports(new,old,stats=stats_proxy(calls),previous=previous)
    assert out['status']=='COMPLETE_WITH_UNKNOWN'
    assert out['native_metrics']['A1788']['execution_accuracy']['denominator']==883
    assert out['paired']['adaptive_A1788_minus_D1788']['execution_accuracy']['difference'] is None
    assert len(calls[0][0])==6


@pytest.mark.parametrize('bad',['roster','groups','reused_score','step'])
def test_changed_comparison_binding_rejected(bad):
    new,old=reports()
    if bad=='roster':new['A1490']['results'][0]['task_key']='other'
    if bad=='groups':new['D1788']['results'][0]['source_group']['group']='other'
    if bad=='reused_score':old['S']['results'][0]['native']=native('W')
    if bad=='step':new['A1788']['step']=1490
    with pytest.raises(ValueError):a.compare_reports(new,old,stats=stats_proxy(),previous=previous)


def actual_consumption(material='m'):
    return dict(status='PASS',material_id=material,updates=298,task_exposures=1488,
        all298_actual_receipts_match_frozen_slots=True,student_prefix_target_count=0,
        teacher_target_tokens=30,teacher_input_positions=100,teacher_microbatches=3)


def material():
    return dict(id='m',dose=dict(updates=298,task_exposures=1488,
        planned_teacher_target_tokens=dict(initial=20,post=10),
        planned_teacher_input_positions=dict(initial=70,post=30),
        planned_teacher_microbatches=dict(initial=2,post=1)))


def train_records():
    return {key:dict(reference=dict(path=key,sha256='sha'),record=dict(status='COMPLETE',protocol_id='p',
        initial_step=start,final_step=end,optimizer_updates=298,outer_updates=outer,learning_rate=1e-5,
        actual_demonstration_consumption=actual_consumption(),planned_demonstration_dose=dict(start_step=start,end_step=end,updates=298,task_exposures=1488,fixed_teacher_material_id='m')))
        for key,start,end,outer in [('A1192',1192,1490,1),('A1490',1490,1788,1),('D1490',1490,1788,0)]}


def assemble(records=None):
    return a.assemble_final_summary(analysis=dict(status='COMPLETE'),protocol_id='p',barrier_ref={},reports={},reused={},
        train_records=train_records() if records is None else records,material_ref={},materials=material(),
        diagnostics={str(s):{} for s in (1192,1490,1788)},tracks={'1192_1490':{},'1490_1788':{}})


def test_real_final_field_assembly_uses_material_plan_and_each_new_window_plan():
    records=train_records()
    assert records['A1490']['record']['planned_demonstration_dose']['start_step']==1490
    out=assemble(records)
    assert out['original_V75_planned_demonstration_dose']==material()['dose']
    assert out['new_optimizer_updates']==894 and out['new_task_exposures']==4464
    assert out['new_development_sessions']==2649 and out['new_total_logical_sessions']==4749
    assert out['actual_demonstration_consumption']['D1490']==actual_consumption()
    assert out['terminal_probe_applied'] is False


@pytest.mark.parametrize('bad',['missing_actual','wrong_material','double_outer','teacher_prefix','wrong_step'])
def test_final_assembly_rejects_incomplete_or_changed_consumption(bad):
    records=train_records();row=records['D1490']['record']
    if bad=='missing_actual':row.pop('actual_demonstration_consumption')
    if bad=='wrong_material':row['actual_demonstration_consumption']['material_id']='other'
    if bad=='double_outer':row['outer_updates']=1
    if bad=='teacher_prefix':row['actual_demonstration_consumption']['student_prefix_target_count']=1
    if bad=='wrong_step':row['final_step']=1789
    with pytest.raises((ValueError,KeyError)):assemble(records)


def test_V75_revision_resolves_missing_plan_key_without_old_run_reexecution():
    n=report(1490,557);n['status']='COMPLETE'
    completed=dict(status='COMPLETE',initial_step=1192,final_step=1490,optimizer_updates=298,
        outer_updates=0,outer_done=[298],learning_rate=1e-5,actual_demonstration_consumption=actual_consumption())
    value=p._revision_contract(material(),completed,n,dict(native_metrics=dict(S=n['metrics'])))
    assert value['planned_demonstration_dose']==material()['dose']
    assert value['actual_demonstration_consumption']==completed['actual_demonstration_consumption']
    assert value['new_native_scores']==value['new_model_calls']==value['new_bootstrap_runs']==0


def test_empty_source_slice_is_NA_not_zero_accuracy():
    _,old=reports()
    out=p.summarize_slice(old,[],stats=stats,previous=previous)
    assert out['status']=='NA_EMPTY_SLICE' and out['native_metrics'] is None


def _barrier_fixture(root):
    jobs={}
    for step in (1192,1490,1788):
        for stage in ('shard00','shard01','shard02','shard03','virtual_point','replay','distribution'):
            key=f'step{step}.{stage}';jobs[key]=dict(job_id=key,kind='class' if stage.startswith('shard') else stage,step=step,stage=stage)
        if step!=1788:
            key=f'step{step}.train';jobs[key]=dict(job_id=key,kind='train',step=step,stage='train')
    jobs['D.step1490.train']=dict(job_id='D.step1490.train',kind='train',step=1490,stage='train')
    jobs.update(e.planned_jobs());accepted_refs={};actual_refs={}
    for index,(key,job) in enumerate(jobs.items(),100):
        directory=e._directory(root,job);attempt=directory/'attempts/attempt0001'
        b.publish(attempt/'launch/record.json',dict(protocol_id='p',pid=index,birth=str(index+1000)))
        b.publish(attempt/'actual_exit/record.json',dict(protocol_id='p',job_id=key,pid=index,birth=str(index+1000),returncode=0,actual_waitpid_observed=True))
        body=dict(protocol_id='p',job_id=key,pid=index,status='COMPLETE',resources=dict(all_gates_passed=True))
        if key in e.planned_jobs():
            seal=b.publish(directory/'whole_queue_seal/record.json',dict(denominator=job['denominator'],registration_id=key+'reg'))
            body.update(whole_queue_seal=b.entry(directory/'whole_queue_seal/record.json'),whole_queue_seal_id=seal['id'],sessions=job['denominator'],registration_id=seal['registration_id'])
        if key=='step1788.distribution':body.update(probe_only=True,applied=False)
        result=b.publish(directory/'result/record.json',body)
        b.publish(directory/'accepted/record.json',dict(protocol_id='p',job_id=key,actual_exit_zero=True,resources_passed=True,
            result_id=result['id'],result=b.entry(directory/'result/record.json'),actual_exit=b.entry(attempt/'actual_exit/record.json')))
        accepted_refs[key]=b.entry(directory/'accepted/record.json');actual_refs[key]=b.entry(attempt/'actual_exit/record.json')
    pre=root/'preparation_cpu/attempt0001'
    b.publish(pre/'actual_exit/record.json',dict(actual_waitpid_observed=True,returncode=0))
    b.publish(root/'preparation_cpu/accepted/record.json',dict(actual_exit=b.entry(pre/'actual_exit/record.json'),actual_exit_zero=True,resources_passed=True))
    for rel in ('v75_cpu_revision','source_overlap'):b.publish(root/rel/'record.json',dict(status='COMPLETE'))
    protocol=dict(id='p',jobs=jobs,preflight_accepted=b.entry(root/'preparation_cpu/accepted/record.json'),
        v75_cpu_revision=b.entry(root/'v75_cpu_revision/record.json'),source_overlap=b.entry(root/'source_overlap/record.json'))
    return protocol,dict(protocol_id='p',active_workers=[],accepted_jobs=accepted_refs,actual_exits=actual_refs)


@pytest.mark.parametrize('bad',[None,'missing_probe','missing_fixed_exit','active_worker'])
def test_no_scoring_until_all30_true_exits_including_fixed_and_terminal_probe(tmp_path,monkeypatch,bad):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    protocol,barrier=_barrier_fixture(tmp_path)
    if bad=='missing_probe':barrier['actual_exits'].pop('step1788.distribution')
    if bad=='missing_fixed_exit':barrier['actual_exits'].pop('D.step1490.train')
    if bad=='active_worker':barrier['active_workers']=[dict(pid=99)]
    b.publish(tmp_path/'all_jobs_exit_barrier/record.json',barrier)
    if bad is None:
        result=e.generation_exit_barrier(tmp_path,protocol)
        assert b.read_ref(result)['active_workers']==[]
    else:
        with pytest.raises(ValueError,match='all30'):e.generation_exit_barrier(tmp_path,protocol)
