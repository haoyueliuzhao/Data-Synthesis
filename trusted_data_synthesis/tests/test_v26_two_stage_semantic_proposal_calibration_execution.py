from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_execution import (  # noqa: E501
    EXPECTED_RUNNER_CONTRACT_ID,
    POSTRUN_AUDIT_TRANSITION,
    PreparedExecution,
    TwoStageExecutionReport,
    prepare_two_stage_execution,
    run_two_stage_calibration,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_runner_preflight import (  # noqa: E501
    ScriptedStageOneClient,
    _compiler_calls,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PACKAGE_ROOT = Path(
    "/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis"
)
PACKAGE_ROOT = CANONICAL_PACKAGE_ROOT if CANONICAL_PACKAGE_ROOT.is_dir() else LOCAL_PACKAGE_ROOT
RUNNER_DIR = (
    LOCAL_PACKAGE_ROOT
    / "artifacts/vtdo_experiment"
    / "finance_v26_109_two_stage_semantic_proposal_runner_preflight_v1_20260822"
)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> PreparedExecution:
    return prepare_two_stage_execution(
        runner_preflight_dir=RUNNER_DIR,
        output_dir=tmp_path_factory.mktemp("v26_110_prepare"),
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )


def test_v26_110_prepare_replays_exact_authorized_denominator(
    prepared: PreparedExecution,
) -> None:
    assert prepared.source_replay.replayed_file_count == 1911
    assert prepared.source_replay.replay_pass_count == 1911
    assert prepared.source_replay.credential_lookup_attempted is False
    assert prepared.source_replay.model_client_constructed is False
    assert prepared.source_replay.provider_calls == 0
    assert prepared.runner_contract.contract_id == EXPECTED_RUNNER_CONTRACT_ID
    assert len(prepared.static.manifest.jobs) == 32
    assert prepared.static.resource.rollout_upper_bound_tokens == 260000
    assert prepared.static.stage_two.provider_call_upper_bound == 0
    assert prepared.preexecution_validity.independently_valid_count == 32
    assert prepared.preexecution_validity.replay_v3_pass_count == 32
    assert prepared.preexecution_validity.mechanism_success_count == 32
    assert prepared.preexecution_validity.real_provider_calls == 0
    assert prepared.preexecution_validity.stage_two_provider_call_count == 0


class _TelemetryCompleteScriptedClient(ScriptedStageOneClient):
    def complete_json_certified(self, prompt: str, certificate: Any) -> Any:
        payload, telemetry = super().complete_json_certified(prompt, certificate)
        response_shape = dict(telemetry.response_shape)
        response_shape["provider_native_tool_call_observed"] = False
        return payload, ModelCallTelemetry.model_validate(
            {
                **telemetry.model_dump(mode="json"),
                "response_shape": response_shape,
            }
        )


def _scripted_factory(
    config: AgentModelConfig,
    _job: Any,
    binding: Any,
) -> _TelemetryCompleteScriptedClient:
    return _TelemetryCompleteScriptedClient(
        config,
        compiler_calls=_compiler_calls(binding),
        final_answer=binding.compiler_trajectory.final_answer,
    )


def test_v26_110_full_scripted_denominator_and_recovery(
    tmp_path: Path,
) -> None:
    report = run_two_stage_calibration(
        runner_preflight_dir=RUNNER_DIR,
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_factory,
    )
    assert report.completed_job_result_count == 32
    assert report.terminal_counts == {"model_valid_trajectory": 32}
    assert report.provider_call_count == 256
    assert report.stage_two_provider_call_count == 0
    assert report.stage_two_authority_passed
    assert report.replay_v3_passed
    assert report.independently_valid_trajectory_count == 32
    assert report.next_permitted_stage == POSTRUN_AUDIT_TRANSITION

    def forbidden_factory(
        _config: AgentModelConfig,
        _job: Any,
        _binding: Any,
    ) -> Any:
        raise AssertionError("completed v26.110 replay constructed a client")

    recovered = run_two_stage_calibration(
        runner_preflight_dir=RUNNER_DIR,
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
        workers=8,
        client_factory=forbidden_factory,
    )
    assert recovered == report


def test_v26_110_report_schema_rejects_denominator_mutation(
    tmp_path: Path,
) -> None:
    report = run_two_stage_calibration(
        runner_preflight_dir=RUNNER_DIR,
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_factory,
    )
    mutated = report.model_dump(mode="json")
    mutated["completed_job_result_count"] = 31
    with pytest.raises(ValidationError):
        TwoStageExecutionReport.model_validate(mutated)
