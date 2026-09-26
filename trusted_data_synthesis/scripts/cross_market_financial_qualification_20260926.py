"""Finite PDF-native financial admission from already frozen offline caches.

This is NOT an evaluation permit. Facts remain issuer-pending, and composition
tasks remain source-exhaustion-pending until an independently recorded review
rules out a same-concept three-year source aggregate. No absence-of-regex-hit is
promoted into that semantic assertion. No PDF/network/model call is made here.
"""

import argparse
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

import prepare_cross_market_sources_20260926 as base
from audit_cross_market_evidence_20260926 import SCALES, consecutive, norm, raw_decimal

RAW = base.RAW / "financial_qualification_01"
AUDIT = base.RAW / "evidence_audit_01"
REVISION = base.RAW / "period_metadata_revision_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_financial_qualification_20260926.py"
SALT = "cross_market_financial_qualification_20260926.v1:"
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
MEAN_METRICS = (
    "revenue",
    "net_income",
    "operating_income",
    "net_cash_provided_by_used_in_operating_activities",
)
METRICS = (
    *MEAN_METRICS,
    "gross_profit",
    "cost_of_revenue",
    "cash_and_cash_equivalents",
    "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents",
    "net_cash_provided_by_used_in_investing_activities",
    "net_cash_provided_by_used_in_financing_activities",
    "capital_expenditures",
    "effect_of_exchange_rate_on_cash_and_cash_equivalents",
    "effect_of_exchange_rate_on_cash_including_restricted",
    "change_in_cash_including_exchange_rate_effect",
    "change_in_cash_including_restricted_and_exchange_rate_effect",
)
# Strict semantic aliases, not the parser's broader metric aliases. In
# particular, cash generated FROM operations is not the operating cash TOTAL.
LABELS = {
    "revenue": {"revenue", "revenues", "turnover", "营业收入", "营业总收入"},
    "gross_profit": {"grossprofit", "毛利"},
    "cost_of_revenue": {"costofsales", "costofrevenue", "costofrevenues", "营业成本"},
    "net_income": {
        "profitfortheyear",
        "lossfortheyear",
        "profit/(loss)fortheyear",
        "(loss)/profitfortheyear",
        "profit(loss)fortheyear",
        "loss/profitfortheyear",
        "净利润",
        "净利润(净亏损以“-”号填列)",
        "净利润(亏损以“-”号填列)",
    },
    "operating_income": {
        "operatingprofit",
        "operatingloss",
        "operatingprofit/(loss)",
        "profitfromoperations",
        "营业利润",
    },
    "net_cash_provided_by_used_in_operating_activities": {
        "经营活动产生的现金流量净额",
        "netcashfromoperatingactivities",
        "netcashusedinoperatingactivities",
        "netcashgeneratedfromoperatingactivities",
        "netcashgeneratedbyoperatingactivities",
        "netcashprovidedbyoperatingactivities",
        "netcashinflowfromoperatingactivities",
        "netcashoutflowfromoperatingactivities",
        "netcashinflow/(outflow)fromoperatingactivities",
        "netcashgeneratedfrom/(usedin)operatingactivities",
        "netcashusedin/generatedfromoperatingactivities",
    },
}
LABELS["cash_and_cash_equivalents"] = {"cashandcashequivalents", "现金及现金等价物"}
for _activity, _chinese in (("investing", "投资"), ("financing", "筹资")):
    LABELS["net_cash_provided_by_used_in_" + _activity + "_activities"] = {
        label.replace("operating", _activity).replace("经营", _chinese)
        for label in LABELS[MEAN_METRICS[3]]
    }
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
EN_END = re.compile(
    r"(?:for\s+the\s+)?year\s+ended\s+(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})",
    re.I,
)
EN_END_MONTH_FIRST = re.compile(
    r"(?:for\s+the\s+)?year\s+ended\s+(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(20\d{2})",
    re.I,
)
UNUSUAL_ANNUAL = re.compile(
    r"(?:52|53|fifty[ -]?(?:two|three))\s*weeks?|(?:变更|更改|変更).{0,18}(?:会计年度|財政年度)|"
    r"(?:change|changed|changing).{0,30}(?:financial|fiscal|reporting)\s+year|"
    r"(?:period|months)\s+ended",
    re.I,
)
AGGREGATE = re.compile(
    r"(?:three[ -]?(?:year|financialyear)|3[ -]?years?|三[个個]?年|三[個个]?年度|三年期)|"
    r"(?:cumulative|aggregate|combined|arithmetic\s+mean|average\s+annual|累计|累計|年平均|三年平均)",
    re.I,
)


def ref(path):
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "financial_output_root")
    base.write(path, value)


