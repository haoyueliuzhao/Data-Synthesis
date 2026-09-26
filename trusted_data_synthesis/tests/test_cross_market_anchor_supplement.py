"""Synthetic geometry only; no real scan, financial qualification, PDF or network."""

from copy import deepcopy

import cross_market_anchor_supplement_20260926 as m
import pytest


def fixture(rows, originals=()):
    doc = dict(
        raw_object_id="raw-synthetic",
        sha256="a" * 64,
        security_id="synthetic:1",
        source_id="hkex_disclosures",
        original_url="https://example.invalid/a.pdf",
        publish_date="2025-01-01",
    )
    words = []
    for y, texts in enumerate(rows):
        for x, text in enumerate(texts):
            words.append(
                dict(
                    x0=x * 40,
                    y0=y * 15,
                    x1=x * 40 + 30,
                    y1=y * 15 + 8,
                    text=text,
                    block=0,
                    line=y,
                    word=x,
                )
            )
    geometry = m.base.record(
        "cross_market_original_PDF_geometry",
        document=doc,
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        page_selection=dict(selected_pages=[7]),
        pages=[dict(page_number=7, words=words)],
    )
    extraction = m.base.record(
        "PDF_extraction_result", document=doc, parsed=dict(candidates=list(originals))
    )
    return extraction, geometry, doc


@pytest.mark.parametrize(
    "label,metric",
    [
        ("RevenuES", "revenue"),
        ("Cost of revenue", "cost_of_revenue"),
        ("Cost of revenues", "cost_of_revenue"),
    ],
)
def test_only_registered_whole_literals_create_unqualified_locators(label, metric):
    ex, g, d = fixture([[*label.split(), "(100)", "(90)"]])
    result = m.scan_document(ex, g, d)
    c = result["new_anchors"][0]
    assert c["candidate_id"].startswith("source_geometry_anchor:")
    assert c["source_field_name"] == label and c["matched_metric_id"] == metric
    assert c["value"] is c["period_start"] is c["period_end"] is c["currency"] is None
    assert c["financial_scope_type"] is c["statement_type"] is None
    assert c["qa_eligible"] == c["kg_eligible"] == 0
    assert not result["mechanical_reviews"][0]["mechanical_checks_passed"]
    assert result["observations_rederived"] == result["tasks_created"] == 0


@pytest.mark.parametrize(
    "words",
    [
        ["Cost", "of", "goods", "sold", "100", "90"],
        ["Revenue", "100", "90"],
        ["Goods", "and", "services", "100", "90"],
        ["Total", "Revenues", "100", "90"],
        ["Other", "Revenues", "100", "90"],
        ["Costofrevenues", "100", "90"],
        ["Cost", "of", "revenues,", "net", "100", "90"],
        ["Revenues", "100%", "90%"],
        ["Revenues"],
    ],
)
def test_unsupported_labels_percentages_or_group_headers_do_not_create_anchors(words):
    result = m.scan_document(*fixture([words]))
    assert result["new_anchors"] == []


def test_exact_prefix_does_not_authorize_discarding_extra_semantic_label_words():
    result = m.scan_document(
        *fixture([["Cost", "of", "revenues", "excluding", "depreciation", "100", "90"]])
    )
    assert result["new_anchors"] == []
    assert (
        result["rejected_rows"][0]["reason"]
        == "unsupported_extra_semantic_label_or_annotation_word"
    )


@pytest.mark.parametrize("extra", ["(net)", "(excluding)", "[restated]", "5(aftertax)"])
def test_parenthetical_semantic_suffix_is_not_disguised_as_note(extra):
    result = m.scan_document(*fixture([["Revenues", extra, "100", "90"]]))
    assert not result["new_anchors"]
    assert (
        result["rejected_rows"][0]["reason"]
        == "unsupported_extra_semantic_label_or_annotation_word"
    )


def test_revenue_hierarchy_does_not_become_literal_revenues():
    result = m.scan_document(*fixture([["Revenue"], ["Goods", "and", "services", "100", "90"]]))
    assert result["new_anchors"] == []


def test_composite_note_tokens_are_kept_without_assigning_them_to_amounts_or_years():
    result = m.scan_document(*fixture([["Cost", "of", "revenues", "5,", "8", "(100)", "(90)"]]))
    c = result["new_anchors"][0]
    p = c["source_geometry_anchor_provenance"]
    assert [w["text"] for w in p["unassigned_annotation_words"]] == ["5,"]
    assert [w["text"] for w in p["unassigned_native_numeric_words"]] == ["8", "(100)", "(90)"]
    assert c["_raw_value_text"] is None
    assert p["numeric_word_count_is_not_observation_count"]


