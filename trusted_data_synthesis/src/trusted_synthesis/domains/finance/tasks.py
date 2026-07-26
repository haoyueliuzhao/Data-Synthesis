from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.schema import TaskPackage, VerifierRequirement
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy


class FinanceTaskPlugin:
    """Finance binding policy over reusable scalar task patterns."""

    plugin_id = "finance_tasks.v1"
    task_family_ids = (
        "fact_retrieval",
        "comparison",
        "temporal_growth",
        "temporal_average",
    )

    def __init__(
        self,
        *,
        allow_structured_claims: bool = False,
        source_grounding_requirement: VerifierRequirement = VerifierRequirement.NOT_APPLICABLE,
    ) -> None:
        self._patterns = ProofGraphTaskSynthesizer(
            FinanceSemanticPolicy(),
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
        )

    def operation_registry(self) -> OperationRegistry:
        return default_registry()

    def fact_retrieval(
        self, proof_graph: ProofGraph, bundle: EvidenceBundle, evidence_id: str
    ) -> TaskPackage:
        return self._patterns.fact_retrieval(proof_graph, bundle, evidence_id)

    def comparison(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left_evidence_id: str,
        right_evidence_id: str,
    ) -> TaskPackage:
        return self._patterns.comparison(
            proof_graph,
            bundle,
            left_evidence_id,
            right_evidence_id,
        )

    def temporal_growth(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        earlier_evidence_id: str,
        later_evidence_id: str,
    ) -> TaskPackage:
        return self._patterns.temporal_growth(
            proof_graph,
            bundle,
            earlier_evidence_id,
            later_evidence_id,
        )

    def temporal_average(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        evidence_ids: tuple[str, ...],
    ) -> TaskPackage:
        return self._patterns.temporal_average(proof_graph, bundle, evidence_ids)
