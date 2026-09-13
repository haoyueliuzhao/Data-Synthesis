"""Fourth purpose in the same existing SQLite wallet; original history stays put."""

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..finance_qa_vnext_surface_build.budget import BudgetRejected
from . import protocol as p

OLD_RESERVATIONS = ("reservations", "teacher_reservations", "eval_reservations")
ALL_RESERVATIONS = (*OLD_RESERVATIONS, "probe01_requests")
PURPOSE = "probe01_registration"
FATAL = "probe01_fatal"
FINAL = "probe01_finalization"


class BudgetStop(BudgetRejected):
    global_fatal = True


def require(value, code):
    if not value:
        raise BudgetStop("probe01_budget." + code)


def _sql(value):
    return " ".join(value.split()).strip().rstrip(";")


def _total_sql():
    return " + ".join(
        [
            "COALESCE((SELECT SUM(tokens) FROM prior_debits),0)",
            *[f"COALESCE((SELECT SUM(charged_tokens) FROM {name}),0)" for name in ALL_RESERVATIONS],
        ]
    )


def triggers():
    result = {}
    for table in ALL_RESERVATIONS:
        name = "probe01_cross4_" + table + "_reserve"
        result[name] = f"""CREATE TRIGGER {name} BEFORE INSERT ON {table} BEGIN
          SELECT CASE WHEN EXISTS(SELECT 1 FROM metadata WHERE key='study_fatal')
            THEN RAISE(ABORT,'probe01_budget.common_persisted_stop') END;
          SELECT CASE WHEN NEW.charged_tokens < 0
            OR {_total_sql()} + NEW.charged_tokens > {p.COMMON_CAP}
            THEN RAISE(ABORT,'probe01_budget.common_four_purpose_cap') END; END"""
        name = "probe01_cross4_" + table + "_send"
        result[name] = f"""CREATE TRIGGER {name} BEFORE UPDATE ON {table}
          WHEN NEW.state='sent' AND EXISTS(SELECT 1 FROM metadata WHERE key='study_fatal')
          BEGIN SELECT RAISE(ABORT,'probe01_budget.no_send_after_common_stop'); END"""
        name = "probe01_cross4_" + table + "_settlement"
        result[name] = f"""CREATE TRIGGER {name} AFTER UPDATE ON {table}
          WHEN NEW.state IN ('settled','usage_unknown','budget_breach') BEGIN
          INSERT OR IGNORE INTO metadata(key,value)
          SELECT 'study_fatal','probe01_budget.common_settlement_contract:' || NEW.request_id
          WHERE NEW.state='budget_breach' OR {_total_sql()} > {p.COMMON_CAP}
            OR (NEW.http_success=1 AND
                (NEW.response_model IS NOT '{p.MODEL}' OR NEW.state='usage_unknown')); END"""
    result["probe01_new_request"] = f"""CREATE TRIGGER probe01_new_request
      BEFORE INSERT ON probe01_requests BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM metadata WHERE key='{PURPOSE}')
        OR EXISTS(SELECT 1 FROM metadata WHERE key IN ('{FATAL}','{FINAL}'))
        THEN RAISE(ABORT,'probe01_budget.purpose_not_open') END;
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM probe01_sessions WHERE session_id=NEW.session_id
          AND state IN ('registered','running'))
        THEN RAISE(ABORT,'probe01_budget.registered_unfinished_session') END;
      SELECT CASE WHEN NEW.state IS NOT 'reserved'
        OR NEW.reserved_tokens IS NOT {p.REQUEST_RESERVATION}
        OR NEW.charged_tokens IS NOT {p.REQUEST_RESERVATION}
        OR NEW.prompt_tokens IS NOT NULL OR NEW.completion_tokens IS NOT NULL
        OR NEW.reported_total_tokens IS NOT NULL OR NEW.http_success IS NOT NULL
        OR NEW.response_model IS NOT NULL OR NEW.outcome IS NOT NULL
        THEN RAISE(ABORT,'probe01_budget.full_lease_before_send') END;
      SELECT CASE WHEN NEW.attempt IS NOT
          (1 + (SELECT COUNT(*) FROM probe01_requests WHERE session_id=NEW.session_id))
        OR NEW.attempt > {p.MAX_RESPONSES}
        OR EXISTS(SELECT 1 FROM probe01_requests WHERE session_id=NEW.session_id
          AND (state IS NOT 'settled' OR http_success IS NOT 1
               OR response_model IS NOT '{p.MODEL}' OR outcome IS NOT 'public_response_received'))
        THEN RAISE(ABORT,'probe01_budget.no_retry_after_failed_unknown_or_inflight_request') END;
      SELECT CASE WHEN (SELECT COUNT(*) FROM probe01_requests) >= {p.REQUEST_CAP}
        OR COALESCE((SELECT SUM(charged_tokens) FROM probe01_requests),0)
           + NEW.charged_tokens > {p.TOKEN_CAP}
        THEN RAISE(ABORT,'probe01_budget.probe_subcap') END; END"""
    result["probe01_request_state"] = f"""CREATE TRIGGER probe01_request_state
      BEFORE UPDATE ON probe01_requests BEGIN
      SELECT CASE WHEN NEW.request_id IS NOT OLD.request_id OR NEW.session_id IS NOT OLD.session_id
        OR NEW.attempt IS NOT OLD.attempt OR NEW.reserved_tokens IS NOT OLD.reserved_tokens
        OR NEW.created_at IS NOT OLD.created_at OR NEW.charged_tokens < 0
        OR NOT ((OLD.state='reserved' AND NEW.state='sent'
          AND NEW.charged_tokens=OLD.charged_tokens AND NEW.prompt_tokens IS NULL
          AND NEW.completion_tokens IS NULL AND NEW.reported_total_tokens IS NULL
          AND NEW.http_success IS NULL AND NEW.response_model IS NULL AND NEW.outcome IS NULL)
          OR (OLD.state='sent' AND NEW.state IN ('settled','usage_unknown','budget_breach')))
        THEN RAISE(ABORT,'probe01_budget.monotonic_request_history') END;
      SELECT CASE WHEN NEW.state='sent'
        AND EXISTS(SELECT 1 FROM metadata WHERE key IN ('{FATAL}','{FINAL}'))
        THEN RAISE(ABORT,'probe01_budget.no_send_after_probe_stop') END;
      SELECT CASE WHEN NEW.state='settled' AND
        (NEW.prompt_tokens IS NULL OR NEW.completion_tokens IS NULL
         OR NEW.reported_total_tokens IS NULL
         OR NEW.prompt_tokens < 0 OR NEW.completion_tokens < 0
         OR NEW.prompt_tokens > {p.INPUT_ALLOWANCE} OR NEW.completion_tokens > {p.OUTPUT_ALLOWANCE}
         OR NEW.reported_total_tokens != NEW.prompt_tokens+NEW.completion_tokens
         OR NEW.charged_tokens != NEW.reported_total_tokens)
        THEN RAISE(ABORT,'probe01_budget.known_settlement_contract') END;
      SELECT CASE WHEN NEW.state='usage_unknown' AND
        (NEW.charged_tokens != OLD.reserved_tokens OR NEW.prompt_tokens IS NOT NULL
          OR NEW.completion_tokens IS NOT NULL OR NEW.reported_total_tokens IS NOT NULL)
        THEN RAISE(ABORT,'probe01_budget.unknown_never_refunded') END;
      SELECT CASE WHEN NEW.state='budget_breach' AND
        (NEW.prompt_tokens IS NULL OR NEW.completion_tokens IS NULL
          OR NEW.charged_tokens != NEW.prompt_tokens+NEW.completion_tokens
          OR NEW.reported_total_tokens != NEW.charged_tokens
          OR NOT(NEW.prompt_tokens > {p.INPUT_ALLOWANCE}
                 OR NEW.completion_tokens > {p.OUTPUT_ALLOWANCE}))
        THEN RAISE(ABORT,'probe01_budget.breach_actual_cost_preserved') END; END"""
    result["probe01_request_no_delete"] = """CREATE TRIGGER probe01_request_no_delete
      BEFORE DELETE ON probe01_requests BEGIN
      SELECT RAISE(ABORT,'probe01_budget.request_history_immutable'); END"""
    for operation in ("INSERT", "DELETE"):
        name = "probe01_sessions_no_" + operation.lower()
        result[name] = f"""CREATE TRIGGER {name} BEFORE {operation} ON probe01_sessions
          BEGIN SELECT RAISE(ABORT,'probe01_budget.fixed_registry'); END"""
    result["probe01_session_state"] = """CREATE TRIGGER probe01_session_state
      BEFORE UPDATE ON probe01_sessions BEGIN
      SELECT CASE WHEN NEW.session_id IS NOT OLD.session_id OR NEW.ordinal IS NOT OLD.ordinal
        OR NEW.task_id IS NOT OLD.task_id OR NEW.profile IS NOT OLD.profile
        OR NEW.basis IS NOT OLD.basis
        OR NEW.replicate IS NOT OLD.replicate OR NEW.registered_json IS NOT OLD.registered_json
        OR NOT ((OLD.state='registered' AND NEW.state='running' AND NEW.terminal IS NULL)
                OR (OLD.state IN ('registered','running') AND NEW.state='finished'
                    AND NEW.terminal IS NOT NULL))
        THEN RAISE(ABORT,'probe01_budget.session_state_or_identity') END; END"""
    for operation in ("UPDATE", "DELETE"):
        name = "probe01_metadata_no_" + operation.lower()
        result[name] = f"""CREATE TRIGGER {name} BEFORE {operation} ON metadata
          WHEN OLD.key IN ('{PURPOSE}','{FATAL}','{FINAL}')
          BEGIN SELECT RAISE(ABORT,'probe01_budget.immutable_purpose_metadata'); END"""
    return result


