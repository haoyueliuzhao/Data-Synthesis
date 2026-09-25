"""Three-arm short-range evaluation with one all-4860 private-scoring barrier.

The original decoder, session receipts, runtime and financial score_one are
unchanged. New code binds real arm labels, the new 180-task panel, two decoding
modes, resumable work units and their independent physical-budget context.
"""

import json
import multiprocessing
import re
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, SimpleNamespace

import fixed_kernel_B_generation_20260922 as legacy_generation
import fixed_kernel_B_scoring_20260922 as legacy_scoring

p = legacy_generation.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_evaluation_20260926.py"
ARMS = ("static", "positive", "negative")
SEEDS = (11, 29, 47)
MODES = ("stochastic", "greedy")
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
SCORE_FIELDS = legacy_scoring.SCORE_FIELDS


def _helpers(c):
    """Rebind pure old helpers to a new RAW/context without mutating old globals."""
    namespace = {**vars(legacy_generation), "b": c, "old": c.old, "p": c.p}
    names = ("_inside_raw", "_validate_session", "inventory", "_load_model")
    for name in names:
        original = getattr(legacy_generation, name)
        namespace[name] = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        namespace[name].__kwdefaults__ = original.__kwdefaults__
    return SimpleNamespace(**{name: namespace[name] for name in names})


def _reference(reference):
    path = Path(reference["path"])
    p.require(
        path.is_absolute() and ".." not in path.parts and path.resolve() == path and path.is_file(),
        "calibration_eval.registered_absolute_regular_asset",
    )
    raw = path.read_bytes()
    p.require(p.sha(raw) == reference["sha256"], "calibration_eval.registered_asset_bytes")
    if "bytes" in reference:
        p.require(len(raw) == reference["bytes"], "calibration_eval.registered_asset_size")
    value = json.loads(raw)
    if "id" in reference:
        p.require(value["id"] == reference["id"], "calibration_eval.registered_asset_identity")
    return value


def public_manifest(plan):
    """Never read/hash the private index here, including during generation."""
    manifest = p.checked(_reference(plan["panel"]["manifest"]), "source_view_manifest_v2")
    admission = p.checked(_reference(plan["panel"]["admission"]), "calibration_panel_admission")
    tasks = manifest["tasks"]
    p.require(
        manifest["split"] == "calibration"
        and len(tasks) == len({row["task_id"] for row in tasks}) == 180
        and Counter(row["group"] for row in tasks) == dict.fromkeys(GROUPS, 60)
        and all(Path(row["path"]).is_absolute() for row in tasks)
        and admission["passed"] is True
        and admission["source_manifest_id"] == manifest["id"],
        "calibration_eval.admitted_new180_fixed_three_groups",
    )
    return manifest


