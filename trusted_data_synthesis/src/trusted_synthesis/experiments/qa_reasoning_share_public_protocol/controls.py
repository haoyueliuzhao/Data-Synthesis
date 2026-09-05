"""Direct protocol admission controls; no extra session, callback or arithmetic."""

from __future__ import annotations

import copy
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .engine import preview
from .fixture import action_payload, update_payload
from .models import record


def _operand(state: dict[str, Any], role: str, evidence_role: str) -> dict[str, str]:
    return {"role": role, "kind": "evidence", "ref_id": state["evidence"][evidence_role]["id"]}


def run_controls(
    protocol: dict[str, Any],
    source: dict[str, Any],
    legacy_contract: dict[str, Any],
    initial_state: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    if not any(e["observation"] is not None for e in events):
        return record(
            "controls",
            status="not_run_missing_actual_pending_state",
            both_initial_choices_admitted=False,
            same_initial_state_for_both=False,
            all_rejected=False,
            reject_update_admitted_without_claim=False,
            source_state_and_transcript_unchanged=True,
            generator_callbacks=0,
            kernel_calls=0,
            extra_complete_protocol_sessions=0,
        )
    original = canonical_json_bytes({"initial": initial_state, "events": events})
    initial = copy.deepcopy(initial_state)
    pending = copy.deepcopy(next(e["post_state"] for e in events if e["observation"] is not None))
    direct = action_payload(
        initial,
        "share_ratio",
        [_operand(initial, "numerator", "freight"), _operand(initial, "denominator", "total")],
        {},
    )
    rebuilt = action_payload(
        initial,
        "relation_sum",
        [
            _operand(initial, "member", "freight"),
            _operand(initial, "member", "other"),
            _operand(initial, "relation", "part_whole"),
        ],
        {"method": "sum"},
    )
    choices = []
    for request in (direct, rebuilt):
        choices.append(
            {
                "state_id": initial["id"],
                "submission": request,
                "admission": preview(
                    initial, canonical_json_bytes(request), protocol, source, legacy_contract
                ),
            }
        )
    cases = []

    def check(name: str, state: dict[str, Any], request: dict[str, Any]) -> None:
        result = preview(state, canonical_json_bytes(request), protocol, source, legacy_contract)
        cases.append(
            {
                "name": name,
                "source_state_id": state["id"],
                "submission": request,
                "rejected": not result["admitted"],
                "result": result,
            }
        )

    wrong = copy.deepcopy(rebuilt)
    wrong["parameters"] = {"method": "mean"}
    check("incorrect_parameters_not_repaired", initial, wrong)
    check(
        "action_blocked_until_generator_update",
        pending,
        action_payload(
            pending,
            "share_ratio",
            [_operand(pending, "numerator", "freight"), _operand(pending, "denominator", "total")],
            {},
        ),
    )
    wrong = copy.deepcopy(direct)
    wrong["inputs"][1] = {
        "role": "denominator",
        "kind": "claim",
        "ref_id": pending["pending_observation"]["id"],
    }
    check("observation_is_not_an_accepted_claim", initial, wrong)
    wrong = update_payload(pending, "accept")
    wrong["state_id"] = initial["id"]
    check("stale_state_update", pending, wrong)
    wrong = update_payload(pending, "accept")
    wrong["observation_id"] = "public_share_protocol_observation:" + "0" * 64
    wrong["public_basis"]["observation_refs"] = [wrong["observation_id"]]
    check("cross_observation_update", pending, wrong)
    wrong = update_payload(pending, "accept")
    wrong["proposed_claim"] = None
    check("missing_proposed_claim_not_host_filled", pending, wrong)
    wrong = update_payload(pending, "accept")
    wrong["proposed_claim"]["value"] = "21814"
    check("proposed_claim_disagrees_with_observation", pending, wrong)
    wrong = copy.deepcopy(direct)
    wrong["origin"] = "model"
    check("caller_cannot_claim_model_origin", initial, wrong)
    reject = update_payload(pending, "reject")
    reject_result = preview(
        pending, canonical_json_bytes(reject), protocol, source, legacy_contract
    )
    missing_final = {
        "kind": "final",
        "state_id": initial["id"],
        "answer_claim_id": pending["pending_observation"]["id"],
        "answer": {"value": "93.508458", "unit": "percent"},
        "citations": [],
        "public_basis": {"relation": "supports", "claim_refs": [], "evidence_refs": []},
    }
    check("final_requires_accepted_percentage_claim", initial, missing_final)
    unchanged = canonical_json_bytes({"initial": initial_state, "events": events}) == original
    return record(
        "controls",
        initial_choice_probes=choices,
        both_initial_choices_admitted=all(c["admission"]["admitted"] for c in choices),
        same_initial_state_for_both=choices[0]["state_id"] == choices[1]["state_id"],
        negative_controls=cases,
        attempted=len(cases),
        rejected=sum(c["rejected"] for c in cases),
        all_rejected=all(c["rejected"] for c in cases),
        explicit_reject_update={"submission": reject, "result": reject_result},
        reject_update_admitted_without_claim=(
            reject_result["admitted"]
            and reject_result["would_clear_pending"]
            and not reject_result["would_create_claim"]
        ),
        source_state_and_transcript_unchanged=unchanged,
        committed_control_updates=0,
        generator_callbacks=0,
        kernel_calls=0,
        extra_complete_protocol_sessions=0,
        model_result=False,
        scope="direct previews of fixed actual states; not executed alternate trajectories",
    )
