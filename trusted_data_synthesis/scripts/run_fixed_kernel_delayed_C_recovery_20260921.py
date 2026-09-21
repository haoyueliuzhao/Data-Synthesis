"""Append-only recovery of two resource-interrupted runs, not a new seed search."""

# ruff: noqa: E501 -- explicit scientific lineage and recovery accounting
import argparse
import copy
import gc
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

import fixed_kernel_delayed_C_recovery_state_20260921 as s
import run_fixed_kernel_delayed_C_20260919 as d
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

p, old = d.p, d.old
OUTPUT, RAW = s.OUTPUT, s.RAW
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delayed_C_recovery_20260921.py"
STATE_SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_delayed_C_recovery_state_20260921.py"


def emit(value):
    print(json.dumps(dict(at=p.now(), **value)), flush=True)


def prepare(root):
    original = root / d.OUTPUT
    parent = p.checked(p.read_json(original / "plan.json"), "delayed_C_registered_plan")
    failure = p.checked(
        p.read_json(original / "coordinator_failure.json"), "delayed_C_coordinator_failure"
    )
    finished = p.checked(
        p.read_json(original / "runs/A_delayed_c_11/report.json"), "delayed_C_run_report"
    )
    p.require(finished["status"] == "COMPLETE_FIXED_FINAL", "recovery.keep_completed_seed11")
    completed = {}
    for seed in (11, 29, 47):
        reports = sorted(
            (original / "runs" / f"A_delayed_c_{seed}" / "updates").glob("*/report.json")
        )
        p.require(
            [int(path.parent.name) for path in reports] == list(range(1, len(reports) + 1)),
            "recovery.contiguous_original_updates",
        )
        completed[seed] = len(reports)
    frozen = {}
    for run in (r for r in parent["runs"] if r["seed"] in (29, 47)):
        directory = original / "runs" / run["key"] / "rounds/epoch5"
        s.prefix(directory)
        paths = [
            "full_G.json",
            "real_point_and_optimizer.safetensors",
            "prefix_RNG.pt",
            "virtual_point/adapter.safetensors",
            "virtual_point/point.json",
            "feedback/generation_manifest.json",
            "feedback/scoring_report.json",
        ]
        if run["seed"] == 47:
            paths += [
                "report.json",
                "numeric_guard.json",
                "distribution_update.json",
                "G_gJ_a.safetensors",
            ]
        for relative in paths:
            path = directory / relative
            frozen[str(path.relative_to(root))] = p.sha(path)
        generated = p.read_json(directory / "feedback/generation_manifest.json")
        scored = p.read_json(directory / "feedback/scoring_report.json")
        p.require(
            generated["complete"]
            and scored["complete"]
            and scored["denominator"] == 360
            and len(generated["trajectories"]) == 360
            and scored["generation_manifest_id"] == generated["id"],
            "recovery.reuse_complete_feedback_only",
        )
    sources = dict(parent["sources"])
    for path, digest in sources.items():
        p.require(p.sha(root / path) == digest, "recovery.original_sources_unchanged")
    for path in (SCRIPT, STATE_SCRIPT):
        sources[path] = p.sha(root / path)
    plan = p.record(
        "delayed_C_recovery_plan",
        parent_plan_id=parent["id"],
        failure_id=failure["id"],
        preserved_seed11_report_id=finished["id"],
        runs=[next(r for r in parent["runs"] if r["seed"] == seed) for seed in (47, 29)],
        authorization="2026-09-21 user: 恢复实验",
        resume_step=200,
        sources=sources,
        frozen_artifacts=frozen,
        budget=s.recovery_budget(completed),
        original_failure_records_preserved=True,
        no_new_feedback_or_scoring=True,
        failed_work_not_zero_reward=True,
        no_formula_or_loss_or_distribution_change=True,
        replay_equivalence=dict(atol=1e-8, rtol=1e-5),
        checkpoint_every_completed_optimizer_step=True,
        checkpoint_every_feedback_response=True,
        independent_worker_failure_isolation=True,
        resource_retries_only=True,
        minimum_training_free_MiB=61440,
        minimum_final_sampling_free_MiB=73728,
        shared_GPU_exclusivity_not_claimed=True,
        B_and_confirmation=0,
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        at=p.now(),
    )
    p.write_once(root / OUTPUT / "plan.json", plan)
    emit(dict(event="recovery_registered", plan_id=plan["id"], budget=plan["budget"]))
    d.audit.publish(
        root,
        OUTPUT,
        "delayed_C_recovery_registration_20260921",
        p.record(
            "delayed_C_recovery_public_registration",
            plan_id=plan["id"],
            parent_plan_id=parent["id"],
            failure_id=failure["id"],
            budget=plan["budget"],
            resumed_seeds=[47, 29],
            original_sources_unchanged=True,
            registration_before_recovery_GPU_work=True,
        ),
        "按用户2026-09-21恢复指令登记资源故障修复：复用本次实验step200的参数、Adam和RNG。保留seed11完成结果及原失败记录；不重新采样或评分720条反馈。seed47的201—303步需重放，103步重复计算独立记账；有效剂量仍为每种子400步。该恢复修订不是声称原1200步物理预算未超出，也不是重新筛选种子。",
    )
    return plan


