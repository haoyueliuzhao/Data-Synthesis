"""Durable control state and resumable final evaluation; frozen numerical kernels are reused."""

# ruff: noqa: E501 -- explicit provenance fields
import gc
import json
import os
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import run_fixed_kernel_delayed_C_recovery_20260921 as r
import torch

p, old, f = r.p, r.old, r.old.feedback
NAME = "aggressive_autorun_20260921"
CONTROL = r.RAW / NAME
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delayed_C_autorun_20260921.py"
HELPER = "trusted_data_synthesis/scripts/fixed_kernel_delayed_C_autorun_state_20260921.py"
FLOORS = dict(sft=32768, feedback=51200, final=57344, score=0)
EXTRA_CALL_CAP_PER_RUN = 5760


class BoundaryYield(BaseException):
    """Only raised between durable units, never inside an optimizer update."""


def atomic_bytes(path, payload, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        p.require(path.read_bytes() == payload, "autorun.immutable_conflict:" + str(path))
        return
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".partial.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                p.require(path.read_bytes() == payload, "autorun.concurrent_immutable_conflict")
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
        handle = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write(path, value, *, immutable=False):
    atomic_bytes(path, p.encode(value), immutable=immutable)


def install_durable_writer(root):
    """Commit recovery JSON on data1 before exposing its local copy; equality-only reuse."""
    original = p.write_once
    prefix = root / r.OUTPUT

    def durable(path, value):
        path = Path(path)
        if path.is_relative_to(prefix):
            p.require(
                ".." not in path.parts
                and (path.resolve().is_relative_to(root) or path.resolve().is_relative_to(r.RAW)),
                "autorun.confined_durable_path",
            )
            references = []
            if value.get("schema_version", "").endswith("anchored_model_parameter_point"):
                references.append(root / value["adapter_directory"] / value["adapter"]["path"])
            if value.get("schema_version", "").endswith("anchored_generated_trajectory"):
                references.append(root / value["path"])
            for reference in references:
                with reference.open("rb") as stream:
                    os.fsync(stream.fileno())
                handle = os.open(reference.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(handle)
                finally:
                    os.close(handle)
            payload = p.encode(value)
            atomic_bytes(CONTROL / "archive" / path.relative_to(root), payload, immutable=True)
            atomic_bytes(path, payload, immutable=True)
        else:
            original(path, value)
        return value

    p.write_once = durable


def archive_metadata(root, known):
    """Old adopted workers still use their original writer; archive only complete JSON."""
    base = root / r.OUTPUT
    for folder in (base / "runs", base / "launches"):
        for path in folder.rglob("*.json"):
            # Final artifacts already live on data1 through the explicitly created links.
            if path.resolve().is_relative_to(r.RAW):
                continue
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue  # The new final worker may be preserving and linking a legacy directory.
            marker = (stat.st_size, stat.st_mtime_ns)
            if known.get(str(path)) == marker:
                continue
            try:
                value = p.read_json(path)
            except (json.JSONDecodeError, FileNotFoundError):
                continue  # An adopted writer may not have finished its exclusive write yet.
            # Adopted original final workers do not use our data1 links or writer yet.
            references = []
            if value.get("schema_version", "").endswith("anchored_generated_trajectory"):
                references.append((root / value["path"], value["sha256"]))
            if value.get("schema_version", "").endswith("anchored_model_parameter_point"):
                references.append(
                    (
                        root / value["adapter_directory"] / value["adapter"]["path"],
                        value["adapter"]["sha256"],
                    )
                )
            for source, digest in references:
                payload = source.read_bytes()
                p.require(p.sha(payload) == digest, "autorun.archive_sealed_reference")
                atomic_bytes(
                    CONTROL / "archive" / source.relative_to(root), payload, immutable=True
                )
            write(CONTROL / "archive" / path.relative_to(root), value, immutable=True)
            known[str(path)] = marker
    for path in (base / "plan.json",):
        write(CONTROL / "archive" / path.relative_to(root), p.read_json(path), immutable=True)


def restore_metadata(root):
    for path in (CONTROL / "archive").rglob("*"):
        if not path.is_file():
            continue
        target = root / path.relative_to(CONTROL / "archive")
        if not target.exists():
            atomic_bytes(target, path.read_bytes(), immutable=True)


def final_links(root, key):
    """Keep original relative receipt paths, but put new final artifacts directly on data1."""
    for name in ("final", "final_greedy"):
        path = root / r.OUTPUT / "runs" / key / name
        target = r.RAW / key / ("durable_" + name)
        if path.is_symlink():
            p.require(path.resolve() == target, "autorun.exact_final_storage_link")
        elif path.exists():
            # Only called by the new locked worker, after the old writer has exited.
            for source in path.rglob("*"):
                if source.is_file():
                    atomic_bytes(
                        target / source.relative_to(path), source.read_bytes(), immutable=True
                    )
            preserved = path.with_name(name + ".preserved_before_data1_link")
            p.require(not preserved.exists(), "autorun.no_preservation_overwrite")
            path.rename(preserved)
        if not path.is_symlink():
            target.mkdir(parents=True, exist_ok=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target, target_is_directory=True)


def cursor(key):
    saved = sorted((r.RAW / key / "updates").glob("*.pt"))
    return int(saved[-1].stem) if saved else 200


def phase(root, key):
    out = root / r.OUTPUT / "runs" / key
    if (out / "report.json").exists():
        return "done"
    if (out / "final_greedy/generation_manifest.json").exists():
        return "score"
    step = cursor(key)
    if step == 400:
        return "final"
    return (
        "feedback"
        if step == 200 and key.endswith("_29") and not (out / "rounds/epoch5/report.json").exists()
        else "sft"
    )


def threshold(phase_name, failures=0):
    return min(77824, FLOORS[phase_name] + 4096 * failures) if phase_name != "score" else 0


def cooldown(failures):
    return min(900, 60 * 2 ** min(max(failures - 1, 0), 4))


def wait_capacity(required, emit):
    for check in range(4):
        torch.cuda.empty_cache()
        free, _ = torch.cuda.mem_get_info()
        capacity = (free + torch.cuda.memory_reserved()) / 2**20
        if capacity >= required:
            return
        emit(
            dict(
                event="waiting_at_durable_capacity_boundary",
                own_capacity_MiB=capacity,
                required_MiB=required,
            )
        )
        if check < 3:
            time.sleep(20)
    raise BoundaryYield("capacity_wait")


def training_worker(root, key, attempt, floors):
    """Wrap control boundaries only; all updates, Adam math, replay and guards stay frozen."""
    stage = {"name": phase(root, key)}
    original_outer, original_emit, execute = r.outer, r.emit, old.inner.execute_update
    install_durable_writer(root)
    old.MIN_HOST_BYTES = 128 * 2**30

    def emit(value):
        original_emit(dict(value, autorun_phase=stage["name"]))
        if value.get("event") == "real_optimizer_update_checkpointed" and value["completed"] == 400:
            raise BoundaryYield("training_complete")

    def outer(*args, **kwargs):
        stage["name"] = "feedback" if key.endswith("_29") else "sft"
        result = original_outer(*args, **kwargs)
        stage["name"] = "sft"
        return result

    def update(*args, **kwargs):
        step = args[3]["step"] + 1
        journal = CONTROL / "update_attempts" / key / f"{attempt:04d}_{step:04d}.json"
        value = dict(run=key, attempt=attempt, step=step, returned_successfully=False, at=p.now())
        write(journal, value, immutable=True)
        result = execute(*args, **kwargs)
        write(journal, dict(value, returned_successfully=True, update_id=result["id"]))
        return result

    r.outer, r.emit, old.inner.execute_update = outer, emit, update
    r.s.wait_capacity = lambda event: wait_capacity(floors[stage["name"]], event)
    try:
        return r.worker(root, key, attempt)
    except BoundaryYield as reason:
        original_emit(
            dict(event="durable_worker_yield", run=key, reason=str(reason), completed=cursor(key))
        )
        return 43


def inventory(root, directory, jobs, point):
    by_index = {}
    for path in directory.rglob("completed/*.json"):
        item = p.checked(p.read_json(path), "anchored_generated_trajectory")
        index = item["job"]["index"]
        p.require(
            0 <= index < len(jobs)
            and item["job"] == jobs[index]
            and item["point_id"] == point["id"],
            "autorun.fixed_final_job_and_point",
        )
        f.validate_receipts(f.read_session(root, item), item, point["id"], False)
        p.require(
            index not in by_index or by_index[index]["id"] == item["id"],
            "autorun.no_duplicate_selected_final",
        )
        by_index[index] = item
    return by_index


def unfinished_call_upper_bound(directory, records):
    total = 0
    for path in directory.glob("resume_attempts/*/meter.json"):
        row = p.read_json(path)
        completed = records.get(row["index"])
        if completed is None or not Path(completed["path"]).is_relative_to(row["directory"]):
            total += row["generate_call_intents"]
    return total


def generate_remaining(root, directory, jobs, point, parent, model, tokenizer, attempt, required):
    records = inventory(root, directory, jobs, point)
    overhead = unfinished_call_upper_bound(directory, records)
    # If an adopted legacy final worker was lost, it lacked our call-ahead journal.
    # Charge all its uncommitted cases at the fixed 32-call maximum, never as zero work.
    key = point.get("run", {}).get("key")
    original_complete = sum(
        "resume_attempts" not in Path(row["path"]).parts for row in records.values()
    )
    if key:
        for path in (CONTROL / "resource_exits").glob(key + "_*.json"):
            lost = p.read_json(path)
            if lost["active"].get("adopted") and lost["completed_training"] == 400:
                overhead += (180 - original_complete) * 32
    p.require(overhead <= EXTRA_CALL_CAP_PER_RUN, "autorun.extra_call_budget")
    theta = {
        name: value.detach().clone()
        for name, value in model.named_parameters()
        if value.requires_grad
    }
    for job in jobs:
        if job["index"] in records:
            continue
        wait_capacity(required, r.emit)
        subdir = directory / "resume_attempts" / f"{attempt:04d}_{job['index']:04d}"
        meter_path = subdir / "meter.json"
        meter = dict(
            index=job["index"],
            directory=str(subdir.relative_to(root)),
            generate_call_intents=0,
            generate_calls_returned=0,
            at=p.now(),
        )
        write(meter_path, meter, immutable=True)
        original_generate = model.generate
        failure = []

        def metered(
            *args,
            meter=meter,
            meter_path=meter_path,
            original_generate=original_generate,
            failure=failure,
            **kwargs,
        ):
            # Reserve the complete uncommitted session against the retry overhead cap.
            p.require(
                overhead + meter["generate_call_intents"] < EXTRA_CALL_CAP_PER_RUN,
                "autorun.extra_call_budget",
            )
            meter["generate_call_intents"] += 1
            write(meter_path, meter)
            try:
                value = original_generate(*args, **kwargs)
            except Exception as error:
                failure.append(error)
                raise
            meter["generate_calls_returned"] += 1
            write(meter_path, meter)
            return value

        model.generate = metered
        try:
            item = f.generate_jobs(
                root,
                subdir,
                [job],
                point,
                parent["assets"],
                model,
                tokenizer,
                theta=theta,
                stochastic=False,
            )[0]
            p.require(
                item["actual_generate_calls"] == meter["generate_call_intents"],
                "autorun.meter_matches_frozen_decoder",
            )
        except Exception as error:
            if failure and isinstance(failure[-1], torch.OutOfMemoryError):
                raise failure[-1] from error
            raise
        finally:
            model.generate = original_generate
        records[job["index"]] = item
    rows = [records[job["index"]] for job in jobs]
    manifest = p.record(
        "anchored_generation_manifest",
        complete=True,
        point_id=point["id"],
        stochastic=False,
        tasks=parent["tasks"],
        source_manifest_id=parent["source_manifest_id"],
        trajectories=rows,
        total_generate_calls=sum(row["actual_generate_calls"] for row in rows),
        total_generated_tokens=sum(row["generated_tokens"] for row in rows),
        actual_sampling_GPU_workers=1,
        sealed_before_private_scoring=True,
        interrupted_attempt_generate_call_upper_bound=overhead,
        incomplete_resource_attempts_not_zero_reward=True,
        at=p.now(),
    )
    p.require(
        len(rows) == 180 and manifest["total_generate_calls"] <= 5760, "autorun.fixed_final_budget"
    )
    write(directory / "generation_manifest.json", manifest, immutable=True)
    return manifest


def final_worker(root, key, attempt, required):
    plan, parent = r.plans(root)
    final_links(root, key)
    install_durable_writer(root)
    run = next(row for row in plan["runs"] if row["key"] == key)
    out, original = root / r.OUTPUT / "runs" / key, root / r.d.OUTPUT / "runs" / key
    saved = torch.load(r.RAW / key / "updates/0400.pt", map_location="cpu", weights_only=False)
    p.require(
        saved["plan_id"] == plan["id"]
        and saved["run_key"] == key
        and saved["completed_updates"] == saved["rng"]["schedule_cursor"] == 400,
        "autorun.only_sealed_step400",
    )
    r.s.check_saved_state(saved["state"], saved["snapshot"], 400)
    totals, seen, ids = Counter(), Counter(), []
    for step in range(1, 401):
        report_path = (original if step <= 200 else out) / "updates" / f"{step:04d}" / "report.json"
        if step > 200 and not report_path.exists():
            committed = torch.load(
                r.RAW / key / "updates" / f"{step:04d}.pt", map_location="cpu", weights_only=False
            )
            p.require(
                committed["plan_id"] == plan["id"]
                and committed["run_key"] == key
                and committed["completed_updates"] == step,
                "autorun.repair_report_from_committed_checkpoint",
            )
            p.write_once(report_path, committed["update_report"])
            del committed
        report = p.read_json(report_path)
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
        ids.append(report["id"])
    cache_root = root / parent["trajectory_cache"]["cache_root"]
    cache = old.trajectory_materials.load_pool(
        cache_root, p.read_json(cache_root / "manifest.json"), "A"
    )
    p.require(
        totals["target_tokens"] == cache.actual_budget["target_tokens_all_epochs"]
        and totals["sequence_tokens"] == cache.actual_budget["sequence_tokens_all_epochs"]
        and seen == Counter({row["package_id"]: 10 for row in cache.packages})
        and ids[-1] == saved["update_report"]["id"],
        "autorun.same_effective_ten_pass_budget",
    )
    del cache
    model, _ = old.trajectory_training.load_registered_student(
        parent["assets"]["base_binding"], run["seed"], trainable=True
    )
    names = {name: value for name, value in model.named_parameters() if value.requires_grad}
    p.require(
        set(names)
        == {name.removeprefix("theta/") for name in saved["state"] if name.startswith("theta/")},
        "autorun.complete_step400_parameter_set",
    )
    with torch.no_grad():
        for name, value in names.items():
            value.copy_(saved["state"]["theta/" + name].to(value.device))
    r.s.restore_rng(saved["rng"])
    expected = {name: saved["state"]["theta/" + name] for name in names}
    p.require(
        old.gate.tensor_digest(names) == old.gate.tensor_digest(expected),
        "autorun.exact_step400_model",
    )
    del saved, expected
    gc.collect()
    model.eval()
    if (out / "final/point.json").exists():
        point = p.checked(p.read_json(out / "final/point.json"), "anchored_model_parameter_point")
        p.require(
            point["parameter_digest"] == old.gate.tensor_digest(names)
            and point["step"] == 400
            and point["run"] == run
            and point["origin_id"] == ids[-1],
            "autorun.reuse_identical_final_point",
        )
    else:
        adapter_path = out / "final/adapter.safetensors"
        if adapter_path.exists():
            # The adapter was not committed by point.json. Preserve it; never treat it as a point.
            orphan = adapter_path.with_name(f"adapter.uncommitted_attempt{attempt}.safetensors")
            p.require(not orphan.exists(), "autorun.no_orphan_overwrite")
            adapter_path.rename(orphan)
        point = old.point_record(
            root,
            out / "final",
            model,
            names,
            parent,
            run,
            step=400,
            kind="sole_recovered_delayed_epoch10_final",
            origin=ids[-1],
        )
    if not (out / "training_report.json").exists():
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
                final_point_id=point["id"],
                at=p.now(),
            ),
        )
    tokenizer = old.load_tokenizer(parent["assets"]["tokenizer_binding"])
    jobs = f.registration(
        parent["tasks"], pool="A", seed=run["seed"], round_index=2, stochastic=False
    )
    directory = out / "final_greedy"
    p.write_once(
        directory / "registration.json",
        p.record(
            "anchored_trajectory_registration", point_id=point["id"], stochastic=False, jobs=jobs
        ),
    )
    generate_remaining(root, directory, jobs, point, parent, model, tokenizer, attempt, required)
    r.emit(dict(event="final_generation_sealed_GPU_released_on_exit", run=key, sessions=180))
    return 0


