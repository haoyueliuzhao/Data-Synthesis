"""Frozen V74 entry: inference probes and a separate CPU-only summary child."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import time

import finqa_v74_binding as b
import finqa_v74_signals as signals


def verify_imported_sources(implementation):
    registration = importlib.import_module("finqa_v74_registration")
    allowed = registration.allowed_import_sources()
    frozen_package = Path(implementation["frozen_source_root"]).resolve()
    rows, hashes = [], {}
    for name, module in sorted(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        script = path.name.startswith("finqa_") or name.startswith("finqa_")
        if not package and not script:
            continue
        b.require(not package or path.is_relative_to(frozen_package), "non-frozen scientific package")
        b.require(str(path) in allowed, "unregistered imported source: " + str(path))
        if str(path) not in hashes:
            hashes[str(path)] = b.sha(path)
        b.require(hashes[str(path)] == allowed[str(path)], "imported source bytes changed")
        rows.append(dict(module=name, path=str(path), sha256=hashes[str(path)]))
    return dict(verified_dependency_count=len(rows), dependencies=rows, dependencies_digest=b.digest(rows))


def check_imports():
    registration = importlib.import_module("finqa_v74_registration")
    protocol, implementation = registration.checked_protocol(), registration.checked_implementation()
    for name in ("worker", "runtime", "inputs", "evaluation", "resources", "controller"):
        importlib.import_module("finqa_v74_" + name)
    _binding, final, _model, measurement = b.source_v73("runtime")._modules()
    measurement._api()
    importlib.import_module("finqa_v74_runtime").native_modules()
    importlib.import_module("finqa_v74_evaluation")._runtime()
    importlib.import_module("finqa_v74_resources").validate_registered_contract(protocol)
    b.require(not final.torch.cuda.is_initialized(), "CPU dependency check initialized CUDA")
    b.require(b.checked(b.ROOT / "prepared/record.json")["protocol"]["id"] == protocol["id"], "preparation differs")
    return b.publish(b.ROOT / "frozen_worker_import_verification/record.json", dict(
        schema="v74_actual_frozen_CPU_dependencies.v1", status="PASS", protocol_id=protocol["id"],
        implementation_id=implementation["id"], CUDA_initialized=False, model_loaded=False,
        new_model_calls=0, resource_constructor_contract_checked=True,
        **verify_imported_sources(implementation)))


def accepted_analysis_jobs(protocol):
    """Independently require the identity-bound, accepted actual worker exits.

    This gate also applies to a directly invoked frozen CPU entry. It reads only
    the small immutable launch/result/exit receipts, never original episodes.
    """
    expected = {"P.continuation"}
    b.require(set(protocol["jobs"]) == expected, "CPU analysis requires one fixed continuation worker")
    barrier_path = b.ROOT / "all_jobs_exit_barrier/record.json"
    barrier = b.checked(barrier_path)
    b.require(barrier["protocol_id"] == protocol["id"] and barrier["active_workers"] == []
        and set(barrier["accepted_jobs"]) == expected and set(barrier["actual_exits"]) == expected,
        "CPU analysis requires the complete empty-worker actual-exit barrier")
    rows, identities = {}, set()
    for key in sorted(expected):
        job = protocol["jobs"][key]
        stable = b.ROOT / "jobs" / key
        accepted_ref = barrier["accepted_jobs"][key]
        b.require(Path(accepted_ref["path"]).resolve() == stable / "accepted/record.json",
                  "barrier accepted reference escaped its registered job")
        accepted = b.read_ref(accepted_ref)
        b.require(accepted["protocol_id"] == protocol["id"] and accepted["job_id"] == key
            and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and type(accepted["attempt"]) is int and accepted["attempt"] > 0,
            "CPU analysis accepted shard binding changed")
        attempt = stable / "attempts" / f"attempt{accepted['attempt']:04d}"
        b.require(accepted["actual_exit"] == barrier["actual_exits"][key]
            and Path(accepted["actual_exit"]["path"]).resolve() == attempt / "actual_exit/record.json"
            and Path(accepted["result"]["path"]).resolve() == stable / "result/record.json",
            "barrier actual-exit/result references differ from the accepted attempt")
        actual, result = b.read_ref(accepted["actual_exit"]), b.read_ref(accepted["result"])
        launch = b.checked(attempt / "launch/record.json")
        completed = b.checked(attempt / "completed/record.json")
        b.require(actual["protocol_id"] == result["protocol_id"] == launch["protocol_id"]
            == completed["protocol_id"] == protocol["id"]
            and actual["job_id"] == result["job_id"] == key == job["job_id"]
            and result["job"] == launch["job"] == job
            and actual["attempt"] == launch["attempt"] == accepted["attempt"]
            and actual["returncode"] == 0 and actual["actual_waitpid_observed"] is True
            and actual["pid"] == launch["pid"] == result["pid"]
            and isinstance(actual["birth"], str) and actual["birth"].isdigit()
            and actual["birth"] == launch["birth"]
            and actual["gpu_index"] == launch["gpu_index"] == result["gpu_index"]
            and launch["gpu_uuid"] == protocol["gpu_uuids"][str(actual["gpu_index"])],
            "CPU analysis needs identity-matched same-job actual exit zero")
        b.require(result["status"] == "COMPLETE" and result["id"] == accepted["result_id"]
            and completed["result"] == accepted["result"]
            and result["resources"]["all_gates_passed"] is True and result["model_released"] is True
            and result["terminal_conditions"] == len(job["condition_ids"]) == 192
            and set(result["outcomes"]) == set(job["condition_ids"])
            and len(result["output_refs"]) == 192
            and all(result[field] == 0 for field in ("optimizer_updates", "new_first_responses", "native_scores", "external_API_calls")),
            "CPU analysis requires the accepted complete inference-only result")
        identity = (actual["pid"], actual["birth"])
        b.require(identity not in identities, "same worker identity cannot count as two accepted shards")
        identities.add(identity)
        rows[key] = dict(job=job, accepted_ref=accepted_ref, accepted=accepted,
                         actual_exit=actual, result=result)
    return b.entry(barrier_path), rows


def analyze(attempt):
    import finqa_v74_registration as registration
    import finqa_v74_resources as resources
    import finqa_v74_controller as controller
    import finqa_v74_evaluation as evaluation

    protocol = registration.checked_protocol()
    attempt = Path(attempt).resolve()
    b.require(attempt == b.ROOT / "final_analysis/attempt0001"
        and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "CPU summary scope changed")
    barrier_ref, accepted_jobs = accepted_analysis_jobs(protocol)
    import torch
    b.require(not torch.cuda.is_initialized(), "CPU analysis must not initialize CUDA")
    policy = controller.cpu_resource_policy()
    b.require(policy == protocol["final_analysis_resource_policy"], "CPU resource policy changed")
    started, pid, birth = time.time(), os.getpid(), resources.birth(os.getpid())
    observations, failures, ended = [], [], threading.Event()

    def sample(label):
        try:
            process, host = resources.process_memory(pid), resources.host_memory()
            ok = (process is not None and process["peak_rss_bytes"] <= policy["rss_historical_peak_limit_bytes"]
                and host["available_bytes"] >= policy["effective_host_available_reserve_bytes"])
            observations.append(dict(epoch=time.time(), label=label, passed=ok,
                peak_rss_bytes=process["peak_rss_bytes"] if process else None,
                available_bytes=host["available_bytes"]))
            if not ok:
                failures.append(dict(label=label, reason="CPU resource gate failed"))
        except Exception as error:
            failures.append(dict(label=label, reason=type(error).__name__))

    def monitor():
        while not ended.wait(1):
            sample("during_analysis")

    sample("before_analysis")
    b.require(not failures, "CPU resource admission failed")
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        bundle = b.read_ref(protocol["inputs"])
        result = accepted_jobs["P.continuation"]["result"]
        outcomes = {key:b.read_ref(ref) for key,ref in result["outcomes"].items()}
        summary = evaluation.evaluate(protocol, bundle, outcomes, root=b.ROOT,
            guard=SimpleNamespace(check=lambda *a, **kw: b.require(not failures, "CPU resource observation failed")),
            all_jobs_exit_barrier=barrier_ref)
        summary = b.publish(b.ROOT / "final_summary/record.json", dict(summary,
            input_ref=protocol["inputs"], all_jobs_exit_barrier=barrier_ref,
            accepted_jobs=[accepted_jobs["P.continuation"]["accepted_ref"]]))
        sample("after_analysis")
        b.require(not failures and not torch.cuda.is_initialized(), "final CPU gate failed")
    finally:
        ended.set(); thread.join(timeout=3)
        closed = b.publish(attempt / "resources/closeout/record.json", dict(
            schema="v74_CPU_summary_resources.v1", status="COMPLETE" if not failures else "FAILED",
            protocol_id=protocol["id"], pid=pid, birth=birth, CUDA_initialized=torch.cuda.is_initialized(),
            all_gates_passed=not failures, policy=policy, observations=observations, failures=failures,
            peak_rss_bytes=max((o["peak_rss_bytes"] or 0) for o in observations),
            minimum_host_available_bytes=min(o["available_bytes"] for o in observations),
            started_epoch=started, finished_epoch=time.time()))
    return b.publish(attempt / "result/record.json", dict(schema="v74_final_CPU_result.v1",
        status="COMPLETE", analysis_status=summary["status"], protocol_id=protocol["id"], pid=pid,
        resources=b.entry(attempt / "resources/closeout/record.json"),
        analysis=b.entry(b.ROOT / "final_summary/record.json"), new_model_calls=0,
        tools_executed=0, native_scores=192, optimizer_updates=0))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check-imports", "activate", "supervise", "run", "worker", "analyze"), required=True)
    parser.add_argument("--root", type=Path, default=b.ROOT)
    parser.add_argument("--job")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--attempt-root", type=Path)
    args = parser.parse_args(argv)
    b.require(args.root.resolve() == b.ROOT and Path(__file__).resolve().parent == b.ROOT / "implementation", "only frozen V74 entry may execute")
    if args.mode in ("worker", "analyze"):
        b.require(args.attempt_root is not None and args.attempt_root.resolve().is_relative_to(b.ROOT), "missing bounded attempt")
        signal_dir = args.attempt_root / "signals"
    else:
        signal_dir = b.ROOT / ("supervisor/signals" if args.mode == "supervise" else "controller/signals" if args.mode == "run" else args.mode + "/signals")
    observer = signals.install(signal_dir, role=args.mode, context=dict(experiment="V74", job=args.job))
    try:
        b.install_scientific_paths(); b.install_registered_auxiliary()
        registration = importlib.import_module("finqa_v74_registration")
        protocol = registration.checked_protocol()
        b.require(protocol["signal_policy"] == signals.signals_policy()
            and protocol["signal_source_bindings"] == signals.external_source_bindings(), "signal contract changed")
        if args.mode == "check-imports":
            result = check_imports()
        else:
            b.require(b.checked(b.ROOT / "frozen_worker_import_verification/record.json")["status"] == "PASS", "cold dependency acceptance required")
            if args.mode == "worker":
                result = importlib.import_module("finqa_v74_worker").run(args.job, args.gpu, args.attempt_root)
            elif args.mode == "analyze":
                result = analyze(args.attempt_root)
            else:
                controller = importlib.import_module("finqa_v74_controller")
                result = controller.Controller().run() if args.mode == "run" else getattr(controller, args.mode)()
        print(json.dumps({key: result.get(key) for key in ("status", "id", "pid")}, ensure_ascii=False))
        return 0 if result.get("status") in ("PASS", "COMPLETE", "ACTIVATED", "STARTED") else 2
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
