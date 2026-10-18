"""Only CPU mock calls: bounded UNKNOWN reexecution and native provider hooks."""

import asyncio
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import finqa_v54_temperature as temperature
import finqa_v55_feedback_recovery as recovery
from test_finance_research_providers import Model, Tokenizer, feedback_config
from test_finance_v54_temperature import SamplingModel, condition
from trusted_synthesis.finance_research.providers import local_model_identity


def messages(task="q0"):
    return [dict(role="system", content="CPU fixture only"),
            dict(role="user", content=json.dumps(dict(dataset="finqa", task_id=task)))]


def request(config, task="q0"):
    actual = messages(task)
    return dict(messages=actual, tools=[], config=config.model_dump(mode="json"),
                rendered_prompt_sha256=hashlib.sha256(json.dumps(actual).encode()).hexdigest(),
                tool_protocol=config.local_tool_protocol, template_tools_kwarg_used=True)


@pytest.fixture
def authorized(tmp_path):
    old, new = tmp_path / "v54_feedback_temperature_01", tmp_path / "v54_feedback_temperature_01/recovery_01"
    model, tokenizer = SamplingModel(), Tokenizer()
    rows = {}
    config = feedback_config(temperature=0.5, seed=11)
    original_request = request(config)
    for seed in (137,251,389):
        identity = local_model_identity(model, tokenizer, model_id="cpu-mock", point_id=f"point-{seed}")
        bound = condition(identity, count=350, production=True)
        refs = {}
        for key in ("parent", "worker_failure", "actual_exit", "T1_intent", "draw0", "draw1",
                    "condition", "incomplete", "failure_event", "episode"):
            directory = old / f"seed{seed}" / key
            recovery._atomic_record(directory, dict(seed=seed, fixture=True, evidence=key))
            refs[key] = recovery._read(directory / "record.json")[1]
        row = dict(seed=seed, condition=bound, expected_condition_id=bound["id"],
                   point_id=identity.point_id, parameter_digest=identity.parameter_digest,
                   authorized_reexecution_count=int(seed in (137,389)),
                   original_unknown_model_calls=int(seed in (137,389)),
                   original_successful_model_returns=0,
                   old_parent=refs["parent"], old_worker_failure=refs["worker_failure"],
                   old_actual_exit=refs["actual_exit"], old_T1_intent=refs["T1_intent"],
                   old_T1_draw_runs=[refs["draw0"],refs["draw1"]])
        if seed in (137,389):
            row.update(old_condition=refs["condition"], old_incomplete=refs["incomplete"],
                       old_failure_event=refs["failure_event"],old_episode=refs["episode"],
                       original_task_id="q0", original_episode_key=bound["ordered_episode_roster"][0]["episode_key"],
                       draw_index=0,draw_seed=11,turn_index=0,
                       scientific_request=original_request,
                       scientific_request_sha256=recovery.digest(original_request))
        else:
            row.update(scientific_request=None,scientific_request_sha256=None,first_execution_only=True)
        rows[str(seed)]=row
    authorization = recovery._bound(dict(
        schema=recovery.AUTHORIZATION_SCHEMA,old_root=str(old),recovery_root=str(new),
        seeds=rows,total_authorized_reexecutions=2,new_logical_feedback_budget=2100,
        claim_reset_allowed=False,old_unknown_records_written=False,
        failure_or_new_unknown_stops_without_retry=True,
    ))
    return dict(root=new,old=old,authorization=authorization,model=model,tokenizer=tokenizer,
                config=config,request=original_request)


def guard(fixture,seed=137):
    authorization=fixture["authorization"]
    return recovery.RecoveryGuard(fixture["root"],seed,authorization["seeds"][str(seed)]["condition"],
                                   authorization,"new-audit-protocol")


def provider(fixture,guard,model=None):
    return temperature.LocalTorchProvider(model or fixture["model"],fixture["tokenizer"],
        temperature.providers.ModelIdentity.model_validate(guard.condition["identity"]),
        condition=guard.condition,recovery_guard=guard)


