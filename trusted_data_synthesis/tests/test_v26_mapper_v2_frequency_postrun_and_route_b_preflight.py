from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyEndpointGenerationPolicy,
    make_bounded_policy_endpoint_projection,
    make_bounded_policy_global_integrity_gate,
    summarize_bounded_policy_cell,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_postrun_audit as postrun,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bounded_policy_endpoint_frequency_preflight_models import (  # noqa: E501
    BoundedPolicyEndpointFixtureAudit,
    BoundedPolicyEstimandContract,
    BoundedPolicyFrequencyApiFixtureAudit,
    BoundedPolicyOutcomeContract,
    BoundedPolicyPreflightReport,
    BoundedPolicyRunnerContract,
    PredecessorReplayAudit,
    ProspectiveTransitionContract,
    RouteBSourceSelectionAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyManifest,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
POSTRUN_DIR = PACKAGE_ROOT / postrun.OUTPUT_DIR
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="session")
def rebuilt_route_b_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_163_route_b_rebuild")
    preflight.build_bounded_policy_endpoint_frequency_preflight(
        implementation_root=PACKAGE_ROOT,
        artifact_root=preflight.RECOVERED_ARTIFACT_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def test_bounded_policy_endpoint_core_separates_horizon_support_and_cell_gates() -> None:
    policy = BoundedPolicyEndpointGenerationPolicy.model_validate(
        _load(FORMAL_DIR / "generation_policy.json")
    )
    horizon = make_bounded_policy_endpoint_projection(
        trajectory_id="horizon-trajectory",
        generation_policy_id=policy.policy_id,
        terminal_class="policy_horizon_exhausted",
        policy_horizon_reason="ordinary_detour_limit",
        raw_instrument_integrity=True,
        measurement_support_available=True,
        resource_accounting_integrity=True,
        provider_identity_integrity=True,
        thinking_usage_integrity=True,
        privacy_compliant=True,
        transport_resolved=True,
        model_terminal_observed=False,
        task_completion=False,
        base_validity=False,
        mechanism_qualification=False,
        qualified_validity=False,
        task_verifier_invocation_count=0,
    )
    assert horizon.policy_terminal_observed is True
    assert horizon.model_terminal_observed is False
    assert horizon.support_exit is False
    assert horizon.instrument_failure is False
    assert horizon.resource_failure is False
    assert horizon.validity_evaluable is True
    assert horizon.bounded_policy_endpoint_observed is True
    assert horizon.state_mapping_eligible is False

    unsupported = make_bounded_policy_endpoint_projection(
        trajectory_id="unsupported-trajectory",
        generation_policy_id=policy.policy_id,
        terminal_class="measurement_support_exit",
        policy_horizon_reason=None,
        raw_instrument_integrity=True,
        measurement_support_available=False,
        resource_accounting_integrity=True,
        provider_identity_integrity=True,
        thinking_usage_integrity=True,
        privacy_compliant=True,
        transport_resolved=True,
        model_terminal_observed=False,
        task_completion=None,
        base_validity=None,
        mechanism_qualification=None,
        qualified_validity=None,
        task_verifier_invocation_count=0,
    )
    assert unsupported.support_exit is True
    assert unsupported.instrument_failure is False
    assert unsupported.bounded_policy_endpoint_observed is False
    assert unsupported.validity_evaluable is False

    passing = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=12,
        complete_raw_count=12,
        bounded_policy_endpoint_count=12,
    )
    zero = summarize_bounded_policy_cell(
        task_condition_cell_id="zero-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=12,
        observed_n_total=12,
        endpoint_count=12,
        qualified_state_ids=(),
    )
    assert zero.q_hat == "0"
    assert zero.q_wilson_interval is not None
    assert zero.pi_instantiated is False
    assert zero.pi_null_reason == "no_qualified_rows"

    incomplete = summarize_bounded_policy_cell(
        task_condition_cell_id="incomplete-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=6,
        observed_n_total=6,
        endpoint_count=5,
        qualified_state_ids=("state-a",),
    )
    assert incomplete.q_hat is None
    assert incomplete.pi_null_reason == "cell_endpoint_gate_failed"


