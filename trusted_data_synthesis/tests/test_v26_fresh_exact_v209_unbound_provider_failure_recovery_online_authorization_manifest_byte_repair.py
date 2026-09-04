# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair as stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models as v231_models,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/c8b1a8ac-fe68-4811-9eae-38e1f2f9fb7f/pasted-text.txt"
)


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v232") / models.RUN_ID
    stage.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=("1" * 40, "1" * 40),
    )
    return output


def test_external_narrow_failure_and_v231_candidate_freeze(built: Path) -> None:
    external = models.ExternalRepairDecision.model_validate(
        _load(built / "external_manifest_byte_repair_decision.json")
    )
    freeze = models.V231CandidateFreeze.model_validate(_load(built / "v231_candidate_freeze.json"))
    assert external.review_byte_count == 10_544
    assert external.audit_decision == "FAIL_NARROWLY_AT_G0"
    assert external.first_failed_gate == "G0_EXACT_V26_230_FREEZE"
    assert external.recovery_population_authority == "RETAINED"
    assert freeze.authorization_id == models.V231_AUTHORIZATION_ID
    assert freeze.authorization_consumable is False
    assert freeze.formal_bytes_modified is False


def test_all_predecessor_manifest_actual_bytes_are_bound(built: Path) -> None:
    expected = {
        "v229_manifest_byte_authority.json": (
            "v26.229",
            16_952,
            models.V229_MANIFEST_SHA256,
            117,
            1_105_367,
        ),
        "v230_manifest_byte_authority.json": (
            "v26.230",
            3_150,
            models.V230_MANIFEST_SHA256,
            20,
            308_132,
        ),
        "v231_manifest_byte_authority.json": (
            "v26.231",
            2_889,
            models.V231_MANIFEST_SHA256,
            18,
            103_759,
        ),
    }
    for name, (version, byte_count, digest, file_count, total_bytes) in expected.items():
        authority = models.ManifestByteAuthority.model_validate(_load(built / name))
        assert authority.predecessor_version == version
        assert authority.expected_byte_count == authority.actual_byte_count == byte_count
        assert authority.expected_sha256 == authority.actual_sha256 == digest
        assert authority.formal_file_count == file_count
        assert authority.formal_total_bytes == total_bytes
        assert authority.manifest_actual_bytes_match
        assert authority.all_member_actual_bytes_match


def test_v230_freeze_and_recovery_parent_bind_both_manifest_authorities(built: Path) -> None:
    freeze = models.V230Freeze.model_validate(_load(built / "v230_freeze.json"))
    parent = models.RecoveryParentBinding.model_validate(
        _load(built / "recovery_parent_binding.json")
    )
    assert freeze.v230_manifest_byte_count == 3_150
    assert freeze.v230_manifest_sha256 == models.V230_MANIFEST_SHA256
    assert freeze.old_v231_freeze_retained_projection_match
    assert parent.v229_manifest_byte_count == 16_952
    assert parent.v229_manifest_sha256 == models.V229_MANIFEST_SHA256
    assert parent.v230_manifest_byte_count == 3_150
    assert parent.v230_manifest_sha256 == models.V230_MANIFEST_SHA256
    assert parent.retained_v231_parent_binding_id == models.V231_PARENT_BINDING_ID
    assert parent.retained_v231_parent_actual_byte_match
    assert parent.recovery_semantic_projection_unchanged


def test_recovery_population_semantics_and_budget_are_unchanged(built: Path) -> None:
    parent = models.RecoveryParentBinding.model_validate(
        _load(built / "recovery_parent_binding.json")
    )
    contract = models.RecoveryExecutionContract.model_validate(
        _load(built / "recovery_execution_contract.json")
    )
    composition = models.RecoveryComposition.model_validate(
        _load(built / "online_execution_composition.json")
    )
    assert len(parent.recovery_job_ids) == 33
    assert sum(row.successful_prefix_call_count for row in parent.budget_rows) == 55
    assert sum(row.successful_prefix_usage_tokens for row in parent.budget_rows) == 665_598
    assert [row.failed_phase for row in parent.budget_rows].count("first_action") == 3
    assert [row.failed_phase for row in parent.budget_rows].count("subsequent_action") == 25
    assert [row.failed_phase for row in parent.budget_rows].count("final") == 5
    assert contract.request_max_tokens == 16_384
    assert contract.maximum_online_provider_calls == 704
    assert contract.maximum_online_rollout_tokens == 36_294_402
    assert contract.retained_v231_contract_id == models.V231_EXECUTION_CONTRACT_ID
    assert contract.retained_contract_projection_match
    assert composition.event_sequence == v231_models.EVENT_SEQUENCE
    assert composition.retained_event_sequence_match


