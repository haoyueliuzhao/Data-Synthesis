from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import (
    PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID,
    PublicPlanCandidateExecution,
    PublicPlanCandidateExecutor,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.patterns import REGISTERED_FINANCIAL_COMPARISON_PAIRS
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.qa_realization_vnext.future_candidate_population import (
    FutureQAPreOutcomeCandidateManifest,
)
from trusted_synthesis.hashing import canonical_hash

STAGE = "offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_only"
EXTERNAL_AUDIT_SHA256 = "c6efa19fd1c5ad9df0d7ebb2916ed66f57e4f5921fcdc8a9f1578ef5c225f16d"
EXTERNAL_AUDIT_BYTE_COUNT = 19_325
OPERATOR_DIRECTIVE = "参照审计报告给出的方案逐项修订优化"
OPERATOR_DIRECTIVE_SHA256 = "7f441e43f03a244a1ecab4ec08cca9e8572d874bafb8c8cc31c5ff32badc83c5"
BASELINE_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_realization_vnext/"
    "future_qa_candidate_population_v2_20260901"
)
BASELINE_MANIFEST_ID = (
    "future_qa_preoutcome_candidate_manifest:"
    "18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad"
)
BASELINE_ARTIFACT_ROOT = (
    "future_qa_candidate_artifact_root:"
    "9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04"
)
EXPECTED_TASK_TYPES = (
    "comparison",
    "derived_growth_comparison",
    "fact_retrieval",
    "registered_cross_metric_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)
EXPECTED_DEPTHS = {
    "comparison": 1,
    "derived_growth_comparison": 3,
    "fact_retrieval": 1,
    "registered_cross_metric_comparison": 1,
    "registered_ratio": 2,
    "temporal_absolute_change": 2,
    "temporal_average": 2,
    "temporal_growth": 2,
}
DEFERRED_RAW_PROPOSALS = (
    "growth_filter_margin_rank",
    "temporal_peak_secondary_lookup",
)


class ExactFileBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class OfflineQARevisionAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    authorization_id: str = Field(min_length=1)
    authorized_stage: Literal[
        "offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_only"
    ] = "offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_only"
    external_audit_sha256: Literal[
        "c6efa19fd1c5ad9df0d7ebb2916ed66f57e4f5921fcdc8a9f1578ef5c225f16d"
    ] = "c6efa19fd1c5ad9df0d7ebb2916ed66f57e4f5921fcdc8a9f1578ef5c225f16d"
    external_audit_byte_count: Literal[19325] = 19325
    operator_directive: Literal["参照审计报告给出的方案逐项修订优化"] = (
        "参照审计报告给出的方案逐项修订优化"
    )
    operator_directive_sha256: Literal[
        "7f441e43f03a244a1ecab4ec08cca9e8572d874bafb8c8cc31c5ff32badc83c5"
    ] = "7f441e43f03a244a1ecab4ec08cca9e8572d874bafb8c8cc31c5ff32badc83c5"
    authorized_phases: tuple[str, ...] = (
        "A_current_semantic_census",
        "B_public_plan_candidate_executor",
        "C_existing_eight_type_materialization",
    )
    deferred_phase: Literal["D_new_raw_operation_closure"] = "D_new_raw_operation_closure"
    provider_execution_authorized: Literal[False] = False
    vtdo_parent_authorized: Literal[False] = False
    schema_version: str = "offline_qa_revision_authorization.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> OfflineQARevisionAuthorization:
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"authorization_id"}),
            prefix="offline_qa_semantic_coverage_revision_authorization:",
        )
        if self.authorization_id != expected:
            raise ValueError("offline QA revision authorization identity is invalid")
        return self


class BaselineSemanticCensus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    census_id: str = Field(min_length=1)
    baseline_manifest_id: Literal[
        "future_qa_preoutcome_candidate_manifest:"
        "18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad"
    ] = (
        "future_qa_preoutcome_candidate_manifest:"
        "18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad"
    )
    baseline_artifact_root: Literal[
        "future_qa_candidate_artifact_root:"
        "9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04"
    ] = (
        "future_qa_candidate_artifact_root:"
        "9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04"
    )
    file_count: int = Field(ge=1)
    byte_count: int = Field(ge=1)
    manifest_member_count: int = Field(ge=1)
    semantic_instance_count: Literal[4] = 4
    surface_candidate_count: Literal[16] = 16
    selected_surface_count: Literal[8] = 8
    task_type_count: Literal[1] = 1
    topology_count: Literal[1] = 1
    answer_schema_count: Literal[1] = 1
    task_types: tuple[str, ...] = ("registered_cross_metric_comparison",)
    registered_pair_count: Literal[4] = 4
    registered_pair_denominator: Literal[6] = 6
    semantic_depth_distribution: dict[str, int] = {"1": 4}
    surface_depth_distribution: dict[str, int] = {"1": 16}
    renderer_count_per_instance: Literal[4] = 4
    non_null_program_execution_count: Literal[0] = 0
    files: tuple[ExactFileBinding, ...] = Field(min_length=1)
    schema_version: str = "baseline_qa_semantic_census.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> BaselineSemanticCensus:
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"census_id"}),
            prefix="baseline_qa_semantic_census:",
        )
        if self.census_id != expected:
            raise ValueError("baseline QA semantic Census identity is invalid")
        return self


class SemanticCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    semantic_plan_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    topology_hash: str = Field(min_length=1)
    parameterized_program_hash: str = Field(min_length=1)
    answer_schema_hash: str = Field(min_length=1)
    registered_pair: str | None = None
    operator_sequence: tuple[str, ...] = Field(min_length=1)
    operation_transitions: tuple[str, ...] = ()
    node_count: int = Field(ge=1)
    edge_count: int = Field(ge=0)
    maximum_dependency_depth: int = Field(ge=1)
    semantic_only_depth: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    subject_count: int = Field(ge=1)
    period_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    retrieval_track: str = Field(min_length=1)
    planning_track: str = Field(min_length=1)
    tool_capabilities: tuple[str, ...]
    renderer_profile_ids: tuple[str, ...] = Field(min_length=2, max_length=2)
    public_plan_execution_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    program_execution_non_null: bool
    executed_plan_node_count: int = Field(ge=1)
    independently_replayed_node_count: int = Field(ge=1)
    independent_replay_passed: bool
    plan_to_trajectory_exact: bool
    quality_assessment_id: str = Field(min_length=1)
    quality_accepted: bool
    schema_version: str = "offline_qa_semantic_coverage_row.v1"

    @model_validator(mode="after")
    def validate_row(self) -> SemanticCoverageRow:
        if self.maximum_dependency_depth != self.semantic_only_depth:
            raise ValueError("semantic-only depth differs from Program dependency depth")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"row_id"}),
            prefix="offline_qa_semantic_coverage_row:",
        )
        if self.row_id != expected:
            raise ValueError("offline QA semantic coverage row identity is invalid")
        return self


class SemanticCoverageCensus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    census_id: str = Field(min_length=1)
    baseline_census_id: str = Field(min_length=1)
    executor_contract_id: str = PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID
    row_manifest_hash: str = Field(min_length=1)
    rows: tuple[SemanticCoverageRow, ...] = Field(min_length=1)
    semantic_instance_count: int = Field(ge=1)
    surface_realization_count: int = Field(ge=1)
    renderer_count_per_instance: Literal[2] = 2
    registered_task_type_count: Literal[8] = 8
    materialized_task_type_count: Literal[8] = 8
    task_type_distribution: dict[str, int]
    topology_count: int = Field(ge=1)
    parameterized_program_count: int = Field(ge=1)
    answer_schema_count: int = Field(ge=1)
    semantic_depth_distribution: dict[str, int]
    node_count_distribution: dict[str, int]
    registered_comparison_pairs: tuple[str, ...] = Field(min_length=6, max_length=6)
    non_null_program_execution_count: int = Field(ge=1)
    independently_replayed_execution_count: int = Field(ge=1)
    exact_plan_trajectory_match_count: int = Field(ge=1)
    quality_accepted_count: int = Field(ge=1)
    provider_call_count: Literal[0] = 0
    gpu_job_count: Literal[0] = 0
    development_job_count: Literal[0] = 0
    vtdo_parent_count: Literal[0] = 0
    vtdo_artifact_write_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    schema_version: str = "offline_qa_semantic_coverage_census.v1"

    @model_validator(mode="after")
    def validate_census(self) -> SemanticCoverageCensus:
        if self.executor_contract_id != PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID:
            raise ValueError("semantic Census executor Contract differs")
        expected_row_manifest = strict_canonical_hash(
            tuple(row.row_id for row in self.rows),
            prefix="offline_qa_semantic_coverage_row_manifest:",
        )
        if self.row_manifest_hash != expected_row_manifest:
            raise ValueError("semantic Census row Manifest differs")
        if self.semantic_instance_count != len(self.rows):
            raise ValueError("semantic Census row denominator mismatch")
        if self.surface_realization_count != len(self.rows) * self.renderer_count_per_instance:
            raise ValueError("surface realization denominator mismatch")
        if set(self.task_type_distribution) != set(EXPECTED_TASK_TYPES):
            raise ValueError("semantic Census task-type set differs from the catalog")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"census_id", "rows"}),
            prefix="offline_qa_semantic_coverage_census:",
        )
        if self.census_id != expected:
            raise ValueError("offline QA semantic coverage Census identity is invalid")
        return self


class NegativeControlAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    controls: tuple[dict[str, Any], ...] = Field(min_length=1)
    control_count: int = Field(ge=1)
    rejected_count: int = Field(ge=1)
    accepted_count: Literal[0] = 0
    output_write_count: Literal[0] = 0
    provider_call_count: Literal[0] = 0
    schema_version: str = "offline_qa_semantic_negative_control_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if self.control_count != len(self.controls) or self.rejected_count != len(self.controls):
            raise ValueError("negative-control rejection denominator mismatch")
        if any(not row.get("rejected") for row in self.controls):
            raise ValueError("negative-control Audit contains an accepted mutation")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"audit_id"}),
            prefix="offline_qa_semantic_negative_control_audit:",
        )
        if self.audit_id != expected:
            raise ValueError("offline QA negative-control Audit identity is invalid")
        return self


class OfflineQAPreflightReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    baseline_census_id: str = Field(min_length=1)
    coverage_census_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    source_commit: str = Field(min_length=40, max_length=40)
    source_tree: str = Field(min_length=40, max_length=40)
    source_files: tuple[ExactFileBinding, ...] = Field(min_length=1)
    gates: dict[str, bool]
    decision: Literal[
        "offline_qa_existing_finance_pattern_catalog_semantic_type_coverage_and_"
        "program_depth_closure_preflight_passed"
    ]
    next_stage: Literal[
        "offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_"
        "independent_audit_only"
    ]
    claim_boundary: dict[str, Any]
    schema_version: str = "offline_qa_semantic_coverage_preflight_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> OfflineQAPreflightReport:
        if any(not value for value in self.gates.values()):
            raise ValueError("offline QA semantic coverage preflight failed a hard Gate")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"report_id"}),
            prefix="offline_qa_semantic_coverage_preflight_report:",
        )
        if self.report_id != expected:
            raise ValueError("offline QA semantic coverage Report identity is invalid")
        return self


class OfflineQABuildProducts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    authorization: OfflineQARevisionAuthorization
    baseline: BaselineSemanticCensus
    census: SemanticCoverageCensus
    negative_controls: NegativeControlAudit
    report: OfflineQAPreflightReport
    evidence_bundles: tuple[EvidenceBundle, ...]
    realized_packages: tuple[RealizedTaskPackage, ...]
    executions: tuple[PublicPlanCandidateExecution, ...]
    trajectories: tuple[Trajectory, ...]
    assessments: tuple[QualityAssessment, ...]


