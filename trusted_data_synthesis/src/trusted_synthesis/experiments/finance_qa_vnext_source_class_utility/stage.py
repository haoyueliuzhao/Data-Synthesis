"""Freeze once, execute nine runs, and confirm only a sealed positive dev choice."""

import argparse
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
)

from .plan import (
    AUDIT_PATH,
    AUDIT_SHA256,
    CONDITIONS,
    CONTROL_SOURCE,
    DOCUMENT,
    GROUPS,
    MAX_PARALLEL_WORKERS,
    OUTPUT,
    PACKAGE,
    PANEL_SOURCE,
    SEEDS,
    TESTS,
    evaluation_config,
    history_guard,
    read_json,
    record,
    reference,
    require,
    sha,
    training_config,
)
from .student_quantity import context_from_target
from .student_quantity import policy as quantity_policy
from .weights import load_rows


def variant_order():
    return [f"{arm}_{seed}" for seed in SEEDS for arm in CONDITIONS]


def masked_registrations(phase, variants, registrations):
    pairs = [
        {"phase": phase, "variant": variant, "task_key": task["task_key"], "group": task["group"]}
        for variant in variants
        for task in registrations
    ]
    random.Random(21951 if phase == "dev" else 21952).shuffle(pairs)
    return {f"{phase}_{i:03d}": item for i, item in enumerate(pairs, 1)}


def prepare(root):
    output = root / OUTPUT
    require(not (output / "preparation").exists(), "prepare.once")
    history_guard(root)
    implementation = source_snapshot(root)
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--", PACKAGE, DOCUMENT, *TESTS], cwd=root
        ),
        "prepare.all_rules_committed",
    )
    remote = subprocess.check_output(
        ["git", "rev-parse", "refs/remotes/origin/main"], cwd=root, text=True
    ).strip()
    require(remote == implementation["source_commit"], "prepare.rules_pushed_before_Student")
    manifests = {
        phase: manifest(output / phase) for phase in ("quantity_revision", "materialization")
    }
    materialized = read_json(output / "materialization/report.json")
    require(materialized["status"] == "INPUT_ESTABLISHED", "prepare.actual_input_gate")
    view = read_json(output / "materialization/weight_view.json")
    require(view["id"] == materialized["view_id"], "prepare.materialization_view_join")
    rows = load_rows(root, view)  # immutable-array validation, never tokenization
    require(len(rows) == view["totals"]["rows"], "prepare.actual_physical_rows")
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json(
        "inputs.json",
        record(
            "pretraining_inputs",
            materialization_report_id=materialized["id"],
            weight_view_id=view["id"],
            phase_manifest_ids={k: v["id"] for k, v in manifests.items()},
            actual_totals=view["totals"],
            fixed_original_physical_rows=True,
            additional_tokenization=False,
            Teacher_requests=0,
        ),
    )
    store.json("training_configuration.json", training_config(view["totals"]))
    store.json("evaluation_configuration.json", evaluation_config())
    store.json("quantity_policy.json", quantity_policy())
    # These exact existing checkpoint shards and software identities are checked
    # again by the unchanged model loader. No exploratory Student load is made.
    checkpoint_path = root / CONTROL_SOURCE / "checkpoint_binding.json"
    store.write("checkpoint_binding.json", checkpoint_path.read_bytes())
    store.json(
        "checkpoint_reference.json", reference(root, CONTROL_SOURCE + "/checkpoint_binding.json")
    )
    old_private = read_json(root / PANEL_SOURCE / "preparation/private/evaluation_targets.json")
    private, registrations, public_refs, contexts = {}, {}, [], {}
    for phase, prefix, count in (("dev", "D", 12), ("confirm", "C", 24)):
        registrations[phase] = []
        for i in range(1, count + 1):
            key = f"{prefix}{i:02d}"
            source = PANEL_SOURCE + f"/preparation/public/{key}.json"
            public = read_json(root / source)
            task = old_private[key]
            require(
                task["panel"] == phase
                and task["group"] in GROUPS
                and task["public_document_id"] == public["id"],
                "prepare.existing_sealed_panel_identity",
            )
            store.write(f"public/{key}.json", (root / source).read_bytes())
            private[key] = task
            contexts[key] = context_from_target(task["unit"])
            public_refs.append(reference(root, source))
            registrations[phase].append(
                {
                    "task_key": key,
                    "group": task["group"],
                    "public_document_id": public["id"],
                    "company_cluster": task["company_cluster"],
                    "report_cluster": task["report_cluster"],
                }
            )
    store.json("private/evaluation_targets.json", private)
    store.json("task_quantity_contexts.json", contexts)
    store.json("evaluation_registrations.json", registrations)
    store.json(
        "public_panel_references.json",
        {"references": public_refs, "all_source_questions_byte_identical": True},
    )
    panel_path = PANEL_SOURCE + "/preparation/panel_selection.json"
    store.json("original_panel_selection_reference.json", reference(root, panel_path))
    store.json(
        "private/dev_review_identity_map.json",
        masked_registrations("dev", variant_order(), registrations["dev"]),
    )
    assignments = [
        {"arm": arm, "seed": seed, "variant": f"{arm}_{seed}", "gpu": index % 6, "wave": index // 6}
        for index, (seed, arm) in enumerate((seed, arm) for seed in SEEDS for arm in CONDITIONS)
    ]
    store.json("worker_assignments.json", assignments)
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    audit = Path(AUDIT_PATH).read_bytes()
    require(sha(audit) == AUDIT_SHA256, "prepare.supplied_audit_identity")
    store.write("external_review.original.txt", audit)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", *TESTS],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={**os.environ, "PYTHONPATH": str(root / "trusted_data_synthesis/src")},
    )
    store.write("new_controls.txt", result.stdout)
    require(result.returncode == 0, "prepare.new_controls_pass_before_Student")
    report = record(
        "source_class_preparation",
        implementation_id=implementation["id"],
        quantity_version=quantity_policy()["version"],
        training_runs=9,
        development_sessions=108,
        maximum_confirmation_sessions=144,
        maximum_total_Student_sessions=252,
        Teacher_sessions=0,
        Teacher_requests=0,
        B0_old_L1_same_task_greedy_auxiliary_NLL=0,
        actual_token_budget=training_config(view["totals"]),
        new_controls_returncode=result.returncode,
        no_Student_weights_or_forward_yet=True,
        no_source_reselection_or_old_qualification_repetition=True,
    )
    store.json("history_guard.json", history_guard(root))
    store.json("report.json", report)
    seal_directory(store, kind="source_class_preparation_manifest", report_id=report["id"])
    return report