def parent_records():
    source = base.checked(
        base.read(base.RAW / "protocol.json"), "cross_market_source_qualification_protocol"
    )
    revision = base.checked(
        base.read(REVISION / "protocol.json"), "cross_market_period_metadata_revision"
    )
    audit = base.checked(base.read(AUDIT / "protocol.json"), "cross_market_evidence_audit_protocol")
    done = base.checked(base.read(AUDIT / "summary.json"), "cross_market_evidence_audit_completed")
    base.require(
        done["protocol_id"] == audit["id"] and done["documents"] == 440, "financial_completed_audit"
    )
    base.require(
        audit["revision_protocol_id"] == revision["id"]
        and revision["parent_protocol_id"] == source["id"],
        "financial_parents",
    )
    return source, revision, audit, done


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    source, revision, audit, done = parent_records()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (
        SCRIPT,
        base.SCRIPT,
        "trusted_data_synthesis/scripts/audit_cross_market_evidence_20260926.py",
    ):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "financial_committed_code",
        )
        sources[name] = base.sha(payload)
    documents = []
    for security in revision["metadata_inventory"]["roster"]:
        for doc in security["documents"]:
            key = base.sha(doc["raw_object_id"])[:24]
            audit_path = AUDIT / "documents" / (key + ".json")
            review = base.checked(base.read(audit_path), "cross_market_PDF_evidence_audit")
            base.require(
                review["document"] == doc and review["status"] == "TEXT_AUDITED_NOT_ADMITTED",
                "financial_audited_document",
            )
            documents.append(
                dict(
                    document=doc,
                    extraction=ref(REVISION / "documents" / (key + ".json")),
                    audit=ref(audit_path),
                    text_bundle=review["text_bundle"],
                )
            )
    plan = base.record(
        "cross_market_financial_qualification_protocol",
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol_id=source["id"],
        revision_protocol_id=revision["id"],
        audit_protocol_id=audit["id"],
        audit_completion_id=done["id"],
        documents=documents,
        document_count=440,
        maximum_cached_document_passes=440,
        maximum_enumerations=1,
        original_PDF_opens=0,
        parser_calls=0,
        network_requests=0,
        model_calls=0,
        scoring_calls=0,
        GPU_processes=0,
        training_updates=0,
        evaluation_authorized=False,
        quotas=dict.fromkeys(GROUPS, 60),
        roster_changes=False,
        public_metric_universe=list(METRICS),
        rules={
            "facts": "all mechanical checks; exact label semantics; original annual header and "
            "explicit year column; independent original-text row/column numeric alignment; "
            "no altered-period/inherited section; preserve signed native amount and unit",
            "annual_calendar_convention": "explicit year ended actual date defines calendar "
            "annual duration; derive previous anniversary+1 only with explicit annual phrase "
            "and matching printed year column, reject week-based/changed annual headers; "
            "source metadata year is never a date proof",
            "versions": "dual requires one common original report for both endpoints and "
            "complete components; three-year chains require overlapping annual observations "
            "with exact same source-native values/labels/currency/scale and report basis; "
            "source versions recorded, no silent coalescing of restatements",
            "dual": "adjacent original Revenue/Cost/Gross-profit statement rows plus exact "
            "closure; source negative cost adds, unsigned positive expense subtracts; "
            "no abs normalization; growth positive base",
            "composition": "three consecutive annual observations of one of four metrics; "
            "complete original-PDF aggregate locator supplied, but semantic absence remains "
            "PENDING_INDEPENDENT_SOURCE_EXHAUSTION_REVIEW until separate review; "
            "no shallow regex absence certificate",
            "other": "three consecutive annual revenues, strictly unique maximum, "
            "same-period NI/OP lookup from same report at all three annual observations",
            "identity": "all facts/tasks remain issuer pending; join admitted per-document "
            "identities before choosing tasks; no security-code-as-issuer",
            "dedup": "one security/group/quantity/metric/actual-period target; latest source "
            "publication then raw-object identity, no outcome-based choice; "
            "issuer-level dedup occurs at later join",
        },
        inspected_before_registration="cached financial examples and mechanical counts "
        "inspected; not value-blind; no model output or Q inspected",
    )
    save(RAW / "protocol.json", plan)
    base.emit(dict(event="financial_qualification_registered", id=plan["id"]))
    return plan


def protocol(root):
    p = base.checked(
        base.read(RAW / "protocol.json"), "cross_market_financial_qualification_protocol"
    )
    for name, digest in p["sources"].items():
        base.require(base.sha(root / name) == digest, "financial_frozen_code:" + name)
    base.require(
        p["document_count"] == len(p["documents"]) == 440 and p["evaluation_authorized"] is False,
        "financial_fixed_scope",
    )
    return p