def test_native_hook_claims_before_counter_then_resolves_actual_return_and_allows_new_work(authorized):
    f=authorized
    g=guard(f)
    local=provider(f,g)
    call_counts=[]
    native_before=g.before_generate

    def before(actual,sha):
        call_counts.append(local.actual_model_calls)
        native_before(actual,sha)

    g.before_generate=before
    turn=asyncio.run(local.chat(messages(),[],f["config"]))
    claim=recovery._read(g.directory/"claim/record.json")[0]
    resolution=recovery._read(g.directory/"resolution/record.json")[0]
    assert call_counts==[0] and local.actual_model_calls==f["model"].calls==1
    assert resolution["claim_id"]==claim["id"]
    assert resolution["actual_returned_turn"]==turn.model_dump(mode="json")
    assert resolution["old_unknown_record_preserved"] and not resolution["old_unknown_reclassified"]
    assert not resolution["whole_episode_complete_claimed"]
    assert turn.receipt.sampling["temperature"]==0.5
    assert len(turn.receipt.sampled_token_logprobs)==len(turn.receipt.raw_generated_token_ids)==2
    assert turn.receipt.actual_eos

    # The same guard spans later turns, new tasks, and the second draw/provider.
    later=messages()+[dict(role="assistant",content="previous actual response")]
    asyncio.run(local.chat(later,[],f["config"]))
    asyncio.run(local.chat(messages("q1"),[],f["config"]))
    second_draw=provider(f,g)
    asyncio.run(second_draw.chat(messages(),[],f["config"].model_copy(update={"seed":29})))
    assert f["model"].calls==4 and g.resolved_this_process
    with pytest.raises(FileExistsError):
        asyncio.run(local.chat(messages(),[],f["config"]))
    assert f["model"].calls==4 and local.actual_model_calls==3
    assert recovery._read(g.directory/"claim/record.json")[0]==claim


def test_failed_generate_consumes_once_claim_and_recreated_guard_cannot_repeat(authorized):
    class FailingModel(Model):
        def generate(self,**kwargs):
            self.calls+=1
            raise RuntimeError("CPU simulated incomplete call")

    f=authorized
    model=FailingModel()
    g=guard(f)
    local=provider(f,g,model)
    with pytest.raises(temperature.providers.ProviderCallError) as caught:
        asyncio.run(local.chat(messages(),[],f["config"]))
    assert caught.value.settlement=="unknown" and caught.value.actual_model_calls==1
    assert (g.directory/"claim/record.json").is_file()
    assert not (g.directory/"resolution").exists()
    with pytest.raises(ValueError,match="unresolved claimed"):
        asyncio.run(local.chat(messages("q1"),[],f["config"]))
    recreated=provider(f,guard(f),model)
    with pytest.raises(FileExistsError):
        asyncio.run(recreated.chat(messages(),[],f["config"]))
    assert model.calls==1 and recreated.actual_model_calls==0


def test_competing_guards_have_one_atomic_claim_winner(authorized):
    first,second=guard(authorized),guard(authorized)
    req=authorized["request"]

    def attempt(g):
        try:
            g.before_generate(req,recovery.digest(req))
            return "claimed"
        except FileExistsError:
            return "already_claimed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,[first,second]))
    assert sorted(outcomes)==["already_claimed","claimed"]
    assert recovery._read(first.directory/"claim/record.json")[0]["authorized_reexecution_ordinal"]==1


@pytest.mark.parametrize("change", ["task","configuration","prompt_render"])
def test_changed_scientific_request_is_rejected_before_claim_or_generate(authorized,change):
    f=authorized
    g=guard(f)
    altered=copy.deepcopy(f["request"])
    if change=="task":
        altered=request(f["config"],"q1")
    elif change=="configuration":
        altered["config"]["temperature"]=1.0
    else:
        altered["rendered_prompt_sha256"]="a"*64
    with pytest.raises(ValueError):
        g.before_generate(altered,recovery.digest(altered))
    assert not (g.directory/"claim").exists()
    assert f["model"].calls==0


def test_seed251_is_first_execution_only_without_a_reexecution_claim(authorized):
    g=guard(authorized,251)
    local=provider(authorized,g)
    turn=asyncio.run(local.chat(messages(),[],authorized["config"]))
    assert local.actual_model_calls==1 and turn.receipt is not None
    assert not g.directory.exists()


def test_changed_condition_or_quota_cannot_be_admitted(authorized):
    f=authorized
    altered=copy.deepcopy(f["authorization"])
    altered["seeds"]["137"]["authorized_reexecution_count"]=2
    altered=recovery._bound({k:v for k,v in altered.items() if k!="id"})
    with pytest.raises(ValueError,match="seed/condition/point/dose"):
        recovery.checked_authorization(altered)
    changed=copy.deepcopy(f["authorization"]["seeds"]["137"]["condition"])
    changed["identity"]["point_id"]="another-point"
    with pytest.raises(ValueError,match="same scientific condition"):
        recovery.RecoveryGuard(f["root"],137,changed,f["authorization"],"new-audit-protocol")
