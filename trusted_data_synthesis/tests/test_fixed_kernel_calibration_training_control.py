"""Synthetic CPU-only checks of the isolated, finite negative-training controller.

No historical artifacts, network, real subprocesses or GPU work are used here.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
r = importlib.import_module("run_fixed_kernel_calibration_training_20260926")
c, p = r, r.p


def setup(tmp_path, monkeypatch):
    root, raw = tmp_path / "repo", tmp_path / "training_stage_20260926"
    root.mkdir()
    raw.mkdir()
    source = root / "synthetic_source.py"
    source.write_text("frozen = True\n")
    monkeypatch.setattr(c, "RAW", raw)
    monkeypatch.setattr(c.b, "read_protocol", lambda _: {"id": "parent"})
    previous = dict(
        id="stage1",
        parent_B_protocol_id="parent",
        prospective_stage2_material_admission_id="admission",
    )
    monkeypatch.setattr(r.stage1, "read_protocol", lambda _: previous)
    monkeypatch.setattr(r, "_admission", lambda value, expected: value)
    plan = p.record(
        r.PROTOCOL,
        frozen=True,
        parent_B_protocol_id="parent",
        stage1_protocol_id="stage1",
        registration_inputs={},
        materials_admission=dict(
            id="admission",
            distributions={
                str(seed): dict(
                    id=f"reflection_{seed}",
                    distribution_sha256=dict(negative=f"distribution_{seed}"),
                )
                for seed in (11, 29, 47)
            },
            reusable_refs=[
                dict(job_key=f"B_prefix_{seed}", step=200, sha256=f"prefix_{seed}")
                for seed in (11, 29, 47)
            ],
        ),
        seeds=[11, 29, 47],
        jobs=[dict(key=f"B_negative_{seed}", seed=seed) for seed in (11, 29, 47)],
        sources={"synthetic_source.py": p.sha(source)},
        start=200,
        stop=240,
        condition="negative",
        committed_optimizer_updates=120,
        per_seed_committed_updates=40,
        new_positive_or_static_updates=0,
        reused_step240_models=6,
        no_directional_sign_gate=True,
        no_seed_or_task_selection=True,
        new_training_updates=120,
        new_feedback_sessions=0,
        new_scoring_cases=0,
        new_population_passes=0,
        physical_budget=dict(
            optimizer=144,
            worker_start=24,
            population=0,
            generate_call=0,
            score_case=0,
            feedback=0,
            probe=0,
        ),
        per_seed_optimizer_attempt_cap=48,
        maximum_attempts_per_job=8,
        resources=dict(
            maximum_parallel_workers=3,
            required_MiB=32768,
            host_free_bytes=64 * 2**30,
            minimum_disk_free_bytes=100 * 2**30,
        ),
        panel_status="NOT_READY",
        evaluation_authorized=False,
        auto_evaluation=False,
    )
    c.write(raw / "protocol.json", plan)
    return root, raw, plan


def state(raw, counts):
    c.write(raw / "budget/state.json", dict(counts=counts, at="synthetic"), immutable=False)


def rewritten(value, kind, **changed):
    fields = {
        key: item for key, item in value.items() if key not in ("kind", "id", "schema_version")
    }
    fields.update(changed)
    return p.record(kind, **fields)


def seed_report(raw, plan, original_seed, **changed):
    seed = original_seed
    key = f"B_negative_{seed}"
    checkpoint = raw / "jobs" / key / "updates/0240.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(f"synthetic checkpoint {seed}".encode())
    binding = p.record(
        "direction_calibration_negative_branch_binding",
        plan_id=plan["id"],
        job_key=key,
        seed=seed,
        reflection_id=f"reflection_{seed}",
        prefix_checkpoint_sha256=f"prefix_{seed}",
        distribution_sha256=f"distribution_{seed}",
    )
    fields = dict(
        complete=True,
        plan_id=plan["id"],
        job_key=key,
        seed=seed,
        condition="negative",
        pool="B",
        start=200,
        stop=240,
        completed_updates=240,
        physical_optimizer_updates=40,
        effective_optimizer_updates=240,
        full_original_epochs=1,
        shared_prefix_updates_reused=200,
        material_admission_id=plan["materials_admission"]["id"],
        branch_binding_id=binding["id"],
        prefix_binding=binding,
        original_prefix_sha256=f"prefix_{seed}",
        distribution_sha256=f"distribution_{seed}",
        generation_sessions=0,
        scoring_sessions=0,
        new_positive_or_static_updates=0,
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=p.sha(checkpoint),
        snapshot_id=f"snapshot_{seed}",
        RNG_binding=dict(id=f"rng_{seed}"),
        rng_complete=True,
        physical_job_totals=dict(
            sequence_tokens=17811694,
            target_tokens=982088,
            rows_completed=3529,
            packages_completed=3529,
        ),
    )
    fields.update(changed)
    result = p.record("direction_calibration_training_report", **fields)
    c.write(raw / "jobs" / key / "report.json", result)
    return result


def completed_seed_files(raw, plan, changed=None):
    for seed in (11, 29, 47):
        seed_report(raw, plan, seed, **((changed or {}) if seed == 29 else {}))
    state(
        raw,
        dict(
            optimizer=120,
            worker_start=3,
            **{f"optimizer:B_negative_{seed}": 40 for seed in (11, 29, 47)},
            **{f"worker_start:B_negative_{seed}": 1 for seed in (11, 29, 47)},
        ),
    )


def test_protocol_accepts_training_only_when_panel_is_not_ready(tmp_path, monkeypatch):
    root, _, plan = setup(tmp_path, monkeypatch)
    assert c.read_protocol(root) == plan


def test_changed_source_fails_before_worker_identity_or_GPU(tmp_path, monkeypatch):
    root, raw, _ = setup(tmp_path, monkeypatch)
    (root / "synthetic_source.py").write_text("frozen = False\n")
    monkeypatch.setattr(r.worker, "run", lambda *a, **kw: pytest.fail("GPU worker called"))
    assert r.run_worker(root, 11, 1, 32768) == 1
    result = p.read_json(raw / "results/B_negative_11/0001.json")
    assert "frozen_source" in result["error"]
    assert not result["resource_retry_allowed"]
    assert not (raw / "worker_identities").exists()


@pytest.mark.parametrize(
    "changed",
    [
        dict(jobs=[dict(key="B_negative_11", seed=11)]),
        dict(condition="positive"),
        dict(start=199),
        dict(stop=241),
        dict(new_positive_or_static_updates=1),
        dict(auto_evaluation=True),
        dict(panel_status="READY"),
    ],
)
def test_protocol_rejects_training_scope_expansion(tmp_path, monkeypatch, changed):
    root, raw, plan = setup(tmp_path, monkeypatch)
    c.write(raw / "protocol.json", rewritten(plan, r.PROTOCOL, **changed), immutable=False)
    with pytest.raises(ValueError, match="negative_training"):
        c.read_protocol(root)


def test_new_input_binding_is_checked_for_byte_changes(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(r.stage1, "RAW", tmp_path)
    source = tmp_path / "reuse_admission.json"
    source.write_bytes(b"original synthetic metadata")
    reference = r.input_ref(source)
    bound = rewritten(plan, r.PROTOCOL, registration_inputs=dict(admission=reference))
    c.write(raw / "protocol.json", bound, immutable=False)
    assert c.read_protocol(root) == bound
    source.write_bytes(b"changed synthetic metadata")
    with pytest.raises(ValueError, match="frozen_registration_input"):
        c.read_protocol(root)


@pytest.mark.parametrize(
    "kind", ["population", "generate_call", "score_case", "reliability_response", "unknown"]
)
def test_evaluation_and_other_unregistered_work_have_zero_budget(tmp_path, monkeypatch, kind):
    _, raw, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        c.reserve(kind, "B_negative_11", 1, 201)
    assert not (raw / "budget/state.json").exists()


@pytest.mark.parametrize("kind,unit", [("optimizer", 201), ("worker_start", 0)])
def test_duplicate_reservation_is_not_repeated_or_charged_again(
    tmp_path, monkeypatch, kind, unit
):
    _, raw, _ = setup(tmp_path, monkeypatch)
    key = "B_negative_29"
    if kind == "optimizer":
        c.reserve("worker_start", key, 1, 0)
    c.reserve(kind, key, 1, unit)
    with pytest.raises(ValueError):
        c.reserve(kind, key, 1, unit)
    assert p.read_json(raw / "budget/state.json")["counts"][kind] == 1


@pytest.mark.parametrize("kind,unit", [("optimizer", 201), ("worker_start", 0)])
@pytest.mark.parametrize("key", ["B_negative_99", "B_static_11", "B_delayed_c_11"])
def test_only_registered_negative_jobs_can_reserve(tmp_path, monkeypatch, kind, unit, key):
    _, raw, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        c.reserve(kind, key, 1, unit)
    assert not (raw / "budget/state.json").exists()


@pytest.mark.parametrize("attempt", [0, 9])
def test_out_of_range_attempt_rejected_before_work(tmp_path, monkeypatch, attempt):
    _, raw, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        c.reserve("worker_start", "B_negative_11", attempt, 0)
    assert not (raw / "budget/state.json").exists()


@pytest.mark.parametrize("unit", [0, 200, 241])
def test_only_updates_201_through_240_allowed(tmp_path, monkeypatch, unit):
    _, raw, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        c.reserve("optimizer", "B_negative_11", 1, unit)
    assert not (raw / "budget/state.json").exists()


def test_global_and_per_seed_optimizer_caps(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    key = "B_negative_11"
    c.reserve("worker_start", key, 8, 0)
    state(raw, {"optimizer": 143, "optimizer:" + key: 47})
    c.reserve("optimizer", key, 8, 240)
    counts = p.read_json(raw / "budget/state.json")["counts"]
    assert counts["optimizer"] == 144
    assert counts["optimizer:" + key] == 48
    with pytest.raises(ValueError):
        c.reserve("optimizer", "B_negative_29", 8, 240)
    state(raw, {"optimizer": 48, "optimizer:" + key: 48})
    with pytest.raises(ValueError):
        c.reserve("optimizer", key, 8, 239)


def test_counter_written_before_intent_and_never_rolled_back(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    c.reserve("worker_start", "B_negative_47", 1, 0)
    c.reserve("worker_start", "B_negative_47", 2, 0)
    original = c.write

    def interrupted(path, value, immutable=True):
        if "intents" in Path(path).parts:
            raise OSError("synthetic interruption after budget counter")
        return original(path, value, immutable)

    monkeypatch.setattr(c, "write", interrupted)
    with pytest.raises(OSError, match="interruption"):
        c.reserve("optimizer", "B_negative_47", 1, 201)
    assert p.read_json(raw / "budget/state.json")["counts"]["optimizer"] == 1
    monkeypatch.setattr(c, "write", original)
    c.reserve("optimizer", "B_negative_47", 2, 201)
    assert p.read_json(raw / "budget/state.json")["counts"]["optimizer"] == 2


def test_worker_start_total_is_finite(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    state(raw, {"worker_start": 23, "worker_start:B_negative_47": 7})
    c.reserve("worker_start", "B_negative_47", 8, 0)
    with pytest.raises(ValueError):
        c.reserve("worker_start", "B_negative_11", 8, 0)


@pytest.mark.parametrize(
    "exception,code",
    [
        (MemoryError("host"), 42),
        (c.torch.OutOfMemoryError("GPU"), 42),
        (c.CapacityWait("headroom"), 43),
        (ValueError("numeric"), 1),
    ],
)
def test_only_resource_worker_failures_are_retriable(tmp_path, monkeypatch, exception, code):
    root, raw, plan = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c, "read_protocol", lambda _: plan)
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999, command=["synthetic"]))
    c.reserve("worker_start", "B_negative_29", 1, 0)

    def failed_worker(*args, **kwargs):
        raise exception

    monkeypatch.setattr(r.worker, "run", failed_worker)
    assert r.run_worker(root, 29, 1, 32768) == code
    value = p.read_json(raw / "results/B_negative_29/0001.json")
    assert value["returncode"] == code and "finished_at" in value
    if code == 1:
        assert not value["resource_retry_allowed"]


def test_finish_requires_all_three_seeds(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    seed_report(raw, plan, 11)
    seed_report(raw, plan, 29)
    monkeypatch.setattr(r, "publish", lambda *a: pytest.fail("published partial completion"))
    assert not r.finish(root, plan)
    assert not (raw / "report.json").exists()
    assert not (raw / "complete.json").exists()


def test_finish_confirms_training_only_without_claiming_value(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    monkeypatch.setattr(r, "publish", lambda *a: True)
    assert r.finish(root, plan)
    complete = p.checked(p.read_json(raw / "complete.json"), r.COMPLETED)
    assert complete["protocol_id"] == plan["id"]
    assert [row["seed"] for row in complete["seeds"]] == [11, 29, 47]
    assert complete["committed_optimizer_updates"] == 120
    assert complete["panel_status"] == "NOT_READY" and not complete["auto_evaluation"]
    assert complete["no_training_value_conclusion_without_new_evaluation"]
    assert complete["new_generation_calls"] == complete["new_scoring_cases"] == 0


@pytest.mark.parametrize(
    "changed",
    [
        dict(seed=11),
        dict(job_key="B_negative_11"),
        dict(plan_id="different"),
        dict(condition="positive"),
        dict(physical_optimizer_updates=39),
        dict(material_admission_id="different"),
        dict(generation_sessions=1),
        dict(distribution_sha256="different"),
        dict(original_prefix_sha256="different"),
        dict(branch_binding_id="different"),
    ],
)
def test_finish_rejects_mismatched_seed_or_material_report(tmp_path, monkeypatch, changed):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan, changed)
    monkeypatch.setattr(r, "publish", lambda *a: pytest.fail("published mismatched result"))
    with pytest.raises(ValueError, match="negative_training"):
        r.finish(root, plan)
    assert not (raw / "complete.json").exists()


def test_finish_rejects_checkpoint_bytes_changed_after_report(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    (raw / "jobs/B_negative_47/updates/0240.pt").write_bytes(b"wrong saved model")
    monkeypatch.setattr(r, "publish", lambda *a: pytest.fail("published changed endpoint"))
    with pytest.raises(ValueError, match="negative_training"):
        r.finish(root, plan)


def test_publication_retry_preserves_completion_without_retraining(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    seen = []

    def publish(_, report):
        seen.append(report["id"])
        return len(seen) == 2

    monkeypatch.setattr(r, "publish", publish)
    monkeypatch.setattr(r, "reserve", lambda *a: pytest.fail("reserved work during publication"))
    monkeypatch.setattr(r.worker, "run", lambda *a: pytest.fail("retrained for publication"))
    assert not r.finish(root, plan)
    assert (raw / "complete.json").exists()
    assert r.finish(root, plan)
    assert len(set(seen)) == 1


def test_existing_aggregate_cannot_hide_partial_or_wrong_seed_summary(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    monkeypatch.setattr(r, "publish", lambda *a: False)
    assert not r.finish(root, plan)
    report = p.read_json(raw / "report.json")
    changed = rewritten(report, r.COMPLETED, seeds=report["seeds"][:2])
    c.write(raw / "report.json", changed, immutable=False)
    monkeypatch.setattr(r, "publish", lambda *a: pytest.fail("published partial aggregate"))
    with pytest.raises(ValueError, match="negative_training"):
        r.finish(root, plan)


class EndOneLoop(BaseException):
    pass


@pytest.mark.parametrize("code", [1, 42])
def test_numeric_failure_stops_but_resource_failure_waits(tmp_path, monkeypatch, code):
    root, raw, plan = setup(tmp_path, monkeypatch)
    key = "B_negative_11"
    row = dict(key=key, seed=11, attempt=2, identity=dict(pid=101))
    status = dict(attempt=2, failures=0, not_before=0, stopped=None)
    c.write(raw / "control/state.json", dict(jobs={key: status}, active={key: row}))
    c.write(raw / "results" / key / "0002.json", dict(returncode=code, error="synthetic"))
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999))
    monkeypatch.setattr(r.identity, "same_process", lambda _: False)
    monkeypatch.setattr(r, "finish", lambda *a: False)
    monkeypatch.setattr(r.old, "host_memory", lambda: dict(MemAvailable_bytes=0))
    monkeypatch.setattr(r.time, "time", lambda: 1000)
    monkeypatch.setattr(r, "spawn", lambda *a, **kw: pytest.fail("spawn without capacity"))

    def stop(_):
        raise EndOneLoop()

    monkeypatch.setattr(r.time, "sleep", stop)
    if code == 1:
        assert r.coordinate(root) == 1
    else:
        with pytest.raises(EndOneLoop):
            r.coordinate(root)
    saved = p.read_json(raw / "control/state.json")
    assert not saved["active"]
    if code == 1:
        assert saved["jobs"][key]["stopped"]["returncode"] == 1
    else:
        assert saved["jobs"][key] == dict(attempt=2, failures=1, not_before=1120, stopped=None)
