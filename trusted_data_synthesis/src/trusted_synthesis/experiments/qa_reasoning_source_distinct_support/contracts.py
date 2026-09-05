"""Inspect exact existing primitive contracts without admitting or executing a binding."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from trusted_synthesis.core.operations.registry import operation_semantic_contract
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    catalog_operation_registry,
)

from .models import identified, require

REGISTRY_PATH = "trusted_data_synthesis/src/trusted_synthesis/core/operations/registry.py"
EXECUTOR_PATH = "trusted_data_synthesis/src/trusted_synthesis/core/operations/executors/numeric.py"


def inspect_registry(repo_root: Path) -> dict[str, Any]:
    registry = catalog_operation_registry()
    semantics = {
        name: operation_semantic_contract(registry.require(name))
        for name in (
            "aggregate",
            "growth",
            "signed_percentage_point_gap",
            "absolute_percentage_point_gap",
        )
    }
    registry_tree = ast.parse((repo_root / REGISTRY_PATH).read_text())
    owner = next(
        n
        for n in registry_tree.body
        if isinstance(n, ast.ClassDef) and n.name == "OperationRegistry"
    )
    method = next(
        n
        for n in owner.body
        if isinstance(n, ast.FunctionDef) and n.name == "validate_compatibility"
    )
    compatibility: dict[str, list[str]] = {}
    for node in ast.walk(method):
        if not (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "policy"
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
        ):
            continue
        policy = node.test.comparators[0].value
        if policy not in {"same_metric_unit_definition", "same_series"}:
            continue
        for statement in node.body:
            if (
                isinstance(statement, ast.Assign)
                and isinstance(statement.value, ast.Tuple)
                and any(
                    isinstance(target, ast.Name) and target.id == "fields"
                    for target in statement.targets
                )
            ):
                compatibility[policy] = [
                    str(ast.literal_eval(value)) for value in statement.value.elts
                ]
    executor_tree = ast.parse((repo_root / EXECUTOR_PATH).read_text())
    aggregate = next(
        n
        for n in executor_tree.body
        if isinstance(n, ast.ClassDef) and n.name == "AggregateExecutor"
    )
    execute = next(
        n for n in aggregate.body if isinstance(n, ast.FunctionDef) and n.name == "execute"
    )
    assignment = next(
        n
        for n in execute.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "method" for t in n.targets)
    )
    constants = [n.value for n in ast.walk(assignment) if isinstance(n, ast.Constant)]
    require(
        semantics["aggregate"]["semantic_version"] == "1.1.0"
        and semantics["aggregate"]["input_order_policy"] == "permutation_invariant"
        and semantics["aggregate"]["compatibility_policy"] == "same_metric_unit_definition"
        and semantics["aggregate"]["input_role_contract"] == ("observations",)
        and "method" in constants
        and "mean" in constants,
        "registry.aggregate",
        "exact aggregate primitive contract differs",
    )
    require(
        compatibility.get("same_metric_unit_definition")
        == ["predicate", "payload_context", "definition"]
        and compatibility.get("same_series")
        == [
            "subject",
            "predicate",
            "payload_context",
            "definition",
            "time_basis",
            "frequency",
            "scope_type",
        ],
        "registry.compatibility",
        "actual compatibility field clauses differ",
    )
    return identified(
        {
            "inspection_only": True,
            "registered_semantics": semantics,
            "compatibility_fields_derived_from_actual_ast": compatibility,
            "aggregate_default_method_from_actual_ast": "mean",
            "prospective_reconstruction_must_explicitly_request_sum": True,
            "primitive_proves_exhaustiveness_or_nonoverlap": False,
            "source_complete_disjoint_period_scope_and_no_elimination_required": True,
            "raw_scalar_evidence_compatibility_may_not_be_bypassed": True,
            "source_identity_copies_are_not_distinct_components": True,
            "actual_task_specific_compatibility_admission": None,
            "actual_task_specific_compatibility_status": "not_evaluated_source_not_instantiated",
            "new_primitive_or_catalog_registration": 0,
            "new_task_or_composition_contract_materialized": 0,
            "primitive_executor_calls": 0,
            "primitive_oracle_calls": 0,
            "prior_four_evidence_runtime_not_used_as_new_support_route_validator": True,
            "prior_ordered_empty_parameter_projection_not_assumed_to_support_aggregate": True,
            "passed_at_metadata_inspection_scope": True,
        },
        "primitive_contract_inspection",
    )
