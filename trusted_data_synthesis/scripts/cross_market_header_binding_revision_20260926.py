"""Audited header/date/unit representations, injected into an isolated v3 core.

Pure cached-word operations. No PDF, file, network, model or qualification run.
Raw words and positions remain unchanged; semantic/version warnings still block.
"""

import re
from datetime import date

import cross_market_layout_qualification_20260926 as core
import cross_market_locator_revision_20260926 as v3

SCRIPT = "trusted_data_synthesis/scripts/cross_market_header_binding_revision_20260926.py"
VERSION = "cross_market_header_binding_revision_04.v1"
MONTHS = "|".join(core.old.MONTHS)
YEAR_LIST = r"(?P<years>20\d{2}(?:(?:and|,|&)20\d{2})*)?"
EN_DAY_FIRST = re.compile(
    r"(?:forthe)?years?ended(?P<day>\d{1,2})(?P<ordinal>st|nd|rd|th)?"
    r"(?P<month>" + MONTHS + r"),?" + YEAR_LIST
)
EN_MONTH_FIRST = re.compile(
    r"(?:forthe)?years?ended(?P<month>" + MONTHS + r")"
    r"(?P<day>\d{1,2})(?P<ordinal>st|nd|rd|th)?,?" + YEAR_LIST
)
MAX_UNIT_WORDS = 6
MAX_UNIT_GAP = 12.0
MAX_TITLE_PHYSICAL_LINES = 6
MAX_TITLE_POINTS = 90.0
NAVIGATION_GAP = 10.0
NAVIGATION = {"keyfigures", "editorial", "managementreport", "accounts", "ourcompany"}
TITLE_PAIRS = (("consolidated", "incomestatement"), ("consolidatedstatementof", "profitorloss"))
SHORT_DATE = re.compile(r"12/31/(\d{2})")
YEAR_TOKEN = re.compile(r"(20\d{2})(?:年度|年)?")
FULL_CN_DATE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
VERSION_NOTE = re.compile(r"\(note(?:[0-9]+[a-z]?(?:\.[0-9]+)*)?\)", re.I)


def compact(text):
    return core.old.norm(text).replace("’", "'").replace("‘", "'")


