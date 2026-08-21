from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_telemetry_repair_preflight import (  # noqa: E501
    DestructivePreflightAudit,
    RolePopulationRetirementAudit,
    TelemetryFixtureAudit,
    ThinkingCompletionRepairContract,
    ThinkingCompletionTelemetryRepairPreflightReport,
    ThinkingRepairFreshnessAudit,
    ThinkingRepairManifest,
    ThinkingRepairPathAudit,
    ThinkingRepairSourceReplayAudit,
    ThinkingRepairTaskPackage,
    build_thinking_completion_telemetry_repair_preflight,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821"


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
    output = tmp_path_factory.mktemp("v26_94_formal")
    report = build_thinking_completion_telemetry_repair_preflight(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_94_dual_build_is_byte_identical(
    formal_build: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    formal_dir, formal_report = formal_build
    independent_dir = tmp_path / "independent"
    independent_report = build_thinking_completion_telemetry_repair_preflight(
        run_id=RUN_ID,
        output_dir=independent_dir,
        package_root=PACKAGE_ROOT,
    )
    formal_files = tuple(sorted(path.name for path in formal_dir.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent_dir.iterdir()))

    assert len(formal_files) == 11
    assert formal_files == independent_files
    assert all(
        (formal_dir / name).read_bytes() == (independent_dir / name).read_bytes()
        for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id


def test_v26_94_report_permits_runner_preflight_only(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    report = ThinkingCompletionTelemetryRepairPreflightReport.model_validate_json(
        (output / "report.json").read_text(encoding="utf-8")
    )

    assert report.source_replayed_file_count == 485
    assert report.repair_task_package_count == 24
    assert report.static_path_count == 48
    assert report.compiler_projection_count == 324
    assert report.repair_job_count == 32
    assert report.maximum_path_upper_bound == 111966
    assert report.minimum_path_headroom_tokens == 8034
    assert report.maximum_prompt_utf8_bytes == 8369
    assert report.model_api_calls == report.gpu_jobs == report.empirical_result_count == 0
    assert not report.execution_runner_materialized
    assert not report.repair_execution_authorized
    assert not report.capability_execution_authorized
    assert not report.reachability_execution_authorized
    assert not report.state_mapping_authorized
    assert report.production_contribution == 0
    assert (
        report.next_permitted_stage
        == "thinking_completion_telemetry_repair_execution_runner_and_preflight_only"
    )
    assert not (output / "checkpoint.jsonl").exists()
    assert not (output / "raw_executions").exists()


def test_v26_94_replays_predecessors_and_retires_role_population(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    replay = ThinkingRepairSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    retirement = RolePopulationRetirementAudit.model_validate_json(
        (output / "role_population_retirement_audit.json").read_text(encoding="utf-8")
    )

    assert replay.replayed_file_count == 485
    assert replay.all_files_passed
    assert all(item.passed for item in replay.entries)
    assert replay.model_api_calls == replay.gpu_jobs == 0
    assert retirement.retired_source_task_count == 24
    assert retirement.retired_from_capability_role_count == 12
    assert retirement.retired_from_reachability_role_count == 12
    assert retirement.v26_92_source_task_overlap_count == 0
    assert retirement.v26_92_operational_package_overlap_count == 0
    assert not retirement.future_role_execution_allowed
    assert retirement.role_mechanism_counts == {
        mechanism: {"capability": 3, "reachability": 3}
        for mechanism in (
            "context_conditioned_action",
            "failure_recovery",
            "semantic_reconciliation",
            "state_dependent_stopping",
        )
    }


def test_v26_94_all_paths_preserve_authority_and_fit_with_short_rescue(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    paths = _rows(output / "thinking_repair_path_audits.json", ThinkingRepairPathAudit)
    requests = tuple(row for path in paths for row in path.request_audits)

    assert len(paths) == 48
    assert len(requests) == 324
    assert sum(item.compiler_projection_count for item in paths) == 324
    assert min(item.minimum_rescue_size_reduction_basis_points for item in paths) == 1154
    assert max(item.full_path_upper_bound for item in paths) == 111966
    assert min(item.minimum_headroom_tokens for item in paths) == 8034
    assert max(item.maximum_prompt_utf8_bytes for item in paths) == 8369
    assert all(item.model_plan_request_removed for item in paths)
    assert all(item.rescue_funded_by_removed_plan_and_repair_reserve for item in paths)
    assert all(item.all_rescue_prompts_strictly_shorter_than_primary for item in paths)
    assert all(
        item.compiler_projection_count == item.compiler_projection_pass_count for item in paths
    )
    assert all(item.prompt_ceiling_passed and item.rollout_ceiling_passed for item in paths)
    assert all(row.primary_not_larger_than_predecessor for row in requests)
    assert all(row.minimum_rescue_size_reduction_basis_points >= 1000 for row in requests)
    assert all(
        row.maximum_rescue_prompt_utf8_bytes < row.primary_prompt_utf8_bytes for row in requests
    )


def test_v26_94_contract_and_manifest_freeze_24_tasks_48_paths_32_jobs(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    packages = _rows(output / "thinking_repair_task_packages.json", ThinkingRepairTaskPackage)
    contract = ThinkingCompletionRepairContract.model_validate_json(
        (output / "thinking_repair_contract.json").read_text(encoding="utf-8")
    )
    manifest = ThinkingRepairManifest.model_validate_json(
        (output / "thinking_repair_job_manifest.json").read_text(encoding="utf-8")
    )
    freshness = ThinkingRepairFreshnessAudit.model_validate_json(
        (output / "thinking_repair_freshness_audit.json").read_text(encoding="utf-8")
    )

    assert len(packages) == 24
    assert len(contract.repair_task_package_ids) == 24
    assert len(contract.repair_path_audit_ids) == 48
    assert contract.exact_job_denominator == 32
    assert contract.zero_failure_cp95_upper_bound <= contract.failure_gate_threshold
    assert contract.one_failure_cp95_upper_bound > contract.failure_gate_threshold
    assert contract.typed_no_call_gate_requires_zero_failures
    assert contract.completion_unusable_gate_requires_zero_failures
    assert contract.provider_transport_failure_is_separate
    assert contract.semantic_validity_cannot_rescue_failure_gates
    assert len(manifest.jobs) == 32
    assert len({item.job_id for item in manifest.jobs}) == 32
    assert len({item.repair_task_package_id for item in manifest.jobs}) == 24
    assert manifest.mechanism_job_counts == {
        "context_conditioned_action": 8,
        "failure_recovery": 8,
        "semantic_reconciliation": 8,
        "state_dependent_stopping": 8,
    }
    assert manifest.path_job_counts == {
        "search_then_open": 12,
        "search_then_structured": 8,
        "structured_direct": 12,
    }
    assert len(manifest.cell_job_counts) == 12
    assert set(manifest.cell_job_counts.values()) <= {2, 3}
    observed = Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in manifest.jobs)
    assert dict(observed) == manifest.cell_job_counts
    assert not contract.execution_authorized
    assert not manifest.execution_authorized
    assert freshness.source_task_overlap_with_v26_92 == 0
    assert freshness.job_overlap_with_v26_92 == 0
    assert freshness.source_role_task_overlap_with_v26_90 == 24
    assert freshness.source_role_population_retired


def test_v26_94_telemetry_privacy_and_destructive_controls(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    fixture = TelemetryFixtureAudit.model_validate_json(
        (output / "telemetry_fixture_audit.json").read_text(encoding="utf-8")
    )
    destructive = DestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )
    fixture_payload = json.loads(
        (output / "telemetry_fixture_audit.json").read_text(encoding="utf-8")
    )

    assert fixture.response_model_retained_on_reasoning_exhaustion
    assert fixture.response_model_retained_on_invalid_json
    assert fixture.native_tool_presence_retained_before_parse
    assert fixture.malformed_usage_response_model == "deepseek-v4-flash"
    assert not fixture.malformed_usage_native_tool_observed
    assert fixture.malformed_usage_strict_envelope_rejected
    assert fixture.malformed_usage_private_reasoning_hit_count == 0
    assert fixture.typed_failure_artifact_count == 3
    assert fixture.serialized_private_reasoning_hit_count == 0
    assert "reasoning_content" not in _keys(fixture_payload)
    assert destructive.rejected_mutation_count == 21
    assert all(item.rejected for item in destructive.mutation_results)
    assert destructive.provider_calls == destructive.gpu_jobs == 0