def plans(root):
    plan = p.checked(p.read_json(root / OUTPUT / "plan.json"), "delayed_C_recovery_plan")
    parent = p.checked(p.read_json(root / d.OUTPUT / "plan.json"), "delayed_C_registered_plan")
    p.require(parent["id"] == plan["parent_plan_id"], "recovery.exact_parent")
    for path, digest in {**plan["sources"], **plan["frozen_artifacts"]}.items():
        p.require(p.sha(root / path) == digest, "recovery.frozen_input:" + path)
    p.require(d.get_admission(root, parent) is not None, "recovery.original_audit_gate")
    return plan, parent


def completed_replay(root, original, directory, raw, plan, run, model, theta):
    """Same response order, same GPU FP32 sum and fixed /360, with durable boundaries."""
    generated = p.checked(
        p.read_json(original / "feedback/generation_manifest.json"), "anchored_generation_manifest"
    )
    scored = p.checked(
        p.read_json(original / "feedback/scoring_report.json"), "anchored_independent_scoring"
    )
    scores = {row["index"]: row for row in scored["scores"]}
    p.require(
        set(scores) == set(range(360)) and scored["generation_manifest_id"] == generated["id"],
        "recovery.fixed_feedback_binding",
    )
    schedule = []
    for item in generated["trajectories"]:
        row = scores[item["job"]["index"]]
        p.require(
            row["session_id"] == item["session_id"] and row["Q"] in (0, 1),
            "recovery.binary_receipt_binding",
        )
        if row["Q"] == 0:
            continue
        session = old.feedback.read_session(root, item)
        for index, turn in enumerate(session["turns"]):
            schedule.append(
                (
                    item["job"]["index"],
                    index,
                    index == len(session["turns"]) - 1,
                    turn["provider_receipt"],
                )
            )
    p.require(
        len(schedule) == 631 and scored["qualified"] == 99, "recovery.seed29_fixed_replay_inventory"
    )
    saved = sorted((raw / "feedback").glob("*.pt"))
    cursor, tokens, positions, positives = 0, 0, 0, 0
    total = {name: torch.zeros_like(value) for name, value in theta.items()}
    if saved:
        checkpoint = torch.load(saved[-1], map_location="cpu", weights_only=False)
        p.require(
            checkpoint["plan_id"] == plan["id"]
            and checkpoint["generation_id"] == generated["id"]
            and checkpoint["scoring_id"] == scored["id"]
            and set(checkpoint["sum"]) == set(theta),
            "recovery.durable_feedback_binding",
        )
        cursor, tokens, positions, positives = (
            checkpoint[key] for key in ("completed", "tokens", "positions", "positives")
        )
        total = {name: value.to(theta[name].device) for name, value in checkpoint["sum"].items()}
        p.require(0 < cursor <= len(schedule), "recovery.feedback_cursor")
    for offset in range(cursor, len(schedule)):
        trajectory, response, last, receipt = schedule[offset]
        s.wait_capacity(emit)
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            values, gradient, used = old.feedback.segmented.segmented_logp(
                model,
                theta,
                receipt["prompt_input_ids"],
                receipt["generated_token_ids"],
                expected=receipt["sampled_token_logprobs"],
                block_size=8,
            )
        for name in total:
            total[name].add_(gradient[name], alpha=1 / 360)
        tokens += len(receipt["generated_token_ids"])
        positions += used["cached_forward_target_positions"]
        positives += int(last)
        del values, gradient
        s.atomic_torch(
            raw / "feedback" / f"{offset + 1:04d}.pt",
            dict(
                plan_id=plan["id"],
                generation_id=generated["id"],
                scoring_id=scored["id"],
                completed=offset + 1,
                tokens=tokens,
                positions=positions,
                positives=positives,
                sum={name: value.detach().cpu().clone() for name, value in total.items()},
            ),
        )
        emit(
            dict(
                event="feedback_response_checkpointed",
                completed=offset + 1,
                total=len(schedule),
                trajectory=trajectory,
                response=response,
                positive_trajectories=positives,
            )
        )
    p.require(
        positives == 99
        and tokens == 30167
        and all(bool(torch.isfinite(v).all()) for v in total.values()),
        "recovery.complete_finite_gJ",
    )
    report = p.record(
        "anchored_full_trajectory_feedback_gradient",
        point_id=generated["point_id"],
        scoring_report_id=scored["id"],
        denominator=360,
        accounting=dict(
            zero_reward_gradient_terms_skipped=261,
            positive_reward_trajectories=99,
            responses_replayed=631,
            sampled_tokens_with_parameter_derivative=tokens,
            cached_forward_target_positions=positions,
        ),
        zero_reward_authentic_receipts_validated=True,
        zero_reward_GPU_replay_not_claimed=True,
        all_sampled_error_and_EOS_tokens_of_positive_trajectories_included=True,
        cross_response_graph_not_required_by_score_function_sum=True,
        prefix_derivatives_within_each_response_preserved=True,
        length_normalization=False,
        gJ_digest=old.gate.tensor_digest(total),
        theoretical_zero_Contribution_claimed=False,
    )
    return total, report


