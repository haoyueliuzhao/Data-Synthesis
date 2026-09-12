"""A fail-closed, single-owner handoff of the unused bounded revision allowance.

Pre-freeze inspection never constructs a ResearchLedger. Migration first retires
the predecessor transactionally; only then is a quarantined successor published
exclusively and activated. A failed/crashed handoff is not automatically resumed.
"""

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from ..finance_qa_vnext_task_build.archive import record, validate_record

GLOBAL_CAP = 1_000_000_000
PRIOR_TOTAL = 221_538
REQUEST_CAP = 34
TOKEN_CAP = 330_752
TABLES = (
    "metadata",
    "reservations",
    "registered_tasks",
    "prior_debits",
    "collection_sessions",
    "teacher_reservations",
)
ZERO_TABLES = ("reservations", "registered_tasks", "collection_sessions", "teacher_reservations")
TRANSITION = "readiness_budget_transition"
ROLE = "readiness_budget_transition_role"
PROTECTED_METADATA = ("policy", "cumulative_policy", TRANSITION, ROLE)


class TransitionRejected(RuntimeError):
    pass


def _require(condition, code):
    if not condition:
        raise TransitionRejected("budget_transition." + code)


def _encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _path(value, *, must_exist):
    path = Path(value)
    _require(path.is_absolute() and ".." not in path.parts, "absolute_exact_database_path")
    _require(path.suffix in {".db", ".sqlite3"} and len(path.parts) > 2, "specific_database_file")
    for candidate in [path, *path.parents]:
        _require(not candidate.is_symlink(), "no_database_or_parent_symlink")
    if must_exist:
        _require(path.is_file(), "existing_regular_predecessor")
    return path


def _quiet_fingerprint(path):
    for suffix in ("-wal", "-journal"):
        sidecar = Path(str(path) + suffix)
        _require(not sidecar.is_symlink(), "no_journal_symlink")
        _require(
            not sidecar.exists() or sidecar.stat().st_size == 0,
            "active_journal_requires_quiescent_predecessor",
        )
    return {"sha256": _sha(path), "bytes": path.stat().st_size}


def _state(db):
    schema = [
        dict(row)
        for row in db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        )
    ]
    names = {row["name"] for row in schema if row["type"] == "table"}
    _require(set(TABLES) <= names, "required_ledger_tables")
    values = {}
    for table in TABLES:
        values[table] = sorted(
            (dict(row) for row in db.execute('SELECT * FROM "' + table + '"')), key=_encode
        )
    return {"schema": schema, "tables": values}


def _readonly(path, *, quiescent=False):
    before = _quiet_fingerprint(path) if quiescent else None
    suffix = "?mode=ro&immutable=1" if quiescent else "?mode=ro"
    with closing(
        sqlite3.connect(path.as_uri() + suffix, uri=True, timeout=30, isolation_level=None)
    ) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        state = _state(db)
        db.execute("ROLLBACK")
    if quiescent:
        _require(_quiet_fingerprint(path) == before, "predecessor_changed_during_inspection")
    return state, before


def _metadata(state):
    rows = state["tables"]["metadata"]
    result = {row["key"]: row["value"] for row in rows}
    _require(len(result) == len(rows), "unique_metadata_keys")
    return result


def _policy(stage_id):
    return {
        "stage_id": stage_id,
        "purpose": "question_rewrite",
        "request_cap": REQUEST_CAP,
        "token_cap": TOKEN_CAP,
        "per_task_cap": 2,
        "input_reservation": 8192,
        "output_cap": 1536,
        "common_new_experiment_cap": GLOBAL_CAP,
        "Teacher_enabled": False,
        "Student_enabled": False,
    }


def _base(state, stage_id, prior_debits):
    _require(isinstance(stage_id, str) and bool(stage_id), "nonempty_stage_identity")
    _require(isinstance(prior_debits, list) and bool(prior_debits), "original_prior_debit_list")
    _require(
        all(
            isinstance(row.get("id"), str) and type(row.get("tokens")) is int and row["tokens"] >= 0
            for row in prior_debits
        ),
        "exact_prior_debits",
    )
    _require(len({row["id"] for row in prior_debits}) == len(prior_debits), "unique_prior_debits")
    _require(sum(row["tokens"] for row in prior_debits) == PRIOR_TOTAL, "original_221538_once")
    metadata = _metadata(state)
    _require(json.loads(metadata["policy"]) == _policy(stage_id), "original_bounded_policy")
    cumulative = {
        "global_cap": GLOBAL_CAP,
        "prior_debits": prior_debits,
        "scope": "same approximately-200-task utility allowance, not a new billion",
    }
    _require(json.loads(metadata["cumulative_policy"]) == cumulative, "original_cumulative_policy")
    actual = state["tables"]["prior_debits"]
    expected = sorted(
        ({"debit_id": row["id"], "tokens": row["tokens"]} for row in prior_debits), key=_encode
    )
    _require(actual == expected, "original_prior_rows_without_redebit")
    return metadata


