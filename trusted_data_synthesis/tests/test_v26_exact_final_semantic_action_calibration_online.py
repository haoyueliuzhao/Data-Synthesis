from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_final_semantic_action_calibration_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
RUNNER_PREFLIGHT_DIR = EVIDENCE_ROOT / online.PREFLIGHT_DIR


class OnlineTelemetryScriptedClient(preflight.ScriptedPrivacyFirstClient):
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


def test_v26_124_scripted_execution_closes_action_final_and_privacy_funnels(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "execution"
    report = online.run_exact_final_semantic_action_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=_scripted_client,
    )
    assert report.run_id == online.RUN_ID
    assert report.source_replay_audit_id.startswith(
        "finance_v26_exact_final_execution_source_replay:"
    )
    assert report.runner_contract_id == online.EXPECTED_RUNNER_CONTRACT_ID
    assert report.outcome_measurement_contract_id == online.EXPECTED_OUTCOME_CONTRACT_ID
    assert report.terminal_counts == {"model_valid_trajectory": 32}
    assert report.provider_call_count == 256
    assert report.provider_envelope_count == 256
    assert report.public_payload_projection_count == 256
    assert report.validated_public_payload_count == 256
    assert report.privacy_rejected_payload_count == 0
    assert report.provider_failure_no_payload_count == 0
    assert report.envelope_only_orphan_count == 0
    assert report.projection_only_orphan_count == 0
    assert report.complete_raw_count == 32
    assert report.exact_four_field_action_payload_count == 224
    assert report.semantic_choice_count == 224
    assert report.visible_action_id_match_count == 224
    assert report.decision_kind_match_count == 224
    assert report.first_choice_accepted_count == 224
    assert report.reversible_stage_two_commit_count == 224
    assert report.runtime_observation_count == 192
    assert report.program_closed_count == 32
    assert report.terminal_node_completed_count == 32
    assert report.postterminal_verification_completed_count == 32
    assert report.final_commit_count == 32
    assert report.final_request_attempt_count == 32
    assert report.final_response_payload_count == 32
    assert report.exact_two_field_final_payload_count == 32
    assert report.final_primary_exact_payload_job_count == 32
    assert report.final_rescue_exact_payload_job_count == 0
    assert report.final_abi_crossed_job_count == 32
    assert report.final_answer_emitted_job_count == 32
    assert report.final_answer_semantically_valid_job_count == 32
    assert report.independently_valid_trajectory_count == 32
    assert report.instrument_failure_job_count == 0
    assert report.privacy_artifact_pairing_passed
    assert report.stage_two_provider_call_count == 0
    assert report.capability_rows == report.state_mapping_rows == 0
    assert report.next_permitted_stage == (
        "exact_final_semantic_action_calibration_postrun_audit_only"
    )

    lineage = online.ExactFinalRawLineageAudit.model_validate(
        online._load(output_dir / "raw_lineage_audit.json")
    )
    assert lineage.file_count == 544
    assert lineage.complete_provider_pair_count == 256
    assert lineage.private_reasoning_payload_count == 0
    assert lineage.invalid_payload_content_persistence_count == 0
    assert lineage.invalid_payload_key_persistence_count == 0

    def fail_if_called(_config: Any, _job: Any, _binding: Any) -> Any:
        raise AssertionError("completed v26.124 recovery constructed a model client")

    recovered = online.run_exact_final_semantic_action_calibration(
        runner_preflight_dir=RUNNER_PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=fail_if_called,
    )
    assert recovered == report
