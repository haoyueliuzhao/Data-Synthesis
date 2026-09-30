"""Prospective V10 purposes in the existing wallet; no model or network operations.

Registration is explicit. It neither creates a wallet nor releases historical
holds. Two transactional counters cover both charged usage and pending/UNKNOWN
worst-case reservations. Old namespaces stop admitting new dispatches.
"""

import json
import sqlite3
import time
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from .contracts import digest, invocation_identity
from .probe_budget import (
    UNKNOWN_ABANDONMENT_ACTION,
    UNKNOWN_ABANDONMENT_PREFIX,
    V6_PURPOSE,
    V9_NETWORK_EXCEPTIONS,
    BudgetUnavailable,
    DuplicateInvocation,
    ProbeBudget,
    RequestPartitionError,
    UnknownAbandonmentError,
    _acknowledged_unknowns,
    _budget_snapshot,
    _json,
    _request_record_digest,
    read_budget_snapshot,
)

PARTITION_KEY = "v10_new_batch_partition"
BATCH_ID = "finqa-v10-20260929-new8000-01"
LIMITS = {
    "generation": {"requests": 199000, "microcny": 100_000_000},
    "review_mapping": {"requests": 17000, "microcny": 550_000_000},
}
OUTPUT_LIMITS = {
    "generation": (2048, 16384),
    "review": (2048, 4096, 8192, 16384, 32768, 65536),
    "mapping": (2048, 4096, 8192, 16384, 32768, 65536),
}
HISTORY = {"requests": 40076, "spent": 336_264_329, "held": 144_834_560, "unknown": 65}
UNALLOCATED_REQUESTS = 1924
UNALLOCATED_MICROCNY = 68_901_111
NETWORK_REASON = "v10 transport response or usage unknown"
NETWORK_POLICY = {
    "schema": "v10_connection_unknown_policy.v1",
    "pending_zero_required": True,
    "no_response_and_no_usage_only": True,
    "exception_types": sorted(V9_NETWORK_EXCEPTIONS),
    "permanent_full_hold": True,
    "no_resend": True,
    "unknown_never_positive": True,
    "clear_only_exact_covered_halt": True,
}


def _coordinate(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"nonempty {name} required")
    return value


def generation_episode_id(batch_id, task_id, slot_index):
    if type(slot_index) is not int or not 0 <= slot_index < 8:
        raise ValueError("new batch slot index must be 0..7")
    return "v10gen:" + digest(
        dict(
            batch_id=_coordinate(batch_id, "batch_id"),
            task_id=_coordinate(task_id, "task_id"),
            slot_index=slot_index,
        )
    )


def review_episode_id(batch_id, slot_id, reviewer):
    if (
        reviewer not in {"A", "B"}
        or not isinstance(slot_id, str)
        or not slot_id.startswith("v10gen:")
    ):
        raise ValueError("V10 generation slot and reviewer A/B required")
    return "v10review:" + digest(
        dict(batch_id=_coordinate(batch_id, "batch_id"), slot_id=slot_id, reviewer=reviewer)
    )


def map_episode_id(batch_id, task_id):
    return "v10map:" + digest(
        dict(batch_id=_coordinate(batch_id, "batch_id"), task_id=_coordinate(task_id, "task_id"))
    )


def _roster(batch_id, slots):
    tasks, seen, result = defaultdict(set), set(), []
    if batch_id != BATCH_ID or not isinstance(slots, list) or len(slots) != 8000:
        raise RequestPartitionError("exact fixed new V10 batch and 8000 slots required")
    for slot in slots:
        task_id, index = slot.get("task_id"), slot.get("slot_index")
        sid = generation_episode_id(batch_id, task_id, index)
        if slot.get("slot_id", slot.get("episode_id")) != sid or sid in seen:
            raise RequestPartitionError("new slot ID must bind batch/task/index exactly once")
        if slot.get("purpose") != "common_material_candidate":
            raise RequestPartitionError("all eight slots remain common material candidates")
        seen.add(sid)
        tasks[task_id].add(index)
        result.append((sid, "generation", task_id, sid, None))
        for reviewer in ("A", "B"):
            result.append(
                (review_episode_id(batch_id, sid, reviewer), "review", task_id, sid, reviewer)
            )
    if len(tasks) != 1000 or any(indices != set(range(8)) for indices in tasks.values()):
        raise RequestPartitionError("exact 1000 tasks with eight original slots each required")
    result.extend((map_episode_id(batch_id, tid), "mapping", tid, None, None) for tid in tasks)
    return sorted(result)


