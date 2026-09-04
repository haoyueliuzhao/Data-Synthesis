from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_reasoning_contract_freeze_independent_audit import (
    models,
)
from trusted_synthesis.experiments.qa_reasoning_contract_freeze_independent_audit.audit import (
    IndependentAuditError,
    _authorization,
    _files,
)
from trusted_synthesis.experiments.qa_reasoning_contract_freeze_independent_audit.runner import (
    build_finance_qa_reasoning_contract_independent_audit,
    validate_written_artifacts,
    write_finance_qa_reasoning_contract_independent_audit_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/f5f6d16a-1b03-4592-90a7-06a653195e8b/pasted-text.txt"
)
SOURCE_COMMIT = "5786b393597e3ea6955fcbb214310ab2606675d2"
SOURCE_TREE = "d856976de04b37c70198228dfdc4ae35388f837e"


@lru_cache(maxsize=1)
def _products():
    return build_finance_qa_reasoning_contract_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
    )


def test_exact_external_authority_and_candidate_freeze() -> None:
    products = _products()
    assert products.authorization["stage"] == models.STAGE
    assert products.candidate_freeze["passed"] is True
    assert products.candidate_freeze["file_count"] == 30
    assert products.candidate_freeze["total_bytes"] == 77_840


def test_detached_candidate_directory_rebuild_is_exact() -> None:
    audit = _products().detached_rebuild
    assert audit["archived_source_file_count"] == 741
    assert audit["path_matches"] == 30
    assert audit["sha256_matches"] == 30
    assert audit["actual_byte_matches"] == 30


def test_ten_contracts_are_independently_reconstructed() -> None:
    products = _products()
    assert tuple(row["name"] for row in products.contract_descriptors) == (models.CONTRACT_NAMES)
    assert products.contract_reconstruction_audit["candidate_actual_byte_matches"] == 10
    assert products.contract_reconstruction_audit["candidate_contract_helper_calls"] == 0


def test_thirteen_scientific_objects_are_independently_reconstructed() -> None:
    products = _products()
    assert tuple(products.scientific_objects) == models.OBJECT_NAMES
    assert products.object_reconstruction_audit["candidate_actual_byte_matches"] == 13
    assert products.object_reconstruction_audit["candidate_object_builder_calls"] == 0


def test_parent_order_and_cross_object_relations_pass() -> None:
    audit = _products().parent_relation_audit
    assert audit["passed"] is True
    assert audit["envelope_precedes_execution"] is True
    assert audit["update_to_next_state"] is True
    assert audit["durable_runtime_commit_claimed"] is False


def test_validity_target_depth_and_coverage_are_independently_derived() -> None:
    audit = _products().semantic_derivation_audit
    assert audit["qa_valid"] is True
    assert audit["trajectory_valid"] is True
    assert audit["qualified"] is True
    assert set(audit["target_allowed_modalities"]) == {
        "management_target",
        "company_guidance",
    }
    assert audit["derived_depth_metrics"] == {
        "semantic_operation_depth": 3,
        "reasoning_depth": 1,
        "evidence_integration_depth": 2,
        "correction_depth": 0,
        "required_decision_count": 1,
        "covered_required_decision_count": 1,
        "critical_decision_coverage": 1.0,
    }
    assert audit["coverage_measured"] is False


def test_all_ten_independent_attacks_reject() -> None:
    audit = _products().negative_control_audit
    assert tuple(row["name"] for row in audit["controls"]) == models.ATTACK_NAMES
    assert tuple(row["rejection_stage"] for row in audit["controls"]) == (models.ATTACK_STAGES)
    assert audit["rejected_count"] == 10
    assert audit["accepted_count"] == 0


def test_candidate_outcomes_are_compared_only_after_independent_work() -> None:
    audit = _products().candidate_final_comparison_audit
    assert audit["comparison_order"] == "after_all_independent_derivations_and_attacks"
    assert all(audit["candidate_actual_byte_comparisons"].values())
    assert audit["candidate_conformance_audit_used_as_input"] is False
    assert audit["candidate_gate_used_as_oracle"] is False
    assert audit["candidate_report_used_as_oracle"] is False


def test_noncompensatory_gate_and_transition_boundary() -> None:
    products = _products()
    assert products.gate["passed_count"] == 8
    assert products.gate["failed_count"] == 0
    assert products.decision["decision"] == models.DECISION
    assert products.transition["next_stage_authorized"] is False
    assert products.transition["prospective_next_stage"] == models.PROSPECTIVE_NEXT_STAGE
    assert products.scope_audit["provider_calls"] == 0
    assert products.scope_audit["archive_evidence_reads"] == 0
    assert products.scope_audit["fixed_fixture_qa_executions"] == 0


def test_invalid_external_review_rejects() -> None:
    with pytest.raises(IndependentAuditError, match="external independent review"):
        _authorization(REVIEW.read_bytes() + b"changed")


def test_two_empty_directory_builds_are_byte_identical(tmp_path: Path) -> None:
    products = _products()
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_finance_qa_reasoning_contract_independent_audit_artifacts(products, left)
    write_finance_qa_reasoning_contract_independent_audit_artifacts(products, right)
    assert _files(left) == _files(right)
    facts = validate_written_artifacts(left)
    assert facts["file_count"] == 21
    assert facts["manifest_member_count"] == 20
    assert facts["manifest_member_matches"] == 20
