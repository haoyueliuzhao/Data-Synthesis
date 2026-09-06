"""New wiring and scheduling controls only; no Provider, Runtime or model samples."""

import threading
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HttpxSender,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import plan, runner, stage
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration.source import (
    history_inventory,
    preserved_sources,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def forbid_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("wiring controls must never send a model request")

    monkeypatch.setattr(HttpxSender, "send", forbidden)


@pytest.fixture(scope="module")
def frozen():
    with execution_guard(phase="preparation") as counts:
        condition, registrations, panel = plan.freeze_condition(
            ROOT,
            record("implementation", control_evidence=True),
            record("constructed_policy", control_evidence=True),
        )
    assert guard_report(counts, phase="preparation")["all_zero"]
    return condition, registrations, panel


def test_exact_fresh_eight_stratified_source_and_unchanged_public_environment(frozen):
    condition, registrations, panel = frozen
    with execution_guard(phase="preparation") as counts:
        controls, requests = plan.wiring_controls(panel, condition, registrations)
    assert guard_report(counts, phase="preparation")["all_zero"]
    assert controls["passed"] and len(requests) == 8
    assert [r["label"] for r in registrations] == [
        "N01",
        "E01",
        "N02",
        "E02",
        "N03",
        "E03",
        "N04",
        "E04",
    ]
    assert len({r["session_id"] for r in registrations}) == 8
    assert all(
        r["reference_route"] is None and r["replacement_allowed"] is False for r in registrations
    )
    assert {r["run_condition_id"] for r in registrations} == {condition["id"]}
    assert requests["N01"]["public"] == requests["E01"]["public"]
    assert len(requests["N01"]["public"]["available_actions"]) == 2


def test_soft_profile_changes_only_frozen_generation_presentation(frozen):
    condition, _, panel = frozen
    neutral, guided = (plan.configuration(name).as_record() for name in ("N", "E"))
    differences = {key for key in neutral if neutral[key] != guided[key]}
    assert differences == {"id", "profile", "system_prompt"}
    assert neutral["system_prompt"] == SYSTEM_PROMPT
    assert guided["system_prompt"] == SYSTEM_PROMPT + "\n\n" + plan.GUIDANCE
    assert condition["profiles"]["E"]["correctness_requirement"] is False
    assert condition["profiles"]["E"]["disclosed_total_success_still_qualified"] is True
    assert canonical_json_bytes(panel.adapter("S").context) == canonical_json_bytes(
        condition["original_context"]
    )
    assert condition["maximum_provider_attempts"] == 8 * 32 == 256
    assert condition["maximum_reserved_token_allowance"] == 8 * 32 * 107_520
    assert all(
        condition["configurations"][name]["maximum_pilot_attempts"] == 256 for name in ("N", "E")
    )
    with pytest.raises(ProtocolError):
        panel.adapter("B")
    with pytest.raises(ProtocolError):
        plan.configuration("unknown")


def test_published_history_and_all_898_prior_python_files_preserved():
    with execution_guard(phase="preparation"):
        history = history_inventory(ROOT)
        sources = preserved_sources(ROOT)
    assert history["file_count"] == 12_984 and history["byte_count"] == 653_652_590
    assert sources["file_count"] == 898


def test_only_new_stage_directory_is_writable_target(tmp_path):
    with pytest.raises(ProtocolError):
        stage._target(tmp_path, tmp_path / "trusted_data_synthesis/artifacts/qa_vnext_task_panel")
    with pytest.raises(ProtocolError):
        stage._target(tmp_path, tmp_path / stage.ARTIFACT_PREFIX)


@pytest.mark.parametrize("initial_outcome", ["success", "known_failure", "unknown"])
def test_fixed_waves_no_success_replacement_or_outcome_adaptation(
    tmp_path, frozen, monkeypatch, initial_outcome
):
    condition, registrations, panel = frozen
    output = tmp_path / stage.ARTIFACT_PREFIX / plan.RUN_TAG
    preparation = {
        "condition": condition,
        "registrations": registrations,
        "panel": panel,
        "configurations": {name: plan.configuration(name) for name in ("N", "E")},
        "report": record("constructed_preparation", control_evidence=True),
        "manifest": record("constructed_manifest", control_evidence=True),
        "comparison_contract": record("constructed_comparison_contract", control_evidence=True),
        "implementation": record("implementation", control_evidence=True),
        "history_inventory": {"control": True},
    }
    monkeypatch.setattr(runner, "prepared", lambda *args: preparation)
    monkeypatch.setattr(runner, "history_inventory", lambda *args: {"control": True})
    monkeypatch.setattr(runner, "verify_source_snapshot", lambda *args: None)
    monkeypatch.setattr(
        runner.online_runner, "_credential", lambda *args: "constructed-no-network-key"
    )
    lock, barrier = threading.Lock(), threading.Barrier(2)
    launched, unfinished = [], []

    def result(registration, status):
        return record(
            "qualification",
            registration_id=registration["id"],
            status=status,
            reason="constructed_scheduling_control",
            provider_attempt_count=0,
            runtime_submission_count=0,
            control_evidence=True,
        )

    def worker(actual_panel, config, registration, child, start, credential):
        assert config.as_record() == condition["configurations"][registration["profile"]]
        assert actual_panel is panel and start["status"] == "started"
        with lock:
            launched.append(registration["label"])
        barrier.wait(timeout=5)
        status = initial_outcome if registration["label"] == "E01" else "success"
        value = result(registration, status)
        child.json("qualification.json", value)
        return value

    def no_worker(prep, registration, child, start):
        unfinished.append(registration["label"])
        assert start["status"] == "not_started"
        value = result(registration, "not_started")
        child.json("qualification.json", value)
        return value

    monkeypatch.setattr(runner.online_runner, "_run_session", worker)
    monkeypatch.setattr(runner, "_qualify_unfinished", no_worker)
    monkeypatch.setattr(
        runner,
        "analyze_new",
        lambda *args: record("support_exploration_report", control_evidence=True),
    )
    runner.run(tmp_path, output)
    schedule = read_json((output / "execution/schedule.json").read_bytes())
    assert schedule["registered_denominator"] == 8 and len(schedule["events"]) == 8
    assert schedule["maximum_parallel_sessions"] == 2 and schedule["replacements"] == 0
    assert [row["label"] for row in schedule["events"]] == list(plan.LABELS)
    assert len(launched) == (2 if initial_outcome == "unknown" else 8)
    assert len(unfinished) == (6 if initial_outcome == "unknown" else 0)
    with pytest.raises(ProtocolError, match="population_already_started"):
        runner.run(tmp_path, output)
