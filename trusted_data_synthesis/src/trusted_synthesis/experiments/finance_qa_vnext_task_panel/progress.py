"""Observe admitted actions across Program and Share without changing their schemas.

Program Claim references carry selectors; Share Claim references need not.  These
diagnostics retain the exact input reference plus a presence bit, so absence is
not confused with an explicit null or filled with an invented selector.  The
unchanged qualifier remains the authority for validity and actual graph depth.
"""

from __future__ import annotations

from typing import Any

from ..finance_qa_vnext_model_execution.models import record, require
from ..finance_qa_vnext_repaired_full_task.measurement import progress as observation_progress


def progress(session: dict[str, Any] | None, qualification: dict[str, Any]) -> dict[str, Any]:
    base = observation_progress(session, qualification)
    candidates, nontransparent, consumptions, merges, absolute = [], [], [], [], []
    first_lookup = None
    if base["evidence_measured"]:
        assert session is not None
        producers = {
            event["observation"]["id"]: event["observation"]["selected_action"]
            for event in session["events"]
            if event.get("observation")
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
            offered = {action["id"] for action in event["request"]["available_actions"]}
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
                claim["id"]: claim
                for claim in event["request"]["state"]["accepted_claims"]
                if claim["status"] == "accepted"
            }
            dependencies = []
            for ref in value["inputs"]:
                if ref["kind"] != "claim":
                    continue
                require(ref["ref_id"] in accepted, "task_panel_progress.actual_accepted_input")
                claim = accepted[ref["ref_id"]]
                producer = producers[claim["observation_id"]]
                dependencies.append(
                    {
                        "claim_id": claim["id"],
                        "role": ref["role"],
                        "selector": ref.get("selector"),
                        "selector_present": "selector" in ref,
                        "input_reference": ref,
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
                "input_references": value["inputs"],
                "ordered_claim_dependencies": dependencies,
            }
            if value["operation"] != "lookup":
                nontransparent.append(action)
            if dependencies:
                consumptions.append(action)
            if value["operation"] == "signed_percentage_point_gap":
                require(
                    [item["role"] for item in dependencies] == ["income_growth", "revenue_growth"]
                    and all(item["producer_operation"] == "growth" for item in dependencies),
                    "task_panel_progress.actual_growth_merge_roles",
                )
                merges.append(action)
            if value["operation"] == "absolute_percentage_point_gap":
                require(
                    len(dependencies) == 1
                    and dependencies[0]["producer_operation"] == "signed_percentage_point_gap",
                    "task_panel_progress.actual_absolute_parent",
                )
                absolute.append(action)
    return record(
        "task_panel_progress",
        **{key: value for key, value in base.items() if key not in {"id", "schema_version"}},
        qualification_id=qualification["id"],
        depth_metrics=qualification.get("depth_metrics"),
        depth_authority="unchanged independent qualification; not action or callback counts",
        candidate_set_rows=candidates,
        first_full_candidate_action_admitted=next(
            (row for row in candidates if row["admitted"] and row["full_set_and_unique"]), None
        ),
        first_lookup_claim_accepted=first_lookup,
        first_nontransparent_operation=nontransparent[0] if nontransparent else None,
        nontransparent_operations=nontransparent,
        actual_claim_consumptions=consumptions,
        first_branch_merge=merges[0] if merges else None,
        first_absolute_operation=absolute[0] if absolute else None,
        raw_input_reference_fields_preserved=True,
        absent_selector_is_not_an_invented_selector=True,
        all_candidate_sets_valid_does_not_imply_task_success=True,
        provider_calls=0,
        financial_operation_executions=0,
    )
