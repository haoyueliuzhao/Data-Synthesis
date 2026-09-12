"""New cover-region revision controls; previous stage controls remain unchanged."""

import copy
import importlib.util
from pathlib import Path

import pytest
from lxml import html

from trusted_synthesis.experiments.finance_qa_vnext_task_build import issuer_tables as producer
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import sha

AUDIT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_eval_readiness_increment.py"
)
SPEC = importlib.util.spec_from_file_location("revision_cover_independent_audit", AUDIT_PATH)
auditor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auditor)

LEGAL = "REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934"
QUOTE = (
    "Free cash flow is defined as cash provided by operating activities "
    "less cash used in investing activities and dividends paid."
)


def cover(
    *, year=2024, date_html=None, annual="☒", transition="☐", company="UNION PACIFIC CORPORATION"
):
    when = date_html or f"December 31, {year}"
    return (
        "<div><p>UNITED STATES SECURITIES AND EXCHANGE COMMISSION</p>"
        "<p>WASHINGTON, D.C. 20549</p><p>FORM 10-K</p><p>(Mark One)</p>"
        f"<p>{annual} ANNUAL {LEGAL}</p><p>For the fiscal year ended {when}</p>"
        f"<p>OR {transition} TRANSITION {LEGAL}</p>"
        "<p>For the transition period from __________ to ____________</p>"
        f"<p>Commission File Number 1-6075</p><p>{company}</p>"
        "<p>(Exact name of registrant as specified in its charter)</p></div>"
    )


def reconciliation(*, heading=2024, cfi="(20)", dividend="(30)", total="50", duplicate_total=False):
    extra = "<tr><td>Free cash flow</td><td>50</td><td>50</td></tr>" if duplicate_total else ""
    return (
        f"<p>{QUOTE}</p><table><tr><td>Millions</td><td>{heading}</td><td>{heading - 1}</td></tr>"
        "<tr><td>Cash provided by operating activities</td><td>$100</td><td>$80</td></tr>"
        f"<tr><td>Cash used in investing activities</td><td>{cfi}</td><td>(10)</td></tr>"
        f"<tr><td>Dividends paid</td><td>{dividend}</td><td>(20)</td></tr>"
        f"<tr><td>Free cash flow</td><td>{total}</td><td>$50</td></tr>{extra}</table>"
    )


def document(*, prefix="", suffix="", cover_options=None, table_options=None):
    return html.fromstring(
        "<html><body>"
        + prefix
        + cover(**(cover_options or {}))
        + reconciliation(**(table_options or {}))
        + suffix
        + "</body></html>"
    )


@pytest.mark.parametrize(
    "when",
    [
        "December 31, 2024",
        "December 31 , 2024",
        "December\n31\t,\n2024",
        "December <span>31</span> <span>,</span> <span>2024</span>",
        "December <span>31 </span><span>, </span><span>2024</span>",
    ],
)
@pytest.mark.parametrize(
    "prefix", ["", "<div style='display:none'>" + "hidden metadata " * 10000 + "</div>"]
)
def test_actual_SEC_cover_accepts_DOM_whitespace_and_arbitrary_hidden_prefix(when, prefix):
    tree = document(prefix=prefix, cover_options={"date_html": when})
    evidence = producer.annual_report_cover(tree)
    independent = auditor.verify_cover_evidence(tree, evidence)
    assert independent["period_end"] == "2024-12-31"
    assert evidence["rule"] == "sec_UNP_annual_cover_region_and_native_CFO_v2"
    assert evidence["cover_region"]["selection_uses_archived_year_known_offset_or_amount"] is False
    assert evidence["native_same_accession_annual_CFO_confirmation_required"]
    original = producer.text(tree)
    assert (
        original[evidence["cover_text_start"] : evidence["cover_text_end"]]
        == evidence["cover_quote"]
    )
    assert bool(evidence["cover_region"]["dom_text_segments"])


