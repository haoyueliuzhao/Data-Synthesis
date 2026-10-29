"""Focused CPU checks for the new V76 schedule, state preparation and consumer wiring."""
from __future__ import annotations
import copy
from fractions import Fraction
import json
from pathlib import Path
from types import SimpleNamespace
import sys

SCRIPTS=str(Path(__file__).resolve().parents[1]/'scripts')
if SCRIPTS not in sys.path:sys.path.append(SCRIPTS)
import pytest
import finqa_v76_binding as binding
binding.install_scientific_paths();binding.install_registered_auxiliary()
import finqa_v76_training as t
import torch
from trusted_synthesis.finance_research import materials as materials
from trusted_synthesis.finance_research import v8_training_driver as v8


def schedule_fixture():
    tasks=[f't{i:03d}' for i in range(744)]
    training,rt=t.runtime()
    return tasks,training.build_task_schedule(tasks,137),rt.conditional.execution_plan(744)


def test_new_epochs_preserve_frozen_ten_epoch_prefix_and_paired_dose():
    tasks,old,plan=schedule_fixture();before=copy.deepcopy((old,plan))
    new_plan,new=t.extended_schedule(old,plan,tasks)
    assert (old,plan)==before
    assert new['batches'][:1490]==old['batches']
    assert new_plan['epochs']==12 and new_plan['final_step']==1788 and new_plan['outer_steps']==[]
    assert new_plan['explicit_Full_outer_steps']==[1192,1490]
    added=new['batches'][1490:]
    assert len(added)==298 and {r['epoch'] for r in added}=={11,12}
    assert sum(len(r['task_ids']) for r in added)==1488
    assert sorted(len(r['task_ids']) for r in added)==[4,4]+[5]*296
    assert t.extended_schedule(old,plan,tasks)[1]==new  # same explicit A/D schedule, no training RNG
    assert new['schedule_sha256']!=old['schedule_sha256']


def test_extension_rejects_changed_original_prefix():
    tasks,old,plan=schedule_fixture();old=copy.deepcopy(old)
    old['batches'][1490-1]['task_ids'].reverse()
    with pytest.raises(ValueError,match='reproduce'):
        t.extended_schedule(old,plan,tasks)


def test_new_window_teacher_dose_uses_real_steps_and_tail_masses():
    tasks,old,plan=schedule_fixture();_,schedule=t.extended_schedule(old,plan,tasks)
    batches=schedule['batches'][1490:]
    tail_task=batches[148]['task_ids'][0]
    package=dict(package_id='teacher',encoding_summary=dict(target_tokens=3,input_positions=7,teacher_turns=2))
    material=dict(id=t.MATERIAL_ID,tasks={tail_task:dict(slots=dict(initial=package,post=None))})
    mu={x:'1/744' for x in tasks}
    dose=t.planned_demonstration_dose(material,batches,mu)
    assert dose['per_step'][0]['step']==1491 and dose['per_step'][-1]['step']==1788
    assert dose['planned_teacher_target_tokens']=={'initial':6}
    assert dose['planned_teacher_microbatches']=={'initial':4}
    assert sum(Fraction(v) for v in dose['realized_average_update_mass'].values())==1
    tail_slots=dose['per_step'][148]['demonstrations']
    assert tail_slots[0]['task_coefficient']=='1/16'


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embed=torch.nn.Embedding(13,4);self.linear=torch.nn.Linear(4,13,bias=False)
    def forward(self,input_ids,attention_mask,use_cache,logits_to_keep):
        return SimpleNamespace(logits=self.linear(self.embed(input_ids))[:,logits_to_keep,:])