def annual_line(line):
    """Match one complete annual sentence, including spaced glyphs, not body prose."""
    text = compact(line["text"])
    match = EN_DAY_FIRST.fullmatch(text) or EN_MONTH_FIRST.fullmatch(text)
    if match:
        day = int(match.group("day"))
        ordinal = match.group("ordinal")
        expected = (
            "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        )
        core.fail(not ordinal or ordinal == expected, "header_invalid_ordinal_day")
        month = core.old.MONTHS[match.group("month")]
        years = [int(y) for y in re.findall(r"20\d{2}", match.group("years") or "")]
        core.fail(
            len(years) <= 2 and len(years) == len(set(years)),
            "header_more_than_two_or_duplicate_actual_annual_years",
        )
        date(years[0] if years else 2000, month, day)
        return dict(
            month=month,
            day=day,
            years=years,
            original_text=line["text"],
            original_word_indices=[w["original_word_index"] for w in line["words"]],
            line_index=line["line_index"],
            grammar="whole_original_English_annual_sentence",
        )
    match = (
        v3.CN_ANNUAL_END.fullmatch(text)
        or v3.CN_YEAR_RANGE.fullmatch(text)
        or v3.CN_YEAR_ONLY.fullmatch(text)
    )
    if match:
        return dict(
            month=12,
            day=31,
            years=[int(match.group(1))],
            original_text=line["text"],
            original_word_indices=[w["original_word_index"] for w in line["words"]],
            line_index=line["line_index"],
            grammar="whole_original_Chinese_annual_sentence",
        )
    return None


def signals(header):
    return [value for line in header if (value := annual_line(line)) is not None]


def unit_scale(text):
    token = compact(text).strip("()（）,:：")
    # Currency must still be uniquely proved elsewhere in the same valid
    # header; these are exact bare unit tokens, never substring guesses.
    if token in {"million", "millions"}:
        return 1000000
    if token in {"thousand", "thousands", "'000"}:
        return 1000
    if re.fullmatch(r"(?:hk\$|us\$|rmb|cny|hkd|usd)(?:m|mn|million)", token):
        return 1000000
    if re.fullmatch(r"(?:hk\$|us\$|rmb|cny|hkd|usd)(?:'000|000|thousand)", token):
        return 1000
    for suffix, scale in (
        ("百万元|百萬元|百萬圆|百萬圓", 1000000),
        ("万元|萬元", 10000),
        ("千元", 1000),
    ):
        if re.fullmatch(
            r"(?:(?:单位|單位)[:：]?)?(?:人民币|人民幣|港币|港幣|美元)?(?:" + suffix + ")", token
        ):
            return scale
    if re.fullmatch(r"(?:单位|單位)[:：]?(?:人民币|人民幣|港币|港幣|美元)?元", token):
        return 1
    if re.fullmatch(r"in(?:hk\$|us\$|rmb|hkd|usd)", token):
        return 1
    return None


def unit_witnesses(line):
    result = []
    words = line["words"]
    for start in range(len(words)):
        for end in range(start + 1, min(len(words), start + MAX_UNIT_WORDS) + 1):
            selected = words[start:end]
            if any(
                not -1 <= b["x0"] - a["x1"] <= MAX_UNIT_GAP
                for a, b in zip(selected, selected[1:], strict=False)
            ):
                break
            scale = unit_scale(" ".join(w["text"] for w in selected))
            if scale is not None:
                result.append(
                    dict(
                        scale=scale,
                        original_text=" ".join(w["text"] for w in selected),
                        word_indices=[w["original_word_index"] for w in selected],
                        line_index=line["line_index"],
                    )
                )
    return result


def unit_only_line(line):
    witnesses = unit_witnesses(line)
    if not witnesses:
        return False
    covered = {i for w in witnesses for i in w["word_indices"]}
    remainder = [
        compact(w["text"]) for w in line["words"] if w["original_word_index"] not in covered
    ]
    return all(t in {"note", "notes", "附注", "附註", "单位", "單位", ":", "："} for t in remainder)


def _data_line(line):
    return False if annual_line(line) or unit_only_line(line) else v3._data_line(line)


def prefix_lines(anchor, line_map):
    included, inspected = [], []
    lines = line_map[anchor["page"]]
    for index in range(
        anchor["start_line"] - 1, max(-1, anchor["start_line"] - v3.MAX_PREFIX_LINES - 1), -1
    ):
        line = lines[index]
        if anchor["y0"] - line["y0"] > v3.MAX_PREFIX_POINTS:
            break
        signal = annual_line(line)
        kind = "annual" if signal else v3.pure_prefix_type(line)
        if kind is None:
            break
        inspected.append(dict(line=line, kind=kind))
        if kind == "annual" or (
            kind == "date_without_annual_phrase" and anchor["statement_type"] == "balance_sheet"
        ):
            included.append(line)
    return list(reversed(included)), list(reversed(inspected))


def exact_spans(line, target):
    words = line["words"]
    result = []
    for start in range(len(words)):
        text = ""
        for end in range(start, min(len(words), start + 40)):
            text += compact(words[end]["text"])
            if not target.startswith(text):
                break
            if text == target:
                result.append(words[start : end + 1])
                break
    return result


def title_spans(page, lines):
    original = core.title_spans(page, lines)
    recovered = []
    for first, second in TITLE_PAIRS:
        for start, line in enumerate(lines):
            for top in exact_spans(line, first):
                for end in range(start + 1, min(len(lines), start + MAX_TITLE_PHYSICAL_LINES)):
                    for bottom in exact_spans(lines[end], second):
                        words = top + bottom
                        x0, x1 = min(w["x0"] for w in words), max(w["x1"] for w in words)
                        y0, y1 = min(w["y0"] for w in words), max(w["y1"] for w in words)
                        if (
                            y1 - y0 > MAX_TITLE_POINTS
                            or abs(top[0]["x0"] - bottom[0]["x0"]) > core.X_TOLERANCE
                        ):
                            continue
                        indices = {w["original_word_index"] for w in words}
                        excluded, valid = [], True
                        for part in lines[start : end + 1]:
                            other = [
                                w for w in part["words"] if w["original_word_index"] not in indices
                            ]
                            if not other:
                                continue
                            if compact(
                                " ".join(w["text"] for w in other)
                            ) not in NAVIGATION or not all(
                                w["x1"] <= x0 - NAVIGATION_GAP or w["x0"] >= x1 + NAVIGATION_GAP
                                for w in other
                            ):
                                valid = False
                                break
                            excluded.extend(other)
                        if not valid or not excluded:
                            continue
                        recovered.append(
                            dict(
                                page=page,
                                start_line=start,
                                end_line=end + 1,
                                y0=y0,
                                y1=y1,
                                text="\n".join(
                                    " ".join(w["text"] for w in group) for group in (top, bottom)
                                ),
                                statement_type="income_statement",
                                consolidated=True,
                                parent=False,
                                header_binding_title_recovery=dict(
                                    version=VERSION,
                                    selected_original_words=words,
                                    excluded_navigation_words=excluded,
                                    maximum_physical_lines=MAX_TITLE_PHYSICAL_LINES,
                                    maximum_vertical_points=MAX_TITLE_POINTS,
                                    navigation_outside_title_x_corridor=True,
                                ),
                            )
                        )
    # Only an unambiguous physical title gets restored. Never delete a parent
    # boundary, or a competing explicit consolidated title.
    unique = []
    for title in recovered:
        peers = [
            q
            for q in recovered
            if not (q["end_line"] <= title["start_line"] or q["start_line"] >= title["end_line"])
        ]
        if len(peers) != 1:
            continue
        if any(
            q["parent"] or q["consolidated"]
            for q in original
            if title["start_line"] <= q["start_line"] < title["end_line"]
        ):
            continue
        unique.append(title)
    original = [
        q
        for q in original
        if not any(
            t["start_line"] < q["start_line"] < t["end_line"]
            and q["end_line"] <= t["end_line"]
            and not q["parent"]
            and not q["consolidated"]
            for t in unique
        )
    ]
    return sorted(original + unique, key=lambda t: (t["start_line"], t["end_line"]))


def semantic_scope_gate(anchor, header, statement_lines):
    text = "\n".join(line["text"] for line in header)
    normalized = compact(text)
    core.fail(not core.RESTATED.search(text), "header_explicit_restatement_pending_review")
    core.fail(
        not re.search(r"continuingoperations|discontinuedoperations|持续经营|持續經營", normalized),
        "header_operating_scope_pending_review",
    )
    # A normal Notes/附注 column is never a warning. Parenthesized comparative
    # notes require proximity and x alignment to actual printed year columns.
    year_rows = []
    for line in header:
        if annual_line(line):
            continue
        columns = [
            w
            for w in line["words"]
            if YEAR_TOKEN.fullmatch(compact(w["text"]))
            or SHORT_DATE.fullmatch(compact(w["text"]))
            or FULL_CN_DATE.fullmatch(compact(w["text"]))
        ]
        if len(columns) >= 2:
            year_rows.append((line, columns))
    for line in header:
        if not VERSION_NOTE.search(compact(line["text"])):
            continue
        notes = []
        for start in range(len(line["words"])):
            for end in range(start + 1, min(len(line["words"]), start + 4) + 1):
                words = line["words"][start:end]
                close = all(
                    -1 <= b["x0"] - a["x1"] <= MAX_UNIT_GAP
                    for a, b in zip(words, words[1:], strict=False)
                )
                if close and VERSION_NOTE.fullmatch(compact(" ".join(w["text"] for w in words))):
                    notes.append(
                        dict(x0=min(w["x0"] for w in words), x1=max(w["x1"] for w in words))
                    )
        for years, columns in year_rows:
            if not (
                0 <= line["line_index"] - years["line_index"] <= 4
                and 0 <= line["y0"] - years["y0"] <= 40
            ):
                continue
            for word in notes:
                if any(
                    min(
                        abs(word["x1"] - c["x1"]),
                        abs((word["x0"] + word["x1"] - c["x0"] - c["x1"]) / 2),
                    )
                    <= core.X_TOLERANCE
                    for c in columns
                ):
                    raise ValueError("header_comparative_note_pending_review")
    page_text = compact("\n".join(line["text"] for line in statement_lines))
    transition = re.search(r"(?:hkfrs|ifrs|会计准则|會計準則)", page_text) and re.search(
        r"initiallyappl|initialadopt|first(?:time)?adopt|first(?:time)?appl|首次(?:采用|採用|应用|應用|执行|執行)",
        page_text,
    )
    comparison = re.search(
        r"comparative(?:information|figures|amounts|data).{0,80}(?:not(?:been)?restated|reclassified)|比较.{0,35}(?:不重述|重分类)|比較.{0,35}(?:不重述|重新分類)",
        page_text,
    )
    core.fail(
        not transition and not comparison,
        "header_accounting_transition_or_comparative_basis_pending",
    )


def header_lines(anchor, line_map):
    lines = line_map[anchor["page"]]
    next_titles = [
        t["start_line"]
        for t in title_spans(anchor["page"], lines)
        if t["start_line"] >= anchor["end_line"]
    ]
    scope_end = min(next_titles, default=len(lines))
    end = scope_end
    for index in range(anchor["end_line"], scope_end):
        if _data_line(lines[index]):
            end = index
            break
    core.fail(end > anchor["end_line"], "geometry_statement_header_empty")
    prefix, _ = prefix_lines(anchor, line_map)
    header = prefix + lines[anchor["start_line"] : end]
    semantic_scope_gate(anchor, header, lines[anchor["start_line"] : scope_end])
    return header


def four_digit_columns(header):
    result = []
    for line in header:
        if annual_line(line):
            continue
        columns = [w for w in line["words"] if YEAR_TOKEN.fullmatch(compact(w["text"]))]
        if len(columns) >= 2:
            core.fail(len(columns) == 2, "geometry_more_than_two_year_columns_unresolved")
            result.append([int(YEAR_TOKEN.fullmatch(compact(w["text"])).group(1)) for w in columns])
    core.fail(
        len(result) == 1 and len(set(result[0])) == 2,
        "header_partial_date_requires_one_original_two_year_column_row",
    )
    return result[0]


def actual_ends(header, instant):
    text = "\n".join(line["text"] for line in header)
    normalized = compact(text)
    core.fail(
        not core.old.UNUSUAL_ANNUAL.search(text)
        and not re.search(
            r"(?:52|53)weeks|[0-9]+个月|[0-9]+個月|quarter|unaudited|未审计|未經審核", normalized
        ),
        "geometry_noncalendar_or_changed_annual_header",
    )
    if instant:
        return v3.actual_ends(header, instant)
    annual = signals(header)
    if not annual:
        return v3.actual_ends(header, instant)
    core.fail(
        len({(s["month"], s["day"]) for s in annual}) == 1, "geometry_conflicting_actual_end_dates"
    )
    explicit = [date(y, s["month"], s["day"]) for s in annual for y in s["years"]]
    if explicit:
        return sorted(set(explicit)), text
    years = four_digit_columns(header)
    return sorted(date(y, annual[0]["month"], annual[0]["day"]) for y in years), text


def year_columns(header, ends):
    choices = []
    printed_actual_years = {y for signal in signals(header) for y in signal["years"]}
    for line in header:
        if annual_line(line):
            continue
        columns = []
        for word in line["words"]:
            token = compact(word["text"])
            match = YEAR_TOKEN.fullmatch(token)
            full = FULL_CN_DATE.fullmatch(token)
            short = SHORT_DATE.fullmatch(token)
            if match or full:
                year = int((match or full).group(1))
                if full:
                    core.fail(
                        (int(full.group(2)), int(full.group(3))) == (ends[-1].month, ends[-1].day),
                        "geometry_printed_column_end_date_disagrees",
                    )
                columns.append(dict(word, year=year, year_basis="printed_absolute_year"))
            elif short:
                years = [y for y in printed_actual_years if y % 100 == int(short.group(1))]
                core.fail(
                    len(years) == 1 and (ends[-1].month, ends[-1].day) == (12, 31),
                    "header_short_date_requires_printed_four_digit_actual_year",
                )
                columns.append(
                    dict(
                        word,
                        year=years[0],
                        year_basis="short_date_bound_to_explicit_four_digit_annual_year",
                        printed_four_digit_annual_years=sorted(printed_actual_years),
                    )
                )
            elif token in core.RELATIVE_YEAR:
                columns.append(
                    dict(
                        word,
                        year=max(d.year for d in ends) + core.RELATIVE_YEAR[token],
                        year_basis="printed_relative_column_with_actual_annual_date",
                    )
                )
        if len(columns) >= 2:
            core.fail(len(columns) == 2, "geometry_more_than_two_year_columns_unresolved")
            core.fail(
                columns[0]["year"] != columns[1]["year"],
                "geometry_same_year_semantic_subcolumns_unresolved",
            )
            choices.append(columns)
    core.fail(bool(choices), "geometry_two_printed_year_columns_missing")
    core.fail(len(choices) == 1, "geometry_multiple_year_header_rows_unresolved")
    return sorted(choices[0], key=lambda w: w["x0"])


def unit_certificate(c, header):
    text = "\n".join(line["text"] for line in header)
    normalized = compact(text)
    currencies = {currency for currency, regex in core.CURRENCY.items() if regex.search(normalized)}
    core.fail(len(currencies) == 1, "geometry_currency_missing_or_multiple")
    witnesses = [w for line in header for w in unit_witnesses(line)]
    scales = {w["scale"] for w in witnesses}
    core.fail(len(scales) == 1, "geometry_native_scale_unresolved")
    core.fail(
        not core.previous.COMPLEX_SUBCOLUMNS.search(normalized),
        "geometry_group_company_or_semantic_subcolumns_unresolved",
    )
    return dict(
        currency=next(iter(currencies)),
        scale=next(iter(scales)),
        original_header=text,
        source="original_header_token_boundaries_not_global_join",
        unit_token_witnesses=witnesses,
        above_title_units_used=False,
    )


def header_binding_proof(anchor, header, ends, columns):
    return dict(
        version=VERSION,
        original_header_lines=header,
        original_annual_signals=signals(header),
        actual_end_dates=[d.isoformat() for d in ends],
        original_year_columns=columns,
        bounded_title_geometry=anchor.get("header_binding_title_recovery"),
        above_title_unit_borrowing=False,
        metadata_year_used=False,
        original_word_indices_and_signs_unchanged=True,
        continuing_operations_comparative_notes_and_accounting_transition_not_waived=True,
    )


def install_header_namespace(namespace):
    core.fail(
        namespace["MAX_HEADER_DISTANCE"] == 4
        and namespace["LINE_TOLERANCE"] == 3
        and namespace["X_TOLERANCE"] == 38,
        "header_unchanged_legacy_layout_thresholds",
    )
    namespace.update(
        title_spans=title_spans,
        header_lines=header_lines,
        actual_ends=actual_ends,
        year_columns=year_columns,
        unit_certificate=unit_certificate,
        _data_line=_data_line,
        header_binding_proof=header_binding_proof,
    )
    return namespace
