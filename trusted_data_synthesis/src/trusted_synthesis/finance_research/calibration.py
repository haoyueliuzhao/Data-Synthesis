"""Bounded audit follow-up: four G diagnostics, then fixed 480-session H0/H1.

This controller never trains or changes the original QA/role plan. Any incomplete
worker stops new launches; there is no automatic generation retry.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import RunConfig, digest
from .planning import task_key, verify_role_plan
from .profiles import profile_definition
from .storage import (
    encode,
    execute_run,
    load_public_snapshot,
    prepare_run,
    read_json,
    runtime_binding,
    score_run,
)

ROOT = Path(__file__).resolve().parents[4]
CACHE = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928"
)
OLD = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_cache_20260926/evaluation_01"
)
OUTPUT = CACHE / "audit_followup_01"
MODEL_SEED = 11


def now():
    return datetime.now(timezone.utc).isoformat()


def publish(directory, value, name="record.json"):
    write_immutable_artifact_directory(directory, {name: encode(value)})


def status(directory, value):
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".status-{os.getpid()}.json"
    with temporary.open("wb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, directory / "status.json")


def identity(pid):
    try:
        data = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if data[0] == "Z" else data[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def leases():
    rows = []
    for path in sorted((CACHE / "gpu_reservation_watch_01").glob("attempt_*/reserved/record.json")):
        row = read_json(path)
        birth = identity(row["pid"])
        if birth and not (path.parent.parent / "released/record.json").exists():
            rows.append({**row, "process_identity": birth, "record": str(path)})
    return rows


def gpu_inventory():
    rows = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    apps = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    processes = {}
    for line in apps.splitlines():
        if line.strip():
            uuid, pid = line.split(",")
            processes.setdefault(uuid.strip(), []).append(int(pid))
    result = []
    for line in rows.splitlines():
        index, uuid, used, free = [x.strip() for x in line.split(",")]
        result.append(
            dict(
                index=int(index),
                uuid=uuid,
                used=int(used),
                free=int(free),
                processes=processes.get(uuid, []),
            )
        )
    return result


def release_owned_holder(gpu, plan):
    """Called only AFTER loading the model, closing the idle handoff window."""
    for lease in plan["initial_leases"]:
        if lease["gpu"] != gpu or identity(lease["pid"]) != lease["process_identity"]:
            continue
        cmd = Path(f"/proc/{lease['pid']}/cmdline").read_bytes()
        if b"reserve_finance_research_gpu_20260928.py" not in cmd:
            raise ValueError("refuse to signal a process outside this reservation")
        os.kill(lease["pid"], signal.SIGTERM)
        for _ in range(100):
            if identity(lease["pid"]) != lease["process_identity"]:
                break
            time.sleep(0.1)
        if identity(lease["pid"]) == lease["process_identity"]:
            raise RuntimeError("reservation did not exit after handoff")


def gate_prompt_length(tokenizer, messages):
    """Count actual IDs, not fields in Transformers' default BatchEncoding."""
    from .tools import TOOL_SPECS

    rendered = tokenizer.apply_chat_template(
        messages, tools=TOOL_SPECS, tokenize=False, add_generation_prompt=True
    )
    return len(
        tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)["input_ids"]
    )


