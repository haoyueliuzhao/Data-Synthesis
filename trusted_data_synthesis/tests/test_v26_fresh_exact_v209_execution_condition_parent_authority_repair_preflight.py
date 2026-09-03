# ruff: noqa: E501, SLF001
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_preflight as subject,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/ed373186-cf67-4d77-a124-1a34ed746694/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V221_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.221 external review is unavailable")
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
    output = tmp_path_factory.mktemp("v26-221") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_repair_authorization_and_v220_freeze(built: Path) -> None:
    authorization = models.ExternalRepairAuthorization.model_validate(
        _load(built, "external_repair_authorization.json")
    )
    freeze = models.V220Freeze.model_validate(_load(built, "v220_freeze.json"))
    assert authorization.review_sha256 == subject.EXTERNAL_REVIEW_SHA256
    assert authorization.review_byte_count == 13_510
    assert authorization.audit_result == "FAIL"
    assert authorization.blocking_defect == (
        "EXACT_V209_EXECUTION_CONDITION_PARENT_AUTHORITY_NOT_CLOSED"
    )
    assert authorization.first_failed_gate == "G2_EXACT_V209_192_JOB_CONDITION"
    assert authorization.only_authorized_stage == models.CONSUMED_STAGE
    assert authorization.operator_directive == subject.OPERATOR_DIRECTIVE
    assert authorization.operator_directive_byte_count == 36
    assert (
        authorization.operator_directive_sha256
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert (freeze.v220_formal_file_count, freeze.v220_formal_total_byte_count) == (
        18,
        126_513,
    )
    assert freeze.v220_authorization_id == models.V220_AUTHORIZATION_ID
    assert freeze.authorization_object_construction_retained
    assert not freeze.exact_v209_condition_authority_retained
    assert not freeze.v220_authorization_consumed
    assert not freeze.v220_authorization_reusable


def test_complete_v209_formal_directory_is_authoritatively_frozen(built: Path) -> None:
    freeze = models.V209FormalAuthorityFreeze.model_validate(
        _load(built, "v209_formal_authority_freeze.json")
    )
    assert freeze.exact_artifact_manifest_id == models.V209_MANIFEST_ID
    assert freeze.exact_artifact_root == models.V209_ARTIFACT_ROOT
    assert (freeze.formal_file_count, freeze.formal_total_byte_count) == (
        21,
        44_916_386,
    )
    assert (freeze.manifest_member_count, freeze.manifest_member_byte_count) == (
        20,
        44_912_918,
    )
    assert len(freeze.members) == 20
    assert (
        freeze.path_match_count,
        freeze.sha256_match_count,
        freeze.byte_count_match_count,
        freeze.actual_byte_match_count,
    ) == (20, 20, 20, 20)
    assert freeze.strict_object_identity_revalidation_count == 1_024
    assert freeze.source_file_commit_match_count == 3
    projection = tuple(item.model_dump(mode="json") for item in freeze.members)
    assert freeze.formal_member_set_sha256 == models.canonical_sha256(projection)


def test_v209_relation_closure_is_complete(built: Path) -> None:
    audit = models.RelationClosureAudit.model_validate(_load(built, "relation_closure_audit.json"))
    assert len(audit.exact_package_ids) == 32
    assert len(audit.exact_job_ids) == 192
    assert audit.manifest_job_count == audit.census_distinct_job_count == 192
    assert audit.census_job_set_matches_manifest
    assert audit.census_row_job_membership_match_count == 792
    assert audit.job_package_membership_match_count == 192
    assert audit.package_replica_cell_match_count == 192
    assert audit.namespace_owner_match_count == 768
    assert audit.namespace_unique_count_each == 192
    assert audit.runner_contract_census_parent_match_count == 12
    assert audit.expected_job_set_match and audit.all_relations_closed
    assert audit.exact_job_set_sha256 == (
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    )
    assert audit.exact_coordinate_set_sha256 == (
        "1bfdada7dbb4eff6a05a1f009b69388da8a9d48e2297cc998d62bbe5fe2af7ed"
    )


def test_authoritative_condition_and_composition_bind_manifest_root(built: Path) -> None:
    condition = models.AuthoritativeExecutionConditionBinding.model_validate(
        _load(built, "authoritative_execution_condition_binding.json")
    )
    composition = models.RepairedCompositionContract.model_validate(
        _load(built, "repaired_composition_contract.json")
    )
    assert condition.exact_v209_artifact_manifest_id == models.V209_MANIFEST_ID
    assert condition.exact_v209_artifact_root == models.V209_ARTIFACT_ROOT
    assert condition.exact_package_count == 32
    assert condition.exact_job_count == 192
    assert condition.exact_coordinate_count == 792
    assert condition.previous_v220_condition_authority_superseded
    assert not condition.current_v220_authorization_consumed
    assert not condition.current_v220_authorization_reusable
    assert not condition.new_online_authorization_created
    assert composition.authoritative_condition_binding_id == condition.binding_id
    assert composition.exact_v209_artifact_manifest_id == models.V209_MANIFEST_ID
    assert composition.exact_v209_artifact_root == models.V209_ARTIFACT_ROOT
    assert composition.v209_formal_admission_required_before_condition_construction
    assert composition.relation_closure_required_before_authorization
    assert composition.current_v220_authorization_forbidden


def test_equal_cardinality_upstream_tamper_controls_reject_before_condition(
    built: Path,
) -> None:
    audit = models.UpstreamTamperAudit.model_validate(_load(built, "upstream_tamper_audit.json"))
    assert audit.attack_count == 4
    assert audit.job_id_attack_count == audit.namespace_attack_count == 2
    assert audit.formal_manifest_rehash_attack_count == 2
    assert audit.prospective_downstream_rehashed_object_count == 12
    assert audit.rejected_before_condition_count == 4
    assert audit.accepted_attack_count == 0
    assert audit.authoritative_condition_created_count == 0
    assert audit.online_authorization_created_count == 0
    assert all(item.cardinality_preserved for item in audit.controls)
    assert all(
        item.candidate_job_count == item.candidate_unique_job_count == 192
        for item in audit.controls
    )
    assert all(
        item.candidate_namespace_count == item.candidate_unique_namespace_count == 192
        for item in audit.controls
    )
    assert all(item.rejected_before_condition_construction for item in audit.controls)
    assert all(not item.authoritative_condition_created for item in audit.controls)
    assert all(not item.online_authorization_created for item in audit.controls)
    stages = {item.rejection_stage for item in audit.controls}
    assert stages == {
        "exact_v209_member_admission",
        "exact_v209_manifest_root_admission",
    }


def test_formal_admission_precedes_object_parsing_in_source() -> None:
    source = inspect.getsource(subject._v209_authority)
    assert source.index("_admit_exact_v209_files(files)") < source.index(
        "ExecutableRunnerPackageCatalog.model_validate"
    )
    assert "artifact_manifest.json" in inspect.getsource(subject._admit_exact_v209_files)
    admission_source = inspect.getsource(subject._admit_exact_v209_files)
    assert "models.V209_MANIFEST_ID" in admission_source
    assert "models.V209_ARTIFACT_ROOT" in admission_source


def test_gate_decision_transition_and_scope(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "prospective_transition.json"))
    assert (gate.passed_count, gate.failed_count) == (8, 0)
    assert gate.all_gates_passed
    assert not gate.online_authorization_issued
    assert decision.decision == models.DECISION
    assert not decision.v220_authorization_consumed
    assert not decision.v220_authorization_reusable
    assert not decision.new_online_authorization_issued
    assert transition.next_stage == models.NEXT_STAGE
    assert not transition.next_stage_authorized
    assert transition.separate_external_audit_decision_required
    assert transition.fresh_online_authorization_required_after_audit
    assert transition.v220_authorization_forbidden
    assert not transition.provider_execution_authorized
    assert not scope.v220_authorization_consumed
    assert not scope.v220_authorization_reused
    assert scope.new_online_authorizations == 0
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
