"""Synthetic new-scope semantics; no real review, API, PDF, GPU or certificate IO."""

import copy

import cross_market_text_table_review_revision_20260927 as m
import pytest


def reference(value, path="/synthetic/record.json"):
    payload = m.base.encode(value)
    return dict(path=path, sha256=m.base.sha(payload), bytes=len(payload))


def fixture(pages=None):
    pages = (
        pages
        if pages is not None
        else [dict(page=1, text="Consolidated revenue totals\n2021 to 2023\n")]
    )
    doc = dict(
        raw_object_id="raw-1", sha256="a" * 64, original_url="https://example.invalid/report.pdf"
    )
    text = dict(pages=pages)
    text_ref = reference(text, "/synthetic/text.json")
    packets = m.core.build_packets(doc, text_ref, pages)
    task = dict(
        group="composition_required",
        task_id="task-1",
        metric_id="revenue",
        periods=[
            ["2021-01-01", "2021-12-31"],
            ["2022-01-01", "2022-12-31"],
            ["2023-01-01", "2023-12-31"],
        ],
        source_exhaustion_review_raw_objects=["raw-1"],
        raw_object_ids=["raw-1"],
    )
    plan = dict(
        id="material-plan",
        financial_protocol_id="financial-plan",
        tasks=[task],
        documents=[dict(document=doc, page_text_reference=text_ref)],
    )
    manifest = dict(
        protocol_id=plan["id"],
        packets=[
            dict(raw_object_id="raw-1", packet_id=p["id"], reference=reference(p)) for p in packets
        ],
    )
    materials, reviews = {}, {}
    for packet in packets:
        materials[packet["id"]] = packet
        projection = m.project_packet(packet, reference(packet))
        payload = empty_payload(packet, projection)
        reviews[packet["id"]] = review(packet, projection, payload)
    return task, plan, manifest, materials, reviews, {"raw-1": text}


def empty_payload(packet, projection):
    return dict(
        packet_id=packet["id"],
        segments_reviewed=[s["segment_key"] for s in projection["line_ledger"]["segments"]],
        findings=[],
        uncertainties=[],
    )


def execution(packet, payload):
    return dict(
        protocol_id="semantic-plan",
        packet_id=packet["id"],
        packet_sha256=m.base.sha(m.base.encode(packet)),
        payload_sha256=m.base.sha(m.base.encode(payload)),
        model="deepseek-v4-pro",
        provider="DeepSeek",
        request_reference=reference({"real_test_fixture": "request"}),
        raw_response_reference=reference({"real_test_fixture": "response"}),
        finish_reason="stop",
        independent_of_Student_and_Q=True,
    )


def review(packet, projection, payload, **execution_changes):
    receipt = execution(packet, payload)
    receipt.update(execution_changes)
    return m.build_packet_review(
        review_protocol_id="semantic-plan",
        packet=packet,
        projection=projection,
        payload=payload,
        execution=receipt,
    )


def assess(values):
    return m.assess_task(*values, review_protocol_id="semantic-plan")


def replace_payload(values, *, finding=None, uncertainty=None):
    packet = next(iter(values[3].values()))
    projection = m.project_packet(packet, reference(packet))
    payload = empty_payload(packet, projection)
    if finding is not None:
        payload["findings"].append(finding)
    if uncertainty is not None:
        payload["uncertainties"].append(uncertainty)
    values[4][packet["id"]] = review(packet, projection, payload)
    return payload


def finding(**changes):
    value = dict(
        id="f1",
        boundary_a="L000000",
        boundary_b="L000001",
        metric="revenue",
        kind="potential_aggregate",
        scope="consolidated",
        aggregation="total",
        period_start="2021-01-01",
        period_end="2023-12-31",
        reason="Synthetic source issue",
    )
    value.update(changes)
    return value


def test_projection_preserves_text_but_removes_universal_visual_gate():
    values = fixture([dict(page=1, text="Line one\nLine two\n"), dict(page=2, text="")])
    packet = next(iter(values[3].values()))
    original = copy.deepcopy(packet)
    projection = m.project_packet(packet, reference(packet))
    rendered = m.base.encode(projection["payload"]).decode()
    assert packet == original
    assert "visual_and_vector_semantics_not_yet_reviewed" not in rendered
    assert "empty_saved_text_requires_original_visual_review" not in rendered
    assert "independent original-source and visual" not in m.request_instruction().lower()
    segments = projection["payload"]["indexed_segments"]
    assert ["".join(line["text"] for line in row["lines"]) for row in segments] == [
        s["text"] for s in packet["segments"]
    ]
    assert projection["payload"]["modality_contract"]["universal_visual_receipts_required"] is False


