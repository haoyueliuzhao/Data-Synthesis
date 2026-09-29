"""One final supplementary pass for this batch's primary network UNKNOWNs.

The user explicitly superseded the former single-item future scheduling limit.
Eligibility freezes only after the original matrix terminates; no verdict-based
selection, third attempt, old-batch/mapping retries, or extra budget is permitted.
"""

import hashlib
import json
import time
from pathlib import Path

from . import v10_final_retry as single
from .contracts import digest, invocation_identity
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .v10_budget import BATCH_ID, NETWORK_POLICY, NETWORK_REASON, review_episode_id

PERMIT_KEY = "v10_network_retry_permit_01"
ACTIVATION_KEY = "v10_network_retry_activation_01"
PRIMARY_REVIEW_COUNT = 11438
USER_REPLY = "批准上述本批全部网络 UNKNOWN 补发范围"
_require, _bound, _artifact, _stored, _append = (
    single._require,
    single._bound,
    single._artifact,
    single._stored,
    single._append,
)


def authorization_definition():
    return _bound(
        dict(
            schema="v10_network_retry_authorization.v1",
            user_reply=USER_REPLY,
            initial_request="补发网络异常造成的审阅",
            question=(
                "请确认撤销此前‘仅指定1项’的未来补发限制：对本批原11438项A/B中所有已确认网络UNKNOWN"
                "（含当前24及原矩阵结束前新增），原矩阵全部终态后各仅1次attempt2；原1并入不重复，"
                "正常返回/旧批/映射不补发，原UNKNOWN/预留保留，补发结果按原规则使用，无3，"
                "总2000/子1300不变，是否批准？"
            ),
            batch_id=BATCH_ID,
            primary_expected_reviews=PRIMARY_REVIEW_COUNT,
            roles=["A", "B"],
            original_attempt_index=1,
            origin_kind="acknowledged_no_response_no_usage_connection_UNKNOWN",
            schedule_after_complete_original_matrix=True,
            freeze_all_eligible_before_supplement_results=True,
            max_supplements_per_eligible_job=1,
            supplementary_attempt_index=2,
            turn_index=0,
            original_full_holds_preserved=True,
            identical_original_HTTP_bytes=True,
            supplementary_result_decides_qualification_without_best_of=True,
            no_attempt3=True,
            no_old_batch_or_mapping_or_normal_return=True,
            unchanged_model_prompt_policy_native_rules_budget_and_request_caps=True,
            hard_cap_microcny=2_000_000_000,
            review_mapping_microcny=1_300_000_000,
            supersede_only_unactivated_single_future_scheduling=True,
        )
    )


def supplement_directory(output):
    return Path(output) / "network_retry_01"


def slot_directory(output, episode_id):
    _require(
        isinstance(episode_id, str) and episode_id.startswith("v10review:"),
        "original review episode required",
    )
    return supplement_directory(output) / "slots" / episode_id.split(":", 1)[1]


def retry_coordinates(run_id, episode_id):
    return invocation_identity(
        dict(run_id=run_id, episode_id=episode_id, attempt_index=2), turn_index=0
    )


def _check_phase(phase):
    jobs = phase.get("jobs", [])
    _require(
        phase.get("batch_id") == BATCH_ID
        and len(jobs) == PRIMARY_REVIEW_COUNT
        and len({j["episode_id"] for j in jobs}) == PRIMARY_REVIEW_COUNT
        and all(
            j.get("kind") == "review"
            and j.get("role") in {"A", "B"}
            and j["episode_id"] == review_episode_id(BATCH_ID, j["slot_id"], j["role"])
            for j in jobs
        ),
        "only the complete original current-batch A/B matrix is covered",
    )


def _has_attempt2(connection):
    return (
        connection.execute(
            "SELECT 1 FROM requests r JOIN v10_request_allocations a USING(invocation_id) "
            "JOIN v10_episode_roster s ON s.episode_id=a.episode_id "
            "WHERE s.kind='review' AND json_extract(r.coordinates_json,'$.attempt_index')=2 LIMIT 1"
        ).fetchone()
        is not None
    )


