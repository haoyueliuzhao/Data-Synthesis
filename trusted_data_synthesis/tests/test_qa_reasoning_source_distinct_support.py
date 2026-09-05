from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.qa_reasoning_candidate_family import runtime as old_runtime
from trusted_synthesis.experiments.qa_reasoning_finite_comparison import preflight as old_builder
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    FixedFixtureRuntimeError,
)
from trusted_synthesis.experiments.qa_reasoning_source_distinct_support import (
    models,
    preflight,
    source,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "82e5505dbb16a83cf704399f405602614c0a0d25"
TREE = "ea0b53e5b3b4dc81c053aef401f62052163fe81d"
REVIEW = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_source_distinct_support/"
    "finance_qa_vnext_source_distinct_support_route_constructibility_"
    "and_finite_separation_preflight_v1_20260905/external_review.txt"
)


def build(directory: Path) -> dict[str, Any]:
    return preflight.build_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=COMMIT,
        source_tree=TREE,
        output_directory=directory,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_support_source") / "formal")


def test_exact_new_external_review_and_old_freeze(products: dict[str, Any]) -> None:
    assert products["authorization"]["maximum_new_tasks"] == 1
    assert products["authorization"]["maximum_new_candidate_runtime_executions"] == 2
    freeze = products["freeze"]
    assert (freeze["file_count"], freeze["total_bytes"]) == (27, 8384212)
    assert freeze["historical_classes_by_task"] == {"F1": 1, "F2": 1}
    assert not freeze["historical_next_stage_authorized"]
    with pytest.raises(models.SupportSourceError):
        preflight.authorization(REVIEW.read_bytes() + b"\n")


def test_source_census_has_exact_fixed_scope_and_no_answer_selection(
    products: dict[str, Any],
) -> None:
    census = products["census"]
    assert census["archive_record_count"] == len(census["record_catalog"]) == 1147
    assert census["structural_candidate_count"] == len(census["candidate_dispositions"]) == 59
    assert census["unique_candidate_source_page_count"] == 19
    assert census["numeric_sum_comparisons_used_for_selection"] == 0
    assert census["growth_gap_answers_computed"] == 0
    assert census["selection_policy"]["component_count"] == 2
    assert (
        census["selection_policy"]["page_disposition_status"]
        == "known_source_annotations_not_data_blind"
    )
    assert sum(census["disposition_counts"].values()) == 59


def test_real_revenue_relations_exist_without_a_complete_new_task(products: dict[str, Any]) -> None:
    census = products["census"]
    assert census["source_relation_witness_count"] == 4
    assert census["source_relation_record_count"] == 12
    assert census["fully_instantiated_binding_count"] == 0 and census["selected_binding"] is None
    assert census["scientific_witness"] is None
    assert all(
        w["exhaustive_nonoverlapping_structure_supported"]
        for w in census["source_relation_witnesses"]
    )
    assert {r["reason"] for r in census["candidate_dispositions"]} == {
        "requires_more_than_two_disclosed_components",
        "complete_revenue_partition_absent",
        "no_complete_two_component_revenue_partition_and_segment_scope",
        "same_report_operating_income_absent",
        "segment_scope_and_operating_income_absent",
        "total_is_not_revenue",
    }


def test_same_report_income_gap_is_record_bound_and_recomputed(products: dict[str, Any]) -> None:
    audit = products["census"]["same_report_income_check"]
    assert audit["source_record_count"] == 27
    assert audit["income_source_hit_count"] == 0
    assert Counter(r["issuer_report_key"] for r in audit["source_records"]) == {
        "C/2009": 9,
        "JPM/2014": 4,
        "JPM/2015": 6,
        "UNP/2015": 4,
        "UNP/2016": 4,
    }
    original = json.loads((ROOT / source.ARCHIVE_PATH).read_bytes())
    by_id = {r["id"]: r for r in original}
    for row in audit["source_records"]:
        record = by_id[row["source_record_id"]]
        text = " ".join(
            record["pre_text"]
            + record["post_text"]
            + [" ".join(str(v) for v in r) for r in record["table_ori"]]
        )
        assert re.search(audit["lexical_pattern"], text, re.IGNORECASE) is None


def test_all_source_references_match_actual_json_without_source_hash_helper(
    products: dict[str, Any],
) -> None:
    records = json.loads((ROOT / source.ARCHIVE_PATH).read_bytes())
    references = []
    for row in products["census"]["candidate_dispositions"]:
        references.extend(row["source_references"])
    for witness in products["census"]["source_relation_witnesses"]:
        references.extend(witness["source_references"])
        for member in witness["same_relation_alias_group"]["source_members"]:
            references.extend(member["used_row_source_references"])
    assert len(references) == 1159
    for reference in references:
        parts = reference["json_pointer"].split("/")[1:]
        assert parts[1] in source.SOURCE_FIELDS
        value: Any = records
        for part in parts:
            value = value[int(part)] if isinstance(value, list) else value[part]
        assert value == reference["source_value"]
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        assert hashlib.sha256(payload).hexdigest() == reference["source_value_sha256"]


