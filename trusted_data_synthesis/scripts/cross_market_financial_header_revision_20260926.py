"""Repair original statement-header localization, not financial thresholds.

The preserved first financial pass looked only at the first five cached table
rows. Some tables start mid-statement or consist solely of fallback label rows.
This revision uses the already-bound original statement page and stops before
the first original financial row. Annual dates, values, labels, signed relations,
quotas and issuer/source-exhaustion gates remain the frozen parent's. Numeric
column cardinality and explicit statement-scope continuity are strengthened.
No original PDF is reopened and no candidate is reparsed.
"""

import argparse
import copy
import re
import subprocess
import types
from datetime import date
from pathlib import Path

import cross_market_financial_qualification_20260926 as old

base = old.base
RAW = base.RAW / "financial_header_revision_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_financial_header_revision_20260926.py"
DATA_LABEL = re.compile(
    r"^(?:[一二三四五六七八九十0-9、.()（）:：]+)?(?:"
    r"revenue|turnover|sales|costof|grossprofit|otherincome|profit|loss|"
    r"non[-–]?currentassets|currentassets|assets|liabilities|property,?plant|"
    r"cashflows?from|operatingactivities|investingactivities|financingactivities|"
    r"营业|净利润|营业利润|经营活动|投[资資]活动|筹资活动|现[金流]|非流动资产|流动资产|资产|负债)"
)
OTHER_STATEMENT = re.compile(
    r"(?:母公司(?:利润|资产负债|现金流量)表|parentcompan(?:y|ies)|"
    r"statementoffinancialposition|balancesheet|incomestatement|statementofprofit|"
    r"statementofcashflows|cashflowstatement|合并(?:利润|资产负债|现金流量)表)"
)
COMPLEX_SUBCOLUMNS = re.compile(
    r"beforebiological|biologicalfairvalue|beforeexceptional|exceptionalitems|"
    r"beforeadjustments|adjustments.*total|集团.*本公司|集團.*本公司|group.*company"
)
STATEMENT_TITLE = re.compile(
    r"(?:母公司|合并|合併|公司)?(?:资产负债表|資產負債表|利润表|利潤表|"
    r"综合收益表|綜合收益表|现金流量表|現金流量表)|"
    r"(?:consolidated|separate|parentcompany|company)?(?:statementsof|statementof)"
    r"(?:profitorloss|income|comprehensiveincome|cashflows|financialposition)|"
    r"(?:consolidated|parentcompany|company)?(?:incomestatement|cashflowstatement|balancesheet)"
)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "header_output_root")
    base.write(path, value)


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent = old.protocol(root)
    completed_path = old.RAW / "summary.json"
    completed = base.checked(
        base.read(completed_path), "cross_market_financial_qualification_completed"
    )
    base.require(
        completed["protocol_id"] == parent["id"]
        and completed["candidate_counts"]
        == {
            "dual_sufficient": 36,
            "composition_required": 177,
            "other_financial": 47,
        },
        "header_preserved_parent_output",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "header_committed_code",
    )
    sources[SCRIPT] = base.sha(payload)
    value = base.record(
        "cross_market_financial_header_revision_protocol",
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol_id=parent["id"],
        parent_completion=old.ref(completed_path),
        parent_completion_id=completed["id"],
        documents=parent["documents"],
        document_count=440,
        fixed_cached_candidates=9513,
        maximum_cached_document_passes=440,
        maximum_enumerations=1,
        original_PDF_opens=0,
        parser_calls=0,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        network_requests=0,
        GPU_processes=0,
        evaluation_authorized=False,
        quotas=parent["quotas"],
        financial_rules_unchanged=parent["rules"],
        public_metric_universe=parent["public_metric_universe"],
        revision_scope="Only locate the original printed year columns within the relevant "
        "statement title-to-first-data-row header, including explicitly bound source period "
        "page when cached table headers are absent. Preserve original financial values, "
        "actual date rules, aliases, source versions and quotas. Strengthen independent "
        "numeric alignment to exactly N monetary tokens, or N+1 only with an explicit "
        "Notes column and syntactically identifiable leading note token; no rightmost-N "
        "truncation of unknown extra monetary columns. Original title-to-target page/line "
        "scope must not cross a parent/company/other statement boundary; repeated same "
        "header requires explicit continued/续 text.",
        no_outcome_based_selection=True,
        roster_replacement=False,
        known_original_capacity_preserved=completed["candidate_counts"],
        diagnostic_sample="SHA256(candidate_id) earliest 12 of all 2289 missing-column "
        "rejects: all 12 have printed columns on the bound original page; only 2 have "
        "columns in cached table, at rows 5 and 29. One sampled report has multiple "
        "subcolumns and stays unresolved; seeing two years alone never admits it.",
        cached_text_pass_is_not_a_refund_of_prior_parser_or_text_extraction_budgets=True,
    )
    save(RAW / "protocol.json", value)
    base.emit(dict(event="financial_header_revision_registered", id=value["id"]))
    return value


