from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay import (  # noqa: E501
    AuthorityPreservingReplayContract,
    AuthorityPreservingVerifierQualificationReport,
    HistoricalVerifierDiagnostic,
    VerifierMutationAudit,
    build_authority_preserving_verifier_qualification,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
FAILURE_AUDIT = ARTIFACT_ROOT / "finance_v26_74_capability_reachability_failure_audit_v2_20260819"
CAPABILITY_RUN = ARTIFACT_ROOT / "finance_v26_71_capability_development_20260819"
CAPABILITY_TASKS = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
REACHABILITY_RUN = ARTIFACT_ROOT / "finance_v26_72_state_reachability_20260819"
REACHABILITY_TASKS = (
    ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
)
FORMAL = ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
RUN_ID = "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
DETAIL_FILES = (
    "destructive_mutation_audits.json",
    "historical_verifier_diagnostics.json",
    "replay_contract.json",
    "report.json",
)


def _build(output: Path) -> AuthorityPreservingVerifierQualificationReport:
    return build_authority_preserving_verifier_qualification(
        run_id=RUN_ID,
        failure_audit_dir=FAILURE_AUDIT,
        capability_run_dir=CAPABILITY_RUN,
        capability_task_source_dir=CAPABILITY_TASKS,
        reachability_run_dir=REACHABILITY_RUN,
        reachability_task_source_dir=REACHABILITY_TASKS,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_75_rebuild")
    _build(output)
    return output


def _load_list(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def test_v26_75_is_deterministic_and_matches_formal(
    rebuilt: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in DETAIL_FILES:
        assert (rebuilt / relative).read_bytes() == (duplicate / relative).read_bytes()
        assert (rebuilt / relative).read_bytes() == (FORMAL / relative).read_bytes()


def test_replay_contract_mirrors_authority_preserving_runtime(rebuilt: Path) -> None:
    contract = AuthorityPreservingReplayContract.model_validate_json(
        (rebuilt / "replay_contract.json").read_text(encoding="utf-8")
    )

    assert contract.replay_execution_order == (
        "identical_failed_action_gate",
        "public_postcompletion_gate",
        "public_tool_argument_gate",
        "public_terminal_verification_gate",
        "public_operation_gate",
        "finance_tool_runtime",
        "public_action_neutral_projection",
        "tool_output_contract",
        "canonical_json_semantic_comparison",
    )
    assert contract.public_operation_contract_required
    assert contract.public_action_neutral_repair_required
    assert contract.typed_terminal_target_required
    assert contract.model_repair_decision_retained
    assert not contract.historical_outcome_rescoring_permitted


def test_historical_diagnostics_preserve_non_replay_gates(rebuilt: Path) -> None:
    rows = _load_list(
        rebuilt / "historical_verifier_diagnostics.json",
        HistoricalVerifierDiagnostic,
    )

    assert len(rows) == 45
    assert Counter(item.role for item in rows) == {
        "capability_development": 14,
        "state_reachability": 31,
    }
    assert sum(item.historical_runtime_replay_passed for item in rows) == 27
    assert all(item.prospective_runtime_replay_passed for item in rows)
    assert all(item.non_replay_checks_identical for item in rows)
    candidates = tuple(item for item in rows if item.prospective_validity_candidate)
    assert len(candidates) == 15
    assert Counter((item.role, item.mechanism_id) for item in candidates) == {
        ("capability_development", "state_dependent_stopping"): 8,
        ("state_reachability", "context_conditioned_action"): 7,
    }
    assert all(not item.historical_validity_reclassified for item in rows)
    assert all(not item.historical_path_assignment_changed for item in rows)
    assert all(not item.creates_state_support for item in rows)


def test_destructive_mutation_matrix_fails_closed(rebuilt: Path) -> None:
    rows = _load_list(
        rebuilt / "destructive_mutation_audits.json",
        VerifierMutationAudit,
    )

    assert len(rows) == 108
    assert Counter(item.mutation_kind for item in rows) == {
        "environment_identity": 45,
        "result_payload": 45,
        "action_binding_payload": 18,
    }
    assert all(item.mutation_rejected and item.replay_failure_ids for item in rows)
    assert all(not item.historical_outcome_mutated for item in rows)
    environment = tuple(item for item in rows if item.mutation_kind == "environment_identity")
    assert all("environment_identity" in item.replay_failure_ids[0] for item in environment)
    payload = tuple(item for item in rows if item.mutation_kind != "environment_identity")
    assert all(
        any("replay_mismatch" in value for value in item.replay_failure_ids) for item in payload
    )


def test_qualification_authorizes_only_fresh_verifier_binding(rebuilt: Path) -> None:
    report = AuthorityPreservingVerifierQualificationReport.model_validate_json(
        (rebuilt / "report.json").read_text(encoding="utf-8")
    )

    assert report.completed_trajectory_count == 45
    assert report.authority_preserving_replay_pass_count == 45
    assert report.non_replay_check_identity_count == 45
    assert report.prospective_validity_candidate_count == 15
    assert report.destructive_mutation_reject_count == 108
    assert report.historical_validity_reclassification_count == 0
    assert report.historical_capability_valid_count == 4
    assert report.historical_reachability_valid_count == 21
    assert report.historical_admitted_state_count == 0
    assert report.historical_admitted_task_count == 0
    assert not report.historical_results_reclassified
    assert not report.historical_state_support_freeze_mutated
    assert report.next_permitted_stage == (
        "fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only"
    )
    assert report.production_contribution == report.api_call_count == report.gpu_job_count == 0


def test_contract_and_report_identity_mutations_fail_closed(rebuilt: Path) -> None:
    contract = json.loads((rebuilt / "replay_contract.json").read_text(encoding="utf-8"))
    contract["comparison_rule"] = "python_object_equality"
    with pytest.raises(ValidationError):
        AuthorityPreservingReplayContract.model_validate(contract)

    report = json.loads((rebuilt / "report.json").read_text(encoding="utf-8"))
    report["report_id"] = "finance_v26_authority_verifier_qualification:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        AuthorityPreservingVerifierQualificationReport.model_validate(report)