def test_v26_162_independent_postrun_audit_freezes_the_negative_lineage() -> None:
    report = postrun.PostrunAuditReport.model_validate(_load(POSTRUN_DIR / "report.json"))
    source = postrun.SourceReplayAudit.model_validate(
        _load(POSTRUN_DIR / "source_replay_audit.json")
    )
    gate = postrun.IndependentGateAudit.model_validate(
        _load(POSTRUN_DIR / "independent_gate_audit.json")
    )
    cells = postrun.CellAndNullAudit.model_validate(_load(POSTRUN_DIR / "cell_and_null_audit.json"))
    support = postrun.SupportBoundaryAudit.model_validate(
        _load(POSTRUN_DIR / "support_boundary_audit.json")
    )
    route_b = postrun.RouteBDecisionContract.model_validate(
        _load(POSTRUN_DIR / "route_b_decision_contract.json")
    )

    assert source.execution_file_count == source.execution_file_byte_match_count == 9_797
    assert source.provider_calls == 0
    assert report.exact_raw_count == 360
    assert report.provider_artifact_triple_count == 3_134
    assert gate.model_endpoint_count == gate.validity_evaluable_count == 359
    assert gate.measurement_support_exit_count == 1
    assert gate.raw_native_instrument_failure_count == 0
    assert gate.resource_accounting_failure_count == 0
    assert report.base_valid_count == report.qualified_valid_count == 139
    assert report.mechanism_qualified_count == 270
    assert gate.passed is False
    assert cells.zero_qualified_cell_count == 8
    assert cells.formal_assignment_count == 0
    assert cells.null_report_count == 48
    assert support.stage_one_provider_call_count == 3
    assert support.transport_invocation_count == 3
    assert support.provider_total_tokens == 40_041
    assert support.later_provider_calls == 0
    assert route_b.selected_route == "route_b_defined_bounded_policy"
    assert route_b.provider_execution_authorized is False
    assert route_b.next_permitted_stage == (
        "fresh_bounded_policy_endpoint_frequency_preflight_only"
    )


