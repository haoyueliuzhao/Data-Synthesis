from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_orphan_support_exit_recovery_execution as execution,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_EXECUTION_DIR = PACKAGE_ROOT / execution.failed_audit.EXECUTION_DIR
FAILED_AUDIT_DIR = PACKAGE_ROOT / execution.failed_audit.OUTPUT_DIR
PREFLIGHT_DIR = PACKAGE_ROOT / execution.preflight.OUTPUT_DIR


@pytest.fixture(scope="module")
def executed(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[execution.RecoveryExecutionReport, Path]:
    output_dir = tmp_path_factory.mktemp("v26_144_execution")
    report = execution.run_recovery_execution(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        historical_execution_dir=HISTORICAL_EXECUTION_DIR,
        failed_audit_dir=FAILED_AUDIT_DIR,
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
    )
    return report, output_dir


def test_v26_144_exact_binding_and_zero_call_execution(
    executed: tuple[execution.RecoveryExecutionReport, Path],
) -> None:
    report, output_dir = executed
    source = execution.ExecutionSourceReplayAudit.model_validate_json(
        (output_dir / "online_source_replay_audit.json").read_text(encoding="utf-8")
    )
    binding = execution.ExecutionPreflightBindingAudit.model_validate_json(
        (output_dir / "preexecution_binding_audit.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 7_256
    assert source.preflight_transitive_file_count == 7_242
    assert source.preflight_output_file_count == 13
    assert source.credential_lookup_attempted is False
    assert source.model_client_constructed is False
    assert source.provider_calls == 0
    assert binding.preflight_output_count == binding.byte_identical_preflight_output_count == 13
    assert binding.recovery_manifest_id == execution.EXPECTED_MANIFEST_ID
    assert binding.runner_contract_id == execution.EXPECTED_RUNNER_ID
    assert binding.outcome_contract_id == execution.EXPECTED_OUTCOME_ID
    assert binding.prospective_execution_id == execution.EXPECTED_EXECUTION_ID
    assert binding.prospective_report_id == execution.EXPECTED_REPORT_IDENTITY
    assert binding.exact_recovery_job_count == 3
    assert binding.fresh_recovery_job_identity_count == 3
    assert binding.provider_call_upper_bound == 0
    assert binding.provider_calls == 0

    assert report.status == "completed_zero_call_support_exit_recovery"
    assert report.pre_registered_report_identity == execution.EXPECTED_REPORT_IDENTITY
    assert report.prospective_execution_id == execution.EXPECTED_EXECUTION_ID
    assert report.exact_recovery_job_count == 3
    assert report.completed_recovery_raw_count == 3
    assert report.typed_support_exit_count == 3
    assert report.fresh_provider_call_count == 0
    assert report.stage_two_provider_call_count == 0
    assert report.credential_lookup_attempted is False
    assert report.model_client_constructed is False
    assert report.historical_terminal_reclassification_count == 0
    assert not report.exact_capability_gate_passed
    assert report.next_permitted_stage == execution.NEXT_STAGE


def test_v26_144_raw_endpoint_and_transition_are_closed(
    executed: tuple[execution.RecoveryExecutionReport, Path],
) -> None:
    _report, output_dir = executed
    raw_paths = sorted((output_dir / "raw_executions").glob("*.json"))
    result_paths = sorted((output_dir / "job_results").glob("*.json"))
    raws = tuple(
        execution.RecoveryRawExecution.model_validate_json(path.read_text(encoding="utf-8"))
        for path in raw_paths
    )
    results = tuple(
        execution.RecoveryJobResult.model_validate_json(path.read_text(encoding="utf-8"))
        for path in result_paths
    )
    checkpoint_rows = tuple(
        execution.RecoveryJobResult.model_validate_json(line)
        for line in (output_dir / "checkpoint_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    lineage = execution.RawLineageAudit.model_validate_json(
        (output_dir / "raw_lineage_audit.json").read_text(encoding="utf-8")
    )
    endpoint = execution.EndpointOutcomeAudit.model_validate_json(
        (output_dir / "endpoint_outcome_audit.json").read_text(encoding="utf-8")
    )
    transition = execution.PostrunTransitionContract.model_validate_json(
        (output_dir / "prospective_transition_contract.json").read_text(encoding="utf-8")
    )

    assert len(raws) == len(results) == len(checkpoint_rows) == 3
    assert {item.recovery_job.recovery_job_id for item in raws} == {
        item.recovery_job_id for item in results
    }
    assert all(item.terminal_disposition == execution.preflight.TYPED_TERMINAL for item in raws)
    assert all(item.observation_error_code == "typed_selector_requires_refinement" for item in raws)
    assert all(item.exact_model_action_commit_observation_preserved for item in raws)
    assert all(item.historical_prefix_provider_calls_reissued == 0 for item in raws)
    assert all(item.new_provider_calls == item.later_provider_calls == 0 for item in raws)
    assert all(item.stage_two_provider_calls == 0 for item in raws)
    assert all(not item.historical_raw_execution_created for item in raws)
    assert all(not item.historical_terminal_assigned for item in raws)
    assert all(item.support_exit_counts_as_measurement_support_boundary for item in raws)
    assert all(not item.support_exit_counts_as_model_invalid for item in raws)
    assert all(not item.support_exit_counts_as_instrument_failure for item in raws)
    assert all(item.measurement_support_boundary_exit for item in results)
    assert all(not item.model_outcome for item in results)
    assert all(not item.instrument_failure for item in results)

    assert lineage.exact_recovery_raw_count == lineage.exact_recovery_result_count == 3
    assert lineage.checkpoint_result_count == lineage.typed_support_exit_count == 3
    assert lineage.new_provider_call_count == 0
    assert lineage.historical_raw_or_terminal_creation_count == 0
    assert endpoint.frozen_complete_raw_model_outcome_count == 93
    assert endpoint.fresh_recovery_support_exit_count == 3
    assert endpoint.exact_lineage_endpoint_count == 96
    assert endpoint.frozen_model_valid_trajectory_count == 17
    assert endpoint.frozen_model_invalid_trajectory_count == 76
    assert endpoint.measurement_support_boundary_exit_count == 3
    assert endpoint.instrument_failure_count == 0
    assert not endpoint.exact_capability_gate_passed
    assert not endpoint.exact_task_weighted_capability_estimate_available
    assert not endpoint.reachability_authorized

    assert transition.next_permitted_stage == execution.NEXT_STAGE
    assert transition.independent_postrun_audit_required
    assert not transition.provider_calls_authorized
    assert not transition.capability_continuation_authorized
    assert not transition.historical_job_rerun_or_reclassification_authorized
    assert not transition.historical_raw_or_terminal_creation_authorized
    assert not transition.reachability_identity_or_execution_authorized
