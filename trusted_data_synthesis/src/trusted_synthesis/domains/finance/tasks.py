from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.binding import EvidenceBinding, make_evidence_binding
from trusted_synthesis.core.task.materialization import temporal_sort_key
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import (
    TaskPatternCompiler,
    TaskPatternInstantiation,
)
from trusted_synthesis.core.task.schema import TaskPackage, VerifierRequirement
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.patterns import finance_task_patterns


class FinanceTaskPlugin:
    """Finance semantics over universal declarative Task Pattern compilation."""

    plugin_id = "finance_tasks.v2"
    task_family_ids = (
        "fact_retrieval",
        "comparison",
        "temporal_growth",
        "temporal_average",
        "temporal_absolute_change",
        "registered_ratio",
        "derived_growth_comparison",
    )

    def __init__(
        self,
        *,
        allow_structured_claims: bool = False,
        source_grounding_requirement: VerifierRequirement = VerifierRequirement.NOT_APPLICABLE,
    ) -> None:
        registry = default_registry()
        patterns = finance_task_patterns(
            allow_structured_claims=allow_structured_claims,
            source_grounding_requirement=source_grounding_requirement,
        )
        self._patterns = {pattern.task_type: pattern for pattern in patterns}
        self._compiler = TaskPatternCompiler(registry, FinanceTaskPatternRuntime())

    @staticmethod
    def operation_registry() -> OperationRegistry:
        return default_registry()

    @property
    def pattern_manifest(self) -> tuple[TaskPatternSpec, ...]:
        return tuple(self._patterns[key] for key in sorted(self._patterns))

    def fact_retrieval(
        self, proof_graph: ProofGraph, bundle: EvidenceBundle, evidence_id: str
    ) -> TaskPackage:
        return self._compile(
            "fact_retrieval",
            proof_graph,
            bundle,
            {"fact": (evidence_id,)},
        ).task

    def comparison(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left_evidence_id: str,
        right_evidence_id: str,
    ) -> TaskPackage:
        return self._compile(
            "comparison",
            proof_graph,
            bundle,
            {"left": (left_evidence_id,), "right": (right_evidence_id,)},
        ).task

    def temporal_growth(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        earlier_evidence_id: str,
        later_evidence_id: str,
    ) -> TaskPackage:
        return self._compile(
            "temporal_growth",
            proof_graph,
            bundle,
            {"earlier": (earlier_evidence_id,), "later": (later_evidence_id,)},
        ).task

    def temporal_absolute_change(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        earlier_evidence_id: str,
        later_evidence_id: str,
    ) -> TaskPackage:
        return self._compile(
            "temporal_absolute_change",
            proof_graph,
            bundle,
            {"earlier": (earlier_evidence_id,), "later": (later_evidence_id,)},
        ).task

    def registered_ratio(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        numerator_evidence_id: str,
        denominator_evidence_id: str,
        *,
        registered_pair: str,
    ) -> TaskPackage:
        return self._compile(
            "registered_ratio",
            proof_graph,
            bundle,
            {
                "numerator": (numerator_evidence_id,),
                "denominator": (denominator_evidence_id,),
            },
            node_parameters={"result": {"registered_pair": registered_pair}},
        ).task

    def derived_growth_comparison(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left_earlier_evidence_id: str,
        left_later_evidence_id: str,
        right_earlier_evidence_id: str,
        right_later_evidence_id: str,
    ) -> TaskPackage:
        return self._compile(
            "derived_growth_comparison",
            proof_graph,
            bundle,
            {
                "left_earlier": (left_earlier_evidence_id,),
                "left_later": (left_later_evidence_id,),
                "right_earlier": (right_earlier_evidence_id,),
                "right_later": (right_later_evidence_id,),
            },
        ).task

    def temporal_average(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        evidence_ids: tuple[str, ...],
    ) -> TaskPackage:
        by_id = {item.evidence_id: item for item in bundle.evidence}
        try:
            ordered_ids = tuple(
                item.evidence_id
                for item in sorted(
                    (by_id[evidence_id] for evidence_id in evidence_ids),
                    key=temporal_sort_key,
                )
            )
        except KeyError as exc:
            raise ValueError(f"evidence not found in bundle: {exc.args[0]}") from exc
        return self._compile(
            "temporal_average",
            proof_graph,
            bundle,
            {"series": ordered_ids},
        ).task

    def compile_binding(
        self,
        task_type: str,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        binding: EvidenceBinding,
    ) -> TaskPatternInstantiation:
        return self._compiler.compile(
            self._patterns[task_type],
            binding,
            bundle,
            proof_graph,
        )

    def _compile(
        self,
        task_type: str,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        role_bindings: dict[str, tuple[str, ...]],
        *,
        node_parameters: dict[str, dict[str, object]] | None = None,
    ) -> TaskPatternInstantiation:
        pattern = self._patterns[task_type]
        binding = make_evidence_binding(
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern.pattern_hash,
            role_bindings=role_bindings,
            source_graph_id=proof_graph.graph_id,
            domain_snapshot_id=proof_graph.source_build_id,
            node_parameters=node_parameters,
        )
        return self._compiler.compile(pattern, binding, bundle, proof_graph)
