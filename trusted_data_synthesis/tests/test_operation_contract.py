from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evaluation.evaluator import ReferenceQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.program import (
    ProgramExecutionError,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import OperationContractError, default_registry
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.domains.science import operations as science_operations
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
)


def _task(finance_evidence: EvidenceItem):
    bundle = EvidenceBundle(
        bundle_id="bundle_operation_contract",
        evidence=(finance_evidence,),
        purpose="operation contract",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    return bundle, task


@pytest.mark.parametrize(
    ("field", "value"),
    (("verifier_id", "wrong.oracle.v9"), ("output_schema", "comparison")),
)
def test_node_contract_mutations_fail_closed(
    finance_evidence: EvidenceItem, field: str, value: str
) -> None:
    bundle, task = _task(finance_evidence)
    node = task.oracle.task_program.nodes[0].model_copy(update={field: value})
    program = task.oracle.task_program.model_copy(update={"nodes": (node,)})
    mutated_task = task.model_copy(
        update={"oracle": task.oracle.model_copy(update={"task_program": program})}
    )

    with pytest.raises(ProgramExecutionError, match="execution_contract"):
        ReferenceWorkflowCompiler().compile(mutated_task, bundle)


def test_operation_manifest_freezes_implementation_contract() -> None:
    for operation in default_registry().manifest():
        assert operation["verifier_id"] == f"{operation['operator_id']}.oracle.v1"
        assert operation["implementation_hash"]
        assert operation["executor_version"] == "1.0.0"
        assert operation["verifier_version"]
        assert operation["semantic_version"]
        assert operation["rounding_policy"]
        assert operation["tolerance_policy"]


def test_growth_replay_uses_the_frozen_decimal_operation_order(
    finance_evidence: EvidenceItem,
) -> None:
    earlier = finance_evidence.model_copy(
        update={
            "payload": ScalarObservation(
                value=Decimal("1.13"),
                unit="USD_per_share",
                currency="USD",
            )
        }
    )
    later = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:growth_later@kg_test",
            "assertion_id": "assertion:finance:growth_later",
            "evidence_version_id": "version:finance:growth_later@kg_test",
            "payload": ScalarObservation(
                value=Decimal("1.62"),
                unit="USD_per_share",
                currency="USD",
            ),
            "temporal_context": TemporalContext(
                label="FY2024",
                valid_from=date(2023, 10, 1),
                valid_to=date(2024, 9, 30),
                basis="fiscal_period",
                frequency="annual",
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "growth_later"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_decimal_growth",
        evidence=(earlier, later),
        purpose="decimal growth replay",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().temporal_growth(
        graph,
        bundle,
        earlier.evidence_id,
        later.evidence_id,
    )
    reference = ReferenceWorkflowCompiler().compile(task, bundle)
    assessment = ReferenceQualityEvaluator().evaluate(task, bundle, graph, reference)

    assert assessment.decision == ReleaseDecision.ACCEPTED
    growth = next(
        operation
        for operation in default_registry().manifest()
        if operation["operator_id"] == "growth"
    )
    assert growth["verifier_version"] == "1.0.1"
    assert growth["formula_id"] == "growth.relative_change_abs_base.v1"


def test_non_finance_oracle_rejects_missing_observed_node_output() -> None:
    for case in build_contract_cases():
        oracle = TaskProgramOracleVerifier(case.registry)
        evidence_by_id = {item.evidence_id: item for item in case.bundle.evidence}
        expected = oracle.derive_expected(case.task.oracle.task_program, evidence_by_id)
        observed = dict(expected.node_outputs)
        observed.pop(case.task.oracle.task_program.nodes[0].node_id)

        report = oracle.verify(case.task.oracle.task_program, evidence_by_id, observed)

        assert not report.passed
        assert not report.node_statuses[case.task.oracle.task_program.nodes[0].node_id]


def test_structured_operation_outputs_are_strict_and_helpers_are_hashed() -> None:
    for case in build_contract_cases():
        oracle = TaskProgramOracleVerifier(case.registry)
        evidence_by_id = {item.evidence_id: item for item in case.bundle.evidence}
        expected = oracle.derive_expected(case.task.oracle.task_program, evidence_by_id)
        first_node = case.task.oracle.task_program.nodes[0]
        definition = case.registry.require(first_node.operator_id)
        extra = {**expected.node_outputs[first_node.node_id], "unexpected": True}

        with pytest.raises(OperationContractError, match="output schema mismatch"):
            case.registry.validate_output(definition, extra)

        manifest = next(
            item
            for item in case.registry.manifest()
            if item["operator_id"] == first_node.operator_id
        )
        assert manifest["output_model_schema"]["additionalProperties"] is False
        assert manifest["implementation_dependency_ids"]


def test_science_executor_helper_defect_is_caught_by_independent_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = next(item for item in build_contract_cases() if item.domain == "science")
    monkeypatch.setattr(
        science_operations,
        "_executor_intervals_overlap",
        lambda left, right: False,
    )
    reference = ReferenceWorkflowCompiler(case.registry).compile(case.task, case.bundle)

    assessment = ReferenceQualityEvaluator(
        semantic_policy=case.semantic_policy,
        workflow_verifier=ReferenceWorkflowVerifier(case.registry),
    ).evaluate(case.task, case.bundle, case.proof_graph, reference)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "independent_recompute" in assessment.fatal_failures
