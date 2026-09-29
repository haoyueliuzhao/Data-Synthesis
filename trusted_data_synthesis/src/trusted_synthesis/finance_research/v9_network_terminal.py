"""Explicitly authorized network-unknown terminals, never fabricated responses.

The original matrix/protocol/request IDs remain unchanged. This separate
execution revision changes closure accounting only, preserving every hold and
making absent replies ineligible under the SAME V8 semantic rules.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .calibration import ROOT, now, publish
from .contracts import digest
from .storage import read_json, runtime_binding
from .v6_collection import bound, persist, require, sha
from .v6_review_provider import _request_body
from .v9_review_recovery import coordinates, production_rows

TERMINAL_KIND = "acknowledged_connection_unknown_no_model_response"
REVISION_DIR = "network_terminal_revision_01"
AUTH_DIR = "network_terminal_authorization_01"
PROTECTED = (
    "v8_review_policy.py",
    "v8_single_target_review.py",
    "semantic_review.py",
    "v6_state_alignment.py",
    "v6_encoding.py",
    "v6_task.py",
    "v6_review_provider.py",
    "v6_decomposed_review.py",
    "v9_review_preflight.py",
    "harness.py",
    "profiles.py",
)


def checked(value):
    require(
        value["id"] == digest({k: v for k, v in value.items() if k != "id"}), "bound record changed"
    )
    return value


def validate_authorization(auth, protocol_id):
    checked(auth)
    require(
        auth["schema"] == "v9_network_unknown_terminal_authorization.v1"
        and auth["user_reply"] == "允许上述有限修订并继续同一矩阵"
        and auth["protocol_id"] == protocol_id
        and auth["hard_cap_microcny"] == 1200000000
        and all(
            auth.get(k) is True
            for k in (
                "risk_acknowledged",
                "no_resend",
                "permanent_full_hold",
                "scope_all_same_matrix_connection_interruptions",
                "unknown_never_positive",
                "no_prefix_training",
                "same_matrix_and_namespace",
            )
        ),
        "explicit bounded same-matrix network-terminal authority required",
    )


def register_revision(output):
    output = Path(output)
    plan = checked(read_json(output / "registration/protocol.json"))
    auth_path = output / AUTH_DIR / "record.json"
    auth = checked(read_json(auth_path))
    validate_authorization(auth, plan["id"])
    current = runtime_binding()
    require(
        all(current[name] == plan["runtime_binding"][name] for name in PROTECTED),
        "frozen V8 semantics or actual requests changed",
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "freeze source before explicit execution revision",
        )
    record = bound(
        dict(
            schema="v9_same_matrix_network_terminal_revision.v1",
            at=now(),
            protocol_id=plan["id"],
            original_source_commit=plan["source_commit"],
            source_commit=commit,
            original_runtime_binding_sha256=digest(plan["runtime_binding"]),
            runtime_binding=current,
            authorization=dict(path=str(auth_path), sha256=sha(auth_path), id=auth["id"]),
            authorization_record=auth,
            protected_sources={n: current[n] for n in PROTECTED},
            jobs_sha256=digest(plan["jobs"]),
            model="deepseek-flash",
            maximum_registered_jobs=13022,
            completion_schema="v9_production_completion_seal.v2",
            complete_means="all13022 authentic terminal records, not all13022 returned responses",
            unknown_is_never_material=True,
            same_namespace_and_job_ids=True,
            original_protocol_bytes_unchanged=True,
            original_stopped_result_preserved=True,
            automatic_new_generation=False,
            automatic_new_technical_trial=False,
        )
    )
    publish(output / REVISION_DIR, record)
    return record


def revision_for(output, plan):
    path = Path(output) / REVISION_DIR / "record.json"
    if not path.exists():
        return None
    revision = checked(read_json(path))
    require(
        revision["schema"] == "v9_same_matrix_network_terminal_revision.v1"
        and revision["protocol_id"] == plan["id"]
        and revision["original_runtime_binding_sha256"] == digest(plan["runtime_binding"])
        and revision["runtime_binding"] == runtime_binding()
        and revision["jobs_sha256"] == digest(plan["jobs"])
        and all(revision["protected_sources"][n] == plan["runtime_binding"][n] for n in PROTECTED),
        "execution revision must retain original matrix and V8 semantics",
    )
    item = revision["authorization"]
    require(sha(item["path"]) == item["sha256"], "network authority bytes changed")
    require(
        read_json(item["path"]) == revision["authorization_record"], "network authority changed"
    )
    validate_authorization(revision["authorization_record"], plan["id"])
    return revision


def validate_terminal(artifact, *, protocol_id, semantic_request_sha256, revision):
    checked(revision)
    require(
        revision["protocol_id"] == protocol_id, "terminal belongs to a different execution revision"
    )
    auth = revision["authorization_record"]
    validate_authorization(auth, protocol_id)
    ack = checked(artifact["unknown_acknowledgement"])
    require(
        artifact.get("terminal_kind") == TERMINAL_KIND
        and artifact["protocol_id"] == protocol_id
        and artifact["semantic_review_request_sha256"] == semantic_request_sha256
        and artifact["network_authorization_id"] == auth["id"]
        and artifact["billing_usage_known"] is False
        and artifact["model_response_received"] is False
        and artifact["usage"] is None
        and artifact["review_text"] is None
        and artifact["api_response_raw"] is None
        and artifact["raw_api_response_sha256"] is None
        and ack["protocol_id"] == protocol_id
        and ack["network_terminal_authorization_id"] == auth["id"]
        and ack["invocation_id"] == artifact["budget_invocation_id"]
        and ack["expected_request_sha256"] == artifact["request_sha256"]
        and ack["permanent_reserved_microcny"] == artifact["budget_reserved_microcny"] > 0
        and ack["reservation_released"] is False
        and ack["actual_usage_known"] is False
        and ack["retry_authorized"] is False,
        "network terminal cannot fabricate model output, settlement or positive material",
    )


def materialize_network_terminals(output, plan, ledger, context):
    from .v9_production_review import _assessment

    output = Path(output)
    revision = revision_for(output, plan)
    require(revision is not None, "network continuation needs its separate explicit revision")
    auth = revision["authorization_record"]
    rows = production_rows(plan["budget_database"])
    jobs = {coordinates(plan, job)["invocation_id"]: job for job in plan["jobs"]}
    require(not set(rows) - set(jobs), "foreign production request cannot enter this matrix")
    expected, requests = {}, {}
    for iid, row in rows.items():
        if row["state"] != "UNKNOWN":
            continue
        job = jobs[iid]
        request = context.request(job)
        body, _ = _request_body(ledger, request)
        expected[iid] = dict(job_key=job["key"], request_sha256=digest(body))
        requests[iid] = request
    if not expected:
        return dict(new_acknowledgements=0, terminal_artifacts=0)
    receipt = ledger.acknowledge_v9_connection_unknowns(
        protocol_id=plan["id"], authorization=auth, expected_requests=expected
    )
    persist(output / "network_terminal_acknowledgements" / receipt["id"], receipt)
    from .v6_decomposed_review import job_directory

    for ack in receipt["records"]:
        iid = ack["invocation_id"]
        row = ledger.request_record(iid)
        request, job = requests[iid], jobs[iid]
        evidence = json.loads(row["evidence_json"])
        require(
            evidence["semantic_review_request_sha256"] == digest(request),
            "original network-error request differs",
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
        artifact = dict(
            terminal_kind=TERMINAL_KIND,
            protocol_id=plan["id"],
            job_key=job["key"],
            budget_invocation_id=iid,
            request_sha256=row["request_sha256"],
            budget_coordinates=json.loads(row["coordinates_json"]),
            billing_usage_known=False,
            budget_reserved_microcny=row["reserved_microcny"],
            unknown_acknowledgement=ack,
            network_authorization_id=auth["id"],
            original_network_evidence=evidence,
            model_response_received=False,
            api_response_raw=None,
            raw_api_response_sha256=None,
            usage=None,
            review_text=None,
            finish_reason=None,
            review_format_error="no_complete_response_connection_unknown",
            actual_model_calls=None,
            http_invocation_attempted=True,
            retries=0,
            actual_model_calls_unconfirmed=True,
            content_repair_performed=False,
            unknown_never_positive=True,
            **bindings,
        )
        validate_terminal(
            artifact,
            protocol_id=plan["id"],
            semantic_request_sha256=digest(request),
            revision=revision,
        )
        directory = job_directory(output, job)
        persist(directory / "response", artifact)
        persist(directory / "assessment", _assessment(artifact, request, job))
    return dict(
        new_acknowledgements=receipt["new_acknowledgements"],
        terminal_artifacts=len(receipt["records"]),
        receipt_id=receipt["id"],
    )


async def run_with_network_terminals(output, env_file, *, resume):
    """Drain each bounded failure batch; continue only explicitly authorized terminals."""
    from .v9_production_review import ProductionContext, checked_plan, ledger_for, run

    plan = checked_plan(output)
    require(revision_for(output, plan) is not None, "registered network revision required")
    attempts = 0
    while True:
        ledger = ledger_for(plan)
        materialize_network_terminals(output, plan, ledger, ProductionContext(output, plan))
        previous = ledger.snapshot()["request_partition"]["consumed"]["production_review"]
        result = await run(output, env_file, resume=resume)
        if result.get("completion_seal_id") or not result["errors"]:
            return result
        after = ledger.snapshot()
        if not after["unacknowledged_unknown_requests"]:
            return result  # Capacity/local/schema failures are not network retries.
        require(not after["pending_requests"], "in-flight calls must drain before acknowledgment")
        attempts += 1
        require(
            after["request_partition"]["consumed"]["production_review"] > previous
            and attempts <= len(plan["jobs"]),
            "no-progress or out-of-scope recovery loop",
        )
        # The next iteration must strictly prove every unknown and the exact halt.
        resume = True
