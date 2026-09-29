"""Small synthetic controls only; no wallet, network, native scoring or GPU calls."""

import copy
import json
import sqlite3

import pytest
from test_finance_v6_strict_review_provider import response_fixture
from test_finance_v10_process_review import fixture
from test_finance_v10_review_production import requests

from trusted_synthesis.finance_research import v10_process_review as old
from trusted_synthesis.finance_research import v10_review_protocol as protocol
from trusted_synthesis.finance_research import v10_review_provider as provider
from trusted_synthesis.finance_research import v11_review_funnel_audit as audit
from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.storage import encode


def side(body=None, *, role="A", finish="tool_calls", raw=None, completion=100):
    _, candidate, default = fixture()
    body = copy.deepcopy(default if body is None else body)
    if role == "B":
        body = {"process": body["process"]}
    raw = json.dumps(body) if raw is None else raw
    normal = finish == "tool_calls"
    inspected = (
        old.inspect_process_review(raw if normal else "", candidate)
        if role == "A"
        else protocol._assess_b(raw if normal else "", candidate)
    )
    return dict(
        role=role,
        slot_id=candidate["slot_id"],
        task_id="synthetic-task",
        request=dict(candidate_request=candidate, max_output_tokens=2048),
        artifact=dict(
            review_text=raw,
            finish_reason=finish,
            review_format_error=None if normal else "strict_finish_not_tool_calls",
            usage={"completion_tokens": completion},
        ),
        inspection=inspected,
        review_status=inspected["review_status"],
        process_validity=inspected["process_validity"],
    )


@pytest.mark.parametrize("area", ["behavior", "context_only"])
def test_supported_claim_can_be_masked_by_auxiliary_annotation_not_financial_error(area):
    _, _, body = fixture()
    location = body["behavior"]["evidence"][0] if area == "behavior" else body["supervision"][1]
    location["end"] += 1
    record = side(body)
    result = audit.diagnose_side(record, "A")
    assert result["saved_category"] == "annotation_failed" and result["raw_status_claim"] == "valid"
    assert result["raw_critical_local_binding_passed"]
    assert result["descriptive_auxiliary_failure_after_bound_raw_process"]
    assert result["first_failure"]["stage"] == ("behavior" if area == "behavior" else "supervision")
    assert result["locator_problems"][0]["problem"] == "unique_exact_quote_wrong_offsets"
    assert record["process_validity"] == "unknown" and not result["saved_judgment_changed"]


def test_declared_critical_error_is_also_preserved_when_bad_context_erases_inspection():
    _, _, body = fixture()
    body["process"]["evidence_and_operations"]["status"] = "critical_error"
    body["supervision"][1]["end"] += 1
    result = audit.diagnose_side(side(body), "A")
    assert result["raw_status_claim"] == "invalid"
    assert result["saved_category"] == "annotation_failed"
    assert result["raw_critical_local_binding_passed"]
    assert result["descriptive_auxiliary_failure_after_bound_raw_process"]


def test_all_locator_issues_include_later_auxiliary_errors_after_critical_first_failure():
    _, _, body = fixture()
    body["process"]["evidence_and_operations"]["evidence"][0]["quote"] = "absent original quote"
    body["behavior"]["evidence"][0]["end"] += 1
    body["supervision"][1]["end"] += 1
    result = audit.diagnose_side(side(body), "A")
    assert result["first_failure"]["stage"] == "process"
    assert {i["context"] for i in result["locator_problems"]} == {
        "critical_process",
        "behavior",
        "supervision",
    }
    assert not result["raw_critical_local_binding_passed"]
    b = audit.diagnose_side(side(body, role="B"), "B")
    assert b["first_failure"]["stage"] == "process"
    assert {i["context"] for i in b["locator_problems"]} == {"critical_process"}


