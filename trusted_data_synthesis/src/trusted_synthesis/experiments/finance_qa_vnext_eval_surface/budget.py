"""A third registered purpose in the existing single-owner research wallet.

No original policy, prior debit, 17-task registry, or original trigger is changed.
Additional SQL guards also protect already instantiated ResearchLedger clients.
"""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_eval_readiness.budget import ResearchLedger
from ..finance_qa_vnext_readiness_revision.budget_transition import check_transition
from ..finance_qa_vnext_surface_build.budget import BudgetRejected
from ..finance_qa_vnext_task_build.archive import record, validate_record

TASK_CAP = 900
REQUEST_CAP = 1800
INPUT_CAP = 8192
OUTPUT_CAP = 1536
RESERVATION = INPUT_CAP + OUTPUT_CAP
TOKEN_CAP = REQUEST_CAP * RESERVATION
GLOBAL_CAP = 1_000_000_000
MODEL = "deepseek-flash"
PURPOSE_KEY = "eval_surface_rewrite_policy"
FINALIZATION_KEY = "eval_surface_rewrite_finalization"
IDENTITY_FIELDS = {
    "task_id",
    "family",
    "surface_version_id",
    "public_messages_sha256",
    "parent_manifest_id",
}
ALL_RESERVATIONS = ("reservations", "teacher_reservations", "eval_reservations")


def encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def canonical_sha256(value):
    return hashlib.sha256(encode(value)).hexdigest()


def require(condition, code):
    if not condition:
        raise BudgetRejected("eval_surface." + code)


def policy():
    return record(
        "evaluation_rewrite_budget_policy",
        purpose="evaluation_question_rewrite",
        task_cap=TASK_CAP,
        request_cap=REQUEST_CAP,
        per_task_cap=2,
        input_reservation=INPUT_CAP,
        output_cap=OUTPUT_CAP,
        token_cap=TOKEN_CAP,
        global_token_cap=GLOBAL_CAP,
        new_wallet_or_prior_redebit=False,
        registry="original selected dev/confirm task identity and complete public-spec SHA",
        atomic_scope="prior + UNP question rewrite + Teacher + evaluation question rewrite",
        ordinary_transport_unknown="hold full lease, no retry of that task",
        successful_HTTP_unknown_billing="hold conservative debit and persist study_fatal",
        settlement_after_study_stop="allowed for already sent requests; never discard actual cost",
        original_four_budget_triggers_unchanged=True,
        evaluation_finalization=(
            "one complete 900-task outcome set; permanently close only this purpose"
        ),
    )