def test_same_provider_single_semantic_pass_without_human_or_visual_claim():
    values = fixture([dict(page=i, text=f"Ordinary context page {i}\n") for i in range(1, 14)])
    result = assess(values)
    assert result["status"] == m.PASS and len(result["packet_review_ids"]) == 2
    assert result["provider_independence_not_claimed"] is True
    assert result["original_visual_content_reviewed"] is False
    assert "all_original_source_pages_reviewed" not in result
    assert "independent_of_scan_provider_and_Student" not in result
    assert result["no_same_concept_three_year_aggregate_in_reviewed_text"] is True


def test_empty_text_is_limited_scope_not_automatic_clearance_of_original_page():
    result = assess(fixture([dict(page=1, text="Annual text"), dict(page=2, text="")]))
    assert result["status"] == m.PASS
    doc = result["documents"][0]
    assert doc["empty_saved_text_pages"] == [2]
    assert doc["empty_text_page_original_semantics"] == "unknown_not_declared_empty_or_nonfinancial"
    assert doc["original_visual_content_reviewed"] is False


def test_potential_exact_window_does_not_become_confirmed_aggregate():
    values = fixture()
    replace_payload(values, finding=finding())
    result = assess(values)
    assert result["status"] == "PENDING_POTENTIAL_AGGREGATE" and not result["passed"]
    assert len(result["potential_aggregates"]) == 1
    assert result["potential_aggregates"][0]["source_span"]["fragments"][0]["quote"]
    assert not result["technical_pending"]


@pytest.mark.parametrize(
    "changes",
    [
        dict(metric="net_income"),
        dict(scope="parent"),
        dict(period_start="2010-01-01", period_end="2012-12-31"),
    ],
)
def test_specific_different_metric_scope_or_window_does_not_block_task(changes):
    values = fixture()
    replace_payload(values, finding=finding(**changes))
    assert assess(values)["status"] == m.PASS


def test_unknown_relevant_period_or_metric_remains_pending():
    values = fixture()
    replace_payload(
        values,
        finding=finding(metric="unknown", scope="unknown", period_start=None, period_end=None),
    )
    assert assess(values)["status"] == "PENDING_POTENTIAL_AGGREGATE"


def test_specific_financial_gap_blocks_affected_task_without_visual_prerequisite():
    values = fixture()
    replace_payload(
        values,
        uncertainty=dict(
            segment_key="S000",
            metric="revenue",
            period_start=None,
            period_end=None,
            reason="Source points to unreadable total table",
        ),
    )
    result = assess(values)
    assert result["status"] == "PENDING_TASK_EVIDENCE" and len(result["evidence_pending"]) == 1


@pytest.mark.parametrize(
    "change",
    [
        dict(finish_reason="length"),
        dict(independent_of_Student_and_Q=False),
        dict(payload_sha256="f" * 64),
        dict(raw_response_reference={}),
    ],
)
def test_actual_execution_binding_and_truncation_are_technical_failures(change):
    values = fixture()
    packet = next(iter(values[3].values()))
    projection = m.project_packet(packet, reference(packet))
    with pytest.raises(ValueError, match="actual_saved_semantic_execution_binding"):
        review(packet, projection, empty_payload(packet, projection), **change)


def test_omitted_segments_and_forged_boundaries_rejected():
    values = fixture()
    packet = next(iter(values[3].values()))
    projection = m.project_packet(packet, reference(packet))
    payload = empty_payload(packet, projection)
    payload["segments_reviewed"] = []
    with pytest.raises(ValueError, match="all_saved_segments"):
        m.validate_semantic_response(packet, projection, payload)
    payload = empty_payload(packet, projection)
    payload["findings"] = [finding(boundary_b="L999999")]
    with pytest.raises(ValueError, match="two_real_line_boundaries"):
        m.validate_semantic_response(packet, projection, payload)


def test_missing_review_is_technical_pending_not_semantic_rejection():
    values = fixture()
    values[4].clear()
    result = assess(values)
    assert result["status"] == "PENDING_TECHNICAL_REVIEW"
    assert result["technical_pending"] and not result["evidence_pending"]
    assert not result["all_saved_text_semantically_reviewed"]


def test_full_character_coverage_still_cannot_omit_tail():
    values = fixture()
    values[5]["raw-1"]["pages"][0]["text"] += "missing tail"
    with pytest.raises(ValueError):
        assess(values)


