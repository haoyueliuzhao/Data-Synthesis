"""Company-specific FCF tables, compiled from original local annual reports.

This is a bounded structured-document adapter, not a list of company/year
answers. A table must have an issuer definition, a complete signed reconciliation
and a same-filing native USD operating-cash-flow anchor. Unsupported layouts,
unexplained dashes, changed definitions and missing source anchors fail closed.
"""

import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal, InvalidOperation

from lxml import html

from .archive import record, require
from .protocol import source_identity

FCF = "issuer_defined_free_cash_flow"
CFO = "net_cash_provided_by_used_in_operating_activities"
LOGICAL_AMOUNT_RULE = "unique_annual_body_directional_adjacent_symbols_v1"
PRINTED_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
MONTHS = (
    "January February March April May June July August September October November December"
).split()
MONTH_RE = "|".join(MONTHS)
DATE_RE = re.compile(rf"\b({MONTH_RE})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", re.I)
MONTH_DAY_RE = re.compile(rf"\b({MONTH_RE})\s+(\d{{1,2}}),?\b", re.I)
DEFINITION_RE = re.compile(
    r"\b(?:we\s+(?:define|calculate)\s+(?:non-GAAP\s+)?free cash flow"
    r"|free cash flow(?:,\s*[^.]{0,100},)?\s+(?:is|was)\s+(?:calculated|defined))"
    r"[^.:]{0,1000}[.:]",
    re.I,
)
TOTAL_RE = re.compile(r"^(?:non-gaap\s+)?free cash flow(?:\s*\(non-gaap\))?\s*[*]?$", re.I)
CFO_RE = re.compile(
    r"^(?:gaap\s+)?(?:net\s+cash\s+(?:provided\s+by|from)\s+operating\s+activities"
    r"|cash\s+provided\s+by\s+operating\s+activities"
    r"|cash\s+flows?\s+from\s+(?:operations|operating\s+activities))"
    r"(?:\s*\(gaap\))?\s*[*]?$",
    re.I,
)

FORMULA_WORDS = set(
    "we define defines defined calculate calculated calculation free cash flow flows non gaap "
    "financial "
    "measure measures as is net provided by from operating activities operations less minus plus "
    "and to outflows for legal settlements settlement business combination other related costs "
    "including compensation expense expenses reduced purchases purchase acquire acquisition "
    "acquisitions of property equipment capital expenditures expenditure also referred the used "
    "proceeds chips act incentives sales sale assets asset disposal dividend dividends payments "
    "paid investing in a an follows".split()
)


def component_roles(value):
    lower = value.lower()
    roles = set()
    if re.search(r"operating activities|cash flows? from operations", lower):
        roles.add("operating_cash_flow")
    if re.search(r"capital expenditures?|property and equipment", lower):
        roles.add("capital_expenditure")
    if re.search(r"legal settlements?", lower):
        roles.add("legal_settlement")
    if "business combination" in lower:
        roles.add("business_combination")
    if "chips" in lower and "incentive" in lower:
        roles.add("CHIPS_proceeds")
    if "dividend" in lower:
        roles.add("dividends")
    if "investing activities" in lower:
        roles.add("investing_cash_flow")
    if "proceeds" in lower and re.search(r"sale|disposal", lower) and "asset" in lower:
        roles.add("asset_disposal_proceeds")
    return roles


def validate_definition_shape(quote, component_labels):
    """Finite, fail-closed formula vocabulary, never just a keyword + closure."""
    row_roles = [component_roles(label) for label in component_labels]
    require(
        all(len(roles) == 1 for roles in row_roles),
        "issuer.unsupported_or_ambiguous_component_role",
    )
    require(
        len(set.union(*row_roles)) == len(row_roles), "issuer.duplicate_financial_component_role"
    )
    require(
        row_roles[0] == {"operating_cash_flow"}, "issuer.first_component_is_operating_cash_flow"
    )
    if re.fullmatch(r"We calculate (?:non-GAAP )?free cash flow as follows:", quote, re.I):
        return
    if re.fullmatch(
        r"Free cash flow (?:was|is) calculated by subtracting capital expenditures from "
        r"the most directly comparable GAAP measure, cash flows from operating activities "
        r"\(also referred to as cash flow from operations\)\.",
        quote,
        re.I,
    ):
        require(
            row_roles == [{"operating_cash_flow"}, {"capital_expenditure"}],
            "issuer.subtraction_clause_complete_roles",
        )
        return
    words = set(re.findall(r"[a-z]+", quote.lower()))
    require(words <= FORMULA_WORDS, "issuer.uninterpreted_definition_vocabulary")
    require(
        component_roles(quote) == set.union(*row_roles),
        "issuer.definition_and_complete_row_roles_disagree",
    )
    segments = re.split(r"\b(?:plus|less|minus|reduced by)\b", quote, flags=re.I)
    require(
        len(segments) >= 2 and all(component_roles(segment) for segment in segments),
        "issuer.uninterpreted_additive_definition_segment",
    )


def text(element):
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _cover_dom_segments(document_tree, start, end):
    """Recover a normalized cover span from exact original DOM text/tail slices."""
    position, segments = 0, []
    for original in document_tree.xpath(".//text()"):
        raw = str(original)
        normalized = " ".join(raw.split())
        if not normalized:
            continue
        left, right = position, position + len(normalized)
        position = right + 1
        if right <= start or left >= end:
            continue
        tokens = list(re.finditer(r"\S+", raw))
        cursor, chosen = left, []
        for token in tokens:
            token_end = cursor + len(token.group(0))
            if token_end > start and cursor < end:
                chosen.append((token, cursor, token_end))
            cursor = token_end + 1
        require(bool(chosen), "issuer.cover_original_DOM_tokens")
        raw_start, raw_end = chosen[0][0].start(), chosen[-1][0].end()
        parent = original.getparent()
        segments.append(
            {
                "element_xpath": parent.getroottree().getpath(parent),
                "slot": "tail" if original.is_tail else "text",
                "raw_character_span": [raw_start, raw_end],
                "raw_text": raw[raw_start:raw_end],
                "normalized_document_span": [chosen[0][1], chosen[-1][2]],
            }
        )
    return segments


