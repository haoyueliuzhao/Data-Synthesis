from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_postrun_audit import (  # noqa: E501
    EXPECTED_RECOVERY_REPORT_ID,
    CompletedTraceScoringAudit,
    IndependentRawLineageAudit,
    ResourceBudgetAudit,
    TokenBudgetCrossing,
    VerifierBoundPostrunAuditReport,
    build_verifier_bound_postrun_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
FAILED_RUN = ARTIFACT_ROOT / "finance_v26_78_verifier_bound_instrument_requalification_20260820"
PREFLIGHT = ARTIFACT_ROOT / "finance_v26_79_verifier_bound_recovery_preflight_20260820"
RECOVERY = ARTIFACT_ROOT / "finance_v26_80_verifier_bound_instrument_recovery_20260820"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
FORMAL = ARTIFACT_ROOT / "finance_v26_81_verifier_bound_postrun_audit_20260820"
EXPECTED_REPORT_ID = (
    "finance_v26_verifier_bound_postrun_audit:"
    "eb7316f9b5e9dcd09013bf3662da64b5f8290f02f1a9e966e3a0268f92d87297"
)
OUTPUT_FILES = (
    "completed_trace_scoring_audit.json",
    "raw_lineage_independent_audit.json",
    "report.json",
    "resource_budget_audit.json",
    "source_replay_audit.json",
)


def _build(output: Path) -> None:
    build_verifier_bound_postrun_audit(
        failed_run_dir=FAILED_RUN,
        preflight_dir=PREFLIGHT,
        recovery_dir=RECOVERY,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def audit_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_81_postrun_audit")
    _build(output)
    return output


def test_v26_81_audit_is_zero_api_and_deterministic(
    audit_dir: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in OUTPUT_FILES:
        assert (audit_dir / relative).read_bytes() == (duplicate / relative).read_bytes()
    report = VerifierBoundPostrunAuditReport.model_validate_json(
        (audit_dir / "report.json").read_text(encoding="utf-8")
    )
    assert report.report_id == EXPECTED_REPORT_ID
    assert report.audited_recovery_report_id == EXPECTED_RECOVERY_REPORT_ID
    assert report.model_api_calls == report.gpu_jobs == 0
    assert not report.model_client_constructed
    assert not report.historical_outcomes_reclassified
    assert not report.historical_artifacts_changed
    assert report.verifier_v2_replay_passed
    assert report.completed_trace_scoring_defect_observed
    assert report.raw_lineage_only_passed
    assert not report.strict_resource_budget_passed
    assert not report.instrument_requalification_passed
    assert report.status == "failed"
    assert report.next_permitted_stage == (
        "fresh_budget_closed_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    )
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert report.production_contribution == 0


def test_v26_81_localizes_completed_trace_scoring_defect(audit_dir: Path) -> None:
    audit = CompletedTraceScoringAudit.model_validate_json(
        (audit_dir / "completed_trace_scoring_audit.json").read_text(encoding="utf-8")
    )
    assert audit.raw_execution_replay_count == 32
    assert audit.verifier_v2_replay_pass_count == 32
    assert audit.completed_trajectory_count == 7
    assert audit.captured_model_contract_failure_count == 25
    assert audit.original_scoring_instrument_failure_count == 7
    assert audit.schema_field_mismatch_count == 7
    assert audit.prospective_model_outcome_count == 32
    assert audit.prospective_instrument_failure_count == 0
    assert audit.prospective_runtime_failure_count == 0
    assert audit.prospective_terminal_counts == {
        "model_invalid_trajectory": 26,
        "model_valid_trajectory": 6,
    }
    assert audit.prospective_independently_valid_count == 6
    assert all(row.independent_non_replay_gate_agreement for row in audit.scoring_failure_rows)
    assert all(not row.historical_terminal_reclassified for row in audit.scoring_failure_rows)


def test_v26_81_retains_the_independent_resource_failure(audit_dir: Path) -> None:
    audit = ResourceBudgetAudit.model_validate_json(
        (audit_dir / "resource_budget_audit.json").read_text(encoding="utf-8")
    )
    assert audit.aggregate_estimated_cost_usd == "0.309099968800000032124"
    assert audit.aggregate_cost_passed
    assert audit.provider_usage_complete_count == 32
    assert audit.per_rollout_token_pass_count == 27
    assert audit.per_rollout_token_failure_count == 5
    assert audit.maximum_total_provider_tokens == 132_963
    assert audit.maximum_overshoot_tokens == 12_963
    assert audit.contract_repair_token_reserve == 0
    assert audit.final_answer_token_reserve == 0
    assert audit.post_response_enforcement_count == 5
    assert not audit.pre_call_provider_token_upper_bound_present
    assert not audit.strict_resource_budget_passed
    assert audit.status == "failed"


def test_v26_81_separates_raw_lineage_from_instrument_gates(audit_dir: Path) -> None:
    audit = IndependentRawLineageAudit.model_validate_json(
        (audit_dir / "raw_lineage_independent_audit.json").read_text(encoding="utf-8")
    )
    assert audit.observed_raw_execution_count == 32
    assert audit.raw_execution_recovery_binding_pass_count == 32
    assert audit.zero_generation_replay_job_count == 17
    assert audit.continuation_job_count == 15
    assert audit.exposed_job_model_call_count == 0
    assert audit.original_provider_artifact_count == 146
    assert audit.continuation_provider_artifact_count == 123
    assert audit.original_provider_exact_byte_pass_count == 146
    assert audit.provider_binding_pass_count == 269
    assert audit.provider_telemetry_pre_host_augmentation_pass_count == 269
    assert audit.provider_call_ids_unique
    assert audit.historical_report_lineage_status == "failed"
    assert audit.historical_report_failed_artifact_count == 7
    assert audit.historical_failed_artifacts_are_instrument_gate_failures
    assert audit.lineage_and_instrument_failure_lists_coupled
    assert audit.lineage_only_passed
    assert audit.status == "passed"


def test_token_budget_crossing_rejects_changed_arithmetic(audit_dir: Path) -> None:
    payload = json.loads((audit_dir / "resource_budget_audit.json").read_text(encoding="utf-8"))[
        "crossings"
    ][0]
    payload["overshoot_tokens"] += 1
    with pytest.raises(ValidationError, match="arithmetic is inconsistent"):
        TokenBudgetCrossing.model_validate(payload)


def test_formal_v26_81_matches_the_deterministic_audit(audit_dir: Path) -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.81 post-run audit has not been frozen yet")
    for relative in OUTPUT_FILES:
        assert (FORMAL / relative).read_bytes() == (audit_dir / relative).read_bytes()
