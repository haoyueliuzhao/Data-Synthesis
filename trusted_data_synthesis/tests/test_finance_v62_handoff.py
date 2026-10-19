"""CPU/mock only: no real crontab, scientific task or process signal."""
import copy
import fcntl
import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace

import pytest

import finqa_v62_handoff as h
import finqa_v62_cron as cron


@pytest.fixture
def environment(tmp_path, monkeypatch):
    science = tmp_path / "science"
    root, source, old = science / "six", science / "source04", science / "old"
    for path in (root, source, old):
        path.mkdir(parents=True)
    for key, value in (("MASTER_ROOT", root), ("SCIENCE_ROOT", science),
                       ("SOURCE_CONTROL_ROOT", source), ("OLD_MASTER", old)):
        monkeypatch.setattr(h, key, value)
    monkeypatch.setattr(os, "getuid", lambda: 1004)
    monkeypatch.setattr(os, "geteuid", lambda: 1004)
    monkeypatch.setattr(h, "_uids", lambda _: (1004,) * 4)
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(
        pid=pid, birth=birth, alive=pid in (101, 102), proc_state="S"))
    monkeypatch.setattr(os, "kill", lambda *a: pytest.fail("no actual process signal in CPU tests"))
    monkeypatch.setattr(h, "_pidfd_term", lambda *a: pytest.fail("unmocked pidfd signal"))
    locks = [science / "owner.lock", *[science / "leases" / f"gpu{i}.lock" for i in range(8)]]
    for path in locks + [old / "cron/envelope.lock", old / "cron/crontab_change.lock", root / "cron/envelope.lock"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    source_protocol = h._write(source / "protocol/record.json", dict(
        scientific_protocol_id=h.SCIENTIFIC_PROTOCOL_ID, scientific_root=str(science)))
    monkeypatch.setattr(h, "SOURCE_CONTROL_PROTOCOL_ID", source_protocol["id"])
    core = [f"core{i:02d}" for i in range(23)]
    prepared = h._write(source / "prepared/record.json", dict(
        initial_job_states={key: {"status": "PENDING"} for key in core},
        attempt_history=[], known_unobserved_attempts=[], evaluation_registered=False))
    old_protocol = h._write(old / "protocol/record.json", dict(
        original_lock_bindings={str(path): {k: v for k, v in h._inode(path).items() if k != "path"}
                                for path in locks}))
    monkeypatch.setattr(h, "OLD_PROTOCOL_ID", old_protocol["id"])
    episode = dict(root=str(source), protocol_id=source_protocol["id"])
    h._write(old / "prepared/record.json", dict(initial_episode=episode))
    for role, pid, relative in (("controller", 101, "controllers/attempt0001/launch/record.json"),
                                ("supervisor", 102, "supervisor/launch/record.json")):
        h._write(source / relative, dict(role=role, pid=pid, birth=f"birth-{pid}",
            controller_attempt=1, control_protocol_id=source_protocol["id"]))
    retired = tmp_path / "retired61/completed/record.json"
    h._write(retired, dict(status="V61_PASSIVE_GUARD_RETIRED"))
    monkeypatch.setattr(h.supersession, "COMPLETED_RECORD_PATH", retired)
    monkeypatch.setattr(h.supersession, "checked_completed", lambda: h.checked_record(retired))
    binding = h.snapshot_binding()
    protocol = h._write(root / "protocol/record.json", dict(handoff_binding=binding))
    h._write(root / "prepared/record.json", dict(protocol_id=protocol["id"], handoff_binding=binding))
    journal = dict(protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=source_protocol["id"],
        controller_attempt=1, accepted={}, job_states={key: {"status": "PENDING"} for key in core},
        active_jobs=[], attempt_history=[], updated_epoch=time.time())
    journal = h._write(source / "journal/state.json", journal)
    monkeypatch.setattr(h, "_admission", lambda _: (protocol, binding))
    monkeypatch.setattr(h, "load_v59_module", lambda _: SimpleNamespace(signal_decision=lambda number, pid, uid, code:
        dict(filtered=(number == 15 and uid != 1004 and code == 0))))
    return SimpleNamespace(root=root, source=source, old=old, science=science,
        binding=binding, protocol=protocol, journal=journal, core=core, prepared=prepared)


def mark_complete(e):
    body = dict(e.journal, accepted={key: {} for key in e.core},
                job_states={key: {"status": "COMPLETE"} for key in e.core})
    return h._write(e.source / "journal/state.json", body)


def transaction(e):
    journal = h.checked_record(e.source / "journal/state.json")
    return h._write(e.root / "handoff/transaction/record.json", dict(
        protocol_id=e.protocol["id"], binding=e.binding, at_epoch=time.time() - 1,
        sender=dict(pid=201, birth="sender-birth", uid=1004, euid=1004),
        boundary=dict(boundary_digest=h._boundary_digest(journal))))


def add_proof(e, tx):
    directory = e.root / "handoff/signals/controller"
    intent = h._write(directory / "intent/record.json", dict(transaction_id=tx["id"],
        at_epoch=tx["at_epoch"], sender=tx["sender"], target=e.binding["controls"]["controller"]))
    dispatch = h._write(directory / "dispatch/record.json", dict(
        schema="v62_pidfd_TERM_dispatch_returned.v1", sender=tx["sender"],
        pidfd_send_returned_success=True, returned_epoch=time.time(),
        transaction_id=tx["id"], intent_id=intent["id"]))
    event = dict(schema="v59_received_signal_kernel_receipt.v1", provenance="kernel_sigwaitinfo",
        role="controller", pid=101, signal=15, si_pid=201, si_uid=1004, si_code=0,
        at_epoch=time.time(), receipt_id="one-exact-receipt", decision=dict(filtered=False))
    proof = h._write(directory / "receipt/record.json", dict(
        schema="v62_exact_maintenance_kernel_receipt_bound.v1", transaction_id=tx["id"],
        intent_id=intent["id"], dispatch_id=dispatch["id"], receiver_observed_while_sender_same_identity=True,
        sender=tx["sender"], event=event, receipt_bound_epoch=time.time()))
    path = e.source / "signals/run-101/received.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event) + "\n")
    return proof, path, event


def test_snapshot_is_readonly_and_binds_fixed_attempt_and_history(environment):
    e = environment
    assert h.snapshot_binding() == e.binding
    assert e.binding["controller_attempt"] == 1 and len(e.binding["core_job_ids"]) == 23
    assert len(e.binding["original_lock_bindings"]) == 9
    assert not (e.root / "handoff").exists()


def test_dead_or_zombie_is_not_live_admission_but_not_fabricated_gone(environment, monkeypatch):
    e = environment
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=True, proc_state="Z"))
    with pytest.raises(h.HandoffError, match="NOT_LIVE_OWNER"):
        h.checked_binding(e.binding, require_live=True)
    assert h.checked_binding(e.binding, require_live=False) == e.binding


