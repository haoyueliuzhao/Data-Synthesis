from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as runner,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_calibration_online import (  # noqa: E501
    EXPECTED_RUNNER_CONTRACT_ID,
    PREFLIGHT_DIR,
    prepare_execution,
    project_job_result,
    run_semantic_action_calibration,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_runner_preflight import (  # noqa: E501
    ScriptedSemanticActionClient,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
RUNNER_PREFLIGHT_DIR = EVIDENCE_ROOT / PREFLIGHT_DIR


class OnlineTelemetryScriptedClient(ScriptedSemanticActionClient):
    def complete_json_certified(self, prompt: str, certificate: Any) -> tuple[dict[str, Any], Any]:
        payload, telemetry = super().complete_json_certified(prompt, certificate)
        return payload, telemetry.model_copy(
            update={"response_shape": {"provider_native_tool_call_observed": False}}
        )


def _scripted_client(config: Any, _job: Any, binding: Any) -> Any:
    return OnlineTelemetryScriptedClient(
        config,
        final_answer=binding.compiler_trajectory.final_answer,
    )


def test_v26_120_scripted_execution_closes_choice_and_outcome_funnels(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "execution"
    report = run_semantic_action_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_client,
    )
    assert report.runner_contract_id == EXPECTED_RUNNER_CONTRACT_ID
    assert report.provider_call_count == 256
    assert report.exact_four_field_proposal_count == 224
    assert report.semantic_choice_count == 224
    assert report.visible_action_id_match_count == 224
    assert report.decision_kind_match_count == 224
    assert report.first_choice_accepted_count == 224
    assert report.reversible_stage_two_commit_count == 224
    assert report.runtime_observation_count == 192
    assert report.public_progress_choice_count == 144
    assert report.program_node_progress_choice_count == 48
    assert report.singleton_choice_count == 64
    assert report.multi_candidate_choice_count == 160
    assert report.candidate_count_distribution == {
        "1": 64,
        "2": 22,
        "3": 38,
        "4": 39,
        "5": 13,
        "6": 23,
        "7": 5,
        "8": 20,
    }
    assert report.selected_prompt_only_reference_count == 224
    assert report.legal_no_progress_choice_count == 48
    assert report.ordinary_replan_after_legal_no_progress_count == 48
    assert report.ordinary_replan_eventual_progress_count == 48
    assert report.terminal_verification_choice_count == 32
    assert report.successful_terminal_verification_observation_count == 32
    assert report.final_commit_count == 32
    assert report.final_answer_count == 32
    assert report.program_closed_count == 32
    assert report.mechanism_success_count == 32
    assert report.independently_valid_trajectory_count == 32
    assert report.instrument_failure_job_count == 0
    assert report.stage_two_provider_call_count == 0
    assert report.capability_rows == report.state_mapping_rows == 0
    assert report.next_permitted_stage == "semantic_action_calibration_postrun_audit_only"

    def fail_if_called(_config: Any, _job: Any, _binding: Any) -> Any:
        raise AssertionError("completed v26.120 recovery constructed a model client")

    replayed = run_semantic_action_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=fail_if_called,
    )
    assert replayed == report


def test_v26_120_keeps_abi_and_semantic_recovery_outcomes_separate(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "combined_recovery"
    prepared = prepare_execution(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
    )
    job = prepared.static.manifest.jobs[0]
    binding = runner.semantic_action_runtime_binding(prepared.static, job)
    raw = runner.execute_semantic_action_job_raw(
        job=job,
        runner_contract=prepared.runner_contract,
        static=prepared.static,
        binding=binding,
        client=OnlineTelemetryScriptedClient(
            prepared.static.agent_model_config,
            final_answer=binding.compiler_trajectory.final_answer,
            combined_recovery_control=True,
        ),
        output_dir=output_dir,
    )
    result, diagnostics = project_job_result(
        raw=raw,
        prepared=prepared,
        output_dir=output_dir,
    )
    assert raw.abi_rescue_attempt_count == 1
    assert len(raw.semantic_rejections) == 1
    assert result.semantic_rejection_count == 1
    assert result.semantic_recovery_used
    assert result.recovery_selected_different_action
    assert result.recovery_committed
    assert result.recovery_public_progress
    assert result.first_action_id_legal is False
    assert result.first_action_semantically_accepted is False
    assert diagnostics[0].response_attempt_phase == "abi_rescue"
    assert diagnostics[0].visible_action_id_match is False
    assert diagnostics[0].selected_zero_based_position is None
    assert diagnostics[1].choice_phase == "semantic_recovery"
    assert diagnostics[1].semantic_accepted
    assert diagnostics[1].public_progress_after_commit
    assert result.independent_validity