def _record(connection, config):
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (PARTITION_KEY,)).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    if (
        record.get("id") != digest({k: v for k, v in record.items() if k != "id"})
        or record.get("config_sha256") != digest(config)
        or record.get("limits") != LIMITS
        or record.get("output_limits") != {k: list(v) for k, v in OUTPUT_LIMITS.items()}
        or record.get("network_policy") != NETWORK_POLICY
        or record.get("historical") != HISTORY
    ):
        raise RequestPartitionError("V10 partition/config/policy changed")
    return record


def allocated_requests(connection):
    """Small counter lookup used by the preserved V8 conservation check."""
    if (
        connection.execute("SELECT 1 FROM metadata WHERE key=?", (PARTITION_KEY,)).fetchone()
        is None
    ):
        return 0
    return connection.execute("SELECT COALESCE(SUM(requests),0) FROM v10_quotas").fetchone()[0]


def partition_snapshot(connection, config):
    record = _record(connection, config)
    if record is None:
        return None
    from .v10_funding import read_overlay

    funding = read_overlay(connection, config)
    effective_limits = {key: dict(value) for key, value in LIMITS.items()}
    from .v12_budget import effective_request_limits

    transferred_requests = effective_request_limits(connection, config)
    if transferred_requests is not None:
        for key, cap in transferred_requests.items():
            effective_limits[key]["requests"] = cap
    if funding is not None:
        effective_limits["review_mapping"]["microcny"] = funding[
            "effective_review_mapping_microcny"
        ]
    quotas = {r["category"]: dict(r) for r in connection.execute("SELECT * FROM v10_quotas")}
    if set(quotas) != set(LIMITS):
        raise RequestPartitionError("V10 subquota rows missing")
    for key, row in quotas.items():
        if (
            row["request_cap"] != LIMITS[key]["requests"]
            or row["money_cap"] != LIMITS[key]["microcny"]
            or any(
                type(row[k]) is not int or row[k] < 0
                for k in ("requests", "dispatched", "spent", "held", "pending", "unknown")
            )
            or row["requests"] > effective_limits[key]["requests"]
            or row["spent"] + row["held"] > effective_limits[key]["microcny"]
            or row["dispatched"] > row["requests"]
            or row["unknown"] + row["pending"] > row["requests"]
        ):
            raise RequestPartitionError("V10 dual subquota counters invalid")
    current = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
    baseline = record["historical_counters"]
    for key in ("requests", "dispatched", "spent", "held", "pending", "unknown"):
        if current[key] != baseline[key] + sum(q[key] for q in quotas.values()):
            raise RequestPartitionError("V10 and original wallet counters do not conserve")
    old = {
        r["category"]: r["consumed"] for r in connection.execute("SELECT * FROM v8_request_quotas")
    }
    if old != record["frozen_v8_consumed"]:
        raise RequestPartitionError("old generation/review dispatch quota changed after V10 freeze")
    result = {
        "id": record["id"],
        "batch_id": record["batch_id"],
        "limits": LIMITS,
        "consumed": {
            k: {f: q[f] for f in ("requests", "dispatched", "spent", "held", "pending", "unknown")}
            for k, q in quotas.items()
        },
        "unallocated_requests": UNALLOCATED_REQUESTS,
        "unallocated_microcny": UNALLOCATED_MICROCNY,
        "unallocated_spendable": False,
        "original_950_buffer_spendable": False,
        "old_namespaces_admitted": False,
        "output_limits": record["output_limits"],
        "roster_sha256": record["roster_sha256"],
    }
    if funding is not None:
        result.update(
            effective_limits=effective_limits,
            original_unallocated_microcny=UNALLOCATED_MICROCNY,
            unallocated_microcny=funding["effective_unallocated_microcny"],
            funding_overlay_id=funding["id"],
            generation_new_reservations_authorized=False,
        )
    return result


