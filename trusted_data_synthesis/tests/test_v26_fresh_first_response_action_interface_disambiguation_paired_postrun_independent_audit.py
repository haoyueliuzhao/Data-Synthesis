# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_postrun_independent_audit as experiment,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_postrun_independent_audit_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
FORMAL_ROOT = PACKAGE_ROOT / experiment.OUTPUT_DIR
AUDIT_PATH = FORMAL_ROOT / "external_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    source = _load(FORMAL_ROOT / "source_identity.json")
    target = tmp_path_factory.mktemp("v26-205") / "audit"
    experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=target,
        external_audit_path=AUDIT_PATH,
        source_identity=(source["source_commit"], source["source_tree"]),
    )
    return target


def test_external_authorization_and_v204_execution_freeze_are_exact() -> None:
    authorization = models.ExternalPostrunAuditAuthorization.model_validate(
        _load(FORMAL_ROOT / "external_authorization.json")
    )
    freeze = models.V204ExecutionFreeze.model_validate(
        _load(FORMAL_ROOT / "v26_204_execution_freeze.json")
    )
    assert authorization.audit_sha256 == experiment.EXTERNAL_AUDIT_SHA256
    assert authorization.audit_byte_count == experiment.EXTERNAL_AUDIT_BYTES
    assert authorization.provider_calls_authorized == 0
    assert authorization.full_repaired_192_job_execution_authorized is False
    assert freeze.execution_artifact_manifest_id == experiment.V204_ARTIFACT_MANIFEST_ID
    assert freeze.execution_artifact_root == experiment.V204_ARTIFACT_ROOT
    assert freeze.execution_source_commit == experiment.V204_SOURCE_COMMIT
    assert freeze.execution_source_tree == experiment.V204_SOURCE_TREE
    assert freeze.formal_directory_file_count == 108
    assert freeze.formal_directory_total_byte_count == 276_582


def test_actual_byte_and_request_identity_reconstruction_close() -> None:
    byte_audit = models.ArtifactByteReconstructionAudit.model_validate(
        _load(FORMAL_ROOT / "artifact_byte_reconstruction_audit.json")
    )
    request_audit = models.RequestIdentityAudit.model_validate(
        _load(FORMAL_ROOT / "request_identity_and_execution_geometry_audit.json")
    )
    assert byte_audit.actual_path_match_count == 107
    assert byte_audit.actual_sha256_match_count == 107
    assert byte_audit.actual_byte_count_match_count == 107
    assert byte_audit.independently_recomputed_artifact_root == experiment.V204_ARTIFACT_ROOT
    assert byte_audit.saved_observation_used_as_outcome_oracle is False
    assert request_audit.reconstructed_request_body_hash_match_count == 24
    assert request_audit.telemetry_request_hash_match_count == 24
    assert request_audit.job_request_cell_arm_parent_match_count == 24
    assert request_audit.paired_semantic_parent_mismatch_count == 0
    assert request_audit.stage_one_call_count == 24
    assert request_audit.stage_two_call_count == request_audit.retry_count == 0
    assert request_audit.http_success_count == request_audit.exact_model_match_count == 24
    assert request_audit.thinking_present_count == request_audit.complete_usage_count == 24


def test_raw_only_independent_observation_reconstruction_is_exact() -> None:
    catalog = models.IndependentObservationCatalog.model_validate(
        _load(FORMAL_ROOT / "independent_observation_catalog.json")
    )
    assert len(catalog.rows) == 24
    assert catalog.saved_response_match_count == catalog.saved_observation_match_count == 24
    assert catalog.parent_chain_match_count == 24
    assert catalog.frozen_parser_source_match is True
    assert catalog.frozen_grammar_source_match is True
    assert catalog.repair_four_action_named_field_count == 12
    assert catalog.repair_invalid_decision_kind_count == 1
    failures = [
        row for row in catalog.rows if row.arm == "R" and not row.exact_four_field_abi_valid
    ]
    assert len(failures) == 1
    failure = failures[0]
    assert failure.public_response_shape == (
        "action_id",
        "decision_kind",
        "protocol",
        "state_id",
    )
    assert failure.action_reference_valid is None
    assert failure.state_binding_valid is None
    assert failure.runtime_step_committed is None
    assert failure.parser_rejection_reason == (
        "SemanticActionResponseRejection:canonical_action_not_exact_four_field_grammar"
    )
    raw = _load(PACKAGE_ROOT / experiment.V204_DIR / "raw" / f"job_{failure.ordinal:03d}.json")
    assert raw["public_response_object"]["decision_kind"] == "revise_selector"
    assert failure.historical_payload_adaptation is False
    assert failure.parser_relaxation is False


