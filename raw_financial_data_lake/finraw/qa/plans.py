from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from finraw.qa.operators import OPERATORS, OperatorError, execute_operator


@dataclass(frozen=True)
class PlanExecution:
    output: dict[str, Any]
    intermediate_results: list[dict[str, Any]]
    status: str
    errors: list[str]


def materialize_plan(
    operator_template: dict[str, Any], binding: dict[str, Any]
) -> dict[str, Any]:
    """Apply binding-specific parameters without mutating the pattern template."""
    plan = copy.deepcopy(operator_template)
    if binding.get("operator_params") and plan.get("operators"):
        plan["operators"][0]["params"] = dict(binding["operator_params"])
    step_params = binding.get("operator_step_params") or {}
    for step in plan.get("operators") or []:
        step_id = str(step.get("step_id") or "")
        if step_id in step_params:
            step["params"] = {
                **dict(step.get("params") or {}),
                **dict(step_params[step_id]),
            }
    return plan


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    operators = plan.get("operators")
    if not isinstance(operators, list) or not operators:
        return ["operator_dag must contain at least one operator"]
    step_ids: set[str] = set()
    for index, step in enumerate(operators):
        step_id = str(step.get("step_id") or "")
        operator = str(step.get("operator") or "")
        if not step_id:
            errors.append(f"operators[{index}] is missing step_id")
        elif step_id in step_ids:
            errors.append(f"duplicate step_id: {step_id}")
        step_ids.add(step_id)
        if operator not in OPERATORS:
            errors.append(f"unknown operator: {operator}")
        for reference in step.get("inputs") or []:
            if "step" in reference and str(reference["step"]) not in step_ids:
                errors.append(
                    f"step {step_id} references a non-previous step: {reference['step']}"
                )
    output_step = str(plan.get("output_step") or "")
    if output_step not in step_ids:
        errors.append(f"output_step does not exist: {output_step}")
    return errors


def execute_plan(
    plan: dict[str, Any],
    input_bindings: dict[str, Any],
    facts_by_id: dict[str, dict[str, Any]],
) -> PlanExecution:
    errors = validate_plan(plan)
    if errors:
        return PlanExecution({}, [], "failed", errors)
    results: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    try:
        for step in plan["operators"]:
            resolved = [
                _resolve_input(reference, input_bindings, facts_by_id, results)
                for reference in step.get("inputs") or []
            ]
            output = execute_operator(
                str(step["operator"]), resolved, dict(step.get("params") or {})
            )
            output = _with_answer_lineage(
                output,
                resolved,
                [
                    str(reference["step"])
                    for reference in step.get("inputs") or []
                    if "step" in reference
                ],
            )
            results[str(step["step_id"])] = output
            trace.append(
                {
                    "step_id": str(step["step_id"]),
                    "operator": str(step["operator"]),
                    "input_references": step.get("inputs") or [],
                    "output": output,
                }
            )
    except (KeyError, OperatorError, TypeError, ValueError) as exc:
        return PlanExecution({}, trace, "failed", [str(exc)])
    return PlanExecution(results[str(plan["output_step"])], trace, "passed", [])


def _with_answer_lineage(
    output: dict[str, Any], inputs: list[Any], input_step_ids: list[str]
) -> dict[str, Any]:
    result = dict(output)
    existing = dict(result.get("lineage") or {})
    input_fact_ids = sorted(
        _collect_values(
            inputs,
            {"fact_id", "input_fact_ids", "primary_fact_id", "secondary_fact_id"},
            lineage_field="input_fact_ids",
        )
    )
    selected_fact_ids = sorted(
        _collect_values(
            result,
            {"fact_id", "input_fact_ids", "primary_fact_id", "secondary_fact_id"},
            lineage_field="selected_fact_ids",
        )
    )
    input_entity_ids = sorted(
        _collect_values(
            inputs, {"entity_id", "winner_id"}, lineage_field="input_entity_ids"
        )
    )
    selected_entity_ids = sorted(
        _collect_values(
            result, {"entity_id", "winner_id"}, lineage_field="selected_entity_ids"
        )
    )
    input_periods = sorted(
        _collect_values(
            inputs, {"period", "result_period"}, lineage_field="input_periods"
        )
    )
    selected_periods = sorted(
        _collect_values(
            result, {"period", "result_period"}, lineage_field="selected_periods"
        )
    )
    result["lineage"] = {
        "input_fact_ids": sorted(
            set(existing.get("input_fact_ids") or []) | set(input_fact_ids)
        ),
        "selected_fact_ids": sorted(
            set(existing.get("selected_fact_ids") or []) | set(selected_fact_ids)
        ),
        "input_entity_ids": sorted(
            set(existing.get("input_entity_ids") or []) | set(input_entity_ids)
        ),
        "selected_entity_ids": sorted(
            set(existing.get("selected_entity_ids") or []) | set(selected_entity_ids)
        ),
        "input_periods": sorted(
            set(existing.get("input_periods") or []) | set(input_periods)
        ),
        "selected_periods": sorted(
            set(existing.get("selected_periods") or []) | set(selected_periods)
        ),
        "input_step_ids": sorted(
            set(existing.get("input_step_ids") or []) | set(input_step_ids)
        ),
    }
    return result


def _collect_values(value: Any, keys: set[str], *, lineage_field: str) -> set[str]:
    output: set[str] = set()
    if isinstance(value, dict):
        lineage = value.get("lineage")
        if isinstance(lineage, dict):
            output.update(
                str(item)
                for item in lineage.get(lineage_field) or []
                if item not in {None, ""}
            )
        for key, item in value.items():
            if key == "lineage":
                continue
            if key in keys:
                values = item if isinstance(item, list) else [item]
                output.update(str(entry) for entry in values if entry not in {None, ""})
            else:
                output.update(_collect_values(item, keys, lineage_field=lineage_field))
    elif isinstance(value, list):
        for item in value:
            output.update(_collect_values(item, keys, lineage_field=lineage_field))
    return output


def operation_depth(plan: dict[str, Any]) -> int:
    depths: dict[str, int] = {}
    for step in plan.get("operators") or []:
        dependencies = [
            depths.get(str(reference["step"]), 0)
            for reference in step.get("inputs") or []
            if "step" in reference
        ]
        depths[str(step.get("step_id"))] = 1 + max(dependencies, default=0)
    return max(depths.values(), default=0)


def operation_cost(plan: dict[str, Any]) -> float:
    return sum(
        OPERATORS[str(step["operator"])].difficulty_cost
        for step in plan.get("operators") or []
        if str(step.get("operator")) in OPERATORS
    )


def _resolve_input(
    reference: dict[str, Any],
    bindings: dict[str, Any],
    facts_by_id: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> Any:
    if "step" in reference:
        return results[str(reference["step"])]
    binding_name = str(reference.get("binding") or "")
    if binding_name not in bindings:
        raise KeyError(f"Missing operation input binding: {binding_name}")
    fact_ids = bindings[binding_name]
    if isinstance(fact_ids, dict) and set(fact_ids) == {"__literal__"}:
        return copy.deepcopy(fact_ids["__literal__"])
    if isinstance(fact_ids, list):
        missing = [fact_id for fact_id in fact_ids if str(fact_id) not in facts_by_id]
        if missing:
            raise KeyError(f"Missing bound facts: {missing}")
        return [facts_by_id[str(fact_id)] for fact_id in fact_ids]
    if str(fact_ids) not in facts_by_id:
        raise KeyError(f"Missing bound fact: {fact_ids}")
    return facts_by_id[str(fact_ids)]
