# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_registry_complement_bound_online_execution_authorization as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_registry_complement_bound_online_execution_authorization_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/31685ec9-8f59-4c24-a76b-ce8dc3bd4814/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V220_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.220 external review is unavailable")
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
    output = tmp_path_factory.mktemp("v26-220") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_decision_and_v219_freeze(built: Path) -> None:
    external = models.ExternalOnlineAuthorizationDecision.model_validate(
        _load(built, "external_online_authorization_decision.json")
    )
    freeze = models.V219IndependentAuditFreeze.model_validate(_load(built, "v219_freeze.json"))
    assert external.review_sha256 == subject.EXTERNAL_REVIEW_SHA256
    assert external.review_byte_count == 13_007
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
    assert not external.online_execution_during_decision_authorized
    assert (freeze.v219_formal_file_count, freeze.v219_formal_total_byte_count) == (
        17,
        46_670,
    )
    assert (
        freeze.v219_manifest_member_count,
        freeze.v219_manifest_member_byte_count,
    ) == (16, 43_862)
    assert freeze.v219_all_seven_gates_passed
    assert freeze.v219_mandatory_revision == "NONE"
    assert not freeze.v219_current_v211_authorization_consumed


def test_complete_v218_repaired_parent_set_is_bound(built: Path) -> None:
    binding = models.V218RepairedParentSetBinding.model_validate(
        _load(built, "v218_repaired_parent_set_binding.json")
    )
    assert binding.v218_source_commit == "6171fcc27a4a88693cb9daa1485b0d658b11a5a1"
    assert binding.v218_source_tree == "1de85c4ee2f69a360bc7b7c13704186042648064"
    assert binding.exact_v195_registry_id == models.REGISTRY_ID
    assert binding.exact_parent_count == len(binding.exact_parent_ids) >= 19
    assert binding.exact_parent_set_sha256 == models.canonical_sha256(binding.exact_parent_ids)
    assert (binding.registry_reachable_count, binding.admitted_terminal_count) == (16, 1)
    assert binding.forbidden_terminal_count == 15
    assert binding.exact_partition_closed
    assert "provider_failure_no_payload" in binding.forbidden_terminal_kinds
    assert "resource_budget_exhausted" in binding.forbidden_terminal_kinds
    assert "provider_no_payload_failure" not in binding.forbidden_terminal_kinds
    assert "resource_failure" not in binding.forbidden_terminal_kinds


def test_exact_v209_condition_is_rederived_without_old_authority(built: Path) -> None:
    condition = models.ExactExecutionConditionBinding.model_validate(
        _load(built, "exact_192_job_condition_binding.json")
    )
    assert (condition.exact_package_count, condition.exact_replica_count) == (32, 6)
    assert condition.exact_job_count == len(condition.exact_job_ids) == 192
    assert condition.exact_registered_coordinate_count == 792
    assert (
        condition.first_action_count,
        condition.subsequent_action_count,
        condition.correction_side_branch_count,
        condition.final_count,
    ) == (192, 288, 120, 192)
    assert (
        condition.maximum_prompt_utf8_bytes,
        condition.maximum_primary_requests,
        condition.maximum_provider_calls,
        condition.maximum_transport_invocations,
        condition.maximum_rollout_tokens,
    ) == (60_000, 21, 23, 24, 1_120_000)
    assert condition.old_v211_authorization_id == models.OLD_V211_AUTHORIZATION_ID
    assert not condition.old_v211_authorization_is_authority
    assert condition.source_condition_change_count == condition.provider_calls == 0


def test_source_bound_composition_and_fresh_authorization(built: Path) -> None:
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
    assert composition.caller_terminal_forbidden
    assert composition.old_v211_authorization_forbidden
    assert composition.unbound_terminal_source_fails_closed
    assert authorization.authorized_stage == models.NEXT_STAGE
    assert authorization.authorization_issued
    assert not authorization.authorization_consumed
    assert authorization.provider_execution_authorized_in_successor
    assert not authorization.provider_execution_during_authorization
    assert not authorization.old_v211_authorization_accepted
    assert not authorization.replacement_run_authorized
    assert authorization.postrun_independent_audit_required


def test_precredential_admission_rejects_old_and_modified_authority(built: Path) -> None:
    audit = models.PrecredentialAdmissionAudit.model_validate(
        _load(built, "precredential_admission_audit.json")
    )
    by_name = {item.control_name: item for item in audit.controls}
    assert audit.legal_control_count == 1
    assert audit.invalid_control_count >= 22
    assert by_name["exact_nonconsuming_probe"].admitted
    assert by_name["old_v211_authorization"].rejected
    assert by_name["modified_authorization_bytes"].rejected
    assert by_name["wrong_v218_parent_set"].rejected
    assert by_name["wrong_job_set"].rejected
    assert by_name["caller_terminal"].rejected
    assert audit.invalid_post_guard_probe_count == 0
    assert not audit.authorization_consumed_by_probe
    assert audit.run_start_receipts == audit.credential_lookups == audit.provider_calls == 0


def test_fully_rehashed_parent_attacks_reject(built: Path) -> None:
    audit = models.ParentAttackAudit.model_validate(_load(built, "parent_attack_audit.json"))
    assert audit.attack_count == 12
    assert audit.fully_rehashed_object_count == 24
    assert audit.rejected_attack_count == 12
    assert audit.accepted_attack_count == 0
    assert all(item.rejected_by_exact_guard for item in audit.attacks)
    assert all(item.mutated_authorization_id for item in audit.attacks)
    assert all(item.mutated_composition_id for item in audit.attacks)
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
    assert not decision.old_v211_authorization_consumed
    assert transition.status == "AUTHORIZED_NOT_CONSUMED"
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.exact_fresh_authorization_required
    assert transition.old_v211_authorization_forbidden
    assert transition.provider_execution_authorized_only_in_successor
    assert not transition.provider_execution_performed_here
    assert scope.fresh_online_authorizations_issued == 1
    assert scope.fresh_online_authorizations_consumed == 0
    assert not scope.old_v211_authorization_consumed
    assert scope.manifest_job_executions == 0
    assert scope.provider_calls == scope.provider_client_constructions == 0
    assert scope.credential_lookups == scope.empirical_rows == scope.empirical_estimates == 0


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