def outer(root, original, out, raw, plan, parent, run, model, optimizer, names, cache, binding):
    directory = out / "rounds/epoch5"
    if (directory / "report.json").exists():
        return p.read_json(directory / "distribution_update.json")["pi_next"]
    if run["seed"] == 47:
        report = p.read_json(original / "report.json")
        p.require(
            p.read_json(original / "numeric_guard.json")["passed"], "recovery.saved_numeric_guard"
        )
        update = p.read_json(original / "distribution_update.json")
        p.require(
            report["distribution_update_id"] == update["id"], "recovery.same_saved_distribution"
        )
        p.write_once(directory / "distribution_update.json", update)
        p.write_once(
            directory / "report.json",
            p.record("delayed_reused_outer", original_report_id=report["id"], at=p.now()),
        )
        return update["pi_next"]
    pi = copy.deepcopy(binding["prior"])
    population_path = raw / "population.pt"
    if population_path.exists():
        stored = torch.load(population_path, map_location="cpu", weights_only=False)
        p.require(stored["plan_id"] == plan["id"], "recovery.population_checkpoint_plan")
        population = old.classes.PopulationGradients(
            stored["keys"],
            stored["names"],
            stored["shapes"],
            stored["matrix"],
            {name: value.to("cuda:0") for name, value in stored["G"].items()},
            stored["accounting"],
        )
    else:

        def event(value):
            if value["completed_packages"] % 25 == 0:
                emit(value)
                s.wait_capacity(emit)

        s.wait_capacity(emit)
        population = old.classes._compute(model, cache, pi, binding["mu"], event_sink=event)
        info = p.read_json(original / "full_G.json")
        p.require(
            old.gate.tensor_digest(population.G) == info["G_digest"], "recovery.bitwise_original_G"
        )
        s.atomic_torch(
            population_path,
            dict(
                plan_id=plan["id"],
                keys=population.keys,
                names=population.names,
                shapes=population.shapes,
                matrix=population.matrix,
                G={name: value.detach().cpu() for name, value in population.G.items()},
                accounting=population.accounting,
            ),
        )
    bound = old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    virtual = old.adam.virtual_step(bound, population.G)
    theta = virtual["theta_bar"]
    point = p.read_json(original / "virtual_point/point.json")
    p.require(
        old.gate.tensor_digest(theta) == point["parameter_digest"],
        "recovery.exact_saved_virtual_point",
    )
    gJ, report = completed_replay(root, original, directory, raw, plan, run, model, theta)
    pullback = old.adam.pullback(bound, population.G, {name: -value for name, value in gJ.items()})
    contributions = population.centered(pi, binding["mu"], pullback["a"])
    scored = p.read_json(original / "feedback/scoring_report.json")
    rewards = [row["Q"] for row in sorted(scored["scores"], key=lambda row: row["index"])]
    update = old.distribution.update_distribution(
        pi,
        binding["prior"],
        contributions["C"],
        binding["mu"],
        rewards,
        control_tasks=binding["control_tasks"],
        condition="c_only_anchored",
        registered_complete=True,
    )
    guard = d.new_point_numeric_guard(
        population,
        bound,
        gJ,
        pullback["a"],
        contributions["C"],
        update,
        pi,
        binding,
        scored["qualified"],
        parent["numeric_limits"],
    )
    p.require(guard["passed"], "recovery.material_numeric_difference_STOP")
    old.adam._verify(bound)
    for name, value in (
        ("gJ", report),
        ("C", contributions),
        ("pullback", pullback["diagnostics"]),
        ("distribution_update", update),
        ("numeric_guard", guard),
    ):
        p.write_once(directory / (name + ".json"), value)
    p.write_once(
        directory / "report.json",
        p.record(
            "delayed_recovered_outer",
            step=200,
            original_feedback_scoring_id=scored["id"],
            qualified=scored["qualified"],
            denominator=360,
            new_feedback_sessions=0,
            distribution_update_id=update["id"],
            numeric_guard_id=guard["id"],
            at=p.now(),
        ),
    )
    result = update["pi_next"]
    del population, bound, virtual, theta, gJ, pullback
    gc.collect()
    torch.cuda.empty_cache()
    return result


