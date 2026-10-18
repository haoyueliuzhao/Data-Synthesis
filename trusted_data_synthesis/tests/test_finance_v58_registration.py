"""Synthetic CPU scope guards; never rerun an actual stopped-run audit."""

from copy import deepcopy

import pytest

import finqa_v58_registration as registration


def snapshot_fixture():
    counts = {
        "seed137.feedback_C05": 1, "seed251.feedback_C05": 3,
        "seed389.feedback_C05": 2, "seed137.shard00": 1,
        "seed137.shard01": 4, "seed137.shard02": 3,
        "seed137.shard03": 2, "seed251.shard00": 2,
        "seed251.shard01": 1, "seed251.shard02": 1, "seed251.shard03": 1,
        "seed137.train_Hold": 1, "seed251.train_Hold": 1, "seed389.train_Hold": 1,
    }
    return dict(
        scientific_root=str(registration.SCIENCE_ROOT),
        source_control_root=str(registration.PREVIOUS_CONTROL_ROOT),
        scientific_protocol_id=registration.SCIENTIFIC_PROTOCOL_ID,
        accepted={key: dict(path="CPU_ACCEPTED_" + key) for key in registration.ACCEPTED_JOBS},
        attempt_history=[dict(job_id=key, attempt=number)
                         for key, count in counts.items() for number in range(1, count + 1)],
        initial_job_states={key: dict(status="COMPLETE" if key in registration.ACCEPTED_JOBS else "PENDING",
                                     attempts=count, progress_units=1)
                            for key, count in counts.items()},
        known_unobserved_attempts=[dict(job_id=key, attempt=number, old_returncode=None)
                                  for key, number in sorted(registration.UNKNOWN_EXIT_ATTEMPTS)],
        resume_audits={key: dict(resume_allowed=True, unknown_calls=0) for key in counts},
        evaluation_registered=False, resource_wait_seconds=159.0,
        total_complete_class_tasks=273, total_complete_class_rows=1834,
        remaining_new_class_tasks=1215, remaining_feedback_episodes=0,
        complete_feedback_episodes=2100, new_feedback_sessions=0, UNKNOWN_feedback_calls=0,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        all_old_process_identities_observed_gone=True, old_missing_returncode=None,
        immutable_old_records_rewritten=False,
    )


def test_contract_and_snapshot_keep_science_dose_and_legitimate_stop_semantics():
    contract = registration.recovery_contract()
    assert contract["inherited_complete_feedback_episodes"] == 2100
    assert contract["remaining_feedback_episodes"] == 0
    assert contract["returned_feedback_or_rewards_resampled"] is False
    assert contract["old_single_request_quota_remaining"] == 0
    assert contract["inherited_complete_new_class_tasks"] == 273
    assert contract["remaining_new_class_tasks"] == 1215
    assert contract["remaining_new_optimizer_updates"] == 1788
    assert contract["new_evaluation_sessions"] == 12267
    assert contract["existing_actual_attempts"] == 24
    assert contract["previously_accepted_jobs"] == 4
    assert contract["explicitly_bound_old_unknown_exit_attempts"] == 7
    assert contract["requested_signal_shielding_not_enabled"] is True
    assert contract["SIGTERM_SIGINT_and_explicit_STOP_remain_terminal"] is True
    assert contract["SIGKILL_not_capturable_or_ignorable"] is True
    assert contract["no_new_unknown_call_or_unknown_exit_automatic_retry_allowance"] is True
    assert contract["total_GPU_workers"] == 4 and contract["extra_non_GPU_observer"] == 1
    snapshot = snapshot_fixture()
    assert registration.validate_snapshot(snapshot) is snapshot


def test_snapshot_rejects_fresh_feedback_budget_or_discarded_class_work():
    for changes in (dict(remaining_feedback_episodes=1),
                    dict(total_complete_class_tasks=272, remaining_new_class_tasks=1216)):
        snapshot = snapshot_fixture()
        snapshot.update(changes)
        with pytest.raises(ValueError, match="durable work"):
            registration.validate_snapshot(snapshot)


