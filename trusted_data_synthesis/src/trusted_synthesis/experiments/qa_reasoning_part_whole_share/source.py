"""Bind one already witnessed FinQA page without searching the Archive.

The column rule was written before this task's target header/cell inspection.
Page annotations are explicitly known-source host interpretations.  Parsing the
frozen JSON container is necessary, but only the four saved indices are projected
to the source-field whitelist; no QA/program/answer value is accessed.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .models import record

ARCHIVE_PATH = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
ARCHIVE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
ARCHIVE_BYTE_COUNT = 14_395_143
ARCHIVE_RECORD_COUNT = 1_147
SOURCE_FIELDS = ("id", "filename", "table_ori", "pre_text", "post_text")
TARGET_RECORD_ID = "UNP/2015/page_56.pdf-1"
TARGET_DOCUMENT_ID = "UNP/2015/page_56.pdf"
TARGET_ARCHIVE_INDEX = 30
TARGET_MEMBERS = (
    (30, "UNP/2015/page_56.pdf-1"),
    (981, "UNP/2015/page_56.pdf-2"),
    (1065, "UNP/2015/page_56.pdf-3"),
    (1099, "UNP/2015/page_56.pdf-4"),
)
WITNESS_PATH = (
    "trusted_data_synthesis/artifacts/qa_reasoning_source_distinct_support/"
    "finance_qa_vnext_source_distinct_support_route_constructibility_and_finite_"
    "separation_preflight_v1_20260905/source_relation_witnesses.jsonl"
)
WITNESS_FILE_SHA256 = "f62e894779a381a4646c1c94d73271761930471aee6899041a0784bfca2157ce"
WITNESS_LINE_INDEX = 2
WITNESS_LINE_SHA256 = "44b27b6136e05f6eeb28387c9ab5afe976276c025f3bf685badb3d39e4115143"
ROW_LABELS = {
    "freight": (7, "Total freight revenues", "total_freight_revenues"),
    "other": (8, "Other revenues", "other_revenues"),
    "total": (9, "Total operating revenues", "total_operating_revenues"),
}
COMMODITY_LABELS = [
    "Agricultural Products",
    "Automotive",
    "Chemicals",
    "Coal",
    "Industrial Products",
    "Intermodal",
]


def selection_policy() -> dict[str, Any]:
    """Fixed before reading this task's target headers or numeric source cells."""
    return {
        "schema_version": "qa_part_whole_share_source_selection.v1",
        "selection_mode": "known_source_targeted_mechanism_design_not_data_blind",
        "target_record_id": TARGET_RECORD_ID,
        "target_document_id": TARGET_DOCUMENT_ID,
        "target_source_page_group_limit": 1,
        "archive_path": ARCHIVE_PATH,
        "archive_sha256": ARCHIVE_SHA256,
        "archive_byte_count": ARCHIVE_BYTE_COUNT,
        "archive_record_count": ARCHIVE_RECORD_COUNT,
        "source_fields": list(SOURCE_FIELDS),
        "excluded_semantic_fields": ["qa", "question", "answer", "program", "exe_ans"],
        "whole_json_container_parsed": True,
        "archive_semantic_rescan": False,
        "raw_record_access": "only indices in the saved target relation alias group",
        "column_rule_fixed_before_target_header_and_value_inspection": True,
        "column_rule": (
            "Choose the latest interpretable annual fiscal-year column whose three "
            "separately disclosed F/O/T cells are complete finite decimals and have "
            "an explicit shared unit and consolidated issuer scope; sort year "
            "descending, then column index ascending."
        ),
        "component_labels": ["Total freight revenues", "Other revenues"],
        "total_label": "Total operating revenues",
        "period_from_actual_header_not_report_directory": True,
        "numeric_sum_or_answer_used_for_selection": False,
        "source_relation_from_structure_and_context_not_numeric_equality": True,
        "fallback_to_other_page_or_question": False,
        "provider_calls": 0,
        "credential_reads": 0,
        "gpu_calls": 0,
        "runtime_executions": 0,
    }


