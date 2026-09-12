"""Pure-mock lifecycle controls: no API, native production, tokenizer or GPU use."""

import hashlib
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import stage
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return raw


def mock_run(tmp_path, monkeypatch, *, defined=40, fail=None):
    output = tmp_path / stage.OUTPUT
    descriptor = {"directory": stage.PARENT, "manifest_id": stage.PARENT_MANIFEST}

    class Parent:
        def __init__(self, *args, **kwargs):
            pass

        def descriptor(self):
            return descriptor

        def verify_all(self):
            return stage.PARENT_MANIFEST

    frozen = record(
        "catalog_bridge_freeze",
        rule=stage.policy(stage.panels.policy()),
        code=[],
        source_files=[],
        tokenizer_assets=[],
        prior_zero_model_evidence=[],
        parent=descriptor,
        panel_source_metadata={"id": "synthetic-metadata"},
        git_commit="synthetic-code-only",
    )
    put(output / "stage_freeze.json", frozen)
    acquisition = record("bounded_source_acquisition", attempts=[], sources=[], request_count=0)
    acquired_path = output / "inputs/source_acquisition.json"
    raw = put(acquired_path, acquisition)
    inputs = record(
        "catalog_bridge_input_freeze",
        stage_freeze_id=frozen["id"],
        source_acquisition_id=acquisition["id"],
        members=[
            {
                "path": str(acquired_path.relative_to(tmp_path)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        ],
    )
    put(output / "input_bytes_freeze.json", inputs)
    state = {"guard": False, "increments": 0, "panels": 0, "controls": 0}
    panel_started = threading.Event()

    @contextmanager
    def guard():
        assert not state["guard"]
        state["guard"] = True
        try:
            yield {"forbidden": {"mock_forbidden": 0}, "allowed_rewrite_socket_calls": {}}
        finally:
            state["guard"] = False

    def panel_run(
        root, panel_output, work, *, expected_policy_id, expected_source_metadata_id, freeze_id
    ):
        assert state["guard"]
        assert root == tmp_path
        assert panel_output == output / "panels"
        assert work == tmp_path / stage.WORK / "panels"
        assert expected_policy_id == stage.panels.policy()["id"]
        assert expected_source_metadata_id == "synthetic-metadata"
        assert freeze_id == frozen["id"]
        state["panels"] += 1
        panel_started.set()
        if fail == "panels":
            raise RuntimeError("synthetic-panel-failure")
        result = {
            "status": "PARTIAL_REAL_PANELS_SUPPLY_SHORTFALL",
            "unique_task_count": 17,
            "quota_complete": False,
        }
        put(panel_output / "report.json", result)
        return result

    def increment(root, pin, key):
        assert state["guard"] and root == tmp_path and pin == frozen
        assert key == "synthetic-secret"
        assert panel_started.wait(timeout=3), "panel future was not started independently"
        state["increments"] += 1
        if fail == "increment":
            raise RuntimeError("synthetic-secret must be redacted")
        put(
            output / "incremental/rewrite_budget_ledger.json",
            {
                "cumulative_conservative_debit": 211838,
                "remaining_registered_global_allowance": 1000000000 - 211838,
            },
        )
        return {"tasks": 14}

    def compose(root, path, parents, freeze_id):
        assert root == tmp_path and path == output and freeze_id == frozen["id"]
        tasks = [
            {"task_id": family + str(i), "family": family}
            for family, count in [
                ("stock_rollforward", 40),
                ("annual_flow", 40),
                ("company_defined_metric", defined),
                ("control", 80),
            ]
            for i in range(count)
        ]
        full = record("composed_task_catalog", tasks=tasks)
        public = record("public_task_catalog", tasks=[], source_catalog_id=full["id"])
        put(output / "catalog.json", full)
        put(output / "public_catalog.json", public)
        return full, public

    def controls(root, full, public):
        assert state["guard"] and root == tmp_path
        state["controls"] += 1
        return {
            "registered": 7,
            "passed": 7,
            "materialization": {
                "status": "PASS_SCRIPTED_REPRESENTATION_ONLY",
                "checks": [],
                "failures": [],
                "policy": {},
                "target_tokens": 123,
            },
        }

    monkeypatch.setattr(stage, "parent", lambda root: Parent())
    monkeypatch.setattr(stage, "Parent", Parent)
    monkeypatch.setattr(stage, "credential", lambda root: "synthetic-secret")
    monkeypatch.setattr(stage, "rewrite_guard", guard)
    monkeypatch.setattr(stage.panels, "run", panel_run)
    monkeypatch.setattr(stage, "build_increment", increment)
    monkeypatch.setattr(stage, "compose", compose)
    monkeypatch.setattr(stage, "run_controls", controls)
    return output, state, acquired_path


@pytest.mark.parametrize("defined,ceiling", [(40, 200), (35, 175)])
def test_run_parallel_guard_signatures_report_keys_and_no_quota_relaxation(
    tmp_path, monkeypatch, defined, ceiling
):
    output, state, _ = mock_run(tmp_path, monkeypatch, defined=defined)
    result = stage.run(tmp_path)
    assert result["balanced_reference_supply_ceiling"] == ceiling
    assert result["evaluation_tasks"] == 17
    assert result["known_cumulative_token_debit"] == 211838
    assert state == {"guard": False, "increments": 1, "panels": 1, "controls": 1}
    report = json.loads((output / "report.json").read_bytes())
    assert not report["evaluation_panel_quota_complete"]
    assert not report["evaluation_worker_primary_qualification_established"]
    assert not report["formal_collection_started"]
    assert not report["common_AB_material_ready_population_established"]
    assert report["Teacher_sessions"] == report["Student_runs"] == report["GPU_runs"] == 0
    assert (report["prospective_population_design"] is None) == (ceiling < 180)
    assert (output / "run_completed.json").exists()
    assert (output / "manifest.json").exists()
    assert not (output / "run_failed.json").exists()
    with pytest.raises(ValueError, match="one_production_run"):
        stage.run(tmp_path)
    assert state["increments"] == state["panels"] == 1


@pytest.mark.parametrize("failure", ["increment", "panels"])
def test_run_failure_closes_guard_seals_denominator_and_never_replays(
    tmp_path, monkeypatch, failure
):
    output, state, _ = mock_run(tmp_path, monkeypatch, fail=failure)
    with pytest.raises(RuntimeError):
        stage.run(tmp_path)
    assert not state["guard"]
    assert state["increments"] == state["panels"] == 1
    assert not (output / "run_completed.json").exists()
    failed = json.loads((output / "run_failed.json").read_bytes())
    assert failed["no_automatic_replay"]
    assert "synthetic-secret" not in json.dumps(failed)
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert manifest["status"] == "failed" and manifest["original_budget_not_reset"]
    with pytest.raises(ValueError, match="one_production_run"):
        stage.run(tmp_path)
    assert state["increments"] == state["panels"] == 1


def test_input_bytes_must_match_acquisition_freeze_before_any_run_marker(tmp_path, monkeypatch):
    output, state, path = mock_run(tmp_path, monkeypatch)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="final_input_bytes"):
        stage.run(tmp_path)
    assert state == {"guard": False, "increments": 0, "panels": 0, "controls": 0}
    assert not (output / "run_started.json").exists()


def test_input_record_cannot_point_to_a_different_acquisition_before_run(tmp_path, monkeypatch):
    output, state, path = mock_run(tmp_path, monkeypatch)
    altered = record("bounded_source_acquisition", attempts=[], sources=[], request_count=1)
    put(path, altered)
    with pytest.raises(ValueError, match="exact_input_freeze_join"):
        stage.run(tmp_path)
    assert state == {"guard": False, "increments": 0, "panels": 0, "controls": 0}
    assert not (output / "run_started.json").exists()


@pytest.mark.parametrize(
    "materialization",
    [
        {"status": "TOKENIZER_UNAVAILABLE", "failures": []},
        {"status": "REPRESENTATION_FAILED", "failures": [{"reason": "synthetic"}]},
        {"status": "PASS_SCRIPTED_REPRESENTATION_ONLY", "failures": [{"reason": "synthetic"}]},
    ],
)
def test_behavior_PASS_cannot_substitute_for_materialization_PASS(
    tmp_path, monkeypatch, materialization
):
    monkeypatch.setattr(stage, "PublicCatalog", lambda *args: object())
    monkeypatch.setattr(stage, "OfflineCatalog", lambda *args: object())
    monkeypatch.setattr(
        stage.controls,
        "run_scripted_controls",
        lambda *args, **kwargs: {"status": "PASS", "materialization": materialization},
    )
    with pytest.raises(ValueError):
        stage.run_controls(tmp_path, {"id": "mock-full", "tasks": []}, {"id": "mock-public"})


def mock_freeze(tmp_path, monkeypatch, *, semantic_requests=0):
    config = tmp_path / "synthetic_configuration.json"
    config_raw = put(config, {"synthetic": "fixed-existing-configuration"})
    config_sha = hashlib.sha256(config_raw).hexdigest()
    history = tmp_path / "synthetic_history.json"
    history_raw = put(history, {"synthetic": "old-confirmation-authority"})
    descriptor = {"directory": stage.PARENT, "manifest_id": stage.PARENT_MANIFEST}
    original = SimpleNamespace(
        manifest={"id": stage.PARENT_MANIFEST},
        members={"rewrite_budget_ledger.json": {"sha256": "0" * 64}},
        verify_all=lambda: stage.PARENT_MANIFEST,
        descriptor=lambda: descriptor,
        read=lambda name: (
            {"original_sources": []}
            if name == "stage_freeze.json"
            else {"conservative_charged_tokens": 211338, "unsettled_or_unknown_count": 0}
        ),
    )
    reports = {
        "trusted_data_synthesis/artifacts/qa_vnext_task_build/task_factory_20260911/report.json": {
            "task_generation_LLM_calls": 0,
            "actual_Teacher_sessions": 0,
            "actual_Student_runs": 0,
        },
        "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/"
        "source_inventory_20260911/source_intake/report.json": {
            "semantic_model_requests": 0,
            "new_Teacher_sessions": 0,
            "Student_runs": 0,
        },
        "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/"
        "source_inventory_20260911/source_census/report.json": {
            "new_semantic_API_requests": semantic_requests,
            "new_Teacher_sessions": 0,
            "new_Student_runs": 0,
        },
    }
    for relative, report in reports.items():
        put(tmp_path / relative, report)
    metadata = {
        "id": "synthetic-metadata",
        "rows": [],
        "historical_confirmation_authority": {
            "path": history.name,
            "sha256": hashlib.sha256(history_raw).hexdigest(),
        },
    }
    monkeypatch.setattr(stage, "parent", lambda root: original)
    monkeypatch.setattr(stage, "credential", lambda root: "synthetic-secret")
    monkeypatch.setattr(stage.panels, "inspect_source_metadata", lambda root: metadata)
    monkeypatch.setattr(stage.assets, "TOKENIZER_MEMBERS", ())
    monkeypatch.setattr(stage.assets, "SOURCE_CONFIGURATION", config.name)
    monkeypatch.setattr(stage.assets, "SOURCE_CONFIGURATION_SHA256", config_sha)
    monkeypatch.setattr(stage, "CODE_EXTRA", [])
    monkeypatch.setattr(stage, "CODE_DIRS", [])
    monkeypatch.setattr(
        stage.subprocess, "check_output", lambda *args, **kwargs: "synthetic-head\n"
    )
    return config


def test_freeze_retains_Student_configuration_pin_for_later_checks(tmp_path, monkeypatch):
    config = mock_freeze(tmp_path, monkeypatch)
    stage.freeze(tmp_path)
    frozen = json.loads((tmp_path / stage.OUTPUT / "stage_freeze.json").read_bytes())
    assert config.name in {row["path"] for row in frozen["source_files"]}
    stage.check_freeze(tmp_path, frozen)
    config.write_bytes(config.read_bytes() + b" ")
    with pytest.raises(ValueError, match="frozen_code_or_source_bytes"):
        stage.check_freeze(tmp_path, frozen)


def test_semantic_API_debit_cannot_be_misreported_as_zero_model_preparation(tmp_path, monkeypatch):
    mock_freeze(tmp_path, monkeypatch, semantic_requests=1)
    with pytest.raises(ValueError, match="earlier_same_study_zero_model"):
        stage.freeze(tmp_path)
    assert not (tmp_path / stage.OUTPUT / "stage_freeze.json").exists()