def test_snapshot_requires_exact_24_attempts_and_four_accepted_jobs():
    snapshot = snapshot_fixture()
    snapshot["attempt_history"].append(dict(job_id="unexpected", attempt=1))
    with pytest.raises(ValueError, match="historical attempt scope"):
        registration.validate_snapshot(snapshot)
    snapshot = snapshot_fixture()
    snapshot["accepted"].pop("seed389.feedback_C05")
    with pytest.raises(ValueError, match="accepted jobs"):
        registration.validate_snapshot(snapshot)


def test_snapshot_never_turns_an_unobserved_exit_into_zero():
    snapshot = snapshot_fixture()
    snapshot["known_unobserved_attempts"][0]["old_returncode"] = 0
    with pytest.raises(ValueError, match="unknown exits.*unknown status"):
        registration.validate_snapshot(snapshot)


def test_unknown_exit_exception_cannot_expand_or_authorize_unknown_generation():
    snapshot = snapshot_fixture()
    snapshot["known_unobserved_attempts"][0]["attempt"] = 99
    with pytest.raises(ValueError, match="unknown exits.*exact scope"):
        registration.validate_snapshot(snapshot)
    snapshot = snapshot_fixture()
    snapshot["resume_audits"]["seed251.feedback_C05"]["unknown_calls"] = 1
    with pytest.raises(ValueError, match="UNKNOWN or failed binding"):
        registration.validate_snapshot(snapshot)


def prepared_fixture(tmp_path, monkeypatch, **changes):
    root = tmp_path / "control"
    protocol_path, snapshot_path = root / "protocol/record.json", tmp_path / "snapshot/record.json"
    protocol = registration.publish(protocol_path, dict(schema="CPU_CONTROL_PROTOCOL"))
    snapshot = snapshot_fixture()
    registration.publish(snapshot_path, snapshot)
    monkeypatch.setattr(registration, "checked_protocol", lambda _root: protocol)
    body = dict(
        schema=registration.PREPARED_SCHEMA, protocol=registration.entry(protocol_path),
        preparation_audit=registration.entry(snapshot_path),
        scientific_root=str(registration.SCIENCE_ROOT),
        scientific_protocol_id=registration.SCIENTIFIC_PROTOCOL_ID,
        remaining_feedback_episodes=0, remaining_new_class_tasks=1215,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        old_single_request_quota_remaining=0, old_missing_returncode=None,
        **{key: deepcopy(snapshot[key]) for key in (
            "initial_job_states", "attempt_history", "accepted", "known_unobserved_attempts",
            "resource_wait_seconds", "evaluation_registered")},
    )
    body.update(changes)
    registration.publish(root / "prepared/record.json", body)
    return root


def test_prepared_reuses_the_exact_bound_snapshot(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch)
    prepared = registration.checked_prepared(root)
    source = registration.read_ref(prepared["preparation_audit"])
    assert prepared["accepted"] == source["accepted"]
    assert prepared["known_unobserved_attempts"] == source["known_unobserved_attempts"]
    assert prepared["old_missing_returncode"] is None


def test_prepared_cannot_silently_change_bound_bootstrap_state(tmp_path, monkeypatch):
    accepted = deepcopy(snapshot_fixture()["accepted"])
    accepted["seed389.feedback_C05"] = dict(path="DIFFERENT_ACCEPTED_RECORD")
    root = prepared_fixture(tmp_path, monkeypatch, accepted=accepted)
    with pytest.raises(ValueError, match="bootstrap snapshot changed"):
        registration.checked_prepared(root)


def test_prepared_cannot_reopen_sampling_or_infer_missing_exit(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path / "sampling", monkeypatch, remaining_feedback_episodes=46)
    with pytest.raises(ValueError, match="scientific budget"):
        registration.checked_prepared(root)
    root = prepared_fixture(tmp_path / "exit", monkeypatch, old_missing_returncode=0)
    with pytest.raises(ValueError, match="unknown historical exit"):
        registration.checked_prepared(root)
