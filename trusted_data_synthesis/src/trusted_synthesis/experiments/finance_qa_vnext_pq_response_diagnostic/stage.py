"""Freeze once, run the fixed non-adaptive queue, then stop for offline review."""

import argparse
import os
import subprocess
import time
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.runtime import initial_messages

from .plan import (
    AUDIT_PATH,
    AUDIT_SHA256,
    EXECUTION_KIND,
    GENERATION_KIND,
    OUTPUT,
    PARENT,
    PREPARATION_KIND,
    SCORE_KIND,
    SOURCE,
    TESTS,
    TRAINED,
    VARIANTS,
    check_reference,
    configuration,
    encode,
    history_guard,
    read_json,
    record,
    reference,
    require,
    sha,
)


def prepare(root):
    history = history_guard(root)
    require(not (root / OUTPUT).exists(), "diagnostic.no_existing_run")
    implementation = source_snapshot(root)
    raw_audit = Path(AUDIT_PATH).read_bytes()
    require(sha(raw_audit) == AUDIT_SHA256, "diagnostic.user_audit_binding")
    parent_prep = root / PARENT / "preparation"
    binding = read_json(parent_prep / "checkpoint_binding.json")
    models, refs = {}, []
    for variant in VARIANTS:
        adapter_path, adapter, report_id, seed = None, None, None, 0
        if variant != "B0":
            seed = int(variant.split("_")[1])
            path = f"{PARENT}/training/{variant}/report.json"
            report = read_json(root / path)
            require(
                report["variant"] == variant and report["optimizer_updates"] == 10,
                "diagnostic.only_completed_final_adapters",
            )
            adapter = report["final_adapter"]
            adapter_path = f"{PARENT}/training/{variant}/{adapter['path']}"
            ref = reference(root, adapter_path)
            require(
                ref["sha256"] == adapter["sha256"] and ref["bytes"] == adapter["bytes"],
                "diagnostic.original_final_adapter_bytes",
            )
            refs += [reference(root, path), ref]
            report_id = report["id"]
        models[variant] = record(
            "fixed_final_model_identity",
            variant=variant,
            seed=seed,
            checkpoint_binding_id=binding["id"],
            adapter_path=adapter_path,
            adapter_record=adapter,
            parent_training_report_id=report_id,
            no_new_training=True,
            origin="local_student_generation",
            lineage="original B0" if variant == "B0" else "original final update-10 adapter",
        )
    source_public = f"{SOURCE}/preparation/public/L1.json"
    source_private = f"{SOURCE}/preparation/private/evaluation_targets.json"
    public = read_json(root / source_public)
    private = read_json(root / source_private)["L1"]
    require(public["id"] == private["public_document_id"], "diagnostic.original_L1_join")
    for path in (
        source_public,
        source_private,
        f"{PARENT}/preparation/weight_view.json",
        f"{PARENT}/preparation/checkpoint_binding.json",
        f"{PARENT}/closeout/report.json",
        f"{PARENT}/closeout/reviews.json",
    ):
        refs.append(reference(root, path))
    store = DurableStore(root / OUTPUT / "preparation")
    store.write("user_audit.raw", raw_audit)
    store.json("configuration.json", configuration())
    store.json("models.json", models)
    store.write("weight_view.json", (parent_prep / "weight_view.json").read_bytes())
    store.write("checkpoint_binding.json", (parent_prep / "checkpoint_binding.json").read_bytes())
    store.write("public/L1.json", (root / source_public).read_bytes())
    store.json("private/L1.json", private)
    store.json("evaluation_policy.json", evaluate.policy())
    store.json("implementation.json", implementation)
    store.json("source_references.json", refs)
    process = subprocess.run(
        [str(root / "trusted_data_synthesis/.venv/bin/python"), "-m", "pytest", "-q", *TESTS],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "trusted_data_synthesis/src")},
        capture_output=True,
    )
    store.write("new_controls.stdout", process.stdout)
    store.write("new_controls.stderr", process.stderr)
    require(process.returncode == 0, "diagnostic.new_controls_failed_no_Student_execution")
    report = record(
        "prepared_response_diagnostic",
        configuration_id=configuration()["id"],
        implementation_id=implementation["id"],
        models=list(models),
        history=history,
        original_public_document_id=public["id"],
        initial_messages_sha256=sha(encode(initial_messages(public))),
        evaluation_policy_id=evaluate.policy()["id"],
        tests=list(TESTS),
        controls_returncode=0,
        old_58_controls_not_rerun=True,
        student_model_loads=0,
        no_new_arrays_or_tokenization=True,
        previous_audit_accepted_as_scoped=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind=PREPARATION_KIND, report_id=report["id"])
    return report


