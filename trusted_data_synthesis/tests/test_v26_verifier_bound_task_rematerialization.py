from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_operation_hardening import (  # noqa: E501
    AuthorityPreservingTaskAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_task_rematerialization import (  # noqa: E501
    V26_VERIFIER_IMPLEMENTATION_VERSION,
    VerifierBoundDefinitionPairCapacityAudit,
    VerifierBoundFreshnessAudit,
    VerifierBoundInstrumentPopulationReport,
    VerifierV2TaskReplayBinding,
    build_verifier_bound_instrument_population,
)
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
DEVELOPMENT = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "development.json"
)
SECONDARY = (
    ARTIFACT_ROOT
    / "finance_v26_42_no_api_joint_scaffold_20260817"
    / "population"
    / "confirmation_source.json"
)
TERTIARY_ROOT = ARTIFACT_ROOT / "finance_v26_40_no_api_joint_scaffold_20260817"
TERTIARY = TERTIARY_ROOT / "population" / "confirmation_source.json"
V26_56 = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"
V26_65 = ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
V26_69 = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
V26_75 = ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
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
FORMAL = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
RUN_ID = "finance_v26_76_verifier_bound_instrument_population_20260819"
SELECTION_SALT = "finance_v26_76_verifier_bound_instrument_population_v1"
DETAIL_FILES = (
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
    "report.json",
    "source_freshness_audit.json",
    "static_model_authority_path_catalogs.json",
    "tool_environment_manifests.json",
    "verifier_v2_replay_bindings.json",
)


def _build(output: Path) -> VerifierBoundInstrumentPopulationReport:
    return build_verifier_bound_instrument_population(
        run_id=RUN_ID,
        development_population_path=DEVELOPMENT,
        secondary_source_path=SECONDARY,
        tertiary_source_path=TERTIARY,
        tertiary_no_api_report_path=TERTIARY_ROOT / "report.json",
        v26_56_dir=V26_56,
        v26_65_dir=V26_65,
        v26_69_dir=V26_69,
        verifier_qualification_dir=V26_75,
        snapshot_path=SNAPSHOT,
        exposure_receipt_path=EXPOSURE_RECEIPT,
        selection_salt=SELECTION_SALT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_76_rebuild")
    _build(output)
    return output


def _load_list(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def test_v26_76_is_deterministic_and_matches_formal(
    rebuilt: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in DETAIL_FILES:
        assert (rebuilt / relative).read_bytes() == (duplicate / relative).read_bytes()
        assert (rebuilt / relative).read_bytes() == (FORMAL / relative).read_bytes()


def test_v26_76_freshness_and_reconciliation_capacity(rebuilt: Path) -> None:
    freshness = VerifierBoundFreshnessAudit.model_validate_json(
        (rebuilt / "source_freshness_audit.json").read_text(encoding="utf-8")
    )
    capacity = VerifierBoundDefinitionPairCapacityAudit.model_validate_json(
        (rebuilt / "definition_pair_capacity_audit.json").read_text(encoding="utf-8")
    )

    assert freshness.selected_task_count == 8
    assert freshness.selected_nonreconciliation_source_task_count == 6
    assert freshness.selected_reconciliation_evidence_count == 8
    assert all(item.overlap_count == 0 and not item.overlap_values for item in freshness.channels)
    assert not freshness.historical_model_outcomes_used_for_selection
    assert not freshness.historical_diagnostic_candidates_used_for_selection
    assert capacity.eligible_definition_pair_count >= 4
    assert capacity.eligible_reconciliation_task_capacity >= 2
    assert capacity.selected_definition_pair_count == 4
    assert capacity.selected_reconciliation_task_count == 2


def test_task_packages_freeze_verifier_v2_before_identity(rebuilt: Path) -> None:
    records = _load_list(rebuilt / "operational_task_records.json", OperationalTaskRecord)
    environments = _load_list(
        rebuilt / "tool_environment_manifests.json", AgentToolEnvironmentManifest
    )
    bindings = _load_list(rebuilt / "verifier_v2_replay_bindings.json", VerifierV2TaskReplayBinding)
    environment_ids = {item.manifest_id for item in environments}
    binding_by_source = {item.semantic_source_id: item for item in bindings}

    assert len(records) == len(bindings) == len(environments) == 8
    assert Counter(item.mechanism_id for item in records) == {
        "context_conditioned_action": 2,
        "semantic_reconciliation": 2,
        "failure_recovery": 2,
        "state_dependent_stopping": 2,
    }
    for record in records:
        package = record.task_package
        binding = binding_by_source[package.semantic_source.semantic_source_id]
        oracle = package.task.oracle.selection_contract["authority_preserving_verifier_v2_binding"]
        assert record.environment_manifest_id in environment_ids
        assert package.verifier_binding.verifier_implementation_id == binding.contract_id
        assert package.verifier_binding.verifier_version == V26_VERIFIER_IMPLEMENTATION_VERSION
        assert oracle["task_replay_binding_contract_id"] == binding.contract_id
        assert oracle["qualified_replay_contract_id"] == binding.qualified_replay_contract_id
        assert binding.environment_manifest_id == record.environment_manifest_id
        assert binding.environment_manifest_hash == record.environment_manifest_hash


def test_static_witnesses_and_mutations_pass(rebuilt: Path) -> None:
    witnesses = _load_list(
        rebuilt / "operational_public_witnesses.json", BoundPublicExecutableWitness
    )
    closures = _load_list(rebuilt / "operation_closure_audits.json", OperationClosureAudit)
    audits = _load_list(
        rebuilt / "authority_preserving_task_audits.json", AuthorityPreservingTaskAudit
    )
    admissions = _load_list(rebuilt / "operational_task_admissions.json", OperationalTaskAdmission)

    assert len(witnesses) == len(closures) == len(audits) == len(admissions) == 8
    assert all(item.full_validity_passed and item.compiler_generated for item in witnesses)
    assert all(item.status == "passed" for item in closures)
    assert sum(len(item.mutation_results) for item in closures) == 64
    assert all(item.status == "passed" for item in audits)
    assert sum(len(item.verification_mutations) for item in audits) == 40
    assert all(item.operational_capability_eligible for item in admissions)
    assert not any(item.operational_vtdo_candidate_eligible for item in admissions)


def test_v26_76_authorizes_only_static_preflight(rebuilt: Path) -> None:
    report = VerifierBoundInstrumentPopulationReport.model_validate_json(
        (rebuilt / "report.json").read_text(encoding="utf-8")
    )

    assert report.task_count == 8
    assert report.verifier_v2_replay_binding_count == 8
    assert report.next_permitted_stage == "verifier_v2_bound_instrument_preflight_only"
    assert report.instrument_preflight_authorized
    assert not report.instrument_requalification_authorized
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert report.model_api_calls == report.gpu_jobs == report.production_contribution == 0


def test_v26_76_identity_mutations_fail_closed(rebuilt: Path) -> None:
    binding = json.loads(
        (rebuilt / "verifier_v2_replay_bindings.json").read_text(encoding="utf-8")
    )[0]
    binding["qualified_replay_contract_id"] = "finance_v26_authority_verifier_contract:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        VerifierV2TaskReplayBinding.model_validate(binding)

    report = json.loads((rebuilt / "report.json").read_text(encoding="utf-8"))
    report["report_id"] = "finance_v26_verifier_bound_instrument_population_report:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        VerifierBoundInstrumentPopulationReport.model_validate(report)
