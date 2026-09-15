"""External evaluation-only admission; frozen generation and training stay unchanged."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import FunctionType, SimpleNamespace

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import parallel_study as s
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

MINIMUM_FREE_MIB = 77824
PREVIOUS_COORDINATOR_PID = 3381543


def validate_resource_tracker(observed):
    expected = [sys.executable, "-c", "from multiprocessing.resource_tracker import main;main(3)"]
    p.require(
        observed["pid"] == 3408891
        and observed["ppid"] == PREVIOUS_COORDINATOR_PID
        and observed["state"] in ("R", "S", "D")
        and observed["cmdline_sha256"]
        == p.sha(b"\0".join(arg.encode() for arg in expected) + b"\0"),
        "evaluation_admission.only_observed_standard_resource_tracker",
    )


def query_gpu_snapshot():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    rows = []
    for line in raw.splitlines():
        index, uuid, free, utilization = [item.strip() for item in line.split(",")]
        rows.append(
            dict(
                index=int(index),
                uuid=uuid,
                free_memory_MiB=int(free),
                utilization_percent=int(utilization),
            )
        )
    return rows


def eligible_devices(rows, wanted, used=()):
    wanted, used = list(wanted), set(used)
    p.require(
        len(wanted) == len(set(wanted)) == 8
        and all(isinstance(uuid, str) and uuid.startswith("GPU-") for uuid in wanted),
        "evaluation_admission.exact_eight_unique_GPUs",
    )
    p.require(
        len({row["uuid"] for row in rows}) == len(rows)
        and len({row["index"] for row in rows}) == len(rows),
        "evaluation_admission.unique_snapshot_GPUs",
    )
    for row in rows:
        p.require(
            type(row["index"]) is int
            and row["index"] >= 0
            and isinstance(row["uuid"], str)
            and row["uuid"].startswith("GPU-")
            and type(row["free_memory_MiB"]) is int
            and row["free_memory_MiB"] >= 0
            and type(row["utilization_percent"]) is int
            and 0 <= row["utilization_percent"] <= 100,
            "evaluation_admission.valid_observation",
        )
    return sorted(
        (
            row
            for row in rows
            if row["uuid"] in wanted
            and row["uuid"] not in used
            and row["free_memory_MiB"] >= MINIMUM_FREE_MIB
        ),
        key=lambda row: row["index"],
    )


def _wanted(frozen):
    return [row["gpu"]["uuid"] for row in frozen["parent_workers"]]


def _boundary(root):
    output = root / s.OUTPUT
    pending = x.jobs_for("A_dev")[-1]
    forbidden = [
        output / name
        for name in (
            "decision.json",
            "report.json",
            "manifest.json",
            "execution_failure.json",
            "parallel_handoff_failure.json",
            "jobs/A_dev/report.json",
        )
    ]
    forbidden += [
        output / "jobs/A_dev" / (x.job_name(pending) + "_job.json"),
        x.job_output(root, {"output_directory": s.OUTPUT}, pending),
    ]
    p.require(
        not any(path.exists() for path in forbidden),
        "evaluation_admission.only_before_ninth_generation_or_scoring",
    )


def capture(root, frozen):
    """Read one exact live/stopped scheduler boundary, without signals or writes."""
    root = Path(root).resolve()
    _boundary(root)
    launch, launch_ref = x._source_record(
        root, s.RUNTIME + "/shared_gpu_coordinator_launch.json", "shared_GPU_coordinator_launch"
    )
    coordinator = s.process_observation(PREVIOUS_COORDINATOR_PID)
    p.require(
        launch["pid"] == coordinator["pid"] == PREVIOUS_COORDINATOR_PID
        and coordinator["pid"] != os.getpid()
        and launch["execution_freeze_id"] == frozen["id"]
        and coordinator["state"] in ("S", "R", "D", "T", "t")
        and coordinator["cmdline_sha256"]
        == p.sha(b"\0".join(arg.encode() for arg in launch["argv"]) + b"\0"),
        "evaluation_admission.original_coordinator_exact_identity",
    )
    directory = root / s.OUTPUT / "jobs/A_dev"
    registry, registry_ref = x._source_record(root, directory / "registry.json", "worker_registry")
    jobs = x.jobs_for("A_dev")
    p.require(
        registry["execution_freeze_id"] == frozen["id"]
        and registry["phase"] == "A_dev"
        and registry["jobs"] == jobs,
        "evaluation_admission.original_nine_job_registry",
    )
    paths = {directory / (x.job_name(job) + "_job.json"): job for job in jobs[:-1]}
    actual = set(directory.glob("*_job.json"))
    p.require(actual == set(paths), "evaluation_admission.exact_eight_existing_requests")
    children_path = (
        Path("/proc")
        / str(PREVIOUS_COORDINATOR_PID)
        / "task"
        / str(PREVIOUS_COORDINATOR_PID)
        / "children"
    )
    children = [int(value) for value in children_path.read_text().split()]
    p.require(len(children) in (8, 9), "evaluation_admission.workers_and_optional_bound_tracker")
    # A zombie has no cmdline: the durable worker_started log binds its PID to its job.
    launch_log = root / s.RUNTIME / "shared_gpu_coordinator.log"
    launches = {}
    for line in launch_log.read_text().splitlines():
        if not line.startswith("{"):
            continue
        value = json.loads(line)
        if value.get("event") == "worker_started":
            launches[value["pid"]] = value
    workers, auxiliary = [], []
    for pid in children:
        observed = s.process_observation(pid)
        p.require(
            observed["ppid"] == PREVIOUS_COORDINATOR_PID
            and observed["state"] in ("S", "R", "D", "Z"),
            "evaluation_admission.original_child_state",
        )
        if pid == 3408891:
            validate_resource_tracker(observed)
            auxiliary.append(observed)
            continue
        started = launches.get(pid)
        p.require(started is not None, "evaluation_admission.logged_original_child")
        job_path = directory / (started["job"] + "_job.json")
        p.require(job_path in paths, "evaluation_admission.child_is_registered_development_job")
        job = paths[job_path]
        supplied, reference = x._source_record(root, job_path, "worker_job")
        p.require(
            supplied["job"] == job
            and supplied["execution_freeze_id"] == frozen["id"]
            and supplied["code_binding"] == frozen["code_binding"]
            and supplied["gpu"]["uuid"] == started["gpu"]["uuid"]
            and supplied["gpu"]["uuid"] in _wanted(frozen),
            "evaluation_admission.exact_original_job_binding",
        )
        if observed["state"] != "Z":
            expected = [
                sys.executable,
                "-m",
                x.__package__ + ".execution",
                "worker",
                "--root",
                str(root),
                "--job",
                str(job_path),
            ]
            p.require(
                observed["cmdline_sha256"]
                == p.sha(b"\0".join(arg.encode() for arg in expected) + b"\0"),
                "evaluation_admission.original_child_exact_command",
            )
        else:
            validate_original_exit(observed, observed)
        workers.append(
            dict(
                job=job,
                gpu=supplied["gpu"],
                process=observed,
                supplied_job_id=supplied["id"],
                job_path=str(job_path.relative_to(root)),
                job_descriptor=reference,
            )
        )
    p.require(
        {x.job_name(row["job"]) for row in workers} == {x.job_name(job) for job in jobs[:-1]}
        and len({row["gpu"]["uuid"] for row in workers}) == 8,
        "evaluation_admission.one_existing_worker_per_original_GPU",
    )
    return dict(
        coordinator=coordinator,
        adopted_workers=workers,
        auxiliary_children=auxiliary,
        previous_launch_id=launch["id"],
        previous_launch_descriptor=launch_ref,
        registry_id=registry["id"],
        registry_descriptor=registry_ref,
        execution_freeze_id=frozen["id"],
        observed_at=p.now(),
    )


def validate_original_exit(bound, observation):
    p.require(
        observation["pid"] == bound["pid"]
        and observation.get("start_ticks") == bound["start_ticks"]
        and observation.get("ppid") == bound["ppid"] == PREVIOUS_COORDINATOR_PID
        and observation["state"] == "Z"
        and observation.get("exit_status_provable") is True
        and observation.get("return_code") == 0,
        "evaluation_admission.actual_original_child_exit_zero_required",
    )
    return observation


def _stopped(coordinator):
    observed = s.process_observation(coordinator["pid"], start_ticks=coordinator["start_ticks"])
    p.require(
        coordinator["pid"] == PREVIOUS_COORDINATOR_PID
        and coordinator["pid"] != os.getpid()
        and observed["state"] in ("T", "t")
        and observed["cmdline_sha256"] == coordinator["cmdline_sha256"],
        "evaluation_admission.original_coordinator_remains_stopped",
    )
    return observed


def validate_handoff(root, frozen, handoff):
    p.checked(handoff, "evaluation_resource_handoff")
    p.require(
        handoff["execution_freeze_id"] == frozen["id"]
        and handoff["signaled_pids"] == [PREVIOUS_COORDINATOR_PID]
        and handoff["training_or_generation_workers_signaled"] is False
        and handoff["publisher_signaled"] is False,
        "evaluation_admission.handoff_exact_freeze",
    )
    _stopped(handoff["coordinator"])
    current = capture(root, frozen)
    p.require(
        [
            {key: row[key] for key in ("pid", "start_ticks", "cmdline_sha256")}
            for row in current["auxiliary_children"]
        ]
        == [
            {key: row[key] for key in ("pid", "start_ticks", "cmdline_sha256")}
            for row in handoff["auxiliary_children"]
        ],
        "evaluation_admission.unchanged_standard_auxiliary_child",
    )
    p.require(
        current["registry_id"] == handoff["registry_id"]
        and current["previous_launch_id"] == handoff["previous_launch_id"]
        and current["coordinator"]["start_ticks"] == handoff["coordinator"]["start_ticks"],
        "evaluation_admission.handoff_exact_scheduler_registry",
    )
    old = {row["process"]["pid"]: row for row in handoff["adopted_workers"]}
    p.require(len(old) == 8, "evaluation_admission.handoff_eight_distinct_PIDs")
    for row in current["adopted_workers"]:
        bound = old.get(row["process"]["pid"])
        p.require(
            bound is not None
            and row["process"]["start_ticks"] == bound["process"]["start_ticks"]
            and row["supplied_job_id"] == bound["supplied_job_id"]
            and row["job_descriptor"] == bound["job_descriptor"]
            and row["job"] == bound["job"]
            and row["gpu"] == bound["gpu"],
            "evaluation_admission.handoff_original_workers_unchanged",
        )
    return current


def _amendment(amendment):
    p.checked(amendment, "evaluation_resource_admission_amendment")
    p.require(
        amendment["minimum_free_GPU_memory_MiB"] == MINIMUM_FREE_MIB
        and amendment["GPU_utilization_is_launch_condition"] is False
        and amendment["scopes"] == ["A_dev", "confirm"],
        "evaluation_admission.only_registered_generation_phases",
    )


def _completed_generation(root, frozen, row):
    supplied, reference = x._source_record(root, row["job_path"], "worker_job")
    p.require(
        supplied["id"] == row["supplied_job_id"] and reference == row["job_descriptor"],
        "evaluation_admission.original_request_bytes_unchanged",
    )
    output = x.job_output(root, frozen, row["job"])
    report = p.checked(p.read_json(output / "report.json"), "generation_report")
    manifest = p.checked(p.read_json(output / "manifest.json"), "evaluation_manifest")
    identity = supplied["public_generation_input"]["model_identity"]
    p.require(
        report["actual_complete"] is True
        and report["status"] == "COMPLETE_FIXED_GENERATION"
        and report["complete_registered_denominator"] is True
        and report["model_identity_id"] == identity["id"]
        and report["split"] == row["job"]["split"]
        and report["completed_task_count"]
        == report["requested_task_count"]
        == len(frozen["evaluation_registry"][row["job"]["split"]])
        and manifest["report_id"] == report["id"]
        and manifest["phase"] == "public_generation",
        "evaluation_admission.actual_complete_original_generation",
    )
    return report["id"]


def _admission(root, frozen, phase, job, gpu, pid, amendment):
    p.write_once(
        root / s.OUTPUT / "evaluation_gpu_admissions" / (x.job_name(job) + ".json"),
        p.record(
            "evaluation_GPU_admission",
            at=p.now(),
            phase=phase,
            job=job,
            gpu=gpu,
            pid=pid,
            execution_freeze_id=frozen["id"],
            resource_admission_amendment_id=amendment["id"],
            minimum_free_GPU_memory_MiB=MINIMUM_FREE_MIB,
            GPU_utilization_is_launch_condition=False,
            actual_process_spawned=True,
            snapshot_is_not_a_memory_reservation=True,
        ),
    )


def _spawn(root, frozen, phase, job, gpu, amendment):
    directory = root / s.OUTPUT / "jobs" / phase
    name = x.job_name(job)
    path = directory / (name + "_job.json")
    supplied = p.record(
        "worker_job",
        job=job,
        gpu=gpu,
        code_binding=frozen["code_binding"],
        execution_freeze_id=frozen["id"],
        launched_at=p.now(),
        public_generation_input=x.public_generation_input(root, frozen, job),
    )
    p.write_once(path, supplied)
    env = dict(os.environ)
    env.update(x.execution_policy()["worker_environment"])
    env["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
    env["PYTHONPATH"] = os.pathsep.join(
        str(x.code_root() / value)
        for value in ("raw_financial_data_lake", "trusted_data_synthesis/src")
    )
    log = (directory / (name + ".log")).open("xb")
    command = [
        sys.executable,
        "-m",
        x.__package__ + ".execution",
        "worker",
        "--root",
        str(root),
        "--job",
        str(path),
    ]
    try:
        process = subprocess.Popen(
            command, cwd=x.code_root(), env=env, stdout=log, stderr=subprocess.STDOUT
        )
    except BaseException:
        log.close()
        raise
    _admission(root, frozen, phase, job, gpu, process.pid, amendment)
    print(
        p.encode(
            dict(event="worker_started", job=name, pid=process.pid, gpu=gpu, at=p.now())
        ).decode(),
        flush=True,
    )
    return dict(
        job=job,
        gpu=gpu,
        process=process,
        log=log,
        supplied_job_id=supplied["id"],
        job_path=str(path.relative_to(root)),
        job_descriptor=dict(
            path=str(path.relative_to(root)),
            bytes=len(p.encode(supplied)),
            sha256=p.sha(p.encode(supplied)),
        ),
    )


def _retire(root, handoff, exits):
    coordinator = handoff["coordinator"]
    p.require(
        len(exits) == 8
        and len({row["job"]["arm"] + str(row["job"]["seed"]) for row in exits}) == 8,
        "evaluation_admission.all_eight_original_exits_recorded_before_retirement",
    )
    for row in handoff["adopted_workers"]:
        validate_original_exit(
            row["process"],
            s.process_observation(row["process"]["pid"], start_ticks=row["process"]["start_ticks"]),
        )
    _stopped(coordinator)
    children = (
        Path("/proc") / str(coordinator["pid"]) / "task" / str(coordinator["pid"]) / "children"
    )
    p.require(
        {int(value) for value in children.read_text().split()}
        == {row["process"]["pid"] for row in handoff["adopted_workers"]}
        | {row["pid"] for row in handoff["auxiliary_children"]},
        "evaluation_admission.only_completed_workers_and_bound_tracker_before_retirement",
    )
    for auxiliary in handoff["auxiliary_children"]:
        observed_auxiliary = s.process_observation(
            auxiliary["pid"], start_ticks=auxiliary["start_ticks"]
        )
        p.require(
            observed_auxiliary["ppid"] == PREVIOUS_COORDINATOR_PID
            and (
                observed_auxiliary["state"] == "Z"
                or observed_auxiliary.get("cmdline_sha256") == auxiliary["cmdline_sha256"]
            ),
            "evaluation_admission.same_auxiliary_not_a_signal_target",
        )
    # This deployment's Python has no os.pidfd_open. A stopped process keeps
    # its PID; recheck the captured start time/command immediately per signal.
    _stopped(coordinator)
    os.kill(coordinator["pid"], signal.SIGTERM)
    _stopped(coordinator)
    os.kill(coordinator["pid"], signal.SIGCONT)
    deadline = time.monotonic() + 10
    observed = s.process_observation(coordinator["pid"], start_ticks=coordinator["start_ticks"])
    while observed["state"] not in ("Z", "X", "gone") and time.monotonic() < deadline:
        time.sleep(0.1)
        observed = s.process_observation(coordinator["pid"], start_ticks=coordinator["start_ticks"])
    receipt = p.record(
        "evaluation_parent_coordinator_retired",
        at=p.now(),
        coordinator=coordinator,
        observation=observed,
        signaled_pids=[coordinator["pid"]],
        original_workers_signaled=False,
        auxiliary_children_signaled=False,
        completed_original_exit_ids=[row["id"] for row in exits],
        status="RETIRED" if observed["state"] in ("Z", "X", "gone") else "RETIREMENT_NOT_CONFIRMED",
    )
    p.write_once(root / s.OUTPUT / "evaluation_parent_coordinator_retired.json", receipt)
    p.require(
        receipt["status"] == "RETIRED",
        "evaluation_admission.actual_original_coordinator_retirement",
    )


def run_adopted_Adev(root, frozen, handoff, amendment):
    root = Path(root).resolve()
    _amendment(amendment)
    directory = root / s.OUTPUT / "jobs/A_dev"
    jobs = x.jobs_for("A_dev")
    pending, running = list(jobs[-1:]), {}
    adopted = {x.job_name(row["job"]): row for row in handoff["adopted_workers"]}
    original_exits, finished, failures, retired = [], [], [], False
    while pending or adopted or running:
        if not retired:
            _stopped(handoff["coordinator"])
        for name, row in list(adopted.items()):
            observed = s.process_observation(
                row["process"]["pid"], start_ticks=row["process"]["start_ticks"]
            )
            if observed["state"] in ("R", "S", "D"):
                p.require(
                    observed["ppid"] == PREVIOUS_COORDINATOR_PID
                    and observed["cmdline_sha256"] == row["process"]["cmdline_sha256"],
                    "evaluation_admission.live_original_child_identity",
                )
                continue
            validate_original_exit(row["process"], observed)
            report_id = _completed_generation(root, frozen, row)
            result = p.record(
                "worker_exit",
                job=row["job"],
                return_code=0,
                gpu=row["gpu"],
                finished_at=p.now(),
                original_exit_observation=observed,
                generation_report_id=report_id,
                adopted_existing_process=True,
                resource_admission_amendment_id=amendment["id"],
            )
            p.write_once(directory / (name + "_exit.json"), result)
            original_exits.append(result)
            finished.append(result)
            del adopted[name]
        if not adopted and not retired:
            _retire(root, handoff, original_exits)
            retired = True
        for name, row in list(running.items()):
            code = row["process"].poll()
            if code is None:
                continue
            row["log"].close()
            report_id = _completed_generation(root, frozen, row) if code == 0 else None
            result = p.record(
                "worker_exit",
                job=row["job"],
                return_code=code,
                gpu=row["gpu"],
                finished_at=p.now(),
                generation_report_id=report_id,
                resource_admission_amendment_id=amendment["id"],
            )
            p.write_once(directory / (name + "_exit.json"), result)
            (finished if code == 0 else failures).append(result)
            del running[name]
        if pending and not failures:
            used = {row["gpu"]["uuid"] for row in [*adopted.values(), *running.values()]}
            free = eligible_devices(query_gpu_snapshot(), _wanted(frozen), used)
            while pending and free and len(adopted) + len(running) < 8:
                job, gpu = pending.pop(0), free.pop(0)
                row = _spawn(root, frozen, "A_dev", job, gpu, amendment)
                running[x.job_name(job)] = row
        if failures and not running and not adopted:
            break
        if pending or adopted or running:
            time.sleep(10)
    result = p.record(
        "worker_phase_report",
        phase="A_dev",
        execution_freeze_id=frozen["id"],
        status="COMPLETE_FIXED_WORKERS" if not failures and not pending else "STOP_WORKER_FAILURE",
        planned=len(jobs),
        finished=finished,
        failures=failures,
        not_started=pending,
        retries=0,
        partial_output_reused=False,
        adopted_existing_processes=8,
        original_workers_restarted=False,
        resource_admission_amendment_id=amendment["id"],
    )
    p.write_once(directory / "report.json", result)
    p.require(result["status"] == "COMPLETE_FIXED_WORKERS", "execution.worker_failure_no_retry")
    return result


def run_new_phase(root, frozen, phase, *, selected, amendment):
    """Run unchanged future confirmation scheduling bytecode with admission substituted."""
    root = Path(root).resolve()
    _amendment(amendment)
    p.require(phase == "confirm", "evaluation_admission.future_confirmation_only")

    def available():
        return eligible_devices(query_gpu_snapshot(), _wanted(frozen))

    def spawn(command, **kwargs):
        process = subprocess.Popen(command, **kwargs)
        supplied = p.checked(p.read_json(command[command.index("--job") + 1]), "worker_job")
        _admission(root, frozen, phase, supplied["job"], supplied["gpu"], process.pid, amendment)
        return process

    namespace = dict(x.run_jobs.__globals__)
    namespace.update(
        available_gpus=available, subprocess=SimpleNamespace(Popen=spawn, STDOUT=subprocess.STDOUT)
    )
    runner = FunctionType(
        x.run_jobs.__code__,
        namespace,
        x.run_jobs.__name__,
        x.run_jobs.__defaults__,
        x.run_jobs.__closure__,
    )
    runner.__kwdefaults__ = x.run_jobs.__kwdefaults__
    return runner(root, frozen, phase, selected=selected)
