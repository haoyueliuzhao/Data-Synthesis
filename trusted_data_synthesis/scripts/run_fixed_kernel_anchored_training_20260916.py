"""Registered six-run A matrix: full G -> sealed360 -> independent Q -> gJ/C/pi -> SFT.

Full seed11 is first, never a pilot. Other runs start only after their predecessor
has delivered its first real update; inner training may then overlap. One outer
gradient loop at a time, with spare-GPU trajectory sampling. B/confirm stay shut.
"""

# ruff: noqa: E501 -- fixed scientific contracts and artifact lineage
import argparse
import contextlib
import copy
import fcntl
import gc
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import fixed_kernel_anchored_feedback_20260916 as feedback
import fixed_kernel_anchored_publication_20260916 as publication
import fixed_kernel_anchored_sources_gpu_gate_20260916 as gate
import fixed_kernel_anchored_sources_gradients_20260916 as classes
import fixed_kernel_anchored_sources_state_20260916 as distribution
import fixed_kernel_source_view_compact_20260915 as views
import torch
from fixed_kernel_anchored_saved_tensors_20260916 import host_memory
from safetensors.torch import save_file

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    trajectory_consumer as inner,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    trajectory_materials,
    trajectory_training,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
    load_tokenizer,
)

OUTPUT = gate.BASE + "/registered_A"
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_anchored_training_20260916.py"
GIVEN = gate.GIVEN
MIN_FREE_MIB = 61440
MIN_HOST_BYTES = 256 * 2**30
CONDITIONS = ("full_anchored_vtdo", "c_only_anchored")
_OWNED = []
SOURCES = [
    SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_publication_20260916.py",
    feedback.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_sources_gradients_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_sources_state_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_segmented_replay_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_canonical_saves_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_saved_tensors_20260916.py",
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_compact_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_given_sources_execution_20260915.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_anchored_vtdo/optimizer_pullback.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_anchored_vtdo/distribution.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_anchored_vtdo/protocol.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/trajectory_consumer.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/trajectory_training.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_pq_student/model.py",
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_runtime_20260915.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_eval_readiness/runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_eval_readiness/assessment.py",
]


