"""Actual candidate acceptance, Claim consumption and branch completion, not textual depth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract

from ..finance_qa_vnext_model_execution.models import read_json, record, require
from ..finance_qa_vnext_repaired_full_task.measurement import progress as observation_progress
from ..finance_qa_vnext_repaired_full_task.measurement import (
    request_presentation as update_presentation,
)


def progress(session: dict[str, Any] | None, qualification: dict[str, Any]) -> dict[str, Any]:
    base = observation_progress(session, qualification)
    candidates, nontransparent, consumptions, merges, absolute = [], [], [], [], []
    first_lookup = None
    if base["evidence_measured"]:
        assert session is not None
        producers = {
            e["observation"]["id"]: e["observation"]["selected_action"]
            for e in session["events"]
            if e.get("observation")
        }
        for event in session["events"]:
            value, receipt = event["parsed"], event["receipt"]
            marker = {
                "sequence": event["sequence"],
                "submission_id": event["submission"]["id"],
                "receipt_id": receipt["id"],
                "request_id": event["request"]["id"],
            }
            if event.get("claim") and event["claim"]["proposition"]["operation"] == "lookup":
                first_lookup = first_lookup or {**marker, "claim_id": event["claim"]["id"]}
            if not value or value["kind"] != "action":
                continue
            offered = {a["id"] for a in event["request"]["available_actions"]}
            declared = value["decision"]["candidate_action_ids"]
            candidates.append(
                {
                    **marker,
                    "available_count": len(offered),
                    "declared_count": len(declared),
                    "full_set_and_unique": set(declared) == offered
                    and len(declared) == len(set(declared)),
                    "selected_current": value["decision"]["selected_action_id"] in offered,
                    "admitted": receipt["admitted"],
                    "error_code": receipt["error_code"],
                }
            )
            if not receipt["admitted"] or event.get("execution") is None:
                continue
            accepted = {
                c["id"]: c
                for c in event["request"]["state"]["accepted_claims"]
                if c["status"] == "accepted"
            }
            dependencies = []
            for ref in value["inputs"]:
                if ref["kind"] != "claim":
                    continue
                require(ref["ref_id"] in accepted, "branch_measurement.actual_accepted_input")
                claim = accepted[ref["ref_id"]]
                producer = producers[claim["observation_id"]]
                dependencies.append(
                    {
                        "claim_id": claim["id"],
                        "role": ref["role"],
                        "selector": ref["selector"],
                        "producer_operation": producer["operation"],
                        "producer_obligation": producer["obligation_id"],
                        "observation_id": claim["observation_id"],
                    }
                )
            action = {
                **marker,
                "operation": value["operation"],
                "selected_action_id": value["decision"]["selected_action_id"],
                "obligation_id": value["decision"]["obligation_id"],
                "ordered_claim_dependencies": dependencies,
            }
            if value["operation"] != "lookup":
                nontransparent.append(action)
            if dependencies:
                consumptions.append(action)
            if value["operation"] == "signed_percentage_point_gap":
                require(
                    [d["role"] for d in dependencies] == ["income_growth", "revenue_growth"]
                    and all(d["producer_operation"] == "growth" for d in dependencies),
                    "branch_measurement.actual_growth_merge_roles",
                )
                merges.append(action)
            if value["operation"] == "absolute_percentage_point_gap":
                require(
                    len(dependencies) == 1
                    and dependencies[0]["producer_operation"] == "signed_percentage_point_gap",
                    "branch_measurement.actual_absolute_parent",
                )
                absolute.append(action)
    return record(
        "action_branch_progress",
        **{k: v for k, v in base.items() if k not in {"id", "schema_version"}},
        candidate_set_rows=candidates,
        first_full_candidate_action_admitted=next(
            (r for r in candidates if r["admitted"] and r["full_set_and_unique"]), None
        ),
        first_lookup_claim_accepted=first_lookup,
        first_nontransparent_operation=nontransparent[0] if nontransparent else None,
        nontransparent_operations=nontransparent,
        actual_claim_consumptions=consumptions,
        first_branch_merge=merges[0] if merges else None,
        first_absolute_operation=absolute[0] if absolute else None,
        all_candidate_sets_valid_does_not_imply_task_success=True,
    )


def request_presentation(
    directory: Path, frozen_initial: dict[str, Any], qualification: dict[str, Any]
) -> dict[str, Any]:
    base = update_presentation(directory, frozen_initial, qualification)
    rows = base["rows"]
    if rows:
        ledger = read_json((directory / "ledger.json").read_bytes())
        require(len(ledger["attempts"]) == len(rows), "branch_measurement.http_row_count")
        for row, attempt in zip(rows, ledger["attempts"], strict=True):
            http = read_json((directory / attempt["paths"]["http_request"]).read_bytes())
            body = read_json(http["body_json"].encode())
            request = read_json(body["messages"][1]["content"].encode())
            row["public_action_contract_present"] = (
                request.get("public_action_contract") == public_action_contract()
            )
    return record(
        "action_branch_actual_request_presentation",
        qualification_id=qualification["id"],
        rows=rows,
        verified_actual_http_requests=len(rows),
        all_full_task_publication=all(
            r["neutral_full_task_system"]
            and r["public_update_contract_present"]
            and r["public_action_contract_present"]
            for r in rows
        )
        if rows
        else None,
        provider_calls=0,
    )
