"""Synthetic tests; no real financial values, PDFs, network or model calls."""

import copy
import pickle

import audit_cross_market_evidence_20260926 as m
import pytest


@pytest.mark.parametrize(
    "text,value", [("1,234.50", "1234.50"), ("(6,581)", "-6581"), ("−12.0", "-12.0"), ("０", "0")]
)
def test_raw_number_roundtrip_preserves_sign(text, value):
    assert m.raw_decimal(text) == m.Decimal(value)


@pytest.mark.parametrize("text", ["—", "-", "", "N/A", "NaN", "1,234 note", "(12"])
def test_ambiguous_raw_values_are_not_silently_zero_or_repaired(text):
    with pytest.raises(ValueError):
        m.raw_decimal(text)


def candidate(metric="gross_profit", year=2024):
    return dict(
        candidate_id="c",
        raw_object_id="r",
        table_id="t",
        page_number=1,
        row_index=0,
        column_index=1,
        value="12",
        _raw_value_text="12",
        source_field_name="Gross profit",
        matched_metric_id=metric,
        _source_id="hkex_disclosures",
        _unit_source_page=1,
        _period_source_page=1,
        _validation_errors=[],
        evidence_status="verified",
        value_scale="thousand",
        currency="USD",
        financial_scope_type="consolidated_entity",
        fiscal_year=year,
        period_start=f"{year}-01-01",
        period_end=f"{year}-12-31",
        extraction_metadata=dict(table_row_span=[0], period_inference="explicit_statement_header"),
    )


def fixture():
    c = candidate()
    parsed = dict(
        tables=[
            dict(
                table_id="t",
                raw_object_id="r",
                page_number=1,
                raw_table_json=dict(rows=[["Gross profit", "12", "10"]]),
            )
        ]
    )
    pages = {
        1: "Consolidated income statement\nFor the year ended 31 December 2024\n"
        "USD'000\nGross profit\n12\n10"
    }
    return c, parsed, pages


def test_mechanical_success_never_promotes_or_certifies_inferred_period():
    c, parsed, pages = fixture()
    original = copy.deepcopy(c)
    result = m.candidate_review(c, parsed, pages)
    assert result["mechanical_checks_passed"] and result["annual_phrase_observed"]
    assert result["qa_eligible"] is False
    assert result["issuer_identity_admitted"] is False
    assert result["period_start_independently_certified"] is False
    assert c == original


def test_wrong_table_parent_and_wrong_raw_value_are_retained_failures():
    c, parsed, pages = fixture()
    parsed["tables"][0]["raw_object_id"] = "other"
    c["value"] = "120"
    result = m.candidate_review(c, parsed, pages)
    assert not result["mechanical_checks_passed"]
    assert {"table_parent", "raw_numeric_roundtrip"} <= set(result["failures"])


def test_negative_cost_is_detected_without_rewriting_original_candidate():
    c, parsed, pages = fixture()
    c.update(
        matched_metric_id="cost_of_revenue",
        source_field_name="costofsales",
        value="-12",
        _raw_value_text="(12)",
    )
    result = m.candidate_review(c, parsed, pages)
    assert result["signed_HK_cost_presentation"]
    assert c["value"] == "-12"
    c["_source_id"] = "cninfo_announcements"
    assert not m.candidate_review(c, parsed, pages)["signed_HK_cost_presentation"]


def test_identity_snippet_does_not_assert_parent_or_crosslisting():
    pages = {1: "Subsidiary\nCompany name\nPossible entity", 41: "Stock code 123"}
    result = m.identity_snippets(pages, set())
    assert len(result) == 1
    assert result[0]["kind"] == "IDENTITY_LOCATOR_NOT_ADJUDICATED"


def extraction(year, metrics, security="s"):
    return dict(
        document=dict(security_id=security, raw_object_id=f"r{year}"),
        parsed=dict(candidates=[candidate(metric, year) for metric in metrics]),
    )


def test_capacity_is_security_level_ceiling_including_separate_endpoint_reports():
    rows = [
        extraction(y, ("gross_profit", "revenue", "cost_of_revenue", "net_income"))
        for y in (2021, 2022, 2023)
    ]
    result = m.structural_capacity(rows)
    assert result["optimistic_security_level_counts"] == dict(
        dual_sufficient=4, composition_required=2, other_financial=1
    )
    assert not result["task_manifest_created"] and result["admitted_tasks"] == 0
    assert (
        m.structural_capacity(rows + rows)["optimistic_security_level_counts"]
        == result["optimistic_security_level_counts"]
    )


def test_capacity_never_fills_missing_components_or_cross_security_windows():
    rows = [
        extraction(2021, ("revenue", "gross_profit")),
        extraction(2022, ("revenue", "gross_profit")),
        extraction(2023, ("revenue",), security="other"),
    ]
    assert m.structural_capacity(rows)["optimistic_security_level_counts"] == dict.fromkeys(
        m.GROUPS, 0
    )


def test_reserved_missing_completion_cannot_reopen_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "audit")
    plan = dict(id="p", maximum_text_extraction_attempts=1)
    doc = dict(raw_object_id="raw")
    assert m.reserve(plan, "key", doc)
    assert not m.reserve(plan, "key", doc)
    with pytest.raises(ValueError, match="attempt_cap"):
        m.reserve(plan, "other", dict(raw_object_id="another"))


def test_spawn_worker_is_picklable():
    assert pickle.loads(pickle.dumps(m.document_job)) is m.document_job
