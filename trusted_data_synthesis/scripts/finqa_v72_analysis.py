"""Single CPU-only final analysis child, under the registered RAM hard gates."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import signal
import sys
import threading
import time

import finqa_v72_binding as binding

GIB = 1024 ** 3
RSS_LIMIT_BYTES = 64 * GIB
HOST_RESERVE_BYTES = 96 * GIB


def resource_policy():
    return dict(schema="v72_single_final_CPU_analysis_resource_policy.v1",
        max_cpu_children=1, GPU_workers_required_exited=4, GPU_initialization_allowed=False,
        rss_historical_peak_limit_bytes=RSS_LIMIT_BYTES,
        effective_host_available_reserve_bytes=HOST_RESERVE_BYTES,
        startup_required_available_bytes=RSS_LIMIT_BYTES + HOST_RESERVE_BYTES,
        native_scoring_and_diagnostics_same_process_lifetime=True,
        sample_interval_seconds=1, actual_exit_zero_required=True,
        unknown_numeric_or_resource_failure_automatic_retry=False,
        explicit_stop_no_auto_restart=True, original_complete_score_artifacts_read_only=True)


class CPUAnalysisStopped(RuntimeError):
    automatic_recovery_allowed = False


def run(root, attempt_root):
    root, directory = Path(root).resolve(), Path(attempt_root).resolve()
    binding.require(root == binding.ROOT.resolve() and directory == root / "final_analysis/attempt0001",
                    "unregistered final CPU child")
    protocol = binding.checked(root / "protocol/record.json")
    binding.require(protocol["final_analysis_resource_policy"] == resource_policy(),
                    "final CPU analysis resource contract changed")
    barrier = binding.checked(root / "all_jobs_exit_barrier/record.json")
    binding.require(barrier["protocol_id"] == protocol["id"] and barrier["active_workers"] == []
                    and len(barrier["accepted_jobs"]) == len(barrier["actual_exits"]) == 4,
                    "all scientific/evaluation actual exits precede private analysis")
    runtime = importlib.import_module("finqa_v72_resources").controller_runtime()
    observations, received, failure = [], [], []
    done = threading.Event()

    def sample(label):
        process, host = runtime.process_memory(os.getpid()), runtime.host_memory()
        row = dict(label=label, epoch=time.time(), process=process, host=host)
        binding.require(isinstance(process, dict) and type(process.get("peak_rss_bytes")) is int
                        and type(host.get("available_bytes")) is int,
                        "CPU child actual resource observation unavailable")
        row["passed"] = (process["peak_rss_bytes"] <= RSS_LIMIT_BYTES
                         and host["available_bytes"] >= HOST_RESERVE_BYTES)
        observations.append(row)
        if not row["passed"]:
            raise CPUAnalysisStopped("final CPU analysis RAM hard gate failed")
        if (root / "STOP").exists() or (root / "control/stop_requested/record.json").exists():
            raise CPUAnalysisStopped("explicit stop before final CPU analysis boundary")
        return row

    def monitor():
        while not done.wait(1):
            try:
                sample("periodic")
            except BaseException as error:
                failure.append(dict(error_type=type(error).__name__, error=str(error)))
                os.kill(os.getpid(), signal.SIGTERM)
                return

    def stopped(signum, _frame):
        received.append(signum)
        raise CPUAnalysisStopped("final CPU child received an explicit or resource stop")

    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    thread, result, status = None, None, "FAILED"
    started = time.time()
    for number in previous:
        signal.signal(number, stopped)
    try:
        sample("before_analysis")
        thread = threading.Thread(target=monitor, name="v72-final-CPU-resource-monitor", daemon=True)
        thread.start()
        result = importlib.import_module("finqa_v72_evaluation").finish(root)
        sample("after_analysis")
        torch = importlib.import_module("torch")
        binding.require(not torch.cuda.is_initialized(), "CPU final analysis unexpectedly initialized CUDA")
        binding.require(result.get("status") == "COMPLETE" and not failure and not received,
                        "incomplete or stopped analysis cannot be accepted")
        status = "COMPLETE"
    except BaseException as error:
        failure.append(dict(error_type=type(error).__name__, error=str(error)))
        raise
    finally:
        done.set()
        if thread is not None:
            thread.join(timeout=5)
        for number, handler in previous.items():
            signal.signal(number, handler)
        torch = sys.modules.get("torch")
        cuda_initialized = bool(torch is not None and torch.cuda.is_initialized())
        resources = binding.publish(directory / "resources/closeout/record.json", dict(
            schema="v72_actual_CPU_analysis_resource_closeout.v1", status=status,
            protocol_id=protocol["id"], pid=os.getpid(), birth=runtime.birth(os.getpid()),
            policy=resource_policy(), started_epoch=started, finished_epoch=time.time(),
            all_gates_passed=status == "COMPLETE" and not failure and not received,
            observations=observations, received_signals=received, failures=failure,
            CUDA_initialized=cuda_initialized, automatic_retry=False))
    return binding.publish(directory / "result/record.json", dict(
        schema="v72_actual_CPU_analysis_complete.v1", status="COMPLETE", protocol_id=protocol["id"],
        pid=os.getpid(), analysis=result, resources=binding.entry(directory / "resources/closeout/record.json"),
        resource_closeout_id=resources["id"], all_four_jobs_actual_exits_previously_accepted=True))
