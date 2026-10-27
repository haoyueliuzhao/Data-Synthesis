"""CPU controls for fixed-slot loss mathematics and exact new-token supervision."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

SCRIPTS=str(Path(__file__).resolve().parents[1]/"scripts")
if SCRIPTS not in sys.path:sys.path.append(SCRIPTS)
import pytest
import finqa_v75_binding as binding
binding.install_scientific_paths();binding.install_registered_auxiliary()
import finqa_v75_training as training
import finqa_v75_materials as material
import torch
from trusted_synthesis.finance_research import materials as original
from trusted_synthesis.finance_research import v8_training_driver as driver_api


@pytest.mark.parametrize("initial,post,expected",[(False,False,(1,0,0)),(True,False,(Fraction(3,4),Fraction(1,4),0)),
    (False,True,(Fraction(3,4),0,Fraction(1,4))),(True,True,(Fraction(1,2),Fraction(1,4),Fraction(1,4)))])
def test_missing_slots_return_to_old(initial,post,expected):
    value=material.slot_weights(initial,post)
    assert tuple(value[k] for k in ("old","initial","post"))==expected
    assert sum(value.values())==1


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embed=torch.nn.Embedding(13,4);self.linear=torch.nn.Linear(4,13,bias=False)
    def forward(self,input_ids,attention_mask,use_cache,logits_to_keep):
        return SimpleNamespace(logits=self.linear(self.embed(input_ids))[:,logits_to_keep,:])


def fixtures():
    tasks=["a","b","c","d","e"]
    rows={name:[dict(input_ids=[1,2,3],target_positions=[1,2],target_ids=[2,3])] for name in tasks}
    pkgs=[dict(package_id=name,task_id=name,state_id="state",whole_package_target_tokens=2) for name in tasks]
    pool=driver_api.tiny_cpu_pool(tasks,pkgs,rows,chi={t:{"state":0.0} for t in tasks})
    batch=original.TaskBatch(task_ids=tuple(tasks),sampling_probability={x:"1/5" for x in tasks},
        sampling_design="uniform_epoch_permutation",schedule_id="frozen",step=1193)
    return pool,batch


def demo(package_id,rows):
    return dict(package_id=package_id,rows=rows,teacher_turns=len(rows),
        target_tokens=sum(len(r["target_ids"]) for r in rows),input_positions=sum(len(r["input_ids"]) for r in rows))


def slot(package):
    return dict(package_id=package["package_id"],encoding_summary={k:package[k] for k in ("teacher_turns","target_tokens","input_positions")})


def test_no_demonstrations_exactly_reuses_old_consumer_and_Adam():
    pool,batch=fixtures();torch.manual_seed(3);left=Model();right=copy.deepcopy(left)
    a=torch.optim.AdamW(left.parameters(),lr=1e-5);c=torch.optim.AdamW(right.parameters(),lr=1e-5)
    expected=original.execute_task_batch_update(left,a,pool,pool._manifest.registration.pi0,batch,device="cpu",arm="C-only")
    actual=training.consume_task_batch(right,c,pool,pool._manifest.registration.pi0,batch,device="cpu",arm="C-only",
        material_record={"id":"empty","tasks":{}},packages={})
    assert all(torch.equal(x,y) for x,y in zip(left.parameters(),right.parameters(),strict=True))
    assert driver_api._tree_digest(a.state_dict())==driver_api._tree_digest(c.state_dict())
    assert expected['weighted_loss']==actual['weighted_loss']
    assert actual['demonstration_consumption']['old_consumer_exact_delegation_when_no_slots'] is True
    assert actual['demonstration_consumption']['teacher_microbatches']==0


def test_two_slots_use_full_suffix_mean_and_single_original_optimizer_step():
    pool,batch=fixtures();torch.manual_seed(5);actual_model=Model();expected_model=copy.deepcopy(actual_model)
    first=demo('initial',[dict(input_ids=[1,4,5],target_positions=[1,2],target_ids=[4,5]),
        dict(input_ids=[1,4,5,6],target_positions=[3],target_ids=[6])])
    post=demo('post',[dict(input_ids=[7,8],target_positions=[1],target_ids=[8])])
    record=dict(id='materials',tasks={'a':dict(slots={'initial':slot(first),'post':slot(post)})})
    a=torch.optim.AdamW(actual_model.parameters(),lr=1e-5);expected=torch.optim.AdamW(expected_model.parameters(),lr=1e-5)
    result=training.consume_task_batch(actual_model,a,pool,pool._manifest.registration.pi0,batch,
        device='cpu',arm='C-only',material_record=record,packages={'initial':first,'post':post})
    expected.zero_grad(set_to_none=True)
    loss=torch.zeros(())
    for task in batch.task_ids:
        row=pool.row_arrays(task)[0];ids=torch.tensor([row['input_ids']]);positions=torch.tensor(row['target_positions'])-1
        logits=expected_model(ids,None,False,positions).logits
        coeff=(.5 if task=='a' else 1)/5/2
        loss+=torch.nn.functional.cross_entropy(logits.reshape(-1,13),torch.tensor(row['target_ids']),reduction='sum')*coeff
    for package in (first,post):
        for row in package['rows']:
            logits=expected_model(torch.tensor([row['input_ids']]),None,False,torch.tensor(row['target_positions'])-1).logits
            loss+=torch.nn.functional.cross_entropy(logits.reshape(-1,13),torch.tensor(row['target_ids']),reduction='sum')*(.25/5/package['target_tokens'])
    loss.backward();torch.nn.utils.clip_grad_norm_(expected_model.parameters(),1,error_if_nonfinite=True);expected.step()
    assert all(torch.allclose(x,y,atol=2e-8,rtol=1e-6) for x,y in zip(actual_model.parameters(),expected_model.parameters(),strict=True))
    assert result['optimizer_step_calls']==result['clip_calls']==result['zero_grad_calls']==1
    consumed=result['demonstration_consumption']
    assert consumed['teacher_target_tokens']==4 and consumed['teacher_input_positions']==9 and consumed['teacher_microbatches']==3
    assert consumed['student_prefix_target_count']==0
    assert result['target_tokens']==14 and result['rows_completed']==8
    coefficients={r['package_id']:Fraction(r['target_token_coefficient']) for r in result['packages']}
    assert coefficients['a']==Fraction(1,20) and coefficients['initial']==Fraction(1,60) and coefficients['post']==Fraction(1,20)


def test_only_one_slot_keeps_three_quarters_old_and_no_other_slot_boost():
    pool,batch=fixtures();torch.manual_seed(7);model=Model();opt=torch.optim.AdamW(model.parameters(),lr=1e-5)
    initial=demo('initial',[dict(input_ids=[1,4],target_positions=[1],target_ids=[4])])
    result=training.consume_task_batch(model,opt,pool,pool._manifest.registration.pi0,batch,device='cpu',arm='C-only',
        material_record=dict(id='materials',tasks={'a':dict(slots={'initial':slot(initial),'post':None})}),packages={'initial':initial})
    coeff={r['package_id']:Fraction(r['target_token_coefficient']) for r in result['packages']}
    assert coeff['a']==Fraction(3,40) and coeff['initial']==Fraction(1,20)


class Tokenizer:
    def decode(self,ids,**kwargs):return ''.join(chr(x) for x in ids)
    def apply_chat_template(self,messages,tools,**kwargs):return messages[0]['content']
    def __call__(self,text,**kwargs):return {'input_ids':[ord(x) for x in text]}


def teacher_turn(prompt,response,identity):
    request=dict(messages=[dict(role='user',content=prompt)],tools=[],config={},
        rendered_prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    receipt=dict(identity=identity,request_sha256=binding.digest(request),prompt_input_ids=[ord(x) for x in prompt],
        raw_generated_token_ids=[ord(x) for x in response]+[0],actual_eos=True,
        sampling=dict(eos_token_ids=[0],context_truncated=False),raw_response_sha256=hashlib.sha256(response.encode()).hexdigest())
    return dict(receipt=receipt,raw_text=response,provider_metadata=dict(request=request))


def test_exact_teacher_suffix_masks_all_student_prefix_and_targets_actual_EOS(monkeypatch):
    monkeypatch.setattr(binding,'source_v73',lambda name:SimpleNamespace(restore_request_tool_order=lambda x:x))
    student=teacher_turn('USER','WRONG',{'model':'L'});teacher=teacher_turn('USER WRONG OBS','<tool>submit</tool>',{'model':'P'})
    value=material.encode_teacher_suffix({'turns':[student,teacher]},teacher_start=1,teacher_identity={'model':'P'},tokenizer=Tokenizer())
    assert value['teacher_turns']==1 and value['student_prefix_target_count']==0 and value['actual_EOS_target_count']==1
    row=value['rows'][0]
    assert min(row['target_positions'])==len('USER WRONG OBS') and row['target_ids'][-1]==0
    assert row['input_ids'][:row['prompt_tokens']]==[ord(x) for x in 'USER WRONG OBS']


@pytest.mark.parametrize('change',['teacher_identity','prompt_ids','raw_ids','EOS','truncated'])
def test_changed_teacher_source_or_token_mapping_blocks(change,monkeypatch):
    monkeypatch.setattr(binding,'source_v73',lambda name:SimpleNamespace(restore_request_tool_order=lambda x:x))
    turn=teacher_turn('SOURCE','submit',{'model':'P'});receipt=turn['receipt']
    if change=='teacher_identity':receipt['identity']={'model':'L'}
    elif change=='prompt_ids':receipt['prompt_input_ids'][0]+=1
    elif change=='raw_ids':receipt['raw_generated_token_ids'][0]+=1
    elif change=='EOS':receipt['actual_eos']=False
    else:receipt['sampling']['context_truncated']=True
    with pytest.raises(ValueError):material.encode_teacher_suffix({'turns':[turn]},teacher_start=0,teacher_identity={'model':'P'},tokenizer=Tokenizer())


def test_source_teacher_EOS_absence_never_invents_an_EOS(monkeypatch):
    monkeypatch.setattr(binding,'source_v73',lambda name:SimpleNamespace(restore_request_tool_order=lambda x:x))
    turn=teacher_turn('SOURCE','submit',{'model':'P'});turn['receipt']['raw_generated_token_ids'].pop();turn['receipt']['actual_eos']=False
    value=material.encode_teacher_suffix({'turns':[turn]},teacher_start=0,teacher_identity={'model':'P'},tokenizer=Tokenizer())
    assert value['actual_EOS_target_count']==0 and value['target_tokens']==len('submit')


def batches():
    return [dict(task_ids=['a','b','c','d'] if index in (148,297) else ['a','b','c','d','e']) for index in range(298)]


def test_exact_four_task_tail_mass_and_effective_not_half_global_dose():
    package=demo('initial',[dict(input_ids=[1,2],target_ids=[2],target_positions=[1])])
    tasks={'a':dict(slots={'initial':slot(package),'post':None})}
    dose=material.planned_dose(tasks,batches())
    expected=(296*Fraction(1,20)+2*Fraction(1,16))/298
    assert Fraction(dose['realized_average_update_mass']['initial'])==expected
    assert Fraction(dose['realized_average_update_mass']['post'])==0
    assert dose['task_exposures']==1488 and dose['four_task_tail_batches']==2
    assert dose['planned_teacher_microbatches']['initial']==298


def test_planned_dose_uses_actual_baseline_coefficients_not_equal_task_assumption():
    package=demo('initial',[dict(input_ids=[1,2],target_ids=[2],target_positions=[1])])
    tasks={'a':dict(slots={'initial':slot(package),'post':None})}
    receipts=[]
    for batch in batches():
        ids=batch['task_ids'];weights={task:Fraction(1,2) if task=='a' else Fraction(1,2*(len(ids)-1)) for task in ids}
        evidence=dict(task_batch=batch,packages=[dict(task_id=t,state_id='state',n_state=1,target_token_coefficient=str(weights[t]/2),whole_package_target_tokens=2) for t in ids],
            target_tokens=2*len(ids),sequence_tokens=3*len(ids),rows_completed=len(ids),physical_package_count=len(ids))
        receipts.append(dict(evidence=evidence))
    dose=material.planned_dose(tasks,batches(),old_receipts=receipts,fixed_pi={t:{"state":"1"} for t in "abcde"})
    assert Fraction(dose['realized_average_update_mass']['initial'])==Fraction(1,8)
    assert Fraction(dose['realized_average_update_mass']['old'])==Fraction(7,8)
    assert dose['planned_candidate_total_microbatches']==1488+298


def test_pretrain_rejects_noncomplete_collection_exit_barrier(tmp_path,monkeypatch):
    monkeypatch.setattr(binding,'ROOT',tmp_path)
    path=tmp_path/'barrier/record.json'
    binding.publish(path,dict(protocol_id='protocol',active_workers=[],accepted_jobs={}))
    with pytest.raises(ValueError,match='all six'):
        material._barrier(tmp_path,binding.entry(path),'protocol')


def test_baseline_contract_retains_original_1192_not_894_reference():
    value=training.training_contract()
    assert value['parent_step']==1192 and value['new_optimizer_updates']==298 and value['task_exposures']==1488
    assert value['new_outer_updates']==0 and value['dropout_RNG_consumption_differs_when_extra_forwards_run']


def test_planned_teacher_mass_does_not_inherit_float_pi_roundoff():
    package=demo('initial',[dict(input_ids=[1,2],target_ids=[2],target_positions=[1])])
    tasks={'a':dict(slots={'initial':slot(package),'post':None})}
    probability='1.0000000000000001'
    receipts=[]
    for batch in batches():
        ids=batch['task_ids']
        evidence=dict(task_batch=batch,packages=[dict(task_id=t,state_id='state',n_state=1,
            target_token_coefficient=str(Fraction(probability)/(len(ids)*2)),whole_package_target_tokens=2) for t in ids],
            target_tokens=2*len(ids),sequence_tokens=3*len(ids),rows_completed=len(ids),physical_package_count=len(ids))
        receipts.append(dict(evidence=evidence))
    dose=material.planned_dose(tasks,batches(),old_receipts=receipts,fixed_pi={t:{'state':probability} for t in 'abcde'})
    expected=(296*Fraction(1,20)+2*Fraction(1,16))/298
    assert Fraction(dose['realized_average_update_mass']['initial'])==expected
    assert sum(Fraction(v) for v in dose['realized_average_update_mass'].values())==1


def test_private_native_step_adapts_loss_and_provenance_without_extra_Adam(tmp_path,monkeypatch):
    pool,batch=fixtures();pool.material_schema='v18_researcher_complete_material_binding.v1'
    first=demo('initial',[dict(input_ids=[1,4],target_positions=[1],target_ids=[4])])
    record=dict(id='materials',tasks={'a':dict(slots={'initial':slot(first),'post':None})})
    monkeypatch.setattr(training,'load_demonstrations',lambda point:(record,{'initial':first}))
    class Driver:
        step=driver_api.TrainingDriver.step
        def commit(self,phase,report):self.commits.append((phase,copy.deepcopy(report)))
    d=Driver();d.pool=pool;d.root=tmp_path;d.model=Model();d.optimizer=torch.optim.AdamW(d.model.parameters(),lr=1e-5)
    d.pi=pool._manifest.registration.pi0;d.arm='C-only';d.step_index=1192;d.shared_step=298;d.final_step=1490
    d.execution_plan={};d.outer_steps=();d.outer_done=[298];d.initialized=True;d.tainted=False;d.device='cpu'
    d.schedule=dict(schedule_sha256='frozen',batches=[dict(task_ids=list(batch.task_ids)) for _ in range(1490)])
    d.commits=[]
    training.install_demonstration_consumer(d,{})
    result=d.step()
    assert d.step_index==1193 and len(d.commits)==1 and d.commits[0][0]=='step' and not d.tainted
    assert result['execution_design']=='v75_original_rows_plus_teacher_suffix_rows'
    assert result['original_supervision_policy']=='v14_state_independent_original_span_union.v1'
    assert result['supervision_policy']=='v75_exact_teacher_suffix_plus_unchanged_old.v1'
    assert result['optimizer_step_calls']==1 and result['demonstration_consumption']['teacher_target_tokens']==1
    assert d.commits[0][1]==result


def test_changed_actual_slot_consumption_rejected_at_committed_step():
    point=dict(step=1192,window_task_batches=[dict(task_ids=['a'])],original_schedule_sha256='frozen',
        demonstration_materials=dict(id='materials'),planned_demonstration_per_step=[dict(step=1193,demonstrations=[dict(task_id='a',slot='initial')])])
    report=dict(optimizer_step_calls=1,clip_calls=1,zero_grad_calls=1,actual_parameter_update=True,CPU_control_only=False,
        execution_design='v75_original_rows_plus_teacher_suffix_rows',supervision_policy='v75_exact_teacher_suffix_plus_unchanged_old.v1',
        original_supervision_policy='v14_state_independent_original_span_union.v1',additional_batch_division=False,additional_loss_scaling=False,
        task_batch=dict(task_ids=['a'],step=1193,schedule_id='frozen'),demonstration_slots_do_not_renormalize=True,
        demonstration_consumption=dict(materials_id='materials',step=1193,student_prefix_target_count=0,original_materials_all_rows_consumed=True,
            slots=[dict(task_id='a',slot='initial')]))
    training._check_step_report(report,point,1193)
    report['demonstration_consumption']['slots']=[]
    with pytest.raises(ValueError,match='actual per-step'):
        training._check_step_report(report,point,1193)
