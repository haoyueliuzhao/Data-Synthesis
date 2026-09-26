"""Routing/provenance tests; no real registration, PDF, model or API execution."""

from copy import deepcopy
from pathlib import Path

import cross_market_repaired_geometry_execution_20260926 as m
import pytest


def execution_binding():
    return dict(
        sources={m.SCRIPT: "synthetic-hash"},
        geometry_root="fixed/geometry",
        scientific_logic_changed=False,
        source_review_semantically_passed=False,
    )


def parents():
    repair = dict(maximum_original_PDF_opens=15, maximum_attempts_per_PDF=1, documents=[{}] * 15)
    geometry = dict(id="geometry:derived", derived_geometry_view=True)
    complete = dict(
        protocol_id=geometry["id"],
        documents=440,
        coverage_pages=104439,
        selected_pages=7530,
        original_blank_pages_rendered=420,
        status="GEOMETRY_COMPLETE_NOT_ADMITTED",
    )
    return repair, geometry, complete


def test_financial_namespace_reuses_exact_frozen_scientific_code_without_global_changes():
    original_root, original_geometry = m.financial.RAW, m.financial.GEOMETRY
    namespace = m.financial_namespace(Path("/unused"), execution_binding())
    assert namespace["RAW"] == m.FINANCIAL and namespace["GEOMETRY"] == m.GEOMETRY
    assert (m.financial.RAW, m.financial.GEOMETRY) == (original_root, original_geometry)
    for name in (
        "financial_facts",
        "_fact",
        "certify",
        "prepared_geometry",
        "document_qualify",
        "run",
    ):
        assert namespace[name].__code__ is getattr(m.financial, name).__code__
        assert namespace[name].__globals__ is namespace
    assert namespace["old"].compile_candidates is m.financial.old.compile_candidates


def test_review_namespace_preserves_packet_and_coverage_code_and_original_globals():
    original_root, original_require, original_checked = (
        m.review.RAW,
        m.review.require,
        m.base.checked,
    )
    namespace = m.review_namespace(Path("/unused"), execution_binding())
    assert namespace["RAW"] == m.REVIEW
    assert (m.review.RAW, m.review.require, m.base.checked) == (
        original_root,
        original_require,
        original_checked,
    )
    for name in (
        "collect_inputs",
        "prepare",
        "build_packets",
        "source_segments",
        "validate_character_coverage",
    ):
        assert namespace[name].__code__ is getattr(m.review, name).__code__


def test_only_exact_legacy_root_guard_is_substituted_after_explicit_validation():
    namespace = m.review_namespace(Path("/unused"), execution_binding())
    with pytest.raises(ValueError, match="this_bounded_supplement_inputs_only"):
        namespace["require"](False, "this_bounded_supplement_inputs_only")
    namespace["validated_repaired_input_roots"] = True
    namespace["require"](False, "this_bounded_supplement_inputs_only")
    for reason in (
        "complete_fixed_geometry_parent",
        "character_coverage_gap_or_change",
        "input_hash",
        "this_bounded_supplement_inputs_only_extra",
    ):
        with pytest.raises(ValueError, match=reason):
            namespace["require"](False, reason)


@pytest.mark.parametrize("target", ["financial", "geometry"])
def test_wrong_input_roots_rejected_before_binding_or_execution(monkeypatch, tmp_path, target):
    def never(*args):
        raise AssertionError("must reject roots before reading registered data")

    monkeypatch.setattr(m, "binding", never)
    financial = tmp_path if target == "financial" else m.FINANCIAL
    geometry = tmp_path if target == "geometry" else m.GEOMETRY
    with pytest.raises(ValueError, match="only_exact_repaired"):
        m.prepare_review(tmp_path, financial, geometry)


