from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_preflight as recovery,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / recovery.predecessor.EXECUTION_DIR
PREDECESSOR_DIR = PACKAGE_ROOT / recovery.predecessor.OUTPUT_DIR
FORMAL_DIR = PACKAGE_ROOT / recovery.OUTPUT_DIR


def test_v26_143_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = recovery.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=rebuilt_dir,
    )
    formal = recovery.RecoveryPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "passed_orphan_support_exit_recovery_preflight"
    assert report.exact_recovery_job_count == 3
    assert report.exact_prefix_reconstruction_count == 3
    assert report.typed_support_exit_fixture_count == 3
    assert report.fresh_recovery_job_identity_count == 3
    assert report.real_provider_calls == 0
    assert report.stage_two_provider_calls == 0
    assert report.historical_raw_or_terminal_creation_count == 0
    assert report.next_permitted_stage == recovery.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_143_identity_runner_outcome_and_transition_are_closed() -> None:
    source = recovery.RecoverySourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    rebuilt = recovery.PredecessorRebuildAudit.model_validate_json(
        (FORMAL_DIR / "predecessor_rebuild_audit.json").read_text(encoding="utf-8")
    )
    catalog = recovery.OrphanSupportExitCandidateCatalog.model_validate_json(
        (FORMAL_DIR / "candidate_catalog.json").read_text(encoding="utf-8")
    )
    contract = recovery.OrphanSupportExitRecoveryContract.model_validate_json(
        (FORMAL_DIR / "recovery_contract.json").read_text(encoding="utf-8")
    )
    manifest = recovery.OrphanSupportExitRecoveryManifest.model_validate_json(
        (FORMAL_DIR / "recovery_manifest.json").read_text(encoding="utf-8")
    )
    outcome = recovery.OrphanSupportExitOutcomeContract.model_validate_json(
        (FORMAL_DIR / "outcome_contract.json").read_text(encoding="utf-8")
    )
    runner = recovery.OrphanSupportExitRunnerContract.model_validate_json(
        (FORMAL_DIR / "runner_contract.json").read_text(encoding="utf-8")
    )
    fixture = recovery.RunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    destructive = recovery.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    transition = recovery.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 7_242
    assert source.predecessor_transitive_file_count == 7_234
    assert source.predecessor_output_file_count == 7
    assert source.provider_calls == 0
    assert rebuilt.predecessor_output_count == rebuilt.byte_identical_output_count == 7
    assert rebuilt.complete_raw_execution_count == 93
    assert rebuilt.orphan_job_count == 3
    assert rebuilt.provider_call_count == 858
    assert rebuilt.provider_calls == 0

    assert catalog.exact_candidate_count == 3
    assert catalog.exact_prefix_reconstruction_count == 3
    assert catalog.exact_action_commit_observation_successor_count == 3
    assert catalog.later_provider_invocation_count == 0
    assert all(item.mechanism_id == "failure_recovery" for item in catalog.candidates)
    assert all(item.prefix_provider_call_count == 1 for item in catalog.candidates)
    assert all(item.observation_status == "failed" for item in catalog.candidates)
    assert all(
        item.observation_error_code == "typed_selector_requires_refinement"
        for item in catalog.candidates
    )
    assert all(not item.selected_prompt_only_reference for item in catalog.candidates)
    assert all(item.typed_terminal == recovery.TYPED_TERMINAL for item in catalog.candidates)
    assert all(item.later_provider_invocation_count == 0 for item in catalog.candidates)

    assert contract.candidate_ids == tuple(item.candidate_id for item in catalog.candidates)
    assert contract.later_provider_call_upper_bound == 0
    assert contract.stage_two_provider_call_upper_bound == 0
    assert not contract.provider_calls_authorized
    assert manifest.exact_job_denominator == 3
    assert manifest.fresh_recovery_job_identity_count == 3
    recovery_ids = {item.recovery_job_id for item in manifest.jobs}
    historical_ids = {item.candidate.historical_job_id for item in manifest.jobs}
    assert len(recovery_ids) == len(historical_ids) == 3
    assert recovery_ids.isdisjoint(historical_ids)

    assert outcome.frozen_complete_raw_model_outcome_count == 93
    assert outcome.exact_recovery_support_exit_count == 3
    assert outcome.exact_lineage_endpoint_count == 96
    assert outcome.frozen_independently_valid_model_outcome_count == 17
    assert outcome.support_exit_counts_as_measurement_support_boundary
    assert not outcome.support_exit_counts_as_model_invalid
    assert not outcome.support_exit_counts_as_instrument_failure
    assert not outcome.exact_capability_gate_passed
    assert not outcome.exact_task_weighted_capability_estimate_available
    assert not outcome.reachability_authorized

    assert runner.exact_recovery_job_denominator == 3
    assert runner.persisted_prefix_replay_only
    assert runner.terminal_emitted_before_later_provider_preparation
    assert runner.later_provider_call_upper_bound == 0
    assert not runner.model_client_route_present
    assert not runner.credential_lookup_route_present
    assert not runner.host_reference_fallback_route_present
    assert fixture.exact_fixture_job_count == fixture.typed_support_exit_count == 3
    assert fixture.new_provider_call_count == fixture.later_provider_call_count == 0
    assert fixture.stage_two_provider_call_count == 0

    assert destructive.mutation_count == destructive.rejected_count == 18
    assert destructive.provider_calls == 0
    assert transition.next_permitted_stage == recovery.NEXT_STAGE
    assert transition.exact_three_job_recovery_execution_authorized
    assert transition.exact_typed_support_exit_required
    assert not transition.provider_calls_authorized
    assert not transition.historical_job_rerun_or_reclassification_authorized
    assert not transition.historical_raw_or_terminal_creation_authorized
    assert not transition.host_action_selection_replacement_or_repair_authorized
    assert not transition.capability_continuation_authorized
    assert not transition.reachability_identity_or_execution_authorized
