"""Freeze once, run one baseline and six paired Students, then assess offline."""

import argparse
import os
import subprocess
import time
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.tokens import (
    load_bound_assets,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

from . import evaluate, weights
from .loss import package_mean_losses, simulated_objective
from .model import bind_checkpoint
from .panel import EVAL_TASKS, Panel
from .plan import (
    ALLOWED_GPUS,
    AUDIT_PATH,
    AUDIT_SHA256,
    DOCUMENT,
    MAX_PARALLEL_WORKERS,
    OUTPUT,
    PACKAGE,
    SEEDS,
    TESTS,
    encode,
    evaluation_config,
    history_guard,
    read_json,
    record,
    require,
    sha,
    training_config,
)
from .runtime import initial_messages


def cpu_loss_probe(view):
    values = {
        row["row_index"]: [
            Fraction(1 + (row["row_index"] * 13 + token * 7) % 83, 19)
            for token in range(row["target_token_count"])
        ]
        for row in view["rows"]
    }
    means = package_mean_losses(view, values)
    objectives = {arm: simulated_objective(view, values, arm) for arm in ("P", "Q")}
    expected = (means["T_L1_03"] - (means["T_L1_01"] + means["T_L1_04"]) / 2) / 36
    require(objectives["Q"] - objectives["P"] == expected, "prepare.exact_Q_minus_P")
    for arm in ("P", "Q"):
        for width in (1, 2, 5, 12, 36):
            result = sum(
                (
                    simulated_objective(
                        view, values, arm, row_indices=list(range(start, min(start + width, 36)))
                    )
                    for start in range(0, 36, width)
                ),
                Fraction(),
            )
            require(result == objectives[arm], "prepare.chunk_invariant_sum")
    return record(
        "CPU_exact_loss_wiring",
        weights=weights.validate_weights(view),
        artificial_nonnegative_NLL_not_model_predictions=True,
        artificial_NLL_formula="(1+(row_index*13+token_index*7)%83)/19",
        objectives={key: str(value) for key, value in objectives.items()},
        measured_Q_minus_P=str(objectives["Q"] - objectives["P"]),
        expected_L1_identity=str(expected),
        exactly_equal=True,
        block_widths=[1, 2, 5, 12, 36],
        all_blocks_add_exactly=True,
        Student_loaded=False,
    )


def prepare(root):
    history_guard(root)
    implementation = source_snapshot(root)
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--", PACKAGE, DOCUMENT, *TESTS], cwd=root
        ),
        "prepare.rules_committed",
    )
    require(
        subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=root, text=True).strip()
        == implementation["source_commit"],
        "prepare.freeze_pushed_before_actual_Student",
    )
    require(not (root / OUTPUT).exists(), "prepare.exclusive_new_experiment")
    panel = Panel(root)
    view = weights.build(root)
    probe = cpu_loss_probe(view)
    store = DurableStore(root / OUTPUT / "preparation")
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("training_configuration.json", training_config())
    store.json("evaluation_configuration.json", evaluation_config())
    store.json("evaluation_policy.json", evaluate.policy())
    store.json("panel_selection.json", panel.design())
    store.json("weight_view.json", view)
    store.json("CPU_loss_wiring.json", probe)
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    audit = Path(AUDIT_PATH).read_bytes()
    require(sha(audit) == AUDIT_SHA256, "prepare.original_user_audit")
    store.write("external_review.original.txt", audit)
    private, registrations, lengths = {}, [], []
    binding, _, tokenizer = load_bound_assets(root)
    for key in EVAL_TASKS:
        task = panel.tasks[key]
        public = public_document(task)
        store.json(f"public/{key}.json", public)
        private[key] = {
            field: task[field]
            for field in (
                "key",
                "qa_id",
                "unit",
                "facts",
                "target",
                "relations",
                "sufficient_routes",
                "goal_scope",
                "interpretation",
                "precision_policy",
                "group",
                "exact_target",
            )
        }
        private[key]["public_document_id"] = public["id"]
        registrations.append(
            {"task_key": key, "group": task["group"], "public_document_id": public["id"]}
        )
        messages = initial_messages(public)
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        count = len(tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"])
        require(count + 1024 <= 32768, "prepare.new_eval_first_prompt_fits")
        require(
            len(
                encode(
                    {"messages": messages, "decoder_configuration_id": evaluation_config()["id"]}
                )
            )
            <= 98304,
            "prepare.new_eval_first_request_byte_budget",
        )
        lengths.append(
            {"task_key": key, "first_prompt_tokens": count, "sha256": sha(rendered.encode())}
        )
    store.json("private/evaluation_targets.json", private)
    store.json("evaluation_registrations.json", registrations)
    store.json(
        "new_evaluation_prefix_sizes.json",
        record(
            "new_eval_prefix_sizes",
            rows=lengths,
            tokenizer_binding_id=binding["id"],
            only_12_new_evaluation_prompts_tokenized=True,
            original_36_rows_retokenized=False,
        ),
    )
    print("preparation binding original checkpoint shards on CPU", flush=True)
    checkpoint = bind_checkpoint()
    store.json("checkpoint_binding.json", checkpoint)
    tests = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            *TESTS,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("new_controls_stdout.txt", tests.stdout)
    store.write("new_controls_stderr.txt", tests.stderr)
    store.json(
        "new_controls.json",
        record(
            "new_pre_Student_controls",
            exit_code=tests.returncode,
            test_files=list(TESTS),
            test_sha256={name: sha((root / name).read_bytes()) for name in TESTS},
            old_45_controls_repeated=False,
            old_19_pairs_recomputed=False,
            original_36_rows_retokenized=False,
            real_Student_loaded=False,
            teacher_calls=0,
        ),
    )
    require(tests.returncode == 0, "prepare.new_controls_pass")
    manifest = seal_directory(
        store, kind="pq_preparation_manifest", checkpoint_binding_id=checkpoint["id"]
    )
    print("preparation sealed", manifest["id"], flush=True)
    return manifest


def check_preparation(root):
    prep = root / OUTPUT / "preparation"
    manifest = verify_directory(prep, kind="pq_preparation_manifest")
    verify_source_snapshot(root, read_json(prep / "implementation.json"))
    require(
        read_json(prep / "training_configuration.json") == training_config(), "run.frozen_train"
    )
    require(
        read_json(prep / "evaluation_configuration.json") == evaluation_config(), "run.frozen_eval"
    )
    require(read_json(prep / "evaluation_policy.json") == evaluate.policy(), "run.frozen_policy")
    require(read_json(prep / "new_controls.json")["exit_code"] == 0, "run.controls_passed")
    registrations = read_json(prep / "evaluation_registrations.json")
    require([row["task_key"] for row in registrations] == list(EVAL_TASKS), "run.all_12_fixed")
    for row in registrations:
        require(
            read_json(prep / f"public/{row['task_key']}.json")["id"] == row["public_document_id"],
            "run.registration_public_join",
        )
    weights.validate_weights(read_json(prep / "weight_view.json"))
    history_guard(root)
    return manifest


def worker_environment(root, gpu):
    require(gpu in ALLOWED_GPUS, "worker.allowed_free_GPU")
    environment = {
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
        environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    return environment


def available_devices():
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    result = []
    for line in raw.splitlines():
        index, name, free = (part.strip() for part in line.split(",", 2))
        if int(index) in ALLOWED_GPUS and name == "NVIDIA A100-SXM4-80GB" and int(free) >= 70000:
            result.append(int(index))
    return sorted(result)


def launch(root, variant, gpu):
    free = subprocess.check_output(
        [
            "nvidia-smi",
            "--id=" + str(gpu),
            "--query-gpu=memory.free",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    ).strip()
    require(int(free) >= 70000, "worker.requires_currently_free_A100_no_other_process_touched")
    logs = root / OUTPUT / "worker_logs"
    logs.mkdir(parents=True, exist_ok=True)
    command = [
        str(root / "trusted_data_synthesis/.venv/bin/python"),
        "-u",
        "-m",
        "trusted_synthesis.experiments.finance_qa_vnext_pq_student.train",
    ]
    if variant == "B0":
        command += ["baseline"]
    else:
        arm, seed = variant.split("_")
        command += ["train", "--arm", arm, "--seed", seed]
    command += ["--root", str(root)]
    stdout = (logs / f"{variant}.stdout").open("xb")
    stderr = (logs / f"{variant}.stderr").open("xb")
    try:
        process = subprocess.Popen(
            command, cwd=root, env=worker_environment(root, gpu), stdout=stdout, stderr=stderr
        )
    finally:
        stdout.close()
        stderr.close()
    print("started", variant, "physical_GPU", gpu, "pid", process.pid, flush=True)
    return process


def verify_pairing(root):
    output = root / OUTPUT
    pairs = []
    for seed in SEEDS:
        identities, reports = {}, {}
        for arm in ("P", "Q"):
            directory = output / f"training/{arm}_{seed}"
            verify_directory(directory, kind="pq_training_manifest")
            identities[arm] = read_json(directory / "identity.json")
            reports[arm] = read_json(directory / "report.json")
            report = reports[arm]
            require(
                report["optimizer_updates"] == 10
                and report["full_passes"] == 10
                and report["actual_supervised_tokens"] == 47930
                and report["actual_sequence_tokens"] == 2326030,
                "pairing.same_physical_budget",
            )
        matched_fields = [
            "seed",
            "checkpoint_binding_id",
            "weight_view_id",
            "configuration_id",
            "scope",
            "initial_adapter_parameter_sha256",
            "orders",
            "initial_CPU_rng_sha256",
            "initial_CUDA_rng_sha256",
            "optimizer_initial_state_empty",
            "device",
        ]
        require(
            all(identities["P"][key] == identities["Q"][key] for key in matched_fields),
            "pairing.identical_nonintervention_settings",
        )
        first = {arm: reports[arm]["records"][0] for arm in ("P", "Q")}
        errors = {
            label: abs(
                first["P"]["package_mean_nll"][label] - first["Q"]["package_mean_nll"][label]
            )
            for label in first["P"]["package_mean_nll"]
        }
        nll = first["P"]["package_mean_nll"]
        observed = first["Q"]["full_pass_weighted_loss"] - first["P"]["full_pass_weighted_loss"]
        expected = (nll["T_L1_03"] - (nll["T_L1_01"] + nll["T_L1_04"]) / 2) / 36
        require(
            max(errors.values()) < 1e-5 and abs(observed - expected) < 1e-5,
            "pairing.actual_first_pass_Q_minus_P_identity",
        )
        pairs.append(
            {
                "seed": seed,
                "identical_fields": matched_fields,
                "maximum_first_pass_package_NLL_error": max(errors.values()),
                "actual_first_pass_Q_minus_P": observed,
                "expected_L1_identity": expected,
                "absolute_identity_error": abs(observed - expected),
                "floating_check_tolerance": 1e-5,
                "final_P_adapter": reports["P"]["final_adapter"],
                "final_Q_adapter": reports["Q"]["final_adapter"],
            }
        )
    prompt_hashes = {}
    for variant in evaluation_config()["variants"]:
        verify_directory(output / "evaluation" / variant, kind="pq_student_generation_manifest")
        report = read_json(output / f"evaluation/{variant}/report.json")
        guard = read_json(output / f"worker_guards/{variant}.json")
        require(
            guard["all_zero"] and not any(guard["calls"].values()), "pairing.offline_public_only"
        )
        hashes = {row["task_key"]: row["initial_messages_sha256"] for row in report["rows"]}
        require(len(hashes) == 12, "pairing.complete_eval_panel")
        if prompt_hashes:
            require(hashes == prompt_hashes, "pairing.identical_public_first_messages")
        prompt_hashes = hashes
    return record(
        "actual_PQ_pairing_audit",
        pairs=pairs,
        all_checks_passed=True,
        actual_training_runs=6,
        baseline_runs=1,
        evaluated_sessions=84,
        total_supervised_training_tokens=6 * 47930,
        total_training_sequence_tokens=6 * 2326030,
        no_teacher_calls=True,
        all_public_first_message_hashes_equal=prompt_hashes,
    )


def run(root):
    manifest = check_preparation(root)
    output = root / OUTPUT
    require(not (output / "execution").exists(), "run.no_implicit_restart_or_extra_training")
    ready = available_devices()
    require(ready, "run.wait_for_free_A100_before_creating_execution_or_loading_Student")
    baseline_gpu = ready[0]
    store = DurableStore(output / "execution")
    store.json(
        "registration.json",
        record(
            "fixed_Student_execution",
            preparation_manifest_id=manifest["id"],
            variants=evaluation_config()["variants"],
            allowed_physical_GPUs=list(ALLOWED_GPUS),
            no_other_GPU_processes_touched=True,
            baseline_before_training=True,
            maximum_parallel_train_workers=MAX_PARALLEL_WORKERS,
            GPU_admission="A100-SXM4-80GB with >=70000 MiB free; one worker per device",
        ),
    )
    statuses = []
    started = time.perf_counter()
    pending = [f"{arm}_{seed}" for seed in SEEDS for arm in ("P", "Q")]
    try:
        process = launch(root, "B0", baseline_gpu)
    except Exception as error:
        statuses.append(
            {
                "variant": "B0",
                "exit_code": None,
                "started": False,
                "physical_GPU": baseline_gpu,
                "launch_error": str(error),
            }
        )
    else:
        statuses.append(
            {
                "variant": "B0",
                "exit_code": process.wait(),
                "started": True,
                "physical_GPU": baseline_gpu,
            }
        )
    store.json("baseline_exit.json", statuses[0])
    if statuses[0]["exit_code"] != 0:
        store.json(
            "process_report.json",
            record(
                "student_process_completion",
                rows=statuses,
                unstarted=pending,
                elapsed_seconds=time.perf_counter() - started,
                all_seven_completed=False,
            ),
        )
        raise ValueError("run.baseline_process_failed_no_training_started")
    active = {}
    failure = False
    last_wait_message = 0.0
    while active or (pending and not failure):
        available = [
            gpu for gpu in available_devices() if gpu not in {p[1] for p in active.values()}
        ]
        while pending and available and not failure and len(active) < MAX_PARALLEL_WORKERS:
            variant, gpu = pending.pop(0), available.pop(0)
            try:
                active[variant] = (launch(root, variant, gpu), gpu)
            except Exception as error:
                row = {
                    "variant": variant,
                    "exit_code": None,
                    "physical_GPU": gpu,
                    "started": False,
                    "launch_error": str(error),
                }
                statuses.append(row)
                store.json(f"exits/{variant}.json", row)
                print("worker not started", row, flush=True)
                failure = True
        for variant, (process, gpu) in list(active.items()):
            code = process.poll()
            if code is None:
                continue
            row = {"variant": variant, "exit_code": code, "physical_GPU": gpu, "started": True}
            statuses.append(row)
            store.json(f"exits/{variant}.json", row)
            print("worker exited", row, flush=True)
            failure |= code != 0
            del active[variant]
        if (
            pending
            and not failure
            and not available
            and time.perf_counter() - last_wait_message >= 30
        ):
            print("waiting for a free eligible A100; pending", pending, flush=True)
            last_wait_message = time.perf_counter()
        if active or (pending and not failure):
            time.sleep(2)
    store.json(
        "process_report.json",
        record(
            "student_process_completion",
            rows=statuses,
            unstarted=pending,
            elapsed_seconds=time.perf_counter() - started,
            all_seven_completed=not failure and len(statuses) == 7,
        ),
    )
    require(
        not failure and not pending and len(statuses) == 7, "run.worker_failure_no_automatic_retry"
    )
    audit = verify_pairing(root)
    store.json("pairing_audit.json", audit)
    history_guard(root)
    seal_directory(store, kind="pq_execution_manifest", pairing_audit_id=audit["id"])
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "assess", "finalize"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare(args.root)
    elif args.mode == "run":
        result = run(args.root)
    elif args.mode == "assess":
        result = evaluate.assess(args.root)
    else:
        require(args.reviews is not None, "finalize.explicit_review_file")
        result = evaluate.finalize(args.root, args.reviews)
    print(result.get("id", result), flush=True)


if __name__ == "__main__":
    main()
