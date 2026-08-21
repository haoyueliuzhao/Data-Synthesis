from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_execution_binding_preflight import (  # noqa: E501
    EXPECTED_DERIVED_8K_MODEL_CONFIG_ID,
    EXPECTED_DERIVED_8K_THINKING_BINDING_ID,
    EXPECTED_FROZEN_MODEL_CONFIG_ID,
    EXPECTED_FROZEN_THINKING_BINDING_ID,
    NEXT_PERMITTED_STAGE,
    RUN_ID,
    ExecutionBindingDestructiveAudit,
    ExecutionBindingPreflightReport,
    ExecutionBindingRootCauseAudit,
    ExecutionBindingSourceReplayAudit,
    ExecutionProfileBindingAudit,
    JobExecutionBindingAudit,
    ProspectiveExecutionRebindingContract,
    build_thinking_8k_execution_binding_preflight,
)
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, ExecutionBindingPreflightReport]:
    output = tmp_path_factory.mktemp("v26_98_execution_binding")
    report = build_thinking_8k_execution_binding_preflight(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_98_replays_v26_97_before_profile_audit(
    built: tuple[Path, ExecutionBindingPreflightReport],
) -> None:
    output, report = built
    audit = ExecutionBindingSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text(encoding="utf-8")
    )

    assert audit.replayed_file_count == audit.replay_pass_count == 746
    assert audit.transitive_source_file_count == 733
    assert audit.predecessor_output_file_count == 12
    assert audit.implementation_file_count == 1
    assert audit.replay_before_profile_audit
    assert not audit.model_client_constructed
    assert not audit.credential_lookup_attempted
    assert audit.model_api_calls == audit.gpu_jobs == 0
    assert report.source_replay_audit_id == audit.audit_id


def test_v26_98_reconstructs_distinct_4k_and_8k_profile_identities(
    built: tuple[Path, ExecutionBindingPreflightReport],
) -> None:
    output, _ = built
    audit = ExecutionProfileBindingAudit.model_validate_json(
        (output / "execution_profile_binding_audit.json").read_text(encoding="utf-8")
    )
    profile_payload = json.loads(
        (PACKAGE_ROOT / "config/deepseek_v4_flash_agent_thinking_v1.json").read_text(
            encoding="utf-8"
        )
    )
    frozen = AgentModelConfig.model_validate(profile_payload["model"])
    values = frozen.model_dump(mode="python")
    values["max_output_tokens"] = 8192
    derived = AgentModelConfig.model_validate(values)

    assert frozen.max_output_tokens == 4096
    assert frozen.public_manifest_hash == EXPECTED_FROZEN_MODEL_CONFIG_ID
    assert bind_prospective_thinking(frozen).binding_id == EXPECTED_FROZEN_THINKING_BINDING_ID
    assert derived.max_output_tokens == 8192
    assert derived.public_manifest_hash == EXPECTED_DERIVED_8K_MODEL_CONFIG_ID
    assert bind_prospective_thinking(derived).binding_id == EXPECTED_DERIVED_8K_THINKING_BINDING_ID
    assert audit.task_package_count == 24
    assert audit.task_package_bound_to_4096_config_count == 24
    assert audit.task_package_bound_to_8192_config_count == 0
    assert audit.exact_8k_task_package_binding_count == 0
    assert not audit.derived_8k_profile_materialized
    assert not audit.exact_execution_profile_binding_passed
    assert all(not item.exact_execution_binding_closed for item in audit.task_package_rows)


def test_v26_98_blocks_every_8k_job_before_provider_call(
    built: tuple[Path, ExecutionBindingPreflightReport],
) -> None:
    output, report = built
    audit = JobExecutionBindingAudit.model_validate_json(
        (output / "job_execution_binding_audit.json").read_text(encoding="utf-8")
    )

    assert audit.manifest_job_count == 32
    assert audit.job_requiring_8192_completion_count == 32
    assert audit.job_with_exact_8192_task_package_profile_count == 0
    assert audit.job_with_profile_binding_mismatch_count == 32
    assert audit.job_authorized_for_provider_call_count == 0
    assert audit.fallback_16k_job_count == 0
    assert audit.historical_job_rerun_count == 0
    assert all(item.completion_bound_difference_tokens == 4096 for item in audit.rows)
    assert all(not item.provider_call_authorized for item in audit.rows)
    assert report.blocked_job_count == 32


def test_v26_98_freezes_root_cause_and_fresh_rebinding_only(
    built: tuple[Path, ExecutionBindingPreflightReport],
) -> None:
    output, report = built
    root_cause = ExecutionBindingRootCauseAudit.model_validate_json(
        (output / "execution_binding_root_cause_audit.json").read_text(encoding="utf-8")
    )
    transition = ProspectiveExecutionRebindingContract.model_validate_json(
        (output / "prospective_rebinding_contract.json").read_text(encoding="utf-8")
    )

    assert root_cause.root_cause == ("completion_candidate_not_bound_to_taskpackage_model_config")
    assert not root_cause.candidate_field_can_override_agent_model_config_identity
    assert not root_cause.request_max_tokens_override_without_new_config_allowed
    assert not root_cause.exact_v26_97_manifest_runner_constructible
    assert root_cause.v26_97_static_candidate_and_path_claims_retained
    assert transition.fresh_8k_model_profile_required
    assert transition.fresh_thinking_binding_required
    assert transition.fresh_task_package_identity_count_required == 24
    assert transition.fresh_path_audit_identity_count_required == 48
    assert transition.fresh_job_identity_count_required == 32
    assert transition.preserved_fresh_seed_count_required == 32
    assert not transition.source_task_selection_change_allowed
    assert not transition.path_selection_change_allowed
    assert not transition.job_assignment_change_allowed
    assert not transition.seed_value_change_allowed
    assert not transition.completion_candidate_change_allowed
    assert not transition.rollout_ceiling_change_allowed
    assert not transition.rescue_renderer_change_allowed
    assert not transition.provider_calls_allowed
    assert transition.next_permitted_stage == NEXT_PERMITTED_STAGE
    assert report.status == "blocked_preflight"
    assert report.failure_type == "execution_profile_binding_failure"
    assert report.next_permitted_stage == NEXT_PERMITTED_STAGE
    assert not report.runner_implementation_materialized
    assert not report.execution_authorized
    assert report.model_api_calls == report.gpu_jobs == 0


def test_v26_98_destructive_controls_reject_identity_shortcuts(
    built: tuple[Path, ExecutionBindingPreflightReport],
) -> None:
    output, _ = built
    audit = ExecutionBindingDestructiveAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )

    assert audit.rejected_mutation_count == 12
    assert all(item.rejected for item in audit.mutation_results)
    assert not audit.model_client_constructed
    assert not audit.credential_lookup_attempted
    assert audit.provider_calls == audit.gpu_jobs == 0


def test_v26_98_dual_build_is_byte_identical(
    built: tuple[Path, ExecutionBindingPreflightReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_8k_execution_binding_preflight(
        run_id=RUN_ID,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 7
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"reasoning_content"' not in serialized
    assert b'"raw_http_body"' not in serialized
