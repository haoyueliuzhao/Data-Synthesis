from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateVerificationReport,
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.public_plan_executor import (
    PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID,
    PublicPlanCandidateExecution,
    PublicPlanCandidateExecutor,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.qa_semantic_coverage import preflight as coverage
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import EvidenceToolRuntime, InMemoryEvidenceToolRuntime

STAGE: Final = (
    "qa_registered_task_catalog_to_generator_and_verifier_execution_totality_preflight_only"
)
NEXT_STAGE: Final = (
    "qa_registered_task_catalog_to_generator_and_verifier_execution_totality_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "qa_registered_eight_task_catalog_generator_verifier_evaluator_totality_"
    "preflight_passed_independent_audit_required"
)
EXTERNAL_AUDIT_SHA256: Final = "c293ab051e7c03e7b0ae49a13950f4faf9af2901c171bfb8d1abff505966f776"
EXTERNAL_AUDIT_BYTE_COUNT: Final = 20_012
OPERATOR_DIRECTIVE_SHA256: Final = (
    "f60f8ab4fd802017b839ee43839d44c85e4a8cc064e016856ca399a3436c9cda"
)
OPERATOR_DIRECTIVE: Final = "并行开展QA合成链路优化"
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 32
GENERATOR_VERSION: Final = "finance_numeric_candidate_totality.v1"
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
PROGRAM_NODE_COUNTS: Final = {
    "comparison": 1,
    "derived_growth_comparison": 7,
    "fact_retrieval": 1,
    "registered_cross_metric_comparison": 1,
    "registered_ratio": 3,
    "temporal_absolute_change": 3,
    "temporal_average": 4,
    "temporal_growth": 3,
}
DEPENDENCY_DEPTHS: Final = {
    "comparison": 1,
    "derived_growth_comparison": 3,
    "fact_retrieval": 1,
    "registered_cross_metric_comparison": 1,
    "registered_ratio": 2,
    "temporal_absolute_change": 2,
    "temporal_average": 2,
    "temporal_growth": 2,
}
REPAIRED_TASK_TYPES: Final = (
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
)
NEGATIVE_CONTROL_NAMES: Final = (
    "unregistered_ratio_pair_substitution",
    "zero_denominator_evidence_substitution",
    "temporal_order_substitution",
    "derived_growth_cross_entity_substitution",
    "program_parameter_substitution",
    "fully_rehashed_wrong_answer_and_citation",
)
SOURCE_PATHS: Final = (
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
BASELINE_QA_DIRECTORY: Final = coverage.BASELINE_DIRECTORY
FORMAL_QA_COVERAGE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_coverage/"
    "offline_qa_semantic_type_coverage_program_depth_closure_v1_20260903"
)
BASELINE_QA_MANIFEST_ID: Final = coverage.BASELINE_MANIFEST_ID
BASELINE_QA_ARTIFACT_ROOT: Final = coverage.BASELINE_ARTIFACT_ROOT
FORMAL_QA_ARTIFACT_MANIFEST_ID: Final = (
    "offline_qa_semantic_coverage_artifact_manifest:"
    "b5b83ba05cc59ad723620ec7ff672e069f9eb938ce3d53eb611faea2b091ca6b"
)
FORMAL_QA_ARTIFACT_ROOT: Final = (
    "offline_qa_semantic_coverage_artifact_root:"
    "a34e87e38ccdf06e1a4eb9941eaae91d96ccc522f963626d90f1b5ad6758f8ba"
)
FORMAL_QA_ROW_MANIFEST_ID: Final = (
    "offline_qa_semantic_coverage_row_manifest:"
    "5967b1e2d803f554d53fbc2bf6ffc372172d234c95010b59cfa87114d673c687"
)
FORMAL_QA_DECISION_ID: Final = (
    "offline_qa_semantic_coverage_decision:"
    "d1d01104cf54810d5407717de762233eedfd752ff64cf42997a85996b0c69060"
)
FORMAL_QA_TRANSITION_ID: Final = (
    "offline_qa_semantic_coverage_transition:"
    "1bf08f075b2bf6ffa45b83b4175cfba80c525e57df57a69e6d53e0a515d1f924"
)

GENERATOR_CONTRACT_ID: Final = canonical_hash(
    {
        "implementation": "FinanceNumericCandidateGenerator.v7_source_bound_adapter",
        "base_generator_contract_id": FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        "public_plan_executor_contract_id": PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID,
        "input_interface": "TaskPublicSpec+EvidenceToolRuntime",
        "source_authority": "RealizedTaskPackage+BindingSnapshot+EvidenceCorpus",
        "registered_task_types": REGISTERED_TASK_TYPES,
        "execution": "registry_topological_complete",
        "version": GENERATOR_VERSION,
    },
    prefix="finance_numeric_candidate_totality_contract:",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExactFileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class QARevisionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    stage: Literal[
        "qa_registered_task_catalog_to_generator_and_verifier_execution_totality_preflight_only"
    ] = STAGE
    external_audit_sha256: Literal[
        "c293ab051e7c03e7b0ae49a13950f4faf9af2901c171bfb8d1abff505966f776"
    ] = EXTERNAL_AUDIT_SHA256
    external_audit_byte_count: Literal[20012] = EXTERNAL_AUDIT_BYTE_COUNT
    operator_directive_sha256: Literal[
        "f60f8ab4fd802017b839ee43839d44c85e4a8cc064e016856ca399a3436c9cda"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive: Literal["并行开展QA合成链路优化"] = OPERATOR_DIRECTIVE
    operator_directive_byte_count: Literal[32] = OPERATOR_DIRECTIVE_BYTE_COUNT
    exact_registered_task_count: Literal[8] = 8
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    vtdo_integration_authorized: Literal[False] = False
    schema_version: str = "qa_generator_totality_authorization.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> QARevisionAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.authorization_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"authorization_id"}),
                prefix="qa_generator_totality_authorization:",
            )
        ):
            raise ValueError("QA totality Authorization identity differs")
        return self


class GeneratorSourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    base_generator_contract_id: str = FINANCE_NUMERIC_GENERATOR_CONTRACT_ID
    totality_generator_contract_id: str = GENERATOR_CONTRACT_ID
    public_plan_executor_contract_id: str = PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_files: tuple[ExactFileBinding, ...] = Field(min_length=14, max_length=14)
    source_file_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finance_numeric_candidate_v7_source_bound: Literal[True] = True
    registered_catalog_totalized: Literal[True] = True
    schema_version: str = "qa_generator_totality_source_binding.v1"

    @model_validator(mode="after")
    def validate_binding(self) -> GeneratorSourceBinding:
        rows = tuple(item.model_dump(mode="json") for item in self.source_files)
        if (
            tuple(item.relative_path for item in self.source_files) != SOURCE_PATHS
            or self.source_file_set_sha256 != hashlib.sha256(canonical_json_bytes(rows)).hexdigest()
            or self.binding_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"binding_id"}),
                prefix="qa_generator_totality_source_binding:",
            )
        ):
            raise ValueError("QA totality Source Binding differs")
        return self


class BaselineQAScopeFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    baseline_directory: Literal[
        "trusted_data_synthesis/artifacts/qa_realization_vnext/"
        "future_qa_candidate_population_v2_20260901"
    ] = BASELINE_QA_DIRECTORY
    baseline_file_count: Literal[18] = 18
    baseline_total_byte_count: Literal[1233274] = 1_233_274
    baseline_manifest_member_count: Literal[17] = 17
    baseline_candidate_manifest_id: Literal[
        "future_qa_preoutcome_candidate_manifest:"
        "18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad"
    ] = BASELINE_QA_MANIFEST_ID
    baseline_artifact_root: Literal[
        "future_qa_candidate_artifact_root:"
        "9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04"
    ] = BASELINE_QA_ARTIFACT_ROOT
    formal_directory: Literal[
        "trusted_data_synthesis/artifacts/qa_semantic_coverage/"
        "offline_qa_semantic_type_coverage_program_depth_closure_v1_20260903"
    ] = FORMAL_QA_COVERAGE_DIRECTORY
    formal_file_count: Literal[17] = 17
    formal_total_byte_count: Literal[810715] = 810_715
    formal_manifest_member_count: Literal[16] = 16
    formal_artifact_manifest_id: Literal[
        "offline_qa_semantic_coverage_artifact_manifest:"
        "b5b83ba05cc59ad723620ec7ff672e069f9eb938ce3d53eb611faea2b091ca6b"
    ] = FORMAL_QA_ARTIFACT_MANIFEST_ID
    formal_artifact_root: Literal[
        "offline_qa_semantic_coverage_artifact_root:"
        "a34e87e38ccdf06e1a4eb9941eaae91d96ccc522f963626d90f1b5ad6758f8ba"
    ] = FORMAL_QA_ARTIFACT_ROOT
    formal_row_manifest_id: Literal[
        "offline_qa_semantic_coverage_row_manifest:"
        "5967b1e2d803f554d53fbc2bf6ffc372172d234c95010b59cfa87114d673c687"
    ] = FORMAL_QA_ROW_MANIFEST_ID
    formal_decision_id: Literal[
        "offline_qa_semantic_coverage_decision:"
        "d1d01104cf54810d5407717de762233eedfd752ff64cf42997a85996b0c69060"
    ] = FORMAL_QA_DECISION_ID
    formal_transition_id: Literal[
        "offline_qa_semantic_coverage_transition:"
        "1bf08f075b2bf6ffa45b83b4175cfba80c525e57df57a69e6d53e0a515d1f924"
    ] = FORMAL_QA_TRANSITION_ID
    documentation_old_id_status: Literal["post_freeze_erratum_only"] = "post_freeze_erratum_only"
    formal_json_is_authority: Literal[True] = True
    formal_json_authority_modified: Literal[False] = False
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    release_objects: Literal[0] = 0
    schema_version: str = "qa_generator_totality_baseline_scope_freeze.v1"

    @model_validator(mode="after")
    def validate_freeze(self) -> BaselineQAScopeFreeze:
        if self.freeze_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"freeze_id"}),
            prefix="qa_generator_totality_baseline_scope_freeze:",
        ):
            raise ValueError("QA baseline Scope Freeze identity differs")
        return self


class TotalityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    evidence_bundle_id: str = Field(min_length=1)
    proof_graph_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    semantic_plan_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    public_plan_execution_id: str = Field(min_length=1)
    verification_trajectory_id: str = Field(min_length=1)
    assessment_id: str = Field(min_length=1)
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    program_node_count: int = Field(ge=1)
    maximum_dependency_depth: int = Field(ge=1)
    workflow_action_count: int = Field(ge=1)
    retrieved_evidence_count: int = Field(ge=1)
    selected_evidence_count: int = Field(ge=1)
    executed_program_node_count: int = Field(ge=1)
    grounded_operation_count: int = Field(ge=1)
    independently_replayed_node_count: int = Field(ge=1)
    generator_succeeded: Literal[True] = True
    insufficient_capability: Literal[False] = False
    exact_program_node_execution_coverage: Literal[True] = True
    exact_operation_correctness: Literal[True] = True
    answer_schema_correct: Literal[True] = True
    answer_correct: Literal[True] = True
    citation_correct: Literal[True] = True
    evaluator_accepted: Literal[True] = True
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = "qa_generator_totality_row.v1"

    @model_validator(mode="after")
    def validate_row(self) -> TotalityRow:
        if (
            self.task_type not in REGISTERED_TASK_TYPES
            or self.program_node_count != PROGRAM_NODE_COUNTS[self.task_type]
            or self.maximum_dependency_depth != DEPENDENCY_DEPTHS[self.task_type]
            or self.executed_program_node_count != self.program_node_count
            or self.grounded_operation_count != self.program_node_count
            or self.independently_replayed_node_count != self.program_node_count
            or self.row_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"row_id"}),
                prefix="qa_generator_totality_row:",
            )
        ):
            raise ValueError("QA totality Row differs")
        return self


class GeneratorTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    rows: tuple[TotalityRow, ...] = Field(min_length=8, max_length=8)
    registered_task_types: tuple[str, ...] = REGISTERED_TASK_TYPES
    registered_task_count: Literal[8] = 8
    successful_generator_branch_count: Literal[8] = 8
    insufficient_capability_count: Literal[0] = 0
    exact_program_execution_count: Literal[8] = 8
    exact_operation_correctness_count: Literal[8] = 8
    answer_schema_correct_count: Literal[8] = 8
    answer_correct_count: Literal[8] = 8
    citation_correct_count: Literal[8] = 8
    evaluator_accepted_count: Literal[8] = 8
    program_node_count_distribution: dict[str, int]
    maximum_dependency_depth_distribution: dict[str, int]
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = "qa_generator_totality_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> GeneratorTotalityAudit:
        if (
            self.registered_task_types != REGISTERED_TASK_TYPES
            or tuple(item.task_type for item in self.rows) != REGISTERED_TASK_TYPES
            or self.program_node_count_distribution != {"1": 3, "3": 3, "4": 1, "7": 1}
            or self.maximum_dependency_depth_distribution != {"1": 3, "2": 4, "3": 1}
            or self.audit_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"audit_id"}),
                prefix="qa_generator_totality_audit:",
            )
        ):
            raise ValueError("QA generator totality Audit differs")
        return self


class NegativeControl(FrozenModel):
    name: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: str = Field(min_length=1)
    output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=6, max_length=6)
    attempted_count: Literal[6] = 6
    rejected_count: Literal[6] = 6
    accepted_count: Literal[0] = 0
    output_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = "qa_generator_totality_negative_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if tuple(
            item.name for item in self.controls
        ) != NEGATIVE_CONTROL_NAMES or self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_generator_totality_negative_audit:",
        ):
            raise ValueError("QA totality Negative Audit differs")
        return self


class ScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    totality_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    canonical_case_count: Literal[8] = 8
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    online_job_manifests: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    qa_release_objects: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    production_rows: Literal[0] = 0
    schema_version: str = "qa_generator_totality_scope_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeAudit:
        if self.audit_id != strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="qa_generator_totality_scope_audit:",
        ):
            raise ValueError("QA totality Scope Audit differs")
        return self


class QAGeneratorTotalityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    baseline_scope_freeze_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    totality_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    decision: Literal[
        "qa_registered_eight_task_catalog_generator_verifier_evaluator_totality_preflight_passed_independent_audit_required"
    ] = DECISION
    next_stage: Literal[
        "qa_registered_task_catalog_to_generator_and_verifier_execution_totality_preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    gpu_execution_authorized: Literal[False] = False
    qa_release_authorized: Literal[False] = False
    archive_grounding_claimed: Literal[False] = False
    realistic_difficulty_claimed: Literal[False] = False
    schema_version: str = "qa_generator_totality_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> QAGeneratorTotalityReport:
        if (
            len(self.gates) != 8
            or not all(self.gates.values())
            or self.report_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"report_id"}),
                prefix="qa_generator_totality_report:",
            )
        ):
            raise ValueError("QA generator totality Report differs")
        return self