def annual_report_cover(document_tree):
    """Locate UNP's actual SEC annual-report cover, not mentions of old 10-Ks.

    No archive year, known text offset, table amount, or closure enters selection.
    The fixed semantic sequence distinguishes a cover from prose citations and
    remains valid when inline XBRL splits the date around its comma.
    """
    document_text = text(document_tree)
    legal = (
        r"REPORT\s+PURSUANT\s+TO\s+SECTION\s+13\s+OR\s+15\(d\)\s+OF\s+THE\s+"
        r"SECURITIES\s+EXCHANGE\s+ACT\s+OF\s+1934"
    )
    pattern = (
        r"SECURITIES\s+AND\s+EXCHANGE\s+COMMISSION\s+WASHINGTON,\s*D\.C\.\s+\d{5}\s+"
        r"FORM\s+10[- ]?K\s+\(Mark\s+One\)\s+(?:\[\s*[Xx]\s*\]|☒|☑)\s+ANNUAL\s+"
        + legal
        + r"\s+(?P<cover>For\s+(?:the\s+)?fiscal\s+year\s+ended\s+December\s+31\s*,?\s+"
        r"(?P<year>20\d{2}))\s+OR\s+(?:\[\s*\]|☐)\s+TRANSITION\s+"
        + legal
        + r"\s+For\s+the\s+transition\s+period\s+from\s+_+\s+to\s+_+\s+"
        r"Commission\s+File\s+Number\s+[0-9-]+\s+UNION\s+PACIFIC\s+CORP\s*ORATION\s+"
        r"\(Exact\s+name\s+of\s+registrant\s+as\s+specified\s+in\s+its\s+charter\)"
    )
    matches = list(re.finditer(pattern, document_text, re.I))
    require(len(matches) == 1, "issuer.cash_dividend_unique_SEC_annual_cover_region")
    match = matches[0]
    segments = _cover_dom_segments(document_tree, match.start(), match.end())
    require(
        " ".join(" ".join(segment["raw_text"].split()) for segment in segments) == match.group(0),
        "issuer.cover_region_exact_DOM_reconstruction",
    )
    return {
        "rule": "sec_UNP_annual_cover_region_and_native_CFO_v2",
        "cover_quote": match.group("cover"),
        "cover_text_start": match.start("cover"),
        "cover_text_end": match.end("cover"),
        "period_end": match.group("year") + "-12-31",
        "cover_region": {
            "normalized_text_start": match.start(),
            "normalized_text_end": match.end(),
            "quote": match.group(0),
            "dom_text_segments": segments,
            "annual_report_selected": True,
            "transition_report_unselected": True,
            "registrant_identity": "UNION PACIFIC CORPORATION",
            "selection_uses_archived_year_known_offset_or_amount": False,
        },
        "native_same_accession_annual_CFO_confirmation_required": True,
        "annual_frequency_alone_used_to_infer_calendar_year": False,
    }


