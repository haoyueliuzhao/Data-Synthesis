from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


def test_v26_140_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_capability_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=rebuilt_dir,
    )
    formal = preflight.CapabilityPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.fresh_capability_task_package_count == 12
    assert report.fresh_capability_path_count == 12
    assert report.fresh_capability_job_count == 96
    assert report.registered_role_state_count == 111
    assert report.registered_v2_action_prompt_count == 333
    assert report.scripted_fixture_call_count == 984
    assert report.eligible_capability_detour_pass_count == 9
    assert report.fresh_reachability_identity_count == 0
    assert report.provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert not report.capability_execution_occurred
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_140_capability_identity_runner_and_transition_are_closed() -> None:
    source = preflight.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    predecessor = preflight.PredecessorIntegrityAudit.model_validate_json(
        (FORMAL_DIR / "predecessor_integrity_audit.json").read_text(encoding="utf-8")
    )
    frozen = preflight.FrozenCapabilityInputAudit.model_validate_json(
        (FORMAL_DIR / "frozen_capability_input_audit.json").read_text(encoding="utf-8")
    )
    tasks = preflight.CapabilityTaskPackageCatalog.model_validate_json(
        (FORMAL_DIR / "capability_task_package_catalog.json").read_text(encoding="utf-8")
    )
    paths = preflight.CapabilityPathCatalog.model_validate_json(
        (FORMAL_DIR / "capability_path_catalog.json").read_text(encoding="utf-8")
    )
    noninterference = preflight.CapabilityPromptNoninterferenceAudit.model_validate_json(
        (FORMAL_DIR / "capability_prompt_noninterference_audit.json").read_text(encoding="utf-8")
    )
    resource = preflight.CapabilityResourceBinding.model_validate_json(
        (FORMAL_DIR / "capability_resource_binding.json").read_text(encoding="utf-8")
    )
    contract = preflight.CapabilityExecutionContract.model_validate_json(
        (FORMAL_DIR / "capability_execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = preflight.CapabilityManifest.model_validate_json(
        (FORMAL_DIR / "privacy_safe_capability_manifest.json").read_text(encoding="utf-8")
    )
    outcome = preflight.CapabilityOutcomeContract.model_validate_json(
        (FORMAL_DIR / "capability_outcome_contract.json").read_text(encoding="utf-8")
    )
    runner = preflight.CapabilityRunnerContract.model_validate_json(
        (FORMAL_DIR / "capability_runner_contract.json").read_text(encoding="utf-8")
    )
    fixture = preflight.RunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "capability_runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    dynamic = preflight.CapabilityDynamicEnvelopeAudit.model_validate_json(
        (FORMAL_DIR / "capability_dynamic_envelope_audit.json").read_text(encoding="utf-8")
    )
    controls = preflight.RunnerControlAudit.model_validate_json(
        (FORMAL_DIR / "capability_runner_control_audit.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 4_535
    assert predecessor.predecessor_rebuild_byte_match_count == 9
    assert predecessor.exact_v2_engineering_s1_qualification_passed
    assert predecessor.historical_v1_gate_remains_failed
    assert frozen.capability_task_count == frozen.capability_path_count == 12
    assert frozen.capability_job_count == 96
    assert frozen.fresh_reachability_job_count == 0
    assert frozen.role_population_task_or_tier_changed is False

    assert tasks.task_package_count == 12
    assert tasks.predecessor_identity_overlap_count == 0
    assert tasks.mechanism_tier_cell_count == 12
    assert all(item.role == "capability" for item in tasks.packages)
    assert all(item.thinking_type == "enabled" for item in tasks.packages)

    assert paths.path_count == 12
    assert paths.registered_state_count == 111
    assert paths.regenerated_action_prompt_count == 333
    assert paths.maximum_candidate_count == 63
    assert paths.maximum_action_primary_prompt_utf8_bytes == 49_504
    assert paths.maximum_action_abi_rescue_prompt_utf8_bytes == 49_608
    assert paths.maximum_action_semantic_recovery_prompt_utf8_bytes == 49_604
    assert paths.maximum_registered_path_static_tokens == 676_111
    assert paths.classifier_sensitive_key_count == 0
    assert paths.reachability_path_count == 0

    assert noninterference.predecessor_sensitive_key_occurrence_count == 666
    assert noninterference.classifier_sensitive_key_count == 0
    assert noninterference.privacy_safe_prompt_echo_privacy_rejection_count == 0
    assert noninterference.privacy_safe_prompt_echo_privacy_accept_count == 333
    assert noninterference.exact_state_candidate_reference_commit_count == 333

    assert resource.prompt_upper_bound_bytes == 60_000
    assert resource.maximum_primary_stage_one_requests == 21
    assert resource.maximum_stage_one_provider_calls == 23
    assert resource.maximum_transport_inclusive_invocations == 24
    assert resource.rollout_upper_bound_tokens == 1_120_000
    assert not resource.old_resource_values_changed
    assert not resource.new_resource_candidate_selected
    assert contract.exact_job_denominator == 96
    assert contract.role == "capability"
    assert not contract.reachability_identity_or_execution_included

    assert manifest.exact_denominator == 96
    assert manifest.distinct_task_package_count == 12
    assert manifest.distinct_seed_count == 96
    assert manifest.exact_assignment_seed_preservation_count == 96
    assert manifest.reachability_job_count == 0
    assert all(item.predecessor_job.seed == item.seed for item in manifest.jobs)
    assert all(
        item.predecessor_job.replicate_index == item.replicate_index for item in manifest.jobs
    )

    assert outcome.model_invalid_trajectories_retained_not_instrument_failures
    assert outcome.detour_support_exit_not_model_invalid
    assert outcome.independent_postrun_audit_required
    assert outcome.passing_capability_does_not_directly_authorize_reachability_execution

    assert runner.capability_only
    assert not runner.reachability_identity_or_route_present
    assert runner.v2_privacy_safe_s1_only_action_prompts
    assert runner.privacy_classifier_unchanged
    assert runner.stage_two_provider_call_upper_bound == 0
    assert fixture.scripted_job_count == fixture.completed_job_count == 96
    assert fixture.scripted_local_calls == 984
    assert fixture.semantic_action_primary_count == 888
    assert fixture.public_observation_count == 792
    assert fixture.raw_recovery_pass_count == 96
    assert fixture.real_provider_calls == 0

    assert dynamic.eligible_capability_detour_count == 9
    assert dynamic.eligible_capability_detour_pass_count == 9
    assert dynamic.maximum_one_detour_prompt_utf8_bytes == 27_881
    assert dynamic.maximum_one_detour_static_tokens == 624_222
    assert dynamic.second_detour_typed_terminal_passed
    assert dynamic.later_provider_calls_after_second_detour == 0
    assert controls.control_count == controls.passed_control_count == 25
    assert destructive.mutation_count == destructive.rejection_count == 39

    assert transition.next_permitted_stage == preflight.NEXT_STAGE
    assert transition.exact_fresh_96_job_capability_execution_authorized
    assert transition.provider_calls_authorized_only_for_exact_capability_denominator
    assert transition.capability_execution_authorized
    assert not transition.reachability_identity_materialization_authorized
    assert not transition.reachability_execution_authorized
    assert not transition.state_mapping_authorized