def test_episode_change_never_followed(environment):
    e = environment
    h._write(e.old / "state.json", dict(protocol_id=h.OLD_PROTOCOL_ID,
        current_episode=dict(root="another-episode", protocol_id="different"), phase="WATCHING", pending_request=None))
    with pytest.raises(h.HandoffError, match="DO_NOT_FOLLOW"):
        h.checked_binding(e.binding)


def test_partial_gpu_locks_are_released_before_yield(environment):
    rows = h._lease_rows(environment.binding)
    with Path(rows[3]["path"]).open("r+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with h._locks(rows) as available:
            assert not available
            for row in rows[:3]:
                with Path(row["path"]).open("r+") as probe:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_replaced_lease_inode_is_not_a_new_free_original(environment):
    row = h._lease_rows(environment.binding)[0]
    path = Path(row["path"])
    path.rename(path.with_suffix(".old"))
    path.touch()
    with pytest.raises(h.HandoffError, match="LEASE_CHANGED"):
        with h._locks([row]):
            pass


def test_passive_polls_cache_only_admission_and_never_retire_old(environment, monkeypatch):
    e = environment
    admissions = []
    monkeypatch.setattr(h, "_admission", lambda _: (admissions.append(1) or e.protocol, e.binding))
    monkeypatch.setattr(h, "_signal_events", lambda *a: pytest.fail("waiting must not reread signal logs"))
    monkeypatch.setattr(h, "_execute", lambda *a: pytest.fail("training incomplete"))
    session = {}
    for _ in range(3):
        assert h.advance_handoff(e.root, session=session)["status"] == "WAITING_FOR_ACCEPTED_TRAINING_CORE"
    assert len(admissions) == 1
    assert not (e.old / "terminal/record.json").exists()


def test_stale_journal_waits_without_forcing_switch(environment):
    e = environment
    h._write(e.source / "journal/state.json", dict(e.journal, updated_epoch=time.time()-60))
    assert h.advance_handoff(e.root)["status"] == "WAITING_FOR_FRESH_SOURCE_JOURNAL"
    assert not (e.root / "handoff/blocked/record.json").exists()


def test_draining_is_not_empty_even_if_core_accepted(environment, monkeypatch):
    e = environment
    journal = mark_complete(e)
    h._write(e.source / "journal/state.json", dict(journal,
        active_jobs=[dict(pid=701, birth="child", lifecycle="DRAINING")]))
    monkeypatch.setattr(h, "_execute", lambda *a: pytest.fail("draining is occupied"))
    assert h.advance_handoff(e.root)["status"] == "WAITING_FOR_NATURAL_GLOBAL_EMPTY"


def test_only_full_lease_fresh_empty_boundary_reaches_execute(environment, monkeypatch):
    e = environment
    mark_complete(e)
    monkeypatch.setattr(h, "_installed_new", lambda *a, **k: (None, None))
    monkeypatch.setattr(h, "_accepted_and_exited", lambda binding, journal: {"boundary_digest": h._boundary_digest(journal)})
    def execute(root, protocol, binding, journal, boundary):
        for row in h._lease_rows(binding):
            with Path(row["path"]).open("r+") as probe:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not journal["active_jobs"] and set(binding["core_job_ids"]) <= set(journal["accepted"])
        return {"status": "MOCK_EXECUTION_ONLY"}
    monkeypatch.setattr(h, "_execute", execute)
    assert h.advance_handoff(e.root)["status"] == "MOCK_EXECUTION_ONLY"


class FakeCron:
    def __init__(self, raw, *, fail_write=False):
        self.raw, self.fail_write = raw, fail_write
        self.calls, self.writes = [], 0

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command == ["crontab", "-l"]:
            return SimpleNamespace(returncode=0, stdout=self.raw, stderr=b"")
        assert command == ["crontab", "-"]
        self.writes += 1
        if self.fail_write:
            raise OSError("synthetic uncertain write")
        self.raw = kwargs["input"]
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


def test_new_cron_present_then_old_exact_line_only_retired(environment):
    e = environment
    tx = transaction(e)
    other = b"MAILTO=private_fixture\n1 1 * * * unrelated\n"
    runner = FakeCron(other + h._old_line()+b"\n"+cron.line(e.root)+b"\n")
    h._retire_old_watchdog(e.root, tx, runner=runner)
    assert runner.raw == other+cron.line(e.root)+b"\n" and runner.writes == 1
    terminal = h.checked_record(e.old / "terminal/record.json")
    assert terminal["transaction_id"] == tx["id"] and terminal["automatic_recovery_allowed"] is False
    assert not (e.source / "STOP").exists() and not (e.old / "STOP").exists()
    assert "private_fixture" not in json.dumps(terminal)


def test_missing_new_cron_does_not_retire_old_guard(environment):
    e = environment
    with pytest.raises(h.HandoffError, match="NEW_GUARD_NOT_INSTALLED"):
        h._retire_old_watchdog(e.root, transaction(e), runner=FakeCron(h._old_line()+b"\n"))
    assert not (e.old / "terminal/record.json").exists()


def test_signal_intent_precedes_mock_pidfd_and_exact_receipt_is_bound(environment, monkeypatch):
    e = environment
    tx = transaction(e)
    events = []
    monkeypatch.setattr(h, "_sender", lambda: tx["sender"])
    monkeypatch.setattr(h, "_pidfd_open", lambda pid: os.open(os.devnull, os.O_RDONLY))
    def send(fd):
        intent = h.checked_record(e.root / "handoff/signals/controller/intent/record.json")
        assert intent["sender"] == tx["sender"] and intent["target"]["pid"] == 101
        events.append(dict(path="fixture", event=dict(schema="v59_received_signal_kernel_receipt.v1",
            provenance="kernel_sigwaitinfo", signal=15, role="controller", pid=101,
            si_pid=201, si_uid=1004, si_code=0, at_epoch=time.time(), receipt_id="one")))
    monkeypatch.setattr(h, "_pidfd_term", send)
    monkeypatch.setattr(h, "_signal_events", lambda *a: events)
    proof = h._dispatch_term(e.root, tx, "controller")
    assert proof["receiver_observed_while_sender_same_identity"] is True and len(events) == 1
    with pytest.raises(h.HandoffError, match="CANNOT_REPEAT"):
        h._dispatch_term(e.root, tx, "controller")
    assert len(events) == 1


@pytest.mark.parametrize("field,value", [("signal", 2), ("si_pid", 999), ("si_uid", 0),
    ("si_code", -1), ("pid", 102), ("role", "scientific_worker"), ("at_epoch", 0)])
def test_exact_signal_match_rejects_other_authorities(environment, field, value):
    e = environment
    tx = transaction(e)
    _, _, event = add_proof(e, tx)
    intent = h.checked_record(e.root / "handoff/signals/controller/intent/record.json")
    assert h._matches(event, intent)
    assert not h._matches(dict(event, **{field: value}), intent)


def test_arbitrary_later_owner_term_and_INT_are_not_maintenance(environment):
    e = environment
    tx = transaction(e)
    _, path, event = add_proof(e, tx)
    assert set(h._check_maintenance_signals(e.root, tx, final=True)) == {"controller"}
    path.write_text(json.dumps(event)+"\n"+json.dumps(dict(event, receipt_id="later", si_pid=999))+"\n")
    with pytest.raises(h.HandoffError, match="UNAUTHORIZED_OWNER_TERM_OR_INT"):
        h._check_maintenance_signals(e.root, tx, final=True)


def test_extra_scientific_worker_signal_is_not_hidden_by_control_receipt(environment):
    e = environment
    tx = transaction(e)
    _, _, event = add_proof(e, tx)
    worker = e.science / "stages/seed137/train/attempts/attempt0001/signals/received.jsonl"
    worker.parent.mkdir(parents=True)
    worker.write_text(json.dumps(dict(event, role="scientific_worker", pid=999,
        receipt_id="worker-stop"))+"\n")
    with pytest.raises(h.HandoffError, match="UNAUTHORIZED_OWNER_TERM_OR_INT"):
        h._check_maintenance_signals(e.root, tx, final=True, extra_paths=[str(worker)])


def test_readonly_observer_retirement_not_a_scientific_stop(environment):
    e = environment
    tx = transaction(e)
    _, _, event = add_proof(e, tx)
    observer = e.source / "signals/observer-777/received.jsonl"
    observer.parent.mkdir(parents=True)
    observer.write_text(json.dumps(dict(event, role="observer", pid=777,
        receipt_id="monitor-retirement"))+"\n")
    assert set(h._check_maintenance_signals(e.root, tx, final=True)) == {"controller"}


def test_interrupted_signal_intent_is_permanent_unknown_no_resend(environment, monkeypatch):
    e = environment
    tx = transaction(e)
    h._write(e.root / "handoff/signals/controller/intent/record.json", dict(
        transaction_id=tx["id"], sender=tx["sender"], target=e.binding["controls"]["controller"]))
    monkeypatch.setattr(h, "_pidfd_term", lambda *a: pytest.fail("ambiguous intent must not resend"))
    with pytest.raises(h.HandoffError, match="UNKNOWN_SIGNAL_DISPATCH_NO_RETRY"):
        h._check_maintenance_signals(e.root, tx, final=True)


def final_setup(e, monkeypatch, code=2):
    tx = transaction(e)
    add_proof(e, tx)
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    h._write(e.source / "control/stop_requested/record.json", dict(schema="v57_terminal_explicit_stop.v1",
        protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID,
        at_epoch=time.time(), reason=dict(signals=[15], marker=False)))
    h._write(e.source / "supervisor/attempts/attempt0001/actual_exit/record.json", dict(
        protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID,
        actual_waitpid_observed=True, returncode=code, pid=101, birth="birth-101"))
    h._write(e.source / "supervisor/closeout/record.json", dict(
        protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID,
        status="STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME", controller_attempts=1, automatic_restart_stopped=True))
    h._write(e.source / "supervisor/orphan_stop/record.json", dict(
        protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID,
        workers=[], all_identities_observed_exited=True))
    return tx


def test_original_control_stop_code_two_preserved_not_fabricated_zero(environment, monkeypatch):
    e = environment
    tx = final_setup(e, monkeypatch)
    assert h._finalize(e.root, tx)["status"] == "READY_FOR_WATCHDOG"
    result = h.checked_record(e.root / "handoff/completed/record.json")
    assert result["controller_actual_returncode"] == 2 and result["controller_zero_exit_not_claimed"]
    assert result["supervisor_OS_returncode"] is None and not result["supervisor_actual_waitpid_observed"]
    assert not result["supervisor_received_maintenance_signal"]


def test_other_control_exit_code_cannot_be_called_authorized_maintenance(environment, monkeypatch):
    e = environment
    tx = final_setup(e, monkeypatch, code=0)
    with pytest.raises(h.HandoffError, match="EXPECTED_STOP_CODE"):
        h._finalize(e.root, tx)


def test_no_final_receipt_yields_none_not_broad_stop_exception(environment):
    e = environment
    assert h.validate_authorized_stop(e.root, e.binding["source_episode"], {}) is None


def test_later_explicit_STOP_always_revokes_handoff_validation(environment, monkeypatch):
    e = environment
    tx = final_setup(e, monkeypatch)
    h._finalize(e.root, tx)
    e.source.joinpath("STOP").touch()
    with pytest.raises(h.HandoffError, match="EXPLICIT_STOP_NOT_MAINTENANCE"):
        h.validate_authorized_stop(e.root, e.binding["source_episode"], {})


def add_original_supervisor_relay(e, tx, *, enrichment=True, wrong_birth=False):
    primary = h.checked_record(e.root / "handoff/signals/controller/receipt/record.json")
    marker = h._write(e.source / "control/stop_requested/record.json", dict(
        schema="v57_terminal_explicit_stop.v1", protocol_id=h.SCIENTIFIC_PROTOCOL_ID,
        control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID, at_epoch=time.time(),
        reason=dict(signals=[15], marker=False)))
    event = dict(primary["event"], receipt_id="original-supervisor-forwarded-once",
                 si_pid=102, at_epoch=max(time.time(), marker["at_epoch"]))
    path = Path(primary["signal_log_path"]) if "signal_log_path" in primary else e.source / "signals/run-101/received.jsonl"
    text = path.read_text()+json.dumps(event)+"\n"
    if enrichment:
        observed = time.time()
        row = dict(schema="v58_received_signal_identity_enrichment.v1",
            receipt_id=event["receipt_id"], receipt_at_epoch=event["at_epoch"],
            observed_at_epoch=observed, pid=101, role="controller",
            kernel_receipt_fsynced_before_proc_reads=True, identities_are_post_signal_observations=True,
            sender_parent_chain=dict(processes=[dict(pid=102,
                birth="wrong" if wrong_birth else "birth-102", ruid=1004, euid=1004,
                identity_consistent=True, observed_at_epoch=observed)]))
        text += json.dumps(row)+"\n"
    path.write_text(text)
    return path, event


def test_frozen_supervisor_one_relay_with_post_signal_birth_enrichment(environment, monkeypatch):
    e = environment
    tx = transaction(e)
    add_proof(e, tx)
    add_original_supervisor_relay(e, tx)
    # The old supervisor has already exited; original enriched evidence remains.
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    proof = h._bind_supervisor_relay(e.root, tx)
    assert proof["sender_evidence"]["kind"] == "ORIGINAL_POST_SIGNAL_IDENTITY_ENRICHMENT"
    assert proof["sender_evidence"]["kernel_birth_claimed"] is False
    assert set(h._check_maintenance_signals(e.root, tx, final=True)) == {
        "controller", "supervisor_forwarded_controller_TERM"}


@pytest.mark.parametrize("wrong_birth", [False, True])
def test_supervisor_relay_gone_without_bound_birth_is_not_waived(environment, monkeypatch, wrong_birth):
    e = environment
    tx = transaction(e)
    add_proof(e, tx)
    add_original_supervisor_relay(e, tx, enrichment=wrong_birth, wrong_birth=wrong_birth)
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    with pytest.raises(h.HandoffError, match="SENDER_BIRTH_(UNPROVEN|CONTRADICTED)"):
        h._bind_supervisor_relay(e.root, tx)


def test_supervisor_second_relay_not_authorized(environment):
    e = environment
    tx = transaction(e)
    add_proof(e, tx)
    path, event = add_original_supervisor_relay(e, tx)
    path.write_text(path.read_text()+json.dumps(dict(event, receipt_id="extra-relay"))+"\n")
    with pytest.raises(h.HandoffError, match="MULTIPLE_SUPERVISOR"):
        h._bind_supervisor_relay(e.root, tx)


def test_supervisor_relay_before_our_primary_receipt_is_forbidden(environment):
    e = environment
    tx = transaction(e)
    with pytest.raises(h.HandoffError, match="REQUIRES_BOUND_PRIMARY"):
        h._bind_supervisor_relay(e.root, tx)


def test_exact_relay_waits_for_live_receivers_pending_enrichment(environment, monkeypatch):
    e = environment
    tx = transaction(e)
    add_proof(e, tx)
    path, event = add_original_supervisor_relay(e, tx, enrichment=False)
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=pid == 101))
    with pytest.raises(h.HandoffEvidencePending, match="WAITING_FOR_EXACT_RELAY"):
        h._bind_supervisor_relay(e.root, tx)
    assert not (e.root / "handoff/derived_supervisor_relay/record.json").exists()
    waits = []
    def append_enrichment(seconds):
        waits.append(seconds)
        observed = time.time()
        row = dict(schema="v58_received_signal_identity_enrichment.v1",
            receipt_id=event["receipt_id"], receipt_at_epoch=event["at_epoch"],
            observed_at_epoch=observed, pid=101, role="controller",
            kernel_receipt_fsynced_before_proc_reads=True, identities_are_post_signal_observations=True,
            sender_parent_chain=dict(processes=[dict(pid=102, birth="birth-102", ruid=1004, euid=1004,
                identity_consistent=True, observed_at_epoch=observed)]))
        path.write_text(path.read_text()+json.dumps(row)+"\n")
    monkeypatch.setattr(h.time, "sleep", append_enrichment)
    proof = h._await_supervisor_relay(e.root, tx)
    assert waits == [0.25] and proof["sender_evidence"]["kernel_birth_claimed"] is False
    assert not (e.root / "handoff/blocked/record.json").exists()


