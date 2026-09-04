from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class PercentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str
    unit: str


class PercentagePointOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str
    unit: str


class ScaleRatioPercentExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        del parameters
        if len(inputs) != 1:
            raise ValueError("scale-ratio-percent requires one input")
        return {"value": str(_number(inputs[0].value) * Decimal("100")), "unit": "percent"}


class ScaleRatioPercentOracle:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        del parameters
        if len(inputs) != 1:
            return _failure("scale_ratio_percent_arity")
        expected = {
            "value": str(_oracle_number(inputs[0].value) * Decimal("100")),
            "unit": "percent",
        }
        return _comparison(expected, observed_output)


class SignedPercentagePointGapExecutor:
    """Return observed minus reference in percentage points."""

    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        del parameters
        if len(inputs) != 2:
            raise ValueError("signed-percentage-point-gap requires two inputs")
        reference, observed = (_number(item.value) for item in inputs)
        return {"value": str(observed - reference), "unit": "percentage_points"}


class SignedPercentagePointGapOracle:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        del parameters
        if len(inputs) != 2:
            return _failure("signed_percentage_point_gap_arity")
        reference = _oracle_number(inputs[0].value)
        observed = _oracle_number(inputs[1].value)
        return _comparison(
            {"value": str(observed - reference), "unit": "percentage_points"},
            observed_output,
        )


class AbsolutePercentagePointGapExecutor:
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        del parameters
        if len(inputs) != 1:
            raise ValueError("absolute-percentage-point-gap requires one input")
        return {"value": str(abs(_number(inputs[0].value))), "unit": "percentage_points"}


class AbsolutePercentagePointGapOracle:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        del parameters
        if len(inputs) != 1:
            return _failure("absolute_percentage_point_gap_arity")
        return _comparison(
            {
                "value": str(abs(_oracle_number(inputs[0].value))),
                "unit": "percentage_points",
            },
            observed_output,
        )


def depth_three_operation_registry(
    *, scale_ratio_program_role: str = "semantic"
) -> OperationRegistry:
    base = default_registry()
    base.register(
        make_operation_definition(
            "scale_ratio_percent",
            ScaleRatioPercentExecutor(),
            ScaleRatioPercentOracle(),
            "one:numeric",
            "percentage",
            "none",
            ("arity=1", "ratio_to_percent_exact"),
            output_model=PercentOutput,
            tool_capability="calculator",
            input_role_contract=("ratio_scalar",),
            parameter_contract=("parameters must be empty",),
            downstream_selector_contract=("numeric consumers must select value",),
            program_role=scale_ratio_program_role,
            semantic_version="1.0.0",
            formula_id="ratio_to_percent.multiply_100.v1",
        )
    )
    base.register(
        make_operation_definition(
            "signed_percentage_point_gap",
            SignedPercentagePointGapExecutor(),
            SignedPercentagePointGapOracle(),
            "two:numeric",
            "scalar",
            "none",
            ("arity=2", "observed_minus_reference"),
            output_model=PercentagePointOutput,
            tool_capability="calculator",
            input_role_contract=("reference_percent", "observed_percent"),
            parameter_contract=("parameters must be empty",),
            downstream_selector_contract=("numeric consumers must select value",),
            semantic_version="1.0.0",
            formula_id="percentage_point_gap.observed_minus_reference.v1",
        )
    )
    base.register(
        make_operation_definition(
            "absolute_percentage_point_gap",
            AbsolutePercentagePointGapExecutor(),
            AbsolutePercentagePointGapOracle(),
            "one:numeric",
            "scalar",
            "none",
            ("arity=1", "absolute_magnitude"),
            output_model=PercentagePointOutput,
            tool_capability="calculator",
            input_role_contract=("signed_percentage_point_gap",),
            parameter_contract=("parameters must be empty",),
            semantic_version="1.0.0",
            formula_id="percentage_point_gap.absolute_value.v1",
        )
    )
    return base


def _number(value: Any) -> Decimal:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        nested = value.get("payload")
        value = value.get("value", nested.get("value") if isinstance(nested, dict) else value)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"depth-three operation input is not numeric: {value!r}") from exc


def _oracle_number(value: Any) -> Decimal:
    """Independent numeric projection for the oracle implementation."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        if "value" in value:
            value = value["value"]
        else:
            payload = value.get("payload")
            value = payload.get("value") if isinstance(payload, dict) else value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"depth-three oracle input is not numeric: {value!r}") from exc


def _comparison(expected: dict[str, Any], observed: dict[str, Any]) -> OperationVerification:
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
