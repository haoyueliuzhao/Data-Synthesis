from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.EXECUTION_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def test_v26_135_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = audit.build_postrun_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=rebuilt_dir,
    )
    formal = audit.PostrunAuditReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "s1_representation_qualification_failed_closed"
    assert report.first_action_interface_qualified_job_count == 31
    assert report.qualified_mechanism_path_cell_count == 12
    assert report.privacy_rejected_job_count == 1
    assert not report.qualification_gate_passed
    assert report.provider_calls == 0
    assert report.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_135_gate_privacy_lineage_and_transition_are_closed() -> None:
    source = audit.PostrunSourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    raw = audit.IndependentRawReconstructionAudit.model_validate_json(
        (FORMAL_DIR / "independent_raw_reconstruction_audit.json").read_text(encoding="utf-8")
    )
    gate = audit.QualificationGateAudit.model_validate_json(
        (FORMAL_DIR / "qualification_gate_audit.json").read_text(encoding="utf-8")
    )
    privacy = audit.PrivacyRejectionAudit.model_validate_json(
        (FORMAL_DIR / "privacy_rejection_audit.json").read_text(encoding="utf-8")
    )
    interpretation = audit.OutcomeInterpretation.model_validate_json(
        (FORMAL_DIR / "outcome_interpretation.json").read_text(encoding="utf-8")
    )
    destructive = audit.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = audit.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 3_864
    assert source.execution_file_count == 638
    assert raw.raw_execution_count == 32
    assert raw.provider_call_count == 197
    assert raw.complete_provider_pair_count == 197
    assert raw.validated_public_payload_count == 196
    assert raw.privacy_rejected_payload_count == 1
    assert raw.exact_model_call_count == 197
    assert raw.thinking_telemetry_call_count == 197
    assert raw.complete_usage_call_count == 197
    assert raw.report_aggregate_match_count == raw.report_aggregate_field_count == 33
    assert raw.private_reasoning_payload_count == 0
    assert raw.stage_two_provider_call_count == 0

    assert gate.entry_quantity_gate_passed
    assert gate.entry_cell_coverage_gate_passed
    assert not gate.zero_integrity_failure_gate_passed
    assert not gate.representation_qualification_gate_passed
    assert gate.first_action_failure_job_ids == (audit.EXPECTED_PRIVACY_REJECTED_JOB_ID,)
    assert gate.terminal_counts == {
        "model_invalid_trajectory": 23,
        "model_valid_trajectory": 9,
    }
    assert gate.ordinary_detour_job_distribution == {"0": 30, "1": 2, "2+": 0}
    assert gate.detour_measurement_support_exit_job_count == 0

    assert privacy.rejected_job_id == audit.EXPECTED_PRIVACY_REJECTED_JOB_ID
    assert privacy.http_success
    assert privacy.response_model == "deepseek-v4-flash"
    assert privacy.projection_status == "privacy_rejected"
    assert not privacy.exact_rejected_payload_persisted
    assert not privacy.exact_rejected_key_persisted
    assert not privacy.exact_semantic_cause_recoverable_from_persisted_artifacts
    assert not privacy.exact_semantic_cause_claimed
    assert not privacy.privacy_persistence_defect_observed

    assert not interpretation.qualification_gate_passed
    assert not interpretation.s1_is_not_interface_floor_claim_authorized
    assert not interpretation.role_scale_s1_readability_claim_authorized
    assert interpretation.only_credential_free_representation_root_cause_audit_authorized
    assert destructive.mutation_count == destructive.rejection_count == 12
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.credential_free_root_cause_audit_authorized
    assert not transition.provider_calls_authorized
    assert not transition.role_provider_calls_authorized
    assert not transition.capability_reachability_state_mapping_authorized
