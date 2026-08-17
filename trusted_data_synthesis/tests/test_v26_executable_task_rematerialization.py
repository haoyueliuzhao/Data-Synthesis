from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.executable_task import (
    ExecutableTaskPackage,
    ExecutableVerifierBinding,
    ToolClosureContract,
    executable_verifier_binding_id,
    matching_sufficient_support_set,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    V26ExecutableTaskRematerializationReport,
    build_v26_executable_task_rematerialization,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
SOURCE_NO_API = ARTIFACT_ROOT / "finance_v26_42_no_api_joint_scaffold_20260817"
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
    "public_executable_witnesses.json",
    "public_witness_observations.json",
    "rematerialized_task_records.json",
    "static_model_authority_path_catalogs.json",
    "task_admissions.json",
    "tool_environment_manifests.json",
)


@pytest.fixture(scope="module")
def built_population(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("v26_executable_task_rematerialization")
    outputs = (root / "first", root / "determinism")
    for output in outputs:
        build_v26_executable_task_rematerialization(
            run_id="finance_v26_56_test",
            source_no_api_dir=SOURCE_NO_API,
            snapshot_path=SNAPSHOT,
            exposure_receipt_path=EXPOSURE_RECEIPT,
            sampling_salt="finance-v26-56-executable-task-rematerialization",
            output_dir=output,
        )
    return outputs


def _rows(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, list)
    return value


def _report(path: Path) -> V26ExecutableTaskRematerializationReport:
    return V26ExecutableTaskRematerializationReport.model_validate_json(
        (path / "report.json").read_text(encoding="utf-8")
    )


def test_new_population_passes_only_static_role_specific_gates(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)

    assert report.task_count == 24
    assert report.target_mechanism_task_counts == {
        "context_conditioned_action": 6,
        "semantic_reconciliation": 6,
        "failure_recovery": 6,
        "state_dependent_stopping": 6,
    }
    assert report.intended_capability_task_count == 12
    assert report.intended_vtdo_candidate_task_count == 12
    assert report.tool_closure_pass_count == 24
    assert report.package_binding_pass_count == 24
    assert report.primary_public_witness_pass_count == 24
    assert report.mechanism_necessity_pass_count == 24
    assert report.capability_measurement_eligible_count == 24
    assert report.static_vtdo_candidate_eligible_count == 12
    assert report.static_model_authority_path_count == 36
    assert report.counterfactual_replay_count == 48
    assert report.compiler_generated_witness_count == 48
    assert report.model_generated_path_count == 0
    assert not report.empirical_reachability_evaluated
    assert report.status == "passed"
    assert report.next_permitted_stage == ("capability_development_and_state_reachability_pilot")
    assert report.capability_development_authorized
    assert report.state_reachability_pilot_authorized
    assert not report.fresh_confirmation_authorized
    assert not report.no_c_vtdo_authorized
    assert not report.student_training_authorized
    assert not report.exact_target_authorized
    assert not report.gp_c_authorized
    assert report.production_contribution == 0
    assert report.model_api_calls == report.gpu_jobs == 0
    expected_implementation_paths = {
        "src/trusted_synthesis/core/trajectory/executable_task.py",
        "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
        (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_executable_task_rematerialization.py"
        ),
    }
    assert {item.relative_path for item in report.implementation_source_files} == (
        expected_implementation_paths
    )
    for item in report.implementation_source_files:
        observed = hashlib.sha256((PACKAGE_ROOT / item.relative_path).read_bytes()).hexdigest()
        assert item.sha256 == observed


def test_real_definition_pair_capacity_is_fresh_and_sufficient(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    audit = json.loads((first / "definition_pair_capacity_audit.json").read_text(encoding="utf-8"))

    assert audit["source_evidence_count"] == 151_114
    assert audit["excluded_evidence_count"] == 26_290
    assert audit["eligible_definition_pair_count"] == 38
    assert audit["eligible_reconciliation_task_capacity"] == 19
    assert audit["selected_definition_pair_count"] == 12
    assert audit["selected_reconciliation_task_count"] == 6
    assert len(audit["selected_evidence_ids"]) == 24
    assert len(set(audit["selected_evidence_ids"])) == 24
    assert audit["status"] == "passed"


def test_tool_closure_is_enforced_before_task_identity(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    record = _report(first).task_records[0]
    closure = record.task_package.tool_closure
    payload = closure.model_dump(mode="python")
    payload["allowed_tool_ids"] = tuple(
        item for item in closure.allowed_tool_ids if item != closure.required_tool_ids[0]
    )

    with pytest.raises(ValidationError, match="not a subset of Allowed Tools"):
        ToolClosureContract.model_validate(payload)


def test_package_binds_every_contract_to_one_semantic_source(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)

    for record in report.task_records:
        package = record.task_package
        source_id = package.semantic_source.semantic_source_id
        assert package.tool_closure.semantic_source_id == source_id
        assert package.answer_projection.task_id == source_id
        assert package.evidence_support_lattice.semantic_source_id == source_id
        assert package.citation_contract.semantic_source_id == source_id
        assert package.public_runtime_contract.semantic_source_id == source_id
        assert package.mechanism_contract.semantic_source_id == source_id
        assert package.verifier_binding.semantic_source_id == source_id
        assert package.task.task_id == package.package_id
        public = package.task.public.metadata["executable_support_bindings"]
        oracle = package.task.oracle.selection_contract["executable_support_bindings"]
        assert "evidence_support_lattice_id" not in public
        assert "mechanism_contract_id" not in public
        assert oracle["evidence_support_lattice_id"] == (
            package.evidence_support_lattice.lattice_id
        )
        assert oracle["mechanism_contract_id"] == package.mechanism_contract.contract_id
        assert oracle["verifier_binding_id"] == package.verifier_binding.binding_id

    payload = report.task_records[0].task_package.model_dump(mode="python")
    payload["verifier_binding"]["mechanism_contract_id"] = "foreign-mechanism"
    binding_values = {
        key: value for key, value in payload["verifier_binding"].items() if key != "binding_id"
    }
    provisional = ExecutableVerifierBinding.model_construct(binding_id="pending", **binding_values)
    payload["verifier_binding"]["binding_id"] = executable_verifier_binding_id(provisional)
    with pytest.raises(ValidationError, match="does not bind the packaged contracts"):
        ExecutableTaskPackage.model_validate(payload)


def test_reconciliation_calculator_consumes_normalization_references(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    report = _report(first)
    reconciliation_environments = {
        item.environment_manifest_id
        for item in report.task_records
        if item.mechanism_id == "semantic_reconciliation"
    }
    observations = [
        item
        for item in _rows(first / "public_witness_observations.json")
        if item["environment_manifest_id"] in reconciliation_environments
    ]
    normalized_refs: dict[str, set[str]] = defaultdict(set)
    consumed_refs: dict[str, set[str]] = defaultdict(set)
    for item in observations:
        environment_id = item["environment_manifest_id"]
        if item["call"]["tool_id"] == "normalize_metric_unit_period":
            normalized_refs[environment_id].add(item["result"]["normalized_operation_ref"])
    for item in observations:
        environment_id = item["environment_manifest_id"]
        if item["call"]["tool_id"] == "calculator":
            for operand in item["call"]["arguments"]["operands"]:
                operation_ref = operand.get("operation_ref")
                if operation_ref in normalized_refs[environment_id]:
                    assert "evidence_id" not in operand
                    assert operand["selector"] == "normalized_inputs.target"
                    consumed_refs[environment_id].add(operation_ref)

    assert set(normalized_refs) == reconciliation_environments
    assert all(len(values) == 2 for values in normalized_refs.values())
    assert consumed_refs == normalized_refs


def test_target_matched_counterfactual_replays_fail_closed(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    rows = _rows(first / "mechanism_counterfactual_replays.json")
    records = {
        item.task_package.package_id: item.mechanism_id for item in _report(first).task_records
    }
    expected_mutations = {
        "context_conditioned_action": {"replace", "bypass"},
        "semantic_reconciliation": {"delete", "bypass"},
        "failure_recovery": {"delete", "replace"},
        "state_dependent_stopping": {"delete", "bypass"},
    }
    observed: dict[str, set[str]] = defaultdict(set)

    assert len(rows) == 48
    for payload in rows:
        replay = MechanismCounterfactualReplayRecord.model_validate(payload)
        mechanism = records[replay.task_package_id]
        observed[mechanism].add(replay.mutation_kind)
        assert all(replay.baseline_checks.values())
        assert not all(replay.mutated_checks.values())
        assert not replay.mutated_checks["mechanism_complete"]
        assert replay.mutation_target == replay.mechanism_contract_id
        assert replay.target_mechanism_absent
        assert not replay.full_validity_passed
    assert observed == expected_mutations
    assert Counter(item["task_package_id"] for item in rows) == Counter(
        {item: 2 for item in records}
    )

    retained = dict(rows[0])
    retained["mutated_checks"] = dict(retained["baseline_checks"])
    with pytest.raises(ValidationError, match="did not break full validity"):
        MechanismCounterfactualReplayRecord.model_validate(retained)

    foreign = dict(rows[0])
    foreign["mutation_target"] = "mechanism_causal_contract:foreign"
    with pytest.raises(ValidationError, match="targets another mechanism"):
        MechanismCounterfactualReplayRecord.model_validate(foreign)


def test_role_specific_catalogs_do_not_claim_empirical_reachability(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    catalogs = _rows(first / "static_model_authority_path_catalogs.json")
    capability = [item for item in catalogs if item["intended_use"] == "capability_measurement"]
    vtdo = [item for item in catalogs if item["intended_use"] == "vtdo_multistate_candidate"]

    assert len(capability) == len(vtdo) == 12
    assert all(item["status"] == "not_required" and not item["paths"] for item in capability)
    for item in vtdo:
        paths = item["paths"]
        assert item["status"] == "passed"
        assert not item["empirical_reachability_evaluated"]
        assert len(paths) == 3
        assert len({path["model_owned_decision_signature"] for path in paths}) == 3
        assert len({path["behavior_signature"] for path in paths}) == 3
        assert len({path["quotient_state_id"] for path in paths}) == 3
        assert len({path["scaffold_surface_signature"] for path in paths}) == 1
        assert all(path["decision_authority"] == "model" for path in paths)
        assert all(path["materialization_origin"] == "compiler" for path in paths)
        assert all(not path["model_generated"] for path in paths)
        assert all(path["empirical_reachability"] == "unmeasured" for path in paths)


def test_citation_uses_lattice_membership_not_exact_gold(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    lattice = _report(first).task_records[0].task_package.evidence_support_lattice
    sufficient = lattice.sufficient_support_sets[0]

    assert not lattice.exact_equality_required
    assert not lattice.unique_support_proven
    match = matching_sufficient_support_set(
        lattice,
        (*sufficient.evidence_ids, "evidence:additional-public-support"),
    )
    assert match is not None
    assert match.support_set_id == sufficient.support_set_id


def test_report_rejects_an_incomplete_implementation_manifest(
    built_population: tuple[Path, Path],
) -> None:
    first, _ = built_population
    payload = _report(first).model_dump(mode="python")
    payload["implementation_source_files"] = payload["implementation_source_files"][:-1]

    with pytest.raises(
        ValidationError,
        match="implementation_source_files|implementation source manifest is incomplete",
    ):
        V26ExecutableTaskRematerializationReport.model_validate(payload)


def test_all_immutable_outputs_replay_byte_identically(
    built_population: tuple[Path, Path],
) -> None:
    first, second = built_population
    for name in (*DETAIL_FILES, "report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
