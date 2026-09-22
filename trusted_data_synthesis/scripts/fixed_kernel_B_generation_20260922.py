"""Resume frozen B generation shards without changing the decoder or reading scores.

Only fully committed, registered trajectories with matching task/point/byte and
callback receipts are reusable. Incomplete sessions stay in their unique attempt
directories. Every model.generate call is reserved and journaled before execution;
completed-session accounting can be reconciled idempotently after interruption.
The caller controls scheduling, global generation sealing and subsequent scoring.
"""

from __future__ import annotations

import fcntl
import re
from contextlib import contextmanager
from pathlib import Path

import fixed_kernel_B_common_20260922 as b

p, old = b.p, b.old
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_generation_20260922.py"


def _inside_raw(path, *, directory=False):
    candidate = Path(path)
    p.require(candidate.is_absolute() and ".." not in candidate.parts, "B_generate.absolute_path")
    resolved, raw = candidate.resolve(), Path(b.RAW).resolve()
    p.require(resolved.is_relative_to(raw), "B_generate.confined_to_RAW")
    if directory:
        p.require(resolved != raw, "B_generate.specific_cohort_directory")
    return resolved


@contextmanager
def _durable_raw_records():
    """Keep numerical code intact; make its RAW JSON commit atomic and immutable."""
    previous = p.write_once

    def durable(path, value):
        if Path(path).resolve().is_relative_to(Path(b.RAW).resolve()):
            return b.write(path, value, immutable=True)
        return previous(path, value)

    p.write_once = durable
    try:
        yield
    finally:
        p.write_once = previous


