from __future__ import annotations

import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_profile_and_manifest_preflight import (  # noqa: E501
    NEXT_STAGE,
    CrossArtifactBindingAudit,
    DesignPreservationAudit,
    DestructivePreflightAudit,
    SourceReplayAudit,
    StageOneThinkingProfile,
    StageTwoCommitProfile,
    TwoStageExecutionContract,
    TwoStageManifest,
    TwoStagePathAudit,
    TwoStageResourceContract,
    TwoStageStaticPreflightReport,
    TwoStageTaskPackage,
    build,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_execution import (  # noqa: E501
    TwoStageRunnerContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    NEXT_STAGE as RUNNER_NEXT_STAGE,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    ClientRequestBindingAudit,
    ModelFailureClassificationAudit,
    PrecallRecoveryAudit,
    ProviderUsageFixtureAudit,
    RunnerFixtureAudit,
    RunnerPreflightReport,
    RunnerSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    DestructivePreflightAudit as RunnerDestructivePreflightAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    build as build_runner_preflight,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def static_built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, TwoStageStaticPreflightReport]:
    output = tmp_path_factory.mktemp("v26_108_two_stage_static")
    report = build(
        output,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    return output, report


def _models(path: Path, model: type[TwoStageTaskPackage] | type[TwoStagePathAudit]) -> tuple:
    return tuple(model.model_validate(item) for item in __import__("json").loads(path.read_bytes()))


def test_v26_108_replays_every_predecessor_profile_and_implementation_file(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    output, report = static_built
    audit = SourceReplayAudit.model_validate_json((output / "source_replay_audit.json").read_text())
    counts: dict[str, int] = {}
    for item in audit.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert audit.replayed_file_count == audit.replay_pass_count == 1884
    assert counts == {
        "v26_107_transitive_source": 1872,
        "v26_107_output": 10,
        "v26_108_profile": 1,
        "v26_108_implementation": 1,
    }
    assert audit.replay_before_profile_parsing
    assert not audit.credential_lookup_attempted
    assert not audit.model_client_constructed
    assert audit.provider_calls == audit.gpu_jobs == 0
    assert report.source_replay_audit_id == audit.audit_id


def test_v26_108_freezes_fresh_stage_profiles_and_zero_generation_commit(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    output, report = static_built
    stage_one = StageOneThinkingProfile.model_validate_json(
        (output / "stage_one_thinking_profile.json").read_text()
    )
    stage_two = StageTwoCommitProfile.model_validate_json(
        (output / "stage_two_commit_profile.json").read_text()
    )

    assert stage_one.max_output_tokens == 16384
    assert stage_one.thinking_type == "enabled"
    assert stage_one.maximum_model_attempts == 1
    assert stage_one.generic_contract_repair_attempts == 0
    assert stage_one.fallback_model_count == 0
    assert not stage_one.model_discovery_enabled
    assert stage_one.stage_one_owns_semantic_proposal
    assert stage_one.stage_one_owns_final_answer
    assert not stage_one.private_reasoning_cross_stage_allowed
    assert stage_two.deterministic_commit_only
    assert stage_two.reversible_mapping_required
    assert not stage_two.compiler_may_choose_semantic_field
    assert not stage_two.provider_profile_present
    assert stage_two.provider_call_upper_bound == 0
    assert report.stage_one_profile_id == stage_one.profile_id
    assert report.stage_two_profile_id == stage_two.profile_id


def test_v26_108_derives_260k_resource_bound_from_complete_paths(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    output, _ = static_built
    resource = TwoStageResourceContract.model_validate_json(
        (output / "two_stage_resource_contract.json").read_text()
    )
    paths = _models(output / "two_stage_path_audits.json", TwoStagePathAudit)

    assert resource.exact_request_completion_bound_tokens == 16384
    assert resource.accounted_completion_bound_tokens == 16385
    assert resource.rollout_upper_bound_tokens == 260000
    assert resource.maximum_primary_stage_one_requests == 10
    assert resource.maximum_stage_one_provider_calls == 11
    assert resource.maximum_stage_two_provider_calls == 0
    assert resource.static_bound_derived_from_complete_compiler_paths
    assert not resource.historical_v26_105_deficit_used_to_select_bound
    assert len(paths) == 48
    assert min(item.primary_stage_one_request_count for item in paths) == 6
    assert max(item.primary_stage_one_request_count for item in paths) == 10
    assert min(item.static_complete_path_upper_bound_tokens for item in paths) == 150514
    assert max(item.static_complete_path_upper_bound_tokens for item in paths) == 246235
    assert min(item.static_rollout_headroom_tokens for item in paths) == 13765
    assert min(item.maximum_primary_prompt_utf8_bytes for item in paths) == 5317
    assert max(item.maximum_primary_prompt_utf8_bytes for item in paths) == 6345
    assert all(item.stage_two_provider_call_count == 0 for item in paths)


def test_v26_108_rematerializes_identity_chain_without_resampling(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    output, report = static_built
    tasks = _models(output / "two_stage_task_packages.json", TwoStageTaskPackage)
    contract = TwoStageExecutionContract.model_validate_json(
        (output / "two_stage_execution_contract.json").read_text()
    )
    manifest = TwoStageManifest.model_validate_json(
        (output / "two_stage_job_manifest.json").read_text()
    )
    design = DesignPreservationAudit.model_validate_json(
        (output / "design_preservation_audit.json").read_text()
    )

    assert len(tasks) == report.task_package_count == 24
    assert len(contract.path_audit_ids) == report.path_count == 48
    assert len(manifest.jobs) == report.job_count == 32
    assert len({item.task_package_id for item in manifest.jobs}) == 24
    assert design.task_semantic_projection_pass_count == 24
    assert design.path_strategy_and_compiler_projection_pass_count == 48
    assert design.job_assignment_and_seed_projection_pass_count == 32
    assert design.source_model_exposed_count == 24
    assert design.source_claimed_fresh_count == 0
    assert design.task_package_identity_overlap_count == 0
    assert design.path_identity_overlap_count == 0
    assert design.job_identity_overlap_count == 0
    assert not design.selection_changed
    assert not design.seed_changed
    assert not design.path_assignment_changed
    assert design.role_or_state_evidence_eligible_count == 0
    assert not contract.runner_implemented
    assert not contract.execution_authorized
    assert not manifest.execution_authorized


def test_v26_108_cross_artifact_and_destructive_gates_fail_closed(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    output, _ = static_built
    cross = CrossArtifactBindingAudit.model_validate_json(
        (output / "cross_artifact_binding_audit.json").read_text()
    )
    destructive = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )

    assert len(cross.rows) == cross.passed_row_count == 104
    assert cross.task_package_row_count == 24
    assert cross.path_row_count == 48
    assert cross.job_row_count == 32
    assert cross.manifest_contract_binding_passed
    assert cross.all_parent_memberships_closed
    assert cross.static_execution_identity_chain_closed
    assert destructive.mutation_count == destructive.rejected_mutation_count == 30
    assert all(item.rejected for item in destructive.mutation_results)
    assert all(item.provider_calls_before_rejection == 0 for item in destructive.mutation_results)
    assert destructive.provider_calls == destructive.gpu_jobs == 0


def test_v26_108_report_authorizes_runner_preflight_only(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
) -> None:
    _, report = static_built

    assert report.status == "static_binding_passed_runner_not_preflighted"
    assert report.next_permitted_stage == NEXT_STAGE
    assert report.provider_calls == report.gpu_jobs == report.empirical_rows == 0
    assert not report.credential_lookup_attempted
    assert not report.model_client_constructed
    assert not report.runner_implemented
    assert not report.execution_authorized
    assert not report.single_stage_32k_allowed
    assert not report.capability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.production_contribution == 0


def test_v26_108_dual_build_is_byte_identical(
    static_built: tuple[Path, TwoStageStaticPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = static_built
    independent = tmp_path / "independent"
    independent_report = build(
        independent,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 12
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id


@pytest.fixture(scope="module")
def runner_built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, RunnerPreflightReport]:
    output = tmp_path_factory.mktemp("v26_109_two_stage_runner")
    report = build_runner_preflight(
        output,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    return output, report


def test_v26_109_replays_complete_v108_lineage_before_profile_or_client(
    runner_built: tuple[Path, RunnerPreflightReport],
) -> None:
    output, report = runner_built
    audit = RunnerSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )
    counts: dict[str, int] = {}
    for item in audit.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert audit.replayed_file_count == audit.replay_pass_count == 1900
    assert counts == {
        "v26_108_transitive_source": 1884,
        "v26_108_output": 12,
        "v26_109_implementation": 4,
    }
    assert audit.replay_before_profile_parsing
    assert audit.replay_before_credential_lookup
    assert audit.replay_before_client_construction
    assert not audit.credential_lookup_attempted
    assert not audit.real_model_client_constructed
    assert audit.provider_calls == audit.gpu_jobs == 0
    assert report.source_replay_audit_id == audit.audit_id


def test_v26_109_direct_fixture_closes_stage1_stage2_and_verifier(
    runner_built: tuple[Path, RunnerPreflightReport],
) -> None:
    output, _ = runner_built
    contract = TwoStageRunnerContract.model_validate_json(
        (output / "execution_contract.json").read_text()
    )
    fixture = RunnerFixtureAudit.model_validate_json(
        (output / "runner_fixture_audit.json").read_text()
    )

    assert contract.runner_implemented
    assert contract.stage_two_provider_call_upper_bound == 0
    assert contract.exact_request_completion_bound_tokens == 16384
    assert contract.rollout_upper_bound_tokens == 260000
    assert fixture.job_count == fixture.completed_count == 32
    assert fixture.stage_one_logical_request_count == 256
    assert fixture.stage_one_scripted_provider_call_count == 256
    assert fixture.stage_two_commit_count == 224
    assert fixture.stage_two_provider_call_count == 0
    assert fixture.public_observation_count == 192
    assert fixture.dynamic_certificate_count == 256
    assert fixture.exact_request_certificate_count == 256
    assert fixture.resource_certificate_count == 256
    assert fixture.verifier_v3_pass_count == 32
    assert fixture.independent_validity_pass_count == 32
    assert fixture.mechanism_score_pass_count == 32
    assert fixture.raw_execution_count == 32
    assert fixture.raw_provider_artifact_count == 256
    assert fixture.fixture_file_count == 288
    assert fixture.private_reasoning_payload_count == fixture.empirical_rows == 0
    assert all(item.compiler_semantic_projection_exact for item in fixture.rows)
    assert all(item.compiler_final_answer_exact for item in fixture.rows)
    assert all(item.verifier_v3_replay_passed for item in fixture.rows)
    assert all(item.reversible_commit_passed for item in fixture.rows)


def test_v26_109_client_usage_and_model_failure_boundaries(
    runner_built: tuple[Path, RunnerPreflightReport],
) -> None:
    output, _ = runner_built
    client = ClientRequestBindingAudit.model_validate_json(
        (output / "client_request_binding_audit.json").read_text()
    )
    usage = ProviderUsageFixtureAudit.model_validate_json(
        (output / "provider_usage_fixture_audit.json").read_text()
    )
    failures = ModelFailureClassificationAudit.model_validate_json(
        (output / "model_failure_classification_audit.json").read_text()
    )

    assert client.exact_model == "deepseek-v4-flash"
    assert client.exact_max_tokens == 16384
    assert client.exact_thinking_type == "enabled"
    assert client.fallback_routes == client.model_discovery_calls == 0
    assert client.stage_two_provider_calls == client.real_provider_calls == 0
    assert usage.admitted_completion_usage_values == (16384, 16385)
    assert usage.rejected_completion_usage_value == 16386
    assert usage.one_token_margin_charged_without_clipping
    assert not usage.one_token_length_failure_reclassified
    assert usage.two_or_more_excess_instrument_failure
    assert usage.rescue_blocked_after_instrument_failure
    assert failures.model_result_control_count == 9
    assert failures.instrument_failure_control_count == 0
    assert failures.historical_terminal_reclassification_count == 0
    assert {item.observed_terminal for item in failures.rows} == {"model_result"}


def test_v26_109_recovery_and_destructive_controls_fail_closed(
    runner_built: tuple[Path, RunnerPreflightReport],
) -> None:
    output, _ = runner_built
    recovery = PrecallRecoveryAudit.model_validate_json(
        (output / "precall_recovery_audit.json").read_text()
    )
    destructive = RunnerDestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )

    assert recovery.complete_raw_recovery_passed
    assert recovery.complete_raw_recovery_provider_calls == 0
    assert recovery.complete_raw_recovery_byte_identical
    assert recovery.orphan_provider_artifact_rejected
    assert recovery.oversized_prompt_rejected_before_provider_call
    assert recovery.reused_prepared_request_rejected
    assert recovery.wrong_request_kind_or_phase_rejected
    assert recovery.insufficient_remaining_budget_rejected
    assert recovery.stage_two_client_construction_count == 0
    assert recovery.stage_two_provider_call_count == 0
    assert destructive.mutation_count == destructive.rejection_count == 30
    assert destructive.unauthorized_provider_call_count == 0
    assert destructive.stage_two_provider_call_count == 0
    assert all(item.observed_rejection for item in destructive.mutation_results)
    assert all(item.provider_calls_before_rejection == 0 for item in destructive.mutation_results)


def test_v26_109_report_authorizes_only_exact_engineering_calibration(
    runner_built: tuple[Path, RunnerPreflightReport],
) -> None:
    _, report = runner_built

    assert report.status == "runner_preflight_passed_execution_not_started"
    assert report.next_permitted_stage == RUNNER_NEXT_STAGE
    assert report.runner_implemented
    assert report.runner_preflight_passed
    assert report.execution_authorized
    assert not report.execution_started
    assert report.real_provider_calls == report.stage_two_provider_calls == 0
    assert report.gpu_jobs == report.empirical_rows == 0
    assert not report.credential_lookup_attempted
    assert not report.real_model_client_constructed
    assert not report.capability_execution_authorized
    assert not report.state_mapping_authorized
    assert not report.single_stage_32k_allowed
    assert report.production_contribution == 0


def test_v26_109_dual_build_is_byte_identical(
    runner_built: tuple[Path, RunnerPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = runner_built
    independent = tmp_path / "independent_runner"
    independent_report = build_runner_preflight(
        independent,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 10
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