def build_offline_qa_semantic_coverage_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> OfflineQABuildProducts:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    if hashlib.sha256(review).hexdigest() != EXTERNAL_AUDIT_SHA256:
        raise ValueError("external QA coverage audit SHA-256 differs")
    if len(review) != EXTERNAL_AUDIT_BYTE_COUNT:
        raise ValueError("external QA coverage audit byte count differs")
    directive_bytes = OPERATOR_DIRECTIVE.encode("utf-8")
    if hashlib.sha256(directive_bytes).hexdigest() != OPERATOR_DIRECTIVE_SHA256:
        raise ValueError("operator directive SHA-256 differs")
    authorization_payload = {
        "authorized_stage": STAGE,
        "external_audit_sha256": EXTERNAL_AUDIT_SHA256,
        "external_audit_byte_count": EXTERNAL_AUDIT_BYTE_COUNT,
        "operator_directive": OPERATOR_DIRECTIVE,
        "operator_directive_sha256": OPERATOR_DIRECTIVE_SHA256,
        "authorized_phases": (
            "A_current_semantic_census",
            "B_public_plan_candidate_executor",
            "C_existing_eight_type_materialization",
        ),
        "deferred_phase": "D_new_raw_operation_closure",
        "provider_execution_authorized": False,
        "vtdo_parent_authorized": False,
        "schema_version": "offline_qa_revision_authorization.v1",
    }
    authorization = OfflineQARevisionAuthorization(
        authorization_id=strict_canonical_hash(
            authorization_payload,
            prefix="offline_qa_semantic_coverage_revision_authorization:",
        ),
        **authorization_payload,
    )
    baseline = _build_baseline_census(root)
    registry = finance_vnext_operation_registry()
    plugin = FinanceTaskPlugin()
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        workflow_verifier=CandidateWorkflowVerifier(
            registry=registry,
            semantic_policy=FinanceSemanticPolicy(),
        ),
    )
    executor = PublicPlanCandidateExecutor(registry)
    bundles: list[EvidenceBundle] = []
    realized_packages: list[RealizedTaskPackage] = []
    executions: list[PublicPlanCandidateExecution] = []
    trajectories: list[Trajectory] = []
    assessments: list[QualityAssessment] = []
    rows: list[SemanticCoverageRow] = []
    for task_type, registered_pair, bundle in _fixture_bundles():
        graph = ProofGraphBuilder().build(bundle)
        instantiation = plugin.compile_evidence_ids(
            task_type,
            graph,
            bundle,
            tuple(item.evidence_id for item in bundle.evidence),
        )
        compilation = plugin.realize_instantiation(
            instantiation,
            graph,
            bundle,
            max_realizations=2,
        )
        if len(compilation.selected) != 2:
            raise ValueError("QA semantic fixture did not materialize exactly two renderers")
        realized = min(compilation.selected, key=lambda item: item.realized_package_id)
        corpus = EvidenceCorpus.from_bundle(bundle)
        execution = executor.generate(realized, corpus)
        assessment = evaluator.evaluate(realized.task, corpus, graph, execution.trajectory)
        if assessment.decision != ReleaseDecision.ACCEPTED:
            raise ValueError("public Plan candidate failed the existing QA quality Gate")
        row = _coverage_row(
            realized,
            compilation.selected,
            bundle,
            execution,
            assessment,
            registered_pair,
        )
        bundles.append(bundle)
        realized_packages.extend(compilation.selected)
        executions.append(execution)
        trajectories.append(execution.trajectory)
        assessments.append(assessment)
        rows.append(row)
    rows_tuple = tuple(sorted(rows, key=lambda item: item.row_id))
    census = _coverage_census(baseline, rows_tuple)
    negative_controls = _negative_control_audit(
        next(
            item
            for item in realized_packages
            if item.semantic_plan.task_type == "registered_cross_metric_comparison"
        ),
        next(
            bundle
            for bundle in bundles
            if len(bundle.evidence) == 2
            and f"{bundle.evidence[0].predicate}/{bundle.evidence[1].predicate}"
            in {"revenue/gross_profit"}
        ),
    )
    source_files = _source_manifest(root)
    gates = {
        "A0_external_scope_exact": authorization.authorized_stage == STAGE,
        "A1_baseline_single_type_census_frozen": (
            baseline.task_type_count == baseline.topology_count == baseline.answer_schema_count == 1
            and baseline.surface_depth_distribution == {"1": 16}
        ),
        "A2_public_plan_executor_source_bound": all(
            row.plan_to_trajectory_exact and row.program_execution_non_null for row in rows_tuple
        ),
        "A3_existing_catalog_types_materialized_8_of_8": (
            census.materialized_task_type_count == census.registered_task_type_count == 8
        ),
        "A4_six_registered_comparison_pairs_materialized": len(census.registered_comparison_pairs)
        == 6,
        "A5_depth_strata_1_2_3_observed": (
            set(census.semantic_depth_distribution) == {"1", "2", "3"}
            and all(row.semantic_only_depth == EXPECTED_DEPTHS[row.task_type] for row in rows_tuple)
        ),
        "A6_nodewise_execution_and_independent_replay_exact": (
            census.non_null_program_execution_count
            == census.independently_replayed_execution_count
            == census.exact_plan_trajectory_match_count
            == census.quality_accepted_count
            == census.semantic_instance_count
        ),
        "A7_negative_controls_reject": negative_controls.accepted_count == 0,
        "A8_stage_D_new_operations_deferred": True,
        "A9_zero_provider_gpu_development_vtdo_boundary": not any(
            (
                census.provider_call_count,
                census.gpu_job_count,
                census.development_job_count,
                census.vtdo_parent_count,
                census.vtdo_artifact_write_count,
                census.empirical_row_count,
            )
        ),
    }
    claim_boundary = {
        "scope": "constructive offline closure of the eight existing Finance Pattern types",
        "semantic_denominator": "one row per BindingSnapshot-level semantic instance",
        "surface_denominator": "two renderer controls per semantic instance, reported separately",
        "implemented": (
            "read-only exact current 16/8 QA pool Census",
            "generic public Program and exact BindingSnapshot candidate executor",
            "topological execution of every Registry node",
            "independent Oracle-verifier replay of every node",
            "all eight existing Finance Pattern types",
            "all six registered cross-metric comparison pairs",
            "semantic dependency depths one, two, and three",
        ),
        "deferred_raw_proposals": DEFERRED_RAW_PROPOSALS,
        "not_claimed": (
            "real-world Finance QA distribution coverage",
            "model readability or model behavior",
            "empirical task difficulty",
            "new argmax, select-by-period, filter, intersection, or rank Operations",
            "Provider execution",
            "QA Release Population or production authority",
            "VTDO parentage, mutation, or downstream evidence",
            "training, release, or production readiness",
        ),
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "development_job_count": 0,
        "vtdo_artifact_write_count": 0,
    }
    report_payload = {
        "authorization_id": authorization.authorization_id,
        "baseline_census_id": baseline.census_id,
        "coverage_census_id": census.census_id,
        "negative_control_audit_id": negative_controls.audit_id,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "source_files": source_files,
        "gates": gates,
        "decision": (
            "offline_qa_existing_finance_pattern_catalog_semantic_type_coverage_and_"
            "program_depth_closure_preflight_passed"
        ),
        "next_stage": (
            "offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_"
            "independent_audit_only"
        ),
        "claim_boundary": claim_boundary,
        "schema_version": "offline_qa_semantic_coverage_preflight_report.v1",
    }
    draft = OfflineQAPreflightReport.model_construct(report_id="pending", **report_payload)
    report = OfflineQAPreflightReport(
        report_id=strict_canonical_hash(
            draft.model_dump(mode="python", exclude={"report_id"}),
            prefix="offline_qa_semantic_coverage_preflight_report:",
        ),
        **report_payload,
    )
    return OfflineQABuildProducts(
        authorization=authorization,
        baseline=baseline,
        census=census,
        negative_controls=negative_controls,
        report=report,
        evidence_bundles=tuple(bundles),
        realized_packages=tuple(realized_packages),
        executions=tuple(executions),
        trajectories=tuple(trajectories),
        assessments=tuple(assessments),
    )


