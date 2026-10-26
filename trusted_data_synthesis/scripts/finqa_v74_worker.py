"""One lazy-P worker for 192 exact-first-response hybrid trajectories."""
from __future__ import annotations
import fcntl
import os
from pathlib import Path
import time
import finqa_v74_binding as b


def directory(job):
    b.require(job["job_id"] == "P.continuation" and job["model"] == "P", "foreign continuation job")
    return b.ROOT / "jobs" / job["job_id"]


def audit(job, protocol_id, source_binding_id=None):
    import finqa_v74_runtime as runtime
    stable = directory(job)
    states, unknown, terminals = [], [], 0
    for key in job["condition_ids"]:
        path = stable / "outputs" / key
        row = runtime.audit_condition(path)
        unknown.extend(row["unknown_intents"])
        if row["complete"]:
            result = b.checked(path / "result.json")
            b.require(result["protocol_id"] == protocol_id and result["condition_id"] == key,
                      "saved terminal belongs to another protocol or condition")
            terminals += 1
        states.append(dict(condition_id=key, **row))
    b.require(all(p.name in job["condition_ids"] for p in (stable / "outputs").glob("*") if p.is_dir()),
              "unregistered condition output")
    return dict(progress_units=sum(s["progress_units"]+int(s["complete"]) for s in states),
        terminal_conditions=terminals, completed_digest=b.digest(states), unknown_calls=len(unknown),
        unknown_intents=unknown,resume_allowed=not unknown,
        new_model_calls=sum(s["new_model_calls"] for s in states))


def is_resource_failure(error, resources):
    return isinstance(error, (resources.ResourceDeferred,resources.ResourceGateError,
        resources.LifetimeResourceFailure,resources.R3CapacityError)) or (
        error.__class__.__name__ == "OutOfMemoryError" and error.__class__.__module__.startswith("torch"))


def run(job_id,gpu_index,attempt_root):
    import finqa_v74_registration as registration
    import finqa_v74_resources as resources
    import finqa_v74_runtime as runtime
    protocol = registration.checked_protocol()
    b.require(job_id in protocol["jobs"], "unregistered job")
    job,attempt = protocol["jobs"][job_id],Path(attempt_root).resolve()
    source=protocol["model_bindings"]["P"]
    stable=directory(job)
    b.require(attempt.parent == stable / "attempts" and attempt.name.startswith("attempt")
        and os.environ.get("V54_JOB_ID") == job_id, "unregistered worker attempt")
    b.require(gpu_index in range(8) and os.environ.get("CUDA_VISIBLE_DEVICES") == protocol["gpu_uuids"][str(gpu_index)],
              "worker device binding differs")
    number=int(attempt.name.removeprefix("attempt"))
    started,guard,predictor=time.time(),None,None
    stable.mkdir(parents=True,exist_ok=True)
    with (stable / "worker.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.publish(attempt / "started/record.json",dict(protocol_id=protocol["id"],job=job,
            pid=os.getpid(),started_epoch=started,gpu_index=gpu_index))
        b.require(audit(job,protocol["id"])["resume_allowed"],"unresolved model/tool call prohibits retry")
        bundle=b.read_ref(protocol["inputs"])
        conditions={c["condition_id"]:c for c in bundle["conditions"]}
        b.require(set(conditions)==set(job["condition_ids"]),"condition roster changed")
        try:
            with resources.execution_context(b.ROOT,job,gpu_index) as guard:
                def predictor_factory():
                    nonlocal predictor
                    if predictor is None:
                        predictor=b.source_v73("runtime").Predictor(source["checkpoint"],"P",guard,source)
                        b.publish(attempt / "model_load/record.json",dict(schema="v74_actual_P_model_loaded.v1",
                            protocol_id=protocol["id"],job_id=job_id,model="P",source_binding_id=b.digest(source),
                            attempt_root=str(attempt),pid=os.getpid(),gpu_index=gpu_index,loaded_epoch=time.time(),
                            load_evidence=predictor.load_evidence,L_model_loaded=False))
                    return predictor
                outcomes={}
                actual_calls=0
                for key in job["condition_ids"]:
                    guard.check("before_hybrid_condition",boundary=True)
                    outcome=runtime.run_condition(conditions[key], output_dir=stable / "outputs" / key,
                        protocol_id=protocol["id"],inputs_id=bundle["id"],attempt=number,
                        predictor_factory=predictor_factory,guard=guard)
                    outcomes[key]=b.entry(stable / "outputs" / key / "result.json")
                    actual_calls += outcome["new_model_calls"]
                    b.require(actual_calls <= protocol["scientific_contract"]["maximum_new_model_calls"],
                              "actual call count exceeded frozen upper bound")
                    b.write_status(stable / "progress/status.json",dict(job_id=job_id,protocol_id=protocol["id"],
                        terminal_conditions=len(outcomes),new_model_calls=actual_calls,updated_epoch=time.time()))
                counters=predictor.counters if predictor else {}
                if predictor:
                    predictor.close(); predictor=None
            state=audit(job,protocol["id"])
            b.require(state["terminal_conditions"]==192 and state["resume_allowed"],"incomplete hybrid panel")
            result=b.publish(stable / "result/record.json",dict(schema="v74_hybrid_worker_complete.v1",
                status="COMPLETE",protocol_id=protocol["id"],job=job,job_id=job_id,pid=os.getpid(),
                gpu_index=gpu_index,started_epoch=started,finished_epoch=time.time(),outcomes=outcomes,
                output_refs=list(outcomes.values()),terminal_conditions=192,new_model_calls=state["new_model_calls"],
                current_attempt_new_forward_counters=counters,resources=guard.report(),model_released=True,
                new_first_responses=0,new_probability_sequences=0,optimizer_updates=0,native_scores=0,external_API_calls=0))
            b.publish(attempt / "completed/record.json",dict(protocol_id=protocol["id"],result=b.entry(stable / "result/record.json")))
            return result
        except BaseException as error:
            state=audit(job,protocol["id"])
            resource=is_resource_failure(error,resources)
            b.publish(attempt / "failure/record.json",dict(protocol_id=protocol["id"],job_id=job_id,
                exception=type(error).__name__,error=str(error),finished_epoch=time.time(),
                confirmed_resource_failure=resource,recoverable_at_actual_return_boundary=resource and state["resume_allowed"],
                durable=state,resources=guard.report() if guard else None))
            raise