def _eligible(connection, config, coordinates, output_limit):
    if coordinates["episode_id"].startswith("v14"):
        from .v14_budget import eligible

        return eligible(connection, config, coordinates, output_limit)
    if coordinates["episode_id"].startswith("v13"):
        from .v13_budget import eligible

        return eligible(connection, config, coordinates, output_limit)
    if coordinates["episode_id"].startswith("v12"):
        from .v12_budget import eligible

        return eligible(connection, config, coordinates, output_limit)
    record = _record(connection, config)
    if record is None:
        return None
    row = connection.execute(
        "SELECT * FROM v10_episode_roster WHERE episode_id=?", (coordinates["episode_id"],)
    ).fetchone()
    if row is None:
        raise BudgetUnavailable("old/unallocated namespace or episode has no V10 capacity")
    if coordinates["attempt_index"] != 1:
        from .v10_network_retry import check_retry_admission

        check_retry_admission(connection, config, coordinates)
    if row["kind"] != "generation" and coordinates["turn_index"] != 0:
        raise BudgetUnavailable("V10 forbids retries and multiple review/mapping turns")
    if output_limit not in OUTPUT_LIMITS[row["kind"]]:
        raise ValueError("output cap outside this exact V10 purpose")
    return "generation" if row["kind"] == "generation" else "review_mapping"


def admit(connection, config, coordinates, output_limit, reservation, *, request_body=None):
    from .v12_budget import eligible, read_matrix_permit
    from .v13_budget import eligible as v13_eligible
    from .v13_budget import read_matrix_permit as read_v13_permit
    from .v14_budget import eligible as v14_eligible
    from .v14_budget import read_matrix_permit as read_v14_permit

    matrix = read_matrix_permit(connection, config)
    material = read_v13_permit(connection, config)
    residual = read_v14_permit(connection, config)
    if residual is not None:
        if (
            not coordinates["episode_id"].startswith(("v14projection:", "v14mapping:"))
            or request_body is None
        ):
            raise BudgetUnavailable("V14 permits only its exact new residual material purposes")
        v14_eligible(connection, config, coordinates, output_limit, request_body=request_body)
    elif material is not None:
        if (
            not coordinates["episode_id"].startswith(("v13projection:", "v13mapping:"))
            or request_body is None
        ):
            raise BudgetUnavailable("V13 permits only its new exact material-purpose matrix")
        v13_eligible(connection, config, coordinates, output_limit, request_body=request_body)
    elif matrix is not None:
        if not coordinates["episode_id"].startswith("v12review:") or request_body is None:
            raise BudgetUnavailable("V12 registration forbids old/unrelated reservations")
        eligible(connection, config, coordinates, output_limit, request_body=request_body)
    category = _eligible(connection, config, coordinates, output_limit)
    if category is None:
        return None
    if coordinates["attempt_index"] != 1:
        from .v10_network_retry import check_retry_admission

        if request_body is None:
            raise BudgetUnavailable("one-off attempt2 requires exact original HTTP bytes")
        check_retry_admission(connection, config, coordinates, request_body=request_body)
    from .v10_funding import read_overlay

    funding = read_overlay(connection, config)
    if funding is not None and category == "generation":
        raise BudgetUnavailable("V10 funding authorizes no new generation reservations")
    quota = connection.execute("SELECT * FROM v10_quotas WHERE category=?", (category,)).fetchone()
    request_cap = matrix["effective_request_limits"][category] if matrix else quota["request_cap"]
    if quota["requests"] >= request_cap:
        raise BudgetUnavailable(f"V10 {category} request sublimit exhausted; no borrowing")
    money_cap = (
        funding["effective_review_mapping_microcny"] if funding is not None else quota["money_cap"]
    )
    if quota["spent"] + quota["held"] + reservation > money_cap:
        raise BudgetUnavailable(
            f"V10 {category} settled+held money sublimit exhausted; no borrowing"
        )
    return category