def cells(table):
    rows = []
    for row_index, row in enumerate(table.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")):
        cursor, entries = 0, []
        for cell_index, cell in enumerate(row.xpath("./th|./td")):
            require(int(cell.get("rowspan", "1")) == 1, "issuer.unsupported_rowspan")
            width = int(cell.get("colspan", "1"))
            require(0 < width < 100, "issuer.invalid_column_span")
            entries.append(
                {
                    "row": row_index,
                    "cell": cell_index,
                    "start": cursor,
                    "stop": cursor + width,
                    "text": text(cell),
                    "raw_text": "".join(cell.itertext()),
                    "cell_xpath": cell.getroottree().getpath(cell),
                    "has_superscript": bool(cell.xpath(".//sup")),
                }
            )
            cursor += width
        rows.append(entries)
    return rows


def scalar(value):
    """Printed signed amounts only; an untagged dash is NOT invented as zero."""
    if re.search(r"\d\s+\d", value):
        return None
    clean = re.sub(r"\s+", "", value).replace("\u2212", "-")
    match = re.fullmatch(
        rf"(?P<currency>\$)?(?:\((?P<inner_currency>\$)?(?P<bracket>{PRINTED_NUMBER})\)"
        rf"|(?P<plain>-?{PRINTED_NUMBER}))",
        clean,
    )
    if match is None or (match["currency"] and match["inner_currency"]):
        return None
    try:
        number = Decimal((match["bracket"] or match["plain"]).replace(",", ""))
        return -number if match["bracket"] else number
    except InvalidOperation:
        return None


def headers(rows, before):
    prefix = " ".join(cell["text"] for row in rows[:before] for cell in row)
    month_days = MONTH_DAY_RE.findall(prefix)
    possibilities = []
    for row in rows[:before]:
        anchors = []
        for cell in row:
            full = DATE_RE.fullmatch(cell["text"])
            year_only = re.fullmatch(r"20\d{2}", cell["text"])
            if full:
                month, day, year = full.groups()
                ending = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date().isoformat()
            elif year_only and len(set(month_days)) == 1:
                month, day = month_days[0]
                ending = (
                    datetime.strptime(f"{month} {day} {cell['text']}", "%B %d %Y")
                    .date()
                    .isoformat()
                )
            else:
                continue
            anchors.append({**cell, "period_end": ending})
        if 2 <= len(anchors) <= 5 and len({item["period_end"] for item in anchors}) == len(anchors):
            possibilities.append(anchors)
    require(len(possibilities) == 1, "issuer.unambiguous_annual_column_headers")
    require(re.search(r"\byears?\s+ended\b", prefix, re.I), "issuer.explicit_annual_table_scope")
    return possibilities[0]


def _contains(outer, inner):
    return outer["start"] <= inner["start"] and inner["stop"] <= outer["stop"]


def _overlaps(left, right):
    return left["start"] < right["stop"] and right["start"] < left["stop"]


def _symbol_roles(cell):
    """A dash is not a sign cell; mixed ')(' cells are never split opportunistically."""
    compact = re.sub(r"\s+", "", cell["text"])
    if not compact or not re.fullmatch(r"[$()]+", compact) or cell.get("has_superscript"):
        return set()
    return ({"prefix"} if "$" in compact or "(" in compact else set()) | (
        {"suffix"} if ")" in compact else set()
    )


def _validate_geometry(row):
    require(bool(row), "issuer.logical_amount_empty_row")
    require(
        len({cell["row"] for cell in row}) == 1
        and len({cell["cell"] for cell in row}) == len(row)
        and all(0 <= cell["start"] < cell["stop"] for cell in row)
        and all(
            left["stop"] == right["start"] and left["cell"] < right["cell"]
            for left, right in zip(row, row[1:], strict=False)
        ),
        "issuer.logical_amount_invalid_physical_geometry",
    )


def row_amount(row, header, *, year_headers=None, header_row=None):
    """Bind a printed amount before parsing its value, in a finite layout domain.

    One digit-bearing physical body must lie wholly inside exactly one annual
    header. Only immediately adjacent symbol-only runs may extend that body:
    '(' and '$' face right; ')' faces left. A physical symbol cell is indivisible
    and needs one owner, regardless of which concatenation would parse or make
    a reconciliation close. External symbols also need a blank original header
    cell and cannot overlap a different year. No blank/body/annotation is hopped.

    Without the complete annual/header-row context, only cells wholly contained
    in the supplied header are supported; external symbols cannot be inferred.
    """
    _validate_geometry(row)
    annual = list(year_headers) if year_headers is not None else [header]
    require(header in annual, "issuer.logical_amount_requested_header_missing")
    require(
        len({item["period_end"] for item in annual}) == len(annual)
        and all(item["start"] < item["stop"] for item in annual)
        and all(
            not _overlaps(left, right)
            for index, left in enumerate(annual)
            for right in annual[index + 1 :]
        ),
        "issuer.logical_amount_ambiguous_annual_headers",
    )
    if header_row is not None:
        _validate_geometry(header_row)
        require(
            all(
                any(
                    all(item[key] == cell[key] for key in ("row", "cell", "start", "stop", "text"))
                    for cell in header_row
                )
                for item in annual
            ),
            "issuer.logical_amount_header_context_mismatch",
        )
    overlap = [cell for cell in row if _overlaps(cell, header)]
    require(
        all(_contains(header, cell) for cell in overlap),
        "issuer.logical_amount_uncertain_column_ownership",
    )
    body_positions = [index for index, cell in enumerate(row) if re.search(r"\d", cell["text"])]
    selected = [index for index in body_positions if _contains(header, row[index])]
    require(len(selected) == 1, "issuer.missing_or_ambiguous_numeric_cell")
    selected_index = selected[0]
    body = row[selected_index]
    require(not body.get("has_superscript"), "issuer.logical_amount_numeric_annotation")
    body_owners = {
        index: [item for item in annual if _contains(item, row[index])] for index in body_positions
    }
    require(
        body_owners[selected_index] == [header],
        "issuer.logical_amount_uncertain_column_ownership",
    )

    def nearby_body(index, direction):
        cursor = index + direction
        crossed = 0
        while 0 <= cursor < len(row):
            if cursor in body_owners:
                return cursor
            # At most two other symbol cells in an uninterrupted physical run.
            if not _symbol_roles(row[cursor]) or crossed >= 2:
                return None
            cursor += direction
            crossed += 1
        return None

    bindings, attached = [], []
    for index, cell in enumerate(row):
        roles = _symbol_roles(cell)
        if not roles:
            continue
        candidate_indices = sorted(
            {
                owner
                for role in roles
                if (owner := nearby_body(index, 1 if role == "prefix" else -1)) is not None
            }
        )
        if selected_index not in candidate_indices:
            continue
        require(candidate_indices == [selected_index], "issuer.logical_amount_shared_symbol_cell")
        require(
            not any(item != header and _overlaps(item, cell) for item in annual),
            "issuer.logical_amount_symbol_crosses_annual_column",
        )
        if not _contains(header, cell):
            require(
                year_headers is not None and header_row is not None,
                "issuer.logical_amount_external_symbol_requires_full_headers",
            )
            header_cover = [item for item in header_row if _overlaps(item, cell)]
            require(
                header_cover
                and header_cover[0]["start"] <= cell["start"]
                and header_cover[-1]["stop"] >= cell["stop"]
                and all(not item["text"] for item in header_cover),
                "issuer.logical_amount_external_symbol_not_blank_header_slot",
            )
        attached.append(cell)
        bindings.append(
            {
                "cell": cell,
                "roles": sorted(roles),
                "candidate_body_cells": [row[owner] for owner in candidate_indices],
                "owner_period_end": header["period_end"],
                "outside_annual_header": not _contains(header, cell),
            }
        )
    included = sorted(
        overlap + [cell for cell in attached if cell not in overlap], key=lambda cell: cell["start"]
    )
    require(
        all(not cell["text"] or cell == body or cell in attached for cell in included),
        "issuer.missing_or_ambiguous_numeric_cell",
    )
    rendered = " ".join(cell["text"] for cell in included if cell["text"])
    amount = scalar(rendered)
    require(amount is not None, "issuer.missing_or_ambiguous_numeric_cell")
    return amount, {
        "printed_text": rendered,
        "cells": included,
        "geometry_certificate": {
            "rule": LOGICAL_AMOUNT_RULE,
            "body": body,
            "annual_header": header,
            "all_annual_headers": annual,
            "original_header_row": header_row,
            "original_amount_row": row,
            "symbol_bindings": bindings,
            "selection_uses_amount_value_or_reconciliation": False,
        },
    }


def table_structure(table, document_text):
    rows = cells(table)
    table_text = text(table)
    position = document_text.find(table_text)
    require(position >= 0, "issuer.table_text_in_original_document")
    after_start = position + len(table_text)
    after_table = document_text[after_start : after_start + 2500]
    original_labels = [next((cell["text"] for cell in row if cell["text"]), "") for row in rows]
    # Trailing footnote markers are source annotations, not financial roles.
    # Keep original DOM labels intact and require the annotated note to exist.
    labels, annotations = [], []
    for index, label in enumerate(original_labels):
        match = re.search(r"\s*(\*|\([0-9]+\))$", label)
        if match:
            marker = match.group(1)
            note = re.search(
                re.escape(marker) + r"\s+(?=[A-Za-z])[^.]{8,1500}(?:[.]|$)", after_table
            )
            require(note is not None, "issuer.footnote_requires_following_source_text")
            normalized = label[: match.start()].rstrip()
            annotations.append(
                {
                    "row": index,
                    "original": label,
                    "normalized": normalized,
                    "marker": marker,
                    "note_quote": note.group(0),
                    "note_text_start": after_start + note.start(),
                    "note_text_end": after_start + note.end(),
                }
            )
            labels.append(normalized)
        else:
            labels.append(label)
    total_rows = [index for index, label in enumerate(labels) if TOTAL_RE.fullmatch(label)]
    require(len(total_rows) == 1, "issuer.one_reported_FCF_total_row")
    end = total_rows[0]
    starts = [index for index, label in enumerate(labels[:end]) if CFO_RE.fullmatch(label)]
    require(len(starts) == 1, "issuer.one_operating_cash_flow_anchor_row")
    start = starts[0]
    selected_rows = [index for index in range(start, end + 1) if labels[index]]
    require(3 <= len(selected_rows) <= 10, "issuer.bounded_complete_reconciliation")
    require(
        len({labels[index].casefold() for index in selected_rows}) == len(selected_rows),
        "issuer.unique_component_labels",
    )
    require(
        not any("free cash flow" in labels[index].lower() for index in selected_rows[1:-1]),
        "issuer.intermediate_total_not_an_additive_component",
    )
    region_start, region_end = (
        max(0, position - 5000),
        min(len(document_text), position + len(table_text) + 5000),
    )
    definitions = list(DEFINITION_RE.finditer(document_text[region_start:region_end]))
    definitions = [match for match in definitions if "per share" not in match.group(0).lower()]
    require(bool(definitions), "issuer.explicit_company_FCF_definition")
    definition = min(definitions, key=lambda match: abs(region_start + match.start() - position))
    quote = definition.group(0)
    validate_definition_shape(quote, [labels[row] for row in selected_rows[:-1]])
    unit_context = document_text[max(0, position - 2000) : position + len(table_text)]
    global_units = re.search(
        r"All dollar amounts in the tables are stated in millions of U\.S\. dollars\.",
        document_text,
        re.I,
    )
    # A separately registered, complete CFO-CFI-dividend issuer definition.
    # No omission of 'net' changes the CFO identity: the actual same-filing
    # USD CFO/annual-period anchor below remains mandatory before Fact creation.
    cash_after_dividends = [labels[row].casefold() for row in selected_rows] == [
        "cash provided by operating activities",
        "cash used in investing activities",
        "dividends paid",
        "free cash flow",
    ] and re.fullmatch(
        r"Free cash flow is defined as cash provided by operating activities "
        r"less cash used in investing activities and dividends paid\.",
        quote,
        re.I,
    ) is not None
    explicit_millions_heading = cash_after_dividends and any(
        cell["text"].casefold() == "millions" for row in rows[:start] for cell in row
    )
    require(
        "in millions" in unit_context.lower()
        or global_units is not None
        or explicit_millions_heading,
        "issuer.explicit_million_scale",
    )
    caption_context = document_text[max(0, position - 250) : position + len(table_text)]
    require(
        not re.search(
            r"in millions of\s+(?:euros|yen|pounds|CNY|RMB|HKD)|[€£]", caption_context, re.I
        ),
        "issuer.explicit_foreign_currency",
    )
    header_resolution = None
    if cash_after_dividends and explicit_millions_heading:
        # This finite summary-table layout prints year indices, not full dates.
        # The literal December-31 annual cover gives proposed dates ONLY. Every
        # proposal must subsequently match an exact same-accession native annual
        # CFO record; a 52/53-week or fiscal-label/end-year mismatch stays rejected.
        original_document = table.getroottree().getroot()
        require(text(original_document) == document_text, "issuer.actual_original_DOM_text_parent")
        header_resolution = annual_report_cover(original_document)
        candidates = []
        for row in rows[:start]:
            annual = [
                {**cell, "period_end": cell["text"] + "-12-31"}
                for cell in row
                if re.fullmatch(r"20\d{2}", cell["text"])
            ]
            if 2 <= len(annual) <= 3 and len({x["period_end"] for x in annual}) == len(annual):
                candidates.append(annual)
        require(len(candidates) == 1, "issuer.cash_dividend_unique_year_heading")
        year_headers = candidates[0]
        require(
            max(x["period_end"] for x in year_headers) == header_resolution["period_end"],
            "issuer.cash_dividend_cover_and_latest_heading",
        )
        require(
            all(
                cell["text"].casefold() in {"", "millions"}
                or re.fullmatch(r"20\d{2}", cell["text"])
                for cell in rows[year_headers[0]["row"]]
            ),
            "issuer.cash_dividend_no_hidden_auxiliary_heading",
        )
    else:
        year_headers = headers(rows, start)
    return {
        "rows": rows,
        "labels": labels,
        "original_labels": original_labels,
        "label_annotations": annotations,
        "selected_rows": selected_rows,
        "headers": year_headers,
        "definition_quote": quote,
        "definition_text_start": region_start + definition.start(),
        "definition_text_end": region_start + definition.end(),
        "table_text": table_text,
        "table_text_start": position,
        "table_text_end": position + len(table_text),
        "nearby_source_text": document_text[
            max(0, position - 1500) : min(len(document_text), position + len(table_text) + 1500)
        ],
        "global_unit_quote": global_units.group(0) if global_units else None,
        "definition_type": "complete signed issuer reconciliation; not a universal FCF formula",
        **({"header_period_resolution": header_resolution} if header_resolution else {}),
    }


def parse_document(root, source, native_observations):
    from .native_facts import resolve_raw

    document, raw, entity = source["document"], source["raw_object"], source["entity"]
    path = resolve_raw(root, raw)
    cik = str(entity["cik"]).zfill(10)
    require(f"cik={cik}/" in raw["storage_uri"], "issuer.original_CIK_document_join")
    document_tree = html.fromstring(path.read_bytes())
    document_text = text(document_tree)
    report_periods = {
        text(node)
        for node in document_tree.iter()
        if str(node.get("name", "")).lower().endswith(":documentperiodenddate")
    }
    report_periods = {
        value for value in report_periods if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    }
    require(len(report_periods) <= 1, "issuer.conflicting_native_report_period")
    accession_match = re.search(r"/accession=([^/]+)/", raw["storage_uri"])
    require(accession_match is not None, "issuer.original_accession_identity")
    accession = accession_match.group(1)
    source_tables, observations, failures = [], [], []
    fcf_mentions = 0
    for index, table in enumerate(document_tree.xpath("//table")):
        displayed = text(table)
        if "free cash flow" not in displayed.lower() or len(displayed) > 12000:
            continue
        fcf_mentions += 1
        table_key = "issuer_table_" + digest([raw["content_sha256"], index])[:24]
        try:
            structure = table_structure(table, document_text)
            shape = {
                "source_cluster": source_identity(entity),
                "target": FCF,
                "definition_quote": structure["definition_quote"],
                "component_labels": [
                    structure["labels"][row] for row in structure["selected_rows"][:-1]
                ],
                "signed_adjustments_as_printed": True,
            }
            definition_key = "issuer_definition_" + digest(shape)[:24]
            table_record = record(
                "issuer_source_table",
                table_id=table_key,
                raw_object_id=raw["raw_object_id"],
                raw_sha256=raw["content_sha256"],
                original_document_id=document["document_id"],
                entity_id=entity["entity_id"],
                source_cluster=source_identity(entity),
                source_id="sec_filings",
                original_url=raw["original_url"],
                table_index=index,
                table_xpath=document_tree.getroottree().getpath(table),
                accession=accession,
                source_definition_identity=definition_key,
                definition_shape=shape,
                structure=structure,
                all_leaf_usage={"split": "train", "allowed_uses": ["train"]},
                new_task_created=False,
            )
            source_tables.append(table_record)
            for header in structure["headers"]:
                try:
                    end = header["period_end"]
                    require(2010 <= int(end[:4]) <= 2025, "issuer.observation_year_scope")
                    values = [
                        row_amount(
                            structure["rows"][row],
                            header,
                            year_headers=structure["headers"],
                            header_row=structure["rows"][header["row"]],
                        )
                        for row in structure["selected_rows"]
                    ]
                    cfo_value = values[0][0]
                    # Same-company, same-accession, same end-date and exact USD
                    # amount jointly determine the annual period and currency.
                    anchors = [
                        native
                        for native in native_observations
                        if native["metric_id"] == CFO
                        and native["record"]["end"] == end
                        and Decimal(str(native["record"]["val"])) == cfo_value * 1000000
                        and any(
                            row["record"].get("accn") == accession
                            for row in native["all_equal_source_occurrences"]
                        )
                    ]
                    require(len(anchors) == 1, "issuer.same_filing_native_USD_CFO_anchor")
                    anchor = anchors[0]
                    filing_dates = {
                        row["record"]["filed"]
                        for row in anchor["all_equal_source_occurrences"]
                        if row["record"].get("accn") == accession and row["record"].get("filed")
                    }
                    require(len(filing_dates) == 1, "issuer.actual_filing_date_unambiguous")
                    # This check is arithmetic validation AFTER the independent
                    # issuer definition and full table structure were bound.
                    require(
                        sum((amount for amount, _ in values[:-1]), Decimal(0)) == values[-1][0],
                        "issuer.full_definition_table_does_not_close",
                    )
                    observations.append(
                        {
                            "entity_id": entity["entity_id"],
                            "source_cluster": source_identity(entity),
                            "source_kind": "issuer_report_table",
                            "raw_object_id": raw["raw_object_id"],
                            "raw_sha256": raw["content_sha256"],
                            "table_id": table_key,
                            "source_definition_identity": definition_key,
                            "definition_shape": shape,
                            "period_start": anchor["record"]["start"],
                            "period_end": end,
                            "document_id": document["document_id"],
                            "filing_date": next(iter(filing_dates)),
                            "archived_document_metadata": {
                                "period_end": document["period_end"],
                                "filing_date": document["filing_date"],
                            },
                            "native_document_period_end": next(iter(report_periods), None),
                            "accession": accession,
                            "cfo_anchor": anchor,
                            "table_record_id": table_record["id"],
                            "rows": [
                                {
                                    "label": structure["labels"][row],
                                    "value": str(amount),
                                    "cell_reference": reference,
                                    "row_index": row,
                                    "is_reported_total": offset == len(values) - 1,
                                }
                                for offset, (row, (amount, reference)) in enumerate(
                                    zip(structure["selected_rows"], values, strict=True)
                                )
                            ],
                            "split": "train",
                            "allowed_uses": ["train"],
                        }
                    )
                except ValueError as exc:
                    failures.append(
                        {
                            "document_id": document["document_id"],
                            "table_id": table_key,
                            "entity_id": entity["entity_id"],
                            "period_end": header["period_end"],
                            "status": "ISSUER_PERIOD_BINDING_REJECTED",
                            "reason": str(exc),
                        }
                    )
        except ValueError as exc:
            failures.append(
                {
                    "document_id": document["document_id"],
                    "table_id": table_key,
                    "entity_id": entity["entity_id"],
                    "status": "ISSUER_TABLE_BINDING_REJECTED",
                    "reason": str(exc),
                }
            )
    if not fcf_mentions:
        failures.append(
            {
                "document_id": document["document_id"],
                "entity_id": entity["entity_id"],
                "period_end": document["period_end"],
                "status": "NO_REGISTERED_FCF_RECONCILIATION_TABLE",
                "reason": "specific annual report has no bounded table labelled free cash flow",
            }
        )
    return {
        "source": source,
        "tables": source_tables,
        "observations": observations,
        "failures": failures,
    }


def prepare(root, archived, native_inputs, *, extra_sources=()):
    selected = {item["entity"]["entity_id"]: item for item in native_inputs}
    sources = []
    for document in archived.fetchall(
        "SELECT * FROM source_documents WHERE source_id='sec_filings' "
        "AND form_type='10-K' AND document_status='passed' "
        "ORDER BY entity_id,period_end,document_id"
    ):
        if document["entity_id"] not in selected:
            continue
        raw = archived.fetchone(
            "SELECT * FROM raw_objects WHERE raw_object_id=?", (document["raw_object_id"],)
        )
        require(raw is not None, "issuer.archived_raw_object_parent")
        sources.append(
            {
                "document": document,
                "raw_object": raw,
                "entity": selected[document["entity_id"]]["entity"],
            }
        )

    for source in extra_sources:
        entity = source["entity"]
        require(entity["entity_id"] in selected, "issuer.extra_source_same_training_scope")
        require(
            source_identity(entity) == source_identity(selected[entity["entity_id"]]["entity"]),
            "issuer.extra_source_CIK_identity",
        )
        sources.append(source)
    require(
        len({source["document"]["document_id"] for source in sources}) == len(sources),
        "issuer.unique_original_source_documents",
    )
    sources.sort(
        key=lambda source: (
            source["entity"]["entity_id"],
            source["document"]["period_end"],
            source["document"]["document_id"],
        )
    )

    def read(source):
        try:
            return parse_document(
                root, source, selected[source["entity"]["entity_id"]]["observations"]
            )
        except (OSError, ValueError) as exc:
            return {
                "source": source,
                "tables": [],
                "observations": [],
                "failures": [
                    {
                        "document_id": source["document"]["document_id"],
                        "entity_id": source["entity"]["entity_id"],
                        "status": "ISSUER_SOURCE_UNAVAILABLE_OR_UNVERIFIABLE",
                        "reason": str(exc),
                    }
                ],
            }

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(read, sources))
    # Select the latest fully qualified period/vintage, not necessarily the
    # latest available disclosure. All failed newer records remain in the
    # rejection ledger. Alternative reports never create extra target identities.
    by_period = defaultdict(list)
    for result in results:
        for observation in result["observations"]:
            by_period[
                observation["entity_id"], observation["period_start"], observation["period_end"]
            ].append(observation)
    chosen, omitted = [], []
    for key in sorted(by_period):
        versions = sorted(
            by_period[key],
            key=lambda row: (row["filing_date"], row["document_id"], row["table_id"]),
        )
        chosen.append(versions[-1])
        omitted.extend(
            {
                "table_id": row["table_id"],
                "period_end": row["period_end"],
                "status": "OLDER_REPORTED_VINTAGE_NOT_A_NEW_TARGET",
            }
            for row in versions[:-1]
        )
    return {
        "sources": sources,
        "tables": [table for result in results for table in result["tables"]],
        "observations": chosen,
        "failures": [failure for result in results for failure in result["failures"]],
        "older_vintage_exclusions": omitted,
        "counts": {
            "documents": len(sources),
            "tables": sum(len(result["tables"]) for result in results),
            "selected_periods": len(chosen),
            "source_clusters": len({row["source_cluster"] for row in chosen}),
        },
    }


