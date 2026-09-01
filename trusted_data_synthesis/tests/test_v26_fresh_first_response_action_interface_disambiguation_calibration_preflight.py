# ruff: noqa: E501
from __future__ import annotations

import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight as experiment,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
FORMAL_ROOT = PACKAGE_ROOT / experiment.OUTPUT_DIR
AUDIT_PATH = FORMAL_ROOT / "external_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    output = tmp_path_factory.mktemp("v26-203") / "formal"
    report = experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=output,
        external_audit_path=AUDIT_PATH,
    )
    return output, report


def test_external_authorization_and_v202_freeze(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load(output / "external_authorization.json")
    )
    freeze = models.V202Freeze.model_validate(_load(output / "v26_202_freeze.json"))
    assert authorization.audit_sha256 == experiment.EXTERNAL_AUDIT_SHA256
    assert authorization.audit_byte_count == experiment.EXTERNAL_AUDIT_BYTES
    assert authorization.provider_calls_authorized is False
    assert freeze.v202_decision_id == experiment.V202_DECISION_ID
    assert freeze.q_first_fraction == freeze.q_bounded_correction_fraction == "0/192"
    assert freeze.post_action_abi_denominator == 0
    assert report["provider_calls"] == report["credential_lookups"] == 0


def test_exact_parser_compiled_contract_and_two_profiles(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    contract = models.ExactActionInterfaceContract.model_validate(
        _load(output / "exact_action_interface_contract.json")
    )
    profiles = tuple(
        models.InterfaceProfile.model_validate(item)
        for item in _load(output / "interface_profiles.json")["profiles"]
    )
    assert contract.field_order == ("state_id", "action_id", "decision_kind", "protocol")
    assert contract.required_fields == contract.allowed_fields == contract.field_order
    assert contract.additional_properties_allowed is False
    assert contract.parser_unchanged is True
    by_arm = {item.arm: item for item in profiles}
    assert by_arm["C"].message_roles == ("user",)
    assert by_arm["C"].source_prompt_bytes_exact is True
    assert by_arm["C"].old_response_abi_visible is True
    assert by_arm["R"].message_roles == ("system", "user")
    assert by_arm["R"].old_response_abi_visible is False
    assert by_arm["R"].action_id_inside_authoritative_contract is True
    assert by_arm["R"].grammar_id_host_side_only is True


def test_pre_response_stratified_population_is_exact(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    population = models.StratifiedCalibrationPopulation.model_validate(
        _load(output / "stratified_calibration_population.json")
    )
    grouped: dict[str, list[models.SourceCell]] = defaultdict(list)
    for cell in population.cells:
        grouped[cell.stratum_id].append(cell)
    assert set(grouped) == {
        "comparison:lower",
        "comparison:higher",
        "scalar_value:lower",
        "scalar_value:higher",
    }
    assert all(len(items) == 3 for items in grouped.values())
    assert all(
        {item.selection_position for item in items} == {"short", "median", "long"}
        for items in grouped.values()
    )
    assert all(item.selection_uses_pre_response_properties_only for item in population.cells)
    assert all(not item.historical_response_shape_used for item in population.cells)
    assert sum(item.new_response_count_read for item in population.cells) == 0
    assert report["source_prompt_census_count"] == 192
    assert report["source_cell_count"] == 12


def test_exact_24_job_pairing_and_model_visible_interface_isolation(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    manifest = models.CalibrationManifest.model_validate(
        _load(output / "calibration_manifest.json")
    )
    population = models.StratifiedCalibrationPopulation.model_validate(
        _load(output / "stratified_calibration_population.json")
    )
    cell_map = {item.source_cell_id: item for item in population.cells}
    requests = {item.job_id: item for item in manifest.requests}
    pairs: dict[str, list[models.CalibrationJob]] = defaultdict(list)
    for job in manifest.jobs:
        pairs[job.source_cell_id].append(job)
    assert Counter(item.arm for item in manifest.jobs) == Counter({"C": 12, "R": 12})
    assert len(pairs) == 12
    assert (
        sum(
            min(rows, key=lambda item: item.execution_order_within_pair).arm == "C"
            for rows in pairs.values()
        )
        == 6
    )
    for cell_id, rows in pairs.items():
        assert {item.arm for item in rows} == {"C", "R"}
        left, right = rows
        assert left.public_task_semantic_sha256 == right.public_task_semantic_sha256
        assert left.current_state_semantic_sha256 == right.current_state_semantic_sha256
        assert left.candidate_set_order_sha256 == right.candidate_set_order_sha256
        assert left.schedule_ids == right.schedule_ids == cell_map[cell_id].schedule_ids
        for job in rows:
            request = requests[job.job_id]
            if job.arm == "C":
                assert len(request.messages) == 1
                assert request.messages[0].content_sha256 == cell_map[cell_id].control_prompt_sha256
            else:
                assert tuple(item.role for item in request.messages) == ("system", "user")
                system = json.loads(request.messages[0].content)
                user = json.loads(request.messages[1].content)
                exact = system["authoritative_response_contract"]
                assert exact["required_fields"] == [
                    "state_id",
                    "action_id",
                    "decision_kind",
                    "protocol",
                ]
                assert exact["field_values"]["action_id"]["one_of"] == list(
                    cell_map[cell_id].candidate_action_ids
                )
                assert "response_abi" not in request.messages[1].content
                assert "grammar_id" not in request.messages[0].content
                assert "grammar_id" not in request.messages[1].content
                assert user["verifier_internal_task_metadata"]["model_response_schema"] is False
    assert manifest.planned_stage_one_calls == 24
    assert manifest.planned_stage_two_calls == 0
    assert manifest.automatic_retries == manifest.recovery_calls == 0
    assert manifest.provider_calls == manifest.empirical_response_count == 0


def test_evidence_chain_and_noncompensatory_online_gates_are_precommitted(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    evidence = models.EvidenceSchemaAudit.model_validate(
        _load(output / "calibration_evidence_schema_audit.json")
    )
    gates = models.OnlineGateContract.model_validate(_load(output / "online_gate_contract.json"))
    assert evidence.scripted_fixture_response_count == 2
    assert evidence.scripted_fixture_observation_count == 2
    assert evidence.exact_parser_fixture_pass_count == 2
    assert evidence.empirical_response_count == evidence.empirical_observation_count == 0
    assert evidence.provider_calls == 0
    assert gates.g3_repair_exact_action_abi_minimum == 9
    assert gates.g4_repair_reference_state_valid_minimum == 8
    assert gates.g5_paired_repair_only_abi_success_minimum == 7
    assert gates.g6_paired_control_only_abi_success_maximum == 1
    assert gates.gate_compensation_allowed is False
    assert gates.online_gate_status == "not_evaluated_preflight_only"


def test_six_control_classes_reject_and_transition_stops_before_online(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    audit = models.PreflightControlAudit.model_validate(
        _load(output / "preflight_control_audit.json")
    )
    decision = models.Decision.model_validate(_load(output / "decision.json"))
    transition = models.Transition.model_validate(_load(output / "prospective_transition.json"))
    assert audit.control_class_count == audit.rejected_control_class_count == 6
    assert audit.accepted_control_class_count == 0
    assert sum(item.case_count for item in audit.controls) == 14
    assert decision.population_preflight_passed is True
    assert decision.online_calibration_executed is False
    assert decision.causal_interface_effect_estimated is False
    assert transition.next_decision == models.NEXT_DECISION
    assert transition.online_execution_authorized is False
    assert transition.provider_calls_authorized is False
    assert transition.maximum_future_provider_calls_after_authorization == 24
    assert transition.full_192_job_condition_authorized is False


def test_empty_directory_rebuild_is_byte_identical(
    built: tuple[Path, dict[str, Any]],
    tmp_path: Path,
) -> None:
    first, _ = built
    second = tmp_path / "rebuild"
    experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=second,
        external_audit_path=AUDIT_PATH,
    )
    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_source_has_no_provider_client_or_execution_path() -> None:
    source = inspect.getsource(experiment)
    assert "StageOneProspectiveThinkingJsonClient" not in source
    assert ".complete_json" not in source
    assert ".invoke(" not in source
    assert "execute_job(" not in source
    assert "DEEPSEEK_API_KEY" not in source
    assert '"provider_calls": 0' in source
    assert "historical response adaptation is forbidden" in source
