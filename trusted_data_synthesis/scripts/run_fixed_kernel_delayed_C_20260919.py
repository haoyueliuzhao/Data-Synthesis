"""Conditionally admitted timing ablation: Static first200, one C update, last200."""

# ruff: noqa: E501 -- explicit frozen budgets, identity and scientific scope
import argparse
import copy
import gc
import json
import os
import random
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import fixed_kernel_proxy_direction_20260919 as direction
import fixed_kernel_proxy_inputs_20260919 as inputs
import fixed_kernel_proxy_numeric_20260919 as numeric
import numpy as np
import run_fixed_kernel_anchored_training_20260916 as old
import run_fixed_kernel_proxy_audit_20260919 as audit
import torch

p = old.p
OUTPUT = inputs.BASE + "/delayed_C_20260919"
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delayed_C_20260919.py"
SOURCES = sorted(set(audit.SOURCES + [SCRIPT]))


def is_distribution_step(step):
    return step == 200


def registration(parent, audit_plan_id):
    inherited = (
        "assets",
        "trajectory_cache",
        "initial_adapter_digests",
        "schedules",
        "training_groups",
        "source_manifest_id",
        "tasks",
        "private_scoring_source_root",
        "runtime_binding",
        "training_configuration",
        "binding_id",
    )
    return dict(
        **{key: copy.deepcopy(parent[key]) for key in inherited},
        parent_plan_id=parent["id"],
        required_proxy_audit_plan_id=audit_plan_id,
        runs=[
            dict(key=f"A_delayed_c_{seed}", seed=seed, pool="A", condition="delayed_c_only")
            for seed in (11, 29, 47)
        ],
        outer_steps=[200],
        epochs=10,
        real_updates_per_run=400,
        new_training_runs=3,
        first_200_steps_exact_pi0=True,
        old_Adam_expression_preserved=True,
        stable_reference_guard_at_new_point=True,
        fresh_initialization_and_empty_Adam=True,
        no_old_checkpoint_or_RNG_resume=True,
        primary_candidate="Delayed-C",
        primary_comparison="Delayed-C minus Static",
        auxiliary_comparison="Delayed-C minus original C-only",
        numerical_core_condition="c_only_anchored",
        feedback_seed_round_index=1,
        new_feedback_sessions=1080,
        new_final_greedy_sessions=540,
        new_sessions_total=1620,
        new_generate_cap=51840,
        new_optimizer_updates=1200,
        SFT_sequence_tokens=538268970,
        SFT_supervision_tokens=29758320,
        extra_class_passes=3,
        extra_class_sequence_tokens=53826897,
        maximum_parallel_training_workers=3,
        maximum_parallel_outer_workers=1,
        B_and_confirmation=0,
        source_utility_is_not_independent_confirmation=True,
        no_Full_or_Novelty_success_relabel=True,
        no_third_round_or_budget_escalation=True,
        release_state="CONDITIONAL_WAIT_FOR_COMPLETED_PROXY_AUDIT",
    )


def prepare(root):
    root = Path(root).resolve()
    out = root / OUTPUT
    p.require(not (out / "plan.json").exists(), "delayed.one_registration")
    parent = p.checked(
        p.read_json(root / inputs.PARENT / "plan.json"), "anchored_registered_A_plan"
    )
    proxy = p.checked(p.read_json(root / inputs.OUTPUT / "plan.json"), "anchored_proxy_audit_plan")
    fields = registration(parent, proxy["id"])
    plan = p.record(
        "delayed_C_registered_plan",
        **fields,
        numeric_limits=proxy["numeric_limits"],
        sources={path: p.sha(root / path) for path in SOURCES},
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        at=p.now(),
    )
    p.write_once(out / "plan.json", plan)
    public = p.record(
        "delayed_C_public_registration",
        plan_id=plan["id"],
        required_proxy_audit_plan_id=proxy["id"],
        runs=fields["runs"],
        outer_steps=[200],
        fresh_full_400_steps=True,
        primary_comparison=fields["primary_comparison"],
        new_training_runs=3,
        new_optimizer_updates=1200,
        new_feedback_sessions=1080,
        new_final_greedy_sessions=540,
        new_generate_cap=51840,
        B_and_confirmation=0,
        training_started=False,
    )
    p.write_once(out / "public_plan.json", public)
    print(
        json.dumps(
            dict(plan_id=plan["id"], state=fields["release_state"], new_training_started=False)
        ),
        flush=True,
    )