def check_preparation(root):
    prep = root / OUTPUT / "preparation"
    verify_directory(prep, kind=PREPARATION_KIND)
    require(read_json(prep / "configuration.json") == configuration(), "diagnostic.fixed_config")
    require(
        read_json(prep / "evaluation_policy.json") == evaluate.policy(), "diagnostic.old_policy"
    )
    verify_source_snapshot(root, read_json(prep / "implementation.json"))
    for ref in read_json(prep / "source_references.json"):
        check_reference(root, ref)
    history_guard(root)
    return read_json(prep / "report.json")


def available_devices():
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    devices = []
    for line in raw.splitlines():
        index, name, free = (v.strip() for v in line.split(",", 2))
        if int(index) in range(8) and name == "NVIDIA A100-SXM4-80GB" and int(free) >= 70000:
            devices.append(int(index))
    return sorted(devices)


def worker_environment(root, gpu):
    env = {
        "PATH": str(root / "trusted_data_synthesis/.venv/bin") + ":/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(root / "trusted_data_synthesis/src"),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    }
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    return env


def launch(root, phase, variant, gpu):
    require(gpu in available_devices(), "diagnostic.currently_free_GPU_required")
    logs = root / OUTPUT / "worker_logs"
    logs.mkdir(parents=True, exist_ok=True)
    command = [
        str(root / "trusted_data_synthesis/.venv/bin/python"),
        "-u",
        "-m",
        "trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic." + phase,
        "--root",
        str(root),
        "--variant",
        variant,
    ]
    with (
        (logs / f"{phase}_{variant}.stdout").open("xb") as stdout,
        (logs / f"{phase}_{variant}.stderr").open("xb") as stderr,
    ):
        process = subprocess.Popen(
            command, cwd=root, env=worker_environment(root, gpu), stdout=stdout, stderr=stderr
        )
    print("started", phase, variant, "GPU", gpu, "pid", process.pid, flush=True)
    return process


def run_queue(root, phase, variants, store):
    pending, active, completed, failed = list(variants), {}, [], False
    while pending or active:
        devices = [gpu for gpu in available_devices() if gpu not in active]
        while (
            pending
            and not failed
            and devices
            and len(active) < configuration()["maximum_parallel_workers"]
        ):
            gpu, variant = devices.pop(0), pending.pop(0)
            active[gpu] = (variant, launch(root, phase, variant, gpu))
        if pending and not active:
            require(not failed, "diagnostic.queue_failed_no_retries")
            raise RuntimeError("diagnostic.no_free_GPU_no_job_started")
        for gpu, (variant, process) in list(active.items()):
            code = process.poll()
            if code is not None:
                result = {
                    "phase": phase,
                    "variant": variant,
                    "physical_gpu": gpu,
                    "pid": process.pid,
                    "returncode": code,
                }
                store.json(f"workers/{phase}_{variant}.json", result)
                completed.append(result)
                print("finished", phase, variant, "returncode", code, flush=True)
                failed |= code != 0
                del active[gpu]
        if active:
            time.sleep(2)
        if failed and not active:
            break
    require(
        not failed and not pending and len(completed) == len(variants),
        "diagnostic.phase_incomplete",
    )
    return completed


def run(root):
    prepared = check_preparation(root)
    require(not (root / OUTPUT / "execution").exists(), "diagnostic.execution_no_reentry")
    require(bool(available_devices()), "diagnostic.wait_for_free_GPU_before_execution")
    store = DurableStore(root / OUTPUT / "execution")
    store.json(
        "start.json",
        record(
            "execution_start", preparation_id=prepared["id"], configuration_id=configuration()["id"]
        ),
    )
    started = time.perf_counter()
    workers = run_queue(root, "scoring", VARIANTS, store)
    for variant in VARIANTS:
        verify_directory(root / OUTPUT / "scoring" / variant, kind=SCORE_KIND)
    # This branch checks completion, never loss values or route preferences.
    workers += run_queue(root, "generation", TRAINED, store)
    for variant in TRAINED:
        verify_directory(root / OUTPUT / "generation" / variant, kind=GENERATION_KIND)
    check_preparation(root)
    report = record(
        "completed_response_execution",
        preparation_id=prepared["id"],
        workers=workers,
        score_models=7,
        score_rows=252,
        score_target_positions=33551,
        score_sequence_positions=1628221,
        generation_sessions=6,
        teacher_calls=0,
        new_training_updates=0,
        adapter_saves=0,
        original_panel_sessions_regenerated=0,
        outcome_adaptive_repeats=0,
        elapsed_seconds=time.perf_counter() - started,
    )
    store.json("report.json", report)
    seal_directory(store, kind=EXECUTION_KIND, report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "assess", "finalize"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command in ("prepare", "run"):
        result = {"prepare": prepare, "run": run}[args.command](root)
    else:
        from . import analysis

        if args.command == "assess":
            result = analysis.assess(root)
        else:
            require(args.reviews is not None, "diagnostic.explicit_reviews_required")
            result = analysis.finalize(root, args.reviews)
    print(result["id"], flush=True)


if __name__ == "__main__":
    main()