def test_schema_action_and_length_wrapper_are_distinct_and_original_error_retained():
    _, candidate, body = fixture()
    del body["supervision"][0]["decision"]
    result = audit.diagnose_side(side(body), "A")
    assert result["first_failure"]["stage"] == "schema"
    assert result["descriptive_auxiliary_failure_after_bound_raw_process"]
    _, _, body = fixture()
    action = body["supervision"][-1]
    action["end"] -= 1
    action["quote"] = action["quote"][:-1]
    assert audit.diagnose_side(side(body), "A")["first_failure"]["stage"] == "action"
    result = audit.diagnose_side(side(raw='{"process":', finish="length", completion=2048), "A")
    assert result["raw_status_claim"] == "incomplete_or_invalid_statuses"
    assert result["completion_reached_cap"] and result["validator_was_given_empty_string"]
    assert (
        result["first_failure"]["reason"] == "non_normal_envelope_passed_empty_string_to_inspector"
    )
    assert result["original_annotation_error"].startswith("JSONDecodeError:")
    assert result["raw_JSON_error"] is not None
    assert candidate["trajectory"]["offset_unit"] == "unicode_codepoint"


def test_locator_diagnosis_never_fuzzy_repairs_or_selects_duplicate_quotes():
    docs = {
        "single": dict(text="prefix alpha suffix", kind="public_content"),
        "many": dict(text="alpha alpha", kind="public_content"),
    }
    expected = {
        "single": "unique_exact_quote_wrong_offsets",
        "many": "multiple_exact_quotes_unresolved_offsets",
        "absent": "missing_segment",
    }
    for segment, problem in expected.items():
        issue = audit.locator_diagnostic(
            dict(segment_id=segment, start=0, end=4, quote="alpha"),
            docs,
            context="behavior",
            path="synthetic",
        )
        assert issue["problem"] == problem
    issue = audit.locator_diagnostic(
        dict(segment_id="single", start=0, end=4, quote="alp ha"),
        docs,
        context="behavior",
        path="synthetic",
    )
    assert issue["problem"] == "quote_absent_from_referenced_segment"
    assert (
        audit.locator_diagnostic(
            dict(segment_id="many", start=6, end=11, quote="alpha"),
            docs,
            context="behavior",
            path="synthetic",
        )
        is None
    )


def test_saved_failure_mechanism_disagreement_fails_closed():
    record = side()
    record.update(review_status="annotation_failed", process_validity="unknown")
    with pytest.raises(ValueError, match="failure path disagree"):
        audit.diagnose_side(record, "A")


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encode(value)
    path.write_bytes(raw)
    return dict(path=str(path.resolve()), id=value["id"], sha256=audit.sha_bytes(raw))


def _synthetic_paid(request, annotation, run_id):
    """Construct a fully hashed test receipt in memory, never a real paid call."""
    response = response_fixture(json.dumps(annotation))
    body = provider.request_body(request)
    wire, raw = audit.canonical(body), audit.canonical(response)
    coords = invocation_identity(
        dict(run_id=run_id, episode_id=request["episode_id"], attempt_index=1), turn_index=0
    )
    row = dict(
        state="SETTLED",
        response_classification="model_response",
        http_status=200,
        dispatched_at=1,
        settled_at=2,
        settled_microcny=10,
        reserved_microcny=100,
        coordinates_json=json.dumps(coords),
        invocation_id=coords["invocation_id"],
        request_body=wire,
        request_sha256=digest(body),
        response_body=raw,
        response_sha256=audit.sha_bytes(raw),
        usage_json=json.dumps(response["usage"]),
        evidence_json=json.dumps(
            dict(
                **provider._binding(request),
                response_id=response["id"],
                finish_reason="tool_calls",
                automatic_retry=False,
                price_sheet_id="synthetic-not-a-real-bill",
            )
        ),
    )
    artifact = provider.restore_artifact(row, request)
    return protocol.review_record(request, artifact, row)


