"""Four-worker V54 resource ownership and native on-demand CUDA lifetime gates.

This module never changes the scientific model, sampling policy, loss, gradient,
or saved state. GPU leases belong to the controller and remain inherited by each
child until its real exit. Missing/changed capacity waits before CUDA/model work.
"""

from __future__ import annotations

import json
import os
import signal
import stat
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import finqa_v37_task_cache as records

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01"
ROOT = V18 / "v54_feedback_temperature_01"
GIB = 1024**3
CUBLAS_WORKSPACE_CONFIG = ":4096:8"
GPU_UUIDS = {
    "0": "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5",
    "1": "GPU-0a62363e-fb3c-74fd-c5fe-1a2720c7e66a",
    "2": "GPU-88a33540-ff55-746e-d82b-45821b463102",
    "3": "GPU-004a2d75-6298-df4d-7b95-103bc6c1b02a",
    "4": "GPU-ae8978c8-5100-933e-78d1-46ed781a8a0e",
    "5": "GPU-f731a280-01e3-2359-ace9-aa2ad2112f55",
    "6": "GPU-6cf85ebf-ae89-905b-5d97-46f83b295526",
    "7": "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434",
}
CPU_AFFINITY = {str(i): "0-37,76-113" if i < 4 else "38-75,114-151" for i in range(8)}
MINIMUM_FREE_GIB = dict(class_=24, feedback=24, replay=56, distribution=24, train=26, generate=24)
HOST_STARTUP_GIB = dict(class_=160, feedback=64, replay=48, distribution=64, train=48, generate=48)
require, digest, sha = records.require, records.digest, records.sha
checked, publish, entry, file_ref, read_ref = (
    records.checked, records.publish, records.entry, records.file_ref, records.read_ref,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def _legacy_measurements():
    # Existing immutable /proc/cgroup measurement implementation, not its policy.
    import finqa_v37_controller
    return finqa_v37_controller


def birth(pid):
    return _legacy_measurements().birth(pid)


def inventory():
    result = _legacy_measurements().inventory()
    for row in result:
        row["memory_free_mib"] = row["free_mib"]
    return result


def host_memory():
    return _legacy_measurements().host_memory()


def process_memory(pid):
    return _legacy_measurements().process_memory(pid)


def kind(job):
    phases = {**{f"shard{i:02d}": "class_" for i in range(4)},
              "feedback_C05": "feedback", "replay_C05": "replay",
              "distribution_C05": "distribution", "generate": "generate",
              **{f"train_{arm}": "train" for arm in ("Hold", "C1", "C05")}}
    stage = job.get("stage")
    require(stage is None or stage in phases, "unregistered V54 scientific stage")
    values = [phases[stage]] if stage is not None else []
    for field in ("kind", "memory_phase"):
        value = job.get(field)
        if value is not None:
            values.append("class_" if value == "class" else value)
    require(values and all(value in MINIMUM_FREE_GIB and value == values[0] for value in values),
            "V54 stage and memory phase differ")
    return values[0]


def resource_policy():
    return dict(schema="v54_native_four_worker_resource_policy.v1",
                allowed_gpu_indices=list(range(8)), gpu_uuids=GPU_UUIDS,
                max_gpu_workers=4, max_workers_per_gpu=1,
                initializing_waiting_and_draining_count=True,
                minimum_free_gib_by_kind=MINIMUM_FREE_GIB,
                feedback_admission_basis=dict(
                    historical_same_model_virtual_peak_allocated_bytes=17140014080,
                    same_context_and_token_caps=True, no_warm_allocation=True,
                    logits_temperature_does_not_expand_KV=True,
                    empirical_admission_is_not_future_peak_guarantee=True),
                host_startup_gib_by_kind=HOST_STARTUP_GIB,
                allocated_lifetime_limit_bytes=76*GIB,
                boundary_physical_free_reserve_bytes=2*GIB,
                class_rss_limit_bytes=160*GIB, other_rss_limit_bytes=192*GIB,
                effective_host_available_reserve_bytes=96*GIB,
                allocator_backend="native", warm_allocation_bytes=0, anchor_bytes=0,
                deterministic_cublas_workspace_config=CUBLAS_WORKSPACE_CONFIG,
                only_one_peak_reset_before_scientific_allocation=True,
                later_peak_resets_allowed=False, other_project_processes_untouched=True,
                pre_cuda_and_pre_model_resource_wait_same_process=True,
                resource_wait_deadline_seconds=None, scientific_deadline_seconds=None)


def worker_environment(row):
    env = dict(os.environ)
    env.update(CUDA_VISIBLE_DEVICES=row["uuid"], CUDA_DEVICE_ORDER="PCI_BUS_ID",
               CUBLAS_WORKSPACE_CONFIG=CUBLAS_WORKSPACE_CONFIG,
               OMP_NUM_THREADS="8", MKL_NUM_THREADS="8", OPENBLAS_NUM_THREADS="1",
               TOKENIZERS_PARALLELISM="false", PYTHONUNBUFFERED="1",
               PYTORCH_CUDA_ALLOC_CONF="backend:native,expandable_segments:False")
    env.pop("PYTORCH_ALLOC_CONF", None)
    env.pop("PYTORCH_NO_CUDA_MEMORY_CACHING", None)
    return env


class ResourceGateError(RuntimeError):
    pass


class ExplicitStop(RuntimeError):
    pass


class ResourceGuard:
    def __init__(self, root, job, gpu_index, *, torch_module=None):
        self.root, self.job, self.gpu = Path(root).resolve(), dict(job), int(gpu_index)
        self.job_id = job.get("job_id", job.get("id"))
        require(isinstance(self.job_id, str) and self.job_id
                and "/" not in self.job_id and ".." not in self.job_id, "invalid V54 job identity")
        self.kind = kind(job)
        self.protocol = checked(self.root / "protocol/record.json")
        require(self.protocol["resource_policy"] == resource_policy(), "resource contract changed")
        require(self.gpu in self.protocol["allowed_gpu_indices"]
                and self.protocol["gpu_uuids"][str(self.gpu)] == GPU_UUIDS[str(self.gpu)],
                "unregistered GPU UUID")
        self.torch = torch_module
        self.stop = SimpleNamespace(requested=False, reason=None, received_signals=[])
        self.observations, self.wait_seconds = [], 0.0
        self.violation = None
        self._reset = None
        self._handlers = {}
        self._thread_stop = threading.Event()
        self._thread = None
        self.lease_identity = None
        self._mutex = threading.Lock()
        self.started_at = now()
        self._began = time.monotonic()
        self.directory = self.root / "resources" / self.job_id / f"pid{os.getpid()}"
        self.directory.mkdir(parents=True, exist_ok=False)
        self._events = (self.directory / "observations.jsonl").open("x", buffering=1)

    def _record(self, value):
        with self._mutex:
            self._events.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")

    def _host(self):
        machine, process = host_memory(), process_memory(os.getpid())
        limit = (160 if self.kind == "class_" else 192) * GIB
        require(process is not None, "own process memory is unavailable")
        peak = max(process["rss_bytes"], process["peak_rss_bytes"])
        return dict(rss_bytes=process["rss_bytes"], peak_rss_bytes=peak,
                    available_bytes=machine["available_bytes"], rss_limit_bytes=limit,
                    available_reserve_bytes=96*GIB,
                    passed=peak <= limit and machine["available_bytes"] >= 96*GIB)

    def _signal(self, signum, _frame):
        self.stop.requested = True
        self.stop.reason = "explicit_signal"
        self.stop.received_signals.append(dict(signal=signum, received_at_epoch=time.time()))

    def _host_sampler(self):
        while not self._thread_stop.wait(1.0):
            try:
                host = self._host()
                if not host["passed"]:
                    self.violation = dict(kind="host_memory", at=now(), host=host)
                    self._record(self.violation)
                    return
            except BaseException as exc:
                self.violation = dict(kind="host_observation_failed", at=now(),
                                      error_type=type(exc).__name__, error=str(exc))
                self._record(self.violation)
                return

    def _wait(self, *, cuda_initialized):
        start = time.monotonic()
        try:
            return self._wait_until_capacity(cuda_initialized=cuda_initialized)
        finally:
            # A stopped wait still consumed this worker's slot and wall time.
            # Count each invocation once, without mixing concurrent worker
            # seconds into the controller's separately recorded queue clock.
            self.wait_seconds += time.monotonic() - start

    def _wait_until_capacity(self, *, cuda_initialized):
        start = time.monotonic()
        minimum = MINIMUM_FREE_GIB[self.kind] * GIB
        while True:
            if self.stop.requested:
                raise ExplicitStop("explicit stop during pre-scientific resource wait")
            rows = {int(row["index"]): row for row in inventory()}
            require(self.gpu in rows and rows[self.gpu]["uuid"] == GPU_UUIDS[str(self.gpu)],
                    "physical GPU identity changed during resource wait")
            host = self._host()
            if host["peak_rss_bytes"] > host["rss_limit_bytes"]:
                # VmHWM cannot fall again; this is a lifetime hard failure,
                # not transient capacity that can recover in the same process.
                self.violation = dict(kind="host_rss_peak", at=now(), host=host)
                self._record(self.violation)
                raise ResourceGateError("pre-model process exceeded its historical RSS hard gate")
            if cuda_initialized:
                require(self.torch.cuda.memory_allocated() == 0,
                        "pre-model waiting cannot contain scientific CUDA tensors")
                free = int(self.torch.cuda.mem_get_info()[0])
                required = max(2*GIB, minimum - 3*GIB)
            else:
                free, required = int(rows[self.gpu]["free_mib"] * 1024**2), minimum
            if host["passed"] and free >= required:
                elapsed = time.monotonic() - start
                self._record(dict(at=now(), event="resource_admitted", gpu_index=self.gpu,
                                  free_bytes=free, required_bytes=required, host=host,
                                  cuda_initialized=cuda_initialized, elapsed_seconds=elapsed))
                return
            self._record(dict(at=now(), event="waiting_for_capacity", gpu_index=self.gpu,
                              free_bytes=free, required_bytes=required, host=host,
                              cuda_initialized=cuda_initialized,
                              no_scientific_work_retried=True))
            time.sleep(2)

    def __enter__(self):
        try:
            require(os.environ.get("CUDA_VISIBLE_DEVICES") in (str(self.gpu), GPU_UUIDS[str(self.gpu)]),
                    "worker visibility differs from registered physical GPU")
            require(os.environ.get("CUBLAS_WORKSPACE_CONFIG") == CUBLAS_WORKSPACE_CONFIG,
                    "fixed deterministic CUBLAS_WORKSPACE_CONFIG=:4096:8 required before CUDA")
            require(os.environ.get("V54_JOB_ID") == self.job_id, "worker job/dispatch mismatch")
            lease = int(os.environ["V54_GPU_LEASE_FD"])
            expected = Path(self.protocol["gpu_lease_root"]) / ("gpu-" + digest(GPU_UUIDS[str(self.gpu)]) + ".lock")
            require(Path(os.readlink(f"/proc/self/fd/{lease}")).resolve() == expected.resolve(),
                    "worker did not inherit its actual project GPU lease")
            actual, target = os.fstat(lease), expected.stat()
            require(stat.S_ISREG(actual.st_mode)
                    and (actual.st_dev, actual.st_ino) == (target.st_dev, target.st_ino),
                    "inherited GPU lease descriptor no longer names the registered inode")
            locks = [line.split() for line in Path(f"/proc/self/fdinfo/{lease}").read_text().splitlines()
                     if line.startswith("lock:")]
            require(any("FLOCK" in row and "WRITE" in row for row in locks),
                    "inherited GPU lease descriptor has no held exclusive flock")
            self.lease_identity = dict(path=str(expected.resolve()), descriptor=lease,
                                       device=actual.st_dev, inode=actual.st_ino,
                                       held_exclusive_flock=True)
            for sig in (signal.SIGTERM, signal.SIGINT):
                self._handlers[sig] = signal.signal(sig, self._signal)
            self._wait(cuda_initialized=False)
            if self.torch is None:
                import torch
                self.torch = torch
            require(not self.torch.cuda.is_initialized(), "V54 must enter its resource gate before CUDA")
            self.torch.cuda.set_device(0)
            require(self.torch.cuda.memory.get_allocator_backend() == "native", "native allocator required")
            require(self.torch.cuda.memory_allocated() == self.torch.cuda.memory_reserved() == 0,
                    "scientific tensors exist before lifetime monitor")
            self._reset = self.torch.cuda.reset_peak_memory_stats
            self._reset()

            def no_reset(*_args, **_kwargs):
                raise ResourceGateError("post-admission lifetime peak reset forbidden")

            self.torch.cuda.reset_peak_memory_stats = no_reset
            self._wait(cuda_initialized=True)
            self.check("before_model_load")
            self._thread = threading.Thread(target=self._host_sampler, daemon=True)
            self._thread.start()
            publish(self.directory / "admission/record.json", dict(
                schema="v54_actual_native_cuda_admission.v1", at=now(),
                protocol_id=self.protocol["id"], job_id=self.job_id,
                gpu_index=self.gpu, gpu_uuid=GPU_UUIDS[str(self.gpu)],
                pid=os.getpid(), birth=birth(os.getpid()),
                minimum_dispatch_free_bytes=MINIMUM_FREE_GIB[self.kind]*GIB,
                warm_allocation_bytes=0, anchor_bytes=0, peak_resets_before_loading=1,
                later_peak_resets_allowed=False, resource_wait_seconds=self.wait_seconds,
                inherited_gpu_lease=self.lease_identity,
                before_model_load=self.observations[-1]))
            return self
        except BaseException as error:
            try:
                self._closeout(error)
            finally:
                self._finish()
            raise

    def check(self, label, boundary=True, **context):
        if self.violation is not None:
            raise ResourceGateError("runtime host resource gate failed: " + str(self.violation))
        if self.stop.requested and self.job.get("stage") != "replay_C05":
            raise ExplicitStop("explicit stop before next scientific operation")
        cuda = self.torch.cuda
        cuda.synchronize()
        free, total = cuda.mem_get_info()
        host = self._host()
        value = dict(at=now(), label=str(label), boundary=bool(boundary),
                     allocated_bytes=int(cuda.memory_allocated()),
                     reserved_bytes=int(cuda.memory_reserved()),
                     peak_allocated_bytes=int(cuda.max_memory_allocated()),
                     peak_reserved_bytes=int(cuda.max_memory_reserved()),
                     free_bytes=int(free), total_bytes=int(total), host=host,
                     stop_requested=self.stop.requested,
                     context={k: v for k, v in context.items() if isinstance(v, (str, int, float, bool, type(None)))})
        value["allocated_pass"] = value["peak_allocated_bytes"] <= 76*GIB
        value["free_pass"] = not boundary or free >= 2*GIB
        value["passed"] = value["allocated_pass"] and value["free_pass"] and host["passed"]
        self.observations.append(value)
        self._record(value)
        if not value["passed"]:
            self.violation = value
            raise ResourceGateError("actual V54 GPU or host resource gate failed")
        return value

    def event_sink(self, event):
        if isinstance(event, dict):
            return self.check(event.get("label", event.get("event", "scientific_boundary")),
                              boundary=event.get("boundary", True))
        return self.check(str(event))

    def report(self):
        values = self.observations
        return dict(all_gates_passed=bool(values) and self.violation is None
                    and all(v["passed"] for v in values),
                    single_process_lifetime_includes_loading=True,
                    actual_boundary_observations=len(values),
                    peak_allocated_bytes=max((v["peak_allocated_bytes"] for v in values), default=0),
                    minimum_boundary_free_bytes=min((v["free_bytes"] for v in values if v["boundary"]), default=None),
                    peak_rss_bytes=max((v["host"]["peak_rss_bytes"] for v in values), default=0),
                    minimum_host_available_bytes=min((v["host"]["available_bytes"] for v in values), default=None),
                    resource_wait_seconds=self.wait_seconds,
                    peak_resets_before_loading=int(self._reset is not None),
                    peak_resets_after_loading=0, warm_allocation_bytes=0, anchor_bytes=0,
                    received_signals=list(self.stop.received_signals),
                    observed_violation=self.violation,
                    observations_path=str(self.directory / "observations.jsonl"))

    def _finish(self):
        self._thread_stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self._reset is not None:
            self.torch.cuda.reset_peak_memory_stats = self._reset
        for sig, handler in self._handlers.items():
            signal.signal(sig, handler)
        if not self._events.closed:
            self._events.flush()
            os.fsync(self._events.fileno())
            self._events.close()

    def _closeout(self, error):
        return publish(self.directory / "closeout/record.json", dict(
            schema="v54_resource_lifetime_closeout.v1", at=now(),
            protocol_id=self.protocol["id"], job_id=self.job_id,
            gpu_index=self.gpu, pid=os.getpid(), birth=birth(os.getpid()),
            elapsed_slot_seconds=time.monotonic()-self._began,
            status="COMPLETE" if error is None else "FAILED_OR_STOPPED",
            error=None if error is None else dict(type=type(error).__name__, message=str(error)),
            inherited_gpu_lease=self.lease_identity, resources=self.report()))

    def __exit__(self, exc_type, exc, _tb):
        final_error = None
        try:
            # End concurrent host sampling before the final serial resource
            # observation, so the accepted closeout and returned report agree.
            self._thread_stop.set()
            if self._thread is not None:
                self._thread.join(timeout=3)
                if self._thread.is_alive():
                    self.violation = dict(kind="host_sampler_did_not_exit", at=now())
                    final_error = ResourceGateError("host sampler did not exit at final boundary")
            if exc is None and final_error is None:
                try:
                    self.check("worker_final_boundary")
                    # Replay defers signals until a complete-response save.
                    # That exception cannot apply to a completed stage exit.
                    if self.stop.requested:
                        raise ExplicitStop("explicit stop at complete scientific stage boundary")
                except BaseException as error:
                    final_error = error
            self._closeout(exc if exc is not None else final_error)
        finally:
            self._finish()
        if exc is None and final_error is not None:
            raise final_error


@contextmanager
def execution_context(root, job, gpu_index):
    with ResourceGuard(root, job, gpu_index) as guard:
        yield guard
