"""Extend the proven rewrite ledger with the SAME atomic cross-purpose allowance.

No in-flight or unknown charge is reclaimed. Formal sessions must all be fixed
before the first Teacher request, and cannot be opened before an admission gate.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from ..finance_qa_vnext_catalog_bridge.budget import IncrementLedger
from ..finance_qa_vnext_surface_build.budget import BudgetRejected

INPUT_ALLOWANCE = 99_328
OUTPUT_ALLOWANCE = 16_384
TEACHER_RESERVATION = INPUT_ALLOWANCE + OUTPUT_ALLOWANCE
NEW_TASK_CAP = 17
REWRITE_REQUEST_CAP = 34
REWRITE_TOKEN_CAP = 330_752
GLOBAL_CAP = 1_000_000_000


class ResearchLedger(IncrementLedger):
    def __init__(self, path, stage_id, *, prior_debits, global_cap=GLOBAL_CAP):
        super().__init__(
            path,
            stage_id,
            prior_debits=prior_debits,
            global_cap=global_cap,
            request_cap=REWRITE_REQUEST_CAP,
            token_cap=REWRITE_TOKEN_CAP,
        )
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS collection_sessions (
                session_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, pool TEXT NOT NULL,
                basis TEXT NOT NULL, replicate INTEGER NOT NULL, state TEXT NOT NULL,
                terminal TEXT, UNIQUE(task_id,pool,basis,replicate))""")
            db.execute("""CREATE TABLE IF NOT EXISTS teacher_reservations (
                request_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                state TEXT NOT NULL, reserved_tokens INTEGER NOT NULL,
                charged_tokens INTEGER NOT NULL,
                prompt_tokens INTEGER, completion_tokens INTEGER, http_success INTEGER,
                response_model TEXT, outcome TEXT, created_at TEXT NOT NULL,
                UNIQUE(session_id,attempt))""")
            # Parent trigger still protects the rewrite-only cap. This additional
            # trigger checks both consumers in the SAME SQLite transaction.
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS all_purposes_before_rewrite
                BEFORE INSERT ON reservations BEGIN
                SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
                THEN RAISE(ABORT,'research.persisted_study_stop') END;
                SELECT CASE WHEN EXISTS
                  (SELECT 1 FROM teacher_reservations WHERE state='budget_breach')
                THEN RAISE(ABORT,'research.prior_reservation_breach') END;
                SELECT CASE WHEN NEW.charged_tokens
                  + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
                  + COALESCE((SELECT SUM(charged_tokens) FROM teacher_reservations),0)
                  + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {int(global_cap)}
                THEN RAISE(ABORT,'research.common_budget_exhausted') END; END""")
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS all_purposes_before_teacher
                BEFORE INSERT ON teacher_reservations BEGIN
                SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
                THEN RAISE(ABORT,'research.persisted_study_stop') END;
                SELECT CASE WHEN NEW.charged_tokens
                  + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
                  + COALESCE((SELECT SUM(charged_tokens) FROM teacher_reservations),0)
                  + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {int(global_cap)}
                THEN RAISE(ABORT,'research.common_budget_exhausted') END; END""")

    def register(self, new_task_ids, old_task_ids):
        values = list(new_task_ids)
        if len(values) > NEW_TASK_CAP:
            raise BudgetRejected("research.only_up_to_17_new_targets")
        return super().register(values, old_task_ids)

    def register_collection(self, tasks, *, gate_id, gate):
        if (
            gate.get("id") != gate_id
            or gate.get("status") != "READY_FOR_FIXED_COLLECTION"
            or not all(
                gate.get(key) is True
                for key in (
                    "panel_quota_complete",
                    "actual_period_semantics_passed",
                    "increment_source_semantics_passed",
                    "new_original_CPU_representation_passed",
                    "complete_trajectory_qualification_passed",
                    "live_transport_controls_passed",
                    "training_catalog_locked",
                    "original_package_consumer_registered",
                )
            )
        ):
            raise BudgetRejected("research.formal_collection_admission_gate")
        if len(tasks) > 260 or len({x["task_id"] for x in tasks}) != len(tasks) or not tasks:
            raise BudgetRejected("research.fixed_unique_candidate_catalog")
        sessions = []
        for pool in ("A", "B"):
            for task in tasks:
                if task["family"] not in {
                    "stock_rollforward",
                    "annual_flow",
                    "company_defined_metric",
                    "control",
                }:
                    raise BudgetRejected("research.registered_training_family")
                bases = ("control",) if task["family"] == "control" else ("endpoint", "movement")
                for basis in bases:
                    for replicate in range(24 if basis == "control" else 32):
                        body = [self.stage_id, pool, task["task_id"], basis, replicate]
                        identifier = (
                            "teacher_session_"
                            + hashlib.sha256(
                                json.dumps(body, separators=(",", ":")).encode()
                            ).hexdigest()
                        )
                        sessions.append(
                            (identifier, task["task_id"], pool, basis, replicate, "registered")
                        )
        if len(sessions) > 25_280:
            raise BudgetRejected("research.fixed_session_upper_bound")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM collection_sessions").fetchone():
                    raise BudgetRejected("research.collection_registered_once")
                if db.execute("SELECT 1 FROM teacher_reservations").fetchone():
                    raise BudgetRejected("research.registration_precedes_all_Teacher_outputs")
                db.execute(
                    "INSERT INTO metadata VALUES ('collection_gate',?)",
                    (json.dumps(gate, sort_keys=True),),
                )
                db.executemany(
                    "INSERT INTO collection_sessions "
                    "(session_id,task_id,pool,basis,replicate,state) VALUES (?,?,?,?,?,?)",
                    sessions,
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return self.sessions()

    def halt(self, reason):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('study_fatal',?)", (str(reason),))

    def mark_sent(self, request_id):
        with self.connection() as db:
            row = db.execute(
                "UPDATE reservations SET state='sent' WHERE request_id=? "
                "AND state='reserved' AND NOT EXISTS "
                "(SELECT 1 FROM metadata WHERE key='study_fatal')",
                (request_id,),
            )
            if row.rowcount != 1:
                raise BudgetRejected("research.single_rewrite_send_before_study_stop")

    def sessions(self):
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM collection_sessions ORDER BY pool,task_id,basis,replicate"
                )
            ]

    def reserve_teacher(self, session_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                session = db.execute(
                    "SELECT * FROM collection_sessions WHERE session_id=?", (session_id,)
                ).fetchone()
                if session is None or session["state"] not in {"registered", "running"}:
                    raise BudgetRejected("research.registered_unfinished_session_only")
                if (
                    db.execute("SELECT 1 FROM reservations WHERE state='budget_breach'").fetchone()
                    or db.execute(
                        "SELECT 1 FROM teacher_reservations WHERE state='budget_breach'"
                    ).fetchone()
                ):
                    raise BudgetRejected("research.prior_reservation_breach")
                prior = db.execute(
                    "SELECT * FROM teacher_reservations WHERE session_id=? ORDER BY attempt",
                    (session_id,),
                ).fetchall()
                if len(prior) >= 32:
                    raise BudgetRejected("research.32_response_limit")
                if prior and (
                    prior[-1]["state"] != "settled"
                    or prior[-1]["http_success"] != 1
                    or prior[-1]["outcome"] != "public_response_received"
                ):
                    raise BudgetRejected("research.no_unknown_inflight_or_transport_retry")
                attempt = len(prior) + 1
                identifier = (
                    "teacher_request_"
                    + hashlib.sha256(f"{session_id}:{attempt}".encode()).hexdigest()
                )
                db.execute(
                    "INSERT INTO teacher_reservations "
                    "(request_id,session_id,attempt,state,reserved_tokens,"
                    "charged_tokens,created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        identifier,
                        session_id,
                        attempt,
                        "reserved",
                        TEACHER_RESERVATION,
                        TEACHER_RESERVATION,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                db.execute(
                    "UPDATE collection_sessions SET state='running' WHERE session_id=?",
                    (session_id,),
                )
                db.execute("COMMIT")
                return {
                    "request_id": identifier,
                    "session_id": session_id,
                    "attempt": attempt,
                    "input_reservation": INPUT_ALLOWANCE,
                    "output_cap": OUTPUT_ALLOWANCE,
                    "reserved_tokens": TEACHER_RESERVATION,
                }
            except sqlite3.IntegrityError as error:
                db.execute("ROLLBACK")
                raise BudgetRejected(str(error)) from error
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def mark_teacher_sent(self, request_id):
        with self.connection() as db:
            row = db.execute(
                "UPDATE teacher_reservations SET state='sent' "
                "WHERE request_id=? AND state='reserved' AND NOT EXISTS "
                "(SELECT 1 FROM metadata WHERE key='study_fatal')",
                (request_id,),
            )
            if row.rowcount != 1:
                raise BudgetRejected("research.exactly_one_teacher_send")

    def settle_teacher(
        self, request_id, *, usage=None, http_success=False, response_model=None, outcome
    ):
        prompt = completion = None
        if isinstance(usage, dict):
            p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
            total = usage.get("total_tokens")
            if all(type(x) is int and x >= 0 for x in (p, c, total)) and total == p + c:
                prompt, completion = p, c
        known = prompt is not None
        breach = known and (prompt > INPUT_ALLOWANCE or completion > OUTPUT_ALLOWANCE)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT * FROM teacher_reservations WHERE request_id=?", (request_id,)
                ).fetchone()
                if row is None or row["state"] != "sent":
                    raise BudgetRejected("research.single_teacher_settlement")
                charged = prompt + completion if known else row["reserved_tokens"]
                state = "budget_breach" if breach else "settled" if known else "usage_unknown"
                db.execute(
                    "UPDATE teacher_reservations SET state=?,prompt_tokens=?,"
                    "completion_tokens=?,charged_tokens=?,http_success=?,response_model=?,"
                    "outcome=? WHERE request_id=?",
                    (
                        state,
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
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return known and not breach

    def finish_session(self, session_id, terminal):
        with self.connection() as db:
            row = db.execute(
                "UPDATE collection_sessions SET state='finished',terminal=? "
                "WHERE session_id=? AND state IN ('registered','running')",
                (terminal, session_id),
            )
            if row.rowcount != 1:
                raise BudgetRejected("research.session_terminal_once")

    def snapshot(self):
        result = super().snapshot()
        with self.connection() as db:
            rows = [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM teacher_reservations ORDER BY session_id,attempt"
                )
            ]
            count = db.execute("SELECT COUNT(*) FROM collection_sessions").fetchone()[0]
            finished = db.execute(
                "SELECT COUNT(*) FROM collection_sessions WHERE state='finished'"
            ).fetchone()[0]
            fatal = db.execute("SELECT value FROM metadata WHERE key='study_fatal'").fetchone()
        charged = result["cumulative_conservative_debit"] + sum(x["charged_tokens"] for x in rows)
        return {
            **result,
            "teacher_reservations": rows,
            "Teacher_registered_sessions": count,
            "Teacher_finished_sessions": finished,
            "Teacher_request_reservations": len(rows),
            "Teacher_conservative_charged_tokens": sum(x["charged_tokens"] for x in rows),
            "cumulative_conservative_debit": charged,
            "remaining_registered_global_allowance": self.cumulative_policy["global_cap"] - charged,
            "all_purposes_share_one_atomic_budget": True,
            "policy_field_scope": (
                "inherited question_rewrite consumer only, not Teacher authorization"
            ),
            "Teacher_policy": {
                "requires_separate_immutable_admission_gate": True,
                "registered_sessions": count,
                "max_responses_per_session": 32,
                "input_reservation": INPUT_ALLOWANCE,
                "output_reservation": OUTPUT_ALLOWANCE,
                "fixed_registry_must_be_complete_before_population_selection": True,
            },
            "Teacher_requests_allowed_in_this_stage": bool(count),
            "incomplete_fixed_collection_may_select_training_population": False,
            "persisted_study_stop": fatal[0] if fatal else None,
        }