def launch(root, item, mode):
    log_dir = root / OUTPUT / "worker_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{mode}_{item['variant']}.log"
    require(not path.exists(), "launch.no_worker_retry")
    command = [
        sys.executable,
        "-B",
        "-u",
        "-m",
        "trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.train",
        mode,
        "--root",
        str(root),
        "--arm",
        item["arm"],
        "--seed",
        str(item["seed"]),
    ]
    env = {
        **os.environ,
        "PYTHONPATH": str(root / "trusted_data_synthesis/src"),
        "CUDA_VISIBLE_DEVICES": str(item["gpu"]),
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    }
    print("worker_started", mode, item["variant"], "GPU", item["gpu"], flush=True)
    started = time.perf_counter()
    with path.open("xb") as handle:
        worker = subprocess.run(
            command, cwd=root, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
        )
    print("worker_completed", mode, item["variant"], "exit", worker.returncode, flush=True)
    return {
        **item,
        "mode": mode,
        "returncode": worker.returncode,
        "elapsed_seconds": time.perf_counter() - started,
        "log_reference": reference(root, str(path.relative_to(root))),
    }


def execute(root, mode):
    require(mode in {"train", "confirm"}, "execute.bounded_mode")
    manifest(root / OUTPUT / "preparation")
    schedule = root / OUTPUT / "execution" / mode
    require(not schedule.exists(), "execute.no_repeated_wave")
    if mode == "train":
        assignments = read_json(root / OUTPUT / "preparation/worker_assignments.json")
    else:
        manifest(root / OUTPUT / "selection")
        authorization = read_json(root / OUTPUT / "selection/confirmation_authorization.json")
        assignments = [
            {
                "variant": variant,
                "arm": variant.rsplit("_", 1)[0],
                "seed": int(variant.rsplit("_", 1)[1]),
                "gpu": i,
                "wave": 0,
            }
            for i, variant in enumerate(authorization["variants"])
        ]
        require(len(assignments) == 6, "execute.six_selected_confirmation_models")
    store = DurableStore(schedule)
    store.json("registrations.json", assignments)
    records, started = [], time.perf_counter()
    for wave in sorted({item["wave"] for item in assignments}):
        current = [item for item in assignments if item["wave"] == wave]
        require(
            len(current) <= MAX_PARALLEL_WORKERS
            and len({i["gpu"] for i in current}) == len(current),
            "execute.one_worker_per_GPU",
        )
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
            records.extend(pool.map(lambda item: launch(root, item, mode), current))
        store.json(f"wave_{wave}.json", {"rows": records.copy()})
        if any(item["returncode"] for item in records):
            break
    completed = len(records) == len(assignments) and not any(r["returncode"] for r in records)
    report = record(
        "source_class_execution_report",
        mode=mode,
        registered_workers=len(assignments),
        attempted_workers=len(records),
        rows=records,
        status="COMPLETED" if completed else "STOPPED_IMPLEMENTATION_OR_EXECUTION_FAILURE",
        automatic_retry_or_budget_extension=False,
        elapsed_seconds=time.perf_counter() - started,
        Teacher_requests=0,
    )
    store.json("report.json", report)
    seal_directory(store, kind="source_class_execution_manifest", report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "prepare",
            "train",
            "assess-dev",
            "finalize-dev",
            "confirm",
            "assess-confirm",
            "finalize-confirm",
            "verify",
        ),
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare(args.root)
    elif args.mode in {"train", "confirm"}:
        result = execute(args.root, args.mode)
    else:
        from .evaluate import assess, finalize, verify

        if args.mode == "verify":
            result = verify(args.root)
        else:
            action, phase = args.mode.split("-", 1)
            result = (
                assess(args.root, phase)
                if action == "assess"
                else finalize(args.root, phase, args.reviews)
            )
    print("completed", args.mode, result["id"], flush=True)


if __name__ == "__main__":
    main()
