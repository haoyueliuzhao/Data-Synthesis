"""Conservative public-table leads for prospective source review.

This pure screen does not certify a financial relation, construct a task, read
a dataset, consult a gold answer/program, or choose a source split. The caller
deduplicates source pages and applies provenance, exclusion and company rules.
The raw table_ori field is authoritative when present; discrepancies and
unknown dash cells are retained rather than repaired through arithmetic.
"""

import hashlib
import json
import re
from fractions import Fraction

GROUPS = (
    "stock_rollforward",
    "annual_flow_components",
    "defined_metric_reconstruction",
)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_UNIT = re.compile(
    r"\b(?:millions?|thousands?|billions?|dollars?|USD|EUR|GBP|shares?|options?|"
    r"barrels?|tonnes?|cans|packs|percent(?:age)?|per\s+share|weighted.average)\b|[%$€£]",
    re.I,
)
_NONADDITIVE = re.compile(r"weighted.average|per.share|margin|yield|percentage|percent|%", re.I)
_STOCK_OBJECT = re.compile(
    r"\b(?:balances?|liabilit\w*|reserves?|allowances?|obligations?|equity|"
    r"stock|options?|awards?|unrecognized tax benefits)\b|cash and cash equivalents",
    re.I,
)
_STOCK_ENDPOINT = re.compile(
    r"\b(?:beginning|ending|opening|closing)\b|"
    r"\bend of (?:the )?(?:year|period|fiscal year)\b|"
    r"\b(?:balance|outstanding)\b.*\b(?:january|december|jan\.?|dec\.?)\b|"
    r"\b(?:balance|outstanding)\b.*\b(?:start|end)\b",
    re.I,
)
_MOVEMENT = re.compile(
    r"add|increas|decreas|reduc|charg|expens|pay|settle|grant|vest|exercis|"
    r"forfeit|cancel|acquir|acquisition|repurchas|translat|revalu|dispos|"
    r"write.?off|written.?off|foreign|currency|other|accretion|provided|used|proceeds",
    re.I,
)
_FLOW = re.compile(
    r"\b(?:revenues?|sales|operating (?:income|profit)|costs?|expenses?|"
    r"shipment volumes?)\b",
    re.I,
)
_TOTAL = re.compile(r"^total\b|^net (?:revenues?|sales)$", re.I)
_METRIC = re.compile(
    r"adjusted ebitda|\bebitda\b|free cash flow|funds from operations|\b(?:FFO|AFFO)\b|"
    r"(?:non.gaap|underlying|adjusted).*(?:income|profit|earnings|expenses?|sga)|"
    r"^cash flow$|^\d{4} net revenue$",
    re.I,
)
_DEFINITION = re.compile(
    r"non.gaap|defined as|measure of gross margin|management.{0,45}(?:measure|metric)|"
    r"reconciliation of.{0,60}(?:ebitda|non.gaap|adjusted|underlying)",
    re.I,
)
_RECONCILIATION = re.compile(r"reconcil|defined as|measure of gross margin", re.I)
_ADJUSTMENT = re.compile(
    r"adjustments?|interest (?:expense|income)|income tax|depreciation|amortization|"
    r"stock.based|mark.to.market|project k|acquisition.related|restructur|"
    r"net (?:income|earnings)|gains?.{0,35}(?:sales?|dispositions?)",
    re.I,
)
_CASH_COMPONENT = re.compile(
    r"cash.*(?:operating|investing)|(?:property|properties|capital).*(?:addition|expend)|"
    r"additions to properties|dividends",
    re.I,
)
_SUBTOTAL = re.compile(r"\b(?:subtotal|total)\b|^adjustments\s*:?\s*$", re.I)
_SCOPE_FLAGS = {
    "NONCOMPARABLE_SCOPE": re.compile(
        r"not (?:directly )?comparab|not comparable|different.*(?:basis|scope)",
        re.I,
    ),
    "PARTIAL_DRIVER_EXPLANATION": re.compile(
        r"primarily due|principally due|mainly due|partially offset|top (?:products|customers)",
        re.I,
    ),
    "EXTERNAL_DEFINITION_REFERENCE": re.compile(
        r"(?:definition|reconciliation).{0,130}\bsee\b|see.{0,100}(?:definition|reconciliation)",
        re.I,
    ),
    "RESTATEMENT_OR_BASIS_CHANGE": re.compile(
        r"reclassif|restat|constant.currency|change in accounting|adoption of",
        re.I,
    ),
    "FORWARD_LOOKING_VALUATION": re.compile(
        r"standardized measure|discounted future net cash|estimated future net cash",
        re.I,
    ),
}


