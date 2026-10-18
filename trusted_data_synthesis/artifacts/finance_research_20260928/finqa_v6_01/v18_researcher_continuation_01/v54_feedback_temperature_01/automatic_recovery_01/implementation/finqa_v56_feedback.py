"""Durable local-generation continuation without repeating a returned token turn.

The original harness is reentered with its exact saved prefix. Prefix provider
returns and pure public tools reconstruct the original messages; no Student is
called for that prefix. A new call first has a durable intent and every returned
ModelTurn is atomically saved before control returns to the harness. Unreturned
intents without conclusive zero-call settlement are never automatically retried.
"""

from __future__ import annotations

import asyncio
import copy
import fcntl
import hashlib
import json
import os
import time
from pathlib import Path

SEEDS = (137, 251, 389)
EXPECTED_COMPLETE = {137: 24, 251: 23, 389: 23}
EXPECTED_PARTIAL_TURNS = {137: 2, 251: 1, 389: 0}


class GenerationBindingError(RuntimeError):
    automatic_recovery_allowed = False


class GenerationUnknown(RuntimeError):
    automatic_recovery_allowed = False


class GenerationPreCallPause(RuntimeError):
    automatic_recovery_allowed = True

    def __init__(self,message,*,evidence=None):
        super().__init__(message)
        self.resume_evidence=evidence or {}
        self.underlying_exception_type=self.resume_evidence.get("exception_type")
        self.errno=self.resume_evidence.get("errno")
        self.actual_model_calls=0


def require(ok, message):
    if not ok:
        raise GenerationBindingError(message)


def digest(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return json.loads(raw), dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def read_ref(reference):
    value, actual = read(reference["path"])
    require(actual == reference, "bound generation source bytes changed")
    return value


def checked_record(path):
    value,reference=read(path)
    require(value.get("id")==digest({k:v for k,v in value.items() if k!="id"}),
            "immutable durable generation content identity changed")
    return value,reference


def bound(body):
    return {**body, "id": digest(body)}


def atomic(directory, body, *, idempotent=False):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    value = bound(body)
    path = Path(directory) / "record.json"
    if idempotent and path.exists():
        require(read(path)[0] == value, "immutable durable generation record changed")
        return value
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                      allow_nan=False) + "\n").encode()
    write_immutable_artifact_directory(path.parent, {"record.json": raw})
    return value


def ensure_file(path, raw):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    path = Path(path)
    if path.exists():
        require(path.read_bytes() == raw, "immutable inherited/canonical file differs")
    else:
        write_immutable_artifact_directory(path.parent, {path.name: raw})


def copy_ref(reference, destination):
    raw = Path(reference["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"],
            "inherited generation bytes changed before copy")
    ensure_file(destination, raw)


def scientific_request(payload):
    return {key: copy.deepcopy(payload[key]) for key in ("messages", "tools", "config")}


def _tool_science(event):
    # Invocation IDs audit pure executions. All arguments/results/visible bytes
    # remain scientific inputs to the next model call and must stay identical.
    return {key: value for key, value in event.items() if key != "invocation_id"}


def _event_files(directory):
    paths = sorted(Path(directory).glob("*/event.json"))
    require([p.parent.name for p in paths] == [f"{i:06d}" for i in range(len(paths))],
            "durable episode events have a gap")
    return [read(path) for path in paths]


