from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_8k_binding_rematerialization import (  # noqa: E501
    EXPECTED_8K_MODEL_CONFIG_ID,
    EXPECTED_8K_THINKING_BINDING_ID,
    EXPECTED_BOUND_PROTOCOL_ID,
    EXPECTED_INITIAL_CANDIDATE_ID,
    NEXT_PERMITTED_STAGE,
    PROFILE_PATH,
    RUN_ID,
    Exact8KCompletionContract,
    Exact8KCrossArtifactBindingAudit,
    Exact8KDesignPreservationAudit,
    Exact8KDestructiveAudit,
    Exact8KFreshnessAudit,
    Exact8KManifest,
    Exact8KPathAudit,
    Exact8KProfileBinding,
    Exact8KRematerializationReport,
    Exact8KSourceReplayAudit,
    Exact8KTaskPackage,
    build_thinking_8k_binding_rematerialization,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_completion_bound_redesign_preflight import (  # noqa: E501
    CompletionBoundManifest,
    CompletionBoundPathAudit,
    CompletionBoundTaskPackage,
)
from trusted_synthesis.runtime.agent.prospective_thinking import bind_prospective_thinking
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("TRUSTED_SYNTHESIS_PACKAGE_ROOT", LOCAL_PACKAGE_ROOT))
V26_97_DIR = (
    PACKAGE_ROOT
    / "artifacts/vtdo_experiment"
    / "finance_v26_97_thinking_completion_bound_redesign_preflight_v1_20260822"
)


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Exact8KRematerializationReport]:
    output = tmp_path_factory.mktemp("v26_99_exact_8k")
    report = build_thinking_8k_binding_rematerialization(
        run_id=RUN_ID,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_v26_99_replays_every_predecessor_and_new_binding_file(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, report = built
    audit = Exact8KSourceReplayAudit.model_validate_json(
        (output / "source_replay_audit.json").read_text()
    )

    assert audit.replayed_file_count == audit.replay_pass_count == 755
    assert audit.predecessor_transitive_source_count == 746
    assert audit.predecessor_output_count == 7
    assert audit.implementation_source_count == audit.persisted_profile_count == 1
    assert audit.replay_before_rematerialization
    assert not audit.credential_lookup_attempted
    assert not audit.model_client_constructed
    assert audit.provider_calls == audit.gpu_jobs == 0
    assert report.source_replay_audit_id == audit.audit_id


def test_v26_99_persists_the_exact_8k_profile(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, _ = built
    audit = Exact8KProfileBinding.model_validate_json(
        (output / "exact_8k_profile_binding.json").read_text()
    )
    payload = json.loads((LOCAL_PACKAGE_ROOT / PROFILE_PATH).read_text())["model"]
    config = AgentModelConfig.model_validate(payload)

    assert config.max_output_tokens == 8192
    assert config.public_manifest_hash == EXPECTED_8K_MODEL_CONFIG_ID
    assert bind_prospective_thinking(config).binding_id == EXPECTED_8K_THINKING_BINDING_ID
    assert audit.model_config_id == EXPECTED_8K_MODEL_CONFIG_ID
    assert audit.thinking_binding_id == EXPECTED_8K_THINKING_BINDING_ID
    assert audit.differing_model_fields == ("max_output_tokens",)
    assert audit.exact_8k_profile_persisted
    assert not audit.model_client_constructed


def test_v26_99_rematerializes_all_taskpackages_without_semantic_change(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, report = built
    tasks = tuple(
        Exact8KTaskPackage.model_validate(item)
        for item in json.loads((output / "exact_8k_task_packages.json").read_text())
    )
    predecessor = tuple(
        CompletionBoundTaskPackage.model_validate(item)
        for item in json.loads((V26_97_DIR / "completion_bound_task_packages.json").read_text())
    )
    preservation = Exact8KDesignPreservationAudit.model_validate_json(
        (output / "design_preservation_audit.json").read_text()
    )

    assert len(tasks) == len(predecessor) == 24
    assert len({item.task_package_id for item in tasks}) == 24
    assert not (
        {item.task_package_id for item in tasks} & {item.task_package_id for item in predecessor}
    )
    assert all(item.model_config_id == EXPECTED_8K_MODEL_CONFIG_ID for item in tasks)
    assert all(item.thinking_binding_id == EXPECTED_8K_THINKING_BINDING_ID for item in tasks)
    assert all(item.completion_bound_protocol_id == EXPECTED_BOUND_PROTOCOL_ID for item in tasks)
    assert all(item.selected_candidate_id == EXPECTED_INITIAL_CANDIDATE_ID for item in tasks)
    assert preservation.task_package_semantic_pass_count == 24
    assert report.exact_8k_task_package_count == 24


def test_v26_99_rebinds_all_paths_without_prompt_or_budget_change(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, report = built
    paths = tuple(
        Exact8KPathAudit.model_validate(item)
        for item in json.loads((output / "exact_8k_path_audits.json").read_text())
    )
    predecessor = tuple(
        CompletionBoundPathAudit.model_validate(item)
        for item in json.loads((V26_97_DIR / "completion_bound_path_audits.json").read_text())
    )
    predecessor_by_id = {item.audit_id: item for item in predecessor}
    preservation = Exact8KDesignPreservationAudit.model_validate_json(
        (output / "design_preservation_audit.json").read_text()
    )

    assert len(paths) == len(predecessor) == 48
    assert not ({item.audit_id for item in paths} & set(predecessor_by_id))
    for item in paths:
        old = predecessor_by_id[item.predecessor_path_audit_id]
        assert item.compiler_state_row_ids == old.compiler_state_row_ids
        assert item.maximum_primary_prompt_utf8_bytes == old.maximum_primary_prompt_utf8_bytes
        assert item.maximum_rescue_prompt_utf8_bytes == old.maximum_rescue_prompt_utf8_bytes
        assert item.candidate_budgets == old.candidate_budgets
    assert preservation.path_prompt_budget_pass_count == 48
    assert preservation.prompt_or_rescue_change_count == 0
    assert report.exact_8k_path_audit_count == 48


def test_v26_99_preserves_manifest_assignments_and_all_seed_values(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, report = built
    manifest = Exact8KManifest.model_validate_json(
        (output / "exact_8k_job_manifest.json").read_text()
    )
    predecessor = CompletionBoundManifest.model_validate_json(
        (V26_97_DIR / "completion_bound_job_manifest.json").read_text()
    )
    preservation = Exact8KDesignPreservationAudit.model_validate_json(
        (output / "design_preservation_audit.json").read_text()
    )

    assert len(manifest.jobs) == len(predecessor.jobs) == 32
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
    assert manifest.fallback_job_count == 0
    assert preservation.job_seed_assignment_pass_count == 32
    assert preservation.seed_value_change_count == 0
    assert preservation.job_assignment_change_count == 0
    assert report.preserved_seed_count == 32


def test_v26_99_closes_static_cross_artifact_binding_without_runner(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, report = built
    contract = Exact8KCompletionContract.model_validate_json(
        (output / "exact_8k_completion_contract.json").read_text()
    )
    manifest = Exact8KManifest.model_validate_json(
        (output / "exact_8k_job_manifest.json").read_text()
    )
    binding = Exact8KCrossArtifactBindingAudit.model_validate_json(
        (output / "cross_artifact_binding_audit.json").read_text()
    )

    assert contract.model_config_id == manifest.model_config_id == EXPECTED_8K_MODEL_CONFIG_ID
    assert contract.thinking_binding_id == manifest.thinking_binding_id
    assert contract.initial_completion_upper_bound_tokens == 8192
    assert manifest.completion_upper_bound_tokens == 8192
    assert binding.task_package_binding_pass_count == 24
    assert binding.path_binding_pass_count == 48
    assert binding.job_binding_pass_count == 32
    assert binding.contract_task_package_ids == contract.task_package_ids
    assert binding.contract_path_audit_ids == contract.path_audit_ids
    assert binding.manifest_contract_id == manifest.contract_id == contract.contract_id
    assert binding.manifest_job_ids == tuple(item.job_id for item in manifest.jobs)
    path_to_task = {
        item.artifact_id: item.task_package_id
        for item in binding.rows
        if item.artifact_kind == "path"
    }
    assert all(
        item.contract_id == contract.contract_id
        and path_to_task[item.path_audit_id] == item.task_package_id
        for item in binding.rows
        if item.artifact_kind == "job" and item.path_audit_id is not None
    )
    assert binding.static_execution_identity_chain_closed
    assert binding.actual_client_binding_deferred_to_runner_preflight
    assert not binding.runner_implementation_materialized
    assert not binding.model_client_constructed
    assert binding.provider_calls == 0
    assert report.static_cross_artifact_binding_pass_count == 104
    assert report.static_execution_identity_chain_closed
    assert not report.execution_authorized
    assert report.next_permitted_stage == NEXT_PERMITTED_STAGE


def test_v26_99_freshness_and_destructive_controls_fail_closed(
    built: tuple[Path, Exact8KRematerializationReport],
) -> None:
    output, _ = built
    freshness = Exact8KFreshnessAudit.model_validate_json(
        (output / "freshness_audit.json").read_text()
    )
    destructive = Exact8KDestructiveAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text()
    )

    assert freshness.fresh_task_package_identity_count == 24
    assert freshness.fresh_path_audit_identity_count == 48
    assert freshness.fresh_job_identity_count == 32
    assert freshness.preserved_seed_value_count == 32
    assert freshness.model_exposed_source_task_count == 22
    assert freshness.model_unexposed_source_task_count == 2
    assert freshness.fallback_16k_job_count == 0
    assert destructive.rejected_mutation_count == 25
    assert all(item.rejected for item in destructive.mutation_results)
    assert not destructive.credential_lookup_attempted
    assert not destructive.model_client_constructed
    assert destructive.provider_calls == destructive.gpu_jobs == 0


def test_v26_99_dual_build_is_byte_identical_and_privacy_redacted(
    built: tuple[Path, Exact8KRematerializationReport],
    tmp_path: Path,
) -> None:
    formal, formal_report = built
    independent = tmp_path / "independent"
    independent_report = build_thinking_8k_binding_rematerialization(
        run_id=RUN_ID,
        output_dir=independent,
        package_root=PACKAGE_ROOT,
    )
    formal_files = sorted(path.name for path in formal.iterdir() if path.is_file())
    independent_files = sorted(path.name for path in independent.iterdir() if path.is_file())

    assert formal_files == independent_files
    assert len(formal_files) == 11
    assert all(
        (formal / name).read_bytes() == (independent / name).read_bytes() for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id
    serialized = b"".join((formal / name).read_bytes() for name in formal_files)
    assert b'"reasoning_content"' not in serialized
    assert b'"raw_http_body"' not in serialized