def annual_period(c, pages, table):
    """Original annual header + printed column, not manifest fiscal-year guess."""
    m = c["extraction_metadata"]
    allowed = {
        "explicit_statement_header",
        "explicit_current_date_comparative_column",
        "explicit_relative_comparative_header",
    }
    if m["period_inference"] not in allowed:
        raise ValueError("inherited_or_unresolved_actual_period")
    start, end = date.fromisoformat(c["period_start"]), date.fromisoformat(c["period_end"])
    if not 364 <= (end - start).days <= 365:
        raise ValueError("noncalendar_annual_duration")
    page = pages[c["_period_source_page"]]
    normalized = norm(page)
    # Restrict unusual-duration detection to this statement header, not unrelated
    # notes later in the report. The original document locator remains public.
    title = norm(m["statement_title"])
    position = normalized.find(title)
    header = normalized[max(0, position) : max(0, position) + 700]
    if UNUSUAL_ANNUAL.search(page[:1400]) or re.search(
        r"(?:52|53)weeks|[0-9]+个月|[0-9]+個月", header
    ):
        raise ValueError("nonstandard_or_changed_annual_header")
    explicit_ends = [
        date(int(y), MONTHS[mon.lower()], int(day)) for day, mon, y in EN_END.findall(page)
    ]
    explicit_ends.extend(
        date(int(y), MONTHS[mon.lower()], int(day))
        for mon, day, y in EN_END_MONTH_FIRST.findall(page)
    )
    english = any(
        e.month == end.month and e.day == end.day and e.year in (end.year, end.year + 1)
        for e in explicit_ends
    )
    chinese = (
        bool(
            re.search(rf"{end.year}年度", normalized)
            or re.search(rf"{end.year}年1[—－–\-~至]12月", normalized)
        )
        and end.month == 12
        and end.day == 31
        and start.month == 1
        and start.day == 1
    )
    if not english and not chinese:
        raise ValueError("missing_actual_annual_header")
    rows = table.get("raw_table_json", {}).get("rows", [])
    first_rows = " ".join(" ".join(str(v or "") for v in row) for row in rows[:5])
    if not re.search(rf"(?<!\d){end.year}(?!\d)", first_rows):
        raise ValueError("missing_explicit_year_column")
    if re.search(r"restated|re[- ]?presented|重述|重列|调整后|調整後", first_rows, re.I):
        raise ValueError("restated_or_represented_column_pending_review")
    expected = date(end.year - 1, end.month, end.day) + timedelta(days=1)
    if start != expected:
        raise ValueError("start_not_annual_header_calendar_duration")
    return dict(
        start=start.isoformat(),
        end=end.isoformat(),
        source_page=c["_period_source_page"],
        basis="explicit_calendar_annual_header_and_printed_year_column",
        current_header_dates=[x.isoformat() for x in explicit_ends],
        printed_year=end.year,
        header_text=page[:1800],
        start_derivation="one calendar year ending on original explicit annual date; "
        "not metadata year",
        inference_not_independent_explicit_start=True,
    )


def semantic_label(c):
    metric, label = c["matched_metric_id"], norm(c["source_field_name"])
    if metric not in LABELS or label not in LABELS[metric]:
        raise ValueError("unregistered_or_ambiguous_native_metric_label")
    if c["financial_scope_type"] != "consolidated_entity":
        raise ValueError("not_consolidated")
    expected_statement = "income_statement"
    if metric.startswith("net_cash_provided_by_used_in_"):
        expected_statement = "cash_flow"
    if metric == "cash_and_cash_equivalents":
        expected_statement = "balance_sheet"
    if c["statement_type"] != expected_statement:
        raise ValueError("wrong_statement_semantics")
    # Revenue and total operating revenue are not silently interchangeable.
    return label


def instant_period(c, pages, table):
    if c["period_start"] is not None:
        raise ValueError("balance_sheet_cash_not_instant")
    end = date.fromisoformat(c["period_end"])
    page = pages[c["_period_source_page"]]
    month = next(name for name, number in MONTHS.items() if number == end.month)
    normalized = norm(page)
    if not any(
        token in normalized
        for year in (end.year, end.year + 1)
        for token in (
            f"{end.day}{month}{year}",
            f"{month}{end.day},{year}",
            f"{year}年{end.month}月{end.day}日",
            f"{year}-{end.month:02d}-{end.day:02d}",
        )
    ):
        raise ValueError("balance_sheet_actual_date_not_explicit")
    first_rows = " ".join(
        " ".join(str(v or "") for v in row) for row in table["raw_table_json"]["rows"][:5]
    )
    if not re.search(rf"(?<!\d){end.year}(?!\d)", first_rows):
        raise ValueError("missing_explicit_year_column")
    return dict(
        start=None,
        end=end.isoformat(),
        source_page=c["_period_source_page"],
        basis="original_balance_sheet_actual_date_and_printed_year_column",
        inference_not_independent_explicit_start=False,
    )


