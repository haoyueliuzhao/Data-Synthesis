"""New driver boundaries only; all wallets/models/reports are synthetic CPU controls."""

import sqlite3
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import stage, worker
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import training_runtime


def wallet(root, finished=1, fatal=False):
    path = root / p.LEDGER
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)")
        db.execute("CREATE TABLE collection_sessions(state TEXT)")
        db.executemany(
            "INSERT INTO collection_sessions VALUES(?)",
            [("finished",)] * finished + [("registered",)] * (24640 - finished),
        )
        db.execute("CREATE TABLE prior_debits(tokens INTEGER)")
        db.execute("INSERT INTO prior_debits VALUES(221538)")
        for name, debit in (
            ("reservations", 10819),
            ("teacher_reservations", 123456),
            ("eval_reservations", 651959),
        ):
            db.execute(f"CREATE TABLE {name}(state TEXT,charged_tokens INTEGER)")
            db.execute(f"INSERT INTO {name} VALUES('usage_unknown',?)", (debit,))
        if fatal:
            db.execute("INSERT INTO metadata VALUES('study_fatal','synthetic stop')")
    return path


def frozen_fixture():
    return {
        "id": "freeze:synthetic",
        "surface_parent": {"manifest_id": p.SURFACE_MANIFEST_ID},
        "materials_manifest_id": "materials:synthetic",
        "training_configuration": p.training_config(),
        "decoder_configuration": {"id": "decoder:synthetic"},
        "base_binding": {"id": "base:synthetic"},
        "tokenizer_binding": {"id": "tokenizer:synthetic"},
        "evaluation_registry": {"dev": [], "confirm": []},
        "actual_common_tasks": 180,
        "actual_material_budget": {
            "pool_budgets": {
                pool: {"target_tokens_all_epochs": 10, "sequence_tokens_all_epochs": 20}
                for pool in ("A", "B")
            }
        },
    }


def training_report(root, frozen, job, initial="same"):
    path = stage.training_path(root, job["pool"], job["arm"], job["seed"])
    path.mkdir(parents=True)
    (path / "final_adapter.safetensors").write_bytes(b"synthetic checkpoint bytes, not a model")
    adapter = {
        "path": "final_adapter.safetensors",
        "bytes": (path / "final_adapter.safetensors").stat().st_size,
        "sha256": p.sha(path / "final_adapter.safetensors"),
        "parameter_digest": "checkpoint:synthetic",
    }
    report = p.record(
        "training_report",
        status="COMPLETE_FINAL_CHECKPOINT",
        actual_complete=True,
        pool=job["pool"],
        arm=job["arm"],
        seed=job["seed"],
        checkpoint_id=adapter["parameter_digest"],
        final_adapter=adapter,
        adapter_directory=str(path.relative_to(root)),
        initial_adapter_digest=initial,
        schedule_id=f"schedule:{job['seed']}",
        target_tokens=10,
        sequence_tokens=20,
        optimizer_updates=360,
        **stage.binding(frozen),
    )
    p.write_once(path / "report.json", report)
    return report


def test_readonly_common_wallet_does_not_drop_unknown_or_reset_prior(tmp_path):
    path = wallet(tmp_path)
    before = path.read_bytes()
    result = stage.collection_status(tmp_path)
    assert result["status"] == "COLLECTION_RUNNING"
    assert result["shared_conservative_debit"] == 1007772
    assert result["teacher_request_states"] == {"usage_unknown": 1}
    assert path.read_bytes() == before
    assert not (tmp_path / p.OUTPUT).exists()


def test_fatal_waits_original_final_seal_not_new_collection(tmp_path):
    wallet(tmp_path, fatal=True)
    result = stage.collection_status(tmp_path)
    assert result["status"] == "COLLECTION_STOPPING"
    assert not result["collection_restarted"]


@pytest.mark.parametrize("finished", [1, 24640])
def test_finished_counter_alone_is_not_completion(tmp_path, finished):
    wallet(tmp_path, finished=finished)
    assert stage.collection_status(tmp_path)["status"] == "COLLECTION_RUNNING"


