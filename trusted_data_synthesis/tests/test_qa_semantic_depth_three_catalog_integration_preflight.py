from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration import models
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    CatalogAdmissionError,
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.preflight import (
    build_qa_semantic_depth_three_catalog_integration_preflight,
    write_qa_semantic_depth_three_catalog_integration_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/5db18c9e-776e-4690-9aa6-d0511f22bf40/pasted-text.txt"
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
    return build_qa_semantic_depth_three_catalog_integration_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=_git("rev-parse", "HEAD"),
        source_tree=_git("rev-parse", "HEAD^{tree}"),
    )


def test_exact_external_decision_and_predecessor_freeze(products: models.Products) -> None:
    review = REVIEW.read_bytes()
    assert len(review) == 13_342
    assert hashlib.sha256(review).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    assert products.external_review_bytes == review
    assert products.operator_directive_bytes == models.OPERATOR_DIRECTIVE.encode()
    freeze = products.predecessor_freeze
    assert (freeze["file_count"], freeze["total_bytes"]) == (17, 49_551)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        16,
        46_959,
    )
    assert freeze["manifest_id"] == models.PREDECESSOR_MANIFEST_ID
    assert freeze["artifact_root"] == models.PREDECESSOR_ROOT_ID
    assert freeze["formal_bytes_modified"] is False


def test_exact_git_source_authority(products: models.Products) -> None:
    binding = products.source_binding
    assert binding["resolved_commit"] == _git("rev-parse", "HEAD")
    assert binding["resolved_tree"] == _git("rev-parse", "HEAD^{tree}")
    assert binding["member_count"] == len(models.SOURCE_PATHS) == 4
    assert tuple(row["relative_path"] for row in binding["members"]) == models.SOURCE_PATHS
    assert all(row["committed_current_bytes_equal"] for row in binding["members"])


def test_historical_catalog_is_immutable_and_fresh_catalog_is_versioned(
    products: models.Products,
) -> None:
    historical = products.historical_catalog_freeze
    descriptor = products.catalog_descriptor
    assert tuple(sorted(FinanceTaskPlugin.task_family_ids)) == models.HISTORICAL_TASK_TYPES
    assert historical["task_types"] == models.HISTORICAL_TASK_TYPES
    assert historical["task_count"] == 8
    assert historical["historical_objects_modified"] is False
    assert descriptor["parent_historical_snapshot_id"] == historical["snapshot_id"]
    assert (
        descriptor["catalog_version"] == "finance_qa_registered_catalog.v3-depth-three-preflight.1"
    )
    assert descriptor["catalog_promoted"] is False
    assert (
        descriptor["historical_task_count"],
        descriptor["extension_task_count"],
        descriptor["total_task_count"],
    ) == (8, 2, 10)


def test_two_tasks_and_three_operations_are_registered_exactly_once(
    products: models.Products,
) -> None:
    descriptor = products.catalog_descriptor
    task_rows = descriptor["task_registrations"]
    operation_rows = descriptor["operation_registrations"]
    assert {
        task_type: sum(row["task_type"] == task_type for row in task_rows)
        for task_type in models.EXTENSION_TASK_TYPES
    } == {task_type: 1 for task_type in models.EXTENSION_TASK_TYPES}
    assert {
        operator_id: sum(row["operator_id"] == operator_id for row in operation_rows)
        for operator_id in models.EXTENSION_OPERATION_IDS
    } == {operator_id: 1 for operator_id in models.EXTENSION_OPERATION_IDS}
    assert all(
        row["program_role"] == "semantic"
        for row in operation_rows
        if row["operator_id"] in models.EXTENSION_OPERATION_IDS
    )


def test_catalog_discovery_precedes_both_complete_execution_chains(
    products: models.Products,
) -> None:
    assert len(products.discovery_receipts) == len(products.integration_rows) == 2
    assert {row["task_type"] for row in products.discovery_receipts} == set(
        models.EXTENSION_TASK_TYPES
    )
    assert all(
        row["catalog_id"] == products.catalog_descriptor["catalog_id"]
        for row in products.discovery_receipts
    )
    assert all(
        row["catalog_lookup_passed"]
        and row["pattern_selection_passed"]
        and row["evidence_binding_passed"]
        and row["program_compilation_passed"]
        and row["protected_realization_passed"]
        and row["program_execution_complete"]
        and row["independent_node_replay_passed"]
        and row["answer_schema_correct"]
        and row["answer_correct"]
        and row["citation_correct"]
        and row["evaluator_accepted"]
        for row in products.integration_rows
    )
    assert {row["semantic_operation_depth"] for row in products.integration_rows} == {3}


def test_direct_catalog_bypass_rejects() -> None:
    descriptor = build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    catalog = RegisteredFinanceQACatalog(descriptor)
    bundle, roles = catalog.control_input("derived_growth_absolute_spread")
    _, package = catalog.compile_control("derived_growth_absolute_spread", bundle, roles)
    with pytest.raises(CatalogAdmissionError, match="Catalog resolution"):
        catalog.admit_package("derived_growth_absolute_spread", None, package)


def test_eight_catalog_authority_controls_reject(products: models.Products) -> None:
    audit = products.negative_audit
    assert tuple(row["name"] for row in audit["controls"]) == models.NEGATIVE_CONTROL_NAMES
    assert (audit["attempted_count"], audit["rejected_count"], audit["accepted_count"]) == (
        8,
        8,
        0,
    )
    assert all(row["rejected"] for row in audit["controls"])
    assert all(row["output_writes"] == row["provider_calls"] == 0 for row in audit["controls"])


def test_gate_scope_decision_and_transition_are_narrow(products: models.Products) -> None:
    assert products.gate["passed_count"] == 8
    assert products.gate["failed_count"] == 0
    assert all(products.gate["gates"].values())
    scope = products.scope_audit
    assert not any(
        scope[key]
        for key in (
            "provider_calls",
            "credential_lookups",
            "gpu_jobs",
            "archive_selections",
            "benchmark_rows",
            "empirical_estimates",
            "online_job_manifests",
            "catalog_promotions",
            "qa_release_objects",
            "vtdo_rows",
            "training_rows",
            "production_rows",
            "mainline_recovery_authorizations_read",
            "mainline_recovery_authorizations_consumed",
        )
    )
    assert products.decision["decision"] == models.DECISION
    assert products.decision["overall_qa_sufficiency_established"] is False
    assert products.transition["next_stage"] == models.NEXT_STAGE
    assert products.transition["next_stage_authorized"] is True
    assert products.transition["catalog_promotion_authorized"] is False


def test_artifacts_are_reproducible_and_self_excluding(
    products: models.Products, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_semantic_depth_three_catalog_integration_artifacts(products, left)
    write_qa_semantic_depth_three_catalog_integration_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1
    for row in manifest["members"]:
        payload = files[row["relative_path"]]
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()


def test_changed_external_review_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="external registered-Catalog audit bytes differ"):
        build_qa_semantic_depth_three_catalog_integration_preflight(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
