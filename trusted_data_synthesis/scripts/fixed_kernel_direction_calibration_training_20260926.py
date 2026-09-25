"""Exactly one negative-direction epoch from each admitted real B step200 point.

The injected execution context owns finite attempt budgets and capacity policy.
This worker does not generate/score feedback, change distributions, run positive
or Static training, or write any historical B artifact.
"""

from collections import Counter
from pathlib import Path

import fixed_kernel_direction_calibration_materials_20260926 as admission

p = admission.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_training_20260926.py"
START, STOP = 200, 240
TOTAL_FIELDS = ("target_tokens", "sequence_tokens", "rows_completed", "packages_completed")


def _registered(plan, seed):
    p.require(type(seed) is int and seed in admission.SEEDS, "calibration_training.fixed_seed")
    p.require(plan["seeds"] == list(admission.SEEDS), "calibration_training.all_three_seeds")
    admitted = p.checked(plan["materials_admission"], "direction_calibration_material_admission")
    p.require(
        admitted["passed"] is True and admitted["seeds"] == list(admission.SEEDS),
        "calibration_training.complete_material_admission",
    )
    reflection = p.checked(admitted["distributions"][str(seed)], "direction_calibration_reflection")
    distribution = reflection["distributions"]["negative"]
    p.require(
        p.sha(p.encode(distribution)) == reflection["distribution_sha256"]["negative"]
        and reflection["binding_id"] == admitted["materials"]["binding"]["id"]
        and reflection["probability_clipping_or_repair"] is False,
        "calibration_training.exact_registered_negative_distribution",
    )
    references = [
        row
        for row in admitted["reusable_refs"]
        if row["job_key"] == f"B_prefix_{seed}" and row["step"] == START
    ]
    p.require(len(references) == 1, "calibration_training.one_real_prefix")
    return admitted, reflection, references[0]


def _recover(c, directory, plan_id, key):
    folder = directory / "updates"
    saved = {int(path.stem): path for path in folder.glob("[0-9][0-9][0-9][0-9].pt")}
    cursor = max(saved, default=START)
    p.require(
        START <= cursor <= STOP and set(saved) == set(range(START + 1, cursor + 1)),
        "calibration_training.contiguous_committed_updates",
    )
    reports = {int(path.stem) for path in folder.glob("[0-9][0-9][0-9][0-9].json")}
    p.require(reports <= set(saved), "calibration_training.no_report_without_checkpoint")
    checkpoint = None
    for step in sorted(set(saved) - reports | ({cursor} if saved else set())):
        current = c.b.load_training(saved[step], plan_id, [key], step=step)
        report = p.checked(current["update_report"], "optimizer_update")
        target = folder / f"{step:04d}.json"
        if target.exists():
            p.require(
                p.read_json(target) == report, "calibration_training.embedded_update_identity"
            )
        else:
            c.write(target, report)
        if step == cursor:
            checkpoint = current
    return cursor, checkpoint


def _prefix(c, admitted, reference):
    path = Path(reference["path"])
    p.require(p.sha(path) == reference["sha256"], "calibration_training.original_prefix_bytes")
    saved = c.b.load_training(
        path, admitted["original_protocol_id"], [reference["job_key"]], step=START
    )
    p.require(
        saved["snapshot"]["id"] == reference["snapshot_id"]
        and admission._rng_binding(saved["rng"], START) == reference["RNG_binding"],
        "calibration_training.original_prefix_Adam_and_RNG",
    )
    return saved