def row_column_certificate(c, pages, table):
    """Independent page-text label-adjacent numeric ordering, fail on ambiguity.

    The PDF parser's positioned-word flag alone does not certify alignment. This
    supports the native one-number-per-line text layout and intentionally rejects
    unresolved split-row/graphic/horizontal layouts instead of guessing columns.
    """
    periods = table["raw_table_json"]["periods"]
    if not 1 <= len(periods) <= 2:
        raise ValueError("unregistered_original_period_column_count")
    slots = [
        index
        for index, p in enumerate(periods)
        if (p.get("period_start"), p.get("period_end")) == (c["period_start"], c["period_end"])
    ]
    # The legacy parser stores a positioned-word index here, NOT a period slot.
    # The independent period slot must come from the actual table period order.
    if len(slots) != 1 or not isinstance(c["column_index"], int) or c["column_index"] < 0:
        raise ValueError("candidate_original_period_column_disagreement")
    if c.get("extraction_metadata", {}).get("value_column_policy") == "consolidated_first_pair":
        raise ValueError("group_company_four_column_alignment_pending")
    header = " ".join(
        " ".join(str(v or "") for v in row) for row in table["raw_table_json"]["rows"][:5]
    )
    years = set(re.findall(r"(?<![\d,])20\d{2}(?![\d,])", header))
    if years - {str(p["fiscal_year"]) for p in periods}:
        raise ValueError("additional_original_year_columns_unresolved")
    lines = pages[c["page_number"]].splitlines()
    label, sequences = norm(c["source_field_name"]), []
    for index, line in enumerate(lines):
        normalized = norm(line)
        if normalized != label and not re.fullmatch(
            r"[一二三四五六七八九十0-9、.()（）]+" + re.escape(label), normalized
        ):
            continue
        numbers, tokens = [], []
        for following in lines[index + 1 : index + 9]:
            if not following.strip():
                continue
            try:
                number = raw_decimal(following)
            except ValueError:
                if not numbers and re.fullmatch(
                    r"(?:\d+[a-z]?\([a-z0-9]+\)|[七八九十]、\d+|[a-z]|\([a-z]+\))", norm(following)
                ):
                    continue
                break
            numbers.append(number)
            tokens.append(following)
        if len(numbers) >= len(periods):
            # A notes column can precede the monetary columns. Taking the final
            # explicitly delimited numeric columns excludes that note integer.
            sequences.append((numbers[-len(periods) :], tokens[-len(periods) :], index + 1))
    expected = raw_decimal(c["_raw_value_text"])
    if not sequences or any(values[slots[0]] != expected for values, _, _ in sequences):
        raise ValueError("independent_original_row_column_alignment_unresolved")
    if len({tuple(values) for values, _, _ in sequences}) != 1:
        raise ValueError("multiple_original_label_rows_disagree")
    values, tokens, line = sequences[0]
    return dict(
        page=c["page_number"],
        label_line=line,
        period_slot=slots[0] + 1,
        ordered_original_amount_tokens=tokens,
        aligned_amounts=[str(v) for v in values],
        period_columns=periods,
        parser_column_index_is_positioned_word_index_not_period_slot=True,
        parser_flag_alone_not_sufficient=True,
    )


def financial_fact(c, doc, review, pages, tables):
    if not review["mechanical_checks_passed"]:
        raise ValueError("prior_mechanical_check_failed:" + ",".join(review["failures"]))
    label = semantic_label(c)
    table = tables[c["table_id"]]
    period = (
        instant_period(c, pages, table)
        if c["matched_metric_id"] == "cash_and_cash_equivalents"
        else annual_period(c, pages, table)
    )
    alignment = row_column_certificate(c, pages, table)
    value = raw_decimal(c["_raw_value_text"])
    if value != Decimal(c["value"]):
        raise ValueError("raw_value_changed")
    if value > 0 and (
        label.startswith("lossfortheyear")
        or label == "operatingloss"
        or "netcashusedin" in label
        or "netcashoutflow" in label
    ):
        raise ValueError("unsigned_loss_or_cash_outflow_requires_sign_adjudication")
    raw_periods = table["raw_table_json"]["periods"]
    if not any(
        p.get("period_start") == c["period_start"] and p.get("period_end") == c["period_end"]
        for p in raw_periods
    ):
        raise ValueError("period_not_in_original_table")
    if c["extraction_metadata"]["value_extraction_method"] != "positioned_words_exact_label":
        raise ValueError("no_exact_positioned_value_extraction")
    scale = SCALES[c["value_scale"]]
    unit_page = norm(pages[c["_unit_source_page"]])
    unit_tokens = {
        "CNY": ("人民币", "人民幣", "rmb", "cny", "renminbi"),
        "HKD": ("港币", "港幣", "hk$", "hkd", "hongkongdollar"),
        "USD": ("美元", "usd", "us$", "unitedstatesdollar"),
    }
    if norm(c["_unit_evidence_text"]) not in unit_page or not any(
        token in unit_page for token in unit_tokens[c["currency"]]
    ):
        raise ValueError("native_unit_currency_evidence_unresolved")
    amount = value * scale
    definition = dict(
        metric_id=c["matched_metric_id"],
        original_label=c["source_field_name"],
        normalized_label=label,
        statement_type=c["statement_type"],
        accounting_basis="native_original_report_not_US_GAAP_relabelled",
        scope="consolidated_entity",
        currency=c["currency"],
    )
    fid = "pdf_fact:" + base.sha(
        base.encode(
            dict(
                candidate_id=c["candidate_id"],
                raw_sha256=doc["sha256"],
                record=dict(start=c["period_start"], end=c["period_end"], val=str(amount)),
            )
        )
    )
    return dict(
        fact_id=fid,
        candidate_id=c["candidate_id"],
        security_id=doc["security_id"],
        entity_id="unresolved_security:" + doc["security_id"],
        issuer_cluster_id=None,
        source_id=doc["source_id"],
        source_definition_id="pdf_definition:" + base.sha(base.encode(definition)),
        raw_object_id=doc["raw_object_id"],
        raw_sha256=doc["sha256"],
        original_url=doc["original_url"],
        native_pointer=(
            f"pdf://{doc['sha256']}#page={c['page_number']}&table={c['table_id']}"
            f"&row={c['row_index']}&period_slot={alignment['period_slot']}"
            f"&parser_word_index={c['column_index']}&candidate={c['candidate_id']}"
        ),
        metric_id=c["matched_metric_id"],
        label=c["source_field_name"],
        native_definition=definition,
        currency=c["currency"],
        unit=c["currency"],
        original_unit=c["unit"],
        value_scale=c["value_scale"],
        original_value=str(value),
        record=dict(start=c["period_start"], end=c["period_end"], val=str(amount)),
        statement_scope="consolidated_entity",
        source_publish_date=doc["publish_date"],
        evidence=dict(
            page=c["page_number"],
            table=c["table_id"],
            row=c["row_index"],
            period_slot=alignment["period_slot"],
            parser_word_index=c["column_index"],
            table_row_span=c["extraction_metadata"].get("table_row_span", [c["row_index"]]),
            raw_value_text=c["_raw_value_text"],
            unit_header=c["_unit_evidence_text"],
            unit_source_page=c["_unit_source_page"],
            period_certificate=period,
            value_extraction_method=c["extraction_metadata"]["value_extraction_method"],
            independent_row_column_certificate=alignment,
            preceding_original_rows={
                str(index): table["raw_table_json"]["rows"][index]
                for index in range(max(0, c["row_index"] - 2), c["row_index"])
            },
        ),
        status="FINANCIALLY_QUALIFIED_ISSUER_PENDING",
        qa_eligible=False,
    )


