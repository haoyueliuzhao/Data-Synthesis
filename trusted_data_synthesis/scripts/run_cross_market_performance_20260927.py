"""Operational GPU admission overlay for the already frozen cross-market study.

The scientific protocol is always returned unchanged and with its original valid
identity. Only new workers use the registered capacity policy; existing workers
retain their implementation and are adopted through the original attempt ledger.
"""

import argparse
import copy
import importlib
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import run_cross_market_cuda_recovery_20260927 as recovery

previous, p = recovery.previous, recovery.p
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_performance_20260927.py"
DIRECTORY = "performance_01"
PROTOCOL = "cross_market_performance_operational_protocol"
CAPACITY_POLICY = dict(
    start_minimum_free_MiB=49152,
    continue_minimum_available_MiB=49152,
    maximum_boundary_wait_seconds=120,
    boundary_poll_seconds=10,
    available_capacity="CUDA free plus current worker reserved after empty_cache",
    empty_cache_at_each_session_boundary=True,
    no_mid_session_checks=True,
)
SOURCES = (SCRIPT, recovery.SCRIPT, recovery.isolation.SCRIPT)
LOGPROB_MODULE = "cross_market_logprob_collection_20260927"


def require(condition, reason):
    p.require(condition, "cross_market_performance." + reason)


def context(raw=None):
    return recovery.context(raw)


def logprob_configuration(root, benchmark_path=None):
    if benchmark_path is None:
        return {"enabled": False}
    helper = importlib.import_module(LOGPROB_MODULE)
    helper_path = Path(helper.__file__).resolve()
    decoder_binding = helper.optimized_decoder_class().logprob_collection_binding
    relative = "trusted_data_synthesis/scripts/" + LOGPROB_MODULE + ".py"
    require(helper_path == Path(root).resolve() / relative, "helper_from_registered_worktree")
    benchmark_path = Path(benchmark_path).resolve()
    benchmark = p.read_json(benchmark_path)
    require(
        all(
            benchmark.get("test", {}).get(key) is True
            for key in ("passed", "bit_exact", "rng_unchanged")
        )
        and benchmark.get("model_calls") == 0
        and benchmark.get("api_calls") == 0
        and benchmark.get("helper_sha256")
        == p.sha(helper_path)
        == decoder_binding["helper_source_sha256"]
        and benchmark.get("anchor_decoder_sha256")
        == p.sha(Path(previous.legacy.old.feedback.__file__))
        == decoder_binding["source_sha256"]
        and decoder_binding["all_other_AST_unchanged"] is True
        and decoder_binding["changed_assignment_count"] == 1,
        "passing_exact_helper_benchmark_without_model_or_API_calls",
    )
    return dict(
        enabled=True,
        module=LOGPROB_MODULE,
        helper_source=relative,
        helper_sha256=p.sha(helper_path),
        decoder_binding=decoder_binding,
        benchmark=recovery.reference(benchmark_path),
        benchmark_is_collector_microbenchmark_not_end_to_end_generation=True,
    )


def register(root, raw=None, logprob_benchmark=None):
    root, c = Path(root).resolve(), context(raw)
    output = c.RAW / DIRECTORY
    with c.locked(c.RAW / "control/coordinator.lock", blocking=False):
        if (output / "protocol.json").exists():
            existing = protocol(root, c.RAW)
            if logprob_benchmark is not None:
                require(
                    existing["logprob_optimization"]
                    == logprob_configuration(root, logprob_benchmark),
                    "same_registered_optional_logprob_optimization",
                )
            return existing
        original = c.read_protocol(root)
        recovered = recovery.protocol(root, c.RAW)
        require(
            not (c.RAW / "generation_seal.json").exists()
            and not (c.RAW / "complete.json").exists(),
            "register_before_global_generation_seal",
        )
        inherited = []
        for path in sorted((c.RAW / "jobspecs").glob("*.json")):
            job = p.checked(p.read_json(path), "cross_market_evaluation_work_unit")
            require(job["protocol_id"] == original["id"], "same_registered_work_unit")
            for row in previous.attempts(c, job):
                if row["alive"]:
                    inherited.append(
                        dict(
                            job_key=job["key"],
                            attempt=row["attempt"],
                            process=row["process"],
                            reserved=row["reserved"],
                            continues_original_worker_policy=True,
                        )
                    )
        optimization = logprob_configuration(root, logprob_benchmark)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        sources = {}
        for name in (
            *SOURCES,
            *((optimization["helper_source"],) if optimization["enabled"] else ()),
        ):
            payload = (root / name).read_bytes()
            require(
                payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
                "committed_operational_sources_before_registration",
            )
            sources[name] = p.sha(payload)
        value = p.record(
            PROTOCOL,
            frozen=True,
            evaluation_protocol=recovery.reference(c.RAW / "protocol.json"),
            evaluation_protocol_id=original["id"],
            cuda_recovery_protocol=recovery.reference(c.RAW / recovery.DIRECTORY / "protocol.json"),
            cuda_recovery_protocol_id=recovered["id"],
            capacity_policy=CAPACITY_POLICY,
            logprob_optimization=optimization,
            original_physical_budget=original["physical_budget"],
            original_scheduling=original["scheduling"],
            registered_budget_snapshot=copy.deepcopy(c._budget_state()),
            inherited_active_workers=inherited,
            environment=recovery.ENVIRONMENT,
            sources=sources,
            code_commit=head,
            scientific_protocol_bytes_unchanged=True,
            scientific_protocol_returned_without_identity_or_scheduling_overrides=True,
            changes_apply_to_new_workers_only=True,
            existing_workers_not_signaled_or_restarted=True,
            original_attempt_limits_and_precharges_unchanged=True,
            original_exact_cuda_failure_reclassification_retained=True,
            model_sampling_scoring_and_private_barrier_unchanged=True,
            telemetry_root=str(output / "telemetry"),
            telemetry_every_completed_sessions=16,
            telemetry_peak_counters_never_reset=True,
            new_training_updates=0,
            new_API_calls=0,
            at=p.now(),
        )
        c.write(output / "protocol.json", value)
        return value


