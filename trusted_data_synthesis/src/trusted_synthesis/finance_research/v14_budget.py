"""Append-only V14 projection/mapping purposes; no new quota, money or wallet."""

import hashlib
import json
import time
from pathlib import Path

from .contracts import digest, invocation_identity
from .probe_budget import (
    UNKNOWN_ABANDONMENT_ACTION,
    UNKNOWN_ABANDONMENT_PREFIX,
    V9_NETWORK_EXCEPTIONS,
    BudgetUnavailable,
    DuplicateInvocation,
    RequestPartitionError,
    UnknownAbandonmentError,
    _acknowledged_unknowns,
    _json,
    _request_record_digest,
)
from .v10_funding import _backup, _file_sha, read_overlay
from .v13_budget import read_matrix_permit as read_parent_permit
from .v13_material_registration import read_ref

KEY = "v14_fixed_residual_material_matrix_01"
ACTION = "v14_material_matrix_registered"
BATCH_ID = "finqa-v14-20260930-representation-01"
SOURCE_BATCH_ID = "finqa-v13-20260930-material-01"
SOURCE_SEAL_ID = "a6ed08fc61b25616e78a47773e81975a161f795b56ce02b5462e406526a3bc73"
USER_REPLY = "参照审计修订并开展后续实验"
REQUEST_LIMITS = {"generation": 191000, "review_mapping": 25000}
NETWORK_REASON = "v14 transport response or usage unknown"
NETWORK_EXCEPTIONS = V9_NETWORK_EXCEPTIONS
MAX_CALLS = 323


def require(condition, message, error=RequestPartitionError):
    if not condition:
        raise error(message)


def bound(value):
    return {**value, "id": digest(value)}


def projection_episode_id(protocol_id, slot_id):
    require(
        isinstance(protocol_id, str)
        and protocol_id
        and isinstance(slot_id, str)
        and slot_id.startswith("v10gen:"),
        "V14 protocol and original V10 slot required",
    )
    return "v14projection:" + digest(dict(protocol_id=protocol_id, slot_id=slot_id))


def mapping_episode_id(protocol_id, task_id):
    require(
        isinstance(protocol_id, str) and protocol_id and isinstance(task_id, str) and task_id,
        "V14 protocol and original task required",
    )
    return "v14mapping:" + digest(dict(protocol_id=protocol_id, task_id=task_id))


def material_episode_id(protocol_id, purpose, task_id, slot_ids):
    require(
        isinstance(slot_ids, list) and len(slot_ids) == len(set(slot_ids)),
        "original distinct slot list required",
    )
    if purpose == "projection":
        require(len(slot_ids) == 1, "one projection slot required")
        return projection_episode_id(protocol_id, slot_ids[0])
    require(purpose == "mapping" and len(slot_ids) >= 2, "only real multi-package mapping is paid")
    return mapping_episode_id(protocol_id, task_id)


def authorization_definition(plan):
    return bound(
        dict(
            schema="v14_fixed_material_authorization.v1",
            user_reply=USER_REPLY,
            batch_id=BATCH_ID,
            plan_id=plan["id"],
            effective_request_limits=REQUEST_LIMITS,
            effective_hard_cap_microcny=2_000_000_000,
            effective_review_mapping_microcny=1_300_000_000,
            original_holds_preserved=True,
            exact_new_call_count=plan["expected_requests"],
            purpose_counts=plan["purpose_counts"],
            representation_review_id=plan["representation_review"]["id"],
            source_review_seal_id=SOURCE_SEAL_ID,
            quotas_increased=False,
            old_retries_authorized=False,
            training_authorized_by_this_permit=False,
            completion_guaranteed=False,
        )
    )


