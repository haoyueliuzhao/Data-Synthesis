from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution import (  # noqa: E501
    ThinkingRepairExecutionContract,
    ThinkingRepairExecutionPreflightReport,
    ThinkingRepairOutcomeInterpretationContract,
    ThinkingRepairRunnerSourceReplayAudit,
    prepare_thinking_repair_execution,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_execution_preflight import (  # noqa: E501
    RESCUE_FAILURE_TYPES,
    V26_95_RUN_ID,
    BudgetRecoveryAudit,
    DestructivePreflightAudit,
    RunnerFixtureAudit,
    build_thinking_repair_execution_preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def formal_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    output = tmp_path_factory.mktemp("v26_95_formal")
    report = build_thinking_repair_execution_preflight(
        run_id=V26_95_RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_95_dual_build_is_byte_identical(
    formal_build: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    formal_dir, formal_report = formal_build
    independent_dir = tmp_path / "independent"
    independent_report = build_thinking_repair_execution_preflight(
        run_id=V26_95_RUN_ID,
        output_dir=independent_dir,
        package_root=PACKAGE_ROOT,
    )
    formal_files = tuple(sorted(path.name for path in formal_dir.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent_dir.iterdir()))

    assert len(formal_files) == 7
    assert formal_files == independent_files
    assert all(
        (formal_dir / name).read_bytes() == (independent_dir / name).read_bytes()
        for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id


def test_v26_95_report_authorizes_only_exact_repair_execution(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    report = ThinkingRepairExecutionPreflightReport.model_validate_json(
        (output / "report.json").read_text(encoding="utf-8")
    )
    contract = ThinkingRepairExecutionContract.model_validate_json(
        (output / "execution_contract.json").read_text(encoding="utf-8")
    )

    assert report.source_replayed_file_count == 498
    assert report.exact_job_count == 32
    assert report.direct_fixture_job_count == 32
    assert report.rescue_fixture_count == 5
    assert report.execution_runner_materialized
    assert report.repair_execution_authorized
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.model_api_calls == report.gpu_jobs == 0
    assert report.production_contribution == 0
    assert report.next_permitted_stage == "thinking_completion_telemetry_repair_execution_only"
    assert contract.execution_run_id.endswith(
        "thinking_completion_telemetry_repair_execution_v1_20260821"
    )
    assert len(contract.job_ids) == len(set(contract.job_ids)) == 32
    assert contract.maximum_rescue_calls_per_job == 1
    assert contract.model_plan_calls_per_job == 0
    assert contract.transient_provider_retries_per_request == 0
    assert not contract.provider_config_contract_repair_loop_used


def test_v26_95_replays_all_v26_94_outputs_bindings_and_runner_sources(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    replay = ThinkingRepairRunnerSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    counts: dict[str, int] = {}
    for item in replay.entries:
        counts[item.source_kind] = counts.get(item.source_kind, 0) + 1

    assert replay.replayed_file_count == replay.replay_pass_count == 498
    assert counts == {
        "v26_94_output": 11,
        "v26_94_replay_binding": 485,
        "v26_95_implementation": 2,
    }
    assert all(item.passed for item in replay.entries)
    assert replay.replay_before_credential_lookup
    assert replay.replay_before_client_construction
    assert replay.model_api_calls == replay.gpu_jobs == 0


def test_v26_95_runner_fixtures_cover_direct_and_all_rescue_outcomes(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    fixture = RunnerFixtureAudit.model_validate_json(
        (output / "runner_fixture_audit.json").read_text(encoding="utf-8")
    )

    assert fixture.direct_fixture_job_count == 32
    assert fixture.direct_fixture_provider_call_count == 224
    assert fixture.direct_fixture_logical_request_count == 224
    assert fixture.direct_fixture_observation_count == 192
    assert fixture.direct_replay_pass_count == 32
    assert fixture.direct_verifier_valid_count == 32
    assert fixture.direct_mechanism_success_count == 32
    assert fixture.direct_cell_summary_count == 12
    assert fixture.full_aggregate_raw_file_count == 256
    assert fixture.full_aggregate_provider_call_count == 224
    assert fixture.full_aggregate_valid_terminal_count == 32
    assert fixture.full_aggregate_status == "passed"
    assert len(fixture.direct_rows) == 32
    assert all(item.completed for item in fixture.direct_rows)
    assert all(item.observations_match_compiler for item in fixture.direct_rows)
    assert all(item.all_primary_prompts_match_registered for item in fixture.direct_rows)
    assert all(
        item.rescue_call_count == item.model_plan_call_count == 0 for item in fixture.direct_rows
    )
    assert tuple(item.failure_type for item in fixture.rescue_rows) == RESCUE_FAILURE_TYPES
    assert all(item.provider_call_count == 6 for item in fixture.rescue_rows)
    assert all(item.completed and item.rescue_call_count == 1 for item in fixture.rescue_rows)
    assert fixture.global_rescue_exhaustion_terminal == "completion_unusable"
    assert fixture.global_rescue_exhaustion_rescue_call_count == 1
    assert fixture.global_rescue_exhaustion_provider_call_count == 6
    assert fixture.telemetry_only_terminal == "instrument_failure"
    assert fixture.telemetry_only_rescue_call_count == 0
    assert (
        fixture.length_failure_transition_control
        == "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    )
    assert (
        fixture.telemetry_failure_transition_control
        == "thinking_response_telemetry_wrapper_repair_only"
    )
    assert fixture.direct_pass_transition_control == "thinking_role_protocol_freeze_only"
    assert fixture.full_aggregate_transition_control == "thinking_role_protocol_freeze_only"
    assert fixture.compiler_fixture_empirical_rows == 0


def test_v26_95_budget_recovery_and_destructive_controls(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    budget = BudgetRecoveryAudit.model_validate_json(
        (output / "budget_recovery_audit.json").read_text(encoding="utf-8")
    )
    destructive = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )

    assert budget.first_execution_provider_call_count == 5
    assert budget.recovered_artifact_id == budget.recovery_artifact_id
    assert budget.raw_only_recovery_provider_call_count == 0
    assert budget.raw_only_recovery_byte_identical
    assert budget.oversized_prompt_denied_before_delegate
    assert budget.oversized_prompt_delegate_call_count == 0
    assert budget.orphan_provider_artifact_rejected
    assert budget.second_rescue_rejected_by_job_scope
    assert budget.explicit_request_kind_budget_certificates_passed
    assert destructive.rejected_mutation_count == 17
    assert all(item.rejected for item in destructive.mutation_results)
    assert destructive.model_api_calls == destructive.gpu_jobs == 0


def test_v26_95_interpretation_freezes_audited_four_way_decision(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    contract = ThinkingRepairOutcomeInterpretationContract.model_validate_json(
        (output / "outcome_interpretation_contract.json").read_text(encoding="utf-8")
    )

    assert contract.zero_failure_cp95_upper_bound <= contract.zero_failure_gate_threshold
    assert contract.one_failure_cp95_upper_bound > contract.zero_failure_gate_threshold
    assert contract.pass_transition == "thinking_role_protocol_freeze_only"
    assert (
        contract.length_failure_transition
        == "thinking_completion_bound_or_two_stage_protocol_redesign_only"
    )
    assert (
        contract.telemetry_only_failure_transition
        == "thinking_response_telemetry_wrapper_repair_only"
    )
    assert not contract.same_bound_prompt_only_retuning_after_length_failure_allowed
    assert contract.completion_success_cannot_establish_capability
    assert contract.low_program_closure_cannot_reopen_completion_optimization
    assert contract.telemetry_only_repair_must_hold_completion_protocol_fixed
    assert contract.fresh_role_population_required_after_pass


def test_v26_95_prepare_only_replays_before_client_construction(
    formal_build: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    preflight_dir, _ = formal_build
    prepared = prepare_thinking_repair_execution(
        runner_preflight_dir=preflight_dir,
        output_dir=tmp_path / "prepared",
        package_root=PACKAGE_ROOT,
    )

    assert prepared.execution_contract.execution_authorized
    assert len(prepared.manifest.jobs) == 32
    assert prepared.source_replay.replayed_file_count == 498
    assert not (tmp_path / "prepared" / "raw_execution").exists()
    assert not (tmp_path / "prepared" / "raw_provider_calls").exists()


def test_v26_95_artifacts_never_persist_private_reasoning(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in output.iterdir()
        if path.suffix == ".json"
    ]
    serialized = json.dumps(payloads, ensure_ascii=False, sort_keys=True)

    assert '"reasoning_content"' not in serialized
    assert '"private_reasoning"' not in serialized
    assert '"raw_http_body"' not in serialized
