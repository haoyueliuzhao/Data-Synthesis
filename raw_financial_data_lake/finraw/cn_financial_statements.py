from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finraw.builds import finish_build, start_build, versioned_id
from finraw.db.client import DBProtocol

PARSER_VERSION = "1.33.0"
EVIDENCE_POLICY_VERSION = "1.33.0"
SOURCE_ID = "cninfo_announcements"
RECORD_TYPE = "cninfo_pdf_announcement"
CN_DISCLOSURE_RECORD_TYPES = {
    SOURCE_ID: RECORD_TYPE,
    "bse_disclosures": "bse_pdf_announcement",
    "hkex_disclosures": "hkex_pdf_annual_report",
}
EXTRACTION_METHOD = "pdf_financial_statement_table"
TABLE_EXTRACTION_METHOD = "pdfplumber_text_table"
TEXT_EXTRACTION_METHOD = "pymupdf_statement_page"

STATEMENT_LAYOUTS = (
    ("合并资产负债表和资产负债表", "balance_sheet", "consolidated_first_pair"),
    ("合并利润表和利润表", "income_statement", "consolidated_first_pair"),
    ("合并现金流量表和现金流量表", "cash_flow", "consolidated_first_pair"),
    ("合并财务状况表和财务状况表", "balance_sheet", "consolidated_first_pair"),
    ("合并及公司资产负债表", "balance_sheet", "consolidated_first_pair"),
    ("合并及公司利润表", "income_statement", "consolidated_first_pair"),
    ("合并及公司现金流量表", "cash_flow", "consolidated_first_pair"),
    ("合并及银行资产负债表", "balance_sheet", "consolidated_first_pair"),
    ("合并及银行利润表", "income_statement", "consolidated_first_pair"),
    ("合并及银行现金流量表", "cash_flow", "consolidated_first_pair"),
    ("合并资产负债表", "balance_sheet", "rightmost_periods"),
    ("合并利润表", "income_statement", "rightmost_periods"),
    ("合并现金流量表", "cash_flow", "rightmost_periods"),
    (
        "CONSOLIDATED STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSIVE INCOME",
        "income_statement",
        "rightmost_periods",
    ),
    (
        "CONSOLIDATED STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSIE INCOME",
        "income_statement",
        "rightmost_periods",
    ),
    (
        "CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME",
        "income_statement",
        "rightmost_periods",
    ),
    (
        "CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
        "income_statement",
        "rightmost_periods",
    ),
    (
        "CONSOLIDATED STATEMENTS OF PROFIT OR LOSS",
        "income_statement",
        "rightmost_periods",
    ),
    ("CONSOLIDATED INCOME STATEMENT", "income_statement", "rightmost_periods"),
    (
        "CONSOLIDATED STATEMENT OF FINANCIAL POSITION",
        "balance_sheet",
        "rightmost_periods",
    ),
    (
        "CONSOLIDATED STATEMENTS OF FINANCIAL POSITION",
        "balance_sheet",
        "rightmost_periods",
    ),
    ("CONSOLIDATED BALANCE SHEET", "balance_sheet", "rightmost_periods"),
    ("CONSOLIDATED STATEMENT OF CASH FLOWS", "cash_flow", "rightmost_periods"),
    ("CONSOLIDATED STATEMENTS OF CASH FLOWS", "cash_flow", "rightmost_periods"),
    ("CONSOLIDATED CASH FLOW STATEMENT", "cash_flow", "rightmost_periods"),
)

TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 4,
    "join_tolerance": 4,
    "intersection_tolerance": 6,
    "text_tolerance": 3,
    "min_words_vertical": 2,
    "min_words_horizontal": 1,
}


