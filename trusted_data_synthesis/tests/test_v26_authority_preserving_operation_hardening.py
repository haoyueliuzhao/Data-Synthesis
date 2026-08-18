from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.core.trajectory.public_operation import (
    AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION,
    AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION,
    AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION,
    AUTHORITY_PRESERVING_STOP_READINESS_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingHardeningReport,
    authority_preserving_hardening_report_id,
    build_authority_preserving_operation_hardening,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    PACKAGE_ROOT
    / "artifacts"
    / "vtdo_experiment"
    / "finance_v26_62_public_operation_instrument_hardening_20260818"
)
RUN_ID = "finance_v26_65_authority_preserving_operation_hardening_test"
DETAIL_FILES = (
    "authority_preserving_task_audits.json",
    "contract_lineage_audit.json",
    "mechanism_counterfactual_replays.json",
    "mechanism_necessity_artifacts.json",
    "operation_closure_audits.json",
    "operational_public_witnesses.json",
    "operational_task_admissions.json",
    "operational_task_records.json",
    "operational_witness_observations.json",
    "static_model_authority_path_catalogs.json",
    "tool_environment_manifests.json",
)


@pytest.fixture(scope="module")
def built_hardening(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, AuthorityPreservingHardeningReport]:
    root = tmp_path_factory.mktemp("v26_authority_preserving_hardening")
    first = root / "first"
    second = root / "second"
    report = build_authority_preserving_operation_hardening(
        run_id=RUN_ID,
        source_dir=SOURCE,
        output_dir=first,
        package_root=PACKAGE_ROOT,
    )
    repeated = build_authority_preserving_operation_hardening(
        run_id=RUN_ID,
        source_dir=SOURCE,
        output_dir=second,
        package_root=PACKAGE_ROOT,
    )
    assert repeated == report
    return first, second, report


def test_v26_65_static_hardening_passes_without_authorizing_measurement(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    _, _, report = built_hardening

    assert report.report_id == authority_preserving_hardening_report_id(report)
    assert report.fresh_task_package_count == 24
    assert report.fresh_public_runtime_contract_count == 24
    assert report.action_neutral_repair_contract_count == 24
    assert report.terminal_verification_target_count == 24
    assert report.repair_prompt_audit_pass_count == 24
    assert report.terminal_verification_audit_pass_count == 24
    assert report.public_witness_pass_count == 24
    assert report.compiler_witness_pass_count == 48
    assert report.mechanism_necessity_pass_count == 24
    assert report.operation_closure_pass_count == 24
    assert report.legacy_operation_mutation_count == 192
    assert report.authority_hardening_mutation_count == 144
    assert report.model_api_calls == report.gpu_jobs == 0
    assert report.status == "passed"
    assert report.next_permitted_stage == (
        "fresh_authority_preserving_instrument_requalification_protocol_only"
    )
    assert report.small_instrument_requalification_authorized
    assert not report.capability_development_authorized
    assert not report.state_reachability_pilot_authorized
    assert report.production_contribution == 0


def test_v26_65_every_output_is_byte_deterministic(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    first, second, report = built_hardening

    for name in (*DETAIL_FILES, "report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for item in report.implementation_source_files:
        assert (
            item.sha256
            == hashlib.sha256((PACKAGE_ROOT / item.relative_path).read_bytes()).hexdigest()
        )


def test_v26_65_fresh_identity_lineage_preserves_only_semantics(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    first, _, report = built_hardening
    lineage = json.loads((first / "contract_lineage_audit.json").read_text())

    assert lineage["source_report_id"] == report.source_report_id
    assert len(lineage["task_lineages"]) == 24
    assert lineage["source_model_outcome_count"] == 0
    assert not lineage["source_model_outcomes_used"]
    assert not lineage["historical_artifacts_mutated"]
    for item in lineage["task_lineages"]:
        assert item["semantic_source_unchanged"]
        assert item["operation_contract_identity_fresh"]
        assert item["public_runtime_contract_identity_fresh"]
        assert item["stop_readiness_contract_identity_fresh"]
        assert item["action_neutral_repair_contract_created"]
        assert item["terminal_verification_target_created"]
        assert item["runtime_projection_identity_fresh"]
        assert item["verifier_binding_identity_fresh"]
        assert item["environment_manifest_identity_fresh"]
        assert item["task_package_identity_fresh"]


def test_v26_65_binds_one_terminal_target_across_public_runtime_and_verifier(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    _, _, report = built_hardening

    for record in report.task_records:
        package = record.task_package
        repair = package.action_neutral_repair_contract
        target = package.terminal_verification_target
        assert repair is not None
        assert target is not None
        assert package.schema_version == AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION
        assert package.stop_readiness_contract.schema_version == (
            AUTHORITY_PRESERVING_STOP_READINESS_VERSION
        )
        assert package.runtime_projection.schema_version == (
            AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION
        )
        assert package.verifier_binding.schema_version == (
            AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION
        )
        assert package.stop_readiness_contract.terminal_verification_target_id == target.target_id
        assert package.runtime_projection.terminal_verification_target_id == target.target_id
        assert package.verifier_binding.terminal_verification_target_id == target.target_id
        assert package.runtime_projection.action_neutral_repair_contract_id == repair.contract_id
        assert package.verifier_binding.action_neutral_repair_contract_id == repair.contract_id
        assert target.public_view.required_claim_fields == ("operation_ref",)
        assert target.public_view.additional_claim_fields_policy == "forbid"
        guidance = package.task.public.metadata["agent_contract_guidance"]
        assert guidance["public_terminal_verification_target"] == (
            target.public_view.model_dump(mode="json")
        )


def test_v26_65_repair_prompts_are_action_neutral(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    _, _, report = built_hardening

    expected_fields = (
        "error_category",
        "failed_tool_id",
        "identical_arguments_forbidden",
        "unresolved_public_variables",
        "unresolved_semantic_requirements",
    )
    for audit in report.task_audits:
        repair = audit.repair_prompt_audit
        assert repair.exposed_context_fields == expected_fields
        assert repair.failed_tool_id_exposed
        assert repair.typed_error_category_exposed
        assert repair.unresolved_semantics_exposed
        assert repair.unresolved_public_variables_exposed
        assert not repair.correct_tool_disclosed
        assert not repair.correct_operator_disclosed
        assert not repair.correct_parameters_disclosed
        assert not repair.expected_arguments_disclosed
        assert repair.action_binding_paths == ()
        assert repair.raw_action_patch_removed
        assert repair.model_repair_authority_retained


def test_v26_65_terminal_verification_mutations_all_fail_closed(
    built_hardening: tuple[Path, Path, AuthorityPreservingHardeningReport],
) -> None:
    _, _, report = built_hardening

    expected = {
        "missing_terminal_reference": "terminal_verification_reference_missing",
        "wrong_terminal_reference": "terminal_verification_reference_wrong",
        "extra_terminal_claim_field": "terminal_verification_extra_claim_fields",
        "verification_before_terminal": "terminal_verification_before_terminal",
        "postcompletion_action": "redundant_action_after_public_operation_completion",
    }
    for audit in report.task_audits:
        assert audit.exact_terminal_reference_accepted
        assert audit.runtime_witness_stop_ready
        assert audit.mechanism_necessity_passed
        assert audit.operation_closure_passed
        assert audit.public_oracle_isolation_passed
        assert {
            item.mutation_kind: item.observed_error_code for item in audit.verification_mutations
        } == expected
        assert all(item.failed_closed for item in audit.verification_mutations)