def test_all_generation_accepted_leaves_original_scoring_untouched(environment, monkeypatch):
    e = environment
    journal = mark_complete(e)
    h._write(e.source / "journal/state.json", dict(journal, evaluation_registered=True))
    monkeypatch.setattr(h, "_execute", lambda *a: pytest.fail("must not interrupt original finish/scoring"))
    result = h.advance_handoff(e.root)
    assert result["status"] == "NO_HANDOFF_REMAINING_WORK"
    assert not (e.old / "terminal/record.json").exists()
    assert not (e.root / "handoff/transaction/record.json").exists()
    # Once this final no-migration choice is persisted, later old completion
    # does not require live identities or retroactively attempt a takeover.
    monkeypatch.setattr(h, "_admission", lambda *a: pytest.fail("no-migration is already final"))
    assert h.advance_handoff(e.root)["status"] == "NO_HANDOFF_REMAINING_WORK"


def test_one_remaining_generation_may_reach_passive_window(environment):
    e = environment
    journal = mark_complete(e)
    states = dict(journal["job_states"], generation_pending={"status": "PENDING"})
    h._write(e.source / "journal/state.json", dict(journal,
        evaluation_registered=True, job_states=states))
    assert h._passive_check(e.binding) is None


def test_final_generation_race_is_rechecked_before_WAL(environment):
    e = environment
    journal = dict(mark_complete(e), evaluation_registered=True)
    assert h._execute(e.root, e.protocol, e.binding, journal, {})["status"] == "NO_HANDOFF_REMAINING_WORK"
    assert not (e.root / "handoff/transaction/record.json").exists()


