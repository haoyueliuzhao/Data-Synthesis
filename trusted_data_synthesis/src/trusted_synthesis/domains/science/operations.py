from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class ScienceProtocolAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    comparable: bool
    mismatches: list[str]


class ScienceEffectComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    higher_ref: str | None
    difference: str
    uncertainty_intervals_overlap: bool
    qualified_conclusion: str


class ScienceDescriptiveSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    weighted_value: str
    total_sample_size: int
    uncertainty_lower: str
    uncertainty_upper: str
    qualified_conclusion: str


class ProtocolAlignmentExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if len(inputs) != 2:
            raise ValueError("protocol alignment requires two experimental results")
        left, right = (_mapping(item.value) for item in inputs)
        fields = ("metric", "unit", "dataset", "method", "protocol")
        mismatches = [field for field in fields if left.get(field) != right.get(field)]
        return {"comparable": not mismatches, "mismatches": mismatches}


class ProtocolAlignmentVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _verification(None, observed_output, "science_protocol_alignment_arity")
        first = _mapping(inputs[0].value)
        second = _mapping(inputs[1].value)
        compared_fields = ("metric", "unit", "dataset", "method", "protocol")
        mismatches = [field for field in compared_fields if first.get(field) != second.get(field)]
        expected = {"comparable": len(mismatches) == 0, "mismatches": mismatches}
        return _verification(expected, observed_output, "science_protocol_alignment")


class EffectComparisonExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if len(inputs) != 3:
            raise ValueError("effect comparison requires alignment and two results")
        alignment = _mapping(inputs[0].value)
        if not alignment.get("comparable"):
            raise ValueError("experimental protocols are not comparable")
        left = _mapping(inputs[1].value)
        right = _mapping(inputs[2].value)
        left_value = Decimal(str(left["value"]))
        right_value = Decimal(str(right["value"]))
        higher_ref = None
        if left_value > right_value:
            higher_ref = inputs[1].ref_id
        elif right_value > left_value:
            higher_ref = inputs[2].ref_id
        overlap = _executor_intervals_overlap(left.get("uncertainty"), right.get("uncertainty"))
        return {
            "higher_ref": higher_ref,
            "difference": str(abs(left_value - right_value)),
            "uncertainty_intervals_overlap": overlap,
            "qualified_conclusion": (
                "observed_difference_with_overlapping_uncertainty"
                if overlap
                else "observed_difference_with_separated_uncertainty"
            ),
        }


class EffectComparisonVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 3:
            return _verification(None, observed_output, "science_effect_comparison_arity")
        alignment = _mapping(inputs[0].value)
        if alignment.get("comparable") is not True:
            return _verification(None, observed_output, "science_protocol_comparable")
        first = _mapping(inputs[1].value)
        second = _mapping(inputs[2].value)
        first_value = Decimal(str(first["value"]))
        second_value = Decimal(str(second["value"]))
        higher_ref = (
            inputs[1].ref_id
            if first_value > second_value
            else inputs[2].ref_id
            if second_value > first_value
            else None
        )
        overlap = _oracle_intervals_overlap(first.get("uncertainty"), second.get("uncertainty"))
        expected = {
            "higher_ref": higher_ref,
            "difference": str(max(first_value, second_value) - min(first_value, second_value)),
            "uncertainty_intervals_overlap": overlap,
            "qualified_conclusion": (
                "observed_difference_with_overlapping_uncertainty"
                if overlap
                else "observed_difference_with_separated_uncertainty"
            ),
        }
        return _verification(expected, observed_output, "science_effect_comparison")


class DescriptiveSynthesisExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        del parameters
        if len(inputs) < 3:
            raise ValueError("descriptive synthesis requires at least three results")
        results = tuple(_mapping(item.value) for item in inputs)
        _require_same_protocol(results)
        total_sample_size = sum(int(item["sample_size"]) for item in results)
        if total_sample_size <= 0:
            raise ValueError("descriptive synthesis requires positive sample sizes")
        weighted = sum(
            Decimal(str(item["value"])) * int(item["sample_size"]) for item in results
        ) / Decimal(total_sample_size)
        intervals = tuple(_mapping(item["uncertainty"]) for item in results)
        return {
            "weighted_value": _decimal_text(weighted),
            "total_sample_size": total_sample_size,
            "uncertainty_lower": _decimal_text(
                min(Decimal(str(item["lower"])) for item in intervals)
            ),
            "uncertainty_upper": _decimal_text(
                max(Decimal(str(item["upper"])) for item in intervals)
            ),
            "qualified_conclusion": "descriptive_sample_size_weighted_summary_not_meta_analysis",
        }


class DescriptiveSynthesisVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        del parameters
        if len(inputs) < 3:
            return _verification(None, observed_output, "science_synthesis_minimum_inputs")
        results = tuple(_mapping(item.value) for item in inputs)
        signature_fields = ("metric", "unit", "dataset", "method", "protocol")
        first = results[0]
        if any(
            any(item.get(field) != first.get(field) for field in signature_fields)
            for item in results[1:]
        ):
            return _verification(None, observed_output, "science_synthesis_protocol_alignment")
        sample_sizes = tuple(int(item["sample_size"]) for item in results)
        total = sum(sample_sizes)
        if total <= 0:
            return _verification(None, observed_output, "science_synthesis_sample_size")
        numerator = sum(
            Decimal(str(result["value"])) * sample_size
            for result, sample_size in zip(results, sample_sizes, strict=True)
        )
        lower_values = tuple(
            Decimal(str(_mapping(item["uncertainty"])["lower"])) for item in results
        )
        upper_values = tuple(
            Decimal(str(_mapping(item["uncertainty"])["upper"])) for item in results
        )
        expected = {
            "weighted_value": _decimal_text(numerator / Decimal(total)),
            "total_sample_size": total,
            "uncertainty_lower": _decimal_text(min(lower_values)),
            "uncertainty_upper": _decimal_text(max(upper_values)),
            "qualified_conclusion": "descriptive_sample_size_weighted_summary_not_meta_analysis",
        }
        return _verification(expected, observed_output, "science_descriptive_synthesis")


def science_operation_registry() -> OperationRegistry:
    registry = default_registry()
    registry.register(
        make_operation_definition(
            "science_align_protocol",
            ProtocolAlignmentExecutor(),
            ProtocolAlignmentVerifier(),
            "two:any",
            "structured",
            "none",
            ("metric_aligned", "protocol_aligned", "dataset_aligned"),
            output_model=ScienceProtocolAlignment,
            tool_capability="protocol_analyzer",
            implementation_dependencies=(_mapping,),
        )
    )
    registry.register(
        make_operation_definition(
            "science_compare_effect",
            EffectComparisonExecutor(),
            EffectComparisonVerifier(),
            "many:any",
            "structured",
            "none",
            ("protocol_comparable", "uncertainty_preserved"),
            output_model=ScienceEffectComparison,
            tool_capability="protocol_analyzer",
            implementation_dependencies=(
                _mapping,
                _executor_intervals_overlap,
                _oracle_intervals_overlap,
            ),
        )
    )
    registry.register(
        make_operation_definition(
            "science_summarize_effects",
            DescriptiveSynthesisExecutor(),
            DescriptiveSynthesisVerifier(),
            "many:any",
            "structured",
            "none",
            (
                "protocol_comparable",
                "sample_size_positive",
                "uncertainty_preserved",
                "descriptive_not_causal",
            ),
            output_model=ScienceDescriptiveSynthesis,
            tool_capability="protocol_analyzer",
            implementation_dependencies=(
                _mapping,
                _require_same_protocol,
                _decimal_text,
            ),
        )
    )
    return registry


def _executor_intervals_overlap(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError("effect comparison requires uncertainty intervals")
    return Decimal(str(left["lower"])) <= Decimal(str(right["upper"])) and Decimal(
        str(right["lower"])
    ) <= Decimal(str(left["upper"]))


def _oracle_intervals_overlap(first: Any, second: Any) -> bool:
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ValueError("oracle comparison requires uncertainty intervals")
    first_lower = Decimal(str(first["lower"]))
    first_upper = Decimal(str(first["upper"]))
    second_lower = Decimal(str(second["lower"]))
    second_upper = Decimal(str(second["upper"]))
    return max(first_lower, second_lower) <= min(first_upper, second_upper)


def _require_same_protocol(results: tuple[dict[str, Any], ...]) -> None:
    first = results[0]
    fields = ("metric", "unit", "dataset", "method", "protocol")
    mismatches = [
        field
        for field in fields
        if any(item.get(field) != first.get(field) for item in results[1:])
    ]
    if mismatches:
        raise ValueError(f"results are not protocol-compatible: {mismatches}")


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude_none=True)
    if isinstance(value, dict):
        return value
    raise ValueError("science operation input must be structured")


def _verification(
    expected: dict[str, Any] | None, observed: dict[str, Any], invariant: str
) -> OperationVerification:
    passed = expected is not None and observed == expected
    return OperationVerification(
        passed=passed,
        expected_output=expected,
        invariant_failures=() if passed else (invariant,),
        message="Science operation verified" if passed else "Science operation mismatch",
    )
