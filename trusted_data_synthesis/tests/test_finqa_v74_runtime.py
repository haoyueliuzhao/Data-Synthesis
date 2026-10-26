"""Native CPU tool state and durable cross-model continuation contracts."""
from __future__ import annotations
import copy
import hashlib
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import finqa_v74_runtime as runtime
from trusted_synthesis.finance_research import contracts, harness, providers, profiles, settlement, v6_task
from trusted_synthesis.finance_research.contracts import ModelTurn, TokenReceipt, ModelIdentity, ToolCall, RunConfig, PublicTask, PublicSource

MODULES = SimpleNamespace(contracts=contracts,harness=harness,providers=providers,profiles=profiles,settlement=settlement,task=v6_task)
IDENTITIES = {name:ModelIdentity(backend='local_torch',model_id=name,parameter_digest=name+'params',point_id=name+'point',tokenizer_digest='tokens',chat_template_digest='template').model_dump(mode='json') for name in ['P','L']}


def turn(name=None, arguments=None, *, identity='P', prompt=(7,), call_id='test-call'):
    args = arguments or {}
    raw = f'public {name}' if name else 'plain public text'
    calls = () if name is None else (ToolCall(call_id=call_id,name=name,raw_arguments=__import__('json').dumps(args),arguments=args),)
    return ModelTurn(raw_text=raw,tool_calls=calls,receipt=TokenReceipt(call_id='receipt-'+call_id,
        identity=ModelIdentity.model_validate(IDENTITIES[identity]),request_sha256='request',
        prompt_input_ids=tuple(prompt),raw_generated_token_ids=(11,12),sampled_token_logprobs=None,
        actual_eos=True,finish_reason='stop',rng_before_sha256='before',rng_after_sha256='after',
        sampling={'eos_token_ids':[12]},raw_response_sha256=hashlib.sha256(raw.encode()).hexdigest())).model_dump(mode='json')


def condition(*, prior=0, first='run_program', actor='P'):
    config=RunConfig(harness_id='bigfinance-derived-vtdo-v7',submission_profile='finqa-public-reasoning-v2',role='development',temperature=0.)
    task=PublicTask(dataset='finqa',task_id='tiny',question='What is one plus one?',sources=(PublicSource(source_id='table',kind='table',content=[['year','amount'],['2020','2']],locator='table'),),version='test')
    public=profiles.public_run_view(task,config.submission_profile)
    messages=harness.public_initial_messages(task,config)
    session=v6_task.PublicProgramSession(public,invocation_context={'run_id':'old','episode_id':'old-episode','attempt_index':1})
    ts,es,ss=[],[],[]
    source='L' if actor=='P' else 'P'
    for i in range(prior):
        old=turn('list_sources',identity=source,call_id='old'+str(i))
        oldturn=ModelTurn.model_validate(old)
        event=session.execute(oldturn.tool_calls[0]).model_dump(mode='json')
        ts.append(old);es.append(event)
        ss.append(dict(attempt_index=i,state='returned',actual_model_calls=1,request_sha256='old-request',evidence={'old':True}))
        messages.append(providers.canonical_assistant_message(oldturn));messages.append(dict(role='tool',tool_call_id=event['call_id'],content=event['visible_output']))
    category='plain_no_tool_call' if first is None else ('compliant_submit_candidate' if first=='submit_program' else 'compliant_nonterminal_candidate')
    firstturn=turn(first,{'program':'add(1, 1)'} if first in ['run_program','submit_program'] else {},identity=actor)
    return dict(condition_id='condition',task_key='finqa:tiny',group='F',direction=actor+'_from_'+source,
        source_model=source,actor_model=actor,actor_identity=IDENTITIES[actor],source_provider=IDENTITIES[source],
        source_turn_index=prior,prefix_turns=ts,prefix_events=es,prefix_settlements=ss,
        config=config.model_dump(mode='json'),public_task=public.model_dump(mode='json'),
        public_task_sha256=contracts.digest(public),first_action_category=category,
        remaining_model_calls=32-prior-1 if category=='compliant_nonterminal_candidate' else 0,
        first_turn=firstturn,prompt_input_ids=[7],first_response_returned={'id':'old-return'},
        first_response_result={'id':'old-normalized'},source_episode={'id':'old-episode'},
        original_request=dict(messages=messages,tools=harness.episode_tool_specs(config),config=config.model_dump(mode='json')))


