from pathlib import Path

from trusted_synthesis.core.measurement.support import (
    classify_measurement_support,
    make_measurement_support_event,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_measurement_support_boundary_redesign as redesign,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / redesign.OUTPUT_DIR


def test_v26_146_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = redesign.build_measurement_support_redesign(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=rebuilt_dir,
    )
    formal = redesign.MeasurementSupportRedesignReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "measurement_support_boundary_redesign_passed"
    assert report.registered_path_count == 48
    assert report.registered_state_count == 522
    assert report.registered_candidate_event_count == 3_089
    assert report.unique_typed_state_count == 3_306
    assert report.failed_observation_event_count == 1_667
    assert report.failed_observation_not_required_count == 1_587
    assert report.failed_observation_typed_support_exit_count == 80
    assert report.progress_observation_event_count == 864
    assert report.successful_no_progress_event_count == 510
    assert report.ordinary_detour_event_count == 378
    assert report.baseline_unavailable_decision_count == 0
    assert report.successor_unavailable_decision_count == 80
    assert report.host_exception_count == 0
    assert report.provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert report.next_permitted_stage == redesign.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_146_typed_closure_authority_and_transition_are_closed() -> None:
    source = redesign.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    predecessor = redesign.PredecessorIntegrityAudit.model_validate_json(
        (FORMAL_DIR / "predecessor_integrity_audit.json").read_text(encoding="utf-8")
    )
    contract = redesign.MeasurementSupportContract.model_validate_json(
        (FORMAL_DIR / "measurement_support_contract.json").read_text(encoding="utf-8")
    )
    authority = redesign.BaselineAuthorityAudit.model_validate_json(
        (FORMAL_DIR / "baseline_authority_audit.json").read_text(encoding="utf-8")
    )
    census = redesign.SupportClosureCensus.model_validate_json(
        (FORMAL_DIR / "support_closure_census.json").read_text(encoding="utf-8")
    )
    orphan = redesign.OrphanFutureContractControl.model_validate_json(
        (FORMAL_DIR / "orphan_future_contract_control.json").read_text(encoding="utf-8")
    )
    destructive = redesign.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = redesign.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 7_294
    assert source.predecessor_transitive_file_count == 7_283
    assert source.predecessor_output_file_count == 7
    assert source.implementation_file_count == 4
    assert source.provider_calls == 0
    assert predecessor.predecessor_output_file_count == 7
    assert predecessor.byte_identical_file_count == 7
    assert predecessor.frozen_lineage_endpoint_count == 96
    assert predecessor.frozen_model_outcome_count == 93
    assert predecessor.frozen_support_exit_count == 3
    assert predecessor.historical_reclassified_count == 0

    assert not contract.failed_observation_requires_baseline
    assert not contract.progress_observation_requires_baseline
    assert contract.successful_no_progress_requires_baseline
    assert contract.unselectable_public_successor_is_typed_support_exit
    assert contract.baseline_uses_current_public_state_only
    assert contract.baseline_is_not_model_visible
    assert not contract.unavailable_is_model_invalid
    assert not contract.unavailable_is_instrument_failure
    assert authority.banned_read_count == 0
    assert authority.oracle_read_count == 0
    assert authority.gold_read_count == 0
    assert authority.correct_answer_read_count == 0
    assert authority.future_trajectory_read_count == 0
    assert authority.target_evidence_read_count == 0
    assert authority.public_path_condition_read_count == 0
    assert authority.model_prompt_exposure_count == 0
    assert authority.candidate_mutation_count == 0

    assert census.registered_path_count == 48
    assert census.registered_state_count == 522
    assert census.registered_prompt_phase_state_count == 1_566
    assert census.registered_candidate_event_count == 3_089
    assert census.semantic_recovery_state_count == 501
    assert census.unique_typed_state_count == 3_306
    assert census.typed_state_resolution_count == 3_306
    assert census.failed_observation_event_count == 1_667
    assert census.failed_observation_not_required_count == 1_587
    assert census.failed_observation_typed_support_exit_count == 80
    assert census.progress_observation_event_count == 864
    assert census.successful_no_progress_event_count == 510
    assert census.unselectable_successor_event_count == 80
    assert census.unselectable_successor_error_counts == {
        "calculator_contract": 76,
        "normalize_metric_unit_period_contract": 4,
    }
    assert census.failed_observation_baseline_classifier_call_count == 0
    assert census.progress_observation_baseline_classifier_call_count == 0
    assert census.successful_no_progress_baseline_classifier_call_count == 510
    assert census.available_decision_count == 510
    assert census.not_required_decision_count == 2_499
    assert census.unavailable_decision_count == 80
    assert census.baseline_unavailable_decision_count == 0
    assert census.successor_unavailable_decision_count == 80
    assert census.ordinary_detour_event_count == 378
    assert census.typed_measurement_support_exit_count == 80
    assert census.host_exception_count == 0
    assert census.full_typed_closure_passed
    assert all(
        set(row.resolution.baseline_action_ids).issubset(row.visible_action_ids)
        for row in census.state_rows
    )
    assert all(
        not row.decision.baseline_classifier_invoked
        for row in census.event_rows
        if row.observation_status == "failed" or row.progress_vector_changed
    )
    assert all(
        row.decision.reason_code == "public_replan_state_unavailable_after_failed_observation"
        for row in census.event_rows
        if not row.successor_state_available
    )

    assert orphan.exact_historical_orphan_count == 3
    assert orphan.future_not_required_count == 3
    assert orphan.failed_observation_baseline_classifier_call_count == 0
    assert orphan.historical_reclassified_count == 0
    assert all(row.historical_terminal_unchanged for row in orphan.rows)
    assert all(row.future_model_replanning_allowed for row in orphan.rows)
    assert all(row.future_decision.status == "not_required" for row in orphan.rows)
    assert destructive.mutation_count == destructive.rejected_count == 16
    assert transition.next_permitted_stage == redesign.NEXT_STAGE
    assert transition.historical_capability_validity_decomposition_audit_authorized
    assert not transition.historical_terminal_or_validity_reclassification_authorized
    assert not transition.verifier_change_authorized
    assert not transition.final_grammar_change_authorized
    assert not transition.new_capability_population_or_identity_materialization_authorized
    assert not transition.provider_calls_authorized
    assert not transition.capability_execution_authorized
    assert not transition.reachability_identity_or_execution_authorized
    assert not transition.state_mapping_authorized


def test_measurement_support_classifier_converts_boundary_failures_to_typed_exits() -> None:
    event = make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before="state-before",
        public_state_id_after="state-after",
        progress_vector_id_before="progress",
        progress_vector_id_after="progress",
        selected_action_id="action",
        observation_status="succeeded",
    )

    def failed_resolver() -> redesign.BaselineActionSetResolution:
        raise RuntimeError("private host detail must not cross the boundary")

    decision = classify_measurement_support(event, baseline_resolver=failed_resolver)
    assert decision.status == "unavailable"
    assert decision.reason_code == "baseline_classifier_exception"
    assert decision.baseline_classifier_invoked
    assert not decision.ordinary_detour_observed

    no_successor = make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before="state-before",
        public_state_id_after="typed-support-terminal",
        progress_vector_id_before="progress",
        progress_vector_id_after="progress",
        selected_action_id="action",
        observation_status="failed",
        successor_public_state_available=False,
    )
    successor_decision = classify_measurement_support(
        no_successor,
        baseline_resolver=failed_resolver,
    )
    assert successor_decision.status == "unavailable"
    assert (
        successor_decision.reason_code == "public_replan_state_unavailable_after_failed_observation"
    )
    assert not successor_decision.baseline_classifier_invoked
