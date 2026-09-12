"""Transactional, persistent request/token reservations for question rewriting only."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REQUEST_CAP = 520
TOKEN_CAP = 2_000_000
INPUT_RESERVATION = 8192
OUTPUT_CAP = 1536
COMMON_NEW_EXPERIMENT_CAP = 1_000_000_000


class BudgetRejected(RuntimeError):
    pass


class Ledger:
    def __init__(self, path, stage_id, *, request_cap=REQUEST_CAP, token_cap=TOKEN_CAP):
        self.path, self.stage_id = Path(path), stage_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = {
            "stage_id": stage_id,
            "purpose": "question_rewrite",
            "request_cap": request_cap,
            "token_cap": token_cap,
            "per_task_cap": 2,
            "input_reservation": INPUT_RESERVATION,
            "output_cap": OUTPUT_CAP,
            "common_new_experiment_cap": COMMON_NEW_EXPERIMENT_CAP,
            "Teacher_enabled": False,
            "Student_enabled": False,
        }
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            db.execute("""CREATE TABLE IF NOT EXISTS reservations (
                request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                reason TEXT NOT NULL, state TEXT NOT NULL, reserved_tokens INTEGER NOT NULL,
                prompt_tokens INTEGER, completion_tokens INTEGER, charged_tokens INTEGER NOT NULL,
                http_success INTEGER, response_model TEXT, outcome TEXT, created_at TEXT NOT NULL,
                UNIQUE(task_id, attempt))""")
            policy = json.dumps(self.policy, sort_keys=True)
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('policy', ?)", (policy,))
            if db.execute("SELECT value FROM metadata WHERE key='policy'").fetchone()[0] != policy:
                raise BudgetRejected("ledger.policy_identity_mismatch")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def reserve(self, task_id, *, repair=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                rows = db.execute(
                    "SELECT * FROM reservations WHERE task_id=? ORDER BY attempt", (task_id,)
                ).fetchall()
                if len(rows) >= 2 or bool(rows) != repair:
                    raise BudgetRejected("ledger.per_task_initial_or_repair_contract")
                if rows and (rows[-1]["state"] != "settled" or rows[-1]["http_success"] != 1):
                    raise BudgetRejected("ledger.no_transport_retry_or_inflight_replay")
                if rows and rows[-1]["outcome"] not in {
                    "response_received",
                    "rewrite_structure_failure",
                }:
                    raise BudgetRejected("ledger.repair_requires_returned_contract_candidate")
                if db.execute("SELECT 1 FROM reservations WHERE state='budget_breach'").fetchone():
                    raise BudgetRejected("ledger.previous_usage_exceeded_reservation")
                total = db.execute(
                    "SELECT COUNT(*) AS n, COALESCE(SUM(charged_tokens),0) AS tokens "
                    "FROM reservations"
                ).fetchone()
                reserved = INPUT_RESERVATION + OUTPUT_CAP
                if (
                    total["n"] >= self.policy["request_cap"]
                    or total["tokens"] + reserved > self.policy["token_cap"]
                ):
                    raise BudgetRejected("ledger.global_request_or_token_cap")
                attempt = len(rows) + 1
                identity = json.dumps([self.stage_id, task_id, attempt], separators=(",", ":"))
                identifier = "rewrite_request_" + hashlib.sha256(identity.encode()).hexdigest()
                db.execute(
                    "INSERT INTO reservations "
                    "(request_id,task_id,attempt,reason,state,reserved_tokens,charged_tokens,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        task_id,
                        attempt,
                        "contract_repair" if repair else "initial",
                        "reserved",
                        reserved,
                        reserved,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                db.execute("COMMIT")
                return {
                    "request_id": identifier,
                    "task_id": task_id,
                    "attempt": attempt,
                    "input_reservation": INPUT_RESERVATION,
                    "output_cap": OUTPUT_CAP,
                    "reserved_tokens": reserved,
                }
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def mark_sent(self, request_id):
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE reservations SET state='sent' WHERE request_id=? AND state='reserved'",
                (request_id,),
            )
            if cursor.rowcount != 1:
                raise BudgetRejected("ledger.request_may_be_sent_only_once")

    def settle(self, request_id, *, usage=None, http_success=False, response_model=None, outcome):
        prompt = completion = None
        if isinstance(usage, dict):
            prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
            valid = all(type(value) is int and value >= 0 for value in (prompt, completion))
            if not valid:
                prompt = completion = None
        known = prompt is not None
        breach = known and (prompt > INPUT_RESERVATION or completion > OUTPUT_CAP)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM reservations WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None or row["state"] != "sent":
                db.execute("ROLLBACK")
                raise BudgetRejected("ledger.exactly_one_settlement_after_send")
            charged = prompt + completion if known else row["reserved_tokens"]
            db.execute(
                "UPDATE reservations SET state=?,prompt_tokens=?,completion_tokens=?,"
                "charged_tokens=?,http_success=?,response_model=?,outcome=? WHERE request_id=?",
                (
                    "budget_breach" if breach else "settled" if known else "usage_unknown",
                    prompt,
                    completion,
                    charged,
                    int(http_success),
                    response_model,
                    outcome,
                    request_id,
                ),
            )
            db.execute("COMMIT")
        return known and not breach

    def snapshot(self):
        with self.connection() as db:
            rows = [
                dict(row)
                for row in db.execute("SELECT * FROM reservations ORDER BY task_id,attempt")
            ]
        return {
            "policy": self.policy,
            "reservations": rows,
            "request_reservations": len(rows),
            "sent_request_count": sum(row["state"] != "reserved" for row in rows),
            "known_prompt_tokens": sum(row["prompt_tokens"] or 0 for row in rows),
            "known_completion_tokens": sum(row["completion_tokens"] or 0 for row in rows),
            "conservative_charged_tokens": sum(row["charged_tokens"] for row in rows),
            "budget_breach_count": sum(row["state"] == "budget_breach" for row in rows),
            "http_success_count": sum(row["http_success"] == 1 for row in rows),
            "unsettled_or_unknown_count": sum(row["state"] != "settled" for row in rows),
            "inflight_reservations_are_not_reclaimed": True,
        }
