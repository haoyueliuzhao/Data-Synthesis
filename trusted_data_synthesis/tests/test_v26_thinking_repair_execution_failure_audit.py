from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_repair_execution_failure_audit import (  # noqa: E501
    RUN_ID,
    CompletionLowerBoundAudit,
    FailedExecutionLineageAudit,
    FailedProviderTelemetryAudit,
    FailureDestructiveAudit,
    FailureSourceReplayAudit,
    InstrumentRootCauseAudit,
    ProspectiveFailureTransitionContract,
    ThinkingRepairFailureAuditReport,
    build_thinking_repair_execution_failure_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, ThinkingRepairFailureAuditReport]:
    output = tmp_path_factory.mktemp("v26_96_failure_audit")
    report = build_thinking_repair_execution_failure_audit(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_96_replays_every_bound_and_failed_execution_file(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, report = built
    source = FailureSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 723
    assert source.bound_source_file_count == 498
    assert source.preflight_output_file_count == 7
    assert source.failed_execution_file_count == 217
    assert source.audit_implementation_file_count == 1
    assert all(item.passed for item in source.entries)
    assert report.model_client_constructed is False
    assert report.model_api_calls == report.gpu_jobs == 0


def test_v26_96_reconstructs_exposure_without_rerun_or_reclassification(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, _ = built
    audit = FailedExecutionLineageAudit.model_validate_json(
        (output / "failed_execution_lineage_audit.json").read_text(encoding="utf-8")
    )

    assert audit.manifest_job_count == 32
    assert audit.checkpoint_job_count == 19
    assert audit.raw_execution_count == 27
    assert audit.raw_uncheckpointed_job_count == 8
    assert audit.provider_orphan_job_count == 1
    assert audit.unopened_job_count == 4
    assert audit.exposed_job_count == 28
    assert audit.provider_artifact_count == 184
    assert audit.raw_bound_provider_artifact_count == 176
    assert audit.orphan_provider_artifact_count == 8
    assert audit.checkpoint_raw_binding_pass_count == 19
    assert audit.historical_job_rerun_count == 0
    assert audit.historical_result_reclassification_count == 0
    assert not audit.completed_report_materialized
    assert {item.state for item in audit.rows} == {
        "checkpoint",
        "raw_uncheckpointed",
        "provider_orphan",
        "unopened",
    }


def test_v26_96_provider_telemetry_is_complete_and_privacy_redacted(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, _ = built
    audit = FailedProviderTelemetryAudit.model_validate_json(
        (output / "provider_telemetry_audit.json").read_text(encoding="utf-8")
    )

    assert audit.provider_artifact_count == 184
    assert audit.http_success_call_count == 184
    assert audit.exact_response_model_call_count == 184
    assert audit.positive_thinking_telemetry_call_count == 184
    assert audit.complete_usage_call_count == 184
    assert audit.primary_call_count == 156
    assert audit.rescue_call_count == 28
    assert audit.reasoning_only_length_truncation_call_count == 48
    assert audit.length_truncated_content_call_count == 2
    assert audit.provider_total_tokens == 775_292
    assert audit.reasoning_tokens == 433_062
    assert audit.completion_tokens == 444_089
    assert audit.estimated_cost_usd == "0.16411017840000001316"
    assert audit.private_reasoning_payload_count == 0
    assert audit.raw_http_body_count == 0
    assert audit.transport_failure_count == 0
    assert audit.response_model_mismatch_count == 0


def test_v26_96_completion_gate_is_irrevocably_failed_without_exact_denominator(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, _ = built
    audit = CompletionLowerBoundAudit.model_validate_json(
        (output / "completion_lower_bound_audit.json").read_text(encoding="utf-8")
    )

    assert audit.exact_denominator_completed is False
    assert audit.complete_raw_completion_unusable_count == 27
    assert audit.formal_completion_unusable_lower_bound_count == 27
    assert audit.maximum_remaining_nonfailure_job_count == 5
    assert audit.completion_gate_can_still_pass is False
    assert audit.exact_denominator_clopper_pearson_reported is False
    assert audit.raw_reasoning_only_failure_count == 46
    assert audit.raw_length_truncated_failure_count == 2
    assert audit.raw_invalid_response_contract_failure_count == 6
    assert audit.orphan_primary_reasoning_only_truncation_observed
    assert audit.orphan_rescue_reasoning_only_truncation_observed
    assert not audit.orphan_job_terminal_reclassified
    assert not audit.same_bound_prompt_only_retuning_allowed


def test_v26_96_localizes_dynamic_off_path_precall_gap(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, _ = built
    audit = InstrumentRootCauseAudit.model_validate_json(
        (output / "instrument_root_cause_audit.json").read_text(encoding="utf-8")
    )

    assert audit.registered_request_kind == "final_answer"
    assert audit.online_request_kind == "decision"
    assert audit.registered_primary_prompt_utf8_bytes == 2865
    assert audit.registered_maximum_rescue_prompt_utf8_bytes == 1609
    assert audit.online_primary_prompt_utf8_bytes == 7914
    assert audit.online_rescue_prompt_utf8_bytes == 7176
    assert audit.online_rescue_reduction_basis_points == 932
    assert audit.reduction_shortfall_basis_points == 68
    assert not audit.primary_matches_registered_hash
    assert not audit.request_kind_matches_registered
    assert audit.primary_reasoning_tokens == audit.rescue_reasoning_tokens == 4096
    assert audit.rescue_http_success_before_gate_failure
    assert audit.rescue_provider_artifact_persisted_before_gate_failure
    assert audit.reduction_computed_after_provider_call
    assert not audit.dynamic_request_kind_precall_gate_present
    assert not audit.dynamic_reduction_precall_gate_present
    assert audit.complete_raw_registered_kind_mismatch_count == 8
    assert audit.complete_raw_registered_primary_hash_mismatch_count == 105
    assert audit.root_cause == "dynamic_off_path_rescue_contract_not_precall_closed"
    assert audit.v26_94_registered_compiler_claim_retained
    assert not audit.v26_94_arbitrary_online_state_coverage_claimed


def test_v26_96_transition_forbids_continuation_and_same_bound_prompt_tuning(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
) -> None:
    output, report = built
    contract = ProspectiveFailureTransitionContract.model_validate_json(
        (output / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )
    destructive = FailureDestructiveAudit.model_validate_json(
        (output / "destructive_audit.json").read_text(encoding="utf-8")
    )

    assert not contract.exposed_v26_95_job_rerun_allowed
    assert not contract.unopened_v26_95_continuation_allowed
    assert contract.unopened_v26_95_job_identities_retired
    assert not contract.same_4096_bound_prompt_only_retuning_allowed
    assert contract.future_completion_bound_change_permitted
    assert contract.future_true_two_stage_protocol_permitted
    assert not contract.unique_successor_design_selected
    assert contract.future_dynamic_request_kind_precall_validation_required
    assert contract.future_dynamic_rescue_reduction_precall_validation_required
    assert contract.future_reachable_state_coverage_required
    assert not contract.role_protocol_frozen
    assert contract.production_contribution == 0
    assert contract.next_permitted_stage == (
        "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    )
    assert destructive.rejected_mutation_count == 12
    assert all(item.rejected for item in destructive.mutation_results)
    assert report.status == "blocked"
    assert report.next_permitted_stage == contract.next_permitted_stage


def test_v26_96_dual_build_is_byte_identical(
    built: tuple[Path, ThinkingRepairFailureAuditReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_repair_execution_failure_audit(
        run_id=RUN_ID,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 8
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    payloads = [json.loads((formal / name).read_text(encoding="utf-8")) for name in formal_files]
    serialized = json.dumps(payloads, ensure_ascii=False, sort_keys=True)
    assert '"reasoning_content"' not in serialized
    assert '"raw_http_body"' not in serialized