def inspect_inherited_run(run_root, *, expected_complete=None, expected_partial_turns=None):
    from trusted_synthesis.finance_research.contracts import Episode
    from trusted_synthesis.finance_research.settlement import episode_is_complete

    root = Path(run_root).resolve()
    run, run_ref = read(root / "run.json")
    require(run["id"] == digest({k: v for k, v in run.items() if k != "id"}),
            "old scientific run changed")
    complete, partial = [], None
    present = {p.parent.name: p for p in (root / "episodes").glob("*/episode.json")}
    require(set(present) <= set(run["episode_keys"]), "unregistered old episode")
    for index, key in enumerate(run["episode_keys"]):
        if key not in present:
            break
        raw, ep_ref = read(present[key])
        episode = Episode.model_validate(raw)
        events = _event_files(root / "events" / key)
        require(events and events[-1][0]["kind"] == "episode_completed"
                and events[-1][0]["payload"] == raw
                and raw["provider"] == run["provider"] and raw["config"] == run["config"],
                "old episode/termination/scientific run binding changed")
        if episode_is_complete(episode):
            require(partial is None, "complete history cannot follow a partial old episode")
            complete.append(dict(index=index, episode_key=key, episode=ep_ref,
                                 events=[ref for _event, ref in events],
                                 returned_turn_count=len(episode.turns)))
        else:
            require(partial is None and raw["stop_reason"] == "provider_error"
                    and len(raw["call_settlements"]) == len(raw["turns"]) + 1,
                    "only one incomplete next episode is admitted")
            last = raw["call_settlements"][-1]
            if last["state"] != "pre_call_rejected" or last["actual_model_calls"] != 0:
                raise GenerationUnknown("old partial episode has an unreturned nonzero/unknown call")
            require(all(x["state"] == "returned" and x["actual_model_calls"] == 1
                        for x in raw["call_settlements"][:-1])
                    and raw["actual_model_calls"] == len(raw["turns"]),
                    "old returned prefix is not completely accounted")
            intents = [e for e, _ref in events if e["kind"] == "model_call_intent"]
            returns = [(e,ref) for e,ref in events if e["kind"] == "model_call_returned"]
            require([e["payload"] for e,_ref in returns] == raw["turns"]
                    and len(intents) == len(returns)+1
                    and intents[-1]["step"] == len(returns), "old returned-turn prefix changed")
            partial = dict(index=index,episode_key=key,episode=ep_ref,
                           events=[ref for _event,ref in events],
                           returned_events=[ref for _event,ref in returns],
                           returned_turn_count=len(returns),
                           last_pre_call_request=scientific_request(intents[-1]["payload"]),
                           last_pre_call_request_sha256=digest(scientific_request(intents[-1]["payload"])),
                           last_settlement=last, tool_events=raw["tool_events"])
    expected_keys = run["episode_keys"][:len(complete)+(partial is not None)]
    require(set(present) == set(expected_keys), "old episode set is not a contiguous actual prefix")
    require({p.name for p in (root/"events").iterdir() if p.is_dir()} == set(expected_keys),
            "old event-only unknown request is not authorized for automatic recovery")
    if expected_complete is not None:
        require(len(complete) == expected_complete, "authorized inherited complete count changed")
    if expected_partial_turns is not None:
        require(partial is not None and partial["returned_turn_count"] == expected_partial_turns,
                "authorized inherited returned-turn count changed")
    return bound(dict(schema="v56_original_run_durable_prefix.v1",source_run_root=str(root),
                      run=run_ref, complete=complete, partial=partial,
                      complete_episode_count=len(complete),
                      partial_returned_turn_count=partial["returned_turn_count"] if partial else 0))


def build_inheritance(old_v55_root):
    from finqa_v54_temperature import checked_condition

    old = Path(old_v55_root).resolve()
    closeout, closeout_ref = read(old/"closeout/record.json")
    require(closeout["active_workers"] == 0 and closeout["status"] == "STOPPED_FAILURE_NO_RETRY",
            "V55 must remain stopped with actual durable evidence")
    rows = {}
    for seed in SEEDS:
        stage = old/f"stages/seed{seed}/feedback_C05"
        conditions=list((stage/"feedback").glob("*/intent/record.json"))
        require(len(conditions)==1, "one actual old scientific condition required")
        condition, condition_ref=read(conditions[0])
        checked_condition(condition)
        feedback_root=conditions[0].parent.parent
        draw=inspect_inherited_run(feedback_root/"draw0",expected_complete=EXPECTED_COMPLETE[seed],
                                   expected_partial_turns=EXPECTED_PARTIAL_TURNS[seed])
        require(not (feedback_root/"draw1").exists() and not (feedback_root/"cohort_seal").exists()
                and not (feedback_root/"native_rewards").exists(),
                "authorized original feedback boundary changed")
        parent,parent_ref=read(old/f"parents/seed{seed}/record.json")
        require(parent["point_id"]==condition["identity"]["point_id"],"old parent point differs")
        _failure,failure_ref=read(stage/"attempts/attempt0001/failure/record.json")
        exit_record,exit_ref=read(stage/"actual_exit/record.json")
        require(exit_record["actual_waitpid_observed"] and exit_record["returncode"]!=0,
                "old feedback process has not actually exited")
        claim_ref=resolution_ref=None
        if seed in (137,389):
            claim,claim_ref=read(old/f"feedback_recovery/seed{seed}/claim/record.json")
            resolution,resolution_ref=read(old/f"feedback_recovery/seed{seed}/resolution/record.json")
            require(resolution["claim_id"]==claim["id"]
                    and resolution["condition_id"]==condition["id"]
                    and resolution["new_actual_model_calls"]==1
                    and resolution["old_unknown_record_preserved"] is True,
                    "the old single-reexecution allowance must already be resolved and consumed")
        rows[str(seed)]=bound(dict(schema="v56_seed_feedback_inheritance.v1",seed=seed,
            old_stage_root=str(stage),old_feedback_root=str(feedback_root),old_parent=parent_ref,
            old_condition=condition_ref,condition=condition,expected_condition_id=condition["id"],
            old_worker_failure=failure_ref,old_actual_exit=exit_ref,
            consumed_claim=claim_ref,consumed_resolution=resolution_ref,
            old_reexecution_allowance_remaining=0,draws={"0":draw},
            inherited_complete_episodes=EXPECTED_COMPLETE[seed],
            inherited_partial_returned_turns=EXPECTED_PARTIAL_TURNS[seed],
            unknown_reexecution_authorized=False))
    return checked_inheritance(bound(dict(schema="v56_seventy_episodes_three_turns_inheritance.v1",
        old_root=str(old),old_closeout=closeout_ref,seeds=rows,inherited_complete_episodes=70,
        inherited_partial_returned_turns=3,new_model_calls_for_inherited_returns=0,
        old_single_reexecution_allowances_remaining=0,unknown_automatic_retry=False,
        logical_feedback_denominator_per_seed=700,old_files_written=False)))


