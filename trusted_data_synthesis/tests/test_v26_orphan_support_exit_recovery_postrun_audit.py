from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_EXECUTION_DIR = PACKAGE_ROOT / audit.failed_audit.EXECUTION_DIR
FAILED_AUDIT_DIR = PACKAGE_ROOT / audit.failed_audit.OUTPUT_DIR
PREFLIGHT_DIR = PACKAGE_ROOT / audit.recovery_preflight.OUTPUT_DIR
EXECUTION_DIR = PACKAGE_ROOT / audit.execution.OUTPUT_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def test_v26_145_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = audit.build_postrun_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        historical_execution_dir=HISTORICAL_EXECUTION_DIR,
        failed_audit_dir=FAILED_AUDIT_DIR,
        preflight_dir=PREFLIGHT_DIR,
        execution_dir=EXECUTION_DIR,
        output_dir=rebuilt_dir,
    )
    formal = audit.PostrunAuditReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "capability_gate_failed_support_boundary_redesign_only"
    assert report.exact_lineage_endpoint_count == 96
    assert report.frozen_model_outcome_count == 93
    assert report.measurement_support_boundary_exit_count == 3
    assert not report.exact_capability_gate_passed
    assert not report.exact_task_weighted_capability_estimate_available
    assert report.provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert report.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_145_raw_outcome_and_transition_are_closed() -> None:
    source = audit.PostrunSourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    rebuilt = audit.IndependentExecutionRebuildAudit.model_validate_json(
        (FORMAL_DIR / "independent_execution_rebuild_audit.json").read_text(
            encoding="utf-8"
        )
    )
    raw = audit.IndependentRawReconstructionAudit.model_validate_json(
        (FORMAL_DIR / "independent_raw_reconstruction_audit.json").read_text(
            encoding="utf-8"
        )
    )
    decision = audit.CapabilityOutcomeDecision.model_validate_json(
        (FORMAL_DIR / "capability_outcome_decision.json").read_text(encoding="utf-8")
    )
    destructive = audit.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = audit.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 7_283
    assert source.execution_transitive_file_count == 7_256
    assert source.execution_file_count == 26
    assert source.provider_calls == 0
    assert rebuilt.execution_file_count == rebuilt.byte_identical_file_count == 26
    assert rebuilt.exact_recovery_raw_count == 3
    assert rebuilt.exact_recovery_result_count == 3
    assert rebuilt.provider_calls == 0

    assert raw.exact_recovery_raw_count == 3
    assert raw.exact_recovery_result_count == 3
    assert raw.checkpoint_result_count == 3
    assert raw.exact_manifest_job_match_count == 3
    assert raw.exact_prefix_parent_match_count == 3
    assert raw.exact_action_commit_observation_successor_match_count == 3
    assert raw.typed_support_exit_count == 3
    assert raw.measurement_support_boundary_count == 3
    assert raw.model_outcome_count == 0
    assert raw.model_invalid_count == 0
    assert raw.instrument_failure_count == 0
    assert raw.historical_prefix_provider_call_reissue_count == 0
    assert raw.new_provider_call_count == raw.later_provider_call_count == 0
    assert raw.stage_two_provider_call_count == 0
    assert raw.historical_raw_or_terminal_creation_count == 0
    assert raw.historical_execution_file_count == 2_680
    assert set(raw.recovery_job_ids).isdisjoint(raw.historical_job_parent_ids)

    assert decision.exact_lineage_endpoint_count == 96
    assert decision.frozen_model_outcome_count == 93
    assert decision.frozen_model_valid_trajectory_count == 17
    assert decision.frozen_model_invalid_trajectory_count == 76
    assert decision.measurement_support_boundary_exit_count == 3
    assert decision.support_exits_are_not_model_outcomes
    assert decision.support_exits_are_not_instrument_failures
    assert not decision.exact_model_outcome_denominator_complete
    assert not decision.exact_task_weighted_capability_estimate_available
    assert not decision.exact_capability_gate_passed
    assert decision.complete_raw_subset_remains_descriptive_only
    assert not decision.reachability_authorized
    assert not decision.state_mapping_authorized

    assert destructive.mutation_count == destructive.rejected_count == 14
    assert destructive.provider_calls == 0
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.credential_free_measurement_support_redesign_only
    assert transition.redesign_may_address_reference_unavailable_classification_only
    assert not transition.historical_outcome_reclassification_authorized
    assert not transition.exact_capability_estimate_authorized
    assert not transition.capability_population_or_job_materialization_authorized
    assert not transition.provider_calls_authorized
    assert not transition.capability_execution_authorized
    assert not transition.reachability_identity_or_execution_authorized
