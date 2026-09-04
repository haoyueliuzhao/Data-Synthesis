from __future__ import annotations

from dataclasses import dataclass

import pytest

from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateVerificationReport,
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.finance_pilot.candidate import (
    CANDIDATE_GENERATOR_VERSION,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.qa_semantic_coverage.preflight import _fixture_bundles
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime


@dataclass(frozen=True)
class _TotalityRow:
    task_type: str
    trajectory: Trajectory
    verification: CandidateVerificationReport
    assessment: QualityAssessment
    node_ids: tuple[str, ...]


@pytest.fixture(scope="module")
def totality_rows() -> dict[str, _TotalityRow]:
    plugin = FinanceTaskPlugin()
    registry = finance_vnext_operation_registry()
    policy = FinanceSemanticPolicy()
    generator = FinanceNumericCandidateGenerator()
    rows: dict[str, _TotalityRow] = {}

    for task_type, _registered_pair, bundle in _fixture_bundles():
        if task_type in rows:
            continue
        graph = ProofGraphBuilder().build(bundle)
        instantiation = plugin.compile_evidence_ids(
            task_type,
            graph,
            bundle,
            tuple(item.evidence_id for item in bundle.evidence),
        )
        realization = plugin.realize_instantiation(
            instantiation,
            graph,
            bundle,
            max_realizations=1,
        ).selected[0]
        corpus = EvidenceCorpus.from_bundle(bundle)
        trajectory = generator.generate(
            realization.task.public,
            InMemoryEvidenceToolRuntime(corpus),
        )
        verifier = CandidateWorkflowVerifier(
            registry=registry,
            semantic_policy=policy,
        ).verify(realization.task, corpus, graph, trajectory)
        assessment = CandidateQualityEvaluator(
            semantic_policy=policy,
            workflow_verifier=CandidateWorkflowVerifier(registry=registry, semantic_policy=policy),
        ).evaluate(realization.task, corpus, graph, trajectory)
        rows[task_type] = _TotalityRow(
            task_type=task_type,
            trajectory=trajectory,
            verification=verifier,
            assessment=assessment,
            node_ids=tuple(node.node_id for node in realization.task.oracle.task_program.nodes),
        )

    return rows


def test_registered_eight_task_generator_verifier_evaluator_totality(
    totality_rows: dict[str, _TotalityRow],
) -> None:
    assert CANDIDATE_GENERATOR_VERSION == "finance_numeric_candidate.v7"
    assert set(totality_rows) == {
        "comparison",
        "derived_growth_comparison",
        "fact_retrieval",
        "registered_cross_metric_comparison",
        "registered_ratio",
        "temporal_absolute_change",
        "temporal_average",
        "temporal_growth",
    }

    for row in totality_rows.values():
        trajectory = row.trajectory
        operation_steps = tuple(
            step
            for step in trajectory.steps
            if step.program_node_id is not None
            and step.action.value in {"select_evidence", "calculate"}
        )
        assert row.verification.passed
        assert row.verification.execution_coverage == 1
        assert row.verification.operation_grounding_score == 1
        assert row.assessment.decision == ReleaseDecision.ACCEPTED
        assert trajectory.final_answer["result"].get("status") != "insufficient_capability"
        assert tuple(step.program_node_id for step in operation_steps) == row.node_ids
        assert set(trajectory.program_execution["node_outputs"]) == set(row.node_ids)
        assert all(
            status.executed and status.grounded and status.verified
            for status in row.verification.program_node_statuses
        )


def test_previously_missing_registered_task_answers_are_exact(
    totality_rows: dict[str, _TotalityRow],
) -> None:
    assert totality_rows["temporal_absolute_change"].trajectory.final_answer["result"] == {
        "value": "18"
    }
    assert totality_rows["registered_ratio"].trajectory.final_answer["result"] == {"value": "0.5"}
    assert totality_rows["derived_growth_comparison"].trajectory.final_answer["result"] == {
        "selected_entity_id": "QA_SEMANTIC_A",
        "selected_entity_name": "QA Semantic Company A",
        "left_entity_id": "QA_SEMANTIC_A",
        "left_entity_name": "QA Semantic Company A",
        "left_growth_pct": "35",
        "right_entity_id": "QA_SEMANTIC_B",
        "right_entity_name": "QA Semantic Company B",
        "right_growth_pct": "20",
        "difference_percentage_points": "15",
    }


def test_registered_task_program_node_counts_are_preserved(
    totality_rows: dict[str, _TotalityRow],
) -> None:
    assert {task_type: len(row.node_ids) for task_type, row in totality_rows.items()} == {
        "fact_retrieval": 1,
        "comparison": 1,
        "temporal_growth": 3,
        "temporal_average": 4,
        "temporal_absolute_change": 3,
        "registered_ratio": 3,
        "derived_growth_comparison": 7,
        "registered_cross_metric_comparison": 1,
    }