def checked_inheritance(value):
    require(value["id"]==digest({k:v for k,v in value.items() if k!="id"})
            and value["schema"]=="v56_seventy_episodes_three_turns_inheritance.v1"
            and set(value["seeds"])=={str(s) for s in SEEDS}
            and value["inherited_complete_episodes"]==70
            and value["inherited_partial_returned_turns"]==3
            and value["old_single_reexecution_allowances_remaining"]==0
            and value["unknown_automatic_retry"] is False,"feedback inheritance contract changed")
    for seed in SEEDS:
        row=value["seeds"][str(seed)]
        require(row["id"]==digest({k:v for k,v in row.items() if k!="id"})
                and row["seed"]==seed and row["expected_condition_id"]==row["condition"]["id"]
                and row["inherited_complete_episodes"]==EXPECTED_COMPLETE[seed]
                and row["inherited_partial_returned_turns"]==EXPECTED_PARTIAL_TURNS[seed]
                and row["old_reexecution_allowance_remaining"]==0
                and row["unknown_reexecution_authorized"] is False,"seed feedback inheritance changed")
    return value


def _copy_inheritance(run_root, inheritance):
    if inheritance is None:
        return
    root=Path(run_root)
    require(inheritance["id"]==digest({k:v for k,v in inheritance.items() if k!="id"}),
            "run inheritance digest changed")
    run=read_ref(inheritance["run"])
    require(read(root/"run.json")[0]==run,"new run must preserve original complete scientific registration")
    for row in inheritance["complete"]:
        key=row["episode_key"]
        for index,reference in enumerate(row["events"]):
            copy_ref(reference,root/f"events/{key}/{index:06d}/event.json")
        copy_ref(row["episode"],root/f"episodes/{key}/episode.json")
    partial=inheritance["partial"]
    if partial is not None:
        key=partial["episode_key"]
        old_episode=read_ref(partial["episode"])
        for index,reference in enumerate(partial["returned_events"]):
            event=read_ref(reference)
            turn=event["payload"]
            require(turn==old_episode["turns"][index],"inherited actual return differs")
            atomic(root/f"durable_returns/{key}/turn{index:04d}",dict(
                schema="v56_actual_returned_turn.v1",turn_index=index,turn=turn,
                scientific_request=scientific_request(turn["provider_metadata"]["request"]),
                scientific_request_sha256=digest(scientific_request(turn["provider_metadata"]["request"])),
                origin="inherited_actual_return",original_return_event=reference,
                call_intent=None,new_model_calls=0),idempotent=True)
        atomic(root/f"inherited_partial/{key}",dict(
            schema="v56_inherited_zero_call_boundary.v1",inheritance_id=inheritance["id"],
            original_episode=partial["episode"],original_events=partial["events"],
            returned_turn_count=partial["returned_turn_count"],
            next_request=partial["last_pre_call_request"],
            next_request_sha256=partial["last_pre_call_request_sha256"],
            last_settlement=partial["last_settlement"],tool_events=partial["tool_events"]),idempotent=True)
        for index,event in enumerate(partial["tool_events"]):
            atomic(root/f"durable_tools/{key}/tool{index:04d}",dict(
                schema="v56_pure_tool_result.v1",tool_index=index,event=event,
                scientific_event=_tool_science(event),origin="inherited_actual_tool_result"),idempotent=True)
    atomic(root/"inheritance",dict(schema="v56_original_run_inherited.v1",
           source=inheritance,old_files_written=False),idempotent=True)


def _turn_records(root,key,identity,config):
    from trusted_synthesis.finance_research.contracts import ModelTurn

    paths=sorted((Path(root)/"durable_returns"/key).glob("turn*/record.json"))
    require([p.parent.name for p in paths]==[f"turn{i:04d}" for i in range(len(paths))],
            "actual returned token prefix has a gap")
    rows=[]
    for index,path in enumerate(paths):
        row,reference=read(path)
        require(row["id"]==digest({k:v for k,v in row.items() if k!="id"})
                and row["turn_index"]==index,"actual returned-turn binding changed")
        turn=ModelTurn.model_validate(row["turn"])
        receipt=turn.receipt
        require(receipt is not None and receipt.identity==identity
                and row["scientific_request"]["config"]==config.model_dump(mode="json")
                and digest(row["scientific_request"])==row["scientific_request_sha256"]
                and scientific_request(turn.provider_metadata["request"])==row["scientific_request"]
                and digest(turn.provider_metadata["request"])==receipt.request_sha256
                and hashlib.sha256(turn.raw_text.encode()).hexdigest()==receipt.raw_response_sha256,
                "returned prefix request/point/receipt changed")
        rows.append((row,reference,turn))
    return rows


