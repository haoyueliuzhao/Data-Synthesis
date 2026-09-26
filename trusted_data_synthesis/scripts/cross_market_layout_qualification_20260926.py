"""Prospective geometric adjudication of the original 9,513 PDF candidates.

No PDF, parser, network, model or scoring calls. A separate bounded acquisition
supplies verbatim positioned words. This module never changes old candidates.
It independently rederives both observations of a candidate-anchored source row
only when the original statement, two year columns and native currency/scale
are explicit. Before/after bindings and new identities are retained. The old
parser amount/period is not authoritative gold or a veto on clear source words.
"""

import argparse
import re
import subprocess
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import cross_market_financial_header_revision_20260926 as previous
import cross_market_financial_qualification_20260926 as old
import register_cross_market_evidence_supplement_20260926 as umbrella

base = old.base
RAW = base.RAW / "original_evidence_revision_02" / "financial"
GEOMETRY = base.RAW / "original_evidence_revision_02" / "geometry"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_layout_qualification_20260926.py"
MAX_HEADER_DISTANCE = 4
LINE_TOLERANCE = 3.0
X_TOLERANCE = 38.0
RESTATED = re.compile(r"restated|re[- ]?presented|重述|重列|调整后|調整後", re.I)
TITLE = re.compile(
    r"(?:合并|合併|母公司|公司)?(?:资产负债表|資產負債表|利润表|利潤表|"
    r"综合收益表|綜合收益表|现金流量表|現金流量表)|"
    r"(?:(?:consolidated|separate|parentcompany|company))?"
    r"(?:(?:statementsof|statementof)(?:profitorloss|income|comprehensiveincome|"
    r"cashflows?|financialposition)|incomestatements?|cashflowstatements?|"
    r"balancesheets?|profitandlossaccounts?)"
)
PARENT = re.compile(r"母公司|parentcompany|separate(?:statement|financial)|companystatement")
CURRENCY = {
    "CNY": re.compile(r"人民币|人民幣|rmb|cny|renminbi"),
    "HKD": re.compile(r"港币|港幣|hk\$|hkd|hongkongdollars?"),
    "USD": re.compile(r"美元|usd|us\$|unitedstatesdollars?"),
}
RELATIVE_YEAR = {
    "本年金额": 0,
    "本年金額": 0,
    "本期金额": 0,
    "本期金額": 0,
    "上年金额": -1,
    "上年金額": -1,
    "上期金额": -1,
    "上期金額": -1,
}


def fail(condition, reason):
    if not condition:
        raise ValueError(reason)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "layout_output_root")
    base.write(path, value)


def lines_for_page(page):
    """Geometry order, independent of PyMuPDF's stream/block order.

    Cluster by vertical centre, at most three PDF points; never merge adjacent
    statement rows via a transitive chain. Word indices preserve the raw locator.
    """
    lines = []
    for index, word in sorted(
        enumerate(page["words"]), key=lambda r: ((r[1]["y0"] + r[1]["y1"]) / 2, r[1]["x0"], r[0])
    ):
        centre = (word["y0"] + word["y1"]) / 2
        if not lines or abs(centre - lines[-1]["anchor_y"]) > LINE_TOLERANCE:
            lines.append(dict(anchor_y=centre, words=[]))
        lines[-1]["words"].append(dict(word, original_word_index=index))
    for index, line in enumerate(lines):
        line["words"].sort(key=lambda w: (w["x0"], w["y0"], w["original_word_index"]))
        line.update(
            line_index=index,
            y0=min(w["y0"] for w in line["words"]),
            y1=max(w["y1"] for w in line["words"]),
            text=" ".join(w["text"] for w in line["words"]),
        )
    return lines


def statement_type(title):
    title = old.norm(title)
    if "现金流量" in title or "現金流量" in title or "cashflow" in title:
        return "cash_flow"
    if any(x in title for x in ("资产负债", "資產負債", "financialposition", "balancesheet")):
        return "balance_sheet"
    return "income_statement"


