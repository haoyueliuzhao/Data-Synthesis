from __future__ import annotations

from trusted_synthesis.core.operations.executors import (
    AggregateExecutor,
    CompareExecutor,
    DifferenceExecutor,
    GrowthExecutor,
    LookupExecutor,
    RatioExecutor,
)
from trusted_synthesis.core.operations.schema import OperationDefinition
from trusted_synthesis.core.operations.verifiers import (
    AggregateOracleVerifier,
    CompareOracleVerifier,
    DifferenceOracleVerifier,
    GrowthOracleVerifier,
    LookupOracleVerifier,
    RatioOracleVerifier,
)


class OperationRegistry:
    def __init__(self, definitions: tuple[OperationDefinition, ...] = ()) -> None:
        self._definitions: dict[str, OperationDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: OperationDefinition) -> None:
        if definition.operator_id in self._definitions:
            raise ValueError(f"operation already registered: {definition.operator_id}")
        self._definitions[definition.operator_id] = definition

    def require(self, operator_id: str) -> OperationDefinition:
        try:
            return self._definitions[operator_id]
        except KeyError as exc:
            raise ValueError(f"unknown operation: {operator_id}") from exc

    def manifest(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "operator_id": item.operator_id,
                "input_schema": item.input_schema,
                "output_schema": item.output_schema,
                "compatibility_policy": item.compatibility_policy,
                "invariant_checks": item.invariant_checks,
                "executor": type(item.executor).__name__,
                "oracle_verifier": type(item.oracle_verifier).__name__,
            }
            for item in sorted(self._definitions.values(), key=lambda value: value.operator_id)
        )


def default_registry() -> OperationRegistry:
    definitions = (
        _definition(
            "lookup",
            LookupExecutor(),
            LookupOracleVerifier(),
            "one:any",
            "payload",
            "none",
            ("arity=1",),
        ),
        _definition(
            "compare",
            CompareExecutor(),
            CompareOracleVerifier(),
            "two:numeric",
            "comparison",
            "same_unit_and_definition",
            ("arity=2",),
        ),
        _definition(
            "difference",
            DifferenceExecutor(),
            DifferenceOracleVerifier(),
            "two:numeric",
            "scalar",
            "same_unit_and_definition",
            ("arity=2",),
        ),
        _definition(
            "ratio",
            RatioExecutor(),
            RatioOracleVerifier(),
            "two:numeric",
            "scalar",
            "registered_ratio_pair",
            ("arity=2", "denominator_non_zero"),
        ),
        _definition(
            "growth",
            GrowthExecutor(),
            GrowthOracleVerifier(),
            "two:ordered_numeric",
            "percentage",
            "same_series",
            ("arity=2", "base_non_zero"),
        ),
        _definition(
            "aggregate",
            AggregateExecutor(),
            AggregateOracleVerifier(),
            "many:numeric",
            "scalar",
            "same_metric_unit_definition",
            ("non_empty", "method_registered"),
        ),
    )
    return OperationRegistry(definitions)


def _definition(
    operator_id,
    executor,
    verifier,
    input_schema,
    output_schema,
    compatibility_policy,
    invariants,
) -> OperationDefinition:
    return OperationDefinition(
        operator_id=operator_id,
        executor=executor,
        oracle_verifier=verifier,
        input_schema=input_schema,
        output_schema=output_schema,
        compatibility_policy=compatibility_policy,
        invariant_checks=invariants,
    )