def score_remaining(root, directory, source_root):
    frozen = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    p.require(
        frozen["complete"] and not frozen["stochastic"] and len(frozen["trajectories"]) == 180,
        "autorun.seal_all_180_before_scoring",
    )
    if (directory / "scoring_report.json").exists():
        report = p.checked(
            p.read_json(directory / "scoring_report.json"), "anchored_independent_scoring"
        )
        p.require(
            report["generation_manifest_id"] == frozen["id"]
            and report["complete"]
            and report["denominator"] == 180,
            "autorun.sealed_score_binding",
        )
        return report
    values, missing = {}, []
    for item in frozen["trajectories"]:
        index = item["job"]["index"]
        path = directory / "score_rows" / f"{index:04d}.json"
        if path.exists():
            value = p.read_json(path)
        elif (directory / "assessments" / f"{index:04d}.json").exists():
            assessment = p.read_json(directory / "assessments" / f"{index:04d}.json")
            p.require(
                assessment.get("session_id") == item["session_id"],
                "autorun.existing_assessment_binding",
            )
            value = dict(
                index=index,
                task_id=item["job"]["task"]["task_id"],
                repeat=0,
                group=item["job"]["task"]["group"],
                session_id=item["session_id"],
                assessment=assessment,
                Q=int(assessment["financial_valid"]),
            )
            write(path, value, immutable=True)
        else:
            missing.append(item)
            continue
        p.require(
            value["index"] == index
            and value["session_id"] == item["session_id"]
            and value["task_id"] == item["job"]["task"]["task_id"]
            and value["Q"] in (0, 1)
            and value["assessment"]["session_id"] == item["session_id"]
            and value["Q"] == int(value["assessment"]["financial_valid"]),
            "autorun.reuse_committed_score_only",
        )
        assessment_path = directory / "assessments" / f"{index:04d}.json"
        if not assessment_path.exists():
            write(assessment_path, value["assessment"], immutable=True)
        values[index] = value
    args = (
        str(root),
        str(source_root),
        frozen["tasks"],
        frozen["source_manifest_id"],
        frozen["point_id"],
        False,
    )
    if missing:
        with ProcessPoolExecutor(
            max_workers=12, initializer=f.initialize_scoring, initargs=args
        ) as executor:
            futures = {executor.submit(f.score_one, item): item for item in missing}
            for future in as_completed(futures):
                value = future.result()
                write(
                    directory / "score_rows" / f"{value['index']:04d}.json", value, immutable=True
                )
                write(
                    directory / "assessments" / f"{value['index']:04d}.json",
                    value["assessment"],
                    immutable=True,
                )
                values[value["index"]] = value
    results = [
        {key: val for key, val in values[index].items() if key != "assessment"}
        for index in range(180)
    ]
    report = p.record(
        "anchored_independent_scoring",
        generation_manifest_id=frozen["id"],
        point_id=frozen["point_id"],
        complete=True,
        denominator=180,
        scores=results,
        qualified=sum(row["Q"] for row in results),
        source_manifest_id=frozen["source_manifest_id"],
        private_references_never_sent_to_generator=True,
        financial_rule_unchanged=True,
        scoring_after_all_generation_complete=True,
        confirm_tasks_opened=0,
        finished_at=p.now(),
    )
    write(directory / "scoring_report.json", report, immutable=True)
    return report


def score_worker(root, key, attempt):
    plan, parent = r.plans(root)
    final_links(root, key)
    install_durable_writer(root)
    run = next(row for row in plan["runs"] if row["key"] == key)
    out = root / r.OUTPUT / "runs" / key
    generated = p.read_json(out / "final_greedy/generation_manifest.json")
    scored = score_remaining(root, out / "final_greedy", parent["private_scoring_source_root"])
    historical = p.read_json(
        root / r.d.OUTPUT / "runs" / key / "rounds/epoch5/feedback/generation_manifest.json"
    )
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
            interrupted_attempt_generate_call_upper_bound=generated.get(
                "interrupted_attempt_generate_call_upper_bound", 0
            ),
            historical_feedback_generate_calls=historical["total_generate_calls"],
            final_assessment_report_id=scored["id"],
            final_point_id=generated["point_id"],
            recovery_attempt=attempt,
            at=p.now(),
        ),
    )
    return 0