def read_matrix_permit(connection, config):
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (KEY,)).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    funding = read_overlay(connection, config)
    parent = read_parent_permit(connection, config)
    require(
        record.get("id") == digest({k: v for k, v in record.items() if k != "id"})
        and record.get("schema") == "v14_material_matrix_permit.v1"
        and record.get("batch_id") == BATCH_ID
        and record.get("run_id") == config["run_id"]
        and record.get("config_sha256") == digest(config)
        and record.get("effective_request_limits") == REQUEST_LIMITS
        and type(record.get("job_count")) is int
        and 0 < record["job_count"] <= MAX_CALLS
        and record["job_count"] == sum(record.get("purpose_counts", {}).values())
        and record.get("source_review_seal_id") == SOURCE_SEAL_ID
        and parent is not None
        and record.get("parent_v13_permit_id") == parent["id"]
        and record.get("source_protocol_id") == parent["plan_id"]
        and record.get("old_new_reservations_authorized") is False
        and funding is not None
        and record.get("funding_overlay_id") == funding["id"]
        and record.get("authorization")
        == authorization_definition(
            dict(
                id=record.get("plan_id"),
                expected_requests=record["job_count"],
                purpose_counts=record["purpose_counts"],
                representation_review=record["representation_review"],
            )
        )
        and connection.execute(
            "SELECT 1 FROM events WHERE action=? AND invocation_id=? AND payload_json=?",
            (ACTION, KEY, row[0]),
        ).fetchone()
        is not None,
        "V14 matrix/funding/authority binding changed",
    )
    return record


def _jobs(plan):
    concurrency = plan.get("concurrency")
    limit = concurrency.get("max") if isinstance(concurrency, dict) else concurrency
    ramp = concurrency.get("ramp") if isinstance(concurrency, dict) else None
    valid_ramp = ramp is None or (
        isinstance(ramp, list)
        and bool(ramp)
        and all(
            isinstance(stage, dict)
            and type(stage.get("settled_at_least")) is int
            and stage["settled_at_least"] >= 0
            and type(stage.get("workers")) is int
            and type(limit) is int
            and 1 <= stage["workers"] <= limit
            for stage in ramp
        )
    )
    require(
        plan.get("id") == digest({k: v for k, v in plan.items() if k != "id"})
        and plan.get("batch_id") == BATCH_ID
        and plan.get("source_batch_id") == SOURCE_BATCH_ID
        and isinstance(plan.get("source_protocol_id"), str)
        and plan["source_protocol_id"]
        and isinstance(plan.get("source_root"), str)
        and plan["source_root"]
        and plan.get("model") == "deepseek-flash"
        and type(limit) is int
        and 1 <= limit <= 16
        and valid_ramp
        and isinstance(plan.get("jobs"), list)
        and 0 < len(plan["jobs"]) == plan.get("expected_requests") <= MAX_CALLS,
        "exact registered residual V14 matrix <=323, concurrency<=16 required",
    )
    seen, purpose_ids = set(), {"projection": set(), "mapping": set()}
    for job in plan["jobs"]:
        kind = job.get("kind")
        eid = material_episode_id(plan["protocol_identity"], kind, job["task_id"], job["slot_ids"])
        require(
            job.get("episode_id") == eid
            and job.get("role") == kind
            and eid not in seen
            and isinstance(job.get("task_id"), str)
            and job["task_id"]
            and type(job.get("max_output_tokens")) is int
            and job["max_output_tokens"] in (2048, 4096, 8192, 16384, 32768, 65536, 131072)
            and all(
                isinstance(job.get(k), str)
                and len(job[k]) == 64
                and all(c in "0123456789abcdef" for c in job[k])
                for k in ("request_sha256", "request_body_sha256")
            ),
            "V14 fixed coordinates/cap/exact request hashes required",
        )
        seen.add(eid)
        require(
            job.get("slot_id") == (job["slot_ids"][0] if kind == "projection" else None),
            "projection/mapping coordinates differ",
        )
        identity = job["slot_id"] if kind == "projection" else job["task_id"]
        require(identity not in purpose_ids[kind], "each fixed purpose is called once")
        purpose_ids[kind].add(identity)
    require(
        {k: len(v) for k, v in purpose_ids.items()} == plan["purpose_counts"],
        "exact fixed purpose counts required",
    )
    return plan["jobs"]