@pytest.mark.parametrize(
    "finished,fatal,expected",
    [
        (24640, False, "COMPLETE_FIXED_COLLECTION"),
        (1, False, "STOP_INCOMPLETE_FIXED_COLLECTION"),
        (24640, True, "STOP_INCOMPLETE_FIXED_COLLECTION"),
    ],
)
def test_complete_report_registry_fatal_join(tmp_path, monkeypatch, finished, fatal, expected):
    wallet(tmp_path, finished, fatal)
    p.write_once(tmp_path / p.COLLECTION / "manifest.json", {})
    report = training_runtime.record(
        "fixed_collection_report",
        status="COMPLETE_FIXED_COLLECTION",
        collection_complete=True,
        registered_session_count=24640,
        finished_session_count=24640,
        recorded_session_count=24640,
    )

    class Parent:
        def __init__(self, *args):
            pass

        def read(self, name):
            return report

    monkeypatch.setattr(stage, "Parent", Parent)
    assert stage.collection_status(tmp_path)["status"] == expected


@pytest.mark.parametrize(
    "status", ["COLLECTION_RUNNING", "COLLECTION_STOPPING", "STOP_INCOMPLETE_FIXED_COLLECTION"]
)
def test_advance_never_materializes_or_loads_from_incomplete(tmp_path, monkeypatch, status):
    monkeypatch.setattr(stage, "collection_status", lambda root: {"status": status})
    monkeypatch.setattr(
        stage.surface_stage, "materialize", lambda *args: pytest.fail("no partial materializer")
    )
    monkeypatch.setattr(stage, "freeze", lambda *args: pytest.fail("no partial freeze"))
    assert stage.advance(tmp_path) == {"status": status}
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "phase,count", [("A_train", 9), ("A_dev", 9), ("B_train", 6), ("confirm", 12)]
)
def test_fixed_job_counts_and_order(phase, count):
    jobs = stage.jobs_for(phase, selected="plus")
    assert len(jobs) == count and len({stage.job_name(job) for job in jobs}) == count
    assert not any(job.get("split") == "dev" and job["pool"] == "B" for job in jobs)


@pytest.mark.parametrize("arm", ["alpha0", "second_best", "", None])
def test_no_B_or_confirmation_without_unique_positive_direction(arm):
    with pytest.raises(ValueError, match="unique_positive"):
        stage.jobs_for("B_train", selected=arm)


def test_evaluation_caps_are_1620_and_8640_not_extra_template():
    assert len(stage.jobs_for("A_dev")) * 180 == 1620
    assert len(stage.jobs_for("confirm", selected="minus")) * 720 == 8640
    assert p.execution_policy()["maximum_evaluation_sessions"] == 10260


def test_gpu_filter_never_takes_busy_or_small_GPU(monkeypatch):
    monkeypatch.setattr(
        stage.subprocess,
        "check_output",
        lambda *a, **k: "0, uuid0, 80000, 1\n2, uuid2, 76000, 0\n1, uuid1, 75000, 0\n",
    )
    assert stage.available_gpus() == [{"index": 2, "uuid": "uuid2", "free_memory_MiB": 76000}]


def test_public_generation_capsule_never_contains_material_body(tmp_path):
    frozen = frozen_fixture()
    frozen["private"] = "must-not-pass"
    job = stage.jobs_for("A_dev")[0]
    training_report(tmp_path, frozen, job)
    capsule = stage.public_generation_input(tmp_path, frozen, job)
    assert set(capsule) == {
        "model_identity",
        "base_binding",
        "tokenizer_binding",
        "decoder_configuration",
        "surface_directory",
        "surface_manifest_id",
        "split",
        "output_directory",
    }
    assert "private" not in p.encode(capsule).decode()
    assert capsule["model_identity"]["final_adapter"]["path"] == "final_adapter.safetensors"
    assert capsule["model_identity"]["adapter_directory"] == str(
        stage.training_path(tmp_path, "A", "alpha0", 11).relative_to(tmp_path)
    )