def _job(job, attempt):
    p.require(
        isinstance(job["key"], str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+", job["key"])
        and job["key"] not in (".", "..")
        and job["phase"] in MODES
        and type(job["seed"]) is int
        and job["seed"] in SEEDS
        and job["condition"] in ARMS
        and type(attempt) is int
        and attempt > 0,
        "calibration_eval.explicit_three_arm_two_mode_job",
    )


def _registration(plan, job, point_id, manifest):
    registered = p.checked(
        p.read_json(job["registration_path"]), "direction_calibration_generation_registration"
    )
    stochastic = job["phase"] == "stochastic"
    expected = [
        (task, repeat) for task in manifest["tasks"] for repeat in ((1, 2) if stochastic else (0,))
    ]
    jobs = registered["jobs"]
    p.require(
        registered["protocol_id"] == plan["id"]
        and registered["point_id"] == point_id
        and registered["source_manifest_id"] == job["source_manifest_id"] == manifest["id"]
        and registered["seed"] == job["seed"]
        and registered["condition"] == job["condition"]
        and registered["phase"] == job["phase"]
        and registered["stochastic"] is stochastic
        and len(jobs) == (360 if stochastic else 180)
        and [(unit["task"], unit["repeat"]) for unit in jobs] == expected
        and [unit["index"] for unit in jobs] == list(range(len(jobs)))
        and all(type(unit["index"]) is int and type(unit["seed"]) is int for unit in jobs),
        "calibration_eval.registered_exact_task_repeat_arm_mode",
    )
    return registered, {unit["index"]: unit for unit in jobs}


@contextmanager
def _durable_records(c):
    previous = c.p.write_once

    def durable(path, value):
        if Path(path).resolve().is_relative_to(Path(c.RAW).resolve()):
            return c.write(path, value, immutable=True)
        return previous(path, value)

    c.p.write_once = durable
    try:
        yield
    finally:
        c.p.write_once = previous


def _generate_one(
    c, helpers, attempt_directory, job, unit, point, assets, model, tokenizer, attempt
):
    meter_path = attempt_directory / "meters" / f"{unit['index']:04d}.json"
    meter = dict(
        job_key=job["key"],
        index=unit["index"],
        attempt=attempt,
        point_id=point["id"],
        phase=job["phase"],
        condition=job["condition"],
        generate_call_intents=0,
        generate_calls_returned=0,
        status="RUNNING",
    )
    c.write(meter_path, meter)
    original_generate, failures = model.generate, []

    def metered(*args, **kwargs):
        number = meter["generate_call_intents"] + 1
        p.require(number <= 32, "calibration_eval.at_most32_generate_calls")
        c.reserve("generate_call", job["key"], attempt, f"{unit['index']}_{number}")
        meter["generate_call_intents"] = number
        c.write(meter_path, meter, immutable=False)
        try:
            value = original_generate(*args, **kwargs)
        except BaseException as failure:
            failures.append(failure)
            raise
        meter["generate_calls_returned"] += 1
        c.write(meter_path, meter, immutable=False)
        return value

    model.generate = metered
    try:
        with _durable_records(c):
            result = c.old.feedback.generate_jobs(
                root=c.RAW,
                directory=attempt_directory,
                jobs=[unit],
                point=point,
                assets=assets,
                model=model,
                tokenizer=tokenizer,
                stochastic=job["phase"] == "stochastic",
            )
        p.require(len(result) == 1, "calibration_eval.one_session_per_commit")
        item = p.checked(result[0], "anchored_generated_trajectory")
        p.require(
            item["job"] == unit
            and item["point_id"] == point["id"]
            and item["actual_generate_calls"]
            == meter["generate_call_intents"]
            == meter["generate_calls_returned"]
            and p.read_json(attempt_directory / "completed" / f"{unit['index']:04d}.json") == item,
            "calibration_eval.actual_calls_match_committed_session",
        )
        helpers._validate_session(
            Path(job["directory"]).resolve(), item, point, job["phase"] == "stochastic"
        )
        # Context includes decoding mode (from repeat) in the ledger key. Point
        # identity itself is unchanged across both decoding modes.
        c.generation_committed(point["id"], unit["index"], item)
        meter.update(status="COMMITTED", committed_record_id=item["id"])
        c.write(meter_path, meter, immutable=False)
        return item
    except BaseException as error:
        actual = failures[-1] if failures else error
        meter.update(status="INTERRUPTED", exception_type=type(actual).__name__)
        c.write(meter_path, meter, immutable=False)
        if isinstance(actual, c.old.feedback.torch.OutOfMemoryError) and actual is not error:
            raise actual from error
        raise
    finally:
        model.generate = original_generate


def run_generation(c, root, job, attempt, required=57344):
    _job(job, attempt)
    root = Path(root).resolve()
    plan = c.read_protocol(root)
    manifest = public_manifest(plan)
    helpers = _helpers(c)
    directory = helpers._inside_raw(job["directory"], directory=True)
    point_path = helpers._inside_raw(job["point_path"])
    helpers._inside_raw(job["registration_path"])
    point = p.checked(p.read_json(point_path), "anchored_model_parameter_point")
    p.require(
        point["step"] == 240
        and point["source_manifest_id"] == manifest["id"]
        and point["run"]["seed"] == job["seed"]
        and point["run"]["condition"] == job["condition"]
        and job.get("point_id", point["id"]) == point["id"],
        "calibration_eval.real_step240_correct_arm_and_seed",
    )
    registration, registered = _registration(plan, job, point["id"], manifest)
    selected = job["jobs"]
    p.require(
        selected
        and len({unit["index"] for unit in selected}) == len(selected)
        and all(registered.get(unit["index"]) == unit for unit in selected),
        "calibration_eval.exact_registered_shard",
    )
    report_path = directory / "job_reports" / (job["key"] + ".json")
    with legacy_generation._shard_lock(directory, job["key"]):
        if report_path.exists():
            report = p.checked(
                p.read_json(report_path), "direction_calibration_generation_job_report"
            )
            p.require(
                report["job_sha256"] == p.sha(p.encode(job))
                and report["protocol_id"] == plan["id"]
                and report["registration_id"] == registration["id"],
                "calibration_eval.existing_shard_binding",
            )
        records = helpers.inventory(
            directory, registered, selected, point, stochastic=job["phase"] == "stochastic"
        )
        for index, item in records.items():
            c.generation_committed(point["id"], index, item)
        missing = [unit for unit in selected if unit["index"] not in records]
        if missing:
            attempt_directory = directory / "attempts" / f"{job['key']}_attempt{attempt:04d}"
            attempt_directory.mkdir(parents=True, exist_ok=False)
            model, tokenizer = helpers._load_model(plan, job, point)
            for unit in missing:
                c.capacity_boundary("generation", required)
                records[unit["index"]] = _generate_one(
                    c,
                    helpers,
                    attempt_directory,
                    job,
                    unit,
                    point,
                    plan["materials"]["assets"],
                    model,
                    tokenizer,
                    attempt,
                )
        rows = [records[unit["index"]] for unit in selected]
        report = p.record(
            "direction_calibration_generation_job_report",
            status="COMPLETE",
            complete=True,
            protocol_id=plan["id"],
            registration_id=registration["id"],
            job_key=job["key"],
            job_sha256=p.sha(p.encode(job)),
            phase=job["phase"],
            seed=job["seed"],
            condition=job["condition"],
            point_id=point["id"],
            source_manifest_id=manifest["id"],
            stochastic=job["phase"] == "stochastic",
            trajectories=rows,
            trajectory_count=len(rows),
            total_generate_calls=sum(row["actual_generate_calls"] for row in rows),
            total_generated_tokens=sum(row["generated_tokens"] for row in rows),
            private_assessment_performed=False,
            complete_global_cohort_not_claimed=True,
        )
        c.write(report_path, report)
        return report


def _sealed_cohort(c, plan, job, directory, manifest):
    frozen = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    registration_path = job.get("registration_path", str(directory / "registration.json"))
    _helpers(c)._inside_raw(registration_path)
    registration, registered = _registration(
        plan, {**job, "registration_path": registration_path}, job["point_id"], manifest
    )
    trajectories = frozen["trajectories"]
    p.require(
        frozen["complete"] is True
        and frozen["stochastic"] is registration["stochastic"]
        and frozen["point_id"] == job["point_id"]
        and frozen["source_manifest_id"] == manifest["id"]
        and frozen["tasks"] == manifest["tasks"]
        and len(trajectories) == len(registered),
        "calibration_eval.complete_exact_cohort_before_private_reads",
    )
    for expected, item in zip(registered.values(), trajectories, strict=True):
        p.checked(item, "anchored_generated_trajectory")
        p.require(
            item["job"] == expected
            and item["point_id"] == job["point_id"]
            and item["private_assessment_performed"] is False
            and type(item["actual_generate_calls"]) is int
            and 0 <= item["actual_generate_calls"] <= 32,
            "calibration_eval.exact_sealed_trajectory",
        )
    return frozen


def require_generation_seal(c, plan, manifest, seal_path):
    helpers = _helpers(c)
    path = helpers._inside_raw(seal_path)
    seal = p.checked(p.read_json(path), "calibration_generation_seal")
    cohorts = seal["cohorts"]
    p.require(
        seal["protocol_id"] == plan["id"]
        and seal["source_manifest_id"] == manifest["id"]
        and seal["complete"] is True
        and seal["all_generation_workers_exited"] is True
        and seal["total_trajectories"] == 4860
        and len(cohorts) == 18
        and {(row["condition"], row["seed"], row["phase"]) for row in cohorts}
        == {(arm, seed, mode) for arm in ARMS for seed in SEEDS for mode in MODES},
        "calibration_eval.all4860_18cohorts_workers_exited_before_private_reads",
    )
    points, task_seeds, cohort_keys, total = {}, {}, set(), 0
    for row in cohorts:
        _job(row, 1)
        p.require(row["key"] not in cohort_keys, "calibration_eval.unique_cohort_key")
        cohort_keys.add(row["key"])
        point_key = row["condition"], row["seed"]
        p.require(
            points.get(point_key, row["point_id"]) == row["point_id"],
            "calibration_eval.same_model_both_modes",
        )
        points[point_key] = row["point_id"]
        path = helpers._inside_raw(row["generation_manifest_path"])
        p.require(
            path.name == "generation_manifest.json"
            and p.sha(path) == row["generation_manifest_sha256"],
            "calibration_eval.sealed_cohort_bytes",
        )
        frozen = _sealed_cohort(
            c, plan, {**row, "source_manifest_id": manifest["id"]}, path.parent, manifest
        )
        total += len(frozen["trajectories"])
        seeds = [item["job"]["seed"] for item in frozen["trajectories"]]
        seed_key = row["seed"], row["phase"]
        p.require(
            task_seeds.get(seed_key, seeds) == seeds,
            "calibration_eval.matched_sampling_seeds_across_arms",
        )
        task_seeds[seed_key] = seeds
    p.require(
        total == 4860 and len(set(points.values())) == 9,
        "calibration_eval.nine_real_model_points_exact4860",
    )
    return seal


def _private_assets(plan, manifest, seal):
    """Caller must validate the all-cohort seal before even hashing this index."""
    assets = p.checked(_reference(plan["panel"]["private_assets"]), "calibration_private_assets")
    p.require(
        assets["source_manifest_id"] == manifest["id"],
        "calibration_eval.private_index_bound_to_public_panel",
    )
    rows = assets["bundles"]
    tasks = {row["task_id"]: row for row in manifest["tasks"]}
    p.require(
        len(rows) == 180 and {row["task_id"] for row in rows} == set(tasks),
        "calibration_eval.exact180_private_bundles",
    )
    bindings = _reference(assets["native_bindings"])
    bundles = {}
    for row in rows:
        bundle = _reference(row)
        task = tasks[row["task_id"]]
        body = {key: value for key, value in bundle.items() if key != "id"}
        p.require(
            bundle["id"] == "EvaluationTaskBundle:" + p.sha(p.encode(body))
            and bundle["task_id"] == row["task_id"]
            and bundle["source_cluster"] == task["source_cluster"]
            and bundle["family"] == task["group"]
            and bundle["validation"]["status"] == "passed",
            "calibration_eval.real_private_reference_identity_and_group",
        )
        bundles[row["task_id"]] = bundle
    return dict(
        bundles=bundles,
        native_bindings=bindings,
        source_manifest_id=manifest["id"],
        generation_seal_id=seal["id"],
        calibration_bundles_opened=180,
        confirm_bundles_opened=0,
        private_uses="offline scoring only after all4860 sealed",
    )


def _score_inventory(directory, frozen, job, seal):
    by_index = {item["job"]["index"]: item for item in frozen["trajectories"]}
    records = {}
    for path in sorted((directory / "score_rows").glob("*.json")):
        value = p.checked(p.read_json(path), "direction_calibration_scored_case")
        index = value["index"]
        p.require(
            type(index) is int
            and index in by_index
            and index not in records
            and path.name == f"{index:04d}.json"
            and value["generation_manifest_id"] == frozen["id"]
            and value["generation_seal_id"] == seal["id"]
            and value["point_id"] == frozen["point_id"]
            and value["source_manifest_id"] == frozen["source_manifest_id"]
            and value["condition"] == job["condition"]
            and value["phase"] == job["phase"]
            and value["seed"] == job["seed"],
            "calibration_eval.exact_committed_score_binding",
        )
        legacy_scoring._validate_score(value, by_index[index], assessment=True)
        records[index] = value
    return records


def _score_missing(c, job, attempt, directory, frozen, missing, private, seal, records):
    workers = min(12, len(missing))
    iterator, pending = iter(missing), {}
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=legacy_scoring.initialize_scoring,
        initargs=(
            str(c.RAW),
            private,
            frozen["source_manifest_id"],
            frozen["point_id"],
            frozen["stochastic"],
        ),
    ) as executor:

        def fill():
            while len(pending) < workers:
                item = next(iterator, None)
                if item is None:
                    return
                c.reserve("score_case", job["key"], attempt, item["job"]["index"])
                pending[executor.submit(c.old.feedback.score_one, item)] = item

        try:
            fill()
            while pending:
                done, _pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda value: pending[value]["job"]["index"]):
                    item = pending.pop(future)
                    value = future.result()
                    legacy_scoring._validate_score(value, item, assessment=True)
                    row = p.record(
                        "direction_calibration_scored_case",
                        **{key: value[key] for key in SCORE_FIELDS},
                        assessment=value["assessment"],
                        generation_manifest_id=frozen["id"],
                        generation_seal_id=seal["id"],
                        point_id=frozen["point_id"],
                        source_manifest_id=frozen["source_manifest_id"],
                        condition=job["condition"],
                        phase=job["phase"],
                        seed=job["seed"],
                    )
                    index = value["index"]
                    c.write(directory / "score_rows" / f"{index:04d}.json", row)
                    records[index] = row
                    c.write(directory / "assessments" / f"{index:04d}.json", value["assessment"])
                fill()
        except BaseException:
            for future in pending:
                future.cancel()
            raise