def fact_key(f):
    return f["metric_id"], f["record"]["start"], f["record"]["end"]


def comparable(a, b):
    return all(
        a[key] == b[key]
        for key in (
            "security_id",
            "source_id",
            "currency",
            "original_unit",
            "value_scale",
            "source_definition_id",
            "statement_scope",
        )
    )


def same_observation(a, b):
    return comparable(a, b) and a["record"] == b["record"]


def amount(f):
    return Decimal(f["record"]["val"])


def unique_facts(facts):
    grouped = defaultdict(list)
    for f in facts:
        grouped[fact_key(f)].append(f)
    usable, conflicts = {}, []
    for key, rows in sorted(grouped.items()):
        if not all(same_observation(rows[0], other) for other in rows[1:]):
            conflicts.append(
                dict(
                    key=key,
                    fact_ids=[f["fact_id"] for f in rows],
                    reason="within_report_native_observation_conflict",
                )
            )
            continue
        usable[key] = min(
            rows, key=lambda f: (f["evidence"]["page"], f["evidence"]["row"], f["fact_id"])
        )
    return usable, conflicts


def signed_relation(gross, revenue, cost):
    facts = (gross, revenue, cost)
    if (
        len({f["raw_object_id"] for f in facts}) != 1
        or len({f["record"]["start"] for f in facts}) != 1
        or len({f["record"]["end"] for f in facts}) != 1
    ):
        raise ValueError("relation_not_one_report_period")
    if (
        len(
            {
                (
                    f["currency"],
                    f["original_unit"],
                    f["statement_scope"],
                    f["evidence"]["page"],
                    f["evidence"]["table"],
                )
                for f in facts
            }
        )
        != 1
    ):
        raise ValueError("relation_not_same_statement_scope_currency_scale")
    rows = [f["evidence"]["row"] for f in (revenue, cost, gross)]
    if not (1 <= rows[1] - rows[0] <= 2 and 1 <= rows[2] - rows[1] <= 2):
        raise ValueError("relation_original_statement_order_not_direct")
    for earlier, later in ((revenue, cost), (cost, gross)):
        for index in range(earlier["evidence"]["row"] + 1, later["evidence"]["row"]):
            row = later["evidence"].get("preceding_original_rows", {}).get(str(index))
            if row is None or any(str(value or "").strip() for value in row):
                raise ValueError("relation_intervening_original_row_not_empty")
    cost_label = cost["native_definition"]["normalized_label"]
    if cost_label not in {"costofsales", "costofrevenue", "costofrevenues", "营业成本"}:
        raise ValueError("relation_cost_semantics")
    coefficient = 1 if amount(cost) < 0 else -1
    if coefficient == 1 and cost["source_id"] != "hkex_disclosures":
        raise ValueError("negative_cost_presentation_unqualified")
    if amount(revenue) + coefficient * amount(cost) != amount(gross):
        raise ValueError("relation_exact_source_amounts_do_not_close")
    return dict(
        rule="native_consolidated_revenue_plus_signed_sales_expense_v1",
        complete=True,
        revenue_fact_id=revenue["fact_id"],
        cost_fact_id=cost["fact_id"],
        gross_profit_fact_id=gross["fact_id"],
        cost_coefficient=coefficient,
        original_row_order=rows,
        numeric_closure_is_not_sole_admission_rule=True,
        original_negative_cost_is_preserved=coefficient == 1,
    )