class Guard:
    def check(self,label,*,boundary):
        assert boundary


class Tokenizer:
    overflow=False
    def apply_chat_template(self,messages,*,tools,tokenize,add_generation_prompt):
        return __import__('json').dumps([messages,tools],sort_keys=True)
    def __call__(self,text,**kwargs):
        assert kwargs==dict(add_special_tokens=False,truncation=False,padding=False)
        return {'input_ids':[1]*23000 if self.overflow else [len(text),17]}


class Predictor:
    model_label='P'
    def __init__(self,responses=None):
        self.provider=SimpleNamespace(actual_model_calls=0)
        self.counters={}
        self.tokenizer=Tokenizer()
        self.responses=responses or [('submit_program',{'program':'add(1, 1)'})]
        self.contexts=[]
    def generate(self,context):
        self.contexts.append(copy.deepcopy(context))
        self.provider.actual_model_calls+=1
        self.counters['model_forward_calls']=self.provider.actual_model_calls
        name,args=self.responses[min(len(self.contexts)-1,len(self.responses)-1)]
        value=turn(name,args,prompt=context['prompt_input_ids'],call_id='new'+str(len(self.contexts)))
        value['receipt']['request_sha256']=contracts.digest(context['request'])
        value['provider_metadata']['request']=copy.deepcopy(context['request'])
        return dict(turn=value,actual_model_generate_calls=1,counters_delta={'model_forward_calls':1},model_label='P')


@pytest.fixture(autouse=True)
def safe_runtime(monkeypatch,tmp_path):
    monkeypatch.setattr(runtime.b,'ROOT',tmp_path)
    # Pure native session path; no FinQA reference/scorer or real program execution.
    monkeypatch.setattr(v6_task,'execute_public_program',lambda task,program:dict(program=program,result=2,executor_sha256='fixture'))


def run(c,tmp_path,predictor=None,*,attempt=1,guard=None):
    def factory():
        assert predictor is not None,'immediate terminal loaded a model'
        return predictor
    return runtime.run_condition(c,output_dir=tmp_path/'condition',protocol_id='protocol',inputs_id='inputs',attempt=attempt,predictor_factory=factory,guard=guard or Guard(),modules=MODULES)


@pytest.mark.parametrize('first,expected',[('submit_program','final_answer'),(None,'no_tool_call')])
def test_immediate_first_response_is_exactly_reused_without_loading_any_model(tmp_path,first,expected):
    c=condition(first=first,actor='L',prior=1)
    result=run(c,tmp_path)
    assert result['episode']['stop_reason']==expected
    assert result['new_model_calls']==0
    assert result['reconstruction_tool_calls']==1
    assert result['new_tool_calls']==int(first is not None)
    assert result['episode']['turns'][:1]==c['prefix_turns']
    assert result['episode']['turns'][1]==c['first_turn']
    assert result['episode']['turns'][0]['receipt']['identity']==IDENTITIES['P']
    assert result['episode']['turns'][1]['receipt']['identity']==IDENTITIES['L']
    assert result['episode']['call_settlements'][0]==c['prefix_settlements'][0]
    assert settlement.episode_is_complete(contracts.Episode.model_validate(result['episode']))
    assert run(c,tmp_path)==result


