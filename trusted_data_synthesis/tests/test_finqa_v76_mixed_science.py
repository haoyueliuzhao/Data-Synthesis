"""Bounded CPU controls for the new fixed-teacher objective and atomic cache."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import finqa_v76_binding as binding
binding.install_scientific_paths()
import finqa_v76_mixed_math as mixed
from finqa_v76_task_cache import MixedTaskCache
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
from trusted_synthesis.finance_research import v8_training_driver as v8


def inputs():
    tensor=lambda values:torch.tensor(values,dtype=torch.float64)
    gradients={'x':{'a':{'w':tensor([1.2,-.8])},'b':{'w':tensor([-.5,1.7])}},
               'y':{'one':{'w':tensor([.4,.9])}}}
    teachers={'x':{'initial':{'w':tensor([2.2,-1.3])},'post':{'w':tensor([-.1,1.8])}},'y':{}}
    pi={'x':{'a':.4,'b':.6},'y':{'one':1.0}};mu={'x':.3,'y':.7}
    weights={'x':{'old':'1/2','initial':'1/4','post':'1/4'},
             'y':{'old':'1','initial':'0','post':'0'}}
    return gradients,teachers,pi,mu,weights


@pytest.mark.parametrize('initial,post,old',[(False,False,'1'),(True,False,'3/4'),(False,True,'3/4'),(True,True,'1/2')])
def test_fixed_missing_slots_and_old_mass(initial,post,old):
    record={'tasks':{'x':{'slots':{'initial':{'package_id':'i'} if initial else None,
                                 'post':{'package_id':'p'} if post else None}}}}
    value=mixed.fixed_weights(record,['x','y'])
    assert value['x']['old']==old and value['y']=={'initial':'0','post':'0','old':'1'}


def test_mixed_population_equals_actual_fixed_slot_objective_and_does_not_add_states():
    g,t,p,mu,w=inputs();before=copy.deepcopy((g,t,p))
    value=mixed.aggregate_mixed_gradient(g,t,p,mu,w,adam=adam)
    expected=.3*(.5*(.4*g['x']['a']['w']+.6*g['x']['b']['w'])+.25*t['x']['initial']['w']+.25*t['x']['post']['w'])+.7*g['y']['one']['w']
    assert torch.allclose(value['w'],expected,atol=1e-15,rtol=1e-15)
    assert set(p['x'])=={'a','b'} and set(g['x'])=={'a','b'}
    assert v8._tree_digest((g,t,p))==v8._tree_digest(before)


def test_C_has_old_mass_once_and_teacher_does_not_enter_centering_support():
    g,t,p,mu,w=inputs();a={'w':torch.tensor([.7,-.4],dtype=torch.float64)}
    ordinary=adam.centered_contributions(g,p,mu,a)
    value=mixed.centered_contributions(g,p,mu,a,w,adam=adam)
    assert value['C']['x']=={z:.5*c for z,c in ordinary['C']['x'].items()}
    assert value['C']['y']=={'one':0.0}
    assert sum(p['x'][z]*v for z,v in value['C']['x'].items())==pytest.approx(0,abs=1e-15)


def optimizer():
    parameter=torch.nn.Parameter(torch.tensor([.2,-.7],dtype=torch.float64))
    opt=torch.optim.AdamW([parameter],lr=1e-5,betas=(.9,.999),eps=1e-8,weight_decay=0,foreach=False,fused=False)
    opt.state[parameter]={'step':torch.tensor(1192.),'exp_avg':torch.tensor([.11,-.09],dtype=torch.float64),
                          'exp_avg_sq':torch.tensor([.04,.08],dtype=torch.float64)}
    return {'w':parameter},opt


@pytest.mark.parametrize('clip',[None,.45])
def test_mixed_Adam_pullback_matches_tangent_finite_difference_with_teacher(clip):
    g,t,p,mu,w=inputs();params,opt=optimizer();before=v8._tree_digest((params,opt.state_dict()))
    prepared=mixed.prepare_virtual_point(params,opt,g,t,p,mu,w,clip_max_norm=clip,adam=adam)
    utility=torch.tensor([.8,-.3],dtype=torch.float64)
    pulled=adam.pullback(prepared['binding'],prepared['G'],{'w':-utility})
    C=mixed.centered_contributions(g,p,mu,pulled['a'],w,adam=adam)['C']['x']
    direction={'a':.3,'b':-.3};predicted=sum(C[z]*direction[z] for z in C)
    def objective(epsilon):
        q=copy.deepcopy(p)
        q['x']={z:p['x'][z]+epsilon*direction[z] for z in p['x']}
        G=mixed.aggregate_mixed_gradient(g,t,q,mu,w,adam=adam)
        theta=adam.virtual_step(prepared['binding'],G)['theta_bar']['w']
        return (theta*utility).sum().item()
    epsilon=1e-3;observed=(objective(epsilon)-objective(-epsilon))/(2*epsilon)
    assert observed==pytest.approx(predicted,rel=2e-5,abs=2e-12)
    oldG=adam.aggregate_gradient(g,p,mu)
    wrong=adam.pullback(prepared['binding'],oldG,{'w':-utility})['a']['w']
    assert not torch.allclose(pulled['a']['w'],wrong,atol=1e-13,rtol=1e-5)
    assert v8._tree_digest((params,opt.state_dict()))==before


def test_missing_or_extra_teacher_gradient_never_zero_filled():
    g,t,p,mu,w=inputs();t['x'].pop('post')
    with pytest.raises(ValueError,match='complete fixed teacher'):
        mixed.aggregate_mixed_gradient(g,t,p,mu,w,adam=adam)
    t['x']['post']={'w':torch.zeros(2,dtype=torch.float64)}
    t['y']['initial']={'w':torch.zeros(2,dtype=torch.float64)}
    with pytest.raises(ValueError,match='complete fixed teacher'):
        mixed.aggregate_mixed_gradient(g,t,p,mu,w,adam=adam)


def cache_fixture(tmp_path):
    spec=[dict(name='w',shape=[2],dtype='torch.float64')]
    task=dict(index=0,task_id='x',state_ids=['a','b'],row_count=2,shard=0)
    plan=dict(schema='v35_complete_task_plan.v1',task_ids=['x'],tasks=[task],parameter_spec=spec,
              assignments=[dict(task_ids=['x'],row_count=2)],state_count=2)
    plan['id']=binding.digest(plan)
    material=dict(id='actual-fixed-material',status='COMPLETE',packages={'pi':{}},
        tasks={'x':{'slots':{'initial':{'package_id':'pi'},'post':None}}})
    rt=SimpleNamespace(torch=torch,v8=v8)
    source=binding.old_module('finqa_v35_task_cache')
    cache=MixedTaskCache(tmp_path/'cache',{'point':'fixed-real-point'},plan,spec,rt,
        materials=material,original_cache_module=source)
    old={'a':{'w':torch.tensor([1.,2.],dtype=torch.float64)},'b':{'w':torch.tensor([3.,4.],dtype=torch.float64)}}
    teacher={'initial':{'w':torch.tensor([5.,6.],dtype=torch.float64)}}
    return cache,old,teacher,material,plan,spec,rt,source


def test_atomic_cache_rejects_half_task_and_teacher_cannot_become_old_state(tmp_path):
    cache,old,teacher,*_=cache_fixture(tmp_path)
    with pytest.raises(ValueError,match='partial or additional'):
        cache.commit('x',old,{})
    assert not cache.directory('x').exists()
    with pytest.raises(ValueError,match='task states incomplete'):
        cache.commit('x',dict(old,initial=teacher['initial']),teacher)
    record=cache.commit('x',old,teacher,receipt={'actual_parent_unchanged':True})
    assert record['complete_fixed_teachers'] and record['teacher_slots']==['initial']
    assert record['task']['state_ids']==['a','b']
    assert cache.has('x') and set(cache.assemble()['x'])=={'a','b'}
    assert set(cache.assemble_teachers()['x'])=={'initial'}


def test_atomic_cache_cold_reader_binds_material_and_detects_tensor_mutation(tmp_path):
    cache,old,teacher,material,plan,spec,rt,source=cache_fixture(tmp_path)
    cache.commit('x',old,teacher)
    fresh=MixedTaskCache(cache.root,cache.binding,plan,spec,rt,materials=material,original_cache_module=source)
    assert fresh.has('x') and torch.equal(fresh.read_teachers('x')['initial']['w'],teacher['initial']['w'])
    fresh.read_teachers('x')['initial']['w'].add_(1)
    with pytest.raises(ValueError,match='bytes or tensors changed'):fresh.has('x')
    foreign=MixedTaskCache(cache.root,cache.binding,plan,spec,rt,materials=dict(material,id='foreign'),original_cache_module=source)
    with pytest.raises(ValueError,match='state/material/source'):foreign.has('x')


def test_partial_cache_directory_is_not_recoverable_complete_task(tmp_path):
    cache,*_=cache_fixture(tmp_path)
    target=cache.directory('x');target.mkdir(parents=True);(target/'record.json').write_text('{}')
    with pytest.raises(ValueError,match='atomic old'):cache.has('x')


def test_fixed_point_diagnostic_keeps_adjustable_weighting_and_no_false_zero_convergence():
    import finqa_v76_diagnostics as diagnostic
    from trusted_synthesis.finance_research import v6_distribution as dist
    p={'x':{'a':.4,'b':.6},'y':{'one':1.0}};mu={'x':.3,'y':.7}
    zero={t:{z:0. for z in row} for t,row in p.items()}
    update=dist.automatic_update(p,p,zero,mu,arm='Full',feedback_all_zero=True)
    result=diagnostic.frozen_reference(current=p,prior=p,mu=mu,update=update,feedback_all_zero=True)
    assert result['status']=='UNINFORMATIVE_FEEDBACK' and not result['numeric_convergence']
    d=diagnostic.distribution_distances(p,{'x':{'a':.6,'b':.4},'y':{'one':1.0}},mu)
    assert d['adjustable']['TV']==pytest.approx(d['all_tasks']['TV']/.3)


def test_fixed_teacher_gradient_uses_suffix_token_mean_and_restores_rng_mode():
    import finqa_v76_runtime as runtime
    memory=binding.old_module('finqa_v34_tail_memory')
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__();self.embed=torch.nn.Embedding(13,4);self.head=torch.nn.Linear(4,13,bias=False)
            self.dropout=torch.nn.Dropout(.4)
        def forward(self,input_ids,attention_mask,use_cache,logits_to_keep):
            return SimpleNamespace(logits=self.head(self.dropout(self.embed(input_ids)))[:,logits_to_keep,:])
    class Monitor:
        def check_stop(self,*args,**kwargs):pass
        def snapshot(self,*args,**kwargs):return {}
    torch.manual_seed(83);model=Model();model.train()
    rows=[dict(input_ids=[1,2,3,4],target_positions=[2,3],target_ids=[3,4]),
          dict(input_ids=[1,2,3,4,5,6],target_positions=[5],target_ids=[6])]
    package=dict(package_id='fixed-i',rows=rows,student_prefix_target_count=0,
        target_mask_check='PASS_EXACT_NEW_TEACHER_RESPONSES_ONLY',target_tokens=3)
    material={'tasks':{'x':{'slots':{'initial':{'package_id':'fixed-i'},'post':None}}}}
    pool=runtime.FixedTeacherSuffixPool('x',material,{'fixed-i':package})
    rng=torch.get_rng_state().clone()
    got,receipt=memory.class_gradients_with_cpu_saves(SimpleNamespace(torch=torch,v8=v8),model,pool,
        device='cpu',monitor=Monitor(),cpu_test=True)
    assert model.training and torch.equal(torch.get_rng_state(),rng)
    assert receipt['rows_completed']==2 and set(got['x'])=={'initial'}
    model.eval();loss=torch.zeros(())
    for row in rows:
        logits=model(torch.tensor([row['input_ids']]),None,False,torch.tensor(row['target_positions'])-1).logits
        loss+=torch.nn.functional.cross_entropy(logits.reshape(-1,13),torch.tensor(row['target_ids']),reduction='sum')/3
    expected=torch.autograd.grad(loss,tuple(model.parameters()))
    assert all(torch.allclose(value,reference,atol=2e-7,rtol=2e-6)
        for value,reference in zip(got['x']['initial'].values(),expected,strict=True))


def test_cold_class_route_uses_registered_restore_and_mixed_cache_without_GPU(tmp_path,monkeypatch):
    import finqa_v76_runtime as runtime
    observed=[];state={'theta':'actual-fixture','rng':'saved'}
    context=dict(id='point',step=1192,protocol_id='registered',training_root='/original/materials',
        parent_checkpoint={'path':'/prepared/state'},parent_state_digest=binding.digest(state))
    state['arm']='C-only';context['parent_state_digest']=binding.digest(state)
    cache=SimpleNamespace(plan={'assignments':[{'task_ids':['task'],'row_count':2}]})
    class Driver:
        def __init__(self,model,opt,pool,**kwargs):
            self.state=None;observed.append(('driver',kwargs['arm'],str(kwargs['root'])))
        def _payload(self):return self.state
    def restore(driver,point,s,rt):
        observed.append(('registered_restore',point['id']));driver.state=copy.deepcopy(s)
    class Monitor:
        def __init__(self,guard,**kwargs):self.guard=guard
        def check_stop(self,*args,**kwargs):pass
        def clear_unused(self,*args,**kwargs):pass
        def snapshot(self,*args,**kwargs):pass
    def load(assets,seed):
        observed.append(('CPU_mock_loader',seed));return object(),object(),object(),object(),False
    launcher=SimpleNamespace(_load_components=load)
    rt=SimpleNamespace(v8=SimpleNamespace(_tree_digest=binding.digest),launcher=launcher,
        torch=SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda:observed.append(('release',)))))
    train=SimpleNamespace(checked_launch=lambda root:({},object(),None,{}),
        adapters=lambda:SimpleNamespace(TrainingDriver=Driver))
    monkeypatch.setattr(runtime.training_api,'runtime',lambda:(train,rt))
    monkeypatch.setattr(runtime.training_api,'load_point',lambda root,step,actual:(context,state))
    monkeypatch.setattr(runtime.training_api,'load_cache',lambda root,point,actual:cache)
    monkeypatch.setattr(runtime.training_api,'restore_driver',restore)
    monkeypatch.setattr(runtime.training_api,'point_root',lambda root,step:Path(root)/'points'/f'step{step}')
    monkeypatch.setattr(runtime,'ScientificMonitor',Monitor)
    def shard(directory,point,stage,driver,pool,actual_cache,actual_rt,monitor):
        assert actual_cache is cache and driver._payload()==state
        observed.append(('mixed_class',stage));return {'new_complete_tasks':1}
    monkeypatch.setattr(runtime,'execute_shard',shard)
    result=runtime.execute(tmp_path,runtime.job_spec(1192,'shard00'),tmp_path/'attempt0001',
                           SimpleNamespace(protocol={'id':'registered'}))
    assert result['complete_class_tasks']==1 and result['complete_class_rows']==2
    assert result['model_released'] and ('registered_restore','point') in observed
    assert observed.index(('registered_restore','point'))<observed.index(('mixed_class','shard00'))
    assert observed[-1]==('release',)
