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
            inputs = _resolve_inputs(node, evidence_by_id, outputs)
            definition = self.registry.require(node.operator_id)
            outputs[node.node_id] = definition.executor.execute(inputs, node.parameters)
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
            inputs = _resolve_inputs(node, evidence_by_id, independently_verified)
            observed = observed_node_outputs.get(node.node_id, {})
            definition = self.registry.require(node.operator_id)
            result = definition.oracle_verifier.verify(inputs, node.parameters, observed)
            statuses[node.node_id] = result.passed
            if result.expected_output is not None:
                independently_verified[node.node_id] = result.expected_output
            failures.extend(f"{node.node_id}:{item}" for item in result.invariant_failures)
        return ProgramVerification(
            program_id=program.program_id,
            passed=all(statuses.values()) and len(statuses) == len(program.nodes),
            node_statuses=statuses,
            invariant_failures=tuple(failures),
            independently_computed_output=independently_verified.get(program.output_node_id),
        )


def _resolve_inputs(
    node: OperationNode,
    evidence_by_id: dict[str, EvidenceItem],
    operation_outputs: dict[str, dict[str, Any]],
) -> tuple[OperationInput, ...]:
    resolved = []
    for ref in node.input_refs:
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
        resolved.append(OperationInput(ref_id=ref.ref_id, value=value))
    return tuple(resolved)
