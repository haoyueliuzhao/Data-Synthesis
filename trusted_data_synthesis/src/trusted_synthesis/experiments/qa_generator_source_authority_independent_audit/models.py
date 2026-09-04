from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE: Final = (
    "qa_generator_source_commit_tree_member_authority_repair_preflight_independent_audit_only"
)
NEXT_STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_only"
)
DECISION: Final = (
    "qa_generator_source_commit_tree_member_authority_repair_preflight_independently_confirmed"
)

EXTERNAL_REVIEW_SHA256: Final = "d9bf1fa44fb1901b0dde5b32a40c1827fc1bce915e521364059ea59a953a076e"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 12_251
OPERATOR_DIRECTIVE: Final = "参照审计报告开展实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "a76f3f3a79633a2d775212ad2b1daf5c6b1543bb9aa47d03897aa3bb361169d8"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 30

CANDIDATE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_generator_source_authority/"
    "qa_generator_source_commit_tree_member_authority_and_depth_metric_"
    "repair_preflight_v1_20260904"
)
CANDIDATE_FILE_COUNT: Final = 24
CANDIDATE_TOTAL_BYTES: Final = 463_886
CANDIDATE_MEMBER_COUNT: Final = 23
CANDIDATE_MEMBER_BYTES: Final = 460_263
CANDIDATE_MANIFEST_BYTE_COUNT: Final = 3_623
CANDIDATE_MANIFEST_SHA256: Final = (
    "fb59acf615a30dc0e45eee95e0c2521e999888b8e0d1b510bfd19986a114f531"
)
CANDIDATE_MANIFEST_ID: Final = (
    "qa_generator_source_authority_artifact_manifest:"
    "6df4b52442396600fc7112f9af7598cb3d1c8cea08532156614288da7e7bec4b"
)
CANDIDATE_ARTIFACT_ROOT: Final = (
    "qa_generator_source_authority_artifact_root:"
    "307fd8ef9563e619f8e8f3815e5b754ccd01bfd872af72bd094e9244cbe85d4b"
)
CANDIDATE_AUTHORIZATION_ID: Final = (
    "qa_generator_source_authority_authorization:"
    "0374527bdc9a26e3bc89855b92c0d054840fc6b964f12de012b3817c132d5d4c"
)
CANDIDATE_PREDECESSOR_FREEZE_ID: Final = (
    "qa_generator_source_authority_predecessor_freeze:"
    "454893143af7f57d952dff22e1aae4d4c5905519c17bbe7f0db21049b2df34d1"
)
CANDIDATE_GENERATOR_BINDING_ID: Final = (
    "qa_generator_authoritative_source_binding:"
    "cd4f225e2e27fa8006828bf4deadd847ad1113d69e9c1c7a0e0d9e3cb3d3e7e9"
)
CANDIDATE_REPAIR_BINDING_ID: Final = (
    "qa_generator_authoritative_source_binding:"
    "df21b1f4f733f199a741007fb602c36bfa6cb5683eae8c3e1dbd00232f7937ff"
)
CANDIDATE_LEGACY_AUDIT_ID: Final = (
    "qa_generator_legacy_source_counterexample_audit:"
    "5b2ad1f7d0083aaa8516bd2d39c759e04081df6173acaefe42c76bad6d311d8f"
)
CANDIDATE_SOURCE_ATTACK_AUDIT_ID: Final = (
    "qa_generator_source_authority_negative_audit:"
    "f7d626a9ac63f89cbfa13be1a4075461e7b0021d3c863b85046458b37cc0a082"
)
CANDIDATE_DEPTH_CONTRACT_ID: Final = (
    "qa_program_depth_metric_contract:"
    "3ba7a43cf65f5a37a3dcc648f62ac78489e8b5af16aea0583005e9cd06472865"
)
CANDIDATE_DEPTH_AUDIT_ID: Final = (
    "qa_program_depth_metric_audit:34eda481363cc892054f483f8f531f0d5ffe955a07f03cefde2ad4bb98d91d66"
)
CANDIDATE_DEPTH_ATTACK_AUDIT_ID: Final = (
    "qa_program_depth_negative_control_audit:"
    "6fdd6c29a0435be0ab9acda436925fc948638d73469ed3c606c0a0e627e24b7b"
)
CANDIDATE_FIXTURE_AUDIT_ID: Final = (
    "qa_generator_source_authority_retained_fixture_audit:"
    "1ad3c4ef3e468bf641af560a68a00554c88bfe1d4469d5cade36276c29118e0c"
)
CANDIDATE_SCOPE_AUDIT_ID: Final = (
    "qa_generator_source_authority_scope_audit:"
    "38b69b80cb16f9700eeef71f0a0cb348d3337e7c1d8aef7ca19371a28c546d14"
)
CANDIDATE_GATE_ID: Final = (
    "qa_generator_source_authority_gate:"
    "a424203dbf5ad7f9f1f69c380286ee20162edd47f917f316adfb57d401cea1c5"
)
CANDIDATE_REPORT_ID: Final = (
    "qa_generator_source_authority_repair_report:"
    "f42aca195e54f4f59c04e47fc4a27984bf75db88338146e87c57e65c9e38a1f8"
)
CANDIDATE_TRANSITION_ID: Final = (
    "qa_generator_source_authority_transition:"
    "4ec41dda6eb1379e33f9abbfba5d66df8c422889c683085b711e87396055fe02"
)

