from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_scalable_kernel_runner_preflight as predecessor,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR
PREDECESSOR_DIR = PACKAGE_ROOT / preflight.PREDECESSOR_DIR


def test_v26_132_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=rebuilt_dir,
    )
    formal = preflight.BoundedDynamicRolePreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report.model_dump(mode="json") == formal.model_dump(mode="json")
    assert report.status == "bounded_dynamic_interaction_preflight_passed"
    assert report.role_task_package_count == 24
    assert report.role_path_count == 48
    assert report.role_job_count == 456
    assert report.registered_reference_path_pass_count == 48
    assert report.dynamic_candidate_check_count == 2_567
    assert report.eligible_one_detour_pass_count == 180
    assert report.provider_calls == 0
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_132_bounded_dynamic_class_and_fresh_identity_chain_are_closed() -> None:
    source = preflight.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    policy = preflight.OrdinaryDetourPolicy.model_validate_json(
        (FORMAL_DIR / "ordinary_detour_policy.json").read_text(encoding="utf-8")
    )
    envelope = preflight.DynamicTrajectoryEnvelopeAudit.model_validate_json(
        (FORMAL_DIR / "dynamic_trajectory_envelope_audit.json").read_text(encoding="utf-8")
    )
    resource = preflight.RoleScalableResourceContract.model_validate_json(
        (FORMAL_DIR / "bounded_dynamic_resource_contract.json").read_text(encoding="utf-8")
    )
    kernel = preflight.RoleScalableKernel.model_validate_json(
        (FORMAL_DIR / "bounded_dynamic_role_kernel.json").read_text(encoding="utf-8")
    )
    tasks = preflight.RoleTaskPackageCatalog.model_validate_json(
        (FORMAL_DIR / "role_task_package_catalog.json").read_text(encoding="utf-8")
    )
    paths = preflight.RolePathCatalog.model_validate_json(
        (FORMAL_DIR / "role_path_catalog.json").read_text(encoding="utf-8")
    )
    chain = preflight.RoleIdentityChain.model_validate_json(
        (FORMAL_DIR / "role_identity_chain.json").read_text(encoding="utf-8")
    )
    reference = preflight.ReferenceRunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "reference_runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    bounded = preflight.BoundedDynamicRunnerPreflightAudit.model_validate_json(
        (FORMAL_DIR / "bounded_dynamic_runner_preflight_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    old_tasks = predecessor.RoleTaskPackageCatalog.model_validate_json(
        (PREDECESSOR_DIR / "role_task_package_catalog.json").read_text(encoding="utf-8")
    )
    old_paths = predecessor.RolePathCatalog.model_validate_json(
        (PREDECESSOR_DIR / "role_path_catalog.json").read_text(encoding="utf-8")
    )
    old_chain = predecessor.RoleIdentityChain.model_validate_json(
        (PREDECESSOR_DIR / "role_identity_chain.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == 3_192
    assert policy.maximum_ordinary_detours == 1
    assert policy.ordinary_detour_classified_after_public_observation is True
    assert policy.ordinary_detour_requires_ordinary_replanning_closure is True
    assert Counter({item.outcome: item.count for item in envelope.outcome_counts}) == Counter(
        {
            "eligible_closed_no_progress": 180,
            "successful_no_selectable_state": 0,
            "successful_no_progress_route_not_closable": 252,
            "successful_progress": 774,
            "tool_not_successful": 1_361,
            "not_public_call": 0,
        }
    )
    assert envelope.candidate_check_count == 2_567
    assert envelope.eligible_path_count == 39
    assert envelope.maximum_one_detour_primary_requests == 21
    assert envelope.maximum_one_detour_provider_calls == 23
    assert envelope.maximum_one_detour_transport_invocations == 24
    assert envelope.maximum_one_detour_prompt_utf8_bytes == 54_768
    assert envelope.maximum_one_detour_static_tokens == 1_091_306
    assert resource.rollout_upper_bound_tokens == 1_120_000
    assert resource.selected_rollout_headroom_tokens == 28_694
    assert kernel.maximum_ordinary_detours == 1
    assert kernel.model_behavior_equivalence_established is False
    assert len(tasks.packages) == 24
    assert len(paths.paths) == 48
    assert len(chain.capability_manifest.jobs) == 96
    assert len(chain.reachability_manifest.jobs) == 360
    assert reference.semantic_action_primary_count == 522
    assert reference.total_primary_request_count == 570
    assert reference.public_observation_count == 474
    assert bounded.control_count == bounded.passed_control_count == 12
    assert bounded.eligible_one_detour_count == bounded.eligible_one_detour_pass_count == 180
    assert bounded.two_detour_primary_requests == 22
    assert bounded.two_detour_provider_calls == 24
    assert bounded.two_detour_transport_invocations == 25
    assert bounded.two_detour_prompt_utf8_bytes == 54_967
    assert bounded.two_detour_static_tokens == 1_145_727
    assert bounded.typed_second_detour_terminal.ordinary_detours_observed == 2
    assert bounded.typed_second_detour_terminal.later_provider_calls == 0
    assert (
        bounded.typed_second_detour_terminal.second_detour_model_proposal_already_observed is True
    )
    assert (
        bounded.typed_second_detour_terminal.second_detour_tool_observation_already_observed is True
    )

    assert {item.task_package_id for item in tasks.packages}.isdisjoint(
        item.task_package_id for item in old_tasks.packages
    )
    assert {item.path_id for item in paths.paths}.isdisjoint(
        item.path_id for item in old_paths.paths
    )
    new_jobs = chain.capability_manifest.jobs + chain.reachability_manifest.jobs
    old_jobs = old_chain.capability_manifest.jobs + old_chain.reachability_manifest.jobs
    assert {item.job_id for item in new_jobs}.isdisjoint(item.job_id for item in old_jobs)
    assert sorted(item.seed for item in new_jobs) == sorted(item.seed for item in old_jobs)
    assert transition.provider_calls_authorized is False
    assert transition.s1_model_visible_representation_qualification_execution_authorized is False
    assert transition.qualification_design_and_runner_preflight_only is True
    assert destructive.mutation_count == destructive.rejection_count == 24
