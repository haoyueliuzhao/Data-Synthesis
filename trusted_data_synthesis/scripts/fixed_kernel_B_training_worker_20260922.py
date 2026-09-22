"""Durable B prefix/tail SFT workers; no feedback or final generation occurs here."""

import copy
import importlib
from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

TOTAL_FIELDS = ("target_tokens", "sequence_tokens", "rows_completed", "packages_completed")


def _common():
    return importlib.import_module("fixed_kernel_B_common_20260922")


def _job(plan, key):
    matches = [row for row in plan["training_jobs"] if row["key"] == key]
    p.require(len(matches) == 1, "B_training.unique_registered_job")
    job = matches[0]
    p.require(job["pool"] == "B" and job["seed"] in (11, 29, 47), "B_training.B_seed")
    condition = job["condition"]
    p.require(condition in {"prefix", "static", "delayed_c"}, "B_training.condition")
    p.require(
        (job["start"], job["stop"]) == ((0, 200) if condition == "prefix" else (200, 400))
        and job["prefix_key"] == f"B_prefix_{job['seed']}"
        and key == f"B_{condition}_{job['seed']}",
        "B_training.fixed_shared_prefix_schedule",
    )
    return job


def _recover_updates(c, directory, plan_id, key, start, stop):
    """Only complete atomically committed checkpoints advance the cursor."""
    folder = directory / "updates"
    saved = {int(path.stem): path for path in folder.glob("[0-9][0-9][0-9][0-9].pt")}
    cursor = max(saved, default=start)
    p.require(
        start <= cursor <= stop and set(saved) == set(range(start + 1, cursor + 1)),
        "B_training.contiguous_committed_updates",
    )
    reports = {int(path.stem) for path in folder.glob("[0-9][0-9][0-9][0-9].json")}
    p.require(reports <= set(saved), "B_training.no_report_without_checkpoint")
    checkpoint = None
    for step in sorted(set(saved) - reports | ({cursor} if saved else set())):
        current = c.load_training(saved[step], plan_id, [key], step=step)
        update = current["update_report"]
        p.checked(update, "optimizer_update")
        report_path = folder / f"{step:04d}.json"
        if report_path.exists():
            p.require(p.read_json(report_path) == update, "B_training.embedded_report_binding")
        else:
            c.write(report_path, update)
        if step == cursor:
            checkpoint = current
    return cursor, checkpoint


def _prefix(c, plan, job):
    directory = c.RAW / "jobs" / job["prefix_key"]
    report = p.checked(p.read_json(directory / "report.json"), "B_training_job_report")
    path = directory / "updates/0200.pt"
    p.require(
        report["plan_id"] == plan["id"]
        and report["job_key"] == job["prefix_key"]
        and report["condition"] == "prefix"
        and report["complete"] is True
        and report["completed_updates"] == 200
        and report["rng_complete"] is True
        and report["checkpoint_path"] == str(path),
        "B_training.only_complete_prefix200_can_fork",
    )
    digest = p.sha(path)
    p.require(digest == report["checkpoint_sha256"], "B_training.prefix_checkpoint_bytes")
    saved = c.load_training(path, plan["id"], [job["prefix_key"]], step=200)
    p.require(
        saved["snapshot"]["id"] == report["snapshot_id"], "B_training.prefix_snapshot_identity"
    )
    return saved, dict(
        prefix_key=job["prefix_key"],
        prefix_checkpoint_path=str(path),
        prefix_checkpoint_sha256=digest,
        prefix_snapshot_id=saved["snapshot"]["id"],
        prefix_completed_updates=200,
        rng_complete=True,
        rng_components=["cpu", "cuda", "python", "numpy", "schedule_cursor"],
    )


def _branch_binding(c, plan, job, prefix):
    record = p.record(
        "B_shared_prefix_branch_binding",
        plan_id=plan["id"],
        job_key=job["key"],
        seed=job["seed"],
        condition=job["condition"],
        pool="B",
        **prefix,
        starts_from_real_model_Adam_and_RNG=True,
        virtual_point_used_for_SFT=False,
    )
    path = c.RAW / "jobs" / job["key"] / "branch_binding.json"
    if path.exists():
        p.require(p.read_json(path) == record, "B_training.unchanged_branch_origin")
    else:
        c.write(path, record)
    sibling = "delayed_c" if job["condition"] == "static" else "static"
    other_path = c.RAW / "jobs" / f"B_{sibling}_{job['seed']}" / "branch_binding.json"
    if other_path.exists():
        other = p.checked(p.read_json(other_path), "B_shared_prefix_branch_binding")
        p.require(
            other["plan_id"] == plan["id"]
            and all(other[name] == value for name, value in prefix.items()),
            "B_training.both_branches_same_prefix_state",
        )
    return record