@pytest.mark.parametrize(
    "body",
    [
        "As reported in our Annual Report on Form 10-K "
        "for the fiscal year ended December 31, 2023.",
        "We adopted the ASU effective for fiscal year ended December 31, 2024.",
        "Our Form 10-K for the fiscal year ended December 31, 2023. " * 4,
    ],
)
def test_body_references_do_not_enter_true_cover_uniqueness(body):
    tree = document(prefix=f"<p>{body}</p>", suffix=f"<p>{body}</p>")
    evidence = producer.annual_report_cover(tree)
    assert auditor.verify_cover_evidence(tree, evidence)["period_end"] == "2024-12-31"
    assert evidence["cover_text_start"] > len(body)


@pytest.mark.parametrize(
    "mutation",
    [
        "FORM_10Q",
        "no_commission",
        "no_annual_legal",
        "no_transition_legal",
        "no_registration",
        "other_issuer",
        "annual_unchecked",
        "transition_checked",
        "September",
        "duplicate_cover",
        "only_body_reference",
        "only_fiscal_literal",
        "fake_padded_FORM_context",
    ],
)
def test_semantically_incomplete_or_ambiguous_cover_is_rejected(mutation):
    value = cover()
    if mutation == "FORM_10Q":
        value = value.replace("FORM 10-K", "FORM 10-Q")
    elif mutation == "no_commission":
        value = value.replace("SECURITIES AND EXCHANGE COMMISSION", "PRIVATE FINANCIAL REPORT")
    elif mutation == "no_annual_legal":
        value = value.replace("ANNUAL " + LEGAL, "ANNUAL REPORT")
    elif mutation == "no_transition_legal":
        value = value.replace("TRANSITION " + LEGAL, "TRANSITION REPORT")
    elif mutation == "no_registration":
        value = value.replace("Commission File Number 1-6075", "Reference")
    elif mutation == "other_issuer":
        value = cover(company="ORACLE CORPORATION")
    elif mutation == "annual_unchecked":
        value = cover(annual="☐")
    elif mutation == "transition_checked":
        value = cover(transition="☒")
    elif mutation == "September":
        value = cover(date_html="September 30, 2024")
    elif mutation == "duplicate_cover":
        value = cover() + cover()
    elif mutation == "only_body_reference":
        value = (
            "<p>See our Annual Report on Form 10-K for the fiscal year ended December 31, 2024.</p>"
        )
    elif mutation == "only_fiscal_literal":
        value = "<p>FORM 10-K For the fiscal year ended December 31, 2024</p>"
    else:
        value = (
            "<p>FORM 10-K</p>"
            + "padding " * 300
            + "<p>For the fiscal year ended December 31, 2024</p>"
        )
    tree = html.fromstring("<html><body>" + value + "</body></html>")
    with pytest.raises(ValueError):
        producer.annual_report_cover(tree)
    with pytest.raises(ValueError):
        auditor.independent_annual_cover(tree)


@pytest.mark.parametrize(
    "mutation",
    [
        "date",
        "region",
        "node",
        "slot",
        "raw_span",
        "raw_text",
        "document_span",
        "missing_segment",
        "extra_field",
    ],
)
def test_independent_cover_reopens_original_DOM_and_rejects_claim_mutation(mutation):
    tree = document(cover_options={"date_html": "December <span>31</span> , <span>2024</span>"})
    claimed = copy.deepcopy(producer.annual_report_cover(tree))
    segment = claimed["cover_region"]["dom_text_segments"][0]
    if mutation == "date":
        claimed["period_end"] = "2023-12-31"
    elif mutation == "region":
        claimed["cover_region"]["normalized_text_start"] += 1
    elif mutation == "node":
        segment["element_xpath"] = "/html/body/nonexistent"
    elif mutation == "slot":
        segment["slot"] = "tail"
    elif mutation == "raw_span":
        segment["raw_character_span"][0] += 1
    elif mutation == "raw_text":
        segment["raw_text"] += " tampered"
    elif mutation == "document_span":
        segment["normalized_document_span"][0] += 1
    elif mutation == "missing_segment":
        claimed["cover_region"]["dom_text_segments"].pop(1)
    else:
        claimed["trusted_archived_year"] = 2024
    with pytest.raises(ValueError):
        auditor.verify_cover_evidence(tree, claimed)


