"""One inference-only model shard, with immutable per-call return boundaries."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

import finqa_v73_binding as b


def directory(job):
    b.require(job["job_id"] in {f"{m}.shard{s}" for m in "PHL" for s in range(2)}, "foreign probe job")
    b.require(job["model"] == job["job_id"].split(".")[0], "job model differs from registered shard")
    return b.ROOT / "jobs" / job["job_id"]


def operations(job):
    return [("generation", key, key) for key in job["context_ids"]] + [
        ("probability", key, b.digest(key)) for key in job["target_keys"]]


def audit(job, protocol_id, source_binding_id=None):
    stable = directory(job)
    permitted = {(kind, op): key for kind, key, op in operations(job)}
    b.require(len(permitted) == len(operations(job)), "duplicate registered probe operations")
    completed, unknown, returns, intents = [], [], {}, {}
    for kind, key, op in operations(job):
        path = stable / "outputs" / kind / op / "returned.json"
        if path.exists():
            record = b.checked(path)
            b.require(record["protocol_id"] == protocol_id and record["job_id"] == job["job_id"]
                and record["model"] == job["model"] and record["key"] == key
                and record["kind"] == kind and record["operation_id"] == op
                and isinstance(record["source_binding_id"], str)
                and (source_binding_id is None or record["source_binding_id"] == source_binding_id),
                "saved return binding changed")
            returns[(kind, op)] = record
            completed.append(record["id"])
    for path in (stable / "outputs").glob("*/*/returned.json"):
        b.require((path.parent.parent.name, path.parent.name) in permitted,
                  "unregistered durable model return")
    for intent_path in stable.glob("attempts/attempt*/operations/*/*/intent.json"):
        intent = b.checked(intent_path)
        pair = (intent["kind"], intent["operation_id"])
        attempt_path = intent_path.parents[3]
        b.require(pair in permitted and intent["protocol_id"] == protocol_id
            and intent["job_id"] == job["job_id"] and intent["model"] == job["model"]
            and intent["key"] == permitted[pair]
            and intent_path.parent.name == pair[1] and intent_path.parent.parent.name == pair[0]
            and intent["attempt_root"] == str(attempt_path.resolve())
            and isinstance(intent["source_binding_id"], str)
            and (source_binding_id is None or intent["source_binding_id"] == source_binding_id),
            "foreign or moved saved intent")
        b.require(intent["id"] not in intents, "duplicate immutable intent identity")
        intents[intent["id"]] = intent
        aborted = intent_path.parent / "not_executed.json"
        if aborted.exists():
            proof = b.checked(aborted)
            b.require(proof["intent_id"] == intent["id"] and proof["confirmed_forward_calls"] == 0
                and proof["actual_generate_calls"] == 0 and proof["confirmed_resource_failure"] is True,
                "no-execution proof changed")
        if pair in returns:
            value = returns[pair]
            if value["intent_id"] == intent["id"]:
                b.require(not aborted.exists(), "same intent cannot be returned and confirmed unexecuted")
                b.require(value["input_id"] == intent["input_id"]
                    and value["source_binding_id"] == intent["source_binding_id"]
                    and value["attempt_root"] == intent["attempt_root"], "return source/input/attempt differs from intent")
            else:
                b.require(aborted.exists(), "return belongs to a different unresolved attempt")
        elif not aborted.exists():
            unknown.append(str(intent_path))
    b.require(all(value["intent_id"] in intents for value in returns.values()),
              "durable return has no corresponding actual call intent")
    return dict(progress_units=len(completed), completed_digest=b.digest(completed),
        unknown_calls=len(unknown), unknown_intents=unknown, resume_allowed=not unknown)


def is_resource_failure(error, resources):
    return isinstance(error, (resources.ResourceDeferred, resources.ResourceGateError,
        resources.LifetimeResourceFailure, resources.R3CapacityError)) or (
        error.__class__.__name__ == "OutOfMemoryError" and error.__class__.__module__.startswith("torch"))


def _normalize_generation(value, context, measurement):
    turn, receipt = value["turn"], value["turn"]["receipt"]
    raw = turn["raw_text"]
    b.require(receipt["raw_response_sha256"] == hashlib.sha256(raw.encode()).hexdigest(), "actual raw return hash changed")
    action = measurement.classification(raw, context["request"]["tools"])
    completion = measurement.completion_labels(response_ids=receipt["raw_generated_token_ids"],
        actual_eos=receipt["actual_eos"], finish_reason=receipt["finish_reason"],
        max_new_tokens=2048, eos_ids=receipt["sampling"]["eos_token_ids"])
    return dict(classification=action, completion=completion,
        raw_response_sha256=receipt["raw_response_sha256"],
        raw_generated_token_ids=receipt["raw_generated_token_ids"],
        response_ids_sha256=b.digest(receipt["raw_generated_token_ids"]))


def run(job_id, gpu_index, attempt_root):
    import finqa_v73_registration as registration
    import finqa_v73_resources as resources
    import finqa_v73_runtime as runtime
    import finqa_v73_measurement as measurement

    protocol = registration.checked_protocol()
    b.require(job_id in protocol["jobs"], "unregistered job")
    job, attempt = protocol["jobs"][job_id], Path(attempt_root).resolve()
    source = protocol["model_bindings"][job["model"]]
    source_binding_id = b.digest(source)
    stable = directory(job)
    b.require(attempt.parent == stable / "attempts" and attempt.name.startswith("attempt")
        and os.environ.get("V54_JOB_ID") == job_id, "unregistered worker attempt")
    b.require(gpu_index in range(8) and os.environ.get("CUDA_VISIBLE_DEVICES") == protocol["gpu_uuids"][str(gpu_index)], "device binding differs")
    stable.mkdir(parents=True, exist_ok=True)
    started, guard, predictor = time.time(), None, None
    with (stable / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.publish(attempt / "started/record.json", dict(protocol_id=protocol["id"], job=job,
            pid=os.getpid(), started_epoch=started, gpu_index=gpu_index))
        b.require(audit(job, protocol["id"], source_binding_id)["resume_allowed"], "unresolved model call prohibits retry")
        bundle = b.read_ref(protocol["inputs"])
        try:
            with resources.execution_context(b.ROOT, job, gpu_index) as guard:
                pending = [op for op in operations(job) if not (stable / "outputs" / op[0] / op[2] / "returned.json").exists()]
                if pending:
                    predictor = runtime.Predictor(source["checkpoint"], job["model"], guard, source)
                    b.publish(attempt / "model_load/record.json", dict(
                        schema="v73_actual_saved_inference_model_loaded.v1",
                        protocol_id=protocol["id"], job_id=job_id, model=job["model"],
                        source_binding_id=source_binding_id, attempt_root=str(attempt),
                        pid=os.getpid(), gpu_index=gpu_index, loaded_epoch=time.time(),
                        load_evidence=predictor.load_evidence))
                output_refs = []
                for kind, key, op in operations(job):
                    output = stable / "outputs" / kind / op
                    path = output / "returned.json"
                    item = bundle["contexts" if kind == "generation" else "targets"][key]
                    if not path.exists():
                        guard.check("before_probe_intent", boundary=True)
                        intent_dir = attempt / "operations" / kind / op
                        before = predictor.counters
                        before_generate_calls = predictor.provider.actual_model_calls
                        intent = b.publish(intent_dir / "intent.json", dict(protocol_id=protocol["id"],
                            job_id=job_id, model=job["model"], kind=kind, key=key, operation_id=op,
                            input_id=b.digest(item), source_binding_id=source_binding_id,
                            attempt_root=str(attempt), created_epoch=time.time()))
                        try:
                            value = predictor.generate(item) if kind == "generation" else predictor.measure(item)
                        except BaseException as error:
                            delta = {k: v - before.get(k, 0) for k, v in predictor.counters.items()}
                            forwards = sum(v for k, v in delta.items() if k.endswith("_forward_calls"))
                            generate_calls = predictor.provider.actual_model_calls - before_generate_calls
                            if is_resource_failure(error, resources) and forwards == 0 and generate_calls == 0:
                                b.publish(intent_dir / "not_executed.json", dict(intent_id=intent["id"],
                                    confirmed_resource_failure=True, confirmed_forward_calls=0,
                                    actual_generate_calls=0, counter_delta=delta, exception=type(error).__name__))
                            raise
                        # A complete model return is durable before post-call resource checks.
                        b.publish(path, dict(protocol_id=protocol["id"], job_id=job_id, model=job["model"],
                            kind=kind, key=key, operation_id=op, input_id=intent["input_id"],
                            intent_id=intent["id"], source_binding_id=source_binding_id,
                            attempt_root=str(attempt), returned_epoch=time.time(), value=value))
                        guard.check("after_durable_probe_return", boundary=True)
                    returned = b.checked(path)
                    b.require(returned["input_id"] == b.digest(item)
                        and returned["source_binding_id"] == source_binding_id
                        and returned["value"]["model_label"] == job["model"], "returned input or model source binding changed")
                    if kind == "generation":
                        receipt = returned["value"]["turn"]["receipt"]
                        b.require(receipt["identity"] == source["model_identity"]
                            and receipt["prompt_input_ids"] == item["prompt_input_ids"]
                            and receipt["request_sha256"] == b.digest(item["request"]),
                            "actual return does not belong to the frozen model/request tokens")
                    else:
                        b.require(returned["value"]["target_id"] == item["target_id"], "returned probability target changed")
                    normalized = (_normalize_generation(returned["value"], item, measurement)
                        if kind == "generation" else dict(measurement=dict(
                            returned["value"]["probability_summary"], groups=returned["value"]["groups"])))
                    b.publish(output / "result.json", dict(protocol_id=protocol["id"], model=job["model"],
                        kind=kind, key=key, returned=b.entry(path), **normalized))
                    output_refs.append(b.entry(output / "result.json"))
                    b.write_status(stable / "progress/status.json", dict(job_id=job_id,
                        protocol_id=protocol["id"], completed_operations=len(output_refs),
                        generation_completed=min(len(output_refs), len(job["context_ids"])),
                        probability_completed=max(0, len(output_refs) - len(job["context_ids"])),
                        updated_epoch=time.time()))
                counters = predictor.counters if predictor else {}
                if predictor:
                    predictor.close()
                    predictor = None
            result = b.publish(stable / "result/record.json", dict(schema="v73_probe_shard_complete.v1",
                status="COMPLETE", protocol_id=protocol["id"], job=job, job_id=job_id,
                gpu_index=gpu_index, pid=os.getpid(), started_epoch=started, finished_epoch=time.time(),
                output_refs=output_refs, actual_new_forward_counters=counters,
                generation_results=len(job["context_ids"]), probability_results=len(job["target_keys"]),
                resources=guard.report(), model_released=True, optimizer_updates=0,
                tools_executed=0, native_scores=0, external_API_calls=0))
            b.publish(attempt / "completed/record.json", dict(protocol_id=protocol["id"],
                result=b.entry(stable / "result/record.json")))
            return result
        except BaseException as error:
            state = audit(job, protocol["id"], source_binding_id)
            recoverable = is_resource_failure(error, resources) and state["resume_allowed"]
            b.publish(attempt / "failure/record.json", dict(protocol_id=protocol["id"], job_id=job_id,
                exception=type(error).__name__, error=str(error), finished_epoch=time.time(),
                confirmed_resource_failure=is_resource_failure(error, resources),
                recoverable_at_actual_return_boundary=recoverable, durable=state,
                actual_return_count=state["progress_units"], resources=guard.report() if guard else None))
            raise
