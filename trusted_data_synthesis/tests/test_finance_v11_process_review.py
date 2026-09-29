"""Synthetic V10/V11 counterexamples only, never reclassify paid V10 records."""

import json

import pytest
from test_finance_v10_process_review import fixture as old_fixture
from test_finance_v10_student_encoding import recovered_chain

from trusted_synthesis.finance_research import v10_process_review as old
from trusted_synthesis.finance_research import v11_process_review as new
from trusted_synthesis.finance_research.contracts import digest


def candidate(*, slot="cpu-slot", content=None, recovery=False):
    episode, old_request, old_body = (
        recovered_chain()
        if recovery
        else old_fixture()
        if content is None
        else old_fixture(content)
    )
    requests = {
        r: new.prepare_review_request(
            episode,
            slot_id=slot,
            role=r,
            native_result=old_request["native_result"],
            integrity=old_request["integrity"],
        )
        for r in ("A", "B")
    }
    # Mechanical encoding of hand-written SYNTHETIC annotations, not old paid review reuse.
    original = old_request["trajectory"]
    view = requests["A"]["trajectory"]
    ids = {
        a["segment_id"]: b["segment_id"]
        for a, b in zip(original["segments"], view["segments"], strict=True)
    }

    def ref(value):
        return dict(id=ids[value["segment_id"]], quote=value["quote"])

    process = {
        k: {**v, "evidence": [ref(e) for e in v["evidence"]]}
        for k, v in old_body["process"].items()
    }
    actions = {
        a["arguments_segment_id"]: a["action_id"] for t in view["turns"] for a in t["actions"]
    }
    segments = {s["segment_id"]: s for s in view["segments"]}
    positives = [v for v in old_body["supervision"] if v["decision"] == "positive"]
    body = dict(
        process=process,
        behavior={
            **old_body["behavior"],
            "evidence": [ref(e) for e in old_body["behavior"]["evidence"]],
        },
        supervision=dict(
            status="complete",
            positive_content=[
                ref(e)
                for e in positives
                if segments[ids[e["segment_id"]]]["kind"] == "public_content"
            ],
            positive_actions=[
                actions[ids[e["segment_id"]]] for e in positives if ids[e["segment_id"]] in actions
            ],
        ),
    )
    return episode, requests, body, old_request, old_body


def inspect(body, request):
    return new.inspect_review(json.dumps(body, ensure_ascii=False), request)


def pair(requests, body):
    return new.resolve_candidate_pair(
        inspect(body, requests["A"]),
        inspect({"process": body["process"]}, requests["B"]),
        q_native=True,
    )


def test_independent_layers_flash_B_process_only_and_no_production_admission():
    _, requests, body, _, _ = candidate()
    a, b = inspect(body, requests["A"]), inspect({"process": body["process"]}, requests["B"])
    assert a["raw_process_claims"]["declared_outcome"] == "valid"
    assert a["process_evidence_binding"]["validated_process_outcome"] == "valid"
    assert a["auxiliary"]["supervision"]["usable"] and a["training_admissibility"]["candidate_gate"]
    assert (
        b["reason_projection"] is None
        and b["auxiliary"]["supervision"]["status"] == "not_applicable"
    )
    assert set(requests["B"]["output_schema"]["properties"]) == {"process"}
    assert "context_only" not in requests["A"]["output_schema"]["$defs"]["Supervision"]["required"]
    assert set(requests["A"]["output_schema"]["$defs"]["Reference"]["properties"]) == {
        "id",
        "quote",
    }
    for req in requests.values():
        assert req["model"] == "deepseek-flash"
        assert "not-for-process-model" not in json.dumps(req["messages"])
        restored = json.loads(json.dumps(req, sort_keys=True))
        assert inspect(body if req["role"] == "A" else {"process": body["process"]}, restored)
    joint = new.resolve_candidate_pair(a, b, q_native=True)
    assert joint["candidate_gate"] and not joint["production_admitted"]
    assert not a["semantic_truth_proved"] and not a["actual_model_call_receipt_verified"]


def test_bad_context_only_projection_keeps_process_while_V10_clears_it():
    _, requests, body, old_request, old_body = candidate()
    old_body["supervision"][1]["end"] += 1
    previous = old.inspect_process_review(json.dumps(old_body), old_request)
    assert previous["process_validity"] == "unknown" and previous["parsed"] is None
    content = requests["A"]["trajectory"]["turns"][0]["public_content_segment_id"]
    body["supervision"]["context_only"] = [dict(id=content, quote="not an original quote")]
    result = inspect(body, requests["A"])
    assert result["raw_process_claims"]["declared_outcome"] == "valid"
    assert result["process_evidence_binding"]["validated_process_outcome"] == "valid"
    assert result["auxiliary"]["supervision"]["status"] == "failed"
    assert not result["training_admissibility"]["candidate_gate"]


