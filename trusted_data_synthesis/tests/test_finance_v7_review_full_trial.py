"""Read-only parent-gate controls; no full trial is registered or runnable."""

import hashlib

import pytest

from trusted_synthesis.finance_research import v7_review_full_trial as future
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import encode


def bound(value):
    return value | {"id": digest(value)}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))


def fixtures(tmp_path, passed):
    jobs = [dict(key=f"slot:{i}") for i in range(12)]
    plan = bound(dict(jobs=jobs, maximum_calls=12))
    hashes = {}
    if passed:
        for job in jobs:
            response = dict(
                finish_reason="tool_calls",
                review_format_error=None,
                synthetic_coordinate=job["key"],
            )
            hashes[job["key"]] = digest(response)
            directory = tmp_path / "jobs" / digest(job["key"])
            write(directory / "response/record.json", response)
            write(directory / "assessment/record.json", dict(interface_admitted=True))
    outcome = bound(
        dict(
            protocol_id=plan["id"],
            technical_trial_admitted=passed,
            returned=12,
            interface_passed=12 if passed else 8,
            denominator=12,
            length_count=0,
            errors=[],
            actual_response_hashes=hashes,
        )
    )
    write(tmp_path / "registration/protocol.json", plan)
    write(tmp_path / "result/record.json", outcome)


def test_failed_r6_blocks_before_registration_or_any_side_effect(tmp_path):
    fixtures(tmp_path, False)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.json")}
    with pytest.raises(ValueError, match="not admitted; R7 remains unregistered"):
        future.prerequisite(tmp_path)
    assert before == {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.json")
    }
    assert not hasattr(future, "register") and not hasattr(future, "run")
    assert not hasattr(future, "request_review") and not hasattr(future, "ledger_for")


def test_readiness_still_grants_no_registration_when_synthetic_parent_passes(tmp_path):
    fixtures(tmp_path, True)
    result = future.prerequisite(tmp_path)
    assert result["prerequisite_satisfied"]
    assert not result["registration_authorized_by_this_helper"]
    assert (
        not result["prospective_scope"]["registered"]
        and not result["prospective_scope"]["runnable"]
    )


def test_scope_is_exact_fresh_96_plus12_and_not_a_training_or_success_splicing_path():
    scope = future.prospective_scope()
    assert scope["task_count"] * scope["slots_per_task"] * scope["isolated_reviewers"] == 96
    assert (
        scope["slot_denominator"] + scope["alignment_denominator"] == scope["maximum_calls"] == 108
    )
    assert scope["slot_required_passes"] == 92 and scope["alignment_required_passes"] == 12
    assert scope["all_108_would_be_fresh"] and scope["no_earlier_success_or_output_reuse"]
    assert scope["own_side_eight_only_alignment"] and not scope["automatic_expansion"]
    assert scope["actual_model_calls"] == 0 and not scope["actual_training"]