def run_scoring(c, root, job, attempt):
    _job(job, attempt)
    plan = c.read_protocol(Path(root).resolve())
    manifest = public_manifest(plan)
    directory = _helpers(c)._inside_raw(job["directory"], directory=True)
    with legacy_scoring._cohort_lock(directory):
        frozen = _sealed_cohort(c, plan, job, directory, manifest)
        seal = require_generation_seal(c, plan, manifest, job["seal_path"])
        p.require(
            any(
                row["seed"] == job["seed"]
                and row["condition"] == job["condition"]
                and row["phase"] == job["phase"]
                and row["point_id"] == job["point_id"]
                and Path(row["generation_manifest_path"]).parent == directory
                for row in seal["cohorts"]
            ),
            "calibration_eval.scoring_only_own_sealed_cohort",
        )
        report_path = directory / "scoring_report.json"
        if report_path.exists():
            report = p.checked(p.read_json(report_path), "anchored_independent_scoring")
            p.require(
                report["protocol_id"] == plan["id"]
                and report["generation_manifest_id"] == frozen["id"]
                and report["generation_seal_id"] == seal["id"]
                and report["point_id"] == job["point_id"]
                and report["source_manifest_id"] == manifest["id"]
                and report["complete"] is True
                and report["condition"] == job["condition"]
                and report["phase"] == job["phase"]
                and report["seed"] == job["seed"]
                and report["financial_rule_unchanged"] is True
                and report["scoring_after_all_generation_complete"] is True
                and report["denominator"] == len(report["scores"]) == len(frozen["trajectories"])
                and report["qualified"] == sum(row["Q"] for row in report["scores"]),
                "calibration_eval.exact_reused_scoring_report",
            )
            for value, item in zip(report["scores"], frozen["trajectories"], strict=True):
                legacy_scoring._validate_score(value, item, assessment=False)
            return report
        records = _score_inventory(directory, frozen, job, seal)
        missing = [item for item in frozen["trajectories"] if item["job"]["index"] not in records]
        private = _private_assets(plan, manifest, seal) if missing else None
        for index, value in records.items():
            c.write(directory / "assessments" / f"{index:04d}.json", value["assessment"])
        if missing:
            _score_missing(c, job, attempt, directory, frozen, missing, private, seal, records)
        values = [records[item["job"]["index"]] for item in frozen["trajectories"]]
        report = p.record(
            "anchored_independent_scoring",
            protocol_id=plan["id"],
            generation_manifest_id=frozen["id"],
            generation_seal_id=seal["id"],
            point_id=frozen["point_id"],
            source_manifest_id=manifest["id"],
            complete=True,
            denominator=len(values),
            scores=[{key: row[key] for key in SCORE_FIELDS} for row in values],
            qualified=sum(row["Q"] for row in values),
            condition=job["condition"],
            phase=job["phase"],
            seed=job["seed"],
            financial_rule_unchanged=True,
            scoring_after_all_generation_complete=True,
            private_references_never_sent_to_generator=True,
            calibration_tasks_opened=180,
            confirm_tasks_opened=0,
            finished_at=p.now(),
        )
        c.write(report_path, report)
        return report
