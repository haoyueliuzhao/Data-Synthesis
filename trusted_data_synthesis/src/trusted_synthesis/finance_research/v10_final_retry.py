"""Exactly one authorized last supplementary call, never a generic retry policy."""

import hashlib
import json
import time
from pathlib import Path

from .contracts import digest, invocation_identity
from .probe_budget import BudgetUnavailable, _acknowledged_unknowns, _json, _request_record_digest
from .v10_budget import BATCH_ID

ORIGIN_INVOCATION_ID = "invocation:90d0508e9d9354283eddc62b377a36ceeefc525ea54644fa6bf98dc1e617aa82"
EPISODE_ID = "v10review:689a196d84b61eadcfb607013a8ecfd72dfb01ebaaa972453d38f109126942c3"
SLOT_ID = "v10gen:674288ee509dea1be51ddd31d066917f9db8d5b42a194232796552da02eb07e6"
TASK_ID = "C/2009/page_141.pdf-2"
ROLE = "A"
ORIGINAL_REQUEST_SHA256 = "c7e4f6005c5b932b399f5851bff208f6035706a2c5189d220730e934bff601e9"
PRIMARY_REVIEW_COUNT = 11438
PERMIT_KEY = "v10_single_final_retry_permit_01"
ACTIVATION_KEY = "v10_single_final_retry_activation_01"
USER_REPLY = "按此范围最后补发一次"


def _require(value, message):
    if not value:
        raise BudgetUnavailable(message)


def _bound(value):
    return {**value, "id": digest(value)}


def _scope():
    return dict(
        batch_id=BATCH_ID,
        origin_invocation_id=ORIGIN_INVOCATION_ID,
        episode_id=EPISODE_ID,
        slot_id=SLOT_ID,
        task_id=TASK_ID,
        role=ROLE,
        original_request_sha256=ORIGINAL_REQUEST_SHA256,
        attempt_index=2,
        turn_index=0,
        last_after_complete_primary_matrix=True,
        max_additional_requests=1,
        original_full_hold_preserved=True,
        no_best_of=True,
        no_attempt3=True,
        other_UNKNOWNs_not_authorized=True,
    )


def authorization_definition():
    return _bound(
        dict(
            schema="v10_single_final_retry_authorization.v1",
            **_scope(),
            user_reply=USER_REPLY,
            question=(
                "当前固定矩阵结束后，仅对此次停派期间的1项UNKNOWN补发一次；保留原UNKNOWN和全部预留，"
                "用事前登记补发返回决定该槽位最终资格，不择优；补发若仍失败不再重试，其他UNKNOWN不自动扩展"
            ),
        )
    )


def supplement_directory(output):
    return Path(output) / "final_retry_01"


def retry_coordinates(run_id):
    return invocation_identity(
        dict(run_id=run_id, episode_id=EPISODE_ID, attempt_index=2), turn_index=0
    )


def _artifact(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = json.loads(raw)
    _require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "retry artifact identity changed",
    )
    return value, dict(path=str(path), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())


def _stored(connection, key):
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    if row is None:
        return None
    value = json.loads(row[0])
    _require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and connection.execute(
            "SELECT 1 FROM events WHERE action=? AND invocation_id=? AND payload_json=?",
            (key, key, row[0]),
        ).fetchone()
        is not None,
        "retry permit/activation immutable event binding changed",
    )
    return value


def _permit_shape(value, config):
    _require(
        value.get("schema") == "v10_single_final_retry_permit.v1"
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and value.get("authorization") == authorization_definition()
        and all(value.get(k) == v for k, v in _scope().items())
        and value.get("run_id") == config["run_id"]
        and value.get("config_sha256") == digest(config)
        and value.get("origin_reserved_microcny") == 2_113_536,
        "not the single specifically authorized last call",
    )


def read_final_retry_permit_from_connection(connection, config):
    permit = _stored(connection, PERMIT_KEY)
    if permit is None:
        return None
    _permit_shape(permit, config)
    original = connection.execute(
        "SELECT * FROM requests WHERE invocation_id=?", (ORIGIN_INVOCATION_ID,)
    ).fetchone()
    coords = invocation_identity(
        dict(run_id=config["run_id"], episode_id=EPISODE_ID, attempt_index=1), turn_index=0
    )
    _require(
        original is not None
        and original["state"] == "UNKNOWN"
        and original["invocation_id"] == coords["invocation_id"]
        and json.loads(original["coordinates_json"]) == coords
        and original["request_sha256"] == ORIGINAL_REQUEST_SHA256
        and original["reserved_microcny"] == 2_113_536
        and original["dispatched_at"] is not None
        and all(
            original[k] is None
            for k in ("response_body", "http_status", "usage_json", "settled_microcny")
        )
        and _request_record_digest(original) == permit["origin_ledger_record_sha256"]
        and hashlib.sha256(original["request_body"]).hexdigest()
        == permit["original_http_body_sha256"],
        "original UNKNOWN/bytes/full reservation no longer match the permit",
    )
    return permit


