"""Three known-source bindings; no question/answer scan or arithmetic selection.

The source page is the alias unit, the task includes its actual year and metric
roles, and overlapping facts connect source groups for future split exclusion.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.source import (
    ARCHIVE_BYTE_COUNT,
    ARCHIVE_PATH,
    ARCHIVE_RECORD_COUNT,
    ARCHIVE_SHA256,
    SOURCE_FIELDS,
    WITNESS_FILE_SHA256,
    WITNESS_PATH,
    _decimal_cell,
    _reference,
    _verify_reference,
)

ROLES = ("target_component", "other_component", "disclosed_total")
CONTEXT_FIELDS = ("subject", "scope", "period", "unit", "currency")
FAMILY = "parameterized_part_whole_share"
WITNESS_LINES = (
    "01a087831b5e6efccaf33492252bdc1c14e8e74ed9dfc5340afc629d49eb913e",
    "4243d8d8f08b142e83958c9777360cb18da5fe94b762be3310ac8c931692b974",
    "44b27b6136e05f6eeb28387c9ab5afe976276c025f3bf685badb3d39e4115143",
    "3dd43fc63c9bc87911e73b74a773883d3146432c5a15a81a1189b46463205d5d",
)
SPECS = (
    ("unp_2016", 3, "UNP/2016/page_52.pdf-1"),
    ("jpm_2014", 0, "JPM/2014/page_70.pdf-1"),
    ("jpm_2015", 1, "JPM/2015/page_82.pdf-1"),
)


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def record(record_type: str, **values: Any) -> dict[str, Any]:
    require("id" not in values and "schema_version" not in values, "cross_source.identity_fields")
    body = {"schema_version": "finance_qa_vnext_" + record_type + ".v2", **copy.deepcopy(values)}
    return {
        **body,
        "id": strict_canonical_hash(body, prefix="finance_qa_vnext_" + record_type + ":"),
    }


@dataclass(frozen=True)
class BoundShareSource:
    source_key: str
    task_id: str
    source_binding_id: str
    context: dict[str, Any]
    evidence: dict[str, Any]
    binding_record: dict[str, Any]
    task: dict[str, Any]
    semantic_contract: dict[str, Any]


def validate_bound_source(source: BoundShareSource) -> None:
    """Protect identities and parallel constructor inputs from mutable-dict drift."""
    for value in (
        source.binding_record,
        source.task,
        source.semantic_contract,
        *source.evidence.values(),
    ):
        record_type = value["schema_version"].removeprefix("finance_qa_vnext_").removesuffix(".v2")
        fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
        require(value == record(record_type, **fields), "cross_source.bound_identity")
    require(
        source.source_binding_id == source.binding_record["id"]
        and source.task_id == source.task["id"]
        and source.task["source_binding_id"] == source.source_binding_id,
        "cross_source.task_binding_identity",
    )
    require(
        source.evidence == source.binding_record["evidence"]
        and source.context == {key: source.binding_record[key] for key in CONTEXT_FIELDS},
        "cross_source.bound_metadata",
    )
    require(
        source.semantic_contract["task_id"] == source.task_id
        and source.semantic_contract["source_binding_id"] == source.source_binding_id
        and source.semantic_contract["semantic_roles"]
        == {key: value["id"] for key, value in source.evidence.items()},
        "cross_source.semantic_binding_identity",
    )


def selection_policy() -> dict[str, Any]:
    return {
        "selection_mode": "known_source_development_not_data_blind",
        "target_record_ids": [item[2] for item in SPECS],
        "source_fields": list(SOURCE_FIELDS),
        "excluded_semantic_fields": ["qa", "question", "answer", "program", "exe_ans"],
        "column_rule": (
            "Latest interpretable annual year with complete separately disclosed target, "
            "other and total cells, explicit common unit and consolidated issuer scope; "
            "year descending, column index ascending."
        ),
        "period_from_actual_header_not_report_directory": True,
        "numeric_sum_or_answer_used_for_selection": False,
        "relation_inferred_from_numeric_equality": False,
        "archive_semantic_rescan": False,
        "fallback_to_other_page": False,
        "provider_calls": 0,
        "runtime_executions": 0,
    }


def _witnesses(repo_root: Path) -> list[dict[str, Any]]:
    payload = (repo_root / WITNESS_PATH).read_bytes()
    require(
        hashlib.sha256(payload).hexdigest() == WITNESS_FILE_SHA256,
        "cross_source.witness_file_identity",
    )
    lines = payload.splitlines()
    require(len(lines) == 4, "cross_source.witness_count")
    for line, expected in zip(lines, WITNESS_LINES, strict=True):
        require(hashlib.sha256(line).hexdigest() == expected, "cross_source.witness_line_identity")
    return [json.loads(line) for line in lines]


def _context(source: dict[str, Any], witness: dict[str, Any]) -> tuple[dict[str, str], list[Any]]:
    is_unp = source["id"].startswith("UNP/")
    if is_unp:
        require(
            "union pacific corporation and its subsidiaries" in source["pre_text"][0],
            "cross_source.issuer",
        )
        require(
            "freight revenue by commodity group" in source["pre_text"][10],
            "cross_source.subtotal_structure",
        )
        require("all of its subsidiaries" in source["post_text"][6], "cross_source.scope")
        require(
            "all intercompany transactions are eliminated" in source["post_text"][8],
            "cross_source.elimination",
        )
        require(len(source["table_ori"]) == 10, "cross_source.complete_table")
        subject = "Union Pacific Corporation and subsidiaries"
    else:
        require("jpmorgan chase & co." in source["pre_text"][0], "cross_source.issuer")
        require(
            "consolidated results of operations on a reported basis" in source["pre_text"][0],
            "cross_source.scope",
        )
        require(
            source["pre_text"][3] == "revenue year ended december 31 .",
            "cross_source.annual_period",
        )
        require(len(source["table_ori"]) == 12, "cross_source.complete_table")
        subject = "JPMorgan Chase & Co. consolidated issuer"
    require(
        source["table_ori"][0][0] in ("Millions", "(in millions)"), "cross_source.explicit_unit"
    )
    refs = [ref for ref in witness["source_references"] if "/table_ori/" not in ref["json_pointer"]]
    return {
        "subject": subject,
        "scope": "consolidated_issuer",
        "unit": "millions",
        "currency": "dollar_as_disclosed",
    }, refs


def _bind(
    key: str,
    witness: dict[str, Any],
    witness_index: int,
    raw: dict[int, dict[str, Any]],
    prior_witness: dict[str, Any],
) -> BoundShareSource:
    members = witness["same_relation_alias_group"]["source_members"]
    index = members[0]["archive_record_index"]
    source = raw[index]
    require(source["id"] == witness["source_record_id"], "cross_source.target_id")
    used_rows = [0, *witness["component_rows"], witness["total_row"]]
    table = source["table_ori"]
    for member in members:
        original = raw[member["archive_record_index"]]
        require(
            original["id"] == member["source_record_id"]
            and original["filename"] == witness["source_document_id"],
            "cross_source.alias_identity",
        )
        require(
            _hash(original) == member["source_fields_sha256"]
            and _hash(original["table_ori"]) == member["table_sha256"],
            "cross_source.alias_hash",
        )
        rows = [original["table_ori"][row] for row in used_rows]
        require(
            rows == [table[row] for row in used_rows] and _hash(rows) == member["used_rows_sha256"],
            "cross_source.alias_rows",
        )
        for reference in member["used_row_source_references"]:
            _verify_reference(reference, original, member["archive_record_index"])
    for reference in witness["source_references"]:
        _verify_reference(reference, source, index)
    require(
        witness["exhaustive_nonoverlapping_structure_supported"] is True
        and witness["source_relation_is_numerical_coincidence_inference"] is False,
        "cross_source.structural_relation",
    )
    common, context_refs = _context(source, witness)
    labels = [*witness["component_labels"], witness["total_label"]]
    row_indices = [*witness["component_rows"], witness["total_row"]]
    require([table[row][0] for row in row_indices] == labels, "cross_source.metric_labels")
    inspected = []
    eligible = []
    for column, header in enumerate(table[0][1:], 1):
        values: dict[str, str] = {}
        reason = None
        try:
            require(bool(re.fullmatch(r"(?:19|20)\d{2}", header)), "cross_source.annual_header")
            values = {
                role: _decimal_cell(table[row][column])
                for role, row in zip(ROLES, row_indices, strict=True)
            }
            require(table[row_indices[2]][column].startswith("$"), "cross_source.currency")
            require(Decimal(values["disclosed_total"]) != 0, "cross_source.zero_denominator")
        except (ValueError, IndexError, TypeError) as error:
            reason = str(error)
        inspected.append(
            {
                "index": column,
                "label": header,
                "complete": reason is None,
                "incomplete_reason": reason,
            }
        )
        if reason is None:
            eligible.append((int(header), column, values))
    require(bool(eligible), "cross_source.no_eligible_year")
    year, column, values = sorted(eligible, key=lambda item: (-item[0], item[1]))[0]
    common["period"] = str(year)
    require(
        str(year) in (source["post_text"][2] if key.startswith("unp") else source["pre_text"][0]),
        "cross_source.period_corroboration",
    )
    group = record(
        "cross_binding_source_group",
        archive_sha256=ARCHIVE_SHA256,
        source_document_id=source["filename"],
        used_rows_sha256=_hash([table[row] for row in used_rows]),
    )
    context_refs = [
        {"archive_path": ARCHIVE_PATH, "archive_sha256": ARCHIVE_SHA256, **ref}
        for ref in context_refs
    ]
    refs = [_reference(source, index, "table_ori", row) for row in range(len(table))] + context_refs
    evidence = {}
    selected_cells = {}
    for role, row, label in zip(ROLES, row_indices, labels, strict=True):
        reference = _reference(source, index, "table_ori", row, column)
        metric = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        evidence[role] = record(
            "cross_binding_numeric_evidence",
            kind="numeric",
            semantic_role=role,
            value=values[role],
            metric=metric,
            definition=label,
            **common,
            source_authority="curated_database",
            provider="FinQA",
            source_group_id=group["id"],
            source_record_id=source["id"],
            source_document_id=source["filename"],
            source_references=[
                reference,
                _reference(source, index, "table_ori", row, 0),
                _reference(source, index, "table_ori", 0),
                *context_refs,
            ],
        )
        selected_cells[role] = {
            "row_index": row,
            "column_index": column,
            "label": label,
            "raw_value": table[row][column],
            "value": values[role],
            "source_reference": reference,
        }
    relation = witness["source_relation_interpretation"]
    evidence["composition_relation"] = record(
        "cross_binding_relation_evidence",
        kind="part_whole",
        **common,
        semantic_role="composition_relation",
        source_authority="curated_database",
        provider="FinQA",
        source_group_id=group["id"],
        source_record_id=source["id"],
        source_document_id=source["filename"],
        member_ids=[evidence[role]["id"] for role in ROLES[:2]],
        total_id=evidence["disclosed_total"]["id"],
        member_metrics=[evidence[role]["metric"] for role in ROLES[:2]],
        total_metric=evidence["disclosed_total"]["metric"],
        exhaustive=True,
        nonoverlapping=True,
        source_references=refs,
        interpretation=relation,
        interpretation_status="known_source_host_annotation_not_data_blind",
        numeric_value_cell_exists=False,
        numeric_sum_computed_for_admission=False,
    )
    binding = record(
        "cross_binding_source_binding",
        source_key=key,
        status="source_bound",
        **common,
        evidence=evidence,
        source_record_id=source["id"],
        source_document_id=source["filename"],
        source_group=group,
        archive_record_index=index,
        source_references=refs,
        archive={
            "path": ARCHIVE_PATH,
            "sha256": ARCHIVE_SHA256,
            "byte_count": ARCHIVE_BYTE_COUNT,
            "container_record_count": ARCHIVE_RECORD_COUNT,
        },
        selection_policy=selection_policy(),
        selected_column={
            "index": column,
            "label": str(year),
            "period_kind": "annual_year_column",
            "report_directory_used_as_period": False,
        },
        inspected_columns=inspected,
        selected_raw_header=table[0],
        selected_raw_cells=selected_cells,
        raw_source_records=[
            {
                "archive_record_index": member["archive_record_index"],
                "source_fields": raw[member["archive_record_index"]],
            }
            for member in members
        ],
        same_page_aliases=witness["same_relation_alias_group"],
        historical_witness={
            "path": WITNESS_PATH,
            "file_sha256": WITNESS_FILE_SHA256,
            "line_index_zero_based": witness_index,
            "line_sha256": WITNESS_LINES[witness_index],
        },
        prior_development_source_witness=prior_witness,
        interpretation_notes={
            "relation": relation,
            "unit": "Explicit table unit is millions.",
            "currency": "Dollar convention is disclosed; no unsupported ISO code is asserted.",
            "period": "Actual year header; no report-folder period substitution.",
            "scope": "Same-page text explicitly describes consolidated issuer results.",
        },
        access_log={
            "allowed_fields": list(SOURCE_FIELDS),
            "whole_container_parsed": True,
            "raw_archive_indices_accessed": [member["archive_record_index"] for member in members],
            "qa_semantic_access": False,
            "archive_rescan": False,
            "historical_execution_replayed": False,
        },
        arithmetic={
            "sum_computed": False,
            "share_answer_computed": False,
            "candidate_executions": 0,
        },
        denominator_admission={
            "finite": True,
            "nonzero": True,
            "value": values["disclosed_total"],
            "composition_not_inferred_from_this_check": True,
        },
    )
    task = record(
        "cross_binding_task",
        task_type=FAMILY,
        source_binding_id=binding["id"],
        **common,
        question=(
            f"For {common['subject']} in fiscal year {year}, what percentage of "
            f"{labels[2]} was {labels[0]}? Report to six decimal places and cite "
            "the actual calculation support."
        ),
        target_component_metric=evidence["target_component"]["metric"],
        total_metric=evidence["disclosed_total"]["metric"],
        evidence_universe_ids=sorted(item["id"] for item in evidence.values()),
        is_new_task=True,
    )
    contract = record(
        "cross_binding_semantic_contract",
        task_id=task["id"],
        source_binding_id=binding["id"],
        semantic_roles={role: evidence[role]["id"] for role in evidence},
        metrics={role: evidence[role]["metric"] for role in ROLES},
        ratio_metric=evidence["target_component"]["metric"] + "_share_ratio",
        percent_metric=evidence["target_component"]["metric"] + "_share_percent",
        numeric={
            "precision": 50,
            "rounding": "ROUND_HALF_EVEN",
            "final_quantum": "0.000001",
            "source_reconciliation_tolerance": "0",
            "answer_tolerance": "0",
        },
        raw_evidence_metadata_rewriting_permitted=False,
        derived_total_requires_actual_same_task_component_relation_lineage=True,
        final_projection="share_percent_quantized",
    )
    return BoundShareSource(
        key, task["id"], binding["id"], common, evidence, binding, task, contract
    )


def load_sources(repo_root: Path) -> tuple[BoundShareSource, ...]:
    witnesses = _witnesses(Path(repo_root))
    payload = (Path(repo_root) / ARCHIVE_PATH).read_bytes()
    require(
        len(payload) == ARCHIVE_BYTE_COUNT
        and hashlib.sha256(payload).hexdigest() == ARCHIVE_SHA256,
        "cross_source.archive_identity",
    )
    container = json.loads(payload)
    require(
        isinstance(container, list) and len(container) == ARCHIVE_RECORD_COUNT,
        "cross_source.archive_container",
    )
    indices = [
        m["archive_record_index"]
        for _, line, _ in SPECS
        for m in witnesses[line]["same_relation_alias_group"]["source_members"]
    ]
    raw = {
        index: {field: container[index].get(field) for field in SOURCE_FIELDS} for index in indices
    }
    del container, payload
    result = []
    for key, line, target in SPECS:
        require(witnesses[line]["source_record_id"] == target, "cross_source.fixed_target")
        result.append(_bind(key, witnesses[line], line, raw, witnesses[2]))
    return tuple(result)


def contamination_registry(
    sources: tuple[BoundShareSource, ...] | list[BoundShareSource],
) -> dict[str, Any]:
    require(
        len(sources) == 3 and {item.source_key for item in sources} == {item[0] for item in SPECS},
        "cross_source.contamination_domain",
    )
    by_key = {item.source_key: item for item in sources}
    sources = [by_key[item[0]] for item in SPECS]
    groups = []
    facts: list[dict[str, Any]] = []
    prior = sources[0].binding_record["prior_development_source_witness"]
    all_tables: list[tuple[Any, Any, Any, str | None, Any]] = [
        (
            source.binding_record["source_group"],
            source.binding_record["same_page_aliases"],
            source.context["subject"],
            source.task_id,
            source.binding_record["source_references"],
        )
        for source in sources
    ]
    prior_group = record(
        "cross_binding_source_group",
        archive_sha256=ARCHIVE_SHA256,
        source_document_id=prior["source_document_id"],
        used_rows_sha256=prior["same_relation_alias_group"]["used_rows_sha256"],
    )
    all_tables.append(
        (
            prior_group,
            prior["same_relation_alias_group"],
            sources[0].context["subject"],
            None,
            prior["source_references"],
        )
    )
    for group, aliases, subject, task_id, refs in all_tables:
        groups.append(
            {
                **group,
                "record_alias_ids": [m["source_record_id"] for m in aliases["source_members"]],
                "task_id": task_id,
                "split": "development_contaminated",
                "prior_development_task": task_id is None,
            }
        )
        rows = {
            int(ref["json_pointer"].split("/")[-1]): ref
            for ref in refs
            if "/table_ori/" in ref["json_pointer"] and len(ref["json_pointer"].split("/")) == 4
        }
        header = rows[0]["source_value"]
        # Compare all disclosed relation cells, not only each task's selected year.
        for row in aliases["used_row_indices"][1:]:
            for column, year in enumerate(header[1:], 1):
                ref = rows[row]
                facts.append(
                    {
                        "source_group_id": group["id"],
                        "subject": subject,
                        "period": year,
                        "metric": ref["source_value"][0],
                        "value": _decimal_cell(ref["source_value"][column]),
                        "unit": "millions",
                        "currency": "dollar_as_disclosed",
                        "source_reference": {
                            **ref,
                            "json_pointer": ref["json_pointer"] + f"/{column}",
                            "source_value": ref["source_value"][column],
                            "source_value_sha256": _hash(ref["source_value"][column]),
                        },
                    }
                )
    overlaps: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    for i, left in enumerate(facts):
        for right in facts[i + 1 :]:
            keys = ("subject", "period", "metric", "unit", "currency")
            if left["source_group_id"] == right["source_group_id"] or any(
                left[k] != right[k] for k in keys
            ):
                continue
            row = {"left": left, "right": right, "exact_task_duplicate": False}
            (overlaps if left["value"] == right["value"] else differences).append(row)
    return record(
        "cross_binding_contamination_registry",
        source_groups=groups,
        source_group_count=len(groups),
        new_task_count=3,
        same_page_alias_record_count=sum(len(g["record_alias_ids"]) for g in groups),
        exact_repeated_fact_links=overlaps,
        comparative_value_differences=differences,
        difference_cause=(
            "not established by the cited source snapshot; no restatement cause inferred"
        ),
        evaluation_readiness="not_ready",
        clean_evaluation_task_count=0,
        split_policy=(
            "Exclude every development source group, all same-table aliases, and transitively "
            "fact-overlapping source groups from future evaluation; "
            "distinct years are not exact task duplicates."
        ),
        broader_exclusion_policy=(
            "Any source group used for development, prompt adjustment or training must also be "
            "registered and excluded, including all aliases and the transitive fact-overlap "
            "closure. These four page groups do not certify the rest of the project clean."
        ),
        future_evaluation_prompt="one common neutral task prompt for all compared systems",
        future_correctness_authority="original source evidence and independent computation",
        teacher_trajectory_imitation_is_evaluation_correctness=False,
        evaluation_readiness_is_collection_gate=False,
        known_source_selection_not_blind=True,
        source_level_independence_claimed=False,
    )


def source_report(sources: tuple[BoundShareSource, ...] | list[BoundShareSource]) -> dict[str, Any]:
    instance_keys = [
        {
            **source.context,
            "target_metric": source.evidence["target_component"]["metric"],
            "total_metric": source.evidence["disclosed_total"]["metric"],
        }
        for source in sources
    ]
    require(
        len({_hash(key) for key in instance_keys}) == len(sources),
        "cross_source.duplicate_semantic_instance",
    )
    return record(
        "cross_binding_source_report",
        bindings=[source.binding_record for source in sources],
        tasks=[source.task for source in sources],
        semantic_contracts=[source.semantic_contract for source in sources],
        semantic_instance_keys_excluding_page_identity=instance_keys,
        distinct_subject_period_metric_instances=len(instance_keys),
        selected_instance_duplicate_pairs=[],
        contamination_registry=contamination_registry(sources),
    )