def register_matrix(ledger, plan, authorization, *, backup_path):
    """Explicit backup + append registration, with no change to original rows/counters."""
    jobs = _jobs(plan)
    require(
        authorization == authorization_definition(plan), "exact new material authority required"
    )
    source_path = Path(plan["source_root"]) / "completion_seal/record.json"
    source_raw = source_path.read_bytes()
    source_seal = json.loads(source_raw)
    require(
        source_seal.get("id") == SOURCE_SEAL_ID == plan.get("source_review_seal_id")
        and digest({k: v for k, v in source_seal.items() if k != "id"}) == SOURCE_SEAL_ID,
        "fixed source V13 completion seal differs",
    )
    representation = read_ref(plan["representation_review"])
    require(
        representation["schema"] == "v14_representation_review.v1"
        and representation["mapping_review_count"] == 633
        and representation["original_successes_preserved"] == 325
        and representation["original_success_partition_evidence_chi_unchanged"] is True,
        "uniform existing-return review and original accepted authority preservation required",
    )
    definition = read_ref(plan["definition"])
    parent_population = read_ref(definition["source_v13_definition"])
    residual_projection = set(representation["residual_projection_slot_ids"])
    residual_mapping = set(representation["residual_mapping_task_ids"])
    network_tasks = set(representation["network_unknown_task_ids"])
    require(
        1 <= len(residual_projection) <= 3
        and 64 <= len(residual_mapping) <= 320
        and representation["m"] == 320 - len(residual_mapping)
        and representation["b"] == 3 - len(residual_projection)
        and len(network_tasks) == 12
        and network_tasks <= residual_mapping
        and len(jobs) == len(residual_projection) + len(residual_mapping),
        "offline review must freeze the exact unresolved scope; no assumed restoration credit",
    )
    backup_path = Path(backup_path).resolve()
    with ledger._transaction() as db:
        prior = read_matrix_permit(db, ledger.config)
        if prior:
            require(
                prior["plan_id"] == plan["id"]
                and prior["authorization"] == authorization
                and prior["backup"]["path"] == str(backup_path)
                and backup_path.is_file()
                and _file_sha(backup_path) == prior["backup"]["sha256"],
                "registered matrix/backup cannot be replaced",
            )
            return prior
        state = ledger._snapshot(db)
        funding = read_overlay(db, ledger.config)
        parent = read_parent_permit(db, ledger.config)
        require(
            not state["pending_requests"]
            and not state["unacknowledged_unknown_requests"]
            and not state["halt"]
            and funding is not None
            and parent is not None
            and parent["plan_id"] == plan["source_protocol_id"]
            and state["effective_hard_cap_microcny"] == 2_000_000_000
            and state["request_cap"] == 258000,
            "V14 registration requires quiescent original funded wallet",
        )
        counters = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        quotas = [dict(r) for r in db.execute("SELECT * FROM v10_quotas ORDER BY category")]
        require(
            all(q["requests"] <= REQUEST_LIMITS[q["category"]] for q in quotas),
            "original effective request caps already exceeded",
        )
        source = {
            r["slot_id"]: r["task_id"]
            for r in db.execute(
                "SELECT slot_id,task_id FROM v10_episode_roster WHERE kind='generation'"
            )
        }
        common = set(parent_population["candidate_slot_ids"])
        blocked = residual_projection
        require(
            len(common) == 2468 and blocked <= common,
            "source fixed candidate/projection scope changed",
        )
        groups = {}
        for sid in common:
            require(sid in source, "source common package absent from original roster")
            groups.setdefault(source[sid], set()).add(sid)
        multi = {task: slots for task, slots in groups.items() if len(slots) >= 2}
        require(
            len(groups) == 744 and len(multi) == 645, "fixed original common task partition changed"
        )
        require(
            {task: set(slots) for task, slots in plan["fixed_task_slots"].items()} == groups
            and all(len(slots) == len(set(slots)) for slots in plan["fixed_task_slots"].values()),
            "plan task grouping must equal the complete original common support",
        )
        require(
            {j["slot_id"] for j in jobs if j["kind"] == "projection"} == residual_projection
            and {j["task_id"] for j in jobs if j["kind"] == "mapping"} == residual_mapping
            and all(
                all(source.get(sid) == j["task_id"] for sid in j["slot_ids"])
                and set(j["slot_ids"])
                == ({j["slot_id"]} if j["kind"] == "projection" else multi[j["task_id"]])
                for j in jobs
            ),
            "V14 must include exactly missing projections and each whole multi-package task",
        )
        old_unknowns = {}
        for reference in representation["network_unknown_sources"]:
            row = db.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (reference["invocation_id"],)
            ).fetchone()
            require(
                row is not None
                and row["state"] == "UNKNOWN"
                and row["usage_json"] is None
                and row["response_body"] is None
                and _request_record_digest(row) == reference["original_ledger_record_sha256"],
                "network recovery must preserve the exact original UNKNOWN/held request",
            )
            coords = json.loads(row["coordinates_json"])
            original_job = db.execute(
                "SELECT job_json FROM v13_review_roster WHERE episode_id=?", (coords["episode_id"],)
            ).fetchone()
            original_job = json.loads(original_job[0]) if original_job else {}
            require(
                original_job.get("kind") == "mapping"
                and original_job.get("task_id") == reference["task_id"]
                and original_job.get("request_sha256") == row["request_sha256"],
                "old UNKNOWN must belong to this same V13 task/mapping, never another batch",
            )
            old_unknowns[reference["task_id"]] = dict(
                invocation_id=row["invocation_id"],
                original_row_sha256=_request_record_digest(row),
                permanent_reserved_microcny=row["reserved_microcny"],
            )
        require(
            set(old_unknowns) == network_tasks,
            "exact twelve original network recovery sources required",
        )
        for job in jobs:
            reason = (
                "projection_completion"
                if job["kind"] == "projection"
                else (
                    "network_recovery_new_once"
                    if job["task_id"] in network_tasks
                    else "mapping_completion"
                )
            )
            require(job["authority_reason"] == reason, "new field authority/recovery scope differs")
        require(
            not db.execute(
                "SELECT 1 FROM requests WHERE "
                "json_extract(coordinates_json,'$.episode_id') LIKE 'v14%' LIMIT 1"
            ).fetchone(),
            "V14 namespace already used without registration",
        )
        backup = _backup(Path(ledger.path).resolve(), backup_path)
        record = bound(
            dict(
                schema="v14_material_matrix_permit.v1",
                run_id=ledger.run_id,
                config_sha256=digest(ledger.config),
                batch_id=BATCH_ID,
                protocol_id=plan["protocol_identity"],
                plan_id=plan["id"],
                concurrency=plan["concurrency"],
                source_batch_id=SOURCE_BATCH_ID,
                source_protocol_id=plan["source_protocol_id"],
                source_root=plan["source_root"],
                source_review_seal_id=SOURCE_SEAL_ID,
                source_review_seal_sha256=hashlib.sha256(source_raw).hexdigest(),
                parent_v13_permit_id=parent["id"],
                representation_review=plan["representation_review"],
                original_network_unknowns=old_unknowns,
                funding_overlay_id=funding["id"],
                original_partition_id=state["v10_partition"]["id"],
                authorization=authorization,
                effective_request_limits=REQUEST_LIMITS,
                original_request_limits={"generation": 199000, "review_mapping": 17000},
                transferred_unused_generation_requests=0,
                money_limits_unchanged=True,
                request_limits_unchanged=True,
                purpose_counts=plan["purpose_counts"],
                old_new_reservations_authorized=False,
                no_retry=True,
                job_count=len(jobs),
                roster_sha256=digest(jobs),
                backup=backup,
                preserved_counters=counters,
                preserved_quota_rows=quotas,
                applied_after_requests=counters["requests"],
                registered_at_unix=time.time(),
            )
        )
        db.execute(
            "CREATE TABLE v14_review_roster (episode_id TEXT PRIMARY KEY,job_json TEXT NOT NULL)"
        )
        db.executemany(
            "INSERT INTO v14_review_roster VALUES (?,?)",
            [(j["episode_id"], _json(j)) for j in jobs],
        )
        db.execute("INSERT INTO metadata VALUES (?,?)", (KEY, _json(record)))
        ledger._event(db, KEY, ACTION, record)
        require(
            dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone()) == counters
            and [dict(r) for r in db.execute("SELECT * FROM v10_quotas ORDER BY category")]
            == quotas,
            "registration must not change original counters/quota rows",
        )
        require(read_matrix_permit(db, ledger.config) == record, "new permit failed replay")
        return record