def test_independent_paired_result_and_g0_g8_match_saved_outputs() -> None:
    evaluation = models.IndependentPairedEvaluation.model_validate(
        _load(FORMAL_ROOT / "independent_paired_calibration_evaluation.json")
    )
    gates = models.IndependentGateReconstruction.model_validate(
        _load(FORMAL_ROOT / "independent_online_gate_reconstruction.json")
    )
    assert evaluation.control_abi_success_count == 0
    assert evaluation.repair_abi_success_count == 11
    assert evaluation.control_reference_state_valid_count == 0
    assert evaluation.repair_reference_state_valid_count == 11
    assert evaluation.control_answer_schema_exact_count == 10
    assert evaluation.control_operation_output_exact_count == 10
    assert evaluation.paired_repair_only_abi_success_count == 11
    assert evaluation.paired_control_only_abi_success_count == 0
    assert evaluation.delta_abi_numerator == 11
    assert sorted(evaluation.stratum_repair_reference_state_valid_counts.values()) == [2, 3, 3, 3]
    assert evaluation.saved_paired_evaluation_exact_match is True
    assert gates.all_gates_passed is True
    assert all(getattr(gates, f"g{index}_passed") for index in range(9))
    assert gates.saved_gate_evaluation_exact_match is True
    assert gates.exact_mcnemar_supplementary_two_sided_p == "0.0009765625"
    assert gates.capability_estimate is None


def test_minimal_authorized_negative_controls_all_reject() -> None:
    audit = models.NegativeControlAudit.model_validate(
        _load(FORMAL_ROOT / "negative_control_audit.json")
    )
    assert audit.control_count == audit.rejected_control_count == 5
    assert audit.accepted_control_count == 0
    assert {item.control_name for item in audit.controls} == {
        "changed_raw_response_bytes",
        "cross_arm_parent_binding",
        "missing_job",
        "duplicate_job",
        "revise_selector_posthoc_adaptation",
    }
    assert all(item.rejected and not item.accepted for item in audit.controls)


def test_decision_and_transition_preserve_scientific_boundary() -> None:
    decision = models.PostrunIndependentAuditDecision.model_validate(
        _load(FORMAL_ROOT / "decision.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load(FORMAL_ROOT / "prospective_transition.json")
    )
    assert decision.v204_actual_artifact_authority == "independently_reconstructed"
    assert decision.v204_scientific_result == "accepted_as_scoped"
    assert decision.composite_repair_effect_supported is True
    assert decision.individual_submechanism_effect_identified is False
    assert decision.full_program_capability_instantiated is False
    assert decision.provider_calls == decision.credential_lookups == 0
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_calls_authorized == 0
    assert transition.full_repaired_192_job_execution_authorized is False
    assert transition.parser_relaxation_authorized is False
    assert transition.historical_response_adaptation_authorized is False
    assert transition.qa_mapper_state_contribution_vtdo_authorized is False


def test_formal_artifact_manifest_and_empty_rebuild_are_byte_exact(rebuilt: Path) -> None:
    artifact = models.ArtifactManifest.model_validate(_load(FORMAL_ROOT / "artifact_manifest.json"))
    actual_files = tuple(sorted(path for path in FORMAL_ROOT.rglob("*") if path.is_file()))
    assert artifact.file_count == 13
    assert len(actual_files) == 14
    assert {item.relative_path for item in artifact.members} == {
        path.relative_to(FORMAL_ROOT).as_posix()
        for path in actual_files
        if path.name != "artifact_manifest.json"
    }
    for member in artifact.members:
        path = FORMAL_ROOT / member.relative_path
        assert path.stat().st_size == member.byte_count
        assert hashlib.sha256(path.read_bytes()).hexdigest() == member.sha256
    rebuilt_files = tuple(sorted(path for path in rebuilt.rglob("*") if path.is_file()))
    assert {path.relative_to(rebuilt).as_posix() for path in rebuilt_files} == {
        path.relative_to(FORMAL_ROOT).as_posix() for path in actual_files
    }
    for rebuilt_path in rebuilt_files:
        formal_path = FORMAL_ROOT / rebuilt_path.relative_to(rebuilt)
        assert rebuilt_path.read_bytes() == formal_path.read_bytes()


def test_source_contains_no_v204_outcome_or_gate_oracle_call() -> None:
    source = inspect.getsource(experiment)
    assert "v204._response_and_observation" not in source
    assert "v204._gate_evaluation" not in source
    assert "v203_models.make_paired_evaluation" not in source
    assert "client_factory" not in source
    assert "credential_loader" not in source
