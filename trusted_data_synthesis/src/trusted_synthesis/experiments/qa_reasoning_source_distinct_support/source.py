"""The one fixed source-only census and its reproducible, finite dispositions.

The selection rule was fixed before the exploratory census. The exact page
interpretations below record that census's findings; replaying them is a
reproduction, not a new blind source search. No Runtime or FinQA QA field is used.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

ARCHIVE_PATH = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
ARCHIVE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
ARCHIVE_BYTE_COUNT = 14_395_143
ARCHIVE_RECORD_COUNT = 1_147
SOURCE_FIELDS = ("id", "filename", "table_ori", "pre_text", "post_text")
REVENUE_PATTERN = r"\brevenues?\b|\bsales\b"
STRUCTURE_PATTERN = (
    r"\btotal\b|\boperating (income|profit)\b|\bincome from operations\b|"
    r"\bproducts?\b|\bservices?\b"
)
INCOME_PATTERN = (
    r"operating\s+(income|profit|earnings|loss)|income\s+from\s+operations|"
    r"profit\s+from\s+operations"
)
INCOME_REPORT_KEYS = ("C/2009", "JPM/2014", "JPM/2015", "UNP/2015", "UNP/2016")

# Findings are attached to exact pages, not open-ended issuer-based selectors.
# A different Archive cannot inherit these source interpretations.
PAGE_DISPOSITIONS = {
    "ANSS/2012/page_93.pdf": (
        "requires_more_than_two_disclosed_components",
        "Six geographic revenue components are disclosed; two would omit source items.",
    ),
    "APD/2016/page_40.pdf": (
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "Industrial gases Americas segment Sales/Operating income table has no exhaustive "
        "two-component revenue partition.",
    ),
    "C/2009/page_45.pdf": (
        "segment_scope_and_operating_income_absent",
        "Net-interest plus non-interest revenues belongs to Special Asset Pool, not "
        "consolidated Citi; the permitted same-report records contain no operating-income source.",
    ),
    "CDW/2017/page_38.pdf": (
        "complete_revenue_partition_absent",
        "Net sales and Income from operations are disclosed; exhaustive revenue components "
        "are not independently disclosed.",
    ),
    "DRE/2002/page_15.pdf": (
        "total_is_not_revenue",
        "The total is property/land disposal gains net of impairment, not revenue.",
    ),
    "DRE/2005/page_30.pdf": (
        "total_is_not_revenue",
        "The total is land/ownership-interest disposal gains net of impairment, not revenue.",
    ),
    "FIS/2016/page_9.pdf": (
        "requires_more_than_two_disclosed_components",
        "IFS, GFS, and Corporate & Other are three disclosed components; the third cannot "
        "be omitted or relabelled as a computed raw Evidence item.",
    ),
    "HII/2015/page_121.pdf": (
        "complete_revenue_partition_absent",
        "Sales and service revenues is one disclosed scalar row, not two separately "
        "disclosed scalar components.",
    ),
    "IP/2006/page_30.pdf": (
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "The segment Sales/Operating Profit table has no exhaustive revenue partition.",
    ),
    "IP/2006/page_31.pdf": (
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "The segment Sales/Operating Profit table has no exhaustive revenue partition.",
    ),
    "JPM/2014/page_70.pdf": (
        "same_report_operating_income_absent",
        "Noninterest revenue plus Net interest income supports Total net revenue, but "
        "the permitted same-report records contain no operating-income evidence.",
    ),
    "JPM/2015/page_82.pdf": (
        "same_report_operating_income_absent",
        "Noninterest revenue plus Net interest income supports Total net revenue, but "
        "the permitted same-report records contain no operating-income evidence.",
    ),
    "LMT/2014/page_50.pdf": (
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "The Space Systems segment table has no exhaustive revenue partition.",
    ),
    "LMT/2016/page_49.pdf": (
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "The Missiles and Fire Control segment table has no exhaustive revenue partition.",
    ),
    "MRK/2013/page_3.pdf": (
        "requires_more_than_two_disclosed_components",
        "Pharmaceutical, Animal Health, Consumer Care, and Other Revenues exceed two "
        "top-level components; the listed top pharmaceutical products are not exhaustive.",
    ),
    "MRO/2003/page_84.pdf": (
        "total_is_not_revenue",
        "The table total is net derivative losses by risk strategy, not revenue.",
    ),
    "SNA/2013/page_83.pdf": (
        "total_is_not_revenue",
        "The table total is other accrued liabilities; deferred subscription revenue is "
        "a liability row, not the current-period revenue total.",
    ),
    "UNP/2015/page_56.pdf": (
        "same_report_operating_income_absent",
        "Total freight revenues plus Other revenues supports Total operating revenues, "
        "but the permitted same-report records contain no operating-income evidence.",
    ),
    "UNP/2016/page_52.pdf": (
        "same_report_operating_income_absent",
        "Total freight revenues plus Other revenues supports Total operating revenues, "
        "but the permitted same-report records contain no operating-income evidence.",
    ),
}


def selection_policy() -> dict[str, Any]:
    return {
        "schema_version": "qa_source_distinct_support_selection_policy.v1",
        "fixed_before_first_source_census": True,
        "selection_rule_status": "prospectively_fixed_before_source_inspection",
        "page_disposition_status": "known_source_annotations_not_data_blind",
        "archive_path": ARCHIVE_PATH,
        "archive_sha256": ARCHIVE_SHA256,
        "archive_byte_count": ARCHIVE_BYTE_COUNT,
        "archive_record_count": ARCHIVE_RECORD_COUNT,
        "selection_fields": list(SOURCE_FIELDS),
        "excluded_semantic_fields": ["qa", "question", "answer", "program", "exe_ans"],
        "whole_json_container_parsed": True,
        "excluded_fields_accessed_for_selection": False,
        "sort_order": [
            "source_record_id_lexicographic",
            "later_fiscal_period_ascending",
            "nearest_comparable_earlier_fiscal_period",
            "supporting_source_record_id_lexicographic",
        ],
        "first_fully_admitted_binding_selected": True,
        "component_count": 2,
        "table_screen": {
            "input": "casefolded concatenation of table_ori row labels",
            "revenue_pattern": REVENUE_PATTERN,
            "structure_pattern": STRUCTURE_PATTERN,
            "conjunction_required": True,
        },
        "source_requirements": [
            "Two separately disclosed revenue components with an explicit exhaustive "
            "and non-overlapping total/component source structure.",
            "No unresolved third component, other component, or elimination; a disclosed "
            "Other revenues component is allowed when it is the explicit complement.",
            "Consolidated issuer scope, currency, units, duration, and revenue definition match.",
            "Earlier revenue and both periods operating income are disclosed in the same "
            "record or the same issuer/report-year Archive records.",
            "Earlier growth bases must be nonzero if all source roles are instantiated.",
            "Structure and role admission precede arithmetic; no growth-gap answer, sum "
            "coincidence, execution result, or repeated route attempt selects a source.",
        ],
        "same_report_join": "first two components of the exact source record ID",
        "runtime_execution_limit": 2,
        "new_task_limit": 1,
        "provider_credential_gpu_limit": 0,
        "external_source_expansion": False,
        "deprecated_financial_data_lake_read": False,
        "scope_limit": "This is the fixed two-component explicit table-structure adapter "
        "domain, not all possible natural-language relations or financial sources.",
    }


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _report_key(record: dict[str, Any]) -> str:
    return "/".join(record["id"].split("/")[:2])


def _income_hits(record: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for field in ("pre_text", "post_text"):
        for index, value in enumerate(record[field] or []):
            if re.search(INCOME_PATTERN, value, re.IGNORECASE):
                hits.append({"field": field, "index": index, "source_text": value})
    for index, row in enumerate(record["table_ori"] or []):
        if re.search(INCOME_PATTERN, " ".join(str(value) for value in row), re.IGNORECASE):
            hits.append({"field": "table_ori", "index": index, "source_row": row})
    return hits


def _source_reference(
    record: dict[str, Any], archive_record_index: int, field: str, index: int
) -> dict[str, Any]:
    value = record[field][index]
    return {
        "source_record_id": record["id"],
        "source_document_id": record["filename"],
        "json_pointer": f"/{archive_record_index}/{field}/{index}",
        "source_value": value,
        "source_value_sha256": _sha256(value),
    }


def _relation_witness(
    record: dict[str, Any],
    archive_record_index: int,
    same_page_entries: list[tuple[int, dict[str, Any]]],
) -> dict[str, Any]:
    is_jpm = record["id"].startswith("JPM/")
    component_rows, total_row = ((9, 10), 11) if is_jpm else ((7, 8), 9)
    used_row_indices = (0, *component_rows, total_row)
    used_rows = [record["table_ori"][index] for index in used_row_indices]
    alias_members = []
    for member_index, member in same_page_entries:
        member_rows = [member["table_ori"][index] for index in used_row_indices]
        if member_rows != used_rows:
            raise ValueError("source.relation_alias: same-page used source rows differ")
        alias_members.append(
            {
                "source_record_id": member["id"],
                "archive_record_index": member_index,
                "source_fields_sha256": _sha256(member),
                "table_sha256": _sha256(member["table_ori"]),
                "used_rows_sha256": _sha256(member_rows),
                "used_row_source_references": [
                    _source_reference(member, member_index, "table_ori", index)
                    for index in used_row_indices
                ],
            }
        )
    source_refs = [
        _source_reference(record, archive_record_index, "table_ori", index)
        for index in (0, *component_rows, total_row)
    ]
    source_refs.append(_source_reference(record, archive_record_index, "pre_text", 0))
    if is_jpm:
        source_refs.append(_source_reference(record, archive_record_index, "pre_text", 3))
    else:
        source_refs.append(_source_reference(record, archive_record_index, "pre_text", 10))
        for index, line in enumerate(record["post_text"]):
            if any(
                phrase in line
                for phrase in (
                    "consolidated financial statements include the accounts",
                    "all intercompany transactions are eliminated",
                )
            ):
                source_refs.append(
                    _source_reference(record, archive_record_index, "post_text", index)
                )
    return {
        "source_record_id": record["id"],
        "source_document_id": record["filename"],
        "same_page_source_record_ids": [member["source_record_id"] for member in alias_members],
        "same_relation_alias_group": {
            "source_document_id": record["filename"],
            "used_row_indices": list(used_row_indices),
            "used_rows_sha256": _sha256(used_rows),
            "source_record_count": len(alias_members),
            "source_members": alias_members,
            "all_used_source_rows_exactly_equal": True,
            "filename_equality_alone_is_sufficient": False,
            "whole_record_byte_equality_asserted": False,
            "interpretation": "These records repeat the same referenced revenue relation "
            "table rows. Context or other fields may differ; source rows, not entire "
            "record bytes, establish this finite alias group.",
        },
        "source_fields_sha256": _sha256(record),
        "issuer_report_key": _report_key(record),
        "component_rows": list(component_rows),
        "component_labels": [record["table_ori"][i][0] for i in component_rows],
        "total_row": total_row,
        "total_label": record["table_ori"][total_row][0],
        "period_labels_as_disclosed": record["table_ori"][0][1:],
        "source_references": source_refs,
        "relation_interpretation_source": "host_reading_of_disclosed_statement_structure",
        "scope": "consolidated_issuer",
        "exhaustive_nonoverlapping_structure_supported": True,
        "source_relation_is_numerical_coincidence_inference": False,
        "source_relation_interpretation": (
            "Noninterest revenue is the disclosed subtotal above Net interest income; "
            "the two disjoint interest/noninterest categories precede Total net revenue. "
            "The preceding individual fee lines belong inside the noninterest subtotal."
            if is_jpm
            else "Total freight revenues is the disclosed subtotal above Other revenues; "
            "those two categories precede Total operating revenues. The six commodity "
            "rows belong inside freight revenue. Consolidation and intercompany elimination "
            "are explicitly stated in the same snapshot."
        ),
        "numeric_sum_computed_for_admission": False,
        "growth_gap_answer_computed": False,
        "available_role_kinds": [
            "revenue_earlier",
            "revenue_later",
            "revenue_component_a_later",
            "revenue_component_b_later",
            "source_partition_relation",
        ],
        "missing_role_kinds": ["income_earlier", "income_later"],
        "fully_instantiated_task_binding": False,
        "source_authority": "curated_database",
        "provider": "FinQA",
        "schema_version": "qa_source_distinct_support_relation_witness.v1",
    }


def source_policy() -> dict[str, Any]:
    """Return the selection rule separately so the runner can freeze it before replay."""
    return selection_policy()


def _annotation_references(
    record: dict[str, Any], archive_record_index: int
) -> list[dict[str, Any]]:
    """Bind the observed page interpretation to exact table and context excerpts."""
    references = [
        _source_reference(record, archive_record_index, "table_ori", index)
        for index in range(len(record["table_ori"] or []))
    ]
    context_pattern = re.compile(
        r"segment|consolidat|compris|consist|following|revenues?|sales|impairment|liabilit",
        re.IGNORECASE,
    )
    for field in ("pre_text", "post_text"):
        for index, line in enumerate(record[field] or []):
            if index == 0 or context_pattern.search(line):
                references.append(_source_reference(record, archive_record_index, field, index))
    return references


def scan_archive(repo_root: Path) -> dict[str, Any]:
    """Replay the fixed finite census without constructing or executing candidates."""
    payload = (repo_root / ARCHIVE_PATH).read_bytes()
    if len(payload) != ARCHIVE_BYTE_COUNT or hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("source.archive_bytes: frozen Archive identity differs")
    raw_records = json.loads(payload)
    if not isinstance(raw_records, list) or len(raw_records) != ARCHIVE_RECORD_COUNT:
        raise ValueError("source.record_domain: frozen Archive record count differs")
    # The whole JSON container must be parsed. Only these source-field values are
    # subsequently accessed; QA/answer/program values never enter any decision.
    indexed_records = [
        (index, {key: record.get(key) for key in SOURCE_FIELDS})
        for index, record in enumerate(raw_records)
    ]
    del raw_records
    if len({record["id"] for _, record in indexed_records}) != ARCHIVE_RECORD_COUNT:
        raise ValueError("source.record_identity: source IDs are not unique")

    record_catalog = []
    candidate_dispositions = []
    income_checks = []
    page_records: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for archive_index, record in sorted(indexed_records, key=lambda item: item[1]["id"]):
        table = record["table_ori"] or []
        labels = [str(row[0]) for row in table if isinstance(row, list) and row]
        label_text = " | ".join(labels).casefold()
        revenue_hit = bool(re.search(REVENUE_PATTERN, label_text))
        structure_hit = bool(re.search(STRUCTURE_PATTERN, label_text))
        screened = revenue_hit and structure_hit
        identity = {
            "source_record_id": record["id"],
            "source_document_id": record["filename"],
            "archive_record_index": archive_index,
            "source_fields_sha256": _sha256(record),
            "table_sha256": _sha256(table),
        }
        record_catalog.append(
            {
                **identity,
                "table_row_labels": labels,
                "revenue_label_hit": revenue_hit,
                "structure_label_hit": structure_hit,
                "structural_candidate": screened,
                "source_fields": list(SOURCE_FIELDS),
            }
        )
        page_records.setdefault(record["filename"], []).append((archive_index, record))
        if screened:
            if record["filename"] not in PAGE_DISPOSITIONS:
                raise ValueError("source.unexplained_structure: census page has no interpretation")
            reason, explanation = PAGE_DISPOSITIONS[record["filename"]]
            candidate_dispositions.append(
                {
                    **identity,
                    "admitted": False,
                    "reason": reason,
                    "explanation": explanation,
                    "arithmetic_selection_used": False,
                    "annotation_origin": "bounded_manual_source_reading_after_fixed_screen",
                    "annotation_is_blind_preregistered_automatic_selector": False,
                    "source_references": _annotation_references(record, archive_index),
                }
            )
        if _report_key(record) in INCOME_REPORT_KEYS:
            income_checks.append(
                {
                    **identity,
                    "issuer_report_key": _report_key(record),
                    "fields_checked": ["table_ori", "pre_text", "post_text"],
                    "field_element_counts": {
                        field: len(record[field] or [])
                        for field in ("table_ori", "pre_text", "post_text")
                    },
                    "table_row_labels": labels,
                    "income_source_hits": _income_hits(record),
                }
            )

    visited_pages = {row["source_document_id"] for row in candidate_dispositions}
    if visited_pages != set(PAGE_DISPOSITIONS):
        raise ValueError("source.census_replay: fixed candidate page domain differs")
    witnesses = []
    for page in sorted(visited_pages):
        if PAGE_DISPOSITIONS[page][0] != "same_report_operating_income_absent":
            continue
        entries = page_records[page]
        archive_index, record = entries[0]
        witnesses.append(_relation_witness(record, archive_index, entries))
    income_hits = sum(len(row["income_source_hits"]) for row in income_checks)
    if income_hits:
        raise ValueError("source.census_replay: unexpected operating-income source mention")
    disposition_counts = dict(
        sorted(Counter(row["reason"] for row in candidate_dispositions).items())
    )
    return {
        "schema_version": "qa_source_distinct_support_source_census.v1",
        "selection_policy": selection_policy(),
        "status": "source_not_instantiated",
        "scientific_witness": None,
        "archive_verified": True,
        "archive_path": ARCHIVE_PATH,
        "archive_sha256": ARCHIVE_SHA256,
        "archive_byte_count": len(payload),
        "archive_record_count": len(record_catalog),
        "source_authority": {
            "authority": "curated_database",
            "provider": "FinQA",
            "original_filing_retrieved": False,
        },
        "record_catalog": record_catalog,
        "structural_candidate_count": len(candidate_dispositions),
        "unique_candidate_source_page_count": len(visited_pages),
        "candidate_dispositions": candidate_dispositions,
        "disposition_counts": disposition_counts,
        "source_relation_witnesses": witnesses,
        "source_relation_witness_count": len(witnesses),
        "source_relation_record_count": sum(
            witness["same_relation_alias_group"]["source_record_count"] for witness in witnesses
        ),
        "same_report_income_check": {
            "issuer_report_keys": list(INCOME_REPORT_KEYS),
            "source_record_count": len(income_checks),
            "lexical_pattern": INCOME_PATTERN,
            "source_records": income_checks,
            "income_source_hit_count": income_hits,
            "missing_role_kinds": ["income_earlier", "income_later"],
            "interpretation": "Within the admitted same-issuer/report-year source records, "
            "the reviewed source snapshots do not disclose operating-income values. "
            "The lexical scan is a reproducible check accompanying the fixed source "
            "reading, not a universal natural-language absence proof.",
        },
        "source_missing_conditions": [
            "The real two-component consolidated revenue witnesses lack both periods "
            "of operating-income Evidence in the permitted same-report snapshots.",
            "The existing revenue/operating-income tables lack two independently "
            "disclosed exhaustive revenue components or have only segment scope.",
        ],
        "fully_instantiated_binding_count": 0,
        "selected_binding": None,
        "new_task_instances": 0,
        "runtime_executions": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "gpu_use": 0,
        "growth_gap_answers_computed": 0,
        "numeric_sum_comparisons_used_for_selection": 0,
        "source_census_interpretation": "reproduction_of_one_previously_completed_fixed_census",
        "scope_limitations": [
            "Only the existing frozen Archive and the fixed two-component table-label "
            "adapter are examined; no external source or alternative task axis is searched.",
            "Three-or-more-component tables are retained as rejected candidates; they "
            "are not evidence of global source absence.",
            "Source_not_instantiated does not mean revenue partitions are absent and "
            "does not establish nonexistence of distinct valid solution behaviors.",
            "No answer equality, probability, training, or benchmark-frequency inference is made.",
        ],
    }
