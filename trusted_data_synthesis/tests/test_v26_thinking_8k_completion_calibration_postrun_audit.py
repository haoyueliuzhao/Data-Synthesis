from __future__ import annotations

import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_completion_calibration_postrun_audit import (  # noqa: E501
    NEXT_STAGE,
    CompletionOutcomeAudit,
    DestructiveAudit,
    ExecutionLineageAudit,
    InstrumentRootCauseAudit,
    PostrunAuditReport,
    PostrunSourceReplayAudit,
    ProspectiveTransitionContract,
    ProviderTelemetryAudit,
    build_thinking_8k_completion_calibration_postrun_audit,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, PostrunAuditReport]:
    output = tmp_path_factory.mktemp("v26_102_exact_8k_postrun")
    report = build_thinking_8k_completion_calibration_postrun_audit(
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_102_replays_every_bound_and_execution_file_before_diagnostics(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    replay = PostrunSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )
    counts: dict[str, int] = {}
    for item in replay.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert replay.replayed_file_count == replay.replay_pass_count == 1211
    assert counts == {
        "v26_100_bound_source": 770,
        "v26_100_preflight_output": 9,
        "v26_101_execution_file": 431,
        "v26_102_implementation": 1,
    }
    assert replay.replay_before_diagnostics
    assert not replay.credential_lookup_attempted
    assert replay.model_api_calls == replay.gpu_jobs == 0
    assert report.source_replay_audit_id == replay.audit_id
    assert report.run_id == (
        "finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822"
    )


def test_v26_102_reconstructs_complete_raw_and_provider_lineage(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = ExecutionLineageAudit.model_validate_json(
        (output / "execution_lineage_audit.json").read_text()
    )

    assert audit.checkpoint_job_count == audit.result_job_count == 32
    assert audit.raw_execution_count == 32
    assert audit.provider_artifact_count == audit.unique_provider_call_id_count == 391
    assert audit.raw_descriptor_count == audit.raw_descriptor_hash_pass_count == 423
    assert audit.canonical_json_file_pass_count == 430
    assert audit.canonical_jsonl_row_pass_count == 32
    assert audit.checkpoint_final_result_match_count == 32
    assert audit.provider_parent_binding_pass_count == 391
    assert audit.all_provider_calls_dynamically_precertified
    assert audit.all_provider_calls_exact_8k_request_bound
    assert audit.private_reasoning_payload_count == 0
    assert audit.raw_http_body_payload_count == audit.raw_request_body_payload_count == 0


def test_v26_102_reproduces_provider_usage_and_privacy_denominator(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = ProviderTelemetryAudit.model_validate_json(
        (output / "provider_telemetry_audit.json").read_text()
    )

    assert audit.provider_call_count == audit.http_success_call_count == 391
    assert audit.exact_requested_model_count == audit.exact_selected_model_count == 391
    assert audit.exact_response_model_count == 391
    assert audit.fallback_count == audit.provider_native_tool_call_count == 0
    assert audit.thinking_telemetry_complete_count == 391
    assert audit.response_envelope_preparse_count == 391
    assert audit.provider_total_tokens == 2_498_889
    assert audit.completion_tokens_total == 1_648_174
    assert audit.reasoning_tokens_total == 1_610_137
    assert audit.estimated_cost_usd == "0.53245247440000004286"
    assert audit.completion_usage_within_request_bound_count == 390
    assert audit.completion_usage_over_request_bound_count == 1
    assert audit.maximum_observed_overrun_tokens == 1


def test_v26_102_reproduces_completion_gate_independently(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = CompletionOutcomeAudit.model_validate_json(
        (output / "completion_outcome_audit.json").read_text()
    )

    assert audit.terminal_counts == {
        "completion_unusable": 28,
        "instrument_failure": 1,
        "model_valid_trajectory": 3,
    }
    assert audit.completion_failure_counts == {
        "invalid_json": 1,
        "invalid_response_contract": 12,
        "length_truncated_content": 3,
        "reasoning_only_length_truncation": 42,
    }
    assert audit.completion_failure_call_count == 58
    assert audit.rescue_attempt_job_count == 30
    assert audit.rescue_provider_call_job_count == 29
    assert audit.typed_no_call_gate_passed
    assert not audit.completion_usability_gate_passed
    assert audit.independently_valid_trajectory_count == 3
    assert audit.role_or_state_evidence_row_count == 0


def test_v26_102_localizes_the_single_provider_usage_overrun(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, _ = built
    audit = InstrumentRootCauseAudit.model_validate_json(
        (output / "instrument_root_cause_audit.json").read_text()
    )

    assert audit.request_max_tokens == audit.request_certificate_max_tokens == 8192
    assert audit.dynamic_certificate_completion_bound == 8192
    assert audit.provider_budget_completion_bound == 8192
    assert audit.provider_reported_completion_tokens == 8193
    assert audit.provider_reported_reasoning_tokens == 8193
    assert audit.provider_reported_overrun_tokens == 1
    assert audit.failure_type == "reasoning_only_length_truncation"
    assert audit.public_content_length == 0
    assert audit.all_certificates_constructed_before_provider_call
    assert audit.rescue_attempted_after_primary_failure
    assert not audit.rescue_provider_call_made
    assert audit.rescue_blocked_after_terminal_budget_state
    assert audit.other_provider_calls_within_bound_count == 390
    assert not audit.host_request_binding_failure_observed
    assert not audit.underlying_provider_generation_vs_accounting_semantics_uniquely_identified
    assert not audit.historical_terminal_reclassified


def test_v26_102_transition_requires_fresh_16k_and_usage_contract_preflight(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    contract = ProspectiveTransitionContract.model_validate_json(
        (output / "prospective_transition_contract.json").read_text()
    )

    assert contract.next_permitted_stage == NEXT_STAGE == report.next_permitted_stage
    assert contract.exact_16k_request_max_tokens == 16384
    assert contract.exact_16k_rollout_ceiling_tokens == 240000
    assert contract.persisted_exact_16k_profile_required
    assert contract.fresh_taskpackage_path_contract_manifest_job_identities_required
    assert contract.provider_usage_semantics_contract_required_before_runner
    assert contract.separate_request_bound_from_provider_reported_usage_accounting
    assert contract.charge_actual_provider_reported_usage_to_rollout_budget
    assert contract.observed_accounting_margin_tokens == 1
    assert contract.prospective_margin_must_reject_two_or_more_tokens
    assert contract.accounting_margin_cannot_rescue_length_or_completion_failure
    assert not contract.automatic_16k_escalation_allowed
    assert not contract.direct_16k_execution_authorized
    assert not contract.v26_101_job_rerun_authorized


def test_v26_102_destructive_controls_reject_shortcuts(
    built: tuple[Path, PostrunAuditReport],
) -> None:
    output, report = built
    audit = DestructiveAudit.model_validate_json((output / "destructive_audit.json").read_text())

    assert audit.mutation_count == audit.rejected_mutation_count == 20
    assert all(item.rejected for item in audit.mutation_results)
    assert audit.model_api_calls == audit.gpu_jobs == 0
    assert report.status == "blocked"
    assert not report.role_protocol_frozen
    assert not report.capability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.production_contribution == 0


def test_v26_102_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, PostrunAuditReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_8k_completion_calibration_postrun_audit(
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
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"reasoning_content":' not in serialized
    assert b'"raw_http_body":' not in serialized
    assert b'"raw_request_body":' not in serialized