def legacy_snapshot(db, original=None):
    """Logical history hashes, not an assertion that SQLite file bytes stay fixed."""
    all_tables = [
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    names = (
        original["original_table_names"]
        if original
        else [x for x in all_tables if not x.startswith(("sqlite_", "probe01_"))]
    )
    require(
        {"metadata", "prior_debits", *OLD_RESERVATIONS} <= set(names),
        "existing_three_purpose_wallet",
    )
    tables, metadata = [], dict(db.execute("SELECT key,value FROM metadata"))
    keys = (
        original["original_metadata_keys"]
        if original
        else sorted(k for k in metadata if not k.startswith("probe01_"))
    )
    require(all(k in metadata for k in keys), "old_metadata_not_removed")
    for name in names:
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name), "safe_table_name")
        columns = [row[1] for row in db.execute(f'PRAGMA table_info("{name}")')]
        require(
            columns and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c) for c in columns),
            "safe_column_names",
        )
        if name == "metadata":
            rows = [[k, metadata[k]] for k in keys]
        else:
            order = ",".join('"' + c + '"' for c in columns)
            rows = [list(row) for row in db.execute(f'SELECT * FROM "{name}" ORDER BY {order}')]
        tables.append(
            {
                "table": name,
                "columns": columns,
                "rows": len(rows),
                "canonical_rows_sha256": p.sha(p.encode(rows)),
            }
        )
    schema = dict(
        db.execute(
            "SELECT name,sql FROM sqlite_master WHERE type IN ('table','trigger','index') "
            "AND sql IS NOT NULL"
        )
    )
    schema_names = (
        original["original_schema_names"]
        if original
        else sorted(k for k in schema if not k.startswith("probe01_"))
    )
    require(all(k in schema for k in schema_names), "old_schema_not_removed")
    return p.record(
        "legacy_wallet_snapshot",
        original_table_names=names,
        original_metadata_keys=keys,
        original_schema_names=schema_names,
        tables=tables,
        schema=[{"name": k, "sql_sha256": p.sha(schema[k])} for k in schema_names],
        owner=json.loads(metadata["policy"])["stage_id"],
        logical_old_rows_not_database_file_bytes=True,
    )


