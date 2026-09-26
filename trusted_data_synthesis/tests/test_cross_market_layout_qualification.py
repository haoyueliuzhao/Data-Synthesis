"""Synthetic PDF words only; no original PDF or model calls."""

from copy import deepcopy

import cross_market_layout_qualification_20260926 as m
import pytest


def word(text, x, y, width=None):
    return dict(
        text=text,
        x0=x,
        x1=x + (width if width is not None else len(text) * 4),
        y0=y,
        y1=y + 10,
        block=0,
        line=0,
        word=0,
    )


def geometry(*, current=2024, previous=2023, footer=False, source="English"):
    title = "Consolidated income statement" if source == "English" else "合并利润表"
    annual = (
        f"For the year ended 31 December {current}" if source == "English" else f"{current}年1—12月"
    )
    unit = "HK$ million" if source == "English" else "单位：人民币元"
    words = [
        word(title, 50, 40),
        word(annual, 50, 60),
        word(unit, 350, 80),
        word(str(current), 380, 100),
        word(str(previous), 460, 100),
    ]
    labels = (
        ("Revenue", "Cost of sales", "Gross profit")
        if source == "English"
        else ("营业收入", "营业成本", "毛利")
    )
    for index, (label, values) in enumerate(
        zip(labels, (("100", "90"), ("(80)", "(70)"), ("20", "20")), strict=True)
    ):
        words.extend(
            [
                word(label, 50, 125 + 20 * index),
                word(values[0], 375, 125 + 20 * index, 25),
                word(values[1], 455, 125 + 20 * index, 25),
            ]
        )
    if footer:
        words.insert(1, word("80", 290, 810))
    return dict(
        id="geometry:id",
        pages=[dict(page_number=1, width=600, height=850, rotation=0, words=words)],
    )


def candidate(metric="revenue"):
    labels = {
        "revenue": "Revenue",
        "cost_of_revenue": "Cost of sales",
        "gross_profit": "Gross profit",
    }
    return dict(
        candidate_id="c1",
        raw_object_id="r1",
        matched_metric_id=metric,
        source_field_name=labels[metric],
        financial_scope_type="consolidated_entity",
        statement_type="income_statement",
        period_start="2024-01-01",
        period_end="2024-12-31",
        currency="HKD",
        value_scale="million",
        unit="million HKD",
        value="100",
        _raw_value_text="100",
        _period_source_page=1,
        _unit_source_page=1,
        _statement_source_page=1,
        page_number=1,
        column_index=1,
        extraction_metadata=dict(
            statement_title="INFERRED bad cache title",
            period_inference="audited_statement_section_period",
        ),
    )


def doc():
    return dict(
        raw_object_id="r1",
        sha256="a" * 64,
        security_id="hkex:00001",
        source_id="hkex_disclosures",
        original_url="https://official.example/report.pdf",
        publish_date="2025-03-01",
    )


def review():
    return dict(mechanical_checks_passed=True, failures=[])


def test_geometry_reorders_stream_and_ignores_footer_page_number():
    g = geometry(footer=True)
    g["pages"][0]["words"].reverse()
    result = m.certify(candidate(), g)
    assert [o["end"] for o in result["observations"]] == ["2024-12-31", "2023-12-31"]
    assert result["old_parser_period_amount_not_used_as_truth_or_veto"]
    assert result["prior_locators"]["statement_title"].startswith("INFERRED")
    assert not result["resolved_locators"]["statement_title"].startswith("INFERRED")


def test_original_candidate_not_mutated_and_bad_cached_period_value_rederived():
    c = candidate()
    c.update(
        period_start="2021-01-01",
        period_end="2021-12-31",
        value="999",
        _raw_value_text="999",
        currency="USD",
    )
    original = deepcopy(c)
    facts = m.financial_facts(c, doc(), review(), geometry())
    assert c == original
    assert [f["record"]["val"] for f in facts] == ["100000000", "90000000"]
    assert all(f["currency"] == "HKD" for f in facts)
    assert facts[0]["original_candidate_bindings"][0]["value"] == "999"
    assert facts[0]["source_rederived_binding"]["value"] == "100"