@dataclass
class ParsedDocument:
    chunks: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def refresh_cn_financial_statements(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    output_dir: str | None = None,
    max_objects: int | None = None,
    report_types: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Parse authoritative PRC consolidated statements into gated candidates."""
    policy = _policy(config)
    selected_source_ids = tuple(
        str(source_id)
        for source_id in (
            policy.get("source_ids") or tuple(CN_DISCLOSURE_RECORD_TYPES)
        )
    )
    unsupported_sources = sorted(
        set(selected_source_ids) - set(CN_DISCLOSURE_RECORD_TYPES)
    )
    if unsupported_sources:
        raise ValueError(
            "Unsupported CN financial statement sources: "
            + ", ".join(unsupported_sources)
        )
    selected_report_types = tuple(
        report_types or policy.get("report_types") or ("annual",)
    )
    configured_limit = int(policy.get("max_objects") or 0)
    effective_limit = (
        int(max_objects)
        if max_objects is not None
        else configured_limit
    )
    allow_single = bool(policy.get("allow_single_official_source", True))
    build_id = start_build(
        db,
        layer="fact_build",
        command="refresh-cn-financial-statements",
        prefix="cn_statement_extraction",
        notes=json.dumps(
            {
                "parser_version": PARSER_VERSION,
                "evidence_policy_version": EVIDENCE_POLICY_VERSION,
                "source_ids": selected_source_ids,
                "report_types": selected_report_types,
                "allow_single_official_source": allow_single,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    report: dict[str, Any] = {
        "build_id": build_id,
        "parser_version": PARSER_VERSION,
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "source_ids": list(selected_source_ids),
        "report_types": list(selected_report_types),
        "object_count": 0,
        "parsed_object_count": 0,
        "failed_object_count": 0,
        "statement_page_count": 0,
        "table_count": 0,
        "candidate_count": 0,
        "evidence_verified_count": 0,
        "promotion_approved_count": 0,
        "source_object_counts": Counter(),
        "source_candidate_counts": Counter(),
        "cross_check_counts": Counter(),
        "metric_counts": Counter(),
        "statement_counts": Counter(),
        "failure_counts": Counter(),
        "failures": [],
        "notes": [
            "Only consolidated primary financial statements from registered official Greater China disclosure sources are parsed; company-only statements, segment tables, notes, and document-presence records are excluded.",
            "pdfplumber supplies table-cell structure while PyMuPDF independently supplies statement identity, period, currency/scale, intact value geometry, and page-text evidence.",
            "Metric aliases are accepted only in their ontology-declared primary statement type; cash-flow reconciliation labels and entity-only statements are excluded.",
            "Candidate approval never sets qa_eligible, kg_eligible, or graph_ready; promotion is consumed by a separate Atomic Fact build and subsequent fact-quality gates.",
        ],
    }
    try:
        configured_entity_hints = _configured_entity_hints(
            config, selected_source_ids
        )
        configured_object_urls = _configured_object_urls(
            config, selected_source_ids
        )
        report["configured_entity_hint_counts"] = {
            source_id: len(values)
            for source_id, values in configured_entity_hints.items()
        }
        objects = _load_objects(
            db,
            selected_report_types,
            effective_limit,
            selected_source_ids,
            configured_entity_hints,
            configured_object_urls,
        )
        report["object_count"] = len(objects)
        for obj in objects:
            report["source_object_counts"][str(obj["source_id"])] += 1
        aliases_by_source, metric_statement_types = _load_metric_aliases(
            db, selected_source_ids
        )
        entities_by_source = _load_entity_aliases(db, selected_source_ids)
        parsed_documents: list[tuple[dict[str, Any], ParsedDocument]] = []
        for obj in objects:
            metadata = _json_value(obj.get("record_json"))
            if not isinstance(metadata, dict):
                metadata = {}
            metadata = {
                **metadata,
                "source_id": obj.get("source_id"),
                "source_publish_date": _iso_date_value(
                    obj.get("source_publish_date")
                ),
                "record_period_hint": obj.get("period_hint"),
            }
            source_id = str(obj["source_id"])
            entity_id = _entity_id_for_object(
                obj,
                metadata,
                entities_by_source.get(source_id, {}),
            )
            if not entity_id:
                _record_failure(
                    report,
                    obj,
                    "missing_canonical_entity",
                    f"No active {source_id} entity alias matched the document stock code.",
                )
                continue
            path = _resolve_storage_path(obj.get("storage_uri"), config)
            if not path or not path.exists():
                _record_failure(
                    report,
                    obj,
                    "missing_pdf",
                    f"Storage path does not exist: {obj.get('storage_uri')}",
                )
                continue
            try:
                pdfminer_logger = logging.getLogger("pdfminer.pdfinterp")
                previous_pdfminer_level = pdfminer_logger.level
                pdfminer_logger.setLevel(logging.ERROR)
                parsed = parse_cninfo_pdf(
                    path,
                    raw_object_id=str(obj["raw_object_id"]),
                    entity_id=entity_id,
                    metadata=metadata,
                    metric_aliases=aliases_by_source.get(source_id, {}),
                    metric_statement_types=metric_statement_types,
                    maximum_statement_pages=int(
                        policy.get("maximum_statement_pages") or 20
                    ),
                    maximum_unit_carry_pages=int(
                        policy.get("maximum_unit_carry_pages") or 12
                    ),
                    maximum_statement_carry_pages=int(
                        policy.get("maximum_statement_carry_pages") or 4
                    ),
                    source_id=source_id,
                )
                pdfminer_logger.setLevel(previous_pdfminer_level)
            except Exception as exc:
                if "previous_pdfminer_level" in locals():
                    pdfminer_logger.setLevel(previous_pdfminer_level)
                _record_failure(
                    report,
                    obj,
                    "pdf_parse_error",
                    f"{type(exc).__name__}: {exc}",
                )
                continue
            if not parsed.tables:
                _record_failure(
                    report,
                    obj,
                    "no_consolidated_statement_tables",
                    "No eligible consolidated statement page with an explicit unit was found.",
                )
                continue
            parsed_documents.append((obj, parsed))
            report["parsed_object_count"] += 1
            report["statement_page_count"] += len(parsed.chunks)
            report["table_count"] += len(parsed.tables)

        all_candidates = [
            candidate
            for _, parsed in parsed_documents
            for candidate in parsed.candidates
        ]
        _apply_accounting_identity_checks(all_candidates)
        _apply_cross_checks(all_candidates, allow_single=allow_single)

        candidate_by_stable = {
            candidate["candidate_id"]: candidate for candidate in all_candidates
        }
        with db.transaction():
            for _, parsed in parsed_documents:
                table_id_map: dict[str, str] = {}
                for chunk in parsed.chunks:
                    _insert_chunk(db, chunk, build_id)
                for table in parsed.tables:
                    stable_table_id = table["table_id"]
                    table_id = versioned_id(stable_table_id, build_id)
                    table_id_map[stable_table_id] = table_id
                    _insert_table(db, table, table_id, build_id)
                for stable_candidate in parsed.candidates:
                    candidate = candidate_by_stable[stable_candidate["candidate_id"]]
                    candidate_id = versioned_id(candidate["candidate_id"], build_id)
                    table_id = table_id_map[candidate["table_id"]]
                    _insert_candidate(
                        db,
                        candidate,
                        candidate_id,
                        table_id,
                        build_id,
                    )
                    _insert_evidence(
                        db,
                        candidate,
                        candidate_id,
                        table_id,
                        build_id,
                    )
                    report["candidate_count"] += 1
                    report["source_candidate_counts"][
                        str(candidate["_source_id"])
                    ] += 1
                    report["evidence_verified_count"] += int(
                        candidate["evidence_status"] == "verified"
                    )
                    report["promotion_approved_count"] += int(
                        candidate["promotion_status"]
                        == "approved_for_atomic_fact"
                    )
                    report["cross_check_counts"][
                        candidate["cross_check_status"]
                    ] += 1
                    report["metric_counts"][candidate["matched_metric_id"]] += 1
                    report["statement_counts"][candidate["statement_type"]] += 1
            if objects:
                _deactivate_superseded_output(
                    db,
                    build_id,
                    tuple(
                        str(obj["raw_object_id"])
                        for obj in objects
                    ),
                )
            if effective_limit <= 0 and any(configured_object_urls.values()):
                _deactivate_out_of_scope_output(
                    db,
                    build_id,
                    selected_source_ids,
                    tuple(str(obj["raw_object_id"]) for obj in objects),
                )

        final_report = _finalize_report(report)
        if output_dir:
            paths = write_cn_statement_report(final_report, output_dir)
            final_report["written_files"] = [str(path) for path in paths]
        finish_build(
            db,
            build_id,
            "success",
            (
                f"objects={report['object_count']}; parsed={report['parsed_object_count']}; "
                f"candidates={report['candidate_count']}; "
                f"approved={report['promotion_approved_count']}"
            ),
        )
        return final_report
    except Exception as exc:
        finish_build(db, build_id, "failed", f"{type(exc).__name__}: {exc}")
        raise


def parse_cninfo_pdf(
    path: Path,
    *,
    raw_object_id: str,
    entity_id: str,
    metadata: dict[str, Any],
    metric_aliases: dict[str, str],
    metric_statement_types: dict[str, str],
    maximum_statement_pages: int = 20,
    maximum_unit_carry_pages: int = 12,
    maximum_statement_carry_pages: int = 4,
    source_id: str = SOURCE_ID,
) -> ParsedDocument:
    try:
        import fitz
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires the project 'pdf' extra: pip install -e '.[pdf]'"
        ) from exc

    chunks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "page_count": 0,
        "eligible_statement_pages": [],
        "skipped_statement_pages": [],
    }

    with fitz.open(path) as fitz_doc:
        diagnostics["page_count"] = len(fitz_doc)
        section_unit: dict[str, Any] | None = None
        section_period: dict[str, Any] | None = None
        inferred_statement_section_open = False
        primary_statement_section_started = False
        primary_statement_section_closed = False
        active_statement: dict[str, Any] | None = None
        page_specs: list[dict[str, Any]] = []
        for page_index, page in enumerate(fitz_doc):
            full_page_text = page.get_text("text")
            page_text = full_page_text
            page_number = page_index + 1
            statement_context = active_statement
            has_non_target_boundary = _is_non_target_statement_boundary(
                full_page_text, source_id=source_id
            )
            boundary_top = (
                _statement_boundary_top(page, source_id=source_id)
                if has_non_target_boundary
                and source_id != "hkex_disclosures"
                else None
            )
            closes_statement_section = False
            if boundary_top is not None:
                prefix_text = page.get_text(
                    "text",
                    clip=fitz.Rect(
                        0,
                        0,
                        page.rect.width,
                        max(boundary_top - 0.5, 0),
                    ),
                )
                prefix_statement = _statement_identity(
                    prefix_text, source_id=source_id
                )
                if (
                    _page_has_registered_metric_label(prefix_text, metric_aliases)
                    and (statement_context or prefix_statement)
                ):
                    page_text = prefix_text
                    closes_statement_section = True
                    active_statement = None
                    inferred_statement_section_open = False
                    if _is_terminal_statement_boundary(
                        full_page_text, source_id=source_id
                    ):
                        primary_statement_section_closed = True
                else:
                    active_statement = None
                    if (
                        primary_statement_section_started
                        and _is_terminal_statement_boundary(
                            full_page_text, source_id=source_id
                        )
                    ):
                        inferred_statement_section_open = False
                        primary_statement_section_closed = True
                    continue
            elif has_non_target_boundary:
                active_statement = None
                if (
                    primary_statement_section_started
                    and _is_terminal_statement_boundary(
                        full_page_text, source_id=source_id
                    )
                ):
                    inferred_statement_section_open = False
                    primary_statement_section_closed = True
                continue
            declared_section_unit = _section_unit_info(
                page_text, source_id=source_id
            )
            if declared_section_unit:
                section_unit = {
                    **declared_section_unit,
                    "unit_source_page": page_number,
                    "unit_inherited": False,
                }
            report_period_end = _english_report_period_end(
                page_text,
                report_year=_report_year(metadata),
                source_id=source_id,
            )
            if (
                report_period_end
                and not primary_statement_section_started
                and "consolidated financial statements" in page_text.casefold()
            ):
                section_period = {
                    "period_end": report_period_end,
                    "period_source_page": page_number,
                }
                inferred_statement_section_open = (
                    source_id == "hkex_disclosures"
                    and not primary_statement_section_closed
                )
            if (
                primary_statement_section_closed
                and not closes_statement_section
            ):
                continue
            explicit_statement = _statement_identity(
                page_text, source_id=source_id
            )
            if (
                not explicit_statement
                and inferred_statement_section_open
                and section_period
                and 0
                <= page_number - int(section_period["period_source_page"])
                <= 20
            ):
                explicit_statement = _inferred_statement_identity(
                    page_text,
                    metric_aliases,
                    metric_statement_types,
                    source_id=source_id,
                )
            if explicit_statement:
                statement = {
                    **explicit_statement,
                    "statement_source_page": page_number,
                    "statement_inherited": False,
                }
                if not closes_statement_section:
                    active_statement = dict(statement)
            elif (
                statement_context
                and page_number
                - int(statement_context["statement_source_page"])
                <= maximum_statement_carry_pages
                and _page_has_registered_metric_label(page_text, metric_aliases)
            ):
                statement = {
                    **statement_context,
                    "statement_inherited": True,
                }
            else:
                continue
            unit_info = _unit_info(page_text, source_id=source_id)
            if unit_info:
                unit_info = {
                    **unit_info,
                    "unit_source_page": page_number,
                    "unit_inherited": False,
                }
            elif (
                statement.get("unit")
                and page_number - int(statement["unit_source_page"])
                <= maximum_statement_carry_pages
            ):
                unit_info = {
                    "unit_header": statement["unit_header"],
                    "unit": statement["unit"],
                    "currency": statement["currency"],
                    "value_scale": statement["value_scale"],
                    "unit_source_page": statement["unit_source_page"],
                    "unit_inherited": True,
                }
            elif (
                section_unit
                and page_number - int(section_unit["unit_source_page"])
                <= maximum_unit_carry_pages
            ):
                unit_info = {
                    **section_unit,
                    "unit_inherited": True,
                }
            direct_periods = _direct_periods_for_statement_page(
                page_text,
                statement,
                report_year=_report_year(metadata),
                source_id=source_id,
                fallback_period_end=(
                    section_period.get("period_end")
                    if section_period
                    and 0
                    <= page_number - int(section_period["period_source_page"])
                    <= 20
                    else None
                ),
            )
            if direct_periods:
                periods = direct_periods
                period_source_page = (
                    int(section_period["period_source_page"])
                    if section_period
                    and direct_periods[0].get("period_inference")
                    == "audited_statement_section_period"
                    else page_number
                )
                next_active_statement = {
                    **statement,
                    **(unit_info or {}),
                    "periods": periods,
                    "period_source_page": period_source_page,
                }
                if not closes_statement_section:
                    active_statement = next_active_statement
            elif (
                statement.get("periods")
                and page_number - int(statement["period_source_page"])
                <= maximum_statement_carry_pages
            ):
                periods = list(statement["periods"])
                period_source_page = int(statement["period_source_page"])
            else:
                periods = []
            if not unit_info:
                diagnostics["skipped_statement_pages"].append(
                    {
                        "page_number": page_number,
                        "reason": "missing_page_or_statement_section_currency_scale",
                    }
                )
                continue
            if not periods:
                diagnostics["skipped_statement_pages"].append(
                    {
                        "page_number": page_number,
                        "reason": "missing_page_or_bounded_statement_period_headers",
                    }
                )
                continue
            primary_statement_section_started = True
            word_clip = (
                fitz.Rect(0, 0, page.rect.width, float(boundary_top))
                if boundary_top is not None
                else None
            )
            positioned_words = page.get_text("words", clip=word_clip)
            page_specs.append(
                {
                    "page_index": page_index,
                    "page_number": page_number,
                    "page_text": page_text,
                    "content_y_max": boundary_top,
                    "page_words": [
                        {
                            "text": str(word[4]),
                            "x0": float(word[0]),
                            "top": float(word[1]),
                            "x1": float(word[2]),
                            "bottom": float(word[3]),
                        }
                        for word in positioned_words
                    ],
                    **statement,
                    **unit_info,
                    "period_source_page": period_source_page,
                    "periods": periods,
                }
            )
            if len(page_specs) >= maximum_statement_pages:
                break

    if not page_specs:
        return ParsedDocument(chunks, tables, candidates, diagnostics)

    with pdfplumber.open(path) as plumber_doc:
        for page_spec in page_specs:
            source_page = plumber_doc.pages[page_spec["page_index"]]
            content_y_max = page_spec.get("content_y_max")
            page = (
                source_page.crop(
                    (0, 0, source_page.width, float(content_y_max)),
                    strict=False,
                )
                if content_y_max is not None
                else source_page
            )
            if not page_spec.get("page_words"):
                page_spec["page_words"] = page.extract_words(
                    use_text_flow=False,
                    keep_blank_chars=False,
                )
            page_candidate_start = len(candidates)
            extracted_tables = page.extract_tables(TABLE_SETTINGS) or []
            for table_index, raw_rows in enumerate(extracted_tables):
                rows = _clean_rows(raw_rows)
                if not rows:
                    continue
                mapped_rows = _mapped_rows(
                    rows,
                    page_spec,
                    metric_aliases,
                    metric_statement_types,
                    raw_object_id,
                    entity_id,
                    metadata,
                    table_index,
                )
                if not mapped_rows:
                    continue
                stable_table_id = _id(
                    "cntable",
                    raw_object_id,
                    page_spec["page_number"],
                    table_index,
                    page_spec["statement_type"],
                )
                table_payload = {
                    "parser_version": PARSER_VERSION,
                    "statement_title": page_spec["statement_title"],
                    "statement_type": page_spec["statement_type"],
                    "financial_scope_type": "consolidated_entity",
                    "value_column_policy": page_spec["value_column_policy"],
                    "statement_source_page": page_spec["statement_source_page"],
                    "statement_inherited": page_spec["statement_inherited"],
                    "period_source_page": page_spec["period_source_page"],
                    "unit_header": page_spec["unit_header"],
                    "unit": page_spec["unit"],
                    "currency": page_spec["currency"],
                    "value_scale": page_spec["value_scale"],
                    "unit_source_page": page_spec["unit_source_page"],
                    "unit_inherited": page_spec["unit_inherited"],
                    "periods": page_spec["periods"],
                    "rows": rows,
                }
                tables.append(
                    {
                        "table_id": stable_table_id,
                        "raw_object_id": raw_object_id,
                        "source_id": source_id,
                        "page_number": page_spec["page_number"],
                        "table_index": table_index,
                        "raw_table_json": table_payload,
                        "extraction_method": TABLE_EXTRACTION_METHOD,
                        "confidence_score": 0.94,
                    }
                )
                for candidate in mapped_rows:
                    candidate["table_id"] = stable_table_id
                    candidates.append(candidate)

            fallback_rows = _missing_positioned_fallback_rows(
                page_spec,
                metric_aliases,
                metric_statement_types,
                candidates[page_candidate_start:],
            )
            if fallback_rows:
                fallback_table_index = 1000
                mapped_rows = _mapped_rows(
                    fallback_rows,
                    page_spec,
                    metric_aliases,
                    metric_statement_types,
                    raw_object_id,
                    entity_id,
                    metadata,
                    fallback_table_index,
                )
                if mapped_rows:
                    stable_table_id = _id(
                        "cntable",
                        raw_object_id,
                        page_spec["page_number"],
                        fallback_table_index,
                        page_spec["statement_type"],
                    )
                    table_payload = {
                        "parser_version": PARSER_VERSION,
                        "layout_mode": "positioned_words_strict_alias_fallback",
                        "statement_title": page_spec["statement_title"],
                        "statement_type": page_spec["statement_type"],
                        "financial_scope_type": "consolidated_entity",
                        "value_column_policy": page_spec["value_column_policy"],
                        "statement_source_page": page_spec["statement_source_page"],
                        "statement_inherited": page_spec["statement_inherited"],
                        "period_source_page": page_spec["period_source_page"],
                        "unit_header": page_spec["unit_header"],
                        "unit": page_spec["unit"],
                        "currency": page_spec["currency"],
                        "value_scale": page_spec["value_scale"],
                        "unit_source_page": page_spec["unit_source_page"],
                        "unit_inherited": page_spec["unit_inherited"],
                        "periods": page_spec["periods"],
                        "rows": fallback_rows,
                    }
                    tables.append(
                        {
                            "table_id": stable_table_id,
                            "raw_object_id": raw_object_id,
                            "source_id": source_id,
                            "page_number": page_spec["page_number"],
                            "table_index": fallback_table_index,
                            "raw_table_json": table_payload,
                            "extraction_method": TABLE_EXTRACTION_METHOD,
                            "confidence_score": 0.92,
                        }
                    )
                    for candidate in mapped_rows:
                        candidate["table_id"] = stable_table_id
                        candidates.append(candidate)

            chunk_text = page_spec["page_text"].strip()
            if any(
                table["page_number"] == page_spec["page_number"]
                for table in tables
            ):
                chunks.append(
                    {
                        "chunk_id": _id(
                            "cnchunk",
                            raw_object_id,
                            page_spec["page_number"],
                            page_spec["statement_type"],
                        ),
                        "raw_object_id": raw_object_id,
                        "source_id": source_id,
                        "page_number": page_spec["page_number"],
                        "section_title": page_spec["statement_title"],
                        "text": chunk_text,
                        "char_start": 0,
                        "char_end": len(chunk_text),
                        "extraction_method": TEXT_EXTRACTION_METHOD,
                        "confidence_score": 0.98,
                    }
                )
                diagnostics["eligible_statement_pages"].append(
                    page_spec["page_number"]
                )

    return ParsedDocument(chunks, tables, candidates, diagnostics)


def _load_objects(
    db: DBProtocol,
    report_types: tuple[str, ...],
    limit: int,
    source_ids: tuple[str, ...] | None = None,
    entity_hints_by_source: dict[str, set[str]] | None = None,
    object_urls_by_source: dict[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    selected_sources = source_ids or tuple(CN_DISCLOSURE_RECORD_TYPES)
    source_clauses = " OR ".join(
        "(ro.source_id = ? AND rr.record_type = ?)"
        for _ in selected_sources
    )
    placeholders = ",".join("?" for _ in report_types)
    sql = f"""
        SELECT ro.raw_object_id, ro.storage_uri, ro.original_url,
               ro.source_id, ro.source_publish_date, ro.content_sha256,
               ro.retrieval_time,
               rr.raw_record_id, rr.record_json, rr.entity_hint,
               rr.period_hint, rr.metric_hint
        FROM raw_objects ro
        JOIN raw_records rr ON rr.raw_object_id = ro.raw_object_id
        WHERE ({source_clauses})
          AND ro.object_type = 'pdf'
          AND ro.validation_status = 'passed'
          AND rr.metric_hint IN ({placeholders})
        ORDER BY rr.entity_hint, rr.period_hint, ro.source_publish_date,
                 ro.raw_object_id, rr.raw_record_id
    """
    params: list[Any] = []
    for source_id in selected_sources:
        params.extend([source_id, CN_DISCLOSURE_RECORD_TYPES[source_id]])
    params.extend(report_types)
    selected_objects: dict[str, dict[str, Any]] = {}
    for row in db.fetchall(sql, params):
        item = dict(row)
        allowed_hints = (entity_hints_by_source or {}).get(
            str(item["source_id"]), set()
        )
        if allowed_hints and _normalized_source_code(
            str(item["source_id"]), item.get("entity_hint")
        ) not in allowed_hints:
            continue
        allowed_urls = (object_urls_by_source or {}).get(
            str(item["source_id"]), set()
        )
        if allowed_urls and _base_url(item.get("original_url")) not in allowed_urls:
            continue
        identity = (
            f"{item['source_id']}|{_base_url(item.get('original_url'))}"
            if allowed_urls
            else str(item["raw_object_id"])
        )
        previous = selected_objects.get(identity)
        current_rank = (
            str(item.get("retrieval_time") or ""),
            str(item["raw_object_id"]),
        )
        previous_rank = (
            str(previous.get("retrieval_time") or ""),
            str(previous["raw_object_id"]),
        ) if previous else ("", "")
        if previous is None or current_rank > previous_rank:
            selected_objects[identity] = item
    unique_objects = sorted(
        selected_objects.values(),
        key=lambda item: (
            str(item.get("entity_hint") or ""),
            str(item.get("period_hint") or ""),
            str(item.get("source_publish_date") or ""),
            str(item.get("raw_object_id") or ""),
        ),
    )
    return unique_objects[:limit] if limit > 0 else unique_objects


def _configured_entity_hints(
    config: dict[str, Any], source_ids: tuple[str, ...]
) -> dict[str, set[str]]:
    config_keys = {
        "cninfo_announcements": "cninfo",
        "bse_disclosures": "bse",
        "hkex_disclosures": "hkex",
    }
    result: dict[str, set[str]] = {}
    for source_id in source_ids:
        source_config = config.get(config_keys[source_id], {})
        values = {
            _normalized_source_code(source_id, item.get("stock_code"))
            for collection in ("stock_pool", "announcements")
            for item in source_config.get(collection, [])
            if item.get("stock_code")
        }
        result[source_id] = {value for value in values if value}
    return result


def _configured_object_urls(
    config: dict[str, Any], source_ids: tuple[str, ...]
) -> dict[str, set[str]]:
    config_keys = {
        "cninfo_announcements": "cninfo",
        "bse_disclosures": "bse",
        "hkex_disclosures": "hkex",
    }
    return {
        source_id: {
            str(item["url"])
            for item in config.get(config_keys[source_id], {}).get(
                "announcements", []
            )
            if item.get("url")
        }
        for source_id in source_ids
    }


def _normalized_source_code(source_id: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if source_id == "hkex_disclosures":
        return text.zfill(5)
    return text.zfill(6)


def _base_url(value: Any) -> str:
    return str(value or "").partition("?")[0]


def _deactivate_superseded_output(
    db: DBProtocol,
    build_id: str,
    raw_object_ids: tuple[str, ...],
) -> None:
    if not raw_object_ids:
        return
    object_placeholders = ",".join("?" for _ in raw_object_ids)
    db.execute(
        f"""
        UPDATE candidate_facts
        SET is_active = 0, superseded_by = ?
        WHERE COALESCE(is_active, 1) = 1
          AND review_status LIKE 'cn_pdf_%%'
          AND raw_object_id IN ({object_placeholders})
          AND COALESCE(build_id, '') <> ?
        """,
        [build_id, *raw_object_ids, build_id],
    )
    db.execute(
        f"""
        UPDATE raw_extracted_tables
        SET is_active = 0, superseded_by = ?
        WHERE COALESCE(is_active, 1) = 1
          AND raw_object_id IN ({object_placeholders})
          AND extraction_method = ?
          AND COALESCE(build_id, '') <> ?
        """,
        [build_id, *raw_object_ids, TABLE_EXTRACTION_METHOD, build_id],
    )
    db.execute(
        f"""
        UPDATE document_text_chunks
        SET is_active = 0, superseded_by = ?
        WHERE COALESCE(is_active, 1) = 1
          AND raw_object_id IN ({object_placeholders})
          AND extraction_method = ?
          AND COALESCE(build_id, '') <> ?
        """,
        [build_id, *raw_object_ids, TEXT_EXTRACTION_METHOD, build_id],
    )


def _deactivate_out_of_scope_output(
    db: DBProtocol,
    build_id: str,
    source_ids: tuple[str, ...],
    selected_raw_object_ids: tuple[str, ...],
) -> None:
    if not source_ids or not selected_raw_object_ids:
        return
    source_placeholders = ",".join("?" for _ in source_ids)
    object_placeholders = ",".join("?" for _ in selected_raw_object_ids)
    source_subquery = (
        "SELECT raw_object_id FROM raw_objects "
        f"WHERE source_id IN ({source_placeholders})"
    )
    shared_params = [
        build_id,
        *source_ids,
        *selected_raw_object_ids,
        build_id,
    ]
    db.execute(
        f"""
        UPDATE candidate_facts
        SET is_active = 0, superseded_by = ?
        WHERE COALESCE(is_active, 1) = 1
          AND review_status LIKE 'cn_pdf_%%'
          AND raw_object_id IN ({source_subquery})
          AND raw_object_id NOT IN ({object_placeholders})
          AND COALESCE(build_id, '') <> ?
        """,
        shared_params,
    )
    for table, method in (
        ("raw_extracted_tables", TABLE_EXTRACTION_METHOD),
        ("document_text_chunks", TEXT_EXTRACTION_METHOD),
    ):
        db.execute(
            f"""
            UPDATE {table}
            SET is_active = 0, superseded_by = ?
            WHERE COALESCE(is_active, 1) = 1
              AND raw_object_id IN ({source_subquery})
              AND raw_object_id NOT IN ({object_placeholders})
              AND extraction_method = ?
              AND COALESCE(build_id, '') <> ?
            """,
            [
                build_id,
                *source_ids,
                *selected_raw_object_ids,
                method,
                build_id,
            ],
        )


def _load_metric_aliases(
    db: DBProtocol,
    source_ids: tuple[str, ...] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    selected_sources = source_ids or tuple(CN_DISCLOSURE_RECORD_TYPES)
    placeholders = ",".join("?" for _ in selected_sources)
    aliases: dict[str, dict[str, str]] = defaultdict(dict)
    statement_types: dict[str, str] = {}
    for row in db.fetchall(
        f"""
        SELECT ma.source_id, ma.raw_field_name, ma.raw_concept_name, ma.metric_id,
               ma.confidence_score, m.statement_type
        FROM metric_alias_map ma
        JOIN metrics m ON m.metric_id = ma.metric_id
        WHERE ma.source_id IN ({placeholders})
          AND COALESCE(ma.is_active, 1) = 1
          AND COALESCE(m.is_active, 1) = 1
        ORDER BY ma.confidence_score DESC
        """,
        list(selected_sources),
    ):
        item = dict(row)
        if item.get("statement_type"):
            statement_types.setdefault(
                str(item["metric_id"]),
                str(item["statement_type"]),
            )
        for raw_name in (
            item.get("raw_field_name"),
            item.get("raw_concept_name"),
        ):
            if raw_name:
                aliases[str(item["source_id"])].setdefault(
                    _normalize_label(str(raw_name)), item["metric_id"]
                )
    return dict(aliases), statement_types


def _load_entity_aliases(
    db: DBProtocol,
    source_ids: tuple[str, ...] | None = None,
) -> dict[str, dict[str, str]]:
    selected_sources = source_ids or tuple(CN_DISCLOSURE_RECORD_TYPES)
    placeholders = ",".join("?" for _ in selected_sources)
    aliases: dict[str, dict[str, str]] = defaultdict(dict)
    for row in db.fetchall(
        f"""
        SELECT source_id, source_code, alias, entity_id
        FROM entity_alias_map
        WHERE source_id IN ({placeholders})
          AND COALESCE(is_active, 1) = 1
        """,
        list(selected_sources),
    ):
        item = dict(row)
        for key in (item.get("source_code"), item.get("alias")):
            if key:
                aliases[str(item["source_id"])][str(key).strip()] = item[
                    "entity_id"
                ]
    return dict(aliases)


def _entity_id_for_object(
    obj: dict[str, Any],
    metadata: dict[str, Any],
    aliases: dict[str, str],
) -> str | None:
    for key in (
        metadata.get("stock_code"),
        obj.get("entity_hint"),
        metadata.get("company_name"),
    ):
        if key is not None and str(key).strip() in aliases:
            return aliases[str(key).strip()]
    return None


def _resolve_storage_path(value: Any, config: dict[str, Any]) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.exists() or path.is_absolute():
        return path
    return Path(str(config.get("storage_root") or "data/fin_raw")) / path


def _statement_identity(
    text: str, *, source_id: str = SOURCE_ID
) -> dict[str, str] | None:
    all_header_lines = [
        re.sub(r"\s+", "", line).casefold()
        for line in text.splitlines()
        if line.strip()
    ]
    leading_header_lines = [
        re.sub(r"\s+", "", line).casefold()
        for line in text[:1200].splitlines()
        if line.strip()
    ]
    if any("目录" in line for line in leading_header_lines[:3]):
        return None
    candidate_lines = (
        leading_header_lines
        if source_id == "bse_disclosures"
        else all_header_lines[:30]
    )
    header_candidates = list(candidate_lines)
    for width in (2, 3):
        header_candidates.extend(
            "".join(candidate_lines[index : index + width])
            for index in range(max(0, len(candidate_lines) - width + 1))
        )
    embedded_header_candidates: list[tuple[list[str], list[str]]] = []
    if source_id == SOURCE_ID:
        for index in range(len(candidate_lines), len(all_header_lines)):
            candidates = [
                "".join(all_header_lines[index : index + width])
                for width in (1, 2, 3)
            ]
            if any("合并" in candidate for candidate in candidates):
                embedded_header_candidates.append(
                    (candidates, all_header_lines[index : index + 14])
                )
    for title, statement_type, value_column_policy in STATEMENT_LAYOUTS:
        normalized_title = re.sub(r"\s+", "", title).casefold()
        chapter_prefix = (
            r"(?:(?:19|20)\d{2}(?:年度|年\d{1,2}月\d{1,2}日))?"
            r"(?:(?:\d+[、.．])|(?:[（(][一二三四五六七八九十百\d]+[）)]))?"
        )
        title_pattern = re.compile(
            rf"^{chapter_prefix}"
            rf"{re.escape(normalized_title)}(?:[（(]续[）)])?$"
        )
        matched = any(
            title_pattern.fullmatch(line) for line in header_candidates
        )
        if not matched:
            for embedded_candidates, embedded_context in (
                embedded_header_candidates
            ):
                if not any(
                    title_pattern.fullmatch(line)
                    for line in embedded_candidates
                ):
                    continue
                if _embedded_statement_header_is_auditable(
                    embedded_context,
                    statement_type,
                    source_id=source_id,
                ):
                    matched = True
                    break
        if matched:
            return {
                "statement_title": title,
                "statement_type": statement_type,
                "value_column_policy": value_column_policy,
            }
    return None


def _embedded_statement_header_is_auditable(
    lines: list[str],
    statement_type: str,
    *,
    source_id: str,
) -> bool:
    """Accept a mid-page primary-statement transition only with its own header."""
    if source_id != SOURCE_ID:
        return False
    context = "\n".join(lines)
    if not _unit_info(context, source_id=source_id):
        return False
    dates = set(
        re.findall(
            r"(?:19|20)\d{2}年\d{1,2}月\d{1,2}日",
            context,
        )
    )
    years = set(re.findall(r"(?:19|20)\d{2}", context))
    return len(dates) >= 2 or len(years) >= 2 or _has_relative_period_columns(
        context,
        statement_type,
    )


def _inferred_statement_identity(
    text: str,
    metric_aliases: dict[str, str],
    metric_statement_types: dict[str, str],
    *,
    source_id: str = SOURCE_ID,
) -> dict[str, Any] | None:
    if source_id != "hkex_disclosures" or not _english_unit_info(text):
        return None
    compact_text = re.sub(r"\s+", "", text[:5000]).casefold()
    metrics_by_statement: dict[str, set[str]] = defaultdict(set)
    for alias, metric_id in metric_aliases.items():
        if len(alias) < 5 or alias not in compact_text:
            continue
        statement_type = metric_statement_types.get(metric_id)
        if statement_type in {"income_statement", "balance_sheet", "cash_flow"}:
            metrics_by_statement[statement_type].add(metric_id)
    ranked = sorted(
        metrics_by_statement.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    if not ranked or len(ranked[0][1]) < 2:
        return None
    if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
        return None
    statement_type, metric_ids = ranked[0]
    anchors = {
        "income_statement": {"revenue", "net_income", "operating_income"},
        "balance_sheet": {"total_assets", "total_liabilities"},
        "cash_flow": {
            "net_cash_provided_by_used_in_operating_activities",
            "net_cash_provided_by_used_in_investing_activities",
            "net_cash_provided_by_used_in_financing_activities",
        },
    }
    if not metric_ids.intersection(anchors[statement_type]):
        return None
    return {
        "statement_title": f"INFERRED CONSOLIDATED {statement_type.upper()}",
        "statement_type": statement_type,
        "value_column_policy": "rightmost_periods",
        "statement_identity_inferred": True,
    }


def _is_non_target_statement_boundary(
    text: str, *, source_id: str = SOURCE_ID
) -> bool:
    page_lines = [
        re.sub(r"\s+", "", line)
        for line in text.splitlines()
        if line.strip()
    ]
    if any(
        re.fullmatch(r"(?:\d+[、.．])?财务报表附注", line)
        for line in page_lines
    ):
        return True
    if source_id == "hkex_disclosures":
        folded_lines = [line.casefold() for line in page_lines]
        if any(
            "notestothefinancialstatements" in line
            or "notestoconsolidatedfinancialstatements" in line
            or "statementofchangesinequity" in line
            for line in folded_lines
        ):
            return True
        if any(
            re.search(
                r"^(?:company|separate)statementof"
                r"(?:financialposition|profit|cashflows)",
                line,
            )
            for line in folded_lines
        ):
            return True
    for line in page_lines:
        normalized = _without_section_prefix(line)
        if "权益变动表" in normalized:
            return True
        normalized = (
            normalized.replace("（续）", "")
            .replace("(续)", "")
            .strip("：:")
        )
        if re.fullmatch(
            r"(?:母公司|公司|银行|本行|个别)"
            r"(?:资产负债表|利润表|现金流量表)",
            normalized,
        ):
            return True
    return False


def _statement_boundary_top(page: Any, *, source_id: str) -> float | None:
    return _statement_boundary_top_from_words(
        page.get_text("words"), source_id=source_id
    )


def _statement_boundary_top_from_words(
    words: list[tuple[Any, ...]], *, source_id: str
) -> float | None:
    grouped: dict[tuple[int, int], list[tuple[Any, ...]]] = defaultdict(list)
    for word in words:
        if len(word) < 8:
            continue
        grouped[(int(word[5]), int(word[6]))].append(word)
    lines = [
        {
            "text": " ".join(
                str(word[4])
                for word in sorted(items, key=lambda item: int(item[7]))
            ),
            "top": min(float(word[1]) for word in items),
        }
        for _, items in sorted(
            grouped.items(),
            key=lambda item: min(float(word[1]) for word in item[1]),
        )
    ]
    for index, line in enumerate(lines):
        for width in (1, 2, 3):
            candidate = " ".join(
                str(item["text"]) for item in lines[index : index + width]
            )
            if _is_non_target_statement_boundary(
                candidate, source_id=source_id
            ):
                return float(line["top"])
    return None


def _is_terminal_statement_boundary(
    text: str, *, source_id: str = SOURCE_ID
) -> bool:
    compact_lines = [
        re.sub(r"\s+", "", line).casefold()
        for line in text.splitlines()
        if line.strip()
    ]
    if source_id == "hkex_disclosures":
        return any(
            "notestothefinancialstatements" in line
            or "notestoconsolidatedfinancialstatements" in line
            for line in compact_lines
        )
    for line in compact_lines:
        normalized = _without_section_prefix(line).strip("：:")
        if re.fullmatch(
            r"财务报表附注(?:[（(]续[）)])?",
            normalized,
        ):
            return True
    return False


def _without_section_prefix(value: str) -> str:
    text = re.sub(r"^\d+[、.．]", "", value)
    return re.sub(
        r"^[（(][一二三四五六七八九十百\d]+[）)]",
        "",
        text,
    )


def _page_has_registered_metric_label(
    text: str,
    metric_aliases: dict[str, str],
) -> bool:
    compact_text = re.sub(r"\s+", "", text).casefold()
    return any(alias in compact_text for alias in metric_aliases if alias)


def _english_unit_info(text: str) -> dict[str, str] | None:
    currency_patterns = {
        "HKD": r"(?:HK\$|HKD|Hong\s+Kong\s+dollars?)",
        "CNY": r"(?:RMB|CNY|Renminbi|Chinese\s+yuan)",
        "USD": r"(?:US\$|USD|United\s+States\s+dollars?)",
    }
    scale_pattern = r"(?:millions?|thousands?|['’]000|000s|['’]?M\b)"
    matches: list[dict[str, str]] = []
    for raw_line in text[:2500].splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        currency = next(
            (
                code
                for code, pattern in currency_patterns.items()
                if re.search(pattern, line, re.IGNORECASE)
            ),
            None,
        )
        if not currency:
            continue
        scale_match = re.search(scale_pattern, line, re.IGNORECASE)
        if scale_match:
            scale_text = scale_match.group(0).casefold()
            if "million" in scale_text or scale_text.endswith("m"):
                scale = "million"
            else:
                scale = "thousand"
            matches.append({
                "unit_header": line,
                "unit": f"{scale} {currency}",
                "currency": currency,
                "value_scale": scale,
            })
            continue
        if re.search(
            r"(?:expressed|presented|denominated|amounts?)\s+in",
            line,
            re.IGNORECASE,
        ):
            matches.append({
                "unit_header": line,
                "unit": currency,
                "currency": currency,
                "value_scale": "unit",
            })
    if not matches:
        return None
    if "for information purpose only" in text.casefold() and len(matches) > 1:
        return {
            **matches[0],
            "value_column_policy": "consolidated_first_pair",
        }
    # Numeric extraction normally uses the rightmost period columns. Most
    # dual-currency HKEX statements put their primary value currency last.
    return matches[-1]


def _unit_info(
    text: str, *, source_id: str = SOURCE_ID
) -> dict[str, str] | None:
    if source_id == "hkex_disclosures":
        return _english_unit_info(text)
    header_matches = list(
        re.finditer(
            r"(?:(?:金额单位(?:均)?为|金额单位[:：]?|单位(?:为)?[:：]?)\s*"
            r"(?:人民币\s*)?|"
            r"(?:除另有标明外[，,]?\s*)?所有金额均以\s*人民币\s*)"
            r"(百万元|千元|万元|亿元|元)(?:列示)?",
            text[:1600],
        )
    )
    if not header_matches:
        # Some audited statements render the currency and scale as repeated
        # value-column headers instead of a conventional ``Unit:`` line. Keep
        # this inference narrow: an exact consolidated statement heading, an
        # explicit notes column, two comparative years, and two identical
        # currency/scale columns are all required. This excludes management
        # discussion tables that merely mention a consolidated statement.
        compact_lines = [
            re.sub(r"\s+", "", line).strip("()（）")
            for line in text[:2200].splitlines()
            if line.strip()
        ]
        has_statement_heading = any(
            re.fullmatch(
                r"(?:(?:19|20)\d{2}(?:年度|年\d{1,2}月\d{1,2}日))?"
                r"(?:(?:\d+[、.．])|(?:[（(][一二三四五六七八九十百\d]+[）)]))?"
                r"合并(?:资产负债表|利润表|现金流量表)(?:[（(]续[）)])?",
                line,
            )
            for line in compact_lines[:20]
        )
        has_notes_column = any(
            line in {"附注", "注释"} for line in compact_lines[:30]
        )
        years = set(
            re.findall(r"(?:19|20)\d{2}", "\n".join(compact_lines[:40]))
        )
        currency_column_count = sum(
            line == "人民币" for line in compact_lines[:40]
        )
        scale_counts = {
            scale: sum(line == scale for line in compact_lines[:40])
            for scale in ("百万元", "千元", "万元", "亿元", "元")
        }
        repeated_scales = [
            scale for scale, count in scale_counts.items() if count >= 2
        ]
        if not (
            has_statement_heading
            and has_notes_column
            and len(years) >= 2
            and currency_column_count >= 2
            and len(repeated_scales) == 1
        ):
            return None
        scale = repeated_scales[0]
        unit_by_scale = {
            "元": "CNY",
            "千元": "thousand CNY",
            "万元": "ten_thousand CNY",
            "百万元": "million CNY",
            "亿元": "hundred_million CNY",
        }
        return {
            "unit_header": f"人民币/{scale} comparative value columns",
            "unit": unit_by_scale[scale],
            "currency": "CNY",
            "value_scale": scale,
        }
    # A statement-local declaration follows the section-level note unit and wins.
    header_match = header_matches[-1]
    scale = header_match.group(1)
    unit_by_scale = {
        "元": "CNY",
        "千元": "thousand CNY",
        "万元": "ten_thousand CNY",
        "百万元": "million CNY",
        "亿元": "hundred_million CNY",
    }
    return {
        "unit_header": header_match.group(0),
        "unit": unit_by_scale[scale],
        "currency": "CNY",
        "value_scale": scale,
    }


def _section_unit_info(
    text: str, *, source_id: str = SOURCE_ID
) -> dict[str, str] | None:
    if source_id == "hkex_disclosures":
        return _english_unit_info(text)
    header_match = re.search(
        r"(?:财务附注中报表|财务报表)的单位为[:：]?\s*"
        r"(?:人民币\s*)?(百万元|千元|万元|亿元|元)",
        text[:1600],
    )
    if not header_match:
        return None
    scale = header_match.group(1)
    local_header = re.search(
        r"单位为[:：]?\s*(?:人民币\s*)?(?:百万元|千元|万元|亿元|元)",
        header_match.group(0),
    )
    unit_by_scale = {
        "元": "CNY",
        "千元": "thousand CNY",
        "万元": "ten_thousand CNY",
        "百万元": "million CNY",
        "亿元": "hundred_million CNY",
    }
    return {
        "unit_header": local_header.group(0) if local_header else header_match.group(0),
        "unit": unit_by_scale[scale],
        "currency": "CNY",
        "value_scale": scale,
    }


def _report_year(metadata: dict[str, Any]) -> int | None:
    value = str(metadata.get("record_period_hint") or "").strip()
    if re.fullmatch(r"(?:19|20)\d{2}", value):
        return int(value)
    return None


def _statement_header_text(text: str, statement_type: str) -> str:
    folded = text.casefold()
    offsets = [
        folded.find(title.casefold())
        for title, candidate_type, _ in STATEMENT_LAYOUTS
        if candidate_type == statement_type and folded.find(title.casefold()) >= 0
    ]
    title_start = min(offsets) if offsets else 0
    start = max(0, title_start - 300)
    return text[start : title_start + 2200]


def _has_relative_period_columns(
    text: str,
    statement_type: str,
) -> bool:
    compact = re.sub(r"\s+", "", text)
    if statement_type == "balance_sheet":
        return any(
            left in compact and right in compact
            for left, right in (
                ("本年年末余额", "上年年末余额"),
                ("期末余额", "上年年末余额"),
                ("本期期末", "上期期末"),
                ("期末余额", "期初余额"),
                ("期末数", "期初数"),
            )
        )
    return any(
        left in compact and right in compact
        for left, right in (
            ("本年发生额", "上年发生额"),
            ("本期发生额", "上期发生额"),
            ("本年金额", "上年金额"),
        )
    )


def _periods_for_statement(
    text: str,
    statement_type: str,
    *,
    report_year: int | None = None,
    source_id: str = SOURCE_ID,
    fallback_period_end: date | None = None,
) -> list[dict[str, Any]]:
    header_text = _statement_header_text(text, statement_type)
    if source_id == "hkex_disclosures":
        return _english_periods(
            header_text,
            statement_type,
            report_year=report_year,
            fallback_period_end=fallback_period_end,
        )
    if statement_type == "balance_sheet":
        matches = re.findall(
            r"((?:19|20)\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
            header_text,
        )
        periods = []
        seen = set()
        for year, month, day in matches:
            end = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            if report_year is not None:
                allowed = {
                    f"{report_year:04d}-12-31",
                    f"{report_year:04d}-01-01",
                    f"{report_year - 1:04d}-12-31",
                }
                if end not in allowed:
                    continue
            if end in seen:
                continue
            seen.add(end)
            periods.append(
                {
                    "label": f"{year}年{int(month)}月{int(day)}日",
                    "period_start": None,
                    "period_end": end,
                    "fiscal_year": (
                        report_year - 1
                        if report_year is not None
                        and end == f"{report_year:04d}-01-01"
                        else int(year)
                    ),
                    "fiscal_quarter": "FY",
                }
            )
        has_relative_columns = _has_relative_period_columns(
            header_text, statement_type
        )
        if (
            report_year is not None
            and not periods
            and has_relative_columns
        ):
            current_end = f"{report_year:04d}-12-31"
            seen.add(current_end)
            periods.append(
                {
                    "label": f"{report_year}年12月31日",
                    "period_start": None,
                    "period_end": current_end,
                    "fiscal_year": report_year,
                    "fiscal_quarter": "FY",
                    "period_inference": (
                        "explicit_relative_comparative_header"
                    ),
                }
            )
        if (
            report_year is not None
            and f"{report_year:04d}-12-31" not in seen
        ):
            return []
        if (
            report_year is not None
            and len(periods) == 1
            and has_relative_columns
        ):
            previous_end = f"{report_year - 1:04d}-12-31"
            periods.append(
                {
                    "label": f"{report_year - 1}年12月31日",
                    "period_start": None,
                    "period_end": previous_end,
                    "fiscal_year": report_year - 1,
                    "fiscal_quarter": "FY",
                    "period_inference": "explicit_relative_comparative_header",
                }
            )
        if report_year is not None:
            period_order = {
                f"{report_year:04d}-12-31": 0,
                f"{report_year:04d}-01-01": 1,
                f"{report_year - 1:04d}-12-31": 2,
            }
            periods.sort(
                key=lambda row: period_order.get(row["period_end"], 99)
            )
        return periods[:2]

    years = []
    seen_years = set()
    for year in re.findall(
        r"((?:19|20)\d{2})\s*年(?:度)?",
        header_text,
    ):
        numeric_year = int(year)
        if report_year is not None and numeric_year not in {
            report_year,
            report_year - 1,
        }:
            continue
        if numeric_year in seen_years:
            continue
        seen_years.add(numeric_year)
        years.append(numeric_year)
    if report_year is not None and report_year not in seen_years:
        return []
    if (
        report_year is not None
        and len(years) == 1
        and _has_relative_period_columns(header_text, statement_type)
    ):
        years.append(report_year - 1)
    if report_year is not None:
        years = [
            year
            for year in (report_year, report_year - 1)
            if year in years
        ]
    return [
        {
            "label": f"{year}年度",
            "period_start": f"{year:04d}-01-01",
            "period_end": f"{year:04d}-12-31",
            "fiscal_year": year,
            "fiscal_quarter": "FY",
            "period_inference": (
                "explicit_relative_comparative_header"
                if year not in seen_years
                else "explicit_statement_header"
            ),
        }
        for year in years[:2]
    ]


def _direct_periods_for_statement_page(
    text: str,
    statement: dict[str, Any],
    *,
    report_year: int | None = None,
    source_id: str = SOURCE_ID,
    fallback_period_end: date | None = None,
) -> list[dict[str, Any]]:
    if statement.get("statement_inherited") and statement.get("periods"):
        return []
    return _periods_for_statement(
        text,
        str(statement["statement_type"]),
        report_year=report_year,
        source_id=source_id,
        fallback_period_end=fallback_period_end,
    )


_ENGLISH_MONTHS = {
    name.casefold(): index
    for index, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}


def _english_dates(text: str) -> list[date]:
    month_names = "|".join(name.title() for name in _ENGLISH_MONTHS)
    matches: list[tuple[int, date]] = []
    patterns = (
        re.compile(
            rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
            rf"(?P<month>{month_names})\s*,?\s*(?P<year>20\d{{2}})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<month>{month_names})\s+"
            rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*"
            rf"(?P<year>20\d{{2}})",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            try:
                parsed = date(
                    int(match.group("year")),
                    _ENGLISH_MONTHS[match.group("month").casefold()],
                    int(match.group("day")),
                )
            except ValueError:
                continue
            matches.append((match.start(), parsed))
    output: list[date] = []
    seen: set[date] = set()
    for _, parsed in sorted(matches):
        if parsed not in seen:
            seen.add(parsed)
            output.append(parsed)
    return output


def _previous_anniversary(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def _english_periods(
    text: str,
    statement_type: str,
    *,
    report_year: int | None,
    fallback_period_end: date | None = None,
) -> list[dict[str, Any]]:
    if report_year is None:
        return []
    explicit_dates = [
        value
        for value in _english_dates(text)
        if value.year in {report_year, report_year - 1}
    ]
    current = next(
        (value for value in explicit_dates if value.year == report_year),
        None,
    )
    current_inferred = False
    if (
        current is None
        and fallback_period_end
        and fallback_period_end.year == report_year
    ):
        current = fallback_period_end
        current_inferred = True
    if current is None:
        return []
    previous = next(
        (value for value in explicit_dates if value.year == report_year - 1),
        _previous_anniversary(current),
    )
    ends = [current, previous]
    periods: list[dict[str, Any]] = []
    for period_end in ends:
        period_start = None
        if statement_type != "balance_sheet":
            period_start = _previous_anniversary(period_end) + timedelta(days=1)
        periods.append(
            {
                "label": period_end.isoformat(),
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat(),
                "fiscal_year": period_end.year,
                "fiscal_quarter": "FY",
                "period_inference": (
                    "audited_statement_section_period"
                    if current_inferred and period_end == current
                    else "audited_statement_section_comparative_period"
                    if current_inferred
                    else "explicit_statement_header"
                    if period_end in explicit_dates
                    else "explicit_current_date_comparative_column"
                ),
            }
        )
    return periods


def _english_report_period_end(
    text: str,
    *,
    report_year: int | None,
    source_id: str = SOURCE_ID,
) -> date | None:
    if source_id != "hkex_disclosures" or report_year is None:
        return None
    folded = re.sub(r"\s+", " ", text)
    for match in re.finditer(
        r"(?:year ended|financial position as at)\s+.{0,45}",
        folded,
        re.IGNORECASE,
    ):
        for value in _english_dates(match.group(0)):
            if value.year == report_year:
                return value
    return None


def _clean_rows(raw_rows: list[list[Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_row in raw_rows:
        row = [
            re.sub(r"\s+", "", str(cell or "")).strip()
            for cell in raw_row
        ]
        if any(row):
            rows.append(row)
    return rows


def _missing_positioned_fallback_rows(
    page_spec: dict[str, Any],
    metric_aliases: dict[str, str],
    metric_statement_types: dict[str, str],
    page_candidates: list[dict[str, Any]],
) -> list[list[str]]:
    """Return one strict alias per page metric not fully recovered from tables."""
    expected_periods = {
        str(period["period_end"])
        for period in page_spec.get("periods", [])
        if period.get("period_end")
    }
    covered_periods: dict[str, set[str]] = defaultdict(set)
    for candidate in page_candidates:
        metric_id = str(candidate.get("matched_metric_id") or "")
        period_end = str(candidate.get("period_end") or "")
        if metric_id and period_end:
            covered_periods[metric_id].add(period_end)

    compact_page_text = re.sub(
        r"\s+", "", str(page_spec.get("page_text") or "")
    ).casefold()
    fallback_alias_by_metric: dict[str, str] = {}
    for alias, metric_id in sorted(
        metric_aliases.items(),
        key=lambda item: (-len(item[0]), item[0], item[1]),
    ):
        if (
            not alias
            or alias not in compact_page_text
            or metric_statement_types.get(metric_id)
            != page_spec.get("statement_type")
            or expected_periods.issubset(covered_periods.get(metric_id, set()))
        ):
            continue
        fallback_alias_by_metric.setdefault(metric_id, alias)
    return [
        [alias]
        for _, alias in sorted(fallback_alias_by_metric.items())
    ]


def _logical_table_rows(
    rows: list[list[str]], expected_value_count: int
) -> list[tuple[int, list[int], list[str]]]:
    """Join one wrapped label row to its immediately following value row."""
    logical: list[tuple[int, list[int], list[str]]] = []
    for row_index, row in enumerate(rows):
        row_values = sum(_decimal_value(cell) is not None for cell in row)
        if row_values or row_index + 1 >= len(rows):
            logical.append((row_index, [row_index], row))
            continue
        following = rows[row_index + 1]
        following_values = sum(
            _decimal_value(cell) is not None for cell in following
        )
        if following_values < expected_value_count:
            logical.append((row_index, [row_index], row))
            continue
        width = max(len(row), len(following))
        padded_row = [*row, *([""] * (width - len(row)))]
        padded_following = [
            *following,
            *([""] * (width - len(following))),
        ]
        combined = [
            padded_row[index] + padded_following[index]
            if index == 0
            else padded_following[index] or padded_row[index]
            for index in range(width)
        ]
        logical.append((row_index, [row_index, row_index + 1], combined))
    return logical


def _table_numeric_values(
    row: list[str],
    expected_value_count: int,
    *,
    value_column_policy: str,
) -> list[tuple[int, str, Decimal]]:
    numeric = [
        (index, cell, value)
        for index, cell in enumerate(row)
        if (value := _decimal_value(cell)) is not None
    ]
    if value_column_policy == "consolidated_first_pair":
        required = expected_value_count * 2
        if len(numeric) < required:
            return []
        return numeric[-required:][:expected_value_count]
    if len(numeric) < expected_value_count:
        return []
    return numeric[-expected_value_count:]


def _mapped_rows(
    rows: list[list[str]],
    page_spec: dict[str, Any],
    metric_aliases: dict[str, str],
    metric_statement_types: dict[str, str],
    raw_object_id: str,
    entity_id: str,
    metadata: dict[str, Any],
    table_index: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    periods = page_spec["periods"]
    for row_index, row_span, row in _logical_table_rows(rows, len(periods)):
        if not row:
            continue
        matched_alias = _matched_metric_alias(row, metric_aliases)
        if not matched_alias:
            continue
        source_field_name, metric_id = matched_alias
        expected_statement_type = metric_statement_types.get(metric_id)
        if (
            not expected_statement_type
            or expected_statement_type != page_spec["statement_type"]
        ):
            continue
        source_field_name, numeric_cells = _positioned_metric_values(
            page_spec.get("page_words") or [],
            source_field_name,
            metric_id,
            metric_aliases,
            len(periods),
            value_column_policy=page_spec["value_column_policy"],
        )
        value_extraction_method = "positioned_words_exact_label"
        if not numeric_cells and len(row_span) == 2:
            numeric_cells = _table_numeric_values(
                row,
                len(periods),
                value_column_policy=page_spec["value_column_policy"],
            )
            value_extraction_method = "adjacent_wrapped_table_rows"
        if not numeric_cells:
            continue
        if len(numeric_cells) != len(periods):
            continue
        for period, (column_index, raw_value, value) in zip(
            periods,
            numeric_cells,
            strict=True,
        ):
            period_inference = period.get(
                "period_inference",
                "explicit_statement_header",
            )
            unit = page_spec["unit"]
            currency = page_spec["currency"]
            if metric_id in {
                "earnings_per_share_basic",
                "earnings_per_share_diluted",
            }:
                unit = f"{currency}_per_share"
            evidence_text = (
                f"{page_spec['statement_title']} | {period['label']} | "
                f"{source_field_name} | {raw_value} | {page_spec['unit_header']} | "
                f"unit_source_page={page_spec['unit_source_page']} | "
                f"statement_source_page={page_spec['statement_source_page']} | "
                f"period_source_page={page_spec['period_source_page']} | "
                f"period_basis={period_inference}"
            )
            evidence_sha256 = hashlib.sha256(
                (
                    f"{raw_object_id}|{page_spec['page_number']}|{table_index}|"
                    f"{row_index}|{column_index}|{page_spec['unit_source_page']}|"
                    f"{page_spec['statement_source_page']}|"
                    f"{page_spec['period_source_page']}|"
                    f"{page_spec['value_column_policy']}|{evidence_text}"
                ).encode("utf-8")
            ).hexdigest()
            page_text = page_spec["page_text"]
            evidence_errors = []
            compact_page_text = re.sub(r"\s+", "", page_text).casefold()
            if source_field_name not in compact_page_text:
                evidence_errors.append("source_label_missing_from_pymupdf_text")
            compact_raw = re.sub(r"\s+", "", raw_value)
            if compact_raw and compact_raw not in re.sub(r"\s+", "", page_text):
                evidence_errors.append("raw_value_missing_from_pymupdf_text")
            evidence_status = (
                "verified" if not evidence_errors else "failed"
            )
            candidate_id = _id(
                "cncand",
                raw_object_id,
                page_spec["page_number"],
                table_index,
                row_index,
                column_index,
                entity_id,
                metric_id,
                period["period_end"],
                str(value),
                unit,
            )
            extraction_metadata = {
                "parser_version": PARSER_VERSION,
                "evidence_policy_version": EVIDENCE_POLICY_VERSION,
                "source_id": metadata.get("source_id") or SOURCE_ID,
                "statement_title": page_spec["statement_title"],
                "statement_source_page": page_spec["statement_source_page"],
                "statement_inherited": page_spec["statement_inherited"],
                "period_source_page": page_spec["period_source_page"],
                "period_label": period["label"],
                "period_inference": period_inference,
                "unit_header": page_spec["unit_header"],
                "unit_source_page": page_spec["unit_source_page"],
                "unit_inherited": page_spec["unit_inherited"],
                "value_column_policy": page_spec["value_column_policy"],
                "value_extraction_method": value_extraction_method,
                "table_row_span": row_span,
                "raw_value_text": raw_value,
                "report_type": metadata.get("report_type"),
                "announcement_id": metadata.get("announcement_id"),
                "source_publish_date": metadata.get("source_publish_date"),
                "record_period_hint": metadata.get("record_period_hint"),
                "financial_scope_type": "consolidated_entity",
                "entity_scope_id": entity_id,
                "verification_methods": [
                    TABLE_EXTRACTION_METHOD,
                    TEXT_EXTRACTION_METHOD,
                ],
                "validation_errors": evidence_errors,
            }
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "raw_object_id": raw_object_id,
                    "table_id": "",
                    "entity_id": entity_id,
                    "metric_hint": metric_id,
                    "value": str(value),
                    "unit": unit,
                    "period_hint": period["period_end"],
                    "period_start": period["period_start"],
                    "period_end": period["period_end"],
                    "fiscal_year": period["fiscal_year"],
                    "fiscal_quarter": period["fiscal_quarter"],
                    "currency": currency,
                    "value_scale": page_spec["value_scale"],
                    "source_field_name": source_field_name,
                    "statement_type": page_spec["statement_type"],
                    "financial_scope_type": "consolidated_entity",
                    "page_number": page_spec["page_number"],
                    "row_index": row_index,
                    "column_index": column_index,
                    "extraction_metadata": extraction_metadata,
                    "evidence_sha256": evidence_sha256,
                    "evidence_text": evidence_text,
                    "confidence_score": 0.97 if not evidence_errors else 0.0,
                    "review_status": (
                        "cn_pdf_programmatic_verified"
                        if not evidence_errors
                        else "cn_pdf_evidence_failed"
                    ),
                    "candidate_state": (
                        "evidence_verified"
                        if not evidence_errors
                        else "parsed"
                    ),
                    "state_reason": (
                        "Strict metric alias, explicit consolidated scope, period, "
                        "page or bounded statement-section currency/scale evidence, "
                        "and independent page-text evidence passed."
                        if not evidence_errors
                        else "; ".join(evidence_errors)
                    ),
                    "matched_metric_id": metric_id,
                    "evidence_status": evidence_status,
                    "cross_check_status": "not_run",
                    "promotion_status": "not_promoted",
                    "promoted_fact_id": None,
                    "qa_eligible": 0,
                    "kg_eligible": 0,
                    "_raw_value_text": raw_value,
                    "_period_label": period["label"],
                    "_unit_source_page": page_spec["unit_source_page"],
                    "_unit_evidence_text": page_spec["unit_header"],
                    "_statement_source_page": page_spec["statement_source_page"],
                    "_period_source_page": page_spec["period_source_page"],
                    "_source_publish_date": metadata.get("source_publish_date"),
                    "_source_id": metadata.get("source_id") or SOURCE_ID,
                    "_validation_errors": evidence_errors,
                }
            )
    return candidates


def _matched_metric_alias(
    row: list[str],
    metric_aliases: dict[str, str],
) -> tuple[str, str] | None:
    label_cells = [
        _normalize_label(cell)
        for cell in row
        if cell and _decimal_value(cell) is None
    ]
    label_cells = [cell for cell in label_cells if cell]
    label_candidates = {
        "".join(label_cells),
    }
    if len(label_cells) == 1:
        label_candidates.add(label_cells[0])
    matches = [
        (alias, metric_id)
        for alias, metric_id in metric_aliases.items()
        if alias
        and any(
            _strict_source_label_match(label, alias)
            for label in label_candidates
        )
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (-len(item[0]), item[0], item[1]))
    return matches[0]

def _positioned_numeric_values(
    words: list[dict[str, Any]],
    source_field_name: str,
    expected_value_count: int,
    *,
    value_column_policy: str = "rightmost_periods",
) -> list[tuple[int, str, Decimal]]:
    """Recover intact values from positioned words when table cells split digits."""
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(
        words,
        key=lambda item: (
            round(float(item.get("top") or 0), 1),
            float(item.get("x0") or 0),
        ),
    ):
        top = float(word.get("top") or 0)
        matching = next(
            (
                line
                for line in reversed(lines[-3:])
                if abs(float(line[0].get("top") or 0) - top) <= 2.0
            ),
            None,
        )
        if matching is None:
            lines.append([word])
        else:
            matching.append(word)

    for line_index, line in enumerate(lines):
        ordered = sorted(line, key=lambda item: float(item.get("x0") or 0))
        numeric = [
            (index, str(word.get("text") or ""), value)
            for index, word in enumerate(ordered)
            if (value := _decimal_value(word.get("text"))) is not None
        ]
        if len(numeric) < expected_value_count:
            continue
        label_matches = False
        for start_index in range(max(0, line_index - 2), line_index + 1):
            prefix_lines = lines[start_index:line_index]
            if any(
                _decimal_value(word.get("text")) is not None
                for prefix_line in prefix_lines
                for word in prefix_line
            ):
                continue
            label_words = [
                word
                for candidate_line in [*prefix_lines, ordered]
                for word in sorted(
                    candidate_line,
                    key=lambda item: float(item.get("x0") or 0),
                )
                if _decimal_value(word.get("text")) is None
            ]
            line_label = _normalize_label(
                "".join(str(word.get("text") or "") for word in label_words)
            )
            if _strict_source_label_match(line_label, source_field_name):
                label_matches = True
                break
        if not label_matches:
            continue
        if value_column_policy == "consolidated_first_pair":
            required_columns = expected_value_count * 2
            if len(numeric) < required_columns:
                continue
            return numeric[-required_columns:][:expected_value_count]
        return numeric[-expected_value_count:]
    return []


def _positioned_metric_values(
    words: list[dict[str, Any]],
    source_field_name: str,
    metric_id: str,
    metric_aliases: dict[str, str],
    expected_value_count: int,
    *,
    value_column_policy: str = "rightmost_periods",
) -> tuple[str, list[tuple[int, str, Decimal]]]:
    aliases = sorted(
        {
            source_field_name,
            *(
                alias
                for alias, candidate_metric_id in metric_aliases.items()
                if candidate_metric_id == metric_id
            ),
        },
        key=lambda value: (-len(value), value),
    )
    for alias in aliases:
        values = _positioned_numeric_values(
            words,
            alias,
            expected_value_count,
            value_column_policy=value_column_policy,
        )
        if values:
            return alias, values
    return source_field_name, []


def _strict_source_label_match(label: str, source_field_name: str) -> bool:
    source_label = _normalize_label(source_field_name)
    if not source_label:
        return False
    if (
        label == source_label
        or label.startswith(f"{source_label}（")
        or label.startswith(f"{source_label}(")
    ):
        return True
    if not re.search(r"[a-z]", source_label):
        return False
    cjk_punctuation_pattern = (
        r"[\u3400-\u9fff\uf900-\ufaff"
        r"\u3000-\u303f\uff00-\uffef╱]+"
    )
    suffix = label[len(source_label) :] if label.startswith(source_label) else ""
    if suffix and re.fullmatch(cjk_punctuation_pattern, suffix):
        return True
    prefix = label[: -len(source_label)] if label.endswith(source_label) else ""
    return bool(prefix and re.fullmatch(cjk_punctuation_pattern, prefix))




def _decimal_value(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text or text in {"-", "—", "–", "不适用", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace(",", "")
        .replace("，", "")
        .replace(" ", "")
        .replace("−", "-")
        .replace("－", "-")
        .replace("(", "")
        .replace(")", "")
    )
    cleaned = re.sub(r"[^\d.+-]", "", cleaned)
    if not cleaned or cleaned in {"+", "-", "."}:
        return None
    try:
        result = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -abs(result) if negative else result


def _normalize_label(value: str) -> str:
    text = re.sub(r"\s+", "", value or "").casefold()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"^[ivxlcdm]+[.．]", "", text)
    text = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", text)
    text = re.sub(r"^[（(][一二三四五六七八九十\d]+[）)]", "", text)
    text = text.lstrip("、.．")
    text = re.sub(r"^(?:加|减)[:：]", "", text)
    text = text.replace("（续）", "").replace("(续)", "")
    return text.strip("：:")

def _apply_accounting_identity_checks(
    candidates: list[dict[str, Any]],
) -> None:
    """Reject complete balance-sheet triples that violate A = L + E."""
    groups: dict[tuple[Any, ...], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    required = {"total_assets", "total_liabilities", "shareholders_equity"}
    for candidate in candidates:
        metric_id = candidate.get("matched_metric_id")
        if metric_id not in required or candidate.get("evidence_status") != "verified":
            continue
        groups[
            (
                candidate.get("raw_object_id"),
                candidate.get("entity_id"),
                candidate.get("period_end"),
                candidate.get("unit"),
                candidate.get("currency"),
                candidate.get("financial_scope_type"),
            )
        ][metric_id].append(candidate)

    for metric_rows in groups.values():
        if set(metric_rows) != required:
            continue
        equity_source_fields = {
            _normalize_label(str(row.get("source_field_name") or ""))
            for row in metric_rows["shareholders_equity"]
        }
        total_equity_labels = {
            _normalize_label(value)
            for value in (
                "所有者权益合计",
                "股东权益合计",
                "Net assets",
                "Total equity",
                "Total shareholders' equity",
            )
        }
        if any(
            source_field and source_field not in total_equity_labels
            for source_field in equity_source_fields
        ):
            continue
        values = {
            metric_id: {Decimal(row["value"]) for row in rows}
            for metric_id, rows in metric_rows.items()
        }
        if any(len(metric_values) != 1 for metric_values in values.values()):
            continue
        assets = next(iter(values["total_assets"]))
        liabilities = next(iter(values["total_liabilities"]))
        equity = next(iter(values["shareholders_equity"]))
        tolerance = max(Decimal("1"), abs(assets) * Decimal("0.000001"))
        if abs(assets - liabilities - equity) <= tolerance:
            continue
        for rows in metric_rows.values():
            for row in rows:
                errors = row.setdefault("_validation_errors", [])
                errors.append("balance_sheet_identity_failed")
                row["evidence_status"] = "failed_accounting_identity"
                row["candidate_state"] = "parsed"
                row["promotion_status"] = "rejected_evidence"
                row["review_status"] = "cn_pdf_accounting_identity_failed"
                row["state_reason"] = (
                    "Complete consolidated balance-sheet values violate "
                    "assets = liabilities + shareholders' equity."
                )
                row["extraction_metadata"]["validation_errors"] = list(errors)




def _apply_cross_checks(
    candidates: list[dict[str, Any]],
    *,
    allow_single: bool,
) -> None:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate["evidence_status"] != "verified":
            candidate["cross_check_status"] = "evidence_failed"
            candidate["promotion_status"] = "rejected_evidence"
            continue
        groups[
            (
                candidate["entity_id"],
                candidate["matched_metric_id"],
                candidate["period_end"],
                candidate["unit"],
                candidate["currency"],
                candidate["financial_scope_type"],
            )
        ].append(candidate)

    for rows in groups.values():
        selected_rows: list[dict[str, Any]] = []
        rows_by_object: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            rows_by_object[str(row["raw_object_id"])].append(row)

        for object_rows in rows_by_object.values():
            object_values = {str(row["value"]) for row in object_rows}
            if len(object_values) == 1:
                selected_rows.extend(object_rows)
                continue

            selected_page = max(
                int(row.get("page_number") or row.get("_statement_source_page") or 0)
                for row in object_rows
            )
            primary_rows = [
                row
                for row in object_rows
                if int(
                    row.get("page_number")
                    or row.get("_statement_source_page")
                    or 0
                )
                == selected_page
            ]
            primary_values = {str(row["value"]) for row in primary_rows}
            if len(primary_values) != 1:
                _reject_conflict_rows(
                    object_rows,
                    "The latest primary-statement page in one official "
                    "document produced multiple values for the same semantic "
                    "fact.",
                )
                continue

            selected_value = next(iter(primary_values))
            selected_rows.extend(primary_rows)
            for row in object_rows:
                row["extraction_metadata"][
                    "same_document_selected_statement_page"
                ] = selected_page
                row["extraction_metadata"][
                    "same_document_selected_value"
                ] = selected_value
                if row in primary_rows:
                    continue
                row["candidate_state"] = "superseded"
                row["cross_check_status"] = (
                    "superseded_same_document_summary"
                )
                row["promotion_status"] = "rejected_superseded"
                row["review_status"] = (
                    "cn_pdf_superseded_same_document_summary"
                )
                row["state_reason"] = (
                    "A later primary-statement page in the same official "
                    "document reports the selected semantic fact."
                )

        if not selected_rows:
            continue
        values = {str(row["value"]) for row in selected_rows}
        object_ids = {str(row["raw_object_id"]) for row in selected_rows}
        if len(values) == 1 and len(object_ids) > 1:
            for row in selected_rows:
                row["candidate_state"] = "cross_checked"
                row["cross_check_status"] = "matched_official_comparative"
                row["promotion_status"] = "approved_for_atomic_fact"
            continue
        if len(values) == 1:
            for row in selected_rows:
                row["cross_check_status"] = "single_official_document"
                row["promotion_status"] = (
                    "approved_for_atomic_fact"
                    if allow_single
                    else "requires_cross_check"
                )
            continue

        publish_dates = {
            str(row.get("_source_publish_date") or "")
            for row in selected_rows
        }
        if "" in publish_dates:
            _reject_conflict_rows(
                selected_rows,
                "Conflicting official versions lack complete publication dates.",
            )
            continue
        latest_publish_date = max(publish_dates)
        latest_rows = [
            row
            for row in selected_rows
            if str(row.get("_source_publish_date")) == latest_publish_date
        ]
        latest_values = {str(row["value"]) for row in latest_rows}
        if len(latest_values) != 1:
            _reject_conflict_rows(
                selected_rows,
                "The latest official publication contains conflicting values.",
            )
            continue
        selected_value = next(iter(latest_values))
        for row in selected_rows:
            row["extraction_metadata"]["latest_official_publish_date"] = (
                latest_publish_date
            )
            row["extraction_metadata"]["selected_official_value"] = selected_value
            if str(row["value"]) == selected_value:
                row["candidate_state"] = "cross_checked"
                row["cross_check_status"] = "latest_official_restated_value"
                row["promotion_status"] = "approved_for_atomic_fact"
                row["review_status"] = "cn_pdf_latest_official_version"
                row["state_reason"] = (
                    "Selected by latest official publication date after a "
                    "historical comparative value changed."
                )
            else:
                row["candidate_state"] = "superseded"
                row["cross_check_status"] = "superseded_official_comparative"
                row["promotion_status"] = "rejected_superseded"
                row["review_status"] = "cn_pdf_superseded_official_version"
                row["state_reason"] = (
                    "A later official filing reports a revised comparative value."
                )


def _reject_conflict_rows(
    rows: list[dict[str, Any]],
    reason: str,
) -> None:
    for row in rows:
        row["candidate_state"] = "conflict"
        row["cross_check_status"] = "conflict"
        row["promotion_status"] = "rejected_conflict"
        row["review_status"] = "cn_pdf_conflict_requires_review"
        row["state_reason"] = reason


def _insert_chunk(
    db: DBProtocol,
    chunk: dict[str, Any],
    build_id: str,
) -> None:
    stable_id = chunk["chunk_id"]
    chunk_id = versioned_id(stable_id, build_id)
    db.execute(
        """
        INSERT INTO document_text_chunks (
            chunk_id, stable_chunk_id, build_id, is_active, superseded_by,
            raw_object_id, source_id, page_number, section_title, text,
            char_start, char_end, extraction_method, confidence_score
        ) VALUES (?, ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            chunk_id,
            stable_id,
            build_id,
            chunk["raw_object_id"],
            chunk["source_id"],
            chunk["page_number"],
            chunk["section_title"],
            chunk["text"],
            chunk["char_start"],
            chunk["char_end"],
            chunk["extraction_method"],
            chunk["confidence_score"],
        ],
    )