def test_fresh_authorization_replaces_but_does_not_consume_v231(built: Path) -> None:
    authorization = models.ExactOnlineAuthorization.model_validate(
        _load(built / "exact_online_execution_authorization.json")
    )
    admission = models.AdmissionAudit.model_validate(
        _load(built / "precredential_admission_audit.json")
    )
    assert authorization.authorization_id != models.V231_AUTHORIZATION_ID
    assert authorization.superseded_v231_authorization_id == models.V231_AUTHORIZATION_ID
    assert authorization.superseded_v231_authorization_consumable is False
    assert authorization.exact_predecessor_manifest_actual_bytes_bound
    assert authorization.maximum_authorization_consumptions == 1
    assert authorization.authorization_consumed is False
    assert admission.legal_control_count == 1
    assert admission.invalid_control_count == 19
    assert admission.authorization_consumptions == 0
    old = next(
        row for row in admission.controls if row.control_name == "superseded_v231_authorization"
    )
    assert old.rejected and old.precredential_rejection


def test_two_same_length_semantic_equivalent_manifest_attacks_reject(built: Path) -> None:
    audit = models.ManifestAttackAudit.model_validate(
        _load(built / "manifest_byte_negative_control_audit.json")
    )
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (2, 2, 0)
    assert tuple(row.attack_name for row in audit.attacks) == (
        "v26_230_manifest_same_length_key_reordering",
        "v26_229_manifest_same_length_key_reordering",
    )
    assert all(row.parsed_json_equal for row in audit.attacks)
    assert all(row.original_byte_count == row.candidate_byte_count for row in audit.attacks)
    assert all(row.original_sha256 != row.candidate_sha256 for row in audit.attacks)
    assert all(row.rejection_stage == "freeze.manifest_bytes" for row in audit.attacks)
    assert audit.attack_output_writes == audit.provider_calls == 0


def test_parent_attacks_scope_gate_decision_and_transition(built: Path) -> None:
    attacks = models.ParentAttackAudit.model_validate(_load(built / "parent_attack_audit.json"))
    scope = models.ScopeAudit.model_validate(_load(built / "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built / "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built / "decision.json"))
    transition = models.Transition.model_validate(_load(built / "transition.json"))
    assert attacks.attack_count == attacks.rejected_attack_count == 10
    assert attacks.accepted_attack_count == 0
    assert scope.online_authorizations_issued == 1
    assert scope.online_authorizations_consumed == 0
    assert scope.superseded_v231_authorizations_consumed == 0
    assert scope.provider_calls == scope.credential_lookups == scope.recovery_executions == 0
    assert gate.passed_count == 8 and gate.failed_count == 0
    assert decision.decision == models.DECISION_VALUE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.next_stage_authorized
    assert not transition.authorization_consumed
    assert not transition.superseded_v231_authorization_reusable


def test_manifest_source_and_complete_second_build(built: Path, tmp_path: Path) -> None:
    manifest = models.ArtifactManifest.model_validate(_load(built / "artifact_manifest.json"))
    source = models.SourceIdentity.model_validate(_load(built / "source_identity.json"))
    assert manifest.file_count == 22
    assert len(source.members) == 4
    assert all(row.committed_current_bytes_match for row in source.members)
    assert {path.name for path in built.iterdir()} == {
        "artifact_manifest.json",
        *(row.relative_path for row in manifest.members),
    }
    second = tmp_path / models.RUN_ID
    stage.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=second,
        external_review_path=REVIEW,
        source_identity=("1" * 40, "1" * 40),
    )
    paths = sorted(path.relative_to(built) for path in built.rglob("*") if path.is_file())
    assert paths == sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert all((built / path).read_bytes() == (second / path).read_bytes() for path in paths)


def test_external_review_tamper_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "review.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"x")
    with pytest.raises(stage.V232Error, match="external.review"):
        stage._external_decision(changed)