def protocol(root, raw=None):
    root, c = Path(root).resolve(), context(raw)
    value = p.checked(p.read_json(c.RAW / DIRECTORY / "protocol.json"), PROTOCOL)
    original, recovered = c.read_protocol(root), recovery.protocol(root, c.RAW)
    require(
        value["frozen"] is True
        and value["capacity_policy"] == CAPACITY_POLICY
        and value["environment"] == recovery.ENVIRONMENT
        and recovery.checked_reference(value["evaluation_protocol"]) == original
        and value["evaluation_protocol_id"] == original["id"]
        and recovery.checked_reference(value["cuda_recovery_protocol"]) == recovered
        and value["cuda_recovery_protocol_id"] == recovered["id"]
        and value["original_physical_budget"] == original["physical_budget"]
        and value["original_scheduling"] == original["scheduling"],
        "same_frozen_science_recovery_and_operational_policy",
    )
    optimization = value["logprob_optimization"]
    require(type(optimization["enabled"]) is bool, "explicit_logprob_optimization_choice")
    expected = logprob_configuration(
        root, optimization["benchmark"]["path"] if optimization["enabled"] else None
    )
    require(optimization == expected, "same_verified_logprob_optimization")
    expected_sources = {*SOURCES}
    if optimization["enabled"]:
        expected_sources.add(optimization["helper_source"])
    require(set(value["sources"]) == expected_sources, "exact_operational_source_scope")
    for name, digest in value["sources"].items():
        require(p.sha(root / name) == digest, "frozen_operational_source:" + name)
    return value