def write_offline_qa_semantic_coverage_artifacts(
    products: OfflineQABuildProducts,
    output_dir: str | Path,
) -> tuple[str, ...]:
    gate_payload = {
        "gate_id": strict_canonical_hash(
            products.report.gates,
            prefix="offline_qa_semantic_coverage_gate_evaluation:",
        ),
        "passed": sum(products.report.gates.values()),
        "failed": sum(not value for value in products.report.gates.values()),
        "rows": products.report.gates,
        "noncompensatory": True,
    }
    decision_payload = {
        "decision_id": strict_canonical_hash(
            {
                "report_id": products.report.report_id,
                "decision": products.report.decision,
            },
            prefix="offline_qa_semantic_coverage_decision:",
        ),
        "report_id": products.report.report_id,
        "decision": products.report.decision,
    }
    transition_payload = {
        "transition_id": strict_canonical_hash(
            {
                "decision_id": decision_payload["decision_id"],
                "next_stage": products.report.next_stage,
                "provider_execution_authorized": False,
            },
            prefix="offline_qa_semantic_coverage_transition:",
        ),
        "decision_id": decision_payload["decision_id"],
        "next_stage": products.report.next_stage,
        "provider_execution_authorized": False,
    }
    payloads = {
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "baseline_semantic_census.json": canonical_json_bytes(products.baseline) + b"\n",
        "claim_boundary.json": canonical_json_bytes(products.report.claim_boundary) + b"\n",
        "coverage_census.json": canonical_json_bytes(
            products.census.model_dump(mode="python", exclude={"rows"})
        )
        + b"\n",
        "coverage_rows.jsonl": _jsonl(products.census.rows),
        "decision.json": canonical_json_bytes(decision_payload) + b"\n",
        "evidence_bundles.jsonl": _jsonl(products.evidence_bundles),
        "gate_evaluation.json": canonical_json_bytes(gate_payload) + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_controls) + b"\n",
        "public_plan_executions.jsonl": _jsonl(products.executions),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "realized_task_packages.jsonl": _jsonl(products.realized_packages),
        "report.json": canonical_json_bytes(products.report) + b"\n",
        "source_manifest.jsonl": _jsonl(products.report.source_files),
        "trajectories.jsonl": _jsonl(products.trajectories),
        "transition.json": canonical_json_bytes(transition_payload) + b"\n",
    }
    artifact_rows = tuple(
        {
            "filename": name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_count": len(content),
        }
        for name, content in sorted(payloads.items())
    )
    artifact_manifest_payload = {
        "files": artifact_rows,
        "artifact_root": strict_canonical_hash(
            artifact_rows,
            prefix="offline_qa_semantic_coverage_artifact_root:",
        ),
        "schema_version": "offline_qa_semantic_coverage_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    artifact_manifest_payload,
                    prefix="offline_qa_semantic_coverage_artifact_manifest:",
                ),
                **artifact_manifest_payload,
            }
        )
        + b"\n"
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def _build_baseline_census(root: Path) -> BaselineSemanticCensus:
    directory = root / BASELINE_DIRECTORY
    paths = tuple(sorted(path for path in directory.iterdir() if path.is_file()))
    artifact_manifest = json.loads((directory / "artifact_manifest.json").read_bytes())
    for row in artifact_manifest["files"]:
        content = (directory / row["filename"]).read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != row["sha256"]
            or len(content) != row["byte_count"]
        ):
            raise ValueError("baseline QA artifact member differs from its Manifest")
    if artifact_manifest["artifact_root"] != BASELINE_ARTIFACT_ROOT:
        raise ValueError("baseline QA artifact Root differs")
    manifest = FutureQAPreOutcomeCandidateManifest.model_validate_json(
        (directory / "future_QA_candidate_population.json").read_bytes()
    )
    if manifest.manifest_id != BASELINE_MANIFEST_ID:
        raise ValueError("baseline QA candidate Manifest identity differs")
    realized = tuple(
        RealizedTaskPackage.model_validate_json(line)
        for line in (directory / "realized_task_packages.jsonl").read_bytes().splitlines()
        if line
    )
    trajectories = tuple(
        Trajectory.model_validate_json(line)
        for line in (directory / "trajectories.jsonl").read_bytes().splitlines()
        if line
    )
    selected = json.loads((directory / "qualification_report.json").read_bytes())["selected_count"]
    pairs = {
        next(iter(item.task.oracle.task_program.nodes)).parameters["registered_pair"]
        for item in realized
    }
    payload = {
        "baseline_manifest_id": BASELINE_MANIFEST_ID,
        "baseline_artifact_root": BASELINE_ARTIFACT_ROOT,
        "file_count": len(paths),
        "byte_count": sum(path.stat().st_size for path in paths),
        "manifest_member_count": len(artifact_manifest["files"]),
        "semantic_instance_count": len({item.semantic_instance_id for item in realized}),
        "surface_candidate_count": len(realized),
        "selected_surface_count": selected,
        "task_type_count": len({item.semantic_plan.task_type for item in realized}),
        "topology_count": len({item.semantic_plan.topology_hash for item in realized}),
        "answer_schema_count": len(
            {
                canonical_hash(item.semantic_plan.answer_schema, prefix="answer_schema:")
                for item in realized
            }
        ),
        "task_types": tuple(sorted({item.semantic_plan.task_type for item in realized})),
        "registered_pair_count": len(pairs),
        "registered_pair_denominator": len(REGISTERED_FINANCIAL_COMPARISON_PAIRS),
        "semantic_depth_distribution": {"1": len({item.semantic_instance_id for item in realized})},
        "surface_depth_distribution": {"1": len(realized)},
        "renderer_count_per_instance": len(realized)
        // len({item.semantic_instance_id for item in realized}),
        "non_null_program_execution_count": sum(
            item.program_execution is not None for item in trajectories
        ),
        "files": tuple(
            ExactFileBinding(
                path=path.relative_to(root).as_posix(),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                byte_count=path.stat().st_size,
            )
            for path in paths
        ),
        "schema_version": "baseline_qa_semantic_census.v1",
    }
    draft = BaselineSemanticCensus.model_construct(census_id="pending", **payload)
    return BaselineSemanticCensus(
        census_id=strict_canonical_hash(
            draft.model_dump(mode="python", exclude={"census_id"}),
            prefix="baseline_qa_semantic_census:",
        ),
        **payload,
    )


