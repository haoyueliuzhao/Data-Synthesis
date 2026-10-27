"""CPU-only fixed candidate evaluation and paired state-stage tests."""
from pathlib import Path
from types import SimpleNamespace
import copy
import importlib.util
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v75_analysis as a
import finqa_v75_evaluation as e
import finqa_v75_binding as b
spec=importlib.util.spec_from_file_location('_v75_native_stats_test',Path(e.__file__).with_name('finqa_v54_statistics.py'))
stats=importlib.util.module_from_spec(spec);spec.loader.exec_module(stats)


def native(state):
    return dict(status='unknown' if state=='UNKNOWN' else 'invalid_prediction' if state=='I' else 'scored',
        program_executable=None if state=='UNKNOWN' else state!='I',
        native=dict(execution_accuracy=None if state=='UNKNOWN' else int(state=='R'),
                    program_accuracy=None if state=='UNKNOWN' else int(state=='R')))


def row(i,state='R',stop='final_answer',tools=1,calls=1):
    return dict(task_key=f'draw20260928/finqa/task{i}',original_task_key=f'finqa/task{i}',
        native=native(state),source_group=dict(group=f'report{i//3}',level='report'),
        stop_reason=stop,tool_call_count=tools,actual_model_calls=calls)


def reports(correct=480):
    result={label:dict(denominator=883,step=1192 if label=='P' else 1490,
        results=[row(i,'R' if i<count else 'I','final_answer' if i<count else 'no_tool_call',1 if i<count else 0,1) for i in range(883)])
        for label,count in (('P',536),('B',431),('S',correct))}
    selection=dict(selected=[dict(task_key=f'draw20260928/finqa/task{i}',group='F' if i<48 else 'K') for i in range(96)])
    return result,selection


def proxy(log=None):
    def clusters(vectors,groups):
        if log is not None:log.append((vectors,groups))
        return dict(status='COMPLETE' if vectors else 'INCOMPLETE',comparisons={},
            same_weights_all_seeds_and_arms=True,uncertainty_scope='obsolete three parent text')
    return SimpleNamespace(native_state=stats.native_state,native_metrics=stats.native_metrics,
        paired_transitions=stats.paired_transitions,source_cluster_sensitivity=clusters)


