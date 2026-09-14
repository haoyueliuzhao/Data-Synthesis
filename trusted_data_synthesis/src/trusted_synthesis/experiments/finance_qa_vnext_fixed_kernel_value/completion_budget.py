"""Prospective seventh-purpose wallet; closed collection history stays closed.

Only the 272 original interrupted/unstarted slots are admitted. Existing public
prefixes are references, never new leases or debits. ``requests``/``new_requests``
return seventh-purpose rows only; ``combined_requests`` is an explicit read-only
view of parent rows followed by new rows at their original response indices.
"""

import json
import re
import sqlite3
from contextlib import contextmanager, nullcontext
from pathlib import Path

from . import budget as parent
from . import protocol as p

BudgetStop = parent.BudgetStop
require = parent.require
PURPOSE = "kernel_completion_registration"
FATAL = "kernel_completion_fatal"
FINAL = "kernel_completion_finalization"
TABLE = "kernel_completion_requests"
SESSIONS = "kernel_completion_sessions"
TOKEN_CAP, REQUEST_CAP, COMMON_CAP = 109024251, 8300, 1000000000
SESSION_CAP, PREFIX_CAP = 272, 404
OLD_RESERVATIONS = parent.ALL_RESERVATIONS
ALL_RESERVATIONS = (*OLD_RESERVATIONS, TABLE)


def _total_sql():
    return " + ".join(
        [
            "COALESCE((SELECT SUM(tokens) FROM prior_debits),0)",
            *[f"COALESCE((SELECT SUM(charged_tokens) FROM {t}),0)" for t in ALL_RESERVATIONS],
        ]
    )


def legacy_snapshot(db, original=None):
    """Hash all six old purposes, including their closed recovery metadata."""
    if original is None:
        original = {
            "original_table_names": [
                r[0]
                for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                if not r[0].startswith(("sqlite_", "kernel_completion_"))
            ],
            "original_metadata_keys": [
                r[0]
                for r in db.execute("SELECT key FROM metadata ORDER BY key")
                if not r[0].startswith("kernel_completion_")
            ],
            "original_schema_names": [
                r[0]
                for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','trigger','index') "
                    "AND sql IS NOT NULL ORDER BY name"
                )
                if not r[0].startswith("kernel_completion_")
            ],
        }
    return parent.legacy_snapshot(db, original)


def validate_manifest(manifest):
    p.checked(manifest, "kernel_completion_manifest")
    require(
        all(
            isinstance(manifest.get(k), str) and manifest[k]
            for k in ("original_freeze_id", "parent_report_id", "authorization_id")
        ),
        "completion_parent_authorization_identity",
    )
    slots = manifest.get("slots")
    require(isinstance(slots, list) and len(slots) == SESSION_CAP, "completion_exact_272_slots")
    ids, prefixes = set(), []
    for slot in slots:
        reg = slot["registered_session"]
        sid, previous = reg["session_id"], slot["prefix_request_ids"]
        require(isinstance(sid, str) and sid and sid not in ids, "completion_unique_original_slots")
        require(slot["parent_status"] in ("budget_aborted", "not_run"), "completion_not_finished")
        require(
            isinstance(previous, list)
            and len(previous) < p.MAX_RESPONSES
            and all(isinstance(x, str) and x for x in previous),
            "completion_bounded_prefix",
        )
        require(slot["parent_status"] != "not_run" or not previous, "completion_notrun_empty")
        ids.add(sid)
        prefixes.extend(previous)
    require(
        len(prefixes) == len(set(prefixes)) == PREFIX_CAP, "completion_exact_404_prefix_requests"
    )
    require(
        sum(p.MAX_RESPONSES - len(s["prefix_request_ids"]) for s in slots) == REQUEST_CAP,
        "completion_exact_8300_remaining_responses",
    )
    require(
        sum(s["parent_status"] == "budget_aborted" for s in slots) == 121,
        "completion_original_status_denominator",
    )
    return manifest