def _insert_table(
    db: DBProtocol,
    table: dict[str, Any],
    table_id: str,
    build_id: str,
) -> None:
    db.execute(
        """
        INSERT INTO raw_extracted_tables (
            table_id, stable_table_id, build_id, is_active, superseded_by,
            raw_object_id, source_id, page_number, table_index,
            raw_table_json, extraction_method, confidence_score
        ) VALUES (?, ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            table_id,
            table["table_id"],
            build_id,
            table["raw_object_id"],
            table["source_id"],
            table["page_number"],
            table["table_index"],
            json.dumps(
                table["raw_table_json"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            table["extraction_method"],
            table["confidence_score"],
        ],
    )


def _insert_candidate(
    db: DBProtocol,
    candidate: dict[str, Any],
    candidate_id: str,
    table_id: str,
    build_id: str,
) -> None:
    columns = [
        "candidate_id",
        "stable_candidate_id",
        "build_id",
        "is_active",
        "superseded_by",
        "raw_object_id",
        "table_id",
        "entity_id",
        "metric_hint",
        "value",
        "unit",
        "period_hint",
        "period_start",
        "period_end",
        "fiscal_year",
        "fiscal_quarter",
        "currency",
        "value_scale",
        "source_field_name",
        "statement_type",
        "financial_scope_type",
        "page_number",
        "row_index",
        "column_index",
        "extraction_metadata",
        "evidence_sha256",
        "evidence_text",
        "confidence_score",
        "review_status",
        "candidate_state",
        "state_reason",
        "matched_metric_id",
        "evidence_status",
        "cross_check_status",
        "promotion_status",
        "promoted_fact_id",
        "qa_eligible",
        "kg_eligible",
    ]
    row = {
        **candidate,
        "candidate_id": candidate_id,
        "stable_candidate_id": candidate["candidate_id"],
        "build_id": build_id,
        "is_active": 1,
        "superseded_by": None,
        "table_id": table_id,
        "extraction_metadata": json.dumps(
            candidate["extraction_metadata"],
            ensure_ascii=False,
            sort_keys=True,
        ),
    }
    db.execute(
        f"""
        INSERT INTO candidate_facts ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        """,
        [row.get(column) for column in columns],
    )


def _insert_evidence(
    db: DBProtocol,
    candidate: dict[str, Any],
    candidate_id: str,
    table_id: str,
    build_id: str,
) -> None:
    evidence_id = _id(
        "cnevidence",
        candidate_id,
        candidate["evidence_sha256"],
    )
    db.execute(
        """
        INSERT INTO candidate_fact_evidence (
            evidence_id, candidate_id, build_id, raw_object_id, table_id,
            page_number, unit_source_page, unit_evidence_text, statement_source_page, period_source_page, statement_type,
            financial_scope_type, row_index, column_index, source_field_name,
            raw_value_text, period_label, evidence_text, evidence_sha256,
            verification_method, validation_status, validation_errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            evidence_id,
            candidate_id,
            build_id,
            candidate["raw_object_id"],
            table_id,
            candidate["page_number"],
            candidate["_unit_source_page"],
            candidate["_unit_evidence_text"],
            candidate["_statement_source_page"],
            candidate["_period_source_page"],
            candidate["statement_type"],
            candidate["financial_scope_type"],
            candidate["row_index"],
            candidate["column_index"],
            candidate["source_field_name"],
            candidate["_raw_value_text"],
            candidate["_period_label"],
            candidate["evidence_text"],
            candidate["evidence_sha256"],
            "pdfplumber_cells+pymupdf_text",
            candidate["evidence_status"],
            json.dumps(
                candidate["_validation_errors"],
                ensure_ascii=False,
                sort_keys=True,
            ),
        ],
    )