def metric_id(observation, row):
    if row["is_reported_total"]:
        return FCF
    return "issuer_fcf_component_" + digest([observation["source_cluster"], row["label"]])[:20]


def definition_id(observation, row):
    return (
        "sdef_"
        + digest([observation["source_definition_identity"], metric_id(observation, row)])[:24]
    )


def source_field(observation, row):
    return (
        "issuer_fcf:"
        + observation["source_definition_identity"]
        + ":"
        + metric_id(observation, row)
    )


def ontology_rows(issuer, metric_build, definition_build):
    metrics, definitions = {}, {}
    for observation in issuer["observations"]:
        for row in observation["rows"]:
            metric = metric_id(observation, row)
            name = "company-defined free cash flow" if row["is_reported_total"] else row["label"]
            metrics[metric] = {
                "metric_id": metric,
                "canonical_name": name,
                "metric_category": "financial_statement",
                "statement_type": "company_non_GAAP_reconciliation",
                "period_type": "period_flow",
                "default_unit": "monetary",
                "default_currency": "USD",
                "accounting_standard": "issuer_defined_non_GAAP",
                "aggregation_rule": (
                    "issuer-specific signed reconciliation; "
                    "no cross-company canonical FCF definition"
                ),
                "revision_risk": "high",
                "ambiguity_notes": (
                    "Definition and full row set must match across compared periods."
                ),
                "build_id": metric_build,
                "is_active": 1,
            }
            identifier = definition_id(observation, row)
            definitions[identifier] = {
                "definition_id": identifier,
                "source_id": "sec_filings",
                "metric_id": metric,
                "raw_concept_name": source_field(observation, row),
                "definition_text": observation["definition_shape"]["definition_quote"],
                "unit_rule": (
                    "table explicitly in millions; currency and annual dates "
                    "confirmed by same-filing native USD CFO"
                ),
                "frequency": "annual",
                "vintage_policy": (
                    "latest fully qualified supplied annual-report table per actual period"
                ),
                "is_forecast": 0,
                "comparable_to_metric_id": metric,
                "comparability_level": "issuer_definition_level",
                "notes": json.dumps(
                    {
                        "source_cluster": observation["source_cluster"],
                        "definition_shape": observation["definition_shape"],
                        "original_row_label": row["label"],
                        "signed_adjustment_as_printed": not row["is_reported_total"],
                    },
                    sort_keys=True,
                ),
                "build_id": definition_build,
                "is_active": 1,
            }
    return list(metrics.values()), list(definitions.values())


