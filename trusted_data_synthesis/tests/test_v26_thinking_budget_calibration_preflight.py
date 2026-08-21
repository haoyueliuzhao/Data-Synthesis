from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    FRESHNESS_CHANNELS,
    PATH_STRATEGIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_budget_calibration_preflight import (  # noqa: E501
    CELL_JOB_COUNTS,
    MECHANISM_TASK_COUNTS,
    BudgetShapeCoverageAudit,
    CalibrationFreshnessAudit,
    CalibrationSourceCapacityAudit,
    CalibrationStressPathAudit,
    CalibrationTaskPackage,
    CompletionUsabilityContract,
    CompletionUsabilityFixtureAudit,
    DestructivePreflightAudit,
    PredecessorReplayAudit,
    ThinkingBudgetCalibrationManifest,
    ThinkingBudgetCalibrationPreflightReport,
    ThinkingContinuityFixtureAudit,
    build_thinking_budget_calibration_preflight,
)
from trusted_synthesis.runtime.agent.thinking_history import ThinkingContinuityContract

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "finance_v26_91_thinking_budget_calibration_preflight_v1_20260821"
SELECTION_SALT = "finance_v26_91_thinking_budget_calibration_preflight.v1"


def _rows(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(model.model_validate(item) for item in payload)


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()), set())
    if isinstance(value, (list, tuple)):
        return set().union(*(_keys(item) for item in value), set())
    return set()


