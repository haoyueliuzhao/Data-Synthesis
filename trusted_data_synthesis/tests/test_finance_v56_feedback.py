"""CPU-only durable generation controls; providers are deterministic test stubs."""

import asyncio
import copy
import json
from pathlib import Path

import pytest

import finqa_v56_feedback as resume
from trusted_synthesis.finance_research import storage,harness
from trusted_synthesis.finance_research.contracts import ModelIdentity,ModelTurn,RunConfig,TokenReceipt
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.planning import build_role_plan
from trusted_synthesis.finance_research.providers import parse_qwen_native_response


class ResourceDeferred(RuntimeError):
    errno=12


class LocalStub:
    """No model, tensor, GPU, network or scoring operation exists in this stub."""
    identity=ModelIdentity(backend="local_torch",model_id="V56_CPU_STUB",point_id="CPU_POINT",
                           parameter_digest="a"*64,tokenizer_digest="b"*64,chat_template_digest="c"*64)

    def __init__(self,*,stop_after=None,unknown=False):
        self.actual_model_calls=0
        self.stop_after=stop_after
        self.unknown=unknown

    async def chat(self,messages,tools,config):
        if self.stop_after is not None and self.actual_model_calls==self.stop_after:
            raise ResourceDeferred("CPU simulated capacity boundary before generation")
        self.actual_model_calls+=1
        if self.unknown:
            raise RuntimeError("CPU simulated started invocation without receipt")
        name="run_program" if len(messages)==2 else "submit_program"
        raw='<tool_call>\n'+json.dumps(dict(name=name,arguments=dict(program="subtract(8, 2)")))+'\n</tool_call>'
        request=dict(messages=copy.deepcopy(messages),tools=copy.deepcopy(tools),
                     config=config.model_dump(mode="json"),rendered_prompt_sha256="d"*64,
                     tool_protocol=config.local_tool_protocol,template_tools_kwarg_used=True)
        call="cpu:"+resume.digest([request,raw])
        receipt=TokenReceipt(call_id=call,identity=self.identity,request_sha256=resume.digest(request),
            prompt_input_ids=(1,1,1),raw_generated_token_ids=(3,2),sampled_token_logprobs=(-.1,-.2),
            actual_eos=True,finish_reason="stop",rng_before_sha256="e"*64,rng_after_sha256="f"*64,
            sampling=dict(do_sample=True,temperature=config.temperature,top_p=1.,top_k=0,
                          seed=config.seed,max_new_tokens=config.max_new_tokens,context_limit=config.context_limit,
                          eos_token_ids=[2],actual_model_generate_calls=1,context_truncated=False,
                          host_JSON_repair=False,length_normalized=False,SFT_mask_used=False),
            raw_response_sha256=resume.hashlib.sha256(raw.encode()).hexdigest())
        return ModelTurn(raw_text=raw,tool_calls=parse_qwen_native_response(raw,call_prefix=call)[1],
                         receipt=receipt,provider_metadata=dict(request=request))


@pytest.fixture
def science(tmp_path):
    rows=[dict(id=f"V56_CPU_{i}/2020/page_1.pdf-1",filename=f"V56_CPU_{i}/2020/page_1.pdf",
        pre_text=["USD"],post_text=[],table=[["Year","Revenue"],["2020","8"],["2019","2"]],
        qa=dict(question="Increase?",exe_ans=6,program="subtract(8, 2)",gold_inds={})) for i in range(2)]
    bundles=adapt_finqa(rows,split="test",revision="V56_CPU_ONLY")
    snapshot=tmp_path/"snapshot"
    storage.import_snapshot(bundles,snapshot,source=dict(CPU_TEST_ONLY=True))
    plan=build_role_plan([bundle.public for bundle in bundles],[bundle.lineage for bundle in bundles])
    config=RunConfig(role="test",tier="EVAL_NATIVE",seed=11,temperature=1.,max_steps=4,max_new_tokens=8,
                     harness_id="bigfinance-derived-vtdo-v7",submission_profile="finqa-public-reasoning-v2")

    def prepare(path):
        return storage.prepare_run(snapshot,plan,path,role="test",config=config,identity=LocalStub.identity)

    root=tmp_path/"generation"
    run=prepare(root)
    return dict(root=root,run=run,prepare=prepare,tmp=tmp_path)


def test_pre_call_pause_keeps_returned_prefix_and_resumes_exact_next_request(science):
    f=science
    first=LocalStub(stop_after=1)
    with pytest.raises(resume.GenerationPreCallPause) as caught:
        asyncio.run(resume.execute_run_resumable(f["root"],first,attempt_root=f["tmp"]/"attempt1"))
    assert first.actual_model_calls==1 and caught.value.actual_model_calls==0
    assert caught.value.underlying_exception_type=="ResourceDeferred" and caught.value.errno==12
    before=resume.audit_resume(f["root"])
    assert before["resume_allowed"] and before["actual_returned_turns"]==1 and before["unknown_calls"]==0
    first_return=next((f["root"]/"durable_returns").glob("*/turn0000/record.json"))
    old_bytes=first_return.read_bytes()
    second=LocalStub()
    asyncio.run(resume.execute_run_resumable(f["root"],second,attempt_root=f["tmp"]/"attempt2"))
    assert second.actual_model_calls==3  # First historical turn is never generated again.
    assert first_return.read_bytes()==old_bytes
    _,seal,episodes=storage.sealed_episodes(f["root"])
    assert seal["registered_denominator"]==2 and all(ep.actual_model_calls==2 for ep in episodes)
    assert all(ep.stop_reason=="final_answer" for ep in episodes)
    assert resume.audit_resume(f["root"])["complete_stage"]
    third=LocalStub()
    asyncio.run(resume.execute_run_resumable(f["root"],third,attempt_root=f["tmp"]/"attempt3"))
    assert third.actual_model_calls==0


