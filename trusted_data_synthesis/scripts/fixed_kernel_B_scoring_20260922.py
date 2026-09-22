"""Resumable CPU scoring of complete, frozen B feedback/confirmation cohorts.

The unchanged feedback.score_one remains the only scoring implementation. A
complete cohort is mandatory before any private asset is opened; confirmation
additionally uses the six-model global generation seal enforced by confirm_views.
Each score_rows record atomically commits both the result and its assessment.
Assessment copies can therefore be repaired without rerunning a committed case.
Failures propagate and never become zero rewards. At most twelve reserved cases
are submitted concurrently; only missing committed score rows are resubmitted.
"""

from __future__ import annotations

import fcntl
import multiprocessing
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path

import fixed_kernel_B_common_20260922 as b
import fixed_kernel_B_confirm_views_20260922 as confirm_views

p, old = b.p, b.old
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_scoring_20260922.py"
SCORE_FIELDS = ("index", "task_id", "repeat", "group", "session_id", "Q")


@contextmanager
def _cohort_lock(directory):
    path = directory / "scoring.lock"
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _sealed_cohort(plan, job, directory):
    frozen = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    registration = p.checked(
        p.read_json(directory / "registration.json"), "B_generation_registration"
    )
    stochastic = job["phase"] == "feedback"
    task_count, case_count = (180, 360) if stochastic else (720, 720)
    tasks, trajectories, jobs = frozen["tasks"], frozen["trajectories"], registration["jobs"]
    p.require(
        frozen["complete"] is True
        and frozen["stochastic"] is registration["stochastic"] is stochastic
        and frozen["point_id"] == registration["point_id"] == job["point_id"]
        and frozen["source_manifest_id"]
        == registration["source_manifest_id"]
        == job["source_manifest_id"]
        and registration["protocol_id"] == plan["id"]
        and registration["seed"] == job["seed"]
        and registration["condition"] == job["condition"]
        and len(tasks) == len({row["task_id"] for row in tasks}) == task_count
        and len(trajectories) == len(jobs) == case_count
        and [row["index"] for row in jobs] == list(range(case_count))
        and all(type(row["index"]) is int for row in jobs)
        and all(Path(row["path"]).is_absolute() for row in tasks),
        "B_score.complete_fixed_cohort_before_private_assets",
    )
    expected_order = [
        (task, repeat) for task in tasks for repeat in ((1, 2) if stochastic else (0,))
    ]
    p.require(
        [(row["task"], row["repeat"]) for row in jobs] == expected_order,
        "B_score.original_task_repeat_order",
    )
    for expected, item in zip(jobs, trajectories, strict=True):
        p.checked(item, "anchored_generated_trajectory")
        p.require(
            item["job"] == expected
            and item["point_id"] == job["point_id"]
            and item["private_assessment_performed"] is False
            and type(item["actual_generate_calls"]) is int
            and 0 <= item["actual_generate_calls"] <= 32,
            "B_score.exact_registered_sealed_trajectory",
        )
    return frozen


def _validate_score(value, item, *, assessment):
    task, unit = item["job"]["task"], item["job"]
    p.require(
        type(value["index"]) is int
        and value["index"] == unit["index"]
        and value["task_id"] == task["task_id"]
        and value["repeat"] == unit["repeat"]
        and value["group"] == task["group"]
        and value["session_id"] == item["session_id"]
        and type(value["Q"]) is int
        and value["Q"] in (0, 1),
        "B_score.exact_case_task_session_and_binary_Q",
    )
    if assessment:
        assessed = value["assessment"]
        p.require(
            assessed["session_id"] == item["session_id"]
            and type(assessed["financial_valid"]) is bool
            and value["Q"] == int(assessed["financial_valid"]),
            "B_score.assessment_session_and_financial_valid",
        )


def _validate_report(report, frozen, job):
    p.checked(report, "anchored_independent_scoring")
    p.require(
        report["complete"] is True
        and report["generation_manifest_id"] == frozen["id"]
        and report["point_id"] == job["point_id"]
        and report["source_manifest_id"] == job["source_manifest_id"]
        and report["denominator"] == len(report["scores"]) == len(frozen["trajectories"])
        and report["financial_rule_unchanged"] is True
        and report["scoring_after_all_generation_complete"] is True
        and report["confirm_tasks_opened"] == (720 if job["phase"] == "confirm" else 0),
        "B_score.complete_report_exact_generation_binding",
    )
    for value, item in zip(report["scores"], frozen["trajectories"], strict=True):
        _validate_score(value, item, assessment=False)
    p.require(
        report["qualified"] == sum(value["Q"] for value in report["scores"]),
        "B_score.report_exact_qualified_total",
    )


def _inventory(directory, frozen):
    records = {}
    by_index = {item["job"]["index"]: item for item in frozen["trajectories"]}
    for path in sorted((directory / "score_rows").glob("*.json")):
        value = p.checked(p.read_json(path), "B_scored_case")
        index = value["index"]
        p.require(
            type(index) is int
            and index in by_index
            and index not in records
            and path.name == f"{index:04d}.json"
            and value["generation_manifest_id"] == frozen["id"]
            and value["point_id"] == frozen["point_id"]
            and value["source_manifest_id"] == frozen["source_manifest_id"],
            "B_score.committed_case_generation_binding",
        )
        _validate_score(value, by_index[index], assessment=True)
        records[index] = value
    return records


def initialize_scoring(raw, private, source_manifest_id, point_id, stochastic):
    """Route immutable assets to the unchanged scorer; no model is loaded."""
    old.feedback._SCORING = (
        Path(raw),
        private,
        source_manifest_id,
        point_id,
        stochastic,
        old.feedback.views.build_runtime(),
        {},
    )