DDL = (
    "CREATE TABLE v10_episode_roster (episode_id TEXT PRIMARY KEY,kind TEXT NOT NULL,"
    "task_id TEXT NOT NULL,slot_id TEXT,reviewer TEXT)",
    "CREATE TABLE v10_request_allocations (invocation_id TEXT PRIMARY KEY,category TEXT NOT NULL,"
    "episode_id TEXT NOT NULL)",
    "CREATE INDEX v10_allocation_category ON v10_request_allocations(category)",
    "CREATE INDEX IF NOT EXISTS v10_event_identity ON events(action,invocation_id)",
    "CREATE TABLE v10_quotas (category TEXT PRIMARY KEY,request_cap INTEGER NOT NULL,"
    "money_cap INTEGER NOT NULL,requests INTEGER NOT NULL DEFAULT 0,"
    "dispatched INTEGER NOT NULL DEFAULT 0,spent INTEGER NOT NULL DEFAULT 0,"
    "held INTEGER NOT NULL DEFAULT 0,pending INTEGER NOT NULL DEFAULT 0,"
    "unknown INTEGER NOT NULL DEFAULT 0)",
    """CREATE TRIGGER v10_reserved AFTER INSERT ON v10_request_allocations BEGIN
       UPDATE v10_quotas SET requests=requests+1,pending=pending+1,
       held=held+(SELECT reserved_microcny FROM requests WHERE invocation_id=NEW.invocation_id)
       WHERE category=NEW.category; END""",
    """CREATE TRIGGER v10_transition AFTER UPDATE OF state ON requests
       WHEN EXISTS(SELECT 1 FROM v10_request_allocations WHERE invocation_id=NEW.invocation_id)
       BEGIN UPDATE v10_quotas SET
       dispatched=dispatched+CASE WHEN OLD.state='RESERVED'
       AND NEW.state='DISPATCHED' THEN 1 ELSE 0 END,
       pending=pending-CASE WHEN OLD.state IN ('RESERVED','DISPATCHED')
       AND NEW.state IN ('SETTLED','UNKNOWN') THEN 1 ELSE 0 END,
       unknown=unknown+CASE WHEN NEW.state='UNKNOWN' AND OLD.state!='UNKNOWN' THEN 1 ELSE 0 END,
       spent=spent+CASE WHEN NEW.state='SETTLED' AND OLD.state!='SETTLED'
       THEN NEW.settled_microcny ELSE 0 END,
       held=held-CASE WHEN NEW.state='SETTLED' AND OLD.state!='SETTLED'
       THEN OLD.reserved_microcny ELSE 0 END
       WHERE category=(SELECT category FROM v10_request_allocations
       WHERE invocation_id=NEW.invocation_id); END""",
)