def consumer_fixture():
    tasks=['a','b','c','d','e'];rows={}
    packages=[]
    for task in tasks:
        for state in ('s0','s1'):
            name=task+state;rows[name]=[dict(input_ids=[1,2,3],target_positions=[1,2],target_ids=[2,3])]
            packages.append(dict(package_id=name,task_id=task,state_id=state,whole_package_target_tokens=2))
    pool=v8.tiny_cpu_pool(tasks,packages,rows,chi={x:{'s0':0.0,'s1':0.0} for x in tasks})
    batch=materials.TaskBatch(task_ids=tuple(tasks),sampling_probability={x:'1/5' for x in tasks},
        sampling_design='uniform_epoch_permutation',schedule_id='test',step=1)
    demo=dict(package_id='teacher',rows=[dict(input_ids=[1,5,6],target_positions=[1,2],target_ids=[5,6])],
        teacher_turns=1,target_tokens=2,input_positions=3)
    slot=dict(package_id='teacher',encoding_summary={k:demo[k] for k in ('teacher_turns','target_tokens','input_positions')})
    material=dict(id=t.MATERIAL_ID,tasks={'a':dict(slots=dict(initial=slot,post=None))})
    return pool,batch,material,{'teacher':demo}


def test_actual_private_step_at_pi0_reproduces_V75_model_and_Adam(tmp_path,monkeypatch):
    pool,batch,material,packages=consumer_fixture();torch.manual_seed(77)
    left=Model();right=copy.deepcopy(left)
    lo=torch.optim.AdamW(left.parameters(),lr=1e-5);ro=torch.optim.AdamW(right.parameters(),lr=1e-5)
    schedule=dict(schedule_sha256='test',batches=[dict(task_ids=list(batch.task_ids),step=1,epoch=1)])
    driver=v8.TrainingDriver(left,lo,pool,root=tmp_path/'actual',seed=137,arm='C-only',device='cpu',cpu_control_schedule=schedule)
    monkeypatch.setattr(t,'load_demonstrations',lambda point:(material,packages))
    t.install_demonstration_consumer(driver,{'demonstration_materials':{'id':t.MATERIAL_ID}})
    actual=driver.step()
    expected=t.previous.consume_task_batch(right,ro,pool,pool._manifest.registration.pi0,batch,
        device='cpu',arm='C-only',material_record=material,packages=packages)
    assert all(torch.equal(x,y) for x,y in zip(left.parameters(),right.parameters(),strict=True))
    assert v8._tree_digest(lo.state_dict())==v8._tree_digest(ro.state_dict())
    assert actual['weighted_loss']==expected['weighted_loss']
    assert actual['supervision_policy']=='v75_exact_teacher_suffix_plus_unchanged_old.v1'
    assert actual['demonstration_consumption']['student_prefix_target_count']==0
    assert actual['optimizer_step_calls']==actual['clip_calls']==1
    assert (tmp_path/'actual/step0001_step/record.json').is_file()


def test_adaptive_pi_changes_only_old_state_weights_not_teacher_mass():
    pool,batch,material,packages=consumer_fixture();q=copy.deepcopy(pool._manifest.registration.pi0)
    for task in q:q[task]={'s0':0.8,'s1':0.2}
    model=Model();optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5)
    report=t.consume_task_batch(model,optimizer,pool,q,batch,device='cpu',arm='Full',material_record=material,packages=packages)
    coefficients={row['package_id']:Fraction(row['target_token_coefficient']) for row in report['packages']}
    assert coefficients['as0']==Fraction(3,4)*Fraction(4,5)/10
    assert coefficients['as1']==Fraction(3,4)*Fraction(1,5)/10
    assert coefficients['teacher']==Fraction(1,40)
    assert report['demonstration_consumption']['slots'][0]['task_coefficient']=='1/20'


