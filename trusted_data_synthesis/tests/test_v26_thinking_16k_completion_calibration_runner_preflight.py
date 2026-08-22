from __future__ import annotations

import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_binding_and_usage_semantics import (  # noqa: E501
    ProviderUsageSemanticsContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_contracts import (  # noqa: E501
    RUNNER_PREFLIGHT_RUN_ID,
    Exact16KExecutionContract,
    Exact16KRunnerPreflightReport,
    Exact16KRunnerSourceReplayAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_execution import (  # noqa: E501
    prepare_exact_16k_execution,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_completion_calibration_execution_preflight import (  # noqa: E501
    DestructivePreflightAudit,
    Exact16KClientBindingAudit,
    PrecallRecoveryAudit,
    ProviderUsageFixtureAudit,
    RunnerFixtureAudit,
    build_exact_16k_runner_preflight,
)
from trusted_synthesis.runtime.agent.prospective_thinking_16k_client import (
    EXACT_16K_MODEL_CONFIG_ID,
    EXACT_16K_THINKING_BINDING_ID,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Exact16KRunnerPreflightReport]:
    output = tmp_path_factory.mktemp("v26_104_exact_16k_runner")
    report = build_exact_16k_runner_preflight(
        run_id=RUNNER_PREFLIGHT_RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_104_replays_v26_103_and_all_runner_sources_before_client(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, report = built
    replay = Exact16KRunnerSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )
    counts: dict[str, int] = {}
    for item in replay.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert replay.replayed_file_count == replay.replay_pass_count == 1237
    assert counts == {
        "v26_103_transitive_source": 1221,
        "v26_103_output": 12,
        "v26_104_implementation": 4,
    }
    assert replay.replay_before_profile_parse
    assert replay.replay_before_credential_lookup
    assert replay.replay_before_client_construction
    assert not replay.credential_lookup_attempted
    assert not replay.model_client_constructed
    assert replay.provider_calls == replay.gpu_jobs == 0
    assert report.source_replay_audit_id == replay.audit_id


def test_v26_104_binds_exact_request_and_separate_usage_accounting(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, _ = built
    client = Exact16KClientBindingAudit.model_validate_json(
        (output / "client_request_binding_audit.json").read_text()
    )
    contract = Exact16KExecutionContract.model_validate_json(
        (output / "execution_contract.json").read_text()
    )
    usage = ProviderUsageSemanticsContract.model_validate_json(
        (output / "provider_usage_semantics_contract.json").read_text()
    )

    assert client.model_config_id == contract.model_config_id == EXACT_16K_MODEL_CONFIG_ID
    assert client.thinking_binding_id == contract.thinking_binding_id
    assert client.thinking_binding_id == EXACT_16K_THINKING_BINDING_ID
    assert client.representative_certificate.request_max_tokens == 16384
    assert client.representative_certificate.thinking_type == "enabled"
    assert client.actual_request_body_builder_shared_with_client
    assert client.exact_route_skips_model_discovery_call
    assert client.uncertified_client_entry_rejected_by_implementation
    assert usage.exact_request_completion_bound_tokens == contract.completion_upper_bound_tokens
    assert usage.maximum_accounting_admissible_completion_tokens == 16385
    assert contract.provider_reported_accounting_margin_tokens == 1
    assert contract.completion_rescue_reserve_tokens == 16384
    assert contract.completion_rescue_accounting_reserve_tokens == 1
    assert contract.final_answer_reserve_tokens == 16384
    assert contract.final_answer_accounting_reserve_tokens == 1
    assert contract.rollout_upper_bound_tokens == 240000
    assert contract.model_discovery_calls_per_job == 0
    assert not contract.automatic_higher_bound_escalation_allowed


def test_v26_104_usage_fixture_admits_plus_one_and_rejects_plus_two(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, report = built
    audit = ProviderUsageFixtureAudit.model_validate_json(
        (output / "provider_usage_fixture_audit.json").read_text()
    )

    assert audit.exact_bound_completion_usage_admitted
    assert audit.one_token_excess_usage_admitted_as_accounting_only
    assert audit.one_token_excess_actual_usage_charged_without_clipping
    assert audit.one_token_excess_length_failure_remained_completion_failure
    assert audit.two_token_excess_rejected_as_instrument_failure
    assert not audit.two_token_excess_completion_rescue_authorized
    assert not audit.request_body_max_tokens_changed_by_accounting_margin
    assert audit.request_accounting_upper_bound_includes_margin
    assert audit.rescue_reserve_includes_accounting_margin
    assert audit.final_answer_reserve_includes_accounting_margin
    assert audit.scripted_provider_call_count == 4
    assert audit.real_provider_call_count == 0
    assert report.provider_usage_fixture_audit_id == audit.audit_id


def test_v26_104_direct_fixtures_close_every_provider_call_pre_call(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, _ = built
    fixture = RunnerFixtureAudit.model_validate_json(
        (output / "runner_fixture_audit.json").read_text()
    )

    assert fixture.direct_fixture_job_count == 32
    assert fixture.direct_fixture_provider_call_count == 224
    assert fixture.direct_fixture_logical_request_count == 224
    assert fixture.direct_fixture_observation_count == 192
    assert fixture.direct_dynamic_certificate_count == 224
    assert fixture.direct_request_binding_certificate_count == 224
    assert fixture.direct_replay_pass_count == 32
    assert fixture.direct_verifier_valid_count == 32
    assert fixture.direct_mechanism_success_count == 32
    assert fixture.direct_cell_summary_count == 12
    assert fixture.full_aggregate_raw_file_count == 256
    assert fixture.full_aggregate_provider_call_count == 224
    assert fixture.full_aggregate_valid_terminal_count == 32
    assert fixture.full_aggregate_status == "passed"
    assert all(item.completed for item in fixture.direct_rows)
    assert all(item.all_provider_calls_dynamically_precertified for item in fixture.direct_rows)
    assert all(item.all_provider_calls_exact_16k_request_bound for item in fixture.direct_rows)


def test_v26_104_rescue_and_final_bound_transitions_are_frozen(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, _ = built
    fixture = RunnerFixtureAudit.model_validate_json(
        (output / "runner_fixture_audit.json").read_text()
    )

    assert len(fixture.rescue_rows) == 5
    assert all(item.completed for item in fixture.rescue_rows)
    assert all(item.maximum_rescue_prompt_utf8_bytes <= 6144 for item in fixture.rescue_rows)
    assert all(item.all_rescue_calls_dynamically_precertified for item in fixture.rescue_rows)
    assert all(item.all_rescue_calls_exact_16k_request_bound for item in fixture.rescue_rows)
    assert fixture.global_rescue_exhaustion_terminal == "completion_unusable"
    assert fixture.global_rescue_exhaustion_rescue_provider_call_count == 1
    assert fixture.telemetry_only_terminal == "instrument_failure"
    assert fixture.telemetry_only_rescue_provider_call_count == 0
    assert fixture.length_failure_transition_control == (
        "true_two_stage_thinking_decision_protocol_only"
    )
    assert fixture.telemetry_failure_transition_control == (
        "thinking_response_telemetry_wrapper_repair_only"
    )
    assert fixture.direct_pass_transition_control == "thinking_role_protocol_freeze_only"


def test_v26_104_off_compiler_budget_and_recovery_controls_fail_closed(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, _ = built
    audit = PrecallRecoveryAudit.model_validate_json(
        (output / "precall_recovery_audit.json").read_text()
    )

    assert audit.first_execution_provider_call_count == 5
    assert audit.raw_only_recovery_provider_call_count == 0
    assert audit.raw_only_recovery_byte_identical
    assert audit.orphan_provider_artifact_rejected
    assert audit.oversized_primary_denied_before_delegate
    assert audit.oversized_primary_delegate_call_count == 0
    assert audit.resource_exhaustion_denied_before_delegate
    assert audit.resource_exhaustion_delegate_call_count == 0
    assert audit.wrong_actual_request_kind_rejected_before_delegate
    assert audit.wrong_actual_request_kind_delegate_call_count == 0
    assert audit.off_compiler_primary_utf8_bytes == 7914
    assert audit.off_compiler_bounded_rescue_utf8_bytes == 3888
    assert audit.off_compiler_provider_calls_before_certificates == 0
    assert audit.off_compiler_scripted_provider_calls_after_certificates == 1
    assert audit.off_compiler_rescue_absolutely_bounded
    assert audit.off_compiler_rescue_dynamically_precertified
    assert audit.off_compiler_rescue_exact_16k_request_bound


def test_v26_104_destructive_controls_and_transition_are_narrow(
    built: tuple[Path, Exact16KRunnerPreflightReport],
) -> None:
    output, report = built
    destructive = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )

    assert destructive.rejected_mutation_count == 30
    assert all(item.rejected for item in destructive.mutation_results)
    assert destructive.model_api_calls == destructive.gpu_jobs == 0
    assert report.execution_runner_materialized
    assert report.exact_16k_execution_authorized
    assert not report.higher_bound_execution_authorized
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.production_contribution == 0
    assert report.next_permitted_stage == "thinking_16k_completion_calibration_execution_only"


def test_v26_104_online_prepare_replays_without_client(
    built: tuple[Path, Exact16KRunnerPreflightReport],
    tmp_path: Path,
) -> None:
    preflight_dir, report = built
    prepared = prepare_exact_16k_execution(
        runner_preflight_dir=preflight_dir,
        output_dir=tmp_path / "prepared",
        package_root=PACKAGE_ROOT,
    )

    assert prepared.preflight_report.report_id == report.report_id
    assert prepared.execution_contract.contract_id == report.execution_contract_id
    assert len(prepared.static.predecessor_manifest.jobs) == 32
    assert prepared.static.agent_model_config.max_output_tokens == 16384
    assert (
        prepared.provider_usage_semantics.maximum_accounting_admissible_completion_tokens == 16385
    )
    assert not (tmp_path / "prepared" / "report.json").exists()
    assert not (tmp_path / "prepared" / "raw_provider_calls").exists()


def test_v26_104_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, Exact16KRunnerPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_exact_16k_runner_preflight(
        run_id=RUNNER_PREFLIGHT_RUN_ID,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
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
    assert b'"reasoning_content":' not in serialized
    assert b'"raw_http_body":' not in serialized
    assert b'"raw_request_body":' not in serialized
