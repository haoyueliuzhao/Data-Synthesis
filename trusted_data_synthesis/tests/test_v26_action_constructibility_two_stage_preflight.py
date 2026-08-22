from __future__ import annotations

import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_action_constructibility_two_stage_preflight import (  # noqa: E501
    NEXT_STAGE,
    ActionConstructibilityFixtureAudit,
    ActionConstructibilityPreflightReport,
    ActionConstructibilityProtocol,
    DestructivePreflightAudit,
    FailureTaxonomyAudit,
    FinalRescueSemanticAudit,
    HistoricalActionInterfaceAudit,
    SourceReplayAudit,
    VerifierV3ReplayAudit,
    build,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_verifier_replay_v3 import (  # noqa: E501
    AuthorityPreservingReplayV3Contract,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, ActionConstructibilityPreflightReport]:
    output = tmp_path_factory.mktemp("v26_107_action_constructibility")
    report = build(
        output,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    return output, report


def test_v26_107_replays_predecessor_and_new_implementation_before_diagnostics(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, report = built
    replay = SourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )
    counts: dict[str, int] = {}
    for item in replay.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert replay.replayed_file_count == replay.replay_pass_count == 1872
    assert counts == {
        "v26_106_transitive_source": 1860,
        "v26_106_output": 9,
        "v26_107_implementation": 3,
    }
    assert replay.replay_before_diagnostics
    assert not replay.credential_lookup_attempted
    assert not replay.model_client_constructed
    assert replay.model_api_calls == replay.gpu_jobs == 0
    assert report.source_replay_audit_id == replay.audit_id


def test_v26_107_refines_historical_action_interface_without_reclassification(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, _ = built
    audit = HistoricalActionInterfaceAudit.model_validate_json(
        (output / "historical_action_interface_audit.json").read_text()
    )

    assert audit.raw_execution_count == 32
    assert audit.provider_artifact_count == 572
    assert audit.calculator_observation_count == 382
    assert audit.calculator_job_count == 30
    assert audit.calculator_success_count == audit.calculator_success_job_count == 1
    assert audit.code_defined_ready_calculator_count == 382
    assert audit.code_defined_not_ready_calculator_count == 0
    assert (
        audit.bare_operand_count,
        audit.operand_object_wrong_fields_count,
        audit.operand_type_or_count_error_count,
        audit.parameters_mismatch_count,
        audit.reference_or_order_mismatch_count,
        audit.exact_argument_match_count,
    ) == (188, 158, 22, 12, 1, 1)
    assert audit.contradictory_tool_affordance_prompt_count == 79
    assert audit.contradictory_tool_affordance_job_count == 12
    assert audit.runtime_unknown_tool_observation_count == 2
    assert not audit.old_prompt_full_tool_input_contract_exposed
    assert not audit.old_prompt_public_symbol_binding_table_exposed
    assert audit.old_static_witness_read_exact_arguments
    assert not audit.historical_terminal_reclassified


def test_v26_107_freezes_exact_response_contract_failure_taxonomy(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, _ = built
    audit = FailureTaxonomyAudit.model_validate_json(
        (output / "failure_taxonomy_audit.json").read_text()
    )

    assert audit.historical_invalid_response_contract_count == 33
    assert audit.public_json_payload_present_count == 33
    assert audit.decision_answer_during_decision_count == 22
    assert audit.public_prompt_echo_count == 7
    assert audit.unregistered_action_enum_count == 3
    assert audit.final_answer_scalar_count == 1
    assert audit.prospective_decision_phase_control_count == 22
    assert audit.prospective_prompt_echo_instruction_count == 7
    assert audit.prospective_response_serialization_count == 4
    assert not audit.historical_completion_failure_count_changed
    assert not audit.historical_job_terminal_changed


def test_v26_107_verifier_v3_replays_unavailable_tools_as_exact_typed_failures(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, report = built
    contract = AuthorityPreservingReplayV3Contract.model_validate_json(
        (output / "verifier_v3_contract.json").read_text()
    )
    audit = VerifierV3ReplayAudit.model_validate_json(
        (output / "verifier_v3_replay_audit.json").read_text()
    )

    assert contract.shared_runtime_verifier_tool_availability_gate
    assert contract.unavailable_tool_replayed_as_exact_typed_failure
    assert not contract.verifier_may_insert_or_choose_model_action
    assert audit.job_count == audit.replay_pass_count == 32
    assert audit.exact_unavailable_tool_failure_count == 2
    assert audit.old_verifier_replay_failure_count == 2
    assert audit.prospective_verifier_replay_failure_count == 0
    assert sum(item.exact_unavailable_tool_failure_count for item in audit.rows) == 2
    assert all(item.passed for item in audit.rows)
    assert audit.provider_calls == audit.empirical_rows == 0
    assert report.verifier_v3_contract_id == contract.contract_id
    assert report.verifier_v3_replay_audit_id == audit.audit_id


def test_v26_107_action_compilation_is_public_reversible_and_model_owned(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, _ = built
    audit = ActionConstructibilityFixtureAudit.model_validate_json(
        (output / "action_constructibility_fixture_audit.json").read_text()
    )

    assert audit.compiler_path_count == 48
    assert audit.compiler_call_count == audit.reversible_compilation_pass_count == 276
    assert audit.compiler_unique_public_state_count == 147
    assert audit.compiler_acquisition_proposal_count == 156
    assert audit.compiler_operation_proposal_count == 72
    assert audit.compiler_verification_proposal_count == 48
    assert audit.variable_tool_subset_pass_count == 276
    assert audit.maximum_action_prompt_utf8_bytes == 6345
    assert audit.prompt_only_reference_task_count == 24
    assert audit.prompt_only_reference_decision_count == 138
    assert audit.prompt_only_reference_prompt_parse_count == 138
    assert audit.prompt_only_reference_call_count == 114
    assert audit.prompt_only_reference_typed_refinement_count == 6
    assert audit.prompt_only_reference_final_ready_count == 24
    assert audit.prompt_only_reference_failure_count_other_than_typed_refinement == 0
    assert not audit.prompt_only_reference_reads_private_task_or_expected_arguments
    assert audit.full_failed_argument_value_count_in_new_history == 0
    assert audit.private_or_oracle_field_count == 0
    assert audit.provider_calls == audit.compiler_fixture_empirical_rows == 0


def test_v26_107_final_rescue_retains_public_terminal_semantics(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, _ = built
    audit = FinalRescueSemanticAudit.model_validate_json(
        (output / "final_rescue_semantic_audit.json").read_text()
    )

    assert audit.compiler_path_count == audit.semantically_sufficient_rescue_count == 48
    assert audit.maximum_rescue_prompt_utf8_bytes == 2515
    assert audit.historical_terminal_value == "0.4107"
    assert audit.historical_primary_answer_was_scalar
    assert audit.historical_rescue_answer_value == "0.1"
    assert not audit.historical_rescue_retained_terminal_value
    assert audit.repaired_rescue_retains_terminal_value
    assert audit.repaired_historical_rescue_prompt_utf8_bytes == 2323
    assert not audit.previous_final_content_reused
    assert not audit.private_reasoning_reused
    assert not audit.historical_terminal_reclassified
    assert audit.provider_calls == 0


def test_v26_107_freezes_true_two_stage_authority_boundary_without_execution(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, report = built
    protocol = ActionConstructibilityProtocol.model_validate_json(
        (output / "action_constructibility_protocol.json").read_text()
    )

    assert protocol.stage_one_name == "thinking_semantic_decision_proposal"
    assert protocol.stage_one_thinking_enabled_required
    assert not protocol.stage_one_private_reasoning_may_cross_boundary
    assert protocol.stage_one_public_proposal_only_crosses_boundary
    assert protocol.stage_two_name == "deterministic_decision_commit_compilation"
    assert not protocol.stage_two_provider_call_required
    assert not protocol.stage_two_may_choose_tool_node_operator_or_operand
    assert protocol.stage_two_reversible_wire_serialization_only
    assert protocol.complete_tool_input_grammar_exposed
    assert protocol.resolved_public_symbol_bindings_exposed
    assert not protocol.correct_hidden_semantic_choice_exposed
    assert protocol.variable_tools_must_be_subset_of_public_tools
    assert protocol.shared_runtime_verifier_availability_gate_required
    assert not protocol.bounded_failure_history_retains_exact_argument_values
    assert protocol.final_rescue_must_retain_terminal_public_result
    assert not protocol.fresh_stage_one_model_profile_materialized
    assert not protocol.fresh_taskpackage_contract_manifest_job_identities_materialized
    assert not protocol.runner_implemented_and_preflighted
    assert not protocol.provider_calls_authorized
    assert report.next_permitted_stage == NEXT_STAGE
    assert report.status == "design_preflight_passed_execution_not_authorized"
    assert report.model_api_calls == report.gpu_jobs == report.empirical_rows == 0
    assert not report.single_stage_32k_allowed
    assert not report.role_protocol_frozen
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert not report.state_mapping_authorized
    assert not report.release_authorized
    assert report.production_contribution == 0


def test_v26_107_destructive_controls_reject_action_and_authority_shortcuts(
    built: tuple[Path, ActionConstructibilityPreflightReport],
) -> None:
    output, report = built
    audit = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )
    names = {item.mutation for item in audit.mutation_results}

    assert audit.mutation_count == audit.rejected_mutation_count == 30
    assert all(item.rejected for item in audit.mutation_results)
    assert all(item.provider_calls_before_rejection == 0 for item in audit.mutation_results)
    assert {
        "variable_tool_outside_public_grammar",
        "proposal_selects_unknown_tool",
        "unknown_tool_typed_failure_changed",
        "failure_summary_retains_exact_evidence_value",
        "proposal_missing_model_semantic_authority",
        "commit_claims_compiler_semantic_selection",
    } <= names
    assert audit.provider_calls == audit.gpu_jobs == 0
    assert report.destructive_preflight_audit_id == audit.audit_id


def test_v26_107_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, ActionConstructibilityPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build(
        independent,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 10
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"private_reasoning":' not in serialized
    assert b'"private_reasoning_content":' not in serialized
    assert b'"raw_http_body":' not in serialized
    assert b'"raw_request_body":' not in serialized
    assert b'"expected_arguments":' not in serialized
