"""Append three exact adjudications to the same wallet, preserving historical holds."""

import hashlib
import json
import time
from pathlib import Path

from .contracts import digest, invocation_identity
from .probe_budget import BudgetUnavailable, DuplicateInvocation, RequestPartitionError, _json
from .v10_funding import _backup, _file_sha
from .v13_material_registration import read_ref
from .v16_budget import read_matrix_permit as read_parent_permit

KEY = "v17_fixed_three_adjudication_matrix_01"
ACTION = "v17_three_adjudication_registered"
BATCH_ID = "finqa-v17-20260930-three-task-continuation-01"
NETWORK_REASON = "v17 transport response or usage unknown"
REQUEST_LIMITS = {"generation": 191000, "review_mapping": 25000}


def require(condition, message, error=RequestPartitionError):
    if not condition:
        raise error(message)


def bound(value):
    return {**value, "id": digest(value)}


def mapping_episode_id(protocol_id, task_id):
    require(
        isinstance(protocol_id, str) and protocol_id and isinstance(task_id, str) and task_id,
        "original task and three-task protocol required",
    )
    return "v17mapping:" + digest(dict(protocol_id=protocol_id, task_id=task_id))


def authorization_definition(plan):
    return bound(
        dict(
            schema="v17_fixed_three_authorization.v1",
            user_reply="追加授权，同时授权推送",
            plan_id=plan["id"],
            batch_id=BATCH_ID,
            predecessor_registration=plan["predecessor_registration"],
            fixed_task_ids=plan["fixed_unresolved_task_ids"],
            exact_new_call_count=3,
            original_packages=13,
            effective_request_limits=REQUEST_LIMITS,
            effective_hard_cap_microcny=2_000_000_000,
            effective_review_mapping_microcny=1_300_000_000,
            quotas_increased=False,
            original_holds_preserved=True,
            old_retries_authorized=False,
            automatic_retries=False,
            training_authorized_by_this_permit=False,
        )
    )


def read_matrix_permit(connection, config):
    row = connection.execute("SELECT value FROM metadata WHERE key=?", (KEY,)).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    parent = read_parent_permit(connection, config)
    require(
        record.get("id") == digest({k: v for k, v in record.items() if k != "id"})
        and record.get("schema") == "v17_three_adjudication_permit.v1"
        and record.get("batch_id") == BATCH_ID
        and record.get("run_id") == config["run_id"]
        and record.get("config_sha256") == digest(config)
        and record.get("job_count") == 3
        and parent is not None
        and record.get("parent_v16_permit_id") == parent["id"]
        and record.get("source_plan_id") == parent["plan_id"]
        and record.get("effective_request_limits") == REQUEST_LIMITS
        and record.get("authorization")
        == authorization_definition(
            dict(
                id=record.get("plan_id"),
                predecessor_registration=record.get("predecessor_registration"),
                fixed_unresolved_task_ids=record.get("fixed_unresolved_task_ids"),
            )
        )
        and connection.execute(
            "SELECT 1 FROM events WHERE action=? AND invocation_id=? AND payload_json=?",
            (ACTION, KEY, row[0]),
        ).fetchone()
        is not None,
        "appended three-task permit and unchanged original funded wallet required",
    )
    return record


def _jobs(plan):
    require(
        plan.get("id") == digest({k: v for k, v in plan.items() if k != "id"})
        and plan.get("schema") == "v17_three_task_adjudication_plan.v1"
        and plan.get("batch_id") == BATCH_ID
        and plan.get("model") == "deepseek-flash"
        and plan.get("expected_requests") == 3
        and plan.get("concurrency") == {"max": 3}
        and plan.get("purpose_counts") == {"mapping": 3}
        and isinstance(plan.get("jobs"), list)
        and len(plan["jobs"]) == 3,
        "exact three-task once-only flash matrix required",
    )
    jobs = plan["jobs"]
    require(
        len({j["task_id"] for j in jobs}) == 3
        and {j["task_id"] for j in jobs} == set(plan["fixed_unresolved_task_ids"])
        and sum(len(j["slot_ids"]) for j in jobs) == 13,
        "three distinct tasks and 13 original packages, no quota-derived expansion",
    )
    for job in jobs:
        require(
            job.get("episode_id") == mapping_episode_id(plan["protocol_identity"], job["task_id"])
            and job.get("kind") == job.get("purpose") == job.get("role") == "mapping"
            and job.get("slot_id") is None
            and len(job["slot_ids"]) == len(set(job["slot_ids"]))
            and job["slot_ids"] == plan["fixed_task_slots"][job["task_id"]]
            and type(job.get("max_output_tokens")) is int
            and job["max_output_tokens"] == 8192
            and all(
                isinstance(job.get(k), str)
                and len(job[k]) == 64
                and all(c in "0123456789abcdef" for c in job[k])
                for k in ("request_sha256", "request_body_sha256")
            ),
            "registered original task, request bytes, cap and coordinates required",
        )
    return jobs