def _distribution(c, plan, job, prefix):
    binding = plan["materials"]["binding"]
    if job["condition"] != "delayed_c":
        return copy.deepcopy(binding["prior"])
    directory = c.RAW / "outer" / job["key"]
    report = p.read_json(directory / "report.json")
    updated = p.checked(
        p.read_json(directory / "distribution_update.json"), "anchored_sources_distribution_step"
    )
    p.require(
        report["plan_id"] == plan["id"]
        and report["job_key"] == job["key"]
        and report["prefix_checkpoint_sha256"] == prefix["prefix_checkpoint_sha256"]
        and report["prefix_snapshot_id"] == prefix["prefix_snapshot_id"]
        and report["numeric_guard_passed"] is True
        and report["distribution_update_id"] == updated["id"],
        "B_training.only_bound_completed_outer_with_passed_guard",
    )
    guard_path = directory / "numeric_guard.json"
    if guard_path.exists():
        p.require(p.read_json(guard_path)["passed"] is True, "B_training.numeric_guard_failed")
    pi = updated["pi_next"]
    p.require(
        set(pi) == set(binding["prior"])
        and all(set(pi[task]) == set(states) for task, states in binding["prior"].items()),
        "B_training.updated_B_support_only",
    )
    p.require(
        all(pi[task] == binding["prior"][task] for task in binding["control_tasks"]),
        "B_training.control_prior_unchanged",
    )
    return pi


def _effective_reports(c, plan, job, cache):
    totals, local_totals, visits, identifiers = Counter(), Counter(), Counter(), []
    for step in range(1, job["stop"] + 1):
        owner = job["prefix_key"] if step <= 200 else job["key"]
        report = p.checked(
            p.read_json(c.RAW / "jobs" / owner / "updates" / f"{step:04d}.json"), "optimizer_update"
        )
        p.require(
            report["pool"] == "B"
            and report["optimizer_step_calls"] == 1
            and report["cache_id"] == cache.cache_id,
            "B_training.report_B_update",
        )
        expected_tasks = plan["materials"]["schedules"][str(job["seed"])]["batches"][step - 1][
            "task_ids"
        ]
        p.require(
            [row["task_id"] for row in report["tasks"]] == expected_tasks
            and report["arm"] == ("prefix" if step <= 200 else job["condition"]),
            "B_training.report_registered_schedule_and_condition",
        )
        totals.update({name: report[name] for name in TOTAL_FIELDS})
        if owner == job["key"]:
            local_totals.update({name: report[name] for name in TOTAL_FIELDS})
        visits.update(row["package_id"] for row in report["packages"])
        identifiers.append(report["id"])
    epochs = job["stop"] // 40
    expected = Counter({row["package_id"]: epochs for row in cache.packages})
    p.require(visits == expected, "B_training.effective_package_visits")
    for actual, budget_key in (
        ("target_tokens", "target_tokens"),
        ("sequence_tokens", "sequence_tokens"),
        ("rows_completed", "rows"),
        ("packages_completed", "packages"),
    ):
        p.require(
            totals[actual] == epochs * cache.actual_budget[budget_key + "_per_epoch"],
            "B_training.effective_B_token_and_package_budget",
        )
    return dict(totals), dict(local_totals), identifiers


