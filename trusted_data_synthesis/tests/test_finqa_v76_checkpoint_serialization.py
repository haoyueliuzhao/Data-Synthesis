"""V76 native checkpoint directory/serialization controls; CPU only.

The two real failed-attempt states are copied without modifying original bytes.
Other cases are explicit tiny CPU controls, never scientific training receipts.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys

SCRIPTS=str(Path(__file__).resolve().parents[1]/'scripts')
if SCRIPTS not in sys.path:sys.path.append(SCRIPTS)
import pytest
import finqa_v76_binding as binding
binding.install_scientific_paths();binding.install_registered_auxiliary()
import finqa_v76_training as t
import torch
from trusted_synthesis.finance_research import v8_training_driver as v8

FAILED_ROOT=binding.PREPARATION_ROOT/'execution_revision_02'
REAL_PREPARED={
    'A':(1192,'e2cbbc4a3381e5774172eca160c4505ece4ad8885b3d0f5465652e23fe707e25'),
    'D':(1490,'5e02e4f209635ff6dffc11f63400352837d15a9edbbffecc7c86b99e7563240f'),
}


@pytest.mark.parametrize('branch',['A','D'])
def test_actual_failed_prepared_bytes_read_under_native_coordinate(tmp_path,branch):
    training,rt=t.runtime()
    step,expected=REAL_PREPARED[branch]
    source=FAILED_ROOT/('fixed' if branch=='D' else '')/'points'/f'step{step:04d}'/'prepared_state'
    record_before=binding.sha(source/'record.json');state_before=binding.sha(source/'state.pt')
    target=tmp_path/f'step{step:04d}_v76_preparation'
    shutil.copytree(source,target)
    assert binding.sha(target/'record.json')==record_before and binding.sha(target/'state.pt')==state_before
    reference=t.checkpoint_ref(target)
    restored=t.read_checkpoint(reference,rt)
    assert rt.v8._tree_digest(restored)==expected==reference['actual_state_digest']
    common=binding.checked(FAILED_ROOT/'schedule/record.json')
    context=binding.checked(source.parent/'context/record.json')
    inherited=t.read_checkpoint(context['source_parent_checkpoint'],rt)
    explicitly_prepared=t.prepare_state(inherited,common,rt,arm=branch,step=step)
    assert rt.v8._tree_digest(explicitly_prepared)==expected
    t.validate_point_state(restored,step,rt,arm=branch,common=common)
    # Exercise the corrected writer and unchanged native reader as well as the copy.
    rewrite=tmp_path/'roundtrip'/f'step{step:04d}_v76_preparation'
    evidence=json.loads((source/'record.json').read_bytes())['evidence']
    rewritten=t._write_prepared_checkpoint(rewrite,restored,evidence,rt)
    reread=t.read_checkpoint(rewritten,rt)
    assert rt.v8._tree_digest(reread)==expected
    assert binding.sha(source/'record.json')==record_before and binding.sha(source/'state.pt')==state_before
    assert torch.cuda.is_initialized() is False


def test_prepared_writer_rejects_noncanonical_name_before_writing(tmp_path):
    target=tmp_path/'prepared_state'
    with pytest.raises(ValueError,match='native step/phase'):
        t._write_prepared_checkpoint(target,{'step':1192},{},SimpleNamespace())
    assert not target.exists()


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embed=torch.nn.Embedding(13,4);self.linear=torch.nn.Linear(4,13,bias=False)
    def forward(self,input_ids,attention_mask,use_cache,logits_to_keep):
        return SimpleNamespace(logits=self.linear(self.embed(input_ids))[:,logits_to_keep,:])


@pytest.fixture(scope='module')
def native_fixture():
    training,rt=t.runtime()
    tasks=[f't{i:03d}' for i in range(744)]
    packages=[dict(package_id=x,task_id=x,state_id='s',whole_package_target_tokens=2) for x in tasks]
    rows={x:[dict(input_ids=[1,2,3],target_positions=[1,2],target_ids=[2,3])] for x in tasks}
    pool=v8.tiny_cpu_pool(tasks,packages,rows,chi={x:{'s':0.0} for x in tasks})
    old=training.build_task_schedule(tasks,137)
    plan,schedule=t.extended_schedule(old,rt.conditional.execution_plan(744),tasks)
    return pool,old,plan,schedule,rt


def make_driver(tmp_path,fixture,step,arm='Full'):
    pool,old,plan,schedule,rt=fixture
    torch.manual_seed(177);model=Model();optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5,
        betas=(0.9,0.999),eps=1e-8,weight_decay=0)
    driver=v8.TrainingDriver(model,optimizer,pool,root=tmp_path,seed=137,arm=arm,device='cpu',cpu_control_schedule=old)
    driver.execution_plan=copy.deepcopy(plan);driver.schedule=copy.deepcopy(schedule)
    driver.final_step=1788;driver.outer_steps=();driver.step_index=step;driver.initialized=True
    driver.outer_done=[298]+([1192]+([1490] if step>1490 else []) if arm=='Full' else [])
    for parameter in driver.parameters.values():
        optimizer.state[parameter]=dict(step=torch.tensor(float(step)),exp_avg=torch.zeros_like(parameter),exp_avg_sq=torch.zeros_like(parameter))
    return driver,rt


@pytest.mark.parametrize('step,arm,phase',[(1192,'C-only','v76_preparation'),
    (1490,'Full','step'),(1490,'Full','outer'),(1788,'Full','step'),(1788,'C-only','step')])
def test_native_commit_and_driver_restore_accept_new_coordinates(tmp_path,native_fixture,step,arm,phase):
    driver,rt=make_driver(tmp_path/'driver',native_fixture,step,arm)
    if phase=='outer':driver.outer_done=[298,1192,1490]
    path=driver.commit(phase,{'explicit_CPU_serialization_control':True,'scientific_optimizer_updates':0})
    reference=t.checkpoint_ref(path);state=t.read_checkpoint(reference,rt)
    expected=v8._tree_digest(state)
    for parameter in driver.parameters.values():
        with torch.no_grad():parameter.zero_()
    point=dict(parent_checkpoint=reference,parent_state_digest=expected)
    t.restore_driver(driver,point,state,rt)
    assert v8._tree_digest(driver._payload())==expected
    assert driver.schedule['updates']==1788 and driver.execution_plan['epochs']==12
    assert driver.outer_steps==() and driver.final_step==1788
    assert driver.step_index==step
    assert torch.cuda.is_initialized() is False


@pytest.mark.parametrize('start,end',[(1490,1491),(1787,1788)])
def test_actual_cpu_native_step_and_restore_beyond_old1490(tmp_path,monkeypatch,native_fixture,start,end):
    driver,rt=make_driver(tmp_path/'driver',native_fixture,start)
    source=driver.commit('step',{'explicit_CPU_serialization_control':True,'scientific_optimizer_updates':0})
    reference=t.checkpoint_ref(source);state=t.read_checkpoint(reference,rt)
    t.restore_driver(driver,{'parent_checkpoint':reference,'parent_state_digest':reference['actual_state_digest']},state,rt)
    material={'id':t.MATERIAL_ID,'tasks':{}}
    monkeypatch.setattr(t,'load_demonstrations',lambda point:(material,{}))
    t.install_demonstration_consumer(driver,{})
    report=driver.step()
    assert driver.step_index==end and report['task_batch']['step']==end
    assert report['task_batch']['task_ids']==native_fixture[3]['batches'][end-1]['task_ids']
    assert report['optimizer_step_calls']==report['clip_calls']==1
    final=t.checkpoint_ref(driver.root/f'step{end:04d}_step')
    saved=t.read_checkpoint(final,rt)
    assert v8._tree_digest(driver._payload())==v8._tree_digest(saved)
    driver.restore(final['path'])
    assert driver.step_index==end and v8._tree_digest(driver._payload())==final['actual_state_digest']
    if end==1788:
        with pytest.raises(ValueError,match='arm complete'):driver.step()
