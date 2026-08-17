from __future__ import annotations

import json

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (
    ExposureCleanPopulationReceipt,
    SourceGroundingPoolAudit,
    exposure_clean_population_receipt_id,
    source_grounding_pool_audit_id,
)
from trusted_synthesis.hashing import canonical_hash


def _receipt_values(tmp_path) -> dict[str, object]:
    excluded = ("evidence:1", "evidence:2")
    return {
        "run_id": "finance_v26_exposure_clean_test",
        "historical_pool_exposure_audit_id": "audit:1",
        "historical_pool_exposure_audit_path": str(tmp_path / "audit.json"),
        "historical_pool_exposure_audit_sha256": "a" * 64,
        "source_grounding_pool_audit_id": "grounding-audit:1",
        "source_grounding_pool_audit_path": str(tmp_path / "grounding.json"),
        "source_grounding_pool_audit_sha256": "d" * 64,
        "historical_record_manifest_id": "manifest:1",
        "source_artifacts_path": str(tmp_path / "source.jsonl"),
        "source_artifacts_sha256": "b" * 64,
        "archive_config_path": str(tmp_path / "archive.json"),
        "archive_config_sha256": "e" * 64,
        "source_grounding_verifier_id": "finance_source_grounding.v1",
        "source_grounding_verifier_version": "1.2.0",
        "source_evidence_count": 3,
        "historical_exposed_evidence_count": 1,
        "historical_exposed_evidence_set_hash": "historical-set:1",
        "grounding_failed_evidence_count": 1,
        "grounding_failed_evidence_set_hash": "grounding-set:1",
        "effective_excluded_evidence_count": 2,
        "eligible_evidence_count": 1,
        "excluded_evidence_ids": excluded,
        "excluded_evidence_set_hash": canonical_hash(
            excluded,
            prefix="finance_v26_exposure_clean_exclusion_set:",
        ),
        "output_population_id": "population:1",
        "output_population_path": str(tmp_path / "population.json"),
        "output_population_sha256": "c" * 64,
        "output_population_content_hash": "population-content:1",
        "output_task_count": 70,
        "selected_excluded_evidence_overlap_count": 0,
        "model_api_calls": 0,
        "status": "passed",
        "schema_version": "finance_v26_exposure_clean_population_receipt.v3",
    }


def test_exposure_clean_receipt_is_content_addressed(tmp_path) -> None:
    values = _receipt_values(tmp_path)
    provisional = ExposureCleanPopulationReceipt.model_construct(receipt_id="pending", **values)
    receipt = ExposureCleanPopulationReceipt(
        receipt_id=exposure_clean_population_receipt_id(provisional),
        **values,
    )

    assert receipt.status == "passed"
    assert len(receipt.excluded_evidence_ids) == 2


def test_source_grounding_pool_audit_is_content_addressed(tmp_path) -> None:
    failed = ("evidence:2",)
    values = {
        "source_artifacts_path": str(tmp_path / "source.jsonl"),
        "source_artifacts_sha256": "a" * 64,
        "archive_config_path": str(tmp_path / "archive.json"),
        "archive_config_sha256": "b" * 64,
        "verifier_id": "finance_source_grounding.v1",
        "verifier_version": "1.2.0",
        "archive_compatibility_hash": "archive-compatible:1",
        "source_evidence_set_hash": "source-set:1",
        "source_evidence_count": 2,
        "raw_object_count": 1,
        "passed_evidence_count": 1,
        "failed_evidence_ids": failed,
        "failed_evidence_set_hash": canonical_hash(
            failed,
            prefix="finance_v26_source_grounding_failed_evidence_set:",
        ),
        "failed_evidence_count": 1,
        "failure_counts": {"source_entailment": 1},
        "failure_source_counts": {"fred_observations": 1},
        "status": "observed",
        "schema_version": "finance_v26_source_grounding_pool_audit.v1",
    }
    provisional = SourceGroundingPoolAudit.model_construct(audit_id="pending", **values)
    audit = SourceGroundingPoolAudit(
        audit_id=source_grounding_pool_audit_id(provisional),
        **values,
    )

    assert audit.failed_evidence_ids == failed
    assert audit.passed_evidence_count == 1


def test_exposure_clean_receipt_rejects_noncanonical_exclusions(tmp_path) -> None:
    values = _receipt_values(tmp_path)
    values["excluded_evidence_ids"] = ("evidence:2", "evidence:1")

    with pytest.raises(ValueError, match="not canonical"):
        ExposureCleanPopulationReceipt(receipt_id="receipt:bad", **values)


def test_exposure_clean_receipt_forbids_extra_fields(tmp_path) -> None:
    values = _receipt_values(tmp_path)
    provisional = ExposureCleanPopulationReceipt.model_construct(receipt_id="pending", **values)
    receipt_id = exposure_clean_population_receipt_id(provisional)
    payload = {"receipt_id": receipt_id, **values, "legacy_bypass": True}

    with pytest.raises(ValueError):
        ExposureCleanPopulationReceipt.model_validate_json(json.dumps(payload))