def _reports(c, directory, materials, seed, cache, by_task):
    totals, visits, identifiers = Counter(), Counter(), []
    for step in range(START + 1, STOP + 1):
        report = p.checked(
            p.read_json(directory / "updates" / f"{step:04d}.json"), "optimizer_update"
        )
        batch = materials["schedules"][str(seed)]["batches"][step - 1]
        expected = [
            row for _, row in sorted(pair for task in batch["task_ids"] for pair in by_task[task])
        ]
        p.require(
            report["pool"] == "B"
            and report["arm"] == "negative"
            and report["cache_id"] == cache.cache_id
            and report["optimizer_step_calls"] == 1
            and report["packages"] == expected
            and report["tasks"]
            == [
                dict(task_id=task, group=materials["training_groups"][task])
                for task in batch["task_ids"]
            ],
            "calibration_training.bound_full_epoch_reports",
        )
        totals.update({field: report[field] for field in TOTAL_FIELDS})
        visits.update(row["package_id"] for row in report["packages"])
        identifiers.append(report["id"])
    p.require(
        visits == Counter(dict.fromkeys((row["package_id"] for row in cache.packages), 1)),
        "calibration_training.every_original_package_once",
    )
    for field, budget in (
        ("target_tokens", "target_tokens"),
        ("sequence_tokens", "sequence_tokens"),
        ("rows_completed", "rows"),
        ("packages_completed", "packages"),
    ):
        p.require(
            totals[field]
            == cache.actual_budget[budget + "_per_epoch"]
            == materials["actual_budget"][budget + "_per_epoch"],
            "calibration_training.exact_original_epoch_budget",
        )
    return dict(totals), identifiers


def run(c, root, seed, attempt, required_MiB=32768):
    """Resume only missing committed updates; numerical/identity errors propagate."""
    root = Path(root).resolve()
    plan = c.read_protocol(root)
    admitted, reflection, reference = _registered(plan, seed)
    key = f"B_negative_{seed}"
    directory = Path(c.RAW) / "jobs" / key
    old_raw = Path(reference["path"]).parents[3].resolve()
    p.require(
        not directory.resolve().is_relative_to(old_raw),
        "calibration_training.never_write_historical_B",
    )
    with c.locked(directory / "execution.lock", blocking=False):
        return _run(
            c,
            root,
            plan,
            admitted,
            reflection,
            reference,
            key,
            seed,
            attempt,
            directory,
            required_MiB,
        )


