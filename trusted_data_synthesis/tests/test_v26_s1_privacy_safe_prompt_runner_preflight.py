from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_runner_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / preflight.EXECUTION_DIR
POSTRUN_DIR = PACKAGE_ROOT / preflight.POSTRUN_DIR
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


def test_v26_137_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_privacy_safe_prompt_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        postrun_dir=POSTRUN_DIR,
        output_dir=rebuilt_dir,
    )
    formal = preflight.PrivacySafePromptPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.fresh_task_package_count == 24
    assert report.fresh_path_count == 48
    assert report.static_state_count == 324
    assert report.regenerated_action_prompt_count == 972
    assert report.classifier_sensitive_prompt_key_count == 0
    assert report.prompt_echo_privacy_accept_count == 972
    assert report.action_interface_static_preservation_count == 972
    assert report.scripted_fixture_job_count == 32
    assert report.scripted_fixture_call_count == 256
    assert report.first_action_interface_fixture_pass_count == 32
    assert report.formal_v26_134_qualification_remains_failed
    assert not report.unique_historical_rejection_cause_identified
    assert report.provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_137_prompt_identity_runner_and_transition_are_closed() -> None:
    source = preflight.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    predecessor = preflight.PredecessorIntegrityAudit.model_validate_json(
        (FORMAL_DIR / "predecessor_integrity_audit.json").read_text(encoding="utf-8")
    )
    prompt = preflight.PrivacySafePromptMetadataContract.model_validate_json(
        (FORMAL_DIR / "privacy_safe_prompt_metadata_contract.json").read_text(encoding="utf-8")
    )
    tasks = preflight.PrivacySafeTaskPackageCatalog.model_validate_json(
        (FORMAL_DIR / "privacy_safe_task_package_catalog.json").read_text(encoding="utf-8")
    )
    paths = preflight.PrivacySafePathCatalog.model_validate_json(
        (FORMAL_DIR / "privacy_safe_path_catalog.json").read_text(encoding="utf-8")
    )
    noninterference = preflight.PromptPrivacyNoninterferenceAudit.model_validate_json(
        (FORMAL_DIR / "prompt_privacy_noninterference_audit.json").read_text(encoding="utf-8")
    )
    resource = preflight.PrivacySafeResourceContract.model_validate_json(
        (FORMAL_DIR / "privacy_safe_resource_contract.json").read_text(encoding="utf-8")
    )
    qualification = preflight.PrivacySafeQualificationContract.model_validate_json(
        (FORMAL_DIR / "privacy_safe_qualification_contract.json").read_text(encoding="utf-8")
    )
    manifest = preflight.PrivacySafeQualificationManifest.model_validate_json(
        (FORMAL_DIR / "privacy_safe_qualification_manifest.json").read_text(encoding="utf-8")
    )
    outcome = preflight.PrivacySafeOutcomeContract.model_validate_json(
        (FORMAL_DIR / "privacy_safe_outcome_contract.json").read_text(encoding="utf-8")
    )
    runner = preflight.PrivacySafeRunnerContract.model_validate_json(
        (FORMAL_DIR / "privacy_safe_runner_contract.json").read_text(encoding="utf-8")
    )
    fixture = preflight.RunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "privacy_safe_runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    controls = preflight.RunnerControlAudit.model_validate_json(
        (FORMAL_DIR / "privacy_safe_runner_control_audit.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 3_884
    assert predecessor.predecessor_rebuild_byte_match_count == 10
    assert predecessor.formal_qualification_remains_failed
    assert predecessor.historical_privacy_rejected_job_count == 1
    assert not predecessor.historical_rejected_payload_or_key_recovered_or_inferred

    assert prompt.prompt_protocol == preflight.PRIVACY_SAFE_PROMPT_PROTOCOL
    assert tuple(item.old_key_path for item in prompt.metadata_renames) == (
        "private_reasoning_reused",
        "response_grammar.private_reasoning_content",
    )
    assert tuple(item.new_key_path for item in prompt.metadata_renames) == (
        "hidden_model_content_reused",
        "response_grammar.hidden_model_content",
    )
    assert prompt.privacy_instruction_scalar_value == preflight.PRIVACY_INSTRUCTION
    assert not prompt.classifier_changed
    assert not prompt.action_grammar_changed
    assert not prompt.candidate_or_s1_changed

    assert tasks.task_package_count == 24
    assert tasks.predecessor_identity_overlap_count == 0
    assert paths.path_count == 48
    assert paths.state_count == 324
    assert paths.regenerated_prompt_count == 972
    assert paths.prompt_hash_changed_count == 972
    assert paths.classifier_sensitive_key_count == 0
    assert paths.prompt_echo_privacy_accept_count == 972
    assert paths.state_candidate_reference_commit_preservation_count == 972
    assert paths.maximum_action_primary_prompt_utf8_bytes == 14_035
    assert paths.maximum_action_abi_rescue_prompt_utf8_bytes == 14_139
    assert paths.maximum_semantic_recovery_prompt_utf8_bytes == 14_135
    assert paths.maximum_registered_path_static_tokens == 340_428

    assert noninterference.predecessor_sensitive_key_occurrence_count == 1_944
    assert noninterference.privacy_safe_sensitive_key_occurrence_count == 0
    assert noninterference.predecessor_prompt_echo_privacy_rejection_count == 972
    assert noninterference.privacy_safe_prompt_echo_privacy_rejection_count == 0
    assert noninterference.privacy_safe_prompt_echo_privacy_accept_count == 972
    assert noninterference.synthetic_forbidden_reasoning_key_privacy_rejection_count == 24
    assert noninterference.predecessor_classifier_case_pass_count == 24
    assert not noninterference.historical_rejection_cause_identified

    assert resource.prompt_upper_bound_bytes == 60_000
    assert resource.maximum_primary_stage_one_requests == 21
    assert resource.maximum_stage_one_provider_calls == 23
    assert resource.maximum_transport_inclusive_invocations == 24
    assert resource.rollout_upper_bound_tokens == 1_120_000
    assert not resource.resource_bound_values_changed
    assert qualification.prior_formal_qualification_failure_retained
    assert qualification.privacy_gate_is_noncompensatory
    assert not qualification.provider_calls_authorized

    assert manifest.exact_denominator == 32
    assert manifest.distinct_task_package_count == 24
    assert manifest.predecessor_job_identity_overlap_count == 0
    assert manifest.role_source_job_count == 0
    assert all(item.thinking_type == "enabled" for item in manifest.jobs)
    assert outcome.clean_prompt_future_privacy_rejection_fails_closed
    assert not outcome.classifier_relaxation_alias_stripping_or_output_repair_authorized
    assert not outcome.repeat_prompt_tuning_until_pass_authorized
    assert runner.privacy_classifier_unchanged
    assert runner.privacy_safe_s1_only_model_visible_action_prompts
    assert runner.stage_two_provider_call_upper_bound == 0

    assert fixture.scripted_job_count == fixture.completed_job_count == 32
    assert fixture.scripted_local_calls == 256
    assert fixture.first_action_interface_qualified_count == 32
    assert fixture.privacy_safe_s1_action_prompt_count == 224
    assert fixture.predecessor_sensitive_prompt_key_count == 0
    assert fixture.real_provider_calls == 0
    assert controls.control_count == controls.passed_control_count == 17
    assert destructive.mutation_count == destructive.rejection_count == 28
    assert transition.next_permitted_stage == preflight.NEXT_STAGE
    assert transition.only_exact_fresh_32_job_engineering_manifest_authorized
    assert transition.provider_calls_authorized
    assert not transition.role_provider_calls_authorized
    assert not transition.capability_reachability_execution_authorized
    assert transition.privacy_gate_remains_zero_tolerance_and_noncompensatory
