from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_recovery import (  # noqa: E501
    FAILED_EXECUTION_BINDING_ID,
    FAILED_PROVIDER_CALL_COUNT,
    RecoveryContract,
    RecoveryExecutionReport,
    RecoveryJob,
    RecoveryManifest,
    RecoveryPreflightReport,
    build_recovery_preflight,
    run_verifier_bound_instrument_recovery,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
FAILED_RUN = ARTIFACT_ROOT / "finance_v26_78_verifier_bound_instrument_requalification_20260820"
PREFLIGHT = ARTIFACT_ROOT / "finance_v26_79_verifier_bound_recovery_preflight_20260820"
FORMAL = ARTIFACT_ROOT / "finance_v26_80_verifier_bound_instrument_recovery_20260820"
FAILED_RUN_ID = "finance_v26_78_verifier_bound_instrument_requalification_20260820"
RECOVERY_RUN_ID = "finance_v26_80_verifier_bound_instrument_recovery_20260820"
EXPECTED_PREFLIGHT_ID = (
    "finance_v26_verifier_bound_recovery_preflight:"
    "a25d500a2ea292f2274b7b1e305d4f5bfadc9b82b8ebaa0ee59474368aff8ccc"
)
PREFLIGHT_FILES = (
    "failed_run_audit.json",
    "failed_run_job_audits.json",
    "raw_provider_artifact_manifest.json",
    "recovery_source_replay_audit.json",
    "recovery_contract.json",
    "recovery_manifest.json",
    "recovery_execution_binding.json",
    "report.json",
)


def _prepare(output: Path) -> None:
    build_recovery_preflight(
        recovery_run_id=RECOVERY_RUN_ID,
        failed_run_id=FAILED_RUN_ID,
        failed_run_dir=FAILED_RUN,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_79_recovery_preflight")
    _prepare(output)
    return output


def test_v26_79_preflight_is_zero_api_and_deterministic(
    prepared: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _prepare(duplicate)
    for relative in PREFLIGHT_FILES:
        assert (prepared / relative).read_bytes() == (duplicate / relative).read_bytes()

    report = RecoveryPreflightReport.model_validate_json(
        (prepared / "report.json").read_text(encoding="utf-8")
    )
    assert report.report_id == EXPECTED_PREFLIGHT_ID
    assert report.source_replay_file_count == report.source_replay_pass_count == 73
    assert report.original_provider_artifact_replay_count == 146
    assert report.exposed_job_zero_generation_replay_count == 17
    assert report.unopened_job_count == 15
    assert report.exposed_job_model_call_count == report.historical_job_retry_count == 0
    assert report.model_api_calls == report.gpu_jobs == 0
    assert not report.model_client_constructed
    assert report.recovery_execution_authorized
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert report.production_contribution == 0


def test_v26_79_audits_the_complete_failed_provider_stream(prepared: Path) -> None:
    audit = json.loads((prepared / "failed_run_audit.json").read_text(encoding="utf-8"))
    assert audit["failed_execution_binding_id"] == FAILED_EXECUTION_BINDING_ID
    assert audit["exposed_job_count"] == 17
    assert audit["unopened_job_count"] == 15
    assert audit["raw_provider_call_artifact_count"] == FAILED_PROVIDER_CALL_COUNT
    assert audit["provider_total_tokens"] == 1_336_075
    assert audit["completed_trajectory_replay_count"] == 5
    assert audit["model_contract_failure_replay_count"] == 12
    assert audit["recovered_observation_count"] == 118
    assert audit["raw_execution_artifact_count"] == 0
    assert audit["rollout_checkpoint_count"] == 0
    assert audit["historical_model_calls_repeated"] is False
    assert len(audit["job_audits"]) == 17
    assert all(row["prompts_exact"] for row in audit["job_audits"])
    assert all(
        row["provider_telemetry_equal_before_host_augmentation"] for row in audit["job_audits"]
    )
    assert all(row["zero_generation_replay_passed"] for row in audit["job_audits"])


def test_v26_79_manifest_partitions_jobs_before_outcomes(prepared: Path) -> None:
    contract = RecoveryContract.model_validate_json(
        (prepared / "recovery_contract.json").read_text(encoding="utf-8")
    )
    manifest = RecoveryManifest.model_validate_json(
        (prepared / "recovery_manifest.json").read_text(encoding="utf-8")
    )
    replay = tuple(item for item in manifest.jobs if item.recovery_role == "zero_generation_replay")
    continuation = tuple(
        item for item in manifest.jobs if item.recovery_role == "unopened_model_continuation"
    )
    assert len(replay) == 17
    assert len(continuation) == 15
    assert {item.original_job.job_id for item in replay} == set(contract.exposed_job_ids)
    assert {item.original_job.job_id for item in continuation} == set(contract.unopened_job_ids)
    assert all(not item.model_call_permitted for item in replay)
    assert all(item.model_call_permitted for item in continuation)
    assert all(
        item.original_provider_capture_binding_id == FAILED_EXECUTION_BINDING_ID for item in replay
    )
    assert all(item.original_provider_capture_binding_id is None for item in continuation)
    assert contract.no_job_selected_by_model_outcome
    assert contract.provider_vs_host_telemetry_comparison_rule == (
        "provider_fields_equal_before_prompt_component_bytes_augmentation"
    )


def test_recovery_job_rejects_exposed_model_call_authority(prepared: Path) -> None:
    manifest = RecoveryManifest.model_validate_json(
        (prepared / "recovery_manifest.json").read_text(encoding="utf-8")
    )
    replay = next(item for item in manifest.jobs if item.recovery_role == "zero_generation_replay")
    payload = replay.model_dump(mode="json")
    payload["model_call_permitted"] = True
    with pytest.raises(ValidationError, match="model-call authority"):
        RecoveryJob.model_validate(payload)


def test_recovery_contract_rejects_partition_overlap(prepared: Path) -> None:
    payload = json.loads((prepared / "recovery_contract.json").read_text(encoding="utf-8"))
    payload["unopened_job_ids"][0] = payload["exposed_job_ids"][0]
    with pytest.raises(ValidationError, match="partition is invalid"):
        RecoveryContract.model_validate(payload)


def test_formal_v26_80_recovery_result_and_authorization() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.80 Recovery execution has not completed yet")
    report = RecoveryExecutionReport.model_validate_json(
        (FORMAL / "report.json").read_text(encoding="utf-8")
    )
    result = report.instrument_result
    assert report.zero_generation_replayed_job_count == 17
    assert report.continuation_model_job_count == 15
    assert report.exposed_job_model_call_count == 0
    assert report.original_provider_call_count == 146
    assert result.completed_rollout_count == result.expected_rollout_count == 32
    assert result.model_outcome_count == 25
    assert result.runtime_failure_count == 0
    assert result.instrument_failure_count == 7
    assert result.exact_requested_model_count == 32
    assert result.fallback_count == 0
    assert result.replay_pass_count == 32
    assert result.raw_integrity_audit.status == "failed"
    assert report.raw_lineage_audit.status == "failed"
    assert report.raw_lineage_audit.original_provider_artifact_count == 146
    assert report.raw_lineage_audit.original_provider_exact_byte_pass_count == 146
    assert report.raw_lineage_audit.provider_artifact_binding_pass_count == 269
    assert not report.raw_first_recovery_lineage_passed
    assert not report.resource_budget_passed
    assert not report.recovery_instrument_ready
    assert report.status == "blocked"
    assert report.next_permitted_stage == "resource_budget_audit_only"
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert report.production_contribution == 0


def test_completed_recovery_replay_constructs_no_model_client() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.80 Recovery execution has not completed yet")
    report_before = (FORMAL / "report.json").read_bytes()

    def fail_client(_: AgentModelConfig) -> Any:
        raise AssertionError("completed Recovery Replay constructed a model client")

    report = run_verifier_bound_instrument_recovery(
        recovery_run_id=RECOVERY_RUN_ID,
        failed_run_id=FAILED_RUN_ID,
        failed_run_dir=FAILED_RUN,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=FORMAL,
        package_root=PACKAGE_ROOT,
        workers=2,
        client_factory=fail_client,
    )
    assert not report.recovery_instrument_ready
    assert report.status == "blocked"
    assert (FORMAL / "report.json").read_bytes() == report_before
