"""Cold fixed collection, candidate training and endpoint generation workers."""
from __future__ import annotations

import fcntl
import importlib
import os
from pathlib import Path
import time

import finqa_v75_binding as b


def directory(job):
    return importlib.import_module("finqa_v75_controller").job_directory(b.ROOT,job)


def audit(job,protocol_id):
    stable=directory(job)
    if job["stage"]=="collect":
        value=importlib.import_module("finqa_v75_collection_runtime").audit(job,stable)
    elif job["stage"]=="train":
        value=importlib.import_module("finqa_v75_training").audit_training_resume(b.ROOT,job)
    else:
        value=importlib.import_module("finqa_v75_evaluation").audit_job_resume(b.ROOT,job)
    value=dict(value)
    value["completed_digest"]=value.get("completed_digest",value.get("durable_progress_digest",b.digest(value)))
    value["complete_stage"]=(stable/"result/record.json").exists()
    if value["complete_stage"]:
        result=b.checked(stable/"result/record.json")
        b.require(result["protocol_id"]==protocol_id and result["job_id"]==job["job_id"],
                  "durable result belongs to another protocol/job")
    return value


def is_resource_failure(error,resources):
    return isinstance(error,(resources.ResourceDeferred,resources.ResourceGateError,
        resources.LifetimeResourceFailure,resources.R3CapacityError)) or (
        error.__class__.__name__=="OutOfMemoryError" and error.__class__.__module__.startswith("torch"))


def accepted_L_outcomes(protocol):
    outcomes={}
    for index in range(2):
        key=f"L.initial.shard{index}";job=protocol["jobs"][key]
        stable=directory(job)
        accepted=b.checked(stable/"accepted/record.json")
        actual=b.read_ref(accepted["actual_exit"]);result=b.read_ref(accepted["result"])
        b.require(accepted["protocol_id"]==actual["protocol_id"]==result["protocol_id"]==protocol["id"]
            and accepted["job_id"]==actual["job_id"]==result["job_id"]==key
            and accepted["actual_exit_zero"] is True and actual["actual_waitpid_observed"] is True
            and actual["returncode"]==0 and result["resources"]["all_gates_passed"] is True
            and result["model_released"] is True and result["id"]==accepted["result_id"],
            "P.post requires both actually accepted L collection exits")
        b.require(set(result["outcomes"])==set(job["task_ids"]) and not set(outcomes).intersection(result["outcomes"]),
                  "L outcome coverage differs from the fixed disjoint shards")
        outcomes.update(result["outcomes"])
    b.require(len(outcomes)==128,"P.post requires all128 original L conditions")
    return outcomes


def require_materials_accepted(protocol):
    directory=b.ROOT/"materials_preparation"
    accepted=b.checked(directory/"accepted/record.json")
    actual,result,resources=(b.read_ref(accepted[k]) for k in ("actual_exit","result","resources"))
    attempt=directory/"attempt0001"
    launch=b.checked(attempt/"launch/record.json")
    b.require(Path(accepted["actual_exit"]["path"]).resolve()==attempt/"actual_exit/record.json"
        and Path(accepted["result"]["path"]).resolve()==attempt/"result/record.json"
        and Path(accepted["resources"]["path"]).resolve()==attempt/"resources/closeout/record.json"
        and accepted["protocol_id"]==actual["protocol_id"]==result["protocol_id"]==resources["protocol_id"]
            ==launch["protocol_id"]==protocol["id"]
        and actual["actual_waitpid_observed"] is True and actual["returncode"]==0
        and result["status"]==resources["status"]=="COMPLETE" and resources["all_gates_passed"] is True
        and resources["CUDA_initialized"] is False
        and actual["pid"]==result["pid"]==resources["pid"]==launch["pid"]
        and actual["birth"]==resources["birth"]==launch["birth"]
        and result["analysis"]==accepted["analysis"]==b.entry(b.ROOT/"materials/record.json"),
        "training requires independently bound successful materials CPU actual exit")
    return accepted


