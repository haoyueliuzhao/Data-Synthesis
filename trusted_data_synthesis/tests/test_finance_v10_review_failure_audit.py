"""Only finite synthetic artifact controls; no model, original label change or wallet."""

import copy
import json

import pytest

from trusted_synthesis.finance_research import v10_review_failure_audit as audit
from trusted_synthesis.finance_research.contracts import digest


def assessment(*, interface=True, semantic=True, effective="valid", reported="valid", error=None):
    return dict(
        interface_admitted=interface,
        semantic_consistent=semantic,
        error=error,
        validation=dict(
            v_trace=effective,
            reported_v_trace=reported,
            parsed=dict(slot=dict(reason_codes=[], propositions=[], mask=[])),
        )
        if interface
        else None,
    )


def test_synthetic_regex_cases_are_not_original_model_outputs():
    rows = audit.regex_examples()
    assert [row["classification"] for row in rows] == ["ordinary_procedural_intent", None, None]
    assert all(row["synthetic_example"] and not row["original_model_output"] for row in rows)
    assert all(not row["rule_was_modified"] for row in rows)


@pytest.mark.parametrize("reported", ["valid", "invalid"])
def test_annotation_failure_is_not_original_financial_error(reported):
    value = assessment(
        semantic=False,
        effective="unknown",
        reported=reported,
        error="approved span needs reviewed proposition",
    )
    original = copy.deepcopy(value)
    result = audit.classify_existing("slot", {"finish_reason": "tool_calls"}, value)
    assert result["category"] == "annotation_internal_inconsistency"
    assert result["annotation_family"] == "approved_fragment_missing_proposition_link"
    assert result["process_error_established"] is False and result["effective_v_trace"] == "unknown"
    assert value == original


def test_invalid_label_preserves_claim_and_does_not_establish_truth():
    value = assessment(effective="invalid", reported="invalid")
    value["validation"]["parsed"]["slot"]["reason_codes"] = ["critical_contradiction_unretracted"]
    result = audit.classify_existing("slot", {}, value)
    assert result["category"] == "consistent_reviewer_invalid_claim"
    assert result["annotated_unretracted_critical_nonsupported_propositions"] == 0
    assert result["reviewer_reason_codes"] == ["critical_contradiction_unretracted"]
    assert result["native_financial_error_frequency_measured"] is False


def test_network_and_structural_failures_remain_separate():
    malformed = assessment(interface=False, semantic=False, error="invalid JSON")
    network = audit.classify_existing("slot", {"terminal_kind": audit.NETWORK_TERMINAL}, malformed)
    assert network["category"] == "network_unknown_no_model_response"
    assert network["actual_model_response"] is False
    structural = audit.classify_existing("slot", {"finish_reason": "length"}, malformed)
    assert structural["category"] == "structure_or_return_format_failure"
    assert (
        structural["actual_model_response"] is True
        and structural["process_error_established"] is False
    )
    assert (
        audit.classify_existing("slot", {}, None)["category"]
        == "model_return_without_assessment_in_snapshot"
    )


def test_descriptive_action_bucket_does_not_match_retraction_substring():
    assert audit.annotation_family("action judgment lacks proposition/evidence binding") == (
        "action_annotation_binding"
    )
    assert audit.annotation_family("zero-mask retraction lacks original evidence") == (
        "target_coverage_or_mask_annotation"
    )


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root):
    # Deliberately not lexicographic directory order: examples must follow jobs.
    jobs = [
        dict(key="slot:" + token, task_id=f"task{i}", reviewer=0, slot_id=f"s{i}", stage="slot")
        for i, token in enumerate(("z", "a", "b", "c"))
    ]
    body = dict(schema="v8_one_full_review_validation.v1", jobs=jobs)
    write(root / "registration/protocol.json", body | dict(id=digest(body)))
    for job in jobs[:3]:
        directory = root / "jobs" / job["key"].replace(":", "_")
        write(
            directory / "response/record.json",
            dict(finish_reason="tool_calls", review_text='{"v_trace":"unknown"}'),
        )
        write(
            directory / "assessment/record.json",
            assessment(
                semantic=False,
                effective="unknown",
                error=(
                    "nonassertive context requires explicit future opt-in "
                    "and an empty optional Q field"
                ),
            ),
        )
    return jobs


def test_bounded_cases_follow_registered_order_not_directory_or_score(tmp_path):
    jobs = fixture(tmp_path)
    report, rows = audit.inspect_batch(tmp_path)
    assert report["original_job_denominator"] == 4
    assert report["categories"] == {
        "annotation_internal_inconsistency": 3,
        "no_response_in_snapshot": 1,
    }
    assert [
        case["job_key"] for case in report["examples"]["annotation_internal_inconsistency"]
    ] == [j["key"] for j in jobs[:2]]
    assert [row["job_key"] for row in rows] == [j["key"] for j in jobs]
    assert report["global_atomic_snapshot_claimed"] is False
    assert report["actual_trace_financial_error_rate"] is None


def test_late_publishes_are_excluded_from_fixed_membership(tmp_path, monkeypatch):
    jobs = fixture(tmp_path)
    original_read = audit._read
    wrote = False

    def read(path):
        nonlocal wrote
        if path.name == "record.json" and path.parent.name == "response" and not wrote:
            wrote = True
            later = tmp_path / "jobs" / jobs[-1]["key"].replace(":", "_")
            write(later / "response/record.json", {})
            write(later / "assessment/record.json", assessment())
        return original_read(path)

    monkeypatch.setattr(audit, "_read", read)
    report, rows = audit.inspect_batch(tmp_path)
    assert report["observed_actual_model_responses"] == 3
    assert rows[-1]["classification"]["category"] == "no_response_in_snapshot"


def test_dedicated_audit_output_is_immutable_and_keeps_old_bytes(tmp_path):
    technical, production, output = (tmp_path / p for p in ("tech", "prod", "audit"))
    fixture(technical)
    fixture(production)
    source = technical / "jobs/slot_z/assessment/record.json"
    raw = source.read_bytes()
    report = audit.run(output, technical, production)
    assert source.read_bytes() == raw and report["no_old_labels_changed"] is True
    assert (output / "record.json").exists() and (output / "report.md").exists()
    assert len((output / "production_snapshot.jobs.jsonl").read_text().splitlines()) == 4
    with pytest.raises(ValueError, match="immutable audit"):
        audit.run(output, technical, production)
    corrected = audit.regroup_descriptive_families(output, tmp_path / "correction")
    assert corrected["original_API_artifacts_reread"] is False
    assert (
        corrected["batches"]["technical108"]["categories"]
        == report["batches"]["technical108"]["categories"]
    )
    assert source.read_bytes() == raw
