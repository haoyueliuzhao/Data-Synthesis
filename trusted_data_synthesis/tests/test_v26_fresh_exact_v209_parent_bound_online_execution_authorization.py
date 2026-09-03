# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/c83d4c4d-b212-400e-bdab-8d03ac0ecc4f/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V223_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.223 external review is unavailable")
    return path


def _load(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_bytes())


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
    if formal.is_dir():
        source = _load(formal, "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        source_identity = ("1" * 40, "2" * 40)
    output = tmp_path_factory.mktemp("v26-223") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_decision_and_v222_freeze(built: Path) -> None:
    external = models.ExternalOnlineAuthorizationDecision.model_validate(
        _load(built, "external_online_authorization_decision.json")
    )
    freeze = models.V222IndependentAuditFreeze.model_validate(_load(built, "v222_freeze.json"))
    assert external.review_sha256 == subject.EXTERNAL_REVIEW_SHA256
    assert external.review_byte_count == 16_856
    assert external.operator_directive == subject.OPERATOR_DIRECTIVE
    assert external.operator_directive_byte_count == 24
    assert (
        external.operator_directive_sha256
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert external.audit_result == "PASSED_AS_SCOPED"
    assert external.blocking_defect == "NONE_FOUND"
    assert external.mandatory_revision == "NONE"
    assert external.only_authorized_stage == models.CONSUMED_STAGE
    assert external.v220_authorization_forbidden_as_future_authority
    assert (freeze.v222_formal_file_count, freeze.v222_formal_total_byte_count) == (
        16,
        74_784,
    )
    assert (
        freeze.v222_manifest_member_count,
        freeze.v222_manifest_member_byte_count,
    ) == (15, 72_169)
    assert (freeze.v222_gate_passed_count, freeze.v222_gate_failed_count) == (6, 0)
    assert freeze.v222_new_online_authorizations == freeze.v222_provider_calls == 0


def test_complete_v221_condition_and_composition_are_reconstructed(built: Path) -> None:
    parents = models.V221RepairedParentBinding.model_validate(
        _load(built, "v221_repaired_parent_binding.json")
    )
    assert parents.exact_v209_artifact_manifest_id == models.V209_MANIFEST_ID
    assert parents.exact_v209_artifact_root == models.V209_ARTIFACT_ROOT
    assert parents.condition_actual_byte_match and parents.composition_actual_byte_match
    assert parents.condition_field_count == parents.condition_field_match_count > 30
    assert parents.composition_field_count == parents.composition_field_match_count > 10
    assert (parents.exact_package_count, parents.exact_job_count) == (32, 192)
    assert parents.exact_coordinate_count == 792
    assert len(parents.exact_package_ids) == 32
    assert len(parents.exact_job_ids) == 192
    assert parents.exact_package_set_sha256 == models.canonical_sha256(parents.exact_package_ids)
    assert parents.exact_job_set_sha256 == models.canonical_sha256(parents.exact_job_ids)
    assert parents.exact_parent_count == len(parents.exact_parent_ids) >= 19
    assert not parents.v220_authorization_consumed
    assert not parents.v220_authorization_reusable


def test_composition_and_fresh_authorization_bind_all_exact_sets(built: Path) -> None:
    composition = models.OnlineExecutionCompositionContract.model_validate(
        _load(built, "online_execution_composition_contract.json")
    )
    authorization = models.ExactOnlineExecutionAuthorization.model_validate(
        _load(built, "exact_online_execution_authorization.json")
    )
    assert composition.event_sequence == models.EVENT_SEQUENCE
    assert len(composition.main_observation_terminal_kinds) == 8
    assert composition.source_bound_failure_terminal_kinds == (
        "instrument_failure",
        "privacy_rejection",
    )
    assert composition.v220_authorization_forbidden
    assert authorization.authorized_stage == models.NEXT_STAGE
    assert authorization.authorization_issued
    assert not authorization.authorization_consumed
    assert authorization.same_stage_consumption_forbidden
    assert not authorization.v220_authorization_accepted
    assert authorization.exact_package_count == 32
    assert authorization.exact_job_count == 192
    assert authorization.exact_registered_coordinate_count == 792
    assert authorization.provider_execution_authorized_in_successor
    assert not authorization.provider_execution_during_authorization
    assert authorization.postrun_independent_audit_required


def test_precredential_admission_rejects_v220_and_parent_changes(built: Path) -> None:
    audit = models.PrecredentialAdmissionAudit.model_validate(
        _load(built, "precredential_admission_audit.json")
    )
    by_name = {item.control_name: item for item in audit.controls}
    assert audit.legal_control_count == 1
    assert audit.invalid_control_count >= 32
    assert by_name["exact_nonconsuming_probe"].admitted
    assert by_name["v220_authorization"].rejected
    assert by_name["modified_authorization_bytes"].rejected
    assert by_name["wrong_v222_freeze"].rejected
    assert by_name["wrong_v221_parent"].rejected
    assert by_name["wrong_v209_artifact_root"].rejected
    assert by_name["wrong_package_set"].rejected
    assert by_name["wrong_job_set"].rejected
    assert by_name["caller_terminal"].rejected
    assert audit.invalid_post_guard_probe_count == 0
    assert not audit.authorization_consumed_by_probe
    assert audit.run_start_receipts == audit.credential_lookups == audit.provider_calls == 0


def test_fully_rehashed_parent_attacks_reject(built: Path) -> None:
    audit = models.ParentAttackAudit.model_validate(_load(built, "parent_attack_audit.json"))
    assert audit.attack_count == 15
    assert audit.fully_rehashed_object_count == 15
    assert audit.rejected_attack_count == 15
    assert audit.accepted_attack_count == 0
    assert all(item.rejected_by_exact_guard for item in audit.attacks)
    assert all(item.mutated_authorization_id for item in audit.attacks)
    assert audit.post_guard_probe_count == audit.provider_calls == 0


def test_gate_decision_transition_and_scope(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.OnlineAuthorizationDecision.model_validate(_load(built, "decision.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load(built, "prospective_transition.json")
    )
    assert (gate.passed_count, gate.failed_count) == (8, 0)
    assert gate.all_gates_passed and gate.authorization_issued
    assert not gate.authorization_consumed
    assert decision.decision == models.DECISION
    assert decision.online_authorization_issued
    assert not decision.online_authorization_consumed
    assert not decision.v220_authorization_consumed
    assert transition.status == "AUTHORIZED_NOT_CONSUMED"
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.exact_fresh_authorization_required
    assert transition.authorization_patch_or_substitution_forbidden
    assert transition.v220_authorization_forbidden
    assert transition.provider_execution_authorized_only_in_successor
    assert not transition.provider_execution_performed_here
    assert scope.fresh_online_authorizations_issued == 1
    assert scope.fresh_online_authorizations_consumed == 0
    assert not scope.v220_authorization_consumed
    assert scope.manifest_job_executions == 0
    assert scope.provider_calls == scope.provider_client_constructions == 0
    assert scope.credential_lookups == scope.empirical_rows == scope.empirical_estimates == 0


def test_report_and_manifest_are_closed(built: Path) -> None:
    report = models.Report.model_validate(_load(built, "report.json"))
    manifest = models.ArtifactManifest.model_validate(_load(built, "artifact_manifest.json"))
    assert report.decision == models.DECISION
    assert report.fresh_online_authorizations == 1
    assert report.authorization_consumptions == 0
    assert report.manifest_job_executions == report.provider_calls == 0
    assert manifest.file_count == len(_files(built)) - 1
    assert {item.relative_path for item in manifest.members} == set(_files(built)) - {
        "artifact_manifest.json"
    }


def test_complete_directory_rebuild_is_byte_exact(built: Path, tmp_path: Path) -> None:
    source = _load(built, "source_identity.json")
    rebuilt = tmp_path / "rebuilt"
    subject.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=(str(source["source_commit"]), str(source["source_tree"])),
    )
    assert _files(rebuilt) == _files(built)
