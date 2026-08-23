from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_rematerialization as v26_118,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_runner_preflight as v26_119,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT


def _build_v26_118(output_dir: Path) -> v26_118.SemanticActionRematerializationReport:
    return v26_118.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )


def _build_v26_119(output_dir: Path) -> v26_119.SemanticActionRunnerPreflightReport:
    return v26_119.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )


def test_v26_118_candidate_authority_and_identity_chain(tmp_path: Path) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build_v26_118(formal_dir)
    independent = _build_v26_118(independent_dir)
    assert formal == independent
    for path in formal_dir.iterdir():
        assert path.read_bytes() == (independent_dir / path.name).read_bytes()
    candidate = json.loads((formal_dir / "candidate_space_authority_audit.json").read_text())
    resource = json.loads((formal_dir / "semantic_action_resource_contract.json").read_text())
    cross = json.loads((formal_dir / "cross_artifact_binding_audit.json").read_text())
    assert candidate["state_count"] == 324
    assert candidate["total_visible_candidate_count"] == 1095
    assert candidate["legal_distractor_count"] == 771
    assert candidate["multi_candidate_state_count"] == 228
    assert candidate["maximum_candidate_count"] == 8
    assert candidate["order_permutation_semantic_match_count"] == 972
    assert candidate["id_free_reference_policy_match_count"] == 324
    assert candidate["opaque_id_substitution_pass_count"] == 324
    assert candidate["opaque_id_static_decision_match_count"] == 324
    assert candidate["opaque_id_canonical_commit_match_count"] == 324
    assert candidate["production_host_alias_normalization_count"] == 0
    assert candidate["candidate_builder_scoped_function_audit_count"] == 7
    assert candidate["forbidden_candidate_builder_symbol_read_count"] == 0
    assert candidate["dropped_distractor_mutation_rejected"]
    assert candidate["correct_only_candidate_mutation_rejected"]
    assert resource["maximum_static_complete_path_bound_tokens"] == 366495
    assert resource["rollout_upper_bound_tokens"] == 400000
    assert resource["minimum_static_headroom_tokens"] == 33505
    assert resource["maximum_abi_rescue_calls_per_job"] == 1
    assert resource["maximum_semantic_recovery_calls_per_job"] == 1
    assert cross["task_identity_overlap_with_v26_112"] == 0
    assert cross["path_identity_overlap_with_v26_112"] == 0
    assert cross["job_identity_overlap_with_v26_112"] == 0
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.next_permitted_stage == "semantic_action_runner_preflight_only"


def test_v26_119_runner_and_separate_recovery_channels(tmp_path: Path) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build_v26_119(formal_dir)
    independent = _build_v26_119(independent_dir)
    assert formal == independent
    for path in formal_dir.iterdir():
        assert path.read_bytes() == (independent_dir / path.name).read_bytes()
    fixture = json.loads((formal_dir / "runner_fixture_audit.json").read_text())
    recovery = json.loads((formal_dir / "semantic_recovery_control_audit.json").read_text())
    certificates = json.loads((formal_dir / "certificate_usage_recovery_audit.json").read_text())
    outcomes = json.loads((formal_dir / "outcome_measurement_contract.json").read_text())
    transition = json.loads((formal_dir / "prospective_transition_contract.json").read_text())
    assert fixture["stage_one_scripted_provider_call_count"] == 256
    assert fixture["exact_four_field_payload_count"] == 224
    assert fixture["semantic_choice_count"] == 224
    assert fixture["stage_two_commit_count"] == 224
    assert fixture["public_observation_count"] == 192
    assert fixture["replay_v3_pass_count"] == 32
    assert fixture["independent_validity_pass_count"] == 32
    assert fixture["mechanism_success_count"] == 32
    assert fixture["stage_two_provider_call_count"] == 0
    assert recovery["abi_rescue_attempt_count"] == 1
    assert recovery["first_choice_semantic_rejection_count"] == 1
    assert recovery["semantic_recovery_attempt_count"] == 1
    assert recovery["recovery_selected_different_action_count"] == 1
    assert recovery["recovery_commit_count"] == 1
    assert recovery["recovery_public_progress_count"] == 1
    assert recovery["completed_after_recovery_count"] == 1
    assert recovery["abi_count_before_semantic_recovery"] == 1
    assert recovery["semantic_count_before_semantic_recovery"] == 1
    assert recovery["correct_action_id_exposed_count"] == 0
    assert certificates["complete_raw_recovery_byte_identical"]
    assert certificates["orphan_provider_artifact_rejected"]
    assert certificates["completion_16385_admitted_and_charged"]
    assert certificates["completion_16386_instrument_failure"]
    assert outcomes["compare_as_same_distribution_with_v26_114"] is False
    assert outcomes["first_choice_failure_retained_after_eventual_success"]
    assert transition["exact_manifest_execution_authorized"]
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.next_permitted_stage == "semantic_action_calibration_execution_only"