def title_spans(page, lines):
    found = []
    for start in range(len(lines)):
        for width in range(1, 4):
            chunk = lines[start : start + width]
            joined = old.norm(" ".join(line["text"] for line in chunk))
            match = TITLE.search(joined)
            if not match:
                continue
            # A footnote sentence that mentions a statement is not its heading.
            prefix = joined[: match.start()]
            if prefix and not re.fullmatch(r"[\d、.()（）:：]+", prefix):
                continue
            if width > 1 and TITLE.search(old.norm(" ".join(x["text"] for x in chunk[1:]))):
                continue
            found.append(
                dict(
                    page=page,
                    start_line=start,
                    end_line=start + width,
                    y0=chunk[0]["y0"],
                    y1=chunk[-1]["y1"],
                    text="\n".join(x["text"] for x in chunk),
                    statement_type=statement_type(match.group(0)),
                    consolidated=bool(re.search(r"consolidated|合并|合併", match.group(0))),
                    parent=bool(PARENT.search(joined)),
                )
            )
            break
    # Wrapped titles can also match from their second line. Prefer the explicit
    # consolidated first-line span, never count the shorter suffix as a boundary.
    return [
        v
        for v in found
        if not any(q is not v and q["start_line"] < v["start_line"] < q["end_line"] for q in found)
    ]


def _amount(word):
    try:
        return old.raw_decimal(word["text"])
    except (ValueError, InvalidOperation):
        return None


def label_rows(c, lines):
    label = old.norm(c["source_field_name"])
    matches = []
    for index, line in enumerate(lines):
        words = line["words"]
        for stop in range(1, len(words) + 1):
            prefix = old.norm(" ".join(w["text"] for w in words[:stop]))
            if prefix != label and not re.fullmatch(
                r"[一二三四五六七八九十0-9、.()（）:：]+" + re.escape(label), prefix
            ):
                continue
            rest = words[stop:]
            if any(_amount(w) is not None for w in rest):
                matches.append(
                    dict(
                        line=line,
                        label_words=words[:stop],
                        rest=rest,
                        row_start_line=index,
                        row_end_line=index,
                    )
                )
        # Native wrapped cash-flow labels can occupy two immediately adjacent
        # lines. Only combine a text-only first line with a value-bearing second.
        if index and not any(_amount(w) is not None for w in lines[index - 1]["words"]):
            previous_words = lines[index - 1]["words"]
            if line["y0"] - lines[index - 1]["y1"] > 8:
                continue
            for stop in range(1, len(words) + 1):
                prefix = old.norm(" ".join(w["text"] for w in previous_words + words[:stop]))
                if prefix == label and any(_amount(w) is not None for w in words[stop:]):
                    matches.append(
                        dict(
                            line=line,
                            label_words=previous_words + words[:stop],
                            rest=words[stop:],
                            row_start_line=index - 1,
                            row_end_line=index,
                        )
                    )
    return matches


def locate_statement(c, rows, title_map, line_map):
    page = c["page_number"]
    valid = []
    for row in rows:
        preceding = [
            t
            for p, titles in title_map.items()
            if page - MAX_HEADER_DISTANCE <= p <= page
            for t in titles
            if p < page or t["end_line"] <= row["row_start_line"]
        ]
        if not preceding:
            continue
        anchor = max(preceding, key=lambda t: (t["page"], t["end_line"]))
        if anchor["parent"] or not anchor["consolidated"]:
            continue
        if anchor["statement_type"] != c["statement_type"]:
            continue
        fail(
            all(p in line_map for p in range(anchor["page"], page + 1)),
            "geometry_scope_intervening_page_missing",
        )
        valid.append((row, anchor))
    fail(bool(valid), "geometry_consolidated_statement_and_row_not_bound")
    fail(len(valid) == 1, "geometry_multiple_same_label_rows_unresolved")
    return valid[0]


def _data_line(line):
    normalized = old.norm(line["text"])
    numbers = [w for w in line["words"] if _amount(w) is not None]
    if previous.DATA_LABEL.search(normalized) and numbers:
        return True
    # The boundary is not limited to our 15 task metrics. For example Chinese
    # balance sheets often start with 货币资金, and currencies mentioned in later
    # accounts/notes must not be borrowed as the statement-header currency.
    if (
        len(numbers) < 2
        or old.EN_END.search(line["text"])
        or old.EN_END_MONTH_FIRST.search(line["text"])
    ):
        return False
    text_words = [w for w in line["words"] if _amount(w) is None]
    if not text_words:
        return False
    if all(
        old.norm(w["text"]) in {"note", "notes", "附注", "附註", "项目", "項目"} for w in text_words
    ) and all(re.fullmatch(r"20\d{2}", old.norm(w["text"])) for w in numbers):
        return False
    # A monetary row has a printed semantic label to the left of its columns.
    return any(
        w["x1"] <= numbers[0]["x0"] and re.search(r"[A-Za-z\u3400-\u9fff]", w["text"])
        for w in text_words
    )


