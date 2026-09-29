"""Independent Probe monetary ledger: reserve before HTTP, settle actual token usage.

All money is integer micro-CNY, rounded upward per request using a frozen official
tariff. Each frozen run cap covers settled cost plus all pending/unknown reservations.
Historical defaults remain 800 CNY / 700 CNY warning / 256000 requests; a new
purpose must explicitly register its own limits rather than inherit prior spend.
This is tariff accounting from actual usage, not a fabricated provider invoice.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from urllib.parse import urlparse

from .contracts import digest, invocation_identity

HARD_CAP_MICROCNY = 800_000_000
WARNING_MICROCNY = 700_000_000
REQUEST_CAP = 256_000
PURPOSE = "finqa_fixed_probe_inventory_v1"
V6_PURPOSE = "finqa_v6_generation_and_semantic_review_v1"
V6_REVIEW_AMENDMENT_PAUSE = "user_authorized_review_capacity_audit"
V6_REVIEW_AMENDMENT_ACTION = "v6_review_capacity_amended"
UNKNOWN_ABANDONMENT_PREFIX = "acknowledged_unknown:"
UNKNOWN_ABANDONMENT_ACTION = "unknown_abandonment_acknowledged"
V8_PARTITION_KEY = "v8_request_partition"
V8_PARTITION_LIMITS = {"generation": 220000, "technical_review": 108, "production_review": 18000}
V9_MONETARY_AMENDMENT_KEY = "v9_prospective_monetary_amendment"
V9_MONETARY_AMENDMENT_ACTION = "v9_prospective_monetary_limit_authorized"
V9_AUTHORIZED_TOTAL_MICROCNY = 1_200_000_000
V9_NETWORK_PROTOCOL_ID = "5ed407ae0906a38698c13729e213cfb6178c0494bd26b54e864bd0e715f0361f"
V9_NETWORK_UNKNOWN_REASON = "review transport response or usage unknown"
V9_NETWORK_EXCEPTIONS = frozenset(
    {
        "RemoteProtocolError",
        "ReadError",
        "WriteError",
        "ConnectError",
        "ReadTimeout",
        "WriteTimeout",
        "ConnectTimeout",
    }
)
V9_NETWORK_BATCH_PREFIX = "v9_network_unknown_batch:"
V9_NETWORK_BATCH_ACTION = "v9_network_unknown_batch_acknowledged"


def validated_budget_limits(
    *,
    hard_cap_microcny=HARD_CAP_MICROCNY,
    warning_microcny=WARNING_MICROCNY,
    request_cap=REQUEST_CAP,
):
    """Return explicit immutable-registration values, never floats or booleans."""
    values = {
        "hard_cap_microcny": hard_cap_microcny,
        "warning_microcny": warning_microcny,
        "request_cap": request_cap,
    }
    if any(type(value) is not int or not 0 < value <= 2**63 - 1 for value in values.values()):
        raise ValueError("budget limits must be positive SQLite-range integers")
    if warning_microcny > hard_cap_microcny:
        raise ValueError("budget warning threshold cannot exceed the hard cap")
    return values


def _json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


class BudgetUnavailable(RuntimeError):
    """No request was sent; the cap or a recorded unknown forbids new work."""


class DuplicateInvocation(RuntimeError):
    """A persisted invocation must never be sent for a second time."""


class InvalidUsage(ValueError):
    """The response does not establish complete tariff-accountable token usage."""


class BudgetAmendmentError(ValueError):
    """An explicit review-capacity amendment cannot change this ledger safely."""


class UnknownAbandonmentError(ValueError):
    """A particular unresolved paid request lacks auditable abandonment authority."""


class RequestPartitionError(ValueError):
    """The new dispatch partition cannot change historical charges or allocation."""


def _v9_authorization(value, *, config_sha256, hard_cap_microcny):
    if (
        not isinstance(value, dict)
        or value.get("schema") != "v9_production_funding_decision.v1"
        or value.get("id") != digest({k: v for k, v in value.items() if k != "id"})
        or value.get("explicit_user_authorization") is not True
        or value.get("user_reply") != "批准1200元总上限及上述风险"
        or value.get("risk_of_incomplete_cohort_accepted") is not True
        or value.get("strategy") != "bounded_full_cohort_attempt"
        or value.get("no_prefix_training") is not True
        or value.get("hard_cap_microcny") != hard_cap_microcny
        or value.get("budget_config_sha256") != config_sha256
        or value.get("preflight_id")
        != "ceeb89519387dfd98e47015128137b9fe901689644c9b4f42391782f399ce4bc"
    ):
        raise BudgetAmendmentError("explicit bound V9 1200-CNY funding authorization required")


def _v9_monetary_amendment(connection, config):
    """Read/validate an append-only overlay; original config bytes never change."""
    row = connection.execute(
        "SELECT value FROM metadata WHERE key=?", (V9_MONETARY_AMENDMENT_KEY,)
    ).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    cap = record.get("effective_hard_cap_microcny")
    if (
        record.get("schema") != "v9_prospective_monetary_amendment.v1"
        or record.get("id") != digest({k: v for k, v in record.items() if k != "id"})
        or record.get("run_id") != config["run_id"]
        or record.get("config_sha256") != digest(config)
        or config["purpose"] != V6_PURPOSE
        or record.get("original_hard_cap_microcny") != config["hard_cap_microcny"]
        or config["hard_cap_microcny"] != HARD_CAP_MICROCNY
        or type(cap) is not int
        or cap != V9_AUTHORIZED_TOTAL_MICROCNY
        or record.get("preserved_warning_microcny") != config["warning_microcny"]
        or record.get("preserved_request_cap") != config["request_cap"]
        or (config["warning_microcny"], config["request_cap"]) != (700000000, 258000)
        or record.get("applied_after_requests") != 35336
        or not connection.execute(
            "SELECT 1 FROM events WHERE invocation_id=? AND action=? AND payload_json=?",
            (record.get("amendment_id"), V9_MONETARY_AMENDMENT_ACTION, row[0]),
        ).fetchone()
    ):
        raise BudgetAmendmentError("V9 prospective monetary authorization/config changed")
    _v9_authorization(
        record.get("authorization"), config_sha256=digest(config), hard_cap_microcny=cap
    )
    partition = _partition_snapshot(connection, config)
    if partition is None or partition["id"] != record.get("request_partition_id"):
        raise BudgetAmendmentError("V9 monetary overlay must preserve its V8 request partition")
    return record


def apply_v9_monetary_amendment(
    path,
    *,
    expected_run_id,
    expected_config_sha256,
    amendment_id,
    effective_hard_cap_microcny,
    authorization,
):
    """Apply the user's explicit 800→1200-CNY authorization to the SAME wallet.

    Only metadata plus its matching event are appended. Configuration, fees,
    request rows, permanent UNKNOWN holds, warning and request partitions remain
    unchanged. Repeating the identical authorization is read-only, including after
    later requests. No broader API permission is treated as a budget authorization.
    """
    if (
        type(effective_hard_cap_microcny) is not int
        or effective_hard_cap_microcny != V9_AUTHORIZED_TOTAL_MICROCNY
        or not isinstance(amendment_id, str)
        or not amendment_id.strip()
        or not isinstance(expected_run_id, str)
        or not expected_run_id.strip()
    ):
        raise BudgetAmendmentError("only the explicit V9 1200-CNY total-cap amendment is supported")
    _v9_authorization(
        authorization,
        config_sha256=expected_config_sha256,
        hard_cap_microcny=effective_hard_cap_microcny,
    )
    path = Path(path)
    if not path.is_file():
        raise BudgetAmendmentError("original paid ledger missing; amendment cannot create it")
    with closing(
        sqlite3.connect(
            path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None
        )
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            stored = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
            if stored is None:
                raise BudgetAmendmentError("original paid configuration missing")
            config = json.loads(stored[0])
            if (
                config.get("run_id") != expected_run_id
                or digest(config) != expected_config_sha256
                or config.get("purpose") != V6_PURPOSE
                or (
                    config.get("hard_cap_microcny"),
                    config.get("warning_microcny"),
                    config.get("request_cap"),
                )
                != (800000000, 700000000, 258000)
            ):
                raise BudgetAmendmentError("exact original 800/700/258000 joint wallet required")
            signature = dict(
                amendment_id=amendment_id,
                run_id=expected_run_id,
                config_sha256=expected_config_sha256,
                effective_hard_cap_microcny=effective_hard_cap_microcny,
                authorization=json.loads(_json(authorization)),
            )
            prior = _v9_monetary_amendment(connection, config)
            if prior is not None:
                if any(prior.get(k) != v for k, v in signature.items()):
                    raise BudgetAmendmentError(
                        "existing V9 monetary authorization cannot be replaced"
                    )
                connection.rollback()
                return prior
            snapshot = _budget_snapshot(connection, config)
            partition = snapshot.get("request_partition")
            if (
                snapshot["pending_requests"]
                or snapshot["unacknowledged_unknown_requests"]
                or snapshot["halt"]
                or snapshot["requests_reserved"] != 35336
                or snapshot["exposure_microcny"] > HARD_CAP_MICROCNY
                or partition is None
                or partition["consumed"]
                != dict(generation=16286, technical_review=108, production_review=0)
            ):
                raise BudgetAmendmentError(
                    "V9 cap registration requires settled 35336-call preproduction history"
                )
            counters = dict(
                connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
            )
            totals = connection.execute(
                "SELECT COUNT(*) AS requests, "
                "SUM(CASE WHEN dispatched_at IS NOT NULL THEN 1 ELSE 0 END) AS dispatched, "
                "SUM(CASE WHEN state='SETTLED' THEN settled_microcny ELSE 0 END) AS spent, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED','UNKNOWN') "
                "THEN reserved_microcny ELSE 0 END) AS held, "
                "SUM(CASE WHEN state='UNKNOWN' THEN 1 ELSE 0 END) AS unknown, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED') THEN 1 ELSE 0 END) AS pending "
                "FROM requests"
            ).fetchone()
            if any(
                counters[k] != totals[k]
                for k in ("requests", "dispatched", "spent", "held", "unknown", "pending")
            ):
                raise BudgetAmendmentError(
                    "original request/fee/reservation counters must conserve"
                )
            original_records = [
                dict(r)
                for r in connection.execute(
                    "SELECT invocation_id,coordinates_json,state,"
                    "reserved_microcny,settled_microcny,"
                    "request_sha256,response_sha256,usage_json FROM requests ORDER BY invocation_id"
                )
            ]
            body = dict(
                schema="v9_prospective_monetary_amendment.v1",
                **signature,
                at_unix=time.time(),
                original_hard_cap_microcny=config["hard_cap_microcny"],
                preserved_warning_microcny=config["warning_microcny"],
                preserved_request_cap=config["request_cap"],
                request_partition_id=partition["id"],
                applied_after_requests=35336,
                preserved_counters=counters,
                historical_request_records_sha256=digest(original_records),
                acknowledged_unknowns_sha256=digest(_acknowledged_unknowns(connection, config)),
                wallet_config_unchanged=True,
                historical_rows_unchanged=True,
                permanent_unknown_holds_unchanged=True,
                request_partition_unchanged=True,
                applies_to_future_reservations_only=True,
                completion_guarantee=False,
            )
            record = {**body, "id": digest(body)}
            connection.execute(
                "INSERT INTO metadata VALUES (?,?)", (V9_MONETARY_AMENDMENT_KEY, _json(record))
            )
            connection.execute(
                "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
                (amendment_id, V9_MONETARY_AMENDMENT_ACTION, _json(record), record["at_unix"]),
            )
            connection.commit()
            return record
        except BaseException:
            connection.rollback()
            raise


def _partition_snapshot(connection, config):
    stored = connection.execute(
        "SELECT value FROM metadata WHERE key=?", (V8_PARTITION_KEY,)
    ).fetchone()
    if stored is None:
        return None
    record = json.loads(stored[0])
    if (
        record.get("id") != digest({k: v for k, v in record.items() if k != "id"})
        or record.get("config_sha256") != digest(config)
        or record.get("limits") != V8_PARTITION_LIMITS
    ):
        raise RequestPartitionError("registered request partition/config changed")
    counts = {
        row["category"]: dict(row) for row in connection.execute("SELECT * FROM v8_request_quotas")
    }
    if set(counts) != set(V8_PARTITION_LIMITS) or any(
        row["quota"] != V8_PARTITION_LIMITS[key] or not 0 <= row["consumed"] <= row["quota"]
        for key, row in counts.items()
    ):
        raise RequestPartitionError("request subquota counters changed")
    requests = connection.execute("SELECT requests FROM counters WHERE singleton=1").fetchone()[0]
    if requests != record["historical_requests"] + sum(row["consumed"] for row in counts.values()):
        raise RequestPartitionError("partition and original request counters do not conserve")
    return dict(
        id=record["id"],
        partition_id=record["partition_id"],
        historical_requests=record["historical_requests"],
        limits=record["limits"],
        consumed={k: v["consumed"] for k, v in counts.items()},
        buffer_requests=950,
        buffer_spendable=False,
        generation_episode_ids_sha256=record["generation_episode_ids_sha256"],
    )


def apply_v8_request_partition(
    path, *, expected_run_id, expected_config_sha256, partition_id, generation_episode_ids, evidence
):
    """One auditable allocation of existing capacity; never create/reset a wallet.

    Idempotent only for the identical authorized partition. Existing UNKNOWN rows,
    their permanent holds and the original 800/700 CNY/258000 limits remain intact.
    """
    ids = sorted(generation_episode_ids)
    if (
        not isinstance(partition_id, str)
        or not partition_id.strip()
        or len(ids) != 8000
        or len(set(ids)) != 8000
        or any(not isinstance(sid, str) or not sid.startswith("v7-slot:") for sid in ids)
        or not isinstance(evidence, dict)
        or not evidence.get("user_authorization")
    ):
        raise RequestPartitionError(
            "explicit authorization and exact original 8000 V7 slots required"
        )
    path = Path(path)
    if not path.is_file():
        raise RequestPartitionError("original paid ledger missing; partition cannot create it")
    with closing(
        sqlite3.connect(
            path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None
        )
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            config = json.loads(
                connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
            )
            if (
                config["run_id"] != expected_run_id
                or digest(config) != expected_config_sha256
                or config["purpose"] != V6_PURPOSE
                or (config["hard_cap_microcny"], config["warning_microcny"], config["request_cap"])
                != (800000000, 700000000, 258000)
            ):
                raise RequestPartitionError("partition must retain the exact original joint wallet")
            signature = dict(
                partition_id=partition_id,
                run_id=expected_run_id,
                config_sha256=expected_config_sha256,
                generation_episode_ids_sha256=digest(ids),
                evidence=evidence,
            )
            prior = connection.execute(
                "SELECT value FROM metadata WHERE key=?", (V8_PARTITION_KEY,)
            ).fetchone()
            if prior:
                record = json.loads(prior[0])
                if any(record.get(k) != v for k, v in signature.items()):
                    raise RequestPartitionError("existing partition cannot be replaced or expanded")
                _partition_snapshot(connection, config)
                connection.rollback()
                return record
            snapshot = _budget_snapshot(connection, config)
            if (
                snapshot["halt"]
                or snapshot["pending_requests"]
                or snapshot["unacknowledged_unknown_requests"]
            ):
                raise RequestPartitionError(
                    "partition registration requires quiescent, unhalted accounted history"
                )
            counters = dict(
                connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
            )
            rows = connection.execute(
                "SELECT invocation_id,coordinates_json,state,reserved_microcny,"
                "settled_microcny,request_sha256,response_sha256 FROM requests "
                "ORDER BY invocation_id"
            ).fetchall()
            if (
                counters["requests"] != 18942
                or len(rows) != 18942
                or any(r["state"] not in {"SETTLED", "UNKNOWN"} for r in rows)
                or sum(r["state"] == "UNKNOWN" for r in rows) != counters["unknown"]
                or any(
                    r["state"] == "SETTLED"
                    and (type(r["settled_microcny"]) is not int or r["settled_microcny"] < 0)
                    for r in rows
                )
                or counters["spent"] != sum(r["settled_microcny"] or 0 for r in rows)
                or counters["held"]
                != sum(r["reserved_microcny"] for r in rows if r["state"] == "UNKNOWN")
                or counters["requests"] + sum(V8_PARTITION_LIMITS.values()) + 950 != 258000
            ):
                raise RequestPartitionError(
                    "historical 18942 requests and all monetary holds must conserve"
                )
            allowed = set(ids)
            if any(
                json.loads(r["coordinates_json"])["episode_id"] in allowed
                or json.loads(r["coordinates_json"])["episode_id"].startswith(
                    ("v8review:", "v8prod:")
                )
                for r in rows
            ):
                raise RequestPartitionError(
                    "new partition namespaces already contain paid attempts"
                )
            body = dict(
                schema="v8_joint_request_partition.v1",
                **signature,
                at_unix=time.time(),
                limits=V8_PARTITION_LIMITS,
                historical_requests=18942,
                buffer_requests=950,
                buffer_spendable=False,
                generation_episode_count=8000,
                preserved_counters=counters,
                historical_request_records_sha256=digest([dict(r) for r in rows]),
                old_unknowns_preserved=snapshot["acknowledged_unknown_requests"],
                wallet_config_unchanged=True,
                old_namespace_new_dispatch_allowed=False,
            )
            record = {**body, "id": digest(body)}
            connection.execute("CREATE TABLE v8_generation_slots (episode_id TEXT PRIMARY KEY)")
            connection.execute(
                "CREATE TABLE v8_request_quotas (category TEXT PRIMARY KEY, "
                "quota INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE TABLE v8_request_allocations (invocation_id TEXT PRIMARY KEY, "
                "category TEXT NOT NULL, episode_id TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO v8_generation_slots VALUES (?)", [(sid,) for sid in ids]
            )
            connection.executemany(
                "INSERT INTO v8_request_quotas(category,quota) VALUES (?,?)",
                V8_PARTITION_LIMITS.items(),
            )
            connection.execute(
                "INSERT INTO metadata VALUES (?,?)", (V8_PARTITION_KEY, _json(record))
            )
            connection.execute(
                "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
                (partition_id, "v8_request_partition_registered", _json(record), time.time()),
            )
            connection.commit()
            return record
        except BaseException:
            connection.rollback()
            raise


def _partition_admit(connection, config, coordinates):
    partition = _partition_snapshot(connection, config)
    if partition is None:
        return None
    sid = coordinates["episode_id"]
    if coordinates["attempt_index"] != 1:
        raise BudgetUnavailable("partition never authorizes an episode retry")
    if sid.startswith("v7-slot:"):
        if not connection.execute(
            "SELECT 1 FROM v8_generation_slots WHERE episode_id=?", (sid,)
        ).fetchone():
            raise BudgetUnavailable("generation slot is outside the exact original new batch")
        category = "generation"
    elif sid.startswith("v8review:") or sid.startswith("v8prod:"):
        if coordinates["turn_index"] != 0:
            raise BudgetUnavailable("each isolated review has one registered request only")
        category = "technical_review" if sid.startswith("v8review:") else "production_review"
    else:
        raise BudgetUnavailable("old/unallocated namespace has no new request partition")
    if partition["consumed"][category] >= partition["limits"][category]:
        raise BudgetUnavailable(f"{category} request partition exhausted; buffer is not spendable")
    return category


def _request_record_digest(row):
    return digest(
        {
            key: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            if isinstance(value, bytes)
            else value
            for key, value in dict(row).items()
        }
    )


def _acknowledged_unknowns(connection, config):
    records = []
    for item in connection.execute(
        "SELECT key,value FROM metadata WHERE key GLOB ? ORDER BY key",
        (UNKNOWN_ABANDONMENT_PREFIX + "*",),
    ):
        record = json.loads(item["value"])
        iid = record.get("invocation_id")
        row = connection.execute("SELECT * FROM requests WHERE invocation_id=?", (iid,)).fetchone()
        if (
            record.get("id") != digest({k: v for k, v in record.items() if k != "id"})
            or item["key"] != UNKNOWN_ABANDONMENT_PREFIX + str(iid)
            or record.get("run_id") != config["run_id"]
            or config["purpose"] != V6_PURPOSE
            or row is None
            or row["state"] != "UNKNOWN"
            or row["usage_json"] is not None
            or row["settled_microcny"] is not None
            or row["settled_at"] is not None
            or row["reserved_microcny"] != record.get("permanent_reserved_microcny")
            or row["request_sha256"] != record.get("expected_request_sha256")
            or _request_record_digest(row) != record.get("original_unknown_record_sha256")
            or not connection.execute(
                "SELECT 1 FROM events WHERE action=? AND invocation_id=? AND payload_json=?",
                (UNKNOWN_ABANDONMENT_ACTION, iid, item["value"]),
            ).fetchone()
        ):
            raise UnknownAbandonmentError(
                "acknowledged unknown no longer binds its original held request"
            )
        records.append(record)
    return records


def _budget_snapshot(connection, config):
    row = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
    halt = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
    acknowledged = _acknowledged_unknowns(connection, config)
    acknowledged_hold = sum(r["permanent_reserved_microcny"] for r in acknowledged)
    if len(acknowledged) > row["unknown"] or acknowledged_hold > row["held"]:
        raise UnknownAbandonmentError(
            "acknowledged reservations are not conserved in original counters"
        )
    spent, held = row["spent"], row["held"]
    monetary = _v9_monetary_amendment(connection, config)
    effective_cap = (
        monetary["effective_hard_cap_microcny"] if monetary else config["hard_cap_microcny"]
    )
    result = {
        "run_id": config["run_id"],
        "purpose": config["purpose"],
        "requests_reserved": row["requests"],
        "requests_dispatched": row["dispatched"],
        "settled_tariff_microcny": spent,
        "held_microcny": held,
        "exposure_microcny": spent + held,
        "remaining_exposure_microcny": effective_cap - spent - held,
        "hard_cap_microcny": config["hard_cap_microcny"],
        "warning_microcny": config["warning_microcny"],
        "request_cap": config["request_cap"],
        "warning_reached": spent >= config["warning_microcny"],
        "exposure_warning_reached": spent + held >= config["warning_microcny"],
        "unknown_requests": row["unknown"],
        "pending_requests": row["pending"],
        "acknowledged_unknown_requests": len(acknowledged),
        "unacknowledged_unknown_requests": row["unknown"] - len(acknowledged),
        "acknowledged_unknown_held_microcny": acknowledged_hold,
        "actual_prompt_tokens_settled": row["prompt_tokens"],
        "actual_cache_hit_tokens_settled": row["hit_tokens"],
        "actual_cache_miss_tokens_settled": row["miss_tokens"],
        "actual_completion_tokens_settled": row["completion_tokens"],
        "halt": json.loads(halt[0]) if halt else None,
        "price_sheet_id": config["price_sheet_id"],
        "cost_semantics": "upward-rounded peak-tariff upper bound applied to actual usage; "
        "not a provider invoice",
    }
    partition = _partition_snapshot(connection, config)
    if partition is not None:
        result["request_partition"] = partition
    if monetary is not None:
        result.update(
            effective_hard_cap_microcny=effective_cap,
            original_remaining_exposure_microcny=config["hard_cap_microcny"] - spent - held,
            monetary_amendment=monetary,
        )
    return result


def read_budget_snapshot(path):
    """Read original config/counters/abandonments without creating or migrating a ledger."""
    path = Path(path)
    if not path.is_file():
        raise UnknownAbandonmentError(
            "original paid ledger missing; read-only snapshot cannot create it"
        )
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        row = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        if row is None:
            raise UnknownAbandonmentError("original paid configuration missing")
        config = json.loads(row[0])
        return dict(
            config=config,
            config_sha256=digest(config),
            snapshot=_budget_snapshot(connection, config),
            acknowledged_unknowns=_acknowledged_unknowns(connection, config),
            request_counts_by_state={
                r[0]: r[1]
                for r in connection.execute("SELECT state,COUNT(*) FROM requests GROUP BY state")
            },
            read_only=True,
        )


def _review_output_limits(value, *, official_max_output_tokens):
    if (
        not isinstance(value, (list, tuple))
        or any(
            type(item) is not int or not 0 < item <= official_max_output_tokens for item in value
        )
        or len(value) != len(set(value))
        or not {2048, 16384} <= set(value)
        or any(item not in {2048, 16384} and item <= 16384 for item in value)
    ):
        raise BudgetAmendmentError(
            "explicit distinct review limits must retain 2048/16384 "
            "and only add larger official caps"
        )
    return tuple(sorted(value))


@dataclass(frozen=True)
class ProbePriceSheet:
    input_hit_cny_per_million: str
    input_miss_cny_per_million: str
    output_cny_per_million: str
    context_input_token_ceiling: int
    official_max_output_tokens: int
    source_url: str
    checked_at_utc: str
    source_sha256: str
    model: str = "deepseek-flash"
    currency: str = "CNY"
    pricing_policy: str = "conservative_peak_upper_bound_all_hours"

    def __post_init__(self):
        rates = (
            self.input_hit_cny_per_million,
            self.input_miss_cny_per_million,
            self.output_cny_per_million,
        )
        if any(
            not isinstance(value, str) or not Decimal(value).is_finite() or Decimal(value) < 0
            for value in rates
        ):
            raise ValueError("tariff rates must be finite nonnegative Decimal strings")
        if Decimal(rates[0]) > Decimal(rates[1]):
            raise ValueError("cache-hit price exceeds the miss-price reservation bound")
        if (
            self.model != "deepseek-flash"
            or self.currency != "CNY"
            or self.pricing_policy != "conservative_peak_upper_bound_all_hours"
        ):
            raise ValueError("Probe tariff must bind deepseek-flash and CNY")
        if any(
            type(v) is not int or v <= 0
            for v in (self.context_input_token_ceiling, self.official_max_output_tokens)
        ):
            raise ValueError("official token ceilings must be positive integers")
        if urlparse(self.source_url).hostname not in {
            "api-docs.deepseek.com",
            "platform.deepseek.com",
            "www.deepseek.com",
            "deepseek.com",
        }:
            raise ValueError("an official DeepSeek tariff source is required")
        if (
            not self.checked_at_utc
            or len(self.source_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.source_sha256)
        ):
            raise ValueError("the retrieved official tariff evidence must be hash-bound")

    @property
    def id(self):
        return "probe_price_sheet:" + digest(asdict(self))

    def cost_microcny(self, *, hit: int, miss: int, output: int) -> int:
        if any(type(value) is not int or value < 0 for value in (hit, miss, output)):
            raise InvalidUsage("usage counts must be nonnegative integers")
        # CNY / 1e6 tokens times 1e6 micro-CNY / CNY cancels exactly.
        amount = (
            Decimal(self.input_hit_cny_per_million) * hit
            + Decimal(self.input_miss_cny_per_million) * miss
            + Decimal(self.output_cny_per_million) * output
        )
        return int(amount.to_integral_value(rounding=ROUND_CEILING))

    def usage(self, value, *, output_limit):
        if not isinstance(value, dict):
            raise InvalidUsage("API usage is missing")
        names = (
            "prompt_tokens",
            "completion_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
        if any(type(value.get(name)) is not int or value[name] < 0 for name in names):
            raise InvalidUsage(
                "complete integer prompt/output/cache-hit/cache-miss counters required"
            )
        if (
            value["prompt_cache_hit_tokens"] + value["prompt_cache_miss_tokens"]
            != value["prompt_tokens"]
        ):
            raise InvalidUsage("cache counters do not sum to actual prompt tokens")
        if (
            type(value.get("total_tokens")) is not int
            or value["total_tokens"] != value["prompt_tokens"] + value["completion_tokens"]
        ):
            raise InvalidUsage("total token count disagrees with prompt plus completion")
        details = value.get("prompt_tokens_details")
        if details is not None and (
            not isinstance(details, dict)
            or (
                "cached_tokens" in details
                and (
                    type(details["cached_tokens"]) is not int
                    or details["cached_tokens"] != value["prompt_cache_hit_tokens"]
                )
            )
        ):
            raise InvalidUsage("optional cached_tokens differs from cache-hit usage")
        completion_details = value.get("completion_tokens_details")
        if completion_details is not None and (
            not isinstance(completion_details, dict)
            or (
                "reasoning_tokens" in completion_details
                and (
                    type(completion_details["reasoning_tokens"]) is not int
                    or not 0 <= completion_details["reasoning_tokens"] <= value["completion_tokens"]
                )
            )
        ):
            raise InvalidUsage("invalid optional reasoning token accounting")
        if (
            value["prompt_tokens"] > self.context_input_token_ceiling
            or value["completion_tokens"] > output_limit
        ):
            raise InvalidUsage(
                "returned usage exceeds the registered official reservation envelope"
            )
        return {name: value[name] for name in names}


def apply_v6_review_amendment(
    path,
    *,
    expected_run_id,
    expected_config_sha256,
    amendment_id,
    allowed_review_output_limits,
    evidence,
):
    """Atomically extend an existing paused V6 ledger; never reset or reconstruct spend.

    The output limits are the complete explicitly authorized set, including the
    original 2048-generation and 16384-review caps. No request, counter, price,
    monetary limit, or request ceiling is rewritten. Only the specific authorized
    audit pause may be cleared, after every paid request has settled.
    """
    path = Path(path)
    if not path.is_file():
        raise BudgetAmendmentError("original paid database is missing; amendment never creates one")
    if (
        not isinstance(expected_run_id, str)
        or not expected_run_id
        or not isinstance(expected_config_sha256, str)
        or len(expected_config_sha256) != 64
        or not isinstance(amendment_id, str)
        or not amendment_id.strip()
        or not isinstance(evidence, dict)
        or not evidence
    ):
        raise BudgetAmendmentError(
            "explicit run, old configuration hash, amendment ID and evidence required"
        )
    evidence = json.loads(_json(evidence))  # Freeze the caller's authorization evidence.
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        if row is None:
            raise BudgetAmendmentError("original paid configuration is absent")
        old = json.loads(row[0])
        if (
            digest(old) != expected_config_sha256
            or old.get("run_id") != expected_run_id
            or old.get("purpose") != V6_PURPOSE
            or old.get("schema") != "probe_budget.v2"
            or old.get("hard_cap_microcny") != HARD_CAP_MICROCNY
            or old.get("warning_microcny") != WARNING_MICROCNY
            or old.get("joint_generation_and_review_cap") is not True
            or old.get("variable_reservation_bound_to_each_actual_request") is not True
        ):
            raise BudgetAmendmentError("original V6 run/configuration or 800/700 CNY limits differ")
        limits = validated_budget_limits(
            **{name: old[name] for name in ("hard_cap_microcny", "warning_microcny", "request_cap")}
        )
        sheet = ProbePriceSheet(**old["price_sheet"])
        previous = _review_output_limits(
            old.get("allowed_output_limits"),
            official_max_output_tokens=sheet.official_max_output_tokens,
        )
        allowed = _review_output_limits(
            allowed_review_output_limits,
            official_max_output_tokens=sheet.official_max_output_tokens,
        )
        if (
            old.get("price_sheet_id") != sheet.id
            or old.get("max_output_tokens") != max(previous)
            or old.get("reservation_microcny_per_request")
            != sheet.cost_microcny(
                hit=0, miss=sheet.context_input_token_ceiling, output=max(previous)
            )
            or not set(previous) < set(allowed)
        ):
            raise BudgetAmendmentError(
                "amendment must extend, never replace, the frozen original caps/tariff"
            )
        event_key = "v6_review_amendment:" + amendment_id
        if connection.execute("SELECT 1 FROM metadata WHERE key=?", (event_key,)).fetchone():
            raise BudgetAmendmentError(
                "amendment ID already recorded; no overwrite or second application"
            )
        halt = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        if halt is None or json.loads(halt[0]).get("reason") != V6_REVIEW_AMENDMENT_PAUSE:
            raise BudgetAmendmentError(
                "only the explicit user-authorized review audit pause may clear"
            )
        pause_event = connection.execute(
            "SELECT sequence FROM events WHERE action='halt' AND payload_json=? "
            "ORDER BY sequence DESC LIMIT 1",
            (halt[0],),
        ).fetchone()
        if pause_event is None or any(
            json.loads(event[0]).get("reason") != V6_REVIEW_AMENDMENT_PAUSE
            for event in connection.execute(
                "SELECT payload_json FROM events WHERE action='halt' AND sequence>?",
                (pause_event[0],),
            )
        ):
            # INSERT OR IGNORE preserves the first halt in metadata. A later
            # in-flight service failure must not disappear behind that pause.
            raise BudgetAmendmentError(
                "another halt occurred during the audit pause; cannot clear it"
            )
        unsettled = connection.execute(
            "SELECT COUNT(*) FROM requests WHERE state!='SETTLED'"
        ).fetchone()[0]
        counters = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        aggregate = connection.execute(
            "SELECT COUNT(*) AS requests,COALESCE(SUM(settled_microcny),0) AS spent,"
            "SUM(CASE WHEN settled_microcny IS NULL OR settled_microcny<0 "
            "OR dispatched_at IS NULL THEN 1 ELSE 0 END) AS invalid FROM requests"
        ).fetchone()
        if (
            unsettled
            or counters is None
            or any(counters[name] != 0 for name in ("pending", "held", "unknown"))
            or counters["requests"] != aggregate["requests"]
            or counters["dispatched"] != aggregate["requests"]
            or counters["spent"] != aggregate["spent"]
            or aggregate["invalid"]
            or not 0 <= counters["spent"] <= limits["hard_cap_microcny"]
            or not 0 <= counters["requests"] <= limits["request_cap"]
        ):
            raise BudgetAmendmentError(
                "all original requests/costs must settle and conserve before amendment"
            )
        new = {
            **old,
            "amendment_id": amendment_id,
            "allowed_output_limits": list(allowed),
            "max_output_tokens": max(allowed),
            "reservation_microcny_per_request": sheet.cost_microcny(
                hit=0, miss=sheet.context_input_token_ceiling, output=max(allowed)
            ),
        }
        record = dict(
            schema="v6_review_capacity_amendment.v1",
            amendment_id=amendment_id,
            run_id=expected_run_id,
            old_config=old,
            new_config=new,
            old_config_sha256=digest(old),
            new_config_sha256=digest(new),
            cleared_halt=json.loads(halt[0]),
            authorization_evidence=evidence,
            preserved_counters=dict(counters),
            all_original_requests_settled=True,
            monetary_and_request_caps_unchanged=True,
            old_request_limits_unchanged=True,
            at_unix=time.time(),
        )
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES (?,?)", (event_key, _json(record))
        )
        connection.execute("UPDATE metadata SET value=? WHERE key='config'", (_json(new),))
        deleted = connection.execute(
            "DELETE FROM metadata WHERE key='halt' AND value=?", (halt[0],)
        )
        if deleted.rowcount != 1:
            raise BudgetAmendmentError("authorized pause identity changed during amendment")
        connection.execute(
            "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
            (amendment_id, V6_REVIEW_AMENDMENT_ACTION, _json(record), record["at_unix"]),
        )
        connection.commit()
        return record
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


class ProbeBudget:
    """One SQLite database per registered inventory, safe across worker processes."""

    def __init__(
        self,
        path,
        *,
        run_id,
        price_sheet,
        max_output_tokens,
        purpose=PURPOSE,
        hard_cap_microcny=HARD_CAP_MICROCNY,
        warning_microcny=WARNING_MICROCNY,
        request_cap=REQUEST_CAP,
        amendment_id=None,
        allowed_output_limits=None,
    ):
        limits = validated_budget_limits(
            hard_cap_microcny=hard_cap_microcny,
            warning_microcny=warning_microcny,
            request_cap=request_cap,
        )
        self.hard_cap_microcny = limits["hard_cap_microcny"]
        self.warning_microcny = limits["warning_microcny"]
        self.request_cap = limits["request_cap"]
        self.path = Path(path)
        self._require_existing = amendment_id is not None or allowed_output_limits is not None
        if self._require_existing:
            if (
                purpose != V6_PURPOSE
                or not isinstance(amendment_id, str)
                or not amendment_id.strip()
                or allowed_output_limits is None
            ):
                raise BudgetAmendmentError(
                    "amended V6 open requires explicit amendment ID and output limits"
                )
            if not self.path.is_file():
                raise BudgetAmendmentError(
                    "original amended database is missing; never recreate the ledger"
                )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id, self.price_sheet = (
            run_id,
            price_sheet
            if isinstance(price_sheet, ProbePriceSheet)
            else ProbePriceSheet(**price_sheet),
        )
        self.max_output_tokens = max_output_tokens
        self.purpose = purpose
        self.allowed_output_limits = (
            _review_output_limits(
                allowed_output_limits,
                official_max_output_tokens=self.price_sheet.official_max_output_tokens,
            )
            if self._require_existing
            else (2048, 16384)
            if purpose == V6_PURPOSE
            else (max_output_tokens,)
        )
        if not isinstance(run_id, str) or not run_id or purpose not in {PURPOSE, V6_PURPOSE}:
            raise ValueError("a dedicated registered Probe run and purpose are required")
        if (
            type(max_output_tokens) is not int
            or max_output_tokens
            not in (
                (max(self.allowed_output_limits),)
                if self._require_existing
                else (16384,)
                if purpose == V6_PURPOSE
                else (2048, 4096)
            )
            or max_output_tokens > self.price_sheet.official_max_output_tokens
        ):
            raise ValueError(
                "Probe output cap must be frozen at 2048 or 4096 within the official limit"
            )
        self.reservation_microcny = self.price_sheet.cost_microcny(
            hit=0, miss=self.price_sheet.context_input_token_ceiling, output=max_output_tokens
        )
        config = {
            "schema": "probe_budget.v1",
            "run_id": run_id,
            "purpose": purpose,
            "price_sheet": asdict(self.price_sheet),
            "price_sheet_id": self.price_sheet.id,
            "max_output_tokens": max_output_tokens,
            **limits,
            "reservation_microcny_per_request": self.reservation_microcny,
            "reservation_input_policy": "official_entire_context_at_cache_miss_price",
            "currency_scale": "1 CNY = 1000000 micro-CNY",
        }
        if purpose == V6_PURPOSE:
            config.update(
                schema="probe_budget.v2",
                allowed_output_limits=list(self.allowed_output_limits),
                joint_generation_and_review_cap=True,
                variable_reservation_bound_to_each_actual_request=True,
            )
        if self._require_existing:
            config["amendment_id"] = amendment_id
        self.config = config
        if not self._require_existing:
            with closing(self._connect()) as connection:
                connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    invocation_id TEXT PRIMARY KEY,
                    coordinates_json TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    request_body BLOB NOT NULL,
                    state TEXT NOT NULL,
                    reserved_microcny INTEGER NOT NULL,
                    settled_microcny INTEGER,
                    created_at REAL NOT NULL,
                    dispatched_at REAL,
                    settled_at REAL,
                    http_status INTEGER,
                    response_classification TEXT,
                    response_body BLOB,
                    response_sha256 TEXT,
                    usage_json TEXT,
                    evidence_json TEXT
                );
                CREATE TABLE IF NOT EXISTS counters (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    requests INTEGER NOT NULL DEFAULT 0,
                    dispatched INTEGER NOT NULL DEFAULT 0,
                    spent INTEGER NOT NULL DEFAULT 0,
                    held INTEGER NOT NULL DEFAULT 0,
                    unknown INTEGER NOT NULL DEFAULT 0,
                    pending INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    hit_tokens INTEGER NOT NULL DEFAULT 0,
                    miss_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO counters(singleton) VALUES (1);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    invocation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    at_unix REAL NOT NULL
                );
                """)
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT value FROM metadata WHERE key='config'"
            ).fetchone()
            if existing is not None and json.loads(existing[0]) != config:
                raise ValueError(
                    "budget database belongs to a different run, purpose, tariff, "
                    "output or budget limit"
                )
            if self._require_existing:
                amendment = connection.execute(
                    "SELECT value FROM metadata WHERE key=?",
                    ("v6_review_amendment:" + amendment_id,),
                ).fetchone()
                if existing is None or amendment is None:
                    raise BudgetAmendmentError("explicit capacity amendment evidence is absent")
                record = json.loads(amendment[0])
                if record.get("new_config") != config or record.get("new_config_sha256") != digest(
                    config
                ):
                    raise BudgetAmendmentError(
                        "amended configuration differs from its durable authorization"
                    )
            connection.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('config',?)", (_json(config),)
            )

    def _connect(self):
        connection = (
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=rw",
                uri=True,
                timeout=30,
                isolation_level=None,
            )
            if self._require_existing
            else sqlite3.connect(self.path, timeout=30, isolation_level=None)
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
            if stored is not None and json.loads(stored[0]) != self.config:
                raise ValueError(
                    "different or stale budget configuration; reopen with explicit frozen amendment"
                )
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _snapshot(self, connection):
        return _budget_snapshot(connection, self.config)

    def snapshot(self):
        connection = self._connect()
        try:
            # Counters, holds and quota rows must describe one database instant
            # while generation and the independent review controller settle.
            connection.execute("BEGIN")
            return self._snapshot(connection)
        finally:
            connection.close()

    def reserve(self, invocation_id, *, coordinates, request, request_body):
        if (
            coordinates.get("run_id") != self.run_id
            or coordinates.get("invocation_id") != invocation_id
        ):
            raise ValueError("invocation coordinates do not belong to this budget run")
        if (
            not isinstance(coordinates.get("episode_id"), str)
            or not coordinates["episode_id"]
            or type(coordinates.get("turn_index")) is not int
            or not 0 <= coordinates["turn_index"] < 32
        ):
            raise ValueError("Probe invocation must identify one of the 32 bounded episode turns")
        if invocation_identity(coordinates, turn_index=coordinates["turn_index"]) != coordinates:
            raise ValueError(
                "invocation ID must be derived from the actual run/episode/attempt/turn"
            )
        if (
            request.get("model") != "deepseek-flash"
            or type(request.get("max_tokens")) is not int
            or request["max_tokens"] not in self.allowed_output_limits
            or request.get("thinking") != {"type": "disabled"}
        ):
            raise ValueError("request differs from the frozen Probe model/output/thinking contract")
        if not isinstance(request_body, bytes) or json.loads(request_body) != request:
            raise ValueError("retained public request bytes differ from the actual HTTP body")
        reservation = self.price_sheet.cost_microcny(
            hit=0, miss=self.price_sheet.context_input_token_ceiling, output=request["max_tokens"]
        )
        with self._transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone():
                raise DuplicateInvocation("invocation already persisted; no duplicate API send")
            state = self._snapshot(connection)
            if state["halt"] or state["unacknowledged_unknown_requests"]:
                raise BudgetUnavailable("unknown or halted Probe ledger forbids new requests")
            if state["requests_reserved"] >= self.request_cap:
                raise BudgetUnavailable(f"{self.request_cap}-request Probe cap exhausted")
            effective_cap = state.get("effective_hard_cap_microcny", self.hard_cap_microcny)
            if state["exposure_microcny"] + reservation > effective_cap:
                raise BudgetUnavailable(
                    "next full official-context reservation exceeds the authorized "
                    f"{effective_cap} micro-CNY cap"
                )
            category = _partition_admit(connection, self.config, coordinates)
            connection.execute(
                """INSERT INTO requests
                (invocation_id,coordinates_json,request_sha256,request_body,state,reserved_microcny,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    invocation_id,
                    _json(coordinates),
                    digest(request),
                    request_body,
                    "RESERVED",
                    reservation,
                    time.time(),
                ),
            )
            connection.execute(
                "UPDATE counters SET requests=requests+1,pending=pending+1,held=held+? "
                "WHERE singleton=1",
                (reservation,),
            )
            if category is not None:
                connection.execute(
                    "INSERT INTO v8_request_allocations VALUES (?,?,?)",
                    (invocation_id, category, coordinates["episode_id"]),
                )
                connection.execute(
                    "UPDATE v8_request_quotas SET consumed=consumed+1 WHERE category=?", (category,)
                )
            self._event(
                connection,
                invocation_id,
                "reserved",
                {
                    "request_sha256": digest(request),
                    "reservation_microcny": reservation,
                },
            )
        return reservation

    def mark_dispatched(self, invocation_id):
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            if row is None or row[0] != "RESERVED":
                raise DuplicateInvocation("only a fresh unsent reservation can be dispatched")
            snapshot = self._snapshot(connection)
            if snapshot["halt"] or snapshot["unacknowledged_unknown_requests"]:
                raise BudgetUnavailable("ledger halted before dispatch; request not sent")
            connection.execute(
                "UPDATE requests SET state='DISPATCHED',dispatched_at=? WHERE invocation_id=?",
                (time.time(), invocation_id),
            )
            connection.execute("UPDATE counters SET dispatched=dispatched+1 WHERE singleton=1")
            self._event(connection, invocation_id, "dispatched", {})

    def _event(self, connection, invocation_id, action, payload):
        connection.execute(
            "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
            (invocation_id, action, _json(payload), time.time()),
        )

    def _halt(self, connection, reason, invocation_id, evidence):
        value = {
            "reason": reason,
            "invocation_id": invocation_id,
            "evidence": evidence,
            "at_unix": time.time(),
        }
        connection.execute("INSERT OR IGNORE INTO metadata VALUES ('halt',?)", (_json(value),))
        self._event(connection, invocation_id, "halt", value)

    def unknown(
        self,
        invocation_id,
        *,
        reason,
        http_status=None,
        response_classification="unknown",
        response_body=None,
        evidence=None,
    ):
        import hashlib

        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            if row is None or row[0] not in {"RESERVED", "DISPATCHED"}:
                raise ValueError("only a pending request can become unknown")
            connection.execute(
                """UPDATE requests SET state='UNKNOWN',http_status=?,response_classification=?,
                response_body=?,response_sha256=?,evidence_json=? WHERE invocation_id=?""",
                (
                    http_status,
                    response_classification,
                    response_body,
                    hashlib.sha256(response_body).hexdigest()
                    if response_body is not None
                    else None,
                    _json(evidence or {}),
                    invocation_id,
                ),
            )
            connection.execute(
                "UPDATE counters SET unknown=unknown+1,pending=pending-1 WHERE singleton=1"
            )
            self._event(
                connection,
                invocation_id,
                "unknown",
                {
                    "reason": reason,
                    "http_status": http_status,
                    "response_classification": response_classification,
                },
            )
            self._halt(connection, reason, invocation_id, evidence or {})

    def settle(
        self,
        invocation_id,
        *,
        usage,
        http_status,
        response_classification,
        response_body,
        evidence=None,
    ):
        import hashlib

        counters = self.price_sheet.usage(usage, output_limit=self.max_output_tokens)
        amount = self.price_sheet.cost_microcny(
            hit=counters["prompt_cache_hit_tokens"],
            miss=counters["prompt_cache_miss_tokens"],
            output=counters["completion_tokens"],
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state,reserved_microcny,request_body FROM requests WHERE invocation_id=?",
                (invocation_id,),
            ).fetchone()
            if row is None or row[0] != "DISPATCHED":
                raise ValueError(
                    "settlement requires one dispatched, not previously settled request"
                )
            self.price_sheet.usage(usage, output_limit=json.loads(row[2])["max_tokens"])
            if amount > row[1]:
                raise InvalidUsage(
                    "actual tariff cost exceeds the official upper-bound reservation"
                )
            connection.execute(
                """UPDATE requests SET state='SETTLED',settled_microcny=?,settled_at=?,
                http_status=?,response_classification=?,response_body=?,response_sha256=?,
                usage_json=?,evidence_json=? WHERE invocation_id=?""",
                (
                    amount,
                    time.time(),
                    http_status,
                    response_classification,
                    response_body,
                    hashlib.sha256(response_body).hexdigest(),
                    _json(usage),
                    _json(evidence or {}),
                    invocation_id,
                ),
            )
            connection.execute(
                """UPDATE counters SET pending=pending-1,spent=spent+?,held=held-?,
                prompt_tokens=prompt_tokens+?,hit_tokens=hit_tokens+?,miss_tokens=miss_tokens+?,
                completion_tokens=completion_tokens+? WHERE singleton=1""",
                (
                    amount,
                    row[1],
                    counters["prompt_tokens"],
                    counters["prompt_cache_hit_tokens"],
                    counters["prompt_cache_miss_tokens"],
                    counters["completion_tokens"],
                ),
            )
            self._event(
                connection,
                invocation_id,
                "settled",
                {
                    "peak_tariff_upper_bound_microcny": amount,
                    "usage": usage,
                    "response_classification": response_classification,
                },
            )
            if response_classification != "model_response":
                self._halt(connection, response_classification, invocation_id, evidence or {})
        return amount

    def halt(self, *, reason, invocation_id, evidence=None):
        with self._transaction() as connection:
            self._halt(connection, reason, invocation_id, evidence or {})

    def acknowledge_unknown_abandonment(
        self,
        invocation_id,
        *,
        authorization_id,
        expected_request_sha256,
        expected_halt_reason,
        reason,
        evidence,
    ):
        """Authorize other future calls while permanently charging this maximum hold to exposure.

        This neither verifies the unknown bill nor settles, erases, releases,
        retries or substitutes the original call. Only its exact halt is cleared.
        One invocation and one explicit authorization are bound transactionally.
        """
        if (
            self.purpose != V6_PURPOSE
            or any(
                not isinstance(v, str) or not v.strip()
                for v in (
                    invocation_id,
                    authorization_id,
                    expected_request_sha256,
                    expected_halt_reason,
                    reason,
                )
            )
            or len(expected_request_sha256) != 64
            or not isinstance(evidence, dict)
            or not evidence
        ):
            raise UnknownAbandonmentError(
                "exact V6 invocation, authorization, hashes and evidence required"
            )
        bound_inputs = dict(
            run_id=self.run_id,
            invocation_id=invocation_id,
            authorization_id=authorization_id,
            expected_request_sha256=expected_request_sha256,
            expected_halt_reason=expected_halt_reason,
            reason=reason,
            authorization_evidence=json.loads(_json(evidence)),
        )
        with self._transaction() as connection:
            acknowledged = _acknowledged_unknowns(connection, self.config)
            for prior in acknowledged:
                if (
                    prior["invocation_id"] == invocation_id
                    or prior["authorization_id"] == authorization_id
                ):
                    if all(prior.get(k) == v for k, v in bound_inputs.items()):
                        return prior  # Idempotent audit lookup; never clear a later halt.
                    raise UnknownAbandonmentError(
                        "abandonment identity already bound to different authorization"
                    )
            row = connection.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            if (
                row is None
                or row["state"] != "UNKNOWN"
                or row["usage_json"] is not None
                or row["settled_microcny"] is not None
                or row["settled_at"] is not None
                or row["request_sha256"] != expected_request_sha256
            ):
                raise UnknownAbandonmentError(
                    "only the exact original UNKNOWN request with absent usage may be abandoned"
                )
            coordinates = json.loads(row["coordinates_json"])
            request = json.loads(row["request_body"])
            if (
                coordinates.get("run_id") != self.run_id
                or invocation_identity(coordinates, turn_index=coordinates["turn_index"])
                != coordinates
                or coordinates["invocation_id"] != invocation_id
                or digest(request) != expected_request_sha256
                or request.get("model") != "deepseek-flash"
                or request.get("max_tokens") not in self.allowed_output_limits
                or row["reserved_microcny"]
                != self.price_sheet.cost_microcny(
                    hit=0,
                    miss=self.price_sheet.context_input_token_ceiling,
                    output=request["max_tokens"],
                )
            ):
                raise UnknownAbandonmentError(
                    "unknown request/run/full reservation binding changed"
                )
            halt_row = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
            halt = json.loads(halt_row[0]) if halt_row else None
            unknown_event = connection.execute(
                "SELECT payload_json FROM events WHERE action='unknown' AND invocation_id=? "
                "ORDER BY sequence DESC LIMIT 1",
                (invocation_id,),
            ).fetchone()
            if (
                halt is None
                or halt.get("invocation_id") != invocation_id
                or halt.get("reason") != expected_halt_reason
                or unknown_event is None
                or json.loads(unknown_event[0]).get("reason") != expected_halt_reason
            ):
                raise UnknownAbandonmentError("refuse to clear an absent or unrelated halt")
            halt_event = connection.execute(
                "SELECT sequence FROM events WHERE action='halt' AND payload_json=? "
                "ORDER BY sequence DESC LIMIT 1",
                (halt_row[0],),
            ).fetchone()
            if halt_event is None or any(
                json.loads(event[0]).get("invocation_id") != invocation_id
                or json.loads(event[0]).get("reason") != expected_halt_reason
                for event in connection.execute(
                    "SELECT payload_json FROM events WHERE action='halt' AND sequence>?",
                    (halt_event[0],),
                )
            ):
                raise UnknownAbandonmentError(
                    "an unrelated later halt must not be hidden or cleared"
                )
            counters = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
            totals = connection.execute(
                "SELECT COUNT(*) AS requests, "
                "SUM(CASE WHEN dispatched_at IS NOT NULL THEN 1 ELSE 0 END) AS dispatched, "
                "SUM(CASE WHEN state='SETTLED' THEN settled_microcny ELSE 0 END) AS spent, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED','UNKNOWN') "
                "THEN reserved_microcny ELSE 0 END) AS held, "
                "SUM(CASE WHEN state='UNKNOWN' THEN 1 ELSE 0 END) AS unknown, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED') THEN 1 ELSE 0 END) AS pending "
                "FROM requests"
            ).fetchone()
            monetary = _v9_monetary_amendment(connection, self.config)
            effective_cap = (
                monetary["effective_hard_cap_microcny"] if monetary else self.hard_cap_microcny
            )
            if (
                counters is None
                or any(
                    counters[k] != totals[k]
                    for k in ("requests", "dispatched", "spent", "held", "unknown", "pending")
                )
                or counters["pending"] != 0
                or counters["spent"] + counters["held"] > effective_cap
            ):
                raise UnknownAbandonmentError(
                    "quiescent original request/fee/reservation counters must conserve"
                )
            record = dict(
                schema="v6_unknown_abandonment.v1",
                **bound_inputs,
                config_sha256=digest(self.config),
                original_unknown_record_sha256=_request_record_digest(row),
                permanent_reserved_microcny=row["reserved_microcny"],
                original_halt=halt,
                preserved_counters=dict(counters),
                original_unknown_state_preserved=True,
                actual_usage_known=False,
                actual_charge_known=False,
                reservation_released=False,
                retry_authorized=False,
                replacement_call_authorized=False,
                future_calls_within_original_cap_only=monetary is None,
                at_unix=time.time(),
            )
            record["id"] = digest(record)
            connection.execute(
                "INSERT INTO metadata(key,value) VALUES (?,?)",
                (UNKNOWN_ABANDONMENT_PREFIX + invocation_id, _json(record)),
            )
            self._event(connection, invocation_id, UNKNOWN_ABANDONMENT_ACTION, record)
            deleted = connection.execute(
                "DELETE FROM metadata WHERE key='halt' AND value=?", (halt_row[0],)
            )
            if deleted.rowcount != 1:
                raise UnknownAbandonmentError("exact target halt changed during acknowledgement")
            return record

    def acknowledge_v9_connection_unknowns(
        self,
        *,
        protocol_id,
        authorization,
        expected_requests,
    ):
        """Conservatively terminalize one approved matrix's connection UNKNOWNs.

        ``expected_requests`` maps each original invocation to its externally
        reconstructed ``job_key`` and HTTP-body ``request_sha256``. All currently
        unacknowledged UNKNOWNs must be covered in one quiescent transaction.
        Original rows, counters and maximum reservations NEVER change. Each row
        gets the existing strict acknowledgement/event binding; no usage, result,
        model judgment, release, retry, substitute call or training material is
        manufactured. Only this fully verified batch's exact current halt clears.

        Repeating the identical saved batch is audit lookup only and does not
        clear/acknowledge later work. The same prospective authorization can cover
        a later complete set of eligible connection failures in the SAME matrix.
        """
        if (
            self.purpose != V6_PURPOSE
            or protocol_id != V9_NETWORK_PROTOCOL_ID
            or not isinstance(authorization, dict)
            or authorization.get("id")
            != digest({k: v for k, v in authorization.items() if k != "id"})
            or authorization.get("schema") != "v9_network_unknown_terminal_authorization.v1"
            or authorization.get("user_reply") != "允许上述有限修订并继续同一矩阵"
            or authorization.get("protocol_id") != protocol_id
            or any(
                authorization.get(k) is not True
                for k in (
                    "risk_acknowledged",
                    "no_resend",
                    "permanent_full_hold",
                    "scope_all_same_matrix_connection_interruptions",
                    "unknown_never_positive",
                )
            )
            or authorization.get("hard_cap_microcny") != V9_AUTHORIZED_TOTAL_MICROCNY
            or authorization.get("terminal_completion_semantics")
            != (
                "all registered jobs have authentic terminal records; "
                "actual returned responses counted separately"
            )
            or not isinstance(expected_requests, dict)
            or not expected_requests
            or any(
                not isinstance(iid, str)
                or not isinstance(item, dict)
                or set(item) != {"job_key", "request_sha256"}
                or not isinstance(item["job_key"], str)
                or not item["job_key"]
                or not isinstance(item["request_sha256"], str)
                or len(item["request_sha256"]) != 64
                for iid, item in expected_requests.items()
            )
        ):
            raise UnknownAbandonmentError(
                "explicit same-matrix connection terminal authority and bindings required"
            )
        signature = dict(
            protocol_id=protocol_id,
            authorization_id=authorization["id"],
            expected_requests=json.loads(_json(expected_requests)),
        )
        batch_key = V9_NETWORK_BATCH_PREFIX + digest(signature)
        with self._transaction() as connection:
            acknowledged = {
                r["invocation_id"]: r for r in _acknowledged_unknowns(connection, self.config)
            }
            prior = connection.execute(
                "SELECT value FROM metadata WHERE key=?", (batch_key,)
            ).fetchone()
            if prior is not None:
                record = json.loads(prior[0])
                if (
                    record.get("id") != digest({k: v for k, v in record.items() if k != "id"})
                    or any(record.get(k) != v for k, v in signature.items())
                    or any(acknowledged.get(r["invocation_id"]) != r for r in record["records"])
                    or not connection.execute(
                        "SELECT 1 FROM events WHERE invocation_id=? "
                        "AND action=? AND payload_json=?",
                        (batch_key, V9_NETWORK_BATCH_ACTION, prior[0]),
                    ).fetchone()
                ):
                    raise UnknownAbandonmentError("saved connection terminal receipt changed")
                return record  # Never clear an unrelated or later halt on idempotent lookup.
            snapshot = self._snapshot(connection)
            monetary = snapshot.get("monetary_amendment")
            rows = {
                r["invocation_id"]: r
                for r in connection.execute(
                    "SELECT * FROM requests WHERE state='UNKNOWN' ORDER BY invocation_id"
                )
            }
            unacknowledged = set(rows) - set(acknowledged)
            if (
                snapshot["pending_requests"] != 0
                or monetary is None
                or snapshot.get("effective_hard_cap_microcny") != V9_AUTHORIZED_TOTAL_MICROCNY
                or set(expected_requests) - set(rows)
                or unacknowledged != set(expected_requests) - set(acknowledged)
            ):
                raise UnknownAbandonmentError(
                    "quiescent complete set of original connection UNKNOWNs required"
                )
            checked_rows, evidence_by_id = {}, {}
            for iid, expected in expected_requests.items():
                row = rows[iid]
                episode_id = "v8prod:" + digest(
                    dict(protocol_id=protocol_id, job_key=expected["job_key"])
                )
                coordinates = invocation_identity(
                    dict(run_id=self.run_id, episode_id=episode_id, attempt_index=1), turn_index=0
                )
                request = json.loads(row["request_body"])
                evidence = json.loads(row["evidence_json"] or "{}")
                event = connection.execute(
                    "SELECT payload_json FROM events WHERE action='unknown' AND invocation_id=? "
                    "ORDER BY sequence DESC LIMIT 1",
                    (iid,),
                ).fetchone()
                unknown = json.loads(event[0]) if event else {}
                if (
                    coordinates["invocation_id"] != iid
                    or json.loads(row["coordinates_json"]) != coordinates
                    or row["dispatched_at"] is None
                    or row["usage_json"] is not None
                    or row["settled_microcny"] is not None
                    or row["settled_at"] is not None
                    or row["http_status"] is not None
                    or row["response_body"] is not None
                    or row["response_sha256"] is not None
                    or row["response_classification"] != "unknown"
                    or row["request_sha256"] != expected["request_sha256"]
                    or digest(request) != expected["request_sha256"]
                    or request.get("model") != "deepseek-flash"
                    or request.get("max_tokens") not in self.allowed_output_limits
                    or row["reserved_microcny"]
                    != self.price_sheet.cost_microcny(
                        hit=0,
                        miss=self.price_sheet.context_input_token_ceiling,
                        output=request["max_tokens"],
                    )
                    or evidence.get("exception_type") not in V9_NETWORK_EXCEPTIONS
                    or evidence.get("service_response_received") is not False
                    or evidence.get("budget_invocation_id") != iid
                    or evidence.get("budget_coordinates") != coordinates
                    or evidence.get("request_sha256") != expected["request_sha256"]
                    or evidence.get("wire_protocol")
                    not in {
                        "v8_single_target_review.v1",
                        "v8_alignment_review.v1",
                    }
                    or unknown
                    != dict(
                        reason=V9_NETWORK_UNKNOWN_REASON,
                        http_status=None,
                        response_classification="unknown",
                    )
                ):
                    raise UnknownAbandonmentError(
                        "UNKNOWN is not the exact approved no-response connection attempt"
                    )
                if iid in acknowledged:
                    old = acknowledged[iid]
                    if (
                        old.get("protocol_id") != protocol_id
                        or old.get("user_authorization_id") != authorization["id"]
                        or old.get("job_key") != expected["job_key"]
                    ):
                        raise UnknownAbandonmentError(
                            "existing UNKNOWN acknowledgement has different authority"
                        )
                checked_rows[iid], evidence_by_id[iid] = row, evidence
            if not unacknowledged:
                # Pure reassembly can combine earlier batches without creating
                # new acknowledgement events, charges, or a halt-clear action.
                body = dict(
                    schema="v9_connection_unknown_batch_acknowledgement.v1",
                    **signature,
                    run_id=self.run_id,
                    config_sha256=digest(self.config),
                    records=[acknowledged[iid] for iid in sorted(expected_requests)],
                    new_acknowledgements=0,
                    original_request_rows_unchanged=True,
                    actual_billing_claimed=False,
                    retry_authorized=False,
                    lookup_only=True,
                    cleared_exact_halt=None,
                )
                return {**body, "id": digest(body)}
            halt_row = connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
            halt = json.loads(halt_row[0]) if halt_row else {}
            active_event = connection.execute(
                "SELECT sequence FROM events WHERE action='halt' AND payload_json=? "
                "ORDER BY sequence DESC LIMIT 1",
                (halt_row[0] if halt_row else "",),
            ).fetchone()
            if (
                halt.get("invocation_id") not in unacknowledged
                or halt.get("reason") != V9_NETWORK_UNKNOWN_REASON
                or active_event is None
                or halt.get("evidence") != evidence_by_id.get(halt.get("invocation_id"))
            ):
                raise UnknownAbandonmentError(
                    "current halt is absent or not this exact connection batch"
                )
            for event in connection.execute(
                "SELECT payload_json FROM events WHERE action='halt' AND sequence>=?",
                (active_event[0],),
            ):
                item = json.loads(event[0])
                if (
                    item.get("invocation_id") not in unacknowledged
                    or item.get("reason") != V9_NETWORK_UNKNOWN_REASON
                    or item.get("evidence") != evidence_by_id.get(item.get("invocation_id"))
                ):
                    raise UnknownAbandonmentError("an unrelated later halt must not be hidden")
            counters = dict(
                connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
            )
            totals = connection.execute(
                "SELECT COUNT(*) AS requests, "
                "SUM(CASE WHEN dispatched_at IS NOT NULL THEN 1 ELSE 0 END) AS dispatched, "
                "SUM(CASE WHEN state='SETTLED' THEN settled_microcny ELSE 0 END) AS spent, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED','UNKNOWN') "
                "THEN reserved_microcny ELSE 0 END) AS held, "
                "SUM(CASE WHEN state='UNKNOWN' THEN 1 ELSE 0 END) AS unknown, "
                "SUM(CASE WHEN state IN ('RESERVED','DISPATCHED') THEN 1 ELSE 0 END) AS pending "
                "FROM requests"
            ).fetchone()
            if (
                any(
                    counters[k] != totals[k]
                    for k in (
                        "requests",
                        "dispatched",
                        "spent",
                        "held",
                        "unknown",
                        "pending",
                    )
                )
                or counters["spent"] + counters["held"] > V9_AUTHORIZED_TOTAL_MICROCNY
            ):
                raise UnknownAbandonmentError(
                    "connection terminal accounting must preserve all full holds"
                )
            records = []
            for iid in sorted(expected_requests):
                if iid in acknowledged:
                    records.append(acknowledged[iid])
                    continue
                row, expected = checked_rows[iid], expected_requests[iid]
                body = dict(
                    schema="v9_connection_unknown_abandonment.v1",
                    run_id=self.run_id,
                    invocation_id=iid,
                    protocol_id=protocol_id,
                    job_key=expected["job_key"],
                    authorization_id="v9-connection:"
                    + digest(
                        dict(
                            authorization_id=authorization["id"],
                            invocation_id=iid,
                        )
                    ),
                    user_authorization_id=authorization["id"],
                    network_terminal_authorization_id=authorization["id"],
                    authorization_evidence=authorization,
                    expected_request_sha256=expected["request_sha256"],
                    expected_halt_reason=V9_NETWORK_UNKNOWN_REASON,
                    config_sha256=digest(self.config),
                    original_unknown_record_sha256=_request_record_digest(row),
                    permanent_reserved_microcny=row["reserved_microcny"],
                    original_halt=halt,
                    preserved_counters=counters,
                    original_unknown_state_preserved=True,
                    actual_usage_known=False,
                    actual_charge_known=False,
                    reservation_released=False,
                    retry_authorized=False,
                    replacement_call_authorized=False,
                    unknown_never_positive=True,
                    connection_exception_type=evidence_by_id[iid]["exception_type"],
                    original_network_evidence_sha256=digest(evidence_by_id[iid]),
                    monetary_amendment_id=monetary["id"],
                    future_calls_within_original_cap_only=False,
                    effective_hard_cap_microcny=V9_AUTHORIZED_TOTAL_MICROCNY,
                    at_unix=time.time(),
                )
                record = {**body, "id": digest(body)}
                connection.execute(
                    "INSERT INTO metadata VALUES (?,?)",
                    (UNKNOWN_ABANDONMENT_PREFIX + iid, _json(record)),
                )
                self._event(connection, iid, UNKNOWN_ABANDONMENT_ACTION, record)
                records.append(record)
            deleted = connection.execute(
                "DELETE FROM metadata WHERE key='halt' AND value=?", (halt_row[0],)
            )
            if deleted.rowcount != 1:
                raise UnknownAbandonmentError(
                    "exact connection halt changed during acknowledgement"
                )
            body = dict(
                schema="v9_connection_unknown_batch_acknowledgement.v1",
                **signature,
                run_id=self.run_id,
                config_sha256=digest(self.config),
                records=records,
                new_acknowledgements=len(unacknowledged),
                preserved_counters=counters,
                permanent_unknown_hold_microcny=counters["held"],
                cleared_exact_halt=halt,
                original_request_rows_unchanged=True,
                actual_billing_claimed=False,
                retry_authorized=False,
                at_unix=time.time(),
            )
            receipt = {**body, "id": digest(body)}
            connection.execute("INSERT INTO metadata VALUES (?,?)", (batch_key, _json(receipt)))
            self._event(connection, batch_key, V9_NETWORK_BATCH_ACTION, receipt)
            return receipt

    def blocking_unsettled(self):
        """Unacknowledged work only; unsettled() still truthfully lists abandoned UNKNOWNs."""
        connection = self._connect()
        try:
            acknowledged = {
                record["invocation_id"]
                for record in _acknowledged_unknowns(connection, self.config)
            }
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT invocation_id,state,coordinates_json FROM requests "
                    "WHERE state IN ('RESERVED','DISPATCHED','UNKNOWN') ORDER BY created_at"
                )
                if row["invocation_id"] not in acknowledged
            ]
        finally:
            connection.close()

    def request_record(self, invocation_id):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def unsettled(self):
        connection = self._connect()
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT invocation_id,state,coordinates_json FROM requests "
                    "WHERE state IN ('RESERVED','DISPATCHED','UNKNOWN') ORDER BY created_at"
                )
            ]
        finally:
            connection.close()