def read_final_retry_permit(ledger):
    with ledger._transaction() as connection:
        return read_final_retry_permit_from_connection(connection, ledger.config)


def _append(connection, key, value):
    payload = _json(value)
    connection.execute("INSERT INTO metadata VALUES (?,?)", (key, payload))
    connection.execute(
        "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,?)",
        (key, key, payload, time.time()),
    )


def register_final_retry(ledger, *, authorization, primary_registration_path):
    _require(
        authorization == authorization_definition(),
        "only the exact one-call user authority is supported",
    )
    phase, phase_ref = _artifact(primary_registration_path)
    _require(
        phase.get("batch_id") == BATCH_ID
        and len(phase["jobs"]) == PRIMARY_REVIEW_COUNT
        and len({j["episode_id"] for j in phase["jobs"]}) == PRIMARY_REVIEW_COUNT
        and sum(
            j["episode_id"] == EPISODE_ID
            and j["slot_id"] == SLOT_ID
            and j["task_id"] == TASK_ID
            and j["role"] == ROLE
            for j in phase["jobs"]
        )
        == 1,
        "exact full original review registration and target required",
    )
    with ledger._transaction() as connection:
        prior = read_final_retry_permit_from_connection(connection, ledger.config)
        if prior:
            _require(
                prior["primary_registration"] == phase_ref, "retry primary matrix cannot change"
            )
            return prior
        row = connection.execute(
            "SELECT * FROM requests WHERE invocation_id=?", (ORIGIN_INVOCATION_ID,)
        ).fetchone()
        _require(row is not None, "specified original UNKNOWN not found")
        acknowledgments = {
            r["invocation_id"]: r for r in _acknowledged_unknowns(connection, ledger.config)
        }
        _require(
            ORIGIN_INVOCATION_ID in acknowledgments,
            "original full-hold terminal acknowledgement required",
        )
        record = _bound(
            dict(
                schema="v10_single_final_retry_permit.v1",
                **_scope(),
                at_unix=time.time(),
                authorization=authorization,
                run_id=ledger.run_id,
                config_sha256=digest(ledger.config),
                primary_registration=phase_ref,
                primary_job_ids_sha256=digest([j["episode_id"] for j in phase["jobs"]]),
                protocol_id=phase["protocol_id"],
                primary_expected_reviews=PRIMARY_REVIEW_COUNT,
                origin_ledger_record_sha256=_request_record_digest(row),
                origin_reserved_microcny=row["reserved_microcny"],
                original_http_body_sha256=hashlib.sha256(row["request_body"]).hexdigest(),
                original_acknowledgment_id=acknowledgments[ORIGIN_INVOCATION_ID]["id"],
            )
        )
        _append(connection, PERMIT_KEY, record)
        _require(
            read_final_retry_permit_from_connection(connection, ledger.config) == record,
            "new retry permit does not bind the original",
        )
        return record


def read_final_retry_activation_from_connection(connection, config):
    record = _stored(connection, ACTIVATION_KEY)
    if record is None:
        return None
    permit = read_final_retry_permit_from_connection(connection, config)
    _require(
        permit is not None
        and record.get("schema") == "v10_final_retry_activation.v1"
        and record.get("permit_id") == permit["id"]
        and record.get("expected_reviews") == PRIMARY_REVIEW_COUNT
        and record.get("primary_registration") == permit["primary_registration"]
        and record.get("all_primary_attempt1_terminal") is True,
        "single retry activation is not bound to the complete original matrix",
    )
    return record


