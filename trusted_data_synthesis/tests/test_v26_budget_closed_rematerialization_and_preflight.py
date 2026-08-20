from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    CompletedTrajectoryScore,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    BudgetClosedInstrumentContract,
    BudgetClosedInstrumentJobManifest,
    BudgetClosedInstrumentPreflightReport,
    BudgetClosureMutationAudit,
    CompilerCompletedScoringAudit,
    ScoringFailureChannelMutationAudit,
    build_budget_closed_instrument_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_task_rematerialization import (  # noqa: E501
    BudgetClosedFreshnessAudit,
    BudgetClosedInstrumentPopulationReport,
    build_budget_closed_instrument_population,
)
from trusted_synthesis.runtime.agent.budget_closed import ProviderTokenBudgetContract

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
DEVELOPMENT = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "development.json"
)
SECONDARY = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "confirmation_source.json"
)
TERTIARY_ROOT = ARTIFACT_ROOT / "finance_v26_40_no_api_joint_scaffold_20260817"
TERTIARY = TERTIARY_ROOT / "population" / "confirmation_source.json"
QUATERNARY_ROOT = ARTIFACT_ROOT / "finance_v26_36_no_api_joint_scaffold_20260817"
QUATERNARY = QUATERNARY_ROOT / "population" / "confirmation_source.json"
V26_56 = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"
V26_65 = ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
V26_69 = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
V26_75 = ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
V26_76 = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
SNAPSHOT = (
    ARTIFACT_ROOT
    / "finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816"
    / "finance_stopping_evidence_snapshot.jsonl"
)
EXPOSURE_RECEIPT = (
    ARTIFACT_ROOT
    / "finance_v26_29_exposure_grounded_source_20260817"
    / "exposure_clean_receipt.json"
)
HISTORICAL_JOB_MANIFESTS = (
    ARTIFACT_ROOT
    / "finance_v26_63_operation_closure_requalification_20260818"
    / "job_manifest.json",
    ARTIFACT_ROOT
    / "finance_v26_66_authority_preserving_instrument_requalification_20260819"
    / "job_manifest.json",
    ARTIFACT_ROOT / "finance_v26_71_capability_development_20260819" / "job_manifest.json",
    ARTIFACT_ROOT / "finance_v26_72_state_reachability_20260819" / "job_manifest.json",
    ARTIFACT_ROOT
    / "finance_v26_77_verifier_bound_instrument_preflight_20260819"
    / "job_manifest.json",
    ARTIFACT_ROOT
    / "finance_v26_79_verifier_bound_recovery_preflight_20260820"
    / "recovery_manifest.json",
)
FORMAL_82 = (
    ARTIFACT_ROOT
    / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
FORMAL_83 = (
    ARTIFACT_ROOT
    / "finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820"
)
RUN_ID_82 = "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
RUN_ID_83 = "finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820"
SELECTION_SALT = "finance_v26_82_budget_closed_verifier_bound_instrument_population_v1"
DETAIL_FILES_82 = (
    "authority_preserving_task_audits.json",
    "compiler_trajectories.json",
    "completed_compiler_trajectory_scores.json",
    "contract_lineage_audit.json",
    "definition_pair_capacity_audit.json",
    "mechanism_counterfactual_replays.json",
    "mechanism_necessity_artifacts.json",
    "operation_closure_audits.json",
    "operational_public_witnesses.json",
    "operational_task_admissions.json",
    "operational_task_records.json",
    "operational_witness_observations.json",
    "provider_token_budget_contract.json",
    "reconciliation_selection_audit.json",
    "report.json",
    "source_freshness_audit.json",
    "static_model_authority_path_catalogs.json",
    "tool_environment_manifests.json",
    "verifier_v2_replay_bindings.json",
)
DETAIL_FILES_83 = (
    "budget_closure_mutation_audits.json",
    "compiler_completed_scoring_audits.json",
    "compiler_replay_audits.json",
    "destructive_replay_mutation_audits.json",
    "execution_contract.json",
    "job_manifest.json",
    "public_private_isolation_audits.json",
    "report.json",
    "scoring_failure_channel_mutation_audits.json",
    "source_replay_audit.json",
)


def _build_82(output: Path) -> BudgetClosedInstrumentPopulationReport:
    return build_budget_closed_instrument_population(
        run_id=RUN_ID_82,
        development_population_path=DEVELOPMENT,
        secondary_source_path=SECONDARY,
        tertiary_source_path=TERTIARY,
        tertiary_no_api_report_path=TERTIARY_ROOT / "report.json",
        quaternary_source_path=QUATERNARY,
        quaternary_no_api_report_path=QUATERNARY_ROOT / "report.json",
        v26_56_dir=V26_56,
        v26_65_dir=V26_65,
        v26_69_dir=V26_69,
        v26_76_dir=V26_76,
        verifier_qualification_dir=V26_75,
        snapshot_path=SNAPSHOT,
        exposure_receipt_path=EXPOSURE_RECEIPT,
        selection_salt=SELECTION_SALT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


def _build_83(output: Path) -> BudgetClosedInstrumentPreflightReport:
    return build_budget_closed_instrument_preflight(
        run_id=RUN_ID_83,
        task_source_dir=FORMAL_82,
        verifier_qualification_dir=V26_75,
        historical_job_manifest_paths=HISTORICAL_JOB_MANIFESTS,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt_82(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_82_rebuild")
    _build_82(output)
    return output


@pytest.fixture(scope="module")
def rebuilt_83(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_83_rebuild")
    _build_83(output)
    return output


def _load_list(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def test_v26_82_and_v26_83_independently_reproduce_formal_bytes(
    rebuilt_82: Path,
    rebuilt_83: Path,
) -> None:
    for relative_path in DETAIL_FILES_82:
        assert (rebuilt_82 / relative_path).read_bytes() == (FORMAL_82 / relative_path).read_bytes()
    for relative_path in DETAIL_FILES_83:
        assert (rebuilt_83 / relative_path).read_bytes() == (FORMAL_83 / relative_path).read_bytes()


def test_v26_82_is_fresh_balanced_and_compiler_only(rebuilt_82: Path) -> None:
    report = BudgetClosedInstrumentPopulationReport.model_validate_json(
        (rebuilt_82 / "report.json").read_text(encoding="utf-8")
    )
    freshness = BudgetClosedFreshnessAudit.model_validate_json(
        (rebuilt_82 / "source_freshness_audit.json").read_text(encoding="utf-8")
    )
    scores = _load_list(
        rebuilt_82 / "completed_compiler_trajectory_scores.json",
        CompletedTrajectoryScore,
    )

    assert report.mechanism_task_counts == {
        "context_conditioned_action": 2,
        "failure_recovery": 2,
        "semantic_reconciliation": 2,
        "state_dependent_stopping": 2,
    }
    assert report.compiler_witness_observation_count == 80
    assert report.compiler_empirical_row_count == 0
    assert report.legacy_operation_mutation_count == 64
    assert report.authority_verification_mutation_count == 40
    assert len(freshness.source_population_ids) == 4
    assert len(freshness.channels) == 8
    assert all(item.overlap_count == 0 and not item.overlap_values for item in freshness.channels)
    assert not freshness.historical_model_outcomes_used_for_selection
    assert not freshness.v26_81_diagnostic_candidates_used_for_selection
    assert len(scores) == 8
    assert all(item.source_kind == "compiler_fixture" for item in scores)
    assert all(item.core_terminal == "valid_trajectory" for item in scores)
    assert all(item.trace_sidecar is not None and item.instrument_admitted for item in scores)
    assert all(not item.empirical_denominator_eligible for item in scores)


def test_v26_83_contract_and_manifest_are_budget_closed(rebuilt_83: Path) -> None:
    contract = BudgetClosedInstrumentContract.model_validate_json(
        (rebuilt_83 / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = BudgetClosedInstrumentJobManifest.model_validate_json(
        (rebuilt_83 / "job_manifest.json").read_text(encoding="utf-8")
    )
    budget = contract.provider_token_budget_contract

    assert contract.model_id == "deepseek-v4-flash"
    assert not contract.fallback_models
    assert contract.pre_call_budget_certificate_required
    assert contract.typed_no_call_terminal_required
    assert contract.completed_trace_shared_scoring_required
    assert contract.failure_namespaces_separated
    assert budget.maximum_total_tokens == 120_000
    assert budget.maximum_prompt_utf8_bytes == 60_000
    assert budget.maximum_output_tokens == 4_096
    assert budget.contract_repair_reserve_tokens == 4_096
    assert budget.final_answer_reserve_tokens == 4_096
    assert len(manifest.jobs) == len({item.job_id for item in manifest.jobs}) == 32
    assert Counter(item.mechanism_id for item in manifest.jobs) == {
        "context_conditioned_action": 8,
        "failure_recovery": 8,
        "semantic_reconciliation": 8,
        "state_dependent_stopping": 8,
    }
    assert set(Counter(item.task_package_id for item in manifest.jobs).values()) == {4}


def test_v26_83_budget_scoring_and_compiler_mutations_fail_closed(rebuilt_83: Path) -> None:
    budget = _load_list(
        rebuilt_83 / "budget_closure_mutation_audits.json",
        BudgetClosureMutationAudit,
    )
    scoring = _load_list(
        rebuilt_83 / "scoring_failure_channel_mutation_audits.json",
        ScoringFailureChannelMutationAudit,
    )
    compiler = _load_list(
        rebuilt_83 / "compiler_completed_scoring_audits.json",
        CompilerCompletedScoringAudit,
    )

    assert Counter(item.mutation_kind for item in budget) == {
        "changed_usage": 1,
        "contract_repair_reserve_insufficient": 1,
        "exact_boundary": 1,
        "final_answer_reserve_insufficient": 1,
        "missing_usage": 1,
        "one_token_over": 1,
        "oversized_prompt": 1,
    }
    exact = next(item for item in budget if item.mutation_kind == "exact_boundary")
    assert exact.observed_behavior == "provider_call_allowed"
    assert exact.provider_call_count == 1
    no_call = tuple(item for item in budget if item.observed_behavior == "typed_no_call")
    assert len(no_call) == 4
    assert all(item.provider_call_count == 0 and item.no_call_reason for item in no_call)
    usage_failures = tuple(
        item for item in budget if item.observed_behavior == "budget_contract_failed"
    )
    assert len(usage_failures) == 2
    assert all(item.provider_call_count == 1 and item.budget_failure_ids for item in usage_failures)
    assert {item.mutation_kind for item in scoring} == {
        "failure_namespace_cross_contamination",
        "legacy_observation_id_access",
        "trajectory_step_schema_change",
    }
    sidecar = next(item for item in scoring if item.mutation_kind == "legacy_observation_id_access")
    assert sidecar.observed_core_terminal == "valid_trajectory"
    assert sidecar.report_completeness_blocked
    assert len(compiler) == 8
    assert all(item.replay_passed and item.failure_channels_empty for item in compiler)


def test_v26_83_authorizes_only_fresh_small_instrument_requalification(
    rebuilt_83: Path,
) -> None:
    report = BudgetClosedInstrumentPreflightReport.model_validate_json(
        (rebuilt_83 / "report.json").read_text(encoding="utf-8")
    )

    assert report.source_file_replay_pass_count >= 67
    assert report.expected_job_count == report.fresh_job_count == 32
    assert report.compiler_replay_pass_count == 8
    assert report.compiler_completed_scoring_pass_count == 8
    assert report.destructive_replay_mutation_reject_count == 24
    assert report.budget_mutation_pass_count == 7
    assert report.scoring_mutation_pass_count == 3
    assert report.historical_job_identity_overlap_count == 0
    assert not report.model_client_constructed
    assert report.model_api_calls == report.gpu_jobs == report.production_contribution == 0
    assert report.next_permitted_stage == (
        "fresh_budget_closed_verifier_bound_instrument_requalification_only"
    )
    assert report.instrument_requalification_authorized
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized


def test_v26_82_v26_83_identity_and_budget_fields_fail_closed(rebuilt_83: Path) -> None:
    contract_payload = json.loads(
        (rebuilt_83 / "execution_contract.json").read_text(encoding="utf-8")
    )
    budget_payload = dict(contract_payload["provider_token_budget_contract"])
    budget_payload["maximum_total_tokens"] = 119_999
    with pytest.raises(ValidationError, match="identity is invalid"):
        ProviderTokenBudgetContract.model_validate(budget_payload)

    contract_payload["failure_namespaces_separated"] = False
    with pytest.raises(ValidationError):
        BudgetClosedInstrumentContract.model_validate(contract_payload)

    report_payload = json.loads((rebuilt_83 / "report.json").read_text(encoding="utf-8"))
    report_payload["report_id"] = "finance_v26_budget_closed_instrument_preflight:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        BudgetClosedInstrumentPreflightReport.model_validate(report_payload)