def _fixture_bundles() -> tuple[tuple[str, str | None, EvidenceBundle], ...]:
    fixtures: list[tuple[str, str | None, EvidenceBundle]] = []
    fixtures.append(
        ("fact_retrieval", None, _bundle("fact", (_evidence("fact", "A", "revenue", 2025, "120"),)))
    )
    fixtures.append(
        (
            "comparison",
            None,
            _bundle(
                "comparison",
                (
                    _evidence("comparison_left", "A", "revenue", 2025, "120"),
                    _evidence("comparison_right", "B", "revenue", 2025, "100"),
                ),
            ),
        )
    )
    fixtures.append(
        (
            "temporal_growth",
            None,
            _bundle(
                "growth",
                (
                    _evidence("growth_earlier", "A", "revenue", 2024, "100"),
                    _evidence("growth_later", "A", "revenue", 2025, "125"),
                ),
            ),
        )
    )
    fixtures.append(
        (
            "temporal_average",
            None,
            _bundle(
                "average",
                tuple(
                    _evidence(f"average_{year}", "A", "revenue", year, value)
                    for year, value in ((2023, "90"), (2024, "105"), (2025, "120"))
                ),
            ),
        )
    )
    fixtures.append(
        (
            "temporal_absolute_change",
            None,
            _bundle(
                "absolute_change",
                (
                    _evidence("change_earlier", "A", "revenue", 2024, "100"),
                    _evidence("change_later", "A", "revenue", 2025, "118"),
                ),
            ),
        )
    )
    fixtures.append(
        (
            "registered_ratio",
            "gross_profit/revenue",
            _bundle(
                "ratio",
                (
                    _evidence("ratio_numerator", "A", "gross_profit", 2025, "60"),
                    _evidence("ratio_denominator", "A", "revenue", 2025, "120"),
                ),
            ),
        )
    )
    fixtures.append(
        (
            "derived_growth_comparison",
            None,
            _bundle(
                "derived_growth",
                (
                    _evidence("derived_left_earlier", "A", "revenue", 2024, "100"),
                    _evidence("derived_left_later", "A", "revenue", 2025, "135"),
                    _evidence("derived_right_earlier", "B", "revenue", 2024, "100"),
                    _evidence("derived_right_later", "B", "revenue", 2025, "120"),
                ),
            ),
        )
    )
    pair_values = {
        "revenue": "150",
        "gross_profit": "90",
        "operating_income": "70",
        "net_income": "55",
        "total_assets": "500",
        "total_liabilities": "280",
        "current_assets": "210",
        "current_liabilities": "130",
        "operating_cash_flow": "85",
    }
    for index, (left, right) in enumerate(REGISTERED_FINANCIAL_COMPARISON_PAIRS, start=1):
        pair = f"{left}/{right}"
        fixtures.append(
            (
                "registered_cross_metric_comparison",
                pair,
                _bundle(
                    f"registered_compare_{index}",
                    (
                        _evidence(f"registered_{index}_left", "A", left, 2025, pair_values[left]),
                        _evidence(
                            f"registered_{index}_right",
                            "A",
                            right,
                            2025,
                            pair_values[right],
                        ),
                    ),
                ),
            )
        )
    return tuple(fixtures)


@cache
def _base_evidence() -> EvidenceItem:
    return build_finance_counterfactual_case(1).bundle.evidence[0]


def _evidence(
    fixture_id: str,
    subject_suffix: str,
    predicate: str,
    year: int,
    value: str,
) -> EvidenceItem:
    source = _base_evidence()
    subject_id = f"QA_SEMANTIC_{subject_suffix}"
    statement_type = (
        "balance_sheet"
        if predicate
        in {"total_assets", "total_liabilities", "current_assets", "current_liabilities"}
        else "income_statement"
    )
    period_type = "instant" if statement_type == "balance_sheet" else "duration"
    suffix = f"{fixture_id}_{predicate}_{subject_suffix}_{year}".casefold()
    return source.model_copy(
        update={
            "evidence_id": f"evidence:finance:{suffix}@qa_semantic_coverage",
            "assertion_id": f"assertion:finance:{suffix}",
            "evidence_version_id": f"version:finance:{suffix}@qa_semantic_coverage",
            "subject": source.subject.model_copy(
                update={
                    "subject_id": subject_id,
                    "name": f"QA Semantic Company {subject_suffix}",
                }
            ),
            "predicate": predicate,
            "payload": ScalarObservation(
                value=Decimal(value),
                unit="million USD",
                currency="USD",
            ),
            "temporal_context": source.temporal_context.model_copy(
                update={
                    "label": f"FY{year}",
                    "valid_from": date(year - 1, 10, 1),
                    "valid_to": date(year, 9, 30),
                    "observed_at": None,
                    "basis": "fiscal_period",
                    "frequency": "annual",
                }
            ),
            "scope": source.scope.model_copy(
                update={
                    "scope_id": subject_id,
                    "label": f"{subject_id} consolidated",
                }
            ),
            "source_locator": source.source_locator.model_copy(
                update={"raw_object_id": f"raw_qa_semantic_{suffix}"}
            ),
            "definition": source.definition.model_copy(
                update={
                    "definition_id": f"sdef_{predicate}_gaap",
                    "text": f"GAAP {predicate.replace('_', ' ')} for the consolidated entity.",
                    "attributes": {
                        **source.definition.attributes,
                        "comparability_level": "xbrl_concept_level",
                        "statement_type": statement_type,
                        "period_type": period_type,
                        "default_unit": "million USD",
                    },
                }
            ),
            "provenance": source.provenance.model_copy(
                update={"source_record_id": f"qa_semantic_{suffix}"}
            ),
            "domain_context": {
                **source.domain_context,
                "fiscal_year": year,
                "economic_period_year": year,
                "statement_type": statement_type,
                "period_type": period_type,
                "is_forecast": False,
            },
        }
    )