class PerformanceContext(previous.evaluation.Context):
    def __init__(self, raw, *, operational_id):
        super().__init__(raw)
        self.operational_id = operational_id
        self._capacity_checks = 0
        self._last_capacity = None
        self.telemetry_root = (
            self.RAW
            / DIRECTORY
            / "telemetry"
            / f"{os.getpid()}_{previous.process_identity(os.getpid())}"
        )

    def telemetry(self, status, **fields):
        cuda = previous.legacy.torch.cuda
        return dict(
            operational_protocol_id=self.operational_id,
            pid=os.getpid(),
            boundary=self._capacity_checks,
            status=status,
            available_MiB=self._last_capacity,
            torch_memory_allocated_MiB=cuda.memory_allocated() / 2**20,
            torch_memory_reserved_MiB=cuda.memory_reserved() / 2**20,
            torch_peak_allocated_MiB=cuda.max_memory_allocated() / 2**20,
            torch_peak_reserved_MiB=cuda.max_memory_reserved() / 2**20,
            lifetime_peaks_not_reset=True,
            at=p.now(),
            **fields,
        )

    def record_worker_exit(self, exit_code):
        if self._capacity_checks:
            self.write(
                self.telemetry_root / "worker_exit.json",
                self.telemetry("WORKER_EXIT", exit_code=exit_code),
            )

    def capacity_boundary(self, phase, required):
        # The unchanged worker calls this once before loading the model; the
        # unchanged generation loop calls it again before each missing session.
        require(phase == "generation", "generation_capacity_boundary_only")
        self._capacity_checks += 1
        startup = self._capacity_checks == 1
        minimum = CAPACITY_POLICY[
            "start_minimum_free_MiB" if startup else "continue_minimum_available_MiB"
        ]
        maximum = 0 if startup else CAPACITY_POLICY["maximum_boundary_wait_seconds"]
        started, waited = time.monotonic(), False
        status_path = self.telemetry_root / f"boundary_{self._capacity_checks:06d}.json"
        while True:
            previous.legacy.torch.cuda.empty_cache()
            free, _ = previous.legacy.torch.cuda.mem_get_info()
            capacity = (free + previous.legacy.torch.cuda.memory_reserved()) / 2**20
            self._last_capacity = capacity
            elapsed = time.monotonic() - started
            enough = capacity >= minimum
            if enough and not waited:
                if self._capacity_checks > 1 and (self._capacity_checks - 1) % 16 == 0:
                    self.write(status_path, self.telemetry("PERIODIC_BOUNDARY"))
                return
            status = "RESUMED" if enough else "RESOURCE_RETRY" if elapsed >= maximum else "WAITING"
            self.write(
                status_path,
                self.telemetry(
                    status,
                    phase=phase,
                    startup=startup,
                    original_required_MiB=required,
                    minimum_MiB=minimum,
                    waited_seconds=elapsed,
                ),
                immutable=False,
            )
            previous.emit(
                "performance_capacity_boundary",
                status=status,
                startup=startup,
                minimum_MiB=minimum,
                available_MiB=capacity,
                waited_seconds=elapsed,
            )
            if enough:
                return
            if elapsed >= maximum:
                raise previous.legacy.CapacityWait(
                    f"{phase}: {capacity:.0f} MiB available < {minimum} MiB "
                    f"after {elapsed:.1f}s operational boundary wait"
                )
            waited = True
            time.sleep(min(CAPACITY_POLICY["boundary_poll_seconds"], maximum - elapsed))


def controller_namespace(plan, recovered):
    # Reuse the existing in-memory exceptions for the exact registered CuBLAS
    # failures; constructing a fresh controller directly would lose that scope.
    namespace = recovery.controller_namespace(recovered)
    contexts = []

    class BoundContext(PerformanceContext):
        def __init__(self, raw):
            super().__init__(raw, operational_id=plan["id"])
            if plan["logprob_optimization"]["enabled"]:
                helper = importlib.import_module(LOGPROB_MODULE)
                feedback = SimpleNamespace(**vars(self.old.feedback))
                feedback.generate_jobs = previous.evaluation._clone(
                    feedback.generate_jobs, {"Decoder": helper.optimized_decoder_class()}
                )
                self.old = SimpleNamespace(**{**vars(self.old), "feedback": feedback})
            contexts.append(self)

    def available_gpus(_original_minimum):
        return previous.available_gpus(CAPACITY_POLICY["start_minimum_free_MiB"])

    namespace.update(
        SCRIPT=SCRIPT,
        evaluation=SimpleNamespace(**{**vars(previous.evaluation), "Context": BoundContext}),
        available_gpus=available_gpus,
        performance_contexts=contexts,
    )
    return namespace


def execute(action, root, raw=None, job=None, attempt=None, logprob_benchmark=None):
    c = context(raw)
    if action == "register":
        return register(root, c.RAW, logprob_benchmark)
    if action == "status":
        return previous.read(c.RAW / "control/status.json")
    if action == "worker":
        require(
            all(os.environ.get(key) == value for key, value in recovery.ENVIRONMENT.items()),
            "real_worker_environment_before_generation",
        )
    plan = protocol(root, c.RAW)
    recovered = recovery.protocol(root, c.RAW)
    namespace = controller_namespace(plan, recovered)
    if action == "worker":
        result = namespace["worker"](Path(root).resolve(), c.RAW, job, attempt)
        for worker_context in namespace["performance_contexts"]:
            try:
                worker_context.record_worker_exit(result)
            except Exception as error:
                # The original outcome is already durable. Diagnostic failure
                # cannot reclassify a completed/failed scientific work unit.
                previous.emit("performance_telemetry_failed", error=repr(error))
        return result
    return namespace[action](Path(root).resolve(), c.RAW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=previous.RAW)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--logprob-benchmark", type=Path)
    args = parser.parse_args()
    require(
        args.logprob_benchmark is None or args.action == "register",
        "benchmark_flag_registration_only",
    )
    value = execute(
        args.action, args.root, args.raw, args.job, args.attempt, args.logprob_benchmark
    )
    if args.action == "worker":
        return value
    if value is not None:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
