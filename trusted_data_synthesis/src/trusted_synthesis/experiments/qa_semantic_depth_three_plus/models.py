from __future__ import annotations

import hashlib
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.schema import QualityAssessment
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.task.program_depth import ProgramDepthMetrics
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateVerificationReport
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecution

STAGE: Final = "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_only"
NEXT_STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "qa_semantic_operation_depth_three_plus_constructibility_and_two_topology_"
    "coverage_preflight_passed_independent_audit_required"
)
EXTERNAL_AUDIT_SHA256: Final = "944de938075e6cfd68caed049264f77ea096f6db6717b377cae114e1bbddc373"
EXTERNAL_AUDIT_BYTE_COUNT: Final = 16_720
OPERATOR_DIRECTIVE: Final = "参照审计，继续优化修订QA链路"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "4b434b8f9fe07ff38b84d57726ace75e87b619bc2b539e9d5ac0e642b9976263"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 41

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_generator_source_authority_independent_audit/"
    "qa_generator_source_commit_tree_member_authority_and_depth_metric_repair_"
    "preflight_independent_audit_v2_20260904"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_generator_source_authority_independent_artifact_manifest:"
    "3dfccec74ea6dc0e15bac876a2dcddeb7b54e9cbbe70cd6367b17938b4deb701"
)
PREDECESSOR_ARTIFACT_ROOT: Final = (
    "qa_generator_source_authority_independent_artifact_root:"
    "32fae37a0129739b07b816c3d22a7001ff4745cfcd8bf9b8e79dfae39dee65a6"
)
PREDECESSOR_REPORT_ID: Final = (
    "qa_generator_source_authority_independent_report:"
    "98f5e0d25f190e4e00ac48610a2c6b9bf0b2c789c312f2766c1bdb623264be2b"
)
PREDECESSOR_DECISION_ID: Final = (
    "qa_generator_source_authority_independent_decision:"
    "681055cfa397321d48dc0e422e50f907cbd36bd71f6312e27ec7e1a655b51d0d"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "qa_generator_source_authority_independent_transition:"
    "78c7d60d2b8572b45baf4ab7649a9d47fb0cda3503f3b725177287bd0e7a7f8e"
)

CASE_IDS: Final = ("branch_merge_growth_gap", "serial_margin_target_gap")
TASK_TYPES: Final = (
    "derived_growth_absolute_spread",
    "registered_margin_target_gap",
)
TOPOLOGY_KINDS: Final = ("branch_and_merge", "serial_chain")
NEGATIVE_CONTROL_NAMES: Final = (
    "serial_irrelevant_lookup_inflation",
    "serial_semantic_scale_bypass",
    "branch_merge_absolute_bypass",
    "branch_to_serial_topology_substitution",
    "branch_cross_metric_evidence_substitution",
    "fully_rehashed_wrong_answer_and_citation",
    "operation_role_laundering",
)

SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/operations.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/patterns.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/preflight.py",
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


class DepthExpansionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    stage: Literal[
        "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_only"
    ] = STAGE
    external_audit_sha256: Literal[
        "944de938075e6cfd68caed049264f77ea096f6db6717b377cae114e1bbddc373"
    ] = EXTERNAL_AUDIT_SHA256
    external_audit_byte_count: Literal[16720] = EXTERNAL_AUDIT_BYTE_COUNT
    operator_directive: Literal["参照审计，继续优化修订QA链路"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "4b434b8f9fe07ff38b84d57726ace75e87b619bc2b539e9d5ac0e642b9976263"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[41] = OPERATOR_DIRECTIVE_BYTE_COUNT
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    archive_selection_authorized: Literal[False] = False
    benchmark_estimation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_semantic_depth_three_plus_authorization.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> DepthExpansionAuthorization:
        directive = self.operator_directive.encode("utf-8")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"authorization_id"}),
            prefix="qa_semantic_depth_three_plus_authorization:",
        )
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id != expected
        ):
            raise ValueError("semantic-depth Authorization differs")
        return self


class PredecessorFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    directory: str = PREDECESSOR_DIRECTORY
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    manifest_member_count: int = Field(gt=0)
    manifest_member_bytes: int = Field(gt=0)
    manifest_id: str = PREDECESSOR_MANIFEST_ID
    artifact_root: str = PREDECESSOR_ARTIFACT_ROOT
    report_id: str = PREDECESSOR_REPORT_ID
    decision_id: str = PREDECESSOR_DECISION_ID
    transition_id: str = PREDECESSOR_TRANSITION_ID
    prior_semantic_depth_distribution: dict[str, int] = {"0": 1, "1": 6, "2": 1}
    prior_maximum_semantic_depth: Literal[2] = 2
    prior_semantic_depth_three_plus_count: Literal[0] = 0
    formal_bytes_modified: Literal[False] = False
    schema_version: str = "qa_semantic_depth_three_plus_predecessor_freeze.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> PredecessorFreeze:
        if (
            self.file_count != 21
            or self.total_byte_count != 99_487
            or self.manifest_member_count != 20
            or self.manifest_member_bytes != 96_276
            or self.freeze_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"freeze_id"}),
                prefix="qa_semantic_depth_three_plus_predecessor_freeze:",
            )
        ):
            raise ValueError("semantic-depth predecessor Freeze differs")
        return self


class SourceMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    committed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    committed_byte_count: int = Field(gt=0)
    current_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_byte_count: int = Field(gt=0)
    bytes_equal: Literal[True] = True


class SourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    requested_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    resolved_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    requested_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    resolved_tree: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    members: tuple[SourceMember, ...] = Field(min_length=5, max_length=5)
    path_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    commit_tree_relation_verified: Literal[True] = True
    all_current_bytes_equal_committed_bytes: Literal[True] = True
    schema_version: str = "qa_semantic_depth_three_plus_source_binding.v1"

    @model_validator(mode="after")
    def validate_binding(self) -> SourceBinding:
        rows = tuple(item.model_dump(mode="json") for item in self.members)
        if (
            self.requested_commit != self.resolved_commit
            or self.requested_tree != self.resolved_tree
            or tuple(item.relative_path for item in self.members) != SOURCE_PATHS
            or not all(item.bytes_equal for item in self.members)
            or self.path_set_sha256
            != hashlib.sha256(canonical_json_bytes(SOURCE_PATHS)).hexdigest()
            or self.member_set_sha256 != hashlib.sha256(canonical_json_bytes(rows)).hexdigest()
            or self.binding_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"binding_id"}),
                prefix="qa_semantic_depth_three_plus_source_binding:",
            )
        ):
            raise ValueError("semantic-depth source Binding differs")
        return self


class RegistryBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    registry_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_operator_count: int = Field(gt=0)
    extension_operator_ids: tuple[str, ...] = (
        "absolute_percentage_point_gap",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    )
    extension_operator_count: Literal[3] = 3
    all_extension_roles_semantic: Literal[True] = True
    executor_oracle_class_pairs_distinct: Literal[True] = True
    schema_version: str = "qa_semantic_depth_three_plus_registry_binding.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> RegistryBinding:
        if self.binding_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"binding_id"}),
            prefix="qa_semantic_depth_three_plus_registry_binding:",
        ):
            raise ValueError("semantic-depth Registry Binding differs")
        return self


class CoverageRow(FrozenModel):
    row_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    registry_binding_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    topology_kind: Literal["serial_chain", "branch_and_merge"]
    evidence_bundle_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    source_program_id: str = Field(min_length=1)
    source_program_hash: str = Field(min_length=1)
    topology_hash: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    verification_trajectory_id: str = Field(min_length=1)
    assessment_id: str = Field(min_length=1)
    depth_metrics_id: str = Field(min_length=1)
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    semantic_transition_sequence: tuple[str, ...] = Field(min_length=3)
    node_count: int = Field(ge=1)
    edge_count: int = Field(ge=1)
    structural_dependency_depth: int = Field(ge=1)
    semantic_operation_depth: int = Field(ge=3)
    workflow_interaction_depth: int = Field(ge=5)
    source_program_exact: Literal[True] = True
    output_dependency_closed: Literal[True] = True
    program_execution_complete: Literal[True] = True
    independent_node_replay_passed: Literal[True] = True
    answer_schema_correct: Literal[True] = True
    answer_correct: Literal[True] = True
    citation_correct: Literal[True] = True
    evaluator_accepted: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = "qa_semantic_depth_three_plus_coverage_row.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> CoverageRow:
        if (
            self.semantic_operation_depth != 3
            or self.workflow_interaction_depth != 5
            or self.row_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"row_id"}),
                prefix="qa_semantic_depth_three_plus_coverage_row:",
            )
        ):
            raise ValueError("semantic-depth coverage row differs")
        return self


class CoverageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    registry_binding_id: str = Field(min_length=1)
    rows: tuple[CoverageRow, ...] = Field(min_length=2, max_length=2)
    case_count: Literal[2] = 2
    topology_count: Literal[2] = 2
    serial_chain_count: Literal[1] = 1
    branch_and_merge_count: Literal[1] = 1
    semantic_depth_three_plus_count: Literal[2] = 2
    semantic_depth_distribution: dict[str, int] = {"3": 2}
    structural_depth_distribution: dict[str, int] = {"4": 2}
    workflow_depth_distribution: dict[str, int] = {"5": 2}
    complete_execution_count: Literal[2] = 2
    independent_replay_count: Literal[2] = 2
    answer_schema_correct_count: Literal[2] = 2
    answer_correct_count: Literal[2] = 2
    citation_correct_count: Literal[2] = 2
    evaluator_accepted_count: Literal[2] = 2
    insufficient_capability_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = "qa_semantic_depth_three_plus_coverage_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> CoverageAudit:
        if (
            tuple(row.case_id for row in self.rows) != CASE_IDS
            or tuple(sorted({row.task_type for row in self.rows})) != TASK_TYPES
            or tuple(sorted({row.topology_kind for row in self.rows})) != TOPOLOGY_KINDS
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_semantic_depth_three_plus_coverage_audit:",
            )
        ):
            raise ValueError("semantic-depth coverage Audit differs")
        return self