def prepare(root):
    root = Path(root).resolve()
    out = root / OUTPUT
    admitted = p.checked(
        p.read_json(root / gate.BASE / "production_admission_r4/report.json"),
        "anchored_production_resource_admission",
    )
    p.require(
        admitted["passed"] and admitted["full_response_contract_admitted"],
        "anchored_A.actual_resource_and_numeric_admission",
    )
    material = p.checked(
        p.read_json(root / gate.BASE / "material_binding/report.json"),
        "anchored_sources_material_admission",
    )
    binding = p.checked(
        p.read_json(root / gate.BASE / "material_binding/A.json"),
        "anchored_sources_material_binding",
    )
    manifest = p.checked(
        p.read_json(root / GIVEN / "inputs_v2/manifest.json"), "source_view_manifest_v2"
    )
    p.require(
        manifest["id"] == material["existing_given_sources_view_manifest_id"]
        and len(manifest["tasks"]) == 180
        and not set(binding["prior"]) & {row["task_id"] for row in manifest["tasks"]},
        "anchored_A.original_dev_and_disjoint_train_roles",
    )
    frozen = p.read_json(root / gate.PARENT / "preparation/execution_freeze.json")
    population_ref = frozen["input_files"]["population"]
    raw = (Path(frozen["input_root"]) / population_ref["path"]).read_bytes()
    p.require(p.sha(raw) == population_ref["sha256"], "anchored_A.original_task_roster")
    population = json.loads(raw)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for path in SOURCES:
        raw = (root / path).read_bytes()
        p.require(
            raw == subprocess.check_output(["git", "show", head + ":" + path], cwd=root),
            "anchored_A.committed_before_first_feedback",
        )
        sources[path] = p.sha(raw)
    runs = []
    for seed in (11, 29, 47):
        for condition in CONDITIONS:
            runs.append(
                dict(
                    key=f"A_{'full' if condition == CONDITIONS[0] else 'c_only'}_{seed}",
                    condition=condition,
                    seed=seed,
                    pool="A",
                )
            )
    schedules = {
        str(seed): p.read_json(
            root / gate.PARENT / "training" / f"A_alpha0_{seed}" / "schedule.json"
        )
        for seed in (11, 29, 47)
    }
    reused = {int(row["model"].rsplit("_", 1)[1]): row for row in material["static_reuse"]}
    p.require(
        all(
            schedules[str(seed)]["id"] == reused[seed]["schedule_id"]
            and len(schedules[str(seed)]["batches"]) == 400
            for seed in (11, 29, 47)
        ),
        "anchored_A.exact_paired_original_schedules",
    )
    plan = p.record(
        "anchored_registered_A_plan",
        code_commit=head,
        sources=sources,
        resource_admission_id=admitted["id"],
        material_admission_id=material["id"],
        binding_id=binding["id"],
        source_manifest_id=manifest["id"],
        tasks=manifest["tasks"],
        runs=runs,
        assets={key: frozen[key] for key in ("base_binding", "tokenizer_binding")},
        training_configuration=frozen["training_configuration"],
        trajectory_cache=frozen["trajectory_cache"],
        schedules=schedules,
        training_groups={row["task_id"]: row["family"] for row in population["tasks"]},
        initial_adapter_digests={
            str(seed): reused[seed]["initial_adapter_digest"] for seed in (11, 29, 47)
        },
        private_scoring_source_root=frozen["source_root"],
        static_reuse=material["static_reuse"],
        runtime_binding=views.binding(),
        fresh_paired_initialization=True,
        warmstart_from_Static_final=False,
        outer_steps=[0, 200],
        total_inner_updates=400,
        epochs=10,
        tasks_per_update=5,
        feedback_per_round=360,
        feedback_rounds_per_run=2,
        feedback_sessions=4320,
        final_greedy_sessions=1080,
        new_sessions_total=5400,
        new_generate_call_cap=172800,
        new_Student_trainings=6,
        actual_SFT_sequence_token_budget=1076537940,
        actual_SFT_supervision_token_budget=59516640,
        extra_class_gradient_sequence_tokens=215307588,
        maximum_concurrent_outer_gradient_workers=1,
        sampling_parallel_on_unleased_admitted_GPUs=True,
        minimum_free_GPU_MiB=MIN_FREE_MIB,
        minimum_host_available_bytes=MIN_HOST_BYTES,
        all_zero_feedback="UNINFORMATIVE_FEEDBACK: keep current pi exactly and continue fixed schedule",
        prior_and_hyperparameters_unchanged=True,
        primary_candidate=CONDITIONS[0],
        C_only_cannot_replace_primary=True,
        development_used_for_meta_learning=True,
        B_or_confirmation_authorized=False,
        no_extra_effect_pilot=True,
        automatic_retry=False,
        at=p.now(),
    )
    p.write_once(out / "plan.json", plan)
    p.write_once(
        out / "public_plan.json",
        p.record(
            "anchored_registered_A_public_plan",
            plan_id=plan["id"],
            code_commit=head,
            resource_admission_id=admitted["id"],
            material_admission_id=material["id"],
            runs=runs,
            first_run=runs[0],
            new_training_runs=6,
            reused_static_training_runs=3,
            new_feedback_sessions=4320,
            new_final_greedy_sessions=1080,
            new_generate_call_cap=172800,
            B_and_confirmation=0,
            full_Student_feedback_loop_not_a_pilot=True,
        ),
    )
    return plan


