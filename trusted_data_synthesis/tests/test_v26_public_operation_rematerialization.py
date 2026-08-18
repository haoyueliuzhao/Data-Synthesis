from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.public_operation import (
    OperationalExecutableTaskPackage,
    OperationalExecutableVerifierBinding,
    PublicOperationContractView,
    PublicStopReadinessContract,
    operational_executable_verifier_binding_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_pipeline import (
    build_v26_public_operation_rematerialization,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    PublicOperationRematerializationReport,
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
PRIOR = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"
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
DETAIL_FILES = (
    "definition_pair_capacity_audit.json",
    "mechanism_counterfactual_replays.json",
    "mechanism_necessity_artifacts.json",
    "operation_closure_audits.json",
    "operational_public_witnesses.json",
    "operational_task_admissions.json",
    "operational_task_records.json",
    "operational_witness_observations.json",
    "source_freshness_audit.json",
    "static_model_authority_path_catalogs.json",
    "tool_environment_manifests.json",
)


@pytest.fixture(scope="module")
def built_population(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("v26_public_operation_rematerialization")
    outputs = (root / "first", root / "determinism")
    for output in outputs:
        build_v26_public_operation_rematerialization(
            run_id="finance_v26_60_test",
            development_population_path=DEVELOPMENT,
            secondary_source_path=SECONDARY_SOURCE,
            tertiary_source_path=TERTIARY_SOURCE,
            tertiary_no_api_report_path=TERTIARY_ROOT / "report.json",
            prior_rematerialization_dir=PRIOR,
            snapshot_path=SNAPSHOT,
            exposure_receipt_path=EXPOSURE_RECEIPT,
            sampling_salt="finance-v26.60-public-operation-rematerialization-20260818",
            output_dir=output,
        )
    return outputs


def _rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def _report(path: Path) -> PublicOperationRematerializationReport:
    return PublicOperationRematerializationReport.model_validate_json(
        (path / "report.json").read_text(encoding="utf-8")
    )


def test_static_operational_support_passes_without_authorizing_measurement(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)

    assert report.target_mechanism_task_counts == {
        "context_conditioned_action": 6,
        "semantic_reconciliation": 6,
        "failure_recovery": 6,
        "state_dependent_stopping": 6,
    }
    assert report.public_operation_contract_count == 24
    assert report.operation_closure_pass_count == 24
    assert report.public_witness_pass_count == 24
    assert report.compiler_witness_pass_count == 48
    assert report.compiler_generated_witness_count == 48
    assert report.mechanism_necessity_pass_count == 24
    assert report.operational_capability_eligible_count == 24
    assert report.operational_vtdo_candidate_eligible_count == 12
    assert report.static_model_authority_path_count == 36
    assert report.destructive_mutation_count == 192
    assert report.model_generated_path_count == 0
    assert report.status == "passed"
    assert report.next_permitted_stage == "fresh_operation_closure_regression_protocol_only"
    assert report.small_regression_protocol_authorized
    assert not report.capability_development_authorized
    assert not report.state_reachability_pilot_authorized
    assert not report.fresh_confirmation_authorized
    assert not report.no_c_vtdo_authorized
    assert not report.student_training_authorized
    assert not report.exact_target_authorized
    assert not report.gp_c_authorized
    assert report.production_contribution == report.model_api_calls == report.gpu_jobs == 0
    for item in report.implementation_source_files:
        assert (
            item.sha256
            == hashlib.sha256((PACKAGE_ROOT / item.relative_path).read_bytes()).hexdigest()
        )


def test_freshness_keeps_source_container_and_row_identities_separate(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    audit = json.loads((first / "source_freshness_audit.json").read_text(encoding="utf-8"))

    assert len(audit["source_population_ids"]) == 3
    assert audit["tertiary_model_api_calls"] == audit["tertiary_gpu_jobs"] == 0
    assert (
        audit["tertiary_no_api_report_sha256"]
        == hashlib.sha256((TERTIARY_ROOT / "report.json").read_bytes()).hexdigest()
    )
    assert audit["source_container_reuse_policy"] == (
        "immutable_container_shared_rows_must_be_identity_disjoint"
    )
    assert len(audit["shared_read_only_source_container_ids"]) == 1
    assert audit["selected_reconciliation_source_record_overlap_count"] == 0
    assert {item["channel"] for item in audit["channels"]} == {
        "source_task_artifact_id",
        "source_task_semantic_signature",
        "source_task_hash",
        "evidence_id",
        "evidence_version_id",
        "source_record_id",
    }
    assert all(item["overlap_count"] == 0 for item in audit["channels"])


def test_public_contract_binds_program_verifier_progress_and_stop_without_private_ids(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)

    for record in report.task_records:
        package = record.task_package
        view = package.operation_contract.public_view
        stop = package.stop_readiness_contract
        public_payload = json.dumps(package.task.public.model_dump(mode="json"), sort_keys=True)
        assert all(item not in public_payload for item in record.target_program_evidence_ids)
        assert "source_program_node_id" not in public_payload
        assert "expected_operator_id" not in public_payload
        assert not view.exact_tool_sequence_required
        assert not view.gold_evidence_ids_exposed
        assert not view.oracle_node_ids_exposed
        assert not view.correct_choice_exposed_for_model_choice
        assert set(stop.required_node_ids) == {item.node_id for item in view.nodes}
        assert stop.terminal_node_id == view.terminal_node_id
        assert package.operation_contract.source_program_dag_hash == (
            package.verifier_binding.source_program_dag_hash
        )
        assert package.operation_contract.source_verifier_dag_hash == (
            package.verifier_binding.source_verifier_dag_hash
        )
        assert {item.public_node_id for item in package.verifier_binding.node_bindings} == {
            item.node_id for item in view.nodes
        }
        guidance = package.task.public.metadata["agent_contract_guidance"]
        assert guidance["public_operation_execution_contract"] == view.model_dump(mode="json")
        assert guidance["public_stop_readiness_contract"] == stop.model_dump(mode="json")


def test_every_runtime_witness_and_acquisition_path_closes_the_same_terminal(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    witnesses = _rows(first / "operational_public_witnesses.json")
    closures = _rows(first / "operation_closure_audits.json")

    assert len(witnesses) == 48
    assert all(item["full_validity_passed"] for item in witnesses)
    assert Counter(item["path_strategy_id"] for item in witnesses) == Counter(
        {
            "structured_direct": 24,
            "search_then_structured": 12,
            "search_then_open": 12,
        }
    )
    assert len(closures) == 24
    for audit in closures:
        paths = audit["path_results"]
        assert all(item["stop_ready"] for item in paths)
        assert len({item["normalized_answer_hash"] for item in paths}) == 1
        assert not audit["exact_tool_sequence_exposed"]
        assert not audit["correct_model_choice_exposed"]
        assert not audit["compiler_used_oracle_next_action"]


def test_all_destructive_operation_mutations_fail_closed(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    closures = _rows(first / "operation_closure_audits.json")
    observed: Counter[str] = Counter()

    for audit in closures:
        mutations = audit["mutation_results"]
        ablations = [
            item for item in mutations if item["mutation_kind"] == "required_node_ablation"
        ]
        assert tuple(item["removed_node_id"] for item in ablations) == tuple(
            audit["required_node_ids"]
        )
        assert all(item["failure_closed"] and not item["stop_ready"] for item in mutations)
        assert audit["every_required_node_ablation_failed_closed"]
        assert audit["target_mechanism_counterfactual_failed_closed"]
        assert audit["public_oracle_isolation_passed"]
        observed.update(item["mutation_kind"] for item in mutations)
        post = next(item for item in mutations if item["mutation_kind"] == "postcompletion_action")
        assert post["postcompletion_violation"]
        assert post["runtime_rejection_error_code"] == (
            "redundant_action_after_public_operation_completion"
        )
        reordered = next(
            item for item in mutations if item["mutation_kind"] == "terminal_before_prerequisite"
        )
        assert reordered["runtime_rejection_error_code"] is not None

    assert sum(observed.values()) == 192
    assert observed["terminal_before_prerequisite"] == 24
    assert observed["first_calculation_only"] == 24
    assert observed["premature_verification"] == 24
    assert observed["terminal_missing"] == 24
    assert observed["postcompletion_action"] == 24


def test_reconciliation_terminal_consumes_public_normalization_references(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)
    environments = {
        item.environment_manifest_id
        for item in report.task_records
        if item.mechanism_id == "semantic_reconciliation"
    }
    rows = [
        item
        for item in _rows(first / "operational_witness_observations.json")
        if item["environment_manifest_id"] in environments
    ]
    emitted: dict[str, set[str]] = defaultdict(set)
    consumed: dict[str, set[str]] = defaultdict(set)
    for item in rows:
        environment = item["environment_manifest_id"]
        if item["call"]["tool_id"] == "normalize_metric_unit_period":
            emitted[environment].add(item["result"]["normalized_operation_ref"])
    for item in rows:
        environment = item["environment_manifest_id"]
        if item["call"]["tool_id"] != "calculator":
            continue
        for operand in item["call"]["arguments"]["operands"]:
            operation_ref = operand.get("operation_ref")
            if operation_ref in emitted[environment]:
                assert operand["selector"] == "normalized_inputs.target"
                assert "evidence_id" not in operand
                consumed[environment].add(operation_ref)
    assert set(emitted) == environments
    assert all(len(values) == 2 for values in emitted.values())
    assert consumed == emitted


def test_contract_mutations_fail_before_a_task_can_retain_its_identity(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    package = _report(first).task_records[0].task_package

    view_payload = package.operation_contract.public_view.model_dump(mode="python")
    view_payload["variables"][0]["semantic_role"] = "evidence:private-forbidden"
    with pytest.raises(ValidationError, match="private identity"):
        PublicOperationContractView.model_validate(view_payload)

    stop_payload = package.stop_readiness_contract.model_dump(mode="python")
    stop_payload["required_node_ids"] = tuple(
        item
        for item in stop_payload["required_node_ids"]
        if item != stop_payload["terminal_node_id"]
    )
    with pytest.raises(ValidationError, match="omits the terminal node"):
        PublicStopReadinessContract.model_validate(stop_payload)

    package_payload = package.model_dump(mode="python")
    binding_payload = dict(package_payload["verifier_binding"])
    binding_payload["source_verifier_dag_hash"] = "source_verifier_dag:foreign"
    values = {key: value for key, value in binding_payload.items() if key != "binding_id"}
    provisional = OperationalExecutableVerifierBinding.model_construct(
        binding_id="pending", **values
    )
    binding_payload["binding_id"] = operational_executable_verifier_binding_id(provisional)
    package_payload["verifier_binding"] = binding_payload
    with pytest.raises(ValidationError, match="another Verifier DAG"):
        OperationalExecutableTaskPackage.model_validate(package_payload)


def test_all_outputs_rebuild_byte_identically(
    built_population: tuple[Path, Path],
) -> None:
    first, second = built_population
    for name in (*DETAIL_FILES, "report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
