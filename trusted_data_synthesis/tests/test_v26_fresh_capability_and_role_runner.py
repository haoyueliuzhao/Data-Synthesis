from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_runner import (  # noqa: E501
    AuthorityPreservingRoleContract,
    AuthorityPreservingRoleJobManifest,
    AuthorityPreservingRoleReport,
    run_authority_preserving_role,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_role_protocol import (  # noqa: E501
    EmpiricalRoleProtocolReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_capability_population import (  # noqa: E501
    FreshCapabilityFreshnessAudit,
    FreshCapabilityPopulationReport,
    build_fresh_capability_population,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
DEVELOPMENT = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "development.json"
)
SECONDARY_SOURCE = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "confirmation_source.json"
)
TERTIARY_ROOT = ARTIFACT_ROOT / "finance_v26_40_no_api_joint_scaffold_20260817"
TERTIARY_SOURCE = TERTIARY_ROOT / "population" / "confirmation_source.json"
V26_56 = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"
V26_65 = ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
V26_68 = ARTIFACT_ROOT / "finance_v26_68_empirical_role_protocol_20260819"
V26_69 = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
SNAPSHOT = (
    ARTIFACT_ROOT
    / "finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816"
    / "finance_stopping_evidence_snapshot.jsonl"
)
EXPOSURE_RECEIPT = (
    ARTIFACT_ROOT
    / "finance_v26_29_exposure_grounded_source_20260817"
    / "exposure_clean_receipt.json"
)
MODEL_CONFIG = PACKAGE_ROOT / "config" / "deepseek_v4_flash_agent_v23_paired_pilot.json"
RUN_ID_69 = "finance_v26_69_fresh_capability_population_20260819"
DETAIL_FILES_69 = (
    "authority_preserving_task_audits.json",
    "contract_lineage_audit.json",
    "definition_pair_capacity_audit.json",
    "mechanism_counterfactual_replays.json",
    "mechanism_necessity_artifacts.json",
    "operation_closure_audits.json",
    "operational_public_witnesses.json",
    "operational_task_admissions.json",
    "operational_task_records.json",
    "operational_witness_observations.json",
    "reconciliation_selection_audit.json",
    "source_freshness_audit.json",
    "static_model_authority_path_catalogs.json",
    "tool_environment_manifests.json",
    "report.json",
)


@pytest.fixture(scope="module")
def rebuilt_v26_69(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_69_rebuild")
    build_fresh_capability_population(
        run_id=RUN_ID_69,
        development_population_path=DEVELOPMENT,
        secondary_source_path=SECONDARY_SOURCE,
        tertiary_source_path=TERTIARY_SOURCE,
        tertiary_no_api_report_path=TERTIARY_ROOT / "report.json",
        v26_56_dir=V26_56,
        v26_65_dir=V26_65,
        snapshot_path=SNAPSHOT,
        exposure_receipt_path=EXPOSURE_RECEIPT,
        selection_salt="finance-v26.69-fresh-capability-population-20260819",
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output


def test_v26_69_rebuild_is_byte_identical(rebuilt_v26_69: Path) -> None:
    for relative in DETAIL_FILES_69:
        assert (rebuilt_v26_69 / relative).read_bytes() == (V26_69 / relative).read_bytes()


def test_v26_69_is_fresh_balanced_and_capability_only() -> None:
    report = FreshCapabilityPopulationReport.model_validate_json(
        (V26_69 / "report.json").read_text(encoding="utf-8")
    )
    freshness = FreshCapabilityFreshnessAudit.model_validate_json(
        (V26_69 / "source_freshness_audit.json").read_text(encoding="utf-8")
    )

    assert report.mechanism_task_counts == {
        "context_conditioned_action": 3,
        "semantic_reconciliation": 3,
        "failure_recovery": 3,
        "state_dependent_stopping": 3,
    }
    assert report.task_count == report.operational_capability_eligible_count == 12
    assert report.operational_vtdo_candidate_eligible_count == 0
    assert report.public_witness_pass_count == report.mechanism_necessity_pass_count == 12
    assert report.legacy_operation_mutation_count >= 96
    assert report.authority_verification_mutation_count == 60
    assert all(item.intended_use == "capability_measurement" for item in report.task_records)
    assert all(item.overlap_count == 0 and not item.overlap_values for item in freshness.channels)
    assert freshness.generated_trajectory_count == 0
    assert not freshness.historical_model_outcomes_used_for_selection
    assert report.model_api_calls == report.gpu_jobs == 0
    assert report.next_permitted_stage == "authority_preserving_role_runner_preflight_only"
    assert not report.capability_development_execution_authorized


def _preflight(
    *,
    role: str,
    output: Path,
) -> AuthorityPreservingRoleReport:
    return run_authority_preserving_role(
        run_id=f"finance_v26_70_{role}_preflight_20260819",
        role=role,  # type: ignore[arg-type]
        task_source_dir=V26_69 if role == "capability_development" else V26_65,
        protocol_source_dir=V26_68 if role == "state_reachability" else None,
        model_config_path=MODEL_CONFIG,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        workers=4,
        audit_only=True,
    )


@pytest.mark.parametrize(
    ("role", "expected_jobs"),
    (("capability_development", 96), ("state_reachability", 360)),
)
def test_role_preflights_are_deterministic_and_construct_no_client(
    tmp_path: Path,
    role: str,
    expected_jobs: int,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = _preflight(role=role, output=first)
    duplicate = _preflight(role=role, output=second)

    assert report == duplicate
    assert report.status == "preflight"
    assert report.model_execution_authorized
    assert report.completed_rollout_count == report.provider_call_count == 0
    assert report.preflight_audit.expected_job_count == expected_jobs
    assert report.preflight_audit.source_design_binding_pass_count == expected_jobs
    assert not report.preflight_audit.model_client_constructed
    for relative in (
        "execution_contract.json",
        "job_manifest.json",
        "static_preflight_audit.json",
        "report.json",
    ):
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_reachability_manifest_preserves_every_v26_68_design_row(tmp_path: Path) -> None:
    output = tmp_path / "reachability"
    _preflight(role="state_reachability", output=output)
    contract = AuthorityPreservingRoleContract.model_validate_json(
        (output / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = AuthorityPreservingRoleJobManifest.model_validate_json(
        (output / "job_manifest.json").read_text(encoding="utf-8")
    )
    source = EmpiricalRoleProtocolReport.model_validate_json(
        (V26_68 / "report.json").read_text(encoding="utf-8")
    )

    assert len(manifest.jobs) == 360
    assert Counter(item.sampling_mode for item in manifest.jobs) == Counter(
        {"reachability_unconditional": 144, "reachability_conditioned": 216}
    )
    assert {item.source_design_job_id for item in manifest.jobs} == {
        item.job_id for item in source.protocol.reachability_jobs
    }
    assert set(contract.static_state_ids) == set(source.protocol.source_static_state_ids)
    assert len(contract.static_state_ids) == 36
    assert all(
        item.requested_static_path_id is None
        and item.requested_quotient_state_id is None
        and item.public_condition_id is None
        for item in manifest.jobs
        if item.sampling_mode == "reachability_unconditional"
    )


def test_source_tamper_fails_before_model_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "tampered_source"
    shutil.copytree(V26_69, source)
    records = source / "operational_task_records.json"
    records.write_text(records.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    def forbidden_client(*args: object, **kwargs: object) -> None:
        raise AssertionError("model client was constructed before source replay")

    monkeypatch.setattr(
        "trusted_synthesis.experiments.vtdo_experiment."
        "phase1_v26_authority_preserving_role_runner.OpenAICompatibleJsonClient",
        forbidden_client,
    )
    with pytest.raises(ValueError, match="source Artifact replay failed"):
        run_authority_preserving_role(
            run_id="tampered_capability_source",
            role="capability_development",
            task_source_dir=source,
            protocol_source_dir=None,
            model_config_path=MODEL_CONFIG,
            output_dir=tmp_path / "output",
            package_root=PACKAGE_ROOT,
            workers=1,
            audit_only=False,
        )