def eligible(connection, config, coordinates, output_limit, *, request_body=None):
    permit = read_matrix_permit(connection, config)
    require(permit is not None, "V14 matrix not registered", BudgetUnavailable)
    row = connection.execute(
        "SELECT job_json FROM v14_review_roster WHERE episode_id=?", (coordinates["episode_id"],)
    ).fetchone()
    require(row is not None, "episode outside exact V14 material matrix", BudgetUnavailable)
    job = json.loads(row[0])
    require(
        coordinates["attempt_index"] == 1
        and coordinates["turn_index"] == 0
        and output_limit == job["max_output_tokens"]
        and job["episode_id"]
        == material_episode_id(permit["protocol_id"], job["kind"], job["task_id"], job["slot_ids"]),
        "V14 forbids changed coordinates/caps/retries",
        BudgetUnavailable,
    )
    if request_body is not None:
        require(
            hashlib.sha256(request_body).hexdigest() == job["request_body_sha256"]
            and digest(json.loads(request_body)) == job["request_sha256"],
            "V14 original registered HTTP bytes changed",
            BudgetUnavailable,
        )
    return "review_mapping"


def continue_reserved(ledger, invocation_id, *, coordinates, request, request_body):
    with ledger._transaction() as db:
        row = db.execute(
            "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
        ).fetchone()
        require(
            row is not None
            and row["state"] == "RESERVED"
            and row["dispatched_at"] is None
            and all(row[k] is None for k in ("response_body", "usage_json", "settled_microcny"))
            and json.loads(row["coordinates_json"]) == coordinates
            and coordinates["run_id"] == ledger.run_id
            and invocation_identity(coordinates, turn_index=0) == coordinates
            and row["request_body"] == request_body
            and json.loads(request_body) == request
            and row["request_sha256"] == digest(request),
            "only exact confirmed-unsent V14 reservation can continue",
            DuplicateInvocation,
        )
        eligible(db, ledger.config, coordinates, request["max_tokens"], request_body=request_body)
        state = ledger._snapshot(db)
        require(
            not state["halt"] and not state["unacknowledged_unknown_requests"],
            "halted reservation cannot dispatch",
            BudgetUnavailable,
        )
        return row["reserved_microcny"]