def test_independent_cover_does_not_call_producer(monkeypatch):
    tree = document()
    claimed = producer.annual_report_cover(tree)

    def forbidden(*args, **kwargs):
        raise AssertionError("producer invoked by independent source audit")

    monkeypatch.setattr(producer, "annual_report_cover", forbidden)
    monkeypatch.setattr(producer, "_cover_dom_segments", forbidden)
    monkeypatch.setattr(producer, "table_structure", forbidden)
    assert auditor.verify_cover_evidence(tree, claimed)["period_end"] == "2024-12-31"


def test_new_header_evidence_binds_original_table_without_changing_definition():
    tree = document(cover_options={"date_html": "December <span>31</span> , <span>2024</span>"})
    table = tree.xpath("//table")[0]
    actual = producer.table_structure(table, producer.text(tree))
    headers, selected, labels, independent = auditor.unp_headers(
        auditor.base.original_grid(table), auditor.base.normalized_text(tree), document_tree=tree
    )
    assert actual["headers"] == headers and actual["selected_rows"] == selected
    assert actual["labels"] == labels and actual["definition_quote"] == QUOTE
    assert auditor.verify_cover_evidence(tree, actual["header_period_resolution"]) == independent


def test_nonunique_FCF_total_and_heading_year_conflict_remain_rejected():
    for options, reason in (
        ({"duplicate_total": True}, "one_reported_FCF_total_row"),
        ({"heading": 2023}, "cover_and_latest_heading"),
    ):
        tree = document(table_options=options)
        with pytest.raises(ValueError, match=reason):
            producer.table_structure(tree.xpath("//table")[0], producer.text(tree))


@pytest.mark.parametrize("mutation", ["none", "native_date", "accession", "CFO_scale", "closure"])
def test_synthetic_complete_parse_keeps_all_original_financial_gates(tmp_path, mutation):
    tree = document(table_options={"total": "49"} if mutation == "closure" else None)
    relative = (
        "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/test/"
        "cik=0000100885/form=10-K/accession=0000100885-25-000042/report.htm"
    )
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(html.tostring(tree))
    source = {
        "entity": {"entity_id": "UNP_US", "cik": "100885"},
        "raw_object": {
            "storage_uri": relative,
            "raw_object_id": "raw-synthetic",
            "original_url": "https://example.test/synthetic-unp-report",
            "content_sha256": sha(path),
            "content_size_bytes": path.stat().st_size,
        },
        "document": {
            "document_id": "synthetic",
            "period_end": "2024-12-31",
            "filing_date": "2025-02-07",
        },
    }
    native = [
        {
            "metric_id": producer.CFO,
            "record": {"start": f"{year}-01-01", "end": f"{year}-12-31", "val": value},
            "all_equal_source_occurrences": [
                {"record": {"accn": "0000100885-25-000042", "filed": "2025-02-07"}}
            ],
        }
        for year, value in ((2024, 100000000), (2023, 80000000))
    ]
    if mutation == "native_date":
        for row in native:
            row["record"]["end"] = row["record"]["end"][:4] + "-12-29"
    elif mutation == "accession":
        for row in native:
            row["all_equal_source_occurrences"][0]["record"]["accn"] = "different-filing"
    elif mutation == "CFO_scale":
        for row in native:
            row["record"]["val"] //= 1000
    result = producer.parse_document(tmp_path, source, native)
    if mutation == "none":
        assert len(result["observations"]) == 2 and not result["failures"]
    elif mutation == "closure":
        assert len(result["observations"]) == 1
        assert any(
            row["reason"] == "issuer.full_definition_table_does_not_close"
            for row in result["failures"]
        )
    else:
        assert not result["observations"]
