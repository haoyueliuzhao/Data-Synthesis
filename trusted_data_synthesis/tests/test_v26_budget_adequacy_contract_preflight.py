from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_adequacy_contract_preflight import (  # noqa: E501
    BudgetAdequacyContractPreflightReport,
    BudgetAdequacyProtocolContract,
    BudgetAdequacyRoleProtocolPreflight,
    BudgetedPublicWitnessAudit,
    RunnerCompletionControlAudit,
    RunnerControlRawExecution,
    build_budget_adequacy_contract_preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
ROOT_CAUSE = ARTIFACT_ROOT / "finance_v26_88_budget_adequacy_root_cause_audit_20260820"
TASK_SOURCE = (
    ARTIFACT_ROOT / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
INSTRUMENT_PREFLIGHT = (
    ARTIFACT_ROOT / "finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820"
)
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
FORMAL = (
    ARTIFACT_ROOT / "finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820"
)
RUN_ID = "finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820"


def _build(output: Path) -> BudgetAdequacyContractPreflightReport:
    return build_budget_adequacy_contract_preflight(
        run_id=RUN_ID,
        root_cause_dir=ROOT_CAUSE,
        task_source_dir=TASK_SOURCE,
        instrument_preflight_dir=INSTRUMENT_PREFLIGHT,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, BudgetAdequacyContractPreflightReport]:
    output = tmp_path_factory.mktemp("v26_89_preflight")
    return output, _build(output)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_v26_89_contract_is_prospective_and_non_authorizing(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
) -> None:
    output, report = built
    contract = BudgetAdequacyProtocolContract.model_validate_json(
        (output / "budget_adequacy_contract.json").read_text(encoding="utf-8")
    )
    assert contract.maximum_total_tokens == 120_000
    assert contract.maximum_prompt_utf8_bytes == 60_000
    assert contract.maximum_output_tokens == 4_096
    assert contract.contract_repair_reserve_tokens == 4_096
    assert contract.final_answer_reserve_tokens == 4_096
    assert contract.capability_minimum_budgeted_paths_per_task == 1
    assert contract.reachability_minimum_budgeted_paths_per_task == 3
    assert contract.reachability_paths_share_one_budget_contract
    assert contract.maximum_no_call_rate_numerator == 1
    assert contract.maximum_no_call_rate_denominator == 10
    assert contract.independent_calibration_minimum_job_count == 32
    assert contract.independent_calibration_admission_rule == "one_sided_95_upper_bound_lte_0.10"
    assert (
        contract.threshold_basis == "prospective_operational_design_independent_of_v26_86_outcomes"
    )
    assert not contract.current_outcomes_used_to_select_threshold
    assert contract.resource_terminals_retained_in_role_denominator
    assert contract.resource_terminals_excluded_from_validity_and_state_mapping
    assert not contract.direct_total_token_ceiling_increase_authorized
    assert not contract.prompt_ceiling_relaxation_authorized
    assert not contract.completion_bound_reduction_authorized
    assert not contract.required_reserve_reduction_authorized
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert report.production_contribution == 0


def test_v26_89_runner_control_exercises_complete_chain_without_empirical_rows(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
) -> None:
    output, report = built
    audit = RunnerCompletionControlAudit.model_validate_json(
        (output / "runner_completion_control_audit.json").read_text(encoding="utf-8")
    )
    assert len(audit.controls) == 8
    assert audit.raw_execution_pass_count == 8
    assert audit.replay_pass_count == 8
    assert audit.non_replay_pass_count == 8
    assert audit.completed_score_pass_count == 8
    assert audit.sidecar_pass_count == 8
    assert audit.aggregation_pass_count == 8
    assert audit.control_job_ids_unique
    assert audit.historical_empirical_job_overlap_count == 0
    assert audit.empirical_row_count == 0
    assert report.runner_control_passed
    for control in audit.controls:
        assert control.completed_score.source_kind == "compiler_fixture"
        assert control.completed_score.core_terminal == "valid_trajectory"
        assert control.completed_score.trace_sidecar is not None
        assert not control.completed_score.empirical_denominator_eligible
        assert control.calls_and_public_results_match_compiler_witness
        assert control.final_answer_matches_compiler_witness
        assert control.empirical_row_contribution == 0
        raw_path = output / control.raw_execution.relative_path
        raw = RunnerControlRawExecution.model_validate_json(raw_path.read_text(encoding="utf-8"))
        assert raw.raw_persisted_before_replay_and_scoring
        assert raw.fixture_usage_not_budget_adequacy_evidence
        assert not raw.empirical_denominator_eligible
        assert raw.model_api_calls == 0


def test_v26_89_static_witness_budget_fails_closed_without_ceiling_change(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
) -> None:
    output, report = built
    audit = BudgetedPublicWitnessAudit.model_validate_json(
        (output / "budgeted_public_witness_audit.json").read_text(encoding="utf-8")
    )
    assert audit.observed_fixture_task_count == 8
    assert audit.prompt_ceiling_pass_count == 8
    assert audit.qualified_fixture_task_count == 0
    assert audit.minimum_static_path_upper_bound > 120_000
    assert audit.maximum_static_path_upper_bound >= (audit.minimum_static_path_upper_bound)
    assert not audit.inherited_120k_budget_adequate_for_fixture_tasks
    assert not audit.direct_budget_increase_authorized
    assert not report.inherited_120k_budget_adequacy_established
    for row in audit.rows:
        assert row.maximum_prompt_utf8_bytes <= 60_000
        assert row.maximum_cumulative_path_upper_bound > 120_000
        assert row.headroom_or_deficit < 0
        assert not row.full_witness_budget_qualified
        assert not row.direct_ceiling_increase_authorized
        assert not row.empirical_evidence


def test_v26_89_role_protocols_remain_separate_and_unmaterialized(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
) -> None:
    output, report = built
    preflight = BudgetAdequacyRoleProtocolPreflight.model_validate_json(
        (output / "role_protocol_preflight.json").read_text(encoding="utf-8")
    )
    assert preflight.capability_task_count == 12
    assert preflight.capability_job_count == 96
    assert preflight.reachability_task_count == 12
    assert preflight.reachability_paths_per_task == 3
    assert preflight.reachability_state_count == 36
    assert preflight.reachability_natural_job_count == 144
    assert preflight.reachability_conditioned_job_count == 216
    assert preflight.reachability_job_count == 360
    assert preflight.capability_and_reachability_denominators_separate
    assert preflight.fresh_capability_task_count == 0
    assert preflight.fresh_reachability_task_count == 0
    assert preflight.independent_budget_calibration_job_count == 0
    assert not preflight.independent_no_call_rate_evaluated
    assert not preflight.capability_contract_materialized
    assert not preflight.reachability_contract_materialized
    assert preflight.compiler_fixture_empirical_row_count == 0
    assert not preflight.protocol_preflight_passed
    assert not report.role_protocol_preflight_passed
    assert report.next_permitted_stage == "fresh_budget_feasible_role_task_rematerialization_only"


def test_v26_89_destructive_mutations_fail_closed(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
) -> None:
    output, _ = built
    contract_payload = _load(output / "budget_adequacy_contract.json")
    contract_payload["direct_total_token_ceiling_increase_authorized"] = True
    with pytest.raises(ValidationError):
        BudgetAdequacyProtocolContract.model_validate(contract_payload)

    witness_payload = _load(output / "budgeted_public_witness_audit.json")
    witness_payload["rows"][0]["cumulative_path_upper_bounds"][-1] += 1
    with pytest.raises(ValidationError):
        BudgetedPublicWitnessAudit.model_validate(witness_payload)

    raw_relative = witness_payload["rows"][0]["runner_control_id"]
    controls = RunnerCompletionControlAudit.model_validate_json(
        (output / "runner_completion_control_audit.json").read_text(encoding="utf-8")
    )
    control = next(item for item in controls.controls if item.control_id == raw_relative)
    raw_payload = _load(output / control.raw_execution.relative_path)
    raw_payload["exchanges"][0]["prompt"] += " changed"
    with pytest.raises(ValidationError):
        RunnerControlRawExecution.model_validate(raw_payload)


def test_v26_89_dual_build_is_byte_identical(
    built: tuple[Path, BudgetAdequacyContractPreflightReport],
    tmp_path: Path,
) -> None:
    output, report = built
    duplicate = tmp_path / "duplicate"
    duplicate_report = _build(duplicate)
    assert duplicate_report.report_id == report.report_id
    first_files = tuple(
        sorted(path.relative_to(output) for path in output.rglob("*") if path.is_file())
    )
    second_files = tuple(
        sorted(path.relative_to(duplicate) for path in duplicate.rglob("*") if path.is_file())
    )
    assert first_files == second_files
    for relative in first_files:
        assert (output / relative).read_bytes() == (duplicate / relative).read_bytes()


def test_formal_v26_89_result() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.89 preflight has not been built yet")
    report = BudgetAdequacyContractPreflightReport.model_validate_json(
        (FORMAL / "report.json").read_text(encoding="utf-8")
    )
    assert report.runner_control_passed
    assert not report.inherited_120k_budget_adequacy_established
    assert not report.role_protocol_preflight_passed
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert report.model_api_calls == 0
    assert report.gpu_jobs == 0
    assert report.production_contribution == 0