def test_same_original_row_multiple_parser_anchors_same_fact_ids():
    c = candidate()
    first = m.financial_facts(c, doc(), review(), geometry())
    c.update(
        candidate_id="c2",
        period_start="2023-01-01",
        period_end="2023-12-31",
        value="90",
        _raw_value_text="90",
    )
    second = m.financial_facts(c, doc(), review(), geometry())
    assert [f["fact_id"] for f in first] == [f["fact_id"] for f in second]


def test_signed_cost_retained_and_old_task_relation_still_exact():
    facts = {
        metric: m.financial_facts(candidate(metric), doc(), review(), geometry())[0]
        for metric in ("revenue", "cost_of_revenue", "gross_profit")
    }
    assert facts["cost_of_revenue"]["record"]["val"] == "-80000000"
    assert (
        m.old.signed_relation(facts["gross_profit"], facts["revenue"], facts["cost_of_revenue"])[
            "cost_coefficient"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "mode",
    [
        "parent",
        "year2026",
        "three_columns",
        "same_year",
        "restated",
        "multiple_currency",
        "unknown_scale",
        "wrong_alignment",
        "extra_money",
        "percent",
        "dash",
        "net_attributable",
    ],
)
def test_unresolved_evidence_stays_rejected(mode):
    g, c = geometry(), candidate()
    words = g["pages"][0]["words"]
    if mode == "parent":
        words[0]["text"] = "Company income statement"
    elif mode == "year2026":
        g = geometry(current=2026, previous=2025)
    elif mode == "three_columns":
        words.append(word("2022", 530, 100))
    elif mode == "same_year":
        words[4]["text"] = "2024"
    elif mode == "restated":
        words.append(word("restated", 455, 112))
    elif mode == "multiple_currency":
        words[2]["text"] = "HK$ million RMB million"
    elif mode == "unknown_scale":
        words[2]["text"] = "HK$"
    elif mode == "wrong_alignment":
        words[6].update(x0=250, x1=275)
    elif mode == "extra_money":
        words.append(word("999", 530, 125))
    elif mode in {"percent", "dash"}:
        words[6]["text"] = "100%" if mode == "percent" else "—"
    elif mode == "net_attributable":
        c.update(
            matched_metric_id="net_income",
            source_field_name="Profit attributable to owners of the Company",
        )
    with pytest.raises(ValueError):
        m.financial_facts(c, doc(), review(), g)


def test_explicit_notes_column_only_excludes_positioned_note_integer():
    g = geometry()
    g["pages"][0]["words"].extend([word("Notes", 295, 100), word("6", 300, 125)])
    result = m.certify(candidate(), g)
    assert result["excluded_note_words"][0]["text"] == "6"
    g["pages"][0]["words"] = [w for w in g["pages"][0]["words"] if w["text"] != "Notes"]
    with pytest.raises(ValueError, match="certified_note"):
        m.certify(candidate(), g)


def test_relative_chinese_columns_require_actual_annual_header():
    g = geometry(source="Chinese")
    words = g["pages"][0]["words"]
    words[3]["text"], words[4]["text"] = "本年金额", "上年金额"
    c = candidate()
    c.update(source_field_name="营业收入", currency="CNY", value_scale="元")
    result = m.certify(c, g)
    assert result["observations"][1]["end"] == "2023-12-31"
    words[1]["text"] = "年度报告"
    with pytest.raises(ValueError, match="annual_date_missing"):
        m.certify(c, g)


def test_continuation_rebinds_wrong_old_period_page_but_checks_intervening_statement():
    g = geometry()
    header_words = [w for w in g["pages"][0]["words"] if w["y0"] < 125]
    data_words = [w for w in g["pages"][0]["words"] if w["y0"] >= 125]
    g["pages"][0]["words"] = header_words
    g["pages"].append(dict(page_number=2, words=data_words, width=600, height=850))
    c = candidate()
    c.update(page_number=2, _period_source_page=9, _statement_source_page=9)
    assert m.certify(c, g)["resolved_locators"]["period_page"] == 1
    g["pages"][1]["words"].append(word("Company income statement", 50, 40))
    with pytest.raises(ValueError, match="consolidated_statement"):
        m.certify(c, g)


def test_geometric_line_clustering_not_transitive():
    page = dict(words=[word("a", 1, 10), word("b", 5, 12), word("c", 8, 14)])
    assert len(m.lines_for_page(page)) == 2


def test_original_mechanical_failure_preserved_not_used_as_false_gold():
    facts = m.financial_facts(
        candidate(),
        doc(),
        dict(mechanical_checks_passed=False, failures=["label_in_cached_table_row"]),
        geometry(),
    )
    assert facts[0]["original_candidate_bindings"][0]["prior_mechanical_review_passed"] is False


def test_conflicting_within_report_observations_not_silently_coalesced():
    facts = m.financial_facts(candidate(), doc(), review(), geometry())
    conflict = deepcopy(facts[0])
    conflict["fact_id"] = "other"
    conflict["record"]["val"] = "999"
    usable, conflicts = m.old.unique_facts([*facts, conflict])
    assert len(usable) == 1 and len(conflicts) == 1


def test_native_printed_hk_m_abbreviation():
    g = geometry()
    g["pages"][0]["words"][2]["text"] = "HK$M"
    assert m.certify(candidate(), g)["unit"]["scale"] == 1000000


def test_note_plus_one_value_and_one_dash_never_becomes_two_year_amounts():
    g = geometry()
    g["pages"][0]["words"].extend([word("Notes", 295, 100), word("6", 300, 125)])
    g["pages"][0]["words"][7]["text"] = "—"
    with pytest.raises(ValueError, match="cardinality"):
        m.certify(candidate(), g)


def test_document_pass_deduplicates_rows_and_accounts_for_every_old_candidate(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "financial")
    descriptor = doc()
    c1, c2, rejected = candidate(), candidate(), candidate()
    c2["candidate_id"] = "c2"
    rejected.update(candidate_id="c3", matched_metric_id="total_assets")
    extraction = m.base.record(
        "PDF_extraction_result", document=descriptor, parsed=dict(candidates=[c1, c2, rejected])
    )
    audit = m.base.record(
        "cross_market_PDF_evidence_audit",
        document=descriptor,
        candidate_reviews=[
            dict(review(), candidate_id=c["candidate_id"]) for c in (c1, c2, rejected)
        ],
    )
    geo = geometry()
    del geo["id"]
    geo = m.base.record("cross_market_original_PDF_geometry", document=descriptor, **geo)
    text = m.base.record(
        "cross_market_original_PDF_page_text",
        raw_sha256=descriptor["sha256"],
        pages=[dict(page=1, text="Consolidated income statement")],
    )
    item = dict(document=descriptor)
    for key, data in (
        ("extraction", extraction),
        ("audit", audit),
        ("geometry", geo),
        ("text_bundle", text),
    ):
        path = tmp_path / (key + ".json")
        m.base.write(path, data)
        item[key] = m.old.ref(path)
    result = m.document_qualify(dict(id="protocol:test"), item)
    assert len(result["qualified_facts"]) == 2
    assert len(result["rejected_candidates"]) == 1
    assert len(result["candidate_adjudications"]) == 3
    assert all(len(f["original_candidate_bindings"]) == 2 for f in result["qualified_facts"])
    assert m.document_qualify(dict(id="protocol:test"), item)["id"] == result["id"]


def test_reserved_unsettled_document_does_not_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "financial")
    descriptor = doc()
    key = m.base.sha(descriptor["raw_object_id"])[:24]
    m.base.write(m.RAW / "document_attempts" / (key + ".json"), dict(attempt=1))
    with pytest.raises(ValueError, match="unsettled_no_auto_retry"):
        m.document_qualify(dict(id="test"), dict(document=descriptor))


def test_header_stops_at_unregistered_cn_balance_first_row_before_body_currency():
    g = geometry(source="Chinese")
    words = g["pages"][0]["words"]
    words[0]["text"] = "合并资产负债表"
    words[5]["text"] = "货币资金"
    words.append(word("其中：美元存款", 50, 140))
    lines = m.lines_for_page(g["pages"][0])
    anchor = m.title_spans(1, lines)[0]
    header = m.header_lines(anchor, {1: lines})
    assert not any("货币资金" in line["text"] or "美元" in line["text"] for line in header)
    assert m.unit_certificate(candidate(), header)["currency"] == "CNY"


def test_note_annotation_must_be_positioned_in_note_column():
    g = geometry()
    words = g["pages"][0]["words"]
    words.extend([word("Notes", 295, 100), word("6(a)", 300, 125)])
    assert m.certify(candidate(), g)
    words[-1].update(x0=525, x1=545)
    with pytest.raises(ValueError, match="not_in_notes_column"):
        m.certify(candidate(), g)
