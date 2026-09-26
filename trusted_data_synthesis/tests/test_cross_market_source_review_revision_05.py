"""Offline planner routing and bounded identity; never prepares real materials."""

from copy import deepcopy

import cross_market_source_review_revision_05_20260927 as m
import pytest


def records(added=20):
    plan = dict(
        id="financial:05",
        evidence_revision_number=5,
        document_count=440,
        documents=[{}] * 440,
        fixed_original_candidates=9513,
        fixed_supplementary_anchors=20,
        fixed_total_candidate_anchors=9533,
        maximum_anchor_scan_documents=0,
        parent_references=dict(
            frozen_anchor_scan=dict(path="/synthetic/oldscan", sha256="oldscan", bytes=1)
        ),
        maximum_new_review_plans=0,
        quotas=dict.fromkeys(m.GROUPS, 60),
    )
    scan = dict(
        id="scan:05",
        protocol_id=plan["id"],
        documents=440,
        status="FROZEN_LITERAL_ANCHORS_REUSED_NO_NEW_SCAN",
        explicit_cached_view=True,
        new_original_source_scans=0,
        source_scan_reference=plan["parent_references"]["frozen_anchor_scan"],
        original_anchors=9513,
        added_anchors=added,
        total_anchors=9513 + added,
        original_candidates_unchanged=True,
    )
    summary = dict(
        protocol_id=plan["id"],
        documents=440,
        status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
        original_input_candidates=9513,
        supplementary_input_candidates=added,
        input_candidates=9513 + added,
        candidate_counts=dict.fromkeys(m.GROUPS, 60),
        original_candidates_unchanged=True,
    )
    candidates = dict(
        protocol_id=plan["id"], candidates=[dict(group=g) for g in m.GROUPS for _ in range(60)]
    )
    return dict(
        financial_protocol=plan,
        financial_completion=summary,
        anchor_scan=scan,
        financial_candidates=candidates,
    )


def args(data):
    return [
        data[k]
        for k in (
            "financial_protocol",
            "financial_completion",
            "anchor_scan",
            "financial_candidates",
        )
    ]


def binding(data):
    return dict(
        sources={m.SCRIPT: "synthetic"},
        references={k: dict(path="/synthetic/" + k, sha256="sha", bytes=1) for k in data},
        registered_total_input_candidates=data["anchor_scan"]["total_anchors"],
        additional_offline_planner_attempts=1,
    )


def test_exact_twenty_anchor_view_not_an_automatic_new_scan():
    assert m.validate_financial_state(*args(records(20))) == dict.fromkeys(m.GROUPS, 60)
    for added in (0, 33, 1024):
        with pytest.raises(ValueError):
            m.validate_financial_state(*args(records(added)))


@pytest.mark.parametrize(
    "change",
    [
        "too_many",
        "new_scan",
        "wrong_scan_ref",
        "not_cached",
        "old_phase",
        "wrong_total",
        "wrong_protocol",
        "wrong_documents",
        "unfinished",
        "changed_originals",
        "group_shortfall",
        "count_mismatch",
    ],
)
def test_bad_identity_budget_or_raw_capacity_stops_before_planning(change):
    data = records()
    if change == "too_many":
        data = records(1025)
    elif change == "new_scan":
        data["anchor_scan"]["new_original_source_scans"] = 1
    elif change == "wrong_scan_ref":
        data["anchor_scan"]["source_scan_reference"] = dict(
            path="/different", sha256="different", bytes=1
        )
    elif change == "not_cached":
        data["anchor_scan"]["explicit_cached_view"] = False
    elif change == "old_phase":
        data["financial_protocol"]["evidence_revision_number"] = 4
    elif change == "wrong_total":
        data["financial_completion"]["input_candidates"] = 9513
    elif change == "wrong_protocol":
        data["anchor_scan"]["protocol_id"] = "different"
    elif change == "wrong_documents":
        data["financial_completion"]["documents"] = 439
    elif change == "unfinished":
        data["financial_completion"]["status"] = "INCOMPLETE"
    elif change == "changed_originals":
        data["financial_completion"]["original_candidates_unchanged"] = False
    elif change == "group_shortfall":
        data["financial_candidates"]["candidates"].pop()
        data["financial_completion"]["candidate_counts"][m.GROUPS[-1]] = 59
    else:
        data["financial_completion"]["candidate_counts"][m.GROUPS[0]] = 61
    with pytest.raises(ValueError):
        m.validate_financial_state(*args(data))


