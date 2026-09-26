"""One prospective cache-only locator revision, not a financial-rule expansion.

Inject into an isolated namespace of the frozen layout module. Only diagnosed
Chinese loss-fill display suffixes, split year/年度 headers and bounded actual
annual dates above a statement title are added. No files or models are accessed.
"""

import re
from datetime import date

import cross_market_layout_qualification_20260926 as frozen

SCRIPT = "trusted_data_synthesis/scripts/cross_market_locator_revision_20260926.py"
VERSION = "cross_market_cache_locator_revision_03.v1"
MAX_PREFIX_LINES = 3
MAX_PREFIX_POINTS = 60.0
MAX_YEAR_SUFFIX_GAP = 12.0
ORDINAL = r"[一二三四五六七八九十0-9、.()（）:：]*"
LOSS_SUFFIXES = {
    "营业利润": {
        frozen.old.norm("（亏损以“－”号填列）"),
        frozen.old.norm('(亏损以"-"号填列)'),
    },
    "净利润": {
        frozen.old.norm("（净亏损以“－”号填列）"),
        frozen.old.norm("（亏损以“－”号填列）"),
        frozen.old.norm('(净亏损以"-"号填列)'),
        frozen.old.norm('(亏损以"-"号填列)'),
    },
}
HEADER_PREFIX_LABELS = {"项目", "項目", "附注", "附註", "note", "notes"}
CN_ANNUAL_END = re.compile(r"(20\d{2})年12月31日止年度")
CN_YEAR_RANGE = re.compile(r"(20\d{2})年1[—－–\-~至]12月")
CN_YEAR_ONLY = re.compile(r"(20\d{2})年度")
CN_DATE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
PURE_UNIT = re.compile(
    r"(?:单位|單位)[:：]?(?:(?:人民币|人民幣|港币|港幣|美元))?"
    r"(?:百万元|百萬元|万元|萬元|千元|元)"
    r"(?:(?:币种|幣種)[:：]?(?:人民币|人民幣|港币|港幣|美元))?|"
    r"(?:币种|幣種)[:：]?(?:人民币|人民幣|港币|港幣|美元)|"
    r"(?:hk\$|us\$|rmb|cny|hkd|usd)(?:million|thousand|['’]000|m|mn)?"
)


def loss_annotation(prefix, c):
    """Exact entire label plus literal registered display note, never substring."""
    label = frozen.old.norm(c["source_field_name"])
    expected_metric = {"营业利润": "operating_income", "净利润": "net_income"}
    if expected_metric.get(label) != c["matched_metric_id"]:
        return None
    for suffix in sorted(LOSS_SUFFIXES.get(label, ())):
        if re.fullmatch(ORDINAL + re.escape(label + suffix), prefix):
            return suffix
    return None


def label_rows(c, lines):
    rows = frozen.label_rows(c, lines)
    for index, line in enumerate(lines):
        candidates = [(line["words"], index, [])]
        if index and not any(frozen._amount(w) is not None for w in lines[index - 1]["words"]):
            if line["y0"] - lines[index - 1]["y1"] <= 8:
                candidates.append((line["words"], index - 1, lines[index - 1]["words"]))
        for words, start, preceding in candidates:
            for stop in range(1, len(words) + 1):
                label_words = preceding + words[:stop]
                prefix = frozen.old.norm(" ".join(w["text"] for w in label_words))
                suffix = loss_annotation(prefix, c)
                if suffix is not None and any(frozen._amount(w) is not None for w in words[stop:]):
                    rows.append(
                        dict(
                            line=line,
                            label_words=label_words,
                            rest=words[stop:],
                            row_start_line=start,
                            row_end_line=index,
                            registered_display_annotation=suffix,
                        )
                    )
    # A separately printed suffix can produce an old partial-label match whose
    # rest begins with that suffix. Use the complete literal match for this same
    # physical row; never merge different rows or discard differing amounts.
    annotated = {
        (r["row_start_line"], r["row_end_line"]): r
        for r in rows
        if r.get("registered_display_annotation")
    }
    result, seen = [], set()
    for row in rows:
        key = row["row_start_line"], row["row_end_line"]
        selected = annotated.get(key, row)
        identity = (key, tuple(w["original_word_index"] for w in selected["label_words"]))
        if identity not in seen:
            seen.add(identity)
            result.append(selected)
    return result


def split_annual_columns(line):
    """Recognize a WHOLE header row; do not coalesce distinct header rows."""
    words = line["words"]
    index, columns = 0, []
    while index < len(words) and frozen.old.norm(words[index]["text"]) in HEADER_PREFIX_LABELS:
        index += 1
    while index < len(words):
        word = words[index]
        token = frozen.old.norm(word["text"])
        match = re.fullmatch(r"(20\d{2})(年度|年)?", token)
        if not match:
            return None
        source_words = [word]
        index += 1
        if not match.group(2) and index < len(words):
            suffix = words[index]
            if frozen.old.norm(suffix["text"]) in {"年度", "年"}:
                if not -1 <= suffix["x0"] - word["x1"] <= MAX_YEAR_SUFFIX_GAP:
                    return None
                source_words.append(suffix)
                index += 1
        columns.append(dict(year=int(match.group(1)), words=source_words))
    return columns if len(columns) == 2 else None


def _data_line(line):
    return False if split_annual_columns(line) is not None else frozen._data_line(line)