@pytest.mark.parametrize(
    "change",
    [
        "documents",
        "coverage_pages",
        "selected_pages",
        "original_blank_pages_rendered",
        "status",
        "protocol_id",
        "derived_view",
        "sixteen",
        "two_attempts",
    ],
)
def test_reconciliation_completeness_and_finite_authority_not_bypassed(change):
    repair, geometry, complete = parents()
    m.validate_parent_records(repair, geometry, complete)
    if change in {"documents", "coverage_pages", "selected_pages", "original_blank_pages_rendered"}:
        complete[change] -= 1
    elif change == "status":
        complete["status"] = "GEOMETRY_INCOMPLETE_NO_AUTOMATIC_RETRY"
    elif change == "protocol_id":
        complete["protocol_id"] = "old:failure"
    elif change == "derived_view":
        geometry["derived_geometry_view"] = False
    elif change == "sixteen":
        repair["maximum_original_PDF_opens"] = 16
    else:
        repair["maximum_attempts_per_PDF"] = 2
    with pytest.raises(ValueError):
        m.validate_parent_records(repair, geometry, complete)


@pytest.mark.parametrize("kind", [m.FINANCIAL_KIND, m.REVIEW_KIND])
def test_protocol_binding_before_first_save_rehashes_parent_without_semantic_change(kind):
    original = m.base.record(
        kind,
        fixed_rules=dict(quota=60, annual_columns=2),
        sources={},
        API_authorized=False,
        approved_API_attempts=0,
    )
    expected = execution_binding()
    before = deepcopy(original)
    value = m.bind_protocol(original, kind, expected)
    assert value is original and value["id"] != before["id"]
    assert value["fixed_rules"] == before["fixed_rules"]
    assert value["API_authorized"] is False and value["approved_API_attempts"] == 0
    assert m.validate_binding(value, kind, expected) is value
    changed = deepcopy(expected)
    changed["geometry_root"] = "different"
    with pytest.raises(ValueError, match="exact_frozen_execution_binding"):
        m.validate_binding(value, kind, changed)


def test_source_hash_conflicts_rejected_not_overwritten():
    value = m.base.record(m.FINANCIAL_KIND, sources={m.SCRIPT: "old-hash"})
    with pytest.raises(ValueError, match="source_hash_conflict"):
        m.bind_protocol(value, m.FINANCIAL_KIND, execution_binding())


def test_protocol_save_binds_only_new_protocol_and_keeps_attempts_plain(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "FINANCIAL", tmp_path / "financial_new")
    namespace = m.financial_namespace(tmp_path, execution_binding())
    plan = m.base.record(m.FINANCIAL_KIND, sources={}, maximum_enumerations=1)
    namespace["save"](m.FINANCIAL / "protocol.json", plan)
    saved = m.base.read(m.FINANCIAL / "protocol.json")
    assert saved["id"] == plan["id"]
    assert saved["execution_adapter"] == execution_binding()
    namespace["save"](m.FINANCIAL / "document_attempts" / "one.json", dict(attempt=1))
    assert m.base.read(m.FINANCIAL / "document_attempts" / "one.json") == dict(attempt=1)


def test_original_registered_budget_cannot_be_silently_relocated(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m.financial, "RAW", tmp_path / "original_financial")
    monkeypatch.setattr(m.review, "RAW", tmp_path / "original_review")
    m.original_budgets_unspent()
    m.base.write(m.financial.RAW / "protocol.json", dict(id="already-registered"))
    with pytest.raises(ValueError, match="already_registered"):
        m.original_budgets_unspent()


def test_cloned_coverage_checker_still_rejects_page_omission():
    namespace = m.review_namespace(Path("/unused"), execution_binding())
    pages = [dict(page=1, text="one"), dict(page=2, text="two")]
    packets = namespace["build_packets"](
        dict(raw_object_id="r", sha256="a", original_url="url"), {}, pages
    )
    assert namespace["validate_character_coverage"](pages, packets)
    for packet in packets:
        packet["segments"] = [s for s in packet["segments"] if s["page"] != 2]
    with pytest.raises(ValueError, match="every_page_requires_packet"):
        namespace["validate_character_coverage"](pages, packets)
