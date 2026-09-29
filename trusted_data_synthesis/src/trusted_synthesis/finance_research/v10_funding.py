"""One explicit 2000/1300-CNY overlay on the existing V10 wallet, never a reset."""

import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .contracts import digest
from .probe_budget import (
    V9_MONETARY_AMENDMENT_KEY,
    BudgetAmendmentError,
    _budget_snapshot,
    _json,
    _request_record_digest,
)

KEY = "v10_funding_overlay_2000_1300_01"
ACTION = "v10_funding_overlay_authorized"
BATCH_ID = "finqa-v10-20260929-new8000-01"
PARTITION_KEY = "v10_new_batch_partition"
TOTAL_MICROCNY = 2_000_000_000
REVIEW_MICROCNY = 1_300_000_000
UNALLOCATED_MICROCNY = 118_901_111
USER_REPLY = "总上限提高到 2000 元，审阅／映射子额 1300 元"


def _require(condition, message):
    if not condition:
        raise BudgetAmendmentError(message)


def validate_authorization(value):
    _require(
        isinstance(value, dict)
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and value.get("schema") == "v10_funding_authorization.v1"
        and value.get("user_reply") == USER_REPLY
        and value.get("batch_id") == BATCH_ID
        and value.get("effective_hard_cap_microcny") == TOTAL_MICROCNY
        and value.get("effective_review_mapping_microcny") == REVIEW_MICROCNY,
        "exact explicit current-batch 2000/1300 funding authority required",
    )
    return value


def _parent(connection, key):
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    _require(row is not None, "original monetary/partition parent missing")
    value = json.loads(row[0])
    _require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "original monetary/partition parent changed",
    )
    return value, dict(
        key=key, id=value["id"], stored_bytes_sha256=hashlib.sha256(row[0].encode()).hexdigest()
    )


def read_overlay(connection, config):
    """Constant-size validation for reservations; never rehash historical payloads here."""
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (KEY,)).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    _require(
        record.get("id") == digest({k: v for k, v in record.items() if k != "id"})
        and record.get("schema") == "v10_prospective_funding_overlay.v1"
        and record.get("run_id") == config["run_id"]
        and record.get("config_sha256") == digest(config)
        and record.get("batch_id") == BATCH_ID
        and record.get("effective_hard_cap_microcny") == TOTAL_MICROCNY
        and record.get("effective_review_mapping_microcny") == REVIEW_MICROCNY
        and record.get("previous_effective_hard_cap_microcny") == 1_200_000_000
        and record.get("previous_review_mapping_microcny") == 550_000_000
        and record.get("preserved_generation_microcny") == 100_000_000
        and record.get("preserved_warning_microcny") == config["warning_microcny"] == 700_000_000
        and record.get("preserved_request_cap") == config["request_cap"] == 258000
        and record.get("effective_unallocated_microcny") == UNALLOCATED_MICROCNY
        and record.get("unallocated_spendable") is False
        and record.get("generation_new_reservations_authorized") is False,
        "V10 funding overlay/config changed",
    )
    validate_authorization(record.get("authorization"))
    monetary, monetary_ref = _parent(connection, V9_MONETARY_AMENDMENT_KEY)
    partition, partition_ref = _parent(connection, PARTITION_KEY)
    _require(
        monetary_ref == record["previous_monetary_amendment"]
        and partition_ref == record["original_v10_partition"]
        and monetary["effective_hard_cap_microcny"] == 1_200_000_000
        and partition["batch_id"] == BATCH_ID
        and partition["limits"]["review_mapping"] == dict(requests=17000, microcny=550_000_000)
        and partition["limits"]["generation"] == dict(requests=199000, microcny=100_000_000)
        and connection.execute(
            "SELECT 1 FROM events WHERE action=? AND invocation_id=? AND payload_json=?",
            (ACTION, KEY, row[0]),
        ).fetchone()
        is not None,
        "funding overlay no longer binds untouched original parents/event",
    )
    return record