def aggregate_locators(pages):
    """Locators for finite independent source-exhaustion review, never proof of absence."""
    found, metric_pages = [], defaultdict(list)
    for number, page in pages.items():
        matches = list(AGGREGATE.finditer(page))
        for match in matches:
            found.append(
                dict(
                    page=number,
                    offset=match.start(),
                    text=page[max(0, match.start() - 220) : match.end() + 380],
                )
            )
        normalized = norm(page)
        for metric, labels in LABELS.items():
            if any(label in normalized for label in labels):
                metric_pages[metric].append(number)
    return dict(
        status="PENDING_INDEPENDENT_SOURCE_EXHAUSTION_REVIEW",
        full_text_pages=len(pages),
        empty_text_pages=[n for n, t in pages.items() if not t.strip()],
        all_native_metric_label_pages=dict(metric_pages),
        regex_matches_are_locators_not_semantic_verdicts=True,
        locators=found,
    )


def document_qualify(plan, item):
    doc = item["document"]
    key = base.sha(doc["raw_object_id"])[:24]
    destination = RAW / "documents" / (key + ".json")
    if destination.exists():
        old = base.checked(base.read(destination), "cross_market_financial_document")
        base.require(
            old["protocol_id"] == plan["id"] and old["document"] == doc, "financial_cached_identity"
        )
        return old
    for name in ("extraction", "audit", "text_bundle"):
        reference = item[name]
        base.require(
            base.sha(Path(reference["path"])) == reference["sha256"],
            "financial_frozen_input:" + name,
        )
    extraction = base.checked(base.read(item["extraction"]["path"]), "PDF_extraction_result")
    audit = base.checked(base.read(item["audit"]["path"]), "cross_market_PDF_evidence_audit")
    text = base.checked(
        base.read(item["text_bundle"]["path"]), "cross_market_original_PDF_page_text"
    )
    base.require(
        extraction["document"] == audit["document"] == doc and text["raw_sha256"] == doc["sha256"],
        "financial_input_parent",
    )
    pages = {p["page"]: p["text"] for p in text["pages"]}
    reviews = {c["candidate_id"]: c for c in audit["candidate_reviews"]}
    tables = {t["table_id"]: t for t in extraction["parsed"]["tables"]}
    qualified, rejected = [], []
    for candidate in extraction["parsed"]["candidates"]:
        try:
            qualified.append(
                financial_fact(candidate, doc, reviews[candidate["candidate_id"]], pages, tables)
            )
        except (ValueError, KeyError, TypeError, InvalidOperation) as error:
            rejected.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    metric_id=candidate["matched_metric_id"],
                    reason=str(error),
                )
            )
    usable, conflicts = unique_facts(qualified)
    result = base.record(
        "cross_market_financial_document",
        protocol_id=plan["id"],
        document=doc,
        input_references={k: item[k] for k in ("extraction", "audit", "text_bundle")},
        status="FINANCIAL_PASS_COMPLETE_ISSUER_AND_TASK_GATES_PENDING",
        qualified_facts=qualified,
        usable_fact_ids=[f["fact_id"] for f in usable.values()],
        rejected_candidates=rejected,
        observation_conflicts=conflicts,
        aggregate_review=aggregate_locators(pages),
        qa_eligible=False,
    )
    save(destination, result)
    return result


def candidate_task(
    group,
    security,
    periods,
    facts,
    quantity,
    metric,
    answer,
    *,
    secondary=None,
    relations=None,
    aggregate_pending=False,
):
    identity = dict(
        group=group,
        security_id=security,
        periods=periods,
        quantity=quantity,
        metric_id=metric,
        secondary_metric_id=secondary,
    )
    return dict(
        task_id="cross_market_task:" + base.sha(base.encode(identity)),
        **identity,
        issuer_cluster_id=None,
        raw_object_ids=sorted({f["raw_object_id"] for f in facts}),
        fact_ids=list(dict.fromkeys(f["fact_id"] for f in facts)),
        currency=facts[0]["currency"],
        unit="percent" if quantity == "relative_change" else facts[0]["currency"],
        answer_exact=str(Fraction(answer)),
        relation_certificates=relations or [],
        native_observations=[
            dict(fact_id=f["fact_id"], metric_id=f["metric_id"], record=f["record"]) for f in facts
        ],
        status="PENDING_ISSUER_AND_SOURCE_EXHAUSTION"
        if aggregate_pending
        else "FINANCIALLY_QUALIFIED_ISSUER_PENDING",
        pending_gates=["issuer_document_identity", "public_runtime_admission"]
        + (
            ["independent_full_source_no_same_concept_three_year_aggregate"]
            if aggregate_pending
            else []
        ),
        qa_eligible=False,
    )


