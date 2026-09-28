"""Read-only prospective full-cohort prerequisite; NOT a runnable experiment.

R6 failed its bounded technical gate. No R7 registration, dispatch, budget access,
implicit continuation or training entry point is provided here.
"""

from __future__ import annotations

from pathlib import Path

from .contracts import digest
from .storage import read_json

SLOT_COUNT, ALIGNMENT_COUNT, MAXIMUM_CALLS = 96, 12, 108


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _identity(value):
    _require(
        value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
        "original trial identity changed",
    )


def prospective_scope():
    return dict(
        task_count=6,
        slots_per_task=8,
        isolated_reviewers=2,
        slot_denominator=SLOT_COUNT,
        alignment_denominator=ALIGNMENT_COUNT,
        maximum_calls=MAXIMUM_CALLS,
        slot_required_passes=92,
        alignment_required_passes=12,
        all_108_would_be_fresh=True,
        no_earlier_success_or_output_reuse=True,
        own_side_eight_only_alignment=True,
        no_positive_yield_gate=True,
        registered=False,
        runnable=False,
        automatic_expansion=False,
        actual_model_calls=0,
        actual_training=False,
    )


def prerequisite(parent):
    """Fail closed before any registration; inspect only existing R6 artifacts."""
    parent = Path(parent)
    plan = read_json(parent / "registration/protocol.json")
    outcome = read_json(parent / "result/record.json")
    _identity(plan)
    _identity(outcome)
    _require(
        outcome["protocol_id"] == plan["id"]
        and outcome["technical_trial_admitted"] is True
        and outcome["returned"] == outcome["interface_passed"] == outcome["denominator"] == 12
        and not outcome["length_count"]
        and not outcome["errors"],
        "R6 fixed twelve-call technical prerequisite is not admitted; R7 remains unregistered",
    )
    _require(len(plan["jobs"]) == plan["maximum_calls"] == 12, "original R6 denominator changed")
    observed = {}
    for job in plan["jobs"]:
        directory = parent / "jobs" / digest(job["key"])
        response = read_json(directory / "response/record.json")
        assessment = read_json(directory / "assessment/record.json")
        _require(
            digest(response) == outcome["actual_response_hashes"][job["key"]]
            and assessment["interface_admitted"] is True
            and response["finish_reason"] == "tool_calls"
            and not response.get("review_format_error"),
            "prerequisite does not match original R6 evidence",
        )
        observed[job["key"]] = digest(response)
    _require(set(observed) == set(outcome["actual_response_hashes"]), "R6 returns were selected")
    return dict(
        prerequisite_satisfied=True,
        parent_protocol_id=plan["id"],
        parent_result_id=outcome["id"],
        original_response_hashes=observed,
        prospective_scope=prospective_scope(),
        registration_authorized_by_this_helper=False,
    )