@pytest.fixture
def synthetic_pair(tmp_path, monkeypatch):
    def no_wallet(*args, **kwargs):
        pytest.fail("funnel diagnosis must not open a wallet")

    monkeypatch.setattr(sqlite3, "connect", no_wallet)
    episode, pair_requests, annotation = requests()
    root, run_id = tmp_path / "synthetic-original", "synthetic-closed-wallet"
    slot_id = pair_requests[0]["slot_id"]
    records = [
        _synthetic_paid(
            request,
            annotation if request["role"] == "A" else {"process": annotation["process"]},
            run_id,
        )
        for request in pair_requests
    ]
    terminals = {}
    for record in records:
        directory = root / "reviews" / slot_id.split(":", 1)[1] / record["role"]
        ref = _write(directory / "record/record.json", record)
        _write(directory / "request/record.json", record["request"])
        _write(directory / "artifact/record.json", record["artifact"])
        terminals[record["role"]] = dict(record=ref, episode_id=record["request"]["episode_id"])
    joint = protocol.resolve_joint_review(*records, q_native=True)
    joint_ref = _write(root / "joint" / slot_id.split(":", 1)[1] / "record.json", joint)
    episode_path = root / "slots" / slot_id.split(":", 1)[1] / "episode/episode.json"
    episode_path.parent.mkdir(parents=True)
    episode_path.write_bytes(encode(episode.model_dump(mode="json")))
    outcome = audit.bound(
        dict(
            schema="v10_generation_slot_outcome.v1",
            status="COMPLETE",
            episode_path=str(episode_path),
            episode_sha256=digest(episode),
            episode_file_sha256=audit.sha_bytes(episode_path.read_bytes()),
        )
    )
    state = dict(
        root=str(root),
        plan=dict(
            id="synthetic-plan",
            batch_id=records[0]["protocol_id"],
            review_policy_id=records[0]["policy_id"],
            budget_config={"run_id": run_id},
        ),
        replacements={},
        anchors={},
        seal=dict(
            id="synthetic-seal",
            joint_slot_ids=[slot_id],
            joint_by_task={episode.task_id: [slot_id]},
            N=1,
        ),
    )
    job = dict(
        index=0,
        slot={"slot_id": slot_id, "task_id": episode.task_id},
        joint=joint_ref,
        outcome=outcome,
        **terminals,
    )
    monkeypatch.setattr(audit, "_STATE", state)
    return state, job


def test_full_pair_seal_http_and_authority_binding_without_wallet(synthetic_pair):
    _, job = synthetic_pair
    pair, sides = audit._audit_pair(job)
    assert pair["A_category"] == pair["B_category"] == "valid"
    assert pair["joint_valid_as_sealed"] and len(sides) == 2
    assert all(s["record_integrity_verified_from_sealed_files"] for s in sides)
    assert all(s["wallet_or_financial_state_reverified"] is False for s in sides)


def test_tampered_or_missing_original_is_not_a_complete_diagnosis(synthetic_pair):
    _, job = synthetic_pair
    from pathlib import Path

    path = Path(job["A"]["record"]["path"])
    raw = path.read_bytes()
    path.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="byte SHA"):
        audit._audit_pair(job)
    path.write_bytes(raw)
    missing = Path(job["outcome"]["episode_path"])
    missing.rename(missing.with_suffix(".held-for-test"))
    with pytest.raises(FileNotFoundError):
        audit._audit_pair(job)


def test_summary_four_by_four_and_fixed_first_two_cases_and_denominator(
    synthetic_pair, monkeypatch
):
    state, job = synthetic_pair
    pair, sides = audit._audit_pair(job)
    monkeypatch.setattr(audit, "PAIR_COUNT", 1)
    monkeypatch.setattr(audit, "SIDE_COUNT", 2)
    summary, files = audit._summarize(iter([(pair, sides)]), state, {})
    assert set(summary["AB_saved_category_cross_table"]) == set(audit.CATEGORIES)
    assert all(
        set(row) == set(audit.CATEGORIES)
        for row in summary["AB_saved_category_cross_table"].values()
    )
    assert summary["AB_saved_category_cross_table"]["valid"]["valid"] == 1
    assert summary["first_failure_agrees_with_every_saved_inspection"]
    assert len(files["sides.jsonl"].splitlines()) == 2
    assert all(len(v) <= 2 for v in json.loads(files["cases.json"])["cases"].values())
    with pytest.raises(ValueError, match="whole audit"):
        audit._summarize(iter([]), state, {})