def _policy(config: dict[str, Any]) -> dict[str, Any]:
    return dict(
        dict(config.get("document_extraction") or {}).get(
            "cn_financial_statements"
        )
        or {}
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _iso_date_value(value: Any) -> str | None:
    """Keep database date values stable at the JSON metadata boundary."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _record_failure(
    report: dict[str, Any],
    obj: dict[str, Any],
    code: str,
    message: str,
) -> None:
    report["failed_object_count"] += 1
    report["failure_counts"][code] += 1
    if len(report["failures"]) < 100:
        report["failures"].append(
            {
                "raw_object_id": obj.get("raw_object_id"),
                "storage_uri": obj.get("storage_uri"),
                "code": code,
                "message": message,
            }
        )


def _finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        **report,
        "source_object_counts": dict(
            sorted(report["source_object_counts"].items())
        ),
        "source_candidate_counts": dict(
            sorted(report["source_candidate_counts"].items())
        ),
        "cross_check_counts": dict(
            sorted(report["cross_check_counts"].items())
        ),
        "metric_counts": dict(
            report["metric_counts"].most_common()
        ),
        "statement_counts": dict(
            sorted(report["statement_counts"].items())
        ),
        "failure_counts": dict(
            sorted(report["failure_counts"].items())
        ),
    }


def write_cn_statement_report(
    report: dict[str, Any],
    output_dir: str,
) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "cn_financial_statement_extraction_report.json"
    md_path = output / "cn_financial_statement_extraction_report.md"
    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# CN Financial Statement Extraction Report",
        "",
        f"Build: {report['build_id']}",
        f"Objects selected: {report['object_count']}",
        f"Objects parsed: {report['parsed_object_count']}",
        f"Objects failed or ineligible: {report['failed_object_count']}",
        f"Statement pages: {report['statement_page_count']}",
        f"Tables: {report['table_count']}",
        f"Candidates: {report['candidate_count']}",
        f"Evidence verified: {report['evidence_verified_count']}",
        f"Approved for Atomic Fact build: {report['promotion_approved_count']}",
        "",
        "## Sources",
        "",
    ]
    for key, value in report.get("source_object_counts", {}).items():
        lines.append(
            f"- {key}: objects={value}; candidates="
            f"{report.get('source_candidate_counts', {}).get(key, 0)}"
        )
    lines.extend([
        "",
        "## Cross-check Status",
        "",
    ])
    for key, value in report.get("cross_check_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Metrics", ""])
    for key, value in report.get("metric_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failure Reasons", ""])
    for key, value in report.get("failure_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Constraints", ""])
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


def _id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"{prefix}_{digest}"