def financial_documents(values):
    source = values[1]["documents"][0]
    return {
        "raw-1": dict(
            document=source["document"],
            input_references=dict(text_bundle=source["page_text_reference"]),
        )
    }


def test_new_panel_contract_accepts_only_explicit_text_scope_and_bound_sources():
    values = fixture()
    result = assess(values)
    assert (
        m.require_composition_review(
            values[0], financial_documents(values), {"task-1": result}, "financial-plan"
        )
        == result["id"]
    )
    wrong = copy.deepcopy(financial_documents(values))
    wrong["raw-1"]["document"]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="task_text_source_content_binding"):
        m.require_composition_review(values[0], wrong, {"task-1": result}, "financial-plan")
    assert m.require_composition_review({"group": "dual_sufficient"}, {}, {}, "p") is None


def bundle(review):
    passed = review["status"] == m.PASS
    return m.base.record(
        m.BUNDLE_KIND,
        review_protocol_id="semantic-plan",
        review_protocol_reference=reference({"protocol": "synthetic"}),
        financial_protocol_id="financial-plan",
        review_scope=m.REVIEW_SCOPE,
        selection_closure=dict(
            complete=True,
            selection_method="synthetic deterministic frontier",
            selected_candidate_task_ids=["task-1"] if passed else [],
            eligible_candidate_task_ids=["task-1"],
            semantically_rejected_candidate_task_ids=[] if passed else ["task-1"],
            reviewed_candidate_task_ids=["task-1"],
        ),
        reviews=[review],
    )


def test_bundle_semantic_pending_is_not_confirmed_aggregate_and_technical_never_closes():
    values = fixture()
    assert m.validate_bundle(bundle(assess(values)))["selection_closure"]["complete"]
    replace_payload(values, finding=finding())
    assert m.validate_bundle(bundle(assess(values)))["reviews"][0]["passed"] is False
    values[4].clear()
    with pytest.raises(ValueError, match="technical_pending_is_not_semantic_ineligibility"):
        m.validate_bundle(bundle(assess(values)))


def test_install_does_not_modify_old_visual_or_certification_globals():
    previous = m.core.require_visual_review
    namespace = {"require_visual_review": previous, "certify_task": m.core.certify_task}
    m.install_text_table_review_namespace(namespace)
    assert namespace["require_composition_review"] is m.require_composition_review
    assert (
        m.core.require_visual_review is previous and namespace["require_visual_review"] is previous
    )
    assert namespace["certify_task"] is m.core.certify_task


def test_frontier_passes_and_semantic_rejections_do_not_require_unreviewed_preflight_tail():
    values = fixture()
    passed = assess(values)
    replace_payload(values, finding=finding())
    rejected = assess(values)

    def renamed(record, name):
        fields = {k: v for k, v in record.items() if k not in {"id", "schema_version"}}
        return m.base.record(m.REVIEW_KIND, **{**fields, "task_id": name})

    pass_ids = [f"pass-{i}" for i in range(60)]
    tail_ids = [f"unreviewed-{i}" for i in range(70)]
    reject_ids = [f"semantic-pending-{i}" for i in range(3)]
    records = [renamed(passed, key) for key in pass_ids] + [
        renamed(rejected, key) for key in reject_ids
    ]
    fields = dict(
        review_protocol_id="semantic-plan",
        review_protocol_reference=reference({"protocol": "synthetic"}),
        financial_protocol_id="financial-plan",
        review_scope=m.REVIEW_SCOPE,
        selection_closure=dict(
            complete=True,
            selection_method="synthetic deterministic frontier",
            selected_candidate_task_ids=pass_ids,
            eligible_candidate_task_ids=pass_ids + tail_ids + reject_ids,
            semantically_rejected_candidate_task_ids=reject_ids,
            reviewed_candidate_task_ids=pass_ids + reject_ids,
        ),
        reviews=records,
    )
    checked = m.validate_bundle(m.base.record(m.BUNDLE_KIND, **fields))
    assert len(checked["reviews"]) == 63
    assert len(checked["selection_closure"]["eligible_candidate_task_ids"]) == 133
    invalid = copy.deepcopy(fields)
    invalid["selection_closure"]["selected_candidate_task_ids"] = pass_ids[:59] + tail_ids[:1]
    with pytest.raises(ValueError, match="bundle_exact_outcomes_and_selected_subset"):
        m.validate_bundle(m.base.record(m.BUNDLE_KIND, **invalid))