def _zero(state):
    _require(
        all(not state["tables"][name] for name in ZERO_TABLES),
        "no_attempts_or_registered_tasks_or_sessions",
    )


def _normalized_sql(value):
    return re.sub(r"\s+", " ", value).strip().rstrip(";").lower()


def _budget_triggers():
    return {
        "registered_increment_only": """CREATE TRIGGER registered_increment_only
            BEFORE INSERT ON reservations BEGIN SELECT CASE WHEN NOT EXISTS
            (SELECT 1 FROM registered_tasks WHERE task_id=NEW.task_id)
            THEN RAISE(ABORT,'increment.unregistered_or_old_task') END; END""",
        "cumulative_budget_before_reserve": f"""CREATE TRIGGER cumulative_budget_before_reserve
            BEFORE INSERT ON reservations BEGIN SELECT CASE WHEN NEW.charged_tokens
            + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
            + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {GLOBAL_CAP}
            THEN RAISE(ABORT,'increment.cumulative_budget_exhausted') END; END""",
        "all_purposes_before_rewrite": f"""CREATE TRIGGER all_purposes_before_rewrite
            BEFORE INSERT ON reservations BEGIN
            SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
            THEN RAISE(ABORT,'research.persisted_study_stop') END;
            SELECT CASE WHEN EXISTS (SELECT 1 FROM teacher_reservations WHERE state='budget_breach')
            THEN RAISE(ABORT,'research.prior_reservation_breach') END;
            SELECT CASE WHEN NEW.charged_tokens
            + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
            + COALESCE((SELECT SUM(charged_tokens) FROM teacher_reservations),0)
            + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {GLOBAL_CAP}
            THEN RAISE(ABORT,'research.common_budget_exhausted') END; END""",
        "all_purposes_before_teacher": f"""CREATE TRIGGER all_purposes_before_teacher
            BEFORE INSERT ON teacher_reservations BEGIN
            SELECT CASE WHEN EXISTS (SELECT 1 FROM metadata WHERE key='study_fatal')
            THEN RAISE(ABORT,'research.persisted_study_stop') END;
            SELECT CASE WHEN NEW.charged_tokens
            + COALESCE((SELECT SUM(charged_tokens) FROM reservations),0)
            + COALESCE((SELECT SUM(charged_tokens) FROM teacher_reservations),0)
            + COALESCE((SELECT SUM(tokens) FROM prior_debits),0) > {GLOBAL_CAP}
            THEN RAISE(ABORT,'research.common_budget_exhausted') END; END""",
    }


def _check_triggers(state, expected):
    actual = {row["name"]: row["sql"] for row in state["schema"] if row["type"] == "trigger"}
    for name, sql in expected.items():
        _require(
            name in actual and _normalized_sql(actual[name]) == _normalized_sql(sql),
            "persistent_trigger_identity:" + name,
        )


def _deny_triggers(prefix):
    return {
        f"{prefix}_{table}_{operation.lower()}": (
            f"CREATE TRIGGER {prefix}_{table}_{operation.lower()} "
            f"BEFORE {operation} ON {table} "
            f"BEGIN SELECT RAISE(ABORT,'budget_transition.{prefix}'); END"
        )
        for table in TABLES
        for operation in ("INSERT", "UPDATE", "DELETE")
    }


def _owner_triggers():
    names = ",".join("'" + key + "'" for key in PROTECTED_METADATA)
    return {
        "revision_owner_metadata_update": f"""CREATE TRIGGER revision_owner_metadata_update
            BEFORE UPDATE ON metadata WHEN OLD.key IN ({names})
            BEGIN SELECT RAISE(ABORT,'budget_transition.owner_metadata_immutable'); END""",
        "revision_owner_metadata_delete": f"""CREATE TRIGGER revision_owner_metadata_delete
            BEFORE DELETE ON metadata WHEN OLD.key IN ({names})
            BEGIN SELECT RAISE(ABORT,'budget_transition.owner_metadata_immutable'); END""",
        "revision_owner_metadata_insert": f"""CREATE TRIGGER revision_owner_metadata_insert
            BEFORE INSERT ON metadata WHEN NEW.key IN ({names}) AND EXISTS
            (SELECT 1 FROM metadata WHERE key=NEW.key AND value != NEW.value)
            BEGIN SELECT RAISE(ABORT,'budget_transition.owner_metadata_immutable'); END""",
        "revision_prior_insert": """CREATE TRIGGER revision_prior_insert
            BEFORE INSERT ON prior_debits WHEN NOT EXISTS
            (SELECT 1 FROM prior_debits WHERE debit_id=NEW.debit_id AND tokens=NEW.tokens)
            BEGIN SELECT RAISE(ABORT,'budget_transition.prior_debits_immutable'); END""",
        **{
            f"revision_prior_{operation.lower()}": (
                f"CREATE TRIGGER revision_prior_{operation.lower()} "
                f"BEFORE {operation} ON prior_debits "
                "BEGIN SELECT RAISE(ABORT,'budget_transition.prior_debits_immutable'); END"
            )
            for operation in ("UPDATE", "DELETE")
        },
    }


