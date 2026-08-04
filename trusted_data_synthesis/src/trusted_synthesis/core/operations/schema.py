from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class OperationInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    ref_id: str
    value: Any


class OperationVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    expected_output: dict[str, Any] | None = None
    invariant_failures: tuple[str, ...] = ()
    message: str


class OperationExecutor(Protocol):
    def execute(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
    ) -> dict[str, Any]: ...


class OperationOracleVerifier(Protocol):
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification: ...


@dataclass(frozen=True)
class OperationDefinition:
    """In-process registry record; only its manifest is serialized."""

    operator_id: str
    verifier_id: str
    executor: OperationExecutor
    oracle_verifier: OperationOracleVerifier
    input_schema: str
    output_schema: str
    compatibility_policy: str
    invariant_checks: tuple[str, ...]
    output_model: type[BaseModel] | None
    tool_capability: str | None
    action_type: str
    execution_mode: str
    program_role: str
    input_role_contract: tuple[str, ...]
    parameter_contract: tuple[str, ...]
    downstream_selector_contract: tuple[str, ...]
    executor_version: str
    verifier_version: str
    semantic_version: str
    formula_id: str
    rounding_policy: str
    tolerance_policy: str
    implementation_hash: str
    implementation_dependency_ids: tuple[str, ...]
    input_order_policy: str = "ordered"