def triggers(legacy):
    """Old guards remain byte-for-byte; these additional guards close old writes."""
    result = {}
    for table in legacy["original_table_names"]:
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table), "completion_safe_table")
        if table == "metadata":
            continue
        for op in ("INSERT", "UPDATE", "DELETE"):
            name = f"kernel_completion_old_{table}_no_{op.lower()}"
            result[name] = f"""CREATE TRIGGER {name} BEFORE {op} ON {table}
              BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_old_history_immutable'); END"""
    for op in ("UPDATE", "DELETE"):
        name = "kernel_completion_metadata_no_" + op.lower()
        result[name] = f"""CREATE TRIGGER {name} BEFORE {op} ON metadata
          WHEN OLD.key IN ('{PURPOSE}','{FATAL}','{FINAL}','study_fatal')
            OR EXISTS(SELECT 1 FROM kernel_completion_legacy_metadata WHERE key=OLD.key)
          BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_frozen_metadata'); END"""
    result[
        "kernel_completion_metadata_no_replace"
    ] = f"""CREATE TRIGGER kernel_completion_metadata_no_replace
      BEFORE INSERT ON metadata WHEN EXISTS(SELECT 1 FROM metadata WHERE key=NEW.key)
        AND (NEW.key IN ('{PURPOSE}','{FATAL}','{FINAL}','study_fatal')
          OR EXISTS(SELECT 1 FROM kernel_completion_legacy_metadata WHERE key=NEW.key))
      BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_metadata_replacement'); END"""
    for op in ("INSERT", "UPDATE", "DELETE"):
        name = "kernel_completion_inventory_no_" + op.lower()
        result[name] = f"""CREATE TRIGGER {name} BEFORE {op} ON kernel_completion_legacy_metadata
          BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_frozen_inventory'); END"""
    result["kernel_completion_new_request"] = f"""CREATE TRIGGER kernel_completion_new_request
      BEFORE INSERT ON {TABLE} BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM metadata WHERE key='{PURPOSE}')
        OR EXISTS(SELECT 1 FROM metadata WHERE key IN ('{FATAL}','{FINAL}','study_fatal'))
        THEN RAISE(ABORT,'kernel_budget.completion_purpose_not_open') END;
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM {SESSIONS} WHERE session_id=NEW.session_id
          AND state IN ('registered','running'))
        THEN RAISE(ABORT,'kernel_budget.completion_registered_unfinished_only') END;
      SELECT CASE WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE request_id=NEW.request_id
          OR (session_id=NEW.session_id AND attempt=NEW.attempt))
        THEN RAISE(ABORT,'kernel_budget.completion_no_replacement') END;
      SELECT CASE WHEN NEW.state IS NOT 'reserved' OR typeof(NEW.attempt) IS NOT 'integer'
        OR typeof(NEW.reserved_tokens) IS NOT 'integer'
        OR typeof(NEW.charged_tokens) IS NOT 'integer'
        OR typeof(NEW.request_id) IS NOT 'text' OR length(NEW.request_id)=0
        OR typeof(NEW.created_at) IS NOT 'text' OR length(NEW.created_at)=0
        OR NEW.reserved_tokens IS NOT {p.REQUEST_RESERVATION}
        OR NEW.charged_tokens IS NOT {p.REQUEST_RESERVATION}
        OR NEW.prompt_tokens IS NOT NULL OR NEW.completion_tokens IS NOT NULL
        OR NEW.reported_total_tokens IS NOT NULL OR NEW.http_success IS NOT NULL
        OR NEW.response_model IS NOT NULL OR NEW.outcome IS NOT NULL
        THEN RAISE(ABORT,'kernel_budget.completion_full_lease_before_send') END;
      SELECT CASE WHEN NEW.attempt IS NOT (1
          + (SELECT prefix_count FROM {SESSIONS} WHERE session_id=NEW.session_id)
          + (SELECT COUNT(*) FROM {TABLE} WHERE session_id=NEW.session_id))
        OR NEW.attempt > {p.MAX_RESPONSES}
        OR EXISTS(SELECT 1 FROM {TABLE} WHERE session_id=NEW.session_id
          AND (state IS NOT 'settled' OR http_success IS NOT 1
            OR response_model IS NOT '{p.MODEL}' OR outcome IS NOT 'public_response_received'))
        THEN RAISE(ABORT,'kernel_budget.completion_no_retry_unknown_failed_or_inflight') END;
      SELECT CASE WHEN (SELECT COUNT(*) FROM {TABLE}) >= {REQUEST_CAP}
        OR COALESCE((SELECT SUM(charged_tokens) FROM {TABLE}),0)+NEW.charged_tokens > {TOKEN_CAP}
        THEN RAISE(ABORT,'kernel_budget.completion_subcap') END;
      SELECT CASE WHEN {_total_sql()}+NEW.charged_tokens > {COMMON_CAP}
        THEN RAISE(ABORT,'kernel_budget.completion_common_seven_purpose_cap') END; END"""
    # Reuse the unchanged closed-state/usage contract, not the parent's namespace
    # or cap. It enforces exactly one send, settlement and proven-unsent refund.
    result["kernel_completion_request_state"] = parent.triggers()[
        "kernel_recovery_request_state"
    ].replace("kernel_recovery", "kernel_completion")
    result["kernel_completion_common_send"] = f"""CREATE TRIGGER kernel_completion_common_send
      BEFORE UPDATE ON {TABLE} WHEN NEW.state='sent'
        AND EXISTS(SELECT 1 FROM metadata WHERE key='study_fatal')
      BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_no_send_after_common_stop'); END"""
    result[
        "kernel_completion_settlement_stop"
    ] = f"""CREATE TRIGGER kernel_completion_settlement_stop
      AFTER UPDATE ON {TABLE} WHEN NEW.state IN ('settled','usage_unknown','budget_breach') BEGIN
      INSERT INTO metadata(key,value) SELECT 'study_fatal',
        'kernel_budget.completion_settlement_contract:' || NEW.request_id
      WHERE NOT EXISTS(SELECT 1 FROM metadata WHERE key='study_fatal')
        AND (NEW.state='budget_breach' OR {_total_sql()} > {COMMON_CAP}
          OR (NEW.http_success=1 AND (NEW.response_model IS NOT '{p.MODEL}'
            OR NEW.state='usage_unknown'))); END"""
    result[
        "kernel_completion_request_no_delete"
    ] = f"""CREATE TRIGGER kernel_completion_request_no_delete
      BEFORE DELETE ON {TABLE} BEGIN
      SELECT RAISE(ABORT,'kernel_budget.completion_history_immutable'); END"""
    for op in ("INSERT", "DELETE"):
        name = "kernel_completion_sessions_no_" + op.lower()
        result[name] = f"""CREATE TRIGGER {name} BEFORE {op} ON {SESSIONS}
          BEGIN SELECT RAISE(ABORT,'kernel_budget.completion_fixed_registry'); END"""
    result["kernel_completion_session_state"] = f"""CREATE TRIGGER kernel_completion_session_state
      BEFORE UPDATE ON {SESSIONS} BEGIN
      SELECT CASE WHEN NEW.session_id IS NOT OLD.session_id OR NEW.ordinal IS NOT OLD.ordinal
        OR NEW.registered_json IS NOT OLD.registered_json OR NEW.slot_json IS NOT OLD.slot_json
        OR NEW.prefix_count IS NOT OLD.prefix_count
        OR NOT ((OLD.state='registered' AND NEW.state='running' AND NEW.terminal IS NULL)
          OR (OLD.state IN ('registered','running') AND NEW.state='finished'
            AND typeof(NEW.terminal)='text' AND length(NEW.terminal)>0))
        THEN RAISE(ABORT,'kernel_budget.completion_monotonic_session') END;
      SELECT CASE WHEN NEW.state='finished' AND EXISTS(SELECT 1 FROM {TABLE}
        WHERE session_id=OLD.session_id AND state IN ('reserved','sent'))
        THEN RAISE(ABORT,'kernel_budget.completion_no_inflight_terminal') END; END"""
    return result