class SourceBindingError(ValueError):
    """The one allowed source failed a concrete source-binding precondition."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SourceBindingError(code)


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _reference_value(source: dict[str, Any], index: int, pointer: str) -> Any:
    parts = pointer.split("/")
    _require(len(parts) in (4, 5), "source.pointer_shape")
    _require(parts[0] == "" and parts[1] == str(index), "source.pointer_record")
    _require(parts[2] in ("table_ori", "pre_text", "post_text"), "source.pointer_field")
    _require(parts[3].isdigit(), "source.pointer_row")
    try:
        value = source[parts[2]][int(parts[3])]
        if len(parts) == 5:
            _require(parts[2] == "table_ori" and parts[4].isdigit(), "source.pointer_cell")
            value = value[int(parts[4])]
    except (IndexError, TypeError, KeyError) as error:
        raise SourceBindingError("source.pointer_out_of_bounds") from error
    return value


def _verify_reference(reference: dict[str, Any], source: dict[str, Any], index: int) -> None:
    _require(reference["source_record_id"] == source["id"], "source.reference_record_id")
    _require(reference["source_document_id"] == source["filename"], "source.reference_document_id")
    actual = _reference_value(source, index, reference["json_pointer"])
    _require(actual == reference["source_value"], "source.reference_value")
    _require(_sha256(actual) == reference["source_value_sha256"], "source.reference_hash")


def _reference(
    source: dict[str, Any], index: int, field: str, row: int, column: int | None = None
) -> dict[str, Any]:
    pointer = f"/{index}/{field}/{row}"
    if column is not None:
        pointer += f"/{column}"
    value = _reference_value(source, index, pointer)
    return {
        "archive_path": ARCHIVE_PATH,
        "archive_sha256": ARCHIVE_SHA256,
        "source_record_id": source["id"],
        "source_document_id": source["filename"],
        "json_pointer": pointer,
        "source_value": value,
        "source_value_sha256": _sha256(value),
    }


def _decimal_cell(value: Any) -> str:
    _require(isinstance(value, str), "source.cell_not_text")
    text = value.strip()
    _require(
        bool(re.fullmatch(r"\$?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text)),
        "source.cell_not_decimal",
    )
    try:
        parsed = Decimal(text.replace("$", "").replace(",", ""))
    except InvalidOperation as error:
        raise SourceBindingError("source.cell_invalid_decimal") from error
    _require(parsed.is_finite(), "source.cell_nonfinite")
    return format(parsed, "f")


def _target_witness(repo_root: Path) -> dict[str, Any]:
    payload = (repo_root / WITNESS_PATH).read_bytes()
    _require(
        hashlib.sha256(payload).hexdigest() == WITNESS_FILE_SHA256,
        "source.saved_witness_file_identity",
    )
    # Only this previously saved target line is parsed semantically.
    selected_line = payload.splitlines()[WITNESS_LINE_INDEX]
    _require(
        hashlib.sha256(selected_line).hexdigest() == WITNESS_LINE_SHA256,
        "source.saved_witness_line_identity",
    )
    witness = json.loads(selected_line)
    _require(witness["source_record_id"] == TARGET_RECORD_ID, "source.saved_witness_record")
    _require(witness["source_document_id"] == TARGET_DOCUMENT_ID, "source.saved_witness_document")
    _require(
        witness["component_rows"] == [7, 8] and witness["total_row"] == 9,
        "source.saved_witness_roles",
    )
    _require(
        witness["source_authority"] == "curated_database" and witness["provider"] == "FinQA",
        "source.authority",
    )
    _require(
        witness["exhaustive_nonoverlapping_structure_supported"] is True,
        "source.saved_relation_unresolved",
    )
    return witness


def load_source(repo_root: Path) -> dict[str, Any]:
    """Return canonical JSON source binding; perform no sum, ratio, or Runtime call."""
    repo_root = Path(repo_root)
    policy = selection_policy()
    witness = _target_witness(repo_root)
    members = witness["same_relation_alias_group"]["source_members"]
    _require(
        [(m["archive_record_index"], m["source_record_id"]) for m in members]
        == list(TARGET_MEMBERS),
        "source.alias_domain",
    )
    payload = (repo_root / ARCHIVE_PATH).read_bytes()
    _require(len(payload) == ARCHIVE_BYTE_COUNT, "source.archive_byte_count")
    _require(hashlib.sha256(payload).hexdigest() == ARCHIVE_SHA256, "source.archive_sha256")
    container = json.loads(payload)
    _require(
        isinstance(container, list) and len(container) == ARCHIVE_RECORD_COUNT,
        "source.archive_container",
    )
    # No loop over records, IDs, or source fields outside these four fixed indices.
    raw_sources = {
        index: {field: container[index].get(field) for field in SOURCE_FIELDS}
        for index, _ in TARGET_MEMBERS
    }
    del container, payload
    target = raw_sources[TARGET_ARCHIVE_INDEX]
    used_indices = [0, 7, 8, 9]
    target_rows = [target["table_ori"][index] for index in used_indices]
    aliases = []
    for member in members:
        index = member["archive_record_index"]
        source = raw_sources[index]
        _require(source["id"] == member["source_record_id"], "source.raw_record_id")
        _require(source["filename"] == TARGET_DOCUMENT_ID, "source.raw_document_id")
        _require(_sha256(source) == member["source_fields_sha256"], "source.raw_fields_hash")
        _require(_sha256(source["table_ori"]) == member["table_sha256"], "source.raw_table_hash")
        rows = [source["table_ori"][row] for row in used_indices]
        _require(
            rows == target_rows and _sha256(rows) == member["used_rows_sha256"],
            "source.alias_used_rows",
        )
        for reference in member["used_row_source_references"]:
            _verify_reference(reference, source, index)
        aliases.append(
            {
                "source_record_id": source["id"],
                "archive_record_index": index,
                "source_fields_sha256": _sha256(source),
                "table_sha256": _sha256(source["table_ori"]),
                "used_rows_sha256": _sha256(rows),
                "used_row_indices": used_indices,
                "used_row_source_references": [
                    _reference(source, index, "table_ori", row) for row in used_indices
                ],
            }
        )
    _require(_sha256(target) == witness["source_fields_sha256"], "source.target_fields_hash")
    for reference in witness["source_references"]:
        _verify_reference(reference, target, TARGET_ARCHIVE_INDEX)

    table = target["table_ori"]
    _require(len(table) == 10, "source.target_table_structure")
    _require(
        [row[0] for row in table[1:7]] == COMMODITY_LABELS, "source.freight_internal_commodity_rows"
    )
    for row, label, _ in ROW_LABELS.values():
        _require(table[row][0] == label, "source.target_metric_label")
    _require(table[0][0] == "Millions", "source.explicit_unit_header")
    _require(
        "union pacific corporation and its subsidiaries" in target["pre_text"][0],
        "source.issuer_scope_context",
    )
    _require(
        "the following table provides freight revenue by commodity group" in target["pre_text"][10],
        "source.commodity_structure_context",
    )
    _require(
        "consolidated financial statements include the accounts of union pacific "
        "corporation and all of its subsidiaries" in target["post_text"][7],
        "source.consolidation_context",
    )
    _require(
        "all intercompany transactions are eliminated" in target["post_text"][9],
        "source.intercompany_elimination_context",
    )

    inspected_columns = []
    complete_columns: list[tuple[int, int, dict[str, str]]] = []
    for column, header in enumerate(table[0][1:], start=1):
        interpreted = isinstance(header, str) and bool(
            re.fullmatch(r"(?:19|20)\d{2}", header.strip())
        )
        parsed = {}
        reason = None
        if interpreted:
            try:
                parsed = {
                    role: _decimal_cell(table[row][column])
                    for role, (row, _, _) in ROW_LABELS.items()
                }
                _require(
                    table[7][column].strip().startswith("$")
                    and table[9][column].strip().startswith("$"),
                    "source.currency_symbols",
                )
            except (SourceBindingError, IndexError) as error:
                reason = str(error)
        else:
            reason = "source.header_not_interpretable_annual_year"
        complete = interpreted and reason is None
        inspected_columns.append(
            {
                "index": column,
                "label": header,
                "interpretable_annual_year": interpreted,
                "complete": complete,
                "incomplete_reason": reason,
            }
        )
        if complete:
            complete_columns.append((int(header), column, parsed))
    _require(bool(complete_columns), "source.no_complete_interpretable_column")
    complete_columns.sort(key=lambda item: (-item[0], item[1]))
    year, column, values = complete_columns[0]
    period = str(year)
    _require(
        bool(re.search(rf"\b{year}\b", target["post_text"][2])), "source.year_context_corroboration"
    )

    common = {
        "period": period,
        "unit": "millions",
        "currency": "dollar_as_disclosed",
        "subject": "Union Pacific Corporation and subsidiaries",
        "scope": "consolidated_issuer",
    }
    context_locations = [
        ("pre_text", 0),
        ("pre_text", 10),
        ("post_text", 2),
        ("post_text", 7),
        ("post_text", 9),
    ]
    context_refs = [
        _reference(target, TARGET_ARCHIVE_INDEX, field, row) for field, row in context_locations
    ]
    all_refs = [
        _reference(target, TARGET_ARCHIVE_INDEX, "table_ori", row) for row in range(len(table))
    ] + context_refs
    selected_cells = {}
    evidence = {}
    for role, (row, label, metric) in ROW_LABELS.items():
        cell_reference = _reference(target, TARGET_ARCHIVE_INDEX, "table_ori", row, column)
        selected_cells[role] = {
            "row_index": row,
            "column_index": column,
            "label": label,
            "raw_value": table[row][column],
            "value": values[role],
            "source_reference": cell_reference,
        }
        evidence[role] = record(
            "numeric_evidence",
            kind="numeric",
            value=values[role],
            metric=metric,
            definition=label,
            **common,
            source_authority="curated_database",
            provider="FinQA",
            source_record_id=TARGET_RECORD_ID,
            source_document_id=TARGET_DOCUMENT_ID,
            source_references=[
                cell_reference,
                _reference(target, TARGET_ARCHIVE_INDEX, "table_ori", row, 0),
                _reference(target, TARGET_ARCHIVE_INDEX, "table_ori", 0),
                *context_refs,
            ],
        )
    interpretation = (
        "The six commodity rows 1..6 precede and are included in the disclosed "
        "Total freight revenues subtotal at row 7. That subtotal and Other "
        "revenues at row 8 are the two top-level revenue categories immediately "
        "preceding Total operating revenues at row 9. The complete ten-row table "
        "has no additional top-level member or elimination row. Same-page text "
        "identifies consolidated Union Pacific Corporation and its subsidiaries "
        "and states that intercompany transactions are eliminated. This is a "
        "bounded host interpretation of disclosed structure/context, not a "
        "literal equation cell or an inference from numerical equality."
    )
    evidence["part_whole"] = record(
        "relation_evidence",
        kind="part_whole",
        member_ids=[evidence["freight"]["id"], evidence["other"]["id"]],
        total_id=evidence["total"]["id"],
        member_metrics=[ROW_LABELS["freight"][2], ROW_LABELS["other"][2]],
        total_metric=ROW_LABELS["total"][2],
        exhaustive=True,
        nonoverlapping=True,
        **common,
        source_authority="curated_database",
        provider="FinQA",
        source_record_id=TARGET_RECORD_ID,
        source_document_id=TARGET_DOCUMENT_ID,
        source_references=all_refs,
        interpretation=interpretation,
        interpretation_status="known_source_host_annotation_not_data_blind",
        numeric_value_cell_exists=False,
        numeric_sum_computed_for_admission=False,
    )
    return record(
        "source_binding",
        status="source_bound",
        **common,
        evidence=evidence,
        source_record_id=TARGET_RECORD_ID,
        source_document_id=TARGET_DOCUMENT_ID,
        archive_record_index=TARGET_ARCHIVE_INDEX,
        source_authority="curated_database",
        provider="FinQA",
        archive={
            "path": ARCHIVE_PATH,
            "sha256": ARCHIVE_SHA256,
            "byte_count": ARCHIVE_BYTE_COUNT,
            "container_record_count": ARCHIVE_RECORD_COUNT,
        },
        selection_policy=policy,
        selection_policy_sha256=_sha256(policy),
        selected_column={
            "index": column,
            "label": period,
            "period_kind": "annual_year_column",
            "report_directory_used_as_period": False,
        },
        inspected_columns=inspected_columns,
        selected_raw_header=table[0],
        selected_raw_cells=selected_cells,
        raw_source_records=[
            {
                "archive_record_index": index,
                "source_fields": raw_sources[index],
                "source_fields_sha256": _sha256(raw_sources[index]),
            }
            for index, _ in TARGET_MEMBERS
        ],
        source_references=all_refs,
        same_page_aliases=aliases,
        same_page_alias_policy={
            "same_used_rows_required": True,
            "filename_equality_sufficient": False,
            "whole_record_byte_equality_asserted": False,
            "independent_source_page_count": 1,
            "record_alias_count": 4,
        },
        historical_witness={
            "path": WITNESS_PATH,
            "file_sha256": WITNESS_FILE_SHA256,
            "line_index_zero_based": WITNESS_LINE_INDEX,
            "line_sha256": WITNESS_LINE_SHA256,
            "value_sha256": _sha256(witness),
            "source_record_id": TARGET_RECORD_ID,
        },
        interpretation_notes={
            "period": (
                "Actual numeric year header in a revenue table under consolidated financial "
                "statements, corroborated by the same-page revenue discussion; no exact "
                "period-end date is invented."
            ),
            "unit": (
                "Millions is explicit in the raw table header; each selected revenue cell "
                "uses this common scale."
            ),
            "currency": (
                "The raw table discloses dollar signs on freight and total. Other revenue "
                "inherits the table convention. No explicit ISO currency code occurs in "
                "the cited snapshot, so none is asserted."
            ),
            "scope": (
                "The source expressly includes Union Pacific Corporation and all "
                "subsidiaries and eliminates intercompany transactions."
            ),
            "relation": interpretation,
        },
        access_log={
            "source_page_groups": 1,
            "raw_archive_indices_accessed": [index for index, _ in TARGET_MEMBERS],
            "raw_source_record_count": 4,
            "allowed_fields": list(SOURCE_FIELDS),
            "whole_container_parsed": True,
            "archive_rescan": False,
            "qa_semantic_access": False,
            "other_source_groups_accessed": False,
            "saved_witness_lines_semantically_parsed": [WITNESS_LINE_INDEX],
        },
        arithmetic={
            "sum_computed": False,
            "share_answer_computed": False,
            "candidate_executions": 0,
        },
    )