def test_only_two_precisely_named_guards_are_replaced(monkeypatch):
    data = records()
    value = binding(data)
    ns = m.namespace(value, data)
    refs = {r["path"]: r for r in value["references"].values()}
    monkeypatch.setattr(m, "ref", lambda path: refs[str(path)])
    with pytest.raises(ValueError, match="bounded_supplement"):
        ns["require"](False, "this_bounded_supplement_inputs_only")
    ns["validated_exact_input_roots"] = True
    ns["require"](False, "this_bounded_supplement_inputs_only")
    ns["require"](False, "complete_fixed_financial_parent")
    for reason in (
        "complete_fixed_geometry_parent",
        "geometry_all_original_pages_inventory_required",
        "character_coverage_gap_or_change",
        "complete_fixed_financial_parent_extra",
    ):
        with pytest.raises(ValueError, match=reason):
            ns["require"](False, reason)


def test_replacement_financial_guard_still_rejects_bad_scan(monkeypatch):
    data = records()
    value = binding(data)
    ns = m.namespace(value, data)
    refs = {r["path"]: r for r in value["references"].values()}
    monkeypatch.setattr(m, "ref", lambda path: refs[str(path)])
    data["anchor_scan"]["added_anchors"] = 21
    with pytest.raises(ValueError, match="registered_scan"):
        ns["require"](False, "complete_fixed_financial_parent")


def test_all_source_union_and_coverage_code_objects_unchanged():
    old_root, old_require, old_checked = m.core.RAW, m.core.require, m.base.checked
    data = records()
    ns = m.namespace(binding(data), data)
    assert (m.core.RAW, m.core.require, m.base.checked) == (old_root, old_require, old_checked)
    for name in (
        "collect_inputs",
        "prepare",
        "build_packets",
        "source_segments",
        "validate_character_coverage",
    ):
        assert ns[name].__code__ is getattr(m.core, name).__code__
    pages = [dict(page=1, text="one"), dict(page=2, text="two")]
    packets = ns["build_packets"](dict(raw_object_id="r", sha256="s", original_url="u"), {}, pages)
    for packet in packets:
        packet["segments"] = [s for s in packet["segments"] if s["page"] == 1]
    with pytest.raises(ValueError, match="every_page"):
        ns["validate_character_coverage"](pages, packets)


def test_wrong_roots_rejected_before_reading_parent_state(monkeypatch, tmp_path):
    def never(*args):
        raise AssertionError("must not inspect registered state for wrong root")

    monkeypatch.setattr(m, "collect_binding", never)
    with pytest.raises(ValueError, match="exact_evidence05"):
        m.prepare(tmp_path, tmp_path, m.GEOMETRY)


def test_protocol_binds_new_offline_phase_before_ID_and_preserves_API_zero():
    data = records()
    value = binding(data)
    plan = m.base.record(
        m.PROTOCOL,
        source_sha256="frozen-core",
        API_authorized=False,
        approved_API_attempts=0,
        visual_coverage_fail_closed=True,
    )
    old_id = plan["id"]
    m.bind_protocol(plan, value)
    assert plan["id"] != old_id and plan["maximum_planner_attempts"] == 1
    assert plan["financial05_zero_review_budget_not_reused"] is True
    assert plan["API_authorized"] is False and plan["Student_calls"] == 0
    assert plan["visual_coverage_fail_closed"] is True
    assert m.validate_binding(plan, value) is plan
    changed = deepcopy(value)
    changed["registered_total_input_candidates"] += 1
    with pytest.raises(ValueError, match="exact_offline"):
        m.validate_binding(plan, changed)
