from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_binding_rematerialization import (  # noqa: E501
    Exact8KManifest,
    Exact8KPathAudit,
    Exact8KTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_16k_binding_and_usage_semantics import (  # noqa: E501
    EXPECTED_16K_CANDIDATE_ID,
    EXPECTED_16K_MODEL_CONFIG_ID,
    EXPECTED_16K_THINKING_BINDING_ID,
    NEXT_PERMITTED_STAGE,
    PROFILE_PATH,
    RUN_ID,
    Exact16KCompletionContract,
    Exact16KCrossArtifactBindingAudit,
    Exact16KDesignPreservationAudit,
    Exact16KDestructiveAudit,
    Exact16KFreshnessAudit,
    Exact16KManifest,
    Exact16KPathAudit,
    Exact16KProfileBinding,
    Exact16KRematerializationReport,
    Exact16KSourceReplayAudit,
    Exact16KTaskPackage,
    ProviderUsageSemanticsContract,
    build_thinking_16k_binding_and_usage_semantics,
)
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))
V26_99_DIR = (
    PACKAGE_ROOT
    / "artifacts/vtdo_experiment"
    / "finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822"
)


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Exact16KRematerializationReport]:
    output = tmp_path_factory.mktemp("v26_103_exact_16k")
    report = build_thinking_16k_binding_and_usage_semantics(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_103_replays_the_complete_authorizing_chain(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, report = built
    audit = Exact16KSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )

    assert audit.replayed_file_count == audit.replay_pass_count == 1221
    assert audit.predecessor_transitive_source_count == 1211
    assert audit.predecessor_output_count == 8
    assert audit.implementation_source_count == audit.persisted_profile_count == 1
    assert audit.replay_before_rematerialization
    assert not audit.credential_lookup_attempted
    assert not audit.model_client_constructed
    assert audit.provider_calls == audit.gpu_jobs == 0
    assert report.source_replay_audit_id == audit.audit_id


def test_v26_103_persists_the_exact_16k_profile_and_usage_contract(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, report = built
    profile = Exact16KProfileBinding.model_validate_json(
        (output / "exact_16k_profile_binding.json").read_text()
    )
    usage = ProviderUsageSemanticsContract.model_validate_json(
        (output / "provider_usage_semantics_contract.json").read_text()
    )
    payload = json.loads((LOCAL_PACKAGE_ROOT / PROFILE_PATH).read_text())["model"]
    config = AgentModelConfig.model_validate(payload)

    assert config.max_output_tokens == 16384
    assert config.public_manifest_hash == EXPECTED_16K_MODEL_CONFIG_ID
    assert bind_prospective_thinking(config).binding_id == EXPECTED_16K_THINKING_BINDING_ID
    assert profile.predecessor_max_output_tokens == 8192
    assert profile.selected_candidate_id == EXPECTED_16K_CANDIDATE_ID
    assert profile.differing_model_fields == ("max_output_tokens",)
    assert usage.exact_request_completion_bound_tokens == 16384
    assert usage.provider_reported_accounting_margin_tokens == 1
    assert usage.maximum_accounting_admissible_completion_tokens == 16385
    assert usage.charge_actual_provider_reported_usage
    assert not usage.usage_clipping_allowed
    assert usage.two_or_more_excess_tokens_fail_closed
    assert usage.accounting_margin_cannot_change_completion_usability
    assert report.provider_usage_semantics_contract_id == usage.contract_id


def test_v26_103_rematerializes_tasks_and_margin_aware_paths(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, report = built
    tasks = tuple(
        Exact16KTaskPackage.model_validate(item)
        for item in json.loads((output / "exact_16k_task_packages.json").read_text())
    )
    old_tasks = tuple(
        Exact8KTaskPackage.model_validate(item)
        for item in json.loads((V26_99_DIR / "exact_8k_task_packages.json").read_text())
    )
    paths = tuple(
        Exact16KPathAudit.model_validate(item)
        for item in json.loads((output / "exact_16k_path_audits.json").read_text())
    )
    old_paths = tuple(
        Exact8KPathAudit.model_validate(item)
        for item in json.loads((V26_99_DIR / "exact_8k_path_audits.json").read_text())
    )
    old_path_by_id = {item.audit_id: item for item in old_paths}

    assert len(tasks) == len(old_tasks) == 24
    assert not (
        {item.task_package_id for item in tasks} & {item.task_package_id for item in old_tasks}
    )
    assert all(item.selected_candidate_id == EXPECTED_16K_CANDIDATE_ID for item in tasks)
    assert all(item.completion_upper_bound_tokens == 16384 for item in tasks)
    assert len(paths) == len(old_paths) == 48
    for item in paths:
        predecessor = old_path_by_id[item.predecessor_path_audit_id]
        base = predecessor.candidate_budgets[1]
        expected_delta = predecessor.primary_request_count + 1
        assert item.compiler_state_row_ids == predecessor.compiler_state_row_ids
        assert (
            item.maximum_primary_prompt_utf8_bytes == predecessor.maximum_primary_prompt_utf8_bytes
        )
        assert item.maximum_rescue_prompt_utf8_bytes == predecessor.maximum_rescue_prompt_utf8_bytes
        assert item.selected_candidate_budget.full_path_token_upper_bound == (
            base.full_path_token_upper_bound + expected_delta
        )
        assert item.selected_candidate_budget.rollout_headroom_tokens == (
            base.rollout_headroom_tokens - expected_delta
        )
        assert item.provider_accounting_margin_tokens_per_call == 1
    assert report.exact_16k_task_package_count == 24
    assert report.exact_16k_path_audit_count == 48


def test_v26_103_preserves_assignments_and_seeds_under_fresh_job_ids(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, report = built
    manifest = Exact16KManifest.model_validate_json(
        (output / "exact_16k_job_manifest.json").read_text()
    )
    predecessor = Exact8KManifest.model_validate_json(
        (V26_99_DIR / "exact_8k_job_manifest.json").read_text()
    )
    preservation = Exact16KDesignPreservationAudit.model_validate_json(
        (output / "design_preservation_audit.json").read_text()
    )

    assert tuple(item.job_seed for item in manifest.jobs) == tuple(
        item.job_seed for item in predecessor.jobs
    )
    assert tuple(item.source_task_artifact_id for item in manifest.jobs) == tuple(
        item.source_task_artifact_id for item in predecessor.jobs
    )
    assert tuple(item.mechanism_id for item in manifest.jobs) == tuple(
        item.mechanism_id for item in predecessor.jobs
    )
    assert tuple(item.path_strategy_id for item in manifest.jobs) == tuple(
        item.path_strategy_id for item in predecessor.jobs
    )
    assert not (
        {item.job_id for item in manifest.jobs} & {item.job_id for item in predecessor.jobs}
    )
    assert manifest.higher_bound_job_count == 0
    assert preservation.job_seed_assignment_pass_count == 32
    assert preservation.expected_usage_margin_budget_change_only
    assert report.preserved_seed_count == 32


def test_v26_103_closes_profile_usage_and_parent_bindings(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, report = built
    usage = ProviderUsageSemanticsContract.model_validate_json(
        (output / "provider_usage_semantics_contract.json").read_text()
    )
    contract = Exact16KCompletionContract.model_validate_json(
        (output / "exact_16k_completion_contract.json").read_text()
    )
    manifest = Exact16KManifest.model_validate_json(
        (output / "exact_16k_job_manifest.json").read_text()
    )
    binding = Exact16KCrossArtifactBindingAudit.model_validate_json(
        (output / "cross_artifact_binding_audit.json").read_text()
    )

    assert contract.selected_completion_upper_bound_tokens == 16384
    assert contract.selected_rollout_upper_bound_tokens == 240000
    assert contract.provider_usage_semantics_contract_id == usage.contract_id
    assert manifest.provider_usage_semantics_contract_id == usage.contract_id
    assert binding.provider_usage_semantics_contract_id == usage.contract_id
    assert all(
        item.provider_usage_semantics_contract_id == usage.contract_id for item in binding.rows
    )
    assert binding.required_future_client_max_tokens == 16384
    assert binding.required_future_accounting_margin_tokens == 1
    assert binding.task_package_binding_pass_count == 24
    assert binding.path_binding_pass_count == 48
    assert binding.job_binding_pass_count == 32
    assert binding.static_execution_identity_chain_closed
    assert not binding.runner_implementation_materialized
    assert report.static_cross_artifact_binding_pass_count == 104
    assert report.next_permitted_stage == NEXT_PERMITTED_STAGE


def test_v26_103_freezes_final_bound_stop_rules(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, _ = built
    contract = Exact16KCompletionContract.model_validate_json(
        (output / "exact_16k_completion_contract.json").read_text()
    )

    assert contract.any_length_failure_next_stage == (
        "true_two_stage_thinking_decision_protocol_only"
    )
    assert contract.any_nonlength_completion_failure_next_stage == (
        "completion_contract_root_cause_audit_only"
    )
    assert contract.completion_usable_but_low_program_closure_next_stage == (
        "completion_tuning_stop_behavior_diagnosis_only"
    )
    assert contract.fully_passing_denominator_next_stage == "thinking_role_protocol_freeze_only"
    assert contract.single_stage_completion_bound_ladder_terminated_after_16k
    assert not contract.higher_bound_candidate_registered
    assert not contract.automatic_bound_escalation_allowed


def test_v26_103_freshness_and_30_destructive_controls_fail_closed(
    built: tuple[Path, Exact16KRematerializationReport],
) -> None:
    output, _ = built
    freshness = Exact16KFreshnessAudit.model_validate_json(
        (output / "freshness_audit.json").read_text()
    )
    destructive = Exact16KDestructiveAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )

    assert freshness.fresh_task_package_identity_count == 24
    assert freshness.fresh_path_audit_identity_count == 48
    assert freshness.fresh_job_identity_count == 32
    assert freshness.preserved_seed_value_count == 32
    assert freshness.model_exposed_source_task_count == 22
    assert freshness.model_unexposed_source_task_count == 2
    assert freshness.higher_bound_job_count == 0
    assert destructive.rejected_mutation_count == 30
    assert all(item.rejected for item in destructive.mutation_results)
    assert destructive.provider_calls == destructive.gpu_jobs == 0


def test_v26_103_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, Exact16KRematerializationReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_16k_binding_and_usage_semantics(
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
