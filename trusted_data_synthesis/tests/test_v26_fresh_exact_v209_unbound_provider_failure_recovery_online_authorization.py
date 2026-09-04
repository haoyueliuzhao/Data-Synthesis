# ruff: noqa: E501
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization as stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models as models,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/88d38082-66a9-4313-95c2-b1e49f980fbd/pasted-text.txt"
)


def _source_identity() -> tuple[str, str]:
    commit = subprocess.run(
        ("git", "log", "-1", "--format=%H", "--", stage.SOURCE_PATHS[0]),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ("git", "rev-parse", f"{commit}^{{tree}}"),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v231") / models.RUN_ID
    stage.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=_source_identity(),
    )
    return output


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_external_review_and_v230_freeze(built: Path) -> None:
    external = models.ExternalDecision.model_validate(
        _load(built / "external_online_authorization_decision.json")
    )
    freeze = models.V230Freeze.model_validate(_load(built / "v230_freeze.json"))
    assert external.review_byte_count == 12_817
    assert external.next_unclosed_gate == "RECOVERY_ONLINE_AUTHORIZATION"
    assert freeze.actual_byte_matches == 20
    assert freeze.component_audit_ids == tuple(sorted(freeze.component_audit_ids))


def test_exact_recovery_parent_population_and_usage(built: Path) -> None:
    parent = models.RecoveryParentBinding.model_validate(
        _load(built / "recovery_parent_binding.json")
    )
    assert len(parent.recovery_job_ids) == 33
    assert sum(row.successful_prefix_call_count for row in parent.budget_rows) == 55
    assert sum(row.successful_prefix_usage_tokens for row in parent.budget_rows) == 665_598
    assert [row.failed_phase for row in parent.budget_rows].count("first_action") == 3
    assert [row.failed_phase for row in parent.budget_rows].count("subsequent_action") == 25
    assert [row.failed_phase for row in parent.budget_rows].count("final") == 5


def test_recovery_semantics_and_budget_are_explicit(built: Path) -> None:
    contract = models.RecoveryExecutionContract.model_validate(
        _load(built / "recovery_execution_contract.json")
    )
    assert contract.recovery_mode == "continue_from_exact_failed_request_to_fresh_terminal"
    assert contract.request_max_tokens == 16_384
    assert not contract.max_tokens_changed_from_v26_226
    assert contract.historical_successful_prefix_provider_calls == 0
    assert contract.maximum_online_provider_calls == 704
    assert contract.maximum_online_provider_calls > contract.exact_failed_request_online_calls
    assert contract.maximum_online_rollout_tokens == 36_294_402


def test_authorization_is_fresh_unconsumed_and_one_time(built: Path) -> None:
    authorization = models.ExactOnlineAuthorization.model_validate(
        _load(built / "exact_online_execution_authorization.json")
    )
    transition = models.Transition.model_validate(_load(built / "transition.json"))
    assert authorization.maximum_authorization_consumptions == 1
    assert authorization.authorization_issued
    assert not authorization.authorization_consumed
    assert authorization.provider_execution_authorized_in_successor
    assert not authorization.provider_execution_during_authorization
    assert transition.next_stage_authorized
    assert not transition.authorization_consumed


def test_precredential_guard_controls_and_parent_attacks(built: Path) -> None:
    admission = models.AdmissionAudit.model_validate(
        _load(built / "precredential_admission_audit.json")
    )
    attacks = models.ParentAttackAudit.model_validate(_load(built / "parent_attack_audit.json"))
    assert admission.legal_control_count == 1
    assert admission.invalid_control_count == 18
    assert admission.authorization_consumptions == 0
    assert attacks.attack_count == 10
    assert attacks.rejected_attack_count == 10
    assert attacks.accepted_attack_count == 0


def test_scope_and_gate(built: Path) -> None:
    scope = models.ScopeAudit.model_validate(_load(built / "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built / "gate_evaluation.json"))
    report = models.Report.model_validate(_load(built / "report.json"))
    assert scope.online_authorizations_issued == 1
    assert scope.provider_calls == 0
    assert scope.recovery_executions == 0
    assert scope.historical_v26_226_writes == 0
    assert gate.passed_count == 8
    assert gate.failed_count == 0
    assert report.decision == models.DECISION_VALUE


def test_manifest_and_source_identity(built: Path) -> None:
    manifest = models.ArtifactManifest.model_validate(_load(built / "artifact_manifest.json"))
    source = models.SourceIdentity.model_validate(_load(built / "source_identity.json"))
    assert manifest.file_count == 17
    assert len(source.members) == 2
    assert all(row.committed_current_bytes_match for row in source.members)
    assert {path.name for path in built.iterdir()} == {
        "artifact_manifest.json",
        *(row.relative_path for row in manifest.members),
    }


def test_complete_second_build_is_byte_identical(built: Path, tmp_path: Path) -> None:
    second = tmp_path / models.RUN_ID
    stage.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=second,
        external_review_path=REVIEW,
        source_identity=_source_identity(),
    )
    first_paths = sorted(path.relative_to(built) for path in built.rglob("*") if path.is_file())
    second_paths = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_paths == second_paths
    assert all((built / path).read_bytes() == (second / path).read_bytes() for path in first_paths)


def test_external_review_tamper_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "review.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"x")
    with pytest.raises(stage.V231Error, match="external.review"):
        stage._external_decision(changed)
