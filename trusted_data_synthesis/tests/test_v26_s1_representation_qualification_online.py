from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


class _OnlineScriptedClient:
    def __init__(self, delegate: preflight.ScriptedS1QualificationClient) -> None:
        self.config = delegate.config
        self._delegate = delegate

    def complete_json_certified(self, prompt: str, certificate: Any) -> Any:
        payload, telemetry = self._delegate.complete_json_certified(prompt, certificate)
        telemetry = telemetry.model_copy(
            update={
                "response_shape": {
                    "provider_native_tool_call_observed": False,
                }
            }
        )
        return payload, telemetry


def _scripted_factory(config: Any, _job: Any, binding: Any) -> _OnlineScriptedClient:
    return _OnlineScriptedClient(
        preflight.ScriptedS1QualificationClient(
            config,
            final_answer=binding.compiler_trajectory.final_answer,
        )
    )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> online.PreparedExecution:
    output_dir = tmp_path_factory.mktemp("v26_134_prepare")
    return online.prepare_execution(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
    )


def test_v26_134_exact_scripted_denominator_and_zero_call_resume(
    prepared: online.PreparedExecution,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert prepared.source_replay.replayed_file_count == 3_225
    assert prepared.preexecution_binding.byte_identical_preflight_output_count == 15
    assert prepared.preexecution_binding.scripted_fixture_call_count == 256
    assert prepared.manifest.manifest_id == online.EXPECTED_MANIFEST_ID
    assert prepared.manifest.role_source_job_count == 0

    monkeypatch.setattr(online, "prepare_execution", lambda **_kwargs: prepared)
    output_dir = tmp_path / "execution"
    report = online.run_s1_representation_qualification(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_factory,
    )
    assert report.completed_job_result_count == 32
    assert report.terminal_counts == {"model_valid_trajectory": 32}
    assert report.provider_call_count == 256
    assert report.first_action_interface_qualified_job_count == 32
    assert report.qualified_mechanism_path_cell_count == 12
    assert report.combined_integrity_gate_failure_job_count == 0
    assert report.representation_qualification_gate_passed
    assert report.role_source_job_count == 0
    assert report.role_class_external_action_opportunity_count == 0
    assert report.stage_two_provider_call_count == 0
    assert report.next_permitted_stage == online.POSTRUN_STAGE

    def _forbidden_client(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("completed v26.134 replay constructed a client")

    recovered = online.run_s1_representation_qualification(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=_forbidden_client,
    )
    assert recovered == report


def test_v26_134_second_detour_is_measurement_support_exit(
    prepared: online.PreparedExecution,
    tmp_path: Path,
) -> None:
    job = next(
        item
        for item in prepared.manifest.jobs
        if item.predecessor_path_audit_id == preflight.EXPECTED_DETOUR_PATH_ID
    )

    def _detour_factory(config: Any, _job: Any, binding: Any) -> _OnlineScriptedClient:
        return _OnlineScriptedClient(
            preflight.ScriptedS1QualificationClient(
                config,
                final_answer=binding.compiler_trajectory.final_answer,
                force_action_id=preflight.EXPECTED_DETOUR_ACTION_ID,
                force_action_uses=2,
            )
        )

    result, raw, _ = online._run_one_job(  # noqa: SLF001
        job=job,
        prepared=prepared,
        client_factory=_detour_factory,
        output_dir=tmp_path / "detour",
    )
    assert raw.ordinary_detour_count == 2
    assert raw.later_provider_calls_after_detour_terminal == 0
    assert result.terminal_category == "ordinary_detour_allowance_exhausted"
    assert result.detour_measurement_support_exit
    assert not result.independent_trajectory_validity
    assert not result.instrument_failure
