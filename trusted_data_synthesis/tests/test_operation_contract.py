from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evaluation.evaluator import ReferenceQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.program import ProgramExecutionError
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler


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
