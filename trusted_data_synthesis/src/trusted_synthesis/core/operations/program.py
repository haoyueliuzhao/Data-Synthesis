from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.core.task.program import InputRefKind, OperationNode, TaskProgram


class ProgramExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    program_id: str
    node_outputs: dict[str, dict[str, Any]]
    final_output: dict[str, Any]


class ProgramVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    program_id: str
    passed: bool
    node_statuses: dict[str, bool]
    invariant_failures: tuple[str, ...]
    independently_computed_output: dict[str, Any] | None


class ProgramExecutionError(ValueError):
    def __init__(self, node_id: str, error_code: str, message: str) -> None:
        self.node_id = node_id
        self.error_code = error_code
        super().__init__(f"{node_id}:{error_code}:{message}")


class TaskProgramExecutor:
    def __init__(self, registry: OperationRegistry):
        self.registry = registry

    def execute(
        self,
        program: TaskProgram,
        evidence_by_id: dict[str, EvidenceItem],
    ) -> ProgramExecution:
        outputs: dict[str, dict[str, Any]] = {}
        for node in program.nodes:
            try:
                inputs = _resolve_inputs(node, evidence_by_id, outputs)
                definition = self.registry.validate_node_contract(node)
                self.registry.validate_inputs(definition, inputs)
                self.registry.validate_compatibility(
                    definition,
                    _node_evidence(program, node.node_id, evidence_by_id),
                    node.parameters,
                )
                output = definition.executor.execute(inputs, node.parameters)
                self.registry.validate_output(definition, output)
                outputs[node.node_id] = output
            except (TypeError, ValueError) as exc:
                raise ProgramExecutionError(node.node_id, "execution_contract", str(exc)) from exc
        return ProgramExecution(
            program_id=program.program_id,
            node_outputs=outputs,
            final_output=outputs[program.output_node_id],
        )


class TaskProgramOracleVerifier:
    """Replays a program through verifier implementations, never executors."""

    def __init__(self, registry: OperationRegistry):
        self.registry = registry

    def verify(
        self,
        program: TaskProgram,
        evidence_by_id: dict[str, EvidenceItem],
        observed_node_outputs: dict[str, dict[str, Any]],
    ) -> ProgramVerification:
        independently_verified: dict[str, dict[str, Any]] = {}
        statuses: dict[str, bool] = {}
        failures: list[str] = []
        for node in program.nodes:
            try:
                inputs = _resolve_inputs(node, evidence_by_id, independently_verified)
                observed = observed_node_outputs.get(node.node_id, {})
                definition = self.registry.validate_node_contract(node)
                self.registry.validate_inputs(definition, inputs)
                self.registry.validate_compatibility(
                    definition,
                    _node_evidence(program, node.node_id, evidence_by_id),
                    node.parameters,
                )
                result = definition.oracle_verifier.verify(inputs, node.parameters, observed)
                if result.expected_output is not None:
                    self.registry.validate_output(definition, result.expected_output)
                    independently_verified[node.node_id] = result.expected_output
                statuses[node.node_id] = result.passed
                failures.extend(f"{node.node_id}:{item}" for item in result.invariant_failures)
            except (TypeError, ValueError) as exc:
                statuses[node.node_id] = False
                failures.append(f"{node.node_id}:verification_contract:{exc}")
        return ProgramVerification(
            program_id=program.program_id,
            passed=all(statuses.values()) and len(statuses) == len(program.nodes),
            node_statuses=statuses,
            invariant_failures=tuple(failures),
            independently_computed_output=independently_verified.get(program.output_node_id),
        )

    def derive_expected(
        self,
        program: TaskProgram,
        evidence_by_id: dict[str, EvidenceItem],
    ) -> ProgramExecution:
        """Compute gold outputs only through oracle verifier implementations."""

        outputs: dict[str, dict[str, Any]] = {}
        for node in program.nodes:
            try:
                inputs = _resolve_inputs(node, evidence_by_id, outputs)
                definition = self.registry.validate_node_contract(node)
                self.registry.validate_inputs(definition, inputs)
                self.registry.validate_compatibility(
                    definition,
                    _node_evidence(program, node.node_id, evidence_by_id),
                    node.parameters,
                )
                result = definition.oracle_verifier.verify(inputs, node.parameters, {})
                if result.expected_output is None:
                    raise ValueError("oracle produced no expected output")
                self.registry.validate_output(definition, result.expected_output)
                outputs[node.node_id] = result.expected_output
            except (TypeError, ValueError) as exc:
                raise ProgramExecutionError(node.node_id, "oracle_contract", str(exc)) from exc
        return ProgramExecution(
            program_id=program.program_id,
            node_outputs=outputs,
            final_output=outputs[program.output_node_id],
        )


def _resolve_inputs(
    node: OperationNode,
    evidence_by_id: dict[str, EvidenceItem],
    operation_outputs: dict[str, dict[str, Any]],
) -> tuple[OperationInput, ...]:
    resolved = []
    for ref in node.input_refs:
        value: Any
        if ref.kind == InputRefKind.EVIDENCE:
            try:
                value = evidence_by_id[ref.ref_id].payload
            except KeyError as exc:
                raise ValueError(f"program evidence input is missing: {ref.ref_id}") from exc
        else:
            try:
                value = operation_outputs[ref.ref_id]
            except KeyError as exc:
                raise ValueError(f"program operation input is missing: {ref.ref_id}") from exc
        if ref.selector:
            value = _select_value(value, ref.selector, ref.ref_id)
        resolved.append(OperationInput(ref_id=ref.ref_id, value=value))
    return tuple(resolved)


def _select_value(value: Any, selector: str, ref_id: str) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    current = value
    for segment in selector.split("."):
        if isinstance(current, BaseModel):
            current = current.model_dump(mode="python")
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"input selector {selector!r} is invalid for {ref_id}")
        current = current[segment]
    return current


def _node_evidence(
    program: TaskProgram,
    node_id: str,
    evidence_by_id: dict[str, EvidenceItem],
) -> tuple[EvidenceItem, ...]:
    nodes = {node.node_id: node for node in program.nodes}
    collected: list[EvidenceItem] = []
    visited: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)
        node = nodes[current_id]
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                if ref.ref_id in evidence_by_id:
                    collected.append(evidence_by_id[ref.ref_id])
            else:
                visit(ref.ref_id)

    visit(node_id)
    unique = []
    seen_ids: set[str] = set()
    for item in collected:
        if item.evidence_id not in seen_ids:
            seen_ids.add(item.evidence_id)
            unique.append(item)
    return tuple(unique)
