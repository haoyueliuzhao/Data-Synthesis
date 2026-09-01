from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.realization_binding import (
    RealizationExecutionBinding,
    bind_realization_execution,
    describe_generated_trajectory,
)
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.release import (
    DiversityAwareReleaseSelection,
    DiversityReleasePolicy,
    SplitPolicy,
    select_diversity_aware_release,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.patterns import REGISTERED_FINANCIAL_COMPARISON_PAIRS
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.semantic_proposals import (
    ProposalAuthorization,
    ProposalCompatibilityRow,
    RawProposalMigrationAudit,
    audit_raw_proposal_compatibility,
    raw_finance_semantic_proposals,
)
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime

POPULATION_ROLE = "future_QA_candidate_population"
AUTHORIZED_TASK_TYPE = "registered_cross_metric_comparison"
BLOCKED_TASK_TYPES = (
    "growth_filter_margin_rank",
    "temporal_peak_secondary_lookup",
)
FIXTURE_BINDINGS = (
    (1, "revenue", "gross_profit", Decimal("72000")),
    (5, "revenue", "operating_income", Decimal("41000")),
    (9, "revenue", "net_income", Decimal("26000")),
    (13, "operating_cash_flow", "net_income", Decimal("35000")),
)
SOURCE_PATHS = (
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/evaluator.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/realization_binding.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/release/diversity_selector.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/realization.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/semantic.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/realization.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/semantic_proposals.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/tasks.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_pilot/candidate.py",
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "future_candidate_population.py"
    ),
)
FORBIDDEN_VTDO_IDENTITY_TOKENS = (
    b"authoritative_kernel_manifest:",
    b"authoritative_execution_kernel_runner:",
    b"authoritative_kernel_job:",
    b"authoritative_kernel_package_catalog:",
    b"authoritative_kernel_raw_namespace:",
    b"authoritative_kernel_result_namespace:",
    b"json_explicit_development_job:",
)

V26_194_EXPECTED_IDS = {
    "package_catalog_id": (
        "authoritative_kernel_package_catalog:"
        "cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211"
    ),
    "manifest_id": (
        "authoritative_kernel_manifest:"
        "15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803"
    ),
    "runner_id": (
        "authoritative_execution_kernel_runner:"
        "7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034"
    ),
    "execution_contract_id": (
        "authoritative_execution_kernel_contract:"
        "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
    ),
}
V26_194_EXPECTED_FILE_SHA256 = {
    "report.json": ("ccd43d53b27636268e78a640589dfc4ccce1f52057510305bef0a4e61709439e"),
    "authoritative_development_manifest.json": (
        "4a661d7956b1078b4125cc1213ba059a33ddf4e1cdfa4b58f1b4897e9382cce3"
    ),
    "authoritative_runner_contract.json": (
        "6d2e7fc04d015f1bce699cd78da3115e85ba07240b1d75a1ac376b17c015041d"
    ),
    "authoritative_execution_contract.json": (
        "5f1d63bec748dde042e3fb92868d24daf9f642a2a7c36fc6ef4434c308e1fa63"
    ),
    "kernel_invocation_audit.json": (
        "944fed2f1b1a0160ea7e7096a8840df51812afd0a7e073af6f2d318e1be70b07"
    ),
}


class LocalSourceBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class BlockedProposalRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    blocked_record_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    compatibility_row_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    missing_operator_ids: tuple[str, ...] = Field(min_length=1)
    disposition: str = "blocked_proposal_not_materialized"
    realized_task_package_count: int = Field(default=0, ge=0)
    population_row_count: int = Field(default=0, ge=0)
    schema_version: str = "future_qa_blocked_proposal.v1"

    @model_validator(mode="after")
    def validate_record(self) -> BlockedProposalRecord:
        if self.task_type not in BLOCKED_TASK_TYPES:
            raise ValueError("blocked QA proposal is not in the frozen blocked set")
        if self.realized_task_package_count or self.population_row_count:
            raise ValueError("blocked QA proposal cannot be materialized")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"blocked_record_id"}),
            prefix="future_qa_blocked_proposal:",
        )
        if self.blocked_record_id != expected:
            raise ValueError("blocked QA proposal identity is invalid")
        return self