def inspect_predecessor(old_path, expected_stage_id, prior_debits):
    """Read-only pre-freeze zero-state proof; no constructor, checkpoint or writes."""
    path = _path(old_path, must_exist=True)
    state, fingerprint = _readonly(path, quiescent=True)
    metadata = _base(state, expected_stage_id, prior_debits)
    _zero(state)
    _require(
        {row["name"] for row in state["schema"] if row["type"] == "table"} == set(TABLES),
        "no_unrecognized_predecessor_purpose_table",
    )
    _require(
        "study_fatal" not in metadata and TRANSITION not in metadata and ROLE not in metadata,
        "predecessor_not_already_halted_or_transferred",
    )
    _require("collection_gate" not in metadata, "no_prior_collection_registration")
    _require(
        "task_registry" not in metadata or json.loads(metadata["task_registry"]) == [],
        "only_known_empty_task_registry",
    )
    _check_triggers(state, _budget_triggers())
    return record(
        "budget_predecessor_inspection",
        path=str(path),
        stage_id=expected_stage_id,
        fingerprint=fingerprint,
        state=state,
        prior_debits=prior_debits,
        prior_global_debit=PRIOR_TOTAL,
        rewrite_requests=0,
        rewrite_charged_tokens=0,
        registered_tasks=0,
        Teacher_registered_sessions=0,
        Teacher_request_reservations=0,
        immutable_read_only=True,
        active_journal_ignored=False,
    )


def _open_write(path):
    db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    return db


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _seed_quarantined(path, predecessor, transition):
    state = predecessor["state"]
    with closing(_open_write(path)) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("BEGIN IMMEDIATE")
        try:
            for kind in ("table", "index"):
                for item in state["schema"]:
                    if item["type"] == kind and item["sql"]:
                        db.execute(item["sql"])
            old_metadata = _metadata(state)
            metadata = {
                "policy": json.dumps(_policy(transition["new_stage_id"]), sort_keys=True),
                "cumulative_policy": old_metadata["cumulative_policy"],
                TRANSITION: _encode(transition),
                ROLE: "quarantined_successor",
                "study_fatal": "transition_quarantine:" + transition["id"],
            }
            db.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
            db.executemany(
                "INSERT INTO prior_debits VALUES (?,?)",
                [(row["debit_id"], row["tokens"]) for row in state["tables"]["prior_debits"]],
            )
            for sql in _budget_triggers().values():
                db.execute(sql)
            for sql in _deny_triggers("revision_quarantine").values():
                db.execute(sql)
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise


def _check_retired(state, transition, prior_debits):
    metadata = _base(state, transition["old_stage_id"], prior_debits)
    _zero(state)
    expected = {
        **_metadata(transition["predecessor"]["state"]),
        TRANSITION: _encode(transition),
        ROLE: "retired_predecessor",
        "study_fatal": "transition_retired:" + transition["id"],
    }
    _require(metadata == expected, "retired_parent_metadata_and_history")
    _check_triggers(state, _budget_triggers())
    _check_triggers(state, _deny_triggers("revision_retired"))


