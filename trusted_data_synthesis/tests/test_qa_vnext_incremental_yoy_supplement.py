"""Post-run YoY audit domain controls; no task generation or frozen-code edits."""

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/audit_qa_vnext_catalog_incremental_yoy_supplement.py"
)
SPEC = importlib.util.spec_from_file_location("yoy_post_run_audit_controls", PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

SOURCE = """<table>
<tr><td>Years Ended May 31,</td><td colspan="6"></td></tr>
<tr><td>(Dollars in millions)</td><td colspan="2">2025</td><td></td>
<td colspan="2">2024</td><td></td></tr>
<tr><td>Net cash provided by operating activities</td><td>$</td><td>20,821</td><td></td>
<td>$</td><td>18,673</td><td></td></tr>
<tr><td>Capital expenditures</td><td></td><td>(21,215</td><td>)</td>
<td></td><td>(6,866</td><td>)</td></tr>
<tr><td>Free cash flow</td><td>$</td><td>(394</td><td>)</td><td>$</td><td>11,807</td><td></td></tr>
</table>"""


def fixture(phrase="year-over-year", start="2024-06-01", end="2025-05-31", source=SOURCE):
    grid = module.base.original_grid(html.fromstring(source))
    headers, selected = module.base.annual_headers(grid)
    checker = module.YoyAudit.__new__(module.YoyAudit)
    checker.grids = {"original": grid}
    checker.header_sets = {"original": headers}
    checker.selected_rows = {"original": selected}
    checker.supplemented = []
    public = {
        "question": (
            f"What was the {phrase} growth rate of Example's company-defined free cash flow "
            f"in the period {start} through {end}? Report in percent."
        ),
        "sources": [{"source_id": "original", "source_kind": "original_issuer_reconciliation"}],
        "quantity_contract": {
            "unit": "percent",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    return checker, public


@pytest.mark.parametrize("phrase", ["year-over-year", "year over year"])
def test_explicit_yoy_derives_prior_end_only_from_public_calendar(phrase):
    checker, public = fixture(phrase)
    # No private bundle, Oracle, fact role map, or reference answer is provided.
    assert checker.public_target(public) == Decimal(100) * Decimal(-12201) / Decimal(11807)
    proof = checker.supplemented[0]
    assert proof["derived_previous_end"] == "2024-05-31"
    assert proof["private_dates_or_answer_used_to_choose_endpoints"] is False
    assert proof["previous_original_total"] == "11807"
    assert proof["current_original_total"] == "-394"


@pytest.mark.parametrize("phrase", ["annual", "month-over-month", "growth", "year over two years"])
def test_non_yoy_phrases_cannot_acquire_implicit_prior_year(phrase):
    checker, public = fixture(phrase)
    with pytest.raises(ValueError):
        checker.public_target(public)


@pytest.mark.parametrize(
    "start,end",
    [
        ("2024-06-02", "2025-05-31"),
        ("2024-06-01", "2025-05-30"),
        ("2023-06-01", "2025-05-31"),
        ("2025-06-01", "2025-05-31"),
    ],
)
def test_only_contiguous_actual_annual_scope_with_both_source_headers_is_supported(start, end):
    checker, public = fixture(start=start, end=end)
    with pytest.raises(ValueError):
        checker.public_target(public)


def test_positive_prior_base_is_not_optional():
    checker, public = fixture(source=SOURCE.replace(">11,807<", ">(11,807)<"))
    with pytest.raises(ValueError, match="positive original prior-year base"):
        checker.public_target(public)


def test_private_style_hint_does_not_replace_missing_public_yoy_phrase():
    checker, public = fixture("annual")
    checker.private = {"previous_period": ["2023-06-01", "2024-05-31"], "answer_exact": "correct"}
    with pytest.raises(ValueError):
        checker.public_target(public)


def test_money_difference_does_not_receive_implicit_period_supplement():
    checker, public = fixture()
    public["quantity_contract"]["unit"] = "million USD"
    with pytest.raises(ValueError, match="supplement only public percent"):
        checker.public_target(public)


def test_missing_explicit_current_scope_is_not_repaired_from_sources():
    checker, public = fixture()
    public["question"] = (
        "What was the year-over-year company-defined free cash flow change "
        "in 2025-05-31 in percent?"
    )
    with pytest.raises(ValueError, match="one explicit public current annual period"):
        checker.public_target(public)


def test_existing_two_endpoint_domain_remains_on_original_auditor_path():
    checker, public = fixture()
    public["question"] = (
        "What was the company-defined free cash flow change from 2024-05-31 "
        "to 2025-05-31? Report in percent."
    )
    assert checker.public_target(public) == Decimal(100) * Decimal(-12201) / Decimal(11807)
    assert checker.supplemented == []


def test_sidecar_must_not_be_written_inside_sealed_root(tmp_path):
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    with pytest.raises(ValueError, match="sidecar outside sealed root"):
        module.save(sealed / "audit.json", {"status": "FAIL"}, sealed)
    assert not (sealed / "audit.json").exists()