GENERATOR_SOURCE_COMMIT: Final = "dba5d949a743dd625e5fe0e10b0f4809ac9f87ad"
GENERATOR_SOURCE_TREE: Final = "d706531377e5303265cd2dcee3e355c6642c466b"
GENERATOR_PATH_SET_SHA256: Final = (
    "2d24258e2d540715069bb5ba207d3b559bb45b2e44213fcb595182d2911e3146"
)
GENERATOR_FILE_SET_SHA256: Final = (
    "f5ea13aaf82a6fb216a47e8b967035bcef73c50daeb7aae61b846a281db2634e"
)
REPAIR_SOURCE_COMMIT: Final = "f26e30c0c6488e5b14b2004bd776e23f23dbc77d"
REPAIR_SOURCE_TREE: Final = "7917ca2e0172394d2779d0186d1046bda872555c"
REPAIR_PATH_SET_SHA256: Final = "674da32629598c78f6a49fe2a6fe88a6a798178732d5698c5453cbeab3ac9999"
REPAIR_FILE_SET_SHA256: Final = "3c4f739eeb9520b69efb2e6da6a78da8bceb4e922f7bd025ff5b7bf21aa82284"
REGISTRY_MANIFEST_SHA256: Final = "74229358e9c21a1f08a4cc33df9a8cd648de72a4b3600309d197c1b664afaf40"