def get_admission(root, plan):
    root = Path(root).resolve()
    report = old.publication.completed_json(root / inputs.OUTPUT / "report.json")
    if report is None:
        p.require(
            not (root / inputs.OUTPUT / "coordinator_failure.json").exists(),
            "delayed.proxy_audit_failed_no_training_release",
        )
        return None
    p.checked(report, "anchored_proxy_audit_report")
    p.require(
        report["plan_id"] == plan["required_proxy_audit_plan_id"]
        and report["status"] == "PASS_AS_SCOPED_READY_FOR_DELAYED_C"
        and report["all_twelve_numeric_points_passed"]
        and report["direction_audit_completed"],
        "delayed.requires_completed_numeric_and_direction_admission",
    )
    return report


def by_task_at_pi(cache, pi):
    result = defaultdict(list)
    for index, row in enumerate(old.examples_at_pi(cache, pi)):
        result[row["task_id"]].append((index, row))
    return result


def new_point_numeric_guard(population, bound, gJ, a, C, updated, pi, binding, qualified, limits):
    blocks, cursor = [], 0
    for parameter in bound.parameters:
        size = parameter.theta.numel()
        blocks.append(
            dict(
                name=parameter.name,
                start=cursor,
                stop=cursor + size,
                shape=list(parameter.theta.shape),
                step=parameter.step,
                group=parameter.group,
            )
        )
        cursor += size

    def flat(values):
        return torch.cat(
            [values[parameter.name].detach().cpu().reshape(-1) for parameter in bound.parameters]
        )

    first = torch.cat(
        [parameter.first.detach().cpu().reshape(-1) for parameter in bound.parameters]
    )
    second = torch.cat(
        [parameter.second.detach().cpu().reshape(-1) for parameter in bound.parameters]
    )
    reference, diagnostics = numeric.pullback(
        flat(population.G),
        first,
        second,
        -flat(gJ),
        blocks,
        bound.groups,
        dict(max_norm=bound.clip_max_norm, epsilon=bound.clip_epsilon),
    )
    geometry = direction.Geometry(
        population.keys, pi, binding["prior"], binding["mu"], binding["control_tasks"]
    )
    reference_C = direction.project(population.matrix, reference, population.keys, geometry)[:, 0]
    comparison = geometry.compare_C(reference_C, geometry.flatten(C))
    reference_pi, status = geometry.propose(reference_C, "c_only_anchored", qualified)
    TV = geometry.TV(reference_pi, geometry.flatten(updated["pi_next"]))
    passed = (
        comparison["relative_weighted_RMS"] <= limits["relative_weighted_C_RMS"]
        and TV <= limits["weighted_pi_TV"]
    )
    return p.record(
        "delayed_new_point_numeric_guard",
        passed=passed,
        step=200,
        original_Adam_used_for_actual_update=True,
        reference_not_substituted=True,
        original_a_vs_reference=numeric.compare(flat(a), reference),
        C_comparison=comparison,
        pi_reference_weighted_TV=TV,
        positive_reward_terms=qualified,
        proposal_status=status,
        stable_reference=diagnostics,
    )


