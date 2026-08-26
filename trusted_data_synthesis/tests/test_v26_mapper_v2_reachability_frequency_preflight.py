from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    make_experimental_condition_v2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    TaskConditionCellCatalogV2,
    make_bounded_generation_policy_v2,
    make_frequency_measurement_gate_v2,
    make_task_condition_cell_catalog_v2,
    make_task_condition_cell_v2,
    summarize_reachability_frequency_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_reachability_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    DestructiveAudit,
    FrequencyApiFixtureAudit,
    FrequencyEstimandContract,
    FrequencyManifest,
    FrequencyPreflightReport,
    FrequencyRunnerContract,
    FreshFrequencySourcePopulation,
    IndependentMapperPreflightAudit,
    ProspectiveTransitionContract,
    ReproducibilityRootAudit,
    RunnerPreflightAudit,
    SourceSelectionAudit,
    ToolSchemaClosureAudit,
    WithinCellContrastAudit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rebuilt_preflight_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_160_rebuild")
    preflight.build_mapper_v2_reachability_frequency_preflight(
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def test_frequency_core_uses_strong_cells_and_never_imputes_missing_states() -> None:
    generation = make_bounded_generation_policy_v2(
        resource_contract_id="resource-contract",
        measurement_support_contract_id="support-contract",
    )
    other_generation = make_bounded_generation_policy_v2(
        resource_contract_id="other-resource-contract",
        measurement_support_contract_id="support-contract",
    )
    unconditional = make_experimental_condition_v2(
        sampling_mode="reachability_unconditional",
        public_condition_id=None,
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id="path-catalog",
    )
    conditioned = make_experimental_condition_v2(
        sampling_mode="reachability_conditioned",
        public_condition_id="public-condition",
        requested_path_id="path-1",
        requested_path_strategy="structured_direct",
        static_path_catalog_id="path-catalog",
    )
    cells = (
        make_task_condition_cell_v2(
            task_package_id="task-1",
            experimental_condition=unconditional,
            generation_policy_id=generation.policy_id,
        ),
        make_task_condition_cell_v2(
            task_package_id="task-1",
            experimental_condition=conditioned,
            generation_policy_id=generation.policy_id,
        ),
    )
    catalog = make_task_condition_cell_catalog_v2(
        static_path_catalog_id="path-catalog",
        generation_policy_id=generation.policy_id,
        cells=cells,
    )
    assert catalog.cell_count == 2
    assert catalog.unconditional_cell_count == 1
    assert catalog.conditioned_cell_count == 1
    assert catalog.empirical_route_signature_count == 0
    assert all(
        item.statistics_key_fields
        == ("task_package_id", "experimental_condition_id", "generation_policy_id")
        for item in catalog.cells
    )

    changed_policy_cell = make_task_condition_cell_v2(
        task_package_id="task-1",
        experimental_condition=unconditional,
        generation_policy_id=other_generation.policy_id,
    )
    assert changed_policy_cell.cell_id != cells[0].cell_id
    with pytest.raises(ValueError, match="TaskConditionCell Catalog changed"):
        make_task_condition_cell_catalog_v2(
            static_path_catalog_id="path-catalog",
            generation_policy_id=generation.policy_id,
            cells=(cells[1], changed_policy_cell),
        )

    failed_gate = make_frequency_measurement_gate_v2(
        exact_job_denominator=2,
        complete_raw_count=2,
        model_endpoint_count=1,
        validity_evaluable_count=1,
        measurement_support_exit_count=1,
    )
    failed_summary = summarize_reachability_frequency_v2(
        experiment_id="experiment",
        measurement_gate=failed_gate,
        cell_catalog=catalog,
        assignments=(),
    )
    assert failed_gate.passed is False
    assert failed_gate.exact_frequency_estimands_null is True
    assert failed_summary.null_report_count == 2
    assert {item.null_reason for item in failed_summary.reports} == {"measurement_gate_failed"}
    assert all(item.distribution is None for item in failed_summary.reports)

    passing_gate = make_frequency_measurement_gate_v2(
        exact_job_denominator=2,
        complete_raw_count=2,
        model_endpoint_count=2,
        validity_evaluable_count=2,
    )
    missing_summary = summarize_reachability_frequency_v2(
        experiment_id="experiment",
        measurement_gate=passing_gate,
        cell_catalog=catalog,
        assignments=(),
    )
    assert passing_gate.passed is True
    assert missing_summary.null_report_count == 2
    assert {item.null_reason for item in missing_summary.reports} == {"no_qualified_rows"}
    assert all(item.distribution is None for item in missing_summary.reports)


def test_v26_160_preflight_freezes_fresh_strong_indexed_denominator() -> None:
    report = FrequencyPreflightReport.model_validate(_load(FORMAL_DIR / "report.json"))
    root = ReproducibilityRootAudit.model_validate(
        _load(FORMAL_DIR / "reproducibility_root_audit.json")
    )
    population = FreshFrequencySourcePopulation.model_validate(
        _load(FORMAL_DIR / "fresh_reachability_source_population.json")
    )
    selection = SourceSelectionAudit.model_validate(
        _load(FORMAL_DIR / "source_selection_audit.json")
    )
    cells = TaskConditionCellCatalogV2.model_validate(
        _load(FORMAL_DIR / "task_condition_cell_catalog.json")
    )
    estimand = FrequencyEstimandContract.model_validate(
        _load(FORMAL_DIR / "frequency_estimand_contract.json")
    )
    manifest = FrequencyManifest.model_validate(_load(FORMAL_DIR / "frequency_manifest.json"))
    runner = FrequencyRunnerContract.model_validate(
        _load(FORMAL_DIR / "frequency_runner_contract.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )

    assert root.predecessor_direct_output_count == 15
    assert root.predecessor_byte_match_count == root.predecessor_direct_output_count
    assert root.missing_historical_snapshot_available is False
    assert root.limitation_preserved_without_false_pass is True
    assert root.v26_158_full_transitive_rebuild_claimed is False
    assert root.credential_lookup_attempted is False
    assert population.task_count == population.mechanism_tier_cell_count == 12
    assert population.model_exposure_count == population.empirical_row_count == 0
    assert selection.prior_selected_source_task_count == 36
    assert selection.eligible_model_unexposed_task_count == 58
    assert len(selection.freshness_channels) == 8
    assert all(item.overlap_count == 0 for item in selection.freshness_channels)
    assert cells.task_count == 12
    assert cells.cell_count == 48
    assert cells.unconditional_cell_count == 12
    assert cells.conditioned_cell_count == cells.conditioned_path_count == 36
    assert cells.empirical_route_signature_count == cells.formal_assignment_count == 0
    assert manifest.exact_denominator == 360
    assert manifest.unconditional_job_count == 144
    assert manifest.conditioned_job_count == 216
    assert manifest.distinct_task_condition_cell_count == 48
    assert manifest.formal_assignment_count == 0
    assert manifest.execution_authorized is False
    assert estimand.unrestricted_natural_agent_distribution_claimed is False
    assert estimand.task_primary_rollout_secondary is True
    assert estimand.empirical_route_signature_conditioning_allowed is False
    assert estimand.no_qualified_row_distribution_is_null is True
    assert estimand.failed_measurement_gate_all_distributions_null is True
    assert runner.maximum_ordinary_detours == 1
    assert runner.reference_mapper_exact_match_required is True
    assert runner.stage_two_provider_call_upper_bound == 0
    assert runner.empirical_execution_authorized is False
    assert report.fresh_job_count == 360
    assert report.formal_state_assignment_count == 0
    assert report.formal_frequency_report_count == 0
    assert report.provider_calls == report.stage_two_provider_calls == report.gpu_jobs == 0
    assert report.frequency_measured is False
    assert report.vtdo_authorized is False
    assert len(report.detail_files) == 32
    assert transition.next_permitted_stage == (
        "fresh_mapper_v2_reachability_frequency_execution_only"
    )
    assert transition.exact_fresh_360_job_execution_authorized is True
    assert transition.historical_rerun_pooling_or_reclassification_authorized is False
    assert transition.vtdo_training_release_or_production_authorized is False


def test_v26_160_preflight_closes_support_tools_mapper_and_null_semantics() -> None:
    tool_closure = ToolSchemaClosureAudit.model_validate(
        _load(FORMAL_DIR / "tool_schema_closure_audit.json")
    )
    within_cell = WithinCellContrastAudit.model_validate(
        _load(FORMAL_DIR / "within_cell_state_contrast_audit.json")
    )
    mapper = IndependentMapperPreflightAudit.model_validate(
        _load(FORMAL_DIR / "independent_mapper_preflight_audit.json")
    )
    frequency_api = FrequencyApiFixtureAudit.model_validate(
        _load(FORMAL_DIR / "frequency_api_fixture_audit.json")
    )
    runner = RunnerPreflightAudit.model_validate(
        _load(FORMAL_DIR / "frequency_runner_preflight_audit.json")
    )
    destructive = DestructiveAudit.model_validate(_load(FORMAL_DIR / "destructive_audit.json"))
    paths = _load(FORMAL_DIR / "reachability_path_catalog.json")
    support = _load(FORMAL_DIR / "support_closure_audit.json")
    detours = _load(FORMAL_DIR / "detour_qualification_audit.json")
    resources = _load(FORMAL_DIR / "reachability_resource_contract.json")
    generation = _load(FORMAL_DIR / "reachability_runner_fixture_audit.json")
    temporal_gold = _load(FORMAL_DIR / "mapper_v2_temporal_gold_fixture_audit.json")

    assert tool_closure.registered_tool_schema_count == 6
    assert tool_closure.environment_tool_count == 6
    assert tool_closure.reachable_candidate_tool_count == 6
    assert tool_closure.reference_commit_tool_count == 6
    assert within_cell.fixture_state_count == 4
    assert within_cell.within_task_condition_state_pair_count == 6
    assert within_cell.action_only_pair_count >= 1
    assert within_cell.result_only_pair_count >= 1
    assert within_cell.failure_or_temporal_pair_count >= 1
    assert mapper.fixture_task_condition_cell_count == 48
    assert mapper.exact_state_match_count == 48
    assert mapper.reference_mapper_called_production_mapper_count == 0
    assert mapper.intentional_mismatch_rejection_count == 1
    assert mapper.formal_assignment_count == 0
    assert frequency_api.failed_gate_all_report_null_count == 48
    assert frequency_api.missing_qualified_cell_null_count == 1
    assert frequency_api.zero_vector_imputation_count == 0
    assert frequency_api.strong_key_rejection_count == 1
    assert frequency_api.conditioned_into_unconditional_rejection_count == 1
    assert frequency_api.route_as_condition_rejection_count == 1
    assert runner.scripted_job_count == runner.scripted_completed_job_count == 360
    assert runner.scripted_raw_recovery_count == 360
    assert runner.covered_task_condition_cell_count == 48
    assert runner.production_reference_match_count == 48
    assert runner.real_provider_calls == runner.stage_two_provider_calls == 0
    assert runner.credential_lookup_attempted is False
    assert destructive.mutation_count == destructive.rejected_count == 25

    assert paths["registered_state_count"] == 411
    assert paths["maximum_candidate_count"] == 63
    assert paths["maximum_prompt_utf8_bytes"] == 53_413
    assert paths["maximum_registered_path_tokens"] == 1_039_122
    assert support["unique_state_count"] == 756
    assert support["candidate_event_count"] == 2_590
    assert support["failed_observation_event_count"] == 90
    assert support["successful_no_progress_event_count"] == 482
    assert support["ordinary_detour_event_count"] == 362
    assert support["typed_support_exit_count"] == 0
    assert detours["qualified_closed_row_count"] == 159
    assert detours["ordinary_replan_not_closed_count"] == 203
    assert detours["distinct_path_count"] == 36
    assert detours["maximum_primary_requests"] == 21
    assert detours["maximum_provider_calls"] == 23
    assert detours["maximum_transport_invocations"] == 24
    assert detours["maximum_prompt_utf8_bytes"] == 53_612
    assert detours["maximum_static_tokens"] == 1_093_418
    assert detours["minimum_rollout_headroom_tokens"] == 26_582
    assert resources["selected_rollout_headroom_tokens"] == 26_582
    assert generation["scripted_job_count"] == generation["completed_job_count"] == 360
    assert generation["scripted_local_calls"] == 4_158
    assert generation["raw_recovery_pass_count"] == 360
    assert temporal_gold["fixture_count"] == temporal_gold["production_pass_count"] == 5
    assert temporal_gold["merge_fixture_count"] == 2
    assert temporal_gold["split_fixture_count"] == 3
    assert temporal_gold["independent_reference_state_match_count"] == 10


def test_v26_160_rebuild_is_byte_identical(rebuilt_preflight_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_preflight_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 33
    for path in formal:
        assert path.read_bytes() == (rebuilt_preflight_dir / path.name).read_bytes()
