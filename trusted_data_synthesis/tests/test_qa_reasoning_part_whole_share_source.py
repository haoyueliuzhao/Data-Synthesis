"""Targeted source replay only: no candidate factory, Runtime, or financial executor."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_part_whole_share import source

ROOT = Path(__file__).resolve().parents[2]
INDICES = (30, 981, 1065, 1099)
SOURCE_FIELDS = ("id", "filename", "table_ori", "pre_text", "post_text")


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def references_in(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if "json_pointer" in value:
            return [value]
        return [reference for item in value.values() for reference in references_in(item)]
    if isinstance(value, list):
        return [reference for item in value for reference in references_in(item)]
    return []


@pytest.fixture(scope="module")
def binding() -> dict[str, Any]:
    return source.load_source(ROOT)


def test_targeted_physical_source_scope_and_no_arithmetic(binding: dict[str, Any]) -> None:
    assert binding["source_record_id"] == "UNP/2015/page_56.pdf-1"
    assert binding["source_document_id"] == "UNP/2015/page_56.pdf"
    assert binding["archive_record_index"] == 30
    assert binding["archive"] == {
        "path": "trusted_data_synthesis/benchmarks/finqa/frozen/test.json",
        "sha256": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
        "byte_count": 14395143,
        "container_record_count": 1147,
    }
    access = binding["access_log"]
    assert access["source_page_groups"] == 1
    assert access["raw_archive_indices_accessed"] == list(INDICES)
    assert access["raw_source_record_count"] == 4
    assert access["allowed_fields"] == list(SOURCE_FIELDS)
    assert access["saved_witness_lines_semantically_parsed"] == [2]
    assert access["whole_container_parsed"]
    assert not access["archive_rescan"]
    assert not access["qa_semantic_access"]
    assert not access["other_source_groups_accessed"]
    assert binding["arithmetic"] == {
        "sum_computed": False,
        "share_answer_computed": False,
        "candidate_executions": 0,
    }
    assert binding["source_authority"] == "curated_database"
    assert binding["provider"] == "FinQA"
    policy = binding["selection_policy"]
    assert policy["selection_mode"] == "known_source_targeted_mechanism_design_not_data_blind"
    assert policy["column_rule_fixed_before_target_header_and_value_inspection"]
    assert not policy["numeric_sum_or_answer_used_for_selection"]
    assert not policy["fallback_to_other_page_or_question"]
    assert all(
        policy[field] == 0
        for field in ("provider_calls", "credential_reads", "gpu_calls", "runtime_executions")
    )


def test_every_reference_replays_exact_raw_value_and_hash(binding: dict[str, Any]) -> None:
    payload = (ROOT / source.ARCHIVE_PATH).read_bytes()
    assert len(payload) == binding["archive"]["byte_count"]
    assert hashlib.sha256(payload).hexdigest() == binding["archive"]["sha256"]
    container = json.loads(payload)
    # No ID search: only saved target indices and the source whitelist are accessed.
    records = {
        index: {field: container[index][field] for field in SOURCE_FIELDS} for index in INDICES
    }
    del container
    references = references_in(binding)
    assert len(references) == 73
    assert len({r["json_pointer"] for r in references}) == 33
    for reference in references:
        pointer = reference["json_pointer"].split("/")[1:]
        index = int(pointer[0])
        assert index in INDICES and pointer[1] in SOURCE_FIELDS
        record = records[index]
        assert reference["source_record_id"] == record["id"]
        assert reference["source_document_id"] == record["filename"]
        assert reference["archive_sha256"] == binding["archive"]["sha256"]
        value: Any = record
        for part in pointer[1:]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert value == reference["source_value"]
        assert canonical_hash(value) == reference["source_value_sha256"]
    for raw in binding["raw_source_records"]:
        assert raw["source_fields"] == records[raw["archive_record_index"]]
        assert set(raw["source_fields"]) == set(SOURCE_FIELDS)
        assert canonical_hash(raw["source_fields"]) == raw["source_fields_sha256"]
    for obj in [binding, *binding["evidence"].values()]:
        body = {key: value for key, value in obj.items() if key != "id"}
        prefix = obj["schema_version"].removesuffix(".v1") + ":"
        assert obj["id"] == prefix + canonical_hash(body)


def test_adapter_cannot_scan_other_records_or_access_gold_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_loads = source.json.loads
    accesses: list[tuple[int, str]] = []
    index_accesses: list[int] = []

    class GuardedRecord(dict):
        def __init__(self, original: dict[str, Any], index: int) -> None:
            super().__init__(original)
            self.index = index

        def get(self, key: str, default: Any = None) -> Any:
            assert key in SOURCE_FIELDS, "QA/gold/non-source field accessed"
            accesses.append((self.index, key))
            return super().get(key, default)

        def __getitem__(self, key: str) -> Any:
            assert key in SOURCE_FIELDS, "QA/gold/non-source field accessed"
            accesses.append((self.index, key))
            return super().__getitem__(key)

    class GuardedContainer(list):
        def __iter__(self) -> Any:
            raise AssertionError("whole Archive iteration is forbidden")

        def __getitem__(self, index: Any) -> Any:
            assert isinstance(index, int) and index in INDICES, "non-target record access"
            index_accesses.append(index)
            return GuardedRecord(super().__getitem__(index), index)

    def guarded_loads(payload: Any, *args: Any, **kwargs: Any) -> Any:
        parsed = original_loads(payload, *args, **kwargs)
        return GuardedContainer(parsed) if isinstance(parsed, list) else parsed

    monkeypatch.setattr(source.json, "loads", guarded_loads)
    result = source.load_source(ROOT)
    expected = [(index, field) for index in INDICES for field in SOURCE_FIELDS]
    assert accesses == expected
    assert index_accesses == [index for index, _ in expected]
    assert result["access_log"]["raw_archive_indices_accessed"] == list(INDICES)


def test_period_scale_currency_and_scope_are_bound_to_actual_source(
    binding: dict[str, Any],
) -> None:
    header = binding["selected_raw_header"]
    assert header == ["Millions", "2015", "2014", "2013"]
    selected = binding["selected_column"]
    years = [(int(label), column) for column, label in enumerate(header[1:], start=1)]
    year, column = sorted(years, key=lambda item: (-item[0], item[1]))[0]
    assert selected["index"] == column == 1
    assert selected["label"] == str(year) == binding["period"]
    assert not selected["report_directory_used_as_period"]
    assert binding["selection_policy"]["period_from_actual_header_not_report_directory"]
    assert all(item["complete"] for item in binding["inspected_columns"])
    assert binding["unit"] == "millions"
    assert binding["currency"] == "dollar_as_disclosed"
    assert binding["currency"] != "USD"
    cells = binding["selected_raw_cells"]
    assert cells["freight"]["raw_value"] == "$20,397"
    assert cells["other"]["raw_value"] == "1,416"
    assert cells["total"]["raw_value"] == "$21,813"
    primary = binding["raw_source_records"][0]["source_fields"]
    assert "union pacific corporation and its subsidiaries" in primary["pre_text"][0]
    assert "consolidated financial statements include the accounts" in primary["post_text"][7]
    assert "all intercompany transactions are eliminated" in primary["post_text"][9]
    assert binding["subject"] == "Union Pacific Corporation and subsidiaries"
    assert binding["scope"] == "consolidated_issuer"


def test_real_metrics_stay_distinct_and_relation_has_no_numeric_cell(
    binding: dict[str, Any],
) -> None:
    evidence = binding["evidence"]
    expected = {
        "freight": ("20397", "total_freight_revenues", "Total freight revenues", 7),
        "other": ("1416", "other_revenues", "Other revenues", 8),
        "total": ("21813", "total_operating_revenues", "Total operating revenues", 9),
    }
    assert set(evidence) == {*expected, "part_whole"}
    assert len({item["id"] for item in evidence.values()}) == 4
    for role, (value, metric, definition, row) in expected.items():
        item = evidence[role]
        assert (item["kind"], item["value"], item["metric"], item["definition"]) == (
            "numeric",
            value,
            metric,
            definition,
        )
        assert item["source_references"][0]["json_pointer"] == f"/30/table_ori/{row}/1"
        assert all(
            item[field] == binding[field]
            for field in ("period", "unit", "currency", "subject", "scope")
        )
    relation = evidence["part_whole"]
    assert relation["kind"] == "part_whole"
    assert "value" not in relation
    assert relation["member_ids"] == [evidence["freight"]["id"], evidence["other"]["id"]]
    assert relation["total_id"] == evidence["total"]["id"]
    assert relation["exhaustive"] and relation["nonoverlapping"]
    assert not relation["numeric_value_cell_exists"]
    assert not relation["numeric_sum_computed_for_admission"]
    assert relation["interpretation_status"] == "known_source_host_annotation_not_data_blind"
    rows = [r for r in relation["source_references"] if "/table_ori/" in r["json_pointer"]]
    assert len(rows) == 10
    assert [r["source_value"][0] for r in rows[7:]] == [
        "Total freight revenues",
        "Other revenues",
        "Total operating revenues",
    ]


def test_same_page_aliases_preserve_record_differences_and_one_page_count(
    binding: dict[str, Any],
) -> None:
    aliases = binding["same_page_aliases"]
    assert [item["archive_record_index"] for item in aliases] == list(INDICES)
    assert [item["source_record_id"] for item in aliases] == [
        f"UNP/2015/page_56.pdf-{suffix}" for suffix in range(1, 5)
    ]
    assert len({item["used_rows_sha256"] for item in aliases}) == 1
    assert len({item["table_sha256"] for item in aliases}) == 1
    assert len({item["source_fields_sha256"] for item in aliases}) == 4
    assert Counter(tuple(item["used_row_indices"]) for item in aliases) == {(0, 7, 8, 9): 4}
    for item, raw in zip(aliases, binding["raw_source_records"], strict=True):
        rows = [raw["source_fields"]["table_ori"][index] for index in (0, 7, 8, 9)]
        assert canonical_hash(rows) == item["used_rows_sha256"]
        assert rows == [ref["source_value"] for ref in item["used_row_source_references"]]
    assert binding["same_page_alias_policy"] == {
        "same_used_rows_required": True,
        "filename_equality_sufficient": False,
        "whole_record_byte_equality_asserted": False,
        "independent_source_page_count": 1,
        "record_alias_count": 4,
    }


@pytest.mark.parametrize(
    ("relative_path", "expected_error"),
    [
        (source.ARCHIVE_PATH, "source.archive_sha256"),
        (source.WITNESS_PATH, "source.saved_witness_file_identity"),
    ],
)
def test_changed_frozen_bytes_stop_before_any_source_reinterpretation(
    relative_path: str,
    expected_error: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = ROOT / relative_path
    original_read = Path.read_bytes

    def guarded_read(path: Path) -> bytes:
        payload = original_read(path)
        if path == target:
            return payload[:-1] + bytes([payload[-1] ^ 1])
        return payload

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(source.SourceBindingError, match=expected_error):
        source.load_source(ROOT)