def populate(db, issuer, fact_build, document_build, native_bindings):
    from finraw.atomic_facts import _fact, _with_build

    from .archive import insert

    sources = {row["raw_object"]["raw_object_id"]: row for row in issuer["sources"]}
    used_raw_ids = {row["raw_object_id"] for row in issuer["observations"]}
    for identifier in sorted(used_raw_ids):
        source = sources[identifier]
        raw, original = source["raw_object"], source["document"]
        insert(db, "raw_objects", [raw])
        document_id = "doc_task_issuer_" + raw["content_sha256"][:24]
        observations = [row for row in issuer["observations"] if row["raw_object_id"] == identifier]
        native_ends = {
            row["native_document_period_end"]
            for row in observations
            if row.get("native_document_period_end")
        }
        native_filed = {row["filing_date"] for row in observations}
        require(
            len(native_ends) <= 1 and len(native_filed) == 1,
            "issuer.actual_document_metadata_consistent",
        )
        insert(
            db,
            "source_documents",
            [
                {
                    **original,
                    "document_id": document_id,
                    "stable_document_id": document_id,
                    "build_id": document_build,
                    "period_end": next(iter(native_ends), None),
                    "filing_date": next(iter(native_filed)),
                    "notes": json.dumps(
                        {
                            "original_archived_document_id": original["document_id"],
                            "original_raw_sha256": raw["content_sha256"],
                            "original_archived_period_end": original["period_end"],
                            "original_archived_filing_date": original["filing_date"],
                            "period_source": (
                                "native DEI DocumentPeriodEndDate when present, "
                                "otherwise unavailable"
                            ),
                            "filing_date_source": (
                                "same-accession original companyfacts disclosure records"
                            ),
                        }
                    ),
                }
            ],
        )
    table_by_id = {row["table_id"]: row for row in issuer["tables"]}
    tables_used = {row["table_id"] for row in issuer["observations"]}
    for identifier in sorted(tables_used):
        table = table_by_id[identifier]
        insert(
            db,
            "raw_extracted_tables",
            [
                {
                    "table_id": identifier,
                    "stable_table_id": identifier,
                    "build_id": document_build,
                    "is_active": 1,
                    "raw_object_id": table["raw_object_id"],
                    "source_id": "sec_filings",
                    "table_index": table["table_index"],
                    "raw_table_json": table,
                    "extraction_method": "bounded_complete_FCF_DOM_table_v1",
                    "confidence_score": 0.95,
                }
            ],
        )
        chunk_id = "definition_" + identifier
        insert(
            db,
            "document_text_chunks",
            [
                {
                    "chunk_id": chunk_id,
                    "stable_chunk_id": chunk_id,
                    "build_id": document_build,
                    "is_active": 1,
                    "raw_object_id": table["raw_object_id"],
                    "source_id": "sec_filings",
                    "section_title": "issuer FCF definition",
                    "text": table["structure"]["definition_quote"],
                    "char_start": table["structure"]["definition_text_start"],
                    "char_end": table["structure"]["definition_text_end"],
                    "extraction_method": "normalized_original_DOM_text",
                    "confidence_score": 0.95,
                }
            ],
        )
    by_pointer = {
        (row["raw_sha256"], row["pointer"]): identifier
        for identifier, row in native_bindings.items()
    }
    facts, bindings = [], {}
    for observation in issuer["observations"]:
        table = table_by_id[observation["table_id"]]
        document_id = "doc_task_issuer_" + observation["raw_sha256"][:24]
        cfo = observation["cfo_anchor"]
        cfo_parent = by_pointer[cfo["raw_sha256"], cfo["pointer"]]
        for row in observation["rows"]:
            metric, field = metric_id(observation, row), source_field(observation, row)
            pointer = (
                table["table_xpath"] + f"/tr[{row['row_index'] + 1}]@{observation['period_end']}"
            )
            binding = {
                "source_kind": "issuer_report_table",
                "entity_id": observation["entity_id"],
                "metric_id": metric,
                "source_cluster": observation["source_cluster"],
                "raw_object_id": observation["raw_object_id"],
                "raw_sha256": observation["raw_sha256"],
                "tag": field,
                "pointer": pointer,
                "source_definition_id": definition_id(observation, row),
                "document_id": document_id,
                "native_definition": {
                    "label": "company-defined free cash flow"
                    if row["is_reported_total"]
                    else row["label"],
                    "description": observation["definition_shape"]["definition_quote"],
                },
                "record": {
                    "val": row["value"],
                    "start": observation["period_start"],
                    "end": observation["period_end"],
                    "fy": int(observation["period_end"][:4]),
                    "fp": "FY",
                    "form": "10-K",
                    "accn": observation["accession"],
                    "filed": observation["filing_date"],
                    "unit": "million USD",
                    "row_label": row["label"],
                    "cell_reference": row["cell_reference"],
                },
                "definition_shape": observation["definition_shape"],
                "table_id": observation["table_id"],
                "table_record": table,
                "is_reported_total": row["is_reported_total"],
                "validation_leaf_fact_ids": [cfo_parent],
                "split": "train",
                "allowed_uses": ["train"],
                "atomic_build_id": fact_build,
            }
            fact = _fact(
                entity_id=observation["entity_id"],
                metric_id=metric,
                value=Decimal(row["value"]),
                unit="million USD",
                currency="USD",
                period_start=observation["period_start"],
                period_end=observation["period_end"],
                fiscal_year=int(observation["period_end"][:4]),
                fiscal_quarter="FY",
                as_of_date=observation["filing_date"],
                report_date=observation["period_end"],
                source_id="sec_filings",
                raw_object_id=observation["raw_object_id"],
                source_field_name=field,
                source_page_or_table=pointer,
                extraction_method="bounded_verified_issuer_FCF_table",
                confidence_score=0.95,
                verification_status="single_source",
                tolerance=None,
                notes=json.dumps(
                    {
                        "native_binding": binding,
                        "frequency": "annual",
                        "period_role": "annual_flow",
                        "financial_scope_type": "consolidated_entity",
                        "entity_scope_id": observation["entity_id"],
                    },
                    sort_keys=True,
                ),
                stable_parts=[
                    "issuer_FCF_native_table_v1",
                    observation["raw_sha256"],
                    pointer,
                    field,
                ],
            )
            fact = _with_build(fact, fact_build)
            facts.append(fact)
            bindings[fact["fact_id"]] = binding
    db.insert_atomic_facts(facts)
    return bindings


