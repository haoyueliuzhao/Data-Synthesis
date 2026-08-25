from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_capability_runner_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_150_rebuild")
    preflight.build_fresh_capability_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v26_150_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 20
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_150_source_population_is_fresh_and_selected_first() -> None:
    population = preflight.FreshCapabilitySourcePopulation.model_validate(
        _load(FORMAL_DIR / "fresh_capability_source_population.json")
    )
    selection = preflight.SourceSelectionAudit.model_validate(
        _load(FORMAL_DIR / "source_selection_audit.json")
    )
    catalog = preflight.TaskPackageCatalog.model_validate(
        _load(FORMAL_DIR / "capability_task_package_catalog.json")
    )
    assert population.task_count == catalog.task_package_count == 12
    assert len({(item.mechanism_id, item.tier) for item in population.tasks}) == 12
    assert selection.tasks_selected_before_joint_contract_load is True
    assert selection.historical_validity_used_for_selection is False
    assert selection.verifier_passability_used_for_selection is False
    assert selection.effective_excluded_evidence_count == 27_323
    assert all(item.overlap_count == 0 for item in selection.freshness_channels)
    assert all(item.source_selection_audit_id == selection.audit_id for item in catalog.packages)


def test_v26_150_path_support_and_resource_closure() -> None:
    paths = preflight.PathCatalog.model_validate(_load(FORMAL_DIR / "capability_path_catalog.json"))
    support = preflight.SupportClosureAudit.model_validate(
        _load(FORMAL_DIR / "support_closure_audit.json")
    )
    resource = preflight.ResourceContract.model_validate(
        _load(FORMAL_DIR / "capability_resource_contract.json")
    )
    assert paths.path_count == 12
    assert paths.registered_state_count == 111
    assert paths.maximum_candidate_count == 63
    assert paths.maximum_prompt_utf8_bytes == 49_684
    assert paths.maximum_registered_path_tokens == 677_638
    assert support.candidate_event_count == support.typed_decision_count == 493
    assert support.failed_observation_event_count == 18
    assert support.failed_observation_baseline_call_count == 0
    assert support.progress_observation_baseline_call_count == 0
    assert (
        support.successful_no_progress_event_count
        == support.successful_no_progress_baseline_call_count
        == 28
    )
    assert support.ordinary_detour_event_count == 16
    assert support.typed_support_exit_count == 0
    assert resource.conservative_one_detour_upper_bound_tokens == 743_963
    assert resource.measured_maximum_reference_prompt_utf8_bytes <= 60_000
    assert resource.conservative_one_detour_upper_bound_tokens <= 1_120_000


def test_v26_150_fixture_manifest_controls_and_transition_are_closed() -> None:
    manifest = preflight.CapabilityManifest.model_validate(
        _load(FORMAL_DIR / "capability_manifest.json")
    )
    fixture = preflight.RunnerFixtureAudit.model_validate(
        _load(FORMAL_DIR / "capability_runner_fixture_audit.json")
    )
    controls = preflight.RunnerControlAudit.model_validate(
        _load(FORMAL_DIR / "capability_runner_control_audit.json")
    )
    destructive = preflight.DestructiveAudit.model_validate(
        _load(FORMAL_DIR / "destructive_audit.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    assert len(manifest.jobs) == len({item.job_id for item in manifest.jobs}) == 96
    assert len({item.seed for item in manifest.jobs}) == 96
    assert len({(item.mechanism_id, item.tier) for item in manifest.jobs}) == 12
    assert all(
        item.candidate_presentation_parent_id == manifest.source_selection_audit_id
        for item in manifest.jobs
    )
    assert fixture.scripted_job_count == fixture.completed_job_count == 96
    assert fixture.first_action_interface_qualified_count == 96
    assert fixture.qualified_final_payload_count == 96
    assert fixture.joint_task_verifier_invocation_count == 96
    assert fixture.joint_qualified_valid_count == 96
    assert fixture.raw_recovery_pass_count == 96
    assert fixture.scripted_local_calls == 984
    assert controls.control_count == controls.passed_count == 30
    assert destructive.mutation_count == destructive.rejected_count == 34
    assert transition.next_permitted_stage == preflight.NEXT_STAGE
    assert transition.exact_fresh_96_job_execution_authorized is True
    assert transition.reachability_identity_or_execution_authorized is False
    assert transition.state_mapping_authorized is False