def test_initial_preparation_changes_only_registered_LR_schedule_and_plan(monkeypatch):
    source=dict(step=1192,parameters={'x':torch.tensor([2.0])},buffers={},rng={'cpu':torch.tensor([1],dtype=torch.uint8)},
        pi={'a':{'s':1}},prior={'a':{'s':1}},outer_done=[298],schedule={'old':True},execution_plan={'old':True},
        optimizer={'param_groups':[{'lr':1e-4,'params':[0],'betas':(0.9,0.999)}],
                   'state':{0:{'step':torch.tensor(1192.),'exp_avg':torch.tensor([.2]),'exp_avg_sq':torch.tensor([.1])}}})
    original=copy.deepcopy(source)
    common={'schedule':{'new':True},'execution_plan':{'epochs':12}}
    monkeypatch.setattr(t.previous,'validate_parent_state',lambda state,rt:state)
    monkeypatch.setattr(t,'checked',lambda path:{'post_state_digest':v8._tree_digest(t.previous.state_with_learning_rate(source,1e-5))})
    rt=SimpleNamespace(v8=v8)
    result=t.prepare_state(source,common,rt,arm='A',step=1192)
    assert v8._tree_digest(source)==v8._tree_digest(original)
    assert result['optimizer']['param_groups'][0]['lr']==1e-5
    assert result['schedule']==common['schedule'] and result['execution_plan']==common['execution_plan']
    for key in ('parameters','buffers','rng','pi','prior','outer_done'):
        assert v8._tree_digest(result[key])==v8._tree_digest(source[key])
    assert v8._tree_digest(result['optimizer']['state'])==v8._tree_digest(source['optimizer']['state'])


@pytest.mark.parametrize('step,branch,expected',[(1192,'A',[298]),(1490,'A',[298,1192]),
    (1788,'A',[298,1192,1490]),(1490,'D',[298]),(1788,'D',[298])])
def test_actual_outer_history_never_backfills_old_596_or_894(step,branch,expected):
    assert t.expected_outer_history(step,branch)==expected


def make_checkpoint(root,name):
    p=root/name;p.mkdir(parents=True);(p/'record.json').write_text('{}');(p/'state.pt').write_bytes(b'x');return p


def test_recovery_prefers_actual_submitted_steps_and_does_not_repeat_outer(tmp_path):
    outer=make_checkpoint(tmp_path,'step1192_outer')
    assert t.latest_window_checkpoint(tmp_path,1192)==outer
    step=make_checkpoint(tmp_path,'step1193_step')
    assert t.latest_window_checkpoint(tmp_path,1192)==step
    make_checkpoint(tmp_path,'step1490_step')
    assert t.latest_window_checkpoint(tmp_path,1490) is None
    second=make_checkpoint(tmp_path,'step1490_outer')
    assert t.latest_window_checkpoint(tmp_path,1490)==second


def test_fixed_branch_rejects_any_outer_checkpoint(tmp_path):
    make_checkpoint(tmp_path,'step1490_outer')
    with pytest.raises(ValueError,match='escaped'):
        t.latest_window_checkpoint(tmp_path,1490,arm='D')


def test_terminal_probe_cannot_train_or_apply_third_update():
    driver=SimpleNamespace(outer_steps=(1192,),final_step=9999)
    with pytest.raises(ValueError,match='terminal'):
        t.configure_fixed_window(driver,1788)
    assert driver.outer_steps==(1192,) and driver.final_step==9999
    contract=t.training_contract()
    assert contract['new_optimizer_updates']==894 and contract['new_task_exposures']==4464
    assert contract['A_explicit_outer_steps']==[1192,1490] and contract['terminal_probe_applied'] is False


