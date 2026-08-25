from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_153_rebuild")
    preflight.build_fresh_reachability_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v26_153_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 19
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_153_frozen_reachability_population_is_not_reselected() -> None:
    frozen = preflight.FrozenReachabilityInputAudit.model_validate(
        _load(FORMAL_DIR / "frozen_reachability_input_audit.json")
    )
    catalog = preflight.TaskPackageCatalog.model_validate(
        _load(FORMAL_DIR / "reachability_task_package_catalog.json")
    )
    assert frozen.frozen_population_id == preflight.EXPECTED_OLD_REACHABILITY_POPULATION_ID
    assert frozen.task_count == catalog.task_package_count == 12
    assert len({(item.mechanism_id, item.tier) for item in frozen.bindings}) == 12
    assert frozen.model_exposure_count_before_preflight == 0
    assert frozen.capability_outcomes_used_for_selection is False
    assert frozen.verifier_passability_used_for_selection is False
    assert frozen.resource_values_used_for_selection is False
    assert frozen.fresh_source_reselection_count == 0
    assert frozen.cross_role_source_overlap_count == 0
    assert all(item.role == "reachability" for item in catalog.packages)
    assert all(item.frozen_input_audit_id == frozen.audit_id for item in catalog.packages)


def test_v26_153_path_support_detour_and_resource_closure() -> None:
    paths = preflight.PathCatalog.model_validate(
        _load(FORMAL_DIR / "reachability_path_catalog.json")
    )
    support = preflight.SupportClosureAudit.model_validate(
        _load(FORMAL_DIR / "support_closure_audit.json")
    )
    detours = preflight.ReachabilityDetourQualificationAudit.model_validate(
        _load(FORMAL_DIR / "detour_qualification_audit.json")
    )
    resource = preflight.ResourceContract.model_validate(
        _load(FORMAL_DIR / "reachability_resource_contract.json")
    )
    assert paths.path_count == 36
    assert paths.registered_state_count == 411
    assert paths.maximum_candidate_count == 63
    assert paths.maximum_prompt_utf8_bytes == 53_423
    assert paths.maximum_registered_path_tokens == 1_038_163
    assert support.candidate_event_count == support.typed_decision_count == 2_593
    assert support.failed_observation_event_count == 90
    assert support.failed_observation_baseline_call_count == 0
    assert support.progress_observation_baseline_call_count == 0
    assert (
        support.successful_no_progress_event_count
        == support.successful_no_progress_baseline_call_count
        == 482
    )
    assert support.ordinary_detour_event_count == 362
    assert support.typed_support_exit_count == 0
    assert detours.candidate_detour_count == 362
    assert detours.qualified_closed_row_count == 159
    assert detours.ordinary_replan_not_closed_count == 203
    assert detours.distinct_path_count == 36
    assert detours.maximum_primary_requests == 21
    assert detours.maximum_provider_calls == 23
    assert detours.maximum_transport_invocations == 24
    assert detours.maximum_prompt_utf8_bytes == 53_622
    assert detours.maximum_static_tokens == 1_092_469
    assert detours.minimum_rollout_headroom_tokens == 27_531
    assert resource.detour_qualification_audit_id == detours.audit_id
    assert resource.conservative_one_detour_upper_bound_tokens == 1_092_469
    assert resource.selected_rollout_headroom_tokens == 27_531


def test_v26_153_fixture_manifest_controls_and_transition_are_closed() -> None:
    manifest = preflight.ReachabilityManifest.model_validate(
        _load(FORMAL_DIR / "reachability_manifest.json")
    )
    outcome = preflight.OutcomeContract.model_validate(
        _load(FORMAL_DIR / "reachability_outcome_contract.json")
    )
    fixture = preflight.RunnerFixtureAudit.model_validate(
        _load(FORMAL_DIR / "reachability_runner_fixture_audit.json")
    )
    controls = preflight.RunnerControlAudit.model_validate(
        _load(FORMAL_DIR / "reachability_runner_control_audit.json")
    )
    destructive = preflight.DestructiveAudit.model_validate(
        _load(FORMAL_DIR / "destructive_audit.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    assert len(manifest.jobs) == len({item.job_id for item in manifest.jobs}) == 360
    assert len({item.seed for item in manifest.jobs}) == 360
    assert Counter(item.sampling_mode for item in manifest.jobs) == Counter(
        {"reachability_unconditional": 144, "reachability_conditioned": 216}
    )
    assert all(
        item.candidate_presentation_parent_id == manifest.frozen_input_audit_id
        for item in manifest.jobs
    )
    assert all(
        item.requested_path_id is None and item.public_path_condition is None
        for item in manifest.jobs
        if item.sampling_mode == "reachability_unconditional"
    )
    assert all(
        item.requested_path_id is not None and item.public_path_condition is not None
        for item in manifest.jobs
        if item.sampling_mode == "reachability_conditioned"
    )
    assert fixture.scripted_job_count == fixture.completed_job_count == 360
    assert fixture.first_action_interface_qualified_count == 360
    assert fixture.qualified_final_payload_count == 360
    assert fixture.joint_task_verifier_invocation_count == 360
    assert fixture.joint_qualified_valid_count == 360
    assert fixture.raw_recovery_pass_count == 360
    assert fixture.scripted_local_calls == 4_158
    assert fixture.action_payload_count == fixture.support_decision_count == 3_798
    assert fixture.public_observation_count == 3_438
    assert controls.control_count == controls.passed_count == 33
    assert destructive.mutation_count == destructive.rejected_count == 34
    assert outcome.static_route_condition_not_accepted_as_empirical_state is True
    assert outcome.state_mapping_eligibility_requires_qualified_valid_true is True
    assert outcome.state_mapping_rows == fixture.state_mapping_rows == 0
    assert transition.next_permitted_stage == preflight.NEXT_STAGE
    assert transition.exact_fresh_360_job_execution_authorized is True
    assert transition.state_mapping_contract_or_rows_authorized is False
