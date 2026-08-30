from __future__ import annotations

from trusted_synthesis.core.operations.executors import CompareExecutor
from trusted_synthesis.core.operations.registry import (
    ComparisonOutput,
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.verifiers import CompareOracleVerifier


def finance_vnext_operation_registry() -> OperationRegistry:
    registry = default_registry()
    registry.register(
        make_operation_definition(
            "registered_compare",
            CompareExecutor(),
            CompareOracleVerifier(),
            "two:numeric",
            "comparison",
            "registered_comparison_pair",
            (
                "arity=2",
                "registered_metric_pair",
                "same_subject_period_scope_source_and_payload_context",
            ),
            output_model=ComparisonOutput,
            tool_capability="calculator",
            input_role_contract=("left_registered_metric", "right_registered_metric"),
            parameter_contract=(
                "registered_pair is required and must equal <left predicate>/<right predicate>",
            ),
            downstream_selector_contract=(
                "select higher_ref or difference explicitly when consumed downstream",
            ),
            semantic_version="1.0.0",
            formula_id="registered_compare.absolute_difference.v1",
        )
    )
    return registry
