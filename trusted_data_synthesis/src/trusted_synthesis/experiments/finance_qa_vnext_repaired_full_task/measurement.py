"""Actual progression and per-Observation outcomes; never substitute for qualification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_model_execution.models import read_json, record, require
from ..finance_qa_vnext_model_execution.transport import SYSTEM_PROMPT


def progress(session: dict[str, Any] | None, qualification: dict[str, Any]) -> dict[str, Any]:
    if session is None or not qualification["evidence_complete"]:
        return record(
            "repaired_progress",
            evidence_measured=False,
            observations=[],
            first_executed_action=None,
            first_accepted_claim=None,
            first_claim_consumption=None,
            complete_success=qualification["end_to_end_success"],
            first_blocking_evidence={"qualification_reason": qualification["reason"]},
        )
    observations: dict[str, dict[str, Any]] = {}
    creators: dict[str, dict[str, Any]] = {}
    first_action = first_claim = first_consumption = first_failure = None
    for event in session["events"]:
        parsed, receipt, sequence = event["parsed"], event["receipt"], event["sequence"]
        marker = {
            "sequence": sequence,
            "submission_id": event["submission"]["id"],
            "receipt_id": receipt["id"],
        }
        if not receipt["admitted"] and first_failure is None:
            first_failure = {
                **marker,
                "kind": "unadmitted_submission",
                "error_code": receipt["error_code"],
                "public_update_contract_present": event["request"].get("public_update_contract")
                == public_update_contract(),
            }
        observation = event.get("observation")
        if observation is not None:
            require(
                receipt["admitted"] and event.get("execution") is not None, "six.actual_observation"
            )
            first_action = first_action or {
                **marker,
                "operation": observation["selected_action"]["operation"],
                "observation_id": observation["id"],
            }
            observations[observation["id"]] = {
                "observation_id": observation["id"],
                "created_sequence": sequence,
                "operation": observation["selected_action"]["operation"],
                "obligation_id": observation["obligation_id"],
                "pending_model_submission_count": 0,
                "first_pending_submission_admitted": None,
                "first_typed_update_admitted": None,
                "first_typed_update_sequence": None,
                "first_rejection": None,
                "eventual_disposition": None,
                "committed_claim_id": None,
                "later_consumers": [],
            }
        pending = event["request"]["state"]["pending_observation"]
        if pending is not None:
            row = observations[pending["id"]]
            row["pending_model_submission_count"] += 1
            if row["first_pending_submission_admitted"] is None:
                row["first_pending_submission_admitted"] = receipt["admitted"]
            if parsed and parsed["kind"] == "update" and row["first_typed_update_sequence"] is None:
                row["first_typed_update_sequence"] = sequence
                row["first_typed_update_admitted"] = receipt["admitted"]
            if not receipt["admitted"] and row["first_rejection"] is None:
                row["first_rejection"] = {**marker, "error_code": receipt["error_code"]}
            if receipt["admitted"] and parsed and parsed["kind"] == "update":
                row["eventual_disposition"] = parsed["disposition"]
        claim = event.get("claim")
        if claim is not None:
            row = observations[claim["observation_id"]]
            row["committed_claim_id"] = claim["id"]
            creators[claim["id"]] = row
            first_claim = first_claim or {
                **marker,
                "claim_id": claim["id"],
                "observation_id": claim["observation_id"],
            }
        consumed = []
        if receipt["admitted"] and parsed:
            if parsed["kind"] == "action" and event.get("execution") is not None:
                consumed = [ref["ref_id"] for ref in parsed["inputs"] if ref["kind"] == "claim"]
            elif parsed["kind"] == "final" and qualification["qa_valid"] is True:
                consumed = [parsed["answer_claim_id"]]
        for claim_id in consumed:
            require(
                claim_id in creators and creators[claim_id]["created_sequence"] < sequence,
                "six.real_later_claim_parent",
            )
            consumer = {**marker, "kind": parsed["kind"], "claim_id": claim_id}
            creators[claim_id]["later_consumers"].append(consumer)
            if first_claim is not None and claim_id == first_claim["claim_id"]:
                first_consumption = first_consumption or consumer
    if first_failure is None and qualification["end_to_end_success"] is not True:
        first_failure = {
            "kind": "termination",
            "qualification_reason": qualification["reason"],
            "callback_stop": session.get("callback_stop"),
            "terminal_state_id": session["terminal_state"]["id"],
        }
    return record(
        "repaired_progress",
        evidence_measured=True,
        first_executed_action=first_action,
        first_accepted_claim=first_claim,
        first_claim_consumption=first_consumption,
        complete_success=qualification["end_to_end_success"],
        first_blocking_evidence=first_failure,
        first_blocking_event_may_later_be_corrected=True,
        observation_count=len(observations),
        observations=list(observations.values()),
        first_update_definition=(
            "first schema-parsed Update; malformed submissions count separately "
            "in all pending submissions"
        ),
        qa_valid=qualification["qa_valid"],
        qualified=qualification["qualified"],
        depth_scope=qualification["depth_scope"],
    )


def request_presentation(
    directory: Path, frozen_initial: dict[str, Any], qualification: dict[str, Any]
) -> dict[str, Any]:
    rows = []
    if qualification["evidence_complete"] and qualification["transport_ledger_id"] is not None:
        ledger = read_json((directory / "ledger.json").read_bytes())
        for attempt in ledger["attempts"]:
            public = read_json((directory / attempt["paths"]["public_request"]).read_bytes())
            http = read_json((directory / attempt["paths"]["http_request"]).read_bytes())
            body = read_json(http["body_json"].encode("utf-8"))
            request = read_json(body["messages"][1]["content"].encode("utf-8"))
            require(
                canonical_json_bytes(request) == canonical_json_bytes(public),
                "six.actual_http_public_request",
            )
            first = attempt["attempt_index"] == 0
            if first:
                require(
                    canonical_json_bytes(public) == canonical_json_bytes(frozen_initial),
                    "six.actual_initial_state",
                )
            rows.append(
                {
                    "attempt_index": attempt["attempt_index"],
                    "request_id": public["id"],
                    "phase": public["state"]["phase"],
                    "is_frozen_initial": first,
                    "neutral_full_task_system": body["messages"][0]["content"] == SYSTEM_PROMPT,
                    "public_update_contract_present": request.get("public_update_contract")
                    == public_update_contract(),
                }
            )
    return record(
        "repaired_actual_request_presentation",
        qualification_id=qualification["id"],
        rows=rows,
        verified_actual_http_requests=len(rows),
        all_full_task_publication=all(
            r["neutral_full_task_system"] and r["public_update_contract_present"] for r in rows
        )
        if rows
        else None,
        provider_calls=0,
    )