def validate_binding(fact, native):
    require(native["source_kind"] == "issuer_report_table", "issuer.binding_source_kind")
    require(
        fact["source_definition_id"] == native["source_definition_id"],
        "issuer.actual_definition_parent",
    )
    require(
        fact["metric_id"] == native["metric_id"] and fact["source_id"] == "sec_filings",
        "issuer.actual_metric_source",
    )
    require(
        fact["normalized_unit"] == "million USD" and fact["normalized_currency"] == "USD",
        "issuer.units",
    )
    require(
        Decimal(str(fact["normalized_value"])) == Decimal(native["record"]["val"]),
        "issuer.native_normalization",
    )
    require(
        fact["period_start"] == native["record"]["start"]
        and fact["period_end"] == native["record"]["end"],
        "issuer.actual_period",
    )
    table = native["table_record"]
    require(
        fact["entity_id"] == native["entity_id"] == table["entity_id"],
        "issuer.actual_company_parent",
    )
    require(native["source_cluster"] == table["source_cluster"], "issuer.actual_source_cluster")
    require(
        table["raw_sha256"] == native["raw_sha256"]
        and table["raw_object_id"] == fact["raw_object_id"],
        "issuer.original_source_parent",
    )
    require(table["source_definition_identity"] in native["tag"], "issuer.definition_identity")
    selected = table["structure"]["selected_rows"]
    row_index = native["record"]["cell_reference"]["cells"][0]["row"]
    require(row_index in selected, "issuer.complete_table_row")
    header = next(
        value
        for value in table["structure"]["headers"]
        if value["period_end"] == fact["period_end"]
    )
    observed, reference = row_amount(
        table["structure"]["rows"][row_index],
        header,
        year_headers=table["structure"]["headers"],
        header_row=table["structure"]["rows"][header["row"]],
    )
    require(
        reference == native["record"]["cell_reference"]
        and observed == Decimal(native["record"]["val"]),
        "issuer.original_cell_replay",
    )
    require(
        table["structure"]["definition_quote"] == native["native_definition"]["description"],
        "issuer.source_definition_quote",
    )