class NegativeControl(FrozenModel):
    name: str = Field(min_length=1)
    rejection_stage: str = Field(min_length=1)
    reason_type: str = Field(min_length=1)
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rejected: Literal[True] = True
    candidate_rehashed: bool
    original_answer_bytes_retained: bool = False
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class NegativeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=7, max_length=7)
    attempted_count: Literal[7] = 7
    rejected_count: Literal[7] = 7
    accepted_count: Literal[0] = 0
    candidate_rehashed_count: int = Field(ge=1)
    original_answer_bytes_retained_count: int = Field(ge=1)
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = "qa_semantic_depth_three_plus_negative_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeAudit:
        if (
            tuple(item.name for item in self.controls) != NEGATIVE_CONTROL_NAMES
            or self.candidate_rehashed_count
            != sum(item.candidate_rehashed for item in self.controls)
            or self.original_answer_bytes_retained_count
            != sum(item.original_answer_bytes_retained for item in self.controls)
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_semantic_depth_three_plus_negative_audit:",
            )
        ):
            raise ValueError("semantic-depth negative Audit differs")
        return self


class ScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    coverage_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    archive_selections: Literal[0] = 0
    benchmark_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    online_job_manifests: Literal[0] = 0
    qa_release_objects: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    production_rows: Literal[0] = 0
    existing_registered_catalog_modified: Literal[False] = False
    predecessor_formal_bytes_modified: Literal[False] = False
    claim_is_constructibility_only: Literal[True] = True
    schema_version: str = "qa_semantic_depth_three_plus_scope_audit.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> ScopeAudit:
        if self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_semantic_depth_three_plus_scope_audit:",
        ):
            raise ValueError("semantic-depth Scope Audit differs")
        return self


class GateEvaluation(FrozenModel):
    gate_id: str = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True
    schema_version: str = "qa_semantic_depth_three_plus_gate.v1"

    @model_validator(mode="after")
    def validate_gate(self) -> GateEvaluation:
        if (
            len(self.gates) != 8
            or not all(self.gates.values())
            or self.gate_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"gate_id"}),
                prefix="qa_semantic_depth_three_plus_gate:",
            )
        ):
            raise ValueError("semantic-depth Gate differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision: Literal[
        "qa_semantic_operation_depth_three_plus_constructibility_and_two_topology_"
        "coverage_preflight_passed_independent_audit_required"
    ] = DECISION
    semantic_depth_three_plus_constructible: Literal[True] = True
    minimum_topology_coverage_closed: Literal[True] = True
    archive_grounding_established: Literal[False] = False
    benchmark_distribution_established: Literal[False] = False
    release_eligibility_established: Literal[False] = False
    schema_version: str = "qa_semantic_depth_three_plus_decision.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> Decision:
        if self.decision_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"decision_id"}),
            prefix="qa_semantic_depth_three_plus_decision:",
        ):
            raise ValueError("semantic-depth Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_"
        "preflight_independent_audit_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    archive_selection_authorized: Literal[False] = False
    benchmark_estimation_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    schema_version: str = "qa_semantic_depth_three_plus_transition.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> Transition:
        if self.transition_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"transition_id"}),
            prefix="qa_semantic_depth_three_plus_transition:",
        ):
            raise ValueError("semantic-depth Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    registry_binding_id: str = Field(min_length=1)
    coverage_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: str = DECISION
    exact_case_count: Literal[2] = 2
    exact_topology_count: Literal[2] = 2
    semantic_depth_distribution: dict[str, int] = {"3": 2}
    provider_calls: Literal[0] = 0
    scope_claim: Literal[
        "deterministic_fixture_constructibility_not_archive_or_benchmark_coverage"
    ] = "deterministic_fixture_constructibility_not_archive_or_benchmark_coverage"
    schema_version: str = "qa_semantic_depth_three_plus_report.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> Report:
        if self.report_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"report_id"}),
            prefix="qa_semantic_depth_three_plus_report:",
        ):
            raise ValueError("semantic-depth Report differs")
        return self


class Products(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    authorization: DepthExpansionAuthorization
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    predecessor_freeze: PredecessorFreeze
    source_binding: SourceBinding
    registry_binding: RegistryBinding
    coverage_audit: CoverageAudit
    negative_audit: NegativeAudit
    scope_audit: ScopeAudit
    gate: GateEvaluation
    decision: Decision
    transition: Transition
    report: Report
    bundles: tuple[EvidenceBundle, ...]
    packages: tuple[RealizedTaskPackage, ...]
    executions: tuple[PublicPlanCandidateExecution, ...]
    verification_reports: tuple[CandidateVerificationReport, ...]
    assessments: tuple[QualityAssessment, ...]
    depth_metrics: tuple[ProgramDepthMetrics, ...]
