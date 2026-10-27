"""V75 collection/material/training/evaluation ordering and real-exit gates."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v75_binding as b
import finqa_v75_controller as control


def jobs():
    result={}
    for phase in ('L.initial','P.initial','P.post'):
        for shard in range(2):
            key=f'{phase}.shard{shard}'
            result[key]=dict(job_id=key,id=key,phase=phase,model=phase[0],stage='collect',kind='generate',memory_phase='generate',
                task_ids=[f'task{shard}'],task_keys=[f'finqa/task{shard}'],maximum_model_calls=31 if phase=='P.post' else 32,
                dependencies=['L.initial.shard0','L.initial.shard1'] if phase=='P.post' else [])
    result['step1192.train']=dict(job_id='step1192.train',stage='train',kind='train',memory_phase='train',
        dependencies=sorted(control.collection_job_ids()))
    for shard in range(2):
        key=f'step1490.dev_greedy.shard{shard}'
        result[key]=dict(job_id=key,stage='generate',kind='generate',memory_phase='generate',dependencies=['step1192.train'])
    return result


def protocol():
    return dict(id='protocol',max_gpu_workers=6,max_workers_per_gpu=1,
        gpu_uuids=control.base.resource_api.GPU_UUIDS,gpu_priority=list(range(8)),
        gpu_lease_root=str(control.base.GPU_LEASE_ROOT),jobs=jobs(),
        materials_resource_policy=control.cpu_resource_policy('materials_preparation'),
        final_analysis_resource_policy=control.cpu_resource_policy('final_analysis'))


@pytest.fixture
def obj(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    p=protocol();reg=SimpleNamespace(checked_protocol=lambda root:p,checked_implementation=lambda root:{})
    runtime=SimpleNamespace(birth=lambda pid:'555',host_memory=lambda:dict(available_bytes=200*control.GIB))
    value=control.Controller(tmp_path,registration=reg,runtime=runtime)
    value.journal=lambda:None;value.status=lambda status:None
    return value


def accept(obj,key):
    directory=obj.job_directory(obj.jobs[key]);exit_path=directory/'attempts/attempt0001/actual_exit/record.json'
    b.publish(exit_path,dict(protocol_id='protocol',job_id=key,returncode=0,actual_waitpid_observed=True))
    value=b.publish(directory/'accepted/record.json',dict(protocol_id='protocol',job_id=key,actual_exit=b.entry(exit_path)))
    obj.accepted[key]=value;obj.job_states[key]['status']='COMPLETE'


def ready_ids(obj):
    return {job['job_id'] for job in obj.ready()}


def test_post_depends_on_both_L_actual_acceptances_not_saved_completion(obj):
    assert ready_ids(obj)=={'L.initial.shard0','L.initial.shard1','P.initial.shard0','P.initial.shard1'}
    accept(obj,'L.initial.shard0')
    obj.job_states['L.initial.shard1']['status']='DRAINING'
    assert not any(key.startswith('P.post') for key in ready_ids(obj))
    accept(obj,'L.initial.shard1')
    assert {'P.post.shard0','P.post.shard1'}<=ready_ids(obj)
    assert 'step1192.train' not in ready_ids(obj)


def test_constructor_rejects_missing_mandatory_post_dependency(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path);p=protocol();p['jobs']['P.post.shard0']['dependencies']=[]
    reg=SimpleNamespace(checked_protocol=lambda root:p,checked_implementation=lambda root:{})
    with pytest.raises(ValueError,match='depend'):
        control.Controller(tmp_path,registration=reg,runtime=SimpleNamespace())


def test_train_waits_actual_material_CPU_success_and_dev_waits_train_exit(obj):
    for key in sorted(control.collection_job_ids()):accept(obj,key)
    assert 'step1192.train' not in ready_ids(obj)
    def finish_materials(phase,mode):
        assert (phase,mode)==('materials_preparation','prepare-materials')
        assert not obj.materials_complete and not obj.active
        return {'path':'material'},{'status':'PASS'}
    obj._run_cpu=finish_materials
    obj.prepare_materials()
    assert obj.materials_complete and ready_ids(obj)=={'step1192.train'}
    obj.job_states['step1192.train']['status']='DRAINING'
    assert not ready_ids(obj)
    accept(obj,'step1192.train')
    assert ready_ids(obj)=={'step1490.dev_greedy.shard0','step1490.dev_greedy.shard1'}


class Process:
    def __init__(self,pid=12345,code=None):self.pid,self.code,self.waits=pid,code,0
    def poll(self):return self.code
    def wait(self):
        assert self.code is not None
        self.waits+=1;return self.code


def child(obj,key,pid,code=None):
    directory=obj.job_directory(obj.jobs[key]);closed=[]
    value=SimpleNamespace(job=obj.jobs[key],process=Process(pid,code),birth='555',gpu=pid%8,
        attempt=1,attempt_dir=directory/'attempts/attempt0001',directory=directory,
        lease=SimpleNamespace(close=lambda:closed.append(True)),pidfd=None,lifecycle='INITIALIZING',
        durable_before=dict(progress_units=0,unknown_calls=0,resume_allowed=True,completed_digest='0'))
    obj.active[key]=value;obj.job_states[key]['status']='RUNNING'
    return value,closed


def test_six_sealed_but_live_draining_children_retain_slots_and_block_dispatch(obj,monkeypatch):
    children=[]
    for index,key in enumerate(sorted(control.collection_job_ids())):
        c,closed=child(obj,key,10000+index);b.publish(c.directory/'result/record.json',dict(status='COMPLETE'))
        children.append((c,closed))
    obj.reap()
    assert len(obj.active)==6 and not obj.accepted and all(c.lifecycle=='DRAINING' and not closed for c,closed in children)
    assert not control.base.can_dispatch(obj.active)
    obj.ready=lambda:[obj.jobs['step1192.train']]
    obj.acquire=lambda job:(_ for _ in ()).throw(AssertionError('cannot dispatch with six live slots'))
    class EndIteration(Exception):pass
    monkeypatch.setattr(control.time,'sleep',lambda seconds:(_ for _ in ()).throw(EndIteration()))
    obj.stop_pool=lambda reason:dict(status='TEST_ENDED',reason=reason)
    assert obj.run()['status']=='TEST_ENDED'
    assert len(obj.active)==6 and all(not closed for _,closed in children)


def test_nonzero_worker_exit_does_not_accept_saved_success(obj):
    c,closed=child(obj,'L.initial.shard0',12345,1)
    b.publish(c.directory/'result/record.json',dict(status='COMPLETE'))
    obj.reap()
    assert not obj.accepted and not obj.active and closed==[True]
    assert obj.job_states[c.job['job_id']]['status']=='HARD_BLOCKED'
    actual=b.checked(c.attempt_dir/'actual_exit/record.json')
    assert actual['actual_waitpid_observed'] and actual['returncode']==1


def cpu_popen(obj,monkeypatch,summary_status='COMPLETE',code=0):
    calls=[]
    def launch(command,**kwargs):
        phase=Path(command[command.index('--attempt-root')+1]).parent.name
        directory=obj.root/phase/'attempt0001';pid=223344
        policy=control.cpu_resource_policy(phase)
        b.publish(directory/'resources/record.json',dict(status='COMPLETE',protocol_id='protocol',pid=pid,birth='555',
            CUDA_initialized=False,all_gates_passed=True,policy=policy))
        b.publish(obj.root/phase/'summary/record.json',dict(status=summary_status,protocol_id='protocol'))
        b.publish(directory/'result/record.json',dict(status='COMPLETE',protocol_id='protocol',pid=pid,
            resources=b.entry(directory/'resources/record.json'),analysis=b.entry(obj.root/phase/'summary/record.json')))
        process=Process(pid,code);calls.append((command,kwargs,process));return process
    monkeypatch.setattr(control.subprocess,'Popen',launch)
    monkeypatch.setattr(control,'_environment',lambda root:dict(CUDA_VISIBLE_DEVICES=''))
    return calls


@pytest.mark.parametrize('phase,mode,summary_status',[
    ('materials_preparation','prepare-materials','PASS'),
    ('final_analysis','analyze','COMPLETE_WITH_UNKNOWN'),
])
def test_each_CPU_phase_has_own_real_exit_resource_acceptance_and_no_relaunch(obj,monkeypatch,phase,mode,summary_status):
    calls=cpu_popen(obj,monkeypatch,summary_status)
    ref,result=obj._run_cpu(phase,mode)
    command,environment,process=calls[0]
    assert command[command.index('--mode')+1]==mode and environment['env']['CUDA_VISIBLE_DEVICES']==''
    assert process.waits==1 and result['status']==summary_status
    accepted=b.checked(obj.root/phase/'accepted/record.json')
    actual=b.read_ref(accepted['actual_exit'])
    assert actual['actual_waitpid_observed'] and actual['returncode']==0 and actual['pid']==process.pid
    assert accepted['phase']==phase and accepted['analysis']==ref
    with pytest.raises(ValueError,match='never relaunch'):obj._run_cpu(phase,mode)
    assert len(calls)==1


def test_CPU_nonzero_exit_blocks_acceptance_even_with_success_artifact(obj,monkeypatch):
    calls=cpu_popen(obj,monkeypatch,code=1)
    with pytest.raises(ValueError,match='actual exit zero'):obj._run_cpu('materials_preparation','prepare-materials')
    assert calls[0][2].waits==1 and not (obj.root/'materials_preparation/accepted/record.json').exists()


@pytest.mark.parametrize('blocked_by',['active_worker','explicit_stop'])
def test_CPU_entry_requires_empty_live_pool_and_no_explicit_stop(obj,monkeypatch,blocked_by):
    calls=cpu_popen(obj,monkeypatch)
    if blocked_by=='active_worker':obj.active['still_live']=SimpleNamespace()
    else:(obj.root/'STOP').write_text('user stop')
    with pytest.raises(ValueError):obj._run_cpu('materials_preparation','prepare-materials')
    assert calls==[]


def test_explicit_stop_is_terminal_no_auto_restart_and_shared_grace_not_reset(obj):
    first=control._stop_marker(obj.root,obj.protocol,dict(kind='EXPLICIT',signals=[15]))
    second=control._stop_marker(obj.root,obj.protocol,dict(kind='FAILURE'))
    assert first==second and first['automatic_restart_allowed'] is False
    result=obj.stop_pool(dict(kind='EXPLICIT'))
    assert result['status']=='STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME'
    assert result['automatic_controller_restart_allowed'] is False and result['automatic_followup_started'] is False