def test_next_cron_after_natural_completion_can_report_no_migration(environment, monkeypatch):
    e = environment
    h._write(e.source / "closeout/record.json", dict(status="COMPLETE",
        protocol_id=h.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID))
    h._write(e.old / "terminal/record.json", dict(protocol_id=h.OLD_PROTOCOL_ID,
        status="COMPLETE_NO_FURTHER_RECOVERY", reason="COMPLETE"))
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    assert h.checked_binding(e.binding, allow_superseded=True) == e.binding
    assert h._passive_check(e.binding) == "COMPLETE_NO_MIGRATION"
    with pytest.raises(h.HandoffError, match="ALREADY_TERMINAL"):
        h.checked_binding(e.binding, allow_superseded=False)


def test_old_failure_terminal_cannot_be_relabelled_as_completion(environment):
    e = environment
    h._write(e.old / "terminal/record.json", dict(protocol_id=h.OLD_PROTOCOL_ID,
        status="BLOCKED_KNOWN_UNSAFE_EXIT", reason="KNOWN_EXIT_NOT_AUTHORIZED"))
    with pytest.raises(h.HandoffError, match="ALREADY_TERMINAL"):
        h.checked_binding(e.binding, allow_superseded=True)


def test_repeated_exact_validation_and_observer_retirement_are_allowed(environment, monkeypatch):
    e = environment
    tx = final_setup(e, monkeypatch)
    h._finalize(e.root, tx)
    journal = h.checked_record(e.source / "journal/state.json")
    observation = dict(episode_root=str(e.source), control_protocol_id=h.SOURCE_CONTROL_PROTOCOL_ID,
        identity_roster_complete=True, identities=[dict(pid=101, birth="birth-101", alive=False)],
        any_sigint_observed=False, unfiltered_unknown_stop_signal=False,
        known_hard_block=False, known_implementation_failure=False,
        journal_id=journal["id"], signal_logs=[])
    first = h.validate_authorized_stop(e.root, e.binding["source_episode"], observation)
    observer = e.source / "signals/observer-777/received.jsonl"
    observer.parent.mkdir(parents=True)
    observer.write_text(json.dumps(dict(role="observer", signal=15, receipt_id="own-monitor"))+"\n")
    assert h.validate_authorized_stop(e.root, e.binding["source_episode"], observation)["id"] == first["id"]


