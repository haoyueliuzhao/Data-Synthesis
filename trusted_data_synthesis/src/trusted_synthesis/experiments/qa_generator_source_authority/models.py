from __future__ import annotations

import hashlib
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from .depth import DepthMetricContract, DepthMetricContractAudit, DepthNegativeControlAudit

STAGE: Final = "qa_generator_source_commit_tree_member_authority_repair_preflight_only"
NEXT_STAGE: Final = (
    "qa_generator_source_commit_tree_member_authority_repair_preflight_independent_audit_only"
)
DECISION: Final = (
    "qa_generator_source_commit_tree_member_authority_repair_preflight_passed_"
    "independent_audit_required"
)
EXTERNAL_AUDIT_SHA256: Final = "118445beed3d77d53cd66b8d1cb4594c4111b7bfd430f6d3ed2360ba01b65033"
EXTERNAL_AUDIT_BYTE_COUNT: Final = 21_798
OPERATOR_DIRECTIVE: Final = "参照审计继续修订优化QA合成链路"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "d7312594a41e3ad1ca523fd87399cc52205bc6c63e9d81bd8552754d916c7fa7"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 44

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
REPAIR_IMPLEMENTATION_PATHS: Final = (
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
SOURCE_ATTACK_NAMES: Final = (
    "nonexistent_commit",
    "real_commit_wrong_tree",
    "changed_source_member",
    "crossed_source_members",
    "uncommitted_worktree_source",
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
PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_generator_totality/"
    "qa_registered_task_catalog_generator_verifier_execution_totality_"
    "preflight_v1_20260904"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_generator_totality_artifact_manifest:"
    "d8c7ce9ad3ea97a15aaeaf170f8680359e88dffbbf045f3e1ddda294c6c17853"
)
PREDECESSOR_ARTIFACT_ROOT: Final = (
    "qa_generator_totality_artifact_root:"
    "f2d08a0b4eb35b51b65a901bddb7ce794b2357bced0e6673d819ccf05bcf63db"
)
PREDECESSOR_REPORT_ID: Final = (
    "qa_generator_totality_report:595e1166ebcbdeb4e9f924a562cad65b540237332ebe3ca158e9a797677d23ee"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "qa_generator_totality_transition:"
    "dbfddcc94d86907c9120b71dacfd4e85a1f0d5d66020f94307e5af75a1d3e642"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identified(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    draft = model_type.model_construct(**{field: "pending", **values})
    return model_type(
        **{
            field: strict_canonical_hash(
                draft.model_dump(mode="python", exclude={field}), prefix=prefix
            ),
            **values,
        }
    )


class SourceAuthorityAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    stage: Literal["qa_generator_source_commit_tree_member_authority_repair_preflight_only"] = STAGE
    external_audit_sha256: Literal[
        "118445beed3d77d53cd66b8d1cb4594c4111b7bfd430f6d3ed2360ba01b65033"
    ] = EXTERNAL_AUDIT_SHA256
    external_audit_byte_count: Literal[21798] = EXTERNAL_AUDIT_BYTE_COUNT
    operator_directive: Literal["参照审计继续修订优化QA合成链路"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "d7312594a41e3ad1ca523fd87399cc52205bc6c63e9d81bd8552754d916c7fa7"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[44] = OPERATOR_DIRECTIVE_BYTE_COUNT
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_authorization.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> SourceAuthorityAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"authorization_id"}),
                prefix="qa_generator_source_authority_authorization:",
            )
        ):
            raise ValueError("QA source-authority Authorization differs")
        return self


class PredecessorFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    directory: Literal[
        "trusted_data_synthesis/artifacts/qa_generator_totality/"
        "qa_registered_task_catalog_generator_verifier_execution_totality_"
        "preflight_v1_20260904"
    ] = PREDECESSOR_DIRECTORY
    file_count: Literal[19] = 19
    total_byte_count: Literal[449574] = 449_574
    manifest_member_count: Literal[18] = 18
    manifest_member_bytes: Literal[446741] = 446_741
    manifest_id: Literal[
        "qa_generator_totality_artifact_manifest:"
        "d8c7ce9ad3ea97a15aaeaf170f8680359e88dffbbf045f3e1ddda294c6c17853"
    ] = PREDECESSOR_MANIFEST_ID
    artifact_root: Literal[
        "qa_generator_totality_artifact_root:"
        "f2d08a0b4eb35b51b65a901bddb7ce794b2357bced0e6673d819ccf05bcf63db"
    ] = PREDECESSOR_ARTIFACT_ROOT
    report_id: Literal[
        "qa_generator_totality_report:"
        "595e1166ebcbdeb4e9f924a562cad65b540237332ebe3ca158e9a797677d23ee"
    ] = PREDECESSOR_REPORT_ID
    transition_id: Literal[
        "qa_generator_totality_transition:"
        "dbfddcc94d86907c9120b71dacfd4e85a1f0d5d66020f94307e5af75a1d3e642"
    ] = PREDECESSOR_TRANSITION_ID
    formal_bytes_modified: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_predecessor_freeze.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> PredecessorFreeze:
        if self.freeze_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"freeze_id"}),
            prefix="qa_generator_source_authority_predecessor_freeze:",
        ):
            raise ValueError("QA totality predecessor Freeze identity differs")
        return self


class SourceMemberBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    committed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    committed_byte_count: int = Field(gt=0)
    current_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_byte_count: int = Field(gt=0)
    bytes_equal: Literal[True] = True

    @model_validator(mode="after")
    def validate_equality(self) -> SourceMemberBinding:
        if (
            self.committed_sha256 != self.current_sha256
            or self.committed_byte_count != self.current_byte_count
        ):
            raise ValueError("committed and current source-member evidence differs")
        return self


class AuthoritativeSourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authority_kind: Literal["generator_verifier", "repair_implementation"]
    requested_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    resolved_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    requested_source_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    resolved_source_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    source_files: tuple[SourceMemberBinding, ...]
    source_path_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_file_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    commit_object_type: Literal["commit"] = "commit"
    commit_tree_relation_verified: Literal[True] = True
    all_members_exist_at_commit: Literal[True] = True
    all_current_bytes_equal_committed_bytes: Literal[True] = True
    schema_version: str = "qa_generator_authoritative_source_binding.v1"

    @model_validator(mode="after")
    def validate_binding(self) -> AuthoritativeSourceBinding:
        expected = (
            GENERATOR_SOURCE_PATHS
            if self.authority_kind == "generator_verifier"
            else REPAIR_IMPLEMENTATION_PATHS
        )
        rows = tuple(item.model_dump(mode="json") for item in self.source_files)
        if (
            self.requested_source_commit != self.resolved_source_commit
            or self.requested_source_tree != self.resolved_source_tree
            or tuple(item.relative_path for item in self.source_files) != expected
            or not all(item.bytes_equal for item in self.source_files)
            or self.source_path_set_sha256
            != hashlib.sha256(canonical_json_bytes(expected)).hexdigest()
            or self.source_file_set_sha256 != hashlib.sha256(canonical_json_bytes(rows)).hexdigest()
            or self.binding_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"binding_id"}),
                prefix="qa_generator_authoritative_source_binding:",
            )
        ):
            raise ValueError("authoritative Git source Binding differs")
        return self


class LegacySourceCounterexampleAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    legacy_binding_id: str = Field(min_length=1)
    fake_source_commit: Literal["0000000000000000000000000000000000000000"] = (
        "0000000000000000000000000000000000000000"
    )
    unrelated_source_tree: Literal["1111111111111111111111111111111111111111"] = (
        "1111111111111111111111111111111111111111"
    )
    legacy_binding_constructed: Literal[True] = True
    legacy_self_declared_source_bound: Literal[True] = True
    legacy_self_declared_catalog_totalized: Literal[True] = True
    legacy_g2_passed: Literal[True] = True
    new_authority_admission_rejected: Literal[True] = True
    rejection_stage: Literal["git_commit_resolution"] = "git_commit_resolution"
    exception_type: str = Field(min_length=1)
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = "qa_generator_legacy_source_counterexample_audit.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> LegacySourceCounterexampleAudit:
        if self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_generator_legacy_source_counterexample_audit:",
        ):
            raise ValueError("legacy source Counterexample Audit identity differs")
        return self


class SourceAuthorityNegativeControl(FrozenModel):
    name: str = Field(min_length=1)
    rejected: bool
    rejection_stage: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class SourceAuthorityNegativeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    generator_source_binding_id: str = Field(min_length=1)
    repair_source_binding_id: str = Field(min_length=1)
    controls: tuple[SourceAuthorityNegativeControl, ...] = Field(min_length=5, max_length=5)
    attempted_count: Literal[5] = 5
    rejected_count: Literal[5] = 5
    accepted_count: Literal[0] = 0
    output_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = "qa_generator_source_authority_negative_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> SourceAuthorityNegativeAudit:
        if (
            tuple(item.name for item in self.controls) != SOURCE_ATTACK_NAMES
            or not all(item.rejected for item in self.controls)
            or self.rejected_count != sum(item.rejected for item in self.controls)
            or self.accepted_count != sum(not item.rejected for item in self.controls)
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_generator_source_authority_negative_audit:",
            )
        ):
            raise ValueError("source-authority Negative Audit differs")
        return self


class RetainedFixtureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    generator_source_binding_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    evidence_bundle_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    public_plan_execution_id: str = Field(min_length=1)
    program_node_count: int = Field(ge=1)
    structural_dependency_depth: int = Field(ge=1)
    executed_node_count: int = Field(ge=1)
    independently_replayed_node_count: int = Field(ge=1)
    generator_succeeded: Literal[True] = True
    insufficient_capability: Literal[False] = False
    operation_correct: Literal[True] = True
    answer_schema_correct: Literal[True] = True
    answer_correct: Literal[True] = True
    citation_correct: Literal[True] = True
    evaluator_accepted: Literal[True] = True

    @model_validator(mode="after")
    def validate_identity(self) -> RetainedFixtureRow:
        if (
            self.task_type not in REGISTERED_TASK_TYPES
            or self.executed_node_count != self.program_node_count
            or self.independently_replayed_node_count != self.program_node_count
            or self.row_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"row_id"}),
                prefix="qa_generator_source_authority_retained_fixture_row:",
            )
        ):
            raise ValueError("retained fixed-fixture Row differs")
        return self


class RetainedFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    generator_source_binding_id: str = Field(min_length=1)
    rows: tuple[RetainedFixtureRow, ...] = Field(min_length=8, max_length=8)
    registered_task_types: tuple[str, ...] = REGISTERED_TASK_TYPES
    registered_task_count: Literal[8] = 8
    generator_success_count: Literal[8] = 8
    exact_program_execution_count: Literal[8] = 8
    exact_operation_correctness_count: Literal[8] = 8
    answer_schema_correct_count: Literal[8] = 8
    answer_correct_count: Literal[8] = 8
    citation_correct_count: Literal[8] = 8
    evaluator_accepted_count: Literal[8] = 8
    insufficient_capability_count: Literal[0] = 0
    deterministic_fixture_constructibility_only: Literal[True] = True
    archive_grounding_claimed: Literal[False] = False
    realistic_difficulty_claimed: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_retained_fixture_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> RetainedFixtureAudit:
        if (
            tuple(item.task_type for item in self.rows) != REGISTERED_TASK_TYPES
            or self.generator_success_count != sum(item.generator_succeeded for item in self.rows)
            or self.exact_operation_correctness_count
            != sum(item.operation_correct for item in self.rows)
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_generator_source_authority_retained_fixture_audit:",
            )
        ):
            raise ValueError("retained fixed-fixture Audit differs")
        return self


class SourceAuthorityScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    generator_source_binding_id: str = Field(min_length=1)
    repair_source_binding_id: str = Field(min_length=1)
    retained_fixture_audit_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    depth_negative_audit_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    online_job_manifests: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    qa_release_objects: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    production_rows: Literal[0] = 0
    schema_version: str = "qa_generator_source_authority_scope_audit.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> SourceAuthorityScopeAudit:
        if self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_generator_source_authority_scope_audit:",
        ):
            raise ValueError("source-authority Scope Audit identity differs")
        return self


class SourceAuthorityRepairReport(FrozenModel):
    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    generator_source_binding_id: str = Field(min_length=1)
    repair_source_binding_id: str = Field(min_length=1)
    legacy_counterexample_audit_id: str = Field(min_length=1)
    source_negative_audit_id: str = Field(min_length=1)
    retained_fixture_audit_id: str = Field(min_length=1)
    depth_contract_id: str = Field(min_length=1)
    depth_metric_audit_id: str = Field(min_length=1)
    depth_negative_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    decision: Literal[
        "qa_generator_source_commit_tree_member_authority_repair_preflight_passed_"
        "independent_audit_required"
    ] = DECISION
    next_stage: Literal[
        "qa_generator_source_commit_tree_member_authority_repair_preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    archive_grounding_claimed: Literal[False] = False
    semantic_depth_three_plus_claimed: Literal[False] = False
    realistic_difficulty_claimed: Literal[False] = False
    schema_version: str = "qa_generator_source_authority_repair_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> SourceAuthorityRepairReport:
        if (
            len(self.gates) != 8
            or not all(self.gates.values())
            or self.report_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"report_id"}),
                prefix="qa_generator_source_authority_repair_report:",
            )
        ):
            raise ValueError("source-authority Repair Report differs")
        return self


class QAGeneratorSourceAuthorityProducts(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    authorization: SourceAuthorityAuthorization
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    predecessor_freeze: PredecessorFreeze
    generator_source_binding: AuthoritativeSourceBinding
    repair_source_binding: AuthoritativeSourceBinding
    legacy_counterexample_audit: LegacySourceCounterexampleAudit
    source_negative_audit: SourceAuthorityNegativeAudit
    retained_fixture_audit: RetainedFixtureAudit
    depth_contract: DepthMetricContract
    depth_metric_audit: DepthMetricContractAudit
    depth_negative_audit: DepthNegativeControlAudit
    scope_audit: SourceAuthorityScopeAudit
    report: SourceAuthorityRepairReport
    bundles: tuple[Any, ...]
    realized_packages: tuple[Any, ...]
    executions: tuple[Any, ...]
    trajectories: tuple[Any, ...]
    verification_reports: tuple[Any, ...]
    assessments: tuple[Any, ...]