def _encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _record(kind, **fields):
    body = {"schema_version": "basis_scale_preparation.v1." + kind, **fields}
    return {**body, "id": kind + ":" + hashlib.sha256(_encode(body)).hexdigest()}


def _evidence(pointer, value):
    return {
        "pointer": pointer,
        "quote": value if isinstance(value, str) else _encode(value).decode("utf-8"),
        "original_value": json.loads(_encode(value)) if isinstance(value, (list, dict)) else value,
    }


def _valid_table(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(row, list) and row for row in value)
        and all(
            isinstance(cell, (str, int, float)) and not isinstance(cell, bool)
            for row in value
            for cell in row
        )
    )


def _amount(value):
    """Only unambiguous displayed scalars; a dash is never converted into zero."""
    text = str(value).strip()
    if text in {"", "-", "—", "–", "−", "N/A", "n/a", "NA"}:
        return {"status": "UNKNOWN", "reason": "DASH_BLANK_OR_NOT_AVAILABLE", "raw": value}
    if any(symbol in text for symbol in ("%", "€", "£")):
        return {"status": "UNKNOWN", "reason": "UNIT_OR_SCALE_REVIEW_REQUIRED", "raw": value}
    cleaned = text.replace("$", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", cleaned):
        return {"status": "UNKNOWN", "reason": "NONSCALAR_OR_MULTIPLE_TOKENS", "raw": value}
    result = Fraction(cleaned.replace(",", ""))
    if negative:
        result = -result
    return {"status": "PARSED_DIAGNOSTIC_ONLY", "exact": str(result), "raw": value}


def _header_rows(table):
    result = []
    for index, row in enumerate(table[:3]):
        tail = row[1:]
        if not tail or _STOCK_ENDPOINT.search(str(row[0])):
            continue
        years = sum(bool(_YEAR.search(str(cell))) for cell in tail)
        nonnumeric = all(_amount(cell)["status"] == "UNKNOWN" for cell in tail)
        label = str(row[0]).strip()
        header_label = (
            not label
            or (bool(_UNIT.search(label)) and not _FLOW.search(label))
            or bool(
                re.match(
                    r"^(?:year|fiscal|period|date|currency|segment|description|item)\b", label, re.I
                )
            )
        )
        # Four-digit amounts in a financial data row are not year headers.
        if (years and header_label) or (nonnumeric and (index == 0 or header_label)):
            result.append(index)
    return result


def _context(entry):
    result = []
    for field in ("pre_text", "post_text"):
        values = entry.get(field, [])
        if isinstance(values, list):
            result.extend(
                (_evidence([field, index], value))
                for index, value in enumerate(values)
                if isinstance(value, str)
            )
    return result


def _table_differences(authoritative, cleaned):
    if not isinstance(authoritative, list) or not isinstance(cleaned, list):
        return [{"reason": "NON_TABLE_VIEW", "authoritative": authoritative, "cleaned": cleaned}]
    result = []
    for row_index in range(max(len(authoritative), len(cleaned))):
        left = authoritative[row_index] if row_index < len(authoritative) else []
        right = cleaned[row_index] if row_index < len(cleaned) else []
        if not isinstance(left, list) or not isinstance(right, list):
            result.append({"row_index": row_index, "authoritative": left, "cleaned": right})
            continue
        for column in range(max(len(left), len(right))):
            original = left[column] if column < len(left) else None
            derived = right[column] if column < len(right) else None
            if original != derived:
                result.append(
                    {
                        "row_index": row_index,
                        "column_index": column,
                        "authoritative_value": original,
                        "cleaned_value": derived,
                        "authoritative_present": column < len(left),
                        "cleaned_present": column < len(right),
                    }
                )
    return result


def _diagnostics(table, field, headers, start, end, components):
    """Check a previously identified contiguous block; never search row subsets."""
    if any(_SUBTOTAL.search(str(table[row][0])) for row in components):
        return [
            {
                "status": "NOT_COMPUTED",
                "reason": "INTERMEDIATE_HIERARCHY_REQUIRES_REVIEW",
                "selected_component_rows": components,
                "relation_certified": False,
            }
        ]
    width = min(len(table[row]) for row in [start, end, *components])
    result = []
    for column in range(1, width):
        descriptions = [str(table[row][column]) for row in headers if column < len(table[row])]
        header = " ".join(descriptions)
        if _NONADDITIVE.search(header):
            result.append(
                {
                    "column_index": column,
                    "status": "NOT_COMPUTED",
                    "reason": "NONADDITIVE_UNIT_COLUMN",
                    "relation_certified": False,
                }
            )
            continue
        values = {row: _amount(table[row][column]) for row in [start, end, *components]}
        if any(value["status"] == "UNKNOWN" for value in values.values()):
            result.append(
                {
                    "column_index": column,
                    "status": "UNDETERMINED",
                    "reason": "UNKNOWN_DISPLAYED_SCALAR",
                    "unknown_cells": [
                        {**value, "pointer": [field, row, column]}
                        for row, value in values.items()
                        if value["status"] == "UNKNOWN"
                    ],
                    "relation_certified": False,
                }
            )
            continue
        endpoint = Fraction(values[end]["exact"]) - Fraction(values[start]["exact"])
        signed_sum = sum((Fraction(values[row]["exact"]) for row in components), Fraction(0))
        result.append(
            {
                "column_index": column,
                "status": "COMPUTED_DIAGNOSTIC_ONLY",
                "endpoint_difference": str(endpoint),
                "sum_of_displayed_signed_components": str(signed_sum),
                "equal": endpoint == signed_sum,
                "row_sign_interpretation_applied": False,
                "selected_component_rows": components,
                "source_pointers": [[field, row, column] for row in [start, *components, end]],
                "relation_certified": False,
                "equality_is_not_financial_sufficiency": True,
            }
        )
    return result


def _lead(group, reasons, evidence, rows, *, diagnostics=()):
    return {
        "group": group,
        "status": "SCREENED_LEAD",
        "review_status": "REVIEW_NEEDED",
        "reason_codes": reasons,
        "evidence": evidence,
        "row_indices": rows,
        "period_scope_status": "REVIEW_NEEDED",
        "physical_unit_status": "REVIEW_NEEDED",
        "component_completeness_and_hierarchy_status": "REVIEW_NEEDED",
        "diagnostics": list(diagnostics),
        "relation_certified": False,
        "new_task_created": False,
    }


def screen_public(entry):
    """Return finite public-source leads, never task or dual-relation certificates.

    Only id, filename, table_ori/table, pre_text/post_text and qa.question are
    inspected. Data-set split, company clustering and previous-use exclusions
    remain the caller's authority. Multiple group leads may describe the same
    source and must not be counted as distinct tasks without later review.
    """
    if not isinstance(entry, dict):
        raise ValueError("screen.public_entry_object_required")
    field = "table_ori" if "table_ori" in entry else "table"
    table = entry.get(field)
    context = _context(entry)
    question = entry.get("qa", {}).get("question") if isinstance(entry.get("qa"), dict) else None
    malformed_question = question is not None and not isinstance(question, str)
    if malformed_question:
        question = None
    comparison = {
        "authoritative_field": field,
        "cleaned_field_present": "table" in entry,
        "views_equal": table == entry.get("table") if "table" in entry else None,
        "differences": _table_differences(table, entry.get("table"))
        if field == "table_ori" and "table" in entry
        else [],
        "cleaned_values_never_substitute_for_authoritative_values": True,
    }
    warnings, leads, period_evidence, unit_evidence, dash_cells = [], [], [], [], []
    headers = []

    def warning(code, evidence=()):
        warnings.append(
            {"code": code, "evidence": list(evidence), "review_status": "REVIEW_NEEDED"}
        )

    if malformed_question:
        warning("MALFORMED_ORIGINAL_QUESTION_NOT_EXPORTED")

    if not _valid_table(table):
        warning("AUTHORITATIVE_TABLE_MISSING_EMPTY_OR_MALFORMED")
    else:
        headers = _header_rows(table)
        labels = [str(row[0]).lower().strip() for row in table]
        label_evidence = [_evidence([field, index, 0], row[0]) for index, row in enumerate(table)]
        all_text = context + [
            _evidence([field, row, column], cell)
            for row, cells in enumerate(table)
            for column, cell in enumerate(cells)
        ]
        period_evidence = [item for item in label_evidence if _YEAR.search(item["quote"])] + [
            _evidence([field, row, column], cell)
            for row in headers
            for column, cell in enumerate(table[row])
            if column and _YEAR.search(str(cell))
        ]
        contextual_periods = [
            item
            for item in context
            if _YEAR.search(item["quote"])
            and re.search(
                r"years? ended|for (?:fiscal )?years?|during (?:fiscal )?years?",
                item["quote"],
                re.I,
            )
        ]
        if not period_evidence:
            period_evidence = contextual_periods
        years = sorted({year for item in period_evidence for year in _YEAR.findall(item["quote"])})
        unit_evidence = [item for item in all_text if _UNIT.search(item["quote"])]
        dash_cells = [
            _evidence([field, row, column], cell)
            for row, cells in enumerate(table)
            for column, cell in enumerate(cells)
            if column and str(cell).strip() in {"-", "—", "–", "−", "N/A", "n/a", "NA"}
        ]
        if dash_cells:
            warning("DASH_OR_NA_IS_UNKNOWN_NOT_ZERO", dash_cells)
        if not unit_evidence:
            warning("PUBLIC_PHYSICAL_UNIT_NOT_ESTABLISHED")
        if not years:
            warning("PUBLIC_PERIOD_NOT_ESTABLISHED")
        if len({len(row) for row in table}) > 1:
            warning("RAGGED_TABLE_OR_SPANNED_HEADER_REQUIRES_REVIEW")
        for code, pattern in _SCOPE_FLAGS.items():
            matches = [item for item in context + label_evidence if pattern.search(item["quote"])]
            if matches:
                warning(code, matches[:6])
        joined = " ".join(item["quote"] for item in context) + " " + " ".join(labels)
        endpoints = [index for index, label in enumerate(labels) if _STOCK_ENDPOINT.search(label)]
        stock_blocks = []
        if endpoints and _STOCK_OBJECT.search(joined):
            if _SCOPE_FLAGS["FORWARD_LOOKING_VALUATION"].search(joined):
                warning("VALUATION_MEASURE_NOT_AUTOMATICALLY_A_STOCK_ACCOUNT")
            else:
                for start, end in zip(endpoints[:-1], endpoints[1:], strict=True):
                    components = list(range(start + 1, end))
                    if components and any(_MOVEMENT.search(labels[row]) for row in components):
                        stock_blocks.append((start, end, components))
                if not stock_blocks:
                    warning("ENDPOINT_LABELS_WITHOUT_ACTUAL_MOVEMENT_ROWS")
        for start, end, components in stock_blocks:
            evidence = [label_evidence[row] for row in [start, *components, end]]
            evidence.extend(
                item
                for item in context
                if re.search(r"roll.?forward|reconcil|activity|changes", item["quote"], re.I)
            )
            lead = _lead(
                "stock_rollforward",
                ["STOCK_OBJECT_CONTEXT", "ORDERED_ENDPOINT_LABELS", "INTERVENING_MOVEMENT_ROWS"],
                evidence,
                [start, *components, end],
                diagnostics=_diagnostics(table, field, headers, start, end, components),
            )
            lead["candidate_endpoint_rows"] = [start, end]
            lead["candidate_component_rows"] = components
            leads.append(lead)

        # A vertical bridge must name the same annual financial metric at both
        # endpoints. Different labels/bases are not unified through equal values.
        bridge_points = []
        for index, label in enumerate(labels):
            if _YEAR.search(label) and _FLOW.search(label):
                stem = re.sub(r"\s+", " ", _YEAR.sub("", label)).strip(" :-,")
                bridge_points.append((index, stem))
        bridges = []
        for (start, left), (end, right) in zip(bridge_points[:-1], bridge_points[1:], strict=True):
            components = list(range(start + 1, end))
            if left == right and components and len(years) >= 2:
                bridges.append((start, end, components))
                lead = _lead(
                    "annual_flow_components",
                    ["SAME_METRIC_TWO_YEAR_ENDPOINT_ROWS", "INTERVENING_DRIVER_ROWS"],
                    [label_evidence[row] for row in [start, *components, end]],
                    [start, *components, end],
                    diagnostics=_diagnostics(table, field, headers, start, end, components),
                )
                lead["candidate_endpoint_rows"] = [start, end]
                lead["candidate_component_rows"] = components
                leads.append(lead)

        totals = [index for index, label in enumerate(labels) if _TOTAL.search(label)]
        flow_anchors = [
            item
            for item in context
            if re.search(
                r"revenues?.{0,35}by|revenue by|sales.{0,35}by|by.{0,35}revenues?|"
                r"costs and expenses|revenue.*commodity|shipment volume",
                item["quote"],
                re.I,
            )
        ]
        if totals and flow_anchors and len(years) >= 2:
            component_rows = [
                index for index in range(min(totals)) if index not in headers and labels[index]
            ]
            if len(component_rows) >= 2:
                lead = _lead(
                    "annual_flow_components",
                    [
                        "MULTIYEAR_PUBLIC_FLOW_COMPONENT_TABLE",
                        "DISCLOSED_FLOW_TOTAL_ROWS",
                        "EXHAUSTIVENESS_AND_NONOVERLAP_REQUIRE_REVIEW",
                    ],
                    [*flow_anchors[:6], *[label_evidence[row] for row in totals]],
                    sorted(set([*component_rows, *totals])),
                )
                lead["candidate_total_rows"] = totals
                lead["candidate_component_rows"] = component_rows
                lead["diagnostics"] = [
                    {
                        "status": "NOT_COMPUTED",
                        "reason": "AGGREGATION_HIERARCHY_REQUIRES_REVIEW",
                        "subset_sum_search_performed": False,
                        "relation_certified": False,
                    }
                ]
                leads.append(lead)
                warning(
                    "FLOW_COMPONENT_HIERARCHY_AND_ELIMINATIONS_REQUIRE_REVIEW",
                    [label_evidence[row] for row in totals],
                )
        elif totals and flow_anchors and len(years) < 2:
            warning("FLOW_COMPARISON_NEEDS_TWO_PUBLIC_YEARS", flow_anchors[:3])

        metric_rows = [index for index, label in enumerate(labels) if _METRIC.search(label)]
        definition_anchors = [
            item for item in context + label_evidence if _DEFINITION.search(item["quote"])
        ]
        reconciliation_anchors = [
            item for item in context + label_evidence if _RECONCILIATION.search(item["quote"])
        ]
        cash_rows = [index for index, label in enumerate(labels) if _CASH_COMPONENT.search(label)]
        adjustment_rows = [index for index, label in enumerate(labels) if _ADJUSTMENT.search(label)]
        local_components = len(cash_rows) >= 2 or len(adjustment_rows) >= 2 or bool(bridges)
        if metric_rows and definition_anchors:
            if len(years) >= 2 and reconciliation_anchors and local_components:
                lead = _lead(
                    "defined_metric_reconstruction",
                    [
                        "PUBLIC_COMPANY_METRIC_DEFINITION_OR_NONGAAP_CONTEXT",
                        "LOCAL_RECONCILIATION_COMPONENT_ROWS",
                        "TWO_PUBLIC_COMPARISON_YEARS",
                    ],
                    [
                        *definition_anchors[:4],
                        *reconciliation_anchors[:4],
                        *[label_evidence[row] for row in metric_rows],
                    ],
                    sorted(
                        set(
                            [
                                *metric_rows,
                                *cash_rows,
                                *adjustment_rows,
                                *[
                                    row
                                    for start, end, _ in bridges
                                    for row in range(start, end + 1)
                                ],
                            ]
                        )
                    ),
                )
                lead["candidate_metric_rows"] = metric_rows
                lead["candidate_component_rows"] = sorted(set([*cash_rows, *adjustment_rows]))
                lead["diagnostics"] = [
                    {
                        "status": "NOT_COMPUTED",
                        "reason": "DEFINITION_SIGNS_AND_HIERARCHY_REQUIRE_REVIEW",
                        "subset_sum_search_performed": False,
                        "relation_certified": False,
                    }
                ]
                leads.append(lead)
            else:
                warning(
                    "METRIC_NAME_OR_EXTERNAL_REFERENCE_WITHOUT_LOCAL_TWO_PERIOD_RECONCILIATION",
                    definition_anchors[:4],
                )

    if comparison["differences"]:
        warning(
            "AUTHORITATIVE_AND_CLEANED_TABLE_DIFFER", [_evidence(["table_ori"], entry["table_ori"])]
        )
    groups = [group for group in GROUPS if any(lead["group"] == group for lead in leads)]
    if len(groups) > 1:
        warning("GROUP_OVERLAP_REQUIRES_TASK_LEVEL_REVIEW")
    return _record(
        "public_source_screen",
        status="SCREENED_LEAD" if leads else "NO_LEAD",
        review_status="REVIEW_NEEDED" if leads else "NO_LEAD",
        groups=groups,
        leads=leads,
        source={
            "original_entry_id": entry.get("id"),
            "filename": entry.get("filename"),
            "authoritative_table_field": field,
            "authoritative_table_sha256": hashlib.sha256(_encode(table)).hexdigest(),
            "header_row_indices": headers,
            "dataset_or_company_split_assigned": False,
        },
        original_question_identity={
            "original_id": entry.get("id"),
            "original_question": question,
            "identity_kind": "ORIGINAL_SOURCE_QUESTION"
            if isinstance(question, str)
            else "SOURCE_WITHOUT_ORIGINAL_QUESTION",
            "is_new_task": False,
            "question_rewritten_or_generated": False,
        },
        table_comparison=comparison,
        period_evidence=period_evidence,
        unit_evidence=unit_evidence,
        source_scope_warnings=warnings,
        dash_cells=dash_cells,
        relation_certificate_created=False,
        task_created=False,
        private_answer_or_program_used=False,
        automatic_source_repair_performed=False,
        closure_used_to_certify_relation=False,
        subset_sum_search_performed=False,
        source_page_deduplication_and_governance_are_callers_responsibility=True,
    )
