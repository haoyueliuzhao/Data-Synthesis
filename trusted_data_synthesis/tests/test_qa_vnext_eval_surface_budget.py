"""Third-purpose wallet controls use only synthetic temporary SQLite state."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.budget import ResearchLedger
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import budget
from trusted_synthesis.experiments.finance_qa_vnext_readiness_revision import budget_transition
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected

PRIOR = [
    {"id": "original_surface", "tokens": 211338},
    {"id": "original_increment", "tokens": 10200},
]


def wallet(tmp_path):
    old, path = tmp_path / "old.sqlite3", tmp_path / "owner.sqlite3"
    predecessor = ResearchLedger(old, "old-freeze", prior_debits=PRIOR)
    predecessor.register([], [])
    proof = budget_transition.inspect_predecessor(old, "old-freeze", PRIOR)
    budget_transition.migrate(old, path, "old-freeze", "owner-freeze", PRIOR, proof)
    legacy = ResearchLedger(path, "owner-freeze", prior_debits=PRIOR)
    bank = budget.EvaluationLedger(path, "owner-freeze", PRIOR, eval_freeze_id="evaluation-freeze")
    return bank, legacy


def registry(count=1):
    return [
        {
            "task_id": f"eval-{i}",
            "split": "dev" if i < 180 else "confirm",
            "identity": {
                "task_id": f"eval-{i}",
                "family": "composition_required",
                "surface_version_id": f"surface-{i}",
                "public_messages_sha256": "b" * 64,
                "parent_manifest_id": "original-panel",
            },
            "spec_sha256": "a" * 64,
        }
        for i in range(count)
    ]


def register(bank, count=1):
    return bank.register_evaluation(
        registry(count),
        policy_id="frozen-execution-policy",
        parent_panel_manifest_id="original-panel",
    )


def gate():
    return {
        "id": "gate",
        "status": "READY_FOR_FIXED_COLLECTION",
        **dict.fromkeys(
            (
                "panel_quota_complete",
                "actual_period_semantics_passed",
                "increment_source_semantics_passed",
                "new_original_CPU_representation_passed",
                "complete_trajectory_qualification_passed",
                "live_transport_controls_passed",
                "training_catalog_locked",
                "original_package_consumer_registered",
            ),
            True,
        ),
    }


def usage(p=5, c=2):
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def settle(bank, lease, *, used=None, success=True, model=budget.MODEL):
    bank.mark_evaluation_sent(lease["request_id"])
    return bank.settle_evaluation(
        lease["request_id"],
        usage=usage() if used is None else used,
        http_success=success,
        response_model=model,
        outcome="response_received",
    )


def test_no_fresh_wallet_or_old_retired_wallet_can_become_new_allowance(tmp_path):
    with pytest.raises(BudgetRejected, match="existing_wallet"):
        budget.EvaluationLedger(tmp_path / "missing.sqlite3", "owner", PRIOR, eval_freeze_id="eval")
    bank, _ = wallet(tmp_path)
    with pytest.raises(BudgetRejected, match="active_inherited"):
        budget.EvaluationLedger(
            tmp_path / "old.sqlite3", "old-freeze", PRIOR, eval_freeze_id="eval"
        )
    assert bank.snapshot()["cumulative_conservative_debit"] == 221538
    assert bank.snapshot()["eval_request_reservations"] == 0


def test_finalization_permanently_closes_unused_eval_attempts_not_other_purposes(tmp_path):
    bank, legacy = wallet(tmp_path)
    register(bank, 900)
    legacy.register(["UNP-0"], [])
    legacy.register_collection(
        [{"task_id": "train", "family": "control"}], gate_id="gate", gate=gate()
    )
    lease = bank.reserve_evaluation("eval-0")
    bank.mark_evaluation_sent(lease["request_id"])
    bank.settle_evaluation(lease["request_id"], outcome="ordinary_timeout")
    value = bank.finalize_evaluation(
        "complete-public-catalog", [row["task_id"] for row in registry(900)]
    )
    assert value["completed_task_count"] == 900 and value["terminal_unknown_count"] == 1
    assert value["retained_conservative_debit"] == 9728
    assert bank.snapshot()["evaluation_finalization"] == value
    assert bank.evaluation_snapshot()["evaluation_finalization"] == value
    with pytest.raises(BudgetRejected, match="finalized"):
        bank.reserve_evaluation("eval-1")
    legacy.reserve("UNP-0")
    legacy.reserve_teacher(legacy.sessions()[0]["session_id"])
    reopened = budget.EvaluationLedger(
        bank.path, "owner-freeze", PRIOR, eval_freeze_id="evaluation-freeze"
    )
    with pytest.raises(BudgetRejected, match="finalized"):
        reopened.reserve_evaluation("eval-1")
    with pytest.raises(BudgetRejected, match="single_evaluation_finalization"):
        reopened.finalize_evaluation("different-catalog", value["outcome_task_ids"])


@pytest.mark.parametrize("defect", ["missing", "duplicate", "wrong", "reserved", "sent"])
def test_finalization_rejects_partial_or_fabricated_sets_and_open_leases(tmp_path, defect):
    bank, _ = wallet(tmp_path)
    register(bank, 900)
    task_ids = [row["task_id"] for row in registry(900)]
    if defect == "missing":
        task_ids.pop()
    elif defect == "duplicate":
        task_ids[-1] = task_ids[0]
    elif defect == "wrong":
        task_ids[-1] = "not-original"
    elif defect in {"reserved", "sent"}:
        lease = bank.reserve_evaluation("eval-0")
        if defect == "sent":
            bank.mark_evaluation_sent(lease["request_id"])
    with pytest.raises(BudgetRejected):
        bank.finalize_evaluation("catalog", task_ids)
    assert bank.snapshot()["evaluation_finalization"] is None


def test_finalization_record_cannot_be_removed_or_rebound(tmp_path):
    bank, _ = wallet(tmp_path)
    register(bank, 900)
    bank.finalize_evaluation("catalog", [row["task_id"] for row in registry(900)])
    with bank.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM metadata WHERE key=?", (budget.FINALIZATION_KEY,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE metadata SET value='other' WHERE key=?", (budget.FINALIZATION_KEY,))


def test_registry_is_separate_and_keeps_all_four_old_triggers_and_policy(tmp_path):
    bank, legacy = wallet(tmp_path)
    with legacy.connection() as db:
        before = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        original = dict(
            db.execute("SELECT key,value FROM metadata WHERE key IN ('policy','cumulative_policy')")
        )
    registered = register(bank, 900)
    assert registered["registered_task_count"] == 900
    assert bank.policy["request_cap"] == 34 and bank.policy["token_cap"] == 330752
    with legacy.connection() as db:
        after = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        assert all(after[name] == sql for name, sql in before.items())
        assert (
            dict(
                db.execute(
                    "SELECT key,value FROM metadata WHERE key IN ('policy','cumulative_policy')"
                )
            )
            == original
        )
        assert db.execute("SELECT COUNT(*) FROM registered_tasks").fetchone()[0] == 0
    with pytest.raises(BudgetRejected, match="17"):
        bank.register([f"not-evaluation-{i}" for i in range(18)], [])


@pytest.mark.parametrize(
    "mutation", ["901", "duplicate", "private_identity", "wrong_parent", "train", "wrong_spec"]
)
def test_bad_registry_never_installs_partial_purpose(tmp_path, mutation):
    bank, _ = wallet(tmp_path)
    rows = registry(901 if mutation == "901" else 2)
    if mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "private_identity":
        rows[0]["identity"]["private_answer"] = "never accepted"
    elif mutation == "wrong_parent":
        rows[0]["identity"]["parent_manifest_id"] = "wrong"
    elif mutation == "train":
        rows[0]["split"] = "train"
    elif mutation == "wrong_spec":
        rows[0]["spec_sha256"] = "wrong"
    with pytest.raises(BudgetRejected):
        bank.register_evaluation(
            rows, policy_id="policy", parent_panel_manifest_id="original-panel"
        )
    assert bank.snapshot()["registered_purpose_count"] == 2


def test_freeze_and_single_registration_precede_all_evaluation_attempts(tmp_path):
    bank, _ = wallet(tmp_path)
    with pytest.raises(BudgetRejected, match="purpose_not_frozen"):
        bank.reserve_evaluation("eval-0")
    register(bank)
    with pytest.raises(BudgetRejected, match="single_evaluation_registration"):
        register(bank)
    with pytest.raises(BudgetRejected, match="frozen_evaluation"):
        budget.EvaluationLedger(bank.path, "owner-freeze", PRIOR, eval_freeze_id="other-freeze")
    with pytest.raises(BudgetRejected, match="registered_evaluation"):
        bank.reserve_evaluation("UNP-training-task")


def test_initial_then_one_repair_and_exact_1800_request_and_token_caps(tmp_path):
    bank, _ = wallet(tmp_path)
    register(bank, 900)
    for i in range(900):
        first = bank.reserve_evaluation(f"eval-{i}")
        settle(bank, first, used=usage(8192, 1536))
        second = bank.reserve_evaluation(f"eval-{i}", repair=True)
        settle(bank, second, used=usage(8192, 1536))
    snapshot = bank.snapshot()
    assert snapshot["eval_request_reservations"] == 1800
    assert snapshot["eval_conservative_charged_tokens"] == 17_510_400
    assert snapshot["cumulative_conservative_debit"] == 221538 + 17_510_400
    with pytest.raises(BudgetRejected, match="one_contract_repair"):
        bank.reserve_evaluation("eval-0", repair=True)


def test_unknown_transport_holds_lease_and_blocks_same_task_retry_not_other_tasks(tmp_path):
    bank, _ = wallet(tmp_path)
    register(bank, 2)
    lease = bank.reserve_evaluation("eval-0")
    bank.mark_evaluation_sent(lease["request_id"])
    result = bank.settle_evaluation(
        lease["request_id"], usage=None, http_success=False, response_model=None, outcome="timeout"
    )
    assert result["state"] == "usage_unknown" and result["charged_tokens"] == 9728
    assert result["study_fatal"] is None
    with pytest.raises(BudgetRejected, match="no_transport"):
        bank.reserve_evaluation("eval-0", repair=True)
    bank.reserve_evaluation("eval-1")
    assert bank.snapshot()["eval_conservative_charged_tokens"] == 19456


@pytest.mark.parametrize(
    "bad_usage,bad_model",
    [
        (None, budget.MODEL),
        (usage(), "wrong-model"),
        ({"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 8}, budget.MODEL),
        ({"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3}, budget.MODEL),
    ],
)
def test_any_complete_HTTP_model_or_billing_defect_persistently_stops_other_purposes(
    tmp_path, bad_usage, bad_model
):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    register(bank, 2)
    lease = bank.reserve_evaluation("eval-0")
    bank.mark_evaluation_sent(lease["request_id"])
    result = bank.settle_evaluation(
        lease["request_id"],
        usage=bad_usage,
        http_success=True,
        response_model=bad_model,
        outcome="response_received",
    )
    assert result["study_fatal"]
    with pytest.raises(BudgetRejected):
        legacy.reserve("UNP-0")
    with pytest.raises(BudgetRejected):
        bank.reserve_evaluation("eval-1")


def test_actual_overrun_is_committed_not_rolled_back_and_sent_tail_can_settle(tmp_path):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    register(bank, 2)
    tail = legacy.reserve("UNP-0")
    legacy.mark_sent(tail["request_id"])
    lease = bank.reserve_evaluation("eval-0")
    result = settle(bank, lease, used=usage(9000, 1600))
    assert result["budget_breach"] and result["charged_tokens"] == 10600 and result["study_fatal"]
    legacy.settle(
        tail["request_id"],
        usage=usage(10, 2),
        http_success=True,
        response_model=budget.MODEL,
        outcome="response_received",
    )
    assert bank.snapshot()["cumulative_conservative_debit"] == 221538 + 10600 + 12


def test_stale_UNP_and_Teacher_senders_respect_new_persistent_fatal(tmp_path):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    legacy.register_collection(
        [{"task_id": "train", "family": "control"}], gate_id="gate", gate=gate()
    )
    register(bank)
    unp = legacy.reserve("UNP-0")
    teacher = legacy.reserve_teacher(legacy.sessions()[0]["session_id"])
    bank.halt("cross-purpose-stop")
    with pytest.raises(BudgetRejected):
        legacy.mark_sent(unp["request_id"])
    with pytest.raises(BudgetRejected):
        legacy.mark_teacher_sent(teacher["request_id"])


def test_old_client_settlement_failure_also_stops_evaluation(tmp_path):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    register(bank)
    lease = legacy.reserve("UNP-0")
    legacy.mark_sent(lease["request_id"])
    legacy.settle(
        lease["request_id"],
        usage=None,
        http_success=True,
        response_model=budget.MODEL,
        outcome="missing_billing",
    )
    assert bank.snapshot()["persisted_study_stop"]
    with pytest.raises(BudgetRejected):
        bank.reserve_evaluation("eval-0")


def test_three_purpose_concurrent_reservations_cannot_exceed_single_remaining_small_lease(tmp_path):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    legacy.register_collection(
        [{"task_id": "train", "family": "control"}], gate_id="gate", gate=gate()
    )
    # This is deliberately synthetic historical aggregate cost, not a generated
    # Teacher observation or a claimed legal one-request token measurement.
    with legacy.connection() as db:
        db.execute(
            "INSERT INTO teacher_reservations (request_id,session_id,attempt,state,"
            "reserved_tokens,charged_tokens,created_at) "
            "VALUES ('synthetic-history','synthetic-history',1,'settled',115712,?,'mock')",
            (budget.GLOBAL_CAP - 221538 - budget.RESERVATION,),
        )
    register(bank)
    barrier = threading.Barrier(3)
    operations = [
        lambda: bank.reserve_evaluation("eval-0"),
        lambda: legacy.reserve("UNP-0"),
        lambda: legacy.reserve_teacher(legacy.sessions()[0]["session_id"]),
    ]

    def execute(operation):
        barrier.wait()
        try:
            operation()
            return True
        except BudgetRejected:
            return False

    with ThreadPoolExecutor(max_workers=3) as pool:
        successes = list(pool.map(execute, operations))
    assert sum(successes) == 1
    assert bank.snapshot()["cumulative_conservative_debit"] == budget.GLOBAL_CAP


def test_global_snapshot_is_single_transaction_and_does_not_double_count_prior(tmp_path):
    bank, legacy = wallet(tmp_path)
    legacy.register(["UNP-0"], [])
    register(bank)
    unp = legacy.reserve("UNP-0")
    legacy.mark_sent(unp["request_id"])
    legacy.settle(
        unp["request_id"],
        usage=usage(10, 3),
        http_success=True,
        response_model=budget.MODEL,
        outcome="response_received",
    )
    settle(bank, bank.reserve_evaluation("eval-0"), used=usage(11, 4))
    report = bank.snapshot()
    assert report["reservations"][0]["task_id"] == "UNP-0"
    assert report["eval_reservations"][0]["task_id"] == "eval-0"
    assert report["cumulative_conservative_debit"] == 221538 + 13 + 15
    assert report["snapshot_single_read_transaction"] and report["prior_debit_counted_once"]


def test_registry_policy_and_terminal_cost_cannot_be_deleted_or_rewritten(tmp_path):
    bank, _ = wallet(tmp_path)
    register(bank)
    settle(bank, bank.reserve_evaluation("eval-0"))
    with bank.connection() as db:
        for sql in (
            "DELETE FROM eval_reservations",
            "UPDATE eval_reservations SET charged_tokens=0",
            "UPDATE eval_registry SET spec_sha256='changed'",
            "DELETE FROM metadata WHERE key='eval_surface_rewrite_policy'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