def _activate(old_path, new_path, transition, prior_debits):
    parent, _ = _readonly(old_path)
    _check_retired(parent, transition, prior_debits)
    with closing(_open_write(new_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            state = _state(db)
            metadata = _base(state, transition["new_stage_id"], prior_debits)
            _zero(state)
            _require(
                metadata.get(TRANSITION) == _encode(transition)
                and metadata.get(ROLE) == "quarantined_successor"
                and metadata.get("study_fatal") == "transition_quarantine:" + transition["id"],
                "exact_quarantined_successor",
            )
            _check_triggers(state, _deny_triggers("revision_quarantine"))
            for name in _deny_triggers("revision_quarantine"):
                db.execute('DROP TRIGGER "' + name + '"')
            db.execute("DELETE FROM metadata WHERE key='study_fatal'")
            db.execute("UPDATE metadata SET value='active_successor' WHERE key=?", (ROLE,))
            for sql in _owner_triggers().values():
                db.execute(sql)
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise


def migrate(
    old_path, new_path, expected_stage_id, new_stage_id, prior_debits, expected_predecessor
):
    """Call once only after the caller has frozen new code/policy and this inspection.

    The parent is durably stopped BEFORE successor creation. If any later step
    fails, do not rerun this function: retained state requires explicit recovery.
    """
    old_path, new_path = _path(old_path, must_exist=True), _path(new_path, must_exist=False)
    _require(old_path != new_path and not new_path.exists(), "exclusive_new_successor_only")
    _require(
        new_stage_id != expected_stage_id and isinstance(new_stage_id, str) and bool(new_stage_id),
        "new_freeze_identity_required",
    )
    validate_record(expected_predecessor, "budget_predecessor_inspection")
    _require(
        inspect_predecessor(old_path, expected_stage_id, prior_debits) == expected_predecessor,
        "frozen_predecessor_inspection_unchanged",
    )
    transition = record(
        "readiness_budget_transition",
        old_path=str(old_path),
        new_path=str(new_path),
        old_stage_id=expected_stage_id,
        new_stage_id=new_stage_id,
        predecessor=expected_predecessor,
        global_token_cap=GLOBAL_CAP,
        inherited_prior_debits=prior_debits,
        inherited_prior_debit=PRIOR_TOTAL,
        prior_debit_added_again=0,
        shared_rewrite_request_cap=REQUEST_CAP,
        shared_rewrite_token_cap=TOKEN_CAP,
        predecessor_purpose_requests=0,
        predecessor_purpose_charged_tokens=0,
        predecessor_history_retained=True,
        old_and_new_may_consume_simultaneously=False,
        failure_policy="fail closed; never reactivate predecessor or allocate another allowance",
        order="durable parent retirement, quarantined exclusive successor creation, activation",
    )
    with closing(_open_write(old_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            current = _state(db)
            _require(
                current == expected_predecessor["state"], "predecessor_changed_before_write_lock"
            )
            _base(current, expected_stage_id, prior_debits)
            _zero(current)
            db.executemany(
                "INSERT INTO metadata VALUES (?,?)",
                [
                    (TRANSITION, _encode(transition)),
                    (ROLE, "retired_predecessor"),
                    ("study_fatal", "transition_retired:" + transition["id"]),
                ],
            )
            for sql in _deny_triggers("revision_retired").values():
                db.execute(sql)
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    # Failure from this point is intentionally one-way: the original ledger is
    # retained and closed. A partial successor must never resurrect the old bank.
    new_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".budget_transition_", dir=new_path.parent))
    seed = temporary / "quarantined.sqlite3"
    _seed_quarantined(seed, expected_predecessor, transition)
    with seed.open("rb") as stream:
        os.fsync(stream.fileno())
    os.link(seed, new_path)  # Atomic exclusive publication; never overwrite a database.
    _sync_directory(new_path.parent)
    _sync_directory(new_path.parent.parent)
    seed.unlink()
    temporary.rmdir()
    _activate(old_path, new_path, transition, prior_debits)
    check_transition(old_path, new_path, transition, new_stage_id, prior_debits)
    return transition


def check_transition(old_path, new_path, expected_transition, new_stage_id, prior_debits):
    """Read-only ownership proof, not a new allowance or all-purpose spend audit.

    Successor consumption and separately authorized additive purpose tables are
    allowed. The predecessor's closed state and original policy/prior/ownership
    fields cannot change. Additional purpose enforcement belongs to its phase.
    """
    old_path, new_path = _path(old_path, must_exist=True), _path(new_path, must_exist=True)
    validate_record(expected_transition, "readiness_budget_transition")
    transition = expected_transition
    _require(
        transition["old_path"] == str(old_path)
        and transition["new_path"] == str(new_path)
        and transition["new_stage_id"] == new_stage_id
        and transition["inherited_prior_debits"] == prior_debits,
        "exact_transition_paths_stage_and_prior",
    )
    old, _ = _readonly(old_path)
    _check_retired(old, transition, prior_debits)
    new, _ = _readonly(new_path)
    metadata = _base(new, new_stage_id, prior_debits)
    _require(
        metadata.get(TRANSITION) == _encode(transition)
        and metadata.get(ROLE) == "active_successor",
        "single_active_successor_identity",
    )
    _require(
        not any(row["name"].startswith("revision_quarantine_") for row in new["schema"]),
        "successor_not_left_quarantined",
    )
    _check_triggers(new, _owner_triggers())
    _check_triggers(new, _budget_triggers())
    return record(
        "budget_transition_verification",
        transition_id=transition["id"],
        status="OWNERSHIP_AND_INHERITANCE_VERIFIED",
        predecessor_retired=True,
        successor_stage_id=new_stage_id,
        inherited_prior_debit=PRIOR_TOTAL,
        successor_rewrite_requests=len(new["tables"]["reservations"]),
        successor_Teacher_requests=len(new["tables"]["teacher_reservations"]),
        successor_study_halted="study_fatal" in metadata,
        additional_purpose_tables_allowed=True,
        grants_new_allowance=False,
        verification_scope="ownership, retired parent, original policy and prior-debit identity",
    )
