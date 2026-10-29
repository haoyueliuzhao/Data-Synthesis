"""CPU controls for the new paired DAG and inherited actual-exit lifecycle."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v76_binding as b
import finqa_v76_queue_base as q
import finqa_v76_controller as c
import finqa_v76_resources as r
import finqa_v76_runtime as science
import finqa_v76_entry as entry
import finqa_v76_registration as reg

def test_fixed_reuse_and_two_Full_windows_do_not_enable_third_update():
    jobs=q.all_jobs()
    assert len(jobs)==30 and len(q.core_jobs())==24
    assert {k for k,v in jobs.items() if not v['dependencies']}=={
        'D.step1490.train',*[f'step1192.shard{i:02d}' for i in range(4)]}
    assert 'step1788.train' not in jobs and 'D.step1192.train' not in jobs
    assert jobs['step1490.shard00']['dependencies']==['step1192.train']
    assert jobs['step1788.shard00']['dependencies']==['step1490.train']
    assert jobs['D.step1788.dev_greedy.shard0']['dependencies']==['D.step1490.train']
    assert sum(v.get('denominator',0) for v in jobs.values())==2649
    with pytest.raises(ValueError):q.job_spec(1788,'train')

def test_every_core_job_matches_real_runtime_or_fixed_training_contract():
    for job in q.core_jobs().values():
        if job['arm']!='D':
            actual=science.job_spec(job['step'],job['stage'])
            assert all(job[k]==v for k,v in actual.items())
        else:assert q.job_directory(b.ROOT,job)==b.ROOT/'fixed/points/step1490/train'
        assert r.kind(job)==('class_' if job['kind']=='class' else job['kind'])

def test_readiness_requires_acceptance_not_written_result_or_draining():
    obj=object.__new__(c.Controller);obj.jobs=q.all_jobs();obj.accepted={};obj.job_states={
        k:c.inherited._initial_state() for k in obj.jobs};obj.active={}
    assert 'step1192.virtual_point' not in {j['job_id'] for j in obj.ready()}
    for i in range(4):
        key=f'step1192.shard{i:02d}';obj.job_states[key]['status']='DRAINING'
    assert 'step1192.virtual_point' not in {j['job_id'] for j in obj.ready()}
    for i in range(4):
        key=f'step1192.shard{i:02d}';obj.accepted[key]={};obj.job_states[key]['status']='COMPLETE'
    assert 'step1192.virtual_point' in {j['job_id'] for j in obj.ready()}
    assert 'A.step1490.dev_greedy.shard0' not in {j['job_id'] for j in obj.ready()}

@pytest.mark.parametrize('unknown,resume,classification,failures,expected',[
 (0,True,'RETRY_SAFE_RESOURCE',0,'BACKOFF'),
 (0,True,'RETRY_SAFE_RESOURCE',2,'HARD_BLOCKED'),
 (1,True,'RETRY_SAFE_RESOURCE',0,'HARD_BLOCKED'),
 (0,False,'RETRY_SAFE_RESOURCE',0,'HARD_BLOCKED'),
 (0,True,'EXPLICIT_STOP',0,'HARD_BLOCKED'),
 (0,True,'HARD_BLOCK',0,'HARD_BLOCKED'),
])
def test_actual_boundary_only_retry_and_three_no_progress_stop(monkeypatch,unknown,resume,classification,failures,expected):
    monkeypatch.setattr(q.records,'checked_file',lambda ref:None)
    audit=dict(resume_allowed=resume,unknown_calls=unknown,progress_units=3,durable_progress_digest='same',evidence=[])
    result=c.failure_decision(dict(classification=classification,evidence=[{}]),audit,
        previous_units=3,no_progress_failures=failures,attempt=3)
    assert result['status']==expected
    if expected=='BACKOFF':assert result['backoff_seconds']==300

def test_resource_protocol_cannot_omit_inherited_capacity_policy():
    p=dict(id='test',resource_policy=r.resource_policy(),resource_recovery_policy=r.resource_recovery_policy(),
        gpu_isolation_policy=r.isolation.gpu_isolation_policy(),allowed_gpu_indices=list(range(8)),
        gpu_uuids=r.GPU_UUIDS,gpu_lease_root=str(q.GPU_LEASE_ROOT),max_gpu_workers=6,max_workers_per_gpu=1)
    assert r.validate_registered_contract(p)['status']=='PASS'
    del p['resource_recovery_policy']
    with pytest.raises(ValueError,match='missing'):r.validate_registered_contract(p)

def test_single_gpu_and_memory_phase_still_bind_fixed_branch():
    job=q.core_jobs()['D.step1490.train'];uuid=r.GPU_UUIDS['6'];p=dict(gpu_uuids=r.GPU_UUIDS)
    row=dict(index=6,uuid=uuid,free_mib=26*1024,gpu_isolation=dict(allowed=True,gpu_uuid=uuid))
    assert q.gpu_eligible(row,p,job)
    assert not q.gpu_eligible(dict(row,free_mib=26*1024-1),p,job)
    with pytest.raises(ValueError):q.gpu_eligible(dict(row,uuid='wrong'),p,job)
    assert not q.can_dispatch({str(i):SimpleNamespace(gpu=i,lifecycle='DRAINING') for i in range(6)})

def test_full_protocol_has_exact_new_dose_and_parent_comparison():
    value=reg.scientific_contract()
    assert value['new_optimizer_updates']==596+298==894
    assert value['new_logical_sessions']==2100+2649==4749
    assert value['main_effect']=='EA(A1788)-EA(D1788)'
    assert value['teacher_gradient_enters_virtual_Adam_and_pullback']
    assert value['V75_failure_reclassified'] is False
    assert c.auto_recovery_policy()['controller_restart']=='forbidden; single controller attempt'


def test_actual_worker_result_connects_to_endpoint_exit_reader(tmp_path,monkeypatch):
    import os
    from contextlib import contextmanager
    import finqa_v76_worker as worker
    import finqa_v76_training as training
    import finqa_v76_evaluation as evaluation
    monkeypatch.setattr(b,'ROOT',tmp_path)
    protocol=b.publish(tmp_path/'protocol/record.json',{'schema':'fixture'})
    job=q.core_jobs()['D.step1490.train'];stable=q.job_directory(tmp_path,job)
    attempt=stable/'attempts/attempt0001'
    monkeypatch.setattr(worker,'checked_attempt_directory',lambda *args:attempt)
    monkeypatch.setattr(worker,'prepare_point_for_job',lambda *args:None)
    monkeypatch.setattr(worker,'validate_result',lambda *args:None)
    monkeypatch.setattr(training,'execute_fixed',lambda *args:{'optimizer_updates':298})
    @contextmanager
    def context(*args):yield SimpleNamespace(report=lambda:{'all_gates_passed':True})
    monkeypatch.setattr(r,'execution_context',context)
    value=worker.run(tmp_path,job,6,attempt_root=attempt)
    pid=os.getpid();assert value['pid']==value['actual_worker_pid']==pid
    b.publish(attempt/'launch/record.json',dict(protocol_id=protocol['id'],pid=pid,birth='777'))
    b.publish(attempt/'actual_exit/record.json',dict(protocol_id=protocol['id'],job_id=job['job_id'],
        pid=pid,birth='777',returncode=0,actual_waitpid_observed=True))
    b.publish(stable/'accepted/record.json',dict(protocol_id=protocol['id'],job_id=job['job_id'],
        actual_exit_zero=True,resources_passed=True,result_id=value['id'],result=b.entry(stable/'result/record.json'),
        actual_exit=b.entry(attempt/'actual_exit/record.json')))
    assert evaluation._accepted(tmp_path,job['job_id'],stable,protocol)[1]==value


def test_complete_result_reuse_requires_matching_original_resource_proof(tmp_path,monkeypatch):
    import finqa_v76_evaluation as evaluation
    monkeypatch.setattr(b,'ROOT',tmp_path)
    stable=tmp_path/'job';attempt=stable/'attempts/attempt0002';protocol={'id':'P'};key='J'
    value=b.publish(stable/'result/record.json',dict(protocol_id='P',job_id=key,pid=11,status='COMPLETE',
        resources={'all_gates_passed':True}))
    b.publish(attempt/'launch/record.json',dict(protocol_id='P',pid=22,birth='222'))
    b.publish(attempt/'actual_exit/record.json',dict(protocol_id='P',job_id=key,pid=22,birth='222',
        returncode=0,actual_waitpid_observed=True))
    b.publish(stable/'accepted/record.json',dict(protocol_id='P',job_id=key,actual_exit_zero=True,resources_passed=True,
        result_id=value['id'],result=b.entry(stable/'result/record.json'),actual_exit=b.entry(attempt/'actual_exit/record.json')))
    with pytest.raises(FileNotFoundError):evaluation._accepted(tmp_path,key,stable,protocol)
    b.publish(tmp_path/'resources/old/record.json',dict(protocol_id='P',job_id=key,pid=11,status='COMPLETE',resources=value['resources']))
    b.publish(attempt/'reused_result/record.json',dict(protocol_id='P',job_id=key,scientific_calls=0,verified_durable_result=True,
        source_result=b.entry(stable/'result/record.json'),source_resource_closeout=b.entry(tmp_path/'resources/old/record.json')))
    assert evaluation._accepted(tmp_path,key,stable,protocol)[1]['pid']==11


def test_actual_protocol_contract_survives_JSON_freeze_roundtrip():
    import json
    policies=reg._policy_fields(reg.modules())
    assert json.loads(json.dumps(policies))==policies
    assert json.loads(json.dumps(q.all_jobs()))==q.all_jobs()


def _one_shot_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    protocol={'id':'protocol'}
    monkeypatch.setattr(reg,'checked_protocol',lambda root:protocol)
    monkeypatch.setattr(reg,'checked_prepared',lambda root:{'status':'PASS'})
    monkeypatch.setattr(r,'controller_runtime',lambda:SimpleNamespace(birth=lambda pid:'777'))
    monkeypatch.setattr(c,'_environment',lambda root:{'CUDA_VISIBLE_DEVICES':''})
    return protocol


def test_actual_activation_function_reaches_one_Popen_after_cold_gates(tmp_path,monkeypatch):
    p=_one_shot_fixture(tmp_path,monkeypatch);calls=[]
    b.publish(tmp_path/'frozen_worker_import_verification/record.json',dict(status='PASS',protocol_id=p['id'],CUDA_initialized=False))
    b.publish(tmp_path/'cold_controller_verification/record.json',dict(status='PASS',protocol_id=p['id'],workers_dispatched=0))
    def popen(command,**kwargs):
        calls.append(command);return SimpleNamespace(pid=12345,poll=lambda:None)
    monkeypatch.setattr(c.subprocess,'Popen',popen)
    result=c.activate(tmp_path)
    assert result['status']=='ACTIVATED' and result['pid']==12345 and len(calls)==1
    assert calls[0][-2:]==['--mode','supervise']
    with pytest.raises(ValueError,match='consumed'):c.activate(tmp_path)
    assert len(calls)==1


@pytest.mark.parametrize('code',[0,75])
def test_actual_supervisor_function_launches_controller_once_and_never_retries(tmp_path,monkeypatch,code):
    p=_one_shot_fixture(tmp_path,monkeypatch);calls=[]
    monkeypatch.setattr(c,'stop_orphaned_workers',lambda *args:{'all_identities_observed_exited':True})
    def popen(command,**kwargs):
        calls.append(command)
        if code==0:b.publish(tmp_path/'closeout/record.json',dict(protocol_id=p['id'],status='COMPLETE'))
        return SimpleNamespace(pid=23456,poll=lambda:code,wait=lambda:code)
    monkeypatch.setattr(c.subprocess,'Popen',popen)
    result=c.supervise(tmp_path)
    assert len(calls)==1 and calls[0][-2:]==['--mode','run']
    assert result['controller_attempts']==1 and result['automatic_restart_stopped']
    assert result['status']==('COMPLETE' if code==0 else 'STOPPED_CONTROLLER_FAILURE_NO_RETRY')
    actual=b.read_ref(result['actual_controller_exit'])
    assert actual['actual_waitpid_observed'] and actual['returncode']==code