def register(output=OUTPUT):
    from transformers import AutoTokenizer

    from .gpu_gate import DIAGNOSTIC_INSTRUCTION, gate_messages
    from .training_policy import training_interface_policy

    output = Path(output).resolve()
    if output.exists():
        return checked_plan(output)
    manifest, tasks, lineages = load_public_snapshot(CACHE / "snapshots/finqa")
    roles = read_json(CACHE / "roles/finqa_v1/plan.json")
    verify_role_plan(roles, tasks, lineages)
    selected = [task for task in tasks if roles["assignments"][task_key(task)] == "calibration"]
    if len(selected) != 120:
        raise ValueError("exact original 120 calibration tasks required")
    old = read_json(OLD / "protocol.json")
    point_path = OLD / "points/static_11/point.json"
    point = read_json(point_path)
    if point["run"] != {"condition": "static", "seed": 11} or point["step"] != 240:
        raise ValueError("preselected Static seed11 step240 required")
    adapter_path = point_path.parent / point["adapter"]["path"]
    if hashlib.sha256(adapter_path.read_bytes()).hexdigest() != point["adapter"]["sha256"]:
        raise ValueError("old fixed checkpoint bytes changed")
    tokenizer = AutoTokenizer.from_pretrained(
        old["materials"]["assets"]["base_binding"]["directory"],
        local_files_only=True,
        trust_remote_code=False,
    )
    lengths = []
    diagnostic = DIAGNOSTIC_INSTRUCTION
    gate_config = RunConfig(
        submission_profile="finqa_program_v1", temperature=1, max_new_tokens=256, role="calibration"
    )
    for task in selected:
        messages, _ = gate_messages(task, gate_config)
        lengths.append((gate_prompt_length(tokenizer, messages), task))
    admissible = [(length, task) for length, task in lengths if length + 2048 <= 24576]
    if not admissible:
        raise ValueError("no calibration context fits unchanged generation budget")
    ordered = sorted(admissible, key=lambda row: (row[0], task_key(row[1])))
    gate_rows = [ordered[0], ordered[-1]]
    jobs = []
    for model in ("base", "static11_step240"):
        for harness in ("H0", "H1"):
            config = RunConfig(
                harness_id="fixed-kernel-finqa-compat-v1"
                if harness == "H0"
                else "bigfinance-derived-vtdo-v2",
                local_tool_protocol="legacy-json-v1"
                if harness == "H0"
                else "qwen2.5-native-tool-call-v1",
                submission_profile="finqa_program_v1",
                temperature=0,
                role="calibration",
            )
            for start in range(0, 120, 30):
                jobs.append(
                    dict(
                        key=f"{model}_{harness}_{start:03d}",
                        model=model,
                        harness=harness,
                        config=config.model_dump(mode="json"),
                        task_keys=[task_key(task) for task in selected[start : start + 30]],
                    )
                )
    jobs.sort(key=lambda job: (int(job["key"].rsplit("_", 1)[1]), job["model"], job["harness"]))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        relative = str(path.relative_to(ROOT))
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", head + ":" + relative], cwd=ROOT
        ):
            raise ValueError("commit research source before registering real generation")
    plan = dict(
        schema="finance_harness_audit_followup.v1",
        at=now(),
        authorization="参照审计修订并开展后续实验；当前有空闲，先抢占几张",
        snapshot=str(CACHE / "snapshots/finqa"),
        snapshot_id=manifest["id"],
        role_plan=roles,
        calibration_tasks=[task_key(task) for task in selected],
        denominator=480,
        jobs=jobs,
        greedy_comparison=True,
        max_generate_calls_H=15360,
        max_generate_calls_G=4,
        maximum_worker_attempts=1,
        maximum_GPU_workers=4,
        initial_leases=leases(),
        assets=old["materials"]["assets"],
        static_point=point,
        static_adapter_path=str(adapter_path),
        checkpoint_choice="lowest preregistered seed11 Static step240, not selected using results",
        gate_tasks=[task.model_dump(mode="json") for _, task in gate_rows],
        gate_prompt_lengths=[n for n, _ in gate_rows],
        gate_diagnostic_instruction=diagnostic,
        gate_config=gate_config.model_dump(mode="json"),
        diagnostic_virtual=dict(
            lr=1e-5, gradient=1e-4, betas=[0.9, 0.999], eps=1e-8, weight_decay=0.0
        ),
        gate_virtual_is_diagnostic_not_population_G=True,
        submission_profile=profile_definition(),
        training_interface_policy=training_interface_policy(),
        runtime_binding=runtime_binding(),
        code_commit=head,
        no_new_training_or_material_collection=True,
        API_model="deepseek-flash",
        API_calls=0,
        all_480_generation_and_workers_exit_before_private_scoring=True,
    )
    plan["id"] = digest(plan)
    publish(output, plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = read_json(Path(output) / "protocol.json")
    if (
        plan["id"] != digest({k: v for k, v in plan.items() if k != "id"})
        or plan["runtime_binding"] != runtime_binding()
    ):
        raise ValueError("frozen follow-up protocol/runtime changed")
    return plan


def load_provider(plan, job, gpu):
    from transformers import AutoTokenizer

    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as existing

    from .providers import LocalTorchProvider, local_model_identity

    static = job["model"] == "static11_step240"
    model, _ = existing.load_student(
        plan["assets"]["base_binding"],
        MODEL_SEED,
        trainable=True,
        adapter_path=Path(plan["static_adapter_path"]) if static else None,
        adapter_record=plan["static_point"]["adapter"] if static else None,
    )
    model.eval()
    release_owned_holder(gpu, plan)
    tokenizer = AutoTokenizer.from_pretrained(
        plan["assets"]["base_binding"]["directory"], local_files_only=True, trust_remote_code=False
    )
    bound = local_model_identity(
        model,
        tokenizer,
        model_id=plan["assets"]["base_binding"]["id"],
        point_id=plan["static_point"]["id"] if static else "base-zero-LoRA-seed11",
    )
    return LocalTorchProvider(model, tokenizer, bound)


def worker(output, key, attempt, gpu):
    output = Path(output)
    plan = checked_plan(output)
    runroot = output / "jobs" / key
    attemptdir = runroot / "attempts" / f"{attempt:02d}"
    publish(
        attemptdir / "started",
        dict(pid=os.getpid(), process_identity=identity(os.getpid()), gpu=gpu, at=now()),
    )
    outcome = None
    try:
        if key == "G":
            from .gpu_gate import run_gate

            report = asyncio.run(
                run_gate(
                    plan, output / "gate", ready_callback=lambda: release_owned_holder(gpu, plan)
                )
            )
            publish(output / "gate_complete", report)
            outcome = dict(status="COMPLETE", eval_native_passed=report["eval_native_passed"])
        else:
            gate = read_json(output / "gate_complete/record.json")
            if not gate["eval_native_passed"]:
                raise ValueError("ordinary execution gate not passed")
            job = next(job for job in plan["jobs"] if job["key"] == key)
            provider = load_provider(plan, job, gpu)
            directory = runroot / "generation"
            if not directory.exists():
                prepare_run(
                    plan["snapshot"],
                    plan["role_plan"],
                    directory,
                    role="calibration",
                    config=RunConfig.model_validate(job["config"]),
                    identity=provider.identity,
                    task_keys=job["task_keys"],
                )
            seal = asyncio.run(execute_run(directory, provider))
            outcome = dict(status="COMPLETE", generation_seal_id=seal["id"])
    except BaseException as error:
        import traceback

        traceback.print_exc()
        outcome = dict(status="BLOCKED", exception_type=type(error).__name__, message=str(error))
    publish(attemptdir / "outcome", {**outcome, "at": now()})
    return 0 if outcome["status"] == "COMPLETE" else 1


def latest(output, key):
    directories = sorted((output / "jobs" / key / "attempts").glob("*"))
    if not directories:
        return None
    directory = directories[-1]
    start = (
        read_json(directory / "started/record.json")
        if (directory / "started/record.json").exists()
        else None
    )
    launched = (
        read_json(directory / "launched/record.json")
        if (directory / "launched/record.json").exists()
        else None
    )
    process = start or launched
    birth = identity(process["pid"]) if process is not None else None
    alive = bool(birth and birth == process["process_identity"])
    outcome = (
        read_json(directory / "outcome/record.json")
        if (directory / "outcome/record.json").exists()
        else None
    )
    return dict(attempt=int(directory.name), alive=alive, process=process, outcome=outcome)


def launch(output, key, attempt, gpu):
    path = output / "logs" / f"{key}_{attempt:02d}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": gpu,
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "1",
    }
    with path.open("ab") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "trusted_synthesis.finance_research.calibration",
                "worker",
                "--output",
                str(output),
                "--key",
                key,
                "--attempt",
                str(attempt),
                "--gpu",
                gpu,
            ],
            cwd=ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    publish(
        output / "jobs" / key / "attempts" / f"{attempt:02d}" / "launched",
        dict(pid=proc.pid, process_identity=identity(proc.pid), gpu=gpu, at=now()),
    )


