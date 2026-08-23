from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_kernel_scalability_design as design,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / design.OUTPUT_DIR
PREDECESSOR_DIR = PACKAGE_ROOT / design.PREDECESSOR_DIR


def test_role_kernel_scalability_design_rebuild_is_byte_identical(
    tmp_path: Path,
) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = design.build_design(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=rebuilt_dir,
    )
    formal = design.RoleKernelScalabilityDesignReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "role_scalability_design_passed"
    assert report.frozen_role_source_task_count == 24
    assert report.full_mechanism_path_count == 48
    assert report.selected_scalability_candidate == "S1_lossless_compact"
    assert report.role_task_package_count == 0
    assert report.role_manifest_count == 0
    assert report.role_job_count == 0
    assert report.role_runner_count == 0
    assert report.provider_calls == 0
    assert report.next_permitted_stage == design.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_full_mechanism_census_and_static_selection_are_closed() -> None:
    source = design.SourceReplayAudit.model_validate_json(
        (FORMAL_DIR / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    census = design.RoleSupportComplexityCensus.model_validate_json(
        (FORMAL_DIR / "role_support_complexity_census.json").read_text(encoding="utf-8")
    )
    compact = design.CompactProjectionProtocol.model_validate_json(
        (FORMAL_DIR / "compact_projection_protocol.json").read_text(encoding="utf-8")
    )
    s0 = design.ScalabilityCandidate.model_validate_json(
        (FORMAL_DIR / "scalability_candidate_s0.json").read_text(encoding="utf-8")
    )
    s1 = design.ScalabilityCandidate.model_validate_json(
        (FORMAL_DIR / "scalability_candidate_s1.json").read_text(encoding="utf-8")
    )
    transition = design.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    destructive = design.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == 3165
    assert census.diagnostic_path_count == 48
    assert census.evaluated_mechanism_count == 4
    assert census.frozen_kernel_compatible_path_count == 18
    assert census.frozen_kernel_incompatible_path_count == 30
    assert census.prompt_ceiling_failure_count == 4
    assert census.primary_request_limit_failure_count == 26
    assert census.provider_call_limit_failure_count == 26
    assert census.rollout_bound_failure_count == 30
    assert census.maximum_candidate_count == 63
    assert census.maximum_s0_prompt_utf8_bytes == 86_161
    assert census.maximum_s1_prompt_utf8_bytes == 54_569
    assert census.maximum_primary_request_count == 20
    assert census.maximum_provider_call_count == 22
    assert census.maximum_s0_static_path_upper_bound_tokens == 1_276_468
    assert census.maximum_s1_static_path_upper_bound_tokens == 1_037_084
    assert compact.state_control_count == 522
    assert compact.exact_state_reconstruction_count == 522
    assert s0.prompt_ceiling_bytes == 100_000
    assert s0.rollout_upper_bound_tokens == 1_300_000
    assert s1.prompt_ceiling_bytes == 60_000
    assert s1.rollout_upper_bound_tokens == 1_060_000
    assert transition.provider_calls_authorized is False
    assert transition.capability_or_reachability_execution_authorized is False
    assert transition.kernel_and_role_identity_chain_preflight_authorized is True
    assert destructive.mutation_count == destructive.rejection_count == 18
