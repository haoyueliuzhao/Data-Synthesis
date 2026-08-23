from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_execution import (  # noqa: E501
    EXPECTED_RUNNER_CONTRACT_ID,
    run_two_stage_calibration,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_runner_preflight import (  # noqa: E501
    ScriptedExactGrammarClient,
    _compiler_calls,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
RUNNER_PREFLIGHT_DIR = EVIDENCE_ROOT / (
    "artifacts/vtdo_experiment/finance_v26_113_exact_response_grammar_runner_preflight_v1_20260823"
)


class OnlineTelemetryScriptedClient(ScriptedExactGrammarClient):
    def complete_json_certified(self, prompt: str, certificate: Any) -> tuple[dict[str, Any], Any]:
        payload, telemetry = super().complete_json_certified(prompt, certificate)
        return payload, telemetry.model_copy(
            update={"response_shape": {"provider_native_tool_call_observed": False}}
        )


def _scripted_client(config: Any, _job: Any, binding: Any) -> ScriptedExactGrammarClient:
    return OnlineTelemetryScriptedClient(
        config,
        compiler_calls=_compiler_calls(binding),
        final_answer=binding.compiler_trajectory.final_answer,
    )


def test_v26_114_scripted_execution_closes_the_full_funnel(tmp_path: Path) -> None:
    output_dir = tmp_path / "execution"
    report = run_two_stage_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_client,
    )
    assert report.runner_contract_id == EXPECTED_RUNNER_CONTRACT_ID
    assert report.provider_call_count == 256
    assert report.semantic_proposal_response_payload_count == 224
    assert report.exact_abi_accepted_count == 224
    assert report.exact_abi_failure_count == 0
    assert report.wrong_state_binding_count == 0
    assert report.semantic_proposal_commit_count == 224
    assert report.observation_count == 192
    assert report.no_rescue_job_count == 32
    assert report.rescue_recovered_job_count == 0
    assert report.program_closed_count == 32
    assert report.mechanism_success_count == 32
    assert report.independently_valid_trajectory_count == 32
    assert report.stage_two_provider_call_count == 0
    assert report.next_permitted_stage == "exact_response_grammar_calibration_postrun_audit_only"

    def fail_if_called(_config: Any, _job: Any, _binding: Any) -> Any:
        raise AssertionError("completed v26.114 recovery constructed a client")

    replayed = run_two_stage_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=fail_if_called,
    )
    assert replayed == report
