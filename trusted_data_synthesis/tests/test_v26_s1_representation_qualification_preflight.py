from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


def test_v26_133_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=rebuilt_dir,
    )
    formal = preflight.S1QualificationPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report.model_dump(mode="json") == formal.model_dump(mode="json")
    assert report.status == "s1_representation_qualification_runner_preflight_passed"
    assert report.qualification_job_count == 32
    assert report.scripted_fixture_job_count == 32
    assert report.scripted_fixture_call_count == 256
    assert report.role_task_provider_exposure_count == 0
    assert report.provider_calls == 0
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_133_s1_source_progress_runner_and_transition_are_closed() -> None:
    source = preflight.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    separation = preflight.QualificationSourceSeparationAudit.model_validate_json(
        (FORMAL_DIR / "qualification_source_separation_audit.json").read_text(
            encoding="utf-8"
        )
    )
    progress = preflight.PublicProgressVectorContract.model_validate_json(
        (FORMAL_DIR / "public_progress_vector_contract.json").read_text(encoding="utf-8")
    )
    paths = preflight.S1QualificationPathCatalog.model_validate_json(
        (FORMAL_DIR / "s1_qualification_path_catalog.json").read_text(encoding="utf-8")
    )
    resource = preflight.S1QualificationResourceContract.model_validate_json(
        (FORMAL_DIR / "s1_qualification_resource_contract.json").read_text(encoding="utf-8")
    )
    contract = preflight.S1RepresentationQualificationContract.model_validate_json(
        (FORMAL_DIR / "s1_representation_qualification_contract.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = preflight.S1QualificationManifest.model_validate_json(
        (FORMAL_DIR / "s1_qualification_manifest.json").read_text(encoding="utf-8")
    )
    outcome = preflight.S1QualificationOutcomeContract.model_validate_json(
        (FORMAL_DIR / "s1_qualification_outcome_contract.json").read_text(encoding="utf-8")
    )
    runner = preflight.S1QualificationRunnerContract.model_validate_json(
        (FORMAL_DIR / "s1_qualification_runner_contract.json").read_text(encoding="utf-8")
    )
    fixture = preflight.RunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "s1_runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    controls = preflight.RunnerControlAudit.model_validate_json(
        (FORMAL_DIR / "s1_runner_control_audit.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == 3_209
    assert source.mismatch_count == 0
    assert len(separation.separation_channels) == 8
    assert all(item.overlap_count == 0 for item in separation.separation_channels)
    assert separation.engineering_source_model_exposed_count == 24
    assert separation.frozen_role_source_model_exposure_count == 0
    assert separation.role_class_external_action_count == 252
    assert separation.engineering_state_overlap_with_role_class_external_states == 0
    assert not separation.role_external_frequency_has_online_opportunity_in_engineering_denominator

    assert progress.component_order == preflight.PROGRESS_VECTOR_COMPONENTS
    assert progress.comparison_rule == "canonical_componentwise_equality"
    assert progress.ordinary_detour_requires_non_reference_action
    assert progress.reference_policy_is_measurement_classifier_not_host_choice
    assert not progress.unchanged_vector_means_action_useless

    assert len(paths.paths) == 48
    assert sum(len(item.state_rows) for item in paths.paths) == 324
    assert paths.primary_reconstruction_pass_count == 324
    assert paths.abi_rescue_reconstruction_pass_count == 324
    assert paths.semantic_recovery_reconstruction_pass_count == 324
    assert paths.reversible_commit_pass_count == 324
    assert paths.maximum_action_primary_prompt_utf8_bytes == 13_951
    assert paths.maximum_action_abi_rescue_prompt_utf8_bytes == 14_055
    assert paths.maximum_semantic_recovery_prompt_utf8_bytes == 14_051
    assert paths.maximum_registered_path_static_tokens == 339_504
    assert paths.full_object_fallback_count == 0

    assert resource.prompt_upper_bound_bytes == 60_000
    assert resource.maximum_primary_stage_one_requests == 21
    assert resource.maximum_stage_one_provider_calls == 23
    assert resource.maximum_transport_inclusive_invocations == 24
    assert resource.rollout_upper_bound_tokens == 1_120_000
    assert resource.maximum_ordinary_detours == 1
    assert contract.first_action_interface_minimum_jobs == 24
    assert contract.required_mechanism_path_cell_coverage == 12
    assert not contract.role_task_provider_exposure_authorized
    assert not contract.qualification_rows_role_or_state_eligible

    assert len(manifest.jobs) == 32
    assert len({item.task_package_id for item in manifest.jobs}) == 24
    assert len(manifest.cell_job_counts) == 12
    assert manifest.role_source_job_count == 0
    assert outcome.detour_terminal_counts_as_measurement_support_exit
    assert not outcome.detour_terminal_counts_as_model_invalid
    assert runner.all_four_counters_independent
    assert runner.s1_only_model_visible_action_prompts
    assert not runner.full_object_fallback_allowed
    assert runner.stage_two_provider_call_upper_bound == 0

    assert fixture.completed_job_count == 32
    assert fixture.first_action_interface_qualified_count == 32
    assert fixture.semantic_action_primary_count == 224
    assert fixture.reversible_commit_count == 224
    assert fixture.public_observation_count == 192
    assert fixture.final_primary_count == 32
    assert fixture.scripted_local_calls == 256
    assert fixture.real_provider_calls == 0
    assert controls.control_count == controls.passed_control_count == 13
    assert controls.one_detour_completed
    assert controls.second_detour_terminal == "ordinary_detour_allowance_exhausted"
    assert controls.second_detour_model_proposal_observed
    assert controls.second_detour_tool_observation_observed
    assert controls.later_provider_calls_after_second_detour == 0
    assert destructive.mutation_count == destructive.rejection_count == 24

    assert transition.only_exact_fresh_32_job_engineering_manifest_authorized
    assert transition.provider_calls_authorized
    assert not transition.role_provider_calls_authorized
    assert not transition.capability_reachability_execution_authorized
    assert not transition.qualification_rows_role_or_state_eligible