def test_V62_requires_completed_passive_V61_retirement_before_snapshot(environment, monkeypatch):
    e = environment
    def absent():
        raise FileNotFoundError("fixture retirement is not complete")
    monkeypatch.setattr(h.supersession, "checked_completed", absent)
    with pytest.raises(FileNotFoundError, match="not complete"):
        h.snapshot_binding()
    assert not (e.root / "handoff").exists()
    assert not (e.old / "terminal/record.json").exists()


def test_V62_bound_retirement_bytes_cannot_change(environment):
    e = environment
    path = Path(e.binding["retired_v61_guard"]["path"])
    h._write(path, dict(status="different-completion"))
    with pytest.raises(h.HandoffError, match="REFERENCE_CHANGED"):
        h.checked_binding(e.binding)


def test_V62_retirement_path_is_exact_not_same_bytes_elsewhere(environment):
    e = environment
    value = h.checked_record(e.binding["retired_v61_guard"]["path"])
    elsewhere = e.root / "copied-retirement/record.json"
    h._write(elsewhere, value)
    body = {key: item for key, item in e.binding.items() if key != "id"}
    body["retired_v61_guard"] = h._ref(elsewhere)
    changed = {**body, "id": h.digest(body)}
    with pytest.raises(h.HandoffError, match="RETIREMENT_RECEIPT_CHANGED"):
        h.checked_binding(changed)


def test_V62_retirement_proof_does_not_reactivate_old_V61_validation(environment, monkeypatch):
    e = environment
    h._write(e.old / "terminal/record.json", dict(schema="v62_old_watchdog_superseded.v1",
        protocol_id=h.OLD_PROTOCOL_ID, handoff_binding_id=e.binding["id"], successor_master=str(e.root)))
    monkeypatch.setattr(h, "_identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    assert h.checked_binding(e.binding, require_live=False, allow_superseded=True) == e.binding
    assert h.policy()["exact_prior_V61_passive_guard_retirement_required"] is True
    assert e.binding["source_episode"]["root"] == str(e.source)
