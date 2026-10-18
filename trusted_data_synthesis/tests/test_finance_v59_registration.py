"""Necessary V59 differences, using synthetic records and no scientific work."""

from copy import deepcopy

import pytest

import finqa_v59_registration as registration


def snapshot_fixture():
    counts = {
        "seed137.feedback_C05": 1, "seed251.feedback_C05": 3, "seed389.feedback_C05": 2,
        "seed137.shard00": 1, "seed137.shard01": 5, "seed137.shard02": 4,
        "seed137.shard03": 3, "seed251.shard00": 3,
        "seed251.shard01": 1, "seed251.shard02": 1, "seed251.shard03": 1,
        "seed137.train_Hold": 1, "seed251.train_Hold": 1, "seed389.train_Hold": 1,
    }
    history = [dict(job_id=key, attempt=i) for key, count in counts.items() for i in range(1, count + 1)]
    return dict(
        schema=registration.SNAPSHOT_SCHEMA, scientific_root=str(registration.SCIENCE_ROOT),
        source_control_root=str(registration.PREVIOUS_CONTROL_ROOT),
        scientific_protocol_id=registration.SCIENTIFIC_PROTOCOL_ID,
        source_control_protocol_id=registration.PREVIOUS_CONTROL_PROTOCOL_ID,
        accepted={key: dict(path="CPU_ACCEPTED_" + key) for key in registration.ACCEPTED_JOBS},
        attempt_history=history, all_old_attempts=deepcopy(history),
        initial_job_states={key: dict(status="COMPLETE" if key in registration.ACCEPTED_JOBS else "PENDING",
                                     attempts=count, progress_units=1) for key, count in counts.items()},
        known_unobserved_attempts=[dict(job_id=key, attempt=number, old_returncode=None)
                                  for key, number in sorted(registration.UNKNOWN_EXIT_ATTEMPTS)],
        resume_audits={key: dict(resume_allowed=True, unknown_calls=0) for key in counts},
        process_identities=[], old_journal=dict(path="CPU_ONLY_OLD_JOURNAL"),
        evaluation_registered=False, resource_wait_seconds=159.7080834461376,
        total_complete_class_tasks=756, total_complete_class_rows=5032, remaining_new_class_tasks=732,
        complete_feedback_episodes=2100, remaining_feedback_episodes=0,
        new_feedback_sessions=0, UNKNOWN_feedback_calls=0,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        all_old_process_identities_observed_gone=True, old_missing_returncode=None,
        immutable_old_records_rewritten=False,
    )


def test_control04_contract_and_actual_scope_are_bounded():
    contract = registration.recovery_contract()
    assert registration.ROOT.name == "signal_recovery_04"
    assert registration.PREVIOUS_CONTROL_ROOT.name == "signal_recovery_03"
    assert len(registration.FILES) == 6
    assert contract["sharing_a_device_with_registered_yyy_owner_forbidden"] is True
    assert contract["GPU_owner_conflict_yields_only_this_experiment_without_signaling_other_users"] is True
    assert (contract["inherited_complete_new_class_tasks"], contract["remaining_new_class_tasks"]) == (756, 732)
    assert contract["inherited_complete_feedback_episodes"] == 2100 and contract["remaining_feedback_episodes"] == 0
    assert contract["existing_actual_attempts"] == 28 and contract["explicitly_bound_old_unknown_exit_attempts"] == 11
    assert contract["total_GPU_workers"] == 4 and contract["owner_uid"] == 1004
    assert contract["owner_SIGTERM_all_SIGINT_explicit_STOP_and_unknown_semantics_remain_terminal"] is True
    assert contract["SIGKILL_not_capturable_ignorable_or_prevented"] is True
    assert contract["external_watchdog_or_extra_outer_recovery_not_added"] is True
    value = snapshot_fixture()
    assert registration.validate_snapshot(value) is value


def test_completed_work_cannot_be_reassigned_or_discarded():
    for changes in (dict(remaining_feedback_episodes=46),
                    dict(total_complete_class_tasks=273, remaining_new_class_tasks=1215)):
        value = snapshot_fixture()
        value.update(changes)
        with pytest.raises(ValueError, match="saved scientific work"):
            registration.validate_snapshot(value)


def test_only_the_exact_eleven_historical_exits_remain_unknown():
    value = snapshot_fixture()
    value["known_unobserved_attempts"][0]["old_returncode"] = 0
    with pytest.raises(ValueError, match="unknown exits.*unknown status"):
        registration.validate_snapshot(value)
    value = snapshot_fixture()
    value["known_unobserved_attempts"][0]["attempt"] = 99
    with pytest.raises(ValueError, match="unknown exits.*exact registered scope"):
        registration.validate_snapshot(value)
    value = snapshot_fixture()
    value["resume_audits"]["seed251.feedback_C05"]["unknown_calls"] = 1
    with pytest.raises(ValueError, match="UNKNOWN generation"):
        registration.validate_snapshot(value)


def test_actual_attempt_numbers_must_be_contiguous_without_reset_or_duplicates():
    value = snapshot_fixture()
    row = next(row for row in value["attempt_history"] if row == dict(job_id="seed137.shard01", attempt=5))
    row["attempt"] = 4
    with pytest.raises(ValueError, match="attempt sequence cannot reset or skip"):
        registration.validate_snapshot(value)


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
        scientific_root=str(registration.SCIENCE_ROOT), scientific_protocol_id=registration.SCIENTIFIC_PROTOCOL_ID,
        remaining_feedback_episodes=0, remaining_new_class_tasks=732,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        old_single_request_quota_remaining=0, old_missing_returncode=None,
        **{key: deepcopy(snapshot[key]) for key in registration.BOOTSTRAP_FIELDS},
    )
    body.update(changes)
    registration.publish(root / "prepared/record.json", body)
    return root


def test_prepared_carries_the_exact_snapshot_without_inventing_exit_codes(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path, monkeypatch)
    result = registration.checked_prepared(root)
    snapshot = registration.read_ref(result["preparation_audit"])
    assert all(result[key] == snapshot[key] for key in registration.BOOTSTRAP_FIELDS)
    assert result["old_missing_returncode"] is None


def test_prepared_rejects_changed_budget_and_changed_bound_audit(tmp_path, monkeypatch):
    root = prepared_fixture(tmp_path / "budget", monkeypatch, remaining_new_optimizer_updates=1000)
    with pytest.raises(ValueError, match="remaining scientific budget"):
        registration.checked_prepared(root)
    changed = deepcopy(snapshot_fixture()["resume_audits"])
    changed["seed137.shard01"]["progress_units"] = 999
    root = prepared_fixture(tmp_path / "binding", monkeypatch, resume_audits=changed)
    with pytest.raises(ValueError, match="bootstrap snapshot changed"):
        registration.checked_prepared(root)