def protocol(root):
    value = base.checked(
        base.read(RAW / "protocol.json"), "cross_market_financial_header_revision_protocol"
    )
    parent = old.protocol(root)
    base.require(
        value["documents"] == parent["documents"] and value["document_count"] == 440,
        "header_same_440_cached_documents",
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "header_frozen_code:" + name)
    base.require(
        base.sha(Path(value["parent_completion"]["path"])) == value["parent_completion"]["sha256"],
        "header_preserved_failure_summary",
    )
    return value


def _numeric_line(text):
    try:
        return old.raw_decimal(text)
    except ValueError:
        return None


def statement_header(c, pages, table):
    """Original column evidence before data, with explicit period order."""
    page_number = c["_period_source_page"]
    lines = pages[page_number].splitlines()
    normalized = [old.norm(line) for line in lines]
    title = old.norm(c["extraction_metadata"]["statement_title"])
    matches = []
    for index in range(len(lines)):
        for width in range(1, 5):
            joined = "".join(normalized[index : index + width])
            if title in joined:
                # The shortest title-containing span must start/end with title
                # material, not an arbitrary prefix or later unrelated data.
                if index and title in "".join(normalized[index + 1 : index + width]):
                    continue
                matches.append((index, min(index + width, len(lines))))
                break
    minimal = []
    for start, end in matches:
        if not any(start >= a and end <= b for a, b in minimal):
            minimal.append((start, end))
    if len(minimal) != 1:
        raise ValueError("original_statement_title_missing_or_ambiguous")
    start, title_end = minimal[0]
    periods = table["raw_table_json"]["periods"]
    years = [str(p["fiscal_year"]) for p in periods]
    if not 1 <= len(years) <= 2 or len(set(years)) != len(years):
        raise ValueError("header_unregistered_period_columns")
    end = len(lines)
    for index in range(title_end, len(lines)):
        line = normalized[index]
        if not line:
            continue
        if DATA_LABEL.search(line):
            end = index
            break
        if OTHER_STATEMENT.search(line):
            end = index
            break
        number = _numeric_line(lines[index])
        if number is not None and line not in years:
            # Explicit day/month fragments in a date header are not observations.
            next_line = normalized[index + 1] if index + 1 < len(lines) else ""
            if 1 <= number <= 31 and next_line in old.MONTHS:
                continue
            end = max(title_end, index - 1)
            break
    header_lines = lines[start:end]
    header_text = "\n".join(header_lines)
    compact = old.norm(header_text)
    if COMPLEX_SUBCOLUMNS.search(compact):
        raise ValueError("original_header_multiple_semantic_subcolumns_unresolved")
    # Only standalone printed column labels count; years in the report title,
    # annual date sentence, footnote or amounts are never column evidence.
    column_years = []
    for line in header_lines:
        normalized_line = old.norm(line)
        full_date = re.fullmatch(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", normalized_line)
        if full_date:
            year, month, day = map(int, full_date.groups())
            printed_date = date(year, month, day).isoformat()
            if printed_date not in {p["period_end"] for p in periods}:
                raise ValueError("original_full_date_column_not_registered_period_end")
            column_years.append(str(year))
            continue
        if re.fullmatch(r"20\d{2}(?:年度|年)?", normalized_line):
            column_years.append(normalized_line[:4])
        elif re.fullmatch(r"20\d{2}(?:年度|年)?\s+20\d{2}(?:年度|年)?", line.strip()):
            column_years.extend(re.findall(r"20\d{2}", line))
        elif re.fullmatch(r"(?:20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}日?\s*){2}", line.strip()):
            column_years.extend(re.findall(r"20\d{2}", line))
    if column_years != years:
        raise ValueError("original_printed_year_column_order_unresolved")
    return dict(
        page=page_number,
        title_start_line_1based=start + 1,
        title_end_line_1based=title_end,
        first_data_or_boundary_line_1based=end + 1,
        original_header_text=header_text,
        printed_year_columns=column_years,
        expected_period_years=years,
        source="complete_frozen_original_statement_page_not_first_five_cached_rows",
        arbitrary_body_or_report_title_years_not_used=True,
    )


def header_table(c, pages, table):
    header = statement_header(c, pages, table)
    surrogate = copy.deepcopy(table)
    # Only the old helper's header argument is replaced. Original tables and
    # candidate row positions are passed unchanged to financial_fact itself.
    surrogate["raw_table_json"]["rows"] = [[header["original_header_text"]]]
    return surrogate, header


def annual_period(c, pages, table):
    surrogate, header = header_table(c, pages, table)
    result = old.annual_period(c, pages, surrogate)
    result["original_column_header_certificate"] = header
    return result


def instant_period(c, pages, table):
    surrogate, header = header_table(c, pages, table)
    result = old.instant_period(c, pages, surrogate)
    result["original_column_header_certificate"] = header
    return result


def row_column_certificate(c, pages, table):
    _, header = header_table(c, pages, table)
    periods = table["raw_table_json"]["periods"]
    if not 1 <= len(periods) <= 2:
        raise ValueError("unregistered_original_period_column_count")
    slots = [
        index
        for index, p in enumerate(periods)
        if (p.get("period_start"), p.get("period_end")) == (c["period_start"], c["period_end"])
    ]
    if len(slots) != 1 or not isinstance(c["column_index"], int) or c["column_index"] < 0:
        raise ValueError("candidate_original_period_column_disagreement")
    if c.get("extraction_metadata", {}).get("value_column_policy") == "consolidated_first_pair":
        raise ValueError("group_company_four_column_alignment_pending")
    has_note_column = any(
        old.norm(line) in {"note", "notes", "附注", "附註", "注", "註"}
        for line in header["original_header_text"].splitlines()
    )
    lines = pages[c["page_number"]].splitlines()
    label, sequences = old.norm(c["source_field_name"]), []
    note_pattern = r"(?:\d+[a-z]?\([a-z0-9]+\)|[一二三四五六七八九十]+、\d+|[a-z]|\([a-z]+\))"
    for index, line in enumerate(lines):
        normalized = old.norm(line)
        if normalized != label and not re.fullmatch(
            r"[一二三四五六七八九十0-9、.()（）]+" + re.escape(label), normalized
        ):
            continue
        numbers, tokens, note_tokens = [], [], []
        for following in lines[index + 1 : index + 9]:
            if not following.strip():
                continue
            try:
                number = old.raw_decimal(following)
            except ValueError:
                if (
                    not numbers
                    and has_note_column
                    and re.fullmatch(note_pattern, old.norm(following))
                ):
                    note_tokens.append(following)
                    continue
                break
            numbers.append(number)
            tokens.append(following)
        if len(numbers) == len(periods) + 1:
            # Syntactic note evidence, never a small-value heuristic. A printed
            # integer can be a note only when the original header has its column.
            if not has_note_column or note_tokens or not re.fullmatch(r"\d+", old.norm(tokens[0])):
                raise ValueError("extra_original_numeric_column_not_certified_note")
            note_tokens = tokens[:1]
            numbers, tokens = numbers[1:], tokens[1:]
        elif len(numbers) > len(periods) + 1:
            raise ValueError("extra_original_monetary_subcolumns_unresolved")
        if len(numbers) == len(periods) and len(note_tokens) <= 1:
            scope = statement_scope(c, pages, header, index + 1)
            sequences.append((numbers, tokens, index + 1, note_tokens, scope))
    expected = old.raw_decimal(c["_raw_value_text"])
    if not sequences or any(values[slots[0]] != expected for values, _, _, _, _ in sequences):
        raise ValueError("independent_original_row_column_alignment_unresolved")
    if len({tuple(values) for values, _, _, _, _ in sequences}) != 1:
        raise ValueError("multiple_original_label_rows_disagree")
    values, tokens, line, notes, scope = sequences[0]
    return dict(
        page=c["page_number"],
        label_line=line,
        period_slot=slots[0] + 1,
        ordered_original_amount_tokens=tokens,
        aligned_amounts=[str(v) for v in values],
        period_columns=periods,
        parser_column_index_is_positioned_word_index_not_period_slot=True,
        parser_flag_alone_not_sufficient=True,
        original_column_header_certificate=header,
        exactly_one_monetary_token_per_period=True,
        explicit_note_column=has_note_column,
        excluded_original_note_tokens=notes,
        unknown_extra_numeric_columns_never_truncated=True,
        original_statement_scope_interval=scope,
    )


def statement_scope(c, pages, header, target_line):
    """Verify the original consolidated title-to-target interval, not a carry flag."""
    first_page, target_page = header["page"], c["page_number"]
    if target_page < first_page:
        raise ValueError("original_scope_target_precedes_statement_header")
    title = old.norm(c["extraction_metadata"]["statement_title"])
    intervals, repeated = [], []
    for page_number in range(first_page, target_page + 1):
        if page_number not in pages:
            raise ValueError("original_scope_intervening_page_missing")
        lines = pages[page_number].splitlines()
        start = header["title_end_line_1based"] if page_number == first_page else 0
        end = target_line - 1 if page_number == target_page else len(lines)
        if end < start:
            raise ValueError("original_scope_target_not_after_bound_header")
        normalized = [old.norm(line) for line in lines]
        index = start
        while index < end:
            match_end = None
            for width in range(1, 5):
                stop = min(index + width, end)
                joined = "".join(normalized[index:stop])
                title_match = STATEMENT_TITLE.search(joined)
                if not title_match:
                    continue
                if index + 1 < stop and STATEMENT_TITLE.search(
                    "".join(normalized[index + 1 : stop])
                ):
                    continue
                if title not in joined and title.startswith(title_match.group(0)) and width < 4:
                    # Long source titles can wrap after "profit or loss".
                    # A matching prefix is not a different statement.
                    continue
                match_end = stop
                context = "".join(normalized[index : min(stop + 3, end)])
                if title not in joined or re.search(
                    r"母公司|parentcompany|separatestatement", context
                ):
                    raise ValueError("original_scope_crossed_other_or_parent_statement")
                if not re.search(
                    r"continued|continuation|续表|續表|续页|續頁|\(续\)|\(續\)", context
                ):
                    raise ValueError("repeated_statement_header_without_explicit_continuation")
                repeated.append(
                    dict(
                        page=page_number,
                        start_line_1based=index + 1,
                        end_line_1based=stop,
                        text="\n".join(lines[index : min(stop + 3, end)]),
                    )
                )
                break
            index = match_end if match_end is not None else index + 1
        intervals.append(
            dict(page=page_number, from_line_1based=start + 1, through_line_1based=end)
        )
    return dict(
        anchor_page=first_page,
        anchor_title_line_1based=header["title_start_line_1based"],
        target_page=target_page,
        target_label_line_1based=target_line,
        inspected_intervals=intervals,
        explicitly_continued_headers=repeated,
        no_intervening_statement_scope_switch=True,
        parser_carry_flag_not_sufficient=True,
    )


def helpers():
    namespace = dict(old.__dict__)
    namespace.update(
        RAW=RAW,
        protocol=protocol,
        save=save,
        annual_period=annual_period,
        instant_period=instant_period,
        row_column_certificate=row_column_certificate,
    )
    for name in ("financial_fact", "document_qualify", "run"):
        original = getattr(old, name)
        function = types.FunctionType(
            original.__code__, namespace, name, original.__defaults__, original.__closure__
        )
        function.__kwdefaults__ = original.__kwdefaults__
        namespace[name] = function
    return namespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.action == "register":
        result = register(args.root.resolve())
    elif args.action == "run":
        result = helpers()["run"](args.root.resolve())
    else:
        result = (
            base.read(RAW / "summary.json")
            if (RAW / "summary.json").exists()
            else protocol(args.root.resolve())
        )
    base.emit(
        dict(
            event="financial_header_revision_" + args.action,
            id=result["id"],
            status=result.get("status"),
        )
    )


if __name__ == "__main__":
    main()
