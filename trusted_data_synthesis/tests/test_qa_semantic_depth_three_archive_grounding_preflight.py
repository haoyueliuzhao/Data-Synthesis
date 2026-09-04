from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_semantic_depth_three_archive_grounding import models
from trusted_synthesis.experiments.qa_semantic_depth_three_archive_grounding.archive import (
    ArchiveAdmissionError,
    select_records,
    validate_archive_bytes,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_archive_grounding.preflight import (
    admit_aggregate,
    aggregate_case_rows,
    build_qa_semantic_depth_three_archive_grounding_preflight,
    write_qa_semantic_depth_three_archive_grounding_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/b0ed619d-ec8d-409a-b2cb-7182783af19f/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def products() -> models.Products:
    return build_qa_semantic_depth_three_archive_grounding_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=_git("rev-parse", "HEAD"),
        source_tree=_git("rev-parse", "HEAD^{tree}"),
    )


def test_external_decision_and_predecessor_are_exact(products: models.Products) -> None:
    review = REVIEW.read_bytes()
    assert len(review) == models.EXTERNAL_REVIEW_BYTE_COUNT
    assert hashlib.sha256(review).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    assert products.external_review_bytes == review
    assert products.operator_directive_bytes == models.OPERATOR_DIRECTIVE.encode()
    freeze = products.predecessor_freeze
    assert (freeze["file_count"], freeze["total_bytes"]) == (17, 48_465)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        16,
        45_866,
    )
    assert freeze["manifest_id"] == models.PREDECESSOR_MANIFEST_ID
    assert freeze["artifact_root"] == models.PREDECESSOR_ROOT_ID
    assert freeze["formal_bytes_modified"] is False


def test_source_archive_and_catalog_authority_are_exact(products: models.Products) -> None:
    source = products.source_binding
    assert source["resolved_commit"] == _git("rev-parse", "HEAD")
    assert source["resolved_tree"] == _git("rev-parse", "HEAD^{tree}")
    assert source["member_count"] == len(models.SOURCE_PATHS) == 4
    assert all(row["committed_current_bytes_equal"] for row in source["members"])
    archive = products.archive_binding
    assert archive["sha256"] == models.ARCHIVE_SHA256
    assert archive["byte_count"] == models.ARCHIVE_BYTE_COUNT
    assert archive["record_count"] == models.ARCHIVE_RECORD_COUNT
    assert archive["selected_record_ids"] == models.SOURCE_RECORD_IDS
    assert archive["raw_financial_data_lake_used"] is False
    assert archive["distribution_inference_performed"] is False
    catalog = products.catalog_freeze
    assert catalog["catalog_id"] == models.CATALOG_ID
    assert (catalog["historical_task_count"], catalog["extension_task_count"]) == (8, 2)
    assert (catalog["total_task_count"], catalog["extension_operation_count"]) == (10, 3)
    assert catalog["catalog_modified"] is False


def test_parameter_grid_is_complete_and_aggregated_from_rows(
    products: models.Products,
) -> None:
    rows = products.case_rows
    assert len(rows) == 12
    assert len({row["case_id"] for row in rows}) == 12
    aggregate = aggregate_case_rows(rows)
    audit = products.parameter_space_audit
    for key, value in aggregate.items():
        if key == "schema_version":
            continue
        assert audit[key] == value
    assert aggregate["task_candidate_counts"] == {
        "derived_growth_absolute_spread": 9,
        "registered_margin_target_gap": 3,
    }
    assert aggregate["task_constructible_counts"] == {
        "derived_growth_absolute_spread": 9,
        "registered_margin_target_gap": 0,
    }
    assert aggregate["task_distinct_binding_counts"] == {
        "derived_growth_absolute_spread": 9,
        "registered_margin_target_gap": 0,
    }
    assert aggregate["fixed_case_count_constants_used"] is False


def test_nine_archive_branch_bindings_execute_and_verify(products: models.Products) -> None:
    rows = [row for row in products.case_rows if row["constructible"]]
    assert len(rows) == 9
    assert {row["subject_id"] for row in rows} == {"finqa:CDW", "finqa:HII"}
    assert {row["numeric_relationship"] for row in rows} == {
        "both_negative",
        "both_positive",
        "mixed_sign",
    }
    assert sum(bool(row["adjacent_periods"]) for row in rows) == 5
    assert sum(bool(row["near_equal_growth"]) for row in rows) == 2
    assert all(
        row["archive_role_complete"]
        and row["program_execution_complete"]
        and row["independent_node_replay_passed"]
        and row["answer_schema_correct"]
        and row["answer_correct"]
        and row["citation_correct"]
        and row["evaluator_accepted"]
        and row["semantic_operation_depth"] == 3
        and row["node_count"] == 8
        for row in rows
    )
    assert len(products.bundles) == len(products.packages) == len(products.executions) == 9
    assert len(products.verification_reports) == len(products.assessments) == 9