def outer_round(root, out, plan, run, model, tokenizer, optimizer, names, cache, binding, pi):
    p.require(pi == binding["prior"], "delayed.first_five_epochs_exactly_Static_pi0")
    p.require(
        len(optimizer.state) == len(names)
        and all(int(optimizer.state[value]["step"].item()) == 200 for value in names.values()),
        "delayed.actual_nonempty_Adam_step200",
    )
    directory = out / "rounds/epoch5"
    p.write_once(
        directory / "started.json", p.record("delayed_outer_started", step=200, at=p.now())
    )
    # This is a fresh-run prefix record, not an assertion that old snapshots had RNG.
    torch.save(
        dict(
            cpu=torch.get_rng_state(),
            cuda=torch.cuda.get_rng_state_all(),
            python=random.getstate(),
            numpy=np.random.get_state(),
            schedule_cursor=200,
        ),
        directory / "prefix_RNG.pt",
    )
    with (directory / "class_gradient_events.jsonl").open("xb") as stream:

        def event(value):
            stream.write(p.encode(dict(at=p.now(), **value)) + b"\n")
            if value["completed_packages"] % 25 == 0:
                stream.flush()

        population = old.classes._compute(model, cache, pi, binding["mu"], event_sink=event)
    p.require(
        population.accounting["packages"] == 3547 and population.accounting["states"] == 1681,
        "delayed.complete_population_G",
    )
    bound = old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    virtual = old.adam.virtual_step(bound, population.G)
    theta = virtual["theta_bar"]
    old.save_vectors(
        directory / "real_point_and_optimizer.safetensors",
        dict(
            theta={v.name: v.theta for v in bound.parameters},
            first_moment={v.name: v.first for v in bound.parameters},
            second_moment={v.name: v.second for v in bound.parameters},
        ),
    )
    p.write_once(
        directory / "full_G.json",
        p.record(
            "delayed_actual_G",
            accounting=population.accounting,
            optimizer_snapshot=bound.snapshot,
            virtual_step=virtual["diagnostics"],
            G_digest=old.gate.tensor_digest(population.G),
            pi=pi,
            real_completed_updates=200,
            first_distribution_update=True,
        ),
    )
    point = old.point_record(
        root,
        directory / "virtual_point",
        model,
        theta,
        plan,
        run,
        step=200,
        kind="delayed_single_virtual_step",
        origin=virtual["diagnostics"]["id"],
    )
    generated, scored = old.sample_and_score(
        root,
        directory / "feedback",
        model,
        tokenizer,
        theta,
        point,
        plan,
        run,
        round_index=1,
        stochastic=True,
    )
    with (directory / "gJ_events.jsonl").open("xb") as stream:

        def event(value):
            stream.write(p.encode(dict(at=p.now(), **value)) + b"\n")
            stream.flush()

        gJ, feedback_report = old.feedback.feedback_gradient(
            root, directory / "feedback", model, theta, event_sink=event
        )
    pullback = old.adam.pullback(bound, population.G, {name: -value for name, value in gJ.items()})
    contributions = population.centered(pi, binding["mu"], pullback["a"])
    rewards = [row["Q"] for row in sorted(scored["scores"], key=lambda row: row["index"])]
    updated = old.distribution.update_distribution(
        pi,
        binding["prior"],
        contributions["C"],
        binding["mu"],
        rewards,
        control_tasks=binding["control_tasks"],
        condition="c_only_anchored",
        registered_complete=True,
    )
    guard = new_point_numeric_guard(
        population,
        bound,
        gJ,
        pullback["a"],
        contributions["C"],
        updated,
        pi,
        binding,
        scored["qualified"],
        plan["numeric_limits"],
    )
    old.save_vectors(directory / "G_gJ_a.safetensors", dict(G=population.G, gJ=gJ, a=pullback["a"]))
    for name, value in (
        ("gJ", feedback_report),
        ("pullback", pullback["diagnostics"]),
        ("C", contributions),
        ("distribution_update", updated),
        ("numeric_guard", guard),
    ):
        p.write_once(directory / (name + ".json"), value)
    p.require(guard["passed"], "delayed.material_numeric_difference_STOP_no_formula_switch")
    old.adam._verify(bound)
    p.require(
        old.gate.tensor_digest(theta) == point["parameter_digest"],
        "delayed.same_virtual_point_through_feedback",
    )
    report = p.record(
        "delayed_completed_outer",
        run=run,
        step=200,
        feedback_sessions=360,
        qualified=scored["qualified"],
        denominator=360,
        generate_calls=generated["total_generate_calls"],
        feedback_report_id=feedback_report["id"],
        C_id=contributions["id"],
        distribution_update_id=updated["id"],
        numeric_guard_id=guard["id"],
        update_status=updated["status"],
        novelty_term_used=False,
        no_direct_policy_gradient_student_step=True,
        at=p.now(),
    )
    p.write_once(directory / "report.json", report)
    result = updated["pi_next"]
    del population, bound, virtual, theta, gJ, pullback
    gc.collect()
    torch.cuda.empty_cache()
    return result, report