def test_nonterminal_actual_execution_then_new_parent_turn_sees_observation(tmp_path):
    c=condition(prior=1)
    p=Predictor()
    result=run(c,tmp_path,p)
    assert result['new_model_calls']==1 and result['new_tool_calls']==2
    assert result['episode']['final_program']=='add(1, 1)'
    assert result['episode']['tool_events'][1]['result_handle']=='r2'
    assert result['episode']['tool_events'][2]['result_handle']=='r3'
    messages=p.contexts[0]['request']['messages']
    assert messages[:len(c['original_request']['messages'])]==c['original_request']['messages']
    assert messages[-1]['role']=='tool' and '"result": 2' in messages[-1]['content']
    assert result['provenance']['episode_provider_semantics']=='successor_only_not_homogeneous_trajectory'


def test_exact_original_tool_state_reconstruction_rejects_changed_output(tmp_path):
    c=condition(prior=1)
    c['prefix_events'][0]['raw_output']['sources'][0]['locator']='corrupted'
    with pytest.raises(ValueError,match='cannot reproduce'):
        run(c,tmp_path,Predictor())
    assert not (tmp_path/'condition/model').exists()


def test_original_budget_counts_prior_and_reused_first_response(tmp_path):
    c=condition(prior=30)
    p=Predictor([('list_sources',{})])
    result=run(c,tmp_path,p)
    assert result['budget_exhausted'] and result['new_model_calls']==1
    assert result['episode']['stop_reason']=='max_steps'
    assert len(result['episode']['turns'])==32
    assert result['episode']['actual_model_calls']==32


def test_no_budget_remains_after_reused_first_nonterminal(tmp_path):
    c=condition(prior=31)
    result=run(c,tmp_path)
    assert result['budget_exhausted'] and result['new_model_calls']==0


def test_dangling_new_model_intent_blocks_reissue(tmp_path):
    c=condition()
    runtime.b.publish(tmp_path/'condition/model/step0001/attempt0001/intent.json',{'kind':'old-unknown'})
    with pytest.raises(runtime.UnknownContinuation):
        run(c,tmp_path,Predictor(),attempt=2)


def test_saved_model_response_is_durable_before_resource_check_and_is_not_generated_twice(tmp_path):
    class StopAfterReturned(Guard):
        def check(self,label,*,boundary):
            if label=='after_durable_hybrid_model_return':
                raise RuntimeError('resource stop after saved return')
    c=condition()
    first=Predictor()
    with pytest.raises(RuntimeError,match='resource stop'):
        run(c,tmp_path,first,guard=StopAfterReturned())
    assert first.provider.actual_model_calls==1
    assert runtime.audit_condition(tmp_path/'condition')['resume_allowed']
    second=Predictor()
    result=run(c,tmp_path,second,attempt=2)
    assert second.provider.actual_model_calls==0
    assert result['new_model_calls']==1
    assert result['durable_new_tool_reconstruction_calls']==1
    assert result['new_tool_calls']==2


def test_context_overflow_terminates_without_truncation_or_generate(tmp_path):
    c=condition()
    p=Predictor();p.tokenizer.overflow=True
    result=run(c,tmp_path,p)
    assert result['context_exhausted'] and result['new_model_calls']==0
    assert p.provider.actual_model_calls==0 and not p.contexts
    assert result['episode']['stop_reason']=='context_exceeded'
    assert settlement.episode_is_complete(contracts.Episode.model_validate(result['episode']))


def test_no_call_after_first_nonterminal_ends_without_reminder(tmp_path):
    c=condition()
    p=Predictor([(None,{})])
    result=run(c,tmp_path,p)
    assert result['new_model_calls']==result['new_tool_calls']==1
    assert result['episode']['stop_reason']=='no_tool_call'


def test_preserved_mixed_identity_cannot_be_relabelled_before_scoring(tmp_path):
    c=condition(first='submit_program',actor='L',prior=1)
    result=copy.deepcopy(run(c,tmp_path))
    result['episode']['turns'][0]['receipt']['identity']=IDENTITIES['L']
    result['episode_sha256']=contracts.digest(result['episode'])
    with pytest.raises(ValueError,match='prefix'):
        runtime.validate_outcome(c,result)
