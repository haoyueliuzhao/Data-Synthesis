from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class InputRefKind(str, Enum):
    EVIDENCE = "evidence"
    OPERATION = "operation"


class ProgramInputRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: InputRefKind
    ref_id: str = Field(min_length=1)
    selector: str | None = None


class OperationNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    input_refs: tuple[ProgramInputRef, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)
    verifier_id: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()


class TaskProgram(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    program_id: str = Field(min_length=1)
    nodes: tuple[OperationNode, ...] = Field(min_length=1)
    output_node_id: str = Field(min_length=1)
    program_version: str = "task_program.v2"

    @model_validator(mode="after")
    def validate_dag(self) -> TaskProgram:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("task program contains duplicate node IDs")
        if self.output_node_id not in set(node_ids):
            raise ValueError("task program output node is missing")
        seen: set[str] = set()
        for node in self.nodes:
            dependencies = set(node.dependencies)
            referenced_operations = {
                ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.OPERATION
            }
            if dependencies != referenced_operations:
                raise ValueError(
                    f"operation dependencies do not match input refs for {node.node_id}"
                )
            if not dependencies.issubset(seen):
                raise ValueError(f"task program is not topologically ordered at {node.node_id}")
            seen.add(node.node_id)
        return self

    @property
    def program_hash(self) -> str:
        return canonical_hash(self, prefix="program:")

    @property
    def semantic_hash(self) -> str:
        """Hash the operation structure without binding it to evidence versions."""

        node_positions = {node.node_id: index for index, node in enumerate(self.nodes)}
        evidence_roles: dict[str, int] = {}
        normalized_nodes = []
        for node in self.nodes:
            refs = []
            for ref in node.input_refs:
                if ref.kind == InputRefKind.OPERATION:
                    normalized_ref = f"operation:{node_positions[ref.ref_id]}"
                else:
                    role = evidence_roles.setdefault(ref.ref_id, len(evidence_roles))
                    normalized_ref = f"evidence_role:{role}"
                refs.append(
                    {
                        "kind": ref.kind.value,
                        "ref": normalized_ref,
                        "selector": ref.selector,
                    }
                )
            normalized_nodes.append(
                {
                    "position": node_positions[node.node_id],
                    "operator_id": node.operator_id,
                    "input_refs": refs,
                    "parameters": node.parameters,
                    "output_schema": node.output_schema,
                    "verifier_id": node.verifier_id,
                    "dependencies": sorted(node_positions[item] for item in node.dependencies),
                }
            )
        return canonical_hash(
            {
                "nodes": normalized_nodes,
                "output_position": node_positions[self.output_node_id],
                "version": self.program_version,
            },
            prefix="program_semantic:",
        )


def make_program(nodes: tuple[OperationNode, ...], output_node_id: str) -> TaskProgram:
    identity = {
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "output_node_id": output_node_id,
        "version": "task_program.v2",
    }
    return TaskProgram(
        program_id=canonical_hash(identity, prefix="program:"),
        nodes=nodes,
        output_node_id=output_node_id,
    )
