from __future__ import annotations

import hashlib
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    wilson_interval,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_transport_recovery import (
    RETRYABLE_FAILURE_REASON,
    build_transport_recovery_authorization,
    run_transport_recovery,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
SOURCE_DIR = ARTIFACT_ROOT / "finance_v26_57_empirical_support_pilot_20260818"
V26_56_SOURCE_DIR = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"
MODEL_CONFIG = PACKAGE_ROOT / "config" / "deepseek_v4_flash_agent_v23_paired_pilot.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_transport_recovery_authorizes_only_the_single_runtime_failure() -> None:
    authorization = build_transport_recovery_authorization(
        run_id="finance_v26_58_transport_recovery_test",
        source_dir=SOURCE_DIR,
        package_root=PACKAGE_ROOT,
    )

    assert authorization.status == "authorized"
    assert authorization.source_failure_reason == RETRYABLE_FAILURE_REASON
    assert authorization.transient_failure_call_count == 1
    assert authorization.successful_recovery_call_count == 4
    assert authorization.repeated_request_hash_count == 1
    assert authorization.authorized_retry_count == 1
    assert authorization.authorized_job_ids == (authorization.source_job_id,)
    assert authorization.model_invalid_outcomes_not_retryable
    assert authorization.result_quality_blind_authorization
    assert authorization.no_other_job_authorized


def test_wilson_boundary_clamp_is_exact() -> None:
    zero_lower, zero_upper = wilson_interval(0, 6)
    full_lower, full_upper = wilson_interval(6, 6)

    assert zero_lower == 0.0
    assert 0.0 < zero_upper < 1.0
    assert 0.0 < full_lower < 1.0
    assert full_upper == 1.0


def test_transport_recovery_preflight_is_credential_free_and_deterministic(
    tmp_path: Path,
) -> None:
    source_hash_before = _sha256(SOURCE_DIR / "report.json")
    outputs = (tmp_path / "first", tmp_path / "second")
    reports = []
    for output in outputs:
        reports.append(
            run_transport_recovery(
                run_id="finance_v26_58_transport_recovery_preflight_test",
                source_dir=SOURCE_DIR,
                v26_56_source_dir=V26_56_SOURCE_DIR,
                model_config_path=MODEL_CONFIG,
                output_dir=output,
                package_root=PACKAGE_ROOT,
                audit_only=True,
            )
        )

    assert reports[0] == reports[1]
    assert reports[0].status == "preflight"
    assert reports[0].replacement_count == 0
    assert reports[0].model_api_call_count == 0
    assert reports[0].next_permitted_stage == "single_authorized_transport_retry"
    assert _sha256(SOURCE_DIR / "report.json") == source_hash_before
    for name in ("transport_recovery_authorization.json", "report.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