def compile_candidates(documents):
    """Enumerate once using frozen rules. Preserve rejection reasons, not Q=0."""
    all_facts = {f["fact_id"]: f for doc in documents for f in doc["qualified_facts"]}
    by_security = defaultdict(list)
    for doc in documents:
        usable = {fact_key(all_facts[key]): all_facts[key] for key in doc["usable_fact_ids"]}
        by_security[doc["document"]["security_id"]].append((doc, usable))
    tasks, rejections = {}, []

    def keep(task):
        # Source choice is latest publication/identity, never arithmetic magnitude
        # or model performance. Multiple report witnesses are not new tasks.
        source_order = tuple(
            sorted(
                (all_facts[f]["source_publish_date"], all_facts[f]["raw_object_id"])
                for f in task["fact_ids"]
            )
        )
        prior = tasks.get(task["task_id"])
        if prior is None or source_order > prior[0]:
            tasks[task["task_id"]] = (source_order, task)

    for security, records in sorted(by_security.items()):
        for doc, lookup in records:
            gross = sorted(
                (f for f in lookup.values() if f["metric_id"] == "gross_profit"),
                key=lambda f: f["record"]["end"],
            )
            for previous in gross:
                for current in gross:
                    p0 = (previous["record"]["start"], previous["record"]["end"])
                    p1 = (current["record"]["start"], current["record"]["end"])
                    if not consecutive(p0, p1):
                        continue
                    try:
                        if not comparable(previous, current):
                            raise ValueError("endpoint_native_definition_changed")
                        facts, relations = [previous, current], []
                        for gross_fact in (previous, current):
                            period = (gross_fact["record"]["start"], gross_fact["record"]["end"])
                            revenue, cost = (
                                lookup[(m, *period)] for m in ("revenue", "cost_of_revenue")
                            )
                            relations.append(signed_relation(gross_fact, revenue, cost))
                            facts.extend((revenue, cost))
                        if not comparable(facts[2], facts[4]) or not comparable(facts[3], facts[5]):
                            raise ValueError("component_definition_changed")
                        change = amount(current) - amount(previous)
                        keep(
                            candidate_task(
                                GROUPS[0],
                                security,
                                [p0, p1],
                                facts,
                                "difference",
                                "gross_profit",
                                change,
                                relations=relations,
                            )
                        )
                        if amount(previous) > 0:
                            keep(
                                candidate_task(
                                    GROUPS[0],
                                    security,
                                    [p0, p1],
                                    facts,
                                    "relative_change",
                                    "gross_profit",
                                    Fraction(change) / Fraction(amount(previous)) * 100,
                                    relations=relations,
                                )
                            )
                        else:
                            rejections.append(
                                dict(
                                    group=GROUPS[0],
                                    security_id=security,
                                    periods=[p0, p1],
                                    reason="growth_nonpositive_base",
                                )
                            )
                    except (ValueError, KeyError) as error:
                        rejections.append(
                            dict(
                                group=GROUPS[0],
                                security_id=security,
                                raw_object_id=doc["document"]["raw_object_id"],
                                periods=[p0, p1],
                                reason=str(error),
                            )
                        )
        # Three-year windows use a shared, exactly equal middle-year observation
        # to bridge TWO original reports; separate-year concatenation alone fails.
        for metric in MEAN_METRICS:
            for earlier_doc, left in records:
                for later_doc, right in records:
                    if (
                        earlier_doc["document"]["raw_object_id"]
                        == later_doc["document"]["raw_object_id"]
                    ):
                        continue
                    if (
                        earlier_doc["document"]["publish_date"]
                        >= later_doc["document"]["publish_date"]
                    ):
                        continue
                    left_rows = sorted(
                        (f for f in left.values() if f["metric_id"] == metric),
                        key=lambda f: f["record"]["end"],
                    )
                    right_rows = sorted(
                        (f for f in right.values() if f["metric_id"] == metric),
                        key=lambda f: f["record"]["end"],
                    )
                    for first in left_rows:
                        for middle in left_rows:
                            p0, p1 = [
                                (f["record"]["start"], f["record"]["end"]) for f in (first, middle)
                            ]
                            if not consecutive(p0, p1):
                                continue
                            mirror = right.get((metric, *p1))
                            if mirror is None:
                                continue
                            for last in right_rows:
                                p2 = (last["record"]["start"], last["record"]["end"])
                                if not consecutive(p1, p2):
                                    continue
                                periods = [p0, p1, p2]
                                if (
                                    not comparable(first, middle)
                                    or not comparable(middle, last)
                                    or not same_observation(middle, mirror)
                                ):
                                    rejections.append(
                                        dict(
                                            group=GROUPS[1],
                                            security_id=security,
                                            metric_id=metric,
                                            periods=periods,
                                            reason="overlap_bridge_native_value_definition_or_unit_disagrees",
                                        )
                                    )
                                    continue
                                selected = [first, mirror, last]
                                task = candidate_task(
                                    GROUPS[1],
                                    security,
                                    periods,
                                    selected,
                                    "three_year_mean",
                                    metric,
                                    sum(Fraction(amount(f)) for f in selected) / 3,
                                    aggregate_pending=True,
                                )
                                task["vintage_bridge"] = dict(
                                    earlier_middle_fact_id=middle["fact_id"],
                                    later_middle_fact_id=mirror["fact_id"],
                                    exact_native_agreement=True,
                                )
                                task["source_exhaustion_review_raw_objects"] = [
                                    earlier_doc["document"]["raw_object_id"],
                                    later_doc["document"]["raw_object_id"],
                                ]
                                keep(task)
                                if metric != "revenue":
                                    continue
                                values = list(map(amount, selected))
                                if values.count(max(values)) != 1:
                                    rejections.append(
                                        dict(
                                            group=GROUPS[2],
                                            security_id=security,
                                            periods=periods,
                                            reason="revenue_argmax_not_unique",
                                        )
                                    )
                                    continue
                                peak = values.index(max(values))
                                for secondary in ("net_income", "operating_income"):
                                    try:
                                        secondary_facts = [
                                            left[(secondary, *p0)],
                                            right[(secondary, *p1)],
                                            right[(secondary, *p2)],
                                        ]
                                        old_middle_secondary = left[(secondary, *p1)]
                                        if not all(
                                            comparable(secondary_facts[0], f)
                                            for f in secondary_facts[1:]
                                        ) or not same_observation(
                                            old_middle_secondary, secondary_facts[1]
                                        ):
                                            raise ValueError(
                                                "lookup_secondary_vintage_bridge_disagrees"
                                            )
                                        if any(
                                            f["raw_object_id"] != r["raw_object_id"]
                                            or f["currency"] != r["currency"]
                                            for f, r in zip(secondary_facts, selected, strict=True)
                                        ):
                                            raise ValueError(
                                                "revenue_lookup_not_same_source_scope_currency"
                                            )
                                        task = candidate_task(
                                            GROUPS[2],
                                            security,
                                            periods,
                                            [*selected, *secondary_facts],
                                            "argmax_then_lookup",
                                            "revenue",
                                            amount(secondary_facts[peak]),
                                            secondary=secondary,
                                        )
                                        task["unique_argmax_period"] = periods[peak]
                                        task["vintage_bridge"] = dict(
                                            revenue=[middle["fact_id"], mirror["fact_id"]],
                                            secondary=[
                                                old_middle_secondary["fact_id"],
                                                secondary_facts[1]["fact_id"],
                                            ],
                                            exact_native_agreement=True,
                                        )
                                        keep(task)
                                    except (KeyError, ValueError) as error:
                                        rejections.append(
                                            dict(
                                                group=GROUPS[2],
                                                security_id=security,
                                                periods=periods,
                                                secondary=secondary,
                                                reason=str(error),
                                            )
                                        )
    ordered = sorted((v[1] for v in tasks.values()), key=lambda t: base.sha(SALT + t["task_id"]))
    return ordered, rejections


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
                base.emit(dict(event="financial_documents_saved", count=index, total=440))
        tasks_path = RAW / "candidate_tasks.json"
        if tasks_path.exists():
            tasks = base.checked(base.read(tasks_path), "cross_market_financial_task_candidates")
            base.require(tasks["protocol_id"] == plan["id"], "financial_cached_tasks")
        else:
            reservation = RAW / "enumeration_attempt.json"
            base.require(not reservation.exists(), "financial_enumeration_unsettled_no_auto_retry")
            save(reservation, dict(protocol_id=plan["id"], at=base.now(), attempt=1))
            candidates, rejected = compile_candidates(documents)
            tasks = base.record(
                "cross_market_financial_task_candidates",
                protocol_id=plan["id"],
                candidates=candidates,
                rejected_relations=rejected,
                qa_eligible=False,
                issuer_admitted=False,
                source_exhaustion_admitted=False,
            )
            save(tasks_path, tasks)
        facts = [f for d in documents for f in d["qualified_facts"]]
        rejects = [f for d in documents for f in d["rejected_candidates"]]
        counts = Counter(t["group"] for t in tasks["candidates"])
        status_counts = Counter(t["status"] for t in tasks["candidates"])
        summary = base.record(
            "cross_market_financial_qualification_completed",
            at=base.now(),
            protocol_id=plan["id"],
            status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
            documents=len(documents),
            input_candidates=len(facts) + len(rejects),
            financially_qualified_issuer_pending_facts=len(facts),
            public_metric_coverage={
                metric: sum(f["metric_id"] == metric for f in facts) for metric in METRICS
            },
            rejected_candidates=len(rejects),
            rejection_reasons=dict(Counter(r["reason"] for r in rejects)),
            candidate_counts={g: counts[g] for g in GROUPS},
            candidate_status_counts=dict(status_counts),
            relation_rejections=len(tasks["rejected_relations"]),
            quotas=dict.fromkeys(GROUPS, 60),
            issuer_admitted_tasks=0,
            admitted_composition_source_exhaustion_tasks=0,
            panel_ready=False,
            independent_issuer_count=None,
            model_sessions=0,
            new_training_updates=0,
            candidate_tasks=ref(tasks_path),
            original_PDF_opens=0,
            parser_calls=0,
            network_requests=0,
            GPU_processes=0,
        )
        save(RAW / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.action == "register":
        result = register(args.root.resolve())
    elif args.action == "run":
        result = run(args.root.resolve())
    else:
        result = (
            base.read(RAW / "summary.json")
            if (RAW / "summary.json").exists()
            else protocol(args.root.resolve())
        )
    base.emit(
        dict(
            event="financial_qualification_" + args.action,
            id=result["id"],
            status=result.get("status"),
        )
    )


if __name__ == "__main__":
    main()