def test_resource_failure_after_durable_return_never_loses_or_repeats_it(science):
    f=science

    def after(event):
        assert Path(event["actual_return"]["path"]).is_file()
        assert Path(event["returned_event"]["path"]).is_file()
        raise ResourceDeferred("CPU post-return gate")

    first=LocalStub()
    with pytest.raises(ResourceDeferred):
        asyncio.run(resume.execute_run_resumable(f["root"],first,attempt_root=f["tmp"]/"attempt1",after_return=after))
    assert first.actual_model_calls==1
    assert resume.audit_resume(f["root"])["resume_allowed"]
    second=LocalStub()
    asyncio.run(resume.execute_run_resumable(f["root"],second,attempt_root=f["tmp"]/"attempt2"))
    assert second.actual_model_calls==3
    assert storage.sealed_episodes(f["root"])[1]["complete"]


def test_started_unknown_is_never_automatically_reissued(science):
    f=science
    first=LocalStub(unknown=True)
    with pytest.raises(resume.GenerationUnknown):
        asyncio.run(resume.execute_run_resumable(f["root"],first,attempt_root=f["tmp"]/"attempt1"))
    audit=resume.audit_resume(f["root"])
    assert not audit["resume_allowed"] and audit["unknown_calls"]==1
    second=LocalStub()
    with pytest.raises(resume.GenerationUnknown):
        asyncio.run(resume.execute_run_resumable(f["root"],second,attempt_root=f["tmp"]/"attempt2"))
    assert first.actual_model_calls==1 and second.actual_model_calls==0


def test_dangling_intent_without_return_or_zero_call_settlement_is_unknown(science):
    f=science
    task=f["run"]["episode_keys"][0]
    request=dict(messages=[],tools=[],config=f["run"]["config"])
    resume.atomic(f["root"]/f"call_attempts/{task}/turn0000/crashed/intent",dict(
        schema="v56_physical_call_intent.v1",turn_index=0,scientific_request=request,
        scientific_request_sha256=resume.digest(request)))
    audit=resume.audit_resume(f["root"])
    assert audit["unknown_calls"]==1 and not audit["resume_allowed"]


def test_changed_reconstruction_request_is_a_binding_failure_not_a_retry(science,monkeypatch):
    f=science
    with pytest.raises(resume.GenerationPreCallPause):
        asyncio.run(resume.execute_run_resumable(f["root"],LocalStub(stop_after=1),attempt_root=f["tmp"]/"attempt1"))
    original=harness.system_message
    monkeypatch.setattr(harness,"system_message",lambda config:dict(original(config),content="changed scientific system"))
    second=LocalStub()
    with pytest.raises(resume.GenerationBindingError):
        asyncio.run(resume.execute_run_resumable(f["root"],second,attempt_root=f["tmp"]/"attempt2"))
    assert second.actual_model_calls==0


def test_inherit_original_complete_episode_and_partial_turn_with_fresh_audit_identity(science):
    f=science
    original=LocalStub(stop_after=3)
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(f["root"],original))
    inherited=resume.inspect_inherited_run(f["root"],expected_complete=1,expected_partial_turns=1)
    old_complete=Path(inherited["complete"][0]["episode"]["path"]).read_bytes()
    old_partial=Path(inherited["partial"]["episode"]["path"]).read_bytes()
    new=f["tmp"]/"new-generation"
    f["prepare"](new)
    second=LocalStub()
    asyncio.run(resume.execute_run_resumable(new,second,attempt_root=f["tmp"]/"new-attempt",inheritance=inherited))
    assert second.actual_model_calls==1
    assert Path(inherited["partial"]["episode"]["path"]).read_bytes()==old_partial
    assert (new/f"episodes/{inherited['complete'][0]['episode_key']}/episode.json").read_bytes()==old_complete
    _,seal,episodes=storage.sealed_episodes(new)
    assert seal["complete"] and [ep.actual_model_calls for ep in episodes]==[2,2]


def test_interrupted_inheritance_copy_keeps_actual_source_progress_without_double_counting(science):
    f=science
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(f["root"],LocalStub(stop_after=3)))
    draw=resume.inspect_inherited_run(f["root"],expected_complete=1,expected_partial_turns=1)
    inheritance=resume.bound(dict(draws={"0":draw},inherited_complete_episodes=1,
                                  inherited_partial_returned_turns=1))
    new=f["tmp"]/"new-generation"
    f["prepare"](new)  # Crash immediately after the immutable run was created.
    before=resume.audit_resume(new,inheritance=inheritance)
    assert before["resume_allowed"] and before["progress_units"]==4
    row=draw["complete"][0]
    resume.copy_ref(row["episode"],new/f"episodes/{row['episode_key']}/episode.json")
    partial_copy=resume.audit_resume(new,inheritance=inheritance)
    assert partial_copy["progress_units"]==4 and partial_copy["actual_returned_turns"]==3
    second=LocalStub()
    asyncio.run(resume.execute_run_resumable(new,second,attempt_root=f["tmp"]/"new-attempt",inheritance=draw))
    final=resume.audit_resume(new,inheritance=inheritance)
    assert final["progress_units"]==6 and second.actual_model_calls==1
