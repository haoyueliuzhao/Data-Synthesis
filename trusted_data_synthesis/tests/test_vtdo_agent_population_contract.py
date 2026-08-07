from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    EXCLUSION_IDENTITY_INDEX_VERSION,
    FINANCE_AGENT_POPULATION_VERSION,
    FinanceAgentPopulationReport,
    _read_population_identity_source,
    finance_agent_population_report_id,
)
from trusted_synthesis.hashing import canonical_hash


def _report_values() -> dict[str, object]:
    exclusion_hashes = ("1" * 64, "2" * 64)
    return {
        "experiment_config_hash": "experiment:1",
        "archive_config_sha256": "a" * 64,
        "kg_build_id": "kg:1",
        "candidate_pool_id": "pool:1",
        "sampling_partition": "partition:1",
        "requested_task_count": 1,
        "attempted_task_count": 1,
        "accepted_task_count": 1,
        "accepted_state_count": 3,
        "requestable_state_count": 3,
        "state_count_by_task": {"task:1": 3},
        "task_type_counts": {"comparison": 1},
        "failure_counts": {},
        "source_to_agent_task_ids": {"source-task:1": "task:1"},
        "excluded_population_artifact_sha256s": exclusion_hashes,
        "excluded_population_artifact_set_id": canonical_hash(
            exclusion_hashes,
            prefix="finance_agent_population_exclusion_set:",
        ),
        "exclusion_identity_index_version": EXCLUSION_IDENTITY_INDEX_VERSION,
        "excluded_population_record_count": 4,
        "excluded_public_evidence_version_set_id": canonical_hash(
            tuple(f"evidence:{index}" for index in range(12)),
            prefix="finance_population_excluded_evidence_version_set:",
        ),
        "excluded_public_evidence_version_count": 12,
        "artifact_sha256": "b" * 64,
        "status": "passed",
        "schema_version": FINANCE_AGENT_POPULATION_VERSION,
    }


def _build_report(values: dict[str, object]) -> FinanceAgentPopulationReport:
    provisional = FinanceAgentPopulationReport.model_construct(
        report_id="pending",
        **values,
    )
    return FinanceAgentPopulationReport(
        report_id=finance_agent_population_report_id(provisional),
        **values,
    )


def test_agent_population_freezes_multiple_exclusion_artifacts() -> None:
    report = _build_report(_report_values())

    assert report.excluded_population_artifact_sha256s == ("1" * 64, "2" * 64)
    assert report.excluded_public_evidence_version_count == 12


def test_agent_population_rejects_wrong_exclusion_set_identity() -> None:
    values = _report_values()
    values["excluded_population_artifact_set_id"] = "wrong:set"

    with pytest.raises(ValidationError, match="exclusion-set identity"):
        _build_report(values)


def test_agent_population_rejects_duplicate_exclusion_artifacts() -> None:
    values = _report_values()
    values["excluded_population_artifact_sha256s"] = ("1" * 64, "1" * 64)
    values["excluded_population_artifact_set_id"] = canonical_hash(
        ("1" * 64, "1" * 64),
        prefix="finance_agent_population_exclusion_set:",
    )

    with pytest.raises(ValidationError, match="duplicated"):
        _build_report(values)


def test_exclusion_identity_reader_accepts_legacy_payload_without_schema_validation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy_population.jsonl"
    payload = {
        "legacy_schema_version": "intentionally-unsupported",
        "joint_compilation": {
            "omega": {
                "public_corpus": {
                    "evidence": [
                        {"evidence_version_id": "evidence:v1"},
                        {"evidence_version_id": "evidence:v2"},
                    ]
                }
            }
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    index = _read_population_identity_source(path)

    assert index["record_count"] == 1
    assert index["evidence_version_ids"] == ("evidence:v1", "evidence:v2")


def test_exclusion_identity_reader_fails_closed_without_evidence_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid_population.jsonl"
    path.write_text(
        json.dumps({"joint_compilation": {"omega": {"public_corpus": {"evidence": [{}]}}}}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="evidence_version_id"):
        _read_population_identity_source(path)


def test_agent_population_rejects_missing_exclusion_evidence_set_identity() -> None:
    values = _report_values()
    values["excluded_public_evidence_version_set_id"] = None

    with pytest.raises(ValidationError, match="Evidence identity"):
        _build_report(values)


def test_agent_population_rejects_zero_exclusion_record_count() -> None:
    values = _report_values()
    values["excluded_population_record_count"] = 0

    with pytest.raises(ValidationError, match="record accounting"):
        _build_report(values)