def test_serial_type_is_blocked_without_fabricated_target(products: models.Products) -> None:
    rows = [row for row in products.case_rows if row["task_type"] == "registered_margin_target_gap"]
    assert len(rows) == 3
    assert {row["period"] for row in rows} == {"FY2015", "FY2016", "FY2017"}
    assert all(not row["archive_role_complete"] and not row["constructible"] for row in rows)
    assert all(
        row["typed_blocker"] == "authoritative_gross_margin_target_evidence_absent" for row in rows
    )
    assert all(row["available_role_evidence_ids"]["target"] == () for row in rows)
    assert products.parameter_space_audit["no_target_labelled_table_rows_in_complete_archive"]


def test_aggregate_rejects_fixed_or_omitted_rows(products: models.Products) -> None:
    aggregate = aggregate_case_rows(products.case_rows)
    changed = dict(aggregate)
    changed["constructible_count"] = 12
    with pytest.raises(ValueError, match="aggregate differs"):
        admit_aggregate(changed, products.case_rows)
    admitted_only = tuple(row for row in products.case_rows if row["constructible"])
    with pytest.raises(ValueError, match="differs"):
        admit_aggregate(aggregate, admitted_only)


def test_nine_negative_controls_reject(products: models.Products) -> None:
    audit = products.negative_audit
    assert tuple(row["name"] for row in audit["controls"]) == models.NEGATIVE_CONTROL_NAMES
    assert (audit["attempted_count"], audit["rejected_count"], audit["accepted_count"]) == (
        9,
        9,
        0,
    )
    assert all(row["rejected"] for row in audit["controls"])
    assert all(row["output_writes"] == row["provider_calls"] == 0 for row in audit["controls"])


def test_gate_fails_only_at_both_type_constructibility(products: models.Products) -> None:
    gate = products.gate
    assert (gate["passed_count"], gate["failed_count"]) == (7, 1)
    assert gate["failed_gate_ids"] == (
        "G4_both_registered_depth_three_types_have_multiple_archive_bindings",
    )
    assert products.decision["decision"] == models.DECISION
    assert products.decision["archive_grounding_established_for_branch_task"] is True
    assert products.decision["archive_grounding_established_for_serial_task"] is False
    assert products.decision["qa_release_eligible"] is False
    assert products.transition["prospective_next_stage"] == models.PROSPECTIVE_NEXT_STAGE
    assert products.transition["next_stage_authorized"] is False


def test_scope_is_zero_external_execution(products: models.Products) -> None:
    scope = products.scope_audit
    assert scope["archive_records_read"] == 1_147
    assert scope["archive_records_selected"] == 2
    assert scope["archive_evidence_bundles_materialized"] == 9
    assert not any(
        scope[key]
        for key in (
            "raw_financial_data_lake_reads",
            "provider_calls",
            "credential_lookups",
            "gpu_jobs",
            "online_generation_jobs",
            "benchmark_distribution_rows",
            "empirical_frequency_estimates",
            "new_task_type_registrations",
            "new_operation_registrations",
            "catalog_promotions",
            "qa_release_objects",
            "vtdo_rows",
            "training_rows",
            "production_rows",
        )
    )


def test_artifacts_are_reproducible_and_self_excluding(
    products: models.Products, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_semantic_depth_three_archive_grounding_artifacts(products, left)
    write_qa_semantic_depth_three_archive_grounding_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1
    for row in manifest["members"]:
        payload = files[row["relative_path"]]
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()


def test_archive_byte_and_selector_changes_reject() -> None:
    payload = (ROOT / models.ARCHIVE_PATH).read_bytes()
    with pytest.raises(ArchiveAdmissionError, match="Archive bytes differ"):
        validate_archive_bytes(payload + b"\n")
    records = json.loads(payload)
    next(row for row in records if row.get("id") == models.SOURCE_RECORD_IDS[0])["id"] = "crossed"
    with pytest.raises(ArchiveAdmissionError, match="not unique"):
        select_records(records)
