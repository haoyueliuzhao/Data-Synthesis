from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FINANCE_AGENT_POPULATION_VERSION,
    FinanceAgentPopulationReport,
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