def worker(root, key):
    root = Path(root).resolve()
    old.OUTPUT = OUTPUT
    plan = p.checked(p.read_json(root / OUTPUT / "plan.json"), "delayed_C_registered_plan")
    admitted = get_admission(root, plan)
    p.require(admitted is not None, "delayed.no_worker_before_audit_gate")
    for path, digest in plan["sources"].items():
        p.require(p.sha(root / path) == digest, "delayed.frozen_loaded_implementation")
    run = next(r for r in plan["runs"] if r["key"] == key)
    out = root / OUTPUT / "runs" / key
    p.write_once(
        out / "started.json",
        p.record(
            "delayed_training_started",
            run=run,
            audit_report_id=admitted["id"],
            pid=os.getpid(),
            at=p.now(),
        ),
    )
    started, stage = time.monotonic(), "load_fresh_original_material_and_model"
    try:
        binding = p.read_json(root / inputs.BASE / "material_binding/A.json")
        p.require(binding["id"] == plan["binding_id"], "delayed.unchanged_material_binding")
        cache_root = root / plan["trajectory_cache"]["cache_root"]
        cache = old.trajectory_materials.load_pool(
            cache_root, p.read_json(cache_root / "manifest.json"), "A"
        )
        old.classes.admit(cache, binding)
        model, scope = old.trajectory_training.load_registered_student(
            plan["assets"]["base_binding"], run["seed"], trainable=True
        )
        p.require(
            old.components.adapter_digest(model)
            == plan["initial_adapter_digests"][str(run["seed"])],
            "delayed.original_paired_initialization",
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = old.trajectory_training.optimizer_factory(
            list(names.values()), plan["training_configuration"]
        )
        p.require(not optimizer.state, "delayed.empty_Adam_no_resume")
        tokenizer = old.load_tokenizer(plan["assets"]["tokenizer_binding"])
        p.write_once(
            out / "identity.json",
            p.record(
                "delayed_training_identity",
                run=run,
                plan_id=plan["id"],
                scope=scope,
                initial_adapter_digest=old.components.adapter_digest(model),
                original_configuration_id=plan["training_configuration"]["id"],
                old_checkpoint_resumed=False,
                first_200_steps_pi0=True,
            ),
        )
        pi = copy.deepcopy(binding["prior"])
        by_task = by_task_at_pi(cache, pi)
        updates, totals, seen, rounds = [], Counter(), Counter(), []
        for batch in plan["schedules"][str(run["seed"])]["batches"]:
            step = batch["step"]
            if is_distribution_step(step):
                stage = "single_epoch5_outer"
                with old.outer_slot(root, key, step):
                    pi, report = outer_round(
                        root, out, plan, run, model, tokenizer, optimizer, names, cache, binding, pi
                    )
                    rounds.append(report)
                    by_task = by_task_at_pi(cache, pi)
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
                p.record("delayed_real_update_started", step=step + 1, at=p.now()),
            )
            model.train()
            with (directory / "events.jsonl").open("xb") as stream:

                def event(value):
                    stream.write(p.encode(dict(at=p.now(), **value)) + b"\n")

                update = old.inner.execute_update(
                    model,
                    optimizer,
                    chosen,
                    details,
                    pool="A",
                    arm="delayed_c_only",
                    device="cuda:0",
                    trajectory_cache=cache,
                    event_sink=event,
                )
                stream.flush()
                os.fsync(stream.fileno())
            p.write_once(directory / "report.json", update)
            seen.update(row["package_id"] for row in chosen)
            totals.update(
                {
                    name: update[name]
                    for name in (
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
                        run=key,
                        completed=step + 1,
                        total=400,
                        at=p.now(),
                    )
                ),
                flush=True,
            )
        p.require(
            len(updates) == 400
            and len(rounds) == 1
            and seen == Counter({row["package_id"]: 10 for row in cache.packages})
            and totals["target_tokens"] == cache.actual_budget["target_tokens_all_epochs"]
            and totals["sequence_tokens"] == cache.actual_budget["sequence_tokens_all_epochs"],
            "delayed.fixed_ten_pass_dose",
        )
        stage = "sole_final_checkpoint_and_greedy180"
        theta = {name: value.detach().clone() for name, value in names.items()}
        final = old.point_record(
            root,
            out / "final",
            model,
            theta,
            plan,
            run,
            step=400,
            kind="sole_delayed_epoch10_final",
            origin=updates[-1],
        )
        p.write_once(
            out / "training_report.json",
            p.record(
                "delayed_completed_training",
                run=run,
                real_optimizer_updates=400,
                epochs=10,
                totals=dict(totals),
                final_point_id=final["id"],
                rounds=rounds,
                unique_final_checkpoint=True,
                at=p.now(),
            ),
        )
        generated, scored = old.sample_and_score(
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
        calls = generated["total_generate_calls"] + rounds[0]["generate_calls"]
        p.require(calls <= 17280, "delayed.per_run_generate_cap")
        p.write_once(
            out / "report.json",
            p.record(
                "delayed_C_run_report",
                run=run,
                plan_id=plan["id"],
                status="COMPLETE_FIXED_FINAL",
                actual_optimizer_updates=400,
                feedback_sessions=360,
                final_greedy_sessions=180,
                final_qualified=scored["qualified"],
                denominator=180,
                actual_generate_calls=calls,
                final_point_id=final["id"],
                final_assessment_report_id=scored["id"],
                outer_report_id=rounds[0]["id"],
                elapsed_seconds=time.monotonic() - started,
                at=p.now(),
            ),
        )
    except Exception as failure:
        p.write_once(
            out / "failure.json",
            p.record(
                "delayed_C_failure",
                run=run,
                stage=stage,
                error=repr(failure),
                traceback=traceback.format_exc(),
                automatic_retry=False,
                at=p.now(),
            ),
        )
        raise


def milestones(root, plan):
    for run in plan["runs"]:
        out = root / OUTPUT / "runs" / run["key"]
        outer = old.publication.completed_json(out / "rounds/epoch5/report.json")
        actual = old.publication.completed_json(out / "updates/0201/report.json")
        if outer and actual:
            audit.publish(
                root,
                OUTPUT,
                run["key"] + "_epoch5",
                p.record(
                    "delayed_public_outer",
                    run=run,
                    actual_Student_updates_completed_at_milestone=201,
                    random_qualified=outer["qualified"],
                    denominator=360,
                    outer_report_id=outer["id"],
                    numeric_guard_id=outer["numeric_guard_id"],
                    novelty_term_used=False,
                    new_feedback_sessions=360,
                ),
                "Delayed-C首次分布更新发生在真实step200，已接入第201次训练更新；随机反馈不是最终greedy成绩。",
            )
        final = old.publication.completed_json(out / "report.json")
        if final:
            audit.publish(
                root,
                OUTPUT,
                run["key"] + "_final",
                final,
                "Delayed-C唯一epoch10最终检查点；主比较仍为Static。该开发集参与元优化，不是独立确认，也不改写旧Full结果。",
            )


def coordinate(root):
    root = Path(root).resolve()
    old.OUTPUT = OUTPUT
    out = root / OUTPUT
    plan = p.checked(p.read_json(out / "plan.json"), "delayed_C_registered_plan")
    p.write_once(
        out / "coordinator_started.json",
        p.record(
            "delayed_C_coordinator_started", pid=os.getpid(), at=p.now(), training_started=False
        ),
    )
    active, cursor = [], 0
    try:
        while get_admission(root, plan) is None:
            print(
                json.dumps(
                    dict(
                        event="waiting_for_completed_proxy_audit",
                        new_training_started=False,
                        at=p.now(),
                    )
                ),
                flush=True,
            )
            time.sleep(30)
        admitted = get_admission(root, plan)
        p.write_once(
            out / "admission.json",
            p.record(
                "delayed_C_actual_admission",
                audit_report_id=admitted["id"],
                plan_id=plan["id"],
                at=p.now(),
            ),
        )
        while cursor < len(plan["runs"]) or active:
            for process, lease, stream, key in list(active):
                if process.poll() is not None:
                    p.require(process.returncode == 0, "delayed.run_failed_no_retry:" + key)
                    lease.close()
                    stream.close()
                    active.remove((process, lease, stream, key))
            milestones(root, plan)
            if (
                cursor < len(plan["runs"])
                and len(active) < 3
                and old.host_memory()["MemAvailable_bytes"] >= 256 * 2**30
            ):
                candidates = old.claim_gpus(root, maximum=1)
                if candidates:
                    gpu, lease = candidates[0]
                    key = plan["runs"][cursor]["key"]
                    stream = (out / (key + ".log")).open("x")
                    env = dict(
                        os.environ,
                        CUDA_VISIBLE_DEVICES=gpu["uuid"],
                        CUBLAS_WORKSPACE_CONFIG=":4096:8",
                        OMP_NUM_THREADS="2",
                        OPENBLAS_NUM_THREADS="2",
                        MKL_NUM_THREADS="2",
                        TOKENIZERS_PARALLELISM="false",
                    )
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            str(root / SCRIPT),
                            "--root",
                            str(root),
                            "--mode",
                            "worker",
                            "--run",
                            key,
                        ],
                        cwd=root,
                        env=env,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        pass_fds=(lease.fileno(),),
                        start_new_session=True,
                    )
                    active.append((process, lease, stream, key))
                    p.write_once(
                        out / "launches" / (key + ".json"),
                        p.record(
                            "delayed_C_launch",
                            run=plan["runs"][cursor],
                            pid=process.pid,
                            gpu=gpu,
                            at=p.now(),
                        ),
                    )
                    cursor += 1
            if cursor < len(plan["runs"]) or active:
                time.sleep(20)
        reports = [p.read_json(out / "runs" / run["key"] / "report.json") for run in plan["runs"]]
        parent_matrix = p.read_json(root / inputs.PARENT / "report.json")
        qualified = sum(row["final_qualified"] for row in reports)
        calls = sum(row["actual_generate_calls"] for row in reports)
        p.require(
            sum(row["actual_optimizer_updates"] for row in reports) == 1200
            and sum(row["feedback_sessions"] for row in reports) == 1080
            and sum(row["final_greedy_sessions"] for row in reports) == 540
            and calls <= 51840,
            "delayed.complete_new_budget",
        )
        final = p.record(
            "delayed_C_matrix",
            plan_id=plan["id"],
            status="COMPLETE_THREE_DELAYED_C_RUNS",
            Delayed_C_qualified=qualified,
            Static_qualified=parent_matrix["Static_qualified"],
            original_C_only_qualified=parent_matrix["C_only_qualified"],
            original_Full_qualified=parent_matrix["Full_qualified"],
            denominator_per_condition=540,
            primary_mean_difference=(qualified - parent_matrix["Static_qualified"]) / 540,
            auxiliary_mean_difference=(qualified - parent_matrix["C_only_qualified"]) / 540,
            primary_direction="POSITIVE_FIXED_DEV_DELAYED_DIRECTION"
            if qualified > parent_matrix["Static_qualified"]
            else "RETAIN_STATIC_NO_POSITIVE_DELAYED_DIRECTION",
            no_Full_or_Novelty_success_relabel=True,
            B_or_confirmation_started=False,
            development_is_not_independent_confirmation=True,
            actual_optimizer_updates=1200,
            actual_feedback_sessions=1080,
            actual_final_greedy_sessions=540,
            actual_generate_calls=calls,
            runs=[
                dict(run=row["run"], qualified=row["final_qualified"], report_id=row["id"])
                for row in reports
            ],
            at=p.now(),
        )
        p.write_once(out / "report.json", final)
        audit.publish(
            root,
            OUTPUT,
            "complete_delayed_C_matrix",
            final,
            "三项Delayed-C按固定剂量完成，主比较不变，旧Full负结果保留。无论是否正差，都没有自动启动B/确认、扩大预算或第三轮反馈。",
        )
    except Exception as failure:
        for process, _, _, _ in active:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        p.write_once(
            out / "coordinator_failure.json",
            p.record(
                "delayed_C_coordinator_failure",
                error=repr(failure),
                traceback=traceback.format_exc(),
                training_runs_released=cursor,
                B_and_confirmation=0,
                at=p.now(),
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "coordinate", "worker"), required=True)
    parser.add_argument("--run")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.root)
    elif args.mode == "coordinate":
        coordinate(args.root)
    else:
        worker(args.root, args.run)