class CompletionLedger:
    def __init__(self, path, completion_freeze_id, manifest=None, *, readonly=False):
        self.path, self.completion_freeze_id = Path(path), completion_freeze_id
        self.readonly, self.manifest, self.freeze_id = readonly, None, None
        self._registration_raw = self._registration_value = self._expected_guards = None
        require(
            self.path.is_absolute()
            and self.path.is_file()
            and ".." not in self.path.parts
            and not any(x.is_symlink() for x in (self.path, *self.path.parents)),
            "completion_existing_regular_wallet",
        )
        require(
            isinstance(completion_freeze_id, str) and completion_freeze_id,
            "completion_authorization_freeze",
        )
        if manifest is not None:
            self.manifest = validate_manifest(manifest)
            self.freeze_id = manifest["original_freeze_id"]
        with self.connection(readonly=True) as db:
            self._registration(db, optional=True)

    @contextmanager
    def connection(self, *, readonly=False, operation="direct_sql"):
        require(readonly or not self.readonly, "completion_readonly_handle")
        gate = nullcontext() if readonly else parent._writer_gate(self.path).enter(operation)
        with gate:
            db = sqlite3.connect(
                self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                uri=True,
                timeout=30,
                isolation_level=None,
            )
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                yield db
            finally:
                db.close()

    def _registration(self, db, *, optional=False):
        found = db.execute("SELECT value FROM metadata WHERE key=?", (PURPOSE,)).fetchone()
        if found is None:
            require(
                optional
                and not db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name LIKE 'kernel_completion_%' LIMIT 1"
                ).fetchone(),
                "completion_no_partial_schema",
            )
            return None
        if self._registration_raw is None:
            value = p.checked(json.loads(found[0]), "kernel_completion_budget_registration")
            require(
                value["completion_freeze_id"] == self.completion_freeze_id,
                "completion_exact_frozen_purpose",
            )
            manifest = validate_manifest(value["manifest"])
            require(self.manifest is None or self.manifest == manifest, "completion_exact_manifest")
            self.manifest, self.freeze_id = manifest, manifest["original_freeze_id"]
            require(
                value["purpose_cap"] == TOKEN_CAP
                and value["request_cap"] == REQUEST_CAP
                and value["common_cap"] == COMMON_CAP
                and value["purpose"] == PURPOSE,
                "completion_exact_caps",
            )
            self._registration_raw, self._registration_value = found[0], value
            self._expected_guards = {
                name: parent._sql(sql) for name, sql in triggers(value["legacy_snapshot"]).items()
            }
        else:
            # Immutable exact bytes only; never cache the live common balance.
            require(found[0] == self._registration_raw, "completion_registration_bytes_unchanged")
            value = self._registration_value
        stored = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
        require(
            all(
                name in stored and parent._sql(stored[name]) == sql
                for name, sql in self._expected_guards.items()
            ),
            "completion_guards_present_unchanged",
        )
        return value

    def register(self, manifest=None, *, legacy_before=None):
        manifest = validate_manifest(manifest or self.manifest)
        self.manifest, self.freeze_id = manifest, manifest["original_freeze_id"]
        with self.connection(operation="register") as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                require(self._registration(db, optional=True) is None, "completion_register_once")
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
                require("study_fatal" not in metadata, "completion_no_common_stop")
                policy = json.loads(metadata["policy"])
                require(
                    policy["stage_id"] == p.OWNER
                    and policy["common_new_experiment_cap"] == COMMON_CAP,
                    "completion_original_wallet_owner_and_cap",
                )
                closed = p.checked(json.loads(metadata[parent.FINAL]), "kernel_budget_finalization")
                require(
                    closed["purpose_closed"] is True
                    and closed["report_id"] == manifest["parent_report_id"]
                    and closed["freeze_id"] == self.freeze_id,
                    "completion_parent_closed_report_and_freeze",
                )
                for table in OLD_RESERVATIONS:
                    require(
                        not db.execute(
                            f"SELECT 1 FROM {table} WHERE state IN ('reserved','sent') LIMIT 1"
                        ).fetchone(),
                        "completion_old_consumers_quiescent",
                    )
                require(
                    db.execute("SELECT COUNT(*) FROM kernel_recovery_sessions").fetchone()[0]
                    == p.SESSION_CAP
                    and not db.execute(
                        "SELECT 1 FROM kernel_recovery_sessions WHERE state IS NOT "
                        "'finished' LIMIT 1"
                    ).fetchone(),
                    "completion_parent_all_slots_terminal",
                )
                before = legacy_snapshot(db)
                require(
                    legacy_before is None or before == legacy_before,
                    "completion_exact_source_snapshot",
                )
                for slot in manifest["slots"]:
                    reg = slot["registered_session"]
                    row = db.execute(
                        "SELECT registered_json,terminal FROM kernel_recovery_sessions "
                        "WHERE session_id=?",
                        (reg["session_id"],),
                    ).fetchone()
                    require(
                        row is not None and json.loads(row[0]) == reg,
                        "completion_same_original_registration",
                    )
                    require(
                        (
                            slot["parent_status"] == "budget_aborted"
                            and row[1] == "fatal_provider_or_budget_stop"
                        )
                        or (
                            slot["parent_status"] == "not_run"
                            and row[1] == "not_requested_or_failed_after_global_stop"
                        ),
                        "completion_parent_stop_terminal_only",
                    )
                    rows = [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM kernel_recovery_requests WHERE session_id=? "
                            "ORDER BY attempt",
                            (reg["session_id"],),
                        )
                    ]
                    require(
                        [r["request_id"] for r in rows] == slot["prefix_request_ids"],
                        "completion_exact_parent_prefix_inventory",
                    )
                    require(
                        all(
                            r["attempt"] == i + 1
                            and r["state"] == "settled"
                            and r["http_success"] == 1
                            and r["response_model"] == p.MODEL
                            and r["outcome"] == "public_response_received"
                            and all(
                                type(r[k]) is int and r[k] >= 0
                                for k in (
                                    "prompt_tokens",
                                    "completion_tokens",
                                    "reported_total_tokens",
                                    "charged_tokens",
                                )
                            )
                            and r["prompt_tokens"] + r["completion_tokens"]
                            == r["reported_total_tokens"]
                            == r["charged_tokens"]
                            and r["prompt_tokens"] <= p.INPUT_ALLOWANCE
                            and r["completion_tokens"] <= p.OUTPUT_ALLOWANCE
                            for i, r in enumerate(rows)
                        ),
                        "completion_safe_known_successful_prefix_only",
                    )
                db.execute(f"""CREATE TABLE {SESSIONS}(
                  session_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
                  registered_json TEXT NOT NULL, slot_json TEXT NOT NULL,
                  prefix_count INTEGER NOT NULL, state TEXT NOT NULL, terminal TEXT)""")
                db.execute(f"""CREATE TABLE {TABLE}(
                  request_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL REFERENCES {SESSIONS}(session_id),
                  attempt INTEGER NOT NULL, state TEXT NOT NULL, reserved_tokens INTEGER NOT NULL,
                  charged_tokens INTEGER NOT NULL, prompt_tokens INTEGER, completion_tokens INTEGER,
                  reported_total_tokens INTEGER, http_success INTEGER, response_model TEXT,
                  outcome TEXT, created_at TEXT NOT NULL, UNIQUE(session_id,attempt))""")
                db.execute("CREATE TABLE kernel_completion_legacy_metadata(key TEXT PRIMARY KEY)")
                db.executemany(
                    "INSERT INTO kernel_completion_legacy_metadata VALUES(?)",
                    [(key,) for key in before["original_metadata_keys"]],
                )
                db.executemany(
                    f"INSERT INTO {SESSIONS} VALUES(?,?,?,?,?,'registered',NULL)",
                    [
                        (
                            s["registered_session"]["session_id"],
                            s["registered_session"]["ordinal"],
                            p.encode(s["registered_session"]).decode(),
                            p.encode(s).decode(),
                            len(s["prefix_request_ids"]),
                        )
                        for s in manifest["slots"]
                    ],
                )
                value = p.record(
                    "kernel_completion_budget_registration",
                    purpose=PURPOSE,
                    completion_freeze_id=self.completion_freeze_id,
                    original_freeze_id=self.freeze_id,
                    manifest=manifest,
                    legacy_snapshot=before,
                    purpose_cap=TOKEN_CAP,
                    request_cap=REQUEST_CAP,
                    common_cap=COMMON_CAP,
                    parent_request_table="kernel_recovery_requests",
                    request_table=TABLE,
                    old_purposes_reopened=False,
                    original_debits_replayed=False,
                    old_unknown_leases_still_charged=True,
                )
                db.execute("INSERT INTO metadata VALUES(?,?)", (PURPOSE, p.encode(value).decode()))
                for sql in triggers(before).values():
                    db.execute(sql)
                self._registration(db)
                require(legacy_snapshot(db, before) == before, "completion_old_history_preserved")
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return value

    def registered(self, session_id):
        with self.connection(readonly=True) as db:
            self._registration(db)
            row = db.execute(
                f"SELECT registered_json FROM {SESSIONS} WHERE session_id=?", (session_id,)
            ).fetchone()
            require(row is not None, "completion_registered_slot_required")
            return json.loads(row[0])

    def sessions(self):
        with self.connection(readonly=True) as db:
            self._registration(db)
            return [dict(r) for r in db.execute(f"SELECT * FROM {SESSIONS} ORDER BY ordinal")]

    def _requests(self, table, session_id=None):
        with self.connection(readonly=True) as db:
            self._registration(db)
            query, params = f"SELECT * FROM {table}", ()
            if session_id is not None:
                query += " WHERE session_id=?"
                params = (session_id,)
            return [dict(r) for r in db.execute(query + " ORDER BY session_id,attempt", params)]

    def new_requests(self, session_id=None):
        return self._requests(TABLE, session_id)

    requests = new_requests

    def parent_requests(self, session_id):
        self.registered(session_id)
        return self._requests("kernel_recovery_requests", session_id)

    def combined_requests(self, session_id):
        return self.parent_requests(session_id) + self.new_requests(session_id)

    def reserve(self, session_id):
        with self.connection(operation="reserve") as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._registration(db)
                row = db.execute(
                    f"SELECT state,prefix_count FROM {SESSIONS} WHERE session_id=?", (session_id,)
                ).fetchone()
                require(
                    row is not None and row[0] in ("registered", "running"),
                    "completion_unfinished_slot_only",
                )
                attempt = (
                    row[1]
                    + 1
                    + db.execute(
                        f"SELECT COUNT(*) FROM {TABLE} WHERE session_id=?", (session_id,)
                    ).fetchone()[0]
                )
                request_id = "kernel_completion_request_" + p.sha(
                    p.encode([self.completion_freeze_id, session_id, attempt])
                )
                db.execute(
                    f"INSERT INTO "
                    f"{TABLE}(request_id,session_id,attempt,state,reserved_tokens,"
                    f"charged_tokens,created_at) VALUES(?,?,?,'reserved',?,?,?)",
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
                        f"UPDATE {SESSIONS} SET state='running' WHERE session_id=?", (session_id,)
                    )
                db.execute("COMMIT")
                return dict(
                    request_id=request_id,
                    session_id=session_id,
                    attempt=attempt,
                    input_reservation=p.INPUT_ALLOWANCE,
                    output_cap=p.OUTPUT_ALLOWANCE,
                    reserved_tokens=p.REQUEST_RESERVATION,
                    completion_freeze_id=self.completion_freeze_id,
                )
            except sqlite3.Error as error:
                db.execute("ROLLBACK")
                raise BudgetStop(str(error)) from error
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def mark_sent(self, request_id):
        with self.connection(operation="mark_sent") as db:
            self._registration(db)
            changed = db.execute(
                f"UPDATE {TABLE} SET state='sent' WHERE request_id=? AND state='reserved'",
                (request_id,),
            )
            require(changed.rowcount == 1, "completion_single_send")

    def settle(self, request_id, *, usage=None, http_success=False, response_model=None, outcome):
        require(
            type(http_success) is bool
            and isinstance(outcome, str)
            and outcome
            and (response_model is None or isinstance(response_model, str)),
            "completion_settlement_observation",
        )
        prompt = completion = total = None
        if isinstance(usage, dict):
            a, b, c = (usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
            if all(type(x) is int and x >= 0 for x in (a, b, c)) and a + b == c:
                prompt, completion, total = a, b, c
        known = prompt is not None
        breach = known and (prompt > p.INPUT_ALLOWANCE or completion > p.OUTPUT_ALLOWANCE)
        state = "budget_breach" if breach else "settled" if known else "usage_unknown"
        with self.connection(operation="settle") as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._registration(db)
                row = db.execute(
                    f"SELECT * FROM {TABLE} WHERE request_id=?", (request_id,)
                ).fetchone()
                require(row is not None and row["state"] == "sent", "completion_single_settlement")
                db.execute(
                    f"UPDATE {TABLE} SET "
                    f"state=?,charged_tokens=?,prompt_tokens=?,completion_tokens=?,"
                    f"reported_total_tokens=?,http_success=?,response_model=?,outcome=? "
                    f"WHERE request_id=?",
                    (
                        state,
                        total if known else row["reserved_tokens"],
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

    def cancel_unsent(self, request_id, reason):
        require(isinstance(reason, str) and reason, "completion_unsent_reason")
        with self.connection(operation="cancel_unsent") as db:
            self._registration(db)
            changed = db.execute(
                f"UPDATE {TABLE} SET "
                f"state='not_sent',charged_tokens=0,prompt_tokens=0,completion_tokens=0,"
                f"reported_total_tokens=0,http_success=0,response_model=NULL,outcome=? "
                f"WHERE request_id=? AND state='reserved'",
                ("not_sent:" + reason, request_id),
            )
            require(changed.rowcount == 1, "completion_cancel_only_proven_unsent")
        return p.record(
            "unsent_reservation_cancellation",
            request_id=request_id,
            reason=reason,
            state="not_sent",
            retained_reserved_tokens=p.REQUEST_RESERVATION,
            released_unused_allowance=p.REQUEST_RESERVATION,
            actual_HTTP_requests=0,
            old_or_network_unknown_leases_refunded=False,
            same_session_retry_allowed=False,
        )

    def halt(self, reason):
        with self.connection(operation="halt") as db:
            self._registration(db)
            db.execute(
                "INSERT INTO metadata SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM metadata "
                "WHERE key=?)",
                (FATAL, str(reason), FATAL),
            )

    def finish(self, session_id, terminal):
        require(isinstance(terminal, str) and terminal, "completion_nonempty_terminal")
        with self.connection(operation="finish") as db:
            self._registration(db)
            changed = db.execute(
                f"UPDATE {SESSIONS} SET state='finished',terminal=? WHERE session_id=? "
                f"AND state IN ('registered','running')",
                (terminal, session_id),
            )
            require(changed.rowcount == 1, "completion_single_terminal")

    def writer_statistics(self, *, include_events=False):
        return parent._writer_gate(self.path).statistics(include_events=include_events)

    def snapshot(self):
        with self.connection(readonly=True) as db:
            registration = self._registration(db)
            counts = dict(db.execute(f"SELECT state,COUNT(*) FROM {SESSIONS} GROUP BY state"))
            charges = [
                dict(r)
                for r in db.execute(
                    f"SELECT state,COUNT(*) AS requests,SUM(charged_tokens) AS "
                    f"charged_tokens FROM {TABLE} GROUP BY state ORDER BY state"
                )
            ]
            common = db.execute("SELECT " + _total_sql()).fetchone()[0]
            stops = dict(
                db.execute(
                    "SELECT key,value FROM metadata WHERE key IN ('study_fatal',?,?)",
                    (FATAL, FINAL),
                )
            )
        debit = sum(r["charged_tokens"] for r in charges)
        return p.record(
            "kernel_completion_wallet_snapshot",
            purpose=PURPOSE,
            request_table=TABLE,
            registration_id=registration["id"],
            completion_freeze_id=self.completion_freeze_id,
            sessions_by_state=counts,
            request_states=charges,
            completion_conservative_debit=debit,
            common_conservative_debit=common,
            remaining_common_allowance=COMMON_CAP - common,
            remaining_completion_allowance=TOKEN_CAP - debit,
            persisted_stops=stops,
            old_unknown_leases_still_charged=True,
            writer_statistics=self.writer_statistics(),
        )

    def finalize(self, *, report_id):
        with self.connection(operation="finalize") as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._registration(db)
                require(
                    not db.execute(
                        f"SELECT 1 FROM {TABLE} WHERE state IN ('reserved','sent') LIMIT 1"
                    ).fetchone(),
                    "completion_no_inflight_finalization",
                )
                require(
                    not db.execute("SELECT 1 FROM metadata WHERE key=?", (FINAL,)).fetchone(),
                    "completion_finalize_once",
                )
                value = p.record(
                    "kernel_budget_finalization",
                    freeze_id=self.freeze_id,
                    original_freeze_id=self.freeze_id,
                    completion_freeze_id=self.completion_freeze_id,
                    purpose=PURPOSE,
                    report_id=report_id,
                    purpose_closed=True,
                    old_purposes_not_reopened=True,
                )
                db.execute("INSERT INTO metadata VALUES(?,?)", (FINAL, p.encode(value).decode()))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return value