def worker(root, key, attempt):
    old.OUTPUT = OUTPUT
    plan, parent = plans(root)
    run = next(row for row in plan["runs"] if row["key"] == key)
    original_run = root / d.OUTPUT / "runs" / key
    original = original_run / "rounds/epoch5"
    out, raw = root / OUTPUT / "runs" / key, RAW / key
    stage, started = "load", time.monotonic()
    p.write_once(
        out / "attempts" / f"{attempt:04d}_started.json",
        p.record(
            "delayed_recovery_worker_started",
            run=run,
            plan_id=plan["id"],
            attempt=attempt,
            pid=os.getpid(),
            at=p.now(),
        ),
    )
    try:
        binding = p.read_json(root / d.inputs.BASE / "material_binding/A.json")
        p.require(binding["id"] == parent["binding_id"], "recovery.original_material")
        cache_root = root / parent["trajectory_cache"]["cache_root"]
        cache = old.trajectory_materials.load_pool(
            cache_root, p.read_json(cache_root / "manifest.json"), "A"
        )
        old.classes.admit(cache, binding)
        model, _ = old.trajectory_training.load_registered_student(
            parent["assets"]["base_binding"], run["seed"], trainable=True
        )
        p.require(
            old.components.adapter_digest(model)
            == parent["initial_adapter_digests"][str(run["seed"])],
            "recovery.original_base_and_adapter",
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = old.trajectory_training.optimizer_factory(
            list(names.values()), parent["training_configuration"]
        )
        tokenizer = old.load_tokenizer(parent["assets"]["tokenizer_binding"])
        saved = sorted((raw / "updates").glob("*.pt"))
        cursor = 200
        if saved:
            checkpoint = torch.load(saved[-1], map_location="cpu", weights_only=False)
            p.require(
                checkpoint["kind"] == "delayed_C_recovery_training"
                and checkpoint["plan_id"] == plan["id"]
                and checkpoint["run_key"] == key,
                "recovery.training_checkpoint_binding",
            )
            state, snapshot, rng = checkpoint["state"], checkpoint["snapshot"], checkpoint["rng"]
            cursor = checkpoint["completed_updates"]
            p.require(
                201 <= cursor <= 400 and rng["schedule_cursor"] == cursor,
                "recovery.training_cursor",
            )
            report_path = out / "updates" / f"{cursor:04d}" / "report.json"
            if not report_path.exists():
                p.write_once(report_path, checkpoint["update_report"])
        else:
            state, snapshot, rng = s.prefix(original)
        bound = s.restore_optimizer(names, optimizer, state, snapshot, step=cursor)
        del bound, state, snapshot
        s.restore_rng(rng)
        emit(
            dict(
                event="recovery_checkpoint_restored",
                run=key,
                completed=cursor,
                optimizer_and_RNG_verified=True,
            )
        )
        stage = "feedback_gJ"
        if cursor == 200:
            with old.outer_slot(root, key, 200):
                pi = outer(
                    root,
                    original,
                    out,
                    raw,
                    plan,
                    parent,
                    run,
                    model,
                    optimizer,
                    names,
                    cache,
                    binding,
                )
            p.require(
                torch.equal(torch.get_rng_state(), rng["cpu"])
                and torch.equal(torch.cuda.get_rng_state(0).cpu(), rng["cuda"][0]),
                "recovery.outer_preserves_training_RNG",
            )
        else:
            p.require(
                (out / "rounds/epoch5/report.json").exists(),
                "recovery.training_requires_completed_outer",
            )
            pi = p.read_json(out / "rounds/epoch5/distribution_update.json")["pi_next"]
        by_task = d.by_task_at_pi(cache, pi)
        s.restore_rng(rng)
        for batch in parent["schedules"][str(run["seed"])]["batches"]:
            step = batch["step"]
            if step < cursor:
                continue
            stage = "inner_SFT"
            s.wait_capacity(emit)
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
                    dict(task_id=task, group=parent["training_groups"][task])
                    for task in batch["task_ids"]
                ],
            }
            model.train()
            update = old.inner.execute_update(
                model,
                optimizer,
                chosen,
                details,
                pool="A",
                arm="delayed_c_only",
                device="cuda:0",
                trajectory_cache=cache,
            )
            stage = "checkpoint_after_completed_SFT"
            if run["seed"] == 47 and step < 303:
                expected = p.read_json(original_run / "updates" / f"{step + 1:04d}" / "report.json")
                comparison = s.compare_replayed_update(
                    update, expected, **plan["replay_equivalence"]
                )
                p.write_once(
                    out / "replay_equivalence" / f"{step + 1:04d}.json",
                    p.record(
                        "delayed_replayed_update_equivalence",
                        step=step + 1,
                        original_update_id=expected["id"],
                        resumed_update_id=update["id"],
                        **comparison,
                    ),
                )
            s.save_training(
                raw / "updates" / f"{step + 1:04d}.pt",
                names,
                optimizer,
                step + 1,
                update,
                plan["id"],
                key,
            )
            p.write_once(out / "updates" / f"{step + 1:04d}" / "report.json", update)
            emit(
                dict(
                    event="real_optimizer_update_checkpointed",
                    run=key,
                    completed=step + 1,
                    total=400,
                )
            )
        totals, seen, update_ids = Counter(), Counter(), []
        for step in range(1, 401):
            source = original_run if step <= 200 else out
            report = p.read_json(source / "updates" / f"{step:04d}" / "report.json")
            totals.update(
                {
                    name: report[name]
                    for name in (
                        "target_tokens",
                        "sequence_tokens",
                        "rows_completed",
                        "packages_completed",
                    )
                }
            )
            seen.update(row["package_id"] for row in report["packages"])
            update_ids.append(report["id"])
        p.require(
            totals["target_tokens"] == cache.actual_budget["target_tokens_all_epochs"]
            and totals["sequence_tokens"] == cache.actual_budget["sequence_tokens_all_epochs"]
            and seen == Counter({row["package_id"]: 10 for row in cache.packages})
            and len(update_ids) == 400,
            "recovery.same_effective_ten_pass_budget",
        )
        stage = "final_evaluation"
        old.MIN_FREE_MIB = plan["minimum_final_sampling_free_MiB"]
        while True:
            torch.cuda.empty_cache()
            free, _ = torch.cuda.mem_get_info()
            if (free + torch.cuda.memory_reserved()) / 2**20 >= old.MIN_FREE_MIB:
                break
            emit(dict(event="waiting_for_final_generation_headroom", required_MiB=old.MIN_FREE_MIB))
            time.sleep(20)
        theta = {name: value.detach().clone() for name, value in names.items()}
        final = old.point_record(
            root,
            out / "final",
            model,
            theta,
            parent,
            run,
            step=400,
            kind="sole_recovered_delayed_epoch10_final",
            origin=update_ids[-1],
        )
        p.write_once(
            out / "training_report.json",
            p.record(
                "delayed_recovered_training",
                run=run,
                plan_id=plan["id"],
                effective_optimizer_updates=400,
                recovery_optimizer_updates=200,
                prefix_checkpoint_step=200,
                duplicate_original_updates=103 if run["seed"] == 47 else 0,
                effective_totals=dict(totals),
                final_point_id=final["id"],
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
            parent,
            run,
            round_index=2,
            stochastic=False,
        )
        historical = p.read_json(original / "feedback/generation_manifest.json")
        p.write_once(
            out / "report.json",
            p.record(
                "delayed_C_recovered_run",
                run=run,
                plan_id=plan["id"],
                parent_plan_id=parent["id"],
                status="COMPLETE_RECOVERED_FIXED_FINAL",
                effective_optimizer_updates=400,
                resumed_optimizer_updates=200,
                new_feedback_sessions=0,
                reused_feedback_sessions=360,
                final_greedy_sessions=180,
                final_qualified=scored["qualified"],
                denominator=180,
                new_generate_calls=generated["total_generate_calls"],
                historical_feedback_generate_calls=historical["total_generate_calls"],
                final_assessment_report_id=scored["id"],
                final_point_id=final["id"],
                recovery_attempt=attempt,
                recovery_attempt_elapsed_seconds=time.monotonic() - started,
                at=p.now(),
            ),
        )
        return 0
    except Exception as failure:
        retry = isinstance(failure, torch.OutOfMemoryError) and stage in (
            "load",
            "feedback_gJ",
            "inner_SFT",
        )
        p.write_once(
            out / "attempts" / f"{attempt:04d}_failure.json",
            p.record(
                "delayed_recovery_attempt_failure",
                run=run,
                plan_id=plan["id"],
                stage=stage,
                resource_retry_allowed=retry,
                error=repr(failure),
                traceback=traceback.format_exc(),
                at=p.now(),
            ),
        )
        emit(
            dict(
                event="recovery_attempt_failed",
                run=key,
                stage=stage,
                resource_retry_allowed=retry,
                error=repr(failure),
            )
        )
        return 42 if retry else 1


def publish_final(root, plan):
    original = p.read_json(root / d.OUTPUT / "runs/A_delayed_c_11/report.json")
    recovered = [
        p.read_json(root / OUTPUT / "runs" / run["key"] / "report.json") for run in plan["runs"]
    ]
    parent = p.read_json(root / d.inputs.PARENT / "report.json")
    qualified = original["final_qualified"] + sum(row["final_qualified"] for row in recovered)
    p.require(
        sum(row["resumed_optimizer_updates"] for row in recovered) == 400
        and sum(row["final_greedy_sessions"] for row in recovered) == 360
        and sum(row["new_generate_calls"] for row in recovered) <= 11520,
        "recovery.complete_new_budget",
    )
    report = p.record(
        "delayed_C_recovered_matrix",
        status="COMPLETE_THREE_DELAYED_C_RUNS_AFTER_RECOVERY",
        recovery_plan_id=plan["id"],
        original_plan_id=plan["parent_plan_id"],
        Delayed_C_qualified=qualified,
        Static_qualified=parent["Static_qualified"],
        original_C_only_qualified=parent["C_only_qualified"],
        original_Full_qualified=parent["Full_qualified"],
        denominator_per_condition=540,
        primary_mean_difference=(qualified - parent["Static_qualified"]) / 540,
        primary_direction="POSITIVE_FIXED_DEV_DELAYED_DIRECTION"
        if qualified > parent["Static_qualified"]
        else "RETAIN_STATIC_NO_POSITIVE_DELAYED_DIRECTION",
        effective_optimizer_updates=1200,
        cumulative_completed_optimizer_updates=1303,
        repeated_completed_optimizer_updates=103,
        new_feedback_sessions=0,
        original_resource_failure_preserved=True,
        development_is_not_independent_confirmation=True,
        B_or_confirmation_started=False,
        no_Full_or_Novelty_success_relabel=True,
        runs=[
            dict(run=row["run"], qualified=row["final_qualified"], report_id=row["id"])
            for row in [original, *recovered]
        ],
        at=p.now(),
    )
    p.write_once(root / OUTPUT / "report.json", report)
    d.audit.publish(
        root,
        OUTPUT,
        "complete_delayed_C_recovery_20260921",
        report,
        "资源故障恢复完成；原失败记录保留。有效训练剂量仍为每种子400步，物理已完成更新累计1303步，包含seed47的103步重放。未新增随机反馈或私有评分，未启动B/确认。",
    )


def coordinate(root):
    old.OUTPUT = OUTPUT
    plan, _ = plans(root)
    out = root / OUTPUT
    p.write_once(
        out / "coordinator_started.json",
        p.record("delayed_recovery_coordinator", pid=os.getpid(), at=p.now()),
    )
    pending = [run["key"] for run in plan["runs"]]
    active, failed, attempts = {}, {}, Counter()
    try:
        while pending or active:
            for key, (process, lease, stream) in list(active.items()):
                code = process.poll()
                if code is None:
                    continue
                lease.close()
                stream.close()
                del active[key]
                if code == 0:
                    report = p.read_json(out / "runs" / key / "report.json")
                    d.audit.publish(
                        root,
                        OUTPUT,
                        key + "_recovered_final",
                        report,
                        "从本次Delayed-C的第200步参数/Adam/RNG恢复；原失败记录保留，不重采样随机反馈。单种子结果不代表整轮结论。",
                    )
                elif (
                    code == 42
                    and attempts[key] < plan["budget"]["maximum_resource_failures_per_run"]
                ):
                    pending.append(key)
                    emit(
                        dict(
                            event="resource_restart_from_durable_checkpoint",
                            run=key,
                            next_attempt=attempts[key] + 1,
                        )
                    )
                else:
                    failed[key] = dict(returncode=code, attempts=attempts[key])
                    emit(dict(event="run_failed_other_worker_continues", run=key, returncode=code))
            if (
                pending
                and len(active) < 2
                and old.host_memory()["MemAvailable_bytes"] >= 256 * 2**30
            ):
                choices = old.claim_gpus(root, maximum=2 - len(active))
                for gpu, lease in choices:
                    if not pending:
                        lease.close()
                        continue
                    key = pending.pop(0)
                    attempts[key] += 1
                    number = attempts[key]
                    path = out / "logs" / f"{key}_attempt{number}.log"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    stream = path.open("x")
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
                            "--attempt",
                            str(number),
                        ],
                        cwd=root,
                        env=env,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        pass_fds=(lease.fileno(),),
                        start_new_session=True,
                    )
                    active[key] = process, lease, stream
                    p.write_once(
                        out / "launches" / f"{key}_{number}.json",
                        p.record(
                            "delayed_recovery_launch",
                            run=key,
                            attempt=number,
                            gpu=gpu,
                            pid=process.pid,
                            at=p.now(),
                        ),
                    )
                    emit(
                        dict(
                            event="recovery_worker_launched",
                            run=key,
                            gpu=gpu["index"],
                            pid=process.pid,
                        )
                    )
            if pending or active:
                time.sleep(20)
        if failed:
            p.write_once(
                out / "coordinator_failure.json",
                p.record(
                    "delayed_recovery_incomplete",
                    failed=failed,
                    healthy_workers_not_killed=True,
                    at=p.now(),
                ),
            )
            return
        publish_final(root, plan)
    except Exception as failure:
        p.write_once(
            out / "coordinator_failure.json",
            p.record(
                "delayed_recovery_coordinator_failure",
                error=repr(failure),
                traceback=traceback.format_exc(),
                healthy_workers_not_killed=True,
                at=p.now(),
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode", choices=("prepare", "coordinate", "worker", "start"), required=True
    )
    parser.add_argument("--run")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "prepare":
        prepare(root)
    elif args.mode == "coordinate":
        coordinate(root)
    elif args.mode == "worker":
        raise SystemExit(worker(root, args.run, args.attempt))
    else:
        path = root / OUTPUT / "coordinator.log"
        with path.open("x") as stream:
            process = subprocess.Popen(
                [sys.executable, str(root / SCRIPT), "--root", str(root), "--mode", "coordinate"],
                cwd=root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        emit(dict(event="recovery_coordinator_started", pid=process.pid))


if __name__ == "__main__":
    main()
