"""Temporary SQLite only: never inspect, stop, or migrate a production ledger."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.budget import ResearchLedger
from trusted_synthesis.experiments.finance_qa_vnext_readiness_revision import (
    budget_transition as move,
)
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected

PRIOR = [{"id": "old_surface", "tokens": 211338}, {"id": "old_increment", "tokens": 10200}]
FLAGS = (
    "panel_quota_complete",
    "actual_period_semantics_passed",
    "increment_source_semantics_passed",
    "new_original_CPU_representation_passed",
    "complete_trajectory_qualification_passed",
    "live_transport_controls_passed",
    "training_catalog_locked",
    "original_package_consumer_registered",
)


def gate():
    return {"id": "gate", "status": "READY_FOR_FIXED_COLLECTION", **dict.fromkeys(FLAGS, True)}


def seed(tmp_path, *, register_empty=True):
    path = tmp_path / "old.sqlite3"
    bank = ResearchLedger(path, "old-freeze", prior_debits=PRIOR)
    if register_empty:
        bank.register([], ["old-public-task"])
    return path, tmp_path / "new.sqlite3", bank


def transition(tmp_path):
    old, new, stale = seed(tmp_path)
    inspected = move.inspect_predecessor(old, "old-freeze", PRIOR)
    receipt = move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, inspected)
    return old, new, stale, inspected, receipt


def test_predecessor_inspection_is_read_only_and_preserves_empty_registration(tmp_path):
    old, _, _ = seed(tmp_path)
    before = old.read_bytes()
    files = sorted(path.name for path in tmp_path.iterdir())
    inspected = move.inspect_predecessor(old, "old-freeze", PRIOR)
    assert old.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == files
    assert inspected["prior_global_debit"] == 221538
    assert inspected["rewrite_requests"] == inspected["Teacher_registered_sessions"] == 0
    assert move._metadata(inspected["state"])["task_registry"] == "[]"


def test_successful_handoff_inherits_exact_prior_once_and_continues_same_subcaps(tmp_path):
    old, new, stale, _, receipt = transition(tmp_path)
    bank = ResearchLedger(new, "new-freeze", prior_debits=PRIOR)
    before = bank.snapshot()
    assert before["cumulative_conservative_debit"] == 221538
    assert before["remaining_registered_global_allowance"] == 999778462
    assert before["policy"]["request_cap"] == 34
    assert before["policy"]["token_cap"] == 330752
    assert bank.sessions() == []
    bank.register(["new-task"], ["old-public-task"])
    request = bank.reserve("new-task")
    bank.mark_sent(request["request_id"])
    bank.settle(
        request["request_id"],
        usage={"prompt_tokens": 8, "completion_tokens": 2},
        http_success=True,
        response_model="mock",
        outcome="response_received",
    )
    checked = move.check_transition(old, new, receipt, "new-freeze", PRIOR)
    assert checked["successor_rewrite_requests"] == 1
    assert bank.snapshot()["cumulative_conservative_debit"] == 221548
    assert stale.snapshot()["request_reservations"] == 0
    assert stale.snapshot()["persisted_study_stop"].startswith("transition_retired:")


@pytest.mark.parametrize(
    "operation",
    ["register", "register_collection", "reserve", "send", "teacher_reserve", "teacher_send"],
)
def test_stale_old_instances_cannot_register_reserve_or_send_after_transfer(tmp_path, operation):
    old, new, stale, _, receipt = transition(tmp_path)
    calls = {
        "register": lambda: stale.register(["old-reopened"], []),
        "register_collection": lambda: stale.register_collection(
            [{"task_id": "task", "family": "control"}], gate_id="gate", gate=gate()
        ),
        "reserve": lambda: stale.reserve("not-registered"),
        "send": lambda: stale.mark_sent("missing-request"),
        "teacher_reserve": lambda: stale.reserve_teacher("missing-session"),
        "teacher_send": lambda: stale.mark_teacher_sent("missing-request"),
    }
    with pytest.raises((BudgetRejected, sqlite3.IntegrityError)):
        calls[operation]()
    assert move.check_transition(old, new, receipt, "new-freeze", PRIOR)["predecessor_retired"]


def test_parent_history_and_retirement_metadata_are_immutable(tmp_path):
    old, new, stale, _, receipt = transition(tmp_path)
    with stale.connection() as db:
        for statement in (
            "DELETE FROM metadata WHERE key='study_fatal'",
            "UPDATE metadata SET value='[]' WHERE key='cumulative_policy'",
            "INSERT INTO registered_tasks VALUES ('old-task')",
            "DELETE FROM prior_debits",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="revision_retired"):
                db.execute(statement)
    assert move.check_transition(old, new, receipt, "new-freeze", PRIOR)["predecessor_retired"]


@pytest.mark.parametrize(
    "kind",
    ["registered_task", "reserved", "sent", "unknown", "settled", "Teacher_registry", "fatal"],
)
def test_any_prior_activity_or_unknown_charge_blocks_migration_without_erasing_state(
    tmp_path, kind
):
    old, new, bank = seed(tmp_path, register_empty=False)
    if kind in {"registered_task", "reserved", "sent", "unknown", "settled"}:
        bank.register(["task"], [])
        if kind != "registered_task":
            lease = bank.reserve("task")
            if kind != "reserved":
                bank.mark_sent(lease["request_id"])
                if kind in {"unknown", "settled"}:
                    bank.settle(
                        lease["request_id"],
                        usage=None
                        if kind == "unknown"
                        else {"prompt_tokens": 3, "completion_tokens": 1},
                        http_success=True,
                        outcome="response_received",
                    )
    elif kind == "Teacher_registry":
        bank.register_collection(
            [{"task_id": "task", "family": "control"}], gate_id="gate", gate=gate()
        )
    else:
        bank.halt("original-global-stop")
    before = old.read_bytes()
    with pytest.raises(move.TransitionRejected):
        move.inspect_predecessor(old, "old-freeze", PRIOR)
    assert old.read_bytes() == before and not new.exists()


def test_active_WAL_is_not_ignored_by_immutable_inspection(tmp_path):
    old, _, bank = seed(tmp_path, register_empty=False)
    with bank.connection() as db:
        db.execute("INSERT INTO registered_tasks VALUES ('still-open-writer')")
        assert old.with_name(old.name + "-wal").stat().st_size > 0
        with pytest.raises(move.TransitionRejected, match="active_journal"):
            move.inspect_predecessor(old, "old-freeze", PRIOR)


def test_mismatched_or_double_counted_prior_debit_is_rejected(tmp_path):
    old, _, _ = seed(tmp_path)
    for prior in (
        PRIOR + [{"id": "copied_total", "tokens": 221538}],
        list(reversed(PRIOR)),
        [PRIOR[0], PRIOR[0]],
    ):
        with pytest.raises(move.TransitionRejected):
            move.inspect_predecessor(old, "old-freeze", prior)


def test_existing_successor_is_not_overwritten_and_old_remains_live(tmp_path):
    old, new, bank = seed(tmp_path)
    proof = move.inspect_predecessor(old, "old-freeze", PRIOR)
    new.write_bytes(b"user-owned-existing-database")
    with pytest.raises(move.TransitionRejected, match="exclusive"):
        move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)
    assert new.read_bytes() == b"user-owned-existing-database"
    assert bank.snapshot()["persisted_study_stop"] is None


def test_repeated_transfer_never_regrants_allowance(tmp_path):
    old, new, _, proof, receipt = transition(tmp_path)
    with pytest.raises(move.TransitionRejected):
        move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)
    with pytest.raises(move.TransitionRejected):
        move.migrate(old, tmp_path / "third.sqlite3", "old-freeze", "third-freeze", PRIOR, proof)
    assert (
        move.check_transition(old, new, receipt, "new-freeze", PRIOR)["grants_new_allowance"]
        is False
    )


def test_failure_after_retirement_keeps_old_closed_and_no_second_allowance(tmp_path, monkeypatch):
    old, new, stale = seed(tmp_path)
    proof = move.inspect_predecessor(old, "old-freeze", PRIOR)

    def fail(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(move, "_seed_quarantined", fail)
    with pytest.raises(OSError, match="simulated"):
        move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)
    assert stale.snapshot()["persisted_study_stop"]
    assert not new.exists()
    with pytest.raises(move.TransitionRejected):
        move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)


def test_failure_before_activation_leaves_visible_successor_quarantined(tmp_path, monkeypatch):
    old, new, stale = seed(tmp_path)
    proof = move.inspect_predecessor(old, "old-freeze", PRIOR)
    monkeypatch.setattr(
        move, "_activate", lambda *args: (_ for _ in ()).throw(OSError("crash before activation"))
    )
    with pytest.raises(OSError, match="activation"):
        move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)
    assert stale.snapshot()["persisted_study_stop"] and new.exists()
    with pytest.raises(sqlite3.IntegrityError, match="revision_quarantine"):
        ResearchLedger(new, "new-freeze", prior_debits=PRIOR)


def test_two_concurrent_transfers_can_publish_only_one_owner(tmp_path):
    old, new, _ = seed(tmp_path)
    proof = move.inspect_predecessor(old, "old-freeze", PRIOR)
    start = threading.Barrier(2)

    def run():
        start.wait()
        try:
            return move.migrate(old, new, "old-freeze", "new-freeze", PRIOR, proof)
        except (move.TransitionRejected, sqlite3.Error):
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: run(), range(2)))
    winners = [item for item in outcomes if item is not None]
    assert len(winners) == 1
    assert move.check_transition(old, new, winners[0], "new-freeze", PRIOR)["predecessor_retired"]


def test_successor_progress_halt_and_additive_authorized_purpose_tables_remain_verifiable(tmp_path):
    old, new, _, _, receipt = transition(tmp_path)
    bank = ResearchLedger(new, "new-freeze", prior_debits=PRIOR)
    bank.register(["new-task"], [])
    bank.reserve("new-task")
    bank.register_collection(
        [{"task_id": "old-task", "family": "control"}], gate_id="gate", gate=gate()
    )
    bank.reserve_teacher(bank.sessions()[0]["session_id"])
    with bank.connection() as db:
        db.execute("CREATE TABLE evaluation_rewrite_reserved (request_id TEXT PRIMARY KEY)")
        db.execute(
            "INSERT INTO metadata VALUES "
            "('future_authorized_purpose_policy','same shared allowance')"
        )
    bank.halt("later-observed-model-contract-stop")
    checked = move.check_transition(old, new, receipt, "new-freeze", PRIOR)
    assert checked["successor_rewrite_requests"] == checked["successor_Teacher_requests"] == 1
    assert checked["successor_study_halted"] and checked["additional_purpose_tables_allowed"]


def test_owner_and_prior_metadata_cannot_be_replaced(tmp_path):
    old, new, _, _, receipt = transition(tmp_path)
    bank = ResearchLedger(new, "new-freeze", prior_debits=PRIOR)
    with bank.connection() as db:
        for sql in (
            "UPDATE prior_debits SET tokens=0",
            "DELETE FROM prior_debits",
            "INSERT INTO prior_debits VALUES ('credit',-221538)",
            "DELETE FROM metadata WHERE key='readiness_budget_transition_role'",
            "UPDATE metadata SET value='wrong' WHERE key='policy'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    assert (
        move.check_transition(old, new, receipt, "new-freeze", PRIOR)["inherited_prior_debit"]
        == 221538
    )


def test_unrecognized_predecessor_purpose_or_modified_budget_trigger_is_not_copied(tmp_path):
    old, _, bank = seed(tmp_path)
    with bank.connection() as db:
        db.execute("DROP TRIGGER all_purposes_before_teacher")
        db.execute(
            "CREATE TRIGGER all_purposes_before_teacher BEFORE INSERT "
            "ON teacher_reservations BEGIN SELECT 1; END"
        )
    with pytest.raises(move.TransitionRejected, match="persistent_trigger"):
        move.inspect_predecessor(old, "old-freeze", PRIOR)


def test_path_symlinks_and_other_transition_id_are_rejected(tmp_path):
    old, new, _, _, receipt = transition(tmp_path)
    link = tmp_path / "old-link.sqlite3"
    link.symlink_to(old)
    with pytest.raises(move.TransitionRejected, match="symlink"):
        move.check_transition(link, new, receipt, "new-freeze", PRIOR)
    with pytest.raises(move.TransitionRejected, match="exact_transition"):
        move.check_transition(old, new, receipt, "other-freeze", PRIOR)