def header_lines(anchor, line_map):
    lines = line_map[anchor["page"]]
    end = len(lines)
    for index in range(anchor["end_line"], len(lines)):
        if _data_line(lines[index]):
            end = index
            break
        normalized = old.norm(lines[index]["text"])
        if TITLE.search(normalized):
            end = index
            break
    fail(end > anchor["end_line"], "geometry_statement_header_empty")
    return lines[anchor["start_line"] : end]


def actual_ends(header, instant):
    text = "\n".join(line["text"] for line in header)
    normalized = old.norm(text)
    fail(
        not old.UNUSUAL_ANNUAL.search(text)
        and not re.search(r"(?:52|53)weeks|[0-9]+个月|[0-9]+個月", normalized),
        "geometry_noncalendar_or_changed_annual_header",
    )
    ends = [
        date(int(y), old.MONTHS[mon.lower()], int(day)) for day, mon, y in old.EN_END.findall(text)
    ]
    ends += [
        date(int(y), old.MONTHS[mon.lower()], int(day))
        for mon, day, y in old.EN_END_MONTH_FIRST.findall(text)
    ]
    for year in re.findall(r"(20\d{2})(?:年度|年1[—－–\-~至]12月)", normalized):
        ends.append(date(int(year), 12, 31))
    if instant:
        for year, month, day in re.findall(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", normalized):
            ends.append(date(int(year), int(month), int(day)))
        for day, mon, year in re.findall(
            r"(?:as\s+at|at)\s+(\d{1,2})\s+(" + "|".join(old.MONTHS) + r")\s+(20\d{2})", text, re.I
        ):
            ends.append(date(int(year), old.MONTHS[mon.lower()], int(day)))
    fail(bool(ends), "geometry_explicit_actual_annual_date_missing")
    fail(len({(x.month, x.day) for x in ends}) == 1, "geometry_conflicting_actual_end_dates")
    return sorted(set(ends)), text


def year_columns(header, ends):
    choices = []
    for line in header:
        columns = []
        for word in line["words"]:
            token = old.norm(word["text"])
            match = re.fullmatch(r"(20\d{2})(?:年度|年)?", token)
            full = re.fullmatch(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", token)
            if match or full:
                year = int((match or full).group(1))
                if full:
                    fail(
                        (int(full.group(2)), int(full.group(3))) == (ends[-1].month, ends[-1].day),
                        "geometry_printed_column_end_date_disagrees",
                    )
                columns.append(dict(word, year=year, year_basis="printed_absolute_year"))
            elif token in RELATIVE_YEAR:
                columns.append(
                    dict(
                        word,
                        year=max(x.year for x in ends) + RELATIVE_YEAR[token],
                        year_basis="printed_relative_column_with_actual_annual_date",
                    )
                )
        if len(columns) >= 2:
            fail(len(columns) == 2, "geometry_more_than_two_year_columns_unresolved")
            fail(
                columns[0]["year"] != columns[1]["year"],
                "geometry_same_year_semantic_subcolumns_unresolved",
            )
            choices.append(columns)
    fail(bool(choices), "geometry_two_printed_year_columns_missing")
    fail(len(choices) == 1, "geometry_multiple_year_header_rows_unresolved")
    return sorted(choices[0], key=lambda w: w["x0"])


def unit_certificate(c, header):
    text = "\n".join(line["text"] for line in header)
    normalized = old.norm(text).replace("’", "'")
    currencies = {currency for currency, regex in CURRENCY.items() if regex.search(normalized)}
    fail(len(currencies) == 1, "geometry_currency_missing_or_multiple")
    scales = set()
    if re.search(
        r"百万元|百萬[元圆圓]|million|\bmn\b|(?:hk\$|us\$|rmb|hkd|usd)m(?=$|[^a-z])", normalized
    ):
        scales.add(1000000)
    if re.search(r"万元|萬元", normalized) and not re.search(r"百万元|百萬元", normalized):
        scales.add(10000)
    if re.search(r"千元|thousand|['’]000|\$000|rmb000|hkd000|usd000", normalized):
        scales.add(1000)
    if not scales and re.search(
        r"单位[:：]?(?:人民币)?元|單位[:：]?(?:人民幣)?元|in(?:hk|us)\$(?=$|[^a-z0-9])|in(?:rmb|hkd|usd)(?=$|[^a-z0-9])",
        normalized,
    ):
        scales.add(1)
    fail(len(scales) == 1, "geometry_native_scale_unresolved")
    fail(
        not previous.COMPLEX_SUBCOLUMNS.search(normalized),
        "geometry_group_company_or_semantic_subcolumns_unresolved",
    )
    return dict(
        currency=next(iter(currencies)),
        scale=next(iter(scales)),
        original_header=text,
        source="actual_statement_geometry_header",
    )


def prepared_geometry(geometry):
    line_map = {p["page_number"]: lines_for_page(p) for p in geometry["pages"]}
    return line_map, {p: title_spans(p, lines) for p, lines in line_map.items()}


def certify(c, geometry, prepared=None):
    line_map, title_map = prepared or prepared_geometry(geometry)
    fail(c["page_number"] in line_map, "geometry_candidate_page_missing")
    rows = label_rows(c, line_map[c["page_number"]])
    row, anchor = locate_statement(c, rows, title_map, line_map)
    header = header_lines(anchor, line_map)
    ends, header_text = actual_ends(header, c["matched_metric_id"] == "cash_and_cash_equivalents")
    fail(not RESTATED.search(header_text), "geometry_restatement_column_pending_review")
    columns = year_columns(header, ends)
    unit = unit_certificate(c, header)
    amounts = [w for w in row["rest"] if _amount(w) is not None]
    other_words = [w for w in row["rest"] if _amount(w) is None]
    other_tokens = [w["text"] for w in other_words]
    note_words = [
        w
        for line in header
        for w in line["words"]
        if old.norm(w["text"]) in {"note", "notes", "附注", "附註", "注", "註"}
    ]
    excluded = []
    if len(amounts) == 3 or (
        amounts
        and len(note_words) == 1
        and amounts[0]["x1"] < columns[0]["x0"] - 15
        and abs(amounts[0]["x1"] - note_words[0]["x1"]) <= X_TOLERANCE
    ):
        note = amounts[0]
        fail(
            len(note_words) == 1
            and re.fullmatch(r"\d+", old.norm(note["text"]))
            and abs(note["x1"] - note_words[0]["x1"]) <= X_TOLERANCE
            and note["x1"] < columns[0]["x0"] - 15,
            "geometry_extra_numeric_column_not_certified_note",
        )
        excluded, amounts = [note], amounts[1:]
    fail(len(amounts) == len(columns) == 2, "geometry_exact_monetary_column_cardinality")
    fail(
        all(
            re.fullmatch(
                r"(?:\d+[a-z]?\([a-z0-9]+\)|[一二三四五六七八九十]+、\d+|\([a-z0-9]+\)|[a-z])",
                old.norm(t),
            )
            for t in other_tokens
        )
        and (not other_tokens or len(note_words) == 1),
        "geometry_unknown_nonmonetary_row_tokens",
    )
    fail(
        not other_words
        or (
            len(other_words) == len(note_words) == 1
            and abs(other_words[0]["x1"] - note_words[0]["x1"]) <= X_TOLERANCE
            and other_words[0]["x1"] < columns[0]["x0"] - 15
            and not excluded
        ),
        "geometry_nonmonetary_annotation_not_in_notes_column",
    )
    for value, column in zip(amounts, columns, strict=True):
        fail(
            min(
                abs(value["x1"] - column["x1"]),
                abs((value["x0"] + value["x1"] - column["x0"] - column["x1"]) / 2),
            )
            <= X_TOLERANCE,
            "geometry_amount_not_aligned_to_year_column",
        )
    fail(
        max(x.year for x in ends) == max(w["year"] for w in columns),
        "geometry_actual_header_and_printed_years_disagree",
    )
    observations = []
    for slot, column in enumerate(columns):
        fail(2010 <= column["year"] <= 2025, "geometry_actual_year_outside_frozen_window")
        end = date(column["year"], ends[-1].month, ends[-1].day)
        start = (
            None
            if c["matched_metric_id"] == "cash_and_cash_equivalents"
            else (date(end.year - 1, end.month, end.day) + timedelta(days=1))
        )
        if start is not None:
            fail(364 <= (end - start).days <= 365, "geometry_noncalendar_annual_duration")
        observations.append(
            dict(
                start=start.isoformat() if start else None,
                end=end.isoformat(),
                raw_value_text=amounts[slot]["text"],
                value=str(_amount(amounts[slot])),
                currency=unit["currency"],
                scale=unit["scale"],
                period_slot=slot + 1,
            )
        )
    # Geometric rows are independently reconstructed. A source-level relation
    # still checks all intervening rows, not just arithmetic equality.
    return dict(
        page=c["page_number"],
        row=row["row_end_line"],
        row_start=row["row_start_line"],
        anchor=anchor,
        header_text=header_text,
        year_columns=columns,
        monetary_words=amounts,
        excluded_note_words=excluded,
        candidate_word_indices=[w["original_word_index"] for w in row["label_words"] + amounts],
        unit=unit,
        current_header_dates=[x.isoformat() for x in ends],
        observations=observations,
        original_candidate_record_unchanged=True,
        old_parser_period_amount_not_used_as_truth_or_veto=True,
        prior_locators=dict(
            period_page=c["_period_source_page"],
            unit_page=c["_unit_source_page"],
            statement_page=c["_statement_source_page"],
            statement_title=c["extraction_metadata"]["statement_title"],
            period_inference=c["extraction_metadata"]["period_inference"],
        ),
        resolved_locators=dict(
            period_page=anchor["page"],
            unit_page=anchor["page"],
            statement_page=anchor["page"],
            statement_title=anchor["text"],
        ),
        locators_independently_replaced=True,
        source_scope="same nearest explicit consolidated statement; no intervening title",
        preceding_geometric_rows={
            str(i): [line_map[c["page_number"]][i]["text"]]
            for i in range(max(0, row["row_end_line"] - 2), row["row_end_line"])
        },
    )


def financial_facts(c, doc, review, geometry, prepared=None):
    semantic = dict(c, financial_scope_type="consolidated_entity")
    metric = c["matched_metric_id"]
    semantic["statement_type"] = (
        "balance_sheet"
        if metric == "cash_and_cash_equivalents"
        else "cash_flow"
        if metric.startswith("net_cash_provided_by_used_in_")
        else "income_statement"
    )
    label = old.semantic_label(semantic)
    fail(c["raw_object_id"] == doc["raw_object_id"], "layout_candidate_document_disagrees")
    certificate = certify(semantic, geometry, prepared)
    original_binding = dict(
        candidate_id=c["candidate_id"],
        start=c["period_start"],
        end=c["period_end"],
        raw_value_text=c["_raw_value_text"],
        value=c["value"],
        currency=c["currency"],
        scale=c["value_scale"],
        period_source_page=c["_period_source_page"],
        statement_type=c["statement_type"],
        financial_scope=c["financial_scope_type"],
        prior_mechanical_review_passed=review["mechanical_checks_passed"],
        prior_failures=review["failures"],
    )
    facts = []
    for binding in certificate["observations"]:
        value = Decimal(binding["value"])
        fail(
            not (
                value > 0
                and (
                    label.startswith("lossfortheyear")
                    or label == "operatingloss"
                    or "netcashusedin" in label
                    or "netcashoutflow" in label
                )
            ),
            "unsigned_loss_or_cash_outflow_requires_sign_adjudication",
        )
        facts.append(_fact(semantic, doc, geometry, label, certificate, binding, original_binding))
    return facts


def _fact(c, doc, geometry, label, certificate, binding, original_binding):
    value = Decimal(binding["value"])
    amount = value * binding["scale"]
    definition = dict(
        metric_id=c["matched_metric_id"],
        original_label=c["source_field_name"],
        normalized_label=label,
        statement_type=c["statement_type"],
        accounting_basis="native_original_report_not_US_GAAP_relabelled",
        scope="consolidated_entity",
        currency=binding["currency"],
    )
    record = dict(start=binding["start"], end=binding["end"], val=str(amount))
    fact_id = "pdf_layout_fact:" + base.sha(
        base.encode(
            dict(
                raw_sha256=doc["sha256"],
                record=record,
                metric_id=c["matched_metric_id"],
                page=certificate["page"],
                row=certificate["row"],
                definition=definition,
                geometry_id=geometry["id"],
                native_binding=binding,
            )
        )
    )
    statement_id = "pdf_geometric_statement:" + base.sha(
        base.encode(dict(raw_object_id=doc["raw_object_id"], anchor=certificate["anchor"]))
    )
    return dict(
        fact_id=fact_id,
        candidate_id=c["candidate_id"],
        original_candidate_bindings=[original_binding],
        source_rederived_binding=binding,
        security_id=doc["security_id"],
        entity_id="unresolved_security:" + doc["security_id"],
        issuer_cluster_id=None,
        source_id=doc["source_id"],
        source_definition_id="pdf_definition:" + base.sha(base.encode(definition)),
        raw_object_id=doc["raw_object_id"],
        raw_sha256=doc["sha256"],
        original_url=doc["original_url"],
        native_pointer=f"pdf://{doc['sha256']}#page={c['page_number']}&layout={geometry['id']}"
        f"&row={certificate['row']}&period_slot={binding['period_slot']}",
        metric_id=c["matched_metric_id"],
        label=c["source_field_name"],
        native_definition=definition,
        currency=binding["currency"],
        unit=binding["currency"],
        original_unit=f"{binding['scale']} {binding['currency']}",
        value_scale={1: "unit", 1000: "thousand", 10000: "万元", 1000000: "million"}[
            binding["scale"]
        ],
        original_value=str(value),
        record=record,
        statement_scope="consolidated_entity",
        source_publish_date=doc["publish_date"],
        evidence=dict(
            page=c["page_number"],
            table=statement_id,
            row=certificate["row"],
            period_slot=binding["period_slot"],
            parser_word_index=c["column_index"],
            table_row_span=list(range(certificate["row_start"], certificate["row"] + 1)),
            raw_value_text=binding["raw_value_text"],
            unit_header=certificate["unit"]["original_header"],
            unit_source_page=certificate["anchor"]["page"],
            period_certificate=dict(
                start=binding["start"],
                end=binding["end"],
                source_page=certificate["anchor"]["page"],
                basis="explicit_original_geometry_calendar_annual_header_and_column",
                inference_not_independent_explicit_start=binding["start"] is not None,
            ),
            value_extraction_method="independent_original_positioned_word_adjudication",
            independent_row_column_certificate=certificate,
            preceding_original_rows=certificate["preceding_geometric_rows"],
        ),
        prior_candidate_unchanged=True,
        status="FINANCIALLY_QUALIFIED_ISSUER_PENDING",
        qa_eligible=False,
    )


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    supplement = umbrella.protocol(root)
    parent = previous.protocol(root)
    completed = base.checked(
        base.read(previous.RAW / "summary.json"), "cross_market_financial_qualification_completed"
    )
    geometry_plan = base.checked(
        base.read(GEOMETRY / "protocol.json"), "cross_market_original_geometry_protocol"
    )
    geometry_done = base.checked(
        base.read(GEOMETRY / "summary.json"), "cross_market_original_geometry_completed"
    )
    fail(geometry_done.get("protocol_id") == geometry_plan["id"], "layout_geometry_parent")
    fail(
        geometry_done["status"] == "GEOMETRY_COMPLETE_NOT_ADMITTED"
        and geometry_done["documents"] == 440,
        "layout_complete_geometry_required",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    payload = (root / SCRIPT).read_bytes()
    fail(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "layout_committed_code",
    )
    sources[SCRIPT] = base.sha(payload)
    documents = []
    for item in parent["documents"]:
        path = GEOMETRY / "documents" / (base.sha(item["document"]["raw_object_id"])[:24] + ".json")
        geometry = base.checked(base.read(path), "cross_market_original_PDF_geometry")
        fail(
            geometry["document"] == item["document"]
            and geometry["protocol_id"] == geometry_plan["id"],
            "layout_registered_geometry_identity",
        )
        documents.append(dict(item, geometry=old.ref(path)))
    value = base.record(
        "cross_market_layout_qualification_protocol",
        at=base.now(),
        code_commit=head,
        sources=sources,
        supplement_protocol_id=supplement["id"],
        supplement_protocol=old.ref(umbrella.RAW / "protocol.json"),
        parent_protocol_id=parent["id"],
        parent_completion=old.ref(previous.RAW / "summary.json"),
        parent_completion_id=completed["id"],
        geometry_protocol=old.ref(GEOMETRY / "protocol.json"),
        geometry_completion=old.ref(GEOMETRY / "summary.json"),
        documents=documents,
        document_count=440,
        fixed_cached_candidates=9513,
        maximum_cached_document_passes=440,
        maximum_enumerations=1,
        maximum_rederived_observations=19026,
        original_PDF_opens=0,
        parser_calls=0,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        network_requests=0,
        GPU_processes=0,
        evaluation_authorized=False,
        quotas=parent["quotas"],
        public_metric_universe=parent["public_metric_universe"],
        rules=dict(
            facts="Existing candidates remain intact. Independently rederive both observations "
            "on each unique candidate-anchored semantic row; old parser values/periods are not "
            "source gold or vetoes. Exact original row, two x-aligned printed years, native "
            "scale/currency, nearest explicit consolidated title, no intervening statement. "
            "Four-column and unresolved restatement reject.",
            annual="Actual annual date + two year columns; relative本年/上年 only anchored to "
            "actual annual header, never metadata. Calendar-anniversary start is a derivation.",
            locator_revision="Old full bindings and new page/period/unit/value bindings "
            "saved together; new geometry-bound fact identity. No original candidate mutation; "
            "no corrections from closure, quotas or model Q. Actual annual endyears2010–2025 only.",
            thresholds=dict(
                line_vertical_center_tolerance_points=LINE_TOLERANCE,
                column_alignment_tolerance_points=X_TOLERANCE,
                maximum_prior_header_pages=MAX_HEADER_DISTANCE,
            ),
            enumeration="Frozen original task kernel and salt, signed GP and overlapping vintage "
            "agreement. All composition remains independent source-exhaustion pending.",
        ),
        no_outcome_based_selection=True,
        roster_replacement=False,
        inspected_before_registration="Known cache locator failures and frozen counts; no model Q. "
        "Only synthetic geometry tests before this production pass; not value-blind.",
    )
    save(RAW / "protocol.json", value)
    return value


def protocol(root):
    value = base.checked(
        base.read(RAW / "protocol.json"), "cross_market_layout_qualification_protocol"
    )
    supplement = umbrella.protocol(root)
    fail(
        value["supplement_protocol_id"] == supplement["id"]
        and value["maximum_rederived_observations"]
        == supplement["maximum_rederived_source_observations"]
        and value["maximum_cached_document_passes"]
        == supplement["maximum_financial_cached_document_passes"],
        "layout_bound_approved_supplement",
    )
    fail(
        value["document_count"] == len(value["documents"]) == 440
        and not value["evaluation_authorized"],
        "layout_fixed_scope",
    )
    for name, digest in value["sources"].items():
        fail(base.sha(root / name) == digest, "layout_frozen_code:" + name)
    for key in (
        "parent_completion",
        "geometry_protocol",
        "geometry_completion",
        "supplement_protocol",
    ):
        fail(
            base.sha(Path(value[key]["path"])) == value[key]["sha256"],
            "layout_frozen_parent:" + key,
        )
    return value


def document_qualify(plan, item):
    doc = item["document"]
    destination = RAW / "documents" / (base.sha(doc["raw_object_id"])[:24] + ".json")
    if destination.exists():
        result = base.checked(base.read(destination), "cross_market_financial_document")
        fail(
            result["protocol_id"] == plan["id"] and result["document"] == doc,
            "layout_cached_document_identity",
        )
        return result
    attempt = RAW / "document_attempts" / destination.name
    fail(not attempt.exists(), "layout_document_unsettled_no_auto_retry")
    save(
        attempt,
        dict(protocol_id=plan["id"], at=base.now(), raw_object_id=doc["raw_object_id"], attempt=1),
    )
    for key in ("extraction", "audit", "text_bundle", "geometry"):
        fail(base.sha(Path(item[key]["path"])) == item[key]["sha256"], "layout_input_hash:" + key)
    extraction = base.checked(base.read(item["extraction"]["path"]), "PDF_extraction_result")
    audit = base.checked(base.read(item["audit"]["path"]), "cross_market_PDF_evidence_audit")
    geometry = base.checked(
        base.read(item["geometry"]["path"]), "cross_market_original_PDF_geometry"
    )
    text = base.checked(
        base.read(item["text_bundle"]["path"]), "cross_market_original_PDF_page_text"
    )
    fail(
        extraction["document"] == audit["document"] == geometry["document"] == doc
        and text["raw_sha256"] == doc["sha256"],
        "layout_input_document_identity",
    )
    reviews = {r["candidate_id"]: r for r in audit["candidate_reviews"]}
    qualified, rejected, adjudications = {}, [], []
    # Geometry is cached in memory per document; no original PDF is touched.
    prepared = prepared_geometry(geometry)
    for candidate in extraction["parsed"]["candidates"]:
        try:
            facts = financial_facts(
                candidate, doc, reviews[candidate["candidate_id"]], geometry, prepared
            )
            for fact in facts:
                if fact["fact_id"] not in qualified:
                    qualified[fact["fact_id"]] = fact
                else:
                    qualified[fact["fact_id"]]["original_candidate_bindings"].extend(
                        fact["original_candidate_bindings"]
                    )
            adjudications.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    status="ORIGINAL_ANCHOR_ROW_INDEPENDENTLY_REDERIVED",
                    fact_ids=[f["fact_id"] for f in facts],
                    original_candidate_unchanged=True,
                )
            )
        except (ValueError, KeyError, TypeError, InvalidOperation) as error:
            rejected.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    metric_id=candidate["matched_metric_id"],
                    reason=str(error),
                )
            )
            adjudications.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    status="UNRESOLVED_OR_OUTSIDE_SCOPE",
                    reason=str(error),
                    original_candidate_unchanged=True,
                )
            )
    facts = list(qualified.values())
    fail(len(facts) <= 2 * len(adjudications), "layout_rederived_document_bound")
    usable, conflicts = old.unique_facts(facts)
    result = base.record(
        "cross_market_financial_document",
        protocol_id=plan["id"],
        document=doc,
        input_references={k: item[k] for k in ("extraction", "audit", "text_bundle", "geometry")},
        status="FINANCIAL_PASS_COMPLETE_ISSUER_AND_TASK_GATES_PENDING",
        qualified_facts=facts,
        candidate_adjudications=adjudications,
        usable_fact_ids=[f["fact_id"] for f in usable.values()],
        rejected_candidates=rejected,
        observation_conflicts=conflicts,
        aggregate_review=old.aggregate_locators({p["page"]: p["text"] for p in text["pages"]}),
        qa_eligible=False,
    )
    save(destination, result)
    return result


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            return base.checked(
                base.read(RAW / "summary.json"), "cross_market_financial_qualification_completed"
            )
        documents = []
        for index, item in enumerate(plan["documents"], 1):
            documents.append(document_qualify(plan, item))
            if index % 40 == 0:
                base.emit(dict(event="layout_documents_saved", count=index, total=440))
        task_path = RAW / "candidate_tasks.json"
        if task_path.exists():
            tasks = base.checked(base.read(task_path), "cross_market_financial_task_candidates")
            fail(tasks["protocol_id"] == plan["id"], "layout_cached_tasks")
        else:
            attempt = RAW / "enumeration_attempt.json"
            fail(not attempt.exists(), "layout_enumeration_unsettled_no_auto_retry")
            save(attempt, dict(protocol_id=plan["id"], at=base.now(), attempt=1))
            candidates, rejected = old.compile_candidates(documents)
            tasks = base.record(
                "cross_market_financial_task_candidates",
                protocol_id=plan["id"],
                candidates=candidates,
                rejected_relations=rejected,
                qa_eligible=False,
                issuer_admitted=False,
                source_exhaustion_admitted=False,
            )
            save(task_path, tasks)
        facts = [f for d in documents for f in d["qualified_facts"]]
        rejects = [r for d in documents for r in d["rejected_candidates"]]
        adjudications = [r for d in documents for r in d["candidate_adjudications"]]
        fail(len(adjudications) == 9513 and len(facts) <= 19026, "layout_total_bound")
        counts = Counter(t["group"] for t in tasks["candidates"])
        summary = base.record(
            "cross_market_financial_qualification_completed",
            at=base.now(),
            protocol_id=plan["id"],
            status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
            documents=len(documents),
            input_candidates=len(adjudications),
            financially_qualified_issuer_pending_facts=len(facts),
            independently_rederived_source_observations=len(facts),
            original_candidate_status_counts=dict(Counter(r["status"] for r in adjudications)),
            public_metric_coverage={
                m: sum(f["metric_id"] == m for f in facts) for m in old.METRICS
            },
            rejected_candidates=len(rejects),
            rejection_reasons=dict(Counter(r["reason"] for r in rejects)),
            candidate_counts={g: counts[g] for g in old.GROUPS},
            candidate_status_counts=dict(Counter(t["status"] for t in tasks["candidates"])),
            relation_rejections=len(tasks["rejected_relations"]),
            quotas=dict.fromkeys(old.GROUPS, 60),
            issuer_admitted_tasks=0,
            admitted_composition_source_exhaustion_tasks=0,
            panel_ready=False,
            independent_issuer_count=None,
            model_sessions=0,
            new_training_updates=0,
            candidate_tasks=old.ref(task_path),
            original_PDF_opens=0,
            parser_calls=0,
            network_requests=0,
            GPU_processes=0,
            original_candidates_unchanged=True,
        )
        save(RAW / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = (
        register(args.root.resolve())
        if args.action == "register"
        else (
            run(args.root.resolve())
            if args.action == "run"
            else base.read(RAW / "summary.json")
            if (RAW / "summary.json").exists()
            else protocol(args.root.resolve())
        )
    )
    base.emit(
        dict(
            event="layout_qualification_" + args.action,
            id=result["id"],
            status=result.get("status"),
        )
    )


if __name__ == "__main__":
    main()