def _confirmation_assets(root, plan, job, frozen, *, needed):
    manifest = p.checked(
        p.read_json(Path(b.RAW) / "confirm_views/manifest.json"), "source_view_manifest_v2"
    )
    p.require(
        manifest["id"] == frozen["source_manifest_id"] and manifest["tasks"] == frozen["tasks"],
        "B_score.exact_confirmation_view_manifest",
    )
    if needed:
        # offline_assets performs the complete global seal check before opening
        # even the first private confirmation catalog or bundle.
        private = confirm_views.offline_assets(root, plan, manifest, job["seal_path"])
        seal_id = private["generation_seal_id"]
        p.require(
            private["source_manifest_id"] == manifest["id"]
            and private["confirm_bundles_opened"] == 720
            and job["point_id"] in private["sealed_point_ids"],
            "B_score.private_capability_matches_sealed_point",
        )
    else:
        # A crash after all score rows committed needs only metadata validation,
        # assessment-copy repair and report creation, not another private read.
        private = None
        seal_id = confirm_views.require_generation_seal(root, plan, manifest, job["seal_path"])[
            "id"
        ]
    return private, seal_id


def _score_missing(job, attempt, directory, frozen, missing, private, seal_id, records):
    workers = min(12, len(missing))
    iterator = iter(missing)
    pending = {}

    with ProcessPoolExecutor(
        max_workers=workers,
        # Fork would copy the controller's task lock and this cohort lock into
        # children, preventing retries if their parent is killed mid-scoring.
        mp_context=multiprocessing.get_context("spawn"),
        initializer=initialize_scoring,
        initargs=(
            str(b.RAW),
            private,
            frozen["source_manifest_id"],
            frozen["point_id"],
            frozen["stochastic"],
        ),
    ) as executor:

        def fill_window():
            while len(pending) < workers:
                item = next(iterator, None)
                if item is None:
                    break
                index = item["job"]["index"]
                b.reserve("score_case", job["key"], attempt, index)
                pending[executor.submit(old.feedback.score_one, item)] = item

        try:
            fill_window()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda value: pending[value]["job"]["index"]):
                    item = pending.pop(future)
                    value = future.result()  # A failure is never an observed Q=0.
                    _validate_score(value, item, assessment=True)
                    row = p.record(
                        "B_scored_case",
                        **{field: value[field] for field in SCORE_FIELDS},
                        assessment=value["assessment"],
                        generation_manifest_id=frozen["id"],
                        point_id=frozen["point_id"],
                        source_manifest_id=frozen["source_manifest_id"],
                        generation_seal_id=seal_id,
                    )
                    index = value["index"]
                    b.write(directory / "score_rows" / f"{index:04d}.json", row, immutable=True)
                    records[index] = row
                    b.write(
                        directory / "assessments" / f"{index:04d}.json",
                        value["assessment"],
                        immutable=True,
                    )
                fill_window()
        except BaseException:
            for future in pending:
                future.cancel()
            raise


def run(root, job, attempt):
    """Score or resume one complete registered cohort, returning the legacy report."""
    root = Path(root).resolve()
    plan = b.read_protocol(root)
    candidate = Path(job["directory"])
    directory, raw = candidate.resolve(), Path(b.RAW).resolve()
    p.require(
        candidate.is_absolute()
        and ".." not in candidate.parts
        and directory.is_relative_to(raw)
        and directory != raw
        and job["phase"] in ("feedback", "confirm")
        and type(job["seed"]) is int
        and job["seed"] in (11, 29, 47)
        and job["condition"] in ("static", "delayed_c")
        and type(attempt) is int
        and attempt > 0,
        "B_score.fixed_job_and_confined_cohort",
    )
    with _cohort_lock(directory):
        frozen = _sealed_cohort(plan, job, directory)
        report_path = directory / "scoring_report.json"
        if report_path.exists():
            report = p.read_json(report_path)
            _validate_report(report, frozen, job)
            return report
        records = _inventory(directory, frozen)
        missing = [item for item in frozen["trajectories"] if item["job"]["index"] not in records]
        if job["phase"] == "confirm":
            private, seal_id = _confirmation_assets(root, plan, job, frozen, needed=bool(missing))
        else:
            private = (
                old.feedback.given.offline_assets(
                    root,
                    Path(plan["materials"]["private_scoring_source_root"]),
                    frozen["tasks"],
                )
                if missing
                else None
            )
            seal_id = None
            if private is not None:
                p.require(private["confirm_bundles_opened"] == 0, "B_score.feedback_dev_only")
        for index, value in records.items():
            p.require(value["generation_seal_id"] == seal_id, "B_score.same_global_generation_seal")
            b.write(
                directory / "assessments" / f"{index:04d}.json",
                value["assessment"],
                immutable=True,
            )
        if missing:
            _score_missing(job, attempt, directory, frozen, missing, private, seal_id, records)
        values = [records[item["job"]["index"]] for item in frozen["trajectories"]]
        report = p.record(
            "anchored_independent_scoring",
            generation_manifest_id=frozen["id"],
            point_id=frozen["point_id"],
            complete=True,
            denominator=len(values),
            scores=[{field: value[field] for field in SCORE_FIELDS} for value in values],
            qualified=sum(value["Q"] for value in values),
            source_manifest_id=frozen["source_manifest_id"],
            private_references_never_sent_to_generator=True,
            financial_rule_unchanged=True,
            scoring_after_all_generation_complete=True,
            confirm_tasks_opened=720 if job["phase"] == "confirm" else 0,
            generation_seal_id=seal_id,
            finished_at=p.now(),
        )
        b.write(report_path, report, immutable=True)
        return report