def read_network_retry_permit_from_connection(connection, config):
    permit = _stored(connection, PERMIT_KEY)
    if permit is None:
        return None
    _require(
        permit.get("schema") == "v10_network_retry_permit.v1"
        and permit.get("authorization") == authorization_definition()
        and permit.get("batch_id") == BATCH_ID
        and permit.get("run_id") == config["run_id"]
        and permit.get("config_sha256") == digest(config)
        and permit.get("primary_expected_reviews") == PRIMARY_REVIEW_COUNT
        and permit.get("supersedes_only_unsent_future_single_scheduling") is True,
        "network supplementary permit/config changed",
    )
    old = single.read_final_retry_permit_from_connection(connection, config)
    _require(
        (None if old is None else old["id"]) == permit["superseded_single_permit_id"]
        and _stored(connection, single.ACTIVATION_KEY) is None,
        "legacy single permit changed or was already activated",
    )
    return permit


def read_network_retry_permit(ledger):
    with ledger._transaction() as connection:
        return read_network_retry_permit_from_connection(connection, ledger.config)


def register_network_retry(ledger, *, authorization, primary_registration_path):
    _require(
        authorization == authorization_definition(),
        "exact current-batch network supplementary authority required",
    )
    phase, phase_ref = _artifact(primary_registration_path)
    _check_phase(phase)
    with ledger._transaction() as connection:
        old = read_network_retry_permit_from_connection(connection, ledger.config)
        if old:
            _require(old["primary_registration"] == phase_ref, "network retry matrix cannot change")
            return old
        single_permit = single.read_final_retry_permit_from_connection(connection, ledger.config)
        _require(
            _stored(connection, single.ACTIVATION_KEY) is None and not _has_attempt2(connection),
            "group registration cannot replace activated/sent supplementary work",
        )
        if single_permit:
            _require(
                single_permit["primary_registration"] == phase_ref,
                "old single permit belongs to another primary matrix",
            )
        permit = _bound(
            dict(
                schema="v10_network_retry_permit.v1",
                at_unix=time.time(),
                authorization=authorization,
                batch_id=BATCH_ID,
                run_id=ledger.run_id,
                config_sha256=digest(ledger.config),
                protocol_id=phase["protocol_id"],
                primary_registration=phase_ref,
                primary_expected_reviews=PRIMARY_REVIEW_COUNT,
                primary_job_ids_sha256=digest([j["episode_id"] for j in phase["jobs"]]),
                superseded_single_permit_id=None if single_permit is None else single_permit["id"],
                supersedes_only_unsent_future_single_scheduling=True,
                old_single_metadata_and_original_requests_unchanged=True,
            )
        )
        _append(connection, PERMIT_KEY, permit)
        return permit


def _network_target(connection, config, job, row, acknowledgments):
    iid = row["invocation_id"]
    if row["state"] != "UNKNOWN":
        return None
    ack = acknowledgments.get(iid)
    evidence = json.loads(row["evidence_json"] or "{}")
    event = connection.execute(
        "SELECT payload_json FROM events WHERE action='unknown' AND invocation_id=? "
        "ORDER BY sequence DESC LIMIT 1",
        (iid,),
    ).fetchone()
    unknown = json.loads(event[0]) if event else {}
    qualifies = (
        ack is not None
        and ack.get("schema") == "v10_connection_unknown_acknowledgement.v1"
        and ack.get("batch_id") == BATCH_ID
        and row["dispatched_at"] is not None
        and row["response_classification"] == "unknown"
        and all(
            row[k] is None
            for k in (
                "response_body",
                "response_sha256",
                "http_status",
                "usage_json",
                "settled_microcny",
                "settled_at",
            )
        )
        and evidence.get("service_response_received") is False
        and evidence.get("exception_type") in NETWORK_POLICY["exception_types"]
        and unknown
        == dict(reason=NETWORK_REASON, http_status=None, response_classification="unknown")
    )
    if not qualifies:
        return None
    body = json.loads(row["request_body"])
    _require(
        body.get("model") == "deepseek-flash"
        and body.get("thinking") == {"type": "disabled"}
        and digest(body) == row["request_sha256"]
        and evidence.get("request_sha256") == row["request_sha256"]
        and evidence.get("budget_invocation_id") == iid
        and evidence.get("budget_coordinates") == json.loads(row["coordinates_json"]),
        "eligible connection origin no longer binds its original request bytes",
    )
    return dict(
        episode_id=job["episode_id"],
        slot_id=job["slot_id"],
        task_id=job["task_id"],
        role=job["role"],
        origin_invocation_id=iid,
        original_request_sha256=row["request_sha256"],
        original_http_body_sha256=hashlib.sha256(row["request_body"]).hexdigest(),
        origin_ledger_record_sha256=_request_record_digest(row),
        origin_reserved_microcny=row["reserved_microcny"],
        original_acknowledgment_id=ack["id"],
        retry_invocation_id=retry_coordinates(config["run_id"], job["episode_id"])["invocation_id"],
    )


