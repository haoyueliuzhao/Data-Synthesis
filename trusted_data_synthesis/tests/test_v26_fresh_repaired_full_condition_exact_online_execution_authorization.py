# ruff: noqa: E501, SLF001
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization as authorization,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_exact_online_execution_authorization_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/aef09d24-82c3-469b-ac61-be8d8fab8fbc/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V211_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / authorization.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.211 external review is unavailable")
    return path


def _load(root: Path, name: str) -> dict[str, object]:
    return json.loads((root / name).read_bytes())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26-211") / "formal"
    authorization.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    return output


def test_exact_external_decision_is_zero_provider_authorization_only() -> None:
    decision, review, directive = authorization._external_decision(_review_path())
    assert len(review) == 12_940
    assert directive.decode("utf-8") == authorization.OPERATOR_DIRECTIVE
    assert decision.review_audit_result == "PASSED_AS_SCOPED"
    assert decision.review_mandatory_revision == "NONE"
    assert decision.only_authorized_stage == models.CONSUMED_STAGE
    assert decision.provider_calls_authorized_during_decision == 0
    assert not decision.online_execution_during_decision_authorized


def test_modified_external_decision_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(_review_path().read_bytes() + b"\n")
    with pytest.raises(authorization.V211Error, match="external review bytes differ"):
        authorization._external_decision(changed)


def test_exact_v210_authority_is_frozen(built: Path) -> None:
    freeze = models.V210AuthorityFreeze.model_validate(_load(built, "v210_authority_freeze.json"))
    assert freeze.v210_source_commit == authorization.V210_SOURCE_COMMIT
    assert freeze.v210_source_tree == authorization.V210_SOURCE_TREE
    assert freeze.v210_formal_file_count == 15
    assert freeze.v210_formal_total_byte_count == 1_344_368
    assert freeze.v210_manifest_member_count == 14
    assert freeze.v210_manifest_member_total_byte_count == 1_341_853
    assert freeze.v210_all_gates_passed
    assert freeze.v210_provider_calls == freeze.v210_credential_lookups == 0


def test_exact_v209_execution_condition_is_unchanged(built: Path) -> None:
    condition = models.FrozenExecutionConditionBinding.model_validate(
        _load(built, "frozen_execution_condition_binding.json")
    )
    assert condition.v209_source_commit == authorization.V209_SOURCE_COMMIT
    assert condition.v209_source_tree == authorization.V209_SOURCE_TREE
    assert len(condition.exact_package_ids) == len(set(condition.exact_package_ids)) == 32
    assert len(condition.exact_job_ids) == len(set(condition.exact_job_ids)) == 192
    assert (
        condition.first_action_count,
        condition.subsequent_action_count,
        condition.correction_side_branch_count,
        condition.final_count,
    ) == (192, 288, 120, 192)
    assert condition.exact_registered_coordinate_count == 792
    assert condition.maximum_provider_calls == 23
    assert condition.maximum_rollout_tokens == 1_120_000
    assert condition.task_component_candidate_schedule_change_count == 0
    assert condition.grammar_policy_resource_change_count == 0


def test_composition_and_authorization_freeze_future_execution_only(built: Path) -> None:
    composition = models.OnlineExecutionCompositionContract.model_validate(
        _load(built, "online_execution_composition_contract.json")
    )
    exact = models.ExactOnlineExecutionAuthorization.model_validate(
        _load(built, "exact_online_execution_authorization.json")
    )
    assert composition.event_sequence == models.EXECUTION_SEQUENCE
    assert composition.consume_exactly_once_before_credential_lookup
    assert composition.durable_run_start_receipt_required
    assert composition.raw_before_result_persistence_required
    assert composition.caller_terminal_forbidden
    assert composition.historical_response_input_forbidden
    assert composition.reference_choice_vector_input_forbidden
    assert composition.prebuilt_final_input_forbidden
    assert not composition.failure_reopens_authorization
    assert exact.authorized_stage == models.NEXT_STAGE
    assert exact.maximum_authorization_consumptions == 1
    assert exact.online_execution_authorized
    assert exact.provider_execution_authorized
    assert not exact.authorization_reuse_authorized
    assert not exact.replacement_run_authorized
    assert not exact.failed_job_rerun_authorized
    assert not exact.recovery_run_authorized
    assert not exact.qa_integration_authorized
    assert exact.provider_calls_during_authorization == 0


def test_precredential_guard_rejects_all_invalid_requests_before_probes(built: Path) -> None:
    audit = models.PrecredentialAdmissionAudit.model_validate(
        _load(built, "precredential_admission_audit.json")
    )
    assert audit.invalid_control_count == 28
    assert len(audit.controls) == 29
    legal = tuple(item for item in audit.controls if item.admitted)
    assert len(legal) == 1
    assert legal[0].control_name == "exact_online_authorization"
    assert (
        legal[0].credential_probe_count,
        legal[0].transport_factory_count,
        legal[0].raw_writer_factory_count,
        legal[0].result_writer_factory_count,
        legal[0].outcome_writer_factory_count,
        legal[0].checkpoint_writer_factory_count,
    ) == (1, 1, 1, 1, 1, 1)
    for control in audit.controls:
        if control.rejected:
            assert control.rejection_reason_sha256 is not None
            assert control.credential_probe_count == 0
            assert control.transport_factory_count == 0
            assert control.raw_writer_factory_count == 0
            assert control.result_writer_factory_count == 0
            assert control.outcome_writer_factory_count == 0
            assert control.checkpoint_writer_factory_count == 0
    assert not audit.authorization_consumed_by_diagnostic_probe
    assert audit.credential_lookups == audit.provider_calls == 0


def test_destructive_scope_gate_decision_and_transition_are_closed(built: Path) -> None:
    destructive = models.DestructiveAudit.model_validate(
        _load(built, "authorization_destructive_audit.json")
    )
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    static = models.StaticAudit.model_validate(_load(built, "static_audit.json"))
    decision = models.OnlineAuthorizationDecision.model_validate(
        _load(built, "online_authorization_decision.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load(built, "prospective_transition.json")
    )
    assert destructive.attack_count == destructive.fully_rehashed_attack_count == 20
    assert destructive.rejected_attack_count == 20
    assert destructive.accepted_attack_count == destructive.post_guard_probe_count == 0
    assert scope.authorization_issued
    assert not scope.authorization_consumed
    assert scope.durable_run_start_receipts == scope.manifest_job_executions == 0
    assert scope.provider_calls == scope.credential_lookups == 0
    assert scope.raw_files_written == scope.result_files_written == 0
    assert scope.trace_rows == scope.outcome_rows == scope.checkpoint_rows == 0
    assert static.passed_gate_count == 30
    assert static.failed_gate_count == 0
    assert decision.decision == models.DECISION
    assert not decision.online_authorization_consumed
    assert transition.status == "AUTHORIZED_NOT_CONSUMED"
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.postrun_independent_audit_required


def test_complete_formal_directory_rebuild_is_byte_exact(built: Path, tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    authorization.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    first = {path.name: path.read_bytes() for path in built.iterdir() if path.is_file()}
    second = {path.name: path.read_bytes() for path in rebuilt.iterdir() if path.is_file()}
    assert len(first) == 17
    assert second == first
    artifact = models.ArtifactManifest.model_validate(_load(built, "artifact_manifest.json"))
    assert artifact.file_count == 16