def _inspect_calls(root,key,returned):
    expected={}
    for path in sorted((Path(root)/"call_attempts"/key).glob("turn*/*/intent/record.json")):
        intent,reference=checked_record(path)
        index=intent["turn_index"]
        request=intent["scientific_request"]
        require(digest(request)==intent["scientific_request_sha256"],"durable call request changed")
        if index in expected:
            require(expected[index]==request,"attempts changed the same scientific request")
        expected[index]=request
        settlement_path=path.parent.parent/"settlement/record.json"
        if settlement_path.exists():
            settlement=checked_record(settlement_path)[0]
            state=settlement["settlement"]
            if state=="pre_call_rejected" and settlement["actual_model_calls"]==0:
                continue
            if state=="returned" and index<len(returned):
                require(returned[index][0]["call_intent"]==reference,
                        "actual return belongs to another physical invocation")
                continue
            raise GenerationUnknown("a prior generation call has no complete returned receipt")
        if index<len(returned) and returned[index][0]["call_intent"]==reference:
            continue
        raise GenerationUnknown("unsettled call intent without durable returned tokens; automatic retry forbidden")
    inherited=Path(root)/f"inherited_partial/{key}/record.json"
    if inherited.exists():
        row=checked_record(inherited)[0]
        index=row["returned_turn_count"]
        require(row["last_settlement"]["state"]=="pre_call_rejected"
                and row["last_settlement"]["actual_model_calls"]==0,
                "old boundary is not a proven zero-call rejection")
        if index in expected:
            require(expected[index]==row["next_request"],"old/new continuation request differs")
        expected[index]=row["next_request"]
    return expected


class _PrefixProvider:
    def __init__(self,provider,run_root,key,attempt_id,returned,expected,stop_check):
        self.provider,self.identity=provider,provider.identity
        self.root,self.key,self.attempt_id=Path(run_root),key,attempt_id
        self.returned,self.expected,self.stop_check=returned,expected,stop_check
        self.cursor=self.actual_model_calls=self.inherited_calls=self.new_calls=0

    async def chat(self,messages,tools,config):
        from trusted_synthesis.finance_research.settlement import failed_call

        index=self.cursor
        request=dict(messages=copy.deepcopy(messages),tools=copy.deepcopy(tools),
                     config=config.model_dump(mode="json"))
        if index in self.expected:
            require(request==self.expected[index],"reconstructed next scientific request differs")
        if index<len(self.returned):
            row,reference,turn=self.returned[index]
            require(request==row["scientific_request"],"reconstructed prefix scientific request differs")
            self.cursor+=1
            self.actual_model_calls+=1
            self.inherited_calls+=1
            return turn
        directory=self.root/f"call_attempts/{self.key}/turn{index:04d}/{self.attempt_id}"
        atomic(directory/"intent",dict(schema="v56_physical_call_intent.v1",episode_key=self.key,
            turn_index=index,attempt_id=self.attempt_id,identity=self.identity.model_dump(mode="json"),
            scientific_request=request,scientific_request_sha256=digest(request)))
        intent_ref=read(directory/"intent/record.json")[1]
        before=getattr(self.provider,"actual_model_calls",None)
        try:
            if self.stop_check is not None:
                self.stop_check()
            turn=await self.provider.chat(messages,tools,config)
        except BaseException as error:
            after=getattr(self.provider,"actual_model_calls",None)
            settlement=failed_call(error,before=before,after=after,
                request_sha256=digest(request),attempt_index=index)
            diagnostic=dict(settlement.evidence,errno=getattr(error,"errno",None))
            for field in ("resource_observation","resume_evidence","failure_class","retry_reason"):
                value=getattr(error,field,None)
                if value is not None:
                    try:
                        json.dumps(value,allow_nan=False)
                    except (TypeError,ValueError):
                        continue
                    diagnostic[field]=value
            settlement=settlement.model_copy(update={"evidence":diagnostic})
            delta=settlement.actual_model_calls
            if isinstance(delta,int):
                self.actual_model_calls+=delta
                self.new_calls+=delta
            atomic(directory/"settlement",dict(schema="v56_physical_call_settlement.v1",
                settlement=settlement.state,actual_model_calls=delta,
                evidence=settlement.model_dump(mode="json"),call_intent=intent_ref))
            raise
        after=getattr(self.provider,"actual_model_calls",None)
        if type(before) is int and type(after) is int and after>=before:
            self.actual_model_calls+=after-before
            self.new_calls+=after-before
        require(type(before) is int and type(after) is int and after-before==1,
                "local generation must truthfully count its single actual call")
        require(turn.receipt is not None and turn.receipt.identity==self.identity
                and scientific_request(turn.provider_metadata["request"])==request
                and digest(turn.provider_metadata["request"])==turn.receipt.request_sha256,
                "actual return does not bind its scientific request and point")
        # This is before the original harness handles tools or starts another call.
        atomic(self.root/f"durable_returns/{self.key}/turn{index:04d}",dict(
            schema="v56_actual_returned_turn.v1",turn_index=index,turn=turn.model_dump(mode="json"),
            scientific_request=request,scientific_request_sha256=digest(request),
            origin="new_actual_provider_return",original_return_event=None,
            call_intent=intent_ref,new_model_calls=1))
        atomic(directory/"settlement",dict(schema="v56_physical_call_settlement.v1",
            settlement="returned",actual_model_calls=1,call_intent=intent_ref,
            durable_return=read(self.root/f"durable_returns/{self.key}/turn{index:04d}/record.json")[1]))
        self.cursor+=1
        return turn