GENERATOR_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/answer.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/evaluator.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/operations/program.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/operations/registry.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/trajectory/candidate_verifier.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/trajectory/public_plan_executor.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/operations.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/pattern_runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/patterns.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/policy.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/tasks.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_pilot/candidate.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_generator_totality/preflight.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_semantic_coverage/preflight.py",
)
REPAIR_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/core/task/program_depth.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_generator_source_authority/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_generator_source_authority/depth.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_generator_source_authority/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_generator_source_authority/preflight.py",
)
REGISTERED_TASK_TYPES: Final = (
    "comparison",
    "derived_growth_comparison",
    "fact_retrieval",
    "registered_cross_metric_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)
SOURCE_ATTACK_NAMES: Final = (
    "nonexistent_commit",
    "real_commit_wrong_tree",
    "changed_source_member",
    "crossed_source_members",
    "uncommitted_worktree_source",
)
SOURCE_ATTACK_STAGES: Final = (
    "git_commit_resolution",
    "commit_tree_relation",
    "committed_member_bytes",
    "committed_member_bytes",
    "current_worktree_member_bytes",
)
DEPTH_ATTACK_NAMES: Final = (
    "delete_required_semantic_dependency",
    "bypass_derived_semantic_chain",
    "inflate_with_irrelevant_lookup",
)
DEPTH_ATTACK_STAGES: Final = (
    "exact_source_program_admission",
    "exact_source_program_admission",
    "output_dependency_closure",
)
GATE_NAMES: Final = (
    "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE",
    "A1_DETACHED_EXACT_DIRECTORY_REBUILD",
    "A2_INDEPENDENT_GIT_SOURCE_AUTHORITY",
    "A3_LEGACY_COUNTEREXAMPLE_AND_SOURCE_ATTACKS",
    "A4_INDEPENDENT_EIGHT_FIXTURE_RECONSTRUCTION",
    "A5_INDEPENDENT_FOUR_DEPTH_METRIC_DERIVATION",
    "A6_INDEPENDENT_DEPTH_ATTACKS",
    "A7_ZERO_EXTERNAL_EXECUTION_SCOPE",
)

EXPECTED_DEPTHS: Final = {
    "comparison": (1, 1, 1, 3),
    "derived_growth_comparison": (7, 3, 2, 4),
    "fact_retrieval": (1, 1, 0, 2),
    "registered_cross_metric_comparison": (1, 1, 1, 3),
    "registered_ratio": (3, 2, 1, 3),
    "temporal_absolute_change": (3, 2, 1, 3),
    "temporal_average": (4, 2, 1, 3),
    "temporal_growth": (3, 2, 1, 3),
}

ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identified(
    model_type: type[ModelT], values: Mapping[str, Any], field: str, prefix: str
) -> ModelT:
    payload = dict(values)
    payload[field] = "pending"
    draft = model_type.model_construct(**payload)
    payload[field] = strict_canonical_hash(
        draft.model_dump(mode="python", exclude={field}), prefix=prefix
    )
    return model_type.model_validate(payload)


class Identified(FrozenModel):
    @classmethod
    def identity_prefix(cls) -> str:
        raise NotImplementedError

    def require_identity(self, field: str) -> None:
        if getattr(self, field) != strict_canonical_hash(
            self.model_dump(mode="python", exclude={field}), prefix=self.identity_prefix()
        ):
            raise ValueError(f"{type(self).__name__} identity differs")


class ExternalIndependentAuditAuthorization(Identified):
    authorization_id: str = Field(min_length=1)
    stage: Literal[
        "qa_generator_source_commit_tree_member_authority_repair_preflight_independent_audit_only"
    ] = STAGE
    external_review_sha256: Literal[
        "d9bf1fa44fb1901b0dde5b32a40c1827fc1bce915e521364059ea59a953a076e"
    ] = EXTERNAL_REVIEW_SHA256
    external_review_byte_count: Literal[12251] = EXTERNAL_REVIEW_BYTE_COUNT
    operator_directive: Literal["参照审计报告开展实验"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "a76f3f3a79633a2d775212ad2b1daf5c6b1543bb9aa47d03897aa3bb361169d8"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[30] = OPERATOR_DIRECTIVE_BYTE_COUNT
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    online_generation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    semantic_depth_expansion_authorized: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_independent_authorization.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_audit_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> ExternalIndependentAuditAuthorization:
        directive = self.operator_directive.encode()
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("independent-audit operator directive differs")
        self.require_identity("authorization_id")
        return self


class CandidateArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class CandidateFreezeAudit(Identified):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    directory: Literal[
        "trusted_data_synthesis/artifacts/qa_generator_source_authority/"
        "qa_generator_source_commit_tree_member_authority_and_depth_metric_"
        "repair_preflight_v1_20260904"
    ] = CANDIDATE_DIRECTORY
    file_count: Literal[24] = CANDIDATE_FILE_COUNT
    total_bytes: Literal[463886] = CANDIDATE_TOTAL_BYTES
    manifest_member_count: Literal[23] = CANDIDATE_MEMBER_COUNT
    manifest_member_bytes: Literal[460263] = CANDIDATE_MEMBER_BYTES
    manifest_byte_count: Literal[3623] = CANDIDATE_MANIFEST_BYTE_COUNT
    manifest_sha256: Literal["fb59acf615a30dc0e45eee95e0c2521e999888b8e0d1b510bfd19986a114f531"] = (
        CANDIDATE_MANIFEST_SHA256
    )
    manifest_id: Literal[
        "qa_generator_source_authority_artifact_manifest:"
        "6df4b52442396600fc7112f9af7598cb3d1c8cea08532156614288da7e7bec4b"
    ] = CANDIDATE_MANIFEST_ID
    artifact_root: Literal[
        "qa_generator_source_authority_artifact_root:"
        "307fd8ef9563e619f8e8f3815e5b754ccd01bfd872af72bd094e9244cbe85d4b"
    ] = CANDIDATE_ARTIFACT_ROOT
    candidate_authorization_id: Literal[
        "qa_generator_source_authority_authorization:"
        "0374527bdc9a26e3bc89855b92c0d054840fc6b964f12de012b3817c132d5d4c"
    ] = CANDIDATE_AUTHORIZATION_ID
    predecessor_freeze_id: Literal[
        "qa_generator_source_authority_predecessor_freeze:"
        "454893143af7f57d952dff22e1aae4d4c5905519c17bbe7f0db21049b2df34d1"
    ] = CANDIDATE_PREDECESSOR_FREEZE_ID
    generator_binding_id: Literal[
        "qa_generator_authoritative_source_binding:"
        "cd4f225e2e27fa8006828bf4deadd847ad1113d69e9c1c7a0e0d9e3cb3d3e7e9"
    ] = CANDIDATE_GENERATOR_BINDING_ID
    repair_binding_id: Literal[
        "qa_generator_authoritative_source_binding:"
        "df21b1f4f733f199a741007fb602c36bfa6cb5683eae8c3e1dbd00232f7937ff"
    ] = CANDIDATE_REPAIR_BINDING_ID
    depth_contract_id: Literal[
        "qa_program_depth_metric_contract:"
        "3ba7a43cf65f5a37a3dcc648f62ac78489e8b5af16aea0583005e9cd06472865"
    ] = CANDIDATE_DEPTH_CONTRACT_ID
    depth_audit_id: Literal[
        "qa_program_depth_metric_audit:"
        "34eda481363cc892054f483f8f531f0d5ffe955a07f03cefde2ad4bb98d91d66"
    ] = CANDIDATE_DEPTH_AUDIT_ID
    depth_attack_audit_id: Literal[
        "qa_program_depth_negative_control_audit:"
        "6fdd6c29a0435be0ab9acda436925fc948638d73469ed3c606c0a0e627e24b7b"
    ] = CANDIDATE_DEPTH_ATTACK_AUDIT_ID
    fixture_audit_id: Literal[
        "qa_generator_source_authority_retained_fixture_audit:"
        "1ad3c4ef3e468bf641af560a68a00554c88bfe1d4469d5cade36276c29118e0c"
    ] = CANDIDATE_FIXTURE_AUDIT_ID
    legacy_audit_id: Literal[
        "qa_generator_legacy_source_counterexample_audit:"
        "5b2ad1f7d0083aaa8516bd2d39c759e04081df6173acaefe42c76bad6d311d8f"
    ] = CANDIDATE_LEGACY_AUDIT_ID
    source_attack_audit_id: Literal[
        "qa_generator_source_authority_negative_audit:"
        "f7d626a9ac63f89cbfa13be1a4075461e7b0021d3c863b85046458b37cc0a082"
    ] = CANDIDATE_SOURCE_ATTACK_AUDIT_ID
    scope_audit_id: Literal[
        "qa_generator_source_authority_scope_audit:"
        "38b69b80cb16f9700eeef71f0a0cb348d3337e7c1d8aef7ca19371a28c546d14"
    ] = CANDIDATE_SCOPE_AUDIT_ID
    gate_id: Literal[
        "qa_generator_source_authority_gate:"
        "a424203dbf5ad7f9f1f69c380286ee20162edd47f917f316adfb57d401cea1c5"
    ] = CANDIDATE_GATE_ID
    report_id: Literal[
        "qa_generator_source_authority_repair_report:"
        "f42aca195e54f4f59c04e47fc4a27984bf75db88338146e87c57e65c9e38a1f8"
    ] = CANDIDATE_REPORT_ID
    transition_id: Literal[
        "qa_generator_source_authority_transition:"
        "4ec41dda6eb1379e33f9abbfba5d66df8c422889c683085b711e87396055fe02"
    ] = CANDIDATE_TRANSITION_ID
    members: tuple[CandidateArtifactMember, ...] = Field(min_length=23, max_length=23)
    path_matches: Literal[24] = 24
    sha256_matches: Literal[24] = 24
    byte_count_matches: Literal[24] = 24
    actual_byte_matches: Literal[24] = 24
    manifest_members_revalidated: Literal[23] = 23
    candidate_report_used_as_oracle: Literal[False] = False
    candidate_gate_used_as_oracle: Literal[False] = False
    candidate_depth_audit_used_as_oracle: Literal[False] = False
    passed: Literal[True] = True
    schema_version: str = "qa_generator_source_authority_candidate_freeze_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_candidate_freeze_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> CandidateFreezeAudit:
        paths = tuple(row.relative_path for row in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or sum(row.byte_count for row in self.members) != CANDIDATE_MEMBER_BYTES
            or strict_canonical_hash(
                tuple(row.model_dump(mode="python") for row in self.members),
                prefix="qa_generator_source_authority_artifact_root:",
            )
            != self.artifact_root
        ):
            raise ValueError("candidate Manifest members differ")
        self.require_identity("audit_id")
        return self


class DetachedRebuildAudit(Identified):
    audit_id: str = Field(min_length=1)
    candidate_freeze_audit_id: str = Field(min_length=1)
    archived_source_file_count: int = Field(gt=0)
    saved_file_count: Literal[24] = 24
    rebuilt_file_count: Literal[24] = 24
    saved_byte_count: Literal[463886] = CANDIDATE_TOTAL_BYTES
    rebuilt_byte_count: Literal[463886] = CANDIDATE_TOTAL_BYTES
    path_matches: Literal[24] = 24
    sha256_matches: Literal[24] = 24
    actual_byte_matches: Literal[24] = 24
    manifest_members_revalidated: Literal[23] = 23
    candidate_report_used_as_oracle: Literal[False] = False
    candidate_gate_used_as_oracle: Literal[False] = False
    credential_like_environment_keys: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_source_authority_detached_rebuild_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_detached_rebuild_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> DetachedRebuildAudit:
        self.require_identity("audit_id")
        return self


class GitSourceMemberAuditRow(FrozenModel):
    relative_path: str = Field(min_length=1)
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    committed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    committed_byte_count: int = Field(gt=0)
    current_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_byte_count: int = Field(gt=0)
    git_blob_matches: Literal[True] = True
    committed_bytes_match: Literal[True] = True
    current_bytes_match: Literal[True] = True

    @model_validator(mode="after")
    def validate_all(self) -> GitSourceMemberAuditRow:
        if (
            self.committed_sha256 != self.current_sha256
            or self.committed_byte_count != self.current_byte_count
        ):
            raise ValueError("independently read committed/current member bytes differ")
        return self


class GitSourceGroupAudit(Identified):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authority_kind: Literal["generator_verifier", "repair_implementation"]
    requested_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    resolved_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    requested_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    resolved_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    commit_object_type: Literal["commit"] = "commit"
    commit_tree_relation_verified: Literal[True] = True
    members: tuple[GitSourceMemberAuditRow, ...]
    member_count: int = Field(ge=5, le=14)
    source_path_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_file_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_binding_id: str = Field(min_length=1)
    candidate_binding_actual_byte_match: Literal[True] = True
    candidate_binding_used_as_authority: Literal[False] = False
    all_members_exist_at_commit: Literal[True] = True
    all_current_bytes_equal_committed_bytes: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_git_source_group_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_git_source_group_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> GitSourceGroupAudit:
        paths: tuple[str, ...]
        if self.authority_kind == "generator_verifier":
            commit = GENERATOR_SOURCE_COMMIT
            tree = GENERATOR_SOURCE_TREE
            paths = GENERATOR_SOURCE_PATHS
            path_hash = GENERATOR_PATH_SET_SHA256
            file_hash = GENERATOR_FILE_SET_SHA256
            binding_id = CANDIDATE_GENERATOR_BINDING_ID
        else:
            commit = REPAIR_SOURCE_COMMIT
            tree = REPAIR_SOURCE_TREE
            paths = REPAIR_SOURCE_PATHS
            path_hash = REPAIR_PATH_SET_SHA256
            file_hash = REPAIR_FILE_SET_SHA256
            binding_id = CANDIDATE_REPAIR_BINDING_ID
        if (
            self.requested_commit != commit
            or self.resolved_commit != commit
            or self.requested_tree != tree
            or self.resolved_tree != tree
            or tuple(row.relative_path for row in self.members) != paths
            or self.member_count != len(paths)
            or self.source_path_set_sha256 != path_hash
            or self.source_file_set_sha256 != file_hash
            or self.candidate_binding_id != binding_id
        ):
            raise ValueError("independent Git source group differs")
        self.require_identity("audit_id")
        return self


class IndependentGitSourceAuthorityAudit(Identified):
    audit_id: str = Field(min_length=1)
    candidate_freeze_audit_id: str = Field(min_length=1)
    generator_group: GitSourceGroupAudit
    repair_group: GitSourceGroupAudit
    source_group_count: Literal[2] = 2
    total_member_count: Literal[19] = 19
    commit_object_matches: Literal[2] = 2
    commit_tree_relation_matches: Literal[2] = 2
    committed_member_byte_matches: Literal[19] = 19
    current_member_byte_matches: Literal[19] = 19
    candidate_binding_actual_byte_matches: Literal[2] = 2
    candidate_source_binding_helper_calls: Literal[0] = 0
    transitive_import_closure_claimed: Literal[False] = False
    runtime_environment_closure_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_git_source_authority_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_git_source_authority_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentGitSourceAuthorityAudit:
        if (
            self.generator_group.authority_kind != "generator_verifier"
            or self.repair_group.authority_kind != "repair_implementation"
        ):
            raise ValueError("independent Git source groups crossed")
        self.require_identity("audit_id")
        return self


class IndependentLegacyCounterexampleAudit(Identified):
    audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    fake_source_commit: Literal["0000000000000000000000000000000000000000"] = (
        "0000000000000000000000000000000000000000"
    )
    unrelated_source_tree: Literal["1111111111111111111111111111111111111111"] = (
        "1111111111111111111111111111111111111111"
    )
    candidate_legacy_binding_id: Literal[
        "qa_generator_totality_source_binding:"
        "f9ee1a7058720579564b6e03bc590340f858984285f104410ba747bb2358fc58"
    ]
    legacy_binding_constructed: Literal[True] = True
    legacy_g2_passed: Literal[True] = True
    new_authority_rejected: Literal[True] = True
    rejection_stage: Literal["git_commit_resolution"] = "git_commit_resolution"
    exception_type: Literal["GitSourceAuthorityError"] = "GitSourceAuthorityError"
    reason_sha256: Literal["10078ab8a5517a9c04c0cdbfc80492748eb3c076d5c486c4a47f6f6c2e5e9726"]
    candidate_counterexample_helper_calls: Literal[0] = 0
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_legacy_counterexample_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_legacy_counterexample_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentLegacyCounterexampleAudit:
        self.require_identity("audit_id")
        return self


class IndependentSourceAttackControl(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: str = Field(min_length=1)
    exception_type: Literal["GitSourceAuthorityError"] = "GitSourceAuthorityError"
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_binding_rehashed: bool
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class IndependentSourceAttackAudit(Identified):
    audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    controls: tuple[IndependentSourceAttackControl, ...] = Field(min_length=5, max_length=5)
    attempted_count: Literal[5] = 5
    rejected_count: Literal[5] = 5
    accepted_count: Literal[0] = 0
    candidate_attack_helper_calls: Literal[0] = 0
    output_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_source_attack_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_source_attack_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentSourceAttackAudit:
        if (
            tuple(row.name for row in self.controls) != SOURCE_ATTACK_NAMES
            or tuple(row.rejection_stage for row in self.controls) != SOURCE_ATTACK_STAGES
        ):
            raise ValueError("independent source-attack partition differs")
        self.require_identity("audit_id")
        return self


class IndependentFixtureRow(Identified):
    row_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    evidence_bundle_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    public_plan_execution_id: str = Field(min_length=1)
    verification_report_id: str = Field(min_length=1)
    quality_assessment_id: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    node_count: int = Field(ge=1)
    executed_node_count: int = Field(ge=1)
    independently_replayed_node_count: int = Field(ge=1)
    generator_succeeded: Literal[True] = True
    insufficient_capability: Literal[False] = False
    operation_correct: Literal[True] = True
    answer_schema_correct: Literal[True] = True
    answer_correct: Literal[True] = True
    citation_correct: Literal[True] = True
    evaluator_accepted: Literal[True] = True
    candidate_object_matches: Literal[6] = 6

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_fixture_row:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentFixtureRow:
        if (
            self.task_type not in REGISTERED_TASK_TYPES
            or self.executed_node_count != self.node_count
            or self.independently_replayed_node_count != self.node_count
        ):
            raise ValueError("independently reconstructed fixture row differs")
        self.require_identity("row_id")
        return self


class IndependentFixtureAudit(Identified):
    audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    rows: tuple[IndependentFixtureRow, ...] = Field(min_length=8, max_length=8)
    registered_task_types: tuple[str, ...] = REGISTERED_TASK_TYPES
    registered_task_count: Literal[8] = 8
    generator_success_count: Literal[8] = 8
    exact_program_execution_count: Literal[8] = 8
    independent_node_replay_count: Literal[8] = 8
    operation_correct_count: Literal[8] = 8
    answer_schema_correct_count: Literal[8] = 8
    answer_correct_count: Literal[8] = 8
    citation_correct_count: Literal[8] = 8
    evaluator_accepted_count: Literal[8] = 8
    insufficient_capability_count: Literal[0] = 0
    candidate_fixture_helper_calls: Literal[0] = 0
    deterministic_fixed_fixture_constructibility_only: Literal[True] = True
    archive_grounding_claimed: Literal[False] = False
    realistic_difficulty_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_fixture_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_fixture_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentFixtureAudit:
        if tuple(row.task_type for row in self.rows) != REGISTERED_TASK_TYPES:
            raise ValueError("independent fixture task domain differs")
        self.require_identity("audit_id")
        return self


class IndependentDepthMetricRow(Identified):
    row_id: str = Field(min_length=1)
    fixture_row_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    program_hash: str = Field(min_length=1)
    metrics_id: str = Field(min_length=1)
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    registry_role_sequence: tuple[Literal["transparent_projection", "semantic"], ...] = Field(
        min_length=1
    )
    node_count: int = Field(ge=1)
    structural_dependency_depth: int = Field(ge=1)
    semantic_operation_depth: int = Field(ge=0)
    workflow_interaction_depth: int = Field(ge=2)
    output_dependency_closed: Literal[True] = True
    exact_source_program_admitted: Literal[True] = True
    plan_template_stage_counted: Literal[False] = False
    answer_template_stage_counted: Literal[False] = False
    candidate_metric_row_match: Literal[True] = True

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_depth_metric_row:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentDepthMetricRow:
        if (
            self.task_type not in EXPECTED_DEPTHS
            or (
                self.node_count,
                self.structural_dependency_depth,
                self.semantic_operation_depth,
                self.workflow_interaction_depth,
            )
            != EXPECTED_DEPTHS[self.task_type]
            or len(self.operator_sequence) != self.node_count
            or len(self.registry_role_sequence) != self.node_count
            or self.workflow_interaction_depth != self.semantic_operation_depth + 2
        ):
            raise ValueError("independently derived depth row differs")
        self.require_identity("row_id")
        return self


class IndependentDepthMetricAudit(Identified):
    audit_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    candidate_depth_contract_id: Literal[
        "qa_program_depth_metric_contract:"
        "3ba7a43cf65f5a37a3dcc648f62ac78489e8b5af16aea0583005e9cd06472865"
    ] = CANDIDATE_DEPTH_CONTRACT_ID
    registry_manifest_sha256: Literal[
        "74229358e9c21a1f08a4cc33df9a8cd648de72a4b3600309d197c1b664afaf40"
    ] = REGISTRY_MANIFEST_SHA256
    rows: tuple[IndependentDepthMetricRow, ...] = Field(min_length=8, max_length=8)
    node_count_distribution: dict[str, int]
    structural_dependency_depth_distribution: dict[str, int]
    semantic_operation_depth_distribution: dict[str, int]
    workflow_interaction_depth_distribution: dict[str, int]
    maximum_structural_dependency_depth: Literal[3] = 3
    maximum_semantic_operation_depth: Literal[2] = 2
    semantic_depth_three_plus_count: Literal[0] = 0
    output_dependency_closed_count: Literal[8] = 8
    exact_source_program_admitted_count: Literal[8] = 8
    candidate_depth_helper_calls: Literal[0] = 0
    candidate_depth_audit_used_as_oracle: Literal[False] = False
    legacy_program_depth_authoritative: Literal[False] = False
    legacy_semantic_only_depth_authoritative: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_depth_metric_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_depth_metric_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentDepthMetricAudit:
        if (
            tuple(row.task_type for row in self.rows) != REGISTERED_TASK_TYPES
            or self.node_count_distribution != {"1": 3, "3": 3, "4": 1, "7": 1}
            or self.structural_dependency_depth_distribution != {"1": 3, "2": 4, "3": 1}
            or self.semantic_operation_depth_distribution != {"0": 1, "1": 6, "2": 1}
            or self.workflow_interaction_depth_distribution != {"2": 1, "3": 6, "4": 1}
        ):
            raise ValueError("independent depth-metric distribution differs")
        self.require_identity("audit_id")
        return self


class IndependentDepthAttackControl(FrozenModel):
    name: str = Field(min_length=1)
    candidate_program_id: str = Field(min_length=1)
    candidate_program_hash: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_answer_retained: Literal[True] = True
    retained_final_answer_sha256: Literal[
        "5c456682a3aa97824b2179d642b142b398af6d496d6781a86dc4c304503de4e8"
    ]
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class IndependentDepthAttackAudit(Identified):
    audit_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    controls: tuple[IndependentDepthAttackControl, ...] = Field(min_length=3, max_length=3)
    attempted_count: Literal[3] = 3
    rejected_count: Literal[3] = 3
    accepted_count: Literal[0] = 0
    retained_final_answer_count: Literal[3] = 3
    candidate_depth_attack_helper_calls: Literal[0] = 0
    output_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = "qa_generator_independent_depth_attack_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_independent_depth_attack_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentDepthAttackAudit:
        if (
            tuple(row.name for row in self.controls) != DEPTH_ATTACK_NAMES
            or tuple(row.rejection_stage for row in self.controls) != DEPTH_ATTACK_STAGES
        ):
            raise ValueError("independent depth-attack partition differs")
        self.require_identity("audit_id")
        return self


class IndependentScopeBoundaryAudit(Identified):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    candidate_freeze_audit_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    source_attack_audit_id: str = Field(min_length=1)
    depth_attack_audit_id: str = Field(min_length=1)
    audit_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audit_source_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    audit_source_relative_path: Literal[
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "qa_generator_source_authority_independent_audit/audit.py"
    ] = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "qa_generator_source_authority_independent_audit/audit.py"
    )
    audit_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_source_byte_count: int = Field(gt=0)
    audit_source_commit_tree_relation_verified: Literal[True] = True
    audit_source_current_bytes_match: Literal[True] = True
    helper_boundary_passed: Literal[True] = True
    candidate_helper_calls: Literal[0] = 0
    candidate_oracle_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    online_job_manifests: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    qa_release_objects: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    production_rows: Literal[0] = 0
    archive_grounding_rows: Literal[0] = 0
    benchmark_distribution_rows: Literal[0] = 0
    semantic_depth_expansion_rows: Literal[0] = 0
    candidate_formal_writes: Literal[0] = 0
    transitive_runtime_closure_claimed: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_independent_scope_audit.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_scope_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentScopeBoundaryAudit:
        self.require_identity("audit_id")
        return self


class IndependentGateEvaluation(Identified):
    gate_id: str = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=8, max_length=8)
    passed: Literal[8] = 8
    failed: Literal[0] = 0
    noncompensatory: Literal[True] = True
    schema_version: str = "qa_generator_source_authority_independent_gate.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_gate:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentGateEvaluation:
        if tuple(self.gates) != GATE_NAMES or not all(self.gates.values()):
            raise ValueError("independent noncompensatory Gate partition differs")
        self.require_identity("gate_id")
        return self


class IndependentAuditDecision(Identified):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    candidate_freeze_audit_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    legacy_counterexample_audit_id: str = Field(min_length=1)
    source_attack_audit_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    depth_attack_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision: Literal[
        "qa_generator_source_commit_tree_member_authority_repair_preflight_independently_confirmed"
    ] = DECISION
    candidate_accepted_as_scoped: Literal[True] = True
    semantic_depth_three_plus_present: Literal[False] = False
    online_generation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_independent_decision.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentAuditDecision:
        self.require_identity("decision_id")
        return self


class IndependentAuditTransition(Identified):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_audit_decision_required: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    online_generation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_independent_transition.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentAuditTransition:
        self.require_identity("transition_id")
        return self


class IndependentAuditReport(Identified):
    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    candidate_freeze_audit_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    git_source_authority_audit_id: str = Field(min_length=1)
    legacy_counterexample_audit_id: str = Field(min_length=1)
    source_attack_audit_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    depth_attack_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    decision: Literal[
        "qa_generator_source_commit_tree_member_authority_repair_preflight_independently_confirmed"
    ] = DECISION
    semantic_operation_depth_distribution: dict[str, int]
    maximum_semantic_operation_depth: Literal[2] = 2
    semantic_depth_three_plus_count: Literal[0] = 0
    deterministic_fixed_fixture_constructibility_only: Literal[True] = True
    archive_grounding_claimed: Literal[False] = False
    benchmark_distribution_claimed: Literal[False] = False
    realistic_difficulty_claimed: Literal[False] = False
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    online_generation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_independent_report.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_report:"

    @model_validator(mode="after")
    def validate_all(self) -> IndependentAuditReport:
        if self.semantic_operation_depth_distribution != {"0": 1, "1": 6, "2": 1}:
            raise ValueError("reported independent semantic-depth distribution differs")
        self.require_identity("report_id")
        return self


class ArtifactManifestMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(Identified):
    manifest_id: str = Field(min_length=1)
    members: tuple[ArtifactManifestMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    member_bytes: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    self_excluding: Literal[True] = True
    schema_version: str = "qa_generator_source_authority_independent_artifact_manifest.v1"

    @classmethod
    def identity_prefix(cls) -> str:
        return "qa_generator_source_authority_independent_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> ArtifactManifest:
        paths = tuple(row.relative_path for row in self.members)
        rows = tuple(row.model_dump(mode="python") for row in self.members)
        body = self.model_dump(mode="python", exclude={"manifest_id"})
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.member_bytes != sum(row.byte_count for row in self.members)
            or self.artifact_root
            != strict_canonical_hash(
                rows, prefix="qa_generator_source_authority_independent_artifact_root:"
            )
            or self.manifest_id
            != strict_canonical_hash(
                body, prefix="qa_generator_source_authority_independent_artifact_manifest:"
            )
        ):
            raise ValueError("independent audit Artifact Manifest differs")
        return self


class QAGeneratorSourceAuthorityIndependentAuditProducts(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    authorization: ExternalIndependentAuditAuthorization
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    candidate_freeze: CandidateFreezeAudit
    detached_rebuild: DetachedRebuildAudit
    git_source_authority_audit: IndependentGitSourceAuthorityAudit
    legacy_counterexample_audit: IndependentLegacyCounterexampleAudit
    source_attack_audit: IndependentSourceAttackAudit
    fixture_audit: IndependentFixtureAudit
    depth_metric_audit: IndependentDepthMetricAudit
    depth_attack_audit: IndependentDepthAttackAudit
    scope_audit: IndependentScopeBoundaryAudit
    gate_evaluation: IndependentGateEvaluation
    decision: IndependentAuditDecision
    transition: IndependentAuditTransition
    report: IndependentAuditReport
