from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.operations.schema import OperationInput


class LookupExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        _require_arity(inputs, 1)
        return {"selected_ref": inputs[0].ref_id, "payload": _json_value(inputs[0].value)}


class CompareExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        _require_arity(inputs, 2)
        left, right = (_number(item.value) for item in inputs)
        higher = None if left == right else inputs[0].ref_id if left > right else inputs[1].ref_id
        return {"higher_ref": higher, "difference": str(abs(left - right))}


class DifferenceExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        _require_arity(inputs, 2)
        return {"value": str(_number(inputs[1].value) - _number(inputs[0].value))}


class RatioExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        _require_arity(inputs, 2)
        denominator = _number(inputs[1].value)
        if denominator == 0:
            raise ValueError("ratio denominator must be non-zero")
        return {"value": str(_number(inputs[0].value) / denominator)}


class GrowthExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        _require_arity(inputs, 2)
        base = _number(inputs[0].value)
        if base == 0:
            raise ValueError("growth base must be non-zero")
        return {"value": str((_number(inputs[1].value) - base) / abs(base) * Decimal("100"))}


class AggregateExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        if not inputs:
            raise ValueError("aggregate requires at least one input")
        method = str(parameters.get("method") or "mean")
        values = [_number(item.value) for item in inputs]
        if method == "mean":
            return {"method": method, "value": str(sum(values) / len(values))}
        if method == "sum":
            return {"method": method, "value": str(sum(values))}
        raise ValueError(f"unsupported aggregate method: {method}")


def _require_arity(inputs: tuple[OperationInput, ...], expected: int) -> None:
    if len(inputs) != expected:
        raise ValueError(f"expected {expected} inputs, received {len(inputs)}")


def _number(value: Any) -> Decimal:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        if "value" in value:
            value = value["value"]
        elif isinstance(value.get("payload"), dict) and "value" in value["payload"]:
            value = value["payload"]["value"]
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"operation input is not numeric: {value!r}") from exc


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value