class _AttemptSink:
    def __init__(self,root,key,*,run_root,prefix_count,after_return):
        self.root=Path(root)/"events"/key
        self.run_root,self.key=Path(run_root),key
        self.index=0
        self.prefix_count=prefix_count
        self.after_return=after_return
        self.tool_index=0

    def __call__(self,event):
        if event["kind"]=="tool_call_returned":
            directory=self.run_root/f"durable_tools/{self.key}/tool{self.tool_index:04d}"
            if (directory/"record.json").exists():
                require(_tool_science(event["payload"])==checked_record(directory/"record.json")[0]["scientific_event"],
                        "pure tool reconstruction differs from its saved actual result")
            else:
                atomic(directory,dict(schema="v56_pure_tool_result.v1",tool_index=self.tool_index,
                    event=event["payload"],scientific_event=_tool_science(event["payload"]),
                    origin="actual_or_reconstructed_pure_tool_execution"))
            self.tool_index+=1
        value=copy.deepcopy(event)
        value["v56_origin"]=("reconstructed_prefix" if type(event["step"]) is int
                             and event["step"]<self.prefix_count else "current_attempt")
        raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
        ensure_file(self.root/f"{self.index:06d}/event.json",raw)
        self.index+=1
        if (self.after_return is not None and event["kind"]=="model_call_returned"
                and event["step"]>=self.prefix_count):
            self.after_return(dict(phase="after_durable_response",episode_key=self.key,
                turn_index=event["step"],
                actual_return=read(self.run_root/f"durable_returns/{self.key}/turn{event['step']:04d}/record.json")[1],
                returned_event=read(self.root/f"{self.index-1:06d}/event.json")[1]))


def _commit_candidate(root,key):
    root=Path(root)
    candidate=checked_record(root/f"complete_candidates/{key}/record.json")[0]
    for index,reference in enumerate(candidate["events"]):
        copy_ref(reference,root/f"events/{key}/{index:06d}/event.json")
    raw=(json.dumps(candidate["episode"],sort_keys=True,ensure_ascii=False,indent=2,
                    allow_nan=False)+"\n").encode()
    ensure_file(root/f"episodes/{key}/episode.json",raw)
    return candidate["episode"]