def test_public_worker_only_reads_capsule_and_uses_same_manifest_receipts(tmp_path, monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_basis_student import decoder, evaluation

    frozen = frozen_fixture()
    job = stage.jobs_for("A_dev")[0]
    training_report(tmp_path, frozen, job)
    capsule = stage.public_generation_input(tmp_path, frozen, job)
    path = tmp_path / p.OUTPUT / "jobs/A_dev/synthetic_job.json"
    p.write_once(
        path,
        p.record(
            "worker_job",
            job=job,
            gpu={"uuid": "synthetic"},
            launched_at="now",
            public_generation_input=capsule,
            **stage.binding(frozen),
        ),
    )
    original = p.read_json
    reads = []

    def read(value):
        reads.append(Path(value))
        assert Path(value) == path
        return original(value)

    monkeypatch.setattr(p, "read_json", read)
    output = tmp_path / capsule["output_directory"]
    sentinel = object()

    def load(root, receipts, *args):
        assert receipts == output / "decoder"
        return sentinel

    def generate(root, directory, **kwargs):
        assert directory == output and kwargs["decoder"] is sentinel
        return {"actual_complete": True}

    monkeypatch.setattr(decoder, "load_decoder", load)
    monkeypatch.setattr(evaluation, "generate", generate)
    assert worker.run(tmp_path, path)["actual_complete"] is True
    assert reads == [path]


def test_final_checkpoint_byte_mismatch_blocks_generation(tmp_path):
    frozen = frozen_fixture()
    job = stage.jobs_for("A_dev")[0]
    training_report(tmp_path, frozen, job)
    (stage.training_path(tmp_path, "A", "alpha0", 11) / "final_adapter.safetensors").write_bytes(
        b"changed"
    )
    with pytest.raises(ValueError, match="adapter_bytes"):
        stage.public_generation_input(tmp_path, frozen, job)


def test_paired_initialization_mismatch_blocks_dev(tmp_path):
    frozen = frozen_fixture()
    jobs = stage.jobs_for("A_train")
    for index, job in enumerate(jobs):
        training_report(tmp_path, frozen, job, initial="changed" if index == 1 else "same")
    with pytest.raises(ValueError, match="paired_seed_initialization"):
        stage.training_reports(tmp_path, jobs, frozen)


@pytest.mark.parametrize("selected", ["alpha0", "plus", "minus"])
def test_actual_phase_order_no_B_dev_and_no_runner_retry(tmp_path, monkeypatch, selected):
    from trusted_synthesis.experiments.finance_qa_vnext_basis_student import analysis

    frozen = frozen_fixture()
    phases = []

    class Parent:
        def __init__(self, *args):
            pass

        def verify_all(self):
            pass

        def read(self, name):
            return frozen

    monkeypatch.setattr(stage, "Parent", Parent)
    monkeypatch.setattr(stage, "verify_code", lambda value: None)
    monkeypatch.setattr(
        stage, "collection_status", lambda root: {"status": "COMPLETE_FIXED_COLLECTION"}
    )
    monkeypatch.setattr(stage, "run_jobs", lambda root, freeze, phase, **kw: phases.append(phase))
    monkeypatch.setattr(stage, "training_reports", lambda *a: [])
    monkeypatch.setattr(stage, "score_jobs", lambda *a: [])
    monkeypatch.setattr(
        analysis,
        "select_actual_direction",
        lambda *a, **k: {"id": "decision", "selected_arm": selected},
    )
    monkeypatch.setattr(analysis, "confirm_actual", lambda *a, **k: {"id": "confirmation"})
    monkeypatch.setattr(stage, "seal", lambda *a, **k: None)
    result = stage.run(tmp_path)
    assert phases == (
        ["A_train", "A_dev"] if selected == "alpha0" else ["A_train", "A_dev", "B_train", "confirm"]
    )
    assert result["actual_evaluation_sessions"] == (1620 if selected == "alpha0" else 10260)
    with pytest.raises(FileExistsError):
        stage.run(tmp_path)


def test_durable_follow_waits_stopping_parent_and_never_restarts(tmp_path, monkeypatch):
    states = iter(["COLLECTION_RUNNING", "COLLECTION_STOPPING", "STOP_INCOMPLETE_FIXED_COLLECTION"])
    monkeypatch.setattr(stage, "collection_status", lambda root: {"status": next(states)})
    monkeypatch.setattr(stage.subprocess, "check_output", lambda *a, **k: "synthetic-code")
    waits = []
    monkeypatch.setattr(stage.time, "sleep", waits.append)
    monkeypatch.setattr(
        stage, "advance", lambda root: {"status": "STOP_INCOMPLETE_FIXED_COLLECTION"}
    )
    monkeypatch.setattr(stage, "try_publish", lambda *a: {"status": "synthetic_no_publication"})
    assert stage.follow(tmp_path)["status"] == "STOP_INCOMPLETE_FIXED_COLLECTION"
    assert waits == [30, 30]
    runtime = tmp_path / "trusted_data_synthesis/artifacts/qa_vnext_basis_student/runtime_20260912"
    assert len(list((runtime / "observations").glob("*.json"))) == 3
    with pytest.raises(FileExistsError):
        stage.follow(tmp_path)


def test_protocol_rejects_overwrite_nan_and_symlink_parents(tmp_path):
    path = tmp_path / "evidence.json"
    p.write_once(path, {"value": 1})
    with pytest.raises(FileExistsError):
        p.write_once(path, {"value": 2})
    with pytest.raises(ValueError):
        p.record("bad", value=float("nan"))
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink_parent"):
        p.path_within(tmp_path, "alias/item.json")
