from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_compatibility_root_cause_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.EXECUTION_DIR
POSTRUN_DIR = PACKAGE_ROOT / audit.POSTRUN_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def test_v26_136_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = audit.build_root_cause_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        postrun_dir=POSTRUN_DIR,
        output_dir=rebuilt_dir,
    )
    formal = audit.RootCauseAuditReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert not report.formal_s1_representation_qualification_passed
    assert report.entry_quantity_gate_passed
    assert report.cell_coverage_gate_passed
    assert report.instrument_integrity_gate_passed
    assert not report.privacy_gate_passed
    assert report.grammar_classifier_compatibility_passed
    assert report.deterministic_prompt_classifier_lexical_hazard_identified
    assert not report.unique_historical_rejection_cause_identified
    assert report.provider_calls == 0
    assert report.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_136_classifier_grammar_prompt_boundary_and_transition_are_closed() -> None:
    source = audit.RootCauseSourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    classifier = audit.PrivacyClassifierTypeSystemAudit.model_validate_json(
        (FORMAL_DIR / "privacy_classifier_type_system_audit.json").read_text(encoding="utf-8")
    )
    grammar = audit.ActionGrammarPrivacyCompatibilityAudit.model_validate_json(
        (FORMAL_DIR / "action_grammar_privacy_compatibility_audit.json").read_text(encoding="utf-8")
    )
    prompt = audit.PromptPrivacyCompatibilityAudit.model_validate_json(
        (FORMAL_DIR / "prompt_privacy_compatibility_audit.json").read_text(encoding="utf-8")
    )
    boundary = audit.AcceptedEntryBoundaryAudit.model_validate_json(
        (FORMAL_DIR / "accepted_entry_boundary_audit.json").read_text(encoding="utf-8")
    )
    gate = audit.QualificationGateDecompositionAudit.model_validate_json(
        (FORMAL_DIR / "qualification_gate_decomposition_audit.json").read_text(encoding="utf-8")
    )
    decision = audit.RootCauseDecision.model_validate_json(
        (FORMAL_DIR / "root_cause_decision.json").read_text(encoding="utf-8")
    )
    destructive = audit.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = audit.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 3_873
    assert classifier.synthetic_case_count == classifier.synthetic_pass_count == 24
    assert classifier.synthetic_rejected_case_count == 10
    assert classifier.synthetic_accepted_case_count == 14
    assert classifier.matching_rule == "casefolded_mapping_key_substring_reasoning"
    assert classifier.scans_mapping_keys
    assert not classifier.scans_scalar_values

    assert grammar.grammar_valid_implies_privacy_acceptance
    assert not grammar.privacy_acceptance_implies_grammar_valid
    assert grammar.historical_exact_action_payload_count == 141
    assert grammar.historical_exact_action_privacy_pass_count == 141
    assert grammar.privacy_rejecting_grammar_valid_mutation_count == 0
    assert not grammar.deterministic_grammar_classifier_incompatibility_found
    assert not grammar.historical_privacy_rejected_row_reclassified

    assert prompt.regenerated_prompt_count == 972
    assert prompt.exact_hash_and_byte_match_count == 972
    assert prompt.model_visible_classifier_sensitive_key_paths == (
        "private_reasoning_reused",
        "response_grammar.private_reasoning_content",
    )
    assert prompt.classifier_sensitive_key_occurrence_count == 1_944
    assert prompt.full_prompt_payload_echo_privacy_rejection_count == 972
    assert prompt.positive_output_instruction_term_count == 0
    assert not prompt.historical_privacy_rejection_attributed_to_prompt_echo

    assert boundary.accepted_first_entry_row_count == 31
    assert boundary.exact_four_field_key_set_count == 31
    assert boundary.first_entry_phase_counts == {"abi_rescue": 5, "primary": 26}
    assert boundary.first_entry_candidate_count_distribution == {"4": 9, "6": 22}
    assert boundary.mechanism_path_cell_count == 12
    assert boundary.neighborhood_mutation_count == 248
    assert boundary.neighborhood_privacy_rejecting_grammar_valid_count == 0
    assert not boundary.rejected_historical_row_payload_or_key_inferred

    assert gate.entry_quantity_gate_passed
    assert gate.cell_coverage_gate_passed
    assert gate.instrument_integrity_gate_passed
    assert not gate.privacy_gate_passed
    assert not gate.overall_authorization_gate_passed
    assert not gate.s1_unreadable_claim_authorized

    assert decision.deterministic_prompt_classifier_lexical_hazard_identified
    assert not decision.unique_historical_privacy_rejection_cause_identified
    assert not decision.privacy_classifier_false_positive_claimed
    assert not decision.model_private_reasoning_leak_claimed
    assert destructive.mutation_count == destructive.rejection_count == 16
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.classifier_sensitive_prompt_metadata_repair_authorized
    assert not transition.classifier_change_authorized
    assert not transition.provider_calls_authorized
    assert not transition.role_provider_calls_authorized