def test_v26_163_route_b_preflight_freezes_fresh_complete_policy_endpoint_chain() -> None:
    report = BoundedPolicyPreflightReport.model_validate(_load(FORMAL_DIR / "report.json"))
    replay = PredecessorReplayAudit.model_validate(
        _load(FORMAL_DIR / "predecessor_replay_audit.json")
    )
    selection = RouteBSourceSelectionAudit.model_validate(
        _load(FORMAL_DIR / "source_selection_audit.json")
    )
    policy = BoundedPolicyEndpointGenerationPolicy.model_validate(
        _load(FORMAL_DIR / "generation_policy.json")
    )
    estimand = BoundedPolicyEstimandContract.model_validate(
        _load(FORMAL_DIR / "frequency_estimand_contract.json")
    )
    outcome = BoundedPolicyOutcomeContract.model_validate(
        _load(FORMAL_DIR / "frequency_outcome_contract.json")
    )
    runner = BoundedPolicyRunnerContract.model_validate(
        _load(FORMAL_DIR / "frequency_runner_contract.json")
    )
    manifest = FrequencyManifest.model_validate(_load(FORMAL_DIR / "frequency_manifest.json"))
    endpoint = BoundedPolicyEndpointFixtureAudit.model_validate(
        _load(FORMAL_DIR / "bounded_policy_endpoint_fixture_audit.json")
    )
    api = BoundedPolicyFrequencyApiFixtureAudit.model_validate(
        _load(FORMAL_DIR / "bounded_policy_frequency_api_fixture_audit.json")
    )
    transition = ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    support = _load(FORMAL_DIR / "support_closure_audit.json")
    detours = _load(FORMAL_DIR / "detour_qualification_audit.json")
    resource = _load(FORMAL_DIR / "reachability_resource_contract.json")
    generation = _load(FORMAL_DIR / "reachability_runner_fixture_audit.json")
    destructive = _load(FORMAL_DIR / "destructive_audit.json")

    assert replay.predecessor_direct_output_count == replay.predecessor_byte_match_count == 9
    assert replay.migrated_checkout_snapshot_available is False
    assert replay.external_recovered_snapshot_available is True
    assert replay.external_recovered_snapshot_sha256 == preflight.EXPECTED_SOURCE_SNAPSHOT_SHA256
    assert replay.external_recovered_snapshot_byte_count == 604_998_387
    assert replay.v26_158_full_transitive_rebuild_claimed is False
    assert selection.exclusion_registry_task_count == 48
    assert selection.exclusion_overlap_with_frame == 0
    assert selection.frame_candidate_count_before_exclusion == 70
    assert selection.frame_candidate_count_after_exclusion == 70
    assert selection.prior_historical_excluded_evidence_count == 27_173
    assert selection.prior_population_evidence_count == 300
    assert selection.effective_excluded_evidence_count == 27_473
    assert all(item.overlap_count == 0 for item in selection.freshness_channels)
    assert policy.maximum_ordinary_detours == 1
    assert policy.horizon_is_generation_policy_endpoint is True
    assert policy.horizon_is_measurement_support_exit is False
    assert estimand.q_uncertainty_method == "wilson_score_95_percent"
    assert estimand.pi_uncertainty_method == "marginal_wilson_score_95_percent"
    assert estimand.minimum_qualified_rows_for_pi == 1
    assert estimand.minimum_qualified_rows_for_empirical_non_degeneracy == 2
    assert estimand.minimum_distinct_states_for_empirical_non_degeneracy == 2
    assert estimand.stable_population_probability_claimed is False
    assert outcome.policy_horizon_is_complete_failure_endpoint is True
    assert runner.policy_horizon_after_observation_before_next_provider is True
    assert runner.stage_two_provider_call_upper_bound == 0
    assert manifest.exact_denominator == 360
    assert manifest.unconditional_job_count == 144
    assert manifest.conditioned_job_count == 216
    assert manifest.historical_job_overlap_count == 0
    assert manifest.historical_seed_overlap_count == 0

    assert support["unique_state_count"] == 756
    assert support["candidate_event_count"] == 2_581
    assert support["ordinary_detour_event_count"] == 362
    assert support["typed_support_exit_count"] == 0
    assert detours["qualified_closed_row_count"] == 159
    assert detours["ordinary_replan_not_closed_count"] == 203
    assert detours["distinct_path_count"] == 36
    assert resource["measured_maximum_reference_prompt_utf8_bytes"] == 52_816
    assert resource["measured_maximum_reference_path_tokens"] == 1_021_830
    assert resource["conservative_one_detour_upper_bound_tokens"] == 1_074_977
    assert resource["selected_rollout_headroom_tokens"] == 45_023
    assert generation["scripted_job_count"] == 360
    assert generation["scripted_local_calls"] == 4_158
    assert generation["raw_recovery_pass_count"] == 360
    assert endpoint.second_detour_policy_terminal == "policy_horizon_exhausted"
    assert endpoint.second_detour_measurement_support_available is True
    assert endpoint.second_detour_raw_instrument_integrity is True
    assert endpoint.second_detour_resource_accounting_integrity is True
    assert endpoint.second_detour_qualified_validity is False
    assert endpoint.second_detour_state_mapping_eligible is False
    assert endpoint.second_detour_task_verifier_invocation_count == 0
    assert api.complete_zero_qualified_q_zero_count == 1
    assert api.complete_zero_qualified_pi_null_count == 1
    assert api.simultaneous_multinomial_coverage_claim_count == 0
    assert destructive["mutation_count"] == destructive["rejected_count"] == 26
    assert report.formal_assignment_count == report.formal_frequency_report_count == 0
    assert report.real_provider_calls == report.stage_two_provider_calls == 0
    assert transition.next_permitted_stage == (
        "fresh_bounded_policy_endpoint_frequency_execution_only"
    )
    assert transition.exact_fresh_360_job_manifest_execution_authorized is True
    assert transition.current_denominator_frequency_authorized is False
    assert transition.state_probability_vtdo_training_release_or_production_authorized is False


def test_v26_163_formal_build_is_byte_stable(rebuilt_route_b_dir: Path) -> None:
    formal_files = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt_files = tuple(sorted(path for path in rebuilt_route_b_dir.iterdir() if path.is_file()))
    assert len(formal_files) == len(rebuilt_files) == 34
    assert tuple(path.name for path in formal_files) == tuple(path.name for path in rebuilt_files)
    for formal in formal_files:
        rebuilt = rebuilt_route_b_dir / formal.name
        assert formal.read_bytes() == rebuilt.read_bytes(), formal.name
        assert _sha256(formal) == _sha256(rebuilt)