def _file_sha(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _request_stream(connection):
    sha, count = hashlib.sha256(), 0
    for row in connection.execute("SELECT * FROM requests ORDER BY invocation_id"):
        sha.update(row["invocation_id"].encode() + b"\0")
        sha.update(_request_record_digest(row).encode() + b"\n")
        count += 1
    return dict(
        schema="v10_original_request_stream.v1",
        rows=count,
        ordering="invocation_id ASC",
        row_encoding="_request_record_digest with exact blob lengths/SHA256",
        sha256=sha.hexdigest(),
    )


def _backup(source, target):
    _require(
        not target.exists() and target.parent.is_dir(),
        "backup must use an explicit new file in an existing directory",
    )
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    # The caller holds BEGIN IMMEDIATE. A second read-only connection copies a
    # coherent pre-amendment wallet while all competing writers remain excluded.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)) as reader:
        with closing(sqlite3.connect(target, timeout=30)) as destination:
            reader.backup(destination)
    return dict(
        path=str(target),
        bytes=target.stat().st_size,
        sha256=_file_sha(target),
        method="SQLite online backup under original-wallet BEGIN IMMEDIATE",
    )


def _append(connection, record):
    payload = _json(record)
    connection.execute("INSERT INTO metadata VALUES (?,?)", (KEY, payload))
    connection.execute(
        "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
        (KEY, ACTION, payload, record["at_unix"]),
    )


def apply_v10_funding(
    path, *, expected_run_id, expected_config_sha256, batch_id, authorization, backup_path
):
    """Backup then append the authorized overlay in a quiescent single transaction.

    Failed publication rolls back both metadata/event. Any backup already made is
    retained, never overwritten; after such a failure use a new explicit backup
    path. Reapplying the identical committed amendment is a read-only lookup.
    """
    validate_authorization(authorization)
    path, backup_path = Path(path).resolve(), Path(backup_path).resolve()
    _require(
        path.is_file() and backup_path != path and batch_id == BATCH_ID,
        "existing original wallet/current batch and distinct backup required",
    )
    signature = dict(
        run_id=expected_run_id,
        config_sha256=expected_config_sha256,
        batch_id=batch_id,
        authorization=authorization,
    )
    with closing(
        sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30, isolation_level=None)
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            config = json.loads(
                connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
            )
            _require(
                config["run_id"] == expected_run_id and digest(config) == expected_config_sha256,
                "original wallet run/config differs",
            )
            prior = read_overlay(connection, config)
            if prior is not None:
                _require(
                    all(prior.get(k) == v for k, v in signature.items())
                    and prior["backup"]["path"] == str(backup_path)
                    and backup_path.is_file()
                    and _file_sha(backup_path) == prior["backup"]["sha256"],
                    "existing funding authority/backup cannot be replaced",
                )
                connection.rollback()
                return prior
            state = _budget_snapshot(connection, config)
            _require(
                not state["pending_requests"]
                and not state["unacknowledged_unknown_requests"]
                and not state["halt"]
                and state.get("effective_hard_cap_microcny") == 1_200_000_000
                and state["exposure_microcny"] <= 1_200_000_000
                and state.get("v10_partition", {}).get("batch_id") == BATCH_ID,
                "funding requires pending zero, no unacknowledged UNKNOWN and no unrelated halt",
            )
            counters = dict(
                connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
            )
            totals = connection.execute(
                "SELECT COUNT(*) AS requests,SUM(dispatched_at IS NOT NULL) AS dispatched,"
                "SUM(COALESCE(settled_microcny,0)) AS spent,"
                "SUM(CASE WHEN state!='SETTLED' THEN reserved_microcny ELSE 0 END) AS held,"
                "SUM(state='UNKNOWN') AS unknown,"
                "SUM(state IN ('RESERVED','DISPATCHED')) AS pending "
                "FROM requests"
            ).fetchone()
            _require(
                all(
                    counters[k] == totals[k]
                    for k in ("requests", "dispatched", "spent", "held", "unknown", "pending")
                ),
                "original request/charge/hold counters do not conserve",
            )
            _, monetary_ref = _parent(connection, V9_MONETARY_AMENDMENT_KEY)
            _, partition_ref = _parent(connection, PARTITION_KEY)
            request_stream = _request_stream(connection)
            quota_before = [
                dict(r) for r in connection.execute("SELECT * FROM v10_quotas ORDER BY category")
            ]
            backup = _backup(path, backup_path)
            record = dict(
                schema="v10_prospective_funding_overlay.v1",
                **signature,
                at_unix=time.time(),
                previous_monetary_amendment=monetary_ref,
                original_v10_partition=partition_ref,
                previous_effective_hard_cap_microcny=1_200_000_000,
                previous_review_mapping_microcny=550_000_000,
                effective_hard_cap_microcny=TOTAL_MICROCNY,
                effective_review_mapping_microcny=REVIEW_MICROCNY,
                preserved_generation_microcny=100_000_000,
                preserved_warning_microcny=700_000_000,
                preserved_request_cap=258000,
                original_unallocated_microcny=68_901_111,
                effective_unallocated_microcny=UNALLOCATED_MICROCNY,
                unallocated_spendable=False,
                original_950_buffer_spendable=False,
                generation_new_reservations_authorized=False,
                applies_only_to_current_batch_review_mapping=True,
                applied_after_requests=counters["requests"],
                preserved_counters=counters,
                preserved_quota_rows=quota_before,
                original_requests=request_stream,
                backup=backup,
                config_tariff_namespaces_requests_and_zero_retry_unchanged=True,
                historical_UNKNOWN_and_current_records_holds_unchanged=True,
                completion_guarantee=False,
            )
            record["id"] = digest(record)
            before = connection.total_changes
            _append(connection, record)
            _require(
                connection.total_changes - before == 2
                and dict(connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
                == counters
                and [
                    dict(r)
                    for r in connection.execute("SELECT * FROM v10_quotas ORDER BY category")
                ]
                == quota_before,
                "funding may append only metadata/event, never counters/quotas",
            )
            _require(
                read_overlay(connection, config) == record,
                "new funding overlay verification failed",
            )
            connection.commit()
            return record
        except BaseException:
            connection.rollback()
            raise