def _run(
    c, root, plan, admitted, reflection, reference, key, seed, attempt, directory, required_MiB
):
    materials = admitted["materials"]
    prefix_state = _prefix(c, admitted, reference)
    binding = p.record(
        "direction_calibration_negative_branch_binding",
        plan_id=plan["id"],
        material_admission_id=admitted["id"],
        original_protocol_id=admitted["original_protocol_id"],
        job_key=key,
        seed=seed,
        condition="negative",
        pool="B",
        start=START,
        stop=STOP,
        prefix_checkpoint_path=reference["path"],
        prefix_checkpoint_sha256=reference["sha256"],
        prefix_snapshot_id=reference["snapshot_id"],
        prefix_RNG_binding=reference["RNG_binding"],
        reflection_id=reflection["id"],
        distribution_sha256=reflection["distribution_sha256"]["negative"],
        starts_from_real_model_Adam_and_RNG=True,
        virtual_point_used_for_SFT=False,
    )
    branch_path = directory / "branch_binding.json"
    if branch_path.exists():
        p.require(p.read_json(branch_path) == binding, "calibration_training.unchanged_branch")
    else:
        c.write(branch_path, binding)
    cursor, checkpoint = _recover(c, directory, plan["id"], key)
    report_path = directory / "report.json"
    if report_path.exists():
        report = p.checked(p.read_json(report_path), "direction_calibration_training_report")
        p.require(
            cursor == STOP
            and report["plan_id"] == plan["id"]
            and report["job_key"] == key
            and report["complete"] is True
            and report["branch_binding_id"] == binding["id"]
            and report["checkpoint_sha256"] == p.sha(directory / "updates/0240.pt")
            and report["physical_optimizer_updates"] == 40,
            "calibration_training.completed_job_identity",
        )
        return report
    cache_root = root / materials["trajectory_cache"]["cache_root"]
    manifest = p.read_json(cache_root / "manifest.json")
    p.require(
        manifest["id"] == materials["trajectory_cache"]["manifest_id"],
        "calibration_training.original_cache",
    )
    cache = c.b.old.trajectory_materials.load_pool(cache_root, manifest, "B")
    c.b.old.classes.admit(cache, materials["binding"])
    negative = reflection["distributions"]["negative"]
    by_task = c.b.d.by_task_at_pi(cache, negative)
    attempt_updates = 0
    if cursor < STOP:
        c.capacity_boundary("SFT", required_MiB=required_MiB)
        model, _ = c.b.old.trajectory_training.load_registered_student(
            materials["assets"]["base_binding"], seed, trainable=True
        )
        p.require(
            c.b.old.components.adapter_digest(model)
            == materials["initial_adapter_digests"][str(seed)],
            "calibration_training.paired_fresh_initial_adapter",
        )
        names = {name: value for name, value in model.named_parameters() if value.requires_grad}
        optimizer = c.b.old.trajectory_training.optimizer_factory(
            list(names.values()), materials["training_configuration"]
        )
        p.require(not optimizer.state, "calibration_training.fresh_optimizer_before_restore")
        resume = checkpoint if checkpoint is not None else prefix_state
        c.s.restore_optimizer(names, optimizer, resume["state"], resume["snapshot"], step=cursor)
        p.require(resume["rng"]["schedule_cursor"] == cursor, "calibration_training.RNG_cursor")
        c.s.restore_rng(resume["rng"])
        schedule = materials["schedules"][str(seed)]["batches"]
        for batch in schedule[cursor:STOP]:
            step = batch["step"] + 1
            p.require(step == cursor + 1, "calibration_training.next_uncommitted_step")
            c.capacity_boundary("SFT", required_MiB=required_MiB)
            chosen = [
                row
                for _, row in sorted(pair for task in batch["task_ids"] for pair in by_task[task])
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
            update = c.b.old.inner.execute_update(
                model,
                optimizer,
                chosen,
                details,
                pool="B",
                arm="negative",
                device=next(iter(names.values())).device,
                trajectory_cache=cache,
            )
            checkpoint_path = directory / "updates" / f"{step:04d}.pt"
            c.b.save_training(checkpoint_path, names, optimizer, step, update, plan["id"], key)
            c.write(checkpoint_path.with_suffix(".json"), update)
            cursor, attempt_updates = step, attempt_updates + 1
            if hasattr(c, "emit"):
                c.emit(
                    dict(
                        event="direction_negative_update_checkpointed",
                        job_key=key,
                        attempt=attempt,
                        completed_updates=cursor,
                        stop=STOP,
                    )
                )
        del model, optimizer, names, resume
    totals, identifiers = _reports(c, directory, materials, seed, cache, by_task)
    final_path = directory / "updates/0240.pt"
    final = c.b.load_training(final_path, plan["id"], [key], step=STOP)
    p.require(
        final["update_report"]["id"] == identifiers[-1],
        "calibration_training.final_report_identity",
    )
    report = p.record(
        "direction_calibration_training_report",
        complete=True,
        plan_id=plan["id"],
        job_key=key,
        seed=seed,
        condition="negative",
        pool="B",
        start=START,
        stop=STOP,
        completed_updates=STOP,
        material_admission_id=admitted["id"],
        branch_binding_id=binding["id"],
        prefix_binding=binding,
        original_prefix_sha256=reference["sha256"],
        original_prefix_snapshot_id=reference["snapshot_id"],
        original_prefix_RNG_binding_id=reference["RNG_binding"]["id"],
        distribution_sha256=reflection["distribution_sha256"]["negative"],
        checkpoint_path=str(final_path),
        checkpoint_sha256=p.sha(final_path),
        snapshot_id=final["snapshot"]["id"],
        RNG_binding=admission._rng_binding(final["rng"], STOP),
        rng_complete=True,
        effective_optimizer_updates=STOP,
        physical_optimizer_updates=STOP - START,
        physical_optimizer_updates_count_committed_updates_only=True,
        uncommitted_attempt_budget_accounted_separately_by_reservations=True,
        shared_prefix_updates_reused=START,
        updates_in_final_attempt=attempt_updates,
        full_original_epochs=1,
        physical_job_totals=totals,
        update_report_ids=identifiers,
        cache_id=cache.cache_id,
        binding_id=materials["binding"]["id"],
        new_positive_or_static_updates=0,
        generation_sessions=0,
        scoring_sessions=0,
        at=p.now(),
    )
    c.write(report_path, report)
    return report