def _bundle(fixture_id: str, evidence: tuple[EvidenceItem, ...]) -> EvidenceBundle:
    payload = {
        "fixture_id": fixture_id,
        "evidence_ids": tuple(item.evidence_id for item in evidence),
        "evidence_version_ids": tuple(item.evidence_version_id for item in evidence),
        "schema_version": "offline_qa_semantic_fixture_bundle.v1",
    }
    return EvidenceBundle(
        bundle_id=strict_canonical_hash(payload, prefix="offline_qa_semantic_fixture_bundle:"),
        evidence=evidence,
        purpose="offline QA semantic type and Program depth closure preflight",
        graph_build_id=f"offline_qa_semantic_graph:{fixture_id}",
        metadata={"provider_generated": False, "stage": STAGE},
    )


def _coverage_row(
    realized: RealizedTaskPackage,
    surfaces: tuple[RealizedTaskPackage, ...],
    bundle: EvidenceBundle,
    execution: PublicPlanCandidateExecution,
    assessment: QualityAssessment,
    registered_pair: str | None,
) -> SemanticCoverageRow:
    program = execution.reconstructed_program
    transitions = tuple(
        sorted(
            f"{next(item for item in program.nodes if item.node_id == dependency).operator_id}"
            f"->{node.operator_id}"
            for node in program.nodes
            for dependency in node.dependencies
        )
    )
    tools = tuple(sorted(realized.task.public.allowed_tools))
    payload = {
        "task_family": realized.semantic_plan.task_family,
        "task_type": realized.semantic_plan.task_type,
        "semantic_task_id": realized.semantic_plan.semantic_task_id,
        "semantic_instance_id": realized.semantic_instance_id,
        "semantic_plan_id": realized.semantic_plan.plan_id,
        "binding_snapshot_id": realized.binding_snapshot_id,
        "topology_hash": realized.semantic_plan.topology_hash,
        "parameterized_program_hash": realized.semantic_plan.parameterized_hash,
        "answer_schema_hash": canonical_hash(
            realized.semantic_plan.answer_schema,
            prefix="answer_schema_semantics:",
        ),
        "registered_pair": registered_pair,
        "operator_sequence": tuple(node.operator_id for node in program.nodes),
        "operation_transitions": transitions,
        "node_count": execution.actual_node_count,
        "edge_count": execution.actual_edge_count,
        "maximum_dependency_depth": execution.maximum_dependency_depth,
        "semantic_only_depth": execution.maximum_dependency_depth,
        "evidence_count": len(bundle.evidence),
        "subject_count": len({item.subject.subject_id for item in bundle.evidence}),
        "period_count": len({item.temporal_context.label for item in bundle.evidence}),
        "source_count": len({item.source.source_id for item in bundle.evidence}),
        "retrieval_track": realized.semantic_plan.retrieval_track.value,
        "planning_track": realized.semantic_plan.planning_track.value,
        "tool_capabilities": tools,
        "renderer_profile_ids": tuple(
            sorted(item.realization.renderer_profile_id for item in surfaces)
        ),
        "public_plan_execution_id": execution.execution_id,
        "trajectory_id": execution.trajectory.trajectory_id,
        "program_execution_non_null": execution.trajectory.program_execution is not None,
        "executed_plan_node_count": execution.actual_node_count,
        "independently_replayed_node_count": execution.independently_replayed_node_count,
        "independent_replay_passed": execution.independent_verification.passed,
        "plan_to_trajectory_exact": all(execution.gates.values()),
        "quality_assessment_id": assessment.assessment_id,
        "quality_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
        "schema_version": "offline_qa_semantic_coverage_row.v1",
    }
    return SemanticCoverageRow(
        row_id=strict_canonical_hash(
            payload,
            prefix="offline_qa_semantic_coverage_row:",
        ),
        **payload,
    )