def coordinate(output):
    output = Path(output)
    plan = checked_plan(output)
    with (output / "coordinator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            keys = ["G"] + [job["key"] for job in plan["jobs"]]
            states = {key: latest(output, key) for key in keys}
            active = {key: row for key, row in states.items() if row and row["alive"]}
            blocked = [
                key
                for key, row in states.items()
                if row
                and not row["alive"]
                and (row["outcome"] is None or row["outcome"]["status"] != "COMPLETE")
            ]
            gate = (
                read_json(output / "gate_complete/record.json")
                if (output / "gate_complete/record.json").exists()
                else None
            )
            if gate is not None and not gate["eval_native_passed"]:
                blocked.append("G_EVAL_NATIVE_FAILED")
            eligible = (
                [job["key"] for job in plan["jobs"]]
                if gate and gate["eval_native_passed"]
                else ["G"]
            )
            used = {row["process"]["gpu"] for row in active.values()}
            own = {
                lease["gpu"]: lease
                for lease in plan["initial_leases"]
                if identity(lease["pid"]) == lease["process_identity"]
            }
            available = []
            for row in gpu_inventory():
                held = own.get(row["uuid"])
                holder_ok = held and set(row["processes"]) == {held["pid"]}
                idle = not row["processes"] and row["used"] <= 1024 and row["free"] >= 49152
                if row["uuid"] not in used and (holder_ok or idle):
                    available.append(row["uuid"])
            if not blocked:
                for key in eligible:
                    if states[key] is not None:
                        continue
                    if not available or len(active) >= 4:
                        break
                    gpu = available.pop(0)
                    launch(output, key, 1, gpu)
                    active[key] = dict(process={"gpu": gpu})
            completed = sum(
                bool(
                    states[key]
                    and states[key]["outcome"]
                    and states[key]["outcome"]["status"] == "COMPLETE"
                )
                for key in keys[1:]
            )
            status(
                output,
                dict(
                    at=now(),
                    protocol_id=plan["id"],
                    phase="H" if gate else "G",
                    active_workers=len(active),
                    H_shards_complete=completed,
                    H_shards=16,
                    blocked=blocked,
                    gate=gate,
                    waiting_for_GPU=not active and not available and not blocked,
                ),
            )
            if blocked:
                return
            if completed == 16 and not active:
                publish(
                    output / "generation_seal",
                    dict(
                        protocol_id=plan["id"],
                        complete=True,
                        denominator=480,
                        all_workers_exited=True,
                        at=now(),
                    ),
                )
                reports = []
                for job in plan["jobs"]:
                    result = score_run(
                        output / "jobs" / job["key"] / "generation", output / "scoring" / job["key"]
                    )
                    reports.append(
                        dict(
                            job_key=job["key"],
                            model=job["model"],
                            harness=job["harness"],
                            report=result,
                        )
                    )
                publish(
                    output / "complete",
                    dict(
                        protocol_id=plan["id"],
                        at=now(),
                        complete=True,
                        comparison="harness interface/migration, not VTDO training value",
                        reports=reports,
                    ),
                )
                status(
                    output,
                    dict(at=now(), phase="COMPLETE", active_workers=0, denominator=480, blocked=[]),
                )
                return
            time.sleep(5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--key")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--gpu")
    args = parser.parse_args(argv)
    if args.action == "register":
        print(json.dumps({"id": register(args.output)["id"]}))
    elif args.action == "worker":
        return worker(args.output, args.key, args.attempt, args.gpu)
    elif args.action == "coordinate":
        coordinate(args.output)
    elif args.action == "status":
        print(json.dumps(read_json(args.output / "status.json")))
    else:
        checked_plan(args.output)
        with (args.output / "coordinator.log").open("ab") as log:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "trusted_synthesis.finance_research.calibration",
                    "coordinate",
                    "--output",
                    str(args.output),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(json.dumps(dict(pid=proc.pid, process_identity=identity(proc.pid), at=now())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