def test_same_page_copies_are_bound_by_used_rows_not_new_supports(products: dict[str, Any]) -> None:
    for witness in products["census"]["source_relation_witnesses"]:
        alias = witness["same_relation_alias_group"]
        assert alias["all_used_source_rows_exactly_equal"]
        assert not alias["filename_equality_alone_is_sufficient"]
        assert not alias["whole_record_byte_equality_asserted"]
        assert len({m["used_rows_sha256"] for m in alias["source_members"]}) == 1
        assert alias["source_record_count"] in {2, 4}


def test_qa_gold_fields_are_not_accessed_by_source_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    original_loads = source.json.loads

    class GuardedRecord(dict):
        def get(self, key: str, default: Any = None) -> Any:
            assert key in source.SOURCE_FIELDS, "QA gold field accessed as source authority"
            return super().get(key, default)

    def guarded_loads(payload: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_loads(payload, *args, **kwargs)
        return [GuardedRecord(row) for row in result]

    monkeypatch.setattr(source.json, "loads", guarded_loads)
    assert source.scan_archive(ROOT)["structural_candidate_count"] == 59


def test_policy_is_written_before_source_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = preflight.scan_archive
    directory = tmp_path / "formal"
    calls = []

    def guarded(root: Path) -> Any:
        receipt = json.loads((directory / "policy_freeze_receipt.json").read_bytes())
        assert receipt["source_replay_started"] is False
        assert receipt["known_source_annotations"] is True
        assert any(
            e["kind"] == "directory_fsync" and e["relative_path"] == "source_policy.json"
            for e in receipt["write_events"]
        )
        calls.append(True)
        return original(root)

    monkeypatch.setattr(preflight, "scan_archive", guarded)
    assert build(directory)["decision"]["scientific_witness"] is None
    assert calls == [True]


def test_no_old_runtime_builder_primitive_executor_or_oracle_is_called(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("source-only phase executed a candidate or verifier")

    monkeypatch.setattr(old_runtime, "run_candidate", forbidden)
    monkeypatch.setattr(old_builder, "build_comparison", forbidden)
    registry = catalog_operation_registry()
    for row in registry.manifest():
        definition = registry.require(str(row["operator_id"]))
        monkeypatch.setattr(type(definition.executor), "execute", forbidden)
        monkeypatch.setattr(type(definition.oracle_verifier), "verify", forbidden)
    result = build(tmp_path / "no_runtime")
    assert (
        result["scope"]["primitive_executor_calls"]
        == result["scope"]["primitive_oracle_calls"]
        == 0
    )
    assert result["decision"]["candidate_runtime_executions"] == 0


def test_registry_inspection_is_not_a_concrete_compatibility_admission(
    products: dict[str, Any],
) -> None:
    audit = products["registry"]
    assert audit["registered_semantics"]["aggregate"]["semantic_version"] == "1.1.0"
    assert audit["aggregate_default_method_from_actual_ast"] == "mean"
    assert audit["prospective_reconstruction_must_explicitly_request_sum"]
    assert audit["actual_task_specific_compatibility_admission"] is None
    assert audit["new_task_or_composition_contract_materialized"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("scientific_witness", 0),
        ("scientific_witness", 1),
        ("formal_semantic_class_count", 1),
        ("candidate_runtime_executions", 1),
        ("two_route_constructibility_passed", True),
    ],
)
def test_uninstantiated_schema_rejects_fabricated_progress(field: str, value: Any) -> None:
    base = {
        "supported_revenue_partition_pages": 4,
        "missing_required_roles": ("income_earlier", "income_later"),
        "scope_qualified_missing_fact": "income role binding missing in the fixed source domain",
    }
    with pytest.raises(ValidationError):
        models.UninstantiatedDecision.model_validate({**base, field: value})


def test_gates_do_not_misreport_missing_source_as_two_route_success(
    products: dict[str, Any],
) -> None:
    gate = products["gate"]
    assert gate["passed"] == 3 and gate["not_instantiated"] == gate["not_run"] == 1
    assert not gate["complete_two_route_preflight_passed"]
    assert products["decision"]["scientific_witness"] is None
    assert products["decision"]["formal_semantic_class_count"] is None
    assert products["null_controls"]["rejected"] == 5
    assert not products["transition"]["next_stage_authorized"]


def test_complete_empty_directory_rebuild_and_immutable_parent(
    products: dict[str, Any], tmp_path: Path
) -> None:
    previous = files_at(ROOT / models.PREDECESSOR)
    second = build(tmp_path / "second")
    assert files_at(second["writer"].root) == files_at(products["writer"].root)
    assert files_at(ROOT / models.PREDECESSOR) == previous
    manifest = second["manifest"]
    validate_manifest(
        files_at(second["writer"].root), manifest["manifest_id"], manifest["artifact_root"]
    )
    with pytest.raises(FixedFixtureRuntimeError):
        build(tmp_path / "second")