def _coverage_census(
    baseline: BaselineSemanticCensus,
    rows: tuple[SemanticCoverageRow, ...],
) -> SemanticCoverageCensus:
    task_counts = Counter(row.task_type for row in rows)
    depth_counts = Counter(row.semantic_only_depth for row in rows)
    node_counts = Counter(row.node_count for row in rows)
    pairs = tuple(
        sorted(
            row.registered_pair
            for row in rows
            if row.task_type == "registered_cross_metric_comparison"
            and row.registered_pair is not None
        )
    )
    payload = {
        "baseline_census_id": baseline.census_id,
        "executor_contract_id": PUBLIC_PLAN_CANDIDATE_EXECUTOR_CONTRACT_ID,
        "row_manifest_hash": strict_canonical_hash(
            tuple(row.row_id for row in rows),
            prefix="offline_qa_semantic_coverage_row_manifest:",
        ),
        "semantic_instance_count": len(rows),
        "surface_realization_count": len(rows) * 2,
        "renderer_count_per_instance": 2,
        "registered_task_type_count": len(EXPECTED_TASK_TYPES),
        "materialized_task_type_count": len(task_counts),
        "task_type_distribution": dict(sorted(task_counts.items())),
        "topology_count": len({row.topology_hash for row in rows}),
        "parameterized_program_count": len({row.parameterized_program_hash for row in rows}),
        "answer_schema_count": len({row.answer_schema_hash for row in rows}),
        "semantic_depth_distribution": {
            str(key): depth_counts[key] for key in sorted(depth_counts)
        },
        "node_count_distribution": {str(key): node_counts[key] for key in sorted(node_counts)},
        "registered_comparison_pairs": pairs,
        "non_null_program_execution_count": sum(row.program_execution_non_null for row in rows),
        "independently_replayed_execution_count": sum(
            row.independent_replay_passed for row in rows
        ),
        "exact_plan_trajectory_match_count": sum(row.plan_to_trajectory_exact for row in rows),
        "quality_accepted_count": sum(row.quality_accepted for row in rows),
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "development_job_count": 0,
        "vtdo_parent_count": 0,
        "vtdo_artifact_write_count": 0,
        "empirical_row_count": 0,
        "schema_version": "offline_qa_semantic_coverage_census.v1",
    }
    return SemanticCoverageCensus(
        census_id=strict_canonical_hash(
            payload,
            prefix="offline_qa_semantic_coverage_census:",
        ),
        rows=rows,
        **payload,
    )


def _negative_control_audit(
    realized: RealizedTaskPackage,
    bundle: EvidenceBundle,
) -> NegativeControlAudit:
    controls = []

    def reject(name: str, action: Any) -> None:
        try:
            action()
        except (KeyError, TypeError, ValueError) as exc:
            controls.append(
                {
                    "name": name,
                    "rejected": True,
                    "reason_type": type(exc).__name__,
                    "reason_sha256": hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
                }
            )
        else:
            controls.append({"name": name, "rejected": False})

    corpus = EvidenceCorpus.from_bundle(bundle)
    reject(
        "missing_bound_evidence",
        lambda: PublicPlanCandidateExecutor(finance_vnext_operation_registry()).generate(
            realized,
            EvidenceCorpus(
                corpus_id="corpus:missing_bound_evidence",
                evidence=bundle.evidence[:1],
                build_id=bundle.graph_build_id,
            ),
        ),
    )
    changed = bundle.evidence[0].model_copy(
        update={"evidence_version_id": "version:mutated@qa_semantic_coverage"}
    )
    reject(
        "cross_version_evidence_substitution",
        lambda: PublicPlanCandidateExecutor(finance_vnext_operation_registry()).generate(
            realized,
            EvidenceCorpus(
                corpus_id="corpus:cross_version",
                evidence=(changed, *bundle.evidence[1:]),
                build_id=bundle.graph_build_id,
            ),
        ),
    )
    reject(
        "registry_missing_registered_compare",
        lambda: PublicPlanCandidateExecutor(default_registry()).generate(realized, corpus),
    )
    first_node = realized.task.public.program_skeleton.nodes[0]
    attacked_node = first_node.model_copy(update={"parameters": {"registered_pair": "x/y"}})
    attacked_skeleton = realized.task.public.program_skeleton.model_copy(
        update={"nodes": (attacked_node, *realized.task.public.program_skeleton.nodes[1:])}
    )
    attacked_public = realized.task.public.model_copy(
        update={"program_skeleton": attacked_skeleton}
    )
    attacked_task = realized.task.model_copy(update={"public": attacked_public})
    attacked_package = realized.model_copy(update={"task": attacked_task})
    reject(
        "public_plan_parameter_substitution",
        lambda: PublicPlanCandidateExecutor(finance_vnext_operation_registry()).generate(
            attacked_package,
            corpus,
        ),
    )
    payload = {
        "controls": tuple(controls),
        "control_count": len(controls),
        "rejected_count": sum(bool(row["rejected"]) for row in controls),
        "accepted_count": sum(not bool(row["rejected"]) for row in controls),
        "output_write_count": 0,
        "provider_call_count": 0,
        "schema_version": "offline_qa_semantic_negative_control_audit.v1",
    }
    return NegativeControlAudit(
        audit_id=strict_canonical_hash(
            payload,
            prefix="offline_qa_semantic_negative_control_audit:",
        ),
        **payload,
    )


def _source_manifest(root: Path) -> tuple[ExactFileBinding, ...]:
    paths = (
        "trusted_data_synthesis/src/trusted_synthesis/core/trajectory/public_plan_executor.py",
        "trusted_data_synthesis/src/trusted_synthesis/domains/finance/pattern_runtime.py",
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_semantic_coverage/"
            "__init__.py"
        ),
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_semantic_coverage/"
            "preflight.py"
        ),
    )
    return tuple(
        ExactFileBinding(
            path=path,
            sha256=hashlib.sha256((root / path).read_bytes()).hexdigest(),
            byte_count=(root / path).stat().st_size,
        )
        for path in paths
    )


def executor_source_has_task_type_branch() -> bool:
    source = inspect.getsource(PublicPlanCandidateExecutor)
    return "task_type ==" in source or "task_type in" in source


def _jsonl(values: tuple[Any, ...]) -> bytes:
    return b"".join(canonical_json_bytes(item) + b"\n" for item in values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the offline QA semantic coverage and Program-depth closure preflight"
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_offline_qa_semantic_coverage_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    write_offline_qa_semantic_coverage_artifacts(products, args.output_dir)


if __name__ == "__main__":
    main()
