from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_failure_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.EXECUTION_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def test_v26_142_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = audit.build_failure_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=rebuilt_dir,
    )
    formal = audit.CapabilityFailureAuditReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "capability_gate_failed_orphan_root_cause_localized"
    assert report.exact_manifest_job_count == 96
    assert report.complete_raw_execution_count == 93
    assert report.orphan_job_count == 3
    assert report.provider_call_count == 858
    assert report.independently_valid_complete_raw_count == 17
    assert report.valid_mechanism_count == 4
    assert not report.exact_denominator_capability_gate_passed
    assert report.historical_orphan_terminal_reclassification_count == 0
    assert report.provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert report.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_142_failed_lineage_root_cause_and_transition_are_closed() -> None:
    source = audit.FailureAuditSourceReplay.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    lineage = audit.FailedLineageAudit.model_validate_json(
        (FORMAL_DIR / "failed_lineage_audit.json").read_text(encoding="utf-8")
    )
    partial = audit.PartialCapabilityOutcomeAudit.model_validate_json(
        (FORMAL_DIR / "partial_capability_outcome_audit.json").read_text(encoding="utf-8")
    )
    root_cause = audit.OrphanRootCauseAudit.model_validate_json(
        (FORMAL_DIR / "orphan_root_cause_audit.json").read_text(encoding="utf-8")
    )
    destructive = audit.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = audit.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 7_234
    assert source.bound_source_file_count == 4_553
    assert source.execution_file_count == 2_680
    assert source.provider_calls == 0

    assert lineage.exact_manifest_job_count == 96
    assert lineage.complete_raw_execution_count == 93
    assert lineage.independently_reprojected_raw_count == 93
    assert lineage.checkpoint_result_count == 93
    assert lineage.orphan_job_count == 3
    assert lineage.manifest_job_artifact_coverage_count == 96
    assert lineage.complete_raw_bound_provider_call_count == 855
    assert lineage.orphan_provider_call_count == 3
    assert lineage.validated_artifact_pair_count == 858
    assert lineage.validated_transport_certificate_count == 858
    assert lineage.completed_report_count == 0
    assert not lineage.exact_denominator_complete
    assert not lineage.capability_gate_passed

    assert partial.complete_raw_subset_count == 93
    assert partial.missing_raw_count == 3
    assert partial.terminal_counts == {
        "model_invalid_trajectory": 76,
        "model_valid_trajectory": 17,
    }
    assert partial.action_entry_count == 92
    assert partial.mechanisms_with_independently_valid_trajectory == 4
    assert partial.provider_call_count == 858
    assert partial.provider_total_tokens == 8_042_572
    assert partial.provider_prompt_tokens == 4_211_294
    assert partial.provider_completion_tokens == 3_831_278
    assert partial.provider_reasoning_tokens == 3_699_772
    assert partial.privacy_rejection_count == 0
    assert partial.provider_failure_no_payload_count == 7
    assert partial.subset_values_are_descriptive_only
    assert not partial.exact_task_weighted_capability_estimate_available
    assert not partial.missing_rows_imputed
    assert not partial.capability_gate_passed

    assert root_cause.orphan_count == 3
    assert root_cause.exact_public_payload_parse_pass_count == 3
    assert root_cause.visible_candidate_commit_pass_count == 3
    assert root_cause.public_observation_replay_pass_count == 3
    assert root_cause.successor_prompt_decode_pass_count == 3
    assert root_cause.successor_state_candidate_preservation_pass_count == 3
    assert root_cause.successor_sensitive_key_count == 0
    assert root_cause.successor_reference_failure_reproduction_count == 3
    assert root_cause.later_provider_invocation_count == 0
    assert root_cause.failure_is_host_measurement_instrument_defect
    assert all(row.public_observation_status == "failed" for row in root_cause.orphan_rows)
    assert all(
        row.public_observation_error_code == "typed_selector_requires_refinement"
        for row in root_cause.orphan_rows
    )
    assert all(not row.selected_prompt_only_reference for row in root_cause.orphan_rows)
    assert all(
        row.typed_measurement_support_exit_recovery_candidate
        for row in root_cause.orphan_rows
    )
    assert all(not row.raw_execution_persisted for row in root_cause.orphan_rows)
    assert all(not row.historical_terminal_assigned for row in root_cause.orphan_rows)

    assert destructive.mutation_count == destructive.rejected_count == 12
    assert destructive.provider_calls == 0
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.exact_orphan_count == 3
    assert transition.reference_unavailable_typed_support_exit_only
    assert transition.zero_later_provider_invocations_required
    assert transition.fresh_recovery_job_identities_required
    assert not transition.provider_calls_authorized
    assert not transition.capability_continuation_authorized
    assert not transition.historical_job_rerun_authorized
    assert not transition.historical_terminal_reclassification_authorized
    assert not transition.host_action_selection_or_repair_authorized
    assert not transition.reachability_identity_or_execution_authorized
