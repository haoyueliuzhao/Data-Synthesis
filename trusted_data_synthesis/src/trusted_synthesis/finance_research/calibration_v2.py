"""R2/G2/H2: visible-reference development retest versus one-shot Direct-DSL.

No new H0, material collection or training. Four synthetic G2 cases consume at
most 16 new generations; 240 H1-R + 240 Direct-DSL cases consume at most 7920.
Unknown executions stop new shard launches, never silently resample a task.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .calibration import (
    CACHE,
    ROOT,
    gpu_inventory,
    identity,
    latest,
    load_provider,
    now,
    publish,
    release_owned_holder,
    status,
)
from .contracts import RunConfig, digest
from .planning import task_key, verify_role_plan
from .profiles import profile_definition
from .storage import (
    execute_run,
    load_public_snapshot,
    prepare_run,
    read_json,
    runtime_binding,
    score_run,
)

PREVIOUS = CACHE / "audit_followup_01"
OUTPUT = CACHE / "reference_revision_01"
CPU_EVIDENCE = CACHE / "r2_preparation_20260928/cpu_controls.xml"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/25afac43-31f2-4c5b-9812-65cbec6f95ee/已粘贴的文本.txt"
)


def cpu_admission(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    document = ET.fromstring(raw)
    cases = list(document.iter("testcase"))
    failures = list(document.iter("failure")) + list(document.iter("error"))
    skipped = list(document.iter("skipped"))
    if not cases or failures or skipped:
        raise ValueError("R2 requires executed CPU controls with no failure/error/skip")
    if not any("test_finance_research_r2" in x.get("classname", "") for x in cases):
        raise ValueError("actual-template R2 controls missing from evidence")
    sources = {}
    for test in sorted((ROOT / "trusted_data_synthesis/tests").glob("test_finance_research_*.py")):
        if any(test.stem in x.get("classname", "") for x in cases):
            sources[str(test.relative_to(ROOT))] = hashlib.sha256(test.read_bytes()).hexdigest()
    return dict(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        test_cases=len(cases),
        failures=0,
        errors=0,
        skipped=0,
        tests=sources,
        meaning="scripted/CPU protocol controls, not actual model success or financial scores",
    )


def build_jobs(tasks):
    if len(tasks) != len(set(tasks)) or len(tasks) != 120:
        raise ValueError("the exact 120 unique development calibration tasks are required")
    jobs = []
    for start in range(0, 120, 30):
        for model in ("base", "static11_step240"):
            for harness in ("Direct-DSL", "H1-R"):
                direct = harness == "Direct-DSL"
                config = RunConfig(
                    harness_id="finqa-direct-dsl-v1" if direct else "bigfinance-derived-vtdo-v3",
                    local_tool_protocol="direct-json-v1"
                    if direct
                    else "qwen2.5-native-tool-call-v1",
                    submission_profile="finqa_program_v2",
                    role="calibration",
                    temperature=0,
                    max_steps=1 if direct else 32,
                    max_new_tokens=2048,
                    context_limit=24576,
                )
                jobs.append(
                    dict(
                        key=f"{model}_{harness}_{start:03d}",
                        model=model,
                        harness=harness,
                        config=config.model_dump(mode="json"),
                        task_keys=tasks[start : start + 30],
                    )
                )
    if sum(len(j["task_keys"]) * j["config"]["max_steps"] for j in jobs) != 7920:
        raise ValueError("fixed H2 generation budget changed")
    return jobs


def register(output=OUTPUT, cpu_evidence=CPU_EVIDENCE):
    from .gpu_gate_v2 import synthetic_gate_cases

    output = Path(output).resolve()
    if (output / "protocol.json").exists():
        return checked_plan(output)
    if output.exists():
        raise ValueError("new immutable registration directory must not already exist")
    previous = read_json(PREVIOUS / "protocol.json")
    old_completion = read_json(PREVIOUS / "complete/record.json")
    if not old_completion["complete"] or old_completion["protocol_id"] != previous["id"]:
        raise ValueError("prior study not sealed complete")
    manifest, tasks, lineages = load_public_snapshot(previous["snapshot"])
    verify_role_plan(previous["role_plan"], tasks, lineages)
    roster = [
        task_key(t)
        for t in tasks
        if previous["role_plan"]["assignments"][task_key(t)] == "calibration"
    ]
    if manifest["id"] != previous["snapshot_id"] or roster != previous["calibration_tasks"]:
        raise ValueError("do not replace the original QA snapshot or 120-task roster")
    adapter = Path(previous["static_adapter_path"])
    if (
        hashlib.sha256(adapter.read_bytes()).hexdigest()
        != previous["static_point"]["adapter"]["sha256"]
    ):
        raise ValueError("fixed old Static checkpoint changed")
    admission = cpu_admission(cpu_evidence)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    sources = list(Path(__file__).parent.rglob("*.py"))
    sources += [ROOT / name for name in admission["tests"]]
    for path in sources:
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
        ):
            raise ValueError("commit source and executed controls before real-call registration")
    plan = dict(
        schema="finance_reference_development_retest.v1",
        at=now(),
        authorization="参照审计修订并开展后续实验；R2/G2/H2 only, no new training",
        audit=dict(path=str(AUDIT), sha256=hashlib.sha256(AUDIT.read_bytes()).hexdigest()),
        previous_protocol_id=previous["id"],
        previous_results_preserved=True,
        development_retest_not_unseen_confirmation=True,
        no_claim_of_isolated_ID_visibility_causal_effect=True,
        snapshot=previous["snapshot"],
        snapshot_id=manifest["id"],
        role_plan=previous["role_plan"],
        calibration_tasks=roster,
        denominator=480,
        jobs=build_jobs(roster),
        greedy_comparison=True,
        max_generate_calls_H=7920,
        max_generate_calls_G=16,
        maximum_total_generate_calls=7936,
        maximum_worker_attempts=1,
        maximum_GPU_workers=4,
        initial_leases=[],
        assets=previous["assets"],
        static_point=previous["static_point"],
        static_adapter_path=previous["static_adapter_path"],
        checkpoint_choice="same original Base and old Static11 step240; no score-based selection",
        gate_cases=synthetic_gate_cases(),
        gate_config=RunConfig(
            harness_id="bigfinance-derived-vtdo-v3",
            submission_profile="finqa_program_v2",
            role="calibration",
            temperature=1,
            max_steps=4,
            max_new_tokens=256,
        ).model_dump(mode="json"),
        diagnostic_virtual=previous["diagnostic_virtual"],
        gate_virtual_is_diagnostic_not_population_G=True,
        gate_admission_policy=dict(
            CPU_actual_template_controls_required=True,
            ordinary_evaluation_requires_settled_and_executable_G2=True,
            actual_prev_path_is_separate_from_numerical_replay=True,
            model_task_failure_is_not_automatically_infrastructure_failure=True,
            retry_failed_model_case=False,
            no_automatic_training_admission=True,
        ),
        submission_profile=profile_definition("finqa_program_v2"),
        cpu_admission=admission,
        runtime_binding=runtime_binding(),
        code_commit=head,
        no_new_training_or_material_collection=True,
        API_model="deepseek-flash",
        API_calls=0,
        all_480_generation_and_workers_exit_before_private_scoring=True,
        comparison="H1-R versus single-shot Direct-DSL task result and cost, not equal-compute",
    )
    plan["id"] = digest(plan)
    publish(output, plan, "protocol.json")
    return plan


def checked_plan(output):
    plan = read_json(Path(output) / "protocol.json")
    if plan["id"] != digest({k: v for k, v in plan.items() if k != "id"}):
        raise ValueError("registered protocol identity changed")
    if plan["runtime_binding"] != runtime_binding():
        raise ValueError("frozen R2 runtime changed; do not silently continue under revised code")
    if plan["max_generate_calls_H"] != 7920 or plan["max_generate_calls_G"] != 16:
        raise ValueError("fixed new-generation budget changed")
    return plan


def worker(output, key, attempt, gpu):
    output = Path(output)
    plan = checked_plan(output)
    if attempt != 1:
        raise ValueError("no automatic worker retries in this registration")
    directory = output / "jobs" / key
    attemptdir = directory / "attempts/01"
    publish(
        attemptdir / "started",
        dict(
            pid=os.getpid(),
            process_identity=identity(os.getpid()),
            gpu=gpu,
            at=now(),
        ),
    )
    try:
        if key == "G2":
            from .gpu_gate_v2 import run_gate

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
                raise ValueError("G2 ordinary execution admission did not pass")
            job = next(j for j in plan["jobs"] if j["key"] == key)
            provider = load_provider(plan, job, gpu)
            generation = directory / "generation"
            if not generation.exists():
                prepare_run(
                    plan["snapshot"],
                    plan["role_plan"],
                    generation,
                    role="calibration",
                    config=RunConfig.model_validate(job["config"]),
                    identity=provider.identity,
                    task_keys=job["task_keys"],
                )
            seal = asyncio.run(execute_run(generation, provider))
            outcome = dict(status="COMPLETE", generation_seal_id=seal["id"])
    except BaseException as error:
        import traceback

        traceback.print_exc()
        outcome = dict(status="BLOCKED", exception_type=type(error).__name__, message=str(error))
    publish(attemptdir / "outcome", {**outcome, "at": now()})
    return 0 if outcome["status"] == "COMPLETE" else 1


def launch(output, key, gpu):
    logpath = output / "logs" / f"{key}_01.log"
    logpath.parent.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": gpu,
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "1",
    }
    with logpath.open("ab") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                __spec__.name,
                "worker",
                "--output",
                str(output),
                "--key",
                key,
                "--attempt",
                "1",
                "--gpu",
                gpu,
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    publish(
        output / "jobs" / key / "attempts/01/launched",
        dict(
            pid=proc.pid,
            process_identity=identity(proc.pid),
            gpu=gpu,
            at=now(),
        ),
    )


def finish(output, plan):
    seal_path = output / "generation_seal/record.json"
    if not seal_path.exists():
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
        directory = output / "scoring" / job["key"]
        result = (
            read_json(directory / "report.json")
            if (directory / "report.json").exists()
            else score_run(output / "jobs" / job["key"] / "generation", directory)
        )
        reports.append(
            dict(job_key=job["key"], model=job["model"], harness=job["harness"], report=result)
        )
    publish(
        output / "complete",
        dict(
            protocol_id=plan["id"],
            at=now(),
            complete=True,
            reports=reports,
            comparison=plan["comparison"],
            development_retest_not_unseen_confirmation=True,
            training_value_claimed=False,
        ),
    )
    status(output, dict(at=now(), phase="COMPLETE", active_workers=0, denominator=480, blocked=[]))


def coordinate(output):
    output = Path(output)
    plan = checked_plan(output)
    with (output / "coordinator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "complete/record.json").exists():
            return
        while True:
            keys = ["G2"] + [j["key"] for j in plan["jobs"]]
            states = {key: latest(output, key) for key in keys}
            active = {key: row for key, row in states.items() if row and row["alive"]}
            blocked = [
                key
                for key, row in states.items()
                if row
                and not row["alive"]
                and (row["outcome"] is None or row["outcome"]["status"] != "COMPLETE")
            ]
            gatepath = output / "gate_complete/record.json"
            gate = read_json(gatepath) if gatepath.exists() else None
            if gate is not None and not gate["eval_native_passed"]:
                blocked.append("G2_EVAL_NATIVE_FAILED")
            eligible = keys[1:] if gate and gate["eval_native_passed"] else ["G2"]
            used = {row["process"]["gpu"] for row in active.values()}
            available = [
                row["uuid"]
                for row in gpu_inventory()
                if row["uuid"] not in used
                and not row["processes"]
                and row["used"] <= 1024
                and row["free"] >= 49152
            ]
            if not blocked:
                for key in eligible:
                    if states[key] is not None:
                        continue
                    if not available or len(active) >= plan["maximum_GPU_workers"]:
                        break
                    gpu = available.pop(0)
                    launch(output, key, gpu)
                    active[key] = dict(process={"gpu": gpu})
            completed = sum(
                bool(
                    states[k]
                    and states[k]["outcome"]
                    and states[k]["outcome"]["status"] == "COMPLETE"
                )
                for k in keys[1:]
            )
            status(
                output,
                dict(
                    at=now(),
                    protocol_id=plan["id"],
                    phase="H2" if gate else "G2",
                    active_workers=len(active),
                    H_shards_complete=completed,
                    H_shards=16,
                    blocked=blocked,
                    gate=gate,
                    waiting_for_GPU=not active and not available and not blocked,
                ),
            )
            if blocked and not active:
                return
            if completed == 16 and not active and not blocked:
                try:
                    finish(output, plan)
                except BaseException as error:
                    import traceback

                    traceback.print_exc()
                    publish(
                        output / "analysis_failure",
                        dict(
                            at=now(),
                            exception_type=type(error).__name__,
                            message=str(error),
                            generation_complete=True,
                            new_model_calls=0,
                        ),
                    )
                    status(
                        output,
                        dict(
                            at=now(),
                            phase="SCORING_BLOCKED",
                            active_workers=0,
                            blocked=[str(error)],
                            generation_complete=True,
                        ),
                    )
                return
            time.sleep(5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--cpu-evidence", type=Path, default=CPU_EVIDENCE)
    parser.add_argument("--key")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--gpu")
    args = parser.parse_args(argv)
    if args.action == "register":
        print({"id": register(args.output, args.cpu_evidence)["id"]})
    elif args.action == "worker":
        return worker(args.output, args.key, args.attempt, args.gpu)
    elif args.action == "coordinate":
        coordinate(args.output)
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    else:
        checked_plan(args.output)
        with (args.output / "coordinator.log").open("ab") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", __spec__.name, "coordinate", "--output", str(args.output)],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(dict(pid=proc.pid, process_identity=identity(proc.pid), at=now()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