def test_behavior_error_is_independent_and_does_not_add_pair_gate():
    _, requests, body, old_request, old_body = candidate()
    old_body["behavior"]["evidence"][0]["end"] += 1
    assert (
        old.inspect_process_review(json.dumps(old_body), old_request)["process_validity"]
        == "unknown"
    )
    body["behavior"]["evidence"] = [dict(id="absent-behavior-reference")]
    result = inspect(body, requests["A"])
    assert result["auxiliary"]["behavior"]["status"] == "failed"
    assert result["process_evidence_binding"]["validated_process_outcome"] == "valid"
    assert pair(requests, body)["candidate_gate"]


def test_critical_missing_evidence_or_malformed_status_stays_unknown_not_repaired():
    _, requests, body, _, _ = candidate()
    body["process"]["evidence_and_operations"]["evidence"] = [dict(id="invented-critical")]
    result = inspect(body, requests["A"])
    assert result["raw_process_claims"]["declared_outcome"] == "valid"
    assert result["process_evidence_binding"]["validated_process_outcome"] == "unknown"
    body["process"]["evidence_and_operations"]["status"] = "not_applicable"
    result = inspect(body, requests["A"])
    assert result["raw_process_claims"]["readable"]
    assert result["raw_process_claims"]["declared_outcome"] is None
    assert result["process_evidence_binding"]["validated_process_outcome"] == "unknown"
    assert not result["training_admissibility"]["candidate_gate"]
    body["process"]["evidence_and_operations"]["status"] = ["supported"]
    result = inspect(body, requests["A"])
    assert not result["raw_process_claims"]["readable"]
    assert result["raw_process_claims"]["raw"]["evidence_and_operations"]["status"] == ["supported"]
    assert result["process_evidence_binding"]["validated_process_outcome"] == "unknown"


def test_bound_critical_error_remains_invalid_even_if_auxiliary_bad():
    _, requests, body, old_request, old_body = candidate()
    old_body["process"]["evidence_and_operations"]["status"] = "critical_error"
    assert (
        old.inspect_process_review(json.dumps(old_body), old_request)["process_validity"]
        == "invalid"
    )
    body["process"]["evidence_and_operations"]["status"] = "critical_error"
    body["behavior"] = {"broken": "auxiliary"}
    result = inspect(body, requests["A"])
    assert result["raw_process_claims"]["declared_outcome"] == "invalid"
    assert result["process_evidence_binding"]["validated_process_outcome"] == "invalid"
    assert not result["training_admissibility"]["candidate_gate"]


def test_whole_unit_ids_unicode_lines_and_whole_successful_action_coordinates():
    _, requests, body, _, _ = candidate(
        content="R: 8 minus 2 equals 6.\r\n第二行；不按分号切割。\n尾行  "
    )
    req = requests["A"]
    for doc in req["trajectory"]["segments"]:
        units = [u for u in req["catalog"]["units"] if u["segment_id"] == doc["segment_id"]]
        assert "".join(u["text"] for u in units) == doc["text"]
        assert all(doc["text"][u["start"] : u["end"]] == u["text"] for u in units)
        if doc["kind"] == "action_arguments":
            assert len(units) == 1
    unit = next(u for u in req["catalog"]["units"] if u["kind"] == "public_content")
    body["supervision"]["positive_content"] = [dict(id=unit["unit_id"])]
    result = inspect(body, req)
    span = result["auxiliary"]["supervision"]["positive_content"][0]
    assert span["quote"] == unit["text"] and span["start"] == unit["start"]
    action = result["auxiliary"]["supervision"]["positive_actions"][0]
    original = next(
        s
        for s in req["trajectory"]["segments"]
        if s["segment_id"] == action["whole_original_arguments"]["segment_id"]
    )
    assert action["whole_original_arguments"]["quote"] == original["text"]
    assert action["whole_original_arguments"]["start"] == 0
    assert action["whole_original_arguments"]["end"] == len(original["text"])


