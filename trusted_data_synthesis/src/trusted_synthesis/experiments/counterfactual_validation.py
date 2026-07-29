from __future__ import annotations

from collections import defaultdict
from statistics import mean

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.contracts import (
    ContractQualityAssessment,
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualCalibrationReport,
    CounterfactualContext,
    calibrate_counterfactuals,
)
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_pattern_validation_cases,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

COUNTERFACTUAL_VALIDATION_SUITE_VERSION = "counterfactual_validation_suite.v1"


class CounterfactualValidationSuiteReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suite_id: str
    suite_version: str
    tasks_per_domain: int = Field(ge=1)
    domain_task_counts: dict[str, int]
    source_sample_count: int = Field(ge=1)
    generated_case_count: int = Field(ge=1)
    mutation_validity_rate: float = Field(ge=0, le=1)
    minimality_pass_rate: float = Field(ge=0, le=1)
    mean_minimality_score: float = Field(ge=0, le=1)
    detection_f1: float = Field(ge=0, le=1)
    root_cause_f1: float = Field(ge=0, le=1)
    failure_closure_f1: float = Field(ge=0, le=1)
    domain_reports: dict[str, CounterfactualCalibrationReport]
    status: str
    failures: tuple[str, ...] = ()

    @property
    def report_hash(self) -> str:
        return canonical_hash(self, prefix="counterfactual_validation_suite:")


def run_counterfactual_validation(
    *,
    tasks_per_domain: int = 10,
) -> CounterfactualValidationSuiteReport:
    cases = (
        *build_finance_counterfactual_cases(count=tasks_per_domain),
        *build_pattern_validation_cases(per_domain=tasks_per_domain),
    )
    grouped: dict[str, list[tuple[CounterfactualContext, QualityContractRuntime]]] = defaultdict(
        list
    )
    registries = {}
    for case in cases:
        context, runtime = compile_counterfactual_context(case)
        grouped[case.domain].append((context, runtime))
        registries[case.domain] = case.counterfactual_registry

    reports = {}
    for domain, items in sorted(grouped.items()):
        runtime_by_task = {context.task.task_id: runtime for context, runtime in items}

        def evaluate_counterfactual(
            context: CounterfactualContext,
            trajectory: Trajectory,
            runtimes: dict[str, QualityContractRuntime] = runtime_by_task,
        ) -> ContractQualityAssessment:
            return runtimes[context.task.task_id].evaluate(
                context.contract,
                context.task,
                context.corpus,
                context.proof_graph,
                trajectory,
            )

        report, _ = calibrate_counterfactuals(
            (context for context, _ in items),
            registries[domain],
            evaluate_counterfactual,
        )
        reports[domain] = report
    failures = tuple(
        f"{domain}:{failure}" for domain, report in reports.items() for failure in report.failures
    )
    identity = {
        "suite_version": COUNTERFACTUAL_VALIDATION_SUITE_VERSION,
        "tasks_per_domain": tasks_per_domain,
        "calibration_ids": {domain: report.calibration_id for domain, report in reports.items()},
    }
    return CounterfactualValidationSuiteReport(
        suite_id=canonical_hash(identity, prefix="counterfactual_validation_suite:"),
        suite_version=COUNTERFACTUAL_VALIDATION_SUITE_VERSION,
        tasks_per_domain=tasks_per_domain,
        domain_task_counts={domain: len(items) for domain, items in sorted(grouped.items())},
        source_sample_count=sum(item.source_sample_count for item in reports.values()),
        generated_case_count=sum(item.generated_case_count for item in reports.values()),
        mutation_validity_rate=_mean(reports, "mutation_validity_rate"),
        minimality_pass_rate=_mean(reports, "minimality_pass_rate"),
        mean_minimality_score=_mean(reports, "mean_minimality_score"),
        detection_f1=_mean(reports, "detection_f1"),
        root_cause_f1=_mean(reports, "root_cause_f1"),
        failure_closure_f1=_mean(reports, "failure_closure_f1"),
        domain_reports=reports,
        status="passed" if not failures else "failed",
        failures=failures,
    )


def compile_counterfactual_context(
    case: ContractCase,
) -> tuple[CounterfactualContext, QualityContractRuntime]:
    compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(case.task, case.bundle, case.proof_graph)
    candidate_generator = (
        FinanceNumericCandidateGenerator()
        if case.domain == "finance"
        else PlanGivenContractCandidate(case.registry)
    )
    candidate = candidate_generator.generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=(FinanceClaimVerifier() if case.domain == "finance" else None),
    )
    runtime = QualityContractRuntime(
        verifier,
        verifier_registry=compiler.verifier_registry,
    )
    return (
        CounterfactualContext(
            source_sample=compiled.sample,
            task=case.task,
            contract=compiled.quality_contract,
            corpus=case.corpus,
            proof_graph=case.proof_graph,
            source_trajectory=candidate,
        ),
        runtime,
    )


def _mean(
    reports: dict[str, CounterfactualCalibrationReport],
    field: str,
) -> float:
    return mean(float(getattr(item, field)) for item in reports.values())
