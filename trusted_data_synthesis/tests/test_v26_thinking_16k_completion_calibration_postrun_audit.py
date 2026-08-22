from __future__ import annotations

import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_postrun_audit import (  # noqa: E501
    NEXT_STAGE,
    CompletionOutcomeAudit,
    DestructiveAudit,
    DynamicBudgetAudit,
    ExecutionLineageAudit,
    InstrumentRootCauseAudit,
    PostrunAuditReport,
    PostrunSourceReplayAudit,
    ProspectiveTransitionContract,
    ProviderTelemetryAudit,
    build_thinking_16k_completion_calibration_postrun_audit,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, PostrunAuditReport]:
    output = tmp_path_factory.mktemp("v26_106_exact_16k_postrun")
    report = build_thinking_16k_completion_calibration_postrun_audit(
        output_dir=output,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    return output, report


def test_v26_106_replays_every_bound_and_execution_file_before_diagnostics(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    replay = PostrunSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )
    counts: dict[str, int] = {}
    for item in replay.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert replay.replayed_file_count == replay.replay_pass_count == 1860
    assert counts == {
        "v26_104_bound_source": 1237,
        "v26_104_preflight_output": 10,
        "v26_105_execution_file": 612,
        "v26_106_implementation": 1,
    }
    assert replay.replay_before_diagnostics
    assert not replay.credential_lookup_attempted
    assert replay.model_api_calls == replay.gpu_jobs == 0
    assert report.source_replay_audit_id == replay.audit_id


def test_v26_106_reconstructs_complete_raw_and_provider_lineage(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = ExecutionLineageAudit.model_validate_json(
        (output / "execution_lineage_audit.json").read_text()
    )

    assert audit.checkpoint_job_count == audit.result_job_count == 32
    assert audit.raw_execution_count == 32
    assert audit.provider_artifact_count == audit.unique_provider_call_id_count == 572
    assert audit.raw_descriptor_count == audit.raw_descriptor_hash_pass_count == 604
    assert audit.canonical_json_file_pass_count == 611
    assert audit.canonical_jsonl_row_pass_count == 32
    assert audit.checkpoint_final_result_match_count == 32
    assert audit.provider_parent_binding_pass_count == 572
    assert audit.all_provider_calls_dynamically_precertified
    assert audit.all_provider_calls_exact_16k_request_bound
    assert audit.all_provider_calls_usage_semantics_bound
    assert audit.all_actual_usage_charged_without_clipping
    assert audit.private_reasoning_payload_count == audit.private_reasoning_hash_count == 0
    assert audit.completed_run_replay_provider_call_count == 0
    assert audit.completed_run_replay_report_byte_identical


def test_v26_106_reproduces_usage_delta_and_reasoning_distribution(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = ProviderTelemetryAudit.model_validate_json(
        (output / "provider_telemetry_audit.json").read_text()
    )

    assert audit.provider_call_count == audit.http_success_call_count == 572
    assert audit.exact_requested_model_count == audit.exact_response_model_count == 572
    assert audit.fallback_count == audit.provider_native_tool_call_count == 0
    assert audit.provider_total_tokens == 4_780_636
    assert audit.completion_tokens_total == 3_105_100
    assert audit.reasoning_tokens_total == 3_001_271
    assert audit.non_reasoning_completion_tokens_total == 103_829
    assert audit.aggregate_reasoning_fraction == "0.966561785450"
    assert audit.median_call_reasoning_fraction == "0.975892584681"
    assert audit.p95_call_reasoning_fraction == "0.993100000000"
    assert audit.completion_usage_below_request_bound_count == 571
    assert audit.completion_usage_at_request_bound_count == 1
    assert audit.one_token_accounting_margin_call_count == 0
    assert audit.two_or_more_excess_token_call_count == 0
    assert audit.finish_reason_length_count == 1
    assert audit.usage_delta_cells[-1].completion_classification == (
        "reasoning_only_length_truncation"
    )


def test_v26_106_reproduces_completion_rescue_and_behavior_denominators(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = CompletionOutcomeAudit.model_validate_json(
        (output / "completion_outcome_audit.json").read_text()
    )

    assert audit.terminal_counts == {
        "completion_unusable": 14,
        "instrument_failure": 2,
        "model_invalid_trajectory": 1,
        "typed_budget_no_call": 15,
    }
    assert audit.completion_failure_counts == {
        "empty_final_content": 1,
        "invalid_json": 2,
        "invalid_response_contract": 33,
        "reasoning_only_length_truncation": 1,
    }
    assert audit.completion_failure_call_count == 37
    assert audit.rescue_attempt_job_count == audit.rescue_provider_call_job_count == 23
    assert audit.rescued_usable_request_count == 23
    assert audit.rescue_completion_failure_count == 0
    assert audit.terminal_second_completion_failure_after_rescue_count == 14
    assert not audit.typed_no_call_gate_passed
    assert not audit.completion_usability_gate_passed
    assert audit.reasoning_only_length_failure_observed
    assert audit.single_stage_completion_bound_ladder_ended
    assert audit.independently_valid_trajectory_count == 0
    assert audit.role_or_state_evidence_row_count == 0


def test_v26_106_localizes_dynamic_budget_terminals_without_provider_calls(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = DynamicBudgetAudit.model_validate_json(
        (output / "dynamic_budget_audit.json").read_text()
    )

    assert len(audit.terminal_rows) == audit.typed_no_call_job_count == 17
    assert audit.denial_reason_counts == {"required_reserve_not_available": 17}
    assert audit.request_kind_counts == {"decision": 17}
    assert audit.cumulative_provider_tokens_minimum == 171_114
    assert audit.cumulative_provider_tokens_maximum == 199_811
    assert audit.projected_deficit_tokens_minimum == 733
    assert audit.projected_deficit_tokens_maximum == 14_912
    assert audit.required_reserve_16385_count == 8
    assert audit.required_reserve_32770_count == 9
    assert audit.no_call_provider_invocation_count == 0
    assert audit.provider_usage_over_rollout_ceiling_count == 0
    assert audit.final_answer_no_call_count == 0
    assert audit.completed_program_node_count_distribution == {"0": 14, "2": 3}
    assert not audit.budget_ceiling_change_authorized


def test_v26_106_localizes_unknown_tool_runtime_replay_mismatch(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = InstrumentRootCauseAudit.model_validate_json(
        (output / "instrument_root_cause_audit.json").read_text()
    )

    assert audit.instrument_failure_job_count == len(audit.failure_rows) == 2
    assert audit.response_telemetry_failure_count == 0
    assert audit.provider_usage_contract_failure_count == 0
    assert audit.provider_call_for_denied_request_count == 0
    assert audit.runner_missing_tool_typed_rejection_branch_present
    assert audit.verifier_unknown_tool_early_continue_branch_present
    assert all(item.selected_tool_id == "open_document" for item in audit.failure_rows)
    assert all(item.selected_tool_absent_from_environment for item in audit.failure_rows)
    assert all(
        item.observation_error_code == "unknown_or_unselectable_tool" for item in audit.failure_rows
    )
    assert all(
        item.replayed_observation_count == item.observation_count - 1 for item in audit.failure_rows
    )
    assert not audit.historical_terminal_reclassified
    assert not audit.model_error_can_be_reclassified_historically


def test_v26_106_transition_requires_replay_repair_and_true_two_stage_preflight(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    contract = ProspectiveTransitionContract.model_validate_json(
        (output / "prospective_transition_contract.json").read_text()
    )

    assert contract.next_permitted_stage == NEXT_STAGE == report.next_permitted_stage
    assert contract.single_stage_completion_bound_ladder_ended
    assert not contract.higher_single_stage_completion_bound_allowed
    assert not contract.exact_32k_profile_registration_allowed
    assert contract.true_two_stage_thinking_decision_design_required
    assert contract.every_future_provider_call_thinking_enabled
    assert not contract.private_reasoning_content_may_be_persisted_or_transferred
    assert contract.verifier_must_replay_unknown_or_unselectable_tool_as_exact_typed_failure
    assert contract.verifier_repair_may_not_insert_or_choose_a_model_action
    assert contract.fresh_dynamic_rollout_budget_contract_required
    assert contract.complete_static_and_runner_preflight_required_before_provider_call
    assert not contract.provider_calls_authorized
    assert not contract.historical_v26_105_job_rerun_authorized
    assert not contract.historical_v26_105_terminal_reclassification_authorized


def test_v26_106_destructive_controls_reject_shortcuts(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    audit = DestructiveAudit.model_validate_json((output / "destructive_audit.json").read_text())

    assert audit.mutation_count == audit.rejected_mutation_count == 30
    assert all(item.rejected for item in audit.mutation_results)
    assert audit.model_api_calls == audit.gpu_jobs == 0
    assert report.status == "blocked"
    assert not report.role_protocol_frozen
    assert not report.capability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.production_contribution == 0


def test_v26_106_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, PostrunAuditReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_16k_completion_calibration_postrun_audit(
        output_dir=independent,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 9
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"reasoning_content":' not in serialized
    assert b'"raw_http_body":' not in serialized
    assert b'"raw_request_body":' not in serialized