def register_v10_batch(
    path, *, expected_run_id, expected_config_sha256, batch_id, generation_slots, evidence
):
    """One prospective allocation in the original paid DB. Never create/reset it."""
    roster = _roster(batch_id, generation_slots)
    if not isinstance(evidence, dict) or not evidence.get("user_authorization"):
        raise RequestPartitionError("audit/user authority required")
    path = Path(path)
    if not path.is_file():
        raise RequestPartitionError("original wallet missing; V10 must not create it")
    signature = dict(
        batch_id=batch_id,
        config_sha256=expected_config_sha256,
        roster_sha256=digest(roster),
        evidence=evidence,
    )
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        try:
            config = json.loads(
                db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
            )
            if config["run_id"] != expected_run_id or digest(config) != expected_config_sha256:
                raise RequestPartitionError("original run/config differs")
            prior = _record(db, config)
            if prior is not None:
                if any(prior[k] != v for k, v in signature.items()):
                    raise RequestPartitionError("registered V10 partition cannot be replaced")
                return prior
            state = _budget_snapshot(db, config)
            counter = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
            if (
                config["purpose"] != V6_PURPOSE
                or state.get("effective_hard_cap_microcny") != 1_200_000_000
                or state["warning_microcny"] != 700_000_000
                or state["request_cap"] != 258000
                or state["halt"]
                or state["pending_requests"]
                or state["unacknowledged_unknown_requests"]
                or any(counter[k] != value for k, value in HISTORY.items())
                or state["acknowledged_unknown_requests"] != 65
                or state["acknowledged_unknown_held_microcny"] != HISTORY["held"]
                or "request_partition" not in state
            ):
                raise RequestPartitionError("exact quiescent stopped historical wallet required")
            rows = db.execute(
                "SELECT COUNT(*),SUM(COALESCE(settled_microcny,0)),"
                "SUM(CASE WHEN state!='SETTLED' THEN reserved_microcny ELSE 0 END),"
                "SUM(state='UNKNOWN'),SUM(state IN ('RESERVED','DISPATCHED')) FROM requests"
            ).fetchone()
            if tuple(rows) != (40076, HISTORY["spent"], HISTORY["held"], 65, 0):
                raise RequestPartitionError("historical rows/counters disagree")
            if db.execute(
                "SELECT 1 FROM requests WHERE "
                "json_extract(coordinates_json,'$.episode_id') LIKE 'v10%' LIMIT 1"
            ).fetchone():
                raise RequestPartitionError("new V10 namespaces already used without partition")
            if max(OUTPUT_LIMITS["review"]) > config["price_sheet"]["official_max_output_tokens"]:
                raise RequestPartitionError(
                    "V10 output ceiling exceeds frozen official tariff contract"
                )
            record = dict(
                schema="v10_dual_purpose_partition.v1",
                **signature,
                limits=LIMITS,
                output_limits={k: list(v) for k, v in OUTPUT_LIMITS.items()},
                historical=HISTORY,
                historical_counters=counter,
                frozen_v8_consumed=state["request_partition"]["consumed"],
                historical_acknowledgements_sha256=digest(_acknowledged_unknowns(db, config)),
                old_namespaces_admitted=False,
                network_policy=NETWORK_POLICY,
                unallocated_requests=UNALLOCATED_REQUESTS,
                unallocated_microcny=UNALLOCATED_MICROCNY,
                unallocated_spendable=False,
                original_950_buffer_spendable=False,
                registered_at_unix=time.time(),
            )
            record["id"] = digest(record)
            for statement in DDL:
                db.execute(statement)
            db.executemany("INSERT INTO v10_episode_roster VALUES (?,?,?,?,?)", roster)
            db.executemany(
                "INSERT INTO v10_quotas(category,request_cap,money_cap) VALUES (?,?,?)",
                [(k, v["requests"], v["microcny"]) for k, v in LIMITS.items()],
            )
            db.execute("INSERT INTO metadata VALUES (?,?)", (PARTITION_KEY, _json(record)))
            db.execute(
                "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
                (batch_id, "v10_partition_registered", _json(record), time.time()),
            )
            partition_snapshot(db, config)
            db.commit()
            return record
        except BaseException:
            db.rollback()
            raise


def open_budget(path):
    """Open only the existing immutable config; never substitute new caps in it."""
    config = read_budget_snapshot(path)["config"]
    kwargs = {
        k: config[k]
        for k in (
            "run_id",
            "price_sheet",
            "max_output_tokens",
            "purpose",
            "hard_cap_microcny",
            "warning_microcny",
            "request_cap",
        )
    }
    if "amendment_id" in config:
        kwargs.update(
            amendment_id=config["amendment_id"],
            allowed_output_limits=config["allowed_output_limits"],
        )
    return ProbeBudget(path, **kwargs)


def continue_reserved(ledger, invocation_id, *, coordinates, request, request_body):
    """Explicit exact-byte continuation of an undelivered reservation, not a retry.

    Caller must subsequently use mark_dispatched, whose atomic state transition
    permits at most one sender. DISPATCHED/UNKNOWN/SETTLED are never resent here.
    """
    with ledger._transaction() as db:
        row = db.execute(
            "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
        ).fetchone()
        if (
            row is None
            or row["state"] != "RESERVED"
            or row["dispatched_at"] is not None
            or any(row[k] is not None for k in ("response_body", "usage_json", "settled_microcny"))
            or coordinates.get("run_id") != ledger.run_id
            or invocation_identity(coordinates, turn_index=coordinates["turn_index"]) != coordinates
            or coordinates.get("invocation_id") != invocation_id
            or json.loads(row["coordinates_json"]) != coordinates
            or row["request_body"] != request_body
            or json.loads(request_body) != request
            or row["request_sha256"] != digest(request)
        ):
            raise DuplicateInvocation(
                "only exact original confirmed-unsent V10 reservation can continue"
            )
        if _eligible(db, ledger.config, coordinates, request["max_tokens"]) is None:
            raise BudgetUnavailable("V10 continuation requires its registered partition")
        state = ledger._snapshot(db)
        if state["halt"] or state["unacknowledged_unknown_requests"]:
            raise BudgetUnavailable("halted V10 reservation cannot dispatch")
        return row["reserved_microcny"]


