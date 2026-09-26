"""Synthetic coverage/accountability tests. No PDF, API, Student, or claimed human review."""

from copy import deepcopy

import cross_market_source_review_20260926 as m
import pytest


def doc():
    return dict(
        raw_object_id="raw-test",
        sha256="a" * 64,
        original_url="https://example.invalid/original.pdf",
    )


def packets(pages=None):
    pages = pages or [dict(page=1, text="Revenue for three years was 123.")]
    return m.build_packets(doc(), dict(path="/unused.json", sha256="b" * 64, bytes=1), pages)


def payload(packet):
    return dict(
        packet_id=packet["id"],
        segments_reviewed=[s["segment_id"] for s in packet["segments"]],
        findings=[],
        uncertainties=[],
    )


def test_every_page_every_character_including_empty_is_covered():
    pages = [
        dict(page=1, text="a" * 25000),
        dict(page=2, text=""),
        dict(page=3, text="last character X"),
    ]
    result = packets(pages)
    assert m.validate_character_coverage(pages, result)
    assert {s["page"] for p in result for s in p["segments"]} == {1, 2, 3}
    assert any(s["text"] == "" for p in result for s in p["segments"])
    assert all(
        sum(len(s["text"]) for s in p["segments"]) <= m.MAX_PACKET_CHARACTERS for p in result
    )


def test_packet_page_count_cap_is_fixed_not_based_on_keyword_hits():
    pages = [dict(page=i, text="irrelevant-looking prose") for i in range(1, 26)]
    result = packets(pages)
    assert len(result) == 3
    assert [len({s["page"] for s in p["segments"]}) for p in result] == [12, 12, 1]


@pytest.mark.parametrize("mode", ["missing_page", "tail_gap", "modified_text", "wrong_source_hash"])
def test_coverage_gaps_and_changed_text_fail(mode):
    pages = [dict(page=1, text="a" * 18000), dict(page=2, text="final")]
    result = deepcopy(packets(pages))
    if mode == "missing_page":
        for p in result:
            p["segments"] = [s for s in p["segments"] if s["page"] != 2]
    elif mode == "tail_gap":
        for p in result:
            p["segments"] = [s for s in p["segments"] if not (s["page"] == 1 and s["start"] > 0)]
    elif mode == "modified_text":
        result[0]["segments"][0]["text"] = "wrong"
    else:
        result[0]["segments"][0]["page_text_sha256"] = "wrong"
    with pytest.raises(ValueError):
        m.validate_character_coverage(pages, result)


def test_geometry_image_flags_and_actual_intervals_survive_packet_projection():
    geometry = dict(
        page_coverage_inventory=[
            dict(
                page_number=1,
                saved_text_empty=False,
                image_placement_count=2,
                image_placements=[dict(bbox=[0, 0, 20, 20])],
            )
        ]
    )
    intervals = [
        dict(
            task_id="task",
            metric_id="revenue",
            periods=[
                ["2021-01-01", "2021-12-31"],
                ["2022-01-01", "2022-12-31"],
                ["2023-01-01", "2023-12-31"],
            ],
        )
    ]
    p = m.build_packets(
        doc(),
        {},
        [dict(page=1, text="Text plus unreviewed raster chart")],
        geometry=geometry,
        geometry_reference={"sha256": "g"},
        task_intervals=intervals,
    )[0]
    assert p["registered_candidate_intervals"] == intervals
    assert p["page_coverage"][0]["original_geometry_inventory"]["image_placement_count"] == 2
    assert (
        "raster_visual_content_not_covered_by_text_alone" in p["page_coverage"][0]["quality_alerts"]
    )
    assert "answer_exact" not in str(p)


def test_valid_API_JSON_still_explicitly_does_not_pass_source_review():
    packet = packets()[0]
    checked = m.validate_scan(packet, payload(packet))
    assert checked["passed"] is False
    assert checked["status"] == "SCHEMA_AND_QUOTES_CHECKED_NOT_SEMANTICALLY_CERTIFIED"


