from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class LookupOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 1:
            return _failure("lookup_arity")
        expected = {
            "selected_ref": inputs[0].ref_id,
            "payload": _json_value_independent(inputs[0].value),
        }
        return _compare(expected, observed_output)


class CompareOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _failure("compare_arity")
        left, right = (_number_independent(item.value) for item in inputs)
        higher = None
        if left > right:
            higher = inputs[0].ref_id
        elif right > left:
            higher = inputs[1].ref_id
        expected = {"higher_ref": higher, "difference": str(max(left, right) - min(left, right))}
        return _compare(expected, observed_output)


class DifferenceOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _failure("difference_arity")
        expected = {
            "value": str(
                _number_independent(inputs[1].value) - _number_independent(inputs[0].value)
            )
        }
        return _compare(expected, observed_output)


class RatioOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _failure("ratio_arity")
        denominator = _number_independent(inputs[1].value)
        if denominator == 0:
            return _failure("denominator_non_zero")
        expected = {"value": str(_number_independent(inputs[0].value) / denominator)}
        return _compare(expected, observed_output)


class GrowthOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _failure("growth_arity")
        first = _number_independent(inputs[0].value)
        second = _number_independent(inputs[1].value)
        if first == 0:
            return _failure("base_non_zero")
        expected = {"value": str((second - first) / abs(first) * Decimal("100"))}
        return _compare(expected, observed_output)


class AggregateOracleVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if not inputs:
            return _failure("aggregate_non_empty")
        method = str(parameters.get("method") or "mean")
        values = [_number_independent(item.value) for item in inputs]
        if method == "mean":
            result = sum(values, Decimal("0")) / Decimal(len(values))
        elif method == "sum":
            result = sum(values, Decimal("0"))
        else:
            return _failure("aggregate_method_registered")
        return _compare({"method": method, "value": str(result)}, observed_output)


def _number_independent(value: Any) -> Decimal:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        nested = value.get("payload")
        value = value.get("value", nested.get("value") if isinstance(nested, dict) else value)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"oracle input is not numeric: {value!r}") from exc


def _json_value_independent(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def _compare(expected: dict[str, Any], observed: dict[str, Any]) -> OperationVerification:
    passed = expected == observed
    return OperationVerification(
        passed=passed,
        expected_output=expected,
        invariant_failures=() if passed else ("output_mismatch",),
        message="Operation output verified" if passed else "Operation output mismatch",
    )


def _failure(invariant: str) -> OperationVerification:
    return OperationVerification(
        passed=False,
        invariant_failures=(invariant,),
        message=f"Operation invariant failed: {invariant}",
    )
