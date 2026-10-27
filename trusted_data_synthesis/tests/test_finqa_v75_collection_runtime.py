"""Native CPU witnesses for V75 last-state extraction and durable collection."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v75_collection as collection
import finqa_v75_collection_runtime as runtime
import finqa_v74_binding as old_binding
from trusted_synthesis.finance_research import contracts,harness,providers,profiles,settlement,v6_task
MODULES=SimpleNamespace(contracts=contracts,harness=harness,providers=providers,profiles=profiles,settlement=settlement,task=v6_task)
IDENTITIES={name:contracts.ModelIdentity(backend='local_torch',model_id=name,parameter_digest=name+'params',point_id=name+'point',tokenizer_digest='tokens',chat_template_digest='template').model_dump(mode='json') for name in ('P','L')}


def inputs():
    task=contracts.PublicTask(dataset='finqa',task_id='tiny',question='What is one plus one?',sources=(contracts.PublicSource(source_id='table',kind='table',content=[['year','amount'],['2020','2']],locator='table'),),version='test')
    row=dict(task_id='tiny',task_key='finqa/tiny',original_task_key='finqa/tiny',source_group=dict(group='tiny-report',level='report'))
    return dict(id='inputs',tasks=[row],public_tasks={'finqa/tiny':task.model_dump(mode='json')},config=collection.config(),model_bindings={n:dict(model_identity=i) for n,i in IDENTITIES.items()})


def job(phase):
    return dict(job_id=phase+'.shard0',phase=phase,model=phase[0],task_ids=['tiny'],maximum_model_calls=31 if phase=='P.post' else 32)


class Tokenizer:
    overflow=False
    def apply_chat_template(self,messages,*,tools,tokenize,add_generation_prompt):
        return json.dumps([messages,tools],sort_keys=True)
    def __call__(self,text,**kwargs):
        assert kwargs==dict(add_special_tokens=False,truncation=False,padding=False)
        return {'input_ids':[1]*23000 if self.overflow else [len(text),17]}


class Predictor:
    def __init__(self,model='P',responses=None):
        self.model_label=model;self.responses=responses or [('submit_program',{'program':'add(1, 1)'})]
        self.tokenizer=Tokenizer();self.provider=SimpleNamespace(actual_model_calls=0);self.counters={};self.contexts=[]
    def generate(self,context):
        self.contexts.append(copy.deepcopy(context));self.provider.actual_model_calls+=1;self.counters['model_forward_calls']=self.provider.actual_model_calls
        name,args=self.responses[min(len(self.contexts)-1,len(self.responses)-1)];raw='public '+str(name)
        calls=() if name is None else (contracts.ToolCall(call_id='call'+str(len(self.contexts)),name=name,arguments=args,raw_arguments=json.dumps(args)),)
        receipt=contracts.TokenReceipt(call_id='receipt'+str(len(self.contexts)),identity=contracts.ModelIdentity.model_validate(IDENTITIES[self.model_label]),
            request_sha256=contracts.digest(context['request']),prompt_input_ids=tuple(context['prompt_input_ids']),raw_generated_token_ids=(11,12),
            sampled_token_logprobs=None,actual_eos=True,finish_reason='stop',rng_before_sha256='before',rng_after_sha256='after',
            sampling={'eos_token_ids':[12]},raw_response_sha256=hashlib.sha256(raw.encode()).hexdigest())
        turn=contracts.ModelTurn(raw_text=raw,tool_calls=calls,receipt=receipt,provider_metadata={'request':copy.deepcopy(context['request'])})
        return dict(turn=turn.model_dump(mode='json'),actual_model_generate_calls=1,counters_delta={'model_forward_calls':1},model_label=self.model_label)


class Guard:
    def check(self,label,*,boundary):assert boundary


@pytest.fixture(autouse=True)
def safe(monkeypatch,tmp_path):
    monkeypatch.setattr(old_binding,'ROOT',tmp_path);monkeypatch.setattr(runtime,'binding',lambda:old_binding)
    monkeypatch.setattr(v6_task,'execute_public_program',lambda task,program:dict(program=program,result=2,executor_sha256='fixture'))


def run(cond,path,predictor,attempt=1,guard=None):
    return runtime.run_condition(cond,output_dir=path,protocol_id='protocol',inputs_id='inputs',attempt=attempt,
        predictor_factory=lambda:predictor,guard=guard or Guard(),modules=MODULES)


def initial(tmp_path,phase='L.initial',responses=None):
    bundle=inputs();cond=runtime.condition(job(phase),bundle,bundle['tasks'][0],modules=MODULES)
    predictor=Predictor(phase[0],responses)
    return bundle,cond,run(cond,tmp_path/phase,predictor),predictor


def test_initial_collection_generates_every_response_and_settles_native_episode(tmp_path):
    _,cond,result,predictor=initial(tmp_path,'P.initial',[('run_program',{'program':'add(1, 1)'}),('submit_program',{'program':'add(1, 1)'})])
    assert result['new_model_calls']==result['new_tool_calls']==2 and result['teacher_turn_start']==0
    assert result['supervised_teacher_turns']==2 and result['episode']['stop_reason']=='final_answer'
    assert result['reconstruction_tool_calls']==0 and len(predictor.contexts)==2
    assert settlement.episode_is_complete(contracts.Episode.model_validate(result['episode']))


def test_last_L_state_is_actual_pre_final_call_not_first_successful_run(tmp_path):
    bundle,_,source,_=initial(tmp_path,responses=[('run_program',{'program':'add(1, 1)'}),('list_sources',{}),(None,{})])
    cond=runtime.condition(job('P.post'),bundle,bundle['tasks'][0],source,modules=MODULES)
    assert cond['source_turn_index']==cond['teacher_turn_start']==2 and cond['maximum_new_model_calls']==30
    assert len(cond['prefix_turns'])==2 and len(cond['prefix_events'])==2
    assert cond['source_request']==source['episode']['turns'][-1]['provider_metadata']['request']
    assert source['episode']['turns'][-1] not in cond['prefix_turns']
    p=Predictor();result=run(cond,tmp_path/'P.post',p)
    assert result['new_model_calls']==1 and result['episode']['actual_model_calls']==3
    assert result['reconstruction_tool_calls']==2 and result['supervised_teacher_turns']==1
    assert result['episode']['turns'][:2]==source['episode']['turns'][:2]
    assert result['episode']['turns'][0]['receipt']['identity']==IDENTITIES['L']
    assert result['episode']['turns'][-1]['receipt']['identity']==IDENTITIES['P']
    assert p.contexts[0]['request']==cond['source_request']


def test_initial_only_L_has_no_post_demo_and_no_relabelled_second_initial_run(tmp_path):
    bundle,_,source,_=initial(tmp_path,responses=[(None,{})])
    cond=runtime.condition(job('P.post'),bundle,bundle['tasks'][0],source,modules=MODULES)
    assert not cond['applicable'] and cond['maximum_new_model_calls']==0
    result=run(cond,tmp_path/'P.post',None)
    assert result['status']=='NOT_APPLICABLE' and result['episode'] is None and result['new_model_calls']==0


def test_32_total_budget_includes_all_L_prefix_calls(tmp_path):
    bundle,_,source,_=initial(tmp_path,responses=[('list_sources',{})])
    assert len(source['episode']['turns'])==32
    cond=runtime.condition(job('P.post'),bundle,bundle['tasks'][0],source,modules=MODULES)
    assert cond['source_turn_index']==31 and cond['maximum_new_model_calls']==1
    result=run(cond,tmp_path/'P.post',Predictor(responses=[('list_sources',{})]))
    assert result['new_model_calls']==1 and result['budget_exhausted']
    assert len(result['episode']['turns'])==result['episode']['actual_model_calls']==32


def test_no_tool_call_gets_no_reminder_or_second_chance(tmp_path):
    _,_,result,p=initial(tmp_path,'P.initial',[(None,{})])
    assert result['new_model_calls']==1 and result['new_tool_calls']==0 and len(p.contexts)==1
    assert result['episode']['stop_reason']=='no_tool_call'


def test_full_history_overflow_has_zero_generation_and_no_truncation(tmp_path):
    bundle=inputs();cond=runtime.condition(job('P.initial'),bundle,bundle['tasks'][0],modules=MODULES)
    p=Predictor();p.tokenizer.overflow=True
    result=run(cond,tmp_path/'overflow',p)
    assert result['context_exhausted'] and result['new_model_calls']==0 and not p.contexts
    assert settlement.episode_is_complete(contracts.Episode.model_validate(result['episode']))


def test_dangling_model_intent_prevents_new_attempt(tmp_path):
    bundle=inputs();cond=runtime.condition(job('P.initial'),bundle,bundle['tasks'][0],modules=MODULES)
    old_binding.publish(tmp_path/'unknown/model/step0000/attempt0001/intent.json',{'unknown':'intent'})
    with pytest.raises(runtime.UnknownCollection):run(cond,tmp_path/'unknown',Predictor(),attempt=2)


def test_return_persisted_before_resource_check_and_never_generated_again(tmp_path):
    class Fail(Guard):
        def check(self,label,*,boundary):
            if label=='after_durable_v75_model_return':raise RuntimeError('resource failure')
    bundle=inputs();cond=runtime.condition(job('P.initial'),bundle,bundle['tasks'][0],modules=MODULES)
    first=Predictor()
    with pytest.raises(RuntimeError):run(cond,tmp_path/'retry',first,guard=Fail())
    assert first.provider.actual_model_calls==1 and runtime.audit_condition(tmp_path/'retry')['resume_allowed']
    second=Predictor();result=run(cond,tmp_path/'retry',second,attempt=2)
    assert second.provider.actual_model_calls==0 and result['new_model_calls']==1


def test_corrupted_L_tool_event_blocks_before_teacher_generation(tmp_path):
    bundle,_,source,_=initial(tmp_path,responses=[('list_sources',{}),(None,{})])
    cond=runtime.condition(job('P.post'),bundle,bundle['tasks'][0],source,modules=MODULES)
    cond['prefix_events'][0]['raw_output']['sources'][0]['locator']='corrupt'
    p=Predictor()
    with pytest.raises(ValueError,match='cannot reproduce'):run(cond,tmp_path/'P.post',p)
    assert not p.contexts


def test_scoped_predictor_adapter_uses_same_native_provider_with_sft_role_only():
    original=Predictor('P')
    original.closed=False;original.final=SimpleNamespace(RunConfig=contracts.RunConfig)
    original.bindings={'model_identity':IDENTITIES['P']};original.guard=Guard()
    original._delta=lambda before:{'model_forward_calls':1}
    config=contracts.RunConfig.model_validate(collection.config())
    task=contracts.PublicTask.model_validate(inputs()['public_tasks']['finqa/tiny'])
    context=runtime._new_request(harness.public_initial_messages(task,config),harness.episode_tool_specs(config),config,original)
    async def chat(messages,tools,actual_config):
        assert messages==context['request']['messages'] and tools==context['request']['tools']
        assert actual_config.role=='sft' and actual_config.temperature==0
        return contracts.ModelTurn.model_validate(original.generate(context)['turn'])
    original.provider.chat=chat
    adapter=runtime.Predictor.__new__(runtime.Predictor);adapter.original=original
    value=adapter.generate(context)
    assert value['actual_model_generate_calls']==1 and value['model_label']=='P'
    assert value['turn']['receipt']['prompt_input_ids']==context['prompt_input_ids']
    foreign=copy.deepcopy(context);foreign['request']['config']['role']='development'
    with pytest.raises(ValueError,match='SFT collection contract'):
        adapter.generate(foreign)
    assert original.provider.actual_model_calls==1
