from __future__ import annotations

import inspect
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.executors import (
    AggregateExecutor,
    CompareExecutor,
    DifferenceExecutor,
    GrowthExecutor,
    LookupExecutor,
    RatioExecutor,
)
from trusted_synthesis.core.operations.schema import OperationDefinition, OperationInput
from trusted_synthesis.core.operations.verifiers import (
    AggregateOracleVerifier,
    CompareOracleVerifier,
    DifferenceOracleVerifier,
    GrowthOracleVerifier,
    LookupOracleVerifier,
    RatioOracleVerifier,
)
from trusted_synthesis.core.task.program import OperationNode
from trusted_synthesis.hashing import canonical_hash


class OperationContractError(ValueError):
    """A program node does not satisfy its frozen registry contract."""


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

    def validate_node_contract(self, node: OperationNode) -> OperationDefinition:
        definition = self.require(node.operator_id)
        failures = []
        if node.verifier_id != definition.verifier_id:
            failures.append(
                f"verifier_id={node.verifier_id!r}, expected={definition.verifier_id!r}"
            )
        if node.output_schema != definition.output_schema:
            failures.append(
                f"output_schema={node.output_schema!r}, expected={definition.output_schema!r}"
            )
        if failures:
            raise OperationContractError(
                f"operation node contract failed for {node.node_id}: {'; '.join(failures)}"
            )
        return definition

    @staticmethod
    def validate_inputs(
        definition: OperationDefinition, inputs: tuple[OperationInput, ...]
    ) -> None:
        cardinality, value_type = definition.input_schema.split(":", maxsplit=1)
        expected = {"one": 1, "two": 2}.get(cardinality)
        if expected is not None and len(inputs) != expected:
            raise OperationContractError(
                f"{definition.operator_id} requires {expected} inputs, received {len(inputs)}"
            )
        if cardinality == "many" and not inputs:
            raise OperationContractError(f"{definition.operator_id} requires non-empty inputs")
        if "numeric" in value_type:
            invalid = [item.ref_id for item in inputs if not _is_numeric(item.value)]
            if invalid:
                raise OperationContractError(
                    f"{definition.operator_id} received non-numeric inputs: {invalid}"
                )

    @staticmethod
    def validate_output(definition: OperationDefinition, output: dict[str, Any]) -> None:
        required_fields = {
            "payload": {"selected_ref", "payload"},
            "comparison": {"higher_ref", "difference"},
            "scalar": {"value"},
            "percentage": {"value"},
        }.get(definition.output_schema, set())
        missing = required_fields - set(output)
        if missing:
            raise OperationContractError(
                f"{definition.operator_id} output is missing fields: {sorted(missing)}"
            )

    @staticmethod
    def validate_compatibility(
        definition: OperationDefinition,
        evidence: tuple[EvidenceItem, ...],
        parameters: dict[str, Any],
    ) -> None:
        policy = definition.compatibility_policy
        if policy == "none":
            return
        if not evidence:
            raise OperationContractError(
                f"{definition.operator_id} has no evidence lineage for {policy}"
            )
        scalar = [item for item in evidence if isinstance(item.payload, ScalarObservation)]
        if len(scalar) != len(evidence):
            raise OperationContractError(
                f"{definition.operator_id} compatibility requires scalar evidence"
            )
        fields: tuple[str, ...]
        if policy == "same_unit_and_definition":
            fields = ("predicate", "payload_context", "definition")
        elif policy == "same_series":
            fields = (
                "subject",
                "predicate",
                "payload_context",
                "definition",
                "time_basis",
                "frequency",
                "scope_type",
            )
        elif policy == "same_metric_unit_definition":
            fields = ("predicate", "payload_context", "definition")
        elif policy == "registered_ratio_pair":
            if len(evidence) != 2 or any(not item.definition.definition_id for item in evidence):
                raise OperationContractError("ratio inputs require registered definitions")
            expected_pair = f"{evidence[0].predicate}/{evidence[1].predicate}"
            if parameters.get("registered_pair") != expected_pair:
                raise OperationContractError(
                    f"ratio pair is not explicitly registered: {expected_pair}"
                )
            return
        else:
            raise OperationContractError(f"unknown compatibility policy: {policy}")
        signatures = [_compatibility_signature(item) for item in evidence]
        required_non_empty = set(fields)
        missing = [
            field
            for field in required_non_empty
            if any(signature[field] in (None, "") for signature in signatures)
        ]
        mismatches = [
            field for field in fields if len({signature[field] for signature in signatures}) != 1
        ]
        if missing or mismatches:
            raise OperationContractError(
                f"{definition.operator_id} compatibility mismatch: "
                f"missing={missing}, unequal={mismatches}"
            )

    def manifest(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "operator_id": item.operator_id,
                "verifier_id": item.verifier_id,
                "input_schema": item.input_schema,
                "output_schema": item.output_schema,
                "compatibility_policy": item.compatibility_policy,
                "invariant_checks": item.invariant_checks,
                "executor": type(item.executor).__name__,
                "oracle_verifier": type(item.oracle_verifier).__name__,
                "executor_version": item.executor_version,
                "verifier_version": item.verifier_version,
                "semantic_version": item.semantic_version,
                "formula_id": item.formula_id,
                "rounding_policy": item.rounding_policy,
                "tolerance_policy": item.tolerance_policy,
                "implementation_hash": item.implementation_hash,
            }
            for item in sorted(self._definitions.values(), key=lambda value: value.operator_id)
        )