def validate_result(root,job,result):
    b.require(result["status"]=="COMPLETE" and result["job_id"]==job["job_id"]
        and result["job"]==job and result["model_released"] is True
        and result["resources"]["all_gates_passed"] is True,
        "successful stage result/resource binding required")
    if job["stage"]=="collect":
        b.require(set(result["outcomes"])==set(job["task_ids"])
            and result["completed_slots"]==len(job["task_ids"])
            and result["logical_sessions"]+result["not_applicable"]==len(job["task_ids"])
            and 0<=result["new_model_calls"]<=job["maximum_model_calls"]
            and all(result[k]==0 for k in ("native_scores","optimizer_updates","new_probability_sequences","external_API_calls")),
            "collection dose or no-scoring boundary changed")
        b.require(job["phase"]=="P.post" or result["not_applicable"]==0,"initial collection cannot skip selected tasks")
    elif job["stage"]=="train":
        importlib.import_module("finqa_v75_training").validate_training_result(root,job,result)
    else:
        b.require(result["sessions"]==job["denominator"] and result["scoring_calls"]==0
            and result["private_references_read"] is False and result["new_API_calls"]==0,
            "autonomous endpoint shard dose or scoring boundary changed")
        seal=b.read_ref(result["whole_queue_seal"])
        b.require(seal["id"]==result["whole_queue_seal_id"] and seal["denominator"]==job["denominator"],
                  "endpoint shard lacks its exact native seal")


def run(job_id,gpu_index,attempt_root):
    import finqa_v75_registration as registration
    import finqa_v75_resources as resources
    protocol=registration.checked_protocol()
    b.require(job_id in protocol["jobs"],"unregistered GPU job")
    job=protocol["jobs"][job_id];stable=directory(job);attempt=Path(attempt_root).resolve()
    b.require(attempt.parent==stable/"attempts" and attempt.name.startswith("attempt")
        and os.environ.get("V54_JOB_ID")==job_id,"foreign worker attempt")
    b.require(gpu_index in range(8) and os.environ.get("CUDA_VISIBLE_DEVICES")==protocol["gpu_uuids"][str(gpu_index)],
              "worker device binding differs")
    number=int(attempt.name.removeprefix("attempt"))
    started,guard,predictor=time.time(),None,None
    stable.mkdir(parents=True,exist_ok=True)
    with (stable/"worker.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        b.publish(attempt/"started/record.json",dict(protocol_id=protocol["id"],job=job,pid=os.getpid(),
            gpu_index=gpu_index,started_epoch=started))
        try:
            b.require(audit(job,protocol["id"])["resume_allowed"],"unresolved state/call prohibits retry")
            with resources.execution_context(b.ROOT,job,gpu_index) as guard:
                if job["stage"]=="collect":
                    runtime=importlib.import_module("finqa_v75_collection_runtime")
                    bundle=b.read_ref(protocol["inputs"])
                    source=protocol["model_bindings"][job["model"]]
                    def predictor_factory():
                        nonlocal predictor
                        if predictor is None:
                            predictor=runtime.Predictor(source["checkpoint"],job["model"],guard,source)
                            b.publish(attempt/"model_load/record.json",dict(protocol_id=protocol["id"],job_id=job_id,
                                model=job["model"],source_binding_id=b.digest(source),load_evidence=predictor.load_evidence,
                                pid=os.getpid(),gpu_index=gpu_index,loaded_epoch=time.time()))
                        return predictor
                    parents=accepted_L_outcomes(protocol) if job["phase"]=="P.post" else None
                    body=runtime.run_collection(job,bundle,output_root=stable,protocol_id=protocol["id"],
                        attempt=number,predictor_factory=predictor_factory,guard=guard,source_L_outcomes=parents)
                    body["current_attempt_new_forward_counters"]=predictor.counters if predictor else {}
                    if predictor is not None:
                        predictor.close();predictor=None
                elif job["stage"]=="train":
                    require_materials_accepted(protocol)
                    body=importlib.import_module("finqa_v75_training").execute(b.ROOT,job,attempt,guard)
                else:
                    body=importlib.import_module("finqa_v75_evaluation").run(b.ROOT,job,gpu_index,attempt,guard)
            result=b.publish(stable/"result/record.json",dict(body,status="COMPLETE",protocol_id=protocol["id"],
                job=job,job_id=job_id,seed=137,stage=job["stage"],step=job.get("step"),arm=job.get("arm"),
                pid=os.getpid(),actual_worker_pid=os.getpid(),gpu_index=gpu_index,
                actual_attempt_root=str(attempt),started_epoch=started,finished_epoch=time.time(),
                resources=guard.report(),model_released=True))
            validate_result(b.ROOT,job,result)
            b.publish(attempt/"completed/record.json",dict(protocol_id=protocol["id"],result=b.entry(stable/"result/record.json")))
            return result
        except BaseException as error:
            state=audit(job,protocol["id"])
            resource=is_resource_failure(error,resources)
            b.publish(attempt/"failure/record.json",dict(protocol_id=protocol["id"],job_id=job_id,
                exception=type(error).__name__,error=str(error),finished_epoch=time.time(),
                confirmed_resource_failure=resource,recoverable_at_actual_return_boundary=resource and state["resume_allowed"],
                durable=state,resources=guard.report() if guard else None))
            raise
