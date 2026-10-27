"""Durable native collection on fixed training tasks and L terminal boundaries.

Only the role changes to sft in the inference adapter. The pinned saved-model
loader, LocalTorchProvider, tool language and greedy generation stay unchanged.
The L prefix is context only; all new post-boundary responses are from P.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import importlib
import json
from pathlib import Path
import time
from types import SimpleNamespace


def binding():
    return importlib.import_module("finqa_v75_binding")


def require(condition,message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return binding().digest(value)


def native_modules():
    b=binding();b.install_scientific_paths();b.install_registered_auxiliary()
    base="trusted_synthesis.finance_research."
    return SimpleNamespace(contracts=importlib.import_module(base+"contracts"),
        harness=importlib.import_module(base+"harness"),providers=importlib.import_module(base+"providers"),
        task=importlib.import_module(base+"v6_task"),settlement=importlib.import_module(base+"settlement"),
        profiles=importlib.import_module(base+"profiles"))


def validate_config(config):
    require((config.harness_id,config.submission_profile,config.local_tool_protocol,
        config.max_steps,config.max_new_tokens,config.context_limit,config.temperature,
        config.top_p,config.top_k,config.seed,config.tier,config.role)==
        ("bigfinance-derived-vtdo-v7","finqa-public-reasoning-v2","qwen2.5-native-tool-call-v1",
         32,2048,24576,0.0,1.0,0,20260928,"EVAL_NATIVE","sft"),"fixed native SFT collection contract changed")


class Predictor:
    """Exact P/L frozen inference implementation, with an explicit sft role gate."""
    def __init__(self,checkpoint_ref,model_label,guard,bindings):
        b=binding();require(model_label in ("P","L"),"collection uses only registered P/L")
        self.original=b.source_v73("runtime").Predictor(checkpoint_ref,model_label,guard,bindings)

    def __getattr__(self,name):
        return getattr(self.original,name)

    def generate(self,context):
        p=self.original
        require(not p.closed,"predictor is closed")
        config=p.final.RunConfig.model_validate(context["request"]["config"])
        validate_config(config)
        actual=_new_request(context["request"]["messages"],context["request"]["tools"],config,p)
        require(actual==context,"actual native template/request tokens differ")
        require(actual["prompt_input_ids"] and len(actual["prompt_input_ids"])+2048<=24576,"full prompt exceeds fixed context")
        p.guard.check("before_v75_collection_response",boundary=True)
        before,before_calls=p.counters,p.provider.actual_model_calls
        request=context["request"]
        turn=asyncio.run(p.provider.chat(copy.deepcopy(request["messages"]),copy.deepcopy(request["tools"]),config))
        value=turn.model_dump(mode="json")
        _verify_turn(value,p.bindings["model_identity"],context)
        require(p.provider.actual_model_calls-before_calls==1,"native response must make one model.generate call")
        return dict(turn=value,counters_delta=p._delta(before),model_label=p.model_label,
            actual_model_generate_calls=1,input_tokens=len(context["prompt_input_ids"]),
            generated_tokens=len(value["receipt"]["raw_generated_token_ids"]),
            tools_executed=0,native_scoring_calls=0,external_API_calls=0)

    def close(self):
        return self.original.close()


class UnknownCollection(RuntimeError):
    pass


def _check(guard,label):
    if guard is not None:
        guard.check(label,boundary=True)


def _new_request(messages,tools,config,predictor):
    rendered=predictor.tokenizer.apply_chat_template(copy.deepcopy(messages),tools=copy.deepcopy(tools),
        tokenize=False,add_generation_prompt=True)
    ids=list(predictor.tokenizer(rendered,add_special_tokens=False,truncation=False,padding=False)["input_ids"])
    request=dict(messages=copy.deepcopy(messages),tools=copy.deepcopy(tools),config=config.model_dump(mode="json"),
        tool_protocol=config.local_tool_protocol,template_tools_kwarg_used=True,
        rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest())
    return dict(request=request,prompt_input_ids=ids)


def _verify_turn(turn,identity,context=None):
    receipt=turn["receipt"]
    require(receipt and receipt["identity"]==identity,"response checkpoint identity changed")
    require(receipt["raw_response_sha256"]==hashlib.sha256(turn["raw_text"].encode()).hexdigest(),"response text changed")
    require(receipt["finish_reason"]==turn["finish_reason"] and 0<len(receipt["raw_generated_token_ids"])<=2048,
        "response EOS/length evidence differs")
    if context is not None:
        require(receipt["prompt_input_ids"]==context["prompt_input_ids"]
            and receipt["request_sha256"]==digest(context["request"])
            and turn["provider_metadata"]["request"]==context["request"],"response not bound to requested complete native history")


def audit_condition(root):
    b=binding();root=Path(root)
    unknown,models,tools,restorations=[],[],[],[]
    for path in sorted(root.glob("model/step*/attempt*/intent.json")):
        intent=b.checked(path);returned=path.with_name("returned.json");rejected=path.with_name("not_executed.json")
        require(not(returned.exists() and rejected.exists()),"model call both returned and rejected")
        if returned.exists():
            row=b.checked(returned);require(row["intent_id"]==intent["id"],"model return has a foreign intent");models.append(row)
        elif rejected.exists():
            row=b.checked(rejected);require(row["intent_id"]==intent["id"] and row["actual_model_calls"]==0
                and row["confirmed_forward_calls"]==0,"zero-call rejection evidence changed")
        else:unknown.append(str(path))
    for pattern,target,reconstruction in (("tool/step*/intent.json",tools,False),("reconstruction/attempt*/event*/intent.json",restorations,True)):
        for path in sorted(root.glob(pattern)):
            returned=path.with_name("returned.json")
            if not returned.exists():unknown.append(str(path));continue
            row,intent=b.checked(returned),b.checked(path)
            require(row["intent_id"]==intent["id"],"tool return has a foreign intent")
            if reconstruction:require(row["exact_event_match"] is True,"failed state restoration cannot resume")
            target.append(row)
    require(len({row["step"] for row in models})==len(models),"a model response was regenerated")
    complete=(root/"result.json").exists()
    result=b.checked(root/"result.json") if complete else None
    require(not complete or result["status"] in ("COMPLETE","NOT_APPLICABLE"),"invalid terminal collection status")
    return dict(complete=complete,status=result["status"] if result else "PENDING",unknown_calls=len(unknown),
        unknown_intents=unknown,resume_allowed=not unknown,new_model_calls=len(models),new_tool_calls=len(tools),
        reconstruction_tool_calls=len(restorations),progress_units=len(models)+len(tools)+int(complete),
        completed_digest=digest([row["id"] for row in models+tools]+([result["id"]] if result else [])))


def audit(job,stable_root):
    root=Path(stable_root);states=[audit_condition(root/"outputs"/digest(task)) for task in job["task_ids"]]
    allowed={digest(task) for task in job["task_ids"]}
    require(all(path.name in allowed for path in (root/"outputs").glob("*") if path.is_dir()),"unregistered collected task")
    return dict(progress_units=sum(v["progress_units"] for v in states),
        completed_digest=digest([v["completed_digest"] for v in states]),
        unknown_calls=sum(v["unknown_calls"] for v in states),
        unknown_intents=[p for v in states for p in v["unknown_intents"]],resume_allowed=all(v["resume_allowed"] for v in states),
        completed_slots=sum(v["complete"] for v in states),terminal_conditions=sum(v["status"]=="COMPLETE" for v in states),
        not_applicable=sum(v["status"]=="NOT_APPLICABLE" for v in states),
        new_model_calls=sum(v["new_model_calls"] for v in states),new_tool_calls=sum(v["new_tool_calls"] for v in states),
        reconstruction_tool_calls=sum(v["reconstruction_tool_calls"] for v in states))


def condition(job,bundle,task,source_L=None,modules=None):
    """Build only the real L pre-final-response prefix, never its future turn."""
    m=modules or native_modules();c=m.contracts
    config=c.RunConfig.model_validate(bundle["config"]);validate_config(config)
    phase=job["phase"];require(phase in ("L.initial","P.initial","P.post"),"foreign collection phase")
    model=phase[0];require(job["model"]==model,"phase/actor differs")
    original=c.PublicTask.model_validate(bundle["public_tasks"][task["original_task_key"]])
    public=m.profiles.public_run_view(original,config.submission_profile)
    base=dict(schema="v75_training_collection_condition.v1",condition_id=digest([phase,task["original_task_key"]]),
        phase=phase,task_id=task["task_id"],task_key=task["original_task_key"],original_task_key=task["original_task_key"],
        source_group=task["source_group"],actor_model=model,actor_identity=bundle["model_bindings"][model]["model_identity"],
        public_task=public.model_dump(mode="json"),public_task_sha256=digest(public.model_dump(mode="json")),
        config=config.model_dump(mode="json"))
    if phase!="P.post":
        return dict(base,applicable=True,source_turn_index=0,teacher_turn_start=0,maximum_new_model_calls=32,
            prefix_turns=[],prefix_events=[],prefix_settlements=[],source_L_outcome=None,
            source_L_stop_reason=None,source_request=dict(messages=m.harness.public_initial_messages(original,config),
                tools=m.harness.episode_tool_specs(config),config=config.model_dump(mode="json")))
    require(source_L is not None and source_L["phase"]=="L.initial" and source_L["task_id"]==task["task_id"]
        and source_L["status"]=="COMPLETE","post condition requires its complete L collection")
    episode=source_L["episode"]
    require(source_L["episode_sha256"]==digest(episode) and episode["task_id"]==task["task_id"]
        and episode["dataset"]==original.dataset and episode["public_task_sha256"]==base["public_task_sha256"],
        "L source task or actual episode bytes changed")
    require(episode["provider"]==bundle["model_bindings"]["L"]["model_identity"]
        and episode["config"]==config.model_dump(mode="json") and episode["all_provider_calls_settled"] is True,
        "L source identity/config/settlement changed")
    turns=episode["turns"]
    if len(turns)<=1:
        return dict(base,applicable=False,source_turn_index=0,teacher_turn_start=None,maximum_new_model_calls=0,
            source_L_outcome=dict(id=source_L["id"],episode_sha256=source_L["episode_sha256"]),
            source_L_stop_reason=episode["stop_reason"],reason="last_L_model_call_is_initial_or_no_returned_model_call",
            source_initial_request_not_duplicated=True)
    bindex=len(turns)-1
    request=turns[-1]["provider_metadata"]["request"]
    prefix=turns[:bindex];events=episode["tool_events"][:bindex]
    require(len(events)==bindex and all(len(turn["tool_calls"])==1 for turn in prefix)
        and [turn["tool_calls"][0]["call_id"] for turn in prefix]==[e["call_id"] for e in events],
        "L pre-last-call prefix lacks complete chronological native tools")
    require(not any(e["name"]=="submit_program" and not e["is_error"] for e in events),"L prefix already terminal")
    require(all(s["state"]=="returned" and s["actual_model_calls"]==1 for s in episode["call_settlements"][:bindex]),
        "L prefix has an unsettled or uncounted source call")
    require(request["config"]==config.model_dump(mode="json")
        and turns[-1]["receipt"]["request_sha256"]==digest(request),"last actual L request binding changed")
    return dict(base,applicable=True,source_turn_index=bindex,teacher_turn_start=bindex,maximum_new_model_calls=32-bindex,
        prefix_turns=copy.deepcopy(prefix),prefix_events=copy.deepcopy(events),prefix_settlements=copy.deepcopy(episode["call_settlements"][:bindex]),
        source_request=copy.deepcopy(request),source_prompt_input_ids=copy.deepcopy(turns[-1]["receipt"]["prompt_input_ids"]),
        source_L_outcome=dict(id=source_L["id"],episode_sha256=source_L["episode_sha256"]),source_L_stop_reason=episode["stop_reason"],
        source_L_last_response_excluded=True,source_L_future_events_excluded=True)


def validate_outcome(cond,result,modules=None):
    require(result["condition_id"]==cond["condition_id"] and result["task_id"]==cond["task_id"],"collected result condition changed")
    if not cond["applicable"]:
        require(result["status"]=="NOT_APPLICABLE" and result["episode"] is None and result["new_model_calls"]==0,
            "absent post state cannot receive demonstration weight or generation")
        return True
    require(result["status"]=="COMPLETE","collected result incomplete")
    episode=result["episode"];prior=cond["source_turn_index"]
    require(episode["turns"][:prior]==cond["prefix_turns"] and episode["tool_events"][:len(cond["prefix_events"])]==cond["prefix_events"]
        and episode["call_settlements"][:prior]==cond["prefix_settlements"],"source L prefix was rewritten")
    require(0<=result["new_model_calls"]<=cond["maximum_new_model_calls"]
        and len(episode["turns"])==prior+result["new_model_calls"]<=32
        and episode["actual_model_calls"]==prior+result["new_model_calls"],"native32 total path budget changed")
    require(episode["provider"]==cond["actor_identity"] and result["episode_sha256"]==digest(episode),"episode actor or content changed")
    for turn in episode["turns"][prior:]:_verify_turn(turn,cond["actor_identity"])
    if modules is not None:
        require(modules.settlement.episode_is_complete(modules.contracts.Episode.model_validate(episode)),"native collection is unsettled")
    return True


def run_condition(cond,*,output_dir,protocol_id,inputs_id,attempt,predictor_factory,guard,modules=None):
    b=binding();root=Path(output_dir)
    bound=dict(protocol_id=protocol_id,inputs_id=inputs_id,condition_id=cond["condition_id"],condition_sha256=digest(cond))
    if (root/"result.json").exists():
        result=b.checked(root/"result.json");require(all(result[k]==v for k,v in bound.items()),"saved collection binding changed")
        validate_outcome(cond,result);return result
    state=audit_condition(root)
    if not state["resume_allowed"]:raise UnknownCollection("unsettled collection operations: "+repr(state["unknown_intents"]))
    b.publish(root/"condition.json",cond)
    common=dict(**bound,phase=cond["phase"],task_id=cond["task_id"],task_key=cond["task_key"],original_task_key=cond["original_task_key"],
        source_group=cond["source_group"],source_turn_index=cond["source_turn_index"],teacher_turn_start=cond["teacher_turn_start"],
        maximum_new_model_calls=cond["maximum_new_model_calls"],source_L_outcome=cond["source_L_outcome"],source_L_stop_reason=cond["source_L_stop_reason"])
    if not cond["applicable"]:
        return b.publish(root/"result.json",dict(common,status="NOT_APPLICABLE",reason=cond["reason"],episode=None,episode_sha256=None,
            new_model_calls=0,new_tool_calls=0,reconstruction_tool_calls=0,supervised_teacher_turns=0,
            native_scoring_calls=0,optimizer_updates=0,external_API_calls=0,completed_epoch=time.time()))
    m=modules or native_modules();c=m.contracts
    config=c.RunConfig.model_validate(cond["config"]);validate_config(config)
    public=c.PublicTask.model_validate(cond["public_task"])
    require(digest(public.model_dump(mode="json"))==cond["public_task_sha256"],"profiled public input changed")
    prior=cond["source_turn_index"]
    require(len(cond["prefix_turns"])==len(cond["prefix_events"])==len(cond["prefix_settlements"])==prior,
        "source prefix counts differ")
    scope=dict(run_id=protocol_id,episode_id=cond["condition_id"],attempt_index=0)
    session=m.task.PublicProgramSession(public,invocation_context=scope)
    messages=copy.deepcopy(cond["source_request"]["messages"][:2]);tools=m.harness.episode_tool_specs(config)
    require(messages[0]==m.harness.system_message(config) and messages[1]["role"]=="user"
        and json.loads(messages[1]["content"])==public.model_dump(mode="json")
        and tools==cond["source_request"]["tools"],"original public input/tool values changed")
    turns,events,settlements=[],[],copy.deepcopy(cond["prefix_settlements"])
    started=time.time();restoration=root/"reconstruction"/f"attempt{attempt:04d}";restore_index=0
    def restore(call,saved,origin,step):
        nonlocal restore_index
        _check(guard,"before_v75_tool_state_restoration")
        directory=restoration/f"event{restore_index:04d}";require(not directory.exists(),"same attempt cannot replay a restoration twice")
        intent=b.publish(directory/"intent.json",dict(**bound,origin=origin,step=step,tool_call=call.model_dump(mode="json"),
            saved_event_sha256=digest(saved),created_epoch=time.time()))
        event=session.execute(call,invocation_id=saved["invocation_id"]);actual=event.model_dump(mode="json")
        b.publish(directory/"returned.json",dict(**bound,intent_id=intent["id"],origin=origin,step=step,
            event=actual,exact_event_match=actual==saved,returned_epoch=time.time()))
        restore_index+=1;require(actual==saved,"isolated native session cannot reproduce source tool event")
        _check(guard,"after_durable_v75_state_restoration");return event
    for step,(raw,event) in enumerate(zip(cond["prefix_turns"],cond["prefix_events"],strict=True)):
        turn=c.ModelTurn.model_validate(raw);require(len(turn.tool_calls)==1,"source prefix contains multiple/no actions")
        restored=restore(turn.tool_calls[0],event,"L_source_prefix",step)
        turns.append(copy.deepcopy(raw));events.append(copy.deepcopy(event))
        messages.append(m.providers.canonical_assistant_message(turn));messages.append(dict(role="tool",tool_call_id=restored.call_id,content=restored.visible_output))
    require(messages==cond["source_request"]["messages"],"reconstructed messages differ from real terminal-boundary L history")
    b.publish(restoration/"verified.json",dict(**bound,source_prefix_turns=prior,source_prefix_tools=len(events),
        exact_messages_match=True,restored_session_attempts=session._tool_attempts,restored_handles=sorted(session.events_by_handle)))
    new_calls,new_tools=0,0;final_program,error,stop_reason=None,None,"max_steps";predictor=None
    for step in range(prior,32):
        if predictor is None:predictor=predictor_factory()
        require(predictor.model_label==cond["actor_model"],"collection loaded wrong actor")
        context=_new_request(messages,tools,config,predictor)
        if step==prior and "source_prompt_input_ids" in cond:
            require(context["prompt_input_ids"]==cond["source_prompt_input_ids"] and context["request"]==cond["source_request"],
                "P terminal-boundary input differs from last actual L call")
        if not context["prompt_input_ids"] or len(context["prompt_input_ids"])+2048>24576:
            stop_reason,error="context_exceeded","ContextLimitError: complete history exceeds original output reservation"
            settlement=dict(attempt_index=step,state="pre_call_rejected",actual_model_calls=0,request_sha256=digest(context["request"]),
                evidence=dict(exception_type="ContextLimitError",actual_prompt_tokens=len(context["prompt_input_ids"]),history_truncated=False))
            settlements.append(settlement);b.publish(root/"context_rejected.json",dict(**bound,step=step,settlement=settlement));break
        step_dir=root/"model"/f"step{step:04d}";saved=list(step_dir.glob("attempt*/returned.json"))
        require(len(saved)<=1,"duplicate new model response")
        if saved:
            returned=b.checked(saved[0]);require(all(returned[k]==v for k,v in bound.items()) and returned["context_sha256"]==digest(context),"saved model return belongs to another full history")
        else:
            _check(guard,"before_v75_new_model_intent")
            directory=step_dir/f"attempt{attempt:04d}";before_calls=predictor.provider.actual_model_calls;before=predictor.counters
            intent=b.publish(directory/"intent.json",dict(**bound,step=step,context=context,context_sha256=digest(context),created_epoch=time.time()))
            try:value=predictor.generate(context)
            except BaseException as exception:
                calls=predictor.provider.actual_model_calls-before_calls
                delta={k:v-before.get(k,0) for k,v in predictor.counters.items()};forwards=sum(v for k,v in delta.items() if k.endswith("_forward_calls"))
                if calls==forwards==0:b.publish(directory/"not_executed.json",dict(**bound,intent_id=intent["id"],actual_model_calls=0,
                    confirmed_forward_calls=0,exception=type(exception).__name__,message=str(exception),no_retry_authorization_implied=True))
                raise
            require(value["actual_model_generate_calls"]==1,"new native response counter must be one")
            returned=b.publish(directory/"returned.json",dict(**bound,step=step,intent_id=intent["id"],context_sha256=digest(context),value=value,returned_epoch=time.time()))
            _check(guard,"after_durable_v75_model_return")
        raw=copy.deepcopy(returned["value"]["turn"]);_verify_turn(raw,cond["actor_identity"],context)
        turn=c.ModelTurn.model_validate(raw);turns.append(raw);new_calls+=1
        settlements.append(dict(attempt_index=step,state="returned",actual_model_calls=1,request_sha256=digest(context["request"]),
            evidence=dict(kind="V75_actual_training_collection_return",returned_id=returned["id"],response_sha256=digest(raw))))
        messages.append(m.providers.canonical_assistant_message(turn))
        if not turn.tool_calls:stop_reason,error="no_tool_call","plain assistant text is not a final_answer submission";break
        if len(turn.tool_calls)!=1:stop_reason,error="multiple_tool_calls","exactly one tool call per model turn is permitted; none executed";break
        call=turn.tool_calls[0];tool_dir=root/"tool"/f"step{step:04d}"
        if (tool_dir/"returned.json").exists():
            saved=b.checked(tool_dir/"returned.json");require(all(saved[k]==v for k,v in bound.items()) and saved["step"]==step,"saved tool belongs to another condition")
            event=restore(call,saved["event"],"durable_new_tool",step)
        else:
            _check(guard,"before_v75_tool_intent")
            invocation=c.invocation_identity(scope,turn_index=step,tool_index=0)
            intent=b.publish(tool_dir/"intent.json",dict(**bound,step=step,tool_call=call.model_dump(mode="json"),invocation=invocation,
                response_sha256=digest(raw),created_epoch=time.time()))
            event=session.execute(call,invocation_id=invocation["invocation_id"])
            b.publish(tool_dir/"returned.json",dict(**bound,step=step,intent_id=intent["id"],event=event.model_dump(mode="json"),returned_epoch=time.time()))
            _check(guard,"after_durable_v75_tool_return")
        events.append(event.model_dump(mode="json"));new_tools+=1
        messages.append(dict(role="tool",tool_call_id=call.call_id,content=event.visible_output))
        if call.name=="submit_program" and not event.is_error:final_program,stop_reason=event.raw_output["program"],"final_answer";break
    episode=c.Episode(task_id=public.task_id,dataset=public.dataset,public_task_sha256=cond["public_task_sha256"],config=config,
        provider=c.ModelIdentity.model_validate(cond["actor_identity"]),turns=tuple(c.ModelTurn.model_validate(v) for v in turns),
        tool_events=tuple(c.ToolEvent.model_validate(v) for v in events),messages=tuple(messages),final_program=final_program,
        stop_reason=stop_reason,error=error,actual_model_calls=prior+new_calls,provider_attempts=len(settlements),
        call_settlements=tuple(c.CallSettlement.model_validate(v) for v in settlements),all_provider_calls_settled=True,
        elapsed_seconds=time.time()-started).model_dump(mode="json")
    restorations=[b.checked(path) for path in sorted(root.glob("reconstruction/attempt*/event*/returned.json"))]
    result=dict(common,status="COMPLETE",episode=episode,episode_sha256=digest(episode),new_model_calls=new_calls,new_tool_calls=new_tools,
        reconstruction_tool_calls=len(restorations),source_prefix_reconstruction_tool_calls=sum(r["origin"]=="L_source_prefix" for r in restorations),
        durable_new_tool_reconstruction_calls=sum(r["origin"]=="durable_new_tool" for r in restorations),
        supervised_teacher_turns=new_calls if cond["actor_model"]=="P" else 0,
        budget_exhausted=stop_reason=="max_steps",context_exhausted=stop_reason=="context_exceeded",
        provenance=dict(source_model="L" if prior else None,successor_model=cond["actor_model"],source_turn_range=[0,prior],
            new_successor_turn_range=[prior,len(turns)],episode_provider_semantics="successor_only_not_homogeneous_trajectory" if prior else "homogeneous_initial_trajectory",
            student_prefix_is_input_only=True,source_L_last_response_included=False,original_prefix_receipts_rewritten=False),
        native_scoring_calls=0,optimizer_updates=0,external_API_calls=0,completed_epoch=time.time())
    validate_outcome(cond,result,modules=m);return b.publish(root/"result.json",result)


def run_collection(job,bundle,*,output_root,protocol_id,attempt,predictor_factory,guard,source_L_outcomes=None):
    """Return a job body; the outer worker adds resource and real-process evidence."""
    b=binding();root=Path(output_root);rows={r["task_id"]:r for r in bundle["tasks"]}
    require(len(job["task_ids"])==len(set(job["task_ids"])) and set(job["task_ids"])<=set(rows),"collection job roster differs")
    if job["phase"]=="P.post":require(source_L_outcomes is not None and set(rows)<=set(source_L_outcomes),"P.post needs complete accepted L roster")
    outcomes={};counts=dict(new_model_calls=0,new_tool_calls=0,reconstruction_tool_calls=0,logical_sessions=0,not_applicable=0)
    m=native_modules()
    for key in job["task_ids"]:
        _check(guard,"before_v75_collection_task")
        source=(source_L_outcomes[key] if source_L_outcomes else None)
        source_ref=copy.deepcopy(source) if source and "path" in source else None
        if source_ref:source=b.read_ref(source_ref)
        if source is not None:
            require(source["protocol_id"]==protocol_id and source["inputs_id"]==bundle["id"],
                "L source result belongs to another protocol/input roster")
        cond=condition(job,bundle,rows[key],source,modules=m)
        if source_ref is not None:
            cond["source_L_outcome_ref"]=source_ref
        path=root/"outputs"/digest(key)
        result=run_condition(cond,output_dir=path,protocol_id=protocol_id,inputs_id=bundle["id"],attempt=attempt,
            predictor_factory=predictor_factory,guard=guard,modules=m)
        outcomes[key]=b.entry(path/"result.json")
        for field in ("new_model_calls","new_tool_calls","reconstruction_tool_calls"):counts[field]+=result[field]
        counts["logical_sessions"]+=result["status"]=="COMPLETE";counts["not_applicable"]+=result["status"]=="NOT_APPLICABLE"
        require(counts["new_model_calls"]<=job["maximum_model_calls"],"fixed collection call cap exceeded")
        b.write_status(root/"progress/status.json",dict(job_id=job["job_id"],protocol_id=protocol_id,completed_slots=len(outcomes),
            **counts,updated_epoch=time.time()))
    return dict(schema="v75_collection_job_result.v1",status="COMPLETE",phase=job["phase"],outcomes=outcomes,
        completed_slots=len(outcomes),**counts,first_response_reuse_from_development=0,native_scores=0,
        optimizer_updates=0,new_probability_sequences=0,external_API_calls=0)
