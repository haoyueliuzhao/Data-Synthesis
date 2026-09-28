"""Synthetic own-side alignment controls, not a paid R7 cohort."""

import copy
import json

import pytest
from test_finance_semantic_review import fixture_review
from test_finance_v6_state_alignment import alignment_fixture, prepared_fixture
from test_finance_v7_slot_review import typed_fixture

from trusted_synthesis.finance_research import v7_flat_alignment as alignment
from trusted_synthesis.finance_research import v7_flat_review as flat
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import ReviewError


def setup(reviewer=0, failed_slot=None):
    prepared = prepared_fixture()
    bundle = prepared["bundle"]
    reviews = {}
    for slot in bundle["slots"]:
        sid = slot["slot_id"]
        request = flat.slot_review_request(bundle, sid, {}, reviewer)
        value = typed_fixture(
            request["flat_baseline_request"]["typed_baseline_request"],
            fixture_review(bundle, reviewer),
        )
        graph = value.pop("semantic_graph")
        value.update(nodes=graph["nodes"], edges=graph["edges"])
        value["actions"] = [dict(action_id=k, **v) for k, v in value["actions"].items()]
        value["mask"] = [dict(target_id=k, **v) for k, v in value["mask"].items()]
        artifact = dict(
            wire_protocol=flat.WIRE_PROTOCOL,
            semantic_review_request_sha256=digest(request),
            finish_reason="tool_calls",
            review_format_error=None,
            review_text="{" if sid == failed_slot else json.dumps(value),
        )
        reviews[sid] = alignment.slot_review_record(request, artifact)
    request = alignment.alignment_request(prepared, reviews, reviewer)
    return prepared, reviews, request


def test_fresh_flat_records_keep_v6_identity_and_align_one_side_eight_only():
    _, reviews, request = setup(1)
    assert len(reviews) == len(request["own_slot_reviews"]) == 8
    assert all(r["wire_protocol"] == "v6_slot_review.v6" for r in reviews.values())
    assert all(r["reviewer"] == 1 for r in request["own_slot_reviews"].values())
    payload = json.loads(request["messages"][1]["content"])
    assert payload["wire_protocol"] == "v6_alignment_review.v5"
    assert payload["slot_review_protocol"] == "v6_slot_review.v6"
    assert (
        not request["other_reviewer_output_visible"]
        and not request["previous_trial_outputs_visible"]
    )
    raw = json.dumps(alignment_fixture(request))
    result = alignment.validate_alignment(raw, request)
    assert result["interface_admitted"] and result["semantic_consistent"]
    assert result["wire_protocol"] == "v6_alignment_review.v5"
    assert result["slot_review_protocol"] == "v6_slot_review.v6"
    assert not result["previous_trial_outputs_reused"]
    restored = json.loads(json.dumps(request, sort_keys=True))
    assert alignment.validate_alignment(raw, restored) == result


def test_failed_flat_slot_stays_unknown_at_its_original_coordinate():
    _, reviews, request = setup(failed_slot="s0")
    assert len(reviews) == 8 and reviews["s0"]["v_trace"] == "unknown"
    assert not reviews["s0"]["interface_admitted"]
    assert len(request["own_eligible_slot_ids"]) == 7
    result = alignment.validate_alignment(json.dumps(alignment_fixture(request)), request)
    assert result["interface_admitted"]
    assert result["pairs"]["s0_s1"]["relation"] == "not_applicable"


def test_old_wire_or_changed_failed_artifact_cannot_enter_fresh_alignment():
    prepared, reviews, _ = setup(failed_slot="s0")
    changed = copy.deepcopy(reviews)
    changed["s0"]["wire_protocol"] = "v6_slot_review.v5"
    with pytest.raises(ReviewError, match="flat-v6"):
        alignment.alignment_request(prepared, changed)
    changed = copy.deepcopy(reviews)
    changed["s0"]["original_slot_artifact_sha256"] = "unbound"
    with pytest.raises(ReviewError, match="changed or reclassified"):
        alignment.alignment_request(prepared, changed)
