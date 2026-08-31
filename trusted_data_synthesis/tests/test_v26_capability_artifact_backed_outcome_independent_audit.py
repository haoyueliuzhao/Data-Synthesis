from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_independent_audit_models as models,
)

EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/126e1c9a-9320-40bc-b134-cd0b1e9e146f/pasted-text.txt"
)


@pytest.fixture(scope="module")
def products() -> tuple[
    models.IndependentAuditAuthorization,
    models.FormalArtifactReplayAudit,
    models.SemanticReplayAudit,
    models.ValidityFactorizationAudit,
    models.NegativeControlAudit,
    models.StaticAudit,
    models.IndependentAuditDecision,
    models.ProspectiveTransition,
]:
    package_root = Path(__file__).resolve().parents[1]
    authorization = audit._authorization(
        package_root=package_root,
        external_audit_input=EXTERNAL_AUDIT,
    )
    formal = audit._formal_replay(
        package_root=package_root,
        authorization=authorization,
    )
    semantic = audit._semantic_replay(
        package_root=package_root,
        authorization=authorization,
    )
    factorization = audit._factorization(package_root)
    destructive = audit._destructive(package_root)
    static = audit._static(
        authorization=authorization,
        source_rebuild=models.SourceRebuildAudit.model_construct(audit_id="source-rebuild-fixture"),
        formal_replay=formal,
        semantic_replay=semantic,
        factorization=factorization,
        destructive=destructive,
    )
    decision = audit._decision(
        authorization=authorization,
        source_rebuild=models.SourceRebuildAudit.model_construct(audit_id="source-rebuild-fixture"),
        formal_replay=formal,
        semantic_replay=semantic,
        factorization=factorization,
        destructive=destructive,
        static=static,
    )
    transition = audit._transition(decision)
    return (
        authorization,
        formal,
        semantic,
        factorization,
        destructive,
        static,
        decision,
        transition,
    )


def test_exact_v186_formal_artifacts_replay(
    products: tuple[object, ...],
) -> None:
    authorization = products[0]
    formal = products[1]
    assert isinstance(authorization, models.IndependentAuditAuthorization)
    assert isinstance(formal, models.FormalArtifactReplayAudit)
    assert authorization.audited_source_commit == audit.AUDITED_SOURCE_COMMIT
    assert authorization.audited_source_tree == audit.AUDITED_SOURCE_TREE
    assert authorization.audited_artifact_commit == audit.AUDITED_ARTIFACT_COMMIT
    assert authorization.audited_artifact_tree == audit.AUDITED_ARTIFACT_TREE
    assert formal.directory_file_count == 398
    assert formal.manifest_member_match_count == formal.manifest_member_count == 397
    assert formal.artifact_root == audit.AUDITED_ARTIFACT_ROOT


def test_independent_raw_result_and_evidence_dag_replay(
    products: tuple[object, ...],
) -> None:
    semantic = products[2]
    assert isinstance(semantic, models.SemanticReplayAudit)
    assert semantic.bundle_count == semantic.exact_job_match_count == 192
    assert semantic.raw_payload_count == semantic.result_payload_count == 192
    assert semantic.actual_artifact_byte_match_count == 384
    assert semantic.canonical_artifact_match_count == 384
    assert semantic.payload_identity_match_count == 384
    assert semantic.descriptor_identity_match_count == 384
    assert semantic.trace_identity_match_count == semantic.row_identity_match_count == 192
    assert semantic.parent_chain_match_count == 192
    assert semantic.formal_empirical_rows == semantic.formal_empirical_estimates == 0


def test_mixed_validity_states_remain_distinct(
    products: tuple[object, ...],
) -> None:
    factorization = products[3]
    assert isinstance(factorization, models.ValidityFactorizationAudit)
    assert {
        (item.final_base_valid, item.final_mechanism_qualified) for item in factorization.states
    } == {(True, False), (False, True)}
    assert {item.derived_locus_stages for item in factorization.states} == {
        ("mechanism",),
        ("base_answer",),
    }


def test_all_thirteen_independent_attacks_reject(
    products: tuple[object, ...],
) -> None:
    destructive = products[4]
    assert isinstance(destructive, models.NegativeControlAudit)
    assert destructive.control_count == destructive.rejected_control_count == 13
    assert destructive.accepted_attack_count == 0
    assert {item.family for item in destructive.controls} == {
        "terminal_validity_factorization",
        "diagnostic_empirical_admission",
        "failure_locus_reconstruction",
        "artifact_byte_authenticity",
        "authoritative_parent_revalidation",
    }
    diagnostic = tuple(
        item for item in destructive.controls if item.family == "diagnostic_empirical_admission"
    )
    assert len(diagnostic) == 2
    assert all(
        item.rejection_reason == audit.EXPECTED_DIAGNOSTIC_REJECTION
        and item.exact_reason_match
        and item.fully_rehashed
        for item in diagnostic
    )


def test_passed_audit_does_not_self_authorize_online_execution(
    products: tuple[object, ...],
) -> None:
    static = products[5]
    decision = products[6]
    transition = products[7]
    assert isinstance(static, models.StaticAudit)
    assert isinstance(decision, models.IndependentAuditDecision)
    assert isinstance(transition, models.ProspectiveTransition)
    assert static.failed_gate_count == 0
    assert decision.decision == models.PASSED_DECISION
    assert decision.next_stage == models.NO_FURTHER_EXPERIMENT
    assert not decision.online_execution_authorized
    assert not transition.provider_execution_authorized
    assert not transition.online_development_authorized
    assert not transition.empirical_rows_authorized


def test_report_and_transition_fail_closed() -> None:
    invalid = models.IndependentAuditDecision.model_construct(
        decision_id="invalid",
        authorization_id="a",
        source_rebuild_audit_id="s",
        formal_replay_audit_id="f",
        semantic_replay_audit_id="e",
        factorization_audit_id="v",
        destructive_audit_id="d",
        static_audit_id="g",
        decision=models.PASSED_DECISION,
        next_stage=models.REPAIR_ONLY,
    )
    with pytest.raises(ValidationError):
        models.IndependentAuditDecision.model_validate(
            invalid.model_dump(mode="python", warnings=False)
        )


def test_immutable_writer_does_not_replace_existing_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_immutable_artifact_directory(output, {"report.json": b"{}\n"})
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_source_archive_binding_is_independent_of_temporary_path(tmp_path: Path) -> None:
    first = tmp_path / "first.tar"
    second = tmp_path / "different-name.tar"
    first.write_bytes(b"same archive bytes")
    second.write_bytes(b"same archive bytes")
    first_binding = audit._logical_binding(
        first,
        logical_path="v26.186-source-0cd043a1.git-archive.tar",
        source_kind="audited_v26_186_git_archive",
    )
    second_binding = audit._logical_binding(
        second,
        logical_path="v26.186-source-0cd043a1.git-archive.tar",
        source_kind="audited_v26_186_git_archive",
    )
    assert first_binding == second_binding