async def execute_run_resumable(run_root,provider,*,attempt_root,inheritance=None,stop_check=None,
                                after_return=None):
    """Run the unchanged public harness from actual durable returns, never UNKNOWN."""
    from trusted_synthesis.finance_research import storage,harness
    from trusted_synthesis.finance_research.contracts import Episode,RunConfig
    from trusted_synthesis.finance_research.settlement import episode_is_complete

    root,attempt=Path(run_root).resolve(),Path(attempt_root).resolve()
    require(not attempt.is_relative_to(root/"episodes") and attempt!=root,
            "attempt audit must be separate from stable scientific episode data")
    with (root/"generation.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run=storage._run_manifest(root)
        config=RunConfig.model_validate(run["config"])
        require(config.harness_id=="bigfinance-derived-vtdo-v7"
                and config.local_tool_protocol=="qwen2.5-native-tool-call-v1",
                "only the original pure public V7 harness is registered for continuation")
        require(provider.identity.model_dump(mode="json")==run["provider"],
                "cold provider differs from the registered actual model point")
        _copy_inheritance(root,inheritance)
        attempt_id=digest(str(attempt))
        atomic(attempt/"started",dict(schema="v56_generation_attempt.v1",attempt_id=attempt_id,
            run_id=run["id"],run_root=str(root),pid=os.getpid(),started_epoch=time.time(),
            inheritance_id=inheritance["id"] if inheritance else None))
        if (root/"generation_seal/seal.json").exists():
            _run,seal,_episodes=storage.sealed_episodes(root)
            atomic(attempt/"result",dict(schema="v56_generation_attempt_result.v1",
                complete=True,already_sealed=True,new_actual_model_calls=0,seal_id=seal["id"]))
            return seal
        manifest,tasks,lineages=storage.load_public_snapshot(run["snapshot"])
        require(manifest["id"]==run["snapshot_id"],"original public snapshot changed")
        storage.verify_role_plan(run["role_plan"],tasks,lineages)
        by_key={storage.task_key(task):task for task in tasks}
        references=[]
        new_calls=inherited_calls=0
        for task_key,key in zip(run["tasks"],run["episode_keys"],strict=True):
            if stop_check is not None:
                stop_check()
            task=by_key[task_key]
            public=storage.runtime_task_view(task,config)
            require(run["public_view_sha256"][task_key]==digest(public),"public task view changed")
            path=root/f"episodes/{key}/episode.json"
            if not path.exists() and (root/f"complete_candidates/{key}/record.json").exists():
                _commit_candidate(root,key)
            if path.exists():
                episode=Episode.model_validate_json(path.read_bytes())
                require(episode_is_complete(episode),"stable episode path is not a complete episode")
            else:
                returned=_turn_records(root,key,provider.identity,config)
                expected=_inspect_calls(root,key,returned)
                proxy=_PrefixProvider(provider,root,key,attempt_id,returned,expected,stop_check)
                sink=_AttemptSink(attempt,key,run_root=root,prefix_count=len(returned),after_return=after_return)
                episode=await harness.run_episode(task,proxy,config,sink=sink,
                    invocation_context=dict(run_id=run["id"],episode_id=key,
                                            attempt_index=int(time.time_ns())))
                new_calls+=proxy.new_calls
                inherited_calls+=proxy.inherited_calls
                require(proxy.cursor>=len(returned),"old returned prefix ended before its saved boundary")
                if not episode_is_complete(episode):
                    atomic(attempt/f"incomplete/{key}",dict(schema="v56_generation_incomplete.v1",
                        episode=episode.model_dump(mode="json"),new_actual_model_calls=proxy.new_calls,
                        inherited_returned_calls=proxy.inherited_calls))
                    last=episode.call_settlements[-1] if episode.call_settlements else None
                    if last is not None and last.evidence.get("exception_type")=="GenerationBindingError":
                        raise GenerationBindingError(str(episode.error))
                    if last is not None and last.state=="pre_call_rejected" and last.actual_model_calls==0:
                        journal=root/f"call_attempts/{key}/turn{len(episode.turns):04d}/{attempt_id}/settlement/record.json"
                        detail=read(journal)[0]["evidence"]["evidence"] if journal.exists() else last.evidence
                        raise GenerationPreCallPause("known zero-call boundary retained: "+key+"; "+str(episode.error),
                                                     evidence=detail)
                    raise GenerationUnknown("generation call outcome is unknown or lacks returned tokens: "+key)
                events=_event_files(attempt/"events"/key)
                require(events[-1][0]["kind"]=="episode_completed"
                        and events[-1][0]["payload"]==episode.model_dump(mode="json"),
                        "completed episode lacks its exact durable completion event")
                atomic(root/f"complete_candidates/{key}",dict(schema="v56_complete_episode_candidate.v1",
                    episode=episode.model_dump(mode="json"),events=[ref for _event,ref in events],
                    new_actual_model_calls=proxy.new_calls,inherited_returned_calls=proxy.inherited_calls))
                _commit_candidate(root,key)
            require(episode.provider==provider.identity and episode.config==config
                    and episode.public_task_sha256==digest(public)
                    and (episode.dataset,episode.task_id)==(task.dataset,task.task_id),
                    "complete episode no longer belongs to its original scientific task")
            references.append(dict(key=key,path=f"episodes/{key}/episode.json",
                                   sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        seal=bound(dict(schema="finance_research_generation_seal.v2",run_id=run["id"],
            episodes=references,complete=True,registered_denominator=run["registered_denominator"],
            all_provider_calls_settled=True,private_references_read=False))
        ensure_file(root/"generation_seal/seal.json",
                    (json.dumps(seal,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        atomic(attempt/"result",dict(schema="v56_generation_attempt_result.v1",complete=True,
            already_sealed=False,new_actual_model_calls=new_calls,
            inherited_returned_turn_reconstructions=inherited_calls,seal_id=seal["id"],
            pure_tool_reexecution_is_not_new_model_generation=True))
        return seal


class V56FeedbackCollector:
    """Same temperature cohort/scorer, with durable generation before common seal."""
    def __init__(self,*,attempt_root,inheritance,**kwargs):
        from finqa_v54_temperature import LocalFeedbackCollector

        require(kwargs.pop("recovery_guard_factory",None) is None,
                "resolved V55 single-call allowances must never be reclaimed")
        self.base=LocalFeedbackCollector(**kwargs)
        self.attempt_root=Path(attempt_root)
        self.inheritance=copy.deepcopy(inheritance)
        require(inheritance["id"]==digest({k:v for k,v in inheritance.items() if k!="id"})
                and inheritance["old_reexecution_allowance_remaining"]==0,
                "registered actual feedback inheritance required")
        self.condition=self.feedback_root=None

    def collect(self,model,tokenizer,theta,*,point_id,event_sink=None):
        import finqa_v54_temperature as temperature
        from trusted_synthesis.finance_research import storage
        from trusted_synthesis.finance_research.planning import task_key

        emit=event_sink or (lambda event:None)
        base=self.base
        with temperature.installed_point(model,theta) as installed:
            identity=temperature.providers.local_model_identity(model,tokenizer,
                model_id=base.model_id,point_id=point_id,parameter_tensors=installed)
            configs=[base.config.model_copy(update={"seed":seed}) for seed in base.seeds]
            condition=temperature.build_condition(identity=identity,temperature=0.5,configs=configs,
                task_roster=base.tasks,source_manifest_sha256=digest(base.manifest),
                role_plan_id=base.role_plan["id"])
            require(condition==self.inheritance["condition"]
                    and read_ref(self.inheritance["old_condition"])==condition,
                    "new collector must preserve the exact old scientific temperature condition")
            for field in ("consumed_claim","consumed_resolution"):
                if self.inheritance[field] is not None:
                    read_ref(self.inheritance[field])
            root=base.root/condition["id"]
            self.condition,self.feedback_root=condition,root
            temperature._publish(root/"intent",condition)
            atomic(root/"inherited_authorization",dict(schema="v56_old_authorization_read_only.v1",
                inheritance_id=self.inheritance["id"],consumed_claim=self.inheritance["consumed_claim"],
                consumed_resolution=self.inheritance["consumed_resolution"],new_claims=0),idempotent=True)
            for index,cfg in enumerate(configs):
                directory=root/f"draw{index}"
                if not (directory/"run.json").exists():
                    storage.prepare_run(base.snapshot,base.role_plan,directory,role="feedback",
                        config=cfg,identity=identity,task_keys=[task_key(task) for task in base.tasks])
                provider=temperature.LocalTorchProvider(model,tokenizer,identity,
                    parameter_tensors=installed,condition=condition,before_call=emit)
                asyncio.run(execute_run_resumable(directory,provider,
                    attempt_root=self.attempt_root/f"draw{index}",
                    inheritance=self.inheritance["draws"].get(str(index)),
                    after_return=lambda value:emit(dict(value,phase="after_durable_feedback_return"))))
        # Both complete draws now exist; the original collector cannot generate.
        # Its common 700 seal precedes private scoring; a saved reward seal is
        # read in full instead of rescored on every subsequent cold attempt.
        cohort,rewards=base.collect(model,tokenizer,theta,point_id=point_id,event_sink=emit)
        self.condition,self.feedback_root=base.condition,base.feedback_root
        return cohort,rewards


def audit_resume(root_or_stage,inheritance=None):
    """CPU-only re-dispatch disposition; no returned turn is inferred from a flag."""
    from trusted_synthesis.finance_research.contracts import Episode,ModelIdentity,RunConfig
    from trusted_synthesis.finance_research.settlement import episode_is_complete

    path=Path(root_or_stage).resolve()
    if (path/"run.json").exists():
        runs=[path]
    elif (path/"intent/record.json").exists():
        runs=[p.parent for p in sorted(path.glob("draw*/run.json"))]
    else:
        runs=[p.parent for p in sorted(path.glob("feedback/*/draw*/run.json"))]
    evidence,progress=[],[]
    observed={}
    complete_count=returned_count=unknown_count=0
    problems=[]
    for root in runs:
        run,run_ref=read(root/"run.json")
        evidence.append(run_ref)
        try:
            require(run["id"]==digest({k:v for k,v in run.items() if k!="id"}),"run registration changed")
            identity,config=ModelIdentity.model_validate(run["provider"]),RunConfig.model_validate(run["config"])
            keys=set(run["episode_keys"])
            actual_keys={p.name for directory in ("episodes","durable_returns","call_attempts")
                         for p in (root/directory).glob("*") if p.is_dir()}
            require(actual_keys<=keys,"unregistered episode progress exists")
            for key in run["episode_keys"]:
                episode_path=root/f"episodes/{key}/episode.json"
                candidate=root/f"complete_candidates/{key}/record.json"
                returns=_turn_records(root,key,identity,config)
                _inspect_calls(root,key,returns)
                for _row,reference,_turn in returns:
                    evidence.append(reference)
                for journal in sorted((root/"call_attempts"/key).glob("turn*/*/*/record.json")):
                    evidence.append(read(journal)[1])
                if episode_path.exists():
                    episode=Episode.model_validate_json(episode_path.read_bytes())
                    require(episode_is_complete(episode) and episode.provider==identity
                            and episode.config==config,"complete episode scientific binding differs")
                    reference=read(episode_path)[1]
                    evidence.append(reference)
                    complete_count+=1
                    returned_count+=len(episode.turns)
                    observed[(run["id"],key)]=(True,len(episode.turns))
                    progress.append(dict(run_id=run["id"],key=key,episode=reference))
                elif candidate.exists():
                    value,reference=checked_record(candidate)
                    episode=Episode.model_validate(value["episode"])
                    require(episode_is_complete(episode),"candidate is not actually complete")
                    complete_count+=1
                    returned_count+=len(episode.turns)
                    observed[(run["id"],key)]=(True,len(episode.turns))
                    evidence.append(reference)
                    progress.append(dict(run_id=run["id"],key=key,candidate=reference))
                elif returns:
                    returned_count+=len(returns)
                    observed[(run["id"],key)]=(False,len(returns))
                    progress.append(dict(run_id=run["id"],key=key,returned=[ref for _r,ref,_t in returns]))
        except GenerationUnknown as error:
            unknown_count+=1
            problems.append(dict(kind="UNKNOWN",run_root=str(root),message=str(error)))
        except (GenerationBindingError,KeyError,ValueError) as error:
            problems.append(dict(kind="BINDING",run_root=str(root),message=str(error)))
    # A cold attempt can fail while copying inherited files. Its original
    # byte-bound source remains durable progress, including after run.json was
    # created. Count each scientific episode/turn once, never audit identities.
    # Read errors deliberately propagate: unavailable evidence is not zero work.
    if inheritance is not None:
        require(inheritance["id"]==digest({k:v for k,v in inheritance.items() if k!="id"}),
                "registered seed inheritance changed")
        for draw in inheritance["draws"].values():
            require(draw["id"]==digest({k:v for k,v in draw.items() if k!="id"}),
                    "registered inherited draw changed")
            original=read_ref(draw["run"])
            identity=ModelIdentity.model_validate(original["provider"])
            config=RunConfig.model_validate(original["config"])
            require(original["id"]==digest({k:v for k,v in original.items() if k!="id"}),
                    "original scientific run binding changed")
            evidence.append(draw["run"])
            for row in draw["complete"]:
                present,count=observed.get((original["id"],row["episode_key"]),(False,0))
                if present:
                    continue
                episode=Episode.model_validate(read_ref(row["episode"]))
                require(episode_is_complete(episode) and episode.provider==identity
                        and episode.config==config and len(episode.turns)==row["returned_turn_count"]
                        and count<=len(episode.turns),"inherited complete source binding changed")
                complete_count+=1
                returned_count+=len(episode.turns)-count
                evidence.append(row["episode"])
                progress.append(dict(run_id=original["id"],key=row["episode_key"],
                    inherited_episode=row["episode"],missing_returned_turns=len(episode.turns)-count))
            partial=draw["partial"]
            if partial is not None:
                _complete,count=observed.get((original["id"],partial["episode_key"]),(False,0))
                missing=partial["returned_turn_count"]-count
                if missing>0:
                    episode=Episode.model_validate(read_ref(partial["episode"]))
                    require(episode.provider==identity and episode.config==config
                            and len(episode.turns)==partial["returned_turn_count"],
                            "inherited partial source binding changed")
                    for index in range(count,len(episode.turns)):
                        reference=partial["returned_events"][index]
                        returned=read_ref(reference)
                        require(returned["kind"]=="model_call_returned"
                                and returned["payload"]==episode.turns[index].model_dump(mode="json"),
                                "inherited returned source differs")
                        evidence.append(reference)
                    evidence.append(partial["episode"])
                    returned_count+=missing
                    progress.append(dict(run_id=original["id"],key=partial["episode_key"],
                        inherited_partial=partial["episode"],missing_returned_turns=missing))
    complete_generation=(bool(runs) and all((root/"generation_seal/seal.json").exists() for root in runs)
                         and (len(runs)==1 if (path/"run.json").exists() else len(runs)==2))
    complete_stage=complete_generation
    if complete_generation and not (path/"run.json").exists():
        feedback_root=runs[0].parent
        complete_stage=all((feedback_root/name).is_file() for name in (
            "cohort_seal/record.json","condition_cohort_binding/record.json","native_rewards/record.json"))
    return dict(schema="v56_actual_generation_resume_audit.v1",resume_allowed=not problems,
                unknown_calls=unknown_count,problems=problems,complete_episodes=complete_count,
                actual_returned_turns=returned_count,progress_units=complete_count+returned_count,
                durable_progress_digest=digest(progress),evidence=evidence,
                complete_generation=complete_generation,complete_stage=complete_stage,
                new_sampling_calls=0,unknown_automatic_retry=False)
