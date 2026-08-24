from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_qualification_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.EXECUTION_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def test_v26_139_rebuild_is_byte_identical(tmp_path: Path) -> None:
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
    assert report.status == "privacy_safe_s1_qualification_passed_capability_preflight_only"
    assert report.first_action_interface_qualified_job_count == 31
    assert report.qualified_mechanism_path_cell_count == 12
    assert report.privacy_rejected_job_count == 0
    assert report.combined_integrity_failure_job_count == 0
    assert report.qualification_gate_passed
    assert report.online_v2_action_prompt_count == 173
    assert report.online_classifier_sensitive_key_count == 0
    assert report.provider_calls == 0
    assert not report.capability_execution_authorized
    assert report.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_139_raw_prompt_entry_gate_and_transition_are_closed() -> None:
    source = audit.PostrunSourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    raw = audit.IndependentRawReconstructionAudit.model_validate_json(
        (FORMAL_DIR / "independent_raw_reconstruction_audit.json").read_text(encoding="utf-8")
    )
    prompt = audit.OnlinePromptNoninterferenceAudit.model_validate_json(
        (FORMAL_DIR / "online_prompt_noninterference_audit.json").read_text(encoding="utf-8")
    )
    entry = audit.EntryBoundaryAudit.model_validate_json(
        (FORMAL_DIR / "entry_boundary_audit.json").read_text(encoding="utf-8")
    )
    gate = audit.QualificationGateAudit.model_validate_json(
        (FORMAL_DIR / "qualification_gate_audit.json").read_text(encoding="utf-8")
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

    assert source.replayed_file_count == source.replay_pass_count == 4_525
    assert source.execution_file_count == 623
    assert raw.raw_execution_count == 32
    assert raw.provider_call_count == 191
    assert raw.complete_provider_pair_count == 191
    assert raw.validated_public_payload_count == 191
    assert raw.privacy_rejected_payload_count == 0
    assert raw.exact_model_call_count == 191
    assert raw.thinking_telemetry_call_count == 191
    assert raw.complete_usage_call_count == 191
    assert raw.report_aggregate_match_count == raw.report_aggregate_field_count == 34
    assert raw.exact_byte_descriptor_pass_count == 605
    assert raw.private_reasoning_payload_count == 0
    assert raw.stage_two_provider_call_count == 0

    assert prompt.semantic_action_attempt_count == 173
    assert prompt.action_primary_attempt_count == 147
    assert prompt.action_abi_rescue_attempt_count == 26
    assert prompt.exact_prompt_hash_reconstruction_count == 173
    assert prompt.exact_prompt_byte_count_match_count == 173
    assert prompt.v2_protocol_prompt_count == 173
    assert prompt.classifier_sensitive_key_occurrence_count == 0
    assert prompt.predecessor_sensitive_key_occurrence_count == 0
    assert prompt.exact_state_reconstruction_count == 173
    assert prompt.exact_candidate_set_and_order_count == 173

    assert entry.failed_entry_job_id == audit.EXPECTED_FAILED_ENTRY_JOB_ID
    assert entry.provider_call_count == 2
    assert entry.validated_public_payload_count == 2
    assert entry.privacy_rejected_payload_count == 0
    assert entry.exact_four_field_key_set_count == 2
    assert entry.visible_action_id_count == 2
    assert entry.decision_kind_mismatch_count == 2
    assert entry.observed_decision_kinds == ("select", "query_fully_qualified")
    assert entry.exact_action_abi_count == 0
    assert entry.model_result_not_instrument_failure
    assert entry.privacy_compliant_public_output
    assert not entry.host_alias_or_decision_kind_repair_authorized

    assert gate.entry_quantity_gate_passed
    assert gate.entry_cell_coverage_gate_passed
    assert gate.zero_integrity_failure_gate_passed
    assert gate.representation_qualification_gate_passed
    assert gate.first_action_failure_job_ids == (audit.EXPECTED_FAILED_ENTRY_JOB_ID,)
    assert gate.terminal_counts == {
        "model_invalid_trajectory": 17,
        "model_valid_trajectory": 15,
    }
    assert gate.ordinary_detour_job_distribution == {"0": 31, "1": 1, "2+": 0}
    assert gate.detour_measurement_support_exit_job_count == 0

    assert interpretation.exact_v2_engineering_s1_interface_qualified
    assert interpretation.historical_v26_134_gate_remains_failed
    assert not interpretation.historical_privacy_rejection_cause_identified
    assert not interpretation.role_scale_s1_readability_claim_authorized
    assert interpretation.fresh_capability_identity_and_runner_preflight_authorized
    assert destructive.mutation_count == destructive.rejection_count == 16
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.exact_v2_engineering_s1_interface_qualification_frozen
    assert transition.fresh_capability_taskpackage_contract_manifest_runner_preflight_authorized
    assert not transition.provider_calls_authorized
    assert not transition.capability_execution_authorized
    assert not transition.role_provider_calls_authorized
    assert not transition.reachability_or_state_mapping_authorized
