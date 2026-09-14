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