def test_duplicate_quote_no_fuzzy_matching_and_contiguous_quote_not_semantic_proof():
    _, requests, body, _, _ = candidate(content="R: 8 is repeated. 8 is repeated.")
    sid = requests["A"]["trajectory"]["turns"][0]["public_content_segment_id"]
    body["process"]["evidence_and_operations"]["evidence"] = [dict(id=sid, quote="8 is repeated.")]
    assert (
        inspect(body, requests["A"])["process_evidence_binding"]["validated_process_outcome"]
        == "unknown"
    )
    _, requests, body, _, _ = candidate(
        content="Excluding discontinued operations, revenue was 8. Review sources."
    )
    sid = requests["A"]["trajectory"]["turns"][0]["public_content_segment_id"]
    for quote in ("revenue was 8.00", "Excluding revenue was 8."):
        body["process"]["evidence_and_operations"]["evidence"] = [dict(id=sid, quote=quote)]
        assert (
            inspect(body, requests["A"])["process_evidence_binding"]["validated_process_outcome"]
            == "unknown"
        )
    body["process"]["evidence_and_operations"]["evidence"] = [dict(id=sid, quote="revenue was 8.")]
    result = inspect(body, requests["A"])
    evidence = result["process_evidence_binding"]["dimensions"]["evidence_and_operations"][
        "evidence"
    ][0]
    assert not evidence["semantic_scope_preserved_proved"]
    assert "Excluding discontinued operations" in json.dumps(requests["A"]["messages"])


def test_failed_action_cannot_be_approved_and_failed_history_is_retained():
    episode, requests, body, _, _ = candidate(recovery=True)
    req = requests["A"]
    assert req["catalog"]["events"][0]["is_error"]
    body["supervision"]["positive_actions"].append(req["catalog"]["actions"][0]["action_id"])
    result = inspect(body, req)
    assert result["process_evidence_binding"]["validated_process_outcome"] == "valid"
    assert result["auxiliary"]["supervision"]["status"] == "failed"
    assert not result["training_admissibility"]["candidate_gate"]
    assert req["episode_sha256"] == digest(episode)
    assert "divide(8, 0)" in json.dumps(req["messages"])


def test_reason0_and_empty_projection_packages_remain_in_mixed_candidate_pool():
    _, zero_requests, zero_body, _, _ = candidate(slot="zero")
    zero_body["supervision"]["positive_content"] = []
    zero_body["supervision"]["positive_actions"] = []
    zero = pair(zero_requests, zero_body)
    assert zero["candidate_gate"] and zero["A"]["reason_projection"]["all_public_reasoning_masked"]
    assert new.candidate_pool_check([zero])["all_pool_public_reasoning_masked"]
    assert not new.candidate_pool_check([zero])["projection_pool_candidate_gate"]
    _, other_requests, other_body, _, _ = candidate(slot="reason-positive")
    other = pair(other_requests, other_body)
    pool = new.candidate_pool_check([zero, other])
    assert pool["candidate_slot_ids"] == ["zero", "reason-positive"]
    assert pool["projection_pool_candidate_gate"] and not pool["production_admitted"]


def test_incomplete_supervision_blocks_whole_joint_pool_never_good_subset():
    _, bad_requests, bad_body, _, _ = candidate(slot="projection-pending")
    bad_body["supervision"]["status"] = "unknown"
    blocked = pair(bad_requests, bad_body)
    assert blocked["joint_process_candidate"] and not blocked["candidate_gate"]
    assert blocked["A"]["reason_projection"]["positive_public_characters"] is None
    assert blocked["A"]["reason_projection"]["all_public_reasoning_masked"] is None
    _, good_requests, good_body, _, _ = candidate(slot="good")
    pool = new.candidate_pool_check([blocked, pair(good_requests, good_body)])
    assert pool["candidate_slot_ids"] == ["projection-pending", "good"]
    assert pool["blocked_slot_ids"] == ["projection-pending"]
    assert pool["all_pool_public_reasoning_masked"] is None
    assert not pool["projection_pool_candidate_gate"] and pool["no_joint_process_candidate_dropped"]


def test_no_old_paid_schema_or_invalid_JSON_can_claim_production_or_repaired_process():
    _, requests, body, old_request, old_body = candidate()
    with pytest.raises(ValueError, match="V11"):
        new.inspect_review(json.dumps(old_body), old_request)
    broken = new.inspect_review('{"process":', requests["A"])
    assert broken["envelope_error"] and not broken["raw_process_claims"]["readable"]
    assert broken["process_evidence_binding"]["validated_process_outcome"] == "unknown"
    assert not broken["training_admissibility"]["production_admitted"]
    b = inspect({"process": body["process"]}, requests["B"])
    a = inspect(body, requests["A"])
    with pytest.raises(ValueError, match="native flag"):
        new.resolve_candidate_pair(a, b, q_native=False)