class CoverageLedger:
    def __init__(self, path, freeze_id):
        self.path, self.freeze_id = Path(path), freeze_id
        require(
            self.path.is_absolute()
            and self.path.is_file()
            and ".." not in self.path.parts
            and not any(x.is_symlink() for x in (self.path, *self.path.parents)),
            "existing_regular_wallet_only",
        )
        with self.connection(readonly=True) as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            require(json.loads(metadata["policy"])["stage_id"] == p.OWNER, "original_wallet_owner")
            require(
                json.loads(metadata["policy"])["common_new_experiment_cap"] == p.COMMON_CAP,
                "original_common_cap",
            )
            self._registration(db, optional=True)

    @contextmanager
    def connection(self, *, readonly=False):
        suffix = "?mode=ro" if readonly else "?mode=rw"
        db = sqlite3.connect(
            self.path.as_uri() + suffix, uri=True, timeout=30, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    def _registration(self, db, *, optional=False):
        found = db.execute("SELECT value FROM metadata WHERE key=?", (PURPOSE,)).fetchone()
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if found is None:
            require(
                optional and not {"probe01_sessions", "probe01_requests"} & tables,
                "no_partial_probe_schema",
            )
            return None
        try:
            value = p.checked(json.loads(found[0]), "probe_budget_registration")
        except (ValueError, TypeError) as error:
            raise BudgetStop("probe01_budget.registration_identity") from error
        require(
            value["freeze_id"] == self.freeze_id and value["policy_id"] == p.policy()["id"],
            "exact_frozen_purpose",
        )
        stored = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        require(
            all(
                name in stored and _sql(stored[name]) == _sql(sql)
                for name, sql in triggers().items()
            ),
            "four_purpose_guards_present_unchanged",
        )
        return value

    def register(self, registry, tasks, *, legacy_before):
        p.validate_registry(registry, tasks, self.freeze_id)
        p.checked(legacy_before, "legacy_wallet_snapshot")
        value = p.record(
            "probe_budget_registration",
            freeze_id=self.freeze_id,
            policy_id=p.policy()["id"],
            owner_stage_id=p.OWNER,
            registered_sessions=len(registry),
            registry_sha256=p.sha(p.encode(registry)),
            legacy_snapshot_id=legacy_before["id"],
            common_cap=p.COMMON_CAP,
            purpose_cap=p.TOKEN_CAP,
            original_requests_and_debits_not_replayed=True,
            no_new_wallet=True,
        )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                require(
                    self._registration(db, optional=True) is None,
                    "one_registration_before_Probe_outputs",
                )
                require(
                    not db.execute("SELECT 1 FROM metadata WHERE key='study_fatal'").fetchone(),
                    "no_prior_common_stop",
                )
                require(
                    legacy_snapshot(db) == legacy_before, "original_wallet_snapshot_at_registration"
                )
                for table in OLD_RESERVATIONS:
                    require(
                        not db.execute(
                            f"SELECT 1 FROM {table} WHERE state IN ('reserved','sent')"
                        ).fetchone(),
                        "old_consumers_quiescent_at_registration",
                    )
                db.execute("""CREATE TABLE probe01_sessions(
                  session_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
                  task_id TEXT NOT NULL,
                  profile TEXT NOT NULL, basis TEXT NOT NULL, replicate INTEGER NOT NULL,
                  registered_json TEXT NOT NULL, state TEXT NOT NULL, terminal TEXT,
                  UNIQUE(task_id,profile,basis,replicate))""")
                db.execute("""CREATE TABLE probe01_requests(
                  request_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL REFERENCES probe01_sessions(session_id),
                  attempt INTEGER NOT NULL, state TEXT NOT NULL, reserved_tokens INTEGER NOT NULL,
                  charged_tokens INTEGER NOT NULL, prompt_tokens INTEGER, completion_tokens INTEGER,
                  reported_total_tokens INTEGER, http_success INTEGER,
                  response_model TEXT, outcome TEXT,
                  created_at TEXT NOT NULL, UNIQUE(session_id,attempt))""")
                db.executemany(
                    "INSERT INTO probe01_sessions VALUES(?,?,?,?,?,?,?,?,NULL)",
                    [
                        (
                            r["session_id"],
                            r["ordinal"],
                            r["task_id"],
                            r["profile"],
                            r["basis"],
                            r["replicate"],
                            p.encode(r).decode(),
                            "registered",
                        )
                        for r in registry
                    ],
                )
                db.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?)",
                    (PURPOSE, p.encode(value).decode()),
                )
                for sql in triggers().values():
                    db.execute(sql)
                self._registration(db)
                require(
                    legacy_snapshot(db, legacy_before) == legacy_before,
                    "old_history_unchanged_by_migration",
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return value

    def sessions(self):
        with self.connection(readonly=True) as db:
            self._registration(db)
            return [
                dict(row) for row in db.execute("SELECT * FROM probe01_sessions ORDER BY ordinal")
            ]

    def requests(self, session_id=None):
        with self.connection(readonly=True) as db:
            query = "SELECT * FROM probe01_requests"
            params = ()
            if session_id is not None:
                query += " WHERE session_id=?"
                params = (session_id,)
            return [dict(row) for row in db.execute(query + " ORDER BY session_id,attempt", params)]

    def registered(self, session_id):
        with self.connection(readonly=True) as db:
            row = db.execute(
                "SELECT registered_json FROM probe01_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        require(row is not None, "registered_session_required")
        return json.loads(row[0])

    def reserve(self, session_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._registration(db)
                row = db.execute(
                    "SELECT state FROM probe01_sessions WHERE session_id=?", (session_id,)
                ).fetchone()
                require(
                    row is not None and row[0] in ("registered", "running"),
                    "unfinished_session_only",
                )
                attempt = (
                    db.execute(
                        "SELECT COUNT(*) FROM probe01_requests WHERE session_id=?", (session_id,)
                    ).fetchone()[0]
                    + 1
                )
                request_id = "probe01_request_" + p.sha(
                    p.encode([self.freeze_id, session_id, attempt])
                )
                db.execute(
                    """INSERT INTO probe01_requests(request_id,session_id,attempt,state,
                  reserved_tokens,charged_tokens,created_at) VALUES(?,?,?,'reserved',?,?,?)""",
                    (
                        request_id,
                        session_id,
                        attempt,
                        p.REQUEST_RESERVATION,
                        p.REQUEST_RESERVATION,
                        p.now(),
                    ),
                )
                if row[0] == "registered":
                    db.execute(
                        "UPDATE probe01_sessions SET state='running' WHERE session_id=?",
                        (session_id,),
                    )
                db.execute("COMMIT")
                return {
                    "request_id": request_id,
                    "session_id": session_id,
                    "attempt": attempt,
                    "input_reservation": p.INPUT_ALLOWANCE,
                    "output_cap": p.OUTPUT_ALLOWANCE,
                    "reserved_tokens": p.REQUEST_RESERVATION,
                }
            except sqlite3.Error as error:
                db.execute("ROLLBACK")
                raise BudgetStop(str(error)) from error
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def mark_sent(self, request_id):
        with self.connection() as db:
            changed = db.execute(
                "UPDATE probe01_requests SET state='sent' WHERE request_id=? AND state='reserved'",
                (request_id,),
            )
            require(changed.rowcount == 1, "single_send")

    def settle(self, request_id, *, usage=None, http_success=False, response_model=None, outcome):
        prompt = completion = total = None
        if isinstance(usage, dict):
            a, b, c = (usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
            if all(type(x) is int and x >= 0 for x in (a, b, c)) and a + b == c:
                prompt, completion, total = a, b, c
        known = prompt is not None
        breach = known and (prompt > p.INPUT_ALLOWANCE or completion > p.OUTPUT_ALLOWANCE)
        state = "budget_breach" if breach else "settled" if known else "usage_unknown"
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT * FROM probe01_requests WHERE request_id=?", (request_id,)
                ).fetchone()
                require(row is not None and row["state"] == "sent", "single_settlement_after_send")
                charged = total if known else row["reserved_tokens"]
                db.execute(
                    """UPDATE probe01_requests SET state=?,charged_tokens=?,prompt_tokens=?,
                  completion_tokens=?,reported_total_tokens=?,http_success=?,response_model=?,outcome=?
                  WHERE request_id=?""",
                    (
                        state,
                        charged,
                        prompt,
                        completion,
                        total,
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

    def halt(self, reason):
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)", (FATAL, str(reason))
            )

    def finish(self, session_id, terminal):
        with self.connection() as db:
            changed = db.execute(
                """UPDATE probe01_sessions SET state='finished',terminal=?
              WHERE session_id=? AND state IN ('registered','running')""",
                (terminal, session_id),
            )
            require(changed.rowcount == 1, "single_session_terminal")

    def snapshot(self):
        with self.connection(readonly=True) as db:
            registration = self._registration(db)
            counts = {
                row[0]: row[1]
                for row in db.execute("SELECT state,COUNT(*) FROM probe01_sessions GROUP BY state")
            }
            charges = [
                dict(row)
                for row in db.execute("""SELECT state,COUNT(*) AS requests,
              SUM(charged_tokens) AS charged_tokens FROM probe01_requests
              GROUP BY state ORDER BY state""")
            ]
            common = db.execute("SELECT " + _total_sql()).fetchone()[0]
            stop = dict(
                db.execute(
                    "SELECT key,value FROM metadata WHERE key IN ('study_fatal',?,?)",
                    (FATAL, FINAL),
                )
            )
        debit = sum(row["charged_tokens"] for row in charges)
        return p.record(
            "probe_wallet_snapshot",
            registration_id=registration["id"],
            sessions_by_state=counts,
            request_states=charges,
            probe_conservative_debit=debit,
            common_conservative_debit=common,
            remaining_common_allowance=p.COMMON_CAP - common,
            remaining_probe_allowance=p.TOKEN_CAP - debit,
            persisted_stops=stop,
            old_unknown_leases_still_charged=True,
        )

    def finalize(self, *, report_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._registration(db)
                require(
                    not db.execute(
                        "SELECT 1 FROM probe01_requests WHERE state IN ('reserved','sent')"
                    ).fetchone(),
                    "no_inflight_finalization",
                )
                require(
                    not db.execute("SELECT 1 FROM metadata WHERE key=?", (FINAL,)).fetchone(),
                    "finalize_once",
                )
                row = p.record(
                    "probe_budget_finalization",
                    freeze_id=self.freeze_id,
                    report_id=report_id,
                    purpose_closed=True,
                    old_purposes_not_reopened=True,
                )
                db.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?)", (FINAL, p.encode(row).decode())
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return row
