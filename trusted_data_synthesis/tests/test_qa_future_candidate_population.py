from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.qa_realization_vnext.future_candidate_population import (
    AUTHORIZED_TASK_TYPE,
    BLOCKED_TASK_TYPES,
    FORBIDDEN_VTDO_IDENTITY_TOKENS,
    BlockedProposalRecord,
    FutureQAPreOutcomeCandidateManifest,
    FutureQAPreOutcomeCandidateRow,
    FutureQAQualificationReport,
    LocalAssessmentCatalog,
    QAVTDOIsolationReceipt,
    build_future_qa_candidate_population,
    write_future_qa_candidate_artifacts,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORMAL = (
    _REPO_ROOT / "trusted_data_synthesis/artifacts/qa_realization_vnext/"
    "future_qa_candidate_population_v2_20260901"
)
_ISOLATION_FILENAME = "qa_vtdo_isolation_receipt.json"


@pytest.fixture(scope="module")
def products():
    return build_future_qa_candidate_population(repo_root=_REPO_ROOT)


def test_preoutcome_manifest_is_offline_authorized_and_has_no_outcome_fields(products) -> None:
    manifest = products.candidate_manifest
    serialized_rows = b"\n".join(
        row.model_dump_json().encode("utf-8") for row in manifest.candidate_rows
    )

    assert manifest.population_role == "future_QA_candidate_population"
    assert manifest.candidate_count == 16
    assert manifest.semantic_task_count == 4
    assert manifest.semantic_instance_count == 4
    assert manifest.blocked_proposal_count == 2
    assert all(manifest.hard_gates.values())
    assert manifest.provider_call_count == manifest.gpu_job_count == 0
    assert manifest.development_job_count == 0
    assert manifest.qa_release_population_manifest_count == 0
    assert {row.task_type for row in manifest.candidate_rows} == {AUTHORIZED_TASK_TYPE}
    assert b"quality_assessment_id" not in serialized_rows
    assert b"execution_binding_id" not in serialized_rows
    assert b"selected_for_future_population" not in serialized_rows
    assert all(
        row.resource_estimate_status == "engineering_estimate_only"
        and row.runner_projection_status == "not_yet_runner_projected"
        and row.online_resource_authority == "not_online_resource_authority"
        for row in manifest.candidate_rows
    )
    source = inspect.getsource(build_future_qa_candidate_population)
    assert source.index("candidate_manifest = FutureQAPreOutcomeCandidateManifest") < source.index(
        "generator = FinanceNumericCandidateGenerator"
    )
    assert manifest.hard_gates["authoritative_registered_pair_registry_bound"]
    assert manifest.hard_gates["unregistered_pair_negative_control_rejects"]
    assert all(
        row.evidence_bundle_hash
        and row.evidence_corpus_hash
        and row.proof_graph_hash
        and row.source_record_ids
        and row.operation_semantic_contract_hashes
        and row.finance_semantic_policy_id == "finance_semantics.v2"
        for row in manifest.candidate_rows
    )


def test_assessment_and_diversity_selection_are_downstream_and_nonempirical(products) -> None:
    catalog = products.local_assessment_catalog
    report = products.qualification_report

    assert catalog.candidate_manifest_id == products.candidate_manifest.manifest_id
    assert len(catalog.records) == catalog.accepted_count == 16
    assert catalog.rejected_count == 0
    assert not catalog.empirical
    assert report.candidate_manifest_id == products.candidate_manifest.manifest_id
    assert report.local_assessment_catalog_id == catalog.catalog_id
    assert report.qualified_count == 16
    assert report.selected_count == 8
    assert not report.empirical
    assert all(report.hard_gates.values())
    assert set(report.selected_candidate_ids).issubset(report.qualified_candidate_ids)
    assert set(products.release_selection.semantic_instance_child_counts.values()) == {2}
    assert {row.exact_fraction for row in products.release_selection.weight_assignments} == {"1/2"}


def test_blocked_proposal_ids_never_materialize_or_enter_candidate_rows(products) -> None:
    blocked_ids = {row.proposal_id for row in products.blocked_records}
    blocked_types = {row.task_type for row in products.blocked_records}
    package_bytes = b"\n".join(
        row.model_dump_json().encode("utf-8") for row in products.realized_packages
    )
    candidate_bytes = b"\n".join(
        row.model_dump_json().encode("utf-8") for row in products.candidate_manifest.candidate_rows
    )
    manifest_bytes = products.candidate_manifest.model_dump_json().encode("utf-8")

    assert blocked_types == set(BLOCKED_TASK_TYPES)
    assert all(row.realized_task_package_count == 0 for row in products.blocked_records)
    assert all(row.population_row_count == 0 for row in products.blocked_records)
    assert all(blocked_id.encode("utf-8") not in package_bytes for blocked_id in blocked_ids)
    assert all(blocked_id.encode("utf-8") not in candidate_bytes for blocked_id in blocked_ids)
    # The Manifest retains them only in an explicit exclusion register.
    assert all(blocked_id.encode("utf-8") in manifest_bytes for blocked_id in blocked_ids)


def test_isolation_receipt_binds_frozen_v26_194_without_becoming_candidate_parent(products) -> None:
    receipt = products.isolation_receipt
    candidate_bytes = b"\n".join(
        row.model_dump_json().encode("utf-8") for row in products.candidate_manifest.candidate_rows
    )

    assert receipt.package_count == 32
    assert receipt.job_count == receipt.raw_namespace_count == receipt.result_namespace_count == 192
    assert receipt.registered_prompt_coordinate_count == 792
    assert receipt.vtdo_python_import_count == receipt.vtdo_artifact_write_count == 0
    assert receipt.qa_candidate_parent_count == 0
    assert receipt.manifest_id.startswith("authoritative_kernel_manifest:")
    assert receipt.runner_id.startswith("authoritative_execution_kernel_runner:")
    assert all(token not in candidate_bytes for token in FORBIDDEN_VTDO_IDENTITY_TOKENS)
    assert receipt.receipt_id not in {
        row.semantic_task_id for row in products.candidate_manifest.candidate_rows
    }


def test_artifact_build_is_byte_deterministic_and_isolated(products, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_future_qa_candidate_artifacts(products, left)
    write_future_qa_candidate_artifacts(
        build_future_qa_candidate_population(repo_root=_REPO_ROOT), right
    )

    assert [path.name for path in sorted(left.iterdir())] == [
        path.name for path in sorted(right.iterdir())
    ]
    assert all(
        path.read_bytes() == (right / path.name).read_bytes() for path in sorted(left.iterdir())
    )
    non_receipt_bytes = b"\n".join(
        path.read_bytes() for path in sorted(left.iterdir()) if path.name != _ISOLATION_FILENAME
    )
    assert all(token not in non_receipt_bytes for token in FORBIDDEN_VTDO_IDENTITY_TOKENS)


def test_formal_artifacts_revalidate_exact_bytes() -> None:
    manifest = FutureQAPreOutcomeCandidateManifest.model_validate_json(
        (_FORMAL / "future_QA_candidate_population.json").read_bytes()
    )
    rows = tuple(
        FutureQAPreOutcomeCandidateRow.model_validate_json(line)
        for line in (_FORMAL / "preoutcome_candidate_rows.jsonl").read_bytes().splitlines()
        if line
    )
    blocked = tuple(
        BlockedProposalRecord.model_validate_json(line)
        for line in (_FORMAL / "blocked_proposals.jsonl").read_bytes().splitlines()
        if line
    )
    catalog = LocalAssessmentCatalog.model_validate_json(
        (_FORMAL / "local_assessment_catalog.json").read_bytes()
    )
    qualification = FutureQAQualificationReport.model_validate_json(
        (_FORMAL / "qualification_report.json").read_bytes()
    )
    receipt = QAVTDOIsolationReceipt.model_validate_json(
        (_FORMAL / _ISOLATION_FILENAME).read_bytes()
    )
    artifact_manifest = json.loads((_FORMAL / "artifact_manifest.json").read_bytes())

    assert manifest.candidate_rows == rows
    assert manifest.blocked_records == blocked
    assert catalog.candidate_manifest_id == manifest.manifest_id
    assert qualification.local_assessment_catalog_id == catalog.catalog_id
    assert manifest.isolation_receipt_id == receipt.receipt_id
    assert all(
        hashlib.sha256((_FORMAL / row["filename"]).read_bytes()).hexdigest() == row["sha256"]
        and (_FORMAL / row["filename"]).stat().st_size == row["byte_count"]
        for row in artifact_manifest["files"]
    )
    non_receipt_bytes = b"\n".join(
        path.read_bytes() for path in sorted(_FORMAL.iterdir()) if path.name != _ISOLATION_FILENAME
    )
    assert all(token not in non_receipt_bytes for token in FORBIDDEN_VTDO_IDENTITY_TOKENS)


def test_core_boundary_mutations_fail_closed(products) -> None:
    row = products.candidate_manifest.candidate_rows[0]
    attacked = row.model_dump(mode="json")
    attacked["resource_estimate_status"] = "online_resource_authority"
    attacked["candidate_id"] = strict_canonical_hash(
        {key: value for key, value in attacked.items() if key != "candidate_id"},
        prefix="future_qa_preoutcome_candidate:",
    )
    with pytest.raises(ValueError):
        FutureQAPreOutcomeCandidateRow.model_validate(attacked)

    blocked = products.blocked_records[0].model_dump(mode="json")
    blocked["realized_task_package_count"] = 1
    blocked["blocked_record_id"] = strict_canonical_hash(
        {key: value for key, value in blocked.items() if key != "blocked_record_id"},
        prefix="future_qa_blocked_proposal:",
    )
    with pytest.raises(ValueError, match="cannot be materialized"):
        BlockedProposalRecord.model_validate(blocked)

    catalog = products.local_assessment_catalog.model_dump(mode="json")
    catalog["empirical"] = True
    catalog["catalog_id"] = strict_canonical_hash(
        {key: value for key, value in catalog.items() if key != "catalog_id"},
        prefix="future_qa_local_assessment_catalog:",
    )
    with pytest.raises(ValueError):
        LocalAssessmentCatalog.model_validate(catalog)

    report = products.qualification_report.model_dump(mode="json")
    report["empirical"] = True
    report["report_id"] = strict_canonical_hash(
        {key: value for key, value in report.items() if key != "report_id"},
        prefix="future_qa_qualification_report:",
    )
    with pytest.raises(ValueError):
        FutureQAQualificationReport.model_validate(report)

    receipt = products.isolation_receipt.model_dump(mode="json")
    receipt["manifest_id"] = "authoritative_kernel_manifest:" + "0" * 64
    receipt["receipt_id"] = strict_canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_id"},
        prefix="qa_vtdo_isolation_receipt:",
    )
    with pytest.raises(ValueError):
        QAVTDOIsolationReceipt.model_validate(receipt)

    manifest = products.candidate_manifest.model_dump(mode="json")
    manifest["semantic_task_count"] += 1
    manifest["manifest_id"] = strict_canonical_hash(
        {key: value for key, value in manifest.items() if key != "manifest_id"},
        prefix="future_qa_preoutcome_candidate_manifest:",
    )
    with pytest.raises(ValueError, match="semantic-task count mismatch"):
        FutureQAPreOutcomeCandidateManifest.model_validate(manifest)
