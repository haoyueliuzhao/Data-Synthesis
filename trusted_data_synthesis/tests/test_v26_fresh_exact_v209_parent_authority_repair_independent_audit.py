# ruff: noqa: E501, SLF001
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_authority_repair_independent_audit as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_authority_repair_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/f2a3729e-e96b-4a75-9308-b58f0e7bda92/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V222_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.222 external review is unavailable")
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
    output = tmp_path_factory.mktemp("v26-222") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_authorization_and_v221_freeze(built: Path) -> None:
    authorization = models.ExternalIndependentAuditAuthorization.model_validate(
        _load(built, "external_independent_audit_authorization.json")
    )
    freeze = models.V221Freeze.model_validate(_load(built, "v221_freeze.json"))
    assert authorization.review_sha256 == subject.EXTERNAL_REVIEW_SHA256
    assert authorization.review_byte_count == 14_613
    assert authorization.audit_result == "PASSED_AS_SCOPED"
    assert authorization.blocking_defect == "NONE_FOUND"
    assert authorization.mandatory_revision == "NONE"
    assert authorization.repaired_object == "EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY"
    assert authorization.operator_directive == subject.OPERATOR_DIRECTIVE
    assert authorization.operator_directive_byte_count == 36
    assert (
        authorization.operator_directive_sha256
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert authorization.only_authorized_stage == models.CONSUMED_STAGE
    assert authorization.v220_authorization_unconsumed
    assert authorization.v220_authorization_forbidden_as_future_authority
    assert not authorization.new_online_authorization_created
    assert authorization.online_execution_blocked
    assert (freeze.v221_formal_file_count, freeze.v221_formal_total_byte_count) == (
        17,
        112_607,
    )
    assert (freeze.v221_manifest_member_count, freeze.v221_manifest_member_byte_count) == (
        16,
        109_876,
    )
    assert freeze.v221_source_commit == models.V221_COMMIT
    assert freeze.v221_source_tree == models.V221_TREE
    assert not freeze.v220_authorization_consumed
    assert freeze.v220_authorization_forbidden_as_successor_authority
    assert freeze.v221_online_authorization_count == freeze.v221_provider_calls == 0


def test_independent_source_does_not_call_candidate_helpers() -> None:
    tree = ast.parse((ROOT / subject.AUDIT_FILE).read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not called & {
        "_admit_exact_v209_files",
        "_relation_closure",
        "_upstream_tamper_audit",
    }
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        "execution_condition_parent_authority_repair_preflight" in item for item in imports
    )


def test_detached_v221_directory_rebuild_is_byte_exact(built: Path) -> None:
    audit = models.DetachedRebuildAudit.model_validate(_load(built, "detached_rebuild_audit.json"))
    assert audit.archived_source_file_count > 0
    assert (
        audit.path_match_count,
        audit.sha256_match_count,
        audit.byte_count_match_count,
        audit.actual_byte_match_count,
    ) == (17, 17, 17, 17)
    assert audit.saved_total_byte_count == audit.rebuilt_total_byte_count == 112_607
    assert audit.manifest_member_revalidation_count == 16
    assert not audit.candidate_report_used_as_outcome_oracle
    assert not audit.candidate_gate_used_as_outcome_oracle
    assert not audit.candidate_formal_freeze_used_as_outcome_oracle
    assert not audit.candidate_relation_audit_used_as_outcome_oracle
    assert not audit.candidate_tamper_audit_used_as_outcome_oracle
    assert audit.credential_like_environment_key_count == audit.credential_lookups == 0
    assert audit.provider_calls == 0


def test_exact_v209_parent_authority_is_independently_rederived(built: Path) -> None:
    audit = models.IndependentV209AuthorityAudit.model_validate(
        _load(built, "independent_v209_authority_audit.json")
    )
    assert audit.exact_v209_manifest_id == models.V209_MANIFEST_ID
    assert audit.exact_v209_artifact_root == models.V209_ROOT
    assert (audit.formal_file_count, audit.formal_total_byte_count) == (
        21,
        44_916_386,
    )
    assert (audit.member_count, audit.member_byte_count) == (20, 44_912_918)
    assert (
        audit.path_match_count,
        audit.sha256_match_count,
        audit.byte_count_match_count,
        audit.actual_byte_match_count,
    ) == (20, 20, 20, 20)
    assert audit.independent_identity_match_count == 1_024
    assert audit.source_commit_tree_match
    assert audit.source_file_commit_match_count == 3
    assert audit.package_catalog_id == subject.OBJECT_IDS["catalog_id"]
    assert audit.manifest_id == subject.OBJECT_IDS["manifest_id"]
    assert audit.runner_id == subject.OBJECT_IDS["runner_id"]
    assert audit.execution_contract_id == subject.OBJECT_IDS["contract_id"]
    assert audit.invocation_census_id == subject.OBJECT_IDS["census_id"]
    assert audit.implementation_id == subject.OBJECT_IDS["implementation_id"]
    assert audit.source_identity_id == subject.OBJECT_IDS["source_identity_id"]
    assert audit.candidate_condition_projection_match_count == 17
    assert audit.candidate_helper_calls == 0
    assert not audit.candidate_formal_freeze_used_as_outcome_oracle
    assert not audit.candidate_condition_used_as_outcome_oracle


def test_v209_relation_closure_is_independently_rederived(built: Path) -> None:
    audit = models.IndependentRelationClosureAudit.model_validate(
        _load(built, "independent_relation_closure_audit.json")
    )
    assert len(audit.exact_package_ids) == 32
    assert len(audit.exact_job_ids) == 192
    assert audit.exact_package_set_sha256 == (
        "3e060a554c17a9755d7c0f66fda2c524761342c47c5c6df36ef8661d9f1789f0"
    )
    assert audit.exact_job_set_sha256 == (
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    )
    assert audit.exact_coordinate_set_sha256 == (
        "1bfdada7dbb4eff6a05a1f009b69388da8a9d48e2297cc998d62bbe5fe2af7ed"
    )
    assert audit.manifest_job_count == audit.census_distinct_job_count == 192
    assert audit.census_job_set_matches_manifest
    assert audit.census_row_job_membership_match_count == 792
    assert audit.job_package_membership_match_count == 192
    assert audit.package_replica_cell_match_count == 192
    assert audit.namespace_owner_match_count == 768
    assert audit.namespace_unique_count_each == 192
    assert audit.parent_match_count == 12
    assert audit.expected_job_set_match
    assert audit.unique_coordinate_count == 792
    assert audit.candidate_relation_projection_match_count == 16
    assert audit.candidate_relation_helper_calls == 0
    assert not audit.candidate_relation_audit_used_as_outcome_oracle


def test_four_attacks_are_independently_reproduced_and_rejected(built: Path) -> None:
    audit = models.IndependentAttackAudit.model_validate(
        _load(built, "independent_upstream_attack_audit.json")
    )
    assert (audit.attack_count, audit.rejected_count, audit.accepted_count) == (4, 4, 0)
    assert audit.candidate_control_projection_match_count == 4
    assert audit.candidate_attack_helper_calls == 0
    assert not audit.candidate_tamper_audit_used_as_outcome_oracle
    assert audit.condition_objects_created == audit.online_authorizations_created == 0
    assert audit.attack_writes == audit.provider_calls == 0
    assert {item.control_name for item in audit.controls} == {
        "equal_cardinality_job_id_stale_manifest",
        "equal_cardinality_job_id_formal_rehash",
        "equal_cardinality_raw_namespace_stale_manifest",
        "equal_cardinality_raw_namespace_formal_rehash",
    }
    assert all(
        item.candidate_job_count == item.candidate_unique_job_count == 192
        for item in audit.controls
    )
    assert all(
        item.candidate_namespace_count == item.candidate_unique_namespace_count == 192
        for item in audit.controls
    )
    assert {item.rejection_stage for item in audit.controls} == {
        "independent_exact_v209_member_admission",
        "independent_exact_v209_manifest_root_admission",
    }
    assert all(item.candidate_control_projection_match for item in audit.controls)
    assert all(item.rejected_before_condition for item in audit.controls)


def test_gate_decision_transition_and_scope(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "prospective_transition.json"))
    assert (gate.passed_count, gate.failed_count) == (6, 0)
    assert gate.all_gates_passed
    assert not gate.online_authorization_issued
    assert decision.decision == models.DECISION
    assert decision.blocking_defect == "NONE_FOUND"
    assert decision.mandatory_revision == "NONE"
    assert not decision.v220_authorization_consumed
    assert not decision.new_online_authorization_issued
    assert transition.next_stage == models.NEXT_STAGE
    assert not transition.next_stage_authorized
    assert transition.separate_external_decision_required
    assert not transition.online_authorization_created
    assert not transition.provider_execution_authorized
    assert transition.v220_authorization_forbidden
    assert scope.v220_authorization_consumptions == 0
    assert scope.new_online_authorizations == 0
    assert scope.manifest_job_executions == 0
    assert scope.provider_calls == scope.provider_client_constructions == 0
    assert scope.credential_lookups == scope.empirical_rows == scope.empirical_estimates == 0
    assert scope.qa_reads == scope.mapper_state_frequency_contribution_vtdo_rows == 0


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
