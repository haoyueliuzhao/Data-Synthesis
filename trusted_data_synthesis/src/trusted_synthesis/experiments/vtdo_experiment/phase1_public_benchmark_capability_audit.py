from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean, median
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_support_confirmation import (
    FinanceCapabilitySupportConfirmationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_workflow_information_audit import (
    WorkflowInformationThresholds,
)
from trusted_synthesis.hashing import canonical_hash

PUBLIC_BENCHMARK_AUDIT_VERSION = "finance_public_benchmark_capability_audit.v1"
PUBLIC_REFERENCE_MANIFEST_VERSION = "v25_21_public_agent_design_references.v1"
FINANCIAL_SNAPSHOT_AUDIT_VERSION = "financial_benchmark_structure_audit.v1"
MECHANISM_CATALOG_VERSION = "finance_capability_mechanism_catalog.v1"
MECHANISM_POPULATION_CONTRACT_VERSION = "finance_v25_21_mechanism_population_contract.v1"
BENCHMARK_ISOLATION_CONTRACT_VERSION = "public_benchmark_isolation_contract.v1"

CapabilityAxis = Literal[
    "information_acquisition",
    "tool_planning",
    "compositional_reasoning",
    "semantic_alignment",
    "verification",
    "recovery",
    "control_stopping",
]
RuntimeArm = Literal["scripted_tool", "autonomous_agent"]
MechanismTier = Literal["easy_control", "bridge", "frontier", "hard_control"]

CAPABILITY_AXES: tuple[CapabilityAxis, ...] = (
    "information_acquisition",
    "tool_planning",
    "compositional_reasoning",
    "semantic_alignment",
    "verification",
    "recovery",
    "control_stopping",
)

OLD_AXIS_BY_CAPABILITY: dict[CapabilityAxis, str] = {
    "information_acquisition": "retrieval",
    "tool_planning": "planning",
    "compositional_reasoning": "calculation",
    "semantic_alignment": "reconciliation",
    "verification": "verification",
    "recovery": "recovery",
    "control_stopping": "stopping",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PublishedStatistic(FrozenModel):
    statistic_id: str = Field(min_length=1)
    value: int = Field(ge=1)
    unit: str = Field(min_length=1)


class PublicBenchmarkDesignReference(FrozenModel):
    benchmark_id: str = Field(min_length=1)
    official_url: str = Field(pattern=r"^https://")
    reference_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    published_population_count: int = Field(ge=1)
    population_count_scope: str = Field(min_length=1)
    published_statistics: tuple[PublishedStatistic, ...] = Field(min_length=1)
    interaction_structures: tuple[str, ...] = Field(min_length=1)
    capability_axes: tuple[CapabilityAxis, ...] = Field(min_length=1)
    evaluation_mechanisms: tuple[str, ...] = Field(min_length=1)
    content_snapshot_status: Literal["not_loaded"] = "not_loaded"

    @model_validator(mode="after")
    def validate_reference(self) -> PublicBenchmarkDesignReference:
        if len(set(self.interaction_structures)) != len(self.interaction_structures):
            raise ValueError("public benchmark reference duplicates an interaction structure")
        if len(set(self.capability_axes)) != len(self.capability_axes):
            raise ValueError("public benchmark reference duplicates a capability axis")
        if len({item.statistic_id for item in self.published_statistics}) != len(
            self.published_statistics
        ):
            raise ValueError("public benchmark reference duplicates a published statistic")
        return self


class PublicBenchmarkContentPolicy(FrozenModel):
    task_content_loaded: Literal[False] = False
    question_answer_access: Literal["forbidden"] = "forbidden"
    synthesis_access: Literal["forbidden"] = "forbidden"
    training_access: Literal["forbidden"] = "forbidden"
    paraphrase_access: Literal["forbidden"] = "forbidden"
    aggregate_statistics_allowed: Literal[True] = True


class PublicBenchmarkReferenceManifest(FrozenModel):
    manifest_version: Literal["v25_21_public_agent_design_references.v1"]
    usage: Literal["design_reference_only"] = "design_reference_only"
    content_policy: PublicBenchmarkContentPolicy
    references: tuple[PublicBenchmarkDesignReference, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_manifest(self) -> PublicBenchmarkReferenceManifest:
        identifiers = {item.benchmark_id for item in self.references}
        required = {"gaia", "bfcl_v4", "webarena", "swe_bench", "agentbench"}
        if identifiers != required:
            raise ValueError("public Agent benchmark reference set is incomplete")
        return self


class FinancialSnapshotSpec(FrozenModel):
    benchmark_id: Literal["finqa", "tat_qa"]
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    source_repository: str = Field(pattern=r"^https://")
    source_revision: str = Field(min_length=40)
    source_blob_sha: str = Field(min_length=40)
    split: str = Field(min_length=1)
    example_count: int = Field(ge=1)
    document_count: int | None = Field(default=None, ge=1)
    adapter_version: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    usage: Literal["evaluation_only"] = "evaluation_only"


class FinancialBenchmarkManifest(FrozenModel):
    manifest_version: str = Field(min_length=1)
    usage: Literal["evaluation_only"] = "evaluation_only"
    total_examples: int = Field(ge=1)
    snapshots: tuple[FinancialSnapshotSpec, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_manifest(self) -> FinancialBenchmarkManifest:
        if {item.benchmark_id for item in self.snapshots} != {"finqa", "tat_qa"}:
            raise ValueError("financial benchmark manifest omits a mandatory snapshot")
        if self.total_examples != sum(item.example_count for item in self.snapshots):
            raise ValueError("financial benchmark total is inconsistent")
        return self


class NumericSummary(FrozenModel):
    count: int = Field(ge=1)
    minimum: float
    median: float
    mean: float
    p90: float
    maximum: float


class StructuralSignal(FrozenModel):
    count: int = Field(ge=0)
    rate: float = Field(ge=0, le=1)
    interpretation: str = Field(min_length=1)


class FinancialBenchmarkStructureAudit(FrozenModel):
    benchmark_id: Literal["finqa", "tat_qa"]
    snapshot_path: str = Field(min_length=1)
    snapshot_sha256: str = Field(min_length=64, max_length=64)
    expected_example_count: int = Field(ge=1)
    observed_example_count: int = Field(ge=1)
    distributions: dict[str, dict[str, int]]
    numeric_summaries: dict[str, NumericSummary]
    structural_signals: dict[str, StructuralSignal]
    structural_signature_count: int = Field(ge=1)
    maximum_structural_signature_share: float = Field(ge=0, le=1)
    normalized_structural_entropy: float = Field(ge=0, le=1)
    interaction_mode: Literal["static_evidence_given"] = "static_evidence_given"
    tool_interaction_observed: Literal[False] = False
    question_text_exported: Literal[False] = False
    answer_text_exported: Literal[False] = False
    usage: Literal["evaluation_statistics_only"] = "evaluation_statistics_only"
    schema_version: str = FINANCIAL_SNAPSHOT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinancialBenchmarkStructureAudit:
        if self.expected_example_count != self.observed_example_count:
            raise ValueError("financial benchmark snapshot denominator changed")
        if any(not distribution for distribution in self.distributions.values()):
            raise ValueError("financial benchmark audit contains an empty distribution")
        return self


class BenchmarkIsolationContract(FrozenModel):
    financial_snapshot_usage: Literal["evaluation_statistics_only"] = "evaluation_statistics_only"
    public_agent_reference_usage: Literal["aggregate_design_reference_only"] = (
        "aggregate_design_reference_only"
    )
    synthesis_access: Literal["forbidden"] = "forbidden"
    training_access: Literal["forbidden"] = "forbidden"
    paraphrase_access: Literal["forbidden"] = "forbidden"
    task_content_export: Literal["forbidden"] = "forbidden"
    benchmark_prompt_exported: Literal[False] = False
    benchmark_answer_exported: Literal[False] = False
    public_agent_task_content_loaded: Literal[False] = False
    aggregate_statistics_allowed: Literal[True] = True
    schema_version: str = BENCHMARK_ISOLATION_CONTRACT_VERSION


class CapabilityMechanism(FrozenModel):
    mechanism_id: str = Field(min_length=1)
    primary_axis: CapabilityAxis
    secondary_axes: tuple[CapabilityAxis, ...]
    benchmark_design_references: tuple[str, ...] = Field(min_length=1)
    required_structure: tuple[str, ...] = Field(min_length=2)
    prohibited_shortcuts: tuple[str, ...] = Field(min_length=1)
    observable_outcomes: tuple[str, ...] = Field(min_length=2)
    tiers: tuple[MechanismTier, ...] = (
        "easy_control",
        "bridge",
        "frontier",
        "hard_control",
    )
    schema_version: str = MECHANISM_CATALOG_VERSION


class CapabilityAxisGap(FrozenModel):
    capability_axis: CapabilityAxis
    legacy_axis: str = Field(min_length=1)
    v25_20_response_by_runtime: dict[RuntimeArm, float | None]
    v25_20_observed_tasks_by_runtime: dict[RuntimeArm, int]
    diagnosis: Literal[
        "saturated_ceiling",
        "autonomous_ceiling",
        "autonomous_floor",
        "boundary_but_coupled",
        "sparse_boundary",
        "host_controlled_in_scripted",
    ]
    financial_benchmark_signals: tuple[str, ...]
    public_agent_design_references: tuple[str, ...]
    required_mechanism_id: str = Field(min_length=1)


class ResponseBand(FrozenModel):
    lower: float = Field(ge=0, le=1)
    upper: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_band(self) -> ResponseBand:
        if self.lower >= self.upper:
            raise ValueError("capability response band is empty")
        return self


class MechanismPopulationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    tiers: tuple[MechanismTier, ...] = (
        "easy_control",
        "bridge",
        "frontier",
        "hard_control",
    )
    bridge_is_mandatory: Literal[True] = True
    development_groups_per_mechanism_by_tier: dict[MechanismTier, int] = {
        "easy_control": 2,
        "bridge": 4,
        "frontier": 4,
        "hard_control": 2,
    }
    development_mechanism_count: int = Field(default=7, ge=7, le=7)
    minimum_development_group_count: int = Field(default=84, ge=84, le=84)
    confirmation_groups_per_mechanism: int = Field(default=5, ge=5)
    replicas_per_confirmation_task: int = Field(default=5, ge=5)
    response_bands: dict[RuntimeArm, dict[CapabilityAxis, ResponseBand]]
    required_freshness_channels: tuple[str, ...] = (
        "task_artifact_id",
        "matched_group_id",
        "evidence_id",
        "evidence_version_id",
        "core_semantic_signature",
        "task_signature",
        "mechanism_signature",
    )
    matching_dimensions: tuple[str, ...] = (
        "public_answer_contract",
        "evidence_scope",
        "core_semantics",
        "output_format",
    )
    frozen_runtime_required: Literal[True] = True
    frozen_agent_prompt_required: Literal[True] = True
    frozen_tool_environment_required: Literal[True] = True
    correctness_is_runtime_gate: Literal[False] = False
    information_thresholds: dict[str, Any]
    information_threshold_manifest_hash: str = Field(min_length=1)
    development_confirmation_disjoint: Literal[True] = True
    benchmark_content_access: Literal["forbidden"] = "forbidden"
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["finance_v25_21_mechanism_population_construction_only"] = (
        "finance_v25_21_mechanism_population_construction_only"
    )
    schema_version: str = MECHANISM_POPULATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> MechanismPopulationContract:
        expected_count = self.development_mechanism_count * sum(
            self.development_groups_per_mechanism_by_tier.values()
        )
        if self.minimum_development_group_count != expected_count:
            raise ValueError("mechanism population group denominator is inconsistent")
        if set(self.development_groups_per_mechanism_by_tier) != set(self.tiers):
            raise ValueError("mechanism population omits a difficulty tier")
        scripted = set(self.response_bands.get("scripted_tool", {}))
        autonomous = set(self.response_bands.get("autonomous_agent", {}))
        if scripted != {
            "information_acquisition",
            "compositional_reasoning",
            "semantic_alignment",
            "verification",
            "recovery",
        }:
            raise ValueError("Scripted response bands include a Host-controlled axis")
        if autonomous != set(CAPABILITY_AXES):
            raise ValueError("Autonomous response bands omit a capability axis")
        if self.information_threshold_manifest_hash != canonical_hash(
            self.information_thresholds,
            prefix="workflow_information_thresholds:",
        ):
            raise ValueError("mechanism population changes the frozen information thresholds")
        if self.contract_id != mechanism_population_contract_id(self):
            raise ValueError("mechanism population contract identity is invalid")
        return self


class PublicBenchmarkCapabilityAudit(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    audit_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    implementation_module: Literal[
        "trusted_synthesis.experiments.vtdo_experiment.phase1_public_benchmark_capability_audit"
    ] = "trusted_synthesis.experiments.vtdo_experiment.phase1_public_benchmark_capability_audit"
    implementation_sha256: str = Field(min_length=64, max_length=64)
    financial_manifest_path: str = Field(min_length=1)
    financial_manifest_sha256: str = Field(min_length=64, max_length=64)
    public_reference_manifest_path: str = Field(min_length=1)
    public_reference_manifest_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_report_path: str = Field(min_length=1)
    source_v25_20_report_sha256: str = Field(min_length=64, max_length=64)
    source_v25_20_report_id: str = Field(min_length=1)
    isolation_contract: BenchmarkIsolationContract
    financial_benchmarks: tuple[FinancialBenchmarkStructureAudit, ...] = Field(
        min_length=2, max_length=2
    )
    public_agent_design_references: tuple[PublicBenchmarkDesignReference, ...] = Field(min_length=5)
    capability_gaps: tuple[CapabilityAxisGap, ...] = Field(min_length=7, max_length=7)
    mechanisms: tuple[CapabilityMechanism, ...] = Field(min_length=7, max_length=7)
    population_contract: MechanismPopulationContract
    audit_passed: Literal[True] = True
    experiment_readiness: Literal["design_ready_population_not_materialized"] = (
        "design_ready_population_not_materialized"
    )
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["finance_v25_21_mechanism_population_construction_only"] = (
        "finance_v25_21_mechanism_population_construction_only"
    )
    schema_version: str = PUBLIC_BENCHMARK_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PublicBenchmarkCapabilityAudit:
        if {item.benchmark_id for item in self.financial_benchmarks} != {"finqa", "tat_qa"}:
            raise ValueError("public benchmark audit omits a financial benchmark")
        if {item.capability_axis for item in self.capability_gaps} != set(CAPABILITY_AXES):
            raise ValueError("public benchmark audit omits a capability gap")
        if {item.primary_axis for item in self.mechanisms} != set(CAPABILITY_AXES):
            raise ValueError("public benchmark audit omits a primary mechanism")
        mechanism_ids = {item.mechanism_id for item in self.mechanisms}
        if any(item.required_mechanism_id not in mechanism_ids for item in self.capability_gaps):
            raise ValueError("capability gap points to an unknown mechanism")
        if self.report_id != public_benchmark_audit_id(self):
            raise ValueError("public benchmark audit identity is invalid")
        return self


def build_public_benchmark_capability_audit(
    *,
    financial_manifest_path: Path,
    public_reference_manifest_path: Path,
    source_v25_20_report_path: Path,
    output_dir: Path,
    run_id: str,
    audit_date: str,
) -> PublicBenchmarkCapabilityAudit:
    financial_manifest = FinancialBenchmarkManifest.model_validate_json(
        financial_manifest_path.read_text(encoding="utf-8")
    )
    reference_manifest = PublicBenchmarkReferenceManifest.model_validate_json(
        public_reference_manifest_path.read_text(encoding="utf-8")
    )
    source_report = FinanceCapabilitySupportConfirmationReport.model_validate_json(
        source_v25_20_report_path.read_text(encoding="utf-8")
    )
    if not source_report.runtime_qualification_passed:
        raise ValueError("v25.21 requires the qualified v25.20 Runtime instrument")
    if source_report.information_matrix_ready:
        raise ValueError("v25.21 gap redesign is invalid after an already-ready information matrix")
    financial_audits = tuple(
        _audit_financial_snapshot(item, financial_manifest_path.parent)
        for item in financial_manifest.snapshots
    )
    mechanisms = _mechanism_catalog()
    gaps = _capability_gaps(source_report, financial_audits, mechanisms)
    population_contract = _mechanism_population_contract()
    values = {
        "run_id": run_id,
        "audit_date": audit_date,
        "implementation_sha256": _sha256(Path(__file__)),
        "financial_manifest_path": str(financial_manifest_path),
        "financial_manifest_sha256": _sha256(financial_manifest_path),
        "public_reference_manifest_path": str(public_reference_manifest_path),
        "public_reference_manifest_sha256": _sha256(public_reference_manifest_path),
        "source_v25_20_report_path": str(source_v25_20_report_path),
        "source_v25_20_report_sha256": _sha256(source_v25_20_report_path),
        "source_v25_20_report_id": source_report.report_id,
        "isolation_contract": BenchmarkIsolationContract(),
        "financial_benchmarks": financial_audits,
        "public_agent_design_references": reference_manifest.references,
        "capability_gaps": gaps,
        "mechanisms": mechanisms,
        "population_contract": population_contract,
    }
    provisional = PublicBenchmarkCapabilityAudit.model_construct(report_id="pending", **values)
    report = PublicBenchmarkCapabilityAudit(
        report_id=public_benchmark_audit_id(provisional),
        **values,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(
        output_dir / "public_benchmark_capability_audit.json",
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    _write_text_atomic(
        output_dir / "public_benchmark_capability_audit.md",
        _render_report(report),
    )
    _write_text_atomic(
        output_dir / "v25_21_capability_mechanism_gap_manifest.json",
        json.dumps(
            {
                "source_report_id": report.report_id,
                "isolation_contract": report.isolation_contract.model_dump(mode="json"),
                "capability_gaps": [
                    item.model_dump(mode="json") for item in report.capability_gaps
                ],
                "mechanisms": [item.model_dump(mode="json") for item in report.mechanisms],
                "population_contract": report.population_contract.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return report


def _audit_financial_snapshot(
    spec: FinancialSnapshotSpec,
    manifest_directory: Path,
) -> FinancialBenchmarkStructureAudit:
    path = (manifest_directory / spec.path).resolve()
    if _sha256(path) != spec.sha256:
        raise ValueError(f"{spec.benchmark_id} snapshot hash differs from the frozen manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if spec.benchmark_id == "finqa":
        return _audit_finqa(spec, path, payload)
    return _audit_tat_qa(spec, path, payload)


def _audit_finqa(
    spec: FinancialSnapshotSpec,
    path: Path,
    payload: Any,
) -> FinancialBenchmarkStructureAudit:
    if not isinstance(payload, list):
        raise ValueError("FinQA snapshot is not a record list")
    operators: Counter[str] = Counter()
    operation_families: Counter[str] = Counter()
    depths: Counter[str] = Counter()
    modalities: Counter[str] = Counter()
    evidence_counts: Counter[str] = Counter()
    signatures: Counter[tuple[str, ...]] = Counter()
    table_rows: list[int] = []
    table_columns: list[int] = []
    question_words: list[int] = []
    multi_step = deep_program = multi_evidence = cross_modal = comparison = 0
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping) or not isinstance(item.get("qa"), Mapping):
            raise ValueError(f"FinQA item {index} is malformed")
        qa = item["qa"]
        question = qa.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"FinQA item {index} has no question")
        sequence = _finqa_operator_sequence(qa.get("program"))
        if not sequence:
            raise ValueError(f"FinQA item {index} has no executable program")
        operators.update(sequence)
        operation_families.update(_finqa_operation_family(operator) for operator in sequence)
        depth = len(sequence)
        depths[str(depth)] += 1
        signatures[sequence] += 1
        multi_step += depth >= 2
        deep_program += depth >= 3
        comparison += "greater" in sequence
        gold = qa.get("gold_inds") or {}
        if not isinstance(gold, (Mapping, list, tuple)):
            raise ValueError(f"FinQA item {index} has malformed gold evidence")
        evidence_count = len(gold)
        evidence_counts[str(evidence_count)] += 1
        multi_evidence += evidence_count >= 2
        keys = tuple(str(key) for key in gold) if isinstance(gold, Mapping) else ()
        has_table = any(key.startswith("table") for key in keys) or bool(qa.get("ann_table_rows"))
        has_text = any(key.startswith("text") for key in keys) or bool(qa.get("ann_text_rows"))
        modality = "both" if has_table and has_text else "table" if has_table else "text"
        if not has_table and not has_text:
            modality = "unknown"
        modalities[modality] += 1
        cross_modal += modality == "both"
        rows, columns = _table_shape(item.get("table"))
        table_rows.append(rows)
        table_columns.append(columns)
        question_words.append(len(question.split()))
    count = len(payload)
    return FinancialBenchmarkStructureAudit(
        benchmark_id="finqa",
        snapshot_path=spec.path,
        snapshot_sha256=spec.sha256,
        expected_example_count=spec.example_count,
        observed_example_count=count,
        distributions={
            "operator": dict(sorted(operators.items())),
            "operation_family": dict(sorted(operation_families.items())),
            "program_depth": dict(sorted(depths.items(), key=lambda item: int(item[0]))),
            "evidence_modality": dict(sorted(modalities.items())),
            "gold_evidence_count": dict(
                sorted(evidence_counts.items(), key=lambda item: int(item[0]))
            ),
        },
        numeric_summaries={
            "program_depth": _numeric_summary(
                [len(_finqa_operator_sequence(item["qa"].get("program"))) for item in payload]
            ),
            "table_row_count": _numeric_summary(table_rows),
            "table_column_count": _numeric_summary(table_columns),
            "question_word_count": _numeric_summary(question_words),
        },
        structural_signals={
            "multi_step_program": _signal(
                multi_step, count, "At least two executable arithmetic/aggregation operations."
            ),
            "deep_program": _signal(deep_program, count, "At least three executable operations."),
            "multi_evidence": _signal(
                multi_evidence, count, "At least two annotated report evidence items."
            ),
            "cross_modal_evidence": _signal(
                cross_modal, count, "Annotated evidence uses both table and report text."
            ),
            "comparison_operator": _signal(
                comparison, count, "Program includes an explicit comparison operator."
            ),
        },
        structural_signature_count=len(signatures),
        maximum_structural_signature_share=max(signatures.values()) / count,
        normalized_structural_entropy=_normalized_entropy(tuple(signatures.values())),
    )


def _audit_tat_qa(
    spec: FinancialSnapshotSpec,
    path: Path,
    payload: Any,
) -> FinancialBenchmarkStructureAudit:
    if not isinstance(payload, list):
        raise ValueError("TAT-QA snapshot is not a document list")
    answer_types: Counter[str] = Counter()
    answer_sources: Counter[str] = Counter()
    scales: Counter[str] = Counter()
    derivations: Counter[str] = Counter()
    fact_counts: Counter[str] = Counter()
    comparison_flags: Counter[str] = Counter()
    signatures: Counter[tuple[str, ...]] = Counter()
    table_rows: list[int] = []
    table_columns: list[int] = []
    question_words: list[int] = []
    arithmetic = multi_span = cross_modal = comparison = multi_evidence = 0
    observed = 0
    for document_index, item in enumerate(payload):
        if not isinstance(item, Mapping) or not isinstance(item.get("questions"), list):
            raise ValueError(f"TAT-QA document {document_index} is malformed")
        rows, columns = _table_shape(item.get("table"))
        questions = item["questions"]
        for question_index, qa in enumerate(questions):
            if not isinstance(qa, Mapping) or not isinstance(qa.get("question"), str):
                raise ValueError(
                    f"TAT-QA document {document_index} question {question_index} is malformed"
                )
            observed += 1
            answer_type = str(qa.get("answer_type") or "unknown")
            answer_source = str(qa.get("answer_from") or "unknown")
            scale = str(qa.get("scale") or "<none>")
            has_derivation = bool(str(qa.get("derivation") or "").strip())
            facts = qa.get("facts") or []
            if not isinstance(facts, list):
                raise ValueError("TAT-QA facts must be a list")
            fact_count = len(facts)
            requires_comparison = bool(qa.get("req_comparison"))
            answer_types[answer_type] += 1
            answer_sources[answer_source] += 1
            scales[scale] += 1
            derivations["nonempty" if has_derivation else "empty"] += 1
            fact_counts[str(fact_count)] += 1
            comparison_flags[str(requires_comparison).lower()] += 1
            arithmetic += answer_type == "arithmetic"
            multi_span += answer_type == "multi-span"
            cross_modal += answer_source == "table-text"
            comparison += requires_comparison
            multi_evidence += fact_count >= 2
            signatures[
                (
                    answer_type,
                    answer_source,
                    scale,
                    "derived" if has_derivation else "direct",
                    _count_bucket(fact_count),
                )
            ] += 1
            table_rows.append(rows)
            table_columns.append(columns)
            question_words.append(len(str(qa["question"]).split()))
    return FinancialBenchmarkStructureAudit(
        benchmark_id="tat_qa",
        snapshot_path=spec.path,
        snapshot_sha256=spec.sha256,
        expected_example_count=spec.example_count,
        observed_example_count=observed,
        distributions={
            "answer_type": dict(sorted(answer_types.items())),
            "answer_source": dict(sorted(answer_sources.items())),
            "scale": dict(sorted(scales.items())),
            "derivation_presence": dict(sorted(derivations.items())),
            "fact_count": dict(sorted(fact_counts.items(), key=lambda item: int(item[0]))),
            "requires_comparison": dict(sorted(comparison_flags.items())),
        },
        numeric_summaries={
            "table_row_count": _numeric_summary(table_rows),
            "table_column_count": _numeric_summary(table_columns),
            "question_word_count": _numeric_summary(question_words),
            "annotated_fact_count": _numeric_summary(
                [int(value) for value, count in fact_counts.items() for _ in range(count)]
            ),
        },
        structural_signals={
            "arithmetic_answer": _signal(
                arithmetic, observed, "Released answer type requires arithmetic."
            ),
            "multi_span_answer": _signal(
                multi_span, observed, "Released answer contains multiple spans."
            ),
            "cross_modal_evidence": _signal(
                cross_modal, observed, "Answer source combines table and report text."
            ),
            "explicit_comparison": _signal(
                comparison, observed, "Released annotation requires comparison."
            ),
            "multi_evidence": _signal(
                multi_evidence, observed, "At least two annotated facts support the answer."
            ),
        },
        structural_signature_count=len(signatures),
        maximum_structural_signature_share=max(signatures.values()) / observed,
        normalized_structural_entropy=_normalized_entropy(tuple(signatures.values())),
    )


def _mechanism_catalog() -> tuple[CapabilityMechanism, ...]:
    return (
        CapabilityMechanism(
            mechanism_id="finance.disambiguating_information_acquisition",
            primary_axis="information_acquisition",
            secondary_axes=("semantic_alignment", "verification"),
            benchmark_design_references=("gaia", "webarena", "bfcl_v4"),
            required_structure=(
                "two_or_more_plausible_entity_metric_source_paths",
                "answer_requires_a_multi_source_or_multi_hop_join",
                "distractors_share_surface_aliases_but_fail_one_typed_constraint",
            ),
            prohibited_shortcuts=(
                "single_exact_lookup_reveals_the_answer",
                "gold_evidence_is_identified_in_the_question",
            ),
            observable_outcomes=(
                "query_decomposition",
                "source_and_definition_disambiguation",
                "evidence_join_completeness",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.typed_tool_plan_and_argument_recovery",
            primary_axis="tool_planning",
            secondary_axes=("information_acquisition", "recovery", "control_stopping"),
            benchmark_design_references=("bfcl_v4", "agentbench", "webarena"),
            required_structure=(
                "multiple_tools_are_plausible_but_only_one_has_the_required_contract",
                "tool_arguments_depend_on_a_prior_observation",
                "at_least_one_recoverable_missing_or_invalid_argument_case",
            ),
            prohibited_shortcuts=("tool_and_arguments_are_fully_spelled_out_in_the_instruction",),
            observable_outcomes=(
                "tool_selection",
                "typed_argument_construction",
                "argument_repair_after_host_feedback",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.dependent_compositional_calculation",
            primary_axis="compositional_reasoning",
            secondary_axes=("semantic_alignment", "verification"),
            benchmark_design_references=("finqa", "tat_qa", "gaia"),
            required_structure=(
                "at_least_three_dependent_operations",
                "one_intermediate_result_is_required_by_a_later_step",
                "unit_or_period_normalization_precedes_the_final_operation",
            ),
            prohibited_shortcuts=(
                "final_answer_is_present_in_any_single_evidence_item",
                "independent_operations_can_be_reordered_without_effect",
            ),
            observable_outcomes=(
                "intermediate_value_correctness",
                "operation_order_correctness",
                "unit_and_period_normalization",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.bridge_semantic_alignment",
            primary_axis="semantic_alignment",
            secondary_axes=("information_acquisition", "compositional_reasoning"),
            benchmark_design_references=("tat_qa", "gaia"),
            required_structure=(
                "easy_and_hard_controls_bound_a_bridge_case",
                "bridge_conflict_is_resolvable_by_unit_period_alias_or_source_definition_rules",
                "hard_case_remains_non_comparable_under_the_same_public_policy",
            ),
            prohibited_shortcuts=(
                "all_compatible_inputs_are_identical",
                "all_conflicts_are_total_definition_conflicts",
            ),
            observable_outcomes=(
                "compatibility_class_selection",
                "bridge_resolution_with_qualifier",
                "hard_conflict_rejection",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.candidate_verification_and_repair",
            primary_axis="verification",
            secondary_axes=("recovery", "control_stopping"),
            benchmark_design_references=("swe_bench", "webarena"),
            required_structure=(
                "candidate_answer_or_analysis_is_provided_as_an_untrusted_artifact",
                "an_independent_check_exposes_a_localized_error_or_confirms_correctness",
                "repair_must_preserve_unaffected_claims_and_evidence",
            ),
            prohibited_shortcuts=(
                "candidate_is_always_wrong",
                "verification_result_is_stated_in_the_instruction",
            ),
            observable_outcomes=(
                "error_localization",
                "evidence_bound_correction",
                "regression_preservation",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.cross_family_failure_recovery",
            primary_axis="recovery",
            secondary_axes=("information_acquisition", "tool_planning", "verification"),
            benchmark_design_references=("bfcl_v4", "webarena", "swe_bench", "agentbench"),
            required_structure=(
                "failure_opportunities_occur_in_at_least_three_primary_families",
                "host_feedback_identifies_a_typed_failure_without_revealing_the_answer",
                "successful_revision_changes_only_the_failed_field_or_action",
            ),
            prohibited_shortcuts=(
                "recovery_is_isolated_to_a_single_recovery_family",
                "retrying_the_identical_action_can_succeed_without_new_information",
            ),
            observable_outcomes=(
                "failure_attribution",
                "field_specific_revision",
                "post_repair_completion",
            ),
        ),
        CapabilityMechanism(
            mechanism_id="finance.state_dependent_control_and_stopping",
            primary_axis="control_stopping",
            secondary_axes=("verification", "tool_planning"),
            benchmark_design_references=("webarena", "agentbench", "gaia"),
            required_structure=(
                "continuation_and_stopping_are_both_plausible_before_the_final_observation",
                "a_public_completeness_or_consistency_invariant_determines_when_to_stop",
                "unnecessary_extra_actions_have_a_measurable_cost_or_failure_risk",
            ),
            prohibited_shortcuts=(
                "fixed_action_count_determines_completion",
                "host_terminates_immediately_after_the_answer_value_appears",
            ),
            observable_outcomes=(
                "completion_invariant_check",
                "premature_stop_detection",
                "redundant_action_avoidance",
            ),
        ),
    )


def _capability_gaps(
    source: FinanceCapabilitySupportConfirmationReport,
    financial_audits: Sequence[FinancialBenchmarkStructureAudit],
    mechanisms: Sequence[CapabilityMechanism],
) -> tuple[CapabilityAxisGap, ...]:
    by_runtime = {cell.runtime_arm.value: cell for cell in source.information_cells}
    response: dict[str, dict[str, tuple[float | None, int]]] = {}
    for runtime, cell in by_runtime.items():
        response[runtime] = {
            item.response_variable: (item.conditional_success_rate, item.observed_task_count)
            for item in cell.axis_specific
        }
    finqa = next(item for item in financial_audits if item.benchmark_id == "finqa")
    tat_qa = next(item for item in financial_audits if item.benchmark_id == "tat_qa")
    mechanism_by_axis = {item.primary_axis: item.mechanism_id for item in mechanisms}
    details: dict[CapabilityAxis, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
        "information_acquisition": (
            "saturated_ceiling",
            (
                f"FinQA multi-evidence proxy={finqa.structural_signals['multi_evidence'].rate:.4f}",
                "TAT-QA cross-modal proxy="
                f"{tat_qa.structural_signals['cross_modal_evidence'].rate:.4f}",
                "Both financial benchmarks provide the evidence context and therefore do not "
                "measure tool retrieval.",
            ),
            ("gaia", "webarena", "bfcl_v4"),
        ),
        "tool_planning": (
            "host_controlled_in_scripted",
            ("FinQA and TAT-QA expose no interactive tool-selection trajectory.",),
            ("bfcl_v4", "agentbench", "webarena"),
        ),
        "compositional_reasoning": (
            "autonomous_ceiling",
            (
                "FinQA multi-step program rate="
                f"{finqa.structural_signals['multi_step_program'].rate:.4f}",
                "TAT-QA arithmetic-answer rate="
                f"{tat_qa.structural_signals['arithmetic_answer'].rate:.4f}",
            ),
            ("finqa", "tat_qa", "gaia"),
        ),
        "semantic_alignment": (
            "autonomous_floor",
            (
                "TAT-QA table-text evidence rate="
                f"{tat_qa.structural_signals['cross_modal_evidence'].rate:.4f}",
                "TAT-QA scale annotations expose unit semantics without an interactive "
                "reconciliation decision.",
            ),
            ("tat_qa", "gaia"),
        ),
        "verification": (
            "boundary_but_coupled",
            (
                "Financial benchmark scoring verifies final answers but does not expose repair "
                "actions.",
            ),
            ("swe_bench", "webarena"),
        ),
        "recovery": (
            "sparse_boundary",
            ("Neither FinQA nor TAT-QA contains a typed failure-observation-revision sequence.",),
            ("bfcl_v4", "webarena", "swe_bench", "agentbench"),
        ),
        "control_stopping": (
            "boundary_but_coupled",
            ("Static financial QA has no state-dependent continuation or stopping decision.",),
            ("webarena", "agentbench", "gaia"),
        ),
    }
    gaps = []
    for axis in CAPABILITY_AXES:
        legacy = OLD_AXIS_BY_CAPABILITY[axis]
        diagnosis, signals, references = details[axis]
        gaps.append(
            CapabilityAxisGap(
                capability_axis=axis,
                legacy_axis=legacy,
                v25_20_response_by_runtime={
                    runtime: response[runtime][legacy][0]
                    for runtime in ("scripted_tool", "autonomous_agent")
                },
                v25_20_observed_tasks_by_runtime={
                    runtime: response[runtime][legacy][1]
                    for runtime in ("scripted_tool", "autonomous_agent")
                },
                diagnosis=diagnosis,
                financial_benchmark_signals=signals,
                public_agent_design_references=references,
                required_mechanism_id=mechanism_by_axis[axis],
            )
        )
    return tuple(gaps)


def _mechanism_population_contract() -> MechanismPopulationContract:
    thresholds = WorkflowInformationThresholds().model_dump(mode="json")
    response_bands: dict[RuntimeArm, dict[CapabilityAxis, ResponseBand]] = {
        "scripted_tool": {
            "information_acquisition": ResponseBand(lower=0.70, upper=0.85),
            "compositional_reasoning": ResponseBand(lower=0.60, upper=0.80),
            "semantic_alignment": ResponseBand(lower=0.60, upper=0.80),
            "verification": ResponseBand(lower=0.35, upper=0.75),
            "recovery": ResponseBand(lower=0.40, upper=0.70),
        },
        "autonomous_agent": {
            "information_acquisition": ResponseBand(lower=0.45, upper=0.90),
            "tool_planning": ResponseBand(lower=0.35, upper=0.75),
            "compositional_reasoning": ResponseBand(lower=0.45, upper=0.90),
            "semantic_alignment": ResponseBand(lower=0.20, upper=0.60),
            "verification": ResponseBand(lower=0.35, upper=0.75),
            "recovery": ResponseBand(lower=0.40, upper=0.70),
            "control_stopping": ResponseBand(lower=0.35, upper=0.75),
        },
    }
    values = {
        "response_bands": response_bands,
        "information_thresholds": thresholds,
        "information_threshold_manifest_hash": canonical_hash(
            thresholds,
            prefix="workflow_information_thresholds:",
        ),
    }
    provisional = MechanismPopulationContract.model_construct(contract_id="pending", **values)
    return MechanismPopulationContract(
        contract_id=mechanism_population_contract_id(provisional),
        **values,
    )


def _finqa_operator_sequence(program: Any) -> tuple[str, ...]:
    if program is None:
        return ()
    values = (program,) if isinstance(program, str) else program
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(
        match.lower()
        for item in values
        for match in re.findall(r"([A-Za-z_][A-Za-z_0-9]*)\s*\(", str(item))
    )


def _finqa_operation_family(operator: str) -> str:
    if operator in {"table_average", "table_max", "table_min", "table_sum"}:
        return "table_aggregation"
    if operator == "greater":
        return "comparison"
    if operator in {"divide", "subtract", "add", "multiply", "exp"}:
        return "arithmetic"
    return "other"


def _table_shape(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        value = value.get("table")
    if not isinstance(value, list):
        return 0, 0
    rows = [item for item in value if isinstance(item, list)]
    return len(rows), max((len(item) for item in rows), default=0)


def _count_bucket(value: int) -> str:
    if value <= 1:
        return str(value)
    if value <= 3:
        return "2-3"
    return "4+"


def _numeric_summary(values: Sequence[int | float]) -> NumericSummary:
    if not values:
        raise ValueError("numeric benchmark summary cannot be empty")
    ordered = sorted(float(value) for value in values)
    p90_index = max(0, math.ceil(0.90 * len(ordered)) - 1)
    return NumericSummary(
        count=len(ordered),
        minimum=ordered[0],
        median=float(median(ordered)),
        mean=float(fmean(ordered)),
        p90=ordered[p90_index],
        maximum=ordered[-1],
    )


def _signal(count: int, denominator: int, interpretation: str) -> StructuralSignal:
    return StructuralSignal(
        count=count,
        rate=count / denominator,
        interpretation=interpretation,
    )


def _normalized_entropy(counts: Sequence[int]) -> float:
    positive = [value for value in counts if value > 0]
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    entropy = -sum((value / total) * math.log(value / total) for value in positive)
    return entropy / math.log(len(positive))


def mechanism_population_contract_id(value: MechanismPopulationContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_v25_21_mechanism_population_contract:",
    )


def public_benchmark_audit_id(value: PublicBenchmarkCapabilityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_public_benchmark_capability_audit:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _render_report(report: PublicBenchmarkCapabilityAudit) -> str:
    lines = [
        "# Finance v25.21 Public Benchmark Capability Audit",
        "",
        f"- Audit ID: `{report.report_id}`",
        f"- Source v25.20 report: `{report.source_v25_20_report_id}`",
        f"- Audit passed: **{report.audit_passed}**",
        f"- Experiment readiness: **{report.experiment_readiness}**",
        f"- Next permitted stage: **{report.next_permitted_stage}**",
        "- API calls / GPU jobs: **0 / 0**",
        "",
        "Public questions and answers were not exported, paraphrased, or made available to "
        "synthesis.",
        "Only aggregate design metadata and deterministic statistics are present in this artifact.",
        "",
        "## Financial Evaluation Snapshots",
        "",
        "| Benchmark | Items | Structural signatures | Max signature share | Entropy |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in report.financial_benchmarks:
        lines.append(
            f"| {item.benchmark_id} | {item.observed_example_count} | "
            f"{item.structural_signature_count} | "
            f"{item.maximum_structural_signature_share:.4f} | "
            f"{item.normalized_structural_entropy:.4f} |"
        )
    lines.extend(("", "### Structural signals", ""))
    for item in report.financial_benchmarks:
        lines.append(f"#### {item.benchmark_id}")
        lines.append("")
        for signal_id, signal in item.structural_signals.items():
            lines.append(
                f"- `{signal_id}`: {signal.count}/{item.observed_example_count} ({signal.rate:.2%})"
            )
        lines.append("")
    lines.extend(
        (
            "## Public Agent Design References",
            "",
            "| Benchmark | Published count | Count scope | Capability axes |",
            "| --- | ---: | --- | --- |",
        )
    )
    for item in report.public_agent_design_references:
        lines.append(
            f"| {item.benchmark_id} | {item.published_population_count} | "
            f"{item.population_count_scope} | {', '.join(item.capability_axes)} |"
        )
    lines.extend(
        (
            "",
            "## v25.20 Capability Gaps",
            "",
            "| Axis | Scripted | Autonomous | Diagnosis | Required mechanism |",
            "| --- | ---: | ---: | --- | --- |",
        )
    )
    for gap in report.capability_gaps:
        scripted = gap.v25_20_response_by_runtime["scripted_tool"]
        autonomous = gap.v25_20_response_by_runtime["autonomous_agent"]
        lines.append(
            f"| {gap.capability_axis} | {_render_rate(scripted)} | "
            f"{_render_rate(autonomous)} | {gap.diagnosis} | `{gap.required_mechanism_id}` |"
        )
    lines.extend(
        (
            "",
            "## v25.21 Population Contract",
            "",
            f"- Mechanisms: **{report.population_contract.development_mechanism_count}**",
            "- Development matched groups: "
            f"**{report.population_contract.minimum_development_group_count}**",
            "- Tiers: **Easy / Bridge / Frontier / Hard**",
            "- Bridge groups per mechanism: **4**",
            "- Confirmation groups per mechanism: **5**",
            "- Replicas per confirmation task: **5**",
            "- Runtime, Agent prompt, tool environment, and information thresholds remain frozen.",
            "- Pro, Beneficiary screening, Exact Target, GP-C, and Contribution remain blocked.",
            "",
        )
    )
    return "\n".join(lines)


def _render_rate(value: float | None) -> str:
    return "host-controlled" if value is None else f"{value:.2%}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit public benchmark capability structures without exposing task content."
    )
    parser.add_argument("--financial-manifest", type=Path, required=True)
    parser.add_argument("--public-reference-manifest", type=Path, required=True)
    parser.add_argument("--source-v25-20-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--audit-date", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_public_benchmark_capability_audit(
        financial_manifest_path=args.financial_manifest,
        public_reference_manifest_path=args.public_reference_manifest,
        source_v25_20_report_path=args.source_v25_20_report,
        output_dir=args.output_dir,
        run_id=args.run_id,
        audit_date=args.audit_date,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "financial_example_count": sum(
                    item.observed_example_count for item in report.financial_benchmarks
                ),
                "public_agent_reference_count": len(report.public_agent_design_references),
                "mechanism_count": len(report.mechanisms),
                "minimum_development_group_count": (
                    report.population_contract.minimum_development_group_count
                ),
                "next_permitted_stage": report.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