def read_network_retry_activation_from_connection(connection, config):
    active = _stored(connection, ACTIVATION_KEY)
    if active is None:
        return None
    permit = read_network_retry_permit_from_connection(connection, config)
    targets = active.get("targets", [])
    _require(
        permit is not None
        and active.get("schema") == "v10_network_retry_activation.v1"
        and active.get("permit_id") == permit["id"]
        and active.get("primary_registration") == permit["primary_registration"]
        and active.get("expected_reviews") == PRIMARY_REVIEW_COUNT
        and active.get("all_primary_attempt1_terminal") is True
        and active.get("target_count") == len(targets)
        and len({t["episode_id"] for t in targets}) == len(targets)
        and active.get("jobs") == [_job(t) for t in targets],
        "frozen complete-matrix network supplementary list changed",
    )
    for target in targets:
        row = connection.execute(
            "SELECT * FROM requests WHERE invocation_id=?", (target["origin_invocation_id"],)
        ).fetchone()
        coords = invocation_identity(
            dict(run_id=config["run_id"], episode_id=target["episode_id"], attempt_index=1),
            turn_index=0,
        )
        _require(
            row is not None
            and row["state"] == "UNKNOWN"
            and json.loads(row["coordinates_json"]) == coords
            and row["invocation_id"] == coords["invocation_id"]
            and _request_record_digest(row) == target["origin_ledger_record_sha256"]
            and row["reserved_microcny"] == target["origin_reserved_microcny"],
            "supplementary origin UNKNOWN/hold changed",
        )
    return active


def read_network_retry_activation(ledger):
    with ledger._transaction() as connection:
        return read_network_retry_activation_from_connection(connection, ledger.config)


def _job(target):
    return dict(
        kind="review",
        network_retry=True,
        **{
            k: target[k]
            for k in ("episode_id", "slot_id", "task_id", "role", "origin_invocation_id")
        },
    )


def activate_network_retries(ledger, *, barrier_path):
    barrier, barrier_ref = _artifact(barrier_path)
    with ledger._transaction() as connection:
        permit = read_network_retry_permit_from_connection(connection, ledger.config)
        _require(permit is not None, "register network supplementary eligibility before activation")
        prior = read_network_retry_activation_from_connection(connection, ledger.config)
        if prior:
            _require(
                prior["primary_completion"] == barrier_ref,
                "frozen activation barrier cannot change",
            )
            return prior
        _require(
            not _has_attempt2(connection), "no supplementary request may precede list activation"
        )
        phase, phase_ref = _artifact(permit["primary_registration"]["path"])
        _check_phase(phase)
        terms = barrier.get("terminals", [])
        _require(
            phase_ref == permit["primary_registration"]
            and barrier.get("schema")
            == "v10_primary_review_matrix_complete_before_network_retry.v1"
            and barrier.get("protocol_id") == phase["protocol_id"]
            and barrier.get("phase_id") == phase["id"]
            and barrier.get("expected_reviews") == len(terms) == PRIMARY_REVIEW_COUNT
            and [t["episode_id"] for t in terms] == [j["episode_id"] for j in phase["jobs"]],
            "all ordered original A/B jobs must terminate before freezing network retries",
        )
        snapshot = ledger._snapshot(connection)
        _require(
            not snapshot["pending_requests"]
            and not snapshot["unacknowledged_unknown_requests"]
            and not snapshot["halt"],
            "complete drained original matrix required",
        )
        acks = {a["invocation_id"]: a for a in _acknowledged_unknowns(connection, ledger.config)}
        targets = []
        for job, terminal in zip(phase["jobs"], terms, strict=True):
            coord = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=job["episode_id"], attempt_index=1),
                turn_index=0,
            )
            row = connection.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (coord["invocation_id"],)
            ).fetchone()
            ref = terminal.get("record", {})
            _require(
                row is not None
                and row["dispatched_at"] is not None
                and json.loads(row["coordinates_json"]) == coord
                and isinstance(ref.get("id"), str)
                and isinstance(ref.get("sha256"), str)
                and len(ref["sha256"]) == 64
                and Path(ref.get("path", "")).is_file()
                and (
                    (
                        row["state"] == "SETTLED"
                        and row["response_classification"] == "model_response"
                        and terminal["terminal_kind"] == "paid_model_return"
                    )
                    or (
                        row["state"] == "UNKNOWN"
                        and coord["invocation_id"] in acks
                        and terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    )
                ),
                "an original primary job has no authentic terminal",
            )
            target = _network_target(connection, ledger.config, job, row, acks)
            if target is not None:
                targets.append(target)
        active = _bound(
            dict(
                schema="v10_network_retry_activation.v1",
                at_unix=time.time(),
                permit_id=permit["id"],
                primary_registration=phase_ref,
                primary_completion=barrier_ref,
                expected_reviews=PRIMARY_REVIEW_COUNT,
                all_primary_attempt1_terminal=True,
                target_count=len(targets),
                targets=targets,
                jobs=[_job(t) for t in targets],
                superseded_single_permit_id=permit["superseded_single_permit_id"],
                eligibility_uses_financial_verdicts=False,
                frozen_before_any_supplement_return=True,
            )
        )
        _append(connection, ACTIVATION_KEY, active)
        return active


