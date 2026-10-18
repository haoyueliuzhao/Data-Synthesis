"""Synthetic CPU guards for a new control episode over unchanged V56 science."""

from copy import deepcopy

import pytest

import finqa_v57_registration as registration


def test_recovery_contract_preserves_science_stop_history_and_remaining_dose():
    contract = registration.recovery_contract()
    assert contract["scientific_root"] == str(registration.SCIENCE_ROOT)
    assert contract["independent_control_root"] == str(registration.ROOT)
    assert registration.ROOT.parent == registration.SCIENCE_ROOT
    assert contract["unchanged_scientific_protocol_id"] == registration.SCIENTIFIC_PROTOCOL_ID
    assert contract["no_scientific_parent_or_feedback_ID_rebinding"] is True
    assert contract["old_stop_marker_and_failed_controller_history_immutable"] is True
    assert contract["old_unknown_exit_code_never_fabricated"] is True
    assert contract["explicit_new_SIGTERM_SIGINT_or_STOP_remains_terminal"] is True
    assert contract["inherited_complete_feedback_episodes"] == 2054
    assert contract["remaining_feedback_episodes"] == 46
    assert contract["inherited_partial_returned_turns"] == 1
    assert contract["UNKNOWN_feedback_reexecution"] is False
    assert contract["old_single_request_quota_remaining"] == 0
    assert contract["remaining_new_class_tasks"] == 1280
    assert contract["remaining_new_optimizer_updates"] == 1788
    assert contract["evaluation_sessions"] == 12267
    assert (contract["max_gpu_workers"], contract["per_gpu_workers"]) == (4, 1)


def stopped_jobs():
    def state(status, attempts, progress=0):
        return dict(status=status, attempts=attempts, no_progress_failures=2,
                    next_eligible_epoch=123.0, progress_units=progress,
                    durable_progress_digest=f"old-progress-{progress}")

    old = dict(
        accepted={"seed137.feedback_C05": dict(path="accepted-feedback"),
                  "seed137.shard00": dict(path="accepted-class")},
        job_states={
            "seed137.feedback_C05": state("COMPLETE", 1, 1993),
            "seed137.shard00": state("COMPLETE", 1, 186),
            "seed251.feedback_C05": state("RUNNING", 2, 1900),
            "seed251.train_Hold": state("PENDING", 0),
        },
    )
    audits = {"seed251.feedback_C05": dict(
        resume_allowed=True, unknown_calls=0, progress_units=1963,
        durable_progress_digest="actual-durable-progress")}
    counts = {key: state["attempts"] for key, state in old["job_states"].items()}
    return old, audits, counts


def test_initial_states_preserve_accepted_attempt_counts_and_actual_durable_progress():
    old, audits, counts = stopped_jobs()
    unchanged = deepcopy(old)
    states = registration.initial_job_states(old, audits, attempt_counts=counts)
    assert old == unchanged
    for key in old["accepted"]:
        assert states[key] == old["job_states"][key]
        assert states[key] is not old["job_states"][key]
    pending = states["seed251.feedback_C05"]
    assert pending["status"] == "PENDING" and pending["attempts"] == 2
    assert pending["progress_units"] == 1963
    assert pending["durable_progress_digest"] == "actual-durable-progress"
    assert pending["no_progress_failures"] == 2
    assert pending["next_eligible_epoch"] == 0.0
    assert pending["initial_authorized_signal_recovery"] is True
    assert states["seed251.train_Hold"]["attempts"] == 0


def test_initial_states_reject_attempt_count_reset():
    old, audits, counts = stopped_jobs()
    counts["seed251.feedback_C05"] = 1
    with pytest.raises(ValueError, match="actual attempt directories"):
        registration.initial_job_states(old, audits, attempt_counts=counts)


def test_initial_states_never_authorize_unknown_feedback_reexecution():
    old, audits, counts = stopped_jobs()
    audits["seed251.feedback_C05"]["unknown_calls"] = 1
    with pytest.raises(ValueError, match="UNKNOWN.*blocks recovery"):
        registration.initial_job_states(old, audits, attempt_counts=counts)


def test_initial_states_reject_durable_progress_regression():
    old, audits, counts = stopped_jobs()
    audits["seed251.feedback_C05"]["progress_units"] = 1899
    with pytest.raises(ValueError, match="lost durable progress"):
        registration.initial_job_states(old, audits, attempt_counts=counts)


def prepared_fixture(tmp_path, monkeypatch, **changes):
    root = tmp_path / "control"
    protocol_path = root / "protocol/record.json"
    protocol = registration.publish(protocol_path, dict(schema="synthetic_control_protocol"))
    monkeypatch.setattr(registration, "checked_protocol", lambda _root: protocol)
    body = dict(
        schema=registration.PREPARED_SCHEMA,
        protocol=registration.entry(protocol_path),
        scientific_root=str(registration.SCIENCE_ROOT),
        scientific_protocol_id=registration.SCIENTIFIC_PROTOCOL_ID,
        remaining_feedback_episodes=46, remaining_new_class_tasks=1280,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        old_single_request_quota_remaining=0, old_missing_returncode=None,
        complete_unaccepted_stage_requires_new_finalizer=True,
        accepted={"seed137.feedback_C05": {}, "seed137.shard00": {}},
        attempt_history=[dict(attempt=i + 1) for i in range(7)],
        known_unobserved_attempts=[dict(attempt=i + 1, old_returncode=None) for i in range(3)],
        evaluation_registered=False,
    )
    body.update(changes)
    registration.publish(root / "prepared/record.json", body)
    return root


def test_checked_prepared_accepts_only_remaining_budget_and_unknown_old_exits(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch)
    result = registration.checked_prepared(root)
    assert result["old_missing_returncode"] is None
    assert result["remaining_feedback_episodes"] == 46
    assert result["complete_unaccepted_stage_requires_new_finalizer"] is True


def test_checked_prepared_rejects_reset_feedback_budget(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch, remaining_feedback_episodes=2100)
    with pytest.raises(ValueError, match="prepared scientific scope"):
        registration.checked_prepared(root)


def test_checked_prepared_rejects_fabricated_old_exit_zero(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch, old_missing_returncode=0)
    with pytest.raises(ValueError, match="unknown historical exit"):
        registration.checked_prepared(root)