def register_matrix(ledger, plan, authorization, *, backup_path):
    from .v17_registration import original_authorities

    jobs = _jobs(plan)
    require(
        authorization == authorization_definition(plan), "specific three-task authority required"
    )
    definition = read_ref(plan["definition"])
    previous, parent_definition, inherited, failed = original_authorities(plan["predecessor_root"])
    require(
        plan["predecessor_registration"] == definition["predecessor_registration"]
        and read_ref(plan["predecessor_registration"]) == previous
        and previous["id"] == plan["source_protocol_id"]
        and definition["inherited_mapping_authorities"] == inherited
        and definition["previous_failed_authorities"] == failed
        and set(plan["fixed_unresolved_task_ids"]) == set(failed)
        and plan["fixed_task_slots"] == parent_definition["fixed_task_slots"],
        "only actual residual three; all 741 original authorities unchanged",
    )
    backup_path = Path(backup_path).resolve()
    with ledger._transaction() as db:
        prior = read_matrix_permit(db, ledger.config)
        if prior:
            require(
                prior["plan_id"] == plan["id"]
                and prior["authorization"] == authorization
                and prior["backup"]["path"] == str(backup_path)
                and _file_sha(backup_path) == prior["backup"]["sha256"],
                "permit/backup immutable",
            )
            return prior
        state, parent = ledger._snapshot(db), read_parent_permit(db, ledger.config)
        require(
            parent is not None
            and parent["plan_id"] == previous["id"]
            and not state["pending_requests"]
            and not state["halt"]
            and not state["unacknowledged_unknown_requests"]
            and state["effective_hard_cap_microcny"] == 2_000_000_000,
            "quiescent original wallet; acknowledged UNKNOWN holds stay retained",
        )
        counters = dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
        quotas = [dict(r) for r in db.execute("SELECT * FROM v10_quotas ORDER BY category")]
        require(
            all(q["requests"] <= REQUEST_LIMITS[q["category"]] for q in quotas), "quotas exceeded"
        )
        roster = {
            r["slot_id"]: r["task_id"]
            for r in db.execute(
                "SELECT slot_id,task_id FROM v10_episode_roster WHERE kind='generation'"
            )
        }
        require(
            all(roster.get(sid) == job["task_id"] for job in jobs for sid in job["slot_ids"]),
            "packages must belong to original generation roster",
        )
        require(
            not db.execute(
                "SELECT 1 FROM requests WHERE "
                "json_extract(coordinates_json,'$.episode_id') LIKE 'v17%' LIMIT 1"
            ).fetchone(),
            "three-task namespace must not be used before registration",
        )
        record = bound(
            dict(
                schema="v17_three_adjudication_permit.v1",
                run_id=ledger.run_id,
                config_sha256=digest(ledger.config),
                batch_id=BATCH_ID,
                plan_id=plan["id"],
                protocol_id=plan["protocol_identity"],
                source_plan_id=previous["id"],
                predecessor_registration=plan["predecessor_registration"],
                parent_v16_permit_id=parent["id"],
                fixed_unresolved_task_ids=plan["fixed_unresolved_task_ids"],
                effective_request_limits=REQUEST_LIMITS,
                job_count=3,
                roster_sha256=digest(jobs),
                authorization=authorization,
                backup=_backup(Path(ledger.path).resolve(), backup_path),
                preserved_counters=counters,
                preserved_quota_rows=quotas,
                money_limits_unchanged=True,
                request_limits_unchanged=True,
                old_new_reservations_authorized=False,
                no_retry=True,
                registered_at_unix=time.time(),
            )
        )
        db.execute(
            "CREATE TABLE v17_review_roster (episode_id TEXT PRIMARY KEY,job_json TEXT NOT NULL)"
        )
        db.executemany(
            "INSERT INTO v17_review_roster VALUES (?,?)",
            [(j["episode_id"], _json(j)) for j in jobs],
        )
        db.execute("INSERT INTO metadata VALUES (?,?)", (KEY, _json(record)))
        ledger._event(db, KEY, ACTION, record)
        require(
            dict(db.execute("SELECT * FROM counters WHERE singleton=1").fetchone()) == counters
            and [dict(r) for r in db.execute("SELECT * FROM v10_quotas ORDER BY category")]
            == quotas,
            "permit append cannot rewrite counters, settled rows or holds",
        )
        require(read_matrix_permit(db, ledger.config) == record, "new permit failed replay")
        return record


def eligible(connection, config, coordinates, output_limit, *, request_body=None):
    permit = read_matrix_permit(connection, config)
    require(permit is not None, "three-task matrix not registered", BudgetUnavailable)
    row = connection.execute(
        "SELECT job_json FROM v17_review_roster WHERE episode_id=?", (coordinates["episode_id"],)
    ).fetchone()
    require(row is not None, "outside fixed three-task matrix", BudgetUnavailable)
    job = json.loads(row[0])
    require(
        coordinates["attempt_index"] == 1
        and coordinates["turn_index"] == 0
        and output_limit == job["max_output_tokens"]
        and job["episode_id"] == mapping_episode_id(permit["protocol_id"], job["task_id"]),
        "no retry, changed task or changed output cap",
        BudgetUnavailable,
    )
    if request_body is not None:
        require(
            hashlib.sha256(request_body).hexdigest() == job["request_body_sha256"]
            and digest(json.loads(request_body)) == job["request_sha256"],
            "registered three-task request bytes changed",
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
            "only exact confirmed-unsent reservation may dispatch",
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
