"""Finite same-matrix recovery: reuse originals, never resend an existing call.

No budget writes or HTTP. RESERVED / DISPATCHED / UNKNOWN rows block this finite
recovery rather than being relabelled unsent. A durable SETTLED model response
may be reconstructed from its exact ledger bytes, without a replacement model.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from .calibration import now, publish
from .contracts import digest, invocation_identity
from .storage import read_json
from .v6_collection import bound, require
from .v6_decomposed_review import job_directory
from .v6_review_provider import _request_body, _strict_review_payload


def coordinates(plan, job):
    episode_id = "v8prod:" + digest(dict(protocol_id=plan["id"], job_key=job["key"]))
    return invocation_identity(
        dict(run_id=plan["budget_config"]["run_id"], episode_id=episode_id, attempt_index=1),
        turn_index=0,
    )


def production_rows(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        return {
            row["invocation_id"]: dict(row)
            for row in db.execute(
                "SELECT r.invocation_id,r.state,r.request_sha256,r.response_sha256,"
                "r.response_classification,r.dispatched_at,r.usage_json,r.settled_microcny "
                "FROM requests r JOIN v8_request_allocations a USING(invocation_id) "
                "WHERE a.category='production_review'"
            )
        }


def restore_settled_artifact(ledger, iid, request):
    """Replay only transport-envelope extraction from a durable original row."""
    row = ledger.request_record(iid)
    require(
        row is not None
        and row["state"] == "SETTLED"
        and row["dispatched_at"] is not None
        and row["response_classification"] == "model_response",
        "only settled original model bytes can be reconstructed",
    )
    body, _ = _request_body(ledger, request)
    original_request = bytes(row["request_body"])
    raw = bytes(row["response_body"])
    require(
        json.loads(original_request) == body
        and digest(body) == row["request_sha256"]
        and hashlib.sha256(raw).hexdigest() == row["response_sha256"],
        "original paid request/response bytes differ",
    )
    evidence = json.loads(row["evidence_json"])
    require(
        evidence["semantic_review_request_sha256"] == digest(request), "review metadata differs"
    )
    value = json.loads(raw)
    require(len(value["choices"]) == 1, "original response envelope missing")
    choice = value["choices"][0]
    finish, message = choice["finish_reason"], choice["message"]
    require(
        finish in {"stop", "length", "content_filter", "tool_calls"}, "not a normal original return"
    )
    usage = ledger.price_sheet.usage(value["usage"], output_limit=body["max_tokens"])
    stored_usage = json.loads(row["usage_json"])
    require(all(usage[k] == stored_usage[k] for k in usage), "actual stored usage differs")
    require(
        ledger.price_sheet.cost_microcny(
            hit=usage["prompt_cache_hit_tokens"],
            miss=usage["prompt_cache_miss_tokens"],
            output=usage["completion_tokens"],
        )
        == row["settled_microcny"],
        "stored tariff differs",
    )
    bindings = {
        k: evidence[k]
        for k in (
            "reviewer",
            "task_bundle_sha256",
            "rubric_sha256",
            "review_request_metadata_sha256",
            "semantic_review_request_sha256",
            "wire_protocol",
            "endpoint",
            "strict_tool_sha256",
        )
    }
    return dict(
        budget_invocation_id=iid,
        budget_coordinates=json.loads(row["coordinates_json"]),
        public_request=body,
        request_sha256=digest(body),
        public_request_body_sha256=hashlib.sha256(original_request).hexdigest(),
        api_response_raw=raw.decode(),
        raw_api_response_sha256=row["response_sha256"],
        api_response=value,
        usage=value["usage"],
        peak_tariff_upper_bound_microcny=row["settled_microcny"],
        budget_reserved_microcny=row["reserved_microcny"],
        price_sheet_id=ledger.price_sheet.id,
        content=message.get("content"),
        finish_reason=finish,
        actual_model_calls=1,
        retries=0,
        content_repair_performed=False,
        **_strict_review_payload(message, finish),
        **bindings,
        recovered_from_exact_original_ledger_bytes=True,
        new_model_calls_during_recovery=0,
    )


def inspect_recovery(output, plan, ledger, context, *, repair_local=False):
    """Called while holding the original controller lock, not concurrently with it."""
    from .v9_network_terminal import TERMINAL_KIND, revision_for, validate_terminal
    from .v9_production_review import _assessment

    rows = production_rows(plan["budget_database"])
    expected = {coordinates(plan, j)["invocation_id"]: j for j in plan["jobs"]}
    require(not set(rows) - set(expected), "foreign production calls cannot be spliced")
    completed, unsent, issues, actions = {}, [], [], []
    totals = dict(cost_microcny=0, prompt_tokens=0, completion_tokens=0)
    for iid, job in expected.items():
        directory = job_directory(output, job)
        response, assessment = (
            directory / "response/record.json",
            directory / "assessment/record.json",
        )
        row = rows.get(iid)
        if row is None:
            if response.exists() or assessment.exists():
                issues.append(
                    dict(job_key=job["key"], reason="saved_return_without_original_ledger_row")
                )
            else:
                unsent.append(job["key"])
            continue
        if row["state"] == "UNKNOWN" and response.exists():
            artifact = read_json(response)
            if artifact.get("terminal_kind") == TERMINAL_KIND:
                revision = revision_for(output, plan)
                require(revision is not None, "terminal recovery needs explicit revised closure")
                validate_terminal(
                    artifact,
                    protocol_id=plan["id"],
                    semantic_request_sha256=digest(context.request(job)),
                    revision=revision,
                )
                require(
                    row["request_sha256"] == artifact["request_sha256"]
                    and row["dispatched_at"] is not None,
                    "network terminal original request changed",
                )
                judged = read_json(assessment)
                require(
                    judged["validation"] is None and judged["interface_admitted"] is False,
                    "missing model response is never positive",
                )
                completed[job["key"]] = dict(
                    stage=job["stage"], interface=False, semantic=False, returned=False
                )
                continue
        if (
            row["state"] != "SETTLED"
            or row["dispatched_at"] is None
            or row["response_classification"] != "model_response"
        ):
            issues.append(
                dict(
                    job_key=job["key"],
                    reason="existing_call_requires_separate_manual_audit_not_resend",
                    ledger_state=row["state"],
                    has_dispatch_marker=row["dispatched_at"] is not None,
                )
            )
            continue
        request = context.request(job)
        if not response.exists():
            if not repair_local:
                issues.append(
                    dict(
                        job_key=job["key"],
                        reason="settled_original_bytes_need_local_reconstruction",
                    )
                )
                continue
            artifact = restore_settled_artifact(ledger, iid, request)
            publish(response.parent, artifact)
            actions.append(
                dict(job_key=job["key"], action="restore_original_ledger_response", new_calls=0)
            )
        artifact = read_json(response)
        require(
            artifact["budget_invocation_id"] == iid
            and artifact["semantic_review_request_sha256"] == digest(request)
            and artifact["request_sha256"] == row["request_sha256"]
            and artifact["raw_api_response_sha256"] == row["response_sha256"]
            and hashlib.sha256(artifact["api_response_raw"].encode()).hexdigest()
            == row["response_sha256"]
            and artifact["peak_tariff_upper_bound_microcny"] == row["settled_microcny"],
            "saved response no longer matches the one paid original",
        )
        if not assessment.exists():
            if not repair_local:
                issues.append(
                    dict(job_key=job["key"], reason="saved_original_needs_frozen_local_assessment")
                )
                continue
            publish(assessment.parent, _assessment(artifact, request, job))
            actions.append(
                dict(job_key=job["key"], action="apply_original_frozen_checker", new_calls=0)
            )
        judged = read_json(assessment)
        validation = judged.get("validation")
        if validation:
            key = "review_request_sha256" if job["stage"] == "slot" else "alignment_request_sha256"
            require(validation[key] == digest(request), "saved assessment request changed")
            require(
                validation["raw_review_sha256"]
                == hashlib.sha256(artifact["review_text"].encode()).hexdigest(),
                "saved assessment original text changed",
            )
        completed[job["key"]] = dict(
            stage=job["stage"],
            returned=True,
            interface=judged["interface_admitted"],
            semantic=judged["semantic_consistent"],
        )
        totals["cost_microcny"] += row["settled_microcny"]
        totals["prompt_tokens"] += artifact["usage"]["prompt_tokens"]
        totals["completion_tokens"] += artifact["usage"]["completion_tokens"]
    budget = ledger.snapshot()
    if budget["halt"] or budget["unacknowledged_unknown_requests"] or budget["pending_requests"]:
        issues.append(dict(reason="unresolved_shared_wallet_or_pending_calls"))
    report = bound(
        dict(
            schema="v9_same_matrix_recovery_audit.v1",
            at=now(),
            protocol_id=plan["id"],
            expected_jobs=len(expected),
            reused_returned_jobs=[
                key for key, value in completed.items() if value.get("returned", True)
            ],
            reused_terminal_jobs=list(completed),
            confirmed_unsent_jobs=unsent,
            blocker_records=issues,
            local_actions=actions,
            original_ledger_states=dict(Counter(r["state"] for r in rows.values())),
            new_model_calls=0,
            ledger_modified=False,
            same_namespace=True,
            resume_admitted=not issues,
            budget=budget,
            reserved_dispatched_unknown_never_assumed_unsent=True,
        )
    )
    return report, completed, totals
