"""New finite cash-after-dividends source-layout controls; no historical re-extraction."""

import pytest
from lxml import html

from trusted_synthesis.experiments.finance_qa_vnext_task_build import issuer_tables as tables
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import sha

QUOTE = (
    "Free cash flow is defined as cash provided by operating activities less cash used "
    "in investing activities and dividends paid."
)


def document(*, cover="December 31, 2024", unit="Millions", quote=QUOTE, extra=""):
    return (
        f"<html><p>FORM 10-K For the fiscal year ended {cover}</p><p>{quote}</p>"
        f"<table><tr><td>{unit}</td><td>2024</td><td>2023</td>{extra}</tr>"
        "<tr><td>Cash provided by operating activities</td><td>$100</td><td>$80</td></tr>"
        "<tr><td>Cash used in investing activities</td><td>(20)</td><td>(10)</td></tr>"
        "<tr><td>Dividends paid</td><td>(30)</td><td>(20)</td></tr>"
        "<tr><td>Free cash flow</td><td>$50</td><td>$50</td></tr></table></html>"
    )


def structure(value):
    dom = html.fromstring(value)
    return tables.table_structure(dom.xpath("//table")[0], tables.text(dom))


def test_literal_cover_and_complete_definition_not_universal_FCF():
    result = structure(document())
    assert [row["period_end"] for row in result["headers"]] == ["2024-12-31", "2023-12-31"]
    assert result["definition_quote"] == QUOTE
    assert result["header_period_resolution"][
        "native_same_accession_annual_CFO_confirmation_required"
    ]
    assert len(result["selected_rows"]) == 4
    for header in result["headers"]:
        values = [
            tables.row_amount(
                result["rows"][r],
                header,
                year_headers=result["headers"],
                header_row=result["rows"][header["row"]],
            )[0]
            for r in result["selected_rows"]
        ]
        assert sum(values[:-1]) == values[-1]


def test_unique_visible_cover_after_long_inline_XBRL_metadata():
    source = document().replace("<html>", "<html><div>" + "hidden metadata " * 10000 + "</div>")
    result = structure(source)
    assert result["header_period_resolution"]["cover_text_start"] > 18000


@pytest.mark.parametrize(
    "source",
    [
        document().replace("FORM 10-K", "OTHER DOCUMENT"),
        document().replace("</html>", "<p>For the fiscal year ended December 31, 2024</p></html>"),
    ],
)
def test_no_arbitrary_selection_among_covers_or_missing_form(source):
    with pytest.raises(ValueError):
        structure(source)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cover": "September 30, 2024"},
        {"cover": "December 31, 2023"},
        {"unit": "Thousands"},
        {"unit": "Millions of euros"},
        {"extra": "<td>Change %</td>"},
        {"quote": QUOTE.replace("and dividends paid", "")},
        {"quote": QUOTE.replace("less", "plus")},
    ],
)
def test_unsupported_scope_scale_or_component_definition_rejected(kwargs):
    with pytest.raises(ValueError):
        structure(document(**kwargs))


def fixture(root):
    relative = (
        "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/test/"
        "cik=0000100885/form=10-K/accession=0000100885-25-000042/report.htm"
    )
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(document())
    raw = {
        "storage_uri": relative,
        "raw_object_id": "raw-test",
        "original_url": "https://example.test",
        "content_size_bytes": path.stat().st_size,
        "content_sha256": sha(path),
    }
    source = {
        "entity": {"entity_id": "UNP_US", "cik": "100885"},
        "raw_object": raw,
        "document": {
            "document_id": "original-test",
            "period_end": "2024-12-31",
            "filing_date": "2025-02-07",
        },
    }
    native = [
        {
            "metric_id": tables.CFO,
            "record": {"start": f"{year}-01-01", "end": f"{year}-12-31", "val": value},
            "all_equal_source_occurrences": [
                {"record": {"accn": "0000100885-25-000042", "filed": "2025-02-07"}}
            ],
        }
        for year, value in ((2024, 100_000_000), (2023, 80_000_000))
    ]
    return source, native


def test_actual_same_filing_USD_anchor_required(tmp_path):
    source, native = fixture(tmp_path)
    good = tables.parse_document(tmp_path, source, native)
    assert len(good["observations"]) == 2 and not good["failures"]
    for row in native:
        row["all_equal_source_occurrences"][0]["record"]["accn"] = "different-filing"
    rejected = tables.parse_document(tmp_path, source, native)
    assert not rejected["observations"]
    assert {x["reason"] for x in rejected["failures"]} == {
        "issuer.same_filing_native_USD_CFO_anchor"
    }


def test_year_heading_cannot_override_actual_52_week_endpoint(tmp_path):
    source, native = fixture(tmp_path)
    for row in native:
        row["record"]["end"] = row["record"]["end"][:4] + "-12-29"
    result = tables.parse_document(tmp_path, source, native)
    assert not result["observations"]


def test_matching_closure_does_not_override_CFO_scale(tmp_path):
    source, native = fixture(tmp_path)
    for row in native:
        row["record"]["val"] //= 1000
    result = tables.parse_document(tmp_path, source, native)
    assert not result["observations"]