def test_disjoint_shards_and_unchanged_native_decode():
    full=dict(denominator=883,tasks=[f'finqa/task{i}' for i in range(883)],
        source_groups={f'finqa/task{i}':dict(group=str(i//3)) for i in range(883)})
    shards=[e.shard_cohort(full,i) for i in (0,1)]
    assert [s['denominator'] for s in shards]==[442,441]
    merged={i:t for s in shards for i,t in zip(s['original_ordinals'],s['tasks'],strict=True)}
    assert [merged[i] for i in range(883)]==full['tasks']
    assert not set(shards[0]['tasks'])&set(shards[1]['tasks'])
    assert sum(j['denominator'] for j in e.planned_jobs().values())==883
    assert all(j['config']==e.panel_config() for j in e.planned_jobs().values())
    with pytest.raises(ValueError):e.panel_config('calibration')
    job=copy.deepcopy(next(iter(e.planned_jobs().values())));job['config']['temperature']=1
    with pytest.raises(ValueError):e._job(job)


def test_separate_low_lr_increment_parent_loss_and_shared_cluster_vectors():
    r,s=reports(480);log=[];v=a.compare_reports(r['S'],r['B'],r['P'],s,stats=proxy(log))
    assert v['estimands']['S_minus_B']['numerator']==49
    assert v['estimands']['S_minus_P']['numerator']==-56
    assert v['estimands']['descriptive_count_case']=='mitigated_decline_but_no_parent_net_gain'
    assert set(log[0][0])=={'execution_accuracy:S-B','execution_accuracy:S-P','program_accuracy:S-B','program_accuracy:S-P'}
    assert len(log[0][1])==883 and log[0][1][0]==log[0][1][1]=='report0'
    assert 'three parent' not in v['source_cluster_sensitivity']['uncertainty_scope']
    assert v['independent_parent_count']==1 and not v['independent_seed_replication']
    assert all(x['denominator']==48 for x in v['fixed_old96_mechanism_slice'].values())


@pytest.mark.parametrize('correct,case',[(431,'candidate_does_not_exceed_reused_low_lr_control'),
    (536,'parent_total_retained_not_per_task_equivalence'),(550,'observed_recipe_increment_and_parent_net_gain_on_development')])
def test_descriptive_cases_have_no_training_gate(correct,case):
    r,s=reports(correct);v=a.compare_reports(r['S'],r['B'],r['P'],s,stats=proxy())
    assert v['estimands']['descriptive_count_case']==case
    assert not v['automatic_followup'] and v['statistics_contract']['advancement_threshold'] is None


def test_unknown_preserves_full_denominator_and_blocks_affected_effects():
    r,s=reports();r['S']['results'][10]['native']=native('UNKNOWN');log=[]
    v=a.compare_reports(r['S'],r['B'],r['P'],s,stats=proxy(log))
    assert v['status']=='COMPLETE_WITH_UNKNOWN' and v['native_metrics']['S']['execution_accuracy']['denominator']==883
    assert v['native_metrics']['S']['execution_accuracy']['complete_dataset_mean'] is None
    assert v['paired']['S-B']['execution_accuracy']['difference'] is None
    assert v['paired']['S-P']['program_accuracy']['difference'] is None and log[0][0]=={}


def test_no_call_stage_denominator_is_all_tasks_and_R_W_separate():
    old=[row(0,'I','no_tool_call',0,1),row(1,'I','no_tool_call',1,2),row(2,'R'),row(3,'R')]
    new=[row(0,'W'),row(1,'R'),row(2,'I','no_tool_call',0,1),row(3,'R')]
    summary=a.no_call_summary(old,4);paired=a.paired_no_call(new,old,4,stats=stats)
    assert summary['post_tool']==dict(count=1,denominator=4,rate=.25)
    assert paired['stages']['initial']['old_stage_no_call_to_candidate_state']['W']==1
    assert paired['stages']['post_tool']['old_stage_no_call_to_candidate_state']['R']==1
    assert paired['stages']['initial']['reduction_count']==0 and paired['stages']['post_tool']['reduction_rate']==.25
    with pytest.raises(ValueError):a.no_call_stage(row(1,'I','no_tool_call',0,2))


@pytest.mark.parametrize('bad',['wrong_parent','changed_cluster','duplicate_slice','missing_task'])
def test_invalid_reference_or_pairing_blocks_comparison(bad):
    r,s=reports()
    if bad=='wrong_parent':r['P']['step']=894
    if bad=='changed_cluster':r['B']['results'][0]['source_group']['group']='other'
    if bad=='duplicate_slice':s['selected'][-1]=s['selected'][0]
    if bad=='missing_task':r['S']['results'].pop()
    with pytest.raises(ValueError):a.compare_reports(r['S'],r['B'],r['P'],s,stats=proxy())


def test_existing_cluster_recipe_and_one_parent_scope():
    c=a.statistics_contract()['source_cluster']
    assert c['replicates']==stats.BOOTSTRAP_REPLICATES==10000
    assert c['seed']==stats.BOOTSTRAP_SEED==20261018
    assert c['same_cluster_weights_all_available_comparisons'] and not c['cross_seed_uncertainty']


def test_no_final_scoring_without_full_actual_exit_barrier(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path);p=dict(id='p',jobs=e.planned_jobs())
    b.publish(tmp_path/'all_jobs_exit_barrier/record.json',dict(protocol_id='p',active_workers=[],accepted_jobs={},actual_exits={}))
    with pytest.raises(ValueError,match='all fixed jobs'):e.generation_exit_barrier(tmp_path,p)


def test_v74_posthoc_strata_three_twenty_six_nineteen(monkeypatch):
    contexts=[];rows=[]
    for group in ('F','K'):
        for i in range(48):
            pp=(i>=3) if group=='F' else True;lp=(i>=29) if group=='F' else i>=5;key=f'{group}{i}'
            contexts.append(dict(task_key=key,group=group,hP=dict(already_executed_tool_events=int(pp)),hL=dict(already_executed_tool_events=int(lp))))
            for direction in ('L_from_P','P_from_L'):
                good=pp if direction=='L_from_P' else not lp or (i>=39 if group=='F' else i>=6)
                rows.append(dict(task_key=key,direction=direction,native=native('R' if good else 'I'),stop_reason='final_answer' if good else 'no_tool_call'))
    monkeypatch.setattr(a,'_stats',lambda:stats)
    v=a.v74_state_stratification(dict(status='COMPLETE',id='sealed',conditional_trajectory_denominator=192,distinct_tasks=96,
        context_structure=dict(rows=contexts),results=rows));f=v['strata']['F']
    assert [f[k]['denominator'] for k in ('both_initial','parent_post_student_initial','both_post_tool')]==[3,26,19]
    assert f['both_post_tool']['directions']['P_from_L']['EA_correct']==9
    assert v['posthoc_descriptive_not_independent_test'] and v['new_native_scores']==0


@pytest.mark.parametrize('result_pid,passed',[(123,True),(999,False)])
def test_accepted_generation_result_requires_same_actual_process(tmp_path,monkeypatch,result_pid,passed):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    directory=tmp_path/'evaluations/jobs/test';attempt=directory/'attempts/attempt0001'
    b.publish(attempt/'launch/record.json',dict(protocol_id='p',pid=123,birth='456'))
    b.publish(attempt/'actual_exit/record.json',dict(protocol_id='p',job_id='test',pid=123,birth='456',returncode=0,actual_waitpid_observed=True))
    result=b.publish(directory/'result/record.json',dict(protocol_id='p',job_id='test',pid=result_pid,status='COMPLETE',resources=dict(all_gates_passed=True)))
    b.publish(directory/'accepted/record.json',dict(protocol_id='p',job_id='test',actual_exit_zero=True,resources_passed=True,result_id=result['id'],result=b.entry(directory/'result/record.json'),actual_exit=b.entry(attempt/'actual_exit/record.json')))
    if passed:
        accepted,actual=e._accepted(tmp_path,'test',directory,dict(id='p'))
        assert actual['pid']==123 and accepted['actual_exit_zero']
    else:
        with pytest.raises(ValueError,match='identity-matched'):e._accepted(tmp_path,'test',directory,dict(id='p'))


def _full_exit_fixture(root):
    jobs={f'{phase}.shard{i}':dict(job_id=f'{phase}.shard{i}',stage='collect')
          for phase in ('L.initial','P.initial','P.post') for i in (0,1)}
    jobs['step1192.train']=dict(job_id='step1192.train',stage='train')
    jobs.update(e.planned_jobs())
    protocol=dict(id='p',jobs=jobs);accepted_refs={};exit_refs={}
    for index,(key,job) in enumerate(jobs.items(),100):
        directory=e._directory(root,job);attempt=directory/'attempts/attempt0001'
        b.publish(attempt/'launch/record.json',dict(protocol_id='p',pid=index,birth=str(index+1000)))
        b.publish(attempt/'actual_exit/record.json',dict(protocol_id='p',job_id=key,pid=index,birth=str(index+1000),returncode=0,actual_waitpid_observed=True))
        body=dict(protocol_id='p',job_id=key,pid=index,status='COMPLETE',resources=dict(all_gates_passed=True))
        if key in e.planned_jobs():
            seal=b.publish(directory/'whole_queue_seal/record.json',dict(denominator=job['denominator'],registration_id='registration-'+key))
            body.update(whole_queue_seal=b.entry(directory/'whole_queue_seal/record.json'),whole_queue_seal_id=seal['id'],sessions=job['denominator'],registration_id=seal['registration_id'])
        result=b.publish(directory/'result/record.json',body)
        b.publish(directory/'accepted/record.json',dict(protocol_id='p',job_id=key,actual_exit_zero=True,resources_passed=True,result_id=result['id'],result=b.entry(directory/'result/record.json'),actual_exit=b.entry(attempt/'actual_exit/record.json')))
        accepted_refs[key]=b.entry(directory/'accepted/record.json');exit_refs[key]=b.entry(attempt/'actual_exit/record.json')
    material=root/'materials_preparation/attempt0001'
    b.publish(material/'launch/record.json',dict(protocol_id='p',pid=200,birth='2200'))
    b.publish(material/'actual_exit/record.json',dict(protocol_id='p',pid=200,birth='2200',returncode=0,actual_waitpid_observed=True))
    b.publish(material/'resources/closeout/record.json',dict(protocol_id='p',pid=200,birth='2200',status='COMPLETE',all_gates_passed=True,CUDA_initialized=False))
    b.publish(material/'result/record.json',dict(protocol_id='p',pid=200,status='COMPLETE'))
    b.publish(root/'materials_preparation/accepted/record.json',dict(protocol_id='p',actual_exit=b.entry(material/'actual_exit/record.json'),result=b.entry(material/'result/record.json'),resources=b.entry(material/'resources/closeout/record.json')))
    barrier=dict(protocol_id='p',active_workers=[],accepted_jobs=accepted_refs,actual_exits=exit_refs,materials_accepted=b.entry(root/'materials_preparation/accepted/record.json'))
    return protocol,barrier


@pytest.mark.parametrize('violation',[None,'missing_actual_exit','live_worker'])
def test_nine_GPU_exits_and_material_CPU_required_as_one_global_barrier(tmp_path,monkeypatch,violation):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    p,barrier=_full_exit_fixture(tmp_path)
    if violation=='missing_actual_exit':barrier['actual_exits'].pop('P.post.shard1')
    if violation=='live_worker':barrier['active_workers']=[dict(pid=123)]
    b.publish(tmp_path/'all_jobs_exit_barrier/record.json',barrier)
    if violation is None:
        ref=e.generation_exit_barrier(tmp_path,p)
        assert b.read_ref(ref)['materials_accepted']==barrier['materials_accepted'] and len(barrier['accepted_jobs'])==9
    else:
        with pytest.raises(ValueError,match='all fixed jobs'):e.generation_exit_barrier(tmp_path,p)