def test_joined_note_lists_are_bounded_annotations_not_financial_values():
    for token in ("5,8", "5,8,12"):
        result = m.scan_document(*fixture([["Revenues", token, "100", "90"]]))
        candidate = result["new_anchors"][0]
        provenance = candidate["source_geometry_anchor_provenance"]
        assert [w["text"] for w in provenance["unassigned_annotation_words"]] == [token]
        assert [w["text"] for w in provenance["unassigned_native_numeric_words"]] == ["100", "90"]
        assert candidate["value"] is candidate["_raw_value_text"] is None
        assert provenance["numeric_word_count_is_not_observation_count"]
    for token in ("5,8,12,16", "5,8(a)"):
        result = m.scan_document(*fixture([["Revenues", token, "100", "90"]]))
        assert not result["new_anchors"]
        assert result["rejected_rows"][0]["reason"] == (
            "unsupported_extra_semantic_label_or_annotation_word"
        )


def test_existing_original_anchor_suppression_uses_page_metric_label_not_pass_status():
    original = dict(
        candidate_id="old-failed",
        raw_object_id="raw-synthetic",
        page_number=7,
        matched_metric_id="cost_of_revenue",
        source_field_name="costofrevenues",
        review_status="FAILED",
    )
    result = m.scan_document(*fixture([["Cost", "of", "revenues", "100", "90"]], [original]))
    assert result["new_anchors"] == []
    assert result["skipped_existing"][0]["original_candidate_ids"] == ["old-failed"]


def test_other_page_or_different_metric_does_not_suppress_new_literal_anchor():
    original = dict(
        candidate_id="old",
        raw_object_id="raw-synthetic",
        page_number=6,
        matched_metric_id="revenue",
        source_field_name="revenues",
    )
    result = m.scan_document(*fixture([["Revenues", "100", "90"]], [original]))
    assert len(result["new_anchors"]) == 1


def test_multiple_same_page_rows_have_distinct_physical_identities_when_not_previously_anchored():
    result = m.scan_document(*fixture([["Revenues", "100", "90"], ["Revenues", "80", "70"]]))
    assert len(result["new_anchors"]) == 2
    assert len({c["candidate_id"] for c in result["new_anchors"]}) == 2


def test_scanning_does_not_mutate_original_candidates_or_geometry_and_is_deterministic():
    args = fixture([["Revenues", "100", "90"]])
    before = deepcopy(args)
    assert m.scan_document(*args) == m.scan_document(*args)
    assert args == before


def test_word_indices_reference_original_cache_not_sorted_replacement_indices():
    ex, g, d = fixture([["Revenues", "100", "90"]])
    body = {k: v for k, v in g.items() if k not in {"id", "schema_version"}}
    body["pages"][0]["words"] = list(reversed(body["pages"][0]["words"]))
    g = m.base.record("cross_market_original_PDF_geometry", **body)
    p = m.scan_document(ex, g, d)["new_anchors"][0]["source_geometry_anchor_provenance"]
    assert p["row_word_indices"] == [2, 1, 0]
    assert p["label_word_indices"] == [2]


def test_new_anchors_have_all_core_consumed_fields_but_no_fabricated_old_credit():
    c = m.scan_document(*fixture([["Revenues", "100", "90"]]))["new_anchors"][0]
    keys = {
        "candidate_id",
        "raw_object_id",
        "page_number",
        "column_index",
        "source_field_name",
        "matched_metric_id",
        "period_start",
        "period_end",
        "_raw_value_text",
        "value",
        "currency",
        "value_scale",
        "_period_source_page",
        "_unit_source_page",
        "_statement_source_page",
        "statement_type",
        "financial_scope_type",
        "extraction_metadata",
    }
    assert keys <= c.keys()
    assert c["extraction_metadata"]["statement_title"] is None
    assert c["extraction_metadata"]["period_inference"] == "not_established_new_geometry_anchor"
    assert c["placeholder_contract"]["no_original_parser_credit"]
    assert c["source_geometry_anchor_provenance"]["not_an_original_9513_parser_candidate"]


def test_per_document_cap_fails_instead_of_returning_first_64():
    with pytest.raises(m.AnchorCapExceeded) as error:
        m.scan_document(*fixture([["Revenues", str(1000 + i), "90"] for i in range(65)]))
    assert error.value.observed == 65 and error.value.limit == 64


def test_global_cap_is_explicit_and_no_truncation():
    assert m.enforce_global_anchor_cap(1024) == 1024
    with pytest.raises(m.AnchorCapExceeded):
        m.enforce_global_anchor_cap(1025)


def test_unregistered_geometry_page_or_changed_cache_identity_fails():
    ex, g, d = fixture([["Revenues", "100", "90"]])
    body = {k: v for k, v in g.items() if k not in {"id", "schema_version"}}
    body["page_selection"]["selected_pages"] = []
    with pytest.raises(ValueError, match="selected_pages"):
        m.scan_document(ex, m.base.record("cross_market_original_PDF_geometry", **body), d)
    ex["parsed"]["candidates"].append(dict(candidate_id="tampered"))
    with pytest.raises(ValueError, match="record_identity"):
        m.scan_document(ex, g, d)


def test_native_number_validation_does_not_treat_notes_or_percentages_as_money():
    assert m.native_number("(1,000.25)")
    assert m.native_number("−10")
    assert not any(m.native_number(v) for v in ["5,", "10%", "1,00", "(a)", "—", "NaN"])
