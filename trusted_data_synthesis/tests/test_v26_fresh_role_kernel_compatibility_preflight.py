from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR
PREDECESSOR_DIR = PACKAGE_ROOT / preflight.PREDECESSOR_DIR


def test_role_kernel_compatibility_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt_dir = tmp_path / "rebuilt"
    report = preflight.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=rebuilt_dir,
        source_frame_input=FORMAL_DIR / "fresh_source_sampling_frame.json",
    )
    formal = preflight.RoleKernelCompatibilityPreflightReport.model_validate_json(
        (FORMAL_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert report == formal
    assert report.status == "role_population_kernel_incompatible"
    assert report.fresh_role_source_task_count == 24
    assert report.diagnostic_path_count == 12
    assert report.incompatible_path_count == 8
    assert report.prompt_ceiling_failure_count == 4
    assert report.request_limit_failure_count == 6
    assert report.rollout_bound_failure_count == 8
    assert report.role_task_package_count == 0
    assert report.role_manifest_count == 0
    assert report.role_job_count == 0
    assert report.role_runner_count == 0
    assert report.provider_calls == 0
    assert report.next_permitted_stage == preflight.NEXT_STAGE
    assert sorted(path.name for path in rebuilt_dir.iterdir()) == sorted(
        path.name for path in FORMAL_DIR.iterdir()
    )
    for formal_path in FORMAL_DIR.iterdir():
        assert formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()


def test_role_kernel_failure_blocks_manifest_and_provider_authority() -> None:
    compatibility = preflight.KernelCompatibilityAudit.model_validate_json(
        (FORMAL_DIR / "kernel_compatibility_audit.json").read_text(encoding="utf-8")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate_json(
        (FORMAL_DIR / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    destructive = preflight.DestructiveAudit.model_validate_json(
        (FORMAL_DIR / "destructive_audit.json").read_text(encoding="utf-8")
    )
    assert compatibility.compatible_path_count == 4
    assert compatibility.incompatible_path_count == 8
    assert compatibility.role_manifest_count == 0
    assert compatibility.role_job_count == 0
    assert compatibility.role_provider_calls == 0
    assert transition.provider_calls_authorized is False
    assert transition.capability_or_reachability_execution_authorized is False
    assert (
        transition.role_task_package_contract_manifest_job_or_runner_materialization_authorized
        is False
    )
    assert destructive.mutation_count == destructive.rejection_count == 12