def test_LLM_cannot_return_a_passed_boolean_certificate():
    packet = packets()[0]
    data = payload(packet)
    data["passed"] = True
    with pytest.raises(ValueError, match="not_semantic_certificate"):
        m.validate_scan(packet, data)


def test_every_submitted_segment_must_be_declared_even_no_findings():
    packet = packets()[0]
    data = payload(packet)
    data["segments_reviewed"] = []
    with pytest.raises(ValueError, match="complete_segment"):
        m.validate_scan(packet, data)


def test_quote_offsets_are_checked_against_original_not_model_explanation():
    packet = packets()[0]
    data = payload(packet)
    segment = packet["segments"][0]
    data["findings"] = [
        dict(
            finding_id="f1",
            segment_id=segment["segment_id"],
            start=0,
            end=7,
            quote="Revenue",
            metric_id="revenue",
            classification="potential_aggregate",
            period_start=None,
            period_end=None,
            reasoning="Needs independent original-context adjudication",
        )
    ]
    assert not m.validate_scan(packet, data)["passed"]
    data["findings"][0]["quote"] = "Invented"
    with pytest.raises(ValueError, match="exact_source_quote"):
        m.validate_scan(packet, data)


def test_packet_delivery_is_not_a_semantic_verdict(monkeypatch):
    monkeypatch.setattr(m, "save", lambda *_: None)
    packet = packets()[0]
    shown = m.display_packet(dict(id="plan"), packet, "independent-test-reviewer")
    assert shown["original_packet"] == packet
    assert shown["receipt"]["semantic_review_completed"] is False


def independent_fixture(monkeypatch):
    monkeypatch.setattr(m, "save", lambda *_: None)
    packet = packets()[0]
    plan = dict(id="plan")
    receipt = m.display_packet(plan, packet, "independent-test-reviewer")["receipt"]
    scans = {
        lane: m.base.record(
            "cross_market_source_scan_result",
            protocol_id="plan",
            packet_id=packet["id"],
            lane=lane,
            status="ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED",
            result=m.validate_scan(packet, payload(packet)),
        )
        for lane in m.LANES
    }
    review = m.base.record(
        "cross_market_independent_source_packet_review",
        protocol_id="plan",
        packet_id=packet["id"],
        delivery_receipt_id=receipt["id"],
        reviewer_id=receipt["reviewer_id"],
        reviewer_role="independent_original_source_adjudicator",
        independent_of_scan_provider_and_Student=True,
        all_packet_original_materials_semantically_reviewed=True,
        semantic_review_notes="Synthetic test attestation only; "
        "not an actual production source review.",
        reviewed_segment_ids=[s["segment_id"] for s in packet["segments"]],
        adjudicated_locator_items={},
        aggregate_inventory=[],
        metric_assessments={
            metric: dict(status="no_multi_year_aggregate", reasoning="Synthetic fixture")
            for metric in m.METRICS
        },
    )
    return plan, packet, review, receipt, scans


def revise_record(record, kind, **changes):
    body = {k: v for k, v in record.items() if k not in {"id", "schema_version"}}
    body.update(changes)
    return m.base.record(kind, **body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("all_packet_original_materials_semantically_reviewed", False),
        ("independent_of_scan_provider_and_Student", False),
        ("reviewed_segment_ids", []),
        ("metric_assessments", {}),
        ("reviewer_role", "API_model"),
    ],
)
def test_missing_real_independent_review_requirements_remain_pending(monkeypatch, field, value):
    plan, packet, review, receipt, scans = independent_fixture(monkeypatch)
    review = revise_record(
        review, "cross_market_independent_source_packet_review", **{field: value}
    )
    with pytest.raises(ValueError):
        m.validate_independent_packet_review(plan, packet, review, receipt, scans)


def test_unresolved_API_uncertainty_needs_independent_adjudication(monkeypatch):
    plan, packet, review, receipt, scans = independent_fixture(monkeypatch)
    data = payload(packet)
    data["uncertainties"] = [
        dict(segment_id=packet["segments"][0]["segment_id"], reason="Possible visual aggregate")
    ]
    scans["discovery"] = revise_record(
        scans["discovery"], "cross_market_source_scan_result", result=m.validate_scan(packet, data)
    )
    with pytest.raises(ValueError, match="every_locator"):
        m.validate_independent_packet_review(plan, packet, review, receipt, scans)


