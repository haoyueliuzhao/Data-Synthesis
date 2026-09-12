"""Reuse the proven rewrite ledger, with registered increments and historical debit."""

import json
import sqlite3

from ..finance_qa_vnext_surface_build.budget import BudgetRejected, Ledger

REQUEST_CAP = 54
TOKEN_CAP = 525_312
GLOBAL_CAP = 1_000_000_000


class IncrementLedger(Ledger):
    def __init__(
        self,
        path,
        stage_id,
        *,
        prior_debits,
        global_cap=GLOBAL_CAP,
        request_cap=REQUEST_CAP,
        token_cap=TOKEN_CAP,
    ):
        if type(global_cap) is not int or global_cap <= 0:
            raise BudgetRejected("increment.exact_positive_global_cap")
        if len(prior_debits) != len({item["id"] for item in prior_debits}):
            raise BudgetRejected("increment.unique_prior_debit_ids")
        super().__init__(path, stage_id, request_cap=request_cap, token_cap=token_cap)
        value = {
            "global_cap": global_cap,
            "prior_debits": prior_debits,
            "scope": "same approximately-200-task utility allowance, not a new billion",
        }
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS registered_tasks (task_id TEXT PRIMARY KEY)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS prior_debits "
                "(debit_id TEXT PRIMARY KEY, tokens INTEGER NOT NULL)"
            )
            text = json.dumps(value, sort_keys=True)
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('cumulative_policy',?)", (text,))
            if (
                db.execute("SELECT value FROM metadata WHERE key='cumulative_policy'").fetchone()[0]
                != text
            ):
                raise BudgetRejected("increment.cumulative_policy_identity")
            for item in prior_debits:
                if type(item["tokens"]) is not int or item["tokens"] < 0:
                    raise BudgetRejected("increment.exact_nonnegative_prior_debit")
                db.execute(
                    "INSERT OR IGNORE INTO prior_debits VALUES (?,?)", (item["id"], item["tokens"])
                )
            db.execute("""CREATE TRIGGER IF NOT EXISTS registered_increment_only
                BEFORE INSERT ON reservations BEGIN
                SELECT CASE WHEN NOT EXISTS
                    (SELECT 1 FROM registered_tasks WHERE task_id=NEW.task_id)
                    THEN RAISE(ABORT,'increment.unregistered_or_old_task') END;
                END""")
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS cumulative_budget_before_reserve
                BEFORE INSERT ON reservations BEGIN
                SELECT CASE WHEN NEW.charged_tokens
                    + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
                    + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {int(global_cap)}
                    THEN RAISE(ABORT,'increment.cumulative_budget_exhausted') END;
                END""")
        self.cumulative_policy = value

    def register(self, new_task_ids, old_task_ids):
        values = list(new_task_ids)
        if len(values) != len(set(values)) or len(values) > 27 or set(values) & set(old_task_ids):
            raise BudgetRejected("increment.only_up_to_27_genuinely_new_tasks")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]:
                    raise BudgetRejected("increment.registration_before_requests")
                if db.execute("SELECT 1 FROM metadata WHERE key='task_registry'").fetchone():
                    raise BudgetRejected("increment.single_task_registration")
                db.executemany(
                    "INSERT INTO registered_tasks VALUES (?)", [(item,) for item in values]
                )
                db.execute(
                    "INSERT INTO metadata VALUES ('task_registry',?)", (json.dumps(sorted(values)),)
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def reserve(self, task_id, *, repair=False):
        try:
            return super().reserve(task_id, repair=repair)
        except sqlite3.IntegrityError as error:
            raise BudgetRejected(str(error)) from error

    def snapshot(self):
        result = super().snapshot()
        with self.connection() as db:
            prior = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
        charged = prior + result["conservative_charged_tokens"]
        return {
            **result,
            "cumulative_policy": self.cumulative_policy,
            "previous_registered_debit": prior,
            "cumulative_conservative_debit": charged,
            "remaining_registered_global_allowance": self.cumulative_policy["global_cap"] - charged,
            "Teacher_requests_allowed_in_this_stage": 0,
        }
