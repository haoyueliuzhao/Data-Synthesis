from __future__ import annotations

import inspect
from typing import Protocol

from trusted_synthesis.core.evaluation.contracts.schema import (
    ClauseMutationSpec,
    QualityClause,
)
from trusted_synthesis.core.evaluation.counterfactual.context import CounterfactualContext
from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualMutationDraft,
    CounterfactualOpportunity,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class CounterfactualOperatorProtocol(Protocol):
    operator_id: str
    operator_version: str
    provider_id: str

    def plan(
        self,
        context: CounterfactualContext,
        clause: QualityClause,
        spec: ClauseMutationSpec,
    ) -> tuple[CounterfactualMutationDraft, ...]: ...

    def apply(
        self,
        context: CounterfactualContext,
        opportunity: CounterfactualOpportunity,
    ) -> Trajectory: ...

    def manifest_parameters(self) -> dict[str, object]: ...


class CounterfactualOperatorRegistry:
    def __init__(
        self,
        operators: tuple[CounterfactualOperatorProtocol, ...] = (),
    ) -> None:
        self._operators: dict[str, CounterfactualOperatorProtocol] = {}
        for operator in operators:
            self.register(operator)

    def register(self, operator: CounterfactualOperatorProtocol) -> None:
        if operator.operator_id in self._operators:
            raise ValueError(
                f"counterfactual operator already registered: {operator.operator_id}"
            )
        self._operators[operator.operator_id] = operator

    def require(
        self,
        operator_id: str,
        operator_version: str | None = None,
    ) -> CounterfactualOperatorProtocol:
        operator = self._operators.get(operator_id)
        if operator is None:
            raise ValueError(f"unknown counterfactual operator: {operator_id}")
        if operator_version is not None and operator.operator_version != operator_version:
            raise ValueError(
                "counterfactual operator version is unavailable: "
                f"{operator_id}@{operator_version}"
            )
        return operator

    def manifest(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "operator_id": operator.operator_id,
                "operator_version": operator.operator_version,
                "provider_id": operator.provider_id,
                "parameters": operator.manifest_parameters(),
                "implementation_hash": canonical_hash(
                    inspect.getsource(type(operator)),
                    prefix="counterfactual_operator_impl:",
                ),
            }
            for operator in sorted(
                self._operators.values(),
                key=lambda item: item.operator_id,
            )
        )

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(
            self.manifest(),
            prefix="counterfactual_operator_manifest:",
        )

    @property
    def operator_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._operators))
