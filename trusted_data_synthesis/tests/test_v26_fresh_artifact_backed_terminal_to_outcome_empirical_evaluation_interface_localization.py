# ruff: noqa: E501
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_interface_localization as experiment,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_empirical_evaluation_interface_localization_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
FORMAL_ROOT = PACKAGE_ROOT / experiment.OUTPUT_DIR
AUDIT_PATH = FORMAL_ROOT / "external_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    output = tmp_path_factory.mktemp("v26-202") / "formal"
    report = experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=output,
        external_audit_path=AUDIT_PATH,
    )
    return output, report


def test_external_authorization_and_v201_freeze(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load(output / "external_authorization.json")
    )
    freeze = models.V201AuditFreeze.model_validate(_load(output / "v26_201_audit_freeze.json"))
    assert authorization.audit_sha256 == experiment.EXTERNAL_AUDIT_SHA256
    assert authorization.audit_byte_count == experiment.EXTERNAL_AUDIT_BYTES
    assert freeze.v201_decision_id == experiment.V201_DECISION_ID
    assert freeze.formal_file_count == 8
    assert freeze.exact_job_count == 192
    assert report["provider_calls"] == 0


def test_end_to_end_estimands_materialize_over_all_192_jobs(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    evaluation = models.ExactEmpiricalEvidenceSetEvaluation.model_validate(
        _load(output / "exact_empirical_evidence_set_evaluation.json")
    )
    assert evaluation.included_job_count == 192
    assert evaluation.excluded_job_count == 0
    assert evaluation.first_response_abi_invalid_count == 188
    assert evaluation.thinking_integrity_failure_count == 4
    assert evaluation.q_first_fraction == report["q_first_fraction"] == "0/192"
    assert (
        evaluation.q_bounded_correction_fraction
        == report["q_bounded_correction_fraction"]
        == "0/192"
    )
    assert evaluation.post_action_abi_denominator == 0
    assert evaluation.post_action_abi_conditional_semantic_fraction is None
    assert evaluation.frozen_v195_parent_validator_applied is True
    assert evaluation.frozen_v195_public_entrypoint_empirical_compatible is False


def test_all_first_prompts_reconstruct_against_actual_request_evidence(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    localization = models.FirstResponseInterfaceLocalization.model_validate(
        _load(output / "first_response_interface_localization.json")
    )
    assert localization.exact_first_prompt_count == 192
    assert localization.prompt_hash_match_count == 192
    assert localization.persisted_envelope_count == 188
    assert localization.missing_envelope_thinking_terminal_count == 4
    assert localization.prepared_request_identity_match_count == 188
    assert localization.response_abi_missing_explicit_action_id_count == 192
    assert all(
        item.prompt_sha256 == item.actual_request_sha256 for item in localization.prompt_rows
    )
    assert sum(item.persisted_envelope_present for item in localization.prompt_rows) == 188


def test_visible_answer_and_operation_schemas_explain_dominant_shapes(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    localization = models.FirstResponseInterfaceLocalization.model_validate(
        _load(output / "first_response_interface_localization.json")
    )
    assert localization.response_exact_answer_schema_match_count == 167
    assert localization.response_exact_operation_output_schema_match_count == 167
    assert localization.response_exact_answer_or_operation_match_count == 167
    assert localization.dominant_difference_higher_ref_count == 128
    assert localization.value_only_count == 39
    assert localization.structural_competing_schema_overlap_confirmed is True
    assert localization.causal_attribution_proven is False
    assert report["response_exact_answer_or_operation_match_count"] == 167
    sources = {item.field_name: item for item in localization.field_sources}
    assert sources["difference"].actual_response_count == 128
    assert sources["higher_ref"].actual_response_count == 128
    assert sources["value"].actual_response_count == 39
    assert all(
        sources[name].source_classification == "task_answer_or_operation_output"
        for name in ("difference", "higher_ref", "value")
    )
    assert sources["action_id"].action_abi_prompt_count == 0
    assert sources["action_id"].candidate_representation_prompt_count == 192


def test_destructive_controls_and_transition_remain_closed(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    destructive = models.DestructiveAudit.model_validate(_load(output / "destructive_audit.json"))
    decision = models.Decision.model_validate(_load(output / "decision.json"))
    transition = models.Transition.model_validate(_load(output / "prospective_transition.json"))
    assert destructive.attack_count == destructive.rejection_count == 8
    assert destructive.accepted_attack_count == 0
    assert decision.q_first_fraction == decision.q_bounded_correction_fraction == "0/192"
    assert decision.post_action_abi_conditional_capability is None
    assert transition.next_decision == models.NEXT_DECISION
    assert transition.provider_execution_authorized is False
    assert transition.full_192_job_rerun_authorized is False
    assert transition.historical_payload_adaptation_authorized is False


def test_empty_directory_rebuild_is_byte_identical(
    built: tuple[Path, dict[str, Any]],
    tmp_path: Path,
) -> None:
    first, _ = built
    second = tmp_path / "rebuild"
    experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=second,
        external_audit_path=AUDIT_PATH,
    )
    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_source_has_no_provider_execution_or_historical_adapter() -> None:
    source = inspect.getsource(experiment)
    assert "StageOneProspectiveThinkingJsonClient" not in source
    assert ".invoke(" not in source
    assert "execute_job(" not in source
    assert "evaluate_fresh_evidence_set(" not in source
    assert "historical response adaptation is forbidden" in source
    assert '"provider_calls": 0' in source