def claim_gpus(root, *, excluded=(), maximum=8):
    directory = Path(root) / OUTPUT / "runtime/gpu_leases"
    directory.mkdir(parents=True, exist_ok=True)
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    rows = [tuple(part.strip() for part in line.split(",")) for line in raw.splitlines()]
    result = []
    for index, uuid, free in sorted(rows, key=lambda row: (-int(row[2]), int(row[0]))):
        if uuid in excluded or int(free) < MIN_FREE_MIB or len(result) >= maximum:
            continue
        handle = (directory / (uuid + ".lock")).open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            continue
        result.append((dict(index=int(index), uuid=uuid, free_MiB=int(free)), handle))
    return result


@contextlib.contextmanager
def outer_slot(root, run_key, step):
    path = Path(root) / OUTPUT / "runtime/outer_gradient.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if host_memory()["MemAvailable_bytes"] >= MIN_HOST_BYTES:
                    break
                fcntl.flock(lock, fcntl.LOCK_UN)
            except BlockingIOError:
                pass
            print(
                json.dumps(
                    dict(event="waiting_for_outer_slot_or_host", run=run_key, step=step, at=p.now())
                ),
                flush=True,
            )
            time.sleep(30)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def point_record(root, directory, model, theta, plan, run, *, step, kind, origin):
    directory.mkdir(parents=True, exist_ok=True)
    adapter = feedback.at_point(
        model,
        theta,
        lambda actual: components.save_adapter(actual, directory / "adapter.safetensors"),
    )
    point = p.record(
        "anchored_model_parameter_point",
        point_kind=kind,
        run=run,
        step=step,
        origin_id=origin,
        source_manifest_id=plan["source_manifest_id"],
        parameter_digest=gate.tensor_digest(theta),
        adapter=adapter,
        adapter_directory=str(directory.relative_to(root)),
        base_binding_id=plan["assets"]["base_binding"]["id"],
    )
    p.write_once(directory / "point.json", point)
    return point


def sample_and_score(
    root, directory, model, tokenizer, theta, point, plan, run, *, round_index, stochastic
):
    directory.mkdir(parents=True, exist_ok=True)
    jobs = feedback.registration(
        plan["tasks"], pool="A", seed=run["seed"], round_index=round_index, stochastic=stochastic
    )
    p.write_once(
        directory / "registration.json",
        p.record(
            "anchored_trajectory_registration",
            point_id=point["id"],
            stochastic=stochastic,
            jobs=jobs,
        ),
    )
    spare = claim_gpus(root, excluded=(os.environ["CUDA_VISIBLE_DEVICES"],), maximum=7)
    shards = [jobs[index :: (len(spare) + 1)] for index in range(len(spare) + 1)]
    children = []
    try:
        for index, (gpu, lease) in enumerate(spare, 1):
            job = dict(
                assets=plan["assets"],
                training_seed=run["seed"],
                point=point,
                directory=str(directory.relative_to(root)),
                stochastic=stochastic,
                jobs=shards[index],
                code_sources=plan["sources"],
                runtime_binding_id=plan["runtime_binding"]["id"],
            )
            job_path = directory / "public_jobs" / (str(index) + ".json")
            p.write_once(job_path, job)
            stream = (directory / (f"sampler_{index}.log")).open("x")
            env = dict(
                os.environ, CUDA_VISIBLE_DEVICES=gpu["uuid"], CUBLAS_WORKSPACE_CONFIG=":4096:8"
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(root / feedback.SCRIPT),
                    "--root",
                    str(root),
                    "--mode",
                    "generate",
                    "--job",
                    str(job_path),
                ],
                cwd=root,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                pass_fds=(lease.fileno(),),
            )
            children.append((process, lease, stream, gpu))
        feedback.generate_jobs(
            root,
            directory,
            shards[0],
            point,
            plan["assets"],
            model,
            tokenizer,
            theta=theta,
            stochastic=stochastic,
        )
        for process, _, _, _ in children:
            p.require(process.wait() == 0, "anchored_A.actual_sampling_worker_failure")
        records = [
            p.checked(
                p.read_json(directory / "completed" / (f"{job['index']:04d}.json")),
                "anchored_generated_trajectory",
            )
            for job in jobs
        ]
        p.require(
            all(
                row["job"] == job and row["point_id"] == point["id"]
                for row, job in zip(records, jobs, strict=True)
            ),
            "anchored_A.complete_fixed_generation_cohort",
        )
        manifest = p.record(
            "anchored_generation_manifest",
            complete=True,
            point_id=point["id"],
            stochastic=stochastic,
            tasks=plan["tasks"],
            source_manifest_id=plan["source_manifest_id"],
            trajectories=records,
            total_generate_calls=sum(row["actual_generate_calls"] for row in records),
            total_generated_tokens=sum(row["generated_tokens"] for row in records),
            actual_sampling_GPU_workers=1 + len(children),
            sealed_before_private_scoring=True,
            at=p.now(),
        )
        p.require(
            manifest["total_generate_calls"] <= len(jobs) * 32, "anchored_A.exact_sampling_budget"
        )
        p.write_once(directory / "generation_manifest.json", manifest)
    except BaseException:
        for process, _, _, _ in children:
            if process.poll() is None:
                process.terminate()
        for process, _, _, _ in children:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        for _, lease, stream, _ in children:
            lease.close()
            stream.close()
    with (directory / "private_scoring.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                str(root / feedback.SCRIPT),
                "--root",
                str(root),
                "--mode",
                "score",
                "--directory",
                str(directory),
                "--source-root",
                plan["private_scoring_source_root"],
            ],
            cwd=root,
            env=dict(os.environ, CUDA_VISIBLE_DEVICES=""),
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
        )
    return manifest, p.checked(
        p.read_json(directory / "scoring_report.json"), "anchored_independent_scoring"
    )