def relation(previous, current, lookup, bindings, usage):
    from .relations import basic, consecutive, definition_pair, endpoint_plan, gate, value, witness

    consecutive(previous, current)
    definition_pair(previous, current, bindings)
    gate(previous["metric_id"] == current["metric_id"] == FCF, "issuer.FCF_target_metric")
    components, all_facts, validation_leaves = [], [previous, current], []
    for endpoint in (previous, current):
        native = bindings[endpoint["fact_id"]]
        shape = native["definition_shape"]
        row_facts = []
        for label in shape["component_labels"]:
            component_metric = (
                "issuer_fcf_component_" + digest([native["source_cluster"], label])[:20]
            )
            component = lookup.get(
                (
                    endpoint["entity_id"],
                    component_metric,
                    endpoint["period_start"],
                    endpoint["period_end"],
                )
            )
            gate(
                component is not None,
                "issuer.missing_declared_reconciliation_component",
                label=label,
                period_end=endpoint["period_end"],
            )
            component_native = bindings[component["fact_id"]]
            gate(
                component_native["table_id"] == native["table_id"],
                "issuer.component_from_wrong_report_or_definition",
            )
            row_facts.append(component)
        basic([endpoint, *row_facts], bindings, usage)
        gate(
            sum((value(row) for row in row_facts), Decimal(0)) == value(endpoint),
            "issuer.complete_table_recompute",
        )
        validation_leaves.extend(native["validation_leaf_fact_ids"])
        all_facts.extend(row_facts)
        components.append(row_facts)
    all_ids = sorted({row["fact_id"] for row in all_facts} | set(validation_leaves))
    from .protocol import all_leaf_uses

    all_leaf_uses(all_ids, {}, usage)
    e_plan, e_inputs = endpoint_plan(previous, current)
    e = witness(e_plan, e_inputs, all_facts, "endpoint")
    m_inputs = {f"previous_{index}": row["fact_id"] for index, row in enumerate(components[0])}
    m_inputs.update({f"current_{index}": row["fact_id"] for index, row in enumerate(components[1])})
    coefficients = [-1] * len(components[0]) + [1] * len(components[1])
    m_plan = {
        "operators": [
            {
                "step_id": "answer",
                "operator": "linear_combination",
                "inputs": [{"binding": key} for key in m_inputs],
                "params": {"coefficients": coefficients},
            }
        ],
        "output_step": "answer",
    }
    m = witness(m_plan, m_inputs, all_facts, "movement")
    gate(Decimal(e["output"]["value"]) == Decimal(m["output"]["value"]), "issuer.two_oracles_agree")
    return record(
        "financial_relation_certificate",
        relation_rule="issuer_full_signed_FCF_reconciliation_v1",
        family="company_defined_metric",
        complete=True,
        definition_shape=bindings[current["fact_id"]]["definition_shape"],
        semantic_basis=(
            "issuer's own complete signed reconciliation and definition; no universal FCF formula"
        ),
        numeric_closure_is_not_sole_admission_rule=True,
        public_fact_ids=[row["fact_id"] for row in all_facts],
        leaf_fact_ids=all_ids,
        private_validation_only_fact_ids=sorted(set(validation_leaves)),
        witnesses=[e, m],
        previous_component_fact_ids=[row["fact_id"] for row in components[0]],
        current_component_fact_ids=[row["fact_id"] for row in components[1]],
    )