@contextmanager
def _shard_lock(directory, key):
    path = directory / ".generation_locks" / (key + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _registration(plan, job, point):
    registration = p.checked(p.read_json(job["registration_path"]), "B_generation_registration")
    stochastic = job["phase"] == "feedback"
    expected = 360 if stochastic else 720
    registered = registration["jobs"]
    p.require(
        registration["protocol_id"] == plan["id"]
        and registration["point_id"] == point["id"]
        and registration["source_manifest_id"]
        == job["source_manifest_id"]
        == point["source_manifest_id"]
        and registration["seed"] == job["seed"]
        and registration["condition"] == job["condition"]
        and registration["stochastic"] is stochastic,
        "B_generate.fixed_registration_point_and_phase",
    )
    p.require(
        len(registered) == expected
        and [row["index"] for row in registered] == list(range(expected))
        and all(type(row["index"]) is int for row in registered)
        and len({(row["task"]["task_id"], row["repeat"]) for row in registered}) == expected
        and len({row["task"]["task_id"] for row in registered}) == (180 if stochastic else 720)
        and all(row["repeat"] in ((1, 2) if stochastic else (0,)) for row in registered)
        and all(type(row["seed"]) is int for row in registered)
        and all(Path(row["task"]["path"]).is_absolute() for row in registered),
        "B_generate.fixed_complete_cohort_registration",
    )
    by_index = {row["index"]: row for row in registered}
    selected = job["jobs"]
    p.require(
        selected
        and len({row["index"] for row in selected}) == len(selected)
        and all(by_index.get(row["index"]) == row for row in selected),
        "B_generate.exact_preregistered_shard",
    )
    return registration, by_index


def _validate_session(directory, item, point, stochastic):
    reference = Path(item["path"])
    p.require(
        not reference.is_absolute()
        and ".." not in reference.parts
        and (Path(b.RAW) / reference).resolve().is_relative_to(directory),
        "B_generate.cohort_session_reference",
    )
    session = old.feedback.read_session(b.RAW, item)
    old.feedback.validate_receipts(session, item, point["id"], stochastic)
    task = item["job"]["task"]
    p.require(
        session["identity"]
        == dict(
            task_id=task["task_id"],
            family=task["group"],
            surface_version_id=task["surface_version_id"],
            public_messages_sha256=task["public_messages_sha256"],
            parent_manifest_id=point["source_manifest_id"],
        )
        and all(
            turn["provider_receipt"]["virtual_or_final_parameter_digest"]
            == point["parameter_digest"]
            and turn["provider_receipt"]["original_greedy_backend"] is (not stochastic)
            for turn in session["turns"]
        ),
        "B_generate.exact_task_source_and_parameter_receipts",
    )


def inventory(directory, registered_jobs, selected_jobs, point, *, stochastic):
    """Check all committed metadata, but decompress only this shard's sessions."""
    directory = _inside_raw(directory, directory=True)
    selected_indices = {row["index"] for row in selected_jobs}
    records = {}
    for path in sorted(directory.rglob("completed/*.json")):
        item = p.checked(p.read_json(path), "anchored_generated_trajectory")
        index = item["job"]["index"]
        p.require(
            index in registered_jobs
            and item["job"] == registered_jobs[index]
            and item["point_id"] == point["id"]
            and item["private_assessment_performed"] is False
            and type(item["actual_generate_calls"]) is int
            and 0 <= item["actual_generate_calls"] <= 32,
            "B_generate.committed_registered_job_and_point",
        )
        p.require(index not in records, "B_generate.one_committed_record_per_job")
        records[index] = item
        if index in selected_indices:
            _validate_session(directory, item, point, stochastic)
    return {index: item for index, item in records.items() if index in selected_indices}


def _load_model(plan, job, point):
    assets = plan["materials"]["assets"]
    p.require(
        old.views.binding()["id"] == plan["materials"]["runtime_binding"]["id"]
        and point["base_binding_id"] == assets["base_binding"]["id"],
        "B_generate.frozen_runtime_and_base_binding",
    )
    adapter = _inside_raw(Path(b.RAW) / point["adapter_directory"] / point["adapter"]["path"])
    model, _ = old.trajectory_training.load_registered_student(
        assets["base_binding"],
        job["seed"],
        trainable=False,
        adapter_path=adapter,
        adapter_record=point["adapter"],
    )
    p.require(
        old.components.adapter_digest(model) == point["adapter"]["parameter_digest"],
        "B_generate.loaded_exact_adapter_digest",
    )
    actual = {
        name: value
        for name, value in model.named_parameters()
        if name.endswith((".lora_A", ".lora_B"))
    }
    p.require(
        old.gate.tensor_digest(actual) == point["parameter_digest"],
        "B_generate.loaded_exact_parameter_point",
    )
    return model, old.load_tokenizer(assets["tokenizer_binding"])


def _generate_one(attempt_directory, job, unit, point, assets, model, tokenizer, attempt):
    meter_path = attempt_directory / "meters" / f"{unit['index']:04d}.json"
    meter = dict(
        job_key=job["key"],
        index=unit["index"],
        attempt=attempt,
        point_id=point["id"],
        directory=str(attempt_directory.relative_to(b.RAW)),
        generate_call_intents=0,
        generate_calls_returned=0,
        status="RUNNING",
    )
    b.write(meter_path, meter, immutable=True)
    original_generate, failures = model.generate, []

    def metered(*args, **kwargs):
        call_number = meter["generate_call_intents"] + 1
        p.require(call_number <= 32, "B_generate.at_most_32_calls_per_session")
        b.reserve("generate_call", job["key"], attempt, f"{unit['index']}_{call_number}")
        meter["generate_call_intents"] = call_number
        b.write(meter_path, meter, immutable=False)
        try:
            value = original_generate(*args, **kwargs)
        except BaseException as failure:
            failures.append(failure)
            raise
        meter["generate_calls_returned"] += 1
        b.write(meter_path, meter, immutable=False)
        return value

    model.generate = metered
    try:
        with _durable_raw_records():
            result = old.feedback.generate_jobs(
                root=b.RAW,
                directory=attempt_directory,
                jobs=[unit],
                point=point,
                assets=assets,
                model=model,
                tokenizer=tokenizer,
                stochastic=job["phase"] == "feedback",
            )
        p.require(len(result) == 1, "B_generate.one_session_per_commit")
        item = p.checked(result[0], "anchored_generated_trajectory")
        p.require(
            item["job"] == unit
            and item["point_id"] == point["id"]
            and item["actual_generate_calls"]
            == meter["generate_call_intents"]
            == meter["generate_calls_returned"]
            and p.read_json(attempt_directory / "completed" / f"{unit['index']:04d}.json") == item,
            "B_generate.meter_matches_committed_trajectory",
        )
        _validate_session(Path(job["directory"]).resolve(), item, point, job["phase"] == "feedback")
        b.generation_committed(point["id"], unit["index"], item)
        meter.update(status="COMMITTED", committed_record_id=item["id"])
        b.write(meter_path, meter, immutable=False)
        return item
    except BaseException as error:
        actual_error = failures[-1] if failures else error
        meter.update(status="INTERRUPTED", exception_type=type(actual_error).__name__)
        b.write(meter_path, meter, immutable=False)
        if (
            isinstance(actual_error, old.feedback.torch.OutOfMemoryError)
            and actual_error is not error
        ):
            raise actual_error from error
        raise
    finally:
        model.generate = original_generate


def run(root, job_dict, attempt, required_MiB=57344):
    """Complete one registered shard, returning its immutable generation-only report."""
    root, job = Path(root).resolve(), job_dict
    plan = b.read_protocol(root)  # Includes frozen scientific-code byte verification.
    p.require(
        isinstance(job["key"], str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+", job["key"])
        and job["key"] not in (".", "..")
        and job["phase"] in ("feedback", "confirm")
        and type(job["seed"]) is int
        and job["seed"] in (11, 29, 47)
        and job["condition"] in ("static", "delayed_c")
        and type(attempt) is int
        and attempt > 0
        and Path(job["point_path"]).is_absolute()
        and Path(job["registration_path"]).is_absolute(),
        "B_generate.fixed_job_identity_and_attempt",
    )
    directory = _inside_raw(job["directory"], directory=True)
    point = p.checked(p.read_json(job["point_path"]), "anchored_model_parameter_point")
    registration, registered = _registration(plan, job, point)
    report_path = directory / "job_reports" / (job["key"] + ".json")
    with _shard_lock(directory, job["key"]):
        if report_path.exists():
            previous = p.checked(p.read_json(report_path), "B_generation_job_report")
            p.require(
                previous["job_sha256"] == p.sha(p.encode(job))
                and previous["protocol_id"] == plan["id"]
                and previous["registration_id"] == registration["id"]
                and previous["point_id"] == point["id"],
                "B_generate.existing_report_exact_job_binding",
            )
        records = inventory(
            directory, registered, job["jobs"], point, stochastic=job["phase"] == "feedback"
        )
        for index, item in records.items():
            # Reconcile a crash after the completed JSON committed but before its
            # accounting transaction; common.generation_committed is idempotent.
            b.generation_committed(point["id"], index, item)
        missing = [unit for unit in job["jobs"] if unit["index"] not in records]
        if missing:
            attempt_directory = directory / "attempts" / f"{job['key']}_attempt{attempt:04d}"
            attempt_directory.mkdir(parents=True, exist_ok=False)
            model, tokenizer = _load_model(plan, job, point)
            for unit in missing:
                b.capacity_boundary("generation", required_MiB)
                item = _generate_one(
                    attempt_directory,
                    job,
                    unit,
                    point,
                    plan["materials"]["assets"],
                    model,
                    tokenizer,
                    attempt,
                )
                records[unit["index"]] = item
                b.emit(
                    dict(
                        event="B_generation_session_committed",
                        job_key=job["key"],
                        attempt=attempt,
                        index=unit["index"],
                        point_id=point["id"],
                    )
                )
        rows = [records[unit["index"]] for unit in job["jobs"]]
        report = p.record(
            "B_generation_job_report",
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
            source_manifest_id=job["source_manifest_id"],
            stochastic=job["phase"] == "feedback",
            trajectories=rows,
            trajectory_count=len(rows),
            total_generate_calls=sum(row["actual_generate_calls"] for row in rows),
            total_generated_tokens=sum(row["generated_tokens"] for row in rows),
            private_assessment_performed=False,
            complete_global_cohort_not_claimed=True,
        )
        b.write(report_path, report, immutable=True)
        return report