def run(root, key, attempt, required_MiB=32768):
    c = _common()
    root = Path(root).resolve()
    plan = c.read_protocol(root)
    job = _job(plan, key)
    directory = c.RAW / "jobs" / key
    materials = plan["materials"]
    prefix_state = None
    prefix = {}
    if job["condition"] != "prefix":
        prefix_state, prefix = _prefix(c, plan, job)
        _branch_binding(c, plan, job, prefix)
    pi = _distribution(c, plan, job, prefix)
    cursor, checkpoint = _recover_updates(c, directory, plan["id"], key, job["start"], job["stop"])
    report_path = directory / "report.json"
    if report_path.exists():
        report = p.checked(p.read_json(report_path), "B_training_job_report")
        p.require(
            cursor == job["stop"]
            and report["plan_id"] == plan["id"]
            and report["job_key"] == key
            and report["complete"] is True
            and report["checkpoint_sha256"] == p.sha(directory / "updates" / f"{cursor:04d}.pt"),
            "B_training.completed_job_identity",
        )
        return report
    cache_root = root / materials["trajectory_cache"]["cache_root"]
    manifest = p.read_json(cache_root / "manifest.json")
    p.require(
        manifest["id"] == materials["trajectory_cache"]["manifest_id"],
        "B_training.bound_cache_manifest",
    )
    cache = c.old.trajectory_materials.load_pool(cache_root, manifest, "B")
    c.old.classes.admit(cache, materials["binding"])
    attempt_updates = 0
    if cursor < job["stop"]:
        c.capacity_boundary("SFT", required_MiB=required_MiB)
        model, _ = c.old.trajectory_training.load_registered_student(
            materials["assets"]["base_binding"], job["seed"], trainable=True
        )
        p.require(
            c.old.components.adapter_digest(model)
            == materials["initial_adapter_digests"][str(job["seed"])],
            "B_training.paired_fresh_initial_adapter",
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = c.old.trajectory_training.optimizer_factory(
            list(names.values()), materials["training_configuration"]
        )
        p.require(not optimizer.state, "B_training.fresh_optimizer_before_restore")
        resume = checkpoint if checkpoint is not None else prefix_state
        rng = None
        if resume is not None:
            c.s.restore_optimizer(
                names, optimizer, resume["state"], resume["snapshot"], step=cursor
            )
            rng = resume["rng"]
            p.require(rng["schedule_cursor"] == cursor, "B_training.RNG_cursor")
            c.s.restore_rng(rng)
        by_task = c.d.by_task_at_pi(cache, pi)
        if rng is not None:
            c.s.restore_rng(rng)
        schedule = materials["schedules"][str(job["seed"])]["batches"]
        for batch in schedule[cursor : job["stop"]]:
            step = batch["step"] + 1
            p.require(step == cursor + 1, "B_training.next_uncommitted_step")
            c.capacity_boundary("SFT", required_MiB=required_MiB)
            chosen = [
                row
                for _, row in sorted(
                    (value for task in batch["task_ids"] for value in by_task[task]),
                    key=lambda value: value[0],
                )
            ]
            details = {
                **batch,
                "tasks": [
                    dict(task_id=task, group=materials["training_groups"][task])
                    for task in batch["task_ids"]
                ],
            }
            c.reserve("optimizer", key, attempt, step)
            model.train()
            update = c.old.inner.execute_update(
                model,
                optimizer,
                chosen,
                details,
                pool="B",
                arm=job["condition"],
                device=next(iter(names.values())).device,
                trajectory_cache=cache,
            )
            checkpoint_path = directory / "updates" / f"{step:04d}.pt"
            c.save_training(checkpoint_path, names, optimizer, step, update, plan["id"], key)
            c.write(directory / "updates" / f"{step:04d}.json", update)
            cursor = step
            attempt_updates += 1
            c.emit(
                dict(
                    event="B_optimizer_update_checkpointed",
                    job_key=key,
                    attempt=attempt,
                    completed_updates=cursor,
                    stop=job["stop"],
                )
            )
        del model, optimizer, names, resume, checkpoint, prefix_state
    totals, physical_totals, identifiers = _effective_reports(c, plan, job, cache)
    final_path = directory / "updates" / f"{job['stop']:04d}.pt"
    final = c.load_training(final_path, plan["id"], [key], step=job["stop"])
    p.require(final["update_report"]["id"] == identifiers[-1], "B_training.final_checkpoint_report")
    report = p.record(
        "B_training_job_report",
        complete=True,
        plan_id=plan["id"],
        job_key=key,
        pool="B",
        seed=job["seed"],
        condition=job["condition"],
        start=job["start"],
        stop=job["stop"],
        completed_updates=job["stop"],
        effective_optimizer_updates=job["stop"],
        physical_optimizer_updates=job["stop"] - job["start"],
        physical_optimizer_updates_count_committed_updates_only=True,
        uncommitted_attempt_budget_accounted_separately_by_reservations=True,
        shared_prefix_updates_reused=job["start"],
        updates_in_final_attempt=attempt_updates,
        checkpoint_path=str(final_path),
        checkpoint_sha256=p.sha(final_path),
        snapshot_id=final["snapshot"]["id"],
        rng_complete=True,
        effective_totals=totals,
        physical_job_totals=physical_totals,
        update_report_ids=identifiers,
        cache_id=cache.cache_id,
        binding_id=materials["binding_id"],
        prefix_binding=prefix,
        final_generation_sessions=0,
        shared_prefix_not_counted_as_new_tail_physical_updates=True,
        at=p.now(),
    )
    c.write(report_path, report)
    return report