def _existing_path(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute_wallet_path")
    require(path.is_file(), "existing_wallet_only")
    require(not any(item.is_symlink() for item in [path, *path.parents]), "no_wallet_symlink")
    return path


def _total():
    return " + ".join(
        [
            "COALESCE((SELECT SUM(tokens) FROM prior_debits),0)",
            *[
                f"COALESCE((SELECT SUM(charged_tokens) FROM {table}),0)"
                for table in ALL_RESERVATIONS
            ],
        ]
    )


def _triggers():
    output = {}
    for table in ALL_RESERVATIONS:
        name = "eval_surface_cross3_" + table + "_reserve"
        output[name] = f"""CREATE TRIGGER {name} BEFORE INSERT ON {table} BEGIN
            SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
            THEN RAISE(ABORT,'eval_surface.persisted_study_stop') END;
            SELECT CASE WHEN {_total()} + NEW.charged_tokens > {GLOBAL_CAP}
            THEN RAISE(ABORT,'eval_surface.common_three_purpose_budget_exhausted') END;
            END"""
        name = "eval_surface_cross3_" + table + "_send"
        output[name] = f"""CREATE TRIGGER {name} BEFORE UPDATE ON {table}
            WHEN NEW.state='sent' AND EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
            BEGIN SELECT RAISE(ABORT,'eval_surface.no_send_after_study_stop'); END"""
        name = "eval_surface_cross3_" + table + "_settlement_stop"
        output[name] = f"""CREATE TRIGGER {name} AFTER UPDATE ON {table}
            WHEN NEW.state IN ('settled','usage_unknown','budget_breach') BEGIN
            INSERT OR IGNORE INTO metadata (key,value)
            SELECT 'study_fatal','eval_surface.cross3_settlement_contract:' || NEW.request_id
            WHERE NEW.state='budget_breach' OR {_total()} > {GLOBAL_CAP}
              OR (NEW.http_success=1 AND
                  (NEW.response_model IS NOT '{MODEL}' OR NEW.state='usage_unknown'));
            END"""
        name = "eval_surface_cross3_" + table + "_no_delete"
        output[name] = f"""CREATE TRIGGER {name} BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT,'eval_surface.request_history_immutable'); END"""
        name = "eval_surface_cross3_" + table + "_state"
        output[name] = f"""CREATE TRIGGER {name} BEFORE UPDATE ON {table} BEGIN
            SELECT CASE WHEN NEW.request_id IS NOT OLD.request_id
              OR NEW.attempt IS NOT OLD.attempt OR NEW.reserved_tokens IS NOT OLD.reserved_tokens
              OR NEW.created_at IS NOT OLD.created_at OR NEW.charged_tokens < 0
              OR NOT ((OLD.state='reserved' AND NEW.state='sent'
                       AND NEW.charged_tokens=OLD.charged_tokens)
                      OR (OLD.state='sent' AND NEW.state IN
                          ('settled','usage_unknown','budget_breach')))
            THEN RAISE(ABORT,'eval_surface.monotonic_original_reservation') END;
            END"""
    output["eval_surface_registered_only"] = f"""CREATE TRIGGER eval_surface_registered_only
        BEFORE INSERT ON eval_reservations BEGIN
        SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='{FINALIZATION_KEY}')
          THEN RAISE(ABORT,'eval_surface.evaluation_purpose_finalized') END;
        SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM eval_registry WHERE task_id=NEW.task_id)
          THEN RAISE(ABORT,'eval_surface.unregistered_evaluation_task') END;
        SELECT CASE WHEN (SELECT COUNT(*) FROM eval_reservations) >= {REQUEST_CAP}
          OR COALESCE((SELECT SUM(charged_tokens) FROM eval_reservations),0)
             + NEW.charged_tokens > {TOKEN_CAP}
          THEN RAISE(ABORT,'eval_surface.evaluation_subcap_exhausted') END;
        END"""
    for operation in ("INSERT", "UPDATE", "DELETE"):
        name = "eval_surface_fixed_registry_" + operation.lower()
        output[name] = f"""CREATE TRIGGER {name} BEFORE {operation} ON eval_registry
            BEGIN SELECT RAISE(ABORT,'eval_surface.registered_catalog_immutable'); END"""
    for operation in ("UPDATE", "DELETE"):
        name = "eval_surface_policy_" + operation.lower()
        output[name] = f"""CREATE TRIGGER {name} BEFORE {operation} ON metadata
            WHEN OLD.key IN ('{PURPOSE_KEY}','{FINALIZATION_KEY}')
            BEGIN SELECT RAISE(ABORT,'eval_surface.purpose_policy_immutable'); END"""
    output["eval_surface_policy_insert"] = f"""CREATE TRIGGER eval_surface_policy_insert
        BEFORE INSERT ON metadata WHEN NEW.key IN ('{PURPOSE_KEY}','{FINALIZATION_KEY}') AND EXISTS
        (SELECT 1 FROM metadata WHERE key=NEW.key AND value != NEW.value)
        BEGIN SELECT RAISE(ABORT,'eval_surface.purpose_policy_immutable'); END"""
    return output


def _sql(value):
    return " ".join(value.split()).strip().rstrip(";")


class EvaluationLedger(ResearchLedger):
    def __init__(self, path, owner_stage_id, prior_debits, *, eval_freeze_id):
        path = _existing_path(path)
        require(
            isinstance(eval_freeze_id, str) and bool(eval_freeze_id), "evaluation_freeze_required"
        )
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
        require(
            metadata.get("readiness_budget_transition_role") == "active_successor",
            "active_inherited_wallet_only",
        )
        require(
            json.loads(metadata["policy"])["stage_id"] == owner_stage_id, "unchanged_wallet_owner"
        )
        transition = json.loads(metadata["readiness_budget_transition"])
        check_transition(transition["old_path"], path, transition, owner_stage_id, prior_debits)
        self.eval_freeze_id = eval_freeze_id
        super().__init__(path, owner_stage_id, prior_debits=prior_debits, global_cap=GLOBAL_CAP)
        with self.connection() as db:
            self._purpose(db, optional=True)

    def _purpose(self, db, *, optional=False):
        found = db.execute("SELECT value FROM metadata WHERE key=?", (PURPOSE_KEY,)).fetchone()
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if found is None:
            require(
                optional and not {"eval_registry", "eval_reservations"} & tables,
                "purpose_not_frozen_or_partial_schema",
            )
            return None
        value = json.loads(found[0])
        validate_record(value, "evaluation_rewrite_registration")
        require(
            value["eval_freeze_id"] == self.eval_freeze_id
            and value["owner_stage_id"] == self.stage_id
            and value["budget_policy"] == policy(),
            "frozen_evaluation_purpose_identity",
        )
        require({"eval_registry", "eval_reservations"} <= tables, "complete_evaluation_schema")
        stored = {
            row[0]: row[1]
            for row in db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
        }
        require(
            all(
                name in stored and _sql(stored[name]) == _sql(sql)
                for name, sql in _triggers().items()
            ),
            "three_purpose_sql_guards_unchanged",
        )
        return value

    def register_evaluation(self, registry, *, policy_id, parent_panel_manifest_id):
        require(
            isinstance(registry, list) and 1 <= len(registry) <= TASK_CAP,
            "one_to_900_evaluation_tasks",
        )
        require(
            len({row["task_id"] for row in registry}) == len(registry), "unique_evaluation_task_ids"
        )
        for row in registry:
            require(
                set(row) == {"task_id", "split", "identity", "spec_sha256"}, "fixed_registry_shape"
            )
            require(
                row["split"] in {"dev", "confirm"} and set(row["identity"]) == IDENTITY_FIELDS,
                "public_evaluation_identity_only",
            )
            require(
                row["task_id"] == row["identity"]["task_id"]
                and row["identity"]["parent_manifest_id"] == parent_panel_manifest_id,
                "original_task_and_panel_join",
            )
            require(
                all(
                    isinstance(row["identity"][key], str) and row["identity"][key]
                    for key in IDENTITY_FIELDS
                )
                and len(row["spec_sha256"]) == 64
                and all(char in "0123456789abcdef" for char in row["spec_sha256"]),
                "identity_and_spec_digest",
            )
        registration = record(
            "evaluation_rewrite_registration",
            eval_freeze_id=self.eval_freeze_id,
            owner_stage_id=self.stage_id,
            budget_policy=policy(),
            execution_policy_id=policy_id,
            parent_panel_manifest_id=parent_panel_manifest_id,
            registry_sha256=canonical_sha256(registry),
            registered_task_count=len(registry),
            registered_before_any_evaluation_attempt=True,
        )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                require(
                    not db.execute("SELECT 1 FROM metadata WHERE key='study_fatal'").fetchone(),
                    "cannot_register_after_study_stop",
                )
                require(self._purpose(db, optional=True) is None, "single_evaluation_registration")
                db.execute(
                    "CREATE TABLE eval_registry (task_id TEXT PRIMARY KEY, split TEXT NOT NULL, "
                    "identity_json TEXT NOT NULL, spec_sha256 TEXT NOT NULL, "
                    "ordinal INTEGER NOT NULL UNIQUE)"
                )
                db.execute(f"""CREATE TABLE eval_reservations (
                    request_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES eval_registry(task_id),
                    eval_freeze_id TEXT NOT NULL, attempt INTEGER NOT NULL CHECK(attempt IN (1,2)),
                    reason TEXT NOT NULL, state TEXT NOT NULL,
                    reserved_tokens INTEGER NOT NULL CHECK(reserved_tokens={RESERVATION}),
                    prompt_tokens INTEGER, completion_tokens INTEGER, reported_total_tokens INTEGER,
                    charged_tokens INTEGER NOT NULL CHECK(charged_tokens>=0), http_success INTEGER,
                    response_model TEXT, outcome TEXT, raw_usage_json TEXT, fatal_reason TEXT,
                    created_at TEXT NOT NULL, UNIQUE(task_id,attempt))""")
                db.executemany(
                    "INSERT INTO eval_registry VALUES (?,?,?,?,?)",
                    [
                        (
                            row["task_id"],
                            row["split"],
                            encode(row["identity"]).decode(),
                            row["spec_sha256"],
                            index,
                        )
                        for index, row in enumerate(registry)
                    ],
                )
                db.execute(
                    "INSERT INTO metadata VALUES (?,?)",
                    (PURPOSE_KEY, encode(registration).decode()),
                )
                for sql in _triggers().values():
                    db.execute(sql)
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return registration

    def evaluation_registration(self, task_id):
        with self.connection() as db:
            self._purpose(db)
            row = db.execute("SELECT * FROM eval_registry WHERE task_id=?", (task_id,)).fetchone()
        require(row is not None, "registered_evaluation_task_only")
        return {
            "task_id": row["task_id"],
            "split": row["split"],
            "identity": json.loads(row["identity_json"]),
            "spec_sha256": row["spec_sha256"],
        }

    def finalize_evaluation(self, public_catalog_id, outcome_task_ids):
        require(
            isinstance(public_catalog_id, str) and bool(public_catalog_id),
            "public_catalog_identity_required",
        )
        require(
            isinstance(outcome_task_ids, list)
            and len(outcome_task_ids) == TASK_CAP
            and all(isinstance(item, str) and bool(item) for item in outcome_task_ids)
            and len(set(outcome_task_ids)) == TASK_CAP,
            "complete_unique_900_outcome_task_ids",
        )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                registration = self._purpose(db)
                require(
                    db.execute("SELECT 1 FROM metadata WHERE key=?", (FINALIZATION_KEY,)).fetchone()
                    is None,
                    "single_evaluation_finalization",
                )
                registered = [row[0] for row in db.execute("SELECT task_id FROM eval_registry")]
                require(
                    len(registered) == TASK_CAP and set(registered) == set(outcome_task_ids),
                    "complete_original_evaluation_registry_outcomes",
                )
                require(
                    not db.execute(
                        "SELECT 1 FROM eval_reservations WHERE state IN ('reserved','sent') LIMIT 1"
                    ).fetchone(),
                    "no_inflight_or_unsent_reserved_evaluation_at_finalization",
                )
                require(
                    not db.execute("SELECT 1 FROM metadata WHERE key='study_fatal'").fetchone(),
                    "cannot_finalize_stopped_study",
                )
                rows = db.execute("SELECT state,charged_tokens FROM eval_reservations").fetchall()
                value = record(
                    "evaluation_rewrite_finalization",
                    eval_freeze_id=self.eval_freeze_id,
                    owner_stage_id=self.stage_id,
                    public_catalog_id=public_catalog_id,
                    registry_sha256=registration["registry_sha256"],
                    registered_task_count=len(registered),
                    completed_task_count=len(outcome_task_ids),
                    outcome_task_ids=sorted(outcome_task_ids),
                    outcome_task_ids_sha256=canonical_sha256(sorted(outcome_task_ids)),
                    no_inflight_requests=True,
                    terminal_request_count=len(rows),
                    terminal_unknown_count=sum(row["state"] == "usage_unknown" for row in rows),
                    retained_conservative_debit=sum(row["charged_tokens"] for row in rows),
                    remaining_evaluation_attempts_permanently_closed=True,
                    unknown_charges_released=False,
                    other_purposes_closed=False,
                    finalized_at=datetime.now(timezone.utc).isoformat(),
                )
                db.execute(
                    "INSERT INTO metadata VALUES (?,?)", (FINALIZATION_KEY, encode(value).decode())
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return value

    def reserve_evaluation(self, task_id, *, repair=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._purpose(db)
                require(
                    db.execute(
                        "SELECT 1 FROM eval_registry WHERE task_id=?", (task_id,)
                    ).fetchone(),
                    "registered_evaluation_task_only",
                )
                rows = db.execute(
                    "SELECT * FROM eval_reservations WHERE task_id=? ORDER BY attempt", (task_id,)
                ).fetchall()
                require(
                    type(repair) is bool and len(rows) < 2 and bool(rows) == repair,
                    "initial_or_one_contract_repair_only",
                )
                if rows:
                    require(
                        rows[0]["state"] == "settled"
                        and rows[0]["http_success"] == 1
                        and rows[0]["outcome"]
                        in {"response_received", "rewrite_structure_failure"},
                        "no_transport_unknown_or_inflight_retry",
                    )
                attempt = len(rows) + 1
                identifier = "eval_rewrite_request_" + canonical_sha256(
                    [self.eval_freeze_id, task_id, attempt]
                )
                db.execute(
                    "INSERT INTO eval_reservations (request_id,task_id,eval_freeze_id,attempt,"
                    "reason,state,reserved_tokens,charged_tokens,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        task_id,
                        self.eval_freeze_id,
                        attempt,
                        "contract_repair" if repair else "initial",
                        "reserved",
                        RESERVATION,
                        RESERVATION,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                db.execute("COMMIT")
                return {
                    "request_id": identifier,
                    "task_id": task_id,
                    "eval_freeze_id": self.eval_freeze_id,
                    "attempt": attempt,
                    "input_reservation": INPUT_CAP,
                    "output_cap": OUTPUT_CAP,
                    "reserved_tokens": RESERVATION,
                    "purpose": "evaluation_question_rewrite",
                }
            except sqlite3.IntegrityError as error:
                db.execute("ROLLBACK")
                raise BudgetRejected(str(error)) from error
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def mark_evaluation_sent(self, request_id):
        try:
            with self.connection() as db:
                changed = db.execute(
                    "UPDATE eval_reservations SET state='sent' WHERE request_id=? "
                    "AND state='reserved' AND NOT EXISTS "
                    "(SELECT 1 FROM metadata WHERE key='study_fatal')",
                    (request_id,),
                )
                require(changed.rowcount == 1, "exactly_one_evaluation_send_before_stop")
        except sqlite3.IntegrityError as error:
            raise BudgetRejected(str(error)) from error

    def settle_evaluation(
        self,
        request_id,
        *,
        usage=None,
        http_success=False,
        response_model=None,
        outcome,
        fatal_reason=None,
    ):
        usage = usage if isinstance(usage, dict) else {}
        p, c, total = (
            usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )

        def valid(value):
            return type(value) is int and 0 <= value <= 2**62 - 1

        parts = valid(p) and valid(c)
        known = parts and valid(total) and total == p + c
        breach = bool(parts and (p > INPUT_CAP or c > OUTPUT_CAP))
        charge = (
            p + c
            if known
            else max(RESERVATION, p + c if parts else 0, total if valid(total) else 0)
        )
        reason = fatal_reason
        if http_success and (response_model != MODEL or not known):
            reason = reason or "evaluation_successful_HTTP_model_or_billing_contract"
        state = "budget_breach" if breach else "settled" if known else "usage_unknown"
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT * FROM eval_reservations WHERE request_id=? AND eval_freeze_id=?",
                    (request_id, self.eval_freeze_id),
                ).fetchone()
                require(
                    row is not None and row["state"] == "sent",
                    "single_settlement_of_sent_evaluation",
                )
                db.execute(
                    "UPDATE eval_reservations SET state=?,prompt_tokens=?,completion_tokens=?,"
                    "reported_total_tokens=?,charged_tokens=?,http_success=?,response_model=?,"
                    "outcome=?,raw_usage_json=?,fatal_reason=? WHERE request_id=?",
                    (
                        state,
                        p if valid(p) else None,
                        c if valid(c) else None,
                        total if valid(total) else None,
                        charge,
                        int(http_success),
                        response_model,
                        outcome,
                        json.dumps(usage, sort_keys=True, default=str),
                        reason,
                        request_id,
                    ),
                )
                if reason:
                    db.execute(
                        "INSERT OR IGNORE INTO metadata VALUES ('study_fatal',?)", (str(reason),)
                    )
                stopped = db.execute(
                    "SELECT value FROM metadata WHERE key='study_fatal'"
                ).fetchone()
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return record(
            "evaluation_rewrite_settlement",
            request_id=request_id,
            state=state,
            usage_known=known,
            charged_tokens=charge,
            budget_breach=breach,
            study_fatal=stopped[0] if stopped else None,
            new_allowance_granted=False,
        )

    def snapshot(self):
        with self.connection() as db:
            db.execute("BEGIN")
            evaluation_policy = self._purpose(db, optional=True)
            unp = [
                dict(row)
                for row in db.execute("SELECT * FROM reservations ORDER BY task_id,attempt")
            ]
            teacher = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM teacher_reservations ORDER BY session_id,attempt"
                )
            ]
            evaluation = (
                [
                    dict(row)
                    for row in db.execute(
                        "SELECT * FROM eval_reservations ORDER BY task_id,attempt"
                    )
                ]
                if evaluation_policy
                else []
            )
            prior = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
            sessions = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM collection_sessions ORDER BY pool,task_id,basis,replicate"
                )
            ]
            stop = db.execute("SELECT value FROM metadata WHERE key='study_fatal'").fetchone()
            finalized = db.execute(
                "SELECT value FROM metadata WHERE key=?", (FINALIZATION_KEY,)
            ).fetchone()
            db.execute("ROLLBACK")
        charges = {
            "UNP_question_rewrite": sum(row["charged_tokens"] for row in unp),
            "Teacher": sum(row["charged_tokens"] for row in teacher),
            "evaluation_question_rewrite": sum(row["charged_tokens"] for row in evaluation),
        }
        cumulative = prior + sum(charges.values())
        return {
            "policy": self.policy,
            "cumulative_policy": self.cumulative_policy,
            "reservations": unp,
            "request_reservations": len(unp),
            "sent_request_count": sum(row["state"] != "reserved" for row in unp),
            "conservative_charged_tokens": charges["UNP_question_rewrite"],
            "known_prompt_tokens": sum(row["prompt_tokens"] or 0 for row in unp),
            "known_completion_tokens": sum(row["completion_tokens"] or 0 for row in unp),
            "unsettled_or_unknown_count": sum(row["state"] != "settled" for row in unp),
            "budget_breach_count": sum(
                row["state"] == "budget_breach" for row in [*unp, *teacher, *evaluation]
            ),
            "teacher_reservations": teacher,
            "Teacher_registered_sessions": len(sessions),
            "Teacher_finished_sessions": sum(row["state"] == "finished" for row in sessions),
            "Teacher_request_reservations": len(teacher),
            "Teacher_conservative_charged_tokens": charges["Teacher"],
            "eval_reservations": evaluation,
            "eval_request_reservations": len(evaluation),
            "eval_sent_request_count": sum(row["state"] != "reserved" for row in evaluation),
            "eval_conservative_charged_tokens": charges["evaluation_question_rewrite"],
            "eval_registered_tasks": evaluation_policy["registered_task_count"]
            if evaluation_policy
            else 0,
            "evaluation_policy": evaluation_policy,
            "evaluation_finalization": json.loads(finalized[0]) if finalized else None,
            "previous_registered_debit": prior,
            "debit_by_purpose": charges,
            "cumulative_conservative_debit": cumulative,
            "remaining_registered_global_allowance": GLOBAL_CAP - cumulative,
            "persisted_study_stop": stop[0] if stop else None,
            "all_purposes_share_one_atomic_budget": True,
            "registered_purpose_count": 3 if evaluation_policy else 2,
            "snapshot_single_read_transaction": True,
            "prior_debit_counted_once": True,
            "legacy_reservations_key_is_UNP_only": True,
        }

    def evaluation_snapshot(self):
        snapshot = self.snapshot()
        return {
            "policy": snapshot["evaluation_policy"],
            "reservations": snapshot["eval_reservations"],
            "request_reservations": snapshot["eval_request_reservations"],
            "conservative_charged_tokens": snapshot["eval_conservative_charged_tokens"],
            "cumulative_conservative_debit": snapshot["cumulative_conservative_debit"],
            "remaining_registered_global_allowance": snapshot[
                "remaining_registered_global_allowance"
            ],
            "persisted_study_stop": snapshot["persisted_study_stop"],
            "evaluation_finalization": snapshot["evaluation_finalization"],
        }