activate_network_retry = activate_network_retries


def check_retry_admission(connection, config, coordinates, *, request_body=None):
    permit = read_network_retry_permit_from_connection(connection, config)
    if permit is None:
        return single.check_retry_admission(
            connection, config, coordinates, request_body=request_body
        )
    active = read_network_retry_activation_from_connection(connection, config)
    _require(
        active is not None, "group permit must freeze the complete network list before any attempt2"
    )
    target = next(
        (
            t
            for t in active["targets"]
            if coordinates == retry_coordinates(config["run_id"], t["episode_id"])
        ),
        None,
    )
    _require(
        target is not None,
        "no supplementary request outside frozen network attempt2 list; no attempt3",
    )
    if request_body is not None:
        raw = connection.execute(
            "SELECT request_body FROM requests WHERE invocation_id=?",
            (target["origin_invocation_id"],),
        ).fetchone()[0]
        _require(
            isinstance(request_body, bytes) and request_body == raw,
            "supplementary HTTP bytes must equal the original network request",
        )
    return permit, active


def provider_retry_binding(ledger, request, wire):
    with ledger._transaction() as connection:
        group = read_network_retry_permit_from_connection(connection, ledger.config)
        if group is not None:
            permit, active = check_retry_admission(
                connection,
                ledger.config,
                retry_coordinates(ledger.run_id, request["episode_id"]),
                request_body=wire,
            )
            target = next(t for t in active["targets"] if t["episode_id"] == request["episode_id"])
            _require(
                request.get("protocol_id") == BATCH_ID
                and all(
                    request.get(k) == target[k]
                    for k in ("episode_id", "slot_id", "task_id", "role")
                ),
                "supplementary request differs from its frozen original job",
            )
            return dict(
                network_retry_permit=permit,
                network_retry_activation=active,
                network_retry_target=target,
            )
    return single.provider_retry_binding(ledger, request, wire)


def validate_retry_row_evidence(row, wire):
    evidence = json.loads(row["evidence_json"] or "{}")
    if "network_retry_permit" not in evidence:
        return single.validate_retry_row_evidence(row, wire)
    permit, active, target = (
        evidence.get(k, {})
        for k in ("network_retry_permit", "network_retry_activation", "network_retry_target")
    )
    coordinates = json.loads(row["coordinates_json"])
    _require(
        permit.get("id") == digest({k: v for k, v in permit.items() if k != "id"})
        and permit.get("schema") == "v10_network_retry_permit.v1"
        and permit.get("authorization") == authorization_definition()
        and permit.get("run_id") == coordinates["run_id"]
        and active.get("id") == digest({k: v for k, v in active.items() if k != "id"})
        and active.get("permit_id") == permit["id"]
        and active.get("expected_reviews") == PRIMARY_REVIEW_COUNT
        and active.get("all_primary_attempt1_terminal") is True
        and target in active.get("targets", [])
        and coordinates == retry_coordinates(coordinates["run_id"], target.get("episode_id"))
        and row["invocation_id"]
        == target.get("retry_invocation_id")
        == coordinates["invocation_id"]
        and row["request_body"] == wire
        and row["request_sha256"] == target.get("original_request_sha256")
        and hashlib.sha256(wire).hexdigest() == target.get("original_http_body_sha256"),
        "attempt2 response does not bind frozen network eligibility and original bytes",
    )