def pure_prefix_type(line):
    text, compact = line["text"].strip(), frozen.old.norm(line["text"])
    if (
        CN_ANNUAL_END.fullmatch(compact)
        or CN_YEAR_RANGE.fullmatch(compact)
        or CN_YEAR_ONLY.fullmatch(compact)
        or frozen.old.EN_END.fullmatch(text)
        or frozen.old.EN_END_MONTH_FIRST.fullmatch(text)
    ):
        return "annual"
    if CN_DATE.fullmatch(compact):
        return "date_without_annual_phrase"
    if PURE_UNIT.fullmatch(compact):
        return "unit_traversal_only_not_currency_evidence"
    return None


def prefix_lines(anchor, line_map):
    lines = line_map[anchor["page"]]
    included, inspected = [], []
    for index in range(
        anchor["start_line"] - 1, max(-1, anchor["start_line"] - MAX_PREFIX_LINES - 1), -1
    ):
        line = lines[index]
        if anchor["y0"] - line["y0"] > MAX_PREFIX_POINTS:
            break
        kind = pure_prefix_type(line)
        if kind is None:
            break
        inspected.append(dict(line=line, kind=kind))
        if kind == "annual" or (
            kind == "date_without_annual_phrase" and anchor["statement_type"] == "balance_sheet"
        ):
            included.append(line)
    return list(reversed(included)), list(reversed(inspected))


def header_lines(anchor, line_map):
    lines = line_map[anchor["page"]]
    end = len(lines)
    for index in range(anchor["end_line"], len(lines)):
        if _data_line(lines[index]) or frozen.TITLE.search(frozen.old.norm(lines[index]["text"])):
            end = index
            break
    frozen.fail(end > anchor["end_line"], "geometry_statement_header_empty")
    prefix, _ = prefix_lines(anchor, line_map)
    return prefix + lines[anchor["start_line"] : end]


def explicit_annual_dates(header):
    dates = []
    for line in header:
        compact, text = frozen.old.norm(line["text"]), line["text"].strip()
        # Full dates/ranges outrank year-column labels. Otherwise an above-title
        # 2023 actual date could be silently overridden by 2024 in a year column.
        chinese = (
            CN_ANNUAL_END.fullmatch(compact)
            or CN_YEAR_RANGE.fullmatch(compact)
            or CN_YEAR_ONLY.fullmatch(compact)
        )
        if chinese:
            dates.append(date(int(chinese.group(1)), 12, 31))
        english = frozen.old.EN_END.fullmatch(text)
        if english:
            day, month, year = english.groups()
            dates.append(date(int(year), frozen.old.MONTHS[month.lower()], int(day)))
        english_first = frozen.old.EN_END_MONTH_FIRST.fullmatch(text)
        if english_first:
            month, day, year = english_first.groups()
            dates.append(date(int(year), frozen.old.MONTHS[month.lower()], int(day)))
    return dates


def actual_ends(header, instant):
    explicit = explicit_annual_dates(header)
    try:
        previous, text = frozen.actual_ends(header, instant)
    except ValueError as error:
        if str(error) != "geometry_explicit_actual_annual_date_missing" or not explicit:
            raise
        previous, text = [], "\n".join(line["text"] for line in header)
    ends = explicit if explicit and not instant else previous
    frozen.fail(bool(ends), "geometry_explicit_actual_annual_date_missing")
    frozen.fail(len({(x.month, x.day) for x in ends}) == 1, "geometry_conflicting_actual_end_dates")
    return sorted(set(ends)), text


def wrap_certify(original):
    def certify(c, geometry, prepared=None):
        prepared = prepared or frozen.prepared_geometry(geometry)
        certificate = original(c, geometry, prepared)
        line_map, _ = prepared
        matching = [
            row
            for row in label_rows(c, line_map[c["page_number"]])
            if row["row_start_line"] == certificate["row_start"]
            and row["row_end_line"] == certificate["row"]
        ]
        frozen.fail(len(matching) == 1, "locator_revision_unique_evidence_row")
        row = matching[0]
        prefix, inspected = prefix_lines(certificate["anchor"], line_map)
        header = header_lines(certificate["anchor"], line_map)
        certificate["locator_revision_evidence"] = dict(
            version=VERSION,
            original_printed_label=" ".join(w["text"] for w in row["label_words"]),
            original_label_words=row["label_words"],
            exact_ignored_display_annotation=row.get("registered_display_annotation"),
            numeric_sign_unchanged=True,
            original_pre_title_lines_inspected=inspected,
            original_pre_title_date_lines_included=prefix,
            pre_title_units_not_used_as_currency_evidence=True,
            split_annual_header_rows=[
                dict(line=line, columns=columns)
                for line in header
                if (columns := split_annual_columns(line)) is not None
            ],
            actual_explicit_annual_dates=[d.isoformat() for d in explicit_annual_dates(header)],
            explicit_actual_dates_not_overridden_by_year_column_labels=True,
        )
        return certificate

    return certify


def install(namespace):
    """Root runner owns registration, frozen sources and one uniform pass."""
    frozen.fail(
        namespace["MAX_HEADER_DISTANCE"] == 4
        and namespace["LINE_TOLERANCE"] == 3.0
        and namespace["X_TOLERANCE"] == 38.0,
        "locator_revision_unchanged_layout_thresholds",
    )
    original = namespace["certify"]
    frozen.fail(
        original.__code__ is frozen.certify.__code__, "locator_revision_frozen_certify_parent"
    )
    namespace.update(
        label_rows=label_rows,
        _data_line=_data_line,
        header_lines=header_lines,
        actual_ends=actual_ends,
        certify=wrap_certify(original),
    )
    return namespace
