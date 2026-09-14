"""Three bounded publisher stubs; no real training, sealing, copying or Git."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import parallel_lineage
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

_SPEC = importlib.util.spec_from_file_location(
    "parallel_publication_test_subject",
    Path(__file__).resolve().parents[1] / "scripts/finalize_fixed_kernel_parallel_tail_20260914.py",
)
publisher = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(publisher)


def test_source_capture_covers_new_operator_and_imported_helpers(tmp_path):
    committed = {}
    for index, name in enumerate(publisher.SOURCES):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        committed[name] = ("synthetic source " + str(index)).encode()
        path.write_bytes(committed[name])

    def runner(_root, *args, **_kwargs):
        if args == ("rev-parse", "HEAD"):
            return SimpleNamespace(stdout=b"synthetic_commit\n")
        assert args[0] == "show"
        return SimpleNamespace(stdout=committed[args[1].split(":", 1)[1]])

    result = publisher.capture_sources(tmp_path, p, runner)
    assert [item["path"] for item in result["sources"]] == list(publisher.SOURCES)
    assert publisher.SCRIPT in publisher.SOURCES
    (tmp_path / publisher.SOURCES[-1]).write_bytes(b"different helper")
    with pytest.raises(ValueError, match="helpers_committed"):
        publisher.capture_sources(tmp_path, p, runner)


def test_publisher_preserves_true_old_and_tail_configurations(monkeypatch):
    monkeypatch.setattr(parallel_lineage, "_base_training_config", lambda: {"id": "base_config"})
    monkeypatch.setattr(parallel_lineage, "_tail_training_config", lambda: {"id": "tail_config"})
    namespace = SimpleNamespace(
        validate_binding=parallel_lineage.validate_binding, SURFACE_MANIFEST_ID="surface"
    )
    frozen = {
        "study_freeze_id": "study",
        "kernel_id": "kernel",
        "training_configuration": {"id": "base_config"},
    }
    budget = {
        "packages_all_epochs": 10,
        "rows_all_epochs": 20,
        "target_tokens_all_epochs": 30,
        "sequence_tokens_all_epochs": 40,
    }
    cache = {
        "id": "cache",
        "material_verification_id": "verification",
        "pool_budgets": {"A": budget, "B": budget},
        "source_material_budgets": {"A": budget, "B": budget},
    }
    for key, config in (
        (parallel_lineage.TAIL, "tail_config"),
        (("A", "plus", 11), "base_config"),
        (("B", "minus", 47), "base_config"),
    ):
        fields = dict(
            pool=key[0],
            arm=key[1],
            seed=key[2],
            study_freeze_id="study",
            surface_manifest_id="surface",
            kernel_id="kernel",
            training_configuration_id=config,
            actual_complete=True,
            status="COMPLETE_FINAL_CHECKPOINT",
            trajectory_cache_id="cache",
            material_verification_id="verification",
            actual_budget=budget,
            source_material_budget=budget,
            optimizer_updates=400,
            epochs_completed=10,
            final_adapter_restored_identity_verified=True,
            adapter_directory="historical_original_directory",
        )
        report = p.record("training_report", **fields)
        original = p.encode(report)
        assert publisher.validate_training_report(report, key, frozen, cache, namespace) is report
        assert p.encode(report) == original
        bad = p.record(
            "training_report", **{**fields, "training_configuration_id": "foreign_config"}
        )
        with pytest.raises(ValueError, match="exact_actual_configuration"):
            publisher.validate_training_report(bad, key, frozen, cache, namespace)


def test_closure_requires_only_new_results_and_original_archive_and_stops_failure(tmp_path):
    namespace = SimpleNamespace(
        OUTPUT="new_execution", MATERIALS="original_materials", MATERIALS_ROOT=tmp_path / "parent"
    )
    expected = (
        tmp_path / namespace.OUTPUT / "report.json",
        tmp_path / namespace.OUTPUT / "manifest.json",
        namespace.MATERIALS_ROOT
        / "original_materials_publication/materials/publication_manifest.json",
    )
    with pytest.raises(ValueError, match="not_ready"):
        publisher.wait_for_closure(tmp_path, namespace, wait=False)
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic closure existence only")
    assert publisher.wait_for_closure(tmp_path, namespace, wait=False) == expected
    assert publisher.PRODUCER_MANIFEST_LIMIT == 128 * 1024 * 1024
    (tmp_path / namespace.OUTPUT / "parallel_handoff_failure.json").write_bytes(
        b"synthetic failure"
    )
    with pytest.raises(ValueError, match="failure_not_relabelled"):
        publisher.wait_for_closure(tmp_path, namespace, wait=False)


def retirement_fixture(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    namespace = SimpleNamespace(
        OUTPUT="new",
        PARENT_ROOT=parent,
        **{
            name: getattr(p, name)
            for name in ("record", "checked", "read_json", "encode", "write_once", "now")
        },
    )
    jobs = [
        dict(kind="train", pool="A", arm=arm, seed=seed)
        for seed in p.SEEDS
        for arm in p.ARMS
        if (arm, seed) != ("minus", 47)
    ]
    pause = p.record(
        "parallel_tail_handoff_pause",
        active_training_workers_signaled=False,
        paused_processes=[
            {"pid": 3169168, "cmdline_sha256": "controller"},
            {"pid": 3171733, "cmdline_sha256": "publisher"},
        ],
    )
    p.write_once(parent / "pause.json", pause)
    frozen = p.record(
        "execution_freeze",
        scheduler_handoff=publisher.descriptor(parent, "pause.json"),
        scheduler_handoff_id=pause["id"],
        parent_execution_freeze_id="old_execution",
        parent_execution_output="old",
        parent_controller=dict(pid=3169168, start_ticks=101, cmdline_sha256="controller"),
        parent_workers=[
            dict(job=job, process={"pid": 10000 + index}) for index, job in enumerate(jobs)
        ],
    )
    p.write_once(tmp_path / "new/preparation/execution_freeze.json", frozen)
    marker = str(
        parent
        / "trusted_data_synthesis/scripts/finalize_fixed_kernel_trajectory_execution_20260914.py"
    )
    states = {
        3169168: dict(
            pid=3169168, state="T", start_ticks=101, cmdline_sha256="controller", argv=["python"]
        ),
        3171733: dict(
            pid=3171733,
            state="T",
            start_ticks=202,
            cmdline_sha256="publisher",
            argv=["python", marker],
        ),
    }

    def observe(pid):
        return dict(states[pid])

    captured = publisher.capture_parent_coordinators(tmp_path, namespace, observe=observe)
    imported = []
    for job in jobs:
        key = "_".join(str(job[name]) for name in ("pool", "arm", "seed"))
        report = p.record(
            "training_report",
            **{name: job[name] for name in ("pool", "arm", "seed")},
            actual_complete=True,
            status="COMPLETE_FINAL_CHECKPOINT",
            optimizer_updates=400,
            epochs_completed=10,
        )
        directory = tmp_path / ("new/training/" + key)
        p.write_once(directory / "report.json", report)
        imported.append(
            p.record(
                "completed_parent_training_import",
                job=job,
                source_root=str(parent),
                source_execution_freeze_id="old_execution",
                report_ID_or_historical_paths_rewritten=False,
                source_worker_exit_observation={"state": "Z"},
                training_report_id=report["id"],
                members=[publisher.descriptor(directory, "report.json")],
            )
        )
    return namespace, frozen, captured, imported, states, observe


def test_retirement_signals_only_two_exact_old_coordinators_after_eight_complete_imports(tmp_path):
    import signal

    namespace, frozen, captured, imported, states, observe = retirement_fixture(tmp_path)
    p.write_once(
        tmp_path / "new/completed_parent_imports.json",
        p.record(
            "completed_parent_training_imports",
            execution_freeze_id=frozen["id"],
            completed_parent_runs=8,
            imports=imported,
            original_report_IDs_preserved=True,
        ),
    )
    calls = []

    def send(pid, signum):
        calls.append((pid, signum))
        if signum == signal.SIGCONT:
            states[pid] = dict(
                pid=pid, state="gone", start_ticks=None, cmdline_sha256=None, argv=[]
            )

    assert publisher.maybe_retire_parent_coordinators(
        tmp_path, namespace, captured, observe=observe, send=send, sleeper=lambda _: None
    )
    assert calls == [
        (3169168, signal.SIGTERM),
        (3169168, signal.SIGCONT),
        (3171733, signal.SIGTERM),
        (3171733, signal.SIGCONT),
    ]
    result = p.read_json(tmp_path / "new/parent_coordinators_retired.json")
    assert result["status"] == "RETIRED_OR_ALREADY_EXITED"
    assert result["training_workers_or_new_processes_signaled"] is False
    assert not (namespace.PARENT_ROOT / "old_workflow/terminal.json").exists()


def test_retirement_without_eight_complete_imports_never_signals(tmp_path):
    namespace, frozen, captured, imported, _states, observe = retirement_fixture(tmp_path)
    calls = []

    def send(pid, signum):
        calls.append((pid, signum))

    assert not publisher.maybe_retire_parent_coordinators(
        tmp_path, namespace, captured, observe=observe, send=send, sleeper=lambda _: None
    )
    p.write_once(
        tmp_path / "new/completed_parent_imports.json",
        p.record(
            "completed_parent_training_imports",
            execution_freeze_id=frozen["id"],
            completed_parent_runs=7,
            imports=imported[:7],
            original_report_IDs_preserved=True,
        ),
    )
    with pytest.raises(ValueError, match="all_eight_actual_imports_required"):
        publisher.maybe_retire_parent_coordinators(
            tmp_path, namespace, captured, observe=observe, send=send, sleeper=lambda _: None
        )
    assert calls == []