class QAGeneratorTotalityProducts(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    authorization: QARevisionAuthorization
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    baseline_scope_freeze: BaselineQAScopeFreeze
    source_binding: GeneratorSourceBinding
    totality_audit: GeneratorTotalityAudit
    negative_audit: NegativeControlAudit
    scope_audit: ScopeAudit
    report: QAGeneratorTotalityReport
    bundles: tuple[EvidenceBundle, ...]
    realized_packages: tuple[RealizedTaskPackage, ...]
    executions: tuple[PublicPlanCandidateExecution, ...]
    trajectories: tuple[Trajectory, ...]
    verification_reports: tuple[CandidateVerificationReport, ...]
    assessments: tuple[QualityAssessment, ...]


class FinanceNumericCandidateGeneratorTotality(FinanceNumericCandidateGenerator):
    """Bind the v7 generator to one exact package, then independently replay it."""

    def __init__(
        self,
        *,
        realized: RealizedTaskPackage,
        corpus: EvidenceCorpus,
        registry: OperationRegistry,
    ) -> None:
        self._realized = realized
        self._corpus = corpus
        self._independent_executor = PublicPlanCandidateExecutor(registry)
        self._generator = FinanceNumericCandidateGenerator()
        self.last_execution: PublicPlanCandidateExecution | None = None

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        if task != self._realized.task.public:
            raise ValueError("totality generator public Task differs from its source package")
        retrieved = runtime.search(task.retrieval_scope)
        exact = tuple(self._corpus.evidence)
        observed = tuple(
            (
                item.evidence_id,
                item.evidence_version_id,
                item.provenance.source_record_id,
                canonical_hash(item, prefix="qa_totality_bound_evidence:"),
            )
            for item in retrieved
        )
        expected = tuple(
            (
                item.evidence_id,
                item.evidence_version_id,
                item.provenance.source_record_id,
                canonical_hash(item, prefix="qa_totality_bound_evidence:"),
            )
            for item in exact
        )
        if observed != expected:
            raise ValueError("totality generator retrieved Evidence differs from bound Corpus")
        trajectory = self._generator.generate(task, runtime)
        execution = self._independent_executor.generate(self._realized, self._corpus)
        self.last_execution = execution
        if trajectory.final_answer.get("result", {}).get("status") == "insufficient_capability":
            raise ValueError("legal registered task reached insufficient_capability")
        if (
            trajectory.program_execution != execution.program_execution.model_dump(mode="json")
            or trajectory.final_answer.get("result")
            != execution.trajectory.final_answer.get("result")
            or {item["evidence_id"] for item in trajectory.final_answer.get("citations", ())}
            != {
                item["evidence_id"]
                for item in execution.trajectory.final_answer.get("citations", ())
            }
        ):
            raise ValueError("v7 generator differs from independent public-Plan replay")
        return trajectory


class _StaticRuntime:
    def __init__(self, values: tuple[EvidenceItem, ...]) -> None:
        self.values = values

    def search(self, retrieval_scope: dict[str, object]) -> tuple[EvidenceItem, ...]:
        del retrieval_scope
        return self.values


def _identified(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    draft = model_type.model_construct(**{field: "pending", **values})
    return model_type(
        **{
            field: strict_canonical_hash(
                draft.model_dump(mode="python", exclude={field}), prefix=prefix
            ),
            **values,
        }
    )


def _source_binding(
    root: Path,
    authorization_id: str,
    source_commit: str,
    source_tree: str,
) -> GeneratorSourceBinding:
    files = tuple(
        ExactFileBinding(
            relative_path=relative_path,
            sha256=hashlib.sha256((root / relative_path).read_bytes()).hexdigest(),
            byte_count=(root / relative_path).stat().st_size,
        )
        for relative_path in SOURCE_PATHS
    )
    return _identified(
        GeneratorSourceBinding,
        {
            "authorization_id": authorization_id,
            "source_commit": source_commit,
            "source_tree": source_tree,
            "source_files": files,
            "source_file_set_sha256": hashlib.sha256(
                canonical_json_bytes(tuple(item.model_dump(mode="json") for item in files))
            ).hexdigest(),
        },
        "binding_id",
        "qa_generator_totality_source_binding:",
    )


def _directory_files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _validate_self_excluding_manifest(
    *,
    files: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    manifest_name: str,
) -> None:
    members = manifest.get("files")
    if not isinstance(members, list):
        raise ValueError(f"{manifest_name} lacks its exact file list")
    by_name = {str(item["filename"]): item for item in members}
    if set(by_name) != set(files) - {"artifact_manifest.json"}:
        raise ValueError(f"{manifest_name} member path set differs")
    for relative_path, item in by_name.items():
        payload = files[relative_path]
        if (
            int(item["byte_count"]) != len(payload)
            or str(item["sha256"]) != hashlib.sha256(payload).hexdigest()
        ):
            raise ValueError(f"{manifest_name} member bytes differ:{relative_path}")


def _baseline_scope_freeze(root: Path, authorization_id: str) -> BaselineQAScopeFreeze:
    baseline_root = root / BASELINE_QA_DIRECTORY
    baseline_files = _directory_files(baseline_root)
    if len(baseline_files) != 18 or sum(map(len, baseline_files.values())) != 1_233_274:
        raise ValueError("old single-type future QA pool geometry differs")
    baseline_artifact = json.loads(baseline_files["artifact_manifest.json"])
    _validate_self_excluding_manifest(
        files=baseline_files,
        manifest=baseline_artifact,
        manifest_name="old future QA Artifact Manifest",
    )
    baseline_candidate = json.loads(baseline_files["future_QA_candidate_population.json"])
    if (
        len(baseline_artifact["files"]) != 17
        or baseline_artifact.get("artifact_root") != BASELINE_QA_ARTIFACT_ROOT
        or baseline_candidate.get("manifest_id") != BASELINE_QA_MANIFEST_ID
    ):
        raise ValueError("old single-type future QA authority differs")

    formal_root = root / FORMAL_QA_COVERAGE_DIRECTORY
    formal_files = _directory_files(formal_root)
    if len(formal_files) != 17 or sum(map(len, formal_files.values())) != 810_715:
        raise ValueError("formal QA semantic-coverage directory geometry differs")
    formal_artifact = json.loads(formal_files["artifact_manifest.json"])
    _validate_self_excluding_manifest(
        files=formal_files,
        manifest=formal_artifact,
        manifest_name="formal QA semantic-coverage Artifact Manifest",
    )
    coverage_census = json.loads(formal_files["coverage_census.json"])
    decision = json.loads(formal_files["decision.json"])
    transition = json.loads(formal_files["transition.json"])
    if (
        len(formal_artifact["files"]) != 16
        or formal_artifact.get("manifest_id") != FORMAL_QA_ARTIFACT_MANIFEST_ID
        or formal_artifact.get("artifact_root") != FORMAL_QA_ARTIFACT_ROOT
        or coverage_census.get("row_manifest_hash") != FORMAL_QA_ROW_MANIFEST_ID
        or decision.get("decision_id") != FORMAL_QA_DECISION_ID
        or transition.get("transition_id") != FORMAL_QA_TRANSITION_ID
        or transition.get("decision_id") != FORMAL_QA_DECISION_ID
    ):
        raise ValueError("formal QA semantic-coverage JSON authority differs")
    return _identified(
        BaselineQAScopeFreeze,
        {"authorization_id": authorization_id},
        "freeze_id",
        "qa_generator_totality_baseline_scope_freeze:",
    )


def _canonical_bundles() -> tuple[tuple[str, EvidenceBundle], ...]:
    selected: dict[str, EvidenceBundle] = {}
    for task_type, _, bundle in coverage._fixture_bundles():  # noqa: SLF001
        selected.setdefault(task_type, bundle)
    if set(selected) != set(REGISTERED_TASK_TYPES):
        raise ValueError("canonical QA totality task set differs from Finance catalog")
    return tuple((task_type, selected[task_type]) for task_type in REGISTERED_TASK_TYPES)


def _check(report: CandidateVerificationReport, name: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == name)


def _row(
    *,
    source_binding_id: str,
    realized: RealizedTaskPackage,
    bundle: EvidenceBundle,
    execution: PublicPlanCandidateExecution,
    verification: CandidateVerificationReport,
    assessment: QualityAssessment,
    trajectory: Trajectory,
) -> TotalityRow:
    task_type = realized.task.public.task_type
    values = {
        "source_binding_id": source_binding_id,
        "task_type": task_type,
        "evidence_bundle_id": bundle.bundle_id,
        "proof_graph_id": realized.task.oracle.proof_graph_id,
        "semantic_task_id": realized.semantic_instance.semantic_task_id,
        "semantic_plan_id": realized.semantic_plan.plan_id,
        "binding_snapshot_id": realized.binding_snapshot.binding_snapshot_id,
        "realized_package_id": realized.realized_package_id,
        "trajectory_id": trajectory.trajectory_id,
        "public_plan_execution_id": execution.execution_id,
        "verification_trajectory_id": verification.trajectory_id,
        "assessment_id": assessment.assessment_id,
        "operator_sequence": tuple(
            node.operator_id for node in execution.reconstructed_program.nodes
        ),
        "program_node_count": execution.actual_node_count,
        "maximum_dependency_depth": execution.maximum_dependency_depth,
        "workflow_action_count": len(trajectory.steps),
        "retrieved_evidence_count": len(verification.retrieved_evidence_ids),
        "selected_evidence_count": len(verification.selected_evidence_ids),
        "executed_program_node_count": verification.executed_program_node_count,
        "grounded_operation_count": verification.grounded_operation_count,
        "independently_replayed_node_count": execution.independently_replayed_node_count,
        "exact_operation_correctness": _check(verification, "operation_correctness"),
        "answer_schema_correct": _check(verification, "answer_schema_validity"),
        "answer_correct": _check(verification, "answer_correctness"),
        "citation_correct": _check(verification, "citation_binding"),
        "evaluator_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
    }
    return _identified(TotalityRow, values, "row_id", "qa_generator_totality_row:")


def _rehashed_trajectory(trajectory: Trajectory, **updates: Any) -> Trajectory:
    values = trajectory.model_dump(mode="python", exclude={"trajectory_id"})
    values.update(updates)
    values["trajectory_id"] = canonical_hash(
        values, prefix="qa_generator_totality_attack_trajectory:"
    )
    return Trajectory.model_validate(values)


def _negative_controls(
    *,
    source_binding_id: str,
    cases: Mapping[str, tuple[RealizedTaskPackage, EvidenceBundle, Trajectory]],
    registry: OperationRegistry,
) -> NegativeControlAudit:
    controls: list[NegativeControl] = []

    def reject(name: str, stage: str, action: Any) -> None:
        try:
            accepted = action()
        except (ValueError, TypeError, KeyError):
            accepted = False
        if accepted:
            raise ValueError(f"negative control accepted:{name}")
        controls.append(NegativeControl(name=name, rejection_stage=stage))

    def changed_program_parameter(task: TaskPublicSpec, name: str, value: object) -> TaskPublicSpec:
        skeleton = task.program_skeleton
        if skeleton is None:
            raise ValueError("negative control requires the public Program")
        nodes = list(skeleton.nodes)
        output_index = next(
            index
            for index, node in enumerate(nodes)
            if node.public_node_id == skeleton.output_node_id
        )
        output = nodes[output_index]
        nodes[output_index] = output.model_copy(
            update={"parameters": {**output.parameters, name: value}}
        )
        return task.model_copy(
            update={"program_skeleton": skeleton.model_copy(update={"nodes": tuple(nodes)})}
        )

    realized, bundle, trajectory = cases["registered_ratio"]
    corpus = EvidenceCorpus.from_bundle(bundle)
    unregistered_ratio = changed_program_parameter(
        realized.task.public, "registered_pair", "unregistered_metric/revenue"
    )
    reject(
        "unregistered_ratio_pair_substitution",
        "generator_source_admission",
        lambda: (
            FinanceNumericCandidateGeneratorTotality(
                realized=realized, corpus=corpus, registry=registry
            ).generate(unregistered_ratio, InMemoryEvidenceToolRuntime(bundle))
            is not None
        ),
    )

    denominator = bundle.evidence[1]
    zero_denominator = denominator.model_copy(
        update={"payload": denominator.payload.model_copy(update={"value": Decimal("0")})}
    )
    reject(
        "zero_denominator_evidence_substitution",
        "generator_source_admission",
        lambda: (
            FinanceNumericCandidateGeneratorTotality(
                realized=realized, corpus=corpus, registry=registry
            ).generate(
                realized.task.public,
                _StaticRuntime((bundle.evidence[0], zero_denominator)),
            )
            is not None
        ),
    )

    growth_realized, growth_bundle, _ = cases["temporal_growth"]
    growth_corpus = EvidenceCorpus.from_bundle(growth_bundle)
    reject(
        "temporal_order_substitution",
        "generator_source_admission",
        lambda: (
            FinanceNumericCandidateGeneratorTotality(
                realized=growth_realized, corpus=growth_corpus, registry=registry
            ).generate(
                growth_realized.task.public,
                _StaticRuntime(tuple(reversed(growth_bundle.evidence))),
            )
            is not None
        ),
    )

    derived_realized, derived_bundle, _ = cases["derived_growth_comparison"]
    derived_corpus = EvidenceCorpus.from_bundle(derived_bundle)
    crossed = derived_bundle.evidence[-1].model_copy(
        update={"subject": derived_bundle.evidence[0].subject}
    )
    reject(
        "derived_growth_cross_entity_substitution",
        "generator_source_admission",
        lambda: (
            FinanceNumericCandidateGeneratorTotality(
                realized=derived_realized, corpus=derived_corpus, registry=registry
            ).generate(
                derived_realized.task.public,
                _StaticRuntime((*tuple(derived_bundle.evidence[:-1]), crossed)),
            )
            is not None
        ),
    )

    changed_parameter = changed_program_parameter(
        derived_realized.task.public, "comparison_tolerance", "999"
    )
    reject(
        "program_parameter_substitution",
        "generator_source_admission",
        lambda: (
            FinanceNumericCandidateGeneratorTotality(
                realized=derived_realized, corpus=derived_corpus, registry=registry
            ).generate(changed_parameter, InMemoryEvidenceToolRuntime(derived_bundle))
            is not None
        ),
    )

    graph = ProofGraphBuilder().build(bundle)
    verifier = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        workflow_verifier=CandidateWorkflowVerifier(
            registry=registry, semantic_policy=FinanceSemanticPolicy()
        ),
    )
    wrong_answer = dict(trajectory.final_answer)
    wrong_result = dict(wrong_answer["result"])
    wrong_result["value"] = "999999"
    wrong_answer["result"] = wrong_result
    citations = list(wrong_answer["citations"])
    citations[0] = {**citations[0], "evidence_id": "evidence:forged:cross-case"}
    wrong_answer["citations"] = citations
    forged = _rehashed_trajectory(trajectory, final_answer=wrong_answer)
    reject(
        "fully_rehashed_wrong_answer_and_citation",
        "verifier_evaluator_admission",
        lambda: (
            verifier.evaluate(realized.task, corpus, graph, forged).decision
            != ReleaseDecision.REJECTED
        ),
    )

    return _identified(
        NegativeControlAudit,
        {"source_binding_id": source_binding_id, "controls": tuple(controls)},
        "audit_id",
        "qa_generator_totality_negative_audit:",
    )


def build_qa_generator_totality_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> QAGeneratorTotalityProducts:
    root = Path(repo_root).resolve()
    audit = Path(external_audit_path).read_bytes()
    if (
        hashlib.sha256(audit).hexdigest() != EXTERNAL_AUDIT_SHA256
        or len(audit) != EXTERNAL_AUDIT_BYTE_COUNT
    ):
        raise ValueError("external QA totality audit bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(directive) != OPERATOR_DIRECTIVE_BYTE_COUNT
        or hashlib.sha256(directive).hexdigest() != OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("QA totality operator directive bytes differ")
    authorization = _identified(
        QARevisionAuthorization,
        {},
        "authorization_id",
        "qa_generator_totality_authorization:",
    )
    baseline_scope_freeze = _baseline_scope_freeze(root, authorization.authorization_id)
    source_binding = _source_binding(
        root,
        authorization.authorization_id,
        source_commit,
        source_tree,
    )
    registry = finance_vnext_operation_registry()
    plugin = FinanceTaskPlugin()
    if tuple(sorted(plugin.task_family_ids)) != REGISTERED_TASK_TYPES:
        raise ValueError("FinanceTaskPlugin registered task catalog differs")
    workflow_verifier = CandidateWorkflowVerifier(
        registry=registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow_verifier
    )

    bundles: list[EvidenceBundle] = []
    packages: list[RealizedTaskPackage] = []
    executions: list[PublicPlanCandidateExecution] = []
    trajectories: list[Trajectory] = []
    reports: list[CandidateVerificationReport] = []
    assessments: list[QualityAssessment] = []
    rows: list[TotalityRow] = []
    case_map: dict[str, tuple[RealizedTaskPackage, EvidenceBundle, Trajectory]] = {}
    for task_type, bundle in _canonical_bundles():
        graph = ProofGraphBuilder().build(bundle)
        instantiation = plugin.compile_evidence_ids(
            task_type, graph, bundle, tuple(item.evidence_id for item in bundle.evidence)
        )
        compilation = plugin.realize_instantiation(instantiation, graph, bundle, max_realizations=1)
        if len(compilation.selected) != 1:
            raise ValueError("canonical totality case did not produce one Surface")
        realized = compilation.selected[0]
        corpus = EvidenceCorpus.from_bundle(bundle)
        generator = FinanceNumericCandidateGeneratorTotality(
            realized=realized, corpus=corpus, registry=registry
        )
        trajectory = generator.generate(realized.task.public, InMemoryEvidenceToolRuntime(corpus))
        execution = generator.last_execution
        if execution is None:
            raise ValueError("totality generator omitted its source execution")
        verification = workflow_verifier.verify(realized.task, corpus, graph, trajectory)
        assessment = evaluator.evaluate(realized.task, corpus, graph, trajectory)
        row = _row(
            source_binding_id=source_binding.binding_id,
            realized=realized,
            bundle=bundle,
            execution=execution,
            verification=verification,
            assessment=assessment,
            trajectory=trajectory,
        )
        bundles.append(bundle)
        packages.append(realized)
        executions.append(execution)
        trajectories.append(trajectory)
        reports.append(verification)
        assessments.append(assessment)
        rows.append(row)
        case_map[task_type] = (realized, bundle, trajectory)

    totality = _identified(
        GeneratorTotalityAudit,
        {
            "authorization_id": authorization.authorization_id,
            "source_binding_id": source_binding.binding_id,
            "rows": tuple(rows),
            "program_node_count_distribution": {"1": 3, "3": 3, "4": 1, "7": 1},
            "maximum_dependency_depth_distribution": {"1": 3, "2": 4, "3": 1},
        },
        "audit_id",
        "qa_generator_totality_audit:",
    )
    negative = _negative_controls(
        source_binding_id=source_binding.binding_id,
        cases=case_map,
        registry=registry,
    )
    scope = _identified(
        ScopeAudit,
        {
            "authorization_id": authorization.authorization_id,
            "source_binding_id": source_binding.binding_id,
            "totality_audit_id": totality.audit_id,
            "negative_audit_id": negative.audit_id,
        },
        "audit_id",
        "qa_generator_totality_scope_audit:",
    )
    gates = {
        "G0_external_scope_exact": True,
        "G1_baseline_and_formal_qa_scope_frozen": (
            baseline_scope_freeze.formal_json_is_authority
            and not baseline_scope_freeze.formal_json_authority_modified
        ),
        "G2_source_bound_successor_generator": (
            source_binding.finance_numeric_candidate_v7_source_bound
            and source_binding.registered_catalog_totalized
        ),
        "G3_registered_task_and_generator_exact_8_of_8": (
            len(totality.rows) == totality.successful_generator_branch_count == 8
        ),
        "G4_program_operation_totality_8_of_8": (totality.exact_operation_correctness_count == 8),
        "G5_answer_schema_answer_citation_8_of_8": (totality.citation_correct_count == 8),
        "G6_six_negative_controls_reject": negative.rejected_count == 6,
        "G7_zero_provider_gpu_online_release": not any(
            (
                scope.provider_calls,
                scope.gpu_jobs,
                scope.online_job_manifests,
                scope.qa_release_objects,
            )
        ),
    }
    report = _identified(
        QAGeneratorTotalityReport,
        {
            "authorization_id": authorization.authorization_id,
            "baseline_scope_freeze_id": baseline_scope_freeze.freeze_id,
            "source_binding_id": source_binding.binding_id,
            "totality_audit_id": totality.audit_id,
            "negative_audit_id": negative.audit_id,
            "scope_audit_id": scope.audit_id,
            "gates": gates,
        },
        "report_id",
        "qa_generator_totality_report:",
    )
    return QAGeneratorTotalityProducts(
        authorization=authorization,
        external_review_bytes=audit,
        operator_directive_bytes=directive,
        baseline_scope_freeze=baseline_scope_freeze,
        source_binding=source_binding,
        totality_audit=totality,
        negative_audit=negative,
        scope_audit=scope,
        report=report,
        bundles=tuple(bundles),
        realized_packages=tuple(packages),
        executions=tuple(executions),
        trajectories=tuple(trajectories),
        verification_reports=tuple(reports),
        assessments=tuple(assessments),
    )


def _jsonl(values: tuple[Any, ...]) -> bytes:
    return b"".join(canonical_json_bytes(item) + b"\n" for item in values)


def write_qa_generator_totality_artifacts(
    products: QAGeneratorTotalityProducts, output_dir: str | Path
) -> tuple[str, ...]:
    gate = {
        "gate_id": strict_canonical_hash(
            products.report.gates, prefix="qa_generator_totality_gate:"
        ),
        "passed": products.report.passed_count,
        "failed": products.report.failed_count,
        "noncompensatory": True,
        "gates": products.report.gates,
    }
    transition = {
        "transition_id": strict_canonical_hash(
            {
                "report_id": products.report.report_id,
                "next_stage": NEXT_STAGE,
                "provider_execution_authorized": False,
                "qa_release_authorized": False,
            },
            prefix="qa_generator_totality_transition:",
        ),
        "report_id": products.report.report_id,
        "next_stage": NEXT_STAGE,
        "provider_execution_authorized": False,
        "qa_release_authorized": False,
    }
    payloads = {
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "baseline_scope_freeze.json": canonical_json_bytes(products.baseline_scope_freeze) + b"\n",
        "evidence_bundles.jsonl": _jsonl(products.bundles),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(gate) + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_audit) + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "program_executions.jsonl": _jsonl(products.executions),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "realized_task_packages.jsonl": _jsonl(products.realized_packages),
        "report.json": canonical_json_bytes(products.report) + b"\n",
        "scope_boundary_audit.json": canonical_json_bytes(products.scope_audit) + b"\n",
        "source_binding.json": canonical_json_bytes(products.source_binding) + b"\n",
        "totality_audit.json": canonical_json_bytes(products.totality_audit) + b"\n",
        "totality_rows.jsonl": _jsonl(products.totality_audit.rows),
        "trajectories.jsonl": _jsonl(products.trajectories),
        "transition.json": canonical_json_bytes(transition) + b"\n",
        "verification_reports.jsonl": _jsonl(products.verification_reports),
    }
    members: tuple[dict[str, Any], ...] = tuple(
        {
            "relative_path": name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }
        for name, payload in sorted(payloads.items())
    )
    manifest_body = {
        "members": members,
        "file_count": len(members),
        "member_bytes": sum(int(item["byte_count"]) for item in members),
        "artifact_root": strict_canonical_hash(
            members, prefix="qa_generator_totality_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "qa_generator_totality_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    manifest_body, prefix="qa_generator_totality_artifact_manifest:"
                ),
                **manifest_body,
            }
        )
        + b"\n"
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    products = build_qa_generator_totality_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    write_qa_generator_totality_artifacts(products, args.output_dir)


if __name__ == "__main__":
    main()
