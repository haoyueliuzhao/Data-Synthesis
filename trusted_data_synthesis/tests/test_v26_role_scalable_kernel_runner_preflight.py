from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_scalable_kernel_runner_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR
PREDECESSOR_DIR = PACKAGE_ROOT / preflight.PREDECESSOR_DIR


def test_v26_131_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=rebuilt_dir,
    )
    formal = preflight.RoleScalableKernelRunnerPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "blocked_by_dynamic_interaction_capacity"
    assert report.role_task_package_count == 24
    assert report.role_path_count == 48
    assert report.role_job_count == 456
    assert report.registered_reference_path_pass_count == 48
    assert report.dynamic_legal_detour_failure_count == 1
    assert report.provider_calls == 0
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_v26_131_identity_chain_and_dynamic_boundary_are_closed() -> None:
    source = preflight.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    kernel = preflight.RoleScalableKernel.model_validate_json(
        (FORMAL_DIR / "role_scalable_kernel.json").read_text(encoding="utf-8")
    )
    tasks = preflight.RoleTaskPackageCatalog.model_validate_json(
        (FORMAL_DIR / "role_task_package_catalog.json").read_text(encoding="utf-8")
    )
    paths = preflight.RolePathCatalog.model_validate_json(
        (FORMAL_DIR / "role_path_catalog.json").read_text(encoding="utf-8")
    )
    reconciliation = preflight.DeepReconciliationCompilerAudit.model_validate_json(
        (FORMAL_DIR / "deep_reconciliation_compiler_audit.json").read_text(encoding="utf-8")
    )
    chain = preflight.RoleIdentityChain.model_validate_json(
        (FORMAL_DIR / "role_identity_chain.json").read_text(encoding="utf-8")
    )
    reference = preflight.ReferenceRunnerFixtureAudit.model_validate_json(
        (FORMAL_DIR / "reference_runner_fixture_audit.json").read_text(encoding="utf-8")
    )
    dynamic = preflight.DynamicInteractionStressAudit.model_validate_json(
        (FORMAL_DIR / "dynamic_interaction_stress_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == 3177
    assert kernel.compact_projection_is_model_visible_generation_condition is True
    assert kernel.static_semantic_losslessness_established is True
    assert kernel.model_behavior_equivalence_established is False
    assert len(tasks.packages) == 24
    assert (
        Counter(item.deep_reconciliation_formal_compiler_used for item in tasks.packages)[True] == 4
    )
    assert len(paths.paths) == 48
    assert reconciliation.source_task_count == 4
    assert reconciliation.registered_path_count == 8
    assert len(chain.capability_manifest.jobs) == 96
    assert len(chain.reachability_manifest.jobs) == 360
    assert reference.semantic_action_primary_count == 522
    assert reference.total_primary_request_count == 570
    assert reference.public_observation_count == 474
    assert dynamic.maximum_candidate_state_count == 63
    assert dynamic.maximum_blocked_action_count == 2
    assert dynamic.detour_maximum_prompt_utf8_bytes == 54_708
    assert dynamic.reference_primary_request_count == 20
    assert dynamic.detour_primary_request_count == 21
    assert dynamic.detour_provider_calls_with_both_recoveries == 23
    assert dynamic.detour_transport_inclusive_invocations == 24
    assert dynamic.detour_static_path_upper_bound_tokens == 1_090_412
    assert dynamic.detour_rollout_excess_tokens == 30_412
    assert dynamic.denied_request_provider_calls == 0
    assert transition.provider_calls_authorized is False
    assert transition.s1_model_visible_representation_qualification_authorized is False
    assert transition.resource_capacity_redesign_only_authorized is True
    assert destructive.mutation_count == destructive.rejection_count == 24