class FutureQAPreOutcomeCandidateRow(BaseModel):
    """Exact pre-outcome candidate identity; no assessment or selection fields are allowed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    population_role: Literal["future_QA_candidate_population"] = "future_QA_candidate_population"
    proposal_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    canonical_plan_id: str = Field(min_length=1)
    evidence_bundle_id: str = Field(min_length=1)
    evidence_bundle_hash: str = Field(min_length=1)
    evidence_corpus_id: str = Field(min_length=1)
    evidence_corpus_hash: str = Field(min_length=1)
    proof_graph_id: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    renderer_profile_id: str = Field(min_length=1)
    realization_id: str = Field(min_length=1)
    realized_task_package_id: str = Field(min_length=1)
    finance_semantic_policy_id: Literal["finance_semantics.v2"] = "finance_semantics.v2"
    operation_semantic_contract_hashes: tuple[str, ...] = Field(min_length=1)
    operation_implementation_hashes: tuple[str, ...] = Field(min_length=1)
    task_family: str = Field(min_length=1)
    task_type: str = AUTHORIZED_TASK_TYPE
    difficulty: Literal["candidate_unmeasured"] = "candidate_unmeasured"
    language: str = Field(min_length=1)
    market: str = Field(min_length=1)
    required_tools: tuple[str, ...] = Field(min_length=1)
    engineering_estimated_prompt_bytes: int = Field(ge=1)
    engineering_estimated_prompt_tokens: int = Field(ge=1)
    engineering_estimated_rollout_tokens: int = Field(ge=1)
    resource_estimate_status: Literal["engineering_estimate_only"] = "engineering_estimate_only"
    runner_projection_status: Literal["not_yet_runner_projected"] = "not_yet_runner_projected"
    online_resource_authority: Literal["not_online_resource_authority"] = (
        "not_online_resource_authority"
    )
    schema_version: str = "future_qa_preoutcome_candidate.v2"

    @model_validator(mode="after")
    def validate_candidate(self) -> FutureQAPreOutcomeCandidateRow:
        if self.population_role != POPULATION_ROLE or self.task_type != AUTHORIZED_TASK_TYPE:
            raise ValueError("pre-outcome candidate crosses the authorized future QA boundary")
        if self.engineering_estimated_prompt_tokens != self.engineering_estimated_prompt_bytes:
            raise ValueError("engineering prompt estimate does not follow the frozen byte rule")
        if (
            self.engineering_estimated_rollout_tokens
            != self.engineering_estimated_prompt_tokens + 4096
        ):
            raise ValueError("engineering rollout estimate lacks the local completion reserve")
        forbidden_keys = {
            "quality_assessment_id",
            "selected_for_future_population",
            "execution_binding_id",
        }
        if forbidden_keys & set(self.model_dump(mode="python")):
            raise ValueError("pre-outcome candidate contains a post-outcome field")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"candidate_id"}),
            prefix="future_qa_preoutcome_candidate:",
        )
        if self.candidate_id != expected:
            raise ValueError("pre-outcome candidate identity is invalid")
        return self


class QAVTDOIsolationReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    package_count: int = Field(ge=1)
    job_count: int = Field(ge=1)
    registered_prompt_coordinate_count: int = Field(ge=1)
    raw_namespace_count: int = Field(ge=1)
    result_namespace_count: int = Field(ge=1)
    source_artifact_sha256: dict[str, str]
    vtdo_python_import_count: int = Field(default=0, ge=0)
    vtdo_artifact_write_count: int = Field(default=0, ge=0)
    qa_candidate_parent_count: int = Field(default=0, ge=0)
    status: Literal["frozen_v26_194_condition_read_only_and_disjoint"] = (
        "frozen_v26_194_condition_read_only_and_disjoint"
    )
    schema_version: str = "qa_vtdo_isolation_receipt.v1"

    @model_validator(mode="after")
    def validate_receipt(self) -> QAVTDOIsolationReceipt:
        expected_values = (
            self.package_catalog_id == V26_194_EXPECTED_IDS["package_catalog_id"],
            self.manifest_id == V26_194_EXPECTED_IDS["manifest_id"],
            self.runner_id == V26_194_EXPECTED_IDS["runner_id"],
            self.execution_contract_id == V26_194_EXPECTED_IDS["execution_contract_id"],
            self.source_artifact_sha256 == V26_194_EXPECTED_FILE_SHA256,
            self.package_count == 32,
            self.job_count == 192,
            self.registered_prompt_coordinate_count == 792,
            self.raw_namespace_count == 192,
            self.result_namespace_count == 192,
            self.vtdo_python_import_count == 0,
            self.vtdo_artifact_write_count == 0,
            self.qa_candidate_parent_count == 0,
        )
        if not all(expected_values):
            raise ValueError("QA/VTDO isolation receipt does not preserve the frozen denominator")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"receipt_id"}),
            prefix="qa_vtdo_isolation_receipt:",
        )
        if self.receipt_id != expected:
            raise ValueError("QA/VTDO isolation receipt identity is invalid")
        return self


class FutureQAPreOutcomeCandidateManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = Field(min_length=1)
    population_role: Literal["future_QA_candidate_population"] = "future_QA_candidate_population"
    source_root: str = Field(min_length=1)
    isolation_receipt_id: str = Field(min_length=1)
    proposal_migration_audit_id: str = Field(min_length=1)
    authorized_proposal_ids: tuple[str, ...] = Field(min_length=1)
    blocked_records: tuple[BlockedProposalRecord, ...] = Field(min_length=1)
    candidate_rows: tuple[FutureQAPreOutcomeCandidateRow, ...] = Field(min_length=1)
    semantic_task_count: int = Field(ge=1)
    semantic_instance_count: int = Field(ge=1)
    candidate_count: int = Field(ge=1)
    blocked_proposal_count: int = Field(ge=1)
    provider_call_count: int = Field(default=0, ge=0)
    gpu_job_count: int = Field(default=0, ge=0)
    development_job_count: int = Field(default=0, ge=0)
    qa_release_population_manifest_count: int = Field(default=0, ge=0)
    hard_gates: dict[str, bool]
    claim_boundary: dict[str, Any]
    schema_version: str = "future_qa_preoutcome_candidate_manifest.v2"

    @model_validator(mode="after")
    def validate_manifest(self) -> FutureQAPreOutcomeCandidateManifest:
        if any(not value for value in self.hard_gates.values()):
            raise ValueError("pre-outcome future QA Manifest failed a hard Gate")
        if any(
            (
                self.provider_call_count,
                self.gpu_job_count,
                self.development_job_count,
                self.qa_release_population_manifest_count,
            )
        ):
            raise ValueError("pre-outcome future QA Manifest crosses an authority boundary")
        if self.candidate_count != len(self.candidate_rows):
            raise ValueError("pre-outcome candidate count mismatch")
        candidate_ids = tuple(row.candidate_id for row in self.candidate_rows)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("pre-outcome Manifest repeats a candidate identity")
        if self.semantic_task_count != len({row.semantic_task_id for row in self.candidate_rows}):
            raise ValueError("pre-outcome semantic-task count mismatch")
        if self.semantic_instance_count != len(
            {row.semantic_instance_id for row in self.candidate_rows}
        ):
            raise ValueError("pre-outcome semantic-instance count mismatch")
        if self.blocked_proposal_count != len(self.blocked_records):
            raise ValueError("pre-outcome blocked-proposal count mismatch")
        if {row.task_type for row in self.blocked_records} != set(BLOCKED_TASK_TYPES):
            raise ValueError("pre-outcome blocked Proposal set differs")
        if len(self.authorized_proposal_ids) != 1:
            raise ValueError("pre-outcome authorized Proposal denominator differs")
        serialized = canonical_json_bytes(self.candidate_rows)
        if any(token in serialized for token in FORBIDDEN_VTDO_IDENTITY_TOKENS):
            raise ValueError("pre-outcome candidates contain frozen VTDO identities")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"manifest_id"}),
            prefix="future_qa_preoutcome_candidate_manifest:",
        )
        if self.manifest_id != expected:
            raise ValueError("pre-outcome future QA Manifest identity is invalid")
        return self


class LocalAssessmentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    quality_assessment_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    accepted: bool
    schema_version: str = "future_qa_local_assessment_record.v1"

    @model_validator(mode="after")
    def validate_record(self) -> LocalAssessmentRecord:
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"record_id"}),
            prefix="future_qa_local_assessment_record:",
        )
        if self.record_id != expected:
            raise ValueError("local QA assessment record identity is invalid")
        return self


class LocalAssessmentCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    records: tuple[LocalAssessmentRecord, ...] = Field(min_length=1)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    empirical: Literal[False] = False
    schema_version: str = "future_qa_local_assessment_catalog.v1"

    @model_validator(mode="after")
    def validate_catalog(self) -> LocalAssessmentCatalog:
        record_ids = tuple(row.record_id for row in self.records)
        candidate_ids = tuple(row.candidate_id for row in self.records)
        if len(record_ids) != len(set(record_ids)) or len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("local assessment Catalog repeats a record or candidate")
        if self.accepted_count != sum(row.accepted for row in self.records):
            raise ValueError("local assessment accepted count mismatch")
        if self.rejected_count != sum(not row.accepted for row in self.records):
            raise ValueError("local assessment rejected count mismatch")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"catalog_id"}),
            prefix="future_qa_local_assessment_catalog:",
        )
        if self.catalog_id != expected:
            raise ValueError("local assessment Catalog identity is invalid")
        return self


class FutureQAQualificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    candidate_manifest_id: str = Field(min_length=1)
    local_assessment_catalog_id: str = Field(min_length=1)
    diversity_selection_id: str = Field(min_length=1)
    qualified_candidate_ids: tuple[str, ...] = Field(min_length=1)
    selected_candidate_ids: tuple[str, ...] = Field(min_length=1)
    qualified_count: int = Field(ge=1)
    selected_count: int = Field(ge=1)
    empirical: Literal[False] = False
    provider_call_count: Literal[0] = 0
    hard_gates: dict[str, bool]
    schema_version: str = "future_qa_qualification_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> FutureQAQualificationReport:
        if any(not value for value in self.hard_gates.values()):
            raise ValueError("future QA qualification failed a hard Gate")
        if self.qualified_count != len(self.qualified_candidate_ids):
            raise ValueError("qualified candidate count mismatch")
        if self.selected_count != len(self.selected_candidate_ids):
            raise ValueError("selected candidate count mismatch")
        if not set(self.selected_candidate_ids).issubset(self.qualified_candidate_ids):
            raise ValueError("diversity selection contains an unqualified candidate")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"report_id"}),
            prefix="future_qa_qualification_report:",
        )
        if self.report_id != expected:
            raise ValueError("future QA qualification report identity is invalid")
        return self


class FutureQABuildProducts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    candidate_manifest: FutureQAPreOutcomeCandidateManifest
    isolation_receipt: QAVTDOIsolationReceipt
    local_assessment_catalog: LocalAssessmentCatalog
    qualification_report: FutureQAQualificationReport
    source_files: tuple[LocalSourceBinding, ...]
    proposal_audit: RawProposalMigrationAudit
    blocked_records: tuple[BlockedProposalRecord, ...]
    evidence_bundles: tuple[EvidenceBundle, ...]
    realized_packages: tuple[RealizedTaskPackage, ...]
    trajectories: tuple[Trajectory, ...]
    quality_assessments: tuple[QualityAssessment, ...]
    execution_bindings: tuple[RealizationExecutionBinding, ...]
    release_selection: DiversityAwareReleaseSelection


def build_future_qa_candidate_population(*, repo_root: str | Path) -> FutureQABuildProducts:
    root = Path(repo_root).resolve()
    source_files = _source_manifest(root)
    source_root = strict_canonical_hash(source_files, prefix="future_qa_source_root:")
    proposal_audit = audit_raw_proposal_compatibility()
    proposals = {proposal.task_type: proposal for proposal in raw_finance_semantic_proposals()}
    compatibility = {row.task_type: row for row in proposal_audit.rows}
    authorized = tuple(
        row for row in proposal_audit.rows if row.authorization == ProposalAuthorization.AUTHORIZED
    )
    blocked_records = tuple(
        _blocked_record(proposals[task_type].proposal_id, compatibility[task_type])
        for task_type in BLOCKED_TASK_TYPES
    )

    # Phase A: build only source, semantic, binding, realization, and pre-outcome objects.
    plugin = FinanceTaskPlugin()
    evidence_bundles: list[EvidenceBundle] = []
    realized_packages: list[RealizedTaskPackage] = []
    bundle_by_package: dict[str, EvidenceBundle] = {}
    graph_by_package: dict[str, Any] = {}
    corpus_by_package: dict[str, EvidenceCorpus] = {}
    portfolio_by_package: dict[str, Any] = {}
    for index, left_predicate, right_predicate, right_value in FIXTURE_BINDINGS:
        bundle = _cross_metric_bundle(index, left_predicate, right_predicate, right_value)
        graph = ProofGraphBuilder().build(bundle)
        corpus = EvidenceCorpus.from_bundle(bundle)
        instantiation = plugin.compile_evidence_ids(
            AUTHORIZED_TASK_TYPE,
            graph,
            bundle,
            tuple(item.evidence_id for item in bundle.evidence),
        )
        compilation = plugin.realize_instantiation(instantiation, graph, bundle, max_realizations=4)
        evidence_bundles.append(bundle)
        for realized in compilation.selected:
            realized_packages.append(realized)
            bundle_by_package[realized.realized_package_id] = bundle
            graph_by_package[realized.realized_package_id] = graph
            corpus_by_package[realized.realized_package_id] = corpus
            portfolio_by_package[realized.realized_package_id] = compilation.portfolio

    proposal_id = proposals[AUTHORIZED_TASK_TYPE].proposal_id
    preoutcome_rows = tuple(
        sorted(
            (
                _preoutcome_candidate_row(
                    realized=realized,
                    bundle=bundle_by_package[realized.realized_package_id],
                    corpus=corpus_by_package[realized.realized_package_id],
                    proof_graph_id=graph_by_package[realized.realized_package_id].graph_id,
                    proof_graph_hash=graph_by_package[realized.realized_package_id].graph_hash,
                    proposal_id=proposal_id,
                )
                for realized in realized_packages
            ),
            key=lambda row: row.candidate_id,
        )
    )
    isolation_receipt = _build_isolation_receipt(root)
    semantic_tasks = {row.semantic_task_id for row in preoutcome_rows}
    semantic_instances = {row.semantic_instance_id for row in preoutcome_rows}
    blocked_proposal_ids = {row.proposal_id for row in blocked_records}
    serialized_candidates = canonical_json_bytes(preoutcome_rows)
    semantic_policy = FinanceSemanticPolicy()
    semantic_policy_checks = tuple(
        semantic_policy.validate_registered_comparison_pair(
            bundle.evidence[0],
            bundle.evidence[1],
            REGISTERED_FINANCIAL_COMPARISON_PAIRS,
        )
        for bundle in evidence_bundles
    )
    unregistered_right = (
        evidence_bundles[0].evidence[1].model_copy(update={"predicate": "inventory"})
    )
    unregistered_control = semantic_policy.validate_registered_comparison_pair(
        evidence_bundles[0].evidence[0],
        unregistered_right,
        REGISTERED_FINANCIAL_COMPARISON_PAIRS,
    )
    manifest_gates = {
        "proposal_authorization_partition_exact": (
            proposal_audit.authorized_count == 1
            and proposal_audit.blocked_count == 2
            and tuple(row.task_type for row in authorized) == (AUTHORIZED_TASK_TYPE,)
        ),
        "authorized_operation_closure_only": {row.task_type for row in preoutcome_rows}
        == {AUTHORIZED_TASK_TYPE},
        "authoritative_registered_pair_registry_bound": all(
            (bundle.evidence[0].predicate, bundle.evidence[1].predicate)
            in REGISTERED_FINANCIAL_COMPARISON_PAIRS
            for bundle in evidence_bundles
        ),
        "registered_pair_semantic_policy_executed": all(
            row.comparable for row in semantic_policy_checks
        ),
        "unregistered_pair_negative_control_rejects": (
            not unregistered_control.comparable
            and "unregistered_financial_comparison_pair" in unregistered_control.reasons
        ),
        "blocked_proposals_retained_exact": (
            {row.task_type for row in blocked_records} == set(BLOCKED_TASK_TYPES)
        ),
        "blocked_proposal_materialization_zero": all(
            row.realized_task_package_count == row.population_row_count == 0
            for row in blocked_records
        ),
        "blocked_proposal_ids_absent_from_candidates": all(
            proposal.encode("utf-8") not in serialized_candidates
            for proposal in blocked_proposal_ids
        ),
        "four_binding_instances_exact": len(semantic_instances) == len(FIXTURE_BINDINGS) == 4,
        "four_renderer_candidates_per_instance": (
            len(preoutcome_rows) == 16
            and all(
                sum(row.semantic_instance_id == instance_id for row in preoutcome_rows) == 4
                for instance_id in semantic_instances
            )
        ),
        "preoutcome_candidate_fields_clean": all(
            not {
                "quality_assessment_id",
                "execution_binding_id",
                "selected_for_future_population",
            }
            & set(row.model_dump(mode="python"))
            for row in preoutcome_rows
        ),
        "lineage_parent_surface_complete": all(
            row.evidence_bundle_hash
            and row.evidence_corpus_hash
            and row.proof_graph_hash
            and row.source_record_ids
            and row.operation_semantic_contract_hashes
            and row.finance_semantic_policy_id == FinanceSemanticPolicy.policy_id
            for row in preoutcome_rows
        ),
        "resource_values_engineering_estimates_only": all(
            row.resource_estimate_status == "engineering_estimate_only"
            and row.runner_projection_status == "not_yet_runner_projected"
            and row.online_resource_authority == "not_online_resource_authority"
            for row in preoutcome_rows
        ),
        "v26_194_identity_and_namespace_scan_zero": all(
            token not in serialized_candidates for token in FORBIDDEN_VTDO_IDENTITY_TOKENS
        ),
        "v26_194_isolation_receipt_exact": (
            isolation_receipt.package_count == 32
            and isolation_receipt.job_count == 192
            and isolation_receipt.registered_prompt_coordinate_count == 792
            and isolation_receipt.raw_namespace_count == 192
            and isolation_receipt.result_namespace_count == 192
        ),
        "qa_release_population_manifest_zero": True,
        "provider_calls_zero": True,
        "gpu_jobs_zero": True,
        "development_jobs_zero": True,
    }
    claim_boundary = {
        "stage": "offline_future_qa_preoutcome_candidate_manifest",
        "population_role": POPULATION_ROLE,
        "phase_order": (
            "Phase A pre-outcome Manifest is constructed before Phase B local generation, "
            "assessment, execution binding, or diversity selection"
        ),
        "implemented": (
            "authorized SemanticTaskProposal compilation",
            "CanonicalSemanticPlan and binding-level SemanticInstance construction",
            "four renderer SurfaceRealizations per exact binding",
            "pre-outcome exact Candidate Manifest",
            "separate local assessment Catalog and diversity selection",
            "blocked proposal retention without task materialization",
            "read-only frozen VTDO isolation receipt",
        ),
        "not_claimed": (
            "current VTDO Development Population authority",
            "current frozen online Manifest or Runner membership",
            "QAReleasePopulationManifest or production Release authority",
            "Provider model behavior",
            "empirical task difficulty",
            "exact Runner prompt or rollout resource authority",
            "temporal or rank Operation authorization",
            "training, release, or production readiness",
        ),
        "resource_estimation_rule": (
            "engineering estimate only: canonical public-task UTF-8 bytes use a local "
            "one-byte-per-token ceiling and add a 4096-token completion reserve; the values "
            "are not Runner-projected or online resource authority"
        ),
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "development_job_count": 0,
    }
    manifest_payload = {
        "population_role": POPULATION_ROLE,
        "source_root": source_root,
        "isolation_receipt_id": isolation_receipt.receipt_id,
        "proposal_migration_audit_id": proposal_audit.audit_id,
        "authorized_proposal_ids": tuple(row.proposal_id for row in authorized),
        "blocked_records": blocked_records,
        "candidate_rows": preoutcome_rows,
        "semantic_task_count": len(semantic_tasks),
        "semantic_instance_count": len(semantic_instances),
        "candidate_count": len(preoutcome_rows),
        "blocked_proposal_count": len(blocked_records),
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "development_job_count": 0,
        "qa_release_population_manifest_count": 0,
        "hard_gates": manifest_gates,
        "claim_boundary": claim_boundary,
        "schema_version": "future_qa_preoutcome_candidate_manifest.v2",
    }
    candidate_manifest = FutureQAPreOutcomeCandidateManifest(
        manifest_id=strict_canonical_hash(
            manifest_payload, prefix="future_qa_preoutcome_candidate_manifest:"
        ),
        **manifest_payload,
    )

    # Phase B: only after the exact pre-outcome Manifest exists, run local controls.
    generator = FinanceNumericCandidateGenerator()
    evaluator = CandidateQualityEvaluator(
        semantic_policy=semantic_policy,
        workflow_verifier=CandidateWorkflowVerifier(
            registry=finance_vnext_operation_registry(), semantic_policy=semantic_policy
        ),
    )
    trajectories: list[Trajectory] = []
    assessments: list[QualityAssessment] = []
    execution_bindings: list[RealizationExecutionBinding] = []
    records = []
    for realized in realized_packages:
        corpus = corpus_by_package[realized.realized_package_id]
        graph = graph_by_package[realized.realized_package_id]
        generated = generator.generate(realized.task.public, InMemoryEvidenceToolRuntime(corpus))
        trajectory, descriptor = describe_generated_trajectory(
            realized,
            corpus,
            generated,
            generator_contract_id=FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        )
        assessment = evaluator.evaluate(realized.task, corpus, graph, trajectory)
        execution_binding = bind_realization_execution(
            realized,
            portfolio_by_package[realized.realized_package_id],
            trajectory,
            assessment,
            descriptor,
        )
        trajectories.append(trajectory)
        assessments.append(assessment)
        execution_bindings.append(execution_binding)
        records.append((realized, trajectory, assessment, execution_binding))

    release_selection = select_diversity_aware_release(
        records,
        policy=DiversityReleasePolicy(
            policy_id="future_qa_candidate_diversity_policy.v1",
            max_total=8,
            max_per_semantic_instance=2,
            max_per_semantic_schema=8,
            coverage_gain_weight=1.0,
            similarity_penalty_weight=0.25,
        ),
        split_policy=SplitPolicy(policy_id="future_qa_candidate_instance_split.v1"),
    )
    candidate_id_by_package = {
        row.realized_task_package_id: row.candidate_id for row in preoutcome_rows
    }
    local_records = tuple(
        sorted(
            (
                _local_assessment_record(
                    candidate_id=candidate_id_by_package[realized.realized_package_id],
                    assessment=assessment,
                    execution_binding=execution_binding,
                )
                for realized, _, assessment, execution_binding in records
            ),
            key=lambda row: row.record_id,
        )
    )
    local_catalog_payload = {
        "candidate_manifest_id": candidate_manifest.manifest_id,
        "records": local_records,
        "accepted_count": sum(row.accepted for row in local_records),
        "rejected_count": sum(not row.accepted for row in local_records),
        "empirical": False,
        "schema_version": "future_qa_local_assessment_catalog.v1",
    }
    local_catalog = LocalAssessmentCatalog(
        catalog_id=strict_canonical_hash(
            local_catalog_payload, prefix="future_qa_local_assessment_catalog:"
        ),
        **local_catalog_payload,
    )
    qualified_candidate_ids = tuple(
        sorted(row.candidate_id for row in local_records if row.accepted)
    )
    selected_candidate_ids = tuple(
        sorted(
            candidate_id_by_package[package_id]
            for package_id in release_selection.selected_realized_package_ids
        )
    )
    qualification_gates = {
        "manifest_constructed_before_phase_b": True,
        "realized_package_validation_exact": all(
            row.realization.validation.passed for row in realized_packages
        ),
        "quality_hard_gates_all_pass": all(
            row.decision == ReleaseDecision.ACCEPTED and all(gate.passed for gate in row.hard_gates)
            for row in assessments
        ),
        "local_assessment_coverage_exact": len(local_records) == len(preoutcome_rows) == 16,
        "execution_binding_coverage_exact": len(execution_bindings) == len(preoutcome_rows),
        "diversity_selection_hard_gates_pass": all(release_selection.hard_gates.values()),
        "two_selected_per_instance_exact": (
            set(release_selection.semantic_instance_child_counts.values()) == {2}
            and len(selected_candidate_ids) == 8
        ),
        "selection_is_qualified_subset": set(selected_candidate_ids).issubset(
            qualified_candidate_ids
        ),
        "empirical_rows_zero": True,
        "provider_calls_zero": True,
    }
    qualification_payload = {
        "candidate_manifest_id": candidate_manifest.manifest_id,
        "local_assessment_catalog_id": local_catalog.catalog_id,
        "diversity_selection_id": release_selection.selection_id,
        "qualified_candidate_ids": qualified_candidate_ids,
        "selected_candidate_ids": selected_candidate_ids,
        "qualified_count": len(qualified_candidate_ids),
        "selected_count": len(selected_candidate_ids),
        "empirical": False,
        "provider_call_count": 0,
        "hard_gates": qualification_gates,
        "schema_version": "future_qa_qualification_report.v1",
    }
    qualification_report = FutureQAQualificationReport(
        report_id=strict_canonical_hash(
            qualification_payload, prefix="future_qa_qualification_report:"
        ),
        **qualification_payload,
    )
    return FutureQABuildProducts(
        candidate_manifest=candidate_manifest,
        isolation_receipt=isolation_receipt,
        local_assessment_catalog=local_catalog,
        qualification_report=qualification_report,
        source_files=source_files,
        proposal_audit=proposal_audit,
        blocked_records=blocked_records,
        evidence_bundles=tuple(evidence_bundles),
        realized_packages=tuple(realized_packages),
        trajectories=tuple(trajectories),
        quality_assessments=tuple(assessments),
        execution_bindings=tuple(execution_bindings),
        release_selection=release_selection,
    )


def write_future_qa_candidate_artifacts(
    products: FutureQABuildProducts,
    output_dir: str | Path,
) -> tuple[str, ...]:
    proposals = raw_finance_semantic_proposals()
    payloads = {
        "blocked_proposals.jsonl": _jsonl(products.blocked_records),
        "claim_boundary.json": _json(products.candidate_manifest.claim_boundary),
        "evidence_bundles.jsonl": _jsonl(products.evidence_bundles),
        "execution_bindings.jsonl": _jsonl(products.execution_bindings),
        "future_QA_candidate_population.json": _json(products.candidate_manifest),
        "local_assessment_catalog.json": _json(products.local_assessment_catalog),
        "preoutcome_candidate_rows.jsonl": _jsonl(products.candidate_manifest.candidate_rows),
        "proposal_compatibility.jsonl": _jsonl(products.proposal_audit.rows),
        "proposal_migration_audit.json": _json(products.proposal_audit),
        "qualification_report.json": _json(products.qualification_report),
        "quality_assessments.jsonl": _jsonl(products.quality_assessments),
        "realized_task_packages.jsonl": _jsonl(products.realized_packages),
        "diversity_selection.json": _json(products.release_selection),
        "semantic_proposals.jsonl": _jsonl(proposals),
        "source_manifest.jsonl": _jsonl(products.source_files),
        "trajectories.jsonl": _jsonl(products.trajectories),
    }
    if any(
        token in content
        for token in FORBIDDEN_VTDO_IDENTITY_TOKENS
        for content in payloads.values()
    ):
        raise ValueError(
            "future QA non-isolation artifacts contain a forbidden VTDO identity or namespace"
        )
    # This one explicit receipt is the only formal file allowed to name the frozen VTDO parents.
    payloads["qa_vtdo_isolation_receipt.json"] = _json(products.isolation_receipt)
    artifact_rows = tuple(
        {
            "filename": filename,
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_count": len(content),
        }
        for filename, content in sorted(payloads.items())
    )
    payloads["artifact_manifest.json"] = _json(
        {
            "files": artifact_rows,
            "artifact_root": strict_canonical_hash(
                artifact_rows,
                prefix="future_qa_candidate_artifact_root:",
            ),
            "isolation_receipt_filename": "qa_vtdo_isolation_receipt.json",
            "schema_version": "future_qa_candidate_artifact_manifest.v2",
        }
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def _cross_metric_bundle(
    index: int,
    left_predicate: str,
    right_predicate: str,
    right_value: Decimal,
) -> EvidenceBundle:
    source = build_finance_counterfactual_case(index).bundle.evidence[0]
    shared_attributes = {
        **source.definition.attributes,
        "statement_type": "income_statement",
        "period_type": "duration",
        "comparability_level": "xbrl_concept_level",
        "default_unit": "million USD",
    }
    left_value = Decimal(str(source.payload.value))
    left = _metric_evidence(source, left_predicate, left_value, shared_attributes)
    right = _metric_evidence(source, right_predicate, right_value, shared_attributes)
    evidence = (left, right)
    bundle_id = strict_canonical_hash(
        {
            "evidence_ids": tuple(row.evidence_id for row in evidence),
            "evidence_version_ids": tuple(row.evidence_version_id for row in evidence),
            "purpose": POPULATION_ROLE,
            "schema_version": "future_qa_evidence_bundle.v1",
        },
        prefix="future_qa_evidence_bundle:",
    )
    return EvidenceBundle(
        bundle_id=bundle_id,
        evidence=evidence,
        purpose="offline future QA candidate generation",
        graph_build_id=f"future_qa_graph_build:{index:04d}",
        metadata={"population_role": POPULATION_ROLE, "provider_generated": False},
    )


def _metric_evidence(
    source: EvidenceItem,
    predicate: str,
    value: Decimal,
    definition_attributes: dict[str, Any],
) -> EvidenceItem:
    suffix = f"{source.subject.subject_id.casefold()}_{predicate}_fy2025"
    return source.model_copy(
        update={
            "evidence_id": f"evidence:finance:{suffix}@future_qa",
            "assertion_id": f"assertion:finance:{suffix}",
            "evidence_version_id": f"version:finance:{suffix}@future_qa",
            "predicate": predicate,
            "payload": source.payload.model_copy(update={"value": value}),
            "definition": source.definition.model_copy(
                update={
                    "definition_id": f"sdef_{predicate}_gaap",
                    "text": f"GAAP {predicate.replace('_', ' ')} for the consolidated entity.",
                    "attributes": definition_attributes,
                }
            ),
            "provenance": source.provenance.model_copy(
                update={"source_record_id": f"future_qa_{suffix}"}
            ),
        }
    )


def _blocked_record(
    proposal_id: str,
    row: ProposalCompatibilityRow,
) -> BlockedProposalRecord:
    payload = {
        "proposal_id": proposal_id,
        "compatibility_row_id": row.row_id,
        "task_type": row.task_type,
        "missing_operator_ids": row.missing_operator_ids,
        "disposition": "blocked_proposal_not_materialized",
        "realized_task_package_count": 0,
        "population_row_count": 0,
        "schema_version": "future_qa_blocked_proposal.v1",
    }
    return BlockedProposalRecord(
        blocked_record_id=strict_canonical_hash(
            payload,
            prefix="future_qa_blocked_proposal:",
        ),
        **payload,
    )


def _preoutcome_candidate_row(
    *,
    realized: RealizedTaskPackage,
    bundle: EvidenceBundle,
    corpus: EvidenceCorpus,
    proof_graph_id: str,
    proof_graph_hash: str,
    proposal_id: str,
) -> FutureQAPreOutcomeCandidateRow:
    prompt_bytes = len(canonical_json_bytes(realized.task.public))
    payload = {
        "population_role": POPULATION_ROLE,
        "proposal_id": proposal_id,
        "semantic_task_id": realized.semantic_plan.semantic_task_id,
        "semantic_instance_id": realized.semantic_instance_id,
        "binding_snapshot_id": realized.binding_snapshot_id,
        "canonical_plan_id": realized.semantic_plan.plan_id,
        "evidence_bundle_id": bundle.bundle_id,
        "evidence_bundle_hash": bundle.bundle_hash,
        "evidence_corpus_id": corpus.corpus_id,
        "evidence_corpus_hash": corpus.corpus_hash,
        "proof_graph_id": proof_graph_id,
        "proof_graph_hash": proof_graph_hash,
        "source_record_ids": realized.binding_snapshot.source_record_ids,
        "evidence_version_ids": realized.binding_snapshot.evidence_version_ids,
        "renderer_profile_id": realized.realization.renderer_profile_id,
        "realization_id": realized.realization.realization_id,
        "realized_task_package_id": realized.realized_package_id,
        "finance_semantic_policy_id": FinanceSemanticPolicy.policy_id,
        "operation_semantic_contract_hashes": tuple(
            sorted({node.operation_semantic_contract_hash for node in realized.semantic_plan.nodes})
        ),
        "operation_implementation_hashes": tuple(
            sorted({node.operation_implementation_hash for node in realized.semantic_plan.nodes})
        ),
        "task_family": "comparison",
        "task_type": AUTHORIZED_TASK_TYPE,
        "difficulty": "candidate_unmeasured",
        "language": realized.realization.language,
        "market": str(bundle.evidence[0].subject.attributes.get("market") or "unregistered"),
        "required_tools": realized.task.public.allowed_tools,
        "engineering_estimated_prompt_bytes": prompt_bytes,
        "engineering_estimated_prompt_tokens": prompt_bytes,
        "engineering_estimated_rollout_tokens": prompt_bytes + 4096,
        "resource_estimate_status": "engineering_estimate_only",
        "runner_projection_status": "not_yet_runner_projected",
        "online_resource_authority": "not_online_resource_authority",
        "schema_version": "future_qa_preoutcome_candidate.v2",
    }
    candidate_id = strict_canonical_hash(payload, prefix="future_qa_preoutcome_candidate:")
    return FutureQAPreOutcomeCandidateRow(candidate_id=candidate_id, **payload)


def _local_assessment_record(
    *,
    candidate_id: str,
    assessment: QualityAssessment,
    execution_binding: RealizationExecutionBinding,
) -> LocalAssessmentRecord:
    payload = {
        "candidate_id": candidate_id,
        "quality_assessment_id": assessment.assessment_id,
        "execution_binding_id": execution_binding.execution_binding_id,
        "accepted": assessment.decision == ReleaseDecision.ACCEPTED,
        "schema_version": "future_qa_local_assessment_record.v1",
    }
    record_id = strict_canonical_hash(payload, prefix="future_qa_local_assessment_record:")
    return LocalAssessmentRecord(record_id=record_id, **payload)


def _build_isolation_receipt(root: Path) -> QAVTDOIsolationReceipt:
    formal = (
        root / "trusted_data_synthesis/artifacts/vtdo_experiment/"
        "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
    )
    names = {
        "report": "report.json",
        "manifest": "authoritative_development_manifest.json",
        "runner": "authoritative_runner_contract.json",
        "execution_contract": "authoritative_execution_contract.json",
        "invocation_audit": "kernel_invocation_audit.json",
    }
    payloads = {key: (formal / name).read_bytes() for key, name in names.items()}
    report = json.loads(payloads["report"])
    manifest = json.loads(payloads["manifest"])
    invocation_audit = json.loads(payloads["invocation_audit"])
    jobs = tuple(manifest["jobs"])
    receipt_payload = {
        "package_catalog_id": report["package_catalog_id"],
        "manifest_id": report["manifest_id"],
        "runner_id": report["runner_id"],
        "execution_contract_id": report["execution_contract_id"],
        "package_count": report["exact_package_count"],
        "job_count": report["exact_job_count"],
        "registered_prompt_coordinate_count": invocation_audit["registered_invocation_count"],
        "raw_namespace_count": len({row["raw_namespace"] for row in jobs}),
        "result_namespace_count": len({row["result_namespace"] for row in jobs}),
        "source_artifact_sha256": {
            names[key]: hashlib.sha256(value).hexdigest() for key, value in sorted(payloads.items())
        },
        "vtdo_python_import_count": 0,
        "vtdo_artifact_write_count": 0,
        "qa_candidate_parent_count": 0,
        "status": "frozen_v26_194_condition_read_only_and_disjoint",
        "schema_version": "qa_vtdo_isolation_receipt.v1",
    }
    receipt_id = strict_canonical_hash(receipt_payload, prefix="qa_vtdo_isolation_receipt:")
    return QAVTDOIsolationReceipt(receipt_id=receipt_id, **receipt_payload)


def _source_manifest(root: Path) -> tuple[LocalSourceBinding, ...]:
    rows = []
    for relative in SOURCE_PATHS:
        payload = (root / relative).read_bytes()
        rows.append(
            LocalSourceBinding(
                path=relative,
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_count=len(payload),
            )
        )
    return tuple(rows)


def _json(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _jsonl(values: tuple[Any, ...]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline future QA candidate population")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_future_qa_candidate_population(repo_root=args.repo_root)
    written = write_future_qa_candidate_artifacts(products, args.output_dir)
    print(products.candidate_manifest.model_dump_json(indent=2))
    print(f"written_files={len(written)}")


if __name__ == "__main__":
    main()
