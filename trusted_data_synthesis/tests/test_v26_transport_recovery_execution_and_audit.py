from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_online as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_failed_call_transport_recovery_preflight as recovery,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_transport_recovery_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = PACKAGE_ROOT / execution.PREFLIGHT_DIR
HISTORICAL_EXECUTION = PACKAGE_ROOT / recovery.HISTORICAL_EXECUTION_DIR
ONLINE_EXECUTION = PACKAGE_ROOT / audit.EXECUTION_DIR


class ExactTelemetryFixture(recovery.historical_preflight.ScriptedPrivacyFirstClient):
    def complete_json_certified(self, prompt: str, certificate: object):  # type: ignore[override]
        payload, telemetry = super().complete_json_certified(prompt, certificate)  # type: ignore[arg-type]
        shape = dict(telemetry.response_shape)
        shape["provider_native_tool_call_observed"] = False
        return payload, telemetry.model_copy(update={"response_shape": shape})


def _fixture_factory(config: object, _job: object, binding: object) -> ExactTelemetryFixture:
    return ExactTelemetryFixture(
        config,  # type: ignore[arg-type]
        final_answer=binding.compiler_trajectory.final_answer,  # type: ignore[attr-defined]
    )


def test_recovery_execution_closes_scripted_model_endpoint_denominator(
    tmp_path: Path,
) -> None:
    output = tmp_path / "execution"
    report = execution.run_recovery_execution(
        preflight_dir=PREFLIGHT,
        historical_execution_dir=HISTORICAL_EXECUTION,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=4,
        client_factory=_fixture_factory,  # type: ignore[arg-type]
    )
    assert report.recovery_terminal_counts == {"model_valid_trajectory": 10}
    assert report.successor_provider_call_count == 74
    assert report.combined_model_outcome_count == 32
    assert report.combined_valid_count == 21
    assert report.exact_32_model_endpoint_denominator_complete is True
    assert report.original_failed_call_usage_imputation_count == 0

    resumed = execution.run_recovery_execution(
        preflight_dir=PREFLIGHT,
        historical_execution_dir=HISTORICAL_EXECUTION,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=4,
        client_factory=_fixture_factory,  # type: ignore[arg-type]
    )
    assert resumed == report


def test_transport_recovery_postrun_audit_is_reproducible(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    independent = tmp_path / "independent"
    first = audit.build_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=ONLINE_EXECUTION,
        output_dir=formal,
    )
    second = audit.build_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=ONLINE_EXECUTION,
        output_dir=independent,
    )
    assert first == second
    assert first.status == "engineering_kernel_qualified"
    assert first.exact_model_endpoint_denominator == 32
    assert first.independently_valid_count == 19
    assert first.model_invalid_count == 13
    assert first.transport_failure_count == 0
    assert first.instrument_failure_count == 0
    assert first.provider_calls == 0
    assert first.next_permitted_stage == audit.NEXT_STAGE
    assert sorted(path.name for path in formal.iterdir()) == sorted(
        path.name for path in independent.iterdir()
    )
    for formal_path in formal.iterdir():
        assert formal_path.read_bytes() == (independent / formal_path.name).read_bytes()
