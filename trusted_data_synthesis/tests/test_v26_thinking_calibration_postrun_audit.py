from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_calibration_postrun_audit import (  # noqa: E501
    EXPECTED_EXECUTION_REPORT_ID,
    CompletionRootCauseAudit,
    PersistenceIntegrityAudit,
    ResponseModelTelemetryGapAudit,
    TelemetryRepairFixtureAudit,
    ThinkingPostrunSourceReplayAudit,
    ThinkingTelemetryRepairContract,
    build_thinking_calibration_postrun_audit,
    redact_provider_response_envelope,
    require_admitted_repaired_envelope,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = (
    PACKAGE_ROOT / "artifacts/vtdo_experiment/"
    "finance_v26_92_thinking_budget_calibration_execution_v1_20260821"
)
RUN_ID = "finance_v26_93_thinking_calibration_postrun_audit_test_v1"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[object, Path]:
    output = tmp_path_factory.mktemp("v26_93_postrun")
    report = build_thinking_calibration_postrun_audit(
        run_id=RUN_ID,
        execution_dir=EXECUTION_DIR,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return report, output


def _load(path: Path, model: type[object]) -> object:
    return model.model_validate_json(path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]


def test_postrun_replays_every_bound_file_without_generation(built: tuple[object, Path]) -> None:
    report, output = built
    source = _load(output / "source_replay_audit.json", ThinkingPostrunSourceReplayAudit)
    persistence = _load(output / "persistence_integrity_audit.json", PersistenceIntegrityAudit)
    assert report.execution_report_id == EXPECTED_EXECUTION_REPORT_ID  # type: ignore[attr-defined]
    assert source.replayed_file_count == 393  # type: ignore[attr-defined]
    assert source.replay_pass_count == 393  # type: ignore[attr-defined]
    assert source.model_client_constructed is False  # type: ignore[attr-defined]
    assert persistence.raw_execution_count == 32  # type: ignore[attr-defined]
    assert persistence.raw_provider_artifact_count == 318  # type: ignore[attr-defined]
    assert persistence.checkpoint_final_result_match_count == 32  # type: ignore[attr-defined]
    assert persistence.private_reasoning_payload_count == 0  # type: ignore[attr-defined]


def test_response_model_gap_is_missing_telemetry_not_observed_mismatch(
    built: tuple[object, Path],
) -> None:
    _, output = built
    audit = _load(output / "provider_telemetry_gap_audit.json", ResponseModelTelemetryGapAudit)
    assert audit.exact_requested_model_call_count == 318  # type: ignore[attr-defined]
    assert audit.exact_selected_model_call_count == 318  # type: ignore[attr-defined]
    assert audit.known_exact_response_model_call_count == 239  # type: ignore[attr-defined]
    assert audit.known_response_model_mismatch_count == 0  # type: ignore[attr-defined]
    assert audit.missing_response_model_call_count == 79  # type: ignore[attr-defined]
    assert audit.missing_response_model_affected_job_count == 32  # type: ignore[attr-defined]
    assert audit.missing_response_model_reason_counts == {  # type: ignore[attr-defined]
        "JSONDecodeError": 5,
        "ReasoningBudgetExhaustedError": 74,
    }
    assert audit.observed_provider_model_mismatch is False  # type: ignore[attr-defined]


def test_completion_failure_is_independent_and_cannot_be_rescued(
    built: tuple[object, Path],
) -> None:
    _, output = built
    audit = _load(output / "completion_root_cause_audit.json", CompletionRootCauseAudit)
    assert audit.typed_no_call_job_count == 0  # type: ignore[attr-defined]
    assert audit.typed_no_call_cp95_upper_32 == pytest.approx(  # type: ignore[attr-defined]
        0.08936819898626475
    )
    assert audit.completion_unusable_job_count == 30  # type: ignore[attr-defined]
    assert audit.completion_unusable_cp95_upper_32 == pytest.approx(  # type: ignore[attr-defined]
        0.9887805056361199
    )
    assert audit.length_finished_provider_call_count == 78  # type: ignore[attr-defined]
    assert audit.length_affected_logical_request_count == 53  # type: ignore[attr-defined]
    assert audit.length_affected_repaired_usable_request_count == 23  # type: ignore[attr-defined]
    assert audit.length_affected_terminal_failure_request_count == 30  # type: ignore[attr-defined]
    assert audit.telemetry_repair_cannot_rescue_completion_gate is True  # type: ignore[attr-defined]


def test_repair_contract_fails_closed_without_private_reasoning(
    built: tuple[object, Path],
) -> None:
    _, output = built
    fixture = _load(output / "repair_fixture_audit.json", TelemetryRepairFixtureAudit)
    contract = _load(output / "telemetry_repair_contract.json", ThinkingTelemetryRepairContract)
    assert fixture.rejected_mutation_count == 5  # type: ignore[attr-defined]
    assert fixture.private_reasoning_content_absent is True  # type: ignore[attr-defined]
    assert contract.historical_v26_92_result_reclassified is False  # type: ignore[attr-defined]
    assert contract.historical_v26_92_job_rerun_allowed is False  # type: ignore[attr-defined]
    assert contract.completion_upper_bound_tokens == 4096  # type: ignore[attr-defined]

    response = {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "{}",
                    "reasoning_content": "synthetic",
                    "tool_calls": [{"id": "forbidden"}],
                },
            }
        ],
        "usage": {
            "completion_tokens": 20,
            "completion_tokens_details": {"reasoning_tokens": 10},
        },
    }
    envelope = redact_provider_response_envelope(response)
    with pytest.raises(ValueError, match="Provider-native tool call"):
        require_admitted_repaired_envelope(envelope)
    assert "reasoning_content" not in envelope.model_dump(mode="json")


def test_postrun_dual_build_is_byte_identical(built: tuple[object, Path], tmp_path: Path) -> None:
    _, formal = built
    independent = tmp_path / "independent"
    build_thinking_calibration_postrun_audit(
        run_id=RUN_ID,
        execution_dir=EXECUTION_DIR,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
    )
    formal_files = sorted(item.name for item in formal.iterdir() if item.is_file())
    independent_files = sorted(item.name for item in independent.iterdir() if item.is_file())
    assert formal_files == independent_files
    assert len(formal_files) == 7
    for name in formal_files:
        assert (formal / name).read_bytes() == (independent / name).read_bytes()
    report = json.loads((formal / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["next_permitted_stage"] == (
        "fresh_thinking_completion_and_response_telemetry_repair_preflight_only"
    )