def default_registry() -> OperationRegistry:
    definitions = (
        make_operation_definition(
            "lookup",
            LookupExecutor(),
            LookupOracleVerifier(),
            "one:any",
            "payload",
            "none",
            ("arity=1",),
        ),
        make_operation_definition(
            "compare",
            CompareExecutor(),
            CompareOracleVerifier(),
            "two:numeric",
            "comparison",
            "same_unit_and_definition",
            ("arity=2",),
        ),
        make_operation_definition(
            "difference",
            DifferenceExecutor(),
            DifferenceOracleVerifier(),
            "two:numeric",
            "scalar",
            "same_unit_and_definition",
            ("arity=2",),
        ),
        make_operation_definition(
            "ratio",
            RatioExecutor(),
            RatioOracleVerifier(),
            "two:numeric",
            "scalar",
            "registered_ratio_pair",
            ("arity=2", "denominator_non_zero"),
        ),
        make_operation_definition(
            "growth",
            GrowthExecutor(),
            GrowthOracleVerifier(),
            "two:ordered_numeric",
            "percentage",
            "same_series",
            ("arity=2", "base_non_zero"),
            verifier_version="1.0.1",
            semantic_version="1.0.1",
            formula_id="growth.relative_change_abs_base.v1",
        ),
        make_operation_definition(
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


def make_operation_definition(
    operator_id,
    executor,
    verifier,
    input_schema,
    output_schema,
    compatibility_policy,
    invariants,
    *,
    executor_version="1.0.0",
    verifier_version="1.0.0",
    semantic_version="1.0.0",
    formula_id=None,
) -> OperationDefinition:
    implementation_hash = canonical_hash(
        {
            "executor": inspect.getsource(type(executor)),
            "verifier": inspect.getsource(type(verifier)),
        },
        prefix="operation_implementation:",
    )
    return OperationDefinition(
        operator_id=operator_id,
        verifier_id=f"{operator_id}.oracle.v1",
        executor=executor,
        oracle_verifier=verifier,
        input_schema=input_schema,
        output_schema=output_schema,
        compatibility_policy=compatibility_policy,
        invariant_checks=invariants,
        executor_version=executor_version,
        verifier_version=verifier_version,
        semantic_version=semantic_version,
        formula_id=formula_id or f"{operator_id}.formula.v1",
        rounding_policy="decimal_exact_no_implicit_rounding",
        tolerance_policy="exact_decimal_and_exact_structure",
        implementation_hash=implementation_hash,
    )


def _is_numeric(value: Any) -> bool:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        nested = value.get("payload")
        value = value.get("value", nested.get("value") if isinstance(nested, dict) else value)
    try:
        Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return True


def _compatibility_signature(evidence: EvidenceItem) -> dict[str, Any]:
    payload = evidence.payload
    payload_value = payload.model_dump(mode="json", exclude_none=True)
    payload_context = {
        key: value
        for key, value in payload_value.items()
        if key not in {"kind", "value", "precision"}
    }
    return {
        "subject": evidence.subject.subject_id,
        "predicate": evidence.predicate,
        "payload_context": canonical_hash(payload_context, prefix="payload_context:"),
        "definition": evidence.definition.definition_id,
        "time_basis": evidence.temporal_context.basis,
        "frequency": evidence.temporal_context.frequency,
        "scope_type": evidence.scope.scope_type if evidence.scope else None,
    }