@pytest.fixture(scope="session")
def formal_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    output = tmp_path_factory.mktemp("v26_91_formal")
    report = build_thinking_budget_calibration_preflight(
        run_id=RUN_ID,
        selection_salt=SELECTION_SALT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_dual_build_is_byte_identical(
    formal_build: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    formal_dir, formal_report = formal_build
    independent_dir = tmp_path / "independent"
    independent_report = build_thinking_budget_calibration_preflight(
        run_id=RUN_ID,
        selection_salt=SELECTION_SALT,
        output_dir=independent_dir,
        package_root=PACKAGE_ROOT,
    )
    formal_files = tuple(sorted(path.name for path in formal_dir.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent_dir.iterdir()))
    assert len(formal_files) == 31
    assert formal_files == independent_files
    assert all(
        (formal_dir / name).read_bytes() == (independent_dir / name).read_bytes()
        for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id


def test_report_authorizes_calibration_execution_only(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    report = ThinkingBudgetCalibrationPreflightReport.model_validate_json(
        (output / "report.json").read_text(encoding="utf-8")
    )
    assert report.calibration_task_count == 31
    assert report.calibration_job_count == 32
    assert report.base_compiler_path_count == 93
    assert report.stress_path_count == 32
    assert report.predecessor_replayed_file_count == 104
    assert report.maximum_calibration_path_upper_bound == 115676
    assert report.minimum_calibration_headroom_tokens == 4324
    assert report.maximum_calibration_prompt_utf8_bytes == 8432
    assert report.model_api_calls == report.gpu_jobs == report.empirical_result_count == 0
    assert report.calibration_execution_authorized
    assert not report.calibration_execution_completed
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.next_permitted_stage == "thinking_budget_calibration_execution_only"
    assert not (output / "checkpoint.jsonl").exists()
    assert not (output / "rollouts.json").exists()
    assert not (output / "raw_executions").exists()


def test_predecessor_replay_precedes_contract_and_manifest(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    audit = PredecessorReplayAudit.model_validate_json(
        (output / "predecessor_replay_audit.json").read_text(encoding="utf-8")
    )
    assert audit.replayed_file_count == 104
    assert audit.v26_90_output_file_count == 25
    assert audit.v26_90_source_file_count == 57
    assert audit.v26_90_implementation_file_count == 22
    assert audit.replay_before_contract_and_manifest
    assert audit.model_api_calls == audit.gpu_jobs == 0
    assert all(item.passed for item in audit.entries)


def test_source_capacity_and_nine_channel_freshness(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    capacity = CalibrationSourceCapacityAudit.model_validate_json(
        (output / "calibration_source_capacity_audit.json").read_text(encoding="utf-8")
    )
    assert capacity.eligible_counts == {
        "context_conditioned_action": 5,
        "semantic_reconciliation": 24,
        "failure_recovery": 9,
        "state_dependent_stopping": 8,
    }
    assert capacity.selected_counts == MECHANISM_TASK_COUNTS
    assert capacity.selected_task_count == 31
    assert not capacity.historical_model_outcomes_loaded
    assert not capacity.compiler_fixture_outcomes_loaded

    freshness = CalibrationFreshnessAudit.model_validate_json(
        (output / "calibration_freshness_audit.json").read_text(encoding="utf-8")
    )
    assert tuple(item.channel for item in freshness.channels) == FRESHNESS_CHANNELS
    assert freshness.historical_task_record_count == 156
    assert freshness.historical_job_identity_count == 1200
    assert all(item.prior_overlap_count == 0 for item in freshness.channels)
    assert all(item.internal_duplicate_count == 0 for item in freshness.channels)
    selected_counts = {item.channel: item.selected_count for item in freshness.channels}
    assert selected_counts["source_task_artifact_id"] == 31
    assert selected_counts["evidence_id"] == 209
    assert selected_counts["task_package_id"] == 62
    assert selected_counts["job_id"] == 32


def test_manifest_freezes_all_mechanism_path_cells(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    manifest = ThinkingBudgetCalibrationManifest.model_validate_json(
        (output / "calibration_job_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.job_count == manifest.distinct_job_count == 32
    assert manifest.distinct_task_count == 31
    assert manifest.mechanism_path_job_counts == CELL_JOB_COUNTS
    assert len({item.job_id for item in manifest.jobs}) == 32
    assert len({item.calibration_task_package_id for item in manifest.jobs}) == 31
    assert all(item.independent_job_identity for item in manifest.jobs)
    assert all(item.thinking_binding_id for item in manifest.jobs)
    assert all(not item.execution_permitted_during_preflight for item in manifest.jobs)
    observed = Counter(f"{item.mechanism_id}:{item.path_strategy_id}" for item in manifest.jobs)
    assert dict(observed) == CELL_JOB_COUNTS


def test_every_stress_prefix_dominates_role_envelope(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    paths = _rows(output / "calibration_stress_path_audits.json", CalibrationStressPathAudit)
    coverage = BudgetShapeCoverageAudit.model_validate_json(
        (output / "budget_shape_coverage_audit.json").read_text(encoding="utf-8")
    )
    assert len(paths) == 32
    assert len(coverage.cells) == 12
    assert {item.path_strategy_id for item in paths} == set(PATH_STRATEGIES)
    assert coverage.every_job_prefix_dominates_role_envelope
    assert coverage.maximum_calibration_path_upper_bound == 115676
    assert coverage.minimum_calibration_headroom_tokens == 4324
    for path in paths:
        assert path.full_path_budget_qualified
        assert path.minimum_prefix_coverage_margin >= 64
        for row in path.rows:
            assert row.calibration_prefix_upper_bound >= row.role_prefix_upper_bound + 64
            assert row.padded_prompt_utf8_bytes == (
                row.unpadded_prompt_utf8_bytes + row.trailing_ascii_space_padding_bytes
            )
            if row.trailing_ascii_space_padding_bytes:
                assert row.padded_prompt_sha256 != row.unpadded_prompt_sha256


def test_thinking_continuity_is_redacted_and_fail_closed(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    contract = ThinkingContinuityContract.model_validate_json(
        (output / "thinking_continuity_contract.json").read_text(encoding="utf-8")
    )
    fixture = ThinkingContinuityFixtureAudit.model_validate_json(
        (output / "thinking_continuity_fixture_audit.json").read_text(encoding="utf-8")
    )
    assert contract.interaction_protocol == "host_instrumented_json_decision"
    assert not contract.provider_native_tool_calls_allowed
    assert not contract.current_turn_reasoning_passback_required
    assert contract.final_content_hash_excludes_reasoning_content
    assert contract.retained_reasoning_fields == (
        "reasoning_content_present",
        "reasoning_content_length",
        "reasoning_tokens",
    )
    payload = json.loads(
        (output / "thinking_continuity_fixture_audit.json").read_text(encoding="utf-8")
    )
    assert "reasoning_content" not in _keys(payload)
    assert fixture.history_audit.turn_count == 3
    assert fixture.rejected_mutation_count == 6
    assert fixture.provider_calls == 0
    assert all(item.rejected for item in fixture.mutation_results)
    assert all(len(item.final_content_sha256) == 64 for item in fixture.history_audit.turns)


def test_completion_usability_is_separate_and_prospective(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    contract = CompletionUsabilityContract.model_validate_json(
        (output / "completion_usability_contract.json").read_text(encoding="utf-8")
    )
    fixture = CompletionUsabilityFixtureAudit.model_validate_json(
        (output / "completion_usability_fixture_audit.json").read_text(encoding="utf-8")
    )
    assert math.isclose(contract.zero_failure_cp95_upper_bound_at_32, 0.08936819898626475)
    assert math.isclose(contract.one_failure_cp95_upper_bound_at_32, 0.13984946027422601)
    assert contract.zero_failure_cp95_upper_bound_at_32 <= 0.10
    assert contract.one_failure_cp95_upper_bound_at_32 > 0.10
    assert contract.zero_failures_required_at_32_jobs
    assert contract.typed_no_call_and_completion_unusable_separate
    assert contract.behavior_diagnostics_are_non_authorizing
    assert contract.task_depth_adequacy_remains_unresolved
    assert fixture.resource_no_call_count == 1
    assert fixture.transport_failure_count == 1
    assert fixture.completion_unusable_count == 6
    assert fixture.usable_completion_count == 2
    assert fixture.outcome_counts["thinking_telemetry_missing_or_empty"] == 1
    assert fixture.no_call_and_completion_denominators_separate


def test_calibration_packages_cannot_enter_role_or_state_denominators(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    packages = _rows(output / "calibration_task_packages.json", CalibrationTaskPackage)
    assert len(packages) == 31
    assert all(item.calibration_only_override for item in packages)
    assert all(not item.capability_denominator_eligible for item in packages)
    assert all(not item.reachability_denominator_eligible for item in packages)
    assert all(not item.state_mapping_eligible for item in packages)
    assert all(not item.release_eligible for item in packages)
    assert all(item.base_path_strategy_ids == PATH_STRATEGIES for item in packages)


def test_destructive_preflight_rejects_all_mutations(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    audit = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )
    assert audit.rejected_mutation_count == 13
    assert all(item.rejected for item in audit.mutation_results)
    assert audit.model_api_calls == audit.gpu_jobs == 0