def preflight(path):
    """Read-only status, including acknowledged UNKNOWN identities and all holds."""
    report = read_budget_snapshot(path)
    report["v10_registered"] = "v10_partition" in report["snapshot"]
    return report


budget_snapshot_v10 = preflight


def acknowledge_connection_unknowns(ledger, *, batch_id, expected_requests):
    """Explicit pending-zero terminal disposition, never inference or retry.

    expected_requests maps invocation_id to the exact request SHA256. The saved
    prospective policy applies only to this batch's dispatched connection errors.
    Returns immutable receipts; original rows, counters and holds do not change.
    """
    if not isinstance(expected_requests, dict) or not expected_requests:
        raise UnknownAbandonmentError("explicit nonempty request/hash set required")
    signature = dict(batch_id=batch_id, expected_requests=expected_requests)
    receipt_key = "v10_network_terminal:" + digest(signature)
    with ledger._transaction() as db:
        policy = _record(db, ledger.config)
        if policy is None or policy["batch_id"] != batch_id:
            raise UnknownAbandonmentError("new batch prospective network policy absent")
        acknowledged = {r["invocation_id"]: r for r in _acknowledged_unknowns(db, ledger.config)}
        prior = db.execute("SELECT value FROM metadata WHERE key=?", (receipt_key,)).fetchone()
        if prior:
            receipt = json.loads(prior[0])
            if (
                receipt.get("id") != digest({k: v for k, v in receipt.items() if k != "id"})
                or receipt.get("partition_id") != policy["id"]
                or any(receipt.get(k) != v for k, v in signature.items())
                or any(acknowledged.get(r["invocation_id"]) != r for r in receipt["records"])
                or not db.execute(
                    "SELECT 1 FROM events WHERE action='v10_connection_unknown_terminal' "
                    "AND invocation_id=? AND payload_json=?",
                    (receipt_key, prior[0]),
                ).fetchone()
            ):
                raise UnknownAbandonmentError("saved terminal receipt binding changed")
            return receipt  # Does not clear any later halt.
        state = ledger._snapshot(db)
        unknown = {
            r["invocation_id"]: r
            for r in db.execute("SELECT * FROM requests WHERE state='UNKNOWN'")
        }
        unack = set(unknown) - set(acknowledged)
        if (
            state["pending_requests"]
            or unack != set(expected_requests) - set(acknowledged)
            or not unack
        ):
            raise UnknownAbandonmentError("complete unacknowledged set at pending zero required")
        evidence_by_id = {}
        for iid, sha in expected_requests.items():
            row = unknown.get(iid)
            if row is None:
                raise UnknownAbandonmentError("only original UNKNOWN rows may be acknowledged")
            coordinates = json.loads(row["coordinates_json"])
            request = json.loads(row["request_body"])
            evidence = json.loads(row["evidence_json"] or "{}")
            events = db.execute(
                "SELECT payload_json FROM events WHERE invocation_id=? AND action='unknown' "
                "ORDER BY sequence DESC LIMIT 1",
                (iid,),
            ).fetchone()
            event = json.loads(events[0]) if events else {}
            allocation = db.execute(
                "SELECT * FROM v10_request_allocations WHERE invocation_id=?", (iid,)
            ).fetchone()
            if (
                allocation is None
                or coordinates.get("run_id") != ledger.run_id
                or invocation_identity(coordinates, turn_index=coordinates["turn_index"])
                != coordinates
                or coordinates.get("invocation_id") != iid
                or allocation["episode_id"] != coordinates["episode_id"]
                or _eligible(db, ledger.config, coordinates, request.get("max_tokens"))
                != allocation["category"]
                or row["dispatched_at"] is None
                or any(
                    row[k] is not None
                    for k in (
                        "usage_json",
                        "settled_microcny",
                        "settled_at",
                        "http_status",
                        "response_body",
                        "response_sha256",
                    )
                )
                or row["response_classification"] != "unknown"
                or row["request_sha256"] != sha
                or digest(request) != sha
                or request.get("model") != "deepseek-flash"
                or request.get("thinking") != {"type": "disabled"}
                or row["reserved_microcny"]
                != ledger.price_sheet.cost_microcny(
                    hit=0,
                    miss=ledger.price_sheet.context_input_token_ceiling,
                    output=request["max_tokens"],
                )
                or evidence.get("exception_type") not in V9_NETWORK_EXCEPTIONS
                or evidence.get("service_response_received") is not False
                or evidence.get("budget_invocation_id") != iid
                or evidence.get("budget_coordinates") != coordinates
                or evidence.get("request_sha256") != sha
                or event
                != dict(reason=NETWORK_REASON, http_status=None, response_classification="unknown")
            ):
                raise UnknownAbandonmentError(
                    "not an exact dispatched V10 no-response connection UNKNOWN"
                )
            evidence_by_id[iid] = evidence
        halt_row = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        halt = json.loads(halt_row[0]) if halt_row else {}
        if (
            halt.get("invocation_id") not in unack
            or halt.get("reason") != NETWORK_REASON
            or halt.get("evidence") != evidence_by_id.get(halt.get("invocation_id"))
        ):
            raise UnknownAbandonmentError("current halt is not exactly covered by this network set")
        active = db.execute(
            "SELECT sequence FROM events WHERE action='halt' AND payload_json=? "
            "ORDER BY sequence DESC LIMIT 1",
            (halt_row[0],),
        ).fetchone()
        if active is None:
            raise UnknownAbandonmentError("active halt event absent")
        for event in db.execute(
            "SELECT payload_json FROM events WHERE action='halt' AND sequence>=?", (active[0],)
        ):
            item = json.loads(event[0])
            if (
                item.get("invocation_id") not in unack
                or item.get("reason") != NETWORK_REASON
                or item.get("evidence") != evidence_by_id.get(item.get("invocation_id"))
            ):
                raise UnknownAbandonmentError(
                    "later non-network/uncovered halt must remain stopped"
                )
        records = []
        for iid in sorted(expected_requests):
            if iid in acknowledged:
                record = acknowledged[iid]
            else:
                row = unknown[iid]
                record = dict(
                    schema="v10_connection_unknown_acknowledgement.v1",
                    run_id=ledger.run_id,
                    batch_id=batch_id,
                    partition_id=policy["id"],
                    invocation_id=iid,
                    expected_request_sha256=row["request_sha256"],
                    permanent_reserved_microcny=row["reserved_microcny"],
                    original_unknown_record_sha256=_request_record_digest(row),
                    actual_charge_known=False,
                    reservation_released=False,
                    retry_authorized=False,
                    model_response=None,
                    model_usage=None,
                    model_result=None,
                    material_eligible=False,
                    registered_at_unix=time.time(),
                )
                record["id"] = digest(record)
                db.execute(
                    "INSERT INTO metadata VALUES (?,?)",
                    (UNKNOWN_ABANDONMENT_PREFIX + iid, _json(record)),
                )
                ledger._event(db, iid, UNKNOWN_ABANDONMENT_ACTION, record)
            records.append(record)
        if (
            db.execute("DELETE FROM metadata WHERE key='halt' AND value=?", (halt_row[0],)).rowcount
            != 1
        ):
            raise UnknownAbandonmentError("covered halt changed during transaction")
        receipt = dict(
            schema="v10_connection_unknown_terminal_receipt.v1",
            **signature,
            partition_id=policy["id"],
            records=records,
            cleared_exact_halt=halt,
            new_acknowledgements=len(unack),
            original_rows_unchanged=True,
            permanent_holds_unchanged=True,
            automatic_resend=False,
        )
        receipt["id"] = digest(receipt)
        db.execute("INSERT INTO metadata VALUES (?,?)", (receipt_key, _json(receipt)))
        ledger._event(db, receipt_key, "v10_connection_unknown_terminal", receipt)
        return receipt