def examples_at_pi(cache, pi):
    counts = Counter((row["task_id"], row["state_id"]) for row in cache.packages)
    return [
        {
            **row,
            "coefficient_float": float(
                distribution.target_coefficient(
                    pi[row["task_id"]][row["state_id"]],
                    counts[row["task_id"], row["state_id"]],
                    row["whole_package_target_tokens"],
                )
            ),
        }
        for row in cache.packages
    ]


def save_vectors(path, vectors):
    save_file(
        {
            prefix + "/" + name: value.detach().cpu().contiguous()
            for prefix, entries in vectors.items()
            for name, value in entries.items()
        },
        str(path),
    )


def run_worker(root, run_key):
    root = Path(root).resolve()
    plan = p.checked(p.read_json(root / OUTPUT / "plan.json"), "anchored_registered_A_plan")
    run = next(row for row in plan["runs"] if row["key"] == run_key)
    out = root / OUTPUT / "runs" / run_key
    p.write_once(
        out / "started.json",
        p.record(
            "anchored_training_started",
            run=run,
            plan_id=plan["id"],
            pid=os.getpid(),
            GPU=os.environ["CUDA_VISIBLE_DEVICES"],
            at=p.now(),
        ),
    )
    step, stage, started = 0, "bind", time.monotonic()
    try:
        for path, expected in plan["sources"].items():
            p.require(p.sha(root / path) == expected, "anchored_A.frozen_loaded_implementation")
        p.require(
            views.binding() == plan["runtime_binding"],
            "anchored_A.original_bound_source_and_financial_runtime",
        )
        cache_root = root / plan["trajectory_cache"]["cache_root"]
        manifest = p.read_json(cache_root / "manifest.json")
        p.require(
            manifest["id"] == plan["trajectory_cache"]["manifest_id"],
            "anchored_A.bound_cache_manifest",
        )
        cache = trajectory_materials.load_pool(cache_root, manifest, "A")
        binding = p.read_json(root / gate.BASE / "material_binding/A.json")
        p.require(binding["id"] == plan["binding_id"], "anchored_A.exact_material_binding")
        classes.admit(
            cache, binding
        )  # Exactly once; no repeated package/mask validation in hot paths.
        pi, prior = copy.deepcopy(binding["prior"]), copy.deepcopy(binding["prior"])
        stage = "fresh_model"
        model, scope = trajectory_training.load_registered_student(
            plan["assets"]["base_binding"], run["seed"], trainable=True
        )
        p.require(
            components.adapter_digest(model) == plan["initial_adapter_digests"][str(run["seed"])],
            "anchored_A.exact_paired_fresh_initialization_not_Static_warmstart",
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = trajectory_training.optimizer_factory(
            list(names.values()), plan["training_configuration"]
        )
        tokenizer = load_tokenizer(plan["assets"]["tokenizer_binding"])
        p.require(not optimizer.state, "anchored_A.fresh_empty_Adam")
        schedule = plan["schedules"][str(run["seed"])]["batches"]
        p.write_once(
            out / "identity.json",
            p.record(
                "anchored_training_identity",
                run=run,
                plan_id=plan["id"],
                scope=scope,
                initial_adapter_digest=components.adapter_digest(model),
                original_configuration_id=plan["training_configuration"]["id"],
                cache_id=cache.cache_id,
                warmstart_from_Static_final=False,
                real_optimizer_updates=0,
            ),
        )
        rounds, updates, seen, totals = [], [], Counter(), Counter()
        for batch in schedule:
            step = batch["step"]
            if step in (0, 200):
                with outer_slot(root, run_key, step):
                    directory = out / "rounds" / ("epoch0" if step == 0 else "epoch5")
                    p.write_once(
                        directory / "started.json",
                        p.record(
                            "anchored_outer_round_started",
                            step=step,
                            actual_epoch=step // 40,
                            at=p.now(),
                        ),
                    )
                    p.require(
                        (step == 0 and not optimizer.state)
                        or (
                            step == 200
                            and len(optimizer.state) == len(names)
                            and all(
                                int(optimizer.state[value]["step"].item()) == 200
                                for value in names.values()
                            )
                        ),
                        "anchored_A.actual_current_optimizer_step_at_outer_boundary",
                    )
                    stage = "full_population_G"
                    with (directory / "class_gradient_events.jsonl").open("xb") as stream:

                        def class_event(event):
                            stream.write(p.encode(dict(at=p.now(), **event)) + b"\n")
                            if event["completed_packages"] % 25 == 0:
                                stream.flush()

                        population = classes._compute(
                            model, cache, pi, binding["mu"], event_sink=class_event
                        )
                    p.require(
                        population.accounting["packages"] == binding["training_packages"]
                        and population.accounting["states"] == binding["states"],
                        "anchored_A.full_original_population_not_diagnostic_G",
                    )
                    bound = adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
                    virtual = adam.virtual_step(bound, population.G)
                    theta = virtual["theta_bar"]
                    save_vectors(
                        directory / "real_point_and_optimizer.safetensors",
                        dict(
                            theta={r.name: r.theta for r in bound.parameters},
                            first_moment={r.name: r.first for r in bound.parameters},
                            second_moment={r.name: r.second for r in bound.parameters},
                        ),
                    )
                    p.write_once(
                        directory / "full_G.json",
                        p.record(
                            "anchored_actual_full_population_G",
                            accounting=population.accounting,
                            optimizer_snapshot=bound.snapshot,
                            virtual_step=virtual["diagnostics"],
                            G_digest=gate.tensor_digest(population.G),
                            control_tasks_included=True,
                            full_training_task_count=200,
                            pi=pi,
                            extra_work_not_inner_SFT=True,
                        ),
                    )
                    point = point_record(
                        root,
                        directory / "virtual_point",
                        model,
                        theta,
                        plan,
                        run,
                        step=step,
                        kind="virtual_full_population_step",
                        origin=virtual["diagnostics"]["id"],
                    )
                    stage = "registered360_generation_then_independent_scoring"
                    generated, scored = sample_and_score(
                        root,
                        directory / "feedback",
                        model,
                        tokenizer,
                        theta,
                        point,
                        plan,
                        run,
                        round_index=step // 200,
                        stochastic=True,
                    )
                    stage = "full_trajectory_gJ"
                    with (directory / "gJ_events.jsonl").open("xb") as stream:

                        def gradient_event(event):
                            stream.write(p.encode(dict(at=p.now(), **event)) + b"\n")
                            stream.flush()

                        gJ, feedback_report = feedback.feedback_gradient(
                            root, directory / "feedback", model, theta, event_sink=gradient_event
                        )
                    pullback = adam.pullback(
                        bound, population.G, {name: -value for name, value in gJ.items()}
                    )
                    contributions = population.centered(pi, binding["mu"], pullback["a"])
                    rewards = [
                        row["Q"] for row in sorted(scored["scores"], key=lambda row: row["index"])
                    ]
                    updated = distribution.update_distribution(
                        pi,
                        prior,
                        contributions["C"],
                        binding["mu"],
                        rewards,
                        control_tasks=binding["control_tasks"],
                        condition=run["condition"],
                        registered_complete=True,
                    )
                    save_vectors(
                        directory / "G_gJ_a.safetensors",
                        dict(G=population.G, gJ=gJ, a=pullback["a"]),
                    )
                    for filename, value in (
                        ("gJ", feedback_report),
                        ("pullback", pullback["diagnostics"]),
                        ("C", contributions),
                        ("distribution_update", updated),
                    ):
                        p.write_once(directory / (filename + ".json"), value)
                    adam._verify(bound)
                    p.require(
                        gate.tensor_digest(theta) == point["parameter_digest"],
                        "anchored_A.virtual_point_unchanged_through_feedback",
                    )
                    pi = updated["pi_next"]
                    summary = p.record(
                        "anchored_complete_outer_round",
                        step=step,
                        point_id=point["id"],
                        full_G=True,
                        feedback_manifest_id=generated["id"],
                        actual_feedback_sessions=360,
                        actual_generate_calls=generated["total_generate_calls"],
                        qualified=scored["qualified"],
                        denominator=360,
                        gJ_id=feedback_report["id"],
                        C_id=contributions["id"],
                        update_id=updated["id"],
                        update_status=updated["status"],
                        novelty_active=updated["novelty_active"],
                        real_parameter_or_optimizer_updated_by_feedback=False,
                        at=p.now(),
                    )
                    p.write_once(directory / "report.json", summary)
                    rounds.append(summary)
                    del population, bound, virtual, theta, gJ, pullback
                    gc.collect()
                    torch.cuda.empty_cache()
                    examples = examples_at_pi(cache, pi)
                    by_task = defaultdict(list)
                    for index, row in enumerate(examples):
                        by_task[row["task_id"]].append((index, row))
            stage = "inner_SFT"
            chosen = [
                row
                for _, row in sorted(
                    (value for task in batch["task_ids"] for value in by_task[task]),
                    key=lambda row: row[0],
                )
            ]
            details = {
                **batch,
                "tasks": [
                    dict(task_id=task, group=plan["training_groups"][task])
                    for task in batch["task_ids"]
                ],
            }
            directory = out / "updates" / f"{step + 1:04d}"
            p.write_once(
                directory / "started.json",
                p.record("anchored_real_update_started", step=step + 1, at=p.now()),
            )
            model.train()
            with (directory / "events.jsonl").open("xb") as stream:

                def training_event(event):
                    stream.write(p.encode(dict(at=p.now(), **event)) + b"\n")

                update = inner.execute_update(
                    model,
                    optimizer,
                    chosen,
                    details,
                    pool="A",
                    arm=run["condition"],
                    device="cuda:0",
                    trajectory_cache=cache,
                    event_sink=training_event,
                )
                stream.flush()
                os.fsync(stream.fileno())
            p.write_once(directory / "report.json", update)
            seen.update(row["package_id"] for row in chosen)
            totals.update(
                {
                    key: update[key]
                    for key in (
                        "target_tokens",
                        "sequence_tokens",
                        "rows_completed",
                        "packages_completed",
                    )
                }
            )
            updates.append(update["id"])
            print(
                json.dumps(
                    dict(
                        event="real_optimizer_update",
                        run=run_key,
                        completed=step + 1,
                        total=400,
                        at=p.now(),
                    )
                ),
                flush=True,
            )
        p.require(
            len(updates) == 400
            and seen == Counter({row["package_id"]: 10 for row in cache.packages})
            and totals["target_tokens"] == cache.actual_budget["target_tokens_all_epochs"]
            and totals["sequence_tokens"] == cache.actual_budget["sequence_tokens_all_epochs"],
            "anchored_A.exact_full_ten_pass_SFT_dose",
        )
        stage = "sole_final_checkpoint_and_greedy180"
        theta = {name: value.detach().clone() for name, value in names.items()}
        final = point_record(
            root,
            out / "final",
            model,
            theta,
            plan,
            run,
            step=400,
            kind="sole_final_epoch10",
            origin=updates[-1],
        )
        p.write_once(
            out / "training_report.json",
            p.record(
                "anchored_completed_training",
                run=run,
                actual_complete=True,
                real_optimizer_updates=400,
                epochs=10,
                totals=dict(totals),
                final_point_id=final["id"],
                rounds=rounds,
                original_cache_id=cache.cache_id,
                unique_final_checkpoint=True,
                at=p.now(),
            ),
        )
        generation, scores = sample_and_score(
            root,
            out / "final_greedy",
            model,
            tokenizer,
            theta,
            final,
            plan,
            run,
            round_index=2,
            stochastic=False,
        )
        report = p.record(
            "anchored_A_run_report",
            run=run,
            plan_id=plan["id"],
            status="COMPLETE_FIXED_FINAL",
            rounds=rounds,
            actual_optimizer_updates=400,
            actual_feedback_sessions=720,
            final_greedy_sessions=180,
            final_qualified=scores["qualified"],
            denominator=180,
            final_point_id=final["id"],
            final_assessment_report_id=scores["id"],
            actual_generate_calls=generation["total_generate_calls"]
            + sum(row["actual_generate_calls"] for row in rounds),
            development_participated_in_meta_learning=True,
            elapsed_seconds=time.monotonic() - started,
            at=p.now(),
        )
        p.write_once(out / "report.json", report)
        return report
    except BaseException as failure:
        traceback.print_exc()
        p.write_once(
            out / "failure.json",
            p.record(
                "anchored_A_run_failure",
                run=run,
                plan_id=plan["id"],
                step=step,
                stage=stage,
                error_type=type(failure).__name__,
                error=str(failure),
                automatic_retry=False,
                partial_feedback_not_zero_reward=True,
                at=p.now(),
            ),
        )
        raise


def _coordinate(root):
    root = Path(root).resolve()
    out = root / OUTPUT
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_registered_A_plan")
    p.write_once(
        out / "coordinator_started.json",
        p.record("anchored_A_coordinator_started", pid=os.getpid(), at=p.now()),
    )
    active, next_index = [], 0
    global _OWNED
    _OWNED = active
    while next_index < len(plan["runs"]) or active:
        for process, lease, stream, run in list(active):
            if process.poll() is not None:
                p.require(
                    process.returncode == 0, "anchored_A.run_failed_no_new_release:" + run["key"]
                )
                lease.close()
                stream.close()
                active.remove((process, lease, stream, run))
        publication.milestones(root, OUTPUT, plan)
        ready = (
            next_index == 0
            or (
                publication.completed_json(
                    out / "runs" / plan["runs"][next_index - 1]["key"] / "updates/0001/report.json"
                )
            )
            is not None
        )
        if (
            next_index < len(plan["runs"])
            and ready
            and host_memory()["MemAvailable_bytes"] >= MIN_HOST_BYTES
        ):
            admitted = claim_gpus(root, maximum=1)
            if admitted:
                gpu, lease = admitted[0]
                run = plan["runs"][next_index]
                stream = (out / (run["key"] + ".log")).open("x")
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(root / SCRIPT),
                        "--root",
                        str(root),
                        "--mode",
                        "worker",
                        "--run-key",
                        run["key"],
                    ],
                    cwd=root,
                    env=dict(
                        os.environ,
                        CUDA_VISIBLE_DEVICES=gpu["uuid"],
                        CUBLAS_WORKSPACE_CONFIG=":4096:8",
                    ),
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    pass_fds=(lease.fileno(),),
                    start_new_session=True,
                )
                active.append((process, lease, stream, run))
                p.write_once(
                    out / "launches" / (run["key"] + ".json"),
                    p.record(
                        "anchored_A_run_launch", run=run, gpu=gpu, pid=process.pid, at=p.now()
                    ),
                )
                next_index += 1
        if next_index < len(plan["runs"]) or active:
            time.sleep(30)
    runs = [p.read_json(out / "runs" / row["key"] / "report.json") for row in plan["runs"]]
    original = p.read_json(root / GIVEN / "report.json")
    baseline = sum(
        row["qualified"]
        for row in original["models"]
        if row["model_key"] in {"A_alpha0_11", "A_alpha0_29", "A_alpha0_47"}
    )
    full = sum(row["final_qualified"] for row in runs if row["run"]["condition"] == CONDITIONS[0])
    c_only = sum(row["final_qualified"] for row in runs if row["run"]["condition"] == CONDITIONS[1])
    report = p.record(
        "anchored_A_complete_matrix",
        plan_id=plan["id"],
        status="COMPLETE_SIX_NEW_A_RUNS",
        runs=[
            {
                key: value[key]
                for key in ("run", "id", "final_qualified", "denominator", "actual_generate_calls")
            }
            for value in runs
        ],
        B_or_confirmation_started=False,
        no_C_only_candidate_substitution=True,
        Static_qualified=baseline,
        Full_qualified=full,
        C_only_qualified=c_only,
        denominator_per_condition=540,
        primary_mean_difference=(full - baseline) / 540,
        primary_direction="POSITIVE_DEVELOPMENT_REQUIRES_NEW_AUTHORIZATION"
        if full > baseline
        else "RETAIN_STATIC_NO_POSITIVE_FULL_DIRECTION",
        at=p.now(),
    )
    p.write_once(out / "report.json", report)
    publication.publish(root, OUTPUT, "complete_A_matrix", report)
    return report


def coordinate(root):
    try:
        return _coordinate(Path(root).resolve())
    except BaseException as failure:
        for process, _, _, _ in _OWNED:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process, lease, stream, _ in _OWNED:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            lease.close()
            stream.close()
        p.write_once(
            Path(root) / OUTPUT / "coordinator_failure.json",
            p.record(
                "anchored_A_coordinator_failure",
                error_type=type(failure).__name__,
                error=str(failure),
                stopped_only_own_registered_run_groups=True,
                raw_artifacts_preserved=True,
                automatic_retry=False,
                at=p.now(),
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "coordinate", "worker"), required=True)
    parser.add_argument("--run-key")
    args = parser.parse_args()
    result = (
        prepare(args.root)
        if args.mode == "prepare"
        else run_worker(args.root, args.run_key)
        if args.mode == "worker"
        else coordinate(args.root)
    )
    print(json.dumps({key: result[key] for key in ("id", "status") if key in result}))
