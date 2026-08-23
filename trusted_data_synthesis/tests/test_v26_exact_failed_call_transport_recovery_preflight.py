from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_preflight as recovery,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_AUDIT = PACKAGE_ROOT / recovery.HISTORICAL_AUDIT_DIR
HISTORICAL_EXECUTION = PACKAGE_ROOT / recovery.HISTORICAL_EXECUTION_DIR


def test_recovery_preflight_is_credential_free_and_reproducible(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    independent = tmp_path / "independent"
    first = recovery.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        historical_audit_dir=HISTORICAL_AUDIT,
        historical_execution_dir=HISTORICAL_EXECUTION,
        output_dir=formal,
    )
    second = recovery.build_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        historical_audit_dir=HISTORICAL_AUDIT,
        historical_execution_dir=HISTORICAL_EXECUTION,
        output_dir=independent,
    )

    assert first == second
    assert first.status == "passed_exact_transport_recovery_preflight"
    assert first.exact_recovery_job_count == 10
    assert first.historical_model_outcome_count == 22
    assert first.scripted_provider_calls == 74
    assert first.real_provider_calls == 0
    assert first.stage_two_provider_calls == 0
    assert first.next_permitted_stage == recovery.NEXT_STAGE
    assert sorted(path.name for path in formal.iterdir()) == sorted(
        path.name for path in independent.iterdir()
    )
    for formal_path in formal.iterdir():
        assert formal_path.read_bytes() == (independent / formal_path.name).read_bytes()

    prepared = recovery.load_prepared_recovery(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        preflight_dir=formal,
    )
    assert len(prepared.recovery_manifest.jobs) == 10
    assert len({item.recovery_job_id for item in prepared.recovery_manifest.jobs}) == 10
    assert {
        item.successful_prefix_provider_call_count for item in prepared.recovery_manifest.jobs
    } == {0, 1, 2}
    assert prepared.recovery_contract.provider_calls_authorized is False


def test_exact_failed_call_replacement_stops_after_one_transport_failure(
    tmp_path: Path,
) -> None:
    prepared = recovery.prepare_recovery_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        historical_audit_dir=HISTORICAL_AUDIT,
        historical_execution_dir=HISTORICAL_EXECUTION,
        output_dir=tmp_path / "prepared",
    )
    job = next(
        item
        for item in prepared.recovery_manifest.jobs
        if item.successful_prefix_provider_call_count == 0
    )
    prefix = recovery.replay_successful_prefix(
        recovery_job=job,
        static=prepared.static,
        historical_runner_contract=prepared.historical_runner_contract,
        historical_execution_dir=HISTORICAL_EXECUTION,
    )
    assert prefix.replay.historical_prefix_provider_calls_reissued == 0
    assert prefix.replay.historical_failed_call_reissued == 0
    assert prefix.replay.exact_failed_prompt_sha256 == job.candidate.request_prompt_sha256
    assert prefix.replay.exact_failed_dynamic_certificate_id == job.candidate.dynamic_certificate_id

    client = recovery.ScriptedTransportFailureClient(prepared.static.agent_model_config)
    raw = recovery.execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=HISTORICAL_EXECUTION,
        client=client,
        output_dir=tmp_path / "transport_failure",
    )
    assert raw.terminal_disposition == "provider_transport_failure"
    assert raw.successor_provider_call_count == 1
    assert raw.exact_failed_call_replacement_attempt_count == 1
    assert raw.original_failed_call_usage_imputed is False
    assert client.call_count == 1

    recovered = recovery.execute_recovery_job_raw(
        recovery_job=job,
        runner_contract=prepared.runner_contract,
        historical_runner_contract=prepared.historical_runner_contract,
        static=prepared.static,
        historical_execution_dir=HISTORICAL_EXECUTION,
        client=None,
        output_dir=tmp_path / "transport_failure",
    )
    assert recovered == raw