def acknowledge_connection_unknowns(ledger, *, protocol_id, expected_requests):
    """Acknowledge no-response errors after drain, never release holds or authorize retries.

    An input may include previously acknowledged V14 rows for cold recovery. The
    independent same-wave controller stop guard never changes billing terminality.
    """
    require(
        isinstance(expected_requests, dict) and expected_requests,
        "exact nonempty unknown request map required",
        UnknownAbandonmentError,
    )
    signature = dict(protocol_id=protocol_id, expected_requests=expected_requests)
    key = "v14_network_terminal:" + digest(signature)
    with ledger._transaction() as db:
        permit = read_matrix_permit(db, ledger.config)
        require(
            permit and permit["protocol_id"] == protocol_id,
            "V14 network authority absent",
            UnknownAbandonmentError,
        )
        state = ledger._snapshot(db)
        acked = {r["invocation_id"]: r for r in _acknowledged_unknowns(db, ledger.config)}
        unknown = {
            r["invocation_id"]: r
            for r in db.execute("SELECT * FROM requests WHERE state='UNKNOWN'")
        }
        unack = set(unknown) - set(acked)
        require(
            not state["pending_requests"] and unack == set(expected_requests) - set(acked),
            "all in-flight requests must drain and exact unacknowledged set be covered",
            UnknownAbandonmentError,
        )
        evidence = {}
        for iid, sha in expected_requests.items():
            row = unknown.get(iid)
            require(
                row is not None, "only UNKNOWN rows may be acknowledged", UnknownAbandonmentError
            )
            coords, body = json.loads(row["coordinates_json"]), json.loads(row["request_body"])
            detail = json.loads(row["evidence_json"] or "{}")
            event = db.execute(
                "SELECT payload_json FROM events WHERE invocation_id=? AND action='unknown' "
                "ORDER BY sequence DESC LIMIT 1",
                (iid,),
            ).fetchone()
            eligible(
                db, ledger.config, coords, body["max_tokens"], request_body=row["request_body"]
            )
            require(
                row["dispatched_at"] is not None
                and row["request_sha256"] == sha
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
                and row["response_classification"] == "unknown"
                and detail.get("exception_type") in V9_NETWORK_EXCEPTIONS
                and detail.get("service_response_received") is False
                and detail.get("budget_invocation_id") == iid
                and detail.get("budget_coordinates") == coords
                and detail.get("request_sha256") == sha
                and event is not None
                and json.loads(event[0])
                == dict(reason=NETWORK_REASON, http_status=None, response_classification="unknown"),
                "only new-matrix no-response connection UNKNOWN may be acknowledged",
                UnknownAbandonmentError,
            )
            if iid in acked:
                require(
                    acked[iid].get("permit_id") == permit["id"],
                    "different-scope acknowledgement",
                    UnknownAbandonmentError,
                )
            evidence[iid] = detail
        prior = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if prior:
            receipt = json.loads(prior[0])
            require(
                receipt.get("id") == digest({k: v for k, v in receipt.items() if k != "id"})
                and receipt["permit_id"] == permit["id"]
                and not unack
                and receipt["records"] == [acked[i] for i in sorted(expected_requests)],
                "terminal receipt changed",
                UnknownAbandonmentError,
            )
            return receipt
        halt = None
        if unack:
            halt_row = db.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
            halt = json.loads(halt_row[0]) if halt_row else {}
            require(
                halt.get("invocation_id") in unack
                and halt.get("reason") == NETWORK_REASON
                and halt.get("evidence") == evidence.get(halt.get("invocation_id")),
                "unrelated halt must remain stopped",
                UnknownAbandonmentError,
            )
            start = min(unknown[i]["dispatched_at"] for i in unack)
            for event in db.execute(
                "SELECT payload_json FROM events WHERE action='halt' AND at_unix>=?", (start,)
            ):
                item = json.loads(event[0])
                require(
                    item.get("invocation_id") in unack
                    and item.get("reason") == NETWORK_REASON
                    and item.get("evidence") == evidence.get(item.get("invocation_id")),
                    "uncovered non-network halt cannot be cleared",
                    UnknownAbandonmentError,
                )
            for iid in sorted(unack):
                row = unknown[iid]
                record = bound(
                    dict(
                        schema="v14_connection_unknown_acknowledgement.v1",
                        run_id=ledger.run_id,
                        permit_id=permit["id"],
                        protocol_id=protocol_id,
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
                    )
                )
                db.execute(
                    "INSERT INTO metadata VALUES (?,?)",
                    (UNKNOWN_ABANDONMENT_PREFIX + iid, _json(record)),
                )
                ledger._event(db, iid, UNKNOWN_ABANDONMENT_ACTION, record)
                acked[iid] = record
            require(
                db.execute(
                    "DELETE FROM metadata WHERE key='halt' AND value=?", (halt_row[0],)
                ).rowcount
                == 1,
                "covered halt changed",
                UnknownAbandonmentError,
            )
        receipt = bound(
            dict(
                schema="v14_connection_unknown_terminal_receipt.v1",
                **signature,
                permit_id=permit["id"],
                records=[acked[i] for i in sorted(expected_requests)],
                drained_wave_unknown_count=len(unack),
                cleared_exact_halt=halt,
                original_rows_unchanged=True,
                permanent_holds_unchanged=True,
                automatic_resend=False,
            )
        )
        db.execute("INSERT INTO metadata VALUES (?,?)", (key, _json(receipt)))
        ledger._event(db, key, "v14_network_terminal", receipt)
        return receipt