def activate_final_retry(ledger, *, barrier_path):
    barrier, barrier_ref = _artifact(barrier_path)
    with ledger._transaction() as connection:
        permit = read_final_retry_permit_from_connection(connection, ledger.config)
        _require(permit is not None, "register the exact retry permit first")
        prior = read_final_retry_activation_from_connection(connection, ledger.config)
        if prior:
            _require(
                prior["primary_completion"] == barrier_ref, "retry completion barrier cannot change"
            )
            return prior
        phase, phase_ref = _artifact(permit["primary_registration"]["path"])
        terms = barrier.get("terminals", [])
        ids = [j["episode_id"] for j in phase["jobs"]]
        _require(
            phase_ref == permit["primary_registration"]
            and barrier.get("schema") == "v10_primary_review_matrix_complete_before_final_retry.v1"
            and barrier.get("protocol_id") == phase["protocol_id"]
            and barrier.get("phase_id") == phase["id"]
            and barrier.get("expected_reviews") == len(terms) == len(ids) == PRIMARY_REVIEW_COUNT
            and [t["episode_id"] for t in terms] == ids,
            "all ordered original review jobs must terminate before the supplementary call",
        )
        snapshot = ledger._snapshot(connection)
        _require(
            not snapshot["pending_requests"]
            and not snapshot["halt"]
            and not snapshot["unacknowledged_unknown_requests"],
            "retry activation requires drained original matrix",
        )
        acks = {r["invocation_id"] for r in _acknowledged_unknowns(connection, ledger.config)}
        for term in terms:
            coord = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=term["episode_id"], attempt_index=1),
                turn_index=0,
            )
            row = connection.execute(
                "SELECT state,response_classification,dispatched_at FROM requests "
                "WHERE invocation_id=?",
                (coord["invocation_id"],),
            ).fetchone()
            reference = term.get("record", {})
            _require(
                row is not None
                and row["dispatched_at"] is not None
                and isinstance(reference.get("sha256"), str)
                and len(reference["sha256"]) == 64
                and isinstance(reference.get("id"), str)
                and Path(reference.get("path", "")).is_file()
                and (
                    (
                        row["state"] == "SETTLED"
                        and row["response_classification"] == "model_response"
                        and term["terminal_kind"] == "paid_model_return"
                    )
                    or (
                        row["state"] == "UNKNOWN"
                        and coord["invocation_id"] in acks
                        and term["terminal_kind"] == "acknowledged_connection_unknown"
                    )
                ),
                "an original matrix job lacks its real returned or acknowledged terminal",
            )
        record = _bound(
            dict(
                schema="v10_final_retry_activation.v1",
                at_unix=time.time(),
                permit_id=permit["id"],
                primary_registration=phase_ref,
                primary_completion=barrier_ref,
                expected_reviews=PRIMARY_REVIEW_COUNT,
                all_primary_attempt1_terminal=True,
                primary_job_ids_sha256=digest(ids),
                retry_invocation_id=retry_coordinates(ledger.run_id)["invocation_id"],
            )
        )
        _append(connection, ACTIVATION_KEY, record)
        return record


def check_retry_admission(connection, config, coordinates, *, request_body=None):
    permit = read_final_retry_permit_from_connection(connection, config)
    activation = read_final_retry_activation_from_connection(connection, config)
    _require(
        permit is not None
        and activation is not None
        and coordinates == retry_coordinates(config["run_id"]),
        "only the activated one-off original attempt2 is allowed; no other retry",
    )
    if request_body is not None:
        original = connection.execute(
            "SELECT request_body FROM requests WHERE invocation_id=?", (ORIGIN_INVOCATION_ID,)
        ).fetchone()[0]
        _require(
            isinstance(request_body, bytes) and request_body == original,
            "supplementary HTTP bytes must exactly equal the original request",
        )
    return permit, activation


def provider_retry_binding(ledger, request, wire):
    _require(
        request.get("protocol_id") == BATCH_ID
        and request.get("episode_id") == EPISODE_ID
        and request.get("slot_id") == SLOT_ID
        and request.get("task_id") == TASK_ID
        and request.get("role") == ROLE,
        "no supplementary call for another slot/role/task",
    )
    with ledger._transaction() as connection:
        permit, active = check_retry_admission(
            connection, ledger.config, retry_coordinates(ledger.run_id), request_body=wire
        )
        return dict(final_retry_permit=permit, final_retry_activation=active)


def validate_retry_row_evidence(row, wire):
    """Restore from the actual ledger row, not a claimed second model response.

    Material loading additionally compares these witnesses to the immutable
    metadata using the two read_*_from_connection functions.
    """
    coordinates = json.loads(row["coordinates_json"])
    evidence = json.loads(row["evidence_json"] or "{}")
    permit, active = (
        evidence.get("final_retry_permit", {}),
        evidence.get("final_retry_activation", {}),
    )
    _require(
        coordinates == retry_coordinates(coordinates["run_id"])
        and row["invocation_id"] == coordinates["invocation_id"]
        and permit.get("id") == digest({k: v for k, v in permit.items() if k != "id"})
        and permit.get("authorization") == authorization_definition()
        and all(permit.get(k) == v for k, v in _scope().items())
        and permit.get("run_id") == coordinates["run_id"]
        and permit.get("origin_reserved_microcny") == 2_113_536
        and hashlib.sha256(wire).hexdigest() == permit.get("original_http_body_sha256")
        and row["request_body"] == wire
        and row["request_sha256"] == ORIGINAL_REQUEST_SHA256
        and active.get("id") == digest({k: v for k, v in active.items() if k != "id"})
        and active.get("permit_id") == permit["id"]
        and active.get("expected_reviews") == PRIMARY_REVIEW_COUNT
        and active.get("all_primary_attempt1_terminal") is True,
        "attempt2 ledger response does not bind the same one-off authority/original bytes",
    )
