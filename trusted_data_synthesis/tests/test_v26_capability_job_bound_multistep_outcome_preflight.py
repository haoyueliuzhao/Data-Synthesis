from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJobManifest,
    EmpiricalCapabilityOutcomeRow,
    JobBoundMultistepOutcomeContract,
    JobBoundRunnerContract,
    evaluate_empirical_capability_estimands,
    make_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_179_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_chain_binds_new_audit_and_freezes_v178() -> None:
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.V178PredecessorFreezeAudit.model_validate(
        _load("v178_predecessor_freeze_audit.json")
    )
    scope = models.V178ScopeNarrowingAudit.model_validate(_load("v178_scope_narrowing_audit.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 19_996
    assert authorization.audited_commit == build_module.AUDITED_COMMIT
    assert predecessor.predecessor_file_count == 14
    assert predecessor.independent_rebuild_match_count == 14
    assert predecessor.predecessor_mutation_count == 0
    assert predecessor.predecessor_decision == models.BLOCKED_PREDECESSOR_STAGE
    assert scope.strongest_outcome_interpretation == (
        "outcome_payload_fixture_and_denominator_geometry_closure"
    )
    assert scope.exact_scan_interpretation == (
        "complete_reference_prefix_component_candidate_acceptance_scan"
    )
    assert scope.empirical_outcome_row_count == 0
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_execution_authorized is False
    assert transition.independent_audit_required_before_execution_decision is True


def test_manifest_is_the_exact_32_by_6_job_set() -> None:
    manifest = CapabilityDevelopmentJobManifest.model_validate(
        _load("development_job_manifest.json")
    )
    audit = models.ExactJobSetAudit.model_validate(_load("exact_192_job_set_audit.json"))
    assert manifest.package_count * manifest.replica_count == 32 * 6 == manifest.job_count
    assert len(manifest.jobs) == len(manifest.expected_job_ids) == 192
    assert len({item.job_id for item in manifest.jobs}) == 192
    assert len({item.raw_namespace for item in manifest.jobs}) == 192
    assert len({item.result_namespace for item in manifest.jobs}) == 192
    assert manifest.expected_job_ids == tuple(sorted(item.job_id for item in manifest.jobs))
    assert all(
        {item.replica_index for item in manifest.jobs if item.runner_package_id == package_id}
        == set(range(6))
        for package_id in {item.runner_package_id for item in manifest.jobs}
    )
    assert audit.missing_job_count == audit.duplicate_job_count == audit.extra_job_count == 0
    assert audit.source_runner_parent_match_count == 192
    assert audit.source_package_parent_match_count == 192
    assert audit.generation_profile_parent_match_count == 192
    assert audit.outcome_contract_parent_match_count == 192


def test_all_accepted_prefix_classes_have_history_invariant_acceptance() -> None:
    audit = models.AcceptedPrefixSurfaceAudit.model_validate(
        _load("accepted_prefix_surface_audit.json")
    )
    assert audit.source_choice_combination_count == 772
    assert audit.replica_execution_count == 4_632
    assert len(audit.rows) == audit.package_component_replica_row_count == 480
    assert audit.reached_prefix_state_count == 14_388
    assert audit.candidate_evaluation_count == 41_124
    assert audit.accepted_action_count == 13_308
    assert audit.typed_rejection_count == 3_240
    assert audit.acceptance_signature_invariant_row_count == 480
    assert audit.history_dependent_acceptance_row_count == 0
    assert all(item.acceptance_signature_count == 1 for item in audit.rows)
    assert audit.runtime_exception_count == 0


def test_scripted_denominator_projects_one_actual_trace_per_job() -> None:
    contract = JobBoundMultistepOutcomeContract.model_validate(
        _load("job_bound_multistep_outcome_contract.json")
    )
    runner = JobBoundRunnerContract.model_validate(_load("job_bound_runner_contract.json"))
    audit = models.ScriptedDenominatorPreflightAudit.model_validate(
        _load("scripted_denominator_preflight_audit.json")
    )
    assert contract.first_policy_definition == (
        "complete_job_qualified_with_zero_component_corrections"
    )
    assert contract.first_action_is_not_job_first_policy_estimand is True
    assert contract.abi_invalid_action_acceptance_evaluable is False
    assert contract.exact_manifest_job_set_required is True
    assert runner.one_current_prompt_at_a_time is True
    assert runner.reference_trace_input_allowed is False
    assert runner.complete_baseline_loading_allowed is False
    assert audit.row_count == audit.unique_row_id_count == audit.unique_job_id_count == 192
    assert audit.exact_job_set_match_count == 192
    assert audit.current_prompt_render_count == audit.action_abi_parse_count == 480
    assert audit.accepted_action_count == 480
    assert audit.final_abi_parse_count == audit.finalized_runtime_result_count == 192
    assert audit.first_policy_qualified_control_count == 192
    assert audit.bounded_policy_qualified_control_count == 192
    assert audit.component_correction_count == 0
    assert audit.empirical_outcome_row_count == audit.empirical_estimand_evaluation_count == 0
    assert all(item.outcome.first_policy_qualified_valid for item in audit.rows)
    assert all(item.outcome.correction_count == 0 for item in audit.rows)


def test_runner_branch_controls_cover_multistep_and_terminal_shapes() -> None:
    audit = models.RunnerBranchControlAudit.model_validate(
        _load("runner_branch_control_audit.json")
    )
    assert len(audit.rows) == audit.scenario_count == 11
    by_scenario = {item.scenario: item for item in audit.rows}
    assert by_scenario[
        "direct_first_attempt_qualified"
    ].outcome.outcome.first_policy_qualified_valid
    abi = by_scenario["abi_invalid_first_response"].outcome.outcome
    assert abi.endpoint_kind == "first_response_abi_invalid"
    assert abi.task_verifier_invoked is False
    assert (
        abi.final_base_valid is abi.final_mechanism_qualified is abi.final_qualified_valid is None
    )
    downstream = by_scenario["accepted_first_action_downstream_task_invalid"].outcome.outcome
    assert downstream.correction_count == 0
    assert downstream.endpoint_kind == "completed_invalid"
    assert downstream.first_policy_qualified_valid is False
    assert by_scenario["one_component_correction"].outcome.outcome.correction_count == 1
    assert by_scenario["two_component_corrections"].outcome.outcome.correction_count == 2
    assert by_scenario[
        "valid_nonreference_correction"
    ].outcome.outcome.bounded_policy_qualified_valid
    assert by_scenario["different_current_invalid_second_response"].source_scope == (
        "canonical_diagnostic"
    )
    terminal_scenarios = {
        "same_current_invalid_second_response",
        "different_current_invalid_second_response",
        "stale_action_second_response",
        "foreign_action_second_response",
    }
    assert all(
        not by_scenario[cast(Any, item)].outcome.outcome.task_verifier_invoked
        for item in terminal_scenarios
    )
    assert (
        by_scenario["correction_terminal_forbids_third_prompt"].later_prompt_after_terminal_count
        == 0
    )
    assert all(item.outcome.exact_manifest_denominator_member is False for item in audit.rows)


def _test_only_empirical_row(
    scripted: Any,
) -> EmpiricalCapabilityOutcomeRow:
    values = {
        "job_id": scripted.job_id,
        "manifest_id": scripted.manifest_id,
        "execution_package_id": scripted.execution_package_id,
        "source_package_artifact_id": scripted.source_package_artifact_id,
        "replica_index": scripted.replica_index,
        "attempt_trace_id": scripted.attempt_trace_id,
        "raw_namespace": scripted.raw_namespace,
        "result_namespace": scripted.result_namespace,
        "raw_execution_id": f"test_only_raw:{scripted.job_id}",
        "result_id": f"test_only_result:{scripted.job_id}",
        "outcome": scripted.outcome,
    }
    return cast(
        EmpiricalCapabilityOutcomeRow,
        make_identity_model(
            EmpiricalCapabilityOutcomeRow,
            values,
            field="row_id",
            prefix="capability_empirical_job_bound_outcome_row:",
        ),
    )


def test_empirical_estimator_requires_the_exact_unique_manifest_set() -> None:
    manifest = CapabilityDevelopmentJobManifest.model_validate(
        _load("development_job_manifest.json")
    )
    scripted = models.ScriptedDenominatorPreflightAudit.model_validate(
        _load("scripted_denominator_preflight_audit.json")
    )
    test_only = tuple(_test_only_empirical_row(item) for item in scripted.rows)
    evaluation = evaluate_empirical_capability_estimands(test_only, manifest=manifest)
    assert evaluation.exact_job_set_match is True
    assert evaluation.q_first_fraction == evaluation.q_bounded_correction_fraction == "192/192"
    with pytest.raises(ValueError, match="repeats"):
        evaluate_empirical_capability_estimands(
            (*test_only[:-1], test_only[0]),
            manifest=manifest,
        )
    with pytest.raises(ValueError, match="denominator"):
        evaluate_empirical_capability_estimands(test_only[:-1], manifest=manifest)
    with pytest.raises(ValueError, match="scripted row"):
        evaluate_empirical_capability_estimands(cast(Any, scripted.rows), manifest=manifest)


def test_destructive_static_source_and_report_parents_close() -> None:
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    source = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    report = models.PreflightReport.model_validate(_load("report.json"))
    assert destructive.mutation_count == destructive.rejection_count == 21
    assert destructive.acceptance_count == 0
    assert all(item.fully_rehashed and item.rejected for item in destructive.mutations)
    assert static.gate_count == static.passed_gate_count == 39
    assert static.failed_gate_count == 0
    assert static.provider_calls == static.development_model_outcomes == 0
    assert source.file_count == 341
    assert source.unresolved_import_count == 0
    assert report.detail_file_count == 17
    assert report.manifest_count == report.runner_count == 1
    assert report.prospective_job_count == report.scripted_outcome_row_count == 192
    assert report.empirical_outcome_row_count == report.provider_calls == 0


def test_empty_directory_warning_error_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_179_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_v178_latest_revision_source_audit.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.empirical_outcome_row_count == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 18
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