def test_recovery_from_final_actual_step_does_not_apply_outer_or_optimizer_again(tmp_path,monkeypatch):
    monkeypatch.setattr(t,'ROOT',tmp_path)
    q={'task':{'state':1.0}}
    parent=dict(pi=q,outer_done=[298])
    point=dict(step=1192,branch='A',probe_only=False,id='point',protocol_id='protocol',
        parent_state_digest='parent',checkpoint_arm='C-only',demonstration_materials={'id':t.MATERIAL_ID},
        planned_demonstration_dose={})
    payload={'actual_complete_state':'restored-endpoint'}
    class Driver:
        root=tmp_path/'training'
        step_index=1192
        pi=q
        outer_done=[298]
        arm='C-only'
        def restore(self,path):
            assert path==tmp_path/'training/step1490_step'
            self.step_index=1490;self.outer_done=[298,1192];self.pi=q
        def _payload(self):return payload
        def commit(self,*a,**kw):raise AssertionError('recovery must not repeat durable outer')
        def step(self):raise AssertionError('recovery must not repeat completed optimizer updates')
    driver=Driver();rt=SimpleNamespace(v8=v8)
    monkeypatch.setattr(t,'_contract',lambda *a,**kw:{'distribution_digest':v8._tree_digest(q)})
    monkeypatch.setattr(t,'publish',lambda path,body:body)
    monkeypatch.setattr(t,'latest_window_checkpoint',lambda *a:tmp_path/'training/step1490_step')
    monkeypatch.setattr(t,'install_demonstration_consumer',lambda *a:None)
    monkeypatch.setattr(t,'validate_point_state',lambda *a,**kw:None)
    monkeypatch.setattr(t,'checkpoint_ref',lambda path:{'path':str(path),'actual_state_digest':v8._tree_digest(payload)})
    monkeypatch.setattr(t,'_window_receipts',lambda *a:[])
    monkeypatch.setattr(t,'summarize_consumption',lambda *a:{'status':'PASS'})
    monkeypatch.setattr(t.binding,'entry',lambda path:{'path':str(path)})
    monitor=SimpleNamespace(check_stop=lambda *a,**kw:None,clear_unused=lambda *a:None)
    result=t.execute_training(tmp_path,point,parent,driver,q,rt=rt,monitor=monitor)
    assert result['updates_in_final_worker']==0 and result['optimizer_updates']==298
    assert result['outer_updates']==1 and result['outer_done']==[298,1192]


@pytest.mark.parametrize('step',[1490,1788])
def test_later_points_reuse_only_static_plan_without_rescanning_rows(tmp_path,monkeypatch,step):
    spec=[dict(name='weight',shape=[2],dtype='torch.float32')]
    registration=SimpleNamespace(state_support={'a':['s']},mu={'a':'1'},pi0={'a':{'s':1}},
        qualification_registration_id='qualification',validator_binding_id='validator')
    pool=SimpleNamespace(cache_id='pool',task_ids=('a',),_manifest=SimpleNamespace(registration=registration))
    body=dict(schema='v35_complete_task_plan.v1',parameter_spec=spec,task_ids=['a'],shards=4,
        global_registration=dict(task_ids=['a'],state_support=registration.state_support,mu=registration.mu,
            pi0=registration.pi0,qualification_registration_id='qualification',validator_binding_id='validator',pool_cache_id='pool'))
    plan=dict(body,id=t.task_cache.digest(body));source={'id':plan['id'],'path':'first-static','sha256':'bound'}
    monkeypatch.setattr(t,'checked_point',lambda *a,**kw:{'pool_id':'pool','parameter_spec':spec,'task_plan':source})
    monkeypatch.setattr(t.binding,'read_ref',lambda ref:plan)
    monkeypatch.setattr(t.task_cache,'make_task_plan',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('old rows rescanned')))
    actual,reference=t.static_task_plan(tmp_path,step,pool,spec)
    assert actual is plan and reference==source
    assert 'gradient' not in actual and 'parent_state_digest' not in actual


def test_static_plan_reuse_rejects_changed_parameter_spec_before_any_cache_read(tmp_path,monkeypatch):
    pool=SimpleNamespace(cache_id='pool')
    monkeypatch.setattr(t,'checked_point',lambda *a,**kw:{'pool_id':'pool','parameter_spec':[{'name':'old'}]})
    with pytest.raises(ValueError,match='parameter specification'):
        t.static_task_plan(tmp_path,1490,pool,[{'name':'new'}])
