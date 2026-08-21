from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_bound_redesign_preflight import (  # noqa: E501
    RUN_ID,
    CompletionBoundContract,
    CompletionBoundDestructiveAudit,
    CompletionBoundManifest,
    CompletionBoundPathAudit,
    CompletionBoundPreflightReport,
    CompletionBoundSourceReplayAudit,
    DynamicRescueCoverageAudit,
    SourceExposureAudit,
    build_thinking_completion_bound_redesign_preflight,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion_bound import (
    RESCUE_PROMPT_UPPER_BOUND_BYTES,
    certify_dynamic_primary_pre_call,
    certify_dynamic_rescue_pre_call,
    make_prospective_completion_bound_protocol,
    render_bounded_rescue_completion_prompt,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))
ROOT_CAUSE_PROVIDER_ARTIFACT = (
    "artifacts/vtdo_experiment/"
    "finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/"
    "raw_provider_calls/7c26dccffd0d5fdd6f63/call_0006.json"
)
TRANSITION_ID = (
    "finance_v26_thinking_repair_failure_transition:"
    "9036133329a0b6cff0e900773b19cd4fd3f7e33b72b09bde388fd49227bea6f4"
)


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, CompletionBoundPreflightReport]:
    output = tmp_path_factory.mktemp("v26_97_completion_bound")
    report = build_thinking_completion_bound_redesign_preflight(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        output = {str(key) for key in value}
        for item in value.values():
            output.update(_all_keys(item))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for item in value:
            output.update(_all_keys(item))
        return output
    return set()


def test_v26_97_protocol_freezes_minimum_first_candidate_and_separate_fallback() -> None:
    protocol = make_prospective_completion_bound_protocol(
        predecessor_transition_contract_id=TRANSITION_ID
    )

    assert [item.completion_upper_bound_tokens for item in protocol.candidates] == [8192, 16384]
    assert [item.rollout_upper_bound_tokens for item in protocol.candidates] == [160_000, 240_000]
    assert protocol.initial_candidate_id == protocol.candidates[0].candidate_id
    assert protocol.fallback_candidate_id == protocol.candidates[1].candidate_id
    assert not protocol.same_4096_bound_prompt_only_repair_allowed
    assert not protocol.fallback_materialized_as_execution_job
    assert not protocol.fallback_automatic_execution_allowed
    assert not protocol.semantic_validity_can_select_bound
    assert protocol.rescue_prompt_upper_bound_bytes == 6144


def test_v26_97_root_cause_state_is_bounded_before_provider_call() -> None:
    artifact = json.loads((PACKAGE_ROOT / ROOT_CAUSE_PROVIDER_ARTIFACT).read_text(encoding="utf-8"))
    protocol = make_prospective_completion_bound_protocol(
        predecessor_transition_contract_id=TRANSITION_ID
    )
    primary = artifact["prompt"]
    rescue = render_bounded_rescue_completion_prompt(
        "decision",
        primary,
        "reasoning_only_length_truncation",
    )
    rescue_payload = json.loads(rescue.partition("\n")[2])
    _, certificate = certify_dynamic_rescue_pre_call(
        protocol=protocol,
        candidate_id=protocol.initial_candidate_id,
        request_kind="decision",
        primary_prompt=primary,
        failure_type="reasoning_only_length_truncation",
        cumulative_usage_tokens_before_request=0,
        required_future_reserve_tokens=0,
    )

    assert len(primary.encode("utf-8")) == 7914
    assert len(rescue.encode("utf-8")) == 3888
    assert len(rescue.encode("utf-8")) <= RESCUE_PROMPT_UPPER_BOUND_BYTES
    assert certificate.provider_call_count_before_certificate == 0
    assert certificate.actual_request_kind_certificate_passed
    assert certificate.actual_primary_prompt_certificate_passed
    assert certificate.actual_rescue_prompt_certificate_passed
    assert certificate.actual_resource_certificate_passed
    keys = _all_keys(rescue_payload)
    assert "acquisitions" not in keys
    assert "failed_actions" not in keys
    assert "failed_arguments" not in keys
    assert "previous_final_content" not in keys
    assert "reasoning_content" not in keys
    assert "raw_http_body" not in keys


def test_v26_97_dynamic_certificates_fail_before_oversized_or_mistyped_calls() -> None:
    artifact = json.loads((PACKAGE_ROOT / ROOT_CAUSE_PROVIDER_ARTIFACT).read_text(encoding="utf-8"))
    protocol = make_prospective_completion_bound_protocol(
        predecessor_transition_contract_id=TRANSITION_ID
    )
    primary = artifact["prompt"]
    with pytest.raises(ValueError, match="request kind"):
        certify_dynamic_primary_pre_call(
            protocol=protocol,
            candidate_id=protocol.initial_candidate_id,
            request_kind="final_answer",
            primary_prompt=primary,
            cumulative_usage_tokens_before_request=0,
            required_future_reserve_tokens=0,
        )
    with pytest.raises(ValueError, match="rollout budget"):
        certify_dynamic_primary_pre_call(
            protocol=protocol,
            candidate_id=protocol.initial_candidate_id,
            request_kind="decision",
            primary_prompt=primary,
            cumulative_usage_tokens_before_request=160_000,
            required_future_reserve_tokens=0,
        )


def test_v26_97_replays_predecessor_and_discloses_repeated_source_exposure(
    built: tuple[Path, CompletionBoundPreflightReport],
) -> None:
    output, report = built
    source = CompletionBoundSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    exposure = SourceExposureAudit.model_validate_json(
        (output / "source_exposure_audit.json").read_text(encoding="utf-8")
    )

    assert source.replayed_file_count == source.replay_pass_count == 733
    assert source.transitive_source_file_count == 723
    assert source.predecessor_output_file_count == 8
    assert source.implementation_file_count == 2
    assert exposure.source_task_overlap_with_v26_95_count == 24
    assert exposure.model_exposed_source_task_count == 22
    assert exposure.model_unexposed_source_task_count == 2
    assert not exposure.source_tasks_claimed_fresh
    assert exposure.repeated_source_use == "engineering_completion_calibration_only"
    assert not exposure.v26_95_semantic_outcomes_used_to_select_tasks_or_jobs
    assert exposure.v26_95_jobs_rerun_or_continued == 0
    assert report.model_client_constructed is False
    assert report.model_api_calls == report.gpu_jobs == 0


def test_v26_97_covers_compiler_and_historical_dynamic_states(
    built: tuple[Path, CompletionBoundPreflightReport],
) -> None:
    output, _ = built
    audit = DynamicRescueCoverageAudit.model_validate_json(
        (output / "dynamic_rescue_coverage_audit.json").read_text(encoding="utf-8")
    )

    assert audit.compiler_registered_state_count == 324
    assert audit.v26_95_exposed_primary_state_count == 156
    assert audit.total_state_count == 480
    assert audit.total_rescue_projection_count == 2400
    assert audit.maximum_observed_rescue_prompt_utf8_bytes == 5702
    assert audit.minimum_rescue_headroom_bytes == 442
    assert audit.dynamic_request_kind_certificate_pass_count == 2400
    assert audit.dynamic_primary_certificate_pass_count == 2400
    assert audit.dynamic_rescue_certificate_pass_count == 2400
    assert audit.dynamic_resource_certificate_pass_count == 2400
    assert audit.certificate_fixture_cumulative_usage_tokens == 0
    assert not audit.online_dynamic_resource_adequacy_established
    assert not audit.execution_runner_resource_logic_materialized
    assert audit.provider_calls == audit.empirical_rows == 0
    assert sum(item.request_kind == "final_answer" for item in audit.rows) == 48


def test_v26_97_both_candidates_fit_static_paths_without_same_run_escalation(
    built: tuple[Path, CompletionBoundPreflightReport],
) -> None:
    output, _ = built
    paths = [
        CompletionBoundPathAudit.model_validate(item)
        for item in json.loads(
            (output / "completion_bound_path_audits.json").read_text(encoding="utf-8")
        )
    ]
    initial = [item.candidate_budgets[0] for item in paths]
    fallback = [item.candidate_budgets[1] for item in paths]

    assert len(paths) == 48
    assert sum(item.primary_request_count for item in paths) == 324
    assert min(item.full_path_token_upper_bound for item in initial) == 76_817
    assert max(item.full_path_token_upper_bound for item in initial) == 151_653
    assert min(item.rollout_headroom_tokens for item in initial) == 8_347
    assert min(item.full_path_token_upper_bound for item in fallback) == 125_969
    assert max(item.full_path_token_upper_bound for item in fallback) == 233_573
    assert min(item.rollout_headroom_tokens for item in fallback) == 6_427
    assert max(item.maximum_primary_prompt_utf8_bytes for item in paths) == 8_369
    assert max(item.maximum_rescue_prompt_utf8_bytes for item in paths) == 5_702


def test_v26_97_freezes_only_fresh_8k_jobs_and_no_execution(
    built: tuple[Path, CompletionBoundPreflightReport],
) -> None:
    output, report = built
    contract = CompletionBoundContract.model_validate_json(
        (output / "completion_bound_contract.json").read_text(encoding="utf-8")
    )
    manifest = CompletionBoundManifest.model_validate_json(
        (output / "completion_bound_job_manifest.json").read_text(encoding="utf-8")
    )
    destructive = CompletionBoundDestructiveAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )

    assert len(contract.task_package_ids) == 24
    assert len(contract.path_audit_ids) == 48
    assert contract.fallback_jobs_materialized == 0
    assert not contract.automatic_bound_escalation_allowed
    assert not contract.execution_runner_materialized
    assert not contract.execution_authorized
    assert len(manifest.jobs) == 32
    assert len({item.job_id for item in manifest.jobs}) == 32
    assert len({item.job_seed for item in manifest.jobs}) == 32
    assert {item.completion_upper_bound_tokens for item in manifest.jobs} == {8192}
    assert {item.rollout_upper_bound_tokens for item in manifest.jobs} == {160_000}
    assert manifest.fallback_job_count == 0
    assert manifest.historical_v26_95_job_overlap_count == 0
    assert destructive.rejected_mutation_count == 18
    assert all(item.rejected for item in destructive.mutation_results)
    assert report.status == "passed_preflight"
    assert report.next_permitted_stage == (
        "thinking_8k_completion_calibration_runner_and_preflight_only"
    )
    assert not report.execution_authorized
    assert not report.role_protocol_frozen
    assert report.production_contribution == 0


def test_v26_97_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, CompletionBoundPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_completion_bound_redesign_preflight(
        run_id=RUN_ID,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 12
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"reasoning_content"' not in serialized
    assert b'"raw_http_body"' not in serialized
    assert b'"previous_final_content"' not in serialized