def test_visual_boolean_without_per_page_evidence_cannot_pass(monkeypatch):
    geometry = dict(
        page_coverage_inventory=[
            dict(page_number=1, saved_text_empty=True, image_placement_count=1),
            dict(page_number=2, saved_text_empty=False, image_placement_count=0),
        ]
    )
    monkeypatch.setattr(m, "read_ref", lambda _: geometry)
    reference = dict(path="unused", sha256="g", bytes=1)
    review = m.base.record(
        "cross_market_document_visual_source_review",
        raw_object_id=doc()["raw_object_id"],
        raw_sha256=doc()["sha256"],
        geometry_reference=reference,
        reviewer_id="independent",
        independent_original_visual_material_review=True,
        all_original_pages_coverage_accounted_for=True,
        unresolved_pages=[],
        page_coverage_ledger=[dict(page_number=1)],
        source_read_receipts=[dict(path="fake")],
    )
    with pytest.raises(ValueError, match="every_original_page"):
        m.require_visual_review(doc(), reference, review)


def test_requests_never_contain_Student_or_Q_results_and_lanes_are_blind():
    packet = packets()[0]
    request = m.request_payload(packet, "challenge", "awaiting-verified-model")
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == m.MAX_OUTPUT_TOKENS
    assert len(request["messages"]) == 2
    assert "you cannot see the other reviewer" in request["messages"][0]["content"]


def test_budget_without_explicit_approval_cannot_authorize_transport():
    plan = m.base.record("cross_market_source_review_protocol", API_authorized=False)
    manifest = m.base.record(
        "cross_market_source_review_packet_manifest", protocol_id=plan["id"], proposed_attempt_cap=4
    )
    approval = m.base.record(
        "cross_market_source_review_budget_approval",
        protocol_id=plan["id"],
        packet_manifest_id=manifest["id"],
        approved=False,
        approved_by="",
        approval_record="",
    )
    with pytest.raises(ValueError, match="explicit_budget"):
        m.validate_budget(plan, manifest, approval)


def test_recorded_aggregate_cannot_coexist_with_no_aggregate_attestation(monkeypatch):
    plan, packet, review, receipt, scans = independent_fixture(monkeypatch)
    row = dict(
        aggregate_id="a1",
        metric_id="revenue",
        financial_scope="consolidated",
        scope_reasoning="Synthetic source",
        period_start="2021-01-01",
        period_end="2023-12-31",
        evidence=[
            dict(segment_id=packet["segments"][0]["segment_id"], start=0, end=7, quote="Revenue")
        ],
    )
    review = revise_record(
        review, "cross_market_independent_source_packet_review", aggregate_inventory=[row]
    )
    with pytest.raises(ValueError, match="contradictory_no_aggregate"):
        m.validate_independent_packet_review(plan, packet, review, receipt, scans)


def test_bad_aggregate_quote_cannot_be_certified_by_reviewer_boolean(monkeypatch):
    plan, packet, review, receipt, scans = independent_fixture(monkeypatch)
    row = dict(
        aggregate_id="a1",
        metric_id="revenue",
        financial_scope="consolidated",
        scope_reasoning="Synthetic source",
        period_start="2021-01-01",
        period_end="2023-12-31",
        evidence=[
            dict(segment_id=packet["segments"][0]["segment_id"], start=0, end=7, quote="FAKED!!")
        ],
    )
    assessments = deepcopy(review["metric_assessments"])
    assessments["revenue"]["status"] = "aggregate_inventory_complete"
    review = revise_record(
        review,
        "cross_market_independent_source_packet_review",
        aggregate_inventory=[row],
        metric_assessments=assessments,
    )
    with pytest.raises(ValueError, match="aggregate_exact_source_quote"):
        m.validate_independent_packet_review(plan, packet, review, receipt, scans)
