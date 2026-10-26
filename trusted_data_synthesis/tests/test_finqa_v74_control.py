"""V74 single-worker and complete-trajectory scoring gates, CPU only."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import finqa_v74_binding as b
import finqa_v74_controller as control
import finqa_v74_entry as entry
import finqa_v74_registration as reg


def protocol():
    job=dict(job_id="P.continuation",model="P",kind="generate",stage="generate",memory_phase="generate",
             condition_ids=[str(i) for i in range(192)])
    return dict(id="protocol",max_gpu_workers=1,max_workers_per_gpu=1,
        gpu_uuids=control.base.resource_api.GPU_UUIDS,gpu_priority=list(range(8)),
        gpu_lease_root=str(control.base.GPU_LEASE_ROOT),jobs={job['job_id']:job})


def test_one_fixed_worker_single_use(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    p=protocol()
    r=SimpleNamespace(checked_protocol=lambda root:p,checked_implementation=lambda root:{})
    obj=control.Controller(tmp_path,runtime=SimpleNamespace(),registration=r)
    assert len(obj.ready())==1 and obj.jobs['P.continuation']['model']=='P'
    p['jobs']['L.forbidden']=dict(p['jobs']['P.continuation'])
    with pytest.raises(ValueError,match='single registered'):
        control.Controller(tmp_path,runtime=SimpleNamespace(),registration=r)


def test_registered_budget_and_zero_training():
    value=reg.contract(961)
    assert value['native_scores']==192 and value['max_gpu_workers']==1
    assert value['new_first_responses']==value['new_probability_sequences']==value['new_optimizer_updates']==0
    with pytest.raises(ValueError):reg.contract(962)


def test_no_score_barrier_before_actual_accepted_worker_exit(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    p=protocol()
    b.publish(tmp_path/'all_jobs_exit_barrier/record.json',dict(protocol_id='protocol',active_workers=[],
        accepted_jobs={},actual_exits={}))
    with pytest.raises(ValueError,match='complete empty-worker'):
        entry.accepted_analysis_jobs(p)


def test_nonzero_exit_never_accepts_saved_terminal_result(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    obj=object.__new__(control.Controller)
    obj.root,obj.protocol=tmp_path,protocol()
    obj.jobs=obj.protocol['jobs'];obj.accepted={};obj.stopping=False
    obj.job_states={'P.continuation':dict(status='RUNNING')}
    obj.journal=lambda:None
    j=obj.jobs['P.continuation'];d=tmp_path/'jobs/P.continuation'
    b.publish(d/'result/record.json',dict(status='COMPLETE'))
    closed=[]
    process=SimpleNamespace(pid=12345,poll=lambda:1,wait=lambda:1)
    child=SimpleNamespace(job=j,process=process,attempt_dir=d/'attempts/attempt0001',directory=d,
        attempt=1,birth='123',gpu=6,lease=SimpleNamespace(close=lambda:closed.append(True)),pidfd=None)
    obj.active={'P.continuation':child}
    obj.reap()
    assert not obj.accepted and not obj.active and closed==[True]
    assert obj.job_states['P.continuation']['status']=='HARD_BLOCKED'


def test_unknown_tool_or_model_call_blocks_recovery():
    state=dict(progress_units=3,unknown_calls=1,resume_allowed=False,completed_digest='test')
    result=control.retry_decision(dict(confirmed_resource_failure=True,recoverable_at_actual_return_boundary=True),
        state,previous_units=2,no_progress_failures=0,returncode=1)
    assert result['status']=='HARD_BLOCKED'
