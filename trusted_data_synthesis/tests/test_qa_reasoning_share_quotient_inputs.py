"""Read the exact saved cohort only; no model, callback, QA replay or kernel execution."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_finite_comparison import inputs as old_inputs
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as pilot_reader
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import inputs, models

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("input loading must not requalify, replay QA or run an old candidate loader")

    with pytest.MonkeyPatch.context() as patch:
        for name in ("audit_records", "audit_session", "aggregate_pilot", "_output"):
            patch.setattr(pilot_reader, name, forbidden)
        patch.setattr(old_inputs, "load_inputs", forbidden)
        patch.setattr(old_inputs, "revalidate_six", forbidden)
        yield inputs.load_inputs(ROOT)


def test_exact_parent_and_six_outcomes_reuse_original_qualification(frozen: dict[str, Any]) -> None:
    assert len(frozen["parent_files"]) == 785
    assert sum(map(len, frozen["parent_files"].values())) == 8_312_321
    assert frozen["parent_manifest"]["manifest_id"] == models.PARENT_MANIFEST
    assert frozen["parent_manifest"]["artifact_root"] == models.PARENT_ROOT
    assert [item["label"] for item in frozen["sessions"]] == list(models.LABELS)
    assert [item["qualification"]["Y"] for item in frozen["sessions"]] == [0, 1, 1, 1, 1, 1]
    for item in frozen["sessions"]:
        original = json.loads(frozen["parent_files"]["online_reports/" + item["label"] + ".json"])
        assert item["qualification"] == original
        assert item["records"]["manifest"]["id"] == original["session_manifest_id"]
    assert frozen["sessions"][0]["qualification"]["qa_valid"] is None
    assert frozen["parent_freeze"]["new_qa_validation"] is False
    assert frozen["parent_freeze"]["new_adapter_audit"] is False


def test_all_original_interactions_remain_bound_without_becoming_new_samples(
    frozen: dict[str, Any],
) -> None:
    counts = [len(item["records"]["events"]) for item in frozen["sessions"]]
    assert counts == [12, 7, 12, 6, 9, 5]
    assert sum(counts) == 51
    events = [event for item in frozen["sessions"] for event in item["records"]["events"]]
    assert sum(event["receipt"]["admitted"] is False for event in events) == 18
    assert sum(event["execution"] is not None for event in events) == 14
    assert sum(event["claim"] is not None for event in events) == 14
    assert sum(event["final"] is not None for event in events) == 5
    assert all(isinstance(event["submission"]["raw_public_json"], str) for event in events)
    assert all(event["submission"]["host_repairs"] == [] for event in events)
    assert frozen["parent_freeze"]["copies_of_original_trajectories_are_new_samples"] is False


def test_new_parent_freeze_binds_all_785_members_and_condition_qualification_references(
    frozen: dict[str, Any],
) -> None:
    binding = frozen["parent_freeze"]
    assert binding["member_count"] == 785 and binding["member_bytes"] == 8_312_321
    assert {item["relative_path"] for item in binding["members"]} == set(frozen["parent_files"])
    assert binding["includes_parent_manifest_member"] is True
    assert binding["source_commit"] == models.PARENT_SOURCE_COMMIT
    assert binding["source_tree"] == models.PARENT_SOURCE_TREE
    for row in binding["members"]:
        original = frozen["parent_files"][row["relative_path"]]
        assert row["byte_count"] == len(original) and row["sha256"] == models.sha(original)
    assert len(binding["condition_references"]) == 9
    for item in binding["cohort"]:
        for key in ("declaration", "qualification", "session_manifest", "initial_state", "stop"):
            reference = item[key]
            assert reference["sha256"] == models.sha(
                frozen["parent_files"][reference["relative_path"]]
            )


def test_only_five_saved_qualified_model_sessions_enter_candidate_domain(
    frozen: dict[str, Any],
) -> None:
    binding = frozen["parent_freeze"]
    assert binding["outcome_session_ids"] == frozen["pilot_registration"]["session_ids"]
    assert binding["qualified_session_ids"] == binding["outcome_session_ids"][1:]
    assert not set(binding["outcome_session_ids"]) & set(binding["excluded_mock_session_ids"])
    assert len(binding["excluded_mock_session_ids"]) == 4
    assert binding["old_fixture_sessions_in_population"] == 0
    assert binding["old_quotient_ids_or_support_labels_are_assignments"] is False


def test_changed_parent_bytes_are_rejected_without_mutating_formal_files(
    frozen: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = dict(frozen["parent_files"])
    changed["report.json"] = b"!" + changed["report.json"][1:]
    monkeypatch.setattr(inputs, "files_at", lambda _: changed)
    with pytest.raises(models.MeasurementError, match="inputs.invalid_frozen_evidence"):
        inputs.load_inputs(ROOT)
    with pytest.raises(models.MeasurementError, match="inputs.parent_changed"):
        inputs.assert_unchanged(ROOT, frozen)


@pytest.mark.parametrize("mutation", ["mock_origin", "promote_failed_session", "wrong_condition"])
def test_frozen_qualification_cannot_be_replaced_promoted_or_cross_conditioned(
    frozen: dict[str, Any],
    mutation: str,
) -> None:
    item = copy.deepcopy(frozen["sessions"][0])
    if mutation == "mock_origin":
        item["qualification"]["origin"] = "adapter_mock"
    elif mutation == "promote_failed_session":
        item["qualification"].update(qualified=True, Y=1, valid_final=True, qa_valid=True)
    else:
        item["qualification"]["model_configuration_id"] = "another_configuration"
    with pytest.raises(models.MeasurementError):
        inputs._validate_session(item, frozen["pilot_registration"], 0)


def test_reader_has_no_adapter_preflight_or_execution_imports_and_preserves_parent(
    frozen: dict[str, Any],
) -> None:
    tree = ast.parse(Path(inputs.__file__).read_text())
    modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        name.endswith((".preflight", ".adapter", ".engine", ".runtime")) for name in modules
    )
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(node.func, ast.Name)
        and node.func.id in {"audit_session", "audit_records", "aggregate_pilot", "replay_pilot"}
        for node in calls
    )
    inputs.assert_unchanged(ROOT, frozen)
