"""Synthetic stage04 integration and finite cache budgets; no original PDFs."""

from copy import deepcopy

import cross_market_anchor_supplement_20260926 as supplement
import pytest
import run_cross_market_evidence_revision_04_20260926 as m
from test_cross_market_layout_qualification import doc, geometry, word


def anchored_case(parent_row=False):
    d = doc()
    g = geometry()
    g["pages"][0]["words"][5]["text"] = "Revenues"
    if parent_row:
        g["pages"][0]["words"].extend(
            [
                word("Parent company income statement", 50, 230),
                word("Revenues", 50, 280),
                word("70", 375, 280, 25),
                word("60", 455, 280, 25),
            ]
        )
    g = m.base.record(
        "cross_market_original_PDF_geometry",
        document=d,
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        page_selection={"selected_pages": [1]},
        pages=g["pages"],
    )
    e = m.base.record("PDF_extraction_result", document=d, parsed={"candidates": []})
    return d, g, e, supplement.scan_document(e, g, d)


def test_unqualified_None_anchor_can_only_rederive_same_physical_source_row():
    d, g, _, scanned = anchored_case()
    c = scanned["new_anchors"][0]
    before = deepcopy(c)
    facts = m.namespace()["financial_facts"](c, d, scanned["mechanical_reviews"][0], g)
    m.verify_supplementary_binding(c, facts)
    assert c == before and c["value"] is None and c["period_start"] is None
    assert facts[0]["record"]["val"] == "100000000"
    assert facts[0]["original_candidate_bindings"][0]["value"] is None
    assert not facts[0]["qa_eligible"]


def test_same_page_parent_anchor_cannot_take_other_consolidated_row_credit():
    d, g, _, scanned = anchored_case(parent_row=True)
    assert len(scanned["new_anchors"]) == 2
    ns = m.namespace()
    primary, parent = scanned["new_anchors"]
    facts = ns["financial_facts"](primary, d, scanned["mechanical_reviews"][0], g)
    m.verify_supplementary_binding(primary, facts)
    # Frozen page/label relocation itself may find the consolidated row. The
    # new exact physical-source guard must reject credit to the parent locator.
    other = ns["financial_facts"](parent, d, scanned["mechanical_reviews"][1], g)
    with pytest.raises(ValueError, match="cannot_rebind_another_row"):
        m.verify_supplementary_binding(parent, other)


@pytest.mark.parametrize("mode", ["page", "word", "label"])
def test_new_locator_cannot_change_page_or_word_lineage(mode):
    d, g, _, scanned = anchored_case()
    c = scanned["new_anchors"][0]
    facts = m.namespace()["financial_facts"](c, d, scanned["mechanical_reviews"][0], g)
    p = c["source_geometry_anchor_provenance"]
    if mode == "page":
        p["page_number"] = 2
    elif mode == "word":
        p["row_word_indices"] = p["label_word_indices"]
    else:
        p["label_word_indices"] = [999]
    with pytest.raises(ValueError, match="cannot_rebind_another_row"):
        m.verify_supplementary_binding(c, facts)


def test_reserved_cache_attempt_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "RAW", tmp_path)
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    plan = {"id": "synthetic"}
    m.reserve(plan, "scan_attempts", "one")
    with pytest.raises(ValueError, match="unsettled_attempt"):
        m.reserve(plan, "scan_attempts", "one")
    assert len(list((tmp_path / "scan_attempts").glob("*.json"))) == 1


def test_new_output_cannot_overwrite_previous_source(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "RAW", tmp_path / "new")
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    with pytest.raises(ValueError, match="output_root"):
        m.save(tmp_path / "prior.json", {"changed": True})


def test_new_anchor_pool_cap_and_observation_budget_are_finite():
    assert m.MAX_NEW_ANCHORS == supplement.MAX_TOTAL_ROWS == 1024
    assert m.MAX_NEW_PER_DOCUMENT == supplement.MAX_ROWS_PER_DOCUMENT == 64
    assert m.MAX_OBSERVATIONS == 2 * (9513 + 1024) == 21074
    with pytest.raises(supplement.AnchorCapExceeded):
        supplement.enforce_global_anchor_cap(1025)


def test_namespace_preserves_financial_semantics_and_header_scope_hook():
    ns = m.namespace()
    assert ns["financial_facts"].__code__ is m.core.financial_facts.__code__
    assert ns["_fact"].__code__ is m.core._fact.__code__
    assert "header_binding_proof" in ns
    d, g, _, scanned = anchored_case()
    g["pages"][0]["words"].append(word("(Restated)", 440, 111))
    # This synthetic mutation is not read via the immutable input loader.
    with pytest.raises(ValueError, match="restatement"):
        ns["financial_facts"](scanned["new_anchors"][0], d, scanned["mechanical_reviews"][0], g)
