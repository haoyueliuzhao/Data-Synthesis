"""Prospective exact bilingual displays and physically certified Notes lists.

No source geometry is edited or shadowed. Root registers the new one-pass budget.
The certification function below copies the frozen geometric certificate with
only its Notes extraction block changed, and extra raw-evidence fields appended.
"""

# ruff: noqa: F821 -- copied certify body is compiled into the validated layout namespace.

import re
import types

import cross_market_layout_qualification_20260926 as frozen
import cross_market_locator_revision_20260926 as v3

SCRIPT = "trusted_data_synthesis/scripts/cross_market_row_binding_revision_20260926.py"
VERSION = "cross_market_exact_row_binding_revision_04.v1"
MAX_COMPOUND_NOTE_REFERENCES = 3
MAX_BILINGUAL_NOTE_HEADER_VERTICAL_SPAN = 36.0
MAX_NOTE_WORD_GAP = 12.0
PAIR_LABELS = {
    "gross_profit": {"grossprofit": {"毛利"}},
    "cost_of_revenue": {
        "costofsales": {"銷售成本", "销售成本"},
        "costofrevenue": {"銷售成本", "销售成本"},
        "costofrevenues": {"銷售成本", "销售成本"},
    },
    "revenue": {"revenue": {"收入", "收益"}, "revenues": {"收入", "收益"}},
}
NOTE_EN = {"note", "notes"}
NOTE_ZH = {"附注", "附註", "注", "註"}
LEGACY_NOTE = re.compile(
    r"(?:\d+[a-z]?\([a-z0-9]+\)|[一二三四五六七八九十]+、\d+|\([a-z0-9]+\)|[a-z])"
)
THOUSANDS_AMOUNT = re.compile(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def registered_display(prefix, c):
    english = frozen.old.norm(c["source_field_name"])
    for chinese in sorted(PAIR_LABELS.get(c["matched_metric_id"], {}).get(english, ())):
        for exact in (english + chinese, chinese + english):
            if re.fullmatch(v3.ORDINAL + re.escape(exact), prefix):
                return dict(
                    rule="exact_registered_bilingual_display_pair",
                    authoritative_original_label=english,
                    duplicate_display_label=chinese,
                )
    if c["matched_metric_id"] == "cost_of_revenue" and english == "营业成本":
        if re.fullmatch(v3.ORDINAL + r"(?:减|減):营业成本", prefix):
            return dict(
                rule="literal_expense_presentation_prefix",
                authoritative_original_label=english,
                prefix_is_not_numeric_sign=True,
            )
    return None


def label_rows(c, lines):
    rows = v3.label_rows(c, lines)
    complete = {}
    for index, line in enumerate(lines):
        for stop in range(1, len(line["words"]) + 1):
            prefix_words = line["words"][:stop]
            prefix = frozen.old.norm(" ".join(w["text"] for w in prefix_words))
            display = registered_display(prefix, c)
            rest = line["words"][stop:]
            if display is None or not any(frozen._amount(w) is not None for w in rest):
                continue
            row = dict(
                line=line,
                label_words=prefix_words,
                rest=rest,
                row_start_line=index,
                row_end_line=index,
                row_binding_display_certificate=display,
            )
            key = index, index
            frozen.fail(key not in complete, "row_binding_multiple_complete_display_matches")
            complete[key] = row
    result, seen = [], set()
    for row in [*rows, *complete.values()]:
        key = row["row_start_line"], row["row_end_line"]
        selected = complete.get(key, row)
        identity = key, tuple(w["original_word_index"] for w in selected["label_words"])
        if identity not in seen:
            result.append(selected)
            seen.add(identity)
    return result


def notes_column(header, columns):
    words = [
        w
        for line in header
        for w in line["words"]
        if frozen.old.norm(w["text"]) in NOTE_EN | NOTE_ZH
    ]
    if not words:
        return dict(unique=False, reason="no_original_Notes_header", header_words=[])
    if len(words) == 1:
        selected = words
    elif len(words) == 2:
        languages = {"en" if frozen.old.norm(w["text"]) in NOTE_EN else "zh" for w in words}
        overlap = min(w["x1"] for w in words) - max(w["x0"] for w in words)
        yspan = max(w["y1"] for w in words) - min(w["y0"] for w in words)
        if (
            languages != {"en", "zh"}
            or overlap <= 0
            or yspan > MAX_BILINGUAL_NOTE_HEADER_VERTICAL_SPAN
        ):
            return dict(
                unique=False,
                reason="ambiguous_or_spatially_distinct_Notes_headers",
                header_words=words,
            )
        selected = words
    else:
        return dict(unique=False, reason="multiple_original_Notes_headers", header_words=words)
    right = max(w["x1"] for w in selected)
    if right >= columns[0]["x0"] - 15:
        return dict(
            unique=False, reason="Notes_header_not_separate_from_year_columns", header_words=words
        )
    return dict(
        unique=True,
        header_words=selected,
        x0=min(w["x0"] for w in selected),
        x1=right,
        bilingual_same_physical_column=len(selected) == 2,
        shared_horizontal_interval=[max(w["x0"] for w in selected), min(w["x1"] for w in selected)],
    )


def note_position(word, column, first_year):
    return (
        column["unique"]
        and word["x1"] < first_year["x0"] - 15
        and abs(word["x1"] - column["x1"]) <= frozen.X_TOLERANCE
    )


def parse_note_words(words):
    frozen.fail(
        bool(words) and len(words) <= 2 * MAX_COMPOUND_NOTE_REFERENCES - 1,
        "row_binding_note_token_bound",
    )
    for left, right in zip(words, words[1:], strict=False):
        frozen.fail(
            -1 <= right["x0"] - left["x1"] <= MAX_NOTE_WORD_GAP,
            "row_binding_notes_not_one_contiguous_physical_cell",
        )
    text = frozen.old.norm("".join(w["text"] for w in words))
    if re.fullmatch(r"\d+", text) and len(words) == 1:
        return dict(kind="single_integer_note", references=[text], raw_joined_text=text)
    if re.fullmatch(r"\d+(?:,\d+){1,2}", text):
        frozen.fail(
            not THOUSANDS_AMOUNT.fullmatch(text),
            "row_binding_ambiguous_thousands_amount_not_a_note_list",
        )
        references = text.split(",")
        frozen.fail(
            len(references) <= MAX_COMPOUND_NOTE_REFERENCES
            and len(set(references)) == len(references),
            "row_binding_integer_note_list_bound",
        )
        return dict(
            kind="explicit_comma_separated_integer_note_list",
            references=references,
            raw_joined_text=text,
        )
    if len(words) == 1 and LEGACY_NOTE.fullmatch(text) and frozen._amount(words[0]) is None:
        return dict(
            kind="frozen_legacy_single_note_syntax", references=[text], raw_joined_text=text
        )
    raise ValueError("geometry_unknown_nonmonetary_row_tokens")


def bind_row_amounts(row, header, columns):
    """Remove only an explicitly proven Notes cell, before numeric conversion."""
    column = notes_column(header, columns)
    words = row["rest"]
    in_notes = [w for w in words if note_position(w, column, columns[0])]
    excluded, syntax = [], None
    if in_notes:
        frozen.fail(
            words[: len(in_notes)] == in_notes, "row_binding_Notes_must_precede_monetary_columns"
        )
        syntax = parse_note_words(in_notes)
        excluded = in_notes
    remaining = words[len(excluded) :]
    # 5,8 is not the amount 58. A comma list outside a proven Notes cell is
    # rejected; ordinary, correctly grouped thousands remain original amounts.
    for word in remaining:
        text = frozen.old.norm(word["text"])
        frozen.fail(
            not (re.fullmatch(r"\d+(?:,\d+)+", text) and not THOUSANDS_AMOUNT.fullmatch(text)),
            "row_binding_compound_note_outside_unique_Notes_column",
        )
    amounts = [w for w in remaining if frozen._amount(w) is not None]
    others = [w for w in remaining if frozen._amount(w) is None]
    if len(amounts) == 3 and not excluded:
        raise ValueError("geometry_extra_numeric_column_not_certified_note")
    frozen.fail(len(amounts) == len(columns) == 2, "geometry_exact_monetary_column_cardinality")
    frozen.fail(not others, "geometry_unknown_nonmonetary_row_tokens")
    proof = dict(
        column=column,
        original_excluded_words=excluded,
        note_syntax=syntax,
        original_geometry_unchanged=True,
        source_word_indices_unchanged=True,
        unknown_tokens_never_discarded=True,
        no_rightmost_numeric_truncation=True,
    )
    return amounts, excluded, proof


def row_locator_evidence(c, row, anchor, header, line_map):
    prefix, inspected = v3.prefix_lines(anchor, line_map)
    return dict(
        version=v3.VERSION,
        original_printed_label=" ".join(w["text"] for w in row["label_words"]),
        original_label_words=row["label_words"],
        exact_ignored_display_annotation=row.get("registered_display_annotation"),
        numeric_sign_unchanged=True,
        original_pre_title_lines_inspected=inspected,
        original_pre_title_date_lines_included=prefix,
        pre_title_units_not_used_as_currency_evidence=True,
        split_annual_header_rows=[
            dict(line=line, columns=cols)
            for line in header
            if (cols := v3.split_annual_columns(line)) is not None
        ],
        actual_explicit_annual_dates=[d.isoformat() for d in v3.explicit_annual_dates(header)],
        explicit_actual_dates_not_overridden_by_year_column_labels=True,
    )


def certify_row_binding(c, geometry, prepared=None):
    line_map, title_map = prepared or prepared_geometry(geometry)
    fail(c["page_number"] in line_map, "geometry_candidate_page_missing")
    rows = label_rows(c, line_map[c["page_number"]])
    row, anchor = locate_statement(c, rows, title_map, line_map)
    header = header_lines(anchor, line_map)
    ends, header_text = actual_ends(header, c["matched_metric_id"] == "cash_and_cash_equivalents")
    fail(not RESTATED.search(header_text), "geometry_restatement_column_pending_review")
    columns = year_columns(header, ends)
    unit = unit_certificate(c, header)
    amounts, excluded, note_certificate = bind_row_amounts(row, header, columns)
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
        note_binding_certificate=note_certificate,
        locator_revision_evidence=row_locator_evidence(c, row, anchor, header, line_map),
        row_binding_revision_evidence=dict(
            version=ROW_BINDING_VERSION,
            display=row.get("row_binding_display_certificate"),
            original_label_words=row["label_words"],
            original_amount_words=amounts,
            geometry_never_shadowed_or_edited=True,
        ),
        header_binding_revision_evidence=(
            header_binding_proof(anchor, header, ends, columns)
            if "header_binding_proof" in globals()
            else None
        ),
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


def install_row_namespace(namespace):
    """Install after v3 and the new header adapter; preserve dynamic helpers."""
    frozen.fail(
        namespace["MAX_HEADER_DISTANCE"] == 4
        and namespace["LINE_TOLERANCE"] == 3.0
        and namespace["X_TOLERANCE"] == 38.0,
        "row_binding_unchanged_layout_thresholds",
    )
    frozen.fail(
        namespace["financial_facts"].__code__ is frozen.financial_facts.__code__,
        "row_binding_frozen_financial_semantics",
    )
    frozen.fail(
        {
            "prepared_geometry",
            "fail",
            "locate_statement",
            "header_lines",
            "actual_ends",
            "RESTATED",
            "year_columns",
            "unit_certificate",
            "X_TOLERANCE",
            "date",
            "timedelta",
            "_amount",
        }
        <= set(namespace),
        "row_binding_required_namespace",
    )
    namespace.update(
        label_rows=label_rows,
        bind_row_amounts=bind_row_amounts,
        row_locator_evidence=row_locator_evidence,
        ROW_BINDING_VERSION=VERSION,
    )
    namespace["certify"] = types.FunctionType(
        certify_row_binding.__code__,
        namespace,
        "certify",
        certify_row_binding.__defaults__,
        certify_row_binding.__closure__,
    )
    return namespace
